"""Test della chat interna: canali, riservatezza, non letti, cifratura, allegati, avvisi (rete simulata) e schermata."""
import io
import json
import os

import pytest

import chat
import notifiche
import storage


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.delenv("CHAT_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    p = str(tmp_path / "c.db")
    storage.svuota_cache()
    return p


ADM = {"username": "admin", "ruolo": "admin"}
MARIO = {"username": "mario", "ruolo": "utente"}
LUCA = {"username": "luca", "ruolo": "utente"}
LET = {"username": "lea", "ruolo": "lettore"}


def test_canale_pubblico_visibile_a_tutti_e_non_letti(db):
    cid = chat.crea_canale("Generale", "pubblico", "admin", path=db)
    assert [c["nome"] for c in chat.canali_visibili("mario", db)] == ["Generale"]
    chat.invia(cid, "luca", "utente", "ciao a tutti", path=db)
    assert chat.canali_visibili("mario", db)[0]["non_letti"] == 1       # primo accesso: la storia vecchia non conta, ma il nuovo si
    assert chat.canali_visibili("luca", db)[0]["non_letti"] == 0        # i propri messaggi non sono "non letti"
    chat.segna_letti(cid, "mario", chat.ultimo_id(cid, db), db)
    assert chat.non_letti_totale("mario", db) == 0


def test_nome_duplicato_e_non_valido(db):
    chat.crea_canale("Generale", "pubblico", "admin", path=db)
    with pytest.raises(ValueError):
        chat.crea_canale("generale", "pubblico", "admin", path=db)
    with pytest.raises(ValueError):
        chat.crea_canale("a", "pubblico", "admin", path=db)
    with pytest.raises(ValueError):
        chat.crea_canale("dm:x", "pubblico", "admin", path=db)


def test_chat_diretta_e_riservata_anche_agli_admin(db):
    cid = chat.canale_diretto("mario", "luca", db)
    assert chat.canale_diretto("luca", "mario", db) == cid                 # stessa chat, qualunque ordine
    chat.invia(cid, "mario", "utente", "segreto", path=db)
    assert chat.messaggi(cid, "luca", path=db)[0]["testo"] == "segreto"
    with pytest.raises(PermissionError):
        chat.messaggi(cid, "admin", path=db)                               # nessun amministratore legge le chat dirette
    with pytest.raises(PermissionError):
        chat.invia(cid, "admin", "admin", "intrusione", path=db)
    assert chat.canali_visibili("admin", db) == []
    assert all(c["tipo"] != "diretto" for c in chat.tutti_i_canali_gestibili(db))
    with pytest.raises(PermissionError):
        chat.esporta_canale(cid, ADM, db)
    assert chat.canali_visibili("mario", db)[0]["etichetta"] == "luca"
    assert chat.canali_visibili("luca", db)[0]["etichetta"] == "mario"


def test_gruppo_privato_solo_membri(db):
    cid = chat.crea_canale("Gara Roma", "privato", "mario", ["luca"], path=db)
    chat.invia(cid, "luca", "utente", "ok", path=db)
    assert [c["nome"] for c in chat.canali_visibili("mario", db)] == ["Gara Roma"]
    assert chat.canali_visibili("admin", db) == []
    with pytest.raises(PermissionError):
        chat.messaggi(cid, "admin", path=db)
    with pytest.raises(PermissionError):
        chat.esporta_canale(cid, ADM, db)
    # l'admin vede il nome nell'elenco di gestione ma non i messaggi
    assert any(c["nome"] == "Gara Roma" for c in chat.tutti_i_canali_gestibili(db))


def test_lettore_non_scrive(db):
    cid = chat.crea_canale("Generale", "pubblico", "admin", path=db)
    with pytest.raises(PermissionError):
        chat.invia(cid, "lea", "lettore", "ciao", path=db)
    assert not chat.puo_scrivere(LET)


def test_cifratura_chat_dirette_e_non_pubblici(db, monkeypatch):
    monkeypatch.setenv("CHAT_KEY", "una-chiave-lunga-e-segreta")
    pub = chat.crea_canale("Generale", "pubblico", "admin", path=db)
    dm = chat.canale_diretto("mario", "luca", db)
    chat.invia(pub, "mario", "utente", "pubblico in chiaro", path=db)
    chat.invia(dm, "mario", "utente", "SEGRETISSIMO", path=db)
    with storage._db(db) as con:
        grezzi = dict(con.execute("SELECT canale_id, testo FROM chat_messaggi").fetchall())
    assert grezzi[pub] == "pubblico in chiaro"
    assert grezzi[dm].startswith("enc:") and "SEGRETISSIMO" not in grezzi[dm]
    assert chat.messaggi(dm, "luca", path=db)[0]["testo"] == "SEGRETISSIMO"
    monkeypatch.setenv("CHAT_KEY", "altra-chiave")
    assert "altra chiave" in chat.messaggi(dm, "luca", path=db)[0]["testo"]
    monkeypatch.delenv("CHAT_KEY")
    assert "manca la chiave" in chat.messaggi(dm, "luca", path=db)[0]["testo"]


def test_allegati_foto_ridotta_pdf_e_rifiuti(db):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4000, 3000), (200, 30, 30)).save(buf, "PNG")
    nome, tipo, b64 = chat.prepara_allegato("foto.png", buf.getvalue())
    import base64
    im = Image.open(io.BytesIO(base64.b64decode(b64)))
    assert nome == "foto.jpg" and tipo == "image/jpeg" and max(im.size) == chat.LIMITE_FOTO_PX
    assert chat.prepara_allegato("a.pdf", b"%PDF-1.4 x")[1] == "application/pdf"
    with pytest.raises(ValueError):
        chat.prepara_allegato("a.pdf", b"non e un pdf")
    with pytest.raises(ValueError):
        chat.prepara_allegato("a.pdf", b"%PDF" + b"0" * (chat.LIMITE_PDF_MB * 1024 * 1024))
    with pytest.raises(ValueError):
        chat.prepara_allegato("virus.exe", b"MZ")
    cid = chat.canale_diretto("mario", "luca", db)
    chat.invia(cid, "mario", "utente", "", ("doc.pdf", b"%PDF-1.4 ciao"), path=db)
    m = chat.messaggi(cid, "luca", path=db)[0]
    assert m["allegato"] == b"%PDF-1.4 ciao" and m["allegato_nome"] == "doc.pdf"


