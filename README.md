# FCR General Contractor — AI Business Plan & Rating Platform

Applicazione Streamlit per l'analisi del merito creditizio, la pianificazione pluriennale e la
generazione di report. Sviluppata da Aetheris Labs.

> Il rating prodotto è una **simulazione indicativa** basata su un modello interno: non è un
> rating regolamentare Basilea 3/4 né un parere di una banca. I dati vanno sempre verificati.

## Come usarlo

1. **Copia i file.** Metti questi file nella stessa cartella, insieme al due loghi
   `aetheris_labs_logo.jpg` e `fcr_logo.png`:
   `app.py`, `core.py`, `charts.py`, `exports.py`, `pdf_report.py`, `theme.py`, `auth.py`, `admin_ui.py`, `make_hash.py`, `bp.py`, `bp_ui.py`, `bp_report.py`, `cf.py`, `cf_ui.py`, `cf_report.py`, `pv.py`, `pv_ui.py`, `pv_report.py`, `sc.py`, `sc_ui.py`, `sc_report.py`, `sl.py`, `sl_ui.py`, `sl_report.py`, `scad.py`, `rep_gen.py`, `ops_report.py`, `ga.py`, `ga_ui.py`, `fo.py`, `fo_ui.py`, `sx.py`, `sx_ui.py`, `mz.py`, `mz_ui.py`, `og.py`, `og_ui.py`, `calendario.py`, `ca_ui.py`, `riepilogo.py`, `fatture.py`, `rp.py`, `rp_ui.py`, `hub.py`, `ora_meteo.py`, `dd.py`, `dd_ui.py`, `dd_report.py`, `report_util.py`, `ui_util.py`, `xbrl.py`, `storage.py`, `ai.py`,
   `requirements.txt`.
   - Il vecchio `app.py` va **sostituito** con quello nuovo.
   - Il vecchio `requirements.txt` va sostituito con quello nuovo (usa `google-genai`, non più
     `google-generativeai`).
   - I file `test_*.py` sono **facoltativi** (servono solo per i test automatici).

2. **Installa le dipendenze.**
   ```
   pip install -r requirements.txt
   ```

3. **Configura i secrets.** Crea il file `.streamlit/secrets.toml` (in locale) oppure inserisci gli
   stessi valori nelle impostazioni "Secrets" dell'hosting (es. Streamlit Cloud):
   ```toml
   APP_PASSWORD = "scegli-una-password-lunga"   # obbligatoria: senza, l'app non parte
   GEMINI_API_KEY = "la-tua-chiave"             # necessaria per le funzioni AI
   GEMINI_MODEL = "gemini-3.8-flash"            # opzionale
   FCR_DB_PATH = "/percorso/persistente/fcr.db" # opzionale, dove salvare le pratiche
   ```
   Senza `GEMINI_API_KEY` ogni utente può inserire la propria chiave nella barra laterale.
   Senza alcuna chiave funzionano comunque calcoli, grafici, Excel e report senza relazione AI.

4. **Avvia l'app.**
   ```
   streamlit run app.py
   ```

## Flusso di lavoro

1. **Dati:** carica il bilancio XBRL depositato al Registro Imprese (`.xbrl`, `.xml` o `.zip`: letto direttamente, senza AI e senza inviare dati a Google) oppure un PDF o Excel (con AI) oppure inserisci i dati a mano. Dopo l'estrazione
   con AI controlla ogni valore con la fonte indicata e premi "Conferma e applica".
2. **Commesse:** inserisci il portafoglio lavori (opzionale).
3. **Simulatore:** muovi le leve, guarda il punteggio e cosa serve per migliorare la fascia.
4. **Piano e Grafici:** imposta le ipotesi del piano triennale e i covenant.
5. **Scenari:** salva e confronta più combinazioni.
6. **Report:** scarica PDF e Word, oppure l'Excel con formule vive.

Usa la barra laterale per salvare e ricaricare le **pratiche**.

## Test (facoltativi)

```
pytest
```
I test di Excel richiedono LibreOffice e vengono saltati se non è installato.

## Cose da sapere

- **Salvataggi:** il database è un file SQLite locale. Su hosting con disco temporaneo
  (es. Streamlit Cloud) i salvataggi si perdono al riavvio: imposta `FCR_DB_PATH` su un volume
  persistente.
