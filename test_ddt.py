"""Archivio DDT: controlli sui file, ricerca a pagine, doppioni, lettura PDF, importazione Excel, sicurezza."""
import io
import zipfile

import pytest

import ddt
import storage


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    p = str(tmp_path / "d.db")
    storage.svuota_cache()
    return p


def pdf(testo="D.D.T. n. 412 del 28/10/2026\nBeton Nord S.r.l.\nCalcestruzzo"):
    from fpdf import FPDF
    f = FPDF()
    f.add_page()
    f.set_font("Helvetica", size=12)
    for riga in testo.split("\n"):
        f.cell(0, 8, riga, new_x="LMARGIN", new_y="NEXT")
    return bytes(f.output())


def png(colore=(200, 30, 30), lato=300):
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (lato, lato), colore).save(b, "PNG")
    return b.getvalue()


def xlsx(righe, nome_foglio="Bolla"):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = nome_foglio
    for r in righe:
        ws.append(r)
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


# ------------------------------------------------------------------ file
def test_riconosce_il_tipo_dal_contenuto_non_dal_nome():
    assert ddt.riconosci(pdf()) == "pdf" and ddt.riconosci(png()) == "png"
    assert ddt.riconosci(xlsx([["a"]])) == "xlsx" and ddt.riconosci(b"MZ\x90\x00 exe") is None and ddt.riconosci(b"") is None


def test_file_travestito_o_di_formato_non_ammesso_viene_rifiutato(db):
    with pytest.raises(ddt.DdtErrore, match="Formato non riconosciuto"):
        ddt.salva("virus.pdf", b"MZ\x90\x00\x03\x00\x00\x00", path=db)
    with pytest.raises(ddt.DdtErrore, match="estensione"):
        ddt.salva("bolla.pdf", png(), path=db)                       # e' una foto con l'estensione sbagliata
    with pytest.raises(ddt.DdtErrore, match="vuoto"):
        ddt.salva("x.pdf", b"", path=db)
    assert ddt.conta(path=db) == 0


def test_dimensione_massima(db, monkeypatch):
    monkeypatch.setattr(ddt, "MAX_BYTES", 1000)
    with pytest.raises(ddt.DdtErrore, match="massimo"):
        ddt.salva("grande.pdf", pdf("x" * 10) + b"0" * 2000, path=db)


def test_zip_bomba_e_xlsx_rovinato(db, monkeypatch):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/workbook.xml", "<workbook/>")
        z.writestr("xl/enorme.xml", "0" * 5_000_000)
    monkeypatch.setattr(ddt, "MAX_ZIP_ESPANSO", 1_000_000)
    with pytest.raises(ddt.DdtErrore, match="troppo grande"):
        ddt.salva("bomba.xlsx", b.getvalue(), path=db)
    assert ddt.riconosci(b"PK\x03\x04 non uno zip") is None


def test_foto_ridotta_e_nome_pulito(db):
    from PIL import Image
    grande = Image.new("RGB", (4000, 3000), (10, 120, 200))
    b = io.BytesIO()
    grande.save(b, "PNG")
    i = ddt.salva("../../etc/passwd<bolla>.png", b.getvalue(), numero="DDT n. 77", path=db)
    meta, dati = ddt.leggi(i, db)
    im = Image.open(io.BytesIO(dati))
    assert max(im.size) <= 2000 and meta["mime"] == "image/jpeg" and meta["nome_file"].endswith(".jpg") and "/" not in meta["nome_file"] and "<" not in meta["nome_file"]
    assert meta["ddt_numero"] == "77"


def test_doppione_riconosciuto_dal_contenuto(db):
    a = ddt.salva("a.pdf", pdf(), numero="412", path=db)
    with pytest.raises(ddt.DdtDoppio) as e:
        ddt.salva("copia_con_altro_nome.pdf", pdf(), numero="999", path=db)
    assert e.value.id_esistente == a and "412" in str(e.value) and ddt.conta(path=db) == 1


