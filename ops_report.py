"""ops_report.py - Dossier PDF ed Excel dei moduli operativi: Gare, Fornitori, Sicurezza, Mezzi, Organico."""
import charts
import rep_gen
from core import fmt_num
from sc import data_da

N = lambda x, d=0: fmt_num(x, d)
EUR = lambda x: fmt_num(x) + " EUR"


def fd(s):
    d = data_da(s)
    return d.strftime("%d/%m/%Y") if d else ""


ST = {"ok": "OK", "warn": "ATTENZ.", "bad": "CRITICO", "nd": "N.D."}
STD = {"ok": "In regola", "warn": "In scadenza", "bad": "Scaduto", "nd": "Senza data"}
png = lambda f: charts.fig_png(f)


def _esito(n_bad, n_warn, tot, voce):
    if n_bad:
        return ("CRITICITÀ RILEVATE", "bad", f"{voce}: {n_bad} da intervenire su {tot}")
    if n_warn:
        return ("DA TENERE D'OCCHIO", "warn", f"{voce}: {n_warn} con scadenze o scostamenti su {tot}")
    return ("TUTTO IN REGOLA", "ok", f"{voce}: nessuna criticità rilevata")


def _finale(out, ctx_titolo):
    return [a for a in out["avvisi"]] or ["I controlli automatici non hanno rilevato criticità."]


# ----------------------------------------------------------------------------- GARE
def report_ga(out, nome=""):
    k, q = out["kpi"], out["params"]
    ctx = rep_gen.costruisci_ctx("Gare e offerte", "Pipeline gare", nome, {"k": k, "n": nome, "o": str(q["oggi"])})
    gare = out["gare"]
    sez = [{"titolo": "Elenco delle gare", "tabella": (["Gara", "Ente", "Stato", "Base", "Ribasso", "Offerta", "Margine %", "Rib. max", "Scadenza"],
                                                         [(d["Gara"][:20], d["Ente"][:14], d["Stato gara"], N(d["Importo base"]), N(d["Ribasso %"], 1) + "%", N(d["Offerta"]), N(d["Margine %"], 1) + "%",
                                                           N(d["Ribasso massimo %"], 1) + "%", fd(d["Scadenza"])) for d in gare])}]
    if gare:
        sez.append({"titolo": "Convenienza delle offerte", "grafico": png(charts.fig_ga_gare(gare, q["margine_target"], "light"),),
                    "testo": [f"Margine atteso con il ribasso scelto. Obiettivo: {N(q['margine_target'], 0)}% sull'offerta. Il ribasso massimo è quello che lascia ancora il margine obiettivo."]})
    sez.append({"titolo": "Valutazioni e documenti", "tabella": (["Gara", "Valore atteso", "Prob. ponderata", "Documenti mancanti", "Giorni", "Consiglio"],
                                                               [(d["Gara"][:22], N(d["Valore atteso"]), N(d["Ponderato"]), str(d["Documenti mancanti"]), "" if d["Giorni"] is None else str(d["Giorni"]), d["Consiglio"][:34]) for d in gare if d["Stato gara"] in ("Da valutare", "In preparazione", "Presentata")]), "pagina": True})
    sez.append({"titolo": "Punti di attenzione", "testo": ["- " + a for a in _finale(out, "")]})
    sez.append({"titolo": "Metodo e limiti", "testo": ["Offerta = importo a base x (1 - ribasso). Costi = importo a base x costi stimati %. Valore atteso = probabilità x margine - costo di partecipazione. "
                                                       "Probabilità e costi sono stime inserite dall'utente: più sono prudenti, più il consiglio è affidabile. Non sostituisce la valutazione tecnica e legale della gara."]})
    tasso = "n.d." if k["tasso_successo"] is None else N(k["tasso_successo"], 0) + "%"
    pdf = rep_gen.genera_pdf(ctx, "Gare e offerte", "Pipeline delle gare", f"Situazione al {q['oggi'].strftime('%d/%m/%Y')}", [("GARE", str(k["n_gare"])), ("APERTE", str(k["n_aperte"]))],
                             [("Pipeline ponderata", EUR(k["ponderato"]), f"su {EUR(k['importo_pipeline'])} offerti", "info"), ("Valore atteso", EUR(k["valore_atteso"]), "margine ponderato", "ok" if k["valore_atteso"] > 0 else "bad"),
                              ("Scadenze vicine", str(k["in_scadenza"] + k["scadute"]), f"{k['scadute']} già scadute", "bad" if k["scadute"] else ("warn" if k["in_scadenza"] else "ok")),
                              ("Tasso di successo", tasso, f"{k['vinte']} vinte, {k['perse']} perse", "info")], _esito(k["n_bad"], k["n_warn"], k["n_gare"], "gare"), sez)
    righe = []
    for i, d in enumerate(gare, start=2):
        base, costi = d["Importo base"], d["Costi stimati"]
        righe.append([d["Gara"], d["Ente"], d["Stato gara"], base, d["Ribasso %"], "=D{r}*(1-E{r}/100)".replace("D{r}", "D{r}"), costi / base * 100 if base else 0, "=D{r}*G{r}/100", "=F{r}-H{r}", "=IF(F{r}=0,0,I{r}/F{r}*100)", d["Scadenza"]])
    x = rep_gen.genera_excel([{"nome": "Gare", "intest": ["Gara", "Ente", "Stato", "Importo base", "Ribasso %", "Offerta", "Costi % base", "Costi stimati", "Margine", "Margine %", "Scadenza"],
                               "righe": righe, "totali": [3, 5, 7, 8], "formati": {4: "pct", 6: "pct", 9: "pct"}},
                              {"nome": "Documenti", "intest": ["Gara", "Documento", "Scadenza", "Fatto"], "righe": [[d["Gara"], d["Documento"], d["Scadenza"], "Sì" if d["Fatto"] else "No"] for d in out["documenti"]]}])
    return pdf, x, ctx["report_id"]


