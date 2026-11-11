"""
guida.py - Guida passo-passo dentro ogni strumento: cosa fare, in che ordine, dove cliccare. Le spunte si aggiornano da sole
(esempio tolto, dati inseriti, salvataggio fatto, dossier generato), cosi' chi usa lo strumento sa sempre a che punto e'.

Per cambiare un testo basta modificare PASSI. Ogni passo: (titolo, istruzione, controllo). Controlli:
  "demo:<chiave>"  -> fatto quando il flag di esempio (ss[chiave]) e' spento
  "dati:<chiave>"  -> fatto quando la tabella ss[chiave] ha righe e non e' un esempio (richiede anche il flag di esempio del modulo)
  "salvato"        -> fatto dopo un salvataggio o una riapertura dell'archivio del modulo
  "dossier"        -> fatto dopo aver generato il dossier del modulo
  None             -> passo senza controllo automatico (si legge e basta)
"""
import streamlit as st

ss = st.session_state

# sigla -> (a cosa serve, [passi], attenzione)
PASSI = {
    "credit": ("Capire che rating darebbe una banca a FCR e cosa fare per migliorarlo.", [
        ("Carica il bilancio", "Nella scheda «1. Dati» trascina il bilancio (PDF, Excel o XBRL) e premi il pulsante blu. Senza file, scegli «Inserimento Dati Manuale».", "demo:dati_demo"),
        ("Controlla i numeri letti", "Verifica ricavi, EBITDA, debiti e patrimonio netto: se un numero non coincide con il bilancio, correggilo a mano e premi «Aggiorna Dati Inseriti».", None),
        ("Aggiungi le commesse", "Nella scheda «2. Commesse» inserisci i lavori in corso: servono a giudicare il portafoglio ordini.", None),
        ("Guarda il rating", "Nella scheda «3. Simulatore» vedi punteggio e fascia. Prova le leve (per esempio meno debito) e guarda come cambia.", None),
        ("Scarica il report", "Nella scheda «6. Report» premi «Genera Report PDF + Word» per il Comitato Fidi.", None),
        ("Salva la pratica", "Nella barra a sinistra premi «💾 Salva pratica»: così non perdi il lavoro.", "salvato"),
    ], "Il rating è una simulazione indicativa, non un rating ufficiale. Controlla sempre i numeri con il commercialista."),
    "bp": ("Pianificare 3-5 anni di una nuova iniziativa (per esempio un capannone): ricavi, costi, mutuo e cassa.", [
        ("Descrivi l'iniziativa", "Nella scheda «1. Wizard AI e Ipotesi» scrivi il nome e racconta il progetto in poche righe.", None),
        ("Genera le ipotesi", "Premi «🪄 Genera le ipotesi con l'AI» (serve la chiave Gemini). Se non c'è, compila le ipotesi a mano.", None),
        ("Controlla le ipotesi", "Rileggi ricavi, costi e importo del mutuo: sono proposte da correggere con i tuoi numeri.", None),
        ("Guarda il piano", "Nelle schede «2. Conto Economico» e «3. Finanziamenti e Cash Flow» controlla utile, rata del mutuo e DSCR.", None),
        ("Scarica il dossier", "Nella scheda «5. Dossier PDF» premi «🚀 Genera il dossier PDF».", None),
        ("Salva", "Apri «💾 Salva e riapri il business plan» in alto, scrivi un nome e premi Salva.", "salvato"),
    ], "Il piano è una stima: l'AI propone, tu decidi. Non è un parere di credito."),
    "cf": ("Capire quanta liquidità serve nei prossimi mesi con il portafoglio dei cantieri.", [
        ("Togli l'esempio", "Il portafoglio che vedi è finto (100 cantieri). Sostituiscilo con i tuoi: importa un file Excel oppure scrivi i cantieri nella tabella.", "demo:cf_demo"),
        ("Inserisci cassa e fido", "Sotto «Ipotesi finanziarie» scrivi la cassa di oggi e il fido concesso dalla banca.", None),
        ("Guarda il Cash Flow", "Nella scheda «2. Cash Flow» vedi mese per mese quando la cassa scende e se si va sotto il fido.", None),
        ("Prova gli imprevisti", "Nella scheda «3. Stress e Soluzioni» simula incassi in ritardo o costi più alti.", None),
        ("Scarica il dossier", "Nella scheda «4. Dossier» premi «📄 Genera dossier PDF ed Excel».", "dossier"),
        ("Salva", "Apri «💾 Salva e riapri il portafoglio» in alto, dai un nome e premi Salva.", "salvato"),
    ], "I cantieri vengono presi dalla tabella: più è aggiornata, più la previsione è affidabile."),
    "pv": ("Passare dal computo dei lavori al prezzo da dare al cliente, con il margine sotto controllo.", [
        ("Inserisci le voci di computo", "Nella scheda «1. Computo» scrivi ogni lavorazione con quantità e COSTI unitari (materiali, manodopera, noli). Puoi anche farle proporre dall'AI da una descrizione.", None),
        ("Imposta spese e utile", "Nella scheda «2. Preventivo e Margine» indica spese generali, utile desiderato, sconto e IVA.", None),
        ("Leggi il margine", "Controlla il prezzo al cliente e lo sconto massimo che puoi concedere senza perdere margine.", None),
        ("Metti alla prova i costi", "Nella scheda «3. Sensibilità e Cash Flow» vedi cosa succede se i costi salgono.", None),
        ("Scarica il preventivo", "Nella scheda «4. Documenti» premi «📄 Genera preventivo (PDF cliente) ed Excel interno».", "dossier"),
        ("Salva", "Apri «💾 Salva e riapri il preventivo» in alto e premi Salva.", "salvato"),
    ], "I costi proposti dall'AI sono stime: verificali su prezzari e progetto prima di inviare un preventivo."),
    "ee": ("Fare un preventivo rapido per pompa di calore, caldaia, cappotto, LED, solare termico o colonnine di ricarica.", [
        ("Scegli l'intervento", "In alto scegli il tipo di lavoro: le voci e i dati da inserire cambiano di conseguenza.", None),
        ("Inserisci i dati", "Nella scheda «1» scrivi i consumi attuali e le caratteristiche dell'intervento: la suite stima il risparmio.", None),
        ("Controlla i costi", "Nella scheda «2» premi «Proponi le voci», poi sostituisci i costi con quelli del tuo listino e imposta ricarico, IVA e detrazione.", None),
        ("Leggi il risultato", "Nella scheda «3» vedi prezzo, risparmio e anni di rientro.", None),
        ("Usa il preventivo", "Nella scheda «5» porti il prezzo nell'Offerta, lo aggiungi allo strumento ESCo o scarichi l'Excel.", None),
        ("Salva", "Apri «💾 Salva e riapri il preventivo» in alto e premi Salva.", "salvato"),
    ], "Consumi, rendimenti e costi proposti sono stime: verificali con un sopralluogo e con il listino."),
    "fp": ("Chiedere ferie e permessi e farli approvare, senza fogli e senza telefonate.", [
        ("Chiedi", "Nella scheda «Chiedi» scegli ferie, permesso a ore, malattia o altro, indica le date e invia: vedi subito i giorni che ti restano.", None),
        ("Approva", "Chi approva trova le richieste in «Da approvare», con l'avviso se in quei giorni restano pochi presenti.", None),
        ("Guarda chi manca", "In «Chi manca» vedi il mese con le assenze di tutti; le ferie approvate compaiono anche nel Calendario.", None),
        ("Regole", "Direzione e amministrazione impostano giorni di ferie, ore di permesso, presenti minimi e chi approva in «Regole».", None),
    ], "La malattia si comunica e vale subito: porta o invia il certificato appena puoi."),
    "ns": ("Registrare le spese di trasferta con la foto dello scontrino e farle rimborsare.", [
        ("Scatta la ricevuta", "In «Nuova spesa» scegli la categoria, scrivi importo e cantiere e allega la foto dello scontrino, anche dalla fotocamera del telefono.", None),
        ("Rimborso chilometrico", "Scegli «Rimborso chilometrico» e scrivi solo i km: l'importo si calcola con la tariffa dell'azienda.", None),
        ("Approvazione", "Il responsabile approva o respinge, con una nota, dalla scheda «Da approvare».", None),
        ("Riepilogo", "L'amministrazione vede il mese per persona, cantiere e categoria, scarica l'Excel e gli scontrini e segna le spese rimborsate.", None),
    ], "Senza ricevuta la spesa si invia solo spiegando bene cosa è stato pagato."),
    "cl": ("Tenere il computo dei lavori rimanenti di un cantiere, con i prezzi aggiornati al nuovo prezzario.", [
        ("Scrivi o carica le voci", "Nella scheda «1» scrivi le voci oppure importa un Excel.", None),
        ("Aggiorna i prezzi", "Per ogni voce metti coefficiente, prezzario nuovo e % di aumento: il prezzo aggiornato si calcola da solo.", None),
        ("Aggiungi le tue colonne", "Con «Aggiungi o togli una colonna» metti le colonne che ti servono (es. subappaltatore, stato).", None),
        ("Guarda i totali", "Nella scheda «2» vedi il computo completo, il totale di progetto, quello aggiornato e la differenza. Scarichi l'Excel.", None),
        ("Salva", "In alto, «Salva e riapri il computo»: dai un nome (es. il cantiere) e lo ritrovano anche i colleghi.", None),
    ], "Le colonne «a mano» servono solo per casi particolari: se le lasci vuote calcolo io."),
    "pc": ("Dare al cliente una pagina con lo stato dei lavori, senza dargli accesso alla suite.", [
        ("Crea il link", "Nella scheda «2» scrivi il nome del cliente e per quanti giorni vale. Copia il link: si vede una volta sola.", None),
        ("Scegli cosa vede", "Nella scheda «3» scrivi a che punto siamo, aggiungi foto e PDF e, se vuoi, un'offerta da accettare.", None),
        ("Mandalo al cliente", "Per email o WhatsApp. Il cliente non ha bisogno di password.", None),
        ("Controlla e chiudi", "Nella scheda «1» vedi se ha accettato (con firma) e puoi revocare o prorogare il link.", None),
    ], "Chi ha il link vede la pagina: metti solo foto e documenti adatti al cliente."),
    "dc": ("Far caricare all'amministratore di un condominio i documenti di una pratica (es. finanziamento), senza dargli accesso alla suite.", [
        ("Crea la richiesta", "Nella scheda «2» scrivi il nome (es. il condominio) e per quanti giorni vale il link. Copia il link: si vede una volta sola.", None),
        ("Togli le voci che non servono", "Nella scheda «3», se qualche documento non si applica a questo caso, togli la spunta: non verrà mostrato e non blocca l'invio.", None),
        ("Mandalo all'amministratore", "Per email o WhatsApp. Non serve nessuna password: il link apre solo questa lista.", None),
        ("Controlla l'arrivo", "Nella scheda «1» vedi quanti documenti sono stati caricati e, quando è tutto pronto, se è stato inviato: scarichi i file da lì.", None),
    ], "Se manca qualcosa dopo l'invio, riapri la richiesta nella scheda «1»: l'amministratore potrà correggere o aggiungere documenti."),
    "mi": ("Controllare gli impianti venduti: produzione, canoni e manutenzione.", [
        ("Aggiungi l'impianto", "Nella scheda «3» scrivi nome, cliente, kWp, data di inizio, canone mensile e prossima manutenzione.", None),
        ("Scrivi le letture", "Nella scheda «2» ogni mese scrivi quanto ha prodotto (dal portale dell'inverter) e quanto hai incassato.", None),
        ("Guarda la situazione", "Nella scheda «1» vedi chi produce meno del 85% dell'atteso, i canoni non incassati e le manutenzioni in arrivo.", None),
        ("Lascia fare al riepilogo", "I problemi arrivano ogni mattina nel riepilogo, se è acceso.", None),
    ], "Se non conosci la produzione attesa, lascia 0: uso 1.200 kWh per ogni kWp."),
    "fe": ("Portare le fatture dei fornitori nello Scadenzario senza riscriverle a mano.", [
        ("Scarica le fatture", "Dal cassetto fiscale o dal programma di fatturazione, in formato XML (anche tante in uno ZIP).", None),
        ("Caricale qui", "Trascinale nel riquadro e scegli se sono ricevute (da pagare) o emesse (da incassare).", None),
        ("Controlla il cantiere", "Se nel testo c'è il codice del cantiere lo propongo io; altrimenti lo scegli dall'elenco.", None),
        ("Aggiungi allo Scadenzario", "Premi il pulsante e poi, nello Scadenzario, Salva. Le fatture già presenti non vengono doppiate.", None),
    ], "Le note di credito non vengono aggiunte."),
    "sp": ("Fare il sopralluogo con il telefono e partire già col preventivo.", [
        ("Compila sul posto", "Rispondi alle domande: tetto, esposizione, superficie, ombre, potenza impegnata.", None),
        ("Scatta le foto", "Tetto, quadro elettrico, contatore e posto dell'inverter.", None),
        ("Leggi gli avvisi", "Ti dico cosa controllare (amianto, potenza, distanza dal quadro).", None),
        ("Crea il preventivo", "Un tasto porta tutto nel Preventivo fotovoltaico, già compilato.", None),
    ], "Salva sempre il sopralluogo prima di andare via."),
    "bd": ("Leggere un bando in pochi secondi e sapere cosa preparare.", [
        ("Carica il PDF", "Il bando o il capitolato con testo selezionabile (non una scansione).", None),
        ("Guarda cosa ho trovato", "CIG, importo, scadenza, categorie SOA e documenti richiesti.", None),
        ("Segui l'elenco", "Spunta le cose da preparare una a una.", None),
    ], "Controlla sempre sul documento originale: la lettura può sbagliare."),
    "sd": ("Non farsi mai sorprendere da una scadenza di persone, ditte o mezzi.", [
        ("Aggiungi le scadenze", "Nella scheda «2» scrivi tipo, persona o mezzo e data. Oppure carica il tuo Excel dalla scheda «3».", None),
        ("Guarda cosa scade", "Nella scheda «1» il semaforo ti dice cosa è scaduto, cosa scade presto e cosa è più avanti.", None),
        ("Scegli quando avvisare", "Nella scheda «3» scegli i giorni di preavviso (di solito 60, 30 e 7).", None),
        ("Lascia fare al riepilogo", "Le scadenze vicine arrivano ogni mattina nel tuo riepilogo, se è acceso.", None),
    ], "Rinnova prima della scadenza e aggiorna la data qui: l'avviso sparisce da solo."),
    "rm": ("Sapere ogni mattina, senza cercare, cosa richiede la tua attenzione.", [
        ("Leggi il riepilogo", "Nella scheda «Il riepilogo di oggi» vedi cosa conta oggi: scadenze, offerte da seguire, chi manca.", None),
        ("Scegli se riceverlo per email", "Se hai un indirizzo email nel profilo, puoi decidere se riceverlo ogni mattina.", None),
        ("Amministratore: accendilo", "Nelle impostazioni accendi l'invio, provalo su di te e invia a tutti.", None),
    ], "Il riepilogo mostra solo gli strumenti che puoi aprire."),
    "lm": ("Scrivere in pochi secondi le lettere che si ripetono, senza ricopiare i dati.", [
        ("Scegli il modello", "Incarico, richiesta di preventivo, convocazione, diffida, risposta tipo o sollecito di pagamento.", None),
        ("Scegli destinatario e cantiere", "Si prendono dalla Rubrica: nome, referente, indirizzo e cliente si compilano da soli.", None),
        ("Completa e controlla", "Compila i pochi campi richiesti: quelli vuoti restano visibili tra [parentesi quadre] nell'anteprima.", None),
        ("Scarica", "Premi «Scarica in Word»: trovi intestazione, data, oggetto, testo e firma.", None),
    ], "Diffide e incarichi sono una base: falli rivedere da un legale. Puoi cambiare i testi nella scheda «Modelli»."),
    "es": ("Valutare un intervento di efficienza energetica che paghi tu e ti ripaghi con il risparmio, e preparare il contratto.", [
        ("Inserisci le bollette", "Nella scheda «1. Diagnosi» scrivi i consumi e le spese dei 12 mesi e, se li hai, i gradi giorno: sono la base per misurare il risparmio.", None),
        ("Elenca gli interventi", "Nella scheda «2. Interventi» scrivi costo, risparmio e incentivi di ogni intervento, oppure aggiungi un impianto da un Preventivo fotovoltaico.", None),
        ("Imposta il contratto", "Scegli risparmio condiviso o canone fisso, durata, finanziamento e risparmio garantito.", None),
        ("Leggi il piano", "Controlla rientro, VAN, TIR e copertura del debito: gli avvisi ti dicono cosa non torna.", None),
        ("Scarica il contratto", "Nella scheda «3. Contratto EPC» scarichi la bozza in Word da completare con il legale.", None),
        ("Salva", "Apri «💾 Salva e riapri il piano ESCo» in alto e premi Salva.", "salvato"),
    ], "Stime al lordo delle imposte: il piano va verificato con il commercialista e il contratto con un legale."),
    "fv": ("Fare in pochi minuti un preventivo fotovoltaico affidabile: prezzo, detrazione, produzione e anni per rientrare.", [
        ("Descrivi il tetto", "Nella scheda «1. Impianto» indica cliente, orientamento, zona, numero e potenza dei moduli, eventuale batteria e i consumi in bolletta.", None),
        ("Controlla i costi", "Nella scheda «2. Costi e prezzo» premi «Proponi le voci», poi sostituisci i costi con quelli del tuo listino e imposta ricarico e IVA.", None),
        ("Leggi il risultato", "Nella scheda «3. Risultato» vedi prezzo, detrazione, risparmio e anni di rientro.", None),
        ("Carica il listino", "Nella scheda «4. Listino» importi il file Excel del fornitore: poi aggiungi le voci con un clic.", None),
        ("Porta il prezzo nell'Offerta", "Nella scheda «5. Documenti» premi «Metti l'impianto nell'Offerta» o scarica l'Excel.", None),
        ("Salva", "Apri «💾 Salva e riapri il preventivo fotovoltaico» in alto e premi Salva.", "salvato"),
    ], "Resa, prezzi dell'energia e detrazione sono stime da verificare alla firma del contratto."),
    "sc": ("Rispondere a «questa settimana ho cassa?» con le fatture da incassare e da pagare.", [
        ("Togli l'esempio", "Premi «Svuota l'esempio e parti da zero»: le fatture che vedi ora sono finte.", "demo:sc_demo"),
        ("Inserisci le fatture", "Apri «🧾 Importa fatture elettroniche (XML)» e trascina i file scaricati dal cassetto fiscale. In alternativa scrivile nella tabella o importa un Excel.", "dati:sc_df"),
        ("Scrivi saldo e fido", "Sotto «Ipotesi di previsione» metti il saldo del conto e il fido della banca.", None),
        ("Guarda la cassa", "Nella scheda «2. Cassa settimanale» vedi settimana per settimana se la cassa regge.", None),
        ("Sollecita i clienti", "Nella scheda «3. Solleciti» trovi le bozze di lettera per chi è in ritardo: rileggile prima di inviarle.", None),
        ("Salva", "Apri «💾 Salva e riapri lo scadenzario», dai un nome (es. «Ottobre») e premi Salva.", "salvato"),
    ], "Nelle fatture XML non c'è il cantiere: puoi scriverlo dopo nella tabella. Le note di credito vanno tolte a mano dalla fattura collegata."),
    "sl": ("Controllare ogni commessa: quanto hai fatturato, quanto hai speso e quanto margine resta a fine lavori.", [
        ("Togli l'esempio", "Premi «Svuota l'esempio e parti da zero»: le commesse che vedi sono finte.", "demo:sl_demo"),
        ("Inserisci le commesse", "Nella scheda «1. Commesse e Dati» scrivi contratto, costi previsti, date e avanzamento reale di ogni commessa.", "dati:sl_com"),
        ("Registra i SAL e i costi", "Nelle tabelle sotto aggiungi i SAL emessi (con la data) e le fatture dei fornitori già sostenute.", None),
        ("Leggi il controllo", "Nella scheda «2. Controllo commesse» il semaforo dice se il margine a finire regge. Rosso = da intervenire.", None),
        ("Passa i dati agli altri strumenti", "Nella scheda «3. Integrazioni» invia SAL e costi allo Scadenzario e le commesse al Cash Flow.", None),
        ("Salva", "Apri «💾 Salva e riapri la contabilità lavori» in alto e premi Salva.", "salvato"),
    ], "«Invia al Cash Flow» sostituisce tutto il portafoglio del Cash Flow: salvalo prima se contiene altri cantieri."),
    "ga": ("Decidere a quali gare partecipare, con che ribasso, e non perdere nessuna scadenza.", [
        ("Togli l'esempio", "Premi «Svuota l'esempio e parti da zero»: le gare che vedi sono finte.", "demo:ga_demo"),
        ("Inserisci le gare", "Nella scheda «1. Gare e Documenti» scrivi ente, importo a base d'asta, costi stimati, scadenza e probabilità di vincere.", "dati:ga_gare"),
        ("Prepara i documenti", "Scegli una gara e premi per aggiungere la check-list dei documenti richiesti, poi spunta quelli pronti.", None),
        ("Scegli il ribasso", "Nella scheda «2. Valutazione» trovi il ribasso massimo che mantiene il margine obiettivo e il valore atteso.", None),
        ("Passa le gare vinte al SAL", "Nella scheda «3. Integrazioni» premi «📐 Invia le gare vinte a SAL e contabilità».", None),
        ("Salva", "Apri «💾 Salva e riapri le gare» in alto e premi Salva.", "salvato"),
    ], "Il ribasso massimo dipende dai costi che inserisci: se sono sottostimati, anche il ribasso consigliato lo è."),
    "fo": ("Tenere sotto controllo documenti, contratti e preventivi dei fornitori e subappaltatori.", [
        ("Togli l'esempio", "Premi «Svuota l'esempio e parti da zero».", "demo:fo_demo"),
        ("Inserisci i documenti", "Nella scheda «1. Dati» scrivi per ogni fornitore DURC, assicurazioni e SOA con la data di scadenza.", "dati:fo_doc"),
        ("Aggiungi contratti e offerte", "Sotto trovi i contratti aperti e le offerte ricevute per la stessa fornitura.", None),
        ("Guarda cosa scade", "Nella scheda «2. Controllo» vedi i documenti scaduti o in scadenza e i fornitori da non usare.", None),
        ("Confronta i preventivi", "Nella scheda «3. Confronto preventivi» vedi l'offerta più bassa tra i fornitori in regola. Se due fornitori hanno scritto la stessa lavorazione in modo diverso, la suite propone di unirle: spunta e conferma.", None),
        ("Salva", "Apri «💾 Salva e riapri i fornitori» in alto e premi Salva.", "salvato"),
    ], "Un fornitore con documenti scaduti non dovrebbe entrare in cantiere: controlla il rosso prima di assegnare lavori."),
    "sx": ("Verificare formazioni, idoneità mediche e documenti obbligatori di ogni cantiere.", [
        ("Togli l'esempio", "Premi «Svuota l'esempio e parti da zero».", "demo:sx_demo"),
        ("Inserisci le persone", "Nella scheda «1. Dati» scrivi chi lavora in quale cantiere e le scadenze di corsi e visite mediche.", "dati:sx_pers"),
        ("Spunta i documenti di cantiere", "Per ogni cantiere indica quali documenti obbligatori (POS, PSC, notifica) sono presenti.", None),
        ("Guarda i problemi", "Nella scheda «2. Controllo» vedi i cantieri a rischio e cosa va rinnovato.", None),
        ("Scarica il dossier", "Nella scheda «3. Dossier» premi il pulsante per PDF ed Excel.", "dossier"),
        ("Salva", "Apri «💾 Salva e riapri la sicurezza» in alto e premi Salva.", "salvato"),
    ], "Strumento di promemoria: la verifica ufficiale resta al responsabile della sicurezza (RSPP)."),
    "da": ("Avere in un unico posto DURC, SOA, certificazioni, assicurazioni e visura dell'azienda, con le scadenze e i file veri.", [
        ("Togli l'esempio", "Premi «Svuota l'esempio e parti da zero».", "demo:da_demo"),
        ("Inserisci i documenti", "Nella scheda «1. Documenti» scrivi tipo, descrizione, numero e scadenza di ogni documento aziendale.", "dati:da_doc"),
        ("Carica il file", "Scegli il documento dal menu qui sotto e allega il PDF o la foto: resta scaricabile da qui.", None),
        ("Guarda le scadenze", "Qui sotto vedi subito quali documenti sono scaduti o in scadenza.", None),
        ("Scarica il dossier", "Nella scheda «2. Dossier» premi il pulsante per PDF ed Excel.", "dossier"),
        ("Salva", "Apri «💾 Salva e riapri i documenti aziendali» in alto e premi Salva.", "salvato"),
    ], "I file caricati qui non finiscono nelle versioni storiche del salvataggio: restano nell'archivio a parte, sempre scaricabili."),
    "mz": ("Sapere quanto costa ogni mezzo all'ora, se è usato abbastanza e quando scadono revisioni e assicurazioni.", [
        ("Togli l'esempio", "Premi «Svuota l'esempio e parti da zero».", "demo:mz_demo"),
        ("Inserisci i mezzi", "Nella scheda «1. Mezzi e Utilizzo» scrivi i costi fissi, i costi per ora e le ore previste all'anno.", "dati:mz_mezzi"),
        ("Registra l'uso e le scadenze", "Aggiungi le ore di uso per cantiere e le scadenze (revisione, assicurazione, tagliando).", None),
        ("Leggi costi e scadenze", "Nella scheda «2. Costi e Scadenze» vedi tariffa oraria, mezzi poco usati e scadenze vicine.", None),
        ("Invia i costi al SAL", "Nella scheda «3. Integrazioni» premi «📐 Invia i costi dei mezzi a SAL e contabilità».", None),
        ("Salva", "Apri «💾 Salva e riapri il parco mezzi» in alto e premi Salva.", "salvato"),
    ], "Se un mezzo ha poche ore di uso, il costo orario sale: è un segnale, non un errore."),
    "og": ("Capire se in certi mesi mancano o avanzano persone rispetto ai cantieri.", [
        ("Togli l'esempio", "Premi «Svuota l'esempio e parti da zero».", "demo:og_demo"),
        ("Inserisci le risorse", "Nella scheda «1. Risorse e Assegnazioni» scrivi persone o squadre con costo orario e ore al giorno (una squadra di 3 = 24). Le ore del mese si calcolano dal calendario, senza sabati, domeniche e festivi. Se qualcuno viene assunto o cessa, scrivi la data: esce da solo dai conti.", "dati:og_ris"),
        ("Ferie e chiusure", "Nella tabella «Ferie, malattie, chiusure» scrivi i giorni di assenza; con «Tutti» valgono per tutta l'azienda. In «Ipotesi» puoi indicare la festa del patrono.", None),
        ("Assegna ai cantieri", "Nella seconda tabella scrivi chi lavora a quale cantiere, da quando a quando, con le ore al mese.", None),
        ("Guarda il carico", "Nella scheda «2. Carico di lavoro» vedi i mesi in sovraccarico (serve più gente) o scarichi (ore ferme).", None),
        ("Scarica il dossier", "Nella scheda «3. Dossier» premi il pulsante per PDF ed Excel.", "dossier"),
        ("Salva", "Apri «💾 Salva e riapri l'organico» in alto e premi Salva.", "salvato"),
    ], "Le ore disponibili vanno scritte al netto di ferie e malattie."),
    "rp": ("Il giornale del cantiere dal telefono: cosa si è fatto oggi e cosa non va.", [
        ("Scrivi il rapportino", "Nella scheda «✍️ Rapportino» scegli il cantiere, scrivi quante persone c'erano, le ore totali e cosa avete fatto. Premi «➕ Salva il rapportino».", "dati:rp_rapp"),
        ("Segnala un problema", "Se qualcosa non va, vai in «⚠️ Segnalazioni», descrivi il problema, scegli la gravità e premi «⚠️ Invia la segnalazione».", None),
        ("Chiudi le segnalazioni risolte", "Sempre in «⚠️ Segnalazioni», quando un problema è risolto premi «✅ Chiusa».", None),
        ("Guarda i cantieri", "In «📊 Cantieri» vedi chi non manda il rapportino da giorni.", None),
    ], "Ogni rapportino si salva subito e lo vede anche l'ufficio. Se in due scrivete insieme non si perde niente."),
    "gt": ("Vedere su una linea del tempo quando parte e finisce ogni fase e dove c'è ritardo.", [
        ("Togli l'esempio", "Premi «Svuota l'esempio e parti da zero».", "demo:gt_demo"),
        ("Inserisci le fasi", "Nella scheda «1. Fasi» scrivi cantiere, fase, inizio, fine e avanzamento reale. Per partire veloce usa «Carica le commesse dal SAL».", "dati:gt_fasi"),
        ("Collega le fasi", "Nella colonna «Parte dopo la fase…» scrivi quale fase deve finire prima (oppure premi «🔗 Collega le fasi in sequenza»). Così, se una fase slitta, il Gantt sposta da solo quelle successive. Per un'attesa scrivi «Strutture +5», per far partire una fase in anticipo «Strutture -10».", None),
        ("Segna fermi e vincoli", "In «Giorni di fermo» scrivi ferie e maltempo (o premi «🎄 Aggiungi le festività italiane»): allungano le fasi. Nella colonna «Non prima del» metti la data di arrivo dei materiali o dei permessi.", None),
        ("Aggiorna l'avanzamento", "Ogni settimana cambia la percentuale di avanzamento reale delle fasi in corso.", None),
        ("Leggi il Gantt", "Nella scheda «2. Gantt e ritardi» la linea rossa è oggi: le barre in giallo o rosso sono in ritardo.", None),
        ("Scarica il dossier", "Nella scheda «3. Dossier» premi il pulsante per PDF ed Excel.", "dossier"),
        ("Salva", "Apri «💾 Salva e riapri il cronoprogramma» in alto e premi Salva.", "salvato"),
    ], "I legami valgono dentro lo stesso cantiere e il nome della fase va scritto uguale. I giorni di fermo e le date «Non prima del» le scrivi tu: il programma non sa da solo che piove o che il camion è in ritardo."),
    "mc": ("Vedere il margine vero di ogni commessa, con i costi di subappalti, ore, materiali e mezzi.", [
        ("Inserisci le commesse", "In «SAL e contabilità lavori» scrivi le commesse con contratto, costi preventivati e avanzamento reale.", None),
        ("Compila gli altri strumenti", "Subappalti, Presenze, Materiali e Parco mezzi: più dati metti, più il margine è vero. Salva ognuno con «Salva e riapri».", None),
        ("Scegli i costi da contare", "Qui sopra scegli quali fonti includere: i costi già mandati a SAL non vengono contati due volte.", None),
        ("Leggi i margini", "Rosso = il margine finale previsto è molto sotto il preventivato; giallo = leggermente sotto.", None),
    ], "È una stima di gestione: il margine finale dipende dall'avanzamento reale che inserisci."),
    "sa": ("Sapere quanto devi ancora pagare a ogni subappaltatore e se i suoi documenti sono in regola.", [
        ("Togli l'esempio", "Premi «Svuota l'esempio e parti da zero».", "demo:sa_demo"),
        ("Inserisci i contratti", "Nella scheda «1. Dati» scrivi subappaltatore, commessa, importo e ritenuta.", "dati:sa_con"),
        ("Registra i SAL e i pagamenti", "Aggiungi ogni SAL ricevuto con l'importo lordo e quanto hai già pagato. Con «Inserimento veloce» scrivi poche lettere del nome («adam») e scegli dai suggerimenti.", None),
        ("Registra i documenti", "DURC, polizze e idoneità con la data di scadenza.", None),
        ("Leggi i risultati", "Nella scheda «2. Risultati» vedi cosa devi pagare e chi ha documenti scaduti: non pagarlo finché non li rinnova.", None),
        ("Salva", "Apri «💾 Salva e riapri i subappalti» in alto e premi Salva.", "salvato"),
    ], "L'avviso sui pagamenti è un promemoria: la valutazione legale resta all'ufficio o al consulente."),
    "pr": ("Registrare le ore di ognuno per commessa e vedere il costo della manodopera.", [
        ("Togli l'esempio", "Premi «Svuota l'esempio e parti da zero».", "demo:pr_demo"),
        ("Inserisci le persone", "Nella scheda «1. Dati» scrivi nome, qualifica e costo orario aziendale (se hai solo la RAL usa «Calcola il costo orario dalla RAL»). Con «Cessato il» la persona non viene più proposta.", "dati:pr_per"),
        ("Registra le ore", "Dal telefono usa «Registra le mie ore»: scegli il giorno, la commessa e le ore, poi premi Registra.", None),
        ("Leggi i risultati", "Nella scheda «2. Risultati» vedi ore, straordinari e costo per commessa.", None),
        ("Salva", "Apri «💾 Salva e riapri le presenze» in alto e premi Salva.", "salvato"),
    ], "Il costo orario è il costo per l'azienda, non la paga netta. Sono dati personali: trattali con riservatezza."),
    "mt": ("Sapere cosa è stato ordinato, cosa è arrivato in cantiere e quanto costa per commessa.", [
        ("Togli l'esempio", "Premi «Svuota l'esempio e parti da zero».", "demo:mt_demo"),
        ("Inserisci gli ordini", "Nella scheda «1. Dati» scrivi materiale, fornitore, commessa, quantità, prezzo e data di consegna prevista.", "dati:mt_ord"),
        ("Segna le consegne", "Quando arriva scrivi «sì» in «Consegnato», la data e il numero del DDT.", None),
        ("Archivia le bolle", "Nella scheda «5. Bolle (DDT)» carica il PDF, la foto o l'Excel della bolla: la suite propone numero e data, tu controlli. Con «Leggi la bolla con l'IA» compila anche le righe e le abbina agli ordini aperti: tu confermi e diventano consegnati. Da Excel puoi anche aggiungere le righe agli ordini.", None),
        ("Registra carichi e scarichi", "Nella seconda tabella segna cosa entra e cosa esce: la giacenza si calcola da sola, per magazzino. Con «Magazzino con la pistola dei codici a barre» spari l'etichetta e il movimento si registra da solo; i codici si scrivono nella tabella «Articoli e codici a barre», dove puoi anche fissare la scorta minima.", None),
        ("Ordine veloce", "Apri «Nuovo ordine veloce»: scrivi poche lettere e scegli dai suggerimenti. Scelti materiale e fornitore il prezzo si compila da solo con l'ultimo pagato.", None),
        ("Salva", "Apri «💾 Salva e riapri i materiali» in alto e premi Salva.", "salvato"),
    ], "Un ritardo si vede in rosso: controlla prima il fornitore."),
    "vr": ("Non perdere le decisioni delle riunioni: ogni azione ha un responsabile e una scadenza.", [
        ("Togli l'esempio", "Premi «Svuota l'esempio e parti da zero».", "demo:vr_demo"),
        ("Scrivi il verbale", "Nella scheda «1. Dati» aggiungi la riunione con data, partecipanti e decisioni.", "dati:vr_ver"),
        ("Aggiungi le azioni", "Nella seconda tabella scrivi cosa fare, chi e entro quando. Il responsabile è il nome utente (es. mario).", None),
        ("Crea i compiti", "Nella scheda «3. Collegamenti» premi «Crea i compiti nella chat»: ognuno li vede nella chat e nel calendario.", None),
        ("Salva", "Apri «💾 Salva e riapri i verbali» in alto e premi Salva.", "salvato"),
    ], "I compiti si creano solo per persone che hanno un utente nella suite."),
    "ac": ("Registrare entrata e uscita dal telefono, senza fogli e senza dimenticanze.", [
        ("Inquadra il QR", "Con la fotocamera del telefono inquadra il codice all'ingresso: si apre la pagina di timbratura.", None),
        ("Accedi", "Scrivi nome utente e password. Se hai già la suite aperta sul telefono entri da solo.", None),
        ("Premi il pulsante", "Entrata quando arrivi, Uscita quando vai via. Fuori dalla rete dell'ufficio il telefono chiede la posizione: serve solo in quel momento.", None),
        ("Controlla le tue ore", "Nella scheda «Le mie presenze» vedi entrata, uscita e ore. Se manca qualcosa chiedi alla direzione di correggerla.", None),
    ], "La posizione si legge solo quando premi Entrata o Uscita da fuori rete e non viene salvata. Se hai dimenticato l'uscita, il giorno dopo puoi comunque timbrare l'entrata."),
    "nv": ("Sapere cosa è cambiato nella suite dopo ogni aggiornamento, senza chiedere a nessuno.", [
        ("Leggi l'ultima novità", "La più recente è in alto, già aperta. Le altre si aprono con un clic.", None),
        ("Cerca", "Scrivi una parola (per esempio «bolle» o «compiti») o scegli uno strumento per vedere solo le novità che lo riguardano.", None),
        ("Aggiungi una novità (amministratori)", "In fondo alla pagina scrivi titolo e voci in parole semplici e premi «Pubblica».", None),
    ], "Se una novità riguarda il tuo lavoro, provala subito: ogni strumento ha il suo riquadro «Come si usa»."),
    "sk": ("Vedere in un posto solo i conti e l'andamento di ogni cantiere.", [
        ("Prima la Rubrica", "In «Rubrica e cantieri» scrivi i cantieri con il loro codice e lo stato. «In corso» e «In preparazione» sono i cantieri vivi.", None),
        ("Scrivi il cantiere sempre uguale", "Negli altri strumenti (Scadenzario, SAL, Presenze, Materiali, Subappalti, Mezzi, Rapportini) usa lo stesso nome o lo stesso codice della Rubrica.", None),
        ("Scegli il cantiere", "Nella Scheda cantiere scegli il cantiere: vedi fatturato, incassato, costi, margine e cassa. Le schede dicono da dove arriva ogni numero.", None),
        ("Sistema i nomi", "Se compare «Non in Rubrica», un nome è scritto diverso: correggilo nello strumento o aggiungi il cantiere alla Rubrica.", None),
    ], "Qui non inserisci nulla: la scheda legge i dati degli altri strumenti, quindi non si scrive niente due volte."),
    "ta": ("Sapere cosa c'è da fare, chi se ne occupa e per quando, tutto in un posto solo.", [
        ("Aggiungi un compito", "Nella scheda «2. Nuovo e tabella» scrivi cosa fare, il responsabile, la scadenza e la commessa.", None),
        ("Muovi i compiti", "Nella bacheca premi ◀ e ▶ per spostare un compito tra Da fare, In corso, In attesa e Fatto.", None),
        ("Controlla i ritardi", "La scheda «4. Per persona» mostra chi ha compiti scaduti. Le scadenze compaiono anche nel Calendario.", None),
        ("Salva", "Apri «💾 Salva e riapri» in alto e premi Salva.", "salvato"),
    ], "Il responsabile è il nome utente: scrivilo uguale per vedere «Solo i miei»."),
    "fc": ("Seguire ogni commessa lungo i 28 passaggi dello schema FCR, sapendo chi deve fare cosa e cosa è bloccato.", [
        ("Avvia una commessa", "Nella scheda «2. Scheda commessa» apri «Avvia il flusso» e scegli la pratica del Registro commerciale: il suo codice è il codice madre.", "dati:fc_df"),
        ("Di' chi è chi", "Nella scheda «5. Chi è chi e collegamenti» scrivi il nome utente di chi ricopre ogni ruolo (DC, DT, CdA…): servono per assegnare compiti e avvisi.", None),
        ("Scrivi le tue iniziali", "In cima alla scheda: finiscono accanto a ogni passaggio che registri, insieme alla data.", None),
        ("Registra i passaggi", "Apri il passaggio e premi «Segna fatto». Dove serve, un'altra persona preme «Approva». Il CdA, il Presidente e l'assemblea danno GO o NO GO.", None),
        ("Lascia fare al flusso", "Ogni passaggio aggiorna da solo lo stato nel Registro commerciale e crea il compito per il responsabile, con scadenza. Chi deve approvare riceve un messaggio in chat.", None),
        ("Guarda cosa blocca", "Se un GO manca, i passaggi dopo non si completano. Il NO GO del CdA o dell'assemblea ferma la commessa; quello del Presidente riporta l'offerta al passo 7.", None),
        ("Controlla e salva", "La scheda «3. Controlli» segnala passaggi senza iniziali, fuori sequenza o fermi. Poi apri «💾 Salva e riapri» in alto e premi Salva.", "salvato"),
    ], "Il flusso non sostituisce le firme e le approvazioni vere: registra chi le ha date e quando."),
    "ad": ("Avere in un posto solo i link dei documenti di ogni commessa e sapere cosa manca o scade.", [
        ("Togli l'esempio", "Premi «Svuota l'esempio e parti da zero».", "demo:ad_demo"),
        ("Inserisci i documenti", "Nella scheda «1. Dati» scrivi commessa, categoria, titolo e il link al file o alla cartella (https://...).", "dati:ad_doc"),
        ("Controlla cosa manca", "Nella scheda «2. Risultati» vedi i documenti attesi che non hai registrato e quelli scaduti.", None),
        ("Salva", "Apri «💾 Salva e riapri l'archivio documenti» in alto e premi Salva.", "salvato"),
    ], "I file restano dove sono: la suite conserva solo il link."),
    "ch": ("Scrivere ai colleghi senza uscire dalla suite: canali, gruppi privati e chat dirette.", [
        ("Scegli dove scrivere", "A sinistra trovi i canali pubblici, i gruppi privati e le chat dirette: un pallino rosso indica i messaggi da leggere.", None),
        ("Apri una chat diretta", "Premi «Nuova chat diretta», scegli la persona e scrivi: la leggete solo voi due.", None),
        ("Allega e collega", "Puoi allegare una foto o un PDF e collegare lo strumento di cui parli: chi legge lo apre con un clic.", None),
        ("Attiva gli avvisi", "Nella scheda «Avvisi sul telefono» collega Telegram o ntfy: l'avviso dice solo chi ha scritto.", None),
    ], "Canali pubblici: li vedono tutti. Gruppi privati e chat dirette: solo i membri, nemmeno gli amministratori."),
    "of": ("Preparare un'offerta completa: computo, parcelle, quadro economico, finanziamento per millesimi e richieste di finanziamento.", [
        ("Descrivi la pratica", "Nella scheda «1. Pratica» scrivi condominio, indirizzo, unità e i testi dell'intervento (o prendi i dati dal Registro commerciale).", None),
        ("Carica il computo", "Nella scheda «2. Computo» importa il file del collega: l'app legge le voci dei capitoli, le ipotesi A/B e gli sconti.", None),
        ("Calcola le parcelle", "Nella scheda «3. Parcelle» scegli categoria e prestazioni (D.Lgs. 36/2023) oppure scrivi la parcella a mano; aggiungi il Responsabile Lavori.", None),
        ("Controlla il QTE", "Nella scheda «4. QTE» trovi lavori, IVA, spese professionali e totale progetto per ogni opzione.", None),
        ("Carica i millesimi e simula", "Nella scheda «5. Finanziamento e millesimi» importa la tabella millesimale e scegli tasso, durate, detrazione e risparmio energetico.", None),
        ("Aggiungi il mercato", "Nella scheda «6. Mercato» scrivi gli annunci della zona (così com'è / efficientato).", None),
        ("Segui i finanziamenti", "Nella scheda «7. Continuità finanziaria» registra le richieste al Condominio e ai condomini (AGOS) con stato, esito e documenti.", None),
        ("Genera l'offerta", "Nella scheda «8. Offerta» premi «Genera» e scarica PowerPoint, PDF ed Excel.", "dossier"),
        ("Salva", "Apri «💾 Salva e riapri l'offerta» in alto, scrivi il codice pratica come nome e premi Salva.", "salvato"),
    ], "I calcoli sono simulazioni: recupero fiscale, risparmio e valori di mercato vanno verificati caso per caso. Salva una pratica per ogni condominio."),
    "rc": ("Sapere a che punto è ogni pratica commerciale, quanto vale e cosa va fatto adesso.", [
        ("Importa il registro", "Nella scheda «4. Importa dal tuo Excel» carica il file del registro: l'app legge i fogli Registro ed Eliminati e riconosce da sola le colonne.", None),
        ("Guarda il cruscotto", "Nella scheda «1. Cruscotto» vedi le pratiche per stato e per commerciale, il valore in corso e la pipeline (valore × % di successo).", None),
        ("Cerca una pratica", "Nella scheda «2. Pratiche» cerca per città, indirizzo, amministratore o codice, e filtra per stato o commerciale.", None),
        ("Segui i prossimi interventi", "Nella scheda «3. Da fare» vedi cosa è scaduto o sta per scadere e chi lo deve fare. Quando è fatto, aggiorna stato e scadenza nella scheda «2».", None),
        ("Salva", "Apri «💾 Salva e riapri il registro» in alto e premi Salva.", "salvato"),
    ], "Il valore pipeline lo ricalcola l'app: non serve scriverlo. Per togliere una pratica senza perderla, metti «Eliminata» nella colonna Archivio."),
    "pz": ("Avere i prezzi di riferimento a portata di mano per preventivi e acquisti, e sapere quando vanno aggiornati.", [
        ("Carica il prezziario", "Nella scheda «2. Carica un prezziario» scegli il file Excel del listino: l'app riconosce il quadrimestre dal nome, mostra cosa ha letto e cosa ha saltato. Poi premi «Salva».", None),
        ("Cerca una voce", "Nella scheda «1. Cerca» scrivi una parola («intonaco»), un codice o scegli un capitolo. Clicca una riga per vedere il dettaglio e le varianti.", None),
        ("Usalo nel preventivo", "In «Computo e Preventivo», apri «📚 Aggiungi voci dal prezziario», scegli le voci e la quantità: codice, unità e costo arrivano da soli.", None),
        ("Controlla gli ordini", "In «Ordini e approvazioni» scrivi nell'ordine il codice della voce e la quantità: chi approva vede un avviso se il prezzo supera quello del prezziario.", None),
        ("Aggiorna ogni quadrimestre", "Quando esce il nuovo listino caricalo qui: nella scheda «3. Confronta quadrimestri» vedi quali prezzi sono saliti o scesi.", None),
    ], "Sono prezzi di riferimento, non offerte dei fornitori. Se un listino è scaduto, nell'Hub compare l'avviso «prezzi da aggiornare»."),
    "ru": ("Avere telefono, email e referente di tutti a portata di mano, e dare a ogni cantiere un codice unico.", [
        ("Togli l'esempio", "Premi «Svuota l'esempio e parti da zero».", "demo:ru_demo"),
        ("Inserisci i contatti", "Nella scheda «1. Contatti e cantieri» scrivi o importa da Excel fornitori, clienti ed enti, con telefono ed email.", "dati:ru_cont"),
        ("Inserisci i cantieri", "Più sotto scrivi i cantieri. Lascia vuoto il «Codice»: premi «🔢 Assegna i codici mancanti» e ognuno riceve il suo (CAN-anno-numero).", "dati:ru_can"),
        ("Chiama o scrivi", "Nella scheda «2. Scheda contatto» scegli un nome: trovi i pulsanti Chiama, Scrivi e WhatsApp e tutto ciò che lo riguarda (documenti, fatture, cantieri).", None),
        ("Controlla i nomi", "Nella scheda «4. Controllo nomi» vedi i nomi scritti diversamente negli altri strumenti (refusi, «Srl» in più) e li correggi tutti con un clic.", None),
        ("Usa lo stesso codice ovunque", "Scrivi il codice cantiere nelle altre tabelle: così ritrovi tutto di un lavoro. La colonna «Codice in altro sistema» serve se un cantiere ha un codice anche altrove.", None),
        ("Salva", "Apri «💾 Salva e riapri la rubrica» in alto e premi Salva.", "salvato"),
    ], "I collegamenti con fatture e documenti funzionano per nome: scrivi il fornitore sempre allo stesso modo in tutti gli strumenti."),
    "pe": ("Avere l'elenco di chi lavora in azienda e dare a ciascuno solo gli accessi che gli servono.", [
        ("Togli l'esempio", "Premi «Svuota l'esempio e parti da zero».", "demo:pe_demo"),
        ("Inserisci il personale", "Nella scheda «1. Elenco del personale» scrivi o importa da Excel nome, ruolo, reparto, telefono e cantiere di ognuno.", "dati:pe_pers"),
        ("Guarda i ruoli", "Nella scheda «2. Ruoli e profili» vedi quali strumenti apre ogni ruolo.", None),
        ("Crea gli accessi", "Nella scheda «3. Accessi all'app» (solo amministratore) scegli la persona, controlla il profilo proposto e premi «Crea account e abilita». Comunica la password temporanea in privato.", None),
        ("Revoca chi esce", "Quando qualcuno non è più in servizio, mettilo «No» in elenco e usa «⛔ Revoca accesso».", None),
        ("Salva", "Apri «💾 Salva e riapri l'elenco» in alto e premi Salva.", "salvato"),
    ], "Sono dati personali: tienili essenziali e dai accesso a questo strumento solo a chi serve. Chi non è nell'elenco ma ha un account compare come «account senza persona»."),
    "lg": ("Passare un cliente allo studio legale con tutto il fascicolo, e non perdere i termini di riserve, contratti e penali.", [
        ("Togli l'esempio", "Premi «Svuota l'esempio e parti da zero».", "demo:lg_demo"),
        ("Registra i solleciti fatti", "Nella scheda «1. Dati» scrivi ogni sollecito mandato a un cliente (data, come, risposta): finisce nel fascicolo.", None),
        ("Scrivi riserve e contratti", "Per ogni riserva o variante scrivi il termine che ti ha detto lo studio. Per i contratti e le polizze la scadenza.", "dati:lg_riserve"),
        ("Passa un cliente allo studio", "Nella scheda «2. Passa allo studio» scegli il cliente, controlla il messaggio e premi «Invia allo studio» (oppure scarica il fascicolo PDF).", None),
        ("Guarda le penali", "Scrivi i termini contrattuali di fine lavori nella scheda 1: nella scheda «4. Penali di ritardo» vedi il ritardo e la penale stimati dal Cronoprogramma.", None),
        ("Scarica il dossier", "Nella scheda «5. Dossier» premi il pulsante per PDF ed Excel.", "dossier"),
        ("Salva", "Apri «💾 Salva e riapri lo studio legale» in alto e premi Salva.", "salvato"),
    ], "È un promemoria, non una consulenza legale: le scadenze di legge le fissa lo studio e tu scrivi le date che comunica. L'invio diretto richiede che l'amministratore imposti STUDIO_LEGALE_EMAIL o lo Slack dello studio."),
    "bk": ("Sapere quali fatture sono state pagate o incassate guardando l'estratto conto, senza spuntare a mano.", [
        ("Togli l'esempio", "Premi «Svuota l'esempio e parti da zero».", "demo:bk_demo"),
        ("Carica l'estratto conto", "Scarica dalla banca l'estratto in Excel o CSV e importalo da «Importa da Excel/CSV». Entrate con +, uscite con −.", "dati:bk_mov"),
        ("Apri prima lo Scadenzario", "Le fatture arrivano dallo Scadenzario: aprilo (o riaprine il salvataggio) prima di venire qui.", None),
        ("Controlla gli abbinamenti", "Nella scheda «2. Abbinamenti» i 🟢 sono sicuri, i 🟡 vanno guardati. Togli la spunta a quelli sbagliati.", None),
        ("Conferma", "Premi «Segna come pagate/incassate»: lo Scadenzario si aggiorna. Poi salvalo.", None),
        ("Scarica il dossier", "Nella scheda «3. Dossier» premi il pulsante per PDF ed Excel.", "dossier"),
        ("Salva", "Apri «💾 Salva e riapri i movimenti» in alto e premi Salva.", "salvato"),
    ], "Gli abbinamenti sono proposte: l'ultima parola è tua. I movimenti senza fattura (stipendi, spese bancarie) restano nell'elenco a parte."),
    "oa": ("Far approvare ogni acquisto alla persona giusta, in base all'importo, con la traccia di chi ha deciso.", [
        ("Togli l'esempio", "Premi «Svuota l'esempio e parti da zero».", "demo:oa_demo"),
        ("Decidi chi approva cosa", "In «Chi approva cosa» scrivi le fasce d'importo e, se vuoi, i nomi utente autorizzati per ognuna.", None),
        ("Inserisci gli ordini", "Una riga per ordine: fornitore, importo, cantiere e chi lo chiede. Poi premi «🔢 Assegna i numeri mancanti».", "dati:oa_ord"),
        ("Approva o respingi", "Nella scheda «2. Da approvare» scegli l'ordine: solo chi è autorizzato (e non l'ha chiesto) può approvare. Per respingere serve il motivo.", None),
        ("Controlla le anomalie", "Nella scheda «3. Controllo» vedi ordini con fornitori irregolari, senza cantiere o in attesa da troppo.", None),
        ("Scarica il dossier", "Nella scheda «4. Dossier» premi il pulsante per PDF ed Excel.", "dossier"),
        ("Salva", "Apri «💾 Salva e riapri gli ordini» in alto e premi Salva: il salvataggio conserva chi ha approvato e quando.", "salvato"),
    ], "I nomi dei richiedenti e degli approvatori sono i nomi utente: per il controllo «chi chiede non approva» devono essere scritti uguali."),
    "ca": ("Una sola lista di tutte le scadenze: fatture, gare, documenti, formazioni, mezzi e fasi.", [
        ("Scegli cosa vedere", "In alto scegli quanti giorni mostrare e il tipo di scadenza.", None),
        ("Leggi le scadenze", "Nella scheda «1. Scadenze» in rosso ci sono quelle già scadute, in giallo quelle vicine.", None),
        ("Mettile sul telefono", "Nella scheda «2. Esporta» scarica il file .ics e aprilo con il calendario del telefono.", None),
        ("Attiva l'email del mattino", "Nella scheda «3. Riepilogo email» trovi come farti mandare ogni mattina il riepilogo su email o Slack.", None),
    ], "Il Calendario legge i dati degli altri strumenti (sessione o ultimo salvataggio): se manca qualcosa, salva prima quello strumento."),
    "dd": ("La situazione dell'azienda in un colpo d'occhio, con i semafori e le cose da fare.", [
        ("Scegli le fonti", "Apri «🔌 Fonti dei dati» e per ogni strumento scegli i dati da usare: quelli su cui stai lavorando o un salvataggio.", None),
        ("Leggi i semafori", "Verde = tutto bene, giallo = attenzione, rosso = intervenire. In alto trovi «Cosa fare».", None),
        ("Cambia le soglie", "Se vuoi semafori più o meno severi, modifica le «Soglie dei semafori».", None),
        ("Scarica il rapporto", "Premi «📄 Genera il rapporto PDF» per la direzione.", "dossier"),
    ], "Se uno strumento mostra «non usato», il Cruscotto non sa niente di quell'area: salva i suoi dati e riseleziona la fonte."),
}


