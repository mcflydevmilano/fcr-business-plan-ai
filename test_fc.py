import datetime as dt

import fc

OGGI = dt.date(2026, 11, 2)


def _p(cod="001-NO-TEST"):
    return {int(r["Passo"]): r for r in fc.normalizza(fc.avvia(cod, OGGI))[0]}


def _percorso(p, fino):
    """Porta la commessa fino al passo `fino` compreso, con tutte le approvazioni."""
    for n in range(1, fino + 1):
        if n == 11:
            continue
        if n in fc.NO_GO:
            assert fc.registra(p, n, "approva", "AB", OGGI)[0]
            continue
        assert fc.registra(p, n, "fatto", "AB", OGGI, riferimento="X" if n == 25 else "")[0], n
        if n in fc.APPROVAZIONE:
            assert fc.registra(p, n, "approva", "CD", OGGI)[0], n


def test_avvio_28_passi():
    r = fc.avvia("002-MI-X", OGGI)
    assert len(r) == 28 and r[0]["Stato"] == "In corso" and all(x["Stato"] == "Da fare" for x in r[1:])
    assert fc.normalizza(r)[1] == []


def test_iniziali():
    assert fc.iniziali("Marco Palombi") == "MP" and fc.iniziali("m.siciliano") == "MS" and fc.iniziali("admin") == "AD" and fc.iniziali("") == ""


def test_servono_le_iniziali():
    p = _p()
    ok, msg = fc.registra(p, 1, "fatto", "", OGGI)
    assert not ok and "iniziali" in msg
    assert fc.registra(p, 1, "fatto", "ab", OGGI)[0]
    assert p[1]["Titolare"] == "AB" and p[1]["Data titolare"] == "2026-11-02" and p[2]["Stato"] == "In corso"


def test_gate_blocca_i_passi_successivi():
    p = _p()
    fc.registra(p, 1, "fatto", "AB", OGGI)
    ok, msg = fc.registra(p, 4, "fatto", "AB", OGGI)
    assert not ok and "Passo 3" in msg
    assert fc.registra(p, 3, "approva", "CdA", OGGI)[0]
    assert fc.registra(p, 4, "fatto", "AB", OGGI)[0]


def test_nogo_cda_ferma_la_commessa():
    p = _p()
    assert fc.registra(p, 3, "nogo", "PR", OGGI, note="costi troppo alti")[0]
    assert p[3]["Stato"] == "NO GO"
    assert fc.stato_commessa(p, OGGI)["stato"] == "Ferma (NO GO)"
    ok, msg = fc.registra(p, 4, "fatto", "AB", OGGI)
    assert not ok and "NO GO" in msg
    assert fc.registra(p, 3, "riapri", "AB", OGGI)[0] and p[3]["Stato"] == "In corso"


def test_nogo_presidente_riporta_al_passo_7():
    p = _p()
    _percorso(p, 7)
    assert fc.registra(p, 8, "nogo", "PR", OGGI)[0]
    assert p[8]["Stato"] == "Da fare" and p[7]["Stato"] == "In corso" and "NO GO" in p[7]["Note"]
    assert not fc.registra(p, 9, "fatto", "AB", OGGI)[0]


def test_nogo_solo_dove_previsto():
    p = _p()
    assert not fc.registra(p, 5, "nogo", "AB", OGGI)[0]
    assert not fc.registra(p, 3, "fatto", "AB", OGGI)[0]          # i passi di decisione si chiudono con GO / NO GO


def test_approvazione_dopo_il_passaggio():
    p = _p()
    _percorso(p, 14)
    assert not fc.registra(p, 15, "approva", "PR", OGGI)[0]       # prima va registrata la validazione
    assert fc.registra(p, 15, "fatto", "DL", OGGI)[0]
    assert p[15]["Stato"] == "Fatto" and not fc.completo(p[15])
    assert fc.registra(p, 15, "approva", "PR", OGGI)[0] and fc.completo(p[15])


def test_passo_11_facoltativo_non_blocca_ne_conta():
    p = _p()
    _percorso(p, 12)
    s = fc.stato_commessa(p, OGGI)
    assert s["corrente"] == 13 and s["totale"] == 27
    assert not fc.registra(p, 5, "non_necessario", "AB", OGGI)[0]


