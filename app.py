"""
FCR General Contractor - AI Business Plan & Rating Platform
Aetheris Labs - Ing. Lorenzo Di Ferdinando

Dipendenze (requirements.txt):
    streamlit>=1.40
    pandas
    openpyxl
    xlrd
    fpdf2>=2.7
    google-genai

Secrets / variabili d'ambiente:
    APP_PASSWORD     (obbligatoria)
    GEMINI_API_KEY   (opzionale: l'utente puo' inserirne una propria nella sidebar)
    GEMINI_MODEL     (opzionale, default: gemini-2.5-flash)
"""
import hmac
import io
import json
import math
import os
import re

import pandas as pd
import streamlit as st
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from google import genai
from google.genai import types

# ----------------------------------------------------------------------------
# COSTANTI
# ----------------------------------------------------------------------------
LOGO_PATH = "aetheris_labs_logo.jpg"
MAX_LOGIN_ATTEMPTS = 5
MAX_UPLOAD_MB = 20
MAX_EXCEL_SHEETS = 8
MAX_EXCEL_ROWS = 300

CAMPI_MONETARI = [
    "ricavi", "ebitda", "utile_netto", "totale_attivo",
    "patrimonio_netto", "debiti_finanziari_totali", "pfn",
]

DATI_DEFAULT = {
    "anno_riferimento": 2025,
    "ricavi": 2500000.0,
    "ebitda": 300000.0,
    "utile_netto": 120000.0,
    "totale_attivo": 3000000.0,
    "patrimonio_netto": 800000.0,
    "debiti_finanziari_totali": 900000.0,
    "pfn": 600000.0,
    "dscr_stimato": 1.45,
}

PIANO_DEFAULT = {
    "g_ricavi": 5.0,
    "g_ebitda": 6.0,
    "rimborso": 50000.0,
    "capex": 60000.0,
    "amm": 100000.0,
    "aliquota": 27.9,      # IRES 24% + IRAP 3,9% (indicativa)
    "tasso": 4.5,
    "ccn_pct": 20.0,
}

# Soglie del modello di scoring interno (indicativo, NON un rating regolamentare)
SOGLIE = {
    "pfn_ebitda": (2.5, 4.5),    # minore = meglio (verde, giallo)
    "pfn_pn": (1.0, 2.0),        # minore = meglio
    "equity_ratio": (0.25, 0.15),  # maggiore = meglio
    "dscr": (1.30, 1.00),        # maggiore = meglio
}

DISCLAIMER = (
    "Il presente documento e' una simulazione indicativa basata su un modello di scoring interno e "
    "su dati forniti dall'utente e/o estratti automaticamente con strumenti di intelligenza artificiale. "
    "Non costituisce un rating regolamentare ai sensi di Basilea 3/4, ne' un parere di merito creditizio "
    "di alcun istituto di credito, ne' consulenza finanziaria. I dati devono essere verificati da un "
    "professionista prima di qualsiasi utilizzo decisionale."
)

st.set_page_config(
    page_title="FCR General Contractor | AI Business Plan & Rating Platform",
    page_icon="📊",
    layout="wide",
)

