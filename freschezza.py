"""
freschezza.py - Da quanto tempo i dati di ogni strumento non vengono salvati. Un semaforo costruito su dati vecchi sembra credibile
ma mente: qui si vede subito cosa e' fermo e di chi e' la mano che l'ha toccato per ultima. Senza Streamlit, quindi testabile.
"""
import datetime as dt

# giorni oltre i quali i dati si considerano «da aggiornare» (giallo); oltre il doppio: rosso
SOGLIE_GG = {"rp": 3, "sc": 7, "bk": 7, "oa": 7, "gt": 7, "sl": 15, "ga": 15, "rc": 7, "of": 15, "lg": 15, "fo": 30, "sx": 30, "mz": 30, "og": 30, "ru": 90, "sa": 15, "pr": 3, "mt": 7, "vr": 14, "ad": 30}
NOMI = {"rp": "Rapportini", "sc": "Scadenzario", "bk": "Riconciliazione bancaria", "oa": "Ordini e approvazioni", "gt": "Cronoprogramma", "sl": "SAL e contabilità lavori", "ga": "Gare e offerte",
        "lg": "Studio legale", "fo": "Fornitori", "sx": "Sicurezza", "mz": "Parco mezzi", "og": "Organico", "ru": "Rubrica e cantieri", "rc": "Registro commerciale", "of": "Offerta e finanziamenti", "sa": "Subappalti", "pr": "Presenze e ore", "mt": "Materiali e magazzino", "vr": "Verbali e riunioni", "ad": "Archivio documenti"}


def _data(ts):
    try:
        return dt.datetime.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def valuta(ultimi, adesso=None, moduli=None):
    """[{modulo, nome, giorni, stato, autore, soglia}] ordinato dal piu' fermo. stato: ok / warn / bad / nd (mai salvato)."""
    adesso = adesso or dt.datetime.now(dt.timezone.utc)
    out = []
    for m, soglia in SOGLIE_GG.items():
        if moduli is not None and m not in moduli:
            continue
        rec = (ultimi or {}).get(m)
        d = _data(rec[0]) if rec else None
        if d is None:
            out.append({"modulo": m, "nome": NOMI[m], "giorni": None, "stato": "nd", "autore": "", "soglia": soglia})
            continue
        g = max(0, (adesso - d).days)
        out.append({"modulo": m, "nome": NOMI[m], "giorni": g, "stato": "ok" if g <= soglia else ("warn" if g <= 2 * soglia else "bad"), "autore": rec[1], "soglia": soglia})
    ordine = {"bad": 0, "warn": 1, "nd": 2, "ok": 3}
    return sorted(out, key=lambda r: (ordine[r["stato"]], -(r["giorni"] or 0), r["nome"]))


def fermi(righe):
    """Solo quelli da aggiornare (mai salvato non conta come fermo: lo strumento puo' non essere in uso)."""
    return [r for r in righe if r["stato"] in ("warn", "bad")]


def frase(r):
    if r.get("testo"):                                        # righe con un testo gia' pronto (es. il prezziario: scade a una data, non dopo N giorni)
        return r["testo"]
    chi = f" (ultimo: {r['autore']})" if r["autore"] else ""
    return f"{r['nome']}: fermo da {r['giorni']} giorni{chi}, di solito si aggiorna ogni {r['soglia']}"
