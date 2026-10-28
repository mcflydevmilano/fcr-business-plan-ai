"""
ricerca.py - Ricerca nella suite: strumenti (per nome e argomento) e dati salvati (contatti, cantieri, fatture, ordini, persone...).
Senza Streamlit, quindi testabile. La ricerca guarda solo gli strumenti consentiti al profilo di chi cerca.
"""
import re
import unicodedata

# argomenti collegati a ogni strumento: chi cerca «fattura» deve trovare lo Scadenzario anche se il nome non lo dice
SINONIMI = {
    "mc": "margini margine commessa costi ricavi utile redditivita sal subappalti", "sa": "subappalti subappaltatori durc polizze ritenute sal pagamenti", "pr": "presenze ore straordinari manodopera timbrature costo orario", "mt": "materiali magazzino ordini consegne giacenze cantiere", "vr": "verbali riunioni decisioni azioni responsabili compiti", "ad": "archivio documenti link cartelle drive sharepoint commessa scadenze",
    "credit": "rating banca bilancio merito creditizio basilea fido comitato", "bp": "business plan piano industriale mutuo investimento capannone",
    "cf": "cash flow liquidita cassa previsione cantieri", "pv": "preventivo computo metrico offerta costi margine voci",
    "ch": "chat messaggi canali conversazione colleghi telegram notifiche avvisi slack gruppo privato", "of": "offerta preventivo computo parcelle qte quadro economico finanziamento mutuo agos millesimi rata detrazione recupero fiscale condominio condomino", "rc": "registro commerciale pratiche pipeline offerte sopralluogo amministratore commerciale contratto stato", "pz": "prezziario listino prezzi camera commercio voci costi materiali", "sc": "fatture incassi pagamenti scadenze clienti fornitori solleciti cassa xml",
    "bk": "banca estratto conto movimenti riconciliazione bonifici", "oa": "ordini acquisto approvazioni fornitori materiali",
    "ga": "gare appalti offerte bandi", "sl": "sal avanzamento lavori contabilita commesse fatturazione", "gt": "cronoprogramma gantt fasi ritardi tempi",
    "rp": "rapportino giornale cantiere presenze ore foto firma segnalazioni", "sx": "sicurezza formazione dpi corsi scadenze lavoratori",
    "mz": "mezzi veicoli manutenzione revisione assicurazione parco", "og": "organico personale carico lavoro squadre ore",
    "fo": "fornitori documenti durc assicurazioni", "ru": "rubrica contatti telefono email cantieri codici clienti", "pe": "persone dipendenti ruoli accessi utenti account",
    "lg": "legale avvocato riserve contratti penali solleciti fascicoli", "ca": "calendario scadenze appuntamenti", "dd": "cruscotto direzione semafori sintesi",
}


def _n(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", s).strip()


def _tok(testo):
    """Parole cercate, senza la vocale finale se sono lunghe: «fattura» trova anche «fatture», «cantieri» trova «cantiere»."""
    return [t[:-1] if len(t) > 4 and t[-1] in "aeio" else t for t in _n(testo).split() if t]


def cerca_strumenti(testo, consentiti, cards):
    """Sigle degli strumenti consentiti che contengono tutte le parole (titolo, descrizione, voci, argomenti). Prima quelli che hanno la parola nel titolo."""
    tok = _tok(testo)
    if not tok:
        return []
    out = []
    for sigla, c in cards.items():
        if consentiti is not None and sigla not in consentiti:
            continue
        titolo = _n(c["titolo"] + " " + c.get("bottone", ""))
        resto = _n(" ".join([c.get("desc", ""), *c.get("voci", []), *c.get("tag", []), SINONIMI.get(sigla, "")]))
        if all(t in titolo or t in resto for t in tok):
            out.append((0 if all(t in titolo for t in tok) else 1, sigla))
    return [s for _, s in sorted(out, key=lambda x: x[0])]


def _liste(obj, nome=""):
    """Tutte le tabelle (liste di dizionari) dentro un salvataggio, con il loro nome."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).startswith("_"):
                continue
            yield from _liste(v, str(k))
    elif isinstance(obj, list) and obj and all(isinstance(x, dict) for x in obj[:3]):
        yield nome, [x for x in obj if isinstance(x, dict)]


def _riassunto(riga, tok, massimo=170):
    """Prima i campi che contengono la parola cercata, poi i primi campi non vuoti."""
    campi = [(k, str(v).strip()) for k, v in riga.items() if v is not None and str(v).strip() not in ("", "nan", "None") and not str(k).startswith("_")]
    trovati = [(k, v) for k, v in campi if any(t in _n(v) for t in tok)]
    altri = [(k, v) for k, v in campi if (k, v) not in trovati]
    parti = [f"{k.replace('_', ' ')}: {v}" for k, v in (trovati + altri)[:5]]
    t = " · ".join(parti)
    return t if len(t) <= massimo else t[:massimo - 1] + "…"


def cerca_dati(testo, payloads, nomi, per_strumento=5):
    """payloads: {sigla: salvataggio}. Restituisce [{sigla, nome, tabella, trovate, righe:[testo]}] solo per gli strumenti con risultati."""
    tok = _tok(testo)
    if not tok or len("".join(tok)) < 2:
        return []
    out = []
    for sigla, pay in (payloads or {}).items():
        righe, totale, viste = [], 0, set()
        for tabella, lista in _liste(pay):
            for r in lista:
                blob = _n(" ".join(str(v) for v in r.values() if v is not None))
                if all(t in blob for t in tok):
                    riassunto = _riassunto(r, tok)
                    if riassunto in viste:
                        continue
                    viste.add(riassunto)
                    totale += 1
                    if len(righe) < per_strumento:
                        righe.append({"tabella": tabella.replace("_", " "), "testo": riassunto})
        if totale:
            out.append({"sigla": sigla, "nome": nomi.get(sigla, sigla), "trovate": totale, "righe": righe})
    return sorted(out, key=lambda x: -x["trovate"])
