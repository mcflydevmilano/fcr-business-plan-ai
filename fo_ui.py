"""fo_ui.py - Interfaccia di Fornitori e subappaltatori."""
import datetime as dt

import pandas as pd
import streamlit as st

import charts
import fo
import ops_report
import theme
from core import fmt_num
from ui_util import banner_esempio, blocco_tabella, pannello_archivio, scarica_dossier, sostituisci_tabella

ss = st.session_state
ICONE = {"ok": "🟢", "warn": "🟡", "bad": "🔴", "nd": "⚪"}


def _esempio():
    g = lambda n: (dt.date.today() + dt.timedelta(days=n)).isoformat()
    docs = [("Calcestruzzi Alfa", "Fornitore", "DURC", g(-5)), ("Calcestruzzi Alfa", "Fornitore", "Visura camerale", g(200)), ("Elettroimpianti Beta", "Subappaltatore", "DURC", g(12)),
            ("Elettroimpianti Beta", "Subappaltatore", "Assicurazione RCT/RCO", g(180)), ("Elettroimpianti Beta", "Subappaltatore", "Idoneità tecnico-professionale", g(300)),
            ("Ponteggi Gamma", "Subappaltatore", "DURC", g(150)), ("Ponteggi Gamma", "Subappaltatore", "Assicurazione RCT/RCO", g(20))]
    contr = [("Calcestruzzi Alfa", "Villa Lago", "Fornitura calcestruzzo", 80000, 60000, 40000), ("Elettroimpianti Beta", "Scuola Elementare", "Impianti elettrici", 110000, 120000, 110000),
             ("Ponteggi Gamma", "Villa Lago", "Noleggio ponteggi", 25000, 9500, 0)]
    off = [("Impianto idraulico Scuola", "Idraulica Delta", 38000), ("Impianto idraulico Scuola", "Elettroimpianti Beta", 41000), ("Impianto idraulico Scuola", "Calcestruzzi Alfa", 35500),
           ("Serramenti Villa", "Infissi Omega", 22000), ("Serramenti Villa", "Falegnameria Sigma", 24500)]
    mk = lambda cols, rows: pd.DataFrame([dict(zip(cols, r)) for r in rows], columns=cols)
    return mk(fo.COLONNE_DOCFO, docs), mk(fo.COLONNE_CONTR, contr), mk(fo.COLONNE_OFF, off)


def _cfg():
    n, t = st.column_config.NumberColumn, st.column_config.TextColumn
    a, b, c = fo.ETICHETTE_DOCFO, fo.ETICHETTE_CONTR, fo.ETICHETTE_OFF
    return ({"Fornitore": t(a["Fornitore"], width="medium"), "Tipo": st.column_config.SelectboxColumn(a["Tipo"], options=fo.TIPI), "Documento": t(a["Documento"], width="medium"),
             "Scadenza": t(a["Scadenza"], help="AAAA-MM-GG o GG/MM/AAAA")},
            {"Fornitore": t(b["Fornitore"]), "Commessa": t(b["Commessa"]), "Descrizione": t(b["Descrizione"]), "Importo": n(b["Importo"], min_value=0.0, step=1000.0, format="%.0f"),
             "Fatturato": n(b["Fatturato"], min_value=0.0, step=500.0, format="%.0f"), "Pagato": n(b["Pagato"], min_value=0.0, step=500.0, format="%.0f")},
            {"Voce": t(c["Voce"], width="medium"), "Fornitore": t(c["Fornitore"]), "Importo": n(c["Importo"], min_value=0.0, step=500.0, format="%.0f")})


def _raccogli():
    return {"docs": ss["fo_doc"].to_dict("records"), "contratti": ss["fo_contr"].to_dict("records"), "offerte": ss["fo_off"].to_dict("records"),
            "params": {"preavviso_gg": ss.get("fo_preavviso_gg", fo.FO_DEFAULT["preavviso_gg"])}}


