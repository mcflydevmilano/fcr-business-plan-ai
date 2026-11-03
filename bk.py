"""
bk.py - Riconciliazione bancaria: abbina i movimenti del conto corrente alle fatture dello Scadenzario.
Deterministico e senza Streamlit. Propone gli abbinamenti con un punteggio e i motivi: l'ultima parola e' sempre di chi li conferma.
"""
import re

from core import fmt_num, to_float
from sc import data_da

COLONNE_MOV = ["Data", "Descrizione", "Importo", "Conto"]
ETICHETTE_MOV = {"Data": "Data", "Descrizione": "Causale / descrizione", "Importo": "Importo (entrate +, uscite −)", "Conto": "Conto corrente"}
COLONNE_CONTI = ["Conto", "Banca", "Iban", "Cantiere", "Saldo_iniziale", "Fido"]
ETICHETTE_CONTI = {"Conto": "Nome del conto", "Banca": "Banca", "Iban": "IBAN", "Cantiere": "Cantiere (vuoto = conto generale)", "Saldo_iniziale": "Saldo iniziale (€)", "Fido": "Fido concesso (€)"}
COLONNE_DEBITI = ["Conto", "Descrizione", "Residuo", "Rata", "Ogni_mesi", "Prossima_rata"]
ETICHETTE_DEBITI = {"Conto": "Conto", "Descrizione": "Debito (mutuo, leasing, anticipo fatture...)", "Residuo": "Residuo da restituire (€)", "Rata": "Rata (€)",
                    "Ogni_mesi": "Una rata ogni (mesi)", "Prossima_rata": "Prossima rata"}
SENZA_CONTO = "(senza conto)"
SINONIMI_MOV = {"Data": ("Data operazione", "Data valuta", "Data contabile"), "Descrizione": ("Causale", "Descrizione operazione", "Dettagli", "Operazione"),
                "Importo": ("Dare/Avere", "Saldo movimento", "Ammontare", "Movimento")}
BK_DEFAULT = {"sicuro": 70, "possibile": 40, "tolleranza": 0.05, "finestra_gg": 120}
_STOP = {"srl", "spa", "snc", "sas", "di", "e", "il", "la", "lo", "dei", "del", "della", "costruzioni", "edile", "impianti", "societa", "soc", "coop", "bonifico", "fattura", "fatt", "saldo", "pagamento", "a", "da", "per"}


def _s(v):
    """Testo pulito; i vuoti di Excel/pandas (None, NaN) diventano stringa vuota."""
    if v is None or (isinstance(v, float) and v != v):
        return ""
    return str(v).strip()


def _k(v):
    return " ".join(_s(v).lower().split())


def normalizza_movimenti(righe):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(_s(r.get(c)) for c in COLONNE_MOV):
            continue
        d, imp = data_da(r.get("Data")), to_float(r.get("Importo"), 0.0)
        if d is None or abs(imp) < 0.005:
            avvisi.append(f"Movimento, riga {i}: data o importo non validi, riga ignorata.")
            continue
        out.append({"Data": d.isoformat(), "Descrizione": _s(r.get("Descrizione")), "Importo": round(imp, 2), "Conto": _s(r.get("Conto"))})
    return out, avvisi


def normalizza_conti(righe):
    """Conti correnti (uno per riga). Il nome e' la chiave: si usa nei movimenti e nei debiti. Restituisce (conti, avvisi)."""
    out, avvisi, visti = [], [], set()
    for i, r in enumerate(righe or [], start=1):
        if not any(_s(r.get(c)) for c in COLONNE_CONTI):
            continue
        nome = _s(r.get("Conto"))
        if not nome:
            avvisi.append(f"Conto, riga {i}: manca il nome, riga ignorata.")
            continue
        if _k(nome) in visti:
            avvisi.append(f"Il conto «{nome}» compare più di una volta: tengo la prima riga.")
            continue
        visti.add(_k(nome))
        out.append({"Conto": nome, "Banca": _s(r.get("Banca")), "Iban": _s(r.get("Iban")).replace(" ", "").upper(), "Cantiere": _s(r.get("Cantiere")),
                    "Saldo_iniziale": round(to_float(r.get("Saldo_iniziale"), 0.0), 2), "Fido": round(max(0.0, to_float(r.get("Fido"), 0.0)), 2)})
    return out, avvisi


