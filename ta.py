"""
ta.py - Compiti e attivita': la bacheca dei compiti. Ogni compito ha responsabile, scadenza, priorita', stato e, se serve,
la commessa (codice madre). Senza Streamlit, quindi testabile. Le scadenze finiscono nel Calendario.
"""
import datetime as dt
import re

from sc import data_da

TA_DEFAULT = {"oggi": None, "preavviso_gg": 3}
STATI = ["Da fare", "In corso", "In attesa", "Fatto"]
PRIORITA = ["Alta", "Media", "Bassa"]
COLONNE = ["Compito", "Commessa", "Responsabile", "Priorita", "Stato", "Scadenza", "Note", "Creato", "Chiuso"]
ETICHETTE = {"Compito": "Compito", "Commessa": "Commessa (codice madre)", "Responsabile": "Responsabile", "Priorita": "Priorità", "Stato": "Stato",
             "Scadenza": "Scadenza", "Note": "Note", "Creato": "Creato il", "Chiuso": "Chiuso il"}
# modi (inglese o italiano) di scrivere gli stati e le priorita'
_STATO = {"done": "Fatto", "completato": "Fatto", "completata": "Fatto", "fatto": "Fatto", "chiuso": "Fatto", "finito": "Fatto", "ok": "Fatto",
          "working on it": "In corso", "in corso": "In corso", "in lavorazione": "In corso", "in progress": "In corso",
          "stuck": "In attesa", "bloccato": "In attesa", "in attesa": "In attesa", "on hold": "In attesa", "sospeso": "In attesa",
          "to do": "Da fare", "da fare": "Da fare", "not started": "Da fare", "non iniziato": "Da fare"}
_PRIORITA = {"high": "Alta", "alta": "Alta", "critical": "Alta", "critica": "Alta", "urgente": "Alta", "medium": "Media", "media": "Media",
             "low": "Bassa", "bassa": "Bassa"}


def _s(v):
    return "" if v is None or str(v).strip().lower() in ("nan", "none", "nat") else str(v).strip()


def stato_canonico(v):
    t = _s(v).lower()
    return _STATO.get(t) or next((s for s in STATI if s.lower() == t), "")


def priorita_canonica(v):
    t = _s(v).lower()
    return _PRIORITA.get(t) or next((p for p in PRIORITA if p.lower() == t), "")


def _data_iso(v):
    d = data_da(v)
    if d is None and _s(v):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", _s(v))          # intervalli di date: «2026-11-02 - 2026-11-10» -> la fine
        for g in reversed(re.findall(r"\d{4}-\d{2}-\d{2}", _s(v))):
            d = data_da(g)
            break
    return d.isoformat() if d else ""


def riga(r, oggi=None):
    """Riga pulita oppure None se vuota. Un compito senza stato e' «Da fare»; chiuso il giorno in cui passa a «Fatto»."""
    oggi = (oggi or dt.date.today()).isoformat()
    z = {c: _s((r or {}).get(c)) for c in COLONNE}
    if not any(z.values()):
        return None
    z["Stato"] = stato_canonico(z["Stato"]) or "Da fare"
    z["Priorita"] = priorita_canonica(z["Priorita"]) or "Media"
    for c in ("Scadenza", "Creato", "Chiuso"):
        z[c] = _data_iso(z[c])
    z["Creato"] = z["Creato"] or oggi
    if z["Stato"] == "Fatto":
        z["Chiuso"] = z["Chiuso"] or oggi
    else:
        z["Chiuso"] = ""
    return z


def normalizza(righe, oggi=None):
    """(righe pulite, avvisi). Servono almeno il testo del compito."""
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        z = riga(r, oggi)
        if z is None:
            continue
        if not z["Compito"]:
            avvisi.append(f"Riga {i}: manca il testo del compito, riga ignorata.")
            continue
        out.append(z)
    return out, avvisi


def muovi(r, stato, oggi=None):
    """Copia del compito spostato in un altro stato."""
    z = dict(r)
    z["Stato"] = stato
    return riga(z, oggi) if stato != "Fatto" else riga({**z, "Chiuso": ""}, oggi)


