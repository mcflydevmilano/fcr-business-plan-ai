"""og_ui.py - Interfaccia di Organico e carico di lavoro."""
import datetime as dt

import pandas as pd
import streamlit as st
import guida

import charts
import og
import ops_report
import theme
from core import fmt_num
from ui_util import esempi_attivi, senza_esempi, banner_esempio, blocco_tabella, pannello_archivio, scarica_dossier, sostituisci_tabella

ss = st.session_state
PARAM = ("mesi", "sat_min_pct")


@senza_esempi
def _esempio():
    oggi = dt.date.today()
    g = lambda n: (oggi + dt.timedelta(days=n)).isoformat()
    ris = [("Squadra Muratori A", "Muratori", 32, 480), ("Squadra Muratori B", "Muratori", 32, 320), ("Impiantisti", "Impianti", 38, 320), ("Capocantiere Bianchi", "Capocantiere", 45, 160), ("Gruista", "Operatore", 34, 160)]
    ass = [("Squadra Muratori A", "Villa Lago", g(-60), g(60), 300), ("Squadra Muratori A", "Scuola Elementare", g(30), g(240), 260), ("Squadra Muratori B", "Scuola Elementare", g(-30), g(150), 280),
           ("Impiantisti", "Scuola Elementare", g(60), g(180), 300), ("Impiantisti", "Villa Lago", g(-30), g(45), 120), ("Capocantiere Bianchi", "Villa Lago", g(-60), g(60), 90),
           ("Capocantiere Bianchi", "Scuola Elementare", g(-30), g(240), 100), ("Gruista", "Scuola Elementare", g(20), g(120), 120)]
    mk = lambda cols, rows: pd.DataFrame([dict(zip(cols, r)) for r in rows], columns=cols)
    return mk(og.COLONNE_RIS, ris), mk(og.COLONNE_ASS, ass)


def _cfg():
    n, t = st.column_config.NumberColumn, st.column_config.TextColumn
    a, b = og.ETICHETTE_RIS, og.ETICHETTE_ASS
    return ({"Risorsa": t(a["Risorsa"], width="medium"), "Ruolo": t(a["Ruolo"]), "Costo_orario": n(a["Costo_orario"], min_value=0.0, step=1.0, format="%.1f"), "Ore_mese": n(a["Ore_mese"], min_value=1.0, step=10.0, format="%.0f")},
            {"Risorsa": t(b["Risorsa"], width="medium"), "Commessa": t(b["Commessa"]), "Dal": t(b["Dal"], help="AAAA-MM-GG o GG/MM/AAAA"), "Al": t(b["Al"], help="Vuoto = senza fine"),
             "Ore_mese": n(b["Ore_mese"], min_value=0.0, step=10.0, format="%.0f")})


def _raccogli():
    return {"ris": ss["og_ris"].to_dict("records"), "ass": ss["og_ass"].to_dict("records"), "params": {k: ss.get("og_" + k, og.OG_DEFAULT[k]) for k in PARAM}}


def _applica(p, nome):
    sostituisci_tabella("og_ris", pd.DataFrame(p.get("ris") or [], columns=og.COLONNE_RIS))
    sostituisci_tabella("og_ass", pd.DataFrame(p.get("ass") or [], columns=og.COLONNE_ASS))
    ss["og_demo"] = False
    ss["_pending"] = {"og_" + k: v for k, v in (p.get("params") or {}).items() if k in PARAM}


