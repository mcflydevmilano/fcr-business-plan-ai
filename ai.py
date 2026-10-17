"""ai.py - Chiamate a Gemini (google-genai) con ripiego su un alias in caso di modello non trovato."""
import re

from google import genai
from google.genai import types


def genera(api_key, contents, modello, fallback=(), json_mode=False, temperature=0.2):
    """Restituisce (testo, modello_usato). Ripiega sui `fallback` solo in caso di errore 404/NOT_FOUND."""
    client = genai.Client(api_key=api_key)
    cfg = types.GenerateContentConfig(
        temperature=temperature,
        response_mime_type="application/json" if json_mode else "text/plain",
    )
    res, usato, last_err = None, modello, None
    for m in [modello] + [x for x in fallback if x != modello]:
        try:
            res = client.models.generate_content(model=m, contents=contents, config=cfg)
            usato = m
            break
        except Exception as e:
            last_err = e
            if "404" not in str(e) and "NOT_FOUND" not in str(e):
                raise
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
