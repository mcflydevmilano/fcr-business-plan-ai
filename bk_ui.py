"""bk_ui.py - Interfaccia della Riconciliazione bancaria."""
import datetime as dt

import pandas as pd
import streamlit as st

import bk
import guida
import sk
import ops_report
import sc
import theme
from core import fmt_num
from ui_util import cantieri_rubrica, colonna_cantiere, esempi_attivi, senza_esempi, banner_esempio, blocco_tabella, pannello_archivio, scarica_dossier, sola_lettura, sostituisci_tabella

ss = st.session_state


@senza_esempi
def _esempio():
    g = lambda n: (dt.date.today() + dt.timedelta(days=n)).isoformat()
    mov = [(g(-3), "BONIFICO DA COMUNE DI ESEMPIO SAL 2 FATT 14/2026", 42500.00), (g(-2), "BONIFICO A CALCESTRUZZI ALFA SRL FATT 311", -9800.00), (g(-2), "COMMISSIONI E SPESE TENUTA CONTO", -18.50),
           (g(-1), "BONIFICO A PONTEGGI GAMMA SALDO PARZIALE", -4000.00), (g(-1), "ADDEBITO CARBURANTE FLOTTA", -612.40)]
    return pd.DataFrame([dict(zip(bk.COLONNE_MOV, (*r, "Conto generale"))) for r in mov], columns=bk.COLONNE_MOV)


@senza_esempi
def _esempio_conti():
    g = lambda n: (dt.date.today() + dt.timedelta(days=n)).isoformat()
    righe = [("Conto generale", "Banca Esempio", "IT60X0542811101000000123456", "", 15000.0, 10000.0), ("Villa Lago", "Banca Esempio", "", "Villa Lago", 8000.0, 0.0)]
    return pd.DataFrame([dict(zip(bk.COLONNE_CONTI, r)) for r in righe], columns=bk.COLONNE_CONTI)


@senza_esempi
def _esempio_debiti():
    g = lambda n: (dt.date.today() + dt.timedelta(days=n)).isoformat()
    return pd.DataFrame([dict(zip(bk.COLONNE_DEBITI, ("Conto generale", "Mutuo capannone", 120000.0, 2500.0, 1, g(12))))], columns=bk.COLONNE_DEBITI)


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
    return {"movimenti": ss["bk_mov"].to_dict("records"), "conti": ss["bk_conti"].to_dict("records") if "bk_conti" in ss else [],
            "debiti": ss["bk_debiti"].to_dict("records") if "bk_debiti" in ss else []}


def _applica(p, nome):
    sostituisci_tabella("bk_mov", pd.DataFrame(p.get("movimenti") or [], columns=bk.COLONNE_MOV))
    sostituisci_tabella("bk_conti", pd.DataFrame(p.get("conti") or [], columns=bk.COLONNE_CONTI))
    sostituisci_tabella("bk_debiti", pd.DataFrame(p.get("debiti") or [], columns=bk.COLONNE_DEBITI))
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


EUR = lambda x: f"{fmt_num(x)} €"


