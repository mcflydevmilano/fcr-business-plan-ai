"""Segreteria: ferie e permessi, note spese, lettere e modelli."""
import datetime as dt
import io
import zipfile

import pytest
from streamlit.testing.v1 import AppTest

import fp
import lm
import ns
import permessi
import richieste
import storage

D = dt.date


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "s.db"))
    storage.svuota_cache()


# ------------------------------------------------------------------ richieste
def test_richieste_creano_decidono_e_tengono_gli_allegati():
    import base64
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
    rid = richieste.crea("ns", "anna verdi", {"x": 1}, [("scontrino.png", png)])
    r = richieste.ottieni(rid)
    assert r["stato"] == "In attesa" and r["dati"] == {"x": 1}
    assert richieste.allegati(rid)[0][1] == "image/jpeg"
    richieste.decidi(rid, "Approvata", "admin", "ok")
    assert richieste.elenca("ns", stati=["Approvata"])[0]["deciso_da"] == "admin"
    assert richieste.elenca("ns", utente="luca neri") == [] and richieste.elenca("fp") == []
    richieste.rinomina_utente("anna verdi", "anna rossi")
    assert richieste.ottieni(rid)["utente"] == "anna rossi"


# ------------------------------------------------------------------ ferie
def test_giorni_lavorativi_e_festivi():
    assert fp.pasqua(2026) == D(2026, 4, 5) and D(2026, 4, 6) in fp.festivi(2026)
    assert fp.giorni_lavorativi(D(2026, 12, 1), D(2026, 12, 31), ["12-07"]) == 20       # 8 e 25 dicembre, S. Ambrogio e fine settimana non contano
    assert fp.giorni_lavorativi(D(2026, 11, 7), D(2026, 11, 8)) == 0


def _req(utente, tipo, dal, al, stato="Approvata", ore=0, i=[0]):
    i[0] += 1
    return {"id": i[0], "utente": utente, "stato": stato, "dati": {"tipo": tipo, "dal": str(dal), "al": str(al), "ore": ore}}


def test_validazione_e_sovrapposizioni():
    cfg = fp.normalizza_cfg({})
    ok = {"tipo": "Ferie", "dal": "2026-08-10", "al": "2026-08-14"}
    assert fp.valida(ok, [], cfg) == ""
    assert "prima" in fp.valida({**ok, "al": "2026-08-01"}, [], cfg)
    assert "ore" in fp.valida({"tipo": "Permesso (ore)", "dal": "2026-08-10", "al": "2026-08-10", "ore": 0}, [], cfg)
    assert "un solo giorno" in fp.valida({"tipo": "Permesso (ore)", "dal": "2026-08-10", "al": "2026-08-11", "ore": 2}, [], cfg)
    assert "motivo" in fp.valida({"tipo": "Altro", "dal": "2026-08-10", "al": "2026-08-10"}, [], cfg).lower()
    assert "giorni lavorativi" in fp.valida({"tipo": "Ferie", "dal": "2026-11-07", "al": "2026-11-08"}, [], cfg)
    gia = [_req("anna", "Ferie", D(2026, 8, 12), D(2026, 8, 20), "In attesa")]
    assert "già" in fp.valida(ok, gia, cfg)
    assert fp.valida(ok, [_req("anna", "Ferie", D(2026, 8, 12), D(2026, 8, 20), "Respinta")], cfg) == ""


def test_giorni_residui():
    cfg = fp.normalizza_cfg({"giorni_ferie": 26, "ore_permesso": 32, "per_persona": {"luca": {"giorni_ferie": 20, "ore_permesso": 16}}})
    lista = [_req("anna", "Ferie", D(2026, 8, 10), D(2026, 8, 14)), _req("anna", "Ferie", D(2026, 9, 1), D(2026, 9, 2), "In attesa"),
             _req("anna", "Permesso (ore)", D(2026, 5, 4), D(2026, 5, 4), ore=3), _req("anna", "Ferie", D(2026, 10, 1), D(2026, 10, 2), "Respinta")]
    r = fp.residui("anna", 2026, lista, cfg)
    assert r["ferie_usate"] == 5 and r["ferie_attesa"] == 2 and r["ferie_residue"] == 19 and r["permessi_residui"] == 29
    assert fp.residui("luca", 2026, [], cfg)["ferie_residue"] == 20
    assert fp.residui("anna", 2027, lista, cfg)["ferie_residue"] == 26                  # anno diverso


def test_ferie_a_cavallo_d_anno_contano_solo_i_giorni_dell_anno():
    cfg = fp.normalizza_cfg({})
    lista = [_req("anna", "Ferie", D(2026, 12, 28), D(2027, 1, 8))]
    assert fp.residui("anna", 2026, lista, cfg)["ferie_usate"] == 4                    # 28, 29, 30 e 31 dicembre


