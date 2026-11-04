"""
novita.py - «Novità e aggiornamenti»: cosa cambia nella suite, in parole semplici, versione per versione.
Le voci del programma stanno qui sotto (le aggiunge chi rilascia l'aggiornamento); le voci scritte a mano dagli amministratori dentro la suite
si salvano a parte e si mescolano a queste. Per ogni persona si ricorda l'ultima novità letta, cosi' l'Hub mostra un avviso solo quando c'e' qualcosa di nuovo.
Senza Streamlit, quindi testabile.
"""
import datetime as dt
import uuid

import storage

NOME_MANUALI = "novita_manuali"
NOME_LETTE = "novita_lette"
MAX_MANUALI = 200

# Piu' recente in alto. Campi: id (versione), data (AAAA-MM-GG), quando (testo da mostrare, facoltativo), titolo, voci (cosa cambia per te), strumenti (sigle o nomi)
NOVITE = [
    {"id": "3.15.1", "data": "2026-11-04", "titolo": "Chat: foto intere con «Scarica» e pulsante «Compito» ben visibile",
     "voci": ["Le foto ricevute nella Chat ora si adattano alla larghezza dello schermo (prima sul telefono uscivano tagliate).",
              "Sotto ogni foto c'è il pulsante «⬇️ Scarica la foto»."],
     "strumenti": ["Chat interna"]},
    {"id": "3.15.0", "data": "2026-11-04", "titolo": "Primi passi guidati, menu riordinato, scorciatoia alle cartelle",
     "voci": ["Nell'Hub c'è «🚀 Primi passi»: i passi in ordine, dal cantiere in avanti (cantieri, contatti, persone, contratti, subappalti, fatture, banche, lavoro quotidiano, controllo). Il passo da fare adesso è evidenziato e ha il pulsante per aprire lo strumento giusto.",
              "I passi si segnano «fatti» da soli quando salvi dati veri (gli esempi non contano). La barra a sinistra mostra «Primi passi (x di y)».",
              "Il menu a sinistra è riordinato nello stesso ordine di lavoro: «1 · Si parte da qui» (Rubrica e cantieri), poi persone, spese, soldi, controllo.",
              "Le linguette (come quelle della Scheda cantiere) ora si leggono bene: la linguetta scelta è evidente.",
              "Scheda cantiere → Cartelle: «📂 Apri» apre la cartella nel NAS (File Station); serve l'accesso al portale del NAS per le persone."],
     "strumenti": ["Hub", "Scheda cantiere"]},
    {"id": "3.14.2", "data": "2026-11-04", "titolo": "Pulsante «Apri» per le cartelle dei cantieri",
     "voci": ["Nella scheda «📁 Cartelle» della Scheda cantiere, accanto a ogni percorso c'è il pulsante «📂 Apri»: apre la cartella nel NAS (File Station).",
              "Il pulsante di copia del percorso resta come alternativa per Esplora file."],
     "strumenti": ["Scheda cantiere"]},
    {"id": "3.14.1", "data": "2026-11-04", "titolo": "Cartelle del NAS collegate ai cantieri",
     "voci": ["Nella «Scheda cantiere» c'è la nuova scheda «📁 Cartelle»: per ogni cantiere mostra dove stanno i suoi file sul NAS (Progetti, CME, Contratti, Contabilità, Sicurezza, Foto e Drone...).",
              "Basta copiare il percorso (icona a destra) e incollarlo nella barra di Esplora file di Windows, dall'ufficio.",
              "La cartella di ogni cantiere si chiama «CODICE - Nome», per esempio «F100 - Villa Lago». Il codice è quello della Rubrica (campo «codice in altro sistema») o, se manca, CAN-….",
              "Quando il NAS sarà collegato al server, un pulsante creerà da solo le cartelle mancanti del cantiere.",
              "La scheda spiega anche la struttura delle cartelle e chi può usarle."],
     "strumenti": ["Scheda cantiere"]},
    {"id": "3.14.0", "data": "2026-11-03", "titolo": "Organico dal calendario, magazzino con pistola, suggerimenti mentre scrivi, bolle lette dall'IA",
     "voci": ["Organico: le ore disponibili ora si calcolano dal calendario vero, dal lunedì al venerdì, senza festività (Pasquetta compresa), festa del patrono, ferie, malattie e chiusure che inserisci.",
              "Organico e Presenze: colonne «Assunto dal» e «Cessato il». Chi è cessato esce da solo da capacità, costi e previsioni; le ore passate restano.",
              "Presenze: calcolatore del costo orario aziendale a partire dalla RAL (con contributi, INAIL, TFR e altri costi).",
              "Materiali: scrivi «cem» e propone «Cemento». Scelto materiale e fornitore, il prezzo unitario si compila da solo con l'ultimo pagato a quel fornitore. Vale anche per fornitore e commessa.",
              "Materiali: nuovo magazzino con più sedi (deposito, cantieri), giacenza per magazzino, scorta minima con avviso «da riordinare» e uso della pistola dei codici a barre: sparo, e carico o scarico si registra da solo.",
              "Subappalti: inserimento veloce con suggerimenti («adam» propone «Adam Costruzioni») per contratti e SAL.",
              "Bolle (DDT): il pulsante «Leggi la bolla con l'IA» compila numero, data e fornitore e abbina le righe agli ordini aperti: tu confermi e diventano «Consegnato: sì» con data e DDT.",
              "Fornitori: nel confronto preventivi la suite propone di unire le voci scritte in modo diverso ma uguali (es. «Intonaco civile 2 mani» e «Intonacatura civile a due strati»). Decidi tu quali unire.",
              "Chat: sistemate le icone delle reazioni, anche da telefono."],
     "strumenti": ["Organico", "Presenze", "Materiali", "Subappalti", "Fornitori", "Chat"]},
    {"id": "3.13.0", "data": "2026-11-03", "titolo": "Scheda cantiere: i conti di ogni cantiere in un posto solo",
     "voci": ["Nuovo strumento «Scheda cantiere»: scegli un cantiere e vedi fatturato, incassato, costi (materiali, ore, mezzi, subappalti), SAL, margine e cassa.",
              "Mostra le fatture ai clienti e dei fornitori di quel cantiere, con quello che è scaduto, e i suoi rapportini e segnalazioni aperte.",
              "Non si scrive nulla due volte: la scheda legge i dati degli altri strumenti. L'importante è scrivere il cantiere sempre con lo stesso nome o codice della Rubrica.",
              "I rapportini ora propongono solo i cantieri vivi (in corso o in preparazione) presi dalla Rubrica e cantieri: un cantiere nuovo si aggiunge prima lì.",
              "In Scadenzario, Presenze, Materiali, Subappalti e Parco mezzi la colonna del cantiere diventa una scelta da elenco.",
              "Se un nome non corrisponde a nessun cantiere della Rubrica, la scheda lo segnala come «Non in Rubrica» così lo correggi."],
     "strumenti": ["Scheda cantiere", "Rapportini", "Rubrica e cantieri"]},
    {"id": "3.12.4", "data": "2026-11-02", "titolo": "Via ogni riferimento a monday",
     "voci": ["In «Compiti e attività» non c'è più la scheda «Importa da monday»: i compiti si scrivono direttamente nella suite.",
              "Tolti anche i richiami a monday da guide, esempi e descrizioni degli strumenti."],
     "strumenti": ["Compiti"]},
    {"id": "3.12.3", "data": "2026-11-02", "titolo": "Chat: corretto l'errore quando si rientra",
     "voci": ["Se uscivi dalla Chat dopo aver allegato una foto o un PDF e poi ci rientravi, compariva un messaggio di errore: ora non succede più.",
              "Lo stesso controllo vale per i caricamenti di file in Offerte e in Registro."],
     "strumenti": ["Chat"]},
    {"id": "3.12.2", "data": "2026-11-02", "titolo": "Spazio libero sul server e sul NAS",
     "voci": ["In «⚙️ Amministrazione suite» (il pulsante sotto il tuo nome, a sinistra, che prima si chiamava «Utenti») c'è la nuova scheda «💾 Spazio»: una barra mostra quanto disco è usato sul server e sul NAS (verde, giallo oltre il 75%, rosso oltre il 90%).",
              "Sotto le barre vedi quanto occupano il database della suite e le copie di sicurezza.",
              "Se il disco sta per finire, compare un avviso in cima alla pagina Amministrazione.",
              "La suite ora gira sul nostro server: più veloce, con i dati in azienda e una copia di sicurezza ogni notte."],
     "strumenti": ["Amministrazione"]},
    {"id": "3.12.1", "data": "2026-11-02", "titolo": "Nuova pagina «Novità e aggiornamenti»",
     "voci": ["Qui trovi, in parole semplici, cosa cambia nella suite a ogni aggiornamento: la più recente è in alto.",
              "Quando c'è una novità che non hai ancora letto, nella pagina iniziale compare un avviso con il pulsante «Leggi le novità».",
              "Puoi cercare per parola o per strumento.",
              "Gli amministratori possono scrivere una novità direttamente dalla pagina, senza aspettare un aggiornamento del programma."],
     "strumenti": ["Novità e aggiornamenti", "Hub"]},
    {"id": "3.12.0", "data": "2026-11-02", "titolo": "Il Flusso commessa lavora per te",
     "voci": ["Quando fai avanzare un passaggio del Flusso commessa, lo stato della pratica nel Registro commerciale si aggiorna da solo.",
              "Ogni passaggio «in corso» diventa un compito per chi lo deve fare, con scadenza. Quando il passaggio è chiuso, il compito si chiude.",
              "Chi deve approvare (CdA, Presidente, assemblea, firma contratti) riceve un messaggio in chat. Se una commessa resta ferma, lo riceve il responsabile.",
              "Nella scheda «Chi è chi e collegamenti» scrivi una volta sola il nome utente di chi ricopre ogni ruolo.",
              "Nel Cruscotto di direzione c'è il nuovo semaforo «Flusso commesse»."],
     "strumenti": ["Flusso commessa", "Compiti e attività", "Registro commerciale", "Cruscotto"]},
    {"id": "3.11.0", "data": "2026-11-02", "titolo": "Due strumenti nuovi: Flusso commessa e Compiti",
     "voci": ["Flusso commessa: i 28 passaggi dello schema FCR, dal primo incontro alla chiusura. Per ogni passaggio vedi chi lo fa, chi approva, con iniziali e data.",
              "I GO / NO GO del CdA, del Presidente e dell'assemblea bloccano i passaggi successivi finché non c'è l'approvazione.",
              "Compiti e attività: la bacheca a colonne (Da fare, In corso, In attesa, Fatto) con responsabile, priorità, scadenza e commessa.",
              "Nella pagina iniziale, «Da dove comincio?» ora ha un percorso per chi lavora in cantiere, in ufficio, sulle commesse e in direzione.",
              "Nuova guida per i colleghi, con la pagina «Cosa faccio io?»."],
     "strumenti": ["Flusso commessa", "Compiti e attività", "Hub"]},
    {"id": "3.10.2", "data": "2026-11-02", "titolo": "Rubrica: importa le rubriche da Excel",
     "voci": ["In «Rubrica e cantieri» carichi in una volta le rubriche dei colleghi e l'elenco degli amministratori da file Excel.",
              "Chi è già in rubrica non viene duplicato: si completano solo i dati mancanti.",
              "Nuovi tipi di contatto: «Amministratore» e «Collaboratore»."],
     "strumenti": ["Rubrica e cantieri"]},
    {"id": "3.10.1", "data": "2026-11-02", "titolo": "Credit Risk: il bilancio in PDF si legge molto più in fretta",
     "voci": ["Se il PDF ha il testo (quelli del Registro Imprese o del gestionale) la lettura richiede pochi secondi invece di minuti.",
              "C'è un tempo massimo di attesa: dopo circa 3 minuti la suite ti avvisa e puoi inserire i dati a mano.",
              "Con un PDF scansionato la lettura resta più lenta: meglio il bilancio in formato XBRL o Excel."],
     "strumenti": ["Credit Risk & Rating"]},
    {"id": "3.10.0", "data": "2026-10-30", "quando": "Fine ottobre 2026", "titolo": "Cinque strumenti nuovi, avvisi e archivio delle bolle",
     "voci": ["Nuovi strumenti: Subappalti, Presenze e ore, Materiali e magazzino, Verbali e riunioni, Archivio documenti per commessa.",
              "Materiali: ora puoi caricare le bolle (DDT) in PDF, foto o Excel. La suite propone numero, data e fornitore e avvisa se una bolla è doppia o manca.",
              "Presenze: le ore si possono prendere dai rapportini giornalieri.",
              "Nella barra laterale: la campanella «Avvisi» con le scadenze e «Esporta tutto in Excel» in un solo file.",
              "Le email della suite sono più sicure: un solo tentativo, nessun ripetersi se il server di posta rifiuta, per non far bloccare il dominio.",
              "Corretto un difetto per cui, aprendo uno strumento, si tornava alla prima scheda."],
     "strumenti": ["Subappalti", "Presenze e ore", "Materiali e magazzino", "Verbali e riunioni", "Archivio documenti", "Avvisi"]},
]


