"""ee_ui.py - Interfaccia dei preventivi di efficienza energetica (pompa di calore, caldaia, cappotto, LED, solare termico, colonnine)."""
import io

import pandas as pd
import streamlit as st

import ee
import es
import fv
import guida
import theme
from core import fmt_num
from ui_util import pannello_archivio, sola_lettura, sostituisci_tabella, tabella_modificabile

ss = st.session_state
_COMUNI = ("prezzo_gas", "prezzo_el", "aumento_energia_pct", "degrado_pct", "ricarico_pct", "anni", "regime", "iva_pct", "detrazione_pct", "detrazione_anni")
_CAMPI = ("ee_cliente", "ee_indirizzo", "ee_modello", "ee_garanzia")


def _tipo():
    ss.setdefault("ee_tipo", "pdc")
    return ss["ee_tipo"]


def _chiave(tipo, k):
    return f"ee_{tipo}_{k}" if k in dict((x[0], 1) for x in ee.PARAMETRI[tipo]) else f"ee_c_{k}"


def _params(tipo):
    out = {k: ss.get(f"ee_c_{k}", v) for k, v in ee.default_params(tipo).items() if k in _COMUNI}
    out.update({k: ss.get(f"ee_{tipo}_{k}", v) for k, _l, v, *_ in ee.PARAMETRI[tipo]})
    return out


def _raccogli():
    t = _tipo()
    return {"tipo": t, "voci": ss["ee_df"].to_dict("records"), "params": _params(t), "campi": {k: ss.get(k) for k in _CAMPI}, "listino": ss["ee_list"].to_dict("records")}


def _applica(p, nome):
    t = p.get("tipo") if p.get("tipo") in ee.TIPI else "pdc"
    sostituisci_tabella("ee_df", pd.DataFrame(p.get("voci") or [], columns=fv.COLONNE_VOCI))
    sostituisci_tabella("ee_list", pd.DataFrame(p.get("listino") or [], columns=fv.COLONNE_LISTINO))
    pend = {"ee_tipo": t, "_ee_tipo_prec": t}
    for k, v in (p.get("params") or {}).items():
        pend[_chiave(t, k) if k in dict((x[0], 1) for x in ee.PARAMETRI[t]) else f"ee_c_{k}"] = v
    pend.update({k: v for k, v in (p.get("campi") or {}).items() if k in _CAMPI and v is not None})
    ss["_pending"] = pend


def _num(c, label, key, mn, mx, step, fmt, help=None, default=None):
    ss.setdefault(key, float(default))
    return c.number_input(label, min_value=mn, max_value=mx, step=step, key=key, format=fmt, help=help, disabled=sola_lettura())


def _scheda_dati(tipo):
    a, b = st.columns(2)
    a.text_input("Cliente", key="ee_cliente", disabled=sola_lettura())
    b.text_input("Indirizzo", key="ee_indirizzo", disabled=sola_lettura())
    c, d = st.columns(2)
    c.text_input("Prodotto scelto (marca e modello)", key="ee_modello", disabled=sola_lettura())
    d.text_input("Garanzia", key="ee_garanzia", disabled=sola_lettura())
    st.markdown("**Dati dell'intervento**")
    par = ee.PARAMETRI[tipo]
    cols = st.columns(3)
    for i, (k, lab, v, mn, mx, stp, fm, hlp) in enumerate(par):
        _num(cols[i % 3], lab, f"ee_{tipo}_{k}", mn, mx, stp, fm, hlp, v)
    st.markdown("**Prezzi dell'energia**")
    e1, e2, e3, e4 = st.columns(4)
    dc = ee.DEFAULT_COMUNI
    _num(e1, "Prezzo del gas (€/Smc)", "ee_c_prezzo_gas", 0.0, 5.0, 0.01, "%.2f", None, dc["prezzo_gas"])
    _num(e2, "Prezzo dell'elettricità (€/kWh)", "ee_c_prezzo_el", 0.0, 2.0, 0.01, "%.2f", None, dc["prezzo_el"])
    _num(e3, "Aumento annuo energia (%)", "ee_c_aumento_energia_pct", 0.0, 10.0, 0.5, "%.1f", None, dc["aumento_energia_pct"])
    _num(e4, "Calo di resa all'anno (%)", "ee_c_degrado_pct", 0.0, 5.0, 0.1, "%.1f", None, dc["degrado_pct"])
    s = ee.stima(tipo, _params(tipo))
    st.info("**Stima del risparmio:** " + s["nota"])


