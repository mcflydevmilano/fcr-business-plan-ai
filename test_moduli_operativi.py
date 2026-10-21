import datetime as dt

import pytest

import fo
import mz
import og
import sx

OGGI = dt.date(2026, 10, 19)
g = lambda n: (OGGI + dt.timedelta(days=n)).isoformat()


def test_fornitori_documenti_contratti_confronto():
    docs, _ = fo.normalizza_docfo([{"Fornitore": "Alfa", "Documento": "DURC", "Scadenza": g(-5)}, {"Fornitore": "Alfa", "Documento": "SOA", "Scadenza": g(200)},
                                   {"Fornitore": "Beta", "Documento": "DURC", "Scadenza": g(10)}, {"Fornitore": "Gamma", "Documento": "DURC", "Scadenza": g(300)}, {"Fornitore": "", "Documento": "x"}])
    contr, _ = fo.normalizza_contratti([{"Fornitore": "Alfa", "Commessa": "Villa", "Importo": 100000, "Fatturato": 60000, "Pagato": 40000},
                                        {"Fornitore": "Beta", "Commessa": "Villa", "Importo": 50000, "Fatturato": 55000, "Pagato": 55000}])
    off, _ = fo.normalizza_offerte([{"Voce": "Impianto", "Fornitore": "Alfa", "Importo": 20000}, {"Voce": "Impianto", "Fornitore": "Gamma", "Importo": 24000},
                                    {"Voce": "Impianto", "Fornitore": "Beta", "Importo": 22000}])
    o = fo.calcola_fo(docs, contr, off, {"oggi": OGGI})
    assert len(docs) == 4
    f = {x["Fornitore"]: x for x in o["fornitori"]}
    assert f["Alfa"]["Stato"] == "bad" and f["Beta"]["Stato"] == "warn" and f["Gamma"]["Stato"] == "ok"
    assert f["Alfa"]["Residuo ordine"] == 40000 and f["Alfa"]["Da pagare"] == 20000
    assert o["kpi"]["sovrafatturati"] == 1 and o["kpi"]["doc_scaduti"] == 1
    c = o["confronto"][0]
    assert c["Più bassa"] == "Alfa" and c["Più bassa in regola"] == "Beta" and c["Minima"] == 20000 and c["Scarto %"] == pytest.approx(20.0)
    assert any("Alfa: ha documenti scaduti" in a for a in o["avvisi"]) and any("fornitore con documenti scaduti" in a for a in o["avvisi"])


def test_sicurezza_persone_e_cantieri():
    pers, _ = sx.normalizza_pers([{"Persona": "Rossi", "Cantiere": "Villa", "Documento": "Visita medica", "Scadenza": g(-1)}, {"Persona": "Rossi", "Cantiere": "Villa", "Documento": "Corso", "Scadenza": g(100)},
                                  {"Persona": "Bianchi", "Cantiere": "Scuola", "Documento": "Corso", "Scadenza": g(15)}])
    docc, _ = sx.normalizza_docc([{"Cantiere": "Villa", "Documento": "PSC", "Presente": True}, {"Cantiere": "Villa", "Documento": "POS", "Presente": False},
                                  {"Cantiere": "Scuola", "Documento": "PSC", "Presente": True}])
    o = sx.calcola_sx(pers, docc, {"oggi": OGGI})
    c = {x["Cantiere"]: x for x in o["cantieri"]}
    assert c["Villa"]["Stato"] == "bad" and c["Villa"]["Documenti mancanti"] == 1 and c["Villa"]["Persone non in regola"] == 1
    assert c["Scuola"]["Stato"] == "warn"
    k = o["kpi"]
    assert k["persone_non_in_regola"] == 1 and k["doc_mancanti"] == 1 and k["cantieri_a_rischio"] == 1 and k["n_persone"] == 2


