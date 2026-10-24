"""Dati dimostrativi: non toccano i dati veri, si caricano e si tolgono, e ogni strumento si apre con i suoi dati di prova."""
import datetime as dt
import os
import tempfile

import pytest
from streamlit.testing.v1 import AppTest

import dd
import demo
import hub
import riepilogo
import storage

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")


@pytest.fixture(autouse=True)
def db(monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
    monkeypatch.setenv("APP_PASSWORD", "segreta")


def test_sposta_date():
    x = {"a": "2026-01-10", "b": ["2026-01-31", {"c": "2026-02-01T10:30"}], "d": "ciao", "e": 5, "f": "2026-13-45"}
    r = demo.sposta_date(x, 5)
    assert r["a"] == "2026-01-15" and r["b"][0] == "2026-02-05" and r["b"][1]["c"] == "2026-02-06T10:30" and r["d"] == "ciao" and r["e"] == 5 and r["f"] == "2026-13-45"


def test_carica_non_tocca_i_dati_veri_e_si_toglie():
    storage.salva_pratica("Registro vero", {"pratiche": [{"Codice": "X"}]}, modulo="rc", autore="u")
    storage.salva_pratica("Portafoglio vero", {"x": 1}, modulo="cf", autore="u")
    fatti = demo.carica("admin")
    assert len(fatti) >= 18 and {"rc", "of", "sc", "cf", "credit", "bp", "pv"} <= set(fatti)
    assert [p["nome"] for p in storage.elenca_pratiche(modulo="rc")] == ["Registro vero"]          # i veri restano soli
    assert [p["nome"] for p in storage.elenca_pratiche(modulo="rc", demo=True)] == [demo.NOME]
    assert storage.carica_pratica("Registro vero", modulo="rc") == {"pratiche": [{"Codice": "X"}]}
    assert storage.ultimi_aggiornamenti()["rc"][2] == "Registro vero" and "sc" not in storage.ultimi_aggiornamenti()      # nessun dato fresco inventato
    payloads, fonti = riepilogo.raccogli()
    assert fonti == {"rc": "Registro vero", "cf": "Portafoglio vero"}
    assert set(demo.presenti()) == set(fatti)
    n = demo.rimuovi()
    assert n == len(fatti) and demo.presenti() == []
    assert [p["nome"] for p in storage.elenca_pratiche(modulo="rc")] == ["Registro vero"] and storage.carica_pratica("Portafoglio vero", modulo="cf") == {"x": 1}


def test_date_sempre_aggiornate_a_oggi():
    demo.carica("a", oggi=dt.date.today() + dt.timedelta(days=100))
    p = storage.carica_pratica(demo.NOME, modulo="rc")
    primo = min(r["Inserita"] for r in p["pratiche"])
    assert primo > (dt.date.today() + dt.timedelta(days=100) - dt.timedelta(days=300)).isoformat()


def test_il_cruscotto_legge_tutto_con_i_dati_demo():
    demo.carica("a")
    m = {}
    for mod in dd.MODULI_METRICHE:
        el = storage.elenca_pratiche(modulo=mod, demo=True)
        assert el, mod
        m[mod] = dd.metriche_da_payload(mod, storage.carica_pratica(el[0]["nome"], modulo=mod))
        assert m[mod] is not None, mod
    righe, gen, az = dd.semafori(m)
    assert not [r for r in righe if r["Stato"] == "nd"] and gen in ("ok", "warn", "bad")
    ind = [r["Indicatore"] for r in righe]
    assert any(i.startswith("Copertura finanziaria") for i in ind) and any(i.startswith("Pipeline commerciale") for i in ind)
    assert dd.dettagli(m)


def _admin(modulo):
    at = AppTest.from_file(APP, default_timeout=240)
    at.session_state["utente"] = {"username": "root", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = modulo
    return at.run()


def test_cruscotto_pulsante_carica_e_mostra():
    at = _admin("dd")
    assert not at.exception
    [b for b in at.button if "Carica i dati dimostrativi" in b.label][0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert demo.presenti()
    at = _admin("dd")
    assert not at.exception, [e.value for e in at.exception]
    assert any("dimostrativi" in i.value for i in at.info) and at.radio(key="dd_modo").value.startswith("🎬")
    at.radio(key="dd_modo").set_value("Dati veri").run()
    assert not at.exception
    [b for b in at.button if "Togli i dati dimostrativi" in b.label][0].click().run()
    assert demo.presenti() == []


@pytest.mark.parametrize("m", ["sc", "cf", "pv", "sl", "ga", "fo", "sx", "mz", "og", "rp", "gt", "bk", "oa", "lg", "pe", "ru", "bp", "rc", "of"])
def test_ogni_strumento_apre_il_suo_salvataggio_demo(m):
    demo.carica("a")
    at = _admin(m)
    assert not at.exception, [e.value for e in at.exception]
    at.checkbox(key=f"sv_demo_{m}").check().run()
    at.selectbox(key=f"sv_scelta_{m}").set_value(demo.NOME)
    at.button(key=f"sv_apri_{m}").click().run()
    assert not at.exception, (m, [e.value for e in at.exception])


def test_credit_apre_la_pratica_demo():
    demo.carica("a")
    at = _admin("credit")
    assert not at.exception
    at.checkbox(key="sv_demo_credit").check().run()
    [b for b in at.button if "Carica" in b.label][0].click().run()
    assert not at.exception, [e.value for e in at.exception]


def test_ia_spiegata_nell_hub_e_nella_barra():
    at = _admin(None)
    assert not at.exception
    assert any("Cos'è l'IA" in e.label for e in at.expander) and any("intelligenza artificiale" in e.label for e in at.expander)
    assert any("IA" in x.value for x in list(at.info) + list(at.warning) + list(at.success))
