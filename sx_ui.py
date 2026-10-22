"""sx_ui.py - Interfaccia di Sicurezza e documenti di cantiere."""
import datetime as dt

import pandas as pd
import streamlit as st
import guida

import charts
import ops_report
import sx
import theme
from ui_util import esempi_attivi, senza_esempi, banner_esempio, blocco_tabella, pannello_archivio, scarica_dossier, sostituisci_tabella

ss = st.session_state
ICONE = {"ok": "🟢", "warn": "🟡", "bad": "🔴", "nd": "⚪"}


@senza_esempi
def _esempio():
    g = lambda n: (dt.date.today() + dt.timedelta(days=n)).isoformat()
    pers = [("Mario Rossi", "Muratore", "Villa Lago", "Visita medica", g(-10)), ("Mario Rossi", "Muratore", "Villa Lago", "Formazione specifica", g(400)),
            ("Luca Bianchi", "Capocantiere", "Villa Lago", "Aggiornamento", g(20)), ("Luca Bianchi", "Capocantiere", "Villa Lago", "Primo soccorso", g(250)),
            ("Paolo Verdi", "Gruista", "Scuola Elementare", "Visita medica", g(90)), ("Paolo Verdi", "Gruista", "Scuola Elementare", "Lavori in quota", g(18)),
            ("Anna Neri", "Geometra", "Scuola Elementare", "Formazione generale", g(500))]
    docc = [("Villa Lago", "Notifica preliminare", True, ""), ("Villa Lago", "PSC (piano di sicurezza e coordinamento)", True, ""), ("Villa Lago", "POS (piano operativo di sicurezza)", False, ""),
            ("Villa Lago", "DURC delle imprese", True, g(-3)), ("Scuola Elementare", "Notifica preliminare", True, ""), ("Scuola Elementare", "PSC (piano di sicurezza e coordinamento)", True, ""),
            ("Scuola Elementare", "POS (piano operativo di sicurezza)", True, ""), ("Scuola Elementare", "DURC delle imprese", True, g(60))]
    return (pd.DataFrame([dict(zip(sx.COLONNE_PERS, r)) for r in pers], columns=sx.COLONNE_PERS), pd.DataFrame([dict(zip(sx.COLONNE_DOCC, r)) for r in docc], columns=sx.COLONNE_DOCC))


def _cfg():
    t = st.column_config.TextColumn
    a, b = sx.ETICHETTE_PERS, sx.ETICHETTE_DOCC
    return ({"Persona": t(a["Persona"]), "Ruolo": t(a["Ruolo"]), "Cantiere": t(a["Cantiere"]), "Documento": t(a["Documento"], width="medium"), "Scadenza": t(a["Scadenza"], help="AAAA-MM-GG o GG/MM/AAAA")},
            {"Cantiere": t(b["Cantiere"]), "Documento": t(b["Documento"], width="large"), "Presente": st.column_config.CheckboxColumn(b["Presente"]), "Scadenza": t(b["Scadenza"], help="AAAA-MM-GG o GG/MM/AAAA")})


def _raccogli():
    return {"pers": ss["sx_pers"].to_dict("records"), "docc": ss["sx_docc"].to_dict("records"), "params": {"preavviso_gg": ss.get("sx_preavviso_gg", sx.SX_DEFAULT["preavviso_gg"])}}


