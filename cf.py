"""
cf.py - Cash flow di cantiere: portafoglio di commesse, incassi e pagamenti mese per mese, fabbisogno di cassa.

Deterministico e senza Streamlit (testabile). Importi in EUR al netto di IVA (l'IVA non e' modellata: va gestita a parte).

Modello, per ogni cantiere (contratto C, inizio mese s, durata d, fine e = s + d - 1):
  Fatturazione   anticipo% di C nel mese s; saldo% nel mese e; il resto (100 - anticipo - saldo)% in rate uguali
                 (stati di avanzamento) in ciascun mese da s a e
  Incasso        ogni fatturazione si incassa dopo `Gg_incasso` giorni (le frazioni di mese si ripartiscono tra due mesi)
  Costi          Costi% di C, uniformi da s a e, pagati dopo `gg_pagamento` giorni
  Costi generali importo fisso mensile per tutto l'orizzonte
  Cassa          cassa(t) = cassa(t-1) + incassi - pagamenti - costi generali - interessi
                 interessi(t) = max(0, -cassa(t-1)) x tasso scoperto / 12
"""
import math

from core import fmt_num, to_float

CF_DEFAULT = {
    "mesi": 18,                 # orizzonte di calcolo
    "cassa0": 0.0,              # cassa iniziale
    "fido": 300_000.0,          # affidamento bancario disponibile
    "tasso_scoperto": 8.0,      # % annuo sugli importi in scoperto
    "costi_generali": 25_000.0,  # costi fissi mensili (struttura, uffici, mezzi...)
    "gg_pagamento": 60,         # giorni medi di pagamento dei fornitori e dei subappaltatori
    # ipotesi di stress (applicate a tutto il portafoglio)
    "gg_incasso_extra": 0,
    "costi_extra_pct": 0.0,
    "ritardo_avvio": 0,
}

COLONNE_CANTIERI = ["Cantiere", "Contratto", "Inizio", "Durata", "Anticipo_pct", "Saldo_pct", "Gg_incasso", "Costi_pct"]
ETICHETTE_COLONNE = {
    "Cantiere": "Cantiere", "Contratto": "Contratto (€)", "Inizio": "Mese di inizio", "Durata": "Durata (mesi)",
    "Anticipo_pct": "Anticipo (%)", "Saldo_pct": "Saldo a fine lavori (%)", "Gg_incasso": "Giorni di incasso",
    "Costi_pct": "Costi (% del contratto)",
}
LIMITI_CF = {"mesi": (6, 60), "tasso_scoperto": (0.0, 30.0), "gg_pagamento": (0, 365), "gg_incasso_extra": (0, 365),
             "costi_extra_pct": (-50.0, 100.0), "ritardo_avvio": (0, 12)}


# ----------------------------------------------------------------------------
# PORTAFOGLIO
# ----------------------------------------------------------------------------
def genera_portafoglio(n, totale, mese_primo=1, mese_ultimo=12, durata=3, anticipo=50.0, saldo=50.0, gg_incasso=30,
                       costi_pct=75.0, prefisso="Cantiere"):
    """`n` cantieri uguali per importo (totale / n) con partenze distribuite in modo uniforme tra mese_primo e mese_ultimo."""
    n = int(max(1, n))
    mese_primo, mese_ultimo = int(max(1, mese_primo)), int(max(mese_primo, mese_ultimo))
    righe = []
    for i in range(n):
        if n == 1:
            m = mese_primo
        else:
            m = mese_primo + round(i * (mese_ultimo - mese_primo) / (n - 1))
        righe.append({"Cantiere": f"{prefisso} {i + 1:03d}", "Contratto": float(totale) / n, "Inizio": int(m), "Durata": int(max(1, durata)),
                      "Anticipo_pct": float(anticipo), "Saldo_pct": float(saldo), "Gg_incasso": int(gg_incasso),
                      "Costi_pct": float(costi_pct)})
    return righe


