import storage
from test_hub_bp import _nuovo


def _invia(at, label):
    b = next(x for x in at.button if x.label == label)
    b.click().run()


def _registro():
    return storage.carica_pratica("Rapportini", modulo="rp")


def test_apertura_e_modulo_in_hub(monkeypatch):
    at = _nuovo(monkeypatch)
    assert "Rapportini di cantiere" in " ".join(m.value for m in at.markdown)
    at = _nuovo(monkeypatch, modulo="rp")
    assert not at.exception and len(at.tabs) == 4 and at.session_state["rp_demo"] is True


def test_nuovo_rapportino_salva_e_toglie_l_esempio(monkeypatch):
    at = _nuovo(monkeypatch, modulo="rp")
    at.text_input(key="nr_nuovo").set_value("Villa Test")
    at.text_area(key="nr_lav").set_value("Getto soletta")
    at.number_input(key="nr_pres").set_value(6)
    at.number_input(key="nr_ore").set_value(48.0)
    _invia(at, "➕ Salva il rapportino")
    assert not at.exception
    reg = _registro()
    assert [r["Cantiere"] for r in reg["rapp"]] == ["Villa Test"] and reg["rapp"][0]["Ore"] == 48 and reg["rapp"][0]["Id"]
    assert at.session_state["rp_demo"] is False


def test_due_telefoni_non_si_sovrascrivono(monkeypatch):
    a = _nuovo(monkeypatch, modulo="rp")
    b = _nuovo(monkeypatch, modulo="rp")
    for at, cant, lav in ((a, "Cantiere A", "Muratura"), (b, "Cantiere B", "Intonaci")):
        at.text_input(key="nr_nuovo").set_value(cant)
        at.text_area(key="nr_lav").set_value(lav)
        at.number_input(key="nr_ore").set_value(16.0)
        _invia(at, "➕ Salva il rapportino")
        assert not at.exception
    assert sorted(r["Cantiere"] for r in _registro()["rapp"]) == ["Cantiere A", "Cantiere B"]


def test_segnalazione_e_chiusura(monkeypatch):
    at = _nuovo(monkeypatch, modulo="rp")
    at.text_input(key="ns_nuovo").set_value("Villa Test")
    at.text_area(key="ns_desc").set_value("Ponteggio instabile")
    at.selectbox(key="ns_grav").set_value("Alta")
    _invia(at, "⚠️ Invia la segnalazione")
    assert not at.exception
    segn = _registro()["segn"]
    assert len(segn) == 1 and segn[0]["Gravita"] == "Alta" and segn[0]["Stato"] == "Aperta"
    at.button(key=f"chi_{segn[0]['Id']}").click().run()
    assert not at.exception and _registro()["segn"][0]["Stato"] == "Chiusa"


def test_dossier_e_cruscotto(monkeypatch):
    at = _nuovo(monkeypatch, modulo="rp")
    at.button(key="gen_rp").click().run()
    assert not at.exception
    rep = at.session_state["rep_rp"]
    assert rep["pdf"][:4] == b"%PDF" and rep["xlsx"][:2] == b"PK"
