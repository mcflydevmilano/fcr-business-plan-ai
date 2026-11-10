"""dc.py - Richiesta documenti: una pagina pubblica, raggiungibile solo da un link segreto, dove l'amministratore di un condominio (o un
condomino) carica i documenti di una lista (es. istruttoria di un finanziamento) e la invia solo quando è completa.
Sicurezza: stesso schema del Portale cliente (pc.py): il link (192 bit casuali) non viene salvato, solo la sua impronta SHA-256; scade,
si revoca, la pagina non mostra e non fa vedere niente della suite oltre a questa lista.
Senza Streamlit, quindi testabile."""
import datetime as dt
import hashlib
import hmac
import re
import secrets
import uuid

import storage

NOME_INDICE = "richieste_documenti"
PREFISSO_CONTENUTO = "doc_richiesta_"
GIORNI_BASE = 60
GIORNI_MAX = 180
MAX_FILE_PER_VOCE = 3
RE_TOKEN = re.compile(r"^[A-Za-z0-9_-]{20,64}$")
MSG_NON_VALIDO = "Questo link non è valido o è scaduto. Chiedi un nuovo link a chi te lo ha mandato."

# Lista base: "Elenco documenti per istruttoria Finanziamento Condominio - RETE". Ogni voce ha un id stabile (non cambia anche se il
# testo viene corretto in futuro) cosi' i documenti gia' caricati non si perdono. Le voci segnate `condizionale` partono come «non
# richieste»: l'amministratore di FCR le attiva solo se si applicano al caso (es. quota di un condomino sopra i 20 mila euro).
CATEGORIE = [
    {"nome": "Informazioni sul condominio e amministratore", "voci": [
        {"id": "v01", "testo": "Presentazione/relazione dell'amministratore sulla composizione del condominio (location, composizione, "
                                "numero condomini, ecc.), integrata con la presentazione da parte del segnalatore (Agente, Promotore, AAF, ecc.)"},
        {"id": "v02", "testo": "Elenco dei condomini con ripartizione in millesimi firmato dall'amministratore"},
        {"id": "v03", "testo": "Regolamento condominiale firmato", "nota": "Se non è firmato: copia della delibera che lo ha approvato, oppure "
                                "una dichiarazione firmata dall'amministratore che il regolamento fornito è quello in vigore."},
        {"id": "v04", "testo": "Copia del codice fiscale del condominio aggiornato, emesso dall'Agenzia delle Entrate"},
        {"id": "v05", "testo": "Documento d'identità (fronte/retro) e tessera sanitaria dell'amministratore, entrambi in corso di validità"},
        {"id": "v06", "testo": "Verbale di nomina dell'amministratore (o sua conferma), firmato"},
    ]},
    {"nome": "Regolarità economica del condominio", "voci": [
        {"id": "v07", "testo": "Copia del verbale di delibera assembleare che approva l'ultimo rendiconto (consuntivo) con il successivo "
                                "preventivo di spesa, firmata da amministratore e Presidente dell'Assemblea"},
        {"id": "v08", "testo": "Ultimo rendiconto (consuntivo) di spese e preventivo di spesa dettagliato per condomino, approvato e firmato dall'amministratore"},
        {"id": "v09", "testo": "Dichiarazione dell'amministratore che non ci sono ritardi oltre il 20% dei millesimi di proprietà, e nessun "
                                "condomino con un ritardo superiore a 4 rate, firmata dall'amministratore"},
        {"id": "v10", "testo": "Aggiornamento dei pagamenti delle rate condominiali dell'anno in corso, con il dettaglio delle spese per "
                                "condomino, firmato dall'amministratore"},
    ]},
    {"nome": "Lavori e finanziamento", "voci": [
        {"id": "v11", "testo": "Copia della delibera assembleare che autorizza la spesa per ristrutturazione, ampliamento o acquisto di "
                                "impianti e macchinari, firmata da amministratore e Presidente dell'Assemblea"},
        {"id": "v12", "testo": "Copia dell'eventuale atto negoziale (se le spese sono ripartite tra i condomini in misura diversa da quella "
                                "legale, compresa l'esenzione totale o parziale per alcuni condomini), firmato", "condizionale": True},
        {"id": "v13", "testo": "Riparto puntuale delle spese straordinarie di ciascun condomino, firmato dall'amministratore"},
        {"id": "v14", "testo": "Copia della delibera assembleare che autorizza la richiesta di finanziamento, firmata da amministratore e "
                                "Presidente dell'Assemblea", "nota": "Serve il voto favorevole di almeno i 2/3 del valore dell'immobile presente "
                                "in assemblea e la maggioranza dei condomini presenti. La delibera deve dare mandato all'amministratore ad "
                                "aprire il conto e richiedere il finanziamento, e deve dire che chi non partecipa versa la propria quota sul "
                                "conto/fondo acceso, nei tempi previsti dal contratto d'appalto."},
        {"id": "v15", "testo": "Elenco dei condomini che aderiscono al finanziamento e di quelli che non partecipano, con il dettaglio degli "
                                "importi per condomino, firmato dall'amministratore"},
        {"id": "v16", "testo": "Documento d'identità (fronte/retro) in corso di validità di ogni condomino partecipante con quota di 20.000 € o più", "condizionale": True},
        {"id": "v17", "testo": "Documento d'identità in corso di validità e codice fiscale del Presidente dell'Assemblea che ha deliberato la richiesta di finanziamento"},
        {"id": "v18", "testo": "Conferma scritta dell'amministratore che nessun condomino si è opposto alla delibera, datata e firmata 30 "
                                "giorni dopo la delibera dei lavori e del finanziamento", "nota": "Se lavori e finanziamento sono stati deliberati "
                                "in assemblee diverse, servono due dichiarazioni distinte."},
        {"id": "v19", "testo": "Preventivo di spesa / computo metrico / cronoprogramma / contratto d'appalto, firmati e timbrati dalla ditta e dall'amministratore"},
        {"id": "v20", "testo": "Perizia, per finanziamenti di 150.000 € o più (salvo i casi di esclusione previsti dalla normativa)", "condizionale": True},
        {"id": "v21", "testo": "Titoli autorizzativi (es. CILAS), se richiesti dal perito o in caso di cessione del credito (sconto in fattura)", "condizionale": True},
        {"id": "v22", "testo": "Atto notorio firmato da ogni condomino che autorizza la cessione della propria quota, con documento d'identità "
                                "(fronte/retro)", "nota": "Solo in caso di cessione del credito o sconto in fattura.", "condizionale": True},
    ]},
    {"nome": "Modulistica", "voci": [
        {"id": "v23", "testo": "Modulo di richiesta di finanziamento, compilato e firmato dall'amministratore"},
        {"id": "v24", "testo": "Modulo di autentica firme, firmato da chi ha identificato l'amministratore", "nota": "Solo se l'amministratore non è stato identificato in filiale.", "condizionale": True},
        {"id": "v25", "testo": "Privacy, accesso ai sistemi informativi e modulo di adeguata verifica del condominio, compilati e firmati dall'amministratore"},
        {"id": "v26", "testo": "Privacy e modulo di adeguata verifica dell'amministratore di condominio, compilati e firmati"},
        {"id": "v27", "testo": "Privacy e accesso ai sistemi informativi, per ogni condomino partecipante con quota di 20.000 € o più, compilati e firmati", "condizionale": True},
        {"id": "v28", "testo": "Privacy con autorizzazione al trattamento dati per fini commerciali del Presidente, compilata e firmata dal Presidente"},
    ]},
]
VOCI = {v["id"]: v for cat in CATEGORIE for v in cat["voci"]}
ORDINE_VOCI = list(VOCI)


