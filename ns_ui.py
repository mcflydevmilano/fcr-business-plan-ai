"""ns_ui.py - Interfaccia delle note spese e trasferte."""
import datetime as dt
import io

import pandas as pd
import streamlit as st

import fp
import guida
import ns
import richieste
import theme
from ui_util import cantieri_rubrica, sola_lettura

ss = st.session_state
ICONE = {"In attesa": "🟡", "Approvata": "🟢", "Respinta": "🔴", "Rimborsata": "💶", "Annullata": "⚪"}
MESI = fp_mesi = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]


def _cantieri():
    return [f"{c['Codice']} · {c['Cantiere']}" for c in cantieri_rubrica(solo_vivi=True) if c.get("Codice")]


def _riga(r):
    d = r["dati"]
    km = f" · {d['km']:g} km" if d.get("km") else ""
    return (f"{ICONE[r['stato']]} **{dt.date.fromisoformat(d['data']):%d/%m/%Y}** · {d['categoria']} · **{d['importo']:.2f} €**{km}"
            + (f" · {d['cantiere']}" if d.get("cantiere") else "") + f" · {r['stato']}" + (f" ({r['deciso_da']}: {r['nota_decisione']})" if r["nota_decisione"] else ""))


def _foto(rid):
    for i, (nome, tipo, dati) in enumerate(richieste.allegati(rid)):
        if tipo.startswith("image/"):
            st.image(dati, caption=nome, width=320)
        else:
            st.download_button(f"📎 {nome}", dati, file_name=nome, mime=tipo, key=f"ns_all_{rid}_{i}")


def _nuova(nome, cfg, audit):
    if sola_lettura():
        st.info("Con il ruolo «lettore» puoi consultare ma non registrare spese.")
        return
    c1, c2 = st.columns(2)
    cat = c1.selectbox("Che spesa è", ns.CATEGORIE, key="ns_n_cat")
    data = c2.date_input("Data", value=dt.date.today(), format="DD/MM/YYYY", key="ns_n_data")
    km = imp = 0.0
    senza = False
    if cat == "Rimborso chilometrico":
        a, b = st.columns(2)
        km = a.number_input("Chilometri percorsi", 0.0, 5000.0, 0.0, 1.0, key="ns_n_km")
        b.metric("Rimborso", f"{ns.importo_km(km, cfg['tariffa_km']):.2f} €", f"{cfg['tariffa_km']:.2f} €/km", delta_color="off")
    else:
        a, b = st.columns(2)
        imp = a.number_input("Importo (€)", 0.0, 100000.0, 0.0, 0.5, key="ns_n_imp", format="%.2f")
        pagato = b.selectbox("Come hai pagato", ns.PAGATO, key="ns_n_pag")
    cant = _cantieri()
    cantiere = st.selectbox("Cantiere (se la spesa è per un lavoro)", ["—"] + cant, key="ns_n_cant") if cant else st.text_input("Cantiere (facoltativo)", key="ns_n_cant_t")
    desc = st.text_input("Descrizione" + (" (percorso e motivo)" if cat == "Rimborso chilometrico" else " (cosa e perché)"), key="ns_n_desc")
    files = []
    if cat != "Rimborso chilometrico":
        up = st.file_uploader("Foto dello scontrino o della fattura (anche dalla fotocamera del telefono)", type=["jpg", "jpeg", "png", "webp", "pdf"], accept_multiple_files=True, key="ns_n_foto")
        files = [(f.name, f.getvalue()) for f in (up or [])][:4]
        senza = st.checkbox("Non ho la ricevuta (lo spiego nella descrizione)", key="ns_n_senza")
    if st.button("📨 Invia la spesa", type="primary", key="ns_n_invia"):
        dati, err = ns.prepara({"categoria": cat, "data": str(data), "km": km, "importo": imp, "cantiere": "" if cantiere == "—" else cantiere, "descrizione": desc,
                                "pagato": ns.PAGATO[0] if cat == "Rimborso chilometrico" else pagato, "senza_ricevuta": senza}, cfg["tariffa_km"], n_allegati=len(files))
        if err:
            st.error(err)
        else:
            try:
                richieste.crea(ns.TIPO, nome, dati, files)
            except ValueError as e:
                st.error(str(e))
                return
            audit("ns_nuova", f"{cat} {dati['importo']:.2f} €")
            for k in ("ns_n_imp", "ns_n_km", "ns_n_desc", "ns_n_senza"):
                ss.pop(k, None)
            ss["_ns_msg"] = f"Spesa di {dati['importo']:.2f} € inviata."
            st.rerun()