# ----------------------------------------------------------------------------- FORNITORI
def report_fo(out, nome=""):
    k, q = out["kpi"], out["params"]
    ctx = rep_gen.costruisci_ctx("Fornitori e subappaltatori", "Documenti e contratti", nome, {"k": k, "n": nome, "o": str(q["oggi"])})
    forn = out["fornitori"]
    da_rin = [d for d in out["documenti"] if d["Stato"] in ("bad", "warn")]
    sez = [{"titolo": "Stato dei fornitori", "tabella": (["Fornitore", "Tipo", "Doc.", "Scaduti", "In scad.", "Contratti", "Fatturato", "Residuo", "Da pagare", "Stato"],
                                                          [(f["Fornitore"][:22], f["Tipo"][:10], str(f["Documenti"]), str(f["Scaduti"]), str(f["In scadenza"]), N(f["Contratti"]), N(f["Fatturato"]), N(f["Residuo ordine"]), N(f["Da pagare"]), ST[f["Stato"]]) for f in forn])},
           {"titolo": "Documenti da rinnovare", "grafico": png(charts.fig_scadenze({"bad": k["doc_scaduti"], "warn": k["doc_in_scadenza"], "ok": k["doc_ok"]}, "Documenti dei fornitori", "light")),
            "tabella": (["Fornitore", "Documento", "Scadenza", "Giorni", "Stato"], [(d["Fornitore"][:24], d["Documento"][:28], fd(d["Scadenza"]), str(d["Giorni"]), STD[d["Stato"]]) for d in da_rin])}]
    if out["confronto"]:
        sez.append({"titolo": "Confronto dei preventivi", "pagina": True, "tabella": (["Voce", "Offerte", "Minima", "Massima", "Scarto", "Più bassa", "Più bassa in regola"],
                                                                                    [(c["Voce"][:24], str(c["Offerte"]), N(c["Minima"]), N(c["Massima"]), N(c["Scarto %"], 1) + "%", c["Più bassa"][:18], c["Più bassa in regola"][:18]) for c in out["confronto"]])})
    sez.append({"titolo": "Punti di attenzione", "testo": ["- " + a for a in _finale(out, "")]})
    sez.append({"titolo": "Metodo e limiti", "testo": ["Un documento è «in scadenza» se scade entro il preavviso indicato, «scaduto» se la data è passata. Residuo ordine = contratto - fatturato; da pagare = fatturato - pagato. "
                                                       "Lo strumento è un promemoria: la regolarità dei fornitori (DURC, SOA, assicurazioni) va verificata con i documenti originali."]})
    pdf = rep_gen.genera_pdf(ctx, "Fornitori e subappaltatori", "Documenti e contratti", f"Situazione al {q['oggi'].strftime('%d/%m/%Y')}", [("FORNITORI", str(k["n_fornitori"])), ("DOCUMENTI", str(k["doc_scaduti"] + k["doc_in_scadenza"] + k["doc_ok"] + k["doc_nd"]))],
                             [("Documenti scaduti", str(k["doc_scaduti"]), f"{k['forn_critici']} fornitori critici", "bad" if k["doc_scaduti"] else "ok"), ("In scadenza", str(k["doc_in_scadenza"]), "entro il preavviso", "warn" if k["doc_in_scadenza"] else "ok"),
                              ("Ordini aperti", EUR(k["residuo"]), f"impegnato {EUR(k['impegnato'])}", "info"), ("Da pagare", EUR(k["da_pagare"]), f"{k['sovrafatturati']} sovrafatturati", "warn" if k["sovrafatturati"] else "info")],
                             _esito(k["forn_critici"], sum(1 for f in forn if f["Stato"] == "warn"), max(1, len(forn)), "fornitori"), sez)
    x = rep_gen.genera_excel([
        {"nome": "Documenti", "intest": ["Fornitore", "Tipo", "Documento", "Scadenza", "Giorni", "Stato"], "righe": [[d["Fornitore"], d["Tipo"], d["Documento"], d["Scadenza"], d["Giorni"], STD[d["Stato"]]] for d in out["documenti"]]},
        {"nome": "Contratti", "intest": ["Fornitore", "Commessa", "Descrizione", "Importo", "Fatturato", "Pagato", "Residuo ordine", "Da pagare"],
         "righe": [[c["Fornitore"], c["Commessa"], c["Descrizione"], c["Importo"], c["Fatturato"], c["Pagato"], "=D{r}-E{r}", "=E{r}-F{r}"] for c in out["contratti"]], "totali": [3, 4, 5, 6, 7]},
        {"nome": "Confronto", "intest": ["Voce", "Offerte", "Minima", "Massima", "Media", "Più bassa", "Più bassa in regola", "Risparmio vs media"],
         "righe": [[c["Voce"], c["Offerte"], c["Minima"], c["Massima"], c["Media"], c["Più bassa"], c["Più bassa in regola"], "=E{r}-C{r}"] for c in out["confronto"]]}])
    return pdf, x, ctx["report_id"]


