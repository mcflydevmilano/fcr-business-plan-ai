"""Test della Scheda cantiere (sk) e dei cantieri vivi nei rapportini."""
import datetime as dt

import pandas as pd
import pytest

import ru
import sk

OGGI = dt.date(2026, 11, 3)
g = lambda n: (OGGI + dt.timedelta(days=n)).isoformat()


def _payloads():
    return {
        "ru": {"cantieri": [{"Codice": "CAN-2026-001", "Cantiere": "Villa Lago", "Cliente": "Lago", "Stato": "In corso", "Esterno": "EXT-9"},
                            {"Codice": "CAN-2026-002", "Cantiere": "Scuola", "Stato": "Concluso"},
                            {"Codice": "CAN-2026-003", "Cantiere": "Capannone", "Stato": "In preparazione"}]},
        "sc": {"docs": [{"Tipo": "Attiva", "Controparte": "Lago", "Cantiere": "  villa   LAGO ", "Documento": "F1", "Scadenza": g(-5), "Importo": 1000, "Saldato": 400},
                        {"Tipo": "Attiva", "Controparte": "Lago", "Cantiere": "CAN-2026-001", "Documento": "F2", "Scadenza": g(20), "Importo": 500, "Saldato": 0},
                        {"Tipo": "Passiva", "Controparte": "Forn", "Cantiere": "EXT-9", "Documento": "P1", "Scadenza": g(5), "Importo": 300, "Saldato": 100},
                        {"Tipo": "Passiva", "Controparte": "Forn", "Cantiere": "Cantiere fantasma", "Documento": "P2", "Scadenza": g(5), "Importo": 50, "Saldato": 0}]},
        "rp": {"rapp": [{"Data": g(-1), "Cantiere": "Villa Lago", "Presenti": 3, "Ore": 24}, {"Data": g(-8), "Cantiere": "villa lago", "Presenti": 2, "Ore": 16}],
               "segn": [{"Data": g(-2), "Cantiere": "Villa Lago", "Descrizione": "Parapetto", "Stato": "Aperta"},
                        {"Data": g(-3), "Cantiere": "Villa Lago", "Descrizione": "Vecchia", "Stato": "Chiusa"}]},
    }


def test_riconosce_cantiere_da_nome_codice_e_codice_esterno():
    o = sk.calcola_sk(_payloads(), OGGI)
    s = next(x for x in o["schede"] if x["Codice"] == "CAN-2026-001")
    assert s["entrate"]["n"] == 2 and s["entrate"]["totale"] == 1500 and s["entrate"]["regolato"] == 400
    assert s["uscite"]["n"] == 1 and s["uscite"]["residuo"] == 200
    assert s["entrate"]["scaduto"] == 600                    # F1 scaduta con 600 da incassare; F2 non ancora
    assert s["cassa"] == 400 - 100
    assert s["rapporti"] == 2 and s["ore"] == 40 and s["segnalazioni_aperte"] == 1
    assert s["giorni_senza_rapporto"] == 1                    # ultimo rapportino lunedì, oggi martedì


def test_nomi_non_in_rubrica_non_spariscono():
    o = sk.calcola_sk(_payloads(), OGGI)
    f = [x for x in o["schede"] if not x["in_rubrica"]]
    assert len(f) == 1 and f[0]["Cantiere"] == "Cantiere fantasma" and f[0]["uscite"]["totale"] == 50
    assert any("Cantiere fantasma" in a for a in o["avvisi"]) and o["kpi"]["non_in_rubrica"] == 1


def test_vivi_per_primi_e_kpi():
    o = sk.calcola_sk(_payloads(), OGGI)
    assert [x["Codice"] for x in o["schede"] if x["vivo"]] == ["CAN-2026-001", "CAN-2026-003"]
    assert not next(x for x in o["schede"] if x["Codice"] == "CAN-2026-002")["vivo"]
    assert o["kpi"]["vivi"] == 2 and o["kpi"]["fatturato_vivi"] == 1500 and o["kpi"]["da_pagare_vivi"] == 200


def test_senza_dati_non_da_errore():
    assert sk.calcola_sk({}, OGGI)["schede"] == []
    assert sk.calcola_sk({"ru": {"cantieri": [{"Cantiere": "Solo uno"}]}}, OGGI)["schede"][0]["vivo"]   # stato mancante = In corso


