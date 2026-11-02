"""fc_ui.py - Interfaccia del Flusso commessa (schema FCR rev. 3.8, 28 passaggi)."""
import datetime as dt

import pandas as pd
import streamlit as st

import fc
import guida
import theme
from ui_util import pannello_archivio, sola_lettura, sostituisci_tabella, tabella_modificabile

ss = st.session_state
ICONE = {"Da fare": "⚪", "In corso": "🔵", "Fatto": "🟡", "Approvato": "🟢", "NO GO": "🔴", "Non necessario": "➖"}
ICONE_STATO = {"Ferma (NO GO)": "🔴", "Ferma da troppo tempo": "🟠", "In attesa di approvazione": "🟡", "In corso": "🔵", "Chiusa": "🟢"}


def _df(righe):
    return pd.DataFrame(righe or [], columns=fc.COLONNE)


def _raccogli():
    return {"passi": ss["fc_df"].to_dict("records"), "params": {"fermo_gg": ss.get("fc_fermo_gg", fc.FC_DEFAULT["fermo_gg"])}}


def _applica(p, nome):
    sostituisci_tabella("fc_df", _df(p.get("passi")))
    ss["_pending"] = {"fc_fermo_gg": (p.get("params") or {}).get("fermo_gg", fc.FC_DEFAULT["fermo_gg"])}


def _codici_registro():
    """Codici madre delle pratiche attive nell'ultimo Registro commerciale salvato (o in quello aperto adesso)."""
    try:
        import rc
        if "rc_df" in ss and len(ss["rc_df"]):
            righe, _ = rc.normalizza(ss["rc_df"].to_dict("records"))
        else:
            import storage
            elenco = storage.elenca_pratiche(modulo="rc")
            righe, _ = rc.normalizza((storage.carica_pratica(elenco[0]["nome"], modulo="rc") or {}).get("pratiche")) if elenco else ([], [])
        return fc.codici_da_registro(righe), {r["Codice"]: r for r in righe}
    except Exception:
        return [], {}


def _salva_passi(righe_tutte, codice, passi):
    """Rimette i passi modificati di una commessa nella tabella generale."""
    altri = [r for r in righe_tutte if r["Codice"] != codice]
    sostituisci_tabella("fc_df", _df(altri + [passi[n] for n in sorted(passi)]))


