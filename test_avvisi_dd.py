"""Avvisi del Cruscotto per email e chat interna."""
import pytest

import avvisi_dd
import chat
import notifiche
import storage


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CHAT_KEY", raising=False)
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "a.db"))
    monkeypatch.setattr(notifiche, "HTTP", lambda *a, **k: (200, "{}"))
    p = str(tmp_path / "a.db")
    storage.svuota_cache()
    return p


def riga(area, ind, stato, val="10 €"):
    return {"Area": area, "Indicatore": ind, "Valore": val, "Stato": stato, "Nota": "n", "Modulo": "sc"}


RIGHE = [riga("Cassa", "Cassa a fine settimana 1", "bad", "-5.000 €"), riga("Margine", "Margine lordo", "warn", "12%"),
         riga("Crediti", "Crediti scaduti", "ok"), riga("Rating", "Rating", "nd")]


def test_normalizza_scarta_regole_vuote_e_email_sbagliate():
    c = avvisi_dd.normalizza({"regole": [
        {"area": "Cassa", "da": "bad", "email": "a@x.it, errata, b@y.it"},
        {"area": "Cassa"},                                   # nessun destinatario
        {"area": "Inventata", "canale": "Generale"},         # area sconosciuta
        {"area": avvisi_dd.TUTTE, "da": "boh", "persone": "mario; luca"}]})
    assert len(c["regole"]) == 2
    assert c["regole"][0]["email"] == ["a@x.it", "b@y.it"]
    assert c["regole"][1]["da"] == "bad" and c["regole"][1]["persone"] == ["mario", "luca"]


def test_gravita_e_area():
    cfg = avvisi_dd.normalizza({"regole": [{"area": "Margine", "da": "bad", "email": "a@x.it"},
                                           {"area": avvisi_dd.TUTTE, "da": "warn", "persone": "mario"}]})
    d = avvisi_dd.da_inviare(RIGHE, cfg, {}, "2026-10-24")
    ris = {r["area"]: [x["Area"] for x in p] for r, p in d}
    assert "Margine" not in ris                                          # giallo, ma la regola vuole solo il rosso
    assert ris[avvisi_dd.TUTTE] == ["Cassa", "Margine"]                  # giallo e rosso; ok e nd mai


def test_invio_in_chat_email_e_telefono_senza_doppioni(db, monkeypatch):
    chat.crea_canale("Cantieri", "pubblico", "admin", path=db)
    chat.salva_prefs("mario", db, ntfy_topic="fcr-x", modo="menzioni")
    mail = []
    monkeypatch.setattr(avvisi_dd, "MAIL", lambda dest, ogg, corpo, env=None: mail.append((dest, ogg, corpo)))
    inviate = []
    monkeypatch.setattr(notifiche, "HTTP", lambda url, dati=None, intest=None, timeout=6: (inviate.append(url) or (200, "{}")))
    cfg = avvisi_dd.normalizza({"regole": [{"area": avvisi_dd.TUTTE, "da": "warn", "canale": "Cantieri", "persone": "mario", "email": "dir@fcr.it"}]})
    e = avvisi_dd.invia(RIGHE, cfg, db, oggi="2026-10-24", utenti_noti=["mario"], link="https://suite", sincrono=True)
    assert e["errori"] == [] and e["email"] == 1 and e["chat"] == 2 and e["regole"] == 1
    assert "Cassa a fine settimana 1" in mail[0][2] and "ROSSO" in mail[0][2] and "https://suite" in mail[0][2]
    canale = [c for c in chat.canali_visibili("luca", db) if c["nome"] == "Cantieri"][0]["id"]
    m = chat.messaggi(canale, "luca", path=db)[-1]
    assert m["autore"] == "Cruscotto" and "GIALLO" in m["testo"] and "@mario" in m["testo"]
    dm = [c for c in chat.canali_visibili("mario", db) if c["tipo"] == "diretto"][0]
    assert dm["etichetta"] == "Cruscotto" and chat.messaggi(dm["id"], "mario", path=db)[-1]["testo"].startswith("Cruscotto di direzione")
    assert any("fcr-x" in u for u in inviate)                            # avviso sul telefono (ntfy) per chi e' citato / scritto in diretta
    # stesso giorno: niente doppioni; con «forza» si rimanda; giorno dopo si rimanda
    assert avvisi_dd.invia(RIGHE, cfg, db, oggi="2026-10-24", sincrono=True)["regole"] == 0
    assert avvisi_dd.invia(RIGHE, cfg, db, oggi="2026-10-24", forza=True, sincrono=True)["regole"] == 1
    assert avvisi_dd.invia(RIGHE, cfg, db, oggi="2026-10-25", sincrono=True)["regole"] == 1
    assert len(mail) == 3


def test_errori_non_bloccano_gli_altri_canali(db, monkeypatch):
    def guasto(*a, **k):
        raise OSError("rete")
    monkeypatch.setattr(avvisi_dd, "MAIL", guasto)
    cfg = avvisi_dd.normalizza({"regole": [{"area": "Cassa", "da": "bad", "canale": "Inesistente", "persone": "mario", "email": "x@y.it"}]})
    e = avvisi_dd.invia(RIGHE, cfg, db, oggi="2026-10-24", sincrono=True)
    assert e["chat"] == 1 and e["email"] == 0 and len(e["errori"]) == 2     # canale non trovato + email fallita; la chat diretta e' partita
    assert any("Inesistente" in x for x in e["errori"]) and any("SMTP" in x for x in e["errori"])


