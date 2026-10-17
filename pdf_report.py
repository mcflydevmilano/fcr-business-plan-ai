"""
pdf_report.py - Report PDF in stile istituzionale: copertina con logo, intestazioni, tabelle colorate,
segnalibri, numeri di pagina, metodologia e informativa privacy.
"""
import io
import os
import re

from fpdf import FPDF
from fpdf.enums import XPos, YPos

import core
from core import (
    CLASSI, DISCLAIMER, LOGO_FCR_PATH, LOGO_PATH, PRIVACY_PUNTI, fmt_eur, fmt_num, fmt_pct, fmt_x, ratio,
)

NAVY = (10, 45, 90)
BLU = (37, 99, 235)
GRIGIO = (100, 116, 139)
TESTO = (30, 41, 59)
CHIARO = (248, 250, 252)
ZEBRA = (241, 245, 249)
BORDO = (226, 232, 240)
VERDE_B, GIALLO_B, ROSSO_B = (22, 163, 74), (217, 119, 6), (220, 38, 38)
TRICOLORE = [(0, 146, 70), (255, 255, 255), (206, 43, 55)]
TONO = {2: VERDE_B, 1: GIALLO_B, 0: ROSSO_B}

STATI = {   # testo cella -> (sfondo, testo)
    "OK": ((220, 252, 231), (22, 101, 52)),
    "SFORATO": ((254, 226, 226), (153, 27, 27)),
    "VERDE": ((220, 252, 231), (22, 101, 52)),
    "GIALLA": ((254, 243, 199), (146, 64, 14)),
    "ROSSA": ((254, 226, 226), (153, 27, 27)),
}
NL = dict(new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def pdf_safe(text):
    """Sostituisce i caratteri non latin-1 (i font core di FPDF non li supportano)."""
    if text is None:
        return ""
    rep = {
        "€": "EUR", "–": "-", "—": "-", "’": "'", "‘": "'", "“": '"', "”": '"',
        "…": "...", "•": "-", "≥": ">=", "≤": "<=", "→": "->", "·": "-",
    }
    for k, v in rep.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


class _PDF(FPDF):
    def __init__(self, ctx):
        super().__init__(format="A4")
        self.ctx = ctx
        self.set_margins(12, 28, 12)
        self.set_auto_page_break(True, margin=20)
        self.alias_nb_pages()
        self.set_title("FCR General Contractor - Report di valutazione")
        self.set_author("FCR General Contractor / Aetheris Labs")

    def header(self):
        if self.page_no() == 1:
            return
        if os.path.exists(LOGO_FCR_PATH):
            try:
                self.image(LOGO_FCR_PATH, 12, 6, 14)
            except Exception:
                pass
        self.set_xy(29, 7)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*NAVY)
        self.cell(110, 5, "FCR GENERAL CONTRACTOR - AI Business Plan & Rating", **dict(new_x=XPos.RIGHT, new_y=YPos.TOP))
        self.set_xy(29, 13)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*GRIGIO)
        pratica = self.ctx.get("pratica") or "-"
        self.cell(110, 4, pdf_safe(f"Report di valutazione del merito di credito | Pratica: {pratica}"))
        self.set_xy(130, 8)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*NAVY)
        self.cell(68, 4, pdf_safe(f"ID {self.ctx['report_id']}"), align="R")
        self.set_xy(130, 13)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*GRIGIO)
        self.cell(68, 4, pdf_safe(self.ctx["generato_il"]), align="R")
        self.set_draw_color(*NAVY)
        self.set_line_width(0.5)
        self.line(12, 21, 198, 21)
        for i, c in enumerate(TRICOLORE):
            self.set_fill_color(*c)
            self.set_draw_color(*BORDO)
            self.set_line_width(0.1)
            self.rect(12 + i * 8, 21.6, 8, 1.2, style="DF" if c == (255, 255, 255) else "F")
        self.set_y(28)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-14)
        self.set_draw_color(*BORDO)
        self.set_line_width(0.2)
        self.line(12, self.get_y(), 198, self.get_y())
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*GRIGIO)
        self.set_y(-12)
        self.cell(58, 5, "Documento riservato - uso interno", align="L")
        self.cell(58, 5, f"Pagina {self.page_no()} di {{nb}}", align="C")
        self.cell(62, 5, pdf_safe(f"Powered by Aetheris Labs | Modello AI: {self.ctx['modello']}"), align="R")
        if os.path.exists(LOGO_PATH):
            try:
                self.image(LOGO_PATH, 190.5, self.h - 12.8, 7.5)
            except Exception:
                pass


