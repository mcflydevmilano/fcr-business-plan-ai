"""fv_ui.py - Interfaccia di Preventivo fotovoltaico."""
import io

import pandas as pd
import streamlit as st

import fv
import guida
import theme
from core import fmt_num
from ui_util import pannello_archivio, sola_lettura, sostituisci_tabella, tabella_modificabile

ss = st.session_state
_P = ("regime", "orientamento", "inclinazione", "ombra_pct", "zona", "resa", "wp_modulo", "n_moduli", "accumulo_kwh", "consumo", "prezzo_acquisto", "prezzo_cessione",
      "autoconsumo_pct", "aumento_energia_pct", "degrado_pct", "manutenzione_kwp", "ricarico_pct", "iva_pct", "detrazione_pct", "detrazione_anni", "anni")
_CAMPI = ("fv_cliente", "fv_indirizzo", "fv_note", "fv_modello_moduli", "fv_modello_inverter", "fv_modello_batteria", "fv_garanzia_moduli", "fv_garanzia_inverter")


def _params():
    return {k: ss.get("fv_" + k, v) for k, v in fv.FV_DEFAULT.items()}


def _raccogli():
    return {"voci": ss["fv_df"].to_dict("records"), "params": _params(), "campi": {k: ss.get(k) for k in _CAMPI}, "listino": ss["fv_list"].to_dict("records")}


def _applica(p, nome):
    sostituisci_tabella("fv_df", pd.DataFrame(p.get("voci") or [], columns=fv.COLONNE_VOCI))
    sostituisci_tabella("fv_list", pd.DataFrame(p.get("listino") or [], columns=fv.COLONNE_LISTINO))
    pend = {"fv_" + k: v for k, v in (p.get("params") or {}).items() if k in fv.FV_DEFAULT}
    pend.update({k: v for k, v in (p.get("campi") or {}).items() if k in _CAMPI and v is not None})
    ss["_pending"] = pend


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
        sc = a.selectbox("Pratica", ["—"] + et, key="fv_da_rc")
        b.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
        if sc != "—" and b.button("Compila", key="fv_da_rc_ok", width="stretch"):
            r = att[et.index(sc)]
            ss["_pending"] = {"fv_cliente": r.get("Amministratore") or r["Codice"], "fv_indirizzo": f"{r['Indirizzo']} {r['Citta']}".strip()}
            st.rerun()


def _num(c, label, key, mn, mx, step, fmt="%.2f", help=None):
    k = "fv_" + key
    ss.setdefault(k, float(fv.FV_DEFAULT[key]))
    return c.number_input(label, min_value=mn, max_value=mx, step=step, key=k, format=fmt, help=help, disabled=sola_lettura())