- **Privacy:** l'app mostra un'informativa e richiede di accettarla (sidebar) prima di attivare l'AI; è ripresa anche in PDF, Word ed Excel. I bilanci caricati vengono inviati a Gemini. Verifica il piano utilizzato e la
  conformità GDPR prima di caricare documenti di clienti.
- **Soglie di scoring:** sono ipotesi di lavoro, modificabili dal Simulatore. Vanno calibrate
  sulla propria politica di rischio.
- **Accesso:** la password è unica e condivisa, con un limite di 5 tentativi per sessione.
  Per un uso con dati reali è consigliabile un'autenticazione più robusta.


## Hub, Business Plan Studio e tema chiaro (novita')

- All'accesso compare un **Hub** con due strumenti: *Credit Risk & Rating* e *Business Plan Studio (3-5 anni)*.
- Il **Cash Flow di cantiere** (`cf.py`, `cf_ui.py`, `cf_report.py`) simula incassi, pagamenti, cassa, scoperto e fido di un portafoglio di cantieri, con stress test, anticipo minimo e dossier PDF/Excel (IVA esclusa).
- **Computo e Preventivo** (`pv.py`, `pv_ui.py`, `pv_report.py`) trasforma un computo in preventivo (spese generali, utile, sconto, sicurezza, IVA), calcola sconto massimo e sensibilità ai costi, produce il PDF per il cliente (senza costi) e l'Excel interno, e può inviare il lavoro al Cash Flow.
- Lo **Scadenzario** (`sc.py`, `sc_ui.py`, `sc_report.py`) gestisce fatture attive e passive (IVA inclusa): scaduto per fasce, clienti da sollecitare con bozze, previsione di cassa settimana per settimana e stress sul ritardo dei clienti, con dossier PDF/Excel.
- **SAL e contabilità lavori** (`sl.py`, `sl_ui.py`, `sl_report.py`): commesse, SAL con anticipo, ritenuta di garanzia e IVA, costi, margine a finire con il metodo del valore maturato (EV, CPI, EAC), invio di SAL e costi allo Scadenzario e delle commesse al Cash Flow, dossier PDF/Excel con formule. Il Cruscotto ne legge il margine a finire.
- **Gare e offerte** (`ga.py`, `ga_ui.py`): elenco gare, ribasso massimo per il margine obiettivo, valore atteso, pipeline ponderata, check-list documenti con scadenze; le gare vinte passano a SAL.
- **Fornitori e subappaltatori** (`fo.py`, `fo_ui.py`): documenti in scadenza (DURC, assicurazioni, SOA), contratti e ordini aperti, confronto dei preventivi con l'offerta più bassa tra i fornitori in regola.
- **Sicurezza e documenti di cantiere** (`sx.py`, `sx_ui.py`): scadenze di formazioni e idoneità, documenti obbligatori per cantiere. Promemoria: non sostituisce RSPP/CSE.
- **Parco mezzi e attrezzature** (`mz.py`, `mz_ui.py`): tariffa oraria, utilizzo, costi fissi non assorbiti, costi per commessa (inviabili a SAL), scadenze.
- **Organico e carico di lavoro** (`og.py`, `og_ui.py`): capacità e assegnazioni mese per mese, sovraccarichi, ore inattive, costo del personale per commessa.
- I moduli operativi condividono `scad.py` (logica delle scadenze) e `rep_gen.py`/`ops_report.py` (dossier PDF ed Excel). Il Cruscotto di direzione legge anche questi moduli.
- **Storico dei salvataggi**: ogni salvataggio conserva le ultime 20 versioni precedenti, ripristinabili dal riquadro «Salva e riapri».
- **Ruolo «lettore»**: consulta e scarica i dossier ma non modifica i dati né salva (si assegna dal pannello Utenti).
- **Importazione con mappatura**: caricando un Excel/CSV l'app propone la corrispondenza delle colonne (utile per gli export del gestionale), da confermare prima dell'import.
- Il **Cruscotto di direzione** (`dd.py`, `dd_ui.py`, `dd_report.py`) legge i dati degli altri moduli (di sessione o salvati) e li traduce in semafori su cassa, scoperto, crediti, margine, rating e DSCR, con le azioni da fare e un rapporto PDF. Le soglie sono ipotesi modificabili.
- Business Plan, Cash Flow, Preventivo, Scadenzario e SAL si salvano con nome nel database (riquadro «Salva e riapri»); con `DATABASE_URL` configurato i dati restano dopo i riavvii.
- Il Business Plan Studio (`bp.py`, `bp_ui.py`, `bp_report.py`) offre wizard AI per le ipotesi, conto economico, mutuo (francese/italiano), cash flow, PFN, DSCR e dossier PDF.
- Il tema e' chiaro (light) in stile FinTech: CSS in `theme.py` e configurazione nativa in **`.streamlit/config.toml`** (cartella con il punto iniziale: va caricata nel repository).
- Nel repository devono esserci anche `aetheris_labs_logo.jpg` e il logo FCR (`fcr_logo.png`).
- Dopo l'aggiornamento riavvia l'app (Reboot su Streamlit Cloud).


