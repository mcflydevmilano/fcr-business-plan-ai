"""bd.py - Lettura di bandi e capitolati: estrae scadenze, importi, requisiti e documenti richiesti (sempre da controllare)."""
import json
import re

import ai

DOCUMENTI = [("DGUE", r"\bDGUE\b|documento di gara unico"), ("DURC", r"\bDURC\b"), ("Polizza / garanzia provvisoria", r"polizza|garanzia provvisoria|cauzione provvisoria|fideiussione"),
             ("Attestazione SOA", r"\bSOA\b|attestazione di qualificazione"), ("Visura camerale", r"visura|camera di commercio|CCIAA"),
             ("Sopralluogo", r"sopralluogo"), ("Patto di integrità", r"patto di integrit"), ("Pagamento contributo ANAC", r"contributo.{0,20}ANAC|ANAC.{0,30}contributo"),
             ("Offerta tecnica", r"offerta tecnica"), ("Offerta economica", r"offerta economica"), ("Avvalimento", r"avvalimento"),
             ("Subappalto: dichiarazione", r"subappalto"), ("Cronoprogramma", r"cronoprogramma"), ("Piano di sicurezza (POS)", r"\bPOS\b|piano operativo di sicurezza")]
MESI = {"gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12}

PROMPT = ("Sei un assistente di un'impresa edile. Dal testo del bando o capitolato estrai SOLO ciò che c'è scritto, senza inventare. Rispondi con un JSON con queste chiavi: "
          "oggetto (stringa), stazione_appaltante (stringa), cig (stringa), cup (stringa), importo_base (numero in euro o null), scadenza_offerte (AAAA-MM-GG o null), "
          "sopralluogo_obbligatorio (true/false/null), categorie_soa (lista di stringhe), requisiti (lista di frasi brevi), documenti_richiesti (lista di stringhe), note (stringa). "
          "Se un dato non c'è, lascia null o lista vuota.")


def _num(s):
    s = s.replace("€", "").replace(" ", "").strip().rstrip(".,")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1 or re.fullmatch(r"\d{1,3}\.\d{3}", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def _data(t):
    m = re.search(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](20\d\d)", t)
    if m:
        g, me, a = map(int, m.groups())
    else:
        m = re.search(r"(\d{1,2})\s+(" + "|".join(MESI) + r")\s+(20\d\d)", t, re.I)
        if not m:
            return None
        g, me, a = int(m.group(1)), MESI[m.group(2).lower()], int(m.group(3))
    return f"{a:04d}-{me:02d}-{g:02d}" if 1 <= me <= 12 and 1 <= g <= 31 else None


def estrai_regole(testo):
    """Estrazione senza IA: codici, importi, date e documenti riconoscibili dalle parole."""
    t = testo or ""
    out = {"oggetto": "", "stazione_appaltante": "", "cig": "", "cup": "", "importo_base": None, "scadenza_offerte": None, "sopralluogo_obbligatorio": None,
           "categorie_soa": [], "requisiti": [], "documenti_richiesti": [], "note": ""}
    m = re.search(r"\bCIG\b[\s:.\-]*([A-Z0-9]{10})\b", t, re.I)
    out["cig"] = m.group(1).upper() if m else ""
    m = re.search(r"\bCUP\b[\s:.\-]*([A-Z]\d{2}[A-Z0-9]{12})\b", t, re.I)
    out["cup"] = m.group(1).upper() if m else ""
    for m in re.finditer(r"(?:importo|base d'asta|base di gara)[^\n€\d]{0,80}(?:€|euro)?\s*([\d.]+(?:,\d{1,2})?)", t, re.I):
        v = _num(m.group(1))
        if v and v >= 1000:
            out["importo_base"] = v
            break
    for m in re.finditer(r"(?:scadenza|termine|entro (?:e non oltre )?(?:il|le ore)|presentazione delle offerte)[^\n]{0,120}", t, re.I):
        d = _data(m.group(0))
        if d:
            out["scadenza_offerte"] = d
            break
    out["categorie_soa"] = sorted({x.upper() for x in re.findall(r"\b(O[GS]\s?\d{1,2})\b", t, re.I)}, key=str)
    out["categorie_soa"] = [re.sub(r"\s", "", x) for x in out["categorie_soa"]]
    m = re.search(r"sopralluogo[^.\n]{0,100}", t, re.I)
    if m:
        out["sopralluogo_obbligatorio"] = bool(re.search(r"obbligator", m.group(0), re.I)) or None
    out["documenti_richiesti"] = [n for n, rx in DOCUMENTI if re.search(rx, t, re.I)]
    m = re.search(r"(?:oggetto(?: dell'appalto| della gara)?|lavori di)[:\s]+([^\n]{10,200})", t, re.I)
    out["oggetto"] = m.group(1).strip() if m else ""
    return out


def estrai_ai(ai_generate, key, testo):
    """Chiede all'IA la stessa scheda; in caso di errore o risposta non valida restituisce None."""
    try:
        raw, _ = ai_generate(key, [PROMPT, "TESTO:\n" + testo[:120000]], json_mode=True, temperature=0.0)
        d = json.loads(raw)
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def unisci(regole, ia):
    """Dati dell'IA, completati con quelli trovati dalle regole dove l'IA non ha trovato niente."""
    out = dict(regole)
    for k, v in (ia or {}).items():
        if k in out and v not in (None, "", []):
            out[k] = v
    return out


def checklist(sch):
    """Elenco di cose da preparare, in ordine."""
    righe = []
    if sch.get("scadenza_offerte"):
        righe.append(f"Consegnare l'offerta entro il {sch['scadenza_offerte']}")
    if sch.get("sopralluogo_obbligatorio"):
        righe.append("Prenotare il sopralluogo (obbligatorio)")
    for c in sch.get("categorie_soa") or []:
        righe.append(f"Verificare di avere la SOA per la categoria {c}")
    righe += [f"Preparare: {d}" for d in sch.get("documenti_richiesti") or [] if d != "Sopralluogo"]
    righe += [f"Requisito da verificare: {x}" for x in sch.get("requisiti") or []]
    return righe


def pdf_testo(dati):
    t, _n = ai.testo_da_pdf(dati, min_car=50)
    return t or ""
