import datetime as dt

import pytest

import fc
import fc_sync
import storage

OGGI = dt.date(2026, 11, 2)


@pytest.fixture
def db(tmp_path):
    p = str(tmp_path / "s.db")
    storage.svuota_cache()
    return p


def _registro(db, stato="S0-Apertura Pratica"):
    storage.salva_pratica("Registro 2026", {"pratiche": [
        {"Codice": "002-MI-X", "Stato": stato, "Archivio": "Attiva", "Citta": "Milano"},
        {"Codice": "003-MI-Y", "Stato": "S2-Offerta", "Archivio": "Attiva"}], "params": {}}, db, autore="t", modulo="rc")


def _passi(codice="002-MI-X"):
    return {int(r["Passo"]): r for r in fc.normalizza(fc.avvia(codice, OGGI))[0]}


def test_dopo_azione_aggiorna_registro_e_crea_compiti(db):
    _registro(db)
    p = _passi()
    fc.registra(p, 1, "fatto", "AB", OGGI)
    msg = fc_sync.dopo_azione("002-MI-X", p, {"responsabili": {"DC": "raffaella", "Commerciale": "marco", "CdA": "saverio"}, "scad_gg": 5}, "admin", path=db, oggi=OGGI)
    assert "S0-Apertura Pratica → S1-Sopralluogo" in msg and "Compiti: 1 nuovi" in msg
    _n, rc_p = fc_sync.ultimo("rc", db)
    assert next(r for r in rc_p["pratiche"] if r["Codice"] == "002-MI-X")["Stato"] == "S1-Sopralluogo"
    assert next(r for r in rc_p["pratiche"] if r["Codice"] == "003-MI-Y")["Stato"] == "S2-Offerta"          # le altre pratiche non si toccano
    _n, ta_p = fc_sync.ultimo("ta", db)
    t = [c for c in ta_p["compiti"] if c["Stato"] != "Fatto"]
    assert len(t) == 1 and t[0]["Compito"].startswith("Passo 2:") and t[0]["Responsabile"] == "marco" and t[0]["Scadenza"] == "2026-11-07"


def test_ripetuto_non_duplica_e_non_retrocede(db):
    _registro(db, "S3-Contratto")
    p = _passi()
    par = {"responsabili": {"Commerciale": "marco"}}
    fc_sync.dopo_azione("002-MI-X", p, par, "admin", path=db, oggi=OGGI)
    fc_sync.dopo_azione("002-MI-X", p, par, "admin", path=db, oggi=OGGI)
    _n, rc_p = fc_sync.ultimo("rc", db)
    assert next(r for r in rc_p["pratiche"] if r["Codice"] == "002-MI-X")["Stato"] == "S3-Contratto"
    _n, ta_p = fc_sync.ultimo("ta", db)
    assert len(ta_p["compiti"]) == 1


def test_interruttori_spenti(db):
    _registro(db)
    p = _passi()
    fc.registra(p, 1, "fatto", "AB", OGGI)
    assert fc_sync.dopo_azione("002-MI-X", p, {"sync_registro": False, "crea_compiti": False}, "admin", path=db, oggi=OGGI) == ""
    assert fc_sync.ultimo("ta", db) == (None, None)
    assert next(r for r in fc_sync.ultimo("rc", db)[1]["pratiche"] if r["Codice"] == "002-MI-X")["Stato"] == "S0-Apertura Pratica"


def test_senza_registro_salvato_non_si_rompe(db):
    p = _passi()
    assert "Compiti: 1 nuovi" in fc_sync.dopo_azione("002-MI-X", p, {}, "admin", path=db, oggi=OGGI)


def test_sessione_aperta_viene_aggiornata(db):
    import pandas as pd
    p = _passi()
    fc.registra(p, 1, "fatto", "AB", OGGI)
    ses = {"rc_df": pd.DataFrame([{"Codice": "002-MI-X", "Stato": "S0-Apertura Pratica", "Archivio": "Attiva"}]), "ta_df": pd.DataFrame(columns=__import__("ta").COLONNE)}
    fc_sync.dopo_azione("002-MI-X", p, {"responsabili": {"Commerciale": "marco"}}, "admin", path=db, sessione=ses, oggi=OGGI)
    assert ses["rc_df"].iloc[0]["Stato"] == "S1-Sopralluogo" and ses["rc_df_v"] == 1
    assert len(ses["ta_df"]) >= 1 and ses["ta_df_v"] == 1


