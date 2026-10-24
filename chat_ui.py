"""chat_ui.py - Chat interna: conversazioni (canali e chat dirette), avvisi sul telefono, gestione e privacy."""
import datetime as dt
import html

import streamlit as st

import chat
import guida
import notifiche
import storage
import theme

ss = st.session_state
AGGIORNA_SEC = 8

INFORMATIVA_BREVE = """
**Chi vede cosa**
- **Canali pubblici**: li vedono tutte le persone che usano la suite. Chi gestisce i canali può archiviarli, esportarli e cancellare un messaggio non adatto (resta traccia nel registro attività).
- **Gruppi privati e chat dirette**: li vedono **solo i loro membri**. Nessun amministratore e nessun gestore li può leggere, nemmeno dall'esportazione.
- Con la chiave di cifratura attiva, testo e allegati di gruppi privati e chat dirette sono **cifrati nel database**.

**Avvisi sul telefono**
- Sono facoltativi e li scegli tu (Telegram e/o app ntfy). L'avviso dice solo «nuovo messaggio da…» e **non contiene mai il testo**.
- Per Telegram all'azienda arriva solo il codice tecnico della tua chat con il bot; per ntfy un nome-codice casuale. Puoi scollegarli quando vuoi.

**Conservazione**
- I messaggi si conservano per il tempo stabilito dall'azienda (e poi si cancellano). Puoi eliminare in qualsiasi momento i tuoi messaggi.

**Uso corretto**
- La chat serve per il lavoro. Non scrivere dati sensibili (salute, sindacato, ecc.) né password.
- Il registro attività conserva solo operazioni come «canale creato» o «messaggio rimosso dalla moderazione», mai il contenuto dei messaggi.

L'informativa completa è disponibile presso la direzione.
"""


def _rerun():
    """Aggiorna solo la conversazione; se la pagina sta girando per intero (non in un aggiornamento del frammento) aggiorna tutto."""
    try:
        st.rerun(scope="fragment")
    except st.errors.StreamlitAPIException:
        st.rerun()


def _ora_locale(ts):
    try:
        d = dt.datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
        try:
            from zoneinfo import ZoneInfo
            d = d.astimezone(ZoneInfo("Europe/Rome"))
        except Exception:
            pass
        adesso = dt.datetime.now(d.tzinfo)
        return d.strftime("%H:%M") if d.date() == adesso.date() else d.strftime("%d/%m %H:%M")
    except Exception:
        return ts[:16]


def _utenti_noti(utenti_secrets=None):
    noti = set((utenti_secrets or {}).keys())
    try:
        noti |= {u["username"] for u in storage.elenca_utenti() if u["attivo"]}
    except Exception:
        pass
    return sorted(noti, key=str.lower)


def _riga_messaggio(m, utente, audit, vai_a, consentiti, nomi_strumenti):
    mio = m["autore"] == utente["username"]
    with st.chat_message("user" if mio else "assistant", avatar="🧑‍💼" if mio else "👤"):
        st.markdown(f"**{html.escape(m['autore'])}** · <span style='color:#64748b;font-size:.8rem'>{_ora_locale(m['ts'])}</span>", unsafe_allow_html=True)
        if m["eliminato"]:
            st.caption("🚫 Messaggio eliminato")
            return
        if m["testo"]:
            st.markdown(html.escape(m["testo"]).replace("\n", "  \n"), unsafe_allow_html=True)
        if m["allegato"]:
            if (m["allegato_tipo"] or "").startswith("image/"):
                st.image(m["allegato"], width=320, caption=m["allegato_nome"])
            else:
                st.download_button(f"📄 {m['allegato_nome']}", m["allegato"], file_name=m["allegato_nome"], mime=m["allegato_tipo"], key=f"chd_{m['id']}")
        if m["link_modulo"]:
            sigla = m["link_modulo"]
            if sigla in consentiti:
                if st.button(f"↗ Apri {nomi_strumenti.get(sigla, sigla)}" + (f" · {m['link_etichetta']}" if m["link_etichetta"] else ""), key=f"chl_{m['id']}"):
                    vai_a(sigla)
            else:
                st.caption(f"↗ {nomi_strumenti.get(sigla, sigla)} (non hai accesso a questo strumento)")
        if mio and st.button("🗑 Elimina", key=f"chx_{m['id']}", type="tertiary"):
            chat.elimina_messaggio(m["id"], utente)
            _rerun()