def test_avviso_presenti_minimi_e_chi_manca():
    pers = ["anna", "luca", "sara", "dario"]
    lista = [_req("anna", "Ferie", D(2026, 8, 10), D(2026, 8, 14)), _req("luca", "Ferie", D(2026, 8, 12), D(2026, 8, 12), "In attesa"), _req("sara", "Permesso (ore)", D(2026, 8, 12), D(2026, 8, 12), ore=2)]
    assert fp.copertura(lista, D(2026, 8, 10), D(2026, 8, 14), pers, 2) == []           # i permessi a ore non contano, restano 2 presenti
    b = fp.copertura(lista, D(2026, 8, 12), D(2026, 8, 12), pers, 3, persona_nuova="dario")
    assert b and b[0]["presenti"] == 1 and set(b[0]["assenti"]) == {"anna", "luca", "dario"}
    assert fp.copertura(lista, D(2026, 8, 15), D(2026, 8, 16), pers, 4) == []            # fine settimana: nessun controllo
    assert fp.copertura(lista, D(2026, 8, 12), D(2026, 8, 12), pers, 3, escludi_id=lista[1]["id"], persona_nuova="dario")[0]["presenti"] == 2
    m = {r["Persona"]: r for r in fp.matrice_mese(lista, 2026, 8, pers)}
    assert m["anna"]["12"] == "F" and m["luca"]["12"] == "F?" and m["sara"]["12"] == "P" and m["anna"]["15"] == "·" and m["dario"]["12"] == ""


def test_chi_puo_approvare():
    cfg = fp.normalizza_cfg({})
    assert fp.puo_approvare("giulia", "editor", "amministrazione", cfg, "anna") and not fp.puo_approvare("giulia", "editor", "cantiere", cfg, "anna")
    assert not fp.puo_approvare("giulia", "editor", "amministrazione", cfg, "Giulia")              # non approva se stessa
    assert fp.puo_approvare("admin", "admin", "", cfg, "admin")
    scelti = fp.normalizza_cfg({"approvatori": ["Marco  Rossi"]})
    assert fp.puo_approvare("marco rossi", "editor", "cantiere", scelti, "anna") and not fp.puo_approvare("giulia", "editor", "amministrazione", scelti, "anna")


def test_assenze_approvate_arrivano_al_calendario():
    import calendario
    richieste.crea(fp.TIPO, "anna verdi", {"tipo": "Ferie", "dal": "2026-11-09", "al": "2026-11-13", "ore": 0}, stato="Approvata")
    richieste.crea(fp.TIPO, "luca neri", {"tipo": "Ferie", "dal": "2026-11-09", "al": "2026-11-13", "ore": 0}, stato="In attesa")
    richieste.crea(fp.TIPO, "sara", {"tipo": "Ferie", "dal": "2026-01-05", "al": "2026-01-09", "ore": 0}, stato="Approvata")
    ass = fp.assenze_per_calendario(D(2026, 11, 6))
    assert [a["persona"] for a in ass] == ["anna verdi"]
    ev = calendario.eventi({"fp": {"assenze": ass}}, D(2026, 11, 11), 30)
    assert len(ev) == 1 and ev[0]["Categoria"] == "Assenza" and "anna verdi" in ev[0]["Titolo"] and "fino al 13/11" in ev[0]["Titolo"] and ev[0]["Stato"] == "ok"


# ------------------------------------------------------------------ note spese
def test_rimborso_chilometrico_e_regole_della_ricevuta():
    oggi = D(2026, 11, 6)
    d, err = ns.prepara({"categoria": "Rimborso chilometrico", "data": "2026-11-05", "km": 120, "descrizione": "Milano - Bergamo, cantiere"}, 0.40, oggi)
    assert not err and d["importo"] == 48.0 and d["tariffa_km"] == 0.4
    assert ns.prepara({"categoria": "Rimborso chilometrico", "data": "2026-11-05", "km": 0, "descrizione": "x"}, 0.4, oggi)[1]
    assert "foto" in ns.prepara({"categoria": "Pasti", "data": "2026-11-05", "importo": 25}, 0.4, oggi)[1]
    assert not ns.prepara({"categoria": "Pasti", "data": "2026-11-05", "importo": 25}, 0.4, oggi, n_allegati=1)[1]
    assert "spiega" in ns.prepara({"categoria": "Pasti", "data": "2026-11-05", "importo": 25, "senza_ricevuta": True, "descrizione": "pranzo"}, 0.4, oggi)[1]
    assert not ns.prepara({"categoria": "Pasti", "data": "2026-11-05", "importo": 25, "senza_ricevuta": True, "descrizione": "pranzo con il direttore lavori"}, 0.4, oggi)[1]
    assert "futuro" in ns.prepara({"categoria": "Pasti", "data": "2026-11-09", "importo": 5}, 0.4, oggi, 1)[1]
    assert ns.prepara({"categoria": "Boh", "data": "2026-11-05", "importo": 5}, 0.4, oggi, 1)[1]


