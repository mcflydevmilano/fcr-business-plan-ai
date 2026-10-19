"""
ga.py - Gare e offerte: elenco delle gare, convenienza del ribasso, documenti richiesti e scadenze.

Per ogni gara: offerta = importo a base x (1 - ribasso); costi stimati = importo a base x costi%;
margine = offerta - costi; ribasso massimo = quello che lascia il margine obiettivo;
valore atteso = probabilita' x margine - costo di partecipazione.
Deterministico e senza Streamlit.
"""
import datetime as dt

from core import to_float
from sc import data_da
from scad import oggi_da

GA_DEFAULT = {"oggi": None, "margine_target": 8.0, "preavviso_gg": 7}
STATI_GARA = ["Da valutare", "In preparazione", "Presentata", "Vinta", "Persa", "Non partecipo"]
APERTE = ("Da valutare", "In preparazione", "Presentata")
COLONNE_GARE = ["Gara", "Ente", "Importo_base", "Scadenza", "Stato", "Ribasso_pct", "Costi_pct", "Probabilita_pct", "Costo_partecipazione"]
ETICHETTE_GARE = {"Gara": "Gara", "Ente": "Ente appaltante", "Importo_base": "Importo a base di gara (€)", "Scadenza": "Scadenza offerta", "Stato": "Stato",
                  "Ribasso_pct": "Ribasso offerto (%)", "Costi_pct": "Costi stimati (% della base)", "Probabilita_pct": "Probabilità di vincere (%)",
                  "Costo_partecipazione": "Costo di partecipazione (€)"}
COLONNE_DOC = ["Gara", "Documento", "Scadenza", "Fatto"]
ETICHETTE_DOC = {"Gara": "Gara", "Documento": "Documento richiesto", "Scadenza": "Da pronto entro", "Fatto": "Fatto"}
CHECKLIST = ["Domanda di partecipazione", "DGUE", "Garanzia provvisoria", "Attestazione SOA", "Sopralluogo", "Offerta economica", "Offerta tecnica", "Pagamento contributo ANAC"]
SINONIMI_GARE = {"Gara": ("Oggetto", "Descrizione", "CIG"), "Ente": ("Stazione appaltante", "Committente"), "Importo_base": ("Importo", "Base d'asta", "Importo lavori"),
                 "Scadenza": ("Termine", "Data scadenza", "Scadenza presentazione")}


def _pct(x, mx=100.0):
    return min(mx, max(0.0, to_float(x, 0.0)))


def _vero(v):
    if isinstance(v, str):
        return v.strip().lower() in ("1", "si", "sì", "s", "true", "x", "ok", "fatto", "yes")
    return bool(v) if v == v else False


def normalizza_gare(righe):
    out, avvisi, visti = [], [], set()
    for i, r in enumerate(righe or [], start=1):
        if not any(str(r.get(c) or "").strip() for c in COLONNE_GARE):
            continue
        nome = str(r.get("Gara") or "").strip()
        base = to_float(r.get("Importo_base"), 0.0)
        if not nome or base <= 0:
            avvisi.append(f"Riga {i} delle gare: servono un nome e un importo a base di gara, riga ignorata.")
            continue
        if nome in visti:
            avvisi.append(f"Gara «{nome}» ripetuta: la seconda riga è ignorata.")
            continue
        visti.add(nome)
        stato = str(r.get("Stato") or "").strip()
        if stato not in STATI_GARA:
            stato = "Da valutare"
        sc_ = data_da(r.get("Scadenza"))
        out.append({"Gara": nome, "Ente": str(r.get("Ente") or "").strip(), "Importo_base": base, "Scadenza": sc_.isoformat() if sc_ else "", "Stato": stato,
                    "Ribasso_pct": _pct(r.get("Ribasso_pct"), 60.0), "Costi_pct": _pct(r.get("Costi_pct"), 150.0), "Probabilita_pct": _pct(r.get("Probabilita_pct")),
                    "Costo_partecipazione": max(0.0, to_float(r.get("Costo_partecipazione"), 0.0))})
    return out, avvisi


def normalizza_doc(righe, nomi):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(str(r.get(c) or "").strip() for c in COLONNE_DOC if c != "Fatto") and not _vero(r.get("Fatto")):
            continue
        g, d = str(r.get("Gara") or "").strip(), str(r.get("Documento") or "").strip()
        if g not in nomi or not d:
            avvisi.append(f"Riga {i} dei documenti: " + ("gara non presente" if g not in nomi else "manca il documento") + ", riga ignorata.")
            continue
        s = data_da(r.get("Scadenza"))
        out.append({"Gara": g, "Documento": d, "Scadenza": s.isoformat() if s else "", "Fatto": _vero(r.get("Fatto"))})
    return out, avvisi


