"""pc.py - Portale cliente: una pagina pubblica, raggiungibile solo da un link segreto, con stato lavori, foto, documenti e accettazione dell'offerta.
Sicurezza: il link (192 bit casuali) non viene salvato, solo la sua impronta SHA-256; scade, si revoca, la pagina mostra solo cio' che e' stato scelto qui."""
import base64
import datetime as dt
import hashlib
import hmac
import re
import secrets
import uuid

import storage

NOME_INDICE = "portale_cliente"
PREFISSO_CONTENUTO = "portale_c_"
GIORNI_BASE = 30
GIORNI_MAX = 180
MAX_FOTO = 6
MAX_DOC = 3
MAX_PASSI = 8
RE_TOKEN = re.compile(r"^[A-Za-z0-9_-]{20,64}$")
MSG_NON_VALIDO = "Questo link non è valido o è scaduto. Chiedi un nuovo link a chi te lo ha mandato."


def hash_token(token):
    return hashlib.sha256(str(token).encode()).hexdigest()


def link(token, base="https://suite.piattaformafcr.it"):
    return f"{base.rstrip('/')}/?cliente={token}"


def _carica_indice(path=None):
    try:
        raw = storage.carica_pratica(NOME_INDICE, path, modulo="cfg")
    except Exception:
        raw = None
    return [x for x in ((raw or {}).get("link") if isinstance(raw, dict) else None) or [] if isinstance(x, dict) and x.get("id") and x.get("hash")]


def _salva_indice(el, autore="", path=None):
    storage.salva_pratica(NOME_INDICE, {"link": el}, path, autore=autore, modulo="cfg")
    storage.svuota_cache()


def elenca(path=None, oggi=None):
    oggi = oggi or dt.date.today()
    out = []
    for x in _carica_indice(path):
        out.append(dict({k: v for k, v in x.items() if k != "hash"}, stato=stato(x, oggi)))
    return out


def stato(entry, oggi=None):
    oggi = oggi or dt.date.today()
    if entry.get("revocato"):
        return "revocato"
    try:
        if dt.date.fromisoformat(entry.get("scade", "")) < oggi:
            return "scaduto"
    except ValueError:
        return "scaduto"
    return "attivo"


def crea(nome, cantiere="", giorni=GIORNI_BASE, autore="", path=None, oggi=None):
    """Crea un link. Restituisce (token, id): il token si vede solo ora."""
    oggi = oggi or dt.date.today()
    giorni = max(1, min(int(giorni), GIORNI_MAX))
    token = secrets.token_urlsafe(24)
    id_ = uuid.uuid4().hex[:10]
    el = _carica_indice(path)
    el.append({"id": id_, "hash": hash_token(token), "nome": str(nome or "").strip()[:80] or "Cliente", "cantiere": str(cantiere or "")[:60], "creato": oggi.isoformat(),
               "scade": (oggi + dt.timedelta(days=giorni)).isoformat(), "revocato": False, "accettata": False, "autore": autore})
    _salva_indice(el, autore, path)
    return token, id_


def trova(token, path=None, oggi=None):
    """(entry o None, stato). Per chi guarda da fuori 'non trovato', 'scaduto' e 'revocato' sono uguali."""
    if not isinstance(token, str) or not RE_TOKEN.match(token):
        return None, "non_valido"
    h = hash_token(token)
    trovato = None
    for x in _carica_indice(path):
        if hmac.compare_digest(x["hash"], h):
            trovato = x
    if not trovato:
        return None, "non_valido"
    s = stato(trovato, oggi)
    return (trovato if s == "attivo" else None), (s if s != "attivo" else "attivo")


def _modifica(id_, f, autore="", path=None):
    el = _carica_indice(path)
    ok = False
    for x in el:
        if x["id"] == id_:
            f(x)
            ok = True
    if ok:
        _salva_indice(el, autore, path)
    return ok


def revoca(id_, autore="", path=None):
    return _modifica(id_, lambda x: x.update(revocato=True), autore, path)


def proroga(id_, giorni, autore="", path=None, oggi=None):
    oggi = oggi or dt.date.today()
    giorni = max(1, min(int(giorni), GIORNI_MAX))
    return _modifica(id_, lambda x: x.update(scade=(oggi + dt.timedelta(days=giorni)).isoformat(), revocato=False), autore, path)


