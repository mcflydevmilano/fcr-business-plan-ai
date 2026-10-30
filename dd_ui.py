"""dd_ui.py - Cruscotto di direzione: semafori di margine, cassa, crediti e rating dai moduli della suite."""
import streamlit as st
import guida

import bp_ui
import cf_ui
import dd
import demo as demo_mod
import dd_report
import pv_ui
import sc_ui
import sl_ui
import og_ui
import rp_ui
import gt_ui
import mz_ui
import sx_ui
import fo_ui
import ga_ui
import html as _html
import os
import pandas as pd
import riepilogo
import storage
import theme
from ui_util import sola_lettura

ss = st.session_state

MODULI = [("sc", "Scadenzario", "Cassa, crediti e debiti"), ("cf", "Cash Flow di cantiere", "Liquidità e margine dei cantieri"),
          ("pv", "Computo e Preventivo", "Margine del preventivo"), ("credit", "Credit Risk & Rating", "Rating indicativo"),
          ("bp", "Business Plan Studio", "DSCR del piano"), ("sl", "SAL e contabilità lavori", "Margine a finire delle commesse"), ("rc", "Registro commerciale", "Pipeline e interventi scaduti"), ("of", "Offerta e finanziamenti", "Copertura finanziaria dell'appalto"), ("ga", "Gare e offerte", "Scadenze delle gare"), ("fo", "Fornitori", "Documenti in scadenza"),
          ("sx", "Sicurezza", "Formazioni e documenti di cantiere"), ("mz", "Parco mezzi", "Scadenze e utilizzo"), ("og", "Organico", "Carico di lavoro"), ("rp", "Rapportini di cantiere", "Segnalazioni e rapportini"), ("gt", "Cronoprogramma", "Ritardi sulle fasi dei cantieri")]
SESSIONE = "Dati della sessione"
NESSUNO = "Non usare"


_SESS_KEY = {"rc": "rc_df", "of": "of_voci", "ga": "ga_gare", "fo": "fo_doc", "sx": "sx_pers", "mz": "mz_mezzi", "og": "og_ris", "rp": "rp_rapp", "gt": "gt_fasi", "lg": "lg_riserve", "sa": "sa_con", "pr": "pr_per", "mt": "mt_ord", "vr": "vr_ver", "ad": "ad_doc"}


def _sessione_disponibile(m):
    if m == "sc":
        return "sc_df" in ss
    if m == "cf":
        return "cf_df" in ss
    if m == "pv":
        return "pv_df" in ss
    if m == "sl":
        return "sl_com" in ss
    if m in _SESS_KEY:
        return _SESS_KEY[m] in ss
    if m == "bp":
        return any(isinstance(k, str) and k.startswith("bp_") for k in ss)
    return False                              # il rating si legge dalle pratiche salvate


def _payload_sessione(m):
    return {"sc": sc_ui._raccogli, "cf": cf_ui._raccogli, "pv": pv_ui._raccogli, "bp": bp_ui._raccogli, "sl": sl_ui._raccogli, "rc": __import__("rc_ui")._raccogli, "of": __import__("of_ui")._raccogli, "ga": ga_ui._raccogli, "fo": fo_ui._raccogli, "sx": sx_ui._raccogli, "mz": mz_ui._raccogli, "og": og_ui._raccogli, "rp": rp_ui._dati, "gt": gt_ui._raccogli, "lg": __import__("lg_ui")._raccogli}.get(m, lambda: getattr(__import__("nuovi_ui"), m + "_ui")._raccogli())()


def _elenco_salvati(m, demo=False):
    try:
        return storage.elenca_pratiche(modulo=m, demo=demo)
    except Exception:
        return []


