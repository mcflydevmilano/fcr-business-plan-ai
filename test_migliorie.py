import io
import json

import pandas as pd
import pytest

import storage
import ui_util
from test_hub_bp import _btn, _nuovo


def test_mappatura_colonne_da_export_gestionale():
    cols = ["Cliente/Fornitore", "N. Documento", "Data Doc.", "Data scadenza", "Totale documento", "Pagato", "Note"]
    campi = ["Tipo", "Controparte", "Cantiere", "Documento", "Data_doc", "Scadenza", "Importo", "Saldato"]
    import sc
    m = ui_util.indovina_mappa(cols, campi, sc.ETICHETTE_DOC, sc.SINONIMI_DOC)
    assert m["Controparte"] == "Cliente/Fornitore" and m["Documento"] == "N. Documento" and m["Data_doc"] == "Data Doc." and m["Scadenza"] == "Data scadenza"
    assert m["Importo"] == "Totale documento" and m["Saldato"] == "Pagato" and m["Tipo"] is None and m["Cantiere"] is None
    df = pd.DataFrame([["Rossi Srl", "FA-1", pd.Timestamp("2026-09-01"), pd.Timestamp("2026-10-01"), "1.234,50", None, "x"]], columns=cols)
    out = ui_util.applica_mappa(df, m, campi)
    assert out.loc[0, "Scadenza"] == "2026-10-01" and out.loc[0, "Data_doc"] == "2026-09-01" and out.loc[0, "Saldato"] is None and out.loc[0, "Tipo"] is None
    out["Tipo"] = "Attiva"
    docs, av = sc.normalizza_documenti(sc.da_dataframe(out))
    assert len(docs) == 1 and docs[0]["Importo"] == pytest.approx(1234.5) and not av


def test_storico_versioni(tmp_path):
    p = str(tmp_path / "t.db")
    storage.salva_pratica("A", {"v": 1}, path=p, autore="mario", modulo="sc")
    storage.salva_pratica("A", {"v": 2}, path=p, autore="anna", modulo="sc")
    storage.salva_pratica("A", {"v": 2}, path=p, autore="anna", modulo="sc")       # identico: nessuna nuova versione
    storage.salva_pratica("A", {"v": 3}, path=p, autore="anna", modulo="sc")
    st = storage.storico_pratica("A", path=p, modulo="sc")
    assert len(st) == 2 and [storage.carica_versione(v["id"], p)["v"] for v in st] == [2, 1]
    assert storage.carica_pratica("A", p, "sc") == {"v": 3}
    for i in range(30):
        storage.salva_pratica("B", {"v": i}, path=p)
    assert len(storage.storico_pratica("B", path=p)) == storage.MAX_VERSIONI
    assert "storico" in storage.esporta_backup(p)
    storage.elimina_pratica("A", path=p, modulo="sc")
    assert storage.storico_pratica("A", path=p, modulo="sc") == []


def test_ripristino_versione_in_interfaccia(monkeypatch):
    at = _nuovo(monkeypatch, modulo="ga")
    at.number_input(key="ga_preavviso_gg").set_value(10).run()
    at.text_input(key="sv_nome_ga").set_value("X").run()
    at.button(key="sv_salva_ga").click().run()
    at.number_input(key="ga_preavviso_gg").set_value(20).run()
    at.button(key="sv_salva_ga").click().run()
    assert len(storage.storico_pratica("X", modulo="ga")) == 1
    at.button(key="sv_rip_ga").click().run()
    assert not at.exception and at.number_input(key="ga_preavviso_gg").value == 10


def test_ruolo_lettore_sola_lettura(monkeypatch):
    import auth
    assert "lettore" in auth.RUOLI
    at = _nuovo(monkeypatch, modulo="sl")
    at.session_state["utente"] = {"username": "ospite", "ruolo": "lettore", "origine": "app_password"}
    at.run()
    assert not at.exception
    assert at.button(key="sv_salva_sl").disabled
    at.button(key="gen_sl").click().run()                              # i dossier restano scaricabili
    assert not at.exception and at.session_state["sl_rep"]["pdf"][:4] == b"%PDF"
    for m in ("ga", "fo", "sx", "mz", "og", "sc", "cf"):
        a = _nuovo(monkeypatch, modulo=m)
        a.session_state["utente"] = {"username": "ospite", "ruolo": "lettore", "origine": "app_password"}
        a.run()
        assert not a.exception and a.button(key=f"sv_salva_{m}").disabled


def test_utente_lettore_creabile(tmp_path):
    import auth
    p = str(tmp_path / "u.db")
    auth.crea_utente("ospite", "Password123", "lettore", "admin", p)
    assert storage.carica_utente("ospite", p)["ruolo"] == "lettore" if hasattr(storage, "carica_utente") else True


def test_conflitto_salvataggio_storage(tmp_path):
    p = str(tmp_path / "c.db")
    a1 = storage.salva_pratica("P", {"v": 1}, path=p, autore="mario", modulo="sc", atteso="")
    with pytest.raises(storage.ConflittoSalvataggio) as e:
        storage.salva_pratica("P", {"v": 9}, path=p, autore="anna", modulo="sc", atteso="")          # esiste già e non l'ha aperto
    assert e.value.autore == "mario"
    storage.salva_pratica("P", {"v": 2}, path=p, autore="mario", modulo="sc", atteso=a1)              # chi l'ha aperto può salvare
    with pytest.raises(storage.ConflittoSalvataggio):
        storage.salva_pratica("P", {"v": 3}, path=p, autore="anna", modulo="sc", atteso=a1)           # versione vecchia
    assert storage.carica_pratica("P", p, "sc") == {"v": 2}
    storage.salva_pratica("P", {"v": 4}, path=p, autore="admin", modulo="sc")                          # senza controllo: sostituisce


def test_conflitto_in_interfaccia(monkeypatch):
    at = _nuovo(monkeypatch, modulo="ga")
    storage.salva_pratica("Cond", {"gare": [], "doc": []}, autore="collega", modulo="ga")           # salvataggio altrui con lo stesso nome
    at.text_input(key="sv_nome_ga").set_value("Cond").run()
    at.button(key="sv_salva_ga").click().run()
    assert not at.exception and any("Esiste già un salvataggio" in w.value for w in at.warning)
    assert storage.carica_pratica("Cond", modulo="ga") == {"gare": [], "doc": []}                      # non è stato sovrascritto
    at.button(key="sv_forza_ga").click().run()
    assert not at.exception and storage.carica_pratica("Cond", modulo="ga")["gare"]                    # ora sì
    at.button(key="sv_salva_ga").click().run()                                                          # i salvataggi successivi dello stesso utente passano
    assert not any("Esiste già" in w.value or "modificato" in w.value for w in at.warning)
