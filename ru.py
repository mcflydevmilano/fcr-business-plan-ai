"""
ru.py - Rubrica contatti e registro cantieri con codice unico. Deterministico e senza Streamlit.
Il codice cantiere (es. CAN-2026-007) e' la chiave comune: lo stesso codice si scrive nelle altre tabelle (fatture, rapportini, cronoprogramma)
e nei sistemi esterni (per esempio monday) per ritrovare tutto di un lavoro.
"""
import re
import urllib.parse

from sc import data_da

RUOLI = ["Fornitore", "Subappaltatore", "Cliente", "Professionista", "Ente / PA", "Banca", "Studio legale", "Altro"]
COLONNE_CONTATTI = ["Nome", "Ruolo", "Referente", "Telefono", "Email", "Note"]
ETICHETTE_CONTATTI = {"Nome": "Ragione sociale", "Ruolo": "Tipo", "Referente": "Persona di riferimento", "Telefono": "Telefono / cellulare", "Email": "Email", "Note": "Note"}
SINONIMI_CONTATTI = {"Nome": ("Ragione sociale", "Anagrafica", "Fornitore", "Cliente"), "Telefono": ("Tel", "Cellulare", "Telefono / cellulare"), "Email": ("Mail", "E-mail", "PEC"),
                     "Referente": ("Contatto", "Persona di riferimento")}
STATI_CANTIERE = ["In preparazione", "In corso", "Sospeso", "Concluso"]
COLONNE_CANTIERI = ["Codice", "Cantiere", "Cliente", "Indirizzo", "Responsabile", "Stato", "Esterno"]
ETICHETTE_CANTIERI = {"Codice": "Codice unico", "Cantiere": "Nome del cantiere", "Cliente": "Cliente", "Indirizzo": "Indirizzo", "Responsabile": "Responsabile",
                      "Stato": "Stato", "Esterno": "Codice in altro sistema (es. monday)"}
_RE_MAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _t(v):
    return "" if v is None or v != v else str(v).strip()


def pulisci_telefono(t):
    """Lascia cifre e il + iniziale. Un numero italiano senza prefisso resta cosi' com'e' (il link usa +39 solo per WhatsApp)."""
    t = _t(t)
    return ("+" if t.startswith("+") else "") + re.sub(r"\D", "", t)


def numero_internazionale(t):
    n = pulisci_telefono(t)
    if n.startswith("+"):
        return n[1:]
    if n.startswith("00"):
        return n[2:]
    return ("39" + n) if n else ""


def link_chiama(t):
    n = pulisci_telefono(t)
    return f"tel:{n}" if n else ""


def link_whatsapp(t, testo=""):
    n = numero_internazionale(t)
    return f"https://wa.me/{n}" + (f"?text={urllib.parse.quote(testo)}" if testo else "") if n else ""


def link_email(m, oggetto="", corpo=""):
    m = _t(m)
    if not _RE_MAIL.match(m):
        return ""
    q = urllib.parse.urlencode({k: v for k, v in (("subject", oggetto), ("body", corpo)) if v}, quote_via=urllib.parse.quote)
    return f"mailto:{m}" + (f"?{q}" if q else "")


def normalizza_contatti(righe):
    out, avvisi, visti = [], [], set()
    for i, r in enumerate(righe or [], start=1):
        if not any(_t(r.get(c)) for c in COLONNE_CONTATTI):
            continue
        n = _t(r.get("Nome"))
        if not n:
            avvisi.append(f"Contatto, riga {i}: manca il nome, riga ignorata.")
            continue
        if n.lower() in visti:
            avvisi.append(f"«{n}» compare più volte nella rubrica: tienine una sola riga.")
        visti.add(n.lower())
        ruolo = _t(r.get("Ruolo"))
        mail = _t(r.get("Email"))
        if mail and not _RE_MAIL.match(mail):
            avvisi.append(f"«{n}»: l'email «{mail}» non sembra valida.")
        out.append({"Nome": n, "Ruolo": ruolo if ruolo in RUOLI else "Altro", "Referente": _t(r.get("Referente")), "Telefono": _t(r.get("Telefono")), "Email": mail, "Note": _t(r.get("Note"))})
    return out, avvisi