def normalizza_debiti(righe, conti=None):
    """Debiti legati a un conto (mutuo, leasing, anticipi). Restituisce (debiti, avvisi)."""
    nomi = {_k(c["Conto"]) for c in (conti or [])}
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(_s(r.get(c)) for c in COLONNE_DEBITI):
            continue
        desc, residuo, rata = _s(r.get("Descrizione")), to_float(r.get("Residuo"), 0.0), to_float(r.get("Rata"), 0.0)
        if not desc or residuo <= 0:
            avvisi.append(f"Debito, riga {i}: servono descrizione e residuo maggiore di zero, riga ignorata.")
            continue
        conto = _s(r.get("Conto"))
        if conti is not None and _k(conto) not in nomi:
            avvisi.append(f"Debito «{desc}»: il conto «{conto or 'non indicato'}» non è nell'elenco dei conti, il debito non conta in nessun prospetto.")
        mesi = int(max(1, min(12, to_float(r.get("Ogni_mesi"), 1) or 1)))
        pr_ = data_da(r.get("Prossima_rata"))
        out.append({"Conto": conto, "Descrizione": desc, "Residuo": round(residuo, 2), "Rata": round(max(0.0, rata), 2), "Ogni_mesi": mesi,
                    "Prossima_rata": pr_.isoformat() if pr_ else ""})
    return out, avvisi


def _parole(t):
    return {w for w in re.findall(r"[a-zà-ù0-9]+", (t or "").lower()) if len(w) > 2 and w not in _STOP}


def _numero_in(descr, numero):
    n = re.sub(r"\W", "", (numero or "").lower())
    return bool(n) and len(n) >= 2 and n in re.sub(r"\W", "", (descr or "").lower())


def punteggio(m, d, p=None):
    """(punteggio, motivi) di un abbinamento movimento/fattura. 0 se il verso non coincide (entrata <-> fattura attiva, uscita <-> passiva)."""
    q = {**BK_DEFAULT, **(p or {})}
    res = d["Importo"] - d["Saldato"]
    if res <= 0 or (m["Importo"] > 0) != (d["Tipo"] == "Attiva"):
        return 0, []
    imp = abs(m["Importo"])
    pt, mot = 0, []
    if abs(imp - res) <= q["tolleranza"]:
        pt += 55
        mot.append("importo uguale al residuo")
    elif abs(imp - d["Importo"]) <= q["tolleranza"]:
        pt += 45
        mot.append("importo uguale alla fattura")
    elif imp < res:
        pt += 10
        mot.append("importo parziale")
    else:
        return 0, []
    if _numero_in(m["Descrizione"], d["Documento"]):
        pt += 30
        mot.append("numero fattura nella causale")
    com = _parole(d["Controparte"]) & _parole(m["Descrizione"])
    if com:
        pt += min(30, 15 * len(com))
        mot.append("nome nella causale: " + ", ".join(sorted(com)))
    alias = q.get("alias") or {}
    cm, cd = alias.get(_k(m.get("Cantiere")), _k(m.get("Cantiere"))), alias.get(_k(d.get("Cantiere")), _k(d.get("Cantiere")))
    if cm and cd and cm == cd:
        pt += 15
        mot.append("stesso cantiere del conto")
    md, ds = data_da(m["Data"]), data_da(d["Scadenza"])
    if md and ds:
        dist = abs((md - ds).days)
        if dist <= 15:
            pt += 10
            mot.append("data vicina alla scadenza")
        elif dist > q["finestra_gg"]:
            pt -= 20
    return max(0, pt), mot


def abbina(movimenti, docs, p=None):
    """Assegnazione avida: i punteggi piu' alti per primi, ogni movimento e ogni fattura una sola volta."""
    q = {**BK_DEFAULT, **(p or {})}
    cand = []
    for i, m in enumerate(movimenti):
        for j, d in enumerate(docs):
            pt, mot = punteggio(m, d, q)
            if pt >= q["possibile"]:
                cand.append((pt, i, j, mot))
    cand.sort(key=lambda c: (-c[0], c[1], c[2]))
    usati_m, usati_d, out = set(), set(), []
    for pt, i, j, mot in cand:
        if i in usati_m or j in usati_d:
            continue
        usati_m.add(i), usati_d.add(j)
        m, d = movimenti[i], docs[j]
        imp, res = abs(m["Importo"]), d["Importo"] - d["Saldato"]
        out.append({"m": i, "d": j, "Punteggio": pt, "Esito": "sicuro" if pt >= q["sicuro"] else "da verificare", "Motivi": mot, "Movimento": m, "Fattura": d,
                    "Chiude": imp >= res - q["tolleranza"], "Saldato dopo": min(d["Importo"], d["Saldato"] + imp)})
    return out


