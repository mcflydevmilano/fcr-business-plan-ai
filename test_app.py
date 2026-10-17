"""Smoke test dell'interfaccia con lo strumento di test integrato di Streamlit (senza chiamate a Gemini)."""
import os
import tempfile

import pytest
from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")


@pytest.fixture()
def at(monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setenv("FCR_DB_PATH", os.path.join(tmp, "test.db"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    import storage
    monkeypatch.setattr(storage, "DB_PATH", os.path.join(tmp, "test.db"))
    app = AppTest.from_file(APP, default_timeout=120)
    app.session_state["password_correct"] = True
    return app.run()


def _btn(at, testo):
    for b in at.button:
        if testo in b.label:
            return b
    raise AssertionError(f"bottone non trovato: {testo}")


def test_login_richiesto(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    app = AppTest.from_file(APP, default_timeout=60).run()
    assert not app.exception
    assert len(app.text_input) == 1 and "Password" in app.text_input[0].label
    assert len(app.tabs) == 0


def test_senza_password_configurata_si_ferma(monkeypatch):
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    app = AppTest.from_file(APP, default_timeout=60).run()
    assert any("APP_PASSWORD" in e.value for e in app.error)


def test_avvio_senza_eccezioni(at):
    assert not at.exception
    assert len(at.tabs) == 6


def test_leve_cambiano_il_punteggio(at):
    prima = at.session_state["delta_pn"] if "delta_pn" in at.session_state else 0
    at.slider(key="delta_pn").set_value(300000).run()
    assert not at.exception
    assert at.session_state["delta_pn"] == 300000 and prima == 0


def test_genera_report_senza_ai_e_excel(at):
    _btn(at, "Genera Report PDF + Word").click().run()
    assert not at.exception
    rep = at.session_state["report"]
    assert rep["pdf"][:4] == b"%PDF" and rep["docx"][:2] == b"PK"
    _btn(at, "Prepara file Excel").click().run()
    assert at.session_state["excel"]["bytes"][:2] == b"PK"


def test_salva_e_carica_pratica_e_scenario(at):
    at.slider(key="delta_ebitda").set_value(50000).run()
    at.text_input(key="nome_scenario").set_value("Prudente").run()
    _btn(at, "Salva scenario").click().run()
    assert "Prudente" in at.session_state["scenari"]

    at.text_input(key="pratica_nome").set_value("Pratica Test").run()
    _btn(at, "Salva pratica").click().run()
    assert not at.exception
    at.slider(key="delta_ebitda").set_value(0).run()
    assert at.session_state["delta_ebitda"] == 0
    _btn(at, "Carica").click().run()
    assert not at.exception
    assert at.session_state["delta_ebitda"] == 50000
    assert "Prudente" in at.session_state["scenari"]


def test_soglie_incoerenti_non_rompono(at):
    at.number_input(key="soglia_pfn_ebitda_v").set_value(9.0).run()
    assert not at.exception


def test_conferma_estrazione_applica_i_dati(at):
    import core
    dati, storico, fonti = core.normalizza_estrazione({
        "anno_riferimento": 2024, "ricavi": 4_000_000, "ebitda": 500_000, "utile_netto": 200_000,
        "totale_attivo": 5_000_000, "patrimonio_netto": 1_500_000, "debiti_finanziari_totali": 1_200_000,
        "pfn": 900_000, "dscr_stimato": 1.6,
        "storico": [{"anno": 2023, "ricavi": 3_800_000, "ebitda": 450_000, "patrimonio_netto": 1_300_000, "pfn": 950_000}],
        "fonti": {"ricavi": "pag. 3"},
    })
    at.session_state["bozza"] = {"dati": dati, "storico": storico, "fonti": fonti}
    at.session_state["bozza_ver"] = 1
    at.run()
    assert not at.exception
    assert at.session_state["financial_data"]["ricavi"] != 4_000_000      # non ancora applicato
    _btn(at, "Conferma e applica").click().run()
    assert not at.exception
    assert at.session_state["financial_data"]["ricavi"] == 4_000_000
    assert at.session_state["financial_data"]["anno_riferimento"] == 2024
    assert at.session_state["dati_demo"] is False
    assert [r["anno"] for r in at.session_state["storico"]] == [2023]
    assert "bozza" not in at.session_state


def test_annulla_estrazione_non_cambia_i_dati(at):
    import core
    dati, storico, fonti = core.normalizza_estrazione({"ricavi": 1_000_000})
    at.session_state["bozza"] = {"dati": dati, "storico": storico, "fonti": fonti}
    at.session_state["bozza_ver"] = 1
    at.run()
    _btn(at, "Annulla").click().run()
    assert at.session_state["financial_data"]["ricavi"] == 2_500_000
    assert at.session_state["dati_demo"] is True
