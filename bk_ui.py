"""bk_ui.py - Interfaccia della Riconciliazione bancaria."""
import datetime as dt

import pandas as pd
import streamlit as st

import bk
import guida
import ops_report
import sc
import theme
from core import fmt_num
from ui_util import banner_esempio, blocco_tabella, pannello_archivio, scarica_dossier, sola_lettura, sostituisci_tabella

ss = st.session_state


def _esempio():
    g = lambda n: (dt.date.today() + dt.timedelta(days=n)).isoformat()
    mov = [(g(-3), "BONIFICO DA COMUNE DI ESEMPIO SAL 2 FATT 14/2026", 42500.00), (g(-2), "BONIFICO A CALCESTRUZZI ALFA SRL FATT 311", -9800.00), (g(-2), "COMMISSIONI E SPESE TENUTA CONTO", -18.50),
           (g(-1), "BONIFICO A PONTEGGI GAMMA SALDO PARZIALE", -4000.00), (g(-1), "ADDEBITO CARBURANTE FLOTTA", -612.40)]
    return pd.DataFrame([dict(zip(bk.COLONNE_MOV, r)) for r in mov], columns=bk.COLONNE_MOV)


def _docs_sc():
    """Fatture dello Scadenzario: sessione o ultimo salvataggio."""
    try:
        import ca_ui
        pay, _ = ca_ui._payloads(True)
    except Exception:
        pay = {}
    if pay.get("sc"):
        return sc.normalizza_documenti(pay["sc"].get("docs"))[0]
    return []


def _raccogli():
    return {"movimenti": ss["bk_mov"].to_dict("records")}


def _applica(p, nome):
    sostituisci_tabella("bk_mov", pd.DataFrame(p.get("movimenti") or [], columns=bk.COLONNE_MOV))
    ss["bk_demo"] = False


