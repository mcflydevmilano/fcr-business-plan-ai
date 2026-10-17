"""
xbrl.py - Lettura del bilancio XBRL depositato al Registro Imprese (tassonomia italiana "itcc-ci").

Il file (.xbrl o .xml, anche dentro uno .zip) contiene i valori gia' strutturati: non serve l'AI e nessun dato
lascia il computer. L'output ha lo stesso formato dell'estrazione AI, cosi' passa dalla stessa schermata di
verifica e conferma.

Cautele:
- si usano solo i valori "senza dimensioni" (contesti senza scenario/segmento), cioe' i totali di bilancio;
- file con DOCTYPE/ENTITY sono rifiutati (protezione da attacchi XML);
- l'EBITDA non e' una voce di bilancio: e' calcolato (A-B + ammortamenti e svalutazioni) e segnalato come tale;
- la PFN e' calcolata (debiti finanziari - disponibilita' liquide) e segnalata come tale.
"""
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict

MAX_BYTES = 40 * 1024 * 1024

# nomi (minuscoli, senza prefisso) in ordine di preferenza; poi sottostringhe come ripiego
VOCI = {
    "ricavi": (["ricavivenditeprestazioni", "ricavidellevenditeedelleprestazioni", "ricavivenditeeprestazioni"],
               ["ricavivendite", "ricavidellevendite"]),
    "valore_produzione": (["totalevaloreproduzione", "valoreproduzione", "totalevaloredellaproduzione"],
                          ["totalevaloreproduzione", "totalevaloredellaproduzione"]),
    "ebit": (["differenzatravaloreecostiproduzione", "differenzavaloreecostiproduzione",
              "differenzatravaloreecostidellaproduzione"],
             ["differenzatravalore", "differenzavalore"]),
    "ammortamenti": (["totaleammortamentiesvalutazioni", "ammortamentiesvalutazioni"],
                     ["totaleammortamentiesvalutazioni", "ammortamentiesvalutazioni"]),
    "utile": (["utileperditaesercizio", "utileperditadellesercizio", "utileperdita"],
              ["utileperdita"]),
    "attivo": (["totaleattivo"], ["totaleattivo"]),
    "pn": (["totalepatrimonionetto", "patrimonionetto"], ["totalepatrimonionetto"]),
    "liquidita": (["totaledisponibilitaliquide", "disponibilitaliquide"], ["disponibilitaliquide"]),
}
# debiti finanziari: somma di queste voci (se esiste il totale lo si usa, altrimenti entro + oltre l'esercizio)
DEBITI_FIN = ["debitiversobanche", "debitiversoaltrifinanziatori", "obbligazioni", "obbligazioniconvertibili",
              "debitiversosocifinanziamenti"]


class XbrlError(ValueError):
    pass


def _apri(dati, nome=""):
    """Restituisce i byte XML: se e' uno zip prende il primo .xbrl/.xml."""
    if len(dati) > MAX_BYTES:
        raise XbrlError("File troppo grande.")
    if dati[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(dati)) as z:
                cand = [i for i in z.infolist()
                        if i.filename.lower().endswith((".xbrl", ".xml")) and not i.filename.startswith("__MACOSX")]
                if not cand:
                    raise XbrlError("Nello zip non c'e' nessun file .xbrl o .xml.")
                cand.sort(key=lambda i: (not i.filename.lower().endswith(".xbrl"), -i.file_size))
                info = cand[0]
                if info.file_size > MAX_BYTES:
                    raise XbrlError("Il file XBRL nello zip e' troppo grande.")
                return z.read(info)
        except zipfile.BadZipFile:
            raise XbrlError("Archivio zip non valido.")
    return dati