def hash_token(token):
    return hashlib.sha256(str(token).encode()).hexdigest()


def link(token, base="https://suite.piattaformafcr.it"):
    return f"{base.rstrip('/')}/?documenti={token}"


def _carica_indice(path=None):
    try:
        raw = storage.carica_pratica(NOME_INDICE, path, modulo="cfg")
    except Exception:
        raw = None
    return [x for x in ((raw or {}).get("link") if isinstance(raw, dict) else None) or [] if isinstance(x, dict) and x.get("id") and x.get("hash")]


def _salva_indice(el, autore="", path=None):
    storage.salva_pratica(NOME_INDICE, {"link": el}, path, autore=autore, modulo="cfg")
    storage.svuota_cache()


def stato(entry, oggi=None):
    oggi = oggi or dt.date.today()
    if entry.get("revocato"):
        return "revocato"
    try:
        if dt.date.fromisoformat(entry.get("scade", "")) < oggi:
            return "scaduto"
    except ValueError:
        return "scaduto"
    return "attivo"


def elenca(path=None, oggi=None):
    oggi = oggi or dt.date.today()
    out = []
    for x in _carica_indice(path):
        out.append(dict({k: v for k, v in x.items() if k != "hash"}, stato=stato(x, oggi)))
    return out


def crea(nome, giorni=GIORNI_BASE, autore="", path=None, oggi=None):
    """Crea una richiesta. Restituisce (token, id): il token si vede solo ora."""
    oggi = oggi or dt.date.today()
    giorni = max(1, min(int(giorni), GIORNI_MAX))
    token = secrets.token_urlsafe(24)
    id_ = uuid.uuid4().hex[:10]
    el = _carica_indice(path)
    el.append({"id": id_, "hash": hash_token(token), "nome": str(nome or "").strip()[:120] or "Condominio", "creato": oggi.isoformat(),
               "scade": (oggi + dt.timedelta(days=giorni)).isoformat(), "revocato": False, "autore": autore})
    _salva_indice(el, autore, path)
    return token, id_


