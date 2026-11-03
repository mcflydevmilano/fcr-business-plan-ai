"""
sk.py - Scheda cantiere: per ogni cantiere della Rubrica mette insieme in un solo posto entrate e uscite, fatture, SAL, costi di materiali, personale,
mezzi e subappalti, rapportini e segnalazioni. Non inserisce dati: legge quelli degli altri strumenti, quindi non c'e' niente da compilare due volte.
Deterministico e senza Streamlit.

Il cantiere di ogni riga si riconosce dal nome, dal codice (CAN-2026-001) o dal «codice in altro sistema» scritti nella Rubrica, senza badare a maiuscole.
Quello che non corrisponde a nessun cantiere della Rubrica finisce in schede «Non in Rubrica», cosi' nulla sparisce e si vede cosa correggere.
"""
import datetime as dt

import bk
import mc
import rp
import sa
import ru
import sc
import sl
from core import to_float

COSTI_ALTRI = "Altri costi (inseriti in SAL)"


def _k(s):
    return " ".join(str(s or "").lower().split())


def indice(cantieri):
    """{nome o codice minuscolo: codice} per riconoscere a quale cantiere appartiene una riga."""
    idx = {}
    for c in cantieri:
        for v in (c.get("Codice"), c.get("Cantiere"), c.get("Esterno")):
            if _k(v):
                idx.setdefault(_k(v), c["Codice"])
    return idx


def _scheda(c, in_rubrica=True):
    return {"Codice": c.get("Codice", ""), "Cantiere": c.get("Cantiere", ""), "Cliente": c.get("Cliente", ""), "Responsabile": c.get("Responsabile", ""),
            "Stato": c.get("Stato", "") if in_rubrica else "Non in Rubrica", "in_rubrica": in_rubrica,
            "attive": [], "passive": [], "costi": {}, "sal": {"emessi": 0, "incassato": 0.0}, "contratto": None,
            "subappalti": [], "conti": [], "rapporti": 0, "ore": 0.0, "ultimo_rapporto": None, "segnalazioni_aperte": 0, "da": set()}


def _somma_fatture(righe, oggi):
    tot = sum(x["Importo"] for x in righe)
    reg = sum(x["Saldato"] for x in righe)
    scaduto = sum(x["Importo"] - x["Saldato"] for x in righe if x["Importo"] - x["Saldato"] > 0.005 and (sc.data_da(x["Scadenza"]) or oggi) < oggi)
    return {"n": len(righe), "totale": tot, "regolato": reg, "residuo": tot - reg, "scaduto": scaduto}