def prossimo_codice(cantieri, anno):
    """CAN-<anno>-<progressivo> successivo a quelli gia' presenti per quell'anno."""
    mx = 0
    for c in cantieri or []:
        m = re.match(rf"^CAN-{anno}-(\d+)$", _t(c.get("Codice")))
        if m:
            mx = max(mx, int(m.group(1)))
    return f"CAN-{anno}-{mx + 1:03d}"


def normalizza_cantieri(righe, anno=None):
    """Pulisce i cantieri; assegna il codice ai cantieri che non l'hanno e segnala i codici doppi."""
    anno = anno or data_da(None, __import__("datetime").date.today()).year
    base = [dict(r) for r in (righe or [])]
    out, avvisi, usati = [], [], set()
    for i, r in enumerate(base, start=1):
        if not any(_t(r.get(c)) for c in COLONNE_CANTIERI):
            continue
        nome = _t(r.get("Cantiere"))
        if not nome:
            avvisi.append(f"Cantiere, riga {i}: manca il nome, riga ignorata.")
            continue
        cod = _t(r.get("Codice")).upper()
        if not cod:
            cod = prossimo_codice([*out, *[{"Codice": _t(x.get("Codice")).upper()} for x in base]], anno)
        if cod in usati:
            avvisi.append(f"Il codice {cod} è usato da più di un cantiere: il codice deve essere unico.")
        usati.add(cod)
        st = _t(r.get("Stato"))
        out.append({"Codice": cod, "Cantiere": nome, "Cliente": _t(r.get("Cliente")), "Indirizzo": _t(r.get("Indirizzo")), "Responsabile": _t(r.get("Responsabile")),
                    "Stato": st if st in STATI_CANTIERE else "In corso", "Esterno": _t(r.get("Esterno"))})
    return out, avvisi


def collegamenti(contatto, docs_fornitori=None, fatture=None, cantieri=None):
    """Tutto cio' che riguarda un contatto: documenti del fornitore, fatture (aperte e chiuse) e cantieri dove compare come cliente o responsabile."""
    n = contatto["Nome"].lower()
    docs = [d for d in (docs_fornitori or []) if d["Fornitore"].lower() == n]
    fat = [f for f in (fatture or []) if f["Controparte"].lower() == n]
    can = [c for c in (cantieri or []) if c["Cliente"].lower() == n or c["Responsabile"].lower() in (n, contatto["Referente"].lower() or "\0")]
    aperto = sum(f["Importo"] - f["Saldato"] for f in fat if f["Importo"] - f["Saldato"] > 0)
    return {"documenti": docs, "fatture": fat, "cantieri": can, "aperto": aperto}


def calcola_ru(contatti, cantieri):
    avvisi = []
    senza_rec = [c["Nome"] for c in contatti if not c["Telefono"] and not c["Email"]]
    if senza_rec:
        avvisi.append(f"{len(senza_rec)} contatti senza telefono né email: " + ", ".join(senza_rec[:6]) + ("…" if len(senza_rec) > 6 else "") + ".")
    senza_ext = [c["Codice"] for c in cantieri if not c["Esterno"]]
    kpi = {"contatti": len(contatti), "cantieri": len(cantieri), "in_corso": sum(1 for c in cantieri if c["Stato"] == "In corso"), "senza_recapito": len(senza_rec),
           "per_ruolo": {r: sum(1 for c in contatti if c["Ruolo"] == r) for r in RUOLI if any(c["Ruolo"] == r for c in contatti)}, "senza_codice_esterno": len(senza_ext)}
    return {"kpi": kpi, "avvisi": avvisi}
