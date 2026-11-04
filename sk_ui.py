"""sk_ui.py - Interfaccia della Scheda cantiere: scegli un cantiere e vedi in un colpo solo entrate, uscite, costi, SAL e rapportini."""
import datetime as dt

import pandas as pd
import streamlit as st

import archivio
import bk_ui
import guida
import mc
import nuovi_ui
import rp_ui
import ru
import ru_ui
import sc_ui
import sk
import storage
import theme
from core import fmt_num

ss = st.session_state
EUR = lambda x: f"{fmt_num(x)} €"
ICONE = {"ok": "🟢", "warn": "🟡", "bad": "🔴", "nd": "⚪"}
# strumento -> (chiave della tabella in sessione, bandiera «dati di esempio», funzione che raccoglie i dati, nome del salvataggio o None per «il piu' recente»)
FONTI = {"bk": ("bk_mov", "bk_demo", lambda: bk_ui._raccogli(), None), "ru": ("ru_can", "ru_demo", lambda: ru_ui._raccogli(), None), "sc": ("sc_df", "sc_demo", lambda: sc_ui._raccogli(), None),
         "rp": ("rp_rapp", "rp_demo", lambda: rp_ui._dati(), rp_ui.NOME)}
NOMI = {"bk": "Conti correnti", "ru": "Rubrica", "sc": "Scadenzario", "rp": "Rapportini", "sl": "SAL", "sa": "Subappalti", "pr": "Presenze", "mt": "Materiali", "mz": "Mezzi"}


def _payload(m):
    if m in nuovi_ui._CHIAVI:
        return nuovi_ui._payload(m)
    chiave, demo, raccogli, nome = FONTI[m]
    if chiave in ss:
        return (None, "esempi esclusi") if ss.get(demo) else (raccogli(), "sessione")
    try:
        if nome:
            p = storage.carica_pratica(nome, modulo=m)
            if p:
                return p, f"salvataggio «{nome}»"
        else:
            el = storage.elenca_pratiche(modulo=m)
            if el:
                return storage.carica_pratica(el[0]["nome"], modulo=m), f"salvataggio «{el[0]['nome']}»"
    except Exception:
        pass
    return None, "nessun dato"


def carica():
    pay, fonti = {}, {}
    for m in NOMI:
        pay[m], fonti[m] = _payload(m)
    return {m: v for m, v in pay.items() if v}, fonti


def _etichetta(s):
    return f"{s['Codice'] + ' · ' if s['Codice'] else ''}{s['Cantiere']} ({s['Stato']})"


def _tab_conti(s):
    a, u = s["entrate"], s["uscite"]
    st.markdown(theme.stat_strip([
        {"label": "Fatturato (attive)", "value": EUR(a["totale"]), "sub": f"{a['n']} fatture", "tono": "info"},
        {"label": "Incassato", "value": EUR(a["regolato"]), "sub": f"da incassare {EUR(a['residuo'])}", "tono": "ok"},
        {"label": "Scaduto da incassare", "value": EUR(a["scaduto"]), "sub": "", "tono": "bad" if a["scaduto"] > 0 else "ok"},
        {"label": "Fatture passive", "value": EUR(u["totale"]), "sub": f"{u['n']} fatture", "tono": "info"},
        {"label": "Pagato", "value": EUR(u["regolato"]), "sub": f"da pagare {EUR(u['residuo'])}", "tono": "ok"},
        {"label": "Cassa del cantiere", "value": EUR(s["cassa"]), "sub": "incassato − pagato", "tono": "bad" if s["cassa"] < 0 else "ok"}]), unsafe_allow_html=True)
    cols = ["Documento", "Controparte", "Data_doc", "Scadenza", "Importo", "Saldato"]
    etich = {"Documento": "N. documento", "Controparte": "Cliente / fornitore", "Data_doc": "Data", "Scadenza": "Scadenza", "Importo": "Importo (€)", "Saldato": "Incassato / pagato (€)"}
    for titolo, righe in (("Entrate: fatture ai clienti", s["attive"]), ("Uscite: fatture dei fornitori", s["passive"])):
        st.markdown(f"##### {titolo}")
        if righe:
            df = pd.DataFrame(righe)[cols].rename(columns=etich)
            df["Residuo (€)"] = df["Importo (€)"] - df["Incassato / pagato (€)"]
            st.dataframe(df, hide_index=True, width="stretch")
        else:
            st.caption("Nessuna fattura per questo cantiere. Nello Scadenzario scrivi il cantiere con lo stesso nome o codice della Rubrica.")