def _aggiorna_scadenzario(docs, conferma):
    """Scrive i pagamenti confermati nella tabella dello Scadenzario aperta in sessione. Restituisce quanti documenti ha aggiornato."""
    if "sc_df" not in ss:
        return 0
    df = ss["sc_df"].copy()
    n = 0
    for a in conferma:
        d = docs[a["d"]]
        for ix in df.index:
            r = df.loc[ix]
            if str(r.get("Controparte") or "").strip() == d["Controparte"] and str(r.get("Documento") or "").strip() == d["Documento"] and abs(float(r.get("Importo") or 0) - d["Importo"]) < 0.01:
                df.at[ix, "Saldato"] = a["Saldato dopo"]
                n += 1
                break
    sostituisci_tabella("sc_df", df)
    return n


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Riconciliazione bancaria", "Abbina i movimenti del conto alle fatture e segna da solo cosa è stato pagato o incassato."), unsafe_allow_html=True)
    guida.mostra("bk")
    if "bk_mov" not in ss:
        ss["bk_mov"] = _esempio()
        ss["bk_demo"] = True
    pannello_archivio("bk", "i movimenti", _raccogli, _applica, audit, utente)
    t1, t2, t3 = st.tabs(["🏦 1. Movimenti", "🔗 2. Abbinamenti", "📄 3. Dossier"])
    t = st.column_config
    with t1:
        banner_esempio("bk_demo", [("bk_mov", bk.COLONNE_MOV)], "svuota_bk")
        blocco_tabella("bk_mov", "Movimenti del conto corrente", "Incolla o importa l'estratto conto (Excel/CSV della banca): entrate con +, uscite con −.", bk.COLONNE_MOV, bk.ETICHETTE_MOV,
                       {"Data": t.TextColumn(bk.ETICHETTE_MOV["Data"]), "Descrizione": t.TextColumn(bk.ETICHETTE_MOV["Descrizione"], width="large"), "Importo": t.NumberColumn(bk.ETICHETTE_MOV["Importo"], format="%.2f")},
                       ss["bk_mov"], "bk", 1, audit, 300, bk.SINONIMI_MOV)
    mov, av = bk.normalizza_movimenti(ss["bk_mov"].to_dict("records"))
    docs = _docs_sc()
    out = bk.calcola_bk(mov, docs)
    k = out["kpi"]

    with t2:
        if not docs:
            st.info("Servono le fatture dello **Scadenzario**: aprilo e inserisci i documenti (o salvali) e torna qui.")
        if not mov:
            st.warning("Nessun movimento valido.")
        else:
            for x in av[:3]:
                st.caption("⚠️ " + x)
            st.markdown(theme.stat_strip([
                {"label": "Abbinamenti sicuri", "value": str(k["sicuri"]), "sub": "importo e riferimento coincidono", "tono": "ok"},
                {"label": "Da verificare", "value": str(k["da_verificare"]), "sub": "controlla a mano", "tono": "warn" if k["da_verificare"] else "ok"},
                {"label": "Senza fattura", "value": str(k["senza_fattura"]), "sub": f"{fmt_num(k['importo_senza'])} €", "tono": "info"},
                {"label": "Riconciliato", "value": fmt_num(k["importo_riconciliato"]) + " €", "sub": f"su {k['movimenti']} movimenti", "tono": "info"}]), unsafe_allow_html=True)
            ab = out["abbinamenti"]
            if ab:
                st.markdown("**Abbinamenti proposti** — spunta quelli corretti")
                righe = [{"Conferma": a["Esito"] == "sicuro", "Esito": ("🟢 sicuro" if a["Esito"] == "sicuro" else "🟡 da verificare"), "Data": a["Movimento"]["Data"], "Movimento": a["Movimento"]["Descrizione"][:48],
                          "Importo €": a["Movimento"]["Importo"], "Fattura": f"{a['Fattura']['Controparte']} · {a['Fattura']['Documento'] or 'n.d.'}", "Residuo €": a["Fattura"]["Importo"] - a["Fattura"]["Saldato"],
                          "Chiude": "sì" if a["Chiude"] else "parziale", "Perché": "; ".join(a["Motivi"])} for a in ab]
                ed = st.data_editor(pd.DataFrame(righe), hide_index=True, width="stretch", key=f"bk_conf_{len(ab)}_{k['importo_riconciliato']:.0f}", disabled=[c for c in righe[0] if c != "Conferma"] if not sola_lettura() else True)
                scelti = [a for a, c in zip(ab, ed["Conferma"].tolist()) if c]
                if st.button(f"✅ Segna {len(scelti)} fatture come pagate/incassate nello Scadenzario", key="bk_applica", type="primary", disabled=sola_lettura() or not scelti):
                    n = _aggiorna_scadenzario(docs, scelti)
                    audit("bk_riconciliati", f"{len(scelti)} abbinamenti confermati, {n} righe aggiornate nello Scadenzario")
                    if n:
                        st.success(f"Aggiornate {n} fatture nello Scadenzario aperto. Ricordati di salvare lo Scadenzario.")
                    else:
                        st.warning("Lo Scadenzario non è aperto in questa sessione (o le fatture vengono da un salvataggio): apri lo Scadenzario dal salvataggio, poi riprova. Qui sotto trovi l'elenco da riportare a mano.")
                    ss["bk_ultimi"] = [{"Fattura": f"{a['Fattura']['Controparte']} {a['Fattura']['Documento']}", "Saldato": a["Saldato dopo"]} for a in scelti]
                if ss.get("bk_ultimi"):
                    st.dataframe(pd.DataFrame(ss["bk_ultimi"]), hide_index=True, width="stretch")
            else:
                st.success("Nessun abbinamento da proporre.") if docs else None
            if out["senza_fattura"]:
                st.markdown("**Movimenti senza fattura**")
                st.dataframe(pd.DataFrame(out["senza_fattura"]), hide_index=True, width="stretch")
            if out["fatture_aperte"]:
                with st.expander(f"Fatture ancora aperte ({len(out['fatture_aperte'])})"):
                    st.dataframe(pd.DataFrame([{"Tipo": d["Tipo"], "Controparte": d["Controparte"], "Documento": d["Documento"], "Scadenza": d["Scadenza"], "Residuo €": d["Importo"] - d["Saldato"]}
                                               for d in out["fatture_aperte"]]), hide_index=True, width="stretch")
            for a in out["avvisi"]:
                st.caption("ℹ️ " + a)

    with t3:
        if not mov:
            st.info("Aggiungi dei movimenti per generare il dossier.")
        else:
            def _gen(nome):
                return ops_report.report_generico(
                    "Riconciliazione bancaria", "Movimenti e fatture", nome, dt.date.today(), [("MOVIMENTI", str(k["movimenti"])), ("ABBINATI", str(k["abbinati"]))],
                    [("Entrate", fmt_num(k["entrate"]) + " €", "sul conto", "ok"), ("Uscite", fmt_num(k["uscite"]) + " €", "dal conto", "info"), ("Abbinati", str(k["abbinati"]), f"{k['da_verificare']} da verificare", "warn" if k["da_verificare"] else "ok"),
                     ("Senza fattura", str(k["senza_fattura"]), fmt_num(k["importo_senza"]) + " €", "warn" if k["senza_fattura"] else "ok")],
                    ("DA CONTROLLARE" if k["senza_fattura"] or k["da_verificare"] else "TUTTO RICONCILIATO", "warn" if k["senza_fattura"] or k["da_verificare"] else "ok", f"{k['abbinati']} abbinati su {k['movimenti']} movimenti"),
                    [{"titolo": "Abbinamenti", "tabella": (["Data", "Movimento", "Importo", "Fattura", "Esito"], [(ops_report.fd(a["Movimento"]["Data"]), a["Movimento"]["Descrizione"][:30], ops_report.N(a["Movimento"]["Importo"], 2),
                                                                                                          (a["Fattura"]["Controparte"][:16] + " " + a["Fattura"]["Documento"])[:26], a["Esito"]) for a in out["abbinamenti"]])},
                     {"titolo": "Movimenti senza fattura", "tabella": (["Data", "Descrizione", "Importo"], [(ops_report.fd(m["Data"]), m["Descrizione"][:50], ops_report.N(m["Importo"], 2)) for m in out["senza_fattura"]])},
                     {"titolo": "Metodo e limiti", "testo": ["Gli abbinamenti sono proposte: importo uguale al residuo, numero fattura o nome nella causale, vicinanza alla scadenza. Vanno confermati da una persona. Non sostituisce la contabilità."]}],
                    [{"nome": "Abbinamenti", "intest": ["Data", "Movimento", "Importo", "Controparte", "Documento", "Esito", "Punteggio"],
                      "righe": [[a["Movimento"]["Data"], a["Movimento"]["Descrizione"], a["Movimento"]["Importo"], a["Fattura"]["Controparte"], a["Fattura"]["Documento"], a["Esito"], a["Punteggio"]] for a in out["abbinamenti"]]},
                     {"nome": "Senza fattura", "intest": bk.COLONNE_MOV, "righe": [[m[c] for c in bk.COLONNE_MOV] for m in out["senza_fattura"]], "totali": [2]}], [k["movimenti"], k["abbinati"]])
            scarica_dossier("bk", _gen, "Riconciliazione", audit, "Riconciliazione bancaria")
