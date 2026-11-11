"""pannello_archivio: apertura automatica dell'ultimo salvataggio (AppTest, senza chiamate a Gemini)."""
import os
import tempfile

import pytest
from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")


def _sessione(db_path, modulo, chiave=False):
    """Una «sessione» nuova (come un collega che apre l'app in un altro momento), sullo stesso database."""
    app = AppTest.from_file(APP, default_timeout=120)
    app.session_state["utente"] = {"username": "tester", "ruolo": "admin", "origine": "app_password"}
    app.session_state["active_module"] = modulo
    return app.run()


@pytest.fixture
def db(monkeypatch):
    import storage
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    path = os.path.join(tmp, "t.db")
    monkeypatch.setattr(storage, "DB_PATH", path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    return path


def test_apre_da_solo_l_ultimo_salvataggio_senza_cliccare_apri(db):
    """Dopo un salvataggio, una sessione nuova sullo stesso strumento parte gia' con quei dati: non serve «Apri»."""
    at = _sessione(db, "sl")
    at.number_input(key="sl_gg_pagamento").set_value(45).run()
    at.text_input(key="sv_nome_sl").set_value("Lavori").run()
    at.button(key="sv_salva_sl").click().run()
    assert not at.exception

    at2 = _sessione(db, "sl")                               # sessione nuova: nessun clic su "Apri"
    assert not at2.exception
    assert at2.number_input(key="sl_gg_pagamento").value == 45
    assert len(at2.session_state["sl_com"]) == 3             # anche la tabella delle commesse e' quella salvata, non l'esempio


def test_apre_il_piu_recente_tra_piu_salvataggi_e_si_puo_ancora_cambiare(db):
    at = _sessione(db, "sl")
    at.number_input(key="sl_gg_pagamento").set_value(30).run()
    at.text_input(key="sv_nome_sl").set_value("Vecchio").run()
    at.button(key="sv_salva_sl").click().run()
    at.number_input(key="sl_gg_pagamento").set_value(60).run()
    at.text_input(key="sv_nome_sl").set_value("Nuovo").run()
    at.button(key="sv_salva_sl").click().run()

    at2 = _sessione(db, "sl")
    assert at2.number_input(key="sl_gg_pagamento").value == 60          # il piu' recente, da solo

    at2.selectbox(key="sv_scelta_sl").set_value("Vecchio").run()        # ma si puo' ancora passare a un altro salvataggio
    at2.button(key="sv_apri_sl").click().run()
    assert not at2.exception and at2.number_input(key="sl_gg_pagamento").value == 30


def test_senza_salvataggi_parte_come_prima_vuoto_o_demo(db):
    at = _sessione(db, "sl")
    assert not at.exception
    assert "_base_sl" not in at.session_state                           # niente da aprire: nessuna apertura automatica


def test_organico_non_apre_in_automatico_una_copia_con_nome(db):
    """Organico ha un elenco unico aziendale con caricamento automatico suo: il pannello «copia di sicurezza con nome»
    non deve sovrascriverlo in automatico con una copia qualunque (auto_apri=False)."""
    at = _sessione(db, "og")
    at.text_input(key="sv_nome_og").set_value("Copia di prova").run()
    at.button(key="sv_salva_og").click().run()
    assert not at.exception

    at2 = _sessione(db, "og")
    assert not at2.exception
    assert "_base_og" not in at2.session_state                          # non aperta in automatico
