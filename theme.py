"""
theme.py - Tema grafico premium (CSS con animazioni) e piccoli componenti HTML per l'interfaccia.

Le animazioni rispettano 'prefers-reduced-motion' (vengono disattivate se l'utente lo richiede).
Gli HTML sono generati su una sola riga: gli spazi iniziali farebbero interpretare il testo come codice dal markdown.
"""
import base64
import functools
import html
import io
import os

_CSS_RAW = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

@property --n { syntax: '<integer>'; initial-value: 0; inherits: false; }

:root {
  --bg: #f8fafc; --panel: #ffffff; --panel2: #f1f5f9;
  --line: #e2e8f0; --line2: #cbd5e1;
  --navy: #0f172a; --ink: #334155; --mut: #64748b;
  --acc: #1e40af; --acc2: #2563eb; --accsoft: #eff6ff;
  --ok: #16a34a; --warn: #d97706; --bad: #dc2626;
  --shadow: 0 1px 2px rgba(15,23,42,.05), 0 4px 14px rgba(15,23,42,.06);
  --shadow-h: 0 2px 4px rgba(15,23,42,.06), 0 14px 34px rgba(30,64,175,.16);
}

@keyframes fadeUp   { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: none; } }
@keyframes popIn    { 0% { opacity: 0; transform: scale(.6); } 70% { transform: scale(1.06); } 100% { opacity: 1; transform: scale(1); } }
@keyframes shimmer  { 0% { background-position: 0% 50%; } 100% { background-position: 220% 50%; } }
@keyframes float    { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }
@keyframes pulse    { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: .5; transform: scale(.7); } }
@keyframes count    { from { --n: 0; } }
@keyframes glowOk   { 0%, 100% { box-shadow: 0 0 0 0 rgba(22,163,74,0); } 50% { box-shadow: 0 0 0 6px rgba(22,163,74,.16); } }
@keyframes glowWarn { 0%, 100% { box-shadow: 0 0 0 0 rgba(217,119,6,0); } 50% { box-shadow: 0 0 0 6px rgba(217,119,6,.16); } }
@keyframes glowBad  { 0%, 100% { box-shadow: 0 0 0 0 rgba(220,38,38,0); } 50% { box-shadow: 0 0 0 6px rgba(220,38,38,.16); } }
@keyframes sweep    { from { left: -120%; } to { left: 140%; } }

html, body, .stApp, [data-testid="stSidebar"], button, input, textarea, select { font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; }
.stApp { background: radial-gradient(900px 420px at 100% -10%, rgba(37,99,235,.07), transparent 60%), var(--bg); color: var(--ink); }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.6rem; max-width: 1400px; animation: fadeUp .5s cubic-bezier(.2,.7,.2,1) both; }
h1, h2, h3, h4, h5 { color: var(--navy) !important; font-weight: 700; letter-spacing: -.01em; }
p, li, label, [data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"] { color: var(--ink); }
[data-testid="stCaptionContainer"], .stCaption, small { color: var(--mut) !important; }
a { color: var(--acc2); }
h3 { margin-top: .6rem; }

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid var(--line); box-shadow: 2px 0 18px rgba(15,23,42,.04); }
[data-testid="stSidebar"] > div:first-child { padding-top: .6rem; }
.brand { text-align: center; padding: 4px 6px 2px 6px; animation: fadeUp .6s ease both; }
.brand img { display: block; width: 78%; max-width: 230px; height: auto; margin: 0 auto 8px auto; mix-blend-mode: multiply; }
.brand .b-name { font-size: 1.05rem; font-weight: 800; letter-spacing: .14em; color: var(--navy); }
.brand .b-sub { font-size: .74rem; color: var(--mut); margin-top: 2px; line-height: 1.35; }
.brand .b-dev { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--line); font-size: .7rem; color: var(--mut); letter-spacing: .06em; text-transform: uppercase; }
.brand .b-who { font-size: .98rem; font-weight: 700; color: var(--acc); margin-top: 2px; }
.b-who2 { margin-top: 2px; }
.brand .b-co { font-size: .78rem; color: var(--mut); }

