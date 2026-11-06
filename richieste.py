"""
richieste.py - Archivio comune delle richieste (ferie e permessi, note spese): una riga per richiesta, con stato, decisione e allegati (foto, PDF).
Ogni persona vede e modifica le sue; chi approva decide. Niente Streamlit, quindi testabile.
"""
import contextlib
import json
import os

import chat
import storage

_PRONTO = set()


def _ddl(pg):
    pk = "SERIAL PRIMARY KEY" if pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
    return [f"CREATE TABLE IF NOT EXISTS richieste (id {pk}, tipo TEXT, utente TEXT, stato TEXT, dati TEXT, creato TEXT, deciso_da TEXT, deciso_il TEXT, nota_decisione TEXT)",
            f"CREATE TABLE IF NOT EXISTS richieste_allegati (id {pk}, richiesta_id INTEGER, nome TEXT, tipo TEXT, dati TEXT)"]


@contextlib.contextmanager
def _db(path=None):
    with storage._db(path) as con:
        chiave = storage._identita_db(path)[:2]
        if chiave not in _PRONTO or (chiave[0] == "sqlite" and not os.path.exists(chiave[1])):
            for d in _ddl(isinstance(con, storage._ConPG)):
                con.execute(d)
            _PRONTO.add(chiave)
        yield con


def crea(tipo, utente, dati, allegati=(), stato="In attesa", path=None):
    """Nuova richiesta. `allegati`: [(nome, byte)] (foto o PDF, si ridimensionano). Restituisce l'id."""
    pronti = [chat.prepara_allegato(n, d) for n, d in allegati or ()]
    with _db(path) as con:
        rid = chat._inserisci(con, "INSERT INTO richieste (tipo, utente, stato, dati, creato) VALUES (?,?,?,?,?)",
                              (tipo, str(utente), stato, json.dumps(dati, ensure_ascii=False, default=str), storage._now()))
        for nome, mime, b64 in pronti:
            con.execute("INSERT INTO richieste_allegati (richiesta_id, nome, tipo, dati) VALUES (?,?,?,?)", (rid, nome, mime, b64))
    storage.svuota_cache()
    return rid


def _riga(r):
    try:
        dati = json.loads(r[4] or "{}")
    except ValueError:
        dati = {}
    return {"id": r[0], "tipo": r[1], "utente": r[2], "stato": r[3], "dati": dati, "creato": r[5], "deciso_da": r[6] or "", "deciso_il": r[7] or "", "nota_decisione": r[8] or ""}


def elenca(tipo, utente=None, stati=None, path=None):
    """Richieste di un tipo, le piu' recenti per prime."""
    q, par = "SELECT id, tipo, utente, stato, dati, creato, deciso_da, deciso_il, nota_decisione FROM richieste WHERE tipo=?", [tipo]
    if utente:
        q += " AND utente=?"
        par.append(str(utente))
    if stati:
        q += " AND stato IN (" + ",".join("?" * len(stati)) + ")"
        par += list(stati)
    with _db(path) as con:
        return [_riga(r) for r in con.execute(q + " ORDER BY id DESC", par).fetchall()]


def ottieni(rid, path=None):
    with _db(path) as con:
        r = con.execute("SELECT id, tipo, utente, stato, dati, creato, deciso_da, deciso_il, nota_decisione FROM richieste WHERE id=?", (int(rid),)).fetchone()
    return _riga(r) if r else None


def decidi(rid, esito, da, nota="", path=None):
    with _db(path) as con:
        con.execute("UPDATE richieste SET stato=?, deciso_da=?, deciso_il=?, nota_decisione=? WHERE id=?", (esito, str(da), storage._now(), str(nota or "")[:300], int(rid)))
    storage.svuota_cache()


def aggiorna_dati(rid, dati, path=None):
    with _db(path) as con:
        con.execute("UPDATE richieste SET dati=? WHERE id=?", (json.dumps(dati, ensure_ascii=False, default=str), int(rid)))
    storage.svuota_cache()


def allegati(rid, path=None):
    """[(nome, tipo, byte)]"""
    import base64
    with _db(path) as con:
        righe = con.execute("SELECT nome, tipo, dati FROM richieste_allegati WHERE richiesta_id=? ORDER BY id", (int(rid),)).fetchall()
    return [(n, t, base64.b64decode(d)) for n, t, d in righe]


def rinomina_utente(vecchio, nuovo, path=None):
    with _db(path) as con:
        con.execute("UPDATE richieste SET utente=? WHERE utente=?", (nuovo, vecchio))
        con.execute("UPDATE richieste SET deciso_da=? WHERE deciso_da=?", (nuovo, vecchio))
