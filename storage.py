"""
storage.py - Salvataggio pratiche, utenti e registro attivita' (PostgreSQL oppure SQLite).

Se e' impostato DATABASE_URL (variabile d'ambiente o Secret di Streamlit, es. la stringa di connessione di Neon)
si usa PostgreSQL e i dati sopravvivono ai riavvii. Altrimenti si usa un file SQLite (FCR_DB_PATH): su piattaforme
con filesystem effimero (Streamlit Community Cloud) quel file si perde ad ogni riavvio.
"""
import contextlib
import json
import os
import sqlite3
import time

DB_PATH = os.environ.get("FCR_DB_PATH", "fcr_pratiche.db")


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())


def _url_db():
    """Stringa di connessione PostgreSQL, se configurata."""
    u = os.environ.get("DATABASE_URL", "").strip()
    if not u:
        try:
            import streamlit as st
            u = str(st.secrets.get("DATABASE_URL", "") or "").strip()
        except Exception:
            u = ""
    return u


_PG_PRONTO = set()


class _ConPG:
    """Adatta una connessione psycopg all'uso di sqlite3 nel resto del modulo (segnaposto ?, execute diretto)."""

    def __init__(self, con):
        self.con = con

    def execute(self, sql, par=()):
        return self.con.execute(sql.replace("?", "%s"), tuple(par))

    def commit(self):
        self.con.commit()

    def close(self):
        self.con.close()


def _schema_pg(con):
    for ddl in (
        "CREATE TABLE IF NOT EXISTS pratiche (nome TEXT PRIMARY KEY, creato TEXT, aggiornato TEXT, payload TEXT, autore TEXT)",
        "CREATE TABLE IF NOT EXISTS report_log (id SERIAL PRIMARY KEY, pratica TEXT, report_id TEXT, creato TEXT, "
        "modello TEXT, hash_dati TEXT, dettagli TEXT)",
        "CREATE TABLE IF NOT EXISTS utenti (username TEXT PRIMARY KEY, hash TEXT NOT NULL, ruolo TEXT NOT NULL DEFAULT 'utente', "
        "attivo INTEGER NOT NULL DEFAULT 1, creato TEXT, ultimo_accesso TEXT, creato_da TEXT)",
        "CREATE TABLE IF NOT EXISTS audit_log (id SERIAL PRIMARY KEY, ts TEXT, utente TEXT, azione TEXT, dettaglio TEXT)",
    ):
        con.execute(ddl)


@contextlib.contextmanager
def _db(path=None):
    url = None if path else _url_db()
    if url:
        import psycopg
        con = _ConPG(psycopg.connect(url, connect_timeout=15))
        try:
            if url not in _PG_PRONTO:
                _schema_pg(con)
                con.commit()
                _PG_PRONTO.add(url)
            yield con
            con.commit()
        finally:
            con.close()
        return
    con = sqlite3.connect(path or DB_PATH)
    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS pratiche ("
            "nome TEXT PRIMARY KEY, creato TEXT, aggiornato TEXT, payload TEXT)"
        )
        con.execute(
            "CREATE TABLE IF NOT EXISTS report_log ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, pratica TEXT, report_id TEXT, creato TEXT, "
            "modello TEXT, hash_dati TEXT, dettagli TEXT)"
        )
        con.execute(
            "CREATE TABLE IF NOT EXISTS utenti ("
            "username TEXT PRIMARY KEY, hash TEXT NOT NULL, ruolo TEXT NOT NULL DEFAULT 'utente', "
            "attivo INTEGER NOT NULL DEFAULT 1, creato TEXT, ultimo_accesso TEXT, creato_da TEXT)"
        )
        con.execute(
            "CREATE TABLE IF NOT EXISTS audit_log ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, utente TEXT, azione TEXT, dettaglio TEXT)"
        )
        cols = [r[1] for r in con.execute("PRAGMA table_info(pratiche)")]
        if "autore" not in cols:
            con.execute("ALTER TABLE pratiche ADD COLUMN autore TEXT")
        yield con
        con.commit()
    finally:
        con.close()


def salva_pratica(nome, payload, path=None, autore=""):
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Il nome della pratica non puo' essere vuoto.")
    testo = json.dumps(payload, ensure_ascii=False, default=str)
    with _db(path) as con:
        esiste = con.execute("SELECT 1 FROM pratiche WHERE nome=?", (nome,)).fetchone()
        if esiste:
            con.execute("UPDATE pratiche SET aggiornato=?, payload=?, autore=? WHERE nome=?", (_now(), testo, autore, nome))
        else:
            con.execute(
                "INSERT INTO pratiche (nome, creato, aggiornato, payload, autore) VALUES (?,?,?,?,?)",
                (nome, _now(), _now(), testo, autore),
            )


def elenca_pratiche(path=None):
    with _db(path) as con:
        return [
            {"nome": r[0], "aggiornato": r[1], "autore": r[2] or ""}
            for r in con.execute("SELECT nome, aggiornato, autore FROM pratiche ORDER BY aggiornato DESC")
        ]


