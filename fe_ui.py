"""fe_ui.py - Interfaccia di «Fatture elettroniche»."""
import io

import pandas as pd
import streamlit as st

import fe
import guida
import sc
import storage
import theme
from ui_util import cantieri_rubrica, sola_lettura, sostituisci_tabella

ss = st.session_state


def _esistenti():
    """Documenti gia' nello Scadenzario: dalla sessione se aperto, altrimenti dall'ultimo salvataggio."""
    try:
        if "sc_df" in ss and not ss.get("sc_demo"):
            return ss["sc_df"].to_dict("records")
        el = storage.elenca_pratiche(modulo="sc")
        return (storage.carica_pratica(el[0]["nome"], modulo="sc") or {}).get("docs", []) if el else []
    except Exception:
        return []


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Fatture elettroniche", "Carichi i file XML delle fatture e le scadenze finiscono nello Scadenzario, con il cantiere giusto."), unsafe_allow_html=True)
    guida.mostra("fe")
    files = st.file_uploader("Carica le fatture (file XML, .p7m o uno ZIP con tante fatture)", type=["xml", "p7m", "zip"], accept_multiple_files=True, key="fe_up")
    direzione = st.radio("Sono fatture…", ["Passiva", "Attiva"], format_func=lambda x: "ricevute dai fornitori (da pagare)" if x == "Passiva" else "emesse ai clienti (da incassare)", horizontal=True, key="fe_dir")
    if not files:
        st.info("Scarica le fatture dal cassetto fiscale o dal tuo programma di fatturazione (formato XML) e trascinale qui. Posso leggerne anche molte insieme in un file ZIP.")
        return
    fatture, errori = [], []
    for f in files:
        a, e = fe.leggi_file(f.name, f.getvalue())
        fatture += a
        errori += e
    for e in errori:
        st.warning(e)
    if not fatture:
        return
    cantieri = cantieri_rubrica()
    codici = [""] + [c["Codice"] for c in cantieri if c.get("Codice")]
    dup = {id(x) for x in fe.duplicati(fatture, _esistenti())}
    righe = [{"Includi": id(f) not in dup and not f["nota_credito"], "Fornitore": f["fornitore"], "Cliente": f["cliente"], "Numero": f["numero"], "Data": f["data"],
              "Totale": f["totale"], "Scadenze": " · ".join(f"{s['data']} {s['importo']:.2f}" for s in f["scadenze"]) or "(non indicata)",
              "Cantiere": fe.suggerisci_cantiere(f, cantieri), "Nota": "già nello Scadenzario" if id(f) in dup else "nota di credito" if f["nota_credito"] else ""} for f in fatture]
    st.markdown(f"**{len(fatture)} fatture lette.** Controlla il cantiere di ognuna: se nel testo c'è il codice del cantiere lo propongo io.")
    mod = st.data_editor(pd.DataFrame(righe), hide_index=True, width="stretch", key=f"fe_ed_{len(fatture)}_{direzione}", disabled=["Fornitore", "Cliente", "Numero", "Data", "Totale", "Scadenze", "Nota"],
                         column_config={"Cantiere": st.column_config.SelectboxColumn("Cantiere", options=codici), "Totale": st.column_config.NumberColumn("Totale €", format="%.2f"),
                                        "Includi": st.column_config.CheckboxColumn("Includi")})
    scelte = [i for i, r in enumerate(mod.to_dict("records")) if r["Includi"]]
    cant = {i: mod.iloc[i]["Cantiere"] or "" for i in scelte}
    nuove, avvisi = fe.a_scadenzario([fatture[i] for i in scelte], direzione, {k: cant[i] for k, i in enumerate(scelte)})
    for a in avvisi:
        st.caption(f"ℹ️ {a}")
    b1, b2 = st.columns(2)
    if b1.button(f"➕ Aggiungi {len(nuove)} scadenze allo Scadenzario", key="fe_to_sc", type="primary", disabled=not nuove or sola_lettura()):
        if "sc_df" not in ss or ss.get("sc_demo"):
            ss["sc_df"] = pd.DataFrame(columns=sc.COLONNE_DOC)
            ss["sc_demo"] = False
        sostituisci_tabella("sc_df", pd.concat([ss["sc_df"], pd.DataFrame(nuove, columns=sc.COLONNE_DOC)], ignore_index=True))
        audit("fe_to_sc", f"{len(nuove)} scadenze")
        st.success(f"Aggiunte {len(nuove)} righe allo Scadenzario. Aprilo e premi Salva per tenerle.")
    out = io.BytesIO()
    pd.DataFrame(righe).to_excel(out, index=False, sheet_name="Fatture")
    b2.download_button("⬇️ Scarica l'elenco in Excel", out.getvalue(), "fatture_lette.xlsx", key="fe_xl", width="stretch")
