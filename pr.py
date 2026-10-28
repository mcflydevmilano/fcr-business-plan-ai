"""
pr.py - Presenze e ore di cantiere: ore per persona e per commessa, straordinari e costo della manodopera.
Costo = ore ordinarie x costo orario + ore oltre le `ore_giorno` della giornata x costo orario maggiorato.
"""
import datetime as dt

from core import to_float
from sc import data_da
from scad import oggi_da

PR_DEFAULT = {"oggi": None, "ore_giorno": 8.0, "magg_straord_pct": 25.0, "max_ore_giorno": 12.0}
COLONNE_PERSONE = ["Persona", "Qualifica", "Costo_orario"]
ETICHETTE_PERSONE = {"Persona": "Persona", "Qualifica": "Qualifica", "Costo_orario": "Costo orario aziendale (€/h)"}
COLONNE_ORE = ["Persona", "Data", "Commessa", "Ore"]
ETICHETTE_ORE = {"Persona": "Persona", "Data": "Data", "Commessa": "Commessa", "Ore": "Ore lavorate"}


def _s(v):
    return str(v or "").strip()


def normalizza_persone(righe):
    out, avvisi, visti = [], [], set()
    for i, r in enumerate(righe or [], start=1):
        if not any(_s(r.get(c)) for c in COLONNE_PERSONE):
            continue
        n, c = _s(r.get("Persona")), to_float(r.get("Costo_orario"), 0.0)
        if not n or c <= 0:
            avvisi.append(f"Riga {i} delle persone: servono nome e costo orario maggiore di zero, riga ignorata.")
            continue
        if n.lower() in visti:
            avvisi.append(f"Persona «{n}» ripetuta: la seconda riga è ignorata.")
            continue
        visti.add(n.lower())
        out.append({"Persona": n, "Qualifica": _s(r.get("Qualifica")), "Costo_orario": c})
    return out, avvisi


def normalizza_ore(righe, nomi):
    nl = {n.lower(): n for n in nomi}
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(_s(r.get(c)) for c in COLONNE_ORE):
            continue
        n, d, ore = _s(r.get("Persona")), data_da(r.get("Data")), to_float(r.get("Ore"), 0.0)
        if n.lower() not in nl or d is None or ore <= 0 or ore > 24:
            avvisi.append(f"Riga {i} delle ore: " + ("persona non presente" if n.lower() not in nl else "data non valida" if d is None else "ore non valide") + ", riga ignorata.")
            continue
        out.append({"Persona": nl[n.lower()], "Data": d.isoformat(), "Commessa": _s(r.get("Commessa")) or "(senza commessa)", "Ore": ore})
    return out, avvisi


def calcola_pr(persone, ore, p=None):
    q = {**PR_DEFAULT, **(p or {})}
    oggi = oggi_da(q)
    og, mag, mx = max(1.0, to_float(q["ore_giorno"], 8.0)), max(0.0, to_float(q["magg_straord_pct"], 25.0)), to_float(q["max_ore_giorno"], 12.0)
    costo = {x["Persona"]: x["Costo_orario"] for x in persone}
    # le ore ordinarie sono le prime `og` di ogni persona nel giorno (in ordine di inserimento); il resto e' straordinario
    giorno, righe, avvisi = {}, [], []
    for r in ore:
        k = (r["Persona"], r["Data"])
        prima = giorno.get(k, 0.0)
        ord_ = max(0.0, min(r["Ore"], og - prima))
        stra = r["Ore"] - ord_
        giorno[k] = prima + r["Ore"]
        c = costo[r["Persona"]]
        righe.append({**r, "Ordinarie": ord_, "Straordinario": stra, "Costo": ord_ * c + stra * c * (1 + mag / 100.0)})
    for (n, d), t in sorted(giorno.items()):
        if t > mx:
            avvisi.append(f"{n} il {d[8:10]}/{d[5:7]}/{d[:4]}: {t:g} ore in un giorno (oltre {mx:g}): controlla se è un errore.")
    per_p = []
    for n in costo:
        m = [r for r in righe if r["Persona"] == n]
        per_p.append({"Persona": n, "Ore": sum(r["Ore"] for r in m), "Straordinario": sum(r["Straordinario"] for r in m), "Costo": sum(r["Costo"] for r in m)})
    per_c = []
    for c in sorted({r["Commessa"] for r in righe}):
        m = [r for r in righe if r["Commessa"] == c]
        per_c.append({"Commessa": c, "Ore": sum(r["Ore"] for r in m), "Costo manodopera": sum(r["Costo"] for r in m)})
    mesi = {}
    for r in righe:
        mesi[r["Data"][:7]] = mesi.get(r["Data"][:7], 0.0) + r["Ore"]
    senza = [r for r in righe if r["Commessa"] == "(senza commessa)"]
    if senza:
        avvisi.append(f"{len(senza)} registrazioni senza commessa: il costo non arriva a nessun margine.")
    kpi = {"n_persone": len(per_p), "ore": sum(r["Ore"] for r in righe), "straordinario": sum(r["Straordinario"] for r in righe), "costo": sum(r["Costo"] for r in righe),
           "n_commesse": len(per_c), "n_anomalie": len([1 for t in giorno.values() if t > mx])}
    return {"params": {"oggi": oggi, "ore_giorno": og, "magg_straord_pct": mag, "max_ore_giorno": mx}, "righe": righe, "persone": per_p, "commesse": per_c,
            "mesi": [{"Mese": m, "Ore": h} for m, h in sorted(mesi.items())], "kpi": kpi, "avvisi": avvisi}


def costi_per_commessa(out):
    return {c["Commessa"]: c["Costo manodopera"] for c in out["commesse"] if c["Commessa"] != "(senza commessa)"}


def per_sl_costi(out):
    r = {}
    for x in out["righe"]:
        if x["Commessa"] == "(senza commessa)":
            continue
        k = (x["Commessa"], x["Data"][:7])
        r[k] = r.get(k, 0.0) + x["Costo"]
    return [{"Commessa": c, "Data": m + "-28", "Fornitore": "Manodopera interna", "Descrizione": f"Ore di cantiere {m}", "Categoria": "Manodopera", "Importo": round(v, 2), "Pagato": round(v, 2)}
            for (c, m), v in sorted(r.items())]
