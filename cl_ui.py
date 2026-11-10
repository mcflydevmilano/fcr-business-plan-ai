"""cl_ui.py - Interfaccia di «Computo di cantiere»."""
import pandas as pd
import streamlit as st

import cl
import guida
import theme
from core import fmt_num
from ui_util import cantieri_rubrica, pannello_archivio, sola_lettura, sostituisci_tabella, tabella_modificabile

ss = st.session_state
_CAMPI = ("cl_titolo", "cl_cantiere", "cl_et_base", "cl_et_agg")


def _extra():
    return [c for c in ss.get("cl_extra", []) if c]


def _df(righe, extra=()):
    df = pd.DataFrame(righe, columns=list(cl.COLONNE) + list(extra))
    for c in cl.NUMERICHE:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in cl.TESTO + list(extra):
        df[c] = df[c].fillna("").astype(str)
    return df


def _raccogli():
    return {"voci": cl.normalizza(ss["cl_df"].to_dict("records"), _extra()), "extra": _extra(), "campi": {k: ss.get(k) for k in _CAMPI}}


def _applica(p, nome):
    extra = [str(c) for c in (p.get("extra") or [])][:cl.MAX_EXTRA]
    ss["cl_extra"] = extra
    sostituisci_tabella("cl_df", _df(cl.normalizza(p.get("voci"), extra), extra))
    ss["_pending"] = {k: v for k, v in (p.get("campi") or {}).items() if k in _CAMPI and v is not None}


def _euro(v):
    return "€ " + fmt_num(v, 2)


def _scheda_voci():
    extra = _extra()
    if ss["cl_df"].empty:
        st.info("Il computo è vuoto. Scrivi le voci nella tabella oppure importa un Excel.")
    a, b = st.columns(2)
    a.text_input("Titolo del computo", key="cl_titolo", placeholder="es. Via Roma 12 - lavori rimanenti", disabled=sola_lettura())
    cant = [""] + [c["Codice"] for c in cantieri_rubrica() if c.get("Codice")]
    if ss.get("cl_cantiere") not in cant:
        cant.append(ss.get("cl_cantiere") or "")
    b.selectbox("Cantiere della Rubrica (facoltativo)", cant, key="cl_cantiere", disabled=sola_lettura())
    st.caption("Scrivi quantità e prezzo di progetto. Se metti anche **coefficiente**, **prezzario nuovo** e **% di aumento**, il prezzo aggiornato si calcola da solo: "
               "prezzo + (prezzario nuovo − prezzo × coefficiente) × %. Le tre colonne «a mano» servono solo per i casi particolari (voci a corpo, adeguamenti ISTAT): se le lasci vuote calcolo io.")
    cfg = {"Descrizione": st.column_config.TextColumn(width="large"), "Quantità": st.column_config.NumberColumn(format="%.2f"),
           "Prezzo unitario €": st.column_config.NumberColumn(format="%.2f"), "Coefficiente": st.column_config.NumberColumn(format="%.2f", help="Di solito 1,05"),
           "Prezzario nuovo €": st.column_config.NumberColumn(format="%.2f"), "% di aumento": st.column_config.NumberColumn(format="%.2f", help="0,8 = si riconosce l'80% della differenza"),
           "Totale esecutivo a mano €": st.column_config.NumberColumn(format="%.2f", help="Solo per voci a corpo senza quantità e prezzo"),
           "Prezzo aggiornato a mano €": st.column_config.NumberColumn(format="%.2f", help="Lascia vuoto per il calcolo automatico"),
           "Totale aggiornato a mano €": st.column_config.NumberColumn(format="%.2f", help="Lascia vuoto per il calcolo automatico")}
    tabella_modificabile("cl_df", _df([], extra), cfg, altezza=520)
    with st.expander("➕ Aggiungi o togli una colonna"):
        a, b = st.columns([3, 1.3])
        nome = a.text_input("Nome della nuova colonna", key="cl_col_nuova", placeholder="es. Subappaltatore, Stato, Data prevista")
        b.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
        if b.button("Aggiungi colonna", key="cl_col_add", width="stretch", disabled=sola_lettura()):
            nome = " ".join(nome.split())[:40]
            if not nome:
                st.warning("Scrivi il nome della colonna.")
            elif nome in cl.COLONNE or nome in cl.COLONNE_RISULTATO or nome in extra:
                st.warning("Questa colonna c'è già.")
            elif len(extra) >= cl.MAX_EXTRA:
                st.warning(f"Si possono aggiungere al massimo {cl.MAX_EXTRA} colonne.")
            else:
                df = ss["cl_df"].copy()
                df[nome] = ""
                ss["cl_extra"] = extra + [nome]
                sostituisci_tabella("cl_df", df)
                st.rerun()
        if extra:
            a, b = st.columns([3, 1.3])
            via = a.selectbox("Colonna da togliere (si perde il suo contenuto)", extra, key="cl_col_via")
            b.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
            if b.button("Togli colonna", key="cl_col_del", width="stretch", disabled=sola_lettura()):
                ss["cl_extra"] = [c for c in extra if c != via]
                sostituisci_tabella("cl_df", ss["cl_df"].drop(columns=[via]))
                st.rerun()
    with st.expander("📥 Importa da Excel"):
        st.download_button("Scarica il modello Excel", cl.modello_excel(), "modello_computo.xlsx", key="cl_modello")
        f = st.file_uploader("Excel con le colonne del computo", type=["xlsx", "xlsm"], key="cl_up")
        modo = st.radio("Le righe lette…", ["sostituiscono il computo", "si aggiungono in fondo"], horizontal=True, key="cl_modo")
        if f is not None and st.button("Importa", key="cl_importa", disabled=sola_lettura()):
            try:
                righe, nuove, avv = cl.da_excel(f.getvalue(), extra)
            except Exception as e:
                righe, nuove, avv = [], extra, [f"Non riesco a leggere il file: {e}"]
            if righe:
                vecchie = [] if modo.startswith("sost") else cl.normalizza(ss["cl_df"].to_dict("records"), extra)
                ss["cl_extra"] = nuove
                sostituisci_tabella("cl_df", _df(vecchie + righe, nuove))
                st.success(avv[0])
                st.rerun()
            for x in avv:
                st.warning(x)


