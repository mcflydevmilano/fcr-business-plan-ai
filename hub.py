"""Hub: schede degli strumenti raggruppate per area, in sequenza logica.
Aggiungere o spostare uno strumento = modificare GRUPPI. Il numero "Strumento N" segue l'ordine."""
import streamlit as st

import theme

CARDS = {'credit': {'icona': '📊',
            'titolo': 'Credit Risk & Rating Basilea 3/4',
            'desc': 'Analisi di bilancio, scoring indicativo, simulatore What-If e dossier per il Comitato '
                    'Fidi.',
            'voci': ['Import bilancio XBRL, PDF o Excel (con AI)',
                     'Scoring PFN/EBITDA, PFN/PN, equity ratio e DSCR',
                     'Simulatore di leve, stress test e covenant',
                     'Report PDF, Word ed Excel con formule vive'],
            'tag': ['Rating', 'Stress test', 'PDF + Excel + Word'],
            'bottone': 'Credit Risk & Rating'},
 'bp': {'icona': '🚀',
        'titolo': 'Business Plan Studio (3-5 anni)',
        'desc': 'Pianificazione industriale e finanziaria di nuove iniziative: conto economico, mutuo e cash '
                'flow.',
        'voci': ['Wizard AI che propone le assunzioni dal testo del progetto',
                 'Conto economico previsionale fino al risultato netto',
                 'Piano di ammortamento del mutuo, cash flow e DSCR',
                 'Dossier PDF del business plan'],
        'tag': ['Wizard AI', 'Mutuo', 'Cash flow'],
        'bottone': 'Business Plan Studio'},
 'cf': {'icona': '🏗️',
        'titolo': 'Cash Flow di cantiere',
        'desc': 'Liquidità del portafoglio cantieri: quando incassi, quando paghi, quanto fido ti serve.',
        'voci': ['Portafoglio di decine di cantieri con anticipo, SAL e saldo',
                 'Cassa mese per mese, scoperto, interessi e fido',
                 'Stress test: incassi in ritardo, costi maggiori, avvii slittati',
                 'Dossier PDF ed Excel con formule vive'],
        'tag': ['Liquidità', 'Stress test', 'PDF + Excel'],
        'bottone': 'Cash Flow di cantiere'},
 'pv': {'icona': '🧮',
        'titolo': 'Computo e Preventivo',
        'desc': 'Dal computo metrico al prezzo al cliente, con il margine sempre sotto controllo.',
        'voci': ['Voci con costi di materiali, manodopera e noli',
                 'Spese generali, utile, sconto, sicurezza e IVA',
                 'Sconto massimo concedibile e rischio aumento costi',
                 'Preventivo PDF per il cliente e invio al Cash Flow'],
        'tag': ['Computo', 'Margine', 'PDF cliente'],
        'bottone': 'Computo e Preventivo'},
 'sc': {'icona': '📅',
        'titolo': 'Scadenzario incassi e pagamenti',
        'desc': 'Fatture attive e passive: quanto incassi e paghi, settimana per settimana.',
        'voci': ['Risposta a «questa settimana ho cassa?»',
                 'Scaduto per fasce di ritardo e clienti da sollecitare',
                 'Bozze di sollecito pronte da rivedere',
                 'Dossier PDF ed Excel con formule vive'],
        'tag': ['Settimanale', 'Solleciti', 'PDF + Excel'],
        'bottone': 'Scadenzario'},
 'dd': {'icona': '🚦',
        'titolo': 'Cruscotto di direzione',
        'desc': "Lo stato dell'azienda in un colpo d'occhio, con i semafori e le azioni da fare.",
        'voci': ['Margine, cassa, scoperto, crediti e rating',
                 'Legge i dati dagli altri moduli, anche salvati',
                 'Soglie dei semafori modificabili',
                 'Rapporto PDF per la direzione'],
        'tag': ['Semafori', 'Azioni', 'PDF'],
        'bottone': 'Cruscotto di direzione'},
 'sl': {'icona': '📐',
        'titolo': 'SAL e contabilità lavori',
        'desc': 'Le commesse in corso: stati di avanzamento, costi e margine a finire.',
        'voci': ['SAL con anticipo, ritenute e IVA',
                 'Margine a finire con il metodo del valore maturato',
                 'Invio dei SAL e dei costi allo Scadenzario',
                 'Dossier PDF ed Excel con formule vive'],
        'tag': ['SAL', 'Margine a finire', 'PDF + Excel'],
        'bottone': 'SAL e contabilità'},
 'ga': {'icona': '🏛️',
        'titolo': 'Gare e offerte',
        'desc': 'Quali gare fare e con che ribasso, e cosa manca prima della scadenza.',
        'voci': ['Ribasso massimo per il margine obiettivo',
                 'Valore atteso e pipeline ponderata',
                 'Check-list dei documenti con scadenze',
                 'Le gare vinte passano a SAL'],
        'tag': ['Ribasso', 'Pipeline', 'PDF + Excel'],
        'bottone': 'Gare e offerte'},
 'fo': {'icona': '🤝',
        'titolo': 'Fornitori e subappaltatori',
        'desc': 'Documenti in scadenza, contratti e confronto preventivi.',
        'voci': ['DURC, assicurazioni e SOA con avvisi',
                 'Ordini aperti, fatturato e da pagare',
                 'Offerta più bassa tra i fornitori in regola',
                 'Dossier PDF ed Excel con formule'],
        'tag': ['Scadenze', 'Contratti', 'Confronto'],
        'bottone': 'Fornitori'},
 'sx': {'icona': '🦺',
        'titolo': 'Sicurezza e documenti di cantiere',
        'desc': 'Formazioni, idoneità e documenti obbligatori per cantiere.',
        'voci': ['Scadenze di corsi e visite mediche',
                 'Check-list documenti per cantiere',
                 'Cantieri a rischio in evidenza',
                 'Dossier PDF ed Excel'],
        'tag': ['Formazione', 'Cantieri', 'PDF + Excel'],
        'bottone': 'Sicurezza'},
 'mz': {'icona': '🚜',
        'titolo': 'Parco mezzi e attrezzature',
        'desc': 'Tariffa oraria dei mezzi, utilizzo e scadenze.',
        'voci': ['Costo orario e costi fissi non assorbiti',
                 'Costi dei mezzi per commessa',
                 'Revisioni e assicurazioni in scadenza',
                 'Invio dei costi a SAL'],
        'tag': ['Tariffe', 'Utilizzo', 'PDF + Excel'],
        'bottone': 'Parco mezzi'},
 'ru': {'icona': '📇',
        'titolo': 'Rubrica e cantieri',
        'desc': 'Tutti i contatti in un posto solo e ogni cantiere con il suo codice unico.',
        'voci': ['Telefono, email e referente di fornitori, clienti ed enti',
                 'Chiama, scrivi o manda un WhatsApp con un tocco',
                 'Per ogni contatto: documenti, fatture e cantieri collegati',
                 'Codice cantiere unico, pronto per monday e altri sistemi'],
        'tag': ['Rubrica', 'Codici cantiere', 'PDF + Excel'],
        'bottone': 'Rubrica e cantieri'},
 'pe': {'icona': '👥',
        'titolo': 'Persone e ruoli',
        'desc': 'L\'elenco di chi lavora in azienda, con il suo ruolo, e a cosa può accedere nell\'app.',
        'voci': ['Elenco del personale con ruolo, reparto, recapiti e cantiere',
                 'Un ruolo aziendale propone il profilo di accesso giusto',
                 'Crea l\'account di una persona dall\'elenco, con il suo profilo',
                 'Revoca l\'accesso di chi non è più in servizio'],
        'tag': ['Personale', 'Ruoli', 'Accessi'],
        'bottone': 'Persone e ruoli'},
 'lg': {'icona': '⚖️',
        'titolo': 'Studio legale',
        'desc': 'Passa un cliente allo studio con il fascicolo completo e tieni sotto controllo riserve, contratti e penali.',
        'voci': ['Fascicolo del cliente: fatture scadute, solleciti già fatti, importi',
                 'Invio allo studio per email o Slack con un clic',
                 'Registro di riserve, varianti e contestazioni con i termini',
                 'Penali di ritardo calcolate dal Cronoprogramma'],
        'tag': ['Fascicolo', 'Riserve', 'Penali'],
        'bottone': 'Studio legale'},
 'bk': {'icona': '🏦',
        'titolo': 'Riconciliazione bancaria',
        'desc': 'Abbina i movimenti del conto alle fatture e segna da solo cosa è pagato o incassato.',
        'voci': ['Importa l\'estratto conto in Excel o CSV',
                 'Abbinamenti con punteggio e motivo, da confermare',
                 'Aggiorna lo Scadenzario con un clic',
                 'Elenco dei movimenti senza fattura'],
        'tag': ['Banca', 'Abbinamenti', 'PDF + Excel'],
        'bottone': 'Riconciliazione bancaria'},
 'oa': {'icona': '🛒',
        'titolo': 'Ordini e approvazioni',
        'desc': 'Chi chiede, chi approva, fino a quanto: ogni ordine ha il suo via libera e resta tracciato.',
        'voci': ['Soglie d\'importo: capocantiere, direttore tecnico, presidente',
                 'Chi chiede un ordine non può approvarlo',
                 'Fornitore con documenti scaduti: approvazione bloccata',
                 'Storico di ogni decisione con nome e ora'],
        'tag': ['Approvazioni', 'Tracciabilità', 'PDF + Excel'],
        'bottone': 'Ordini e approvazioni'},
 'gt': {'icona': '📅',
        'titolo': 'Cronoprogramma dei cantieri (Gantt)',
        'desc': 'Quando parte e finisce ogni fase, a che punto è davvero e dove si accumula ritardo.',
        'voci': ['Diagramma di Gantt con la linea di oggi',
                 'Avanzamento reale contro previsto, per fase e cantiere',
                 'Fine stimata e giorni di ritardo',
                 'Parte dalle commesse del SAL e dalle squadre di Organico'],
        'tag': ['Gantt', 'Ritardi', 'PDF + Excel'],
        'bottone': 'Cronoprogramma'},
 'rp': {'icona': '📝',
        'titolo': 'Rapportini di cantiere',
        'desc': 'Il giornale del cantiere dal telefono: presenze, ore, lavorazioni e segnalazioni.',
        'voci': ['Moduli rapidi pensati per il capocantiere',
                 'Condiviso con l\'ufficio, anche se compilano in più persone',
                 'Segnalazioni con gravità, responsabile e scadenza',
                 'Avviso se un cantiere non manda il rapportino'],
        'tag': ['Telefono', 'Segnalazioni', 'PDF + Excel'],
        'bottone': 'Rapportini'},
 'og': {'icona': '👷',
        'titolo': 'Organico e carico di lavoro',
        'desc': 'Quanta gente serve nei prossimi mesi e quanto costano le ore ferme.',
        'voci': ['Capacità e assegnazioni mese per mese',
                 'Sovraccarichi e mesi scarichi',
                 'Costo del personale per commessa',
                 'Dossier PDF ed Excel'],
        'tag': ['Carico', 'Squadre', 'PDF + Excel'],
        'bottone': 'Organico'},
 'ca': {'icona': '🗓️',
        'titolo': 'Calendario scadenze',
        'desc': 'Tutte le scadenze in una lista: fatture, gare, documenti, formazioni e mezzi.',
        'voci': ['Scadute e prossime in ordine di data',
                 'Calendario per il telefono (file .ics)',
                 'Riepilogo email ogni mattina',
                 'Legge i dati dei moduli, anche salvati'],
        'tag': ['Scadenze', 'Telefono', 'Email'],
        'bottone': 'Calendario scadenze'}}

