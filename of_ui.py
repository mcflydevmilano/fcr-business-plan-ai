"""of_ui.py - Offerta e finanziamenti: dal computo all'offerta, con le richieste di finanziamento di Condominio e condomini."""
import datetime as dt
import io

import pandas as pd
import streamlit as st

import guida
import of
import theme
from ui_util import pannello_archivio, sola_lettura, sostituisci_tabella, tabella_modificabile

ss = st.session_state
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
TESTI = ("cod", "condominio", "indirizzo", "cf", "zona", "commerciale", "data")
AREE = {"descrizione": "Descrizione dell'intervento e obiettivi", "stato_fatto": "Stato di fatto (criticità visibili)", "opere_comuni": "Perimetro comune (una riga per la sintesi)",
        "opere_comuni_dettaglio": "Opere comuni alle alternative (dettaglio, facoltativo)", "imprevisti": "Lavorazioni impreviste (se vuoto: testo standard)",
        "carico_condominio": "A carico del Condominio (se vuoto: testo standard)", "carico_condomini": "A carico dei singoli condòmini (se vuoto: testo standard)"}
ETI_PRAT = {"cod": "Codice pratica", "condominio": "Condominio", "indirizzo": "Indirizzo e città", "cf": "Codice fiscale del condominio", "zona": "Zona (per il confronto di mercato)",
            "commerciale": "Commerciale", "data": "Data dell'offerta"}
DF = {"of_voci": of.COL_VOCI, "of_sconti": of.COL_SCONTI, "of_unita": of.COL_UNITA, "of_annunci": of.COL_ANNUNCI, "of_conf": ["Parametro", "A", "B"], "of_ric": of.COL_FIN,
      "of_cat": ["cat", "id", "quota"]}
NUM = {"of_voci": ("Quantita", "Prezzo"), "of_sconti": ("Importo",), "of_unita": ("Millesimi", "Mq"), "of_annunci": ("Mq", "Prezzo"), "of_ric": ("Lavori", "Richiesto", "Deliberato"), "of_cat": ("quota",)}


COSI_COM_E = "Così com'è"

def _df(chiave, righe=None):
    d = pd.DataFrame(righe or [], columns=DF[chiave])
    for c in NUM.get(chiave, ()):
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0.0)
    for c in d.columns:
        if c not in NUM.get(chiave, ()):
            d[c] = d[c].fillna("").astype(str).replace("nan", "")
    return d


def _rec(chiave):
    d = ss[chiave]
    return d.where(pd.notna(d), None).to_dict("records")


def _prest_df(codici):
    cod = set(codici or [])
    return pd.DataFrame([{"Sel": p["cod"] in cod, "Cod": p["cod"], "Fase": p["fase"], "Descrizione": p["desc"], "Q Edilizia": p["q"].get("EDILIZIA", 0.0),
                          "Q Strutture": p["q"].get("STRUTTURE", 0.0), "Q Impianti": p["q"].get("IMPIANTI", 0.0)} for p in of.PRESTAZIONI])


def _init():
    oggi = dt.date.today()
    for k in TESTI:
        ss.setdefault(f"of_p_{k}", f"{oggi.day} {MESI[oggi.month - 1]} {oggi.year}" if k == "data" else "")
    for k in AREE:
        ss.setdefault(f"of_p_{k}", "")
    ss.setdefault("of_p_ui", 0)
    ss.setdefault("of_p_validita_gg", 15)
    for h in ("A", "B"):
        ss.setdefault(f"of_nome_{h}", "")
        ss.setdefault(f"of_desc_{h}", "")
        ss.setdefault(f"of_impman_{h}", 0.0)
        ss.setdefault(f"of_parman_{h}", 0.0)
    ss.setdefault("of_bim", False)
    ss.setdefault("of_sconto", 0.0)
    ss.setdefault("of_rl_imp", 0.0)
    ss.setdefault("of_rl_pct", 0.0)
    ss.setdefault("of_iva_lav", 10.0)
    ss.setdefault("of_cassa", 4.0)
    ss.setdefault("of_iva_prof", 22.0)
    ss.setdefault("of_tan", 6.0)
    ss.setdefault("of_durate", "3, 5, 10")
    ss.setdefault("of_detr", "50, 36")
    ss.setdefault("of_anni", 10)
    ss.setdefault("of_risp", 0.0)
    ss.setdefault("of_base_spese", False)
    ss.setdefault("of_sc_opz", "A")
    ss.setdefault("of_sc_anni", 10)
    ss.setdefault("of_sc_det", 50)
    ss.setdefault("of_m_ante", 0.0)
    ss.setdefault("of_m_post", 0.0)
    ss.setdefault("of_mq", 100)
    for c in DF:
        if c not in ss:
            ss[c] = _df(c, [{"cat": "EDILIZIA", "id": "E.06", "quota": 100.0}] if c == "of_cat" else None)
    if "of_prest" not in ss:
        ss["of_prest"] = _prest_df(of.PARCELLE_DEFAULT["codici"])


def _numeri(txt, default):
    out = []
    for x in str(txt).replace(";", ",").split(","):
        try:
            out.append(float(x.strip().replace(",", ".")))
        except ValueError:
            pass
    return out or default