# ----------------------------------------------------------------------------- SICUREZZA
def report_sx(out, nome=""):
    k, q = out["kpi"], out["params"]
    ctx = rep_gen.costruisci_ctx("Sicurezza e documenti di cantiere", "Scadenze e documenti", nome, {"k": k, "n": nome, "o": str(q["oggi"])})
    da_rin = [d for d in out["scadenze"] if d["Stato"] in ("bad", "warn")]
    manc = [d for d in out["documenti"] if not d["Presente"]]
    sez = [{"titolo": "Situazione per cantiere", "tabella": (["Cantiere", "Persone", "Non in regola", "Doc. mancanti", "Doc. scaduti", "Stato"],
                                                            [(c["Cantiere"][:26], str(c["Persone"]), str(c["Persone non in regola"]), str(c["Documenti mancanti"]), str(c["Documenti scaduti"]), ST[c["Stato"]]) for c in out["cantieri"]])},
           {"titolo": "Formazioni e idoneità da rinnovare", "grafico": png(charts.fig_scadenze({"bad": k["scaduti"], "warn": k["in_scadenza"], "ok": k["ok"]}, "Formazioni e idoneità", "light")),
            "tabella": (["Persona", "Cantiere", "Documento", "Scadenza", "Giorni", "Stato"], [(d["Persona"][:20], d["Cantiere"][:16], d["Documento"][:24], fd(d["Scadenza"]), str(d["Giorni"]), STD[d["Stato"]]) for d in da_rin]), "pagina": True},
           {"titolo": "Documenti di cantiere mancanti", "tabella": (["Cantiere", "Documento"], [(d["Cantiere"][:30], d["Documento"][:60]) for d in manc])},
           {"titolo": "Punti di attenzione", "testo": ["- " + a for a in _finale(out, "")]},
           {"titolo": "Metodo e limiti", "testo": ["Promemoria delle scadenze inserite: non sostituisce il RSPP, il coordinatore per la sicurezza né la verifica degli obblighi di legge, e non attesta la regolarità del cantiere. "
                                                "Una persona è «non in regola» se almeno una sua formazione o idoneità risulta scaduta."]}]
    pdf = rep_gen.genera_pdf(ctx, "Sicurezza e documenti di cantiere", "Scadenze e documenti", f"Situazione al {q['oggi'].strftime('%d/%m/%Y')}", [("PERSONE", str(k["n_persone"])), ("CANTIERI", str(k["n_cantieri"]))],
                             [("Persone non in regola", str(k["persone_non_in_regola"]), f"su {k['n_persone']}", "bad" if k["persone_non_in_regola"] else "ok"), ("In scadenza", str(k["in_scadenza"]), "formazioni e idoneità", "warn" if k["in_scadenza"] else "ok"),
                              ("Documenti mancanti", str(k["doc_mancanti"]), f"{k['doc_scaduti']} scaduti", "bad" if k["doc_mancanti"] else "ok"), ("Cantieri a rischio", str(k["cantieri_a_rischio"]), f"su {k['n_cantieri']}", "bad" if k["cantieri_a_rischio"] else "ok")],
                             _esito(k["cantieri_a_rischio"], sum(1 for c in out["cantieri"] if c["Stato"] == "warn"), max(1, k["n_cantieri"]), "cantieri"), sez)
    x = rep_gen.genera_excel([
        {"nome": "Scadenze personale", "intest": ["Persona", "Ruolo", "Cantiere", "Documento", "Scadenza", "Giorni", "Stato"], "righe": [[d["Persona"], d["Ruolo"], d["Cantiere"], d["Documento"], d["Scadenza"], d["Giorni"], STD[d["Stato"]]] for d in out["scadenze"]]},
        {"nome": "Documenti cantiere", "intest": ["Cantiere", "Documento", "Presente", "Scadenza"], "righe": [[d["Cantiere"], d["Documento"], "Sì" if d["Presente"] else "No", d["Scadenza"]] for d in out["documenti"]]}])
    return pdf, x, ctx["report_id"]


