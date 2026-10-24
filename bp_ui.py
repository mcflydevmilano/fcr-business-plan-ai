"""
bp_ui.py - Interfaccia del modulo "Business Plan Studio" (nuove iniziative, 3-5 anni).

Si usa da app.py:  bp_ui.render(ai_generate, active_key, fcr_uri, ai_module)
Le ipotesi stanno tutte nella scheda 1 (chiavi di sessione "bp_<nome>"), cosi' i calcoli sono sempre aggiornati
nelle schede successive.
"""
import json

import pandas as pd
import streamlit as st
import guida

import bp
import bp_report
import charts
import core
import theme
from core import fmt_eur, fmt_num, fmt_x

ss = st.session_state

ESEMPIO_PROGETTO = (
    "FCR General Contractor intende lanciare una nuova divisione specializzata in riqualificazioni energetiche NZEB "
    "per edifici residenziali e industriali. Si stima un fatturato del primo anno di 1.500.000 euro con un margine "
    "EBITDA del 15%, un investimento iniziale in macchinari e software di 200.000 euro e l'assunzione di 3 tecnici "
    "e un capocantiere."
)

PROMPT_ASSUNZIONI = (
    "Sei un Senior Financial Advisor esperto di business plan bancabili per imprese di costruzioni italiane. "
    "Dal progetto descritto ricava le ipotesi del piano e restituisci ESCLUSIVAMENTE un oggetto JSON con queste chiavi "
    "numeriche: ricavi_y1 (euro), crescita (% annua dei ricavi dal 2° anno), cv_pct (costi variabili in % dei ricavi), "
    "personale (euro annui totali del personale), infl_personale (% di aumento annuo), costi_fissi (altri costi fissi in "
    "euro annui), capex (investimento iniziale in euro), anni_amm (anni di ammortamento), mutuo (euro di finanziamento "
    "bancario), tasso (% annuo), durata (anni del finanziamento), equity (mezzi propri in euro), aliquota (% IRES+IRAP), "
    "ccn_pct (% di capitale circolante sulla variazione dei ricavi), n_anni (3, 4 o 5). "
    "Usa i numeri forniti nella descrizione quando ci sono (se i costi sono dati per persona, moltiplicali); per gli altri "
    "valori proponi stime prudenti e ordinarie per il settore. Numeri senza separatori delle migliaia e con il punto "
    "come separatore decimale; le percentuali come numeri (15 per 15%). Aggiungi 'motivazioni': oggetto con, per ogni "
    "chiave, una frase breve che dice se il valore e' dato dalla descrizione o e' una tua stima, e 'note': una frase "
    "con i rischi principali da verificare. Non inventare fatti di mercato."
)

MSG_QUOTA = (
    "⏳ La quota giornaliera gratuita di Gemini e' esaurita. Puoi continuare subito inserendo le ipotesi a mano nei "
    "campi qui sotto: calcoli, grafici e dossier PDF funzionano comunque, senza testo scritto dall'AI. "
    "Per usare l'AI riprova piu' tardi (di solito entro 24 ore) o inserisci un'altra chiave API nella barra laterale."
)


def _df(df):
    st.dataframe(df, width="stretch", hide_index=True)


def _fig(fig):
    st.image(charts.fig_png(fig, 120))


def _num(label, key, mn, mx, step, help=None, fmt=None):
    k = "bp_" + key
    if k not in ss:
        ss[k] = type(mn)(bp.BP_DEFAULT[key])
    if fmt is None:
        fmt = "%d" if isinstance(mn, int) else "%.0f"
    return st.number_input(label, min_value=mn, max_value=mx, step=step, key=k, help=help, format=fmt)


def _sld(label, key, mn, mx, step, help=None):
    k = "bp_" + key
    if k not in ss:
        ss[k] = float(bp.BP_DEFAULT[key])
    return st.slider(label, float(mn), float(mx), step=float(step), key=k, help=help)


def _params():
    return {k: ss.get("bp_" + k, v) for k, v in bp.BP_DEFAULT.items()}


