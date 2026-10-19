"""
auth.py - Autenticazione per utente (senza Streamlit, quindi testabile).

Fonti degli utenti, in quest'ordine:
  1. Secrets / variabili d'ambiente: sezione [users] (persistono ai riavvii dell'hosting).
        [users.mario]
        hash = "pbkdf2_sha256$..."      # generato con:  python make_hash.py
        ruolo = "admin"                   # oppure "utente" (predefinito)
     In alternativa  mario = "pbkdf2_sha256$..."  (ruolo utente).
  2. Utenti creati dal pannello Amministrazione (salvati nel database SQLite).
  3. Compatibilita': APP_PASSWORD = password condivisa, accesso come utente "admin" (sconsigliato: usa i secrets [users]).

Le password sono salvate solo come hash PBKDF2-SHA256 con sale casuale. Dopo troppi tentativi falliti l'utente viene
bloccato per un po' (conteggio nel registro attivita').
"""
import hashlib
import hmac
import re
import secrets as _secrets

import storage

ITERAZIONI = 240_000
MAX_TENTATIVI = 5
FINESTRA_BLOCCO_S = 15 * 60
LUNGHEZZA_MIN_PASSWORD = 10
RUOLI = ("admin", "utente", "lettore")        # lettore = sola consultazione: niente modifica dei dati ne' salvataggi
_RE_USER = re.compile(r"^[a-z0-9][a-z0-9._-]{2,39}$")


def hash_password(password, salt=None, iterazioni=ITERAZIONI):
    salt = salt or _secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), iterazioni)
    return f"pbkdf2_sha256${iterazioni}${salt}${dk.hex()}"


def verifica_password(password, memorizzato):
    try:
        alg, it, salt, atteso = str(memorizzato).split("$")
        if alg != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(dk.hex(), atteso)
    except Exception:
        return False


def normalizza_username(u):
    return (u or "").strip().lower()


def valida_username(u):
    if not _RE_USER.match(u or ""):
        return "Nome utente non valido: 3-40 caratteri tra lettere minuscole, numeri, punto, trattino e underscore."
    return None


def valida_password(pw, username=""):
    if len(pw or "") < LUNGHEZZA_MIN_PASSWORD:
        return f"La password deve avere almeno {LUNGHEZZA_MIN_PASSWORD} caratteri."
    if username and username.lower() in pw.lower():
        return "La password non deve contenere il nome utente."
    if pw.isdigit() or pw.isalpha():
        return "Usa una combinazione di lettere e numeri (o simboli)."
    return None


def genera_password_temporanea():
    alfabeto = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(_secrets.choice(alfabeto) for _ in range(12)) + "7"


def utenti_da_secrets(cfg):
    """`cfg`: mapping {username: hash | {hash, ruolo}} proveniente dai secrets. Restituisce {username: {hash, ruolo}}."""
    out = {}
    try:
        items = dict(cfg or {}).items()
    except Exception:
        return out
    for nome, v in items:
        n = normalizza_username(nome)
        if isinstance(v, str):
            h, ruolo = v, "utente"
        else:
            try:
                h, ruolo = v.get("hash", ""), v.get("ruolo", "utente")
            except Exception:
                continue
        if n and h:
            out[n] = {"hash": str(h), "ruolo": ruolo if ruolo in RUOLI else "utente"}
    return out


def bloccato(username, path=None):
    return storage.tentativi_falliti(username, FINESTRA_BLOCCO_S, path) >= MAX_TENTATIVI


def autentica(username, password, utenti_secrets=None, app_password=None, path=None):
    """
    Restituisce (utente, errore). utente = {"username", "ruolo", "origine"} oppure None.
    Il messaggio di errore e' volutamente generico (non rivela se l'utente esiste).
    """
    u = normalizza_username(username)
    if not u or not password:
        return None, "Inserisci nome utente e password."
    if bloccato(u, path):
        storage.log_evento(u, "login_bloccato", "troppi tentativi", path)
        return None, "Troppi tentativi falliti: riprova tra 15 minuti o contatta l'amministratore."
    utente = None
    sec = (utenti_secrets or {}).get(u)
    if sec and verifica_password(password, sec["hash"]):
        utente = {"username": u, "ruolo": sec["ruolo"], "origine": "secrets"}
    if utente is None and not sec:
        rec = storage.utente_db(u, path)
        if rec and rec["attivo"] and verifica_password(password, rec["hash"]):
            utente = {"username": u, "ruolo": rec["ruolo"], "origine": "db"}
            storage.aggiorna_utente(u, path, ultimo_accesso=storage._now())
        elif rec is None and app_password and u == "admin" and hmac.compare_digest(password.encode(), str(app_password).encode()):
            utente = {"username": "admin", "ruolo": "admin", "origine": "app_password"}
    if utente is None:
        # verifica fittizia per non rendere distinguibile (a tempo) un utente inesistente
        verifica_password(password, "pbkdf2_sha256$1000$00$00")
        storage.log_evento(u, "login_fallito", "", path)
        return None, "Credenziali non valide."
    storage.log_evento(u, "login", utente["origine"], path)
    return utente, None


def ancora_valido(utente, utenti_secrets=None, path=None):
    """Controllo a ogni esecuzione: un utente disattivato/eliminato perde l'accesso subito."""
    if not utente:
        return False
    if utente["origine"] == "secrets":
        return utente["username"] in (utenti_secrets or {})
    if utente["origine"] == "db":
        rec = storage.utente_db(utente["username"], path)
        return bool(rec and rec["attivo"])
    return True


def crea_utente(username, password, ruolo="utente", da="", path=None):
    u = normalizza_username(username)
    err = valida_username(u) or valida_password(password, u)
    if err:
        raise ValueError(err)
    if ruolo not in RUOLI:
        raise ValueError("Ruolo non valido.")
    storage.salva_utente(u, hash_password(password), ruolo, da, path)
    storage.log_evento(da, "utente_creato", f"{u} ({ruolo})", path)


def cambia_password(username, vecchia, nuova, path=None):
    rec = storage.utente_db(username, path)
    if not rec or not verifica_password(vecchia, rec["hash"]):
        raise ValueError("La password attuale non e' corretta.")
    err = valida_password(nuova, username)
    if err:
        raise ValueError(err)
    storage.aggiorna_utente(username, path, hash=hash_password(nuova))
    storage.log_evento(username, "password_cambiata", "", path)


def reimposta_password(username, nuova, da="", path=None):
    err = valida_password(nuova, username)
    if err:
        raise ValueError(err)
    storage.aggiorna_utente(username, path, hash=hash_password(nuova))
    # azzera i tentativi falliti: usa un evento che li sblocca
    storage.log_evento(da, "password_reimpostata", username, path)
