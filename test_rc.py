"""Registro commerciale: lettura dell'Excel, cruscotto, scadenze, ricerca, esportazione e apertura dello strumento."""
import datetime as dt
import io
import os
import tempfile

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import rc
import rc_ui
import storage

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
INT = ["Codice", "Data inserimento pratica", "Data sopralluogo", "data offerta", "Città", "PR", "Indirizzo", "Amministratore", "Commerciale", "Affiancato da", "Finanziamento", "N. UI",
       "Stato", "Tipo lavori", "Prossimo intervento", "Revisioni", "Scadenza prossimo intervento", "Chi deve fare prossimo intervento", "Valore stimato da QTE", "% successo stimata", "Valore pipeline", "Note", "Banca"]


@pytest.fixture(autouse=True)
def db(monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
    monkeypatch.setenv("APP_PASSWORD", "segreta")


def _riga(**kw):
    base = dict.fromkeys(INT)
    base.update(kw)
    return [base[c] for c in INT]


def _xlsx(attive, eliminate=None):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        riga0 = [" "] + [None] * (len(INT) - 1)        # come nel file reale: sopra l'intestazione c'e' una riga di totali
        pd.DataFrame([riga0, INT, *attive]).to_excel(w, sheet_name="Registro", header=False, index=False)
        pd.DataFrame([INT, *(eliminate or [])]).to_excel(w, sheet_name="Eliminati", header=False, index=False)
        pd.DataFrame([["S0-Apertura Pratica", None, "sì"]]).to_excel(w, sheet_name="Cpodice", header=False, index=False)
    buf.seek(0)
    return buf


OGGI = dt.date(2026, 10, 22)


def _file():
    a = [_riga(Codice="001-MI-ROSSI", **{"Città": "Milano"}, PR="mi", Indirizzo="Via Roma 1", Amministratore="Bianchi", Commerciale="Verdi", Stato="s2-Offerta", **{"Valore stimato da QTE": 100000, "% successo stimata": 0.5},
               **{"Prossimo intervento": "S3-Contratto", "Scadenza prossimo intervento": pd.Timestamp("2026-10-01"), "Chi deve fare prossimo intervento": "Verdi", "data offerta": pd.Timestamp("2026-09-01")}),
         _riga(Codice="002-TO-NERI", **{"Città": "Torino"}, PR="TO", Indirizzo="Via Po 2", Commerciale="Gialli", Stato="S0-Apertura Pratica", **{"Valore stimato da QTE": "250.000", "% successo stimata": "20%", "Finanziamento": "x"}),
         _riga(Codice="003-VA-BLU", **{"Città": "Varese"}, Indirizzo="Via Alba 3", Stato="S3-Contratto", **{"Valore stimato da QTE": 50000, "% successo stimata": 100}),
         _riga(), _riga()]
    e = [_riga(Codice="016-MI-OLD", **{"Città": "Milano"}, Indirizzo="Via Vecchia", Stato="S7-Annullato")]
    return _xlsx(a, e)


def test_stati_e_percentuali():
    assert rc.stato_canonico("s0-Apertura Pratica") == "S0-Apertura Pratica"
    assert rc.stato_canonico("S2") == "S2-Offerta" and rc.stato_canonico("Offerta") == "S2-Offerta" and rc.stato_canonico("") == ""
    assert rc.percentuale(0.5) == 50 and rc.percentuale("20%") == 20 and rc.percentuale(100) == 100 and rc.percentuale(None) == 0


def test_importa_excel_legge_registro_ed_eliminati():
    righe, avvisi, rapp = rc.importa_excel(_file())
    assert rapp["righe"] == 3 and rapp["eliminate"] == 1 and set(rapp["fogli"]) == {"Registro", "Eliminati"}
    r = {x["Codice"]: x for x in righe}
    assert r["001-MI-ROSSI"]["Stato"] == "S2-Offerta" and r["001-MI-ROSSI"]["PR"] == "MI" and r["001-MI-ROSSI"]["Successo"] == 50
    assert r["001-MI-ROSSI"]["Scadenza"] == "2026-10-01" and r["002-TO-NERI"]["Valore"] == 250000 and r["002-TO-NERI"]["Finanziamento"] == "sì"
    assert r["016-MI-OLD"]["Archivio"] == "Eliminata"
    assert rc.pipeline(r["001-MI-ROSSI"]) == 50000


def test_cruscotto_e_avvisi():
    righe, _, _ = rc.importa_excel(_file())
    o = rc.calcola(righe, OGGI)
    k = o["kpi"]
    assert k["n_attive"] == 3 and k["n_eliminate"] == 1 and k["n_vinte"] == 1 and k["n_scadute"] == 1
    assert k["pipeline"] == 50000 + 50000 + 50000 and k["valore_aperte"] == 400000
    assert {e["Commerciale"] for e in o["per_commerciale"]} == {"Verdi", "Gialli", "(senza commerciale)"}
    assert any("scaduti" in a for a in o["avvisi"]) and any("commerciale" in a for a in o["avvisi"])
    assert o["da_fare"][0]["Giorni"] == -21 and o["da_fare"][0]["Stato_scad"] == "bad"


def test_filtra_e_unisci():
    righe, _, _ = rc.importa_excel(_file())
    assert [r["Codice"] for r in rc.filtra(righe, "milano")] == ["001-MI-ROSSI"]
    assert [r["Codice"] for r in rc.filtra(righe, "", stati=["S3-Contratto"])] == ["003-VA-BLU"]
    assert [r["Codice"] for r in rc.filtra(righe, "", archivio="Eliminata")] == ["016-MI-OLD"]
    nuove = [dict(righe[0], Stato="S3-Contratto"), dict(righe[0], Codice="009-NEW")]
    u = rc_ui.unisci(righe, nuove)
    assert len(u) == len(righe) + 1 and [x for x in u if x["Codice"] == "001-MI-ROSSI"][0]["Stato"] == "S3-Contratto"


def test_codice_doppio_e_stato_strano():
    r, a = rc.normalizza([{"Codice": "A", "Stato": "S2", "Indirizzo": "x"}, {"Codice": "a", "Stato": "boh", "Indirizzo": "y"}])
    assert len(r) == 2 and any("più di una volta" in x for x in a) and any("non riconosciuto" in x for x in a)


def test_excel_in_uscita():
    righe, _, _ = rc.importa_excel(_file())
    b = rc.excel_bytes(righe, rc.calcola(righe, OGGI))
    x = pd.ExcelFile(io.BytesIO(b))
    assert {"Pratiche", "Per stato", "Per commerciale", "Da fare", "Eliminate"} <= set(x.sheet_names)
    assert len(pd.read_excel(x, "Pratiche")) == 3


def test_file_sbagliato():
    buf = io.BytesIO()
    pd.DataFrame([["a", "b"], [1, 2]]).to_excel(buf, index=False, header=False)
    buf.seek(0)
    righe, avvisi, rapp = rc.importa_excel(buf)
    assert righe == [] and rapp["saltati"]


def _admin(modulo):
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["utente"] = {"username": "root", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = modulo
    return at.run()


def test_strumento_si_apre_vuoto_e_con_dati():
    at = _admin("rc")
    assert not at.exception, [e.value for e in at.exception]
    assert any("registro è vuoto" in i.value for i in at.info)
    righe, _, _ = rc.importa_excel(_file())
    at.session_state["rc_df"] = rc_ui._df(righe)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Pratiche attive" in m.value for m in at.markdown)


def test_hub_mostra_la_scheda_e_i_permessi():
    import permessi
    assert "rc" in permessi.PROFILI_BASE["commerciale"] and "rc" in permessi.TUTTI
    at = _admin(None)
    assert not at.exception and any("Registro commerciale" in b.label for b in at.button)


def test_cruscotto_del_commerciale():
    righe, _, _ = rc.importa_excel(_file())
    nomi = rc.nomi_commerciali(righe)
    assert "Verdi" in nomi and "Gialli" in nomi
    assert rc.riconosci_commerciale("verdi", nomi) == "Verdi" and rc.riconosci_commerciale("boh", nomi) == ""
    assert rc.riconosci_commerciale("mrossi", ["Rossi Mario"], [{"Utente": "mrossi", "Persona": "Mario Rossi"}]) == "Rossi Mario"
    v = rc.vista_commerciale(righe, "Verdi", OGGI)
    assert v["kpi"]["n_attive"] == 1 and v["kpi"]["pipeline"] == 50000 and len(v["da_fare"]) == 1 and v["da_fare"][0]["Stato_scad"] == "bad"
    v2 = rc.vista_commerciale(righe, "Gialli", OGGI)
    assert v2["kpi"]["pipeline"] == 50000 and v2["da_fare"] == []
