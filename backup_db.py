"""
backup_db.py - Copia di sicurezza COMPLETA e cifrata del database (tutte le tabelle: pratiche, utenti con le password cifrate, chat, registro).

Il file e' compresso e cifrato con la chiave BACKUP_KEY (una frase lunga): senza la chiave non si apre. CONSERVARE LA CHIAVE ALTROVE:
se si perde, il backup e' inutilizzabile.
    python backup_db.py                         # crea il backup in BACKUP_DIR (predefinito: backups/), tiene gli ultimi 30,
                                                #   e, se BACKUP_EMAIL e' impostata, lo manda per email come allegato
    python backup_db.py --verifica FILE         # prova il ripristino in un database temporaneo e confronta i conteggi (non tocca i dati veri)
    python backup_db.py --ripristina FILE --su PERCORSO.db     # ripristina in un file SQLite
    python backup_db.py --ripristina FILE --su-database-url    # ripristina sul database di DATABASE_URL (SOSTITUISCE i dati attuali)
Variabili: DATABASE_URL, BACKUP_KEY, BACKUP_DIR, BACKUP_TENERE, BACKUP_EMAIL, SMTP_*.
"""
import base64
import datetime as dt
import glob
import gzip
import hashlib
import json
import os
import sys
import tempfile

import chat
import storage

VERSIONE_FORMATO = 1


def _fernet(chiave=None):
    k = (chiave or os.environ.get("BACKUP_KEY") or "").strip()
    if len(k) < 12:
        raise ValueError("Imposta BACKUP_KEY (almeno 12 caratteri, meglio una frase lunga): senza non si crea ne' si apre il backup.")
    from cryptography.fernet import Fernet
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("backup|" + k).encode("utf-8")).digest()))


def _tabelle(con):
    try:
        r = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
    except Exception:
        r = con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name").fetchall()
    return [x[0] for x in r]


def esporta(path=None):
    """Tutte le tabelle: {nome: {"colonne": [...], "righe": [[...]]}}."""
    with chat._db(path) as con:                 # crea anche le tabelle della chat, se mancano
        out = {}
        for t in _tabelle(con):
            cur = con.execute(f"SELECT * FROM {t}")
            col = [d[0] for d in cur.description]
            out[t] = {"colonne": col, "righe": [list(r) for r in cur.fetchall()]}
    return {"formato": VERSIONE_FORMATO, "generato": storage._now(), "tabelle": out}


def cifra(dati, chiave=None):
    return _fernet(chiave).encrypt(gzip.compress(json.dumps(dati, ensure_ascii=False).encode("utf-8")))


def apri(blob, chiave=None):
    try:
        return json.loads(gzip.decompress(_fernet(chiave).decrypt(blob)).decode("utf-8"))
    except ValueError:
        raise
    except Exception:
        raise ValueError("Backup non leggibile: chiave sbagliata o file danneggiato.")


def conteggi(dati):
    return {t: len(v["righe"]) for t, v in dati["tabelle"].items()}


def ripristina(dati, path=None):
    """SOSTITUISCE il contenuto delle tabelle del database con quello del backup."""
    with chat._db(path) as con:
        pg = isinstance(con, storage._ConPG)
        esistenti = set(_tabelle(con))
        for t, v in dati["tabelle"].items():
            if t not in esistenti:
                continue
            con.execute(f"DELETE FROM {t}")
            col = v["colonne"]
            sql = f"INSERT INTO {t} ({', '.join(col)}) VALUES ({', '.join('?' * len(col))})"
            for r in v["righe"]:
                con.execute(sql, r)
            if pg and "id" in col:
                con.execute(f"SELECT setval(pg_get_serial_sequence('{t}', 'id'), COALESCE((SELECT MAX(id) FROM {t}), 1), (SELECT COUNT(*) FROM {t}) > 0)")
    storage.svuota_cache()


def verifica(blob, chiave=None):
    """Apre il backup, lo ripristina in un database temporaneo e confronta i conteggi. Restituisce i conteggi se tutto torna."""
    dati = apri(blob, chiave)
    with tempfile.TemporaryDirectory() as d:
        tmp = os.path.join(d, "prova.db")
        ripristina(dati, tmp)
        riletto = esporta(tmp)
    a, b = conteggi(dati), conteggi(riletto)
    mancanti = {t: (n, b.get(t)) for t, n in a.items() if b.get(t) != n}
    if mancanti:
        raise ValueError(f"Il ripristino di prova non torna: {mancanti}")
    return a


def crea(path=None, cartella=None, tenere=None, chiave=None):
    """Scrive il backup cifrato nella cartella e toglie i piu' vecchi. Restituisce (percorso, conteggi, contenuto)."""
    cartella = cartella or os.environ.get("BACKUP_DIR") or "backups"
    tenere = int(tenere or os.environ.get("BACKUP_TENERE") or 30)
    dati = esporta(path)
    blob = cifra(dati, chiave)
    verifica(blob, chiave)                          # un backup che non si riapre non serve: meglio saperlo subito
    os.makedirs(cartella, exist_ok=True)
    nome = os.path.join(cartella, "fcr_backup_" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S_%f") + ".bak")
    with open(nome, "wb") as f:
        f.write(blob)
    for vecchio in sorted(glob.glob(os.path.join(cartella, "fcr_backup_*.bak")))[:-tenere]:
        os.remove(vecchio)
    return nome, conteggi(dati), blob


def invia_email(nome, blob, cont, destinatari):
    import avvisi_dd
    tot = sum(cont.values())
    avvisi_dd.MAIL(destinatari, "FCR Suite - backup cifrato " + dt.date.today().strftime("%d/%m/%Y"),
                   f"In allegato la copia cifrata del database ({tot} righe in {len(cont)} tabelle).\n"
                   "Si apre solo con la chiave BACKUP_KEY: conservala in un posto sicuro, diverso da questa casella.\n"
                   "Per provare il ripristino: python backup_db.py --verifica FILE",
                   allegati=[(os.path.basename(nome), blob, "application/octet-stream")])


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    try:
        if "--verifica" in a:
            c = verifica(open(a[a.index("--verifica") + 1], "rb").read())
            print("Backup valido e ripristinabile:", ", ".join(f"{t}={n}" for t, n in c.items()))
            return 0
        if "--ripristina" in a:
            dati = apri(open(a[a.index("--ripristina") + 1], "rb").read())
            if "--su" in a:
                ripristina(dati, a[a.index("--su") + 1])
            elif "--su-database-url" in a:
                ripristina(dati, None)
            else:
                print("Indica dove ripristinare: --su PERCORSO.db oppure --su-database-url")
                return 2
            print("Ripristino completato:", ", ".join(f"{t}={n}" for t, n in conteggi(dati).items()))
            return 0
        nome, cont, blob = crea()
        print(f"Backup creato: {nome} ({sum(cont.values())} righe, {len(cont)} tabelle), verificato.")
        dest = [x.strip() for x in (os.environ.get("BACKUP_EMAIL") or "").split(",") if x.strip()]
        if dest:
            invia_email(nome, blob, cont, dest)
            print("Inviato per email a", ", ".join(dest))
        return 0
    except Exception as e:
        print("ERRORE:", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