# ----------------------------------------------------------------------------
# CSS (prima del login, cosi' si applica anche alla schermata di accesso)
# ----------------------------------------------------------------------------
st.markdown(
    """
<style>
    .stApp { background-color: #0b0f19; color: #e2e8f0; font-family: 'Inter', sans-serif; }
    [data-testid="stSidebar"] > div:first-child { padding-top: 1rem; }
    [data-testid="stSidebar"] { background-color: #111827; border-right: 1px solid #1f2937; }
    [data-testid="stSidebar"] img { border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
    h1, h2, h3 { color: #f8fafc; font-weight: 700; }
    .stTabs [data-baseweb="tab"] {
        background-color: #1e293b; border-radius: 8px 8px 0px 0px; color: #94a3b8;
        padding: 10px 20px; font-weight: 600; border: none;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #1e3a8a 0%, #0284c7 100%) !important;
        color: #ffffff !important; box-shadow: 0 4px 12px rgba(2, 132, 199, 0.3);
    }
    .stButton > button, .stDownloadButton > button {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); color: white;
        border-radius: 8px; padding: 0.6rem 1.2rem; font-weight: 600; border: none;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4); transition: all 0.3s ease;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        transform: translateY(-2px); box-shadow: 0 6px 20px rgba(37, 99, 235, 0.6);
    }
    [data-testid="stMetricValue"] { font-size: 1.8rem; font-weight: 700; color: #38bdf8; }
    .stTextInput input, .stNumberInput input {
        background-color: #1e293b; color: white; border-radius: 6px; border: 1px solid #334155;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------------------
# UTILITA'
# ----------------------------------------------------------------------------
def get_secret(name, default=None):
    """Legge da st.secrets, poi dalle variabili d'ambiente."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name, default)


def show_logo(col_ratio=(1, 2.2, 1)):
    if not os.path.exists(LOGO_PATH):
        return False
    _, mid, _ = st.columns(list(col_ratio))
    with mid:
        try:
            st.image(LOGO_PATH, width="stretch")
        except Exception:
            st.image(LOGO_PATH, use_container_width=True)
    return True


def show_df(df):
    try:
        st.dataframe(df, width="stretch", hide_index=True)
    except Exception:
        st.dataframe(df, use_container_width=True, hide_index=True)


def fmt_num(x, dec=0):
    """Formato italiano: 1.234.567,89"""
    if x is None or (isinstance(x, float) and (math.isnan(x))):
        return "n.d."
    if isinstance(x, float) and math.isinf(x):
        return "n.s."
    s = f"{x:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_eur(x, dec=0):
    v = fmt_num(x, dec)
    return v if v in ("n.d.", "n.s.") else f"{v} EUR"


def fmt_x(x):
    v = fmt_num(x, 2)
    return v if v in ("n.d.", "n.s.") else f"{v}x"


def to_float(v, default=0.0):
    """Converte numeri o stringhe (anche in formato italiano) in float."""
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("€", "").replace("EUR", "").replace(" ", "")
    if not s:
        return default
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        n = float(s)
    except ValueError:
        return default
    return -n if neg else n


def normalizza_dati(raw):
    """Unisce l'output dell'AI ai default, converte i tipi e scala le migliaia."""
    if isinstance(raw, list) and raw:
        raw = raw[0]
    if not isinstance(raw, dict):
        raise ValueError("Il modello non ha restituito un oggetto JSON valido.")

    in_migliaia = bool(raw.get("valori_in_migliaia", False))
    dati = dict(DATI_DEFAULT)
    for k, default in DATI_DEFAULT.items():
        if k in raw and raw[k] is not None:
            dati[k] = to_float(raw[k], default)
    dati["anno_riferimento"] = int(dati["anno_riferimento"]) or DATI_DEFAULT["anno_riferimento"]
    if in_migliaia:
        for k in CAMPI_MONETARI:
            dati[k] *= 1000.0
    return dati


def valida_dati(d):
    """Restituisce una lista di avvisi di coerenza."""
    w = []
    if d["ricavi"] <= 0:
        w.append("I ricavi sono nulli o negativi.")
    if d["ebitda"] > d["ricavi"] > 0:
        w.append("L'EBITDA supera i ricavi: controlla le unita' (euro o migliaia?).")
    if d["totale_attivo"] > 0 and d["patrimonio_netto"] > d["totale_attivo"]:
        w.append("Il patrimonio netto supera il totale attivo.")
    if d["pfn"] > d["debiti_finanziari_totali"] > 0:
        w.append("La PFN supera i debiti finanziari totali (possibile solo con liquidita' negativa).")
    if d["patrimonio_netto"] <= 0:
        w.append("Patrimonio netto nullo o negativo: situazione di possibile perdita del capitale.")
    if d["ebitda"] <= 0:
        w.append("EBITDA nullo o negativo: i rapporti basati sull'EBITDA non sono significativi.")
    return w


def ratio(num, den):
    """Rapporto sicuro. Den <= 0 con num > 0 -> inf (non significativo)."""
    if den > 0:
        return num / den
    return math.inf if num > 0 else 0.0


# ----------------------------------------------------------------------------
# MOTORE DI CALCOLO
# ----------------------------------------------------------------------------
def proietta(ricavi0, ebitda0, pfn0, p, anno_base, n=3):
    """
    Proiezione pluriennale con free cash flow:
        FCF  = EBITDA - imposte - capex - interessi - variazione CCN
        PFN_t = PFN_(t-1) - FCF
    Il rimborso del debito NON riduce la PFN (usa cassa), ma pesa sul DSCR.
        DSCR = (EBITDA - imposte - variazione CCN) / (interessi + rimborso)
    """
    rows = []
    r_prev, e, pfn = ricavi0, ebitda0, pfn0
    for i in range(1, n + 1):
        r = r_prev * (1 + p["g_ricavi"] / 100.0)
        e = e * (1 + p["g_ebitda"] / 100.0)
        interessi = max(pfn, 0.0) * p["tasso"] / 100.0
        imposte = max(e - p["amm"] - interessi, 0.0) * p["aliquota"] / 100.0
        d_ccn = p["ccn_pct"] / 100.0 * (r - r_prev)
        fcf = e - imposte - p["capex"] - interessi - d_ccn
        pfn_new = pfn - fcf
        servizio = interessi + p["rimborso"]
        dscr = (e - imposte - d_ccn) / servizio if servizio > 0 else None
        rows.append(
            {
                "Anno": f"Anno {i} ({int(anno_base) + i})",
                "Ricavi": r,
                "EBITDA": e,
                "FCF": fcf,
                "PFN": pfn_new,
                "PFN/EBITDA": ratio(pfn_new, e),
                "DSCR": dscr,
            }
        )
        r_prev, pfn = r, pfn_new
    return rows


def _punti_min(v, verde, giallo):
    return 2 if v < verde else (1 if v < giallo else 0)


def _punti_max(v, verde, giallo):
    return 2 if v >= verde else (1 if v >= giallo else 0)


def calcola_rating(pfn, ebitda, pn, attivo, dscr):
    pfn_ebitda = ratio(pfn, ebitda)
    pfn_pn = ratio(pfn, pn)
    equity_ratio = pn / attivo if attivo > 0 else 0.0

    punti = _punti_min(pfn_ebitda, *SOGLIE["pfn_ebitda"])
    punti += _punti_min(pfn_pn, *SOGLIE["pfn_pn"])
    punti += _punti_max(equity_ratio, *SOGLIE["equity_ratio"])
    punti += 2 if dscr is None else _punti_max(dscr, *SOGLIE["dscr"])

    if pn <= 0 or ebitda <= 0 or punti < 4:
        classe = "FASCIA ROSSA - Rischio Elevato / Requisiti di Garanzia"
    elif punti >= 7:
        classe = "FASCIA VERDE - Rating Elevato / Bancabile"
    else:
        classe = "FASCIA GIALLA - Rating Neutro / Sotto Osservazione"

    return {
        "pfn_ebitda": pfn_ebitda,
        "pfn_pn": pfn_pn,
        "equity_ratio": equity_ratio,
        "dscr": dscr,
        "punti": punti,
        "classe": classe,
    }


# ----------------------------------------------------------------------------
# AUTENTICAZIONE
# ----------------------------------------------------------------------------
def check_password():
    expected = get_secret("APP_PASSWORD")
    if not expected:
        st.error("⚠️ Configurazione mancante: imposta APP_PASSWORD nei secrets o nelle variabili d'ambiente.")
        return False

    if st.session_state.get("password_correct"):
        return True

    attempts = st.session_state.get("login_attempts", 0)

    def password_entered():
        given = st.session_state.pop("password_input", "")
        if st.session_state.get("login_attempts", 0) >= MAX_LOGIN_ATTEMPTS:
            return
        if hmac.compare_digest(given.encode("utf-8"), str(expected).encode("utf-8")):
            st.session_state["password_correct"] = True
            st.session_state["login_attempts"] = 0
        else:
            st.session_state["password_correct"] = False
            st.session_state["login_attempts"] = st.session_state.get("login_attempts", 0) + 1

    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        show_logo()
        st.markdown(
            "<h2 style='color:#f8fafc;margin-top:15px;font-size:1.4rem;text-align:center;'>FCR GENERAL CONTRACTOR</h2>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='color:#38bdf8;font-size:0.85rem;font-weight:500;margin-bottom:25px;text-align:center;'>"
            "Aetheris Labs — Area Riservata Protetta</p>",
            unsafe_allow_html=True,
        )
        if attempts >= MAX_LOGIN_ATTEMPTS:
            st.error("Troppi tentativi. Ricarica la pagina piu' tardi.")
        else:
            st.text_input("Password di Accesso:", type="password", on_change=password_entered, key="password_input")
            if st.session_state.get("password_correct") is False:
                st.error("😕 Password errata. Riprova.")
    return False


if not check_password():
    st.stop()


# ----------------------------------------------------------------------------
# AI (google-genai)
# ----------------------------------------------------------------------------
MODEL_NAME = get_secret("GEMINI_MODEL", "gemini-2.5-flash")
SERVER_API_KEY = get_secret("GEMINI_API_KEY", "")


def ai_generate(api_key, contents, json_mode=False, temperature=0.2):
    client = genai.Client(api_key=api_key)
    cfg = types.GenerateContentConfig(
        temperature=temperature,
        response_mime_type="application/json" if json_mode else "text/plain",
    )
    res = client.models.generate_content(model=MODEL_NAME, contents=contents, config=cfg)
    try:
        text = res.text
    except Exception:
        text = None
    if not text:
        raise RuntimeError("Risposta vuota o bloccata dal modello. Riprova.")
    return text


def pulisci_testo_ia(testo):
    """Rimuove markdown residuo."""
    if not testo:
        return ""
    t = testo.replace("```", "").replace("`", "")
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.MULTILINE)
    t = t.replace("**", "").replace("__", "")
    return t.strip()


