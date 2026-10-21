"""rp_ui.py - Interfaccia dei Rapportini di cantiere: pensata per il telefono (moduli corti, pulsanti grandi), con salvataggio automatico condiviso."""
import datetime as dt

import pandas as pd
import streamlit as st
import guida

import charts
import ops_report
import rp
import storage
import theme
from ui_util import banner_esempio, blocco_tabella, pannello_archivio, scarica_dossier, sola_lettura, sostituisci_tabella

ss = st.session_state
NOME = "Rapportini"                     # salvataggio condiviso: tutti i capicantiere scrivono qui
PARAM = ("giorni_senza_rapporto", "preavviso_gg", "finestra_gg")
NUOVO = "➕ Nuovo cantiere (scrivilo qui sotto)"


def _esempio():
    oggi = rp.oggi_italia()
    g = lambda n: (oggi - dt.timedelta(days=n)).isoformat()
    r = [(g(0), "Villa Lago", "Bianchi", "Sereno", 8, 64, "Getto solaio primo piano", "Autopompa", ""), (g(1), "Villa Lago", "Bianchi", "Nuvoloso", 7, 56, "Armatura solaio", "Gru", ""),
         (g(1), "Scuola Elementare", "Verdi", "Pioggia", 5, 30, "Impianto elettrico piano terra", "", "Lavori interrotti 2 ore per pioggia"), (g(6), "Capannone Nord", "Neri", "Sereno", 6, 48, "Posa pannelli di tamponamento", "Piattaforma", "")]
    s = [(g(2), "Villa Lago", "Sicurezza", "Alta", "Parapetto del ponteggio lato nord mancante", "Bianchi", (oggi + dt.timedelta(days=1)).isoformat(), "Aperta"),
         (g(4), "Scuola Elementare", "Materiale / consegna", "Media", "Consegna cavi in ritardo di una settimana", "Verdi", (oggi + dt.timedelta(days=5)).isoformat(), "In corso")]
    rr, ss_ = [dict(zip(rp.COLONNE_RAPP[1:], x)) for x in r], [dict(zip(rp.COLONNE_SEGN[1:], x)) for x in s]
    return (pd.DataFrame(rp.normalizza_rapp(rr)[0], columns=rp.COLONNE_RAPP), pd.DataFrame(rp.normalizza_segn(ss_)[0], columns=rp.COLONNE_SEGN))


def _records(chiave):
    return [] if chiave not in ss else ss[chiave].to_dict("records")


def _params():
    return {k: ss.get("rp_" + k, rp.RP_DEFAULT[k]) for k in PARAM}


def _dati():
    return {"rapp": rp.normalizza_rapp(_records("rp_rapp"))[0], "segn": rp.normalizza_segn(_records("rp_segn"))[0], "params": _params()}


def _raccogli():
    ss["_rp_firma"] = _firma()                         # chiamata dal pannello al salvataggio: da qui i dati coincidono con il database
    return _dati()


def _firma():
    import hashlib
    import json
    return hashlib.sha1(json.dumps([_records("rp_rapp"), _records("rp_segn")], default=str, sort_keys=True).encode("utf-8")).hexdigest()


def _applica(p, nome=""):
    sostituisci_tabella("rp_rapp", pd.DataFrame(p.get("rapp") or [], columns=rp.COLONNE_RAPP))
    sostituisci_tabella("rp_segn", pd.DataFrame(p.get("segn") or [], columns=rp.COLONNE_SEGN))
    ss["rp_demo"] = False
    ss["_rp_firma"] = _firma()
    ss["_pending"] = {"rp_" + k: v for k, v in (p.get("params") or {}).items() if k in PARAM}


