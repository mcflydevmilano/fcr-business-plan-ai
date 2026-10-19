import pytest

import auth
import storage


@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "t.db")


def test_hash_e_verifica():
    h = auth.hash_password("Segreta12345")
    assert h.startswith("pbkdf2_sha256$") and "Segreta12345" not in h
    assert auth.verifica_password("Segreta12345", h)
    assert not auth.verifica_password("segreta12345", h)
    assert auth.hash_password("Segreta12345") != h                      # sale casuale
    assert not auth.verifica_password("x", "formato-non-valido")


def test_regole_password_e_username():
    assert auth.valida_password("corta1") is not None
    assert auth.valida_password("soloLettereLunghe") is not None
    assert auth.valida_password("1234567890123") is not None
    assert auth.valida_password("mario.rossi2026", "mario.rossi") is not None
    assert auth.valida_password("Buona-Password-7") is None
    assert auth.valida_username("Mario Rossi") is not None and auth.valida_username("mario.rossi") is None


def test_login_utente_db_e_revoca(db):
    auth.crea_utente("Luca", "Password-Lunga-1", "utente", da="admin", path=db)
    u, err = auth.autentica("luca", "Password-Lunga-1", path=db)
    assert err is None and u["username"] == "luca" and u["ruolo"] == "utente"
    assert auth.ancora_valido(u, path=db)
    storage.aggiorna_utente("luca", db, attivo=0)                       # revoca
    assert not auth.ancora_valido(u, path=db)
    assert auth.autentica("luca", "Password-Lunga-1", path=db)[0] is None
    with pytest.raises(ValueError):
        auth.crea_utente("luca", "Altra-Password-2", path=db)           # duplicato


def test_login_da_secrets_e_ruolo():
    h = auth.hash_password("Admin-Password-9")
    sec = auth.utenti_da_secrets({"Anna": {"hash": h, "ruolo": "admin"}, "bob": h, "rotto": {"x": 1}})
    assert set(sec) == {"anna", "bob"} and sec["anna"]["ruolo"] == "admin" and sec["bob"]["ruolo"] == "utente"
    u, err = auth.autentica("ANNA", "Admin-Password-9", utenti_secrets=sec, path=":memory:x")
    assert err is None and u["ruolo"] == "admin" and u["origine"] == "secrets"
    assert auth.ancora_valido(u, utenti_secrets=sec) and not auth.ancora_valido(u, utenti_secrets={})


def test_app_password_solo_per_admin_e_solo_se_configurata(db):
    assert auth.autentica("admin", "qualunque", path=db)[0] is None
    u, _ = auth.autentica("admin", "vecchia-password", app_password="vecchia-password", path=db)
    assert u and u["ruolo"] == "admin"
    assert auth.autentica("mario", "vecchia-password", app_password="vecchia-password", path=db)[0] is None


def test_blocco_dopo_troppi_tentativi_e_sblocco(db):
    auth.crea_utente("sara", "Password-Lunga-1", path=db)
    for _ in range(auth.MAX_TENTATIVI):
        u, err = auth.autentica("sara", "sbagliata", path=db)
        assert u is None
    u, err = auth.autentica("sara", "Password-Lunga-1", path=db)         # anche la password giusta e' bloccata
    assert u is None and "Troppi tentativi" in err
    auth.reimposta_password("sara", "Nuova-Password-3", da="admin", path=db)
    u, err = auth.autentica("sara", "Nuova-Password-3", path=db)
    assert err is None and u["username"] == "sara"


def test_messaggio_generico_e_audit(db):
    _, e1 = auth.autentica("inesistente", "xxxxxxxxxxxx", path=db)
    auth.crea_utente("tina", "Password-Lunga-1", path=db)
    _, e2 = auth.autentica("tina", "sbagliata", path=db)
    assert e1 == e2 == "Credenziali non valide."
    azioni = [e["Azione"] for e in storage.elenca_eventi(path=db)]
    assert "login_fallito" in azioni and "utente_creato" in azioni


def test_cambio_password(db):
    auth.crea_utente("gina", "Password-Lunga-1", path=db)
    with pytest.raises(ValueError):
        auth.cambia_password("gina", "errata", "Nuova-Password-3", path=db)
    with pytest.raises(ValueError):
        auth.cambia_password("gina", "Password-Lunga-1", "corta", path=db)
    auth.cambia_password("gina", "Password-Lunga-1", "Nuova-Password-3", path=db)
    assert auth.autentica("gina", "Nuova-Password-3", path=db)[0]
    assert auth.autentica("gina", "Password-Lunga-1", path=db)[0] is None


def test_pratiche_registrano_l_autore(db):
    storage.salva_pratica("P1", {"a": 1}, db, autore="luca")
    assert storage.elenca_pratiche(db)[0]["autore"] == "luca"
