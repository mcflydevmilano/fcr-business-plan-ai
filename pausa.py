"""
pausa.py - Promemoria gentili per chi lavora a lungo al computer: occhi, acqua, gambe e la pausa vera.
Funziona nel browser (nessun dato salvato sul server): conta solo il tempo in cui la pagina e' aperta e si usa il mouse o la tastiera.
Se l'utente si ferma per oltre 5 minuti, il conteggio riparte da zero (sta gia' facendo una pausa).

Tempistiche (tempo di lavoro continuo):
  30 min  -> riposa gli occhi (20 secondi guardando lontano)
  60 min  -> bevi un bicchiere d'acqua
  90 min  -> alzati e muoviti 2 minuti
  120 min -> pausa vera di 15 minuti (art. 175 D.Lgs. 81/2008: 15 minuti ogni 2 ore di lavoro al videoterminale)
"""
import streamlit as st

_JS_MOTORE = r"""
export default function(component) {
  if (window.__fcrPausa) return;
  const d = document;
  const LS = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const SET = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
  const scala = Math.max(1, parseFloat(LS('fcr_pausa_scala') || '1'));          // solo per le prove: 60 = un minuto diventa un secondo
  const MIN = 60000 / scala;

  const COL = { blu: '#1e3fae', az: '#0b4f9c', ros: '#c8102e', grigio: '#64748b', chiaro: '#e0e7ff', verde: '#16a34a' };
  const ARTE = {
    occhi: `<svg viewBox="0 0 120 80" width="112" height="75" aria-hidden="true"><rect width="120" height="80" rx="12" fill="#e0f2fe"/>
      <circle cx="96" cy="18" r="9" fill="#fde047"/><path d="M0 60 L28 34 L50 58 L74 30 L120 62 V80 H0Z" fill="#86efac"/><path d="M0 68 L40 52 L80 66 L120 56 V80 H0Z" fill="#22c55e"/>
      <ellipse cx="60" cy="36" rx="30" ry="17" fill="#fff" stroke="#1e3fae" stroke-width="3"/><circle cx="60" cy="36" r="11" fill="#1e3fae"/><circle cx="60" cy="36" r="5" fill="#0f172a"/><circle cx="64" cy="32" r="2.4" fill="#fff"/></svg>`,
    acqua: `<svg viewBox="0 0 120 80" width="112" height="75" aria-hidden="true"><rect width="120" height="80" rx="12" fill="#e0f2fe"/>
      <path d="M40 14 H80 L74 68 Q73 72 69 72 H51 Q47 72 46 68Z" fill="#fff" stroke="#1e3fae" stroke-width="3"/><path d="M43 34 H77 L73.5 66 Q73 69 69 69 H51 Q47 69 46.5 66Z" fill="#38bdf8"/>
      <circle cx="56" cy="50" r="3" fill="#fff" opacity=".8"/><circle cx="66" cy="58" r="2.2" fill="#fff" opacity=".8"/><circle cx="60" cy="42" r="1.8" fill="#fff" opacity=".8"/>
      <path d="M96 22 q6 9 0 14 q-6 -5 0 -14Z" fill="#38bdf8"/><path d="M22 30 q4 7 0 11 q-4 -4 0 -11Z" fill="#7dd3fc"/></svg>`,
    gambe: `<svg viewBox="0 0 120 80" width="112" height="75" aria-hidden="true"><rect width="120" height="80" rx="12" fill="#fef3c7"/>
      <rect x="0" y="68" width="120" height="12" fill="#fcd34d"/><circle cx="60" cy="18" r="8" fill="#f59e0b"/><path d="M60 26 V48" stroke="#1e3fae" stroke-width="6" stroke-linecap="round"/>
      <path d="M60 32 L38 14 M60 32 L82 14" stroke="#1e3fae" stroke-width="5" stroke-linecap="round"/><path d="M60 48 L46 68 M60 48 L74 68" stroke="#1e3fae" stroke-width="6" stroke-linecap="round"/>
      <path d="M22 40 l6 -6 M98 40 l-6 -6 M16 54 h8 M96 54 h8" stroke="#f59e0b" stroke-width="3" stroke-linecap="round"/></svg>`,
    pausa: `<svg viewBox="0 0 120 80" width="112" height="75" aria-hidden="true"><rect width="120" height="80" rx="12" fill="#fee2e2"/>
      <path d="M36 34 H80 V54 Q80 68 66 68 H50 Q36 68 36 54Z" fill="#fff" stroke="#c8102e" stroke-width="3"/><path d="M80 40 H88 Q96 40 96 48 Q96 56 88 56 H80" fill="none" stroke="#c8102e" stroke-width="3"/>
      <path d="M46 26 q-5 -7 0 -13 M58 26 q-5 -7 0 -13 M70 26 q-5 -7 0 -13" fill="none" stroke="#f87171" stroke-width="3" stroke-linecap="round"/><path d="M30 72 H86" stroke="#c8102e" stroke-width="3" stroke-linecap="round"/></svg>`
  };
  const MSG = {
    occhi: { titolo: 'Occhi, fate una vacanza!', durata: '20 secondi', testi: [
      'Alza lo sguardo dallo schermo e guarda qualcosa lontano: una finestra, un cantiere, una nuvola. Gli occhi ringraziano.',
      'Sono passati 30 minuti. Guarda fuori per 20 secondi e batti le palpebre un paio di volte: lo schermo non scappa.',
      'Pausa occhi! Cerca la cosa più lontana che vedi e fissala un momento. Poi si riparte.'] },
    acqua: { titolo: 'Un bicchiere d\'acqua?', durata: '2 minuti', testi: [
      'Un\'ora di lavoro: è il momento di un bicchiere d\'acqua. Anche il cervello va "irrigato", non solo il cantiere.',
      'Bevi! Chi si idrata ragiona meglio e sbaglia meno i conti. (Il caffè vale, ma non conta come acqua.)',
      'Acqua in arrivo: alzati, riempi il bicchiere e bevi con calma. Vale come mini pausa.'] },
    gambe: { titolo: 'Su le gambe!', durata: '2-3 minuti', testi: [
      'Un\'ora e mezza seduti: alzati, stira schiena e spalle, fai due passi. La sedia può aspettare.',
      'Metti in piedi la schiena: allunga le braccia in alto, ruota le spalle, cammina fino alla finestra e ritorno.',
      'Pausa movimento! Meglio due minuti in piedi adesso che il mal di schiena stasera.'] },
    pausa: { titolo: 'Pausa vera: 15 minuti', durata: '15 minuti', testi: [
      'Due ore al computer: staccati per 15 minuti. Lontano dallo schermo, magari un caffè e due chiacchiere. È un tuo diritto, non una perdita di tempo.',
      'Fermi tutti! Ora la pausa lunga: allontanati dalla scrivania per 15 minuti. I numeri li ritrovi dopo, più lucidi.',
      'Basta schermo per un po\': 15 minuti di pausa. Cammina, respira, bevi qualcosa. Ci vediamo dopo.'] }
  };
  const CICLO = [['occhi', 30], ['acqua', 60], ['gambe', 90], ['pausa', 120]];

  const st = { attivi: 0, ultimo: Date.now(), indice: 0, rimanda: 0, aperto: false };
  const spento = () => LS('fcr_pausa_off') === '1';

  const css = d.createElement('style');
  css.textContent = `
  #fcr-pausa{position:fixed;top:72px;right:22px;z-index:100000;width:min(360px,calc(100vw - 32px));background:#fff;border-radius:18px;border:1px solid #e2e8f0;
    box-shadow:0 20px 50px rgba(15,23,42,.28);font-family:inherit;color:#0f172a;overflow:hidden;animation:fcrPausaIn .35s ease both}
  #fcr-pausa .fp-top{height:5px;background:linear-gradient(90deg,#1e3fae,#c8102e)}
  #fcr-pausa .fp-body{display:flex;gap:14px;padding:16px 16px 6px;align-items:center}
  #fcr-pausa .fp-t{font-weight:800;font-size:17px;line-height:1.2;margin-bottom:4px}
  #fcr-pausa .fp-d{font-size:13.5px;line-height:1.45;color:#334155}
  #fcr-pausa .fp-dur{display:inline-block;margin:8px 0 0;font-size:12px;font-weight:700;color:#1e3fae;background:#e0e7ff;border-radius:99px;padding:3px 10px}
  #fcr-pausa .fp-bt{display:flex;gap:8px;padding:10px 16px 14px}
  #fcr-pausa button{flex:1;border:0;border-radius:10px;padding:10px 8px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
  #fcr-pausa .fp-ok{background:#1e3fae;color:#fff}
  #fcr-pausa .fp-no{background:#f1f5f9;color:#334155}
  #fcr-pausa .fp-off{display:block;width:100%;background:none;color:#94a3b8;font-size:12px;font-weight:500;padding:0 0 10px;text-decoration:underline}
  @keyframes fcrPausaIn{from{opacity:0;transform:translateY(-14px) scale(.97)}to{opacity:1;transform:none}}
  @media (max-width:640px){#fcr-pausa{top:auto;bottom:90px;right:16px}}`;
  d.head.appendChild(css);

  function chiudi() { const e = d.getElementById('fcr-pausa'); if (e) e.remove(); st.aperto = false; }

  function mostra(tipo, prova) {
    chiudi();
    const m = MSG[tipo];
    const testo = m.testi[Math.floor(Math.random() * m.testi.length)];
    const el = d.createElement('div');
    el.id = 'fcr-pausa';
    el.setAttribute('role', 'status');
    el.innerHTML = `<div class="fp-top"></div><div class="fp-body"><div>${ARTE[tipo]}</div><div><div class="fp-t">${m.titolo}</div><div class="fp-d">${testo}</div><span class="fp-dur">⏱ ${m.durata}</span></div></div>
      <div class="fp-bt"><button class="fp-ok" type="button">Ok, fatto! ✔</button><button class="fp-no" type="button">Tra 5 minuti</button></div>
      <button class="fp-off" type="button">Non mostrare più questi promemoria</button>`;
    d.body.appendChild(el);
    st.aperto = true;
    el.querySelector('.fp-ok').onclick = () => { chiudi(); if (!prova && tipo === 'pausa') { st.attivi = 0; st.indice = 0; } };
    el.querySelector('.fp-no').onclick = () => { chiudi(); st.rimanda = Date.now() + 5 * MIN; };
    el.querySelector('.fp-off').onclick = () => { chiudi(); SET('fcr_pausa_off', '1'); };
    if (tipo !== 'pausa') setTimeout(() => { if (d.getElementById('fcr-pausa') === el) chiudi(); }, 45000);
  }

  ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'].forEach(ev => window.addEventListener(ev, () => { st.ultimo = Date.now(); }, { passive: true }));

  setInterval(() => {
    const ora = Date.now();
    if (d.hidden) return;
    if (ora - st.ultimo > 5 * MIN) { st.attivi = 0; st.indice = 0; return; }   // fermo da oltre 5 minuti: sta gia' facendo una pausa
    st.attivi += 1000;
    if (spento() || st.aperto || ora < st.rimanda) return;
    const [tipo, minuti] = CICLO[st.indice];
    if (st.attivi >= minuti * MIN) {
      mostra(tipo, false);
      st.indice = (st.indice + 1) % CICLO.length;
      if (st.indice === 0) st.attivi = 0;                    // dopo la pausa lunga il ciclo ricomincia
    }
  }, 1000);

  window.__fcrPausa = { mostra: t => mostra(t, true), riattiva: () => { SET('fcr_pausa_off', '0'); }, spento };
}
"""

