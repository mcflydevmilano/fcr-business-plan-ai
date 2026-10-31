"""Test dei sei strumenti nuovi: Subappalti, Presenze, Materiali, Verbali, Archivio documenti, Margini per commessa."""
import datetime as dt

import ad
import mc
import mt
import pr
import sa
import vr

OGGI = dt.date(2026, 10, 28)
g = lambda n: (OGGI + dt.timedelta(days=n)).isoformat()


# ---- subappalti ----
def _sa():
    c, _ = sa.normalizza_contratti([{"Subappaltatore": "Edil Rossi", "Commessa": "Villa Lago", "Lavorazione": "Murature", "Importo_contratto": 100000, "Ritenuta_pct": 5},
                                    {"Subappaltatore": "Edil Rossi", "Commessa": "Villa Lago", "Importo_contratto": 5}, {"Subappaltatore": "", "Commessa": "X", "Importo_contratto": 10}])
    s, _ = sa.normalizza_sal([{"Subappaltatore": "Edil Rossi", "Commessa": "Villa Lago", "Data": g(-30), "Importo_SAL": 40000, "Pagato": 20000},
                              {"Subappaltatore": "Ignoto", "Commessa": "Villa Lago", "Importo_SAL": 1}], c)
    d, _ = sa.normalizza_doc([{"Subappaltatore": "Edil Rossi", "Documento": "DURC", "Scadenza": g(-5)}, {"Subappaltatore": "Edil Rossi", "Documento": "Polizza RC", "Scadenza": g(200)}], {"Edil Rossi"})
    return c, s, d


def test_sa_calcolo_e_documenti_scaduti():
    c, s, d = _sa()
    assert len(c) == 1 and len(s) == 1 and len(d) == 2
    o = sa.calcola_sa(c, s, d, {"oggi": OGGI})
    r = o["contratti"][0]
    assert r["SAL lordi"] == 40000 and round(r["Ritenute"]) == 2000 and round(r["Da pagare"]) == 18000 and round(r["Avanzamento %"]) == 40
    assert r["Stato"] == "bad" and o["kpi"]["doc_scaduti"] == 1
    assert any("Non pagare" in a for a in o["avvisi"])
    assert sa.costi_per_commessa(o) == {"Villa Lago": 40000}


def test_sa_sal_oltre_contratto_e_pagato_in_eccesso():
    c, _ = sa.normalizza_contratti([{"Subappaltatore": "A", "Commessa": "C", "Importo_contratto": 1000, "Ritenuta_pct": 0}])
    s, _ = sa.normalizza_sal([{"Subappaltatore": "A", "Commessa": "C", "Importo_SAL": 1200, "Pagato": 1500}], c)
    o = sa.calcola_sa(c, s, [], {"oggi": OGGI})
    t = " ".join(o["avvisi"])
    assert "oltre il contratto" in t and "pagato più del dovuto" in t and "nessun documento" in t


# ---- presenze ----
def test_pr_straordinario_e_costi():
    pe, _ = pr.normalizza_persone([{"Persona": "Mario", "Costo_orario": 30}, {"Persona": "mario", "Costo_orario": 1}, {"Persona": "Senza", "Costo_orario": 0}])
    assert [p["Persona"] for p in pe] == ["Mario"]
    ore, av = pr.normalizza_ore([{"Persona": "mario", "Data": g(-1), "Commessa": "Villa Lago", "Ore": 6}, {"Persona": "Mario", "Data": g(-1), "Commessa": "Scuola", "Ore": 4},
                                 {"Persona": "Luigi", "Data": g(-1), "Ore": 3}, {"Persona": "Mario", "Data": g(-2), "Ore": 8}], {"Mario"})
    assert len(ore) == 3 and len(av) == 1
    o = pr.calcola_pr(pe, ore, {"oggi": OGGI, "ore_giorno": 8, "magg_straord_pct": 25})
    # giorno -1: 6 ordinarie + 2 ord + 2 straordinario (4 ore Scuola: 2 ordinarie, 2 straord.)
    assert round(o["kpi"]["straordinario"], 2) == 2.0
    vl = {c["Commessa"]: c["Costo manodopera"] for c in o["commesse"]}
    assert round(vl["Villa Lago"]) == 180 and round(vl["Scuola"], 2) == round(2 * 30 + 2 * 30 * 1.25, 2)
    assert "(senza commessa)" in vl and any("senza commessa" in a for a in o["avvisi"])
    assert "Villa Lago" in pr.costi_per_commessa(o) and "(senza commessa)" not in pr.costi_per_commessa(o)


