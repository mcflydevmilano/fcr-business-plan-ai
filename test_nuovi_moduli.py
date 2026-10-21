"""Permessi per profilo, Rubrica, Studio legale, Riconciliazione bancaria, Ordini e approvazioni, foto/firma e installazione."""
import datetime as dt
import io
import os
import tempfile

import pytest
from streamlit.testing.v1 import AppTest

import bk
import firma
import lg
import oa
import permessi
import ru
import sc
import storage

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
OGGI = dt.date(2026, 10, 21)


@pytest.fixture(autouse=True)
def db(monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
    monkeypatch.setenv("APP_PASSWORD", "segreta")


def _app(utente, modulo=None):
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["utente"] = utente
    if modulo:
        at.session_state["active_module"] = modulo
    return at.run()


def _u(nome, ruolo="utente"):
    return {"username": nome, "ruolo": ruolo, "origine": "app_password"}


def _bottoni(at):
    return [b.label for b in at.button]


# ------------------------------------------------------------------ PERMESSI
def test_permessi_cruscotto_solo_presidente_e_admin():
    cfg = permessi.configurazione_base()
    assert "dd" not in permessi.moduli_consentiti(_u("mario"), cfg)            # profilo predefinito: direzione
    cfg["utenti"]["lorenzo"] = "presidente"
    assert "dd" in permessi.moduli_consentiti(_u("lorenzo"), cfg)
    assert permessi.moduli_consentiti(_u("x", "admin"), cfg) == set(permessi.TUTTI)


def test_permessi_normalizza_e_salva():
    cfg = permessi.normalizza({"profili": {"segreteria": ["ru", "inesistente", "ca"], "presidente": []}, "utenti": {"Anna": "segreteria", "Bob": "fantasma"}, "predefinito": "boh"})
    assert cfg["profili"]["segreteria"] == ["ru", "ca"]
    assert set(cfg["profili"]["presidente"]) == set(permessi.TUTTI)             # il presidente non resta mai senza strumenti
    assert cfg["utenti"] == {"anna": "segreteria"} and cfg["predefinito"] == "direzione"
    permessi.salva_config(cfg, "admin")
    assert permessi.carica_config()["utenti"] == {"anna": "segreteria"}
    assert permessi.puo(_u("anna"), "ru", permessi.carica_config()) and not permessi.puo(_u("anna"), "sc", permessi.carica_config())


def test_hub_nasconde_gli_strumenti_non_abilitati():
    at = _app(_u("mario"))
    assert not at.exception
    etichette = " ".join(_bottoni(at))
    assert "Cruscotto" not in etichette and "Rapportini" in etichette
    admin = _app(_u("root", "admin"))
    assert "Cruscotto" in " ".join(_bottoni(admin))


def test_accesso_diretto_a_strumento_chiuso_e_negato():
    at = _app(_u("mario"), "dd")
    assert not at.exception
    assert any("non è abilitato" in e.value for e in at.error)
    assert len(at.tabs) == 0


def test_il_presidente_apre_il_cruscotto():
    cfg = permessi.configurazione_base()
    cfg["utenti"]["lorenzo"] = "presidente"
    permessi.salva_config(cfg, "admin")
    at = _app(_u("lorenzo"), "dd")
    assert not at.exception and not any("non è abilitato" in e.value for e in at.error)


def test_il_calendario_non_mostra_le_scadenze_degli_strumenti_chiusi():
    cfg = permessi.configurazione_base()
    cfg["profili"]["cantiere"] = ["ca", "rp"]
    cfg["utenti"]["geo"] = "cantiere"
    permessi.salva_config(cfg, "admin")
    at = _app(_u("geo"), "ca")
    assert not at.exception


def test_pannello_permessi_per_admin():
    at = _app(_u("root", "admin"), "admin")
    assert not at.exception
    assert any("Permessi" in t.label for t in at.tabs)


# ------------------------------------------------------------------ RUBRICA
def test_ru_collegamenti_e_codici():
    assert ru.link_whatsapp("333 123 4567") == "https://wa.me/393331234567"
    assert ru.link_chiama("+39 02 123") == "tel:+3902123"
    assert ru.link_email("a@b.it", "Ciao").startswith("mailto:a@b.it?subject=Ciao")
    assert ru.link_email("non-una-mail") == ""
    c, av = ru.normalizza_cantieri([{"Cantiere": "A"}, {"Codice": "CAN-2026-005", "Cantiere": "B"}, {"Cantiere": "C"}], 2026)
    assert [x["Codice"] for x in c] == ["CAN-2026-006", "CAN-2026-005", "CAN-2026-007"] and not av
    _, av2 = ru.normalizza_cantieri([{"Codice": "CAN-1", "Cantiere": "A"}, {"Codice": "CAN-1", "Cantiere": "B"}], 2026)
    assert any("unico" in a for a in av2)


def test_ru_scheda_contatto_collega_fatture_e_documenti():
    cont, _ = ru.normalizza_contatti([{"Nome": "Alfa Srl", "Ruolo": "Fornitore", "Telefono": "333 1", "Email": "x@y.it"}])
    docs = [{"Fornitore": "alfa srl", "Documento": "DURC", "Scadenza": "2026-01-01", "Tipo": "Fornitore"}]
    fat = [{"Controparte": "Alfa Srl", "Importo": 100.0, "Saldato": 40.0}]
    col = ru.collegamenti(cont[0], docs, fat, [])
    assert len(col["documenti"]) == 1 and col["aperto"] == 60.0


# ------------------------------------------------------------------ STUDIO LEGALE
def _fatture():
    return sc.normalizza_documenti([{"Tipo": "Attiva", "Controparte": "Mario Verdi SRL", "Documento": "7", "Scadenza": "2026-08-01", "Importo": 10000, "Saldato": 0, "Cantiere": "Villa Lago"}])[0]


def test_lg_fascicolo_suggerisce_studio_dopo_solleciti():
    sol = lg.normalizza_solleciti([{"Cliente": "Mario Verdi SRL", "Data": "2026-09-01", "Livello": lg.LIVELLI[0]}, {"Cliente": "Mario Verdi SRL", "Data": "2026-09-20", "Livello": lg.LIVELLI[1], "Esito": "Nulla"}])[0]
    f = lg.fascicoli(_fatture(), sol, OGGI)
    assert len(f) == 1 and f[0]["Solleciti fatti"] == 2 and f[0]["Suggerimento"].startswith("Passa allo studio")
    ogg, corpo = lg.testo_passaggio(f[0], "Il cliente contesta")
    assert "Mario Verdi SRL" in ogg and "SOLLECITI GIÀ EFFETTUATI" in corpo and "Il cliente contesta" in corpo and "Nulla" in corpo


def test_lg_penali_dal_gantt_con_tetto():
    termini = lg.normalizza_termini([{"Cantiere": "Villa Lago", "Importo": 100000, "Termine": "2026-10-01", "Penale_per_mille": 1.0}])[0]
    comm = [{"Commessa": "villa lago", "Fine stimata": "2026-10-21"}]
    p = lg.penali(termini, comm, 10.0)[0]
    assert p["Ritardo gg"] == 20 and p["Penale"] == pytest.approx(2000.0) and p["Stato"] == "warn"
    p2 = lg.penali(termini, [{"Commessa": "Villa Lago", "Fine stimata": "2027-06-01"}], 10.0)[0]
    assert p2["Penale"] == pytest.approx(10000.0) and p2["Stato"] == "bad"                 # tetto del 10%
    assert lg.penali(termini, [], 10.0)[0]["Stato"] == "nd"


def test_lg_riserve_con_termine_scaduto():
    ris = lg.normalizza_riserve([{"Cantiere": "A", "Descrizione": "Roccia", "Importo": 5000, "Termine": "2026-10-01", "Stato": "Inviata"},
                                 {"Cantiere": "A", "Descrizione": "Vecchia", "Termine": "2026-01-01", "Stato": "Chiusa"}])[0]
    out = lg.calcola_lg(ris, [], [], [], [], [], {"oggi": OGGI})
    assert out["kpi"]["riserve_aperte"] == 1 and out["kpi"]["termini_scaduti"] == 1 and out["avvisi"]


def test_lg_invio_senza_canali_spiega_cosa_manca():
    assert lg.canali_attivi({}) == {"email": False, "slack": False}
    with pytest.raises(RuntimeError, match="STUDIO_LEGALE"):
        lg.invia_studio("o", "c", env={})


def test_lg_invio_email_con_allegato(monkeypatch):
    inviati = []

    class _S:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, u, p): pass
        def send_message(self, m): inviati.append(m)
    monkeypatch.setattr(lg.smtplib, "SMTP", _S)
    env = {"STUDIO_LEGALE_EMAIL": "studio@x.it", "SMTP_HOST": "h", "SMTP_USER": "u@x.it", "SMTP_PASSWORD": "p"}
    assert lg.invia_studio("Oggetto", "Corpo", [("f.pdf", b"%PDF-1", "application/pdf")], env) == ["email"]
    assert inviati[0]["To"] == "studio@x.it" and any(p.get_filename() == "f.pdf" for p in inviati[0].iter_attachments())


