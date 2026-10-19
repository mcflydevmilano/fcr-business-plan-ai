"""dd_ui.py - Cruscotto di direzione: semafori di margine, cassa, crediti e rating dai moduli della suite."""
import streamlit as st

import bp_ui
import cf_ui
import dd
import dd_report
import pv_ui
import sc_ui
import sl_ui
import storage
import theme

ss = st.session_state

MODULI = [("sc", "Scadenzario", "Cassa, crediti e debiti"), ("cf", "Cash Flow di cantiere", "Liquidità e margine dei cantieri"),
          ("pv", "Computo e Preventivo", "Margine del preventivo"), ("credit", "Credit Risk & Rating", "Rating indicativo"),
          ("bp", "Business Plan Studio", "DSCR del piano"), ("sl", "SAL e contabilità lavori", "Margine a finire delle commesse")]
SESSIONE = "Dati della sessione"
NESSUNO = "Non usare"


def _sessione_disponibile(m):
    if m == "sc":
        return "sc_df" in ss
    if m == "cf":
        return "cf_df" in ss
    if m == "pv":
        return "pv_df" in ss
    if m == "sl":
        return "sl_com" in ss
    if m == "bp":
        return any(isinstance(k, str) and k.startswith("bp_") for k in ss)
    return False                              # il rating si legge dalle pratiche salvate


def _payload_sessione(m):
    return {"sc": sc_ui._raccogli, "cf": cf_ui._raccogli, "pv": pv_ui._raccogli, "bp": bp_ui._raccogli, "sl": sl_ui._raccogli}[m]()


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
        if m == "credit":
            return dd.metriche_credit(payload)
        return dd.metriche_bp(payload)
    except Exception as e:
        st.warning(f"Impossibile leggere i dati di «{m}»: {e}")
        return None


def render(fcr_uri, audit=None):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Cruscotto di direzione",
                           "Margine, cassa, crediti e rating dell'azienda in un colpo d'occhio: semafori e azioni da fare."), unsafe_allow_html=True)
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
                demo = (m in ("sc", "cf", "sl") and ss.get(f"{m}_demo"))
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
    if st.button("📄 Genera il rapporto PDF", type="primary", key="gen_dd"):
        ctx = dd_report.costruisci_ctx_dd(righe, gen, azioni, fonti)
        ss["dd_rep"] = {"pdf": dd_report.genera_pdf_dd(ctx), "id": ctx["report_id"]}
        audit("dd_report", ctx["report_id"])
    rep = ss.get("dd_rep")
    if rep:
        st.download_button("📥 Scarica il rapporto di direzione", rep["pdf"], file_name=f"Cruscotto_{rep['id']}.pdf", mime="application/pdf")
    st.caption("I semafori sintetizzano i dati dei moduli secondo soglie di lavoro modificabili: sono un supporto alle decisioni, non una valutazione regolamentare.")