def test_messaggio_vuoto_e_troppo_lungo(db):
    cid = chat.canale_diretto("mario", "luca", db)
    with pytest.raises(ValueError):
        chat.invia(cid, "mario", "utente", "   ", path=db)
    with pytest.raises(ValueError):
        chat.invia(cid, "mario", "utente", "x" * (chat.MAX_TESTO + 1), path=db)
    chat.invia(cid, "mario", "utente", "", link=("of", "Condominio Rossi"), path=db)       # un collegamento basta
    assert chat.messaggi(cid, "luca", path=db)[0]["link_modulo"] == "of"


def test_eliminazione_moderazione_e_archivio(db):
    cid = chat.crea_canale("Generale", "pubblico", "admin", path=db)
    m = chat.invia(cid, "mario", "utente", "brutto", path=db)["id"]
    with pytest.raises(PermissionError):
        chat.elimina_messaggio(m, LUCA, db)
    chat.elimina_messaggio(m, ADM, db)                                      # l'admin modera i canali pubblici
    assert chat.messaggi(cid, "luca", path=db)[0]["eliminato"] and chat.messaggi(cid, "luca", path=db)[0]["testo"] == ""
    dm = chat.canale_diretto("mario", "luca", db)
    m2 = chat.invia(dm, "mario", "utente", "x", path=db)["id"]
    with pytest.raises(PermissionError):
        chat.elimina_messaggio(m2, ADM, db)                                 # ma non i messaggi privati
    chat.archivia_canale(cid, True, db)
    assert chat.canali_visibili("mario", db) == [c for c in chat.canali_visibili("mario", db) if c["tipo"] == "diretto"]
    with pytest.raises(PermissionError):
        chat.invia(cid, "mario", "utente", "ancora", path=db)
    with pytest.raises(ValueError):
        chat.archivia_canale(dm, True, db)


def test_gestori_e_esportazione(db):
    chat.crea_canale("Generale", "pubblico", "admin", path=db)
    cfg = chat.carica_cfg(db)
    assert chat.e_gestore(ADM, cfg) and not chat.e_gestore(MARIO, cfg)
    chat.salva_cfg({"gestori": ["Mario"]}, "admin", db)
    storage.svuota_cache()
    assert chat.e_gestore(MARIO, chat.carica_cfg(db))
    cid = chat.canali_visibili("mario", db)[0]["id"]
    chat.invia(cid, "luca", "utente", "ciao", path=db)
    assert "luca: ciao" in chat.esporta_canale(cid, ADM, db)
    with pytest.raises(PermissionError):
        chat.esporta_canale(cid, LUCA, db)