def _tab_costi(s):
    if not s["costi"]:
        st.info("Nessun costo registrato per questo cantiere. I costi arrivano da SAL, Subappalti, Presenze e ore, Materiali e Mezzi: in ognuno scrivi il cantiere come nella Rubrica.")
        return
    righe = [{"Voce": k, "Importo (€)": round(v, 2)} for k, v in sorted(s["costi"].items(), key=lambda kv: -kv[1])]
    righe.append({"Voce": "Totale costi", "Importo (€)": round(s["costi_totali"], 2)})
    st.dataframe(pd.DataFrame(righe), hide_index=True, width="stretch")
    st.caption("I costi di subappalti, ore, materiali e mezzi sono contati una volta sola, anche se sono stati mandati anche a SAL.")


def _tab_sal(s):
    c = s["contratto"]
    if not c:
        st.info("Questo cantiere non ha ancora il contratto in «SAL e contabilità lavori». Aggiungilo lì (con lo stesso nome o codice) per vedere avanzamento e margine finale.")
    else:
        st.markdown(theme.stat_strip([
            {"label": "Contratto", "value": EUR(c["contratto"]), "sub": f"avanzamento {fmt_num(c['avanzamento'], 1)}%", "tono": "info"},
            {"label": "Margine finale stimato", "value": f"{fmt_num(c['margine_finale_pct'], 1)}%", "sub": f"preventivato {fmt_num(c['margine_atteso_pct'], 1)}%", "tono": c["stato"] if c["stato"] in ("ok", "warn", "bad") else "info"},
            {"label": "Costi a finire", "value": EUR(c["costi_a_finire"]), "sub": "stima di gestione", "tono": "info"}]), unsafe_allow_html=True)
    st.caption(f"SAL emessi: {s['sal']['emessi']} · incassato sui SAL: {EUR(s['sal']['incassato'])}")


def _tab_conti_correnti(s):
    if not s["conti"]:
        st.info("Nessun conto corrente per questo cantiere. In «Riconciliazione bancaria» aggiungi il conto e nella colonna Cantiere scegli questo cantiere.")
        return
    righe = [{"Conto": x["conto"]["Conto"], "Banca": x["conto"]["Banca"], "Saldo": x["saldo"], "Fido": x["fido"], "Disponibile": x["disponibile"], "Debiti": x["debito_residuo"],
              "Rate nel periodo": x["rate_periodo"], "Minimo previsto": x["minimo"]["Saldo previsto"] if x["minimo"] else 0.0,
              "Allarme": "🔴" if x["primo_sotto_zero"] and x["primo_sotto_zero"]["Stato"] == "bad" else ("🟡" if x["primo_sotto_zero"] else "🟢")} for x in s["conti"]]
    st.dataframe(pd.DataFrame(righe).round(0), hide_index=True, width="stretch")
    for x in s["conti"]:
        for a in x["avvisi"]:
            st.warning(f"{x['conto']['Conto']}: {a}")
    st.caption("Il prospetto completo di ogni conto, con la previsione settimana per settimana, è in «Riconciliazione bancaria», scheda «Prospetto per conto».")


def _tab_subappalti(s):
    if not s["subappalti"]:
        st.info("Nessun subappaltatore su questo cantiere. In «Subappalti» scrivi il contratto con questo cantiere nella colonna Commessa.")
        return
    righe = [{"Subappaltatore": d["Subappaltatore"], "Lavorazione": d["Lavorazione"], "Contratto": d["Contratto"], "SAL lordi": d["SAL lordi"], "Avanz. %": round(d["Avanzamento %"], 1),
              "Ritenute": d["Ritenute"], "Pagato": d["Pagato"], "Da pagare": d["Da pagare"], "Documenti": ICONE[d["Documenti"]], "Lavora anche su": d["Altri_cantieri"] or "—"} for d in s["subappalti"]]
    st.dataframe(pd.DataFrame(righe).round(0), hide_index=True, width="stretch")
    st.caption("Qui vedi solo i contratti di questo cantiere. Documenti obbligatori (DURC, polizze) valgono per il subappaltatore su tutti i suoi cantieri.")


