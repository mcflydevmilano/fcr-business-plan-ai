"""mz_ui.py - Interfaccia del Parco mezzi e attrezzature."""
import datetime as dt

import pandas as pd
import streamlit as st
import guida

import charts
import mz
import ops_report
import sl
import theme
from core import fmt_num
from ui_util import banner_esempio, blocco_tabella, pannello_archivio, scarica_dossier, sostituisci_tabella, sola_lettura

ss = st.session_state
ICONE = {"ok": "🟢", "warn": "🟡", "bad": "🔴", "nd": "⚪"}
PARAM = ("preavviso_gg", "utilizzo_min_pct")


def _esempio():
    g = lambda n: (dt.date.today() + dt.timedelta(days=n)).isoformat()
    mezzi = [("Escavatore CAT 320", "Movimento terra", 18000, 28, 1100), ("Autocarro Iveco", "Trasporto", 9000, 22, 900), ("Gru a torre", "Sollevamento", 26000, 12, 500), ("Minipala Bobcat", "Movimento terra", 6000, 15, 700)]
    uso = [("Escavatore CAT 320", "Villa Lago", g(-60), 180), ("Escavatore CAT 320", "Scuola Elementare", g(-30), 260), ("Escavatore CAT 320", "Capannone Nord", g(-200), 300), ("Autocarro Iveco", "Villa Lago", g(-45), 220),
           ("Autocarro Iveco", "Scuola Elementare", g(-100), 310), ("Gru a torre", "Scuola Elementare", g(-70), 120), ("Minipala Bobcat", "Capannone Nord", g(-90), 90)]
    scad = [("Escavatore CAT 320", "Revisione", g(40)), ("Autocarro Iveco", "Assicurazione", g(-6)), ("Autocarro Iveco", "Revisione", g(120)), ("Gru a torre", "Verifica periodica", g(18)), ("Minipala Bobcat", "Manutenzione programmata", g(200))]
    mk = lambda cols, rows: pd.DataFrame([dict(zip(cols, r)) for r in rows], columns=cols)
    return mk(mz.COLONNE_MEZZI, mezzi), mk(mz.COLONNE_USO, uso), mk(mz.COLONNE_SCAD, scad)


def _cfg():
    n, t = st.column_config.NumberColumn, st.column_config.TextColumn
    a, b, c = mz.ETICHETTE_MEZZI, mz.ETICHETTE_USO, mz.ETICHETTE_SCAD
    return ({"Mezzo": t(a["Mezzo"], width="medium"), "Tipo": t(a["Tipo"]), "Costo_fisso_annuo": n(a["Costo_fisso_annuo"], min_value=0.0, step=500.0, format="%.0f"),
             "Costo_var_orario": n(a["Costo_var_orario"], min_value=0.0, step=1.0, format="%.1f"), "Ore_annue_prev": n(a["Ore_annue_prev"], min_value=1.0, step=50.0, format="%.0f")},
            {"Mezzo": t(b["Mezzo"], width="medium"), "Commessa": t(b["Commessa"]), "Data": t(b["Data"], help="AAAA-MM-GG o GG/MM/AAAA"), "Ore": n(b["Ore"], min_value=0.0, step=1.0, format="%.1f")},
            {"Mezzo": t(c["Mezzo"], width="medium"), "Documento": t(c["Documento"]), "Scadenza": t(c["Scadenza"], help="AAAA-MM-GG o GG/MM/AAAA")})


def _raccogli():
    return {"mezzi": ss["mz_mezzi"].to_dict("records"), "uso": ss["mz_uso"].to_dict("records"), "scad": ss["mz_scad"].to_dict("records"), "params": {k: ss.get("mz_" + k, mz.MZ_DEFAULT[k]) for k in PARAM}}


def _applica(p, nome):
    for chiave, cols, k in (("mz_mezzi", mz.COLONNE_MEZZI, "mezzi"), ("mz_uso", mz.COLONNE_USO, "uso"), ("mz_scad", mz.COLONNE_SCAD, "scad")):
        sostituisci_tabella(chiave, pd.DataFrame(p.get(k) or [], columns=cols))
    ss["mz_demo"] = False
    ss["_pending"] = {"mz_" + k: v for k, v in (p.get("params") or {}).items() if k in PARAM}


