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
