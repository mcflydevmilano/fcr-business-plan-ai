import guida


def test_tutti_i_moduli_hanno_passi():
    for s in ("credit", "bp", "cf", "pv", "sc", "sl", "ga", "fo", "sx", "mz", "og", "rp", "gt", "ca", "dd"):
        serve, passi, _ = guida.PASSI[s]
        assert serve and len(passi) >= 4
        for t, x, c in passi:
            assert t and x
            assert c is None or c.split(":")[0] in ("demo", "dati", "salvato", "dossier")


def test_dettagli_cruscotto_e_messaggio():
    import datetime as dt
    import dd
    import sc
    oggi = dt.date(2026, 10, 21)
    righe = [
        {"Tipo": "Attiva", "Controparte": "Cliente A", "Cantiere": "Villa Lago", "Documento": "1", "Data_doc": "2026-07-01", "Scadenza": "2026-08-01", "Importo": 10000, "Saldato": 0},
        {"Tipo": "Passiva", "Controparte": "Fornitore B", "Cantiere": "Villa Lago", "Documento": "9", "Data_doc": "2026-09-01", "Scadenza": "2026-10-01", "Importo": 5000, "Saldato": 1000},
    ]
    m = {"sc": dd.metriche_sc({"docs": righe}, oggi=oggi)}
    bl = dd.dettagli(m)
    ids = {b["id"]: b for b in bl}
    assert ids["sc_clienti"]["righe"][0]["Cliente"] == "Cliente A"
    assert ids["sc_fornitori"]["righe"][0]["Scaduto (€)"] == 4000
    ogg, testo = dd.messaggio_team(bl, "Amministrazione", da="mario", oggi=oggi)
    assert "Cliente A" in testo and "Fornitore B" in testo and "mario" in testo
    assert dd.messaggio_team(bl, "Acquisti", oggi=oggi)[1].count("Cliente A") == 0


def test_messaggio_assistenza():
    import datetime as dt
    import assistenza
    t = assistenza.costruisci_messaggio("⚠️ Segnalo un problema", "Non salva", utente="mario", strumento="rp", quando=dt.datetime(2026, 10, 21, 9, 5))
    assert "Non salva" in t and "mario" in t and "rp" in t and "21/10/2026 09:05" in t


def test_registro_descrive_le_modifiche(tmp_path):
    import registro
    import storage
    v = {"fasi": [{"Commessa": "A", "Fase": "x", "Avanzamento": 10}, {"Commessa": "A", "Fase": "y", "Avanzamento": 0}], "params": {"soglia_pct": 15}}
    n = {"fasi": [{"Commessa": "A", "Fase": "x", "Avanzamento": 40}, {"Commessa": "B", "Fase": "z", "Avanzamento": 0}, {"Commessa": "B", "Fase": "w", "Avanzamento": 0}], "params": {"soglia_pct": 20}}
    t = registro.descrivi_modifiche(v, n)
    assert "Fasi" in t and "+2 righe" in t and "modificata" in t and "Avanzamento 10→40" in t and "soglia_pct 15→20" in t
    assert "senza modifiche" in registro.descrivi_modifiche(v, v)
    db = str(tmp_path / "t.db")
    storage.salva_pratica("Ottobre", v, path=db, autore="mario", modulo="gt")
    storage.salva_pratica("Ottobre", n, path=db, autore="luisa", modulo="gt")
    ev = storage.elenca_eventi(path=db, azione="modifiche_dati")
    assert [e["Utente"] for e in ev] == ["luisa", "mario"]
    assert "Cronoprogramma" in ev[0]["Dettaglio"] and "Ottobre" in ev[0]["Dettaglio"] and "Fasi" in ev[0]["Dettaglio"]
    assert len(storage.elenca_eventi(path=db, cerca="LUISA")) == 1
    assert storage.elenca_eventi(path=db, da="2999-01-01") == []