def test_pulizia_per_conservazione(db):
    cid = chat.canale_diretto("mario", "luca", db)
    chat.invia(cid, "mario", "utente", "vecchio", path=db)
    chat.invia(cid, "mario", "utente", "nuovo", path=db)
    with storage._db(db) as con:
        con.execute("UPDATE chat_messaggi SET ts='2020-01-01 00:00:00' WHERE testo='vecchio'")
    assert chat.pulisci(24, db) == 1
    assert [m["testo"] for m in chat.messaggi(cid, "luca", path=db)] == ["nuovo"]
    with pytest.raises(ValueError):
        chat.pulisci(0, db)


def test_menzioni_e_destinatari(db):
    assert chat.menzioni("ciao @Luca e @sconosciuto", ["luca", "mario"]) == {"luca"}
    pub = chat.crea_canale("Generale", "pubblico", "admin", path=db)
    dm = chat.canale_diretto("mario", "luca", db)
    chat.salva_prefs("luca", db, telegram_chat_id="111", modo="menzioni")
    chat.salva_prefs("lea", db, ntfy_topic="top", modo="tutto")
    chat.salva_prefs("zeno", db, telegram_chat_id="999", modo="niente")
    assert [d["username"] for d in chat.destinatari_avviso(dm, "mario", set(), db)] == ["luca"]
    assert [d["username"] for d in chat.destinatari_avviso(pub, "mario", set(), db)] == ["lea"]          # luca vuole solo menzioni
    assert sorted(d["username"] for d in chat.destinatari_avviso(pub, "mario", {"luca"}, db)) == ["lea", "luca"]
    assert chat.destinatari_avviso(pub, "lea", set(), db) == []                                         # l'autore non si avvisa
    priv = chat.crea_canale("Privato", "privato", "mario", ["luca"], path=db)
    assert chat.destinatari_avviso(priv, "mario", set(), db) == []                                      # luca vuole solo menzioni; lea non e' membro
    assert [d["username"] for d in chat.destinatari_avviso(priv, "mario", {"luca"}, db)] == ["luca"]


def test_silenzio_notturno(db):
    p = {"silenzio_da": "20:00", "silenzio_a": "07:30"}
    assert chat.in_silenzio(p, "23:00") and chat.in_silenzio(p, "06:00") and not chat.in_silenzio(p, "12:00")
    assert not chat.in_silenzio({"silenzio_da": "", "silenzio_a": ""}, "23:00")
    dm = chat.canale_diretto("mario", "luca", db)
    chat.salva_prefs("luca", db, telegram_chat_id="1", silenzio_da="20:00", silenzio_a="07:30")
    assert chat.destinatari_avviso(dm, "mario", set(), db, adesso="22:00") == []
    assert len(chat.destinatari_avviso(dm, "mario", set(), db, adesso="10:00")) == 1


def test_avvisi_senza_testo_del_messaggio(db, monkeypatch):
    chiamate = []
    monkeypatch.setattr(notifiche, "HTTP", lambda url, dati=None, intest=None, timeout=6: (chiamate.append((url, dati, intest)) or (200, "{}")))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOK")
    monkeypatch.setenv("APP_URL", "https://suite.example")
    dm = chat.canale_diretto("mario", "luca", db)
    chat.salva_prefs("luca", db, telegram_chat_id="111", ntfy_topic="fcr-abc")
    info = chat.invia(dm, "mario", "utente", "PASSWORD DEL SERVER 1234", path=db)
    assert notifiche.avvisa(info, "mario", "PASSWORD DEL SERVER 1234", ["mario", "luca"], db, sincrono=True) == 1
    assert len(chiamate) == 2
    tg = next(c for c in chiamate if "api.telegram.org/botTOK/sendMessage" in c[0])
    nt = next(c for c in chiamate if "ntfy.sh/fcr-abc" in c[0])
    assert json.loads(tg[1])["chat_id"] == "111" and "mario" in json.loads(tg[1])["text"] and "https://suite.example" in json.loads(tg[1])["text"]
    assert all(b"PASSWORD" not in (c[1] or b"") for c in chiamate)
    assert nt[2]["Click"] == "https://suite.example"


