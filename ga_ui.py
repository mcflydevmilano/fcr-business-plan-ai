"""ga_ui.py - Interfaccia di Gare e offerte."""
import datetime as dt

import pandas as pd
import streamlit as st

import charts
import ga
import ops_report
import sl
import theme
from core import fmt_num
from ui_util import banner_esempio, blocco_tabella, scarica_dossier, sostituisci_tabella, sola_lettura

ss = st.session_state
PARAM_CHIAVI = ("margine_target", "preavviso_gg")


def _esempio():
    g = lambda n: (dt.date.today() + dt.timedelta(days=n)).isoformat()
    gare = [("Scuola Primaria Via Roma", "Comune di Esempio", 1_200_000, g(6), "In preparazione", 12, 80, 30, 2500), ("Ristrutturazione Palazzo Civico", "Comune di Esempio", 650_000, g(20), "Da valutare", 15, 84, 25, 1500),
            ("Messa in sicurezza Ponte", "Provincia", 900_000, g(-4), "Da valutare", 10, 86, 20, 2000), ("Riqualificazione Piazza", "Comune di Prova", 400_000, g(-30), "Presentata", 14, 82, 35, 1200),
            ("Capannone Logistica", "Privato Srl", 750_000, g(-90), "Vinta", 8, 80, 100, 0), ("Strada Provinciale 12", "Provincia", 520_000, g(-120), "Persa", 18, 83, 0, 0)]
    docs = [("Scuola Primaria Via Roma", "DGUE", g(3), True), ("Scuola Primaria Via Roma", "Garanzia provvisoria", g(4), False), ("Scuola Primaria Via Roma", "Offerta economica", g(5), False),
            ("Ristrutturazione Palazzo Civico", "Sopralluogo", g(10), False), ("Messa in sicurezza Ponte", "DGUE", g(-6), False)]
    return (pd.DataFrame([dict(zip(ga.COLONNE_GARE, r)) for r in gare], columns=ga.COLONNE_GARE), pd.DataFrame([dict(zip(ga.COLONNE_DOC, r)) for r in docs], columns=ga.COLONNE_DOC))


def _cfg():
    n, t = st.column_config.NumberColumn, st.column_config.TextColumn
    e, d = ga.ETICHETTE_GARE, ga.ETICHETTE_DOC
    gare = {"Gara": t(e["Gara"], width="medium"), "Ente": t(e["Ente"]), "Importo_base": n(e["Importo_base"], min_value=0.0, step=10000.0, format="%.0f"),
            "Scadenza": t(e["Scadenza"], help="AAAA-MM-GG o GG/MM/AAAA"), "Stato": st.column_config.SelectboxColumn(e["Stato"], options=ga.STATI_GARA, required=True),
            "Ribasso_pct": n(e["Ribasso_pct"], min_value=0.0, max_value=60.0, step=0.5, format="%.1f"), "Costi_pct": n(e["Costi_pct"], min_value=0.0, max_value=150.0, step=0.5, format="%.1f"),
            "Probabilita_pct": n(e["Probabilita_pct"], min_value=0.0, max_value=100.0, step=5.0, format="%.0f"), "Costo_partecipazione": n(e["Costo_partecipazione"], min_value=0.0, step=100.0, format="%.0f")}
    doc = {"Gara": t(d["Gara"], width="medium"), "Documento": t(d["Documento"], width="medium"), "Scadenza": t(d["Scadenza"], help="AAAA-MM-GG o GG/MM/AAAA"), "Fatto": st.column_config.CheckboxColumn(d["Fatto"])}
    return gare, doc


def _params():
    p = {k: ss.get("ga_" + k, v) for k, v in ga.GA_DEFAULT.items() if k in PARAM_CHIAVI}
    p["oggi"] = ss.get("ga_oggi", dt.date.today())
    return p


def _raccogli():
    return {"gare": ss["ga_gare"].to_dict("records"), "doc": ss["ga_doc"].to_dict("records"), "params": {k: ss.get("ga_" + k, ga.GA_DEFAULT[k]) for k in PARAM_CHIAVI}}


def _applica(p, nome):
    sostituisci_tabella("ga_gare", pd.DataFrame(p.get("gare") or [], columns=ga.COLONNE_GARE))
    sostituisci_tabella("ga_doc", pd.DataFrame(p.get("doc") or [], columns=ga.COLONNE_DOC))
    ss["ga_demo"] = False
    ss["_pending"] = {"ga_" + k: v for k, v in (p.get("params") or {}).items() if k in PARAM_CHIAVI}


