"""es_ui.py - Interfaccia dello strumento ESCo: diagnosi, investimento e contratto."""
import io

import pandas as pd
import streamlit as st

import es
import fv
import guida
import theme
from core import fmt_num
from ui_util import pannello_archivio, sola_lettura, sostituisci_tabella, tabella_modificabile

ss = st.session_state
_NUM = ("mq", "gg_anno", "gg_normali", "prezzo_el", "prezzo_gas", "aumento_energia_pct", "durata", "quota_esco_pct", "canone", "garantito_pct", "debito_pct", "tasso_pct", "durata_debito", "sconto_pct", "degrado_pct")
_TXT = ("cliente", "indirizzo", "uso", "modello")


def _params():
    return {k: ss.get("es_" + k, v) for k, v in es.ES_DEFAULT.items()}


def _raccogli():
    return {"bollette": ss["es_bol"].to_dict("records"), "interventi": ss["es_int"].to_dict("records"), "params": _params()}


def _applica(p, nome):
    sostituisci_tabella("es_bol", pd.DataFrame(p.get("bollette") or es.bollette_vuote(), columns=es.COLONNE_BOLLETTE))
    sostituisci_tabella("es_int", pd.DataFrame(p.get("interventi") or [], columns=es.COLONNE_INT))
    ss["_pending"] = {"es_" + k: v for k, v in (p.get("params") or {}).items() if k in es.ES_DEFAULT}


def _num(c, label, key, mn, mx, step, fmt="%.0f", help=None):
    k = "es_" + key
    ss.setdefault(k, float(es.ES_DEFAULT[key]))
    return c.number_input(label, min_value=mn, max_value=mx, step=step, key=k, format=fmt, help=help, disabled=sola_lettura())


def _da_registro():
    if sola_lettura():
        return
    try:
        import rc
        import storage
        el = storage.elenca_pratiche(modulo="rc")
        righe, _ = rc.normalizza((storage.carica_pratica(el[0]["nome"], modulo="rc") or {}).get("pratiche")) if el else ([], [])
    except Exception:
        return
    att = [r for r in righe if r["Archivio"] == "Attiva" and r["Codice"]]
    if not att:
        return
    et = [f"{r['Codice']} · {r['Indirizzo']} {r['Citta']}".strip() for r in att]
    with st.expander("🔗 Prendi cliente e indirizzo dal Registro commerciale"):
        a, b = st.columns([3, 1.4])
        sc = a.selectbox("Pratica", ["—"] + et, key="es_da_rc")
        b.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
        if sc != "—" and b.button("Compila", key="es_da_rc_ok", width="stretch"):
            r = att[et.index(sc)]
            ss["_pending"] = {"es_cliente": r.get("Amministratore") or f"Condominio {r['Indirizzo']}".strip(), "es_indirizzo": f"{r['Indirizzo']} {r['Citta']}".strip(), "es_mq": float(ss.get("es_mq") or 0)}
            st.rerun()


def _scheda_diagnosi(base):
    st.caption("Il consumo di partenza è la base di tutto: il risparmio si misura confrontando con questi numeri. Servono le bollette di 12 mesi (meglio 24-36).")
    a, b, c = st.columns(3)
    a.text_input("Cliente", key="es_cliente", disabled=sola_lettura())
    b.text_input("Indirizzo dell'immobile", key="es_indirizzo", disabled=sola_lettura())
    c.text_input("Uso (casa, uffici, capannone…)", key="es_uso", disabled=sola_lettura())
    d, e, f = st.columns(3)
    _num(d, "Superficie (m²)", "mq", 0.0, 1000000.0, 10.0)
    _num(e, "Gradi giorno dell'anno delle bollette", "gg_anno", 0.0, 4000.0, 10.0, help="Si trovano per comune sul sito ENEA/ARPA o nelle tabelle UNI 10349 e servono per togliere l'effetto dell'inverno più o meno freddo.")
    _num(f, "Gradi giorno normali della zona", "gg_normali", 0.0, 4000.0, 10.0)
    cfg = {"Mese": st.column_config.TextColumn("Mese", disabled=True), "El_kWh": st.column_config.NumberColumn("Elettricità kWh", min_value=0.0, format="%.0f"),
           "El_euro": st.column_config.NumberColumn("Elettricità €", min_value=0.0, format="%.2f"), "Gas_Smc": st.column_config.NumberColumn("Gas Smc", min_value=0.0, format="%.0f"),
           "Gas_euro": st.column_config.NumberColumn("Gas €", min_value=0.0, format="%.2f")}
    tabella_modificabile("es_bol", pd.DataFrame(es.bollette_vuote(), columns=es.COLONNE_BOLLETTE), cfg, altezza=460, num_rows="fixed")
    if not (base["mesi_el"] or base["mesi_gas"]):
        st.info("Inserisci i consumi mese per mese.")
        return
    st.markdown(theme.stat_strip([
        {"label": "Spesa annua", "value": f"{fmt_num(base['costo_annuo'])} €", "sub": f"luce {fmt_num(base['el_euro'])} € · gas {fmt_num(base['gas_euro'])} €", "tono": "info"},
        {"label": "Elettricità", "value": f"{fmt_num(base['el_kwh'])} kWh", "sub": f"{base['prezzo_el']:.3f} €/kWh medio", "tono": "ok"},
        {"label": "Gas (corretto per il clima)", "value": f"{fmt_num(base['gas_smc_corretto'])} Smc", "sub": f"{base['prezzo_gas']:.3f} €/Smc medio", "tono": "ok"},
        {"label": "Energia per m²", "value": f"{base['kwh_m2']} kWh/m²" if base["kwh_m2"] else "—", "sub": f"{fmt_num(base['kwh_totali'])} kWh totali", "tono": "info"}]), unsafe_allow_html=True)
    for x in base["avvisi"]:
        st.warning(x)