def _raccogli():
    durate = [int(x) if float(x).is_integer() else x for x in _numeri(ss["of_durate"], [3, 5, 10])]
    det = _numeri(ss["of_detr"], [50, 36])
    codici = [r["Cod"] for r in _rec("of_prest") if r.get("Sel")]
    return {
        "pratica": {**{k: ss[f"of_p_{k}"] for k in TESTI}, **{k: ss[f"of_p_{k}"] for k in AREE}, "ui": ss["of_p_ui"], "validita_gg": ss["of_p_validita_gg"]},
        "voci": _rec("of_voci"), "sconti": _rec("of_sconti"),
        "opzioni": {h: {"nome": ss[f"of_nome_{h}"], "desc": ss[f"of_desc_{h}"], "imponibile_manuale": ss[f"of_impman_{h}"]} for h in ("A", "B")},
        "parcelle": {"categorie": _rec("of_cat"), "codici": codici, "bim": ss["of_bim"], "sconto_pct": ss["of_sconto"], "manuale": {h: ss[f"of_parman_{h}"] for h in ("A", "B")},
                     "rl_importo": ss["of_rl_imp"], "rl_pct": ss["of_rl_pct"]},
        "qte_par": {"iva_lavori": ss["of_iva_lav"] / 100, "cassa": ss["of_cassa"] / 100, "iva_prof": ss["of_iva_prof"] / 100},
        "params": {"tan": ss["of_tan"] / 100, "durate": durate, "detrazioni": det, "anni": int(ss["of_anni"]), "risparmio_annuo": ss["of_risp"], "base_con_spese": ss["of_base_spese"]},
        "scenario": {"opzione": ss["of_sc_opz"], "anni": ss["of_sc_anni"], "detrazione": ss["of_sc_det"]},
        "unita": _rec("of_unita"), "annunci": _rec("of_annunci"), "confronto": _rec("of_conf"), "richieste": _rec("of_ric"),
        "mercato_manuale": {"ante": ss["of_m_ante"], "post": ss["of_m_post"]}, "mq_esempio": ss["of_mq"],
    }


def _applica(p, nome):
    pr, pend = p.get("pratica") or {}, {}
    for k in TESTI + tuple(AREE):
        pend[f"of_p_{k}"] = str(pr.get(k) or "")
    pend["of_p_ui"] = int(pr.get("ui") or 0)
    pend["of_p_validita_gg"] = int(pr.get("validita_gg") or 15)
    for h in ("A", "B"):
        o = (p.get("opzioni") or {}).get(h) or {}
        pend.update({f"of_nome_{h}": o.get("nome") or "", f"of_desc_{h}": o.get("desc") or "", f"of_impman_{h}": float(o.get("imponibile_manuale") or 0),
                     f"of_parman_{h}": float(((p.get("parcelle") or {}).get("manuale") or {}).get(h) or 0)})
    pa, qp, fp = {**of.PARCELLE_DEFAULT, **(p.get("parcelle") or {})}, {**of.QTE_DEFAULT, **(p.get("qte_par") or {})}, {**of.PARAMS_DEFAULT, **(p.get("params") or {})}
    sc, mm = p.get("scenario") or {}, p.get("mercato_manuale") or {}
    pend.update({"of_bim": bool(pa.get("bim")), "of_sconto": float(pa.get("sconto_pct") or 0), "of_rl_imp": float(pa.get("rl_importo") or 0), "of_rl_pct": float(pa.get("rl_pct") or 0),
                 "of_iva_lav": qp["iva_lavori"] * 100, "of_cassa": qp["cassa"] * 100, "of_iva_prof": qp["iva_prof"] * 100,
                 "of_tan": fp["tan"] * 100, "of_durate": ", ".join(str(x) for x in fp["durate"]), "of_detr": ", ".join(str(int(x)) for x in fp["detrazioni"]), "of_anni": int(fp["anni"]),
                 "of_risp": float(fp.get("risparmio_annuo") or 0), "of_base_spese": bool(fp.get("base_con_spese")),
                 "of_sc_opz": sc.get("opzione") or "A", "of_sc_anni": sc.get("anni") or 10, "of_sc_det": sc.get("detrazione") or 50,
                 "of_m_ante": float(mm.get("ante") or 0), "of_m_post": float(mm.get("post") or 0), "of_mq": int(p.get("mq_esempio") or 100)})
    for chiave, campo in (("of_voci", "voci"), ("of_sconti", "sconti"), ("of_unita", "unita"), ("of_annunci", "annunci"), ("of_conf", "confronto"), ("of_ric", "richieste")):
        sostituisci_tabella(chiave, _df(chiave, p.get(campo)))
    sostituisci_tabella("of_cat", _df("of_cat", pa.get("categorie")))
    sostituisci_tabella("of_prest", _prest_df(pa.get("codici")))
    ss["_pending"] = pend


def _euro(v, d=0):
    return of.euro(v, d)


def _scarica(etichetta, dati, nome, mime, chiave):
    st.download_button(etichetta, dati, file_name=nome, mime=mime, key=chiave)


