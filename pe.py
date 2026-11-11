"""
pe.py - Persone e ruoli: l'elenco di chi lavora in azienda, con il suo ruolo, e il collegamento con gli accessi all'app.
Deterministico e senza Streamlit.

Ogni ruolo aziendale ha un profilo di accesso predefinito (quali strumenti vede). Dall'elenco si crea l'account di una persona
e si assegna il profilo in un colpo solo; il profilo si puo' sempre cambiare dalla scheda Permessi.
"""
import re
import unicodedata

import pandas as pd

from sc import data_da

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
_RE_USER = re.compile(r"^[a-z0-9][a-z0-9._-]*( [a-z0-9][a-z0-9._-]*)*$")

# ----------------------------------------------------------------------------
# LIBRO MATRICOLA: la scheda completa di ogni persona (contratto, anagrafica, residenza, documenti), come nel registro cartaceo.
# Colonne aggiuntive rispetto all'elenco base: si importano dal file Excel dell'azienda, ma restano modificabili a mano riga per riga.
COLONNE_MATRICOLA = ["Matricola", "Cognome", "Nome", "Assunzione", "Cessazione", "Tempo", "Scadenza_contratto", "Prima_scadenza", "Proroga_1", "Proroga_2", "Proroga_3", "Proroga_4",
                      "Trasformazioni", "Licenziamento", "Orario_tipo", "Ore", "Qualifica", "Mansioni", "Livello", "CCNL", "Note_matricola", "Data_nascita", "Luogo_nascita", "Nascita_prov",
                      "Codice_fiscale", "Residenza_via", "Residenza_civico", "Residenza_citta", "Residenza_prov", "Residenza_cap", "Domicilio_via", "Domicilio_citta", "Domicilio_prov",
                      "Domicilio_cap", "Sesso", "Cittadinanza", "CI_numero", "CI_scadenza", "Doc_permesso_numero", "Permesso_scadenza", "Rilasciato_da", "Varie", "IBAN"]
COLONNE_PERSONE_COMPLETE = COLONNE_PERSONE + COLONNE_MATRICOLA
COLONNE_DATE_MATRICOLA = ("Assunzione", "Cessazione", "Scadenza_contratto", "Prima_scadenza", "Proroga_1", "Proroga_2", "Proroga_3", "Proroga_4", "Data_nascita", "CI_scadenza", "Permesso_scadenza")
ETICHETTE_MATRICOLA = {"Matricola": "N. matricola", "Cognome": "Cognome", "Nome": "Nome", "Assunzione": "Data assunzione", "Cessazione": "Data cessazione", "Tempo": "Tipo contratto",
                        "Scadenza_contratto": "Ultima scadenza contratto", "Prima_scadenza": "Prima scadenza", "Proroga_1": "1° proroga", "Proroga_2": "2° proroga", "Proroga_3": "3° proroga",
                        "Proroga_4": "4° proroga", "Trasformazioni": "Trasformazioni", "Licenziamento": "Licenziamento / dimissioni", "Orario_tipo": "Tipologia orario", "Ore": "Ore settimanali",
                        "Qualifica": "Qualifica", "Mansioni": "Mansioni", "Livello": "Livello", "CCNL": "CCNL", "Note_matricola": "Note", "Data_nascita": "Data di nascita",
                        "Luogo_nascita": "Luogo di nascita", "Nascita_prov": "Prov. nascita", "Codice_fiscale": "Codice fiscale", "Residenza_via": "Residenza (via e civico)",
                        "Residenza_civico": "N. civico", "Residenza_citta": "Città residenza", "Residenza_prov": "Prov. residenza", "Residenza_cap": "CAP residenza",
                        "Domicilio_via": "Domicilio (via e civico)", "Domicilio_citta": "Città domicilio", "Domicilio_prov": "Prov. domicilio", "Domicilio_cap": "CAP domicilio", "Sesso": "Sesso",
                        "Cittadinanza": "Cittadinanza", "CI_numero": "Carta d'identità n°", "CI_scadenza": "Scadenza CI", "Doc_permesso_numero": "N. documento / permesso di soggiorno",
                        "Permesso_scadenza": "Scadenza permesso di soggiorno", "Rilasciato_da": "Rilasciato da (comune/questura)", "Varie": "Varie", "IBAN": "IBAN"}
