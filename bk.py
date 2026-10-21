"""
bk.py - Riconciliazione bancaria: abbina i movimenti del conto corrente alle fatture dello Scadenzario.
Deterministico e senza Streamlit. Propone gli abbinamenti con un punteggio e i motivi: l'ultima parola e' sempre di chi li conferma.
"""
import re

from core import fmt_num, to_float
from sc import data_da

COLONNE_MOV = ["Data", "Descrizione", "Importo"]
ETICHETTE_MOV = {"Data": "Data", "Descrizione": "Causale / descrizione", "Importo": "Importo (entrate +, uscite −)"}
SINONIMI_MOV = {"Data": ("Data operazione", "Data valuta", "Data contabile"), "Descrizione": ("Causale", "Descrizione operazione", "Dettagli", "Operazione"),
                "Importo": ("Dare/Avere", "Saldo movimento", "Ammontare", "Movimento")}
BK_DEFAULT = {"sicuro": 70, "possibile": 40, "tolleranza": 0.05, "finestra_gg": 120}
_STOP = {"srl", "spa", "snc", "sas", "di", "e", "il", "la", "lo", "dei", "del", "della", "costruzioni", "edile", "impianti", "societa", "soc", "coop", "bonifico", "fattura", "fatt", "saldo", "pagamento", "a", "da", "per"}


def normalizza_movimenti(righe):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(str(r.get(c) or "").strip() for c in COLONNE_MOV):
            continue
        d, imp = data_da(r.get("Data")), to_float(r.get("Importo"), 0.0)
        if d is None or abs(imp) < 0.005:
            avvisi.append(f"Movimento, riga {i}: data o importo non validi, riga ignorata.")
            continue
        out.append({"Data": d.isoformat(), "Descrizione": str(r.get("Descrizione") or "").strip(), "Importo": round(imp, 2)})
    return out, avvisi


def _parole(t):
    return {w for w in re.findall(r"[a-zà-ù0-9]+", (t or "").lower()) if len(w) > 2 and w not in _STOP}


def _numero_in(descr, numero):
    n = re.sub(r"\W", "", (numero or "").lower())
    return bool(n) and len(n) >= 2 and n in re.sub(r"\W", "", (descr or "").lower())


def punteggio(m, d, p=None):
    """(punteggio, motivi) di un abbinamento movimento/fattura. 0 se il verso non coincide (entrata <-> fattura attiva, uscita <-> passiva)."""
    q = {**BK_DEFAULT, **(p or {})}
    res = d["Importo"] - d["Saldato"]
    if res <= 0 or (m["Importo"] > 0) != (d["Tipo"] == "Attiva"):
        return 0, []
    imp = abs(m["Importo"])
    pt, mot = 0, []
    if abs(imp - res) <= q["tolleranza"]:
        pt += 55
        mot.append("importo uguale al residuo")
    elif abs(imp - d["Importo"]) <= q["tolleranza"]:
        pt += 45
        mot.append("importo uguale alla fattura")
    elif imp < res:
        pt += 10
        mot.append("importo parziale")
    else:
        return 0, []
    if _numero_in(m["Descrizione"], d["Documento"]):
        pt += 30
        mot.append("numero fattura nella causale")
    com = _parole(d["Controparte"]) & _parole(m["Descrizione"])
    if com:
        pt += min(30, 15 * len(com))
        mot.append("nome nella causale: " + ", ".join(sorted(com)))
    md, ds = data_da(m["Data"]), data_da(d["Scadenza"])
    if md and ds:
        dist = abs((md - ds).days)
        if dist <= 15:
            pt += 10
            mot.append("data vicina alla scadenza")
        elif dist > q["finestra_gg"]:
            pt -= 20
    return max(0, pt), mot


def abbina(movimenti, docs, p=None):
    """Assegnazione avida: i punteggi piu' alti per primi, ogni movimento e ogni fattura una sola volta."""
    q = {**BK_DEFAULT, **(p or {})}
    cand = []
    for i, m in enumerate(movimenti):
        for j, d in enumerate(docs):
            pt, mot = punteggio(m, d, q)
            if pt >= q["possibile"]:
                cand.append((pt, i, j, mot))
    cand.sort(key=lambda c: (-c[0], c[1], c[2]))
    usati_m, usati_d, out = set(), set(), []
    for pt, i, j, mot in cand:
        if i in usati_m or j in usati_d:
            continue
        usati_m.add(i), usati_d.add(j)
        m, d = movimenti[i], docs[j]
        imp, res = abs(m["Importo"]), d["Importo"] - d["Saldato"]
        out.append({"m": i, "d": j, "Punteggio": pt, "Esito": "sicuro" if pt >= q["sicuro"] else "da verificare", "Motivi": mot, "Movimento": m, "Fattura": d,
                    "Chiude": imp >= res - q["tolleranza"], "Saldato dopo": min(d["Importo"], d["Saldato"] + imp)})
    return out


def calcola_bk(movimenti, docs, p=None):
    ab = abbina(movimenti, docs, p)
    usati_m = {a["m"] for a in ab}
    usati_d = {a["d"] for a in ab}
    senza = [m for i, m in enumerate(movimenti) if i not in usati_m]
    aperte = [d for j, d in enumerate(docs) if j not in usati_d and d["Importo"] - d["Saldato"] > 0]
    ent = sum(m["Importo"] for m in movimenti if m["Importo"] > 0)
    usc = -sum(m["Importo"] for m in movimenti if m["Importo"] < 0)
    kpi = {"movimenti": len(movimenti), "entrate": ent, "uscite": usc, "abbinati": len(ab), "sicuri": sum(1 for a in ab if a["Esito"] == "sicuro"),
           "da_verificare": sum(1 for a in ab if a["Esito"] != "sicuro"), "senza_fattura": len(senza), "importo_senza": sum(abs(m["Importo"]) for m in senza),
           "fatture_aperte": len(aperte), "importo_riconciliato": sum(abs(a["Movimento"]["Importo"]) for a in ab)}
    avvisi = []
    if senza:
        avvisi.append(f"{len(senza)} movimenti senza fattura ({fmt_num(kpi['importo_senza'])} €): spese bancarie, stipendi o fatture non registrate nello Scadenzario.")
    if kpi["da_verificare"]:
        avvisi.append(f"{kpi['da_verificare']} abbinamenti da verificare a mano prima di confermarli.")
    return {"abbinamenti": ab, "senza_fattura": senza, "fatture_aperte": aperte, "kpi": kpi, "avvisi": avvisi}


def applica_pagamenti(docs, abbinamenti):
    """Copia dei documenti con 'Saldato' aggiornato per gli abbinamenti confermati."""
    nuovi = [dict(d) for d in docs]
    for a in abbinamenti:
        nuovi[a["d"]]["Saldato"] = a["Saldato dopo"]
    return nuovi
