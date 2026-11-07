"""mattino_ui.py - Interfaccia di «Il mio riepilogo»."""
import datetime as dt
import os

import streamlit as st

import guida
import mattino
import permessi
import posta
import storage
import theme

ss = st.session_state


def render(fcr_uri, audit, utente, profilo, utenti_secrets):
    audit = audit or (lambda *a, **k: None)
    nome = (utente or {}).get("username", "")
    admin = (utente or {}).get("ruolo") == "admin"
    st.markdown(theme.hero(fcr_uri, "Il mio riepilogo", "Ogni mattina, solo le cose che ti riguardano: scadenze, offerte da seguire, chi manca. Anche per email."), unsafe_allow_html=True)
    guida.mostra("rm")
    cfg = mattino.carica_cfg()
    pc = permessi.carica_config()
    cons = permessi.moduli_consentiti(utente, pc)
    tabs = st.tabs(["☀️ Il riepilogo di oggi", "⚙️ Impostazioni (amministratore)"] if admin else ["☀️ Il riepilogo di oggi"])

    with tabs[0]:
        oggi = dt.date.today()
        sez = mattino.sezioni(utente, permessi.profilo_di(utente, pc), cons, oggi)
        st.markdown(f"##### Buongiorno {nome.title()}, ecco cosa conta oggi · {mattino.data_it(oggi)}")
        if not sez:
            st.success("Oggi non c'è niente di urgente per te.")
        for titolo, righe in sez:
            with st.container(border=True):
                st.markdown(f"**{titolo}**")
                for r in righe:
                    st.markdown(f"- {r}")
        st.caption("Si aggiorna ogni volta che apri questa pagina. Mostra solo gli strumenti che puoi aprire.")
        mail = next((u.get("email") for u in storage.elenca_utenti() if u["username"].lower() == nome.lower()), "")
        if not cfg["attivo"]:
            st.info("L'invio automatico per email non è ancora acceso: lo accende l'amministratore.")
        elif not posta.indirizzo_valido(mail or ""):
            st.warning("Non hai un indirizzo email nel tuo profilo: così non ricevi il riepilogo al mattino. Chiedi all'amministratore di inserirlo.")
        else:
            vuole = st.checkbox(f"Voglio ricevere questo riepilogo ogni mattina per email ({mail})", value=nome.lower() not in cfg["escludi"], key="rm_vuole")
            if vuole != (nome.lower() not in cfg["escludi"]):
                esc = set(cfg["escludi"]) - {nome.lower()} if vuole else set(cfg["escludi"]) | {nome.lower()}
                mattino.salva_cfg({**cfg, "escludi": sorted(esc)}, nome)
                st.rerun()

    if admin:
        with tabs[1]:
            st.markdown("**Invio automatico**")
            c1, c2 = st.columns(2)
            attivo = c1.toggle("Invio acceso (dal lunedì al venerdì)", value=cfg["attivo"], key="rm_attivo")
            solo = c2.toggle("Non mandare se non c'è niente da dire", value=cfg["solo_se_c_e"], key="rm_solo")
            e1, e2 = st.columns(2)
            em = e1.checkbox("Email a ciascuno (a chi ha un indirizzo)", value=cfg["email"], key="rm_email")
            sl = e2.checkbox("Messaggio su Slack con il quadro dell'azienda", value=cfg["slack"], key="rm_slack")
            if st.button("💾 Salva le impostazioni", key="rm_salva", type="primary"):
                mattino.salva_cfg({**cfg, "attivo": attivo, "solo_se_c_e": solo, "email": em, "slack": sl}, nome)
                audit("riepilogo_impostazioni", f"attivo={attivo}")
                st.success("Salvato.")
                st.rerun()
            smtp = posta.smtp_pronto()
            slack_ok = (os.environ.get("SLACK_RIEPILOGO_WEBHOOK_URL") or os.environ.get("SLACK_WEBHOOK_URL") or "").startswith("https://hooks.slack.com/")
            st.caption(f"Posta: {'✅ configurata' if smtp else '❌ non configurata (servono SMTP_HOST, SMTP_USER, SMTP_PASSWORD)'} · "
                       f"Slack: {'✅ configurato' if slack_ok else '❌ non configurato (serve SLACK_RIEPILOGO_WEBHOOK_URL)'}")
            try:
                utenti = storage.elenca_utenti()
                senza = [u["username"] for u in utenti if u.get("attivo") and not posta.indirizzo_valido(u.get("email") or "")]
                if senza:
                    st.warning("Senza indirizzo email (non ricevono nulla): " + ", ".join(senza))
            except Exception:
                pass
            ult = (mattino._stato() or {})
            if ult.get("ultimo"):
                st.caption(f"Ultimo invio: {ult['ultimo']} · inviati a {len((ult.get('report') or {}).get('inviati', []))} persone.")
            st.markdown("**Prova**")
            p1, p2 = st.columns(2)
            if p1.button("📧 Mandami una prova", key="rm_prova", width="stretch"):
                mail = next((u.get("email") for u in storage.elenca_utenti() if u["username"].lower() == nome.lower()), "")
                try:
                    sez = mattino.sezioni(utente, permessi.profilo_di(utente, pc), cons)
                    posta.invia([mail], mattino.oggetto(), mattino.testo(utente, sez), html=mattino.corpo_html(utente, sez))
                    st.success(f"Prova inviata a {mail}.")
                except Exception as ex:
                    st.error(f"Non è partita: {ex}")
            if p2.button("📨 Invia adesso a tutti", key="rm_tutti", width="stretch"):
                rep = mattino.invia_tutti(forza=True)
                audit("riepilogo_inviato", f"{len(rep['inviati'])} email")
                st.success(f"Inviati: {', '.join(rep['inviati']) or 'nessuno'}" + (" · Slack: ok" if rep["slack"] else ""))
                for e in rep["errori"]:
                    st.error(e)
            with st.expander("🛠️ Come farlo partire da solo ogni mattina (una volta sola, sul server)"):
                st.markdown("""
Nel server, dopo aver aggiornato la suite:
```
sudo cp ~/fcr-suite-app/deploy/fcr-mattino.service ~/fcr-suite-app/deploy/fcr-mattino.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fcr-mattino.timer
```
Parte dal lunedì al venerdì alle 7:30. Per provarlo subito: `sudo systemctl start fcr-mattino.service`.
Per vedere cosa manderebbe senza spedire: `cd ~/fcr-suite-app && python3 invia_mattino.py --prova`.
Per Slack crea un *Incoming Webhook* e mettilo in `/etc/fcr-suite.env` come `SLACK_RIEPILOGO_WEBHOOK_URL=https://hooks.slack.com/...`, poi `sudo systemctl restart fcr-suite`.
""")
