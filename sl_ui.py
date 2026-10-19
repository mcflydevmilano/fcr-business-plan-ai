"""sl_ui.py - Interfaccia di SAL e contabilita' lavori."""
import datetime as dt

import pandas as pd
import streamlit as st

import cf
import charts
import sc
import sl
import sl_report
import theme
from core import fmt_num
from ui_util import modello_excel, pannello_archivio, sostituisci_tabella, tabella_modificabile

ss = st.session_state
PARAM_CHIAVI = ("gg_pagamento", "gg_svincolo")
TABELLE = (("sl_com", "up_slc", "imp_slc", sl.COLONNE_COMMESSE, sl.ETICHETTE_COMMESSE),
           ("sl_sal", "up_sls", "imp_sls", sl.COLONNE_SAL, sl.ETICHETTE_SAL),
           ("sl_cos", "up_slk", "imp_slk", sl.COLONNE_COSTI, sl.ETICHETTE_COSTI))
STATI = {"ok": "🟢 In linea", "warn": "🟡 Attenzione", "bad": "🔴 Critica"}


def _esempio():
    oggi = dt.date.today()
    g = lambda n: (oggi + dt.timedelta(days=n)).isoformat()
    com = [("Villa Lago", "Rossi Costruzioni", 100000, 10000, 88000, 50, 5, 10, 10, 30, g(-120), g(60)),
           ("Scuola Elementare", "Comune di Esempio", 400000, 0, 320000, 60, 5, 0, 10, 60, g(-150), g(90)),
           ("Capannone Nord", "Immobiliare Sole Srl", 250000, 15000, 205000, 80, 5, 20, 22, 30, g(-200), g(30))]
    sal = [("Villa Lago", "0", g(-118), 0, 12100, g(-100)), ("Villa Lago", "1", g(-60), 30, 0, ""),
           ("Scuola Elementare", "1", g(-100), 25, 100000, g(-35)), ("Scuola Elementare", "2", g(-40), 50, 0, ""),
           ("Capannone Nord", "0", g(-198), 0, 60000, g(-170)), ("Capannone Nord", "1", g(-120), 40, 90000, g(-85)), ("Capannone Nord", "2", g(-45), 70, 0, "")]
    cos = [("Villa Lago", g(-50), "Calcestruzzi Alfa", "Strutture", "Materiali", 40000, 30000), ("Villa Lago", g(-10), "Ponteggi Gamma", "Ponteggi", "Noli", 20000, 0),
           ("Scuola Elementare", g(-90), "Elettroimpianti Beta", "Impianti", "Subappalti", 110000, 110000), ("Scuola Elementare", g(-30), "Edilsud", "Murature", "Materiali", 80000, 40000),
           ("Capannone Nord", g(-130), "Acciaierie Delta", "Struttura metallica", "Materiali", 120000, 120000), ("Capannone Nord", g(-40), "Impianti Beta", "Impianti", "Subappalti", 60000, 20000)]
    mk = lambda cols, rows: pd.DataFrame([dict(zip(cols, r)) for r in rows], columns=cols)
    return mk(sl.COLONNE_COMMESSE, com), mk(sl.COLONNE_SAL, sal), mk(sl.COLONNE_COSTI, cos)


def _cfg():
    n, t = st.column_config.NumberColumn, st.column_config.TextColumn
    e, s, k = sl.ETICHETTE_COMMESSE, sl.ETICHETTE_SAL, sl.ETICHETTE_COSTI
    data = "AAAA-MM-GG o GG/MM/AAAA"
    com = {"Commessa": t(e["Commessa"]), "Cliente": t(e["Cliente"]), "Contratto": n(e["Contratto"], min_value=0.0, step=1000.0, format="%.0f"),
           "Varianti": n(e["Varianti"], step=1000.0, format="%.0f"), "Costi_prev": n(e["Costi_prev"], min_value=0.0, step=1000.0, format="%.0f"),
           "Avanz_reale_pct": n(e["Avanz_reale_pct"], min_value=0.0, max_value=100.0, step=5.0, format="%.1f"),
           "Ritenuta_pct": n(e["Ritenuta_pct"], min_value=0.0, max_value=100.0, step=0.5, format="%.1f"),
           "Anticipo_pct": n(e["Anticipo_pct"], min_value=0.0, max_value=100.0, step=5.0, format="%.0f"),
           "Iva_pct": n(e["Iva_pct"], min_value=0.0, max_value=100.0, step=1.0, format="%.0f"), "Gg_incasso": n(e["Gg_incasso"], min_value=0, step=15, format="%d"),
           "Inizio": t(e["Inizio"], help=data), "Fine_prev": t(e["Fine_prev"], help=data)}
    sal = {"Commessa": t(s["Commessa"]), "Numero": t(s["Numero"]), "Data": t(s["Data"], help=data),
           "Avanzamento_pct": n(s["Avanzamento_pct"], min_value=0.0, max_value=100.0, step=5.0, format="%.1f"),
           "Incassato": n(s["Incassato"], min_value=0.0, step=100.0, format="%.2f"), "Data_incasso": t(s["Data_incasso"], help=data)}
    cos = {"Commessa": t(k["Commessa"]), "Data": t(k["Data"], help=data), "Fornitore": t(k["Fornitore"]), "Descrizione": t(k["Descrizione"]), "Categoria": t(k["Categoria"]),
           "Importo": n(k["Importo"], min_value=0.0, step=100.0, format="%.2f"), "Pagato": n(k["Pagato"], min_value=0.0, step=100.0, format="%.2f")}
    return {"sl_com": com, "sl_sal": sal, "sl_cos": cos}