def test_riepilogo_mensile_e_zip_scontrini():
    import base64
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
    def nuova(u, cat, imp, cant, data, stato, pagato=ns.PAGATO[0], allegati=()):
        rid = richieste.crea(ns.TIPO, u, {"categoria": cat, "data": data, "importo": imp, "cantiere": cant, "descrizione": "x", "pagato": pagato}, allegati)
        richieste.decidi(rid, stato, "admin")
        return rid
    nuova("anna", "Pasti", 30.0, "C1 · Villa", "2026-11-03", "Approvata", allegati=[("a.png", png)])
    nuova("anna", "Carburante", 70.0, "C1 · Villa", "2026-11-10", "Approvata", pagato=ns.PAGATO[1])
    nuova("luca", "Pasti", 20.0, "", "2026-11-04", "Rimborsata")
    nuova("luca", "Pasti", 99.0, "C2", "2026-11-05", "Respinta")
    nuova("luca", "Pasti", 15.0, "C2", "2026-10-30", "Approvata")
    m = ns.del_mese(richieste.elenca(ns.TIPO), 2026, 11)
    assert len(m) == 3
    r = ns.riepilogo(m)
    assert r["totale"] == 120.0
    per = {x["Voce"]: x for x in r["persone"]}
    assert per["anna"]["Totale €"] == 100.0 and per["anna"]["Da rimborsare €"] == 30.0 and per["luca"]["Da rimborsare €"] == 0.0
    cant = {x["Voce"]: x["Totale €"] for x in r["cantieri"]}
    assert cant["C1 · Villa"] == 100.0 and cant["(non indicato)"] == 20.0
    z, n = ns.zip_scontrini(m)
    assert n == 1 and len(zipfile.ZipFile(io.BytesIO(z)).namelist()) == 1


# ------------------------------------------------------------------ lettere
def test_compilazione_lettera_e_campi_mancanti():
    m = lm.MODELLI_BASE["preventivo"]
    assert [c[0] for c in lm.campi(m)] == ["oggetto_richiesta", "scadenza", "consegna"] and lm.campi(m)[1][2] == "data"
    az = lm.AZIENDA_BASE
    auto = lm.valori_automatici(az, {"Nome": "Edil Rossi Srl", "Referente": "Mario"}, {"Cantiere": "Villa Lago", "Indirizzo": "Via Roma 1", "Codice": "CAN-1", "Cliente": "Condominio Rossi"})
    ogg, corpo, mancanti = lm.compila(m, {**auto, "oggetto_richiesta": "Fornitura di 200 mq di isolante", "scadenza": D(2026, 11, 20)})
    assert ogg == "Richiesta di preventivo - Villa Lago" and "Edil Rossi Srl" in corpo and "20/11/2026" in corpo and "Via Roma 1" in corpo
    assert mancanti == ["Consegna richiesta entro", "Firmatario"] and "[Firmatario]" in corpo
    assert not lm.compila(lm.MODELLI_BASE["risposta"], {"destinatario": "X", "data_comunicazione": "01/11/2026", "argomento": "a", "giorni": 5})[2]


def test_modelli_personalizzati_e_word(tmp_path):
    cfg = lm.carica_cfg()
    assert len(lm.modelli(cfg)) == 7
    cfg["modelli"]["mio_x"] = {"titolo": "Mio", "oggetto": "Ciao {{destinatario}}", "corpo": "Testo {{codice_cantiere}} e {{altro_dato}}"}
    cfg["modelli"]["diffida"] = {"titolo": "Diffida mia", "oggetto": "O", "corpo": "C {{giorni}}"}
    cfg["azienda"]["firmatario"] = "Ing. Rossi"
    lm.salva_cfg(cfg, "admin")
    c2 = lm.carica_cfg()
    mod = lm.modelli(c2)
    assert mod["mio_x"]["base"] is False and mod["diffida"]["titolo"] == "Diffida mia" and mod["diffida"]["modificato"] and c2["azienda"]["firmatario"] == "Ing. Rossi"
    assert [c[0] for c in lm.campi(mod["mio_x"])] == ["altro_dato"]
    ogg, corpo, _ = lm.compila(mod["incarico"], lm.valori_automatici(c2["azienda"], {"Nome": "Studio Bianchi"}, {}))
    word = lm.docx_lettera(c2["azienda"], "Spett.le Studio Bianchi", ogg, corpo, "Milano, 06/11/2026", "Ing. Rossi", "Presidente")
    z = zipfile.ZipFile(io.BytesIO(word))
    xml = z.read("word/document.xml").decode("utf-8")
    assert "Studio Bianchi" in xml and "FCR General Contractor" in xml and "Ing. Rossi" in xml and "Oggetto" in xml


