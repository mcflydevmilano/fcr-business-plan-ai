"""ESCo: diagnosi, modello dell'investimento, contratto EPC."""
import io
import zipfile

import pytest
from streamlit.testing.v1 import AppTest

import es
import permessi
import storage


def _bol(el=300, gas_inverno=120, gas_estate=10):
    b = es.bollette_vuote()
    for i, r in enumerate(b):
        inv = i < 5 or i > 9
        r.update(El_kWh=el, El_euro=el * 0.3, Gas_Smc=gas_inverno if inv else gas_estate, Gas_euro=(gas_inverno if inv else gas_estate) * 1.1)
    return b


def test_situazione_di_partenza_e_clima():
    p = {"mq": 300, "gg_anno": 2000, "gg_normali": 2200}
    b = es.situazione_di_partenza(_bol(), p)
    assert b["el_kwh"] == 3600 and b["prezzo_el"] == pytest.approx(0.3) and b["fattore_clima"] == 1.1
    assert b["gas_smc_corretto"] == round(b["gas_smc"] * 1.1) and b["kwh_m2"] == round(b["kwh_totali"] / 300, 1)
    senza = es.situazione_di_partenza(_bol())
    assert any("gradi giorno" in a for a in senza["avvisi"])


def test_anno_incompleto_si_porta_a_dodici_mesi():
    b = es.bollette_vuote()
    for r in b[:6]:
        r.update(El_kWh=100, El_euro=30)
    s = es.situazione_di_partenza(b)
    assert s["el_kwh"] == 1200 and any("6 mesi" in a for a in s["avvisi"])


def _piano(**extra):
    iv = es.normalizza_interventi([{"Intervento": "Relamping", "Tipo": "Illuminazione LED", "Investimento": 10000, "Risp_El_kWh": 12000, "Manutenzione": 100}])[0]
    base = es.situazione_di_partenza(_bol(el=2000), {})
    return iv, base, es.modello(iv, base, {"prezzo_el": 0.3, "quota_esco_pct": 70, "durata": 10, "debito_pct": 0, **extra})


def test_modello_senza_debito_quadra():
    iv, base, o = _piano()
    k = o["kpi"]
    assert k["risparmio_anno1"] == 3600 and k["ricavo_esco_anno1"] == 2520 and k["al_cliente_anno1"] == 1080
    assert k["garantito_anno1"] == 3240 and k["debito"] == 0 and k["rata"] == 0
    assert 4 <= k["rientro_anni"] <= 6 and k["van"] > 0 and k["tir"] > 10 and k["dscr_min"] is None
    assert o["flusso"][0]["Flusso ESCo €"] == 2520 - 100 and len(o["flusso"]) == 10


def test_debito_e_copertura():
    _, _, o = _piano(debito_pct=70, tasso_pct=5, durata_debito=8)
    k = o["kpi"]
    assert k["debito"] == 7000 and k["rata"] > 1000 and k["dscr_min"] > 1.2
    assert o["flusso"][0]["Rata debito €"] == -round(k["rata"]) and o["flusso"][9]["Rata debito €"] == 0
    _, _, duro = _piano(debito_pct=100, tasso_pct=12, durata_debito=3)
    assert any("Copertura" in a for a in duro["avvisi"])


def test_canone_fisso_e_avvisi():
    _, _, o = _piano(modello="Canone fisso", canone=5000)
    assert o["kpi"]["al_cliente_anno1"] < 0 and any("canone" in a for a in o["avvisi"])
    iv = es.normalizza_interventi([{"Intervento": "Gas", "Investimento": 1000, "Risp_Gas_Smc": 99999}])[0]
    assert any("gas superiore" in a for a in es.modello(iv, es.situazione_di_partenza(_bol()), {"prezzo_gas": 1})["avvisi"])


def test_interventi_incompleti_scartati_e_incentivi_in_piu_anni():
    ok, av = es.normalizza_interventi([{"Intervento": "x", "Investimento": 0}, {}, {"Intervento": "ok", "Investimento": "1.000", "Incentivo": 600, "Incentivo_anni": 3}])
    assert len(ok) == 1 and len(av) == 1 and ok[0]["Tipo"] == "Altro"
    o = es.modello(ok, {}, {"durata": 5, "debito_pct": 0, "quota_esco_pct": 0})
    assert [r["Incentivi €"] for r in o["flusso"]] == [200, 200, 200, 0, 0]


def test_bozza_contratto_word():
    iv, base, o = _piano()
    sez = es.bozza_epc({"cliente": "Condominio Rossi", "indirizzo": "Via Roma 1"}, iv, base, o)
    testo = " ".join(" ".join(p) for _, p in sez)
    assert "Condominio Rossi" in testo and "3.240" in testo and "70%" in testo and "IPMVP" in testo and len(sez) >= 12
    z = zipfile.ZipFile(io.BytesIO(es.docx_epc(sez)))
    assert "word/document.xml" in z.namelist()


def test_strumento_registrato_nei_profili():
    assert "es" in permessi.TUTTI and "es" in permessi.PROFILI_BASE["commerciale"] and "es" in permessi.NOMI


def test_modulo_si_apre_e_importa_il_fotovoltaico(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "e.db"))
    storage.svuota_cache()
    import fv
    storage.salva_pratica("Rossi FV", {"voci": fv.voci_standard(fv.FV_DEFAULT), "params": fv.FV_DEFAULT}, modulo="fv")
    at = AppTest.from_file("app.py", default_timeout=90)
    at.session_state["utente"] = {"username": "admin", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = "es"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    at.selectbox(key="es_da_fv").set_value("Rossi FV").run()
    next(b for b in at.button if b.key == "es_da_fv_ok").click().run()
    assert not at.exception
    r = at.session_state["es_int"]
    assert len(r) == 1 and r.iloc[0]["Tipo"] == "Fotovoltaico" and r.iloc[0]["Investimento"] > 0 and r.iloc[0]["Risp_El_kWh"] > 0
