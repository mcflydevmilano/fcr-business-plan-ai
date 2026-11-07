import datetime as dt
import pytest

import mattino
import rc
import sd
import storage

OGGI = dt.date(2026, 11, 9)       # lunedi'


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "m.db"))
    storage.svuota_cache()


def _dati():
    sd.salva({"voci": [{"Tipo": "DURC", "Soggetto": "Ditta X", "Scadenza": "2026-11-12"}], "preavvisi": [60, 30, 7]})
    storage.salva_pratica("reg", {"pratiche": [{"Codice": "A1", "Indirizzo": "Via Roma 1", "Amministratore": "Rossi", "Stato": "S2-Offerta", "Offerta": "2026-10-20", "Valore": 1000}]}, modulo="rc")


def test_sezioni_rispettano_i_permessi():
    _dati()
    u = {"username": "anna", "ruolo": "utente"}
    tutte = dict(mattino.sezioni(u, "commerciale", {"rc", "sd"}, OGGI))
    assert "Offerte da seguire" in tutte and "Scadenze di persone e mezzi" in tutte
    solo_sd = dict(mattino.sezioni(u, "cantiere", {"sd"}, OGGI))
    assert "Offerte da seguire" not in solo_sd and "Scadenze di persone e mezzi" in solo_sd
    assert mattino.sezioni(u, "cantiere", set(), OGGI) == []


def test_testo_e_html():
    _dati()
    u = {"username": "anna", "ruolo": "utente"}
    s = mattino.sezioni(u, "commerciale", {"rc", "sd"}, OGGI)
    t = mattino.testo(u, s, OGGI)
    assert "Buongiorno Anna" in t and "lunedì 9 novembre" in t and "DURC" in t
    assert "<li" in mattino.corpo_html(u, s, OGGI) and "Oggi non c'è niente" in mattino.testo(u, [], OGGI)


def test_invio_una_volta_al_giorno_e_non_nel_weekend(monkeypatch):
    _dati()
    storage.salva_utente("anna", "x", "admin", "", email="anna@example.com")
    inviati = []
    monkeypatch.setattr(mattino.posta, "invia", lambda dest, ogg, corpo, **k: inviati.append(dest))
    mattino.salva_cfg({"attivo": True, "email": True, "slack": False})
    r = mattino.invia_tutti(oggi=OGGI)
    assert r["inviati"] == ["anna"] and inviati == [["anna@example.com"]]
    assert mattino.invia_tutti(oggi=OGGI)["inviati"] == []                         # gia' partito oggi
    assert mattino.invia_tutti(oggi=dt.date(2026, 11, 14))["inviati"] == []        # sabato
    assert len(mattino.invia_tutti(oggi=OGGI, forza=True)["inviati"]) == 1         # forzato


def test_spento_non_invia(monkeypatch):
    _dati()
    storage.salva_utente("anna", "x", "admin", "", email="anna@example.com")
    monkeypatch.setattr(mattino.posta, "invia", lambda *a, **k: pytest.fail("non doveva inviare"))
    assert mattino.invia_tutti(oggi=OGGI)["inviati"] == []


def test_chi_non_lo_vuole_e_chi_non_ha_niente(monkeypatch):
    _dati()
    storage.salva_utente("anna", "x", "admin", "", email="anna@example.com")
    storage.salva_utente("luca", "x", "admin", "", email="luca@example.com")
    inviati = []
    monkeypatch.setattr(mattino.posta, "invia", lambda dest, *a, **k: inviati.append(dest[0]))
    mattino.salva_cfg({"attivo": True, "email": True, "slack": False, "escludi": ["luca"]})
    mattino.invia_tutti(oggi=OGGI)
    assert inviati == ["anna@example.com"]
