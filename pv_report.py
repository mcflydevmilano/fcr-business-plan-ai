"""pv_report.py - Preventivo per il cliente (PDF senza costi/margini) e Excel interno con formule."""
import io
import time

import charts
import core
from core import fmt_num
from pdf_report import BLU, GRIGIO, NAVY, VERDE_B, _PDF, _strumenti
from report_util import copertina


def costruisci_ctx_pv(out, cliente="", oggetto="", validita_gg=30, note=""):
    firma = {"k": out["kpi"], "c": cliente, "o": oggetto}
    return {
        "pv": out, "cliente": cliente or "", "oggetto": oggetto or "", "validita_gg": int(validita_gg), "note": note or "",
        "modello": "nessuno", "pratica": oggetto or "", "report_id": core.hash_payload(firma, 8).upper(),
        "generato_il": time.strftime("%d/%m/%Y %H:%M"),
        "header_titolo": "FCR GENERAL CONTRACTOR - Preventivo", "header_sub": (oggetto or "Preventivo lavori") + (f" | {cliente}" if cliente else ""),
        "titolo_documento": "FCR General Contractor - Preventivo", "footer_sx": "Offerta non vincolante fino ad accettazione", "footer_dx": "Powered by Aetheris Labs",
    }


def genera_pdf_pv(ctx):
    """Documento per il cliente: voci, prezzi, sicurezza, IVA. NON contiene costi, spese generali ne' utile."""
    out = ctx["pv"]
    k, q = out["kpi"], out["params"]
    pdf = _PDF(ctx)
    T = _strumenti(pdf, {})
    copertina(pdf, T.tile, ctx, "Preventivo lavori", "Offerta economica", ctx["oggetto"] or "Preventivo lavori", [
        ("DATA", ctx["generato_il"]), ("RIF.", ctx["report_id"]), ("CLIENTE", ctx["cliente"] or "-"), ("VALIDITA'", f"{ctx['validita_gg']} giorni")],
        [("Lavori", fmt_num(k["prezzo_lavori"]) + " EUR", f"{k['n_voci']} voci", BLU),
         ("Oneri sicurezza", fmt_num(k["oneri_sicurezza"]) + " EUR", "non soggetti a ribasso", BLU),
         ("IVA " + fmt_num(q["iva_pct"], 0) + "%", fmt_num(k["iva"]) + " EUR", "", BLU),
         ("Totale", fmt_num(k["totale"]) + " EUR", "IVA inclusa", VERDE_B)])
    pdf.add_page()
    T.sezione("Computo dei lavori", 1, 60)
    cats = {}
    for r in out["voci"]:
        cats.setdefault(r["Categoria"], []).append(r)
    for cat, rr in cats.items():
        T.sottotitolo(cat)
        righe = [((r["Codice"] or "-"), r["Descrizione"][:60], r["UM"], fmt_num(r["Quantita"], 2), fmt_num(r["Prezzo unitario"], 2), fmt_num(r["Prezzo"], 2)) for r in rr]
        righe.append(("", "Totale " + cat, "", "", "", fmt_num(sum(r["Prezzo"] for r in rr), 2)))
        T.tabella(["Cod.", "Descrizione", "U.M.", "Quantita'", "Prezzo unit.", "Importo"], righe, [18, 82, 12, 22, 24, 28], ["L", "L", "C", "R", "R", "R"], size=8, h=5.8)
    T.sezione("Riepilogo economico", 2, 60)
    T.tabella(["Voce", "Importo (EUR)"], [
        ("Importo dei lavori", fmt_num(k["prezzo_lavori"], 2)), ("Oneri per la sicurezza (non ribassabili)", fmt_num(k["oneri_sicurezza"], 2)),
        ("Imponibile", fmt_num(k["imponibile"], 2)), (f"IVA {fmt_num(q['iva_pct'], 0)}%", fmt_num(k["iva"], 2)), ("TOTALE", fmt_num(k["totale"], 2))],
        [130, 52], ["L", "R"])
    T.sezione("Condizioni", 3, 40)
    T.paragrafo(f"Offerta valida {ctx['validita_gg']} giorni dalla data del documento. Quantita' e prezzi si intendono a corpo/misura secondo il computo sopra riportato; "
                "varianti e lavorazioni non indicate saranno quotate a parte.", 9)
    if ctx["note"]:
        T.paragrafo("Note: " + ctx["note"], 9)
    return bytes(pdf.output())