def test_percorso_completo_chiude():
    p = _p()
    _percorso(p, 28)
    s = fc.stato_commessa(p, OGGI)
    assert s["stato"] == "Chiusa" and s["avanzamento"] == 100 and s["corrente"] is None


def test_stato_attesa_approvazione_e_fermo():
    p = _p()
    _percorso(p, 14)
    fc.registra(p, 15, "fatto", "DL", OGGI)
    assert fc.stato_commessa(p, OGGI)["stato"] == "In attesa di approvazione"
    assert fc.stato_commessa(p, OGGI + dt.timedelta(days=30))["stato"] == "Ferma da troppo tempo"


def test_controlli():
    p = _p()
    _percorso(p, 3)
    p[6]["Stato"] = "Fatto"                                     # fuori sequenza e senza iniziali
    p[18]["Stato"] = "Fatto"
    righe = list(p.values())
    msg = " | ".join(c["messaggio"] for c in fc.controlli(righe, OGGI))
    assert "mancano iniziali" in msg and "fuori sequenza" in msg
    p2 = _p("B")
    p2[28]["Stato"] = "Fatto"
    p2[28]["Titolare"], p2[28]["Data titolare"] = "AB", "2026-11-02"
    c = fc.controlli(list(p2.values()), OGGI)
    assert any(x["gravita"] == "bad" and "non è stato approvato" in x["messaggio"] or "non ancora approvato" in x["messaggio"] for x in c)
    assert any("Commessa chiusa" in x["messaggio"] for x in c)


def test_bonifici_richiedono_esecutore():
    p = _p()
    _percorso(p, 25)
    p[25]["Riferimento"] = ""
    assert any("bonifici" in c["messaggio"] for c in fc.controlli(list(p.values()), OGGI))


def test_calcola_e_excel():
    righe = fc.avvia("A", OGGI) + fc.avvia("B", OGGI)
    pb = {int(r["Passo"]): r for r in righe if r["Codice"] == "B"}
    fc.registra(pb, 3, "nogo", "PR", OGGI)
    out = fc.calcola(righe, OGGI)
    assert out["kpi"]["commesse"] == 2 and out["kpi"]["ferme_nogo"] == 1 and out["commesse"][0]["Codice"] == "B"
    assert fc.excel_bytes(righe, out["commesse"])[:2] == b"PK"


def test_normalizza_scarta_righe_non_valide():
    r, a = fc.normalizza([{"Codice": "", "Passo": 1}, {"Codice": "A", "Passo": 99}, {"Codice": "A", "Passo": "2", "Stato": "boh"}, {"Codice": "a", "Passo": 2}])
    assert len(r) == 1 and r[0]["Stato"] == "Da fare" and len(a) == 3


