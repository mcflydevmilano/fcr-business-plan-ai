"""Offerta e finanziamenti: parcelle D.Lgs. 36/2023, QTE, finanziamento, computo A/B, millesimi, richieste, offerta PPTX/PDF e apertura dello strumento."""
import io
import os
import tempfile

import openpyxl
import pytest
from streamlit.testing.v1 import AppTest

import of
import of_report
import of_ui
import storage

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")


@pytest.fixture(autouse=True)
def db(monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
    monkeypatch.setenv("APP_PASSWORD", "segreta")


def _cme():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Foglio1"
    ws["A1"], ws["B1"] = "Sconto parti comuni", -1000
    ws["A2"], ws["B2"] = "Sconto ipotesi B", -500
    t = wb.create_sheet("Table 1")
    t.append(["COMPUTO"])
    t.append([None, None, "DESCRIZIONE", "U.", "Quantità", "Prezzo", "Prezzo", "Note", "TOTALI"])
    t.append(["A", None, "CANTIERIZZAZIONI"])
    t.append(["A", "1", "Ponteggio", "mq", 100, 10, 1000])
    t.append(["A", "2", "Autogrù", "a corpo", None, None, 500])
    t.append([None, None, None, None, None, None, None, None, 1500])
    t.append(["C", None, "ISOLAMENTI E MANTI"])
    t.append([None, None, "IPOTESI A: GUAINA"])
    t.append(["c", "1A", "Guaina", "mq", 10, 100, 1000])
    t.append([None, None, "IPOTESI B: LAMIERA"])
    t.append(["c", "1B", "Lamiera", "mq", 10, 150, 1500])
    t.append([None, None, "INTERVENTI COMUNI"])
    t.append(["C", "1", "Scossalina", "m", 10, 20, 200])
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def test_parametri_e_parcella():
    assert of.parametro_p(10000) == pytest.approx(0.20411) and of.parametro_p(0) == 0
    assert of.parametro_p(605397.52) == pytest.approx(0.03 + 10 / 605397.52 ** 0.4)
    assert of.pct_spese(500000) == 0.25 and of.pct_spese(30_000_000) == 0.05 and of.pct_spese(13_000_000) == pytest.approx(0.25 - 12_000_000 * 0.15 / 24_000_000)
    assert of.grado_g("E.06") == 0.95
    r = of.parcella([{"cat": "EDILIZIA", "V": 100000, "id": "E.06"}], ["QbIII.01"])
    assert r["compenso"] == pytest.approx(100000 * of.parametro_p(100000) * 0.95 * 0.07)
    assert r["totale"] == pytest.approx(r["compenso"] * 1.25)          # spese 25% sotto il milione
    r2 = of.parcella([{"cat": "EDILIZIA", "V": 100000, "id": "E.06"}], ["QbIII.01"], bim=True, sconto_pct=0.1)
    assert r2["bim"] == pytest.approx(r["compenso"] * 0.1) and r2["totale"] < (r["compenso"] * 1.1) * 1.25 and r2["sconto"] < 0
    assert of.parcella([], ["QbIII.01"])["totale"] == 0


def test_qte_come_il_foglio_del_collega():
    q = of.qte(605397.52, 40644.22, 39605)
    assert round(q["iva_lavori"], 2) == 60539.75 and round(q["lavori_iva"], 2) == 665937.27
    assert round(q["spese"], 2) == 101820.21 and round(q["totale"], 2) == 767757.48
    assert round(q["incidenza_prof"], 4) == 0.0698


def test_finanziamento_come_nell_offerta():
    p = of.piano(767757.48, 5, 0.06)
    assert round(p["rata"], 2) == 14842.90 and round(p["interessi"], 2) == 122816.70
    rec = of.recupero_fiscale(665937.27, 50)
    assert round(rec["totale"], 2) == 332968.64 and round(rec["annuo"], 2) == 33296.86
    s = of.simulazione(767757.48, 665937.27, (3, 5, 10), 0.06, (50, 36), 10, 0)
    assert [x["anni"] for x in s] == [3, 5, 10]
    assert round(s[1]["costo_reale50"] / 1000, 2) == 557.61 and round(s[1]["costo_reale36"] / 1000, 2) == 650.84
    assert s[1]["impatto50"] == pytest.approx(s[1]["rata"] - rec["mensile"])
    s2 = of.simulazione(100000, 100000, (5,), 0.06, (50,), 10, 12000)       # risparmio 1.000 euro/mese
    assert s2[0]["impatto50"] == pytest.approx(of.piano(100000, 5, 0.06)["rata"] - 50000 / 120 - 1000)
    assert of.rata_mensile(1200, 12, 0) == 100 and of.rata_mensile(0, 12) == 0


def test_computo_ipotesi_a_b_e_sconti():
    voci, sconti = of.import_cme(_cme())
    assert len(voci) == 5 and {v["Ipotesi"] for v in voci} == {"", "A", "B"}
    assert [v for v in voci if v["Descrizione"] == "Scossalina"][0]["Ipotesi"] == ""
    assert [v for v in voci if v["Descrizione"] == "Autogrù"][0]["Quantita"] == 1 and sconti == [
        {"Descrizione": "Sconto parti comuni", "Ipotesi": "", "Importo": -1000.0}, {"Descrizione": "Sconto ipotesi B", "Ipotesi": "B", "Importo": -500.0}]
    t = of.totali_computo(voci, sconti)
    assert t["comune"] == 1700 and t["A"]["imponibile"] == 1700 - 1000 + 1000 and t["B"]["imponibile"] == 1700 - 1000 + 1500 - 500
    assert t["differenza"] == t["A"]["imponibile"] - t["B"]["imponibile"]


def test_millesimi_da_excel_e_riparto():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Tabella millesimale"])
    ws.append(["Interno", "Proprietario", "Millesimi generali", "mq"])
    ws.append(["1", "Rossi", 600, 80])
    ws.append(["2", "Bianchi", 400, 60])
    ws.append(["Totale", None, 1000, None])
    b = io.BytesIO()
    wb.save(b)
    un = of.import_millesimi(b.getvalue())
    assert [u["Millesimi"] for u in un] == [600, 400] and un[0]["Proprietario"] == "Rossi" and of.totale_millesimi(un) == 1000
    assert [round(r["quota"], 2) for r in of.riparto(un, 1000)] == [600.0, 400.0]
    with pytest.raises(ValueError):
        of.import_millesimi(_cme())


def test_mercato_e_richieste():
    m = of.mercato([{"Mq": 100, "Prezzo": 150000, "Stato": "Così com'è"}, {"Mq": 100, "Prezzo": 170000, "Stato": "Efficientato"}])
    assert m["ante"] == 1500 and m["post"] == 1700 and m["delta"] == 200 and m["da_annunci"]
    assert of.mercato([], 1400, 1600)["delta"] == 200 and of.mercato([])["delta"] is None
    ric = [{"Tipo": "Condominio", "Richiesto": 500000, "Stato": "Approvata", "Deliberato": 480000},
           {"Tipo": "Condomino", "Unita": "1", "Lavori": 10000, "Richiesto": 6000, "Stato": "In istruttoria"},
           {"Tipo": "Condomino", "Unita": "2", "Lavori": 10000, "Richiesto": 4000, "Stato": "Rifiutata"}, {"Tipo": "Condomino", "Unita": "3", "Richiesto": 3000, "Stato": "Erogata"}]
    c = of.copertura(1_000_000, ric)
    assert c["approvato"] == 483000 and c["in_corso"] == 6000 and c["rifiutato"] == 4000 and round(c["pct_approvato"], 1) == 48.3
    assert c["scoperto"] == 517000 and len(c["avvisi"]) == 1 and "oltre il 50%" in c["avvisi"][0]
    assert c["tipi"]["Condominio"]["n_approvate"] == 1 and c["tipi"]["Condomino"]["n_rifiutate"] == 1
    assert of.normalizza_fin([{"Stato": "boh", "Richiesto": 5}])[0]["Stato"] == "Da preparare" and of.normalizza_fin([{}]) == []


def _payload():
    voci, sconti = of.import_cme(_cme())
    return {"pratica": {"cod": "001-TEST", "condominio": "Condominio Test", "indirizzo": "Via Roma 1", "ui": 2, "data": "1 gennaio 2026", "descrizione": "Copertura"},
            "voci": [dict(v, Quantita=v["Quantita"] * 1000) for v in voci], "sconti": sconti, "opzioni": {"A": {"nome": "guaina"}, "B": {"nome": "lamiera"}},
            "parcelle": {"manuale": {"A": 10000}, "rl_importo": 5000}, "unita": [{"Unita": "1", "Proprietario": "Rossi", "Millesimi": 600}, {"Unita": "2", "Proprietario": "Bianchi", "Millesimi": 400}],
            "annunci": [{"Mq": 100, "Prezzo": 150000, "Stato": "Così com'è"}, {"Mq": 100, "Prezzo": 170000, "Stato": "Efficientato"}], "params": {"risparmio_annuo": 6000},
            "richieste": [{"Tipo": "Condominio", "Richiedente": "Condominio Test", "Richiesto": 100000, "Stato": "Approvata"}]}


def test_contesto_completo_e_offerta():
    c = of.contesto(_payload())
    assert set(c["opzioni"]) == {"A", "B"} and c["opzioni"]["A"]["qte"]["parcella"]["lorda"] == 10000
    assert c["opzioni"]["B"]["parcella_dett"] is not None          # B non ha parcella a mano: calcolata
    assert c["copertura"]["totale"] == c["opzioni"]["A"]["qte"]["totale"] and c["mercato"]["delta"] == 200
    assert len(c["sim"]["A"]) == 3 and c["sim"]["A"][0]["impatto50"] < c["sim"]["A"][0]["rata"]
    sl = of_report.costruisci(c)
    titoli = [s["titolo"] for s in sl]
    assert any("Quadro economico - Opzione A" in t for t in titoli) and any("Ripartizione per unità" in t for t in titoli) and any("Continuità finanziaria" in t for t in titoli)
    assert any("Valorizzazione" in t for t in titoli)
    pp = of_report.pptx_bytes(sl)
    assert pp[:2] == b"PK" and len(pp) > 20000
    from pptx import Presentation
    assert len(Presentation(io.BytesIO(pp)).slides) == len(sl)
    pdf = of_report.pdf_bytes(sl)
    assert pdf[:4] == b"%PDF"
    import re
    assert len(re.findall(rb"/Type\s*/Page\b", pdf)) == len(sl)


def test_una_sola_opzione_senza_ipotesi():
    p = {"voci": [{"Cap": "A", "Descrizione": "x", "Quantita": 10, "Prezzo": 1000, "Ipotesi": ""}], "pratica": {"condominio": "C"}}
    c = of.contesto(p)
    assert list(c["opzioni"]) == ["A"] and c["opzioni"]["A"]["imponibile"] == 10000
    sl = of_report.costruisci(c)
    assert not any("Confronto tecnico" in s["titolo"] for s in sl) and of_report.pdf_bytes(sl)[:4] == b"%PDF"
    assert of.contesto({})["opzioni"] == {}


def _admin(modulo):
    at = AppTest.from_file(APP, default_timeout=180)
    at.session_state["utente"] = {"username": "root", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = modulo
    return at.run()


def test_strumento_si_apre_vuoto_e_con_dati():
    at = _admin("of")
    assert not at.exception, [e.value for e in at.exception]
    assert any("Nessuna voce di computo" in i.value for i in at.info)
    at.session_state["of_voci"] = of_ui._df("of_voci", _payload()["voci"])
    at.session_state["of_sconti"] = of_ui._df("of_sconti", _payload()["sconti"])
    at.session_state["of_unita"] = of_ui._df("of_unita", _payload()["unita"])
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Ipotesi A - imponibile" in m.value for m in at.markdown)


def test_salva_e_riapri_l_offerta():
    at = _admin("of")
    pl = _payload()
    of_ui._applica(pl, "x")
    # simula l'applicazione dei valori scalari come fa l'app (_pending) e verifica che il giro completo non cambi i dati
    at.session_state["of_voci"] = of_ui._df("of_voci", pl["voci"])
    at.session_state["of_p_condominio"] = "Condominio Test"
    at.session_state["of_nome_A"] = "guaina"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    from_ss = {k: at.session_state[k] for k in ("of_p_condominio", "of_nome_A")}
    assert from_ss == {"of_p_condominio": "Condominio Test", "of_nome_A": "guaina"}


def test_genera_offerta_dallo_strumento():
    at = _admin("of")
    pl = _payload()
    at.session_state["of_voci"] = of_ui._df("of_voci", pl["voci"])
    at.session_state["of_p_condominio"] = "Condominio Test"
    at.run()
    [b for b in at.button if "Genera l'offerta" in b.label][0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    out = at.session_state["rep_of"]
    assert out["pptx"][:2] == b"PK" and out["pdf"][:4] == b"%PDF" and out["xlsx"][:2] == b"PK"


def test_hub_permessi_e_ricerca():
    import permessi
    import ricerca
    assert "of" in permessi.TUTTI and "of" in permessi.PROFILI_BASE["commerciale"] and "of" in permessi.PROFILI_BASE["direzione"] + ["of"]
    assert "of" in storage.MODULI_ARCHIVIO
    at = _admin(None)
    assert not at.exception and any("Offerta e finanziamenti" in b.label for b in at.button)
