"""
gt.py - Cronoprogramma dei cantieri (diagramma di Gantt): fasi con inizio, fine e avanzamento, confronto tra avanzamento previsto e reale,
ritardi e stima della fine. Deterministico e senza Streamlit.

Regole (dichiarate anche nel dossier):
  - Avanzamento previsto di una fase oggi = quota di durata trascorsa (lineare tra inizio e fine).
  - Scostamento = avanzamento reale - previsto (in punti %). Sotto -soglia: «in ritardo»; sotto -2*soglia o fase oltre la fine non completata: «critica».
  - Fine stimata = inizio + durata / (avanzamento reale / previsto), con ritmo tra 0,34 e 1 (non si anticipa mai la fine prevista, e al massimo si triplica la durata).
  - Legami: la colonna «Dopo» indica da quali fasi (dello stesso cantiere) dipende una fase. Una fase non ancora iniziata non parte prima della fine (stimata) delle fasi da cui dipende:
    se queste slittano, slitta anche lei (a catena). Una fase gia' iniziata resta dov'e', ma si segnala se e' partita prima della fine delle precedenti.
    «Dopo» accetta anche un'attesa o un anticipo: «Strutture +5» = 5 giorni dopo la fine; «Strutture -10» = parte 10 giorni prima che finiscano (sovrapposizione).
  - «Non prima del»: data minima di inizio (arrivo materiali, permessi). Una fase non iniziata non parte prima.
  - Giorni di fermo (ferie, maltempo, festivita'): i giorni di fermo che cadono dentro una fase non completata la allungano di altrettanti giorni, e le fasi successive slittano.
  - Commessa: avanzamento pesato sulla durata delle fasi; inizio = prima fase, fine = ultima.
"""
import datetime as dt
import re

from core import to_float
from sc import data_da
from scad import oggi_da

GT_DEFAULT = {"oggi": None, "soglia_pct": 15.0, "preavviso_gg": 7}
LIMITI_GT = {"soglia_pct": (1.0, 60.0), "preavviso_gg": (0, 60)}
COLONNE_FASI = ["Commessa", "Fase", "Inizio", "Fine", "Avanzamento", "Responsabile", "Dopo", "NonPrima"]
COLONNE_FERMI = ["Commessa", "Dal", "Al", "Motivo"]
ETICHETTE_FERMI = {"Commessa": "Cantiere (o «Tutti»)", "Dal": "Dal", "Al": "Al (incluso)", "Motivo": "Motivo"}
ETICHETTE_FASI = {"Commessa": "Cantiere / commessa", "Fase": "Fase", "Inizio": "Inizio", "Fine": "Fine prevista", "Avanzamento": "Avanzamento reale (%)", "Responsabile": "Responsabile", "Dopo": "Parte dopo la fase…", "NonPrima": "Non prima del"}


def _txt(v):
    return "" if v is None or v != v else str(v).strip()


def _elenco_dopo(testo):
    return [x.strip() for x in re.split(r"[;,\n]", testo or "") if x.strip()]


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
                    "Responsabile": _txt(r.get("Responsabile")), "Dopo": _txt(r.get("Dopo")),
                    "NonPrima": (data_da(r.get("NonPrima")).isoformat() if data_da(r.get("NonPrima")) else "")})
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


_LEGAME = re.compile(r"^(.*?)\s*([+-]\s*\d+)\s*(?:gg?|giorni|giorno)?$", re.IGNORECASE)


def _legame(testo):
    """«Strutture» -> ("Strutture", 0); «Strutture +5» -> 5 giorni dopo la fine; «Strutture -10» -> parte 10 giorni prima della fine."""
    t = testo.strip()
    m = _LEGAME.match(t)
    if m and m.group(1).strip():
        return m.group(1).strip(), int(m.group(2).replace(" ", ""))
    return t, 0


