"""
salute.py - Stato del server (memoria, processore, disco, tempo acceso) e prova di velocita'.
Legge solo i dati di Linux (/proc): nessuna libreria in piu'. Se la suite gira su un sistema senza /proc (per esempio Windows) le cifre
non ci sono e la scheda lo dice, senza dare errore. La prova di velocita' misura il computer su cui gira la suite
e conserva gli ultimi risultati, cosi' si vede se dopo una modifica (per esempio piu' RAM) e' davvero piu' veloce.
"""
import hashlib
import os
import shutil
import tempfile
import time
import datetime as dt

import storage

NOME_STORICO = "salute_storico"
MAX_STORICO = 20


def _leggi(percorso):
    try:
        with open(percorso, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def memoria():
    """Memoria del computer in MB: totale, usata, disponibile, percentuale, swap. None se non leggibile."""
    kb = {}
    for riga in _leggi("/proc/meminfo").splitlines():
        p = riga.replace(":", "").split()
        if len(p) >= 2 and p[1].isdigit():
            kb[p[0]] = int(p[1])
    if "MemTotal" not in kb:
        return None
    tot = kb["MemTotal"] / 1024
    disp = kb.get("MemAvailable", kb.get("MemFree", 0)) / 1024
    usata = max(0.0, tot - disp)
    st_ = kb.get("SwapTotal", 0) / 1024
    su = max(0.0, st_ - kb.get("SwapFree", 0) / 1024)
    return {"totale": tot, "usata": usata, "disponibile": disp, "perc": 100 * usata / tot if tot else 0.0, "swap_totale": st_, "swap_usata": su}


def memoria_suite():
    """MB occupati dal programma della suite (questo processo)."""
    for riga in _leggi("/proc/self/status").splitlines():
        if riga.startswith("VmRSS:"):
            try:
                return int(riga.split()[1]) / 1024
            except (ValueError, IndexError):
                return None
    return None


def carico():
    """(carico medio 1 minuto, numero di processori, tempo acceso in secondi)."""
    try:
        c1 = float(_leggi("/proc/loadavg").split()[0])
    except (ValueError, IndexError):
        c1 = None
    try:
        acceso = float(_leggi("/proc/uptime").split()[0])
    except (ValueError, IndexError):
        acceso = None
    return c1, os.cpu_count() or 1, acceso


def durata_it(sec):
    if sec is None:
        return "-"
    s = int(sec)
    g, r = divmod(s, 86400)
    h, r = divmod(r, 3600)
    m = r // 60
    if g:
        return f"{g} g {h} h"
    return f"{h} h {m} min" if h else f"{m} min"


def giudizio_memoria(perc):
    """('ok'|'attenzione'|'critico', testo in parole semplici)."""
    if perc < 70:
        return "ok", "La memoria è sufficiente: c'è ancora molto spazio libero."
    if perc < 85:
        return "attenzione", "La memoria si sta riempiendo: tienila d'occhio. Se succede spesso conviene aggiungere RAM."
    return "critico", "La memoria è quasi piena: la suite può rallentare. Riavvia il servizio o aggiungi RAM."


def _cpu():
    t = time.perf_counter()
    x = 0
    for i in range(6_000_000):
        x += i * i % 7
    a = time.perf_counter() - t
    blob = os.urandom(1024 * 1024) * 16
    t = time.perf_counter()
    hashlib.sha256(blob).hexdigest()
    b = time.perf_counter() - t
    return a + b


def _ram():
    t = time.perf_counter()
    buf = bytearray(128 * 1024 * 1024)
    for _ in range(3):
        copia = bytes(buf)
    dt_ = time.perf_counter() - t
    del buf, copia
    return 3 * 128 / dt_ if dt_ > 0 else 0.0


def _disco():
    blob = os.urandom(1024 * 1024) * 32
    with tempfile.NamedTemporaryFile(dir=tempfile.gettempdir(), delete=True) as f:
        t = time.perf_counter()
        f.write(blob)
        f.flush()
        os.fsync(f.fileno())
        w = time.perf_counter() - t
        f.seek(0)
        t = time.perf_counter()
        f.read()
        r = time.perf_counter() - t
    return (32 / w if w > 0 else 0.0), (32 / r if r > 0 else 0.0)


def _database(path=None):
    """Millisecondi medi per salvare e per leggere una pratica piccola (il database vero della suite)."""
    nome = "__prova_velocita__"
    t = time.perf_counter()
    for i in range(10):
        storage.salva_pratica(nome, {"i": i, "x": "a" * 500}, path, autore="prova", modulo="cfg")
    s = (time.perf_counter() - t) / 10 * 1000
    t = time.perf_counter()
    for _ in range(20):
        storage.svuota_cache()
        storage.carica_pratica(nome, path, modulo="cfg")
    l = (time.perf_counter() - t) / 20 * 1000
    return s, l


def prova(path=None):
    """Esegue la prova (3-6 secondi) e ne conserva il risultato. Restituisce il risultato."""
    cpu = _cpu()
    ram = _ram()
    dw, dr = _disco()
    try:
        dbs, dbl = _database(path)
    except Exception:
        dbs = dbl = None
    m = memoria()
    r = {"quando": dt.datetime.now().isoformat(timespec="seconds"), "cpu_s": round(cpu, 2), "ram_mbs": round(ram), "disco_w": round(dw), "disco_r": round(dr),
         "db_scrivi_ms": None if dbs is None else round(dbs, 1), "db_leggi_ms": None if dbl is None else round(dbl, 1),
         "ram_tot_mb": round(m["totale"]) if m else None}
    try:
        st_ = storage.carica_pratica(NOME_STORICO, path, modulo="cfg") or {}
        lista = (st_.get("prove") or []) + [r]
        storage.salva_pratica(NOME_STORICO, {"prove": lista[-MAX_STORICO:]}, path, autore="sistema", modulo="cfg")
    except Exception:
        pass
    return r


def storico(path=None):
    try:
        return (storage.carica_pratica(NOME_STORICO, path, modulo="cfg") or {}).get("prove") or []
    except Exception:
        return []


def confronto(nuova, vecchia):
    """Per ogni misura, di quanto e' cambiata rispetto alla prova precedente (percentuale; positivo = meglio)."""
    if not vecchia:
        return {}
    out = {}
    for k, meglio_basso in (("cpu_s", True), ("ram_mbs", False), ("disco_w", False), ("disco_r", False), ("db_scrivi_ms", True), ("db_leggi_ms", True)):
        a, b = nuova.get(k), vecchia.get(k)
        if a and b:
            out[k] = round(((b - a) / b if meglio_basso else (a - b) / b) * 100)
    return out