# ------------------------------------------------------------------ interfaccia
def test_registrati_nei_profili():
    for s in ("fp", "ns", "lm"):
        assert s in permessi.TUTTI and s in permessi.NOMI and s in permessi.PROFILI_BASE["commerciale"]
    assert "lm" not in permessi.PROFILI_BASE["cantiere"] and "fp" in permessi.PROFILI_BASE["cantiere"]


def _app(modulo, utente="admin", ruolo="admin"):
    at = AppTest.from_file("app.py", default_timeout=90)
    at.session_state["utente"] = {"username": utente, "ruolo": ruolo, "origine": "app_password"}
    at.session_state["active_module"] = modulo
    return at.run()


@pytest.mark.parametrize("modulo", ["fp", "ns", "lm"])
def test_le_pagine_si_aprono(modulo):
    at = _app(modulo)
    assert not at.exception, [e.value for e in at.exception]


def test_richiesta_ferie_dalla_pagina_e_approvazione():
    at = _app("fp")
    at.selectbox(key="fp_n_tipo").set_value("Permesso (ore)")
    at.number_input(key="fp_n_ore").set_value(2.0)
    at.run()
    next(b for b in at.button if b.key == "fp_invia").click().run()
    assert not at.exception, [e.value for e in at.exception]
    r = richieste.elenca(fp.TIPO)
    assert len(r) == 1 and r[0]["stato"] == "In attesa" and r[0]["dati"]["ore"] == 2.0
    # chi chiede e' l'admin: un altro utente con profilo amministrazione approva
    richieste.crea(fp.TIPO, "anna verdi", {"tipo": "Ferie", "dal": "2026-12-14", "al": "2026-12-18", "ore": 0})
    at2 = _app("fp")
    next(b for b in at2.button if b.key.startswith("fp_ok_") and "anna" in str(richieste.ottieni(int(b.key.split("_")[-1]))["utente"])).click().run()
    assert not at2.exception
    assert [x["stato"] for x in richieste.elenca(fp.TIPO, utente="anna verdi")] == ["Approvata"]


def test_nota_spesa_con_km_dalla_pagina():
    at = _app("ns")
    at.selectbox(key="ns_n_cat").set_value("Rimborso chilometrico").run()
    at.number_input(key="ns_n_km").set_value(100.0)
    at.text_input(key="ns_n_desc").set_value("Milano - Monza, sopralluogo")
    at.run()
    next(b for b in at.button if b.key == "ns_n_invia").click().run()
    assert not at.exception, [e.value for e in at.exception]
    r = richieste.elenca(ns.TIPO)
    assert len(r) == 1 and r[0]["dati"]["importo"] == 40.0


def test_excel_ore_del_mese_con_dettaglio(tmp_path):
    import openpyxl
    import ac_ui
    import acc
    cfg = acc.normalizza_cfg({"ip": "203.0.113.7"})
    for g in (3, 4):
        acc.timbra("anna verdi", "entrata", cfg, "203.0.113.7", adesso=dt.datetime(2026, 11, g, 7, 0))
        acc.timbra("anna verdi", "pausa", cfg, "203.0.113.7", adesso=dt.datetime(2026, 11, g, 11, 0), motivo="Pausa pranzo o caffè")
        acc.timbra("anna verdi", "rientro", cfg, "203.0.113.7", adesso=dt.datetime(2026, 11, g, 12, 0))
        acc.timbra("anna verdi", "uscita", cfg, "203.0.113.7", adesso=dt.datetime(2026, 11, g, 16, 0))
    righe = acc.tabella(storage.elenca_timbrature(), dt.date(2026, 11, 1), dt.date(2026, 11, 30))
    wb = openpyxl.load_workbook(io.BytesIO(ac_ui._excel_mese(righe, "Novembre 2026")))
    assert wb.sheetnames == ["Ore del mese", "Dettaglio giorni"]
    riga = [c.value for c in wb["Ore del mese"][2]]
    assert riga[0] == "anna verdi" and "16:00" in riga and 16.0 in riga                  # 8 ore al giorno (9 di presenza meno 1 di pausa), due giorni
    assert wb["Dettaglio giorni"].max_row == 3