# (titolo sezione, sottotitolo, [sigle])  -  ogni gruppo ha un numero pari di schede, tranne l'ultimo (a tutta larghezza)
GRUPPI = [
    ("Parte finanziaria", "Dott. Claudio Arosio",
     ["credit", "bp", "cf", "sc", "bk"]),
    ("Offerte e commesse", "Dalla gara al preventivo, fino all'avanzamento lavori",
     ["ga", "pv", "sl", "gt"]),
    ("Cantiere e risorse", "Rapportini, sicurezza, mezzi e persone",
     ["rp", "sx", "mz", "og"]),
    ("Fornitori, acquisti e scadenze", "Contatti, ordini approvati, documenti dei fornitori e calendario unico",
     ["ru", "fo", "oa", "ca"]),
    ("Studio legale", "Riserve, contratti e passaggio dei crediti allo studio",
     ["lg"]),
    ("Direzione e persone", "La sintesi di tutta l'azienda e chi ci lavora",
     ["pe", "dd"]),
]


ICONE_GRUPPO = {"Parte finanziaria": "💰", "Offerte e commesse": "🏗️", "Cantiere e risorse": "👷",
                "Fornitori, acquisti e scadenze": "📦", "Studio legale": "⚖️", "Direzione e persone": "📊"}


def numero(sigla):
    ordine = [s for _, _, ss in GRUPPI for s in ss]
    return f"Strumento {ordine.index(sigla) + 1}"


