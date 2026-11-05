"""
ac_ui.py - Accessi del personale: pagina di timbratura (telefono), presenze, registro e impostazioni della sede.
La timbratura funziona anche FUORI dalla suite: dal QR o dalla pagina di accesso, con nome utente e password, senza aprire la suite.
La posizione e' letta dal telefono solo quando si preme Entrata o Uscita da fuori rete, e non viene salvata.
"""
import datetime as dt
import io

import pandas as pd
import streamlit as st

import acc
import notifiche
import storage
import theme

ss = st.session_state

_CSS = """
.ac-box { display: flex; flex-direction: column; gap: 12px; margin: 6px 0; }
.ac-btn { font: inherit; font-size: 1.25rem; font-weight: 700; padding: 20px 16px; border-radius: 16px; border: 2px solid #1d4ed8; background: #fff; color: #1d4ed8; cursor: pointer; width: 100%; }
.ac-btn.main { background: #1d4ed8; color: #fff; }
.ac-btn:disabled { opacity: .55; cursor: wait; }
.ac-msg { text-align: center; color: #475569; font-size: .95rem; min-height: 1.2em; }
"""
_JS = """
export default function(component) {
  const { data, setTriggerValue, parentElement } = component;
  const box = parentElement.querySelector('.ac-box');
  const msg = parentElement.querySelector('.ac-msg');
  box.innerHTML = '';
  msg.textContent = '';
  (data.azioni || []).forEach((a) => {
    const b = document.createElement('button');
    b.className = 'ac-btn' + (a.principale ? ' main' : '');
    b.textContent = a.label;
    b.onclick = () => {
      if (!a.gps) { setTriggerValue('azione', { azione: a.id, t: Date.now() }); return; }
      if (!navigator.geolocation) { setTriggerValue('azione', { azione: a.id, errore: 'nogps', t: Date.now() }); return; }
      b.disabled = true;
      msg.textContent = 'Sto leggendo la posizione (solo adesso)…';
      navigator.geolocation.getCurrentPosition(
        (p) => setTriggerValue('azione', { azione: a.id, lat: p.coords.latitude, lon: p.coords.longitude, acc: p.coords.accuracy, t: Date.now() }),
        (e) => { b.disabled = false; msg.textContent = ''; setTriggerValue('azione', { azione: a.id, errore: String(e.code), t: Date.now() }); },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
      );
    };
    box.appendChild(b);
  });
}
"""
_componente = st.components.v2.component("ac_timbra", html="<div class='ac-box'></div><div class='ac-msg'></div>", css=_CSS, js=_JS)

_ERRORI_GPS = {"1": "Hai negato la posizione. Abilitala per questo sito nelle impostazioni del browser e riprova: serve solo al momento di Entrata e Uscita.",
               "2": "Non riesco a leggere la posizione: controlla che il GPS sia acceso e riprova.",
               "3": "La posizione ci sta mettendo troppo: avvicinati a una finestra e riprova.",
               "nogps": "Questo telefono o browser non permette di leggere la posizione."}


def _ip():
    try:
        return acc.ip_cliente(dict(st.context.headers), getattr(st.context, "ip_address", "") or "")
    except Exception:
        return ""