def test_costi_e_sal_da_altri_strumenti():
    p = _payloads()
    p["sl"] = {"commesse": [{"Commessa": "Villa Lago", "Contratto": 100000, "Costi_prev": 70000, "Avanz_reale_pct": 50}],
               "sal": [{"Commessa": "Villa Lago", "Numero": 1, "Data": g(-10), "Avanzamento_pct": 30, "Incassato": 20000, "Data_incasso": g(-2)}],
               "costi": [{"Commessa": "Villa Lago", "Data": g(-9), "Fornitore": "Edil", "Descrizione": "Cemento", "Categoria": "Materiali", "Importo": 5000, "Pagato": 5000}]}
    p["pr"] = {"persone": [{"Persona": "Mario", "Costo_orario": 30}], "ore": [{"Persona": "Mario", "Data": g(-3), "Commessa": "CAN-2026-001", "Ore": 10}]}
    s = next(x for x in sk.calcola_sk(p, OGGI)["schede"] if x["Codice"] == "CAN-2026-001")
    assert s["sal"] == {"emessi": 1, "incassato": 20000.0}
    assert s["contratto"]["contratto"] == 100000
    assert s["costi"]["Altri costi (inseriti in SAL)"] == 5000
    assert s["costi"]["Manodopera (presenze)"] == pytest.approx(315.0)          # 10 ore × 30 € più gli oneri previsti da Presenze e ore
    assert s["costi_totali"] == pytest.approx(5315.0) and s["margine_corrente"] == pytest.approx(1500 - 5315)


def test_cantieri_per_rapportino_solo_vivi():
    nomi = sk.cantieri_per_rapportino(_payloads()["ru"]["cantieri"])
    assert sorted(nomi) == ["Capannone", "Villa Lago"]
    assert ru.cantieri_vivi([{"Stato": "Sospeso"}, {"Stato": "In corso"}]) == [{"Stato": "In corso"}]