def _carica_condiviso():
    """All'apertura: se esiste il registro condiviso lo carica; altrimenti parte con un esempio."""
    try:
        p = storage.carica_pratica(NOME, modulo="rp")
        meta = storage.meta_pratica(NOME, modulo="rp") if p else None
    except Exception:
        p, meta = None, None
    if p:
        _applica(p, NOME)
        ss["_base_rp"] = {"nome": NOME, "agg": meta["aggiornato"] if meta else ""}
    else:
        ss["rp_rapp"], ss["rp_segn"] = _esempio()
        ss["rp_demo"] = True


def _aggiorna_se_cambiato():
    """Se un collega ha salvato nel registro condiviso e qui non ci sono modifiche in sospeso, rilegge i dati."""
    base = ss.get("_base_rp") or {}
    if base.get("nome") != NOME or ss.get("_rp_toccati") or ss.get("rp_demo") or ss.get("_rp_firma") != _firma():
        return
    try:
        meta = storage.meta_pratica(NOME, modulo="rp")
        if meta and meta["aggiornato"] != base.get("agg"):
            p = storage.carica_pratica(NOME, modulo="rp")
            if p:
                _applica(p, NOME)
                ss["_base_rp"] = {"nome": NOME, "agg": meta["aggiornato"]}
    except Exception:
        pass


def _sincronizza(utente, audit):
    """Salva nel registro condiviso fondendo il lavoro degli altri telefoni: non si perde nulla anche se in due compilano insieme."""
    toc = ss.get("_rp_toccati", set())
    rapp, segn = _records("rp_rapp"), _records("rp_segn")
    for _ in range(4):
        try:
            meta = storage.meta_pratica(NOME, modulo="rp")
            db = storage.carica_pratica(NOME, modulo="rp") if meta else None
            payload = {"rapp": rp.unisci((db or {}).get("rapp"), rapp, toc), "segn": rp.unisci((db or {}).get("segn"), segn, toc), "params": (db or {}).get("params") or _params()}
            agg = storage.salva_pratica(NOME, payload, autore=utente, modulo="rp", atteso=meta["aggiornato"] if meta else "")
        except storage.ConflittoSalvataggio:
            continue                                   # qualcuno ha salvato nel frattempo: rileggi e riprova
        except Exception as e:
            return False, f"Salvataggio non riuscito: {e}"
        _applica(payload)
        ss["_base_rp"] = {"nome": NOME, "agg": agg}
        ss["_rp_toccati"] = set()
        audit("rp_sync", NOME)
        return True, ""
    return False, "Troppi salvataggi contemporanei: riprova tra un istante."


def _aggiungi(tabella, colonne, riga, utente, audit):
    if ss.get("rp_demo"):                              # il primo dato vero sostituisce l'esempio
        ss["rp_rapp"], ss["rp_segn"] = pd.DataFrame(columns=rp.COLONNE_RAPP), pd.DataFrame(columns=rp.COLONNE_SEGN)
        ss["rp_demo"] = False
    norm = rp.normalizza_rapp if tabella == "rp_rapp" else rp.normalizza_segn
    ok, _ = norm([riga])
    if not ok:
        st.error("Mancano dei dati obbligatori.")
        return False
    nuova = ok[0]
    sostituisci_tabella(tabella, pd.concat([ss[tabella], pd.DataFrame([nuova], columns=colonne)], ignore_index=True))
    ss["_rp_toccati"] = set(ss.get("_rp_toccati", set())) | {nuova["Id"]}
    okk, err = _sincronizza(utente, audit)
    if okk:
        st.toast("Salvato e condiviso ✅")
    else:
        st.warning(err + " I dati restano sul tuo schermo: riprova a salvare dal pannello «Salva e riapri».")
    return True


def _cantieri():
    return sorted({r["Cantiere"] for r in _records("rp_rapp") + _records("rp_segn") if r.get("Cantiere")})


def _scelta_cantiere(sel, nuovo):
    return (nuovo.strip() if sel == NUOVO or nuovo.strip() else sel)


