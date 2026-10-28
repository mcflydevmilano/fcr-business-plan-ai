"""vr.py - Verbali e riunioni: decisioni prese e azioni assegnate con scadenza. Le azioni aperte diventano compiti (chat) e scadenze (calendario)."""
from core import to_float
from sc import data_da
from scad import oggi_da

VR_DEFAULT = {"oggi": None, "preavviso_gg": 3}
STATI = ["Aperta", "Fatta"]
COLONNE_VERBALI = ["Data", "Titolo", "Commessa", "Partecipanti", "Decisioni"]
ETICHETTE_VERBALI = {"Data": "Data", "Titolo": "Titolo della riunione", "Commessa": "Commessa", "Partecipanti": "Partecipanti", "Decisioni": "Decisioni prese"}
COLONNE_AZIONI = ["Verbale", "Azione", "Responsabile", "Scadenza", "Stato"]
ETICHETTE_AZIONI = {"Verbale": "Riunione (titolo)", "Azione": "Cosa fare", "Responsabile": "Responsabile", "Scadenza": "Scadenza", "Stato": "Stato"}


def _s(v):
    return str(v or "").strip()


def normalizza_verbali(righe):
    out, avvisi, visti = [], [], set()
    for i, r in enumerate(righe or [], start=1):
        if not any(_s(r.get(c)) for c in COLONNE_VERBALI):
            continue
        t, d = _s(r.get("Titolo")), data_da(r.get("Data"))
        if not t or d is None:
            avvisi.append(f"Riga {i} dei verbali: servono titolo e data, riga ignorata.")
            continue
        if t in visti:
            avvisi.append(f"Riunione «{t}» ripetuta: dai titoli diversi, la seconda riga è ignorata.")
            continue
        visti.add(t)
        out.append({"Data": d.isoformat(), "Titolo": t, "Commessa": _s(r.get("Commessa")), "Partecipanti": _s(r.get("Partecipanti")), "Decisioni": _s(r.get("Decisioni"))})
    return out, avvisi


def normalizza_azioni(righe, titoli):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(_s(r.get(c)) for c in COLONNE_AZIONI):
            continue
        v, a, s = _s(r.get("Verbale")), _s(r.get("Azione")), data_da(r.get("Scadenza"))
        if v not in titoli or not a:
            avvisi.append(f"Riga {i} delle azioni: " + ("riunione non presente" if v not in titoli else "manca cosa fare") + ", riga ignorata.")
            continue
        stato = "Fatta" if _s(r.get("Stato")).lower() in ("fatta", "fatto", "chiusa", "ok", "sì", "si") else "Aperta"
        out.append({"Verbale": v, "Azione": a, "Responsabile": _s(r.get("Responsabile")), "Scadenza": s.isoformat() if s else "", "Stato": stato})
    return out, avvisi


def calcola_vr(verbali, azioni, p=None):
    q = {**VR_DEFAULT, **(p or {})}
    oggi, prev = oggi_da(q), int(max(0, to_float(q["preavviso_gg"], 3)))
    righe, avvisi = [], []
    for a in azioni:
        s = data_da(a["Scadenza"])
        g = (s - oggi).days if s else None
        st = "ok" if a["Stato"] == "Fatta" else ("nd" if g is None else "bad" if g < 0 else "warn" if g <= prev else "ok")
        righe.append({**a, "Giorni": g, "Stato semaforo": st})
        if st == "bad":
            avvisi.append(f"«{a['Azione'][:70]}» ({a['Responsabile'] or 'senza responsabile'}): in ritardo di {-g} giorni.")
        if a["Stato"] == "Aperta" and not a["Responsabile"]:
            avvisi.append(f"«{a['Azione'][:70]}»: nessun responsabile.")
    aperte = [r for r in righe if r["Stato"] == "Aperta"]
    per_resp = []
    for n in sorted({r["Responsabile"] or "(nessuno)" for r in aperte}):
        m = [r for r in aperte if (r["Responsabile"] or "(nessuno)") == n]
        per_resp.append({"Responsabile": n, "Azioni aperte": len(m), "In ritardo": sum(1 for r in m if r["Stato semaforo"] == "bad")})
    kpi = {"n_verbali": len(verbali), "n_azioni": len(righe), "aperte": len(aperte), "fatte": len(righe) - len(aperte),
           "in_ritardo": sum(1 for r in aperte if r["Stato semaforo"] == "bad"), "in_arrivo": sum(1 for r in aperte if r["Stato semaforo"] == "warn"),
           "senza_resp": sum(1 for r in aperte if not r["Responsabile"])}
    kpi["n_bad"], kpi["n_warn"] = kpi["in_ritardo"], kpi["in_arrivo"] + kpi["senza_resp"]
    return {"params": {"oggi": oggi, "preavviso_gg": prev}, "verbali": verbali, "azioni": righe, "responsabili": per_resp, "kpi": kpi, "avvisi": avvisi}