/* ---------- hero ---------- */
.hero { display: flex; align-items: center; gap: 22px; margin: 2px 0 6px 0; animation: fadeUp .6s ease both; }
.hero-logo { width: 92px; height: auto; flex: none; filter: drop-shadow(0 6px 14px rgba(30,64,175,.22)); animation: float 6s ease-in-out infinite; }
.hero-title { font-size: 2rem; font-weight: 800; letter-spacing: -.02em; line-height: 1.12; margin: 0; color: var(--navy);
  background: linear-gradient(90deg, #0f172a 0%, #1e40af 40%, #0f172a 80%); background-size: 220% auto;
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; animation: shimmer 10s linear infinite; }
.hero-sub { color: var(--mut); font-size: .95rem; margin-top: 6px; max-width: 880px; }
.tricolor { height: 3px; width: 132px; border-radius: 3px; margin-top: 10px;
  background: linear-gradient(90deg, #009246 0 33.3%, #e2e8f0 33.3% 66.6%, #ce2b37 66.6% 100%); }
.login-wrap { text-align: center; animation: fadeUp .7s ease both; }
.login-logo { display: block; margin: 0 auto 10px auto; width: 64%; max-width: 280px; height: auto; mix-blend-mode: multiply; }
.login-fcr { display: block; margin: 0 auto 6px auto; width: 120px; height: auto; filter: drop-shadow(0 8px 18px rgba(30,64,175,.25)); animation: float 6s ease-in-out infinite; }
.login-title { font-size: 1.35rem; font-weight: 800; color: var(--navy); letter-spacing: .02em; }
.login-sub { font-size: .85rem; color: var(--acc); font-weight: 600; margin: 4px 0 18px 0; }

/* ---------- hub ---------- */
.hub-title { text-align: center; font-size: 2.1rem; font-weight: 800; color: var(--navy); margin: 6px 0 4px 0; letter-spacing: -.02em; }
.hub-sub { text-align: center; color: var(--mut); font-size: 1.02rem; margin-bottom: 26px; }
.hub-logo { display: block; margin: 0 auto 10px auto; width: 96px; filter: drop-shadow(0 8px 18px rgba(30,64,175,.25)); animation: float 6s ease-in-out infinite; }
.hub-card { margin-bottom: 20px; position: relative; background: var(--panel); border: 1px solid var(--line); border-radius: 18px; padding: 26px 26px 20px 26px; min-height: 400px;
  box-shadow: var(--shadow); overflow: hidden; animation: fadeUp .6s ease both; transition: transform .28s ease, box-shadow .28s ease, border-color .28s ease; }
.hub-card::before { content: ""; position: absolute; left: 0; top: 0; right: 0; height: 4px; background: linear-gradient(90deg, var(--acc), #38bdf8); }
.hub-card.bp::before { background: linear-gradient(90deg, #0f766e, #14b8a6); }
.hub-card:hover { transform: translateY(-4px); box-shadow: var(--shadow-h); border-color: #bfdbfe; }
.hub-card.bp:hover { border-color: #99f6e4; box-shadow: 0 2px 4px rgba(15,23,42,.06), 0 14px 34px rgba(15,118,110,.16); }
.hub-badge { width: 46px; height: 46px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.45rem; background: var(--accsoft); margin-bottom: 14px; }
.hub-card.bp .hub-badge { background: #f0fdfa; }
.hub-num { font-size: .7rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--acc2); }
.hub-card.bp .hub-num { color: #0f766e; }
.hub-card h2 { font-size: 1.32rem; margin: 2px 0 8px 0; color: var(--navy) !important; }
.hub-card p { color: var(--ink); font-size: .93rem; line-height: 1.55; margin: 0 0 12px 0; }
.hub-card ul { list-style: none; padding: 0; margin: 0 0 10px 0; }
.hub-card li { position: relative; padding: 4px 0 4px 26px; font-size: .9rem; color: var(--ink); }
.hub-card li::before { content: "✓"; position: absolute; left: 0; top: 4px; width: 18px; height: 18px; border-radius: 50%; background: #dbeafe; color: var(--acc);
  font-size: .72rem; font-weight: 800; display: flex; align-items: center; justify-content: center; }
.hub-card.bp li::before { background: #ccfbf1; color: #0f766e; }
.hub-card.cf::before { background: linear-gradient(90deg, #c2410c, #fb923c); }
.hub-card.cf:hover { border-color: #fed7aa; box-shadow: 0 2px 4px rgba(15,23,42,.06), 0 14px 34px rgba(194,65,12,.16); }
.hub-card.cf .hub-badge { background: #fff7ed; }
.hub-card.cf .hub-num { color: #c2410c; }
.hub-card.cf li::before { background: #ffedd5; color: #c2410c; }
.hub-card.pv::before { background: linear-gradient(90deg, #6d28d9, #a78bfa); }
.hub-card.pv:hover { border-color: #ddd6fe; box-shadow: 0 2px 4px rgba(15,23,42,.06), 0 14px 34px rgba(109,40,217,.16); }
.hub-card.pv .hub-badge { background: #f5f3ff; }
.hub-card.pv .hub-num { color: #6d28d9; }
.hub-card.pv li::before { background: #ede9fe; color: #6d28d9; }
.hub-tags { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
.hub-tag { font-size: .68rem; font-weight: 600; padding: 3px 9px; border-radius: 999px; background: var(--panel2); color: var(--mut); border: 1px solid var(--line); }

/* ---------- strip di stato ---------- */
.strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 16px 0 8px 0; }
.chip { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 12px 16px; box-shadow: var(--shadow);
  animation: fadeUp .5s ease both; transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease; }
.chip:hover { transform: translateY(-3px); border-color: #bfdbfe; box-shadow: var(--shadow-h); }
.chip .lbl { font-size: .68rem; text-transform: uppercase; letter-spacing: .09em; color: var(--mut); }
.chip .val { font-size: 1.5rem; font-weight: 700; color: var(--navy); margin-top: 2px; }
.chip .sub { font-size: .72rem; color: var(--mut); margin-top: 1px; }
.chip.ok { border-left: 3px solid var(--ok); } .chip.warn { border-left: 3px solid var(--warn); }
.chip.bad { border-left: 3px solid var(--bad); } .chip.info { border-left: 3px solid var(--acc2); }

/* ---------- badge e punteggio ---------- */
.fascia { display: inline-flex; align-items: center; gap: 10px; padding: 8px 18px; border-radius: 999px; font-weight: 700; letter-spacing: .05em; color: #fff; }
.fascia .dot { width: 10px; height: 10px; border-radius: 50%; background: #fff; animation: pulse 1.8s ease-in-out infinite; }
.fascia.ok   { background: linear-gradient(135deg, #15803d, #22c55e); animation: popIn .5s ease both, glowOk 2.6s ease-in-out .6s infinite; }
.fascia.warn { background: linear-gradient(135deg, #b45309, #f59e0b); animation: popIn .5s ease both, glowWarn 2.6s ease-in-out .6s infinite; }
.fascia.bad  { background: linear-gradient(135deg, #b91c1c, #ef4444); animation: popIn .5s ease both, glowBad 2.2s ease-in-out .6s infinite; }
.scorecard { display: flex; align-items: center; gap: 28px; flex-wrap: wrap; background: var(--panel); border: 1px solid var(--line);
  border-radius: 18px; padding: 18px 24px; margin: 10px 0 6px 0; box-shadow: var(--shadow); animation: fadeUp .5s ease both; }
.score-num { font-size: 3.4rem; font-weight: 800; line-height: 1; color: var(--navy); animation: count 1.4s ease-out both; counter-reset: n var(--n); }
.score-num::after { content: counter(n); }
.score-max { font-size: 1.25rem; color: var(--mut); margin-left: 4px; font-weight: 600; }
.score-lbl { font-size: .7rem; text-transform: uppercase; letter-spacing: .1em; color: var(--mut); margin-bottom: 4px; }
.meter { display: flex; gap: 6px; margin-top: 12px; }
.meter i { width: 28px; height: 10px; border-radius: 4px; background: #e2e8f0; animation: popIn .45s ease both; animation-delay: calc(var(--i) * 80ms); }
.meter i.on.ok { background: linear-gradient(90deg, #16a34a, #4ade80); } .meter i.on.warn { background: linear-gradient(90deg, #d97706, #fbbf24); }
.meter i.on.bad { background: linear-gradient(90deg, #dc2626, #f87171); }
.score-desc { color: var(--mut); font-size: .88rem; margin-top: 8px; max-width: 520px; }

/* ---------- componenti Streamlit ---------- */
[data-testid="stMetric"] { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 14px 16px; box-shadow: var(--shadow);
  animation: fadeUp .5s ease both; transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease; }
[data-testid="stMetric"]:hover { transform: translateY(-3px); border-color: #bfdbfe; box-shadow: var(--shadow-h); }
[data-testid="stMetricValue"] { font-size: 1.7rem; font-weight: 700; color: var(--acc) !important; }
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * { color: var(--mut) !important; }

.stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid var(--line); padding-bottom: 0; }
.stTabs button[data-baseweb="tab"] { background: var(--panel) !important; border: 1px solid var(--line) !important; border-bottom: none !important;
  border-radius: 10px 10px 0 0 !important; color: var(--ink) !important; padding: 10px 20px !important; height: auto !important; font-weight: 600;
  transition: background .2s ease, color .2s ease, transform .2s ease; }
.stTabs button[data-baseweb="tab"] p { color: inherit !important; font-weight: 600; }
.stTabs button[data-baseweb="tab"]:hover { background: var(--accsoft) !important; color: var(--acc) !important; transform: translateY(-2px); }
.stTabs button[data-baseweb="tab"][aria-selected="true"] { background: var(--acc) !important; color: #fff !important; border-color: var(--acc) !important;
  box-shadow: 0 6px 16px rgba(30,64,175,.28); }
.stTabs button[data-baseweb="tab"][aria-selected="true"] p { color: #fff !important; }
.stTabs [data-baseweb="tab-highlight"] { background-color: var(--acc2) !important; height: 3px; border-radius: 3px; }

.stButton > button, .stDownloadButton > button, [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"] {
  position: relative; overflow: hidden; background: var(--acc); color: #fff !important; border-radius: 10px; padding: .6rem 1.2rem; font-weight: 600; border: none;
  box-shadow: 0 2px 8px rgba(30,64,175,.28); transition: transform .22s ease, box-shadow .22s ease, background .22s ease; }
.stButton > button p, .stDownloadButton > button p { color: #fff !important; }
.stButton > button::after, .stDownloadButton > button::after { content: ""; position: absolute; top: 0; left: -120%; width: 55%; height: 100%;
  background: linear-gradient(120deg, transparent, rgba(255,255,255,.35), transparent); transform: skewX(-20deg); }
.stButton > button:hover, .stDownloadButton > button:hover { background: #1d4ed8; transform: translateY(-2px); box-shadow: 0 8px 22px rgba(30,64,175,.38); color: #fff !important; }
.stButton > button:hover::after, .stDownloadButton > button:hover::after { animation: sweep .8s ease; }
.stButton > button:active, .stDownloadButton > button:active { transform: translateY(0) scale(.98); }
.stButton > button:disabled { background: #cbd5e1; box-shadow: none; color: #fff !important; }
/* pulsanti di invio dei form (login, nuovo utente, cambio password) */
[data-testid="stFormSubmitButton"] > button, [data-testid="stBaseButton-primaryFormSubmit"], [data-testid="stBaseButton-secondaryFormSubmit"] {
  background: var(--acc) !important; color: #fff !important; border: none !important; border-radius: 10px; font-weight: 600; box-shadow: 0 2px 8px rgba(30,64,175,.28); }
[data-testid="stFormSubmitButton"] > button p, [data-testid="stFormSubmitButton"] > button span { color: #fff !important; }
[data-testid="stFormSubmitButton"] > button:hover { background: #1d4ed8 !important; transform: translateY(-2px); }
/* pulsanti secondari (es. Annulla, Torna all'Hub) */
[data-testid="stSidebar"] .stButton > button { background: #ffffff; color: var(--acc) !important; border: 1px solid #bfdbfe; box-shadow: none; }
[data-testid="stSidebar"] .stButton > button p { color: var(--acc) !important; }
[data-testid="stSidebar"] .stButton > button:hover { background: var(--accsoft); box-shadow: 0 4px 12px rgba(30,64,175,.15); color: var(--acc) !important; }

/* campi di input: sfondo chiaro, bordo definito, testo scuro */
.stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input,
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"] { background-color: #ffffff !important; color: var(--navy) !important; }
.stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input { border: 1px solid var(--line2) !important; border-radius: 8px !important; transition: border-color .2s ease, box-shadow .2s ease; }
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"] { border-radius: 8px !important; }
.stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus { border-color: var(--acc2) !important; box-shadow: 0 0 0 3px rgba(37,99,235,.18) !important; }
.stNumberInput button { background: #f1f5f9 !important; color: var(--ink) !important; border: 1px solid var(--line) !important; box-shadow: none !important; }
.stNumberInput button:hover { background: var(--accsoft) !important; }
[data-baseweb="select"] > div { background-color: #ffffff !important; color: var(--navy) !important; border: 1px solid var(--line2) !important; border-radius: 8px !important; }
[data-baseweb="select"] * { color: var(--navy) !important; }
[data-baseweb="popover"] [data-baseweb="menu"], [data-baseweb="popover"] ul { background: #ffffff !important; border: 1px solid var(--line); box-shadow: var(--shadow-h); }
[data-baseweb="popover"] li { color: var(--navy) !important; background: #ffffff; }
[data-baseweb="popover"] li:hover, [data-baseweb="popover"] li[aria-selected="true"] { background: var(--accsoft) !important; }
.stRadio label, .stCheckbox label { color: var(--ink) !important; }
::placeholder { color: #94a3b8 !important; opacity: 1; }

[data-testid="stAlert"] { border-radius: 12px; animation: fadeUp .4s ease both; }
[data-testid="stDataFrame"], [data-testid="stDataEditor"] { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: #fff; box-shadow: var(--shadow); animation: fadeUp .45s ease both; }
[data-testid="stExpander"] { border: 1px solid var(--line) !important; border-radius: 12px; background: var(--panel); }
[data-testid="stExpander"] summary p { color: var(--navy) !important; font-weight: 600; }
[data-testid="stImage"] img { border-radius: 12px; }
[data-testid="stPyplot"], .stPyplot { background: #fff; border: 1px solid var(--line); border-radius: 14px; padding: 8px; box-shadow: var(--shadow); animation: fadeUp .5s ease both; }
[data-testid="stFileUploaderDropzone"] { background: #ffffff; border: 1.5px dashed #93c5fd; border-radius: 14px; transition: border-color .25s ease, background .25s ease; }
[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--acc2); background: var(--accsoft); }
[data-testid="stFileUploaderDropzone"] * { color: var(--ink) !important; }
[data-testid="stFileUploaderDropzone"] button { background: #fff !important; color: var(--acc) !important; border: 1px solid #bfdbfe !important; box-shadow: none !important; }
[data-testid="stToast"] { border-radius: 12px; border: 1px solid var(--line); box-shadow: var(--shadow-h); }
[data-testid="stCode"], pre { border-radius: 10px; }
hr { border-color: var(--line); }

::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 8px; } ::-webkit-scrollbar-thumb:hover { background: #94a3b8; }

@media (max-width: 700px) {
  .hero { gap: 12px; } .hero-logo { width: 62px; } .hero-title { font-size: 1.35rem; }
  .hub-title { font-size: 1.5rem; } .score-num { font-size: 2.8rem; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
"""

CSS = "<style>" + _CSS_RAW + "</style>"


@functools.lru_cache(maxsize=8)
def logo_uri(path, larghezza=260, senza_sfondo=False):
    """Logo ridimensionato e codificato in data-URI (leggero da reinviare ad ogni rerun).
    senza_sfondo=True rende trasparente lo sfondo chiaro di un logo scuro (niente riquadro bianco/grigio attorno);
    altrimenti i JPG restano JPG (piu' leggeri) e i PNG restano PNG (trasparenza conservata)."""
    if not path or not os.path.exists(path):
        return ""
    try:
        from PIL import Image
        jpg = path.lower().endswith((".jpg", ".jpeg")) and not senza_sfondo
        with Image.open(path) as im:
            im = im.convert("RGB" if jpg else "RGBA")
            if im.width > larghezza:
                im = im.resize((larghezza, round(im.height * larghezza / im.width)), Image.LANCZOS)
            if senza_sfondo:
                im = _togli_sfondo_chiaro(im)
            buf = io.BytesIO()
            if jpg:
                im.save(buf, format="JPEG", quality=90, optimize=True)
            else:
                im.save(buf, format="PNG", optimize=True)
        mime = "image/jpeg" if jpg else "image/png"
        return f"data:{mime};base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return ""


def _togli_sfondo_chiaro(im):
    """Trasforma il bianco/grigio chiarissimo in trasparenza mantenendo i colori scuri del logo."""
    import numpy as np
    from PIL import Image
    a = np.asarray(im.convert("RGB"), dtype=np.float32)
    alpha = 255.0 - a.min(axis=2)                       # piu' e' scuro il pixel, piu' e' opaco
    alpha = np.clip((alpha - 14.0) * (255.0 / (255.0 - 14.0)), 0, 255)   # soglia anti-rumore JPEG
    sicuro = np.maximum(alpha, 1.0)[..., None] / 255.0
    rgb = np.clip(255.0 + (a - 255.0) / sicuro, 0, 255)  # colore originale "tolto" dal bianco
    rgb = np.where(alpha[..., None] < 1.0, 0.0, rgb)
    out = np.dstack([rgb, alpha]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def tono(classe):
    c = (classe or "").upper()
    return "ok" if "VERDE" in c else ("warn" if "GIALLA" in c else "bad")


def _e(t):
    return html.escape(str(t), quote=True)


def hero(uri, titolo, sottotitolo):
    logo = f'<img class="hero-logo" src="{uri}" alt="FCR"/>' if uri else ""
    return (f'<div class="hero">{logo}<div><h1 class="hero-title">{_e(titolo)}</h1>'
            f'<div class="hero-sub">{_e(sottotitolo)}</div><div class="tricolor"></div></div></div>')


def login_header(uri_fcr, uri_aeth):
    """Intestazione della schermata di login: logo FCR, logo Aetheris grande e titoli."""
    fcr = f'<img class="login-fcr" src="{uri_fcr}" alt="FCR"/>' if uri_fcr else ""
    aeth = f'<img class="login-logo" src="{uri_aeth}" alt="Aetheris Labs"/>' if uri_aeth else ""
    return (f'<div class="login-wrap">{fcr}{aeth}<div class="login-title">FCR GENERAL CONTRACTOR</div>'
            f'<div class="login-sub">Aetheris Labs - Area Riservata Protetta</div></div>')


def sidebar_brand(uri_aeth):
    logo = f'<img src="{uri_aeth}" alt="Aetheris Labs"/>' if uri_aeth else ""
    return (f'<div class="brand">{logo}<div class="b-name">AETHERIS LABS</div>'
            f'<div class="b-sub">Software, AI &amp; Game Development Division</div>'
            f'<div class="b-dev">Sviluppato da</div><div class="b-who">Ing. Lorenzo Di Ferdinando</div>'
            f'<div class="b-who b-who2">Dott. Claudio Arosio</div>'
            f'<div class="b-co">FCR General Contractor</div></div>')


def hub_header(uri_fcr):
    logo = f'<img class="hub-logo" src="{uri_fcr}" alt="FCR"/>' if uri_fcr else ""
    return (f'{logo}<div class="hub-title">FCR General Contractor &amp; Aetheris Labs</div>'
            f'<div class="hub-sub">Seleziona lo strumento operativo che desideri utilizzare</div>')


def hub_card(numero, icona, titolo, descrizione, voci, tags, variante=""):
    li = "".join(f"<li>{_e(v)}</li>" for v in voci)
    tg = "".join(f'<span class="hub-tag">{_e(t)}</span>' for t in tags)
    return (f'<div class="hub-card {variante}"><div class="hub-badge">{icona}</div><div class="hub-num">{_e(numero)}</div>'
            f'<h2>{_e(titolo)}</h2><p>{_e(descrizione)}</p><ul>{li}</ul><div class="hub-tags">{tg}</div></div>')


def stat_strip(voci):
    """voci: lista di dict {label, value, sub, tono} con tono in ok|warn|bad|info."""
    chip = "".join(
        f'<div class="chip {_e(v.get("tono", "info"))}"><div class="lbl">{_e(v["label"])}</div>'
        f'<div class="val">{_e(v["value"])}</div><div class="sub">{_e(v.get("sub", ""))}</div></div>'
        for v in voci
    )
    return f'<div class="strip">{chip}</div>'


def fascia_badge(classe):
    nome = classe.split(" - ")[0].replace("FASCIA ", "")
    return f'<span class="fascia {tono(classe)}"><span class="dot"></span>FASCIA {_e(nome)}</span>'


def scorecard(punti, classe, massimo=8):
    t = tono(classe)
    desc = classe.split(" - ")[1] if " - " in classe else ""
    blocchi = "".join(
        f'<i class="{"on " + t if i < punti else ""}" style="--i:{i}"></i>' for i in range(massimo)
    )
    return (
        f'<div class="scorecard"><div><div class="score-lbl">Punteggio di scoring</div>'
        f'<div><span class="score-num" style="--n:{int(punti)}"></span><span class="score-max">/ {massimo}</span></div>'
        f'<div class="meter">{blocchi}</div></div>'
        f'<div>{fascia_badge(classe)}<div class="score-desc">{_e(desc)}. Valutazione indicativa del modello interno, '
        f'non un rating regolamentare.</div></div></div>'
    )
