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
NOME_VISTE = "novita_viste"
GIORNI_NEW = 14            # per quanti giorni uno strumento cambiato porta il bollino NEW
MAX_MANUALI = 200

# Piu' recente in alto. Campi: id (versione), data (AAAA-MM-GG), quando (testo da mostrare, facoltativo), titolo, voci (cosa cambia per te), strumenti (sigle o nomi)
NOVITE = [
    {"id": "3.28.1", "data": "2026-11-10", "titolo": "Corretto un errore cambiando strumento dopo aver aperto un caricamento file", "voci": [
        "Se uscivi da uno strumento con un caricamento file (es. Computo di cantiere, Fatture elettroniche, Lettura bandi, Scadenze di persone e mezzi, Sopralluogo) e poi ci tornavi, a volte compariva un errore tecnico (\u00abis read-only\u00bb). Ora non succede più."], "strumenti": []},
    {"id": "3.28.0", "data": "2026-11-10", "titolo": "Computo di cantiere con i prezzi aggiornati",
     "voci": ["Computo di cantiere (nuovo): i lavori rimanenti con le colonne del computo del Comune (codice E.P.U., descrizione, quantità, prezzo, totale da esecutivo, coefficiente, prezzario nuovo, % di aumento, prezzo e totale aggiornati). Il prezzo aggiornato si calcola da solo.",
              "Puoi aggiungere le tue colonne, importare ed esportare in Excel e salvare un computo per ogni cantiere.",
              "Il computo di Sommacampagna (ex limonaia, 55 voci) è già pronto: si carica con un pulsante."],
     "strumenti": ["Computo di cantiere"]},
    {"id": "3.27.1", "data": "2026-11-09", "titolo": "Lettura del bilancio con l'AI più resistente ai momenti di sovraccarico",
     "voci": ["Se il servizio AI di Google è sovraccarico (errore 503), la suite ora riprova con più pazienza e passa da sola a due modelli di riserva prima di arrendersi. Con un PDF con testo la lettura resta rapida. Se non basta, premi di nuovo il pulsante dopo qualche minuto o inserisci i dati a mano."],
     "strumenti": []},
    {"id": "3.27.0", "data": "2026-11-07", "titolo": "Controllo impianti ESCo e portale cliente",
     "voci": ["Controllo impianti ESCo (nuovo): per ogni impianto venduto scrivi ogni mese la produzione e il canone incassato. Vedi se produce meno dell'85% dell'atteso, quali canoni mancano e le manutenzioni in scadenza. I problemi arrivano anche nel riepilogo del mattino.",
              "Portale cliente (nuovo): un link segreto per ogni cliente, senza password. Vede lo stato dei lavori, le foto e i documenti che scegli tu e può accettare l'offerta firmando col dito. Il link scade e si può revocare."],
     "strumenti": ["Controllo impianti ESCo", "Portale cliente"]},
    {"id": "3.26.0", "data": "2026-11-07", "titolo": "Fatture elettroniche, sopralluogo da telefono, lettura bandi",
     "voci": ["Fatture elettroniche (nuovo): carichi i file XML (anche .p7m o uno ZIP con tante fatture) e le scadenze vanno nello Scadenzario, col cantiere giusto se nel testo c'è il suo codice. Le fatture già presenti non vengono doppiate.",
              "Sopralluogo da telefono (nuovo): domande guidate sul posto, foto di tetto e quadro, avvisi su amianto, potenza e distanze. Un tasto porta tutto nel Preventivo fotovoltaico, già compilato; riepilogo in Word.",
              "Lettura bandi (nuovo): carichi il PDF del bando e trovi CIG, importo, scadenza, categorie SOA e l'elenco dei documenti da preparare. Va sempre controllato sull'originale."],
     "strumenti": ["Fatture elettroniche", "Sopralluogo da telefono", "Lettura bandi"]},
    {"id": "3.25.0", "data": "2026-11-07", "titolo": "Riepilogo del mattino, offerte da seguire, scadenze di persone e mezzi",
     "voci": ["Il mio riepilogo (nuovo): ogni mattina solo le cose che ti riguardano, in base ai tuoi strumenti: semafori urgenti, offerte da seguire, scadenze vicine, chi manca oggi. Per email a chi ha l'indirizzo e, per l'azienda, su Slack. Lo accende l'amministratore; ognuno può scegliere se riceverlo.",
              "Registro commerciale, scheda «Da fare»: nuova sezione «Offerte da seguire» con le offerte inviate da più di 7 giorni senza risposta. Per ognuna la lettera di seguito è già scritta (si scarica in Word) e, dopo il seguito, la pratica sparisce per due settimane.",
              "Scadenze di persone e mezzi (nuovo): formazione sulla sicurezza, visite mediche, DURC, assicurazioni, revisioni in un elenco con semaforo e avvisi a 60, 30 e 7 giorni. Importi il tuo Excel e scarichi l'elenco.",
              "Lettere e modelli: nuovo modello «Seguito a un'offerta inviata»."],
     "strumenti": ["Il mio riepilogo", "Scadenze di persone e mezzi", "Registro commerciale", "Lettere e modelli"]},
    {"id": "3.24.2", "data": "2026-11-07", "titolo": "Avviso «modifiche non salvate» e Hub più ordinato",
     "voci": ["Se in uno strumento ci sono modifiche non salvate compare in basso a sinistra «Modifiche non salvate»: toccalo e ti porta al pulsante Salva.",
              "Se aggiorni o chiudi la pagina con modifiche non salvate, il browser ti chiede conferma.",
              "Se cambi strumento con modifiche non salvate, una finestra ti chiede se restare a salvare o uscire comunque (la copia automatica resta).",
              "Hub: i gruppi di strumenti si aprono chiusi; il bollino NEW sul titolo del gruppo dice dove guardare."],
     "strumenti": []},
    {"id": "3.24.1", "data": "2026-11-07", "titolo": "Aggiorna la pagina senza perdere lo strumento",
     "voci": ["Se aggiorni la pagina (F5, ↻ o il tasto del browser) resti nello strumento in cui eri, invece di tornare all'Hub. Lo strumento è scritto nell'indirizzo, quindi puoi anche salvare il link di uno strumento tra i preferiti del browser."],
     "strumenti": []},
    {"id": "3.24.0", "data": "2026-11-07", "titolo": "Controllo della memoria e prova di velocità del server",
     "voci": ["Amministrazione, scheda «Spazio»: quanta RAM sta usando il server (con un giudizio in parole semplici), carico del processore, da quanto è acceso e quanta memoria occupa la suite.",
              "Pulsante «Misura la velocità adesso»: calcolo, memoria, disco e tempi del database. Ogni prova resta salvata e mostra di quanto è cambiata rispetto alla precedente, così si vede la differenza dopo una modifica come più RAM."],
     "strumenti": ["Amministrazione"]},
    {"id": "3.23.2", "data": "2026-11-06", "titolo": "Promemoria delle pause più affidabili; testo leggibile nella chat",
     "voci": ["Pause e piccolo svago: i pulsanti di prova funzionano sempre e il riquadro dice da quanto lavori e tra quanto arriva il prossimo avviso; se i promemoria non sono attivi lo dice e come rimetterli (Ctrl+F5).",
              "Chat: i pulsanti dentro le bolle (per esempio «Scarica la foto») hanno di nuovo il testo bianco ben leggibile."],
     "strumenti": ["Chat interna"]},
    {"id": "3.23.1", "data": "2026-11-06", "titolo": "Chat con un aspetto nuovo",
     "voci": ["Messaggi a bolle: i tuoi a destra in azzurro, quelli dei colleghi a sinistra in bianco, su uno sfondo morbido.",
              "Elenco delle conversazioni più pulito, con la conversazione aperta evidenziata.",
              "Allegati, collegamento a uno strumento e «Importante» stanno in un riquadro che si apre solo quando servono: il campo per scrivere resta semplice."],
     "strumenti": ["Chat interna"]},
    {"id": "3.23.0", "data": "2026-11-06", "titolo": "Bollino NEW sugli strumenti nuovi e suite più chiara",
     "voci": ["Bollino NEW: gli strumenti nuovi o cambiati da poco hanno un bollino rosso nell'Hub e nel menu laterale; una striscia «Dove sono le novità» in alto li elenca. Il bollino si spegne quando apri lo strumento (per te soltanto) e dopo 14 giorni.",
              "Dentro lo strumento nuovo compare un avviso che dice cosa è cambiato.",
              "Telefono: i riquadri coi numeri stanno in due colonne e i titoli sono più piccoli, così si legge di più senza scorrere.",
              "I gruppi dell'Hub con strumenti nuovi si aprono da soli."],
     "strumenti": ["Novità e aggiornamenti"]},
    {"id": "3.22.0", "data": "2026-11-06", "titolo": "Segreteria: ferie e permessi, note spese, lettere; ore mensili e uscite in orario",
     "voci": ["Ferie e permessi: chiedi, il responsabile approva, il calendario mostra chi manca. Giorni residui di ciascuno e avviso se in un periodo restano troppo pochi presenti.",
              "Note spese e trasferte: foto dello scontrino, importo, cantiere e rimborso chilometrico; approvazione e riepilogo mensile per persona, cantiere e categoria, con Excel e scontrini scaricabili.",
              "Lettere e modelli: incarico, richiesta di preventivo, convocazione, diffida, risposta tipo e sollecito, compilati dalla Rubrica e scaricabili in Word; i modelli si possono cambiare.",
              "Accessi del personale: nuovo pulsante «Esco per un po'» con il motivo (le commissioni di lavoro contano come ore lavorate) e «Sono rientrato»; ore totali del mese per persona, anche in Excel."],
     "strumenti": ["Ferie e permessi", "Note spese e trasferte", "Lettere e modelli", "Accessi del personale"]},
    {"id": "3.21.0", "data": "2026-11-06", "titolo": "Nuovo strumento: ESCo (diagnosi, investimento, contratto)",
     "voci": ["Diagnosi: bollette di luce e gas mese per mese, consumo di partenza corretto per il clima, spesa annua e kWh per m².",
              "Investimento: più interventi (anche dal Preventivo fotovoltaico), incentivi, finanziamento, risparmio garantito, quota alla ESCo o canone fisso.",
              "Piano: rientro, VAN, TIR, copertura del debito e flusso anno per anno, con avvisi su ciò che non torna.",
              "Contratto: bozza di contratto di prestazione energetica (EPC) in Word, con i numeri del piano, da completare con il legale.",
              "Nuovo «Preventivi efficienza energetica»: pompa di calore, caldaia a condensazione, cappotto e serramenti, relamping LED, solare termico e colonnine di ricarica, con le stesse schede del fotovoltaico (costi, detrazione, risparmio, rientro, listino). Il prezzo passa nell'Offerta e l'intervento nello strumento ESCo."],
     "strumenti": ["ESCo: efficienza energetica", "Preventivi efficienza energetica", "Preventivo fotovoltaico"]},
    {"id": "3.20.0", "data": "2026-11-06", "titolo": "Nuovo strumento: Preventivo fotovoltaico",
     "voci": ["Dal tetto del cliente al prezzo: orientamento, zona, ombre, moduli, batteria e consumi in bolletta.",
              "Costi con ricarico, IVA e detrazione (50% prima casa, 36% altre abitazioni, tetto 96.000 €); regime azienda senza detrazione.",
              "Produzione stimata, risparmio, cessione dell'energia, anni di rientro e guadagno nel tempo.",
              "Listino prezzi caricabile da Excel o CSV così com'è; aggiungi le voci con un clic.",
              "Cliente e indirizzo dal Registro commerciale; il prezzo passa nell'Offerta con un clic; Excel scaricabile."],
     "strumenti": ["Preventivo fotovoltaico", "Offerta e finanziamenti"]},
    {"id": "3.19.0", "data": "2026-11-06", "titolo": "Il lavoro non si perde più e gli strumenti si parlano",
     "voci": ["Salvataggio automatico: se il telefono si blocca o chiudi la scheda per sbaglio, riaprendo lo strumento ti viene proposto di riprendere il lavoro non salvato (copia solo tua, valida 30 giorni).",
              "Compiti in un solo elenco: «La mia giornata» mostra insieme i compiti della chat e quelli della bacheca assegnati a te; la bacheca mostra anche i compiti nati in chat, con il pulsante «Fatto».",
              "Computo e Preventivo: cliente e oggetto si prendono dal Registro commerciale.",
              "Offerta e finanziamenti: il computo si può importare da un preventivo già fatto, senza riscriverlo.",
              "Ordini e approvazioni: gli ordini approvati si mandano a Materiali (Ordini e consegne) con un clic, senza doppioni."],
     "strumenti": ["Computo e Preventivo", "Offerta e finanziamenti", "Ordini e approvazioni", "Compiti e attività"]},
    {"id": "3.18.0", "data": "2026-11-06", "titolo": "Utenti, profili ed email in un solo posto; cantieri a scelta da elenco",
     "voci": ["Amministrazione → Utenti: crei la persona con nome e cognome, email e profilo (cosa vede) in un solo passaggio; la password provvisoria arriva per email.",
              "Anche «Persone e ruoli» crea gli account allo stesso modo, con l'email della persona.",
              "Il campo Cantiere/Commessa è un menu preso da «Rubrica e cantieri» anche in Rapportini, Cronoprogramma, SAL, Organico, Fornitori, Cash Flow, Sicurezza, Verbali e Archivio documenti: niente più cantieri scritti in due modi.",
              "Correggendo il nome di una persona, si aggiorna anche l'elenco di «Persone e ruoli»."],
     "strumenti": ["Amministrazione", "Persone e ruoli"]},
    {"id": "3.17.3", "data": "2026-11-06", "titolo": "Accesso ricordato anche sul telefono",
     "voci": ["Inserisci la password una volta: per 12 ore la suite non te la richiede più, anche dopo aver chiuso e riaperto il telefono.",
              "Se il telefono perde il cookie, l'accesso viene ripreso da una copia di riserva sul dispositivo.",
              "Dopo 12 ore, o dopo «Esci», la password viene richiesta di nuovo."],
     "strumenti": []},
    {"id": "3.17.2", "data": "2026-11-06", "titolo": "Computo e Preventivo: importa un computo già fatto senza riclassificare le colonne",
     "voci": ["Carichi il tuo Excel (o CSV) così com'è: la suite trova da sola la riga delle intestazioni, anche sotto titoli e dati dell'azienda.",
              "Capisce nomi come Tariffa, Designazione dei lavori, Q.tà, Prezzo unitario, Importo, e legge tutti i fogli del file.",
              "I titoli dei capitoli (DEMOLIZIONI, OPERE MURARIE…) diventano la categoria delle voci; totali e riporti vengono saltati.",
              "Se il prezzo manca ma c'è l'importo, il prezzo unitario si calcola da solo. Se proprio non riconosce le colonne, le indichi una volta guardando le prime righe."],
     "strumenti": ["Computo e Preventivo"]},
    {"id": "3.17.1", "data": "2026-11-06", "titolo": "Timbratura anche da fuori sede",
     "voci": ["Chi lavora fuori dall'ufficio (cantiere, sopralluogo, da casa) può timbrare scrivendo dove va e cosa fa.",
              "La giustificazione resta nel registro, segnata come «fuori sede», e la vede la direzione.",
              "L'amministratore sceglie quali persone sono abilitate (Accessi del personale → Impostazioni).",
              "Nuovo pulsante tondo ↻ in basso a destra, su tutte le pagine: aggiorna la suite come il tasto F5."],
     "strumenti": ["Accessi del personale"]},
    {"id": "3.17.0", "data": "2026-11-06", "titolo": "Nuovi utenti con nome e cognome e password inviata per email",
     "voci": ["Il nome utente ora si scrive con lo spazio: «Mario Rossi» (niente punto o trattino).",
              "Nuovo utente: si scrivono nome, cognome ed email e la suite spedisce da sola una password provvisoria.",
              "Al primo accesso la persona deve scegliere una password sua.",
              "In Amministrazione si può correggere il nome o l'email di una persona: il cambio vale anche per timbrature, chat e permessi."],
     "strumenti": ["Amministrazione"]},
    {"id": "3.16.1", "data": "2026-11-06", "titolo": "Menu del telefono più comodo, pagina di timbratura più netta",
     "voci": ["Sul telefono il menu laterale mostra subito gli strumenti, senza passare da logo, orologio e profilo.",
              "Pulsante «Menu» grande e blu in alto a sinistra; voci e pulsanti più grandi da toccare.",
              "Dopo aver scelto uno strumento il menu si chiude da solo e si vede subito la pagina.",
              "La pagina aperta dal QR ora serve solo a timbrare: non c'è più il pulsante per entrare nella suite.",
              "Il fumetto dell'assistente non copre più il menu sul telefono."],
     "strumenti": ["Tutta la suite", "Accessi del personale"]},
    {"id": "3.16.0", "data": "2026-11-05", "titolo": "Accessi del personale: timbratura con il QR",
     "voci": ["Nuovo strumento «Accessi del personale»: entrata e uscita con il telefono (le pause si possono attivare dalle impostazioni, ma di base non ci sono).",
              "Si inquadra il QR all'ingresso e si entra con nome utente e password: la pagina di timbratura si apre senza entrare nella suite. C'è anche il pulsante «Devi solo timbrare?» nella pagina di accesso.",
              "Entrata e uscita valgono dalla rete dell'ufficio oppure, da un'altra rete, solo se il telefono è vicino alla sede. La posizione si legge solo in quel momento e non viene salvata.",
              "Ognuno vede le proprie ore. Direzione e amministrazione hanno il registro (chi è dentro, ore, uscite dimenticate), le correzioni tracciate con il motivo e l'Excel per il consulente.",
              "Prima di usarlo: impostare la sede e l'indirizzo di rete in «Sede e QR», stampare il foglio e comunicare ai dipendenti come funziona (c'è un modello di comunicazione)."],
     "strumenti": ["Accessi del personale"]},
    {"id": "3.15.3", "data": "2026-11-05", "titolo": "Video corsi: pulsante «Guarda il video»",
     "voci": ["Dove c'è un video, nello strumento e nei Primi passi compare il pulsante «🎬 Guarda il video». Dove non c'è ancora non si vede nulla.",
              "Gli amministratori incollano i link in Amministrazione → «🎬 Video»."],
     "strumenti": ["Hub", "Amministrazione"]},
    {"id": "3.15.2", "data": "2026-11-04", "titolo": "Segnala un problema, avviso di modifica più chiaro",
     "voci": ["Il pulsante con la foto di Lorenzo (in basso a destra) ora salva ogni segnalazione dentro la suite, con lo strumento in cui eri e se scrivi da telefono o da computer. Funziona sempre, anche senza Slack.",
              "Le segnalazioni si leggono in Amministrazione → «📨 Segnalazioni».",
              "Se un collega modifica lo stesso salvataggio prima di te, l'avviso ora dice chi, quando (ora italiana) e cosa conviene fare: Annulla, riapri e rifai la modifica."],
     "strumenti": ["Amministrazione"]},
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


def _sigle_di(voce):
    """Le sigle degli strumenti citati da una novita' (per nome come in Permessi, oppure direttamente la sigla)."""
    import permessi
    inv = {n.lower(): s for s, n in permessi.NOMI.items()}
    out = []
    for x in voce.get("strumenti") or []:
        k = _s(x)
        s = inv.get(k.lower()) or (k if k in permessi.NOMI else None)
        if s and s not in out:
            out.append(s)
    return out


def sigle_nuove(utente, oggi=None, path=None):
    """{sigla: novita} degli strumenti nuovi o cambiati da poco che questa persona non ha ancora aperto.
    Si accende da sola quando si aggiunge una voce a NOVITE con quello strumento; si spegne per la persona quando lo apre, o dopo GIORNI_NEW giorni."""
    oggi = oggi or dt.date.today()
    try:
        viste = (storage.carica_pratica(NOME_VISTE, path, modulo="cfg") or {}).get(_s(utente).lower(), {})
    except Exception:
        viste = {}
    out = {}
    for v in tutte(path):                       # dalla piu' recente: vale la novita' piu' nuova di ogni strumento
        try:
            eta = (oggi - dt.date.fromisoformat(_s(v.get("data")))).days
        except ValueError:
            continue
        if eta < 0 or eta > GIORNI_NEW:
            continue
        for s in _sigle_di(v):
            if s not in out and viste.get(s) != _chiave(v):
                out[s] = v
    return out


def segna_vista(utente, sigla, novita, path=None):
    """La persona ha aperto lo strumento: il bollino NEW si spegne per lei."""
    if not _s(utente) or not novita:
        return
    tutti = storage.carica_pratica(NOME_VISTE, path, modulo="cfg") or {}
    mie = tutti.setdefault(_s(utente).lower(), {})
    if mie.get(sigla) == _chiave(novita):
        return
    mie[sigla] = _chiave(novita)
    storage.salva_pratica(NOME_VISTE, tutti, path, autore=_s(utente), modulo="cfg")
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