def _scheda(codice, passi, righe, utente, audit):
    s = fc.stato_commessa(passi, dt.date.today(), ss["fc_fermo_gg"])
    st.markdown(f"### {ICONE_STATO.get(s['stato'], '⚪')} {codice}")
    st.progress(s["avanzamento"] / 100, text=f"{s['fatti']} passaggi su {s['totale']} · {s['avanzamento']}%")
    if s["corrente"]:
        st.caption(f"Adesso: passo {s['corrente']} «{s['titolo_corrente']}» · responsabile {s['chi']} · stato commessa: {s['stato']}"
                   + (f" · ultimo aggiornamento {s['giorni_fermo']} giorni fa" if s["giorni_fermo"] else ""))
        st.caption(f"Nel Registro commerciale questa pratica dovrebbe essere allo stato **{fc.stato_dal_passo(s['corrente'])}**.")
    ini = st.text_input("Le tue iniziali (vanno scritte accanto a ogni passaggio)", fc.iniziali(utente), max_chars=6, key="fc_ini")
    solo_lettura = sola_lettura()
    for n in sorted(passi):
        r, d = passi[n], fc.PASSO[n]
        titolo = f"{ICONE[r['Stato']]} {n}. {d['titolo']}"
        with st.expander(titolo, expanded=(n == s["corrente"])):
            st.caption(f"**Chi:** {d['chi']}  ·  {d['cosa']}" + (f"  ·  Strumento: {d['strumento']}" if d["strumento"] else ""))
            if n in fc.GATE:
                st.caption("🚦 Decisione: finché non è approvata, i passaggi successivi non si possono completare.")
            traccia = []
            if r["Titolare"]:
                traccia.append(f"fatto da **{r['Titolare']}** il {r['Data titolare']}")
            if r["Approvatore"]:
                traccia.append(f"{'NO GO' if r['Stato'] == 'NO GO' else 'approvato'} da **{r['Approvatore']}** il {r['Data approvazione']}")
            if r["Esecutore"]:
                traccia.append(f"eseguito da **{r['Esecutore']}** il {r['Data esecuzione']}")
            st.markdown(f"Stato: **{r['Stato']}**" + (" · " + " · ".join(traccia) if traccia else ""))
            if r["Note"]:
                st.info(r["Note"])
            if solo_lettura:
                continue
            nota = st.text_input("Nota" + (" (obbligatoria per il NO GO)" if n in fc.NO_GO else ""), "", key=f"fcn_{codice}_{n}")
            rif = ""
            if n in (15, 16, 25):
                rif = st.text_input("Contratto / identificativo dell'operazione", r["Riferimento"], key=f"fcr_{codice}_{n}")
            azioni = []
            if r["Stato"] == "Da fare":
                azioni.append(("▶️ Avvia", "avvia"))
            if n in fc.NO_GO:
                if r["Stato"] not in ("Approvato", "NO GO"):
                    azioni += [("✅ GO (approvato)", "approva"), ("⛔ NO GO", "nogo")]
            else:
                if r["Stato"] in ("Da fare", "In corso"):
                    azioni.append(("✔️ Segna fatto", "fatto"))
                if n in fc.APPROVAZIONE and r["Stato"] == "Fatto":
                    azioni.append(("✅ Approva", "approva"))
            if n in fc.FACOLTATIVI and r["Stato"] in ("Da fare", "In corso"):
                azioni.append(("➖ Non necessario", "non_necessario"))
            if r["Stato"] in ("Fatto", "Approvato", "NO GO", "Non necessario"):
                azioni.append(("↩️ Riapri", "riapri"))
            cols = st.columns(max(len(azioni), 1))
            for col, (et, az) in zip(cols, azioni):
                if col.button(et, key=f"cmd_fc_{codice}_{n}_{az}", width="stretch"):
                    if az == "nogo" and not nota.strip():
                        st.warning("Scrivi nella nota il motivo del NO GO.")
                        continue
                    ok, msg = fc.registra(passi, n, az, ini, dt.date.today(), rif, nota.strip())
                    if ok:
                        if n in fc.CON_ESECUTORE and az == "fatto":
                            passi[n].update({"Esecutore": ini.upper(), "Data esecuzione": dt.date.today().isoformat()})
                        _salva_passi(righe, codice, passi)
                        audit("fc_passo", f"{codice} passo {n}: {az}")
                        st.toast(msg)
                        st.rerun()
                    else:
                        st.warning(msg)
            if n in fc.CON_ESECUTORE and r["Stato"] in ("Da fare", "In corso", "Fatto"):
                st.caption("Per i bonifici l'esecutore e la data si registrano con «Segna fatto»: scrivi sopra l'identificativo dell'operazione.")


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Flusso commessa", "I 28 passaggi dello schema FCR, dal primo incontro alla chiusura: chi fa cosa, chi approva e cosa blocca."), unsafe_allow_html=True)
    guida.mostra("fc")
    if "fc_df" not in ss:
        ss["fc_df"] = _df([])
    ss.setdefault("fc_fermo_gg", fc.FC_DEFAULT["fermo_gg"])
    pannello_archivio("fc", "il flusso delle commesse", _raccogli, _applica, audit, utente)
    righe, avv = fc.normalizza(ss["fc_df"].to_dict("records"))
    out = fc.calcola(righe, dt.date.today(), {"fermo_gg": ss["fc_fermo_gg"]})
    k = out["kpi"]
    t1, t2, t3, t4 = st.tabs(["📊 1. Cruscotto", "🧭 2. Scheda commessa", "🔎 3. Controlli", "📋 4. Tabella e Excel"])

    with t1:
        if not righe:
            st.info("Nessuna commessa nel flusso. Vai nella scheda «2. Scheda commessa» e avvia la prima scegliendo il codice dal Registro commerciale.")
        else:
            st.markdown(theme.stat_strip([
                {"label": "Commesse nel flusso", "value": str(k["commesse"]), "sub": f"{k['in_corso']} in corso, {k['chiuse']} chiuse", "tono": "ok"},
                {"label": "In attesa di approvazione", "value": str(k["attesa_appr"]), "sub": "passaggio fatto, manca l'approvazione", "tono": "warn" if k["attesa_appr"] else "ok"},
                {"label": "Ferme da troppo tempo", "value": str(k["ferme"]), "sub": f"nessun aggiornamento da oltre {ss['fc_fermo_gg']} giorni", "tono": "warn" if k["ferme"] else "ok"},
                {"label": "Ferme per NO GO", "value": str(k["ferme_nogo"]), "sub": "decisione negativa", "tono": "bad" if k["ferme_nogo"] else "ok"}]), unsafe_allow_html=True)
            df = pd.DataFrame(out["commesse"])
            df.insert(1, " ", df["Stato"].map(ICONE_STATO))
            st.dataframe(df, hide_index=True, width="stretch", column_config={
                "Avanzamento": st.column_config.ProgressColumn("Avanzamento", min_value=0, max_value=100, format="%d%%"),
                "Passo": st.column_config.NumberColumn("N°", format="%d"), "Giorni": st.column_config.NumberColumn("Giorni dall'ultimo aggiornamento", format="%d")})
            for c in out["controlli"][:3]:
                st.caption(("🔴 " if c["gravita"] == "bad" else "🟠 ") + f"{c['codice']}: {c['messaggio']}")
        ss["fc_fermo_gg"] = int(st.number_input("Giorni senza aggiornamenti dopo i quali una commessa è «ferma»", 3, 90, int(ss["fc_fermo_gg"]), 1, key="fc_fermo_in"))

    with t2:
        esistenti = sorted({r["Codice"] for r in righe})
        reg, _info = _codici_registro()
        nuovi = [c for c in reg if c not in esistenti]
        with st.expander("➕ Avvia il flusso di una nuova commessa", expanded=not esistenti):
            st.caption("Il codice madre è quello della pratica nel Registro commerciale e non cambia più fino alla chiusura.")
            scelta = st.selectbox("Pratica del Registro commerciale", ["—"] + nuovi, key="fc_nuovo_sel") if nuovi else "—"
            libero = st.text_input("Oppure scrivi un codice madre", "", key="fc_nuovo_txt", placeholder="es. 002-MI-MILLELIRE")
            cod = (libero.strip() if libero.strip() else (scelta if scelta != "—" else ""))
            if st.button("Avvia il flusso", type="primary", key="cmd_fc_avvia", disabled=sola_lettura() or not cod):
                if cod.lower() in {c.lower() for c in esistenti}:
                    st.warning("Questa commessa è già nel flusso.")
                else:
                    sostituisci_tabella("fc_df", _df(righe + fc.avvia(cod)))
                    audit("fc_avvio", cod)
                    st.toast(f"Flusso avviato per {cod}")
                    st.rerun()
        if not esistenti:
            st.info("Avvia una commessa per vedere i suoi 28 passaggi.")
        else:
            cm = st.selectbox("Commessa", esistenti, key="fc_sel")
            passi = {int(r["Passo"]): dict(r) for r in righe if r["Codice"] == cm}
            _scheda(cm, passi, righe, utente, audit)

    with t3:
        if not righe:
            st.info("Avvia almeno una commessa.")
        else:
            for a in avv[:3]:
                st.caption("⚠️ " + a)
            if not out["controlli"]:
                st.success("Nessuna anomalia: ogni passaggio ha iniziali, data e approvazioni nell'ordine previsto.")
            else:
                st.caption("Controlli sulle regole dello schema: traccia di ogni passaggio (iniziali e data), approvazioni, ordine dei passaggi e commesse ferme.")
                st.dataframe(pd.DataFrame([{"": "🔴" if c["gravita"] == "bad" else "🟠", "Commessa": c["codice"], "Passo": c["passo"], "Cosa non va": c["messaggio"]} for c in out["controlli"]]),
                             hide_index=True, width="stretch")

    with t4:
        st.caption("Tutti i passaggi in tabella: utile per correggere un dato a mano. Di norma si lavora dalla scheda commessa.")
        cfg = {c: st.column_config.TextColumn(fc.ETICHETTE[c]) for c in fc.COLONNE}
        cfg["Stato"] = st.column_config.SelectboxColumn("Stato", options=fc.STATI, required=True)
        cfg["Passo"] = st.column_config.NumberColumn("Passo", min_value=1, max_value=fc.N_PASSI, step=1, format="%d")
        tabella_modificabile("fc_df", _df([]), cfg, altezza=420)
        if righe:
            st.download_button("📥 Scarica in Excel", fc.excel_bytes(righe, out["commesse"]), file_name=f"flusso_commesse_{dt.date.today().isoformat()}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_fc_xlsx")
