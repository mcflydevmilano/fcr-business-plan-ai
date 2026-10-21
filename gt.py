"""
gt.py - Cronoprogramma dei cantieri (diagramma di Gantt): fasi con inizio, fine e avanzamento, confronto tra avanzamento previsto e reale,
ritardi e stima della fine. Deterministico e senza Streamlit.

Regole (dichiarate anche nel dossier):
  - Avanzamento previsto di una fase oggi = quota di durata trascorsa (lineare tra inizio e fine).
  - Scostamento = avanzamento reale - previsto (in punti %). Sotto -soglia: «in ritardo»; sotto -2*soglia o fase oltre la fine non completata: «critica».
  - Fine stimata = inizio + durata / (avanzamento reale / previsto), con ritmo tra 0,34 e 1 (non si anticipa mai la fine prevista, e al massimo si triplica la durata).
  - Commessa: avanzamento pesato sulla durata delle fasi; inizio = prima fase, fine = ultima.
"""
import datetime as dt

from core import to_float
from sc import data_da
from scad import oggi_da

GT_DEFAULT = {"oggi": None, "soglia_pct": 15.0, "preavviso_gg": 7}
LIMITI_GT = {"soglia_pct": (1.0, 60.0), "preavviso_gg": (0, 60)}
COLONNE_FASI = ["Commessa", "Fase", "Inizio", "Fine", "Avanzamento", "Responsabile"]
ETICHETTE_FASI = {"Commessa": "Cantiere / commessa", "Fase": "Fase", "Inizio": "Inizio", "Fine": "Fine prevista", "Avanzamento": "Avanzamento reale (%)", "Responsabile": "Responsabile"}


def normalizza_fasi(righe):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(str(r.get(c) if r.get(c) == r.get(c) else "").strip() for c in COLONNE_FASI):
            continue
        com, fase = str(r.get("Commessa") or "").strip(), str(r.get("Fase") or "").strip()
        d0, d1 = data_da(r.get("Inizio")), data_da(r.get("Fine"))
        if not com or d0 is None or d1 is None:
            avvisi.append(f"Fase {i}: servono cantiere, inizio e fine, riga ignorata.")
            continue
        if d1 < d0:
            avvisi.append(f"Fase «{fase or com}»: la fine è prima dell'inizio, scambiate.")
            d0, d1 = d1, d0
        av = min(100.0, max(0.0, to_float(r.get("Avanzamento"), 0.0)))
        out.append({"Commessa": com, "Fase": fase or "Intera commessa", "Inizio": d0.isoformat(), "Fine": d1.isoformat(), "Avanzamento": av,
                    "Responsabile": str(r.get("Responsabile") or "").strip() if r.get("Responsabile") == r.get("Responsabile") else ""})
    return out, avvisi


def _prevista(d0, d1, oggi):
    if oggi <= d0:
        return 0.0
    if oggi >= d1:
        return 100.0
    return 100.0 * (oggi - d0).days / max(1, (d1 - d0).days)


def _stima_fine(d0, d1, av, prev):
    """Fine stimata con il ritmo reale; mai prima della fine prevista."""
    if av >= 100.0 or prev <= 0 or av <= 0:
        return d1
    ritmo = min(1.0, max(0.34, av / prev))
    durata = (d1 - d0).days
    return max(d1, d0 + dt.timedelta(days=round(durata / ritmo)))


def _stato(oggi, d0, d1, av, prev, soglia):
    if av >= 100.0:
        return "done"
    if oggi > d1:
        return "bad"
    if oggi < d0:
        return "wait"
    scost = av - prev
    return "bad" if scost < -2 * soglia else ("warn" if scost < -soglia else "ok")


