"""scad.py - Logica comune per le scadenze (documenti, formazioni, revisioni): scaduto / in scadenza / in regola."""
import datetime as dt

from sc import data_da

PREAVVISO_DEFAULT = 30
ETICHETTE = {"ok": "In regola", "warn": "In scadenza", "bad": "Scaduto", "nd": "Senza data"}


def stato_scadenza(scadenza, oggi, preavviso=PREAVVISO_DEFAULT):
    """Restituisce (stato, giorni): stato in ok/warn/bad/nd; giorni = giorni mancanti (negativi se scaduta)."""
    d = data_da(scadenza)
    if d is None:
        return "nd", None
    g = (d - oggi).days
    return ("bad" if g < 0 else "warn" if g <= preavviso else "ok"), g


def peggiore(stati):
    ordine = {"bad": 3, "warn": 2, "nd": 1, "ok": 0}
    return max(stati, key=lambda s: ordine[s]) if stati else "ok"


def conta(stati):
    return {"bad": stati.count("bad"), "warn": stati.count("warn"), "ok": stati.count("ok"), "nd": stati.count("nd")}


def oggi_da(p):
    return data_da((p or {}).get("oggi"), dt.date.today())
