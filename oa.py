"""
oa.py - Ordini di acquisto e approvazioni: chi chiede, chi approva, entro quale importo, con traccia di ogni decisione.
Deterministico e senza Streamlit.

Regole:
  - Ogni ordine ha un livello di approvazione che dipende dall'importo (tabella delle soglie).
  - Chi ha chiesto l'ordine non puo' approvarlo (separazione dei ruoli).
  - Un'approvazione vale per l'importo approvato: se l'importo cambia dopo, l'ordine torna «Da riapprovare».
  - Un fornitore con documenti scaduti (DURC, assicurazioni...) blocca l'approvazione.
"""
import re

from core import fmt_num, to_float
from sc import data_da

COLONNE_ORDINI = ["Numero", "Data", "Fornitore", "Cantiere", "Descrizione", "Importo", "Richiedente", "Note", "Voce", "Quantita"]
ETICHETTE_ORDINI = {"Numero": "N. ordine", "Data": "Data", "Fornitore": "Fornitore", "Cantiere": "Cantiere", "Descrizione": "Cosa si ordina", "Importo": "Importo (€, IVA esclusa)", "Richiedente": "Chi lo chiede", "Note": "Note", "Voce": "Voce del prezziario (codice)", "Quantita": "Quantità"}
COLONNE_SOGLIE = ["Fino_a", "Livello", "Approvatori"]
ETICHETTE_SOGLIE = {"Fino_a": "Fino a (€) — vuoto = oltre l'ultima", "Livello": "Chi approva (ruolo)", "Approvatori": "Nomi utente autorizzati (separati da virgola)"}
SOGLIE_BASE = [{"Fino_a": 2000.0, "Livello": "Capocantiere", "Approvatori": ""}, {"Fino_a": 20000.0, "Livello": "Direttore tecnico", "Approvatori": ""}, {"Fino_a": None, "Livello": "Presidente", "Approvatori": ""}]
STATI = ["Da approvare", "Approvato", "Respinto", "Da riapprovare"]


def _t(v):
    return "" if v is None or v != v else str(v).strip()


def prossimo_numero(ordini, anno):
    mx = 0
    for o in ordini or []:
        m = re.match(rf"^ODA-{anno}-(\d+)$", _t(o.get("Numero")).upper())
        if m:
            mx = max(mx, int(m.group(1)))
    return f"ODA-{anno}-{mx + 1:03d}"


def normalizza_ordini(righe, anno=None):
    import datetime as dt
    anno = anno or dt.date.today().year
    base = [dict(r) for r in (righe or [])]
    out, avvisi, usati = [], [], set()
    for i, r in enumerate(base, start=1):
        if not any(_t(r.get(c)) for c in COLONNE_ORDINI):
            continue
        f, imp = _t(r.get("Fornitore")), to_float(r.get("Importo"), 0.0)
        if not f or imp <= 0:
            avvisi.append(f"Ordine, riga {i}: servono fornitore e importo, riga ignorata.")
            continue
        num = _t(r.get("Numero")).upper() or prossimo_numero([*out, *[{"Numero": _t(x.get("Numero"))} for x in base]], anno)
        if num in usati:
            avvisi.append(f"Il numero {num} è usato da più di un ordine: deve essere unico.")
        usati.add(num)
        d = data_da(r.get("Data"))
        out.append({"Numero": num, "Data": d.isoformat() if d else "", "Fornitore": f, "Cantiere": _t(r.get("Cantiere")), "Descrizione": _t(r.get("Descrizione")), "Importo": imp,
                    "Richiedente": _t(r.get("Richiedente")), "Note": _t(r.get("Note")),
                    "Voce": _t(r.get("Voce")), "Quantita": to_float(r.get("Quantita"), 0.0)})
    return out, avvisi


def normalizza_soglie(righe):
    """Soglie ordinate per importo; l'ultima senza limite. Se la tabella e' vuota usa quelle base."""
    s = []
    for r in righe or []:
        liv = _t(r.get("Livello"))
        if not liv:
            continue
        lim = r.get("Fino_a")
        lim = None if lim is None or lim != lim or _t(lim) == "" else to_float(lim, 0.0)
        s.append({"Fino_a": lim, "Livello": liv, "Approvatori": [x.strip().lower() for x in _t(r.get("Approvatori")).split(",") if x.strip()]})
    if not s:
        s = [{**x, "Approvatori": []} for x in SOGLIE_BASE]
    s.sort(key=lambda x: (x["Fino_a"] is None, x["Fino_a"] or 0))
    if s[-1]["Fino_a"] is not None:
        s.append({"Fino_a": None, "Livello": s[-1]["Livello"], "Approvatori": list(s[-1]["Approvatori"])})
    return s


def livello_richiesto(importo, soglie):
    for s in soglie:
        if s["Fino_a"] is None or importo <= s["Fino_a"]:
            return s
    return soglie[-1]


