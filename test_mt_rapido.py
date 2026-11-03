"""Materiali: inserimento veloce con prezzo automatico e pistola barcode."""
import os
import tempfile

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import mt
import storage

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")


@pytest.fixture(autouse=True)
def db(monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
    monkeypatch.setenv("APP_PASSWORD", "segreta")


def _mt():
    at = AppTest.from_file(APP, default_timeout=240)
    at.session_state["utente"] = {"username": "root", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = "mt"
    at.session_state["mt_ord"] = pd.DataFrame([{"Materiale": "Cemento", "Fornitore": "Beton Nord", "Commessa": "Villa Lago", "Quantita": 10, "Um": "sacchi", "Prezzo_unit": 7.0,
                                                "Consegna_prevista": "", "Consegnato": "no", "Data_consegna": "", "Ddt": ""}], columns=mt.COLONNE_ORDINI)
    at.session_state["mt_mov"] = pd.DataFrame(columns=mt.COLONNE_MOV)
    at.session_state["mt_art"] = pd.DataFrame([{"Codice": "111", "Materiale": "Cemento", "Um": "sacchi", "Magazzino": "Deposito", "Scorta_min": 5, "Prezzo": 7.5}], columns=mt.COLONNE_ART)
    at.session_state["mt_demo"] = False
    return at.run()


def test_prezzo_automatico_ordine_veloce():
    at = _mt()
    assert not at.exception, [e.value for e in at.exception]
    at.selectbox(key="mt_q_mat").set_value("Cemento").run()
    at.selectbox(key="mt_q_for").set_value("Beton Nord").run()
    assert at.session_state["mt_q_prz"] == 7.0 and at.session_state["mt_q_um"] == "sacchi"
    at.number_input(key="mt_q_qta").set_value(4.0).run()
    at.button(key="mt_q_ok").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.session_state["mt_ord"]) == 2


def test_pistola_carica_e_codice_sconosciuto():
    at = _mt()
    at.text_input(key="mt_p_cod").set_value("111")
    [b for b in at.button if b.label == "Registra" and "mt_p_form" in str(getattr(b, "form_id", ""))][0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.session_state["mt_mov"]) == 1 and at.session_state["mt_mov"].iloc[0]["Magazzino"] == "Deposito"
    assert "Giacenza ora: 1" in at.session_state["mt_p_msg"][1]
    at.text_input(key="mt_p_cod").set_value("999")
    [b for b in at.button if b.label == "Registra" and "mt_p_form" in str(getattr(b, "form_id", ""))][0].click().run()
    assert at.session_state["mt_p_nuovo"] == "999" and not at.exception


def test_subappalti_inserimento_veloce():
    import sa
    at = AppTest.from_file(APP, default_timeout=240)
    at.session_state["utente"] = {"username": "root", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = "sa"
    at.session_state["sa_con"] = pd.DataFrame([{"Subappaltatore": "Adam Costruzioni", "Commessa": "Villa Lago", "Lavorazione": "Murature", "Importo_contratto": 50000, "Ritenuta_pct": 5}], columns=sa.COLONNE_CONTRATTI)
    at.session_state["sa_sal"] = pd.DataFrame(columns=sa.COLONNE_SAL)
    at.session_state["sa_doc"] = pd.DataFrame(columns=sa.COLONNE_DOC)
    at.session_state["sa_demo"] = False
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    at.selectbox(key="sa_q_sub").set_value("Adam Costruzioni").run()
    at.selectbox(key="sa_q_com").set_value("Villa Lago").run()
    at.number_input(key="sa_q_imp").set_value(12000.0).run()
    at.button(key="sa_q_ok").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.session_state["sa_con"]) == 2
