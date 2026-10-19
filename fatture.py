"""
fatture.py - Lettura delle fatture elettroniche italiane (FatturaPA, file .xml o .xml.p7m) per alimentare lo Scadenzario.

Deterministico e senza Streamlit. Per ogni fattura produce una riga per ogni rata di pagamento:
  Tipo (Attiva/Passiva), Controparte, Documento, Data_doc, Scadenza, Importo (IVA inclusa, cioe' quanto entra/esce dal conto).

Regole:
  - Attiva se il cedente/prestatore (chi emette) e' la mia azienda, Passiva se lo e' il cessionario/committente (chi riceve).
  - Importo = ImportoPagamento della rata; se manca, ImportoTotaleDocumento (o imponibile + imposta) meno l'IVA in split payment.
  - Scadenza = DataScadenzaPagamento; se manca, data documento + 30 giorni (segnalato).
  - Note di credito (TD04, TD08) e documenti non fiscali: NON importati, segnalati (vanno ad abbattere la fattura collegata).
"""
import datetime as dt
import re
import xml.etree.ElementTree as ET


NOTE_CREDITO = {"TD04", "TD08"}
TIPI_FATTURA = {"TD01", "TD02", "TD03", "TD05", "TD06", "TD07", "TD24", "TD25", "TD26"}   # fatture, parcelle, acconti, note di debito...


def to_float(s):
    """Importi FatturaPA: punto decimale, senza separatore delle migliaia."""
    try:
        return float((s or "").strip())
    except ValueError:
        return 0.0


def _tag(e):
    return e.tag.split("}")[-1] if isinstance(e.tag, str) else ""


def _trova(e, *percorso):
    """Primo discendente che segue il percorso di nomi (senza namespace); None se manca."""
    cur = [e]
    for nome in percorso:
        prossimi = []
        for c in cur:
            prossimi += [x for x in c if _tag(x) == nome]
        if not prossimi:
            return None
        cur = prossimi
    return cur[0]


def _tutti(e, *percorso):
    cur = [e]
    for nome in percorso:
        prossimi = []
        for c in cur:
            prossimi += [x for x in c if _tag(x) == nome]
        cur = prossimi
    return cur


def _testo(e, *percorso):
    x = _trova(e, *percorso) if percorso else e
    return (x.text or "").strip() if x is not None and x.text else ""


def estrai_xml(dati):
    """Dai byte di un file .xml o .p7m (firma CAdES) restituisce il testo XML della fattura."""
    if isinstance(dati, str):
        dati = dati.encode("utf-8")
    i = dati.find(b"<?xml")
    if i < 0:
        m = re.search(rb"<(\w+:)?FatturaElettronica", dati)
        if not m:
            raise ValueError("Non e' una fattura elettronica (manca l'elemento FatturaElettronica).")
        i = m.start()
    m = re.search(rb"</(\w+:)?FatturaElettronica\s*>", dati[i:])
    fine = i + m.end() if m else len(dati)
    return dati[i:fine]


def _anagrafica(parte):
    """Denominazione (o nome e cognome) e partita IVA / codice fiscale di un cedente o cessionario."""
    d = _trova(parte, "DatiAnagrafici")
    if d is None:
        return "", ""
    nome = _testo(d, "Anagrafica", "Denominazione") or " ".join(x for x in (_testo(d, "Anagrafica", "Nome"), _testo(d, "Anagrafica", "Cognome")) if x)
    piva = _testo(d, "IdFiscaleIVA", "IdCodice") or _testo(d, "CodiceFiscale")
    return nome, piva.upper().replace(" ", "")


def _data(s):
    try:
        return dt.date.fromisoformat((s or "")[:10])
    except ValueError:
        return None


def leggi_fattura(dati):
    """Legge UNA fattura (byte o testo). Restituisce un dict con i dati grezzi, oppure solleva ValueError."""
    try:
        radice = ET.fromstring(estrai_xml(dati))
    except ET.ParseError as e:
        raise ValueError(f"XML non leggibile: {e}")
    if _tag(radice) != "FatturaElettronica":
        raise ValueError("Non e' una fattura elettronica.")
    ced, ces = _trova(radice, "FatturaElettronicaHeader", "CedentePrestatore"), _trova(radice, "FatturaElettronicaHeader", "CessionarioCommittente")
    if ced is None or ces is None:
        raise ValueError("Intestazione della fattura incompleta (cedente o cessionario mancante).")
    corpi = _tutti(radice, "FatturaElettronicaBody")
    if not corpi:
        raise ValueError("La fattura non ha un corpo (FatturaElettronicaBody).")
    nome_ced, piva_ced = _anagrafica(ced)
    nome_ces, piva_ces = _anagrafica(ces)
    docs = []
    for corpo in corpi:                       # un file puo' contenere piu' fatture (lotto)
        dg = _trova(corpo, "DatiGenerali", "DatiGeneraliDocumento")
        if dg is None:
            continue
        riepiloghi = _tutti(corpo, "DatiBeniServizi", "DatiRiepilogo")
        imponibile = sum(to_float(_testo(r, "ImponibileImporto")) or 0 for r in riepiloghi)
        imposta = sum(to_float(_testo(r, "Imposta")) or 0 for r in riepiloghi)
        split = sum(to_float(_testo(r, "Imposta")) or 0 for r in riepiloghi if _testo(r, "EsigibilitaIVA") == "S")
        totale = to_float(_testo(dg, "ImportoTotaleDocumento"))
        if not totale:
            totale = imponibile + imposta
        rate = []
        for p in _tutti(corpo, "DatiPagamento", "DettaglioPagamento"):
            imp = to_float(_testo(p, "ImportoPagamento"))
            if imp:
                rate.append({"scadenza": _data(_testo(p, "DataScadenzaPagamento")), "importo": imp})
        docs.append({"tipo_doc": _testo(dg, "TipoDocumento"), "numero": _testo(dg, "Numero"), "data": _data(_testo(dg, "Data")),
                     "totale": totale, "split": split, "rate": rate, "causale": " ".join(_testo(c) for c in _tutti(dg, "Causale"))[:120]})
    if not docs:
        raise ValueError("Nessun documento leggibile nella fattura.")
    return {"cedente": nome_ced, "piva_cedente": piva_ced, "cessionario": nome_ces, "piva_cessionario": piva_ces, "documenti": docs}


