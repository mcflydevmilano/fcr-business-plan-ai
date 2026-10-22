"""pv_ui.py - Interfaccia del modulo Computo e Preventivo."""
import json

import pandas as pd
import streamlit as st
import guida

import charts
import cf
import pv
import pz_ui
import pv_report
import theme
from core import fmt_num
from ui_util import modello_excel, pannello_archivio, sola_lettura, sostituisci_tabella, tabella_modificabile

ss = st.session_state

ESEMPIO = [
    {"Codice": "A.01", "Categoria": "Demolizioni", "Descrizione": "Demolizione di tramezzi in laterizio", "UM": "mq", "Quantita": 180, "Materiali": 0, "Manodopera": 14, "Noli_altro": 4},
    {"Codice": "B.01", "Categoria": "Strutture", "Descrizione": "Calcestruzzo armato per cordoli e solette", "UM": "mc", "Quantita": 45, "Materiali": 150, "Manodopera": 70, "Noli_altro": 18},
    {"Codice": "C.01", "Categoria": "Finiture", "Descrizione": "Intonaco civile e tinteggiatura", "UM": "mq", "Quantita": 620, "Materiali": 7, "Manodopera": 16, "Noli_altro": 1.5},
    {"Codice": "D.01", "Categoria": "Impianti", "Descrizione": "Impianto elettrico completo", "UM": "corpo", "Quantita": 1, "Materiali": 9500, "Manodopera": 8200, "Noli_altro": 600},
]

PROMPT = (
    "Sei un computista esperto di lavori edili in Italia. Dato il testo dei lavori, proponi un computo metrico estimativo di massima. "
    "Rispondi SOLO con JSON: {\"voci\": [{\"codice\": str, \"categoria\": str, \"descrizione\": str, \"um\": str, \"quantita\": numero, "
    "\"materiali\": numero, \"manodopera\": numero, \"noli_altro\": numero}], \"note\": str}. Materiali, manodopera e noli sono COSTI UNITARI in euro "
    "per unita' di misura (non prezzi di vendita). Massimo 25 voci. Sono stime indicative: segnala in 'note' cosa va verificato."
)


def _num(label, key, mn, mx, step, fmt="%.1f"):
    k = "pv_" + key
    if k not in ss:
        ss[k] = float(pv.PV_DEFAULT[key])
    return st.number_input(label, min_value=mn, max_value=mx, step=step, key=k, format=fmt)


def _params():
    return {k: ss.get("pv_" + k, v) for k, v in pv.PV_DEFAULT.items()}


def _df(df):
    st.dataframe(df, hide_index=True, width="stretch")


def _fig(fig):
    st.pyplot(fig, clear_figure=True)


_CAMPI = ("pv_cliente", "pv_oggetto", "pv_validita", "pv_note")


def _raccogli():
    return {"voci": ss["pv_df"].to_dict("records"), "params": _params(), "campi": {k: ss.get(k) for k in _CAMPI}}


def _applica(p, nome):
    sostituisci_tabella("pv_df", pd.DataFrame(p.get("voci") or [], columns=pv.COLONNE_VOCI))
    pend = {"pv_" + k: v for k, v in (p.get("params") or {}).items() if k in pv.PV_DEFAULT}
    pend.update({k: v for k, v in (p.get("campi") or {}).items() if k in _CAMPI and v is not None})
    ss["_pending"] = pend


