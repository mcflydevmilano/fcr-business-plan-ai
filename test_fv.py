"""Preventivo fotovoltaico: calcoli, listino, collegamento con l'Offerta."""
import io

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import fv
import storage


def _base(**k):
    p = dict(fv.FV_DEFAULT)
    p.update(k)
    return p


def test_calcolo_quadra_a_mano():
    p = _base(ricarico_pct=20, iva_pct=10, detrazione_pct=50)
    voci = [{"Voce": "Tutto", "Quantita": 1, "Um": "corpo", "Costo_unit": 10000.0}]
    o = fv.calcola(voci, p)
    k = o["kpi"]
    assert k["imponibile"] == 12000.0 and k["iva"] == 1200.0 and k["totale"] == 13200.0
    assert k["detrazione"] == 6600.0 and k["netto_detrazione"] == 6600.0 and k["margine"] == 2000.0
    assert len(o["flusso"]) == 25
    assert sum(r["Detrazione €"] for r in o["flusso"]) == 6600


def test_tetto_di_spesa_della_detrazione():
    voci = [{"Voce": "Grande", "Quantita": 1, "Um": "corpo", "Costo_unit": 200000.0}]
    o = fv.calcola(voci, _base(ricarico_pct=0, iva_pct=0, detrazione_pct=50))
    assert o["kpi"]["detrazione"] == 48000.0 and any("tetto" in a or "96" in a for a in o["avvisi"])


def test_orientamento_e_ombre_riducono_la_produzione():
    v = fv.normalizza_voci(fv.voci_standard(_base()))[0]
    sud = fv.calcola(v, _base())["kpi"]["produzione"]
    assert fv.calcola(v, _base(orientamento="Est / Ovest"))["kpi"]["produzione"] < sud
    assert fv.calcola(v, _base(ombra_pct=20))["kpi"]["produzione"] == pytest.approx(sud * 0.8, abs=1)


def test_rientro_e_regime_azienda():
    v = fv.normalizza_voci(fv.voci_standard(_base()))[0]
    privato = fv.calcola(v, _base())["kpi"]["rientro_anni"]
    azienda = fv.calcola(v, _base(**fv.REGIMI["Azienda o altro uso (nessuna detrazione, IVA 22%)"]))["kpi"]["rientro_anni"]
    assert privato and azienda and azienda > privato


def test_voci_standard_con_batteria_e_righe_vuote():
    v = fv.voci_standard(_base(accumulo_kwh=5))
    assert any("Batteria" in x["Voce"] for x in v) and not any("Batteria" in x["Voce"] for x in fv.voci_standard(_base()))
    ok, av = fv.normalizza_voci([{"Voce": "", "Quantita": 0, "Costo_unit": 0}, {"Voce": "x", "Quantita": 0, "Costo_unit": 5}, {"Voce": "ok", "Quantita": "2", "Costo_unit": "1.234,50"}])
    assert len(ok) == 1 and ok[0]["Costo_unit"] == 1234.5 and len(av) == 1


def test_listino_letto_cosi_com_e():
    df = pd.DataFrame([["Listino 2026", None, None, None], ["Cod.", "Descrizione prodotto", "UM", "Prezzo netto"],
                       ["M1", "Modulo 430W", "pz", "112,50"], ["I1", "Inverter 5kW", "pz", "980"], [None, "Totale", None, None]])
    buf = io.BytesIO()
    df.to_excel(buf, header=False, index=False)
    righe, av = fv.leggi_listino(buf.getvalue(), "l.xlsx")
    assert [r["Descrizione"] for r in righe] == ["Modulo 430W", "Inverter 5kW"] and righe[0]["Costo_unit"] == 112.5 and righe[0]["Codice"] == "M1"
    csv = b"Descrizione;Prezzo;UM\nBatteria 5kWh;2400;pz\n"
    r2, _ = fv.leggi_listino(csv, "l.csv")
    assert r2 and r2[0]["Costo_unit"] == 2400.0
    assert fv.leggi_listino(b"non e' un file", "x.xlsx")[0] == []


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "f.db"))
    storage.svuota_cache()


def test_modulo_si_apre_e_manda_il_prezzo_all_offerta(db):
    at = AppTest.from_file("app.py", default_timeout=90)
    at.session_state["utente"] = {"username": "admin", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = "fv"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    b = next(x for x in at.button if x.key == "fv_to_of")
    b.click().run()
    assert not at.exception
    voci = at.session_state["of_voci"]
    assert (voci["Cap"] == "FV").sum() == 1 and float(voci.loc[voci["Cap"] == "FV", "Prezzo"].iloc[0]) > 0
    next(x for x in at.button if x.key == "fv_to_of").click().run()
    assert (at.session_state["of_voci"]["Cap"] == "FV").sum() == 1                     # secondo invio: sostituisce, non raddoppia
