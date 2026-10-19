"""
admin_ui.py - Pannello di amministrazione (solo ruolo admin): utenti e registro attivita'.
Si usa da app.py:  admin_ui.render(utente_corrente, utenti_secrets, audit)
"""
import pandas as pd
import streamlit as st

import auth
import storage


def render(utente, utenti_secrets, audit):
    st.markdown("## 👥 Amministrazione")
    if utente.get("ruolo") != "admin":
        st.error("Accesso riservato agli amministratori.")
        return
    t1, t2 = st.tabs(["Utenti", "Registro attività"])

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
        f1, f2, f3 = st.columns([2, 2, 1])
        utenti_log = [""] + sorted({e["Utente"] for e in storage.elenca_eventi(1000) if e["Utente"]})
        fu = f1.selectbox("Utente", utenti_log, format_func=lambda x: x or "Tutti", key="adm_f_utente")
        azioni_log = [""] + sorted({e["Azione"] for e in storage.elenca_eventi(1000)})
        fa = f2.selectbox("Azione", azioni_log, format_func=lambda x: x or "Tutte", key="adm_f_azione")
        n = f3.number_input("Righe", 20, 1000, 200, 20, key="adm_f_n")
        ev = storage.elenca_eventi(int(n), fu or None, fa or None)
        df = pd.DataFrame(ev, columns=["Data (UTC)", "Utente", "Azione", "Dettaglio"])
        st.dataframe(df, width="stretch", hide_index=True)
        st.download_button("📥 Scarica il registro (CSV)", df.to_csv(index=False).encode("utf-8-sig"), file_name="registro_attivita.csv", mime="text/csv")
        st.caption("Il registro e' nel database dell'applicazione: su hosting con disco temporaneo si azzera al riavvio. "
                   "Per una conservazione stabile imposta FCR_DB_PATH su un volume persistente.")
