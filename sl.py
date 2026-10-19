"""
sl.py - SAL e contabilita' lavori: commesse, stati di avanzamento, costi, margine a finire (earned value) e collegamenti
con Scadenzario, Cash Flow di cantiere e Cruscotto di direzione.

Deterministico e senza Streamlit. Importi in EUR. Il contratto e i costi sono al netto di IVA; le fatture di SAL sono calcolate con l'IVA
della commessa (l'incasso e' quello lordo).

Modello per ogni commessa (contratto C = contratto + varianti approvate):
  SAL            riga con avanzamento CUMULATIVO %: lordo = C x (avanzamento - avanzamento precedente)
                 recupero anticipo = lordo x anticipo%;  ritenuta di garanzia = lordo x ritenuta%
                 imponibile fattura = lordo - recupero - ritenuta;  fattura = imponibile x (1 + IVA)
                 Una riga con avanzamento 0% e' la fattura di ANTICIPO (C x anticipo%).
  Ritenute       trattenute cumulate; si svincolano dopo `gg_svincolo` giorni dalla fine prevista.
  Earned value   EV = costi preventivati x avanzamento; AC = costi sostenuti; CPI = EV / AC;
                 costi a finire attesi (EAC) = costi preventivati / CPI (se avanzamento >= 5% e AC > 0, altrimenti il preventivo);
                 margine finale previsto = C - EAC.
"""
import datetime as dt

from core import fmt_num, to_float
from sc import data_da

SL_DEFAULT = {"oggi": None, "gg_pagamento": 60, "gg_svincolo": 90}
COLONNE_COMMESSE = ["Commessa", "Cliente", "Contratto", "Varianti", "Costi_prev", "Avanz_reale_pct", "Ritenuta_pct", "Anticipo_pct", "Iva_pct", "Gg_incasso", "Inizio", "Fine_prev"]
ETICHETTE_COMMESSE = {"Commessa": "Commessa", "Cliente": "Cliente", "Contratto": "Contratto (€, IVA esclusa)", "Varianti": "Varianti approvate (€)",
                      "Costi_prev": "Costi preventivati (€)", "Avanz_reale_pct": "Avanzamento reale oggi (%)", "Ritenuta_pct": "Ritenuta di garanzia (%)",
                      "Anticipo_pct": "Anticipo contrattuale (%)", "Iva_pct": "IVA (%)", "Gg_incasso": "Giorni di incasso", "Inizio": "Inizio lavori", "Fine_prev": "Fine prevista"}
COLONNE_SAL = ["Commessa", "Numero", "Data", "Avanzamento_pct", "Incassato", "Data_incasso"]
ETICHETTE_SAL = {"Commessa": "Commessa", "Numero": "N. SAL", "Data": "Data SAL", "Avanzamento_pct": "Avanzamento cumulativo (%)", "Incassato": "Incassato (€, IVA inclusa)", "Data_incasso": "Data incasso"}
COLONNE_COSTI = ["Commessa", "Data", "Fornitore", "Descrizione", "Categoria", "Importo", "Pagato"]
ETICHETTE_COSTI = {"Commessa": "Commessa", "Data": "Data", "Fornitore": "Fornitore", "Descrizione": "Descrizione", "Categoria": "Categoria", "Importo": "Importo (€, IVA esclusa)", "Pagato": "Già pagato (€)"}
TOLL_OK, TOLL_WARN = 1.0, 5.0       # punti percentuali di margine persi rispetto al preventivo


def _pct(x):
    return min(100.0, max(0.0, to_float(x, 0.0)))


def _iso(v):
    d = data_da(v)
    return d.isoformat() if d else ""


