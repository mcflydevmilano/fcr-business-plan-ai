"""
video.py - Video corsi: ogni strumento (e ogni passo dei Primi passi) puo' avere un video, mostrato come pulsante «🎬 Guarda il video».
I link si incollano in Amministrazione → «🎬 Video» (YouTube «non in elenco», Vimeo, ecc.). Senza link il pulsante non compare.
Chiavi: la sigla dello strumento (es. "ru") oppure "pp_<id>" per un passo dei Primi passi (se manca, vale il video del suo primo strumento).
"""
import storage

NOME = "video_corsi"


def url_valido(u):
    u = str(u or "").strip()
    return u if u.lower().startswith("https://") and " " not in u and len(u) < 500 else ""


def normalizza(raw):
    out = {}
    for k, v in ((raw or {}).get("video") or {}).items():
        v = url_valido(v)
        if v:
            out[str(k)] = v
    return out


def carica(path=None):
    try:
        raw = storage.cache_lettura("video_corsi_cfg", lambda: storage.carica_pratica(NOME, path, modulo="cfg"), path, ttl=20)
    except Exception:
        raw = None
    return normalizza(raw)


def salva(video, autore="", path=None):
    video = normalizza({"video": video})
    storage.salva_pratica(NOME, {"video": video}, path, autore=autore, modulo="cfg")
    return video


def link(chiave, sigle_di_riserva=(), path=None):
    """Indirizzo del video per la chiave, oppure per il primo strumento di riserva che ne ha uno; '' se non c'e'."""
    v = carica(path)
    for k in (chiave, *sigle_di_riserva):
        if k in v:
            return v[k]
    return ""


def pulsante(chiave, sigle_di_riserva=(), key=None, **kw):
    import streamlit as st
    u = link(chiave, sigle_di_riserva)
    if u:
        st.link_button("🎬 Guarda il video", u, key=key, help="Un breve video che spiega questo passo", **kw)
