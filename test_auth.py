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
    assert auth.valida_username("mario rossi") is None and auth.valida_username("mario.rossi") is None
    assert auth.valida_username("mario  ") is not None and auth.valida_username("ma") is not None and auth.valida_username("mario/rossi") is not None


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


def test_nome_con_spazio_e_password_provvisoria(db):
    assert auth.nome_da_testo("  Mario ", "ROSSI") == "mario rossi" and auth.mostra_nome("mario rossi") == "Mario Rossi"
    tmp = auth.genera_password_temporanea()
    auth.crea_utente(auth.nome_da_testo("Mario", "Rossi"), tmp, "utente", "admin", db, email="mario@fcrgeneralcontractor.eu", cambio_pw=True)
    u, err = auth.autentica("Mario  Rossi", tmp, path=db)
    assert u and u["username"] == "mario rossi"
    assert auth.deve_cambiare_password(u, db)
    assert storage.utente_db("mario rossi", db)["email"] == "mario@fcrgeneralcontractor.eu"
    auth.cambia_password("mario rossi", tmp, "Mia-Password-77", db)
    assert not auth.deve_cambiare_password(u, db)
    with pytest.raises(ValueError):
        auth.crea_utente("luca bianchi", "Password-Lunga-1", email="non-una-mail", path=db)


def test_rinomina_utente_riporta_il_nome_ovunque(db):
    auth.crea_utente("mario rosi", "Password-Lunga-1", "utente", "admin", db)
    storage.aggiungi_timbratura("mario rosi", "entrata", "rete", path=db)
    storage.log_evento("mario rosi", "x", "", db)
    auth.crea_utente("anna verdi", "Password-Lunga-1", "utente", "admin", db)
    with pytest.raises(ValueError):
        auth.rinomina_utente("mario rosi", "anna verdi", "admin", path=db)
    with pytest.raises(ValueError):
        auth.rinomina_utente("mario rosi", "mario rosi", "admin", path=db)
    auth.rinomina_utente("mario rosi", "Mario Rossi", "admin", path=db)
    assert storage.utente_db("mario rosi", db) is None and storage.utente_db("mario rossi", db)
    assert [t["utente"] for t in storage.elenca_timbrature(path=db)] == ["mario rossi"]
    u, _ = auth.autentica("mario rossi", "Password-Lunga-1", path=db)
    assert u


def test_rinomina_sposta_chat_e_permessi(db):
    import chat, permessi
    auth.crea_utente("mario rosi", "Password-Lunga-1", "utente", "admin", db)
    auth.crea_utente("anna verdi", "Password-Lunga-1", "utente", "admin", db)
    cid = chat.canale_diretto("anna verdi", "mario rosi", db)
    cfg = permessi.carica_config(db)
    cfg["utenti"]["mario rosi"] = list(cfg["profili"])[0]
    permessi.salva_config(cfg, "admin", db)
    auth.rinomina_utente("mario rosi", "mario rossi", "admin", path=db)
    assert chat.canale_diretto("anna verdi", "mario rossi", db) == cid
    assert "mario rossi" in permessi.carica_config(db)["utenti"] and "mario rosi" not in permessi.carica_config(db)["utenti"]


def test_testo_email_accesso():
    import admin_ui
    ogg, corpo = admin_ui.testo_accesso("mario rossi", "Abc123xyz789", True)
    assert "Abc123xyz789" in corpo and "Ciao Mario," in corpo and "password tua" in corpo and ogg


def test_rinomina_aggiorna_anche_persone_e_ruoli(db):
    import onboarding
    import pe
    esito = onboarding.crea_account("mario rosi", "", "utente", "cantiere", "admin", db)
    assert esito["utente"] == "mario rosi" and not esito["inviata"] and storage.utente_db("mario rosi", db)["cambio_pw"] == 1
    import permessi
    assert permessi.carica_config(db)["utenti"]["mario rosi"] == "cantiere"
    storage.salva_pratica("elenco", {"persone": [{"Persona": "Mario Rossi", "Ruolo": "Geometra", "Utente": "mario rosi"}]}, db, autore="x", modulo="pe")
    auth.rinomina_utente("mario rosi", "mario rossi", "admin", path=db)
    assert pe.persone_salvate(db)[0]["Utente"] == "mario rossi"
    ogg, corpo = onboarding.testo_accesso("mario rossi", "Abc123xyz789", True, strumenti=["Chat interna", "Rapportini"])
    assert "Chat interna, Rapportini" in corpo
    with pytest.raises(ValueError):
        onboarding.crea_account("anna bianchi", "non-una-mail", "utente", "cantiere", "admin", db)
    with pytest.raises(ValueError):
        onboarding.crea_account("anna bianchi", "", "utente", "profilo-inesistente", "admin", db)