_JS_PANNELLO = r"""
export default function(component) {
  const { parentElement } = component;
  parentElement.innerHTML = '';
  const stile = 'padding:8px 10px;border-radius:9px;border:1px solid #cbd5e1;background:#fff;color:#0f172a;font-size:13px;font-weight:600;cursor:pointer;';
  const mk = (txt, fn) => { const b = document.createElement('button'); b.type = 'button'; b.textContent = txt; b.style.cssText = stile; b.onclick = fn; return b; };
  const riga = document.createElement('div');
  riga.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;margin-top:4px';
  const nota = document.createElement('div');
  nota.style.cssText = 'font-size:12.5px;color:#475569;margin-top:8px';
  const stato = () => { const p = window.__fcrPausa; nota.textContent = p && p.spento() ? 'I promemoria sono spenti su questo dispositivo.' : 'I promemoria sono accesi.'; };
  const prova = t => () => { if (window.__fcrPausa) window.__fcrPausa.mostra(t); };
  riga.append(mk('👁️ Occhi', prova('occhi')), mk('💧 Acqua', prova('acqua')), mk('🚶 Gambe', prova('gambe')), mk('☕ Pausa', prova('pausa')));
  const ri = mk('🔔 Riaccendi i promemoria', () => { if (window.__fcrPausa) window.__fcrPausa.riattiva(); stato(); });
  ri.style.marginTop = '8px';
  parentElement.append(riga, ri, nota);
  stato();
}
"""