# ----------------------------------------------------------------------------
# NORMALIZZAZIONE
# ----------------------------------------------------------------------------
def normalizza_commesse(righe):
    out, avvisi, visti = [], [], set()
    for i, r in enumerate(righe or [], start=1):
        if not any(str(r.get(c) or "").strip() for c in COLONNE_COMMESSE):
            continue
        nome = str(r.get("Commessa") or "").strip()
        contratto = to_float(r.get("Contratto"), 0.0)
        if not nome or contratto <= 0:
            avvisi.append(f"Riga {i} delle commesse: serve un nome e un contratto maggiore di zero, riga ignorata.")
            continue
        if nome in visti:
            avvisi.append(f"Commessa «{nome}» ripetuta: la seconda riga e' ignorata.")
            continue
        visti.add(nome)
        av = r.get("Avanz_reale_pct")
        ini, fine = data_da(r.get("Inizio")), data_da(r.get("Fine_prev"))
        if ini and fine and fine < ini:
            avvisi.append(f"«{nome}»: la fine prevista e' precedente all'inizio.")
        out.append({"Commessa": nome, "Cliente": str(r.get("Cliente") or "").strip(), "Contratto": contratto, "Varianti": to_float(r.get("Varianti"), 0.0),
                    "Costi_prev": max(0.0, to_float(r.get("Costi_prev"), 0.0)),
                    "Avanz_reale_pct": None if (av is None or str(av).strip() == "" or (isinstance(av, float) and av != av)) else _pct(av),
                    "Ritenuta_pct": _pct(r.get("Ritenuta_pct")), "Anticipo_pct": _pct(r.get("Anticipo_pct")), "Iva_pct": min(30.0, max(0.0, to_float(r.get("Iva_pct"), 22.0))),
                    "Gg_incasso": int(max(0, to_float(r.get("Gg_incasso"), 30))), "Inizio": _iso(ini), "Fine_prev": _iso(fine)})
    return out, avvisi


def normalizza_sal(righe, nomi):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(str(r.get(c) or "").strip() for c in COLONNE_SAL):
            continue
        nome = str(r.get("Commessa") or "").strip()
        d = data_da(r.get("Data"))
        if nome not in nomi or d is None:
            avvisi.append(f"Riga {i} dei SAL: " + ("commessa non presente" if nome not in nomi else "data non valida") + ", riga ignorata.")
            continue
        out.append({"Commessa": nome, "Numero": str(r.get("Numero") or "").strip(), "Data": d.isoformat(), "Avanzamento_pct": _pct(r.get("Avanzamento_pct")),
                    "Incassato": max(0.0, to_float(r.get("Incassato"), 0.0)), "Data_incasso": _iso(r.get("Data_incasso"))})
    return out, avvisi


def normalizza_costi(righe, nomi):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(str(r.get(c) or "").strip() for c in COLONNE_COSTI):
            continue
        nome = str(r.get("Commessa") or "").strip()
        imp = to_float(r.get("Importo"), 0.0)
        d = data_da(r.get("Data"))
        if nome not in nomi or imp <= 0 or d is None:
            avvisi.append(f"Riga {i} dei costi: " + ("commessa non presente" if nome not in nomi else "importo non valido" if imp <= 0 else "data non valida") + ", riga ignorata.")
            continue
        out.append({"Commessa": nome, "Data": d.isoformat(), "Fornitore": str(r.get("Fornitore") or "").strip(), "Descrizione": str(r.get("Descrizione") or "").strip(),
                    "Categoria": str(r.get("Categoria") or "").strip() or "Varie", "Importo": imp, "Pagato": min(imp, max(0.0, to_float(r.get("Pagato"), 0.0)))})
    return out, avvisi


def _par(p):
    q = {**SL_DEFAULT, **(p or {})}
    q["oggi"] = data_da(q.get("oggi"), dt.date.today())
    q["gg_pagamento"] = int(min(365, max(0, to_float(q["gg_pagamento"], 60))))
    q["gg_svincolo"] = int(min(720, max(0, to_float(q["gg_svincolo"], 90))))
    return q


