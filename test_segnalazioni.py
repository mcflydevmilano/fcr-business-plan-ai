import assistenza
import storage
import ui_util


def test_segnalazione_salvata_e_letta(tmp_path):
    p = str(tmp_path / "t.db")
    assistenza.registra_segnalazione("⚠️ Segnalo un problema", "Non salva\ni cantieri ‖ boh", "marco", "Rubrica e cantieri", "3.15.2", "telefono", path=p)
    r = assistenza.elenco_segnalazioni(path=p)
    assert len(r) == 1
    assert r[0]["Da"] == "marco" and r[0]["Strumento"] == "Rubrica e cantieri" and r[0]["Dispositivo"] == "telefono"
    assert r[0]["Versione"] == "v3.15.2" and "Non salva" in r[0]["Messaggio"]


def test_ora_italiana_nel_conflitto():
    assert ui_util._ora_it("2026-11-04 14:32:10") == "04/11 alle 15:32"
    assert "UTC" in ui_util._ora_it("boh")


def test_conflitto_vero(tmp_path):
    p = str(tmp_path / "t.db")
    t1 = storage.salva_pratica("x", {"a": 1}, p, autore="a", modulo="sa")
    storage.salva_pratica("x", {"a": 2}, p, autore="b", modulo="sa", atteso=t1)
    try:
        storage.salva_pratica("x", {"a": 3}, p, autore="a", modulo="sa", atteso=t1)
        assert False
    except storage.ConflittoSalvataggio as c:
        assert c.autore == "b"
