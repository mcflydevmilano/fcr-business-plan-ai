"""
posta.py - UNICO punto da cui la suite spedisce email (avvisi del Cruscotto, riepilogo del mattino, fascicoli allo studio, backup).

Regole, pensate per non far scattare il blocco del dominio («max defers and failures per hour»):
  - UN solo tentativo per invio: se fallisce ci si ferma, mai nuovi tentativi automatici.
  - Un solo messaggio per invio, con tutti i destinatari validi (niente un messaggio per destinatario).
  - Indirizzi controllati PRIMA di parlare col server: quelli non validi non vengono nemmeno inviati.
  - Timeout esplicito (10 secondi) e connessione sempre chiusa (with): SSL sulla 465, STARTTLS sulla 587.
  - Salvagente: dopo MAX_ERRORI_ORA errori nell'ultima ora (contati nel registro attivita') gli invii restano bloccati
    fino a quando non passa l'ora, cosi' un guasto non puo' trasformarsi in centinaia di tentativi falliti.
Impostazioni (Secrets o variabili d'ambiente): SMTP_HOST, SMTP_PORT (465 o 587), SMTP_USER, SMTP_PASSWORD, MAIL_FROM, MAIL_TO.
"""
import datetime as dt
import os
import re
import smtplib
import ssl
import time
from email.message import EmailMessage

import storage

INDIRIZZO_PREDEFINITO = "amministrazione@fcrgeneralcontractor.eu"
TIMEOUT = 10
MAX_ERRORI_ORA = 3
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-']+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")


class InvioBloccato(Exception):
    """Invio NON tentato: salvagente attivo o dati non validi. Nessuna connessione e' stata aperta."""


class InvioFallito(Exception):
    """Il server ha rifiutato o non ha risposto. L'invio e' stato interrotto e NON verra' ripetuto da solo."""


def indirizzo_valido(x):
    return bool(EMAIL_RE.match(str(x or "").strip()))


def mittente(env=None):
    env = env or os.environ
    m = (env.get("MAIL_FROM") or "").strip()
    if indirizzo_valido(m):
        return m
    u = (env.get("SMTP_USER") or "").strip()
    return u if indirizzo_valido(u) else INDIRIZZO_PREDEFINITO


def destinatari_predefiniti(env=None):
    env = env or os.environ
    lista = pulisci(str(env.get("MAIL_TO") or "").replace(";", ","))
    return lista or [INDIRIZZO_PREDEFINITO]


def pulisci(destinatari):
    """Lista di indirizzi validi, senza doppioni e senza spazi. Accetta una lista o una stringa separata da virgole."""
    if isinstance(destinatari, str):
        destinatari = destinatari.split(",")
    visti, out = set(), []
    for x in destinatari or []:
        x = str(x or "").strip()
        if x and indirizzo_valido(x) and x.lower() not in visti:
            visti.add(x.lower())
            out.append(x)
    return out


def smtp_pronto(env=None):
    env = env or os.environ
    return bool(env.get("SMTP_HOST") and env.get("SMTP_USER") and env.get("SMTP_PASSWORD"))


def errori_ultima_ora(path=None, adesso=None):
    """Quanti errori di invio sono nel registro nell'ultima ora (0 se il registro non e' leggibile)."""
    try:
        limite = (adesso or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)) - dt.timedelta(hours=1)
        n = 0
        for e in storage.elenca_eventi(limite=50, azione="email_errore", path=path):
            if dt.datetime.strptime(str(e["Data (UTC)"])[:19], "%Y-%m-%d %H:%M:%S") >= limite:
                n += 1
        return n
    except Exception:
        return 0


def _messaggio(destinatari, oggetto, corpo, allegati, html, env):
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = oggetto, mittente(env), ", ".join(destinatari)
    msg.set_content(corpo)
    if html:
        msg.add_alternative(html, subtype="html")
    for nome, dati, mime in allegati or ():
        tipo, sotto = mime.split("/", 1)
        msg.add_attachment(dati, maintype=tipo, subtype=sotto, filename=nome)
    return msg


