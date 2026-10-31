"""
nuovi_ui.py - Schermate degli strumenti nuovi: Subappalti (sa), Presenze e ore (pr), Materiali e magazzino (mt), Verbali e riunioni (vr),
Archivio documenti (ad) e Margini per commessa (mc). Un solo motore comune per le cinque schermate a tabelle; ognuna ha le sue tabelle, i suoi risultati e le sue integrazioni.
"""
import datetime as dt
import io
import types

import pandas as pd
import streamlit as st

import ad
import guida
import mc
import mt
import pr
import sa
import sl
import storage
import theme
import vr
from core import fmt_num
from ui_util import banner_esempio, blocco_tabella, esempi_attivi, pannello_archivio, senza_esempi, sola_lettura, sostituisci_tabella

ss = st.session_state
ICONE = {"ok": "🟢", "warn": "🟡", "bad": "🔴", "nd": "⚪"}
EUR = lambda x: f"{fmt_num(x)} €"
g = lambda n: (dt.date.today() + dt.timedelta(days=n)).isoformat()


def _mk(cols, rows):
    return pd.DataFrame([dict(zip(cols, r)) for r in rows], columns=cols)


def _t(label, **k):
    return st.column_config.TextColumn(label, **k)


def _n(label, **k):
    return st.column_config.NumberColumn(label, **k)


def _xlsx(fogli):
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as w:
        for nome, righe in fogli.items():
            df = pd.DataFrame(righe)
            if df.empty:
                df = pd.DataFrame({"(vuoto)": []})
            df.to_excel(w, sheet_name=nome[:31], index=False)
    return bio.getvalue()


def _tabella(righe, **cfg):
    if righe:
        st.dataframe(pd.DataFrame(righe), hide_index=True, width="stretch", **cfg)