def _dati():
    gare, a1 = ga.normalizza_gare(ss["ga_gare"].to_dict("records"))
    doc, a2 = ga.normalizza_doc(ss["ga_doc"].to_dict("records"), {g["Gara"] for g in gare})
    return gare, doc, a1 + a2


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Gare e offerte", "Quali gare conviene fare, con quale ribasso, e cosa manca prima della scadenza."), unsafe_allow_html=True)
    if "ga_gare" not in ss:
        ss["ga_gare"], ss["ga_doc"] = _esempio()
        ss["ga_demo"] = True
    from ui_util import pannello_archivio
    pannello_archivio("ga", "le gare", _raccogli, _applica, audit, utente)
    t1, t2, t3, t4 = st.tabs(["🏛️ 1. Gare e Documenti", "📊 2. Valutazione", "🔗 3. Integrazioni", "📄 4. Dossier"])
    cg, cd = _cfg()
    with t1:
        banner_esempio("ga_demo", [("ga_gare", ga.COLONNE_GARE), ("ga_doc", ga.COLONNE_DOC)], "svuota_ga")
        blocco_tabella("ga_gare", "Gare", "Importi IVA esclusa. «Costi stimati» = costi diretti e oneri in % dell'importo a base di gara; «Ribasso offerto» è quello che pensi di offrire.",
                       ga.COLONNE_GARE, ga.ETICHETTE_GARE, cg, ss["ga_gare"], "ga", 1, audit, 260, ga.SINONIMI_GARE)
        blocco_tabella("ga_doc", "Documenti richiesti", "Una riga per documento da preparare; spunta «Fatto» quando è pronto.", ga.COLONNE_DOC, ga.ETICHETTE_DOC, cd, ss["ga_doc"], "ga", 2, audit, 240)
        nomi = [g["Gara"] for g in _dati()[0]]
        if nomi:
            a, b = st.columns([3, 1])
            sel = a.selectbox("Aggiungi la check-list standard a", nomi, key="ga_sel_chk")
            b.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
            if b.button("➕ Aggiungi", key="chk_ga", width="stretch"):
                att = ss["ga_doc"]
                gia = set(att[att["Gara"] == sel]["Documento"].astype(str)) if len(att) else set()
                nuovi = pd.DataFrame([{"Gara": sel, "Documento": d, "Scadenza": "", "Fatto": False} for d in ga.CHECKLIST if d not in gia], columns=ga.COLONNE_DOC)
                if len(nuovi):
                    sostituisci_tabella("ga_doc", pd.concat([att, nuovi], ignore_index=True) if len(att) else nuovi)
                    st.rerun()
        st.subheader("Ipotesi")
        a, b, c = st.columns(3)
        a.date_input("Data di riferimento", key="ga_oggi", value=dt.date.today())
        ss.setdefault("ga_margine_target", float(ga.GA_DEFAULT["margine_target"]))
        ss.setdefault("ga_preavviso_gg", int(ga.GA_DEFAULT["preavviso_gg"]))
        b.number_input("Margine obiettivo (% sull'offerta)", 0.0, 50.0, step=1.0, key="ga_margine_target")
        c.number_input("Allarme scadenza (giorni prima)", 0, 90, step=1, key="ga_preavviso_gg")

    gare, doc, av_n = _dati()
    out = ga.calcola_ga(gare, doc, _params())
    k, det, q = out["kpi"], out["gare"], out["params"]

    with t2:
        if not det:
            st.warning("Nessuna gara valida: inserisci almeno una gara con nome e importo a base.")
        else:
            for x in av_n[:3]:
                st.caption("⚠️ " + x)
            if k["scadute"] or k["n_bad"]:
                st.error(f"**{k['n_bad']} gare critiche**: scadenze superate o documenti mancanti a ridosso della scadenza.")
            elif k["n_warn"]:
                st.warning(f"**{k['n_warn']} gare da seguire.**")
            else:
                st.success("**Nessuna gara in ritardo.**")
            tasso = "n.d." if k["tasso_successo"] is None else f"{fmt_num(k['tasso_successo'], 0)}%"
            st.markdown(theme.stat_strip([
                {"label": "Pipeline ponderata", "value": f"{fmt_num(k['ponderato'])} €", "sub": f"{k['n_aperte']} gare aperte", "tono": "info"},
                {"label": "Valore atteso", "value": f"{fmt_num(k['valore_atteso'])} €", "sub": "margine × probabilità", "tono": "ok" if k["valore_atteso"] > 0 else "bad"},
                {"label": "Scadenze vicine", "value": str(k["in_scadenza"] + k["scadute"]), "sub": f"{k['scadute']} già scadute", "tono": "bad" if k["scadute"] else ("warn" if k["in_scadenza"] else "ok")},
                {"label": "Tasso di successo", "value": tasso, "sub": f"{k['vinte']} vinte · {k['perse']} perse", "tono": "info"}]), unsafe_allow_html=True)
            for a in out["avvisi"][:6]:
                st.warning(a)
            st.pyplot(charts.fig_ga_gare(det, q["margine_target"], "light"), clear_figure=True)
            tab = pd.DataFrame([{"Gara": d["Gara"], "Stato": {"ok": "🟢", "warn": "🟡", "bad": "🔴"}[d["Stato"]] + " " + d["Stato gara"], "Offerta": d["Offerta"], "Margine %": d["Margine %"], "Ribasso max %": d["Ribasso massimo %"],
                                 "Valore atteso": d["Valore atteso"], "Scadenza": d["Scadenza"], "Giorni": d["Giorni"], "Doc. mancanti": d["Documenti mancanti"], "Consiglio": d["Consiglio"]} for d in det])
            st.dataframe(tab.round(1), hide_index=True, width="stretch")
            st.subheader("Simulatore del ribasso")
            sel = st.selectbox("Gara", [d["Gara"] for d in det], key="ga_sim_gara")
            d = next(x for x in det if x["Gara"] == sel)
            r = st.slider("Ribasso da offrire (%)", 0.0, 40.0, float(min(40.0, d["Ribasso %"])), 0.5, key=f"ga_sim_{sel}")
            off = d["Importo base"] * (1 - r / 100.0)
            mar = off - d["Costi stimati"]
            c1, c2, c3 = st.columns(3)
            c1.metric("Offerta", f"{fmt_num(off)} €")
            c2.metric("Margine", f"{fmt_num(mar)} €", f"{fmt_num(mar / off * 100 if off else 0, 1)}%")
            c3.metric("Ribasso massimo per il margine obiettivo", f"{fmt_num(d['Ribasso massimo %'], 1)}%")
            if d["Ribasso massimo %"] < 0:
                st.error("Con questi costi anche l'importo a base non raggiunge il margine obiettivo.")
            elif r > d["Ribasso massimo %"]:
                st.warning("Oltre questo ribasso il margine scende sotto l'obiettivo.")

    with t3:
        st.caption("Le gare **vinte** diventano commesse in SAL e contabilità lavori (contratto = offerta, costi preventivati = costi stimati). Quelle già presenti non vengono toccate.")
        vinte = ga.per_commesse(out, gare)
        st.write(f"Gare vinte pronte da inviare: **{len(vinte)}**")
        if st.button("📐 Invia le gare vinte a SAL e contabilità", key="to_sl_ga", disabled=not vinte or sola_lettura()):
            if "sl_com" not in ss:
                ss["sl_com"], ss["sl_sal"], ss["sl_cos"] = (pd.DataFrame(columns=c) for c in (sl.COLONNE_COMMESSE, sl.COLONNE_SAL, sl.COLONNE_COSTI))
                ss["sl_demo"] = False
            att = ss["sl_com"]
            if ss.get("sl_demo"):
                for chiave, cols in (("sl_com", sl.COLONNE_COMMESSE), ("sl_sal", sl.COLONNE_SAL), ("sl_cos", sl.COLONNE_COSTI)):
                    sostituisci_tabella(chiave, pd.DataFrame(columns=cols))
                ss["sl_demo"] = False
                att = ss["sl_com"]
            gia = set(att["Commessa"].astype(str)) if len(att) else set()
            nuove = pd.DataFrame([r for r in vinte if r["Commessa"] not in gia], columns=sl.COLONNE_COMMESSE)
            if len(nuove):
                sostituisci_tabella("sl_com", pd.concat([att, nuove], ignore_index=True) if len(att) else nuove)
            audit("ga_to_sl", str(len(nuove)))
            st.success(f"Aggiunte {len(nuove)} commesse. Completa in SAL date di inizio/fine, ritenuta e anticipo.")

    with t4:
        if not det:
            st.info("Aggiungi delle gare per generare il dossier.")
        else:
            scarica_dossier("ga", lambda n: ops_report.report_ga(out, n), "Gare", audit, "Gare e offerte")
        st.caption("Probabilità e costi sono stime tue: il consiglio vale quanto le ipotesi inserite.")
