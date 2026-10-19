import datetime as dt

import fatture

NS = 'xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"'


def xml(numero="FA-1", data="2026-09-01", ced=("Mia Srl", "01234567890"), ces=("Cliente Spa", "09876543210"), tipo="TD01",
        totale="1220.00", rate=(("2026-10-01", "1220.00"),), esig="I", imposta="220.00"):
    pag = "".join(f"<DettaglioPagamento><DataScadenzaPagamento>{d}</DataScadenzaPagamento><ImportoPagamento>{i}</ImportoPagamento></DettaglioPagamento>" for d, i in rate)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<p:FatturaElettronica {NS} versione="FPR12"><FatturaElettronicaHeader>
<CedentePrestatore><DatiAnagrafici><IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>{ced[1]}</IdCodice></IdFiscaleIVA><Anagrafica><Denominazione>{ced[0]}</Denominazione></Anagrafica></DatiAnagrafici></CedentePrestatore>
<CessionarioCommittente><DatiAnagrafici><IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>{ces[1]}</IdCodice></IdFiscaleIVA><Anagrafica><Denominazione>{ces[0]}</Denominazione></Anagrafica></DatiAnagrafici></CessionarioCommittente>
</FatturaElettronicaHeader><FatturaElettronicaBody>
<DatiGenerali><DatiGeneraliDocumento><TipoDocumento>{tipo}</TipoDocumento><Data>{data}</Data><Numero>{numero}</Numero><ImportoTotaleDocumento>{totale}</ImportoTotaleDocumento><Causale>Lavori</Causale></DatiGeneraliDocumento></DatiGenerali>
<DatiBeniServizi><DatiRiepilogo><ImponibileImporto>1000.00</ImponibileImporto><Imposta>{imposta}</Imposta><EsigibilitaIVA>{esig}</EsigibilitaIVA></DatiRiepilogo></DatiBeniServizi>
<DatiPagamento><CondizioniPagamento>TP02</CondizioniPagamento>{pag}</DatiPagamento></FatturaElettronicaBody></p:FatturaElettronica>""".encode()


def test_attiva_e_passiva():
    a, p = fatture.leggi_fattura(xml()), fatture.leggi_fattura(xml("F-9", ced=("Fornitore", "05555555555"), ces=("Mia Srl", "01234567890")))
    righe, av = fatture.righe_scadenzario([a, p], "IT01234567890")
    assert [r["Tipo"] for r in righe] == ["Attiva", "Passiva"] and not av
    assert righe[0]["Controparte"] == "Cliente Spa" and righe[1]["Controparte"] == "Fornitore"
    assert righe[0]["Importo"] == 1220.0 and righe[0]["Scadenza"] == "2026-10-01" and righe[0]["Documento"] == "FA-1"


def test_rate_multiple_e_split_payment():
    f = fatture.leggi_fattura(xml(rate=(("2026-10-01", "600.00"), ("2026-11-01", "620.00"))))
    righe, _ = fatture.righe_scadenzario([f], "01234567890")
    assert [r["Importo"] for r in righe] == [600.0, 620.0] and righe[0]["Documento"].endswith("(rata 1/2)")
    s = fatture.leggi_fattura(xml(rate=(), esig="S"))            # nessuna rata: totale - IVA split
    r, av = fatture.righe_scadenzario([s], "01234567890")
    assert r[0]["Importo"] == 1000.0 and r[0]["Scadenza"] == "2026-10-01" and any("30 giorni" in x for x in av)


def test_note_credito_e_partita_iva_sconosciuta():
    nc = fatture.leggi_fattura(xml(tipo="TD04"))
    r, av = fatture.righe_scadenzario([nc], "01234567890")
    assert not r and "nota di credito" in av[0]
    r, av = fatture.righe_scadenzario([fatture.leggi_fattura(xml())], "99999999999")
    assert not r and "non riconosco" in av[0]


def test_p7m_e_errori():
    firmato = b"\x30\x82\x01garbage" + xml() + b"\x00\x01firma"
    assert fatture.leggi_fattura(firmato)["cedente"] == "Mia Srl"
    for brutto in (b"ciao", b"<?xml version='1.0'?><altro/>"):
        try:
            fatture.leggi_fattura(brutto)
            assert False
        except ValueError:
            pass


def test_piva_probabile_e_duplicati():
    fs = [fatture.leggi_fattura(xml("1")), fatture.leggi_fattura(xml("2", ces=("Altro", "07777777777")))]
    assert fatture.piva_probabile(fs) == "01234567890"
    righe, _ = fatture.righe_scadenzario(fs, "01234567890")
    nuove, doppie = fatture.senza_duplicati(righe, [righe[0]])
    assert doppie == 1 and len(nuove) == 1