def _da_fotovoltaico():
    try:
        import storage
        nomi = [x["nome"] for x in storage.elenca_pratiche(modulo="fv")]
    except Exception:
        return
    if not nomi or sola_lettura():
        return
    a, b = st.columns([3, 1.4])
    sc = a.selectbox("Aggiungi un intervento da un Preventivo fotovoltaico salvato", ["—"] + nomi, key="es_da_fv")
    b.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
    if sc != "—" and b.button("Aggiungi", key="es_da_fv_ok", width="stretch"):
        p = storage.carica_pratica(sc, modulo="fv") or {}
        voci, _ = fv.normalizza_voci(p.get("voci"))
        par = {k: v for k, v in (p.get("params") or {}).items() if k in fv.FV_DEFAULT}
        o = fv.calcola(voci, par)
        k = o["kpi"]
        if not k["kwp"]:
            st.warning("Quel preventivo non ha un impianto.")
            return
        riga = {"Intervento": f"Impianto fotovoltaico {k['kwp']:.2f} kWp", "Tipo": "Fotovoltaico", "Investimento": k["costo"], "Risp_El_kWh": k["autoconsumo_kwh"], "Risp_Gas_Smc": 0.0,
                "Altri_ricavi": o["flusso"][0]["Cessione €"], "Manutenzione": round(k["kwp"] * float(o["params"]["manutenzione_kwp"]), 2), "Incentivo": 0.0, "Incentivo_anni": 1.0}
        att = ss["es_int"]
        sostituisci_tabella("es_int", pd.concat([att, pd.DataFrame([riga], columns=es.COLONNE_INT)], ignore_index=True))
        st.rerun()


def _scheda_investimento(base, ints, out):
    st.caption("Un intervento per riga: quanto costa all'ESCo, quanta energia fa risparmiare e quali incentivi porta. Il risparmio del gas e dell'elettricità si valuta ai prezzi della diagnosi.")
    _da_fotovoltaico()
    cfg = {"Intervento": st.column_config.TextColumn("Intervento", width="large"), "Tipo": st.column_config.SelectboxColumn("Tipo", options=es.TIPI)}
    for c in es.COLONNE_INT[2:]:
        cfg[c] = st.column_config.NumberColumn(es.ETICHETTE_INT[c], min_value=0.0, format="%.0f")
    tabella_modificabile("es_int", pd.DataFrame(columns=es.COLONNE_INT), cfg, altezza=260)
    st.markdown("**Prezzi dell'energia e contratto**")
    a, b, c, d = st.columns(4)
    _num(a, "Prezzo elettricità (€/kWh)", "prezzo_el", 0.0, 2.0, 0.01, "%.3f", "Vuoto (0) = media delle bollette.")
    _num(b, "Prezzo gas (€/Smc)", "prezzo_gas", 0.0, 5.0, 0.01, "%.3f", "Vuoto (0) = media delle bollette.")
    _num(c, "Aumento annuo energia (%)", "aumento_energia_pct", 0.0, 10.0, 0.5, "%.1f")
    _num(d, "Durata del contratto (anni)", "durata", 1.0, 30.0, 1.0)
    ss.setdefault("es_modello", es.ES_DEFAULT["modello"])
    e, f, g, h = st.columns(4)
    e.selectbox("Come si paga la ESCo", es.MODELLI, key="es_modello")
    if ss["es_modello"] == "Risparmio condiviso":
        _num(f, "Quota del risparmio alla ESCo (%)", "quota_esco_pct", 0.0, 100.0, 1.0)
    else:
        _num(f, "Canone annuo (€)", "canone", 0.0, 10000000.0, 100.0)
    _num(g, "Risparmio garantito (% dell'atteso)", "garantito_pct", 0.0, 100.0, 1.0)
    _num(h, "Degrado annuo (%)", "degrado_pct", 0.0, 5.0, 0.1, "%.1f")
    st.markdown("**Finanziamento**")
    i, j, k_, l = st.columns(4)
    _num(i, "Parte finanziata (%)", "debito_pct", 0.0, 100.0, 5.0)
    _num(j, "Tasso (%)", "tasso_pct", 0.0, 20.0, 0.25, "%.2f")
    _num(k_, "Durata del finanziamento (anni)", "durata_debito", 1.0, 30.0, 1.0)
    _num(l, "Tasso di sconto per il VAN (%)", "sconto_pct", 0.0, 30.0, 0.5, "%.1f", "Rendimento minimo che pretendi dall'investimento.")
    if not ints:
        st.info("Aggiungi almeno un intervento.")
        return
    k = out["kpi"]
    st.markdown(theme.stat_strip([
        {"label": "Investimento", "value": f"{fmt_num(k['investimento'])} €", "sub": f"finanziato {fmt_num(k['debito'])} € · rata {fmt_num(k['rata'])} €", "tono": "info"},
        {"label": "Risparmio 1° anno", "value": f"{fmt_num(k['risparmio_anno1'])} €", "sub": f"{k['risparmio_percentuale']}% della spesa" if k["risparmio_percentuale"] is not None else "", "tono": "ok"},
        {"label": "Alla ESCo (1° anno)", "value": f"{fmt_num(k['ricavo_esco_anno1'])} €", "sub": f"al cliente {fmt_num(k['al_cliente_anno1'])} €", "tono": "ok"},
        {"label": "Rientro", "value": f"{k['rientro_anni']:.1f} anni" if k["rientro_anni"] is not None else "oltre il contratto", "sub": f"VAN {fmt_num(k['van'])} €", "tono": "ok" if (k["rientro_anni"] or 99) <= out["params"]["durata"] * 0.6 else "warn"},
        {"label": "TIR", "value": f"{k['tir']}%" if k["tir"] is not None else "—", "sub": f"sul capitale proprio {k['tir_capitale_proprio']}%" if k["tir_capitale_proprio"] is not None else "", "tono": "ok" if (k["tir"] or -1) > out["params"]["sconto_pct"] else "bad"},
        {"label": "Copertura del debito", "value": f"{k['dscr_min']:.2f}" if k["dscr_min"] else "—", "sub": f"media {k['dscr_medio']:.2f}" if k["dscr_medio"] else "nessun debito", "tono": "ok" if (k["dscr_min"] or 9) >= 1.2 else "bad"}]), unsafe_allow_html=True)
    for x in out["avvisi"]:
        st.warning(x)
    df = pd.DataFrame(out["flusso"])
    st.line_chart(df.set_index("Anno")[["Cumulato ESCo €"]], height=240)
    with st.expander("Anno per anno"):
        st.dataframe(df, hide_index=True, width="stretch")
    st.caption("Valori al lordo delle imposte e senza inflazione sui costi di manutenzione: va confrontato con il piano economico-finanziario del commercialista.")


