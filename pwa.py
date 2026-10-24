"""
pwa.py - Rende la suite installabile sul telefono (icona nella schermata Home, schermo intero) e mostra le istruzioni.
Il manifesto e le icone sono generati al volo: non servono file aggiuntivi sul server.
Su Android (Chrome) compare anche il pulsante «Installa»; su iPhone si usa Condividi -> Aggiungi alla schermata Home.
"""
import base64
import functools
import io
import os

import streamlit as st

import core

_JS_INIETTA = """
export default function(component) {
  const { data } = component;
  const d = document;
  const rimpiazza = (sel, el) => { d.head.querySelectorAll(sel).forEach(n => n.remove()); d.head.appendChild(el); };
  const link = (rel, href, extra) => { const l = d.createElement('link'); l.rel = rel; l.href = href; Object.assign(l, extra || {}); return l; };
  const meta = (name, content) => { const m = d.createElement('meta'); m.name = name; m.content = content; return m; };
  const icona = n => 'data:image/png;base64,' + data['i' + n];
  const man = { name: 'FCR General Contractor - Suite', short_name: 'FCR Suite', description: 'Strumenti di gestione di FCR General Contractor', lang: 'it',
    start_url: location.origin + '/', scope: location.origin + '/', display: 'standalone', background_color: '#f8fafc', theme_color: '#0b4f9c',
    icons: [{ src: icona(192), sizes: '192x192', type: 'image/png', purpose: 'any' }, { src: icona(512), sizes: '512x512', type: 'image/png', purpose: 'any' }] };
  const url = URL.createObjectURL(new Blob([JSON.stringify(man)], { type: 'application/manifest+json' }));
  rimpiazza('link[rel="manifest"]', link('manifest', url));
  rimpiazza('link[rel="icon"], link[rel="shortcut icon"]', link('icon', icona(192), { type: 'image/png' }));
  rimpiazza('link[rel="apple-touch-icon"]', link('apple-touch-icon', icona(180)));
  rimpiazza('meta[name="theme-color"]', meta('theme-color', '#0b4f9c'));
  rimpiazza('meta[name="apple-mobile-web-app-capable"]', meta('apple-mobile-web-app-capable', 'yes'));
  rimpiazza('meta[name="mobile-web-app-capable"]', meta('mobile-web-app-capable', 'yes'));
  rimpiazza('meta[name="apple-mobile-web-app-title"]', meta('apple-mobile-web-app-title', 'FCR Suite'));
  if (!window.__fcrPwa) {
    window.__fcrPwa = true;
    window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); window.__fcrInstallEv = e; });
  }
}
"""

_JS_PULSANTE = """
export default function(component) {
  const { parentElement } = component;
  parentElement.innerHTML = '';
  const b = document.createElement('button');
  b.type = 'button';
  b.textContent = '📲 Installa l\\'app';
  b.style.cssText = 'width:100%;padding:11px 14px;border-radius:10px;border:0;background:#0b4f9c;color:#fff;font-size:15px;font-weight:700;cursor:pointer';
  const m = document.createElement('div');
  m.style.cssText = 'font-size:12.5px;color:#475569;margin-top:6px';
  b.onclick = async () => {
    const ev = window.__fcrInstallEv;
    if (!ev) { m.textContent = 'Il telefono non propone l\\'installazione da qui: usa le istruzioni qui sopra (menu del browser → Installa app / Aggiungi a Home).'; return; }
    ev.prompt(); await ev.userChoice; window.__fcrInstallEv = null;
  };
  parentElement.append(b, m);
}
"""


@st.cache_resource(show_spinner=False)
def icona_scheda():
    """Immagine per la linguetta del browser: logo FCR su fondo bianco (il PNG originale e' trasparente e sparisce)."""
    from PIL import Image
    try:
        logo = Image.open(core.LOGO_FCR_PATH).convert("RGBA")
        base = Image.new("RGBA", (128, 128), (255, 255, 255, 255))
        logo.thumbnail((116, 116))
        base.alpha_composite(logo, ((128 - logo.width) // 2, (128 - logo.height) // 2))
        return base.convert("RGB")
    except Exception:
        return "📊"


@functools.lru_cache(maxsize=1)
def _icone():
    """Icone PNG in base64: logo FCR centrato su fondo blu, nei tre formati richiesti."""
    from PIL import Image
    out = {}
    logo = None
    try:
        if core.LOGO_FCR_PATH and os.path.exists(core.LOGO_FCR_PATH):
            logo = Image.open(core.LOGO_FCR_PATH).convert("RGBA")
    except Exception:
        logo = None
    for n in (180, 192, 512):
        base = Image.new("RGBA", (n, n), (255, 255, 255, 255))
        if logo is not None:
            l = logo.copy()
            l.thumbnail((int(n * 0.78), int(n * 0.78)))
            base.alpha_composite(l, ((n - l.width) // 2, (n - l.height) // 2))
        buf = io.BytesIO()
        base.convert("RGB").save(buf, "PNG", optimize=True)
        out[f"i{n}"] = base64.b64encode(buf.getvalue()).decode("ascii")
    return out


def inietta():
    """Da chiamare una volta all'avvio di ogni esecuzione: aggiunge manifesto e meta tag alla pagina. Non mostra nulla."""
    try:
        comp = st.components.v2.component("fcr_pwa_head", js=_JS_INIETTA)
        comp(data=_icone(), key="fcr_pwa_head_c")
    except Exception:
        pass                                           # versioni di Streamlit senza componenti v2: l'app funziona lo stesso


def pannello():
    """Riquadro «Installa l'app sul telefono» per la barra laterale."""
    with st.expander("📲 Installa l'app sul telefono"):
        st.markdown(
            "**Android (Chrome):** menu ⋮ in alto a destra → **Installa app** (o «Aggiungi a schermata Home»).  \n"
            "**iPhone (Safari):** tasto Condividi ⬆︎ → **Aggiungi alla schermata Home**.  \n"
            "Si apre a schermo intero come un'app, con l'icona FCR. Serve comunque la connessione e il login.")
        try:
            st.components.v2.component("fcr_pwa_btn", js=_JS_PULSANTE)(key="fcr_pwa_btn_c")
        except Exception:
            pass
