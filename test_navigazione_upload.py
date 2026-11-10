"""Cambiare strumento non deve mai provare a "ricordare" il valore di un caricamento file: Streamlit non lo permette e manda in errore
la pagina appena il widget viene ricreato (successo in passato con «cl», «sd», «fv», ecc.). Vedi app.py: _chiavi_pulsanti/_e_pulsante/_vai_ora."""
import os
import tempfile

import pytest
from streamlit.testing.v1 import AppTest

import storage

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
# le chiavi dei caricamenti file che, nel codice, condividono il prefisso di stato del loro stesso modulo (le piu' a rischio:
# se tornassero a essere "ricordate" tra uno strumento e l'altro, riaprire lo strumento manderebbe un errore alla persona)
CHIAVI_CARICAMENTO = ["cl_up", "bd_up", "fe_up", "sd_up", "sp_foto", "ee_up_list", "fv_up_list", "ns_n_foto", "ns_foto"]


@pytest.fixture(autouse=True)
def db(monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
    monkeypatch.setenv("APP_PASSWORD", "segreta")


def _admin(modulo):
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["utente"] = {"username": "root", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = modulo
    return at.run()


@pytest.mark.parametrize("modulo", ["cl", "bd", "fe", "sd", "sp"])
def test_uscire_e_rientrare_in_uno_strumento_con_caricamento_file_non_rompe_nulla(modulo):
    at = _admin(modulo)
    assert not at.exception, [e.value for e in at.exception]
    at.button(key="hub_top").click().run()                 # "🏠 Hub": e' qui che lo stato dello strumento lasciato viene fotografato
    assert not at.exception, [e.value for e in at.exception]
    at.session_state["active_module"] = modulo              # si torna nello stesso strumento
    at.run()
    assert not at.exception, [e.value for e in at.exception]


def test_le_chiavi_di_caricamento_non_finiscono_mai_nella_fotografia_dello_stato():
    at = _admin("cl")
    at.button(key="hub_top").click().run()
    snap = at.session_state.get("_snap_cl") or {}
    assert "cl_up" not in snap
    for k in CHIAVI_CARICAMENTO:
        assert k not in snap, f"{k} non deve essere ricordata tra uno strumento e l'altro"
