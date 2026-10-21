"""
FCR General Contractor - AI Business Plan & Rating Platform
Aetheris Labs - Ing. Lorenzo Di Ferdinando, Dott. Claudio Arosio

File dell'applicazione (interfaccia). La logica sta in:
    core.py      calcoli, scoring, scenari, stress test, covenant, commesse
    charts.py    grafici
    exports.py   report PDF / Word / Excel con formule
    storage.py   salvataggio pratiche e registro dei report (SQLite)

Secrets / variabili d'ambiente:
    [users.nome]     accessi per utente: hash = "..." (da make_hash.py) e ruolo = "admin" | "utente"   (consigliato)
    APP_PASSWORD     (solo compatibilita': password unica per l'utente "admin")
    GEMINI_API_KEY   (opzionale: l'utente puo' inserirne una propria nella sidebar)
    GEMINI_MODEL     (opzionale, default: gemini-3.8-flash)
    FCR_DB_PATH      (opzionale, percorso del database delle pratiche)
"""
import json
import math
import os

import pandas as pd
import streamlit as st
from google.genai import types

import admin_ui
import ai
import auth
import charts
import core
import exports
import storage
import bp_ui
import cf_ui
import dd_ui
import sc_ui
import sl_ui
import ga_ui
import fo_ui
import sx_ui
import mz_ui
import og_ui
import rp_ui
import gt_ui
import ca_ui
import hub
import guida
import ora_meteo
import pv_ui
import theme
import ui_util
import xbrl
from core import (
    COLONNE_COMMESSE, COVENANT_DEFAULT, DATI_DEFAULT, DISCLAIMER, LEVE_DEFAULT, PIANO_DEFAULT,
    SOGLIE_DEFAULT, fmt_eur, fmt_num, fmt_pct, fmt_x, ratio, to_float,
)

MAX_UPLOAD_MB = 20
MAX_EXCEL_SHEETS = 8
MAX_EXCEL_ROWS = 300
LOGO_PATH = exports.LOGO_PATH
FCR_URI = theme.logo_uri(core.LOGO_FCR_PATH, 260)
AETH_URI = theme.logo_uri(core.LOGO_PATH, 560, senza_sfondo=True)

ETICHETTE = {
    "ricavi": "Ricavi delle vendite (EUR)",
    "ebitda": "EBITDA / MOL (EUR)",
    "utile_netto": "Utile netto (EUR)",
    "totale_attivo": "Totale attivo (EUR)",
    "patrimonio_netto": "Patrimonio netto (EUR)",
    "debiti_finanziari_totali": "Debiti finanziari totali (EUR)",
    "pfn": "Posizione finanziaria netta - PFN (EUR)",
    "dscr_stimato": "DSCR stimato (x)",
}
COL_STORICO = ["anno", "ricavi", "ebitda", "patrimonio_netto", "pfn"]

st.set_page_config(
    page_title="FCR General Contractor & Aetheris Labs | Financial Suite",
    page_icon=core.LOGO_FCR_PATH if os.path.exists(core.LOGO_FCR_PATH) else "📊",
    layout="wide",
)

# ----------------------------------------------------------------------------
# CSS (prima del login, cosi' si applica anche alla schermata di accesso)
# ----------------------------------------------------------------------------
st.markdown(theme.CSS, unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# UTILITA' DI INTERFACCIA
# ----------------------------------------------------------------------------
ss = st.session_state


def get_secret(name, default=None):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name, default)


def show_df(df):
    try:
        st.dataframe(df, width="stretch", hide_index=True)
    except Exception:
        st.dataframe(df, use_container_width=True, hide_index=True)


def show_editor(df, **kw):
    try:
        return st.data_editor(df, width="stretch", **kw)
    except Exception:
        return st.data_editor(df, use_container_width=True, **kw)


def show_fig(fig):
    """Mostra il grafico a dimensione naturale (non stirato a tutta larghezza) in alta risoluzione."""
    st.image(charts.fig_png(fig, 120))


def slider_k(label, mn, mx, default, step, key):
    """Slider con chiave: passa il default solo se lo stato non e' gia' impostato."""
    if key in ss:
        return st.slider(label, mn, mx, step=step, key=key)
    return st.slider(label, mn, mx, default, step, key=key)


def number_k(label, mn, mx, default, step, key):
    if key in ss:
        return st.number_input(label, mn, mx, step=step, key=key)
    return st.number_input(label, mn, mx, default, step, key=key)


def classe_breve(classe):
    return classe.split(" - ")[0].replace("FASCIA ", "")


# ----------------------------------------------------------------------------
# AUTENTICAZIONE
# ----------------------------------------------------------------------------
def _utenti_secrets():
    cfg = get_secret("users")
    if isinstance(cfg, str):                      # variabile d'ambiente: JSON {"mario": "hash"} o {"mario": {"hash":..., "ruolo":...}}
        try:
            cfg = json.loads(cfg)
        except ValueError:
            cfg = {}
    return auth.utenti_da_secrets(cfg)


UTENTI_SECRETS = _utenti_secrets()
APP_PASSWORD = get_secret("APP_PASSWORD")


def audit(azione, dettaglio=""):
    storage.log_evento((ss.get("utente") or {}).get("username", ""), azione, dettaglio)


def check_login():
    if not UTENTI_SECRETS and not APP_PASSWORD:
        st.error("⚠️ Configurazione mancante: aggiungi almeno un utente nei secrets (sezione [users.nome] con hash e ruolo) "
                 "oppure, in modo transitorio, APP_PASSWORD.")
        return False
    u = ss.get("utente")
    if u:
        if auth.ancora_valido(u, UTENTI_SECRETS):
            return True
        ss.clear()                                # accesso revocato mentre la sessione era aperta
        st.warning("Il tuo accesso non e' piu' valido. Accedi di nuovo.")
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        st.markdown(theme.login_header(FCR_URI, AETH_URI), unsafe_allow_html=True)
        with st.form("login_form"):
            nome = st.text_input("Nome utente", key="login_user")
            pw = st.text_input("Password", type="password", key="login_pw")
            invia = st.form_submit_button("Accedi", type="primary", width="stretch")
        if invia:
            utente, errore = auth.autentica(nome, pw, UTENTI_SECRETS, APP_PASSWORD)
            if utente:
                ss["utente"] = utente
                st.rerun()
            st.error(errore)
        if APP_PASSWORD and not UTENTI_SECRETS:
            st.caption("Modalita' compatibilita': accesso come utente `admin` con la password condivisa.")
    return False


if not check_login():
    st.stop()


# ----------------------------------------------------------------------------
# AI (google-genai)
# ----------------------------------------------------------------------------
MODEL_NAME = get_secret("GEMINI_MODEL", "gemini-3.8-flash")
FALLBACK_MODELS = ["gemini-flash-latest"]
SERVER_API_KEY = get_secret("GEMINI_API_KEY", "")


def ai_generate(api_key, contents, json_mode=False, temperature=0.2):
    return ai.genera(api_key, contents, MODEL_NAME, FALLBACK_MODELS, json_mode, temperature)


pulisci_testo_ia = ai.pulisci_testo


