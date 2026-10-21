import datetime as dt

import gt

OGGI = dt.date(2026, 10, 21)
g = lambda n: (OGGI + dt.timedelta(days=n)).isoformat()


def fase(c, f, a, b, av):
    return {"Commessa": c, "Fase": f, "Inizio": g(a), "Fine": g(b), "Avanzamento": av, "Responsabile": ""}


def calc(righe, **p):
    fasi, _ = gt.normalizza_fasi(righe)
    return gt.calcola_gt(fasi, {"oggi": OGGI, **p})


def test_stati_delle_fasi():
    out = calc([fase("A", "Scavi", -50, 0, 100), fase("A", "Strutture", -40, 40, 50), fase("A", "Impianti", -40, 40, 10), fase("A", "Finiture", 10, 60, 0), fase("B", "Tetto", -60, -10, 80)])
    st = {f["Fase"]: f["Stato"] for f in out["fasi"]}
    assert st == {"Scavi": "done", "Strutture": "ok", "Impianti": "bad", "Finiture": "wait", "Tetto": "bad"}
    tetto = next(f for f in out["fasi"] if f["Fase"] == "Tetto")
    assert tetto["Ritardo gg"] == 10 and tetto["Prevista"] == 100.0
    assert out["kpi"]["fasi_critiche"] == 2 and any("Tetto" in a for a in out["avvisi"])


def test_stima_fine_e_commessa():
    out = calc([fase("A", "Strutture", -50, 50, 25)])            # a meta' tempo (50%) ha fatto il 25%: ritmo 0,5 -> durata 200 gg
    f = out["fasi"][0]
    assert f["Fine stimata"] == g(150) and f["Stato"] == "warn" and f["Scostamento"] == -25.0


def test_commessa_pesata_e_importi_da_altri_moduli():
    out = calc([fase("A", "Corta", -10, 0, 100), fase("A", "Lunga", -40, 60, 40)])
    c = out["commesse"][0]
    assert c["Fasi"] == 2 and c["Inizio"] == g(-40) and c["Fine"] == g(60) and 45 < c["Avanzamento"] < 46
    com = [{"Commessa": "Villa", "Inizio": g(-30), "Fine_prev": g(90), "Avanz_reale_pct": 20}, {"Commessa": "Senza date"}]
    f = gt.fasi_da_commesse_sl(com)
    assert len(f) == 1 and f[0]["Avanzamento"] == 20.0
    a = gt.fasi_da_assegnazioni([{"Risorsa": "Squadra A", "Commessa": "Villa", "Dal": g(0), "Al": ""}])
    assert a[0]["Fase"] == "Squadra A" and a[0]["Fine"] == g(365)


def test_righe_invalide_e_date_invertite():
    fasi, av = gt.normalizza_fasi([{"Commessa": "A", "Fase": "x", "Inizio": g(10), "Fine": g(0), "Avanzamento": 150}, {"Commessa": "", "Inizio": g(0), "Fine": g(5)}])
    assert len(fasi) == 1 and fasi[0]["Inizio"] == g(0) and fasi[0]["Avanzamento"] == 100.0 and len(av) == 2


def test_legami_slittamento_a_catena():
    g = lambda n: (OGGI + dt.timedelta(days=n)).isoformat()
    righe = [
        {"Commessa": "V", "Fase": "A", "Inizio": g(-50), "Fine": g(40), "Avanzamento": 35},
        {"Commessa": "V", "Fase": "B", "Inizio": g(41), "Fine": g(111), "Avanzamento": 0, "Dopo": "A"},
        {"Commessa": "V", "Fase": "C", "Inizio": g(111), "Fine": g(201), "Avanzamento": 0, "Dopo": "B"},
        {"Commessa": "V", "Fase": "D", "Inizio": g(0), "Fine": g(10), "Avanzamento": 0, "Dopo": "Z; D; "},
    ]
    out = calc(righe)
    f = {x["Fase"]: x for x in out["fasi"]}
    assert f["A"]["Fine stimata"] > g(40)
    assert f["B"]["Slitta gg"] > 0 and f["B"]["Inizio stimato"] == f["A"]["Fine stimata"]
    assert f["C"]["Slitta gg"] == f["B"]["Slitta gg"] > 0                  # il ritardo si propaga a catena
    assert f["B"]["Stato"] == "warn" and "«A»" in f["B"]["Motivo"]
    assert any("non esiste" in a for a in out["avvisi"]) and any("se stessa" in a for a in out["avvisi"])
    assert out["kpi"]["fasi_slittate"] == 2


def test_legami_ciclo_e_sequenza():
    g = lambda n: (OGGI + dt.timedelta(days=n)).isoformat()
    righe = [{"Commessa": "V", "Fase": "A", "Inizio": g(0), "Fine": g(10), "Avanzamento": 0, "Dopo": "B"},
             {"Commessa": "V", "Fase": "B", "Inizio": g(10), "Fine": g(20), "Avanzamento": 0, "Dopo": "A"}]
    out = calc(righe)
    assert any("giro chiuso" in a for a in out["avvisi"])
    seq = gt.in_sequenza([{"Commessa": "V", "Fase": "B", "Inizio": g(20), "Fine": g(30), "Dopo": ""}, {"Commessa": "V", "Fase": "A", "Inizio": g(0), "Fine": g(10), "Dopo": ""}])
    assert seq[0]["Dopo"] == "A" and seq[1]["Dopo"] == ""


def test_attese_vincoli_e_fermi():
    righe = [
        {"Commessa": "V", "Fase": "A", "Inizio": g(-10), "Fine": g(20), "Avanzamento": 33},
        {"Commessa": "V", "Fase": "B", "Inizio": g(10), "Fine": g(40), "Avanzamento": 0, "Dopo": "A +5"},
        {"Commessa": "V", "Fase": "C", "Inizio": g(0), "Fine": g(10), "Avanzamento": 0, "Dopo": "A -10"},
        {"Commessa": "V", "Fase": "D", "Inizio": g(5), "Fine": g(15), "Avanzamento": 0, "NonPrima": g(30)},
    ]
    fasi, _ = gt.normalizza_fasi(righe)
    out0 = gt.calcola_gt(fasi, {"oggi": OGGI})
    f = {x["Fase"]: x for x in out0["fasi"]}
    assert f["B"]["Inizio stimato"] == (OGGI + dt.timedelta(days=(dt.date.fromisoformat(f["A"]["Fine stimata"]) - OGGI).days + 5)).isoformat()   # attesa +5
    assert f["C"]["Inizio stimato"] < f["A"]["Fine stimata"]                                                                                          # anticipo -10
    assert f["D"]["Inizio stimato"] == g(30) and f["D"]["Slitta gg"] == 25 and "non prima del" in f["D"]["Motivo"]
    fermi, _ = gt.normalizza_fermi([{"Commessa": "Tutti", "Dal": g(5), "Al": g(14), "Motivo": "Ferie"}])
    out1 = gt.calcola_gt(fasi, {"oggi": OGGI}, fermi)
    f1 = {x["Fase"]: x for x in out1["fasi"]}
    assert f1["A"]["Giorni di fermo"] >= 1 and f1["A"]["Fine stimata"] > f["A"]["Fine stimata"]                                                         # il fermo allunga A
    assert f1["B"]["Inizio stimato"] > f["B"]["Inizio stimato"]                                                                                         # e B slitta
    nuove = gt.festivita_italiane(2026)
    assert "2026-04-06" in [x["Dal"] for x in nuove] and "2026-12-25" in [x["Dal"] for x in nuove]                                                      # Pasquetta 2026 = 6 aprile