PROMPT_ESTRAZIONE = (
    "Sei un analista fidi esperto. Dal bilancio fornito estrai i dati contabili dell'ultimo esercizio "
    "e restituisci ESCLUSIVAMENTE un oggetto JSON con queste chiavi: anno_riferimento (intero), "
    "ricavi, ebitda, utile_netto, totale_attivo, patrimonio_netto, debiti_finanziari_totali, pfn, "
    "dscr_stimato (numeri, senza separatori delle migliaia e con il punto come separatore decimale), "
    "valori_in_migliaia (true se gli importi del documento sono espressi in migliaia di euro, altrimenti false). "
    "Riporta gli importi ESATTAMENTE come nel documento, senza convertire le unita'. "
    "Se un dato non e' reperibile usa null."
)


# ----------------------------------------------------------------------------
# PDF
# ----------------------------------------------------------------------------
def pdf_safe(text):
    """Sostituisce i caratteri non latin-1 per i font core di FPDF."""
    if text is None:
        return ""
    rep = {
        "€": "EUR", "–": "-", "—": "-", "’": "'", "‘": "'", "“": '"', "”": '"',
        "…": "...", "•": "-", "≥": ">=", "≤": "<=", "→": "->",
    }
    for k, v in rep.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


class PDFReport(FPDF):
    def header(self):
        self.set_fill_color(15, 23, 42)
        self.rect(0, 0, 210, 26, "F")
        if os.path.exists(LOGO_PATH):
            try:
                self.image(LOGO_PATH, 10, 4, 18)
            except Exception:
                pass
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(255, 255, 255)
        self.set_xy(32, 6)
        self.cell(0, 6, "FCR GENERAL CONTRACTOR - RISK MANAGEMENT REPORT", align="L")
        self.set_font("Helvetica", "", 8)
        self.set_xy(32, 13)
        self.cell(0, 6, "Powered by Aetheris Labs | Lead Eng: Ing. Lorenzo Di Ferdinando", align="L")
        self.set_y(32)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Pagina {self.page_no()} - FCR General Contractor / Aetheris Labs", align="C")