def normalizza_cantieri(righe):
    """Pulisce le righe (da editor o file): restituisce (cantieri validi, avvisi). Le righe vuote o con contratto <= 0 sono scartate."""
    puliti, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        contratto = to_float(r.get("Contratto"), 0.0)
        if contratto <= 0:
            if any(str(r.get(c) or "").strip() for c in COLONNE_CANTIERI if c != "Cantiere") or str(r.get("Cantiere") or "").strip():
                avvisi.append(f"Riga {i}: contratto nullo o non valido, riga ignorata.")
            continue
        nome = str(r.get("Cantiere") or "").strip() or f"Cantiere {len(puliti) + 1:03d}"
        inizio = int(max(1, round(to_float(r.get("Inizio"), 1) or 1)))
        durata = int(max(1, round(to_float(r.get("Durata"), 1) or 1)))
        anticipo = min(100.0, max(0.0, to_float(r.get("Anticipo_pct"), 0.0)))
        saldo = min(100.0, max(0.0, to_float(r.get("Saldo_pct"), 0.0)))
        if anticipo + saldo > 100.0 + 1e-9:
            avvisi.append(f"{nome}: anticipo + saldo superano il 100%: saldo ridotto a {fmt_num(100 - anticipo, 0)}%.")
            saldo = 100.0 - anticipo
        gg = int(min(365, max(0, round(to_float(r.get("Gg_incasso"), 30)))))
        costi = min(150.0, max(0.0, to_float(r.get("Costi_pct"), 75.0)))
        puliti.append({"Cantiere": nome, "Contratto": contratto, "Inizio": inizio, "Durata": durata, "Anticipo_pct": anticipo,
                       "Saldo_pct": saldo, "Gg_incasso": gg, "Costi_pct": costi})
    return puliti, avvisi


# ----------------------------------------------------------------------------
# CALCOLO
# ----------------------------------------------------------------------------
def _sposta(serie, giorni):
    """Ritarda i flussi di `giorni` (mesi da 30 giorni): la parte frazionaria si ripartisce tra due mesi consecutivi.
    Restituisce (nuova serie della stessa lunghezza, importo che cade oltre l'orizzonte)."""
    n = len(serie)
    mesi = max(0.0, giorni) / 30.0
    k = int(math.floor(mesi))
    f = mesi - k
    out, fuori = [0.0] * n, 0.0
    for t, v in enumerate(serie):
        if not v:
            continue
        for sh, w in ((k, 1.0 - f), (k + 1, f)):
            if w <= 0:
                continue
            if t + sh < n:
                out[t + sh] += v * w
            else:
                fuori += v * w
    return out, fuori


def _clamp(chiave, v):
    lo, hi = LIMITI_CF.get(chiave, (-math.inf, math.inf))
    return min(max(v, lo), hi)


