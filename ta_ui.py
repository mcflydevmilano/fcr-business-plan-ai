"""ta_ui.py - Interfaccia di Compiti e attivita' (la bacheca dei compiti)."""
import datetime as dt

import pandas as pd
import streamlit as st

import guida
import ta
import theme
from ui_util import pannello_archivio, sola_lettura, sostituisci_tabella, tabella_modificabile

ss = st.session_state
SIMBOLO = {"Alta": "🔴", "Media": "🟠", "Bassa": "🟢"}
TESTA = {"Da fare": "⚪ Da fare", "In corso": "🔵 In corso", "In attesa": "🟡 In attesa", "Fatto": "🟢 Fatto"}
MAX_PER_COLONNA = 25


def _df(righe):
    return pd.DataFrame(righe or [], columns=ta.COLONNE)


def _raccogli():
    return {"compiti": ss["ta_df"].to_dict("records"), "params": {"preavviso_gg": ss.get("ta_preavviso_gg", ta.TA_DEFAULT["preavviso_gg"])}}


def _applica(p, nome):
    sostituisci_tabella("ta_df", _df(p.get("compiti")))
    ss["_pending"] = {"ta_preavviso_gg": (p.get("params") or {}).get("preavviso_gg", ta.TA_DEFAULT["preavviso_gg"])}


def _carte(df, utente):
    """[(indice nella tabella, compito pulito)] dei compiti validi."""
    out = []
    for i, r in df.iterrows():
        z = ta.riga(r.to_dict())
        if z and z["Compito"]:
            out.append((i, z))
    return out


def _sposta(i, nuovo, audit):
    df = ss["ta_df"].copy()
    z = ta.muovi(ta.riga(df.loc[i].to_dict()), nuovo)
    for c in ta.COLONNE:
        df.at[i, c] = z[c]
    sostituisci_tabella("ta_df", df)
    audit("ta_sposta", f"{z['Compito'][:50]} → {nuovo}")
    st.rerun()


def _bacheca(carte, oggi, audit, utente):
    resp = sorted({z["Responsabile"] for _i, z in carte if z["Responsabile"]})
    comm = sorted({z["Commessa"] for _i, z in carte if z["Commessa"]})
    f1, f2, f3, f4 = st.columns([2, 2, 3, 1.4])
    scelta = f1.selectbox("Responsabile", ["Tutti", "Solo i miei"] + resp, key="ta_f_resp")
    cm = f2.selectbox("Commessa", ["Tutte"] + comm, key="ta_f_comm")
    q = f3.text_input("Cerca", key="ta_f_q", placeholder="parola nel compito, nelle note…")
    solo_miei = scelta == "Solo i miei"
    f4.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
    lettura = sola_lettura()
    col = st.columns(len(ta.STATI))
    for c, stato in zip(col, ta.STATI):
        sel = [(i, z) for i, z in carte if z["Stato"] == stato]
        sel = [(i, z) for i, z in sel if (not solo_miei or utente.lower() in z["Responsabile"].lower()) and (scelta in ("Tutti", "Solo i miei") or z["Responsabile"] == scelta)
               and (cm == "Tutte" or z["Commessa"] == cm) and (not q.strip() or q.strip().lower() in " ".join(z.values()).lower())]
        if stato == "Fatto":
            sel = [(i, z) for i, z in sel if z["Chiuso"] and (oggi - dt.date.fromisoformat(z["Chiuso"])).days <= 14]
        sel.sort(key=lambda x: (x[1]["Scadenza"] or "9999-12-31", ta.PRIORITA.index(x[1]["Priorita"])))
        c.markdown(f"**{TESTA[stato]}** · {len(sel)}" + (" (ultimi 14 giorni)" if stato == "Fatto" else ""))
        for i, z in sel[:MAX_PER_COLONNA]:
            with c.container(border=True):
                rit = ta.in_ritardo(z, oggi)
                st.markdown(f"{SIMBOLO[z['Priorita']]} **{z['Compito']}**")
                righe = []
                if z["Responsabile"]:
                    righe.append(f"👤 {z['Responsabile']}")
                if z["Scadenza"]:
                    righe.append(("🔴 scaduto " if rit else "📅 ") + z["Scadenza"])
                if z["Commessa"]:
                    righe.append(f"🏗️ {z['Commessa']}")
                if righe:
                    st.caption("  ·  ".join(righe))
                if z["Note"]:
                    st.caption(z["Note"][:120])
                if not lettura:
                    k = ta.STATI.index(stato)
                    b1, b2 = st.columns(2)
                    if k > 0 and b1.button("◀", key=f"cmd_ta_{i}_i", help=f"Sposta in «{ta.STATI[k - 1]}»", width="stretch"):
                        _sposta(i, ta.STATI[k - 1], audit)
                    if k < len(ta.STATI) - 1 and b2.button("▶", key=f"cmd_ta_{i}_a", help=f"Sposta in «{ta.STATI[k + 1]}»", width="stretch"):
                        _sposta(i, ta.STATI[k + 1], audit)
        if len(sel) > MAX_PER_COLONNA:
            c.caption(f"+ altri {len(sel) - MAX_PER_COLONNA} nella scheda «2. Nuovo e tabella»")


