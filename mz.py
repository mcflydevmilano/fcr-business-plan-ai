"""
mz.py - Parco mezzi e attrezzature: tariffa oraria interna, utilizzo, costi per commessa, scadenze (revisione, assicurazione, manutenzione).
Tariffa = costi fissi annui / ore annue previste + costo variabile orario. Utilizzo e costi si calcolano sugli ultimi 12 mesi.
"""
import datetime as dt

from core import to_float
from sc import data_da
from scad import conta, oggi_da, peggiore, stato_scadenza

MZ_DEFAULT = {"oggi": None, "preavviso_gg": 30, "utilizzo_min_pct": 50.0}
COLONNE_MEZZI = ["Mezzo", "Tipo", "Costo_fisso_annuo", "Costo_var_orario", "Ore_annue_prev"]
ETICHETTE_MEZZI = {"Mezzo": "Mezzo / attrezzatura", "Tipo": "Tipo", "Costo_fisso_annuo": "Costi fissi annui (€)", "Costo_var_orario": "Costo variabile orario (€/h)", "Ore_annue_prev": "Ore annue previste"}
COLONNE_USO = ["Mezzo", "Commessa", "Data", "Ore"]
ETICHETTE_USO = {"Mezzo": "Mezzo", "Commessa": "Commessa", "Data": "Data", "Ore": "Ore di utilizzo"}
COLONNE_SCAD = ["Mezzo", "Documento", "Scadenza"]
ETICHETTE_SCAD = {"Mezzo": "Mezzo", "Documento": "Scadenza di", "Scadenza": "Data"}
DOCUMENTI = ["Revisione", "Assicurazione", "Bollo", "Manutenzione programmata", "Verifica periodica"]


def normalizza_mezzi(righe):
    out, avvisi, visti = [], [], set()
    for i, r in enumerate(righe or [], start=1):
        if not any(str(r.get(c) or "").strip() for c in COLONNE_MEZZI):
            continue
        n = str(r.get("Mezzo") or "").strip()
        ore = to_float(r.get("Ore_annue_prev"), 0.0)
        if not n or ore <= 0:
            avvisi.append(f"Riga {i} dei mezzi: servono nome e ore annue previste, riga ignorata.")
            continue
        if n in visti:
            avvisi.append(f"Mezzo «{n}» ripetuto: la seconda riga è ignorata.")
            continue
        visti.add(n)
        out.append({"Mezzo": n, "Tipo": str(r.get("Tipo") or "").strip(), "Costo_fisso_annuo": max(0.0, to_float(r.get("Costo_fisso_annuo"), 0.0)),
                    "Costo_var_orario": max(0.0, to_float(r.get("Costo_var_orario"), 0.0)), "Ore_annue_prev": ore})
    return out, avvisi


def normalizza_uso(righe, nomi):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(str(r.get(c) or "").strip() for c in COLONNE_USO):
            continue
        m, d, ore = str(r.get("Mezzo") or "").strip(), data_da(r.get("Data")), to_float(r.get("Ore"), 0.0)
        if m not in nomi or d is None or ore <= 0:
            avvisi.append(f"Riga {i} dell'utilizzo: " + ("mezzo non presente" if m not in nomi else "data non valida" if d is None else "ore non valide") + ", riga ignorata.")
            continue
        out.append({"Mezzo": m, "Commessa": str(r.get("Commessa") or "").strip() or "(senza commessa)", "Data": d.isoformat(), "Ore": ore})
    return out, avvisi


def normalizza_scad(righe, nomi):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(str(r.get(c) or "").strip() for c in COLONNE_SCAD):
            continue
        m, d, s = str(r.get("Mezzo") or "").strip(), str(r.get("Documento") or "").strip(), data_da(r.get("Scadenza"))
        if m not in nomi or not d:
            avvisi.append(f"Riga {i} delle scadenze: " + ("mezzo non presente" if m not in nomi else "manca il tipo") + ", riga ignorata.")
            continue
        out.append({"Mezzo": m, "Documento": d, "Scadenza": s.isoformat() if s else ""})
    return out, avvisi


