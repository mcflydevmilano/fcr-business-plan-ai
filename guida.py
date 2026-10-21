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
        ("Confronta i preventivi", "Nella scheda «3. Confronto preventivi» vedi l'offerta più bassa tra i fornitori in regola.", None),
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
        ("Inserisci le risorse", "Nella scheda «1. Risorse e Assegnazioni» scrivi persone o squadre con costo orario e ore disponibili al mese.", "dati:og_ris"),
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
    "ru": ("Avere telefono, email e referente di tutti a portata di mano, e dare a ogni cantiere un codice unico.", [
        ("Togli l'esempio", "Premi «Svuota l'esempio e parti da zero».", "demo:ru_demo"),
        ("Inserisci i contatti", "Nella scheda «1. Contatti e cantieri» scrivi o importa da Excel fornitori, clienti ed enti, con telefono ed email.", "dati:ru_cont"),
        ("Inserisci i cantieri", "Più sotto scrivi i cantieri. Lascia vuoto il «Codice»: premi «🔢 Assegna i codici mancanti» e ognuno riceve il suo (CAN-anno-numero).", "dati:ru_can"),
        ("Chiama o scrivi", "Nella scheda «2. Scheda contatto» scegli un nome: trovi i pulsanti Chiama, Scrivi e WhatsApp e tutto ciò che lo riguarda (documenti, fatture, cantieri).", None),
        ("Usa lo stesso codice ovunque", "Scrivi il codice cantiere nelle altre tabelle e in monday: così ritrovi tutto di un lavoro. Nella colonna «Codice in altro sistema» metti quello di monday.", None),
        ("Salva", "Apri «💾 Salva e riapri la rubrica» in alto e premi Salva.", "salvato"),
    ], "I collegamenti con fatture e documenti funzionano per nome: scrivi il fornitore sempre allo stesso modo in tutti gli strumenti."),
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
