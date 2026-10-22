"""rc_ui.py - Interfaccia del Registro commerciale."""
import datetime as dt

import pandas as pd
import streamlit as st
import guida

import rc
import theme
from ui_util import pannello_archivio, sola_lettura, sostituisci_tabella, tabella_modificabile

ss = st.session_state
ICONE = {"ok": "🟢", "warn": "🟡", "bad": "🔴", "nd": "⚪"}
NUMERICHE = ("Valore", "Successo", "UI", "Revisioni")


def _df(righe):
    d = pd.DataFrame(righe or [], columns=rc.COLONNE)
    for c in NUMERICHE:
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0.0)
    return d


def _cfg():
    t, n, s = st.column_config.TextColumn, st.column_config.NumberColumn, st.column_config.SelectboxColumn
    e = rc.ETICHETTE
    cfg = {c: t(e[c]) for c in rc.COLONNE}
    cfg.update({"Stato": s(e["Stato"], options=rc.STATI), "Prossimo": s(e["Prossimo"], options=rc.STATI), "Archivio": s(e["Archivio"], options=rc.ARCHIVI, required=True),
                "Valore": n(e["Valore"], min_value=0.0, format="%.0f"), "Successo": n(e["Successo"], min_value=0.0, max_value=100.0, format="%.0f"),
                "UI": n(e["UI"], min_value=0, step=1, format="%d"), "Revisioni": n(e["Revisioni"], min_value=0, step=1, format="%d"),
                "Lavori": t(e["Lavori"], width="medium"), "Note": t(e["Note"], width="large"), "Indirizzo": t(e["Indirizzo"], width="medium"),
                "Inserita": t(e["Inserita"], help="AAAA-MM-GG o GG/MM/AAAA"), "Sopralluogo": t(e["Sopralluogo"], help="AAAA-MM-GG o GG/MM/AAAA"),
                "Offerta": t(e["Offerta"], help="AAAA-MM-GG o GG/MM/AAAA"), "Scadenza": t(e["Scadenza"], help="AAAA-MM-GG o GG/MM/AAAA")})
    return cfg


def _raccogli():
    return {"pratiche": ss["rc_df"].to_dict("records"), "params": {"preavviso_gg": ss.get("rc_preavviso_gg", rc.RC_DEFAULT["preavviso_gg"])}}


def _applica(p, nome):
    sostituisci_tabella("rc_df", _df(p.get("pratiche")))
    ss["_pending"] = {"rc_preavviso_gg": (p.get("params") or {}).get("preavviso_gg", rc.RC_DEFAULT["preavviso_gg"])}


def unisci(attuali, nuove):
    """Aggiorna le pratiche con lo stesso codice e aggiunge quelle nuove. Le righe senza codice si aggiungono sempre."""
    per_cod = {(r["Codice"].lower(), r["Archivio"]): i for i, r in enumerate(attuali) if r["Codice"]}
    out = [dict(r) for r in attuali]
    for r in nuove:
        k = (r["Codice"].lower(), r["Archivio"])
        if r["Codice"] and k in per_cod:
            out[per_cod[k]] = r
        else:
            out.append(r)
    return out


