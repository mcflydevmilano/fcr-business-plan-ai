"""Collegamenti tra strumenti (3.19.0): compiti unificati, preventivo -> offerta, ordini approvati -> materiali."""
import pytest

import chat
import mt
import of
import storage
import ta


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "c.db"))
    storage.svuota_cache()


def test_compiti_della_bacheca_assegnati_a_me():
    storage.salva_pratica("Bacheca", {"compiti": [
        {"Compito": "Chiamare il fornitore", "Responsabile": "Marco Colombo", "Scadenza": "2026-11-20"},
        {"Compito": "Gia' fatto", "Responsabile": "Marco Colombo", "Stato": "Fatto"},
        {"Compito": "Di un altro", "Responsabile": "Anna Verdi"},
        {"Compito": "Senza data", "Responsabile": "marco colombo, Anna Verdi"}]}, modulo="ta")
    m = ta.miei("marco colombo")
    assert [t["titolo"] for t in m] == ["Chiamare il fornitore", "Senza data"]
    assert m[0]["scadenza"] == "2026-11-20"
    assert ta.miei("luca neri") == [] and ta.miei("") == []


def test_preventivo_diventa_voci_d_offerta():
    voci = [{"Codice": "1", "Categoria": "Opere murarie", "Descrizione": "Muro", "UM": "mq", "Quantita": 10, "Materiali": 20, "Manodopera": 30, "Noli_altro": 0}]
    r = of.voci_da_preventivo({"voci": voci, "params": {"sg_pct": 15, "utile_pct": 10, "sicurezza_pct": 2, "sconto_pct": 0}})
    assert r[0]["Descrizione"] == "Muro" and r[0]["Quantita"] == 10
    assert abs(r[0]["Prezzo"] - 50 * 1.15 * 1.1) < 0.01                    # prezzo di vendita, non costo
    assert r[-1]["Cap"] == "Sicurezza" and r[-1]["Prezzo"] > 0
    assert of.voci_da_preventivo({}) == []


def test_ordini_approvati_in_materiali_senza_doppioni():
    oa_ = [{"Stato": "Approvato", "Descrizione": "Cemento", "Fornitore": "Edil", "Cantiere": "C1", "Importo": 500.0, "Quantita": 10.0, "Voce": ""},
           {"Stato": "Da approvare", "Descrizione": "Ferro", "Fornitore": "Edil", "Cantiere": "C1", "Importo": 900.0, "Quantita": 0.0, "Voce": ""}]
    nuove, gia = mt.righe_da_ordini_approvati(oa_)
    assert len(nuove) == 1 and gia == 0 and nuove[0]["Prezzo_unit"] == 50.0 and nuove[0]["Consegnato"] == "no"
    nuove2, gia2 = mt.righe_da_ordini_approvati(oa_, nuove)
    assert nuove2 == [] and gia2 == 1
