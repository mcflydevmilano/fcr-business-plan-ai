"""pc_ui.py - Portale cliente: la pagina pubblica (render_pubblico) e lo strumento interno per gestirla (render)."""
import base64
import datetime as dt
import os

import streamlit as st

import chat
import firma
import guida
import pc
import theme
from ui_util import cantieri_rubrica, sola_lettura

ss = st.session_state
ICONA = {"attivo": "🟢", "scaduto": "⚪", "revocato": "🔴"}


def _base():
    return os.environ.get("FCR_PUBLIC_URL", "https://suite.piattaformafcr.it")


def render_pubblico(token):
    """Pagina vista dal cliente: nessun menu, nessun accesso alla suite. Non scrive niente nell'URL e non mostra mai il token."""
    entry, s = pc.trova(token)
    if not entry:
        st.markdown("## 🔒 Portale cliente")
        st.info(pc.MSG_NON_VALIDO)
        return
    c = pc.carica_contenuto(entry["id"])
    st.markdown(f"## 🏗️ FCR General Contractor")
    st.markdown(f"### {entry['nome']}")
    if c["saluto"]:
        st.write(c["saluto"])
    if c["stato_testo"] or c["avanzamento"]:
        st.markdown("#### A che punto siamo")
        st.progress(c["avanzamento"] / 100, text=f"{c['avanzamento']}% completato")
        if c["stato_testo"]:
            st.write(c["stato_testo"])
    if c["passi"]:
        st.markdown("#### Prossimi passi")
        for p in c["passi"]:
            st.markdown(f"- {p}")
    if c["foto"]:
        st.markdown("#### Foto")
        cols = st.columns(2)
        for i, f in enumerate(c["foto"]):
            try:
                cols[i % 2].image(base64.b64decode(f["dati"]), caption=f.get("didascalia") or None, width="stretch")
            except Exception:
                pass
    if c["documenti"]:
        st.markdown("#### Documenti")
        for i, d in enumerate(c["documenti"]):
            try:
                st.download_button(f"📄 {d['nome']}", base64.b64decode(d["dati"]), d["nome"], mime="application/pdf", key=f"pcd_{i}")
            except Exception:
                pass
    o = c["offerta"]
    if o["attiva"]:
        st.markdown("#### La nostra offerta")
        st.markdown(f"**{o['titolo']}**" + (f" · € {o['importo']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if o["importo"] else ""))
        if o["descrizione"]:
            st.write(o["descrizione"])
        a = c["accettazione"]
        if a:
            st.success(f"✅ Offerta accettata da {a['nome']} il {a['data'][:10]}. Grazie!")
        else:
            st.caption("Se sei d'accordo, scrivi il tuo nome, firma con il dito e conferma.")
            nome = st.text_input("Nome e cognome", key="pc_nome")
            sg = firma.pad("pc_firma")
            ok = st.checkbox("Ho letto l'offerta e la accetto", key="pc_ok")
            if st.button("✍️ Accetto l'offerta", key="pc_accetta", type="primary", disabled=not ok):
                fatto, motivo = pc.accetta(token, nome, sg)
                if fatto:
                    st.rerun()
                else:
                    st.error(motivo)


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    nome = utente.get("username", "") if isinstance(utente, dict) else str(utente or "")
    st.markdown(theme.hero(fcr_uri, "Portale cliente", "Un link segreto per ogni cliente: vede lo stato dei lavori, le foto, i documenti e può accettare l'offerta con la firma."), unsafe_allow_html=True)
    guida.mostra("pc")
    oggi = dt.date.today()
    t1, t2, t3 = st.tabs(["🔗 1. Link dei clienti", "➕ 2. Nuovo link", "✏️ 3. Cosa vede il cliente"])
    el = pc.elenca(oggi=oggi)
    with t1:
        if not el:
            st.info("Nessun link creato. Creane uno nella scheda «2».")
        for x in el:
            c = pc.carica_contenuto(x["id"])
            with st.expander(f"{ICONA[x['stato']]} {x['nome']} · {x['stato']} fino al {x['scade']}" + (" · ✅ offerta accettata" if x["accettata"] else "")):
                st.caption(f"Cantiere: {x['cantiere'] or '—'} · creato il {x['creato']} da {x['autore']}")
                if c["accettazione"]:
                    a = c["accettazione"]
                    st.success(f"Accettata da {a['nome']} il {a['data'][:16].replace('T', ' alle ')} · {a['titolo']} · € {a['importo']:,.2f}")
                    try:
                        st.image(base64.b64decode(a["firma"]), width=220)
                    except Exception:
                        pass
                b1, b2, b3 = st.columns(3)
                gg = b3.number_input("Giorni", 1, pc.GIORNI_MAX, pc.GIORNI_BASE, key=f"pc_gg_{x['id']}", label_visibility="collapsed")
                if b1.button("🚫 Revoca", key=f"pc_rev_{x['id']}", disabled=x["stato"] == "revocato" or sola_lettura()):
                    pc.revoca(x["id"], nome)
                    audit("pc_revoca", x["nome"])
                    st.rerun()
                if b2.button("⏳ Proroga di (giorni)", key=f"pc_pro_{x['id']}", disabled=sola_lettura()):
                    pc.proroga(x["id"], gg, nome)
                    audit("pc_proroga", x["nome"])
                    st.rerun()
        st.caption("Per sicurezza il link completo si vede una sola volta, quando lo crei. Se lo perdi, revoca questo e creane uno nuovo.")
    with t2:
        cant = cantieri_rubrica()
        n = st.text_input("Nome del cliente (lo vede nella pagina)", key="pc_n_nome")
        cod = st.selectbox("Cantiere collegato (facoltativo)", [""] + [c["Codice"] for c in cant if c.get("Codice")], key="pc_n_cant")
        gg = st.slider("Il link vale per (giorni)", 7, pc.GIORNI_MAX, pc.GIORNI_BASE, key="pc_n_gg")
        if st.button("Crea il link", key="pc_crea", type="primary", disabled=not n.strip() or sola_lettura()):
            token, id_ = pc.crea(n, cod, gg, nome)
            ss["pc_nuovo"] = (pc.link(token, _base()), n)
            audit("pc_crea", n)
        if ss.get("pc_nuovo"):
            st.success(f"Link per {ss['pc_nuovo'][1]}: copialo ora e mandalo al cliente. Non si potrà rivedere.")
            st.code(ss["pc_nuovo"][0], language=None)
            st.caption("Poi compila cosa vede nella scheda «3».")
    with t3:
        vivi = [x for x in el if x["stato"] != "revocato"]
        if not vivi:
            st.info("Crea prima un link.")
            return
        sel = st.selectbox("Cliente", [x["id"] for x in vivi], format_func=lambda i: next(x["nome"] for x in vivi if x["id"] == i), key="pc_sel")
        c = pc.carica_contenuto(sel)
        k = f"pc_c_{sel}_"
        c["saluto"] = st.text_input("Saluto", c["saluto"], key=k + "sal", placeholder="Buongiorno Sig. Rossi, ecco come procedono i lavori.")
        c["avanzamento"] = st.slider("Avanzamento lavori (%)", 0, 100, c["avanzamento"], key=k + "av")
        c["stato_testo"] = st.text_area("A che punto siamo", c["stato_testo"], key=k + "st", height=100)
        c["passi"] = [r for r in st.text_area("Prossimi passi (uno per riga)", "\n".join(c["passi"]), key=k + "pa", height=100).split("\n")]
        st.markdown("**Foto da mostrare** (non mettere dati riservati o di altri clienti)")
        for i, f in enumerate(c["foto"]):
            a, b = st.columns([4, 1])
            a.caption(f"📷 {f['nome']}")
            if b.button("Togli", key=f"{k}ft{i}"):
                c["foto"].pop(i)
                pc.salva_contenuto(sel, c, nome)
                st.rerun()
        nf = st.file_uploader("Aggiungi foto", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True, key=k + "fu")
        for f in nf or []:
            if len(c["foto"]) >= pc.MAX_FOTO or any(x["nome"] == f.name for x in c["foto"]):
                continue
            try:
                n_, t_, d_ = chat.prepara_allegato(f.name, f.getvalue())
                c["foto"].append({"nome": n_, "tipo": t_, "dati": d_, "didascalia": ""})
            except Exception as e:
                st.warning(f"{f.name}: {e}")
        for i, d in enumerate(c["documenti"]):
            a, b = st.columns([4, 1])
            a.caption(f"📄 {d['nome']}")
            if b.button("Togli", key=f"{k}dc{i}"):
                c["documenti"].pop(i)
                pc.salva_contenuto(sel, c, nome)
                st.rerun()
        nd = st.file_uploader("Aggiungi documenti PDF", type=["pdf"], accept_multiple_files=True, key=k + "du")
        for f in nd or []:
            if len(c["documenti"]) >= pc.MAX_DOC or any(x["nome"] == f.name for x in c["documenti"]):
                continue
            try:
                n_, t_, d_ = chat.prepara_allegato(f.name, f.getvalue())
                c["documenti"].append({"nome": n_, "tipo": t_, "dati": d_})
            except Exception as e:
                st.warning(f"{f.name}: {e}")
        st.markdown("**Offerta da far accettare**")
        o = c["offerta"]
        bloccata = bool(c["accettazione"])
        if bloccata:
            st.info("L'offerta è già stata accettata: non si può più cambiare.")
        o["attiva"] = st.checkbox("Mostra un'offerta da accettare", o["attiva"], key=k + "oa", disabled=bloccata)
        o["titolo"] = st.text_input("Titolo", o["titolo"], key=k + "ot", disabled=bloccata)
        o["importo"] = st.number_input("Importo €", 0.0, 100000000.0, float(o["importo"]), 100.0, key=k + "oi", disabled=bloccata)
        o["descrizione"] = st.text_area("Descrizione", o["descrizione"], key=k + "od", disabled=bloccata, height=100)
        if st.button("💾 Salva quello che vede il cliente", key=k + "sv", type="primary", disabled=sola_lettura()):
            pc.salva_contenuto(sel, c, nome)
            audit("pc_contenuto", next(x["nome"] for x in vivi if x["id"] == sel))
            st.success("Salvato.")
