"""due_passaggi.py - Verifica in due passaggi (codice a 6 cifre da app tipo Google Authenticator, Microsoft Authenticator, Aegis, 1Password).

TOTP secondo RFC 6238 (SHA-1, 30 secondi, 6 cifre), scritto con la sola libreria standard. I segreti si conservano nel database,
cifrati con la chiave CHAT_KEY (o DUEPASSAGGI_KEY, se impostata): senza chiavi restano in chiaro nel database. Ogni persona ha anche 8 codici di
emergenza monouso, salvati solo come impronta. Senza Streamlit, quindi testabile.
"""
import base64
import hashlib
import hmac
import io
import os
import re
import secrets
import struct
import time

import storage

NOME_CFG = "sicurezza_2fa"
EMITTENTE = "FCR Suite"
PASSO_S = 30
CIFRE = 6
N_CODICI = 8


# ----------------------------------------------------------------------------
# TOTP
# ----------------------------------------------------------------------------
def nuovo_segreto():
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _chiave(segreto):
    s = re.sub(r"[\s-]", "", str(segreto)).upper()
    return base64.b32decode(s + "=" * (-len(s) % 8))


def codice(segreto, t=None):
    """Il codice valido in questo momento (o all'istante `t`, in secondi)."""
    return _codice_passo(segreto, int((time.time() if t is None else t) // PASSO_S))


def _codice_passo(segreto, passo):
    h = hmac.new(_chiave(segreto), struct.pack(">Q", passo), hashlib.sha1).digest()
    o = h[-1] & 0x0F
    n = (struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % (10 ** CIFRE)
    return str(n).zfill(CIFRE)


def passo_valido(segreto, testo, t=None, finestra=1):
    """Numero del passo di 30 secondi a cui corrisponde il codice (tollera 1 passo prima o dopo), oppure None."""
    testo = re.sub(r"\s", "", str(testo or ""))
    if not re.fullmatch(r"\d{%d}" % CIFRE, testo):
        return None
    ora = int((time.time() if t is None else t) // PASSO_S)
    for p in range(ora - finestra, ora + finestra + 1):
        if hmac.compare_digest(_codice_passo(segreto, p), testo):
            return p
    return None


def uri(segreto, username, emittente=EMITTENTE):
    from urllib.parse import quote
    return f"otpauth://totp/{quote(emittente)}:{quote(username)}?secret={segreto}&issuer={quote(emittente)}&digits={CIFRE}&period={PASSO_S}"


def qr_png(testo):
    """QR code (PNG) del testo, oppure None se la libreria segno non c'e'."""
    try:
        import segno
        buf = io.BytesIO()
        segno.make(testo, error="m").save(buf, kind="png", scale=5, border=2)
        return buf.getvalue()
    except Exception:
        return None


def raggruppa(segreto):
    return " ".join(segreto[i:i + 4] for i in range(0, len(segreto), 4))


# ----------------------------------------------------------------------------
# Cifratura del segreto nel database
# ----------------------------------------------------------------------------
def _fernet():
    k = (os.environ.get("DUEPASSAGGI_KEY") or os.environ.get("CHAT_KEY") or "").strip()
    if not k:
        try:
            import streamlit as st
            k = str(st.secrets.get("DUEPASSAGGI_KEY", "") or st.secrets.get("CHAT_KEY", "") or "").strip()
        except Exception:
            k = ""
    if not k:
        return None
    from cryptography.fernet import Fernet
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("2fa|" + k).encode("utf-8")).digest()))


def _cifra(s):
    f = _fernet()
    return "enc:" + f.encrypt(s.encode()).decode() if f else "pt:" + s


def _decifra(s):
    if str(s).startswith("pt:"):
        return s[3:]
    f = _fernet()
    if not f or not str(s).startswith("enc:"):
        raise ValueError("Segreto non leggibile: manca la chiave con cui era stato cifrato.")
    return f.decrypt(s[4:].encode()).decode()


# ----------------------------------------------------------------------------
# Stato per persona
# ----------------------------------------------------------------------------
def _carica(path=None):
    try:
        raw = storage.carica_pratica(NOME_CFG, path, modulo="cfg")
    except Exception:
        raw = None
    raw = raw if isinstance(raw, dict) else {}
    raw.setdefault("utenti", {})
    raw.setdefault("obbligatorio_admin", False)
    return raw


def _salva(cfg, autore="", path=None):
    storage.salva_pratica(NOME_CFG, cfg, path, autore=autore, modulo="cfg")


def _u(username):
    return str(username or "").strip().lower()


def attivo(username, path=None):
    return bool(_carica(path)["utenti"].get(_u(username), {}).get("segreto"))


def obbligatorio_admin(path=None):
    return bool(_carica(path)["obbligatorio_admin"])


def imposta_obbligatorio_admin(valore, autore="", path=None):
    cfg = _carica(path)
    cfg["obbligatorio_admin"] = bool(valore)
    _salva(cfg, autore, path)


def deve_configurare(utente, path=None):
    """True se la persona e' un amministratore, la regola e' attiva e non ha ancora configurato i due passaggi."""
    return bool(utente and utente.get("ruolo") == "admin" and obbligatorio_admin(path) and not attivo(utente["username"], path))


def _impronta(c):
    return hashlib.sha256(re.sub(r"[\s-]", "", str(c)).lower().encode()).hexdigest()


def attiva(username, segreto, testo, autore="", path=None):
    """Conferma la configurazione con un codice dell'app e la salva. Restituisce i codici di emergenza (si mostrano una volta sola)."""
    p = passo_valido(segreto, testo)
    if p is None:
        raise ValueError("Il codice non e' corretto: controlla l'ora del telefono e riprova.")
    emergenza = [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _ in range(N_CODICI)]
    cfg = _carica(path)
    cfg["utenti"][_u(username)] = {"segreto": _cifra(segreto), "recupero": [_impronta(c) for c in emergenza], "ultimo": p}
    _salva(cfg, autore or username, path)
    storage.log_evento(autore or username, "2fa_attivata", username, path)
    return emergenza


def verifica_login(username, testo, path=None):
    """Controlla il codice dell'app (una volta sola: lo stesso codice non vale due volte) oppure un codice di emergenza (si consuma).
    Restituisce 'app', 'emergenza' o None."""
    cfg = _carica(path)
    rec = cfg["utenti"].get(_u(username))
    if not rec:
        return None
    try:
        seg = _decifra(rec["segreto"])
    except ValueError:
        return None
    p = passo_valido(seg, testo)
    if p is not None and p > int(rec.get("ultimo", 0)):
        rec["ultimo"] = p
        _salva(cfg, username, path)
        return "app"
    imp = _impronta(testo)
    if imp in rec.get("recupero", []):
        rec["recupero"].remove(imp)
        _salva(cfg, username, path)
        storage.log_evento(username, "2fa_codice_emergenza", f"restano {len(rec['recupero'])}", path)
        return "emergenza"
    return None


def codici_emergenza_rimasti(username, path=None):
    return len(_carica(path)["utenti"].get(_u(username), {}).get("recupero", []))


def disattiva(username, autore="", path=None):
    """Toglie i due passaggi (per esempio quando una persona ha perso il telefono: lo fa l'amministratore)."""
    cfg = _carica(path)
    if cfg["utenti"].pop(_u(username), None) is not None:
        _salva(cfg, autore, path)
        storage.log_evento(autore, "2fa_disattivata", username, path)
        return True
    return False