def calcola_cf(cantieri, p=None):
    """Calcola il cash flow mensile del portafoglio. `cantieri`: righe gia' normalizzate (normalizza_cantieri)."""
    q = {**CF_DEFAULT, **(p or {})}
    for k in LIMITI_CF:
        q[k] = _clamp(k, to_float(q[k], CF_DEFAULT[k]))
    n = int(q["mesi"])
    ritardo = int(q["ritardo_avvio"])
    inc, pag = [0.0] * n, [0.0] * n
    ric_comp, cos_comp = [0.0] * n, [0.0] * n
    attivi = [0] * n
    dettaglio, fuori_inc, fuori_pag = [], 0.0, 0.0
    for c in cantieri:
        s = c["Inizio"] + ritardo
        d = c["Durata"]
        e = s + d - 1
        C = c["Contratto"]
        costi_pct = c["Costi_pct"] + q["costi_extra_pct"]
        fatt, cost = [0.0] * n, [0.0] * n
        rata_sal = (100.0 - c["Anticipo_pct"] - c["Saldo_pct"]) / 100.0 * C / d
        for m in range(s, e + 1):
            if 1 <= m <= n:
                i = m - 1
                fatt[i] += rata_sal
                cost[i] += C * max(0.0, costi_pct) / 100.0 / d
                ric_comp[i] += C / d
                cos_comp[i] += C * max(0.0, costi_pct) / 100.0 / d
                attivi[i] += 1
        if 1 <= s <= n:
            fatt[s - 1] += C * c["Anticipo_pct"] / 100.0
        if 1 <= e <= n:
            fatt[e - 1] += C * c["Saldo_pct"] / 100.0
        inc_c, f_i = _sposta(fatt, c["Gg_incasso"] + q["gg_incasso_extra"])
        pag_c, f_p = _sposta(cost, q["gg_pagamento"])
        for i in range(n):
            inc[i] += inc_c[i]
            pag[i] += pag_c[i]
        fuori_inc += f_i
        fuori_pag += f_p
        costi_tot = C * max(0.0, costi_pct) / 100.0
        dettaglio.append({
            "Cantiere": c["Cantiere"], "Contratto": C, "Inizio": s, "Fine": e, "Margine": C - costi_tot,
            "Margine %": (C - costi_tot) / C * 100.0, "Incassato nel periodo": sum(inc_c),
            "Incassi oltre l'orizzonte": f_i,
            "Oltre l'orizzonte": e > n,
        })
    righe, cassa = [], q["cassa0"]
    cum_ric = cum_cos = cum_inc = cum_pag = 0.0
    interessi_tot, primo_fuori_fido = 0.0, None
    for t in range(n):
        interessi = max(0.0, -cassa) * q["tasso_scoperto"] / 100.0 / 12.0
        flusso = inc[t] - pag[t] - q["costi_generali"]
        cassa = cassa + flusso - interessi
        interessi_tot += interessi
        cum_ric += ric_comp[t]
        cum_cos += cos_comp[t]
        cum_inc += inc[t]
        cum_pag += pag[t]
        utilizzo = max(0.0, -cassa)
        if primo_fuori_fido is None and utilizzo > q["fido"] + 1e-9:
            primo_fuori_fido = t + 1
        righe.append({
            "Mese": t + 1, "Cantieri attivi": attivi[t], "Ricavi di competenza": ric_comp[t], "Costi di competenza": cos_comp[t],
            "Incassi": inc[t], "Pagamenti": pag[t], "Costi generali": q["costi_generali"], "Interessi": interessi,
            "Flusso netto": flusso - interessi, "Cassa finale": cassa, "Utilizzo scoperto": utilizzo,
            "Fido residuo": q["fido"] - utilizzo,
            "Crediti netti": cum_ric - cum_inc, "Debiti fornitori": cum_cos - cum_pag,
        })
    utilizzi = [r["Utilizzo scoperto"] for r in righe]
    picco = max(utilizzi) if utilizzi else 0.0
    mese_picco = (utilizzi.index(picco) + 1) if picco > 0 else None
    contratti = sum(c["Contratto"] for c in cantieri)
    costi_diretti = sum(c["Contratto"] * max(0.0, c["Costi_pct"] + q["costi_extra_pct"]) / 100.0 for c in cantieri)
    margine_lordo = contratti - costi_diretti
    gg_medio = (sum(c["Gg_incasso"] * c["Contratto"] for c in cantieri) / contratti) if contratti else 0.0
    kpi = {
        "n_cantieri": len(cantieri), "contratti": contratti, "costi_diretti": costi_diretti, "margine_lordo": margine_lordo,
        "margine_lordo_pct": (margine_lordo / contratti * 100.0) if contratti else 0.0,
        "costi_generali_tot": q["costi_generali"] * n, "margine_netto": margine_lordo - q["costi_generali"] * n,
        "cassa_finale": righe[-1]["Cassa finale"] if righe else q["cassa0"],
        "cassa_minima": min([q["cassa0"]] + [r["Cassa finale"] for r in righe]),
        "picco_fabbisogno": picco, "mese_picco": mese_picco, "mesi_in_scoperto": sum(1 for u in utilizzi if u > 0),
        "fido": q["fido"], "primo_mese_fuori_fido": primo_fuori_fido, "interessi_totali": interessi_tot,
        "incassi_tot": sum(inc), "pagamenti_tot": sum(pag), "gg_incasso_medio": gg_medio,
        "incassi_oltre_orizzonte": fuori_inc, "pagamenti_oltre_orizzonte": fuori_pag, "mesi": n,
        "cantieri_oltre_orizzonte": sum(1 for d_ in dettaglio if d_["Oltre l'orizzonte"]),
    }
    out = {"params": q, "mesi": righe, "cantieri": dettaglio, "kpi": kpi}
    out["avvisi"] = valida_cf(q, out)
    return out


