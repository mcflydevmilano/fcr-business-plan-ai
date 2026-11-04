"""
percorso.py - «Primi passi»: la strada guidata per chi apre la suite per la prima volta, dal cantiere in avanti.
Per ogni passo dice cosa fare, perche', in che strumento, e se e' gia' stato fatto (dai salvataggi veri, mai dagli esempi).
Senza Streamlit, quindi testabile.
"""
import storage

# sigle = strumenti da aprire; controllo = (sigla dei dati, chiave che deve contenere almeno una riga) oppure (sigla, None) = basta un salvataggio
PASSI = [
    {"id": "cantieri", "titolo": "Scrivi i cantieri", "sigle": ["ru"], "controllo": ("ru", "cantieri"),
     "perche": "Tutto il resto (fatture, ore, materiali, subappalti) si lega al cantiere. Per ognuno scrivi il nome, il codice che usate in azienda (es. F100) e lo stato «In corso».",
     "dove": "Rubrica e cantieri → tabella «Cantieri»"},
    {"id": "contatti", "titolo": "Scrivi clienti, fornitori e subappaltatori", "sigle": ["ru"], "controllo": ("ru", "contatti"),
     "perche": "Servono per i suggerimenti mentre scrivi (basta «cem» o «adam») e per non scrivere due volte lo stesso nome.",
     "dove": "Rubrica e cantieri → tabella «Contatti»"},
    {"id": "persone", "titolo": "Inserisci le persone e il costo orario", "sigle": ["pr"], "controllo": ("pr", "per"),
     "perche": "Per sapere quanto costa la manodopera di ogni cantiere. Se hai solo la RAL usa «Calcola il costo orario dalla RAL».",
     "dove": "Presenze e ore → «Persone»"},
    {"id": "contratti", "titolo": "Inserisci il contratto di ogni cantiere", "sigle": ["sl"], "controllo": ("sl", None),
     "perche": "Con l'importo del contratto la suite calcola avanzamento e margine di ogni cantiere.",
     "dove": "SAL e contabilità"},
    {"id": "subappalti", "titolo": "Registra i subappalti", "sigle": ["sa"], "controllo": ("sa", "con"),
     "perche": "Un subappaltatore può lavorare su più cantieri: una riga per ciascuno, con la ritenuta. Così sai quanto devi ancora pagare.",
     "dove": "Subappalti → «Inserimento veloce»"},
    {"id": "fatture", "titolo": "Inserisci fatture e scadenze", "sigle": ["sc"], "controllo": ("sc", None),
     "perche": "Le fatture ai clienti e dei fornitori, con il cantiere a cui appartengono. Da qui escono incassi, pagamenti e scaduti.",
     "dove": "Scadenzario"},
    {"id": "banche", "titolo": "Collega i conti correnti", "sigle": ["bk"], "controllo": ("bk", None),
     "perche": "Ogni cantiere può avere i suoi conti. La suite li confronta con le fatture e prevede la cassa futura.",
     "dove": "Riconciliazione bancaria"},
    {"id": "giorno", "titolo": "Ogni giorno: rapportini, ore e materiali", "sigle": ["rp", "pr", "mt"], "controllo": ("rp", None),
     "perche": "Dal telefono, in cantiere: il rapportino della giornata, le ore di ognuno e le bolle dei materiali. Sono i dati che fanno muovere i conti.",
     "dove": "Rapportini · Presenze e ore · Materiali"},
    {"id": "controllo", "titolo": "Guarda tutto in un posto", "sigle": ["sk", "dd"], "controllo": None,
     "perche": "Quando hai fatto i passi sopra, la Scheda cantiere mostra entrate, uscite, costi, SAL e margine di ogni cantiere; il Cruscotto la sintesi dell'azienda.",
     "dove": "Scheda cantiere · Cruscotto di direzione"},
]


def _conta(sigla, chiave, nome):
    try:
        d = storage.carica_pratica(nome, modulo=sigla) or {}
    except Exception:
        return 0
    if chiave is None:
        return 1
    v = d.get(chiave)
    return len([r for r in v if isinstance(r, dict) and any(str(x).strip() for x in r.values())]) if isinstance(v, list) else 0


def valuta(aggiornati, consentiti=None):
    """aggiornati = storage.ultimi_aggiornamenti() (solo dati veri). Restituisce (passi, fatti, totale).
    Ogni passo: dict del passo + 'stato' = 'fatto' | 'adesso' (il primo da fare) | 'dopo', + 'n' (numero mostrato). Il passo finale non conta come «da fare»."""
    aggiornati = aggiornati or {}
    out = []
    for p in PASSI:
        sigle = [s for s in p["sigle"] if consentiti is None or s in consentiti]
        if not sigle:
            continue
        c = p["controllo"]
        if c is None:
            fatto = None
        else:
            sig, chiave = c
            fatto = sig in aggiornati and _conta(sig, chiave, aggiornati[sig][2]) > 0
        out.append({**p, "sigle": sigle, "fatto": fatto})
    primo = next((p for p in out if p["fatto"] is False), None)
    for n, p in enumerate(out, start=1):
        p["n"] = n
        p["stato"] = "fatto" if p["fatto"] else ("adesso" if p is primo else "dopo")
    da_fare = [p for p in out if p["fatto"] is not None]
    return out, sum(1 for p in da_fare if p["fatto"]), len(da_fare)