def normalizza_fermi(righe):
    """Giorni di fermo: ferie, maltempo, festivita'. Cantiere vuoto o «Tutti» = vale per ogni cantiere."""
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(_txt(r.get(c)) for c in COLONNE_FERMI):
            continue
        d0, d1 = data_da(r.get("Dal")), data_da(r.get("Al"))
        if d0 is None:
            avvisi.append(f"Fermo {i}: manca la data «Dal», riga ignorata.")
            continue
        d1 = d1 or d0
        if d1 < d0:
            d0, d1 = d1, d0
        c = _txt(r.get("Commessa"))
        out.append({"Commessa": "" if c.lower() in ("", "tutti", "tutte", "*") else c, "Dal": d0.isoformat(), "Al": d1.isoformat(), "Motivo": _txt(r.get("Motivo"))})
    return out, avvisi


def festivita_italiane(anno):
    """Festivita' nazionali italiane (con Pasquetta) per l'anno indicato."""
    a, b, c = anno % 19, anno // 100, anno % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mese, giorno = divmod(h + l - 7 * m + 114, 31)
    pasqua = dt.date(anno, mese, giorno + 1)
    fisse = [((1, 1), "Capodanno"), ((1, 6), "Epifania"), ((4, 25), "Liberazione"), ((5, 1), "Festa del lavoro"), ((6, 2), "Festa della Repubblica"), ((8, 15), "Ferragosto"),
             ((11, 1), "Ognissanti"), ((12, 8), "Immacolata"), ((12, 25), "Natale"), ((12, 26), "Santo Stefano")]
    out = [{"Commessa": "Tutti", "Dal": dt.date(anno, m_, g_).isoformat(), "Al": dt.date(anno, m_, g_).isoformat(), "Motivo": n} for (m_, g_), n in fisse]
    p2 = pasqua + dt.timedelta(days=1)
    out.append({"Commessa": "Tutti", "Dal": p2.isoformat(), "Al": p2.isoformat(), "Motivo": "Pasquetta"})
    return sorted(out, key=lambda x: x["Dal"])


def _giorni_fermo(fermi, commessa, d0, d1):
    """Insieme dei giorni di fermo (per quel cantiere) tra d0 incluso e d1 escluso."""
    s = set()
    for x in fermi:
        if x["Commessa"] and x["Commessa"].lower() != commessa.lower():
            continue
        a, b = data_da(x["Dal"]), data_da(x["Al"])
        giorno = max(a, d0)
        while giorno <= b and giorno < d1:
            s.add(giorno)
            giorno += dt.timedelta(days=1)
    return s


