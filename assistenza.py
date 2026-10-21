"""
assistenza.py - Bottone rotondo con la foto di Lorenzo, fisso in basso a destra, non invasivo.
Dopo qualche secondo compare una nuvoletta ("se hai bisogno di assistenza o vuoi segnalare qualcosa, scrivimi qui") che sparisce da sola.
Cliccando si apre un piccolo modulo: il messaggio arriva su Slack nel canale/DM di Lorenzo.

Segreti (Streamlit Secrets, mai su GitHub):
  SLACK_ASSISTENZA_WEBHOOK_URL   Incoming Webhook che scrive nel DM di Lorenzo (o in un canale suo). Diverso da quello del riepilogo.
  SLACK_DM_URL                   (facoltativo) link che apre la chat Slack, es. slack://user?team=T0000&id=U0000 oppure https://app.slack.com/client/T0000/U0000
"""
import base64
import datetime as dt
import html
import json
import os
import urllib.request

import streamlit as st

ss = st.session_state
FOTO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ing_lore.jpg")
NOME = "Lorenzo"
TIPI = ["🛠️ Ho bisogno di assistenza", "⚠️ Segnalo un problema", "💡 Ho un'idea / un suggerimento"]


def _segreto(nome):
    v = os.environ.get(nome, "")
    if not v:
        try:
            v = st.secrets.get(nome, "")
        except Exception:
            v = ""
    return str(v or "").strip()


def _foto_uri():
    try:
        with open(FOTO, "rb") as f:
            return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
    except OSError:
        return ""


def costruisci_messaggio(tipo, testo, utente="", strumento="", quando=None):
    """Testo per Slack del messaggio di un collega."""
    quando = quando or dt.datetime.now()
    return (f"*{tipo}*\n{testo.strip()}\n\n"
            f"_Da: {utente or 'utente non indicato'}" + (f" · strumento: {strumento}" if strumento else "") + f" · {quando.strftime('%d/%m/%Y %H:%M')}_")


def invia_slack(testo, url):
    if not url.startswith("https://hooks.slack.com/"):
        raise RuntimeError("SLACK_ASSISTENZA_WEBHOOK_URL mancante o non valido.")
    req = urllib.request.Request(url, data=json.dumps({"text": testo}).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        if r.status != 200:
            raise RuntimeError(f"Slack ha risposto {r.status}")


def _css(uri):
    img = f"background-image:url('{uri}');" if uri else "background:#1e3a8a;"
    return f"""<style>
.st-key-assist_box {{ position: fixed; right: 22px; bottom: 22px; z-index: 999990; width: 64px; height: 64px; }}
.st-key-assist_box [data-testid="stPopover"] > div > button, .st-key-assist_box button[data-testid="stPopoverButton"] {{
  width: 64px; height: 64px; min-height: 64px; padding: 0; border-radius: 50%; {img} background-size: cover; background-position: center;
  border: 3px solid #fff; box-shadow: 0 4px 14px rgba(15,23,42,.35), 0 0 0 2px #22c55e; color: transparent; font-size: 0; overflow: hidden; }}
.st-key-assist_box [data-testid="stPopover"] button svg, .st-key-assist_box [data-testid="stPopover"] button span {{ display: none; }}
.st-key-assist_box [data-testid="stPopover"] button:hover {{ transform: scale(1.06); }}
.as-bolla {{ position: fixed; right: 100px; bottom: 34px; max-width: 260px; background: #fff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 14px 14px 4px 14px;
  padding: 10px 14px; font-size: .88rem; line-height: 1.4; box-shadow: 0 6px 20px rgba(15,23,42,.18); pointer-events: none; opacity: 0; z-index: 999989;
  animation: as-bolla 14s ease 4s 1 both; }}
@keyframes as-bolla {{ 0% {{ opacity: 0; transform: translateY(8px); }} 6% {{ opacity: 1; transform: none; }} 88% {{ opacity: 1; }} 100% {{ opacity: 0; visibility: hidden; }} }}
@media (max-width: 640px) {{ .st-key-assist_box {{ right: 12px; bottom: 12px; width: 54px; height: 54px; }}
  .st-key-assist_box [data-testid="stPopover"] > div > button, .st-key-assist_box button[data-testid="stPopoverButton"] {{ width: 54px; height: 54px; min-height: 54px; }}
  .as-bolla {{ right: 76px; bottom: 20px; max-width: 200px; font-size: .8rem; }} }}
@media print {{ .st-key-assist_box, .as-bolla {{ display: none; }} }}
</style>"""


def render(utente="", strumento=""):
    """Da chiamare una volta per esecuzione, dopo il login."""
    st.markdown(_css(_foto_uri()), unsafe_allow_html=True)
    st.markdown(f"<div class='as-bolla'>👋 Cari colleghi, se avete bisogno di assistenza o volete segnalare qualcosa, <b>scrivetemi qui</b>.</div>", unsafe_allow_html=True)
    url, dm = _segreto("SLACK_ASSISTENZA_WEBHOOK_URL"), _segreto("SLACK_DM_URL")
    with st.container(key="assist_box"):
        with st.popover("💬", help=f"Scrivi a {NOME}"):
            st.markdown(f"**Ciao, sono {NOME}!** Scrivimi qui se ti serve aiuto o se vuoi segnalare qualcosa: ti rispondo appena posso.")
            with st.form("as_form", clear_on_submit=True, border=False):
                tipo = st.selectbox("Di cosa si tratta?", TIPI, key="as_tipo")
                testo = st.text_area("Scrivi il messaggio", key="as_testo", height=110, placeholder="Es. Nel Rapportino non riesco a salvare / Manca il cantiere X nell'elenco…")
                inv = st.form_submit_button("📨 Invia", type="primary", use_container_width=True)
            if inv:
                if not testo.strip():
                    st.warning("Scrivi prima il messaggio.")
                elif not url:
                    st.error("L'invio non è ancora attivo: chiedi a Lorenzo di configurare il canale Slack." + (" Intanto puoi scrivergli direttamente sotto." if dm else ""))
                else:
                    try:
                        invia_slack(costruisci_messaggio(tipo, testo, utente, strumento), url)
                        st.success("Messaggio inviato. Grazie! 🙏")
                    except Exception as e:
                        st.error(f"Invio non riuscito: {e}")
            if dm:
                st.link_button("Apri la chat Slack", dm, use_container_width=True)