def _dati():
    r, a1 = og.normalizza_ris(ss["og_ris"].to_dict("records"))
    a, a2 = og.normalizza_ass(ss["og_ass"].to_dict("records"), {x["Risorsa"] for x in r})
    return r, a, a1 + a2


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Organico e carico di lavoro", "Quanta gente serve nei prossimi mesi, quando si è in troppi o in pochi e quanto costano le ore ferme."), unsafe_allow_html=True)
    guida.mostra("og")
    if "og_ris" not in ss:
        ss["og_ris"], ss["og_ass"] = _esempio()
        ss["og_demo"] = esempi_attivi()
    pannello_archivio("og", "l'organico", _raccogli, _applica, audit, utente)
    t1, t2, t3 = st.tabs(["👷 1. Risorse e Assegnazioni", "📊 2. Carico di lavoro", "📄 3. Dossier"])
    cr, ca = _cfg()
    with t1:
        banner_esempio("og_demo", [("og_ris", og.COLONNE_RIS), ("og_ass", og.COLONNE_ASS)], "svuota_og")
        blocco_tabella("og_ris", "Risorse", "Persone o squadre. «Ore al mese» = ore realmente disponibili (al netto di ferie e malattie medie).", og.COLONNE_RIS, og.ETICHETTE_RIS, cr, ss["og_ris"], "og", 1, audit, 220)
        blocco_tabella("og_ass", "Assegnazioni alle commesse", "Una riga per ogni periodo in cui una risorsa lavora a una commessa, con le ore mensili. Al vuoto = senza fine.", og.COLONNE_ASS, og.ETICHETTE_ASS, ca, ss["og_ass"], "og", 2, audit, 280)
        ss.setdefault("og_mesi", int(og.OG_DEFAULT["mesi"]))
        ss.setdefault("og_sat_min_pct", float(og.OG_DEFAULT["sat_min_pct"]))
        st.subheader("Ipotesi")
        a, b, c = st.columns(3)
        a.date_input("Data di riferimento", key="og_oggi", value=dt.date.today())
        b.number_input("Mesi da prevedere", 1, 24, step=1, key="og_mesi")
        c.number_input("Saturazione minima (%)", 0.0, 100.0, step=5.0, key="og_sat_min_pct", help="Sotto questa soglia il mese è considerato «scarico».")

    ris, ass, av_n = _dati()
    out = og.calcola_og(ris, ass, {"oggi": ss.get("og_oggi", dt.date.today()), "mesi": ss.get("og_mesi", 6), "sat_min_pct": ss.get("og_sat_min_pct", 60.0)})
    k, mesi = out["kpi"], out["mesi"]

    with t2:
        if not ris:
            st.warning("Nessuna risorsa valida: inserisci nome e ore disponibili.")
        else:
            for x in av_n[:3]:
                st.caption("⚠️ " + x)
            if k["mesi_sovraccarico"]:
                st.error(f"**{k['mesi_sovraccarico']} mesi in sovraccarico**: al picco servono circa {fmt_num(k['ore_extra_picco'])} ore in più (≈ {fmt_num(k['persone_in_piu_picco'], 1)} persone).")
            elif k["mesi_scarico"]:
                st.warning(f"**{k['mesi_scarico']} mesi con poco lavoro**: ore ferme per circa {fmt_num(k['costo_inattivo'])} €.")
            else:
                st.success("**Carico equilibrato** nel periodo.")
            st.markdown(theme.stat_strip([
                {"label": "Saturazione media", "value": f"{fmt_num(k['saturazione_media'], 0)}%", "sub": f"picco {fmt_num(k['picco_saturazione'], 0)}%", "tono": "info"},
                {"label": "Mesi in sovraccarico", "value": str(k["mesi_sovraccarico"]), "sub": f"{fmt_num(k['ore_extra_picco'])} ore extra al picco", "tono": "bad" if k["mesi_sovraccarico"] else "ok"},
                {"label": "Mesi con poco lavoro", "value": str(k["mesi_scarico"]), "sub": "sotto la saturazione minima", "tono": "warn" if k["mesi_scarico"] else "ok"},
                {"label": "Costo ore inattive", "value": f"{fmt_num(k['costo_inattivo'])} €", "sub": "stima sul periodo", "tono": "warn" if k["costo_inattivo"] > 0 else "ok"}]), unsafe_allow_html=True)
            for a in out["avvisi"][:6]:
                st.warning(a)
            st.pyplot(charts.fig_og_carico(mesi, "light"), clear_figure=True)
            st.dataframe(pd.DataFrame([{k2: v for k2, v in m.items() if k2 != "Stato"} for m in mesi]).round(0), hide_index=True, width="stretch")
            st.markdown("**Saturazione per risorsa (%)**")
            st.dataframe(pd.DataFrame([{k2: v for k2, v in r.items() if k2 != "Stato"} for r in out["risorse"]]).round(0), hide_index=True, width="stretch")
            if out["commesse"]:
                st.markdown("**Costo del personale per commessa (€)**")
                st.dataframe(pd.DataFrame(out["commesse"]), hide_index=True, width="stretch")

    with t3:
        if not ris:
            st.info("Aggiungi delle risorse per generare il dossier.")
        else:
            scarica_dossier("og", lambda n: ops_report.report_og(out, ris, ass, n), "Organico", audit, "Organico e carico di lavoro")
        st.caption("Non tiene conto di ferie, malattie e straordinari: inseriscili nelle ore disponibili.")
