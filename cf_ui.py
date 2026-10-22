"""cf_ui.py - Interfaccia del modulo Cash Flow di cantiere."""

import pandas as pd
import streamlit as st
import guida

import cf
import cf_report
import charts
import theme
from core import fmt_num
from ui_util import esempi_attivi, modello_excel, pannello_archivio, sostituisci_tabella, tabella_modificabile

ss = st.session_state


def _num(label, key, mn, mx, step, help=None, fmt="%.0f"):
    k = "cf_" + key
    if k not in ss:
        ss[k] = type(mn)(cf.CF_DEFAULT[key])
    return st.number_input(label, min_value=mn, max_value=mx, step=step, key=k, help=help, format=fmt)


def _params():
    return {k: ss.get("cf_" + k, v) for k, v in cf.CF_DEFAULT.items() if k in ("mesi", "cassa0", "fido", "tasso_scoperto", "costi_generali", "gg_pagamento")}


def _cfg():
    n, e = st.column_config.NumberColumn, cf.ETICHETTE_COLONNE
    return {"Cantiere": st.column_config.TextColumn(e["Cantiere"]), "Contratto": n(e["Contratto"], min_value=0.0, step=1000.0, format="%.0f"),
            "Inizio": n(e["Inizio"], min_value=1, step=1, format="%d"), "Durata": n(e["Durata"], min_value=1, step=1, format="%d"),
            "Anticipo_pct": n(e["Anticipo_pct"], min_value=0.0, max_value=100.0, step=5.0, format="%.0f"),
            "Saldo_pct": n(e["Saldo_pct"], min_value=0.0, max_value=100.0, step=5.0, format="%.0f"),
            "Gg_incasso": n(e["Gg_incasso"], min_value=0, step=15, format="%d"),
            "Costi_pct": n(e["Costi_pct"], min_value=0.0, max_value=200.0, step=1.0, format="%.1f")}


def _df(df):
    st.dataframe(df, hide_index=True, width="stretch")


def _fig(fig):
    st.pyplot(fig, clear_figure=True)


def _raccogli():
    return {"cantieri": ss["cf_df"].to_dict("records"), "params": _params(), "nome": ss.get("cf_nome", "")}


