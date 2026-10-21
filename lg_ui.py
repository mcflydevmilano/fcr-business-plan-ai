"""lg_ui.py - Interfaccia dello Studio legale."""
import datetime as dt
import urllib.parse

import pandas as pd
import streamlit as st

import gt
import guida
import lg
import ops_report
import sc
import theme
from core import fmt_num
from ui_util import banner_esempio, blocco_tabella, pannello_archivio, scarica_dossier, sola_lettura, sostituisci_tabella

ss = st.session_state
ICONE = {"ok": "🟢", "warn": "🟡", "bad": "🔴", "nd": "⚪"}
_PRINC = ("lg_riserve", "lg_contratti", "lg_termini", "lg_solleciti")
_COLS = {"lg_riserve": lg.COLONNE_RISERVE, "lg_contratti": lg.COLONNE_CONTRATTI, "lg_termini": lg.COLONNE_TERMINI, "lg_solleciti": lg.COLONNE_SOLLECITI}


def _esempio():
    g = lambda n: (dt.date.today() + dt.timedelta(days=n)).isoformat()
    mk = lambda cols, rows: pd.DataFrame([dict(zip(cols, r)) for r in rows], columns=cols)
    ris = [("Villa Lago", "Riserva", "Maggiori oneri per scavo in presenza di roccia", 18500, g(-20), g(6), "Inviata"),
           ("Scuola Elementare", "Variante", "Spostamento impianto elettrico richiesto dal Comune", 12400, g(-5), g(40), "Da inviare"),
           ("Scuola Elementare", "Richiesta di proroga", "Sospensione per maltempo di 12 giorni", 0, g(-10), g(-2), "Inviata"),
           ("Villa Lago", "Contestazione", "Contestazione su SAL n. 3", 6200, g(-60), g(-30), "Chiusa")]
    con = [("Contratto d'appalto Villa Lago", "Famiglia Lago", "Villa Lago", 480000, g(300), ""), ("Contratto Scuola Elementare", "Comune di Esempio", "Scuola Elementare", 950000, g(520), ""),
           ("Polizza fideiussoria definitiva", "Assicurazioni Esempio", "Scuola Elementare", 95000, g(12), "Da rinnovare"), ("Subappalto elettrico", "Elettroimpianti Beta", "Scuola Elementare", 110000, g(-8), "Scaduto")]
    ter = [("Villa Lago", 480000, g(35), 1.0), ("Scuola Elementare", 950000, g(60), 1.0)]
    sol = [("Mario Verdi SRL", g(-40), lg.LIVELLI[0], "Email", "Nessuna risposta"), ("Mario Verdi SRL", g(-20), lg.LIVELLI[1], "PEC", "Ha promesso il pagamento, non arrivato")]
    return mk(lg.COLONNE_RISERVE, ris), mk(lg.COLONNE_CONTRATTI, con), mk(lg.COLONNE_TERMINI, ter), mk(lg.COLONNE_SOLLECITI, sol)


def _cfg():
    n, t, s = st.column_config.NumberColumn, st.column_config.TextColumn, st.column_config.SelectboxColumn
    a, b, c, d = lg.ETICHETTE_RISERVE, lg.ETICHETTE_CONTRATTI, lg.ETICHETTE_TERMINI, lg.ETICHETTE_SOLLECITI
    return ({"Cantiere": t(a["Cantiere"]), "Tipo": s(a["Tipo"], options=lg.TIPI_RISERVA), "Descrizione": t(a["Descrizione"], width="large"), "Importo": n(a["Importo"], min_value=0.0, step=500.0, format="%.0f"),
             "Data": t(a["Data"], help="AAAA-MM-GG o GG/MM/AAAA"), "Termine": t(a["Termine"], help="La data la comunica lo studio legale."), "Stato": s(a["Stato"], options=lg.STATI_RISERVA)},
            {"Contratto": t(b["Contratto"], width="medium"), "Controparte": t(b["Controparte"]), "Cantiere": t(b["Cantiere"]), "Importo": n(b["Importo"], min_value=0.0, step=1000.0, format="%.0f"),
             "Scadenza": t(b["Scadenza"]), "Note": t(b["Note"])},
            {"Cantiere": t(c["Cantiere"]), "Importo": n(c["Importo"], min_value=0.0, step=1000.0, format="%.0f"), "Termine": t(c["Termine"]),
             "Penale_per_mille": n(c["Penale_per_mille"], min_value=0.0, max_value=5.0, step=0.1, format="%.2f", help="Di solito tra 0,3 e 1 per mille al giorno: fa fede il contratto.")},
            {"Cliente": t(d["Cliente"]), "Data": t(d["Data"]), "Livello": s(d["Livello"], options=lg.LIVELLI), "Modalita": s(d["Modalita"], options=lg.MODI), "Esito": t(d["Esito"], width="large")})