def in_ritardo(r, oggi):
    d = data_da(r["Scadenza"])
    return r["Stato"] != "Fatto" and d is not None and d < oggi


def calcola(righe, oggi=None, params=None):
    oggi = data_da(oggi, dt.date.today())
    prev = int((params or {}).get("preavviso_gg", TA_DEFAULT["preavviso_gg"]))
    aperti = [r for r in righe if r["Stato"] != "Fatto"]
    ritardo = [r for r in aperti if in_ritardo(r, oggi)]
    in_arrivo = [r for r in aperti if r["Scadenza"] and 0 <= (data_da(r["Scadenza"]) - oggi).days <= prev]
    senza_resp = [r for r in aperti if not r["Responsabile"]]
    per_resp = {}
    for r in aperti:
        x = per_resp.setdefault(r["Responsabile"] or "(senza responsabile)", {"Responsabile": r["Responsabile"] or "(senza responsabile)", "Aperti": 0, "In ritardo": 0})
        x["Aperti"] += 1
        x["In ritardo"] += in_ritardo(r, oggi)
    chiusi30 = [r for r in righe if r["Stato"] == "Fatto" and r["Chiuso"] and (oggi - data_da(r["Chiuso"])).days <= 30]
    return {"kpi": {"totale": len(righe), "aperti": len(aperti), "ritardo": len(ritardo), "in_arrivo": len(in_arrivo), "senza_resp": len(senza_resp), "chiusi_30": len(chiusi30),
                    "in_corso": sum(r["Stato"] == "In corso" for r in righe), "in_attesa": sum(r["Stato"] == "In attesa" for r in righe)},
            "per_responsabile": sorted(per_resp.values(), key=lambda x: (-x["In ritardo"], -x["Aperti"])), "ritardo": ritardo}


def filtra(righe, responsabile="", commessa="", testo="", solo_aperti=False):
    t = testo.strip().lower()
    out = []
    for r in righe:
        if responsabile and responsabile.lower() not in r["Responsabile"].lower():
            continue
        if commessa and r["Commessa"] != commessa:
            continue
        if t and t not in " ".join(r.values()).lower():
            continue
        if solo_aperti and r["Stato"] == "Fatto":
            continue
        out.append(r)
    return out


def ordina(righe):
    """Prima le scadenze piu' vicine, poi la priorita'."""
    return sorted(righe, key=lambda r: (r["Scadenza"] or "9999-12-31", PRIORITA.index(r["Priorita"])))


def excel_bytes(righe, kpi=None):
    import io
    import pandas as pd
    b = io.BytesIO()
    with pd.ExcelWriter(b, engine="openpyxl") as w:
        pd.DataFrame([{ETICHETTE[c]: r[c] for c in COLONNE} for r in righe], columns=[ETICHETTE[c] for c in COLONNE]).to_excel(w, sheet_name="Compiti", index=False)
    return b.getvalue()


def miei(username, path=None):
    """Compiti aperti della bacheca assegnati a questa persona, nella stessa forma dei compiti della chat ({titolo, scadenza, ...}): servono a «La mia giornata»."""
    import storage
    nome = re.sub(r"\s+", " ", str(username or "").strip()).lower()
    if not nome:
        return []
    try:
        elenco = storage.elenca_pratiche(path, modulo="ta")
        p = storage.carica_pratica(elenco[0]["nome"], path, "ta") if elenco else None
    except Exception:
        return []
    righe, _ = normalizza((p or {}).get("compiti"))
    out = []
    for r in righe:
        if r["Stato"] == "Fatto" or nome not in re.sub(r"\s+", " ", r["Responsabile"]).lower():
            continue
        out.append({"id": None, "titolo": r["Compito"], "scadenza": r["Scadenza"], "assegnato": username, "fonte": "bacheca"})
    return sorted(out, key=lambda t: (t["scadenza"] or "9999-12-31", t["titolo"]))
