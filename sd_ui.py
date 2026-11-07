"""sd_ui.py - Interfaccia di «Scadenze di persone e mezzi»."""
import datetime as dt

import pandas as pd
import streamlit as st

import guida
import sd
import theme
from ui_util import sola_lettura

ss = st.session_state


def render(fcr_uri, audit, utente, profilo, utenti_secrets):
    audit = audit or (lambda *a, **k: None)
    nome = (utente or {}).get("username", "")
    st.markdown(theme.hero(fcr_uri, "Scadenze di persone e mezzi", "Formazione, visite mediche, DURC, assicurazioni, revisioni: tutto in un elenco, con l'avviso prima che scadano."), unsafe_allow_html=True)
    guida.mostra("sd")
    cfg = sd.carica()
    oggi = dt.date.today()
    el = sd.elenco(cfg["voci"], oggi, cfg["preavvisi"])
    r = sd.riepilogo(cfg["voci"], oggi, cfg["preavvisi"])
    t1, t2, t3 = st.tabs(["⏰ 1. Cosa scade", "✏️ 2. Elenco da modificare", "📥 3. Importa, esporta e regole"])

    with t1:
        st.markdown(theme.stat_strip([
            {"label": "Scaduti", "value": str(r["scaduto"]), "sub": "da rinnovare subito", "tono": "bad" if r["scaduto"] else "ok"},
            {"label": f"Entro {cfg['preavvisi'][0]} giorni", "value": str(r["urgente"]), "sub": "urgenti", "tono": "bad" if r["urgente"] else "ok"},
            {"label": f"Entro {cfg['preavvisi'][1] if len(cfg['preavvisi']) > 1 else 30} giorni", "value": str(r["vicino"]), "sub": "da programmare", "tono": "warn" if r["vicino"] else "ok"},
            {"label": f"Entro {cfg['preavvisi'][-1]} giorni", "value": str(r["attenzione"]), "sub": "in arrivo", "tono": "info"},
        ]), unsafe_allow_html=True)
        if not el:
            st.info("L'elenco è vuoto. Aggiungi la prima scadenza nella scheda «2», oppure carica il tuo Excel nella scheda «3».")
        else:
            c1, c2 = st.columns([2, 1])
            tipi = c1.multiselect("Tipo", sorted({v["Tipo"] for v in el}), key="sd_f_tipo", placeholder="Tutti")
            cerca = c2.text_input("Cerca persona o mezzo", key="sd_f_cerca")
            vis = [v for v in el if (not tipi or v["Tipo"] in tipi) and (not cerca or cerca.lower() in v["Soggetto"].lower())]
            st.dataframe(pd.DataFrame([{"": sd.STATI[v["stato"]][0], "Stato": sd.STATI[v["stato"]][1], "Tipo": v["Tipo"], "Persona o mezzo": v["Soggetto"], "Scadenza": v["Scadenza"],
                                        "Giorni": v["giorni"], "Responsabile": v["Responsabile"], "Note": v["Note"]} for v in vis]), hide_index=True, width="stretch")
            st.caption("🔴 scaduto · 🟠 entro il primo preavviso · 🟡 entro il secondo · 🟢 entro il terzo · ⚪ più avanti. Le scadenze vicine compaiono anche nel riepilogo del mattino.")

    with t2:
        if sola_lettura():
            st.info("Sei in sola lettura: non puoi modificare l'elenco.")
        st.markdown("**Aggiungi una scadenza**")
        noti = sd.soggetti_noti()
        with st.form("sd_nuova", clear_on_submit=True):
            a, b, c = st.columns(3)
            tipo = a.selectbox("Tipo", sd.TIPI, key="sd_n_tipo")
            sogg = b.selectbox("Persona o mezzo", noti, index=None, accept_new_options=True, placeholder="Scegli o scrivi (nome, targa, ditta)", key="sd_n_sogg")
            scad = c.date_input("Scadenza", value=None, format="DD/MM/YYYY", key="sd_n_scad")
            d, e = st.columns(2)
            resp = d.text_input("Responsabile (chi se ne occupa)", key="sd_n_resp")
            note = e.text_input("Note", key="sd_n_note")
            if st.form_submit_button("Aggiungi", type="primary") and not sola_lettura():
                if not sogg or not scad:
                    st.warning("Servono almeno la persona o il mezzo e la data di scadenza.")
                else:
                    cfg["voci"].append({"Tipo": tipo, "Soggetto": sogg, "Scadenza": scad.isoformat(), "Responsabile": resp, "Note": note})
                    sd.salva(cfg, nome)
                    audit("scadenza_aggiunta", f"{tipo} · {sogg}")
                    st.rerun()
        st.markdown("**Modifica l'elenco** (puoi correggere, aggiungere righe o cancellarle)")
        df = pd.DataFrame([{c: v.get(c, "") for c in sd.COLONNE} for v in cfg["voci"]], columns=sd.COLONNE)
        df["Scadenza"] = pd.to_datetime(df["Scadenza"], errors="coerce").dt.date
        mod = st.data_editor(df, num_rows="dynamic", hide_index=True, width="stretch", key="sd_ed",
                             column_config={"Tipo": st.column_config.SelectboxColumn("Tipo", options=sd.TIPI, required=True),
                                            "Scadenza": st.column_config.DateColumn("Scadenza", format="DD/MM/YYYY"),
                                            "Soggetto": st.column_config.TextColumn("Persona o mezzo")})
        if st.button("💾 Salva le modifiche", key="sd_salva", type="primary", disabled=sola_lettura()):
            ids = [v["id"] for v in cfg["voci"]]
            nuove = []
            for i, rr in enumerate(mod.to_dict("records")):
                rr["id"] = ids[i] if i < len(ids) and rr.get("Soggetto") == cfg["voci"][i]["Soggetto"] else ""
                nuove.append(rr)
            cfg["voci"] = nuove
            sd.salva(cfg, nome)
            audit("scadenze_salvate", f"{len(nuove)} voci")
            st.success("Elenco salvato.")
            st.rerun()

    with t3:
        up = st.file_uploader("Importa dal tuo Excel o CSV (colonne: Tipo, Persona/Mezzo, Scadenza, Responsabile, Note)", type=["xlsx", "xls", "csv"], key="sd_up")
        if up is not None:
            try:
                nuove = sd.da_excel(up)
                st.write(f"Trovate {len(nuove)} scadenze.")
                if nuove and st.button("Aggiungi all'elenco", key="sd_imp", type="primary", disabled=sola_lettura()):
                    cfg["voci"] = cfg["voci"] + nuove
                    sd.salva(cfg, nome)
                    audit("scadenze_importate", f"{len(nuove)} voci")
                    st.success("Importate.")
                    st.rerun()
            except Exception as ex:
                st.error(f"Non riesco a leggere il file: {ex}")
        st.download_button("⬇️ Scarica l'elenco in Excel", sd.excel_bytes(cfg["voci"], oggi, cfg["preavvisi"]), "scadenze_persone_e_mezzi.xlsx", key="sd_xl")
        st.divider()
        st.markdown("**Quando avvisare**")
        pre = st.multiselect("Giorni di preavviso (da 1 a 3 valori)", [90, 60, 45, 30, 21, 15, 10, 7, 3, 1], default=[p for p in cfg["preavvisi"] if p in (90, 60, 45, 30, 21, 15, 10, 7, 3, 1)], key="sd_pre", max_selections=3)
        if st.button("Salva i preavvisi", key="sd_pre_ok", disabled=sola_lettura()) and pre:
            cfg["preavvisi"] = sorted(pre)
            sd.salva(cfg, nome)
            st.success("Preavvisi salvati.")
            st.rerun()