def _prospetto(conti, mov, docs, debiti, alias, avvisi):
    """Un prospetto per ogni conto: dove siamo, cosa dobbiamo, cosa succede nelle prossime settimane."""
    if not conti:
        st.info("Aggiungi i **conti correnti** nella scheda 1 (uno per l'azienda e uno per ogni cantiere che ha il suo conto): qui vedrai per ognuno saldo, debiti e previsione.")
        return
    settimane = st.slider("Quante settimane in avanti", 4, 26, 12, key="bk_sett")
    P = bk.prospetti(conti, mov, docs, debiti, alias=alias, p={"settimane": settimane})
    for a in avvisi[:6]:
        st.caption("⚠️ " + a)
    T = P["totale"]
    st.markdown(theme.stat_strip([
        {"label": "Saldo di tutti i conti", "value": EUR(T["saldo"]), "sub": f"{T['conti']} conti", "tono": "bad" if T["saldo"] < 0 else "info"},
        {"label": "Disponibile con i fidi", "value": EUR(T["disponibile"]), "sub": f"fidi {EUR(T['fido'])}", "tono": "info"},
        {"label": "Debiti da restituire", "value": EUR(T["debito_residuo"]), "sub": f"rate nel periodo {EUR(T['rate_periodo'])}", "tono": "warn" if T["debito_residuo"] else "ok"},
        {"label": "Conti in sofferenza", "value": str(T["sotto_zero"]), "sub": "saldo previsto sotto zero", "tono": "bad" if T["sotto_zero"] else "ok"}]), unsafe_allow_html=True)
    st.markdown("##### Tutti i conti a confronto")
    riga = lambda x: {"Conto": x["conto"]["Conto"], "Cantiere": x["conto"]["Cantiere"] or "generale", "Banca": x["conto"]["Banca"], "Saldo": round(x["saldo"]), "Fido": round(x["fido"]),
                      "Debiti": round(x["debito_residuo"]), "Da incassare": round(x["fatture_attive_aperte"]), "Da pagare": round(x["fatture_passive_aperte"]),
                      f"Saldo tra {settimane} sett.": round(x["previsione"][-1]["Saldo previsto"]), "Minimo previsto": round(x["minimo"]["Saldo previsto"]) if x["minimo"] else 0,
                      "Allarme": "🔴" if x["primo_sotto_zero"] and x["primo_sotto_zero"]["Stato"] == "bad" else ("🟡" if x["primo_sotto_zero"] else "🟢")}
    st.dataframe(pd.DataFrame([riga(x) for x in P["conti"]]), hide_index=True, width="stretch")
    if P["senza_conto"]:
        st.warning(f"{len(P['senza_conto'])} fatture dello Scadenzario non hanno un conto: nessun conto «generale» le raccoglie. Aggiungi un conto senza cantiere per vederle nel prospetto.")
    st.caption("Le fatture dello Scadenzario vanno al conto del loro cantiere; quelle senza cantiere, o di un cantiere senza conto, al conto generale. Se un cantiere ha più conti, al primo dell'elenco.")
    nomi = [x["conto"]["Conto"] for x in P["conti"]]
    scelto = st.selectbox("Apri il prospetto di un conto", nomi, key="bk_conto_sel")
    x = P["conti"][nomi.index(scelto)] if scelto in nomi else P["conti"][0]
    c = x["conto"]
    st.markdown(f"#### {c['Conto']}")
    st.caption(" · ".join(v for v in (c["Banca"], c["Iban"], f"Cantiere: {c['Cantiere']}" if c["Cantiere"] else "Conto generale") if v))
    st.markdown(theme.stat_strip([
        {"label": "Saldo oggi", "value": EUR(x["saldo"]), "sub": f"iniziale {EUR(c['Saldo_iniziale'])} + entrate {EUR(x['entrate'])} − uscite {EUR(x['uscite'])}", "tono": "bad" if x["saldo"] < 0 else "ok"},
        {"label": "Disponibile", "value": EUR(x["disponibile"]), "sub": f"con fido di {EUR(x['fido'])}", "tono": "info"},
        {"label": "Debiti", "value": EUR(x["debito_residuo"]), "sub": f"{len(x['debiti'])} voci, rate nel periodo {EUR(x['rate_periodo'])}", "tono": "warn" if x["debito_residuo"] else "ok"},
        {"label": "Fatture aperte", "value": f"{EUR(x['fatture_attive_aperte'])} / {EUR(x['fatture_passive_aperte'])}", "sub": "da incassare / da pagare", "tono": "info"}]), unsafe_allow_html=True)
    for a in x["avvisi"]:
        st.warning(a)
    if x["debiti"]:
        st.markdown("**Debiti del conto**")
        st.dataframe(pd.DataFrame(x["debiti"]).drop(columns=["Conto"]).rename(columns=bk.ETICHETTE_DEBITI), hide_index=True, width="stretch")
    st.markdown(f"**Previsione del saldo, settimana per settimana** ({settimane} settimane)")
    prev = pd.DataFrame(x["previsione"])
    st.line_chart(prev.set_index("Settimana")[["Saldo previsto", "Disponibile con fido"]])
    st.dataframe(prev.drop(columns=["Stato"]).assign(Allarme=prev["Stato"].map({"ok": "🟢", "warn": "🟡", "bad": "🔴"})), hide_index=True, width="stretch")
    st.caption("È una previsione di gestione: parte dal saldo di oggi, aggiunge gli incassi e toglie i pagamenti attesi alle scadenze dello Scadenzario e le rate dei debiti. "
               "Le fatture attive già scadute contano per il 50% nella prima settimana, quelle passive scadute per il 100%. 🟡 = sotto zero ma dentro il fido, 🔴 = oltre il fido.")


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Riconciliazione bancaria", "Abbina i movimenti del conto alle fatture e segna da solo cosa è stato pagato o incassato."), unsafe_allow_html=True)
    guida.mostra("bk")
    if "bk_mov" not in ss:
        ss["bk_mov"] = _esempio()
        ss["bk_demo"] = esempi_attivi()
    if "bk_conti" not in ss:
        ss["bk_conti"] = _esempio_conti()
    if "bk_debiti" not in ss:
        ss["bk_debiti"] = _esempio_debiti()
    for chiave, cols in (("bk_mov", ("Data", "Descrizione", "Conto")), ("bk_conti", ("Conto", "Banca", "Iban", "Cantiere")), ("bk_debiti", ("Conto", "Descrizione", "Prossima_rata"))):
        for c in cols:                                 # salvataggi vecchi: colonne nuove vuote (NaN) = tipo numerico, che l'editor di testo rifiuta
            if c in ss[chiave].columns and ss[chiave][c].dtype != object:
                ss[chiave][c] = ss[chiave][c].astype(object).where(ss[chiave][c].notna(), "")
    pannello_archivio("bk", "i movimenti", _raccogli, _applica, audit, utente)
    t1, tp, t2, t3 = st.tabs(["🏦 1. Conti e movimenti", "📊 2. Prospetto per conto", "🔗 3. Abbinamenti", "📄 4. Dossier"])
    t = st.column_config
    with t1:
        banner_esempio("bk_demo", [("bk_mov", bk.COLONNE_MOV), ("bk_conti", bk.COLONNE_CONTI), ("bk_debiti", bk.COLONNE_DEBITI)], "svuota_bk")
        blocco_tabella("bk_conti", "Conti correnti", "Un conto per riga: quello generale dell'azienda e quelli dei singoli cantieri. Il fido è quanto la banca ti lascia andare in rosso.",
                       bk.COLONNE_CONTI, bk.ETICHETTE_CONTI,
                       {"Conto": t.TextColumn(bk.ETICHETTE_CONTI["Conto"], width="medium"), "Banca": t.TextColumn(bk.ETICHETTE_CONTI["Banca"]), "Iban": t.TextColumn(bk.ETICHETTE_CONTI["Iban"], width="medium"),
                        "Cantiere": colonna_cantiere(bk.ETICHETTE_CONTI["Cantiere"], (("bk_conti", "Cantiere"),)),
                        "Saldo_iniziale": t.NumberColumn(bk.ETICHETTE_CONTI["Saldo_iniziale"], format="%.2f", help="Saldo del conto prima del primo movimento che inserisci qui sotto."),
                        "Fido": t.NumberColumn(bk.ETICHETTE_CONTI["Fido"], min_value=0.0, format="%.0f")},
                       ss["bk_conti"], "bk", 2, audit, 200)
        blocco_tabella("bk_debiti", "Debiti legati ai conti", "Mutui, leasing, anticipi su fatture, finanziamenti: per ognuno il residuo, la rata e quando scade la prossima. Servono a prevedere il saldo futuro.",
                       bk.COLONNE_DEBITI, bk.ETICHETTE_DEBITI,
                       {"Conto": t.TextColumn(bk.ETICHETTE_DEBITI["Conto"], width="medium", help="Scrivi il nome del conto come nella tabella «Conti correnti»."),
                        "Descrizione": t.TextColumn(bk.ETICHETTE_DEBITI["Descrizione"], width="large"), "Residuo": t.NumberColumn(bk.ETICHETTE_DEBITI["Residuo"], min_value=0.0, format="%.0f"),
                        "Rata": t.NumberColumn(bk.ETICHETTE_DEBITI["Rata"], min_value=0.0, format="%.0f"), "Ogni_mesi": t.NumberColumn(bk.ETICHETTE_DEBITI["Ogni_mesi"], min_value=1, max_value=12, step=1, format="%d"),
                        "Prossima_rata": t.TextColumn(bk.ETICHETTE_DEBITI["Prossima_rata"], help="AAAA-MM-GG o GG/MM/AAAA")},
                       ss["bk_debiti"], "bk", 3, audit, 200)
        blocco_tabella("bk_mov", "Movimenti del conto corrente", "Incolla o importa l'estratto conto (Excel/CSV della banca): entrate con +, uscite con −.", bk.COLONNE_MOV, bk.ETICHETTE_MOV,
                       {"Data": t.TextColumn(bk.ETICHETTE_MOV["Data"]), "Descrizione": t.TextColumn(bk.ETICHETTE_MOV["Descrizione"], width="large"), "Importo": t.NumberColumn(bk.ETICHETTE_MOV["Importo"], format="%.2f"),
                        "Conto": t.TextColumn(bk.ETICHETTE_MOV["Conto"], width="medium", help="Il nome del conto, come scritto in «Conti correnti».")},
                       ss["bk_mov"], "bk", 1, audit, 300, bk.SINONIMI_MOV)
    mov, av = bk.normalizza_movimenti(ss["bk_mov"].to_dict("records"))
    docs = _docs_sc()
    conti, av_c = bk.normalizza_conti(ss["bk_conti"].to_dict("records"))
    debiti, av_d = bk.normalizza_debiti(ss["bk_debiti"].to_dict("records"), conti)
    alias = sk.indice(cantieri_rubrica())
    out = bk.calcola_bk(mov, docs, {"alias": alias}, conti)
    k = out["kpi"]

    with tp:
        _prospetto(conti, mov, docs, debiti, alias, av_c + av_d)

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
                ed = st.data_editor(pd.DataFrame(righe), hide_index=True, width="stretch", key=f"conf_bk_{len(ab)}_{k['importo_riconciliato']:.0f}", disabled=[c for c in righe[0] if c != "Conferma"] if not sola_lettura() else True)
                scelti = [a for a, c in zip(ab, ed["Conferma"].tolist()) if c]
                if st.button(f"✅ Segna {len(scelti)} fatture come pagate/incassate nello Scadenzario", key="applica_bk", type="primary", disabled=sola_lettura() or not scelti):
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
