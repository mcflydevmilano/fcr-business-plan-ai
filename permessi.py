"""permessi.py - Chi vede quali strumenti (senza Streamlit, quindi testabile).

Ogni utente ha un PROFILO; ogni profilo ha l'elenco degli strumenti che puo' aprire. L'amministratore vede sempre tutto.
La configurazione e' salvata nel database (pratica riservata cfg|permessi), quindi resta anche dopo i riavvii.
Il ruolo (admin / utente / lettore) decide invece se si puo' MODIFICARE: sono due cose indipendenti.
"""
import storage

TUTTI = ["credit", "bp", "cf", "sc", "bk", "oa", "ga", "pv", "sl", "gt", "rp", "sx", "mz", "og", "fo", "ru", "pe", "lg", "ca", "dd", "pz", "rc"]
NOMI = {"credit": "Credit Risk & Rating", "bp": "Business Plan", "cf": "Cash Flow di cantiere", "sc": "Scadenzario", "bk": "Riconciliazione bancaria",
        "oa": "Ordini e approvazioni", "ga": "Gare e offerte", "pv": "Computo e Preventivo", "sl": "SAL e contabilità lavori", "gt": "Cronoprogramma",
        "rp": "Rapportini", "sx": "Sicurezza", "mz": "Parco mezzi", "og": "Organico", "fo": "Fornitori", "ru": "Rubrica e cantieri", "pe": "Persone e ruoli",
        "lg": "Studio legale", "ca": "Calendario", "dd": "Cruscotto di direzione", "pz": "Prezziario", "rc": "Registro commerciale"}
RISERVATI = {"dd"}            # strumenti che nessun profilo (tranne presidente e admin) riceve per impostazione predefinita

PROFILI_BASE = {
    "presidente": list(TUTTI),
    "direzione": [s for s in TUTTI if s not in RISERVATI],
    "amministrazione": ["credit", "bp", "cf", "sc", "bk", "oa", "pv", "pz", "fo", "ru", "pe", "ca"],
    "commerciale": ["rc", "ga", "pv", "pz", "sl", "gt", "ru", "ca"],
    "cantiere": ["rp", "sx", "mz", "og", "gt", "fo", "ru", "oa", "pz", "ca"],
    "legale": ["lg", "ru", "sc", "fo", "ca"],
}
PROFILO_PREDEFINITO = "direzione"
NUOVI_STRUMENTI = ["pz", "rc"]      # aggiunti dopo i primi salvataggi dei permessi: ai profili gia' salvati si danno secondo le regole base
NOME_PRATICA = "permessi"


def configurazione_base():
    return {"profili": {k: list(v) for k, v in PROFILI_BASE.items()}, "utenti": {}, "predefinito": PROFILO_PREDEFINITO}


def normalizza(cfg):
    """Rende valida una configurazione qualsiasi: tiene solo strumenti noti, profili esistenti, almeno il presidente completo."""
    base = configurazione_base()
    cfg = cfg if isinstance(cfg, dict) else {}
    profili = {}
    for nome, mod in (cfg.get("profili") or base["profili"]).items():
        n = str(nome).strip().lower()
        if n:
            profili[n] = [s for s in TUTTI if s in set(mod or [])]
    noti = set(cfg.get("noti") or [s for s in TUTTI if s not in NUOVI_STRUMENTI])
    for s in TUTTI:                                            # strumento nato dopo il salvataggio: i profili base lo ricevono, quelli personalizzati no
        if s not in noti:
            for nome, mod in PROFILI_BASE.items():
                if nome in profili and s in mod and s not in profili[nome]:
                    profili[nome] = [x for x in TUTTI if x in set(profili[nome]) | {s}]
    profili["presidente"] = list(TUTTI)                        # il presidente non puo' restare senza strumenti
    profili.setdefault(PROFILO_PREDEFINITO, list(PROFILI_BASE[PROFILO_PREDEFINITO]))      # chi non ha un profilo cade sempre su uno esistente
    pred = str(cfg.get("predefinito") or PROFILO_PREDEFINITO).strip().lower()
    if pred not in profili:
        pred = PROFILO_PREDEFINITO if PROFILO_PREDEFINITO in profili else next(iter(profili))
    utenti = {str(u).strip().lower(): str(p).strip().lower() for u, p in (cfg.get("utenti") or {}).items() if str(p).strip().lower() in profili}
    return {"profili": profili, "utenti": utenti, "predefinito": pred, "noti": list(TUTTI)}


def carica_config(path=None):
    try:
        raw = storage.carica_pratica(NOME_PRATICA, path, modulo="cfg")
    except Exception:
        raw = None
    return normalizza(raw)


def salva_config(cfg, autore="", path=None):
    cfg = normalizza(cfg)
    storage.salva_pratica(NOME_PRATICA, cfg, path, autore=autore, modulo="cfg")
    return cfg


def profilo_di(utente, cfg):
    nome = (utente or {}).get("username", "")
    return cfg["utenti"].get(str(nome).lower(), cfg["predefinito"])


def moduli_consentiti(utente, cfg):
    """Insieme delle sigle apribili. Admin: tutto."""
    if (utente or {}).get("ruolo") == "admin":
        return set(TUTTI)
    return set(cfg["profili"].get(profilo_di(utente, cfg), []))


def puo(utente, sigla, cfg):
    return sigla in (None, "admin") or sigla in moduli_consentiti(utente, cfg)
