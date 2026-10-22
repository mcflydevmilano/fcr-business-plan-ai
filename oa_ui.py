"""oa_ui.py - Interfaccia di Ordini e approvazioni."""
import datetime as dt

import pandas as pd
import streamlit as st

import fo
import guida
import oa
import ops_report
import theme
from core import fmt_num
from ui_util import esempi_attivi, senza_esempi, banner_esempio, blocco_tabella, pannello_archivio, scarica_dossier, sola_lettura, sostituisci_tabella

ss = st.session_state
ICONE = {"Da approvare": "🟡", "Da riapprovare": "🟠", "Approvato": "🟢", "Respinto": "🔴"}


def _ord_df(righe):
    """Tabella degli ordini; le colonne nuove (Voce) mancanti nei salvataggi vecchi diventano testo vuoto, non numeri."""
    df = pd.DataFrame(righe or [], columns=oa.COLONNE_ORDINI)
    df["Voce"] = df["Voce"].astype(object).where(df["Voce"].notna(), "")
    return df


@senza_esempi
def _esempio():
    g = lambda n: (dt.date.today() + dt.timedelta(days=n)).isoformat()
    anno = dt.date.today().year
    ordini = [(f"ODA-{anno}-001", g(-12), "Calcestruzzi Alfa", "Villa Lago", "Calcestruzzo fondazioni", 8400, "capocantiere", ""),
              (f"ODA-{anno}-002", g(-3), "Elettroimpianti Beta", "Scuola Elementare", "Quadri elettrici piano terra", 24500, "capocantiere", ""),
              (f"ODA-{anno}-003", g(-1), "Ponteggi Gamma", "Villa Lago", "Noleggio ponteggi, 4 settimane", 1800, "capocantiere", "")]
    mk = lambda cols, rows: _ord_df([dict(zip(cols, r)) for r in rows])
    return mk(oa.COLONNE_ORDINI, ordini), pd.DataFrame(oa.SOGLIE_BASE, columns=oa.COLONNE_SOGLIE)


def _cfg():
    n, t = st.column_config.NumberColumn, st.column_config.TextColumn
    a, b = oa.ETICHETTE_ORDINI, oa.ETICHETTE_SOGLIE
    return ({"Numero": t(a["Numero"], help="Lascialo vuoto: lo assegna l'app."), "Data": t(a["Data"]), "Fornitore": t(a["Fornitore"]), "Cantiere": t(a["Cantiere"]), "Descrizione": t(a["Descrizione"], width="large"),
             "Importo": n(a["Importo"], min_value=0.0, step=100.0, format="%.0f"), "Richiedente": t(a["Richiedente"], help="Il nome utente di chi chiede l'ordine."), "Note": t(a["Note"]),
             "Voce": t(a["Voce"], help="Facoltativo: il codice della voce nel Prezziario (es. B.06.04.0025.b). Con la quantità, l'app controlla se il prezzo unitario supera quello di riferimento."),
             "Quantita": n(a["Quantita"], min_value=0.0, step=1.0, format="%.2f", help="Quantità ordinata, nell'unità del prezziario.")},
            {"Fino_a": n(b["Fino_a"], min_value=0.0, step=500.0, format="%.0f"), "Livello": t(b["Livello"]), "Approvatori": t(b["Approvatori"], width="large", help="Vuoto = può approvare chiunque non sia il richiedente.")})


def _raccogli():
    return {"ordini": ss["oa_ord"].to_dict("records"), "soglie": ss["oa_sog"].to_dict("records"), "approvazioni": ss.get("oa_appr", []), "soglia_prezzario": ss.get("oa_soglia_pz", 10.0)}


def _applica(p, nome):
    sostituisci_tabella("oa_ord", _ord_df(p.get("ordini")))
    sostituisci_tabella("oa_sog", pd.DataFrame(p.get("soglie") or oa.SOGLIE_BASE, columns=oa.COLONNE_SOGLIE))
    ss["oa_appr"] = list(p.get("approvazioni") or [])
    ss["_pending"] = {"oa_soglia_pz": float(p.get("soglia_prezzario", 10.0))}
    ss["oa_demo"] = False