# ----------------------------------------------------------------------------
# MOTORE COMUNE
# ----------------------------------------------------------------------------
def _motore(S, fcr_uri, audit, utente):
    audit = audit or (lambda *a, **k: None)
    sg = S["sigla"]
    st.markdown(theme.hero(fcr_uri, S["titolo"], S["sottotitolo"]), unsafe_allow_html=True)
    guida.mostra(sg)
    if S["tabelle"][0]["chiave"] not in ss:
        for T, df in zip(S["tabelle"], S["esempio"]()):
            ss[T["chiave"]] = df
        ss[f"{sg}_demo"] = esempi_attivi()

    def raccogli():
        d = {T["chiave"].split("_", 1)[1]: ss[T["chiave"]].to_dict("records") for T in S["tabelle"]}
        d["params"] = {P["k"]: ss.get(f"{sg}_{P['k']}", P["default"]) for P in S["param"]}
        return d

    def applica(p, nome):
        for T in S["tabelle"]:
            sostituisci_tabella(T["chiave"], pd.DataFrame(p.get(T["chiave"].split("_", 1)[1]) or [], columns=T["colonne"]))
        ss[f"{sg}_demo"] = False
        ss["_pending"] = {f"{sg}_{k}": v for k, v in (p.get("params") or {}).items() if k in {P["k"] for P in S["param"]}}

    S["_raccogli"] = raccogli
    pannello_archivio(sg, S["archivio"], raccogli, applica, audit, utente)
    extra = S.get("tab_extra")
    t1, t2, t3, t4, *t5 = st.tabs(["📝 1. Dati", "📊 2. Risultati", "🔗 3. Collegamenti", "📥 4. Excel"] + ([extra[0]] if extra else []))
    with t1:
        banner_esempio(f"{sg}_demo", [(T["chiave"], T["colonne"]) for T in S["tabelle"]], f"svuota_{sg}")
        if S.get("rapido"):
            S["rapido"](utente, audit)
        for i, T in enumerate(S["tabelle"], start=1):
            blocco_tabella(T["chiave"], T["titolo"], T["nota"], T["colonne"], T["etichette"], T["cfg"](), ss[T["chiave"]], sg, i, audit, T.get("altezza", 240))
        st.subheader("Ipotesi")
        cols = st.columns(len(S["param"]) + 1)
        cols[0].date_input("Data di riferimento", key=f"{sg}_oggi", value=dt.date.today())
        for c, P in zip(cols[1:], S["param"]):
            ss.setdefault(f"{sg}_{P['k']}", P["default"])
            if P["kind"] == "text":
                c.text_input(P["label"], key=f"{sg}_{P['k']}", help=P.get("help"))
            else:
                c.number_input(P["label"], P["min"], P["max"], step=P["step"], key=f"{sg}_{P['k']}", help=P.get("help"))
    dati, av_n = S["leggi"]()
    par = {"oggi": ss.get(f"{sg}_oggi", dt.date.today()), **{P["k"]: ss.get(f"{sg}_{P['k']}", P["default"]) for P in S["param"]}}
    out = S["calcola"](dati, par)
    k = out["kpi"]
    with t2:
        if not S["ha_dati"](dati):
            st.warning(S["vuoto"])
        else:
            for x in av_n[:3]:
                st.caption("⚠️ " + x)
            if k.get("n_bad"):
                st.error(f"**{k['n_bad']} {S['unita']} da sistemare subito.**")
            elif k.get("n_warn"):
                st.warning(f"**{k['n_warn']} {S['unita']} da tenere d'occhio.**")
            else:
                st.success("**Tutto in ordine.**")
            st.markdown(theme.stat_strip(S["strip"](out)), unsafe_allow_html=True)
            for a in out["avvisi"][:10]:
                st.warning(a)
            S["risultati"](out)
    with t3:
        S["collegamenti"](out, dati, utente, audit)
    with t4:
        if not S["ha_dati"](dati):
            st.info("Inserisci dei dati per scaricare l'Excel.")
        else:
            st.download_button("📥 Scarica tutto in Excel", _xlsx(S["fogli"](out)), file_name=f"{S['file']}_{dt.date.today().isoformat()}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"dlx_{sg}")
            st.caption("Un foglio per ogni tabella dei risultati. I valori sono quelli calcolati oggi.")
    if extra:
        with t5[0]:
            extra[1](out, dati, utente, audit)


def _invia_a_sal(chiave, righe, marcatore, audit, sigla):
    """Mette nei costi di SAL le righe di questo strumento, sostituendo quelle gia' inviate prima."""
    if "sl_cos" not in ss:
        ss["sl_com"], ss["sl_sal"], ss["sl_cos"] = (pd.DataFrame(columns=c) for c in (sl.COLONNE_COMMESSE, sl.COLONNE_SAL, sl.COLONNE_COSTI))
        ss["sl_demo"] = False
    att = ss["sl_cos"]
    if len(att):
        att = att[~att.apply(marcatore, axis=1)]
    nuove = pd.DataFrame(righe, columns=sl.COLONNE_COSTI)
    sostituisci_tabella("sl_cos", pd.concat([att, nuove], ignore_index=True) if len(att) else nuove)
    audit(f"{sigla}_to_sl", str(len(nuove)))
    st.success(f"Inviate {len(nuove)} righe di costo. Contano solo se la commessa esiste in SAL e contabilità lavori. "
               "Il margine per commessa non le conta due volte.")


def _coll_sal(sigla, righe_fn, marcatore, nota):
    def f(out, dati, utente, audit):
        st.caption(nota)
        righe = righe_fn(out, dati)
        st.write(f"Righe di costo pronte: **{len(righe)}**")
        if st.button("📐 Invia i costi a SAL e contabilità", key=f"to_sl_{sigla}", disabled=not righe or sola_lettura()):
            _invia_a_sal("sl_cos", righe, marcatore, audit, sigla)
        st.info("Le scadenze e i ritardi compaiono anche nel **Calendario** (uno strumento diverso, stesso elenco unico).")
    return f


# ----------------------------------------------------------------------------
# SUBAPPALTI
# ----------------------------------------------------------------------------
@senza_esempi
def _es_sa():
    return (_mk(sa.COLONNE_CONTRATTI, [("Edil Rossi Srl", "Villa Lago", "Murature e intonaci", 120000, 5), ("Impianti Bianchi", "Villa Lago", "Impianto elettrico", 45000, 5), ("Edil Rossi Srl", "Scuola Elementare", "Opere in c.a.", 200000, 5)]),
            _mk(sa.COLONNE_SAL, [("Edil Rossi Srl", "Villa Lago", g(-60), 40000, 38000), ("Edil Rossi Srl", "Villa Lago", g(-20), 30000, 0), ("Impianti Bianchi", "Villa Lago", g(-15), 12000, 11400), ("Edil Rossi Srl", "Scuola Elementare", g(-30), 80000, 76000)]),
            _mk(sa.COLONNE_DOC, [("Edil Rossi Srl", "DURC", g(-8)), ("Edil Rossi Srl", "Polizza RC", g(220)), ("Impianti Bianchi", "DURC", g(25)), ("Impianti Bianchi", "Idoneità tecnico-professionale", g(300))]))


def _cfg_sa():
    a, b, c = sa.ETICHETTE_CONTRATTI, sa.ETICHETTE_SAL, sa.ETICHETTE_DOC
    return ({"Subappaltatore": _t(a["Subappaltatore"], width="medium"), "Commessa": _t(a["Commessa"]), "Lavorazione": _t(a["Lavorazione"]), "Importo_contratto": _n(a["Importo_contratto"], min_value=0.0, step=1000.0, format="%.0f"),
             "Ritenuta_pct": _n(a["Ritenuta_pct"], min_value=0.0, max_value=20.0, step=0.5, format="%.1f")},
            {"Subappaltatore": _t(b["Subappaltatore"], width="medium"), "Commessa": _t(b["Commessa"]), "Data": _t(b["Data"], help="AAAA-MM-GG o GG/MM/AAAA"), "Importo_SAL": _n(b["Importo_SAL"], min_value=0.0, step=500.0, format="%.0f"),
             "Pagato": _n(b["Pagato"], min_value=0.0, step=500.0, format="%.0f")},
            {"Subappaltatore": _t(c["Subappaltatore"], width="medium"), "Documento": st.column_config.SelectboxColumn(c["Documento"], options=sa.DOCUMENTI), "Scadenza": _t(c["Scadenza"], help="AAAA-MM-GG o GG/MM/AAAA")})


def _leggi_sa():
    c, a1 = sa.normalizza_contratti(ss["sa_con"].to_dict("records"))
    s, a2 = sa.normalizza_sal(ss["sa_sal"].to_dict("records"), c)
    d, a3 = sa.normalizza_doc(ss["sa_doc"].to_dict("records"), {x["Subappaltatore"] for x in c})
    return (c, s, d), a1 + a2 + a3


def _ris_sa(o):
    _tabella([{"Subappaltatore": d["Subappaltatore"], "Commessa": d["Commessa"], "Stato": ICONE[d["Stato"]], "Contratto": d["Contratto"], "SAL lordi": d["SAL lordi"], "Avanz. %": d["Avanzamento %"],
               "Ritenute": d["Ritenute"], "Pagato": d["Pagato"], "Da pagare": d["Da pagare"], "Documenti": ICONE[d["Documenti"]]} for d in o["contratti"]])
    c1, c2 = st.columns(2)
    c1.markdown("**Subappalti per commessa**")
    with c1:
        _tabella(o["commesse"])
    c2.markdown("**Documenti in scadenza o scaduti**")
    ren = [{"Subappaltatore": d["Subappaltatore"], "Documento": d["Documento"], "Scadenza": d["Scadenza"], "Giorni": d["Giorni"], "Stato": ICONE[d["Stato"]]} for d in o["documenti"] if d["Stato"] in ("bad", "warn")]
    if ren:
        with c2:
            _tabella(ren)
    else:
        c2.success("Nessun documento in scadenza.")


SPEC_SA = {
    "sigla": "sa", "titolo": "Subappalti e subappaltatori", "sottotitolo": "Contratti, SAL, ritenute e documenti obbligatori (DURC, polizze): sai chi puoi pagare e chi no.",
    "archivio": "i subappalti", "file": "subappalti", "unita": "subappalti", "vuoto": "Inserisci almeno un contratto con subappaltatore, commessa e importo.",
    "tabelle": [{"chiave": "sa_con", "titolo": "Contratti di subappalto", "nota": "Una riga per ogni subappaltatore e commessa. La ritenuta di garanzia è la quota trattenuta su ogni SAL.", "colonne": sa.COLONNE_CONTRATTI, "etichette": sa.ETICHETTE_CONTRATTI,
                 "cfg": lambda: _cfg_sa()[0]},
                {"chiave": "sa_sal", "titolo": "SAL dei subappaltatori", "nota": "Ogni stato di avanzamento ricevuto, con l'importo lordo e quanto hai già pagato.", "colonne": sa.COLONNE_SAL, "etichette": sa.ETICHETTE_SAL,
                 "cfg": lambda: _cfg_sa()[1], "altezza": 260},
                {"chiave": "sa_doc", "titolo": "Documenti obbligatori", "nota": "DURC, polizze, idoneità, autorizzazione al subappalto: con la data di scadenza.", "colonne": sa.COLONNE_DOC, "etichette": sa.ETICHETTE_DOC, "cfg": lambda: _cfg_sa()[2]}],
    "esempio": _es_sa, "leggi": _leggi_sa, "calcola": lambda d, p: sa.calcola_sa(*d, p), "ha_dati": lambda d: bool(d[0]),
    "param": [{"k": "preavviso_gg", "label": "Preavviso scadenze (giorni)", "kind": "int", "min": 0, "max": 180, "step": 5, "default": 30}],
    "strip": lambda o: [{"label": "Contrattato", "value": EUR(o["kpi"]["contrattato"]), "sub": f"{o['kpi']['n_sub']} subappaltatori", "tono": "info"},
                        {"label": "SAL lordi", "value": EUR(o["kpi"]["sal_lordi"]), "sub": f"ritenute {EUR(o['kpi']['ritenute'])}", "tono": "info"},
                        {"label": "Da pagare", "value": EUR(o["kpi"]["da_pagare"]), "sub": "al netto delle ritenute", "tono": "warn" if o["kpi"]["da_pagare"] > 0 else "ok"},
                        {"label": "Documenti scaduti", "value": str(o["kpi"]["doc_scaduti"]), "sub": f"{o['kpi']['doc_in_arrivo']} in arrivo", "tono": "bad" if o["kpi"]["doc_scaduti"] else "ok"}],
    "risultati": _ris_sa, "fogli": lambda o: {"Contratti": o["contratti"], "Documenti": o["documenti"], "Per commessa": o["commesse"]},
}
SPEC_SA["collegamenti"] = lambda out, dati, utente, audit: _coll_sal("sa", lambda o, d: sa.per_sl_costi(o, d[1]), lambda r: str(r.get("Descrizione")) == "SAL subappaltatore",
                                                                    "Porta i SAL dei subappaltatori tra i costi delle commesse di **SAL e contabilità lavori** (categoria «Subappalti»).")(out, dati, utente, audit)


# ----------------------------------------------------------------------------
# PRESENZE E ORE
# ----------------------------------------------------------------------------
@senza_esempi
def _es_pr():
    return (_mk(pr.COLONNE_PERSONE, [("Mario Bianchi", "Capocantiere", 32), ("Luca Verdi", "Operaio specializzato", 26), ("Anna Neri", "Geometra", 34)]),
            _mk(pr.COLONNE_ORE, [("Mario Bianchi", g(-3), "Villa Lago", 8), ("Mario Bianchi", g(-2), "Villa Lago", 10), ("Luca Verdi", g(-3), "Scuola Elementare", 8), ("Luca Verdi", g(-2), "Villa Lago", 8), ("Anna Neri", g(-2), "Scuola Elementare", 6)]))


def _cfg_pr():
    a, b = pr.ETICHETTE_PERSONE, pr.ETICHETTE_ORE
    return ({"Persona": _t(a["Persona"], width="medium"), "Qualifica": _t(a["Qualifica"]), "Costo_orario": _n(a["Costo_orario"], min_value=0.0, step=1.0, format="%.1f")},
            {"Persona": _t(b["Persona"], width="medium"), "Data": _t(b["Data"], help="AAAA-MM-GG o GG/MM/AAAA"), "Commessa": _t(b["Commessa"]), "Ore": _n(b["Ore"], min_value=0.0, max_value=1000.0, step=0.5, format="%.1f")})


def _leggi_pr():
    p, a1 = pr.normalizza_persone(ss["pr_per"].to_dict("records"))
    o, a2 = pr.normalizza_ore(ss["pr_ore"].to_dict("records"), {x["Persona"] for x in p})
    return (p, o), a1 + a2


def _rapido_pr(utente, audit):
    """Inserimento veloce dal telefono: una riga alla volta, senza aprire la tabella."""
    nomi = [str(x) for x in ss["pr_per"]["Persona"].dropna().tolist()] if len(ss["pr_per"]) else []
    with st.expander("⚡ Registra le mie ore (veloce, dal telefono)", expanded=False):
        if not nomi:
            st.info("Prima inserisci le persone (con il costo orario) nella tabella qui sotto.")
            return
        mio = next((n for n in nomi if n.lower().split()[0] == str(utente).lower() or n.lower() == str(utente).lower()), None)
        with st.form("rapido_pr", clear_on_submit=True):
            c1, c2 = st.columns(2)
            chi = c1.selectbox("Chi", nomi, index=nomi.index(mio) if mio else 0)
            quando = c2.date_input("Giorno", value=dt.date.today())
            c3, c4 = st.columns(2)
            comm = c3.text_input("Commessa")
            ore = c4.number_input("Ore", 0.5, 24.0, 8.0, step=0.5)
            if st.form_submit_button("Registra", type="primary", disabled=sola_lettura()):
                riga = pd.DataFrame([{"Persona": chi, "Data": quando.isoformat(), "Commessa": comm.strip(), "Ore": ore}], columns=pr.COLONNE_ORE)
                sostituisci_tabella("pr_ore", pd.concat([ss["pr_ore"], riga], ignore_index=True))
                audit("pr_ore_registrate", f"{chi} {quando.isoformat()} {ore:g} h")
                st.success("Ore registrate. Ricorda di salvare con «Salva e riapri».")
                st.rerun()


def _importa_rapportini_pr(utente, audit):
    """Porta le ore totali dei rapportini giornalieri tra le ore lavorate, come «Squadra». Riimportare sostituisce solo quelle righe."""
    with st.expander("📥 Importa le ore dai rapportini giornalieri", expanded=False):
        st.caption("Ogni rapportino porta le ore totali del cantiere (non i nomi): vengono registrate come «" + pr.SQUADRA + "», con il costo orario medio delle persone "
                   "(modificabile nella tabella Persone) e senza straordinario. Riimportare aggiorna solo queste righe.")
        if st.button("Importa ora", key="pr_imp_rp", disabled=sola_lettura()):
            rapp = []
            if "rp_rapp" in ss and not ss.get("rp_demo") and len(ss["rp_rapp"]):
                rapp = __import__("rp").normalizza_rapp(ss["rp_rapp"].to_dict("records"))[0]
            else:
                try:
                    rapp = ((storage.carica_pratica("Rapportini", modulo="rp") or {}).get("rapp")) or []
                except Exception:
                    rapp = []
            nuove = pr.da_rapportini(rapp)
            if not nuove:
                st.warning("Nessun rapportino con ore trovato (salva prima i rapportini, o toglili dalla modalità esempio).")
                return
            per = ss["pr_per"]
            if not len(per) or not (per["Persona"].astype(str) == pr.SQUADRA).any():
                costo = pr.costo_orario_squadra(pr.normalizza_persone(per.to_dict("records"))[0])
                sostituisci_tabella("pr_per", pd.concat([per, pd.DataFrame([{"Persona": pr.SQUADRA, "Qualifica": "Ore dai rapportini", "Costo_orario": costo}], columns=pr.COLONNE_PERSONE)], ignore_index=True))
            att = ss["pr_ore"]
            att = att[att["Persona"].astype(str) != pr.SQUADRA] if len(att) else att
            sostituisci_tabella("pr_ore", pd.concat([att, pd.DataFrame(nuove, columns=pr.COLONNE_ORE)], ignore_index=True) if len(att) else pd.DataFrame(nuove, columns=pr.COLONNE_ORE))
            audit("pr_import_rapportini", str(len(nuove)))
            st.success(f"Importate {len(nuove)} registrazioni. Salva con «Salva e riapri».")
            st.rerun()


def _rapido_e_import_pr(utente, audit):
    _rapido_pr(utente, audit)
    _importa_rapportini_pr(utente, audit)


def _ris_pr(o):
    c1, c2 = st.columns(2)
    c1.markdown("**Per persona**")
    with c1:
        _tabella(o["persone"])
    c2.markdown("**Per commessa (costo della manodopera)**")
    with c2:
        _tabella(o["commesse"])
    if o["mesi"]:
        st.markdown("**Ore per mese**")
        st.bar_chart(pd.DataFrame(o["mesi"]).set_index("Mese"))


SPEC_PR = {
    "sigla": "pr", "titolo": "Presenze e ore di cantiere", "sottotitolo": "Chi ha lavorato, dove e quante ore: costo della manodopera per commessa.",
    "archivio": "le presenze", "file": "presenze", "unita": "controlli", "vuoto": "Inserisci almeno una persona con il costo orario e delle ore lavorate.",
    "tabelle": [{"chiave": "pr_per", "titolo": "Persone", "nota": "Il costo orario è il costo aziendale (stipendio, contributi, quote), non la paga netta.", "colonne": pr.COLONNE_PERSONE, "etichette": pr.ETICHETTE_PERSONE,
                 "cfg": lambda: _cfg_pr()[0], "altezza": 200},
                {"chiave": "pr_ore", "titolo": "Ore lavorate", "nota": "Una riga per persona, giorno e commessa. Le ore oltre la giornata ordinaria sono straordinario.", "colonne": pr.COLONNE_ORE, "etichette": pr.ETICHETTE_ORE,
                 "cfg": lambda: _cfg_pr()[1], "altezza": 300}],
    "esempio": _es_pr, "leggi": _leggi_pr, "calcola": lambda d, p: pr.calcola_pr(*d, p), "ha_dati": lambda d: bool(d[0]),
    "param": [{"k": "ore_giorno", "label": "Ore ordinarie al giorno", "kind": "float", "min": 1.0, "max": 12.0, "step": 0.5, "default": 8.0},
              {"k": "magg_straord_pct", "label": "Maggiorazione straordinario (%)", "kind": "float", "min": 0.0, "max": 100.0, "step": 5.0, "default": 25.0},
              {"k": "max_ore_giorno", "label": "Ore massime plausibili al giorno", "kind": "float", "min": 8.0, "max": 24.0, "step": 1.0, "default": 12.0}],
    "strip": lambda o: [{"label": "Ore totali", "value": fmt_num(o["kpi"]["ore"]), "sub": f"{o['kpi']['n_persone']} persone", "tono": "info"},
                        {"label": "Straordinario", "value": fmt_num(o["kpi"]["straordinario"]), "sub": "ore", "tono": "warn" if o["kpi"]["straordinario"] > 0 else "ok"},
                        {"label": "Costo manodopera", "value": EUR(o["kpi"]["costo"]), "sub": f"{o['kpi']['n_commesse']} commesse", "tono": "info"},
                        {"label": "Anomalie", "value": str(o["kpi"]["n_anomalie"]), "sub": "giornate troppo lunghe", "tono": "bad" if o["kpi"]["n_anomalie"] else "ok"}],
    "risultati": _ris_pr, "rapido": _rapido_e_import_pr, "fogli": lambda o: {"Registrazioni": o["righe"], "Persone": o["persone"], "Commesse": o["commesse"], "Mesi": o["mesi"]},
}
SPEC_PR["collegamenti"] = lambda out, dati, utente, audit: _coll_sal("pr", lambda o, d: pr.per_sl_costi(o), lambda r: str(r.get("Fornitore")) == "Manodopera interna",
                                                                    "Porta il costo della manodopera (un totale per commessa e per mese) tra i costi di **SAL e contabilità lavori**. "
                                                                    "Il rapportino di cantiere resta quello di Rapportini: qui contano solo le ore.")(out, dati, utente, audit)


# ----------------------------------------------------------------------------
# MATERIALI
# ----------------------------------------------------------------------------
@senza_esempi
def _es_mt():
    return (_mk(mt.COLONNE_ORDINI, [("Calcestruzzo C25/30", "Beton Nord", "Villa Lago", 60, "mc", 120, g(-4), "no", ""), ("Ferro d'armatura", "Acciai Lombardi", "Villa Lago", 3000, "kg", 1.1, g(-20), "sì", g(-19), "DDT 412"),
                                   ("Laterizi", "Fornaci Est", "Scuola Elementare", 8000, "pz", 0.6, g(5), "no", ""), ("Tubi multistrato", "Idro Sud", "Scuola Elementare", 400, "m", 3.2, g(12), "no", "")]),
            _mk(mt.COLONNE_MOV, [("Ferro d'armatura", "Villa Lago", g(-19), "Carico", 3000), ("Ferro d'armatura", "Villa Lago", g(-12), "Scarico", 1800), ("Ferro d'armatura", "Villa Lago", g(-3), "Scarico", 900)]))


def _cfg_mt():
    a, b = mt.ETICHETTE_ORDINI, mt.ETICHETTE_MOV
    return ({"Materiale": _t(a["Materiale"], width="medium"), "Fornitore": _t(a["Fornitore"]), "Commessa": _t(a["Commessa"]), "Quantita": _n(a["Quantita"], min_value=0.0, step=1.0), "Um": _t(a["Um"], width="small"),
             "Prezzo_unit": _n(a["Prezzo_unit"], min_value=0.0, step=0.1, format="%.2f"), "Consegna_prevista": _t(a["Consegna_prevista"], help="AAAA-MM-GG o GG/MM/AAAA"),
             "Consegnato": st.column_config.SelectboxColumn(a["Consegnato"], options=["no", "sì"]), "Data_consegna": _t(a["Data_consegna"], help="AAAA-MM-GG o GG/MM/AAAA"),
             "Ddt": _t(a["Ddt"], help="Numero del documento di trasporto scritto sulla bolla, per esempio 412 del 28/10")},
            {"Materiale": _t(b["Materiale"], width="medium"), "Commessa": _t(b["Commessa"]), "Data": _t(b["Data"], help="AAAA-MM-GG o GG/MM/AAAA"),
             "Tipo": st.column_config.SelectboxColumn(b["Tipo"], options=mt.TIPI_MOV), "Quantita": _n(b["Quantita"], min_value=0.0, step=1.0)})


def _leggi_mt():
    o, a1 = mt.normalizza_ordini(ss["mt_ord"].to_dict("records"))
    m, a2 = mt.normalizza_mov(ss["mt_mov"].to_dict("records"))
    return (o, m), a1 + a2


def _ris_mt(o):
    _tabella([{"": ICONE[r["Stato"]], "Materiale": r["Materiale"], "Commessa": r["Commessa"], "Fornitore": r["Fornitore"], "Quantità": r["Quantita"], "Um": r["Um"], "Importo": r["Importo"],
               "Consegna prevista": r["Consegna_prevista"], "Consegnato": r["Consegnato"], "Giorni": r["Giorni"]} for r in o["ordini"]])
    c1, c2 = st.columns(2)
    c1.markdown("**Giacenze di cantiere**")
    with c1:
        _tabella(o["giacenze"])
    c2.markdown("**Costo dei materiali consegnati, per commessa**")
    with c2:
        _tabella(o["commesse"])


SPEC_MT = {
    "sigla": "mt", "titolo": "Materiali e magazzino", "sottotitolo": "Ordini e consegne, giacenze di cantiere e costo dei materiali per commessa.",
    "archivio": "i materiali", "file": "materiali", "unita": "problemi", "vuoto": "Inserisci almeno un ordine con materiale e quantità.",
    "tabelle": [{"chiave": "mt_ord", "titolo": "Ordini e consegne", "nota": "Segna «sì» in «Consegnato» quando arriva e scrivi il numero del DDT della bolla. L'importo è quantità × prezzo unitario, IVA esclusa.", "colonne": mt.COLONNE_ORDINI, "etichette": mt.ETICHETTE_ORDINI,
                 "cfg": lambda: _cfg_mt()[0], "altezza": 280},
                {"chiave": "mt_mov", "titolo": "Carichi e scarichi di magazzino", "nota": "Carico = arriva in cantiere; Scarico = usato o spostato. La giacenza è la differenza.", "colonne": mt.COLONNE_MOV, "etichette": mt.ETICHETTE_MOV,
                 "cfg": lambda: _cfg_mt()[1]}],
    "esempio": _es_mt, "leggi": _leggi_mt, "calcola": lambda d, p: mt.calcola_mt(*d, p), "ha_dati": lambda d: bool(d[0]),
    "param": [{"k": "preavviso_gg", "label": "Preavviso consegne (giorni)", "kind": "int", "min": 0, "max": 60, "step": 1, "default": 7}],
    "strip": lambda o: [{"label": "Ordinato", "value": EUR(o["kpi"]["ordinato"]), "sub": f"{o['kpi']['n_ordini']} ordini", "tono": "info"},
                        {"label": "Consegnato", "value": EUR(o["kpi"]["consegnato"]), "sub": "costo sostenuto", "tono": "info"},
                        {"label": "In ritardo", "value": str(o["kpi"]["in_ritardo"]), "sub": f"{o['kpi']['in_arrivo']} in arrivo", "tono": "bad" if o["kpi"]["in_ritardo"] else "ok"},
                        {"label": "Giacenze negative", "value": str(o["kpi"]["giacenze_negative"]), "sub": "da controllare", "tono": "warn" if o["kpi"]["giacenze_negative"] else "ok"}],
    "risultati": _ris_mt, "fogli": lambda o: {"Ordini": o["ordini"], "Giacenze": o["giacenze"], "Commesse": o["commesse"]},
}
SPEC_MT["tab_extra"] = ("📎 5. Bolle (DDT)", lambda out, dati, utente, audit: __import__("ddt_ui").render(out, dati, utente, audit))
SPEC_MT["collegamenti"] = lambda out, dati, utente, audit: _coll_sal("mt", lambda o, d: mt.per_sl_costi(o), lambda r: str(r.get("Descrizione")).endswith("(da Materiali)"),
                                                                    "Porta i materiali consegnati tra i costi delle commesse di **SAL e contabilità lavori** (categoria «Materiali»; già pagato = 0 finché non lo segni in SAL).")(out, dati, utente, audit)


# ----------------------------------------------------------------------------
# VERBALI
# ----------------------------------------------------------------------------
@senza_esempi
def _es_vr():
    return (_mk(vr.COLONNE_VERBALI, [(g(-5), "Riunione di cantiere Villa Lago", "Villa Lago", "Mario, Luca, direttore lavori", "Anticipare il getto della soletta di 3 giorni. Sostituire il fornitore dei tubi."),
                                     (g(-1), "Coordinamento sicurezza Scuola", "Scuola Elementare", "Anna, RSPP", "Nuovo ponteggio lato sud entro venerdì.")]),
            _mk(vr.COLONNE_AZIONI, [("Riunione di cantiere Villa Lago", "Ordinare il calcestruzzo per il getto", "mario", g(-1), "Aperta"), ("Riunione di cantiere Villa Lago", "Chiedere offerta a un nuovo fornitore di tubi", "anna", g(4), "Aperta"),
                                    ("Coordinamento sicurezza Scuola", "Montare il ponteggio lato sud", "luca", g(3), "Aperta"), ("Coordinamento sicurezza Scuola", "Aggiornare il POS", "anna", g(-3), "Fatta")]))


def _cfg_vr():
    a, b = vr.ETICHETTE_VERBALI, vr.ETICHETTE_AZIONI
    return ({"Data": _t(a["Data"], help="AAAA-MM-GG o GG/MM/AAAA"), "Titolo": _t(a["Titolo"], width="large"), "Commessa": _t(a["Commessa"]), "Partecipanti": _t(a["Partecipanti"]), "Decisioni": _t(a["Decisioni"], width="large")},
            {"Verbale": _t(b["Verbale"], width="large"), "Azione": _t(b["Azione"], width="large"), "Responsabile": _t(b["Responsabile"], help="Il nome utente della persona (es. mario), così diventa un compito in chat"),
             "Scadenza": _t(b["Scadenza"], help="AAAA-MM-GG o GG/MM/AAAA"), "Stato": st.column_config.SelectboxColumn(b["Stato"], options=vr.STATI)})


def _leggi_vr():
    v, a1 = vr.normalizza_verbali(ss["vr_ver"].to_dict("records"))
    a, a2 = vr.normalizza_azioni(ss["vr_azi"].to_dict("records"), {x["Titolo"] for x in v})
    return (v, a), a1 + a2


def _ris_vr(o):
    c1, c2 = st.columns(2)
    c1.markdown("**Azioni aperte per responsabile**")
    with c1:
        _tabella(o["responsabili"])
    c2.markdown("**Tutte le azioni**")
    with c2:
        _tabella([{"": ICONE[r["Stato semaforo"]], "Cosa": r["Azione"], "Chi": r["Responsabile"], "Scadenza": r["Scadenza"], "Stato": r["Stato"]} for r in o["azioni"]])


def _coll_vr(out, dati, utente, audit):
    import chat
    import chat_ui
    st.caption("Le azioni aperte con un responsabile e una scadenza diventano **compiti** nella Chat interna: li vedi nella scheda «Compiti» e nel Calendario. "
               "Il responsabile deve essere il **nome utente** di una persona che può leggere il canale «Cantieri».")
    aperte = [a for a in dati[1] if a["Stato"] == "Aperta" and a["Responsabile"]]
    noti = {x.lower(): x for x in chat_ui._utenti_noti(None)}
    esistenti = set()
    try:
        esistenti = {(t["titolo"], t["assegnato"]) for t in chat.compiti(utente, tutti=True)}
    except Exception:
        pass
    da_fare = [a for a in aperte if a["Responsabile"].lower() in noti and (a["Azione"][:140], noti[a["Responsabile"].lower()]) not in esistenti]
    ignote = sorted({a["Responsabile"] for a in aperte if a["Responsabile"].lower() not in noti})
    st.write(f"Compiti da creare: **{len(da_fare)}**" + (f" · responsabili non riconosciuti: {', '.join(ignote)}" if ignote else ""))
    if st.button("✅ Crea i compiti nella chat", key="compiti_vr", disabled=not da_fare or sola_lettura()):
        me = ss.get("utente") or {}
        try:
            canali = chat.canali_visibili(me["username"])
            cid = next((c["id"] for c in canali if c["nome"] == "Cantieri"), None) or next((c["id"] for c in canali if c["tipo"] == "pubblico"), None)
            if not cid:
                st.error("Non c'è un canale pubblico dove scrivere: creane uno dalla Chat interna.")
            else:
                m = chat.invia(cid, me["username"], me.get("ruolo", "utente"), "📋 Azioni dal verbale: i compiti sono assegnati a chi di competenza.", link=("vr", "Verbali e riunioni"))
                n = 0
                for a in da_fare:
                    try:
                        chat.crea_compito(m["id"], me, a["Azione"], noti[a["Responsabile"].lower()], a["Scadenza"])
                        n += 1
                    except (ValueError, PermissionError) as e:
                        st.warning(f"«{a['Azione'][:40]}»: {e}")
                audit("vr_compiti_creati", str(n))
                st.success(f"Creati {n} compiti.")
        except Exception as e:
            st.error(f"Non sono riuscito a creare i compiti: {e}")


SPEC_VR = {
    "sigla": "vr", "titolo": "Verbali e riunioni", "sottotitolo": "Cosa si è deciso e chi deve fare cosa entro quando: le azioni diventano compiti.",
    "archivio": "i verbali", "file": "verbali", "unita": "azioni", "vuoto": "Inserisci almeno un verbale con titolo e data.",
    "tabelle": [{"chiave": "vr_ver", "titolo": "Verbali", "nota": "Una riga per riunione: data, titolo, partecipanti e decisioni prese.", "colonne": vr.COLONNE_VERBALI, "etichette": vr.ETICHETTE_VERBALI, "cfg": lambda: _cfg_vr()[0]},
                {"chiave": "vr_azi", "titolo": "Azioni", "nota": "Una riga per ogni cosa da fare. «Riunione» deve essere uguale al titolo del verbale.", "colonne": vr.COLONNE_AZIONI, "etichette": vr.ETICHETTE_AZIONI,
                 "cfg": lambda: _cfg_vr()[1], "altezza": 280}],
    "esempio": _es_vr, "leggi": _leggi_vr, "calcola": lambda d, p: vr.calcola_vr(*d, p), "ha_dati": lambda d: bool(d[0]),
    "param": [{"k": "preavviso_gg", "label": "Preavviso scadenze (giorni)", "kind": "int", "min": 0, "max": 30, "step": 1, "default": 3}],
    "strip": lambda o: [{"label": "Verbali", "value": str(o["kpi"]["n_verbali"]), "sub": f"{o['kpi']['n_azioni']} azioni", "tono": "info"},
                        {"label": "Azioni aperte", "value": str(o["kpi"]["aperte"]), "sub": f"{o['kpi']['fatte']} fatte", "tono": "info"},
                        {"label": "In ritardo", "value": str(o["kpi"]["in_ritardo"]), "sub": f"{o['kpi']['in_arrivo']} in arrivo", "tono": "bad" if o["kpi"]["in_ritardo"] else "ok"},
                        {"label": "Senza responsabile", "value": str(o["kpi"]["senza_resp"]), "sub": "azioni aperte", "tono": "warn" if o["kpi"]["senza_resp"] else "ok"}],
    "risultati": _ris_vr, "collegamenti": _coll_vr, "fogli": lambda o: {"Verbali": o["verbali"], "Azioni": o["azioni"], "Responsabili": o["responsabili"]},
}


# ----------------------------------------------------------------------------
# ARCHIVIO DOCUMENTI
# ----------------------------------------------------------------------------
@senza_esempi
def _es_ad():
    return (_mk(ad.COLONNE_DOC, [("Villa Lago", "Contratto", "Contratto d'appalto firmato", "https://drive.google.com/esempio/contratto-villa-lago", "", "Direzione"),
                                 ("Villa Lago", "Sicurezza", "POS aggiornato", "https://drive.google.com/esempio/pos-villa-lago", g(25), "Anna"),
                                 ("Scuola Elementare", "Contratto", "Contratto d'appalto", "https://drive.google.com/esempio/contratto-scuola", "", "Direzione"),
                                 ("Scuola Elementare", "Autorizzazioni", "Permesso di costruire", "S:\\Commesse\\Scuola\\permesso.pdf", g(-10), "Luca")]),)


def _cfg_ad():
    a = ad.ETICHETTE_DOC
    return {"Commessa": _t(a["Commessa"]), "Categoria": st.column_config.SelectboxColumn(a["Categoria"], options=ad.CATEGORIE), "Titolo": _t(a["Titolo"], width="large"),
            "Link": st.column_config.TextColumn(a["Link"], width="large", help="Indirizzo che inizia con https:// (Drive, SharePoint, cartella condivisa)"), "Scadenza": _t(a["Scadenza"], help="AAAA-MM-GG o GG/MM/AAAA"), "Responsabile": _t(a["Responsabile"])}


def _leggi_ad():
    d, a = ad.normalizza_doc(ss["ad_doc"].to_dict("records"))
    return (d,), a


def _ris_ad(o):
    _tabella([{"": ICONE[r["Stato"]], "Commessa": r["Commessa"], "Categoria": r["Categoria"], "Titolo": r["Titolo"], "Apri": r["Link"] if r["Link ok"] else None, "Scadenza": r["Scadenza"], "Responsabile": r["Responsabile"]} for r in o["documenti"]],
             column_config={"Apri": st.column_config.LinkColumn("Apri", display_text="🔗 Apri")})
    c1, c2 = st.columns(2)
    c1.markdown("**Per commessa**")
    with c1:
        _tabella(o["commesse"])
    c2.markdown("**Documenti attesi che mancano**")
    if o["mancanti"]:
        with c2:
            _tabella(o["mancanti"])
    else:
        c2.success("Ogni commessa ha i documenti attesi.")


SPEC_AD = {
    "sigla": "ad", "titolo": "Archivio documenti per commessa", "sottotitolo": "Dove sta ogni documento, con il link, la scadenza e cosa manca per commessa.",
    "archivio": "l'archivio documenti", "file": "archivio_documenti", "unita": "documenti", "vuoto": "Inserisci almeno un documento con commessa e titolo.",
    "tabelle": [{"chiave": "ad_doc", "titolo": "Documenti", "nota": "I file restano dove sono (Drive, SharePoint, server): qui metti il link e la scadenza. Il link deve iniziare con https://.", "colonne": ad.COLONNE_DOC, "etichette": ad.ETICHETTE_DOC,
                 "cfg": _cfg_ad, "altezza": 320}],
    "esempio": _es_ad, "leggi": _leggi_ad, "calcola": lambda d, p: ad.calcola_ad(d[0], p), "ha_dati": lambda d: bool(d[0]),
    "param": [{"k": "preavviso_gg", "label": "Preavviso scadenze (giorni)", "kind": "int", "min": 0, "max": 180, "step": 5, "default": 30},
              {"k": "attesi", "label": "Documenti attesi per ogni commessa", "kind": "text", "default": "Contratto, Sicurezza, Contabilità", "help": "Categorie separate da virgola"}],
    "strip": lambda o: [{"label": "Documenti", "value": str(o["kpi"]["n_doc"]), "sub": f"{o['kpi']['n_commesse']} commesse", "tono": "info"},
                        {"label": "Scaduti", "value": str(o["kpi"]["scaduti"]), "sub": f"{o['kpi']['in_arrivo']} in arrivo", "tono": "bad" if o["kpi"]["scaduti"] else "ok"},
                        {"label": "Mancanti", "value": str(o["kpi"]["mancanti"]), "sub": "documenti attesi", "tono": "warn" if o["kpi"]["mancanti"] else "ok"},
                        {"label": "Senza link", "value": str(o["kpi"]["senza_link"]), "sub": "non apribili", "tono": "warn" if o["kpi"]["senza_link"] else "ok"}],
    "risultati": _ris_ad, "collegamenti": lambda out, dati, utente, audit: st.info("Le scadenze dei documenti compaiono nel **Calendario**. Il collegamento con Monday e con le cartelle aziendali lo decidiamo insieme: oggi basta incollare il link."),
    "fogli": lambda o: {"Documenti": o["documenti"], "Commesse": o["commesse"], "Mancanti": o["mancanti"]},
}


# ----------------------------------------------------------------------------
# MARGINI PER COMMESSA
# ----------------------------------------------------------------------------
_CHIAVI = {"sl": "sl_com", "sa": "sa_con", "pr": "pr_per", "mt": "mt_ord", "mz": "mz_mezzi"}


def _payload(m):
    """Dati dello strumento: quelli aperti in sessione (se non sono di esempio) oppure l'ultimo salvataggio."""
    if _CHIAVI[m] in ss:
        if ss.get(f"{m}_demo"):
            return None, "esempi esclusi"
        import mz_ui
        racc = {"sl": lambda: __import__("sl_ui")._raccogli(), "mz": mz_ui._raccogli}.get(m) or SPEC_BY[m]["_raccogli"]
        return racc(), "sessione"
    try:
        el = storage.elenca_pratiche(modulo=m)
        if el:
            return storage.carica_pratica(el[0]["nome"], modulo=m), f"salvataggio «{el[0]['nome']}»"
    except Exception:
        pass
    return None, "nessun dato"


def render_mc(fcr_uri, audit=None, utente=""):
    st.markdown(theme.hero(fcr_uri, "Margini per commessa", "Contratto, SAL e costi reali di subappalti, manodopera, materiali e mezzi: il margine vero di ogni commessa."), unsafe_allow_html=True)
    guida.mostra("mc")
    pay, fonti = {}, {}
    for m in _CHIAVI:
        pay[m], fonti[m] = _payload(m)
    pay = {m: v for m, v in pay.items() if v}
    st.caption("Dati letti da: " + " · ".join(f"{n}: {fonti[m]}" for m, n in (("sl", "SAL"), ("sa", "Subappalti"), ("pr", "Presenze"), ("mt", "Materiali"), ("mz", "Mezzi"))))
    scelte = st.multiselect("Costi da contare, oltre a quelli inseriti in SAL", [mc.FONTI[f] for f in mc.FONTI_ORDINE], default=[mc.FONTI[f] for f in mc.FONTI_ORDINE if f in pay], key="mc_fonti",
                            help="Se una fonte non ha dati non cambia nulla. I costi già mandati a SAL da quegli strumenti non vengono contati due volte.")
    inv = {v: k for k, v in mc.FONTI.items()}
    out = mc.calcola_mc(pay, tuple(inv[s] for s in scelte), dt.date.today())
    if not out:
        st.info("Per calcolare i margini servono le **commesse** in «SAL e contabilità lavori» (contratto, costi preventivati, avanzamento). Inseriscile o salvale e torna qui.")
        return
    k = out["kpi"]
    dif = k["differenza_vs_sal"]
    st.markdown(theme.stat_strip([
        {"label": "Margine finale previsto", "value": EUR(k["margine_finale"]), "sub": f"{fmt_num(k['margine_finale_pct'], 1)}% del contratto", "tono": "bad" if k["margine_finale"] < 0 else "info"},
        {"label": "Preventivato", "value": EUR(k["margine_atteso"]), "sub": f"{fmt_num(k['margine_atteso_pct'], 1)}%", "tono": "info"},
        {"label": "Costi aggiunti", "value": EUR(k["costi_extra"]), "sub": "da subappalti, ore, materiali, mezzi", "tono": "info"},
        {"label": "Effetto sul margine", "value": EUR(dif), "sub": "rispetto a quanto vede SAL", "tono": "bad" if dif < -1 else "ok"}]), unsafe_allow_html=True)
    for a in out["avvisi"][:10]:
        st.warning(a)
    st.subheader("Commesse")
    righe = [{"": ICONE[c["Stato"]], "Commessa": c["Commessa"], "Contratto": c["Contratto totale"], "Avanz. %": c["Avanzamento %"], "Costi sostenuti": c["Costi sostenuti"], "Margine corrente": c["Margine corrente"],
              "Margine finale %": c["Margine finale %"], "Preventivato %": c["Margine atteso %"], "Scostamento pp": c["Scostamento margine (pp)"], "Costi a finire": c["Costi a finire (EAC)"]} for c in out["commesse"]]
    st.dataframe(pd.DataFrame(righe).round(1), hide_index=True, width="stretch")
    st.subheader("Da dove arrivano i costi")
    st.dataframe(pd.DataFrame(out["composizione"]).round(0), hide_index=True, width="stretch")
    st.caption("Margine finale = contratto − costi a finire stimati (costi sostenuti ÷ avanzamento, se l'avanzamento è almeno 5%). È una stima di gestione, non un dato contabile.")
    st.download_button("📥 Scarica in Excel", _xlsx({"Commesse": out["commesse"], "Costi": out["composizione"], "Fatture": out["fatture"]}), file_name=f"margini_commesse_{dt.date.today().isoformat()}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dlx_mc")


# ----------------------------------------------------------------------------
# PUNTO DI INGRESSO (come gli altri moduli: sa_ui.render(fcr_uri, audit, utente))
# ----------------------------------------------------------------------------
SPEC_BY = {"sa": SPEC_SA, "pr": SPEC_PR, "mt": SPEC_MT, "vr": SPEC_VR, "ad": SPEC_AD}


def _modulo(sg):
    S = SPEC_BY[sg]

    def raccogli():
        d = {T["chiave"].split("_", 1)[1]: ss[T["chiave"]].to_dict("records") for T in S["tabelle"]}
        d["params"] = {P["k"]: ss.get(f"{sg}_{P['k']}", P["default"]) for P in S["param"]}
        return d
    return types.SimpleNamespace(render=lambda fcr_uri, audit=None, utente="": _motore(S, fcr_uri, audit, utente), _raccogli=raccogli)


sa_ui, pr_ui, mt_ui, vr_ui, ad_ui = (_modulo(x) for x in ("sa", "pr", "mt", "vr", "ad"))
mc_ui = types.SimpleNamespace(render=render_mc)
for _s in SPEC_BY.values():
    _s.setdefault("_raccogli", None)
SPEC_SA["_raccogli"], SPEC_PR["_raccogli"], SPEC_MT["_raccogli"], SPEC_VR["_raccogli"], SPEC_AD["_raccogli"] = (m._raccogli for m in (sa_ui, pr_ui, mt_ui, vr_ui, ad_ui))
