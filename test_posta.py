"""Test della posta: un solo tentativo, nessun retry, salvagente anti-blocco, indirizzi puliti."""
import smtplib

import pytest

import posta
import storage

ENV = {"SMTP_HOST": "smtp.x", "SMTP_PORT": "587", "SMTP_USER": "amministrazione@fcrgeneralcontractor.eu", "SMTP_PASSWORD": "pw"}


class Finto:
    chiamate = []
    errore = None
    chiuso = 0

    def __init__(self, host, port, timeout=None, context=None):
        Finto.chiamate.append(("connect", host, port, timeout))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        Finto.chiuso += 1
        return False

    def starttls(self, **k):
        Finto.chiamate.append(("starttls",))

    def login(self, u, p):
        if Finto.errore:
            raise Finto.errore

    def send_message(self, m):
        Finto.chiamate.append(("send", m["To"], m["From"]))
        return {}


@pytest.fixture(autouse=True)
def _pulito(tmp_path, monkeypatch):
    Finto.chiamate, Finto.errore, Finto.chiuso = [], None, 0
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    storage.svuota_cache()
    monkeypatch.setattr(smtplib, "SMTP", Finto)
    monkeypatch.setattr(smtplib, "SMTP_SSL", Finto)


def test_invio_riuscito_con_timeout_e_connessione_chiusa():
    ok = posta.invia(["a@x.it", "A@x.it", "non-valido", " b@x.it "], "Oggetto", "Corpo", env=ENV)
    assert ok == ["a@x.it", "b@x.it"]                                   # doppioni e indirizzi non validi tolti
    assert Finto.chiamate[0] == ("connect", "smtp.x", 587, 10) and ("starttls",) in Finto.chiamate
    assert len([c for c in Finto.chiamate if c[0] == "send"]) == 1 and Finto.chiuso == 1
    assert Finto.chiamate[-1][2] == "amministrazione@fcrgeneralcontractor.eu"


def test_porta_465_usa_ssl_senza_starttls():
    posta.invia(["a@x.it"], "O", "C", env={**ENV, "SMTP_PORT": "465"})
    assert ("starttls",) not in Finto.chiamate and Finto.chiamate[0][2] == 465 and Finto.chiuso == 1


def test_errore_di_password_si_ferma_subito_senza_riprovare():
    Finto.errore = smtplib.SMTPAuthenticationError(535, b"no")
    with pytest.raises(posta.InvioFallito, match="non verrà ripetuto"):
        posta.invia(["a@x.it"], "O", "C", env=ENV)
    assert len([c for c in Finto.chiamate if c[0] == "connect"]) == 1 and Finto.chiuso == 1


def test_errori_generici_e_di_rete_non_vengono_ripetuti():
    for err in (smtplib.SMTPException("x"), TimeoutError("t"), OSError("rete")):
        Finto.chiamate, Finto.errore = [], err
        with pytest.raises(posta.InvioFallito):
            posta.invia(["a@x.it"], "O", "C", env=ENV)
        assert len([c for c in Finto.chiamate if c[0] == "connect"]) == 1


def test_salvagente_blocca_dopo_tre_errori_nell_ora():
    Finto.errore = smtplib.SMTPException("x")
    for _ in range(posta.MAX_ERRORI_ORA):
        with pytest.raises(posta.InvioFallito):
            posta.invia(["a@x.it"], "O", "C", env=ENV)
    Finto.chiamate, Finto.errore = [], None
    with pytest.raises(posta.InvioBloccato, match="nell'ultima ora"):
        posta.invia(["a@x.it"], "O", "C", env=ENV)
    assert Finto.chiamate == []                                         # nessuna connessione aperta: il dominio non viene toccato


def test_senza_destinatari_validi_o_senza_configurazione_non_si_collega():
    with pytest.raises(posta.InvioBloccato):
        posta.invia(["xxx", ""], "O", "C", env=ENV)
    with pytest.raises(posta.InvioBloccato):
        posta.invia(["a@x.it"], "O", "C", env={})
    assert Finto.chiamate == []


def test_indirizzi_predefiniti():
    assert posta.mittente({}) == "amministrazione@fcrgeneralcontractor.eu"
    assert posta.mittente({"MAIL_FROM": "rotto"}) == "amministrazione@fcrgeneralcontractor.eu"
    assert posta.mittente({"MAIL_FROM": "x@y.it"}) == "x@y.it"
    assert posta.destinatari_predefiniti({}) == ["amministrazione@fcrgeneralcontractor.eu"]
    assert posta.destinatari_predefiniti({"MAIL_TO": "a@x.it; b@x.it"}) == ["a@x.it", "b@x.it"]


def test_avvisi_automatici_non_riprovano_la_posta_dopo_un_errore(monkeypatch, tmp_path):
    import avvisi_dd
    db = str(tmp_path / "p.db")
    posta._registra("errore di prova", db)
    chiamate = []
    monkeypatch.setattr(avvisi_dd, "MAIL", lambda *a, **k: chiamate.append(1))
    righe = [{"Area": "Cassa", "Indicatore": "Scoperto", "Valore": "1", "Stato": "bad", "Nota": "", "Modulo": "cf"}]
    cfg = avvisi_dd.normalizza({"regole": [{"area": avvisi_dd.TUTTE, "da": "warn", "email": "a@x.it"}]})
    e = avvisi_dd.invia(righe, cfg, db, oggi="2026-10-30")
    assert chiamate == [] and any("sospesa" in x for x in e["errori"])
    avvisi_dd.invia(righe, cfg, db, oggi="2026-10-30", forza=True)       # chi preme «Invia ora» puo' riprovare
    assert chiamate == [1]
