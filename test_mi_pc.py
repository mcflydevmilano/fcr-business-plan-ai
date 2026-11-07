"""Controllo impianti ESCo e portale cliente."""
import datetime as dt
import os
import tempfile

import pytest
from streamlit.testing.v1 import AppTest

import mi
import pc
import storage

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
OGGI = dt.date(2026, 11, 7)


@pytest.fixture(autouse=True)
def db(monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
    monkeypatch.setenv("APP_PASSWORD", "segreta")


def _admin(modulo):
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["utente"] = {"username": "root", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = modulo
    return at.run()


def _imp():
    return mi.normalizza([{"nome": "Scuola", "cliente": "Comune", "kwp": 10, "inizio": "2026-06-01", "canone": 500, "manutenzione": "2026-11-20",
                           "letture": {"2026-08": 1000, "2026-09": 1100}, "incassi": {"2026-06": 500, "2026-07": 500, "2026-08": 500}}])


def test_mi_analisi_e_avvisi():
    i = _imp()[0]
    a = {x["mese"]: x for x in mi.analisi(i, OGGI)}
    assert a["2026-08"]["stato"] == "bad" and a["2026-09"]["perc"] == 99.5 and a["2026-09"]["stato"] == "ok" and a["2026-10"]["stato"] == "manca"
    assert "2026-05" not in a                                              # prima dell'inizio contratto
    fr = [f for _, f in mi.avvisi([i], OGGI)]
    assert any("canone non incassato per 2 mesi" in f for f in fr) and any("manca la lettura di ottobre" in f for f in fr) and any("manutenzione tra 13 giorni" in f for f in fr)
    assert mi.riepilogo([i], OGGI)["insoluti"] == 2 and mi.normalizza([{"nome": ""}]) == []
    assert mi.excel_bytes([i], OGGI)[:2] == b"PK"


def test_mi_salva_e_mattino():
    mi.salva(_imp(), "x")
    assert mi.carica()[0]["letture"]["2026-08"] == 1000
    import mattino
    sez = mattino.sezioni({"username": "root", "ruolo": "admin"}, "direzione", {"mi"}, dt.date(2026, 11, 7))
    assert any(t == "Impianti ESCo" for t, _ in sez)


def test_pc_il_token_non_si_salva_e_la_validita():
    t, i = pc.crea("Rossi", "001", 30, "admin", oggi=OGGI)
    assert t not in repr(storage.carica_pratica(pc.NOME_INDICE, modulo="cfg"))
    assert pc.trova(t, oggi=OGGI)[1] == "attivo" and pc.trova(t[:-1] + ("a" if t[-1] != "a" else "b"), oggi=OGGI)[0] is None
    assert pc.trova(t, oggi=dt.date(2027, 1, 1))[1] == "scaduto" and pc.trova("../../x")[1] == "non_valido" and pc.trova(None)[1] == "non_valido"
    pc.revoca(i)
    assert pc.trova(t, oggi=OGGI)[0] is None
    pc.proroga(i, 10, oggi=OGGI)
    assert pc.trova(t, oggi=OGGI)[1] == "attivo"


def test_pc_contenuto_limiti_e_accettazione():
    t, i = pc.crea("Rossi", oggi=dt.date.today())
    c = pc.contenuto_vuoto()
    c.update(avanzamento=250, passi=["a"] * 20, foto=[{"nome": "f", "tipo": "text/html", "dati": "x"}] + [{"nome": "g", "tipo": "image/jpeg", "dati": "x"}] * 9)
    c["offerta"].update(attiva=True, titolo="FV", importo=1000)
    pc.salva_contenuto(i, c, "a")
    s = pc.carica_contenuto(i)
    assert s["avanzamento"] == 100 and len(s["passi"]) == pc.MAX_PASSI and len(s["foto"]) == pc.MAX_FOTO
    assert pc.accetta(t, "A", b"x")[0] is False and pc.accetta(t, "Mario Rossi", None)[0] is False
    assert pc.accetta(t, "Mario Rossi", b"png")[0] is True and pc.accetta(t, "Altro Nome", b"png")[0] is False
    c["offerta"]["importo"] = 1
    pc.salva_contenuto(i, c, "a")
    assert pc.carica_contenuto(i)["offerta"]["importo"] == 1000 and pc.carica_contenuto(i)["accettazione"]["nome"] == "Mario Rossi"
    assert [x for x in pc.elenca() if x["id"] == i][0]["accettata"] is True and "hash" not in pc.elenca()[0]
    pc.revoca(i)
    assert pc.accetta(t, "Mario Rossi", b"png")[0] is False


@pytest.mark.parametrize("m", ["mi", "pc"])
def test_si_aprono(m):
    at = _admin(m)
    assert not at.exception, [e.value for e in at.exception]


def test_pagina_pubblica_senza_login():
    t, i = pc.crea("Famiglia Verdi", oggi=dt.date.today())
    c = pc.contenuto_vuoto()
    c.update(stato_testo="Posati i pannelli", avanzamento=40)
    pc.salva_contenuto(i, c, "a")
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params["cliente"] = t
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    testo = " ".join(m.value for m in at.markdown)
    assert "Famiglia Verdi" in testo and "Posati i pannelli" in " ".join(m.value for m in at.markdown) and not at.sidebar.button
    at2 = AppTest.from_file(APP, default_timeout=120)
    at2.query_params["cliente"] = "x" * 30
    at2.run()
    assert not at2.exception and any(pc.MSG_NON_VALIDO in i.value for i in at2.info)
