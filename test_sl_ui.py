import storage
from test_hub_bp import _btn, _nuovo


def test_hub_sette_strumenti_e_apertura_sl(monkeypatch):
    at = _nuovo(monkeypatch)
    assert "Strumento 7" in " ".join(m.value for m in at.markdown)
    _btn(at, "Apri SAL e contabilit").click().run()
    assert not at.exception and len(at.tabs) == 4
    assert any("Margine a finire" in m.value for m in at.markdown)


def test_salva_e_riapri_sl(monkeypatch):
    at = _nuovo(monkeypatch, modulo="sl")
    at.number_input(key="sl_gg_pagamento").set_value(45).run()
    at.text_input(key="sv_nome_sl").set_value("Lavori").run()
    at.button(key="sv_salva_sl").click().run()
    assert not at.exception and [p["nome"] for p in storage.elenca_pratiche(modulo="sl")] == ["Lavori"]
    assert storage.elenca_pratiche() == []
    at.number_input(key="sl_gg_pagamento").set_value(30).run()
    at.button(key="sv_apri_sl").click().run()
    assert not at.exception and at.number_input(key="sl_gg_pagamento").value == 45
    assert len(at.session_state["sl_com"]) == 3


def test_report_sl(monkeypatch):
    at = _nuovo(monkeypatch, modulo="sl")
    at.button(key="sl_gen").click().run()
    assert not at.exception and at.session_state["sl_rep"]["pdf"][:4] == b"%PDF" and at.session_state["sl_rep"]["xlsx"][:2] == b"PK"


def test_integrazioni_sl(monkeypatch):
    at = _nuovo(monkeypatch, modulo="sl")
    at.button(key="sl_to_sc").click().run()
    assert not at.exception
    sc_df = at.session_state["sc_df"]
    n = len(sc_df)
    assert n > 0 and sc_df["Documento"].str.startswith("SL:").all()
    at.button(key="sl_to_sc").click().run()                          # secondo invio: sostituisce, non duplica
    assert len(at.session_state["sc_df"]) == n
    at.button(key="sl_to_cf").click().run()
    assert not at.exception and len(at.session_state["cf_df"]) == 3 and at.session_state["cf_demo"] is False


def test_cruscotto_legge_sl(monkeypatch):
    at = _nuovo(monkeypatch, modulo="sl")
    _btn(at, "Torna all'Hub").click().run()
    _btn(at, "Apri Cruscotto").click().run()
    assert not at.exception
    assert "Margine a finire delle commesse" in " ".join(m.value for m in at.markdown)