def _euro(v):
    return f"{v:,.0f} €".replace(",", ".")


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Registro commerciale", "Tutte le pratiche dalla prima richiesta al contratto: a che punto sono, quanto valgono e cosa va fatto adesso."), unsafe_allow_html=True)
    guida.mostra("rc")
    if "rc_df" not in ss:
        ss["rc_df"] = _df([])
    ss.setdefault("rc_preavviso_gg", rc.RC_DEFAULT["preavviso_gg"])
    pannello_archivio("rc", "il registro", _raccogli, _applica, audit, utente)
    righe, avv = rc.normalizza(ss["rc_df"].to_dict("records"))
    out = rc.calcola(righe, dt.date.today(), {"preavviso_gg": ss["rc_preavviso_gg"]})
    k = out["kpi"]
    t1, t2, t3, t4 = st.tabs(["📊 1. Cruscotto", "📋 2. Pratiche", "⏰ 3. Da fare", "📥 4. Importa dal tuo Excel"])

    with t1:
        if not righe:
            st.info("Il registro è vuoto. Vai nella scheda «4. Importa dal tuo Excel» e carica il file del registro commerciale, oppure scrivi le pratiche nella scheda «2».")
        else:
            st.markdown(theme.stat_strip([
                {"label": "Pratiche attive", "value": str(k["n_attive"]), "sub": f"{k['n_eliminate']} eliminate", "tono": "ok"},
                {"label": "Valore in corso", "value": _euro(k["valore_aperte"]), "sub": f"{k['n_aperte']} pratiche aperte", "tono": "ok"},
                {"label": "Pipeline pesata", "value": _euro(k["pipeline"]), "sub": "valore × % di successo", "tono": "ok"},
                {"label": "Interventi scaduti", "value": str(k["n_scadute"]), "sub": f"{k['n_in_scadenza']} in arrivo", "tono": "bad" if k["n_scadute"] else "ok"}]), unsafe_allow_html=True)
            for a in out["avvisi"]:
                st.warning(a)
            for a in avv[:3]:
                st.caption("⚠️ " + a)
            c1, c2 = st.columns([2, 3])
            ps = pd.DataFrame(out["per_stato"])
            c1.markdown("**Pratiche per stato**")
            c1.bar_chart(ps.set_index("Stato")["Pratiche"], horizontal=True, height=330)
            c2.markdown("**Valore e pipeline per stato**")
            c2.dataframe(ps.assign(Valore=ps["Valore"].map(_euro), Pipeline=ps["Pipeline"].map(_euro)), hide_index=True, width="stretch", height=330)
            st.markdown("**Per commerciale**")
            pc = pd.DataFrame(out["per_commerciale"])
            st.dataframe(pc.assign(**{"Valore aperte": pc["Valore aperte"].map(_euro), "Pipeline": pc["Pipeline"].map(_euro)}), hide_index=True, width="stretch")
            if k["tasso_successo"] is not None:
                st.caption(f"Tasso di successo (contratti sul totale di contratti e offerte non accettate): {k['tasso_successo']:.0f}%")
            st.download_button("📥 Scarica il registro in Excel", rc.excel_bytes(righe, out), file_name=f"registro_commerciale_{dt.date.today().isoformat()}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="rc_dl")

    with t2:
        att = [r for r in righe]
        f1, f2, f3, f4 = st.columns([3, 2, 2, 1.4])
        q = f1.text_input("Cerca (città, indirizzo, amministratore, commerciale, codice…)", key="rc_cerca")
        stati = f2.multiselect("Stato", rc.STATI, key="rc_f_stato")
        cms = sorted({r["Commerciale"] or "(senza commerciale)" for r in att})
        com = f3.multiselect("Commerciale", cms, key="rc_f_comm")
        arch = f4.selectbox("Archivio", ["Attiva", "Eliminata"], key="rc_f_arch")
        ris = rc.filtra(righe, q, stati, com, arch)
        st.caption(f"{len(ris)} pratiche trovate.")
        if ris:
            vis = pd.DataFrame([{rc.ETICHETTE[c]: r[c] for c in ("Codice", "Stato", "Citta", "Indirizzo", "Amministratore", "Commerciale", "Lavori", "Valore", "Successo", "Prossimo", "Scadenza", "Note")}
                                | {"Pipeline": rc.pipeline(r)} for r in ris])
            st.dataframe(vis, hide_index=True, width="stretch", height=320)
        with st.expander("✏️ Modifica tutte le pratiche (aggiungi righe, cambia stato, sposta tra attive ed eliminate)"):
            tabella_modificabile("rc_df", ss["rc_df"], _cfg(), altezza=420)
            st.caption("Per eliminare una pratica dal registro senza perderla, cambia «Archivio» in «Eliminata». Il cestino della tabella la cancella del tutto.")

    with t3:
        st.number_input("Preavviso (giorni)", 0, 60, step=1, key="rc_preavviso_gg")
        df_ = out["da_fare"]
        if not df_:
            st.success("Nessun prossimo intervento in programma.")
        else:
            chi = st.multiselect("Chi lo deve fare", sorted({d["Chi"] or "(nessuno)" for d in df_}), key="rc_f_chi")
            vis = [d for d in df_ if not chi or (d["Chi"] or "(nessuno)") in chi]
            st.dataframe(pd.DataFrame([{"": ICONE[d["Stato_scad"]], "Codice": d["Codice"], "Indirizzo": d["Indirizzo"], "Ora in": d["Stato"], "Prossimo": d["Prossimo"], "Scadenza": d["Scadenza"],
                                        "Giorni": d["Giorni"], "Chi": d["Chi"]} for d in vis]), hide_index=True, width="stretch")
            st.caption("🔴 scaduto · 🟡 in arrivo · 🟢 più avanti · ⚪ senza data. Aggiorna la scadenza nella scheda «2. Pratiche» quando l'intervento è fatto.")

    with t4:
        st.markdown("Carica il file Excel del registro commerciale. L'app legge i fogli **Registro** ed **Eliminati**, riconosce da sola le colonne e ricalcola il valore pipeline.")
        if sola_lettura():
            st.caption("Importazione non disponibile per il ruolo «lettore».")
        else:
            up = st.file_uploader("File del registro (.xlsx)", type=["xlsx"], key="rc_file")
            if up is not None:
                try:
                    nuove, avvi, rapp = rc.importa_excel(up)
                except Exception as e:
                    st.error(f"File non leggibile: {e}")
                    nuove = []
                if nuove:
                    st.success(f"Letti {rapp['righe']} pratiche attive e {rapp['eliminate']} eliminate dai fogli: {', '.join(rapp['fogli'])}.")
                    for a in avvi[:8]:
                        st.caption("⚠️ " + a)
                    modo = st.radio("Cosa fare con quelle già presenti", ["Aggiorna per codice e aggiungi le nuove", "Sostituisci tutto"], key="rc_modo")
                    if st.button("Importa nel registro", type="primary", key="rc_importa"):
                        att = [r for r in rc.normalizza(ss["rc_df"].to_dict("records"))[0]]
                        fin = nuove if modo == "Sostituisci tutto" else unisci(att, nuove)
                        sostituisci_tabella("rc_df", _df(fin))
                        audit("rc_import", f"{up.name}: {len(nuove)} righe")
                        st.rerun()
                elif up is not None:
                    st.error("Non ho trovato le colonne del registro (Codice, Stato, Commerciale…). Controlla che sia il file giusto.")