def test_mezzi_tariffa_utilizzo_e_costi():
    mezzi, _ = mz.normalizza_mezzi([{"Mezzo": "Escavatore", "Tipo": "Movimento terra", "Costo_fisso_annuo": 12000, "Costo_var_orario": 20, "Ore_annue_prev": 1000},
                                    {"Mezzo": "Gru", "Costo_fisso_annuo": 20000, "Costo_var_orario": 10, "Ore_annue_prev": 400}])
    nomi = {m["Mezzo"] for m in mezzi}
    uso, _ = mz.normalizza_uso([{"Mezzo": "Escavatore", "Commessa": "Villa", "Data": g(-30), "Ore": 400}, {"Mezzo": "Escavatore", "Commessa": "Scuola", "Data": g(-500), "Ore": 999},
                                {"Mezzo": "Gru", "Commessa": "Villa", "Data": g(-10), "Ore": 300}], nomi)
    sc, _ = mz.normalizza_scad([{"Mezzo": "Gru", "Documento": "Revisione", "Scadenza": g(-2)}], nomi)
    o = mz.calcola_mz(mezzi, uso, sc, {"oggi": OGGI})
    e = o["mezzi"][0]
    assert e["Tariffa oraria"] == pytest.approx(32.0) and e["Ore 12 mesi"] == 400 and e["Utilizzo %"] == pytest.approx(40.0)
    assert e["Costo imputato"] == pytest.approx(12800) and e["Fissi non assorbiti"] == pytest.approx(7200) and e["Stato"] == "warn"
    gr = o["mezzi"][1]
    assert gr["Tariffa oraria"] == pytest.approx(60.0) and gr["Stato"] == "bad"
    assert {c["Commessa"] for c in o["commesse"]} == {"Villa"}
    import sl
    righe = mz.per_sl_costi(o)
    assert len(righe) == 2 and sum(r["Importo"] for r in righe) == pytest.approx(12800 + 18000)
    assert sl.normalizza_costi(righe, {"Villa"})[0] and not sl.normalizza_costi(righe, {"Villa"})[1]


def test_organico_sovraccarico_e_ore_libere():
    ris, _ = og.normalizza_ris([{"Risorsa": "Squadra A", "Ruolo": "Muratori", "Costo_orario": 30, "Ore_mese": 160}, {"Risorsa": "Squadra B", "Ruolo": "Impiantisti", "Costo_orario": 40, "Ore_mese": 160}])
    nomi = {r["Risorsa"] for r in ris}
    ass, av = og.normalizza_ass([{"Risorsa": "Squadra A", "Commessa": "Villa", "Dal": "2026-10-01", "Al": "2026-11-30", "Ore_mese": 100},
                                 {"Risorsa": "Squadra A", "Commessa": "Scuola", "Dal": "2026-11-01", "Al": "", "Ore_mese": 120},
                                 {"Risorsa": "Squadra B", "Commessa": "Villa", "Dal": "2026-10-01", "Al": "2026-10-31", "Ore_mese": 80},
                                 {"Risorsa": "Fantasma", "Commessa": "X", "Dal": "2026-10-01", "Ore_mese": 10}], nomi)
    assert len(ass) == 3 and av
    o = og.calcola_og(ris, ass, {"oggi": OGGI, "mesi": 3})
    ott, nov, dic = o["mesi"]
    assert ott["Ore assegnate"] == 180 and ott["Capacità ore"] == 320 and ott["Stato"] == "warn"      # 56%: sotto il 60% di saturazione minima
    assert nov["Ore assegnate"] == 220 and nov["Ore extra necessarie"] == 60 and nov["Stato"] == "bad"  # Squadra A 100+120 > 160
    assert dic["Ore assegnate"] == 120
    assert o["kpi"]["mesi_sovraccarico"] == 1 and o["kpi"]["ore_extra_picco"] == 60
    assert nov["Costo assegnato"] == pytest.approx(220 * 30)
    assert o["commesse"][0]["Commessa"] == "Scuola"