def calcola_mz(mezzi, uso, scad, p=None):
    q = {**MZ_DEFAULT, **(p or {})}
    oggi, prev = oggi_da(q), int(max(0, to_float(q["preavviso_gg"], 30)))
    soglia = to_float(q["utilizzo_min_pct"], 50.0)
    da = oggi - dt.timedelta(days=365)
    uso12 = [u for u in uso if da < data_da(u["Data"]) <= oggi]
    rs = []
    for s in scad:
        st, g = stato_scadenza(s["Scadenza"], oggi, prev)
        rs.append({**s, "Stato": st, "Giorni": g})
    det, avvisi = [], []
    for m in mezzi:
        ore = sum(u["Ore"] for u in uso12 if u["Mezzo"] == m["Mezzo"])
        tariffa = m["Costo_fisso_annuo"] / m["Ore_annue_prev"] + m["Costo_var_orario"]
        ut = ore / m["Ore_annue_prev"] * 100.0
        non_ass = m["Costo_fisso_annuo"] * max(0.0, 1 - ore / m["Ore_annue_prev"])
        ms = [s for s in rs if s["Mezzo"] == m["Mezzo"]]
        st_s = peggiore([s["Stato"] for s in ms]) if ms else "nd"
        stato = "bad" if st_s == "bad" else ("warn" if st_s == "warn" or ut < soglia else "ok")
        det.append({"Mezzo": m["Mezzo"], "Tipo": m["Tipo"], "Tariffa oraria": tariffa, "Ore 12 mesi": ore, "Utilizzo %": ut, "Costo imputato": ore * tariffa,
                    "Fissi non assorbiti": non_ass, "Scadenze scadute": sum(1 for s in ms if s["Stato"] == "bad"), "Scadenze in arrivo": sum(1 for s in ms if s["Stato"] == "warn"), "Stato": stato})
        if st_s == "bad":
            avvisi.append(f"{m['Mezzo']}: scadenza superata ({', '.join(s['Documento'] for s in ms if s['Stato'] == 'bad')}).")
        if ut < soglia:
            avvisi.append(f"{m['Mezzo']}: usato al {ut:.0f}% delle ore previste, {non_ass:,.0f} € di costi fissi non coperti dalle commesse.".replace(",", "."))
    tar = {d["Mezzo"]: d["Tariffa oraria"] for d in det}
    righe_uso = [{**u, "Tariffa": tar[u["Mezzo"]], "Costo": u["Ore"] * tar[u["Mezzo"]]} for u in uso12]
    comm = []
    for c in sorted({u["Commessa"] for u in righe_uso}):
        m = [u for u in righe_uso if u["Commessa"] == c]
        comm.append({"Commessa": c, "Ore": sum(u["Ore"] for u in m), "Costo mezzi": sum(u["Costo"] for u in m)})
    cs = conta([s["Stato"] for s in rs])
    kpi = {"n_mezzi": len(det), "costo_imputato": sum(d["Costo imputato"] for d in det), "fissi_non_assorbiti": sum(d["Fissi non assorbiti"] for d in det),
           "ore_12m": sum(d["Ore 12 mesi"] for d in det), "scad_scadute": cs["bad"], "scad_in_arrivo": cs["warn"], "scad_ok": cs["ok"],
           "sottoutilizzati": sum(1 for d in det if d["Utilizzo %"] < soglia), "n_bad": sum(1 for d in det if d["Stato"] == "bad"), "n_warn": sum(1 for d in det if d["Stato"] == "warn")}
    return {"params": {"oggi": oggi, "preavviso_gg": prev, "utilizzo_min_pct": soglia}, "mezzi": det, "uso": righe_uso, "commesse": comm, "scadenze": rs, "kpi": kpi, "avvisi": avvisi}


def per_sl_costi(out):
    """Costi dei mezzi per commessa, come righe per la tabella Costi di SAL e contabilita' lavori (fornitore interno, gia' saldati)."""
    return [{"Commessa": u["Commessa"], "Data": u["Data"], "Fornitore": "Parco mezzi interno", "Descrizione": f"{u['Mezzo']} - {u['Ore']:g} h", "Categoria": "Mezzi",
             "Importo": round(u["Costo"], 2), "Pagato": round(u["Costo"], 2)} for u in out["uso"] if u["Commessa"] != "(senza commessa)"]
