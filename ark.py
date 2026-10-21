"""
ark.py - «Mattoncini FCR»: un breakout (palla, trave e muro di mattoni) per la pausa, con classifica dei colleghi.
Il gioco gira nel browser; a fine partita invia il punteggio e qui si tiene il migliore di ogni persona.
E' uno svago: la classifica non e' a prova di imbroglio, ma i valori impossibili vengono scartati.
Salvataggio: strumento «al», nome «Arkanoid» (una sola riga per utente, pesa pochissimo).
"""
import html
import time

import storage

NOME = "Arkanoid"
MAX_PUNTI = 60_000


def _carica(path=None):
    try:
        return (storage.carica_pratica(NOME, path, modulo="al") or {}).get("punteggi", {})
    except Exception:
        return {}


def registra(username, punti, path=None):
    """Salva il punteggio se e' il migliore della persona. Restituisce 'record', 'partita' (non migliora) o 'scartato'."""
    try:
        punti = int(punti)
    except (TypeError, ValueError):
        return "scartato"
    u = str(username or "").strip().lower()
    if not u or punti <= 0 or punti > MAX_PUNTI:
        return "scartato"
    for _ in range(4):
        try:
            meta = storage.meta_pratica(NOME, path, modulo="al")
            db = (storage.carica_pratica(NOME, path, modulo="al") or {}) if meta else {}
            pun = dict(db.get("punteggi") or {})
            rec = dict(pun.get(u) or {"best": 0, "partite": 0})
            rec["partite"] = int(rec.get("partite", 0)) + 1
            esito = "partita"
            if punti > int(rec.get("best", 0)):
                rec["best"], rec["quando"], esito = punti, time.strftime("%Y-%m-%d"), "record"
            pun[u] = rec
            storage.salva_pratica(NOME, {"punteggi": pun}, path, autore=u, modulo="al", atteso=meta["aggiornato"] if meta else "")
            return esito
        except storage.ConflittoSalvataggio:
            continue
    return "scartato"


def classifica(n=10, path=None):
    """[(posizione, utente, record, partite, data)] in ordine decrescente di record."""
    righe = sorted(((u, int(r.get("best", 0)), int(r.get("partite", 0)), r.get("quando", "")) for u, r in _carica(path).items() if r.get("best")),
                   key=lambda x: (-x[1], x[0]))
    return [(i + 1, u, b, p, d) for i, (u, b, p, d) in enumerate(righe[:n])]


def classifica_html(utente="", n=10, path=None):
    righe = classifica(n, path)
    if not righe:
        return "<div style='color:#64748b;padding:6px 0'>Nessun punteggio ancora: sii il primo! 🏆</div>"
    medaglie = {1: "🥇", 2: "🥈", 3: "🥉"}
    out = []
    mio = str(utente or "").strip().lower()
    for pos, u, best, partite, data in righe:
        stile = "background:#eff6ff;border:1px solid #bfdbfe;" if u == mio else "border:1px solid #e2e8f0;"
        out.append(f"<div style='display:flex;align-items:center;gap:10px;{stile}border-radius:10px;padding:7px 12px;margin:5px 0;background-clip:padding-box'>"
                   f"<span style='width:30px;font-size:1.15rem;text-align:center'>{medaglie.get(pos, str(pos))}</span>"
                   f"<b style='flex:1;color:#0f172a'>{html.escape(u.title())}{' (tu)' if u == mio else ''}</b>"
                   f"<span style='color:#64748b;font-size:.78rem'>{partite} partit{'a' if partite == 1 else 'e'}</span>"
                   f"<b style='color:#1e3fae;min-width:64px;text-align:right'>{best}</b></div>")
    return "".join(out)