def _applica_legami(fl, oggi, fermi=()):
    """Propaga legami («Dopo», con anticipi/attese), vincoli «Non prima del» e giorni di fermo. Aggiorna in place Inizio stimato, Fine stimata, Slitta gg,
    Giorni di fermo, Motivo e Stato. Ritorna gli avvisi."""
    note = []
    chiave = lambda f: (f["Commessa"].lower(), f["Fase"].lower())
    idx = {chiave(f): f for f in fl}
    for f in fl:
        f["Legami"] = []
        for voce in _elenco_dopo(f.get("Dopo")):
            nome, lag = _legame(voce)
            p = idx.get((f["Commessa"].lower(), nome.lower()))
            if p is None:
                note.append(f"{f['Commessa']} · {f['Fase']}: la fase «{nome}» indicata in «Parte dopo» non esiste in questo cantiere, legame ignorato.")
            elif p is f:
                note.append(f"{f['Commessa']} · {f['Fase']}: non può partire dopo se stessa, legame ignorato.")
            else:
                f["Legami"].append((p["Fase"], lag))
                f["Predecessori"].append(p["Fase"])
    stato_v, ordine = {}, []

    def visita(f):
        k = chiave(f)
        if stato_v.get(k) is not None:
            return
        stato_v[k] = 1
        for nome, lag in list(f["Legami"]):
            p = idx[(f["Commessa"].lower(), nome.lower())]
            if stato_v.get(chiave(p)) == 1:
                f["Legami"].remove((nome, lag))
                f["Predecessori"].remove(nome)
                note.append(f"{f['Commessa']} · {f['Fase']}: i legami «Parte dopo» fanno un giro chiuso con «{nome}», legame ignorato.")
                continue
            visita(p)
        stato_v[k] = 2
        ordine.append(f)
    for f in fl:
        visita(f)
    for f in ordine:
        iniz_ok = f["Avanzamento"] > 0 or f["Stato"] == "done"          # gia' iniziata: non si sposta
        motivi, richiesta = [], None
        for nome, lag in f["Legami"]:
            p = idx[(f["Commessa"].lower(), nome.lower())]
            fp = min(p["d1"], oggi) if p["Stato"] == "done" else data_da(p["Fine stimata"])
            req = fp + dt.timedelta(days=lag)
            if richiesta is None or req > richiesta[0]:
                richiesta = (req, f"«{nome}» finisce il {fp.strftime('%d/%m/%Y')}" + (f" e servono {lag} giorni di attesa" if lag > 0 else (f" e questa fase parte {-lag} giorni prima" if lag < 0 else "")))
            if f["Avanzamento"] > 0 and p["Stato"] != "done" and lag >= 0:
                note.append(f"{f['Commessa']} · {f['Fase']}: è già iniziata ma «{p['Fase']}» non è ancora finita ({p['Avanzamento']:.0f}%).")
            if f["Avanzamento"] <= 0 and f["d0"] < p["d1"] + dt.timedelta(days=lag):
                note.append(f"{f['Commessa']} · {f['Fase']}: nel piano parte il {f['d0'].strftime('%d/%m/%Y')}, prima di quanto permette «{p['Fase']}» (fine prevista {p['d1'].strftime('%d/%m/%Y')}): controlla le date.")
        vincolo = data_da(f.get("NonPrima"))
        if vincolo and not iniz_ok and (richiesta is None or vincolo > richiesta[0]):
            richiesta = (vincolo, f"c'è il vincolo «non prima del {vincolo.strftime('%d/%m/%Y')}» (materiali o permessi)")
        ist = f["d0"]
        if richiesta and not iniz_ok and richiesta[0] > ist:
            ist = richiesta[0]
            motivi.append(f"parte il {ist.strftime('%d/%m/%Y')} invece del {f['d0'].strftime('%d/%m/%Y')} perché {richiesta[1]}")
        durata_giorni = (f["d1"] - f["d0"]).days
        fine = data_da(f["Fine stimata"])
        extra = 0
        if f["Stato"] != "done":
            if not iniz_ok:                                           # l'inizio non cade in un giorno di fermo
                mosso = False
                while _giorni_fermo(fermi, f["Commessa"], ist, ist + dt.timedelta(days=1)):
                    ist += dt.timedelta(days=1)
                    mosso = True
                if mosso:
                    motivi.append(f"l'inizio cade in un giorno di fermo: parte il {ist.strftime('%d/%m/%Y')}")
                fine = max(fine, ist + dt.timedelta(days=durata_giorni)) if ist != f["d0"] else fine
            base = max(ist, oggi) if iniz_ok else ist
            while True:                                               # i giorni di fermo dentro la fase allungano la fase, e questo puo' farne entrare altri
                n = len(_giorni_fermo(fermi, f["Commessa"], base, fine + dt.timedelta(days=extra)))
                if n == extra:
                    break
                extra = n
            if extra:
                fine += dt.timedelta(days=extra)
                motivi.append(f"si ferma {extra} giorni (ferie, maltempo o festività): finisce il {fine.strftime('%d/%m/%Y')}")
        f["Inizio stimato"] = ist.isoformat()
        f["Slitta gg"] = (ist - f["d0"]).days
        f["Giorni di fermo"] = extra
        f["Fine stimata"] = fine.isoformat()
        if f["Stato"] != "done" and (extra or f["Slitta gg"] > 0):
            f["Ritardo gg"] = max(f["Ritardo gg"], (fine - f["d1"]).days)
        f["Motivo"] = "; ".join(motivi)
        if motivi and f["Stato"] in ("wait", "ok") and (fine > f["d1"] or f["Slitta gg"] > 0):
            f["Stato"] = "warn"
    return note


