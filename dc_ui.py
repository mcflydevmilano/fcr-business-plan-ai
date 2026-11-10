"""dc_ui.py - Richiesta documenti: la pagina pubblica (render_pubblico) e lo strumento interno per gestirla (render)."""
import base64
import datetime as dt
import os

import streamlit as st

import chat
import dc
import guida
import theme
from ui_util import sola_lettura

ss = st.session_state
ICONA = {"attivo": "🟢", "scaduto": "⚪", "revocato": "🔴"}


def _base():
    return os.environ.get("FCR_PUBLIC_URL", "https://suite.piattaformafcr.it")


def _carica_file(voce, key_pref, max_file=dc.MAX_FILE_PER_VOCE):
    """Uploader + elenco dei file già caricati per una voce, con il pulsante «Togli». Restituisce la lista aggiornata."""
    file = list(voce["file"])
    for i, f in enumerate(file):
        a, b = st.columns([5, 1])
        a.caption(f"📄 {f['nome']}")
        if b.button("Togli", key=f"{key_pref}_x{i}"):
            file.pop(i)
            return file, True
    if len(file) < max_file:
        nf = st.file_uploader("Carica il documento (foto o PDF)", type=["pdf", "jpg", "jpeg", "png", "webp"], accept_multiple_files=True,
                               key=f"{key_pref}_up", label_visibility="collapsed")
        for f in nf or []:
            if len(file) >= max_file or any(x["nome"] == f.name for x in file):
                continue
            try:
                n_, t_, d_ = chat.prepara_allegato(f.name, f.getvalue())
                file.append({"nome": n_, "tipo": t_, "dati": d_})
            except Exception as e:
                st.warning(f"{f.name}: {e}")
            else:
                return file, True
    return file, False


