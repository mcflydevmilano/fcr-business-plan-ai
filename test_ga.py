import datetime as dt

import pytest

import ga

OGGI = dt.date(2026, 10, 19)
g = lambda n: (OGGI + dt.timedelta(days=n)).isoformat()


def _dati():
    gare, _ = ga.normalizza_gare([
        {"Gara": "Scuola", "Ente": "Comune", "Importo_base": 1000000, "Scadenza": g(5), "Stato": "In preparazione", "Ribasso_pct": 10, "Costi_pct": 80, "Probabilita_pct": 30, "Costo_partecipazione": 2000},
        {"Gara": "Ponte", "Ente": "Provincia", "Importo_base": 500000, "Scadenza": g(-3), "Stato": "Da valutare", "Ribasso_pct": 20, "Costi_pct": 85, "Probabilita_pct": 20},
        {"Gara": "Strada", "Ente": "ANAS", "Importo_base": 300000, "Scadenza": g(-60), "Stato": "Vinta", "Ribasso_pct": 5, "Costi_pct": 80, "Probabilita_pct": 100}])
    doc, _ = ga.normalizza_doc([{"Gara": "Scuola", "Documento": "DGUE", "Scadenza": g(2), "Fatto": True}, {"Gara": "Scuola", "Documento": "Garanzia", "Scadenza": g(3), "Fatto": False},
                                {"Gara": "Fantasma", "Documento": "X"}], {"Scuola", "Ponte", "Strada"})
    return gare, doc


def test_margine_ribasso_massimo_e_valore_atteso():
    gare, doc = _dati()
    o = ga.calcola_ga(gare, doc, {"oggi": OGGI, "margine_target": 8})
    s = o["gare"][0]
    assert s["Offerta"] == pytest.approx(900000) and s["Margine"] == pytest.approx(100000) and s["Margine %"] == pytest.approx(11.111, abs=1e-2)
    # ribasso massimo: costi 800000 / (1-0.08) = 869565 -> ribasso 13,04%
    assert s["Ribasso massimo %"] == pytest.approx(13.043, abs=1e-2)
    assert s["Valore atteso"] == pytest.approx(0.3 * 100000 - 2000) and s["Consiglio"] == "Conviene partecipare"
    p = o["gare"][1]
    assert p["Margine"] == pytest.approx(400000 * 1 - 425000) and p["Consiglio"] == "Non conviene a queste condizioni"


def test_stati_scadenze_e_documenti():
    gare, doc = _dati()
    o = ga.calcola_ga(gare, doc, {"oggi": OGGI})
    assert len(doc) == 2                                              # il documento di una gara inesistente è scartato
    s, p, v = o["gare"]
    assert s["Stato"] == "bad" and s["Documenti mancanti"] == 1       # scade tra 5 giorni con un documento mancante
    assert p["Stato"] == "bad"                                        # scadenza superata, non presentata
    assert v["Stato"] == "ok"
    k = o["kpi"]
    assert k["scadute"] == 1 and k["in_scadenza"] == 1 and k["doc_mancanti"] == 1 and k["vinte"] == 1 and k["tasso_successo"] == 100.0
    assert any("scade tra 5 giorni" in a for a in o["avvisi"])


def test_gara_vinta_diventa_commessa():
    gare, doc = _dati()
    o = ga.calcola_ga(gare, doc, {"oggi": OGGI})
    r = ga.per_commesse(o, gare)
    assert len(r) == 1 and r[0]["Commessa"] == "Strada" and r[0]["Contratto"] == pytest.approx(285000) and r[0]["Costi_prev"] == pytest.approx(240000)
    import sl
    assert len(sl.normalizza_commesse(r)[0]) == 1
