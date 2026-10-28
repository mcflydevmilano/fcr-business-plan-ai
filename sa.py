"""
sa.py - Subappalti e subappaltatori: contratti, SAL dei subappaltatori, ritenute e documenti obbligatori (DURC, polizze, idoneita').
Deterministico, senza Streamlit. Importi in EUR al netto di IVA.
Regola chiave: se un documento obbligatorio e' scaduto, i pagamenti a quel subappaltatore vanno fermati finche' non e' rinnovato
(la legge rende l'appaltatore responsabile in solido: DURC, retribuzioni e contributi).
"""
import datetime as dt

from core import to_float
from sc import data_da
from scad import conta, oggi_da, peggiore, stato_scadenza

SA_DEFAULT = {"oggi": None, "preavviso_gg": 30}
DOCUMENTI = ["DURC", "Polizza RC", "Polizza CAR", "Idoneità tecnico-professionale", "Autorizzazione al subappalto", "Assicurazione INAIL", "Altro"]
COLONNE_CONTRATTI = ["Subappaltatore", "Commessa", "Lavorazione", "Importo_contratto", "Ritenuta_pct"]
ETICHETTE_CONTRATTI = {"Subappaltatore": "Subappaltatore", "Commessa": "Commessa", "Lavorazione": "Lavorazione", "Importo_contratto": "Importo del contratto (€)", "Ritenuta_pct": "Ritenuta di garanzia (%)"}
COLONNE_SAL = ["Subappaltatore", "Commessa", "Data", "Importo_SAL", "Pagato"]
ETICHETTE_SAL = {"Subappaltatore": "Subappaltatore", "Commessa": "Commessa", "Data": "Data SAL", "Importo_SAL": "Importo SAL lordo (€)", "Pagato": "Già pagato (€)"}
COLONNE_DOC = ["Subappaltatore", "Documento", "Scadenza"]
ETICHETTE_DOC = {"Subappaltatore": "Subappaltatore", "Documento": "Documento", "Scadenza": "Scadenza"}


def _s(v):
    return str(v or "").strip()


def normalizza_contratti(righe):
    out, avvisi, visti = [], [], set()
    for i, r in enumerate(righe or [], start=1):
        if not any(_s(r.get(c)) for c in COLONNE_CONTRATTI):
            continue
        sub, com, imp = _s(r.get("Subappaltatore")), _s(r.get("Commessa")), to_float(r.get("Importo_contratto"), 0.0)
        if not sub or not com or imp <= 0:
            avvisi.append(f"Riga {i} dei contratti: servono subappaltatore, commessa e importo maggiore di zero, riga ignorata.")
            continue
        if (sub, com) in visti:
            avvisi.append(f"Contratto «{sub} - {com}» ripetuto: la seconda riga è ignorata.")
            continue
        visti.add((sub, com))
        out.append({"Subappaltatore": sub, "Commessa": com, "Lavorazione": _s(r.get("Lavorazione")), "Importo_contratto": imp,
                    "Ritenuta_pct": min(20.0, max(0.0, to_float(r.get("Ritenuta_pct"), 0.0)))})
    return out, avvisi


def normalizza_sal(righe, contratti):
    chiavi = {(c["Subappaltatore"], c["Commessa"]) for c in contratti}
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(_s(r.get(c)) for c in COLONNE_SAL):
            continue
        sub, com, d, imp = _s(r.get("Subappaltatore")), _s(r.get("Commessa")), data_da(r.get("Data")), to_float(r.get("Importo_SAL"), 0.0)
        if (sub, com) not in chiavi or imp <= 0:
            avvisi.append(f"Riga {i} dei SAL: " + ("contratto non presente" if (sub, com) not in chiavi else "importo non valido") + ", riga ignorata.")
            continue
        out.append({"Subappaltatore": sub, "Commessa": com, "Data": d.isoformat() if d else "", "Importo_SAL": imp, "Pagato": max(0.0, to_float(r.get("Pagato"), 0.0))})
    return out, avvisi


def normalizza_doc(righe, nomi):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(_s(r.get(c)) for c in COLONNE_DOC):
            continue
        sub, doc, d = _s(r.get("Subappaltatore")), _s(r.get("Documento")), data_da(r.get("Scadenza"))
        if sub not in nomi or not doc:
            avvisi.append(f"Riga {i} dei documenti: " + ("subappaltatore senza contratto" if sub not in nomi else "manca il tipo di documento") + ", riga ignorata.")
            continue
        out.append({"Subappaltatore": sub, "Documento": doc, "Scadenza": d.isoformat() if d else ""})
    return out, avvisi


