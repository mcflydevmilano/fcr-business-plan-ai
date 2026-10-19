"""report_util.py - Elementi comuni dei dossier PDF dei moduli Cash Flow e Preventivo."""
import os

from core import LOGO_FCR_PATH, LOGO_PATH
from pdf_report import BLU, BORDO, CHIARO, GRIGIO, NAVY, NL, TESTO, TRICOLORE, pdf_safe


def copertina(pdf, tile, ctx, nome_modulo, titolo, sottotitolo, info, tiles, esito=None):
    """Pagina di copertina. info: [(etichetta, valore)] (max 4); tiles: [(etichetta, valore, sotto, rgb)] (max 4);
    esito: (titolo, rgb, riga) oppure None."""
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
    pdf.cell(0, 7, pdf_safe(nome_modulo))
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
    pdf.cell(0, 5, pdf_safe(titolo.upper()))
    pdf.set_xy(14, 81)
    pdf.set_font("Helvetica", "B", 21)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 10, pdf_safe(sottotitolo))
    pdf.set_xy(14, 93)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(*TESTO)
    pdf.cell(0, 6, pdf_safe(ctx.get("riga_cover", "")))

    pdf.set_fill_color(*CHIARO)
    pdf.set_draw_color(*BORDO)
    pdf.set_line_width(0.25)
    pdf.rect(14, 106, 182, 22, style="DF", round_corners=True, corner_radius=2.5)
    for i, (lab, val) in enumerate(info[:4]):
        x = 18 + i * 45
        pdf.set_xy(x, 111)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*GRIGIO)
        pdf.cell(42, 4, pdf_safe(lab))
        pdf.set_xy(x, 117)
        pdf.set_font("Helvetica", "B", 10.5)
        pdf.set_text_color(*NAVY)
        pdf.cell(42, 6, pdf_safe(val))

    if esito:
        tit, rgb, riga = esito
        pdf.set_fill_color(*rgb)
        pdf.rect(14, 138, 182, 36, style="F", round_corners=True, corner_radius=3)
        pdf.set_xy(20, 144)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(150, 4, "ESITO DEI CONTROLLI AUTOMATICI")
        pdf.set_xy(20, 150)
        pdf.set_font("Helvetica", "B", 19)
        pdf.cell(170, 12, pdf_safe(tit))
        pdf.set_xy(20, 164)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(170, 5, pdf_safe(riga))
    for i, (lab, val, sub, rgb) in enumerate(tiles[:4]):
        tile(14 + i * 46, 184, 43.5, 28, lab, val, sub, rgb)

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
    pdf.multi_cell(120, 3.4, pdf_safe(ctx.get("nota_cover", "Proiezione basata su ipotesi dell'utente: non costituisce garanzia di risultato ne' consulenza.")), **NL)
    pdf.set_xy(138, 270)
    pdf.cell(30, 4, "Powered by", align="R")
    if os.path.exists(LOGO_PATH):
        try:
            pdf.image(LOGO_PATH, 170, 258, 26)
        except Exception:
            pass