JS_GIOCO = r"""
export default function(component) {
  const { parentElement, setStateValue } = component;
  const root = parentElement; root.innerHTML = '';
  const W = 400, H = 520, dpr = window.devicePixelRatio || 1;
  const wrap = document.createElement('div'); wrap.style.cssText = 'display:flex;justify-content:center';
  const cv = document.createElement('canvas');
  cv.width = W * dpr; cv.height = H * dpr;
  cv.style.cssText = 'width:min(100%,400px);aspect-ratio:400/520;border-radius:16px;touch-action:none;display:block;box-shadow:0 10px 28px rgba(15,23,42,.3);cursor:none;background:#0a1640';
  wrap.append(cv); root.append(wrap);
  const g = cv.getContext('2d'); g.scale(dpr, dpr);

  const COLORI = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#38bdf8', '#818cf8'];
  const COLS = 8, MX = 12, BW = (W - 2 * MX) / COLS, BH = 20, TOP = 64;
  const S = { stato: 'pronto', punti: 0, vite: 3, liv: 1, msg: '', msgT: 0, mattoni: [], px: W / 2, pw: 78, palla: { x: W / 2, y: H - 46, vx: 0, vy: 0 }, inviato: false };
  const PY = H - 34, PH = 12, R = 6;

  function costruisci() {
    S.mattoni = [];
    const righe = Math.min(4 + S.liv, 8);
    for (let r = 0; r < righe; r++) for (let c = 0; c < COLS; c++) {
      const duro = S.liv >= 2 && r < Math.min(S.liv - 1, 3);
      S.mattoni.push({ x: MX + c * BW, y: TOP + r * (BH + 4), vivo: true, col: COLORI[r % COLORI.length], colpi: duro ? 2 : 1, max: duro ? 2 : 1, val: (righe - r) * 10 });
    }
  }
  function attacca() { S.palla.x = S.px; S.palla.y = PY - R - 1; S.palla.vx = S.palla.vy = 0; S.stato = 'pronto'; }
  function avvia() { S.punti = 0; S.vite = 3; S.liv = 1; S.inviato = false; costruisci(); attacca(); messaggio('Livello 1 · Si parte! 🏗️'); }
  function messaggio(t) { S.msg = t; S.msgT = 150; }
  function lancia() {
    if (S.stato === 'pronto') { const v = 4.1 + (S.liv - 1) * 0.45; const a = (Math.random() * 0.6 - 0.3); S.palla.vx = v * Math.sin(a); S.palla.vy = -v * Math.cos(a); S.stato = 'gioco'; }
    else if (S.stato === 'fine') avvia();
  }
  const frasi = ['Livello %L · Il cantiere si complica! 🚧', 'Livello %L · Attenzione ai mattoni duri! 🧱', 'Livello %L · Sei una macchina! 🚜', 'Livello %L · Capocantiere in arrivo! 👷'];

  let mouseUsato = false;
  const xDa = e => { const r = cv.getBoundingClientRect(); return (e.clientX - r.left) * (W / r.width); };
  cv.addEventListener('pointermove', e => { S.px = Math.max(S.pw / 2, Math.min(W - S.pw / 2, xDa(e))); mouseUsato = true; });
  cv.addEventListener('pointerdown', e => { S.px = Math.max(S.pw / 2, Math.min(W - S.pw / 2, xDa(e))); lancia(); e.preventDefault(); });
  const tasti = {};
  const kd = e => { if (['ArrowLeft', 'ArrowRight', ' ', 'a', 'd'].includes(e.key)) { e.preventDefault(); tasti[e.key] = true; if (e.key === ' ') lancia(); } };
  const ku = e => { tasti[e.key] = false; };
  window.addEventListener('keydown', kd); window.addEventListener('keyup', ku);

  function aggiorna(k) {
    const v = 6 * k;
    if (tasti['ArrowLeft'] || tasti['a']) S.px -= v; if (tasti['ArrowRight'] || tasti['d']) S.px += v;
    S.px = Math.max(S.pw / 2, Math.min(W - S.pw / 2, S.px));
    const b = S.palla;
    if (S.stato === 'pronto') { b.x = S.px; b.y = PY - R - 1; return; }
    if (S.stato !== 'gioco') return;
    b.x += b.vx * k; b.y += b.vy * k;
    if (b.x < R) { b.x = R; b.vx = Math.abs(b.vx); } if (b.x > W - R) { b.x = W - R; b.vx = -Math.abs(b.vx); }
    if (b.y < R) { b.y = R; b.vy = Math.abs(b.vy); }
    if (b.vy > 0 && b.y + R >= PY && b.y + R <= PY + PH + 6 && b.x >= S.px - S.pw / 2 - R && b.x <= S.px + S.pw / 2 + R) {
      const t = (b.x - S.px) / (S.pw / 2), vel = Math.hypot(b.vx, b.vy), ang = t * 1.05;
      b.vx = vel * Math.sin(ang); b.vy = -vel * Math.cos(ang); b.y = PY - R;
    }
    for (const m of S.mattoni) {
      if (!m.vivo) continue;
      if (b.x + R > m.x && b.x - R < m.x + BW - 2 && b.y + R > m.y && b.y - R < m.y + BH) {
        const dx = Math.min(b.x + R - m.x, m.x + BW - 2 - (b.x - R)), dy = Math.min(b.y + R - m.y, m.y + BH - (b.y - R));
        if (dx < dy) b.vx = -b.vx; else b.vy = -b.vy;
        m.colpi--; S.punti += m.val;
        if (m.colpi <= 0) m.vivo = false;
        const vel = Math.hypot(b.vx, b.vy), nv = Math.min(vel * 1.004, 9.5); b.vx *= nv / vel; b.vy *= nv / vel;
        break;
      }
    }
    if (!S.mattoni.some(m => m.vivo)) { S.punti += 100 * S.liv; S.liv++; costruisci(); attacca(); messaggio(frasi[(S.liv - 2) % frasi.length].replace('%L', S.liv)); }
    if (b.y - R > H) {
      S.vite--;
      if (S.vite <= 0) { S.stato = 'fine'; if (!S.inviato) { S.inviato = true; setStateValue('punteggio', { p: S.punti, n: Date.now() }); } }
      else { attacca(); messaggio('Persa! Restano ' + S.vite + ' vite ❤️'); }
    }
  }

  function rr(x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
  function testo(t, x, y, s, col, al) { g.font = '700 ' + s + 'px Inter, system-ui, sans-serif'; g.fillStyle = col; g.textAlign = al || 'center'; g.fillText(t, x, y); }

  function disegna() {
    const sf = g.createLinearGradient(0, 0, 0, H); sf.addColorStop(0, '#0a1640'); sf.addColorStop(1, '#1e3fae'); g.fillStyle = sf; g.fillRect(0, 0, W, H);
    g.strokeStyle = 'rgba(255,255,255,.05)'; g.lineWidth = 1;
    for (let x = 0; x < W; x += 25) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, H); g.stroke(); }
    for (let y = 0; y < H; y += 25) { g.beginPath(); g.moveTo(0, y); g.lineTo(W, y); g.stroke(); }
    testo('PUNTI ' + S.punti, 14, 26, 15, '#fff', 'left'); testo('LIV ' + S.liv, W / 2, 26, 15, '#fdba74');
    testo('❤'.repeat(Math.max(S.vite, 0)), W - 14, 26, 15, '#f87171', 'right');
    for (const m of S.mattoni) {
      if (!m.vivo) continue;
      g.globalAlpha = m.colpi < m.max ? .6 : 1; g.fillStyle = m.col; rr(m.x + 1, m.y, BW - 2, BH, 4); g.fill();
      g.fillStyle = 'rgba(255,255,255,.28)'; rr(m.x + 3, m.y + 2, BW - 6, 5, 2); g.fill();
      if (m.max > 1) { g.strokeStyle = 'rgba(15,23,42,.7)'; g.lineWidth = 2; rr(m.x + 1, m.y, BW - 2, BH, 4); g.stroke(); }
      g.globalAlpha = 1;
    }
    const pg = g.createLinearGradient(0, PY, 0, PY + PH); pg.addColorStop(0, '#93c5fd'); pg.addColorStop(1, '#1e40af');
    g.fillStyle = pg; rr(S.px - S.pw / 2, PY, S.pw, PH, 6); g.fill();
    g.fillStyle = '#16a34a'; rr(S.px - S.pw / 2, PY, 10, PH, 5); g.fill(); g.fillStyle = '#ef4444'; rr(S.px + S.pw / 2 - 10, PY, 10, PH, 5); g.fill();
    g.fillStyle = '#fff'; g.beginPath(); g.arc(S.palla.x, S.palla.y, R, 0, 7); g.fill();
    g.fillStyle = '#f97316'; g.beginPath(); g.arc(S.palla.x - 1.5, S.palla.y - 1.5, R / 2.4, 0, 7); g.fill();
    if (S.msgT > 0 && S.stato !== 'fine') { g.globalAlpha = Math.min(1, S.msgT / 40); testo(S.msg, W / 2, H / 2 + 40, 17, '#fff'); g.globalAlpha = 1; }
    if (S.stato === 'pronto' && S.msgT < 100) testo(mouseUsato ? 'Clicca o premi SPAZIO per lanciare' : 'Tocca per lanciare', W / 2, H - 70, 14, 'rgba(255,255,255,.85)');
    if (S.stato === 'fine') {
      g.fillStyle = 'rgba(10,22,64,.82)'; g.fillRect(0, 0, W, H);
      testo('Partita finita!', W / 2, H / 2 - 40, 28, '#fff'); testo(S.punti + ' punti', W / 2, H / 2 + 4, 38, '#fdba74');
      testo('Il punteggio è in classifica 🏆', W / 2, H / 2 + 38, 14, 'rgba(255,255,255,.85)'); testo('Clicca per rigiocare', W / 2, H / 2 + 76, 16, '#93c5fd');
    }
  }

  let ultimo = performance.now(), fermo = false;
  function ciclo(t) {
    if (fermo) return;
    const k = Math.min((t - ultimo) / 16.67, 2.5); ultimo = t;
    if (!document.hidden) { aggiorna(k); if (S.msgT > 0) S.msgT--; }
    disegna(); requestAnimationFrame(ciclo);
  }
  avvia(); requestAnimationFrame(ciclo);
  return () => { fermo = true; window.removeEventListener('keydown', kd); window.removeEventListener('keyup', ku); };
}
"""