def _scheda_contratto(base, ints, out):
    if not ints:
        st.info("Completa prima diagnosi e interventi.")
        return
    sez = es.bozza_epc(_params(), ints, base, out)
    st.caption("Bozza di contratto di prestazione energetica (EPC) con i numeri del tuo piano. Le parti tra [parentesi quadre] vanno completate; fai rivedere il testo da un legale.")
    for t, pars in sez:
        with st.expander(t):
            for p in pars:
                st.write(p)
    st.download_button("📥 Scarica la bozza in Word", es.docx_epc(sez), file_name="bozza_contratto_epc.docx", key="dl_es_docx",
                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame([(k, v) for k, v in {**{f"Partenza - {k}": v for k, v in base.items() if k != "avvisi"}, **{f"Piano - {k}": v for k, v in out["kpi"].items()}}.items()], columns=["Dato", "Valore"]).to_excel(w, sheet_name="Riepilogo", index=False)
        pd.DataFrame(ints).to_excel(w, sheet_name="Interventi", index=False)
        pd.DataFrame(out["flusso"]).to_excel(w, sheet_name="Anno per anno", index=False)
    st.download_button("📥 Scarica il piano in Excel", buf.getvalue(), file_name="piano_esco.xlsx", key="dl_es_xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "ESCo: efficienza energetica", "Consumi di partenza, piano dell'investimento e bozza del contratto di prestazione energetica."), unsafe_allow_html=True)
    guida.mostra("es")
    if "es_bol" not in ss:
        ss["es_bol"] = pd.DataFrame(es.bollette_vuote(), columns=es.COLONNE_BOLLETTE)
    if "es_int" not in ss:
        ss["es_int"] = pd.DataFrame(columns=es.COLONNE_INT)
    pannello_archivio("es", "il piano ESCo", _raccogli, _applica, audit, utente)
    _da_registro()
    base = es.situazione_di_partenza(ss["es_bol"].to_dict("records"), _params())
    ints, av = es.normalizza_interventi(ss["es_int"].to_dict("records"))
    out = es.modello(ints, base, _params())
    t1, t2, t3 = st.tabs(["🔎 1. Diagnosi e consumi", "💶 2. Interventi e investimento", "📄 3. Contratto EPC"])
    with t1:
        _scheda_diagnosi(base)
    with t2:
        _scheda_investimento(base, ints, out)
        for a in av[:3]:
            st.caption("⚠️ " + a)
    with t3:
        _scheda_contratto(base, ints, out)
