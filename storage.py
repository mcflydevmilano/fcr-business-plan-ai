"""
storage.py - Salvataggio pratiche e registro dei report (SQLite).

ATTENZIONE: su piattaforme con filesystem effimero (es. Streamlit Community Cloud) il file
si perde ad ogni riavvio. Imposta FCR_DB_PATH su un volume persistente oppure sostituisci
questo modulo con un database gestito (PostgreSQL, ecc.).
"""
import contextlib
import json
import os
import sqlite3
import time

DB_PATH = os.environ.get("FCR_DB_PATH", "fcr_pratiche.db")


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())


@contextlib.contextmanager
def _db(path=None):
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
        yield con
        con.commit()
    finally:
        con.close()


def salva_pratica(nome, payload, path=None):
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Il nome della pratica non puo' essere vuoto.")
    testo = json.dumps(payload, ensure_ascii=False, default=str)
    with _db(path) as con:
        esiste = con.execute("SELECT 1 FROM pratiche WHERE nome=?", (nome,)).fetchone()
        if esiste:
            con.execute("UPDATE pratiche SET aggiornato=?, payload=? WHERE nome=?", (_now(), testo, nome))
        else:
            con.execute(
                "INSERT INTO pratiche (nome, creato, aggiornato, payload) VALUES (?,?,?,?)",
                (nome, _now(), _now(), testo),
            )


def elenca_pratiche(path=None):
    with _db(path) as con:
        return [
            {"nome": r[0], "aggiornato": r[1]}
            for r in con.execute("SELECT nome, aggiornato FROM pratiche ORDER BY aggiornato DESC")
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