# --- schermate ---------------------------------------------------------------
def _app(tmp_path, monkeypatch, modulo):
    from streamlit.testing.v1 import AppTest
    import storage
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setenv("FCR_DB_PATH", str(tmp_path / "n.db"))
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "n.db"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ESEMPI_ATTIVI", raising=False)
    storage.svuota_cache()
    at = AppTest.from_file("app.py", default_timeout=120)
    at.session_state["utente"] = {"username": "root", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = modulo
    return at


def _salva_rubrica(cantieri):
    import storage
    storage.salva_pratica("rubrica", {"contatti": [], "cantieri": cantieri}, autore="t", modulo="ru")


def test_schermata_scheda_cantiere_vuota_e_con_dati(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch, "sk").run()
    assert not at.exception, [e.value for e in at.exception]
    _salva_rubrica(_payloads()["ru"]["cantieri"])
    import storage
    storage.salva_pratica("scadenzario", {"docs": _payloads()["sc"]["docs"], "params": {}}, autore="t", modulo="sc")
    at = _app(tmp_path, monkeypatch, "sk").run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.selectbox(key="sk_sel").value.startswith("CAN-2026-001")


def test_rapportino_propone_solo_cantieri_vivi(tmp_path, monkeypatch):
    _app(tmp_path, monkeypatch, "rp")                      # prepara il database
    _salva_rubrica(_payloads()["ru"]["cantieri"])
    at = _app(tmp_path, monkeypatch, "rp").run()
    assert not at.exception, [e.value for e in at.exception]
    sel = at.selectbox(key="nr_cantiere")
    assert sorted(sel.options) == ["Capannone", "Villa Lago"]     # niente «Scuola» (concluso) e niente voce «nuovo cantiere»


def test_rapportino_senza_rubrica_come_prima(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch, "rp").run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Nuovo cantiere" in o for o in at.selectbox(key="nr_cantiere").options)


# --- Scadenzario per cantiere, conti correnti, subappaltatori su piu' cantieri ----------------
import bk
import sa


def test_scadenzario_diviso_per_cantiere_con_totale():
    import sc
    docs, _ = sc.normalizza_documenti(_payloads()["sc"]["docs"])
    cant, _ = ru.normalizza_cantieri(_payloads()["ru"]["cantieri"])
    r = sk.riepilogo_documenti(docs, cant, OGGI)
    nomi = [x["Cantiere"] for x in r["righe"]]
    assert nomi[0].startswith("CAN-2026-001") and "Cantiere fantasma" in nomi        # vivi per primi, poi i nomi non in Rubrica
    villa = r["righe"][0]
    assert villa["Da incassare"] == 1100 and villa["Da pagare"] == 200 and villa["Di cui scaduto"] == 600 and villa["Saldo netto"] == 900
    assert r["totale"]["Da pagare"] == 250 and r["totale"]["Fatture"] == 4          # il totale comprende tutto, anche il cantiere fantasma
    assert len(r["docs"][villa["Cantiere"]]) == 3


def test_conti_correnti_per_cantiere_prospetto_e_debiti():
    conti, _ = bk.normalizza_conti([{"Conto": "Villa Lago BPER", "Cantiere": "Villa Lago", "Saldo_iniziale": 10000, "Fido": 5000}, {"Conto": "Generale", "Saldo_iniziale": 2000}])
    debiti, av = bk.normalizza_debiti([{"Conto": "Villa Lago BPER", "Descrizione": "Mutuo", "Residuo": 9000, "Rata": 3000, "Ogni_mesi": 1, "Prossima_rata": g(10)},
                                       {"Conto": "Boh", "Descrizione": "X", "Residuo": 5}], conti)
    assert len(av) == 1 and "Boh" in av[0]
    mov, _ = bk.normalizza_movimenti([{"Data": g(-1), "Descrizione": "x", "Importo": -3000, "Conto": "Villa Lago BPER"}, {"Data": g(-1), "Descrizione": "y", "Importo": 500, "Conto": float("nan")}])
    docs = [{"Tipo": "Attiva", "Controparte": "A", "Cantiere": "villa lago", "Documento": "1", "Scadenza": g(14), "Importo": 20000, "Saldato": 0, "Data_doc": ""},
            {"Tipo": "Passiva", "Controparte": "B", "Cantiere": "", "Documento": "2", "Scadenza": g(-3), "Importo": 1000, "Saldato": 0, "Data_doc": ""}]
    r = bk.prospetti(conti, mov, docs, debiti, OGGI)
    v, gen = r["conti"]
    assert v["saldo"] == 7000 and v["disponibile"] == 12000 and v["debito_residuo"] == 9000
    assert [w["Saldo previsto"] for w in v["previsione"][:3]] == [7000, 4000, 24000]   # rata di 3.000 e incasso di 20.000 nelle settimane giuste
    assert gen["saldo"] == 2000 and gen["previsione"][0]["Saldo previsto"] == 1000       # la passiva senza cantiere pesa sul conto generale
    assert r["totale"]["saldo"] == 9000 and r["totale"]["debito_residuo"] == 9000


def test_conto_sotto_zero_segnala_allarme():
    conti, _ = bk.normalizza_conti([{"Conto": "C", "Saldo_iniziale": 100, "Fido": 0}])
    docs = [{"Tipo": "Passiva", "Controparte": "B", "Cantiere": "", "Documento": "2", "Scadenza": g(3), "Importo": 1000, "Saldato": 0, "Data_doc": ""}]
    x = bk.prospetti(conti, [], docs, [], OGGI)["conti"][0]
    assert x["primo_sotto_zero"]["Stato"] == "bad" and x["avvisi"]


def test_movimento_prende_il_cantiere_del_conto_per_abbinare():
    conti, _ = bk.normalizza_conti([{"Conto": "C1", "Cantiere": "Villa Lago"}])
    mov, _ = bk.normalizza_movimenti([{"Data": g(0), "Descrizione": "bonifico", "Importo": 500, "Conto": "C1"}])
    docs = [{"Tipo": "Attiva", "Controparte": "Zeta", "Cantiere": "Villa Lago", "Documento": "9", "Scadenza": g(0), "Importo": 500, "Saldato": 0, "Data_doc": ""}]
    out = bk.calcola_bk(mov, docs, None, conti)
    assert any("stesso cantiere" in m for m in out["abbinamenti"][0]["Motivi"])


def test_subappaltatore_su_piu_cantieri():
    con, _ = sa.normalizza_contratti([{"Subappaltatore": "Edil", "Commessa": "A", "Importo_contratto": 1000, "Ritenuta_pct": 5}, {"Subappaltatore": "Edil", "Commessa": "B", "Importo_contratto": 2000}])
    assert len(con) == 2
    sal, _ = sa.normalizza_sal([{"Subappaltatore": "Edil", "Commessa": "A", "Data": g(-5), "Importo_SAL": 400, "Pagato": 100}, {"Subappaltatore": "Edil", "Commessa": "B", "Data": g(-4), "Importo_SAL": 900}], con)
    doc, _ = sa.normalizza_doc([{"Subappaltatore": "Edil", "Documento": "DURC", "Scadenza": g(200)}], {"Edil"})
    o = sa.calcola_sa(con, sal, doc, {"oggi": OGGI})
    x = sa.per_subappaltatore(o)
    assert len(x) == 1 and x[0]["N. cantieri"] == 2 and x[0]["SAL lordi"] == 1300 and x[0]["Contratti"] == 3000
    p = {"ru": {"cantieri": [{"Cantiere": "A", "Stato": "In corso"}, {"Cantiere": "B", "Stato": "In corso"}]}, "sa": {"contratti": [dict(c) for c in con], "sal": sal, "doc": doc}}
    sch = {s["Cantiere"]: s for s in sk.calcola_sk(p, OGGI)["schede"]}
    assert sch["A"]["costi"]["Subappalti"] == 400 and sch["B"]["costi"]["Subappalti"] == 900         # ogni contratto sul suo cantiere
    assert sch["A"]["subappalti"][0]["Altri_cantieri"] == "B" and sch["B"]["subappalti"][0]["Altri_cantieri"] == "A"


def test_scheda_cantiere_mostra_i_conti_del_cantiere():
    p = _payloads()
    p["bk"] = {"conti": [{"Conto": "Villa Lago BPER", "Cantiere": "villa lago", "Saldo_iniziale": 1000, "Fido": 0}, {"Conto": "Generale", "Saldo_iniziale": 50}], "movimenti": [], "debiti": []}
    s = next(x for x in sk.calcola_sk(p, OGGI)["schede"] if x["Codice"] == "CAN-2026-001")
    assert [c["conto"]["Conto"] for c in s["conti"]] == ["Villa Lago BPER"]            # il conto generale non e' di nessun cantiere


def test_schermata_prospetto_per_conto_con_dati(tmp_path, monkeypatch):
    import storage
    _app(tmp_path, monkeypatch, "bk")
    _salva_rubrica(_payloads()["ru"]["cantieri"])
    storage.salva_pratica("scadenzario", {"docs": _payloads()["sc"]["docs"], "params": {}}, autore="t", modulo="sc")
    at = _app(tmp_path, monkeypatch, "bk")
    at.session_state["bk_conti"] = pd.DataFrame([{"Conto": "Villa Lago BPER", "Banca": "BPER", "Iban": "", "Cantiere": "Villa Lago", "Saldo_iniziale": 1000.0, "Fido": 500.0},
                                                 {"Conto": "Generale", "Banca": "", "Iban": "", "Cantiere": "", "Saldo_iniziale": 0.0, "Fido": 0.0}], columns=bk.COLONNE_CONTI)
    at.session_state["bk_debiti"] = pd.DataFrame([{"Conto": "Generale", "Descrizione": "Mutuo", "Residuo": 5000.0, "Rata": 500.0, "Ogni_mesi": 1, "Prossima_rata": g(7)}], columns=bk.COLONNE_DEBITI)
    at.session_state["bk_mov"] = pd.DataFrame([{"Data": g(-1), "Descrizione": "bonifico", "Importo": 200.0, "Conto": "Villa Lago BPER"}], columns=bk.COLONNE_MOV)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.selectbox(key="bk_conto_sel").options == ["Villa Lago BPER", "Generale"]


def test_schermata_scadenzario_si_apre_per_cantiere(tmp_path, monkeypatch):
    import sc
    at = _app(tmp_path, monkeypatch, "sc")
    at.session_state["sc_df"] = pd.DataFrame(_payloads()["sc"]["docs"], columns=sc.COLONNE_DOC).fillna("")
    at.session_state["sc_demo"] = False
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.tabs[0].label.startswith("🏗️ 1. Per cantiere")
    assert any(d.value is not None for d in at.dataframe)
