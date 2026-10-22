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


def _now_ms():
    """Timestamp con i millisecondi, per riconoscere due salvataggi ravvicinati."""
    t = time.time()
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t)) + f".{int(t * 1000) % 1000:03d}"


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
        "CREATE TABLE IF NOT EXISTS pratiche_storico (id SERIAL PRIMARY KEY, nome TEXT, salvato TEXT, autore TEXT, payload TEXT)",
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
            "CREATE TABLE IF NOT EXISTS pratiche_storico ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, salvato TEXT, autore TEXT, payload TEXT)"
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


MODULI_ARCHIVIO = ("bp", "cf", "pv", "sc", "sl", "ga", "fo", "sx", "mz", "og", "rp", "gt", "cfg", "ru", "lg", "bk", "oa", "al", "pe", "pz")        # il Credit Risk usa i nomi "semplici"; gli altri moduli hanno un prefisso riservato


MAX_VERSIONI = 20          # versioni precedenti conservate per ogni salvataggio


def _chiave(nome, modulo="credit"):
    nome = (nome or "").strip()
    if modulo in MODULI_ARCHIVIO:
        return f"{modulo}|{nome}" if nome else ""
    if any(nome.startswith(m + "|") for m in MODULI_ARCHIVIO):
        raise ValueError("Il nome non puo' iniziare con un prefisso riservato (" + ", ".join(m + "|" for m in MODULI_ARCHIVIO) + ").")
    return nome


class ConflittoSalvataggio(Exception):
    """Il salvataggio esiste gia' ed e' stato modificato da qualcun altro (o non e' quello che si era aperto)."""

    def __init__(self, autore="", aggiornato=""):
        super().__init__(f"salvataggio modificato da {autore or 'un altro utente'} il {aggiornato}")
        self.autore, self.aggiornato = autore, aggiornato


def meta_pratica(nome, path=None, modulo="credit"):
    """{aggiornato, autore} del salvataggio, oppure None."""
    with _db(path) as con:
        r = con.execute("SELECT aggiornato, autore FROM pratiche WHERE nome=?", (_chiave(nome, modulo),)).fetchone()
    return {"aggiornato": r[0], "autore": r[1] or ""} if r else None


def salva_pratica(nome, payload, path=None, autore="", modulo="credit", atteso=None):
    """Salva (o sostituisce) un salvataggio e restituisce il suo nuovo timestamp.
    `atteso`: timestamp del salvataggio che l'utente aveva aperto ('' = nessuno). Se non e' None e il salvataggio esistente e' diverso
    (qualcun altro l'ha modificato, o il nome esiste gia' ed e' un'altra cosa) solleva ConflittoSalvataggio e non scrive nulla."""
    nome = _chiave(nome, modulo)
    if not nome:
        raise ValueError("Il nome non puo' essere vuoto.")
    testo = json.dumps(payload, ensure_ascii=False, default=str)
    with _db(path) as con:
        esiste = con.execute("SELECT payload, aggiornato, autore FROM pratiche WHERE nome=?", (nome,)).fetchone()
        if esiste and atteso is not None and esiste[1] != atteso:
            raise ConflittoSalvataggio(esiste[2] or "", esiste[1])
        adesso = _now_ms()
        vecchio_testo = esiste[0] if esiste else None
        if esiste:
            if esiste[0] != testo:                                   # conserva la versione che sta per essere sostituita
                con.execute("INSERT INTO pratiche_storico (nome, salvato, autore, payload) VALUES (?,?,?,?)", (nome, esiste[1], esiste[2] or "", esiste[0]))
                con.execute("DELETE FROM pratiche_storico WHERE nome=? AND id NOT IN "
                            "(SELECT id FROM pratiche_storico WHERE nome=? ORDER BY id DESC LIMIT ?)", (nome, nome, MAX_VERSIONI))
            con.execute("UPDATE pratiche SET aggiornato=?, payload=?, autore=? WHERE nome=?", (adesso, testo, autore, nome))
        else:
            con.execute(
                "INSERT INTO pratiche (nome, creato, aggiornato, payload, autore) VALUES (?,?,?,?,?)",
                (nome, adesso, adesso, testo, autore),
            )
    _registra_modifiche(nome, modulo, vecchio_testo, payload, autore, path)
    return adesso


def _registra_modifiche(chiave, modulo, vecchio_testo, nuovo, autore, path):
    """Registro attivita': ogni salvataggio scrive chi, quando, quale strumento e COSA e' cambiato. Non blocca mai il salvataggio."""
    try:
        if modulo == "pz":                                           # prezziario: migliaia di righe compresse, niente confronto voce per voce
            log_evento(autore, "prezziario_salvato", f"«{chiave.split('|', 1)[-1]}»: prezziario caricato o aggiornato", path)
            return
        if modulo == "al":                                           # foto e firme: niente confronto sui dati binari, solo chi e quando
            log_evento(autore, "allegati_salvati", f"«{chiave.split('|', 1)[-1]}»: foto o firme aggiornate", path)
            return
        import registro
        vecchio = json.loads(vecchio_testo) if vecchio_testo else None
        nome = chiave.split("|", 1)[1] if modulo in MODULI_ARCHIVIO and "|" in chiave else chiave
        cosa = registro.descrivi_modifiche(vecchio, json.loads(json.dumps(nuovo, ensure_ascii=False, default=str)))
        log_evento(autore, "modifiche_dati", f"[{registro.NOMI_MODULO.get(modulo, modulo)}] «{nome}»: {cosa}", path)
    except Exception:
        pass


