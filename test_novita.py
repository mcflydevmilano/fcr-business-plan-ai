import pytest

import novita
import storage
import versione


@pytest.fixture
def db(tmp_path):
    storage.svuota_cache()
    return str(tmp_path / "n.db")


def test_l_ultima_novita_e_la_versione_corrente():
    """Ad ogni rilascio va aggiunta la voce in novita.py: se ci si dimentica, questo test lo ricorda."""
    assert novita.NOVITE[0]["id"] == versione.VERSIONE
    for v in novita.NOVITE:
        assert v["titolo"] and v["voci"] and v["data"]


def test_ordine_e_manuali(db):
    base = novita.tutte(db)
    assert base[0]["id"] == versione.VERSIONE and not base[0]["manuale"]
    i = novita.aggiungi("", "Rapportino senza campo", "- prima voce\n\n- seconda voce", ["Rapportini di cantiere", " "], "2099-01-01", "anna", db)
    t = novita.tutte(db)
    assert t[0]["id"] == i and t[0]["manuale"] and t[0]["voci"] == ["prima voce", "seconda voce"] and t[0]["strumenti"] == ["Rapportini di cantiere"]
    assert len(t) == len(base) + 1
    assert novita.elimina(i, "2099-01-01", db) and not novita.elimina(i, "2099-01-01", db)
    assert len(novita.tutte(db)) == len(base)
    assert not novita.elimina(novita.NOVITE[0]["id"], novita.NOVITE[0]["data"], db)             # le voci del programma non si cancellano


def test_validazione(db):
    with pytest.raises(ValueError):
        novita.aggiungi("", "", "x", [], None, "a", db)
    with pytest.raises(ValueError):
        novita.aggiungi("", "titolo", "  \n ", [], None, "a", db)
    with pytest.raises(ValueError):
        novita.aggiungi("", "titolo", "x", [], "ieri", "a", db)


def test_lette_per_persona(db):
    assert novita.da_leggere("mario", db)["id"] == versione.VERSIONE
    novita.segna_lette("Mario", db)
    assert novita.da_leggere("mario", db) is None
    assert novita.da_leggere("anna", db) is not None                       # ognuno ha le sue
    novita.aggiungi("9.9.9", "Nuova", "voce", [], "2099-01-01", "admin", db)
    assert novita.da_leggere("mario", db)["id"] == "9.9.9"                # una novita' nuova torna da leggere
    assert novita.da_leggere("", db) is None


def test_filtra():
    t = novita.tutte()
    assert all("Compiti e attività" in v["strumenti"] for v in novita.filtra(t, strumento="Compiti e attività"))
    assert novita.filtra(t, "bolle")
    assert novita.filtra(t, "xyzxyz") == []
    assert novita.data_it("2026-11-02") == "2 novembre 2026"


def _app(tmp_path, monkeypatch, utente="admin", pw="segreta"):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("APP_PASSWORD", pw)
    monkeypatch.setenv("ESEMPI_ATTIVI", "1")
    monkeypatch.setenv("FCR_DB_PATH", str(tmp_path / "n.db"))
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "n.db"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    storage.svuota_cache()
    at = AppTest.from_file("app.py", default_timeout=120).run()
    at.text_input(key="login_user").set_value(utente)
    at.text_input(key="login_pw").set_value(pw)
    at.button[0].click().run()
    return at


def test_schermata_e_avviso_nell_hub(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    assert not at.exception, [e.value for e in at.exception]
    apri = next(b for b in at.button if b.key == "hub_nv_apri")             # avviso nell'Hub: c'e' una novita' non letta
    apri.click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Novità e aggiornamenti" in m.value for m in at.markdown)
    assert any("novità da leggere" in s.value for s in at.success)
    # l'amministratore pubblica una novita'
    at.text_input(key="nv_n_tit").set_value("Prova")
    at.text_area(key="nv_n_voci").set_value("una cosa\naltra cosa")
    next(b for b in at.get("form_submit_button") if "Pubblica" in b.proto.label).click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any(v["titolo"] == "Prova" and v["manuale"] for v in novita.tutte())
    # tornando all'Hub l'avviso e' sparito
    at.session_state["active_module"] = None
    at.run()
    assert not any(b.key == "hub_nv_apri" for b in at.button)
