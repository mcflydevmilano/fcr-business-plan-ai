"""
da.py - Documenti aziendali FCR: DURC, SOA, certificazioni, assicurazioni, visura camerale e altri documenti dell'azienda
(non di un singolo cantiere o fornitore), con le loro scadenze.
Deterministico e senza Streamlit. I file veri (PDF o foto) stanno nell'archivio di doc_allegati.py (categoria "azienda");
qui sta solo l'elenco con tipo, numero/descrizione, scadenza e responsabile.
"""
from core import to_float
from scad import conta, oggi_da, peggiore, stato_scadenza
from sc import data_da

DA_DEFAULT = {"oggi": None, "preavviso_gg": 30}
TIPI = ["DURC", "SOA", "Certificazione ISO", "Assicurazione RCT/RCO", "Assicurazione CAR/Postuma", "Visura camerale", "Polizza fideiussoria", "Altro"]
COLONNE_DOC = ["Tipo", "Descrizione", "Numero", "Scadenza", "Responsabile"]
ETICHETTE_DOC = {"Tipo": "Tipo di documento", "Descrizione": "Descrizione", "Numero": "Numero / categoria", "Scadenza": "Scadenza", "Responsabile": "Responsabile"}
SINONIMI_DOC = {"Tipo": ("Categoria", "Documento"), "Scadenza": ("Data scadenza", "Valido fino al"), "Numero": ("Numero documento", "Protocollo")}


def normalizza_doc(righe):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(str(r.get(c) or "").strip() for c in COLONNE_DOC):
            continue
        t = str(r.get("Tipo") or "").strip()
        if not t:
            avvisi.append(f"Riga {i}: serve almeno il tipo di documento, riga ignorata.")
            continue
        s = data_da(r.get("Scadenza"))
        out.append({"Tipo": t, "Descrizione": str(r.get("Descrizione") or "").strip(), "Numero": str(r.get("Numero") or "").strip(),
                    "Scadenza": s.isoformat() if s else "", "Responsabile": str(r.get("Responsabile") or "").strip()})
    return out, avvisi


def calcola_da(doc, p=None):
    q = {**DA_DEFAULT, **(p or {})}
    oggi, prev = oggi_da(q), int(max(0, to_float(q["preavviso_gg"], 30)))
    righe = []
    for d in doc:
        st, g = stato_scadenza(d["Scadenza"], oggi, prev)
        righe.append({**d, "Stato": st, "Giorni": g})
    c = conta([d["Stato"] for d in righe])
    kpi = {"n_doc": len(doc), "scaduti": c["bad"], "in_scadenza": c["warn"], "ok": c["ok"], "senza_scadenza": c["nd"], "stato_peggiore": peggiore([d["Stato"] for d in righe])}
    avvisi = [f"{d['Tipo']}" + (f" ({d['Descrizione']})" if d["Descrizione"] else "") + ": documento scaduto, va rinnovato." for d in righe if d["Stato"] == "bad"]
    return {"params": {"oggi": oggi, "preavviso_gg": prev}, "documenti": righe, "kpi": kpi, "avvisi": avvisi}