def _raccogli():
    return {**{k[3:]: ss[k].to_dict("records") for k in _PRINC}, "invii": ss.get("lg_invii", []),
            "params": {"preavviso_gg": ss.get("lg_preavviso_gg", 15), "tetto_pct": ss.get("lg_tetto_pct", 10.0)}}


def _applica(p, nome):
    for k in _PRINC:
        sostituisci_tabella(k, pd.DataFrame(p.get(k[3:]) or [], columns=_COLS[k]))
    ss["lg_invii"] = list(p.get("invii") or [])
    ss["lg_demo"] = False
    ss["_pending"] = {"lg_preavviso_gg": (p.get("params") or {}).get("preavviso_gg", 15), "lg_tetto_pct": (p.get("params") or {}).get("tetto_pct", 10.0)}


def _altri_moduli():
    """Fatture e commesse del Cronoprogramma dagli altri strumenti (sessione o ultimo salvataggio)."""
    try:
        import ca_ui
        pay, _ = ca_ui._payloads(True)
    except Exception:
        pay = {}
    fatt = sc.normalizza_documenti((pay.get("sc") or {}).get("docs"))[0] if pay.get("sc") else []
    comm = []
    if pay.get("gt"):
        fasi, _ = gt.normalizza_fasi(pay["gt"].get("fasi"))
        fermi, _ = gt.normalizza_fermi(pay["gt"].get("fermi")) if pay["gt"].get("fermi") else ([], [])
        if fasi:
            comm = gt.calcola_gt(fasi, pay["gt"].get("params"), fermi)["commesse"]
    return fatt, comm, "sc" in pay, "gt" in pay