def _scheda_risultato(out, audit):
    extra = _extra()
    b, a = ss.get("cl_et_base") or "progetto", ss.get("cl_et_agg") or "aggiornato"
    st.markdown(theme.stat_strip([
        {"label": f"Totale {b}", "value": _euro(out["tot_esecutivo"]), "sub": "rimanente da esecutivo", "tono": "info"},
        {"label": f"Totale {a}", "value": _euro(out["tot_aggiornato"]), "sub": "con i prezzi aggiornati", "tono": "ok"},
        {"label": "Differenza", "value": _euro(out["differenza"]), "sub": f"{out['aumento_pct']:+.2f}%".replace(".", ","), "tono": "warn" if out["differenza"] > 0 else "info"},
        {"label": "Voci", "value": str(len(out["righe"])), "sub": "nel computo", "tono": "info"},
    ]), unsafe_allow_html=True)
    for x in out["avvisi"][:5]:
        st.caption("⚠️ " + x)
    c1, c2 = st.columns(2)
    c1.text_input("Come chiamare il totale di progetto", key="cl_et_base", placeholder="es. 2021")
    c2.text_input("Come chiamare il totale aggiornato", key="cl_et_agg", placeholder="es. 2025")
    df = pd.DataFrame(out["righe"], columns=list(cl.COLONNE_RISULTATO) + extra)
    num = [c for c in cl.COLONNE_RISULTATO if c.endswith("€") or c in ("Quantità", "Coefficiente", "% di aumento")]
    st.dataframe(df, hide_index=True, width="stretch", height=520,
                 column_config={**{c: st.column_config.NumberColumn(format="%.2f") for c in num}, "Descrizione": st.column_config.TextColumn(width="large")})
    if len(out["per_capitolo"]) > 1:
        st.markdown("**Per capitolo**")
        st.dataframe(pd.DataFrame(out["per_capitolo"]), hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="%.2f") for c in ("Totale da esecutivo €", "Totale aggiornato €")})
    if st.download_button("⬇️ Scarica il computo in Excel", cl.excel_bytes(cl.normalizza(ss["cl_df"].to_dict("records"), extra), extra, ss.get("cl_titolo") or "Computo", (b, a)),
                          "computo_cantiere.xlsx", key="cl_xl", type="primary"):
        audit("cl_excel", ss.get("cl_titolo") or "")


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Computo di cantiere", "I lavori rimanenti con le colonne del computo del Comune e i prezzi aggiornati al nuovo prezzario."), unsafe_allow_html=True)
    guida.mostra("cl")
    if "cl_df" not in ss:
        ss["cl_df"] = _df([])
    ss.setdefault("cl_extra", [])
    for k in _CAMPI:
        ss.setdefault(k, "")
    pannello_archivio("cl", "il computo", _raccogli, _applica, audit, utente)
    righe = cl.normalizza(ss["cl_df"].to_dict("records"), _extra())
    out = cl.calcola(righe, _extra())
    t1, t2 = st.tabs(["✏️ 1. Voci del computo", "💶 2. Computo con prezzi aggiornati"])
    with t1:
        _scheda_voci()
    with t2:
        if not righe:
            st.info("Aggiungi le voci nella scheda «1».")
        else:
            _scheda_risultato(out, audit)
