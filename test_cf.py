import math

import pytest

import cf


def _c(**kw):
    base = {"Cantiere": "A", "Contratto": 100_000, "Inizio": 1, "Durata": 4, "Anticipo_pct": 30, "Saldo_pct": 20, "Gg_incasso": 0, "Costi_pct": 70}
    base.update(kw)
    return cf.normalizza_cantieri([base])[0]


P0 = {"mesi": 12, "cassa0": 0, "fido": 1e9, "tasso_scoperto": 0, "costi_generali": 0, "gg_pagamento": 0}


def test_incassi_con_anticipo_sal_e_saldo():
    o = cf.calcola_cf(_c(), P0)
    inc = [r["Incassi"] for r in o["mesi"]]
    # anticipo 30% al mese 1; SAL = 50% in 4 rate da 12.500; saldo 20% al mese 4
    assert inc[0] == pytest.approx(30_000 + 12_500)
    assert inc[1] == pytest.approx(12_500) and inc[2] == pytest.approx(12_500)
    assert inc[3] == pytest.approx(12_500 + 20_000)
    assert sum(inc) == pytest.approx(100_000)
    assert o["kpi"]["pagamenti_tot"] == pytest.approx(70_000)
    assert o["kpi"]["cassa_finale"] == pytest.approx(30_000)


def test_ritardi_di_incasso_e_pagamento_spostano_i_flussi():
    o = cf.calcola_cf(_c(Gg_incasso=30), P0)
    inc = [r["Incassi"] for r in o["mesi"]]
    assert inc[0] == 0 and inc[1] == pytest.approx(42_500)
    # 45 giorni = 1,5 mesi: meta' nel mese +1, meta' nel mese +2
    o2 = cf.calcola_cf(_c(Gg_incasso=45), P0)
    assert o2["mesi"][1]["Incassi"] == pytest.approx(42_500 / 2) and o2["mesi"][2]["Incassi"] == pytest.approx(42_500 / 2 + 12_500 / 2)
    assert sum(r["Incassi"] for r in o2["mesi"]) == pytest.approx(100_000)
    o3 = cf.calcola_cf(_c(), {**P0, "gg_pagamento": 60})
    assert o3["mesi"][0]["Pagamenti"] == 0 and o3["mesi"][2]["Pagamenti"] == pytest.approx(17_500)


def test_flussi_oltre_orizzonte_non_si_perdono_in_silenzio():
    o = cf.calcola_cf(_c(Gg_incasso=300), {**P0, "mesi": 6})
    assert o["kpi"]["incassi_oltre_orizzonte"] > 0
    assert o["kpi"]["incassi_tot"] + o["kpi"]["incassi_oltre_orizzonte"] == pytest.approx(100_000)
    assert any("dopo l'orizzonte" in a for a in o["avvisi"])


def test_cassa_interessi_fido_e_picco():
    c = _c(Anticipo_pct=0, Saldo_pct=100, Costi_pct=80, Durata=3)
    o = cf.calcola_cf(c, {**P0, "tasso_scoperto": 12, "fido": 50_000, "costi_generali": 1_000})
    m = o["mesi"]
    assert m[0]["Cassa finale"] == pytest.approx(-(80_000 / 3) - 1_000)
    assert m[0]["Interessi"] == 0
    assert m[1]["Interessi"] == pytest.approx(-m[0]["Cassa finale"] * 0.01)       # 12% / 12 sul saldo negativo precedente
    assert o["kpi"]["picco_fabbisogno"] == pytest.approx(max(r["Utilizzo scoperto"] for r in m))
    assert o["kpi"]["primo_mese_fuori_fido"] is not None and any("supera il fido" in a for a in o["avvisi"])
    for i in range(1, len(m)):                                                      # coerenza cassa(t) = cassa(t-1) + flusso netto
        assert m[i]["Cassa finale"] == pytest.approx(m[i - 1]["Cassa finale"] + m[i]["Flusso netto"])


def test_portafoglio_generato_cento_cantieri_in_dodici_mesi():
    righe = cf.genera_portafoglio(100, 5_000_000, 1, 12, 3, 50, 50, 30, 75)
    assert len(righe) == 100 and sum(r["Contratto"] for r in righe) == pytest.approx(5_000_000)
    assert min(r["Inizio"] for r in righe) == 1 and max(r["Inizio"] for r in righe) == 12
    puliti, av = cf.normalizza_cantieri(righe)
    assert not av
    o = cf.calcola_cf(puliti, {"mesi": 24, "fido": 0, "costi_generali": 0})
    k = o["kpi"]
    assert k["n_cantieri"] == 100 and k["contratti"] == pytest.approx(5_000_000)
    assert k["margine_lordo"] == pytest.approx(1_250_000) and k["margine_lordo_pct"] == pytest.approx(25)
    assert k["incassi_tot"] == pytest.approx(5_000_000) and k["pagamenti_tot"] == pytest.approx(3_750_000)
    assert k["cassa_finale"] == pytest.approx(1_250_000 - o["kpi"]["interessi_totali"], abs=1)


def test_normalizzazione_scarta_e_corregge():
    puliti, av = cf.normalizza_cantieri([
        {"Cantiere": "ok", "Contratto": "100.000", "Inizio": 2, "Durata": 3, "Anticipo_pct": 70, "Saldo_pct": 60, "Gg_incasso": 30, "Costi_pct": 70},
        {"Cantiere": "zero", "Contratto": 0}, {}, {"Cantiere": "", "Contratto": None},
        {"Cantiere": "", "Contratto": 50_000, "Inizio": None, "Durata": None},
    ])
    assert len(puliti) == 2 and puliti[0]["Saldo_pct"] == 30
    assert puliti[1]["Inizio"] == 1 and puliti[1]["Durata"] == 1 and puliti[1]["Cantiere"].startswith("Cantiere")
    assert any("superano il 100%" in a for a in av) and any("contratto nullo" in a for a in av)


def test_stress_peggiora_il_fabbisogno_e_anticipo_minimo():
    c, _ = cf.normalizza_cantieri(cf.genera_portafoglio(20, 2_000_000, 1, 8, 4, 20, 40, 30, 78))
    p = {"mesi": 18, "fido": 100_000, "costi_generali": 15_000, "gg_pagamento": 30}
    st = cf.stress_cf(c, p)
    assert list(st)[0] == "Base"
    base = st["Base"]["kpi"]["picco_fabbisogno"]
    assert st["Incassi +60 giorni"]["kpi"]["picco_fabbisogno"] >= st["Incassi +30 giorni"]["kpi"]["picco_fabbisogno"] >= base
    assert st["Costi +10%"]["kpi"]["picco_fabbisogno"] >= base
    conf = cf.confronto_stress(st)
    assert conf[0]["Variazione picco"] == 0 and len(conf) == len(cf.STRESS_DEFAULT)
    a = cf.anticipo_minimo(c, p, soglia=0)
    if a is not None:
        mod = [{**x, "Anticipo_pct": float(a), "Saldo_pct": min(x["Saldo_pct"], 100.0 - a)} for x in c]
        assert cf.calcola_cf(mod, p)["kpi"]["picco_fabbisogno"] <= 1e-6


def test_portafoglio_vuoto_non_si_rompe():
    o = cf.calcola_cf([], {})
    assert o["kpi"]["n_cantieri"] == 0 and o["avvisi"] and len(o["mesi"]) == cf.CF_DEFAULT["mesi"]