@st.fragment(run_every=AGGIORNA_SEC)
def _conversazioni(utente, utenti_noti, audit, vai_a, consentiti, nomi_strumenti):
    u = utente["username"]
    scrive = chat.puo_scrivere(utente)
    canali = chat.canali_visibili(u)
    ids = {c["id"] for c in canali}
    if ss.get("chat_cid") not in ids:
        ss["chat_cid"] = next((c["id"] for c in canali), None)
    sel = ss.get("chat_cid")
    msgs, ultimo = [], 0
    if sel:
        try:
            msgs = chat.messaggi(sel, u)
            ultimo = msgs[-1]["id"] if msgs else 0
            chat.segna_letti(sel, u, ultimo)
            canali = chat.canali_visibili(u)
        except PermissionError:
            ss["chat_cid"] = sel = None
    sx, dx = st.columns([1, 2.4], gap="medium")
    with sx:
        gruppi = (("pubblico", "# Canali"), ("privato", "🔒 Gruppi privati"), ("diretto", "💬 Chat dirette"))
        for tipo, titolo in gruppi:
            elenco = [c for c in canali if c["tipo"] == tipo]
            if not elenco and tipo != "diretto":
                continue
            st.markdown(f"<div class='sb-label' style='margin-top:.4rem'>{titolo}</div>", unsafe_allow_html=True)
            for c in elenco:
                badge = f"  🔴 {c['non_letti']}" if c["non_letti"] else ""
                pre = ("▶ " if c["id"] == sel else "") + ("# " if tipo == "pubblico" else ("🔒 " if tipo == "privato" else ""))
                if st.button(f"{pre}{c['etichetta']}{badge}", key=f"chc_{c['id']}", width="stretch", type="primary" if c["id"] == sel else "secondary"):
                    ss["chat_cid"] = c["id"]
                    _rerun()
        if scrive:
            altri = [x for x in utenti_noti if x.lower() != u.lower()]
            with st.expander("➕ Nuova chat diretta"):
                dest = st.selectbox("Con chi", altri, index=None, placeholder="Scegli una persona", key="chat_dm_con")
                if st.button("Apri la chat", key="chat_dm_apri", disabled=not dest):
                    ss["chat_cid"] = chat.canale_diretto(u, dest)
                    _rerun()
            with st.expander("➕ Nuovo gruppo privato"):
                nome = st.text_input("Nome del gruppo", key="chat_gp_nome", max_chars=40)
                mem = st.multiselect("Membri", altri, key="chat_gp_mem")
                if st.button("Crea il gruppo", key="chat_gp_crea", disabled=not (nome and mem)):
                    try:
                        ss["chat_cid"] = chat.crea_canale(nome, "privato", u, mem)
                        audit("chat_gruppo_creato", nome)
                        ss["chat_gp_nome"], ss["chat_gp_mem"] = "", []
                        _rerun()
                    except ValueError as e:
                        st.error(str(e))
    with dx:
        if not sel:
            st.info("Nessun canale ancora. Chi gestisce i canali può crearne dalla scheda «Gestione»; intanto puoi aprire una chat diretta.")
            return
        cur = next((c for c in canali if c["id"] == sel), None)
        if cur:
            titolo = ("# " if cur["tipo"] == "pubblico" else "🔒 " if cur["tipo"] == "privato" else "💬 ") + cur["etichetta"]
            st.markdown(f"#### {html.escape(titolo)}")
            if cur["tipo"] == "pubblico":
                st.caption(cur["descrizione"] or "Canale pubblico: lo vedono tutti.")
            elif cur["tipo"] == "privato":
                st.caption("Membri: " + ", ".join(chat.membri(sel)) + " · nessun altro, amministratori compresi, può leggere questo gruppo.")
            else:
                st.caption("Chat diretta: la leggete solo voi due.")
        with st.container(height=470, border=True):
            if not msgs:
                st.caption("Nessun messaggio: scrivi tu il primo.")
            for m in msgs:
                _riga_messaggio(m, utente, audit, vai_a, consentiti, nomi_strumenti)
        if cur and not scrive:
            st.info("Il tuo ruolo è «lettore»: puoi leggere ma non scrivere.")
            return
        with st.form("chat_invio", clear_on_submit=True, border=False):
            testo = st.text_area("Scrivi un messaggio", key="chat_testo", height=80, max_chars=chat.MAX_TESTO, label_visibility="collapsed",
                                 placeholder="Scrivi un messaggio… usa @nome per citare qualcuno")
            c1, c2 = st.columns([2, 2])
            with c1:
                allegato = st.file_uploader("Allega una foto o un PDF", type=["jpg", "jpeg", "png", "webp", "pdf"], key="chat_allegato",
                                            help=f"Foto ridotte automaticamente; PDF fino a {chat.LIMITE_PDF_MB} MB.")
            with c2:
                strumenti = [s for s in consentiti if s in nomi_strumenti and s != "ch"]
                sc = st.selectbox("Collega uno strumento (facoltativo)", strumenti, index=None, format_func=lambda s: nomi_strumenti[s],
                                  placeholder="Nessuno", key="chat_link")
            if st.form_submit_button("Invia", type="primary"):
                try:
                    info = chat.invia(sel, u, utente["ruolo"], testo, (allegato.name, allegato.getvalue()) if allegato else None,
                                      (sc, "") if sc else None)
                    notifiche.avvisa(info, u, testo, utenti_noti)
                    _rerun()
                except (ValueError, PermissionError) as e:
                    st.error(str(e))


