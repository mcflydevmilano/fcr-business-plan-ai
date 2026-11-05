import datetime as dt

import pytest

import acc
import storage

CFG = acc.normalizza_cfg({"lat": 45.4408, "lon": 9.1693, "raggio_m": 150, "ip": "203.0.113.7, 198.51.100.0/24"})
SEDE_IP = "203.0.113.7"
FUORI_IP = "93.1.2.3"


def _db(tmp_path):
    return str(tmp_path / "a.db")


def _t(h, m=0, g=5):
    return dt.datetime(2026, 11, g, h, m)        # UTC


def test_cfg_normalizza():
    c = acc.normalizza_cfg({"lat": "95", "lon": "x", "raggio_m": 5, "ip": "1.2.3.4, boh, 10.0.0.0/24"})
    assert c["lat"] is None and c["lon"] is None
    assert c["raggio_m"] == 30
    assert c["ip"] == ["1.2.3.4", "10.0.0.0/24"]


def test_ip_cliente_e_sede():
    assert acc.ip_cliente({"CF-Connecting-IP": "1.1.1.1", "X-Forwarded-For": "2.2.2.2"}) == "1.1.1.1"
    assert acc.ip_cliente({"X-Forwarded-For": "2.2.2.2, 3.3.3.3"}) == "2.2.2.2"
    assert acc.ip_cliente({}, "10.0.0.5") == "10.0.0.5"
    assert acc.ip_in_sede(SEDE_IP, CFG) and acc.ip_in_sede("198.51.100.40", CFG)
    assert not acc.ip_in_sede(FUORI_IP, CFG) and not acc.ip_in_sede("boh", CFG)


def test_distanza():
    assert acc.distanza_m(45.0, 9.0, 45.0, 9.0) == 0
    assert 110000 < acc.distanza_m(45.0, 9.0, 46.0, 9.0) < 112000


def test_valuta_accesso():
    assert acc.valuta_accesso(CFG, SEDE_IP)["ok"] and acc.valuta_accesso(CFG, SEDE_IP)["metodo"] == "rete"
    v = acc.valuta_accesso(CFG, FUORI_IP)
    assert not v["ok"] and v["serve_posizione"]
    v = acc.valuta_accesso(CFG, FUORI_IP, {"lat": 45.4409, "lon": 9.1694, "acc": 20})
    assert v["ok"] and v["metodo"] == "posizione" and v["distanza_m"] < 30
    v = acc.valuta_accesso(CFG, FUORI_IP, {"lat": 45.50, "lon": 9.17, "acc": 20})
    assert not v["ok"] and not v["serve_posizione"] and "m dalla sede" in v["messaggio"]
    v = acc.valuta_accesso(CFG, FUORI_IP, {"lat": 45.4408, "lon": 9.1693, "acc": 900})
    assert not v["ok"] and v["serve_posizione"] and "poco preciso" in v["messaggio"]
    v = acc.valuta_accesso(acc.normalizza_cfg({}), FUORI_IP, {"lat": 1, "lon": 1, "acc": 5})
    assert not v["ok"] and "non è ancora impostata" in v["messaggio"]
    assert not acc.valuta_accesso(CFG, FUORI_IP, {"lat": "x"})["ok"]


def test_stato_e_azioni():
    assert acc.stato([]) == "fuori" and acc.azioni_consentite("fuori") == ["entrata"]
    assert acc.stato([{"tipo": "entrata", "ts": "2026-11-05 08:00:00"}], _t(9)) == "dentro"
    assert acc.stato([{"tipo": "pausa", "ts": "2026-11-05 08:00:00"}], _t(9)) == "in_pausa"
    # uscita dimenticata ieri: oggi si riparte da fuori
    assert acc.stato([{"tipo": "entrata", "ts": "2026-11-04 08:00:00"}], _t(9)) == "fuori"