def calcola_sk(payloads, oggi=None):
    """
    payloads: {'ru': {...cantieri}, 'sc': {...docs}, 'rp': {...rapp, segn}, 'sl', 'sa', 'pr', 'mt', 'mz'} (quelli che esistono).
    Restituisce {'schede': [...], 'avvisi': [...], 'kpi': {...}}: le schede dei cantieri vivi per prime.
    """
    p = payloads or {}
    oggi = oggi or dt.date.today()
    cant, avvisi = ru.normalizza_cantieri((p.get("ru") or {}).get("cantieri"))
    idx = indice(cant)
    schede = {c["Codice"]: _scheda(c) for c in cant}

    def dove(nome, strumento):
        k = _k(nome)
        if not k:
            return None
        cod = idx.get(k)
        if cod:
            return schede[cod]
        sch = schede.setdefault("?" + k, _scheda({"Cantiere": str(nome).strip()}, in_rubrica=False))
        sch["da"].add(strumento)
        return sch

    # fatture (Scadenzario)
    if p.get("sc"):
        docs, _ = sc.normalizza_documenti(p["sc"].get("docs"))
        for d in docs:
            s = dove(d["Cantiere"], "Scadenzario")
            if s is not None:
                s["attive" if d["Tipo"] == "Attiva" else "passive"].append(d)

    # contratto, avanzamento e SAL (SAL e contabilita' lavori)
    if p.get("sl"):
        m = mc.calcola_mc(p, oggi=oggi)
        if m:
            for c in m["commesse"]:
                s = dove(c["Commessa"], "SAL")
                if s is not None:
                    s["contratto"] = {"contratto": c["Contratto totale"], "avanzamento": c["Avanzamento %"], "margine_finale_pct": c["Margine finale %"],
                                      "margine_atteso_pct": c["Margine atteso %"], "costi_a_finire": c["Costi a finire (EAC)"], "stato": c["Stato"]}
        com, _ = sl.normalizza_commesse(p["sl"].get("commesse"))
        nomi = {c["Commessa"] for c in com}
        sal, _ = sl.normalizza_sal(p["sl"].get("sal"), nomi)
        for x in sal:
            s = dove(x["Commessa"], "SAL")
            if s is not None:
                s["sal"]["emessi"] += 1
                s["sal"]["incassato"] += x["Incassato"]
        costi_sl, _ = sl.normalizza_costi(p["sl"].get("costi"), nomi)
        for x in costi_sl:
            if not mc._marcata(x):
                s = dove(x["Commessa"], "SAL")
                if s is not None:
                    s["costi"][COSTI_ALTRI] = s["costi"].get(COSTI_ALTRI, 0.0) + x["Importo"]

    # conti correnti del cantiere (Riconciliazione bancaria): saldo, debiti e previsione
    if p.get("bk"):
        conti_bk, _ = bk.normalizza_conti(p["bk"].get("conti"))
        mov_bk, _ = bk.normalizza_movimenti(p["bk"].get("movimenti"))
        deb_bk, _ = bk.normalizza_debiti(p["bk"].get("debiti"), conti_bk)
        docs_bk = sc.normalizza_documenti((p.get("sc") or {}).get("docs"))[0] if p.get("sc") else []
        for x in bk.prospetti(conti_bk, mov_bk, docs_bk, deb_bk, oggi, alias=idx)["conti"]:
            s = dove(x["conto"]["Cantiere"], "Conti correnti")
            if s is not None:
                s["conti"].append(x)

    # subappaltatori del cantiere (uno stesso subappaltatore puo' lavorare su piu' cantieri: ogni contratto va al suo)
    if p.get("sa"):
        con, _ = sa.normalizza_contratti(p["sa"].get("contratti"))
        sal_sa, _ = sa.normalizza_sal(p["sa"].get("sal"), con)
        doc_sa, _ = sa.normalizza_doc(p["sa"].get("doc"), {x["Subappaltatore"] for x in con})
        o_sa = sa.calcola_sa(con, sal_sa, doc_sa, p["sa"].get("params") or {})
        altri = {}
        for d in o_sa["contratti"]:
            altri.setdefault(d["Subappaltatore"], []).append(d["Commessa"])
        for d in o_sa["contratti"]:
            s = dove(d["Commessa"], "Subappalti")
            if s is not None:
                s["subappalti"].append(dict(d, Altri_cantieri=", ".join(c for c in altri[d["Subappaltatore"]] if c != d["Commessa"])))

    # costi diretti: subappalti, ore, materiali, mezzi
    for fonte, righe in mc.righe_fonti(p, oggi).items():
        for x in righe:
            s = dove(x["Commessa"], mc.FONTI[fonte])
            if s is not None:
                s["costi"][mc.FONTI[fonte]] = s["costi"].get(mc.FONTI[fonte], 0.0) + x["Importo"]

    # rapportini e segnalazioni
    if p.get("rp"):
        rapp, _ = rp.normalizza_rapp(p["rp"].get("rapp"))
        for r in rapp:
            s = dove(r["Cantiere"], "Rapportini")
            if s is None:
                continue
            d = sc.data_da(r["Data"])
            s["rapporti"] += 1
            s["ore"] += r["Ore"]
            if d and (s["ultimo_rapporto"] is None or d > s["ultimo_rapporto"]):
                s["ultimo_rapporto"] = d
        segn, _ = rp.normalizza_segn(p["rp"].get("segn"))
        for z in segn:
            if z["Stato"] != "Chiusa":
                s = dove(z["Cantiere"], "Rapportini")
                if s is not None:
                    s["segnalazioni_aperte"] += 1

    out = []
    for s in schede.values():
        costi_tot = sum(s["costi"].values())
        att, pas = _somma_fatture(s["attive"], oggi), _somma_fatture(s["passive"], oggi)
        s["entrate"] = att
        s["uscite"] = pas
        s["costi_totali"] = costi_tot
        s["fatturato"] = att["totale"]
        s["margine_corrente"] = att["totale"] - costi_tot
        s["cassa"] = att["regolato"] - pas["regolato"]
        s["giorni_senza_rapporto"] = rp.giorni_lavorativi(s["ultimo_rapporto"], oggi) if s["ultimo_rapporto"] else None
        s["vivo"] = s["in_rubrica"] and s["Stato"] in ru.STATI_VIVI
        s["da"] = sorted(s["da"])
        out.append(s)
    out.sort(key=lambda s: (not s["vivo"], not s["in_rubrica"], s["Codice"] or s["Cantiere"].lower()))
    for s in out:
        if not s["in_rubrica"]:
            avvisi.append(f"«{s['Cantiere']}» compare in {', '.join(s['da'])} ma non è nella Rubrica dei cantieri: aggiungilo lì o correggi il nome, così i dati finiscono nella sua scheda.")
    vivi = [s for s in out if s["vivo"]]
    kpi = {"cantieri": len([s for s in out if s["in_rubrica"]]), "vivi": len(vivi), "non_in_rubrica": len([s for s in out if not s["in_rubrica"]]),
           "fatturato_vivi": sum(s["fatturato"] for s in vivi), "costi_vivi": sum(s["costi_totali"] for s in vivi),
           "da_incassare_vivi": sum(s["entrate"]["residuo"] for s in vivi), "da_pagare_vivi": sum(s["uscite"]["residuo"] for s in vivi)}
    return {"schede": out, "avvisi": avvisi, "kpi": kpi}


