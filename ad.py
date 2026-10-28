"""ad.py - Archivio documenti per commessa: elenco ordinato con link alla cartella o al file (Drive, SharePoint, server), scadenze e documenti attesi che mancano."""
from core import to_float
from sc import data_da
from scad import conta, oggi_da, stato_scadenza

AD_DEFAULT = {"oggi": None, "preavviso_gg": 30, "attesi": "Contratto, Sicurezza, Contabilità"}
CATEGORIE = ["Contratto", "Progetto", "Sicurezza", "Contabilità", "Verbali", "Fotografie", "Autorizzazioni", "Altro"]
COLONNE_DOC = ["Commessa", "Categoria", "Titolo", "Link", "Scadenza", "Responsabile"]
ETICHETTE_DOC = {"Commessa": "Commessa", "Categoria": "Categoria", "Titolo": "Titolo", "Link": "Link (cartella o file)", "Scadenza": "Scadenza", "Responsabile": "Responsabile"}


def _s(v):
    return str(v or "").strip()


def link_valido(v):
    v = _s(v)
    return v.lower().startswith(("http://", "https://", "\\\\", "file://"))


def normalizza_doc(righe):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(_s(r.get(c)) for c in COLONNE_DOC):
            continue
        c, t = _s(r.get("Commessa")), _s(r.get("Titolo"))
        if not c or not t:
            avvisi.append(f"Riga {i} dei documenti: servono commessa e titolo, riga ignorata.")
            continue
        cat = _s(r.get("Categoria")).capitalize() or "Altro"
        cat = next((x for x in CATEGORIE if x.lower() == cat.lower()), cat)
        d = data_da(r.get("Scadenza"))
        out.append({"Commessa": c, "Categoria": cat, "Titolo": t, "Link": _s(r.get("Link")), "Scadenza": d.isoformat() if d else "", "Responsabile": _s(r.get("Responsabile"))})
    return out, avvisi


def calcola_ad(docs, p=None):
    q = {**AD_DEFAULT, **(p or {})}
    oggi, prev = oggi_da(q), int(max(0, to_float(q["preavviso_gg"], 30)))
    attesi = [x.strip() for x in str(q["attesi"] or "").replace(";", ",").split(",") if x.strip()]
    righe, avvisi = [], []
    for d in docs:
        st, g = stato_scadenza(d["Scadenza"], oggi, prev)
        righe.append({**d, "Stato": st, "Giorni": g, "Link ok": link_valido(d["Link"])})
        if st == "bad":
            avvisi.append(f"{d['Commessa']}: «{d['Titolo']}» è scaduto da {-g} giorni.")
    senza_link = [r for r in righe if not r["Link ok"]]
    if senza_link:
        avvisi.append(f"{len(senza_link)} documenti senza un link valido (deve iniziare con https://): non si possono aprire dalla suite.")
    commesse = sorted({r["Commessa"] for r in righe})
    mancanti = []
    for c in commesse:
        cat = {r["Categoria"].lower() for r in righe if r["Commessa"] == c}
        for a in attesi:
            if a.lower() not in cat:
                mancanti.append({"Commessa": c, "Manca": a})
    for m in mancanti[:12]:
        avvisi.append(f"{m['Commessa']}: manca un documento di tipo «{m['Manca']}».")
    per_c = []
    for c in commesse:
        m = [r for r in righe if r["Commessa"] == c]
        per_c.append({"Commessa": c, "Documenti": len(m), "Scaduti": sum(1 for r in m if r["Stato"] == "bad"), "Senza link": sum(1 for r in m if not r["Link ok"]), "Mancanti": sum(1 for x in mancanti if x["Commessa"] == c)})
    cs = conta([r["Stato"] for r in righe])
    kpi = {"n_doc": len(righe), "n_commesse": len(commesse), "scaduti": cs["bad"], "in_arrivo": cs["warn"], "senza_link": len(senza_link), "mancanti": len(mancanti),
           "n_bad": cs["bad"], "n_warn": cs["warn"] + len(mancanti) + len(senza_link)}
    return {"params": {"oggi": oggi, "preavviso_gg": prev, "attesi": ", ".join(attesi)}, "documenti": righe, "commesse": per_c, "mancanti": mancanti, "kpi": kpi, "avvisi": avvisi}