def _params():
    p = {k: ss.get("sl_" + k, v) for k, v in sl.SL_DEFAULT.items() if k in PARAM_CHIAVI}
    p["oggi"] = ss.get("sl_oggi", dt.date.today())
    return p


def _raccogli():
    return {"commesse": ss["sl_com"].to_dict("records"), "sal": ss["sl_sal"].to_dict("records"), "costi": ss["sl_cos"].to_dict("records"),
            "params": {k: ss.get("sl_" + k, sl.SL_DEFAULT[k]) for k in PARAM_CHIAVI}}


def _applica(p, nome):
    for chiave, _u, _i, cols, _e in TABELLE:
        sostituisci_tabella(chiave, pd.DataFrame(p.get({"sl_com": "commesse", "sl_sal": "sal", "sl_cos": "costi"}[chiave]) or [], columns=cols))
    ss["sl_demo"] = False
    ss["_pending"] = {"sl_" + k: v for k, v in (p.get("params") or {}).items() if k in PARAM_CHIAVI}


def _df(df):
    st.dataframe(df, hide_index=True, width="stretch")


def _dati():
    com, a1 = sl.normalizza_commesse(ss["sl_com"].to_dict("records"))
    nomi = {c["Commessa"] for c in com}
    sal, a2 = sl.normalizza_sal(ss["sl_sal"].to_dict("records"), nomi)
    cos, a3 = sl.normalizza_costi(ss["sl_cos"].to_dict("records"), nomi)
    return com, sal, cos, a1 + a2 + a3