def _row(pdf, cells, widths, aligns, fill=False, h=6):
    """Riga di tabella con celle affiancate."""
    for i, (txt, w, a) in enumerate(zip(cells, widths, aligns)):
        last = i == len(cells) - 1
        pdf.cell(
            w, h, pdf_safe(txt), border=1, align=a, fill=fill,
            new_x=XPos.LMARGIN if last else XPos.RIGHT,
            new_y=YPos.NEXT if last else YPos.TOP,
        )


def _titolo(pdf, txt):
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, pdf_safe(txt), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def genera_pdf_report(base, scen, rating, piano, relazione, dati_demo):
    pdf = PDFReport()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 8, "VALUTAZIONE DEL MERITO DI CREDITO E BUSINESS PLAN", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(
        0, 6, "Analisi indicativa, scoring prospettico e parere per il Comitato Fidi",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.ln(2)

    if dati_demo:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(185, 28, 28)
        pdf.multi_cell(
            0, 5,
            pdf_safe("ATTENZIONE: il report e' basato su dati di esempio non verificati."),
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
        pdf.ln(1)

    # 1. Sintesi
    _titolo(pdf, f"1. Sintesi Indicatori (anno base {int(base['anno_riferimento'])}) - Base vs Scenario")
    w, al = [80, 50, 50], ["L", "R", "R"]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(30, 41, 59)
    pdf.set_text_color(255, 255, 255)
    _row(pdf, ["  Parametro", "Base  ", "Scenario  "], w, al, fill=True, h=7)

    dscr1 = rating["dscr"]
    righe = [
        ("Ricavi delle Vendite", fmt_eur(base["ricavi"]), fmt_eur(scen["ricavi"])),
        ("EBITDA (MOL)", fmt_eur(base["ebitda"]), fmt_eur(scen["ebitda"])),
        ("Patrimonio Netto", fmt_eur(base["patrimonio_netto"]), fmt_eur(scen["pn"])),
        ("Posizione Finanziaria Netta", fmt_eur(base["pfn"]), fmt_eur(scen["pfn"])),
        ("PFN / EBITDA", fmt_x(ratio(base["pfn"], base["ebitda"])), fmt_x(rating["pfn_ebitda"])),
        ("PFN / Patrimonio Netto", fmt_x(ratio(base["pfn"], base["patrimonio_netto"])), fmt_x(rating["pfn_pn"])),
        (
            "Patrimonio Netto / Totale Attivo",
            fmt_num(100 * base["patrimonio_netto"] / base["totale_attivo"], 1) + "%" if base["totale_attivo"] > 0 else "n.d.",
            fmt_num(100 * rating["equity_ratio"], 1) + "%",
        ),
        ("DSCR (Anno 1 del piano)", "-", fmt_x(dscr1) if dscr1 is not None else "n.d."),
        ("Punteggio scoring (max 8)", "-", str(rating["punti"])),
    ]
    pdf.set_font("Helvetica", "", 9)
    fill = False
    for lab, a, b in righe:
        pdf.set_text_color(0, 0, 0)
        pdf.set_fill_color(*((241, 245, 249) if fill else (255, 255, 255)))
        _row(pdf, ["  " + lab, a + "  ", b + "  "], w, al, fill=True)
        fill = not fill
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(
        0, 7, pdf_safe("Giudizio stimato (scenario): " + rating["classe"]),
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.ln(3)

    # 2. Piano
    _titolo(pdf, "2. Proiezioni Economico-Finanziarie Pluriennali (partendo dallo scenario)")
    w2 = [42, 30, 30, 30, 30, 28]
    al2 = ["L", "R", "R", "R", "R", "R"]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(30, 41, 59)
    pdf.set_text_color(255, 255, 255)
    _row(pdf, ["  Anno", "Ricavi", "EBITDA", "FCF", "PFN", "PFN/EBITDA"], w2, al2, fill=True, h=7)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(0, 0, 0)
    for r in piano:
        _row(
            pdf,
            ["  " + r["Anno"], fmt_num(r["Ricavi"]), fmt_num(r["EBITDA"]), fmt_num(r["FCF"]),
             fmt_num(r["PFN"]), fmt_x(r["PFN/EBITDA"])],
            w2, al2,
        )
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, "Importi in EUR. FCF = EBITDA - imposte - capex - interessi - variazione CCN.",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    # 3. Relazione
    _titolo(pdf, "3. Relazione e Parere del Risk Management")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(0, 5, pdf_safe(relazione), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    # Disclaimer
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 4, pdf_safe("Avvertenza: " + DISCLAIMER), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())


# ----------------------------------------------------------------------------
# STATO
# ----------------------------------------------------------------------------
if "financial_data" not in st.session_state:
    st.session_state["financial_data"] = dict(DATI_DEFAULT)
    st.session_state["dati_demo"] = True

dati = st.session_state["financial_data"]

# ----------------------------------------------------------------------------
# INTESTAZIONE E SIDEBAR
# ----------------------------------------------------------------------------
st.title("📊 FCR GENERAL CONTRACTOR — AI Business Plan & Rating")
st.markdown(
    "Piattaforma di Credit Risk Management e Pianificazione Strategica Pluriennale "
    "(scoring indicativo ispirato ai criteri Basilea 3/4)."
)

with st.sidebar:
    if not show_logo((1, 2.5, 1)):
        st.warning("⚠️ Logo non trovato.")
    st.markdown("<h3 style='text-align:center;color:#f8fafc;margin-top:10px;'>AETHERIS LABS</h3>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align:center;color:#94a3b8;font-size:0.85rem;'>Software, AI & Game Development Division</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.markdown("<p style='text-align:center;margin-bottom:2px;'>🛠️ <b>Sviluppato da</b></p>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;color:#38bdf8;margin:0;'>Ing. Lorenzo Di Ferdinando</h4>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:#94a3b8;font-size:0.85rem;'>FCR General Contractor</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    user_api_key = st.text_input("Gemini API Key personale (opzionale)", value="", type="password")
    active_key = user_api_key.strip() or SERVER_API_KEY
    if active_key:
        st.info("Motore AI attivo per estrazione dati e relazione.")
    else:
        st.warning("Nessuna chiave API: inseriscila qui per usare le funzioni AI.")

# ----------------------------------------------------------------------------
# CALCOLO SCENARIO E PIANO (unica fonte di verita' per tab 2, 3 e 4)
# ----------------------------------------------------------------------------
ss = st.session_state
delta_pfn = ss.get("delta_pfn", 0)
delta_pn = ss.get("delta_pn", 0)
delta_ebitda = ss.get("delta_ebitda", 0)
piano_par = {k: ss.get(f"piano_{k}", v) for k, v in PIANO_DEFAULT.items()}

scen = {
    "ricavi": dati["ricavi"],
    "ebitda": dati["ebitda"] + delta_ebitda,
    "pfn": dati["pfn"] + delta_pfn - delta_pn,   # l'aumento di capitale riduce il debito netto
    "pn": dati["patrimonio_netto"] + delta_pn,
    "attivo": dati["totale_attivo"] + delta_pn,
}
piano = proietta(scen["ricavi"], scen["ebitda"], scen["pfn"], piano_par, dati["anno_riferimento"])
dscr_anno1 = piano[0]["DSCR"]
rating = calcola_rating(scen["pfn"], scen["ebitda"], scen["pn"], scen["attivo"], dscr_anno1)
rating_base = calcola_rating(
    dati["pfn"], dati["ebitda"], dati["patrimonio_netto"], dati["totale_attivo"], None
)

# ----------------------------------------------------------------------------
# TABS
# ----------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    ["📂 1. Acquisizione Dati", "⚡ 2. Simulatore What-If", "📈 3. Business Plan Pluriennale", "📑 4. Report PDF"]
)

# --- TAB 1 -------------------------------------------------------------------
with tab1:
    st.subheader("Importazione Bilancio Aziendale (PDF o Excel)")
    if ss.get("dati_demo"):
        st.warning("⚠️ Stai usando **dati di esempio non verificati**. Carica un bilancio o inserisci i dati reali.")

    mode = st.radio("Modalita' di caricamento:", ["Upload File (PDF o Excel)", "Inserimento Dati Manuale"])

    if mode == "Upload File (PDF o Excel)":
        uploaded = st.file_uploader("Trascina qui il bilancio (.pdf, .xlsx, .xls)", type=["pdf", "xlsx", "xls"])
        st.caption(
            "I dati del bilancio vengono inviati al servizio Gemini. Verifica il piano utilizzato e la "
            "conformita' GDPR prima di caricare documenti di clienti."
        )
        if uploaded and st.button("🚀 Estrai Dati Contabili con AI", type="primary"):
            if not active_key:
                st.error("Inserisci la chiave API Gemini nella sidebar.")
            elif uploaded.size > MAX_UPLOAD_MB * 1024 * 1024:
                st.error(f"File troppo grande (max {MAX_UPLOAD_MB} MB).")
            else:
                name = uploaded.name.lower()
                with st.spinner("Elaborazione dati contabili in corso..."):
                    try:
                        if name.endswith(".pdf"):
                            contents = [
                                PROMPT_ESTRAZIONE,
                                types.Part.from_bytes(data=uploaded.getvalue(), mime_type="application/pdf"),
                            ]
                        else:
                            engine = "xlrd" if name.endswith(".xls") else "openpyxl"
                            xls = pd.ExcelFile(uploaded, engine=engine)
                            testo = ""
                            for sheet in xls.sheet_names[:MAX_EXCEL_SHEETS]:
                                df = pd.read_excel(xls, sheet_name=sheet, header=None).head(MAX_EXCEL_ROWS)
                                testo += f"\n--- Foglio: {sheet} ---\n" + df.to_string(index=False, header=False)
                            contents = [PROMPT_ESTRAZIONE, testo]

                        raw_txt = ai_generate(active_key, contents, json_mode=True, temperature=0.0)
                        nuovi = normalizza_dati(json.loads(raw_txt))
                        ss["financial_data"] = nuovi
                        ss["dati_demo"] = False
                        ss.pop("report", None)
                        st.success("Dati estratti con successo. Verificali prima di procedere.")
                        st.rerun()
                    except json.JSONDecodeError:
                        st.error("Il modello non ha restituito un JSON valido. Riprova.")
                    except Exception as e:
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
            k = 1000.0 if in_migliaia else 1.0
            ss["financial_data"] = {
                **dati,
                "anno_riferimento": int(anno_in),
                "ricavi": ricavi_in * k,
                "ebitda": ebitda_in * k,
                "utile_netto": utile_in * k,
                "totale_attivo": attivo_in * k,
                "patrimonio_netto": pn_in * k,
                "debiti_finanziari_totali": deb_in * k,
                "pfn": pfn_in * k,
            }
            ss["dati_demo"] = False
            ss.pop("report", None)
            st.success("Dati aggiornati con successo.")
            st.rerun()

    for avviso in valida_dati(dati):
        st.warning(f"⚠️ {avviso}")

    st.markdown("### 📊 Stato Attuale del Dataset")
    st.json(dati)

# --- TAB 2 -------------------------------------------------------------------
with tab2:
    st.subheader("🎯 Simulatore di Scoring e Ottimizzazione")
    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("#### ⚙️ Leve Strategiche")
        st.slider("Variazione Debito Netto - PFN (€)", -500000, 500000, 0, 25000, key="delta_pfn")
        st.slider("Iniezione Capitale / Mezzi Propri (€)", 0, 500000, 0, 25000, key="delta_pn")
        st.slider("Variazione EBITDA (€)", -100000, 300000, 0, 10000, key="delta_ebitda")
        st.caption(
            "L'aumento di capitale entra come liquidita': aumenta il patrimonio netto e riduce la PFN. "
            "Una PFN negativa indica cassa netta."
        )

    with col2:
        st.markdown("#### 📈 Output Modulo di Scoring")
        m1, m2, m3, m4 = st.columns(4)
        d1 = rating["pfn_ebitda"] - rating_base["pfn_ebitda"]
        d2 = rating["pfn_pn"] - rating_base["pfn_pn"]
        m1.metric(
            "PFN / EBITDA", fmt_x(rating["pfn_ebitda"]),
            delta=None if math.isinf(d1) or math.isnan(d1) else f"{d1:+.2f}x vs base",
            delta_color="inverse",
        )
        m2.metric(
            "PFN / Patrimonio Netto", fmt_x(rating["pfn_pn"]),
            delta=None if math.isinf(d2) or math.isnan(d2) else f"{d2:+.2f}x vs base",
            delta_color="inverse",
        )
        m3.metric("DSCR (Anno 1)", fmt_x(rating["dscr"]) if rating["dscr"] is not None else "n.d.")
        m4.metric("Fascia", rating["classe"].split(" - ")[0].replace("FASCIA ", ""))
        st.info(f"**Posizionamento:** {rating['classe']}  \nPunteggio: {rating['punti']}/8")
        st.caption(
            "Soglie (verde/giallo): PFN/EBITDA < 2,5x / 4,5x · PFN/PN < 1,0x / 2,0x · "
            "PN/Attivo ≥ 25% / 15% · DSCR ≥ 1,30 / 1,00. Modello interno indicativo."
        )
        st.caption(
            f"Scenario: EBITDA {fmt_eur(scen['ebitda'])} · PFN {fmt_eur(scen['pfn'])} · "
            f"PN {fmt_eur(scen['pn'])}"
        )

# --- TAB 3 -------------------------------------------------------------------
with tab3:
    st.subheader("📈 Proiezioni Pluriennali (3 Anni)")
    st.caption("Il piano parte dai valori dello scenario impostato nel simulatore.")
    cp1, cp2, cp3 = st.columns(3)
    with cp1:
        st.slider("Crescita Annua Ricavi (%)", -10.0, 30.0, PIANO_DEFAULT["g_ricavi"], 0.5, key="piano_g_ricavi")
        st.slider("Crescita Annua EBITDA (%)", -10.0, 30.0, PIANO_DEFAULT["g_ebitda"], 0.5, key="piano_g_ebitda")
        st.slider("CCN su variazione ricavi (%)", 0.0, 60.0, PIANO_DEFAULT["ccn_pct"], 1.0, key="piano_ccn_pct")
    with cp2:
        st.number_input("Capex annuo (€)", 0.0, 5_000_000.0, PIANO_DEFAULT["capex"], 10000.0, key="piano_capex")
        st.number_input("Ammortamenti annui (€)", 0.0, 5_000_000.0, PIANO_DEFAULT["amm"], 10000.0, key="piano_amm")
        st.number_input("Rimborso annuo quota capitale (€)", 0.0, 5_000_000.0, PIANO_DEFAULT["rimborso"], 10000.0,
                        key="piano_rimborso")
    with cp3:
        st.number_input("Tasso d'interesse sulla PFN (%)", 0.0, 20.0, PIANO_DEFAULT["tasso"], 0.25, key="piano_tasso")
        st.number_input("Aliquota fiscale (%)", 0.0, 60.0, PIANO_DEFAULT["aliquota"], 0.5, key="piano_aliquota")

    df_piano = pd.DataFrame(
        [
            {
                "Anno": r["Anno"],
                "Ricavi": fmt_eur(r["Ricavi"]),
                "EBITDA": fmt_eur(r["EBITDA"]),
                "Free Cash Flow": fmt_eur(r["FCF"]),
                "PFN": fmt_eur(r["PFN"]),
                "PFN/EBITDA": fmt_x(r["PFN/EBITDA"]),
                "DSCR": fmt_x(r["DSCR"]) if r["DSCR"] is not None else "n.d.",
            }
            for r in piano
        ]
    )
    show_df(df_piano)
    st.caption(
        "FCR = EBITDA − imposte − capex − interessi − variazione CCN; PFN(t) = PFN(t−1) − FCF. "
        "Il rimborso del debito usa cassa e non modifica la PFN, ma incide sul DSCR "
        "= (EBITDA − imposte − ΔCCN) / (interessi + rimborso)."
    )

# --- TAB 4 -------------------------------------------------------------------
with tab4:
    st.subheader("📑 Generazione Report per il Comitato di Credito")
    if ss.get("dati_demo"):
        st.warning("⚠️ I dati sono di esempio non verificati: il report lo riportera' esplicitamente.")

    if st.button("🚀 Genera Report PDF", type="primary"):
        if not active_key:
            st.error("Inserisci la chiave API Gemini nella sidebar.")
        else:
            with st.spinner("Creazione del report in corso..."):
                try:
                    tabella_piano = "\n".join(
                        f"- {r['Anno']}: ricavi {fmt_num(r['Ricavi'])} EUR, EBITDA {fmt_num(r['EBITDA'])} EUR, "
                        f"FCF {fmt_num(r['FCF'])} EUR, PFN {fmt_num(r['PFN'])} EUR, "
                        f"PFN/EBITDA {fmt_x(r['PFN/EBITDA'])}, "
                        f"DSCR {fmt_x(r['DSCR']) if r['DSCR'] is not None else 'n.d.'}"
                        for r in piano
                    )
                    prompt = (
                        "Agisci come Risk Manager e redigi una relazione formale per il Comitato di Credito.\n"
                        f"DATI ANNO BASE ({int(dati['anno_riferimento'])}): ricavi {fmt_num(dati['ricavi'])} EUR, "
                        f"EBITDA {fmt_num(dati['ebitda'])} EUR, utile netto {fmt_num(dati['utile_netto'])} EUR, "
                        f"totale attivo {fmt_num(dati['totale_attivo'])} EUR, patrimonio netto "
                        f"{fmt_num(dati['patrimonio_netto'])} EUR, debiti finanziari "
                        f"{fmt_num(dati['debiti_finanziari_totali'])} EUR, PFN {fmt_num(dati['pfn'])} EUR.\n"
                        f"SCENARIO SIMULATO: EBITDA {fmt_num(scen['ebitda'])} EUR, PFN {fmt_num(scen['pfn'])} EUR, "
                        f"PN {fmt_num(scen['pn'])} EUR, PFN/EBITDA {fmt_x(rating['pfn_ebitda'])}, "
                        f"PFN/PN {fmt_x(rating['pfn_pn'])}, PN/Attivo {fmt_num(100 * rating['equity_ratio'], 1)}%, "
                        f"giudizio del modello interno: {rating['classe']}.\n"
                        f"PIANO TRIENNALE (crescita ricavi {piano_par['g_ricavi']}%, EBITDA {piano_par['g_ebitda']}%, "
                        f"capex {fmt_num(piano_par['capex'])} EUR, tasso {piano_par['tasso']}%):\n{tabella_piano}\n\n"
                        "Struttura: 1. Solvibilita' e struttura finanziaria. 2. Punti di forza e criticita'. "
                        "3. Sostenibilita' del piano pluriennale (usa i numeri forniti). 4. Raccomandazioni. "
                        "Usa SOLO i dati forniti, non inventare cifre. Precisa che e' una valutazione indicativa "
                        "e non un rating regolamentare. Scrivi in italiano, in testo semplice senza markdown."
                    )
                    relazione = pulisci_testo_ia(ai_generate(active_key, prompt, temperature=0.3))
                    pdf_bytes = genera_pdf_report(dati, scen, rating, piano, relazione, ss.get("dati_demo", False))
                    ss["report"] = {"text": relazione, "pdf": pdf_bytes}
                except Exception as e:
                    st.error(f"Errore nella generazione del report: {e}")

    # Fuori dall'if del bottone: sopravvive al rerun causato dal download
    if ss.get("report"):
        st.markdown("### 📄 Sintesi della Relazione")
        st.text(ss["report"]["text"])
        st.download_button(
            label="📥 Scarica Report PDF",
            data=ss["report"]["pdf"],
            file_name="Report_Rating_FCR_General_Contractor.pdf",
            mime="application/pdf",
        )
        st.caption(DISCLAIMER)