def trova(token, path=None, oggi=None):
    """(entry o None, stato). Per chi guarda da fuori 'non trovato', 'scaduto' e 'revocato' sono uguali."""
    if not isinstance(token, str) or not RE_TOKEN.match(token):
        return None, "non_valido"
    h = hash_token(token)
    trovato = None
    for x in _carica_indice(path):
        if hmac.compare_digest(x["hash"], h):
            trovato = x
    if not trovato:
        return None, "non_valido"
    s = stato(trovato, oggi)
    return (trovato if s == "attivo" else None), (s if s != "attivo" else "attivo")


def _modifica(id_, f, autore="", path=None):
    el = _carica_indice(path)
    ok = False
    for x in el:
        if x["id"] == id_:
            f(x)
            ok = True
    if ok:
        _salva_indice(el, autore, path)
    return ok


def revoca(id_, autore="", path=None):
    return _modifica(id_, lambda x: x.update(revocato=True), autore, path)


def proroga(id_, giorni, autore="", path=None, oggi=None):
    oggi = oggi or dt.date.today()
    giorni = max(1, min(int(giorni), GIORNI_MAX))
    return _modifica(id_, lambda x: x.update(scade=(oggi + dt.timedelta(days=giorni)).isoformat(), revocato=False), autore, path)


def _voce_vuota(id_):
    return {"richiesta": not VOCI[id_].get("condizionale"), "file": [], "nota": ""}


def contenuto_vuoto():
    return {"voci": {i: _voce_vuota(i) for i in ORDINE_VOCI}, "nota_finale": "", "firmatario": "", "inviata": None}


def _s(v, n):
    return str(v or "").strip()[:n]


def normalizza_contenuto(c):
    c = c if isinstance(c, dict) else {}
    voci_in = c.get("voci") if isinstance(c.get("voci"), dict) else {}
    voci = {}
    for i in ORDINE_VOCI:
        v = voci_in.get(i) if isinstance(voci_in.get(i), dict) else {}
        file = [{"nome": _s(f.get("nome"), 120), "tipo": _s(f.get("tipo"), 40) or "application/octet-stream", "dati": f.get("dati") or ""}
                for f in (v.get("file") or []) if isinstance(f, dict) and f.get("dati")][:MAX_FILE_PER_VOCE]
        voci[i] = {"richiesta": bool(v.get("richiesta", not VOCI[i].get("condizionale"))), "file": file, "nota": _s(v.get("nota"), 300)}
    return {"voci": voci, "nota_finale": _s(c.get("nota_finale"), 2000), "firmatario": _s(c.get("firmatario"), 120), "inviata": c.get("inviata") if isinstance(c.get("inviata"), str) else None}


def carica_contenuto(id_, path=None):
    try:
        raw = storage.carica_pratica(PREFISSO_CONTENUTO + str(id_), path, modulo="cfg")
    except Exception:
        raw = None
    return normalizza_contenuto(raw if raw is not None else contenuto_vuoto())


def salva_contenuto(id_, c, autore="", path=None):
    storage.salva_pratica(PREFISSO_CONTENUTO + str(id_), normalizza_contenuto(c), path, autore=autore, modulo="cfg")
    storage.svuota_cache()


def voci_mancanti(c):
    """Id delle voci richieste ma senza ancora nessun file."""
    return [i for i in ORDINE_VOCI if c["voci"][i]["richiesta"] and not c["voci"][i]["file"]]


def completa(c):
    return not voci_mancanti(c)


def invia(token, firmatario, nota_finale="", path=None, adesso=None):
    """Chiude la richiesta e la segna come inviata. (True, '') oppure (False, motivo). Una volta sola, solo se e' completa."""
    entry, s = trova(token, path)
    if not entry:
        return False, MSG_NON_VALIDO
    c = carica_contenuto(entry["id"], path)
    if c["inviata"]:
        return False, "Hai già inviato questi documenti."
    firmatario = _s(firmatario, 120)
    if len(firmatario) < 3:
        return False, "Scrivi nome e cognome di chi sta inviando."
    mancanti = voci_mancanti(c)
    if mancanti:
        return False, f"Mancano ancora {len(mancanti)} documenti: caricali prima di inviare."
    c["firmatario"] = firmatario
    c["nota_finale"] = _s(nota_finale, 2000)
    c["inviata"] = (adesso or dt.datetime.now()).isoformat(timespec="seconds")
    storage.salva_pratica(PREFISSO_CONTENUTO + entry["id"], c, path, autore="condominio", modulo="cfg")
    storage.svuota_cache()
    return True, ""


def riapri(id_, autore="", path=None):
    """L'amministratore FCR riapre una richiesta già inviata, per far correggere o aggiungere qualcosa."""
    c = carica_contenuto(id_, path)
    c["inviata"] = None
    storage.salva_pratica(PREFISSO_CONTENUTO + str(id_), c, path, autore=autore, modulo="cfg")
    storage.svuota_cache()
