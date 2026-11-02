"""
spazio.py - Quanto spazio resta sul server e sul NAS (disco, database, copie di sicurezza). Senza Streamlit, quindi testabile.
Percorsi (variabili d'ambiente, tutte facoltative):
  FCR_DISCO_SERVER   disco da misurare per il server (predefinito "/")
  FCR_NAS_PATH       cartella dove e' montato il NAS (predefinito "/mnt/nas")
  BACKUP_DIR         cartella delle copie di sicurezza (se vuota si prova ~/backup)
"""
import os
import shutil

import storage

SOGLIA_ATTENZIONE = 75      # % di disco usato oltre la quale la barra diventa gialla
SOGLIA_CRITICA = 90         # % oltre la quale diventa rossa


def percorso_server():
    return os.environ.get("FCR_DISCO_SERVER", "").strip() or "/"


def percorso_nas():
    return os.environ.get("FCR_NAS_PATH", "").strip() or "/mnt/nas"


def cartella_backup():
    for p in (os.environ.get("BACKUP_DIR", "").strip(), os.path.expanduser("~/backup"), "backups"):
        if p and os.path.isdir(p):
            return p
    return ""


def leggibile(n):
    """Dimensione in unita' comode, con la virgola decimale (es. 12,3 GB)."""
    n = float(n or 0)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            s = f"{n:.0f}" if u == "B" else f"{n:.1f}".replace(".", ",")
            return f"{s} {u}"
        n /= 1024


def stato(perc):
    """ok / attenzione / critico in base alla percentuale di disco usato."""
    if perc is None:
        return "nd"
    if perc >= SOGLIA_CRITICA:
        return "critico"
    if perc >= SOGLIA_ATTENZIONE:
        return "attenzione"
    return "ok"


def uso(path, richiedi_montaggio=False):
    """
    Spazio di un disco o di una cartella montata. Restituisce un dizionario:
    percorso, disponibile (bool), motivo (se non disponibile), totale, usato, libero, perc, stato.
    Con richiedi_montaggio=True la cartella deve essere davvero un punto di mount (altrimenti si misurerebbe il disco del server
    al posto del NAS spento o scollegato).
    """
    out = {"percorso": path, "disponibile": False, "motivo": "", "totale": 0, "usato": 0, "libero": 0, "perc": None, "stato": "nd"}
    if not path or not os.path.isdir(path):
        out["motivo"] = "cartella non trovata"
        return out
    if richiedi_montaggio and not os.path.ismount(path):
        out["motivo"] = "non collegato (la cartella esiste ma il NAS non risulta montato)"
        return out
    try:
        d = shutil.disk_usage(path)
    except OSError as e:
        out["motivo"] = f"non leggibile ({e})"
        return out
    perc = round(d.used * 100.0 / d.total, 1) if d.total else None
    out.update(disponibile=True, totale=d.total, usato=d.used, libero=d.free, perc=perc, stato=stato(perc))
    return out


def server():
    return uso(percorso_server())


def nas():
    p = percorso_nas()
    r = uso(p, richiedi_montaggio=True)
    r["configurato"] = bool(os.environ.get("FCR_NAS_PATH", "").strip()) or os.path.isdir(p)
    return r


def dimensione_cartella(path):
    """Somma dei file di una cartella (0 se non esiste)."""
    tot, n = 0, 0
    if not path or not os.path.isdir(path):
        return 0, 0
    for r, _d, files in os.walk(path):
        for f in files:
            try:
                tot += os.path.getsize(os.path.join(r, f))
                n += 1
            except OSError:
                pass
    return tot, n


def dimensione_db(path=None):
    """Dimensione del database in byte, o None se non si riesce a leggerla."""
    try:
        if not path and storage._url_db():
            with storage._db() as con:
                r = con.execute("SELECT pg_database_size(current_database())").fetchone()
            return int(r[0])
        p = path or storage.DB_PATH
        return os.path.getsize(p) if os.path.exists(p) else 0
    except Exception:
        return None


def riepilogo(path_db=None):
    """Tutto insieme per la scheda «Spazio»."""
    cart = cartella_backup()
    bk_byte, bk_n = dimensione_cartella(cart)
    return {"server": server(), "nas": nas(), "db": dimensione_db(path_db),
            "backup": {"cartella": cart, "byte": bk_byte, "file": bk_n}}


def avvisi(r=None):
    """Frasi di avviso (vuote se tutto a posto) per disco del server o del NAS quasi pieni."""
    r = r or {"server": server(), "nas": nas()}
    out = []
    for chiave, nome in (("server", "il server"), ("nas", "il NAS")):
        x = r[chiave]
        if x.get("disponibile") and x["stato"] in ("attenzione", "critico"):
            out.append(f"Lo spazio di {nome} è usato al {x['perc']:.0f}%: restano {leggibile(x['libero'])}.")
    return out