# --------------------------------------------------------------------------------------------------------------------------- schede
def _scheda_pratica():
    st.caption("I dati della pratica e i testi che finiscono nell'offerta. I campi vuoti usano i testi standard FCR.")
    try:
        import storage
        import rc
        if storage.elenca_pratiche(modulo="rc"):
            nome_rc = storage.elenca_pratiche(modulo="rc")[0]["nome"]
            righe, _ = rc.normalizza((storage.carica_pratica(nome_rc, modulo="rc") or {}).get("pratiche"))
            att = [r for r in righe if r["Archivio"] == "Attiva" and r["Codice"]]
            if att:
                sc = st.selectbox("Prendi i dati dal Registro commerciale", ["—"] + [f"{r['Codice']} · {r['Indirizzo']} {r['Citta']}".strip() for r in att], key="of_da_rc")
                if sc != "—" and st.button("Compila dal registro", key="of_da_rc_ok"):
                    r = att[[f"{x['Codice']} · {x['Indirizzo']} {x['Citta']}".strip() for x in att].index(sc)]
                    ss["_pending"] = {"of_p_cod": r["Codice"], "of_p_indirizzo": f"{r['Indirizzo']} - {r['Citta']}".strip(" -"), "of_p_ui": int(r["UI"] or 0),
                                      "of_p_commerciale": r["Commerciale"], "of_p_condominio": r["Amministratore"] and f"Condominio {r['Indirizzo']}" or ""}
                    st.rerun()
    except Exception:
        pass
    c = st.columns(3)
    for i, k in enumerate(TESTI):
        c[i % 3].text_input(ETI_PRAT[k], key=f"of_p_{k}", disabled=sola_lettura())
    c1, c2 = st.columns(2)
    c1.number_input("Unità abitative (UI)", 0, 2000, step=1, key="of_p_ui")
    c2.number_input("Validità dell'offerta (giorni)", 1, 120, step=1, key="of_p_validita_gg")
    for k, e in AREE.items():
        st.text_area(e, key=f"of_p_{k}", height=90 if k in ("descrizione", "stato_fatto") else 70, disabled=sola_lettura())


def _scheda_computo(ctx):
    st.markdown("Carica il **computo metrico** del collega (foglio «Table 1» con i capitoli A–E e le ipotesi A/B; gli sconti sono letti dal «Foglio1»), oppure scrivi le voci a mano.")
    if not sola_lettura():
        up = st.file_uploader("Computo metrico (.xlsx)", type=["xlsx"], key="of_up_cme")
        if up is not None:
            try:
                voci, sconti = of.import_cme(up.getvalue())
            except Exception as e:
                st.error(f"File non leggibile: {e}")
                voci = []
            if voci:
                st.success(f"Lette {len(voci)} voci e {len(sconti)} sconti.")
                if st.button("Importa il computo (sostituisce le voci attuali)", type="primary", key="of_imp_cme"):
                    sostituisci_tabella("of_voci", _df("of_voci", voci))
                    sostituisci_tabella("of_sconti", _df("of_sconti", sconti))
                    st.rerun()
            elif up is not None:
                st.error("Non ho trovato voci di computo nel file.")
    t = ctx["computo"]
    if _rec("of_voci"):
        st.markdown(theme.stat_strip([
            {"label": "Parte comune", "value": _euro(t["comune"]), "sub": f"sconti comuni {_euro(t['sconti_comuni'])}", "tono": "info"},
            {"label": "Ipotesi A - imponibile", "value": _euro(t["A"]["imponibile"]), "sub": f"voci {_euro(t['A']['voci'])} · sconto {_euro(t['A']['sconti'])}", "tono": "ok"},
            {"label": "Ipotesi B - imponibile", "value": _euro(t["B"]["imponibile"]), "sub": f"voci {_euro(t['B']['voci'])} · sconto {_euro(t['B']['sconti'])}", "tono": "warn"},
            {"label": "Differenza A − B", "value": _euro(t["differenza"]), "sub": "sull'imponibile lavori", "tono": "info"}]), unsafe_allow_html=True)
        cap = of.per_capitolo(_rec("of_voci"))
        st.dataframe(pd.DataFrame([{"Capitolo": k[0], "Ipotesi": k[1] or "comune", "Importo": v} for k, v in sorted(cap.items())]).assign(Importo=lambda d: d["Importo"].map(_euro)),
                     hide_index=True, width="stretch", height=220)
    else:
        st.info("Nessuna voce di computo: importa il file del collega o scrivi le voci qui sotto. Senza ipotesi A/B (colonna Ipotesi vuota) tutte le voci valgono per l'unica opzione A.")
    t_ = st.column_config.TextColumn
    n_ = st.column_config.NumberColumn
    with st.expander("✏️ Voci di computo (modifica, aggiungi, togli)", expanded=not _rec("of_voci")):
        tabella_modificabile("of_voci", ss["of_voci"], {"Cap": t_("Cap.", width="small"), "Cod": t_("N.", width="small"), "Descrizione": t_("Descrizione", width="large"), "UM": t_("UM", width="small"),
                                                       "Quantita": n_("Quantità", format="%.2f"), "Prezzo": n_("Prezzo unit. €", format="%.2f"),
                                                       "Ipotesi": st.column_config.SelectboxColumn("Ipotesi", options=list(of.IPOTESI), help="vuoto = voce comune a entrambe")}, altezza=380)
        st.caption("Importo di ogni voce = quantità × prezzo. Lavori «a corpo»: quantità 1 e prezzo = importo.")
    with st.expander("🏷️ Sconti (negativi) comuni o per ipotesi"):
        tabella_modificabile("of_sconti", ss["of_sconti"], {"Descrizione": t_("Descrizione", width="large"), "Ipotesi": st.column_config.SelectboxColumn("Ipotesi", options=list(of.IPOTESI)),
                                                           "Importo": n_("Importo € (negativo)", format="%.2f")}, altezza=200)
    with st.expander("🅰️🅱️ Nome e descrizione delle due opzioni"):
        for h in ("A", "B"):
            c1, c2 = st.columns([1, 2])
            c1.text_input(f"Opzione {h} - nome", key=f"of_nome_{h}", placeholder="es. guaina + pannello sandwich")
            c2.text_area(f"Opzione {h} - descrizione tecnica", key=f"of_desc_{h}", height=90)
            c1.number_input(f"Imponibile {h} a mano (0 = dal computo)", 0.0, step=100.0, key=f"of_impman_{h}")
        tabella_modificabile("of_conf", ss["of_conf"], {"Parametro": st.column_config.TextColumn("Parametro", width="medium"), "A": st.column_config.TextColumn("Opzione A"),
                                                       "B": st.column_config.TextColumn("Opzione B")}, altezza=220)
        st.caption("La tabella di confronto tecnico compare nell'offerta; l'ultima riga (costo lavori) la aggiunge l'app.")