def _blocco_timbra(nome, cfg, audit, chiave):
    """Stato, pulsanti grandi e messaggi. La posizione si chiede solo per Entrata/Uscita da fuori della rete dell'ufficio."""
    ip = _ip()
    ev = storage.elenca_timbrature(utente=nome)
    s = acc.stato(ev)
    in_sede = acc.ip_in_sede(ip, cfg)
    ultimo = acc.a_locale(ev[-1]["ts"]) if ev else None
    testo = {"fuori": "Sei **fuori**", "dentro": "Sei **in ufficio**", "in_pausa": "Sei **in pausa**"}[s]
    if ultimo:
        testo += f" · ultima timbratura: {acc.ETICHETTE[ev[-1]['tipo']].lower()} alle {ultimo.strftime('%H:%M')} del {ultimo.strftime('%d/%m')}"
    st.markdown(testo)
    azioni = [{"id": t, "label": acc.ETICHETTE[t], "gps": (t in acc.CON_CONTROLLO and not in_sede), "principale": i == 0}
              for i, t in enumerate(acc.azioni_consentite(s))]
    msg = ss.pop(f"_ac_msg_{chiave}", None)
    if msg:
        (st.success if msg[0] else st.error)(msg[1])
    r = _componente(data={"azioni": azioni}, key=f"ac_comp_{chiave}", on_azione_change=lambda: None)
    a = getattr(r, "azione", None) if r else None
    if a and a.get("t") != ss.get(f"_ac_t_{chiave}"):
        ss[f"_ac_t_{chiave}"] = a.get("t")
        if a.get("errore"):
            ss[f"_ac_msg_{chiave}"] = (False, _ERRORI_GPS.get(str(a["errore"]), "Posizione non disponibile."))
        else:
            pos = {"lat": a["lat"], "lon": a["lon"], "acc": a.get("acc")} if "lat" in a else None
            res = acc.timbra(nome, a["azione"], cfg, ip, pos)
            ss[f"_ac_msg_{chiave}"] = (res["ok"], res["messaggio"])
            if res["ok"]:
                audit("ac_timbratura", acc.ETICHETTE[a["azione"]])
        st.rerun()
    if in_sede:
        st.caption("📶 Sei collegato alla rete dell'ufficio: non serve la posizione.")
    else:
        st.caption("📍 Fuori dalla rete dell'ufficio, per Entrata e Uscita il telefono chiede la posizione. Viene letta solo in quel momento, non viene seguita né salvata.")
    return s


def stazione(utente, fcr_uri, apri_suite=None, esci=None):
    """Pagina di timbratura indipendente dalla suite (dal QR o dalla pagina di accesso)."""
    st.markdown(theme.hero(fcr_uri, "Timbratura", "Entrata, pausa e uscita dal telefono."), unsafe_allow_html=True)
    cfg = acc.carica_cfg()
    nome = utente["username"]
    st.markdown(f"Ciao **{nome}**.")
    _blocco_timbra(nome, cfg, lambda az, d="": storage.log_evento(nome, az, d), "stazione")
    c1, c2 = st.columns(2)
    if apri_suite and c1.button("Apri la suite", key="ac_apri_suite", width="stretch"):
        apri_suite()
    if esci and c2.button("Esci", key="ac_esci", width="stretch"):
        esci()


def _excel(righe):
    buf = io.BytesIO()
    df = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in righe])
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Presenze")
    return buf.getvalue()


