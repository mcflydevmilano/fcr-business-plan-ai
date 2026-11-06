"""
admin_ui.py - Pannello di amministrazione (solo ruolo admin): utenti e registro attivita'.
Si usa da app.py:  admin_ui.render(utente_corrente, utenti_secrets, audit)
"""
import pandas as pd
import streamlit as st

import auth
import onboarding
import posta
import permessi
import spazio
import storage


testo_accesso = onboarding.testo_accesso


def _manda_accesso(nome, mail, password, nuovo=True):
    ogg, corpo = testo_accesso(nome, password, nuovo)
    if posta.invia_con_feedback([mail], ogg, corpo):
        storage.log_evento("sistema", "email_accesso", f"{nome} -> {mail}")
    else:
        st.warning(f"L'email non è partita. Password provvisoria di **{nome}**: `{password}` — comunicala a voce (non verrà mostrata di nuovo).")


def render(utente, utenti_secrets, audit):
    st.markdown("## ⚙️ Amministrazione suite")
    if utente.get("ruolo") != "admin":
        st.error("Accesso riservato agli amministratori.")
        return
    for frase in spazio.avvisi():
        st.warning("💾 " + frase + " Vedi la scheda «Spazio».")
    try:
        import assistenza
        _segn = assistenza.elenco_segnalazioni()
    except Exception:
        _segn = []
    t1, t2, t3, t4, t5, t6, t7 = st.tabs(["Utenti", "Registro attività", "Backup", "🔒 Permessi", "💾 Spazio", f"📨 Segnalazioni ({len(_segn)})" if _segn else "📨 Segnalazioni", "🎬 Video"])
    with t7:
        _video_admin(utente, audit)
    with t6:
        st.markdown("#### Segnalazioni dei colleghi")
        st.caption("Arrivano dal pulsante con la tua foto, in basso a destra. Ogni riga dice chi scrive, in quale strumento si trovava, da telefono o computer e con quale versione.")
        if _segn:
            st.dataframe(pd.DataFrame(_segn), width="stretch", hide_index=True)
        else:
            st.info("Nessuna segnalazione per ora.")

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
                                        "Profilo": permessi.carica_config()["utenti"].get(u["username"], "(predefinito)"), "Email": u.get("email") or "", "Creato": (u["creato"] or "")[:16], "Ultimo accesso": (u["ultimo_accesso"] or "mai")[:16]} for u in utenti]),
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
                if rec.get("email") and posta.smtp_pronto():
                    _manda_accesso(sel, rec["email"], tmp, nuovo=False)
            if c3.button("🗑️ Elimina", key="adm_elimina", width="stretch"):
                storage.elimina_utente(sel)
                audit("utente_eliminato", sel)
                st.rerun()
            nuovo_ruolo = st.radio("Ruolo", list(auth.RUOLI), index=list(auth.RUOLI).index(rec["ruolo"]), horizontal=True, key=f"adm_ruolo_{sel}")
            if nuovo_ruolo != rec["ruolo"]:
                storage.aggiorna_utente(sel, ruolo=nuovo_ruolo)
                audit("ruolo_cambiato", f"{sel} -> {nuovo_ruolo}")
                st.rerun()
            _cfgu = permessi.carica_config()
            _att = _cfgu["utenti"].get(sel, _cfgu["predefinito"])
            _pl = list(_cfgu["profili"])
            p1, p2 = st.columns([3, 1])
            _nuovo_prof = p1.selectbox("Cosa vede (profilo)", _pl, index=_pl.index(_att) if _att in _pl else 0, key=f"adm_prof_{sel}",
                                       help="Quali strumenti apre questa persona. I profili si modificano nella scheda «Permessi».")
            p2.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
            if p2.button("💾 Salva", key=f"adm_prof_salva_{sel}", width="stretch") and _nuovo_prof != _att:
                onboarding.imposta_profilo(sel, _nuovo_prof, utente["username"])
                audit("pe_profilo_cambiato", f"{sel}: {_att} → {_nuovo_prof}")
                st.success("Profilo aggiornato.")
            with st.expander("✏️ Correggi nome o email di questa persona"):
                st.caption("Se il nome ha un errore, correggilo qui: il cambio vale ovunque (accessi, timbrature, chat, permessi). "
                           "La persona dovrà entrare con il nuovo nome.")
                nuovo_nome = st.text_input("Nome e cognome (con lo spazio)", value=sel, key=f"adm_nome_{sel}")
                if st.button("💾 Salva il nome", key=f"adm_nome_salva_{sel}"):
                    try:
                        auth.rinomina_utente(sel, nuovo_nome, utente["username"], utenti_secrets)
                        st.session_state.pop("adm_sel", None)
                        st.session_state["adm_msg"] = f"Nome cambiato in «{auth.normalizza_username(nuovo_nome)}»."
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
                nuova_mail = st.text_input("Email", value=rec.get("email") or "", key=f"adm_mail_{sel}", placeholder="nome@fcrgeneralcontractor.eu")
                if st.button("💾 Salva l'email", key=f"adm_mail_salva_{sel}"):
                    try:
                        auth.modifica_email(sel, nuova_mail, utente["username"])
                        st.success("Email salvata.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
        else:
            st.caption("Nessun utente creato dal pannello.")
        _m = st.session_state.pop("adm_msg", None)
        if _m:
            st.success(_m)
        with st.expander("🔐 Verifica in due passaggi"):
            import due_passaggi
            _ob = st.checkbox("Obbligatoria per tutti gli amministratori", value=due_passaggi.obbligatorio_admin(), key="adm_2fa_ob",
                              help="Al prossimo accesso chi non l'ha ancora attivata deve configurarla prima di proseguire.")
            if _ob != due_passaggi.obbligatorio_admin():
                due_passaggi.imposta_obbligatorio_admin(_ob, utente["username"])
                audit("2fa_obbligo", "attivo" if _ob else "spento")
                st.rerun()
            _nomi = sorted({u["username"] for u in utenti} | set(utenti_secrets or {}))
            if _nomi:
                _x = st.selectbox("Persona che ha perso il telefono", _nomi, key="adm_2fa_sel")
                st.caption("Attiva" if due_passaggi.attivo(_x) else "Non attiva")
                if due_passaggi.attivo(_x) and st.button("Azzera i due passaggi di questa persona", key="adm_2fa_reset"):
                    due_passaggi.disattiva(_x, utente["username"])
                    st.rerun()
        tmp = st.session_state.get("adm_tmp")
        if tmp:
            st.success(f"Password temporanea per **{tmp[0]}**: `{tmp[1]}` — comunicala all'utente: non verra' mostrata di nuovo "
                       "e va cambiata al primo accesso (barra laterale → Account).")

        st.markdown("#### Nuovo utente")
        _pronta = posta.smtp_pronto()
        if _pronta:
            st.caption("Scrivi nome, cognome ed email: la suite crea l'account con una password provvisoria e la spedisce alla persona per email. "
                       "Al primo accesso dovrà sceglierne una sua.")
        else:
            st.info("La posta non è ancora configurata (servono SMTP_HOST, SMTP_USER, SMTP_PASSWORD): l'account si crea lo stesso e la password provvisoria "
                    "la vedi qui sotto, da comunicare a voce.")
        with st.form("adm_nuovo", clear_on_submit=True):
            n1, n2 = st.columns(2)
            nome_p = n1.text_input("Nome", placeholder="Mario")
            cogn_p = n2.text_input("Cognome", placeholder="Rossi")
            m1, m2, m3 = st.columns([3, 1.4, 1.6])
            mail = m1.text_input("Email della persona", placeholder="mario.rossi@fcrgeneralcontractor.eu")
            ruolo = m2.selectbox("Può modificare?", list(auth.RUOLI), index=1, help="admin = tutto; utente = lavora e modifica; lettore = solo consulta.")
            _cfgp = permessi.carica_config()
            _prof = m3.selectbox("Cosa vede (profilo)", list(_cfgp["profili"]), index=list(_cfgp["profili"]).index(_cfgp["predefinito"]),
                                 help="Il profilo decide quali strumenti vede. I profili si modificano nella scheda «Permessi».")
            if st.form_submit_button("Crea utente e invia la password"):
                nome = auth.nome_da_testo(nome_p, cogn_p)
                if not nome_p.strip() or not cogn_p.strip():
                    st.error("Scrivi sia il nome sia il cognome.")
                elif _pronta and not posta.indirizzo_valido(mail):
                    st.error("Scrivi un indirizzo email valido: serve per inviare la password.")
                else:
                    try:
                        esito = onboarding.crea_account(nome, mail, ruolo, _prof, utente["username"])
                    except ValueError as e:
                        st.error(str(e))
                    else:
                        st.success(f"Utente «{nome}» creato con il profilo «{_prof}».")
                        if esito["inviata"]:
                            st.info(f"Ho inviato la password provvisoria a {mail}.")
                        else:
                            st.warning(f"L'email non è partita. Password provvisoria di **{nome}**: `{esito['password']}` — comunicala a voce (non verrà mostrata di nuovo).")

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

    with t5:
        _spazio()


def _video_admin(utente, audit):
    import video
    import percorso
    import permessi
    st.markdown("#### Video corsi")
    st.caption("Incolla il link di ogni video (YouTube «non in elenco», Vimeo…, deve cominciare con https://). Dove c'è un link compare il pulsante «🎬 Guarda il video» "
               "nello strumento; dove manca non compare nulla. I passi dei Primi passi usano, se non hanno un video proprio, quello del primo strumento.")
    attuali = video.carica()
    righe = [{"Dove": "Passo · " + p["titolo"], "Chiave": f"pp_{p['id']}", "Link": attuali.get(f"pp_{p['id']}", "")} for p in percorso.PASSI]
    righe += [{"Dove": "Strumento · " + str(n), "Chiave": s, "Link": attuali.get(s, "")} for s, n in permessi.NOMI.items()]
    ed = st.data_editor(pd.DataFrame(righe), hide_index=True, width="stretch", key="adm_video", disabled=["Dove", "Chiave"],
                        column_config={"Chiave": None, "Link": st.column_config.LinkColumn("Link del video", help="https://…")})
    if st.button("Salva i link dei video", type="primary", key="adm_video_salva"):
        nuovi = {r["Chiave"]: r["Link"] for _, r in ed.iterrows() if str(r["Link"] or "").strip()}
        scartati = [k for k, v in nuovi.items() if not video.url_valido(v)]
        video.salva(nuovi, utente.get("username", ""))
        storage.svuota_cache()
        audit("video_salvati", f"{len(nuovi) - len(scartati)} link")
        if scartati:
            st.warning(f"{len(scartati)} link non validi sono stati ignorati (devono cominciare con https://).")
        else:
            st.success("Salvato.")


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


_COLORI = {"ok": "#2e9e5b", "attenzione": "#e0a100", "critico": "#d03b3b", "nd": "#9aa0a6"}


def _barra(titolo, x, aiuto=""):
    """Barra dello spazio usato: verde sotto il 75%, gialla fino al 90%, rossa oltre."""
    st.markdown(f"**{titolo}**")
    if not x.get("disponibile"):
        st.warning(f"{x.get('motivo') or 'non disponibile'}. {aiuto}")
        return
    perc = x["perc"] or 0
    col = _COLORI.get(x["stato"], _COLORI["nd"])
    st.markdown(
        f"<div style='background:#e6e8eb;border-radius:8px;height:22px;overflow:hidden'>"
        f"<div style='width:{min(perc, 100):.1f}%;height:100%;background:{col}'></div></div>",
        unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("Usato", f"{spazio.leggibile(x['usato'])}", f"{perc:.0f}%", delta_color="off")
    c2.metric("Libero", spazio.leggibile(x["libero"]))
    c3.metric("Totale", spazio.leggibile(x["totale"]))
    if x["stato"] == "critico":
        st.error("Spazio quasi finito: libera spazio o amplia il disco prima che la suite si fermi.")
    elif x["stato"] == "attenzione":
        st.warning("Lo spazio sta finendo: conviene fare pulizia o programmare un disco più grande.")


def _spazio():
    st.markdown("#### Spazio del server e del NAS")
    st.caption("Si aggiorna ogni volta che apri questa scheda. Verde: tutto a posto. Giallo: oltre il 75%. Rosso: oltre il 90%.")
    if st.button("🔄 Aggiorna", key="cmd_spazio_agg"):
        st.rerun()
    r = spazio.riepilogo()
    _barra("🖥️ Server (disco del computer in ufficio)", r["server"], "Se vedi questo messaggio la suite non gira sul server.")
    st.divider()
    nas = r["nas"]
    _barra("🗄️ NAS (archivio e copie di sicurezza)", nas,
           "Controlla che il NAS sia acceso e collegato al server (cartella " + spazio.percorso_nas() + ").")
    st.divider()
    st.markdown("**Cosa occupa spazio**")
    c1, c2 = st.columns(2)
    db = r["db"]
    c1.metric("Database della suite", spazio.leggibile(db) if db is not None else "non leggibile")
    bk = r["backup"]
    c2.metric("Copie di sicurezza", spazio.leggibile(bk["byte"]), f"{bk['file']} file" if bk["cartella"] else "cartella non trovata", delta_color="off")
    if bk["cartella"]:
        st.caption(f"Cartella delle copie: {bk['cartella']}")
