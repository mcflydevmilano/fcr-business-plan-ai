"""versione.py - Nome, versione e proprieta' del software. Unico punto da aggiornare a ogni rilascio."""
NOME = "FCR Suite"
VERSIONE = "3.0.0"
DATA_RILASCIO = "21/10/2026"
PROPRIETARIO = "Aetheris Labs"
COPYRIGHT = "© 2026 Aetheris Labs. Tutti i diritti riservati."
CLIENTE = "FCR General Contractor"
AUTORE = "Ing. Lorenzo Di Ferdinando"
NOTE_LEGALI = f"{NOME} è un software di proprietà di {PROPRIETARIO}, concesso in uso a {CLIENTE}. Ne sono vietate la copia e la diffusione senza autorizzazione."


def riga_versione():
    return f"{NOME} v{VERSIONE} · Software di proprietà di {PROPRIETARIO}"


def riga_pdf():
    """Testo per il piede di pagina dei PDF (solo ASCII: i font standard dei PDF non hanno le lettere accentate)."""
    return f"{NOME} v{VERSIONE} - Software di proprieta' {PROPRIETARIO}"


def nota_copertina():
    return f"{NOME} v{VERSIONE} - Software di proprieta' di {PROPRIETARIO}. {COPYRIGHT.replace('©', '(c)')}"


def aggiungi_foglio_info(wb, documento="", generato_il=""):
    """Aggiunge a un file Excel (openpyxl) l'ultimo foglio «Informazioni» con software, versione e proprieta'."""
    from openpyxl.styles import Alignment, Font
    if "Informazioni" in wb.sheetnames:
        return
    ws = wb.create_sheet("Informazioni")
    righe = [("Documento", documento or "-"), ("Generato il", generato_il or "-"), ("Software", f"{NOME} v{VERSIONE}"), ("Proprietà del software", PROPRIETARIO),
             ("Concesso in uso a", CLIENTE), ("Copyright", COPYRIGHT), ("Note", NOTE_LEGALI), ("Avvertenza", "Le proiezioni sono stime basate sui dati inseriti: non costituiscono consulenza finanziaria o legale.")]
    for i, (k, v) in enumerate(righe, start=1):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True)
        c = ws.cell(row=i, column=2, value=v)
        c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 100
