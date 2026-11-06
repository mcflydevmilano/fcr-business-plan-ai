"""
ns.py - Note spese e trasferte: la persona registra la spesa con la foto dello scontrino, il responsabile approva, l'amministrazione ha il riepilogo del mese.
Senza Streamlit, quindi testabile.
"""
import datetime as dt
import io
import zipfile

import richieste
import storage

TIPO = "ns"
CATEGORIE = ["Carburante", "Pedaggi e parcheggi", "Pasti", "Alloggio", "Treno, aereo, taxi", "Materiale e attrezzatura", "Rimborso chilometrico", "Altro"]
STATI = ["In attesa", "Approvata", "Respinta", "Rimborsata", "Annullata"]
PAGATO = ["Di tasca mia (da rimborsare)", "Carta aziendale (non da rimborsare)"]
NOME_CFG = "note_spese_cfg"
CFG_BASE = {"tariffa_km": 0.40, "approvatori": []}


def normalizza_cfg(raw):
    c = {"tariffa_km": CFG_BASE["tariffa_km"], "approvatori": []}
    raw = raw if isinstance(raw, dict) else {}
    try:
        c["tariffa_km"] = round(min(max(float(raw.get("tariffa_km", c["tariffa_km"])), 0.0), 5.0), 4)
    except (TypeError, ValueError):
        pass
    c["approvatori"] = sorted({" ".join(str(x).split()).lower() for x in (raw.get("approvatori") or []) if str(x).strip()})
    return c


def carica_cfg(path=None):
    try:
        return normalizza_cfg(storage.carica_pratica(NOME_CFG, path, modulo="cfg"))
    except Exception:
        return normalizza_cfg({})


def salva_cfg(cfg, autore="", path=None):
    storage.salva_pratica(NOME_CFG, normalizza_cfg(cfg), path, autore=autore, modulo="cfg")


def importo_km(km, tariffa):
    return round(max(0.0, float(km or 0)) * max(0.0, float(tariffa or 0)), 2)


def prepara(dati, tariffa_km, oggi=None, n_allegati=0):
    """(dati puliti, errore). L'importo del rimborso chilometrico si calcola da km e tariffa; per le altre categorie serve la ricevuta salvo spiegazione."""
    oggi = oggi or dt.date.today()
    d = {k: str(dati.get(k) or "").strip() for k in ("categoria", "cantiere", "descrizione", "pagato")}
    if d["categoria"] not in CATEGORIE:
        return None, "Scegli la categoria."
    try:
        data = dt.date.fromisoformat(str(dati.get("data"))[:10])
    except ValueError:
        return None, "Indica la data della spesa."
    if data > oggi:
        return None, "La data della spesa è nel futuro."
    if (oggi - data).days > 400:
        return None, "La spesa è troppo vecchia: parlane con l'amministrazione."
    d["data"] = str(data)
    d["pagato"] = d["pagato"] if d["pagato"] in PAGATO else PAGATO[0]
    if d["categoria"] == "Rimborso chilometrico":
        km = float(dati.get("km") or 0)
        if km <= 0:
            return None, "Indica i chilometri percorsi."
        if len(d["descrizione"]) < 5:
            return None, "Scrivi il percorso (da dove a dove) e il motivo."
        d.update(km=km, tariffa_km=float(tariffa_km), importo=importo_km(km, tariffa_km), senza_ricevuta=False)
        d["pagato"] = PAGATO[0]
    else:
        imp = float(dati.get("importo") or 0)
        if imp <= 0:
            return None, "Indica l'importo."
        if imp > 100000:
            return None, "Importo non valido."
        senza = bool(dati.get("senza_ricevuta"))
        if not n_allegati and not senza:
            return None, "Allega la foto dello scontrino o della fattura, oppure spunta «Non ho la ricevuta»."
        if senza and len(d["descrizione"]) < 8:
            return None, "Senza ricevuta spiega bene cosa è stato pagato e perché."
        d.update(importo=round(imp, 2), senza_ricevuta=senza, km=0.0, tariffa_km=0.0)
    return d, ""


def da_rimborsare(r):
    d = r["dati"]
    return d.get("pagato", PAGATO[0]) == PAGATO[0] and r["stato"] in ("Approvata", "In attesa")


def del_mese(lista, anno, mese, stati=("Approvata", "Rimborsata")):
    return [r for r in lista if r["stato"] in stati and str(r["dati"].get("data", ""))[:7] == f"{anno}-{mese:02d}"]


def riepilogo(lista):
    """Tabelle per l'amministrazione: per persona, per cantiere, per categoria (importi in euro)."""
    def somma(chiave):
        t = {}
        for r in lista:
            k = chiave(r) or "(non indicato)"
            x = t.setdefault(k, {"n": 0, "totale": 0.0, "da_rimborsare": 0.0})
            x["n"] += 1
            x["totale"] += r["dati"]["importo"]
            if r["dati"].get("pagato", PAGATO[0]) == PAGATO[0] and r["stato"] != "Rimborsata":
                x["da_rimborsare"] += r["dati"]["importo"]
        return [{"Voce": k, "Spese": v["n"], "Totale €": round(v["totale"], 2), "Da rimborsare €": round(v["da_rimborsare"], 2)} for k, v in sorted(t.items(), key=lambda kv: -kv[1]["totale"])]
    return {"persone": somma(lambda r: r["utente"]), "cantieri": somma(lambda r: r["dati"].get("cantiere")), "categorie": somma(lambda r: r["dati"]["categoria"]),
            "totale": round(sum(r["dati"]["importo"] for r in lista), 2)}


def righe_dettaglio(lista):
    return [{"Data": r["dati"]["data"], "Persona": r["utente"], "Categoria": r["dati"]["categoria"], "Cantiere": r["dati"].get("cantiere", ""), "Descrizione": r["dati"].get("descrizione", ""),
             "Importo €": r["dati"]["importo"], "Km": r["dati"].get("km") or "", "Pagato con": r["dati"].get("pagato", ""), "Ricevuta": "no" if r["dati"].get("senza_ricevuta") else "sì",
             "Stato": r["stato"], "Deciso da": r["deciso_da"], "N.": r["id"]} for r in sorted(lista, key=lambda r: (r["dati"]["data"], r["id"]))]


def zip_scontrini(lista, path=None):
    """Archivio .zip con le foto e i PDF delle spese indicate, nominati per data, persona e categoria."""
    buf = io.BytesIO()
    n = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for r in lista:
            for i, (nome, _tipo, dati) in enumerate(richieste.allegati(r["id"], path), start=1):
                ext = nome.rsplit(".", 1)[-1].lower() if "." in nome else "jpg"
                base = f"{r['dati']['data']}_{r['utente']}_{r['dati']['categoria'].split(',')[0]}_{r['id']}_{i}".replace(" ", "-")
                z.writestr(f"{base}.{ext}", dati)
                n += 1
    return buf.getvalue(), n