# ----------------------------------------------------------------------------- MEZZI
def report_mz(out, mezzi, nome=""):
    k, q = out["kpi"], out["params"]
    ctx = rep_gen.costruisci_ctx("Parco mezzi e attrezzature", "Costi e scadenze", nome, {"k": k, "n": nome, "o": str(q["oggi"])})
    det = out["mezzi"]
    sez = [{"titolo": "Costi e utilizzo dei mezzi", "tabella": (["Mezzo", "Tariffa €/h", "Ore 12 mesi", "Utilizzo", "Costo imputato", "Fissi non assorbiti", "Stato"],
                                                               [(d["Mezzo"][:24], N(d["Tariffa oraria"], 1), N(d["Ore 12 mesi"]), N(d["Utilizzo %"], 0) + "%", N(d["Costo imputato"]), N(d["Fissi non assorbiti"]), ST[d["Stato"]]) for d in det])}]
    if det:
        sez.append({"titolo": "Costo imputato e non assorbito", "grafico": png(charts.fig_mz_costi(det, "light"))})
    sez.append({"titolo": "Costo dei mezzi per commessa", "tabella": (["Commessa", "Ore", "Costo mezzi"], [(c["Commessa"][:30], N(c["Ore"]), N(c["Costo mezzi"])) for c in out["commesse"]]), "pagina": True})
    sez.append({"titolo": "Scadenze", "tabella": (["Mezzo", "Scadenza di", "Data", "Giorni", "Stato"], [(d["Mezzo"][:24], d["Documento"][:26], fd(d["Scadenza"]), str(d["Giorni"]), STD[d["Stato"]]) for d in out["scadenze"] if d["Stato"] in ("bad", "warn")])})
    sez.append({"titolo": "Punti di attenzione", "testo": ["- " + a for a in _finale(out, "")]})
    sez.append({"titolo": "Metodo e limiti", "testo": ["Tariffa oraria = costi fissi annui / ore annue previste + costo variabile orario. Il costo imputato alle commesse è ore x tariffa (ultimi 12 mesi); "
                                                       "i costi fissi non assorbiti sono la parte dei fissi non coperta perché il mezzo è usato meno del previsto. Le tariffe dipendono dai costi e dalle ore che inserisci."]})
    pdf = rep_gen.genera_pdf(ctx, "Parco mezzi e attrezzature", "Costi e scadenze", f"Situazione al {q['oggi'].strftime('%d/%m/%Y')}", [("MEZZI", str(k["n_mezzi"])), ("ORE 12 MESI", N(k["ore_12m"]))],
                             [("Costo imputato", EUR(k["costo_imputato"]), "alle commesse, 12 mesi", "info"), ("Fissi non assorbiti", EUR(k["fissi_non_assorbiti"]), f"{k['sottoutilizzati']} mezzi sottoutilizzati", "warn" if k["fissi_non_assorbiti"] > 0 else "ok"),
                              ("Scadenze scadute", str(k["scad_scadute"]), "revisioni e assicurazioni", "bad" if k["scad_scadute"] else "ok"), ("In arrivo", str(k["scad_in_arrivo"]), "entro il preavviso", "warn" if k["scad_in_arrivo"] else "ok")],
                             _esito(k["n_bad"], k["n_warn"], max(1, k["n_mezzi"]), "mezzi"), sez)
    mi = {m["Mezzo"]: m for m in mezzi}
    righe = []
    for d in det:
        m = mi[d["Mezzo"]]
        righe.append([d["Mezzo"], m["Costo_fisso_annuo"], m["Costo_var_orario"], m["Ore_annue_prev"], "=B{r}/D{r}+C{r}", d["Ore 12 mesi"], "=E{r}*F{r}", "=IF(D{r}=0,0,F{r}/D{r}*100)", "=B{r}*MAX(0,1-F{r}/D{r})"])
    x = rep_gen.genera_excel([{"nome": "Mezzi", "intest": ["Mezzo", "Fissi annui", "Variabile €/h", "Ore previste", "Tariffa €/h", "Ore 12 mesi", "Costo imputato", "Utilizzo %", "Fissi non assorbiti"],
                               "righe": righe, "totali": [1, 5, 6, 8], "formati": {2: "pct", 4: "pct", 7: "pct"}},
                              {"nome": "Utilizzo", "intest": ["Mezzo", "Commessa", "Data", "Ore", "Tariffa €/h", "Costo"], "righe": [[u["Mezzo"], u["Commessa"], u["Data"], u["Ore"], u["Tariffa"], "=D{r}*E{r}"] for u in out["uso"]], "formati": {4: "pct"}},
                              {"nome": "Scadenze", "intest": ["Mezzo", "Scadenza di", "Data", "Giorni", "Stato"], "righe": [[d["Mezzo"], d["Documento"], d["Scadenza"], d["Giorni"], STD[d["Stato"]]] for d in out["scadenze"]]}])
    return pdf, x, ctx["report_id"]


