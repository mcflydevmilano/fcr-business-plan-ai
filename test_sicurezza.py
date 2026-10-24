import time
import pytest
import auth, storage, due_passaggi as d


def test_vettore_rfc6238():
    assert d.codice("GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ", 59) == "287082"


def test_attiva_verifica_emergenza(tmp_path, monkeypatch):
    monkeypatch.delenv("CHAT_KEY", raising=False); monkeypatch.delenv("DUEPASSAGGI_KEY", raising=False)
    db = str(tmp_path / "x.db")
    s = d.nuovo_segreto()
    with pytest.raises(ValueError):
        d.attiva("mario", s, "000000", path=db)
    em = d.attiva("mario", s, d.codice(s), path=db)
    assert len(em) == 8 and d.attivo("mario", db)
    assert d.verifica_login("mario", d.codice(s), db) is None            # lo stesso codice non vale due volte
    assert d.verifica_login("mario", em[0], db) == "emergenza"
    assert d.verifica_login("mario", em[0], db) is None                  # monouso
    assert d.codici_emergenza_rimasti("mario", db) == 7
    assert d.disattiva("mario", "admin", db) and not d.attivo("mario", db)


def test_segreto_cifrato(tmp_path, monkeypatch):
    monkeypatch.setenv("CHAT_KEY", "chiave-di-prova")
    db = str(tmp_path / "x.db")
    s = d.nuovo_segreto()
    d.attiva("anna", s, d.codice(s), path=db)
    assert s not in str(storage.carica_pratica(d.NOME_CFG, db, modulo="cfg"))


def test_obbligo_admin(tmp_path):
    db = str(tmp_path / "x.db")
    u = {"username": "boss", "ruolo": "admin"}
    assert not d.deve_configurare(u, db)
    d.imposta_obbligatorio_admin(True, "boss", db)
    assert d.deve_configurare(u, db) and not d.deve_configurare({"username": "x", "ruolo": "utente"}, db)


def test_blocco_codici_e_scadenza(tmp_path):
    db = str(tmp_path / "x.db")
    for _ in range(auth.MAX_TENTATIVI):
        storage.log_evento("mario", "2fa_fallito", "", db)
    assert auth.bloccato_2fa("mario", db) and not auth.bloccato_2fa("altro", db)
    auth.crea_utente("luca", "Password12345", path=db)
    u = {"username": "luca", "origine": "db"}
    assert auth.giorni_a_scadenza_password(u, 180, db) in (179, 180)
    assert auth.giorni_a_scadenza_password(u, 0, db) is None
    assert auth.giorni_a_scadenza_password({"username": "s", "origine": "secrets"}, 180, db) is None
    with pytest.raises(ValueError):
        auth.cambia_password_scaduta("luca", "Password12345", "Password12345", db)


def _login(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setenv("FCR_DB_PATH", str(tmp_path / "ui.db"))
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "ui.db"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CHAT_KEY", raising=False)
    storage.svuota_cache()
    at = AppTest.from_file("app.py", default_timeout=90).run()
    at.text_input(key="login_user").set_value("admin")
    at.text_input(key="login_pw").set_value("segreta")
    at.button[0].click().run()
    return at


def test_login_con_due_passaggi(tmp_path, monkeypatch):
    at = _login(tmp_path, monkeypatch)
    assert not at.exception and at.session_state["utente"]["username"] == "admin"
    s = d.nuovo_segreto()
    d.attiva("admin", s, d.codice(s), "admin")
    from streamlit.testing.v1 import AppTest
    storage.svuota_cache()
    at = AppTest.from_file("app.py", default_timeout=90).run()
    at.text_input(key="login_user").set_value("admin")
    at.text_input(key="login_pw").set_value("segreta")
    at.button[0].click().run()
    assert "utente" not in at.session_state and at.session_state["_2fa_attesa"]["username"] == "admin"
    at.text_input(key="login_2fa_codice").set_value("000000")
    at.button[0].click().run()
    assert "utente" not in at.session_state
    at.text_input(key="login_2fa_codice").set_value(d.codice(s, time.time() + 30))       # passo successivo, non ancora usato
    at.button[0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["utente"]["username"] == "admin"


def test_admin_deve_configurare_i_due_passaggi(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setenv("FCR_DB_PATH", str(tmp_path / "ob.db"))
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "ob.db"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    storage.svuota_cache()
    d.imposta_obbligatorio_admin(True, "x")
    at = AppTest.from_file("app.py", default_timeout=90).run()
    at.text_input(key="login_user").set_value("admin")
    at.text_input(key="login_pw").set_value("segreta")
    at.button[0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("obbligatoria la verifica in due passaggi" in w.value for w in at.warning)
    seg = at.session_state["_2fa_segreto"]
    at.text_input[0].set_value(d.codice(seg))
    [b for b in at.button if b.label == "Attiva"][0].click().run()
    assert at.session_state["_2fa_codici"] and d.attivo("admin")
