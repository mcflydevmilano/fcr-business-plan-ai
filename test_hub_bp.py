"""Hub, navigazione tra moduli e Business Plan Studio (AppTest, senza chiamate a Gemini)."""
import json
import os
import tempfile

import pytest
from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")


def _nuovo(monkeypatch, chiave=False, modulo=None):
    import storage
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setattr(storage, "DB_PATH", os.path.join(tmp, "t.db"))
    if chiave:
        monkeypatch.setenv("GEMINI_API_KEY", "chiave-finta")
    else:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = AppTest.from_file(APP, default_timeout=120)
    app.session_state["utente"] = {"username": "tester", "ruolo": "admin", "origine": "app_password"}
    if modulo:
        app.session_state["active_module"] = modulo
    if chiave:
        app.session_state["privacy_ok"] = True
    return app.run()


def _btn(at, testo):
    for b in at.button:
        if testo in b.label:
            return b
    raise AssertionError(f"bottone non trovato: {testo}; presenti: {[b.label for b in at.button]}")


def test_dopo_il_login_si_vede_l_hub(monkeypatch):
    at = _nuovo(monkeypatch)
    assert not at.exception
    assert len(at.tabs) == 0
    testo = " ".join(m.value for m in at.markdown)
    assert "Strumento 1" in testo and "Strumento 2" in testo
    assert "Credit Risk &amp; Rating Basilea 3/4" in testo or "Credit Risk & Rating Basilea 3/4" in testo
    _btn(at, "Apri Credit Risk")
    _btn(at, "Apri Business Plan Studio")


def test_apre_i_due_moduli_e_torna_all_hub(monkeypatch):
    at = _nuovo(monkeypatch)
    _btn(at, "Apri Credit Risk").click().run()
    assert not at.exception and len(at.tabs) == 6
    _btn(at, "Torna all'Hub").click().run()
    assert len(at.tabs) == 0
    _btn(at, "Apri Business Plan Studio").click().run()
    assert not at.exception and len(at.tabs) == 5


def test_credit_risk_ricorda_le_leve_dopo_il_giro_nell_hub(monkeypatch):
    at = _nuovo(monkeypatch, modulo="credit")
    at.slider(key="delta_pn").set_value(200000).run()
    _btn(at, "Torna all'Hub").click().run()
    _btn(at, "Apri Credit Risk").click().run()
    assert not at.exception
    assert at.session_state["delta_pn"] == 200000


def test_bp_calcola_e_ricorda_le_ipotesi(monkeypatch):
    at = _nuovo(monkeypatch, modulo="bp")
    assert not at.exception
    at.number_input(key="bp_ricavi_y1").set_value(2_000_000.0).run()
    at.radio(key="bp_n_anni").set_value(5).run()
    assert not at.exception
    assert at.session_state["bp_n_anni"] == 5
    _btn(at, "Torna all'Hub").click().run()
    _btn(at, "Apri Business Plan Studio").click().run()
    assert not at.exception
    assert at.session_state["bp_ricavi_y1"] == 2_000_000.0 and at.session_state["bp_n_anni"] == 5


def test_wizard_ai_propone_e_applica_le_ipotesi(monkeypatch):
    import ai
    risposta = json.dumps({"ricavi_y1": 1800000, "crescita": 12, "cv_pct": 50, "personale": 300000, "capex": 220000,
                           "anni_amm": 4, "mutuo": 150000, "tasso": 5, "durata": 6, "equity": 70000,
                           "motivazioni": {"ricavi_y1": "dato dalla descrizione"}, "note": "Verificare i tempi."})
    monkeypatch.setattr(ai, "genera", lambda *a, **k: (risposta, "modello-finto"))
    at = _nuovo(monkeypatch, chiave=True, modulo="bp")
    _btn(at, "Genera le ipotesi con l'AI").click().run()
    assert not at.exception
    assert at.session_state["bp_prop"]["valori"]["ricavi_y1"] == 1_800_000
    _btn(at, "Applica le ipotesi proposte").click().run()
    assert not at.exception
    assert at.session_state["bp_ricavi_y1"] == 1_800_000 and at.session_state["bp_durata"] == 6
    assert "bp_prop" not in at.session_state


def test_wizard_quota_esaurita_messaggio_amichevole(monkeypatch):
    import ai

    def finta(*a, **k):
        raise Exception("429 RESOURCE_EXHAUSTED quota")

    monkeypatch.setattr(ai, "genera", finta)
    at = _nuovo(monkeypatch, chiave=True, modulo="bp")
    _btn(at, "Genera le ipotesi con l'AI").click().run()
    assert not at.exception
    assert any("quota giornaliera" in e.value for e in at.error)
    assert not any("429" in e.value for e in at.error)


def test_wizard_bloccato_senza_chiave(monkeypatch):
    at = _nuovo(monkeypatch, modulo="bp")
    assert _btn(at, "Genera le ipotesi con l'AI").disabled


def test_dossier_pdf_senza_ai(monkeypatch):
    at = _nuovo(monkeypatch, modulo="bp")
    _btn(at, "Genera il dossier PDF").click().run()
    assert not at.exception
    rep = at.session_state["bp_report"]
    assert rep["pdf"][:4] == b"%PDF" and rep["quota"] is False


def test_dossier_con_quota_esaurita_genera_comunque_il_pdf(monkeypatch):
    import ai

    def finta(*a, **k):
        raise Exception("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(ai, "genera", finta)
    at = _nuovo(monkeypatch, chiave=True, modulo="bp")
    _btn(at, "Genera il dossier PDF").click().run()
    assert not at.exception
    rep = at.session_state["bp_report"]
    assert rep["quota"] is True and rep["pdf"][:4] == b"%PDF"
    assert any("non e' disponibile ora" in w.value for w in at.warning)