def prompt_relazione(ctx):
    out, q, k = ctx["bp"], ctx["bp"]["params"], ctx["bp"]["kpi"]
    righe = "\n".join(
        f"- {r['Anno']}: ricavi {fmt_num(r['Ricavi'])} EUR, EBITDA {fmt_num(r['EBITDA'])} EUR ({fmt_num(r['Margine EBITDA %'], 1)}%), "
        f"utile netto {fmt_num(r['Utile netto'])} EUR, flusso operativo {fmt_num(r['FCF operativo'])} EUR, "
        f"cassa finale {fmt_num(r['Cassa finale'])} EUR, PFN {fmt_num(r['PFN'])} EUR, "
        f"DSCR {fmt_x(r['DSCR']) if r['DSCR'] is not None else 'n.d.'}"
        for r in out["anni"]
    )
    avvisi = "; ".join(out["avvisi"]) or "nessuno"
    return (
        "Agisci come Senior Financial Advisor e redigi la relazione strategica di un business plan destinata a una banca.\n"
        f"INIZIATIVA: {ctx.get('nome') or 'non indicata'}. {ctx.get('descrizione', '')}\n"
        f"IPOTESI: ricavi anno 1 {fmt_num(q['ricavi_y1'])} EUR, crescita {fmt_num(q['crescita'], 1)}% annua, costi variabili "
        f"{fmt_num(q['cv_pct'], 1)}% dei ricavi, personale {fmt_num(q['personale'])} EUR, altri costi fissi {fmt_num(q['costi_fissi'])} EUR, "
        f"investimento {fmt_num(q['capex'])} EUR ammortizzato in {int(q['anni_amm'])} anni, finanziamento {fmt_num(q['mutuo'])} EUR al "
        f"{fmt_num(q['tasso'], 2)}% su {int(q['durata'])} anni, mezzi propri {fmt_num(q['equity'])} EUR.\n"
        f"RISULTATI:\n{righe}\n"
        f"Payback: {fmt_num(k['payback_anni'], 1) + ' anni' if k['payback_anni'] is not None else 'oltre l orizzonte del piano'}. "
        f"DSCR minimo: {fmt_x(k['dscr_min']) if k['dscr_min'] is not None else 'n.d.'}. Cassa minima: {fmt_num(k['cassa_minima'])} EUR.\n"
        f"PUNTI DI ATTENZIONE RILEVATI: {avvisi}.\n"
        "Struttura: 1. Executive summary dell'iniziativa. 2. Mercato di riferimento (solo considerazioni qualitative, senza "
        "cifre di mercato inventate). 3. Sostenibilita' economico-finanziaria del piano. 4. Rischi strategici e misure di "
        "mitigazione. 5. Raccomandazioni. Usa SOLO i numeri forniti e riportali con le stesse cifre. Precisa che e' una "
        "proiezione basata su ipotesi. Scrivi in italiano, in testo semplice senza markdown."
    )


def _contesto_numeri(out, descrizione):
    nums = [core.to_float(m.group(0), None) for m in core._RE_NUM.finditer(descrizione or "")]
    return {"params": out["params"], "anni": out["anni"], "mutuo": out["mutuo"], "kpi": out["kpi"],
            "descrizione": [n for n in nums if n is not None]}


def _raccogli():
    return {k: v for k, v in ss.items() if isinstance(k, str) and k.startswith("bp_") and k not in ("bp_prop", "bp_report")
            and isinstance(v, (int, float, str, bool)) and not k.endswith("_v")}


def _applica(p, nome):
    ss["_pending"] = {k: v for k, v in p.items() if isinstance(k, str) and k.startswith("bp_")}