def render_pubblico(token):
    """Pagina vista dall'amministratore del condominio: nessun menu, nessun accesso alla suite. Non mostra mai il token."""
    entry, s = dc.trova(token)
    if not entry:
        st.markdown("## 🔒 Richiesta documenti")
        st.info(dc.MSG_NON_VALIDO)
        return
    c = dc.carica_contenuto(entry["id"])
    st.markdown("## 🏗️ FCR General Contractor")
    st.markdown(f"### Documenti per: {entry['nome']}")
    if c["inviata"]:
        st.success(f"✅ Documenti inviati il {c['inviata'][:16].replace('T', ' alle ')} da {c['firmatario']}. Grazie, ci siamo.")
        st.caption("Se manca o va corretto qualcosa, ti scriviamo noi. Non serve rifare l'invio.")
        return
    st.write("Carica qui i documenti dell'elenco per l'istruttoria del finanziamento. Puoi tornare su questa pagina quante volte vuoi "
             "prima di inviare: quello che carichi resta salvato. Si invia una sola volta, e solo quando è tutto completo.")
    voci_richieste = [i for i in dc.ORDINE_VOCI if c["voci"][i]["richiesta"]]
    fatte = [i for i in voci_richieste if c["voci"][i]["file"]]
    st.progress(len(fatte) / len(voci_richieste) if voci_richieste else 1.0, text=f"{len(fatte)} di {len(voci_richieste)} documenti caricati")
    if not ss.get("dc_rev"):
        for cat in dc.CATEGORIE:
            voci_cat = [v for v in cat["voci"] if c["voci"][v["id"]]["richiesta"]]
            if not voci_cat:
                continue
            st.markdown(f"#### {cat['nome']}")
            for v in voci_cat:
                i = v["id"]
                voce = c["voci"][i]
                fatto = bool(voce["file"])
                with st.container(border=True):
                    st.markdown(("✅ " if fatto else "⬜ ") + v["testo"])
                    if v.get("nota"):
                        st.caption(v["nota"])
                    nuovo_file, cambiato = _carica_file(voce, f"dc_v_{i}")
                    if cambiato:
                        c["voci"][i]["file"] = nuovo_file
                        dc.salva_contenuto(entry["id"], c, "condominio")
                        st.rerun()
        st.markdown("#### Note per noi (facoltativo)")
        c["nota_finale"] = st.text_area("Scrivi qui se c'è qualcosa da segnalare", c["nota_finale"], key="dc_nota", label_visibility="collapsed")
        if st.button("💾 Salva", key="dc_salva"):
            dc.salva_contenuto(entry["id"], c, "condominio")
            st.success("Salvato. Puoi continuare più tardi da questo stesso link.")
        st.divider()
        mancanti = dc.voci_mancanti(c)
        if mancanti:
            st.warning(f"Mancano ancora {len(mancanti)} documenti: non si può inviare finché non sono tutti caricati.")
        nome = st.text_input("Nome e cognome di chi invia", key="dc_firmatario", placeholder="es. Mario Rossi, amministratore")
        if st.button("Controlla e invia ➜", key="dc_vai_rev", type="primary", disabled=bool(mancanti) or len(nome.strip()) < 3):
            dc.salva_contenuto(entry["id"], dict(c, firmatario=nome), "condominio")
            ss["dc_rev"] = True
            st.rerun()
    else:
        st.markdown("#### Controlla prima di inviare")
        st.caption("Dopo l'invio non si può più modificare: se serve una correzione, scrivi a chi ti ha mandato il link.")
        for cat in dc.CATEGORIE:
            voci_cat = [v for v in cat["voci"] if c["voci"][v["id"]]["richiesta"]]
            if not voci_cat:
                continue
            righe = [("✅" if c["voci"][v["id"]]["file"] else "⬜") + " " + v["testo"] for v in voci_cat]
            st.markdown(f"**{cat['nome']}**")
            for r in righe:
                st.markdown(f"- {r}")
        st.markdown(f"**Invia come:** {c['firmatario'] or '—'}")
        if c["nota_finale"]:
            st.markdown(f"**Note:** {c['nota_finale']}")
        ok = st.checkbox("Confermo di aver caricato tutti i documenti richiesti, che sono leggibili e corretti", key="dc_ok1")
        ok2 = st.checkbox("Confermo che voglio inviare adesso: dopo non si può più modificare", key="dc_ok2")
        b1, b2 = st.columns(2)
        if b1.button("← Torna indietro", key="dc_indietro"):
            ss["dc_rev"] = False
            st.rerun()
        if b2.button("✅ Invia definitivamente", key="dc_invia", type="primary", disabled=not (ok and ok2)):
            fatto, motivo = dc.invia(token, c["firmatario"], c["nota_finale"])
            if fatto:
                ss["dc_rev"] = False
                st.rerun()
            else:
                st.error(motivo)


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    nome = utente.get("username", "") if isinstance(utente, dict) else str(utente or "")
    st.markdown(theme.hero(fcr_uri, "Richiesta documenti", "Un link segreto per ogni condominio: carica i documenti dell'istruttoria "
                "(es. finanziamento) e li invia solo quando sono completi. Non vede e non può raggiungere nient'altro della suite."), unsafe_allow_html=True)
    guida.mostra("dc")
    oggi = dt.date.today()
    t1, t2, t3 = st.tabs(["🔗 1. Le richieste", "➕ 2. Nuova richiesta", "⚙️ 3. Voci necessarie"])
    el = dc.elenca(oggi=oggi)
    with t1:
        if not el:
            st.info("Nessuna richiesta creata. Creane una nella scheda «2».")
        for x in el:
            c = dc.carica_contenuto(x["id"])
            fatte = sum(1 for i in dc.ORDINE_VOCI if c["voci"][i]["richiesta"] and c["voci"][i]["file"])
            richieste = sum(1 for i in dc.ORDINE_VOCI if c["voci"][i]["richiesta"])
            bollino = " · ✅ inviata" if c["inviata"] else f" · {fatte}/{richieste} documenti"
            with st.expander(f"{ICONA[x['stato']]} {x['nome']} · {x['stato']} fino al {x['scade']}" + bollino):
                st.caption(f"Creata il {x['creato']} da {x['autore']}")
                if c["inviata"]:
                    st.success(f"Inviata il {c['inviata'][:16].replace('T', ' alle ')} da {c['firmatario']}" + (f" · nota: {c['nota_finale']}" if c["nota_finale"] else ""))
                for cat in dc.CATEGORIE:
                    voci_cat = [v for v in cat["voci"] if c["voci"][v["id"]]["richiesta"]]
                    if not voci_cat:
                        continue
                    st.markdown(f"**{cat['nome']}**")
                    for v in voci_cat:
                        voce = c["voci"][v["id"]]
                        if voce["file"]:
                            cols = st.columns(len(voce["file"]))
                            for j, f in enumerate(voce["file"]):
                                try:
                                    cols[j].download_button(f"📄 {v['testo'][:40]}…", base64.b64decode(f["dati"]), f["nome"], key=f"dcf_{x['id']}_{v['id']}_{j}")
                                except Exception:
                                    pass
                        else:
                            st.caption("⬜ " + v["testo"][:90])
                b1, b2, b3, b4 = st.columns(4)
                gg = b4.number_input("Giorni", 1, dc.GIORNI_MAX, dc.GIORNI_BASE, key=f"dc_gg_{x['id']}", label_visibility="collapsed")
                if b1.button("🚫 Revoca", key=f"dc_rev_{x['id']}", disabled=x["stato"] == "revocato" or sola_lettura()):
                    dc.revoca(x["id"], nome)
                    audit("dc_revoca", x["nome"])
                    st.rerun()
                if b2.button("⏳ Proroga di (giorni)", key=f"dc_pro_{x['id']}", disabled=sola_lettura()):
                    dc.proroga(x["id"], gg, nome)
                    audit("dc_proroga", x["nome"])
                    st.rerun()
                if c["inviata"] and b3.button("🔓 Riapri", key=f"dc_riap_{x['id']}", disabled=sola_lettura(), help="Permette al condominio di correggere o aggiungere documenti."):
                    dc.riapri(x["id"], nome)
                    audit("dc_riapri", x["nome"])
                    st.rerun()
        st.caption("Per sicurezza il link completo si vede una sola volta, quando lo crei. Se lo perdi, revoca questo e creane uno nuovo.")
    with t2:
        n = st.text_input("Nome (lo vede chi riceve il link): condominio, o condominio e condomino", key="dc_n_nome",
                           placeholder="es. Condominio Via Roma 12, oppure Condominio Via Roma 12 - Sig. Rossi")
        gg = st.slider("Il link vale per (giorni)", 7, dc.GIORNI_MAX, dc.GIORNI_BASE, key="dc_n_gg")
        if st.button("Crea la richiesta", key="dc_crea", type="primary", disabled=not n.strip() or sola_lettura()):
            token, id_ = dc.crea(n, gg, nome)
            ss["dc_nuovo"] = (dc.link(token, _base()), n)
            audit("dc_crea", n)
        if ss.get("dc_nuovo"):
            st.success(f"Link per {ss['dc_nuovo'][1]}: copialo ora e mandalo all'amministratore del condominio. Non si potrà rivedere.")
            st.code(ss["dc_nuovo"][0], language=None)
            st.caption("Se alcune voci non si applicano a questo caso (es. nessun condomino con quota sopra i 20.000 €), togline il "
                       "bisogno nella scheda «3» prima di mandare il link.")
    with t3:
        vivi = [x for x in el if x["stato"] != "revocato"]
        if not vivi:
            st.info("Crea prima una richiesta.")
            return
        sel = st.selectbox("Richiesta", [x["id"] for x in vivi], format_func=lambda i: next(x["nome"] for x in vivi if x["id"] == i), key="dc_sel")
        c = dc.carica_contenuto(sel)
        bloccata = bool(c["inviata"])
        if bloccata:
            st.info("Questa richiesta è già stata inviata: riaprila nella scheda «1» se serve cambiare le voci necessarie.")
        st.caption("Spunta solo le voci che servono davvero per questo condominio: quelle senza spunta non vengono mostrate e non bloccano l'invio.")
        for cat in dc.CATEGORIE:
            st.markdown(f"**{cat['nome']}**")
            for v in cat["voci"]:
                c["voci"][v["id"]]["richiesta"] = st.checkbox(v["testo"], c["voci"][v["id"]]["richiesta"], key=f"dc_req_{sel}_{v['id']}", disabled=bloccata)
        if st.button("💾 Salva le voci necessarie", key="dc_salva_voci", type="primary", disabled=bloccata or sola_lettura()):
            dc.salva_contenuto(sel, c, nome)
            audit("dc_voci", next(x["nome"] for x in vivi if x["id"] == sel))
            st.success("Salvato.")
