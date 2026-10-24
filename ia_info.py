"""ia_info.py - Spiegazione chiara dell'intelligenza artificiale: cosa fa, come si usa, perche' un pulsante e' grigio. Un solo posto, usato in barra laterale, Hub e strumenti."""
import streamlit as st

ss = st.session_state

DOVE = [
    ("📊 Credit Risk", "«Estrai Dati Contabili con AI»", "legge un bilancio in PDF o Excel e compila i numeri al posto tuo (con il file XBRL non serve l'IA)."),
    ("🚀 Business Plan", "«Genera le ipotesi con l'AI»", "da poche righe di descrizione propone ricavi, costi e mutuo da cui partire."),
    ("🧮 Computo e Preventivo", "«Proponi le voci con l'AI»", "da una descrizione dei lavori propone le voci del computo con quantità e costi."),
    ("📄 Report PDF/Word", "relazione di commento", "scrive il testo che accompagna numeri e grafici (si può generare anche senza)."),
]


def stato(active_key=None):
    """'ok' (IA attiva), 'privacy' (c'e' la chiave ma manca la casella dell'informativa), 'nochiave' (nessuna chiave)."""
    if active_key:
        return "ok"
    return "privacy" if ss.get("_ia_chiave") else "nochiave"


def barra_laterale(active_key, ha_chiave):
    """Stato dell'IA in barra laterale, in italiano semplice."""
    if active_key:
        st.success("🤖 **IA pronta.** I pulsanti «con l'AI» sono attivi.")
    elif ha_chiave:
        st.warning("🤖 **IA spenta.** Per accenderla spunta la casella «Ho letto l'informativa privacy…» qui sopra. Tutto il resto funziona lo stesso.")
    else:
        st.info("🤖 **IA non disponibile** (manca la chiave). Gli strumenti funzionano ugualmente: i campi si compilano a mano. Per attivarla scrivi a Lorenzo.")


def attivazione(active_key, cosa="questa funzione"):
    """Sotto un pulsante «con l'AI»: se l'IA e' attiva ricorda di controllare, altrimenti dice esattamente cosa fare."""
    s = stato(active_key)
    if s == "ok":
        st.caption("🤖 L'IA propone una **bozza**: controlla sempre numeri e testi prima di usarli.")
    elif s == "privacy":
        st.info(f"🤖 **Per usare {cosa}:** nella barra a sinistra spunta «Ho letto l'informativa privacy…» (una volta per sessione), poi torna qui. "
                "Senza IA puoi compilare tutto a mano.")
    else:
        st.info(f"🤖 **{cosa[0].upper() + cosa[1:]} richiede l'IA, che qui non è attiva** (manca la chiave). Compila a mano: tutto il resto funziona uguale. Per attivarla scrivi a Lorenzo.")


def spiegazione():
    """Il testo completo («Cos'è l'IA e come si usa»)."""
    st.markdown("**In una frase:** l'IA è un assistente che **legge e propone**. I calcoli e le decisioni restano tuoi.")
    st.markdown("##### Dove la trovi")
    for strumento, pulsante, cosa in DOVE:
        st.markdown(f"- **{strumento}** · {pulsante}: {cosa}")
    st.markdown("##### Come si usa, in 3 passi")
    st.markdown("1. **Accendila** (una volta per sessione): nella barra a sinistra spunta «Ho letto l'informativa privacy…». Se non vedi la spunta, apri la barra con la freccia in alto.\n"
                "2. **Dalle il materiale** in modo semplice: un file, oppure due righe scritte come le diresti a un collega (es. «capannone da 2.000 m², investimento 1,2 milioni, 6 operai»).\n"
                "3. **Controlla e correggi**: quello che propone appare come bozza. Solo quando sei d'accordo premi «Applica» o salva.")
    st.markdown("##### Cosa l'IA NON fa")
    st.markdown("- **Non fa i calcoli.** Rating, cash flow, rate, parcelle, margini e semafori li calcola il programma con formule fisse: sono sempre gli stessi, con o senza IA.\n"
                "- **Non decide e non invia nulla** da sola: niente email, niente salvataggi automatici.\n"
                "- **Può sbagliare** (numeri letti male, costi non aggiornati). Le sue proposte sono stime da verificare su bilancio, prezzari e progetto.")
    st.markdown("##### Se il pulsante è grigio")
    st.markdown("- **Casella dell'informativa non spuntata** → spuntala nella barra a sinistra.\n"
                "- **Nessuna chiave** (la barra dice «IA non disponibile») → scrivi a Lorenzo, oppure compila a mano.\n"
                "- **«Quota esaurita» o «servizio sovraccarico»** → è un limite del servizio di Google: riprova più tardi (di solito entro 24 ore) o continua a mano.")
    st.markdown("##### Privacy")
    st.markdown("PDF, Excel e testi scritti per l'IA vengono inviati al servizio Gemini di Google solo quando premi il pulsante. I file **XBRL** si leggono sul posto, senza IA e senza inviare nulla. "
                "Evita di inserire dati personali di singole persone. Il testo completo è nella barra a sinistra, «Privacy e trattamento dei dati».")
    st.caption("Tutto il resto della suite (offerte, registro, scadenzario, cronoprogramma…) funziona senza IA.")