def _tab_rapportini(s):
    if not s["rapporti"] and not s["segnalazioni_aperte"]:
        st.info("Nessun rapportino per questo cantiere.")
        return
    g = s["giorni_senza_rapporto"]
    st.markdown(theme.stat_strip([
        {"label": "Rapportini", "value": str(s["rapporti"]), "sub": f"{fmt_num(s['ore'], 0)} ore in tutto", "tono": "info"},
        {"label": "Ultimo rapportino", "value": s["ultimo_rapporto"].strftime("%d/%m/%Y") if s["ultimo_rapporto"] else "—",
         "sub": "" if g is None else f"{g} giorni lavorativi fa", "tono": "ok" if (g is not None and g <= 2) else "warn" if (g is not None and g <= 5) else "bad"},
        {"label": "Segnalazioni aperte", "value": str(s["segnalazioni_aperte"]), "sub": "", "tono": "bad" if s["segnalazioni_aperte"] else "ok"}]), unsafe_allow_html=True)


def _tab_cartelle(s):
    """Dove stanno i file di questo cantiere sul NAS, con il percorso da incollare in Esplora file."""
    ps = archivio.percorsi(s)
    if not ps:
        st.info("Manca il nome del cantiere.")
        return
    st.caption(f"Cartelle del cantiere **{archivio.nome_cantiere(s)}** sul NAS. Copia il percorso (icona a destra) e incollalo nella barra di Esplora file di Windows: "
               "funziona dal computer dell'ufficio, collegato alla rete aziendale.")
    for p in ps:
        c1, c2 = st.columns([1, 4])
        stato = "" if p["esiste"] is None else (" ✅" if p["esiste"] else " ➖ da creare")
        c1.markdown(f"**{p['area']}**{stato}  \n<span style='font-size:.8rem;opacity:.7'>{p['chi']}</span>", unsafe_allow_html=True)
        c2.code(p["unc"], language=None)
    if archivio.montato():
        mancanti = [p for p in ps if not p["esiste"]]
        if st.button(f"Crea le {len(mancanti)} cartelle mancanti", key="sk_crea_cartelle", disabled=not mancanti):
            try:
                n, v = archivio.crea_cartelle(s)
                st.success(f"Create {n} cartelle ({v} già c'erano).")
                st.rerun()
            except OSError as e:
                st.error(str(e))
    else:
        st.caption("Le cartelle si creano a mano in File Station con questo nome. Quando il NAS sarà collegato al server, qui comparirà il pulsante per crearle in automatico.")
    with st.expander("📋 La struttura delle cartelle e le regole"):
        st.markdown("**Regole**: massimo 3 livelli (area → cantiere → file). La cartella di ogni cantiere si chiama **`CODICE - Nome`**, "
                    "con il codice usato in azienda (campo «codice in altro sistema» della Rubrica) o, se manca, quello della Rubrica.")
        st.dataframe(pd.DataFrame([{"Cartella": archivio.NOME_AREA[a[0]], "Una per cantiere": "sì" if a[2] else "no", "Chi": a[3], "Cosa ci va": a[4]} for a in archivio.AREE]), hide_index=True, width="stretch")


def _tutti(schede):
    righe = [{"Codice": s["Codice"], "Cantiere": s["Cantiere"], "Stato": s["Stato"], "Fatturato": round(s["fatturato"]), "Incassato": round(s["entrate"]["regolato"]),
              "Da incassare": round(s["entrate"]["residuo"]), "Costi": round(s["costi_totali"]), "Margine corrente": round(s["margine_corrente"]), "Cassa": round(s["cassa"]),
              "Rapportini": s["rapporti"], "Giorni senza rapportino": s["giorni_senza_rapporto"]} for s in schede]
    return righe