MSG_QUOTA_ESTRAZIONE = (
    "⏳ La quota giornaliera gratuita di Gemini e' esaurita, quindi l'estrazione automatica non e' disponibile ora. "
    "Puoi continuare subito scegliendo **Inserimento Dati Manuale** qui sopra, oppure riprovare piu' tardi "
    "(di solito la quota si ripristina entro 24 ore). In alternativa attiva la fatturazione su Google AI Studio "
    "o inserisci un'altra chiave API nella barra laterale."
)
MSG_QUOTA_REPORT = (
    "⏳ L'AI non e' disponibile ora (quota esaurita o servizio sovraccarico): **PDF e Word sono stati generati senza la relazione "
    "scritta dall'AI** (contengono comunque tabelle, grafici, stress test, covenant e commesse). Per avere anche la "
    "relazione puoi riprovare piu' tardi (la quota si ripristina di solito entro 24 ore), attivare la fatturazione "
    "su Google AI Studio o inserire un'altra chiave API nella barra laterale."
)

PROMPT_ESTRAZIONE = (
    "Sei un analista fidi esperto. Dal bilancio fornito estrai i dati dell'ultimo esercizio e restituisci "
    "ESCLUSIVAMENTE un oggetto JSON con queste chiavi: anno_riferimento (intero), ricavi, ebitda, utile_netto, "
    "totale_attivo, patrimonio_netto, debiti_finanziari_totali, pfn, dscr_stimato (numeri, senza separatori delle "
    "migliaia e con il punto come separatore decimale), valori_in_migliaia (true se gli importi del documento sono "
    "espressi in migliaia di euro, altrimenti false), storico (array degli ESERCIZI PRECEDENTI presenti nel documento, "
    "ciascuno {anno, ricavi, ebitda, patrimonio_netto, pfn}; array vuoto se assenti), fonti (oggetto con una chiave per "
    "ciascun dato sopra, il cui valore e' una breve indicazione di dove l'hai letto, es. 'pag. 4 - Conto economico, "
    "voce A1' oppure 'foglio Bilancio, cella B12'; stringa vuota se il dato non e' reperibile). "
    "Se l'EBITDA non e' esposto calcolalo (valore della produzione - costi della produzione + ammortamenti e "
    "svalutazioni) e scrivilo nella fonte. La PFN e' debiti finanziari meno disponibilita' liquide. "
    "Riporta gli importi ESATTAMENTE come nel documento, senza convertire le unita'. "
    "Se un dato non e' reperibile usa null."
)


def prompt_relazione(ctx):
    base, scen, rating = ctx["dati"], ctx["scen"], ctx["rating"]
    piano_txt = "\n".join(
        f"- {r['Anno']}: ricavi {fmt_num(r['Ricavi'])} EUR, EBITDA {fmt_num(r['EBITDA'])} EUR, FCF {fmt_num(r['FCF'])} EUR, "
        f"PFN {fmt_num(r['PFN'])} EUR, PFN/EBITDA {fmt_x(r['PFN/EBITDA'])}, "
        f"DSCR {fmt_x(r['DSCR']) if r['DSCR'] is not None else 'n.d.'}"
        for r in ctx["piano"]
    )
    punti_txt = "; ".join(f"{d['indicatore']}: {core.fmt_num(d['valore'], 2) if d['valore'] is not None else 'n.d.'} -> {d['punti']}/2"
                          for d in rating["dettaglio"])
    stress_txt = "\n".join(
        f"- {s['Caso']}: PFN/EBITDA a fine piano {fmt_x(s['PFN/EBITDA anno 3'])}, "
        f"DSCR minimo {fmt_x(s['DSCR minimo']) if s['DSCR minimo'] is not None else 'n.d.'}, fascia {s['Fascia']}"
        for s in ctx["stress"]
    )
    cov_txt = "; ".join(f"{c['Anno']}: leva {c['Esito leva']}, DSCR {c['Esito DSCR']}" for c in ctx["cov_res"])
    storico_txt = ""
    if ctx["storico"]:
        storico_txt = "STORICO: " + "; ".join(
            f"{r['anno']}: ricavi {fmt_num(r['ricavi'])}, EBITDA {fmt_num(r['ebitda'])}, PN {fmt_num(r['patrimonio_netto'])}, PFN {fmt_num(r['pfn'])}"
            for r in ctx["storico"]
        ) + "\n"
    k = ctx.get("commesse_kpi")
    comm_txt = ""
    if k:
        comm_txt = (
            f"PORTAFOGLIO COMMESSE: {k['n_commesse']} commesse, importo {fmt_num(k['importo_totale'])} EUR, backlog "
            f"{fmt_num(k['backlog'])} EUR, margine medio sul backlog {fmt_num(k['margine_backlog_pct'], 1)}%, primo cliente "
            f"{fmt_num(k['top1_pct'], 0)}% e primi tre {fmt_num(k['top3_pct'], 0)}% del totale, crediti {fmt_num(k['crediti'])} EUR, "
            f"produzione non fatturata {fmt_num(k['da_fatturare'])} EUR.\n"
        )
    return (
        "Agisci come Risk Manager e redigi una relazione formale per il Comitato di Credito.\n"
        f"DATI ANNO BASE ({int(base['anno_riferimento'])}): ricavi {fmt_num(base['ricavi'])} EUR, EBITDA {fmt_num(base['ebitda'])} EUR, "
        f"utile netto {fmt_num(base['utile_netto'])} EUR, totale attivo {fmt_num(base['totale_attivo'])} EUR, patrimonio netto "
        f"{fmt_num(base['patrimonio_netto'])} EUR, debiti finanziari {fmt_num(base['debiti_finanziari_totali'])} EUR, PFN {fmt_num(base['pfn'])} EUR.\n"
        f"{storico_txt}"
        f"SCENARIO: EBITDA {fmt_num(scen['ebitda'])} EUR, PFN {fmt_num(scen['pfn'])} EUR, PN {fmt_num(scen['pn'])} EUR. "
        f"Indicatori: {punti_txt}. Punteggio {rating['punti']}/8, giudizio del modello interno: {rating['classe']}.\n"
        f"PIANO TRIENNALE:\n{piano_txt}\n"
        f"COVENANT (PFN/EBITDA max {fmt_x(ctx['covenant']['pfn_ebitda_max'])}, DSCR min {fmt_x(ctx['covenant']['dscr_min'])}): {cov_txt}\n"
        f"STRESS TEST:\n{stress_txt}\n"
        f"{comm_txt}\n"
        "Struttura: 1. Solvibilita' e struttura finanziaria. 2. Punti di forza e criticita'. 3. Sostenibilita' del piano "
        "pluriennale e tenuta negli stress test. 4. Raccomandazioni. "
        "Usa SOLO i dati forniti e riportali con le stesse cifre; non inventare numeri ne' stime. Precisa che e' una "
        "valutazione indicativa e non un rating regolamentare. Scrivi in italiano, in testo semplice senza markdown."
    )


# ----------------------------------------------------------------------------
# STATO
# ----------------------------------------------------------------------------
def storico_to_df(lst):
    df = pd.DataFrame(lst or [], columns=COL_STORICO)
    return df.astype({c: "float64" for c in COL_STORICO})


def df_to_storico(df, anno_base):
    out = {}
    for _, r in df.iterrows():
        anno = to_float(r.get("anno"), 0)
        if 1900 <= anno < anno_base:
            out[int(anno)] = {"anno": int(anno), **{k: to_float(r.get(k), 0.0) for k in COL_STORICO[1:]}}
    return [out[a] for a in sorted(out)]


def commesse_df_pulito(df):
    d = pd.DataFrame(df if df is not None else [], columns=COLONNE_COMMESSE).copy()
    for c in ("Importo", "Avanzamento_pct", "Fatturato", "Incassato", "Margine_pct"):
        d[c] = pd.to_numeric(d[c], errors="coerce").astype("float64")
    for c in ("Commessa", "Cliente"):
        d[c] = d[c].astype("object").where(d[c].notna(), "")
    return d


