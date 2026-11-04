import percorso


def test_nessun_dato_primo_passo_adesso():
    passi, fatti, tot = percorso.valuta({}, None)
    assert fatti == 0 and tot >= 7
    assert passi[0]["stato"] == "adesso"
    assert all(p["stato"] != "adesso" for p in passi[1:])
    assert [p["n"] for p in passi] == list(range(1, len(passi) + 1))


def test_consentiti_filtra():
    passi, _, _ = percorso.valuta({}, ["sc"])
    assert [p["id"] for p in passi] == ["fatture"]
    assert passi[0]["stato"] == "adesso"


def test_cantieri_fatto(monkeypatch):
    monkeypatch.setattr(percorso.storage, "carica_pratica", lambda nome, modulo=None: {"cantieri": [{"Nome": "A"}]})
    passi, fatti, _ = percorso.valuta({"ru": (None, None, "x")}, None)
    assert passi[0]["stato"] == "fatto" and fatti == 1
    assert passi[1]["stato"] == "adesso"