def calcola_bk(movimenti, docs, p=None, conti=None):
    """Con `conti` ogni movimento prende il cantiere del suo conto (aiuta a trovare la fattura giusta) e si segnalano i conti non riconosciuti."""
    mappa = {_k(c["Conto"]): c for c in (conti or [])}
    movimenti = [dict(m, Cantiere=(mappa.get(_k(m.get("Conto"))) or {}).get("Cantiere", "")) for m in movimenti]
    ab = abbina(movimenti, docs, p)
    usati_m = {a["m"] for a in ab}
    usati_d = {a["d"] for a in ab}
    senza = [m for i, m in enumerate(movimenti) if i not in usati_m]
    aperte = [d for j, d in enumerate(docs) if j not in usati_d and d["Importo"] - d["Saldato"] > 0]
    ent = sum(m["Importo"] for m in movimenti if m["Importo"] > 0)
    usc = -sum(m["Importo"] for m in movimenti if m["Importo"] < 0)
    kpi = {"movimenti": len(movimenti), "entrate": ent, "uscite": usc, "abbinati": len(ab), "sicuri": sum(1 for a in ab if a["Esito"] == "sicuro"),
           "da_verificare": sum(1 for a in ab if a["Esito"] != "sicuro"), "senza_fattura": len(senza), "importo_senza": sum(abs(m["Importo"]) for m in senza),
           "fatture_aperte": len(aperte), "importo_riconciliato": sum(abs(a["Movimento"]["Importo"]) for a in ab)}
    avvisi = []
    if conti is not None:
        ignoti = sorted({m["Conto"] or SENZA_CONTO for m in movimenti if _k(m.get("Conto")) not in mappa})
        if ignoti and conti:
            avvisi.append("Movimenti su conti non presenti nell'elenco: " + ", ".join(ignoti) + ".")
    if senza:
        avvisi.append(f"{len(senza)} movimenti senza fattura ({fmt_num(kpi['importo_senza'])} €): spese bancarie, stipendi o fatture non registrate nello Scadenzario.")
    if kpi["da_verificare"]:
        avvisi.append(f"{kpi['da_verificare']} abbinamenti da verificare a mano prima di confermarli.")
    return {"movimenti": movimenti, "abbinamenti": ab, "senza_fattura": senza, "fatture_aperte": aperte, "kpi": kpi, "avvisi": avvisi}


def applica_pagamenti(docs, abbinamenti):
    """Copia dei documenti con 'Saldato' aggiornato per gli abbinamenti confermati."""
    nuovi = [dict(d) for d in docs]
    for a in abbinamenti:
        nuovi[a["d"]]["Saldato"] = a["Saldato dopo"]
    return nuovi


# ----------------------------------------------------------------------------
# PROSPETTO PER CONTO: saldo di oggi, debiti e previsione dei prossimi mesi
# ----------------------------------------------------------------------------
PROSPETTO_DEFAULT = {"settimane": 12, "incasso_scaduti_pct": 50.0, "pagamento_scaduti_pct": 100.0}


def assegna_documenti(conti, docs, alias=None):
    """
    Divide le fatture dello Scadenzario tra i conti: ogni fattura va al conto del suo cantiere (se il cantiere ha piu' conti, al primo);
    le fatture senza cantiere, o di un cantiere che non ha un conto, vanno al primo conto «generale» (senza cantiere).
    Restituisce {nome conto: [fatture]}, con la chiave SENZA_CONTO per quelle che non hanno dove andare.
    """
    alias = alias or {}
    canon = lambda x: alias.get(_k(x), _k(x))
    per_cantiere, generale = {}, None
    for c in conti:
        if _k(c["Cantiere"]):
            per_cantiere.setdefault(canon(c["Cantiere"]), c["Conto"])
        elif generale is None:
            generale = c["Conto"]
    out = {c["Conto"]: [] for c in conti}
    for d in docs:
        dest = per_cantiere.get(canon(d.get("Cantiere"))) if _k(d.get("Cantiere")) else None
        dest = dest or generale
        out.setdefault(dest or SENZA_CONTO, []).append(d)
    return out