# ------------------------------------------------------------------ ricerca, pagine, modifica
def test_elenco_a_pagine_filtri_e_senza_dati_pesanti(db):
    for n in range(30):
        ddt.salva(f"b{n}.png", png((n * 8, 10, 10), 50 + n), numero=str(100 + n), data=f"2026-10-{(n % 28) + 1:02d}", fornitore="Beton Nord" if n % 2 else "Acciai", commessa="Villa Lago", path=db)
    assert ddt.conta(path=db) == 30
    p1, p2 = ddt.elenca(limite=25, path=db), ddt.elenca(limite=25, offset=25, path=db)
    assert len(p1) == 25 and len(p2) == 5 and not ({x["id"] for x in p1} & {x["id"] for x in p2})
    assert "dati" not in p1[0]                                                  # gli elenchi non portano mai i file
    assert ddt.conta(testo="beton", path=db) == 15 and ddt.conta(testo="119", path=db) == 1
    assert ddt.conta(da="2026-10-10", a="2026-10-12", path=db) >= 3
    assert ddt.conta(testo="100%'; DROP TABLE ddt_file;--", path=db) == 0 and ddt.conta(path=db) == 30   # nessuna iniezione


def test_modifica_elimina_e_spazio(db):
    i = ddt.salva("a.pdf", pdf(), path=db)
    assert ddt.conta(solo_senza_numero=True, path=db) == 1
    ddt.aggiorna(i, numero="DDT n. 55/A", fornitore="Cave Est", path=db)
    assert ddt.per_numero("55/A", db)[0]["fornitore"] == "Cave Est" and ddt.conta(solo_senza_numero=True, path=db) == 0
    n, b = ddt.spazio(db)
    assert n == 1 and b == len(pdf()) or b > 0
    ddt.elimina(i, db)
    assert ddt.conta(path=db) == 0 and ddt.leggi(i, db) is None and ddt.spazio(db) == (0, 0)


def test_normalizza_numero():
    assert ddt.normalizza_numero("DDT n. 412") == "412" and ddt.normalizza_numero(" D.D.T. nr. 12/B ") == "12/B"
    assert ddt.normalizza_numero(None) == "" and ddt.normalizza_numero("412") == "412"


# ------------------------------------------------------------------ lettura PDF e nome file
def test_propone_numero_data_e_fornitore_dal_pdf():
    p = ddt.proponi("scansione001.pdf", pdf())
    assert p["numero"] == "412" and p["data"] == "2026-10-28" and "Beton Nord" in p["fornitore"]


def test_propone_dal_nome_del_file_se_il_pdf_non_ha_testo():
    p = ddt.proponi("DDT_412_2026-10-28.png", png())
    assert p["numero"] == "412" and p["data"] == "2026-10-28"
    assert ddt.proponi("foto.jpg", png()) == {"numero": "", "data": "", "fornitore": ""}
    assert ddt.proponi_da_testo("")["numero"] == "" and ddt.testo_pdf(b"%PDF-1.4 rotto") == ""


# ------------------------------------------------------------------ Excel
def test_importa_excel_con_intestazioni_diverse_e_righe_vuote():
    f = xlsx([["Bolla fornitore Beton Nord"], [], ["Descrizione", "Q.tà", "UM", "Prezzo unitario", "N. DDT", "Data DDT", "Cantiere"],
              ["Calcestruzzo C25/30", "60", "mc", "120,50", 412.0, "28/10/2026", "Villa Lago"],
              [None, None, None, None, None, None, None],
              ["Ferro d'armatura", 3000, "kg", 1.1, "412", "2026-10-28", "Villa Lago"],
              ["senza quantita", None, "pz", 1, "412", None, None]])
    righe, av, riconosciute = ddt.leggi_excel(f, "bolla.xlsx")
    assert len(righe) == 2 and len(av) == 1 and "riga 7" in av[0]
    assert righe[0] == {"Materiale": "Calcestruzzo C25/30", "Fornitore": "", "Commessa": "Villa Lago", "Quantita": 60.0, "Um": "mc", "Prezzo_unit": 120.5,
                        "Consegna_prevista": "", "Consegnato": "sì", "Data_consegna": "2026-10-28", "Ddt": "412"}
    assert righe[1]["Ddt"] == "412" and {"Materiale", "Quantita", "Ddt"} <= set(riconosciute)


def test_propone_numero_dall_excel_se_e_unico():
    f = xlsx([["Descrizione", "Q.tà", "N. DDT", "Data DDT", "Fornitore"], ["Cemento", 10, "600", "28/10/2026", "Beton Nord"], ["Ferro", 5, "600", "28/10/2026", "Beton Nord"]])
    assert ddt.proponi("bolla.xlsx", f) == {"numero": "600", "data": "2026-10-28", "fornitore": "Beton Nord"}
    g = xlsx([["Descrizione", "Q.tà", "N. DDT"], ["Cemento", 10, "600"], ["Ferro", 5, "601"]])
    assert ddt.proponi("bolla.xlsx", g)["numero"] == ""                          # due numeri diversi: non indovina