def imposta_dati(dati, storico, demo=False):
    ss["financial_data"] = dati
    ss["storico_base"] = storico_to_df(storico)
    ss["storico_ver"] = ss.get("storico_ver", 0) + 1
    ss["storico"] = storico
    ss["dati_demo"] = demo
    ss.pop("report", None)
    ss.pop("excel", None)


def imposta_commesse(df):
    d = commesse_df_pulito(df)
    ss["commesse_base"] = d
    ss["commesse_ver"] = ss.get("commesse_ver", 0) + 1
    ss["commesse"] = d


if "financial_data" not in ss:
    ss["financial_data"] = dict(DATI_DEFAULT)
    ss["dati_demo"] = True
    ss["storico"] = []
    ss["storico_base"] = storico_to_df([])
    ss["storico_ver"] = 0
    ss["scenari"] = {}
    imposta_commesse(commesse_df_pulito(core.commesse_vuote().iloc[0:0]))

# Valori di widget da applicare PRIMA che i widget vengano creati (carica pratica / scenario)
if "_pending" in ss:
    for _k, _v in ss.pop("_pending").items():
        ss[_k] = _v

dati = ss["financial_data"]
leve = {k: ss.get(k, 0) for k in LEVE_DEFAULT}
piano_par = {k: ss.get(f"piano_{k}", v) for k, v in PIANO_DEFAULT.items()}
soglie = {k: (ss.get(f"soglia_{k}_v", v[0]), ss.get(f"soglia_{k}_g", v[1])) for k, v in SOGLIE_DEFAULT.items()}
_valid = {"da": ss.get("soglia_valid_da", ""), "data": ss.get("soglia_valid_data", ""), "fonte": ss.get("soglia_fonte", "")}
cov = {
    "pfn_ebitda_max": ss.get("cov_lev", COVENANT_DEFAULT["pfn_ebitda_max"]),
    "dscr_min": ss.get("cov_dscr", COVENANT_DEFAULT["dscr_min"]),
}
res = core.esegui_scenario(dati, leve, piano_par, soglie)
res_base = core.esegui_scenario(dati, LEVE_DEFAULT, piano_par, soglie)
scen, piano, rating = res["scen"], res["piano"], res["rating"]


def payload_pratica():
    return {
        "dati": ss["financial_data"], "storico": ss["storico"],
        "commesse": commesse_df_pulito(ss["commesse"]).to_dict("records"),
        "scenari": ss["scenari"], "leve": leve, "piano_par": piano_par,
        "soglie": {k: list(v) for k, v in soglie.items()}, "covenant": cov, "dati_demo": ss["dati_demo"],
        "validazione": _valid,
    }


def applica_payload(p, nome):
    imposta_dati({**DATI_DEFAULT, **p.get("dati", {})}, p.get("storico", []), p.get("dati_demo", False))
    imposta_commesse(pd.DataFrame(p.get("commesse") or [], columns=COLONNE_COMMESSE))
    ss["scenari"] = p.get("scenari", {})
    pend = {"pratica_nome": nome}
    for k in LEVE_DEFAULT:
        pend[k] = int(p.get("leve", {}).get(k, 0))
    for k, v in PIANO_DEFAULT.items():
        pend[f"piano_{k}"] = float(p.get("piano_par", {}).get(k, v))
    for k, (v, g) in SOGLIE_DEFAULT.items():
        s = p.get("soglie", {}).get(k, [v, g])
        pend[f"soglia_{k}_v"], pend[f"soglia_{k}_g"] = float(s[0]), float(s[1])
    vz = p.get("validazione", {})
    pend["soglia_valid_da"], pend["soglia_valid_data"], pend["soglia_fonte"] = vz.get("da", ""), vz.get("data", ""), vz.get("fonte", "")
    c = p.get("covenant", COVENANT_DEFAULT)
    pend["cov_lev"], pend["cov_dscr"] = float(c["pfn_ebitda_max"]), float(c["dscr_min"])
    ss["_pending"] = pend


# ----------------------------------------------------------------------------
# INTESTAZIONE E SIDEBAR
# ----------------------------------------------------------------------------
MODULO = ss.get("active_module")          # None = Hub, "credit" = Credit Risk & Rating, "bp" = Business Plan Studio
PREFISSI_STATO = {"credit": ("delta_", "piano_", "soglia_", "cov_", "pratica_nome"), "bp": ("bp_",), "cf": ("cf_",), "pv": ("pv_",), "sc": ("sc_",), "sl": ("sl_",), "ga": ("ga_",), "fo": ("fo_",), "sx": ("sx_",), "mz": ("mz_",), "og": ("og_",), "rp": ("rp_",), "gt": ("gt_",), "ca": ("ca_",), "dd": ("dd_",)}


def vai_a(modulo):
    """Cambia modulo ripristinando i valori dei widget che Streamlit altrimenti dimentica."""
    if MODULO in PREFISSI_STATO:
        pf = PREFISSI_STATO[MODULO]
        ss["_snap_" + MODULO] = {k: v for k, v in ss.items() if isinstance(k, str) and k.startswith(pf)}
    ss["active_module"] = modulo
    if modulo in PREFISSI_STATO and ss.get("_snap_" + modulo):
        ss["_pending"] = dict(ss["_snap_" + modulo])
    st.rerun()


with st.sidebar:
    st.markdown(theme.sidebar_brand(AETH_URI), unsafe_allow_html=True)
    if not AETH_URI:
        st.caption("Logo Aetheris non trovato: carica aetheris_labs_logo.jpg accanto ad app.py.")
    ora_meteo.render_sidebar()
    _u = ss["utente"]
    st.markdown(f"<div style='font-size:.82rem;color:#475569;text-align:center'>👤 <b>{_u['username']}</b> · {_u['ruolo']}</div>", unsafe_allow_html=True)
    _ca, _cb = st.columns(2)
    if _u["ruolo"] == "admin" and _ca.button("👥 Utenti", key="btn_admin", width="stretch"):
        vai_a("admin")
    if _cb.button("Esci", key="btn_logout", width="stretch"):
        audit("logout")
        ss.clear()
        st.rerun()
    if _u["origine"] == "db":
        with st.expander("🔑 Account · cambia password"):
            with st.form("form_pw", clear_on_submit=True):
                _p0 = st.text_input("Password attuale", type="password")
                _p1 = st.text_input("Nuova password", type="password")
                if st.form_submit_button("Cambia password"):
                    try:
                        auth.cambia_password(_u["username"], _p0, _p1)
                        st.success("Password aggiornata.")
                    except ValueError as _e:
                        st.error(str(_e))
    st.markdown("---")
    if MODULO is not None:
        if st.button("🏠 Torna all'Hub Principale", width="stretch"):
            vai_a(None)
        st.markdown("---")

if MODULO is not None:
    if st.button("🏠 Hub", key="hub_top"):                    # visibile solo su telefono (la barra laterale e' chiusa)
        vai_a(None)