## Accesso per utente (novita')

Ogni persona ha il proprio nome utente e la propria password; gli amministratori gestiscono gli utenti dal pulsante **Utenti**
(creazione, revoca, reimpostazione password, ruolo) e consultano il **registro attivita'** (accessi, salvataggi, import, report).

**Come creare il primo amministratore (consigliato, persiste ai riavvii).** Genera l'hash della password sul tuo computer:

    python make_hash.py

poi incolla nei *Secrets* di Streamlit (Manage app → Settings → Secrets):

    [users.mario]
    hash = "pbkdf2_sha256$240000$...."
    ruolo = "admin"

    [users.anna]
    hash = "pbkdf2_sha256$240000$...."
    ruolo = "utente"

- Gli utenti dei secrets si revocano togliendo la riga. Gli utenti creati dal pannello stanno nel database: su hosting con disco
  temporaneo si perdono al riavvio (imposta `FCR_DB_PATH` su un volume persistente).
- `APP_PASSWORD` resta valida solo per compatibilita' (accesso come `admin`): una volta creati gli utenti, rimuovila.
- Dopo 5 tentativi falliti l'utente e' bloccato 15 minuti. Le password nuove: almeno 10 caratteri, con lettere e numeri.

## Soglie di rating per settore e validazione

Nel Credit Risk, in *Soglie di scoring*, puoi scegliere un profilo (edilizia, ESCo, immobiliare, industria, servizi), importare
benchmark reali da file JSON (formato nel pulsante di aiuto) e indicare chi ha validato le soglie: compare nei report.
I profili inclusi sono **ipotesi di lavoro, non benchmark ufficiali**.

## Business Plan: fisco, scenari e sensibilita'

Modello fiscale *dettagliato* (IRES + IRAP, riporto perdite fino all'80% del reddito) o *semplice*; scheda **Scenari e Sensibilita'**
con scenari pessimistico/base/ottimistico modificabili, grafico tornado e mappa ricavi x costi variabili; tutto incluso nel dossier PDF.

## Calendario scadenze, riepilogo email, salvataggi simultanei

- **Calendario scadenze** (`calendario.py`, `ca_ui.py`, Hub, gruppo «Cantiere e risorse»): vista unica di incassi, pagamenti, gare, documenti, formazione, mezzi; export `.ics` ed Excel.
- **Riepilogo email mattutino** (`riepilogo.py`, `.github/workflows/riepilogo.yml`): GitHub Actions, feriali alle 06:00 UTC. Secrets richiesti: `DATABASE_URL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_TO`. Prova locale: `python riepilogo.py --dry-run`. Legge l'ultima versione salvata.
- **Protezione salvataggi simultanei**: se la pratica è cambiata dopo l'apertura, compare l'avviso con «Sovrascrivi comunque»; la versione sovrascritta resta nello storico (ultime 20).
- **Telefono**: pulsante Hub in alto visibile solo sotto i 700 px.

## Fatture XML e Rapportini di cantiere

- **Import fatture elettroniche** (`fatture.py`, nello Scadenzario): file FatturaPA `.xml` o `.xml.p7m`. Le emesse diventano incassi, le ricevute pagamenti (in base alla tua partita IVA); una riga per ogni rata. Le note di credito non vengono importate; i doppioni sono saltati; lo split payment toglie l'IVA.
- **Rapportini di cantiere** (`rp.py`, `rp_ui.py`, `ops_report.py`): moduli rapidi da telefono per rapportino giornaliero e segnalazioni, salvati nel registro condiviso «Rapportini» con fusione automatica tra telefoni diversi. Alimentano Cruscotto, Calendario e riepilogo email.
- L'Hub è organizzato in gruppi (`hub.py`): per spostare o aggiungere uno strumento basta modificare `GRUPPI`.

## Cronoprogramma (Gantt)

`gt.py`, `gt_ui.py`: fasi dei cantieri con inizio, fine e avanzamento; diagramma di Gantt con la linea di oggi, ritardi e fine stimata. Si può partire dalle commesse del SAL o dalle assegnazioni di Organico. Alimenta Cruscotto e Calendario (categoria «Fine fase»).

## Permessi per profilo (chi vede cosa)

`permessi.py`, scheda **Utenti → 🔒 Permessi**: ogni persona ha un *profilo* (presidente, direzione, amministrazione, commerciale, cantiere, legale…) e ogni profilo apre solo gli strumenti spuntati. L'amministratore vede sempre tutto. Il **Cruscotto di direzione** è riservato al profilo *presidente* (e all'amministratore). Chi non ha un profilo assegnato riceve «direzione» (tutto tranne il Cruscotto). Il *ruolo* (admin / utente / lettore) decide invece chi può modificare i dati: sono due cose separate. Gli strumenti chiusi spariscono dall'Hub, dalle scorciatoie e dal Calendario, e un accesso diretto viene rifiutato e scritto nel registro («accesso_negato»). La configurazione è salvata nel database.