def _foglio_qr(url, sede):
    """Foglio A4 da stampare (PDF) con il QR e le istruzioni."""
    import segno
    from PIL import Image, ImageDraw, ImageFont
    qr = segno.make(url, error="m")
    b = io.BytesIO()
    qr.save(b, kind="png", scale=14, border=2, dark="#0f172a")
    qi = Image.open(io.BytesIO(b.getvalue())).convert("RGB")
    W, H = 1240, 1754
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)

    def font(sz, grassetto=False):
        for p in (("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf") if grassetto else
                  ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf")):
            try:
                return ImageFont.truetype(p, sz)
            except OSError:
                continue
        return ImageFont.load_default(size=sz)

    def centrato(testo, y, f, colore="#0f172a"):
        w = d.textlength(testo, font=f)
        d.text(((W - w) / 2, y), testo, font=f, fill=colore)

    centrato("TIMBRATURA", 150, font(110, True), "#1d4ed8")
    centrato("Inquadra il codice con il telefono", 300, font(52))
    lato = 820
    qi = qi.resize((lato, lato), Image.NEAREST)
    im.paste(qi, ((W - lato) // 2, 420))
    y = 1300
    for riga in ("1. Inquadra il codice con la fotocamera", "2. Accedi con nome utente e password", "3. Premi Entrata, Pausa, Rientro o Uscita"):
        centrato(riga, y, font(44))
        y += 78
    centrato(f"Sede: {sede}", 1600, font(34), "#475569")
    out = io.BytesIO()
    im.save(out, format="PDF", resolution=150)
    return out.getvalue(), b.getvalue()


MODELLO_COMUNICAZIONE = """Oggetto: rilevazione delle presenze con QR code

Da [data] le entrate e le uscite dall'ufficio si registrano con il telefono, inquadrando il QR code all'ingresso ed entrando con il proprio nome utente.
Si registrano: nome, data e ora di Entrata, Inizio e Fine pausa, Uscita. Il sistema controlla che la timbratura avvenga dalla rete dell'ufficio oppure, da altra rete, che il telefono si trovi in sede: la posizione viene letta solo nel momento in cui si preme Entrata o Uscita, non viene seguita durante la giornata e non viene conservata (si conserva solo il fatto che la verifica sia andata a buon fine).
I dati servono alla rilevazione delle presenze e al calcolo delle ore, e sono visibili alla persona interessata, alla direzione e all'amministrazione. Sono conservati per [periodo] e inviati al consulente del lavoro per le buste paga.
Le correzioni (per esempio una timbratura dimenticata) si chiedono alla direzione e restano registrate con il motivo.
Per informazioni sul trattamento dei dati: [riferimento privacy]."""


def render(fcr_uri, audit, utente, profilo, utenti_secrets=None):
    audit = audit or (lambda *a, **k: None)
    nome = utente["username"]
    gestore = utente.get("ruolo") == "admin" or profilo in ("presidente", "direzione", "amministrazione", "accesso completo")
    impostazioni = utente.get("ruolo") == "admin" or profilo in ("presidente", "direzione", "accesso completo")
    st.markdown(theme.hero(fcr_uri, "Accessi del personale", "Entrata, pause e uscita con il telefono, dal QR all'ingresso."), unsafe_allow_html=True)
    cfg = acc.carica_cfg()
    nomi = ["📲 Timbra", "🗓️ Le mie presenze"] + (["👥 Registro"] if gestore else []) + (["⚙️ Sede e QR"] if impostazioni else [])
    tabs = st.tabs(nomi)
    with tabs[0]:
        _blocco_timbra(nome, cfg, audit, "modulo")
    with tabs[1]:
        _mie(nome)
    i = 2
    if gestore:
        with tabs[i]:
            _registro(utente, audit, utenti_secrets)
        i += 1
    if impostazioni:
        with tabs[i]:
            _impostazioni(cfg, utente, audit)


def _mie(nome):
    oggi = dt.datetime.now(acc.fuso()).date()
    c1, c2 = st.columns(2)
    da = c1.date_input("Dal", oggi.replace(day=1), format="DD/MM/YYYY", key="ac_mie_da")
    a = c2.date_input("Al", oggi, format="DD/MM/YYYY", key="ac_mie_a")
    if not da or not a or da > a:
        st.info("Scegli un periodo valido.")
        return
    u0, u1 = acc.intervallo_giorni(da, a)
    ev = storage.elenca_timbrature(u0, u1, nome)
    righe = acc.tabella(ev, da, a)
    if not righe:
        st.info("Nessuna timbratura nel periodo.")
        return
    st.metric("Ore in ufficio nel periodo", acc.ore(sum(r["_min"] for r in righe)))
    st.dataframe(pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_") and k != "Persona"} for r in righe]), width="stretch", hide_index=True,
                 column_config={"Giorno": st.column_config.DateColumn("Giorno", format="DD/MM/YYYY")})
    st.caption("Se manca una timbratura (per esempio un'uscita dimenticata), chiedi alla direzione di correggerla.")


def _nomi(utenti_secrets):
    n = set((utenti_secrets or {}).keys())
    try:
        n |= {u["username"] for u in storage.elenca_utenti() if u["attivo"]}
        n |= {e["utente"] for e in storage.elenca_timbrature()}
    except Exception:
        pass
    return sorted(n, key=str.lower)


def _registro(utente, audit, utenti_secrets):
    oggi = dt.datetime.now(acc.fuso()).date()
    tutti = _nomi(utenti_secrets)
    # chi e' dentro adesso
    u0, u1 = acc.intervallo_giorni(oggi, oggi)
    di_oggi = storage.elenca_timbrature(u0, u1)
    per = {}
    for e in di_oggi:
        per.setdefault(e["utente"], []).append(e)
    dentro = [(p, acc.stato(e)) for p, e in sorted(per.items()) if acc.stato(e) != "fuori"]
    st.markdown("#### Adesso")
    if dentro:
        st.write(" · ".join(f"**{p}** ({'in pausa' if s == 'in_pausa' else 'in ufficio'})" for p, s in dentro))
    else:
        st.caption("Nessuno risulta in ufficio in questo momento.")
    st.markdown("#### Presenze")
    c1, c2, c3 = st.columns([1, 1, 2])
    da = c1.date_input("Dal", oggi.replace(day=1), format="DD/MM/YYYY", key="ac_reg_da")
    a = c2.date_input("Al", oggi, format="DD/MM/YYYY", key="ac_reg_a")
    chi = c3.selectbox("Persona", ["Tutte"] + tutti, key="ac_reg_chi")
    if not da or not a or da > a:
        st.info("Scegli un periodo valido.")
        return
    u0, u1 = acc.intervallo_giorni(da, a)
    ev = storage.elenca_timbrature(u0, u1, None if chi == "Tutte" else chi)
    righe = acc.tabella(ev, da, a)
    if righe:
        st.dataframe(pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in righe]), width="stretch", hide_index=True,
                     column_config={"Giorno": st.column_config.DateColumn("Giorno", format="DD/MM/YYYY")})
        tot = {}
        for r in righe:
            tot[r["Persona"]] = tot.get(r["Persona"], 0) + r["_min"]
        st.markdown("**Totale ore per persona:** " + " · ".join(f"{p} {acc.ore(m)}" for p, m in sorted(tot.items())))
        anom = [r for r in righe if r["Note"]]
        if anom:
            st.warning(f"{len(anom)} giorni da controllare (uscite mancanti, correzioni a mano): vedi la colonna «Note».")
        st.download_button("Scarica in Excel", _excel(righe), file_name=f"presenze_{da:%Y%m%d}_{a:%Y%m%d}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="ac_reg_xls")
    else:
        st.info("Nessuna timbratura nel periodo.")
    with st.expander("✏️ Correggi o annulla una timbratura"):
        st.caption("Le correzioni restano nel registro con il motivo e il tuo nome. Una timbratura annullata non si cancella.")
        with st.form("ac_corr", clear_on_submit=True):
            a1, a2, a3, a4 = st.columns([2, 2, 1, 1])
            pers = a1.selectbox("Persona", tutti, key="ac_c_p") if tutti else a1.text_input("Persona", key="ac_c_p")
            tipo = a2.selectbox("Cosa", acc.TIPI, format_func=lambda t: acc.ETICHETTE[t], key="ac_c_t")
            giorno = a3.date_input("Giorno", oggi, format="DD/MM/YYYY", key="ac_c_g")
            ora = a4.time_input("Ora", dt.time(8, 0), key="ac_c_o")
            motivo = st.text_input("Motivo (obbligatorio)", key="ac_c_m", placeholder="es. uscita dimenticata")
            ok = st.form_submit_button("Aggiungi la timbratura")
        if ok:
            try:
                acc.correggi(pers, tipo, dt.datetime.combine(giorno, ora), motivo, utente["username"])
                audit("ac_correzione", f"{pers}: {tipo} {giorno} {ora:%H:%M} - {motivo[:60]}")
                st.success("Aggiunta.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
        recenti = list(reversed(storage.elenca_timbrature(u0, u1, None if chi == "Tutte" else chi)))[:40]
        if recenti:
            etich = {e["id"]: f"{acc.a_locale(e['ts']):%d/%m %H:%M} · {e['utente']} · {acc.ETICHETTE[e['tipo']]}" + (" (a mano)" if e["metodo"] == "manuale" else "") for e in recenti}
            with st.form("ac_ann", clear_on_submit=True):
                sel = st.selectbox("Timbratura da annullare", list(etich), format_func=lambda i: etich[i], key="ac_a_s")
                mot = st.text_input("Motivo (obbligatorio)", key="ac_a_m")
                ok2 = st.form_submit_button("Annulla la timbratura")
            if ok2:
                try:
                    acc.annulla(sel, mot, utente["username"])
                    audit("ac_annullo", f"{etich[sel]} - {mot[:60]}")
                    st.success("Annullata.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))


def _impostazioni(cfg, utente, audit):
    st.markdown("#### Sede e controlli")
    st.caption("La timbratura di Entrata e Uscita vale se il telefono è collegato alla rete dell'ufficio, oppure, da un'altra rete, se la posizione letta in quel momento è vicina alla sede. Pausa e rientro non chiedono posizione.")
    ip_ora = _ip()
    c1, c2 = st.columns(2)
    sede = c1.text_input("Indirizzo della sede (solo per il foglio da stampare)", cfg["sede"], key="ac_s_sede")
    url = c2.text_input("Indirizzo della suite", cfg["url"] or notifiche.app_url() or "https://suite.piattaformafcr.it", key="ac_s_url")
    c3, c4 = st.columns(2)
    raggio = c3.number_input("Distanza massima dalla sede (metri)", 30, 2000, cfg["raggio_m"], 10, key="ac_s_raggio",
                             help="All'interno degli edifici il GPS sbaglia anche di 50-100 m: 150 m è un buon punto di partenza.")
    inc = c4.number_input("Precisione GPS minima accettata (± metri)", 30, 2000, cfg["max_incertezza_m"], 10, key="ac_s_inc")
    ips = st.text_area("Indirizzi di rete dell'ufficio (uno per riga)", "\n".join(cfg["ip"]), key="ac_s_ip", height=80,
                       help="L'indirizzo pubblico della connessione internet dell'ufficio. Si legge anche con il pulsante qui sotto, dalla rete dell'ufficio.")
    st.caption(f"Il tuo indirizzo di rete in questo momento: `{ip_ora or 'non rilevato'}`" +
               (" — è un indirizzo interno: apri la suite da suite.piattaformafcr.it per leggere quello pubblico." if ip_ora.startswith(("192.168.", "10.", "172.16.", "127.")) else ""))
    b1, b2 = st.columns(2)
    nuovo = dict(cfg, sede=sede, url=url.strip(), raggio_m=raggio, max_incertezza_m=inc, ip=ips)
    if b1.button("➕ Aggiungi il mio indirizzo di rete attuale", key="ac_s_addip", width="stretch", disabled=not ip_ora or ip_ora.startswith(("192.168.", "10.", "127."))):
        elenco = [x for x in ips.splitlines() if x.strip()]
        if ip_ora not in elenco:
            elenco.append(ip_ora)
        acc.salva_cfg(dict(nuovo, ip="\n".join(elenco)), utente["username"])
        storage.svuota_cache()
        audit("ac_impostazioni", "indirizzo di rete aggiunto")
        st.rerun()
    if b2.button("Salva le impostazioni", type="primary", key="ac_s_salva", width="stretch"):
        acc.salva_cfg(nuovo, utente["username"])
        storage.svuota_cache()
        audit("ac_impostazioni", "salvate")
        st.success("Salvato.")
    st.markdown("**Posizione della sede**")
    if cfg["lat"] is None:
        st.warning("Non ancora impostata: senza, da fuori rete non si può timbrare. Vai in ufficio e premi il pulsante qui sotto.")
    else:
        st.caption(f"Impostata ({cfg['lat']:.5f}, {cfg['lon']:.5f}). Per aggiornarla, ripremi il pulsante stando in ufficio.")
    r = _componente(data={"azioni": [{"id": "sede", "label": "📍 Usa la mia posizione attuale come sede", "gps": True, "principale": False}]}, key="ac_comp_sede", on_azione_change=lambda: None)
    a = getattr(r, "azione", None) if r else None
    if a and a.get("t") != ss.get("_ac_t_sede"):
        ss["_ac_t_sede"] = a.get("t")
        if "lat" in a:
            acc.salva_cfg(dict(nuovo, lat=a["lat"], lon=a["lon"]), utente["username"])
            storage.svuota_cache()
            audit("ac_impostazioni", f"posizione della sede impostata (precisione ±{int(a.get('acc') or 0)} m)")
            st.success(f"Sede impostata (precisione ±{int(a.get('acc') or 0)} m).")
        else:
            st.error(_ERRORI_GPS.get(str(a.get("errore")), "Posizione non disponibile."))
    st.markdown("#### QR da stampare")
    base = (url or "").strip().rstrip("/")
    if not base.startswith("http"):
        st.info("Scrivi l'indirizzo della suite (https://…) per creare il QR.")
        return
    link = base + "/?timbra=1"
    try:
        pdf, png = _foglio_qr(link, sede)
    except Exception as e:
        st.error(f"Non riesco a creare il QR: {e}")
        return
    q1, q2 = st.columns([1, 2])
    q1.image(png, width=220)
    q2.markdown(f"Il codice apre `{link}`: pagina di timbratura con nome utente e password, senza aprire la suite.")
    q2.download_button("⬇️ Foglio A4 da stampare (PDF)", pdf, file_name="qr_timbratura.pdf", mime="application/pdf", key="ac_qr_pdf")
    q2.download_button("⬇️ Solo il QR (PNG)", png, file_name="qr_timbratura.png", mime="image/png", key="ac_qr_png")
    with st.expander("📄 Comunicazione ai dipendenti (modello)"):
        st.caption("Da far leggere al consulente del lavoro prima di usarla. La rilevazione delle presenze richiede un'informativa chiara; dubbi sull'accordo con le rappresentanze vanno chiariti con lui.")
        st.code(MODELLO_COMUNICAZIONE, language=None)