def test_pr_giornata_troppo_lunga():
    pe, _ = pr.normalizza_persone([{"Persona": "Anna", "Costo_orario": 20}])
    ore, _ = pr.normalizza_ore([{"Persona": "Anna", "Data": g(-1), "Commessa": "C", "Ore": 9}, {"Persona": "Anna", "Data": g(-1), "Commessa": "C", "Ore": 6}], {"Anna"})
    o = pr.calcola_pr(pe, ore, {"oggi": OGGI})
    assert o["kpi"]["n_anomalie"] == 1 and any("15 ore" in a for a in o["avvisi"])


# ---- materiali ----
def test_mt_ritardi_giacenze_costi():
    od, _ = mt.normalizza_ordini([{"Materiale": "Cemento", "Fornitore": "Beton", "Commessa": "Villa Lago", "Quantita": 100, "Um": "q", "Prezzo_unit": 8, "Consegna_prevista": g(-3), "Consegnato": "no"},
                                  {"Materiale": "Ferro", "Commessa": "Villa Lago", "Quantita": 10, "Prezzo_unit": 50, "Consegna_prevista": g(-10), "Consegnato": "sì", "Data_consegna": g(-9)},
                                  {"Materiale": "", "Quantita": 5}])
    mv, _ = mt.normalizza_mov([{"Materiale": "Ferro", "Commessa": "Villa Lago", "Data": g(-9), "Tipo": "carico", "Quantita": 10}, {"Materiale": "Ferro", "Commessa": "Villa Lago", "Data": g(-5), "Tipo": "Scarico", "Quantita": 12},
                               {"Materiale": "Ferro", "Tipo": "Altro", "Quantita": 1}])
    assert len(od) == 2 and len(mv) == 2
    o = mt.calcola_mt(od, mv, {"oggi": OGGI})
    assert o["kpi"]["in_ritardo"] == 1 and o["kpi"]["giacenze_negative"] == 1
    assert mt.costi_per_commessa(o) == {"Villa Lago": 500}
    assert any("in ritardo di 3 giorni" in a for a in o["avvisi"]) and any("giacenza negativa" in a for a in o["avvisi"])
    assert mt.per_sl_costi(o)[0]["Descrizione"].endswith("(da Materiali)")


# ---- verbali ----
def test_vr_azioni_in_ritardo_e_senza_responsabile():
    v, _ = vr.normalizza_verbali([{"Data": g(-2), "Titolo": "Riunione cantiere", "Commessa": "Villa Lago", "Decisioni": "Anticipare il getto"}, {"Titolo": "Senza data"}])
    assert len(v) == 1
    a, av = vr.normalizza_azioni([{"Verbale": "Riunione cantiere", "Azione": "Ordinare il calcestruzzo", "Responsabile": "mario", "Scadenza": g(-1), "Stato": "Aperta"},
                                  {"Verbale": "Riunione cantiere", "Azione": "Pulire l'area", "Scadenza": g(2), "Stato": "Aperta"},
                                  {"Verbale": "Riunione cantiere", "Azione": "Rilievo", "Responsabile": "luca", "Scadenza": g(-5), "Stato": "fatta"},
                                  {"Verbale": "Altro", "Azione": "x"}], {"Riunione cantiere"})
    assert len(a) == 3 and len(av) == 1
    o = vr.calcola_vr(v, a, {"oggi": OGGI})
    k = o["kpi"]
    assert k["aperte"] == 2 and k["fatte"] == 1 and k["in_ritardo"] == 1 and k["senza_resp"] == 1 and k["in_arrivo"] == 1