def _scheda_parcelle(ctx):
    st.markdown("Compenso professionale secondo il **D.Lgs. 36/2023** (all. I.13): **V × P × G × ΣQ**. P = 20,411% sotto 25.000 €, altrimenti 0,03 + 10 / V^0,4. "
                "V è l'importo dei lavori dell'opzione, ripartito sulle categorie.")
    c1, c2 = st.columns(2)
    st.markdown("**1. Categorie dell'opera** (quota % dei lavori e destinazione funzionale, che dà il grado di complessità G)")
    cat_cfg = {"cat": st.column_config.SelectboxColumn("Categoria", options=list(of.CATEGORIE), required=True),
               "id": st.column_config.SelectboxColumn("Destinazione (ID opera)", options=[o["id"] for o in of.OPERE], required=True, help="Es. E.06 = edilizia residenziale corrente, G = 0,95"),
               "quota": st.column_config.NumberColumn("Quota dei lavori %", min_value=0.0, max_value=100.0, format="%.1f")}
    tabella_modificabile("of_cat", ss["of_cat"], cat_cfg, altezza=130)
    ids = {r["id"]: r for r in of.OPERE}
    st.caption(" · ".join(f"{r['id']}: G {ids[r['id']]['g']} {ids[r['id']]['desc'][:50]}" for r in _rec("of_cat") if r.get("id") in ids))
    st.markdown("**2. Prestazioni incluse** (spunta quelle che fate)")
    b1, b2, b3, _ = st.columns([1.3, 1.6, 1, 2])
    for col, (lab, cods) in zip((b1, b2), of.PRESET.items()):
        if col.button(f"+ {lab}", key=f"of_pre_{lab}"):
            d = ss["of_prest"].copy()
            d.loc[d["Cod"].isin(cods), "Sel"] = True
            sostituisci_tabella("of_prest", d)
            st.rerun()
    if b3.button("Nessuna", key="of_pre_no"):
        d = ss["of_prest"].copy()
        d["Sel"] = False
        sostituisci_tabella("of_prest", d)
        st.rerun()
    nc = st.column_config.NumberColumn
    tabella_modificabile("of_prest", ss["of_prest"], {"Sel": st.column_config.CheckboxColumn("Sì", width="small"), "Cod": st.column_config.TextColumn("Codice", disabled=True, width="small"),
                                                     "Fase": st.column_config.TextColumn("Fase", disabled=True, width="small"), "Descrizione": st.column_config.TextColumn("Prestazione", disabled=True, width="large"),
                                                     "Q Edilizia": nc(disabled=True, format="%.4f"), "Q Strutture": nc(disabled=True, format="%.4f"), "Q Impianti": nc(disabled=True, format="%.4f")},
                         altezza=300, num_rows="fixed")
    st.markdown("**3. Altre voci**")
    d1, d2, d3 = st.columns(3)
    d1.checkbox("Progettazione BIM (+10%)", key="of_bim")
    d2.number_input("Sconto sul corrispettivo %", 0.0, 100.0, step=0.5, key="of_sconto")
    d3.caption("Spese ed oneri accessori: 25% fino a 1 milione di lavori, poi decrescenti (formula del foglio).")
    r1, r2 = st.columns(2)
    r1.number_input("Responsabile Lavori - importo lordo €", 0.0, step=100.0, key="of_rl_imp")
    r2.number_input("oppure % dei lavori (se > 0 prevale)", 0.0, 20.0, step=0.1, key="of_rl_pct", help="Nel foglio di esempio l'etichetta dice 3% ma l'importo (39.605 €) è il 6,5% dei lavori: scegli tu.")
    m1, m2 = st.columns(2)
    m1.number_input("Parcella lorda Opzione A a mano € (0 = calcolata)", 0.0, step=100.0, key="of_parman_A")
    m2.number_input("Parcella lorda Opzione B a mano € (0 = calcolata)", 0.0, step=100.0, key="of_parman_B")
    st.markdown("**Risultato**")
    righe = []
    for h, o in ctx["opzioni"].items():
        d = o["parcella_dett"]
        righe.append({"Opzione": h, "Lavori (V)": _euro(o["imponibile"]), "Parcella lorda": _euro(o["qte"]["parcella"]["lorda"], 2),
                      "Origine": "inserita a mano" if d is None else f"calcolata: compenso {_euro(d['compenso'], 2)} + spese {_euro(d['spese'], 2)}",
                      "Incidenza sui lavori": f"{o['qte']['parcella']['lorda'] / o['imponibile'] * 100:.2f}%"})
    if righe:
        st.dataframe(pd.DataFrame(righe), hide_index=True, width="stretch")
        for h, o in ctx["opzioni"].items():
            d = o["parcella_dett"]
            if d and d["righe"]:
                with st.expander(f"Dettaglio calcolo Opzione {h}"):
                    st.dataframe(pd.DataFrame([{"Categoria": of.CATEGORIE[r["cat"]], "V": _euro(r["V"]), "P": f"{r['P'] * 100:.4f}%", "G": r["G"], "ΣQ": round(r["SQ"], 4), "Compenso V·P·G·ΣQ": _euro(r["compenso"], 2)}
                                               for r in d["righe"]]), hide_index=True, width="stretch")
                    st.dataframe(pd.DataFrame([{"Fase": of.FASI[f], "Compenso": _euro(v, 2)} for f, v in d["per_fase"].items()]), hide_index=True, width="stretch")
    else:
        st.info("Mancano i lavori: importa il computo nella scheda «2».")


