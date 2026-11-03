"""
simil.py - Somiglianza tra testi scritti in modo diverso («Intonaco civile 2 mani» ~ «Intonacatura civile a due strati»).
Deterministico, senza rete: toglie accenti, punteggiatura e parole vuote, riduce le parole alla radice e confronta.
Serve a suggerire (mai a decidere): l'utente conferma sempre.
"""
import difflib
import re
import unicodedata

VUOTE = {"di", "a", "da", "in", "con", "su", "per", "tra", "fra", "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "e", "ed", "o", "del", "dello", "della", "dei", "degli", "delle",
         "al", "allo", "alla", "ai", "agli", "alle", "dal", "dalla", "nel", "nello", "nella", "nei", "sul", "sulla", "compreso", "compresa", "inclusi", "incluso", "fornitura", "posa", "opera",
         "eseguito", "eseguita", "mano", "mani", "n", "nr", "tipo", "cad", "cadauno", "mq", "mc", "ml", "kg", "pz", "m"}
NUMERI = {"uno": "1", "una": "1", "due": "2", "tre": "3", "quattro": "4", "cinque": "5", "sei": "6", "sette": "7", "otto": "8", "nove": "9", "dieci": "10"}


def _senza_accenti(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "")) if unicodedata.category(c) != "Mn")


def radice(p):
    """Radice grossolana: toglie le vocali finali e i suffissi piu' comuni (intonaco/intonacatura -> intonac)."""
    p = NUMERI.get(p, p)
    if p.isdigit() or len(p) <= 3:
        return p
    for suf in ("atura", "azione", "amento", "imento", "mento", "zione", "tura", "ura", "ione", "ura", "ico", "ica", "ici", "ichi", "iche", "ale", "ali", "ere", "are", "ire"):
        if p.endswith(suf) and len(p) - len(suf) >= 4:
            p = p[:-len(suf)]
            break
    while len(p) > 4 and p[-1] in "aeiou":
        p = p[:-1]
    return p


def parole(testo):
    t = _senza_accenti(str(testo or "").lower())
    t = re.sub(r"(\d+)[,.](\d+)", r"\1\2", t)
    out = []
    for w in re.findall(r"[a-z0-9]+", t):
        if w in VUOTE:
            continue
        out.append(radice(w))
    return out


def chiave(testo):
    return " ".join(sorted(set(parole(testo))))


def similarita(a, b):
    """0..1. Massimo tra: parole in comune (Jaccard), parole di uno contenute nell'altro e somiglianza dei caratteri."""
    pa, pb = set(parole(a)), set(parole(b))
    if not pa or not pb:
        return 0.0
    inter = len(pa & pb)
    jac = inter / len(pa | pb)
    cont = inter / min(len(pa), len(pb)) * (0.85 if inter < min(len(pa), len(pb)) else 0.95)
    car = difflib.SequenceMatcher(None, chiave(a), chiave(b)).ratio()
    # i numeri diversi (es. 10 cm vs 20 cm) rendono le voci diverse
    na, nb = {p for p in pa if p.isdigit()}, {p for p in pb if p.isdigit()}
    pen = 0.5 if na and nb and not (na & nb) else 1.0
    return min(1.0, max(jac, cont, car * 0.9) * pen)


def raggruppa(voci, soglia=0.62):
    """Raggruppa voci simili. `voci`: lista di stringhe. Restituisce liste di indici, ogni gruppo con almeno una voce."""
    gruppi = []
    for i, v in enumerate(voci):
        mig, best = None, 0.0
        for g in gruppi:
            s = max(similarita(v, voci[j]) for j in g)
            if s > best:
                best, mig = s, g
        if mig is not None and best >= soglia:
            mig.append(i)
        else:
            gruppi.append([i])
    return gruppi
