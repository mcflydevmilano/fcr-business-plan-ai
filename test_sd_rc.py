import datetime as dt
import pytest

import rc
import sd
import storage

OGGI = dt.date(2026, 11, 7)


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "s.db"))
    storage.svuota_cache()


def _r(**k):
    base = {"Codice": "A1", "Indirizzo": "Via Roma 1", "Citta": "Milano", "Amministratore": "Studio Rossi", "Stato": "S2-Offerta", "Offerta": "2026-10-20", "Valore": 50000}
    base.update(k)
    return rc.normalizza([base])[0][0]


def test_offerte_da_seguire():
    assert len(rc.da_sollecitare([_r()], OGGI)) == 1
    assert rc.da_sollecitare([_r(Offerta="2026-11-05")], OGGI) == []                 # troppo recente
    assert rc.da_sollecitare([_r(Stato="S3-Contratto")], OGGI) == []                 # non e' piu' un'offerta
    assert rc.da_sollecitare([_r(Offerta="")], OGGI) == []                           # senza data non si puo' dire
    assert rc.da_sollecitare([_r(Archivio="Eliminata")], OGGI) == []


def test_dopo_il_seguito_sparisce_per_due_settimane():
    rc.segna_sollecito("A1", OGGI)
    s = rc.carica_solleciti()
    assert rc.da_sollecitare([_r()], OGGI + dt.timedelta(days=5), solleciti=s) == []
    assert len(rc.da_sollecitare([_r()], OGGI + dt.timedelta(days=15), solleciti=s)) == 1


def test_lettera_di_seguito_senza_buchi():
    o, c = rc.lettera_seguito(_r(), oggi=OGGI)
    assert "20/10/2026" in o and "Via Roma 1" in c and "Studio Rossi" in c and "[" not in c


def test_scadenze_stati():
    v = lambda d: {"Tipo": "DURC", "Soggetto": "Ditta X", "Scadenza": d}
    assert sd.stato(v("2026-11-01"), OGGI)[0] == "scaduto"
    assert sd.stato(v("2026-11-10"), OGGI) == ("urgente", 3)
    assert sd.stato(v("2026-12-01"), OGGI)[0] == "vicino"
    assert sd.stato(v("2027-01-01"), OGGI)[0] == "attenzione"
    assert sd.stato(v("2027-06-01"), OGGI)[0] == "ok"
    assert sd.stato({"Soggetto": "x"}, OGGI)[0] == "senza"


def test_scadenze_salva_ricarica_e_ordina():
    sd.salva({"voci": [{"Tipo": "DURC", "Soggetto": "B", "Scadenza": "2026-12-20"}, {"Tipo": "Visita medica", "Soggetto": "A", "Scadenza": "2026-11-01"}, {}], "preavvisi": [60, 30, 7]})
    c = sd.carica()
    assert [v["Soggetto"] for v in c["voci"]] == ["B", "A"] and all(v["id"] for v in c["voci"])
    e = sd.elenco(c["voci"], OGGI)
    assert e[0]["Soggetto"] == "A" and e[0]["stato"] == "scaduto"
    assert sd.riepilogo(c["voci"], OGGI)["scaduto"] == 1
    assert "scaduto da 6 giorni" in sd.frase(e[0])


def test_scadenze_excel_roundtrip():
    voci = sd.normalizza([{"Tipo": "Assicurazione / polizza", "Soggetto": "Furgone AB123CD", "Scadenza": "2026-11-30"}])
    b = sd.excel_bytes(sd.elenco(voci, OGGI), OGGI)
    import io
    back = sd.da_excel(io.BytesIO(b))
    assert back and back[0]["Soggetto"] == "Furgone AB123CD" and back[0]["Scadenza"] == "2026-11-30"


# ---- interfaccia ----
import os
from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(__file__), "app.py")


def _app(modulo, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["utente"] = {"username": "admin", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = modulo
    return at.run()


def test_ui_scadenze_aggiunge_una_voce(monkeypatch):
    storage.salva_pratica("org", {"persone": [{"Persona": "Furgone AB123CD"}]}, modulo="pe")
    at = _app("sd", monkeypatch)
    assert not at.exception
    at.selectbox(key="sd_n_sogg").set_value("Furgone AB123CD")
    at.date_input(key="sd_n_scad").set_value(dt.date(2026, 12, 1))
    next(b for b in at.button if "Aggiungi" in b.label).click().run()
    assert not at.exception
    assert [v["Soggetto"] for v in sd.carica()["voci"]] == ["Furgone AB123CD"]


def test_ui_riepilogo_si_apre_e_salva_le_impostazioni(monkeypatch):
    import mattino
    at = _app("rm", monkeypatch)
    assert not at.exception
    at.toggle(key="rm_attivo").set_value(True)
    at.button(key="rm_salva").click().run()
    assert not at.exception and mattino.carica_cfg()["attivo"] is True


def test_ui_offerte_da_seguire_nel_registro(monkeypatch):
    import rc_ui
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["utente"] = {"username": "admin", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = "rc"
    at.session_state["rc_df"] = rc_ui._df(rc.normalizza([{"Codice": "A1", "Indirizzo": "Via Roma 1", "Amministratore": "Rossi", "Stato": "S2-Offerta", "Offerta": "2020-01-10", "Valore": 1000}])[0])
    at.run()
    assert not at.exception
    assert any("Offerte da seguire (1)" in m.value for m in at.markdown)
    at.button(key="rc_seg_ok_0").click().run()
    assert not at.exception and "A1" in rc.carica_solleciti()