def _scheda_costi(tipo):
    st.caption("I costi sono quelli che paghi tu, IVA esclusa. I valori proposti sono stime: sostituiscili con il tuo listino.")
    c1, c2 = st.columns(2)
    if c1.button("↻ Proponi le voci per questi dati", key="ee_voci_std", disabled=sola_lettura(), help="Sostituisce la tabella con le voci standard calcolate sui dati della scheda 1."):
        sostituisci_tabella("ee_df", pd.DataFrame(ee.voci_standard(tipo, _params(tipo)), columns=fv.COLONNE_VOCI))
        st.rerun()
    lst = [r for r in ss["ee_list"].to_dict("records") if str(r.get("Descrizione") or "").strip()]
    if lst and not sola_lettura():
        et = [f"{r['Descrizione']} · {fmt_num(float(r.get('Costo_unit') or 0))} €/{r.get('Um', '')}".strip(" /") for r in lst]
        sc = c2.selectbox("Aggiungi una voce dal listino", ["—"] + et, key="ee_add_list")
        if sc != "—" and c2.button("Aggiungi alla tabella", key="ee_add_list_ok"):
            r = lst[et.index(sc)]
            riga = pd.DataFrame([{"Voce": r["Descrizione"], "Quantita": 1.0, "Um": r.get("Um", ""), "Costo_unit": float(r.get("Costo_unit") or 0)}], columns=fv.COLONNE_VOCI)
            sostituisci_tabella("ee_df", pd.concat([ss["ee_df"], riga], ignore_index=True))
            st.rerun()
    cfg = {"Voce": st.column_config.TextColumn("Voce", width="large"), "Quantita": st.column_config.NumberColumn("Quantità", min_value=0.0, format="%.2f"),
           "Um": st.column_config.TextColumn("U.M.", width="small"), "Costo_unit": st.column_config.NumberColumn("Costo unitario €", min_value=0.0, format="%.2f")}
    tabella_modificabile("ee_df", pd.DataFrame(columns=fv.COLONNE_VOCI), cfg, altezza=300)
    st.markdown("**Prezzo al cliente e fisco**")
    ss.setdefault("ee_c_regime", ee.DEFAULT_COMUNI["regime"])
    prec = ss.get("_ee_regime_prec")
    r = st.selectbox("Chi compra", list(fv.REGIMI), key="ee_c_regime")
    if prec is not None and prec != r:
        ss["ee_c_detrazione_pct"], ss["ee_c_iva_pct"] = fv.REGIMI[r]["detrazione_pct"], fv.REGIMI[r]["iva_pct"]
    ss["_ee_regime_prec"] = r
    ss.setdefault("ee_c_detrazione_pct", ee.default_params(tipo)["detrazione_pct"])
    ss.setdefault("ee_c_iva_pct", fv.REGIMI[r]["iva_pct"])
    a, b, c, d = st.columns(4)
    _num(a, "Ricarico sui costi (%)", "ee_c_ricarico_pct", 0.0, 200.0, 1.0, "%.0f", None, ee.DEFAULT_COMUNI["ricarico_pct"])
    _num(b, "IVA (%)", "ee_c_iva_pct", 0.0, 22.0, 1.0, "%.0f", None, 10.0)
    _num(c, "Detrazione (%)", "ee_c_detrazione_pct", 0.0, 110.0, 1.0, "%.0f", "In 10 quote annuali. Verifica l'aliquota in vigore alla data dei lavori: in alternativa esiste il Conto Termico (contributo GSE).", 50.0)
    _num(d, "Anni di calcolo", "ee_c_anni", 5.0, 40.0, 1.0, "%.0f", None, float(ee.DEFAULT_COMUNI["anni"]))