def _applica(p, nome):
    for chiave, cols, k in (("fo_doc", fo.COLONNE_DOCFO, "docs"), ("fo_contr", fo.COLONNE_CONTR, "contratti"), ("fo_off", fo.COLONNE_OFF, "offerte")):
        sostituisci_tabella(chiave, pd.DataFrame(p.get(k) or [], columns=cols))
    ss["fo_demo"] = False
    ss["_pending"] = {"fo_preavviso_gg": (p.get("params") or {}).get("preavviso_gg", fo.FO_DEFAULT["preavviso_gg"])}


def _dati():
    d, a1 = fo.normalizza_docfo(ss["fo_doc"].to_dict("records"))
    c, a2 = fo.normalizza_contratti(ss["fo_contr"].to_dict("records"))
    o, a3 = fo.normalizza_offerte(ss["fo_off"].to_dict("records"))
    return d, c, o, a1 + a2 + a3


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Fornitori e subappaltatori", "Documenti in scadenza, contratti e ordini aperti, e il confronto dei preventivi."), unsafe_allow_html=True)
    if "fo_doc" not in ss:
        ss["fo_doc"], ss["fo_contr"], ss["fo_off"] = _esempio()
        ss["fo_demo"] = True
    pannello_archivio("fo", "i fornitori", _raccogli, _applica, audit, utente)
    t1, t2, t3, t4 = st.tabs(["🧾 1. Dati", "🔎 2. Controllo", "⚖️ 3. Confronto preventivi", "📄 4. Dossier"])
    cd, cc, co = _cfg()
    with t1:
        banner_esempio("fo_demo", [("fo_doc", fo.COLONNE_DOCFO), ("fo_contr", fo.COLONNE_CONTR), ("fo_off", fo.COLONNE_OFF)], "svuota_fo")
        blocco_tabella("fo_doc", "Documenti dei fornitori", "Una riga per documento (DURC, assicurazione, SOA...) con la sua scadenza.", fo.COLONNE_DOCFO, fo.ETICHETTE_DOCFO, cd, ss["fo_doc"], "fo", 1, audit, 260, fo.SINONIMI_DOCFO)
        a, b, c = st.columns([2, 2, 1])
        nuovo = a.text_input("Nuovo fornitore: aggiungi i documenti standard", key="fo_nuovo_nome", placeholder="Ragione sociale")
        tipo = b.selectbox("Tipo", fo.TIPI, key="fo_nuovo_tipo")
        c.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
        if c.button("➕ Aggiungi", key="agg_fo", width="stretch") and nuovo.strip():
            nuovi = pd.DataFrame([{"Fornitore": nuovo.strip(), "Tipo": tipo, "Documento": d, "Scadenza": ""} for d in fo.DOCUMENTI_TIPO[:4]], columns=fo.COLONNE_DOCFO)
            sostituisci_tabella("fo_doc", pd.concat([ss["fo_doc"], nuovi], ignore_index=True) if len(ss["fo_doc"]) else nuovi)
            st.rerun()
        blocco_tabella("fo_contr", "Contratti e ordini", "Importi IVA esclusa. «Fatturato» e «Pagato» sono i valori finora.", fo.COLONNE_CONTR, fo.ETICHETTE_CONTR, cc, ss["fo_contr"], "fo", 2, audit, 220)
        blocco_tabella("fo_off", "Preventivi da confrontare", "Una riga per ogni offerta ricevuta; stessa «voce» per le offerte da confrontare.", fo.COLONNE_OFF, fo.ETICHETTE_OFF, co, ss["fo_off"], "fo", 3, audit, 220)
        ss.setdefault("fo_preavviso_gg", int(fo.FO_DEFAULT["preavviso_gg"]))
        st.subheader("Ipotesi")
        a, b = st.columns(2)
        a.date_input("Data di riferimento", key="fo_oggi", value=dt.date.today())
        b.number_input("Preavviso scadenze (giorni)", 0, 180, step=5, key="fo_preavviso_gg")

    docs, contr, off, av_n = _dati()
    out = fo.calcola_fo(docs, contr, off, {"oggi": ss.get("fo_oggi", dt.date.today()), "preavviso_gg": ss.get("fo_preavviso_gg", 30)})
    k = out["kpi"]

    with t2:
        if not out["fornitori"]:
            st.warning("Nessun dato: inserisci almeno un documento o un contratto.")
        else:
            for x in av_n[:3]:
                st.caption("⚠️ " + x)
            if k["forn_critici"]:
                st.error(f"**{k['forn_critici']} fornitori con documenti scaduti.**")
            elif k["doc_in_scadenza"]:
                st.warning(f"**{k['doc_in_scadenza']} documenti in scadenza.**")
            else:
                st.success("**Tutti i documenti sono in regola.**")
            st.markdown(theme.stat_strip([
                {"label": "Documenti scaduti", "value": str(k["doc_scaduti"]), "sub": f"{k['forn_critici']} fornitori critici", "tono": "bad" if k["doc_scaduti"] else "ok"},
                {"label": "In scadenza", "value": str(k["doc_in_scadenza"]), "sub": "entro il preavviso", "tono": "warn" if k["doc_in_scadenza"] else "ok"},
                {"label": "Ordini aperti", "value": f"{fmt_num(k['residuo'])} €", "sub": f"impegnato {fmt_num(k['impegnato'])} €", "tono": "info"},
                {"label": "Da pagare", "value": f"{fmt_num(k['da_pagare'])} €", "sub": f"{k['sovrafatturati']} sovrafatturati", "tono": "warn" if k["sovrafatturati"] else "info"}]), unsafe_allow_html=True)
            for a in out["avvisi"][:8]:
                st.warning(a)
            c1, c2 = st.columns([2, 3])
            c1.pyplot(charts.fig_scadenze({"bad": k["doc_scaduti"], "warn": k["doc_in_scadenza"], "ok": k["doc_ok"]}, "Documenti dei fornitori", "light"), clear_figure=True)
            c2.dataframe(pd.DataFrame([{"Fornitore": f["Fornitore"], "Stato": ICONE[f["Stato"]], "Scaduti": f["Scaduti"], "In scadenza": f["In scadenza"], "Contratti": f["Contratti"], "Residuo ordine": f["Residuo ordine"],
                                        "Da pagare": f["Da pagare"]} for f in out["fornitori"]]).round(0), hide_index=True, width="stretch")
            st.markdown("**Documenti da rinnovare**")
            ren = [{"Fornitore": d["Fornitore"], "Documento": d["Documento"], "Scadenza": d["Scadenza"], "Giorni": d["Giorni"], "Stato": ICONE[d["Stato"]] + " " + ("Scaduto" if d["Stato"] == "bad" else "In scadenza")}
                   for d in sorted(out["documenti"], key=lambda x: (x["Giorni"] is None, x["Giorni"] or 0)) if d["Stato"] in ("bad", "warn")]
            st.dataframe(pd.DataFrame(ren), hide_index=True, width="stretch") if ren else st.success("Nessun documento da rinnovare.")

    with t3:
        if not out["confronto"]:
            st.info("Inserisci almeno due offerte per la stessa voce.")
        else:
            st.caption("Per ogni voce: l'offerta più bassa e la più bassa tra i fornitori con i documenti in regola.")
            st.dataframe(pd.DataFrame(out["confronto"]).round(1), hide_index=True, width="stretch")
            st.metric("Risparmio potenziale rispetto alla media", f"{fmt_num(k['risparmio_potenziale'])} €")

    with t4:
        if not out["fornitori"]:
            st.info("Aggiungi dei dati per generare il dossier.")
        else:
            scarica_dossier("fo", lambda n: ops_report.report_fo(out, n), "Fornitori", audit, "Fornitori e subappaltatori")
        st.caption("Promemoria: la regolarità dei fornitori va verificata sui documenti originali.")