def _mie(nome, lista, audit):
    mie = [r for r in lista if r["utente"] == nome]
    if not mie:
        st.caption("Nessuna spesa registrata.")
        return
    da_r = sum(r["dati"]["importo"] for r in mie if ns.da_rimborsare(r))
    st.metric("Ancora da rimborsarti", f"{da_r:.2f} €")
    for r in mie[:40]:
        x, y = st.columns([5, 1.3])
        x.markdown(_riga(r))
        if r["stato"] == "In attesa" and not sola_lettura() and y.button("Annulla", key=f"ns_ann_{r['id']}", width="stretch"):
            richieste.decidi(r["id"], "Annullata", nome, "annullata da chi l'ha inserita")
            audit("ns_annullata", f"{r['dati']['categoria']} {r['dati']['importo']:.2f}")
            st.rerun()
        with x.expander("Vedi ricevuta"):
            _foto(r["id"])


def _da_approvare(nome, ruolo, profilo, lista, cfg, audit):
    attesa = [r for r in lista if r["stato"] == "In attesa" and fp.puo_approvare(nome, ruolo, profilo, cfg, r["utente"])]
    if not attesa:
        st.success("Nessuna spesa da approvare.")
        return
    for r in sorted(attesa, key=lambda r: r["dati"]["data"]):
        with st.container(border=True):
            st.markdown(f"**{r['utente']}** · " + _riga(r).split(" · ", 1)[1].rsplit(" · ", 1)[0] + (f" — {r['dati']['descrizione']}" if r["dati"].get("descrizione") else ""))
            if r["dati"].get("senza_ricevuta"):
                st.warning("Senza ricevuta.")
            _foto(r["id"])
            nota = st.text_input("Nota (obbligatoria se respingi)", key=f"ns_nota_{r['id']}")
            a, b = st.columns(2)
            if a.button("✅ Approva", key=f"ns_ok_{r['id']}", type="primary", width="stretch"):
                richieste.decidi(r["id"], "Approvata", nome, nota)
                audit("ns_approvata", f"{r['utente']} {r['dati']['importo']:.2f}")
                st.rerun()
            if b.button("⛔ Respingi", key=f"ns_no_{r['id']}", width="stretch", disabled=not nota.strip()):
                richieste.decidi(r["id"], "Respinta", nome, nota)
                audit("ns_respinta", f"{r['utente']} {r['dati']['importo']:.2f}")
                st.rerun()