def _calcola(m, payload):
    try:
        if m == "sc":
            return dd.metriche_sc(payload)
        if m == "cf":
            return dd.metriche_cf(payload)
        if m == "pv":
            return dd.metriche_pv(payload)
        if m == "sl":
            return dd.metriche_sl(payload)
        if m in ("rc", "of", "ga", "fo", "sx", "mz", "og", "rp", "gt"):
            return getattr(dd, "metriche_" + m)(payload)
        if m == "credit":
            return dd.metriche_credit(payload)
        return dd.metriche_bp(payload)
    except Exception as e:
        st.warning(f"Impossibile leggere i dati di «{m}»: {e}")
        return None


def _canali():
    email = all(os.environ.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "MAIL_TO"))
    slack = (os.environ.get("SLACK_WEBHOOK_URL") or "").startswith("https://hooks.slack.com/")
    return email, slack


def _avvisa(blocchi, squadra, audit):
    """Manda l'avviso interno su Slack e/o email (gli stessi canali del riepilogo del mattino)."""
    chi = (ss.get("utente") or {}).get("username", "")
    ogg, testo = dd.messaggio_team(blocchi, squadra, da=chi)
    email, slack = _canali()
    if not (email or slack):
        st.warning("Nessun canale configurato: per mandare gli avvisi servono i segreti di Slack (SLACK_WEBHOOK_URL) e/o dell'email. Le istruzioni sono in Calendario scadenze, scheda «3. Riepilogo email».")
        return
    inviati = []
    try:
        if slack:
            riepilogo.invia_slack(ogg, testo)
            inviati.append("Slack")
        if email:
            riepilogo.invia(ogg, testo, "<pre style='font-family:Segoe UI,Arial,sans-serif;font-size:14px'>" + _html.escape(testo) + "</pre>")
            inviati.append("email")
    except Exception as e:
        st.error(f"Invio non riuscito: {e}")
    if inviati:
        st.success("Avviso inviato a " + (squadra or "tutto il team") + " su " + " e ".join(inviati) + ".")
        audit("dd_avviso", f"{squadra or 'tutti'}")


def _da_fare(blocchi, vai_a, audit):
    st.subheader("Chi contattare e cosa controllare")
    if not blocchi:
        st.caption("Nessun nominativo da mostrare: le liste compaiono quando ci sono fatture, documenti o segnalazioni da gestire.")
        return
    lettore = sola_lettura()
    squadre = sorted({b["squadra"] for b in blocchi})
    with st.container(key="avvdd_team"):
        st.caption("Gli avvisi vanno sul canale Slack e/o sull'email del team (gli stessi del riepilogo del mattino). Nel messaggio c'è l'elenco con i nomi.")
        cols = st.columns(len(squadre) + 1)
        for col, s in zip(cols, squadre):
            if col.button(f"📨 Avvisa {s}", key=f"avv_{s}", disabled=lettore, width="stretch"):
                _avvisa(blocchi, s, audit)
        if cols[-1].button("📨 Avvisa tutti", key="avv_tutti", disabled=lettore, width="stretch"):
            _avvisa(blocchi, None, audit)
    nomi_mod = {m: n for m, n, _ in MODULI}
    for b in blocchi:
        ico = "🔴" if b["gravita"] == "bad" else "🟡"
        with st.expander(f"{ico} {b['titolo']} · {len(b['righe'])}  —  a cura di: {b['squadra']}", expanded=b["gravita"] == "bad"):
            st.dataframe(pd.DataFrame(b["righe"], columns=b["colonne"]), hide_index=True, width="stretch")
            a, c = st.columns(2)
            if vai_a and a.button(f"Apri {nomi_mod.get(b['modulo'], b['modulo'])}  →", key=f"vai_{b['id']}", width="stretch"):
                vai_a(b["modulo"])
            if c.button(f"📨 Avvisa solo per questa lista", key=f"avvb_{b['id']}", disabled=lettore, width="stretch"):
                _avvisa([b], b["squadra"], audit)