def contenuto_vuoto():
    return {"saluto": "", "stato_testo": "", "avanzamento": 0, "passi": [], "foto": [], "documenti": [],
            "offerta": {"attiva": False, "titolo": "", "importo": 0.0, "descrizione": ""}, "accettazione": None}


def _s(v, n):
    return str(v or "").strip()[:n]


def normalizza_contenuto(c):
    c = c if isinstance(c, dict) else {}
    o = c.get("offerta") if isinstance(c.get("offerta"), dict) else {}
    try:
        imp = max(0.0, float(o.get("importo") or 0))
    except (TypeError, ValueError):
        imp = 0.0
    try:
        av = max(0, min(100, int(float(c.get("avanzamento") or 0))))
    except (TypeError, ValueError):
        av = 0
    foto = [{"nome": _s(f.get("nome"), 80), "tipo": "image/jpeg" if str(f.get("tipo", "")).startswith("image/") else "", "dati": f.get("dati") or "", "didascalia": _s(f.get("didascalia"), 120)}
            for f in (c.get("foto") or []) if isinstance(f, dict) and f.get("dati") and str(f.get("tipo", "")).startswith("image/")][:MAX_FOTO]
    doc = [{"nome": _s(d.get("nome"), 80), "tipo": "application/pdf", "dati": d.get("dati") or ""}
           for d in (c.get("documenti") or []) if isinstance(d, dict) and d.get("dati") and d.get("tipo") == "application/pdf"][:MAX_DOC]
    acc = c.get("accettazione") if isinstance(c.get("accettazione"), dict) else None
    return {"saluto": _s(c.get("saluto"), 300), "stato_testo": _s(c.get("stato_testo"), 2000), "avanzamento": av,
            "passi": [_s(p, 200) for p in (c.get("passi") or []) if _s(p, 200)][:MAX_PASSI], "foto": foto, "documenti": doc,
            "offerta": {"attiva": bool(o.get("attiva")), "titolo": _s(o.get("titolo"), 120), "importo": imp, "descrizione": _s(o.get("descrizione"), 3000)}, "accettazione": acc}


def carica_contenuto(id_, path=None):
    try:
        raw = storage.carica_pratica(PREFISSO_CONTENUTO + str(id_), path, modulo="cfg")
    except Exception:
        raw = None
    return normalizza_contenuto(raw)


def salva_contenuto(id_, c, autore="", path=None):
    """Non permette di toccare l'accettazione gia' registrata."""
    vecchio = carica_contenuto(id_, path)
    n = normalizza_contenuto(c)
    n["accettazione"] = vecchio["accettazione"]
    if vecchio["accettazione"]:
        n["offerta"] = vecchio["offerta"]            # l'offerta accettata non si cambia sotto gli occhi del cliente
    storage.salva_pratica(PREFISSO_CONTENUTO + str(id_), n, path, autore=autore, modulo="cfg")
    storage.svuota_cache()


def accetta(token, nome, firma_png, path=None, oggi=None):
    """Registra l'accettazione. (True, '') oppure (False, motivo). Una volta sola, solo con link valido e offerta attiva."""
    entry, s = trova(token, path, oggi)
    if not entry:
        return False, MSG_NON_VALIDO
    c = carica_contenuto(entry["id"], path)
    if not c["offerta"]["attiva"]:
        return False, "Non c'è nessuna offerta da accettare."
    if c["accettazione"]:
        return False, "L'offerta risulta già accettata."
    nome = _s(nome, 80)
    if len(nome) < 3:
        return False, "Scrivi nome e cognome."
    if not firma_png:
        return False, "Disegna la firma."
    c["accettazione"] = {"data": dt.datetime.now().isoformat(timespec="seconds"), "nome": nome, "importo": c["offerta"]["importo"], "titolo": c["offerta"]["titolo"],
                         "firma": base64.b64encode(firma_png).decode("ascii")}
    storage.salva_pratica(PREFISSO_CONTENUTO + entry["id"], c, path, autore="cliente", modulo="cfg")
    _modifica(entry["id"], lambda x: x.update(accettata=True), "cliente", path)
    storage.svuota_cache()
    return True, ""