def inietta():
    """Da chiamare una volta per esecuzione: avvia il promemoria nel browser. Non mostra nulla finche' non e' ora di una pausa."""
    try:
        st.components.v2.component("fcr_pausa_motore", js=_JS_MOTORE)(key="fcr_pausa_motore_c")
    except Exception:
        pass


@st.dialog("🧱 Mattoncini FCR · la pausa dei colleghi", width="large")
def _finestra_svago():
    import ark
    ark.finestra_gioco((st.session_state.get("utente") or {}).get("username", ""), st)


def pannello():
    """Riquadro per la barra laterale: spiega le tempistiche e permette di vedere un esempio di ogni avviso."""
    with st.expander("☕ Pause e piccolo svago"):
        st.markdown(
            "Ti ricordiamo di fare pause mentre lavori:  \n"
            "👁️ **ogni 30 min** guarda lontano 20 secondi  \n"
            "💧 **ogni ora** un bicchiere d'acqua  \n"
            "🚶 **ogni 90 min** alzati e muoviti  \n"
            "☕ **ogni 2 ore** pausa di 15 minuti (è la regola per chi usa il computer: art. 175 D.Lgs. 81/2008)  \n\n"
            "Il conteggio riparte se ti fermi più di 5 minuti. Prova gli avvisi:")
        try:
            st.components.v2.component("fcr_pausa_pannello", js=_JS_PANNELLO)(key="fcr_pausa_pannello_c")
        except Exception:
            pass
        st.markdown("---")
        st.markdown("**🎮 Un momento di svago**  \nTi va di rompere qualche mattone? Sfida i colleghi: la classifica è di tutti.")
        if st.button("🧱 Gioca a Mattoncini FCR", key="svago_apri", width="stretch"):
            _finestra_svago()
