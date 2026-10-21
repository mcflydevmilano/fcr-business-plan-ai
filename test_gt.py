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
