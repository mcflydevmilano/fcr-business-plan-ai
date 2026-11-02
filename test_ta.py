import datetime as dt

import pandas as pd

import ta

OGGI = dt.date(2026, 11, 2)


def test_riga_default_e_chiusura():
    r = ta.riga({"Compito": "Chiamare Rossi", "Stato": "Done"}, OGGI)
    assert r["Stato"] == "Fatto" and r["Chiuso"] == "2026-11-02" and r["Priorita"] == "Media" and r["Creato"] == "2026-11-02"
    a = ta.riga({"Compito": "x", "Stato": "boh", "Priorita": "High", "Scadenza": "05/11/2026"}, OGGI)
    assert a["Stato"] == "Da fare" and a["Priorita"] == "Alta" and a["Scadenza"] == "2026-11-05" and a["Chiuso"] == ""
    assert ta.riga({}, OGGI) is None


def test_normalizza_scarta_senza_testo():
    righe, avv = ta.normalizza([{"Compito": "a"}, {"Responsabile": "mario"}, {}], OGGI)
    assert len(righe) == 1 and len(avv) == 1


def test_muovi_riapre_e_chiude():
    r = ta.riga({"Compito": "a"}, OGGI)
    f = ta.muovi(r, "Fatto", OGGI)
    assert f["Stato"] == "Fatto" and f["Chiuso"] == "2026-11-02"
    assert ta.muovi(f, "In corso", OGGI)["Chiuso"] == ""


def test_calcola_ritardi_e_responsabili():
    righe, _ = ta.normalizza([
        {"Compito": "a", "Responsabile": "mario", "Scadenza": "2026-10-30"},
        {"Compito": "b", "Responsabile": "mario", "Scadenza": "2026-11-03"},
        {"Compito": "c", "Scadenza": "2026-10-01", "Stato": "Fatto"},
        {"Compito": "d", "Responsabile": "anna", "Stato": "In attesa"}], OGGI)
    o = ta.calcola(righe, OGGI)
    k = o["kpi"]
    assert (k["aperti"], k["ritardo"], k["in_arrivo"], k["senza_resp"], k["in_attesa"]) == (3, 1, 1, 0, 1)
    assert o["per_responsabile"][0]["Responsabile"] == "mario" and o["per_responsabile"][0]["In ritardo"] == 1


def test_filtra_e_ordina():
    righe, _ = ta.normalizza([{"Compito": "a", "Responsabile": "Mario Rossi", "Commessa": "X", "Scadenza": "2026-12-01"},
                              {"Compito": "b", "Responsabile": "anna", "Commessa": "Y", "Scadenza": "2026-11-05", "Priorita": "Alta"},
                              {"Compito": "c", "Responsabile": "anna", "Stato": "Fatto"}], OGGI)
    assert [r["Compito"] for r in ta.filtra(righe, responsabile="rossi")] == ["a"]
    assert [r["Compito"] for r in ta.filtra(righe, solo_aperti=True)] == ["a", "b"]
    assert [r["Compito"] for r in ta.ordina(righe)][0] == "b"


def test_export_excel():
    r, _ = ta.normalizza([{"Compito": "Ordinare ponteggio", "Responsabile": "Mario", "Stato": "In corso"}], OGGI)
    assert ta.excel_bytes(r)[:2] == b"PK"


def test_scadenze_nel_calendario():
    import calendario
    p = {"ta": {"compiti": [{"Compito": "Ordinare ponteggio", "Responsabile": "mario", "Scadenza": "2026-11-05"},
                            {"Compito": "Fatto già", "Scadenza": "2026-11-05", "Stato": "Fatto"}], "params": {"preavviso_gg": 3}}}
    ev = calendario.eventi(p, OGGI, 60)
    assert len(ev) == 1 and ev[0]["Categoria"] == "Attività" and ev[0]["Modulo"] == "Compiti e attività" and ev[0]["Giorni"] == 3 and ev[0]["Stato"] == "warn"


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
    at.session_state["active_module"] = "ta"
    at.run()
    return at


def test_schermata_compiti(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    assert not at.exception, [e.value for e in at.exception]
    assert not [u for u in at.get("file_uploader") if "monday" in str(u.key)]
    righe = [ta.riga({"Compito": "Ordinare ponteggio", "Responsabile": "admin", "Stato": "In corso", "Scadenza": "2026-11-10"}),
             ta.riga({"Compito": "Inviare PEC", "Responsabile": "anna", "Stato": "Fatto"})]
    at.session_state["ta_df"] = pd.DataFrame(righe, columns=ta.COLONNE)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    df = at.session_state["ta_df"]
    assert sorted(df["Compito"]) == ["Inviare PEC", "Ordinare ponteggio"]
    # sposta «Ordinare ponteggio» da In corso a In attesa
    i = int(df.index[df["Compito"] == "Ordinare ponteggio"][0])
    next(b for b in at.button if b.key == f"cmd_ta_{i}_a").click().run()
    assert not at.exception
    assert at.session_state["ta_df"].loc[i, "Stato"] == "In attesa"