def _applica(p, nome):
    sostituisci_tabella("cf_df", pd.DataFrame(p.get("cantieri") or [], columns=cf.COLONNE_CANTIERI))
    ss["cf_demo"] = False
    ss["_pending"] = {"cf_" + k: v for k, v in (p.get("params") or {}).items() if k in cf.CF_DEFAULT}
    ss["_pending"]["cf_nome"] = p.get("nome") or nome


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Cash Flow di cantiere",
                           "Liquidità del portafoglio cantieri: incassi, pagamenti, cassa mese per mese, fabbisogno di fido e stress test."),
                unsafe_allow_html=True)
    guida.mostra("cf")
    if "cf_df" not in ss:
        ss["cf_df"] = pd.DataFrame(cf.genera_portafoglio(100, 5_000_000, 1, 12, 3, 50, 50, 30, 75.0) if esempi_attivi() else [], columns=cf.COLONNE_CANTIERI)
        ss["cf_demo"] = esempi_attivi()
    pannello_archivio("cf", "il portafoglio", _raccogli, _applica, audit, utente)
    t1, t2, t3, t4 = st.tabs(["🏗️ 1. Portafoglio e Ipotesi", "💶 2. Cash Flow", "🧪 3. Stress e Soluzioni", "📄 4. Dossier"])

    with t1:
        st.subheader("Genera un portafoglio")
        st.caption("Crea n cantieri uguali con partenze distribuite nel tempo; poi modifica la tabella riga per riga. Importi IVA esclusa.")
        with st.form("cf_gen"):
            a, b, c = st.columns(3)
            n = a.number_input("Numero di cantieri", 1, 1000, 100, 1)
            tot = a.number_input("Ricavi totali (€)", 0.0, 1e10, 5_000_000.0, 100_000.0, format="%.0f")
            costi = a.number_input("Costi diretti (% del contratto)", 0.0, 150.0, 75.0, 1.0)
            m1 = b.number_input("Primo mese di inizio", 1, 60, 1, 1)
            m2 = b.number_input("Ultimo mese di inizio", 1, 60, 12, 1)
            dur = b.number_input("Durata di ogni cantiere (mesi)", 1, 60, 3, 1)
            ant = c.number_input("Anticipo alla partenza (%)", 0.0, 100.0, 50.0, 5.0)
            sal = c.number_input("Saldo a fine lavori (%)", 0.0, 100.0, 50.0, 5.0)
            gg = c.number_input("Giorni di incasso", 0, 365, 30, 15)
            if st.form_submit_button("Genera il portafoglio"):
                if ant + sal > 100:
                    st.error("Anticipo + saldo non possono superare il 100%.")
                else:
                    sostituisci_tabella("cf_df", pd.DataFrame(cf.genera_portafoglio(int(n), tot, int(m1), int(max(m1, m2)), int(dur), ant, sal, int(gg), costi),
                                                              columns=cf.COLONNE_CANTIERI))
                    ss["cf_demo"] = False
                    audit("cf_genera", f"{int(n)} cantieri, {tot:.0f} EUR")
                    st.rerun()
        st.download_button("📥 Scarica il modello Excel per l'import", modello_excel(cf.COLONNE_CANTIERI, cf.ETICHETTE_COLONNE, cf.genera_portafoglio(3, 150000, 1, 3, 3, 50, 50, 30, 75.0)),
                           file_name="modello_cantieri.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        up = st.file_uploader("…oppure importa da Excel/CSV (colonne: " + ", ".join(cf.COLONNE_CANTIERI) + ")", type=["xlsx", "csv"], key="up_cf")
        if up is not None and st.button("Importa il file"):
            try:
                d = pd.read_csv(up, sep=None, engine="python") if up.name.lower().endswith(".csv") else pd.read_excel(up)
                inv = {v.lower(): k for k, v in cf.ETICHETTE_COLONNE.items()}
                inv.update({k.lower(): k for k in cf.COLONNE_CANTIERI})
                d = d.rename(columns={c: inv.get(str(c).strip().lower(), c) for c in d.columns})
                puliti, av = cf.normalizza_cantieri(cf.da_dataframe(d))
                if not puliti:
                    st.error("Nessun cantiere valido nel file (serve almeno la colonna 'Contratto').")
                else:
                    sostituisci_tabella("cf_df", pd.DataFrame(puliti, columns=cf.COLONNE_CANTIERI))
                    ss["cf_demo"] = False
                    audit("cf_import", up.name)
                    for x in av[:5]:
                        st.warning(x)
                    st.rerun()
            except Exception as e:
                st.error(f"File non leggibile: {e}")
        if ss.get("cf_demo"):
            st.info("Portafoglio di esempio: 100 cantieri, 5 milioni di ricavi, 50% di anticipo e 50% a fine lavori. Modificalo o generane uno tuo.")
        st.subheader("Cantieri")
        tabella_modificabile("cf_df", ss["cf_df"], _cfg(), altezza=320)
        st.subheader("Ipotesi finanziarie")
        a, b, c = st.columns(3)
        with a:
            _num("Orizzonte (mesi)", "mesi", 6, 60, 1)
            _num("Cassa iniziale (€)", "cassa0", 0.0, 1e10, 10_000.0)
        with b:
            _num("Fido disponibile (€)", "fido", 0.0, 1e10, 50_000.0)
            _num("Tasso sullo scoperto (% annuo)", "tasso_scoperto", 0.0, 30.0, 0.5, fmt="%.1f")
        with c:
            _num("Costi generali mensili (€)", "costi_generali", 0.0, 1e9, 1_000.0)
            _num("Giorni di pagamento fornitori", "gg_pagamento", 0, 365, 15)

    cantieri, av_norm = cf.normalizza_cantieri(cf.da_dataframe(ss["cf_df"]))
    p = _params()
    out = cf.calcola_cf(cantieri, p)
    k = out["kpi"]
    stress = cf.stress_cf(cantieri, p) if cantieri else {}

    with t2:
        if not cantieri:
            st.warning("Nessun cantiere valido: inserisci almeno una riga con un contratto.")
        else:
            tono = "bad" if k["primo_mese_fuori_fido"] else ("warn" if k["picco_fabbisogno"] > 0 else "ok")
            st.markdown(theme.stat_strip([
                {"label": "Contratti", "value": f"{fmt_num(k['contratti'])} €", "sub": f"{k['n_cantieri']} cantieri", "tono": "info"},
                {"label": "Margine lordo", "value": f"{fmt_num(k['margine_lordo'])} €", "sub": f"{fmt_num(k['margine_lordo_pct'], 1)}%", "tono": "ok"},
                {"label": "Picco di fabbisogno", "value": f"{fmt_num(k['picco_fabbisogno'])} €", "sub": f"mese {k['mese_picco']}" if k["mese_picco"] else "nessuno scoperto", "tono": tono},
                {"label": "Cassa finale", "value": f"{fmt_num(k['cassa_finale'])} €", "sub": f"dopo {k['mesi']} mesi", "tono": "info"},
            ]), unsafe_allow_html=True)
            for a in out["avvisi"]:
                (st.error if k["primo_mese_fuori_fido"] and "supera il fido" in a else st.warning)(a)
            _fig(charts.fig_cf_mensile(out["mesi"], p["fido"] or None, "light"))
            _fig(charts.fig_cf_crediti(out["mesi"], "light"))
            with st.expander("Tabella mensile", expanded=False):
                _df(pd.DataFrame(out["mesi"]))
            with st.expander("Dettaglio per cantiere", expanded=False):
                _df(pd.DataFrame(out["cantieri"]))

    with t3:
        if not cantieri:
            st.info("Aggiungi dei cantieri per vedere gli stress test.")
        else:
            st.subheader("Cosa succede se le cose vanno peggio")
            _df(pd.DataFrame(cf.confronto_stress(stress)))
            _fig(charts.fig_cf_stress(stress, p["fido"] or None, "light"))
            st.subheader("Quanto anticipo serve?")
            sogg = st.number_input("Scoperto massimo accettabile (€)", 0.0, 1e10, float(p["fido"]), 50_000.0, key="cf_soglia", format="%.0f")
            am = cf.anticipo_minimo(cantieri, p, sogg)
            if am is None:
                st.error("Neanche con il 100% di anticipo si rispetta questa soglia: i costi generali e i pagamenti superano la liquidità disponibile.")
            else:
                st.success(f"Con un anticipo del **{am}%** su tutti i cantieri (saldo ridotto di conseguenza) lo scoperto massimo resta entro {fmt_num(sogg)} €.")

    with t4:
        if not cantieri:
            st.info("Aggiungi dei cantieri per generare il dossier.")
        else:
            nome = st.text_input("Nome del portafoglio", "Portafoglio cantieri", key="cf_nome")
            if st.button("📄 Genera dossier PDF ed Excel", type="primary"):
                with st.spinner("Preparo i documenti..."):
                    ctx = cf_report.costruisci_ctx_cf(out, stress, nome)
                    ss["cf_rep"] = {"pdf": cf_report.genera_pdf_cf(ctx), "xlsx": cf_report.genera_excel_cf(ctx), "id": ctx["report_id"]}
                    audit("cf_report", ctx["report_id"])
            rep = ss.get("cf_rep")
            if rep:
                c1, c2 = st.columns(2)
                c1.download_button("📥 Scarica il dossier PDF", rep["pdf"], file_name=f"CashFlow_{rep['id']}.pdf", mime="application/pdf", width="stretch")
                c2.download_button("📥 Scarica l'Excel con formule", rep["xlsx"], file_name=f"CashFlow_{rep['id']}.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
                st.caption("Il dossier riflette i dati al momento della generazione: rigeneralo dopo ogni modifica.")
        st.caption("Modello semplificato: importi IVA esclusa, avanzamento lineare, nessuna trattenuta di garanzia. Proiezione, non garanzia di risultato.")
