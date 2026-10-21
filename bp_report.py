"""
bp_report.py - Dossier PDF del Business Plan Studio (stesso stile del report di credito).
"""
import os
import re
import time

import charts
import core
from bp import confronto_scenari as bp_confronto
from core import DISCLAIMER, LOGO_FCR_PATH, LOGO_PATH, PRIVACY_PUNTI, fmt_num, fmt_x
from pdf_report import (
    BLU, BORDO, CHIARO, GIALLO_B, GRIGIO, NAVY, NL, ROSSO_B, TESTO, TRICOLORE, VERDE_B, _PDF, _strumenti, pdf_safe,
)

ETICHETTE_ASSUNZIONI = [
    ("ricavi_y1", "Ricavi anno 1", "eur"), ("crescita", "Crescita annua dei ricavi (dal 2° anno)", "pct"),
    ("cv_pct", "Costi variabili (% dei ricavi)", "pct"), ("personale", "Costo del personale annuo (anno 1)", "eur"),
    ("infl_personale", "Aumento annuo del personale", "pct"), ("costi_fissi", "Altri costi fissi e servizi", "eur"),
    ("capex", "Investimento iniziale (CAPEX)", "eur"), ("anni_amm", "Anni di ammortamento", "n"),
    ("mutuo", "Finanziamento bancario", "eur"), ("tasso", "Tasso d'interesse annuo", "pct"),
    ("durata", "Durata del finanziamento (anni)", "n"), ("equity", "Mezzi propri apportati", "eur"),
    ("ccn_pct", "Capitale circolante (% sulla variazione ricavi)", "pct"),
]


def costruisci_ctx_bp(out, nome, descrizione="", modello="nessuno"):
    firma = {"p": out["params"], "nome": nome, "modello": modello}
    return {
        "bp": out, "nome": nome or "", "descrizione": descrizione or "", "modello": modello,
        "report_id": core.hash_payload(firma, 10).upper(), "generato_il": time.strftime("%d/%m/%Y %H:%M"),
        "pratica": nome or "",
        "header_titolo": "FCR GENERAL CONTRACTOR - Business Plan Studio",
        "header_sub": "Dossier del business plan | Iniziativa: " + (nome or "non indicata"),
    }


def grafici_bp(out):
    a, k = out["anni"], out["kpi"]
    scen = out.get("scenari")
    return {
        "scenari": charts.fig_png(charts.fig_bp_scenari(scen, "light")) if scen else None,
        "tornado": charts.fig_png(charts.fig_tornado(out["sensibilita"], out.get("sens_metrica", ""), "light")) if out.get("sensibilita") else None,
        "economico": charts.fig_png(charts.fig_bp_economico(a, "light")),
        "finanza": charts.fig_png(charts.fig_bp_finanza(a, k["cassa_iniziale"], "light")),
        "mutuo": charts.fig_png(charts.fig_bp_mutuo(out["mutuo"], "light")) if out["params"]["mutuo"] > 0 else None,
        "dscr": charts.fig_png(charts.fig_dscr(a, None, 1.2, "light")) if k["dscr_min"] is not None else None,
    }


def _v(x, tipo):
    if tipo == "eur":
        return fmt_num(x) + " EUR"
    if tipo == "pct":
        return fmt_num(x, 1) + "%"
    return str(int(x))


