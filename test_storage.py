import pytest

import storage


def test_salva_carica_elimina(tmp_path):
    db = str(tmp_path / "t.db")
    storage.salva_pratica("Alfa", {"x": 1, "testo": "perche'"}, path=db)
    storage.salva_pratica("Alfa", {"x": 2}, path=db)             # aggiorna, non duplica
    storage.salva_pratica("Beta", {"y": 1}, path=db)
    assert [p["nome"] for p in storage.elenca_pratiche(path=db)].count("Alfa") == 1
    assert storage.carica_pratica("Alfa", path=db) == {"x": 2}
    assert storage.carica_pratica("Zeta", path=db) is None
    storage.elimina_pratica("Alfa", path=db)
    assert storage.carica_pratica("Alfa", path=db) is None


def test_nome_vuoto_rifiutato(tmp_path):
    with pytest.raises(ValueError):
        storage.salva_pratica("  ", {}, path=str(tmp_path / "t.db"))


def test_registro_report(tmp_path):
    db = str(tmp_path / "t.db")
    storage.log_report("Alfa", "ABC123", "modello-x", "hash1", {"punti": 5}, path=db)
    storage.log_report("Beta", "DEF456", "modello-x", "hash2", path=db)
    assert [r["report_id"] for r in storage.elenco_report("Alfa", path=db)] == ["ABC123"]
    assert len(storage.elenco_report(path=db)) == 2
