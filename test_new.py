import datetime as dt
import novita, hub, theme

OGGI = dt.date(2026, 11, 6)


def test_new_dalle_novita_recenti(tmp_path):
    p = str(tmp_path / "n.db")
    n = novita.sigle_nuove("anna", OGGI, p)
    assert "fp" in n and "fv" in n
    assert "cf" not in n


def test_new_si_spegne_quando_apri_e_per_persona(tmp_path):
    p = str(tmp_path / "n.db")
    n = novita.sigle_nuove("anna", OGGI, p)
    novita.segna_vista("anna", "fp", n["fp"], p)
    assert "fp" not in novita.sigle_nuove("anna", OGGI, p)
    assert "fp" in novita.sigle_nuove("luca", OGGI, p)


def test_new_scade_dopo_giorni(tmp_path):
    p = str(tmp_path / "n.db")
    assert novita.sigle_nuove("anna", OGGI + dt.timedelta(days=novita.GIORNI_NEW + 30), p) == {}


def test_new_automatico_con_nuova_voce(tmp_path):
    p = str(tmp_path / "n.db")
    novita.aggiungi("9.9.9", "Prova", ["x"], ["Scadenzario"], data=OGGI.isoformat(), path=p)
    n = novita.sigle_nuove("anna", OGGI, p)
    assert n["sc"]["id"] == "9.9.9"
    novita.segna_vista("anna", "sc", n["sc"], p)
    assert "sc" not in novita.sigle_nuove("anna", OGGI, p)


def test_una_voce_vecchia_non_riaccende_il_bollino_gia_spento(tmp_path):
    p = str(tmp_path / "n.db")
    novita.aggiungi("1.0.0", "Vecchia", ["x"], ["Scadenzario"], data=(OGGI - dt.timedelta(days=5)).isoformat(), path=p)
    novita.aggiungi("1.0.1", "Nuova", ["y"], ["Scadenzario"], data=OGGI.isoformat(), path=p)
    n = novita.sigle_nuove("anna", OGGI, p)
    novita.segna_vista("anna", "sc", n["sc"], p)                       # ha aperto lo Scadenzario: si spegne per la novita' piu' recente
    assert "sc" not in novita.sigle_nuove("anna", OGGI, p)             # e la voce piu' vecchia non lo riaccende


def test_aprire_la_pagina_novita_spegne_tutti_i_bollini_pendenti(tmp_path):
    p = str(tmp_path / "n.db")
    n = novita.sigle_nuove("anna", OGGI, p)
    assert "fp" in n and "fv" in n                                    # due strumenti ancora col bollino NEW
    novita.segna_tutte_viste("anna", OGGI, p)
    assert novita.sigle_nuove("anna", OGGI, p) == {}                  # aprendo la pagina delle novita' si spengono tutti, non uno alla volta
    assert "fp" in novita.sigle_nuove("luca", OGGI, p)                 # per un altro collega restano accesi


def test_pill_nella_scheda():
    assert "new-pill" in theme.hub_card("1", "x", "t", "d", [], [], "", nuovo=True)
    assert "new-pill" not in theme.hub_card("1", "x", "t", "d", [], [])