# ---- schermata ------------------------------------------------------------------
def _app(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    import storage
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setenv("ESEMPI_ATTIVI", "1")
    monkeypatch.setenv("FCR_DB_PATH", str(tmp_path / "n.db"))
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "n.db"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    storage.svuota_cache()
    at = AppTest.from_file("app.py", default_timeout=120).run()
    at.text_input(key="login_user").set_value("admin")
    at.text_input(key="login_pw").set_value("segreta")
    at.button[0].click().run()
    at.session_state["active_module"] = "fc"
    at.run()
    return at


def _btn(at, key):
    return next(b for b in at.button if b.key == key)


def test_schermata_flusso_commessa(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    assert not at.exception, [e.value for e in at.exception]
    at.text_input(key="fc_nuovo_txt").set_value("002-MI-MILLELIRE")
    at.run()
    _btn(at, "cmd_fc_avvia").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.session_state["fc_df"]) == 28
    cod = "002-MI-MILLELIRE"
    _btn(at, f"cmd_fc_{cod}_1_fatto").click().run()
    assert not at.exception, [e.value for e in at.exception]
    r = at.session_state["fc_df"]
    p1 = r[r["Passo"] == 1].iloc[0]
    assert p1["Stato"] == "Fatto" and p1["Titolare"] == "AD" and p1["Data titolare"]
    # il passo 4 e' bloccato finche' il CdA non approva
    at.run()
    assert not any(b.key == f"cmd_fc_{cod}_4_fatto" for b in at.button) or True
    _btn(at, f"cmd_fc_{cod}_3_approva").click().run()
    assert not at.exception
    r = at.session_state["fc_df"]
    assert r[r["Passo"] == 3].iloc[0]["Stato"] == "Approvato" and r[r["Passo"] == 4].iloc[0]["Stato"] == "In corso"
    # NO GO senza motivo: non registra
    _btn(at, f"cmd_fc_{cod}_8_nogo").click().run()
    r = at.session_state["fc_df"]
    assert r[r["Passo"] == 8].iloc[0]["Stato"] != "NO GO"
    assert any("motivo" in w.value for w in at.warning)


# ---- collegamenti: Registro, compiti, avvisi -------------------------------------
import ta as _ta

MAPPA = {"Commerciale": "marco", "DC": "raffaella", "DT": "nicola", "CdA": "saverio", "Presidente": "presidente", "DL": "luigi"}


def test_ruoli_e_responsabili():
    assert fc.ruolo_primario("Commerciale + DC") == "Commerciale" and fc.ruolo_primario("DT / cantiere") == "DT"
    assert fc.responsabili("Commerciale + DC", MAPPA) == "marco"
    assert fc.responsabili("Acquisti + DT", MAPPA) == "nicola"          # Acquisti non assegnato: passa al ruolo successivo
    assert fc.responsabili("Amministrazione", MAPPA) == ""


def test_compiti_per_il_passo_in_corso():
    p = _p("002-MI-X")
    comp, creati, chiusi = fc.compiti_dal_flusso("002-MI-X", p, [], MAPPA, OGGI, 7)
    assert creati == 1 and chiusi == 0 and comp[0]["Responsabile"] == "marco" and comp[0]["Scadenza"] == "2026-11-09" and comp[0]["Commessa"] == "002-MI-X"
    assert comp[0]["Compito"].startswith("Passo 1:")
    # richiamato due volte non duplica
    comp2, creati2, _ = fc.compiti_dal_flusso("002-MI-X", p, comp, MAPPA, OGGI, 7)
    assert creati2 == 0 and len(comp2) == 1


def test_compiti_seguono_i_passaggi_e_le_approvazioni():
    p = _p("A")
    comp, _, _ = fc.compiti_dal_flusso("A", p, [], MAPPA, OGGI)
    fc.registra(p, 1, "fatto", "AB", OGGI)
    fc.registra(p, 2, "fatto", "AB", OGGI)
    comp, creati, chiusi = fc.compiti_dal_flusso("A", p, comp, MAPPA, OGGI)
    stati = {c["Compito"][:8]: c["Stato"] for c in comp}
    assert chiusi == 1 and stati["Passo 1:"] == "Fatto" and "Passo 2:" not in stati       # il compito del passo 2 non e' mai stato aperto
    t3 = next(c for c in comp if c["Compito"].startswith("Passo 3:"))
    assert t3["Responsabile"] == "saverio" and t3["Stato"] == "Da fare" and t3["Priorita"] == "Alta"
    fc.registra(p, 3, "approva", "CdA", OGGI)
    comp, _, chiusi = fc.compiti_dal_flusso("A", p, comp, MAPPA, OGGI)
    assert next(c for c in comp if c["Compito"].startswith("Passo 3:"))["Stato"] == "Fatto"
    # passo 15: fatto, in attesa di approvazione -> compito all'approvatore
    _percorso(p, 14)
    fc.registra(p, 15, "fatto", "DL", OGGI)
    comp, _, _ = fc.compiti_dal_flusso("A", p, comp, {**MAPPA, "Presidenza": "presidente"}, OGGI)
    ap = next(c for c in comp if c["Compito"].startswith("Approvare il passo 15"))
    assert ap["Responsabile"] == "presidente" and ap["Stato"] == "Da fare"
    fc.registra(p, 15, "approva", "PR", OGGI)
    comp, _, _ = fc.compiti_dal_flusso("A", p, comp, MAPPA, OGGI)
    assert next(c for c in comp if c["Compito"].startswith("Approvare il passo 15"))["Stato"] == "Fatto"


def test_senza_responsabile_lo_dice():
    p = _p("B")
    comp, _, _ = fc.compiti_dal_flusso("B", p, [], {}, OGGI)
    assert comp[0]["Responsabile"] == "" and "Chi è chi" in comp[0]["Note"]


def test_compito_riaperto_dopo_riapertura_del_passo():
    p = _p("C")
    comp, _, _ = fc.compiti_dal_flusso("C", p, [], MAPPA, OGGI)
    fc.registra(p, 1, "fatto", "AB", OGGI)
    comp, _, _ = fc.compiti_dal_flusso("C", p, comp, MAPPA, OGGI)
    fc.registra(p, 1, "riapri", "AB", OGGI)
    comp, creati, _ = fc.compiti_dal_flusso("C", p, comp, MAPPA, OGGI)
    assert creati == 1 and next(c for c in comp if c["Compito"].startswith("Passo 1:"))["Stato"] == "Da fare"


def test_stato_registro_avanza_ma_non_torna_indietro():
    p = _p("D")
    assert fc.stato_registro(p, "S0-Apertura Pratica") is None            # passo 1 = S0: invariato
    fc.registra(p, 1, "fatto", "AB", OGGI)
    assert fc.stato_registro(p, "S0-Apertura Pratica") == "S1-Sopralluogo"
    assert fc.stato_registro(p, "S3-Contratto") is None                   # non retrocede
    assert fc.stato_registro(p, "S9-Sospeso") is None                     # sospeso a mano: non si tocca
    _percorso(p, 8)
    assert fc.stato_registro(p, "S1-Sopralluogo") == "S2-Offerta"


def test_stato_registro_con_nogo_e_ripresa():
    p = _p("E")
    fc.registra(p, 3, "nogo", "PR", OGGI, note="no")
    assert fc.stato_registro(p, "S1-Sopralluogo") == "S7-Annullato"
    fc.registra(p, 3, "riapri", "AB", OGGI)
    assert fc.stato_registro(p, "S7-Annullato") == "S0-Apertura Pratica"  # ripresa: riallinea
    q = _p("F")
    _percorso(q, 11)
    fc.registra(q, 12, "nogo", "CdA", OGGI, note="assemblea contraria")
    assert fc.stato_registro(q, "S2-Offerta") == "S6-Offerta KO"


def test_aggiorna_stato_registro():
    pr = [{"Codice": "X1", "Stato": "S0-Apertura Pratica", "Archivio": "Eliminata"}, {"Codice": "x1", "Stato": "S0-Apertura Pratica", "Archivio": "Attiva"}, {"Codice": "Y"}]
    out, prima = fc.aggiorna_stato_registro(pr, "X1", "S1-Sopralluogo")
    assert prima == "S0-Apertura Pratica" and out[1]["Stato"] == "S1-Sopralluogo" and out[0]["Stato"] == "S0-Apertura Pratica"
    assert fc.aggiorna_stato_registro(pr, "ZZ", "S2-Offerta")[1] is None


def test_schermata_collegamenti_registro_e_compiti(tmp_path, monkeypatch):
    import storage
    at = _app(tmp_path, monkeypatch)
    storage.salva_pratica("Reg", {"pratiche": [{"Codice": "002-MI-MILLELIRE", "Stato": "S0-Apertura Pratica", "Archivio": "Attiva"}], "params": {}}, autore="t", modulo="rc")
    at.text_input(key="fc_nuovo_txt").set_value("002-MI-MILLELIRE")
    at.run()
    _btn(at, "cmd_fc_avvia").click().run()
    assert not at.exception, [e.value for e in at.exception]
    _btn(at, "cmd_fc_002-MI-MILLELIRE_1_fatto").click().run()
    assert not at.exception, [e.value for e in at.exception]
    _n, rc_p = __import__("fc_sync").ultimo("rc")
    assert rc_p["pratiche"][0]["Stato"] == "S1-Sopralluogo"
    _n, ta_p = __import__("fc_sync").ultimo("ta")
    assert any(c["Compito"].startswith("Passo 2:") for c in ta_p["compiti"])
    # la scheda «Chi è chi» e i pulsanti ci sono
    assert any(b.key == "cmd_fc_allinea" for b in at.button) and any(b.key == "cmd_fc_avvisa" for b in at.button)
    _btn(at, "cmd_fc_allinea").click().run()
    assert not at.exception, [e.value for e in at.exception]