if MODULO == "credit":
    with st.sidebar:
        st.markdown("#### 📁 Pratica")
        st.text_input("Nome pratica", key="pratica_nome", placeholder="es. Rossi Costruzioni 2025")
        if st.button("💾 Salva pratica", width="stretch", disabled=ss["utente"]["ruolo"] == "lettore"):
            try:
                if ui_util.salva_protetto("credit", ss.get("pratica_nome", ""), payload_pratica(), ss["utente"]["username"], audit):
                    st.toast("Pratica salvata", icon="✅")
            except Exception as e:
                st.error(f"Impossibile salvare: {e}")
        ui_util.conflitto_salvataggio("credit", ss["utente"]["username"], audit)
        try:
            elenco = storage.elenca_pratiche()
        except Exception as e:
            elenco = []
            st.error(f"Database non disponibile: {e}")
        if elenco:
            scelta = st.selectbox("Pratiche salvate", [p["nome"] for p in elenco],
                                  format_func=lambda n: next(f"{p['nome']}  ({p['aggiornato'][:16]}" + (f", {p['autore']}" if p['autore'] else "") + ")" for p in elenco if p['nome'] == n))
            c1, c2 = st.columns(2)
            if c1.button("📂 Carica", width="stretch"):
                payload = storage.carica_pratica(scelta)
                audit("pratica_caricata", scelta)
                if payload:
                    _meta = storage.meta_pratica(scelta)
                    ss["_base_credit"] = {"nome": scelta, "agg": _meta["aggiornato"] if _meta else ""}
                    applica_payload(payload, scelta)
                    st.rerun()
            if c2.button("🗑️ Elimina", width="stretch", disabled=ss["utente"]["ruolo"] == "lettore"):
                storage.elimina_pratica(scelta)
                audit("pratica_eliminata", scelta)
                st.rerun()
        if storage.database_persistente():
            st.caption("Salvataggi su database esterno: restano anche dopo il riavvio dell'app.")
        else:
            st.caption("Database esterno non configurato: i salvataggi sono in un file locale e su hosting con disco temporaneo "
                       "(es. Streamlit Cloud) si perdono al riavvio. Imposta DATABASE_URL nei Secrets.")
        st.markdown("---")


with st.sidebar:
    user_api_key = st.text_input("Gemini API Key personale (opzionale)", value="", type="password")
    with st.expander("🔒 Privacy e trattamento dei dati"):
        for _t, _x in core.PRIVACY_PUNTI:
            st.markdown(f"**{_t}**  \n{_x}")
    st.checkbox("Ho letto l'informativa privacy e ho titolo a trattare i dati caricati", key="privacy_ok")
    _chiave = user_api_key.strip() or SERVER_API_KEY
    active_key = _chiave if ss.get("privacy_ok") else ""
    if active_key:
        st.info("Motore AI attivo per estrazione dati e relazione.")
    elif _chiave:
        st.warning("Accetta l'informativa privacy per attivare le funzioni AI. Calcoli, grafici ed Excel restano disponibili.")
    else:
        st.warning("Nessuna chiave API: le funzioni AI non sono disponibili (grafici, Excel e calcoli si').")

# ----------------------------------------------------------------------------
# HUB E ROUTING TRA I DUE MODULI
# ----------------------------------------------------------------------------
if MODULO == "admin":
    admin_ui.render(ss["utente"], UTENTI_SECRETS, audit)
    st.stop()

if MODULO is None:
    st.markdown(theme.hub_header(FCR_URI), unsafe_allow_html=True)
    hub.render(vai_a)
    st.stop()

if MODULO == "bp":
    bp_ui.render(ai_generate, active_key, FCR_URI, ai, audit, ss["utente"]["username"])
    st.stop()

if MODULO == "cf":
    cf_ui.render(FCR_URI, audit, ss["utente"]["username"])
    st.stop()

if MODULO == "sc":
    sc_ui.render(FCR_URI, audit, ss["utente"]["username"])
    st.stop()

if MODULO == "sl":
    sl_ui.render(FCR_URI, audit, ss["utente"]["username"])
    st.stop()

for _m, _ui in (("ga", ga_ui), ("fo", fo_ui), ("sx", sx_ui), ("mz", mz_ui), ("og", og_ui), ("rp", rp_ui), ("gt", gt_ui)):
    if MODULO == _m:
        _ui.render(FCR_URI, audit, ss["utente"]["username"])
        st.stop()

if MODULO == "ca":
    ca_ui.render(FCR_URI, audit)
    st.stop()

if MODULO == "dd":
    dd_ui.render(FCR_URI, audit, vai_a)
    st.stop()

if MODULO == "pv":
    pv_ui.render(ai_generate, active_key, FCR_URI, ai, audit, ss["utente"]["username"])
    st.stop()

# ----------------------------------------------------------------------------
# MODULO 1: CREDIT RISK & RATING
# ----------------------------------------------------------------------------
st.markdown(
    theme.hero(
        FCR_URI,
        "Credit Risk & Rating",
        "Valutazione del merito di credito e pianificazione pluriennale "
        "(scoring indicativo ispirato ai criteri Basilea 3/4).",
    ),
    unsafe_allow_html=True,
)
guida.mostra("credit")

# ----------------------------------------------------------------------------
# TABS
# ----------------------------------------------------------------------------
tab_dati, tab_comm, tab_sim, tab_piano, tab_scen, tab_rep = st.tabs(
    ["📂 1. Dati", "🏗️ 2. Commesse", "⚡ 3. Simulatore", "📈 4. Piano e Grafici", "🔀 5. Scenari", "📑 6. Report"]
)