## Rubrica e cantieri, Studio legale, Riconciliazione bancaria, Ordini e approvazioni

- **Rubrica e cantieri** (`ru.py`, `ru_ui.py`): contatti con chiama / scrivi / WhatsApp, documenti e fatture collegati (per nome), cantieri con codice unico `CAN-anno-numero` e colonna per il codice di monday.
- **Studio legale** (`lg.py`, `lg_ui.py`): fascicolo del cliente con fatture scadute e solleciti già fatti, invio allo studio per email (con PDF allegato) e/o Slack, registro di riserve/varianti/contestazioni con i termini fissati dallo studio, contratti e polizze in scadenza, penali di ritardo calcolate dal Cronoprogramma. Promemoria organizzativo: non è consulenza legale. Segreti: `STUDIO_LEGALE_EMAIL` (con `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`) e/o `STUDIO_LEGALE_SLACK_WEBHOOK_URL`.
- **Riconciliazione bancaria** (`bk.py`, `bk_ui.py`): abbina i movimenti dell'estratto conto alle fatture dello Scadenzario (importo, numero fattura, nome nella causale, data), propone e fa confermare, poi aggiorna lo Scadenzario.
- **Ordini e approvazioni** (`oa.py`, `oa_ui.py`): soglie d'importo per chi approva, chi chiede non approva, fornitori con documenti scaduti bloccati, decisioni tracciate con nome e ora, nuova approvazione se l'importo cambia.

## Foto, firma e app sul telefono

Nel Rapportino e nelle Segnalazioni si possono allegare foto (ridotte a 1280 px) e, nel rapportino, la firma disegnata con il dito (`firma.py`). Gli allegati stanno in un salvataggio a parte, legati all'Id, e il registro attività scrive solo «chi e quando». `pwa.py` rende la suite installabile (Android: menu ⋮ → Installa app; iPhone: Condividi → Aggiungi alla schermata Home).

## Persone e ruoli

`pe.py`, `pe_ui.py`: elenco del personale (ruolo, reparto, recapiti, cantiere, in servizio) e accessi all'app. Ogni **ruolo aziendale** propone un profilo di accesso (es. Capocantiere → «cantiere», Responsabile amministrativo → «amministrazione», Presidente → «presidente»). L'amministratore, dalla scheda «Accessi», crea l'account di una persona direttamente dall'elenco (password temporanea mostrata una sola volta), le assegna il profilo, la collega a un account esistente o ne revoca l'accesso. Avvisa se qualcuno non più in servizio ha ancora l'accesso o se esistono account senza persona. I nomi del personale entrano anche nel «Controllo nomi» della Rubrica (responsabili, richiedenti, compilatori). Strumento con dati personali: per impostazione predefinita lo vedono presidente, direzione e amministrazione.

## Prezziario (3.2.0)
Strumento «Prezziario» (gruppo *Offerte e commesse*): carica un listino Excel (per esempio quello della Camera di Commercio Milano Monza Brianza Lodi, un quadrimestre alla volta) e lo trasforma in prezzi consultabili.

