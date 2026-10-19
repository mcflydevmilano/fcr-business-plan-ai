"""Archivio su PostgreSQL. Si esegue solo se TEST_DATABASE_URL e' impostata (altrimenti viene saltato)."""
import os

import pytest

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL non impostata")


@pytest.fixture
def pg(monkeypatch):
    import storage
    monkeypatch.setenv("DATABASE_URL", URL)
    with storage._db() as con:
        for t in ("pratiche", "report_log", "utenti", "audit_log"):
            con.execute(f"DELETE FROM {t}")
    return storage


def test_pratiche_utenti_e_log(pg):
    pg.salva_pratica("Alfa", {"x": 1}, autore="mario")
    pg.salva_pratica("Alfa", {"x": 2}, autore="anna")
    assert pg.carica_pratica("Alfa") == {"x": 2}
    assert pg.elenca_pratiche()[0]["autore"] == "anna"
    pg.elimina_pratica("Alfa")
    assert pg.carica_pratica("Alfa") is None
    pg.salva_utente("luca", "hash", "utente", "admin")
    with pytest.raises(ValueError):
        pg.salva_utente("luca", "h", "utente")
    pg.aggiorna_utente("luca", ruolo="admin", attivo=0)
    u = pg.utente_db("luca")
    assert u["ruolo"] == "admin" and u["attivo"] == 0
    pg.log_report("Alfa", "R1", "m", "h", {"a": 1})
    assert pg.elenco_report("Alfa")[0]["report_id"] == "R1"
    pg.log_evento("luca", "login_fallito", "x")
    pg.log_evento("luca", "login_fallito", "x")
    assert pg.tentativi_falliti("luca", 900) == 2
    pg.log_evento("luca", "login")
    assert pg.tentativi_falliti("luca", 900) == 0
    assert pg.elenca_eventi(10, utente="luca")[0]["Azione"] == "login"
    pg.elimina_utente("luca")
    assert pg.utente_db("luca") is None