def _importa(idx, up_key, imp_key, audit):
    chiave, _u, _i, cols, etich = TABELLE[idx]
    up = st.file_uploader("Importa da Excel/CSV", type=["xlsx", "csv"], key=up_key)
    if up is not None and st.button("Importa il file", key=imp_key):
        try:
            d = pd.read_csv(up, sep=None, engine="python") if up.name.lower().endswith(".csv") else pd.read_excel(up)
            inv = {v.lower(): k for k, v in etich.items()}
            inv.update({k.lower(): k for k in cols})
            d = d.rename(columns={c: inv.get(str(c).strip().lower(), c) for c in d.columns})
            d = d.reindex(columns=cols)
            if d.dropna(how="all").empty:
                st.error("Nessuna riga valida nel file.")
            else:
                sostituisci_tabella(chiave, d.dropna(how="all").astype(object).where(d.notna(), None))
                ss["sl_demo"] = False
                audit("sl_import", up.name)
                st.rerun()
        except Exception as e:
            st.error(f"File non leggibile: {e}")


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "SAL e contabilità lavori",
                           "Commesse, stati di avanzamento, costi e margine a finire: quanto ho fatturato, quanto mi devono, e quanto guadagnerò davvero."),
                unsafe_allow_html=True)
    if "sl_com" not in ss:
        c, s, k = _esempio()
        ss["sl_com"], ss["sl_sal"], ss["sl_cos"] = c, s, k
        ss["sl_demo"] = True
    pannello_archivio("sl", "le commesse", _raccogli, _applica, audit, utente)
    t1, t2, t3, t4 = st.tabs(["🏗️ 1. Commesse e Dati", "📊 2. Controllo commesse", "🔗 3. Integrazioni", "📄 4. Dossier"])
    cfg = _cfg()

    with t1:
        if ss.get("sl_demo"):
            st.info("Commesse di esempio con date relative a oggi. Sostituiscile con le tue: modifica le tabelle o importa un file.")
            if st.button("Svuota l'esempio e parti da zero", key="sl_svuota"):
                for chiave, _u, _i, cols, _e in TABELLE:
                    sostituisci_tabella(chiave, pd.DataFrame(columns=cols))
                ss["sl_demo"] = False
                st.rerun()
        ex = _esempio()
        st.subheader("Commesse")
        st.caption("Una riga per commessa (da un preventivo accettato). L'avanzamento reale è quello che stimi oggi in cantiere; i costi preventivati vengono dal Computo e Preventivo.")
        tabella_modificabile("sl_com", ss["sl_com"], cfg["sl_com"], altezza=220)
        st.subheader("SAL emessi")
        st.caption("Avanzamento **cumulativo** a quella data (0% = fattura di anticipo). L'importo lordo del SAL è la quota maturata dall'ultimo SAL, "
                   "meno recupero anticipo e ritenuta, più IVA.")
        tabella_modificabile("sl_sal", ss["sl_sal"], cfg["sl_sal"], altezza=240)
        st.subheader("Costi sostenuti")
        st.caption("Fatture dei fornitori e costi di cantiere. «Già pagato» = quanto hai già saldato; il resto è debito verso il fornitore.")
        tabella_modificabile("sl_cos", ss["sl_cos"], cfg["sl_cos"], altezza=260)
        with st.expander("Importa da Excel/CSV e modelli"):
            for i, (nome, (chiave, _u, _i, cols, etich)) in enumerate(zip(("Commesse", "SAL", "Costi"), TABELLE)):
                st.markdown(f"**{nome}** - colonne: " + ", ".join(cols))
                st.download_button(f"📥 Modello Excel: {nome}", modello_excel(cols, etich, ex[i].head(3).to_dict("records")),
                                   file_name=f"modello_sl_{nome.lower()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"dl_sl_{i}")
                _importa(i, TABELLE[i][1], TABELLE[i][2], audit)
        st.subheader("Ipotesi")
        a, b, c = st.columns(3)
        a.date_input("Data di riferimento", key="sl_oggi", value=dt.date.today())
        if "sl_gg_pagamento" not in ss:
            ss["sl_gg_pagamento"] = int(sl.SL_DEFAULT["gg_pagamento"])
        if "sl_gg_svincolo" not in ss:
            ss["sl_gg_svincolo"] = int(sl.SL_DEFAULT["gg_svincolo"])
        b.number_input("Pagamento ai fornitori (giorni)", 0, 365, step=15, key="sl_gg_pagamento", help="Scadenza stimata dei costi: data fattura + questi giorni.")
        c.number_input("Svincolo ritenute dopo (giorni)", 0, 1000, step=30, key="sl_gg_svincolo", help="Giorni dalla fine prevista dei lavori.")

    com, sal, cos, av_n = _dati()
    p = _params()
    out = sl.calcola_sl(com, sal, cos, p)
    k, det = out["kpi"], out["commesse"]

    with t2:
        if not det:
            st.warning("Nessuna commessa valida: inserisci almeno una commessa con nome e contratto.")
        else:
            for x in av_n[:4]:
                st.caption("⚠️ " + x)
            if k["n_bad"]:
                st.error(f"**{k['n_bad']} commesse in sofferenza**: il margine finale previsto è molto sotto il preventivo.")
            elif k["n_warn"]:
                st.warning(f"**{k['n_warn']} commesse da tenere d'occhio.**")
            else:
                st.success("**Tutte le commesse sono in linea** con il preventivo.")
            mt = "bad" if k["margine_finale_pct"] < k["margine_atteso_pct"] - sl.TOLL_WARN else ("warn" if k["margine_finale_pct"] < k["margine_atteso_pct"] - sl.TOLL_OK else "ok")
            st.markdown(theme.stat_strip([
                {"label": "Contratti", "value": f"{fmt_num(k['contratti'])} €", "sub": f"avanzamento {fmt_num(k['avanzamento'], 0)}%", "tono": "info"},
                {"label": "Margine a finire", "value": f"{fmt_num(k['margine_finale_pct'], 1)}%", "sub": f"preventivato {fmt_num(k['margine_atteso_pct'], 1)}%", "tono": mt},
                {"label": "Da fatturare", "value": f"{fmt_num(k['da_fatturare'])} €", "sub": "lavori eseguiti non fatturati", "tono": "warn" if k["da_fatturare"] > 0 else "ok"},
                {"label": "Crediti scaduti", "value": f"{fmt_num(k['crediti_scaduti'])} €", "sub": "SAL non incassati", "tono": "bad" if k["crediti_scaduti"] > 0 else "ok"},
            ]), unsafe_allow_html=True)
            for a in out["avvisi"]:
                st.warning(a)
            st.pyplot(charts.fig_sl_margini(det, "light"), clear_figure=True)
            tab = pd.DataFrame([{"Commessa": d["Commessa"], "Stato": STATI[d["Stato"]], "Contratto": d["Contratto totale"], "Avanz. %": d["Avanzamento %"],
                                 "Fatturato %": d["Avanzamento fatturato %"], "Da fatturare": d["Da fatturare"], "Incassato": d["Incassato"], "Costi sostenuti": d["Costi sostenuti"],
                                 "Margine prev. %": d["Margine atteso %"], "Margine finale %": d["Margine finale %"], "Scostamento pp": d["Scostamento margine (pp)"]} for d in det])
            _df(tab.round(1))
            scelta = st.selectbox("Dettaglio commessa", [d["Commessa"] for d in det], key="sl_sel")
            d = next(x for x in det if x["Commessa"] == scelta)
            c1, c2 = st.columns([3, 2])
            with c1:
                st.pyplot(charts.fig_sl_commessa(d, "light"), clear_figure=True)
            with c2:
                st.metric("Indice di costo (CPI)", "n.d." if d["CPI"] is None else fmt_num(d["CPI"], 2), help="Valore maturato / costi sostenuti. Sotto 1 = costi più alti del previsto.")
                st.metric("Costi a finire attesi", f"{fmt_num(d['Costi a finire (EAC)'])} €")
                st.metric("Margine finale previsto", f"{fmt_num(d['Margine finale previsto'])} €", f"{fmt_num(d['Scostamento margine (pp)'], 1)} pp", delta_color="normal")
                st.metric("Debiti fornitori", f"{fmt_num(d['Debiti fornitori'])} €", f"di cui scaduti {fmt_num(d['Fornitori scaduti'])} €", delta_color="off")
            fat = [f for f in out["fatture"] if f["Commessa"] == scelta]
            if fat:
                _df(pd.DataFrame([{**f, "Scaduta": "sì" if f["Scaduta"] else ""} for f in fat]).round(2))

    with t3:
        st.caption("Porta i dati di questa pagina negli altri strumenti. L'invio **sostituisce** solo le righe già inviate da qui (documenti «SL:»), senza toccare le altre.")
        a, b = st.columns(2)
        with a:
            st.markdown("**Scadenzario incassi e pagamenti**")
            st.write("SAL emessi → fatture attive; costi non pagati → fatture passive.")
            if st.button("📅 Invia allo Scadenzario", key="sl_to_sc", disabled=not det):
                if "sc_df" not in ss:
                    ss["sc_df"] = pd.DataFrame(columns=sc.COLONNE_DOC)
                att = ss["sc_df"]
                if ss.get("sc_demo"):
                    att = pd.DataFrame(columns=sc.COLONNE_DOC)
                    ss["sc_demo"] = False
                if len(att):
                    att = att[~att["Documento"].astype(str).str.startswith(sl.PREFISSO_DOC)]
                nuove = pd.DataFrame(sl.per_scadenzario(out, cos, p), columns=sc.COLONNE_DOC)
                sostituisci_tabella("sc_df", pd.concat([att, nuove], ignore_index=True) if len(att) else nuove)
                audit("sl_to_sc", str(len(nuove)))
                st.success(f"Inviate {len(nuove)} righe allo Scadenzario. Aprilo dall'Hub per vedere la cassa settimanale.")
        with b:
            st.markdown("**Cash Flow di cantiere**")
            st.write("Le commesse diventano cantieri, con i costi a finire attesi al posto del preventivo.")
            if st.button("💶 Invia al Cash Flow", key="sl_to_cf", disabled=not det):
                righe = sl.per_cash_flow(out, com)
                sostituisci_tabella("cf_df", pd.DataFrame(righe, columns=cf.COLONNE_CANTIERI))
                ss["cf_demo"] = False
                audit("sl_to_cf", str(len(righe)))
                st.success(f"Portafoglio del Cash Flow sostituito con {len(righe)} commesse (mese 1 = prima partenza).")
        st.info("Il **Cruscotto di direzione** legge questo modulo dalla sessione o da un salvataggio e aggiunge i semafori su margine a finire e commesse critiche.")

    with t4:
        if not det:
            st.info("Aggiungi delle commesse per generare il dossier.")
        else:
            nome = st.text_input("Nome del documento", "SAL e contabilità lavori", key="sl_nome")
            if st.button("📄 Genera dossier PDF ed Excel", type="primary", key="sl_gen"):
                with st.spinner("Preparo i documenti..."):
                    ctx = sl_report.costruisci_ctx_sl(out, com, sal, cos, nome)
                    ss["sl_rep"] = {"pdf": sl_report.genera_pdf_sl(ctx), "xlsx": sl_report.genera_excel_sl(ctx), "id": ctx["report_id"]}
                    audit("sl_report", ctx["report_id"])
            rep = ss.get("sl_rep")
            if rep:
                c1, c2 = st.columns(2)
                c1.download_button("📥 Scarica il dossier PDF", rep["pdf"], file_name=f"SAL_{rep['id']}.pdf", mime="application/pdf", width="stretch")
                c2.download_button("📥 Scarica l'Excel con formule", rep["xlsx"], file_name=f"SAL_{rep['id']}.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
        st.caption("L'avanzamento reale è una stima inserita da te; il margine a finire presume che l'efficienza dei costi osservata continui.")
