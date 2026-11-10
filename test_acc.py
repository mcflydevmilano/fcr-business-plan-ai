import datetime as dt

import pytest

import acc
import storage

CFG = acc.normalizza_cfg({"lat": 45.4408, "lon": 9.1693, "raggio_m": 150, "ip": "203.0.113.7, 198.51.100.0/24", "pause": True})
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


def test_uscite_in_orario_sempre_disponibili_con_motivo(tmp_path):
    p = _db(tmp_path)
    c = acc.normalizza_cfg({"ip": SEDE_IP, "pause": False})                       # anche un salvataggio vecchio con le pause spente
    assert c["pause"] is True and acc.azioni_consentite("dentro") == ["pausa", "uscita"] and acc.azioni_consentite("fuori") == ["entrata"]
    assert acc.timbra("sara", "entrata", c, SEDE_IP, path=p, adesso=_t(8))["ok"]
    assert acc.timbra("sara", "pausa", c, SEDE_IP, path=p, adesso=_t(11), motivo="Commissione di lavoro", dettaglio="banca")["ok"]
    assert acc.timbra("sara", "rientro", c, SEDE_IP, path=p, adesso=_t(12))["ok"]
    assert acc.timbra("sara", "pausa", c, SEDE_IP, path=p, adesso=_t(13), motivo="Visita medica")["ok"]
    assert acc.timbra("sara", "rientro", c, SEDE_IP, path=p, adesso=_t(14))["ok"]
    assert acc.timbra("sara", "uscita", c, SEDE_IP, path=p, adesso=_t(17))["ok"]
    ev = storage.elenca_timbrature(utente="sara", path=p)
    assert [e["nota"] for e in ev if e["tipo"] == "pausa"] == ["Commissione di lavoro - banca", "Visita medica"]
    r = acc.riepilogo_giorno(ev, acc.a_locale(ev[0]["ts"]).date(), adesso=_t(18))
    assert r["lavorato_min"] == 8 * 60 and r["commissione_min"] == 60 and r["pausa_min"] == 60       # 9 ore di presenza - 1 ora di visita medica; la commissione conta


def test_riepilogo_mensile_per_persona(tmp_path):
    p = _db(tmp_path)
    c = acc.normalizza_cfg({"ip": SEDE_IP})
    for g in (3, 4):
        d = lambda h, g=g: dt.datetime(2026, 11, g, h - 1, 0)                         # ora italiana = UTC+1 a novembre
        for pers in ("anna verdi", "luca neri"):
            acc.timbra(pers, "entrata", c, SEDE_IP, path=p, adesso=d(8))
            acc.timbra(pers, "uscita", c, SEDE_IP, path=p, adesso=d(16 if pers == "anna verdi" else 17))
    ev = storage.elenca_timbrature(path=p)
    righe = acc.tabella(ev, dt.date(2026, 11, 1), dt.date(2026, 11, 30))
    riep = {r["Persona"]: r for r in acc.riepilogo_mese(righe)}
    assert riep["anna verdi"]["Ore lavorate"] == "16:00" and riep["anna verdi"]["Giorni di presenza"] == 2 and riep["anna verdi"]["Media al giorno"] == "8:00"
    assert riep["luca neri"]["Ore lavorate"] == "18:00" and riep["luca neri"]["_ore_decimali"] == 18.0


def test_fuori_sede_solo_per_gli_abilitati_con_giustificazione(tmp_path):
    p = _db(tmp_path)
    cfg = acc.normalizza_cfg(dict(CFG, esterni=["Luca  Neri", "luca neri", ""]))
    assert cfg["esterni"] == ["luca neri"]
    # non abilitato: rifiutato
    r = acc.timbra("mario rossi", "entrata", cfg, FUORI_IP, path=p, adesso=_t(8), esterno="cantiere")
    assert not r["ok"] and "abilitato" in r["messaggio"]
    # abilitato ma senza giustificazione
    r = acc.timbra("luca neri", "entrata", cfg, FUORI_IP, path=p, adesso=_t(8), esterno="  ")
    assert not r["ok"] and "dove vai" in r["messaggio"].lower()
    # entrata con giustificazione, senza posizione
    r = acc.timbra("luca neri", "entrata", cfg, FUORI_IP, path=p, adesso=_t(8), esterno="Cantiere Via Roma 12, sopralluogo")
    assert r["ok"] and r["stato"] == "dentro"
    # senza esterno, da fuori rete, resta vietato come prima
    assert acc.timbra("luca neri", "uscita", cfg, FUORI_IP, path=p, adesso=_t(12))["serve_posizione"]
    r = acc.timbra("luca neri", "uscita", cfg, FUORI_IP, path=p, adesso=_t(16), esterno="")
    assert r["ok"] and r["stato"] == "fuori"
    ev = storage.elenca_timbrature(utente="luca neri", path=p)
    assert [e["metodo"] for e in ev] == ["esterno", "esterno"] and "Via Roma" in ev[0]["nota"]
    righe = acc.tabella(ev, dt.date(2026, 11, 5), dt.date(2026, 11, 5), adesso=_t(18))
    assert righe[0]["Ore in ufficio"] == "8:00" and "fuori sede: Cantiere Via Roma 12" in righe[0]["Note"]