def calcola_gt(fasi, p=None):
    p = {**GT_DEFAULT, **(p or {})}
    oggi, soglia, prev_gg = oggi_da(p), float(p["soglia_pct"]), int(p["preavviso_gg"])
    fl = []
    for f in fasi:
        d0, d1 = data_da(f["Inizio"]), data_da(f["Fine"])
        prev = _prevista(d0, d1, oggi)
        av = f["Avanzamento"]
        st = _stato(oggi, d0, d1, av, prev, soglia)
        fine_st = _stima_fine(d0, d1, av, prev) if st in ("ok", "warn", "bad") else d1
        fl.append({**f, "d0": d0, "d1": d1, "Prevista": round(prev, 1), "Scostamento": round(av - prev, 1) if st not in ("wait", "done") else 0.0, "Stato": st,
                   "Ritardo gg": (oggi - d1).days if (st == "bad" and oggi > d1) else max(0, (fine_st - d1).days), "Fine stimata": fine_st.isoformat(),
                   "In scadenza": av < 100 and 0 <= (d1 - oggi).days <= prev_gg})
    com = {}
    for f in fl:
        com.setdefault(f["Commessa"], []).append(f)
    commesse = []
    for nome, fs in com.items():
        peso = [max(1, (f["d1"] - f["d0"]).days) for f in fs]
        tot = float(sum(peso))
        av = sum(f["Avanzamento"] * w for f, w in zip(fs, peso)) / tot
        pr = sum(f["Prevista"] * w for f, w in zip(fs, peso)) / tot
        d0, d1 = min(f["d0"] for f in fs), max(f["d1"] for f in fs)
        fine_st = max([data_da(f["Fine stimata"]) for f in fs] + [d1]) if av < 100 else d1
        stati = [f["Stato"] for f in fs]
        stato = "done" if all(s == "done" for s in stati) else ("bad" if "bad" in stati else ("warn" if "warn" in stati else ("wait" if all(s in ("wait", "done") for s in stati) else "ok")))
        commesse.append({"Commessa": nome, "Inizio": d0.isoformat(), "Fine": d1.isoformat(), "Avanzamento": round(av, 1), "Prevista": round(pr, 1), "Scostamento": round(av - pr, 1),
                         "Fine stimata": fine_st.isoformat(), "Ritardo gg": max(0, (fine_st - d1).days, (oggi - d1).days if av < 100 and oggi > d1 else 0), "Fasi": len(fs),
                         "Fasi in ritardo": sum(1 for s in stati if s in ("warn", "bad")), "Stato": stato})
    ordine = {"bad": 0, "warn": 1, "ok": 2, "wait": 3, "done": 4}
    commesse.sort(key=lambda c: (ordine[c["Stato"]], c["Commessa"]))
    fl.sort(key=lambda f: (f["Commessa"], f["d0"]))
    kpi = {"commesse": len(commesse), "fasi": len(fl), "fasi_in_ritardo": sum(1 for f in fl if f["Stato"] in ("warn", "bad")), "fasi_critiche": sum(1 for f in fl if f["Stato"] == "bad"),
           "commesse_in_ritardo": sum(1 for c in commesse if c["Stato"] in ("warn", "bad")), "fasi_in_scadenza": sum(1 for f in fl if f["In scadenza"]),
           "ritardo_max_gg": max([c["Ritardo gg"] for c in commesse] + [0]), "completate": sum(1 for f in fl if f["Stato"] == "done")}
    avvisi = [f"{f['Commessa']} · {f['Fase']}: oltre la fine prevista e non completata ({f['Avanzamento']:.0f}%)." if f["Stato"] == "bad" and oggi > f["d1"]
              else f"{f['Commessa']} · {f['Fase']}: avanzamento {f['Avanzamento']:.0f}% contro {f['Prevista']:.0f}% previsto." for f in fl if f["Stato"] in ("bad", "warn")]
    return {"params": {**p, "oggi": oggi}, "fasi": fl, "commesse": commesse, "kpi": kpi, "avvisi": avvisi}


def fasi_da_commesse_sl(commesse):
    """Una fase «Intera commessa» per ogni commessa del SAL che ha inizio e fine previsti."""
    out = []
    for c in commesse or []:
        d0, d1 = data_da(c.get("Inizio")), data_da(c.get("Fine_prev"))
        if str(c.get("Commessa") or "").strip() and d0 and d1:
            out.append({"Commessa": str(c["Commessa"]).strip(), "Fase": "Intera commessa", "Inizio": d0.isoformat(), "Fine": d1.isoformat(),
                        "Avanzamento": to_float(c.get("Avanz_reale_pct"), 0.0), "Responsabile": ""})
    return out


def fasi_da_assegnazioni(assegnazioni, oggi=None):
    """Una fase per ogni assegnazione di Organico (risorsa su commessa); «Al» vuoto = un anno da «Dal»."""
    out = []
    for a in assegnazioni or []:
        d0 = data_da(a.get("Dal"))
        if not (str(a.get("Commessa") or "").strip() and d0):
            continue
        d1 = data_da(a.get("Al")) or (d0 + dt.timedelta(days=365))
        out.append({"Commessa": str(a["Commessa"]).strip(), "Fase": str(a.get("Risorsa") or "Squadra").strip(), "Inizio": d0.isoformat(), "Fine": d1.isoformat(), "Avanzamento": 0.0, "Responsabile": ""})
    return out