def _scheda_impianto():
    st.caption("Chi è il cliente e com'è fatto il tetto. I valori di partenza sono medie italiane: correggili con quelli del sopralluogo.")
    a, b = st.columns(2)
    a.text_input("Cliente", key="fv_cliente", disabled=sola_lettura())
    b.text_input("Indirizzo dell'impianto", key="fv_indirizzo", disabled=sola_lettura())
    c1, c2, c3 = st.columns(3)
    ss.setdefault("fv_orientamento", fv.FV_DEFAULT["orientamento"])
    ss.setdefault("fv_inclinazione", fv.FV_DEFAULT["inclinazione"])
    ss.setdefault("fv_zona", fv.FV_DEFAULT["zona"])
    c1.selectbox("Orientamento della falda", list(fv.ORIENTAMENTI), key="fv_orientamento")
    c2.selectbox("Inclinazione", list(fv.INCLINAZIONI), key="fv_inclinazione")
    zona = c3.selectbox("Zona d'Italia", list(fv.ZONE), key="fv_zona")
    c4, c5, c6 = st.columns(3)
    if "fv_resa" not in ss:
        ss["fv_resa"] = fv.ZONE[zona]
    if ss.get("_fv_zona_prec") != zona:
        if ss.get("_fv_zona_prec") is not None:
            ss["fv_resa"] = fv.ZONE[zona]
        ss["_fv_zona_prec"] = zona
    _num(c4, "Resa (kWh per kWp all'anno)", "resa", 700.0, 1900.0, 10.0, "%.0f", "Quanto produce ogni kWp in un anno con orientamento ideale. Nord ≈ 1.100, Centro ≈ 1.250, Sud ≈ 1.400.")
    _num(c5, "Perdita per ombre (%)", "ombra_pct", 0.0, 80.0, 1.0, "%.0f")
    c6.markdown("")
    d1, d2, d3 = st.columns(3)
    _num(d1, "Numero di moduli", "n_moduli", 0.0, 500.0, 1.0, "%.0f")
    _num(d2, "Potenza di un modulo (Wp)", "wp_modulo", 250.0, 800.0, 5.0, "%.0f")
    _num(d3, "Batteria di accumulo (kWh)", "accumulo_kwh", 0.0, 100.0, 0.5, "%.1f")
    st.markdown("**Prodotti scelti** (compaiono nel preventivo)")
    e1, e2, e3 = st.columns(3)
    e1.text_input("Moduli (marca e modello)", key="fv_modello_moduli", disabled=sola_lettura())
    e2.text_input("Inverter (marca e modello)", key="fv_modello_inverter", disabled=sola_lettura())
    e3.text_input("Batteria (marca e modello)", key="fv_modello_batteria", disabled=sola_lettura())
    f1, f2 = st.columns(2)
    f1.text_input("Garanzia moduli", key="fv_garanzia_moduli", placeholder="es. 25 anni sul prodotto, 30 sulla resa", disabled=sola_lettura())
    f2.text_input("Garanzia inverter", key="fv_garanzia_inverter", placeholder="es. 10 anni", disabled=sola_lettura())
    st.markdown("**Consumi e prezzi dell'energia**")
    g1, g2, g3, g4 = st.columns(4)
    _num(g1, "Consumo annuo (kWh)", "consumo", 0.0, 500000.0, 100.0, "%.0f", "Dalla bolletta: somma dei kWh dei 12 mesi.")
    _num(g2, "Prezzo che paga oggi (€/kWh)", "prezzo_acquisto", 0.05, 1.0, 0.01)
    _num(g3, "Prezzo di cessione (€/kWh)", "prezzo_cessione", 0.0, 0.5, 0.005, "%.3f", "Ritiro dedicato GSE: circa 0,10 €/kWh (prezzo zonale), da verificare.")
    _num(g4, "Aumento annuo energia (%)", "aumento_energia_pct", 0.0, 10.0, 0.5, "%.1f")
    h1, h2 = st.columns([3, 1.4])
    _num(h1, "Quota di energia consumata in casa (%)", "autoconsumo_pct", 0.0, 100.0, 1.0, "%.0f", "Il resto va in rete. Senza batteria è di solito 30-40%, con batteria fino a 70-80%.")
    h2.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
    sug = fv.autoconsumo_suggerito(_params())
    if h2.button(f"Usa il valore stimato ({sug:.0f}%)", key="fv_aut_sug", disabled=sola_lettura() or not sug, width="stretch"):
        ss["_pending"] = {"fv_autoconsumo_pct": float(sug)}
        st.rerun()