def _tab_avvisi(utente, utenti_noti):
    u = utente["username"]
    p = chat.prefs(u)
    st.markdown("Ricevi un avviso sul telefono quando arriva un messaggio. **L'avviso non contiene mai il testo**: dice solo chi ha scritto.")
    modo = st.radio("Quando avvisarmi", list(chat.MODI_AVVISO), index=list(chat.MODI_AVVISO).index(p["modo"]), format_func=chat.MODI_AVVISO.get, key="chat_modo")
    sil = st.checkbox("Non disturbare di notte", value=bool(p["silenzio_da"] and p["silenzio_a"]), key="chat_sil")
    b, b2, _ = st.columns([1, 1, 2])
    da = b.text_input("Dalle (HH:MM)", p["silenzio_da"] or "20:00", key="chat_sil_da", disabled=not sil)
    a2 = b2.text_input("Alle (HH:MM)", p["silenzio_a"] or "07:30", key="chat_sil_a", disabled=not sil)
    if st.button("Salva le preferenze", key="chat_prefs_ok"):
        try:
            for t in ((da, a2) if sil else ()):
                dt.datetime.strptime(t, "%H:%M")
            chat.salva_prefs(u, modo=modo, silenzio_da=da if sil else "", silenzio_a=a2 if sil else "")
            st.success("Preferenze salvate.")
        except ValueError:
            st.error("Scrivi gli orari nel formato HH:MM, per esempio 20:00.")
    st.divider()
    st.markdown("##### 📨 Telegram")
    if not notifiche.telegram_attivo():
        st.info("Telegram non è ancora configurato: l'amministratore deve inserire TELEGRAM_BOT_TOKEN nei Secrets. Intanto puoi usare ntfy.")
    elif p["telegram_chat_id"]:
        st.success("Telegram collegato.")
    else:
        if st.button("Collega Telegram", key="chat_tg_avvia"):
            chat.nuovo_codice_telegram(u)
            st.rerun()
        if p["telegram_codice"]:
            lk = notifiche.link_telegram(p["telegram_codice"])
            if lk:
                st.markdown(f"1. Tocca **[questo link]({lk})** dal telefono e premi **Avvia / Start** in Telegram.")
            else:
                st.warning("Non riesco a contattare Telegram: riprova tra poco.")
            if st.button("2. Ho premuto Start: verifica", key="chat_tg_verifica"):
                if notifiche.collega_telegram(u):
                    st.rerun()
                else:
                    st.warning("Non vedo ancora il tuo Start: attendi qualche secondo e riprova.")
    st.markdown("##### 🔔 App ntfy (alternativa, anche su server aziendale)")
    if p["ntfy_topic"]:
        st.success("ntfy attivo.")
        st.markdown(f"Installa l'app **ntfy** (iPhone/Android), scegli **Iscriviti a un argomento**, server `{notifiche.ntfy_url()}`, argomento:")
        st.code(p["ntfy_topic"], language=None)
        st.caption("Il codice è segreto: non condividerlo. Con il server ntfy pubblico chi lo conosce potrebbe leggere gli avvisi (che però non contengono il testo dei messaggi).")
    elif st.button("Attiva ntfy", key="chat_ntfy_on"):
        chat.nuovo_topic_ntfy(u)
        st.rerun()
    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("Manda un avviso di prova", key="chat_prova", disabled=not (p["telegram_chat_id"] or p["ntfy_topic"])):
        r = notifiche.prova_avviso(u)
        st.write({k: ("ok" if v else "non riuscito") for k, v in r.items() if v is not None})
    if c2.button("Scollega i miei telefoni", key="chat_scollega", disabled=not (p["telegram_chat_id"] or p["ntfy_topic"] or p["telegram_codice"])):
        chat.scollega_avvisi(u)
        st.rerun()


