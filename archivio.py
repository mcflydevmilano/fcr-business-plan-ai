"""
archivio.py - Struttura delle cartelle sul NAS (condivisa «fcr») e collegamento con i cantieri della suite.
Regola: area numerata -> cartella del cantiere «CODICE - Nome» -> file. Il CODICE e' quello usato in azienda (campo «codice in altro sistema»,
es. F100) oppure, se manca, il codice della Rubrica (CAN-...). Senza Streamlit.
Variabili d'ambiente: FCR_NAS_UNC (percorso che vedono i colleghi in Windows, predefinito \\\\192.168.1.240\\fcr) e FCR_NAS_PATH
(dove la share «fcr» e' montata sul server, predefinito /mnt/nas) - serve solo per creare le cartelle dalla suite.
"""
import os
import re

# (numero, nome cartella, una cartella per cantiere?, chi la usa, descrizione)
AREE = [
    ("01", "Commerciale", False, "direzione, commerciali", "Offerte, clienti, contatti commerciali."),
    ("02", "Tecnico Commerciale", True, "direzione, amministrazione, tecnici, igc", "Rilievi e sopralluoghi prima dell'offerta."),
    ("03", "Progetti", True, "direzione, amministrazione, tecnici, igc", "Disegni, relazioni, pratiche tecniche."),
    ("04", "CME", True, "direzione, tecnici, igc (amministrazione legge)", "Computi metrici estimativi e preventivi."),
    ("05", "Contratti", True, "direzione, amministrazione (igc legge)", "Contratti con clienti, subappaltatori e fornitori."),
    ("06", "Contabilita Cantieri", True, "direzione, tecnici, igc (amministrazione legge)", "SAL, contabilità, fatture del cantiere."),
    ("07", "Finanza", False, "direzione, amministrazione", "Banche, finanziamenti, flussi di cassa."),
    ("08", "Amministrazione", False, "direzione, amministrazione", "Bilancio, auto aziendali, procedure, documenti aziendali, carta intestata."),
    ("09", "Sicurezza e Certificazioni", True, "da definire", "POS, DURC, certificazioni, documenti di sicurezza."),
    ("10", "Foto e Drone", True, "da definire", "Foto di cantiere e riprese con il drone."),
    ("90", "Archivio storico", False, "sola lettura per quasi tutti", "Le vecchie cartelle F100… così come sono, senza smontarle."),
    ("99", "Backup suite", False, "solo amministratori", "Copie di sicurezza della suite."),
]
NOME_AREA = {a[0]: f"{a[0]} {a[1]}" for a in AREE}
_VIETATI = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def base_unc():
    return (os.environ.get("FCR_NAS_UNC", "").strip() or r"\\192.168.1.240\fcr").rstrip("\\")


def base_montaggio():
    return os.environ.get("FCR_NAS_PATH", "").strip() or "/mnt/nas"


def montato():
    p = base_montaggio()
    return os.path.isdir(p) and os.path.ismount(p)


def nome_cantiere(c):
    """«F100 - Villa Lago»: codice aziendale (o della Rubrica) e nome, senza caratteri vietati da Windows."""
    cod = _VIETATI.sub("", str(c.get("Esterno") or c.get("Codice") or "").strip()).strip(" .")
    nome = _VIETATI.sub("", str(c.get("Cantiere") or "").strip()).rstrip(" .")
    return " - ".join(x for x in (cod, nome) if x)[:120]


def percorsi(c, radice=None):
    """Elenco delle cartelle del cantiere: [{numero, area, cartella, unc, esiste}]. `esiste` e' None se il NAS non e' montato sul server."""
    radice = radice if radice is not None else (base_montaggio() if montato() else None)
    nc = nome_cantiere(c)
    out = []
    for num, nome, per_c, chi, desc in AREE:
        if not per_c or not nc:
            continue
        area = NOME_AREA[num]
        esiste = None
        if radice:
            cod = (_VIETATI.sub("", str(c.get("Esterno") or c.get("Codice") or "")).strip())
            d = os.path.join(radice, area)
            try:
                esiste = os.path.isdir(os.path.join(d, nc)) or bool(cod) and any(x.lower().startswith(cod.lower() + " ") and os.path.isdir(os.path.join(d, x)) for x in os.listdir(d))
            except OSError:
                esiste = False
        out.append({"numero": num, "area": area, "cartella": nc, "unc": f"{base_unc()}\\{area}\\{nc}", "esiste": esiste, "chi": chi})
    return out


def crea_cartelle(c, radice=None):
    """Crea le cartelle mancanti del cantiere sul NAS montato. Restituisce (create, gia_presenti). Solleva OSError se il NAS non e' montato."""
    radice = radice or base_montaggio()
    if not os.path.isdir(radice):
        raise OSError("Il NAS non è collegato al server.")
    nc = nome_cantiere(c)
    if not nc:
        return 0, 0
    reale = os.path.realpath(radice)
    nuove = vecchie = 0
    for p in percorsi(c, radice):
        d = os.path.join(radice, p["area"], nc)
        if os.path.commonpath([reale, os.path.realpath(d)]) != reale:
            continue                                                   # difesa: mai fuori dalla radice
        if p["esiste"]:
            vecchie += 1
        else:
            os.makedirs(d, exist_ok=True)
            nuove += 1
    return nuove, vecchie