# =============================== TAB 1: DATI ==================================
with tab_dati:
    st.subheader("Importazione Bilancio Aziendale (XBRL, PDF o Excel)")
    if ss.get("dati_demo"):
        st.warning("⚠️ Stai usando **dati di esempio non verificati**. Carica un bilancio o inserisci i dati reali.")

    mode = st.radio("Modalita' di caricamento:", ["Upload File (XBRL, PDF o Excel)", "Inserimento Dati Manuale"])

    if mode == "Upload File (XBRL, PDF o Excel)":
        uploaded = st.file_uploader("Trascina qui il bilancio (.pdf, .xlsx, .xls, oppure XBRL .xbrl / .xml / .zip)",
                                    type=["pdf", "xlsx", "xls", "xbrl", "xml", "zip"])
        st.caption("**XBRL** (il bilancio depositato al Registro Imprese): i dati sono gia' strutturati, vengono letti "
                   "sul posto senza AI e **non lasciano il computer**. Per PDF ed Excel i dati vengono inviati al "
                   "servizio Gemini: leggi l'informativa privacy nella barra laterale.")
        e_xbrl = bool(uploaded) and uploaded.name.lower().endswith((".xbrl", ".xml", ".zip"))
        etichetta = "📥 Importa bilancio XBRL" if e_xbrl else "🚀 Estrai Dati Contabili con AI"
        if uploaded and st.button(etichetta, type="primary"):
            if uploaded.size > MAX_UPLOAD_MB * 1024 * 1024:
                st.error(f"File troppo grande (max {MAX_UPLOAD_MB} MB).")
            elif e_xbrl:
                try:
                    raw_x, avvisi_x = xbrl.leggi(uploaded.getvalue(), uploaded.name)
                    d_n, s_n, f_n = core.normalizza_estrazione(raw_x)
                    ss["bozza"] = {"dati": d_n, "storico": s_n, "fonti": f_n, "origine": "xbrl", "avvisi": avvisi_x}
                    ss["bozza_ver"] = ss.get("bozza_ver", 0) + 1
                    audit("import_xbrl", uploaded.name)
                except xbrl.XbrlError as e:
                    st.error(f"Importazione XBRL non riuscita: {e}")
                except Exception as e:
                    st.error(f"Errore durante la lettura del file XBRL: {e}")
            elif not active_key:
                st.error("Per usare l'AI inserisci la chiave API Gemini e accetta l'informativa privacy nella sidebar.")
            else:
                name = uploaded.name.lower()
                with st.spinner("Elaborazione dati contabili in corso..."):
                    try:
                        if name.endswith(".pdf"):
                            contents = [PROMPT_ESTRAZIONE,
                                        types.Part.from_bytes(data=uploaded.getvalue(), mime_type="application/pdf")]
                        else:
                            engine = "xlrd" if name.endswith(".xls") else "openpyxl"
                            xls = pd.ExcelFile(uploaded, engine=engine)
                            testo = ""
                            for sheet in xls.sheet_names[:MAX_EXCEL_SHEETS]:
                                df = pd.read_excel(xls, sheet_name=sheet, header=None).head(MAX_EXCEL_ROWS)
                                testo += f"\n--- Foglio: {sheet} ---\n" + df.to_string(index=False, header=False)
                            contents = [PROMPT_ESTRAZIONE, testo]
                        raw_txt, _usato = ai_generate(active_key, contents, json_mode=True, temperature=0.0)
                        d_n, s_n, f_n = core.normalizza_estrazione(json.loads(raw_txt))
                        ss["bozza"] = {"dati": d_n, "storico": s_n, "fonti": f_n}
                        ss["bozza_ver"] = ss.get("bozza_ver", 0) + 1
                        audit("import_ai", uploaded.name)
                    except json.JSONDecodeError:
                        st.error("Il modello non ha restituito un JSON valido. Riprova.")
                    except Exception as e:
                        if ai.errore_temporaneo(e):
                            st.error(ai.messaggio_errore(e) + " Puoi continuare subito scegliendo **Inserimento Dati Manuale** qui sopra.")
                        else:
                            st.error(f"Errore durante l'elaborazione: {e}")
    else:
        in_migliaia = st.checkbox("Gli importi che inserisco sono in migliaia di euro")
        col_a, col_b = st.columns(2)
        with col_a:
            anno_in = st.number_input("Anno di riferimento", min_value=1990, max_value=2100,
                                      value=int(dati["anno_riferimento"]), step=1)
            ricavi_in = st.number_input("Ricavi delle Vendite", value=float(dati["ricavi"]))
            ebitda_in = st.number_input("EBITDA / MOL", value=float(dati["ebitda"]))
            utile_in = st.number_input("Utile Netto", value=float(dati["utile_netto"]))
        with col_b:
            attivo_in = st.number_input("Totale Attivo", value=float(dati["totale_attivo"]))
            pn_in = st.number_input("Patrimonio Netto", value=float(dati["patrimonio_netto"]))
            deb_in = st.number_input("Debiti Finanziari Totali", value=float(dati["debiti_finanziari_totali"]))
            pfn_in = st.number_input("Posizione Finanziaria Netta (PFN)", value=float(dati["pfn"]))
        if st.button("Aggiorna Dati Inseriti"):
            kk = 1000.0 if in_migliaia else 1.0
            nuovi = {
                **dati, "anno_riferimento": int(anno_in), "ricavi": ricavi_in * kk, "ebitda": ebitda_in * kk,
                "utile_netto": utile_in * kk, "totale_attivo": attivo_in * kk, "patrimonio_netto": pn_in * kk,
                "debiti_finanziari_totali": deb_in * kk, "pfn": pfn_in * kk,
            }
            imposta_dati(nuovi, [r for r in ss["storico"] if r["anno"] < nuovi["anno_riferimento"]])
            st.rerun()

    # ---- Verifica dei dati estratti (conferma campo per campo) ---------------
    bozza = ss.get("bozza")
    if bozza:
        st.markdown("### ✍️ Verifica i dati estratti prima di applicarli")
        _xb = bozza.get("origine") == "xbrl"
        st.caption("Confronta ogni valore con la fonte indicata " + ("nel file XBRL" if _xb else "dall'AI")
                   + " e correggi dove serve. I campi 'NON TROVATO' contengono valori di esempio da sostituire.")
        for _a in bozza.get("avvisi", []):
            st.info(_a)
        ver = ss.get("bozza_ver", 0)
        anno_b = st.number_input("Anno di riferimento", min_value=1990, max_value=2100,
                                 value=int(bozza["dati"]["anno_riferimento"]), step=1, key=f"bozza_anno_{ver}")
        chiavi = [k for k in DATI_DEFAULT if k != "anno_riferimento"]
        df_b = pd.DataFrame(
            {"Campo": [ETICHETTE[k] for k in chiavi],
             "Valore": [float(bozza["dati"][k]) for k in chiavi],
             "Fonte indicata": [bozza["fonti"].get(k, "") for k in chiavi]},
            index=chiavi,
        )
        ed_b = show_editor(
            df_b, key=f"ed_bozza_{ver}", disabled=["Campo", "Fonte indicata"],
            column_config={"Valore": st.column_config.NumberColumn(format="%.2f")},
        )
        st.markdown("**Esercizi precedenti rilevati (opzionale, modificabili):**")
        ed_s = show_editor(
            storico_to_df(bozza["storico"]), key=f"ed_bozza_storico_{ver}", num_rows="dynamic",
            column_config={"anno": st.column_config.NumberColumn("Anno", format="%.0f"),
                           **{k: st.column_config.NumberColumn(k, format="%.0f") for k in COL_STORICO[1:]}},
        )
        nuovi = dict(DATI_DEFAULT)
        for k in chiavi:
            nuovi[k] = to_float(ed_b.loc[k, "Valore"], DATI_DEFAULT[k])
        nuovi["anno_riferimento"] = int(anno_b)
        for a in core.valida_dati(nuovi):
            st.warning(f"⚠️ {a}")
        cb1, cb2 = st.columns(2)
        if cb1.button("✅ Conferma e applica", type="primary"):
            imposta_dati(nuovi, df_to_storico(ed_s, nuovi["anno_riferimento"]))
            ss.pop("bozza", None)
            st.rerun()
        if cb2.button("Annulla"):
            ss.pop("bozza", None)
            st.rerun()

    # ---- Storico ---------------------------------------------------------------
    with st.expander("📚 Storico esercizi precedenti (per vedere il trend)", expanded=False):
        st.caption("Inserisci fino a 3-4 esercizi precedenti all'anno base. Sono usati nei grafici e nei report.")
        ed_st = show_editor(
            ss["storico_base"], key=f"ed_storico_{ss['storico_ver']}", num_rows="dynamic",
            column_config={"anno": st.column_config.NumberColumn("Anno", format="%.0f"),
                           **{k: st.column_config.NumberColumn(k, format="%.0f") for k in COL_STORICO[1:]}},
        )
        ss["storico"] = df_to_storico(ed_st, int(dati["anno_riferimento"]))

    for avviso in core.valida_dati(dati):
        st.warning(f"⚠️ {avviso}")
    st.markdown("### 📊 Stato Attuale del Dataset")
    st.json(dati)