def _tab_gestione(utente, utenti_noti, audit):
    cfg = chat.carica_cfg()
    admin = utente["ruolo"] == "admin"
    st.markdown("##### Nuovo canale pubblico")
    a, b = st.columns([1, 2])
    nome = a.text_input("Nome", key="chat_nc_nome", max_chars=40)
    desc = b.text_input("A cosa serve", key="chat_nc_desc", max_chars=120)
    if st.button("Crea il canale", key="chat_nc_ok", disabled=not nome):
        try:
            chat.crea_canale(nome, "pubblico", utente["username"], descrizione=desc)
            audit("chat_canale_creato", nome)
            st.success("Canale creato.")
            st.rerun()
        except ValueError as e:
            st.error(str(e))
    if st.button("Aggiungi i canali consigliati che mancano", key="chat_nc_base", help="Generale, Cantieri, Commerciale e gare, Amministrazione, Acquisti, Sicurezza, Mezzi, Legale, Assistenza, Idee."):
        n = chat.crea_canali_iniziali(utente["username"], solo_se_vuoto=False)
        audit("chat_canali_iniziali", f"{n} canali")
        st.success(f"Creati {n} canali." if n else "Ci sono già tutti.")
        st.rerun()
    st.markdown("##### Canali esistenti")
    for c in chat.tutti_i_canali_gestibili():
        cols = st.columns([3, 1.2, 1.2])
        icona = "#" if c["tipo"] == "pubblico" else "🔒"
        cols[0].markdown(f"{icona} **{html.escape(c['nome'])}**" + ("  _(archiviato)_" if c["archiviato"] else "") +
                         ("" if c["tipo"] == "pubblico" else "  · privato: contenuto non visibile"))
        if cols[1].button("Ripristina" if c["archiviato"] else "Archivia", key=f"chat_ar_{c['id']}"):
            chat.archivia_canale(c["id"], not c["archiviato"])
            audit("chat_canale_archiviato" if not c["archiviato"] else "chat_canale_ripristinato", c["nome"])
            st.rerun()
        if c["tipo"] == "pubblico":
            cols[2].download_button("Esporta", chat.esporta_canale(c["id"], utente), file_name=f"canale_{c['nome']}.txt", key=f"chat_ex_{c['id']}",
                                    on_click=lambda n=c["nome"]: audit("chat_canale_esportato", n))
    if admin:
        st.divider()
        st.markdown("##### Chi può gestire i canali")
        st.caption("Gli amministratori gestiscono sempre. Qui scegli altre persone a cui dare lo stesso compito (creare, archiviare, esportare i canali pubblici).")
        scelti = st.multiselect("Altri gestori", [x for x in utenti_noti], default=[x for x in cfg["gestori"] if x in utenti_noti], key="chat_gestori")
        if st.button("Salva i gestori", key="chat_gestori_ok"):
            chat.salva_cfg({"gestori": scelti}, utente["username"])
            audit("chat_gestori_aggiornati", ", ".join(scelti))
            st.success("Gestori aggiornati.")
        st.divider()
        st.markdown("##### Conservazione dei messaggi")
        mesi = st.number_input("Cancella i messaggi più vecchi di (mesi)", 1, 120, 24, key="chat_mesi")
        conf = st.checkbox("Confermo: la cancellazione non si può annullare", key="chat_mesi_conf")
        if st.button("Cancella i messaggi vecchi", key="chat_mesi_ok", disabled=not conf):
            n = chat.pulisci(mesi)
            audit("chat_pulizia", f"{n} messaggi oltre {mesi} mesi")
            st.success(f"Cancellati {n} messaggi.")
        st.divider()
        st.markdown("##### Stato del servizio")
        st.write(f"- Cifratura di gruppi privati e chat dirette: **{'attiva' if chat.cifratura_attiva() else 'NON attiva (manca CHAT_KEY)'}**")
        st.write(f"- Telegram: **{'configurato' if notifiche.telegram_attivo() else 'non configurato (TELEGRAM_BOT_TOKEN)'}**")
        st.write(f"- ntfy: server `{notifiche.ntfy_url()}`")
        st.write(f"- Indirizzo della suite negli avvisi (APP_URL): **{notifiche.app_url() or 'non impostato'}**")


def render(fcr_uri, audit=None, utente=None, utenti_secrets=None, consentiti=None, vai_a=None, nomi_strumenti=None):
    audit = audit or (lambda *a, **k: None)
    consentiti = set(consentiti or [])
    nomi_strumenti = nomi_strumenti or {}
    vai_a = vai_a or (lambda m: None)
    st.markdown(theme.hero(fcr_uri, "Chat interna", "Canali per i temi comuni, chat dirette tra colleghi e avvisi sul telefono."), unsafe_allow_html=True)
    guida.mostra("ch")
    noti = _utenti_noti(utenti_secrets)
    gest = chat.e_gestore(utente)
    try:
        chat.crea_canali_iniziali(utente["username"])             # alla prima apertura prepara i canali consigliati
    except Exception:
        pass
    nomi = ["💬 Conversazioni", "📱 Avvisi sul telefono"] + (["⚙️ Gestione"] if gest else []) + ["🔒 Privacy"]
    tabs = st.tabs(nomi)
    with tabs[0]:
        _conversazioni(utente, noti, audit, vai_a, consentiti, nomi_strumenti)
    with tabs[1]:
        _tab_avvisi(utente, noti)
    if gest:
        with tabs[2]:
            _tab_gestione(utente, noti, audit)
    with tabs[-1]:
        st.markdown(INFORMATIVA_BREVE)
