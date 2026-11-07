"""
fe.py - Fatture elettroniche (FatturaPA, file XML / .p7m / .zip dallo SdI): lettura e passaggio allo Scadenzario.
Legge fornitore, numero, data, importi, scadenze di pagamento e causale; propone il cantiere cercando il codice nel testo. Senza Streamlit (testabile).
"""
import datetime as dt
import io
import re
import xml.etree.ElementTree as ET
import zipfile

TIPI_NOTA_CREDITO = {"TD04", "TD08"}
GIORNI_SCADENZA_STIMATA = 30


def _senza_ns(tag):
    return tag.rsplit("}", 1)[-1]


def _f(el, percorso, default=""):
    """Testo del primo discendente che segue il percorso (nomi senza namespace, separati da /)."""
    cur = [el]
    for nome in percorso.split("/"):
        nxt = []
        for c in cur:
            nxt += [x for x in c if _senza_ns(x.tag) == nome]
        if not nxt:
            return default
        cur = nxt
    return (cur[0].text or "").strip() or default


def _tutti(el, percorso):
    cur = [el]
    for nome in percorso.split("/"):
        cur = [x for c in cur for x in c if _senza_ns(x.tag) == nome]
    return cur


def _num(v):
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return 0.0


def _xml_da_p7m(dati):
    """Dentro un file firmato (.p7m) l'XML e' in chiaro: lo si ritaglia."""
    m = re.search(rb"<\?xml.*?</(?:\w+:)?FatturaElettronica>", dati, re.S)
    return m.group(0) if m else dati


def _anagrafica(el):
    d = _f(el, "DatiAnagrafici/Anagrafica/Denominazione")
    if not d:
        d = " ".join(x for x in (_f(el, "DatiAnagrafici/Anagrafica/Nome"), _f(el, "DatiAnagrafici/Anagrafica/Cognome")) if x)
    piva = _f(el, "DatiAnagrafici/IdFiscaleIVA/IdCodice") or _f(el, "DatiAnagrafici/CodiceFiscale")
    return d, piva


def leggi_xml(dati, nome_file=""):
    """Elenco di fatture (un file puo' contenerne piu' di una). Solleva ValueError se non e' una fattura elettronica."""
    if isinstance(dati, str):
        dati = dati.encode("utf-8")
    if not dati.lstrip()[:1] == b"<":
        dati = _xml_da_p7m(dati)
    try:
        radice = ET.fromstring(dati)
    except ET.ParseError as ex:
        raise ValueError(f"{nome_file or 'file'}: non è una fattura elettronica leggibile ({ex})")
    if _senza_ns(radice.tag) != "FatturaElettronica":
        raise ValueError(f"{nome_file or 'file'}: non è una fattura elettronica.")
    head = next((x for x in radice if _senza_ns(x.tag) == "FatturaElettronicaHeader"), None)
    if head is None:
        raise ValueError(f"{nome_file or 'file'}: manca l'intestazione della fattura.")
    ced, piva_c = _anagrafica(next((x for x in head if _senza_ns(x.tag) == "CedentePrestatore"), head))
    ces, piva_s = _anagrafica(next((x for x in head if _senza_ns(x.tag) == "CessionarioCommittente"), head))
    out = []
    for body in [x for x in radice if _senza_ns(x.tag) == "FatturaElettronicaBody"]:
        tipo = _f(body, "DatiGenerali/DatiGeneraliDocumento/TipoDocumento", "TD01")
        segno = -1.0 if tipo in TIPI_NOTA_CREDITO else 1.0
        totale = _num(_f(body, "DatiGenerali/DatiGeneraliDocumento/ImportoTotaleDocumento"))
        riepi = _tutti(body, "DatiBeniServizi/DatiRiepilogo")
        imponibile = sum(_num(_f(r, "ImponibileImporto")) for r in riepi)
        iva = sum(_num(_f(r, "Imposta")) for r in riepi)
        if not totale:
            totale = imponibile + iva
        scad = []
        for p in _tutti(body, "DatiPagamento/DettaglioPagamento"):
            s = _f(p, "DataScadenzaPagamento")
            imp = _num(_f(p, "ImportoPagamento"))
            if imp or s:
                scad.append({"data": s, "importo": imp, "modalita": _f(p, "ModalitaPagamento")})
        desc = [(_f(r, "Descrizione")) for r in _tutti(body, "DatiBeniServizi/DettaglioLinee")][:30]
        causali = " ".join((c.text or "").strip() for c in _tutti(body, "DatiGenerali/DatiGeneraliDocumento/Causale"))
        cig = _f(body, "DatiGenerali/DatiOrdineAcquisto/CodiceCIG") or _f(body, "DatiGenerali/DatiContratto/CodiceCIG")
        cup = _f(body, "DatiGenerali/DatiOrdineAcquisto/CodiceCUP") or _f(body, "DatiGenerali/DatiContratto/CodiceCUP")
        out.append({"file": nome_file, "tipo_doc": tipo, "nota_credito": tipo in TIPI_NOTA_CREDITO, "fornitore": ced, "piva_fornitore": piva_c, "cliente": ces, "piva_cliente": piva_s,
                    "numero": _f(body, "DatiGenerali/DatiGeneraliDocumento/Numero"), "data": _f(body, "DatiGenerali/DatiGeneraliDocumento/Data"),
                    "totale": round(segno * totale, 2), "imponibile": round(segno * imponibile, 2), "iva": round(segno * iva, 2), "divisa": _f(body, "DatiGenerali/DatiGeneraliDocumento/Divisa", "EUR"),
                    "scadenze": scad, "causale": causali, "descrizioni": [d for d in desc if d], "cig": cig, "cup": cup})
    if not out:
        raise ValueError(f"{nome_file or 'file'}: nessuna fattura dentro il file.")
    return out


