"""Scadenzario: assegnazione del cantiere a piu' fatture insieme e saldo multiplo (interfaccia)."""
import os
import tempfile

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import sc
import storage

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")


def _w(elementi, key):
    """Il widget con questa key, o None se non c'e' (invece di sollevare KeyError come fa l'accesso diretto)."""
    return next((w for w in elementi if w.key == key), None)


@pytest.fixture(autouse=True)
def db(monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
    monkeypatch.setenv("APP_PASSWORD", "segreta")


def _righe():
    return [
        {"Tipo": "Attiva", "Controparte": "Mario Rossi", "Cantiere": "", "Documento": "1/1", "Data_doc": "2026-01-10", "Scadenza": "2026-01-10", "Importo": 1000.0, "Saldato": 0},
        {"Tipo": "Attiva", "Controparte": "Mario Rossi", "Cantiere": "", "Documento": "1/2", "Data_doc": "2026-02-10", "Scadenza": "2026-02-10", "Importo": 500.0, "Saldato": 0},
        {"Tipo": "Passiva", "Controparte": "Edil Alfa Srl", "Cantiere": "Via Verdi", "Documento": "F-9", "Data_doc": "2026-03-01", "Scadenza": "2026-03-01", "Importo": 800.0, "Saldato": 0},
        {"Tipo": "Passiva", "Controparte": "Edil Beta Srl", "Cantiere": "", "Documento": "F-10", "Data_doc": "2026-03-05", "Scadenza": "2026-03-05", "Importo": 300.0, "Saldato": 300.0},
    ]


def _admin():
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["utente"] = {"username": "root", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = "sc"
    at.session_state["sc_df"] = pd.DataFrame(_righe(), columns=sc.COLONNE_DOC)
    at.session_state["sc_demo"] = False
    return at.run()


def test_assegna_cantiere_a_piu_fatture_della_stessa_controparte():
    at = _admin()
    assert not at.exception, [e.value for e in at.exception]
    sel = _w(at.selectbox, "sc_bulk_contr")
    assert set(sel.options) == {"Edil Beta Srl", "Mario Rossi"}   # le due controparti con almeno una fattura senza cantiere
    sel.set_value("Mario Rossi").run()
    testo = _w(at.text_input, "sc_bulk_cant")
    testo.set_value("Via Verdi 2").run()
    _w(at.button, "sc_bulk_cant_ok").click().run()
    df = at.session_state["sc_df"]
    righe_mr = df[df["Controparte"] == "Mario Rossi"]
    assert (righe_mr["Cantiere"] == "Via Verdi 2").all()
    # la fattura con cantiere gia' assegnato non viene toccata
    assert df[df["Documento"] == "F-9"]["Cantiere"].iloc[0] == "Via Verdi"


def test_non_tocca_le_righe_che_hanno_gia_un_cantiere():
    at = _admin()
    _w(at.text_input, "sc_bulk_cant").set_value("Qualcosa").run()
    _w(at.button, "sc_bulk_cant_ok").click().run()
    df = at.session_state["sc_df"]
    assert df[df["Documento"] == "F-9"]["Cantiere"].iloc[0] == "Via Verdi"
    assert df[df["Documento"] == "F-10"]["Cantiere"].iloc[0] == "Qualcosa"   # F-10 era senza cantiere ed e' stata aggiornata


def test_salda_piu_fatture_insieme():
    at = _admin()
    assert not at.exception, [e.value for e in at.exception]
    ms = _w(at.multiselect, "sc_bulk_saldo")
    assert len(ms.options) == 3                                       # F-10 (indice 3) e' gia' saldata per intero, non compare tra le opzioni
    ms.set_value([0, 1, 2]).run()                                      # le tre righe aperte: indici del DataFrame originale
    _w(at.button, "sc_bulk_saldo_ok").click().run()
    df = at.session_state["sc_df"]
    assert (df["Importo"] == df["Saldato"]).all()


def test_salda_solo_le_selezionate():
    at = _admin()
    ms = _w(at.multiselect, "sc_bulk_saldo")
    ms.set_value([0]).run()                                           # indice 0 = la fattura "1/1"
    _w(at.button, "sc_bulk_saldo_ok").click().run()
    df = at.session_state["sc_df"]
    assert df[df["Documento"] == "1/1"]["Saldato"].iloc[0] == 1000.0
    assert df[df["Documento"] == "1/2"]["Saldato"].iloc[0] == 0


def test_sezioni_non_compaiono_se_non_serve():
    """Nessuna fattura senza cantiere e nessuna aperta: le due sezioni non vengono mostrate."""
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["utente"] = {"username": "root", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = "sc"
    at.session_state["sc_df"] = pd.DataFrame([{"Tipo": "Attiva", "Controparte": "X", "Cantiere": "Y", "Documento": "1", "Data_doc": "2026-01-01",
                                                "Scadenza": "2026-01-01", "Importo": 100.0, "Saldato": 100.0}], columns=sc.COLONNE_DOC)
    at.session_state["sc_demo"] = False
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert _w(at.selectbox, "sc_bulk_contr") is None
    assert _w(at.multiselect, "sc_bulk_saldo") is None


def test_lettore_non_vede_i_pannelli():
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["utente"] = {"username": "l", "ruolo": "lettore", "origine": "app_password"}
    at.session_state["active_module"] = "sc"
    at.session_state["sc_df"] = pd.DataFrame(_righe(), columns=sc.COLONNE_DOC)
    at.session_state["sc_demo"] = False
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert _w(at.selectbox, "sc_bulk_contr") is None
    assert _w(at.multiselect, "sc_bulk_saldo") is None
