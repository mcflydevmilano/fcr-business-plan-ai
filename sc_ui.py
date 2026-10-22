"""sc_ui.py - Interfaccia dello Scadenzario incassi e pagamenti."""
import datetime as dt

import pandas as pd
import streamlit as st
import guida

import charts
import sc
import fatture
import sc_report
import theme
from core import fmt_num
from ui_util import esempi_attivi, senza_esempi, importa_dati, sola_lettura, modello_excel, pannello_archivio, sostituisci_tabella, tabella_modificabile

ss = st.session_state

PARAM_CHIAVI = ("cassa0", "fido", "settimane", "ritardo_attivo_gg", "incasso_scaduti_pct", "pagamento_scaduti_pct")


@senza_esempi
def _esempio():
    oggi = dt.date.today()
    g = lambda n: (oggi + dt.timedelta(days=n)).isoformat()
    righe = [
        ("Attiva", "Condominio Aurora", "Via Verdi", "FA-101", g(-60), g(-30), 48000, 0),
        ("Attiva", "Immobiliare Sole Srl", "Capannone Nord", "FA-118", g(-30), g(0), 35000, 0),
        ("Attiva", "Comune di Esempio", "Scuola Elementare", "FA-124", g(-10), g(20), 120000, 0),
        ("Attiva", "Rossi Costruzioni", "Villa Lago", "FA-130", g(-5), g(25), 60000, 0),
        ("Passiva", "Calcestruzzi Alfa", "Capannone Nord", "F-2201", g(-45), g(-15), 18000, 0),
        ("Passiva", "Elettroimpianti Beta", "Scuola Elementare", "F-2230", g(-20), g(10), 27000, 0),
        ("Passiva", "Ponteggi Gamma", "Villa Lago", "F-2244", g(-10), g(20), 9500, 0),
        ("Passiva", "Stipendi e oneri (stima)", "", "", g(-2), g(12), 42000, 0),
    ]
    return pd.DataFrame([dict(zip(sc.COLONNE_DOC, (t, c, ca, n, d0, s, i, sa))) for t, c, ca, n, d0, s, i, sa in righe], columns=sc.COLONNE_DOC)


def _cfg():
    e, n = sc.ETICHETTE_DOC, st.column_config.NumberColumn
    return {"Tipo": st.column_config.SelectboxColumn(e["Tipo"], options=list(sc.TIPI), required=True),
            "Controparte": st.column_config.TextColumn(e["Controparte"], width="medium"), "Cantiere": st.column_config.TextColumn(e["Cantiere"]),
            "Documento": st.column_config.TextColumn(e["Documento"]), "Data_doc": st.column_config.TextColumn(e["Data_doc"], help="AAAA-MM-GG o GG/MM/AAAA"),
            "Scadenza": st.column_config.TextColumn(e["Scadenza"], help="AAAA-MM-GG o GG/MM/AAAA"),
            "Importo": n(e["Importo"], min_value=0.0, step=100.0, format="%.2f"), "Saldato": n(e["Saldato"], min_value=0.0, step=100.0, format="%.2f")}


def _num(label, key, mn, mx, step, fmt="%.0f"):
    k = "sc_" + key
    if k not in ss:
        ss[k] = type(mn)(sc.SC_DEFAULT[key])
    return st.number_input(label, min_value=mn, max_value=mx, step=step, key=k, format=fmt)


def _params():
    p = {k: ss.get("sc_" + k, sc.SC_DEFAULT[k]) for k in PARAM_CHIAVI}
    p["oggi"] = ss.get("sc_oggi", dt.date.today())
    return p


def _raccogli():
    return {"docs": ss["sc_df"].to_dict("records"), "params": {**_params(), "oggi": None}}


def _applica(p, nome):
    sostituisci_tabella("sc_df", pd.DataFrame(p.get("docs") or [], columns=sc.COLONNE_DOC))
    ss["sc_demo"] = False
    ss["_pending"] = {"sc_" + k: v for k, v in (p.get("params") or {}).items() if k in PARAM_CHIAVI}