def leggi_file(nome, dati):
    """Un file qualsiasi caricato: XML, .p7m o .zip con molti file. Restituisce (fatture, errori)."""
    fatture, errori = [], []
    n = (nome or "").lower()
    if n.endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(dati)) as z:
                for i in z.namelist():
                    if i.lower().endswith((".xml", ".p7m")) and not i.startswith("__MACOSX"):
                        f, e = leggi_file(i, z.read(i))
                        fatture += f
                        errori += e
        except zipfile.BadZipFile:
            errori.append(f"{nome}: archivio zip non valido.")
        return fatture, errori
    try:
        fatture += leggi_xml(dati, nome)
    except ValueError as ex:
        errori.append(str(ex))
    return fatture, errori


def _d(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def suggerisci_cantiere(fattura, cantieri):
    """Codice del cantiere se compare nel testo della fattura (causale, descrizioni, CIG/CUP). Vuoto se non si capisce."""
    testo = " ".join([fattura.get("causale", ""), fattura.get("cig", ""), fattura.get("cup", "")] + list(fattura.get("descrizioni") or [])).lower()
    for c in cantieri or []:
        cod = str(c.get("Codice") or "").strip().lower()
        if len(cod) >= 3 and cod in testo:
            return c["Codice"]
    return ""


def chiave(f):
    return (re.sub(r"\W", "", f.get("piva_fornitore", "")).lower(), str(f.get("numero", "")).strip().lower(), f.get("data", ""))


def duplicati(fatture, documenti_esistenti):
    """Fatture gia' presenti nello Scadenzario (stesso numero e stessa controparte)."""
    noti = {(str(d.get("Documento", "")).strip().lower(), str(d.get("Controparte", "")).strip().lower()) for d in documenti_esistenti or []}
    return [f for f in fatture if (f"fattura n. {f['numero']}".lower(), f["fornitore"].strip().lower()) in noti or (f"fattura n. {f['numero']}".lower(), f["cliente"].strip().lower()) in noti]


def a_scadenzario(fatture, direzione="Passiva", cantieri_per_fattura=None):
    """Righe per lo Scadenzario (colonne di sc.COLONNE_DOC): una per ogni scadenza di pagamento. Le note di credito si saltano (si trattano a mano)."""
    cantieri_per_fattura = cantieri_per_fattura or {}
    righe, saltate = [], []
    for i, f in enumerate(fatture):
        if f["nota_credito"]:
            saltate.append(f"{f['fornitore']} n. {f['numero']}: nota di credito, da trattare a mano")
            continue
        controparte = f["fornitore"] if direzione == "Passiva" else f["cliente"]
        scad = f["scadenze"] or []
        if not scad:
            base = _d(f["data"]) or dt.date.today()
            scad = [{"data": (base + dt.timedelta(days=GIORNI_SCADENZA_STIMATA)).isoformat(), "importo": f["totale"], "modalita": ""}]
            saltate.append(f"{controparte} n. {f['numero']}: scadenza non indicata, stimata a {GIORNI_SCADENZA_STIMATA} giorni")
        for s in scad:
            righe.append({"Tipo": direzione, "Controparte": controparte, "Cantiere": cantieri_per_fattura.get(i, ""), "Documento": f"Fattura n. {f['numero']}",
                          "Data_doc": f["data"], "Scadenza": s["data"] or f["data"], "Importo": s["importo"] or f["totale"], "Saldato": 0.0})
    return righe, saltate