def carica_pratica(nome, path=None):
    with _db(path) as con:
        r = con.execute("SELECT payload FROM pratiche WHERE nome=?", (nome,)).fetchone()
    return json.loads(r[0]) if r else None


def elimina_pratica(nome, path=None):
    with _db(path) as con:
        con.execute("DELETE FROM pratiche WHERE nome=?", (nome,))


def log_report(pratica, report_id, modello, hash_dati, dettagli=None, path=None):
    with _db(path) as con:
        con.execute(
            "INSERT INTO report_log (pratica, report_id, creato, modello, hash_dati, dettagli) VALUES (?,?,?,?,?,?)",
            (pratica or "", report_id, _now(), modello, hash_dati, json.dumps(dettagli or {}, ensure_ascii=False, default=str)),
        )


def elenco_report(pratica=None, limit=20, path=None):
    with _db(path) as con:
        if pratica:
            cur = con.execute(
                "SELECT report_id, creato, modello, hash_dati, pratica FROM report_log WHERE pratica=? ORDER BY id DESC LIMIT ?",
                (pratica, limit),
            )
        else:
            cur = con.execute(
                "SELECT report_id, creato, modello, hash_dati, pratica FROM report_log ORDER BY id DESC LIMIT ?", (limit,)
            )
        return [
            {"report_id": r[0], "creato": r[1], "modello": r[2], "hash_dati": r[3], "pratica": r[4]}
            for r in cur
        ]


# ----------------------------------------------------------------------------
# REGISTRO ATTIVITA' (audit log)
# ----------------------------------------------------------------------------
def log_evento(utente, azione, dettaglio="", path=None):
    """Registra chi ha fatto cosa. Non solleva mai eccezioni: il log non deve bloccare l'applicazione."""
    try:
        with _db(path) as con:
            con.execute("INSERT INTO audit_log (ts, utente, azione, dettaglio) VALUES (?,?,?,?)",
                        (_now(), utente or "", azione, str(dettaglio)[:500]))
    except Exception:
        pass


def elenca_eventi(limite=200, utente=None, azione=None, path=None):
    q, par = "SELECT ts, utente, azione, dettaglio FROM audit_log", []
    cond = []
    if utente:
        cond.append("utente=?")
        par.append(utente)
    if azione:
        cond.append("azione=?")
        par.append(azione)
    if cond:
        q += " WHERE " + " AND ".join(cond)
    q += " ORDER BY id DESC LIMIT ?"
    par.append(int(limite))
    with _db(path) as con:
        return [{"Data (UTC)": r[0], "Utente": r[1], "Azione": r[2], "Dettaglio": r[3]} for r in con.execute(q, par)]


def tentativi_falliti(utente, secondi, path=None):
    """Login falliti dell'utente negli ultimi `secondi`, a partire dall'ultimo accesso riuscito o reimpostazione password."""
    da = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() - secondi))
    with _db(path) as con:
        r = con.execute("SELECT MAX(id) FROM audit_log WHERE (azione='login' AND utente=?) OR (azione='password_reimpostata' AND dettaglio=?)",
                        (utente, utente)).fetchone()[0] or 0
        return con.execute("SELECT COUNT(*) FROM audit_log WHERE utente=? AND azione='login_fallito' AND ts>=? AND id>?",
                           (utente, da, r)).fetchone()[0]


# ----------------------------------------------------------------------------
# UTENTI
# ----------------------------------------------------------------------------
def utente_db(username, path=None):
    with _db(path) as con:
        r = con.execute("SELECT username, hash, ruolo, attivo, creato, ultimo_accesso FROM utenti WHERE username=?", (username,)).fetchone()
    return dict(zip(("username", "hash", "ruolo", "attivo", "creato", "ultimo_accesso"), r)) if r else None


def elenca_utenti(path=None):
    with _db(path) as con:
        return [dict(zip(("username", "ruolo", "attivo", "creato", "ultimo_accesso", "creato_da"), r)) for r in
                con.execute("SELECT username, ruolo, attivo, creato, ultimo_accesso, creato_da FROM utenti ORDER BY username")]


def salva_utente(username, hash_pw, ruolo="utente", creato_da="", path=None):
    with _db(path) as con:
        if con.execute("SELECT 1 FROM utenti WHERE username=?", (username,)).fetchone():
            raise ValueError("Esiste gia' un utente con questo nome.")
        con.execute("INSERT INTO utenti (username, hash, ruolo, attivo, creato, creato_da) VALUES (?,?,?,1,?,?)",
                    (username, hash_pw, ruolo, _now(), creato_da))


def aggiorna_utente(username, path=None, **campi):
    ammessi = {"hash", "ruolo", "attivo", "ultimo_accesso"}
    campi = {k: v for k, v in campi.items() if k in ammessi}
    if not campi:
        return
    with _db(path) as con:
        con.execute("UPDATE utenti SET " + ", ".join(f"{k}=?" for k in campi) + " WHERE username=?", (*campi.values(), username))


def elimina_utente(username, path=None):
    with _db(path) as con:
        con.execute("DELETE FROM utenti WHERE username=?", (username,))
