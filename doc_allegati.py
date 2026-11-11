"""
doc_allegati.py - Archivio generico di documenti allegati (PDF, foto): usato da Fornitori (es. il PDF del DURC di un
fornitore) e da Documenti aziendali FCR (DURC, SOA, certificazioni, assicurazioni, visura dell'azienda).

I file stanno in una tabella a parte (`doc_allegati`), NON nei salvataggi delle pratiche: cosi' non appesantiscono i
dati principali e non finiscono nelle versioni storiche. Riusa i controlli gia' scritti e testati in ddt.py (tipo
riconosciuto dal contenuto, dimensione massima, foto ridotte, file doppi per impronta).

`categoria` distingue chi usa l'archivio ("fornitori", "azienda", ...); `riferimento` e `voce` sono liberi
(per i fornitori: nome del fornitore e tipo di documento; per l'azienda: vuoto e tipo di documento).
"""
import contextlib
import hashlib
import os
import uuid

import storage
from ddt import DdtErrore, prepara

_PRONTO = set()


class DocDoppio(DdtErrore):
    def __init__(self, id_esistente):
        super().__init__("Questo file è già stato caricato (stesso contenuto di un documento già presente).")
        self.id_esistente = id_esistente


def _ddl(pg):
    blob = "BYTEA" if pg else "BLOB"
    return ("CREATE TABLE IF NOT EXISTS doc_allegati (id TEXT PRIMARY KEY, creato TEXT, categoria TEXT, riferimento TEXT, voce TEXT, scadenza TEXT, "
            f"nome_file TEXT, mime TEXT, dimensione INTEGER, sha256 TEXT, caricato_da TEXT, note TEXT, dati {blob})",
            "CREATE INDEX IF NOT EXISTS doc_allegati_cat ON doc_allegati (categoria, riferimento, voce)",
            "CREATE INDEX IF NOT EXISTS doc_allegati_sha ON doc_allegati (sha256)")


@contextlib.contextmanager
def _db(path=None):
    with storage._db(path) as con:
        chiave = storage._identita_db(path)[:2]
        if chiave not in _PRONTO or (chiave[0] == "sqlite" and not os.path.exists(chiave[1])):
            for ddl in _ddl(isinstance(con, storage._ConPG)):
                con.execute(ddl)
            _PRONTO.add(chiave)
        yield con


COLONNE_META = ("id", "creato", "categoria", "riferimento", "voce", "scadenza", "nome_file", "mime", "dimensione", "caricato_da", "note")
_SEL = ", ".join(COLONNE_META)


def _riga(r):
    return dict(zip(COLONNE_META, r))


def _s(v, n=200):
    return str(v or "").strip()[:n]


def salva(categoria, riferimento, voce, nome, dati, scadenza="", note="", utente="", path=None):
    """Salva un documento. Restituisce l'id. Solleva DdtErrore (file non valido) o DdtDoppio (stesso contenuto già presente)."""
    nome, _tipo, mime, dati = prepara(nome, dati)
    sha = hashlib.sha256(dati).hexdigest()
    with _db(path) as con:
        r = con.execute("SELECT id FROM doc_allegati WHERE sha256=? AND categoria=? LIMIT 1", (sha, _s(categoria, 40))).fetchone()
        if r:
            raise DocDoppio(r[0])
        i = uuid.uuid4().hex[:16]
        con.execute("INSERT INTO doc_allegati (id, creato, categoria, riferimento, voce, scadenza, nome_file, mime, dimensione, sha256, caricato_da, note, dati) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (i, storage._now(), _s(categoria, 40), _s(riferimento), _s(voce), _s(scadenza, 10), nome, mime, len(dati), sha, _s(utente, 60), _s(note, 500), dati))
    storage.svuota_cache()
    return i


def elenca(categoria, riferimento=None, path=None):
    """Documenti di una categoria (ed eventualmente di un riferimento), dati descrittivi (mai il file), dal più recente."""
    cond, par = ["categoria=?"], [_s(categoria, 40)]
    if riferimento is not None:
        cond.append("riferimento=?")
        par.append(_s(riferimento))
    with _db(path) as con:
        return [_riga(r) for r in con.execute(f"SELECT {_SEL} FROM doc_allegati WHERE {' AND '.join(cond)} ORDER BY creato DESC, id", par).fetchall()]


def leggi(id_, path=None):
    """(dati_descrittivi, bytes) oppure None."""
    with _db(path) as con:
        r = con.execute(f"SELECT {_SEL}, dati FROM doc_allegati WHERE id=?", (_s(id_, 40),)).fetchone()
    if not r:
        return None
    return _riga(r[:-1]), bytes(r[-1])


def elimina(id_, path=None):
    with _db(path) as con:
        con.execute("DELETE FROM doc_allegati WHERE id=?", (_s(id_, 40),))
    storage.svuota_cache()


def conteggio(categoria, path=None):
    """{riferimento: numero di documenti} per una categoria (es. quanti documenti ha caricato ogni fornitore)."""
    with _db(path) as con:
        righe = con.execute("SELECT riferimento, COUNT(*) FROM doc_allegati WHERE categoria=? GROUP BY riferimento", (_s(categoria, 40),)).fetchall()
    return {r[0]: r[1] for r in righe}