def riepilogo_documenti(docs, cantieri, oggi=None):
    """
    Lo Scadenzario diviso per cantiere: una riga per cantiere (vivi per primi), poi i nomi non in Rubrica, poi le fatture senza cantiere, e il TOTALE.
    `docs` sono i documenti gia' normalizzati da sc.normalizza_documenti. Restituisce {'righe': [...], 'totale': {...}, 'docs': {etichetta: [documenti]}}.
    """
    oggi = oggi or dt.date.today()
    idx = indice(cantieri)
    info = {c["Codice"]: c for c in cantieri}
    gruppi = {}

    def gruppo(chiave, nome, stato, codice=""):
        return gruppi.setdefault(chiave, {"Codice": codice, "Cantiere": nome, "Stato": stato, "docs": []})
    for c in cantieri:
        if c.get("Stato") in ru.STATI_VIVI:
            gruppo(c["Codice"], c["Cantiere"], c["Stato"], c["Codice"])
    for d in docs:
        k = _k(d.get("Cantiere"))
        cod = idx.get(k)
        if cod:
            gruppo(cod, info[cod]["Cantiere"], info[cod]["Stato"], cod)["docs"].append(d)
        elif k:
            gruppo("?" + k, str(d["Cantiere"]).strip(), "Non in Rubrica")["docs"].append(d)
        else:
            gruppo("", "(senza cantiere)", "")["docs"].append(d)

    def ordine(g):
        return (g["Stato"] == "", g["Stato"] == "Non in Rubrica", g["Stato"] not in ru.STATI_VIVI, g["Codice"] or g["Cantiere"].lower())
    righe, per_doc = [], {}
    for g in sorted(gruppi.values(), key=ordine):
        att = _somma_fatture([d for d in g["docs"] if d["Tipo"] == "Attiva"], oggi)
        pas = _somma_fatture([d for d in g["docs"] if d["Tipo"] == "Passiva"], oggi)
        etichetta = f"{g['Codice'] + ' · ' if g['Codice'] else ''}{g['Cantiere']}"
        righe.append({"Cantiere": etichetta, "Stato": g["Stato"], "Fatture": len(g["docs"]), "Da incassare": att["residuo"], "Di cui scaduto": att["scaduto"],
                      "Da pagare": pas["residuo"], "Pagamenti scaduti": pas["scaduto"], "Saldo netto": att["residuo"] - pas["residuo"],
                      "Fatturato": att["totale"], "Incassato": att["regolato"], "Fatture fornitori": pas["totale"], "Pagato": pas["regolato"]})
        per_doc[etichetta] = g["docs"]
    chiavi = ("Fatture", "Da incassare", "Di cui scaduto", "Da pagare", "Pagamenti scaduti", "Saldo netto", "Fatturato", "Incassato", "Fatture fornitori", "Pagato")
    tot = {k: sum(r[k] for r in righe) for k in chiavi}
    return {"righe": righe, "totale": tot, "docs": per_doc}


def cantieri_per_rapportino(cantieri):
    """Nomi dei cantieri vivi proposti nel rapportino (dalla Rubrica)."""
    return [c["Cantiere"] for c in ru.cantieri_vivi(ru.normalizza_cantieri(cantieri)[0])]
