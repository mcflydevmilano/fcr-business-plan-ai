"""bd_ui.py - Interfaccia di «Lettura bandi»."""
import streamlit as st

import bd
import guida
import theme

ss = st.session_state


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Lettura bandi", "Carichi il bando o il capitolato in PDF e ti preparo scadenze, importi, requisiti e cose da preparare."), unsafe_allow_html=True)
    guida.mostra("bd")
    st.warning("Quello che trovo va sempre controllato da una persona sul documento originale.")
    f = st.file_uploader("Bando o capitolato (PDF)", type=["pdf"], key="bd_up")
    incolla = st.text_area("…oppure incolla qui il testo", key="bd_txt", height=120)
    testo = ""
    if f is not None:
        testo = bd.pdf_testo(f.getvalue())
        if not testo:
            st.info("Questo PDF sembra una scansione (immagine): non riesco a leggerne il testo. Incolla il testo qui sotto o usa un PDF con testo selezionabile.")
    testo = testo or incolla
    if not testo.strip():
        return
    ai_fn, key = ss.get("_ia", (None, ""))
    sch = bd.estrai_regole(testo)
    if key and ai_fn and st.toggle("Usa anche l'AI per leggere meglio", value=True, key="bd_ai"):
        ia = bd.estrai_ai(ai_fn, key, testo)
        if ia:
            sch = bd.unisci(sch, ia)
        else:
            st.caption("L'AI non ha risposto: ti mostro quello che ho trovato con le regole.")
    st.markdown("### Cosa ho trovato")
    a, b, c = st.columns(3)
    a.metric("CIG", sch["cig"] or "—")
    b.metric("Importo base", f"€ {sch['importo_base']:,.0f}".replace(",", ".") if sch.get("importo_base") else "—")
    c.metric("Scadenza offerte", sch["scadenza_offerte"] or "—")
    if sch.get("oggetto"):
        st.write("**Oggetto:** " + str(sch["oggetto"]))
    if sch.get("categorie_soa"):
        st.write("**Categorie SOA:** " + ", ".join(sch["categorie_soa"]))
    st.markdown("### Cose da preparare")
    for i, r in enumerate(bd.checklist(sch)):
        st.checkbox(r, key=f"bd_ck_{i}")