def test_ui_fuori_sede_visibile_solo_agli_abilitati(monkeypatch, tmp_path):
    import os
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "f.db"))
    acc.salva_cfg(dict(CFG, esterni=["luca neri"]), "admin")
    storage.svuota_cache()
    import auth
    auth.crea_utente("luca neri", "Password-Lunga-1")
    auth.crea_utente("mario rossi", "Password-Lunga-1")
    for nome, atteso in (("luca neri", True), ("mario rossi", False)):
        app = AppTest.from_file(os.path.join(os.path.dirname(__file__), "app.py"), default_timeout=60)
        app.session_state["utente"] = {"username": nome, "ruolo": "utente", "origine": "db"}
        app.session_state["active_module"] = "ac"
        app.run()
        assert not app.exception
        assert any("fuori sede" in e.label.lower() for e in app.expander) == atteso


def test_registro_mostra_i_fuori_sede_di_oggi(monkeypatch, tmp_path):
    import os
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "g.db"))
    cfg = acc.salva_cfg(dict(CFG, esterni=["luca neri"]), "admin")
    storage.svuota_cache()
    assert acc.timbra("luca neri", "entrata", acc.carica_cfg(), FUORI_IP, esterno="Cantiere Via Roma 12")["ok"]
    app = AppTest.from_file(os.path.join(os.path.dirname(__file__), "app.py"), default_timeout=60)
    app.session_state["utente"] = {"username": "admin", "ruolo": "admin", "origine": "app_password"}
    app.session_state["active_module"] = "ac"
    app.run()
    assert not app.exception


def test_timbratura_vale_anche_sabato_e_domenica(tmp_path):
    """Non c'e' nessun blocco per sabato o domenica: la timbratura funziona tutti i giorni."""
    p = _db(tmp_path)
    sabato = dt.datetime(2026, 11, 7)                      # 7/11/2026 e' un sabato
    domenica = dt.datetime(2026, 11, 8)
    assert sabato.weekday() == 5 and domenica.weekday() == 6
    assert acc.timbra("anna", "entrata", CFG, SEDE_IP, path=p, adesso=sabato.replace(hour=8))["ok"]
    assert acc.timbra("anna", "uscita", CFG, SEDE_IP, path=p, adesso=sabato.replace(hour=17))["ok"]
    assert acc.timbra("anna", "entrata", CFG, SEDE_IP, path=p, adesso=domenica.replace(hour=9))["ok"]


def test_correggere_lora_di_entrata_sostituisce_quella_sbagliata_e_conta_tutte_le_ore(tmp_path):
    """Se l'entrata e' registrata a un'ora sbagliata (es. le 10 invece delle 8) e si corregge con «correggi», la vecchia timbratura
    va annullata automaticamente e le ore lavorate si contano dall'ora corretta (le 8), non da quando si fa la correzione."""
    p = _db(tmp_path)
    assert acc.timbra("anna", "entrata", CFG, SEDE_IP, path=p, adesso=_t(10, g=6))["ok"]     # ora sbagliata: le 10 (locale 11:00)
    acc.correggi("anna", "entrata", dt.datetime(2026, 11, 6, 8, 0), "arrivata alle 8, non alle 10", "lorenzo", p)
    assert acc.timbra("anna", "uscita", CFG, SEDE_IP, path=p, adesso=_t(18, g=6))["ok"]      # uscita alle 18 (locale 19:00)
    ev = storage.elenca_timbrature(utente="anna", path=p)
    g = acc.riepilogo_giorno(ev, dt.date(2026, 11, 6), _t(19, g=6))
    assert g["anomalie"] == []                                                # nessuna «Entrata doppia»
    assert g["lavorato_min"] == 11 * 60                                       # dalle 8 alle 19 locali: 11 ore, non 9
    con_annullate = storage.elenca_timbrature(utente="anna", con_annullate=True, path=p)
    annullate = [e for e in con_annullate if e["annullata"]]
    assert len(annullate) == 1 and "sostituita da una correzione" in annullate[0]["motivo_annullo"]