# ----------------------------------------------------------------------------
# CALCOLO
# ----------------------------------------------------------------------------
def calcola_sl(commesse, sal, costi, p=None):
    q = _par(p)
    oggi = q["oggi"]
    dett, fatture, avvisi = [], [], []
    for c in commesse:
        nome = c["Commessa"]
        C = c["Contratto"] + c["Varianti"]
        righe_sal = sorted([s for s in sal if s["Commessa"] == nome], key=lambda s: (s["Data"], s["Numero"]))
        prev, lordo_tot, rit_tot, rec_tot, incassato_tot, fatt_tot = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        scaduto_cli, anticipo_gia = 0.0, False
        for s in righe_sal:
            av = max(prev, s["Avanzamento_pct"])
            if s["Avanzamento_pct"] < prev - 1e-9:
                avvisi.append(f"{nome}: il SAL {s['Numero'] or s['Data']} ha un avanzamento ({fmt_num(s['Avanzamento_pct'], 1)}%) inferiore al precedente: considerato {fmt_num(prev, 1)}%.")
            if av == 0 and prev == 0 and c["Anticipo_pct"] > 0 and not anticipo_gia:
                lordo, rec, rit, anticipo_gia, tipo = C * c["Anticipo_pct"] / 100.0, 0.0, 0.0, True, "Anticipo"
                imp = lordo
            else:
                lordo = C * (av - prev) / 100.0
                rec, rit, tipo = lordo * c["Anticipo_pct"] / 100.0, lordo * c["Ritenuta_pct"] / 100.0, "SAL"
                imp = lordo - rec - rit
            iva = imp * c["Iva_pct"] / 100.0
            tot = imp + iva
            scad = data_da(s["Data"]) + dt.timedelta(days=c["Gg_incasso"])
            inc = min(tot, s["Incassato"])
            if s["Incassato"] > tot + 0.5:
                avvisi.append(f"{nome}: incassato {fmt_num(s['Incassato'])} EUR superiore alla fattura del SAL {s['Numero'] or s['Data']} ({fmt_num(tot)} EUR).")
            res = tot - inc
            scaduta = res > 0.5 and scad < oggi
            if scaduta:
                scaduto_cli += res
            fatture.append({"Commessa": nome, "Numero": s["Numero"], "Tipo": tipo, "Data": s["Data"], "Avanzamento": av, "Lordo": lordo, "Recupero anticipo": rec,
                            "Ritenuta": rit, "Imponibile": imp, "IVA": iva, "Totale": tot, "Scadenza": scad.isoformat(), "Incassato": inc, "Residuo": res, "Scaduta": scaduta})
            prev = av
            lordo_tot += lordo
            rit_tot += rit
            rec_tot += rec
            incassato_tot += inc
            fatt_tot += imp
        avanz_sal = prev
        avanz = c["Avanz_reale_pct"] if c["Avanz_reale_pct"] is not None else avanz_sal
        if c["Avanz_reale_pct"] is not None and avanz < avanz_sal - 1e-9:
            avvisi.append(f"{nome}: l'avanzamento reale ({fmt_num(avanz, 1)}%) e' inferiore a quello gia' fatturato ({fmt_num(avanz_sal, 1)}%): possibile sovrafatturazione.")
        eseguito = C * avanz / 100.0
        fatturato_lordo = fatt_tot + rit_tot          # imponibile fatturato + ritenute trattenute (anticipo compreso)
        da_fatt = max(0.0, eseguito - fatturato_lordo)
        costi_c = [x for x in costi if x["Commessa"] == nome]
        ac = sum(x["Importo"] for x in costi_c)
        pagati = sum(x["Pagato"] for x in costi_c)
        forn_scaduti = sum(x["Importo"] - x["Pagato"] for x in costi_c if x["Importo"] - x["Pagato"] > 0.5 and data_da(x["Data"]) + dt.timedelta(days=q["gg_pagamento"]) < oggi)
        ev = c["Costi_prev"] * avanz / 100.0
        cpi = (ev / ac) if ac > 0 and ev > 0 else None
        eac = c["Costi_prev"] / cpi if (cpi and avanz >= 5.0) else c["Costi_prev"]
        eac = max(eac, ac)
        m_att = C - c["Costi_prev"]
        m_fin = C - eac
        m_att_pct, m_fin_pct = (m_att / C * 100.0) if C else 0.0, (m_fin / C * 100.0) if C else 0.0
        ini, fine = data_da(c["Inizio"]), data_da(c["Fine_prev"])
        atteso = None
        if ini and fine and fine > ini:
            atteso = min(100.0, max(0.0, (oggi - ini).days / (fine - ini).days * 100.0))
        ritardo_pp = (atteso - avanz) if atteso is not None else 0.0
        scost = m_fin_pct - m_att_pct
        if m_fin < 0 or scost < -TOLL_WARN:
            stato = "bad"
        elif scost < -TOLL_OK or ritardo_pp > 15:
            stato = "warn"
        else:
            stato = "ok"
        if fine and fine < oggi and avanz < 100:
            stato = "bad" if stato == "bad" else "warn"
            avvisi.append(f"{nome}: la data di fine prevista e' passata ma l'avanzamento e' {fmt_num(avanz, 1)}%.")
        if ac > 0 and avanz == 0:
            avvisi.append(f"{nome}: ci sono costi sostenuti ma l'avanzamento e' 0%: aggiorna l'avanzamento reale.")
        dett.append({"Commessa": nome, "Cliente": c["Cliente"], "Contratto totale": C, "Varianti": c["Varianti"], "Costi preventivati": c["Costi_prev"],
                     "Avanzamento %": avanz, "Avanzamento fatturato %": avanz_sal, "Lavori eseguiti": eseguito, "Fatturato (lordo lavori)": fatturato_lordo, "Da fatturare": da_fatt,
                     "Ritenute trattenute": rit_tot, "Imponibile fatturato": fatt_tot, "Incassato": incassato_tot,
                     "Crediti scaduti": scaduto_cli, "Costi sostenuti": ac, "Pagati": pagati, "Debiti fornitori": ac - pagati, "Fornitori scaduti": forn_scaduti,
                     "EV": ev, "CPI": cpi, "Costi a finire (EAC)": eac, "Margine atteso": m_att, "Margine atteso %": m_att_pct, "Margine finale previsto": m_fin,
                     "Margine finale %": m_fin_pct, "Scostamento margine (pp)": scost, "Margine corrente": eseguito - ac, "Avanzamento atteso %": atteso, "Ritardo (pp)": ritardo_pp,
                     "Cassa commessa": incassato_tot / (1 + c["Iva_pct"] / 100.0) - pagati, "Stato": stato})
    k = _kpi(dett, fatture, q)
    out = {"params": q, "commesse": dett, "fatture": fatture, "kpi": k, "avvisi": avvisi}
    out["avvisi"] += _avvisi(dett, k)
    return out


