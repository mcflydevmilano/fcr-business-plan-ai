"""
admin_ui.py - Pannello di amministrazione (solo ruolo admin): utenti e registro attivita'.
Si usa da app.py:  admin_ui.render(utente_corrente, utenti_secrets, audit)
"""
import pandas as pd
import streamlit as st

import auth
import permessi
import storage


def render(utente, utenti_secrets, audit):
    st.markdown("## 👥 Amministrazione")
    if utente.get("ruolo") != "admin":
        st.error("Accesso riservato agli amministratori.")
        return
    t1, t2, t3, t4 = st.tabs(["Utenti", "Registro attività", "Backup", "🔒 Permessi"])

    with t1:
        st.markdown("#### Utenti configurati nei secrets")
        if utenti_secrets:
            st.dataframe(pd.DataFrame([{"Utente": n, "Ruolo": v["ruolo"], "Origine": "secrets (persistente)"} for n, v in utenti_secrets.items()]),
                         width="stretch", hide_index=True)
            st.caption("Si modificano o si revocano dai secrets dell'hosting (Settings → Secrets), rimuovendo la riga dell'utente.")
        else:
            st.info("Nessun utente nei secrets. Consigliato: aggiungi almeno un amministratore in `[users.nome]` (vedi README) "
                    "perche' gli utenti creati qui sotto sono salvati nel database e su hosting con disco temporaneo si perdono al riavvio.")

        st.markdown("#### Utenti creati dal pannello")
        utenti = storage.elenca_utenti()
        if utenti:
            st.dataframe(pd.DataFrame([{"Utente": u["username"], "Ruolo": u["ruolo"], "Stato": "attivo" if u["attivo"] else "revocato",
                                        "Creato": (u["creato"] or "")[:16], "Ultimo accesso": (u["ultimo_accesso"] or "mai")[:16]} for u in utenti]),
                         width="stretch", hide_index=True)
            sel = st.selectbox("Seleziona un utente", [u["username"] for u in utenti], key="adm_sel")
            rec = next(u for u in utenti if u["username"] == sel)
            c1, c2, c3 = st.columns(3)
            if rec["attivo"]:
                if c1.button("⛔ Revoca accesso", key="adm_revoca", width="stretch"):
                    storage.aggiorna_utente(sel, attivo=0)
                    audit("utente_revocato", sel)
                    st.rerun()
            elif c1.button("✅ Riattiva", key="adm_riattiva", width="stretch"):
                storage.aggiorna_utente(sel, attivo=1)
                audit("utente_riattivato", sel)
                st.rerun()
            if c2.button("🔑 Reimposta password", key="adm_reset", width="stretch"):
                tmp = auth.genera_password_temporanea()
                auth.reimposta_password(sel, tmp, utente["username"])
                st.session_state["adm_tmp"] = (sel, tmp)
            if c3.button("🗑️ Elimina", key="adm_elimina", width="stretch"):
                storage.elimina_utente(sel)
                audit("utente_eliminato", sel)
                st.rerun()
            nuovo_ruolo = st.radio("Ruolo", list(auth.RUOLI), index=list(auth.RUOLI).index(rec["ruolo"]), horizontal=True, key=f"adm_ruolo_{sel}")
            if nuovo_ruolo != rec["ruolo"]:
                storage.aggiorna_utente(sel, ruolo=nuovo_ruolo)
                audit("ruolo_cambiato", f"{sel} -> {nuovo_ruolo}")
                st.rerun()
        else:
            st.caption("Nessun utente creato dal pannello.")
        tmp = st.session_state.get("adm_tmp")
        if tmp:
            st.success(f"Password temporanea per **{tmp[0]}**: `{tmp[1]}` — comunicala all'utente: non verra' mostrata di nuovo "
                       "e va cambiata al primo accesso (barra laterale → Account).")

        st.markdown("#### Nuovo utente")
        with st.form("adm_nuovo", clear_on_submit=True):
            n1, n2, n3 = st.columns([2, 2, 1])
            nome = n1.text_input("Nome utente", placeholder="es. mario.rossi")
            pw = n2.text_input("Password iniziale", type="password", help=f"Almeno {auth.LUNGHEZZA_MIN_PASSWORD} caratteri, con lettere e numeri.")
            ruolo = n3.selectbox("Ruolo", list(auth.RUOLI), index=1)
            if st.form_submit_button("Crea utente"):
                try:
                    auth.crea_utente(nome, pw, ruolo, utente["username"])
                    st.success(f"Utente {auth.normalizza_username(nome)} creato.")
                except ValueError as e:
                    st.error(str(e))

    with t2:
        import datetime as _dt
        from zoneinfo import ZoneInfo
        st.caption("Qui trovi chi ha fatto cosa e quando: accessi, salvataggi (con l'elenco di cosa è cambiato), importazioni, report generati, avvisi inviati. Ogni salvataggio dice quali righe sono state aggiunte, tolte o modificate.")
        f1, f2, f3 = st.columns([2, 2, 2])
        utenti_log = [""] + sorted({e["Utente"] for e in storage.elenca_eventi(2000) if e["Utente"]})
        fu = f1.selectbox("Utente", utenti_log, format_func=lambda x: x or "Tutti", key="adm_f_utente")
        azioni_log = [""] + sorted({e["Azione"] for e in storage.elenca_eventi(2000)})
        fa = f2.selectbox("Azione", azioni_log, format_func=lambda x: {"": "Tutte", "modifiche_dati": "modifiche_dati (salvataggi)"}.get(x, x), key="adm_f_azione")
        cerca = f3.text_input("Cerca nel testo", key="adm_f_cerca", placeholder="es. Villa Lago, fattura, Rossi…")
        g1, g2, g3 = st.columns([2, 2, 2])
        da = g1.date_input("Dal giorno", value=None, key="adm_f_da")
        a_ = g2.date_input("Al giorno", value=None, key="adm_f_a")
        n = g3.number_input("Righe massime", 20, 5000, 300, 50, key="adm_f_n")
        ev = storage.elenca_eventi(int(n), fu or None, fa or None, da=da.isoformat() if da else None, a=a_.isoformat() if a_ else None, cerca=cerca or None)
        roma = ZoneInfo("Europe/Rome")

        def _ora(ts):
            try:
                return _dt.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_dt.timezone.utc).astimezone(roma).strftime("%d/%m/%Y %H:%M:%S")
            except ValueError:
                return ts
        df = pd.DataFrame([{"Data e ora (Italia)": _ora(e["Data (UTC)"]), "Utente": e["Utente"], "Azione": e["Azione"], "Cosa": e["Dettaglio"]} for e in ev],
                          columns=["Data e ora (Italia)", "Utente", "Azione", "Cosa"])
        st.dataframe(df, width="stretch", hide_index=True, column_config={"Cosa": st.column_config.TextColumn("Cosa", width="large")})
        if len(df):
            k = st.selectbox("Leggi per intero una riga", range(len(df)), format_func=lambda i: f"{df.iloc[i]['Data e ora (Italia)']} · {df.iloc[i]['Utente']} · {df.iloc[i]['Azione']}", key="adm_f_riga")
            st.info(str(df.iloc[k]["Cosa"]) or "—")
        d1, d2 = st.columns(2)
        d1.download_button("📥 Scarica il registro (CSV)", df.to_csv(index=False).encode("utf-8-sig"), file_name="registro_attivita.csv", mime="text/csv", width="stretch")
        import io
        buf = io.BytesIO()
        df.to_excel(buf, index=False, sheet_name="Registro")
        d2.download_button("📥 Scarica il registro (Excel)", buf.getvalue(), file_name="registro_attivita.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
        st.caption("Il registro non si può modificare dall'app. È nel database (Neon): resta anche dopo i riavvii. Le modifiche fatte nelle tabelle ma non salvate non compaiono finché qualcuno non preme Salva.")

    with t3:
        import json
        st.markdown("#### Copia di sicurezza dei dati")
        st.caption("Scarica tutte le pratiche, i portafogli, i preventivi, gli scadenzari, l'elenco utenti (senza password) e il registro attività. "
                   "Conservala in un posto sicuro: contiene dati dei clienti. Il piano gratuito del database non include backup automatici.")
        if st.button("Prepara il backup", key="adm_bk"):
            try:
                bk = storage.esporta_backup()
                st.session_state["adm_backup"] = json.dumps(bk, ensure_ascii=False, indent=1, default=str).encode("utf-8")
                audit("backup_esportato", f"{len(bk['pratiche'])} salvataggi")
            except Exception as e:
                st.error(f"Backup non riuscito: {e}")
        if st.session_state.get("adm_backup"):
            st.download_button("📥 Scarica il backup (JSON)", st.session_state["adm_backup"], file_name="backup_fcr_suite.json", mime="application/json")


    with t4:
        _permessi(utente, utenti_secrets, audit)


def _permessi(utente, utenti_secrets, audit):
    cfg = permessi.carica_config()
    st.markdown("#### Chi vede quali strumenti")
    st.caption("Ogni persona ha un **profilo**; ogni profilo apre solo gli strumenti spuntati. L'amministratore vede sempre tutto. "
               "Il **ruolo** (admin / utente / lettore) decide invece chi può modificare i dati: sono due cose separate. "
               "Il Cruscotto di direzione è riservato al profilo «presidente» (e all'amministratore).")
    nomi_profili = list(cfg["profili"])
    st.markdown("**1. Assegna un profilo a ciascun utente**")
    nomi_utenti = sorted({*(utenti_secrets or {}), *(u["username"] for u in storage.elenca_utenti()), *cfg["utenti"]})
    nuovi = dict(cfg["utenti"])
    try:
        import pe
        _pers = {p["Utente"]: f"{p['Persona']} ({p['Ruolo']})" for p in pe.persone_salvate() if p["Utente"]}
    except Exception:
        _pers = {}
    if not nomi_utenti:
        st.info("Non ci sono ancora utenti da abilitare: creali dalla scheda «Utenti».")
    for n in nomi_utenti:
        corrente = cfg["utenti"].get(n, cfg["predefinito"])
        nuovi[n] = st.selectbox(f"{n} — {_pers[n]}" if n in _pers else n, nomi_profili, index=nomi_profili.index(corrente), key=f"perm_u_{n}",
                                help="Se non scegli nulla, vale il profilo predefinito." if n not in cfg["utenti"] else None)
    predef = st.selectbox("Profilo per chi non ha ancora un profilo assegnato", nomi_profili, index=nomi_profili.index(cfg["predefinito"]), key="perm_pred")

    st.markdown("**2. Cosa apre ciascun profilo**")
    profili = {}
    for p in nomi_profili:
        with st.expander(f"{p} · {len(cfg['profili'][p])} strumenti", expanded=False):
            sel = st.multiselect("Strumenti abilitati", permessi.TUTTI, default=cfg["profili"][p], format_func=lambda s: permessi.NOMI[s],
                                 key=f"perm_p_{p}", disabled=(p == "presidente"))
            profili[p] = sel
    with st.expander("➕ Nuovo profilo"):
        c1, c2 = st.columns([2, 1])
        nuovo = c1.text_input("Nome del profilo", key="perm_nuovo", placeholder="es. segreteria")
        if c2.button("Aggiungi", key="perm_add", width="stretch") and nuovo.strip():
            cfg["profili"][nuovo.strip().lower()] = []
            permessi.salva_config(cfg, utente["username"])
            audit("permessi_modificati", f"nuovo profilo {nuovo.strip().lower()}")
            st.rerun()
    if st.button("💾 Salva i permessi", key="perm_salva", type="primary"):
        salvato = permessi.salva_config({"profili": profili, "utenti": nuovi, "predefinito": predef}, utente["username"])
        audit("permessi_modificati", "; ".join(f"{u}→{p}" for u, p in sorted(salvato["utenti"].items())) or "profili aggiornati")
        st.success("Permessi salvati. Hanno effetto al prossimo caricamento di pagina di ciascun utente.")
        st.rerun()
