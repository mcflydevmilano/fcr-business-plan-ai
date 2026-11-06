"""
onboarding.py - Nuova persona con accesso alla suite in un colpo solo: account, password provvisoria, profilo (cosa vede) ed email.
Senza Streamlit (testabile). Lo usano sia Amministrazione → Utenti sia Persone e ruoli.
"""
import auth
import permessi
import posta
import storage


def testo_accesso(nome, password, nuovo=True, url="", strumenti=None):
    """(oggetto, corpo) dell'email con la password provvisoria. `strumenti`: nomi degli strumenti che la persona potra' usare."""
    url = url or "https://suite.piattaformafcr.it"
    ben = f"Ciao {auth.mostra_nome(nome).split()[0]}," if nome else "Ciao,"
    prima = ("ti abbiamo creato l'accesso alla FCR Suite, il gestionale di FCR General Contractor." if nuovo
             else "l'amministratore ha reimpostato la tua password della FCR Suite.")
    usa = f"Strumenti a tua disposizione: {', '.join(strumenti)}.\n\n" if strumenti else ""
    corpo = (f"{ben}\n\n{prima}\n\nIndirizzo: {url}\nNome utente: {auth.mostra_nome(nome)}  (maiuscole e minuscole non contano; lo spazio sì)\n"
             f"Password provvisoria: {password}\n\n"
             "Al primo accesso la suite ti chiede di scegliere una password tua (almeno 10 caratteri, con lettere e numeri): "
             "è obbligatorio, poi la password provvisoria non funziona più.\n\n"
             f"{usa}"
             "Non dare la password a nessuno e cancella questa email dopo il primo accesso.\n"
             "Se non riesci a entrare, scrivi all'amministratore.\n\nFCR Suite")
    return "Il tuo accesso alla FCR Suite", corpo


def strumenti_del_profilo(profilo, path=None):
    cfg = permessi.carica_config(path)
    return [permessi.NOMI[s] for s in cfg["profili"].get(profilo, []) if s in permessi.NOMI]


def imposta_profilo(username, profilo, da="", path=None):
    cfg = permessi.carica_config(path)
    if profilo not in cfg["profili"]:
        raise ValueError("Profilo non valido.")
    cfg["utenti"][username] = profilo
    permessi.salva_config(cfg, da, path)


def crea_account(username, email, livello, profilo, da="", path=None):
    """Crea l'utente con password generata (da cambiare al primo accesso), gli assegna il profilo e, se c'e' la posta, gli scrive.
    Restituisce {utente, password, inviata}. Solleva ValueError se il nome o l'email non vanno bene o l'utente esiste."""
    password = auth.genera_password_temporanea()
    auth.crea_utente(username, password, livello, da, path, email=email, cambio_pw=True)
    u = auth.normalizza_username(username)
    imposta_profilo(u, profilo, da, path)
    inviata = False
    if email and posta.indirizzo_valido(email) and posta.smtp_pronto():
        ogg, corpo = testo_accesso(u, password, True, strumenti=strumenti_del_profilo(profilo, path))
        inviata = bool(posta.invia_con_feedback([email], ogg, corpo))
        if inviata:
            storage.log_evento("sistema", "email_accesso", f"{u} -> {email}", path)
    return {"utente": u, "password": password, "inviata": inviata}