# ----------------------------------------------------------------------------- ORGANICO
def report_og(out, ris, ass, nome=""):
    k, q = out["kpi"], out["params"]
    ctx = rep_gen.costruisci_ctx("Organico e carico di lavoro", "Capacità e assegnazioni", nome, {"k": k, "n": nome, "o": str(q["oggi"])})
    mesi = out["mesi"]
    lab = [m["Mese"] for m in mesi]
    sez = [{"titolo": "Carico mese per mese", "grafico": png(charts.fig_og_carico(mesi, "light")),
            "tabella": (["Mese", "Capacità", "Assegnate", "Saturaz.", "Ore extra", "Ore libere", "Costo assegnato", "Stato"],
                        [(m["Mese"], N(m["Capacità ore"]), N(m["Ore assegnate"]), N(m["Saturazione %"], 0) + "%", N(m["Ore extra necessarie"]), N(m["Ore libere"]), N(m["Costo assegnato"]), ST[m["Stato"]]) for m in mesi])},
           {"titolo": "Saturazione per risorsa (%)", "pagina": True, "tabella": (["Risorsa", "Ruolo"] + lab[:6] + ["Picco"], [(r["Risorsa"][:18], r["Ruolo"][:12]) + tuple(str(r[m]) for m in lab[:6]) + (N(r["Picco %"], 0) + "%",) for r in out["risorse"]])},
           {"titolo": "Costo del personale per commessa (€)", "tabella": (["Commessa"] + lab[:6] + ["Totale"], [(c["Commessa"][:22],) + tuple(N(c[m]) for m in lab[:6]) + (N(c["Totale"]),) for c in out["commesse"]])},
           {"titolo": "Punti di attenzione", "testo": ["- " + a for a in _finale(out, "")]},
           {"titolo": "Metodo e limiti", "testo": ["Ogni assegnazione pesa con le sue ore mensili in tutti i mesi tra Dal e Al. Saturazione = ore assegnate / ore disponibili. «Ore extra» = ore oltre la capacità di una risorsa; "
                                                "«ore libere» = capacità non assegnata. Il costo delle ore inattive è una stima con il costo orario inserito. Non tiene conto di ferie, malattie e straordinari."]}]
    pdf = rep_gen.genera_pdf(ctx, "Organico e carico di lavoro", "Capacità e assegnazioni", f"Previsione dal {q['oggi'].strftime('%d/%m/%Y')} per {q['mesi']} mesi", [("RISORSE", str(k["n_risorse"])), ("MESI", str(q["mesi"]))],
                             [("Saturazione media", N(k["saturazione_media"], 0) + "%", f"picco {N(k['picco_saturazione'], 0)}%", "info"), ("Mesi in sovraccarico", str(k["mesi_sovraccarico"]), f"{N(k['ore_extra_picco'])} ore extra al picco", "bad" if k["mesi_sovraccarico"] else "ok"),
                              ("Mesi con poco lavoro", str(k["mesi_scarico"]), "sotto la saturazione minima", "warn" if k["mesi_scarico"] else "ok"), ("Costo ore inattive", EUR(k["costo_inattivo"]), "stima sul periodo", "warn" if k["costo_inattivo"] > 0 else "ok")],
                             _esito(k["mesi_sovraccarico"], k["mesi_scarico"], max(1, q["mesi"]), "mesi"), sez)
    righe_m = [[m["Mese"], m["Capacità ore"], m["Ore assegnate"], "=IF(B{r}=0,0,C{r}/B{r}*100)", m["Ore extra necessarie"], m["Ore libere"], m["Costo assegnato"], m["Costo ore inattive"]] for m in mesi]
    x = rep_gen.genera_excel([{"nome": "Carico mensile", "intest": ["Mese", "Capacità ore", "Ore assegnate", "Saturazione %", "Ore extra", "Ore libere", "Costo assegnato", "Costo ore inattive"], "righe": righe_m, "totali": [1, 2, 4, 5, 6, 7], "formati": {3: "pct"}},
                              {"nome": "Risorse", "intest": ["Risorsa", "Ruolo", "Costo orario", "Ore al mese"], "righe": [[r["Risorsa"], r["Ruolo"], r["Costo_orario"], r["Ore_mese"]] for r in ris]},
                              {"nome": "Assegnazioni", "intest": ["Risorsa", "Commessa", "Dal", "Al", "Ore al mese"], "righe": [[a["Risorsa"], a["Commessa"], a["Dal"], a["Al"] or None, a["Ore_mese"]] for a in ass]}])
    return pdf, x, ctx["report_id"]