def _importa_xml(audit):
    """Fatture elettroniche (FatturaPA) -> righe dello scadenzario."""
    if sola_lettura():
        st.caption("Importazione non disponibile per il ruolo «lettore».")
        return
    st.caption("Carica i file .xml (o .xml.p7m) scaricati dal cassetto fiscale o dal portale delle fatture: le fatture emesse diventano incassi, "
               "quelle ricevute pagamenti. Ogni rata di pagamento diventa una riga con la sua scadenza.")
    up = st.file_uploader("Fatture elettroniche", type=["xml", "p7m"], accept_multiple_files=True, key="xml_fatture")
    if not up:
        return
    lette, nomi = [], []
    for f in up:
        try:
            lette.append(fatture.leggi_fattura(f.getvalue()))
            nomi.append(f.name)
        except ValueError as e:
            st.error(f"{f.name}: {e}")
    if not lette:
        return
    prob = fatture.piva_probabile(lette) or ""
    if not ss.get("xml_piva") and prob:
        ss["xml_piva"] = prob
    piva = st.text_input("Partita IVA della tua azienda", key="xml_piva", help="Serve a distinguere le fatture che hai emesso da quelle che hai ricevuto. Proposta in base ai file caricati.")
    if not piva.strip():
        st.info("Scrivi la tua partita IVA per continuare.")
        return
    righe, avvisi = fatture.righe_scadenzario(lette, piva, nomi)
    demo = bool(ss.get("sc_demo"))
    esistenti = [] if demo else ss["sc_df"].to_dict("records")
    nuove, doppie = fatture.senza_duplicati(righe, esistenti)
    for a in avvisi[:8]:
        st.warning(a)
    if doppie:
        st.caption(f"{doppie} righe già presenti nello scadenzario: saltate.")
    if not nuove:
        st.info("Nessuna riga nuova da importare.")
        return
    st.dataframe(pd.DataFrame(nuove, columns=sc.COLONNE_DOC), hide_index=True, width="stretch")
    st.caption("Il cantiere non è nelle fatture: puoi compilarlo dopo nella tabella. Le righe importate risultano non ancora pagate/incassate.")
    if demo:
        st.caption("I dati di esempio verranno sostituiti.")
    if st.button(f"Importa {len(nuove)} righe", key="xml_importa"):
        base = pd.DataFrame(columns=sc.COLONNE_DOC) if demo else ss["sc_df"]
        sostituisci_tabella("sc_df", pd.concat([base, pd.DataFrame(nuove, columns=sc.COLONNE_DOC)], ignore_index=True))
        ss["sc_demo"] = False
        audit("sc_import_xml", f"{len(nuove)} righe da {len(lette)} file")
        st.rerun()