# ============================= TAB 2: COMMESSE ================================
with tab_comm:
    st.subheader("🏗️ Portafoglio commesse e lavori in corso")
    st.caption("Inserisci le commesse in corso: importo contrattuale, avanzamento (%), SAL fatturati e incassati, "
               "margine atteso. Il portafoglio entra nei report e nella relazione.")
    ed_c = show_editor(
        ss["commesse_base"], key=f"ed_commesse_{ss['commesse_ver']}", num_rows="dynamic",
        column_config={
            "Commessa": st.column_config.TextColumn("Commessa"),
            "Cliente": st.column_config.TextColumn("Cliente"),
            "Importo": st.column_config.NumberColumn("Importo contratto (EUR)", format="%.0f", min_value=0),
            "Avanzamento_pct": st.column_config.NumberColumn("Avanzamento (%)", format="%.1f", min_value=0, max_value=100),
            "Fatturato": st.column_config.NumberColumn("Fatturato SAL (EUR)", format="%.0f", min_value=0),
            "Incassato": st.column_config.NumberColumn("Incassato (EUR)", format="%.0f", min_value=0),
            "Margine_pct": st.column_config.NumberColumn("Margine atteso (%)", format="%.1f"),
        },
    )
    ss["commesse"] = commesse_df_pulito(ed_c)
    kpi_c, per_cli = core.analisi_commesse(ss["commesse"], dati["ricavi"])
    if kpi_c is None:
        st.info("Nessuna commessa inserita (aggiungi almeno una riga con importo > 0).")
    else:
        m = st.columns(4)
        m[0].metric("Backlog residuo", fmt_eur(kpi_c["backlog"]))
        m[1].metric("Copertura ricavi", fmt_x(kpi_c["copertura_ricavi"]) if kpi_c["copertura_ricavi"] is not None else "n.d.")
        m[2].metric("Margine medio backlog", fmt_pct(kpi_c["margine_backlog_pct"]))
        m[3].metric("Primo cliente", fmt_pct(kpi_c["top1_pct"], 0))
        m2 = st.columns(3)
        m2[0].metric("Crediti da commesse", fmt_eur(kpi_c["crediti"]))
        m2[1].metric("Prodotto non fatturato", fmt_eur(kpi_c["da_fatturare"]),
                     help="Negativo = fatturato in eccesso rispetto all'avanzamento (anticipi).")
        m2[2].metric("Primi 3 clienti", fmt_pct(kpi_c["top3_pct"], 0))
        if kpi_c["top1_pct"] > 40:
            st.warning("⚠️ Forte concentrazione su un solo cliente: rischio di dipendenza.")
        show_fig(charts.fig_commesse(per_cli, "light"))

# ============================ TAB 3: SIMULATORE ===============================
with tab_sim:
    st.subheader("🎯 Simulatore di Scoring e Ottimizzazione")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("#### ⚙️ Leve Strategiche")
        slider_k("Variazione Debito Netto - PFN (€)", -500000, 500000, 0, 25000, "delta_pfn")
        slider_k("Iniezione Capitale / Mezzi Propri (€)", 0, 500000, 0, 25000, "delta_pn")
        slider_k("Variazione EBITDA (€)", -100000, 300000, 0, 10000, "delta_ebitda")
        st.caption("L'aumento di capitale entra come liquidita': aumenta il patrimonio netto e riduce la PFN. "
                   "Una PFN negativa indica cassa netta.")
    with col2:
        st.markdown("#### 📈 Output Modulo di Scoring")
        m1, m2, m3, m4 = st.columns(4)
        d1 = rating["pfn_ebitda"] - res_base["rating"]["pfn_ebitda"]
        d2 = rating["pfn_pn"] - res_base["rating"]["pfn_pn"]
        m1.metric("PFN / EBITDA", fmt_x(rating["pfn_ebitda"]),
                  delta=None if (math.isinf(d1) or math.isnan(d1) or d1 == 0) else f"{d1:+.2f}x vs base", delta_color="inverse")
        m2.metric("PFN / Patrimonio Netto", fmt_x(rating["pfn_pn"]),
                  delta=None if (math.isinf(d2) or math.isnan(d2) or d2 == 0) else f"{d2:+.2f}x vs base", delta_color="inverse")
        m3.metric("DSCR (Anno 1)", fmt_x(rating["dscr"]) if rating["dscr"] is not None else "n.d.")
        m4.metric("Fascia", classe_breve(rating["classe"]))
        st.markdown(theme.scorecard(rating["punti"], rating["classe"]), unsafe_allow_html=True)

    st.markdown("#### 🔍 Perche' questo punteggio")
    det = pd.DataFrame(
        [
            {
                "Indicatore": x["indicatore"],
                "Valore": exports._valore_dettaglio(x),
                "Soglie (verde / giallo)": exports._soglie_testo(x),
                "Punti": f"{x['punti']}/2",
                "Esito": {2: "🟢", 1: "🟡", 0: "🔴"}[x["punti"]],
            }
            for x in rating["dettaglio"]
        ]
    )
    show_df(det)
    st.caption("Verde: punteggio ≥ 7 su 8. Rossa: punteggio < 4, oppure patrimonio netto ≤ 0, oppure EBITDA ≤ 0.")

    with st.expander("⚙️ Soglie di scoring per settore (calibrazione)"):
        st.caption("I profili sono ipotesi di lavoro ragionate, NON benchmark ufficiali (Cerved, Istat, Banca d'Italia). "
                   "Prima di usarli per decisioni vanno validati da un esperto, oppure sostituiti con benchmark reali importati da file.")
        st.markdown(f"**Profilo in uso:** {core.nome_profilo(soglie)}")
        cp1, cp2 = st.columns([3, 1])
        prof_sel = cp1.selectbox("Profilo di settore", list(core.PROFILI_SOGLIE), key="profilo_sel", label_visibility="collapsed")
        if cp2.button("Applica", key="profilo_applica", width="stretch"):
            ss["_pending"] = {f"soglia_{k}_{i}": float(core.PROFILI_SOGLIE[prof_sel][k][j])
                              for k in SOGLIE_DEFAULT for j, i in enumerate(("v", "g"))}
            st.rerun()
        up = st.file_uploader("Importa benchmark da file JSON", type=["json"], key="profilo_file",
                              help='Formato: {"nome": "...", "fonte": "...", "soglie": {"pfn_ebitda": [2.5, 4.5], "pfn_pn": [1.0, 2.0], "equity_ratio": [0.25, 0.15], "dscr": [1.3, 1.0]}}')
        if up is not None and ss.get("_profilo_file_id") != (up.name, up.size):
            try:
                _n, _f, _s = core.parse_profilo_soglie(up.getvalue().decode("utf-8"))
                ss["_pending"] = {f"soglia_{k}_{i}": float(_s[k][j]) for k in SOGLIE_DEFAULT for j, i in enumerate(("v", "g"))}
                ss["_pending"]["soglia_fonte"] = _f or _n
                ss["_profilo_file_id"] = (up.name, up.size)
                st.rerun()
            except ValueError as _e:
                st.error(str(_e))
        st.download_button("📥 Scarica le soglie correnti (JSON)", core.profilo_json(core.nome_profilo(soglie), soglie, ss.get("soglia_fonte", "")),
                           file_name="soglie_rating.json", mime="application/json")
        st.markdown("**Validazione** (compare nei report)")
        cv1, cv2 = st.columns(2)
        cv1.text_input("Validate da (nome e qualifica)", key="soglia_valid_da", placeholder="es. Dott. Rossi, commercialista")
        cv2.text_input("Data validazione", key="soglia_valid_data", placeholder="gg/mm/aaaa")
        st.text_input("Fonte / benchmark utilizzato", key="soglia_fonte", placeholder="es. Cerved Industry Forecast 2025, ATECO 41-43")
        st.caption(core.testo_validazione(_valid))
        nomi_s = {"pfn_ebitda": "PFN / EBITDA (minore = meglio)", "pfn_pn": "PFN / PN (minore = meglio)",
                  "equity_ratio": "PN / Attivo (decimale, maggiore = meglio)", "dscr": "DSCR (maggiore = meglio)"}
        for k, lab in nomi_s.items():
            ca, cb = st.columns(2)
            with ca:
                number_k(f"{lab} - verde", 0.0, 50.0, float(SOGLIE_DEFAULT[k][0]), 0.05, f"soglia_{k}_v")
            with cb:
                number_k(f"{lab} - giallo", 0.0, 50.0, float(SOGLIE_DEFAULT[k][1]), 0.05, f"soglia_{k}_g")
            v, g = soglie[k]
            if (core.VERSO[k] == "min" and v > g) or (core.VERSO[k] == "max" and v < g):
                st.warning(f"⚠️ Soglie incoerenti per {lab}: la soglia verde deve essere "
                           f"{'≤' if core.VERSO[k] == 'min' else '≥'} della gialla.")

    st.markdown("#### 🎯 Cosa serve per migliorare la fascia")

    @st.cache_data(show_spinner=False)
    def tabella_leve(d_in, lv_in, par_in, sog_in):
        # attenzione: i parametri NON devono iniziare con "_" (verrebbero esclusi dalla chiave di cache)
        out = []
        for target in ("VERDE", "GIALLA"):
            riga = {"Obiettivo": f"Fascia {target.lower()}"}
            for leva, nome in (("delta_pn", "Capitale da iniettare"), ("delta_ebitda", "Miglioramento EBITDA"),
                               ("delta_pfn", "Riduzione del debito netto")):
                x = core.leva_minima(d_in, lv_in, par_in, sog_in, leva, target, step=5000.0, massimo=3_000_000.0)
                riga[nome] = "non raggiungibile con questa leva" if x is None else ("gia' raggiunta" if x == 0 else fmt_eur(x))
            out.append(riga)
        return out

    st.caption("Valore minimo di ciascuna leva, da sola, per raggiungere l'obiettivo (le altre impostazioni restano come sono).")
    show_df(pd.DataFrame(tabella_leve(dati, leve, piano_par, soglie)))

    st.markdown("#### 🌪️ Stress test")
    st_rows = core.stress_test(dati, leve, piano_par, soglie)
    show_df(pd.DataFrame(
        [{"Caso": s["Caso"], "PFN/EBITDA a fine piano": fmt_x(s["PFN/EBITDA anno 3"]),
          "DSCR minimo": fmt_x(s["DSCR minimo"]) if s["DSCR minimo"] is not None else "n.d.",
          "Punteggio": f"{s['Punteggio']}/8", "Fascia": s["Fascia"]} for s in st_rows]
    ))

