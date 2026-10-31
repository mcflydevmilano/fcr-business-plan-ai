"""
mt.py - Materiali e magazzino di cantiere: ordini e consegne, giacenze (carichi e scarichi) e costo dei materiali per commessa.
Deterministico, senza Streamlit. Importi in EUR al netto di IVA.
"""
from core import to_float
from sc import data_da
from scad import oggi_da

MT_DEFAULT = {"oggi": None, "preavviso_gg": 7}
COLONNE_ORDINI = ["Materiale", "Fornitore", "Commessa", "Quantita", "Um", "Prezzo_unit", "Consegna_prevista", "Consegnato", "Data_consegna", "Ddt"]
ETICHETTE_ORDINI = {"Materiale": "Materiale", "Fornitore": "Fornitore", "Commessa": "Commessa", "Quantita": "Quantità", "Um": "Unità", "Prezzo_unit": "Prezzo unitario (€)",
                    "Consegna_prevista": "Consegna prevista", "Consegnato": "Consegnato (sì/no)", "Data_consegna": "Data consegna", "Ddt": "N. DDT (documento di trasporto)"}
COLONNE_MOV = ["Materiale", "Commessa", "Data", "Tipo", "Quantita"]
ETICHETTE_MOV = {"Materiale": "Materiale", "Commessa": "Cantiere / commessa", "Data": "Data", "Tipo": "Carico o scarico", "Quantita": "Quantità"}
TIPI_MOV = ["Carico", "Scarico"]


def _s(v):
    return str(v or "").strip()


def _si(v):
    return _s(v).lower() in ("si", "sì", "s", "true", "1", "yes", "x", "consegnato")


def normalizza_ordini(righe):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(_s(r.get(c)) for c in COLONNE_ORDINI):
            continue
        m, q = _s(r.get("Materiale")), to_float(r.get("Quantita"), 0.0)
        if not m or q <= 0:
            avvisi.append(f"Riga {i} degli ordini: servono materiale e quantità maggiore di zero, riga ignorata.")
            continue
        cons = _si(r.get("Consegnato"))
        dc, dp = data_da(r.get("Data_consegna")), data_da(r.get("Consegna_prevista"))
        out.append({"Materiale": m, "Fornitore": _s(r.get("Fornitore")), "Commessa": _s(r.get("Commessa")) or "(senza commessa)", "Quantita": q, "Um": _s(r.get("Um")) or "pz",
                    "Prezzo_unit": max(0.0, to_float(r.get("Prezzo_unit"), 0.0)), "Consegna_prevista": dp.isoformat() if dp else "", "Consegnato": "sì" if cons else "no",
                    "Data_consegna": dc.isoformat() if dc else "", "Ddt": _s(r.get("Ddt"))})
    return out, avvisi


def normalizza_mov(righe):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(_s(r.get(c)) for c in COLONNE_MOV):
            continue
        m, d, t, q = _s(r.get("Materiale")), data_da(r.get("Data")), _s(r.get("Tipo")).capitalize(), to_float(r.get("Quantita"), 0.0)
        if not m or t not in TIPI_MOV or q <= 0:
            avvisi.append(f"Riga {i} dei movimenti: " + ("manca il materiale" if not m else "tipo non valido (Carico o Scarico)" if t not in TIPI_MOV else "quantità non valida") + ", riga ignorata.")
            continue
        out.append({"Materiale": m, "Commessa": _s(r.get("Commessa")) or "(senza commessa)", "Data": d.isoformat() if d else "", "Tipo": t, "Quantita": q})
    return out, avvisi


def calcola_mt(ordini, mov, p=None):
    q = {**MT_DEFAULT, **(p or {})}
    oggi, prev = oggi_da(q), int(max(0, to_float(q["preavviso_gg"], 7)))
    righe, avvisi, senza_ddt = [], [], 0
    for o in ordini:
        importo = o["Quantita"] * o["Prezzo_unit"]
        g = (data_da(o["Consegna_prevista"]) - oggi).days if o["Consegna_prevista"] else None
        if o["Consegnato"] == "sì":
            st = "ok"
        elif g is None:
            st = "nd"
        else:
            st = "bad" if g < 0 else ("warn" if g <= prev else "ok")
        righe.append({**o, "Importo": importo, "Giorni": g, "Stato": st})
        if o["Consegnato"] == "sì" and not o["Ddt"]:
            senza_ddt += 1
            avvisi.append(f"{o['Materiale']} ({o['Commessa']}): consegnato ma senza numero DDT: scrivilo, serve per controllare la fattura.")
        if st == "bad":
            avvisi.append(f"{o['Materiale']} ({o['Commessa']}): consegna in ritardo di {-g} giorni" + (f", fornitore {o['Fornitore']}" if o["Fornitore"] else "") + ".")
    gi = {}
    for x in mov:
        k = (x["Materiale"], x["Commessa"])
        gi[k] = gi.get(k, 0.0) + (x["Quantita"] if x["Tipo"] == "Carico" else -x["Quantita"])
    giacenze = [{"Materiale": m, "Cantiere": c, "Giacenza": v} for (m, c), v in sorted(gi.items())]
    for g in giacenze:
        if g["Giacenza"] < -1e-9:
            avvisi.append(f"{g['Materiale']} ({g['Cantiere']}): giacenza negativa ({g['Giacenza']:g}): uno scarico non ha un carico, controlla.")
    com = {}
    for r in righe:
        if r["Consegnato"] == "sì":
            com[r["Commessa"]] = com.get(r["Commessa"], 0.0) + r["Importo"]
    per_comm = [{"Commessa": c, "Costo materiali consegnati": v} for c, v in sorted(com.items())]
    ritardi = sum(1 for r in righe if r["Stato"] == "bad")
    kpi = {"n_ordini": len(righe), "ordinato": sum(r["Importo"] for r in righe), "consegnato": sum(r["Importo"] for r in righe if r["Consegnato"] == "sì"),
           "in_ritardo": ritardi, "in_arrivo": sum(1 for r in righe if r["Stato"] == "warn"), "senza_ddt": senza_ddt, "giacenze_negative": sum(1 for g in giacenze if g["Giacenza"] < -1e-9),
           "n_bad": ritardi + sum(1 for g in giacenze if g["Giacenza"] < -1e-9), "n_warn": sum(1 for r in righe if r["Stato"] == "warn")}
    return {"params": {"oggi": oggi, "preavviso_gg": prev}, "ordini": righe, "giacenze": giacenze, "commesse": per_comm, "kpi": kpi, "avvisi": avvisi}


def costi_per_commessa(out):
    return {c["Commessa"]: c["Costo materiali consegnati"] for c in out["commesse"] if c["Commessa"] != "(senza commessa)"}


def per_sl_costi(out):
    return [{"Commessa": r["Commessa"], "Data": r["Data_consegna"] or out["params"]["oggi"].isoformat(), "Fornitore": r["Fornitore"] or "Materiali", "Descrizione": f"{r['Materiale']} - {r['Quantita']:g} {r['Um']}" + (f" - DDT {r['Ddt']}" if r["Ddt"] else "") + " (da Materiali)",
             "Categoria": "Materiali", "Importo": round(r["Importo"], 2), "Pagato": 0.0} for r in out["ordini"] if r["Consegnato"] == "sì" and r["Commessa"] != "(senza commessa)"]