def _df(df):
    st.dataframe(df, hide_index=True, width="stretch")


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Scadenzario incassi e pagamenti",
                           "Fatture attive e passive, scaduto, solleciti e fabbisogno di cassa settimana per settimana: questa settimana ho cassa?"),
                unsafe_allow_html=True)
    guida.mostra("sc")
    if "sc_df" not in ss:
        ss["sc_df"] = _esempio()
        ss["sc_demo"] = esempi_attivi()
        ss.setdefault("sc_cassa0", 20_000.0 if esempi_attivi() else 0.0)       # valori di esempio: il fido e il saldo reali vanno inseriti dall'utente
        ss.setdefault("sc_fido", 50_000.0 if esempi_attivi() else 0.0)
    pannello_archivio("sc", "lo scadenzario", _raccogli, _applica, audit, utente)
    t1, t2, t3, t4 = st.tabs(["🧾 1. Documenti e Ipotesi", "📅 2. Cassa settimanale", "📨 3. Solleciti", "📄 4. Dossier"])

    with t1:
        if ss.get("sc_demo"):
            st.info("Scadenzario di esempio con date relative a oggi. Sostituiscilo con le tue fatture: modifica la tabella o importa un file.")
            if st.button("Svuota l'esempio e parti da zero"):
                sostituisci_tabella("sc_df", pd.DataFrame(columns=sc.COLONNE_DOC))
                ss["sc_demo"] = False
                st.rerun()
        st.download_button("📥 Scarica il modello Excel per l'import", modello_excel(sc.COLONNE_DOC, sc.ETICHETTE_DOC, _esempio.originale().head(3).to_dict("records")),
                           file_name="modello_scadenzario.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with st.expander("🧾 Importa fatture elettroniche (XML)"):
            _importa_xml(audit)
        with st.expander("📂 Importa dall'export del gestionale o del commercialista"):
            tipo_fisso = st.radio("Tipo dei documenti nel file", ["Leggi dalla colonna Tipo", "Sono tutti incassi (fatture attive)", "Sono tutti pagamenti (fatture passive)"], key="sc_tipo_file")

            def _imposta_tipo(df):
                if tipo_fisso.startswith("Sono tutti incassi"):
                    df["Tipo"] = "Attiva"
                elif tipo_fisso.startswith("Sono tutti pagamenti"):
                    df["Tipo"] = "Passiva"
                return df
            importa_dati("sc_df", sc.COLONNE_DOC, sc.ETICHETTE_DOC, "sc", 1, audit, sc.SINONIMI_DOC, dopo=lambda: ss.__setitem__("sc_demo", False), trasforma=_imposta_tipo)
        st.subheader("Documenti aperti e chiusi di recente")
        st.caption("Tipo «Attiva» = fattura emessa a un cliente (da incassare); «Passiva» = fattura di un fornitore (da pagare). Importi IVA inclusa. "
                   "In «Già incassato / pagato» metti quanto è già stato regolato: il residuo conta solo quello che resta.")
        tabella_modificabile("sc_df", ss["sc_df"], _cfg(), altezza=330)
        st.subheader("Ipotesi di previsione")
        a, b, c = st.columns(3)
        with a:
            st.date_input("Data di riferimento", key="sc_oggi", value=dt.date.today())
            _num("Saldo di conto (€)", "cassa0", -1e9, 1e10, 1_000.0)
        with b:
            _num("Fido disponibile (€)", "fido", 0.0, 1e10, 10_000.0)
            _num("Settimane di previsione", "settimane", 4, 52, 1, "%d")
        with c:
            _num("Ritardo abituale dei clienti (giorni)", "ritardo_attivo_gg", 0, 365, 5, "%d")
            _num("Scaduto attivo incassato in settimana 1 (%)", "incasso_scaduti_pct", 0.0, 100.0, 10.0)
        _num("Scaduto passivo pagato in settimana 1 (%)", "pagamento_scaduti_pct", 0.0, 100.0, 10.0)

    docs, av_n = sc.normalizza_documenti(sc.da_dataframe(ss["sc_df"]))
    p = _params()
    out = sc.calcola_sc(docs, p)
    k = out["kpi"]

    with t2:
        if not docs:
            st.warning("Nessun documento valido: inserisci almeno una fattura con tipo, scadenza e importo.")
        else:
            for x in av_n[:3]:
                st.caption("⚠️ " + x)
            if k["prima_settimana_fuori_fido"]:
                st.error(f"**Attenzione:** dalla settimana {k['prima_settimana_fuori_fido']} lo scoperto supera il fido.")
            elif k["ok_settimana"]:
                st.success(f"**Sì, questa settimana hai cassa.** A fine settimana 1 sul conto restano circa {fmt_num(k['cassa_settimana1'])} €.")
            else:
                st.warning(f"**Questa settimana la cassa va in negativo** ({fmt_num(k['cassa_settimana1'])} €), ma resta dentro il fido.")
            tono = "bad" if k["scaduto_attivo_pct"] > 25 else ("warn" if k["scaduto_attivo_pct"] > 10 else "ok")
            st.markdown(theme.stat_strip([
                {"label": "Da incassare", "value": f"{fmt_num(k['da_incassare'])} €", "sub": "residuo clienti", "tono": "info"},
                {"label": "Da pagare", "value": f"{fmt_num(k['da_pagare'])} €", "sub": "residuo fornitori", "tono": "info"},
                {"label": "Crediti scaduti", "value": f"{fmt_num(k['scaduto_attivo'])} €", "sub": f"{fmt_num(k['scaduto_attivo_pct'], 0)}% dei crediti", "tono": tono},
                {"label": "Scoperto massimo", "value": f"{fmt_num(k['picco_fabbisogno'])} €", "sub": f"settimana {k['settimana_picco']}" if k["settimana_picco"] else "nessuno", "tono": "bad" if k["prima_settimana_fuori_fido"] else ("warn" if k["picco_fabbisogno"] else "ok")},
            ]), unsafe_allow_html=True)
            for a in out["avvisi"]:
                st.warning(a)
            st.pyplot(charts.fig_sc_settimane(out["settimane"], p["fido"] or None, "light"), clear_figure=True)
            c1, c2 = st.columns(2)
            with c1:
                st.pyplot(charts.fig_sc_fasce(out["fasce"], "light"), clear_figure=True)
            with c2:
                st.markdown("**E se i clienti pagano in ritardo?**")
                _df(pd.DataFrame(sc.confronto_ritardi(docs, p)))
            with st.expander("Tabella settimanale"):
                _df(pd.DataFrame([{**r, "Dal": r["Dal"].strftime("%d/%m/%Y"), "Al": r["Al"].strftime("%d/%m/%Y")} for r in out["settimane"]]))

    with t3:
        sol = sc.solleciti(docs, out["params"]["oggi"])
        if not sol:
            st.success("Nessun credito scaduto da sollecitare.")
        else:
            st.caption("Clienti con fatture scadute, dal piu' esposto. Le bozze vanno riviste prima dell'invio; il livello 3 va verificato con il legale.")
            _df(pd.DataFrame([{"Cliente": c["Cliente"], "Totale scaduto": c["Totale scaduto"], "Ritardo max (gg)": c["Ritardo max (gg)"], "Livello": c["Livello"], "Fatture": len(c["Fatture"])} for c in sol]))
            scelta = st.selectbox("Bozza di sollecito per", [c["Cliente"] for c in sol], key="sc_sel_sol")
            c = next(c for c in sol if c["Cliente"] == scelta)
            ogg, corpo = sc.testo_sollecito(c)
            st.text_input("Oggetto", ogg, key=f"sc_ogg_{scelta}")
            st.text_area("Testo", corpo, height=300, key=f"sc_testo_{scelta}")

    with t4:
        if not docs:
            st.info("Aggiungi dei documenti per generare il dossier.")
        else:
            nome = st.text_input("Nome del documento", "Scadenzario", key="sc_nome")
            if st.button("📄 Genera dossier PDF ed Excel", type="primary", key="gen_sc"):
                with st.spinner("Preparo i documenti..."):
                    ctx = sc_report.costruisci_ctx_sc(out, docs, nome)
                    ss["sc_rep"] = {"pdf": sc_report.genera_pdf_sc(ctx), "xlsx": sc_report.genera_excel_sc(ctx), "id": ctx["report_id"]}
                    audit("sc_report", ctx["report_id"])
            rep = ss.get("sc_rep")
            if rep:
                c1, c2 = st.columns(2)
                c1.download_button("📥 Scarica il dossier PDF", rep["pdf"], file_name=f"Scadenzario_{rep['id']}.pdf", mime="application/pdf", width="stretch")
                c2.download_button("📥 Scarica l'Excel con formule", rep["xlsx"], file_name=f"Scadenzario_{rep['id']}.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
        st.caption("Previsione basata sulle fatture inserite: non include stipendi, imposte e rate di finanziamento se non registrati come documenti.")
