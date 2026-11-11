import pytest

import doc_allegati as da

PDF = b"%PDF-1.4 contenuto di prova"


def test_salva_elenca_leggi_elimina(tmp_path):
    p = str(tmp_path / "d.db")
    i = da.salva("fornitori", "Calcestruzzi Alfa", "DURC", "durc.pdf", PDF, scadenza="2026-12-01", utente="mario", path=p)
    assert da.elenca("fornitori", path=p)[0]["id"] == i
    assert da.elenca("fornitori", "Calcestruzzi Alfa", path=p)[0]["voce"] == "DURC"
    assert da.elenca("fornitori", "Altro fornitore", path=p) == []
    meta, dati = da.leggi(i, path=p)
    assert meta["nome_file"] == "durc.pdf" and dati == PDF
    da.elimina(i, path=p)
    assert da.elenca("fornitori", path=p) == []


def test_stesso_file_due_volte_e_rifiutato(tmp_path):
    p = str(tmp_path / "d.db")
    da.salva("fornitori", "Alfa", "DURC", "durc.pdf", PDF, path=p)
    with pytest.raises(da.DocDoppio):
        da.salva("fornitori", "Alfa", "DURC", "durc_copia.pdf", PDF, path=p)


def test_categorie_separate(tmp_path):
    p = str(tmp_path / "d.db")
    da.salva("fornitori", "Alfa", "DURC", "a.pdf", PDF, path=p)
    da.salva("azienda", "", "DURC", "b.pdf", PDF, path=p)                     # stesso contenuto ma categoria diversa: non e' un doppio
    assert len(da.elenca("fornitori", path=p)) == 1 and len(da.elenca("azienda", path=p)) == 1
    assert da.conteggio("fornitori", path=p) == {"Alfa": 1}


def test_file_non_valido_respinto(tmp_path):
    p = str(tmp_path / "d.db")
    with pytest.raises(Exception):
        da.salva("azienda", "", "SOA", "finto.pdf", b"non e' un pdf", path=p)
