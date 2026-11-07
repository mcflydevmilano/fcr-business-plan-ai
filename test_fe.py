import io
import zipfile

import fe

XML = """<?xml version="1.0" encoding="UTF-8"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2" versione="FPR12">
<FatturaElettronicaHeader>
 <CedentePrestatore><DatiAnagrafici><IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>01234567890</IdCodice></IdFiscaleIVA><Anagrafica><Denominazione>Edil Rossi Srl</Denominazione></Anagrafica></DatiAnagrafici></CedentePrestatore>
 <CessionarioCommittente><DatiAnagrafici><IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>09876543210</IdCodice></IdFiscaleIVA><Anagrafica><Denominazione>FCR General Contractor</Denominazione></Anagrafica></DatiAnagrafici></CessionarioCommittente>
</FatturaElettronicaHeader>
<FatturaElettronicaBody>
 <DatiGenerali><DatiGeneraliDocumento><TipoDocumento>TD01</TipoDocumento><Divisa>EUR</Divisa><Data>2026-10-15</Data><Numero>45/A</Numero><ImportoTotaleDocumento>1220.00</ImportoTotaleDocumento><Causale>Lavori cantiere 014-MI-VILLALAGO</Causale></DatiGeneraliDocumento></DatiGenerali>
 <DatiBeniServizi><DettaglioLinee><NumeroLinea>1</NumeroLinea><Descrizione>Posa cappotto</Descrizione></DettaglioLinee><DatiRiepilogo><AliquotaIVA>22.00</AliquotaIVA><ImponibileImporto>1000.00</ImponibileImporto><Imposta>220.00</Imposta></DatiRiepilogo></DatiBeniServizi>
 <DatiPagamento><CondizioniPagamento>TP01</CondizioniPagamento><DettaglioPagamento><ModalitaPagamento>MP05</ModalitaPagamento><DataScadenzaPagamento>2026-11-30</DataScadenzaPagamento><ImportoPagamento>610.00</ImportoPagamento></DettaglioPagamento><DettaglioPagamento><ModalitaPagamento>MP05</ModalitaPagamento><DataScadenzaPagamento>2026-12-30</DataScadenzaPagamento><ImportoPagamento>610.00</ImportoPagamento></DettaglioPagamento></DatiPagamento>
</FatturaElettronicaBody>
</p:FatturaElettronica>"""


def test_legge_fattura_con_namespace():
    f = fe.leggi_xml(XML)[0]
    assert f["fornitore"] == "Edil Rossi Srl" and f["piva_fornitore"] == "01234567890" and f["cliente"] == "FCR General Contractor"
    assert f["numero"] == "45/A" and f["data"] == "2026-10-15" and f["totale"] == 1220.0 and f["imponibile"] == 1000.0 and f["iva"] == 220.0
    assert [s["data"] for s in f["scadenze"]] == ["2026-11-30", "2026-12-30"] and "Posa cappotto" in f["descrizioni"]


def test_p7m_e_zip():
    firmato = b"\x30\x82binario" + XML.encode() + b"\x00firma"
    assert fe.leggi_xml(firmato)[0]["numero"] == "45/A"
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("a.xml", XML)
        z.writestr("b.xml", "<ciao/>")
    fatt, err = fe.leggi_file("lotto.zip", b.getvalue())
    assert len(fatt) == 1 and len(err) == 1 and "b.xml" in err[0]


def test_file_non_valido():
    fatt, err = fe.leggi_file("x.xml", b"non xml")
    assert fatt == [] and err


def test_scadenzario_una_riga_per_rata_e_cantiere_suggerito():
    f = fe.leggi_xml(XML)
    cod = fe.suggerisci_cantiere(f[0], [{"Codice": "999-XX-ALTRO"}, {"Codice": "014-MI-VILLALAGO"}])
    assert cod == "014-MI-VILLALAGO"
    righe, avv = fe.a_scadenzario(f, "Passiva", {0: cod})
    assert len(righe) == 2 and righe[0]["Controparte"] == "Edil Rossi Srl" and righe[0]["Importo"] == 610.0 and righe[0]["Cantiere"] == cod
    import sc
    docs, avvisi = sc.normalizza_documenti(righe)
    assert len(docs) == 2 and not avvisi                                  # lo Scadenzario le accetta cosi' come sono
    att, _ = fe.a_scadenzario(f, "Attiva")
    assert att[0]["Controparte"] == "FCR General Contractor"


def test_scadenza_stimata_nota_di_credito_e_duplicati():
    f = fe.leggi_xml(XML.replace("TD01", "TD04"))
    assert f[0]["totale"] == -1220.0
    righe, avv = fe.a_scadenzario(f)
    assert righe == [] and "nota di credito" in avv[0]
    senza = XML.replace("<DatiPagamento>", "<X>").replace("</DatiPagamento>", "</X>")
    righe, avv = fe.a_scadenzario(fe.leggi_xml(senza))
    assert righe[0]["Scadenza"] == "2026-11-14" and "stimata" in avv[0]
    nuove, _ = fe.a_scadenzario(fe.leggi_xml(XML))
    assert len(fe.duplicati(fe.leggi_xml(XML), [{"Documento": "Fattura n. 45/A", "Controparte": "Edil Rossi Srl"}])) == 1
