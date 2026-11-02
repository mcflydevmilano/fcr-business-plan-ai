import os

import spazio


def test_leggibile():
    assert spazio.leggibile(0) == "0 B"
    assert spazio.leggibile(1536) == "1,5 KB"
    assert spazio.leggibile(5 * 1024 ** 3) == "5,0 GB"


def test_stato_soglie():
    assert spazio.stato(10) == "ok"
    assert spazio.stato(75) == "attenzione"
    assert spazio.stato(89.9) == "attenzione"
    assert spazio.stato(90) == "critico"
    assert spazio.stato(None) == "nd"


def test_uso_disco_reale(tmp_path):
    r = spazio.uso(str(tmp_path))
    assert r["disponibile"] and r["totale"] > 0 and 0 <= r["perc"] <= 100
    assert r["usato"] + r["libero"] <= r["totale"] * 1.01


def test_cartella_inesistente(tmp_path):
    r = spazio.uso(str(tmp_path / "manca"))
    assert not r["disponibile"] and "non trovata" in r["motivo"]


def test_nas_non_montato_non_si_confonde_col_server(tmp_path, monkeypatch):
    # la cartella esiste ma non e' un punto di mount: non si deve mostrare lo spazio del disco del server al posto del NAS
    monkeypatch.setenv("FCR_NAS_PATH", str(tmp_path))
    r = spazio.nas()
    assert not r["disponibile"] and "non collegato" in r["motivo"]


def test_nas_montato(tmp_path, monkeypatch):
    monkeypatch.setenv("FCR_NAS_PATH", str(tmp_path))
    monkeypatch.setattr(os.path, "ismount", lambda p: True)
    r = spazio.nas()
    assert r["disponibile"] and r["configurato"]


def test_dimensione_cartella(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"x" * 1000)
    (tmp_path / "s").mkdir()
    (tmp_path / "s" / "b.bin").write_bytes(b"y" * 500)
    assert spazio.dimensione_cartella(str(tmp_path)) == (1500, 2)
    assert spazio.dimensione_cartella(str(tmp_path / "no")) == (0, 0)


def test_dimensione_db_sqlite(tmp_path):
    p = tmp_path / "x.db"
    p.write_bytes(b"z" * 2048)
    assert spazio.dimensione_db(str(p)) == 2048


def test_avvisi(monkeypatch):
    pieno = {"disponibile": True, "stato": "critico", "perc": 95.0, "libero": 5 * 1024 ** 3}
    ok = {"disponibile": True, "stato": "ok", "perc": 20.0, "libero": 1}
    spento = {"disponibile": False, "stato": "nd", "perc": None, "libero": 0}
    assert len(spazio.avvisi({"server": pieno, "nas": spento})) == 1
    assert "server" in spazio.avvisi({"server": pieno, "nas": ok})[0]
    assert spazio.avvisi({"server": ok, "nas": spento}) == []


def test_riepilogo_ha_tutto(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path))
    (tmp_path / "b.gz").write_bytes(b"1" * 10)
    r = spazio.riepilogo(str(tmp_path / "nuovo.db"))
    assert set(r) == {"server", "nas", "db", "backup"} and r["backup"]["file"] == 1


def test_scheda_spazio_nell_amministrazione(monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setenv("FCR_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("FCR_NAS_PATH", raising=False)
    import storage
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "t.db"))
    app = AppTest.from_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py"), default_timeout=120)
    app.session_state["utente"] = {"username": "tester", "ruolo": "admin", "origine": "app_password"}
    app.session_state["active_module"] = "admin"
    app.run()
    assert not app.exception
    assert any("Spazio" in t.label for t in app.tabs)
    testo = " ".join(m.value for m in app.markdown)
    assert "Server (disco del computer in ufficio)" in testo and "NAS (archivio e copie di sicurezza)" in testo