def calcola_sa(contratti, sal, docs, p=None):
    q = {**SA_DEFAULT, **(p or {})}
    oggi, prev = oggi_da(q), int(max(0, to_float(q["preavviso_gg"], 30)))
    rd = []
    for d in docs:
        st, g = stato_scadenza(d["Scadenza"], oggi, prev)
        rd.append({**d, "Stato": st, "Giorni": g})
    det, avvisi = [], []
    for c in contratti:
        s = [x for x in sal if x["Subappaltatore"] == c["Subappaltatore"] and x["Commessa"] == c["Commessa"]]
        lordo, pagato = sum(x["Importo_SAL"] for x in s), sum(x["Pagato"] for x in s)
        rit = lordo * c["Ritenuta_pct"] / 100.0
        netto = lordo - rit
        da_pagare = max(0.0, netto - pagato)
        ds = [x for x in rd if x["Subappaltatore"] == c["Subappaltatore"]]
        st_doc = peggiore([x["Stato"] for x in ds]) if ds else "nd"
        stato = "bad" if st_doc == "bad" else ("warn" if st_doc in ("warn", "nd") or lordo > c["Importo_contratto"] or pagato > netto + 0.01 else "ok")
        det.append({"Subappaltatore": c["Subappaltatore"], "Commessa": c["Commessa"], "Lavorazione": c["Lavorazione"], "Contratto": c["Importo_contratto"], "SAL lordi": lordo,
                    "Avanzamento %": lordo / c["Importo_contratto"] * 100.0, "Ritenute": rit, "Pagato": pagato, "Da pagare": da_pagare, "Residuo contratto": c["Importo_contratto"] - lordo,
                    "Documenti": st_doc, "Stato": stato})
        if st_doc == "bad":
            scad = ", ".join(x["Documento"] for x in ds if x["Stato"] == "bad")
            avvisi.append(f"{c['Subappaltatore']} ({c['Commessa']}): documento scaduto ({scad}). Non pagare finché non è rinnovato: l'appaltatore risponde in solido." +
                          (f" Da pagare ora: {da_pagare:,.0f} €." if da_pagare > 0 else "").replace(",", "."))
        if lordo > c["Importo_contratto"] + 0.01:
            avvisi.append(f"{c['Subappaltatore']} ({c['Commessa']}): SAL oltre il contratto di {lordo - c['Importo_contratto']:,.0f} € (serve un atto aggiuntivo).".replace(",", "."))
        if pagato > netto + 0.01:
            avvisi.append(f"{c['Subappaltatore']} ({c['Commessa']}): pagato più del dovuto (+{pagato - netto:,.0f} €).".replace(",", "."))
        if not ds:
            avvisi.append(f"{c['Subappaltatore']}: nessun documento registrato (DURC, polizze, idoneità).")
    cs = conta([d["Stato"] for d in rd])
    per_comm = []
    for com in sorted({d["Commessa"] for d in det}):
        m = [d for d in det if d["Commessa"] == com]
        per_comm.append({"Commessa": com, "Contratti": sum(d["Contratto"] for d in m), "SAL lordi": sum(d["SAL lordi"] for d in m), "Da pagare": sum(d["Da pagare"] for d in m)})
    kpi = {"n_sub": len({d["Subappaltatore"] for d in det}), "contrattato": sum(d["Contratto"] for d in det), "sal_lordi": sum(d["SAL lordi"] for d in det),
           "da_pagare": sum(d["Da pagare"] for d in det), "ritenute": sum(d["Ritenute"] for d in det), "doc_scaduti": cs["bad"], "doc_in_arrivo": cs["warn"],
           "n_bad": sum(1 for d in det if d["Stato"] == "bad"), "n_warn": sum(1 for d in det if d["Stato"] == "warn")}
    return {"params": {"oggi": oggi, "preavviso_gg": prev}, "contratti": det, "documenti": rd, "commesse": per_comm, "kpi": kpi, "avvisi": avvisi}


def costi_per_commessa(out):
    """{commessa: costo sostenuto} = SAL dei subappaltatori al netto IVA, per il margine della commessa."""
    r = {}
    for d in out["contratti"]:
        r[d["Commessa"]] = r.get(d["Commessa"], 0.0) + d["SAL lordi"]
    return r


def per_sl_costi(out, sal):
    """Righe per la tabella Costi di SAL e contabilita' lavori (fornitore = il subappaltatore)."""
    return [{"Commessa": x["Commessa"], "Data": x["Data"], "Fornitore": x["Subappaltatore"], "Descrizione": "SAL subappaltatore", "Categoria": "Subappalti",
             "Importo": round(x["Importo_SAL"], 2), "Pagato": round(x["Pagato"], 2)} for x in sal]