def _salva_flusso(db, passi_attesa, mappa):
    righe = []
    p = _passi()
    for n in range(1, passi_attesa):
        if n in fc.NO_GO:
            fc.registra(p, n, "approva", "XX", OGGI)
        elif n != 11:
            fc.registra(p, n, "fatto", "XX", OGGI)
            if n in fc.APPROVAZIONE:
                fc.registra(p, n, "approva", "XX", OGGI)
    righe = [p[n] for n in sorted(p)]
    storage.salva_pratica("Flusso", {"passi": righe, "responsabili": mappa, "params": {"fermo_gg": 14}}, db, autore="t", modulo="fc")


def test_da_avvisare_approvatore_e_fermo():
    p = _passi()
    fc.registra(p, 1, "fatto", "AB", OGGI)
    fc.registra(p, 2, "fatto", "AB", OGGI)
    righe = list(p.values())                              # passo 3 (CdA) in attesa di decisione
    d = fc_sync.da_avvisare(righe, {"CdA": "saverio, anna"}, OGGI)
    assert sorted(u for u, _k, _t in d) == ["anna", "saverio"] and "aspetta la tua approvazione" in d[0][2]
    d2 = fc_sync.da_avvisare(righe, {"CdA": "saverio"}, OGGI + dt.timedelta(days=40))
    assert d2 and "aspetta la tua approvazione" in d2[0][2]
    q = _passi("Z")
    fc.registra(q, 1, "fatto", "AB", OGGI)
    d3 = fc_sync.da_avvisare(list(q.values()), {"DC": "raffaella", "Commerciale": "marco"}, OGGI + dt.timedelta(days=30))
    assert any(u == "marco" and "ferma da" in t for u, _k, t in d3)             # passo 2: «Commerciale + DC» -> il primo ruolo assegnato
    assert fc_sync.da_avvisare(list(q.values()), {}, OGGI) == []


def test_avvisa_in_chat_una_volta_al_giorno(db, monkeypatch):
    import chat
    _salva_flusso(db, 3, {"CdA": "saverio", "Commerciale": "marco"})
    monkeypatch.setattr(storage, "elenca_utenti", lambda path=None: [{"username": "saverio"}, {"username": "marco"}])
    es = fc_sync.avvisa(db, OGGI, sincrono=True, link="")
    assert es["chat"] == 1 and es["errori"] == []
    cid = chat.canale_diretto(fc_sync.AUTORE, "saverio", db)
    msgs = chat.messaggi(cid, "saverio", path=db)
    assert any("aspetta la tua approvazione" in str(m) for m in msgs)
    es2 = fc_sync.avvisa(db, OGGI, sincrono=True, link="")
    assert es2["chat"] == 0 and es2["saltati"] == 1
    es3 = fc_sync.avvisa(db, OGGI + dt.timedelta(days=1), sincrono=True, link="")
    assert es3["chat"] == 1


def test_avvisa_utente_sconosciuto_e_dry_run(db, monkeypatch):
    _salva_flusso(db, 3, {"CdA": "fantasma"})
    monkeypatch.setattr(storage, "elenca_utenti", lambda path=None: [{"username": "saverio"}])
    es = fc_sync.avvisa(db, OGGI, dry_run=True, link="")
    assert es["chat"] == 0 and len(es["da_inviare"]) == 1 and es["errori"] == []
    es = fc_sync.avvisa(db, OGGI, link="")
    assert es["chat"] == 0 and "non è un utente" in es["errori"][0]


def test_semafori_del_flusso_nel_cruscotto():
    import dd
    p = _passi()
    fc.registra(p, 1, "fatto", "AB", OGGI)
    fc.registra(p, 2, "fatto", "AB", OGGI)
    righe = [dict(r) for r in p.values()]
    m = {"fc": dd.metriche_da_payload("fc", {"passi": righe, "params": {"fermo_gg": 14}}, OGGI + dt.timedelta(days=30))}
    sem, _gen, _az = dd.semafori(m)
    r = next(x for x in sem if x["Area"] == "Flusso commesse")
    assert r["Stato"] == "warn" and r["Valore"] == "1" and r["Modulo"] == "fc"
    det = dd.dettagli(m)
    assert det and det[0]["id"] == "fc_ferme" and det[0]["righe"][0]["Commessa"] == "002-MI-X"
    import avvisi_dd
    assert "Flusso commesse" in avvisi_dd.AREE
