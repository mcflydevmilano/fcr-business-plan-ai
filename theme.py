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
  --bg: #070b14; --panel: rgba(17, 24, 39, .72); --panel2: rgba(30, 41, 59, .55);
  --line: rgba(148, 163, 184, .16); --acc: #38bdf8; --acc2: #2563eb;
  --ok: #22c55e; --warn: #f59e0b; --bad: #ef4444; --txt: #e2e8f0; --mut: #94a3b8;
}

@keyframes fadeUp   { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }
@keyframes popIn    { 0% { opacity: 0; transform: scale(.6); } 70% { transform: scale(1.08); } 100% { opacity: 1; transform: scale(1); } }
@keyframes shimmer  { 0% { background-position: 0% 50%; } 100% { background-position: 220% 50%; } }
@keyframes float    { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-5px); } }
@keyframes pulse    { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: .45; transform: scale(.7); } }
@keyframes count    { from { --n: 0; } }
@keyframes glowOk   { 0%, 100% { box-shadow: 0 0 0 0 rgba(34,197,94,.0); } 50% { box-shadow: 0 0 26px 3px rgba(34,197,94,.45); } }
@keyframes glowWarn { 0%, 100% { box-shadow: 0 0 0 0 rgba(245,158,11,.0); } 50% { box-shadow: 0 0 26px 3px rgba(245,158,11,.45); } }
@keyframes glowBad  { 0%, 100% { box-shadow: 0 0 0 0 rgba(239,68,68,.0); } 50% { box-shadow: 0 0 26px 3px rgba(239,68,68,.5); } }
@keyframes sweep    { from { left: -120%; } to { left: 140%; } }

html, body, .stApp, [data-testid="stSidebar"] { font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; }
.stApp {
  background:
    radial-gradient(1100px 560px at 8% -8%, rgba(37, 99, 235, .20), transparent 60%),
    radial-gradient(900px 480px at 100% 0%, rgba(56, 189, 248, .13), transparent 55%),
    radial-gradient(700px 400px at 50% 110%, rgba(0, 146, 70, .07), transparent 60%),
    var(--bg);
  color: var(--txt);
}
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.5rem; max-width: 1400px; animation: fadeUp .6s cubic-bezier(.2,.7,.2,1) both; }
h1, h2, h3, h4 { color: #f8fafc; font-weight: 700; letter-spacing: -.01em; }
h3 { margin-top: .6rem; }

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0d1424 0%, #090e19 100%); border-right: 1px solid var(--line); }
[data-testid="stSidebar"] > div:first-child { padding-top: 1rem; }
[data-testid="stSidebar"] img { border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,.35); }