def _applica(p, nome):
    sostituisci_tabella("sx_pers", pd.DataFrame(p.get("pers") or [], columns=sx.COLONNE_PERS))
    sostituisci_tabella("sx_docc", pd.DataFrame(p.get("docc") or [], columns=sx.COLONNE_DOCC))
    ss["sx_demo"] = False
    ss["_pending"] = {"sx_preavviso_gg": (p.get("params") or {}).get("preavviso_gg", sx.SX_DEFAULT["preavviso_gg"])}


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Sicurezza e documenti di cantiere", "Formazioni e idoneità in scadenza, documenti obbligatori per ogni cantiere."), unsafe_allow_html=True)
    guida.mostra("sx")
    if "sx_pers" not in ss:
        ss["sx_pers"], ss["sx_docc"] = _esempio()
        ss["sx_demo"] = esempi_attivi()
    pannello_archivio("sx", "i dati di sicurezza", _raccogli, _applica, audit, utente)
    t1, t2, t3 = st.tabs(["🦺 1. Dati", "🔎 2. Controllo", "📄 3. Dossier"])
    cp, cd = _cfg()
    with t1:
        banner_esempio("sx_demo", [("sx_pers", sx.COLONNE_PERS), ("sx_docc", sx.COLONNE_DOCC)], "svuota_sx")
        blocco_tabella("sx_pers", "Formazioni e idoneità del personale", "Una riga per ogni corso, visita o idoneità di una persona, con la sua scadenza.", sx.COLONNE_PERS, sx.ETICHETTE_PERS, cp, ss["sx_pers"], "sx", 1, audit, 280, sx.SINONIMI_PERS)
        blocco_tabella("sx_docc", "Documenti di cantiere", "Spunta «Presente» quando il documento è in cantiere e valido.", sx.COLONNE_DOCC, sx.ETICHETTE_DOCC, cd, ss["sx_docc"], "sx", 2, audit, 280)
        a, b = st.columns([3, 1])
        cant = a.text_input("Aggiungi la check-list standard a un cantiere", key="sx_nuovo_cantiere", placeholder="Nome del cantiere")
        b.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
        if b.button("➕ Aggiungi", key="chk_sx", width="stretch") and cant.strip():
            att = ss["sx_docc"]
            gia = set(att[att["Cantiere"] == cant.strip()]["Documento"].astype(str)) if len(att) else set()
            nuovi = pd.DataFrame([{"Cantiere": cant.strip(), "Documento": d, "Presente": False, "Scadenza": ""} for d in sx.DOC_CANTIERE if d not in gia], columns=sx.COLONNE_DOCC)
            if len(nuovi):
                sostituisci_tabella("sx_docc", pd.concat([att, nuovi], ignore_index=True) if len(att) else nuovi)
                st.rerun()
        ss.setdefault("sx_preavviso_gg", int(sx.SX_DEFAULT["preavviso_gg"]))
        st.subheader("Ipotesi")
        a, b = st.columns(2)
        a.date_input("Data di riferimento", key="sx_oggi", value=dt.date.today())
        b.number_input("Preavviso scadenze (giorni)", 0, 180, step=5, key="sx_preavviso_gg")

    pers, a1 = sx.normalizza_pers(ss["sx_pers"].to_dict("records"))
    docc, a2 = sx.normalizza_docc(ss["sx_docc"].to_dict("records"))
    out = sx.calcola_sx(pers, docc, {"oggi": ss.get("sx_oggi", dt.date.today()), "preavviso_gg": ss.get("sx_preavviso_gg", 30)})
    k = out["kpi"]

    with t2:
        if not pers and not docc:
            st.warning("Nessun dato: inserisci almeno una scadenza o un documento di cantiere.")
        else:
            for x in (a1 + a2)[:3]:
                st.caption("⚠️ " + x)
            if k["cantieri_a_rischio"]:
                st.error(f"**{k['cantieri_a_rischio']} cantieri con documenti mancanti o persone non in regola.**")
            elif k["in_scadenza"]:
                st.warning(f"**{k['in_scadenza']} scadenze in arrivo.**")
            else:
                st.success("**Tutto in regola.**")
            st.markdown(theme.stat_strip([
                {"label": "Persone non in regola", "value": str(k["persone_non_in_regola"]), "sub": f"su {k['n_persone']}", "tono": "bad" if k["persone_non_in_regola"] else "ok"},
                {"label": "In scadenza", "value": str(k["in_scadenza"]), "sub": "formazioni e idoneità", "tono": "warn" if k["in_scadenza"] else "ok"},
                {"label": "Documenti mancanti", "value": str(k["doc_mancanti"]), "sub": f"{k['doc_scaduti']} scaduti", "tono": "bad" if k["doc_mancanti"] else "ok"},
                {"label": "Cantieri a rischio", "value": str(k["cantieri_a_rischio"]), "sub": f"su {k['n_cantieri']}", "tono": "bad" if k["cantieri_a_rischio"] else "ok"}]), unsafe_allow_html=True)
            for a in out["avvisi"][:8]:
                st.warning(a)
            c1, c2 = st.columns([2, 3])
            c1.pyplot(charts.fig_scadenze({"bad": k["scaduti"], "warn": k["in_scadenza"], "ok": k["ok"]}, "Formazioni e idoneità", "light"), clear_figure=True)
            c2.dataframe(pd.DataFrame([{"Cantiere": c["Cantiere"], "Stato": ICONE[c["Stato"]], "Persone": c["Persone"], "Non in regola": c["Persone non in regola"], "Doc. mancanti": c["Documenti mancanti"],
                                        "Doc. scaduti": c["Documenti scaduti"]} for c in out["cantieri"]]), hide_index=True, width="stretch")
            ren = [{"Persona": d["Persona"], "Cantiere": d["Cantiere"], "Documento": d["Documento"], "Scadenza": d["Scadenza"], "Giorni": d["Giorni"], "Stato": ICONE[d["Stato"]]}
                   for d in sorted(out["scadenze"], key=lambda x: (x["Giorni"] is None, x["Giorni"] or 0)) if d["Stato"] in ("bad", "warn")]
            st.markdown("**Da rinnovare**")
            st.dataframe(pd.DataFrame(ren), hide_index=True, width="stretch") if ren else st.success("Nessuna scadenza imminente.")

    with t3:
        if not pers and not docc:
            st.info("Aggiungi dei dati per generare il dossier.")
        else:
            scarica_dossier("sx", lambda n: ops_report.report_sx(out, n), "Sicurezza", audit, "Sicurezza e documenti di cantiere")
        st.caption("Promemoria delle scadenze inserite: non sostituisce il RSPP, il coordinatore per la sicurezza né la verifica degli obblighi di legge.")