def elenca_pratiche(path=None, modulo="credit"):
    with _db(path) as con:
        righe = con.execute("SELECT nome, aggiornato, autore FROM pratiche ORDER BY aggiornato DESC").fetchall()
    out = []
    for nome, agg, aut in righe:
        pref = next((m for m in MODULI_ARCHIVIO if nome.startswith(m + "|")), "credit")
        if pref == modulo:
            out.append({"nome": nome.split("|", 1)[1] if pref != "credit" else nome, "aggiornato": agg, "autore": aut or ""})
    return out


def ultimi_aggiornamenti(path=None):
    """{modulo: (aggiornato, autore, nome)} dell'ultimo salvataggio di ogni strumento. Serve a capire quali dati sono fermi da troppo."""
    with _db(path) as con:
        righe = con.execute("SELECT nome, aggiornato, autore FROM pratiche ORDER BY aggiornato DESC").fetchall()
    out = {}
    for nome, agg, aut in righe:
        pref = next((m for m in MODULI_ARCHIVIO if nome.startswith(m + "|")), "credit")
        if pref in ("cfg", "al", "pz"):
            continue
        out.setdefault(pref, (agg, aut or "", nome.split("|", 1)[1] if pref != "credit" else nome))
    return out


def carica_pratica(nome, path=None, modulo="credit"):
    with _db(path) as con:
        r = con.execute("SELECT payload FROM pratiche WHERE nome=?", (_chiave(nome, modulo),)).fetchone()
    return json.loads(r[0]) if r else None


def elimina_pratica(nome, path=None, modulo="credit"):
    with _db(path) as con:
        con.execute("DELETE FROM pratiche WHERE nome=?", (_chiave(nome, modulo),))
        con.execute("DELETE FROM pratiche_storico WHERE nome=?", (_chiave(nome, modulo),))


def storico_pratica(nome, path=None, modulo="credit"):
    """Versioni precedenti di un salvataggio, dalla piu' recente: [{id, salvato, autore}]."""
    with _db(path) as con:
        righe = con.execute("SELECT id, salvato, autore FROM pratiche_storico WHERE nome=? ORDER BY id DESC", (_chiave(nome, modulo),)).fetchall()
    return [{"id": r[0], "salvato": r[1], "autore": r[2] or ""} for r in righe]


def carica_versione(id_versione, path=None):
    with _db(path) as con:
        r = con.execute("SELECT payload FROM pratiche_storico WHERE id=?", (int(id_versione),)).fetchone()
    return json.loads(r[0]) if r else None


def database_persistente():
    """True se i dati stanno in un database esterno (PostgreSQL) e non in un file locale."""
    return bool(_url_db())


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
                        (_now(), utente or "", azione, str(dettaglio)[:1500]))
    except Exception:
        pass


def elenca_eventi(limite=200, utente=None, azione=None, path=None, da=None, a=None, cerca=None):
    """Registro attivita' dal piu' recente. `da`/`a`: date 'AAAA-MM-GG' (estremi inclusi, ora UTC); `cerca`: testo libero in utente, azione e dettaglio."""
    q, par = "SELECT ts, utente, azione, dettaglio FROM audit_log", []
    cond = []
    if utente:
        cond.append("utente=?")
        par.append(utente)
    if azione:
        cond.append("azione=?")
        par.append(azione)
    if da:
        cond.append("ts>=?")
        par.append(str(da) + " 00:00:00")
    if a:
        cond.append("ts<=?")
        par.append(str(a) + " 23:59:59")
    if cerca:
        cond.append("(LOWER(dettaglio) LIKE ? OR LOWER(azione) LIKE ? OR LOWER(utente) LIKE ?)")
        par += ["%" + str(cerca).lower() + "%"] * 3
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


def esporta_backup(path=None):
    """Copia di tutti i dati (pratiche, utenti SENZA hash delle password, report, registro) in un dizionario JSON-serializzabile."""
    out = {"generato": _now(), "database": "postgresql" if (not path and _url_db()) else "sqlite"}
    with _db(path) as con:
        out["pratiche"] = [dict(zip(("nome", "creato", "aggiornato", "autore", "payload"), r)) for r in
                           con.execute("SELECT nome, creato, aggiornato, autore, payload FROM pratiche ORDER BY nome")]
        out["storico"] = [dict(zip(("nome", "salvato", "autore", "payload"), r)) for r in
                          con.execute("SELECT nome, salvato, autore, payload FROM pratiche_storico ORDER BY id")]
        out["utenti"] = [dict(zip(("username", "ruolo", "attivo", "creato", "ultimo_accesso", "creato_da"), r)) for r in
                         con.execute("SELECT username, ruolo, attivo, creato, ultimo_accesso, creato_da FROM utenti ORDER BY username")]
        out["report_log"] = [dict(zip(("pratica", "report_id", "creato", "modello", "hash_dati"), r)) for r in
                             con.execute("SELECT pratica, report_id, creato, modello, hash_dati FROM report_log ORDER BY id")]
        out["audit_log"] = [dict(zip(("ts", "utente", "azione", "dettaglio"), r)) for r in
                            con.execute("SELECT ts, utente, azione, dettaglio FROM audit_log ORDER BY id")]
    return out
