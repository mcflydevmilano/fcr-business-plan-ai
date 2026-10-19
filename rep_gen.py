"""rep_gen.py - Generatore comune di dossier PDF ed Excel per i moduli operativi (gare, fornitori, sicurezza, mezzi, organico)."""
import io
import re
import time

import core
from core import DISCLAIMER
from pdf_report import BLU, GIALLO_B, GRIGIO, ROSSO_B, VERDE_B, _PDF, _strumenti
from report_util import copertina

COL = {"ok": VERDE_B, "warn": GIALLO_B, "bad": ROSSO_B, "info": BLU}
_NUM = re.compile(r"^[\-+(]?[\d.,]+[%x)]?$")


def costruisci_ctx(titolo, sotto, nome, firma):
    return {"nome": nome or "", "modello": "nessuno", "pratica": nome or "", "report_id": core.hash_payload(firma, 10).upper(),
            "generato_il": time.strftime("%d/%m/%Y %H:%M"), "header_titolo": f"FCR GENERAL CONTRACTOR - {titolo}", "header_sub": f"{sotto} | " + (nome or titolo),
            "titolo_documento": f"FCR General Contractor - {titolo}", "footer_dx": "Powered by Aetheris Labs"}


def larghezze(intest, righe, totale=182.0):
    pesi = []
    for j, t in enumerate(intest):
        m = max([len(str(t)) * 0.9] + [len(str(r[j])) for r in righe[:60] if j < len(r)])
        pesi.append(min(max(m, 6), 34))
    k = totale / sum(pesi)
    return [p * k for p in pesi]


def allineamenti(intest, righe):
    out = []
    for j in range(len(intest)):
        v = [str(r[j]) for r in righe[:30] if j < len(r) and str(r[j]).strip()]
        out.append("R" if v and all(_NUM.match(x) for x in v) else "L")
    return out


def genera_pdf(ctx, modulo, titolo, sottotitolo, meta, tiles, esito, sezioni, note=()):
    """meta: [(etichetta, valore)] max 4; tiles: [(etichetta, valore, sotto, 'ok'|'warn'|'bad'|'info')] max 4; esito: (titolo, tono, riga);
    sezioni: [{"titolo", "testo": [str], "tabella": (intest, righe), "grafico": png, "pagina": bool}]."""
    pdf = _PDF(ctx)
    grafici = {f"g{i}": s["grafico"] for i, s in enumerate(sezioni) if s.get("grafico")}
    T = _strumenti(pdf, grafici)
    es = (esito[0], COL[esito[1]], esito[2]) if esito else None
    copertina(pdf, T.tile, ctx, modulo, titolo, sottotitolo, ([("DATA", ctx["generato_il"]), ("ID REPORT", ctx["report_id"])] + list(meta))[:4],
              [(a, b, c, COL[d]) for a, b, c, d in tiles][:4], es)
    pdf.add_page()
    for n, s in enumerate(sezioni, start=1):
        if s.get("pagina") and n > 1:
            pdf.add_page()
        T.sezione(s["titolo"], n, 70 if s.get("tabella") else 50)
        for t in s.get("testo", []):
            T.paragrafo(t, 9)
        if s.get("grafico"):
            T.immagine(f"g{n - 1}", 165)
        if s.get("tabella"):
            intest, righe = s["tabella"]
            if righe:
                T.tabella(intest, righe, larghezze(intest, righe), allineamenti(intest, righe), size=8, h=5.8)
            else:
                T.paragrafo("Nessun dato.", 9)
    for t in note:
        T.paragrafo(t, 8.5)
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*GRIGIO)
    pdf.set_x(14)
    pdf.multi_cell(182, 4.1, "Avvertenza: " + DISCLAIMER.replace("modello di scoring interno", "modello di controllo").encode("latin-1", "replace").decode("latin-1"))
    return bytes(pdf.output())


def genera_excel(fogli):
    """fogli: [{"nome", "intest": [...], "righe": [[...]], "totali": [indici colonna da sommare], "formati": {indice: 'num'|'pct'|'data'}}].
    Le celle stringa che iniziano con '=' sono formule; '{r}' diventa il numero di riga."""
    import datetime as dt
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    wb.remove(wb.active)
    for f in fogli:
        ws = wb.create_sheet(f["nome"][:31])
        for j, t in enumerate(f["intest"], 1):
            c = ws.cell(row=1, column=j, value=t)
            c.fill, c.font = PatternFill("solid", fgColor="1E293B"), Font(color="FFFFFF", bold=True)
            ws.column_dimensions[get_column_letter(j)].width = max(14, len(str(t)) + 4)
        ws.freeze_panes = "A2"
        for i, r in enumerate(f["righe"], start=2):
            for j, v in enumerate(r, 1):
                if isinstance(v, str) and v.startswith("="):
                    v = v.replace("{r}", str(i))
                if isinstance(v, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", v):
                    v = dt.date.fromisoformat(v)
                c = ws.cell(row=i, column=j, value=v)
                fm = (f.get("formati") or {}).get(j - 1)
                if isinstance(v, dt.date):
                    c.number_format = "DD/MM/YYYY"
                elif fm == "pct":
                    c.number_format = "0.0"
                elif isinstance(v, (int, float)) or fm == "num" or (isinstance(v, str) and v.startswith("=")):
                    c.number_format = '#,##0;[Red]-#,##0'
        if f.get("totali") and f["righe"]:
            u = len(f["righe"]) + 1
            ws.cell(row=u + 1, column=1, value="Totale").font = Font(bold=True)
            for j in f["totali"]:
                L = get_column_letter(j + 1)
                c = ws.cell(row=u + 1, column=j + 1, value=f"=SUM({L}2:{L}{u})")
                c.font, c.number_format = Font(bold=True), '#,##0;[Red]-#,##0'
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()