def _scheda(sigla, vai_a):
    c = CARDS[sigla]
    with st.container(key=f"hubc_{sigla}"):      # il contenitore permette di allineare l'altezza delle schede in riga
        st.markdown(
            theme.hub_card(numero(sigla), c["icona"], c["titolo"], c["desc"], c["voci"], c["tag"],
                           "" if sigla == "credit" else sigla),
            unsafe_allow_html=True,
        )
        if st.button(f"Apri {c['bottone']}  →", key=f"hub_{sigla}", width="stretch"):
            vai_a(sigla)


NOTA = "Le simulazioni sono indicative e non costituiscono rating regolamentare, parere di credito o consulenza."


PERCORSI = [
    ("👷 Sono in cantiere", "Scrivi il rapportino e segnala i problemi, dal telefono.", [("rp", "✍️ Scrivi il rapportino")]),
    ("🗂️ Lavoro in ufficio", "Fatture, commesse, fornitori, gare e scadenze.", [("sc", "🧾 Fatture e cassa"), ("sl", "🏗️ Commesse e SAL"), ("ca", "📅 Scadenze")]),
    ("📊 Dirigo l'azienda", "La situazione in un colpo d'occhio.", [("dd", "📊 Apri il Cruscotto")]),
]


def _da_dove_comincio(vai_a, consentiti=None):
    with st.expander("🚀 Da dove comincio? Scegli chi sei", expanded=False):
        st.caption("Ogni strumento ha in alto il riquadro «🧭 Come si usa»: ti dice cosa fare, passo per passo. Gli esempi che vedi sono finti: li togli con «Svuota l'esempio».")
        percorsi = [(t, x, [(s, e) for s, e in b if consentiti is None or s in consentiti]) for t, x, b in PERCORSI]
        percorsi = [p for p in percorsi if p[2]]
        if not percorsi:
            st.caption("Apri uno strumento dall'elenco qui sotto.")
            return
        cols = st.columns(len(percorsi), gap="large")
        for col, (titolo, testo, bottoni) in zip(cols, percorsi):
            with col:
                st.markdown(f"**{titolo}**")
                st.caption(testo)
                for s, etichetta in bottoni:
                    if st.button(etichetta, key=f"start_{s}", use_container_width=True):
                        vai_a(s)


