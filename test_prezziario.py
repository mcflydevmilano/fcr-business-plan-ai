"""Prezziario: lettura del listino, ricerca, salvataggio, scadenza, confronto, controllo prezzi negli ordini e uso nel Computo."""
import datetime as dt
import os
import tempfile

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import oa
import permessi
import pz
import pz_ui
import storage

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")


@pytest.fixture(autouse=True)
def db(monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
    monkeypatch.setenv("APP_PASSWORD", "segreta")


def _file():
    """Righe come nel listino della Camera di Commercio: intestazioni a prezzo zero, avvertenze, apostrofi HTML, codici ripetuti, descrizione ridotta."""
    cols = ["Codice", "Descrizione ridotta", "Unità di misura", "Prezzo", "Incidenza manodopera", "Incidenza Noli & Trasporti", "Incidenza sicurezza", "Gruppo", "Supergruppo", "Sottogruppo"]
    r = [("C.05", "energie alternative", "", 0, 0, "", 0, "<nessuno>", "energie alternative e rinnovabili", "<nessuno>"),
         ("C.05.01.0005", "Installatore di livello B1", "ora", 49.14, 0, "", 0, "MANO D&apos;OPERA", "energie alternative e rinnovabili", "<nessuno>"),
         ("C.05.01.0045 AVVERTENZE", "AVVERTENZE SUBFORNITURA ...", "", 0, 0, "", 0, "MANO D&apos;OPERA", "energie alternative e rinnovabili", "<nessuno>"),
         ("B.06.04.0025.b", "Rivestimento interno in piastrelle in bicottura posato co ... uraria alla posa in opera", "m²", 27.85, 0, "", 0, "Rivestimenti", "Opere di pavimentazione", "<nessuno>"),
         ("B.02.04.0195.c", "Controsoffitto in aderenza a semplice orditura", "m²", "53,66", 0, "", 0, "Controsoffitti", "Opere da cementista", "<nessuno>"),
         ("C.01.03.0080.a", "Canna fumaria doppia parete", "m", 155.64, 0, "", 0, "Canne", "impianti di climatizzazione", "<nessuno>"),
         ("C.01.03.0080.a", "Canna fumaria doppia parete", "m", 175.84, 0, "", 0, "Canne", "impianti di climatizzazione", "<nessuno>"),
         ("A.01.02.0160.c", "Sosta di autobetoniera: riduzione", "cad", -18, 0, "", 0, "Calcestruzzi", "Opere speciali", "<nessuno>"),
         ("A.00.00.0122.a", "Es. calcolo importo", "0", 45, 0, "", 0, "Sicurezza", "Principali costi della sicurezza", "<nessuno>"),
         ("", "riga senza codice", "cad", 5, 0, "", 0, "x", "y", "z")]
    return pd.DataFrame(r, columns=cols)


def test_lettura_del_file_come_il_listino_reale():
    righe, rap = pz.da_dataframe(_file())
    assert rap["voci"] == 7 and rap["intestazioni"] == 1 and rap["avvertenze"] == 1 and rap["senza_codice"] == 1
    assert rap["prezzi_negativi"] == 1 and rap["senza_um"] == 1 and rap["codici_ripetuti"] == 1
    assert rap["caratteri_puliti"] == 1 and rap["descrizioni_tagliate"] == 1 and not rap["incidenze_presenti"]
    assert "MANO D'OPERA" == righe[0]["gruppo"]                                   # &apos; ripulito
    assert [r["chiave"] for r in righe if r["codice"] == "C.01.03.0080.a"] == ["C.01.03.0080.a", "C.01.03.0080.a#2"]
    assert next(r for r in righe if r["codice"] == "B.02.04.0195.c")["prezzo"] == 53.66   # numero scritto all'italiana
    assert righe[0]["supergruppo"] == "energie alternative e rinnovabili" and righe[0]["sottogruppo"] == ""   # «<nessuno>» tolto
    av = " ".join(pz.avvisi_rapporto(rap))
    assert "descrizione completa" in av and "incidenze" in av


def test_file_senza_colonne_indispensabili():
    with pytest.raises(ValueError, match="Prezzo"):
        pz.da_dataframe(pd.DataFrame({"Codice": ["A"], "Descrizione": ["x"]}))


def test_incidenze_in_frazione_diventano_percentuali():
    df = _file().copy()
    df["Incidenza manodopera"] = df["Incidenza manodopera"].astype(float)
    df.loc[3, "Incidenza manodopera"] = 0.35
    righe, rap = pz.da_dataframe(df)
    assert rap["incidenze_presenti"] and next(r for r in righe if r["codice"] == "B.06.04.0025.b")["inc_mo"] == pytest.approx(35.0)


def test_ricerca_per_parola_codice_e_capitolo():
    righe, _ = pz.da_dataframe(_file())
    df = pz.prepara(righe)
    assert list(pz.cerca(df, "piastrelle bicottura")["codice"]) == ["B.06.04.0025.b"]
    assert list(pz.cerca(df, "PIASTRELLE")["codice"]) == ["B.06.04.0025.b"]            # maiuscole e minuscole uguali
    assert list(pz.cerca(df, "B.02")["codice"]) == ["B.02.04.0195.c"]                  # inizio del codice
    assert len(pz.cerca(df, "canna fumaria")) == 2                                      # le due varianti
    assert len(pz.cerca(df, "", supergruppo="Opere da cementista")) == 1
    assert list(pz.cerca(df, "mano d'opera")["codice"]) == ["C.05.01.0005"]            # cerca anche nel gruppo
    assert pz.cerca(df, "parola inesistente").empty
    assert "Opere da cementista" in pz.capitoli(df)


def test_salvataggio_scadenza_e_prezziario_in_vigore(tmp_path):
    p = str(tmp_path / "x.db")
    righe, _ = pz.da_dataframe(_file())
    meta = pz.salva_prezziario({"anno": 2026, "quad": 2, "nome": "CCIAA"}, righe, "lorenzo", p)
    assert meta["periodo"] == "2° quadrimestre 2026" and meta["valido_da"] == "2026-05-01" and meta["valido_a"] == "2026-08-31"
    ind = pz.carica_indice(p)
    assert list(ind) == ["2026-Q2"] and len(pz.carica_righe("2026-Q2", p)) == len(righe)
    assert pz.stato_validita(ind, dt.date(2026, 7, 1))["stato"] == "ok"
    s = pz.stato_validita(ind, dt.date(2026, 10, 22))
    assert s["stato"] == "warn" and s["giorni"] == 52 and "prezzi da aggiornare" in s["testo"]
    assert pz.stato_validita(ind, dt.date(2027, 3, 1))["stato"] == "bad"                # oltre un quadrimestre di ritardo
    assert pz.stato_validita({}, dt.date(2026, 10, 22))["stato"] == "nd"
    pz.salva_prezziario({"anno": 2026, "quad": 3}, righe[:2], "lorenzo", p)               # arriva il 3° quadrimestre
    ind = pz.carica_indice(p)
    assert pz.corrente(ind, dt.date(2026, 10, 22))["id"] == "2026-Q3" and pz.stato_validita(ind, dt.date(2026, 10, 22))["stato"] == "ok"
    pz.elimina_prezziario("2026-Q3", "lorenzo", p)
    assert list(pz.carica_indice(p)) == ["2026-Q2"]


def test_confronto_tra_quadrimestri():
    a, _ = pz.da_dataframe(_file())
    nuove = [dict(r) for r in a]
    nuove[1]["prezzo"] = 28.5                                                           # B.06.04.0025.b: +2,3%
    nuove[0]["prezzo"] = 49.14                                                          # invariata
    nuove = nuove[:-1] + [{**a[0], "chiave": "Z.01", "codice": "Z.01", "prezzo": 10.0}]
    c = pz.confronta(a, nuove)
    assert c["variate"][0]["codice"] == "B.06.04.0025.b" and c["variate"][0]["variazione_pct"] == pytest.approx(2.34, abs=0.01)
    assert len(c["nuove"]) == 1 and len(c["eliminate"]) == 1 and c["invariate"] >= 1 and c["aumenti"] == 1


def test_costo_dal_prezzo_e_split_manodopera():
    r = {"codice": "X", "descrizione": "d", "um": "m²", "prezzo": 126.5, "supergruppo": "Capitolo", "inc_mo": 40.0, "inc_noli": 10.0}
    v = pz.voce_per_computo(r, 10, "prezzo", 15.0, 10.0)
    assert v["Materiali"] + v["Manodopera"] + v["Noli_altro"] == pytest.approx(100.0, abs=0.01)     # 126,5 / 1,15 / 1,10 = 100
    assert v["Manodopera"] == pytest.approx(40.0, abs=0.01) and v["Quantita"] == 10.0 and v["Codice"] == "X"
    w = pz.voce_per_computo({**r, "inc_mo": 0, "inc_noli": 0}, 1, "costo")
    assert w["Materiali"] == 126.5 and w["Manodopera"] == 0


def test_controllo_prezzo_negli_ordini():
    righe, _ = pz.da_dataframe(_file())
    prezzi = pz.indice_prezzi(righe)
    ok = {"Voce": "B.06.04.0025.b", "Quantita": 100, "Importo": 2785.0}
    assert pz.controllo_prezzo(ok, prezzi) is None
    caro = {"Voce": "B.06.04.0025.b", "Quantita": 100, "Importo": 3500.0}               # 35 €/m² contro 27,85
    assert "sopra il prezziario" in pz.controllo_prezzo(caro, prezzi) and "26%" in pz.controllo_prezzo(caro, prezzi)
    assert pz.controllo_prezzo({**caro, "Importo": 3000.0}, prezzi) is None             # +7,7%: entro il 10%
    assert pz.controllo_prezzo({"Voce": "NON.ESISTE", "Quantita": 1, "Importo": 5}, prezzi) == "la voce NON.ESISTE non è nel prezziario"
    assert pz.controllo_prezzo({"Voce": "", "Quantita": 1, "Importo": 5}, prezzi) is None   # senza voce, nessun controllo
    variante = {"Voce": "C.01.03.0080.a", "Quantita": 10, "Importo": 1900.0}            # 190 €/m: dentro 155,64-175,84 +10%? 175,84*1,1=193,4 -> ok
    assert pz.controllo_prezzo(variante, prezzi) is None
    ordini, _ = oa.normalizza_ordini([{"Numero": "ODA-2026-001", "Data": "2026-10-20", "Fornitore": "Ceramiche Srl", "Cantiere": "Villa Lago", "Importo": 3500, "Richiedente": "capo",
                                       "Voce": "B.06.04.0025.b", "Quantita": 100}])
    out = oa.calcola_oa(ordini, oa.normalizza_soglie([]), [], prezzi=prezzi, soglia_prezzo=10.0)
    assert any("sopra il prezziario" in a for a in out["ordini"][0]["Anomalie"])
    out2 = oa.calcola_oa(ordini, oa.normalizza_soglie([]), [], prezzi=prezzi, soglia_prezzo=50.0)
    assert not any("prezziario" in a for a in out2["ordini"][0]["Anomalie"])


def test_periodo_dal_nome_del_file():
    assert pz_ui.periodo_da_nome("Listino_CCAA_2_quadrimestre_2026.xlsx") == (2026, 2)
    assert pz_ui.periodo_da_nome("listino 3° quadrimestre 2027.xlsx") == (2027, 3)
    assert pz_ui.periodo_da_nome("prezzi.xlsx") is None
    assert pz.date_quadrimestre(2026, 1) == (dt.date(2026, 1, 1), dt.date(2026, 4, 30))


def test_permessi_vecchi_ricevono_il_prezziario_secondo_le_regole_base():
    vecchia = {"profili": {"amministrazione": ["sc", "pv"], "commerciale": ["ga", "pv"], "personale": ["rp"], "direzione": ["sc"]}, "utenti": {}, "predefinito": "direzione"}
    n = permessi.normalizza(vecchia)
    assert "pz" in n["profili"]["amministrazione"] and "pz" in n["profili"]["commerciale"]
    assert "pz" not in n["profili"]["personale"]                                          # profilo personalizzato: non si aggiunge da solo
    assert "pz" in n["profili"]["presidente"] and n["noti"] == permessi.TUTTI
    assert permessi.normalizza(n)["profili"]["amministrazione"] == n["profili"]["amministrazione"]   # stabile alle riletture


def _admin(modulo):
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["utente"] = {"username": "root", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = modulo
    return at.run()


def test_strumento_prezziario_si_apre_vuoto_e_con_dati():
    at = _admin("pz")
    assert not at.exception and any("Nessun prezziario" in w.value for w in at.warning)
    righe, _ = pz.da_dataframe(_file())
    pz.salva_prezziario({"anno": 2026, "quad": 2, "nome": "CCIAA"}, righe, "root")
    st_cache = __import__("streamlit").cache_data
    st_cache.clear()
    at = _admin("pz")
    assert not at.exception, [e.value for e in at.exception]
    assert any("2° quadrimestre 2026" in (w.value or "") for w in [*at.warning, *at.success])     # scaduto o in vigore a seconda della data
    at.text_input(key="cerca_testo").set_value("piastrelle").run()
    assert not at.exception and any("1 voci trovate" in m.value for m in at.markdown)


def test_computo_ha_il_selettore_del_prezziario_e_l_hub_lo_mostra():
    at = _admin("pv")
    assert not at.exception, [e.value for e in at.exception]
    at = _admin(None)
    assert not at.exception and any("Prezziario" in b.label for b in at.button)


def test_ordini_salvati_prima_del_prezziario_si_riaprono():
    """Un salvataggio vecchio non ha le colonne Voce e Quantità: la tabella non deve andare in errore."""
    import oa_ui
    df = oa_ui._ord_df([{"Numero": "ODA-2026-001", "Fornitore": "Alfa", "Importo": 100, "Data": "2026-10-01"}])
    assert df["Voce"].tolist() == [""] and list(df.columns) == oa.COLONNE_ORDINI