def _griglia_semafori(righe, vai_a, apri, audit):
    """Le caselle del Cruscotto, tre per riga. Sotto ognuna un pulsante che apre lo strumento da cui arriva il dato
    (con il salvataggio che il Cruscotto sta usando) e lascia il pulsante «Torna al Cruscotto» in cima."""
    nomi = {m: n for m, n, _ in MODULI}
    for i0 in range(0, len(righe), 3):
        cols = st.columns(3)
        for j, r in enumerate(righe[i0:i0 + 3]):
            i = i0 + j
            with cols[j], st.container(key=f"semc_{i}"):
                st.markdown(theme.semaforo_card(r), unsafe_allow_html=True)
                m = r.get("Modulo")
                if not (vai_a and m):
                    continue
                etichetta = {"bad": "Vai al problema  →", "warn": "Vai al problema  →", "nd": "Compila i dati  →"}.get(r["Stato"], "Apri  →")
                if st.button(etichetta, key=f"semvai_{i}", type="primary" if r["Stato"] in ("bad", "warn") else "secondary",
                             help=f"Apre «{nomi.get(m, m)}»", width="stretch"):
                    ss["_apri_pratica"] = {"modulo": m, "nome": apri.get(m), "giri": 0}
                    ss["_torna_dd"] = {"indicatore": r["Indicatore"], "valore": r["Valore"], "nota": r["Nota"], "stato": r["Stato"]}
                    audit("dd_semaforo_aperto", f"{r['Indicatore']} -> {m}")
                    vai_a(m)


