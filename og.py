"""
og.py - Organico e carico di lavoro: capacita' delle risorse, assegnazioni alle commesse mese per mese, sovraccarichi e ore inutilizzate.
Una assegnazione vale per ogni mese compreso tra Dal e Al (Al vuoto = senza fine), con le ore mensili indicate.
"""
import datetime as dt

from core import to_float
from sc import data_da
from scad import oggi_da

OG_DEFAULT = {"oggi": None, "mesi": 6, "sat_min_pct": 60.0, "ore_giorno": 8.0, "festivita": True, "patrono": ""}
COLONNE_RIS = ["Risorsa", "Ruolo", "Costo_orario", "Ore_giorno", "Ore_mese", "Assunzione", "Cessazione"]
ETICHETTE_RIS = {"Risorsa": "Risorsa (persona o squadra)", "Ruolo": "Ruolo", "Costo_orario": "Costo orario aziendale (€/h)",
                 "Ore_giorno": "Ore al giorno (vuoto = 8; part-time = meno)", "Ore_mese": "Ore al mese fisse (facoltativo: vuoto = uso il calendario)",
                 "Assunzione": "Assunto dal (facoltativo)", "Cessazione": "Cessato il (facoltativo)"}
COLONNE_ASS = ["Risorsa", "Commessa", "Dal", "Al", "Ore_mese"]
ETICHETTE_ASS = {"Risorsa": "Risorsa", "Commessa": "Commessa", "Dal": "Dal", "Al": "Al", "Ore_mese": "Ore al mese"}
COLONNE_ASSENZE = ["Risorsa", "Dal", "Al", "Motivo"]
ETICHETTE_ASSENZE = {"Risorsa": "Risorsa (o «Tutti» per una chiusura aziendale)", "Dal": "Dal", "Al": "Al (vuoto = solo quel giorno)", "Motivo": "Motivo (ferie, malattia, ponte...)"}
MESI_IT = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
TUTTI = "tutti"


def _s(v):
    if v is None or (isinstance(v, float) and v != v):
        return ""
    return str(v).strip()


def normalizza_ris(righe):
    """Risorse. Ore_giorno e Ore_mese sono facoltative: senza nessuna delle due si calcola con 8 ore al giorno dal calendario.
    Con Ore_mese (e senza Ore_giorno) si usano quelle ore fisse, ridotte in proporzione ai giorni in cui la persona e' in forza."""
    out, avvisi, visti = [], [], set()
    for i, r in enumerate(righe or [], start=1):
        if not any(_s(r.get(c)) for c in COLONNE_RIS):
            continue
        n = _s(r.get("Risorsa"))
        if not n:
            avvisi.append(f"Riga {i} delle risorse: manca il nome, riga ignorata.")
            continue
        if n in visti:
            avvisi.append(f"Risorsa «{n}» ripetuta: la seconda riga è ignorata.")
            continue
        visti.add(n)
        og_, om = max(0.0, to_float(r.get("Ore_giorno"), 0.0)), max(0.0, to_float(r.get("Ore_mese"), 0.0))
        if og_ > 24:
            avvisi.append(f"«{n}»: più di 24 ore al giorno non è possibile, uso 8.")
            og_ = 0.0
        ass_, ces = data_da(r.get("Assunzione")), data_da(r.get("Cessazione"))
        if ass_ and ces and ces < ass_:
            avvisi.append(f"«{n}»: la cessazione è prima dell'assunzione, ignoro la cessazione.")
            ces = None
        out.append({"Risorsa": n, "Ruolo": _s(r.get("Ruolo")), "Costo_orario": max(0.0, to_float(r.get("Costo_orario"), 0.0)), "Ore_giorno": og_, "Ore_mese": om,
                    "Assunzione": ass_.isoformat() if ass_ else "", "Cessazione": ces.isoformat() if ces else ""})
    return out, avvisi


def normalizza_assenze(righe, nomi):
    """Ferie, malattie, chiusure: una riga per periodo. «Tutti» = chiusura per tutta l'azienda."""
    out, avvisi = [], []
    ok = {n.lower() for n in nomi} | {TUTTI}
    for i, r in enumerate(righe or [], start=1):
        if not any(_s(r.get(c)) for c in COLONNE_ASSENZE):
            continue
        n, dal = _s(r.get("Risorsa")), data_da(r.get("Dal"))
        al = data_da(r.get("Al")) or dal
        if n.lower() not in ok or dal is None or (al and al < dal):
            avvisi.append(f"Riga {i} delle assenze: risorsa o date non valide, riga ignorata.")
            continue
        out.append({"Risorsa": TUTTI.capitalize() if n.lower() == TUTTI else next((x for x in nomi if x.lower() == n.lower()), n), "Dal": dal.isoformat(), "Al": al.isoformat(), "Motivo": _s(r.get("Motivo"))})
    return out, avvisi


