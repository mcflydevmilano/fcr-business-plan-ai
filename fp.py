"""
fp.py - Ferie e permessi: la persona chiede, il responsabile approva, il calendario mostra chi manca.
Giorni lavorativi (senza sabato, domenica e festivi), giorni residui di ciascuno, avviso se in un periodo restano troppo pochi presenti. Senza Streamlit.
"""
import datetime as dt

import richieste
import storage

TIPO = "fp"
TIPI = ["Ferie", "Permesso (ore)", "Malattia", "Altro"]
STATI = ["In attesa", "Approvata", "Respinta", "Annullata"]
NOME_CFG = "ferie_cfg"
CFG_BASE = {"giorni_ferie": 26.0, "ore_permesso": 32.0, "minimo_presenti": 2, "approvatori": [], "personale": [], "per_persona": {}, "festivi_locali": ["12-07"]}
FESTIVI_FISSI = ["01-01", "01-06", "04-25", "05-01", "06-02", "08-15", "11-01", "12-08", "12-25", "12-26"]


def pasqua(anno):
    a, b, c = anno % 19, anno // 100, anno % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mese, giorno = divmod(h + l - 7 * m + 114, 31)
    return dt.date(anno, mese, giorno + 1)


def festivi(anno, locali=()):
    out = {dt.date(anno, int(x[:2]), int(x[3:])) for x in list(FESTIVI_FISSI) + list(locali or ())}
    out.add(pasqua(anno) + dt.timedelta(days=1))
    return out


def lavorativo(giorno, locali=()):
    return giorno.weekday() < 5 and giorno not in festivi(giorno.year, locali)


def giorni_lavorativi(dal, al, locali=()):
    n, g = 0, dal
    while g <= al:
        n += 1 if lavorativo(g, locali) else 0
        g += dt.timedelta(days=1)
    return n


def _d(v):
    return v if isinstance(v, dt.date) else dt.date.fromisoformat(str(v)[:10])


def normalizza_cfg(raw):
    c = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v) for k, v in CFG_BASE.items()}
    raw = raw if isinstance(raw, dict) else {}
    for k, mx in (("giorni_ferie", 60.0), ("ore_permesso", 300.0)):
        try:
            c[k] = min(max(float(raw.get(k, c[k])), 0.0), mx)
        except (TypeError, ValueError):
            pass
    try:
        c["minimo_presenti"] = int(min(max(int(raw.get("minimo_presenti", 2)), 0), 100))
    except (TypeError, ValueError):
        pass
    for k in ("approvatori", "personale"):
        c[k] = sorted({" ".join(str(x).split()).lower() for x in (raw.get(k) or []) if str(x).strip()})
    pp = {}
    for u, v in (raw.get("per_persona") or {}).items():
        if isinstance(v, dict):
            try:
                pp[" ".join(str(u).split()).lower()] = {"giorni_ferie": float(v["giorni_ferie"]), "ore_permesso": float(v["ore_permesso"])}
            except (KeyError, TypeError, ValueError):
                continue
    c["per_persona"] = pp
    loc = []
    for x in raw.get("festivi_locali", c["festivi_locali"]) or []:
        try:
            dt.date(2024, int(str(x)[:2]), int(str(x)[3:5]))
            loc.append(str(x)[:5])
        except (TypeError, ValueError):
            pass
    c["festivi_locali"] = loc
    return c


def carica_cfg(path=None):
    try:
        return normalizza_cfg(storage.carica_pratica(NOME_CFG, path, modulo="cfg"))
    except Exception:
        return normalizza_cfg({})


def salva_cfg(cfg, autore="", path=None):
    storage.salva_pratica(NOME_CFG, normalizza_cfg(cfg), path, autore=autore, modulo="cfg")


def spettanze(utente, cfg):
    p = (cfg.get("per_persona") or {}).get(" ".join(str(utente).split()).lower())
    return (p["giorni_ferie"], p["ore_permesso"]) if p else (cfg["giorni_ferie"], cfg["ore_permesso"])


def puo_approvare(utente, ruolo_utente, profilo, cfg, richiedente):
    """Chi approva: amministratore, direzione e amministrazione, oppure le persone scelte nelle regole. Nessuno approva le proprie richieste (tranne l'amministratore)."""
    nome = " ".join(str(utente).split()).lower()
    if nome == " ".join(str(richiedente).split()).lower() and ruolo_utente != "admin":
        return False
    if cfg.get("approvatori"):
        return ruolo_utente == "admin" or nome in cfg["approvatori"]
    return ruolo_utente == "admin" or profilo in ("presidente", "direzione", "amministrazione", "accesso completo")


def giorni_richiesta(dati, locali=()):
    """Giorni lavorativi (ferie, malattia, altro) o ore (permesso) di una richiesta."""
    if dati.get("tipo") == "Permesso (ore)":
        return 0.0
    return float(giorni_lavorativi(_d(dati["dal"]), _d(dati["al"]), locali))


