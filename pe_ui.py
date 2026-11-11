"""pe_ui.py - Interfaccia di Persone e ruoli (elenco del personale e accessi all'app)."""
import datetime as dt

import pandas as pd
import streamlit as st

import auth
import guida
import ops_report
import onboarding
import pe
import permessi
import storage
import theme
from ui_util import esempi_attivi, senza_esempi, banner_esempio, blocco_tabella, pannello_archivio, scarica_dossier, sola_lettura, sostituisci_tabella

ss = st.session_state


@senza_esempi
def _esempio():
    righe = [("Anna Bianchi", "Direttore generale", "Direzione", "02 5551001", "a.bianchi@fcr.example", "", "Dipendente", "", "Sì"),
             ("Luca Verdi", "Direttore tecnico", "Tecnico", "333 1000002", "l.verdi@fcr.example", "", "Dipendente", "", "Sì"),
             ("Paola Neri", "Responsabile amministrativo", "Amministrazione", "02 5551003", "p.neri@fcr.example", "", "Dipendente", "", "Sì"),
             ("Marco Colombo", "Capocantiere", "Cantieri", "347 1000004", "", "Scuola Elementare", "Dipendente", "", "Sì"),
             ("Giulia Esposito", "Ufficio gare / commerciale", "Commerciale", "02 5551005", "g.esposito@fcr.example", "", "Dipendente", "", "Sì"),
             ("Franco Bruno", "Operaio", "Cantieri", "348 1000006", "", "Villa Lago", "Dipendente", "", "Sì")]
    return pd.DataFrame([dict(zip(pe.COLONNE_PERSONE, r)) for r in righe], columns=pe.COLONNE_PERSONE)


def _cfg():
    t = st.column_config.TextColumn
    a = pe.ETICHETTE_PERSONE
    return {"Persona": t(a["Persona"], width="medium"), "Ruolo": st.column_config.SelectboxColumn(a["Ruolo"], options=pe.RUOLI, width="medium"), "Reparto": t(a["Reparto"]),
            "Telefono": t(a["Telefono"]), "Email": t(a["Email"], width="medium"), "Cantiere": t(a["Cantiere"], help="Come nella Rubrica."),
            "Tipo": st.column_config.SelectboxColumn(a["Tipo"], options=pe.TIPI), "Utente": t(a["Utente"], help="Lo compila da solo la scheda «Accessi»."),
            "Attivo": st.column_config.SelectboxColumn(a["Attivo"], options=["Sì", "No"])}


def _cfg_matricola():
    t = st.column_config.TextColumn
    n = st.column_config.NumberColumn
    a = pe.ETICHETTE_PERSONE_COMPLETE
    cfg = {"Persona": t(a["Persona"], width="medium", disabled=True, help="Si ricava da Nome e Cognome importati."),
           "Tipo": st.column_config.SelectboxColumn(a["Tipo"], options=pe.TIPI), "Attivo": st.column_config.SelectboxColumn(a["Attivo"], options=["Sì", "No"]),
           "Cantiere": t(a["Cantiere"]), "Ruolo": st.column_config.SelectboxColumn(a["Ruolo"], options=pe.RUOLI), "Reparto": t(a["Reparto"]), "Email": t(a["Email"]),
           "Telefono": t(a["Telefono"]), "Utente": t(a["Utente"])}
    for c in pe.COLONNE_MATRICOLA:
        if c in cfg:
            continue
        if c in pe.COLONNE_DATE_MATRICOLA:
            cfg[c] = t(a[c], help="Formato AAAA-MM-GG.")
        elif c == "Ore":
            cfg[c] = n(a[c])
        else:
            cfg[c] = t(a[c])
    return cfg


def _raccogli():
    return {"persone": ss["pe_pers"].to_dict("records"), "matricola": ss["pe_matricola"].to_dict("records")}


def _applica(p, nome):
    sostituisci_tabella("pe_pers", pd.DataFrame(p.get("persone") or [], columns=pe.COLONNE_PERSONE))
    sostituisci_tabella("pe_matricola", pd.DataFrame(p.get("matricola") or [], columns=pe.COLONNE_PERSONE_COMPLETE))
    ss["pe_demo"] = False


def _account(utenti_secrets):
    """Tutti gli account esistenti: {username: {ruolo, attivo, origine}}."""
    out = {u: {"ruolo": v["ruolo"], "attivo": True, "origine": "secrets"} for u, v in (utenti_secrets or {}).items()}
    try:
        for u in storage.elenca_utenti():
            out.setdefault(u["username"], {"ruolo": u["ruolo"], "attivo": bool(u["attivo"]), "origine": "database"})
    except Exception:
        pass
    return out