def _fascicolo_pdf(f, out, nome):
    q = out["params"]
    return ops_report.report_generico(
        "Studio legale", "Fascicolo cliente", nome, q["oggi"], [("CLIENTE", f["Cliente"][:20]), ("SCADUTO", fmt_num(f["Totale scaduto"]) + " EUR")],
        [("Credito scaduto", fmt_num(f["Totale scaduto"]) + " EUR", f"{len(f['Fatture'])} fatture", "bad"), ("Ritardo massimo", f"{f['Ritardo max (gg)']} gg", f["Livello"][4:], "warn"),
         ("Solleciti fatti", str(f["Solleciti fatti"]), "registrati", "info"), ("Suggerimento", "Studio" if f["Suggerimento"].startswith("Passa") else "Sollecito", "", "info")],
        ("FASCICOLO PER LO STUDIO", "warn", f["Suggerimento"]),
        [{"titolo": "Fatture scadute", "tabella": (["Documento", "Cantiere", "Scadenza", "Residuo", "Ritardo gg"],
                                                   [(x["Documento"] or "n.d.", x["Cantiere"][:20], ops_report.fd(x["Scadenza"]), ops_report.N(x["Residuo"], 2), str(x["Ritardo"])) for x in f["Fatture"]])},
         {"titolo": "Solleciti già fatti", "tabella": (["Data", "Livello", "Come", "Esito"], [(ops_report.fd(s["Data"]), s["Livello"][4:], s["Modalita"], s["Esito"][:50]) for s in f["Storico"]] or [("-", "nessuno", "", "")])},
         {"titolo": "Nota", "testo": ["Fascicolo preparato dall'applicazione FCR come promemoria per lo studio legale. Gli importi sono quelli registrati nello Scadenzario: vanno verificati sui documenti originali."]}],
        [{"nome": "Fatture", "intest": ["Documento", "Cantiere", "Scadenza", "Residuo", "Ritardo gg"], "righe": [[x["Documento"], x["Cantiere"], x["Scadenza"], x["Residuo"], x["Ritardo"]] for x in f["Fatture"]], "totali": [3]}], f["Cliente"])


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Studio legale", "Passa un cliente allo studio con tutto il fascicolo, tieni le riserve sotto controllo e calcola le penali di ritardo."), unsafe_allow_html=True)
    guida.mostra("lg")
    if "lg_riserve" not in ss:
        for k, df in zip(_PRINC, _esempio()):
            ss[k] = df
        ss["lg_demo"] = True
    ss.setdefault("lg_invii", [])
    pannello_archivio("lg", "lo studio legale", _raccogli, _applica, audit, utente)
    st.caption("Promemoria organizzativo: le scadenze di legge le fissa lo studio legale, qui si scrivono le date che comunica. Non è una consulenza legale.")
    t1, t2, t3, t4, t5 = st.tabs(["🧾 1. Dati", "📨 2. Passa allo studio", "⚖️ 3. Riserve e contratti", "⏱️ 4. Penali di ritardo", "📄 5. Dossier"])
    cr, cc, ct, cs = _cfg()
    with t1:
        banner_esempio("lg_demo", [(k, _COLS[k]) for k in _PRINC], "svuota_lg")
        blocco_tabella("lg_riserve", "Riserve, varianti e contestazioni", "Una riga per ogni richiesta. «Termine» è la data limite che ti ha dato lo studio.", lg.COLONNE_RISERVE, lg.ETICHETTE_RISERVE, cr, ss["lg_riserve"], "lg", 1, audit, 220)
        blocco_tabella("lg_contratti", "Contratti e polizze", "Con la scadenza: l'app ti avvisa prima.", lg.COLONNE_CONTRATTI, lg.ETICHETTE_CONTRATTI, cc, ss["lg_contratti"], "lg", 2, audit, 220)
        blocco_tabella("lg_termini", "Termini contrattuali per il calcolo delle penali", "Il nome del cantiere deve essere uguale a quello del Cronoprogramma.", lg.COLONNE_TERMINI, lg.ETICHETTE_TERMINI, ct, ss["lg_termini"], "lg", 3, audit, 160)
        blocco_tabella("lg_solleciti", "Solleciti già fatti ai clienti", "Scrivi ogni sollecito che hai mandato: finisce nel fascicolo per lo studio.", lg.COLONNE_SOLLECITI, lg.ETICHETTE_SOLLECITI, cs, ss["lg_solleciti"], "lg", 4, audit, 200)
        ss.setdefault("lg_preavviso_gg", 15)
        ss.setdefault("lg_tetto_pct", 10.0)
        st.subheader("Ipotesi")
        a, b = st.columns(2)
        a.number_input("Preavviso scadenze (giorni)", 0, 90, step=5, key="lg_preavviso_gg")
        b.number_input("Tetto delle penali (% del contratto)", 1.0, 30.0, step=0.5, key="lg_tetto_pct", help="Spesso il 10%: fa fede il contratto.")

    riserve, a1 = lg.normalizza_riserve(ss["lg_riserve"].to_dict("records"))
    contratti, a2 = lg.normalizza_contratti(ss["lg_contratti"].to_dict("records"))
    termini, a3 = lg.normalizza_termini(ss["lg_termini"].to_dict("records"))
    solleciti, a4 = lg.normalizza_solleciti(ss["lg_solleciti"].to_dict("records"))
    fatture, comm, ha_sc, ha_gt = _altri_moduli()
    out = lg.calcola_lg(riserve, contratti, termini, solleciti, comm, fatture, {"preavviso_gg": ss.get("lg_preavviso_gg", 15), "tetto_pct": ss.get("lg_tetto_pct", 10.0)})
    k = out["kpi"]

    with t2:
        if not ha_sc:
            st.info("Per i fascicoli servono le fatture dello **Scadenzario**: aprilo e inserisci i documenti (o salvali). Qui vedrai i clienti con fatture scadute.")
        elif not out["fascicoli"]:
            st.success("Nessun cliente con fatture scadute da sollecitare o passare allo studio.")
        if out["fascicoli"]:
            st.dataframe(pd.DataFrame([{"Cliente": f["Cliente"], "Scaduto €": f["Totale scaduto"], "Ritardo gg": f["Ritardo max (gg)"], "Fatture": len(f["Fatture"]), "Solleciti fatti": f["Solleciti fatti"],
                                        "Cosa fare": f["Suggerimento"]} for f in out["fascicoli"]]).round(0), hide_index=True, width="stretch")
            nome = st.selectbox("Cliente da passare allo studio", [f["Cliente"] for f in out["fascicoli"]], key="lg_sel_cli")
            f = next(x for x in out["fascicoli"] if x["Cliente"] == nome)
            ris_c = [r for r in out["riserve"] if r["Stato"] in lg.APERTI and r["Cantiere"] in {x["Cantiere"] for x in f["Fatture"]}]
            nota = st.text_area("Nota per lo studio (facoltativa)", key="lg_nota", placeholder="es. Il cliente contesta la qualità del lavoro; ha dichiarato di voler pagare a rate.")
            ogg, corpo = lg.testo_passaggio(f, nota, riserve=ris_c)
            ogg = st.text_input("Oggetto", ogg, key="lg_ogg")
            corpo = st.text_area("Messaggio", corpo, height=280, key="lg_corpo")
            canali = lg.canali_attivi()
            pdf, xlsx, rid = _fascicolo_pdf(f, out, f"Fascicolo {f['Cliente']}")
            c1, c2, c3 = st.columns(3)
            c1.download_button("📥 Fascicolo PDF", pdf, file_name=f"fascicolo_{rid}.pdf", mime="application/pdf", width="stretch", key="lg_dl_pdf")
            studio = lg.destinatari()
            mail = f"mailto:{','.join(studio)}?" + urllib.parse.urlencode({"subject": ogg, "body": corpo[:1500]}, quote_via=urllib.parse.quote) if studio else ""
            if mail:
                c2.link_button("✉️ Apri nella tua posta", mail, width="stretch")
            if c3.button("📨 Invia allo studio", key="lg_invia", type="primary", width="stretch", disabled=sola_lettura() or not (canali["email"] or canali["slack"])):
                try:
                    usati = lg.invia_studio(ogg, corpo, [(f"fascicolo_{rid}.pdf", pdf, "application/pdf")])
                    ss["lg_invii"] = [*ss.get("lg_invii", []), {"Data": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "Cliente": f["Cliente"], "Importo": f["Totale scaduto"], "Canale": " + ".join(usati), "Utente": utente}]
                    audit("lg_passato_allo_studio", f"{f['Cliente']} · {fmt_num(f['Totale scaduto'])} € · via {' + '.join(usati)}")
                    st.success("Inviato allo studio via " + " e ".join(usati) + ". Ricordati di salvare per tenere traccia dell'invio.")
                except Exception as e:
                    st.error(f"Invio non riuscito: {e}")
            if not (canali["email"] or canali["slack"]):
                st.caption("L'invio diretto non è ancora configurato: scarica il fascicolo e inoltralo, oppure chiedi all'amministratore di impostare STUDIO_LEGALE_EMAIL (e la posta SMTP) o STUDIO_LEGALE_SLACK_WEBHOOK_URL nei Secrets.")
        if ss.get("lg_invii"):
            st.markdown("**Già passati allo studio**")
            st.dataframe(pd.DataFrame(ss["lg_invii"]), hide_index=True, width="stretch")

    with t3:
        for x in (a1 + a2 + a3 + a4)[:4]:
            st.caption("⚠️ " + x)
        st.markdown(theme.stat_strip([
            {"label": "Richieste aperte", "value": str(k["riserve_aperte"]), "sub": f"{fmt_num(k['importo_riserve'])} € richiesti", "tono": "info"},
            {"label": "Termini scaduti", "value": str(k["termini_scaduti"]), "sub": f"{k['termini_vicini']} in arrivo", "tono": "bad" if k["termini_scaduti"] else ("warn" if k["termini_vicini"] else "ok")},
            {"label": "Contratti scaduti", "value": str(k["contratti_scaduti"]), "sub": f"{k['contratti_in_scadenza']} in scadenza", "tono": "bad" if k["contratti_scaduti"] else ("warn" if k["contratti_in_scadenza"] else "ok")},
            {"label": "Penali stimate", "value": fmt_num(k["penali_stimate"]) + " €", "sub": f"{k['cantieri_in_ritardo']} cantieri in ritardo", "tono": "warn" if k["penali_stimate"] else "ok"}]), unsafe_allow_html=True)
        for a in out["avvisi"][:8]:
            st.warning(a)
        if out["riserve"]:
            st.markdown("**Riserve, varianti e contestazioni**")
            st.dataframe(pd.DataFrame([{"": ICONE[r["Stato scadenza"]] if r["Stato"] in lg.APERTI else "", "Cantiere": r["Cantiere"], "Tipo": r["Tipo"], "Di cosa si tratta": r["Descrizione"], "Importo €": r["Importo"],
                                        "Termine": r["Termine"], "Giorni": r["Giorni"], "Stato": r["Stato"]} for r in out["riserve"]]), hide_index=True, width="stretch")
        if out["contratti"]:
            st.markdown("**Contratti e polizze**")
            st.dataframe(pd.DataFrame([{"": ICONE[c["Stato scadenza"]], "Contratto": c["Contratto"], "Controparte": c["Controparte"], "Importo €": c["Importo"], "Scadenza": c["Scadenza"], "Giorni": c["Giorni"], "Note": c["Note"]}
                                       for c in out["contratti"]]), hide_index=True, width="stretch")

    with t4:
        if not termini:
            st.info("Inserisci i termini contrattuali nella scheda 1.")
        else:
            if not ha_gt:
                st.warning("Per stimare il ritardo serve il **Cronoprogramma**: aprilo e inserisci le fasi (o salvalo).")
            st.caption("Ritardo = fine lavori stimata dal Cronoprogramma meno il termine del contratto. Penale = importo × ‰ al giorno × giorni, fino al tetto. Fa fede il contratto: verifica con lo studio.")
            st.dataframe(pd.DataFrame([{"": ICONE[x["Stato"]], "Cantiere": x["Cantiere"], "Termine contratto": x["Termine"], "Fine stimata": x["Fine stimata"], "Ritardo gg": x["Ritardo gg"], "‰/giorno": x["Penale_per_mille"],
                                        "Penale stimata €": x["Penale"], "Tetto €": x["Tetto"], "Nota": x["Nota"]} for x in out["penali"]]).round(0), hide_index=True, width="stretch")

    with t5:
        def _gen(nome):
            return ops_report.report_generico(
                "Studio legale", "Riserve, contratti e penali", nome, out["params"]["oggi"], [("RISERVE APERTE", str(k["riserve_aperte"])), ("CONTRATTI", str(k["contratti"]))],
                [("Richieste aperte", str(k["riserve_aperte"]), f"{fmt_num(k['importo_riserve'])} €", "info"), ("Termini scaduti", str(k["termini_scaduti"]), f"{k['termini_vicini']} in arrivo", "bad" if k["termini_scaduti"] else "ok"),
                 ("Contratti da rinnovare", str(k["contratti_scaduti"] + k["contratti_in_scadenza"]), "scaduti o in scadenza", "warn" if (k["contratti_scaduti"] + k["contratti_in_scadenza"]) else "ok"),
                 ("Penali stimate", fmt_num(k["penali_stimate"]) + " €", f"{k['cantieri_in_ritardo']} cantieri", "warn" if k["penali_stimate"] else "ok")],
                ops_report._esito(k["n_bad"], k["n_warn"], max(1, k["riserve_aperte"] + k["contratti"]), "pratiche"),
                [{"titolo": "Riserve, varianti e contestazioni", "tabella": (["Cantiere", "Tipo", "Descrizione", "Importo", "Termine", "Stato"],
                                                                              [(r["Cantiere"][:16], r["Tipo"][:14], r["Descrizione"][:34], ops_report.N(r["Importo"]), ops_report.fd(r["Termine"]), r["Stato"]) for r in out["riserve"]])},
                 {"titolo": "Contratti e polizze", "tabella": (["Contratto", "Controparte", "Importo", "Scadenza", "Giorni"], [(c["Contratto"][:30], c["Controparte"][:20], ops_report.N(c["Importo"]), ops_report.fd(c["Scadenza"]),
                                                                                                              "" if c["Giorni"] is None else str(c["Giorni"])) for c in out["contratti"]])},
                 {"titolo": "Penali di ritardo", "tabella": (["Cantiere", "Termine", "Fine stimata", "Ritardo gg", "Penale", "Tetto"], [(x["Cantiere"][:18], ops_report.fd(x["Termine"]), ops_report.fd(x["Fine stimata"]), "" if x["Ritardo gg"] is None else str(x["Ritardo gg"]),
                                                                                                                                      ops_report.N(x["Penale"]), ops_report.N(x["Tetto"])) for x in out["penali"]]), "pagina": True},
                 {"titolo": "Punti di attenzione", "testo": ["- " + a for a in (out["avvisi"] or ["Nessuna criticità rilevata."])]},
                 {"titolo": "Metodo e limiti", "testo": ["Le scadenze di legge sono fissate dallo studio legale e riportate qui come promemoria. Le penali sono una stima: ritardo dal Cronoprogramma × importo × ‰ al giorno, fino al tetto indicato. "
                                                          "Non è una consulenza legale: ogni valutazione va condivisa con lo studio."]}],
                [{"nome": "Riserve", "intest": lg.COLONNE_RISERVE, "righe": [[r[c] for c in lg.COLONNE_RISERVE] for r in out["riserve"]], "totali": [3]},
                 {"nome": "Contratti", "intest": lg.COLONNE_CONTRATTI, "righe": [[c[x] for x in lg.COLONNE_CONTRATTI] for c in out["contratti"]], "totali": [3]},
                 {"nome": "Penali", "intest": ["Cantiere", "Importo", "Termine", "Penale ‰", "Fine stimata", "Ritardo gg", "Penale stimata"],
                  "righe": [[x["Cantiere"], x["Importo"], x["Termine"], x["Penale_per_mille"], x["Fine stimata"], x["Ritardo gg"] or 0, "=B{r}*D{r}/1000*F{r}"] for x in out["penali"]]}], [k["riserve_aperte"], k["contratti"]])
        scarica_dossier("lg", _gen, "Studio_legale", audit, "Studio legale")