def _freschezza(righe):
    """Strumenti i cui dati non si salvano da troppo tempo: un semaforo su dati vecchi sembra credibile ma mente."""
    fermi = [r for r in righe if r["stato"] in ("warn", "bad")]
    if not righe:
        return
    ico = {"ok": "🟢", "warn": "🟡", "bad": "🔴", "nd": "⚪"}
    salvati = [r for r in righe if r["stato"] != "nd"]
    titolo = "🕒 Dati aggiornati? " + (f"{len(fermi)} strumenti fermi da troppo tempo" if fermi else ("nessun dato salvato ancora" if not salvati else "gli strumenti in uso sono aggiornati"))
    with st.expander(titolo, expanded=bool([r for r in fermi if r["stato"] == "bad"])):
        st.caption("Quando è stato l'ultimo salvataggio di ogni strumento. Se i dati sono fermi, i semafori e il Cruscotto non raccontano la situazione di oggi.")
        for r in righe:
            quando = "mai salvato" if r["giorni"] is None else ("oggi" if r["giorni"] == 0 else f"{r['giorni']} giorni fa")
            chi = f" · da {r['autore']}" if r["autore"] else ""
            st.markdown(f"{ico[r['stato']]} **{r['nome']}** — {quando}{chi}  <span style='color:#94a3b8'>(si aggiorna ogni {r['soglia']} gg)</span>", unsafe_allow_html=True)


def render(vai_a, consentiti=None, freschezza_righe=None):
    """consentiti: insieme di sigle visibili a chi guarda (None = tutte). I gruppi rimasti vuoti spariscono."""
    _da_dove_comincio(vai_a, consentiti)
    _freschezza(freschezza_righe or [])
    for n, (titolo, sotto, sigle) in enumerate(GRUPPI):
        sigle = [s for s in sigle if consentiti is None or s in consentiti]
        if not sigle:
            continue
        finanziaria = n == 0
        icona = ICONE_GRUPPO.get(titolo, "📁")
        with st.expander(f"{icona}  {titolo}  ·  {len(sigle)} " + ("strumento" if len(sigle) == 1 else "strumenti"),
                         expanded=(n == 0)):
            st.caption(sotto)
            for i in range(0, len(sigle), 2):
                riga = sigle[i:i + 2]
                if len(riga) == 1:
                    _scheda(riga[0], vai_a)
                    continue
                cols = st.columns(2, gap="large")
                for col, s in zip(cols, riga):
                    with col:
                        _scheda(s, vai_a)
            if finanziaria:                          # l'avvertenza riguarda la parte finanziaria: sta dentro la sezione
                st.caption(NOTA)
