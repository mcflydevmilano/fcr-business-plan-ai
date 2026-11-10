"""Computo di cantiere: formula dei prezzi aggiornati, dati di Sommacampagna, Excel, colonne aggiunte e interfaccia."""
import io
import os
import tempfile

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import cl
import storage

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")


@pytest.fixture(autouse=True)
def db(monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
    monkeypatch.setenv("APP_PASSWORD", "segreta")


def test_formula_come_nel_computo_del_comune():
    r = cl.normalizza([{"Codice E.P.U.": "E.13.002.00", "Quantità": "617,78", "Prezzo unitario €": 17.24, "Coefficiente": 1.05, "Prezzario nuovo €": 23.26, "% di aumento": 0.8}])[0]
    c = cl.calcola_riga(r)
    assert round(c["Totale da esecutivo €"], 2) == 10650.53 and round(c["F x I €"], 2) == 18.10 and round(c["Differenza €"], 2) == 5.16
    assert round(c["Aumento €"], 2) == 4.13 and round(c["Prezzo aggiornato €"], 2) == 21.37 and round(c["Totale aggiornato €"], 2) == 13199.73


def test_senza_prezzario_il_prezzo_resta_e_i_valori_a_mano_vincono():
    r = cl.normalizza([{"Descrizione": "x", "Quantità": 10, "Prezzo unitario €": 5}, {"Descrizione": "a corpo", "Totale esecutivo a mano €": 100, "Totale aggiornato a mano €": 150},
                       {"Descrizione": "istat", "Quantità": 2, "Prezzo unitario €": 10, "Prezzo aggiornato a mano €": 11.8}, {}, {"Descrizione": ""}])
    assert len(r) == 3
    o = cl.calcola(r)
    assert o["tot_esecutivo"] == 50 + 100 + 20 and o["tot_aggiornato"] == 50 + 150 + 23.6
    assert cl._n("1.234,56") == 1234.56 and cl._n("(8,82)") == -8.82 and cl._n("") is None and cl._n("€ 12,50") == 12.5


def test_il_computo_di_sommacampagna_torna_al_centesimo():
    e = cl.esempio()
    o = cl.calcola(cl.normalizza(e["voci"]))
    assert len(o["righe"]) == 55 and o["tot_esecutivo"] == 684155.49 and o["tot_aggiornato"] == 844141.38
    assert o["righe"][0]["Codice E.P.U."] == "E.13.002.00" and "finito a frattazzo" in o["righe"][0]["Descrizione"]


def test_excel_andata_e_ritorno_con_colonna_aggiunta():
    righe = cl.normalizza([dict(v, Subappaltatore="Edilmar") for v in cl.esempio()["voci"][:5]], ["Subappaltatore"])
    x = cl.excel_bytes(righe, ["Subappaltatore"])
    assert {"Computo", "Riepilogo", "Per capitolo", "Dati da reimportare"} <= set(pd.ExcelFile(io.BytesIO(x)).sheet_names)
    b = io.BytesIO()
    pd.read_excel(io.BytesIO(x), sheet_name="Dati da reimportare").to_excel(b, index=False)
    lette, extra, _ = cl.da_excel(b.getvalue())
    assert extra == ["Subappaltatore"] and len(lette) == 5 and lette[0]["Subappaltatore"] == "Edilmar"
    assert cl.calcola(lette)["tot_aggiornato"] == cl.calcola(righe)["tot_aggiornato"]
    vuoto = io.BytesIO()
    pd.DataFrame([["a", "b"], [1, 2]]).to_excel(vuoto, index=False, header=False)
    assert cl.da_excel(vuoto.getvalue())[0] == []
    assert cl.da_excel(cl.modello_excel())[0][0]["Codice E.P.U."] == "E.13.002.00"


def _admin():
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["utente"] = {"username": "root", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = "cl"
    return at.run()


def test_interfaccia_carica_sommacampagna_e_aggiunge_una_colonna():
    at = _admin()
    assert not at.exception, [e.value for e in at.exception]
    at.button(key="cl_esempio").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.session_state["cl_df"]) == 55 and at.session_state["cl_titolo"].startswith("Sommacampagna")
    assert any("844.141,38" in m.value for m in at.markdown)
    at.text_input(key="cl_col_nuova").set_value("Subappaltatore")
    at.button(key="cl_col_add").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Subappaltatore" in at.session_state["cl_df"].columns and at.session_state["cl_extra"] == ["Subappaltatore"]
    at.button(key="cl_col_del").click().run()
    assert "Subappaltatore" not in at.session_state["cl_df"].columns


def test_salva_e_riapre():
    import cl_ui  # noqa: F401
    e = cl.esempio()
    storage.salva_pratica("Sommacampagna", {"voci": e["voci"], "extra": ["Stato"], "campi": {"cl_titolo": "Somma"}}, autore="x", modulo="cl")
    assert storage.elenca_pratiche(modulo="cl")[0]["nome"] == "Sommacampagna"
    at = _admin()
    at.session_state["_apri_pratica"] = {"modulo": "cl", "nome": "Sommacampagna"}
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.session_state["cl_df"]) == 55 and "Stato" in at.session_state["cl_df"].columns and at.session_state["cl_titolo"] == "Somma"
