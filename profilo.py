"""
profilo.py - Foto profilo degli utenti (la «fotina» nella barra laterale).
La foto viene ritagliata al centro in un quadrato di 256 px e salvata in JPEG: pesa pochi KB.
Stanno tutte in un unico salvataggio (strumento «al», nome «Profili»), uno per utente; ognuno modifica solo la propria.
"""
import base64
import io
import time

import storage

NOME = "Profili"
LATO = 256
MAX_BYTE = 8_000_000


def riduci(dati, lato=LATO):
    """Foto qualsiasi -> quadrato centrato lato x lato in JPEG (corregge l'orientamento del telefono)."""
    from PIL import Image, ImageOps
    if len(dati) > MAX_BYTE:
        raise ValueError("La foto è troppo grande (massimo 8 MB).")
    try:
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(dati)))
    except Exception:
        raise ValueError("Il file non è una foto valida (usa JPG, PNG o WEBP).")
    im = ImageOps.fit(im.convert("RGB"), (lato, lato), method=Image.LANCZOS, centering=(0.5, 0.4))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82, optimize=True)
    return buf.getvalue()


def _tutte(path=None):
    try:
        return (storage.carica_pratica(NOME, path, modulo="al") or {}).get("foto", {})
    except Exception:
        return {}


def foto_di(username, path=None):
    """Foto in base64 (JPEG) oppure None."""
    rec = _tutte(path).get(str(username).strip().lower())
    return rec.get("jpg") if rec else None


def _scrivi(username, rec, path=None):
    u = str(username).strip().lower()
    for _ in range(4):
        try:
            meta = storage.meta_pratica(NOME, path, modulo="al")
            db = (storage.carica_pratica(NOME, path, modulo="al") or {}) if meta else {}
            foto = dict(db.get("foto") or {})
            if rec is None:
                foto.pop(u, None)
            else:
                foto[u] = rec
            storage.salva_pratica(NOME, {"foto": foto}, path, autore=u, modulo="al", atteso=meta["aggiornato"] if meta else "")
            return True
        except storage.ConflittoSalvataggio:
            continue
    return False


def imposta(username, dati, path=None):
    """Salva la foto (bytes grezzi): la riduce e la scrive. Solleva ValueError se non e' una foto valida."""
    jpg = riduci(dati)
    if not _scrivi(username, {"jpg": base64.b64encode(jpg).decode("ascii"), "quando": time.strftime("%Y-%m-%d %H:%M")}, path):
        raise RuntimeError("Salvataggio non riuscito: riprova.")


def rimuovi(username, path=None):
    return _scrivi(username, None, path)
