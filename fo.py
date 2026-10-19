"""
fo.py - Fornitori e subappaltatori: documenti in scadenza (DURC, assicurazioni, SOA...), contratti e ordini aperti, confronto dei preventivi.
Deterministico e senza Streamlit.
"""
from core import to_float
from sc import data_da
from scad import conta, oggi_da, peggiore, stato_scadenza

FO_DEFAULT = {"oggi": None, "preavviso_gg": 30}
TIPI = ["Fornitore", "Subappaltatore", "Professionista"]
DOCUMENTI_TIPO = ["DURC", "Assicurazione RCT/RCO", "Visura camerale", "Attestazione SOA", "Idoneità tecnico-professionale", "Polizza fideiussoria"]
COLONNE_DOCFO = ["Fornitore", "Tipo", "Documento", "Scadenza"]
ETICHETTE_DOCFO = {"Fornitore": "Fornitore / subappaltatore", "Tipo": "Tipo", "Documento": "Documento", "Scadenza": "Scadenza"}
COLONNE_CONTR = ["Fornitore", "Commessa", "Descrizione", "Importo", "Fatturato", "Pagato"]
ETICHETTE_CONTR = {"Fornitore": "Fornitore", "Commessa": "Commessa", "Descrizione": "Descrizione", "Importo": "Importo contratto (€)", "Fatturato": "Fatturato finora (€)", "Pagato": "Pagato finora (€)"}
COLONNE_OFF = ["Voce", "Fornitore", "Importo"]
ETICHETTE_OFF = {"Voce": "Voce / lavorazione", "Fornitore": "Fornitore", "Importo": "Offerta (€)"}
SINONIMI_DOCFO = {"Fornitore": ("Ragione sociale", "Impresa", "Anagrafica"), "Documento": ("Certificato", "Tipo documento"), "Scadenza": ("Data scadenza", "Valido fino al")}


def normalizza_docfo(righe):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(str(r.get(c) or "").strip() for c in COLONNE_DOCFO):
            continue
        f, d = str(r.get("Fornitore") or "").strip(), str(r.get("Documento") or "").strip()
        if not f or not d:
            avvisi.append(f"Riga {i} dei documenti: servono fornitore e documento, riga ignorata.")
            continue
        t = str(r.get("Tipo") or "").strip()
        s = data_da(r.get("Scadenza"))
        out.append({"Fornitore": f, "Tipo": t if t in TIPI else "Fornitore", "Documento": d, "Scadenza": s.isoformat() if s else ""})
    return out, avvisi


def normalizza_contratti(righe):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(str(r.get(c) or "").strip() for c in COLONNE_CONTR):
            continue
        f, imp = str(r.get("Fornitore") or "").strip(), to_float(r.get("Importo"), 0.0)
        if not f or imp <= 0:
            avvisi.append(f"Riga {i} dei contratti: servono fornitore e importo, riga ignorata.")
            continue
        fat = max(0.0, to_float(r.get("Fatturato"), 0.0))
        out.append({"Fornitore": f, "Commessa": str(r.get("Commessa") or "").strip(), "Descrizione": str(r.get("Descrizione") or "").strip(), "Importo": imp,
                    "Fatturato": fat, "Pagato": min(fat, max(0.0, to_float(r.get("Pagato"), 0.0)))})
    return out, avvisi


def normalizza_offerte(righe):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(str(r.get(c) or "").strip() for c in COLONNE_OFF):
            continue
        v, f, imp = str(r.get("Voce") or "").strip(), str(r.get("Fornitore") or "").strip(), to_float(r.get("Importo"), 0.0)
        if not v or not f or imp <= 0:
            avvisi.append(f"Riga {i} delle offerte: servono voce, fornitore e importo, riga ignorata.")
            continue
        out.append({"Voce": v, "Fornitore": f, "Importo": imp})
    return out, avvisi


