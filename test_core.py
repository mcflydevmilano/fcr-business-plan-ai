import math

import pytest

import core
from core import (
    DATI_DEFAULT, PIANO_DEFAULT, SOGLIE_DEFAULT, analisi_commesse, calcola_rating, commesse_vuote,
    esegui_scenario, fmt_eur, fmt_num, fmt_x, leva_minima, livello_classe, normalizza_estrazione,
    proietta, ratio, stress_test, to_float, valida_dati, verifica_covenant,
)


def test_to_float_formati():
    assert to_float("1.234.567,89") == pytest.approx(1234567.89)
    assert to_float("1234,5") == pytest.approx(1234.5)
    assert to_float("(500)") == -500
    assert to_float("1.234.567") == 1234567
    assert to_float("abc", 7) == 7
    assert to_float(None, 3) == 3
    assert to_float(True, 9) == 9


def test_formattazione_italiana():
    assert fmt_num(1234567.891, 2) == "1.234.567,89"
    assert fmt_eur(1000) == "1.000 EUR"
    assert fmt_x(math.inf) == "n.s."
    assert fmt_x(None) == "n.d."


def test_ratio_sicuro():
    assert ratio(100, 50) == 2
    assert math.isinf(ratio(100, 0))
    assert ratio(-100, 0) == 0.0


def test_normalizza_estrazione_migliaia_e_storico():
    raw = {
        "anno_riferimento": "2025", "ricavi": "2.500", "ebitda": 300, "patrimonio_netto": 800,
        "totale_attivo": 3000, "pfn": 600, "valori_in_migliaia": True,
        "storico": [{"anno": 2024, "ricavi": 2400, "ebitda": 280, "patrimonio_netto": 700, "pfn": 650},
                    {"anno": 2025, "ricavi": 1}],           # l'anno base va scartato
        "fonti": {"ricavi": "pag. 3"},
    }
    dati, storico, fonti = normalizza_estrazione(raw)
    assert dati["ricavi"] == 2_500_000
    assert dati["pfn"] == 600_000
    assert len(storico) == 1 and storico[0]["ricavi"] == 2_400_000
    assert fonti["ricavi"] == "pag. 3"
    assert "NON TROVATO" in fonti["utile_netto"]


def test_normalizza_rifiuta_non_dict():
    with pytest.raises(ValueError):
        normalizza_estrazione("testo")


def test_valida_dati_segnala_incoerenze():
    d = dict(DATI_DEFAULT, ebitda=10_000_000.0)
    assert any("EBITDA supera i ricavi" in w for w in valida_dati(d))
    assert valida_dati(DATI_DEFAULT) == []


def test_proiezione_coerente_con_fcf():
    p = dict(PIANO_DEFAULT)
    righe = proietta(2_500_000, 300_000, 600_000, p, 2025)
    pfn_prev = 600_000
    for r in righe:
        fcf = r["EBITDA"] - r["Imposte"] - r["Capex"] - r["Interessi"] - r["dCCN"]
        assert r["FCF"] == pytest.approx(fcf)
        assert r["PFN"] == pytest.approx(pfn_prev - fcf)
        pfn_prev = r["PFN"]
    assert righe[0]["Ricavi"] == pytest.approx(2_500_000 * 1.05)


def test_rimborso_non_cambia_pfn_ma_cambia_dscr():
    a = proietta(2_500_000, 300_000, 600_000, dict(PIANO_DEFAULT, rimborso=0), 2025)
    b = proietta(2_500_000, 300_000, 600_000, dict(PIANO_DEFAULT, rimborso=200_000), 2025)
    assert a[0]["PFN"] == pytest.approx(b[0]["PFN"])
    assert b[0]["DSCR"] < a[0]["DSCR"]


def test_pfn_puo_diventare_negativa():
    p = dict(PIANO_DEFAULT, capex=0, g_ebitda=30.0)
    righe = proietta(2_000_000, 800_000, 100_000, p, 2025)
    assert righe[-1]["PFN"] < 0


def test_rating_verde_giallo_rosso():
    verde = calcola_rating(100_000, 500_000, 2_000_000, 4_000_000, 2.0)
    assert livello_classe(verde["classe"]) == 2 and verde["punti"] == 8
    rosso = calcola_rating(5_000_000, 300_000, 800_000, 3_000_000, 0.8)
    assert livello_classe(rosso["classe"]) == 0
    # EBITDA negativo => sempre rosso
    neg = calcola_rating(0, -1, 1_000_000, 2_000_000, None)
    assert livello_classe(neg["classe"]) == 0


def test_soglie_personalizzate_cambiano_il_giudizio():
    stretto = dict(SOGLIE_DEFAULT, pfn_ebitda=(0.5, 1.0))
    base = calcola_rating(600_000, 300_000, 800_000, 3_000_000, 1.5)
    sev = calcola_rating(600_000, 300_000, 800_000, 3_000_000, 1.5, stretto)
    assert sev["punti"] < base["punti"]