# ----------------------------------------------------------------------------- RAPPORTINI
def report_rp(out, rapp, segn, nome=""):
    k, q = out["kpi"], out["params"]
    ctx = rep_gen.costruisci_ctx("Rapportini di cantiere", "Giornale e segnalazioni", nome, {"k": k, "n": nome, "o": str(q["oggi"])})
    cant, seg = out["cantieri"], out["segnalazioni"]
    ultimi = sorted(rapp, key=lambda r: r["Data"], reverse=True)[:25]
    sez = []
    if cant:
        sez.append({"titolo": "Situazione dei cantieri", "grafico": png(charts.fig_rp_ore(cant, "light")),
                    "tabella": (["Cantiere", "Ultimo rapp.", "Gg senza", "Rapp.", "Ore", "Pres. medie", "Segn. aperte", "Stato"],
                                [(c["Cantiere"][:22], fd(c["Ultimo rapportino"]), str(c["Giorni lavorativi senza rapportino"]), str(c["Rapportini"]), N(c["Ore"], 0), N(c["Presenze medie"], 1),
                                  str(c["Segnalazioni aperte"]), ST[c["Stato"]]) for c in cant])})
    if seg:
        sez.append({"titolo": "Segnalazioni aperte", "pagina": True,
                    "tabella": (["Data", "Cantiere", "Tipo", "Gravità", "Descrizione", "Resp.", "Scadenza", "Stato"],
                                [(fd(s["Data"]), s["Cantiere"][:16], s["Tipo"][:14], s["Gravita"], s["Descrizione"][:44], s["Responsabile"][:12], fd(s["Scadenza"]), s["Stato"]) for s in seg])})
    if ultimi:
        sez.append({"titolo": "Ultimi rapportini", "tabella": (["Data", "Cantiere", "Compilato da", "Meteo", "Pres.", "Ore", "Lavorazioni"],
                                                              [(fd(r["Data"]), r["Cantiere"][:16], r["Compilato_da"][:12], r["Meteo"][:10], N(r["Presenti"], 0), N(r["Ore"], 0), r["Lavorazioni"][:48]) for r in ultimi])})
    sez.append({"titolo": "Punti di attenzione", "testo": ["- " + a for a in _finale(out, "")]})
    sez.append({"titolo": "Metodo e limiti", "testo": ["Un cantiere risulta «in ritardo» quando non ha rapportini da più di %d giorni lavorativi (lun-ven; i festivi non sono esclusi), «critico» oltre il doppio. "
                                                        "Sono considerati attivi i cantieri con un rapportino negli ultimi %d giorni. Le ore sono il totale dichiarato dal capocantiere." % (q["giorni_senza_rapporto"], q["finestra_gg"])]})
    n_bad, n_warn = sum(1 for c in cant if c["Stato"] == "bad") + k["segn_alte"], sum(1 for c in cant if c["Stato"] == "warn") + k["segn_in_scadenza"]
    pdf = rep_gen.genera_pdf(ctx, "Rapportini di cantiere", "Giornale e segnalazioni", f"Situazione al {q['oggi'].strftime('%d/%m/%Y')} (ultimi {q['finestra_gg']} giorni)",
                             [("CANTIERI", str(k["cantieri_attivi"])), ("RAPPORTINI", str(k["rapportini"]))],
                             [("Rapportini", str(k["rapportini"]), f"{N(k['ore'], 0)} ore lavorate", "info"),
                              ("Cantieri senza rapportino", str(k["cantieri_senza_rapporto"]), "oltre la soglia di giorni", "warn" if k["cantieri_senza_rapporto"] else "ok"),
                              ("Segnalazioni aperte", str(k["segn_aperte"]), f"{k['segn_alte']} di gravità alta", "bad" if k["segn_alte"] else ("warn" if k["segn_aperte"] else "ok")),
                              ("Segnalazioni scadute", str(k["segn_scadute"]), f"{k['segn_in_scadenza']} in scadenza", "bad" if k["segn_scadute"] else "ok")],
                             _esito(n_bad, n_warn, max(1, k["cantieri_attivi"] + k["segn_aperte"]), "Cantieri e segnalazioni"), sez)
    x = rep_gen.genera_excel([{"nome": "Rapportini", "intest": ["Data", "Cantiere", "Compilato da", "Meteo", "Persone presenti", "Ore lavorate", "Lavorazioni", "Mezzi", "Note"],
                               "righe": [[r["Data"], r["Cantiere"], r["Compilato_da"], r["Meteo"], r["Presenti"], r["Ore"], r["Lavorazioni"], r["Mezzi"], r["Note"]] for r in sorted(rapp, key=lambda r: r["Data"])],
                               "totali": [4, 5]},
                              {"nome": "Segnalazioni", "intest": ["Data", "Cantiere", "Tipo", "Gravità", "Descrizione", "Responsabile", "Scadenza", "Stato"],
                               "righe": [[s["Data"], s["Cantiere"], s["Tipo"], s["Gravita"], s["Descrizione"], s["Responsabile"], s["Scadenza"], s["Stato"]] for s in segn]}])
    return pdf, x, ctx["report_id"]