def _s(v):
    return str(v or "").strip()


def _voce(v, manuale=False):
    return {"id": _s(v.get("id")), "data": _s(v.get("data")), "quando": _s(v.get("quando")), "titolo": _s(v.get("titolo")),
            "voci": [_s(x) for x in (v.get("voci") or []) if _s(x)], "strumenti": [_s(x) for x in (v.get("strumenti") or []) if _s(x)], "manuale": manuale, "autore": _s(v.get("autore"))}


def carica_manuali(path=None):
    try:
        raw = storage.carica_pratica(NOME_MANUALI, path, modulo="cfg") or {}
    except Exception:
        raw = {}
    out = []
    for v in raw.get("voci") or []:
        x = _voce(v, True)
        if x["id"] and x["titolo"] and x["voci"]:
            out.append(x)
    return out


def tutte(path=None):
    """Tutte le novita', dalla piu' recente. A parita' di data, prima quelle scritte a mano."""
    elenco = [(_voce(v), 0, i) for i, v in enumerate(NOVITE)] + [(v, 1, i) for i, v in enumerate(carica_manuali(path))]
    elenco.sort(key=lambda t: (t[0]["data"], t[1], -t[2]), reverse=True)
    return [t[0] for t in elenco]


def aggiungi(versione, titolo, voci, strumenti=(), data=None, autore="", path=None):
    """Aggiunge una novita' scritta a mano. `voci`: elenco di frasi (o testo con una voce per riga). Restituisce l'id."""
    if isinstance(voci, str):
        voci = voci.splitlines()
    voci = [_s(x).lstrip("-•* ").strip() for x in voci if _s(x).lstrip("-•* ").strip()]
    titolo = _s(titolo)
    if not titolo or not voci:
        raise ValueError("Servono un titolo e almeno una voce.")
    try:
        d = dt.date.fromisoformat(_s(data)) if data else dt.date.today()
    except ValueError:
        raise ValueError("La data non è valida.")
    attuali = [v for v in (storage.carica_pratica(NOME_MANUALI, path, modulo="cfg") or {}).get("voci") or []]
    if len(attuali) >= MAX_MANUALI:
        raise ValueError("Ci sono troppe novità scritte a mano: elimina le più vecchie.")
    nuovo = {"id": _s(versione) or f"nota-{uuid.uuid4().hex[:6]}", "data": d.isoformat(), "titolo": titolo, "voci": voci, "strumenti": [_s(x) for x in strumenti if _s(x)], "autore": autore}
    attuali.append(nuovo)
    storage.salva_pratica(NOME_MANUALI, {"voci": attuali}, path, autore=autore or "admin", modulo="cfg")
    storage.svuota_cache()
    return nuovo["id"]


