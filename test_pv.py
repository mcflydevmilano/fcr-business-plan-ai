import pandas as pd
import pytest

import pv

VOCI = [
    {"Codice": "A1", "Categoria": "Opere murarie", "Descrizione": "Demolizione", "UM": "mq", "Quantita": 100, "Materiali": 0, "Manodopera": 20, "Noli_altro": 5},
    {"Codice": "B1", "Categoria": "Isolamento", "Descrizione": "Cappotto 12 cm", "UM": "mq", "Quantita": 500, "Materiali": 30, "Manodopera": 25, "Noli_altro": 5},
]
P = {"sg_pct": 15, "utile_pct": 10, "sicurezza_pct": 2, "sconto_pct": 0, "iva_pct": 10, "margine_min_pct": 5}


def _voci():
    v, av = pv.normalizza_voci(VOCI)
    assert not av
    return v


def test_catena_dei_costi_e_dei_prezzi():
    o = pv.calcola_preventivo(_voci(), P)
    k = o["kpi"]
    cd = 100 * 25 + 500 * 60
    assert k["costi_diretti"] == pytest.approx(cd)
    assert k["spese_generali"] == pytest.approx(cd * 0.15) and k["costo_industriale"] == pytest.approx(cd * 1.15)
    assert k["listino"] == pytest.approx(cd * 1.15 * 1.10)
    assert k["prezzo_lavori"] == pytest.approx(k["listino"], abs=0.02)
    assert k["oneri_sicurezza"] == pytest.approx(k["listino"] * 0.02, abs=0.01)
    assert k["imponibile"] == pytest.approx(k["prezzo_lavori"] + k["oneri_sicurezza"], abs=0.01)
    assert k["iva"] == pytest.approx(k["imponibile"] * 0.10, abs=0.01) and k["totale"] == pytest.approx(k["imponibile"] + k["iva"], abs=0.01)
    assert k["utile"] == pytest.approx(k["costo_industriale"] * 0.10, abs=0.02)
    assert k["margine_pct"] == pytest.approx(k["utile"] / k["imponibile"] * 100)
    assert sum(r["Prezzo"] for r in o["voci"]) == pytest.approx(k["prezzo_lavori"])          # il cliente vede la stessa somma
    assert sum(c["Costo"] for c in o["categorie"]) == pytest.approx(cd)


def test_sconto_riduce_prezzo_e_margine_ma_non_gli_oneri_di_sicurezza():
    base = pv.calcola_preventivo(_voci(), P)["kpi"]
    sc = pv.calcola_preventivo(_voci(), {**P, "sconto_pct": 5})["kpi"]
    assert sc["prezzo_lavori"] == pytest.approx(base["prezzo_lavori"] * 0.95, abs=0.05)
    assert sc["oneri_sicurezza"] == pytest.approx(base["oneri_sicurezza"])                 # non ribassabili
    assert sc["utile"] < base["utile"] and sc["sconto"] == pytest.approx(base["listino"] * 0.05, abs=0.05)


def test_sconto_massimo_mantiene_il_margine_minimo():
    o = pv.calcola_preventivo(_voci(), P)
    smax = o["kpi"]["sconto_max_pct"]
    assert 0 < smax < 20
    al_limite = pv.calcola_preventivo(_voci(), {**P, "sconto_pct": smax})["kpi"]
    assert al_limite["margine_pct"] == pytest.approx(P["margine_min_pct"], abs=0.05)
    oltre = pv.calcola_preventivo(_voci(), {**P, "sconto_pct": smax + 3})
    assert oltre["kpi"]["margine_pct"] < P["margine_min_pct"] and any("supera quello massimo" in a for a in oltre["avvisi"])


def test_preventivo_in_perdita_e_sensibilita_costi():
    o = pv.calcola_preventivo(_voci(), {**P, "sconto_pct": 40})
    assert o["kpi"]["utile"] < 0 and any("in perdita" in a for a in o["avvisi"])
    s = pv.sensibilita_costi(_voci(), P)
    assert [r["Variazione costi %"] for r in s][:3] == [-10, -5, 0]
    zero = next(r for r in s if r["Variazione costi %"] == 0)
    assert zero["Utile"] == pytest.approx(pv.calcola_preventivo(_voci(), P)["kpi"]["utile"], abs=0.02)
    assert all(a["Margine %"] > b["Margine %"] for a, b in zip(s, s[1:]))
    x = pv.costi_massimi_aumento(_voci(), P)                                              # aumento dei costi che azzera l'utile
    az = pv.sensibilita_costi(_voci(), P, variazioni=(x,))[0]
    assert az["Utile"] == pytest.approx(0, abs=1)


def test_normalizzazione_voci():
    v, av = pv.normalizza_voci([
        {"Descrizione": "ok", "Quantita": "1.250,5", "Materiali": "10,5"},
        {"Descrizione": "senza quantita", "Quantita": 0, "Materiali": 5},
        {"Descrizione": "", "Quantita": 3, "Materiali": 2},
        {"Descrizione": "senza costi", "Quantita": 2},
        {}, {"Descrizione": None, "Quantita": None},
    ])
    assert [x["Descrizione"] for x in v] == ["ok", "Voce 2", "senza costi"]
    assert v[0]["Quantita"] == pytest.approx(1250.5) and v[0]["Materiali"] == pytest.approx(10.5) and v[0]["UM"] == "cad"
    assert any("quantita' nulla" in a for a in av) and any("manca la descrizione" in a for a in av) and any("nessun costo" in a for a in av)
    assert pv.calcola_preventivo([], P)["avvisi"] and pv.calcola_preventivo([], P)["kpi"]["totale"] == 0


def test_import_da_tabella_con_nomi_flessibili():
    df = pd.DataFrame({"Voce": ["Cappotto", "Infissi"], "Qta": [100, 10], "U.M.": ["mq", "cad"], "Costo unitario": [55, 800]})
    righe, av = pv.voci_da_dataframe(df)
    voci, _ = pv.normalizza_voci(righe)
    assert [v["Quantita"] for v in voci] == [100, 10] and voci[0]["Materiali"] == 55 and any("Materiali" in a for a in av)
    with pytest.raises(ValueError):
        pv.voci_da_dataframe(pd.DataFrame({"Nome": ["x"]}))


def test_voci_proposte_dall_ai():
    voci, note = pv.normalizza_voci_ai({"voci": [{"descrizione": "Cappotto", "quantita": 300, "um": "mq", "materiali": 30, "manodopera": 25},
                                                  "spazzatura", {"descrizione": "x", "quantita": 0}], "note": "stime"})
    assert len(voci) == 1 and voci[0]["Quantita"] == 300 and note == "stime"
    for bad in (None, {}, [], {"voci": []}, [{"descrizione": "x", "quantita": 0}]):
        with pytest.raises(ValueError):
            pv.normalizza_voci_ai(bad)


def test_passaggio_al_cash_flow():
    import cf
    o = pv.calcola_preventivo(_voci(), P)
    riga = pv.per_cash_flow(o, "Condominio Rossi", 2, 4, 30, 30, 45)
    assert riga["Contratto"] == pytest.approx(o["kpi"]["imponibile"])
    assert riga["Costi_pct"] / 100 * riga["Contratto"] == pytest.approx(o["kpi"]["costi_totali_impresa"])
    puliti, av = cf.normalizza_cantieri([riga])
    assert puliti and not av
    m = cf.calcola_cf(puliti, {"mesi": 12})["kpi"]["margine_lordo"]
    assert m == pytest.approx(o["kpi"]["utile"], abs=0.5)
