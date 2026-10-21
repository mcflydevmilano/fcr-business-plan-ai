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
    """Cerca la foto accanto ad app.py: ing_lore.jpg, .jpeg o .png (anche con maiuscole)."""
    cartella = os.path.dirname(FOTO)
    try:
        nomi = sorted(os.listdir(cartella))
    except OSError:
        return ""
    for n in nomi:
        base, ext = os.path.splitext(n.lower())
        if base == "ing_lore" and ext in (".jpg", ".jpeg", ".png"):
            try:
                with open(os.path.join(cartella, n), "rb") as f:
                    mime = "image/png" if ext == ".png" else "image/jpeg"
                    return f"data:{mime};base64," + base64.b64encode(f.read()).decode()
            except OSError:
                return ""
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


# ----------------------------------------------------------------------------
# Saluti: benvenuto al login e arrivederci al logout (fumetto con la foto)
# ----------------------------------------------------------------------------
def ora_italia(adesso=None):
    if adesso is not None:
        return adesso
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("Europe/Rome")).replace(tzinfo=None)
    except Exception:
        return dt.datetime.now()


def saluto(adesso=None):
    """Buongiorno fino alle 13, Buon pomeriggio fino alle 18, poi Buonasera (e di notte)."""
    h = ora_italia(adesso).hour
    if 5 <= h < 13:
        return "Buongiorno"
    if 13 <= h < 18:
        return "Buon pomeriggio"
    return "Buonasera"


_BENVENUTO = {
    "Buongiorno": ["{s} {n}! Caffè pronto? I cantieri e i numeri ti aspettano, ma prima un bel respiro. ☕",
                   "{s} {n}! Oggi si costruisce qualcosa di buono. Io sono qui se ti serve una mano. 🏗️",
                   "{s} {n}, bentornato nella suite! Il casco è facoltativo, il buonumore no. 😄"],
    "Buon pomeriggio": ["{s} {n}! A metà strada: se non hai ancora bevuto, adesso è il momento. 💧",
                        "{s} {n}, bentornato! Il pomeriggio è lungo ma i conti tornano più in fretta con la suite. 📊",
                        "{s} {n}! Se qualcosa non torna, scrivimi: ci pensiamo insieme. 🛠️"],
    "Buonasera": ["{s} {n}! Ultimo sprint della giornata: facciamo le cose con calma, che i numeri non scappano. 🌙",
                  "{s} {n}, ancora al lavoro? Quando hai finito, stacca: il cantiere sopravvive fino a domani. 😉",
                  "{s} {n}! Una serata di numeri: se serve aiuto, sono qui. ✨"],
}


def frase_benvenuto(nome, adesso=None, scelta=None):
    s = saluto(adesso)
    pool = _BENVENUTO[s]
    t = pool[(scelta if scelta is not None else dt.datetime.now().microsecond) % len(pool)]
    return t.format(s=s, n=html.escape(str(nome or "").strip().title()))


def frase_addio(nome, adesso=None, scelta=None):
    d = ora_italia(adesso)
    n = html.escape(str(nome or "").strip().title())
    if d.weekday() == 4 and d.hour >= 12:
        pool = [f"A presto {n}! Buon fine settimana: lascia i cantieri ai cantieri. 🏖️", f"Ciao {n}, è venerdì: stacca e goditi il weekend! 🎉"]
    elif d.hour < 13:
        pool = [f"A presto {n}! Buona giornata e buon lavoro! ☀️", f"Ciao {n}, ci vediamo dopo. Fai una pausa e bevi un po' d'acqua. 💧"]
    elif d.hour < 18:
        pool = [f"A presto {n}! Buon proseguimento di pomeriggio. 👋", f"Ciao {n}, grazie del lavoro! Alla prossima. 🙌"]
    else:
        pool = [f"Buona serata {n}! Riposati, domani si riparte. 🌙", f"Ciao {n}, grazie e buona serata! Stasera niente numeri. 🍕"]
    return pool[(scelta if scelta is not None else dt.datetime.now().microsecond) % len(pool)]


def _css_saluto(uri, durata):
    img = f"background-image:url('{uri}');" if uri else "background:#1e3a8a;"
    return f"""<style>
.as-ben-av {{ position: fixed; right: 22px; bottom: 22px; width: 64px; height: 64px; border-radius: 50%; {img} background-size: cover; background-position: center;
  border: 3px solid #fff; box-shadow: 0 4px 14px rgba(15,23,42,.35), 0 0 0 2px #22c55e; z-index: 999988; pointer-events: none; }}
.as-ben {{ position: fixed; right: 100px; bottom: 30px; max-width: 300px; background: #fff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 16px 16px 4px 16px;
  padding: 13px 16px; font-size: .95rem; line-height: 1.45; box-shadow: 0 10px 28px rgba(15,23,42,.25); pointer-events: none; opacity: 0; z-index: 999991;
  animation: as-ben {durata}s ease .6s 1 both; }}
@keyframes as-ben {{ 0% {{ opacity: 0; transform: translateY(10px) scale(.96); }} 5% {{ opacity: 1; transform: none; }} 90% {{ opacity: 1; }} 100% {{ opacity: 0; visibility: hidden; }} }}
@media (max-width: 640px) {{ .as-ben-av {{ right: 12px; bottom: 12px; width: 54px; height: 54px; }} .as-ben {{ right: 76px; bottom: 18px; max-width: 220px; font-size: .85rem; }} }}
@media print {{ .as-ben, .as-ben-av {{ display: none; }} }}
</style>"""


def bolla_saluto(testo, durata=11, con_foto=False):
    """Fumetto temporaneo accanto alla foto in basso a destra. con_foto=True lo usa anche dove la foto non c'e' (pagina di login)."""
    avatar = "<div class='as-ben-av'></div>" if con_foto else ""
    st.markdown(_css_saluto(_foto_uri(), durata) + avatar + f"<div class='as-ben'>{testo}</div>", unsafe_allow_html=True)


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
    benvenuto = bool(st.session_state.pop("_benvenuto", False))
    if benvenuto:
        bolla_saluto(frase_benvenuto(utente or "collega"), 11)
    else:
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