def valida_cf(q, out):
    k, w = out["kpi"], []
    if k["n_cantieri"] == 0:
        return ["Nessun cantiere nel portafoglio: aggiungi almeno una riga con un contratto."]
    if k["primo_mese_fuori_fido"]:
        w.append(f"Dal mese {k['primo_mese_fuori_fido']} lo scoperto supera il fido ({fmt_num(q['fido'])} EUR): picco di {fmt_num(k['picco_fabbisogno'])} EUR "
                 f"al mese {k['mese_picco']}. Servono piu' liquidita', anticipi maggiori o incassi piu' rapidi.")
    elif k["picco_fabbisogno"] > 0:
        w.append(f"La cassa va in scoperto per {k['mesi_in_scoperto']} mesi, con un picco di {fmt_num(k['picco_fabbisogno'])} EUR al mese "
                 f"{k['mese_picco']}: dentro il fido ({fmt_num(q['fido'])} EUR) ma da monitorare. Interessi stimati: {fmt_num(k['interessi_totali'])} EUR.")
    if k["margine_netto"] < 0:
        w.append("Il margine netto del portafoglio (dopo i costi generali) e' negativo nell'orizzonte considerato.")
    for d in out["cantieri"]:
        if d["Margine"] < 0:
            w.append(f"{d['Cantiere']}: costi superiori al contratto (margine negativo).")
            break
    if k["cantieri_oltre_orizzonte"]:
        w.append(f"{k['cantieri_oltre_orizzonte']} cantieri finiscono oltre l'orizzonte di {k['mesi']} mesi: parte di incassi e costi non e' inclusa. Allunga l'orizzonte.")
    if k["incassi_oltre_orizzonte"] > 1:
        w.append(f"{fmt_num(k['incassi_oltre_orizzonte'])} EUR di incassi cadono dopo l'orizzonte del calcolo.")
    if k["gg_incasso_medio"] > q["gg_pagamento"] + 30:
        w.append(f"Incassate in media a {fmt_num(k['gg_incasso_medio'], 0)} giorni ma pagate i fornitori a {fmt_num(q['gg_pagamento'], 0)}: "
                 "la differenza va finanziata con la vostra cassa.")
    return w


# ----------------------------------------------------------------------------
# STRESS TEST E FABBISOGNO
# ----------------------------------------------------------------------------
STRESS_DEFAULT = {
    "Base": {},
    "Incassi +30 giorni": {"gg_incasso_extra": 30},
    "Incassi +60 giorni": {"gg_incasso_extra": 60},
    "Costi +10%": {"costi_extra_pct": 10.0},
    "Avvio cantieri +1 mese": {"ritardo_avvio": 1},
    "Combinato (+30 gg, +5% costi, +1 mese)": {"gg_incasso_extra": 30, "costi_extra_pct": 5.0, "ritardo_avvio": 1},
}


def stress_cf(cantieri, p=None, casi=None):
    """{nome caso: risultato}. Le ipotesi di stress si sommano a quelle gia' presenti in `p`."""
    p = p or {}
    out = {}
    for nome, delta in (casi or STRESS_DEFAULT).items():
        q = dict(p)
        for k, v in delta.items():
            q[k] = to_float(q.get(k, CF_DEFAULT[k]), 0.0) + v
        out[nome] = calcola_cf(cantieri, q)
    return out


def confronto_stress(risultati):
    base = next(iter(risultati.values()))["kpi"]["picco_fabbisogno"]
    righe = []
    for nome, o in risultati.items():
        k = o["kpi"]
        righe.append({"Caso": nome, "Picco fabbisogno": k["picco_fabbisogno"], "Mese del picco": k["mese_picco"],
                      "Cassa minima": k["cassa_minima"], "Cassa finale": k["cassa_finale"], "Interessi": k["interessi_totali"],
                      "Fuori fido dal mese": k["primo_mese_fuori_fido"], "Variazione picco": k["picco_fabbisogno"] - base})
    return righe


def anticipo_minimo(cantieri, p=None, soglia=0.0, passo=5):
    """Anticipo % (uguale per tutti i cantieri, saldo ridotto di conseguenza) minimo per cui lo scoperto massimo non supera `soglia`.
    None se neanche con il 100% di anticipo si rispetta la soglia."""
    for a in range(0, 101, passo):
        mod = [{**c, "Anticipo_pct": float(a), "Saldo_pct": min(c["Saldo_pct"], 100.0 - a)} for c in cantieri]
        if calcola_cf(mod, p)["kpi"]["picco_fabbisogno"] <= soglia + 1e-6:
            return a
    return None


def da_dataframe(df):
    """Righe dict da un DataFrame pandas (colonne come COLONNE_CANTIERI)."""
    return [{c: (None if c not in df.columns else df.iloc[i][c]) for c in COLONNE_CANTIERI} for i in range(len(df))]
