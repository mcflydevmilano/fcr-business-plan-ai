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

import versione

_CSS_RAW = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Barlow+Condensed:wght@600;700&display=swap');

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
.block-container { padding-top: 1.6rem; max-width: 1400px; animation: fadeUp .5s cubic-bezier(.2,.7,.2,1) backwards; /* mai «both»: una trasformazione residua farebbe scorrere con la pagina gli elementi fissi (foto di assistenza) */ }
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
[data-testid="stColumn"]:has([class*="st-key-hubc_"]) > div, [data-testid="stColumn"]:has([class*="st-key-hubc_"]) > div > div { height: 100%; }
[class*="st-key-hubc_"] { height: 100%; display: flex; flex-direction: column; }
[class*="st-key-hubc_"] > div:first-child { flex: 1 1 auto; display: flex; flex-direction: column; }
[class*="st-key-hubc_"] > div:first-child div:has(.hub-card) { flex: 1 1 auto; height: 100%; }
[class*="st-key-hubc_"] .hub-card { height: calc(100% - 20px); box-sizing: border-box; }
.gd { display: flex; flex-direction: column; gap: 8px; margin: 6px 0 4px 0; }
.gd-step { display: flex; gap: 12px; align-items: flex-start; padding: 10px 12px; border: 1px solid var(--line); border-radius: 12px; background: var(--panel); }
.gd-step.ok { background: #f0fdf4; border-color: #bbf7d0; }
.gd-step.next { border-color: var(--acc); box-shadow: 0 0 0 2px rgba(37,99,235,.12); }
.gd-n { flex: none; width: 26px; height: 26px; border-radius: 50%; background: #e2e8f0; color: var(--navy); font-weight: 800; font-size: .85rem; display: flex; align-items: center; justify-content: center; }
.gd-step.ok .gd-n { background: #22c55e; color: #fff; }
.gd-step.next .gd-n { background: var(--acc); color: #fff; }
.gd-t { font-weight: 700; color: var(--navy); font-size: .97rem; }
.gd-x { color: var(--ink); font-size: .9rem; line-height: 1.45; margin-top: 2px; }
.hub-sez { margin: 30px 0 14px 0; padding-left: 14px; border-left: 4px solid var(--acc); }
.hub-sez-t { font-size: 1.25rem; font-weight: 800; color: var(--navy); letter-spacing: -.01em; }
.hub-sez-sub { color: var(--mut); font-size: .95rem; margin-top: 2px; }
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
.hub-card.sc::before { background: linear-gradient(90deg, #0e7490, #22d3ee); }
.hub-card.sc:hover { border-color: #a5f3fc; box-shadow: 0 2px 4px rgba(15,23,42,.06), 0 14px 34px rgba(14,116,144,.16); }
.hub-card.sc .hub-badge { background: #ecfeff; }
.hub-card.sc .hub-num { color: #0e7490; }
.hub-card.sc li::before { background: #cffafe; color: #0e7490; }
.hub-card.sl::before { background: linear-gradient(90deg, #4d7c0f, #a3e635); }
.hub-card.sl:hover { border-color: #d9f99d; box-shadow: 0 2px 4px rgba(15,23,42,.06), 0 14px 34px rgba(77,124,15,.16); }
.hub-card.sl .hub-badge { background: #f7fee7; }
.hub-card.sl .hub-num { color: #4d7c0f; }
.hub-card.sl li::before { background: #ecfccb; color: #4d7c0f; }
.hub-card.ga::before { background: linear-gradient(90deg, #7c3aed, #c4b5fd); }
.hub-card.ga:hover { border-color: #c4b5fd; box-shadow: 0 2px 4px rgba(15,23,42,.06), 0 14px 34px rgba(124,58,237,.16); }
.hub-card.ga .hub-badge { background: #f5f3ff; }
.hub-card.ga .hub-num { color: #7c3aed; }
.hub-card.ga li::before { background: #ede9fe; color: #7c3aed; }
.hub-card.fo::before { background: linear-gradient(90deg, #b45309, #fcd34d); }
.hub-card.fo:hover { border-color: #fcd34d; box-shadow: 0 2px 4px rgba(15,23,42,.06), 0 14px 34px rgba(180,83,9,.16); }
.hub-card.fo .hub-badge { background: #fffbeb; }
.hub-card.fo .hub-num { color: #b45309; }
.hub-card.fo li::before { background: #fef3c7; color: #b45309; }
.hub-card.sx::before { background: linear-gradient(90deg, #dc2626, #fca5a5); }
.hub-card.sx:hover { border-color: #fca5a5; box-shadow: 0 2px 4px rgba(15,23,42,.06), 0 14px 34px rgba(220,38,38,.16); }
.hub-card.sx .hub-badge { background: #fef2f2; }
.hub-card.sx .hub-num { color: #dc2626; }
.hub-card.sx li::before { background: #fee2e2; color: #dc2626; }
.hub-card.mz::before { background: linear-gradient(90deg, #475569, #94a3b8); }
.hub-card.mz:hover { border-color: #94a3b8; box-shadow: 0 2px 4px rgba(15,23,42,.06), 0 14px 34px rgba(71,85,105,.16); }
.hub-card.mz .hub-badge { background: #f1f5f9; }
.hub-card.mz .hub-num { color: #475569; }
.hub-card.mz li::before { background: #e2e8f0; color: #475569; }
.hub-card.og::before { background: linear-gradient(90deg, #0f766e, #5eead4); }
.hub-card.og:hover { border-color: #5eead4; box-shadow: 0 2px 4px rgba(15,23,42,.06), 0 14px 34px rgba(15,118,110,.16); }
.hub-card.og .hub-badge { background: #f0fdfa; }
.hub-card.og .hub-num { color: #0f766e; }
.hub-card.og li::before { background: #ccfbf1; color: #0f766e; }
.hub-card.rp::before { background: linear-gradient(90deg, #4338ca, #a5b4fc); }
.hub-card.rp:hover { border-color: #c7d2fe; box-shadow: 0 2px 4px rgba(15,23,42,.06), 0 14px 34px rgba(67,56,202,.16); }
.hub-card.rp .hub-badge { background: #eef2ff; }
.hub-card.rp .hub-num { color: #4338ca; }
.hub-card.rp li::before { background: #e0e7ff; color: #4338ca; }
.hub-card.gt::before { background: linear-gradient(90deg, #b45309, #fcd34d); }
.hub-card.gt:hover { border-color: #fde68a; box-shadow: 0 2px 4px rgba(15,23,42,.06), 0 14px 34px rgba(180,83,9,.16); }
.hub-card.gt .hub-badge { background: #fffbeb; }
.hub-card.gt .hub-num { color: #b45309; }
.hub-card.gt li::before { background: #fef3c7; color: #b45309; }
.hub-card.ca::before { background: linear-gradient(90deg, #0369a1, #38bdf8); }
.hub-card.ca:hover { border-color: #bae6fd; box-shadow: 0 2px 4px rgba(15,23,42,.06), 0 14px 34px rgba(3,105,161,.16); }
.hub-card.ca .hub-badge { background: #f0f9ff; }
.hub-card.ca .hub-num { color: #0369a1; }
.hub-card.ca li::before { background: #e0f2fe; color: #0369a1; }
.hub-card.dd::before { background: linear-gradient(90deg, #be123c, #fb7185); }
.hub-card.dd:hover { border-color: #fecdd3; box-shadow: 0 2px 4px rgba(15,23,42,.06), 0 14px 34px rgba(190,18,60,.16); }
.hub-card.dd .hub-badge { background: #fff1f2; }
.hub-card.dd .hub-num { color: #be123c; }
.hub-card.dd li::before { background: #ffe4e6; color: #be123c; }
.sem-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 12px; margin: 10px 0 18px 0; }
.sem { display: flex; gap: 12px; align-items: flex-start; background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 13px 15px; box-shadow: var(--shadow); }
.sem .dot { flex: 0 0 18px; width: 18px; height: 18px; border-radius: 50%; margin-top: 3px; box-shadow: 0 0 0 4px rgba(148,163,184,.18); }
.sem.ok .dot { background: #22c55e; box-shadow: 0 0 0 4px rgba(34,197,94,.18); }
.sem.warn .dot { background: #f59e0b; box-shadow: 0 0 0 4px rgba(245,158,11,.2); }
.sem.bad .dot { background: #ef4444; box-shadow: 0 0 0 4px rgba(239,68,68,.2); }
.sem.nd .dot { background: #cbd5e1; }
.sem .area { font-size: .66rem; text-transform: uppercase; letter-spacing: .09em; color: var(--mut); }
.sem .ind { font-size: .86rem; color: var(--ink); font-weight: 600; margin-top: 1px; }
.sem .vl { font-size: 1.35rem; font-weight: 700; color: var(--navy); margin-top: 2px; }
.sem .nt { font-size: .72rem; color: var(--mut); margin-top: 2px; }
.sem-big { display: flex; align-items: center; gap: 16px; border-radius: 16px; padding: 18px 22px; margin: 6px 0 14px 0; border: 1px solid var(--line); background: var(--panel); box-shadow: var(--shadow); }
.sem-big .dot { width: 34px; height: 34px; border-radius: 50%; }
.sem-big.ok .dot { background: #22c55e; } .sem-big.warn .dot { background: #f59e0b; } .sem-big.bad .dot { background: #ef4444; } .sem-big.nd .dot { background: #cbd5e1; }
.sem-big .tt { font-size: 1.25rem; font-weight: 700; color: var(--navy); } .sem-big .ss { font-size: .85rem; color: var(--mut); }
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
/* pulsanti con tooltip (help=): Streamlit li annida piu' in profondita', quindi il testo va forzato bianco con selettori discendenti */
[data-testid="stBaseButton-primary"] p, [data-testid="stBaseButton-secondary"] p, [data-testid="stBaseButton-primary"] span, [data-testid="stBaseButton-secondary"] span,
.stButton button p, .stDownloadButton button p { color: #fff !important; }
[data-testid="stBaseButton-primary"]:disabled p, [data-testid="stBaseButton-secondary"]:disabled p { color: #fff !important; }
/* «Sfoglia i file» del caricamento file: Streamlit gli dà sfondo bianco, ma il testo e' forzato bianco sopra */
[data-testid="stFileUploaderDropzone"] button, [data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] { background: var(--acc) !important; border: none !important; }
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

.st-key-hub_top { display: none; }
@media (max-width: 700px) {
  .st-key-hub_top { display: block !important; margin-left: 46px; max-width: 100px; }
  .hero { gap: 12px; } .hero-logo { width: 62px; } .hero-title { font-size: 1.35rem; }
  .hub-title { font-size: 1.5rem; } .score-num { font-size: 2.8rem; }
}
/* Telefono: le scritte dei tasti vanno a capo invece di essere tagliate */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button, [data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"] {
  height: auto !important; min-height: 2.5rem; white-space: normal !important; overflow-wrap: anywhere; line-height: 1.25; padding-top: .45rem; padding-bottom: .45rem;
}
.stButton > button p, .stDownloadButton > button p, .stFormSubmitButton > button p { white-space: normal !important; overflow: visible !important; text-overflow: clip !important; overflow-wrap: anywhere; line-height: 1.25; }
@media (max-width: 640px) {
  .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button { font-size: .88rem; padding-left: .55rem; padding-right: .55rem; }
  .stTabs [data-baseweb="tab"] { padding-left: 10px; padding-right: 10px; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
"""

EXTRA = '''
/* ---------- tavola di progetto: banner dell'Hub con cartiglio ---------- */
.tav { position: relative; margin: 4px 0 20px 0; padding: 30px 34px 22px 34px; border-radius: 6px; color: #fff; overflow: hidden;
  background: linear-gradient(rgba(127,176,255,.16) 1px, transparent 1px) 0 0 / 120px 120px, linear-gradient(90deg, rgba(127,176,255,.16) 1px, transparent 1px) 0 0 / 120px 120px,
              linear-gradient(rgba(127,176,255,.07) 1px, transparent 1px) 0 0 / 24px 24px, linear-gradient(90deg, rgba(127,176,255,.07) 1px, transparent 1px) 0 0 / 24px 24px,
              radial-gradient(1100px 420px at 12% -20%, #14418a 0%, #0b2a5b 55%, #08204a 100%);
  box-shadow: 0 18px 40px rgba(8,32,74,.28); animation: tavIn .9s ease both; }
.tav::before { content: ""; position: absolute; inset: 9px; border: 1px solid rgba(159,194,255,.35); border-radius: 3px; pointer-events: none; }
.tav-top { display: flex; align-items: stretch; justify-content: space-between; gap: 28px; flex-wrap: wrap; position: relative; }
.tav-id { display: flex; align-items: center; gap: 22px; min-width: 260px; flex: 1 1 520px; }
.tav-logo { width: 104px; height: auto; flex: none; filter: drop-shadow(0 8px 18px rgba(0,0,0,.45)); }
.tav .tav-h, .tav h1 { color: #fff !important; -webkit-text-fill-color: #fff; font-family: 'Barlow Condensed', 'Arial Narrow', 'Inter', sans-serif; font-weight: 700; font-size: clamp(2rem, 3.6vw, 3.1rem); line-height: 1.02; overflow-wrap: normal; word-break: normal; hyphens: none; letter-spacing: .005em; color: #fff; margin: 0; }
.tav-s { color: #bcd3ff; font-size: 1rem; margin-top: 8px; max-width: 460px; line-height: 1.45; }
.tav-tri { height: 3px; width: 150px; margin-top: 14px; transform-origin: left; animation: tavRule 1.1s .35s cubic-bezier(.2,.7,.2,1) both;
  background: linear-gradient(90deg, #009246 0 33.3%, #f1f5f9 33.3% 66.6%, #ce2b37 66.6% 100%); }
.cart { display: grid; grid-template-columns: 1.7fr 1fr; align-self: flex-end; margin-left: auto; min-width: 300px; flex: 0 1 400px; border: 1px solid rgba(159,194,255,.55); background: rgba(8,32,74,.55); backdrop-filter: blur(2px); }
.cart > div { padding: 8px 12px 9px 12px; border-right: 1px solid rgba(159,194,255,.35); border-bottom: 1px solid rgba(159,194,255,.35); }
.cart > div:nth-child(2n) { border-right: none; } .cart > div:nth-last-child(-n+2) { border-bottom: none; }
.cart .k { font-size: .7rem; color: #9fc2ff; letter-spacing: .03em; }
.cart .v { font-size: .98rem; font-weight: 600; color: #fff; margin-top: 2px; line-height: 1.25; }
.cart .v.ver { color: #ff8a3d; font-family: 'Barlow Condensed', 'Inter', sans-serif; font-size: 1.45rem; font-weight: 700; line-height: 1.1; }
.quota { position: relative; margin-top: 22px; height: 26px; }
.quota svg { width: 100%; height: 26px; display: block; overflow: visible; }
.quota .ln { stroke: #ff8a3d; stroke-width: 1.2; stroke-dasharray: 1600; stroke-dashoffset: 1600; animation: tavDraw 1.6s .5s cubic-bezier(.3,.7,.2,1) forwards; }
.quota .lbl { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); padding: 0 16px; background: #0a2552; color: #ffb98a; font-size: .8rem; font-weight: 600; letter-spacing: .03em; white-space: nowrap; opacity: 0; animation: tavFade .6s 1.5s ease forwards; }
@keyframes tavIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
@keyframes tavRule { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@keyframes tavDraw { to { stroke-dashoffset: 0; } }
@keyframes tavFade { to { opacity: 1; } }
@media (max-width: 640px) { .tav { padding: 22px 18px 16px 18px; } .tav-h { font-size: 1.9rem; } .tav-logo { width: 76px; } .cart { min-width: 0; width: 100%; flex-basis: 100%; grid-template-columns: 1fr 1fr; } }
@media (prefers-reduced-motion: reduce) { .tav, .tav-tri, .quota .ln, .quota .lbl { animation: none !important; stroke-dashoffset: 0; opacity: 1; transform: none; } }

/* titoli: lettering tecnico da tavola di cantiere */
.hub-sez-t { font-family: 'Barlow Condensed', 'Inter', sans-serif; font-size: 1.75rem; font-weight: 700; letter-spacing: .005em; }
.hero-title { font-family: 'Barlow Condensed', 'Inter', sans-serif; font-size: 2.7rem; font-weight: 700; letter-spacing: .005em; line-height: 1.02;
  background: none; -webkit-text-fill-color: var(--navy); color: var(--navy); animation: none; }
.hero-logo { animation: none; }
.hero { padding-bottom: 6px; border-bottom: 1px solid var(--line); margin-bottom: 14px; }
.b-ver { margin-top: 10px; padding-top: 8px; border-top: 1px dashed var(--line2); font-size: .68rem; color: var(--mut); line-height: 1.4; }
.b-ver b { color: #c2410c; font-weight: 700; }
.login-prop { margin: 18px 0 22px 0; font-size: .74rem; color: var(--mut); line-height: 1.45; }
'''

SIDEBAR_CSS = """
[data-testid="stSidebar"] { background: linear-gradient(180deg, #f1f5f9 0%, #ffffff 34%); }
[data-testid="stSidebar"] > div:first-child { padding-top: .8rem; }
.sb-brand { position: relative; overflow: hidden; text-align: center; color: #fff; border-radius: 20px; padding: 16px 14px 14px; margin-bottom: 12px;
  background: linear-gradient(140deg, #0a1640 0%, #1e3fae 62%, #2563eb 100%); box-shadow: 0 12px 28px rgba(30,64,175,.34); animation: fadeUp .5s ease backwards; }
.sb-brand::before { content: ""; position: absolute; inset: 0; pointer-events: none;
  background-image: linear-gradient(rgba(255,255,255,.07) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.07) 1px, transparent 1px); background-size: 22px 22px; }
.sb-brand::after { content: ""; position: absolute; right: -40px; top: -40px; width: 140px; height: 140px; border-radius: 50%; pointer-events: none;
  background: radial-gradient(circle, rgba(249,115,22,.55), transparent 68%); }
.sb-brand > * { position: relative; z-index: 1; }
.sb-logo { background: #fff; border-radius: 14px; padding: 8px 12px; width: 66%; margin: 0 auto 10px; box-shadow: 0 4px 14px rgba(2,6,23,.25); }
.sb-logo img { display: block; width: 100%; height: auto; mix-blend-mode: multiply; }
.sb-name { font-size: .98rem; font-weight: 800; letter-spacing: .22em; text-indent: .22em; }
.sb-sub { font-size: .68rem; color: rgba(255,255,255,.72); margin-top: 3px; line-height: 1.35; }
.sb-dev { margin-top: 12px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,.2); display: flex; flex-direction: column; gap: 1px; }
.sb-dev span { font-size: .62rem; letter-spacing: .14em; text-transform: uppercase; color: rgba(255,255,255,.6); }
.sb-dev b { font-size: .95rem; color: #fff; }
.sb-dev em { font-style: normal; font-size: .74rem; color: rgba(255,255,255,.75); }
.sb-ver { display: inline-block; margin-top: 11px; font-size: .68rem; color: rgba(255,255,255,.8); background: rgba(255,255,255,.13);
  border: 1px solid rgba(255,255,255,.26); border-radius: 99px; padding: 3px 11px; }
.sb-ver b { color: #fdba74; }

.st-key-sb_ora, .st-key-sb_utente { background: #fff; border: 1px solid var(--line); border-radius: 16px; padding: 8px 10px 6px; margin-bottom: 10px; box-shadow: var(--shadow); }
.st-key-sb_ora iframe { border-radius: 10px; }
.sb-meteo { border-top: 1px dashed var(--line2); padding: 9px 2px 14px; margin-top: 2px; overflow: visible; }
.st-key-sb_ora, .st-key-sb_ora [data-testid="stMarkdownContainer"], .st-key-sb_ora [data-testid="stElementContainer"] { overflow: visible !important; }
.sb-meteo .mt-top { display: flex; align-items: center; justify-content: center; gap: 10px; }
.sb-meteo .mt-ico { font-size: 2rem; line-height: 1; }
.sb-meteo .mt-temp { font-size: 1.35rem; font-weight: 800; color: var(--navy); line-height: 1.05; }
.sb-meteo .mt-txt { font-size: .8rem; color: #334155; }
.sb-meteo .mt-citta { text-align: center; font-size: .72rem; font-weight: 700; color: var(--acc); margin: 7px 0 7px; letter-spacing: .04em; }
.sb-meteo .mt-grid { display: flex; gap: 6px; }
.sb-meteo .mt-c { flex: 1 1 0; min-width: 0; text-align: center; background: var(--panel2); border-radius: 9px; padding: 5px 2px; }
.sb-meteo .mt-c span { display: block; font-size: .6rem; text-transform: uppercase; letter-spacing: .08em; color: var(--mut); }
.sb-meteo .mt-c b { font-size: .8rem; color: var(--navy); white-space: nowrap; }
.sb-urow { display: flex; align-items: center; gap: 11px; padding: 4px 2px 8px; }
.sb-avatar { flex: 0 0 auto; width: 46px; height: 46px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-weight: 800; font-size: 1rem;
  background: linear-gradient(135deg, #1e3fae, #2563eb); box-shadow: 0 0 0 3px #dbeafe, 0 4px 10px rgba(30,64,175,.3); }
.sb-avatar.sb-foto { background-size: cover; background-position: center; color: transparent; }
.sb-uname { font-weight: 700; color: var(--navy); font-size: .95rem; line-height: 1.2; word-break: break-word; }
.sb-chips { margin-top: 4px; display: flex; flex-wrap: wrap; gap: 4px; }
.chip { font-size: .64rem; font-weight: 700; letter-spacing: .03em; padding: 2px 8px; border-radius: 99px; text-transform: capitalize; }
.chip.admin { background: #fee2e2; color: #b91c1c; } .chip.utente { background: #dbeafe; color: #1e40af; } .chip.lettore { background: #e2e8f0; color: #475569; }
.chip.prof { background: #dcfce7; color: #15803d; text-transform: none; }
.sb-label { font-size: .66rem; font-weight: 800; letter-spacing: .16em; color: #94a3b8; text-transform: uppercase; margin: 14px 4px 6px; }

.st-key-sb_nav [data-testid="stExpander"] { border: 0 !important; box-shadow: none !important; background: transparent !important; }
.st-key-sb_nav [data-testid="stExpander"] details { border: 1px solid var(--line); border-radius: 12px; background: #fff; box-shadow: none; margin-bottom: 6px; }
.st-key-sb_nav [data-testid="stExpander"] summary { padding: .45rem .7rem; font-size: .84rem; font-weight: 700; color: var(--navy); }
.st-key-sb_nav [data-testid="stExpander"] summary:hover { background: var(--accsoft); border-radius: 12px; }
.st-key-sb_nav [data-testid="stExpanderDetails"] { padding: 0 .35rem .4rem; }
.st-key-sb_nav .stButton > button { justify-content: flex-start !important; text-align: left; width: 100%; border: 0 !important; background: transparent !important;
  box-shadow: none !important; padding: .32rem .6rem; min-height: 0; font-size: .84rem; border-radius: 9px; }
.st-key-sb_nav .stButton > button > div { justify-content: flex-start !important; width: 100%; }
.st-key-sb_nav [data-testid="stMarkdownContainer"] { width: 100%; }
.st-key-sb_nav .stButton > button p { text-align: left; width: 100%; font-weight: 600; color: #334155 !important; }
.st-key-sb_nav .stButton > button:hover { background: var(--accsoft) !important; transform: translateX(2px); }
.st-key-sb_nav .stButton > button:hover p { color: var(--acc) !important; }
.st-key-sb_nav button[data-testid="stBaseButton-primary"] { background: linear-gradient(135deg, #1e3fae, #2563eb) !important; box-shadow: 0 6px 14px rgba(30,64,175,.3) !important; }
.st-key-sb_nav button[data-testid="stBaseButton-primary"] p { color: #fff !important; }
.st-key-sb_nav button[data-testid="stBaseButton-primary"]:hover { transform: none; }
.st-key-sb_hubbtn .stButton > button > div { justify-content: center !important; }
.st-key-sb_hubbtn .stButton > button p { text-align: center !important; }
.st-key-sb_hubbtn .stButton > button { justify-content: center !important; border: 1px solid #bfdbfe !important; background: #fff !important; font-weight: 700; }
.st-key-sb_hubbtn button[data-testid="stBaseButton-primary"] { background: linear-gradient(135deg, #1e3fae, #2563eb) !important; border: 0 !important; box-shadow: 0 6px 14px rgba(30,64,175,.3) !important; }
.st-key-sb_hubbtn button[data-testid="stBaseButton-primary"] p { color: #fff !important; }
.st-key-sb_utente .stButton > button { border-radius: 10px; font-size: .82rem; padding: .3rem .5rem; min-height: 0; }
@media (prefers-reduced-motion: reduce) { .sb-brand { animation: none; } }
"""


def _css_versione():
    """Piede di pagina su ogni schermata: versione e proprieta' del software, senza codice nelle singole pagine."""
    riga = versione.riga_versione().replace("\\", "").replace('"', "") + " · " + versione.COPYRIGHT.replace('"', "")
    return ('[data-testid="stMain"]::after, section.main::after { content: "' + riga + '"; display: block; text-align: center; font-size: .72rem; color: #64748b; '
            'padding: 34px 16px 96px 16px; letter-spacing: .01em; }')


CSS = "<style>" + _CSS_RAW + EXTRA + SIDEBAR_CSS + _css_versione() + "</style>"


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
            f'<div class="login-sub">Aetheris Labs - Area Riservata Protetta</div>'
            f'<div class="login-prop">{_e(versione.NOME)} v{_e(versione.VERSIONE)} · Software di proprietà di {_e(versione.PROPRIETARIO)}<br>{_e(versione.COPYRIGHT)}</div></div>')


def sidebar_brand(uri_aeth):
    logo = f'<div class="sb-logo"><img src="{uri_aeth}" alt="Aetheris Labs"/></div>' if uri_aeth else ""
    return (f'<div class="sb-brand">{logo}<div class="sb-name">AETHERIS LABS</div>'
            f'<div class="sb-sub">Software, AI &amp; Game Development Division</div>'
            f'<div class="sb-dev"><span>Sviluppato da</span><b>Ing. Lorenzo Di Ferdinando</b><em>FCR General Contractor</em></div>'
            f'<div class="sb-ver">{_e(versione.NOME)} <b>v{_e(versione.VERSIONE)}</b></div></div>')


def sidebar_utente(username, ruolo, profilo, foto_b64=None):
    """Scheda dell'utente: iniziali in un cerchio, nome, ruolo e profilo come etichette colorate."""
    nome = _e(username)
    sigla = _e("".join(p[0] for p in str(username).replace(".", " ").replace("_", " ").split()[:2]).upper() or str(username)[:1].upper())
    cl = ruolo if ruolo in ("admin", "utente", "lettore") else "utente"
    if foto_b64 and all(c.isalnum() or c in "+/=" for c in foto_b64):          # solo base64 pulito dentro lo stile
        av = f'<div class="sb-avatar sb-foto" style="background-image:url(data:image/jpeg;base64,{foto_b64})"></div>'
    else:
        av = f'<div class="sb-avatar">{sigla}</div>'
    return (f'<div class="sb-urow">{av}<div><div class="sb-uname">{nome}</div>'
            f'<div class="sb-chips"><span class="chip {cl}">{_e(ruolo)}</span><span class="chip prof">{_e(profilo)}</span></div></div></div>')


def hub_header(uri_fcr, n_strumenti=15):
    """Banner dell'Hub come una tavola di progetto: titolo, cartiglio (proprieta' e versione) e linea di quota."""
    logo = f'<img class="tav-logo" src="{uri_fcr}" alt="FCR"/>' if uri_fcr else ""
    cart = (f'<div class="cart"><div><div class="k">Progetto</div><div class="v">{_e(versione.NOME)}</div></div>'
            f'<div><div class="k">Versione</div><div class="v ver">{_e(versione.VERSIONE)}</div></div>'
            f'<div><div class="k">Proprietà del software</div><div class="v">{_e(versione.PROPRIETARIO)}</div></div>'
            f'<div><div class="k">Rilascio</div><div class="v">{_e(versione.DATA_RILASCIO)}</div></div></div>')
    quota = (f'<div class="quota"><svg viewBox="0 0 1000 26" preserveAspectRatio="none" aria-hidden="true"><g class="ln-g">'
             '<line class="ln" x1="0" y1="13" x2="1000" y2="13"/><line class="ln" x1="0" y1="3" x2="0" y2="23"/><line class="ln" x1="1000" y1="3" x2="1000" y2="23"/>'
             '<path class="ln" d="M0 13 L14 8 M0 13 L14 18 M1000 13 L986 8 M1000 13 L986 18"/></g></svg>'
             f'<span class="lbl">{n_strumenti} strumenti · una sola suite</span></div>')
    return (f'<div class="tav"><div class="tav-top"><div class="tav-id">{logo}<div><h1 class="tav-h">FCR General Contractor</h1>'
            f'<div class="tav-s">La suite operativa per offerte, cantieri, fornitori e finanza: {n_strumenti} strumenti, un solo posto.</div><div class="tav-tri"></div></div></div>{cart}</div>{quota}</div>')


def hub_sezione(titolo, sotto=""):
    s = f'<div class="hub-sez-sub">{_e(sotto)}</div>' if sotto else ""
    return f'<div class="hub-sez"><div class="hub-sez-t">{_e(titolo)}</div>{s}</div>'


def hub_card(numero, icona, titolo, descrizione, voci, tags, variante=""):
    li = "".join(f"<li>{_e(v)}</li>" for v in voci)
    tg = "".join(f'<span class="hub-tag">{_e(t)}</span>' for t in tags)
    return (f'<div class="hub-card {variante}"><div class="hub-badge">{icona}</div><div class="hub-num">{_e(numero)}</div>'
            f'<h2>{_e(titolo)}</h2><p>{_e(descrizione)}</p><ul>{li}</ul><div class="hub-tags">{tg}</div></div>')


def semafori_html(righe):
    """Griglia di semafori. righe: dict con Area, Indicatore, Valore, Stato (ok|warn|bad|nd), Nota."""
    celle = "".join(
        f'<div class="sem {_e(r["Stato"])}"><div class="dot"></div><div><div class="area">{_e(r["Area"])}</div>'
        f'<div class="ind">{_e(r["Indicatore"])}</div><div class="vl">{_e(r["Valore"])}</div><div class="nt">{_e(r["Nota"])}</div></div></div>'
        for r in righe)
    return f'<div class="sem-grid">{celle}</div>'


def semaforo_generale(stato, titolo, sotto):
    return (f'<div class="sem-big {_e(stato)}"><div class="dot"></div><div><div class="tt">{_e(titolo)}</div>'
            f'<div class="ss">{_e(sotto)}</div></div></div>')


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
