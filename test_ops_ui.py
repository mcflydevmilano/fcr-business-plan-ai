import pytest

import storage
from test_hub_bp import _btn, _nuovo

MODULI = [("ga", "Apri Gare e offerte", "ga_margine_target", 12.0, 4), ("fo", "Apri Fornitori", "fo_preavviso_gg", 45, 4), ("sx", "Apri Sicurezza", "sx_preavviso_gg", 45, 3),
          ("mz", "Apri Parco mezzi", "mz_preavviso_gg", 45, 4), ("og", "Apri Organico", "og_mesi", 8, 3)]


def test_hub_dodici_strumenti(monkeypatch):
    at = _nuovo(monkeypatch)
    t = " ".join(m.value for m in at.markdown)
    assert "Organico e carico di lavoro" in t
    for _m, btn, *_ in MODULI:
        _btn(at, btn).click().run()
        assert not at.exception
        _btn(at, "Torna all'Hub").click().run()
        assert not at.exception


@pytest.mark.parametrize("modulo,btn,chiave,valore,ntab", MODULI)
def test_apertura_salvataggio_report(monkeypatch, modulo, btn, chiave, valore, ntab):
    at = _nuovo(monkeypatch, modulo=modulo)
    assert not at.exception and len(at.tabs) == ntab
    at.number_input(key=chiave).set_value(valore).run()
    at.text_input(key=f"sv_nome_{modulo}").set_value("Prova").run()
    at.button(key=f"sv_salva_{modulo}").click().run()
    assert not at.exception and [p["nome"] for p in storage.elenca_pratiche(modulo=modulo)] == ["Prova"]
    assert storage.elenca_pratiche() == []
    at.number_input(key=chiave).set_value(valore - 1 if isinstance(valore, int) else valore - 1.0).run()
    at.button(key=f"sv_apri_{modulo}").click().run()
    assert not at.exception and at.number_input(key=chiave).value == valore
    at.button(key=f"gen_{modulo}").click().run()
    assert not at.exception
    rep = at.session_state[f"rep_{modulo}"]
    assert rep["pdf"][:4] == b"%PDF" and rep["xlsx"][:2] == b"PK"


def test_checklist_e_integrazioni(monkeypatch):
    at = _nuovo(monkeypatch, modulo="ga")
    n0 = len(at.session_state["ga_doc"])
    at.selectbox(key="ga_sel_chk").set_value("Riqualificazione Piazza").run()
    at.button(key="chk_ga").click().run()
    assert not at.exception and len(at.session_state["ga_doc"]) == n0 + 8
    at.button(key="to_sl_ga").click().run()
    assert not at.exception and "Capannone Logistica" in list(at.session_state["sl_com"]["Commessa"])
    n = len(at.session_state["sl_com"])
    at.button(key="to_sl_ga").click().run()
    assert len(at.session_state["sl_com"]) == n                       # secondo invio: nessun duplicato
    at = _nuovo(monkeypatch, modulo="mz")
    at.button(key="to_sl_mz").click().run()
    assert not at.exception and (at.session_state["sl_cos"]["Fornitore"] == "Parco mezzi interno").any()


def test_cruscotto_legge_i_nuovi_moduli(monkeypatch):
    at = _nuovo(monkeypatch, modulo="ga")
    for m, btn in (("fo", "Apri Fornitori"), ("sx", "Apri Sicurezza"), ("mz", "Apri Parco mezzi"), ("og", "Apri Organico")):
        _btn(at, "Torna all'Hub").click().run()
        _btn(at, btn).click().run()
        assert not at.exception
    _btn(at, "Torna all'Hub").click().run()
    _btn(at, "Apri Cruscotto").click().run()
    assert not at.exception
    t = " ".join(x.value for x in at.markdown)
    for voce in ("Gare in scadenza o in ritardo", "Documenti dei fornitori scaduti", "Cantieri con documenti o formazioni non in regola", "Scadenze dei mezzi superate", "Mesi in sovraccarico"):
        assert voce in t, voce


def test_cronoprogramma_gantt_e_integrazioni(monkeypatch):
    at = _nuovo(monkeypatch, modulo="gt")
    assert not at.exception and len(at.tabs) == 3 and at.session_state["gt_demo"] is True
    at.button(key="gen_gt").click().run()
    assert not at.exception
    rep = at.session_state["rep_gt"]
    assert rep["pdf"][:4] == b"%PDF" and rep["xlsx"][:2] == b"PK"
    at.text_input(key="sv_nome_gt").set_value("Prova").run()
    at.button(key="sv_salva_gt").click().run()
    assert not at.exception and [p["nome"] for p in storage.elenca_pratiche(modulo="gt")] == ["Prova"]
    at = _nuovo(monkeypatch, modulo="sl")                           # SAL di esempio -> fasi del cronoprogramma
    n_sl = len(at.session_state["sl_com"])
    _btn(at, "Torna all'Hub").click().run()
    _btn(at, "Apri Cronoprogramma").click().run()
    at.button(key="da_sl_gt").click().run()
    assert not at.exception and len(at.session_state["gt_fasi"]) == n_sl and at.session_state["gt_demo"] is False
