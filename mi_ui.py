"""mi_ui.py - Interfaccia di «Controllo impianti ESCo»."""
import datetime as dt

import pandas as pd
import streamlit as st

import guida
import mi
import theme
from ui_util import sola_lettura

ss = st.session_state
ICONA = {"ok": "🟢", "warn": "🟡", "bad": "🔴", "manca": "⚪"}


def _df_impianti(imp):
    return pd.DataFrame([{"Nome": i["nome"], "Cliente": i["cliente"], "kWp": i["kwp"], "Inizio": i["inizio"], "Attesa annua kWh": i["attesa_annua"], "Canone mensile €": i["canone"],
                          "Prossima manutenzione": i["manutenzione"]} for i in imp], columns=mi.COLONNE)


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    nome = utente.get("username", "") if isinstance(utente, dict) else str(utente or "")
    st.markdown(theme.hero(fcr_uri, "Controllo impianti ESCo", "Dopo la vendita: l'impianto produce quanto promesso? Il canone è stato incassato? La manutenzione è in regola?"), unsafe_allow_html=True)
    guida.mostra("mi")
    imp = mi.carica()
    oggi = dt.date.today()
    t1, t2, t3 = st.tabs(["📊 1. Situazione", "✏️ 2. Letture e incassi", "🏭 3. Impianti"])
    with t1:
        r = mi.riepilogo(imp, oggi)
        st.markdown(theme.stat_strip([
            {"label": "Impianti", "value": str(r["impianti"]), "sub": f"{r['kwp']} kWp in tutto", "tono": "info"},
            {"label": "Produzione", "value": f"{r['perc']:.0f}%" if r["perc"] is not None else "—", "sub": "di quella attesa (12 mesi)", "tono": mi.stato_perc(r["perc"]) if r["perc"] is not None else "info"},
            {"label": "Canoni da incassare", "value": str(r["insoluti"]), "sub": "mesi non incassati", "tono": "bad" if r["insoluti"] else "ok"},
            {"label": "Da guardare", "value": str(r["avvisi"]), "sub": "avvisi", "tono": "warn" if r["avvisi"] else "ok"},
        ]), unsafe_allow_html=True)
        if not imp:
            st.info("Non c'è ancora nessun impianto. Aggiungilo nella scheda «3».")
        for stato, frase in mi.avvisi(imp, oggi):
            (st.error if stato == "bad" else st.warning)(frase)
        for i in imp:
            a = mi.analisi(i, oggi)
            with st.expander(f"{i['nome']} · {i['cliente']}"):
                if not a:
                    st.caption("Nessun mese concluso da controllare.")
                    continue
                st.dataframe(pd.DataFrame([{"": ICONA[x["stato"]], "Mese": mi.etichetta_mese(x["mese"]), "Atteso kWh": x["atteso"], "Letto kWh": x["letto"], "% atteso": x["perc"],
                                            "Canone €": x["canone"], "Incassato €": x["incassato"], "Canone": "✅" if x["canone_ok"] else "❌"} for x in a]), hide_index=True, width="stretch")
                g, s = mi.manutenzione(i, oggi)
                if g is not None:
                    st.caption(f"{ICONA[s]} Manutenzione: {i['manutenzione']} ({'scaduta' if g < 0 else f'tra {g} giorni'})")
        if imp:
            st.download_button("⬇️ Scarica in Excel", mi.excel_bytes(imp, oggi), "impianti_esco.xlsx", key="mi_xl")
    with t2:
        if not imp:
            st.info("Aggiungi prima un impianto nella scheda «3».")
        else:
            sel = st.selectbox("Impianto", [i["id"] for i in imp], format_func=lambda x: next(i["nome"] for i in imp if i["id"] == x), key="mi_sel")
            cur = next(i for i in imp if i["id"] == sel)
            mesi = mi.mesi_chiusi(cur, oggi, 24)[::-1]
            df = pd.DataFrame([{"Mese": m, "Letto kWh": cur["letture"].get(m), "Incassato €": cur["incassi"].get(m)} for m in mesi])
            st.caption("Scrivi quanto ha prodotto l'impianto (dal portale dell'inverter o dal contatore) e quanto hai incassato di canone. Solo i mesi già conclusi.")
            mod = st.data_editor(df, hide_index=True, disabled=["Mese"], width="stretch", key=f"mi_ed_{sel}",
                                 column_config={"Letto kWh": st.column_config.NumberColumn(min_value=0.0, format="%.0f"), "Incassato €": st.column_config.NumberColumn(min_value=0.0, format="%.2f")})
            if st.button("💾 Salva letture e incassi", key="mi_salva_l", type="primary", disabled=sola_lettura()):
                cur["letture"] = {r["Mese"]: r["Letto kWh"] for r in mod.to_dict("records") if pd.notna(r["Letto kWh"])}
                cur["incassi"] = {r["Mese"]: r["Incassato €"] for r in mod.to_dict("records") if pd.notna(r["Incassato €"])}
                mi.salva(imp, nome)
                audit("mi_letture", cur["nome"])
                st.success("Salvato.")
                st.rerun()
    with t3:
        st.caption("Un impianto per riga. «Attesa annua» è quanto doveva produrre in un anno: se la lasci a 0 uso 1.200 kWh per ogni kWp.")
        mod = st.data_editor(_df_impianti(imp), num_rows="dynamic", hide_index=True, width="stretch", key="mi_anag",
                             column_config={"kWp": st.column_config.NumberColumn(min_value=0.0), "Attesa annua kWh": st.column_config.NumberColumn(min_value=0.0),
                                            "Canone mensile €": st.column_config.NumberColumn(min_value=0.0),
                                            "Inizio": st.column_config.TextColumn(help="AAAA-MM-GG"), "Prossima manutenzione": st.column_config.TextColumn(help="AAAA-MM-GG")})
        if st.button("💾 Salva gli impianti", key="mi_salva_a", type="primary", disabled=sola_lettura()):
            vecchi = {i["nome"]: i for i in imp}
            nuovi = []
            for r in mod.to_dict("records"):
                if not str(r.get("Nome") or "").strip() or r.get("Nome") is None:
                    continue
                base = vecchi.get(str(r["Nome"]).strip()) or mi.nuovo()
                nuovi.append(dict(base, nome=r["Nome"], cliente=r["Cliente"] or "", kwp=r["kWp"], inizio=r["Inizio"] or "", attesa_annua=r["Attesa annua kWh"],
                                  canone=r["Canone mensile €"], manutenzione=r["Prossima manutenzione"] or ""))
            mi.salva(nuovi, nome)
            audit("mi_impianti", f"{len(nuovi)} impianti")
            st.success("Salvato.")
            st.rerun()