def genera_pdf_bp(ctx, relazione="", grafici=None):
    out = ctx["bp"]
    q, anni, k = out["params"], out["anni"], out["kpi"]
    n = len(anni)
    grafici = grafici if grafici is not None else grafici_bp(out)
    pdf = _PDF(ctx)
    T = _strumenti(pdf, grafici)
    spazio, sezione, sottotitolo, paragrafo = T.spazio, T.sezione, T.sottotitolo, T.paragrafo
    tabella, tile, immagine = T.tabella, T.tile, T.immagine
    cont = [0]

    def prossima():
        cont[0] += 1
        return cont[0]

    w_anno = {3: 36, 4: 30, 5: 26}[n]
    larghezze = [186 - n * w_anno] + [w_anno] * n
    allin = ["L"] + ["R"] * n

    # =============================== COPERTINA ====================================
    pdf.add_page()
    for i, c in enumerate(TRICOLORE):
        pdf.set_fill_color(*c)
        pdf.set_draw_color(*BORDO)
        pdf.rect(i * 70, 0, 70, 4, style="DF" if c == (255, 255, 255) else "F")
    if os.path.exists(LOGO_FCR_PATH):
        try:
            pdf.image(LOGO_FCR_PATH, 14, 16, 46)
        except Exception:
            pass
    pdf.set_xy(66, 24)
    pdf.set_font("Helvetica", "B", 23)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 10, "FCR GENERAL CONTRACTOR")
    pdf.set_xy(66, 36)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*BLU)
    pdf.cell(0, 7, "Business Plan Studio")
    pdf.set_xy(66, 44)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRIGIO)
    pdf.cell(0, 5, "FINANCE  -  CONSTRUCTION  -  RENEWABLES")
    pdf.set_draw_color(*NAVY)
    pdf.set_line_width(0.6)
    pdf.line(14, 66, 196, 66)

    pdf.set_xy(14, 74)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*GRIGIO)
    pdf.cell(0, 5, "DOSSIER DEL BUSINESS PLAN")
    pdf.set_xy(14, 81)
    pdf.set_font("Helvetica", "B", 21)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 10, "Piano Economico-Finanziario")
    pdf.set_xy(14, 93)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(*TESTO)
    pdf.cell(0, 6, pdf_safe("Iniziativa: " + (ctx.get("nome") or "non indicata")))

    pdf.set_fill_color(*CHIARO)
    pdf.set_draw_color(*BORDO)
    pdf.set_line_width(0.25)
    pdf.rect(14, 106, 182, 22, style="DF", round_corners=True, corner_radius=2.5)
    info = [("DATA", ctx["generato_il"]), ("ID REPORT", ctx["report_id"]),
            ("ORIZZONTE", f"{n} anni ({anni[0]['AnnoNum']}-{anni[-1]['AnnoNum']})"), ("MODELLO AI", str(ctx["modello"])[:22])]
    for i, (lab, val) in enumerate(info):
        x = 18 + i * 45
        pdf.set_xy(x, 111)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*GRIGIO)
        pdf.cell(42, 4, lab)
        pdf.set_xy(x, 117)
        pdf.set_font("Helvetica", "B", 10.5)
        pdf.set_text_color(*NAVY)
        pdf.cell(42, 6, pdf_safe(val))

    # esito sintetico: sostenibile / da verificare
    critico = any("cassa scende" in a or "DSCR minimo" in a and (k["dscr_min"] or 9) < 1.0 for a in out["avvisi"])
    colore = ROSSO_B if critico else (GIALLO_B if out["avvisi"] else VERDE_B)
    titolo_esito = "PUNTI CRITICI DA RISOLVERE" if critico else ("SOSTENIBILE CON ATTENZIONI" if out["avvisi"] else "PIANO SOSTENIBILE")
    pdf.set_fill_color(*colore)
    pdf.rect(14, 138, 182, 36, style="F", round_corners=True, corner_radius=3)
    pdf.set_xy(20, 144)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(120, 4, "ESITO DEI CONTROLLI AUTOMATICI SUL PIANO")
    pdf.set_xy(20, 150)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(130, 12, titolo_esito)
    pdf.set_xy(20, 164)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(130, 5, pdf_safe(f"{len(out['avvisi'])} punti di attenzione" if out["avvisi"] else "Nessun avviso"))
    pdf.set_xy(140, 144)
    pdf.set_font("Helvetica", "B", 28)
    pdf.cell(50, 16, f"{anni[-1]['AnnoNum']}", align="R")
    pdf.set_xy(140, 161)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(50, 4, "ultimo anno di piano", align="R")

    ult = anni[-1]
    tiles = [
        (f"Ricavi {ult['AnnoNum']}", fmt_num(ult["Ricavi"]) + " EUR", f"da {fmt_num(anni[0]['Ricavi'])} EUR nel primo anno", BLU),
        (f"EBITDA {ult['AnnoNum']}", fmt_num(ult["EBITDA"]) + " EUR", f"margine {fmt_num(ult['Margine EBITDA %'], 1)}%", VERDE_B),
        ("DSCR minimo", fmt_x(k["dscr_min"]) if k["dscr_min"] is not None else "n.d.", "target indicativo >= 1,20x",
         VERDE_B if (k["dscr_min"] or 9) >= 1.2 else (GIALLO_B if (k["dscr_min"] or 9) >= 1.0 else ROSSO_B)),
        ("Payback", (fmt_num(k["payback_anni"], 1) + " anni") if k["payback_anni"] is not None else "oltre il piano",
         "rientro dell'investimento", BLU),
    ]
    for i, (lab, val, sub, rgb) in enumerate(tiles):
        tile(14 + i * 46, 184, 43.5, 28, lab, val, sub, rgb)

    # piede di copertina
    pdf.set_draw_color(*BORDO)
    pdf.set_line_width(0.3)
    pdf.line(14, 262, 196, 262)
    pdf.set_xy(14, 265)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*NAVY)
    pdf.cell(130, 4, "DOCUMENTO RISERVATO - USO INTERNO")
    pdf.set_xy(14, 270)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*GRIGIO)
    pdf.multi_cell(130, 3.4, pdf_safe("Proiezione basata su ipotesi dell'utente: non costituisce garanzia di risultato, parere di merito creditizio ne' consulenza finanziaria."), **NL)
    pdf.set_xy(138, 270)
    pdf.set_font("Helvetica", "", 7)
    pdf.cell(30, 4, "Powered by", align="R")
    if os.path.exists(LOGO_PATH):
        try:
            pdf.image(LOGO_PATH, 170, 258, 26)
        except Exception:
            pass

    # ================================ CONTENUTO ===================================
    pdf.add_page()
    sezione("Sintesi dell'iniziativa e ipotesi", prossima(), 90)
    if ctx.get("descrizione"):
        paragrafo(ctx["descrizione"], 9.2, TESTO, 4.9)
        pdf.ln(2)
    righe_ip = [(et, _v(q[ch], tp)) for ch, et, tp in ETICHETTE_ASSUNZIONI]
    if q["fisco"] == "semplice":
        righe_ip.append(("Imposte (aliquota unica, senza riporto perdite)", _v(q["aliquota"], "pct")))
    else:
        righe_ip += [("IRES", _v(q["ires"], "pct")), ("IRAP", _v(q["irap"], "pct") + f" (personale deducibile {fmt_num(q['irap_ded_pers'], 0)}%)"),
                     ("Riporto perdite fiscali", "si' (max 80% del reddito)" if q["riporto"] else "no")]
    tabella(["Ipotesi", "Valore"], righe_ip, [126, 60], ["L", "R"])
    tabella(["Fonti e impieghi iniziali", "Importo"], [
        ("Investimento iniziale (CAPEX)", fmt_num(q["capex"]) + " EUR"),
        ("Finanziamento bancario", fmt_num(q["mutuo"]) + " EUR"),
        ("Mezzi propri", fmt_num(q["equity"]) + " EUR"),
        ("Copertura / (fabbisogno) iniziale", fmt_num(0.0 if abs(k["gap_fonti"]) < 0.5 else -k["gap_fonti"]) + " EUR"),
    ], [126, 60], ["L", "R"])

    sezione("Conto economico previsionale", prossima(), 100)
    voci_ce = [("Ricavi delle vendite", "Ricavi", 1), ("Costi variabili", "Costi variabili", -1), ("Costo del personale", "Personale", -1),
               ("Altri costi operativi", "Altri costi", -1), ("EBITDA", "EBITDA", 1), ("Ammortamenti", "Ammortamenti", -1),
               ("EBIT", "EBIT", 1), ("Interessi passivi", "Interessi", -1), ("Utile ante imposte", "Utile ante imposte", 1),
               ("di cui IRES", "IRES", -1), ("di cui IRAP", "IRAP", -1),
               ("Imposte", "Imposte", -1), ("Utile netto", "Utile netto", 1)]
    if q["fisco"] == "semplice":
        voci_ce = [v for v in voci_ce if v[1] not in ("IRES", "IRAP")]
    righe = [(et, *[fmt_num(sg * r[ch]) for r in anni]) for et, ch, sg in voci_ce]
    righe.insert(5, ("Margine EBITDA %", *[fmt_num(r["Margine EBITDA %"], 1) + "%" for r in anni]))
    tabella(["Voce (EUR)"] + [str(r["AnnoNum"]) for r in anni], righe, larghezze, allin)
    immagine("economico", 150)

    sezione("Cash flow e posizione finanziaria", prossima(), 95)
    voci_cf = [("EBITDA", "EBITDA", 1), ("Imposte", "Imposte", -1), ("Variazione capitale circolante", "Variazione CCN", -1),
               ("Flusso operativo (FCF)", "FCF operativo", 1), ("Interessi", "Interessi", -1),
               ("Rimborso quota capitale", "Quota capitale", -1), ("Flusso netto dell'anno", "Flusso netto", 1),
               ("Cassa di fine anno", "Cassa finale", 1), ("Debito residuo", "Debito residuo", 1), ("PFN", "PFN", 1)]
    righe = [(et, *[fmt_num(sg * r[ch]) for r in anni]) for et, ch, sg in voci_cf]
    righe.append(("DSCR", *[fmt_x(r["DSCR"]) if r["DSCR"] is not None else "n.d." for r in anni]))
    tabella(["Voce (EUR)"] + [str(r["AnnoNum"]) for r in anni], righe, larghezze, allin)
    paragrafo(f"Cassa iniziale (dopo investimento, finanziamento e mezzi propri): {fmt_num(k['cassa_iniziale'])} EUR. "
              f"Cassa minima nel periodo: {fmt_num(k['cassa_minima'])} EUR.", 8.5, GRIGIO)
    pdf.ln(1)
    immagine("finanza", 150)
    if grafici.get("dscr"):
        immagine("dscr", 150)

    if q["mutuo"] > 0:
        sezione("Finanziamento e piano di ammortamento", prossima(), 90)
        paragrafo(f"Finanziamento di {fmt_num(q['mutuo'])} EUR al {fmt_num(q['tasso'], 2)}% su {int(q['durata'])} anni, "
                  f"rate annuali con ammortamento {q['tipo_rata']}. Interessi totali: {fmt_num(k['interessi_tot'])} EUR.", 9)
        pdf.ln(1.5)
        tabella(["Anno", "Quota capitale", "Interessi", "Rata", "Debito residuo"],
                [(str(r["Anno"]), fmt_num(r["Quota capitale"]), fmt_num(r["Interessi"]), fmt_num(r["Rata"]), fmt_num(r["Debito residuo"]))
                 for r in out["mutuo"]], [26, 40, 40, 40, 40], ["L", "R", "R", "R", "R"])
        immagine("mutuo", 150)

    if out.get("scenari"):
        sezione("Scenari e analisi di sensibilita'", prossima(), 100)
        paragrafo("Gli scenari applicano scostamenti prudenziali e favorevoli alle ipotesi base (valori modificabili dall'utente). "
                  "La sensibilita' mostra di quanto cambia la metrica variando una sola ipotesi per volta.", 8.8)
        pdf.ln(1.5)
        conf = bp_confronto(out["scenari"])
        tabella(["Scenario", "EBITDA ult. anno", "Utile cum.", "Cassa min.", "DSCR min", "Payback"],
                [(c["Scenario"], fmt_num(c["EBITDA ultimo anno"]), fmt_num(c["Utile netto cumulato"]), fmt_num(c["Cassa minima"]),
                  fmt_x(c["DSCR minimo"]) if c["DSCR minimo"] is not None else "n.d.",
                  (fmt_num(c["Payback (anni)"], 1) + " anni") if c["Payback (anni)"] is not None else "oltre")
                 for c in conf], [34, 33, 31, 31, 24, 33], ["L", "R", "R", "R", "R", "R"])
        immagine("scenari", 150)
        if grafici.get("tornado"):
            immagine("tornado", 150)

    sezione("Punti di attenzione", prossima(), 40)
    if out["avvisi"]:
        for a in out["avvisi"]:
            paragrafo("- " + a, 9, TESTO, 4.9)
    else:
        paragrafo("I controlli automatici non hanno rilevato criticita' (cassa sempre positiva, DSCR adeguato, fonti coerenti con l'investimento).", 9)
    pdf.ln(2)

    if relazione:
        sezione("Relazione strategica", prossima())
        for riga in relazione.split("\n"):
            t = riga.strip()
            if not t:
                pdf.ln(2)
                continue
            if re.match(r"^\d+[\.\)]\s+\S", t) and len(t) <= 95:
                spazio(20)
                pdf.ln(1.5)
                paragrafo(t, 10, NAVY, 5.5, "B")
            else:
                paragrafo(t, 9.2, TESTO, 4.9)
        pdf.ln(2)

    sezione("Metodologia e limiti", prossima(), 70)
    paragrafo("Ricavi(t) = Ricavi(1) x (1 + crescita)^(t-1). EBITDA = ricavi - costi variabili - personale - altri costi fissi. "
              "Gli interessi derivano dal piano di ammortamento del finanziamento (rate annuali). Le imposte seguono il modello scelto: "
              "\"dettagliato\" = IRES sul reddito (al netto delle perdite pregresse, utilizzabili fino all'80% del reddito) piu' IRAP su EBIT + "
              "personale non deducibile (dovuta anche in perdita civilistica); \"semplice\" = aliquota unica sugli utili positivi. "
              "Il reddito imponibile e' assunto pari all'utile ante imposte: variazioni fiscali (indeducibilita', ACE, super-ammortamenti, "
              "interessi passivi eccedenti il 30% del ROL, regime dei contributi) non sono modellate e vanno verificate dal commercialista. La variazione del capitale circolante e' "
              "una percentuale della variazione dei ricavi (nel primo anno, dei ricavi). Flusso operativo = EBITDA - imposte - variazione CCN; "
              "DSCR = flusso operativo / (interessi + quota capitale); PFN = debito residuo - cassa.", 8.5)
    pdf.ln(1.5)
    paragrafo("Limiti: il modello e' semplificato (anni solari interi, un solo finanziamento, nessuna stagionalita', IVA, "
              "contributi, valore residuo). Ogni ipotesi e' definita dall'utente e va validata con dati di mercato.", 8.5)

    sezione("Informativa sulla privacy e avvertenze", prossima(), 70)
    for titolo_p, testo_p in PRIVACY_PUNTI:
        spazio(16)
        paragrafo(titolo_p, 8.6, NAVY, 4.6, "B")
        paragrafo(testo_p, 8, TESTO, 4.0)
        pdf.ln(0.8)
    spazio(26)
    y0 = pdf.get_y()
    pdf.set_fill_color(*CHIARO)
    pdf.set_draw_color(*BORDO)
    pdf.set_line_width(0.25)
    pdf.set_font("Helvetica", "I", 8)
    righe_av = pdf.multi_cell(178, 4.1, pdf_safe("Avvertenza: " + DISCLAIMER), dry_run=True, output="LINES")
    pdf.rect(12, y0, 186, 4.1 * len(righe_av) + 6, style="DF", round_corners=True, corner_radius=2)
    pdf.set_xy(16, y0 + 3)
    pdf.set_text_color(*GRIGIO)
    pdf.multi_cell(178, 4.1, pdf_safe("Avvertenza: " + DISCLAIMER), **NL)
    return bytes(pdf.output())