def render(ai_generate, active_key, fcr_uri, ai, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Computo e Preventivo",
                           "Dal computo metrico al preventivo: costi, spese generali, utile, sconto, sicurezza e IVA, con margine sempre sotto controllo."),
                unsafe_allow_html=True)
    guida.mostra("pv")
    if "pv_df" not in ss:
        ss["pv_df"] = pd.DataFrame(ESEMPIO, columns=pv.COLONNE_VOCI)
    for k, v in (("pv_cliente", ""), ("pv_oggetto", "Ristrutturazione edificio"), ("pv_validita", 30), ("pv_note", "")):
        ss.setdefault(k, v)
    pannello_archivio("pv", "il preventivo", _raccogli, _applica, audit, utente)
    t1, t2, t3, t4 = st.tabs(["📝 1. Computo", "💰 2. Preventivo e Margine", "📈 3. Sensibilità e Cash Flow", "📄 4. Documenti"])

    with t1:
        st.subheader("Voci di computo")
        st.caption("Per ogni voce inserisci i COSTI unitari dell'impresa (materiali, manodopera, noli/altro): il prezzo al cliente lo calcola il preventivo.")
        if ai_generate:
            with st.expander("🤖 Proponi le voci con l'AI da una descrizione dei lavori"):
                testo = st.text_area("Descrizione dei lavori", key="pv_testo", height=100,
                                     placeholder="Es.: rifacimento bagni in un condominio di 12 appartamenti, impianti e finiture incluse")
                if st.button("Genera il computo", disabled=not bool(active_key)):
                    with st.spinner("L'AI prepara il computo..."):
                        try:
                            raw, _m = ai_generate(active_key, [PROMPT, "LAVORI:\n" + testo], json_mode=True, temperature=0.2)
                            voci, note = pv.normalizza_voci_ai(json.loads(raw))
                            ss["pv_prop"] = {"voci": voci, "note": note}
                        except (json.JSONDecodeError, ValueError) as e:
                            st.error(f"Risposta non utilizzabile: {e}")
                        except Exception as e:
                            st.error((ai.messaggio_errore(e) + " Puoi inserire le voci a mano.") if ai.errore_temporaneo(e) else f"Errore: {e}")
                if not active_key:
                    st.caption("Serve una chiave Gemini e l'accettazione dell'informativa privacy (barra laterale).")
                prop = ss.get("pv_prop")
                if prop:
                    st.warning("Quantità e costi proposti dall'AI sono STIME: verificali su prezzari ufficiali e sul progetto prima di usarli.")
                    _df(pd.DataFrame(prop["voci"], columns=pv.COLONNE_VOCI))
                    if prop["note"]:
                        st.info("**Da verificare:** " + prop["note"])
                    c1, c2 = st.columns(2)
                    if c1.button("✅ Sostituisci il computo con queste voci"):
                        sostituisci_tabella("pv_df", pd.DataFrame(prop["voci"], columns=pv.COLONNE_VOCI))
                        ss.pop("pv_prop", None)
                        audit("pv_ai_voci", f"{len(prop['voci'])} voci")
                        st.rerun()
                    if c2.button("Scarta"):
                        ss.pop("pv_prop", None)
                        st.rerun()
        st.download_button("📥 Scarica il modello Excel per l'import", modello_excel(pv.COLONNE_VOCI, pv.ETICHETTE_VOCI, ESEMPIO[:3]),
                           file_name="modello_computo.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        up = st.file_uploader("Importa un computo da Excel/CSV (colonne: Descrizione, Quantità, Materiali, Manodopera…)", type=["xlsx", "csv"], key="up_pv")
        if up is not None and st.button("Importa il file", key="imp_pv"):
            try:
                d = pd.read_csv(up, sep=None, engine="python") if up.name.lower().endswith(".csv") else pd.read_excel(up)
                righe, avv = pv.voci_da_dataframe(d)
                voci, av2 = pv.normalizza_voci(righe)
                if not voci:
                    st.error("Nessuna voce valida nel file.")
                else:
                    sostituisci_tabella("pv_df", pd.DataFrame(voci, columns=pv.COLONNE_VOCI))
                    audit("pv_import", up.name)
                    for x in (avv + av2)[:5]:
                        st.warning(x)
                    st.rerun()
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"File non leggibile: {e}")
        with st.expander("📚 Aggiungi voci dal prezziario"):
            _nuove = pz_ui.scegli_voci("voce_prezziario", ss.get("pv_sg_pct", pv.PV_DEFAULT["sg_pct"]), ss.get("pv_utile_pct", pv.PV_DEFAULT["utile_pct"]))
            if _nuove:
                _base = ss["pv_df"]
                _base = _base[_base.apply(lambda r: any(str(r.get(c) or "").strip() not in ("", "nan", "0", "0.0") for c in pv.COLONNE_VOCI), axis=1)] if len(_base) else _base
                sostituisci_tabella("pv_df", pd.concat([_base, pd.DataFrame(_nuove, columns=pv.COLONNE_VOCI)], ignore_index=True))
                audit("pv_prezziario", f"{len(_nuove)} voci aggiunte dal prezziario")
                st.rerun()
        if not sola_lettura() and len(ss["pv_df"]):
            with st.expander("🗑️ Togli voci dal computo"):
                _tb = ss["pv_df"].reset_index(drop=True)
                _et = {i: f"{i + 1}. {str(r.get('Codice') or '').strip()} {str(r.get('Descrizione') or '').strip()[:70]}".replace("  ", " ") for i, r in _tb.iterrows()}
                _sel = st.multiselect("Scegli le voci da togliere", list(_et), format_func=lambda i: _et[i], key=f"togli_voci_sel_{ss.get('pv_df_v', 0)}",
                                      placeholder="Scegli una o più voci…")
                _c1, _c2 = st.columns(2)
                if _c1.button("🗑️ Togli le voci scelte", key="togli_voci_ok", disabled=not _sel, width="stretch"):
                    sostituisci_tabella("pv_df", _tb.drop(index=_sel).reset_index(drop=True))
                    audit("pv_voci_tolte", f"{len(_sel)} voci tolte")
                    st.rerun()
                if _c2.button("Svuota tutta la tabella", key="togli_voci_tutte", width="stretch"):
                    sostituisci_tabella("pv_df", _tb.iloc[0:0])
                    audit("pv_voci_tolte", "tabella svuotata")
                    st.rerun()
                st.caption("In alternativa, nella tabella spunta la casella a sinistra della riga e usa il cestino che compare in alto a destra.")
        n, e_ = st.column_config.NumberColumn, pv.ETICHETTE_VOCI
        cfg = {"Codice": st.column_config.TextColumn(e_["Codice"]), "Categoria": st.column_config.TextColumn(e_["Categoria"]),
               "Descrizione": st.column_config.TextColumn(e_["Descrizione"], width="large"), "UM": st.column_config.TextColumn(e_["UM"]),
               "Quantita": n(e_["Quantita"], min_value=0.0, format="%.2f"), "Materiali": n(e_["Materiali"] + " €/UM", min_value=0.0, format="%.2f"),
               "Manodopera": n(e_["Manodopera"] + " €/UM", min_value=0.0, format="%.2f"), "Noli_altro": n(e_["Noli_altro"] + " €/UM", min_value=0.0, format="%.2f")}
        tabella_modificabile("pv_df", ss["pv_df"], cfg, altezza=330)
        st.subheader("Parametri del preventivo")
        a, b, c = st.columns(3)
        with a:
            _num("Spese generali (% sui costi diretti)", "sg_pct", 0.0, 60.0, 0.5)
            _num("Utile d'impresa (% sui costi industriali)", "utile_pct", 0.0, 60.0, 0.5)
        with b:
            _num("Sconto al cliente (% sul listino)", "sconto_pct", 0.0, 60.0, 0.5)
            _num("Oneri di sicurezza (% sul listino)", "sicurezza_pct", 0.0, 20.0, 0.1)
        with c:
            _num("Aliquota IVA (%)", "iva_pct", 0.0, 30.0, 1.0, fmt="%.0f")
            _num("Margine minimo accettabile (% sull'imponibile)", "margine_min_pct", 0.0, 50.0, 0.5)

    voci, av_n = pv.normalizza_voci(ss["pv_df"].to_dict("records"))
    p = _params()
    out = pv.calcola_preventivo(voci, p)
    k = out["kpi"]

    with t2:
        if not voci:
            st.warning("Nessuna voce valida: inserisci almeno una riga con descrizione e quantità.")
        else:
            tono = "ok" if k["margine_pct"] >= p["margine_min_pct"] else "bad"
            st.markdown(theme.stat_strip([
                {"label": "Costo industriale", "value": f"{fmt_num(k['costo_industriale'])} €", "sub": "costi + spese generali", "tono": "info"},
                {"label": "Imponibile", "value": f"{fmt_num(k['imponibile'])} €", "sub": f"totale con IVA {fmt_num(k['totale'])} €", "tono": "info"},
                {"label": "Utile", "value": f"{fmt_num(k['utile'])} €", "sub": f"{fmt_num(k['utile_su_costi_pct'], 1)}% sui costi", "tono": tono},
                {"label": "Margine", "value": f"{fmt_num(k['margine_pct'], 1)}%", "sub": f"minimo {fmt_num(p['margine_min_pct'], 1)}%", "tono": tono},
            ]), unsafe_allow_html=True)
            for a in out["avvisi"]:
                st.warning(a)
            st.info(f"Sconto massimo concedibile per restare al margine minimo: **{fmt_num(k['sconto_max_pct'], 1)}%** (attuale {fmt_num(p['sconto_pct'], 1)}%).")
            c1, c2 = st.columns(2)
            with c1:
                _fig(charts.fig_pv_composizione(k))
            with c2:
                _fig(charts.fig_pv_categorie(out["categorie"]))
            with st.expander("Dettaglio voci (interno: include i costi)"):
                _df(pd.DataFrame(out["voci"]))

    with t3:
        if not voci:
            st.info("Aggiungi delle voci per vedere la sensibilità.")
        else:
            st.subheader("Se i costi aumentano a prezzo già offerto")
            sens = pv.sensibilita_costi(voci, p)
            _fig(charts.fig_pv_sensibilita(sens))
            ma = pv.costi_massimi_aumento(voci, p)
            if ma is not None:
                st.caption(f"Un aumento dei costi diretti oltre il {fmt_num(ma, 1)}% azzera l'utile.")
            st.subheader("Invia al Cash Flow di cantiere")
            st.caption("Aggiunge questo lavoro al portafoglio del modulo Cash Flow (contratto = imponibile, costi = costi totali dell'impresa).")
            a, b, c, d = st.columns(4)
            nome = a.text_input("Nome cantiere", ss["pv_oggetto"] or "Nuovo cantiere", key="pv_cf_nome")
            ini = b.number_input("Mese di inizio", 1, 60, 1, 1, key="pv_cf_ini")
            dur = c.number_input("Durata (mesi)", 1, 60, 3, 1, key="pv_cf_dur")
            gg = d.number_input("Giorni di incasso", 0, 365, 30, 15, key="pv_cf_gg")
            a, b = st.columns(2)
            ant = a.number_input("Anticipo (%)", 0.0, 100.0, 30.0, 5.0, key="pv_cf_ant")
            sal = b.number_input("Saldo (%)", 0.0, 100.0, 30.0, 5.0, key="pv_cf_sal")
            if st.button("➕ Aggiungi al portafoglio Cash Flow"):
                if ant + sal > 100:
                    st.error("Anticipo + saldo non possono superare il 100%.")
                else:
                    riga = pv.per_cash_flow(out, nome, int(ini), int(dur), ant, sal, int(gg))
                    base = ss.get("cf_df")
                    if base is None or ss.get("cf_demo", True):
                        base = pd.DataFrame(columns=cf.COLONNE_CANTIERI)       # il portafoglio di esempio non si mescola con un lavoro reale
                    sostituisci_tabella("cf_df", pd.concat([base, pd.DataFrame([riga], columns=cf.COLONNE_CANTIERI)], ignore_index=True))
                    ss["cf_demo"] = False
                    audit("pv_to_cf", nome)
                    st.success("Cantiere aggiunto. Aprilo dal modulo Cash Flow per vedere l'effetto sulla liquidità.")

    with t4:
        if not voci:
            st.info("Aggiungi delle voci per generare i documenti.")
        else:
            a, b = st.columns(2)
            a.text_input("Cliente", key="pv_cliente")
            b.text_input("Oggetto dei lavori", key="pv_oggetto")
            a.number_input("Validità dell'offerta (giorni)", 1, 365, key="pv_validita")
            st.text_area("Note per il cliente (facoltative)", key="pv_note", height=70)
            if st.button("📄 Genera preventivo (PDF cliente) ed Excel interno", type="primary"):
                with st.spinner("Preparo i documenti..."):
                    ctx = pv_report.costruisci_ctx_pv(out, ss["pv_cliente"], ss["pv_oggetto"], ss["pv_validita"], ss["pv_note"])
                    ss["pv_rep"] = {"pdf": pv_report.genera_pdf_pv(ctx), "xlsx": pv_report.genera_excel_pv(ctx), "id": ctx["report_id"]}
                    audit("pv_report", ctx["report_id"])
            rep = ss.get("pv_rep")
            if rep:
                c1, c2 = st.columns(2)
                c1.download_button("📥 Preventivo per il cliente (PDF)", rep["pdf"], file_name=f"Preventivo_{rep['id']}.pdf", mime="application/pdf", width="stretch")
                c2.download_button("📥 Excel interno con formule", rep["xlsx"], file_name=f"Preventivo_interno_{rep['id']}.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
                st.caption("Il PDF per il cliente NON contiene costi, spese generali né utile. L'Excel interno sì: non inviarlo al cliente.")