def _scheda_risultato(out):
    k = out["kpi"]
    if not k["costo"]:
        st.info("Aggiungi le voci di costo nella scheda «2».")
        return
    st.markdown(theme.stat_strip([
        {"label": "Prezzo (IVA esclusa)", "value": f"{fmt_num(k['imponibile'])} €", "sub": f"costo {fmt_num(k['costo'])} € · margine {fmt_num(k['margine'])} €", "tono": "ok"},
        {"label": "Totale con IVA", "value": f"{fmt_num(k['totale'])} €", "sub": f"dopo detrazione {fmt_num(k['netto_detrazione'])} €", "tono": "ok"},
        {"label": "Risparmio 1° anno", "value": f"{fmt_num(k['risparmio_anno1'])} €", "sub": f"gas {fmt_num(k['risp_gas_smc'])} Smc · elettricità {fmt_num(k['risp_el_kwh'])} kWh", "tono": "ok" if k["risparmio_anno1"] > 0 else "bad"},
        {"label": "Rientro", "value": f"{k['rientro_anni']:.1f} anni" if k["rientro_anni"] is not None else "oltre il periodo", "sub": f"guadagno finale {fmt_num(k['guadagno_finale'])} €", "tono": "warn" if (k["rientro_anni"] or 99) > 9 else "ok"}]), unsafe_allow_html=True)
    for a in out["avvisi"]:
        st.warning(a)
    df = pd.DataFrame(out["flusso"])
    st.line_chart(df.set_index("Anno")[["Cumulato €"]], height=240)
    with st.expander("Anno per anno"):
        st.dataframe(df, hide_index=True, width="stretch")
    st.caption("Stime indicative: consumi reali, abitudini e prezzi dell'energia cambiano il risultato. Da verificare con un sopralluogo.")