def stato_ordine(o, approvazioni):
    """(stato, ultima decisione o None). Le decisioni sono in ordine cronologico; conta l'ultima dell'ordine."""
    dec = [a for a in approvazioni if a["Numero"] == o["Numero"]]
    if not dec:
        return "Da approvare", None
    u = dec[-1]
    if abs(to_float(u.get("Importo"), 0.0) - o["Importo"]) > 0.005:
        return "Da riapprovare", u
    return ("Approvato" if u["Esito"] == "Approvato" else "Respinto"), u


def fornitori_irregolari(docs_fornitori, oggi):
    """Nomi (minuscolo) dei fornitori con almeno un documento scaduto."""
    return {d["Fornitore"].lower() for d in (docs_fornitori or []) if d.get("Scadenza") and data_da(d["Scadenza"]) < oggi}


def puo_approvare(utente, ruolo, o, soglie, irregolari=()):
    """(consentito, motivo). `utente`: nome utente, `ruolo`: admin/utente/lettore."""
    if ruolo == "lettore":
        return False, "Il tuo ruolo è «lettore»: non puoi approvare."
    if _t(o["Richiedente"]).lower() == utente.lower() and utente:
        return False, "Hai chiesto tu l'ordine: deve approvarlo un'altra persona."
    s = livello_richiesto(o["Importo"], soglie)
    if s["Approvatori"] and utente.lower() not in s["Approvatori"] and ruolo != "admin":
        return False, f"Per questo importo approva: {s['Livello']} ({', '.join(s['Approvatori'])})."
    if o["Fornitore"].lower() in irregolari:
        return False, "Il fornitore ha documenti scaduti (DURC, assicurazione…): rinnovali prima di approvare."
    return True, ""


def registra(approvazioni, o, esito, utente, quando, motivo=""):
    return [*approvazioni, {"Numero": o["Numero"], "Esito": esito, "Da": utente, "Quando": quando, "Importo": o["Importo"], "Motivo": _t(motivo)}]


def calcola_oa(ordini, soglie, approvazioni, docs_fornitori=None, oggi=None, giorni_attesa=7, prezzi=None, soglia_prezzo=10.0):
    import datetime as dt
    oggi = oggi or dt.date.today()
    irr = fornitori_irregolari(docs_fornitori, oggi)
    righe, avvisi = [], []
    for o in ordini:
        stato, dec = stato_ordine(o, approvazioni)
        liv = livello_richiesto(o["Importo"], soglie)
        d = data_da(o["Data"])
        attesa = (oggi - d).days if d and stato in ("Da approvare", "Da riapprovare") else 0
        anom = []
        if o["Fornitore"].lower() in irr:
            anom.append("fornitore con documenti scaduti")
        if stato == "Approvato" and dec and liv["Approvatori"] and dec["Da"].lower() not in liv["Approvatori"]:
            anom.append(f"approvato da {dec['Da']}, non autorizzato per {liv['Livello']}")
        if stato == "Approvato" and dec and dec["Da"].lower() == o["Richiedente"].lower() and o["Richiedente"]:
            anom.append("approvato da chi l'ha chiesto")
        if not o["Cantiere"]:
            anom.append("senza cantiere")
        if prezzi:
            try:
                import pz
                cp = pz.controllo_prezzo(o, prezzi, soglia_prezzo)
            except Exception:
                cp = None
            if cp:
                anom.append(cp)
        righe.append({**o, "Stato": stato, "Livello": liv["Livello"], "Decisione": dec, "Attesa gg": attesa, "Anomalie": anom})
        if anom and stato != "Respinto":
            avvisi.append(f"{o['Numero']} · {o['Fornitore']}: " + "; ".join(anom) + ".")
        if attesa > giorni_attesa:
            avvisi.append(f"{o['Numero']} · {o['Fornitore']}: in attesa di approvazione da {attesa} giorni.")
    da_app = [r for r in righe if r["Stato"] in ("Da approvare", "Da riapprovare")]
    kpi = {"ordini": len(righe), "da_approvare": len(da_app), "importo_da_approvare": sum(r["Importo"] for r in da_app), "approvati": sum(1 for r in righe if r["Stato"] == "Approvato"),
           "importo_approvato": sum(r["Importo"] for r in righe if r["Stato"] == "Approvato"), "respinti": sum(1 for r in righe if r["Stato"] == "Respinto"),
           "anomalie": sum(1 for r in righe if r["Anomalie"] and r["Stato"] != "Respinto"), "in_ritardo": sum(1 for r in da_app if r["Attesa gg"] > giorni_attesa),
           "per_fornitore": {}}
    for r in righe:
        if r["Stato"] != "Respinto":
            kpi["per_fornitore"][r["Fornitore"]] = kpi["per_fornitore"].get(r["Fornitore"], 0) + r["Importo"]
    return {"ordini": righe, "kpi": kpi, "avvisi": avvisi, "irregolari": irr}