def _docs_fornitori():
    try:
        import ca_ui
        pay, _ = ca_ui._payloads(True)
    except Exception:
        pay = {}
    return fo.normalizza_docfo((pay.get("fo") or {}).get("docs"))[0] if pay.get("fo") else []


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Ordini e approvazioni", "Chi chiede, chi approva, fino a quanto: ogni ordine ha il suo via libera e resta tutto tracciato."), unsafe_allow_html=True)
    guida.mostra("oa")
    if "oa_ord" not in ss:
        ss["oa_ord"], ss["oa_sog"] = _esempio()
        ss["oa_demo"] = esempi_attivi()
    ss.setdefault("oa_appr", [])
    pannello_archivio("oa", "gli ordini", _raccogli, _applica, audit, utente)
    t1, t2, t3, t4 = st.tabs(["🧾 1. Ordini e regole", "✅ 2. Da approvare", "🔎 3. Controllo", "📄 4. Dossier"])
    co, cs = _cfg()
    me = ss.get("utente") or {}
    nome_u, ruolo_u = me.get("username", utente), me.get("ruolo", "utente")
    with t1:
        banner_esempio("oa_demo", [("oa_ord", oa.COLONNE_ORDINI), ("oa_sog", oa.COLONNE_SOGLIE)], "svuota_oa")
        blocco_tabella("oa_ord", "Ordini di acquisto", "Una riga per ordine. Se cambi l'importo di un ordine già approvato, torna da riapprovare.", oa.COLONNE_ORDINI, oa.ETICHETTE_ORDINI, co, ss["oa_ord"], "oa", 1, audit, 260)
        if st.button("🔢 Assegna i numeri mancanti", key="numeri_oa", disabled=sola_lettura()):
            nuovi, _ = oa.normalizza_ordini(ss["oa_ord"].to_dict("records"))
            sostituisci_tabella("oa_ord", _ord_df(nuovi))
            audit("oa_numeri_assegnati", f"{len(nuovi)} ordini")
            st.rerun()
        ss.setdefault("oa_soglia_pz", 10.0)
        st.number_input("Avviso se il prezzo unitario supera il prezziario di più del… (%)", min_value=0.0, max_value=100.0, step=1.0, key="oa_soglia_pz",
                        help="Vale per gli ordini con «Voce» e «Quantità» compilate. L'avviso non blocca l'approvazione: la persona che decide lo vede.")
        blocco_tabella("oa_sog", "Chi approva cosa", "Per ogni fascia d'importo: il ruolo e, se vuoi, i nomi utente autorizzati. L'ultima riga (senza limite) vale per gli importi più alti.",
                       oa.COLONNE_SOGLIE, oa.ETICHETTE_SOGLIE, cs, ss["oa_sog"], "oa", 2, audit, 160)
    with t1:
        try:
            import pe
            _p = [p for p in (pe.normalizza_persone(ss["pe_pers"].to_dict("records"))[0] if ("pe_pers" in ss and not ss.get("pe_demo")) else pe.persone_salvate()) if p["Utente"]]
        except Exception:
            _p = []
        if _p:
            with st.expander("👥 Persone con account (nomi utente da usare qui)"):
                st.dataframe(pd.DataFrame([{"Nome utente": p["Utente"], "Persona": p["Persona"], "Ruolo": p["Ruolo"]} for p in _p]), hide_index=True, width="stretch")
    grezzi = ss["oa_ord"].to_dict("records")
    ordini, av = oa.normalizza_ordini(grezzi)
    soglie = oa.normalizza_soglie(ss["oa_sog"].to_dict("records"))
    docs_fo = _docs_fornitori()
    try:
        import pz_ui
        _prezzi = pz_ui.prezzi_attivi()
    except Exception:
        _prezzi = {}
    out = oa.calcola_oa(ordini, soglie, ss["oa_appr"], docs_fo, prezzi=_prezzi, soglia_prezzo=float(ss.get("oa_soglia_pz", 10.0)))
    k = out["kpi"]
    senza_numero = any(not str(r.get("Numero") or "").strip() for r in grezzi if str(r.get("Fornitore") or "").strip())

    with t2:
        for x in av[:3]:
            st.caption("⚠️ " + x)
        if senza_numero:
            st.warning("Alcuni ordini non hanno ancora il numero: premi «Assegna i numeri mancanti» nella scheda 1, poi potrai approvarli.")
        da_app = [r for r in out["ordini"] if r["Stato"] in ("Da approvare", "Da riapprovare")]
        if not da_app:
            st.success("Nessun ordine in attesa di approvazione.")
        else:
            st.dataframe(pd.DataFrame([{"": ICONE[r["Stato"]], "N.": r["Numero"], "Fornitore": r["Fornitore"], "Cantiere": r["Cantiere"], "Cosa": r["Descrizione"], "Importo €": r["Importo"],
                                        "Chi approva": r["Livello"], "Richiesto da": r["Richiedente"], "Attesa gg": r["Attesa gg"], "Stato": r["Stato"]} for r in da_app]), hide_index=True, width="stretch")
            sel = st.selectbox("Ordine da decidere", [r["Numero"] for r in da_app], format_func=lambda n: next(f"{r['Numero']} · {r['Fornitore']} · {fmt_num(r['Importo'])} €" for r in da_app if r["Numero"] == n), key="oa_sel")
            o = next(r for r in da_app if r["Numero"] == sel)
            ok, motivo = oa.puo_approvare(nome_u, ruolo_u, o, soglie, out["irregolari"])
            if senza_numero:
                ok, motivo = False, "Assegna prima i numeri degli ordini."
            st.markdown(f"**{o['Descrizione'] or o['Fornitore']}** — {fmt_num(o['Importo'])} € per {o['Cantiere'] or 'cantiere non indicato'}. Serve il via libera di **{o['Livello']}**.")
            if o["Anomalie"]:
                st.warning("Attenzione: " + "; ".join(o["Anomalie"]) + ".")
            if not ok:
                st.info("🔒 " + motivo)
            mot = st.text_input("Motivo (obbligatorio per respingere)", key="oa_motivo")
            c1, c2 = st.columns(2)
            adesso = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
            if c1.button("✅ Approva", key="ok_oa", type="primary", disabled=not ok or sola_lettura(), width="stretch"):
                ss["oa_appr"] = oa.registra(ss["oa_appr"], o, "Approvato", nome_u, adesso, mot)
                audit("oa_approvato", f"{o['Numero']} · {o['Fornitore']} · {fmt_num(o['Importo'])} € · da {nome_u}")
                st.rerun()
            if c2.button("⛔ Respingi", key="no_oa", disabled=not ok or sola_lettura() or not mot.strip(), width="stretch"):
                ss["oa_appr"] = oa.registra(ss["oa_appr"], o, "Respinto", nome_u, adesso, mot)
                audit("oa_respinto", f"{o['Numero']} · {o['Fornitore']} · {fmt_num(o['Importo'])} € · da {nome_u}: {mot}")
                st.rerun()
            st.caption("Ricordati di salvare dopo le decisioni: il salvataggio conserva anche chi ha approvato e quando.")

    with t3:
        if not ordini:
            st.info("Inserisci almeno un ordine.")
        else:
            st.markdown(theme.stat_strip([
                {"label": "Da approvare", "value": str(k["da_approvare"]), "sub": f"{fmt_num(k['importo_da_approvare'])} €", "tono": "warn" if k["da_approvare"] else "ok"},
                {"label": "Approvati", "value": str(k["approvati"]), "sub": f"{fmt_num(k['importo_approvato'])} €", "tono": "ok"},
                {"label": "Respinti", "value": str(k["respinti"]), "sub": "", "tono": "info"},
                {"label": "Anomalie", "value": str(k["anomalie"]), "sub": f"{k['in_ritardo']} in attesa da troppo", "tono": "bad" if k["anomalie"] else "ok"}]), unsafe_allow_html=True)
            for a in out["avvisi"][:8]:
                st.warning(a)
            st.dataframe(pd.DataFrame([{"": ICONE[r["Stato"]], "N.": r["Numero"], "Data": r["Data"], "Fornitore": r["Fornitore"], "Cantiere": r["Cantiere"], "Importo €": r["Importo"], "Stato": r["Stato"],
                                        "Deciso da": (r["Decisione"] or {}).get("Da", ""), "Quando": (r["Decisione"] or {}).get("Quando", ""), "Anomalie": "; ".join(r["Anomalie"])} for r in out["ordini"]]), hide_index=True, width="stretch")
            if ss["oa_appr"]:
                with st.expander("Storico di tutte le decisioni"):
                    st.dataframe(pd.DataFrame(ss["oa_appr"]), hide_index=True, width="stretch")

    with t4:
        if not ordini:
            st.info("Aggiungi degli ordini per generare il dossier.")
        else:
            def _gen(nome):
                return ops_report.report_generico(
                    "Ordini e approvazioni", "Registro degli ordini", nome, dt.date.today(), [("ORDINI", str(k["ordini"])), ("DA APPROVARE", str(k["da_approvare"]))],
                    [("Da approvare", str(k["da_approvare"]), fmt_num(k["importo_da_approvare"]) + " €", "warn" if k["da_approvare"] else "ok"), ("Approvati", str(k["approvati"]), fmt_num(k["importo_approvato"]) + " €", "ok"),
                     ("Respinti", str(k["respinti"]), "", "info"), ("Anomalie", str(k["anomalie"]), "da controllare", "bad" if k["anomalie"] else "ok")],
                    ops_report._esito(k["anomalie"], k["da_approvare"], max(1, k["ordini"]), "ordini"),
                    [{"titolo": "Registro degli ordini", "tabella": (["N.", "Fornitore", "Cantiere", "Importo", "Stato", "Deciso da", "Quando"],
                                                                      [(r["Numero"], r["Fornitore"][:20], r["Cantiere"][:16], ops_report.N(r["Importo"]), r["Stato"], (r["Decisione"] or {}).get("Da", "")[:14], (r["Decisione"] or {}).get("Quando", "")) for r in out["ordini"]])},
                     {"titolo": "Punti di attenzione", "testo": ["- " + a for a in (out["avvisi"] or ["Nessuna anomalia rilevata."])]},
                     {"titolo": "Metodo e limiti", "testo": ["Ogni ordine segue la fascia d'importo della tabella «Chi approva cosa». Chi chiede un ordine non può approvarlo; un fornitore con documenti scaduti blocca l'approvazione; "
                                                          "se l'importo cambia dopo l'approvazione, l'ordine torna da riapprovare."]}],
                    [{"nome": "Ordini", "intest": ["Numero", "Data", "Fornitore", "Cantiere", "Descrizione", "Importo", "Richiedente", "Stato", "Deciso da", "Quando"],
                      "righe": [[r["Numero"], r["Data"], r["Fornitore"], r["Cantiere"], r["Descrizione"], r["Importo"], r["Richiedente"], r["Stato"], (r["Decisione"] or {}).get("Da", ""), (r["Decisione"] or {}).get("Quando", "")] for r in out["ordini"]], "totali": [5]},
                     {"nome": "Decisioni", "intest": ["Numero", "Esito", "Da", "Quando", "Importo", "Motivo"], "righe": [[a["Numero"], a["Esito"], a["Da"], a["Quando"], a["Importo"], a["Motivo"]] for a in ss["oa_appr"]]}], [k["ordini"], k["approvati"]])
            scarica_dossier("oa", _gen, "Ordini", audit, "Ordini e approvazioni")