def test_excel_senza_colonne_minime_o_non_excel():
    with pytest.raises(ddt.DdtErrore, match="Materiale"):
        ddt.leggi_excel(xlsx([["Nome", "Colore"], ["a", "rosso"]]))
    with pytest.raises(ddt.DdtErrore, match="Non è un file Excel"):
        ddt.leggi_excel(pdf())


def test_importazione_non_duplica_le_righe_gia_presenti():
    esist = [{"Materiale": "Ferro", "Commessa": "Villa Lago", "Quantita": 10, "Ddt": "412"}]
    nuove = [{"Materiale": "ferro ", "Commessa": "villa lago", "Quantita": 10.0, "Ddt": "DDT n. 412"}, {"Materiale": "Sabbia", "Commessa": "Villa Lago", "Quantita": 5, "Ddt": "412"},
             {"Materiale": "Sabbia", "Commessa": "Villa Lago", "Quantita": 5, "Ddt": "412"}]
    ok, dop = ddt.righe_nuove(esist, [{**n, "Ddt": ddt.normalizza_numero(n["Ddt"])} for n in nuove])
    assert [r["Materiale"] for r in ok] == ["Sabbia"] and dop == 2


# ------------------------------------------------------------------ controlli incrociati
def test_controlli_tra_tabella_e_archivio(db):
    ddt.salva("a.pdf", pdf(), numero="412", path=db)
    ddt.salva("b.png", png(), numero="999", path=db)
    ordini = [{"Materiale": "A", "Consegnato": "sì", "Ddt": "412"}, {"Materiale": "B", "Consegnato": "sì", "Ddt": "500"}, {"Materiale": "C", "Consegnato": "sì", "Ddt": ""},
              {"Materiale": "D", "Consegnato": "no", "Ddt": ""}]
    c = ddt.controlli(ordini, db)
    assert [o["Materiale"] for o in c["senza_file"]] == ["B"] and [o["Materiale"] for o in c["senza_numero"]] == ["C"] and [f["ddt_numero"] for f in c["file_orfani"]] == ["999"]


def test_backup_json_ha_solo_i_dati_descrittivi(db):
    ddt.salva("a.pdf", pdf(), numero="412", path=db)
    e = ddt.elenco_per_backup(db)
    assert e[0]["ddt_numero"] == "412" and "dati" not in e[0]