- **Carica**: l'app riconosce il quadrimestre dal nome del file, salta intestazioni e avvertenze, ripulisce i caratteri HTML (`&apos;`) e segnala cosa manca (descrizioni accorciate, incidenze a zero, voci senza unità). I codici ripetuti restano come varianti (`codice`, `codice#2`…).
- **Cerca**: per parola, inizio del codice, capitolo, gruppo e unità. Clic su una riga per il dettaglio e le varianti; risultati scaricabili in Excel.
- **Computo e Preventivo**: «📚 Aggiungi voci dal prezziario». Il prezzo diventa costo diretto togliendo spese generali e utile (o si usa com'è); se il file ha le incidenze, il costo si divide tra manodopera, noli e materiali.
- **Ordini e approvazioni**: due colonne facoltative, «Voce» (codice) e «Quantità». Se il prezzo unitario supera il prezziario oltre la soglia scelta (predefinita 10%) compare un avviso per chi approva; non blocca.
- **Scadenza**: il listino vale per il suo quadrimestre. Finito il periodo, nell'Hub e nel Cruscotto compare «prezzi da aggiornare» (rosso dopo oltre 120 giorni).
- **Confronto**: con due quadrimestri caricati, la scheda 3 mostra quali prezzi sono saliti o scesi, per capitolo e per voce.
- Permessi: lo strumento è abilitato ai profili amministrazione, commerciale, cantiere e direzione; i profili già salvati lo ricevono da soli secondo queste regole.

## Novità 3.3.0
- **Ricerca nella home**: casella unica per strumenti, dati salvati (cantieri, fornitori, fatture, persone…) e voci del prezziario.
- **Resta collegato dopo F5**: il login viene ricordato 12 ore (cookie firmato, senza password dentro). Si cancella con «Esci», cambiando la password o disattivando l'utente. Opzionale nei Secrets: `SESSIONE_ORE` (1-168) e `SESSION_SECRET` (testo lungo casuale; senza, la chiave deriva dagli altri segreti).
- **Favicon** con il logo FCR su fondo bianco; **tasti su telefono** con le scritte a capo invece che tagliate.

## Registro commerciale (3.4.0)
Strumento nuovo nel gruppo «Offerte e commesse». Importa il tuo Excel (fogli Registro ed Eliminati), mostra le pratiche per stato (S0-S9) e per commerciale, il valore in corso, la pipeline pesata (valore × % di successo, ricalcolata dall'app), i prossimi interventi scaduti o in arrivo e permette ricerca e filtri. Si salva e si riapre come gli altri strumenti; l'Excel si può riscaricare. Lo ricevono i profili presidente, direzione e commerciale. Le pratiche eliminate restano nel registro con «Archivio = Eliminata».
Nei Secrets si può mettere `ESEMPI_ATTIVI = "1"` solo per riavere i dati di esempio (di norma gli strumenti partono vuoti).

## Offerta e finanziamenti (3.5.0)

Nuovo strumento (sigla `of`, gruppo «Offerte e commesse») che segue la catena commerciale: computo → parcelle → QTE → offerta, più la continuità finanziaria.

- **Computo A/B**: import del file del collega (foglio «Table 1», sconti dal «Foglio1»); voci comuni o per ipotesi; imponibile per ipotesi.
- **Parcelle D.Lgs. 36/2023**: V·P·G·ΣQ con le tabelle Z1/Z2 (`parcelle_z.json`, ricavato dal foglio Rev7; le prestazioni a scaglioni progressivi non sono incluse: per quelle usare l'importo a mano). BIM +10%, spese e oneri accessori, sconto; in alternativa parcella a mano.
- **QTE**: lavori + IVA, parcella e Responsabile Lavori con cassa 4% e IVA 22% (come il foglio «Quadro economico»).
- **Finanziamento**: rata alla francese a più durate, TAN, detrazione (%), anni di recupero e risparmio energetico modificabili per pratica; riparto per millesimi (tabella da Excel); impatto reale = rata − recupero fiscale − risparmio.
- **Mercato**: annunci «così com'è» / «efficientato» → €/m² e differenza.
- **Continuità finanziaria**: richieste al Condominio e ai condomini (AGOS, fino al 50% dei lavori privati) con stato, esito, documenti e copertura dell'appalto.
- **Offerta**: PowerPoint e PDF generati dallo stesso schema (`of_report.py`), più Excel dei calcoli. Il PDF usa i font in `fonts/`; il PPTX richiede `python-pptx` (aggiunto a `requirements.txt`).

## Accesso, rotella di caricamento e velocità (3.6.0)
- **Nuovo accesso**: sfondo blu «tavola di progetto», emblema FCR, scheda bianca con il logo Aetheris Labs; funziona anche da telefono. Il browser può salvare nome utente e password.
- **Rotella di caricamento**: l'emblema Aetheris gira al centro dello schermo quando la suite sta lavorando (compare solo se l'attesa supera circa un terzo di secondo, non blocca i clic; sostituisce l'omino «Running» di Streamlit). File `aetheris_icona.png`.
- **Velocità**: le connessioni al database (Neon) restano aperte e si riusano invece di riaprirne una a ogni lettura (il Cruscotto ne apriva fino a 53 per ogni clic, ora 0-1); le liste dei salvataggi, i permessi e l'indice dei prezziari si ricordano per pochi secondi e si aggiornano a ogni salvataggio; i grafici con gli stessi dati non si ridisegnano; google-genai si carica solo quando si usa l'IA; i caratteri di Google non rallentano più lo stile.
- L'orologio della barra laterale usa `st.iframe` (il vecchio componente è deprecato).

## Cruscotto cliccabile (3.6.1)
- Ogni casella del Cruscotto ha sotto un pulsante: «Vai al problema →» (rosse e arancioni), «Compila i dati →» (senza dati), «Apri →» (verdi). Apre lo strumento da cui arriva il dato, con il salvataggio che il Cruscotto sta usando già caricato, e in cima compaiono «← Torna al Cruscotto» e la riga con il semaforo da cui si arriva.
- Corretto un errore che compariva tornando in uno strumento (per esempio il Cruscotto) dopo averne visitato un altro: i pulsanti non vengono più ripristinati come se fossero valori.
- Cambiando strumento la pagina riparte dall'alto.

## Chat interna (3.7.0)
Strumento «Chat interna» (gruppo Comunicazione): canali pubblici, gruppi privati e chat dirette, contatore dei non letti, foto e PDF, collegamento a uno strumento, avvisi sul telefono.
- **Riservatezza**: gruppi privati e chat dirette li leggono solo i membri, nessun amministratore (nemmeno esportando). Con il segreto `CHAT_KEY` testo e allegati di queste chat sono cifrati nel database. **Conserva la chiave: se la perdi, quei messaggi non si leggono più.**
- **Gestione**: gli amministratori e le persone da loro scelte creano/archiviano/esportano i canali pubblici; ogni operazione lascia traccia nel registro attività (mai il testo).
- **Avvisi**: Telegram (`TELEGRAM_BOT_TOKEN`, bot creato con @BotFather) e/o ntfy (`NTFY_URL`, anche server proprio). `APP_URL` = indirizzo della suite, usato nei link. L'avviso non contiene mai il testo.
- **Allegati**: foto ridotte a 1600 px (JPEG), originale max 12 MB; PDF max 8 MB; salvati nel database (nessun file su disco: si trasferisce con il database sul vostro hosting).
- **Conservazione**: pulsante «Cancella i messaggi più vecchi di N mesi» in Gestione (proposta 24 mesi).
- Nuovi secrets facoltativi: `CHAT_KEY`, `TELEGRAM_BOT_TOKEN`, `NTFY_URL`, `APP_URL`. Nuova dipendenza: `cryptography`.

### Avvisi del Cruscotto (3.7.1)
Nel Cruscotto, riquadro «🔔 Avvisi per email e chat interna»: per ogni area (Cassa, Margine, Crediti, …) l'amministratore indica da quale gravità avvisare (rosso, o giallo e rosso), il canale della chat, le persone (messaggio diretto dal «Cruscotto» + avviso sul telefono) e gli indirizzi email. Lo stesso problema si manda al massimo una volta al giorno. L'invio automatico parte all'apertura del Cruscotto solo se tutti i dati vengono da salvataggi veri (mai da prove o dati dimostrativi); c'è anche «Invia ora». Email: Secrets `SMTP_HOST`, `SMTP_PORT` (587 o 465), `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM` (facoltativo).
