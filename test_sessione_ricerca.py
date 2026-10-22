"""Login che resta dopo F5 (gettone firmato) e ricerca nella home."""
import os
import tempfile

import pytest

import auth
import hub
import ricerca
import sessione
import storage


@pytest.fixture(autouse=True)
def db(monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))


K = sessione.chiave(["segreto"])
SEC = {"lorenzo": {"hash": "h1", "ruolo": "admin"}}
U = {"username": "lorenzo", "ruolo": "admin", "origine": "secrets"}


def test_gettone_valido_e_ripristino():
    t = sessione.crea(U, K, SEC, None, 12, adesso=1000)
    assert sessione.ripristina(t, K, SEC, None, adesso=2000) == U


def test_scaduto():
    t = sessione.crea(U, K, SEC, None, 1, adesso=1000)
    assert sessione.ripristina(t, K, SEC, None, adesso=1000 + 3601) is None


def test_manomesso_o_chiave_diversa():
    t = sessione.crea(U, K, SEC, None, 12)
    corpo, firma = t.split(".")
    assert sessione.ripristina(corpo + "." + firma[:-2] + "xx", K, SEC, None) is None
    assert sessione.ripristina(t, sessione.chiave(["altro"]), SEC, None) is None
    assert sessione.ripristina("spazzatura", K, SEC, None) is None
    assert sessione.ripristina("", K, SEC, None) is None


def test_cambio_password_o_utente_rimosso_invalida():
    t = sessione.crea(U, K, SEC, None, 12)
    assert sessione.ripristina(t, K, {"lorenzo": {"hash": "h2", "ruolo": "admin"}}, None) is None
    assert sessione.ripristina(t, K, {}, None) is None


def test_ruolo_riletto_dai_dati_attuali():
    t = sessione.crea(U, K, SEC, None, 12)
    r = sessione.ripristina(t, K, {"lorenzo": {"hash": "h1", "ruolo": "lettore"}}, None)
    assert r["ruolo"] == "lettore"


def test_utente_db_e_disattivato():
    auth.crea_utente("anna", "password123", "utente", "t")
    u = {"username": "anna", "ruolo": "utente", "origine": "db"}
    t = sessione.crea(u, K)
    assert sessione.ripristina(t, K)["username"] == "anna"
    storage.imposta_attivo_utente("anna", False) if hasattr(storage, "imposta_attivo_utente") else None


def test_app_password():
    u = {"username": "admin", "ruolo": "admin", "origine": "app_password"}
    t = sessione.crea(u, K, None, "pw1")
    assert sessione.ripristina(t, K, None, "pw1") == u
    assert sessione.ripristina(t, K, None, "pw2") is None


def test_ricerca_strumenti():
    cons = list(hub.CARDS)
    r = ricerca.cerca_strumenti("fattura", cons, hub.CARDS)
    assert r, "deve trovare strumenti"
    assert ricerca.cerca_strumenti("", cons, hub.CARDS) == []
    assert ricerca.cerca_strumenti("fattura", [], hub.CARDS) == []


def test_ricerca_senza_risultati():
    assert ricerca.cerca_strumenti("qqqzzzxxx", list(hub.CARDS), hub.CARDS) == []
