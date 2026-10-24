"""
demo.py - Dati dimostrativi: un salvataggio «DEMO - Esempio» per ogni strumento, letto da demo_dati.json (creato da genera_demo.py).
Non tocca mai i dati veri: i salvataggi dimostrativi hanno un nome riservato e sono esclusi da riepilogo email, freschezza, ricerca e permessi.
Le date vengono spostate a oggi ad ogni caricamento, cosi' scadenze e ritardi sono sempre credibili.
"""
import datetime as dt
import json
import os
import re

import storage

QUI = os.path.dirname(os.path.abspath(__file__))
NOME = storage.PREFISSO_DEMO + "Esempio"
_DATA = re.compile(r"^(\d{4})-(\d{2})-(\d{2})((?:[T ]\d{2}:\d{2}(?::\d{2})?)?)$")


def _leggi():
    try:
        with open(os.path.join(QUI, "demo_dati.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def disponibili():
    d = _leggi()
    return sorted(k for k in d if k != "_base")


def sposta_date(x, giorni):
    """Sposta di `giorni` ogni data ISO (AAAA-MM-GG) trovata nei dati, anche annidata."""
    if isinstance(x, dict):
        return {k: sposta_date(v, giorni) for k, v in x.items()}
    if isinstance(x, list):
        return [sposta_date(v, giorni) for v in x]
    if isinstance(x, str):
        m = _DATA.match(x)
        if m:
            try:
                nuova = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) + dt.timedelta(days=giorni)
                return nuova.isoformat() + m.group(4)
            except ValueError:
                return x
    return x


def carica(utente="", path=None, oggi=None):
    """Scrive (o riscrive) i salvataggi dimostrativi. Restituisce l'elenco dei moduli caricati."""
    dati = _leggi()
    oggi = oggi or dt.date.today()
    try:
        base = dt.date.fromisoformat(dati.get("_base"))
    except Exception:
        base = oggi
    giorni = (oggi - base).days
    fatti = []
    for m, payload in dati.items():
        if m == "_base":
            continue
        storage.salva_pratica(NOME, sposta_date(payload, giorni), path, autore=utente or "demo", modulo=m)
        fatti.append(m)
    return fatti


def presenti(path=None):
    """Moduli che hanno un salvataggio dimostrativo."""
    out = []
    for m in disponibili():
        try:
            if storage.elenca_pratiche(path, modulo=m, demo=True):
                out.append(m)
        except Exception:
            continue
    return out


def rimuovi(path=None):
    """Cancella solo i salvataggi dimostrativi. Restituisce quanti ne ha tolti."""
    n = 0
    for m in disponibili():
        try:
            for p in storage.elenca_pratiche(path, modulo=m, demo=True):
                storage.elimina_pratica(p["nome"], path, m)
                n += 1
        except Exception:
            continue
    return n