def test_collegamento_telegram(db, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOK")
    cod = chat.nuovo_codice_telegram("luca", db)
    inviati = []

    def finto(url, dati=None, intest=None, timeout=6):
        if url.endswith("getMe"):
            return 200, json.dumps({"result": {"username": "FcrBot"}})
        if "getUpdates" in url:
            return 200, json.dumps({"result": [{"message": {"text": "/start altro", "chat": {"id": 5}}},
                                               {"message": {"text": f"/start {cod}", "chat": {"id": 777}}}]})
        inviati.append(url)
        return 200, "{}"
    monkeypatch.setattr(notifiche, "HTTP", finto)
    assert notifiche.link_telegram(cod) == f"https://t.me/FcrBot?start={cod}"
    assert notifiche.collega_telegram("luca", db)
    p = chat.prefs("luca", db)
    assert p["telegram_chat_id"] == "777" and p["telegram_codice"] == ""
    assert not notifiche.collega_telegram("mario", db)
    chat.scollega_avvisi("luca", db)
    assert chat.prefs("luca", db)["telegram_chat_id"] == ""


def test_topic_ntfy_casuale(db):
    a, b = chat.nuovo_topic_ntfy("luca", db), chat.nuovo_topic_ntfy("mario", db)
    assert a != b and a.startswith("fcr-") and len(a) > 16


def test_chat_e_collegata_ai_permessi_e_all_hub():
    import hub
    import permessi
    assert "ch" in permessi.TUTTI and "ch" in hub.CARDS
    for nome, mod in permessi.PROFILI_BASE.items():
        assert "ch" in mod, nome
    assert any("ch" in g[2] for g in hub.GRUPPI)
    assert hub.numero("ch").startswith("Strumento")


# ---- schermata ----
def _app(tmp_path, monkeypatch, nome="ui.db"):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setenv("FCR_DB_PATH", str(tmp_path / nome))
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / nome))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    storage.svuota_cache()
    at = AppTest.from_file("app.py", default_timeout=90).run()
    at.text_input(key="login_user").set_value("admin")
    at.text_input(key="login_pw").set_value("segreta")
    at.button[0].click().run()
    at.session_state["active_module"] = "ch"
    at.run()
    return at