# ----------------------------------------------------------------------------- CRONOPROGRAMMA
def report_gt(out, nome=""):
    k, q = out["kpi"], out["params"]
    ctx = rep_gen.costruisci_ctx("Cronoprogramma dei cantieri", "Gantt e ritardi", nome, {"k": k, "n": nome, "o": str(q["oggi"])})
    com, fasi = out["commesse"], out["fasi"]
    stn = {"ok": "Nei tempi", "warn": "In ritardo", "bad": "CRITICA", "done": "Completata", "wait": "Da iniziare"}
    sez = [{"titolo": "Diagramma di Gantt", "grafico": png(charts.fig_gt(out, "light"))},
           {"titolo": "Cantieri", "tabella": (["Cantiere", "Inizio", "Fine prev.", "Avanz.", "Previsto", "Fine stimata", "Ritardo gg", "Stato"],
                                              [(c["Commessa"][:22], fd(c["Inizio"]), fd(c["Fine"]), N(c["Avanzamento"], 0) + "%", N(c["Prevista"], 0) + "%", fd(c["Fine stimata"]), str(c["Ritardo gg"]), stn[c["Stato"]]) for c in com])},
           {"titolo": "Fasi", "pagina": True, "tabella": (["Cantiere", "Fase", "Inizio", "Fine", "Avanz.", "Previsto", "Scost.", "Stato"],
                                                          [(f["Commessa"][:16], f["Fase"][:22], fd(f["Inizio"]), fd(f["Fine"]), N(f["Avanzamento"], 0) + "%", N(f["Prevista"], 0) + "%", N(f["Scostamento"], 0), stn[f["Stato"]]) for f in fasi])},
           {"titolo": "Punti di attenzione", "testo": ["- " + a for a in _finale(out, "")]},
           {"titolo": "Metodo e limiti", "testo": ["Avanzamento previsto = quota di durata trascorsa (lineare tra inizio e fine). Una fase è «in ritardo» se l'avanzamento reale è sotto il previsto di oltre %d punti, «critica» oltre il doppio o se ha superato la fine "
                                                "senza essere completata. Fine stimata = inizio + durata / ritmo reale (ritmo limitato tra 0,34 e 1). Le fasi legate dalla colonna «Parte dopo la fase» slittano a catena se quelle precedenti finiscono più tardi; non sono modellati i calendari di lavoro (ferie, maltempo)." % q["soglia_pct"]]}]
    pdf = rep_gen.genera_pdf(ctx, "Cronoprogramma dei cantieri", "Gantt e ritardi", f"Situazione al {q['oggi'].strftime('%d/%m/%Y')}", [("CANTIERI", str(k["commesse"])), ("FASI", str(k["fasi"]))],
                             [("Cantieri in ritardo", str(k["commesse_in_ritardo"]), f"su {k['commesse']}", "bad" if k["commesse_in_ritardo"] else "ok"), ("Fasi in ritardo", str(k["fasi_in_ritardo"]), f"{k['fasi_critiche']} critiche", "bad" if k["fasi_critiche"] else ("warn" if k["fasi_in_ritardo"] else "ok")),
                              ("Ritardo massimo", f"{k['ritardo_max_gg']} gg", "stima sulla fine prevista", "warn" if k["ritardo_max_gg"] else "ok"), ("Fasi in scadenza", str(k["fasi_in_scadenza"]), f"entro {q['preavviso_gg']} giorni", "warn" if k["fasi_in_scadenza"] else "ok")],
                             _esito(k["fasi_critiche"], k["fasi_in_ritardo"] - k["fasi_critiche"], max(1, k["fasi"]), "Fasi"), sez)
    x = rep_gen.genera_excel([{"nome": "Fasi", "intest": ["Cantiere", "Fase", "Inizio", "Fine", "Avanzamento %", "Previsto %", "Scostamento", "Fine stimata", "Responsabile", "Parte dopo", "Inizio stimato", "Slitta (gg)", "Giorni di fermo", "Perché"],
                               "righe": [[f["Commessa"], f["Fase"], f["Inizio"], f["Fine"], f["Avanzamento"], f["Prevista"], "=E{r}-F{r}", f["Fine stimata"], f["Responsabile"], "; ".join(f["Predecessori"]), f["Inizio stimato"], f["Slitta gg"], f["Giorni di fermo"], f["Motivo"]] for f in fasi]},
                              {"nome": "Cantieri", "intest": ["Cantiere", "Inizio", "Fine prevista", "Avanzamento %", "Previsto %", "Fine stimata", "Ritardo gg", "Fasi"],
                               "righe": [[c["Commessa"], c["Inizio"], c["Fine"], c["Avanzamento"], c["Prevista"], c["Fine stimata"], c["Ritardo gg"], c["Fasi"]] for c in com]}])
    return pdf, x, ctx["report_id"]


# ----------------------------------------------------------------------------- DOSSIER GENERICO (Rubrica, Studio legale, Banca, Ordini)
def report_generico(titolo, sotto, nome, oggi, meta, tiles, esito, sezioni, fogli, firma):
    """Dossier PDF + Excel costruito dal modulo stesso: sezioni = [{"titolo","testo","tabella":(intest,righe)}], fogli = fogli per genera_excel."""
    ctx = rep_gen.costruisci_ctx(titolo, sotto, nome, {"f": firma, "n": nome, "o": str(oggi)})
    pdf = rep_gen.genera_pdf(ctx, titolo, sotto, f"Situazione al {oggi.strftime('%d/%m/%Y')}", meta, tiles, esito, sezioni)
    return pdf, rep_gen.genera_excel(fogli), ctx["report_id"]