def render(ai_generate, active_key, fcr_uri, ai, audit=None, utente=""):
    st.markdown(
        theme.hero(fcr_uri, "Business Plan Studio",
                   "Pianificazione economico-finanziaria di nuove iniziative: conto economico, finanziamento e cash flow "
                   "da 3 a 5 anni, con wizard AI e dossier PDF."),
        unsafe_allow_html=True,
    )
    guida.mostra("bp")
    for k, v in (("bp_nome", "Divisione riqualificazioni NZEB"), ("bp_descr", ESEMPIO_PROGETTO)):
        ss.setdefault(k, v)

    from ui_util import pannello_archivio
    pannello_archivio("bp", "il business plan", _raccogli, _applica, audit, utente)
    t1, t2, t3, t4, t5 = st.tabs(["🤖 1. Wizard AI e Ipotesi", "📊 2. Conto Economico", "🏦 3. Finanziamenti e Cash Flow",
                                  "🎯 4. Scenari e Sensibilità", "📄 5. Dossier PDF"])

    # ============================ 1. WIZARD + IPOTESI ============================
    with t1:
        st.subheader("Descrivi l'iniziativa")
        st.text_input("Nome dell'iniziativa", key="bp_nome")
        st.text_area("Descrizione del progetto (importi, investimenti, personale, tempi...)", key="bp_descr", height=130)
        wizard_on = bool(active_key)
        if st.button("🪄 Genera le ipotesi con l'AI", type="primary", disabled=not wizard_on):
            with st.spinner("L'AI sta ricavando le ipotesi dal testo..."):
                try:
                    raw, _modello = ai_generate(active_key, [PROMPT_ASSUNZIONI, "PROGETTO:\n" + ss["bp_descr"]],
                                                json_mode=True, temperature=0.1)
                    valori, mot, note = bp.normalizza_assunzioni(json.loads(raw))
                    if not valori:
                        st.error("L'AI non ha proposto valori utilizzabili. Riprova o inserisci le ipotesi a mano.")
                    else:
                        ss["bp_prop"] = {"valori": valori, "mot": mot, "note": note}
                except json.JSONDecodeError:
                    st.error("Il modello non ha restituito un JSON valido. Riprova.")
                except Exception as e:
                    st.error((ai.messaggio_errore(e) + " Puoi inserire le ipotesi a mano nei campi qui sotto.") if ai.errore_temporaneo(e) else f"Errore durante la generazione: {e}")
        import ia_info
        ia_info.attivazione(active_key, "il wizard")
        st.caption("Senza l'IA puoi inserire le ipotesi a mano qui sotto: tutto il resto funziona uguale.")

        prop = ss.get("bp_prop")
        if prop:
            st.markdown("#### Ipotesi proposte dall'AI: verificale prima di applicarle")
            p_att = _params()
            righe = [{"Ipotesi": bp.ETICHETTE_BP.get(k, k), "Proposta": v, "Attuale": float(p_att.get(k, 0)),
                      "Motivazione": prop["mot"].get(k, "")} for k, v in prop["valori"].items()]
            _df(pd.DataFrame(righe))
            if prop["note"]:
                st.info("**Da verificare:** " + prop["note"])
            c1, c2 = st.columns(2)
            if c1.button("✅ Applica le ipotesi proposte"):
                ss["_pending"] = {"bp_" + k: v for k, v in prop["valori"].items()}
                ss.pop("bp_prop", None)
                st.toast("Ipotesi applicate", icon="✅")
                st.rerun()
            if c2.button("Scarta la proposta"):
                ss.pop("bp_prop", None)
                st.rerun()

        st.subheader("Ipotesi del piano")
        a, b, c = st.columns(3)
        with a:
            st.markdown("**Ricavi e costi**")
            _num("Ricavi anno 1 (€)", "ricavi_y1", 0.0, 500_000_000.0, 50_000.0)
            _sld("Crescita annua dei ricavi dal 2° anno (%)", "crescita", -20, 100, 1)
            _sld("Costi variabili / materie prime (% ricavi)", "cv_pct", 0, 95, 1)
            _num("Costo del personale annuo (€)", "personale", 0.0, 100_000_000.0, 10_000.0)
            _sld("Aumento annuo del personale (%)", "infl_personale", 0, 20, 0.5)
            _num("Altri costi fissi e servizi (€)", "costi_fissi", 0.0, 100_000_000.0, 10_000.0)
        with b:
            st.markdown("**Investimento e fisco**")
            _num("Investimento iniziale / CAPEX (€)", "capex", 0.0, 500_000_000.0, 25_000.0)
            _num("Anni di ammortamento", "anni_amm", 1, 20, 1)
            ss.setdefault("bp_fisco", "dettagliato")
            st.radio("Modello fiscale", ["dettagliato", "semplice"], key="bp_fisco", horizontal=True,
                     help="Dettagliato: IRES e IRAP separate, con riporto delle perdite. Semplice: un'unica aliquota sugli utili positivi.")
            if ss["bp_fisco"] == "semplice":
                _sld("Aliquota fiscale unica (%)", "aliquota", 0, 60, 0.5)
            else:
                _sld("Aliquota IRES (%)", "ires", 0, 40, 0.5)
                _sld("Aliquota IRAP (%)", "irap", 0, 10, 0.1, help="Base ordinaria 3,9%, con differenze regionali: verifica l'aliquota della tua regione.")
                _sld("Personale deducibile dall'IRAP (%)", "irap_ded_pers", 0, 100, 5,
                     help="Quota del costo del personale che riduce la base IRAP (es. dipendenti a tempo indeterminato). Prudenzialmente 0.")
                ss.setdefault("bp_riporto", True)
                st.checkbox("Riporta le perdite fiscali (utilizzo fino all'80% del reddito)", key="bp_riporto")
            _sld("Capitale circolante (% sulla variazione dei ricavi)", "ccn_pct", 0, 60, 1,
                 help="Quanta cassa viene assorbita da crediti e magazzino per ogni euro di ricavi in piu'. Nei lavori edili e' spesso alta.")
            ss.setdefault("bp_n_anni", 3)
            st.radio("Orizzonte del piano (anni)", [3, 4, 5], key="bp_n_anni", horizontal=True)
            _num("Anno di inizio", "anno_inizio", 2000, 2100, 1)
        with c:
            st.markdown("**Finanziamento**")
            _num("Finanziamento bancario / mutuo (€)", "mutuo", 0.0, 500_000_000.0, 25_000.0)
            _sld("Tasso di interesse annuo (%)", "tasso", 0, 20, 0.25)
            _num("Durata del finanziamento (anni)", "durata", 1, 30, 1)
            ss.setdefault("bp_tipo_rata", "francese")
            st.radio("Tipo di ammortamento", ["francese", "italiano"], key="bp_tipo_rata", horizontal=True,
                     help="Francese: rata costante. Italiano: quota capitale costante e rata decrescente.")
            _num("Mezzi propri apportati (€)", "equity", 0.0, 500_000_000.0, 25_000.0)

    out = bp.calcola_bp(_params())
    anni, k, q = out["anni"], out["kpi"], out["params"]

    with t1:
        ult = anni[-1]
        dscr_tono = "info" if k["dscr_min"] is None else ("ok" if k["dscr_min"] >= 1.2 else ("warn" if k["dscr_min"] >= 1.0 else "bad"))
        st.markdown(theme.stat_strip([
            {"label": f"Ricavi {ult['AnnoNum']}", "value": fmt_eur(ult["Ricavi"]), "sub": f"da {fmt_eur(anni[0]['Ricavi'])} nel 1° anno", "tono": "info"},
            {"label": f"EBITDA {ult['AnnoNum']}", "value": fmt_eur(ult["EBITDA"]), "sub": f"margine {fmt_num(ult['Margine EBITDA %'], 1)}%",
             "tono": "ok" if ult["EBITDA"] > 0 else "bad"},
            {"label": "DSCR minimo", "value": fmt_x(k["dscr_min"]) if k["dscr_min"] is not None else "n.d.", "sub": "target indicativo ≥ 1,20x", "tono": dscr_tono},
            {"label": "Cassa minima", "value": fmt_eur(k["cassa_minima"]), "sub": "nel periodo del piano", "tono": "ok" if k["cassa_minima"] >= 0 else "bad"},
            {"label": "Payback", "value": f"{fmt_num(k['payback_anni'], 1)} anni" if k["payback_anni"] is not None else "oltre il piano",
             "sub": "rientro dell'investimento", "tono": "info" if k["payback_anni"] is not None else "warn"},
        ]), unsafe_allow_html=True)
        for a_ in out["avvisi"]:
            st.warning(a_)

    # ============================ 2. CONTO ECONOMICO ============================
    with t2:
        st.subheader("Conto economico previsionale")
        voci = [("Ricavi delle vendite", "Ricavi", 1), ("Costi variabili", "Costi variabili", -1), ("Costo del personale", "Personale", -1),
                ("Altri costi operativi", "Altri costi", -1), ("EBITDA (MOL)", "EBITDA", 1), ("Ammortamenti", "Ammortamenti", -1),
                ("EBIT", "EBIT", 1), ("Interessi passivi", "Interessi", -1), ("Utile ante imposte", "Utile ante imposte", 1),
                ("di cui IRES", "IRES", -1), ("di cui IRAP", "IRAP", -1),
                ("Imposte", "Imposte", -1), ("Utile netto", "Utile netto", 1)]
        if q["fisco"] == "semplice":
            voci = [v for v in voci if v[1] not in ("IRES", "IRAP")]
        righe = [{"Voce (EUR)": et, **{str(r["AnnoNum"]): fmt_num(sg * r[ch]) for r in anni}} for et, ch, sg in voci]
        righe.insert(5, {"Voce (EUR)": "Margine EBITDA %", **{str(r["AnnoNum"]): fmt_num(r["Margine EBITDA %"], 1) + "%" for r in anni}})
        _df(pd.DataFrame(righe))
        if q["fisco"] == "semplice":
            st.caption("Modello semplice: aliquota unica applicata solo agli utili positivi, senza riporto delle perdite.")
        else:
            st.caption("IRES sul risultato ante imposte (al netto delle perdite pregresse, max 80% del reddito); IRAP su EBIT + personale non deducibile, "
                       "dovuta anche in perdita. Il reddito imponibile e' assunto uguale all'utile civilistico: verifica le variazioni fiscali con il commercialista.")
            if anni[-1]["Perdite fiscali residue"] > 1:
                st.info(f"Perdite fiscali ancora riportabili a fine piano: {fmt_eur(anni[-1]['Perdite fiscali residue'])}.")
        _fig(charts.fig_bp_economico(anni, "light"))

    # ============================ 3. FINANZIAMENTI E CASH FLOW ====================
    with t3:
        st.subheader("Fonti, impieghi e finanziamento")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Investimento", fmt_eur(q["capex"]))
        m2.metric("Fonti (mutuo + mezzi propri)", fmt_eur(k["fonti"]))
        rata1 = out["mutuo"][0]["Rata"] if q["mutuo"] > 0 else 0.0
        m3.metric("Rata anno 1", fmt_eur(rata1))
        m4.metric("Copertura EBITDA / rata (anno 1)", fmt_x(k["copertura_ebitda_y1"]) if k["copertura_ebitda_y1"] is not None else "n.d.")
        if q["mutuo"] > 0:
            st.markdown("#### Piano di ammortamento")
            _df(pd.DataFrame([{"Anno": r["Anno"], "Quota capitale": fmt_num(r["Quota capitale"]), "Interessi": fmt_num(r["Interessi"]),
                               "Rata": fmt_num(r["Rata"]), "Debito residuo": fmt_num(r["Debito residuo"])} for r in out["mutuo"]]))
            st.caption(f"Interessi totali sul finanziamento: {fmt_eur(k['interessi_tot'])}.")
            _fig(charts.fig_bp_mutuo(out["mutuo"], "light"))
        st.markdown("#### Cash flow e posizione finanziaria")
        voci_cf = [("EBITDA", "EBITDA", 1), ("Imposte", "Imposte", -1), ("Variazione capitale circolante", "Variazione CCN", -1),
                   ("Flusso operativo (FCF)", "FCF operativo", 1), ("Interessi", "Interessi", -1),
                   ("Rimborso quota capitale", "Quota capitale", -1), ("Flusso netto dell'anno", "Flusso netto", 1),
                   ("Cassa di fine anno", "Cassa finale", 1), ("Debito residuo", "Debito residuo", 1), ("PFN (debito − cassa)", "PFN", 1)]
        righe = [{"Voce (EUR)": et, **{str(r["AnnoNum"]): fmt_num(sg * r[ch]) for r in anni}} for et, ch, sg in voci_cf]
        righe.append({"Voce (EUR)": "DSCR", **{str(r["AnnoNum"]): (fmt_x(r["DSCR"]) if r["DSCR"] is not None else "n.d.") for r in anni}})
        _df(pd.DataFrame(righe))
        st.caption(f"Cassa iniziale (dopo investimento, finanziamento e mezzi propri): {fmt_eur(k['cassa_iniziale'])}.")
        g1, g2 = st.columns(2)
        with g1:
            _fig(charts.fig_bp_finanza(anni, k["cassa_iniziale"], "light"))
        with g2:
            if k["dscr_min"] is not None:
                _fig(charts.fig_dscr(anni, None, 1.2, "light"))
            else:
                st.info("Nessun finanziamento: il DSCR non e' calcolabile.")

    # ============================ 4. SCENARI E SENSIBILITA' =====================
    with t4:
        st.subheader("Scenari: pessimistico, base, ottimistico")
        st.caption("Ogni scenario modifica le ipotesi base con gli scostamenti qui sotto (modificabili). Il caso base e' sempre quello inserito nella scheda 1.")
        if "bp_scen_df" not in ss:
            ss["bp_scen_df"] = pd.DataFrame(
                [{"Scenario": n, **{et: float(d.get(c, 0.0)) for c, (_k, _m, et) in bp.CAMPI_SCENARIO.items()}}
                 for n, d in bp.SCENARI_DEFAULT.items() if n != "Base"])
        ed = st.data_editor(ss["bp_scen_df"], width="stretch", hide_index=True, key="scen_editor_tmp",
                            disabled=["Scenario"], num_rows="fixed")
        scen_def = {}
        for _, r_ in ed.iterrows():
            scen_def[str(r_["Scenario"])] = {c: core.to_float(r_[et], 0.0) for c, (_k, _m, et) in bp.CAMPI_SCENARIO.items()}
        risultati = bp.calcola_scenari(_params(), scen_def)
        conf = bp.confronto_scenari(risultati)
        _df(pd.DataFrame([{
            "Scenario": c["Scenario"], "Ricavi ultimo anno": fmt_num(c["Ricavi ultimo anno"]),
            "EBITDA ultimo anno": fmt_num(c["EBITDA ultimo anno"]), "Utile netto cumulato": fmt_num(c["Utile netto cumulato"]),
            "Cassa minima": fmt_num(c["Cassa minima"]), "DSCR minimo": fmt_x(c["DSCR minimo"]) if c["DSCR minimo"] is not None else "n.d.",
            "Payback": f"{fmt_num(c['Payback (anni)'], 1)} anni" if c["Payback (anni)"] is not None else "oltre il piano"} for c in conf]))
        peggio = risultati.get("Pessimistico")
        if peggio and peggio["kpi"]["cassa_minima"] < -1:
            st.warning(f"Nello scenario pessimistico la cassa scende a {fmt_eur(peggio['kpi']['cassa_minima'])}: servirebbe una linea di liquidita' di scorta.")
        _fig(charts.fig_bp_scenari(risultati, "light"))

        st.subheader("Sensibilità: quali ipotesi pesano di più")
        opzioni = list(bp.METRICHE)
        met = st.selectbox("Indicatore da analizzare", opzioni, format_func=lambda m: bp.METRICHE[m], index=1, key="bp_sens_metrica")
        sens = bp.sensibilita(_params(), met)
        if not sens:
            st.info("Questo indicatore non e' calcolabile (ad esempio il DSCR senza finanziamento). Scegline un altro.")
        else:
            _df(pd.DataFrame([{"Variabile": r["Variabile"], "Variazione": r["Variazione"],
                               "Con valore minore": fmt_num(r["Con valore minore"], 2 if met == "dscr_min" else 0),
                               "Caso base": fmt_num(r["Base"], 2 if met == "dscr_min" else 0),
                               "Con valore maggiore": fmt_num(r["Con valore maggiore"], 2 if met == "dscr_min" else 0)} for r in sens]))
            _fig(charts.fig_tornado(sens, bp.METRICHE[met], "light"))
            st.caption("Per ogni riga si varia una sola ipotesi per volta (verso l'alto e verso il basso) tenendo ferme le altre.")
        ss["_bp_scen_out"] = {"scenari": risultati, "sensibilita": sens, "sens_metrica": bp.METRICHE[met]}

        with st.expander("Mappa di sensibilità: ricavi × costi variabili"):
            base_r, base_c = float(q["ricavi_y1"]), float(q["cv_pct"])
            xs = [round(base_r * f) for f in (0.8, 0.9, 1.0, 1.1, 1.2)]
            ys = [max(0.0, base_c + d) for d in (-10, -5, 0, 5, 10)]
            mat = bp.griglia(_params(), "ricavi_y1", xs, "cv_pct", ys, "cassa_minima" if q["mutuo"] <= 0 else "dscr_min")
            usa_d = q["mutuo"] > 0
            tab = pd.DataFrame([[fmt_num(v, 2) if (v is not None and usa_d) else (fmt_num(v) if v is not None else "n.d.") for v in riga] for riga in mat],
                               index=[f"Costi variabili {fmt_num(y, 0)}%" for y in ys], columns=[f"Ricavi {fmt_num(x)}" for x in xs])
            st.caption("Valori: " + ("DSCR minimo" if usa_d else "cassa minima (EUR)") + ". Sotto 1,00 il flusso non copre il servizio del debito.")
            st.dataframe(tab, width="stretch")

    # ============================ 5. DOSSIER PDF ================================
    with t5:
        st.subheader("Dossier del Business Plan")
        usa_ai = st.checkbox("Includi la relazione strategica scritta dall'AI", value=bool(active_key), disabled=not active_key, key="bp_usa_ai")
        st.caption("💡 Se togli la spunta ottieni comunque il dossier PDF completo di ipotesi, conto economico, cash flow, "
                   "finanziamento e grafici, ma senza il testo dell'AI (utile se la quota Gemini e' esaurita).")
        if st.button("🚀 Genera il dossier PDF", type="primary"):
            with st.spinner("Creazione del dossier in corso..."):
                try:
                    out_pdf = {**out, **ss.get("_bp_scen_out", {})}
                    ctx = bp_report.costruisci_ctx_bp(out_pdf, ss.get("bp_nome", ""), ss.get("bp_descr", ""), "nessuno")
                    relazione, quota, sospetti = "", False, []
                    if usa_ai and active_key:
                        try:
                            testo, usato = ai_generate(active_key, prompt_relazione(ctx), temperature=0.3)
                            relazione = ai.pulisci_testo(testo)
                            ctx["modello"] = usato
                            sospetti = core.numeri_sospetti(relazione, _contesto_numeri(out, ss.get("bp_descr", "")))
                        except Exception as e_ai:
                            if not ai.errore_temporaneo(e_ai):
                                raise
                            quota = True
                    if audit:
                        audit("dossier_bp", f"{ctx['report_id']} iniziativa={ss.get('bp_nome', '')}")
                    ss["bp_report"] = {"pdf": bp_report.genera_pdf_bp(ctx, relazione), "id": ctx["report_id"],
                                       "sospetti": sospetti, "quota": quota, "modello": ctx["modello"]}
                except Exception as e:
                    st.error(f"Errore nella generazione del dossier: {e}")
        rep = ss.get("bp_report")
        if rep:
            if rep["quota"]:
                st.warning("⏳ L'AI non e' disponibile ora (quota esaurita o servizio sovraccarico): **il dossier e' stato generato senza la relazione "
                           "scritta dall'AI**. Contiene comunque tutte le tabelle e i grafici.")
            if rep["sospetti"]:
                st.warning("⚠️ La relazione dell'AI cita cifre che non trovo nei calcoli: " + ", ".join(rep["sospetti"])
                           + ". Controllale prima di usare il documento.")
            st.success(f"Dossier pronto (ID {rep['id']}). Modello AI: {rep['modello']}.")
            st.download_button("📥 Scarica il dossier PDF", rep["pdf"], file_name=f"Business_Plan_{rep['id']}.pdf",
                               mime="application/pdf")