def test_schermata_chat_si_apre_e_si_scrive(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    assert not at.exception, [e.value for e in at.exception]
    cid = [c for c in chat.canali_visibili("admin") if c["nome"] == "Generale"][0]["id"]      # creato da solo alla prima apertura
    at.run()
    assert any("Generale" in b.label for b in at.button) and any("Cantieri" in b.label for b in at.button)
    [b for b in at.button if "Generale" in b.label][0].click().run()
    at.text_area(key="chat_testo").set_value("Buongiorno a tutti")
    [b for b in at.button if b.label == "Invia"][0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert chat.messaggi(cid, "admin")[-1]["testo"] == "Buongiorno a tutti"
    assert any("Buongiorno a tutti" in m.value for m in at.markdown)


def test_schermata_gestione_solo_per_chi_gestisce(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch, "ui2.db")
    assert any("Gestione" in t.label for t in at.tabs)
    assert any("Privacy" in t.label for t in at.tabs)
    assert any("Avvisi sul telefono" in t.label for t in at.tabs)


def test_badge_non_letti_nella_barra_laterale(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch, "ui3.db")
    dm = chat.canale_diretto("mario", "admin")
    chat.invia(dm, "mario", "utente", "ciao admin")
    storage.svuota_cache()
    at.session_state["active_module"] = None
    at.run()
    assert any(b.label.startswith("💬  Chat interna") and "🔴 1" in b.label for b in at.button)


def test_canali_iniziali_una_sola_volta(db):
    n = chat.crea_canali_iniziali("admin", path=db)
    assert n == len(chat.CANALI_INIZIALI) >= 8
    assert chat.crea_canali_iniziali("admin", path=db) == 0                     # non si ricreano
    cid = [c for c in chat.canali_visibili("mario", db) if c["nome"] == "Sicurezza"][0]["id"]
    chat.archivia_canale(cid, True, db)
    assert chat.crea_canali_iniziali("admin", path=db) == 0                     # un canale archiviato non ricompare
    assert chat.crea_canali_iniziali("admin", solo_se_vuoto=False, path=db) == 0  # il nome esiste ancora: nessun doppione


def test_avatar_usa_la_foto_profilo():
    import chat_ui
    foto = {"mario": {"jpg": "QUJD"}}
    assert chat_ui._avatar("Mario", foto) == "data:image/jpeg;base64,QUJD"       # nome scritto in modo diverso: stessa persona
    assert chat_ui._avatar("luca", foto) == "🧑‍💼"                               # senza foto: icona


# ---- risposte, modifica, reazioni, conferme, ricerca, compiti ----
def test_risposta_citazione_e_modifica(db, monkeypatch):
    monkeypatch.setenv("CHAT_KEY", "chiave-di-prova")
    dm = chat.canale_diretto("mario", "luca", db)
    a = chat.invia(dm, "mario", "utente", "Hai il computo?", path=db)["id"]
    b = chat.invia(dm, "luca", "utente", "Si, te lo mando", path=db, risposta_a=a)["id"]
    m = chat.messaggi(dm, "mario", path=db)[-1]
    assert m["risposta_a"]["autore"] == "mario" and m["risposta_a"]["testo"] == "Hai il computo?"
    other = chat.canale_diretto("mario", "zeno", db)
    with pytest.raises(ValueError):
        chat.invia(other, "mario", "utente", "x", path=db, risposta_a=a)           # non si risponde a un messaggio di un altro canale
    with pytest.raises(PermissionError):
        chat.modifica_messaggio(a, LUCA, "falso", db)
    chat.modifica_messaggio(a, MARIO, "Hai il computo aggiornato?", db)
    with storage._db(db) as con:
        assert con.execute("SELECT testo FROM chat_messaggi WHERE id=?", (a,)).fetchone()[0].startswith("enc:")      # resta cifrato
    primo = chat.messaggi(dm, "luca", path=db)[0]
    assert primo["testo"] == "Hai il computo aggiornato?" and primo["modificato"]


def test_reazioni_e_conferma_di_lettura(db):
    cid = chat.crea_canale("Cantiere Roma", "privato", "mario", ["luca", "lea"], path=db)
    mid = chat.invia(cid, "mario", "utente", "Domani stop lavori", path=db, importante=True)["id"]
    assert chat.reagisci(mid, "luca", "👍", db) is True
    assert chat.reagisci(mid, "luca", "👍", db) is False                         # secondo clic toglie
    chat.reagisci(mid, "lea", "👍", db)
    with pytest.raises(ValueError):
        chat.reagisci(mid, "luca", "💣", db)
    with pytest.raises(PermissionError):
        chat.reagisci(mid, "admin", "👍", db)                                    # non e' un suo canale
    chat.conferma_lettura(mid, "luca", db)
    chat.conferma_lettura(mid, "luca", db)
    m = chat.messaggi(cid, "mario", path=db)[0]
    assert m["reazioni"] == {"👍": ["lea"]} and m["confermato_da"] == ["luca"] and m["da_confermare"] == ["lea"]


def test_ricerca_rispetta_i_permessi_e_decifra(db, monkeypatch):
    monkeypatch.setenv("CHAT_KEY", "k")
    pub = chat.crea_canale("Generale", "pubblico", "admin", path=db)
    dm = chat.canale_diretto("mario", "luca", db)
    chat.invia(pub, "mario", "utente", "Preventivo condominio Rossi", path=db)
    chat.invia(dm, "mario", "utente", "Il preventivo riservato per Bianchi", path=db)
    chat.invia(dm, "luca", "utente", "", ("computo.pdf", b"%PDF-1.4 x"), path=db)
    assert len(chat.cerca("mario", "preventivo", path=db)) == 2
    assert len(chat.cerca("admin", "preventivo", path=db)) == 1                  # l'admin non trova nulla nelle chat dirette
    assert chat.cerca("admin", "Bianchi", path=db) == []
    assert [r["allegato_nome"] for r in chat.cerca("luca", solo_allegati=True, path=db)] == ["computo.pdf"]
    assert chat.cerca("mario", "", path=db) == []
    assert [r["autore"] for r in chat.cerca("mario", autore="luca", path=db)] == ["luca"]


def test_compiti_dalla_chat_e_calendario(db):
    import calendario
    cid = chat.crea_canale("Cantiere Roma", "privato", "mario", ["luca"], path=db)
    mid = chat.invia(cid, "mario", "utente", "Serve il DURC", path=db)["id"]
    with pytest.raises(PermissionError):
        chat.crea_compito(mid, MARIO, "Chiedere il DURC", "zeno", "2026-11-05", db)     # zeno non legge il canale
    with pytest.raises(ValueError):
        chat.crea_compito(mid, MARIO, "Chiedere il DURC", "luca", "domani", db)
    tid = chat.crea_compito(mid, MARIO, "Chiedere il DURC", "luca", "2026-11-05", db)
    assert [t["titolo"] for t in chat.compiti("luca", path=db)] == ["Chiedere il DURC"]
    assert chat.compiti("mario", path=db) == [] and len(chat.compiti("mario", tutti=True, path=db)) == 1
    ev = calendario.eventi({"ch": {"compiti": chat.compiti("luca", path=db)}}, "2026-11-01", 60)
    assert ev[0]["Categoria"] == "Compito" and ev[0]["Data"].isoformat() == "2026-11-05"
    with pytest.raises(PermissionError):
        chat.chiudi_compito(tid, {"username": "admin", "ruolo": "admin"}, db)
    chat.chiudi_compito(tid, LUCA, db)
    assert chat.compiti("luca", path=db) == []


def test_database_vecchio_si_aggiorna(tmp_path, monkeypatch):
    import sqlite3
    monkeypatch.delenv("DATABASE_URL", raising=False)
    p = str(tmp_path / "vecchio.db")
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE chat_messaggi (id INTEGER PRIMARY KEY AUTOINCREMENT, canale_id INTEGER, autore TEXT, ts TEXT, testo TEXT, cifrato INTEGER DEFAULT 0, "
                "allegato_nome TEXT, allegato_tipo TEXT, allegato_dati TEXT, link_modulo TEXT, link_etichetta TEXT, eliminato INTEGER DEFAULT 0)")
    con.commit(); con.close()
    chat._PRONTO.clear()
    storage.svuota_cache()
    cid = chat.crea_canale("Generale", "pubblico", "admin", path=p)
    chat.invia(cid, "mario", "utente", "dopo l'aggiornamento", path=p, importante=True)
    assert chat.messaggi(cid, "luca", path=p)[0]["importante"]


def test_schermata_conversazione_ricca_senza_errori(tmp_path, monkeypatch):
    """Messaggio importante, risposta, reazioni e allegato insieme: nessun pulsante con la stessa chiave."""
    at = _app(tmp_path, monkeypatch, "ricca.db")
    cid = [c for c in chat.canali_visibili("admin") if c["nome"] == "Generale"][0]["id"]
    a = chat.invia(cid, "mario", "utente", "Domani riunione", path=None, importante=True)["id"]
    chat.invia(cid, "luca", "utente", "Ricevuto", risposta_a=a)
    chat.invia(cid, "admin", "admin", "Ok", importante=True)
    chat.reagisci(a, "luca", "👍")
    chat.invia(cid, "mario", "utente", "", ("doc.pdf", b"%PDF-1.4 x"))
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any(b.label == "✔ Confermo di aver letto" for b in at.button)
    [b for b in at.button if b.label == "✔ Confermo di aver letto"][0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert chat.messaggi(cid, "admin")[0]["confermato_da"] == ["admin"]


def test_schermata_cerca_e_compiti(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch, "cerca.db")
    cid = [c for c in chat.canali_visibili("admin") if c["nome"] == "Cantieri"][0]["id"]
    mid = chat.invia(cid, "mario", "utente", "Serve il DURC della ditta Rossi")["id"]
    chat.crea_compito(mid, {"username": "admin", "ruolo": "admin"}, "Chiedere il DURC", "admin", "2026-12-01")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    at.text_input(key="chat_cerca_t").set_value("durc").run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Serve il DURC" in m.value for m in at.markdown)
    assert any("Chiedere il DURC" in m.value for m in at.markdown)               # scheda Compiti
    [b for b in at.button if b.label == "Fatto"][0].click().run()
    assert chat.compiti("admin") == []


def test_aggiornamento_manuale_e_automatico_a_scelta(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch, "agg.db")
    assert not at.exception, [e.value for e in at.exception]
    assert any(b.label.endswith("Aggiorna") for b in at.button)
    assert at.session_state["chat_auto"] is False                      # di default non si ricarica da sola
    at.toggle(key="chat_auto").set_value(True).run()
    assert not at.exception, [e.value for e in at.exception]
    [b for b in at.button if b.label.endswith("Aggiorna")][0].click().run()
    assert not at.exception, [e.value for e in at.exception]