def render(fcr_uri, audit=None, utente=""):
    st.markdown(theme.hero(fcr_uri, "Scheda cantiere", "Per ogni cantiere: entrate e uscite, fatture, costi, SAL e rapportini, tutto in un posto."), unsafe_allow_html=True)
    guida.mostra("sk")
    pay, fonti = carica()
    st.caption("Dati letti da: " + " · ".join(f"{NOMI[m]}: {fonti[m]}" for m in NOMI))
    if not pay.get("ru"):
        st.info("Per cominciare serve l'elenco dei cantieri nella **Rubrica e cantieri**: ogni cantiere ha un codice (CAN-anno-numero) e uno stato. "
                "Poi negli altri strumenti scrivi il cantiere con lo stesso nome o codice.")
    out = sk.calcola_sk(pay, dt.date.today())
    k = out["kpi"]
    st.markdown(theme.stat_strip([
        {"label": "Cantieri vivi", "value": str(k["vivi"]), "sub": f"{k['cantieri']} in Rubrica", "tono": "info"},
        {"label": "Fatturato (vivi)", "value": EUR(k["fatturato_vivi"]), "sub": f"da incassare {EUR(k['da_incassare_vivi'])}", "tono": "info"},
        {"label": "Costi (vivi)", "value": EUR(k["costi_vivi"]), "sub": f"fatture da pagare {EUR(k['da_pagare_vivi'])}", "tono": "info"},
        {"label": "Non in Rubrica", "value": str(k["non_in_rubrica"]), "sub": "nomi da correggere", "tono": "warn" if k["non_in_rubrica"] else "ok"}]), unsafe_allow_html=True)
    if out["avvisi"]:
        with st.expander(f"⚠️ {len(out['avvisi'])} cose da sistemare"):
            for a in out["avvisi"][:20]:
                st.write("• " + a)
    tutti = st.toggle("Mostra anche cantieri sospesi o conclusi", key="sk_tutti", value=False)
    schede = [s for s in out["schede"] if tutti or s["vivo"] or not s["in_rubrica"]]
    if not schede:
        st.info("Nessun cantiere vivo. Nella Rubrica metti lo stato «In corso» al cantiere, oppure attiva «Mostra anche cantieri sospesi o conclusi».")
        return
    nomi = [_etichetta(s) for s in schede]
    scelto = st.selectbox("Cantiere", nomi, key="sk_sel")
    s = schede[nomi.index(scelto)] if scelto in nomi else schede[0]
    st.caption(" · ".join(x for x in (f"Cliente: {s['Cliente']}" if s["Cliente"] else "", f"Responsabile: {s['Responsabile']}" if s["Responsabile"] else "", f"Stato: {s['Stato']}") if x))
    t = s["contratto"]
    st.markdown(theme.stat_strip([
        {"label": "Fatturato", "value": EUR(s["fatturato"]), "sub": f"incassato {EUR(s['entrate']['regolato'])}", "tono": "info"},
        {"label": "Costi sostenuti", "value": EUR(s["costi_totali"]), "sub": "materiali, ore, mezzi, subappalti", "tono": "info"},
        {"label": "Margine corrente", "value": EUR(s["margine_corrente"]), "sub": "fatturato − costi", "tono": "bad" if s["margine_corrente"] < 0 else "ok"},
        {"label": "Contratto", "value": EUR(t["contratto"]) if t else "—", "sub": f"avanzamento {fmt_num(t['avanzamento'], 1)}%" if t else "non in SAL", "tono": "info"}]), unsafe_allow_html=True)
    t1, t2, t3, t5, t6, t4, t7 = st.tabs(["💶 Entrate e uscite", "🧱 Costi", "📋 SAL e margine", "🤝 Subappaltatori", "🏦 Conti correnti", "✍️ Rapportini", "📁 Cartelle"])
    with t1:
        _tab_conti(s)
    with t2:
        _tab_costi(s)
    with t3:
        _tab_sal(s)
    with t5:
        _tab_subappalti(s)
    with t6:
        _tab_conti_correnti(s)
    with t4:
        _tab_rapportini(s)
    with t7:
        _tab_cartelle(s)
    st.subheader("Tutti i cantieri a confronto")
    righe = _tutti(schede)
    st.dataframe(pd.DataFrame(righe), hide_index=True, width="stretch")
    st.caption("Margine corrente = fatture attive − costi sostenuti. Cassa = incassato − pagato sulle fatture. Sono dati di gestione presi dagli altri strumenti, non un bilancio.")
    st.download_button("📥 Scarica in Excel", nuovi_ui._xlsx({"Cantieri": righe, **{(f"{x['Codice'] or 'X'}")[:31]: [{"Voce": a, "Importo": round(b, 2)} for a, b in x["costi"].items()] for x in schede[:20]}}),
                       file_name=f"cantieri_{dt.date.today().isoformat()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dlx_sk")