def _spedisci(msg, env):
    """Una sola connessione, un solo tentativo, sempre chiusa. 465 = SSL, altre porte (587) = STARTTLS."""
    host, porta = env["SMTP_HOST"], int(env.get("SMTP_PORT", "587") or 587)
    contesto = ssl.create_default_context()
    if porta == 465:
        with smtplib.SMTP_SSL(host, porta, timeout=TIMEOUT, context=contesto) as s:
            s.login(env["SMTP_USER"], env["SMTP_PASSWORD"])
            return s.send_message(msg)
    with smtplib.SMTP(host, porta, timeout=TIMEOUT) as s:
        s.starttls(context=contesto)
        s.login(env["SMTP_USER"], env["SMTP_PASSWORD"])
        return s.send_message(msg)


def invia(destinatari, oggetto, corpo, allegati=(), html=None, env=None, path=None):
    """Spedisce UNA email. Restituisce la lista dei destinatari a cui e' stata consegnata al server.
    Solleva InvioBloccato (non tentato) o InvioFallito (tentato e fallito, nessun nuovo tentativo)."""
    env = env or os.environ
    if not smtp_pronto(env):
        raise InvioBloccato("La posta non è configurata: servono SMTP_HOST, SMTP_USER e SMTP_PASSWORD nei Secrets.")
    dest = pulisci(destinatari)
    if not dest:
        raise InvioBloccato("Nessun indirizzo email valido tra i destinatari: invio annullato.")
    if errori_ultima_ora(path) >= MAX_ERRORI_ORA:
        raise InvioBloccato(f"Invio bloccato per proteggere il dominio: ci sono già {MAX_ERRORI_ORA} errori di posta nell'ultima ora. "
                            "Controlla le impostazioni della posta e riprova tra un'ora.")
    msg = _messaggio(dest, oggetto, corpo, allegati, html, env)
    try:
        rifiutati = _spedisci(msg, env) or {}
    except smtplib.SMTPAuthenticationError as e:
        _registra("autenticazione rifiutata (utente o password errati)", path)
        raise InvioFallito("Il server ha rifiutato nome utente o password della posta. Invio interrotto, non verrà ripetuto.") from e
    except smtplib.SMTPRecipientsRefused as e:
        _registra(f"destinatari rifiutati: {', '.join(e.recipients)[:200]}", path)
        raise InvioFallito("Il server ha rifiutato tutti i destinatari. Invio interrotto, non verrà ripetuto.") from e
    except smtplib.SMTPException as e:
        _registra(f"errore SMTP {type(e).__name__}: {e}", path)
        raise InvioFallito("Errore del server di posta. Invio interrotto, non verrà ripetuto.") from e
    except Exception as e:                                          # rete assente, timeout, certificato, porta sbagliata...
        _registra(f"errore {type(e).__name__}: {e}", path)
        raise InvioFallito("Impossibile contattare il server di posta (rete, porta o timeout). Invio interrotto, non verrà ripetuto.") from e
    if rifiutati:                                                   # consegna parziale: e' un fallimento per il server, lo segnaliamo e contiamo
        _registra(f"destinatari rifiutati: {', '.join(rifiutati)[:200]}", path)
    ok = [d for d in dest if d not in rifiutati]
    return ok


def _registra(dettaglio, path=None):
    storage.log_evento("sistema", "email_errore", dettaglio, path)


def invia_con_feedback(destinatari, oggetto, corpo, allegati=(), html=None, env=None, path=None):
    """Per le schermate Streamlit: spedisce e mostra subito l'esito. Restituisce True se la posta e' partita."""
    import streamlit as st
    try:
        ok = invia(destinatari, oggetto, corpo, allegati, html, env, path)
    except InvioBloccato as e:
        st.warning(str(e))
        return False
    except InvioFallito as e:
        st.error(f"{e} L'invio è stato bloccato per non far scattare il blocco del dominio.")
        return False
    st.success("Email inviata a " + ", ".join(ok) + ".")
    return True
