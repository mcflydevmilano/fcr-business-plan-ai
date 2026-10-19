import datetime as dt

import dd
import sc

OGGI = dt.date(2026, 10, 19)
RIGHE = [
    {"Tipo": "Attiva", "Controparte": "Rossi", "Importo": 10000, "Scadenza": "2026-10-01", "Documento": "1"},
    {"Tipo": "Attiva", "Controparte": "Bianchi", "Importo": 20000, "Saldato": 5000, "Scadenza": "2026-10-25"},
    {"Tipo": "Passiva", "Controparte": "Forn", "Importo": 8000, "Scadenza": "2026-10-22"},
    {"Tipo": "Passiva", "Controparte": "Forn2", "Importo": 3000, "Scadenza": "2026-10-10"},
]


def _out(**p):
    docs, _ = sc.normalizza_documenti(RIGHE)
    return docs, sc.calcola_sc(docs, {"oggi": OGGI, "cassa0": 1000, "fido": 5000, **p})


def test_normalizzazione_e_date():
    docs, av = sc.normalizza_documenti(RIGHE + [{"Tipo": "x", "Importo": 5, "Scadenza": "2026-10-10"}, {"Tipo": "inc", "Importo": 5, "Scadenza": "31/12/2026"},
                                                {"Tipo": "Attiva", "Importo": 5, "Scadenza": "boh"}])
    assert len(docs) == 5 and len(av) == 2
    assert docs[-1]["Scadenza"] == "2026-12-31"
    assert sc.data_da("19/10/26") == dt.date(2026, 10, 19)


def test_prima_settimana_e_totali():
    _, o = _out()
    s1 = o["settimane"][0]
    assert s1["Incassi"] == 5000 + 15000          # 50% dello scaduto Rossi + Bianchi (scade il 25, ultimo giorno della settimana 1)
    assert s1["Pagamenti"] == 11000               # entrambe le passive: una scaduta, una in settimana
    assert abs(s1["Cassa finale"] - 10000) < 1e-6
    k = o["kpi"]
    assert k["da_incassare"] == 25000 and k["da_pagare"] == 11000 and k["scaduto_attivo"] == 10000
    assert abs(k["ritardo_medio_gg"] - 18) < 1e-9 and k["ok_settimana"] and k["incerti"] == 5000


def test_cassa_cumulata_coerente_e_fido():
    _, o = _out(cassa0=-20000)
    cassa = -20000
    for r in o["settimane"]:
        cassa += r["Incassi"] - r["Pagamenti"]
        assert abs(r["Cassa finale"] - cassa) < 1e-6
    assert o["kpi"]["picco_fabbisogno"] > 0 and o["kpi"]["prima_settimana_fuori_fido"] == 1
    assert any("supera il fido" in a for a in o["avvisi"])


def test_ritardo_clienti_sposta_gli_incassi():
    docs, base = _out()
    _, tardi = _out(ritardo_attivo_gg=14)
    assert tardi["settimane"][0]["Incassi"] < base["settimane"][0]["Incassi"]
    righe = sc.confronto_ritardi(docs, {"oggi": OGGI, "cassa0": 1000, "fido": 5000})
    assert righe[0]["Ritardo clienti (gg)"] == 0 and len(righe) == 4


def test_fasce_e_solleciti():
    docs, o = _out()
    f = {x["Fascia"]: x for x in o["fasce"]}
    assert f["1-30 gg"]["Attive"] == 10000 and f["Non scaduto"]["Attive"] == 15000 and f["1-30 gg"]["Passive"] == 3000
    sol = sc.solleciti(docs, OGGI)
    assert len(sol) == 1 and sol[0]["Cliente"] == "Rossi" and sol[0]["Livello"].startswith("2")
    ogg, testo = sc.testo_sollecito(sol[0])
    assert "Rossi" in testo and "10.000" in testo and ogg == "Sollecito di pagamento"
    assert sc.livello_sollecito(10).startswith("1") and sc.livello_sollecito(60).startswith("3")


def test_saldato_oltre_importo_e_documento_chiuso():
    docs, _ = sc.normalizza_documenti([{"Tipo": "Attiva", "Importo": 100, "Saldato": 500, "Scadenza": "2026-10-01"}])
    assert docs[0]["Saldato"] == 100
    o = sc.calcola_sc(docs, {"oggi": OGGI})
    assert o["kpi"]["da_incassare"] == 0 and o["kpi"]["scaduto_attivo"] == 0


def test_semafori_e_stato_generale():
    docs, _ = sc.normalizza_documenti(RIGHE)
    m = {"sc": dd.metriche_sc({"docs": RIGHE, "params": {"cassa0": 1000, "fido": 5000}}, OGGI)}
    righe, gen, az = dd.semafori(m)
    st = {r["Indicatore"]: r["Stato"] for r in righe}
    assert st["Cassa a fine settimana 1"] == "ok"
    assert st["Crediti scaduti sul totale da incassare"] == "bad"      # 40% scaduto
    assert gen == "bad" and any("Sollecita" in a[1] for a in az)
    assert any(r["Stato"] == "nd" for r in righe)                      # moduli senza dati


def test_cruscotto_dai_payload_dei_moduli():
    import cf as cfm
    import pv as pvm
    cant = cfm.genera_portafoglio(10, 500000, 1, 3, 3, 50, 50, 30, 95)
    m = {"cf": dd.metriche_cf({"cantieri": cant, "params": {"fido": 1_000_000}}),
         "pv": dd.metriche_pv({"voci": [{"Descrizione": "Scavo", "Quantita": 10, "Manodopera": 100}], "params": {}}),
         "credit": dd.metriche_credit({"dati": {}}),
         "bp": dd.metriche_bp({"bp_ricavi_y1": 1_000_000.0, "bp_nome": "X"})}
    righe, gen, az = dd.semafori(m)
    st = {r["Indicatore"]: r["Stato"] for r in righe}
    assert st["Margine lordo del portafoglio cantieri"] == "bad"       # costi al 95%: margine 5%
    assert "Rating indicativo dell'azienda" in st and gen in ("ok", "warn", "bad")
    assert dd.conteggio(righe)["nd"] >= 1
