"""Struttura cartelle del NAS e collegamento con i cantieri."""
import os

import archivio


def test_nome_e_percorsi_cantiere(tmp_path):
    c = {"Codice": "CAN-2026-001", "Esterno": "F100", "Cantiere": 'Villa: "Lago"?'}
    assert archivio.nome_cantiere(c) == "F100 - Villa Lago"
    assert archivio.nome_cantiere({"Codice": "CAN-2026-002", "Cantiere": "Scuola"}) == "CAN-2026-002 - Scuola"
    ps = archivio.percorsi(c, radice=None)
    aree = [p["area"] for p in ps]
    assert aree == ["02 Tecnico Commerciale", "03 Progetti", "04 CME", "05 Contratti", "06 Contabilita Cantieri", "09 Sicurezza e Certificazioni", "10 Foto e Drone"]
    assert ps[1]["unc"].endswith("\\03 Progetti\\F100 - Villa Lago") and ps[1]["esiste"] is None
    # NAS «montato»: una cartella esiste gia' con altro nome ma stesso codice
    os.makedirs(tmp_path / "03 Progetti" / "F100 - Villa sul lago")
    r = {p["area"]: p["esiste"] for p in archivio.percorsi(c, radice=str(tmp_path))}
    assert r["03 Progetti"] is True and r["04 CME"] is False
    n, v = archivio.crea_cartelle(c, radice=str(tmp_path))
    assert (n, v) == (6, 1) and (tmp_path / "04 CME" / "F100 - Villa Lago").is_dir()
    assert archivio.crea_cartelle(c, radice=str(tmp_path)) == (0, 7)


def test_nome_pericoloso_non_esce_dalla_radice(tmp_path):
    c = {"Codice": "X", "Cantiere": "../../etc"}
    assert "/" not in archivio.nome_cantiere(c) and archivio.nome_cantiere({"Codice": "..", "Cantiere": ".."}) == ""
    archivio.crea_cartelle(c, radice=str(tmp_path))
    assert all(str(p).startswith(str(tmp_path)) for p in tmp_path.rglob("*"))
    assert not os.path.exists(tmp_path.parent / "etc")


def test_senza_nas_collegato():
    try:
        archivio.crea_cartelle({"Codice": "A", "Cantiere": "B"}, radice="/percorso/che/non/esiste")
        assert False
    except OSError:
        pass


def test_link_apri_e_file_di_attivazione():
    assert archivio.link_apri("03 Progetti/F100 - Villa Lago") == "fcrnas:03%20Progetti/F100%20-%20Villa%20Lago"
    assert "%27" in archivio.link_apri("D'Amico") and '"' not in archivio.link_apri('a"b') and "&" not in archivio.link_apri("a&b")
    ps = archivio.percorsi({"Esterno": "F100", "Cantiere": "Villa Lago"}, radice=None)
    assert ps[1]["link"] == "fcrnas:03%20Progetti/F100%20-%20Villa%20Lago"
    reg = archivio.file_attivazione()
    assert reg.startswith("Windows Registry Editor Version 5.00") and "[HKEY_CURRENT_USER\\Software\\Classes\\fcrnas\\shell\\open\\command]" in reg
    assert "192.168.1.240" in reg and "explorer.exe" in reg and "URL Protocol" in reg
