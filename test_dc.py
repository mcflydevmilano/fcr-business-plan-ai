"""Richiesta documenti: link segreto, caricamento, invio e pagina pubblica."""
import datetime as dt
import os
import tempfile

import pytest
from streamlit.testing.v1 import AppTest

import dc
import storage

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
OGGI = dt.date(2026, 11, 10)


@pytest.fixture(autouse=True)
def db(monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
    monkeypatch.setenv("APP_PASSWORD", "segreta")


def _admin(modulo):
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["utente"] = {"username": "root", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = modulo
    return at.run()


def _un_file(id_="v01"):
    return {"nome": "x.pdf", "tipo": "application/pdf", "dati": "ZmFrZQ=="}


def test_il_token_non_si_salva_e_la_validita():
    t, i = dc.crea("Condominio Rossi", 30, "admin", oggi=OGGI)
    assert t not in repr(storage.carica_pratica(dc.NOME_INDICE, modulo="cfg"))
    assert dc.trova(t, oggi=OGGI)[1] == "attivo"
    assert dc.trova(t[:-1] + ("a" if t[-1] != "a" else "b"), oggi=OGGI)[0] is None
    assert dc.trova(t, oggi=dt.date(2027, 1, 1))[1] == "scaduto"
    assert dc.trova("../../x")[1] == "non_valido" and dc.trova(None)[1] == "non_valido"
    dc.revoca(i)
    assert dc.trova(t, oggi=OGGI)[0] is None
    dc.proroga(i, 10, oggi=OGGI)
    assert dc.trova(t, oggi=OGGI)[1] == "attivo"


def test_le_voci_condizionali_partono_non_richieste():
    c = dc.contenuto_vuoto()
    assert c["voci"]["v01"]["richiesta"] is True            # voce normale
    assert c["voci"]["v20"]["richiesta"] is False            # perizia >=150k: condizionale
    assert c["voci"]["v22"]["richiesta"] is False            # cessione del credito: condizionale
    assert len(dc.ORDINE_VOCI) == 28


def test_non_si_invia_se_manca_qualcosa():
    t, i = dc.crea("Condominio Bianchi", oggi=OGGI)
    fatto, motivo = dc.invia(t, "Mario Rossi")
    assert fatto is False and "Mancano" in motivo
    c = dc.carica_contenuto(i)
    richieste = [k for k in dc.ORDINE_VOCI if c["voci"][k]["richiesta"]]
    for k in richieste:
        c["voci"][k]["file"] = [_un_file()]
    dc.salva_contenuto(i, c, "condominio")
    fatto, motivo = dc.invia(t, "Mario Rossi")
    assert fatto is True and motivo == ""
    c2 = dc.carica_contenuto(i)
    assert c2["inviata"] and c2["firmatario"] == "Mario Rossi"
    fatto2, motivo2 = dc.invia(t, "Mario Rossi")                  # non si invia due volte
    assert fatto2 is False and "già inviato" in motivo2


def test_voce_non_richiesta_non_blocca_e_riapri_sblocca():
    t, i = dc.crea("Condominio Verdi", oggi=OGGI)
    c = dc.carica_contenuto(i)
    for k in dc.ORDINE_VOCI:
        c["voci"][k]["richiesta"] = k == "v01"                    # solo una voce richiesta
    dc.salva_contenuto(i, c, "admin")
    assert dc.invia(t, "A")[0] is False                            # manca ancora v01
    c = dc.carica_contenuto(i)
    c["voci"]["v01"]["file"] = [_un_file()]
    dc.salva_contenuto(i, c, "condominio")
    assert dc.invia(t, "Anna Neri")[0] is True
    assert dc.carica_contenuto(i)["inviata"]
    dc.riapri(i, "admin")
    assert dc.carica_contenuto(i)["inviata"] is None
    assert dc.invia(t, "Anna Neri")[0] is True                    # dopo la riapertura si può rimandare


def test_si_apre():
    at = _admin("dc")
    assert not at.exception, [e.value for e in at.exception]


def test_pagina_pubblica_senza_login():
    t, i = dc.crea("Condominio Via Roma 12", oggi=OGGI)
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params["documenti"] = t
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    testo = " ".join(m.value for m in at.markdown)
    assert "Condominio Via Roma 12" in testo and not at.sidebar.button
    at2 = AppTest.from_file(APP, default_timeout=120)
    at2.query_params["documenti"] = "x" * 30
    at2.run()
    assert not at2.exception and any(dc.MSG_NON_VALIDO in i.value for i in at2.info)


def test_pagina_pubblica_mostra_inviata_senza_modulo():
    t, i = dc.crea("Condominio Gialli", oggi=OGGI)
    c = dc.carica_contenuto(i)
    for k in dc.ORDINE_VOCI:
        if c["voci"][k]["richiesta"]:
            c["voci"][k]["file"] = [_un_file()]
    dc.salva_contenuto(i, c, "condominio")
    dc.invia(t, "Mario Rossi")
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params["documenti"] = t
    at.run()
    assert not at.exception
    testo = " ".join(m.value for m in at.success)
    assert "Mario Rossi" in testo
