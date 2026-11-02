"""
ta.py - Compiti e attivita': la bacheca che sostituisce il monday dei compiti. Ogni compito ha responsabile, scadenza, priorita', stato e, se serve,
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
SINONIMI = {"Compito": ("Item", "Name", "Nome", "Attività", "Attivita", "Task", "Titolo", "Elemento"),
            "Commessa": ("Codice", "Progetto", "Cantiere", "Board", "Gruppo", "Group"),
            "Responsabile": ("Persona", "Person", "Owner", "Assegnato a", "Assegnatario", "People", "Persone", "Incaricato"),
            "Priorita": ("Priority", "Priorità", "Importanza"),
            "Stato": ("Status", "Stato avanzamento"),
            "Scadenza": ("Due date", "Data scadenza", "Date", "Data", "Timeline", "Entro il", "Deadline"),
            "Note": ("Notes", "Descrizione", "Commento", "Commenti", "Text", "Testo", "Update")}
# come monday (inglese o italiano) chiama gli stati e le priorita'
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
        m = re.search(r"(\d{4}-\d{2}-\d{2})", _s(v))          # intervalli di monday: «2026-11-02 - 2026-11-10» -> la fine
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


def da_excel(sorgente):
    """Legge un export di monday (o un Excel con colonne simili). Se ci sono piu' fogli li legge tutti. Restituisce (righe grezze, avvisi)."""
    import pandas as pd
    xls = pd.ExcelFile(sorgente)
    righe, avvisi = [], []
    norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())
    for nome in xls.sheet_names:
        raw = pd.read_excel(xls, nome, header=None, dtype=object)
        h = None
        for i in range(min(len(raw), 12)):                       # monday mette il nome della bacheca e del gruppo sopra le colonne
            celle = [norm(c) for c in raw.iloc[i] if _s(c)]
            if any(c in celle for c in ("compito", "item", "name", "nome", "task", "attivita", "titolo", "elemento")):
                h = i
                break
        if h is None:
            avvisi.append(f"Foglio «{nome}»: non trovo l'intestazione, saltato.")
            continue
        cols = list(raw.iloc[h])
        mappa = {}
        for campo in COLONNE:
            cand = [norm(campo)] + [norm(x) for x in SINONIMI.get(campo, ())]
            for j, c in enumerate(cols):
                if norm(c) in cand and j not in mappa.values():
                    mappa[campo] = j
                    break
        if "Compito" not in mappa:
            avvisi.append(f"Foglio «{nome}»: manca la colonna del compito, saltato.")
            continue
        for _, rr in raw.iloc[h + 1:].iterrows():
            d = {c: rr.iloc[j] for c, j in mappa.items()}
            if _s(d.get("Compito")):
                righe.append(d)
    return righe, avvisi


def importa_excel(sorgente, oggi=None):
    grezze, avv = da_excel(sorgente)
    righe, a2 = normalizza(grezze, oggi)
    return righe, avv + a2


def unisci(attuali, nuove):
    """Aggiunge i compiti nuovi; se esiste gia' lo stesso compito con la stessa commessa lo aggiorna. Restituisce (elenco, aggiunti, aggiornati)."""
    chiave = lambda r: (r["Compito"].lower(), r["Commessa"].lower())
    out = [dict(r) for r in attuali]
    idx = {chiave(r): i for i, r in enumerate(out)}
    agg = upd = 0
    for r in nuove:
        k = chiave(r)
        if k in idx:
            out[idx[k]] = r
            upd += 1
        else:
            idx[k] = len(out)
            out.append(r)
            agg += 1
    return out, agg, upd


def excel_bytes(righe, kpi=None):
    import io
    import pandas as pd
    b = io.BytesIO()
    with pd.ExcelWriter(b, engine="openpyxl") as w:
        pd.DataFrame([{ETICHETTE[c]: r[c] for c in COLONNE} for r in righe], columns=[ETICHETTE[c] for c in COLONNE]).to_excel(w, sheet_name="Compiti", index=False)
    return b.getvalue()
