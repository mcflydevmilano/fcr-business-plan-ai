"""dd_report.py - Rapporto di direzione in PDF (semafori e azioni)."""
import time

import core
from core import DISCLAIMER
from pdf_report import BLU, GIALLO_B, GRIGIO, NAVY, ROSSO_B, TESTO, VERDE_B, _PDF, _strumenti
from report_util import copertina
import dd

COL = {"ok": VERDE_B, "warn": GIALLO_B, "bad": ROSSO_B, "nd": (148, 163, 184)}
ETI = {"ok": "OK", "warn": "ATTENZIONE", "bad": "CRITICO", "nd": "DATI MANCANTI"}


def costruisci_ctx_dd(righe, generale, azioni, fonti):
    firma = {"r": [(r["Indicatore"], r["Valore"], r["Stato"]) for r in righe]}
    return {"righe": righe, "generale": generale, "azioni": azioni, "fonti": fonti, "modello": "nessuno", "pratica": "",
            "report_id": core.hash_payload(firma, 10).upper(), "generato_il": time.strftime("%d/%m/%Y %H:%M"),
            "header_titolo": "FCR GENERAL CONTRACTOR - Cruscotto di direzione", "header_sub": "Semafori di margine, cassa, crediti e rating",
            "titolo_documento": "FCR General Contractor - Cruscotto di direzione", "footer_dx": "Powered by Aetheris Labs"}


def genera_pdf_dd(ctx):
    righe, gen, azioni = ctx["righe"], ctx["generale"], ctx["azioni"]
    c = dd.conteggio(righe)
    pdf = _PDF(ctx)
    T = _strumenti(pdf, {})
    esito = {"ok": ("SITUAZIONE SOTTO CONTROLLO", VERDE_B, "Nessun indicatore in allarme"),
             "warn": ("ALCUNI PUNTI DI ATTENZIONE", GIALLO_B, f"{c['warn']} indicatori in attenzione"),
             "bad": ("INTERVENTI NECESSARI", ROSSO_B, f"{c['bad']} indicatori critici, {c['warn']} in attenzione"),
             "nd": ("DATI INSUFFICIENTI", COL["nd"], "Compila i moduli per popolare il cruscotto")}[gen]
    copertina(pdf, T.tile, ctx, "Cruscotto di direzione", "Rapporto di direzione", "Stato dell'azienda in sintesi", [
        ("DATA", ctx["generato_il"]), ("ID REPORT", ctx["report_id"]), ("INDICATORI", str(len(righe))), ("CRITICI", str(c["bad"]))],
        [("In regola", str(c["ok"]), "indicatori verdi", VERDE_B), ("Attenzione", str(c["warn"]), "indicatori gialli", GIALLO_B),
         ("Critici", str(c["bad"]), "indicatori rossi", ROSSO_B), ("Mancanti", str(c["nd"]), "dati non inseriti", BLU)], esito)
    pdf.add_page()
    T.sezione("Semafori", 1, 60)
    for r in righe:
        if pdf.get_y() > 262:
            pdf.add_page()
        y = pdf.get_y()
        pdf.set_fill_color(*COL[r["Stato"]])
        pdf.ellipse(14, y + 1.6, 4, 4, style="F")
        pdf.set_xy(21, y)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(*NAVY)
        pdf.cell(78, 6, core_safe(r["Indicatore"]))
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(34, 6, core_safe(str(r["Valore"])), align="R")
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*GRIGIO)
        pdf.cell(0, 6, "   " + core_safe(r["Nota"])[:70])
        pdf.set_xy(14, y + 7)
        pdf.set_draw_color(226, 232, 240)
        pdf.line(14, y + 6.8, 198, y + 6.8)
    T.sezione("Cosa fare", 2, 50)
    if azioni:
        for g, t in azioni:
            T.paragrafo(("[CRITICO] " if g == "bad" else "[ATTENZIONE] ") + t, 9)
    else:
        T.paragrafo("Nessuna azione urgente.", 9)
    T.sezione("Fonti dei dati", 3, 40)
    for k, v in ctx["fonti"].items():
        T.paragrafo(f"- {k}: {v}", 9)
    T.paragrafo("Le soglie dei semafori sono ipotesi di lavoro configurabili, non standard di settore o parametri regolamentari.", 8.5, GRIGIO)
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*GRIGIO)
    pdf.set_x(14)
    pdf.multi_cell(182, 4.1, "Avvertenza: " + DISCLAIMER.replace("modello di scoring interno", "modello di sintesi").encode("latin-1", "replace").decode("latin-1"))
    return bytes(pdf.output())


def core_safe(t):
    from pdf_report import pdf_safe
    return pdf_safe(t)