def _avvisi(righe, modo_demo, apri, metriche, audit, gen=None, azioni=None, fonti=None):
    """Avvisi del Cruscotto per email e chat interna: invio automatico (solo da dati veri e salvati) e impostazione di chi riceve cosa."""
    import avvisi_dd
    import chat
    import notifiche
    u = ss.get("utente") or {}
    admin = u.get("ruolo") == "admin"
    try:
        cfg = avvisi_dd.carica_cfg()
    except Exception:
        return
    noti = []
    try:
        noti = [x["username"] for x in storage.elenca_utenti()]
    except Exception:
        pass
    salvati = bool(metriche) and all(apri.get(m) for m in metriche)          # tutti i dati vengono da salvataggi, non da prove nella sessione
    if cfg["auto"] and cfg["regole"] and not modo_demo and salvati and u.get("ruolo") in ("admin", "utente") and not ss.get("_dd_auto"):
        ss["_dd_auto"] = True                              # una volta per sessione: poi vale il «una volta al giorno»
        try:
            esito = avvisi_dd.invia(righe, cfg, utenti_noti=noti)
            if esito["regole"]:
                audit("avvisi_cruscotto_auto", f"chat {esito['chat']}, email {esito['email']}")
                st.toast(f"Avvisi inviati: {esito['chat']} in chat, {esito['email']} email", icon="🔔")
            if any("Email" in x for x in esito["errori"]):
                st.warning("Gli avvisi per email non sono stati inviati: l'invio è stato bloccato per prevenire il blocco del dominio. Controlla le impostazioni della posta.")
        except Exception:
            pass
    with st.expander("🔔 Avvisi per email e chat interna", expanded=False):
        n_gr = sum(1 for r in righe if r["Stato"] in ("bad", "warn"))
        st.caption("Chi viene avvisato quando un semaforo diventa giallo o rosso. Lo stesso problema si manda al massimo una volta al giorno. "
                   "Gli avvisi automatici partono solo da dati veri e salvati, mai da prove o dati dimostrativi.")
        st.write(f"- Email: **{'pronta' if avvisi_dd.smtp_pronto() else 'non configurata (servono SMTP_HOST, SMTP_USER, SMTP_PASSWORD nei Secrets)'}**")
        if admin and not sola_lettura():
            canali = [""] + [c["nome"] for c in chat.tutti_i_canali_gestibili() if c["tipo"] == "pubblico" and not c["archiviato"]]
            base = pd.DataFrame([{"Area": r["area"], "Da": avvisi_dd.GRAVITA[r["da"]], "Canale chat": r["canale"], "Persone (nomi utente)": ", ".join(r["persone"]),
                                  "Email": ", ".join(r["email"])} for r in cfg["regole"]] or [{"Area": avvisi_dd.TUTTE, "Da": avvisi_dd.GRAVITA["bad"], "Canale chat": "", "Persone (nomi utente)": "", "Email": ""}])
            ed = st.data_editor(base, num_rows="dynamic", hide_index=True, width="stretch", key="avvdd_tab", column_config={
                "Area": st.column_config.SelectboxColumn(options=[avvisi_dd.TUTTE] + avvisi_dd.AREE, required=True),
                "Da": st.column_config.SelectboxColumn(options=list(avvisi_dd.GRAVITA.values()), required=True),
                "Canale chat": st.column_config.SelectboxColumn(options=canali),
                "Persone (nomi utente)": st.column_config.TextColumn(help="Nomi utente separati da virgola: ricevono un messaggio diretto dal «Cruscotto» e l'avviso sul telefono."),
                "Email": st.column_config.TextColumn(help="Indirizzi separati da virgola.")})
            auto = st.checkbox("Invia automaticamente quando qualcuno apre il Cruscotto (da dati salvati)", value=cfg["auto"], key="avvdd_auto")
            rep = cfg["report"]
            rattivo = st.checkbox("Rapporto di direzione in PDF ogni lunedì, per email", value=rep["attivo"], key="avvdd_rep_on",
                                  help="Lo manda il controllo programmato (job_avvisi.py): serve che sia attivo sul vostro server o su GitHub Actions.")
            remail = st.text_input("Indirizzi del rapporto (separati da virgola)", ", ".join(rep["email"]), key="avvdd_rep_email", disabled=not rattivo)
            if st.button("💾 Salva le regole", key="avvdd_salva"):
                inv = {v: k for k, v in avvisi_dd.GRAVITA.items()}
                regole = [{"area": r["Area"], "da": inv.get(r["Da"], "bad"), "canale": r["Canale chat"] or "", "persone": r["Persone (nomi utente)"] or "", "email": r["Email"] or ""}
                          for r in ed.to_dict("records")]
                nuova = avvisi_dd.salva_cfg({"regole": regole, "auto": auto, "report": {"attivo": rattivo, "email": remail}}, u.get("username", ""))
                audit("avvisi_cruscotto_regole", f"{len(nuova['regole'])} regole")
                ignote = sorted({p for r in nuova["regole"] for p in r["persone"] if p not in noti})
                if ignote:
                    st.warning("Nomi utente non riconosciuti: " + ", ".join(ignote))
                st.success(f"Salvate {len(nuova['regole'])} regole.")
        else:
            st.caption("Le regole le imposta l'amministratore." if cfg["regole"] else "Nessuna regola impostata: le imposta l'amministratore.")
        if cfg["report"]["attivo"] and cfg["report"]["email"] and u.get("ruolo") in ("admin", "utente") and gen is not None:
            if st.button("📄 Invia ora il rapporto PDF", key="avvdd_rep_ora", help="Manda subito il PDF di questa schermata a chi e' indicato nel rapporto settimanale."):
                e = avvisi_dd.invia_rapporto(righe, gen, azioni or [], fonti or {}, cfg, forza=True)
                audit("avvisi_cruscotto_rapporto", f"email {e['email']}")
                (st.success(f"Rapporto inviato a {e['email']} indirizzi.") if e["email"] else st.error(" ".join(e["errori"]) or e["saltato"]))
        if cfg["regole"] and u.get("ruolo") in ("admin", "utente"):
            if st.button(f"📨 Invia ora gli avvisi ({n_gr} semafori da guardare)", key="avvdd_ora", disabled=not n_gr,
                         help="Manda subito, anche se sono gia' stati inviati oggi. Se stai guardando dati dimostrativi o non salvati, gli avvisi si basano su quelli."):
                esito = avvisi_dd.invia(righe, cfg, forza=True, utenti_noti=noti)
                audit("avvisi_cruscotto_manuale", f"chat {esito['chat']}, email {esito['email']}")
                st.success(f"Inviati: {esito['chat']} messaggi in chat, {esito['email']} email, {esito['telefono']} avvisi sul telefono.")
                for e in esito["errori"]:
                    st.error(e)