def _kpi(dett, fatture, q):
    s = lambda key: sum(d[key] for d in dett)
    C, att, eac = s("Contratto totale"), s("Margine atteso"), s("Costi a finire (EAC)")
    fin = C - eac
    return {"n_commesse": len(dett), "contratti": C, "costi_prev": s("Costi preventivati"), "eac": eac, "margine_atteso": att, "margine_atteso_pct": (att / C * 100.0) if C else 0.0,
            "margine_finale": fin, "margine_finale_pct": (fin / C * 100.0) if C else 0.0, "eseguito": s("Lavori eseguiti"), "fatturato": s("Fatturato (lordo lavori)"),
            "da_fatturare": s("Da fatturare"), "incassato": s("Incassato"), "crediti_scaduti": s("Crediti scaduti"), "ritenute": s("Ritenute trattenute"),
            "costi_sostenuti": s("Costi sostenuti"), "debiti_fornitori": s("Debiti fornitori"), "fornitori_scaduti": s("Fornitori scaduti"),
            "avanzamento": (s("Lavori eseguiti") / C * 100.0) if C else 0.0, "n_bad": sum(1 for d in dett if d["Stato"] == "bad"), "n_warn": sum(1 for d in dett if d["Stato"] == "warn"),
            "n_ok": sum(1 for d in dett if d["Stato"] == "ok"), "cassa_commesse": s("Cassa commessa"), "n_sal": len(fatture)}