def calcola_fo(docs, contratti, offerte, p=None):
    q = {**FO_DEFAULT, **(p or {})}
    oggi, prev = oggi_da(q), int(max(0, to_float(q["preavviso_gg"], 30)))
    righe_doc = []
    for d in docs:
        st, g = stato_scadenza(d["Scadenza"], oggi, prev)
        righe_doc.append({**d, "Stato": st, "Giorni": g})
    nomi = sorted({d["Fornitore"] for d in docs} | {c["Fornitore"] for c in contratti} | {o["Fornitore"] for o in offerte})
    forn, avvisi = [], []
    for n in nomi:
        md = [d for d in righe_doc if d["Fornitore"] == n]
        mc = [c for c in contratti if c["Fornitore"] == n]
        st = peggiore([d["Stato"] for d in md]) if md else "nd"
        imp, fat, pag = sum(c["Importo"] for c in mc), sum(c["Fatturato"] for c in mc), sum(c["Pagato"] for c in mc)
        res = imp - fat
        forn.append({"Fornitore": n, "Tipo": md[0]["Tipo"] if md else "", "Documenti": len(md), "Scaduti": sum(1 for d in md if d["Stato"] == "bad"),
                     "In scadenza": sum(1 for d in md if d["Stato"] == "warn"), "Stato": st, "Contratti": imp, "Fatturato": fat, "Residuo ordine": res, "Da pagare": fat - pag})
        if st == "bad" and (res > 0 or fat - pag > 0):
            avvisi.append(f"{n}: ha documenti scaduti ma ci sono ordini aperti o pagamenti da fare. Chiedi il rinnovo prima di pagare o affidare altro lavoro.")
        if not md and mc:
            avvisi.append(f"{n}: ha contratti ma nessun documento registrato.")
    contr = []
    for c in contratti:
        sovra = c["Fatturato"] > c["Importo"] * 1.005
        contr.append({**c, "Residuo": c["Importo"] - c["Fatturato"], "Da pagare": c["Fatturato"] - c["Pagato"], "Sovrafatturato": sovra})
        if sovra:
            avvisi.append(f"{c['Fornitore']} ({c['Commessa'] or 'senza commessa'}): fatturato {c['Fatturato']:,.0f} € oltre il contratto di {c['Importo']:,.0f} €.".replace(",", "."))
    stato_f = {f["Fornitore"]: f["Stato"] for f in forn}
    conf, risp = [], 0.0
    for v in sorted({o["Voce"] for o in offerte}):
        of = [o for o in offerte if o["Voce"] == v]
        imp = [o["Importo"] for o in of]
        best = min(of, key=lambda o: o["Importo"])
        ok = [o for o in of if stato_f.get(o["Fornitore"]) != "bad"]
        best_ok = min(ok, key=lambda o: o["Importo"]) if ok else None
        media = sum(imp) / len(imp)
        conf.append({"Voce": v, "Offerte": len(of), "Minima": min(imp), "Massima": max(imp), "Media": media, "Scarto %": (max(imp) - min(imp)) / min(imp) * 100.0,
                     "Più bassa": best["Fornitore"], "Più bassa in regola": best_ok["Fornitore"] if best_ok else "nessuno in regola", "Risparmio vs media": media - best["Importo"]})
        risp += media - best["Importo"]
        if best_ok is None or best_ok["Fornitore"] != best["Fornitore"]:
            avvisi.append(f"«{v}»: l'offerta più bassa ({best['Fornitore']}) è di un fornitore con documenti scaduti.")
    c = conta([d["Stato"] for d in righe_doc])
    kpi = {"n_fornitori": len(nomi), "doc_scaduti": c["bad"], "doc_in_scadenza": c["warn"], "doc_ok": c["ok"], "doc_nd": c["nd"],
           "forn_critici": sum(1 for f in forn if f["Stato"] == "bad"), "impegnato": sum(x["Importo"] for x in contratti), "fatturato": sum(x["Fatturato"] for x in contratti),
           "residuo": sum(x["Residuo"] for x in contr), "da_pagare": sum(x["Da pagare"] for x in contr), "sovrafatturati": sum(1 for x in contr if x["Sovrafatturato"]), "risparmio_potenziale": risp}
    return {"params": {"oggi": oggi, "preavviso_gg": prev}, "documenti": righe_doc, "fornitori": forn, "contratti": contr, "confronto": conf, "kpi": kpi, "avvisi": avvisi}