# ---- archivio ----
def test_ad_link_scadenze_e_mancanti():
    d, _ = ad.normalizza_doc([{"Commessa": "Villa Lago", "Categoria": "contratto", "Titolo": "Contratto firmato", "Link": "https://drive.example/abc", "Scadenza": ""},
                              {"Commessa": "Villa Lago", "Categoria": "Sicurezza", "Titolo": "POS", "Link": "C:\\locale\\pos.pdf", "Scadenza": g(-4)}, {"Commessa": "", "Titolo": "x"}])
    assert len(d) == 2 and d[0]["Categoria"] == "Contratto"
    o = ad.calcola_ad(d, {"oggi": OGGI})
    assert o["kpi"]["scaduti"] == 1 and o["kpi"]["senza_link"] == 1 and o["kpi"]["mancanti"] == 1
    assert o["mancanti"] == [{"Commessa": "Villa Lago", "Manca": "Contabilità"}]
    assert ad.link_valido("https://x.it") and not ad.link_valido("www.x.it")


# ---- margini per commessa ----
def _payloads():
    sl = {"commesse": [{"Commessa": "Villa Lago", "Cliente": "X", "Contratto": 200000, "Costi_prev": 150000, "Avanz_reale_pct": 50, "Iva_pct": 22, "Inizio": g(-100), "Fine_prev": g(100)}],
          "sal": [{"Commessa": "Villa Lago", "Numero": 1, "Data": g(-30), "Avanzamento_pct": 50}],
          "costi": [{"Commessa": "Villa Lago", "Data": g(-20), "Fornitore": "Beton", "Importo": 30000, "Pagato": 30000, "Categoria": "Materiali"},
                    {"Commessa": "Villa Lago", "Data": g(-10), "Fornitore": "Parco mezzi interno", "Descrizione": "Escavatore - 100 h", "Importo": 5000, "Pagato": 5000, "Categoria": "Mezzi"}]}
    sa_p = {"contratti": [{"Subappaltatore": "Edil", "Commessa": "Villa Lago", "Importo_contratto": 60000}], "sal": [{"Subappaltatore": "Edil", "Commessa": "Villa Lago", "Data": g(-15), "Importo_SAL": 25000, "Pagato": 0}]}
    pr_p = {"persone": [{"Persona": "Mario", "Costo_orario": 30}], "ore": [{"Persona": "Mario", "Data": g(-3), "Commessa": "Villa Lago", "Ore": 8}, {"Persona": "Mario", "Data": g(-2), "Commessa": "Altrove", "Ore": 8}]}
    return {"sl": sl, "sa": sa_p, "pr": pr_p}


def test_mc_somma_i_costi_senza_doppio_conteggio():
    o = mc.calcola_mc(_payloads(), oggi=OGGI)
    c = o["commesse"][0]
    # manuali 30.000 (il costo «Parco mezzi interno» e' una riga inviata da Mezzi: si toglie) + subappalti 25.000 + manodopera 240
    assert round(c["Costi sostenuti"]) == 30000 + 25000 + 240
    assert o["kpi"]["differenza_vs_sal"] < 0
    comp = o["composizione"][0]
    assert comp["Costi inseriti in SAL"] == 30000 and comp["Subappalti"] == 25000 and round(comp["Manodopera (presenze)"]) == 240
    assert "Altrove" in o["non_assegnati"] and any("Altrove" in a for a in o["avvisi"])


def test_mc_si_puo_escludere_una_fonte_e_senza_sl_non_calcola():
    o = mc.calcola_mc(_payloads(), includi=("pr",), oggi=OGGI)
    assert round(o["commesse"][0]["Costi sostenuti"]) == 30000 + 240
    assert mc.calcola_mc({}, oggi=OGGI) is None and mc.calcola_mc({"sl": {"commesse": []}}) is None


