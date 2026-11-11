"""novita_ui.py - Pagina «Novità e aggiornamenti»."""
import datetime as dt

import streamlit as st

import guida
import novita
import theme

ss = st.session_state


def _scheda(v, aperta, nuova=False):
    quando = v["quando"] or novita.data_it(v["data"])
    titolo = f"{'🆕 ' if nuova else ''}Versione {v['id']} · {quando} · {v['titolo']}" if v["id"][:1].isdigit() else f"{'🆕 ' if nuova else ''}{quando} · {v['titolo']}"
    with st.expander(titolo, expanded=aperta):
        for x in v["voci"]:
            st.markdown(f"- {x}")
        if v["strumenti"]:
            st.caption("Strumenti: " + ", ".join(v["strumenti"]))
        if v["manuale"] and v["autore"]:
            st.caption(f"Scritta da {v['autore']}")


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Novità e aggiornamenti", "Cosa è cambiato nella suite, in parole semplici, e cosa puoi fare di nuovo."), unsafe_allow_html=True)
    guida.mostra("nv")
    admin = (ss.get("utente") or {}).get("ruolo") == "admin"
    tutte = novita.tutte()
    nuova = novita.da_leggere(utente)
    chiave_nuova = f"{nuova['id']}|{nuova['data']}" if nuova else None
    if nuova:
        st.success(f"🆕 Hai delle novità da leggere: ultimo aggiornamento, versione {nuova['id']}.")
        novita.segna_lette(utente)                              # da questo momento l'avviso nell'Hub sparisce
    novita.segna_tutte_viste(utente)                            # e anche i bollini NEW sugli strumenti citati, senza doverli aprire uno per uno
    f1, f2 = st.columns([3, 2])
    q = f1.text_input("Cerca nelle novità", key="nv_cerca", placeholder="es. compiti, bolle, rubrica…")
    tutti_str = sorted({s for v in tutte for s in v["strumenti"]})
    s = f2.selectbox("Strumento", ["Tutti"] + tutti_str, key="nv_str")
    ok = novita.filtra(tutte, q, "" if s == "Tutti" else s)
    if not ok:
        st.info("Nessuna novità trovata.")
    for i, v in enumerate(ok):
        _scheda(v, aperta=(i == 0 and not q and s == "Tutti"), nuova=(f"{v['id']}|{v['data']}" == chiave_nuova))
    st.caption("Hai un'idea o hai trovato qualcosa che non funziona? Scrivilo nella chat: così lo sistemiamo e finisce qui tra le novità.")
    if admin:
        with st.expander("✍️ Aggiungi una novità (solo amministratori)"):
            st.caption("Scrivi in parole semplici cosa è cambiato per chi usa la suite. Ogni riga è una voce.")
            with st.form("nv_nuova", clear_on_submit=True):
                a, b = st.columns([1, 3])
                ver = a.text_input("Versione (facoltativa)", key="nv_n_ver", placeholder="es. 3.13.0")
                tit = b.text_input("Titolo", key="nv_n_tit", placeholder="es. Rapportino anche senza campo")
                voci = st.text_area("Cosa cambia (una voce per riga)", key="nv_n_voci", height=130)
                strumenti = st.text_input("Strumenti interessati (separati da virgola)", key="nv_n_str", placeholder="es. Rapportini di cantiere, Presenze e ore")
                data = st.date_input("Data", value=dt.date.today(), format="DD/MM/YYYY", key="nv_n_data")
                inviato = st.form_submit_button("➕ Pubblica la novità")
            if inviato:
                try:
                    novita.aggiungi(ver, tit, voci, [x for x in strumenti.split(",")], data.isoformat(), utente)
                    audit("nv_aggiunta", tit[:60])
                    st.toast("Novità pubblicata")
                    st.rerun()
                except ValueError as e:
                    st.warning(str(e))
            man = [v for v in tutte if v["manuale"]]
            if man:
                st.markdown("**Novità scritte a mano**")
                for v in man:
                    c1, c2 = st.columns([5, 1])
                    c1.caption(f"{novita.data_it(v['data'])} · {v['titolo']}")
                    if c2.button("🗑️", key=f"cmd_nv_del_{v['id']}_{v['data']}", help="Elimina questa novità"):
                        novita.elimina(v["id"], v["data"], autore=utente)
                        audit("nv_eliminata", v["titolo"][:60])
                        st.rerun()