def _rate(debito, oggi, fine):
    """Date e importi delle rate di un debito fino a `fine` (senza superare il residuo)."""
    d0 = data_da(debito.get("Prossima_rata"))
    if not d0 or debito["Rata"] <= 0:
        return []
    out, residuo, d = [], debito["Residuo"], d0
    while d <= fine and residuo > 0.005:
        imp = min(debito["Rata"], residuo)
        if d >= oggi:
            out.append((d, imp))
        residuo -= imp
        mese = d.month - 1 + debito["Ogni_mesi"]
        try:
            d = d.replace(year=d.year + mese // 12, month=mese % 12 + 1)
        except ValueError:                              # 31 -> mese corto
            d = d.replace(year=d.year + mese // 12, month=mese % 12 + 1, day=28)
    return out


def prospetto_conto(conto, movimenti, docs, debiti, oggi, p=None):
    """
    Il prospetto di UN conto: dove siamo oggi (saldo, fido, disponibile), cosa dobbiamo restituire (debiti e rate)
    e che saldo avra' il conto nelle prossime settimane con incassi e pagamenti previsti. E' una previsione di gestione, non un saldo bancario.
    Prudenza: le fatture attive scadute entrano per `incasso_scaduti_pct`% nella settimana 1, quelle passive scadute per `pagamento_scaduti_pct`%.
    """
    q = {**PROSPETTO_DEFAULT, **(p or {})}
    n = int(q["settimane"])
    mie = [m for m in movimenti if _k(m.get("Conto")) == _k(conto["Conto"])]
    ent = sum(m["Importo"] for m in mie if m["Importo"] > 0)
    usc = -sum(m["Importo"] for m in mie if m["Importo"] < 0)
    saldo = conto["Saldo_iniziale"] + ent - usc
    mio_debiti = [d for d in debiti if _k(d["Conto"]) == _k(conto["Conto"])]
    fine = oggi + dt_giorni(7 * n)
    incassi, pagamenti, rate = [0.0] * n, [0.0] * n, [0.0] * n

    def settimana(d):
        return max(0, min(n - 1, (d - oggi).days // 7)) if d >= oggi else 0

    for d in docs:
        res = d["Importo"] - d["Saldato"]
        if res <= 0.005:
            continue
        sc_ = data_da(d["Scadenza"]) or oggi
        if sc_ > fine:
            continue
        if d["Tipo"] == "Attiva":
            incassi[settimana(sc_)] += res * (q["incasso_scaduti_pct"] / 100.0 if sc_ < oggi else 1.0)
        else:
            pagamenti[settimana(sc_)] += res * (q["pagamento_scaduti_pct"] / 100.0 if sc_ < oggi else 1.0)
    for dbt in mio_debiti:
        for dr, imp in _rate(dbt, oggi, fine):
            rate[settimana(dr)] += imp
    righe, cum, minimo = [], saldo, None
    for i in range(n):
        cum += incassi[i] - pagamenti[i] - rate[i]
        inizio = oggi + dt_giorni(7 * i)
        riga = {"Settimana": i + 1, "Dal": inizio.isoformat(), "Incassi": round(incassi[i], 2), "Pagamenti": round(pagamenti[i], 2), "Rate": round(rate[i], 2),
                "Saldo previsto": round(cum, 2), "Disponibile con fido": round(cum + conto["Fido"], 2),
                "Stato": "bad" if cum + conto["Fido"] < 0 else ("warn" if cum < 0 else "ok")}
        righe.append(riga)
        if minimo is None or cum < minimo["Saldo previsto"]:
            minimo = riga
    sotto = next((r for r in righe if r["Stato"] != "ok"), None)
    debito_tot = sum(d["Residuo"] for d in mio_debiti)
    avvisi = []
    if sotto:
        avvisi.append(f"Dalla settimana {sotto['Settimana']} (dal {sotto['Dal']}) il saldo previsto va sotto zero" + (" e oltre il fido." if sotto["Stato"] == "bad" else " (dentro il fido)."))
    return {"conto": conto, "movimenti": len(mie), "entrate": ent, "uscite": usc, "saldo": saldo, "fido": conto["Fido"], "disponibile": saldo + conto["Fido"],
            "debiti": mio_debiti, "debito_residuo": debito_tot, "rate_periodo": sum(rate),
            "fatture_attive_aperte": sum(d["Importo"] - d["Saldato"] for d in docs if d["Tipo"] == "Attiva" and d["Importo"] - d["Saldato"] > 0.005),
            "fatture_passive_aperte": sum(d["Importo"] - d["Saldato"] for d in docs if d["Tipo"] == "Passiva" and d["Importo"] - d["Saldato"] > 0.005),
            "previsione": righe, "minimo": minimo, "primo_sotto_zero": sotto, "avvisi": avvisi}


def dt_giorni(n):
    import datetime as dt
    return dt.timedelta(days=n)


def prospetti(conti, movimenti, docs, debiti, oggi=None, alias=None, p=None):
    """Un prospetto per ogni conto, piu' i totali. Restituisce {'conti': [...], 'totale': {...}}."""
    import datetime as dt
    oggi = oggi or dt.date.today()
    per_conto = assegna_documenti(conti, docs, alias)
    out = [prospetto_conto(c, movimenti, per_conto.get(c["Conto"], []), debiti, oggi, p) for c in conti]
    tot = {"saldo": sum(x["saldo"] for x in out), "fido": sum(x["fido"] for x in out), "disponibile": sum(x["disponibile"] for x in out),
           "debito_residuo": sum(x["debito_residuo"] for x in out), "rate_periodo": sum(x["rate_periodo"] for x in out), "conti": len(out),
           "sotto_zero": sum(1 for x in out if x["primo_sotto_zero"]), "senza_conto": len(per_conto.get(SENZA_CONTO, []))}
    return {"conti": out, "totale": tot, "senza_conto": per_conto.get(SENZA_CONTO, [])}
