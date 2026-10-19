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
     ["credit", "bp", "cf", "sc"]),
    ("Offerte e commesse", "Dalla gara al preventivo, fino all'avanzamento lavori",
     ["ga", "pv", "sl", "fo"]),
    ("Cantiere e risorse", "Sicurezza, mezzi, persone e scadenze",
     ["sx", "mz", "og", "ca"]),
    ("Direzione", "La sintesi di tutta l'azienda",
     ["dd"]),
]


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


def render(vai_a):
    for n, (titolo, sotto, sigle) in enumerate(GRUPPI):
        st.markdown(theme.hub_sezione(titolo, sotto), unsafe_allow_html=True)
        for i in range(0, len(sigle), 2):
            riga = sigle[i:i + 2]
            if len(riga) == 1:
                _scheda(riga[0], vai_a)
                continue
            cols = st.columns(2, gap="large")
            for col, s in zip(cols, riga):
                with col:
                    _scheda(s, vai_a)
        if n == 0:                                   # l'avvertenza riguarda la parte finanziaria: sta subito sotto
            st.caption(NOTA)