def calcola_gt(fasi, p=None, fermi=None):
    fermi = fermi or []
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
                   "In scadenza": av < 100 and 0 <= (d1 - oggi).days <= prev_gg, "Inizio stimato": d0.isoformat(), "Slitta gg": 0, "Giorni di fermo": 0, "Predecessori": [], "Legami": [], "Motivo": ""})
    note = _applica_legami(fl, oggi, fermi)
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
           "ritardo_max_gg": max([c["Ritardo gg"] for c in commesse] + [0]), "completate": sum(1 for f in fl if f["Stato"] == "done"), "fasi_slittate": sum(1 for f in fl if f["Slitta gg"] > 0 or f["Giorni di fermo"] > 0),
           "legami": sum(len(f["Predecessori"]) for f in fl)}
    avvisi = []
    for f in fl:
        if f["Stato"] not in ("bad", "warn"):
            continue
        if f["Motivo"] and f["Avanzamento"] <= 0 and f["Stato"] == "warn":
            avvisi.append(f"{f['Commessa']} · {f['Fase']}: {f['Motivo']}.")
        elif f["Stato"] == "bad" and oggi > f["d1"]:
            avvisi.append(f"{f['Commessa']} · {f['Fase']}: oltre la fine prevista e non completata ({f['Avanzamento']:.0f}%).")
        else:
            avvisi.append(f"{f['Commessa']} · {f['Fase']}: avanzamento {f['Avanzamento']:.0f}% contro {f['Prevista']:.0f}% previsto.")
    avvisi += note
    return {"params": {**p, "oggi": oggi}, "fasi": fl, "commesse": commesse, "kpi": kpi, "avvisi": avvisi}


def fasi_da_commesse_sl(commesse):
    """Una fase «Intera commessa» per ogni commessa del SAL che ha inizio e fine previsti."""
    out = []
    for c in commesse or []:
        d0, d1 = data_da(c.get("Inizio")), data_da(c.get("Fine_prev"))
        if str(c.get("Commessa") or "").strip() and d0 and d1:
            out.append({"Commessa": str(c["Commessa"]).strip(), "Fase": "Intera commessa", "Inizio": d0.isoformat(), "Fine": d1.isoformat(),
                        "Avanzamento": to_float(c.get("Avanz_reale_pct"), 0.0), "Responsabile": "", "Dopo": "", "NonPrima": ""})
    return out


def fasi_da_assegnazioni(assegnazioni, oggi=None):
    """Una fase per ogni assegnazione di Organico (risorsa su commessa); «Al» vuoto = un anno da «Dal»."""
    out = []
    for a in assegnazioni or []:
        d0 = data_da(a.get("Dal"))
        if not (str(a.get("Commessa") or "").strip() and d0):
            continue
        d1 = data_da(a.get("Al")) or (d0 + dt.timedelta(days=365))
        out.append({"Commessa": str(a["Commessa"]).strip(), "Fase": str(a.get("Risorsa") or "Squadra").strip(), "Inizio": d0.isoformat(), "Fine": d1.isoformat(), "Avanzamento": 0.0, "Responsabile": "", "Dopo": "", "NonPrima": ""})
    return out


def in_sequenza(fasi):
    """Per ogni cantiere, mette ogni fase «dopo» quella che la precede per data di inizio (solo dove «Dopo» e' vuoto). Restituisce le righe aggiornate."""
    per = {}
    for i, f in enumerate(fasi):
        per.setdefault(str(f.get("Commessa") or "").strip().lower(), []).append(i)
    out = [dict(f) for f in fasi]
    for idxs in per.values():
        ordinate = sorted(idxs, key=lambda i: (str(data_da(fasi[i].get("Inizio")) or "9999"), str(data_da(fasi[i].get("Fine")) or "9999")))
        for prev, cur in zip(ordinate, ordinate[1:]):
            if not _txt(fasi[cur].get("Dopo")) and _txt(fasi[prev].get("Fase")):
                out[cur]["Dopo"] = _txt(fasi[prev].get("Fase"))
    return out
