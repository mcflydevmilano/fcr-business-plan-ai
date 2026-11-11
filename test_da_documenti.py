import da
from test_hub_bp import _nuovo

PDF = b"%PDF-1.4 visura di prova"


def test_calcola_da_stati_e_avvisi():
    doc = [{"Tipo": "DURC", "Descrizione": "", "Numero": "", "Scadenza": "2020-01-01", "Responsabile": "Anna"}]
    out = da.calcola_da(doc, {"oggi": "2026-11-11", "preavviso_gg": 30})
    assert out["kpi"]["scaduti"] == 1 and out["documenti"][0]["Stato"] == "bad"
    assert "DURC" in out["avvisi"][0]


def test_apre_senza_errori_con_esempio_e_mostra_il_tab_dossier(monkeypatch):
    at = _nuovo(monkeypatch, modulo="da")
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.tabs) == 2
    assert any("Documenti aziendali" in m.value for m in at.markdown)


def test_carica_un_documento_aziendale(monkeypatch):
    at = _nuovo(monkeypatch, modulo="da")
    righe = list(at.session_state["da_doc"].to_dict("records"))
    assert righe
    t = righe[0]["Tipo"]
    at.selectbox(key="da_doc_sel").set_value(0).run()
    X = "application/pdf"
    at.file_uploader(key="da_doc_up").set_value([("doc.pdf", PDF, X)]).run()
    next(b for b in at.button if b.key == "da_doc_allega").click().run()
    assert not at.exception, [e.value for e in at.exception]
    import doc_allegati
    elenco = doc_allegati.elenca("azienda", t)
    assert elenco and elenco[0]["nome_file"] == "doc.pdf"
    assert any("doc.pdf" in c.value for c in at.caption)