def _scheda_costi():
    st.caption("I costi sono quelli che paghi tu (IVA esclusa). Il prezzo al cliente si ottiene aggiungendo il ricarico. I valori proposti sono stime: sostituiscili con il tuo listino.")
    c1, c2 = st.columns(2)
    if c1.button("↻ Proponi le voci per questa potenza", key="fv_voci_std", disabled=sola_lettura(), help="Sostituisce la tabella con le voci standard per numero di moduli e batteria indicati."):
        sostituisci_tabella("fv_df", pd.DataFrame(fv.voci_standard(_params()), columns=fv.COLONNE_VOCI))
        st.rerun()
    lst = [r for r in ss["fv_list"].to_dict("records") if str(r.get("Descrizione") or "").strip()]
    if lst and not sola_lettura():
        et = [f"{r.get('Descrizione', '')} · {fmt_num(float(r.get('Costo_unit') or 0))} €/{r.get('Um', '')}".strip(" /") for r in lst]
        sc = c2.selectbox("Aggiungi una voce dal listino", ["—"] + et, key="fv_add_list")
        if sc != "—" and c2.button("Aggiungi alla tabella", key="fv_add_list_ok"):
            r = lst[et.index(sc)]
            riga = pd.DataFrame([{"Voce": r["Descrizione"], "Quantita": 1.0, "Um": r.get("Um", ""), "Costo_unit": float(r.get("Costo_unit") or 0)}], columns=fv.COLONNE_VOCI)
            sostituisci_tabella("fv_df", pd.concat([ss["fv_df"], riga], ignore_index=True))
            st.rerun()
    cfg = {"Voce": st.column_config.TextColumn("Voce", width="large"), "Quantita": st.column_config.NumberColumn("Quantità", min_value=0.0, format="%.2f"),
           "Um": st.column_config.TextColumn("U.M.", width="small"), "Costo_unit": st.column_config.NumberColumn("Costo unitario €", min_value=0.0, format="%.2f")}
    tabella_modificabile("fv_df", pd.DataFrame(columns=fv.COLONNE_VOCI), cfg, altezza=330)
    st.markdown("**Prezzo al cliente e fisco**")
    ss.setdefault("fv_regime", fv.FV_DEFAULT["regime"])
    prec = ss.get("_fv_regime_prec")
    r = st.selectbox("Chi compra", list(fv.REGIMI), key="fv_regime")
    if prec is not None and prec != r:                       # cambiando regime si aggiornano detrazione e IVA, poi restano modificabili
        ss["fv_detrazione_pct"], ss["fv_iva_pct"] = fv.REGIMI[r]["detrazione_pct"], fv.REGIMI[r]["iva_pct"]
    ss["_fv_regime_prec"] = r
    ss.setdefault("fv_detrazione_pct", fv.REGIMI[r]["detrazione_pct"])
    ss.setdefault("fv_iva_pct", fv.REGIMI[r]["iva_pct"])
    a, b, c, d = st.columns(4)
    _num(a, "Ricarico sui costi (%)", "ricarico_pct", 0.0, 200.0, 1.0, "%.0f", "Spese generali e utile insieme, applicati ai costi.")
    _num(b, "IVA (%)", "iva_pct", 0.0, 22.0, 1.0, "%.0f")
    _num(c, "Detrazione (%)", "detrazione_pct", 0.0, 110.0, 1.0, "%.0f", "Detrazione IRPEF in 10 quote annuali: 50% prima casa, 36% altre abitazioni (tetto 96.000 € di spesa).")
    _num(d, "Manutenzione (€/kWp all'anno)", "manutenzione_kwp", 0.0, 100.0, 1.0, "%.0f")


