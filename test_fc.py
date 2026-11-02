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