def valida(dati, esistenti=(), cfg=None):
    """Messaggio d'errore o ''. `esistenti`: le altre richieste della stessa persona (non annullate/respinte)."""
    t = dati.get("tipo")
    if t not in TIPI:
        return "Scegli il tipo di richiesta."
    try:
        dal, al = _d(dati["dal"]), _d(dati["al"])
    except (KeyError, ValueError):
        return "Indica le date."
    if al < dal:
        return "La data di fine è prima di quella di inizio."
    if t == "Permesso (ore)":
        if dal != al:
            return "Il permesso a ore vale per un solo giorno."
        try:
            if not 0 < float(dati.get("ore") or 0) <= 8:
                return "Indica le ore di permesso (da mezz'ora a 8 ore)."
        except (TypeError, ValueError):
            return "Indica le ore di permesso."
    if t == "Altro" and len(str(dati.get("motivo") or "").strip()) < 3:
        return "Spiega il motivo."
    if t != "Permesso (ore)" and giorni_lavorativi(dal, al, (cfg or {}).get("festivi_locali", ())) == 0:
        return "Nel periodo scelto non ci sono giorni lavorativi."
    for r in esistenti:
        if r["stato"] in ("In attesa", "Approvata"):
            d2 = r["dati"]
            if _d(d2["dal"]) <= al and _d(d2["al"]) >= dal and not (t == "Permesso (ore)" and d2.get("tipo") == "Permesso (ore)"):
                return f"Hai già una richiesta ({d2.get('tipo')}) dal {_d(d2['dal']):%d/%m/%Y} al {_d(d2['al']):%d/%m/%Y}."
    return ""


def residui(utente, anno, lista, cfg):
    """Spettanza, usate, in attesa e residue di ferie (giorni) e permessi (ore) per un anno."""
    sf, sp = spettanze(utente, cfg)
    loc = cfg.get("festivi_locali", ())
    usate = attesa = ore_u = ore_a = 0.0
    a0, a1 = dt.date(anno, 1, 1), dt.date(anno, 12, 31)
    for r in lista:
        if r["utente"] != utente or r["stato"] not in ("Approvata", "In attesa"):
            continue
        d = r["dati"]
        if d.get("tipo") == "Ferie":
            n = float(giorni_lavorativi(max(_d(d["dal"]), a0), min(_d(d["al"]), a1), loc)) if _d(d["dal"]) <= a1 and _d(d["al"]) >= a0 else 0.0
            usate, attesa = (usate + n, attesa) if r["stato"] == "Approvata" else (usate, attesa + n)
        elif d.get("tipo") == "Permesso (ore)" and _d(d["dal"]).year == anno:
            o = float(d.get("ore") or 0)
            ore_u, ore_a = (ore_u + o, ore_a) if r["stato"] == "Approvata" else (ore_u, ore_a + o)
    return {"ferie_spettanti": sf, "ferie_usate": usate, "ferie_attesa": attesa, "ferie_residue": sf - usate - attesa,
            "permessi_spettanti": sp, "permessi_usati": ore_u, "permessi_attesa": ore_a, "permessi_residui": sp - ore_u - ore_a}


def assenti_il(lista, giorno, stati=("Approvata", "In attesa"), escludi_id=None):
    """Persone assenti per l'intero giorno (ferie, malattia, altro: i permessi a ore non contano)."""
    out = {}
    for r in lista:
        d = r["dati"]
        if r["stato"] in stati and r["id"] != escludi_id and d.get("tipo") != "Permesso (ore)" and _d(d["dal"]) <= giorno <= _d(d["al"]):
            out[r["utente"]] = d["tipo"]
    return out


def copertura(lista, dal, al, personale, minimo, locali=(), escludi_id=None, persona_nuova=None):
    """Giorni lavorativi del periodo in cui i presenti scendono sotto il minimo: [{giorno, presenti, assenti[]}]. `persona_nuova` = chi sta chiedendo (si conta assente)."""
    out, g = [], dal
    tot = len(set(personale))
    while g <= al:
        if lavorativo(g, locali):
            ass = set(assenti_il(lista, g, escludi_id=escludi_id)) & set(personale)
            if persona_nuova:
                ass.add(persona_nuova)
            presenti = tot - len(ass)
            if tot and presenti < minimo:
                out.append({"giorno": g, "presenti": presenti, "assenti": sorted(ass)})
        g += dt.timedelta(days=1)
    return out


def matrice_mese(lista, anno, mese, personale, locali=()):
    """Righe persona x giorni del mese: sigla F (ferie), M (malattia), A (altro), P (permesso a ore), - (festivo/fine settimana), ? se in attesa."""
    g0 = dt.date(anno, mese, 1)
    g1 = dt.date(anno + (mese == 12), mese % 12 + 1, 1) - dt.timedelta(days=1)
    giorni = [g0 + dt.timedelta(days=i) for i in range((g1 - g0).days + 1)]
    sigla = {"Ferie": "F", "Malattia": "M", "Altro": "A", "Permesso (ore)": "P"}
    righe = []
    for p in sorted(set(personale), key=str.lower):
        riga = {"Persona": p}
        for g in giorni:
            c = "" if lavorativo(g, locali) else "·"
            for r in lista:
                d = r["dati"]
                if r["utente"] == p and r["stato"] in ("Approvata", "In attesa") and _d(d["dal"]) <= g <= _d(d["al"]):
                    c = sigla.get(d.get("tipo"), "A") + ("?" if r["stato"] == "In attesa" else "")
                    break
            riga[f"{g.day:02d}"] = c
        righe.append(riga)
    return righe


def assenze_per_calendario(oggi=None, giorni=60, path=None):
    """Assenze approvate in corso o future, per il Calendario: [{persona, dal, al, tipo}]."""
    oggi = oggi or dt.date.today()
    fine = oggi + dt.timedelta(days=giorni)
    out = []
    for r in richieste.elenca(TIPO, stati=["Approvata"], path=path):
        d = r["dati"]
        try:
            if _d(d["al"]) >= oggi and _d(d["dal"]) <= fine:
                out.append({"persona": r["utente"], "dal": str(_d(d["dal"])), "al": str(_d(d["al"])), "tipo": d.get("tipo", "Assenza")})
        except (KeyError, ValueError):
            continue
    return out