# ============================ TAB 4: PIANO E GRAFICI ==========================
with tab_piano:
    st.subheader("📈 Proiezioni Pluriennali (3 Anni)")
    st.caption("Il piano parte dai valori dello scenario impostato nel simulatore.")
    cp1, cp2, cp3 = st.columns(3)
    with cp1:
        slider_k("Crescita Annua Ricavi (%)", -10.0, 30.0, PIANO_DEFAULT["g_ricavi"], 0.5, "piano_g_ricavi")
        slider_k("Crescita Annua EBITDA (%)", -10.0, 30.0, PIANO_DEFAULT["g_ebitda"], 0.5, "piano_g_ebitda")
        slider_k("CCN su variazione ricavi (%)", 0.0, 60.0, PIANO_DEFAULT["ccn_pct"], 1.0, "piano_ccn_pct")
    with cp2:
        number_k("Capex annuo (€)", 0.0, 5_000_000.0, PIANO_DEFAULT["capex"], 10000.0, "piano_capex")
        number_k("Ammortamenti annui (€)", 0.0, 5_000_000.0, PIANO_DEFAULT["amm"], 10000.0, "piano_amm")
        number_k("Rimborso annuo quota capitale (€)", 0.0, 5_000_000.0, PIANO_DEFAULT["rimborso"], 10000.0, "piano_rimborso")
    with cp3:
        number_k("Tasso d'interesse sulla PFN (%)", 0.0, 20.0, PIANO_DEFAULT["tasso"], 0.25, "piano_tasso")
        number_k("Aliquota fiscale (%)", 0.0, 60.0, PIANO_DEFAULT["aliquota"], 0.5, "piano_aliquota")
        number_k("Covenant: PFN/EBITDA massimo (x)", 0.0, 20.0, COVENANT_DEFAULT["pfn_ebitda_max"], 0.1, "cov_lev")
        number_k("Covenant: DSCR minimo (x)", 0.0, 10.0, COVENANT_DEFAULT["dscr_min"], 0.05, "cov_dscr")

    show_df(pd.DataFrame(
        [{"Anno": r["Anno"], "Ricavi": fmt_eur(r["Ricavi"]), "EBITDA": fmt_eur(r["EBITDA"]),
          "Free Cash Flow": fmt_eur(r["FCF"]), "PFN": fmt_eur(r["PFN"]), "PFN/EBITDA": fmt_x(r["PFN/EBITDA"]),
          "DSCR": fmt_x(r["DSCR"]) if r["DSCR"] is not None else "n.d."} for r in piano]
    ))
    st.caption("FCF = EBITDA − imposte − capex − interessi − variazione CCN; PFN(t) = PFN(t−1) − FCF. "
               "Il rimborso del debito usa cassa e non modifica la PFN, ma incide sul DSCR = (EBITDA − imposte − ΔCCN) / (interessi + rimborso).")

    st.markdown("#### Verifica covenant")
    cov_res = core.verifica_covenant(piano, cov)
    show_df(pd.DataFrame(
        [{"Anno": c["Anno"], "PFN/EBITDA": fmt_x(c["PFN/EBITDA"]), "Limite": fmt_x(c["Limite PFN/EBITDA"]),
          "Leva": "✅ OK" if c["Esito leva"] == "OK" else "❌ SFORATO",
          "DSCR": fmt_x(c["DSCR"]) if c["DSCR"] is not None else "n.d.", "Limite DSCR": fmt_x(c["Limite DSCR"]),
          "Copertura DSCR": "✅ OK" if c["Esito DSCR"] == "OK" else "❌ SFORATO"} for c in cov_res]
    ))

    st.markdown("#### Grafici")
    gc1, gc2 = st.columns(2)
    piani = {"Scenario corrente": piano}
    if any(v != 0 for v in leve.values()):
        piani["Base (nessuna leva)"] = res_base["piano"]
    with gc1:
        show_fig(charts.fig_pfn_ebitda(piani, soglie, cov["pfn_ebitda_max"], "light",
                                       anno_base=int(dati["anno_riferimento"]), base_val=ratio(scen["pfn"], scen["ebitda"])))
    with gc2:
        show_fig(charts.fig_dscr(piano, soglie, cov["dscr_min"], "light"))
    gc3, gc4 = st.columns(2)
    with gc3:
        show_fig(charts.fig_cascata(piano, scen["pfn"], "light"))
    with gc4:
        show_fig(charts.fig_storico(ss["storico"], dati, piano, "light"))