def _avvisi(dett, k):
    w = []
    if not dett:
        return ["Nessuna commessa: aggiungi almeno una riga con nome e contratto."]
    for d in dett:
        if d["Stato"] == "bad" and d["Margine finale previsto"] < 0:
            w.append(f"{d['Commessa']}: a questo ritmo di spesa chiudera' in PERDITA ({fmt_num(d['Margine finale previsto'])} EUR).")
        elif d["Stato"] == "bad":
            w.append(f"{d['Commessa']}: margine finale previsto {fmt_num(d['Margine finale %'], 1)}% contro {fmt_num(d['Margine atteso %'], 1)}% preventivato.")
    if k["da_fatturare"] > 1:
        w.append(f"{fmt_num(k['da_fatturare'])} EUR di lavori eseguiti non risultano ancora fatturati: emetti i SAL per non finanziare i cantieri.")
    if k["crediti_scaduti"] > 1:
        w.append(f"{fmt_num(k['crediti_scaduti'])} EUR di SAL sono scaduti e non incassati.")
    return w


# ----------------------------------------------------------------------------
# COLLEGAMENTI CON GLI ALTRI MODULI
# ----------------------------------------------------------------------------
PREFISSO_DOC = "SL:"


def per_scadenzario(out, costi, p=None):
    """Righe per lo Scadenzario: SAL emessi (Attiva, residuo da incassare) e costi non pagati (Passiva). Il numero documento inizia con 'SL:'."""
    q = _par(p or out.get("params"))
    righe = []
    cl = {d["Commessa"]: d["Cliente"] for d in out["commesse"]}
    for f in out["fatture"]:
        righe.append({"Tipo": "Attiva", "Controparte": cl.get(f["Commessa"]) or f["Commessa"], "Cantiere": f["Commessa"], "Documento": f"{PREFISSO_DOC}{f['Commessa']}-{f['Numero'] or f['Data']}",
                      "Data_doc": f["Data"], "Scadenza": f["Scadenza"], "Importo": f["Totale"], "Saldato": f["Incassato"]})
    for x in costi:
        righe.append({"Tipo": "Passiva", "Controparte": x["Fornitore"] or "(fornitore non indicato)", "Cantiere": x["Commessa"],
                      "Documento": f"{PREFISSO_DOC}{x['Commessa']}-{x['Data']}-{(x['Descrizione'] or x['Categoria'])[:20]}", "Data_doc": x["Data"],
                      "Scadenza": (data_da(x["Data"]) + dt.timedelta(days=q["gg_pagamento"])).isoformat(), "Importo": x["Importo"], "Saldato": x["Pagato"]})
    return righe


def per_cash_flow(out, commesse):
    """Righe per il portafoglio del Cash Flow: i mesi sono relativi alla prima partenza; i costi sono quelli a finire attesi (EAC)."""
    ini = [data_da(c["Inizio"]) for c in commesse if data_da(c["Inizio"])]
    if not ini:
        return []
    base = min(ini)
    det = {d["Commessa"]: d for d in out["commesse"]}
    righe = []
    for c in commesse:
        i, f = data_da(c["Inizio"]), data_da(c["Fine_prev"])
        d = det.get(c["Commessa"])
        if not i or not d:
            continue
        mese = (i.year - base.year) * 12 + (i.month - base.month) + 1
        durata = max(1, ((f.year - i.year) * 12 + (f.month - i.month) + 1) if f else 3)
        C = d["Contratto totale"]
        righe.append({"Cantiere": c["Commessa"], "Contratto": C, "Inizio": mese, "Durata": durata, "Anticipo_pct": c["Anticipo_pct"],
                      "Saldo_pct": min(100.0 - c["Anticipo_pct"], c["Ritenuta_pct"]), "Gg_incasso": c["Gg_incasso"],
                      "Costi_pct": (d["Costi a finire (EAC)"] / C * 100.0) if C else 0.0})
    return righe