def _locale(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _data(s):
    m = re.match(r"\s*(\d{4})-(\d{2})-(\d{2})", s or "")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def _giorni(a, b):
    from datetime import date
    return (date(*b) - date(*a)).days


def leggi(dati, nome=""):
    """
    Legge un bilancio XBRL. Restituisce (raw, avvisi):
    raw nello stesso formato dell'estrazione AI (valori in euro), avvisi = lista di frasi per l'utente.
    """
    xml = _apri(dati, nome)
    testa = xml[:4096].upper()
    if b"<!DOCTYPE" in testa or b"<!ENTITY" in xml[:200000].upper():
        raise XbrlError("File XML non ammesso (contiene definizioni DOCTYPE/ENTITY).")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        raise XbrlError(f"File XML non leggibile: {e}")

    # --- contesti: solo quelli senza dimensioni -----------------------------------------
    contesti = {}
    for el in root.iter():
        if _locale(el.tag) != "context":
            continue
        cid = el.attrib.get("id")
        if not cid:
            continue
        ha_dim = any(_locale(x.tag) in ("scenario", "segment") and len(list(x)) > 0 for x in el.iter())
        if ha_dim:
            continue
        inizio = fine = istante = None
        for x in el.iter():
            n = _locale(x.tag)
            if n == "startDate":
                inizio = _data(x.text)
            elif n == "endDate":
                fine = _data(x.text)
            elif n == "instant":
                istante = _data(x.text)
        if istante:
            contesti[cid] = ("i", istante, istante)
        elif inizio and fine:
            contesti[cid] = ("d", inizio, fine)

    # --- fatti numerici: nome -> anno -> (valore, nome originale) ----------------------
    fatti = defaultdict(dict)
    for el in root.iter():
        rif = el.attrib.get("contextRef")
        if rif is None or rif not in contesti or el.attrib.get("{http://www.w3.org/2001/XMLSchema-instance}nil"):
            continue
        testo = (el.text or "").strip()
        if not testo:
            continue
        try:
            v = float(testo)
        except ValueError:
            continue
        tipo, a, b = contesti[rif]
        if tipo == "d" and not 300 <= _giorni(a, b) <= 400:
            continue                      # periodi diversi dall'esercizio annuale
        anno = b[0]
        nome_loc = _locale(el.tag)
        chiave = nome_loc.lower()
        # a parita' di nome e anno si tiene il primo (i duplicati coerenti sono identici)
        fatti[chiave].setdefault(anno, (v, nome_loc, b))

    if not fatti:
        raise XbrlError("Nel file non ho trovato valori di bilancio (e' davvero un bilancio XBRL?).")

    anni = sorted({a for d in fatti.values() for a in d}, reverse=True)
    # l'anno base e' il piu' recente per cui esiste almeno il totale attivo o i ricavi
    anno_base = next((a for a in anni if any(a in fatti.get(k, {}) for k in ("totaleattivo",))), anni[0])

    def cerca(voce, anno):
        esatti, parziali = VOCI[voce]
        for n in esatti:
            if n in fatti and anno in fatti[n]:
                return fatti[n][anno]
        for n in fatti:
            if anno in fatti[n] and any(n.startswith(p) or p in n for p in parziali) \
                    and not any(x in n for x in ("entro", "oltre", "variazion", "imposte")):
                return fatti[n][anno]
        return None

    def debiti_fin(anno):
        tot, nomi = 0.0, []
        for base in DEBITI_FIN:
            if base in fatti and anno in fatti[base]:
                tot += fatti[base][anno][0]
                nomi.append(fatti[base][anno][1])
                continue
            parti = [n for n in fatti if n.startswith(base) and anno in fatti[n] and ("entro" in n or "oltre" in n)]
            for n in parti:
                tot += fatti[n][anno][0]
                nomi.append(fatti[n][anno][1])
        return (tot, nomi) if nomi else (None, [])

    def valori(anno):
        out, fonti, mancanti = {}, {}, []

        def prendi(voce, chiave):
            r = cerca(voce, anno)
            if r:
                out[chiave] = r[0]
                fonti[chiave] = f"XBRL: {r[1]} (al {r[2][2]:02d}/{r[2][1]:02d}/{r[2][0]})"
            return r

        prendi("ricavi", "ricavi")
        prendi("utile", "utile_netto")
        prendi("attivo", "totale_attivo")
        prendi("pn", "patrimonio_netto")
        # EBITDA = (A - B) + ammortamenti e svalutazioni
        ebit = cerca("ebit", anno)
        amm = cerca("ammortamenti", anno)
        if ebit is None:
            vp, cp = cerca("valore_produzione", anno), fatti.get("totalecostiproduzione", {}).get(anno)
            if vp and cp:
                ebit = (vp[0] - cp[0], "A-B calcolato", vp[2])
        if ebit is not None:
            e = ebit[0] + (amm[0] if amm else 0.0)
            out["ebitda"] = e
            fonti["ebitda"] = ("CALCOLATO: differenza A-B (" + ebit[1] + ") + ammortamenti e svalutazioni (B.10)"
                               + ("" if amm else " [B.10 non trovato: considerato 0]"))
        deb, nomi_deb = debiti_fin(anno)
        liq = cerca("liquidita", anno)
        if deb is not None:
            out["debiti_finanziari_totali"] = deb
            fonti["debiti_finanziari_totali"] = "XBRL: somma di " + ", ".join(nomi_deb)
            out["pfn"] = deb - (liq[0] if liq else 0.0)
            fonti["pfn"] = ("CALCOLATO: debiti finanziari - disponibilita' liquide"
                            + ("" if liq else " [liquidita' non trovate: considerate 0]"))
        return out, fonti

    base, fonti = valori(anno_base)
    raw = {"anno_riferimento": anno_base, "valori_in_migliaia": False, "fonti": fonti}
    raw.update(base)

    storico = []
    for a in anni:
        if a >= anno_base:
            continue
        v, _ = valori(a)
        riga = {"anno": a, "ricavi": v.get("ricavi"), "ebitda": v.get("ebitda"),
                "patrimonio_netto": v.get("patrimonio_netto"), "pfn": v.get("pfn")}
        if any(riga[k] for k in ("ricavi", "ebitda", "patrimonio_netto", "pfn")):
            storico.append(riga)
    raw["storico"] = storico

    avvisi = []
    campi = {"ricavi": "ricavi", "ebitda": "EBITDA", "utile_netto": "utile netto", "totale_attivo": "totale attivo",
             "patrimonio_netto": "patrimonio netto", "debiti_finanziari_totali": "debiti finanziari", "pfn": "PFN"}
    manca = [n for k, n in campi.items() if k not in base]
    if manca:
        avvisi.append("Voci non trovate nel file (da inserire a mano): " + ", ".join(manca) + ".")
    avvisi.append("EBITDA e PFN non sono voci di bilancio: sono calcolati dal programma (vedi colonna Fonte) e "
                  "possono differire dalle definizioni usate dalla banca (es. accantonamenti, attivita' finanziarie "
                  "correnti, leasing).")
    return raw, avvisi