def test_configurazione_si_salva_e_si_rilegge(db):
    avvisi_dd.salva_cfg({"regole": [{"area": "Cassa", "da": "warn", "email": "a@b.it"}], "auto": False}, "admin", db)
    storage.svuota_cache()
    c = avvisi_dd.carica_cfg(db)
    assert c["auto"] is False and c["regole"][0]["da"] == "warn"


def test_smtp_pronto():
    assert not avvisi_dd.smtp_pronto({})
    assert avvisi_dd.smtp_pronto({"SMTP_HOST": "h", "SMTP_USER": "u", "SMTP_PASSWORD": "p"})


def test_schermata_cruscotto_con_avvisi(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setenv("FCR_DB_PATH", str(tmp_path / "u.db"))
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "u.db"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    storage.svuota_cache()
    at = AppTest.from_file("app.py", default_timeout=90).run()
    at.text_input(key="login_user").set_value("admin")
    at.text_input(key="login_pw").set_value("segreta")
    at.button[0].click().run()
    at.session_state["active_module"] = "dd"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Avvisi per email e chat interna" in e.label for e in at.expander)


# ---- rapporto settimanale e controllo programmato ----
def _salva_demo_veri(path):
    import datetime as dt
    import demo
    d = demo._leggi()
    g = (dt.date.today() - dt.date.fromisoformat(d["_base"])).days
    for m, p in d.items():
        if m != "_base":
            storage.salva_pratica("Pratica prova", demo.sposta_date(p, g), path, autore="t", modulo=m)
    storage.svuota_cache()


def test_cfg_rapporto_normalizzata():
    c = avvisi_dd.normalizza({"report": {"attivo": True, "email": "a@x.it, errata"}})
    assert c["report"] == {"attivo": True, "email": ["a@x.it"]}
    assert avvisi_dd.normalizza({})["report"] == {"attivo": False, "email": []}


def test_rapporto_pdf_allegato_una_volta_al_giorno(db, monkeypatch):
    mail = []
    monkeypatch.setattr(avvisi_dd, "MAIL", lambda dest, ogg, corpo, env=None, allegati=(): mail.append((dest, ogg, corpo, allegati)))
    _salva_demo_veri(db)
    import job_avvisi
    righe, gen, azioni, fonti = job_avvisi.prepara(db)
    cfg = avvisi_dd.normalizza({"report": {"attivo": True, "email": "dir@fcr.it"}})
    e = avvisi_dd.invia_rapporto(righe, gen, azioni, fonti, cfg, db, oggi="2026-10-26")
    assert e["email"] == 1 and not e["errori"]
    nome, dati, mime = mail[0][3][0]
    assert nome.startswith("Cruscotto_") and dati[:4] == b"%PDF" and mime == "application/pdf"
    assert avvisi_dd.invia_rapporto(righe, gen, azioni, fonti, cfg, db, oggi="2026-10-26")["saltato"] == "gia' inviato oggi"
    assert avvisi_dd.invia_rapporto(righe, gen, azioni, fonti, cfg, db, oggi="2026-10-26", forza=True)["email"] == 1
    assert avvisi_dd.invia_rapporto(righe, gen, azioni, fonti, avvisi_dd.normalizza({}), db)["saltato"]


def test_job_invia_avvisi_e_rapporto_di_lunedi(db, monkeypatch):
    import datetime as dt
    import job_avvisi
    mail = []
    monkeypatch.setattr(avvisi_dd, "MAIL", lambda dest, ogg, corpo, env=None, allegati=(): mail.append((dest, ogg, bool(allegati))))
    _salva_demo_veri(db)
    chat.crea_canali_iniziali("admin", path=db)
    avvisi_dd.salva_cfg({"regole": [{"area": avvisi_dd.TUTTE, "da": "bad", "canale": "Generale", "email": "a@x.it"}],
                         "report": {"attivo": True, "email": "dir@fcr.it"}}, "admin", db)
    storage.svuota_cache()
    lunedi = dt.date(2026, 10, 26)
    assert lunedi.weekday() == 0
    out = job_avvisi.esegui(db, lunedi)
    assert out["avvisi"]["regole"] == 1 and out["rapporto"]["email"] == 1
    assert [m[2] for m in mail] == [False, True]                              # prima l'avviso (senza allegato), poi il rapporto con PDF
    canale = [c for c in chat.canali_visibili("zeno", db) if c["nome"] == "Generale"][0]["id"]
    assert chat.messaggi(canale, "zeno", path=db)[-1]["autore"] == "Cruscotto"
    # stesso giorno: niente doppioni; martedi' niente rapporto; --rapporto lo forza
    assert job_avvisi.esegui(db, lunedi)["avvisi"]["regole"] == 0
    assert job_avvisi.esegui(db, dt.date(2026, 10, 27))["rapporto"] is None
    assert job_avvisi.esegui(db, dt.date(2026, 10, 27), forza_rapporto=True)["rapporto"]["email"] == 1


def test_job_dry_run_non_invia(db, monkeypatch):
    import datetime as dt
    import job_avvisi
    mail = []
    monkeypatch.setattr(avvisi_dd, "MAIL", lambda *a, **k: mail.append(1))
    _salva_demo_veri(db)
    avvisi_dd.salva_cfg({"regole": [{"area": avvisi_dd.TUTTE, "da": "warn", "email": "a@x.it"}]}, "admin", db)
    storage.svuota_cache()
    out = job_avvisi.esegui(db, dt.date(2026, 10, 26), dry_run=True)
    assert out["avvisi"] and mail == []
