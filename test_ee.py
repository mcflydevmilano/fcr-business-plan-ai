"""Preventivi di efficienza energetica: sei tipi, stessa logica del fotovoltaico."""
import pytest
from streamlit.testing.v1 import AppTest

import ee
import es
import permessi
import storage


@pytest.mark.parametrize("tipo", list(ee.TIPI))
def test_ogni_tipo_ha_voci_costo_e_risparmio(tipo):
    p = ee.default_params(tipo)
    v = ee.voci_standard(tipo, p)
    assert v and all(x["Quantita"] > 0 and x["Costo_unit"] > 0 for x in v)
    o = ee.calcola(tipo, v, p)
    k = o["kpi"]
    assert k["imponibile"] > k["costo"] > 0 and k["totale"] > k["imponibile"] and k["risparmio_anno1"] > 0 and k["rientro_anni"]
    assert not o["avvisi"] and len(o["flusso"]) == 20 and o["stima"]["nota"]


def test_pompa_di_calore_toglie_gas_e_aggiunge_elettricita():
    s = ee.stima("pdc", {**ee.default_params("pdc"), "gas_smc": 2000, "rend_vecchio": 0.8, "scop": 3.5})
    assert s["risp_gas_smc"] == 2000 and s["risp_el_kwh"] == pytest.approx(-(2000 * 9.6 * 0.8) / 3.5)


def test_caldaia_cappotto_led_solare_colonnine_a_mano():
    assert ee.stima("cal", {"gas_smc": 1000, "rend_vecchio": 0.8, "rend_nuovo": 0.96})["risp_gas_smc"] == pytest.approx(1000 * (1 - 0.8 / 0.96))
    cap = ee.stima("cap", {"gas_smc": 99999, "rend_vecchio": 1.0, "mq_involucro": 100, "u_prima": 1.0, "u_dopo": 0.2, "gg": 2000})
    assert cap["risp_gas_smc"] == pytest.approx(0.8 * 100 * 2000 * 24 / 1000 / 9.6)
    assert ee.stima("cap", {"gas_smc": 100, "rend_vecchio": 1.0, "mq_involucro": 1000, "u_prima": 2, "u_dopo": 0.2, "gg": 3000})["risp_gas_smc"] == 100          # mai oltre il consumo
    led = ee.stima("led", {"punti": 100, "w_vecchi": 58, "w_nuovi": 22, "ore": 3000, "manut_risp": 150})
    assert led["risp_el_kwh"] == 10800 and led["ricavi_altri"] == 150
    sol = ee.stima("sol", {"persone": 4, "litri": 50, "copertura": 0.6, "rend_vecchio": 0.8})
    assert sol["risp_gas_smc"] == pytest.approx(4 * 50 * 4.186 * 35 / 3600 * 365 * 0.6 / 9.6 / 0.8)
    col = ee.stima("col", {"n": 4, "kwh_anno": 8000, "prezzo_vendita": 0.55, "costo_energia": 0.28, "gestione": 250})
    assert col["ricavi_altri"] == pytest.approx(4 * 8000 * 0.27) and col["manutenzione"] == 1000


def test_avvisi_quando_non_conviene():
    p = {**ee.default_params("cal"), "rend_nuovo": 0.7}
    assert any("rendimento" in a for a in ee.calcola("cal", ee.voci_standard("cal", p), p)["avvisi"])
    p = {**ee.default_params("col"), "prezzo_vendita": 0.2}
    assert any("colonnine non guadagnano" in a for a in ee.calcola("col", ee.voci_standard("col", p), p)["avvisi"])
    assert ee.default_params("led")["detrazione_pct"] == 0.0 and ee.default_params("pdc")["detrazione_pct"] == 50.0


def test_esporta_all_esco_con_consumo_elettrico_negativo():
    p = ee.default_params("pdc")
    o = ee.calcola("pdc", ee.voci_standard("pdc", p), p)
    riga = ee.intervento_per_esco("pdc", o["kpi"], o["stima"], "PdC Rossi")
    ok, av = es.normalizza_interventi([riga])
    assert not av and ok[0]["Risp_El_kWh"] < 0 and ok[0]["Risp_Gas_Smc"] == 2000 and ok[0]["Investimento"] == o["kpi"]["costo"]
    base = es.situazione_di_partenza([{"Mese": "Gennaio", "El_kWh": 400, "El_euro": 120, "Gas_Smc": 2000, "Gas_euro": 2200}] * 12)
    m = es.modello(ok, base, {"prezzo_el": 0.3, "prezzo_gas": 1.1})
    assert m["kpi"]["risparmio_anno1"] == pytest.approx(2000 * 1.1 - (-ok[0]["Risp_El_kWh"]) * 0.3, abs=1)


def test_registrato():
    assert "ee" in permessi.TUTTI and "ee" in permessi.PROFILI_BASE["commerciale"] and "ee" in permessi.NOMI


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "e.db"))
    storage.svuota_cache()
    at = AppTest.from_file("app.py", default_timeout=90)
    at.session_state["utente"] = {"username": "admin", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = "ee"
    return at.run()


def test_ui_tutti_i_tipi_e_collegamenti(app):
    at = app
    assert not at.exception, [e.value for e in at.exception]
    for t in ee.TIPI:
        at.selectbox(key="ee_tipo").set_value(t).run()
        assert not at.exception, (t, [e.value for e in at.exception])
        assert len(at.session_state["ee_df"]) >= 3
    at.selectbox(key="ee_tipo").set_value("led").run()
    next(b for b in at.button if b.key == "ee_to_of").click().run()
    assert (at.session_state["of_voci"]["Cap"] == "EE-led").sum() == 1
    next(b for b in at.button if b.key == "ee_to_of").click().run()
    assert (at.session_state["of_voci"]["Cap"] == "EE-led").sum() == 1
    next(b for b in at.button if b.key == "ee_to_es").click().run()
    assert not at.exception and at.session_state["es_int"].iloc[0]["Tipo"] == "Illuminazione LED"
    next(b for b in at.button if b.key == "ee_to_es").click().run()
    assert len(at.session_state["es_int"]) == 1


def test_salvataggio_e_riapertura_tengono_tipo_e_voci(app):
    at = app
    at.selectbox(key="ee_tipo").set_value("cap").run()
    at.text_input(key="sv_nome_ee").set_value("Condominio Verdi").run()
    next(b for b in at.button if b.key == "sv_salva_ee").click().run()
    assert not at.exception and storage.elenca_pratiche(modulo="ee")
    p = storage.carica_pratica("Condominio Verdi", modulo="ee")
    assert p["tipo"] == "cap" and p["voci"] and p["params"]["mq_involucro"] == 300