def test_lg_calendario_ha_i_termini_legali():
    import calendario
    ev = calendario.eventi({"lg": {"riserve": [{"Cantiere": "A", "Descrizione": "Roccia", "Termine": "2026-10-25", "Stato": "Inviata"}], "contratti": [{"Contratto": "Polizza", "Scadenza": "2026-10-30"}]}}, OGGI, 30)
    assert {e["Categoria"] for e in ev} == {"Termine legale", "Contratto"}


# ------------------------------------------------------------------ BANCA
def test_bk_abbina_importo_e_riferimento_senza_riusare_le_fatture():
    docs = sc.normalizza_documenti([
        {"Tipo": "Attiva", "Controparte": "Comune di Esempio", "Documento": "14/2026", "Scadenza": "2026-10-10", "Importo": 42500, "Saldato": 0},
        {"Tipo": "Passiva", "Controparte": "Calcestruzzi Alfa", "Documento": "311", "Scadenza": "2026-10-12", "Importo": 9800, "Saldato": 0}])[0]
    mov = bk.normalizza_movimenti([{"Data": "2026-10-18", "Descrizione": "BONIFICO DA COMUNE DI ESEMPIO FATT 14/2026", "Importo": 42500},
                                   {"Data": "2026-10-19", "Descrizione": "BONIFICO A CALCESTRUZZI ALFA FATT 311", "Importo": -9800},
                                   {"Data": "2026-10-19", "Descrizione": "SPESE CONTO", "Importo": -18.5}])[0]
    out = bk.calcola_bk(mov, docs)
    assert out["kpi"]["sicuri"] == 2 and out["kpi"]["senza_fattura"] == 1
    assert all(a["Chiude"] for a in out["abbinamenti"])
    nuovi = bk.applica_pagamenti(docs, out["abbinamenti"])
    assert nuovi[0]["Saldato"] == 42500 and nuovi[1]["Saldato"] == 9800