# ============================== TAB 5: SCENARI ================================
with tab_scen:
    st.subheader("🔀 Confronto scenari")
    st.caption("Salva la combinazione corrente di leve e ipotesi con un nome e confrontala con gli altri scenari.")
    cs1, cs2 = st.columns([3, 1])
    nome_sc = cs1.text_input("Nome scenario", placeholder="es. Prudente, Aumento di capitale, Ottimista", key="nome_scenario")
    if cs2.button("➕ Salva scenario", width="stretch"):
        n = (nome_sc or "").strip()
        if not n:
            st.error("Inserisci un nome.")
        elif n in ("Base", "Corrente"):
            st.error("Nome riservato.")
        else:
            ss["scenari"][n] = {"leve": {k: int(v) for k, v in leve.items()}, "piano_par": dict(piano_par)}
            st.success(f"Scenario '{n}' salvato.")

    conf = {"Base": res_base}
    if any(v != 0 for v in leve.values()):
        conf["Corrente (non salvato)"] = res
    for n, sc in ss["scenari"].items():
        conf[n] = core.esegui_scenario(dati, sc["leve"], sc.get("piano_par", piano_par), soglie)

    righe_c = []
    for n, r in conf.items():
        dscrs = [x["DSCR"] for x in r["piano"] if x["DSCR"] is not None]
        lv = r["leve"]
        desc = "; ".join(f"{lab} {v:+,.0f}".replace(",", ".") for lab, v in
                         (("Debito", lv["delta_pfn"]), ("Capitale", lv["delta_pn"]), ("EBITDA", lv["delta_ebitda"])) if v) or "nessuna leva"
        righe_c.append({"Scenario": n, "Leve": desc, "PFN/EBITDA a fine piano": fmt_x(r["piano"][-1]["PFN/EBITDA"]),
                        "PFN a fine piano": fmt_eur(r["piano"][-1]["PFN"]),
                        "DSCR minimo": fmt_x(min(dscrs)) if dscrs else "n.d.",
                        "Punteggio": f"{r['rating']['punti']}/8", "Fascia": classe_breve(r["rating"]["classe"])})
    show_df(pd.DataFrame(righe_c))
    if len(conf) > 1:
        show_fig(charts.fig_confronto(conf, soglie, "light"))
    else:
        st.info("Modifica le leve nel simulatore e salva uno scenario per avviare il confronto.")

    if ss["scenari"]:
        st.markdown("#### Scenari salvati")
        for n in list(ss["scenari"].keys()):
            c1, c2, c3 = st.columns([4, 1, 1])
            c1.write(f"**{n}**")
            if c2.button("Carica", key=f"load_{n}"):
                sc = ss["scenari"][n]
                pend = {k: int(v) for k, v in sc["leve"].items()}
                for k, v in sc.get("piano_par", piano_par).items():
                    pend[f"piano_{k}"] = float(v)
                ss["_pending"] = pend
                st.rerun()
            if c3.button("Elimina", key=f"del_{n}"):
                ss["scenari"].pop(n)
                st.rerun()

# ============================== TAB 6: REPORT =================================
with tab_rep:
    st.subheader("📑 Report per il Comitato di Credito")
    if ss.get("dati_demo"):
        st.warning("⚠️ I dati sono di esempio non verificati: i documenti lo riporteranno esplicitamente.")

    ctx = exports.costruisci_ctx(
        dati, leve, piano_par, soglie, cov, ss["storico"], commesse_df_pulito(ss["commesse"]),
        ss["scenari"], ss["dati_demo"], MODEL_NAME, ss.get("pratica_nome", ""), _valid,
    )
    st.caption(f"ID report corrente: **{ctx['report_id']}** (cambia al variare di dati, leve, ipotesi, soglie, scenari e commesse).")

    usa_ai = st.checkbox("Includi la relazione scritta dall'AI", value=bool(active_key), disabled=not active_key)
    st.caption("💡 Se togli la spunta ottieni comunque PDF e Word completi di tabelle, grafici, stress test, covenant e "
               "commesse, ma senza il testo del parere dell'AI. Utile se la quota di Gemini e' esaurita o se non hai una chiave.")
    if st.button("🚀 Genera Report PDF + Word", type="primary"):
        with st.spinner("Creazione dei documenti in corso..."):
            try:
                avvisi, quota_esaurita, relazione = [], False, None
                if usa_ai and active_key:
                    try:
                        testo, usato = ai_generate(active_key, prompt_relazione(ctx), temperature=0.3)
                        relazione = pulisci_testo_ia(testo)
                        ctx["modello"] = usato
                        avvisi = core.numeri_sospetti(relazione, {k: v for k, v in ctx.items() if k not in ("commesse_df", "per_cliente")})
                    except Exception as e_ai:
                        if not ai.errore_temporaneo(e_ai):
                            raise
                        quota_esaurita = True
                if relazione is None:
                    relazione = "Relazione non generata (funzione AI non utilizzata). Vedere tabelle e grafici."
                    ctx["modello"] = "nessuno"
                grafici = exports.grafici_report(ctx)
                ss["report"] = {
                    "text": relazione, "pdf": exports.genera_pdf(ctx, relazione, grafici),
                    "docx": exports.genera_docx(ctx, relazione, grafici), "report_id": ctx["report_id"],
                    "avvisi": avvisi, "modello": ctx["modello"], "quota": quota_esaurita,
                }
                audit("report_credit", f"{ctx['report_id']} pratica={ss.get('pratica_nome', '')}")
                try:
                    storage.log_report(ss.get("pratica_nome", ""), ctx["report_id"], ctx["modello"], ctx["hash_dati"],
                                       {"punti": rating["punti"], "classe": rating["classe"]})
                except Exception:
                    pass
            except Exception as e:
                st.error(f"Errore nella generazione del report: {e}")

    rep = ss.get("report")
    if rep:
        if rep.get("quota"):
            st.warning(MSG_QUOTA_REPORT)
        if rep["report_id"] != ctx["report_id"]:
            st.warning("⚠️ Dati o ipotesi sono cambiati dopo la generazione: rigenera i documenti per allinearli.")
        if rep["avvisi"]:
            st.warning("⚠️ La relazione cita numeri che non risultano nei dati di calcolo: verificali prima dell'uso → "
                       + ", ".join(rep["avvisi"][:12]))
        st.markdown("### 📄 Relazione")
        st.text(rep["text"])
        d1, d2 = st.columns(2)
        d1.download_button("📥 Scarica PDF", rep["pdf"], file_name=f"Report_{rep['report_id']}.pdf", mime="application/pdf")
        d2.download_button("📥 Scarica Word (modificabile)", rep["docx"], file_name=f"Report_{rep['report_id']}.docx",
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    st.markdown("### 📊 Excel con formule vive")
    st.caption("Il foglio Input contiene le ipotesi (celle gialle); Piano, Rating e Commesse si ricalcolano modificandole.")
    if st.button("Prepara file Excel"):
        try:
            ss["excel"] = {"bytes": exports.genera_excel(ctx), "report_id": ctx["report_id"]}
            audit("excel_credit", ctx["report_id"])
        except Exception as e:
            st.error(f"Errore nella generazione dell'Excel: {e}")
    if ss.get("excel"):
        st.download_button("📥 Scarica Excel", ss["excel"]["bytes"], file_name=f"Modello_{ss['excel']['report_id']}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if ss["excel"]["report_id"] != ctx["report_id"]:
            st.warning("⚠️ L'Excel preparato non riflette le ultime modifiche: preparalo di nuovo.")

    with st.expander("🗂️ Registro dei report generati (audit)"):
        try:
            reg = storage.elenco_report(ss.get("pratica_nome") or None)
            if reg:
                show_df(pd.DataFrame(reg))
            else:
                st.caption("Nessun report registrato per questa pratica.")
        except Exception as e:
            st.caption(f"Registro non disponibile: {e}")

    st.caption(DISCLAIMER)
