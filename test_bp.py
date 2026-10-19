import math

import pytest

import bp


def test_mutuo_francese_chiude_a_zero_e_rata_costante():
    s = bp.piano_mutuo(200_000, 4.5, 5, "francese")
    assert s[-1]["Debito residuo"] == pytest.approx(0, abs=1e-6)
    assert sum(r["Quota capitale"] for r in s) == pytest.approx(200_000)
    rate = [r["Rata"] for r in s]
    assert max(rate) - min(rate) < 1e-6
    assert s[0]["Interessi"] == pytest.approx(200_000 * 0.045)       # interessi sull'intero capitale il 1° anno
    assert s[1]["Interessi"] < s[0]["Interessi"]                        # poi calano con il debito residuo


def test_mutuo_italiano_e_tasso_zero():
    s = bp.piano_mutuo(100_000, 5, 4, "italiano")
    assert all(r["Quota capitale"] == pytest.approx(25_000) for r in s)
    assert s[-1]["Debito residuo"] == pytest.approx(0, abs=1e-6)
    z = bp.piano_mutuo(100_000, 0, 4)
    assert all(r["Interessi"] == 0 and r["Rata"] == pytest.approx(25_000) for r in z)
    assert all(r["Rata"] == 0 for r in bp.piano_mutuo(0, 4.5, 3))


def test_conto_economico_e_cassa_coerenti():
    o = bp.calcola_bp({})
    q = o["params"]
    cassa = q["equity"] + q["mutuo"] - q["capex"]
    prev_r = 0.0
    for r in o["anni"]:
        assert r["EBITDA"] == pytest.approx(r["Ricavi"] - r["Costi variabili"] - r["Personale"] - r["Altri costi"])
        assert r["EBIT"] == pytest.approx(r["EBITDA"] - r["Ammortamenti"])
        assert r["Utile ante imposte"] == pytest.approx(r["EBIT"] - r["Interessi"])
        assert r["Imposte"] == pytest.approx(max(0, r["Utile ante imposte"]) * q["aliquota"] / 100)
        assert r["Utile netto"] == pytest.approx(r["Utile ante imposte"] - r["Imposte"])
        assert r["Variazione CCN"] == pytest.approx((r["Ricavi"] - prev_r) * q["ccn_pct"] / 100)
        assert r["FCF operativo"] == pytest.approx(r["EBITDA"] - r["Imposte"] - r["Variazione CCN"])
        cassa += r["FCF operativo"] - r["Interessi"] - r["Quota capitale"]
        assert r["Cassa finale"] == pytest.approx(cassa)
        assert r["PFN"] == pytest.approx(r["Debito residuo"] - r["Cassa finale"])
        servizio = r["Interessi"] + r["Quota capitale"]
        assert r["DSCR"] == pytest.approx(r["FCF operativo"] / servizio)
        prev_r = r["Ricavi"]
    assert o["anni"][1]["Ricavi"] == pytest.approx(o["anni"][0]["Ricavi"] * (1 + q["crescita"] / 100))


def test_orizzonte_da_3_a_5_anni_e_ammortamento_limitato():
    assert len(bp.calcola_bp({"n_anni": 5})["anni"]) == 5
    assert len(bp.calcola_bp({"n_anni": 9})["anni"]) == 5          # limitato a 5
    o = bp.calcola_bp({"n_anni": 5, "anni_amm": 3, "capex": 300_000})
    assert [round(r["Ammortamenti"]) for r in o["anni"]] == [100_000, 100_000, 100_000, 0, 0]


def test_nessuna_imposta_in_perdita_e_avvisi():
    o = bp.calcola_bp({"ricavi_y1": 400_000, "cv_pct": 70, "personale": 300_000, "costi_fissi": 100_000})
    assert o["anni"][0]["EBITDA"] < 0
    assert o["anni"][0]["Imposte"] == 0
    assert any("EBITDA dell'anno 1" in a for a in o["avvisi"])


def test_fonti_insufficienti_e_cassa_negativa_segnalate():
    o = bp.calcola_bp({"capex": 500_000, "mutuo": 100_000, "equity": 0})
    assert o["kpi"]["gap_fonti"] == pytest.approx(400_000)
    assert any("non coprono l'investimento" in a for a in o["avvisi"])
    assert o["kpi"]["cassa_iniziale"] == pytest.approx(-400_000)


def test_senza_debito_dscr_assente_e_payback():
    o = bp.calcola_bp({"mutuo": 0, "equity": 250_000})
    assert all(r["DSCR"] is None for r in o["anni"])
    assert o["kpi"]["dscr_min"] is None
    assert o["kpi"]["payback_anni"] is not None and 0 < o["kpi"]["payback_anni"] <= 3


def test_normalizza_assunzioni_limiti_e_alias():
    valori, mot, note = bp.normalizza_assunzioni({
        "ricavi_y1": "1.500.000", "crescita_pct": 250, "costi_variabili_pct": 55, "anni_ammortamento": 4.6,
        "chiave_inventata": 1, "capex": None, "motivazioni": {"capex": "stima", "xx": "ignora"}, "note": "Verificare"})
    assert valori["ricavi_y1"] == 1_500_000
    assert valori["crescita"] == 100.0                       # portato al limite massimo
    assert valori["cv_pct"] == 55.0 and valori["anni_amm"] == 5
    assert "chiave_inventata" not in valori and "capex" not in valori
    assert mot == {"capex": "stima"} and note == "Verificare"
    with pytest.raises(ValueError):
        bp.normalizza_assunzioni("testo")