def _imposta_utente(persona, username):
    df = ss["pe_pers"].copy()
    df.loc[df["Persona"] == persona, "Utente"] = username
    sostituisci_tabella("pe_pers", df)


def _tab_accessi(persone, utente, utenti_secrets, audit):
    if utente.get("ruolo") != "admin":
        st.info("🔒 Gli accessi li gestisce l'amministratore. Qui vedi solo l'elenco.")
        return
    cfg = permessi.carica_config()
    profili = list(cfg["profili"])
    acc = _account(utenti_secrets)
    st.caption("Dall'elenco crei l'account di una persona e le dai il profilo giusto in un colpo solo. Il profilo decide **quali strumenti vede**; il livello decide se **può modificare** i dati (lettore = solo consulta).")
    if ss.get("tmp_pe"):
        u, pw, inviata, mail = ss.pop("tmp_pe")
        if inviata:
            st.success(f"Account **{u}** creato: ho inviato la password provvisoria a {mail}. Al primo accesso la persona sceglie la sua.")
        else:
            st.success(f"Account **{u}** creato. Password provvisoria: `{pw}` — comunicala alla persona in privato; non verrà mostrata di nuovo e va cambiata al primo accesso.")
    st.markdown("**Stato degli accessi**")
    righe = []
    for p in persone:
        u = p["Utente"]
        stato = "nessun account" if not u else ("non esiste" if u not in acc else ("attivo" if acc[u]["attivo"] else "revocato"))
        righe.append({"Persona": p["Persona"], "Ruolo": p["Ruolo"], "Profilo proposto": pe.profilo_per_ruolo(p["Ruolo"], cfg.get("mappa_ruoli")), "Utente": u, "Account": stato,
                      "Profilo attuale": cfg["utenti"].get(u, cfg["predefinito"] + " (predefinito)") if u else ""})
    st.dataframe(pd.DataFrame(righe), hide_index=True, width="stretch")

    senza = [p for p in persone if not p["Utente"] and p["Attivo"] == "Sì"]
    st.markdown("**➕ Crea l'account di una persona**")
    if not senza:
        st.caption("Tutte le persone in servizio hanno già un account (o l'elenco è vuoto).")
    else:
        nome = st.selectbox("Persona", [p["Persona"] for p in senza], key="pe_sel_crea")
        p = next(x for x in senza if x["Persona"] == nome)
        a, b, c = st.columns([2, 1.3, 1.7])
        user = a.text_input("Nome utente (nome e cognome)", pe.username_suggerito(nome, acc), key=f"pe_user_{nome}")
        mail = st.text_input("Email della persona (la password provvisoria arriva qui)", p.get("Email") or "", key=f"pe_mail_{nome}")
        livello = b.selectbox("Può modificare?", ["utente", "lettore"], format_func=lambda x: "Sì, può modificare" if x == "utente" else "No, solo consulta", key="pe_livello",
                              index=1 if p["Ruolo"] in ("Presidente", "Operaio") else 0)
        prop = pe.profilo_per_ruolo(p["Ruolo"], cfg.get("mappa_ruoli"))
        prof = c.selectbox("Cosa vede (profilo)", profili, index=profili.index(prop) if prop in profili else 0, key=f"pe_prof_{nome}")
        st.caption(f"Per il ruolo «{p['Ruolo']}» si propone il profilo «{prop}». Il profilo «presidente» apre anche il Cruscotto.")
        if st.button("🔐 Crea account e abilita", key="crea_pe", type="primary"):
            try:
                esito = onboarding.crea_account(user, mail, livello, prof, utente["username"])
            except ValueError as e:
                st.error(str(e))
            else:
                user = esito["utente"]
                _imposta_utente(nome, user)
                audit("pe_account_creato", f"{nome} → {user} ({livello}, profilo {prof})")
                ss["tmp_pe"] = (user, esito["password"], esito["inviata"], mail)
                st.rerun()

    liberi = [u for u in acc if u not in {p["Utente"] for p in persone if p["Utente"]}]
    if senza and liberi:
        with st.expander("🔗 Collega una persona a un account già esistente"):
            c1, c2, c3 = st.columns([2, 2, 1])
            pn = c1.selectbox("Persona", [p["Persona"] for p in senza], key="pe_col_p")
            un = c2.selectbox("Account", liberi, key="pe_col_u")
            c3.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
            if c3.button("Collega", key="collega_pe", width="stretch"):
                _imposta_utente(pn, un)
                audit("pe_account_collegato", f"{pn} ↔ {un}")
                st.rerun()

    con = [p for p in persone if p["Utente"] and p["Utente"] in acc]
    if con:
        st.markdown("**🛠️ Cambia il profilo o revoca l'accesso**")
        pn = st.selectbox("Persona", [p["Persona"] for p in con], key="pe_sel_mod")
        p = next(x for x in con if x["Persona"] == pn)
        att = cfg["utenti"].get(p["Utente"], cfg["predefinito"])
        c1, c2, c3 = st.columns([2, 1, 1])
        nuovo = c1.selectbox("Profilo", profili, index=profili.index(att) if att in profili else 0, key=f"pe_nuovo_prof_{p['Utente']}")
        c2.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
        c3.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
        if c2.button("💾 Salva profilo", key="salva_prof_pe", width="stretch") and nuovo != att:
            cfg["utenti"][p["Utente"]] = nuovo
            permessi.salva_config(cfg, utente["username"])
            audit("pe_profilo_cambiato", f"{p['Utente']}: {att} → {nuovo}")
            st.success("Profilo aggiornato.")
        info = acc[p["Utente"]]
        if info["origine"] == "secrets":
            c3.caption("Account nei Secrets: per revocarlo togli la riga dai Secrets.")
        elif info["attivo"]:
            if c3.button("⛔ Revoca accesso", key="revoca_pe", width="stretch"):
                storage.aggiorna_utente(p["Utente"], attivo=0)
                audit("utente_revocato", f"{p['Utente']} (da Persone e ruoli)")
                st.rerun()
        elif c3.button("✅ Riattiva", key="riattiva_pe", width="stretch"):
            storage.aggiorna_utente(p["Utente"], attivo=1)
            audit("utente_riattivato", f"{p['Utente']} (da Persone e ruoli)")
            st.rerun()
    st.caption("Ricordati di salvare l'elenco (riquadro «💾 Salva l'elenco» in alto): il collegamento persona ↔ account resta nel salvataggio.")