def elimina(id_, data, path=None, autore=""):
    """Toglie una novita' scritta a mano (le voci del programma non si cancellano). Restituisce True se l'ha trovata."""
    attuali = (storage.carica_pratica(NOME_MANUALI, path, modulo="cfg") or {}).get("voci") or []
    resto = [v for v in attuali if not (_s(v.get("id")) == id_ and _s(v.get("data")) == data)]
    if len(resto) == len(attuali):
        return False
    storage.salva_pratica(NOME_MANUALI, {"voci": resto}, path, autore=autore or "admin", modulo="cfg")
    storage.svuota_cache()
    return True


def _chiave(v):
    return f"{v['id']}|{v['data']}"


def ultima(path=None):
    t = tutte(path)
    return t[0] if t else None


def _lette(path=None):
    try:
        raw = storage.carica_pratica(NOME_LETTE, path, modulo="cfg") or {}
    except Exception:
        raw = {}
    return raw if isinstance(raw, dict) else {}


def da_leggere(utente, path=None):
    """L'ultima novita' se questa persona non l'ha ancora aperta, altrimenti None."""
    u = ultima(path)
    if not u or not _s(utente):
        return None
    return None if _lette(path).get(_s(utente).lower()) == _chiave(u) else u


def segna_lette(utente, path=None):
    """Ricorda che la persona ha visto l'ultima novita'."""
    u = ultima(path)
    if not u or not _s(utente):
        return
    lette = _lette(path)
    k = _s(utente).lower()
    if lette.get(k) == _chiave(u):
        return
    lette[k] = _chiave(u)
    storage.salva_pratica(NOME_LETTE, lette, path, autore=_s(utente), modulo="cfg")
    storage.svuota_cache()


def data_it(iso):
    try:
        d = dt.date.fromisoformat(iso)
    except ValueError:
        return iso
    mesi = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
    return f"{d.day} {mesi[d.month - 1]} {d.year}"


def filtra(elenco, testo="", strumento=""):
    t = _s(testo).lower()
    out = []
    for v in elenco:
        if strumento and strumento not in v["strumenti"]:
            continue
        if t and t not in " ".join([v["titolo"], v["id"], *v["voci"], *v["strumenti"]]).lower():
            continue
        out.append(v)
    return out