# ----------------------------------------------------------------------------
def genera_pdf(ctx, relazione, grafici=None):
    if grafici is None:
        import exports
        grafici = exports.grafici_report(ctx)
    pdf = _PDF(ctx)
    base, scen, rating, piano = ctx["dati"], ctx["scen"], ctx["rating"], ctx["piano"]
    livello = core.livello_classe(rating["classe"])
    colore_classe = TONO[livello]

    # ---------- helper di disegno -------------------------------------------------
    def spazio(h):
        if pdf.get_y() + h > 277:
            pdf.add_page()

    def sezione(testo, numero=None, riserva=45):
        spazio(riserva)       # evita titoli isolati a fondo pagina
        pdf.ln(2)
        y = pdf.get_y()
        pdf.set_fill_color(*BLU)
        pdf.rect(12, y + 0.5, 1.6, 6.5, style="F")
        pdf.set_xy(16, y)
        pdf.set_font("Helvetica", "B", 12.5)
        pdf.set_text_color(*NAVY)
        etichetta = f"{numero}. {testo}" if numero else testo
        pdf.start_section(pdf_safe(etichetta))
        pdf.cell(0, 7.5, pdf_safe(etichetta), **NL)
        pdf.ln(1.5)

    def sottotitolo(testo):
        spazio(16)
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(*BLU)
        pdf.cell(0, 6, pdf_safe(testo), **NL)

    def paragrafo(testo, size=9, colore=TESTO, h=4.8, stile=""):
        pdf.set_font("Helvetica", stile, size)
        pdf.set_text_color(*colore)
        pdf.multi_cell(0, h, pdf_safe(testo), **NL)

    def tabella(intest, righe, widths, aligns, size=8.5, h=6.6, zebra=True):
        """Tabella con intestazione ripetuta a cambio pagina e celle di stato colorate."""
        def testata():
            pdf.set_font("Helvetica", "B", size)
            pdf.set_fill_color(*NAVY)
            pdf.set_text_color(255, 255, 255)
            pdf.set_draw_color(*NAVY)
            pdf.set_line_width(0.2)
            for i, (t, w, a) in enumerate(zip(intest, widths, aligns)):
                last = i == len(intest) - 1
                pdf.cell(w, h + 1, pdf_safe(("  " if a == "L" else "") + t + ("  " if a != "L" else "")), border=1, align=a, fill=True,
                         new_x=XPos.LMARGIN if last else XPos.RIGHT, new_y=YPos.NEXT if last else YPos.TOP)

        if len(righe) <= 14:
            spazio((len(righe) + 1) * h + 8)
        testata()
        pdf.set_font("Helvetica", "", size)
        pdf.set_draw_color(*BORDO)
        for n, r in enumerate(righe):
            if pdf.get_y() + h > 277:
                pdf.add_page()
                testata()
                pdf.set_font("Helvetica", "", size)
                pdf.set_draw_color(*BORDO)
            sfondo = ZEBRA if (zebra and n % 2) else (255, 255, 255)
            for i, (t, w, a) in enumerate(zip(r, widths, aligns)):
                last = i == len(r) - 1
                txt = str(t)
                fill_c, text_c = sfondo, TESTO
                chiave = txt.strip().split(" ")[0].upper()
                if chiave in STATI and len(txt.strip()) <= 9:
                    fill_c, text_c = STATI[chiave]
                    pdf.set_font("Helvetica", "B", size)
                pdf.set_fill_color(*fill_c)
                pdf.set_text_color(*text_c)
                pdf.cell(w, h, pdf_safe(("  " if a == "L" else "") + txt + ("  " if a != "L" else "")), border=1, align=a, fill=True,
                         new_x=XPos.LMARGIN if last else XPos.RIGHT, new_y=YPos.NEXT if last else YPos.TOP)
                pdf.set_font("Helvetica", "", size)
        pdf.ln(3)

    def tile(x, y, w, h, label, value, sub, rgb):
        pdf.set_fill_color(*CHIARO)
        pdf.set_draw_color(*BORDO)
        pdf.set_line_width(0.25)
        pdf.rect(x, y, w, h, style="DF", round_corners=True, corner_radius=2.5)
        pdf.set_fill_color(*rgb)
        pdf.rect(x + 1.5, y, w - 3, 1.6, style="F")
        pdf.set_xy(x + 3, y + 4)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*GRIGIO)
        pdf.cell(w - 6, 4, pdf_safe(label))
        pdf.set_xy(x + 3, y + 9.5)
        pdf.set_font("Helvetica", "B", 15)
        pdf.set_text_color(*NAVY)
        pdf.cell(w - 6, 8, pdf_safe(value))
        pdf.set_xy(x + 3, y + h - 6.5)
        pdf.set_font("Helvetica", "", 6.5)
        pdf.set_text_color(*GRIGIO)
        pdf.cell(w - 6, 4, pdf_safe(sub))

    def immagine(nome, w=178):
        png = grafici.get(nome)
        if not png:
            return
        try:
            from PIL import Image
            with Image.open(io.BytesIO(png)) as im:
                h = w * im.height / im.width
        except Exception:
            h = w * 0.5
        spazio(h + 4)
        pdf.image(io.BytesIO(png), x=(210 - w) / 2, w=w)
        pdf.ln(3)

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
    pdf.cell(0, 7, "AI Business Plan & Rating")
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
    pdf.cell(0, 5, "REPORT DI VALUTAZIONE DEL MERITO DI CREDITO")
    pdf.set_xy(14, 81)
    pdf.set_font("Helvetica", "B", 21)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 10, "Business Plan e Scoring Prospettico")
    pdf.set_xy(14, 93)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(*TESTO)
    pdf.cell(0, 6, pdf_safe("Pratica: " + (ctx.get("pratica") or "non indicata")))

    # scheda informazioni
    pdf.set_fill_color(*CHIARO)
    pdf.set_draw_color(*BORDO)
    pdf.set_line_width(0.25)
    pdf.rect(14, 106, 182, 22, style="DF", round_corners=True, corner_radius=2.5)
    info = [("DATA", ctx["generato_il"]), ("ID REPORT", ctx["report_id"]),
            ("ANNO BASE", str(int(base["anno_riferimento"]))), ("MODELLO AI", str(ctx["modello"])[:22])]
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

    # badge del giudizio
    pdf.set_fill_color(*colore_classe)
    pdf.rect(14, 138, 182, 36, style="F", round_corners=True, corner_radius=3)
    pdf.set_xy(20, 144)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(120, 4, "GIUDIZIO DEL MODELLO DI SCORING (INDICATIVO)")
    pdf.set_xy(20, 150)
    pdf.set_font("Helvetica", "B", 25)
    pdf.cell(120, 12, pdf_safe(rating["classe"].split(" - ")[0]))
    pdf.set_xy(20, 164)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(130, 5, pdf_safe(rating["classe"].split(" - ")[1] if " - " in rating["classe"] else ""))
    pdf.set_xy(150, 144)
    pdf.set_font("Helvetica", "B", 34)
    pdf.cell(40, 18, f"{rating['punti']}/8", align="R")
    pdf.set_xy(150, 163)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(40, 4, "punteggio", align="R")

    # KPI
    for i, d in enumerate(rating["dettaglio"]):
        sub = "Verde " + core.soglie_testo(d).split(" / ")[0]
        tile(14 + i * 46, 184, 43.5, 28, d["indicatore"].replace(" (anno 1 del piano)", " (anno 1)"),
             core.valore_dettaglio(d), sub, TONO[d["punti"]])

    # avvisi in copertina
    y_av = 222
    if ctx.get("dati_demo"):
        pdf.set_draw_color(*ROSSO_B)
        pdf.set_fill_color(254, 242, 242)
        pdf.set_line_width(0.4)
        pdf.rect(14, y_av, 182, 14, style="DF", round_corners=True, corner_radius=2)
        pdf.set_xy(18, y_av + 2.5)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*ROSSO_B)
        pdf.cell(0, 4.5, "ATTENZIONE: dati di esempio non verificati")
        pdf.set_xy(18, y_av + 7.5)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(0, 4, "Il report non e' basato sul bilancio reale dell'impresa.")
        y_av += 18
    if ctx.get("avvisi_dati"):
        pdf.set_draw_color(*GIALLO_B)
        pdf.set_fill_color(255, 251, 235)
        pdf.set_line_width(0.4)
        pdf.rect(14, y_av, 182, 10, style="DF", round_corners=True, corner_radius=2)
        pdf.set_xy(18, y_av + 3)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(*GIALLO_B)
        pdf.cell(0, 4, pdf_safe(f"{len(ctx['avvisi_dati'])} avvisi sulla qualita' dei dati: vedere la sezione 1."))

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
    pdf.multi_cell(130, 3.4, pdf_safe("Simulazione indicativa: non costituisce rating regolamentare, parere di merito creditizio ne' consulenza finanziaria."), **NL)
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
    n = 0

    def prossima():
        nonlocal n
        n += 1
        return n

    # 1. Qualita' dei dati
    if ctx.get("avvisi_dati"):
        sezione("Avvisi sulla qualita' dei dati", prossima())
        y0 = pdf.get_y()
        altezza = 6 + 5.2 * len(ctx["avvisi_dati"])
        spazio(altezza + 4)
        y0 = pdf.get_y()
        pdf.set_fill_color(255, 251, 235)
        pdf.set_draw_color(*GIALLO_B)
        pdf.set_line_width(0.3)
        pdf.rect(12, y0, 186, altezza, style="DF", round_corners=True, corner_radius=2)
        pdf.set_xy(16, y0 + 3)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(120, 53, 15)
        for a in ctx["avvisi_dati"]:
            pdf.set_x(16)
            pdf.multi_cell(178, 5.2, pdf_safe("- " + a), **NL)
        pdf.set_y(y0 + altezza + 3)

    # Sintesi
    sezione("Sintesi indicatori: base e scenario", prossima(), 110)
    righe = [
        ("Ricavi delle vendite", fmt_eur(base["ricavi"]), fmt_eur(scen["ricavi"])),
        ("EBITDA (MOL)", fmt_eur(base["ebitda"]), fmt_eur(scen["ebitda"])),
        ("Utile netto", fmt_eur(base["utile_netto"]), "-"),
        ("Totale attivo", fmt_eur(base["totale_attivo"]), fmt_eur(scen["attivo"])),
        ("Patrimonio netto", fmt_eur(base["patrimonio_netto"]), fmt_eur(scen["pn"])),
        ("Debiti finanziari totali", fmt_eur(base["debiti_finanziari_totali"]), "-"),
        ("Posizione finanziaria netta (PFN)", fmt_eur(base["pfn"]), fmt_eur(scen["pfn"])),
        ("PFN / EBITDA", fmt_x(ratio(base["pfn"], base["ebitda"])), fmt_x(rating["pfn_ebitda"])),
        ("PFN / Patrimonio netto", fmt_x(ratio(base["pfn"], base["patrimonio_netto"])), fmt_x(rating["pfn_pn"])),
        ("Patrimonio netto / Totale attivo",
         fmt_pct(100 * base["patrimonio_netto"] / base["totale_attivo"]) if base["totale_attivo"] > 0 else "n.d.",
         fmt_pct(100 * rating["equity_ratio"])),
        ("DSCR (anno 1 del piano)", "-", fmt_x(rating["dscr"]) if rating["dscr"] is not None else "n.d."),
    ]
    tabella(["Parametro", "Base", "Scenario"], righe, [86, 50, 50], ["L", "R", "R"])
    leve = ctx.get("leve") or {}
    if any(leve.get(k) for k in ("delta_pfn", "delta_pn", "delta_ebitda")):
        paragrafo(
            f"Leve applicate allo scenario: variazione debito netto {fmt_eur(leve.get('delta_pfn', 0))}, "
            f"capitale iniettato {fmt_eur(leve.get('delta_pn', 0))}, variazione EBITDA {fmt_eur(leve.get('delta_ebitda', 0))}.",
            8, GRIGIO, 4.2, "I")
        pdf.ln(1)

    sottotitolo("Dettaglio del punteggio")
    tabella(
        ["Indicatore", "Valore", "Soglie (verde / giallo)", "Punti"],
        [(d["indicatore"], core.valore_dettaglio(d), core.soglie_testo(d), f"{d['punti']}/2") for d in rating["dettaglio"]]
        + [("TOTALE", "", rating["classe"].split(" - ")[0].replace("FASCIA ", ""), f"{rating['punti']}/8")],
        [66, 36, 56, 28], ["L", "R", "R", "R"],
    )

    # Piano
    sezione("Proiezioni pluriennali", prossima())
    tabella(
        ["Anno", "Ricavi", "EBITDA", "FCF", "PFN", "PFN/EBITDA", "DSCR"],
        [(r["Anno"], fmt_num(r["Ricavi"]), fmt_num(r["EBITDA"]), fmt_num(r["FCF"]), fmt_num(r["PFN"]),
          fmt_x(r["PFN/EBITDA"]), fmt_x(r["DSCR"]) if r["DSCR"] is not None else "n.d.") for r in piano],
        [32, 27, 27, 26, 27, 24, 23], ["L", "R", "R", "R", "R", "R", "R"], size=8,
    )
    p = ctx["piano_par"]
    paragrafo(
        f"Importi in EUR. Ipotesi: crescita annua ricavi {fmt_num(p['g_ricavi'], 1)}% ed EBITDA {fmt_num(p['g_ebitda'], 1)}%; "
        f"capex {fmt_num(p['capex'])}; ammortamenti {fmt_num(p['amm'])}; rimborso annuo {fmt_num(p['rimborso'])}; tasso sulla PFN "
        f"{fmt_num(p['tasso'], 2)}%; aliquota fiscale {fmt_num(p['aliquota'], 1)}%; capitale circolante pari al "
        f"{fmt_num(p['ccn_pct'], 0)}% della variazione dei ricavi.", 7.5, GRIGIO, 4, "I")
    pdf.ln(2)
    for nome in ("pfn_ebitda", "dscr", "cascata", "storico", "confronto"):
        immagine(nome)

    # Covenant
    if ctx.get("cov_res"):
        sezione("Verifica covenant", prossima(), 45)
        tabella(
            ["Anno", "PFN/EBITDA", "Limite", "Leva", "DSCR", "Limite", "DSCR"],
            [(c["Anno"], fmt_x(c["PFN/EBITDA"]), fmt_x(c["Limite PFN/EBITDA"]), c["Esito leva"],
              fmt_x(c["DSCR"]) if c["DSCR"] is not None else "n.d.", fmt_x(c["Limite DSCR"]), c["Esito DSCR"])
             for c in ctx["cov_res"]],
            [34, 28, 24, 26, 26, 24, 24], ["L", "R", "R", "C", "R", "R", "C"],
        )

    # Stress test
    if ctx.get("stress"):
        sezione("Stress test", prossima(), 75)
        tabella(
            ["Caso", "PFN/EBITDA a fine piano", "DSCR minimo", "Punti", "Fascia"],
            [(s["Caso"], fmt_x(s["PFN/EBITDA anno 3"]),
              fmt_x(s["DSCR minimo"]) if s["DSCR minimo"] is not None else "n.d.", f"{s['Punteggio']}/8", s["Fascia"])
             for s in ctx["stress"]],
            [74, 38, 28, 20, 26], ["L", "R", "R", "C", "C"],
        )

    # Commesse
    k = ctx.get("commesse_kpi")
    if k:
        sezione("Portafoglio commesse", prossima(), 85)
        tabella(
            ["Indicatore", "Valore"],
            [
                ("Numero commesse", str(k["n_commesse"])),
                ("Importo totale dei contratti", fmt_eur(k["importo_totale"])),
                ("Backlog residuo", fmt_eur(k["backlog"])),
                ("Copertura ricavi (backlog / ricavi base)", fmt_x(k["copertura_ricavi"]) if k["copertura_ricavi"] is not None else "n.d."),
                ("Produzione eseguita non fatturata (negativo = anticipi)", fmt_eur(k["da_fatturare"])),
                ("Crediti verso clienti da commesse", fmt_eur(k["crediti"])),
                ("Margine medio ponderato sul backlog", fmt_pct(k["margine_backlog_pct"])),
                ("Concentrazione primo cliente / primi tre", f"{fmt_pct(k['top1_pct'], 0)} / {fmt_pct(k['top3_pct'], 0)}"),
            ],
            [120, 66], ["L", "R"],
        )
        immagine("commesse")

    # Storico
    if ctx.get("storico"):
        sezione("Storico degli esercizi precedenti", prossima())
        tabella(
            ["Anno", "Ricavi", "EBITDA", "Patrimonio netto", "PFN"],
            [(str(r["anno"]), fmt_num(r["ricavi"]), fmt_num(r["ebitda"]), fmt_num(r["patrimonio_netto"]), fmt_num(r["pfn"]))
             for r in ctx["storico"]],
            [26, 40, 40, 44, 36], ["L", "R", "R", "R", "R"],
        )

    # Relazione
    sezione("Relazione e parere del Risk Management", prossima())
    for riga in (relazione or "").split("\n"):
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

    # Metodologia
    sezione("Metodologia, ipotesi e limiti", prossima(), 90)
    s = ctx.get("soglie") or core.SOGLIE_DEFAULT
    nomi = {"pfn_ebitda": "PFN / EBITDA", "pfn_pn": "PFN / Patrimonio netto",
            "equity_ratio": "Patrimonio netto / Attivo", "dscr": "DSCR (anno 1)"}
    righe_s = []
    for key, nome in nomi.items():
        v, g = s[key]
        if key == "equity_ratio":
            righe_s.append((nome, f">= {fmt_pct(100 * v, 0)}", f">= {fmt_pct(100 * g, 0)}", "< " + fmt_pct(100 * g, 0)))
        elif core.VERSO[key] == "min":
            righe_s.append((nome, f"< {fmt_num(v, 2)}", f"< {fmt_num(g, 2)}", f">= {fmt_num(g, 2)}"))
        else:
            righe_s.append((nome, f">= {fmt_num(v, 2)}", f">= {fmt_num(g, 2)}", f"< {fmt_num(g, 2)}"))
    tabella(["Indicatore", "2 punti (verde)", "1 punto (giallo)", "0 punti (rosso)"], righe_s,
            [66, 40, 40, 40], ["L", "R", "R", "R"])
    paragrafo("Punteggio totale = somma dei punti dei quattro indicatori (massimo 8). Fascia verde: punteggio pari o superiore a 7; "
              "gialla: da 4 a 6; rossa: inferiore a 4, oppure patrimonio netto non positivo, oppure EBITDA non positivo. "
              "Le soglie sono ipotesi di lavoro configurabili e non derivano da una calibrazione statistica su dati di insolvenza.", 8.5)
    pdf.ln(1.5)
    paragrafo("Piano: FCF = EBITDA - imposte - capex - interessi - variazione del capitale circolante; PFN(t) = PFN(t-1) - FCF. "
              "Il rimborso del debito non riduce la PFN (utilizza cassa) ma incide sul DSCR = (EBITDA - imposte - variazione CCN) / "
              "(interessi + rimborso). Gli stress test applicano shock a EBITDA, ricavi e tassi sullo scenario corrente.", 8.5)
    pdf.ln(1.5)
    paragrafo("Limiti: il modello e' semplificato e non considera stagionalita', garanzie, Centrale Rischi, rating di settore, "
              "contenziosi ne' la qualita' dei crediti. Le ipotesi del piano sono definite dall'utente.", 8.5)

    # Privacy e avvertenze
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
    altezza = 4.1 * len(righe_av) + 6
    pdf.rect(12, y0, 186, altezza, style="DF", round_corners=True, corner_radius=2)
    pdf.set_xy(16, y0 + 3)
    pdf.set_text_color(*GRIGIO)
    pdf.multi_cell(178, 4.1, pdf_safe("Avvertenza: " + DISCLAIMER), **NL)

    return bytes(pdf.output())
