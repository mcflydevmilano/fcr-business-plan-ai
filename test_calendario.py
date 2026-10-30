import datetime as dt

import pytest

import calendario
import riepilogo
from test_hub_bp import _btn, _nuovo

OGGI = dt.date(2026, 10, 19)
g = lambda n: (OGGI + dt.timedelta(days=n)).isoformat()


def _pay():
    return {"sc": {"docs": [{"Tipo": "Attiva", "Controparte": "Rossi", "Documento": "FA-1", "Scadenza": g(-3), "Importo": 1000, "Saldato": 0},
                            {"Tipo": "Passiva", "Controparte": "Alfa", "Documento": "F-2", "Scadenza": g(5), "Importo": 500, "Saldato": 500},
                            {"Tipo": "Passiva", "Controparte": "Beta", "Documento": "F-3", "Scadenza": g(10), "Importo": 700, "Saldato": 100}]},
            "ga": {"gare": [{"Gara": "Scuola", "Importo_base": 100000, "Scadenza": g(4), "Stato": "In preparazione"}, {"Gara": "Vinta", "Importo_base": 5000, "Scadenza": g(2), "Stato": "Vinta"}],
                   "doc": [{"Gara": "Scuola", "Documento": "DGUE", "Scadenza": g(3), "Fatto": False}, {"Gara": "Scuola", "Documento": "Offerta", "Scadenza": g(3), "Fatto": True}]},
            "fo": {"docs": [{"Fornitore": "Alfa", "Documento": "DURC", "Scadenza": g(20)}]},
            "sx": {"pers": [{"Persona": "Rossi", "Cantiere": "Villa", "Documento": "Visita", "Scadenza": g(40)}], "docc": [{"Cantiere": "Villa", "Documento": "DURC", "Presente": True, "Scadenza": g(15)}]},
            "mz": {"mezzi": [{"Mezzo": "Gru", "Ore_annue_prev": 500}], "scad": [{"Mezzo": "Gru", "Documento": "Revisione", "Scadenza": g(-1)}]}}


def test_eventi_ordine_stati_e_filtri():
    ev = calendario.eventi(_pay(), OGGI, 30)
    titoli = [e["Titolo"] for e in ev]
    assert not any("F-2" in t for t in titoli)                       # fattura già saldata: non compare
    assert not any("Vinta" in t for t in titoli) and not any("Offerta" in t for t in titoli)
    assert [e["Giorni"] for e in ev] == sorted(e["Giorni"] for e in ev)
    inc = next(e for e in ev if e["Categoria"] == "Incasso")
    assert inc["Stato"] == "bad" and inc["Importo"] == 1000
    assert next(e for e in ev if e["Categoria"] == "Pagamento")["Importo"] == 600
    assert all(e["Giorni"] <= 30 for e in ev) and not any("Visita" in e["Titolo"] for e in ev)      # visita a 40 giorni: oltre l'orizzonte
    assert len(calendario.eventi(_pay(), OGGI, 30, ["Gara"])) == 1
    r = calendario.riassunto(ev)
    assert r["scadute"] == 2 and r["totale"] == len(ev)


def test_ics_valido():
    ev = calendario.eventi(_pay(), OGGI, 30)
    ics = calendario.genera_ics(ev)
    assert ics.startswith("BEGIN:VCALENDAR") and ics.strip().endswith("END:VCALENDAR")
    assert ics.count("BEGIN:VEVENT") == sum(1 for e in ev if e["Giorni"] >= 0)       # le scadute non entrano nel calendario
    assert "DTSTART;VALUE=DATE:20261023" in ics and "\r\n" in ics


def test_riepilogo_testo_e_invio(monkeypatch):
    ogg, testo, h, crit = riepilogo.costruisci(_pay(), OGGI)
    assert "Riepilogo del 19/10/2026" in ogg and crit >= 2 and "SCADUTE (2)" in testo and "<h2" in h
    with pytest.raises(RuntimeError):
        riepilogo.invia(ogg, testo, h, {})
    inviati = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=0):
            inviati.append((host, port))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self, **k):
            pass

        def login(self, u, p):
            assert p == "pw"

        def send_message(self, m):
            inviati.append((m["To"], m["Subject"]))
    monkeypatch.setattr(riepilogo.smtplib, "SMTP", FakeSMTP)
    dest = riepilogo.invia(ogg, testo, h, {"SMTP_HOST": "smtp.x", "SMTP_USER": "a@x.it", "SMTP_PASSWORD": "pw", "MAIL_TO": "b@x.it, c@x.it"})
    assert dest == ["b@x.it", "c@x.it"] and inviati[0] == ("smtp.x", 587) and inviati[1][0] == "b@x.it, c@x.it"


def test_main_dry_run_dal_database(monkeypatch, tmp_path, capsys):
    import storage
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "r.db"))
    assert riepilogo.main(["--dry-run"]) == 0 and "Nessun salvataggio" in capsys.readouterr().out
    storage.salva_pratica("Oggi", _pay()["sc"], modulo="sc")
    assert riepilogo.main(["--dry-run"]) == 0 and "RIEPILOGO FCR" in capsys.readouterr().out


def test_pagina_calendario(monkeypatch):
    at = _nuovo(monkeypatch)
    assert "Calendario scadenze" in " ".join(m.value for m in at.markdown)
    _btn(at, "Apri Scadenzario").click().run()
    _btn(at, "Torna all'Hub").click().run()
    _btn(at, "Apri Calendario scadenze").click().run()
    assert not at.exception and len(at.tabs) == 3
    assert any("Scadute" in m.value for m in at.markdown)


def test_riepilogo_slack(monkeypatch):
    import json

    import riepilogo
    testo = "RIEPILOGO FCR - 20/10/2026\n\nCOSA FARE\n- [critico] Incassi in ritardo\n\nSCADUTE (1)\n- 19/10 [Incasso] Rossi\n\nSEMAFORI\n- Cassa: 5 [CRITICO]"
    m = riepilogo.per_slack("FCR - Riepilogo", testo)
    t = m["blocks"][1]["text"]["text"]
    assert m["blocks"][0]["type"] == "header" and "*COSA FARE*" in t and "*SCADUTE (1)*" in t and ":red_circle:" in t
    inviati = []

    class R:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(riepilogo.urllib.request, "urlopen", lambda req, timeout=0: (inviati.append(json.loads(req.data)), R())[1])
    assert riepilogo.invia_slack("x", testo, {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/T/B/X"}) and inviati[0]["text"] == "x"
    import pytest
    with pytest.raises(RuntimeError):
        riepilogo.invia_slack("x", testo, {"SLACK_WEBHOOK_URL": "http://altro.it"})