def _scheda_qte(ctx):
    a, b, c = st.columns(3)
    a.number_input("IVA lavori %", 0.0, 30.0, step=1.0, key="of_iva_lav")
    b.number_input("Cassa previdenziale %", 0.0, 10.0, step=0.5, key="of_cassa")
    c.number_input("IVA professionisti %", 0.0, 30.0, step=1.0, key="of_iva_prof")
    if not ctx["opzioni"]:
        st.info("Il quadro economico compare appena ci sono i lavori nel computo.")
        return
    cols = st.columns(len(ctx["opzioni"]))
    for col, (h, o) in zip(cols, ctx["opzioni"].items()):
        q = o["qte"]
        col.markdown(f"#### Opzione {h}")
        col.dataframe(pd.DataFrame([
            ["Lavori imponibili", q["imponibile"]], [f"IVA lavori {ss['of_iva_lav']:.0f}%", q["iva_lavori"]], ["Totale lavori con IVA", q["lavori_iva"]],
            ["Parcella lorda", q["parcella"]["lorda"]], [f"Cassa {ss['of_cassa']:.0f}%", q["parcella"]["cassa"]], [f"IVA {ss['of_iva_prof']:.0f}% parcella", q["parcella"]["iva"]], ["Totale parcella", q["parcella"]["totale"]],
            ["Responsabile Lavori lordo", q["rl"]["lorda"]], ["Cassa", q["rl"]["cassa"]], ["IVA", q["rl"]["iva"]], ["Totale Responsabile Lavori", q["rl"]["totale"]],
            ["Totale spese professionali", q["spese"]], ["TOTALE PROGETTO", q["totale"]], ["Capitale per millesimo", q["totale"] / 1000], ["Incidenza spese professionali sui lavori", q["incidenza_prof"] * 100]],
            columns=["Voce", "Importo"]).assign(Importo=lambda d: d["Importo"].map(lambda v: f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))), hide_index=True, width="stretch", height=560)


