import fo
from test_hub_bp import _btn, _nuovo

X = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF = b"%PDF-1.4 prova durc"


def test_posa_smaltimento_si_salvano_e_compaiono_nel_confronto():
    off = [{"Voce": "Impianto X", "Fornitore": "A", "Importo": 1000, "Posa": "Sì", "Smaltimento": "No"},
           {"Voce": "Impianto X", "Fornitore": "B", "Importo": 900, "Posa": "No", "Smaltimento": "No"}]
    righe, av = fo.normalizza_offerte(off)
    assert righe[0]["Posa"] == "Sì" and righe[0]["Smaltimento"] == "No" and righe[1]["Posa"] == "No"
    out = fo.calcola_fo([], [], righe)
    assert out["confronto"][0]["Posa (più bassa)"] == "No"                          # B e' la piu' bassa e non include la posa
    assert any("non sono tutte comparabili" in a for a in out["avvisi"])            # posa diversa tra le due offerte: va segnalato


def test_fo_carica_e_scarica_un_documento(monkeypatch):
    at = _nuovo(monkeypatch, modulo="fo")
    assert not at.exception
    righe = list(at.session_state["fo_doc"].to_dict("records"))
    assert righe, "l'esempio deve avere almeno un documento"
    f = righe[0]
    at.selectbox(key="fo_doc_sel").set_value(0).run()
    at.file_uploader(key="fo_doc_up").set_value([("durc.pdf", PDF, "application/pdf")]).run()
    next(b for b in at.button if b.key == "fo_doc_allega").click().run()
    assert not at.exception, [e.value for e in at.exception]
    import doc_allegati
    elenco = doc_allegati.elenca("fornitori", f["Fornitore"])
    assert elenco and elenco[0]["nome_file"] == "durc.pdf" and elenco[0]["voce"] == f["Documento"]
    assert any("durc.pdf" in c.value for c in at.caption)
    next(b for b in at.button if (b.key or "").startswith("fo_doc_del_")).click().run()
    assert not at.exception and doc_allegati.elenca("fornitori", f["Fornitore"]) == []