ETICHETTE_PERSONE_COMPLETE = {**ETICHETTE_PERSONE, **ETICHETTE_MATRICOLA}
# intestazioni del libro matricola -> colonna interna. Alcune compaiono piu' di una volta nel file con lo stesso testo (PROV, CITTA', CAP):
# si distinguono dall'ordine in cui compaiono da sinistra a destra, non dal testo (vedi _intestazioni_matricola).
_ALIAS_MATRICOLA_UNICHE = {"mat.": "Matricola", "cognome": "Cognome", "nome": "Nome", "cantiere": "Cantiere", "data assunzione": "Assunzione", "data cessazione": "Cessazione",
                           "tempo": "Tempo", "prima scadenza": "Prima_scadenza", "1 proroga": "Proroga_1", "2 proroga": "Proroga_2", "3 proroga": "Proroga_3", "4 proroga": "Proroga_4",
                           "trasformazioni": "Trasformazioni", "tipologia orario": "Orario_tipo", "ore": "Ore", "qualifica": "Qualifica", "livello": "Livello", "ccnl": "CCNL",
                           "note": "Note_matricola", "luogo di nascita": "Luogo_nascita", "codice fiscale": "Codice_fiscale", "tel/cell.": "Telefono", "n. civ.": "Residenza_civico",
                           "sesso": "Sesso", "varie": "Varie", "iban": "IBAN", "residenza": "Residenza_via", "domicilio": "Domicilio_via", "ci n": "CI_numero",
                           "mansioni": "Mansioni", "mansione": "Mansioni", "cittadinzanza": "Cittadinanza", "cittadinanza": "Cittadinanza"}
# per queste, l'ordine di apparizione decide (prima occorrenza -> primo elemento, ecc.); oltre l'ultimo elemento resta l'ultimo.
_ALIAS_MATRICOLA_RIPETUTE = {"prov": ["Nascita_prov", "Residenza_prov", "Domicilio_prov"], "citta": ["Residenza_citta", "Domicilio_citta"], "cap": ["Residenza_cap", "Domicilio_cap"]}
# frammenti (contenuti nell'intestazione normalizzata) per le colonne con un'intestazione lunga o su piu' righe
_ALIAS_MATRICOLA_CONTIENE = [("ultima scadenza", "Scadenza_contratto"), ("licenziamento", "Licenziamento"), ("data di", "Data_nascita"),
                             ("permesso di soggiorno scadenz", "Permesso_scadenza"), ("permesso di sogg", "Doc_permesso_numero"), ("rilasciato da", "Rilasciato_da"), ("scadenza", "CI_scadenza")]


def _n_matricola(s):
    s = re.sub(r"[°'\n]", " ", str(s or "").strip().lower())
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s).strip()


def _intestazioni_matricola(riga):
    """{indice_colonna: colonna_interna} leggendo l'intestazione del libro matricola, gestendo le colonne ripetute per ordine di apparizione."""
    contatori = {}
    mappa = {}
    for j, v in enumerate(riga):
        n = _n_matricola(v)
        if not n:
            continue
        if n in _ALIAS_MATRICOLA_RIPETUTE:
            lista = _ALIAS_MATRICOLA_RIPETUTE[n]
            i = contatori.get(n, 0)
            mappa[j] = lista[min(i, len(lista) - 1)]
            contatori[n] = i + 1
        elif n in _ALIAS_MATRICOLA_UNICHE:
            mappa[j] = _ALIAS_MATRICOLA_UNICHE[n]
        else:
            for frammento, campo in _ALIAS_MATRICOLA_CONTIENE:
                if frammento in n:
                    mappa[j] = campo
                    break
    return mappa


def _t(v):
    return "" if v is None or v != v else str(v).strip()


def _data_matricola(v):
    if v is None or v != v or _t(v) == "":
        return ""
    d = data_da(v)
    return d.isoformat() if d else _t(v)


def da_matricola(sorgente):
    """Legge il libro matricola: trova il foglio e la riga di intestazione da solo (cerca «MAT.» e «COGNOME»). Restituisce (righe_grezze, rapporto)."""
    xls = pd.ExcelFile(sorgente)
    rapp = {"foglio": None, "righe": 0, "saltati": []}
    for nome in xls.sheet_names:
        raw = pd.read_excel(xls, nome, header=None)
        h = next((i for i in range(min(len(raw), 10)) if len(_intestazioni_matricola(list(raw.iloc[i]))) >= 5 and "Matricola" in _intestazioni_matricola(list(raw.iloc[i])).values()
                  and "Cognome" in _intestazioni_matricola(list(raw.iloc[i])).values()), None)
        if h is None:
            rapp["saltati"].append(nome)
            continue
        mappa = _intestazioni_matricola(list(raw.iloc[h]))
        righe = []
        for _, riga in raw.iloc[h + 1:].iterrows():
            d = {}
            for j, c in mappa.items():                     # due colonne diverse possono mappare sullo stesso campo (es. «MANSIONI»/«MANSIONE»): vince la prima non vuota
                v = riga.iloc[j]
                if c not in d or (not _t(d[c]) and _t(v)):
                    d[c] = v
            if any(_t(d.get(c)) for c in ("Matricola", "Cognome", "Nome")):
                righe.append(d)
        rapp["foglio"] = nome
        rapp["righe"] = len(righe)
        return righe, rapp
    return [], rapp


