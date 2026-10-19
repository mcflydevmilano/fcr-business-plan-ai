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
    o = bp.calcola_bp({"fisco": "semplice"})
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
    o = bp.calcola_bp({"ricavi_y1": 400_000, "cv_pct": 70, "personale": 300_000, "costi_fissi": 100_000, "fisco": "semplice"})
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


# ----------------------------- fisco dettagliato, scenari, sensibilita' -----------------------------
def test_ires_irap_e_riporto_perdite():
    # anno 1 in perdita, poi utile: le perdite si riportano e riducono l'IRES (max 80% del reddito), l'IRAP resta dovuta
    p = {"fisco": "dettagliato", "n_anni": 4, "ricavi_y1": 600_000, "crescita": 80, "cv_pct": 50, "personale": 250_000,
         "costi_fissi": 100_000, "capex": 0, "mutuo": 0, "equity": 0, "ccn_pct": 0, "anni_amm": 5}
    o = bp.calcola_bp(p)
    r = o["anni"]
    assert r[0]["Utile ante imposte"] < 0 and r[0]["IRES"] == 0
    assert r[0]["Perdite fiscali residue"] == pytest.approx(-r[0]["Utile ante imposte"])
    persa = r[0]["Perdite fiscali residue"]
    pool = persa
    for x in r[1:]:
        if x["Utile ante imposte"] > 0:
            uso = min(pool, 0.8 * x["Utile ante imposte"])
            assert x["Perdite utilizzate"] == pytest.approx(uso)
            assert x["IRES"] == pytest.approx((x["Utile ante imposte"] - uso) * 0.24)
            pool -= uso
        assert x["IRAP"] == pytest.approx(max(0, x["EBIT"] + x["Personale"]) * 0.039)
        assert x["Imposte"] == pytest.approx(x["IRES"] + x["IRAP"])
    # senza riporto l'IRES e' piu' alta
    senza = bp.calcola_bp({**p, "riporto": False})
    assert sum(x["IRES"] for x in senza["anni"]) > sum(x["IRES"] for x in r)


def test_irap_dovuta_anche_in_perdita_e_deduzione_personale():
    p = {"fisco": "dettagliato", "ricavi_y1": 500_000, "cv_pct": 50, "personale": 150_000, "costi_fissi": 80_000, "capex": 0,
         "mutuo": 0, "equity": 0}
    base = bp.calcola_bp(p)["anni"][0]
    assert base["IRAP"] == pytest.approx((base["EBIT"] + 150_000) * 0.039)
    ded = bp.calcola_bp({**p, "irap_ded_pers": 100})["anni"][0]
    assert ded["IRAP"] == pytest.approx(max(0, ded["EBIT"]) * 0.039)


def test_scenari_ordinati_e_base_invariata():
    sc = bp.calcola_scenari({})
    assert list(sc) == ["Pessimistico", "Base", "Ottimistico"]
    assert sc["Base"]["anni"] == bp.calcola_bp({})["anni"]
    peg, bas, ott = (sc[n]["anni"][-1]["EBITDA"] for n in ("Pessimistico", "Base", "Ottimistico"))
    assert peg < bas < ott
    q = bp.applica_scenario({"ricavi_y1": 1_000_000, "tasso": 4.0}, {"ricavi_pct": -20, "tasso_pp": 1.5})
    assert q["ricavi_y1"] == pytest.approx(800_000) and q["tasso"] == pytest.approx(5.5)
    # lo scenario "Base" passato dall'utente viene ignorato (resta quello corrente)
    assert bp.calcola_scenari({}, {"Base": {"ricavi_pct": 50}})["Base"]["anni"] == bp.calcola_bp({})["anni"]
    assert len(bp.confronto_scenari(sc)) == 3


def test_sensibilita_tornado_e_griglia():
    r = bp.sensibilita({}, "cassa_minima")
    assert r and all(a["Impatto"] >= b["Impatto"] for a, b in zip(r, r[1:]))
    ric = next(x for x in r if x["chiave"] == "ricavi_y1")
    assert ric["Con valore maggiore"] >= ric["Con valore minore"]
    assert bp.sensibilita({"mutuo": 0}, "dscr_min") == []            # DSCR non definito senza finanziamento
    g = bp.griglia({}, "ricavi_y1", [1e6, 2e6], "cv_pct", [50, 60], "utile_cum")
    assert len(g) == 2 and len(g[0]) == 2 and g[0][1] > g[0][0] and g[0][0] > g[1][0]