def _riepilogo(nome, lista, audit):
    oggi = dt.date.today()
    c1, c2 = st.columns(2)
    mese = c1.selectbox("Mese", range(1, 13), index=oggi.month - 1, format_func=lambda m: MESI[m - 1], key="ns_r_mese")
    anno = c2.selectbox("Anno", range(oggi.year, oggi.year - 4, -1), key="ns_r_anno")
    mensili = ns.del_mese(lista, anno, mese)
    if not mensili:
        st.info("Nessuna spesa approvata in questo mese.")
        return
    rie = ns.riepilogo(mensili)
    st.markdown(theme.stat_strip([{"label": "Totale del mese", "value": f"{rie['totale']:.2f} €", "sub": f"{len(mensili)} spese", "tono": "info"},
                                  {"label": "Da rimborsare", "value": f"{sum(x['Da rimborsare €'] for x in rie['persone']):.2f} €", "sub": "non ancora pagate ai colleghi", "tono": "warn"}]), unsafe_allow_html=True)
    st.markdown("**Per persona**")
    st.dataframe(pd.DataFrame(rie["persone"]).rename(columns={"Voce": "Persona"}), hide_index=True, width="stretch")
    a, b = st.columns(2)
    a.markdown("**Per cantiere**")
    a.dataframe(pd.DataFrame(rie["cantieri"]).rename(columns={"Voce": "Cantiere"}), hide_index=True, width="stretch")
    b.markdown("**Per categoria**")
    b.dataframe(pd.DataFrame(rie["categorie"]).rename(columns={"Voce": "Categoria"}), hide_index=True, width="stretch")
    da_pagare = [r for r in mensili if r["stato"] == "Approvata" and ns.da_rimborsare(r)]
    if da_pagare and not sola_lettura():
        pers = sorted({r["utente"] for r in da_pagare})
        sc = st.selectbox("Segna come rimborsate le spese di", ["—"] + pers, key="ns_r_pag", help="Dopo aver fatto il bonifico o pagato in busta paga.")
        if sc != "—" and st.button(f"💶 Segna rimborsate ({sum(r['dati']['importo'] for r in da_pagare if r['utente'] == sc):.2f} €)", key="ns_r_pag_ok"):
            for r in da_pagare:
                if r["utente"] == sc:
                    richieste.decidi(r["id"], "Rimborsata", nome, f"rimborsata il {dt.date.today():%d/%m/%Y}")
            audit("ns_rimborsate", sc)
            st.rerun()
    det = pd.DataFrame(ns.righe_dettaglio(mensili))
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame(rie["persone"]).rename(columns={"Voce": "Persona"}).to_excel(w, index=False, sheet_name="Per persona")
        pd.DataFrame(rie["cantieri"]).rename(columns={"Voce": "Cantiere"}).to_excel(w, index=False, sheet_name="Per cantiere")
        pd.DataFrame(rie["categorie"]).rename(columns={"Voce": "Categoria"}).to_excel(w, index=False, sheet_name="Per categoria")
        det.to_excel(w, index=False, sheet_name="Dettaglio")
    d1, d2 = st.columns(2)
    d1.download_button("📥 Scarica il riepilogo in Excel", buf.getvalue(), file_name=f"note_spese_{anno}_{mese:02d}.xlsx", key="ns_r_xls", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    z, n = ns.zip_scontrini(mensili)
    d2.download_button(f"🗂️ Scarica gli scontrini ({n})", z, file_name=f"scontrini_{anno}_{mese:02d}.zip", key="ns_r_zip", mime="application/zip", disabled=not n)


def render(fcr_uri, audit, utente, profilo, utenti_secrets=None):
    audit = audit or (lambda *a, **k: None)
    nome, ruolo = utente["username"], utente.get("ruolo")
    st.markdown(theme.hero(fcr_uri, "Note spese e trasferte", "Foto dello scontrino, importo, cantiere: il responsabile approva, l'amministrazione ha il riepilogo."), unsafe_allow_html=True)
    guida.mostra("ns")
    cfg = ns.carica_cfg()
    lista = richieste.elenca(ns.TIPO)
    gestore = ruolo == "admin" or profilo in ("presidente", "direzione", "amministrazione", "accesso completo")
    n_att = sum(1 for r in lista if r["stato"] == "In attesa" and fp.puo_approvare(nome, ruolo, profilo, cfg, r["utente"]))
    approva = gestore or n_att > 0
    nomi = ["➕ Nuova spesa", "🧾 Le mie spese"] + ([f"✅ Da approvare{f' ({n_att})' if n_att else ''}"] if approva else []) + (["📊 Riepilogo del mese", "⚙️ Regole"] if gestore else [])
    tabs = st.tabs(nomi)
    with tabs[0]:
        msg = ss.pop("_ns_msg", None)
        if msg:
            st.success(msg)
        _nuova(nome, cfg, audit)
    with tabs[1]:
        _mie(nome, lista, audit)
    i = 2
    if approva:
        with tabs[i]:
            _da_approvare(nome, ruolo, profilo, lista, cfg, audit)
        i += 1
    if gestore:
        with tabs[i]:
            _riepilogo(nome, lista, audit)
        with tabs[i + 1]:
            c1, c2 = st.columns(2)
            tar = c1.number_input("Rimborso chilometrico (€ per km)", 0.0, 5.0, cfg["tariffa_km"], 0.01, key="ns_c_tar", format="%.2f", help="Di solito la tariffa ACI del veicolo o quella stabilita dall'azienda.")
            pers = sorted({r["utente"] for r in lista} | set(cfg["approvatori"]))
            appr = c2.multiselect("Chi approva le spese (vuoto = direzione e amministrazione)", pers, default=cfg["approvatori"], key="ns_c_appr")
            extra = st.text_input("Aggiungi un nome utente tra gli approvatori", key="ns_c_extra")
            if st.button("💾 Salva", key="ns_c_salva", type="primary"):
                ns.salva_cfg({"tariffa_km": tar, "approvatori": appr + ([extra.strip().lower()] if extra.strip() else [])}, nome)
                audit("ns_regole", f"{tar:.2f} €/km")
                st.success("Regole salvate.")
                st.rerun()