def _scheda_listino():
    st.caption("Carica il listino del fornitore (Excel o CSV) così com'è: la suite trova da sola la riga delle intestazioni e le colonne Descrizione, Prezzo, Codice, U.M., Fornitore.")
    if not sola_lettura():
        up = st.file_uploader("Listino prezzi (.xlsx, .csv)", type=["xlsx", "xls", "csv"], key="fv_up_list")
        if up is not None:
            righe, av = fv.leggi_listino(up.getvalue(), up.name)
            for a in av[:3]:
                st.warning(a)
            if righe:
                st.success(f"Lette {len(righe)} righe di listino.")
                a, b = st.columns(2)
                if a.button("Aggiungi al listino", type="primary", key="fv_list_add"):
                    sostituisci_tabella("fv_list", pd.concat([ss["fv_list"], pd.DataFrame(righe, columns=fv.COLONNE_LISTINO)], ignore_index=True))
                    st.rerun()
                if b.button("Sostituisci il listino", key="fv_list_sost"):
                    sostituisci_tabella("fv_list", pd.DataFrame(righe, columns=fv.COLONNE_LISTINO))
                    st.rerun()
    cfg = {"Descrizione": st.column_config.TextColumn("Descrizione", width="large"), "Costo_unit": st.column_config.NumberColumn("Costo €", min_value=0.0, format="%.2f")}
    tabella_modificabile("fv_list", pd.DataFrame(columns=fv.COLONNE_LISTINO), cfg, altezza=320)


def _scheda_risultato(out, audit):
    k = out["kpi"]
    if not k["kwp"]:
        st.info("Indica numero e potenza dei moduli nella scheda «1. Impianto».")
        return
    st.markdown(theme.stat_strip([
        {"label": "Impianto", "value": f"{k['kwp']:.2f} kWp", "sub": f"{fmt_num(k['produzione'])} kWh/anno", "tono": "info"},
        {"label": "Prezzo (IVA esclusa)", "value": f"{fmt_num(k['imponibile'])} €", "sub": f"{fmt_num(k['per_kwp'])} €/kWp", "tono": "ok"},
        {"label": "Totale con IVA", "value": f"{fmt_num(k['totale'])} €", "sub": f"dopo detrazione {fmt_num(k['netto_detrazione'])} €", "tono": "ok"},
        {"label": "Rientro", "value": f"{k['rientro_anni']:.1f} anni" if k["rientro_anni"] is not None else "oltre il periodo", "sub": f"risparmio 1° anno {fmt_num(k['risparmio_anno1'])} €", "tono": "warn" if (k["rientro_anni"] or 99) > 9 else "ok"}]), unsafe_allow_html=True)
    for a in out["avvisi"]:
        st.warning(a)
    st.markdown(f"Il cliente copre circa **{k['copertura_pct']:.0f}%** dei suoi consumi con l'energia prodotta. Margine dell'impresa: **{fmt_num(k['margine'])} €**. Dopo {out['params']['anni']} anni il guadagno cumulato è di **{fmt_num(k['guadagno_finale'])} €**.")
    df = pd.DataFrame(out["flusso"])
    st.line_chart(df.set_index("Anno")[["Cumulato €"]], height=240)
    with st.expander("Anno per anno"):
        st.dataframe(df, hide_index=True, width="stretch")
    st.caption("Stime indicative: la resa reale dipende da ombre, sporco, temperatura e meteo; i prezzi dell'energia e la detrazione vanno verificati alla data del contratto.")