def normalizza_matricola(righe):
    """(righe pulite nello schema COLONNE_PERSONE_COMPLETE, avvisi). «Persona» si ricava da Cognome e Nome."""
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        cognome, nome = _t(r.get("Cognome")), _t(r.get("Nome"))
        if not cognome and not nome:
            continue
        z = {c: "" for c in COLONNE_PERSONE_COMPLETE}
        for c in COLONNE_MATRICOLA:
            z[c] = _data_matricola(r.get(c)) if c in COLONNE_DATE_MATRICOLA else _t(r.get(c))
        z["Persona"] = f"{nome} {cognome}".strip()
        z["Cantiere"] = _t(r.get("Cantiere"))
        z["Telefono"] = _t(r.get("Telefono"))
        z["Tipo"] = "Dipendente"
        z["Attivo"] = "No" if z["Cessazione"] or z["Licenziamento"] else "Sì"
        if not z["Persona"]:
            avvisi.append(f"Riga {i}: manca cognome e nome, riga ignorata.")
            continue
        out.append(z)
    return out, avvisi


def importa_matricola(sorgente):
    """(righe, avvisi, rapporto) dal file Excel del libro matricola."""
    grezze, rapp = da_matricola(sorgente)
    righe, avvisi = normalizza_matricola(grezze)
    if rapp.get("saltati") and not rapp.get("foglio"):
        avvisi.append("Non ho trovato un foglio con le colonne del libro matricola (servono almeno «MAT.» e «COGNOME»).")
    return righe, avvisi, rapp


def unisci_matricola(attuali, nuove):
    """Aggiorna per matricola (o per nome se manca) e aggiunge le righe nuove."""
    per_mat = {r["Matricola"].lower(): i for i, r in enumerate(attuali) if r.get("Matricola")}
    per_nome = {r["Persona"].lower(): i for i, r in enumerate(attuali) if r.get("Persona")}
    out = [dict(r) for r in attuali]
    for r in nuove:
        i = per_mat.get(r["Matricola"].lower()) if r.get("Matricola") else None
        if i is None:
            i = per_nome.get(r["Persona"].lower())
        if i is None:
            out.append(r)
        else:
            out[i] = {**out[i], **r}
    return out


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
        if user and not (3 <= len(user) <= 40 and _RE_USER.match(user)):
            avvisi.append(f"«{n}»: il nome utente «{user}» non è valido (3-40 caratteri: lettere, numeri e spazi).")
        z = {"Persona": n, "Ruolo": _t(r.get("Ruolo")) or "Altro", "Reparto": _t(r.get("Reparto")), "Telefono": _t(r.get("Telefono")), "Email": _t(r.get("Email")),
             "Cantiere": _t(r.get("Cantiere")), "Tipo": t if t in TIPI else "Dipendente", "Utente": user, "Attivo": "No" if att in ("no", "n", "false", "0", "cessato") else "Sì"}
        for c in COLONNE_MATRICOLA:                        # conserva anche la scheda del libro matricola, se presente (non obbligatoria)
            z[c] = _data_matricola(r.get(c)) if c in COLONNE_DATE_MATRICOLA else _t(r.get(c))
        out.append(z)
    return out, avvisi


def profilo_per_ruolo(ruolo, mappa=None):
    return {**PROFILO_PER_RUOLO, **(mappa or {})}.get(ruolo, "cantiere")


def _ascii(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def username_suggerito(persona, esistenti=()):
    """«nome cognome» in minuscolo senza accenti, con lo spazio; se esiste gia' aggiunge un numero."""
    parole = [w for w in re.findall(r"[a-z0-9]+", _ascii(_t(persona)).lower())]
    base = " ".join([parole[0], parole[-1]]) if len(parole) >= 2 else (parole[0] if parole else "utente")
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