def test_scenario_capitale_riduce_pfn_e_aumenta_pn():
    r = esegui_scenario(DATI_DEFAULT, {"delta_pn": 100_000}, PIANO_DEFAULT)
    assert r["scen"]["pfn"] == DATI_DEFAULT["pfn"] - 100_000
    assert r["scen"]["pn"] == DATI_DEFAULT["patrimonio_netto"] + 100_000


def test_leva_minima_raggiunge_il_target():
    dati = dict(DATI_DEFAULT, pfn=2_500_000.0, patrimonio_netto=600_000.0)
    corrente = esegui_scenario(dati, {}, PIANO_DEFAULT)
    assert livello_classe(corrente["rating"]["classe"]) < 2
    x = leva_minima(dati, {}, PIANO_DEFAULT, None, "delta_pn", "VERDE", step=10_000, massimo=5_000_000)
    assert x is not None and x > 0
    dopo = esegui_scenario(dati, {"delta_pn": x}, PIANO_DEFAULT)
    assert livello_classe(dopo["rating"]["classe"]) == 2
    prima = esegui_scenario(dati, {"delta_pn": x - 10_000}, PIANO_DEFAULT)
    assert livello_classe(prima["rating"]["classe"]) < 2     # minimo davvero minimo


def test_leva_minima_gia_soddisfatta_e_irraggiungibile():
    ok = dict(DATI_DEFAULT, pfn=0.0, patrimonio_netto=2_000_000.0)
    assert leva_minima(ok, {}, PIANO_DEFAULT, None, "delta_pn", "GIALLA") == 0
    perso = dict(DATI_DEFAULT, ebitda=-100_000.0)
    assert leva_minima(perso, {}, PIANO_DEFAULT, None, "delta_pn", "VERDE", massimo=50_000) is None


def test_stress_test_peggiora_i_risultati():
    righe = stress_test(DATI_DEFAULT, {}, PIANO_DEFAULT)
    assert righe[0]["Caso"] == "Scenario corrente"
    assert righe[2]["PFN/EBITDA anno 3"] > righe[0]["PFN/EBITDA anno 3"]
    assert righe[-1]["Punteggio"] <= righe[0]["Punteggio"]


def test_covenant():
    r = esegui_scenario(DATI_DEFAULT, {}, PIANO_DEFAULT)
    ok = verifica_covenant(r["piano"], {"pfn_ebitda_max": 99.0, "dscr_min": 0.0})
    assert all(x["Esito leva"] == "OK" and x["Esito DSCR"] == "OK" for x in ok)
    ko = verifica_covenant(r["piano"], {"pfn_ebitda_max": 0.0, "dscr_min": 99.0})
    assert all(x["Esito leva"] == "SFORATO" or x["PFN/EBITDA"] <= 0 for x in ko)
    assert all(x["Esito DSCR"] == "SFORATO" for x in ko)


def test_analisi_commesse():
    import pandas as pd
    df = pd.DataFrame(
        [
            {"Commessa": "A", "Cliente": "X", "Importo": 1000, "Avanzamento_pct": 50, "Fatturato": 400, "Incassato": 300, "Margine_pct": 10},
            {"Commessa": "B", "Cliente": "Y", "Importo": 1000, "Avanzamento_pct": 0, "Fatturato": 0, "Incassato": 0, "Margine_pct": 20},
        ]
    )
    kpi, cli = analisi_commesse(df, ricavi_base=2000)
    assert kpi["backlog"] == 1500
    assert kpi["da_fatturare"] == 100       # 500 eseguiti - 400 fatturati
    assert kpi["crediti"] == 100
    assert kpi["margine_backlog_pct"] == pytest.approx((500 * 10 + 1000 * 20) / 1500)
    assert kpi["top1_pct"] == 50
    assert kpi["copertura_ricavi"] == pytest.approx(0.75)
    assert analisi_commesse(commesse_vuote().iloc[0:0])[0] is None


def test_hash_stabile():
    assert core.hash_payload({"a": 1, "b": 2}) == core.hash_payload({"b": 2, "a": 1})
    assert core.hash_payload({"a": 1}) != core.hash_payload({"a": 2})


def test_numeri_sospetti():
    ctx = {"ricavi": 2_500_000.0, "pfn": 600_000.0, "rapporto": 2.0, "punti": 5}
    ok = "I ricavi sono 2.500.000 EUR e la PFN 600.000 EUR; il rapporto e' 2,00x nel 2025."
    assert core.numeri_sospetti(ok, ctx) == []
    ko = "I ricavi sono 2.500.000 EUR ma la PFN e' 1.234.567 EUR."
    assert core.numeri_sospetti(ko, ctx) == ["1.234.567"]
    assert core.numeri_sospetti("PFN di 600 mila euro e 2,5 milioni di ricavi", ctx) == []
