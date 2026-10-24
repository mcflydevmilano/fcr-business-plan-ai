import os
import pytest
import auth, backup_db as b, chat, storage


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKUP_KEY", "una-frase-molto-lunga-di-prova")
    monkeypatch.delenv("DATABASE_URL", raising=False); monkeypatch.delenv("CHAT_KEY", raising=False)
    storage.svuota_cache()
    p = str(tmp_path / "a.db")
    auth.crea_utente("mario", "Password12345", "admin", "t", p)
    storage.salva_pratica("P1", {"x": 1}, p, autore="mario", modulo="sc")
    cid = chat.crea_canale("Generale", "pubblico", "mario", path=p)
    chat.invia(cid, "mario", "admin", "ciao", path=p)
    return p


def test_giro_completo(db, tmp_path):
    nome, cont, blob = b.crea(db, str(tmp_path / "bk"), 2)
    assert cont["utenti"] == 1 and cont["pratiche"] >= 1 and cont["chat_canali"] == 1
    assert b"mario" not in blob and b"Password" not in blob                 # cifrato
    assert b.verifica(blob) == cont
    nuovo = str(tmp_path / "n.db")
    b.ripristina(b.apri(blob), nuovo)
    assert auth.autentica("mario", "Password12345", path=nuovo)[0]          # anche le password tornano
    assert storage.carica_pratica("P1", nuovo, modulo="sc") == {"x": 1}


def test_chiave_sbagliata_e_rotazione(db, tmp_path):
    _, _, blob = b.crea(db, str(tmp_path / "bk"), 2)
    with pytest.raises(ValueError):
        b.apri(blob, "un-altra-chiave-sbagliata")
    for _ in range(3):
        b.crea(db, str(tmp_path / "bk"), 2)
    assert len(os.listdir(tmp_path / "bk")) == 2


def test_senza_chiave(db, monkeypatch):
    monkeypatch.delenv("BACKUP_KEY")
    with pytest.raises(ValueError):
        b.cifra({"tabelle": {}})
    assert b.main([]) == 1
