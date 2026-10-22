"""dd_ui.py - Cruscotto di direzione: semafori di margine, cassa, crediti e rating dai moduli della suite."""
import streamlit as st
import guida

import bp_ui
import cf_ui
import dd
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
          ("bp", "Business Plan Studio", "DSCR del piano"), ("sl", "SAL e contabilità lavori", "Margine a finire delle commesse"), ("ga", "Gare e offerte", "Scadenze delle gare"), ("fo", "Fornitori", "Documenti in scadenza"),
          ("sx", "Sicurezza", "Formazioni e documenti di cantiere"), ("mz", "Parco mezzi", "Scadenze e utilizzo"), ("og", "Organico", "Carico di lavoro"), ("rp", "Rapportini di cantiere", "Segnalazioni e rapportini"), ("gt", "Cronoprogramma", "Ritardi sulle fasi dei cantieri")]
SESSIONE = "Dati della sessione"
NESSUNO = "Non usare"


_SESS_KEY = {"ga": "ga_gare", "fo": "fo_doc", "sx": "sx_pers", "mz": "mz_mezzi", "og": "og_ris", "rp": "rp_rapp", "gt": "gt_fasi", "lg": "lg_riserve"}


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
    return {"sc": sc_ui._raccogli, "cf": cf_ui._raccogli, "pv": pv_ui._raccogli, "bp": bp_ui._raccogli, "sl": sl_ui._raccogli, "ga": ga_ui._raccogli, "fo": fo_ui._raccogli, "sx": sx_ui._raccogli, "mz": mz_ui._raccogli, "og": og_ui._raccogli, "rp": rp_ui._dati, "gt": gt_ui._raccogli, "lg": __import__("lg_ui")._raccogli}[m]()


def _elenco_salvati(m):
    try:
        return storage.elenca_pratiche(modulo=m)
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
        if m in ("ga", "fo", "sx", "mz", "og", "rp", "gt"):
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
    with st.container(key="dd_avvisi_team"):
        st.caption("Gli avvisi vanno sul canale Slack e/o sull'email del team (gli stessi del riepilogo del mattino). Nel messaggio c'è l'elenco con i nomi.")
        cols = st.columns(len(squadre) + 1)
        for col, s in zip(cols, squadre):
            if col.button(f"📨 Avvisa {s}", key=f"avv_{s}", disabled=lettore, use_container_width=True):
                _avvisa(blocchi, s, audit)
        if cols[-1].button("📨 Avvisa tutti", key="avv_tutti", disabled=lettore, use_container_width=True):
            _avvisa(blocchi, None, audit)
    nomi_mod = {m: n for m, n, _ in MODULI}
    for b in blocchi:
        ico = "🔴" if b["gravita"] == "bad" else "🟡"
        with st.expander(f"{ico} {b['titolo']} · {len(b['righe'])}  —  a cura di: {b['squadra']}", expanded=b["gravita"] == "bad"):
            st.dataframe(pd.DataFrame(b["righe"], columns=b["colonne"]), hide_index=True, use_container_width=True)
            a, c = st.columns(2)
            if vai_a and a.button(f"Apri {nomi_mod.get(b['modulo'], b['modulo'])}  →", key=f"vai_{b['id']}", use_container_width=True):
                vai_a(b["modulo"])
            if c.button(f"📨 Avvisa solo per questa lista", key=f"avvb_{b['id']}", disabled=lettore, use_container_width=True):
                _avvisa([b], b["squadra"], audit)


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
    metriche, fonti = {}, {}
    with st.expander("🔌 Fonti dei dati", expanded=False):
        st.caption("Per ogni modulo scegli i dati da usare: quelli su cui stai lavorando ora, un salvataggio, oppure nessuno.")
        for m, nome, _ in MODULI:
            salvati = _elenco_salvati(m)
            opz = ([SESSIONE] if _sessione_disponibile(m) else []) + [p["nome"] for p in salvati] + [NESSUNO]
            scelta = st.selectbox(nome, opz, key=f"dd_fonte_{m}")
            if scelta == NESSUNO:
                fonti[nome] = "non usato"
                continue
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
    soglie = {"margine_target": ss.get("dd_margine", dd.DD_DEFAULT["margine_target"]), "scaduto_warn": ss.get("dd_scw", dd.DD_DEFAULT["scaduto_warn"]),
              "scaduto_bad": ss.get("dd_scb", dd.DD_DEFAULT["scaduto_bad"])}
    righe, gen, azioni = dd.semafori(metriche, soglie)
    c = dd.conteggio(righe)
    titolo = {"ok": "Tutto sotto controllo", "warn": "Alcuni punti di attenzione", "bad": "Servono interventi", "nd": "Dati insufficienti"}[gen]
    st.markdown(theme.semaforo_generale(gen, titolo, f"{c['ok']} in regola · {c['warn']} da tenere d'occhio · {c['bad']} {'critico' if c['bad'] == 1 else 'critici'} · {c['nd']} senza dati"), unsafe_allow_html=True)
    st.markdown(theme.semafori_html(righe), unsafe_allow_html=True)
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