def render(fcr_uri, audit=None, utente="", utenti_secrets=None):
    audit = audit or (lambda *a, **k: None)
    me = ss.get("utente") or {"username": utente, "ruolo": "utente"}
    st.markdown(theme.hero(fcr_uri, "Persone e ruoli", "Chi lavora in azienda, con che ruolo, e a cosa può accedere nell'app."), unsafe_allow_html=True)
    guida.mostra("pe")
    if "pe_pers" not in ss:
        ss["pe_pers"] = _esempio()
        ss["pe_demo"] = esempi_attivi()
    if "pe_matricola" not in ss:
        ss["pe_matricola"] = pd.DataFrame(columns=pe.COLONNE_PERSONE_COMPLETE)
    pannello_archivio("pe", "l'elenco", _raccogli, _applica, audit, utente)
    st.caption("🔒 Dati personali dei lavoratori: tienili essenziali e dai accesso a questo strumento solo a chi serve (si decide da Utenti → Permessi).")
    t1, t2, t3, t4, t5 = st.tabs(["🧾 1. Elenco del personale", "🎭 2. Ruoli e profili", "🔐 3. Accessi all'app", "📄 4. Dossier", "📋 5. Libro Matricola"])
    with t1:
        banner_esempio("pe_demo", [("pe_pers", pe.COLONNE_PERSONE)], "svuota_pe")
        blocco_tabella("pe_pers", "Personale", "Una riga per persona. Il ruolo serve a proporre i permessi giusti.", pe.COLONNE_PERSONE, pe.ETICHETTE_PERSONE, _cfg(), ss["pe_pers"], "pe", 1, audit, 320, pe.SINONIMI_PERSONE)
    persone, av = pe.normalizza_persone(ss["pe_pers"].to_dict("records"))
    acc = _account(utenti_secrets)
    out = pe.calcola_pe(persone, acc)
    k = out["kpi"]

    with t2:
        cfg = permessi.carica_config()
        st.caption("Ogni ruolo ha un profilo di accesso predefinito (quali strumenti vede). Qui sotto vedi cosa apre ciascun profilo; per cambiarlo vai in Utenti → Permessi.")
        st.dataframe(pd.DataFrame([{"Ruolo in azienda": r, "Profilo proposto": pe.profilo_per_ruolo(r), "Persone": k["per_ruolo"].get(r, 0),
                                    "Strumenti che vede": ", ".join(permessi.NOMI[s] for s in cfg["profili"].get(pe.profilo_per_ruolo(r), []))} for r in pe.RUOLI]),
                     hide_index=True, width="stretch")
        st.info("Chi crea gli account è l'amministratore. Un ruolo non elencato riceve il profilo più prudente («cantiere»).")

    with t3:
        for x in av[:3]:
            st.caption("⚠️ " + x)
        _tab_accessi(persone, me, utenti_secrets, audit)
        for a in out["avvisi"][:6]:
            st.warning(a)

    with t4:
        if not persone:
            st.info("Aggiungi delle persone per generare il dossier.")
        else:
            def _gen(nome):
                return ops_report.report_generico(
                    "Persone e ruoli", "Elenco del personale", nome, dt.date.today(), [("PERSONE", str(k["persone"])), ("CON ACCOUNT", str(k["con_account"]))],
                    [("Persone", str(k["persone"]), f"{k['in_servizio']} in servizio", "info"), ("Con account", str(k["con_account"]), "accesso all'app", "info"),
                     ("Senza recapito", str(k["senza_recapito"]), "né telefono né email", "warn" if k["senza_recapito"] else "ok"), ("Da revocare", str(k["da_revocare"]), "non in servizio con accesso", "bad" if k["da_revocare"] else "ok")],
                    ("ELENCO IN ORDINE" if not out["avvisi"] else "DA CONTROLLARE", "ok" if not out["avvisi"] else "warn", f"{k['persone']} persone"),
                    [{"titolo": "Personale", "tabella": (["Persona", "Ruolo", "Reparto", "Telefono", "Cantiere", "In servizio", "Utente"],
                                                          [(p["Persona"][:22], p["Ruolo"][:22], p["Reparto"][:14], p["Telefono"][:14], p["Cantiere"][:16], p["Attivo"], p["Utente"][:16]) for p in persone])},
                     {"titolo": "Punti di attenzione", "testo": ["- " + a for a in (out["avvisi"] or ["Nessuna anomalia rilevata."])]},
                     {"titolo": "Nota", "testo": ["Documento con dati personali: va conservato e condiviso solo con chi ne ha titolo."]}],
                    [{"nome": "Personale", "intest": pe.COLONNE_PERSONE, "righe": [[p[c] for c in pe.COLONNE_PERSONE] for p in persone]}], [k["persone"]])
            scarica_dossier("pe", _gen, "Persone", audit, "Persone e ruoli")

    with t5:
        st.caption("La scheda completa di ogni dipendente (contratto, anagrafica, residenza, documenti), come nel registro cartaceo. Tutto l'elenco è già visibile qui sotto, senza doverlo aprire riga per riga.")
        blocco_tabella("pe_matricola", "Libro Matricola", "Una riga per dipendente, con tutti i dati del libro matricola.", pe.COLONNE_PERSONE_COMPLETE, pe.ETICHETTE_PERSONE_COMPLETE,
                        _cfg_matricola(), ss["pe_matricola"], "pe", 5, audit, 420, None)
        st.markdown("**📥 Importa / aggiorna dal file del Libro Matricola**")
        if sola_lettura():
            st.caption("Importazione non disponibile per il ruolo «lettore».")
        else:
            up = st.file_uploader("File del libro matricola (.xlsx)", type=["xlsx"], key="up_pe_matricola")
            if up is not None:
                try:
                    nuove, avvi, rapp = pe.importa_matricola(up)
                except Exception as e:
                    st.error(f"File non leggibile: {e}")
                    nuove = []
                if nuove:
                    st.success(f"Lette {rapp['righe']} persone dal foglio «{rapp['foglio']}».")
                    for a in avvi[:8]:
                        st.caption("⚠️ " + a)
                    modo = st.radio("Cosa fare con quelle già presenti", ["Aggiorna per matricola/nome e aggiungi le nuove", "Sostituisci tutto"], key="pe_matricola_modo")
                    if st.button("Importa nel Libro Matricola", type="primary", key="pe_matricola_importa"):
                        att = ss["pe_matricola"].to_dict("records")
                        fin = nuove if modo == "Sostituisci tutto" else pe.unisci_matricola(att, nuove)
                        sostituisci_tabella("pe_matricola", pd.DataFrame(fin, columns=pe.COLONNE_PERSONE_COMPLETE))
                        audit("pe_matricola_import", f"{up.name}: {len(nuove)} righe")
                        st.rerun()
                elif up is not None:
                    st.error("Non ho trovato le colonne del libro matricola (servono almeno «MAT.» e «COGNOME»). Controlla che sia il file giusto.")
