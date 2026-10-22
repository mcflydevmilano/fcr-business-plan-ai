"""
sessione.py - Resta collegato dopo l'aggiornamento della pagina (F5) senza rifare il login, per un tempo limitato.

Come funziona: al login il server firma un «gettone» (nome utente + scadenza + impronta della password) e il browser lo conserva in un cookie.
Quando la pagina si ricarica, il server ricontrolla la firma, la scadenza e che l'utente sia ancora attivo e con la stessa password.
Il gettone non contiene la password. Cambiare la password o disattivare l'utente lo invalida subito; «Esci» lo cancella.
Senza Streamlit (a parte le due funzioni che scrivono il cookie), quindi testabile.
"""
import base64
import hashlib
import hmac
import json
import os
import time

import auth
import storage

COOKIE = "fcr_sess"
ORE_PREDEFINITE = 12
_CASUALE = os.urandom(32)            # ultima spiaggia: senza segreti configurati i gettoni valgono finche' il server resta acceso


def chiave(segreti):
    """Chiave di firma ricavata dai segreti dell'app (mai dal codice, che e' pubblico). `segreti`: lista di testi, quelli vuoti si ignorano."""
    parti = [str(s) for s in segreti if s]
    if not parti:
        return _CASUALE
    return hashlib.sha256(("fcr-sessione|" + "|".join(parti)).encode("utf-8")).digest()


def _b64(b):
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def impronta(utente, utenti_secrets=None, app_password=None, path=None):
    """Breve riassunto della password dell'utente: se cambia, i gettoni vecchi non valgono piu'."""
    u = utente["username"]
    if utente["origine"] == "secrets":
        base = ((utenti_secrets or {}).get(u) or {}).get("hash", "")
    elif utente["origine"] == "db":
        rec = storage.utente_db(u, path)
        base = rec["hash"] if rec else ""
    else:
        base = str(app_password or "")
    return hashlib.sha256(("imp|" + str(base)).encode("utf-8")).hexdigest()[:12] if base else ""


def crea(utente, key, utenti_secrets=None, app_password=None, ore=ORE_PREDEFINITE, adesso=None, path=None):
    adesso = adesso if adesso is not None else time.time()
    corpo = _b64(json.dumps({"u": utente["username"], "o": utente["origine"], "e": int(adesso + ore * 3600), "i": impronta(utente, utenti_secrets, app_password, path)},
                            separators=(",", ":")).encode("utf-8"))
    firma = _b64(hmac.new(key, corpo.encode("ascii"), hashlib.sha256).digest())
    return f"{corpo}.{firma}"


def leggi(token, key, adesso=None):
    """Contenuto del gettone se la firma e la scadenza sono valide, altrimenti None."""
    try:
        corpo, firma = str(token).split(".", 1)
        atteso = _b64(hmac.new(key, corpo.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(firma, atteso):
            return None
        dati = json.loads(_unb64(corpo).decode("utf-8"))
        if int(dati["e"]) < (adesso if adesso is not None else time.time()):
            return None
        return dati
    except Exception:
        return None


def ripristina(token, key, utenti_secrets=None, app_password=None, path=None, adesso=None):
    """L'utente da riportare dentro (con ruolo riletto dai dati attuali) oppure None se il gettone non vale piu'."""
    dati = leggi(token, key, adesso)
    if not dati:
        return None
    u, origine = dati.get("u", ""), dati.get("o", "")
    if origine == "secrets":
        sec = (utenti_secrets or {}).get(u)
        utente = {"username": u, "ruolo": sec["ruolo"], "origine": "secrets"} if sec else None
    elif origine == "db":
        rec = storage.utente_db(u, path)
        utente = {"username": u, "ruolo": rec["ruolo"], "origine": "db"} if rec and rec["attivo"] else None
    elif origine == "app_password" and app_password and u == "admin":
        utente = {"username": "admin", "ruolo": "admin", "origine": "app_password"}
    else:
        utente = None
    if not utente or not auth.ancora_valido(utente, utenti_secrets, path):
        return None
    if not hmac.compare_digest(dati.get("i", ""), impronta(utente, utenti_secrets, app_password, path)):
        return None                                           # password cambiata dopo l'emissione del gettone
    return utente


_JS = """
export default function(component) {
  const { data } = component;
  const sec = location.protocol === 'https:' ? '; Secure' : '';
  const base = '; path=/; SameSite=Lax' + sec;
  try {
    if (data && data.token) document.cookie = '""" + COOKIE + """=' + data.token + '; max-age=' + data.durata + base;
    else document.cookie = '""" + COOKIE + """=; max-age=0' + base;
  } catch (e) {}
}
"""


def scrivi_cookie(token, ore=ORE_PREDEFINITE):
    """Salva il gettone nel browser (token vuoto = cancella il cookie). Da chiamare dentro un'esecuzione dell'app."""
    import streamlit as st
    try:
        st.components.v2.component("fcr_sessione_cookie", js=_JS)(data={"token": token or "", "durata": int(ore * 3600)}, key="fcr_sessione_cookie_c")
    except Exception:
        pass


def cookie_corrente():
    """Il cookie di sessione inviato dal browser (testo) oppure ''."""
    import streamlit as st
    try:
        return st.context.cookies.get(COOKIE, "") or ""
    except Exception:
        return ""