def _scheda_documenti(out, audit):
    k = out["kpi"]
    if not k["kwp"]:
        st.info("Completa prima l'impianto.")
        return
    if not sola_lettura():
        st.markdown("**Porta il prezzo nell'Offerta**")
        st.caption("Aggiunge una voce «Impianto fotovoltaico» alle voci dell'Offerta e finanziamenti (sostituisce quella già inviata da qui).")
        if st.button("➡️ Metti l'impianto nell'Offerta", key="fv_to_of"):
            import of_ui
            nome = f"Impianto fotovoltaico {k['kwp']:.2f} kWp"
            riga = {"Cap": "FV", "Cod": "FV", "Descrizione": nome, "UM": "a corpo", "Quantita": 1.0, "Prezzo": k["imponibile"], "Ipotesi": ""}
            att = ss["of_voci"] if "of_voci" in ss else pd.DataFrame(columns=of_ui.DF["of_voci"])
            if len(att):
                att = att[att["Cap"].astype(str) != "FV"]
            sostituisci_tabella("of_voci", pd.concat([att, of_ui._df("of_voci", [riga])], ignore_index=True))
            audit("fv_to_of", f"{nome} · {fmt_num(k['imponibile'])} €")
            st.success(f"Inserito nell'Offerta: {nome}, {fmt_num(k['imponibile'])} € IVA esclusa.")
    righe = [("Cliente", ss.get("fv_cliente", "")), ("Indirizzo", ss.get("fv_indirizzo", "")), ("Potenza", f"{k['kwp']:.2f} kWp"), ("Moduli", f"{ss.get('fv_n_moduli', 0):.0f} x {ss.get('fv_wp_modulo', 0):.0f} Wp {ss.get('fv_modello_moduli', '')}".strip()),
             ("Inverter", ss.get("fv_modello_inverter", "")), ("Batteria", f"{ss.get('fv_accumulo_kwh', 0):.1f} kWh {ss.get('fv_modello_batteria', '')}".strip()), ("Produzione annua stimata", f"{k['produzione']} kWh"),
             ("Imponibile", k["imponibile"]), ("IVA", k["iva"]), ("Totale", k["totale"]), ("Detrazione totale", k["detrazione"]), ("Costo netto dopo detrazione", k["netto_detrazione"]),
             ("Rientro (anni)", k["rientro_anni"] if k["rientro_anni"] is not None else ""), ("Garanzia moduli", ss.get("fv_garanzia_moduli", "")), ("Garanzia inverter", ss.get("fv_garanzia_inverter", ""))]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame(righe, columns=["Dato", "Valore"]).to_excel(w, sheet_name="Riepilogo", index=False)
        pd.DataFrame(fv.normalizza_voci(ss["fv_df"].to_dict("records"))[0]).to_excel(w, sheet_name="Costi", index=False)
        pd.DataFrame(out["flusso"]).to_excel(w, sheet_name="Anno per anno", index=False)
    st.download_button("📥 Scarica il preventivo in Excel", buf.getvalue(), file_name="preventivo_fotovoltaico.xlsx", key="dl_fv_xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with st.expander("Promemoria per il cliente (da ricordare nel contratto)"):
        st.markdown("- Detrazione IRPEF in 10 quote annuali: serve il **bonifico parlante** e la **comunicazione ENEA entro 90 giorni** dalla fine dei lavori.\n"
                    "- Pratiche di connessione e GSE: di solito alcune settimane dopo la fine dei lavori.\n- Garanzie distinte per moduli e inverter, collaudo e responsabile dopo la messa in esercizio.\n"
                    "- Vendita fuori dai locali commerciali: inserire il modulo di recesso e i dati completi dell'impresa.")


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Preventivo fotovoltaico", "Dal tetto del cliente al prezzo: costi, ricarico, detrazione, produzione e tempo di rientro."), unsafe_allow_html=True)
    guida.mostra("fv")
    if "fv_df" not in ss:
        ss["fv_df"] = pd.DataFrame(fv.voci_standard(fv.FV_DEFAULT), columns=fv.COLONNE_VOCI)
    if "fv_list" not in ss:
        ss["fv_list"] = pd.DataFrame(columns=fv.COLONNE_LISTINO)
    pannello_archivio("fv", "il preventivo fotovoltaico", _raccogli, _applica, audit, utente)
    _da_registro()
    voci, avv = fv.normalizza_voci(ss["fv_df"].to_dict("records"))
    out = fv.calcola(voci, _params())
    t1, t2, t3, t4, t5 = st.tabs(["🏠 1. Impianto", "💶 2. Costi e prezzo", "📈 3. Risultato", "📚 4. Listino", "📄 5. Documenti"])
    with t1:
        _scheda_impianto()
    with t2:
        _scheda_costi()
        for a in avv[:3]:
            st.caption("⚠️ " + a)
    with t3:
        _scheda_risultato(out, audit)
    with t4:
        _scheda_listino()
    with t5:
        _scheda_documenti(out, audit)
