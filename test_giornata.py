"""«La mia giornata»: caselle diverse per profilo, solo su strumenti consentiti, solo dati veri."""
import datetime as dt

import pytest

import demo
import miagiornata
import permessi
import storage


@pytest.fixture
def dati(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    p = str(tmp_path / "g.db")
    storage.svuota_cache()
    return p


def _payloads_demo():
    """Payload dimostrativi con date di oggi, passati come se fossero salvataggi veri."""
    dati = demo._leggi()
    oggi = dt.date.today()
    base = dt.date.fromisoformat(dati["_base"])
    return {m: demo.sposta_date(p, (oggi - base).days) for m, p in dati.items() if m != "_base"}


def _c(profilo, utente="x", ruolo="utente", **kw):
    cfg = permessi.configurazione_base()
    u = {"username": utente, "ruolo": ruolo}
    cons = permessi.moduli_consentiti({"username": utente, "ruolo": ruolo}, {**cfg, "utenti": {utente: profilo}})
    return miagiornata.caselle(u, profilo, cons, payloads=_payloads_demo(), **kw), cons


def test_senza_dati_non_mostra_niente(dati):
    assert miagiornata.caselle({"username": "x"}, "direzione", set(permessi.TUTTI), payloads={}, ultimi={}, compiti=[], path=dati) == []


def test_ogni_profilo_vede_solo_i_suoi_strumenti():
    for profilo in permessi.PROFILI_BASE:
        cas, cons = _c(profilo)
        for c in cas:
            assert c["Modulo"] is None or c["Modulo"] in cons, (profilo, c)          # nessun collegamento a strumenti che la persona non puo' aprire
        assert len(cas) <= miagiornata.MAX_CASELLE


def test_profili_diversi_caselle_diverse():
    amm, _ = _c("amministrazione")
    com, _ = _c("commerciale")
    cant, _ = _c("cantiere")
    direz, _ = _c("presidente", ruolo="admin")
    aree = lambda cas: {c["Area"] for c in cas}
    assert {"Crediti", "Cassa"} & aree(amm) and "Cruscotto" not in aree(amm)               # il Cruscotto e' riservato
    assert "Cruscotto" in aree(direz)
    assert aree(amm) != aree(com) or aree(com) != aree(cant)
    assert "Debiti" not in aree(com)


def test_ordine_per_urgenza():
    cas, _ = _c("presidente", ruolo="admin")
    ordine = [miagiornata.ORDINE_STATO[c["Stato"]] for c in cas]
    assert ordine == sorted(ordine)


def test_compiti_e_dati_fermi():
    oggi = dt.date.today()
    compiti = [{"id": 1, "titolo": "Chiamare la banca", "scadenza": (oggi - dt.timedelta(days=2)).isoformat(), "assegnato": "x", "creato_da": "y"}]
    ultimi = {"rp": ("2020-01-01 10:00:00", "mario")}
    cas, _ = _c("cantiere", compiti=compiti, ultimi=ultimi)
    comp = [c for c in cas if c["Area"] == "Compiti"][0]
    assert comp["Stato"] == "bad" and "in ritardo" in comp["Nota"] and comp["Modulo"] == "ch"
    fermi = [c for c in cas if c["Area"] == "Dati da aggiornare"][0]
    assert fermi["Modulo"] == "rp" and "mario" in fermi["Nota"]


def test_saluto():
    assert miagiornata.saluto({"username": "lorenzo"}, dt.datetime(2026, 1, 1, 9)) == "Buongiorno, lorenzo"
    assert miagiornata.saluto({"username": "lorenzo"}, dt.datetime(2026, 1, 1, 20)).startswith("Buonasera")


def test_hub_mostra_la_mia_giornata_con_dati_veri(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setenv("FCR_DB_PATH", str(tmp_path / "h.db"))
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "h.db"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    storage.svuota_cache()
    for m, p in _payloads_demo().items():                                            # salvataggi veri (senza prefisso DEMO)
        storage.salva_pratica("Pratica prova", p, autore="t", modulo=m)
    storage.svuota_cache()
    at = AppTest.from_file("app.py", default_timeout=90).run()
    at.text_input(key="login_user").set_value("admin")
    at.text_input(key="login_pw").set_value("segreta")
    at.button[0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("La mia giornata" in e.label for e in at.expander)
    assert any(b.key and b.key.startswith("giorv_") for b in at.button)
    [b for b in at.button if b.key == "giorv_0"][0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["active_module"] in permessi.TUTTI
