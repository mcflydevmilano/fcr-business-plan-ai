"""notifiche.py - Avvisi sul telefono per la chat: Telegram (bot aziendale) e/o ntfy (app di avvisi, anche su server proprio).

Gli avvisi NON contengono mai il testo del messaggio: dicono solo «nuovo messaggio da X» e portano alla suite.
Impostazioni (Secrets o variabili d'ambiente): TELEGRAM_BOT_TOKEN, NTFY_URL (es. https://ntfy.sh o il vostro server), APP_URL (indirizzo della suite).
"""
import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request

import chat

NTFY_PREDEFINITO = "https://ntfy.sh"


def _cfg(nome, predefinito=""):
    v = os.environ.get(nome, "")
    if not v:
        try:
            import streamlit as st
            v = str(st.secrets.get(nome, "") or "")
        except Exception:
            v = ""
    return (v or predefinito).strip()


def token_telegram():
    return _cfg("TELEGRAM_BOT_TOKEN")


def ntfy_url():
    return _cfg("NTFY_URL", NTFY_PREDEFINITO).rstrip("/")


def app_url():
    return _cfg("APP_URL")


def telegram_attivo():
    return bool(token_telegram())


# Funzione di rete sostituibile nei test: (url, dati(bytes|None), intestazioni(dict)) -> (codice_http, corpo)
def _http(url, dati=None, intestazioni=None, timeout=6):
    req = urllib.request.Request(url, data=dati, headers=intestazioni or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


HTTP = _http


def _solo_latin1(t):
    return t.encode("latin-1", "ignore").decode("latin-1")


def testo_avviso(autore, tipo, nome_canale, menzione=False):
    """Frase dell'avviso: nessun contenuto del messaggio."""
    if tipo == "diretto":
        return f"Nuovo messaggio da {autore}"
    if menzione:
        return f"{autore} ti ha citato in «{nome_canale}»"
    return f"Nuovo messaggio in «{nome_canale}» da {autore}"


def invia_telegram(chat_id, testo, token=None):
    token = token or token_telegram()
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    corpo = {"chat_id": chat_id, "text": testo + ("\n" + app_url() if app_url() else ""), "disable_web_page_preview": True}
    cod, _ = HTTP(url, json.dumps(corpo).encode("utf-8"), {"Content-Type": "application/json"})
    return cod == 200


def invia_ntfy(topic, testo):
    if not topic:
        return False
    intest = {"Title": "FCR Suite", "Priority": "default", "Tags": "speech_balloon"}
    if app_url():
        intest["Click"] = app_url()
    cod, _ = HTTP(f"{ntfy_url()}/{urllib.parse.quote(topic)}", testo.encode("utf-8"), {k: _solo_latin1(v) for k, v in intest.items()})
    return cod == 200


def avvisa(info, autore, testo_msg="", utenti_noti=(), path=None, sincrono=False):
    """Manda gli avvisi per un messaggio appena scritto (`info` = risultato di chat.invia). Restituisce quanti avvisi ha tentato."""
    citati = chat.menzioni(testo_msg, utenti_noti)
    dest = chat.destinatari_avviso(info["canale"], autore, citati, path)
    if not dest:
        return 0

    def lavoro():
        for d in dest:
            t = testo_avviso(autore, info["tipo"], info["nome"], d["username"] in citati)
            if d["telegram_chat_id"]:
                invia_telegram(d["telegram_chat_id"], t)
            if d["ntfy_topic"]:
                invia_ntfy(d["ntfy_topic"], t)
    if sincrono:
        lavoro()
    else:
        threading.Thread(target=lavoro, daemon=True).start()
    return len(dest)


# --- Collegamento di Telegram: la persona tocca il link, il bot riceve /start CODICE ---
def nome_bot(token=None):
    cod, corpo = HTTP(f"https://api.telegram.org/bot{token or token_telegram()}/getMe")
    try:
        return json.loads(corpo)["result"]["username"] if cod == 200 else ""
    except Exception:
        return ""


def link_telegram(codice, token=None):
    nb = nome_bot(token)
    return f"https://t.me/{nb}?start={codice}" if nb else ""


def collega_telegram(username, path=None, token=None):
    """Cerca tra i messaggi arrivati al bot quello con il codice della persona. True se ha collegato il telefono."""
    token = token or token_telegram()
    p = chat.prefs(username, path)
    if not token or not p["telegram_codice"]:
        return False
    cod, corpo = HTTP(f"https://api.telegram.org/bot{token}/getUpdates?limit=100")
    if cod != 200:
        return False
    try:
        agg = json.loads(corpo).get("result", [])
    except Exception:
        return False
    atteso = f"/start {p['telegram_codice']}"
    for u in reversed(agg):
        m = u.get("message") or {}
        if str(m.get("text", "")).strip() == atteso and m.get("chat", {}).get("id"):
            chat.salva_prefs(username, path, telegram_chat_id=str(m["chat"]["id"]), telegram_codice="")
            invia_telegram(str(m["chat"]["id"]), "Collegamento riuscito: da ora ricevi qui gli avvisi della chat FCR.", token)
            return True
    return False


def prova_avviso(username, path=None):
    """Manda un avviso di prova ai canali collegati. Restituisce {'telegram': bool|None, 'ntfy': bool|None}."""
    p = chat.prefs(username, path)
    r = {"telegram": None, "ntfy": None}
    if p["telegram_chat_id"]:
        r["telegram"] = invia_telegram(p["telegram_chat_id"], "Prova: gli avvisi della chat FCR funzionano.")
    if p["ntfy_topic"]:
        r["ntfy"] = invia_ntfy(p["ntfy_topic"], "Prova: gli avvisi della chat FCR funzionano.")
    return r