def test_bk_il_verso_conta_e_il_pagamento_parziale_non_chiude():
    docs = sc.normalizza_documenti([{"Tipo": "Passiva", "Controparte": "Ponteggi Gamma", "Documento": "88", "Scadenza": "2026-10-12", "Importo": 9500, "Saldato": 0}])[0]
    entrata = bk.normalizza_movimenti([{"Data": "2026-10-18", "Descrizione": "Ponteggi Gamma", "Importo": 9500}])[0]
    assert bk.calcola_bk(entrata, docs)["abbinamenti"] == []                       # un'entrata non salda una fattura passiva
    parziale = bk.normalizza_movimenti([{"Data": "2026-10-18", "Descrizione": "PONTEGGI GAMMA FATT 88 ACCONTO", "Importo": -4000}])[0]
    a = bk.calcola_bk(parziale, docs)["abbinamenti"][0]
    assert not a["Chiude"] and a["Saldato dopo"] == 4000


# ------------------------------------------------------------------ ORDINI
def test_oa_chi_chiede_non_approva_e_soglie():
    o = oa.normalizza_ordini([{"Fornitore": "Alfa", "Importo": 5000, "Richiedente": "mario", "Cantiere": "V", "Data": "2026-10-20"}], 2026)[0][0]
    soglie = oa.normalizza_soglie([{"Fino_a": 2000, "Livello": "Capocantiere", "Approvatori": ""}, {"Fino_a": 20000, "Livello": "Direttore tecnico", "Approvatori": "luca"}, {"Fino_a": None, "Livello": "Presidente", "Approvatori": "lorenzo"}])
    assert oa.livello_richiesto(o["Importo"], soglie)["Livello"] == "Direttore tecnico"
    assert not oa.puo_approvare("mario", "utente", o, soglie)[0]                   # e' il richiedente
    assert not oa.puo_approvare("anna", "utente", o, soglie)[0]                    # non e' tra gli approvatori
    assert oa.puo_approvare("luca", "utente", o, soglie)[0]
    assert not oa.puo_approvare("luca", "lettore", o, soglie)[0]
    assert not oa.puo_approvare("luca", "utente", o, soglie, {"alfa"})[0]          # fornitore con documenti scaduti


