"""ai.py - Chiamate a Gemini (google-genai) con ripiego su un alias in caso di modello non trovato."""
import importlib
import re
import time


class _Pigro:
    """Carica google-genai solo alla prima chiamata all'IA: all'avvio della suite risparmia mezzo secondo e non serve a chi non usa l'IA."""

    def __init__(self, nome):
        self._nome = nome
        self._mod = None

    def __getattr__(self, attr):
        if self._mod is None:
            self._mod = importlib.import_module(self._nome)
        return getattr(self._mod, attr)


genai = _Pigro("google.genai")
types = _Pigro("google.genai.types")


# secondi di attesa tra i tentativi quando il servizio e' sovraccarico (503/500/504): 3 tentativi per modello
ATTESE_RIPROVA = (2.0, 5.0)


def genera(api_key, contents, modello, fallback=(), json_mode=False, temperature=0.2, attese=None):
    """
    Restituisce (testo, modello_usato). Con errore 404/NOT_FOUND passa subito al modello di ripiego; con errori
    temporanei (503 UNAVAILABLE, 500, 504) riprova con una breve attesa e poi passa al modello di ripiego.
    Gli altri errori (es. 429 quota, chiave non valida) vengono sollevati subito.
    """
    attese = ATTESE_RIPROVA if attese is None else attese
    client = genai.Client(api_key=api_key)
    cfg = types.GenerateContentConfig(
        temperature=temperature,
        response_mime_type="application/json" if json_mode else "text/plain",
    )
    res, usato, last_err = None, modello, None
    for m in [modello] + [x for x in fallback if x != modello]:
        for tentativo in range(len(attese) + 1):
            try:
                res = client.models.generate_content(model=m, contents=contents, config=cfg)
                usato = m
                break
            except Exception as e:
                last_err = e
                if "404" in str(e) or "NOT_FOUND" in str(e):
                    break                              # modello inesistente: prova il successivo
                if not errore_sovraccarico(e):
                    raise
                if tentativo < len(attese):
                    time.sleep(attese[tentativo])
        if res is not None:
            break
    if res is None:
        raise last_err
    try:
        text = res.text
    except Exception:
        text = None
    if not text:
        raise RuntimeError("Risposta vuota o bloccata dal modello. Riprova.")
    return text, usato


def pulisci_testo(testo):
    """Rimuove il markdown residuo dal testo generato."""
    if not testo:
        return ""
    t = testo.replace("```", "").replace("`", "")
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.MULTILINE)
    t = t.replace("**", "").replace("__", "")
    return t.strip()


def errore_quota(e):
    """True se l'errore indica quota/limite di richieste esaurito (HTTP 429)."""
    t = str(e)
    return "429" in t or "RESOURCE_EXHAUSTED" in t


def errore_sovraccarico(e):
    """True per errori temporanei lato Google: 503 UNAVAILABLE (modello sovraccarico), 500 INTERNAL, 504 DEADLINE_EXCEEDED."""
    t = str(e)
    return any(x in t for x in ("503", "UNAVAILABLE", "500 INTERNAL", "504", "DEADLINE_EXCEEDED", "overloaded"))


def errore_temporaneo(e):
    """True se l'AI non e' utilizzabile ora ma l'app puo' continuare senza: quota esaurita o servizio sovraccarico."""
    return errore_quota(e) or errore_sovraccarico(e)


def messaggio_errore(e):
    """Messaggio comprensibile per l'utente."""
    if errore_quota(e):
        return ("⏳ La quota giornaliera gratuita di Gemini e' esaurita. Riprova piu' tardi (di solito entro 24 ore), "
                "inserisci un'altra chiave API nella barra laterale o attiva la fatturazione su Google AI Studio.")
    if errore_sovraccarico(e):
        return ("⏳ Il servizio AI di Google e' momentaneamente sovraccarico (errore 503): l'app ha gia' riprovato piu' volte. "
                "Non e' un problema dei tuoi dati: riprova tra qualche minuto. Nel frattempo puoi inserire i dati a mano.")
    return f"Errore del servizio AI: {e}"
