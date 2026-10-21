"""
anagrafica.py - Nomi coerenti tra gli strumenti. I collegamenti (fatture, documenti, cantieri) avvengono per nome: un refuso li spezza.
Qui si confronta ogni nome scritto nelle tabelle con la Rubrica e si propone la correzione piu' vicina. Senza Streamlit, quindi testabile.
"""
import difflib
import re

_STOP = {"srl", "spa", "snc", "sas", "sa", "soc", "societa", "coop", "di", "e", "il", "la", "lo", "dei", "del", "della", "s", "r", "l", "p", "a", "c", "n"}

# (chiave in session_state, colonna, tipo: "soggetto" = contatto della rubrica, "cantiere"), etichetta
TABELLE = [("sc_df", "Controparte", "soggetto", "Scadenzario · cliente/fornitore"), ("sc_df", "Cantiere", "cantiere", "Scadenzario · cantiere"),
           ("fo_doc", "Fornitore", "soggetto", "Fornitori · documenti"), ("fo_contr", "Fornitore", "soggetto", "Fornitori · contratti"), ("fo_contr", "Commessa", "cantiere", "Fornitori · contratti (cantiere)"),
           ("fo_off", "Fornitore", "soggetto", "Fornitori · preventivi"), ("gt_fasi", "Commessa", "cantiere", "Cronoprogramma"),
           ("lg_riserve", "Cantiere", "cantiere", "Studio legale · riserve"), ("lg_contratti", "Controparte", "soggetto", "Studio legale · contratti"),
           ("lg_contratti", "Cantiere", "cantiere", "Studio legale · contratti (cantiere)"), ("lg_termini", "Cantiere", "cantiere", "Studio legale · termini"),
           ("lg_solleciti", "Cliente", "soggetto", "Studio legale · solleciti"), ("oa_ord", "Fornitore", "soggetto", "Ordini · fornitore"), ("oa_ord", "Cantiere", "cantiere", "Ordini · cantiere"),
           ("rp_rapp", "Cantiere", "cantiere", "Rapportini"), ("rp_segn", "Cantiere", "cantiere", "Segnalazioni"),
           ("sl_com", "Commessa", "cantiere", "SAL · commesse"), ("sl_com", "Cliente", "soggetto", "SAL · cliente"), ("sl_sal", "Commessa", "cantiere", "SAL · avanzamenti"),
           ("sl_cos", "Commessa", "cantiere", "SAL · costi"), ("sl_cos", "Fornitore", "soggetto", "SAL · costi (fornitore)"),
           ("gt_fasi", "Responsabile", "persona", "Cronoprogramma · responsabile"), ("rp_segn", "Responsabile", "persona", "Segnalazioni · responsabile"), ("rp_rapp", "Compilato_da", "persona", "Rapportini · compilato da"),
           ("ru_can", "Responsabile", "persona", "Cantieri · responsabile"), ("oa_ord", "Richiedente", "persona", "Ordini · richiedente"), ("sx_pers", "Persona", "persona", "Sicurezza · persone")]


def _t(v):
    return "" if v is None or v != v else str(v).strip()


def chiave(nome):
    """Forma confrontabile: minuscolo, senza punteggiatura e senza forme societarie (srl, spa...)."""
    parole = [w for w in re.findall(r"[a-zà-ù0-9]+", _t(nome).lower()) if w not in _STOP]
    return " ".join(parole)


def elenchi(contatti, cantieri, persone=None):
    """Nomi ufficiali: {'soggetto': contatti della Rubrica, 'cantiere': cantieri della Rubrica, 'persona': personale (nome e cognome o nome utente)}."""
    pers = set()
    for p in persone or []:
        for k in ("Persona", "Utente"):
            if _t(p.get(k)):
                pers.add(_t(p.get(k)))
    return {"soggetto": sorted({_t(c.get("Nome")) for c in contatti or [] if _t(c.get("Nome"))}),
            "cantiere": sorted({_t(c.get("Cantiere")) for c in cantieri or [] if _t(c.get("Cantiere"))}), "persona": sorted(pers)}


def suggerisci(nome, ufficiali, soglia=0.72):
    """Il nome ufficiale piu' simile (o None). Confronta le forme senza srl/spa; accetta anche un nome contenuto nell'altro."""
    k = chiave(nome)
    if not k or not ufficiali:
        return None
    best, miglior = None, 0.0
    for u in ufficiali:
        ku = chiave(u)
        if not ku:
            continue
        r = difflib.SequenceMatcher(None, k, ku).ratio()
        if len(k) >= 4 and len(ku) >= 4 and (k in ku or ku in k):
            r = max(r, 0.85)
        if r > miglior:
            best, miglior = u, r
    return best if miglior >= soglia else None


def controlla(tabelle, ufficiali):
    """tabelle: {chiave_ss: lista di righe dict}. Restituisce i nomi che NON sono nella Rubrica, uno per (tipo, valore), con dove compaiono e un suggerimento."""
    noti = {t: {_t(n).lower() for n in v} for t, v in ufficiali.items()}      # i collegamenti confrontano il nome scritto per intero (senza badare alle maiuscole)
    trovati = {}
    for chiave_ss, col, tipo, etichetta in TABELLE:
        if not ufficiali.get(tipo):                       # elenco ufficiale vuoto: non c'e' nulla con cui confrontare
            continue
        for riga in tabelle.get(chiave_ss) or []:
            v = _t(riga.get(col))
            if not v or v.lower() in noti.get(tipo, set()):
                continue
            d = trovati.setdefault((tipo, v), {"tipo": tipo, "valore": v, "dove": {}, "suggerimento": suggerisci(v, ufficiali.get(tipo, []))})
            d["dove"][(chiave_ss, col, etichetta)] = d["dove"].get((chiave_ss, col, etichetta), 0) + 1
    return sorted(trovati.values(), key=lambda d: (d["suggerimento"] is None, d["tipo"], d["valore"].lower()))


def sostituisci(righe, colonna, vecchio, nuovo):
    """Copia delle righe con `vecchio` sostituito da `nuovo` nella colonna. Restituisce (righe, quante)."""
    n, out = 0, []
    for r in righe:
        r = dict(r)
        if _t(r.get(colonna)) == vecchio:
            r[colonna] = nuovo
            n += 1
        out.append(r)
    return out, n
