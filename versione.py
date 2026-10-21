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