def _nuovo(utente, audit):
    with st.form("ta_nuovo", clear_on_submit=True):
        t = st.text_input("Cosa c'è da fare", key="ta_n_titolo")
        a, b, c, d = st.columns(4)
        resp = a.text_input("Responsabile", utente, key="ta_n_resp")
        com = b.text_input("Commessa (codice madre)", "", key="ta_n_comm", placeholder="es. 002-MI-MILLELIRE")
        pri = c.selectbox("Priorità", ta.PRIORITA, index=1, key="ta_n_pri")
        scad = d.date_input("Scadenza", value=None, format="DD/MM/YYYY", key="ta_n_scad")
        note = st.text_input("Note", key="ta_n_note")
        ok = st.form_submit_button("➕ Aggiungi il compito", disabled=sola_lettura())
    if ok:
        if not t.strip():
            st.warning("Scrivi cosa c'è da fare.")
            return
        nuova = ta.riga({"Compito": t, "Commessa": com, "Responsabile": resp, "Priorita": pri, "Scadenza": scad.isoformat() if scad else "", "Note": note})
        sostituisci_tabella("ta_df", pd.concat([ss["ta_df"], _df([nuova])], ignore_index=True))
        audit("ta_nuovo", t[:60])
        st.toast("Compito aggiunto")
        st.rerun()


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Compiti e attività", "Cosa c'è da fare, chi lo fa e per quando: la bacheca di tutta l'azienda."), unsafe_allow_html=True)
    guida.mostra("ta")
    if "ta_df" not in ss:
        ss["ta_df"] = _df([])
    ss.setdefault("ta_preavviso_gg", ta.TA_DEFAULT["preavviso_gg"])
    pannello_archivio("ta", "i compiti", _raccogli, _applica, audit, utente)
    oggi = dt.date.today()
    righe, avv = ta.normalizza(ss["ta_df"].to_dict("records"))
    out = ta.calcola(righe, oggi, {"preavviso_gg": ss["ta_preavviso_gg"]})
    k = out["kpi"]
    t1, t2, t4 = st.tabs(["🗂️ 1. Bacheca", "➕ 2. Nuovo e tabella", "📊 3. Per persona"])

    with t1:
        st.markdown(theme.stat_strip([
            {"label": "Aperti", "value": str(k["aperti"]), "sub": f"{k['in_corso']} in corso, {k['in_attesa']} in attesa", "tono": "ok"},
            {"label": "In ritardo", "value": str(k["ritardo"]), "sub": "scadenza passata", "tono": "bad" if k["ritardo"] else "ok"},
            {"label": "In scadenza", "value": str(k["in_arrivo"]), "sub": f"entro {ss['ta_preavviso_gg']} giorni", "tono": "warn" if k["in_arrivo"] else "ok"},
            {"label": "Senza responsabile", "value": str(k["senza_resp"]), "sub": "da assegnare", "tono": "warn" if k["senza_resp"] else "ok"}]), unsafe_allow_html=True)
        if not righe:
            st.info("Nessun compito. Aggiungine uno nella scheda «2».")
        else:
            _bacheca(_carte(ss["ta_df"], utente), oggi, audit, utente)

    with t2:
        _nuovo(utente, audit)
        for a in avv[:3]:
            st.caption("⚠️ " + a)
        cfg = {c: st.column_config.TextColumn(ta.ETICHETTE[c]) for c in ta.COLONNE}
        cfg.update({"Stato": st.column_config.SelectboxColumn("Stato", options=ta.STATI), "Priorita": st.column_config.SelectboxColumn("Priorità", options=ta.PRIORITA),
                    "Compito": st.column_config.TextColumn("Compito", width="large"), "Note": st.column_config.TextColumn("Note", width="large"),
                    "Scadenza": st.column_config.TextColumn("Scadenza", help="AAAA-MM-GG o GG/MM/AAAA")})
        tabella_modificabile("ta_df", _df([]), cfg, altezza=380)
        ss["ta_preavviso_gg"] = int(st.number_input("Giorni di preavviso per le scadenze", 0, 30, int(ss["ta_preavviso_gg"]), 1, key="ta_prev_in"))

    with t4:
        if not righe:
            st.info("Nessun compito.")
        else:
            pr = pd.DataFrame(out["per_responsabile"])
            if len(pr):
                st.dataframe(pr, hide_index=True, width="stretch")
                st.bar_chart(pr.set_index("Responsabile")[["Aperti", "In ritardo"]], height=260)
            if out["ritardo"]:
                st.markdown("**In ritardo**")
                st.dataframe(pd.DataFrame([{"Compito": r["Compito"], "Responsabile": r["Responsabile"], "Scadenza": r["Scadenza"], "Commessa": r["Commessa"]} for r in ta.ordina(out["ritardo"])]),
                             hide_index=True, width="stretch")
            st.download_button("📥 Scarica in Excel", ta.excel_bytes(righe), file_name=f"compiti_{oggi.isoformat()}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_ta_xlsx")
