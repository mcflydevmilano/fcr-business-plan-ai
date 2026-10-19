import datetime as dt

import rp

OGGI = dt.date(2026, 10, 21)          # mercoledi'


def g(n):
    return (OGGI + dt.timedelta(days=n)).isoformat()


def rapp(d, cant, ore=40, pres=5, chi="Bianchi", lav="Getto solaio"):
    return {"Data": d, "Cantiere": cant, "Compilato_da": chi, "Meteo": "Sereno", "Presenti": pres, "Ore": ore, "Lavorazioni": lav, "Mezzi": "", "Note": ""}


def segn(d, cant, desc, gr="Media", stato="Aperta", scad=""):
    return {"Data": d, "Cantiere": cant, "Tipo": "Sicurezza", "Gravita": gr, "Descrizione": desc, "Responsabile": "Rossi", "Scadenza": scad, "Stato": stato}


def test_giorni_lavorativi():
    assert rp.giorni_lavorativi(dt.date(2026, 10, 16), dt.date(2026, 10, 19)) == 1      # ven -> lun
    assert rp.giorni_lavorativi(dt.date(2026, 10, 19), dt.date(2026, 10, 19)) == 0


def test_cantieri_senza_rapportino():
    r, _ = rp.normalizza_rapp([rapp(g(0), "Villa Lago"), rapp(g(-1), "Villa Lago"), rapp(g(-8), "Scuola"), rapp(g(-3), "Capannone"), rapp(g(-60), "Vecchio")])
    out = rp.calcola_rp(r, [], {"oggi": OGGI})
    per = {c["Cantiere"]: c for c in out["cantieri"]}
    assert per["Villa Lago"]["Stato"] == "ok" and per["Villa Lago"]["Rapportini"] == 2 and per["Villa Lago"]["Ore"] == 80
    assert per["Capannone"]["Stato"] == "warn"                  # lun-mar-mer: 3 giorni lavorativi dopo l'ultimo > soglia 2
    assert per["Scuola"]["Stato"] == "bad"
    assert "Vecchio" not in per                                  # fermo da oltre 30 giorni: non attivo
    assert out["kpi"]["cantieri_senza_rapporto"] == 2


def test_segnalazioni():
    s, _ = rp.normalizza_segn([segn(g(-2), "Villa", "Ponteggio senza parapetto", "Alta"), segn(g(-5), "Villa", "Consegna in ritardo", "Bassa", scad=g(-1)),
                               segn(g(-9), "Scuola", "Fessura", "Media", "Chiusa"), segn(g(-1), "Scuola", "Cartelli mancanti", "Bassa", scad=g(10))])
    out = rp.calcola_rp([], s, {"oggi": OGGI})
    k = out["kpi"]
    assert k["segn_aperte"] == 3 and k["segn_alte"] == 1 and k["segn_scadute"] == 1
    assert out["segnalazioni"][0]["Gravita"] == "Alta" and any("Ponteggio" in a for a in out["avvisi"])


def test_unisci_senza_perdere_i_dati_degli_altri():
    base = [{"Id": "a", "x": 1}, {"Id": "b", "x": 1}]
    db = base + [{"Id": "c", "x": 1}]                              # un collega ha aggiunto "c"
    mio = base + [{"Id": "d", "x": 1}]                             # io ho aggiunto "d"
    out = rp.unisci(db, mio, toccati={"d"})
    assert [r["Id"] for r in out] == ["a", "b", "c", "d"]
    mio2 = [{"Id": "a", "x": 1}, {"Id": "b", "x": 9}]             # ho modificato "b"; "c" e' di un altro
    assert {r["Id"]: r["x"] for r in rp.unisci(db, mio2, {"b"})} == {"a": 1, "b": 9, "c": 1}
    assert [r["Id"] for r in rp.unisci(db, [{"Id": "a", "x": 1}], set())] == ["a", "b", "c"]


def test_id_stabile_e_righe_invalide():
    r1, av = rp.normalizza_rapp([rapp(g(0), "A"), rapp(g(0), "A"), {"Data": "", "Cantiere": "B", "Ore": 5}])
    assert len(r1) == 1 and len(av) == 1 and r1[0]["Id"]
    assert rp.normalizza_rapp(r1)[0][0]["Id"] == r1[0]["Id"]