# ----------------------------------------------------------------------------
# CALENDARIO: giorni lavorativi veri (lun-ven, senza festivita' e chiusure)
# ----------------------------------------------------------------------------
def _patrono(testo):
    """«GG/MM» o «GG-MM» -> (mese, giorno), oppure None."""
    import re
    m = re.match(r"^\s*(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*$", str(testo or ""))
    if not m:
        return None
    g, me = int(m.group(1)), int(m.group(2))
    return (me, g) if 1 <= me <= 12 and 1 <= g <= 31 else None


def festivi(a, b, nazionali=True, patrono=""):
    """Insieme delle date festive (festivita' nazionali con Pasquetta + festa del patrono) tra a e b inclusi."""
    import gt
    out = set()
    pat = _patrono(patrono)
    for anno in range(a.year, b.year + 1):
        if nazionali:
            out |= {data_da(x["Dal"]) for x in gt.festivita_italiane(anno)}
        if pat:
            try:
                out.add(dt.date(anno, pat[0], pat[1]))
            except ValueError:
                pass
    return {d for d in out if a <= d <= b}


def _giorni(a, b):
    d = a
    while d <= b:
        yield d
        d += dt.timedelta(days=1)


def giorni_lavorativi_mese(a, b, fest):
    """Giorni dal lunedi' al venerdi' tra a e b, senza le date in `fest`."""
    return sum(1 for d in _giorni(a, b) if d.weekday() < 5 and d not in fest)


def capacita_risorsa(r, a, b, fest, assenze, ore_giorno_default=8.0):
    """(ore disponibili, giorni disponibili) di una risorsa tra a e b: lun-ven, senza festivita', chiusure e assenze, solo dall'assunzione alla cessazione."""
    ass_, ces = data_da(r["Assunzione"]), data_da(r["Cessazione"])
    mie = [(data_da(x["Dal"]), data_da(x["Al"])) for x in assenze if x["Risorsa"].lower() in (TUTTI, r["Risorsa"].lower())]
    giorni = 0
    for d in _giorni(a, b):
        if d.weekday() >= 5 or d in fest:
            continue
        if (ass_ and d < ass_) or (ces and d > ces):
            continue
        if any(x <= d <= y for x, y in mie):
            continue
        giorni += 1
    if r["Ore_giorno"] > 0 or r["Ore_mese"] <= 0:
        return giorni * (r["Ore_giorno"] if r["Ore_giorno"] > 0 else ore_giorno_default), giorni
    base = giorni_lavorativi_mese(a, b, fest)
    return (r["Ore_mese"] * giorni / base if base else 0.0), giorni


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


