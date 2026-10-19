import datetime as dt

import pytest

import sl

OGGI = dt.date(2026, 10, 19)
g = lambda n: (OGGI + dt.timedelta(days=n)).isoformat()


def _dati(avanz=50, costi_extra=None):
    com, _ = sl.normalizza_commesse([{"Commessa": "Villa Lago", "Cliente": "Rossi", "Contratto": 100000, "Varianti": 10000, "Costi_prev": 88000, "Avanz_reale_pct": avanz,
                                      "Ritenuta_pct": 5, "Anticipo_pct": 10, "Iva_pct": 10, "Gg_incasso": 30, "Inizio": g(-120), "Fine_prev": g(60)}])
    nomi = {c["Commessa"] for c in com}
    sal, _ = sl.normalizza_sal([{"Commessa": "Villa Lago", "Numero": "0", "Data": g(-118), "Avanzamento_pct": 0, "Incassato": 12100},
                                {"Commessa": "Villa Lago", "Numero": "1", "Data": g(-60), "Avanzamento_pct": 30, "Incassato": 0}], nomi)
    cos, _ = sl.normalizza_costi([{"Commessa": "Villa Lago", "Data": g(-50), "Fornitore": "A", "Importo": 40000, "Pagato": 30000},
                                  {"Commessa": "Villa Lago", "Data": g(-10), "Fornitore": "B", "Importo": 20000}] + (costi_extra or []), nomi)
    return com, sal, cos


def test_fatture_anticipo_e_sal():
    com, sal, cos = _dati()
    o = sl.calcola_sl(com, sal, cos, {"oggi": OGGI})
    a, s1 = o["fatture"]
    assert a["Tipo"] == "Anticipo" and a["Imponibile"] == 11000 and a["Totale"] == pytest.approx(12100) and a["Residuo"] == 0
    assert s1["Lordo"] == pytest.approx(33000) and s1["Recupero anticipo"] == pytest.approx(3300) and s1["Ritenuta"] == pytest.approx(1650)
    assert s1["Imponibile"] == pytest.approx(28050) and s1["Totale"] == pytest.approx(30855) and s1["Scaduta"] is True


def test_earned_value_e_margine_a_finire():
    com, sal, cos = _dati()
    d = sl.calcola_sl(com, sal, cos, {"oggi": OGGI})["commesse"][0]
    assert d["EV"] == pytest.approx(44000) and d["Costi sostenuti"] == 60000
    assert d["CPI"] == pytest.approx(44000 / 60000)
    assert d["Costi a finire (EAC)"] == pytest.approx(120000) and d["Margine finale previsto"] == pytest.approx(-10000)
    assert d["Margine atteso %"] == pytest.approx(20.0) and d["Stato"] == "bad"
    assert d["Fornitori scaduti"] == 0                      # il fornitore A e' a 50 giorni: 10.000 da pagare, scade a 60
    assert d["Da fatturare"] == pytest.approx(110000 * 0.5 - (39050 + 1650))


def test_commessa_in_linea_con_il_preventivo():
    com, sal, _ = _dati(avanz=60)
    nomi = {"Villa Lago"}
    cos, _ = sl.normalizza_costi([{"Commessa": "Villa Lago", "Data": g(-40), "Fornitore": "A", "Importo": 52800, "Pagato": 52800}], nomi)
    d = sl.calcola_sl(com, sal, cos, {"oggi": OGGI})["commesse"][0]
    assert d["CPI"] == pytest.approx(1.0) and d["Stato"] == "ok" and d["Margine finale %"] == pytest.approx(20.0)


def test_poco_avanzamento_usa_il_preventivo():
    com, sal, cos = _dati(avanz=3)
    d = sl.calcola_sl(com, sal, cos, {"oggi": OGGI})["commesse"][0]
    assert d["Costi a finire (EAC)"] == pytest.approx(max(88000, 60000))


def test_fornitori_scaduti_e_normalizzazioni():
    com, sal, cos = _dati(costi_extra=[{"Commessa": "Villa Lago", "Data": g(-100), "Fornitore": "C", "Importo": 5000, "Pagato": 1000}])
    d = sl.calcola_sl(com, sal, cos, {"oggi": OGGI, "gg_pagamento": 60})["commesse"][0]
    assert d["Fornitori scaduti"] == pytest.approx(4000)
    c2, av = sl.normalizza_commesse([{"Commessa": "", "Contratto": 5}, {"Commessa": "X", "Contratto": 0}, {"Commessa": "A", "Contratto": 10}, {"Commessa": "A", "Contratto": 20}])
    assert [c["Commessa"] for c in c2] == ["A"] and len(av) == 3
    s2, av2 = sl.normalizza_sal([{"Commessa": "Z", "Data": g(0)}, {"Commessa": "A", "Data": "boh"}], {"A"})
    assert s2 == [] and len(av2) == 2


def test_collegamenti_scadenzario_e_cash_flow():
    import cf
    import sc
    com, sal, cos = _dati()
    o = sl.calcola_sl(com, sal, cos, {"oggi": OGGI})
    righe = sl.per_scadenzario(o, cos)
    docs, av = sc.normalizza_documenti(righe)
    assert len(docs) == 4 and not av and all(d["Documento"].startswith("SL:") for d in docs)
    assert sum(1 for d in docs if d["Tipo"] == "Attiva") == 2
    cant = sl.per_cash_flow(o, com)
    puliti, _ = cf.normalizza_cantieri(cant)
    assert len(puliti) == 1 and puliti[0]["Inizio"] == 1 and puliti[0]["Contratto"] == 110000


def test_sal_con_avanzamento_decrescente_e_sovrafatturazione():
    com, _, _ = _dati(avanz=20)
    sal, _ = sl.normalizza_sal([{"Commessa": "Villa Lago", "Numero": "1", "Data": g(-60), "Avanzamento_pct": 40}, {"Commessa": "Villa Lago", "Numero": "2", "Data": g(-30), "Avanzamento_pct": 35}], {"Villa Lago"})
    o = sl.calcola_sl(com, sal, [], {"oggi": OGGI})
    assert any("inferiore al precedente" in a for a in o["avvisi"]) and any("sovrafatturazione" in a for a in o["avvisi"])
