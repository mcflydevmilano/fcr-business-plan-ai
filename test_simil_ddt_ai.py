"""Somiglianza tra testi, lettura bolla con IA (pulizia e abbinamento agli ordini aperti)."""
import ddt
import mt
import simil


def test_somiglianza_voci_scritte_diversamente():
    assert simil.similarita("Intonaco civile 2 mani", "Intonacatura civile a due strati") >= 0.8
    assert simil.similarita("Tubi multistrato", "Tubo multistrato 16mm") >= 0.6
    assert simil.similarita("Muratura in laterizio 30 cm", "Muratura in laterizio 20 cm") < 0.6     # misure diverse = voci diverse
    assert simil.similarita("Cemento", "Sabbia") == 0
    assert simil.similarita("", "x") == 0


def test_raggruppa():
    v = ["Intonaco civile 2 mani", "Pittura lavabile pareti", "Intonacatura civile a due strati", "Tinteggiatura lavabile pareti interne", "Demolizione tramezzi"]
    g = simil.raggruppa(v)
    assert [0, 2] in g and [4] in g and any(set(x) >= {1} for x in g)


def test_bolla_ia_pulizia_e_abbinamento():
    b = ddt.normalizza_ai({"numero": " DDT 412/A ", "data": "28/10/2026", "fornitore": "Beton Nord Srl",
                           "righe": [{"descrizione": "Calcestruzzo C25/30", "quantita": "60", "um": "mc"}, {"descrizione": "Mattoni forati", "quantita": 100}, {"descrizione": "", "quantita": 5}, "x"]})
    assert b["data"] == "2026-10-28" and b["numero"] and len(b["righe"]) == 2
    assert ddt.normalizza_ai("spazzatura")["righe"] == [] and ddt.normalizza_ai({"data": "2026-13-45"})["data"] == ""
    ordini, _ = mt.normalizza_ordini([
        {"Materiale": "Calcestruzzo C25/30", "Fornitore": "Beton Nord", "Commessa": "Villa Lago", "Quantita": 60, "Um": "mc", "Prezzo_unit": 120},
        {"Materiale": "Calcestruzzo C25/30", "Fornitore": "Altro srl", "Commessa": "Scuola", "Quantita": 60, "Um": "mc", "Prezzo_unit": 125},
        {"Materiale": "Laterizi", "Fornitore": "Fornaci Est", "Commessa": "Scuola", "Quantita": 8000, "Um": "pz", "Prezzo_unit": 0.6, "Consegnato": "sì"}])
    abb = ddt.abbina_ordini(b["righe"], ordini, b["fornitore"])
    assert abb[0]["indice"] == 0                                 # a parita' di materiale vince il fornitore giusto
    assert abb[1]["indice"] is None
    nuovi, n = ddt.conferma_consegne(ordini, [0], "412/A", "2026-10-28")
    assert n == 1 and nuovi[0]["Consegnato"] == "sì" and nuovi[0]["Ddt"] == "412/A" and nuovi[0]["Data_consegna"] == "2026-10-28" and ordini[0]["Consegnato"] == "no"
    assert ddt.conferma_consegne(nuovi, [0], "x", "2026-11-01")[1] == 0       # gia' consegnato: non si tocca


def test_unisci_voci_preventivi():
    import fo
    off, _ = fo.normalizza_offerte([
        {"Voce": "Intonaco civile 2 mani", "Fornitore": "Alfa", "Importo": 5000},
        {"Voce": "Intonacatura civile a due strati", "Fornitore": "Beta", "Importo": 4800},
        {"Voce": "Intonaco civile 2 mani", "Fornitore": "Gamma", "Importo": 5200},
        {"Voce": "Impianto elettrico", "Fornitore": "Alfa", "Importo": 9000}])
    g = fo.gruppi_simili(off)
    assert len(g) == 1 and g[0]["canonica"] == "Intonaco civile 2 mani" and g[0]["fornitori"] == ["Alfa", "Beta", "Gamma"]
    nuove, n = fo.applica_gruppi(off, g)
    assert n == 1 and {o["Voce"] for o in nuove} == {"Intonaco civile 2 mani", "Impianto elettrico"}
    conf = fo.calcola_fo([], [], nuove)["confronto"]
    assert [c["Offerte"] for c in conf if c["Voce"] == "Intonaco civile 2 mani"] == [3]
    # risposta IA: numeri da 1, risposte sbagliate ignorate
    assert fo.gruppi_da_risposta_ia(off, '{"gruppi": [[1, 2]]}')[0]["canonica"] == "Intonaco civile 2 mani"
    assert fo.gruppi_da_risposta_ia(off, "boh") == [] and fo.gruppi_da_risposta_ia(off, '{"gruppi": [[1, 99], [3]]}') == []