def _norm_id(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper()).removeprefix("IT")


def piva_probabile(fatture):
    """Partita IVA che compare in piu' fatture (di solito e' la tua azienda). None se non determinabile."""
    conta = {}
    for f in fatture:
        for k in {_norm_id(f["piva_cedente"]), _norm_id(f["piva_cessionario"])}:
            if k:
                conta[k] = conta.get(k, 0) + 1
    if not conta:
        return None
    k, n = max(conta.items(), key=lambda kv: kv[1])
    return k if n >= 2 or len(fatture) == 1 else None


def righe_scadenzario(fatture, mia_piva, nome_file=None):
    """Da fatture lette -> (righe, avvisi). `mia_piva`: partita IVA della tua azienda (con o senza IT).
    Ogni riga: dict con le colonne di sc.COLONNE_DOC (Saldato = 0, Cantiere vuoto)."""
    mia = _norm_id(mia_piva)
    righe, avvisi = [], []
    for i, f in enumerate(fatture):
        etichetta = (nome_file[i] if nome_file else f"fattura {i + 1}")
        e_ced, e_ces = _norm_id(f["piva_cedente"]) == mia and mia, _norm_id(f["piva_cessionario"]) == mia and mia
        if e_ced:
            tipo, controparte = "Attiva", f["cessionario"]
        elif e_ces:
            tipo, controparte = "Passiva", f["cedente"]
        else:
            avvisi.append(f"{etichetta}: non riconosco la tua partita IVA ({f['piva_cedente'] or '?'} → {f['piva_cessionario'] or '?'}); riga saltata.")
            continue
        for d in f["documenti"]:
            if d["tipo_doc"] in NOTE_CREDITO:
                avvisi.append(f"{etichetta}: nota di credito {d['numero']} non importata (riduci a mano la fattura collegata).")
                continue
            if d["tipo_doc"] and d["tipo_doc"] not in TIPI_FATTURA:
                avvisi.append(f"{etichetta}: documento {d['numero']} di tipo {d['tipo_doc']} non importato.")
                continue
            rate = d["rate"]
            if not rate:
                importo = d["totale"] - d["split"]
                if importo <= 0:
                    avvisi.append(f"{etichetta}: importo non trovato, riga saltata.")
                    continue
                base = d["data"] or dt.date.today()
                rate = [{"scadenza": base + dt.timedelta(days=30), "importo": importo}]
                avvisi.append(f"{etichetta}: nessuna scadenza indicata, stimata a 30 giorni dalla data fattura.")
            n = len(rate)
            for k, r in enumerate(rate, 1):
                sc = r["scadenza"]
                if sc is None:
                    sc = (d["data"] or dt.date.today()) + dt.timedelta(days=30)
                    avvisi.append(f"{etichetta}: rata {k} senza scadenza, stimata a 30 giorni.")
                righe.append({"Tipo": tipo, "Controparte": controparte, "Cantiere": "", "Documento": d["numero"] + (f" (rata {k}/{n})" if n > 1 else ""),
                              "Data_doc": d["data"].isoformat() if d["data"] else "", "Scadenza": sc.isoformat(), "Importo": round(r["importo"], 2), "Saldato": 0})
    return righe, avvisi


def senza_duplicati(righe, esistenti):
    """Toglie le righe gia' presenti (stessa controparte, numero e data documento). `esistenti`: lista di dict."""
    chiave = lambda r: (str(r.get("Tipo", "")), str(r.get("Controparte", "")).strip().lower(), str(r.get("Documento", "")).strip().lower(), str(r.get("Data_doc", ""))[:10], round(float(r.get("Importo") or 0), 2))
    visti = {chiave(r) for r in esistenti}
    nuove, doppie = [], 0
    for r in righe:
        if chiave(r) in visti:
            doppie += 1
        else:
            nuove.append(r)
            visti.add(chiave(r))
    return nuove, doppie
