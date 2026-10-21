"""
firma.py - Foto e firma per i rapportini e le segnalazioni, pensate per il telefono.
Le foto vengono ridotte (lato massimo 1280 px, JPEG) prima del salvataggio, cosi' pesano poco. La firma si disegna con il dito.
Gli allegati stanno in un salvataggio a parte (strumento «al»), legati all'Id del rapportino: non appesantiscono i dati principali.
"""
import base64
import io
import time

import storage

NOME_ALLEGATI = "Rapportini"
MAX_FOTO = 6
LATO_MAX = 1280
QUALITA = 72


def riduci_foto(dati, lato=LATO_MAX, qualita=QUALITA):
    """Ridimensiona e ricomprime una foto (bytes) in JPEG. Corregge l'orientamento letto dall'EXIF (le foto del telefono)."""
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(dati)))
    im = im.convert("RGB")
    im.thumbnail((lato, lato))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=qualita, optimize=True)
    return buf.getvalue()


def a_b64(dati):
    return base64.b64encode(dati).decode("ascii")


def da_b64(testo):
    return base64.b64decode(testo.encode("ascii"))


def da_dataurl(url):
    """'data:image/png;base64,....' -> bytes PNG, oppure None se non valido."""
    if not isinstance(url, str) or not url.startswith("data:image/png;base64,"):
        return None
    try:
        dati = base64.b64decode(url.split(",", 1)[1])
    except Exception:
        return None
    return dati if dati[:8] == b"\x89PNG\r\n\x1a\n" and len(dati) < 400_000 else None


def firma_vuota(png):
    """True se la firma e' praticamente bianca/trasparente (nessun tratto)."""
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    a = im.getchannel("A")
    return a.getbbox() is None


def carica(path=None):
    try:
        return (storage.carica_pratica(NOME_ALLEGATI, path, modulo="al") or {}).get("allegati", {})
    except Exception:
        return {}


def aggiungi(id_, foto, firma_png, firmatario, utente, path=None):
    """Aggiunge foto (lista di bytes gia' ridotti) e/o firma (bytes PNG) all'Id indicato, fondendo con quanto salvato da altri telefoni."""
    if not foto and not firma_png:
        return True
    for _ in range(4):
        try:
            meta = storage.meta_pratica(NOME_ALLEGATI, path, modulo="al")
            db = (storage.carica_pratica(NOME_ALLEGATI, path, modulo="al") or {}) if meta else {}
            al = dict(db.get("allegati") or {})
            rec = dict(al.get(id_) or {"foto": [], "firma": None})
            rec["foto"] = (list(rec.get("foto") or []) + [{"jpg": a_b64(f), "quando": time.strftime("%Y-%m-%d %H:%M"), "da": utente} for f in foto])[:MAX_FOTO]
            if firma_png:
                rec["firma"] = {"png": a_b64(firma_png), "nome": firmatario, "quando": time.strftime("%Y-%m-%d %H:%M"), "da": utente}
            al[id_] = rec
            storage.salva_pratica(NOME_ALLEGATI, {"allegati": al}, path, autore=utente, modulo="al", atteso=meta["aggiornato"] if meta else "")
            return True
        except storage.ConflittoSalvataggio:
            continue
    return False


JS_PAD = """
export default function(component) {
  const { parentElement, setStateValue, data } = component;
  const root = parentElement;
  root.innerHTML = '';
  const wrap = document.createElement('div');
  wrap.style.cssText = 'font-family:inherit';
  const cv = document.createElement('canvas');
  const W = Math.min(root.clientWidth || 360, 560), H = 150;
  const dpr = window.devicePixelRatio || 1;
  cv.width = W * dpr; cv.height = H * dpr;
  cv.style.cssText = 'width:' + W + 'px;height:' + H + 'px;border:2px dashed #94a3b8;border-radius:12px;background:#fff;touch-action:none;display:block';
  const ctx = cv.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.lineWidth = 2.4; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.strokeStyle = '#0f172a';
  let down = false, sporco = false;
  const pos = e => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  cv.addEventListener('pointerdown', e => { down = true; cv.setPointerCapture(e.pointerId); const [x, y] = pos(e); ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + 0.1, y + 0.1); ctx.stroke(); sporco = true; e.preventDefault(); });
  cv.addEventListener('pointermove', e => { if (!down) return; const [x, y] = pos(e); ctx.lineTo(x, y); ctx.stroke(); e.preventDefault(); });
  const fine = () => { down = false; };
  cv.addEventListener('pointerup', fine); cv.addEventListener('pointercancel', fine);
  const barra = document.createElement('div');
  barra.style.cssText = 'display:flex;gap:8px;margin-top:8px;align-items:center;flex-wrap:wrap';
  const mk = (t, bg, fg) => { const b = document.createElement('button'); b.type = 'button'; b.textContent = t;
    b.style.cssText = 'padding:10px 16px;border-radius:10px;border:1px solid #cbd5e1;background:' + bg + ';color:' + fg + ';font-size:15px;font-weight:600;cursor:pointer'; return b; };
  const ok = mk('✍️ Conferma la firma', '#0b4f9c', '#ffffff'), no = mk('Cancella', '#f1f5f9', '#0f172a');
  const msg = document.createElement('span'); msg.style.cssText = 'font-size:13px;color:#475569';
  no.onclick = () => { ctx.clearRect(0, 0, W, H); sporco = false; msg.textContent = ''; setStateValue('firma', ''); };
  ok.onclick = () => { if (!sporco) { msg.textContent = 'Disegna prima la firma con il dito.'; return; } setStateValue('firma', cv.toDataURL('image/png')); msg.textContent = '✓ Firma acquisita'; };
  barra.append(ok, no, msg);
  wrap.append(cv, barra);
  root.append(wrap);
}
"""


def pad(key):
    """Disegno della firma con il dito. Restituisce i bytes PNG confermati oppure None. Se il componente non e' disponibile restituisce None."""
    try:
        import streamlit as st
        comp = st.components.v2.component("fcr_firma_pad", js=JS_PAD)
        res = comp(key=key, on_firma_change=lambda: None)
        return da_dataurl(getattr(res, "firma", "") or "")
    except Exception:
        return None