def _scheda_fin(ctx):
    st.markdown("**Ipotesi del finanziamento** (cambiano per pratica)")
    a, b, c, d = st.columns(4)
    a.number_input("TAN annuo %", 0.0, 20.0, step=0.25, key="of_tan")
    b.text_input("Durate in anni", key="of_durate", help="Separate da virgola, es. 3, 5, 10")
    c.text_input("Detrazioni % (scenari)", key="of_detr", help="es. 50, 36")
    d.number_input("Anni di recupero fiscale", 1, 20, step=1, key="of_anni")
    e, f = st.columns(2)
    e.number_input("Risparmio energetico stimato dell'edificio (€/anno)", 0.0, step=500.0, key="of_risp", help="Dal progettista o dall'APE. 0 = non incluso nelle simulazioni.")
    f.checkbox("Recupero fiscale anche sulle spese tecniche (oltre ai lavori con IVA)", key="of_base_spese")
    if not ctx["opzioni"]:
        st.info("Servono i lavori nel computo per simulare il finanziamento.")
    for h, o in ctx["opzioni"].items():
        st.markdown(f"#### Opzione {h} - capitale {_euro(o['qte']['totale'], 2)}")
        rr = []
        for x in ctx["sim"][h]:
            row = {"Durata": f"{x['anni']} anni", "Rata condominio/mese": _euro(x["rata"], 2), "Rata/millesimo/mese": _euro(x["rata"] / 1000, 2), "Interessi": _euro(x["interessi"], 2), "Totale rimborsato": _euro(x["totale"], 2)}
            for dd in ctx["params"]["detrazioni"]:
                row[f"Impatto reale/mill./mese ({int(dd)}%)"] = _euro(x[f"impatto{int(dd)}"] / 1000, 2)
                row[f"Costo reale/mill. ({int(dd)}%)"] = _euro(x[f"costo_reale{int(dd)}"] / 1000, 2)
            rr.append(row)
        st.dataframe(pd.DataFrame(rr), hide_index=True, width="stretch")
    st.caption("Impatto reale = rata − recupero fiscale mensile − risparmio energetico mensile. Costo reale = capitale + interessi − recupero fiscale − risparmio sul periodo.")
    st.markdown("---\n**Tabella millesimale** (una per condominio)")
    if not sola_lettura():
        up = st.file_uploader("Importa la tabella millesimale (.xlsx con colonne Unità, Proprietario, Millesimi, Mq)", type=["xlsx"], key="of_up_mill")
        if up is not None:
            try:
                un = of.import_millesimi(up.getvalue())
            except Exception as e:
                st.error(f"File non leggibile: {e}")
                un = []
            if un:
                st.success(f"Lette {len(un)} unità, millesimi totali {of.totale_millesimi(un):.3f}.")
                if st.button("Importa la tabella", type="primary", key="of_imp_mill"):
                    sostituisci_tabella("of_unita", _df("of_unita", un))
                    ss["_pending"] = {"of_p_ui": len(un)}
                    st.rerun()
    tabella_modificabile("of_unita", ss["of_unita"], {"Unita": st.column_config.TextColumn("Unità"), "Proprietario": st.column_config.TextColumn("Proprietario", width="large"),
                                                     "Millesimi": st.column_config.NumberColumn("Millesimi", format="%.3f"), "Mq": st.column_config.NumberColumn("m²", format="%.1f")}, altezza=260)
    un = ctx["unita"]
    if un:
        tot = of.totale_millesimi(un)
        (st.success if abs(tot - 1000) < 0.5 else st.warning)(f"Totale millesimi: {tot:.3f} su 1000 · {len(un)} unità.")
    if un and ctx["opzioni"]:
        st.markdown("**Ripartizione per unità** (scegli lo scenario)")
        s1, s2, s3 = st.columns(3)
        s1.selectbox("Opzione", list(ctx["opzioni"]), key="of_sc_opz")
        s2.number_input("Durata (anni)", 1, 30, step=1, key="of_sc_anni")
        s3.number_input("Detrazione %", 0, 100, step=1, key="of_sc_det")
        x = of.simulazione(ctx["opzioni"][ss["of_sc_opz"]]["qte"]["totale"],
                           ctx["opzioni"][ss["of_sc_opz"]]["qte"]["lavori_iva"] + (ctx["opzioni"][ss["of_sc_opz"]]["qte"]["spese"] if ss["of_base_spese"] else 0),
                           [ss["of_sc_anni"]], ss["of_tan"] / 100, [ss["of_sc_det"]], int(ss["of_anni"]), ss["of_risp"])[0]
        det = int(ss["of_sc_det"])
        ris_m = ss["of_risp"] / 12
        rec_m = x["rata"] - x[f"impatto{det}"] - ris_m
        tabv = pd.DataFrame([{"Unità": u["Unita"], "Proprietario": u["Proprietario"], "Millesimi": u["Millesimi"], "Quota capitale": u["Millesimi"] / 1000 * ctx["opzioni"][ss["of_sc_opz"]]["qte"]["totale"],
                              "Rata/mese": x["rata"] * u["Millesimi"] / 1000, "Recupero fiscale/mese": rec_m * u["Millesimi"] / 1000, "Risparmio energ./mese": ris_m * u["Millesimi"] / 1000,
                              "IMPATTO REALE/mese": x[f"impatto{det}"] * u["Millesimi"] / 1000} for u in un])
        st.dataframe(tabv.style.format({c: "{:,.2f}" for c in tabv.columns[3:]} | {"Millesimi": "{:.3f}"}), hide_index=True, width="stretch", height=300)
        buf = io.BytesIO()
        tabv.to_excel(buf, index=False, sheet_name="Ripartizione")
        st.download_button("📥 Scarica la ripartizione in Excel", buf.getvalue(), file_name="ripartizione_millesimi.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="of_dl_rip")


def _scheda_mercato(ctx):
    st.markdown("Inserisci gli **annunci** raccolti dai siti delle agenzie della zona (uno per riga): l'app calcola i €/m² medi di una casa «così com'è» e di una «efficientata».")
    tabella_modificabile("of_annunci", ss["of_annunci"], {"Fonte": st.column_config.TextColumn("Fonte/agenzia"), "Zona": st.column_config.TextColumn("Zona"),
                                                         "Stato": st.column_config.SelectboxColumn("Stato", options=of.STATI_IMM, required=True), "Mq": st.column_config.NumberColumn("m²", min_value=0.0),
                                                         "Prezzo": st.column_config.NumberColumn("Prezzo €", min_value=0.0, format="%.0f"), "Link": st.column_config.LinkColumn("Link")}, altezza=260)
    a, b, c = st.columns(3)
    a.number_input("€/m² così com'è (se non hai annunci)", 0.0, step=50.0, key="of_m_ante")
    b.number_input("€/m² efficientato (se non hai annunci)", 0.0, step=50.0, key="of_m_post")
    c.number_input("Esempio su un appartamento di m²", 10, 400, step=10, key="of_mq")
    m = ctx["mercato"]
    if m["ante"] and m["post"]:
        st.markdown(theme.stat_strip([
            {"label": "Così com'è", "value": f"{m['ante']:,.0f} €/m²".replace(",", "."), "sub": f"{m['n'][COSI_COM_E]} annunci" if m["da_annunci"] else "valore indicato", "tono": "warn"},
            {"label": "Efficientato", "value": f"{m['post']:,.0f} €/m²".replace(",", "."), "sub": f"{m['n']['Efficientato']} annunci" if m["da_annunci"] else "valore indicato", "tono": "ok"},
            {"label": "Differenza", "value": f"{m['delta']:,.0f} €/m²".replace(",", "."), "sub": f"{m['delta'] / m['ante'] * 100:.1f}%", "tono": "info"},
            {"label": f"Su {ss['of_mq']} m²", "value": _euro(m["delta"] * ss["of_mq"]), "sub": "valore potenziale", "tono": "info"}]), unsafe_allow_html=True)
    else:
        st.info("Servono almeno un annuncio «così com'è» e uno «efficientato», oppure i due valori a mano.")
    st.caption("Il confronto è una stima basata su annunci pubblici, non una perizia: nell'offerta è indicato così.")


def _scheda_fin_rich(ctx):
    st.markdown("Tieni mappate le **richieste di finanziamento**: una al **Condominio** (parti comuni, sul codice fiscale del condominio) e una per ogni **condomino** (fino al 50% dei lavori privati, AGOS).")
    ss["of_ric"] = ss["of_ric"]
    if not sola_lettura():
        c1, c2 = st.columns([2, 3])
        if c1.button("➕ Crea una riga per ogni unità (condomini)", key="of_ric_gen", help="Una richiesta «Da preparare» per ogni unità della tabella millesimale, con AGOS come istituto."):
            att = _rec("of_ric")
            gia = {r.get("Unita") for r in att if r.get("Tipo") == "Condomino"}
            for u in ctx["unita"]:
                if u["Unita"] not in gia:
                    att.append({"Tipo": "Condomino", "Unita": u["Unita"], "Richiedente": u["Proprietario"], "Istituto": "AGOS", "Stato": "Da preparare"})
            sostituisci_tabella("of_ric", _df("of_ric", att))
            st.rerun()
    cov = ctx["copertura"]
    if cov["totale"]:
        st.markdown(theme.stat_strip([
            {"label": "Totale appalto", "value": _euro(cov["totale"]), "sub": "totale progetto", "tono": "info"},
            {"label": "Coperto (approvato/erogato)", "value": _euro(cov["approvato"]), "sub": f"{cov['pct_approvato']:.1f}%", "tono": "ok" if cov["pct_approvato"] >= 100 else "warn"},
            {"label": "In istruttoria", "value": _euro(cov["in_corso"]), "sub": f"potenziale {cov['pct_potenziale']:.1f}%", "tono": "info"},
            {"label": "Scoperto", "value": _euro(cov["scoperto"]), "sub": f"rifiutato {_euro(cov['rifiutato'])}", "tono": "bad" if cov["scoperto"] > 0 and cov["pct_potenziale"] < 100 else "ok"}]), unsafe_allow_html=True)
        tp = cov["tipi"]
        st.dataframe(pd.DataFrame([{"Tipo": t, "Richieste": v["n"], "Approvate": v["n_approvate"], "In corso": v["n_in_corso"], "Rifiutate/ritirate": v["n_rifiutate"],
                                    "Approvato €": _euro(v["approvato"]), "In corso €": _euro(v["in_corso"]), "Rifiutato €": _euro(v["rifiutato"])} for t, v in tp.items()]), hide_index=True, width="stretch")
    for a in cov["avvisi"]:
        st.warning(a)
    tabella_modificabile("of_ric", ss["of_ric"], {"Tipo": st.column_config.SelectboxColumn("Tipo", options=of.TIPI_FIN, required=True), "Unita": st.column_config.TextColumn("Unità"),
                                                 "Richiedente": st.column_config.TextColumn("Richiedente", width="medium"), "Istituto": st.column_config.TextColumn("Istituto", help="AGOS per i condomini"),
                                                 "Lavori": st.column_config.NumberColumn("Lavori privati €", format="%.0f", help="Valore dei lavori sulle parti private (per il limite del 50%)"),
                                                 "Richiesto": st.column_config.NumberColumn("Richiesto €", format="%.0f"), "Stato": st.column_config.SelectboxColumn("Stato", options=of.STATI_FIN, required=True),
                                                 "Deliberato": st.column_config.NumberColumn("Deliberato €", format="%.0f"), "Data richiesta": st.column_config.TextColumn("Data richiesta", help="GG/MM/AAAA"),
                                                 "Data esito": st.column_config.TextColumn("Data esito"), "Esito": st.column_config.TextColumn("Esito / motivo", width="medium"),
                                                 "Documenti": st.column_config.TextColumn("Documenti (consegnati / mancanti)", width="large"), "Note": st.column_config.TextColumn("Note", width="medium")}, altezza=380)
    st.caption("Stati: " + " → ".join(of.STATI_FIN[:6]) + " (o Rifiutata / Ritirata). Per i condomini il limite è il 50% dei lavori privati: l'app avvisa se la richiesta lo supera.")
    with st.expander("🌐 Tutte le richieste di tutte le pratiche salvate"):
        try:
            import storage
            rows = []
            for pr in storage.elenca_pratiche(modulo="of"):
                dati = storage.carica_pratica(pr["nome"], modulo="of") or {}
                for r in of.normalizza_fin(dati.get("richieste")):
                    rows.append({"Pratica": pr["nome"], **{k: r[k] for k in ("Tipo", "Unita", "Richiedente", "Istituto", "Richiesto", "Stato", "Deliberato", "Data esito", "Esito")}})
            if rows:
                dfa = pd.DataFrame(rows)
                stt = st.multiselect("Stato", of.STATI_FIN, key="of_ric_f", placeholder="Tutti")
                st.dataframe(dfa[dfa["Stato"].isin(stt)] if stt else dfa, hide_index=True, width="stretch", height=300)
            else:
                st.caption("Nessuna richiesta salvata nelle altre pratiche.")
        except Exception as e:
            st.caption(f"Elenco non disponibile ({e}).")


def _excel(ctx):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for h, o in ctx["opzioni"].items():
            q = o["qte"]
            pd.DataFrame([["Lavori imponibili", q["imponibile"]], ["IVA lavori", q["iva_lavori"]], ["Totale lavori con IVA", q["lavori_iva"]], ["Parcella lorda", q["parcella"]["lorda"]],
                          ["Totale parcella (cassa e IVA)", q["parcella"]["totale"]], ["Responsabile Lavori lordo", q["rl"]["lorda"]], ["Totale Responsabile Lavori", q["rl"]["totale"]],
                          ["Totale spese professionali", q["spese"]], ["TOTALE PROGETTO", q["totale"]]], columns=["Voce", "Importo"]).to_excel(w, index=False, sheet_name=f"QTE {h}")
            rr = []
            for x in ctx["sim"][h]:
                rr.append({"Durata anni": x["anni"], "Rata mensile": x["rata"], "Interessi": x["interessi"], "Totale": x["totale"]} | {f"Impatto mensile {int(d)}%": x[f"impatto{int(d)}"] for d in ctx["params"]["detrazioni"]})
            pd.DataFrame(rr).to_excel(w, index=False, sheet_name=f"Finanziamento {h}")
        ss["of_voci"].to_excel(w, index=False, sheet_name="Computo")
        if ctx["unita"]:
            pd.DataFrame(ctx["unita"]).to_excel(w, index=False, sheet_name="Millesimi")
    return buf.getvalue()


def _scheda_offerta(ctx, audit):
    import of_report
    st.markdown("Genera l'offerta nello stile FCR: copertina, riservatezza, presentazione, sintesi, opzioni, quadro economico, finanziamento a più durate, recupero fiscale, impatto per millesimo, ripartizione per unità, mercato, continuità finanziaria e percorso decisionale.")
    if not ctx["opzioni"]:
        st.info("Mancano i lavori: importa il computo.")
        return
    mancanze = []
    if not ctx["pratica"].get("condominio"):
        mancanze.append("il nome del condominio")
    if not ctx["unita"]:
        mancanze.append("la tabella millesimale (la ripartizione per unità sarà omessa)")
    if not ctx["mercato"]["ante"]:
        mancanze.append("il confronto di mercato (sarà omesso)")
    if not ctx["params"]["risparmio_annuo"]:
        mancanze.append("il risparmio energetico (le simulazioni useranno solo il recupero fiscale)")
    if mancanze:
        st.info("Non ancora inserito: " + "; ".join(mancanze) + ".")
    if st.button("🚀 Genera l'offerta (PPTX + PDF)", type="primary", key="of_gen"):
        with st.spinner("Preparo le diapositive…"):
            sl = of_report.costruisci({**ctx, "pratica": {**ctx["pratica"], "sintesi_sotto": ""}})
            ss["rep_of"] = {"pptx": of_report.pptx_bytes(sl), "pdf": of_report.pdf_bytes(sl), "xlsx": _excel(ctx), "n": len(sl), "nome": (ctx["pratica"].get("cod") or "offerta").replace(" ", "_")}
        audit("of_offerta", ctx["pratica"].get("cod") or "")
    out = ss.get("rep_of")
    if out:
        st.success(f"Offerta pronta: {out['n']} diapositive.")
        c1, c2, c3 = st.columns(3)
        c1.download_button("📊 Scarica PowerPoint", out["pptx"], file_name=f"FCR_Offerta_{out['nome']}.pptx", mime="application/vnd.openxmlformats-officedocument.presentationml.presentation", key="of_dl_pptx")
        c2.download_button("📄 Scarica PDF", out["pdf"], file_name=f"FCR_Offerta_{out['nome']}.pdf", mime="application/pdf", key="of_dl_pdf")
        c3.download_button("📥 Scarica i calcoli in Excel", out["xlsx"], file_name=f"FCR_Calcoli_{out['nome']}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="of_dl_xlsx")
        st.caption("Rigenera l'offerta dopo ogni modifica ai dati: il file scaricato non si aggiorna da solo.")


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Offerta e finanziamenti", "Dal computo all'offerta: parcelle, quadro economico, finanziamento per millesimi e richieste di finanziamento di Condominio e condomini."), unsafe_allow_html=True)
    guida.mostra("of")
    _init()
    pannello_archivio("of", "l'offerta", _raccogli, _applica, audit, utente)
    ctx = of.contesto(_raccogli())
    t = st.tabs(["🏢 1. Pratica", "📐 2. Computo", "🧮 3. Parcelle", "📋 4. QTE", "💶 5. Finanziamento e millesimi", "🏠 6. Mercato", "🏦 7. Continuità finanziaria", "📄 8. Offerta"])
    with t[0]:
        _scheda_pratica()
    with t[1]:
        _scheda_computo(ctx)
    with t[2]:
        _scheda_parcelle(ctx)
    with t[3]:
        _scheda_qte(ctx)
    with t[4]:
        _scheda_fin(ctx)
    with t[5]:
        _scheda_mercato(ctx)
    with t[6]:
        _scheda_fin_rich(ctx)
    with t[7]:
        _scheda_offerta(ctx, audit)