# ------------------------------------------------------------------ schermata
def _app(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("APP_PASSWORD", "segreta")
    monkeypatch.setenv("ESEMPI_ATTIVI", "1")
    monkeypatch.setenv("FCR_DB_PATH", str(tmp_path / "ui.db"))
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "ui.db"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    storage.svuota_cache()
    at = AppTest.from_file("app.py", default_timeout=120).run()
    at.text_input(key="login_user").set_value("admin")
    at.text_input(key="login_pw").set_value("segreta")
    at.button[0].click().run()
    at.session_state["active_module"] = "mt"
    at.run()
    return at


def test_scheda_ddt_si_apre_e_mostra_archivio_vuoto(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    assert not at.exception, [e.value for e in at.exception]
    assert any("Bolle (DDT)" in m.value for m in at.markdown)
    at.radio(key="ddt_sez").set_value("🗂️ Archivio").run()
    assert not at.exception and any("Non c'è ancora nessuna bolla" in i.value for i in at.info)
    at.radio(key="ddt_sez").set_value("✅ Controlli").run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("senza il file della bolla" in w.value for w in at.warning)            # l'esempio ha una consegna con DDT 412 e nessun file


def test_carica_pdf_foto_ed_excel_dalla_scheda(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    up = at.file_uploader(key="ddt_up_0")
    xl = xlsx([["Materiale", "Quantità", "Um", "Prezzo", "N. DDT"], ["Cemento", 10, "q", 8, "600"], ["Ferro", 5, "q", 60, "600"]])
    up.set_value([("DDT_412_2026-10-28.pdf", pdf(), "application/pdf"), ("foto.png", png(), "image/png"), ("rotto.pdf", b"MZ non e' un pdf", "application/pdf"), ("bolla600.xlsx", xl, "application/vnd.ms-excel")])
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Formato non riconosciuto" in e.value for e in at.error)
    assert any("Numero e data letti dal file" in c.value for c in at.caption)
    assert at.text_input(key=next(t.key for t in at.text_input if t.label == "N. DDT")).value == "412"
    assert any("2 righe lette dall'Excel" in m.value for m in at.markdown)
    at.button(key=next(b.key for b in at.button if b.key and b.key.startswith("ddt_imp_"))).click().run()
    assert len(at.session_state["mt_ord"]) >= 2 and "600" in set(at.session_state["mt_ord"]["Ddt"])
    at.button(key="ddt_salva").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert ddt.conta() == 3                                                      # PDF, foto ed Excel archiviati; il file rotto no
    assert {m["ddt_numero"] for m in ddt.elenca()} >= {"412"}


# ------------------------------------------------------------------ PostgreSQL vero (solo se TEST_DATABASE_URL e' impostata)
@pytest.mark.skipif(not __import__("os").environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL non impostata")
def test_archivio_su_postgresql(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", __import__("os").environ["TEST_DATABASE_URL"])
    storage.svuota_cache()
    with ddt._db() as con:
        con.execute("DELETE FROM ddt_file")
    p = pdf()
    i = ddt.salva("a.pdf", p, numero="DDT n. 412", data="2026-10-28", fornitore="Beton Nord", commessa="Villa Lago", utente="mario")
    with pytest.raises(ddt.DdtDoppio):
        ddt.salva("b.pdf", p)
    meta, dati = ddt.leggi(i)
    assert dati == p and isinstance(dati, bytes) and meta["ddt_numero"] == "412" and meta["dimensione"] == len(p)
    for n in range(30):
        ddt.salva(f"f{n}.png", png((n * 7, 20, 20), 40 + n), numero=str(500 + n), fornitore="Acciai" if n % 2 else "Cave")
    assert ddt.conta() == 31 and ddt.conta(testo="acciai") == 15 and len(ddt.elenca(limite=25)) == 25 and "dati" not in ddt.elenca()[0]
    ddt.aggiorna(i, numero="413")
    assert ddt.per_numero("413")[0]["id"] == i and ddt.spazio()[0] == 31
    assert ddt.controlli([{"Materiale": "A", "Consegnato": "sì", "Ddt": "413"}, {"Materiale": "B", "Consegnato": "sì", "Ddt": "9"}])["senza_file"][0]["Materiale"] == "B"
    assert storage.esporta_backup()["ddt_file"] and "dati" not in storage.esporta_backup()["ddt_file"][0]
    ddt.elimina(i)
    assert ddt.leggi(i) is None
    with ddt._db() as con:
        con.execute("DELETE FROM ddt_file")


def test_archivio_ricerca_modifica_ed_eliminazione_dalla_scheda(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    a = ddt.salva("a.pdf", pdf(), numero="412", data="2026-10-28", fornitore="Beton Nord", commessa="Villa Lago", utente="mario")
    ddt.salva("b.png", png(), numero="500", fornitore="Acciai", utente="mario")
    at.radio(key="ddt_sez").set_value("🗂️ Archivio").run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("2 bolle trovate" in c.value for c in at.caption)
    at.text_input(key="ddt_cerca").set_value("beton").run()
    assert any("1 bolle trovate" in c.value for c in at.caption)
    at.selectbox(key="ddt_sel").set_value(0).run()
    assert not at.exception, [e.value for e in at.exception]
    assert [b.key for b in at.get("download_button") if str(b.key).startswith("ddt_dl_")] == [f"ddt_dl_{a}"]   # il file si legge solo dopo aver scelto la bolla
    f = [x for x in at.text_input if x.label == "Fornitore" and x.value == "Beton Nord"][0]
    f.set_value("Beton Nord SRL")
    [b for b in at.button if b.label == "Salva le correzioni"][0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert ddt.per_numero("412")[0]["fornitore"] == "Beton Nord SRL"
    # eliminazione: serve la conferma
    assert at.button(key=f"ddt_del_{a}").disabled
    at.checkbox(key=f"ddt_conf_{a}").check().run()
    at.button(key=f"ddt_del_{a}").click().run()
    assert not at.exception and ddt.leggi(a) is None and ddt.conta() == 1


def test_lettore_non_puo_caricare_ne_eliminare(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    at.session_state["utente"] = {**at.session_state["utente"], "ruolo": "lettore"}
    at.run()
    assert not at.exception and any("sola lettura" in i.value for i in at.info)
    assert not [u for u in at.file_uploader if u.key and u.key.startswith("ddt_up_")]