def test_oa_cambio_importo_richiede_nuova_approvazione():
    o = oa.normalizza_ordini([{"Fornitore": "Alfa", "Importo": 5000, "Richiedente": "mario", "Cantiere": "V"}], 2026)[0][0]
    ap = oa.registra([], o, "Approvato", "luca", "2026-10-21 10:00")
    assert oa.stato_ordine(o, ap)[0] == "Approvato"
    assert oa.stato_ordine({**o, "Importo": 7000.0}, ap)[0] == "Da riapprovare"
    assert oa.stato_ordine(o, oa.registra(ap, o, "Respinto", "luca", "x", "caro"))[0] == "Respinto"


def test_oa_segnala_anomalie():
    o = oa.normalizza_ordini([{"Fornitore": "Alfa", "Importo": 5000, "Richiedente": "mario"}], 2026)[0]
    ap = oa.registra([], o[0], "Approvato", "mario", "x")
    out = oa.calcola_oa(o, oa.normalizza_soglie([]), ap, [{"Fornitore": "Alfa", "Scadenza": "2026-01-01"}], OGGI)
    assert out["kpi"]["anomalie"] == 1
    assert any("documenti scaduti" in a for a in out["avvisi"]) and any("approvato da chi" in a for a in out["avvisi"]) and any("senza cantiere" in a for a in out["avvisi"])


# ------------------------------------------------------------------ FOTO E FIRMA, APP INSTALLABILE
def _jpg(w=2400, h=1800):
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (w, h), (200, 80, 10)).save(b, "JPEG")
    return b.getvalue()


def test_foto_ridotte_e_salvate_senza_perdere_quelle_degli_altri():
    from PIL import Image
    grande = _jpg()
    piccola = firma.riduci_foto(grande)
    assert len(piccola) < len(grande) and max(Image.open(io.BytesIO(piccola)).size) == firma.LATO_MAX
    assert firma.aggiungi("R1", [piccola], None, "", "mario")
    assert firma.aggiungi("R1", [piccola], None, "", "luca")
    assert firma.aggiungi("R2", [], b"\x89PNG\r\n\x1a\n" + b"0" * 10, "Luca", "luca")
    al = firma.carica()
    assert len(al["R1"]["foto"]) == 2 and al["R2"]["firma"]["nome"] == "Luca"
    for _ in range(10):
        firma.aggiungi("R1", [piccola], None, "", "mario")
    assert len(firma.carica()["R1"]["foto"]) == firma.MAX_FOTO


def test_firma_dataurl_valida_solo_png():
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGBA", (50, 20), (0, 0, 0, 0)).save(b, "PNG")
    url = "data:image/png;base64," + firma.a_b64(b.getvalue())
    assert firma.da_dataurl(url) == b.getvalue() and firma.firma_vuota(b.getvalue())
    assert firma.da_dataurl("data:image/jpeg;base64,AAAA") is None and firma.da_dataurl("boh") is None


def test_allegati_non_riempiono_il_registro_di_dati_binari():
    firma.aggiungi("R1", [firma.riduci_foto(_jpg(400, 300))], None, "", "mario")
    ev = storage.elenca_eventi(5)
    assert ev[0]["Azione"] == "allegati_salvati" and len(ev[0]["Dettaglio"]) < 100


def test_pwa_icone_e_pannello():
    import pwa
    ic = pwa._icone()
    assert set(ic) == {"i180", "i192", "i512"}
    from PIL import Image
    assert Image.open(io.BytesIO(__import__("base64").b64decode(ic["i512"]))).size == (512, 512)


@pytest.mark.parametrize("modulo", ["ru", "lg", "bk", "oa", "rp", "ca"])
def test_i_nuovi_strumenti_si_aprono(modulo):
    at = _app(_u("root", "admin"), modulo)
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.tabs) >= 3
