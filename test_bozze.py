"""Salvataggio automatico (bozze): niente perdite di lavoro, niente scritture inutili."""
import os

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import permessi
import storage

APP = os.path.join(os.path.dirname(__file__), "app.py")


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "b.db"))
    storage.svuota_cache()
    yield


def _app(modulo):
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["utente"] = {"username": "admin", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = modulo
    return at.run()


def _bozze():
    return [n for n, _, _ in storage._righe_pratiche() if n.startswith("bz|")]


def test_storage_bozza_va_e_viene_senza_sporcare_gli_elenchi():
    storage.salva_bozza("mario rossi", "pe", {"persone": [{"Persona": "Anna"}]})
    p, quando = storage.carica_bozza("mario rossi", "pe")
    assert p == {"persone": [{"Persona": "Anna"}]} and quando
    assert storage.carica_bozza("luca neri", "pe") == (None, "")
    assert storage.elenca_pratiche(modulo="pe") == [] and storage.elenca_pratiche() == []          # non e' un salvataggio con nome
    assert "bz" not in storage.ultimi_aggiornamenti()
    assert not [e for e in storage.elenca_eventi(50) if "bz|" in str(e)]                              # nessun rumore nel registro attivita'
    storage.elimina_bozza("mario rossi", "pe")
    assert storage.carica_bozza("mario rossi", "pe") == (None, "")


def test_la_bozza_nasce_solo_se_cambia_qualcosa_e_si_riprende():
    at = _app("pe")
    assert not at.exception and not _bozze()                                    # aprire e basta non scrive niente
    at.run()
    assert not _bozze()
    df = pd.DataFrame([{c: "" for c in __import__("pe").COLONNE_PERSONE}])
    df.loc[0, ["Persona", "Ruolo", "Attivo"]] = ["Anna Verdi", "Geometra", "Sì"]
    at.session_state["pe_pers"] = df
    at.run()
    assert _bozze() == ["bz|pe|admin"]                                          # copia automatica
    nuovo = _app("pe")                                                          # "pagina chiusa e riaperta"
    assert any("lavoro non salvato" in w.value for w in nuovo.warning)
    next(b for b in nuovo.button if b.key == "bz_si_pe").click().run()
    assert not nuovo.exception
    assert "Anna Verdi" in nuovo.session_state["pe_pers"]["Persona"].tolist()
    assert not [w for w in nuovo.warning if "lavoro non salvato" in w.value]


def test_scarta_la_copia_e_il_salvataggio_con_nome_la_toglie():
    at = _app("pe")
    df = pd.DataFrame([{c: "" for c in __import__("pe").COLONNE_PERSONE}])
    df.loc[0, ["Persona", "Ruolo", "Attivo"]] = ["Luca Neri", "Operaio", "Sì"]
    at.session_state["pe_pers"] = df
    at.run()
    nuovo = _app("pe")
    next(b for b in nuovo.button if b.key == "bz_no_pe").click().run()
    assert not _bozze()
    at2 = _app("pe")
    at2.session_state["pe_pers"] = df
    at2.run()
    assert _bozze()
    at2.text_input(key="sv_nome_pe").set_value("Elenco ufficio").run()
    next(b for b in at2.button if b.key == "sv_salva_pe").click().run()
    assert storage.elenca_pratiche(modulo="pe") and not _bozze()                 # salvato con nome: la copia automatica non serve piu'


MODULI = [m for m in permessi.TUTTI if m not in ("credit", "dd", "ch", "ca", "ac", "nv", "sk", "pe")]


@pytest.mark.parametrize("modulo", MODULI)
def test_nessuna_bozza_senza_modifiche(modulo):
    at = _app(modulo)
    assert not at.exception, [e.value for e in at.exception]
    at.run()
    assert not _bozze(), f"{modulo}: scrive bozze anche se nessuno ha cambiato niente"