def _dati():
    m, a1 = mz.normalizza_mezzi(ss["mz_mezzi"].to_dict("records"))
    nomi = {x["Mezzo"] for x in m}
    u, a2 = mz.normalizza_uso(ss["mz_uso"].to_dict("records"), nomi)
    s, a3 = mz.normalizza_scad(ss["mz_scad"].to_dict("records"), nomi)
    return m, u, s, a1 + a2 + a3


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Parco mezzi e attrezzature", "Quanto costa un'ora di ogni mezzo, quanto viene usato e quali scadenze arrivano."), unsafe_allow_html=True)
    guida.mostra("mz")
    if "mz_mezzi" not in ss:
        ss["mz_mezzi"], ss["mz_uso"], ss["mz_scad"] = _esempio()
        ss["mz_demo"] = True
    pannello_archivio("mz", "il parco mezzi", _raccogli, _applica, audit, utente)
    t1, t2, t3, t4 = st.tabs(["🚜 1. Mezzi e Utilizzo", "📊 2. Costi e Scadenze", "🔗 3. Integrazioni", "📄 4. Dossier"])
    cm, cu, cs = _cfg()
    with t1:
        banner_esempio("mz_demo", [("mz_mezzi", mz.COLONNE_MEZZI), ("mz_uso", mz.COLONNE_USO), ("mz_scad", mz.COLONNE_SCAD)], "svuota_mz")
        blocco_tabella("mz_mezzi", "Mezzi", "Costi fissi annui = ammortamento, assicurazione, bollo. Costo variabile orario = carburante, manutenzione e usura per ora di lavoro.", mz.COLONNE_MEZZI, mz.ETICHETTE_MEZZI, cm, ss["mz_mezzi"], "mz", 1, audit, 220)
        blocco_tabella("mz_uso", "Utilizzo sulle commesse", "Una riga per periodo di utilizzo: quante ore il mezzo ha lavorato per quella commessa.", mz.COLONNE_USO, mz.ETICHETTE_USO, cu, ss["mz_uso"], "mz", 2, audit, 260)
        blocco_tabella("mz_scad", "Scadenze", "Revisione, assicurazione, bollo, manutenzione, verifiche periodiche.", mz.COLONNE_SCAD, mz.ETICHETTE_SCAD, cs, ss["mz_scad"], "mz", 3, audit, 220)
        ss.setdefault("mz_preavviso_gg", int(mz.MZ_DEFAULT["preavviso_gg"]))
        ss.setdefault("mz_utilizzo_min_pct", float(mz.MZ_DEFAULT["utilizzo_min_pct"]))
        st.subheader("Ipotesi")
        a, b, c = st.columns(3)
        a.date_input("Data di riferimento", key="mz_oggi", value=dt.date.today())
        b.number_input("Preavviso scadenze (giorni)", 0, 180, step=5, key="mz_preavviso_gg")
        c.number_input("Utilizzo minimo accettabile (%)", 0.0, 100.0, step=5.0, key="mz_utilizzo_min_pct")

    mezzi, uso, scad, av_n = _dati()
    out = mz.calcola_mz(mezzi, uso, scad, {"oggi": ss.get("mz_oggi", dt.date.today()), "preavviso_gg": ss.get("mz_preavviso_gg", 30), "utilizzo_min_pct": ss.get("mz_utilizzo_min_pct", 50.0)})
    k, det = out["kpi"], out["mezzi"]

    with t2:
        if not det:
            st.warning("Nessun mezzo valido: inserisci nome e ore annue previste.")
        else:
            for x in av_n[:3]:
                st.caption("⚠️ " + x)
            if k["n_bad"]:
                st.error(f"**{k['n_bad']} mezzi con scadenze superate.**")
            elif k["n_warn"]:
                st.warning(f"**{k['n_warn']} mezzi da tenere d'occhio** (scadenze vicine o poco utilizzo).")
            else:
                st.success("**Parco mezzi in ordine.**")
            st.markdown(theme.stat_strip([
                {"label": "Costo imputato", "value": f"{fmt_num(k['costo_imputato'])} €", "sub": "alle commesse, 12 mesi", "tono": "info"},
                {"label": "Fissi non assorbiti", "value": f"{fmt_num(k['fissi_non_assorbiti'])} €", "sub": f"{k['sottoutilizzati']} mezzi sottoutilizzati", "tono": "warn" if k["fissi_non_assorbiti"] > 0 else "ok"},
                {"label": "Scadenze superate", "value": str(k["scad_scadute"]), "sub": "revisioni e assicurazioni", "tono": "bad" if k["scad_scadute"] else "ok"},
                {"label": "In arrivo", "value": str(k["scad_in_arrivo"]), "sub": "entro il preavviso", "tono": "warn" if k["scad_in_arrivo"] else "ok"}]), unsafe_allow_html=True)
            for a in out["avvisi"][:8]:
                st.warning(a)
            st.pyplot(charts.fig_mz_costi(det, "light"), clear_figure=True)
            st.dataframe(pd.DataFrame([{"Mezzo": d["Mezzo"], "Stato": ICONE[d["Stato"]], "Tariffa €/h": d["Tariffa oraria"], "Ore 12 mesi": d["Ore 12 mesi"], "Utilizzo %": d["Utilizzo %"], "Costo imputato": d["Costo imputato"],
                                        "Fissi non assorbiti": d["Fissi non assorbiti"]} for d in det]).round(1), hide_index=True, width="stretch")
            c1, c2 = st.columns(2)
            c1.markdown("**Costo mezzi per commessa**")
            c1.dataframe(pd.DataFrame(out["commesse"]).round(0), hide_index=True, width="stretch")
            c2.markdown("**Scadenze in arrivo o superate**")
            ren = [{"Mezzo": d["Mezzo"], "Scadenza di": d["Documento"], "Data": d["Scadenza"], "Giorni": d["Giorni"], "Stato": ICONE[d["Stato"]]} for d in out["scadenze"] if d["Stato"] in ("bad", "warn")]
            c2.dataframe(pd.DataFrame(ren), hide_index=True, width="stretch") if ren else c2.success("Nessuna scadenza imminente.")

    with t3:
        st.caption("Porta il costo dei mezzi nei costi delle commesse di **SAL e contabilità lavori**, come costo sostenuto (fornitore «Parco mezzi interno», già saldato). "
                   "L'invio sostituisce solo le righe già inviate da qui. Attenzione a non contare due volte i mezzi se li inserisci già a mano come costi.")
        righe = mz.per_sl_costi(out)
        st.write(f"Righe di costo pronte: **{len(righe)}**")
        if st.button("📐 Invia i costi dei mezzi a SAL e contabilità", key="to_sl_mz", disabled=not righe or sola_lettura()):
            if "sl_cos" not in ss:
                ss["sl_com"], ss["sl_sal"], ss["sl_cos"] = (pd.DataFrame(columns=c) for c in (sl.COLONNE_COMMESSE, sl.COLONNE_SAL, sl.COLONNE_COSTI))
                ss["sl_demo"] = False
            att = ss["sl_cos"]
            if len(att):
                att = att[att["Fornitore"].astype(str) != "Parco mezzi interno"]
            nuove = pd.DataFrame(righe, columns=sl.COLONNE_COSTI)
            sostituisci_tabella("sl_cos", pd.concat([att, nuove], ignore_index=True) if len(att) else nuove)
            audit("mz_to_sl", str(len(nuove)))
            st.success(f"Inviate {len(nuove)} righe di costo. Vengono considerate solo se la commessa esiste in SAL.")

    with t4:
        if not det:
            st.info("Aggiungi dei mezzi per generare il dossier.")
        else:
            scarica_dossier("mz", lambda n: ops_report.report_mz(out, mezzi, n), "Mezzi", audit, "Parco mezzi e attrezzature")
        st.caption("Le tariffe dipendono dai costi e dalle ore inserite: sono stime di gestione, non valori contabili.")
