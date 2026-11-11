"""sp_ui.py - Interfaccia di «Sopralluogo da telefono»."""
import base64

import streamlit as st

import chat
import guida
import sp
import theme
from ui_util import sola_lettura

ss = st.session_state


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    username = utente.get("username", "") if isinstance(utente, dict) else str(utente or "")
    st.markdown(theme.hero(fcr_uri, "Sopralluogo da telefono", "Compili sul posto, scatti le foto e il preventivo fotovoltaico parte già precompilato."), unsafe_allow_html=True)
    guida.mostra("sp")
    t1, t2 = st.tabs(["📱 1. Nuovo sopralluogo", "📋 2. Sopralluoghi fatti"])
    with t1:
        r = ss.get("sp_rec") or sp.nuovo()
        ss["sp_rec"] = r
        r["cliente"] = st.text_input("Cliente", r["cliente"], key="sp_cliente")
        r["indirizzo"] = st.text_input("Indirizzo", r["indirizzo"], key="sp_indirizzo")
        a, b = st.columns(2)
        r["tetto"] = a.selectbox("Che tetto è?", sp.TIPI_TETTO, index=sp.TIPI_TETTO.index(r["tetto"]), key="sp_tetto")
        r["orientamento"] = b.selectbox("Verso dove guarda?", sp.ORIENTAMENTI, index=sp.ORIENTAMENTI.index(r["orientamento"]), key="sp_orient")
        a, b = st.columns(2)
        r["superficie_m2"] = a.number_input("Superficie utile (m²)", 0.0, 5000.0, float(r["superficie_m2"]), 5.0, key="sp_sup")
        r["copertura"] = b.selectbox("Com'è la copertura?", sp.COPERTURE, index=sp.COPERTURE.index(r["copertura"]), key="sp_cop")
        a, b = st.columns(2)
        r["ombre"] = a.selectbox("Ombre sul tetto", list(sp.OMBRE), index=list(sp.OMBRE).index(r["ombre"]), key="sp_ombre")
        r["zona"] = b.selectbox("Zona d'Italia", sp.ZONE, index=sp.ZONE.index(r["zona"]), key="sp_zona")
        a, b, c = st.columns(3)
        r["potenza_kw"] = a.number_input("Potenza impegnata (kW)", 0.0, 100.0, float(r["potenza_kw"]), 0.5, key="sp_pot")
        r["distanza_m"] = b.number_input("Quadro → inverter (m)", 0.0, 500.0, float(r["distanza_m"]), 1.0, key="sp_dist")
        r["consumo_kwh"] = c.number_input("Consumo annuo (kWh)", 0.0, 1000000.0, float(r["consumo_kwh"]), 100.0, key="sp_cons")
        r["accumulo"] = st.checkbox("Il cliente vuole anche la batteria", r["accumulo"], key="sp_acc")
        r["note"] = st.text_area("Note", r["note"], key="sp_note")
        st.markdown("**Foto**")
        for key, et in sp.CHECK:
            st.caption("• " + et)
        nuove = st.file_uploader("Scatta o scegli le foto", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True, key="sp_foto")
        if nuove:
            gia = {f["nome"] for f in r["foto"]}
            for f in nuove:
                if f.name in gia or len(r["foto"]) >= sp.MAX_FOTO:
                    continue
                try:
                    n, tipo, dati = chat.prepara_allegato(f.name, f.getvalue())
                    r["foto"].append({"nome": n, "tipo": tipo, "dati": dati})
                except Exception as e:
                    st.warning(f"{f.name}: {e}")
        st.caption(f"{len(r['foto'])} foto (massimo {sp.MAX_FOTO}).")
        n = sp.stima_moduli(r["superficie_m2"], r["tetto"])
        st.metric("Stima", f"{n} moduli", f"≈ {sp.kwp(n)} kWp")
        for c in sp.controlli(r):
            st.warning(c)
        b1, b2, b3 = st.columns(3)
        if b1.button("💾 Salva il sopralluogo", key="sp_salva", type="primary", disabled=sola_lettura()):
            sp.aggiungi(r, username)
            audit("sp_salva", r["cliente"])
            st.success("Sopralluogo salvato.")
        if b2.button("☀️ Crea il preventivo fotovoltaico", key="sp_crea_fv", disabled=sola_lettura()):
            sp.aggiungi(r, username)
            ss["_pending"] = sp.parametri_fv(r)
            ss["active_module"] = "fv"
            audit("sp_crea_fv", r["cliente"])
            st.rerun()
        b3.download_button("⬇️ Riepilogo Word", sp.docx_bytes(r), "sopralluogo.docx", key="sp_docx", width="stretch")
        if st.button("🆕 Nuovo sopralluogo", key="sp_nuovo"):
            ss.pop("sp_rec", None)
            for k in [k for k in ss if str(k).startswith("sp_") and k != "sp_rec"]:
                ss.pop(k, None)
            st.rerun()
    with t2:
        el = sp.carica()
        if not el:
            st.info("Nessun sopralluogo salvato.")
        for x in el:
            with st.expander(f"{x.get('data', '')} · {x.get('cliente') or 'senza nome'} · {x.get('indirizzo', '')}"):
                st.text(sp.testo(x))
                for f in x.get("foto") or []:
                    try:
                        st.image(base64.b64decode(f["dati"]), caption=f["nome"], width=240)
                    except Exception:
                        pass
                if st.button("Riapri", key=f"sp_ri_{x['id']}"):
                    for k in [k for k in ss if str(k).startswith("sp_") and not str(k).startswith("sp_ri_")]:
                        ss.pop(k, None)
                    ss["sp_rec"] = dict(x, foto=list(x.get("foto") or []))
                    st.rerun()