def calcola_og(ris, ass, p=None, assenze=None):
    """Capacita' mese per mese dal calendario vero (lun-ven, senza festivita' e assenze, dall'assunzione alla cessazione)."""
    q = {**OG_DEFAULT, **(p or {})}
    oggi = oggi_da(q)
    n = int(min(24, max(1, to_float(q["mesi"], 6))))
    sat_min = to_float(q["sat_min_pct"], 60.0)
    og_def = to_float(q.get("ore_giorno"), 8.0) or 8.0
    mesi, avvisi = [], []
    periodi = _mesi(oggi, n)
    fest = festivi(periodi[0][0], periodi[-1][1], bool(q.get("festivita", True)), q.get("patrono", ""))
    ass_l = list(assenze or [])
    # le persone gia' cessate non entrano piu' in capacita', costi e previsioni
    attive = [r for r in ris if not (data_da(r["Cessazione"]) and data_da(r["Cessazione"]) < periodi[0][0])]
    usciti = [r["Risorsa"] for r in ris if r not in attive]
    if usciti:
        avvisi.append("Non più in forza (esclusi dai calcoli): " + ", ".join(usciti) + ".")
    ass = [x for x in ass if x["Risorsa"] not in usciti]
    cap_r = {r["Risorsa"]: r for r in attive}
    per_comm, matrice = {}, {r["Risorsa"]: [] for r in attive}
    giorni_mese = []
    for a, b in periodi:
        etic = f"{MESI_IT[a.month - 1]} {a.year}"
        capm = {r["Risorsa"]: capacita_risorsa(r, a, b, fest, ass_l, og_def) for r in attive}
        giorni_mese.append(giorni_lavorativi_mese(a, b, fest))
        ass_r = {r["Risorsa"]: 0.0 for r in attive}
        costo = 0.0
        for x in ass:
            dal, al = data_da(x["Dal"]), data_da(x["Al"])
            if dal <= b and (al is None or al >= a):
                ass_r[x["Risorsa"]] += x["Ore_mese"]
                c = x["Ore_mese"] * cap_r[x["Risorsa"]]["Costo_orario"]
                costo += c
                per_comm.setdefault(x["Commessa"], {})
                per_comm[x["Commessa"]][etic] = per_comm[x["Commessa"]].get(etic, 0.0) + c
        cap = sum(v[0] for v in capm.values())
        tot = sum(ass_r.values())
        extra = sum(max(0.0, ass_r[k] - capm[k][0]) for k in ass_r)
        libere = sum(max(0.0, capm[k][0] - ass_r[k]) for k in ass_r)
        inattivo = sum(max(0.0, capm[k][0] - ass_r[k]) * cap_r[k]["Costo_orario"] for k in ass_r)
        for k in ass_r:
            matrice[k].append(ass_r[k] / capm[k][0] * 100.0 if capm[k][0] else (999.0 if ass_r[k] > 0 else 0.0))
            if ass_r[k] > 0 and capm[k][0] <= 0:
                avvisi.append(f"{etic}: «{k}» ha ore assegnate ma non è in forza o è assente tutto il mese.")
        sat = tot / cap * 100.0 if cap else 0.0
        stato = "bad" if extra > 0 else ("warn" if sat < sat_min else "ok")
        mesi.append({"Mese": etic, "Giorni lavorativi": giorni_mese[-1], "Capacità ore": cap, "Ore assegnate": tot, "Saturazione %": sat, "Ore extra necessarie": extra,
                     "Ore libere": libere, "Costo assegnato": costo, "Costo ore inattive": inattivo, "Stato": stato})
        if extra > 0:
            avvisi.append(f"{etic}: servono circa {extra:,.0f} ore in più della capacità (sovraccarico).".replace(",", "."))
    mesi_label = [m["Mese"] for m in mesi]
    risorse = [{"Risorsa": k, "Ruolo": cap_r[k]["Ruolo"], **{mesi_label[i]: round(v) for i, v in enumerate(vals)}, "Picco %": max(vals) if vals else 0.0,
                "Stato": "bad" if vals and max(vals) > 100 else ("warn" if vals and max(vals) < sat_min else "ok")} for k, vals in matrice.items()]
    commesse = [{"Commessa": c, **{m: round(v.get(m, 0.0)) for m in mesi_label}, "Totale": round(sum(v.values()))} for c, v in sorted(per_comm.items())]
    cap0 = mesi[0]["Capacità ore"] if mesi else 0.0
    ore_media = (cap0 / len(attive)) if attive else 0.0
    picco_extra = max((m["Ore extra necessarie"] for m in mesi), default=0.0)
    kpi = {"n_risorse": len(attive), "capacita_mensile": cap0, "saturazione_media": (sum(m["Saturazione %"] for m in mesi) / len(mesi)) if mesi else 0.0,
           "picco_saturazione": max((m["Saturazione %"] for m in mesi), default=0.0), "mesi_sovraccarico": sum(1 for m in mesi if m["Stato"] == "bad"),
           "mesi_scarico": sum(1 for m in mesi if m["Stato"] == "warn"), "ore_extra_picco": picco_extra, "persone_in_piu_picco": (picco_extra / ore_media) if ore_media else 0.0,
           "costo_inattivo": sum(m["Costo ore inattive"] for m in mesi), "costo_assegnato": sum(m["Costo assegnato"] for m in mesi), "n_usciti": len(usciti),
           "giorni_festivi": len(fest)}
    return {"params": {"oggi": oggi, "mesi": n, "sat_min_pct": sat_min, "ore_giorno": og_def, "patrono": q.get("patrono", "")}, "mesi": mesi, "risorse": risorse,
            "commesse": commesse, "kpi": kpi, "avvisi": list(dict.fromkeys(avvisi))}