def render(fcr_uri, audit=None, vai_a=None):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Cruscotto di direzione",
                           "Margine, cassa, crediti e rating dell'azienda in un colpo d'occhio: semafori e azioni da fare."), unsafe_allow_html=True)
    guida.mostra("dd")
    try:
        import freschezza
        _righe_fr = freschezza.valuta(storage.ultimi_aggiornamenti())
        try:
            import pz
            _righe_fr.append(pz.stato_validita(pz.carica_indice()))
        except Exception:
            pass
        _fermi = freschezza.fermi(_righe_fr)
    except Exception:
        _fermi = []
    if _fermi:
        st.warning("**Attenzione: alcuni dati sono vecchi.** I semafori sotto si basano su dati che non vengono salvati da tempo:  \n" + "  \n".join("• " + freschezza.frase(r) for r in _fermi[:8]))
    metriche, fonti, apri = {}, {}, {}
    demo_presenti = demo_mod.presenti()
    n_veri = sum(1 for m, _, _ in MODULI if _elenco_salvati(m))
    modo_demo = False
    if demo_presenti:
        modo = st.radio("Dati mostrati", ["Dati veri", "🎬 Dati dimostrativi"], index=1 if n_veri < 3 else 0, horizontal=True, key="dd_modo",
                        help="I dati dimostrativi sono fittizi: servono a vedere come funziona il cruscotto. Non toccano i dati veri.")
        modo_demo = modo.startswith("🎬")
        if modo_demo:
            st.info("🎬 **Stai vedendo dati dimostrativi (fittizi).** Servono a mostrare come funziona il cruscotto: per i dati dell'azienda scegli «Dati veri» qui sopra.")
    with st.expander("🔌 Fonti dei dati", expanded=False):
        st.caption("Per ogni modulo scegli i dati da usare: quelli su cui stai lavorando ora, un salvataggio, oppure nessuno.")
        for m, nome, _ in MODULI:
            salvati = _elenco_salvati(m, modo_demo)
            opz = ([SESSIONE] if _sessione_disponibile(m) and not modo_demo else []) + [p["nome"] for p in salvati] + [NESSUNO]
            scelta = st.selectbox(nome, opz, key=f"dd_fonte_{m}_{'d' if modo_demo else 'v'}")
            if scelta == NESSUNO:
                fonti[nome] = "non usato"
                continue
            apri[m] = None if scelta == SESSIONE else scelta          # cosa aprire se si clicca il semaforo di questo strumento
            if scelta == SESSIONE:
                payload = _payload_sessione(m)
                demo = (m in ("sc", "cf", "sl", "ga", "fo", "sx", "mz", "og", "rp", "gt") and ss.get(f"{m}_demo"))
                fonti[nome] = "dati della sessione" + (" (esempio)" if demo else "")
            else:
                payload = storage.carica_pratica(scelta, modulo=m)
                fonti[nome] = f"salvataggio «{scelta}»"
            if payload:
                metriche[m] = _calcola(m, payload)
        with st.expander("Soglie dei semafori"):
            a, b, c = st.columns(3)
            marg = a.number_input("Margine lordo obiettivo (%)", 0.0, 80.0, dd.DD_DEFAULT["margine_target"], 1.0, key="dd_margine")
            sw = b.number_input("Crediti scaduti: giallo oltre (%)", 0.0, 100.0, dd.DD_DEFAULT["scaduto_warn"], 1.0, key="dd_scw")
            sb = c.number_input("Crediti scaduti: rosso oltre (%)", 0.0, 100.0, dd.DD_DEFAULT["scaduto_bad"], 1.0, key="dd_scb")
    if (ss.get("utente") or {}).get("ruolo") == "admin" and not sola_lettura():
        with st.expander("🎬 Dati dimostrativi (per far vedere la suite)"):
            st.caption("Carica un esempio compilato per ogni strumento, con date aggiornate a oggi. **Non tocca i dati veri**: i salvataggi di prova si chiamano «DEMO - Esempio» e non entrano nel riepilogo email, nella ricerca o nei permessi.")
            c1, c2 = st.columns(2)
            if c1.button("🎬 Carica i dati dimostrativi", key="dd_demo_on", width="stretch"):
                fatti = demo_mod.carica((ss.get("utente") or {}).get("username", ""))
                audit("demo_caricati", ", ".join(fatti))
                st.toast(f"Caricati {len(fatti)} strumenti di prova", icon="🎬")
                st.rerun()
            if c2.button("🧹 Togli i dati dimostrativi", key="dd_demo_off", width="stretch", disabled=not demo_presenti):
                n = demo_mod.rimuovi()
                audit("demo_rimossi", str(n))
                st.toast(f"Tolti {n} salvataggi di prova", icon="🧹")
                st.rerun()
            if demo_presenti:
                st.caption("Presenti per: " + ", ".join(sorted(demo_presenti)) + ". In ogni strumento, nel riquadro «Salva e riapri», spunta «Mostra anche i dati dimostrativi» per aprirli.")
    soglie = {"margine_target": ss.get("dd_margine", dd.DD_DEFAULT["margine_target"]), "scaduto_warn": ss.get("dd_scw", dd.DD_DEFAULT["scaduto_warn"]),
              "scaduto_bad": ss.get("dd_scb", dd.DD_DEFAULT["scaduto_bad"])}
    righe, gen, azioni = dd.semafori(metriche, soglie)
    c = dd.conteggio(righe)
    titolo = {"ok": "Tutto sotto controllo", "warn": "Alcuni punti di attenzione", "bad": "Servono interventi", "nd": "Dati insufficienti"}[gen]
    st.markdown(theme.semaforo_generale(gen, titolo, f"{c['ok']} in regola · {c['warn']} da tenere d'occhio · {c['bad']} {'critico' if c['bad'] == 1 else 'critici'} · {c['nd']} senza dati"), unsafe_allow_html=True)
    _griglia_semafori(righe, vai_a, apri, audit)
    _avvisi(righe, modo_demo, apri, metriche, audit, gen, azioni, fonti)
    st.caption("🟢 in regola · 🟡 da tenere d'occhio · 🔴 serve un intervento · ⚪ mancano i dati. Sotto, «Cosa fare» dice cosa decidere e «Chi contattare» chi chiamare.")
    st.subheader("Cosa fare")
    if azioni:
        for g, t in azioni:
            (st.error if g == "bad" else st.warning)(t)
    elif gen == "nd":
        st.info("Inserisci i dati nei moduli (o salvali) per popolare il cruscotto.")
    else:
        st.success("Nessuna azione urgente.")
    _da_fare(dd.dettagli(metriche), vai_a, audit)
    if st.button("📄 Genera il rapporto PDF", type="primary", key="gen_dd"):
        ctx = dd_report.costruisci_ctx_dd(righe, gen, azioni, fonti)
        ss["dd_rep"] = {"pdf": dd_report.genera_pdf_dd(ctx), "id": ctx["report_id"]}
        audit("dd_report", ctx["report_id"])
    rep = ss.get("dd_rep")
    if rep:
        st.download_button("📥 Scarica il rapporto di direzione", rep["pdf"], file_name=f"Cruscotto_{rep['id']}.pdf", mime="application/pdf")
    st.caption("I semafori sintetizzano i dati dei moduli secondo soglie di lavoro modificabili: sono un supporto alle decisioni, non una valutazione regolamentare.")