# ---- schermate ----
def _app(tmp_path, monkeypatch, modulo, nome="n.db"):
    from streamlit.testing.v1 import AppTest
    import storage
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setenv("ESEMPI_ATTIVI", "1")
    monkeypatch.setenv("FCR_DB_PATH", str(tmp_path / nome))
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / nome))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    storage.svuota_cache()
    at = AppTest.from_file("app.py", default_timeout=120).run()
    at.text_input(key="login_user").set_value("admin")
    at.text_input(key="login_pw").set_value("segreta")
    at.button[0].click().run()
    at.session_state["active_module"] = modulo
    at.run()
    return at


import pytest


@pytest.mark.parametrize("sigla,titolo", [("sa", "Subappalti"), ("pr", "Presenze"), ("mt", "Materiali"), ("vr", "Verbali"), ("ad", "Archivio documenti")])
def test_schermate_con_esempio_si_aprono_senza_errori(tmp_path, monkeypatch, sigla, titolo):
    at = _app(tmp_path, monkeypatch, sigla)
    assert not at.exception, [e.value for e in at.exception]
    assert any(titolo in h.value for h in at.markdown)
    assert at.session_state[f"{sigla}_demo"] is True
    # i risultati si calcolano e mostrano almeno un avviso o un indicatore
    assert len(at.warning) + len(at.error) + len(at.success) >= 1


def test_margini_per_commessa_con_dati_di_sessione(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch, "mc")
    assert not at.exception, [e.value for e in at.exception]
    assert any("Per calcolare i margini" in i.value for i in at.info) or any("Margine finale previsto" in m.value for m in at.markdown)


def test_nuovi_strumenti_nel_calendario(tmp_path):
    import calendario
    p = {"sa": {"contratti": [{"Subappaltatore": "Edil", "Commessa": "C", "Importo_contratto": 1000}], "doc": [{"Subappaltatore": "Edil", "Documento": "DURC", "Scadenza": g(5)}]},
         "mt": {"ordini": [{"Materiale": "Cemento", "Commessa": "C", "Quantita": 1, "Consegna_prevista": g(2), "Consegnato": "no"}]},
         "vr": {"ver": [{"Data": g(-1), "Titolo": "R1"}], "azi": [{"Verbale": "R1", "Azione": "Fare", "Responsabile": "m", "Scadenza": g(1), "Stato": "Aperta"}]},
         "ad": {"doc": [{"Commessa": "C", "Titolo": "POS", "Scadenza": g(9)}]}}
    ev = calendario.eventi(p, OGGI, 30)
    assert {e["Categoria"] for e in ev} == {"Documento subappalto", "Consegna", "Azione di riunione", "Documento commessa"}


def test_permessi_e_hub_conoscono_i_nuovi_strumenti():
    import hub
    import permessi
    nuovi = ["mc", "sa", "pr", "mt", "vr", "ad"]
    assert all(s in permessi.TUTTI and s in permessi.NOMI and s in hub.CARDS for s in nuovi)
    assert all(any(s in g_[2] for g_ in hub.GRUPPI) for s in nuovi)
    assert "pr" in permessi.PROFILI_BASE["cantiere"] and "mc" not in permessi.PROFILI_BASE["cantiere"]


def test_utilita_avvisi_ed_excel(tmp_path, monkeypatch):
    import io
    import pandas as pd
    import storage
    import utilita
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "u.db"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    storage.svuota_cache()
    storage.salva_pratica("Cantiere", {"ord": [{"x": 1}], "ordini": [{"Materiale": "Cemento", "Commessa": "C", "Quantita": 1, "Consegna_prevista": g(-2), "Consegnato": "no"}]}, modulo="mt")
    ev = utilita.avvisi(None)
    assert any(e["Categoria"] == "Consegna" and e["Giorni"] < 0 for e in ev)
    dati, n = utilita.excel_tutto(None)
    x = pd.ExcelFile(io.BytesIO(dati))
    assert x.sheet_names[0] == "Indice" and n >= 1 and "mt_ordini" in x.sheet_names
    dati2, n2 = utilita.excel_tutto(["sc"])                   # chi non vede lo strumento non ne esporta i dati
    assert n2 == 0