def _scheda_documenti(tipo, out, audit):
    k = out["kpi"]
    if not k["costo"]:
        st.info("Completa prima le voci di costo.")
        return
    nome = f"{ee.TIPI[tipo]}" + (f" - {ss.get('ee_modello')}" if ss.get("ee_modello") else "")
    if not sola_lettura():
        a, b = st.columns(2)
        a.markdown("**Porta il prezzo nell'Offerta**")
        if a.button("➡️ Metti nell'Offerta", key="ee_to_of"):
            import of_ui
            cap = f"EE-{tipo}"
            riga = {"Cap": cap, "Cod": "EE", "Descrizione": nome, "UM": "a corpo", "Quantita": 1.0, "Prezzo": k["imponibile"], "Ipotesi": ""}
            att = ss["of_voci"] if "of_voci" in ss else pd.DataFrame(columns=of_ui.DF["of_voci"])
            if len(att):
                att = att[att["Cap"].astype(str) != cap]
            sostituisci_tabella("of_voci", pd.concat([att, of_ui._df("of_voci", [riga])], ignore_index=True))
            audit("ee_to_of", f"{nome} · {fmt_num(k['imponibile'])} €")
            a.success(f"Inserito nell'Offerta: {nome}, {fmt_num(k['imponibile'])} € IVA esclusa.")
        b.markdown("**Valutalo come investimento della ESCo**")
        if b.button("🌿 Aggiungi allo strumento ESCo", key="ee_to_es"):
            if "es_int" not in ss:
                ss["es_int"] = pd.DataFrame(columns=es.COLONNE_INT)
            if "es_bol" not in ss:
                ss["es_bol"] = pd.DataFrame(es.bollette_vuote(), columns=es.COLONNE_BOLLETTE)
            riga = ee.intervento_per_esco(tipo, k, out["stima"], nome)
            att = ss["es_int"]
            if len(att):
                att = att[att["Intervento"].astype(str) != nome]
            sostituisci_tabella("es_int", pd.concat([att, pd.DataFrame([riga], columns=es.COLONNE_INT)], ignore_index=True))
            audit("ee_to_es", nome)
            b.success("Aggiunto agli interventi dello strumento ESCo (investimento = il tuo costo).")
    righe = [("Cliente", ss.get("ee_cliente", "")), ("Indirizzo", ss.get("ee_indirizzo", "")), ("Intervento", ee.TIPI[tipo]), ("Prodotto", ss.get("ee_modello", "")), ("Garanzia", ss.get("ee_garanzia", "")),
             ("Imponibile", k["imponibile"]), ("IVA", k["iva"]), ("Totale", k["totale"]), ("Detrazione", k["detrazione"]), ("Costo netto dopo detrazione", k["netto_detrazione"]),
             ("Risparmio 1° anno", k["risparmio_anno1"]), ("Rientro (anni)", k["rientro_anni"] if k["rientro_anni"] is not None else ""), ("Stima", out["stima"]["nota"])]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame(righe, columns=["Dato", "Valore"]).to_excel(w, sheet_name="Riepilogo", index=False)
        pd.DataFrame(fv.normalizza_voci(ss["ee_df"].to_dict("records"))[0]).to_excel(w, sheet_name="Costi", index=False)
        pd.DataFrame(out["flusso"]).to_excel(w, sheet_name="Anno per anno", index=False)
    st.download_button("📥 Scarica il preventivo in Excel", buf.getvalue(), file_name=f"preventivo_{tipo}.xlsx", key="dl_ee_xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _scheda_listino():
    st.caption("Carica il listino del fornitore (Excel o CSV) così com'è: la suite trova da sola le intestazioni.")
    if not sola_lettura():
        up = st.file_uploader("Listino prezzi (.xlsx, .csv)", type=["xlsx", "xls", "csv"], key="ee_up_list")
        if up is not None:
            righe, av = fv.leggi_listino(up.getvalue(), up.name)
            for a in av[:3]:
                st.warning(a)
            if righe:
                st.success(f"Lette {len(righe)} righe di listino.")
                a, b = st.columns(2)
                if a.button("Aggiungi al listino", type="primary", key="ee_list_add"):
                    sostituisci_tabella("ee_list", pd.concat([ss["ee_list"], pd.DataFrame(righe, columns=fv.COLONNE_LISTINO)], ignore_index=True))
                    st.rerun()
                if b.button("Sostituisci il listino", key="ee_list_sost"):
                    sostituisci_tabella("ee_list", pd.DataFrame(righe, columns=fv.COLONNE_LISTINO))
                    st.rerun()
    cfg = {"Descrizione": st.column_config.TextColumn("Descrizione", width="large"), "Costo_unit": st.column_config.NumberColumn("Costo €", min_value=0.0, format="%.2f")}
    tabella_modificabile("ee_list", pd.DataFrame(columns=fv.COLONNE_LISTINO), cfg, altezza=320)


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Preventivi efficienza energetica", "Pompa di calore, caldaia, cappotto, LED, solare termico e colonnine: prezzo, detrazione, risparmio e rientro."), unsafe_allow_html=True)
    guida.mostra("ee")
    if "ee_list" not in ss:
        ss["ee_list"] = pd.DataFrame(columns=fv.COLONNE_LISTINO)
    tipo = _tipo()
    if "ee_df" not in ss:
        ss["ee_df"] = pd.DataFrame(ee.voci_standard(tipo, _params(tipo)), columns=fv.COLONNE_VOCI)
        ss["_ee_tipo_prec"] = tipo
    pannello_archivio("ee", "il preventivo", _raccogli, _applica, audit, utente)
    sc = st.selectbox("Che intervento stai preventivando?", list(ee.TIPI), format_func=lambda k: ee.TIPI[k], key="ee_tipo", disabled=sola_lettura())
    if ss.get("_ee_tipo_prec") != sc:                      # cambiando tipo le voci di partenza cambiano; chi ha gia' lavorato non perde nulla perche' il salvataggio e' per tipo
        ss["_ee_tipo_prec"] = sc
        sostituisci_tabella("ee_df", pd.DataFrame(ee.voci_standard(sc, _params(sc)), columns=fv.COLONNE_VOCI))
        ss["ee_c_detrazione_pct"] = ee.default_params(sc)["detrazione_pct"]
        st.rerun()
    tipo = sc
    voci, avv = fv.normalizza_voci(ss["ee_df"].to_dict("records"))
    out = ee.calcola(tipo, voci, _params(tipo))
    t1, t2, t3, t4, t5 = st.tabs(["🏠 1. Dati e risparmio", "💶 2. Costi e prezzo", "📈 3. Risultato", "📚 4. Listino", "📄 5. Documenti"])
    with t1:
        _scheda_dati(tipo)
    with t2:
        _scheda_costi(tipo)
        for a in avv[:3]:
            st.caption("⚠️ " + a)
    with t3:
        _scheda_risultato(out)
    with t4:
        _scheda_listino()
    with t5:
        _scheda_documenti(tipo, out, audit)
