"""Fatture XML (interfaccia), sopralluogo e lettura bandi."""
import os
import tempfile

import pytest
from streamlit.testing.v1 import AppTest

import bd
import sp
import storage

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")


@pytest.fixture(autouse=True)
def db(monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
    monkeypatch.setenv("APP_PASSWORD", "segreta")


def _admin(modulo):
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["utente"] = {"username": "root", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = modulo
    return at.run()


@pytest.mark.parametrize("m", ["fe", "sp", "bd"])
def test_si_aprono(m):
    at = _admin(m)
    assert not at.exception, [e.value for e in at.exception]


def test_sp_stima_controlli_e_passaggio_al_fv():
    r = dict(sp.nuovo(), superficie_m2=50, cliente="Rossi", indirizzo="Via Po 1", copertura="Eternit / amianto", potenza_kw=3, accumulo=True, ombre="Media (alberi o palazzi vicini)")
    assert sp.stima_moduli(50, "Falda 30°") == 15 and sp.stima_moduli(50, "Tetto piano") == 11
    c = " ".join(sp.controlli(r))
    assert "amianto" in c and "potenza impegnata" in c and "Nessuna foto" in c
    p = sp.parametri_fv(r)
    assert p["fv_n_moduli"] == 15 and p["fv_ombra_pct"] == 15 and p["fv_accumulo_kwh"] == 5 and p["fv_cliente"] == "Rossi"
    import fv
    assert {k[3:] for k in p if k.startswith("fv_") and k[3:] in fv.FV_DEFAULT} <= set(fv.FV_DEFAULT)
    assert sp.docx_bytes(r)[:2] == b"PK"


def test_sp_salva_e_rilegge():
    r = dict(sp.nuovo(), cliente="Bianchi")
    sp.aggiungi(r, "mario")
    sp.aggiungi(dict(r, cliente="Bianchi 2"), "mario")
    el = sp.carica()
    assert len(el) == 1 and el[0]["cliente"] == "Bianchi 2" and el[0]["autore"] == "mario"


def test_sp_ui_crea_il_preventivo_fv():
    at = _admin("sp")
    at.text_input(key="sp_cliente").set_value("Verdi")
    at.number_input(key="sp_sup").set_value(40.0)
    at.run()
    at.button(key="sp_crea_fv").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["active_module"] == "fv"
    assert at.session_state["fv_cliente"] == "Verdi" and at.session_state["fv_n_moduli"] == 12


def test_bd_regole_e_checklist():
    t = ("Oggetto: lavori di riqualificazione energetica. CIG: 9A1B2C3D4E CUP B12C23000450001\nImporto a base di gara € 1.250.000,00. "
         "Termine presentazione offerte: 15/12/2026 ore 12. Sopralluogo obbligatorio. Cat. OG1 e OS28. DGUE, DURC, polizza.")
    s = bd.estrai_regole(t)
    assert s["cig"] == "9A1B2C3D4E" and s["cup"] == "B12C23000450001" and s["importo_base"] == 1250000 and s["scadenza_offerte"] == "2026-12-15"
    assert s["categorie_soa"] == ["OG1", "OS28"] and s["sopralluogo_obbligatorio"] is True
    ck = bd.checklist(s)
    assert ck[0].endswith("2026-12-15") and any("DURC" in x for x in ck)
    assert bd.estrai_regole("")["cig"] == "" and bd.estrai_regole(None)["importo_base"] is None
    u = bd.unisci(s, {"importo_base": 99, "oggetto": "", "cig": None})
    assert u["importo_base"] == 99 and u["cig"] == "9A1B2C3D4E"
    assert bd.estrai_ai(lambda *a, **k: ("non json", "m"), "k", "x") is None


def test_bd_ui_con_testo():
    at = _admin("bd")
    at.text_area(key="bd_txt").set_value("CIG: 9A1B2C3D4E importo a base di gara € 80.000,00 DURC")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Cosa ho trovato" in m.value for m in at.markdown)