def _tab_rapportino(utente, audit):
    st.markdown("##### Rapportino del giorno")
    cant = _cantieri()
    with st.form("form_rapp", clear_on_submit=True):
        sel = st.selectbox("Cantiere", cant + [NUOVO] if cant else [NUOVO], key="nr_cantiere")
        nuovo = st.text_input("Se è un cantiere nuovo, scrivi qui il nome", key="nr_nuovo")
        a, b = st.columns(2)
        data = a.date_input("Data", value=rp.oggi_italia(), key="nr_data", format="DD/MM/YYYY")
        meteo = b.selectbox("Meteo", rp.METEO, key="nr_meteo")
        c, d = st.columns(2)
        pres = c.number_input("Persone presenti", 0, 500, step=1, key="nr_pres")
        ore = d.number_input("Ore lavorate (totale di tutti)", 0.0, 5000.0, step=1.0, key="nr_ore", help="Persone × ore lavorate. Es. 6 persone per 8 ore = 48.")
        lav = st.text_area("Lavorazioni eseguite", key="nr_lav", height=90, placeholder="Es. Getto solaio primo piano, posa tubazioni bagno…")
        mezzi = st.text_input("Mezzi usati (facoltativo)", key="nr_mezzi")
        note = st.text_area("Note (facoltative)", key="nr_note", height=70)
        invia = st.form_submit_button("➕ Salva il rapportino", type="primary", width="stretch", disabled=sola_lettura())
    if invia:
        cantiere = _scelta_cantiere(sel, nuovo)
        if not cantiere or cantiere == NUOVO:
            st.error("Scegli il cantiere o scrivine il nome.")
        elif not lav.strip():
            st.error("Scrivi almeno una riga sulle lavorazioni eseguite.")
        else:
            riga = {"Data": data, "Cantiere": cantiere, "Compilato_da": utente, "Meteo": meteo, "Presenti": pres, "Ore": ore, "Lavorazioni": lav, "Mezzi": mezzi, "Note": note}
            if _aggiungi("rp_rapp", rp.COLONNE_RAPP, riga, utente, audit):
                st.rerun()
    r, _ = rp.normalizza_rapp(_records("rp_rapp"))
    if r:
        st.markdown("##### Ultimi inseriti")
        for x in sorted(r, key=lambda q: q["Data"], reverse=True)[:6]:
            st.markdown(f"**{x['Cantiere']}** · {pd.Timestamp(x['Data']).strftime('%d/%m')} · {x['Presenti']:.0f} persone, {x['Ore']:.0f} ore  \n<span style='color:#64748b;font-size:.88rem'>{x['Lavorazioni'][:110]}</span>", unsafe_allow_html=True)


