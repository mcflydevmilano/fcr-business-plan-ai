"""
pe.py - Persone e ruoli: l'elenco di chi lavora in azienda, con il suo ruolo, e il collegamento con gli accessi all'app.
Deterministico e senza Streamlit.

Ogni ruolo aziendale ha un profilo di accesso predefinito (quali strumenti vede). Dall'elenco si crea l'account di una persona
e si assegna il profilo in un colpo solo; il profilo si puo' sempre cambiare dalla scheda Permessi.
"""
import re
import unicodedata

RUOLI = ["Presidente", "Direttore generale", "Direttore tecnico", "Responsabile amministrativo", "Impiegato amministrativo", "Ufficio gare / commerciale",
         "Capocantiere", "Geometra", "Operaio", "Addetto sicurezza (RSPP)", "Referente legale", "Altro"]
# ruolo aziendale -> profilo di accesso (vedi permessi.py). Un ruolo non elencato prende il profilo piu' prudente: «cantiere».
PROFILO_PER_RUOLO = {"Presidente": "presidente", "Direttore generale": "direzione", "Direttore tecnico": "direzione", "Responsabile amministrativo": "amministrazione",
                     "Impiegato amministrativo": "amministrazione", "Ufficio gare / commerciale": "commerciale", "Capocantiere": "cantiere", "Geometra": "cantiere",
                     "Operaio": "cantiere", "Addetto sicurezza (RSPP)": "cantiere", "Referente legale": "legale", "Altro": "cantiere"}
TIPI = ["Dipendente", "Collaboratore", "Tirocinante"]
COLONNE_PERSONE = ["Persona", "Ruolo", "Reparto", "Telefono", "Email", "Cantiere", "Tipo", "Utente", "Attivo"]
ETICHETTE_PERSONE = {"Persona": "Nome e cognome", "Ruolo": "Ruolo in azienda", "Reparto": "Reparto / ufficio", "Telefono": "Telefono / cellulare", "Email": "Email", "Cantiere": "Cantiere assegnato",
                     "Tipo": "Tipo", "Utente": "Nome utente nell'app", "Attivo": "In servizio"}
SINONIMI_PERSONE = {"Persona": ("Nominativo", "Dipendente", "Cognome e nome", "Nome"), "Ruolo": ("Mansione", "Qualifica", "Funzione"), "Telefono": ("Cellulare", "cell", "Tel"), "Email": ("Mail", "E-mail"),
                    "Cantiere": ("Commessa", "Sede")}
_RE_USER = re.compile(r"^[a-z0-9][a-z0-9._-]{2,39}$")


def _t(v):
    return "" if v is None or v != v else str(v).strip()


def normalizza_persone(righe):
    out, avvisi, visti = [], [], set()
    for i, r in enumerate(righe or [], start=1):
        if not any(_t(r.get(c)) for c in COLONNE_PERSONE):
            continue
        n = _t(r.get("Persona"))
        if not n:
            avvisi.append(f"Persona, riga {i}: manca il nome, riga ignorata.")
            continue
        if n.lower() in visti:
            avvisi.append(f"«{n}» compare più volte nell'elenco.")
        visti.add(n.lower())
        t = _t(r.get("Tipo"))
        att = _t(r.get("Attivo")).lower()
        user = _t(r.get("Utente")).lower()
        if user and not _RE_USER.match(user):
            avvisi.append(f"«{n}»: il nome utente «{user}» non è valido (3-40 caratteri: lettere minuscole, numeri, punto, trattino).")
        out.append({"Persona": n, "Ruolo": _t(r.get("Ruolo")) or "Altro", "Reparto": _t(r.get("Reparto")), "Telefono": _t(r.get("Telefono")), "Email": _t(r.get("Email")),
                    "Cantiere": _t(r.get("Cantiere")), "Tipo": t if t in TIPI else "Dipendente", "Utente": user, "Attivo": "No" if att in ("no", "n", "false", "0", "cessato") else "Sì"})
    return out, avvisi


def profilo_per_ruolo(ruolo, mappa=None):
    return {**PROFILO_PER_RUOLO, **(mappa or {})}.get(ruolo, "cantiere")


def _ascii(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def username_suggerito(persona, esistenti=()):
    """nome.cognome in minuscolo senza accenti; se esiste gia' aggiunge un numero."""
    parole = [w for w in re.findall(r"[a-z0-9]+", _ascii(_t(persona)).lower())]
    base = ".".join([parole[0], parole[-1]]) if len(parole) >= 2 else (parole[0] if parole else "utente")
    base = (base + "xx")[:36] if len(base) < 3 else base[:36]
    nomi = {e.lower() for e in esistenti}
    cand, n = base, 2
    while cand in nomi:
        cand = f"{base}{n}"
        n += 1
    return cand


def calcola_pe(persone, utenti_app=None):
    """utenti_app: {username: {'ruolo', 'attivo'}} di tutti gli account esistenti (secrets e database)."""
    ua = {k.lower(): v for k, v in (utenti_app or {}).items()}
    avvisi = []
    collegati = {p["Utente"] for p in persone if p["Utente"]}
    for p in persone:
        if p["Utente"] and p["Utente"] not in ua:
            avvisi.append(f"{p['Persona']}: il nome utente «{p['Utente']}» non esiste ancora nell'app.")
        if p["Attivo"] == "No" and p["Utente"] and ua.get(p["Utente"], {}).get("attivo", True):
            avvisi.append(f"{p['Persona']} non è più in servizio ma ha ancora l'accesso attivo: revocalo.")
    orfani = sorted(u for u in ua if u not in collegati)
    if orfani:
        avvisi.append("Account senza persona nell'elenco: " + ", ".join(orfani[:8]) + ("…" if len(orfani) > 8 else "") + ".")
    per_ruolo = {}
    for p in persone:
        per_ruolo[p["Ruolo"]] = per_ruolo.get(p["Ruolo"], 0) + 1
    kpi = {"persone": len(persone), "in_servizio": sum(1 for p in persone if p["Attivo"] == "Sì"), "con_account": sum(1 for p in persone if p["Utente"]),
           "senza_recapito": sum(1 for p in persone if not p["Telefono"] and not p["Email"]), "per_ruolo": per_ruolo, "account_orfani": len(orfani),
           "da_revocare": sum(1 for p in persone if p["Attivo"] == "No" and p["Utente"] and ua.get(p["Utente"], {}).get("attivo", True))}
    return {"kpi": kpi, "avvisi": avvisi, "orfani": orfani}


def persone_salvate(path=None):
    """Elenco delle persone dall'ultimo salvataggio dello strumento (per chi lo usa senza aprirlo)."""
    import storage
    try:
        el = storage.elenca_pratiche(path, modulo="pe")
        if el:
            return normalizza_persone((storage.carica_pratica(el[0]["nome"], path, modulo="pe") or {}).get("persone"))[0]
    except Exception:
        pass
    return []