/* ---------- hero ---------- */
.hero { display: flex; align-items: center; gap: 22px; margin: 2px 0 4px 0; animation: fadeUp .7s ease both; }
.hero-logo { width: 96px; height: auto; flex: none; filter: drop-shadow(0 8px 20px rgba(56,189,248,.35)); animation: float 5.5s ease-in-out infinite; }
.hero-title {
  font-size: 2.1rem; font-weight: 800; letter-spacing: -.02em; line-height: 1.12; margin: 0;
  background: linear-gradient(90deg, #f8fafc 0%, #7dd3fc 30%, #f8fafc 60%, #7dd3fc 90%);
  background-size: 220% auto; -webkit-background-clip: text; background-clip: text; color: transparent;
  animation: shimmer 9s linear infinite;
}
.hero-sub { color: var(--mut); font-size: .95rem; margin-top: 6px; max-width: 880px; }
.tricolor { height: 3px; width: 132px; border-radius: 3px; margin-top: 10px;
  background: linear-gradient(90deg, #009246 0 33.3%, #f8fafc 33.3% 66.6%, #ce2b37 66.6% 100%); }
.login-logo { display: block; margin: 0 auto 6px auto; width: 150px; height: auto; filter: drop-shadow(0 10px 26px rgba(56,189,248,.4)); animation: float 5.5s ease-in-out infinite, fadeUp .8s ease both; }

/* ---------- strip di stato ---------- */
.strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 16px 0 8px 0; }
.chip { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 12px 16px; backdrop-filter: blur(8px);
  animation: fadeUp .6s ease both; transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease; }
.chip:nth-child(1) { animation-delay: .05s; } .chip:nth-child(2) { animation-delay: .12s; }
.chip:nth-child(3) { animation-delay: .19s; } .chip:nth-child(4) { animation-delay: .26s; }
.chip:hover { transform: translateY(-3px); border-color: rgba(56,189,248,.5); box-shadow: 0 12px 32px rgba(2,132,199,.2); }
.chip .lbl { font-size: .68rem; text-transform: uppercase; letter-spacing: .09em; color: var(--mut); }
.chip .val { font-size: 1.55rem; font-weight: 700; color: #f8fafc; margin-top: 2px; }
.chip .sub { font-size: .72rem; color: #64748b; margin-top: 1px; }
.chip.ok   { border-left: 3px solid var(--ok); }
.chip.warn { border-left: 3px solid var(--warn); }
.chip.bad  { border-left: 3px solid var(--bad); }
.chip.info { border-left: 3px solid var(--acc); }

/* ---------- badge e punteggio ---------- */
.fascia { display: inline-flex; align-items: center; gap: 10px; padding: 8px 18px; border-radius: 999px; font-weight: 700; letter-spacing: .05em; color: #fff; }
.fascia .dot { width: 10px; height: 10px; border-radius: 50%; background: #fff; animation: pulse 1.8s ease-in-out infinite; }
.fascia.ok   { background: linear-gradient(135deg, #15803d, #22c55e); animation: popIn .5s ease both, glowOk 2.6s ease-in-out .6s infinite; }
.fascia.warn { background: linear-gradient(135deg, #b45309, #f59e0b); animation: popIn .5s ease both, glowWarn 2.6s ease-in-out .6s infinite; }
.fascia.bad  { background: linear-gradient(135deg, #b91c1c, #ef4444); animation: popIn .5s ease both, glowBad 2.2s ease-in-out .6s infinite; }
.scorecard { display: flex; align-items: center; gap: 28px; flex-wrap: wrap; background: var(--panel); border: 1px solid var(--line);
  border-radius: 18px; padding: 18px 24px; margin: 10px 0 6px 0; animation: fadeUp .6s ease both; }
.score-num { font-size: 3.6rem; font-weight: 800; line-height: 1; color: #f8fafc; animation: count 1.4s ease-out both; counter-reset: n var(--n); }
.score-num::after { content: counter(n); }
.score-max { font-size: 1.3rem; color: var(--mut); margin-left: 4px; font-weight: 600; }
.score-lbl { font-size: .7rem; text-transform: uppercase; letter-spacing: .1em; color: var(--mut); margin-bottom: 4px; }
.meter { display: flex; gap: 6px; margin-top: 12px; }
.meter i { width: 28px; height: 10px; border-radius: 4px; background: rgba(148,163,184,.2); animation: popIn .45s ease both; animation-delay: calc(var(--i) * 80ms); }
.meter i.on.ok   { background: linear-gradient(90deg, #16a34a, #4ade80); box-shadow: 0 0 10px rgba(34,197,94,.55); }
.meter i.on.warn { background: linear-gradient(90deg, #d97706, #fbbf24); box-shadow: 0 0 10px rgba(245,158,11,.55); }
.meter i.on.bad  { background: linear-gradient(90deg, #dc2626, #f87171); box-shadow: 0 0 10px rgba(239,68,68,.55); }
.score-desc { color: var(--mut); font-size: .88rem; margin-top: 8px; max-width: 520px; }

/* ---------- componenti Streamlit ---------- */
[data-testid="stMetric"] { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 14px 16px;
  animation: fadeUp .55s ease both; transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease; }
[data-testid="stMetric"]:hover { transform: translateY(-3px); border-color: rgba(56,189,248,.5); box-shadow: 0 12px 30px rgba(2,132,199,.18); }
[data-testid="stMetricValue"] { font-size: 1.75rem; font-weight: 700; color: var(--acc); }
[data-testid="stMetricLabel"] { color: var(--mut); }

.stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] { background: var(--panel2); border-radius: 10px 10px 0 0; color: var(--mut); padding: 10px 18px; font-weight: 600; border: none;
  transition: background .25s ease, color .25s ease, transform .2s ease; }
.stTabs [data-baseweb="tab"]:hover { color: #f8fafc; transform: translateY(-2px); }
.stTabs [aria-selected="true"] { background: linear-gradient(135deg, #1e3a8a 0%, #0284c7 100%) !important; color: #fff !important; box-shadow: 0 6px 18px rgba(2,132,199,.32); }
.stTabs [data-baseweb="tab-highlight"] { background-color: var(--acc) !important; height: 3px; border-radius: 3px; }

.stButton > button, .stDownloadButton > button {
  position: relative; overflow: hidden; background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); color: #fff; border-radius: 10px;
  padding: .6rem 1.2rem; font-weight: 600; border: none; box-shadow: 0 4px 14px rgba(37,99,235,.4);
  transition: transform .25s ease, box-shadow .25s ease; }
.stButton > button::after, .stDownloadButton > button::after { content: ""; position: absolute; top: 0; left: -120%; width: 55%; height: 100%;
  background: linear-gradient(120deg, transparent, rgba(255,255,255,.38), transparent); transform: skewX(-20deg); }
.stButton > button:hover, .stDownloadButton > button:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(37,99,235,.6); }
.stButton > button:hover::after, .stDownloadButton > button:hover::after { animation: sweep .8s ease; }
.stButton > button:active, .stDownloadButton > button:active { transform: translateY(0) scale(.98); }

.stTextInput input, .stNumberInput input, .stTextArea textarea, [data-baseweb="select"] > div {
  background-color: #111a2c !important; color: #fff !important; border-radius: 8px !important; border: 1px solid #263349 !important; transition: border-color .2s ease, box-shadow .2s ease; }
.stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus { border-color: var(--acc) !important; box-shadow: 0 0 0 3px rgba(56,189,248,.2) !important; }

[data-testid="stAlert"] { border-radius: 12px; border: 1px solid var(--line); animation: fadeUp .45s ease both; }
[data-testid="stDataFrame"], [data-testid="stDataEditor"] { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; animation: fadeUp .5s ease both; }
[data-testid="stExpander"] { border: 1px solid var(--line) !important; border-radius: 12px; background: var(--panel); }
[data-testid="stImage"] img, [data-testid="stImage"] canvas { border-radius: 12px; }
[data-testid="stPyplot"], .stPyplot { animation: fadeUp .6s ease both; }
[data-testid="stFileUploaderDropzone"] { background: var(--panel2); border: 1.5px dashed rgba(56,189,248,.4); border-radius: 14px; transition: border-color .25s ease, background .25s ease; }
[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--acc); background: rgba(56,189,248,.06); }
[data-testid="stSlider"] [role="slider"] { box-shadow: 0 0 0 4px rgba(56,189,248,.18); }
[data-testid="stToast"] { border-radius: 12px; border: 1px solid var(--line); }
hr { border-color: var(--line); }

::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb { background: #243049; border-radius: 8px; }
::-webkit-scrollbar-thumb:hover { background: #33425f; }

@media (max-width: 700px) {
  .hero { gap: 12px; } .hero-logo { width: 62px; } .hero-title { font-size: 1.35rem; }
  .score-num { font-size: 2.8rem; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
"""

CSS = "<style>" + _CSS_RAW + "</style>"


@functools.lru_cache(maxsize=8)
def logo_uri(path, larghezza=260):
    """Logo ridimensionato e codificato in data-URI (leggero da reinviare ad ogni rerun)."""
    if not path or not os.path.exists(path):
        return ""
    try:
        from PIL import Image
        with Image.open(path) as im:
            im = im.convert("RGBA")
            if im.width > larghezza:
                im = im.resize((larghezza, round(im.height * larghezza / im.width)), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format="PNG", optimize=True)
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return ""


def tono(classe):
    c = (classe or "").upper()
    return "ok" if "VERDE" in c else ("warn" if "GIALLA" in c else "bad")


def _e(t):
    return html.escape(str(t), quote=True)


def hero(uri, titolo, sottotitolo):
    logo = f'<img class="hero-logo" src="{uri}" alt="FCR"/>' if uri else ""
    return (f'<div class="hero">{logo}<div><h1 class="hero-title">{_e(titolo)}</h1>'
            f'<div class="hero-sub">{_e(sottotitolo)}</div><div class="tricolor"></div></div></div>')


def login_logo(uri):
    return f'<img class="login-logo" src="{uri}" alt="FCR"/>' if uri else ""


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