def test_giornata_completa(tmp_path):
    p = _db(tmp_path)
    r = acc.timbra("marco", "entrata", CFG, SEDE_IP, path=p, adesso=_t(7, 55))
    assert r["ok"] and r["stato"] == "dentro"
    assert not acc.timbra("marco", "entrata", CFG, SEDE_IP, path=p, adesso=_t(8))["ok"]          # doppia entrata
    assert acc.timbra("marco", "pausa", CFG, FUORI_IP, path=p, adesso=_t(11))["ok"]               # pausa: nessuna posizione
    assert acc.timbra("marco", "rientro", CFG, FUORI_IP, path=p, adesso=_t(11, 30))["ok"]
    r = acc.timbra("marco", "uscita", CFG, FUORI_IP, path=p, adesso=_t(16))                       # fuori rete, senza posizione
    assert not r["ok"] and r["serve_posizione"]
    r = acc.timbra("marco", "uscita", CFG, FUORI_IP, {"lat": 45.4409, "lon": 9.1693, "acc": 30}, path=p, adesso=_t(16))
    assert r["ok"] and r["stato"] == "fuori"
    ev = storage.elenca_timbrature(utente="marco", path=p)
    assert [e["tipo"] for e in ev] == ["entrata", "pausa", "rientro", "uscita"]
    assert ev[3]["metodo"] == "posizione" and ev[3]["distanza_m"] is not None
    g = acc.riepilogo_giorno(ev, acc.a_locale(ev[0]["ts"]).date(), _t(20))
    assert g["pausa_min"] == 30
    assert g["lavorato_min"] == 3 * 60 + 5 + 4 * 60 + 30     # 7:55-11:00 + 11:30-16:00
    assert not g["anomalie"] and not g["aperta"]


def test_uscita_dimenticata_e_correzione(tmp_path):
    p = _db(tmp_path)
    acc.timbra("anna", "entrata", CFG, SEDE_IP, path=p, adesso=_t(8, g=4))
    assert acc.timbra("anna", "entrata", CFG, SEDE_IP, path=p, adesso=_t(8, g=5))["ok"]          # il giorno dopo si riparte
    ev = storage.elenca_timbrature(utente="anna", path=p)
    g4 = acc.riepilogo_giorno(ev, acc.a_locale(ev[0]["ts"]).date(), _t(9, g=5))
    assert "Uscita mancante" in g4["anomalie"]
    with pytest.raises(ValueError):
        acc.correggi("anna", "uscita", dt.datetime(2026, 11, 4, 17, 0), "  ", "lorenzo", p)
    acc.correggi("anna", "uscita", dt.datetime(2026, 11, 4, 17, 0), "dimenticata", "lorenzo", p)
    ev = storage.elenca_timbrature(utente="anna", path=p)
    g4 = acc.riepilogo_giorno(ev, dt.date(2026, 11, 4), _t(9, g=5))
    assert not g4["anomalie"] or g4["anomalie"] == [] and g4["manuale"]
    assert g4["manuale"]


def test_annulla_resta_nel_registro(tmp_path):
    p = _db(tmp_path)
    acc.timbra("luca", "entrata", CFG, SEDE_IP, path=p, adesso=_t(8))
    i = storage.elenca_timbrature(path=p)[0]["id"]
    with pytest.raises(ValueError):
        acc.annulla(i, "", "lorenzo", p)
    acc.annulla(i, "errore", "lorenzo", p)
    assert storage.elenca_timbrature(path=p) == []
    tutte = storage.elenca_timbrature(con_annullate=True, path=p)
    assert len(tutte) == 1 and tutte[0]["annullata"] == 1 and "errore" in tutte[0]["motivo_annullo"]


def test_tabella_e_ore():
    assert acc.ore(125) == "2:05"
    ev = [{"utente": "a", "tipo": "entrata", "ts": "2026-11-05 07:00:00", "metodo": "rete"},
          {"utente": "a", "tipo": "uscita", "ts": "2026-11-05 15:00:00", "metodo": "rete"}]
    t = acc.tabella(ev, dt.date(2026, 11, 5), dt.date(2026, 11, 6), _t(20))
    assert len(t) == 1 and t[0]["Ore in ufficio"] == "8:00" and t[0]["Entrata"] == "08:00" and t[0]["Uscita"] == "16:00"


def test_foglio_qr_si_crea():
    import ac_ui
    pdf, png = ac_ui._foglio_qr("https://suite.example.it/?timbra=1", "Via Prova 1, Milano")
    assert pdf[:4] == b"%PDF" and png[:4] == b"\x89PNG"


def test_modulo_accessi_si_apre(monkeypatch, tmp_path):
    import os
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "m.db"))
    app = AppTest.from_file(os.path.join(os.path.dirname(__file__), "app.py"), default_timeout=60)
    app.session_state["utente"] = {"username": "admin", "ruolo": "admin", "origine": "app_password"}
    app.session_state["active_module"] = "ac"
    app.run()
    assert not app.exception
    assert len(app.tabs) >= 4


def test_pagina_timbratura_senza_login(monkeypatch, tmp_path):
    import os
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "m.db"))
    app = AppTest.from_file(os.path.join(os.path.dirname(__file__), "app.py"), default_timeout=60)
    app.query_params["timbra"] = "1"
    app.run()
    assert not app.exception
    assert any("Timbratura" in m.value for m in app.markdown)
    assert not any("Hub" in b.label for b in app.button)          # non apre la suite
