"""
og.py - Organico e carico di lavoro: capacita' delle risorse, assegnazioni alle commesse mese per mese, sovraccarichi e ore inutilizzate.
Una assegnazione vale per ogni mese compreso tra Dal e Al (Al vuoto = senza fine), con le ore mensili indicate.
"""
import datetime as dt

from core import to_float
from sc import data_da
from scad import oggi_da

OG_DEFAULT = {"oggi": None, "mesi": 6, "sat_min_pct": 60.0}
COLONNE_RIS = ["Risorsa", "Ruolo", "Costo_orario", "Ore_mese"]
ETICHETTE_RIS = {"Risorsa": "Risorsa (persona o squadra)", "Ruolo": "Ruolo", "Costo_orario": "Costo orario (€/h)", "Ore_mese": "Ore disponibili al mese"}
COLONNE_ASS = ["Risorsa", "Commessa", "Dal", "Al", "Ore_mese"]
ETICHETTE_ASS = {"Risorsa": "Risorsa", "Commessa": "Commessa", "Dal": "Dal", "Al": "Al", "Ore_mese": "Ore al mese"}
MESI_IT = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]


def normalizza_ris(righe):
    out, avvisi, visti = [], [], set()
    for i, r in enumerate(righe or [], start=1):
        if not any(str(r.get(c) or "").strip() for c in COLONNE_RIS):
            continue
        n, ore = str(r.get("Risorsa") or "").strip(), to_float(r.get("Ore_mese"), 0.0)
        if not n or ore <= 0:
            avvisi.append(f"Riga {i} delle risorse: servono nome e ore disponibili, riga ignorata.")
            continue
        if n in visti:
            avvisi.append(f"Risorsa «{n}» ripetuta: la seconda riga è ignorata.")
            continue
        visti.add(n)
        out.append({"Risorsa": n, "Ruolo": str(r.get("Ruolo") or "").strip(), "Costo_orario": max(0.0, to_float(r.get("Costo_orario"), 0.0)), "Ore_mese": ore})
    return out, avvisi


def normalizza_ass(righe, nomi):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(str(r.get(c) or "").strip() for c in COLONNE_ASS):
            continue
        n, c, dal, al, ore = str(r.get("Risorsa") or "").strip(), str(r.get("Commessa") or "").strip(), data_da(r.get("Dal")), data_da(r.get("Al")), to_float(r.get("Ore_mese"), 0.0)
        if n not in nomi or not c or dal is None or ore <= 0 or (al and al < dal):
            avvisi.append(f"Riga {i} delle assegnazioni: dati non validi (risorsa, commessa, date o ore), riga ignorata.")
            continue
        out.append({"Risorsa": n, "Commessa": c, "Dal": dal.isoformat(), "Al": al.isoformat() if al else "", "Ore_mese": ore})
    return out, avvisi


def _mesi(inizio, n):
    out, y, m = [], inizio.year, inizio.month
    for _ in range(n):
        a = dt.date(y, m, 1)
        y2, m2 = (y + 1, 1) if m == 12 else (y, m + 1)
        out.append((a, dt.date(y2, m2, 1) - dt.timedelta(days=1)))
        y, m = y2, m2
    return out


def calcola_og(ris, ass, p=None):
    q = {**OG_DEFAULT, **(p or {})}
    oggi = oggi_da(q)
    n = int(min(24, max(1, to_float(q["mesi"], 6))))
    sat_min = to_float(q["sat_min_pct"], 60.0)
    mesi, avvisi = [], []
    cap_r = {r["Risorsa"]: r for r in ris}
    per_comm, matrice = {}, {r["Risorsa"]: [] for r in ris}
    for a, b in _mesi(oggi, n):
        etic = f"{MESI_IT[a.month - 1]} {a.year}"
        ass_r = {r["Risorsa"]: 0.0 for r in ris}
        costo = 0.0
        for x in ass:
            dal, al = data_da(x["Dal"]), data_da(x["Al"])
            if dal <= b and (al is None or al >= a):
                ass_r[x["Risorsa"]] += x["Ore_mese"]
                c = x["Ore_mese"] * cap_r[x["Risorsa"]]["Costo_orario"]
                costo += c
                per_comm.setdefault(x["Commessa"], {})
                per_comm[x["Commessa"]][etic] = per_comm[x["Commessa"]].get(etic, 0.0) + c
        cap = sum(r["Ore_mese"] for r in ris)
        tot = sum(ass_r.values())
        extra = sum(max(0.0, ass_r[k] - cap_r[k]["Ore_mese"]) for k in ass_r)
        libere = sum(max(0.0, cap_r[k]["Ore_mese"] - ass_r[k]) for k in ass_r)
        inattivo = sum(max(0.0, cap_r[k]["Ore_mese"] - ass_r[k]) * cap_r[k]["Costo_orario"] for k in ass_r)
        for k in ass_r:
            matrice[k].append(ass_r[k] / cap_r[k]["Ore_mese"] * 100.0)
        sat = tot / cap * 100.0 if cap else 0.0
        stato = "bad" if extra > 0 else ("warn" if sat < sat_min else "ok")
        mesi.append({"Mese": etic, "Capacità ore": cap, "Ore assegnate": tot, "Saturazione %": sat, "Ore extra necessarie": extra, "Ore libere": libere,
                     "Costo assegnato": costo, "Costo ore inattive": inattivo, "Stato": stato})
        if extra > 0:
            avvisi.append(f"{etic}: servono circa {extra:,.0f} ore in più della capacità (sovraccarico).".replace(",", "."))
    mesi_label = [m["Mese"] for m in mesi]
    risorse = [{"Risorsa": k, "Ruolo": cap_r[k]["Ruolo"], **{mesi_label[i]: round(v) for i, v in enumerate(vals)}, "Picco %": max(vals) if vals else 0.0,
                "Stato": "bad" if vals and max(vals) > 100 else ("warn" if vals and max(vals) < sat_min else "ok")} for k, vals in matrice.items()]
    commesse = [{"Commessa": c, **{m: round(v.get(m, 0.0)) for m in mesi_label}, "Totale": round(sum(v.values()))} for c, v in sorted(per_comm.items())]
    ore_media = (sum(r["Ore_mese"] for r in ris) / len(ris)) if ris else 0.0
    picco_extra = max((m["Ore extra necessarie"] for m in mesi), default=0.0)
    kpi = {"n_risorse": len(ris), "capacita_mensile": sum(r["Ore_mese"] for r in ris), "saturazione_media": (sum(m["Saturazione %"] for m in mesi) / len(mesi)) if mesi else 0.0,
           "picco_saturazione": max((m["Saturazione %"] for m in mesi), default=0.0), "mesi_sovraccarico": sum(1 for m in mesi if m["Stato"] == "bad"),
           "mesi_scarico": sum(1 for m in mesi if m["Stato"] == "warn"), "ore_extra_picco": picco_extra, "persone_in_piu_picco": (picco_extra / ore_media) if ore_media else 0.0,
           "costo_inattivo": sum(m["Costo ore inattive"] for m in mesi), "costo_assegnato": sum(m["Costo assegnato"] for m in mesi)}
    return {"params": {"oggi": oggi, "mesi": n, "sat_min_pct": sat_min}, "mesi": mesi, "risorse": risorse, "commesse": commesse, "kpi": kpi, "avvisi": avvisi}
