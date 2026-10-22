"""Senza esempi la suite parte vuota e ogni strumento si apre senza errori."""
import os
import tempfile

import pytest
from streamlit.testing.v1 import AppTest

import storage

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
SIGLE = ["bk", "fo", "ga", "gt", "lg", "mz", "oa", "og", "pe", "rp", "ru", "sc", "sl", "sx", "cf", "pv", "ca", "pz", "dd", "rc"]


@pytest.fixture(autouse=True)
def db(monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setenv("ESEMPI_ATTIVI", "0")


@pytest.mark.parametrize("sigla", SIGLE)
def test_si_apre_vuoto(sigla):
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["utente"] = {"username": "root", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = sigla
    at.run()
    assert not at.exception, (sigla, [e.value for e in at.exception])
    assert not any("Dati di esempio" in (i.value or "") for i in at.info), sigla


def test_tabelle_davvero_vuote():
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["utente"] = {"username": "root", "ruolo": "admin", "origine": "app_password"}
    for sigla, chiave in [("fo", "fo_doc"), ("pv", "pv_df"), ("cf", "cf_df"), ("sc", "sc_df"), ("ru", "ru_cont")]:
        at.session_state["active_module"] = sigla
        at.run()
        assert not at.exception, sigla
        assert len(at.session_state[chiave]) == 0, chiave