def _fatto(sigla, controllo):
    """True/False se il passo e' verificabile, None se non lo e'."""
    if not controllo:
        return None
    tipo, _, arg = controllo.partition(":")
    try:
        if tipo == "demo":
            return arg in ss and not ss.get(arg)
        if tipo == "dati":
            flag = {"credit": "dati_demo"}.get(sigla, f"{sigla}_demo")
            return arg in ss and len(ss[arg]) > 0 and not ss.get(flag)
        if tipo == "salvato":
            return bool(ss.get(f"_base_{sigla}"))
        if tipo == "dossier":
            return bool(ss.get(f"rep_{sigla}"))
    except Exception:
        return None
    return None


def stato(sigla):
    """[(titolo, testo, fatto)] per lo strumento."""
    _, passi, _ = PASSI[sigla]
    return [(t, x, _fatto(sigla, c)) for t, x, c in passi]


def mostra(sigla):
    """Riquadro «Come si usa» da mettere subito sotto il titolo dello strumento."""
    try:
        import video
        video.pulsante(sigla, key=f"vid_{sigla}")
    except Exception:
        pass
    if sigla not in PASSI:
        return
    serve, _, attenzione = PASSI[sigla]
    righe = stato(sigla)
    verificabili = [r for r in righe if r[2] is not None]
    fatti = sum(1 for r in verificabili if r[2])
    demo = bool(ss.get(f"{sigla}_demo") or (sigla == "credit" and ss.get("dati_demo")))
    titolo = "🧭 Come si usa, passo passo" + (f"  ·  {fatti} di {len(verificabili)} fatti" if verificabili else "")
    primo = next((i for i, r in enumerate(righe) if r[2] is False), None)
    with st.expander(titolo, expanded=demo and fatti == 0):
        st.caption(f"A cosa serve: {serve}")
        html = []
        for i, (t, x, f) in enumerate(righe, start=1):
            cls = "ok" if f else ("next" if (i - 1) == primo else "")
            marca = "✓" if f else str(i)
            html.append(f"<div class='gd-step {cls}'><div class='gd-n'>{marca}</div><div><div class='gd-t'>{t}</div><div class='gd-x'>{x}</div></div></div>")
        st.markdown("<div class='gd'>" + "".join(html) + "</div>", unsafe_allow_html=True)
        if attenzione:
            st.info("**Attenzione.** " + attenzione)