def test_presenze_importa_ore_dai_rapportini(tmp_path, monkeypatch):
    import pr
    righe = pr.da_rapportini([{"Data": g(-1), "Cantiere": "Villa Lago", "Ore": 40, "Presenti": 5}, {"Data": "x", "Cantiere": "A", "Ore": 8}, {"Data": g(-2), "Cantiere": "B", "Ore": 0}])
    assert len(righe) == 1 and righe[0]["Persona"] == pr.SQUADRA and righe[0]["Ore"] == 40
    persone = [{"Persona": "Mario", "Qualifica": "", "Costo_orario": 30.0}, {"Persona": "Luca", "Qualifica": "", "Costo_orario": 20.0}]
    c = pr.costo_orario_squadra(persone)
    assert c == 25.0
    p, _ = pr.normalizza_persone([*persone, {"Persona": pr.SQUADRA, "Costo_orario": c}])
    o, av = pr.normalizza_ore(righe + [{"Persona": "Mario", "Data": g(-1), "Commessa": "Villa Lago", "Ore": 40}], {x["Persona"] for x in p})
    assert len(o) == 1 and any("ore non valide" in a for a in av)            # 40 h valide solo per la squadra
    out = pr.calcola_pr(p, o)
    assert out["kpi"]["straordinario"] == 0 and out["kpi"]["n_anomalie"] == 0 and out["kpi"]["costo"] == 40 * 25.0


def test_presenze_pulsante_importa_rapportini(tmp_path, monkeypatch):
    import storage
    at = _app(tmp_path, monkeypatch, "pr")
    storage.salva_pratica("Rapportini", {"rapp": [{"Id": "1", "Data": g(-1), "Cantiere": "Villa Lago", "Ore": 40, "Presenti": 5}]}, modulo="rp")
    at.session_state["rp_demo"] = False
    at.button(key="pr_imp_rp").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert (at.session_state["pr_ore"]["Persona"] == "Squadra (da rapportini)").sum() == 1
    assert (at.session_state["pr_per"]["Persona"] == "Squadra (da rapportini)").sum() == 1


def test_materiali_ddt_avviso_e_costo_in_sal():
    od, _ = mt.normalizza_ordini([
        {"Materiale": "Ferro", "Fornitore": "Acciai", "Commessa": "Villa Lago", "Quantita": 10, "Um": "q", "Prezzo_unit": 50, "Consegnato": "sì", "Data_consegna": g(-2), "Ddt": " 412 del 28/10 "},
        {"Materiale": "Sabbia", "Fornitore": "Cave", "Commessa": "Villa Lago", "Quantita": 5, "Um": "mc", "Prezzo_unit": 20, "Consegnato": "sì", "Data_consegna": g(-1)},
        {"Materiale": "Ghiaia", "Commessa": "Villa Lago", "Quantita": 1, "Prezzo_unit": 10, "Consegnato": "no"}])
    o = mt.calcola_mt(od, [], {"oggi": OGGI})
    assert od[0]["Ddt"] == "412 del 28/10" and o["kpi"]["senza_ddt"] == 1
    assert any("Sabbia" in a and "senza numero DDT" in a for a in o["avvisi"]) and not any("Ghiaia" in a and "DDT" in a for a in o["avvisi"])
    righe = mt.per_sl_costi(o)
    assert "DDT 412 del 28/10" in righe[0]["Descrizione"] and all(r["Descrizione"].endswith("(da Materiali)") for r in righe)
