"""Velocita': connessioni al database riutilizzate, cache delle letture, grafici non ridisegnati, accesso e rotella di caricamento."""
import sys
import types

import pytest

import charts
import storage
import theme


class FinteCon:
    def __init__(self, url, vive):
        self.url, self.vive, self.closed, self.broken = url, vive, False, False
        self.eseguite = []

    def execute(self, sql, par=()):
        if not self.vive[0] and sql.strip().upper().startswith("SELECT 1"):
            raise RuntimeError("connessione chiusa dal server")
        self.eseguite.append(sql)
        return self

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def commit(self): pass
    def rollback(self): pass

    def close(self):
        self.closed = True


@pytest.fixture
def pg_finto(monkeypatch):
    aperte, vive = [], [True]

    def connect(url, **kw):
        assert kw.get("prepare_threshold") is None            # niente istruzioni preparate (pooler di Neon)
        c = FinteCon(url, vive)
        aperte.append(c)
        return c
    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=connect))
    monkeypatch.setenv("DATABASE_URL", "postgresql://finto/db")
    storage.chiudi_connessioni()
    storage._PG_PRONTO.discard("postgresql://finto/db")
    yield aperte, vive
    storage.chiudi_connessioni()
    storage._PG_PRONTO.discard("postgresql://finto/db")


def test_la_connessione_postgres_si_riusa(pg_finto):
    aperte, _ = pg_finto
    for _ in range(6):
        with storage._db() as con:
            con.execute("SELECT 2")
    assert len(aperte) == 1 and not aperte[0].closed


def test_connessione_morta_si_riapre(pg_finto, monkeypatch):
    aperte, _ = pg_finto
    monkeypatch.setattr(storage, "_POOL_PING_DOPO", -1)       # a ogni uso controlla che sia ancora viva
    with storage._db() as con:
        con.execute("SELECT 2")
    orig = FinteCon.execute

    def ex(self, sql, par=()):
        if self is aperte[0] and sql.strip().upper().startswith("SELECT 1"):
            raise RuntimeError("connessione chiusa dal server")      # la prima connessione e' morta mentre era ferma
        return orig(self, sql, par)
    monkeypatch.setattr(FinteCon, "execute", ex)
    with storage._db() as con:
        con.execute("SELECT 3")
    assert len(aperte) == 2 and aperte[0].closed and not aperte[1].closed


def test_errore_nel_blocco_non_lascia_transazioni(pg_finto):
    aperte, _ = pg_finto
    with pytest.raises(ValueError):
        with storage._db():
            raise ValueError("x")
    with storage._db():
        pass
    assert len(aperte) == 1


def test_elenco_salvataggi_in_cache_e_invalidato_dalle_scritture(tmp_path):
    db = str(tmp_path / "v.db")
    storage.salva_pratica("Alfa", {"a": 1}, db, modulo="sl")
    n = []
    orig = storage._db

    import contextlib

    @contextlib.contextmanager
    def spia(path=None):
        n.append(1)
        with orig(path) as c:
            yield c
    storage._db = spia
    try:
        for _ in range(5):
            assert [p["nome"] for p in storage.elenca_pratiche(db, modulo="sl")] == ["Alfa"]
            storage.ultimi_aggiornamenti(db)
        assert len(n) == 1                                      # una sola lettura per dieci richieste
        storage.salva_pratica("Beta", {"a": 2}, db, modulo="sl")
        assert {p["nome"] for p in storage.elenca_pratiche(db, modulo="sl")} == {"Alfa", "Beta"}
        storage.elimina_pratica("Alfa", db, modulo="sl")
        assert [p["nome"] for p in storage.elenca_pratiche(db, modulo="sl")] == ["Beta"]
    finally:
        storage._db = orig


def test_cache_restituisce_copie(tmp_path):
    db = str(tmp_path / "c.db")
    storage.salva_pratica("x", {"l": [1]}, db)
    f = lambda: storage.carica_pratica("x", db)          # noqa: E731
    a = storage.cache_lettura("k", f, db)
    a["l"].append(99)
    assert storage.cache_lettura("k", f, db) == {"l": [1]}


def test_grafici_non_si_ridisegnano_se_i_dati_sono_uguali(monkeypatch):
    chiamate = []
    from matplotlib.figure import Figure
    orig = Figure.savefig
    monkeypatch.setattr(Figure, "savefig", lambda self, *a, **k: (chiamate.append(1), orig(self, *a, **k))[1])
    a = charts.fig_png(charts.fig_scadenze({"bad": 1, "warn": 2, "ok": 3}), 100)
    b = charts.fig_png(charts.fig_scadenze({"bad": 1, "warn": 2, "ok": 3}), 100)
    assert a == b and len(chiamate) == 1
    c = charts.fig_png(charts.fig_scadenze({"bad": 5, "warn": 2, "ok": 3}), 100)      # dati diversi: si ridisegna
    assert len(chiamate) == 2 and c != a


def test_rotella_di_caricamento_con_logo_aetheris():
    css = theme.CSS
    assert 'data-test-script-state="running"' in css and "ldSpin" in css and "stStatusWidget" in css
    assert "data:image/png;base64," in css                     # l'emblema e' incorporato


def test_accesso_nuovo(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("app.py", default_timeout=60).run()
    assert not at.exception
    tutto = " ".join(m.value for m in at.markdown)
    assert "FCR GENERAL CONTRACTOR" in tutto and "Accedi alla suite" in tutto and "lg-badge" in tutto and "Aetheris" in tutto
    assert at.text_input(key="login_user").placeholder


def test_blocchi_style_separati_da_riga_vuota():
    """Due <style> sulla stessa riga: Streamlit mostrerebbe il secondo come testo."""
    assert "</style>\n\n<style>" in theme.CSS


def test_sintassi_compatibile_con_python_311():
    """Streamlit Cloud puo' usare Python 3.11: niente f-string con barre rovesciate o apici uguali dentro le graffe."""
    import glob
    import shutil
    import subprocess
    py = shutil.which("python3.11")
    if not py:
        pytest.skip("python3.11 non disponibile")
    for f in glob.glob("*.py"):
        r = subprocess.run([py, "-c", "import sys;compile(open(sys.argv[1],encoding='utf-8').read(), sys.argv[1], 'exec')", f], capture_output=True, text=True)
        assert r.returncode == 0, f"{f}: {r.stderr[-300:]}"