def finestra_gioco(utente, st):
    """Contenuto della finestra di gioco: il campo, la registrazione del punteggio e la classifica."""
    ss = st.session_state
    st.caption("Muovi la trave con mouse, dito o frecce ←/→. Clic, tocco o SPAZIO per lanciare la palla. Tre vite: più mattoni rompi, più punti fai.")
    campo, lista = st.columns([1.1, 1], gap="large")
    with campo:
        res = st.components.v2.component("fcr_arkanoid", js=JS_GIOCO)(key="ark_campo", on_punteggio_change=lambda: None)
    p = getattr(res, "punteggio", None)
    esito_msg = None
    if isinstance(p, dict) and p.get("n") != ss.get("_ark_n"):
        ss["_ark_n"] = p.get("n")
        esito = registra(utente, p.get("p"), None)
        if esito == "record":
            st.balloons()
            esito_msg = ("success", f"🏆 Nuovo record personale: {int(p['p'])} punti!")
        elif esito == "partita":
            esito_msg = ("info", f"{int(p['p'])} punti. Il tuo record resta quello in classifica: riprova!")
    with lista:
        if esito_msg:
            getattr(st, esito_msg[0])(esito_msg[1])
        st.markdown("**🏆 Classifica dei colleghi**")
        st.markdown(classifica_html(utente), unsafe_allow_html=True)
        st.caption("Il tuo punteggio migliore resta in classifica. Si gioca nei ritagli di pausa: niente premi, solo gloria. 😄")