def calcola_ga(gare, doc, p=None):
    q = {**GA_DEFAULT, **(p or {})}
    oggi = oggi_da(q)
    target, prev = _pct(q["margine_target"], 50.0), int(max(0, to_float(q["preavviso_gg"], 7)))
    det, avvisi = [], []
    for g in gare:
        base = g["Importo_base"]
        offerta = base * (1 - g["Ribasso_pct"] / 100.0)
        costi = base * g["Costi_pct"] / 100.0
        margine = offerta - costi
        mp = margine / offerta * 100.0 if offerta else 0.0
        minima = costi / (1 - target / 100.0) if target < 100 else costi
        rmax = (1 - minima / base) * 100.0
        ev = g["Probabilita_pct"] / 100.0 * margine - g["Costo_partecipazione"]
        giorni = (data_da(g["Scadenza"]) - oggi).days if g["Scadenza"] else None
        mie = [d for d in doc if d["Gara"] == g["Gara"]]
        mancanti = [d for d in mie if not d["Fatto"]]
        aperta = g["Stato"] in ("Da valutare", "In preparazione")
        if mp >= target and ev > 0:
            consiglio = "Conviene partecipare"
        elif margine > 0 and ev > 0:
            consiglio = "Margine sotto l'obiettivo: rivedi il ribasso"
        else:
            consiglio = "Non conviene a queste condizioni"
        if g["Stato"] in ("Vinta", "Persa", "Non partecipo", "Presentata"):
            consiglio = "—"
        if aperta and giorni is not None and giorni < 0:
            stato = "bad"
            avvisi.append(f"{g['Gara']}: scadenza superata e offerta non presentata.")
        elif aperta and giorni is not None and giorni <= prev and mancanti:
            stato = "bad"
            avvisi.append(f"{g['Gara']}: scade tra {giorni} giorni e mancano {len(mancanti)} documenti.")
        elif aperta and ((giorni is not None and giorni <= 2 * prev) or mancanti):
            stato = "warn"
        else:
            stato = "ok"
        for d in mie:
            s = data_da(d["Scadenza"])
            if not d["Fatto"] and s and s < oggi and aperta:
                avvisi.append(f"{g['Gara']}: il documento «{d['Documento']}» doveva essere pronto il {s.strftime('%d/%m/%Y')}.")
        det.append({"Gara": g["Gara"], "Ente": g["Ente"], "Stato gara": g["Stato"], "Importo base": base, "Ribasso %": g["Ribasso_pct"], "Offerta": offerta, "Costi stimati": costi,
                    "Margine": margine, "Margine %": mp, "Ribasso massimo %": rmax, "Valore atteso": ev if g["Stato"] in APERTE else 0.0,
                    "Ponderato": g["Probabilita_pct"] / 100.0 * offerta if g["Stato"] in APERTE else 0.0, "Scadenza": g["Scadenza"], "Giorni": giorni,
                    "Documenti": len(mie), "Documenti mancanti": len(mancanti), "Consiglio": consiglio, "Stato": stato})
    aperte = [d for d in det if d["Stato gara"] in APERTE]
    v, pe = sum(1 for d in det if d["Stato gara"] == "Vinta"), sum(1 for d in det if d["Stato gara"] == "Persa")
    kpi = {"n_gare": len(det), "n_aperte": len(aperte), "importo_pipeline": sum(d["Offerta"] for d in aperte), "ponderato": sum(d["Ponderato"] for d in aperte),
           "valore_atteso": sum(d["Valore atteso"] for d in aperte), "in_scadenza": sum(1 for d in det if d["Stato gara"] in ("Da valutare", "In preparazione") and d["Giorni"] is not None and 0 <= d["Giorni"] <= prev),
           "scadute": sum(1 for d in det if d["Stato gara"] in ("Da valutare", "In preparazione") and d["Giorni"] is not None and d["Giorni"] < 0),
           "doc_mancanti": sum(d["Documenti mancanti"] for d in aperte), "vinte": v, "perse": pe, "tasso_successo": (v / (v + pe) * 100.0) if (v + pe) else None,
           "margine_medio_pct": (sum(d["Margine %"] for d in aperte) / len(aperte)) if aperte else 0.0,
           "n_bad": sum(1 for d in det if d["Stato"] == "bad"), "n_warn": sum(1 for d in det if d["Stato"] == "warn")}
    docs = []
    for d in doc:
        s = data_da(d["Scadenza"])
        docs.append({**d, "Giorni": (s - oggi).days if s else None})
    return {"params": {"oggi": oggi, "margine_target": target, "preavviso_gg": prev}, "gare": det, "documenti": docs, "kpi": kpi, "avvisi": avvisi}


def per_commesse(out, gare):
    """Gare vinte -> righe per la tabella commesse di SAL e contabilita' lavori (contratto = offerta, costi = costi stimati)."""
    righe = []
    for d in out["gare"]:
        if d["Stato gara"] == "Vinta":
            righe.append({"Commessa": d["Gara"], "Cliente": d["Ente"], "Contratto": round(d["Offerta"], 2), "Varianti": 0, "Costi_prev": round(d["Costi stimati"], 2),
                          "Avanz_reale_pct": 0, "Ritenuta_pct": 5, "Anticipo_pct": 0, "Iva_pct": 22, "Gg_incasso": 60, "Inizio": "", "Fine_prev": ""})
    return righe