def genera_excel_pv(ctx):
    """Excel interno: costi unitari, totali e prezzi con formule; parametri modificabili."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    out = ctx["pv"]
    q = out["params"]
    wb = Workbook()
    giallo, testata = PatternFill("solid", fgColor="FFF2CC"), PatternFill("solid", fgColor="1E293B")
    f_h, f_in = Font(color="FFFFFF", bold=True), Font(color="1D4ED8", bold=True)
    EUR = '#,##0.00'
    ws = wb.active
    ws.title = "Parametri"
    ws["A1"] = "Preventivo interno - parametri (celle gialle modificabili). DOCUMENTO RISERVATO: contiene costi e margini."
    ws["A1"].font = Font(bold=True)
    par = [("Spese generali %", q["sg_pct"]), ("Utile d'impresa %", q["utile_pct"]), ("Sconto %", q["sconto_pct"]), ("Oneri sicurezza % del listino", q["sicurezza_pct"]), ("IVA %", q["iva_pct"])]
    for i, (e, v) in enumerate(par, start=3):
        ws.cell(row=i, column=1, value=e)
        c = ws.cell(row=i, column=2, value=v)
        c.fill, c.font = giallo, f_in
    ws.column_dimensions["A"].width = 38
    wv = wb.create_sheet("Voci")
    for j, t in enumerate(["Codice", "Categoria", "Descrizione", "UM", "Quantita", "Materiali", "Manodopera", "Noli/altro", "Costo unitario", "Costo", "Prezzo"], 1):
        c = wv.cell(row=1, column=j, value=t)
        c.fill, c.font = testata, f_h
    for i, r in enumerate(out["voci"], start=2):
        for j, key in enumerate(["Codice", "Categoria", "Descrizione", "UM", "Quantita", "Materiali", "Manodopera", "Noli_altro"], 1):
            wv.cell(row=i, column=j, value=r[key])
        wv.cell(row=i, column=9, value=f"=F{i}+G{i}+H{i}").number_format = EUR
        wv.cell(row=i, column=10, value=f"=E{i}*I{i}").number_format = EUR
        wv.cell(row=i, column=11, value=f"=ROUND(J{i}*(1+Parametri!$B$3/100)*(1+Parametri!$B$4/100)*(1-Parametri!$B$5/100),2)").number_format = EUR
    u = len(out["voci"]) + 1
    labels = [("Costi diretti", f"=SUM(J2:J{u})"), ("Spese generali", f"=B{u+3}*Parametri!$B$3/100"), ("Costo industriale", f"=B{u+3}+B{u+4}"),
              ("Listino (con utile)", f"=B{u+5}*(1+Parametri!$B$4/100)"), ("Prezzo lavori scontato", f"=SUM(K2:K{u})"),
              ("Oneri sicurezza", f"=ROUND(B{u+6}*Parametri!$B$6/100,2)"), ("Imponibile", f"=B{u+7}+B{u+8}"),
              ("IVA", f"=ROUND(B{u+9}*Parametri!$B$7/100,2)"), ("TOTALE", f"=B{u+9}+B{u+10}"),
              ("Utile effettivo", f"=B{u+7}-B{u+5}"), ("Margine % su imponibile", f"=IF(B{u+9}=0,0,B{u+12}/B{u+9}*100)")]
    # etichette in colonna A, valori in B; riga base u+3
    wr = wb.create_sheet("Riepilogo")
    for i, (e, f) in enumerate(labels, start=1):
        wr.cell(row=i, column=1, value=e).font = Font(bold=(e in ("TOTALE", "Imponibile")))
    # riscrive le formule con riferimenti locali al foglio Riepilogo
    ref = {n: f"B{i}" for i, (n, _) in enumerate(labels, start=1)}
    P = lambda r: f"Parametri!$B${r}"
    f = {
        "Costi diretti": f"=SUM(Voci!J2:J{u})",
        "Spese generali": f"={ref['Costi diretti']}*{P(3)}/100",
        "Costo industriale": f"={ref['Costi diretti']}+{ref['Spese generali']}",
        "Listino (con utile)": f"={ref['Costo industriale']}*(1+{P(4)}/100)",
        "Prezzo lavori scontato": f"=SUM(Voci!K2:K{u})",
        "Oneri sicurezza": f"=ROUND({ref['Listino (con utile)']}*{P(6)}/100,2)",
        "Imponibile": f"={ref['Prezzo lavori scontato']}+{ref['Oneri sicurezza']}",
        "IVA": f"=ROUND({ref['Imponibile']}*{P(7)}/100,2)",
        "TOTALE": f"={ref['Imponibile']}+{ref['IVA']}",
        "Utile effettivo": f"={ref['Prezzo lavori scontato']}-{ref['Costo industriale']}",
        "Margine % su imponibile": f"=IF({ref['Imponibile']}=0,0,{ref['Utile effettivo']}/{ref['Imponibile']}*100)",
    }
    for i, (e, _) in enumerate(labels, start=1):
        wr.cell(row=i, column=2, value=f[e]).number_format = EUR
    wr.column_dimensions["A"].width = 30
    wr.column_dimensions["B"].width = 18
    for col, w in zip("ABCDEFGHIJK", [10, 16, 50, 6, 10, 12, 12, 12, 14, 14, 14]):
        wv.column_dimensions[col].width = w
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()