def _tab_segnalazioni(utente, audit, out):
    st.markdown("##### Nuova segnalazione")
    cant = _cantieri()
    with st.form("form_segn", clear_on_submit=True):
        sel = st.selectbox("Cantiere", cant + [NUOVO] if cant else [NUOVO], key="ns_cantiere")
        nuovo = st.text_input("Se è un cantiere nuovo, scrivi qui il nome", key="ns_nuovo")
        a, b = st.columns(2)
        tipo = a.selectbox("Tipo", rp.TIPI_SEGN, key="ns_tipo")
        grav = b.selectbox("Gravità", rp.GRAVITA, index=1, key="ns_grav")
        desc = st.text_area("Cosa non va", key="ns_desc", height=90)
        c, d = st.columns(2)
        resp = c.text_input("Chi deve intervenire", key="ns_resp")
        entro = d.date_input("Da risolvere entro", value=None, key="ns_entro", format="DD/MM/YYYY")
        invia = st.form_submit_button("⚠️ Invia la segnalazione", type="primary", width="stretch", disabled=sola_lettura())
    if invia:
        cantiere = _scelta_cantiere(sel, nuovo)
        if not cantiere or cantiere == NUOVO:
            st.error("Scegli il cantiere o scrivine il nome.")
        elif not desc.strip():
            st.error("Descrivi il problema.")
        else:
            riga = {"Data": rp.oggi_italia(), "Cantiere": cantiere, "Tipo": tipo, "Gravita": grav, "Descrizione": desc, "Responsabile": resp, "Scadenza": entro or "", "Stato": "Aperta"}
            if _aggiungi("rp_segn", rp.COLONNE_SEGN, riga, utente, audit):
                st.rerun()
    seg = out["segnalazioni"]
    st.markdown(f"##### Segnalazioni aperte ({len(seg)})")
    if not seg:
        st.success("Nessuna segnalazione aperta.")
    for s in seg[:15]:
        ico = {"bad": "🔴", "warn": "🟠", "ok": "🟢"}[s["Livello"]]
        scad = f" · entro {pd.Timestamp(s['Scadenza']).strftime('%d/%m')}" + (" (scaduta)" if s["Stato scadenza"] == "bad" else "") if s["Scadenza"] else ""
        with st.container(border=True):
            st.markdown(f"{ico} **{s['Cantiere']}** · {s['Tipo']} · gravità {s['Gravita'].lower()}{scad}  \n{s['Descrizione']}  \n<span style='color:#64748b;font-size:.85rem'>{s['Stato']}" + (f" · {s['Responsabile']}" if s["Responsabile"] else "") + "</span>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            if s["Stato"] == "Aperta" and c1.button("In corso", key=f"inc_{s['Id']}", width="stretch", disabled=sola_lettura()):
                _cambia_stato(s["Id"], "In corso", utente, audit)
            if c2.button("✅ Chiusa", key=f"chi_{s['Id']}", width="stretch", disabled=sola_lettura()):
                _cambia_stato(s["Id"], "Chiusa", utente, audit)


def _cambia_stato(id_, stato, utente, audit):
    df = ss["rp_segn"].copy()
    df.loc[df["Id"] == id_, "Stato"] = stato
    sostituisci_tabella("rp_segn", df)
    ss["_rp_toccati"] = set(ss.get("_rp_toccati", set())) | {id_}
    ok, err = _sincronizza(utente, audit)
    if not ok:
        st.warning(err)
    st.rerun()


def _cfg():
    n, t, s = st.column_config.NumberColumn, st.column_config.TextColumn, st.column_config.SelectboxColumn
    a, b = rp.ETICHETTE_RAPP, rp.ETICHETTE_SEGN
    return ({"Id": None, "Data": t(a["Data"], help="AAAA-MM-GG o GG/MM/AAAA"), "Cantiere": t(a["Cantiere"]), "Compilato_da": t(a["Compilato_da"]), "Meteo": s(a["Meteo"], options=list(rp.METEO)),
             "Presenti": n(a["Presenti"], min_value=0.0, step=1.0, format="%.0f"), "Ore": n(a["Ore"], min_value=0.0, step=1.0, format="%.0f"), "Lavorazioni": t(a["Lavorazioni"], width="large"), "Mezzi": t(a["Mezzi"]), "Note": t(a["Note"])},
            {"Id": None, "Data": t(b["Data"]), "Cantiere": t(b["Cantiere"]), "Tipo": s(b["Tipo"], options=list(rp.TIPI_SEGN)), "Gravita": s(b["Gravita"], options=list(rp.GRAVITA)),
             "Descrizione": t(b["Descrizione"], width="large"), "Responsabile": t(b["Responsabile"]), "Scadenza": t(b["Scadenza"], help="AAAA-MM-GG o GG/MM/AAAA"), "Stato": s(b["Stato"], options=list(rp.STATI_SEGN))})


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Rapportini di cantiere", "Il giornale del cantiere dal telefono: presenze, ore, lavorazioni e segnalazioni, condivise con l'ufficio in tempo reale."), unsafe_allow_html=True)
    guida.mostra("rp")
    if "rp_rapp" not in ss:
        _carica_condiviso()
    else:
        _aggiorna_se_cambiato()
    for k in PARAM:
        ss.setdefault("rp_" + k, rp.RP_DEFAULT[k])
    rapp, a1 = rp.normalizza_rapp(_records("rp_rapp"))
    segn, a2 = rp.normalizza_segn(_records("rp_segn"))
    out = rp.calcola_rp(rapp, segn, {**_params(), "oggi": rp.oggi_italia()})
    k = out["kpi"]
    if ss.get("rp_demo"):
        st.info("Esempio: il primo rapportino o la prima segnalazione che inserisci sostituisce questi dati.")
    t1, t2, t3, t4 = st.tabs(["✍️ Rapportino", "⚠️ Segnalazioni", "📊 Cantieri", "📋 Registro e dossier"])
    with t1:
        _tab_rapportino(utente, audit)
    with t2:
        _tab_segnalazioni(utente, audit, out)
    with t3:
        if not out["cantieri"]:
            st.info("Nessun rapportino negli ultimi giorni.")
        else:
            if k["cantieri_senza_rapporto"]:
                st.warning(f"**{k['cantieri_senza_rapporto']} cantieri** senza rapportino oltre la soglia.")
            else:
                st.success("Tutti i cantieri attivi hanno rapportini aggiornati.")
            st.markdown(theme.stat_strip([
                {"label": "Cantieri attivi", "value": str(k["cantieri_attivi"]), "sub": f"ultimi {out['params']['finestra_gg']} giorni", "tono": "info"},
                {"label": "Rapportini", "value": str(k["rapportini"]), "sub": f"{k['ore']:,.0f} ore".replace(",", "."), "tono": "info"},
                {"label": "Segnalazioni aperte", "value": str(k["segn_aperte"]), "sub": f"{k['segn_alte']} gravi", "tono": "bad" if k["segn_alte"] else ("warn" if k["segn_aperte"] else "ok")},
                {"label": "Senza rapportino", "value": str(k["cantieri_senza_rapporto"]), "sub": "oltre la soglia", "tono": "warn" if k["cantieri_senza_rapporto"] else "ok"}]), unsafe_allow_html=True)
            st.pyplot(charts.fig_rp_ore(out["cantieri"], "light"), clear_figure=True)
            st.dataframe(pd.DataFrame([{k2: v for k2, v in c.items() if k2 != "Stato"} for c in out["cantieri"]]), hide_index=True, width="stretch")
    with t4:
        pannello_archivio("rp", "i rapportini", _raccogli, _applica, audit, utente)
        banner_esempio("rp_demo", [("rp_rapp", rp.COLONNE_RAPP), ("rp_segn", rp.COLONNE_SEGN)], "svuota_rp")
        cr, cs = _cfg()
        blocco_tabella("rp_rapp", "Registro dei rapportini", "Correzioni e import. Per salvare le modifiche usa «Salva e riapri» qui sopra (nome «Rapportini» per il registro condiviso).",
                       rp.COLONNE_RAPP, rp.ETICHETTE_RAPP, cr, ss["rp_rapp"], "rp", 1, audit, 260)
        blocco_tabella("rp_segn", "Registro delle segnalazioni", "", rp.COLONNE_SEGN, rp.ETICHETTE_SEGN, cs, ss["rp_segn"], "rp", 2, audit, 220)
        for x in (a1 + a2)[:4]:
            st.caption("⚠️ " + x)
        st.subheader("Soglie")
        c1, c2, c3 = st.columns(3)
        c1.number_input("Giorni lavorativi senza rapportino", 1, 30, step=1, key="rp_giorni_senza_rapporto")
        c2.number_input("Preavviso scadenza segnalazioni (giorni)", 0, 60, step=1, key="rp_preavviso_gg")
        c3.number_input("Cantiere attivo se rapporto negli ultimi (giorni)", 7, 120, step=1, key="rp_finestra_gg")
        st.subheader("Dossier")
        if not rapp:
            st.info("Inserisci almeno un rapportino per generare il dossier.")
        else:
            scarica_dossier("rp", lambda n: ops_report.report_rp(out, rapp, segn, n), "Rapportini", audit, "Rapportini di cantiere")
