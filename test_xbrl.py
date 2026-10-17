import io
import zipfile

import pytest

import core
import xbrl


def esempio():
    ctx = lambda i, inst=None, a=None, b=None, dim=False: (
        f'<xbrli:context id="{i}"><xbrli:entity><xbrli:identifier scheme="http://www.rgs.it">X</xbrli:identifier>'
        + ('<xbrli:segment><xbrldi:explicitMember dimension="d:x">m:y</xbrldi:explicitMember></xbrli:segment>' if dim else '') + '</xbrli:entity>'
        + (f'<xbrli:period><xbrli:instant>{inst}</xbrli:instant></xbrli:period>' if inst else
           f'<xbrli:period><xbrli:startDate>{a}</xbrli:startDate><xbrli:endDate>{b}</xbrli:endDate></xbrli:period>')
        + '</xbrli:context>')
    f = lambda n, c, v: f'<itcc-ci:{n} contextRef="{c}" unitRef="eur" decimals="0">{v}</itcc-ci:{n}>'
    x = ('<?xml version="1.0" encoding="UTF-8"?><xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" '
         'xmlns:itcc-ci="http://www.xbrl.org/it/fr/gaap/ci/2018-11-04" xmlns:xbrldi="http://xbrl.org/2006/xbrldi">'
         + ctx("i25", inst="2025-12-31") + ctx("i24", inst="2024-12-31") + ctx("d25", a="2025-01-01", b="2025-12-31")
         + ctx("d24", a="2024-01-01", b="2024-12-31") + ctx("dim25", inst="2025-12-31", dim=True)
         + f("RicaviVenditePrestazioni", "d25", 2500000) + f("RicaviVenditePrestazioni", "d24", 2400000)
         + f("DifferenzaTraValoreECostiProduzione", "d25", 200000) + f("DifferenzaTraValoreECostiProduzione", "d24", 180000)
         + f("TotaleAmmortamentiESvalutazioni", "d25", 100000) + f("TotaleAmmortamentiESvalutazioni", "d24", 100000)
         + f("UtilePerditaEsercizio", "d25", 120000) + f("UtilePerditaEsercizio", "d24", 90000)
         + f("TotaleAttivo", "i25", 3000000) + f("TotaleAttivo", "i24", 2800000)
         + f("TotalePatrimonioNetto", "i25", 800000) + f("TotalePatrimonioNetto", "i24", 700000)
         + f("DebitiVersoBanche", "i25", 900000) + f("DebitiVersoBanche", "i24", 950000)
         + f("TotaleDisponibilitaLiquide", "i25", 300000) + f("TotaleDisponibilitaLiquide", "i24", 250000)
         + f("TotaleAttivo", "dim25", 111)
         + '</xbrli:xbrl>')
    return x.encode()


def test_legge_valori_e_calcola_ebitda_pfn():
    raw, avvisi = xbrl.leggi(esempio())
    d, storico, fonti = core.normalizza_estrazione(raw)
    assert d["anno_riferimento"] == 2025
    assert d["ricavi"] == 2_500_000 and d["totale_attivo"] == 3_000_000      # il fatto con dimensioni (111) e' ignorato
    assert d["ebitda"] == 300_000                                              # A-B 200.000 + ammortamenti 100.000
    assert d["debiti_finanziari_totali"] == 900_000 and d["pfn"] == 600_000    # 900.000 - 300.000 di liquidita'
    assert fonti["ebitda"].startswith("CALCOLATO") and fonti["ricavi"].startswith("XBRL")
    assert len(storico) == 1 and storico[0]["anno"] == 2024 and storico[0]["ricavi"] == 2_400_000
    assert core.valida_dati(d) == []
    assert any("EBITDA e PFN" in a for a in avvisi)


def test_legge_dentro_uno_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("bilancio.pdf", b"%PDF-finto")
        z.writestr("bilancio.xbrl", esempio())
    raw, _ = xbrl.leggi(buf.getvalue())
    assert raw["ricavi"] == 2_500_000


def test_voci_mancanti_segnalate():
    xml = esempio().replace(b"TotalePatrimonioNetto", b"AltraVoce")
    raw, avvisi = xbrl.leggi(xml)
    assert "patrimonio_netto" not in raw
    assert any("patrimonio netto" in a for a in avvisi)
    _, _, fonti = core.normalizza_estrazione(raw)
    assert "NON TROVATO" in fonti["patrimonio_netto"]


def test_rifiuta_doctype_e_file_non_xbrl():
    with pytest.raises(xbrl.XbrlError):
        xbrl.leggi(b'<?xml version="1.0"?><!DOCTYPE a [<!ENTITY x "y">]><a>&x;</a>')
    with pytest.raises(xbrl.XbrlError):
        xbrl.leggi(b"<a><b>testo</b></a>")
    with pytest.raises(xbrl.XbrlError):
        xbrl.leggi(b"non e' xml")
    with pytest.raises(xbrl.XbrlError):
        xbrl.leggi(b"PK\x03\x04rotto")
