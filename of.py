"""
of.py - Offerta e finanziamenti: dal computo all'offerta, senza Streamlit (testabile).

Catena: computo (voci + sconti, ipotesi A/B) -> parcelle D.Lgs. 36/2023 (V*P*G*SQ) -> QTE -> finanziamento (rata francese)
con riparto per millesimi, recupero fiscale e risparmio energetico -> confronto di mercato -> richieste di finanziamento
(Condominio e condomino) con la copertura dell'appalto.
"""
import io
import json
import math
import os
import re

import openpyxl

_QUI = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------------------------------------------------------------- tabelle D.Lgs. 36/2023
CATEGORIE = {"EDILIZIA": "Edilizia", "STRUTTURE": "Strutture", "IMPIANTI": "Impianti", "VIABILITA": "Infrastrutture per la mobilità",
             "IDRAULICA": "Idraulica", "TIC": "Tecnologie dell'informazione", "PAESAGGIO": "Paesaggio, ambiente, agroalimentare",
             "TERRITORIO": "Territorio e urbanistica"}
FASI = {"a.0": "a.0 Pianificazione e programmazione", "aI": "a.I Studi di fattibilità", "aII": "a.II Stime e valutazioni", "aIII": "a.III Rilievi, studi e analisi",
        "aIV": "a.IV Piani economici", "bI": "b.I Fattibilità tecnico-economica", "bII": "b.II Progetto definitivo", "bIII": "b.III Progetto esecutivo",
        "cI": "c.I Esecuzione dei lavori", "dI": "d.I Verifiche e collaudi", "eI": "e.I Monitoraggi"}
PRESET = {   # prestazioni tipiche proposte (si possono cambiare una per una)
    "Progetto esecutivo": ["QbIII.01", "QbIII.02", "QbIII.03", "QbIII.04", "QbIII.05", "QbIII.07"],
    "Direzione lavori e sicurezza": ["QcI.01", "QcI.02", "QcI.11", "QcI.12"],
}


def _carica():
    try:
        with open(os.path.join(_QUI, "parcelle_z.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"opere": [], "prest": []}


Z = _carica()
OPERE = Z["opere"]            # [{cat, id, desc, g}]
PRESTAZIONI = Z["prest"]      # [{fase, cod, desc, q:{CAT: Q}}]


def opere_di(cat):
    return [o for o in OPERE if o["cat"] == cat]


def grado_g(id_opera):
    for o in OPERE:
        if o["id"] == id_opera:
            return float(o["g"])
    return 0.0


def parametro_p(v):
    """P = 20,411% sotto 25.000 euro, altrimenti 0,03 + 10 / V^0,4 (allegato I.13)."""
    v = float(v or 0)
    if v <= 0:
        return 0.0
    return 0.20411 if v < 25000 else 0.03 + 10 / math.pow(v, 0.4)


def pct_spese(v_tot):
    """% spese ed oneri accessori sul compenso: 25% fino a 1 milione, poi scende linearmente fino al 10% a 25 milioni (5% oltre)."""
    v = float(v_tot or 0)
    if v > 25_000_000:
        return 0.05
    if v < 1_000_000:
        return 0.25
    return 0.25 - (v - 1_000_000) * (0.15 / 24_000_000)


def somma_q(cat, codici):
    sel = set(codici or [])
    return sum(p["q"].get(cat, 0.0) for p in PRESTAZIONI if p["cod"] in sel)


def parcella(opere, codici, bim=False, sconto_pct=0.0, spese_pct=None):
    """opere: [{cat, V, id}] -> compenso per categoria e totale.
    Compenso netto = somma su categorie di V*P*G*SQ. Poi: +10% BIM, + spese ed oneri accessori (% su compenso), - sconto."""
    righe, tot_v = [], 0.0
    per_fase = {f: 0.0 for f in FASI}
    for o in opere or []:
        cat, v, g = o.get("cat"), float(o.get("V") or 0), grado_g(o.get("id"))
        if not cat or v <= 0 or g <= 0:
            continue
        p, q = parametro_p(v), somma_q(cat, codici)
        righe.append({"cat": cat, "V": v, "P": p, "G": g, "SQ": q, "compenso": v * p * g * q})
        tot_v += v
        for f in FASI:
            qf = sum(pr["q"].get(cat, 0.0) for pr in PRESTAZIONI if pr["cod"] in set(codici or []) and pr["fase"] == f)
            per_fase[f] += v * p * g * qf
    e = sum(r["compenso"] for r in righe)
    f_bim = e * 0.10 if bim else 0.0
    sp = pct_spese(tot_v) if spese_pct is None else float(spese_pct)
    spese = sp * (e + f_bim)
    sc = -float(sconto_pct or 0) * (e + f_bim + spese)
    return {"righe": righe, "V": tot_v, "compenso": e, "bim": f_bim, "spese_pct": sp, "spese": spese, "sconto": sc,
            "totale": e + f_bim + spese + sc, "per_fase": {f: v for f, v in per_fase.items() if v}}


# ----------------------------------------------------------------------------------------------------------------------- computo A/B
COL_VOCI = ["Cap", "Cod", "Descrizione", "UM", "Quantita", "Prezzo", "Ipotesi"]
COL_SCONTI = ["Descrizione", "Ipotesi", "Importo"]
IPOTESI = ("", "A", "B")          # "" = voce comune a entrambe


def _f(x):
    try:
        if x is None or (isinstance(x, str) and not x.strip()):
            return 0.0
        return float(x)
    except Exception:
        return 0.0


def importo_voce(v):
    return _f(v.get("Quantita")) * _f(v.get("Prezzo"))


def _ip(x):
    x = str(x or "").strip().upper()
    return x if x in ("A", "B") else ""


def totali_computo(voci, sconti):
    """Imponibile per ipotesi: voci comuni + voci dell'ipotesi + sconti comuni + sconti dell'ipotesi."""
    com = sum(importo_voce(v) for v in voci or [] if not _ip(v.get("Ipotesi")))
    sc_com = sum(_f(s.get("Importo")) for s in sconti or [] if not _ip(s.get("Ipotesi")))
    out = {"comune": com, "sconti_comuni": sc_com}
    for h in ("A", "B"):
        voci_h = sum(importo_voce(v) for v in voci or [] if _ip(v.get("Ipotesi")) == h)
        sc_h = sum(_f(s.get("Importo")) for s in sconti or [] if _ip(s.get("Ipotesi")) == h)
        out[h] = {"voci": voci_h, "sconti": sc_h, "imponibile": com + sc_com + voci_h + sc_h}
    out["differenza"] = out["A"]["imponibile"] - out["B"]["imponibile"]
    return out


def per_capitolo(voci):
    d = {}
    for v in voci or []:
        k = (str(v.get("Cap") or "-"), _ip(v.get("Ipotesi")))
        d[k] = d.get(k, 0.0) + importo_voce(v)
    return d


def import_cme(dati):
    """Legge il computo dal foglio «Table 1» (capitoli A-E, ipotesi A/B) e gli sconti dal «Foglio1». `dati`: bytes o percorso."""
    wb = openpyxl.load_workbook(io.BytesIO(dati) if isinstance(dati, (bytes, bytearray)) else dati, data_only=True)
    nomi = {n.lower(): n for n in wb.sheetnames}
    voci, sconti = [], []
    ws = wb[nomi.get("table 1", wb.sheetnames[-1])]
    cap, ip = "", ""
    for r in ws.iter_rows(min_row=1):
        a, b, c, d, e, f, g = (r[i].value if len(r) > i else None for i in range(7))
        testo = str(c or "").strip()
        if testo.upper().startswith("IPOTESI A"):
            ip = "A"
            continue
        if testo.upper().startswith("IPOTESI B"):
            ip = "B"
            continue
        if testo.upper().startswith("INTERVENTI COMUNI") and d is None and g is None:
            ip = ""
            continue
        titolo_cap = a and str(a).strip().isalpha() and len(str(a).strip()) == 1 and testo and d is None and g is None and b is None
        if titolo_cap:
            if testo.upper().startswith(("INTERVENTI COMUNI", "TINTEGGIATURA", "ALTRE", "CANTIERIZZ", "DEMOLIZ")) or not testo.upper().startswith("ISOLAMENTI"):
                ip = ""
            cap = str(a).strip().upper()
            continue
        if testo and d is not None and isinstance(g, (int, float)):
            q, p = _f(e), _f(f)
            if not q and not p:        # a corpo: quantita 1, prezzo = importo
                q, p = 1.0, float(g)
            voci.append({"Cap": cap or (str(a).strip().upper() if a else ""), "Cod": str(b or "").strip(), "Descrizione": " ".join(testo.split()), "UM": str(d).strip(),
                         "Quantita": q, "Prezzo": p, "Ipotesi": ip})
    if "foglio1" in nomi:
        w1 = wb[nomi["foglio1"]]
        for r in w1.iter_rows(min_row=1):
            lab, val = r[0].value, r[1].value if len(r) > 1 else None
            if isinstance(lab, str) and isinstance(val, (int, float)) and val < 0:
                m = re.search(r"ipotesi\s*([AB])", lab, re.I)
                sconti.append({"Descrizione": lab.strip(), "Ipotesi": m.group(1).upper() if m else "", "Importo": float(val)})
    return voci, sconti


# ----------------------------------------------------------------------------------------------------------------------- QTE
def qte(imponibile, parcella_lorda, rl_lorda, iva_lavori=0.10, cassa=0.04, iva_prof=0.22):
    """Quadro tecnico economico come nel foglio «Quadro economico»: lavori + IVA, parcella e responsabile lavori con cassa e IVA."""
    imp = float(imponibile or 0)
    iva_l = imp * iva_lavori
    lav_iva = imp + iva_l

    def prof(lorda):
        lorda = float(lorda or 0)
        cs = lorda * cassa
        imponibile_p = lorda + cs
        iva = imponibile_p * iva_prof
        return {"lorda": lorda, "cassa": cs, "imponibile": imponibile_p, "iva": iva, "totale": imponibile_p + iva}

    p, r = prof(parcella_lorda), prof(rl_lorda)
    spese = p["totale"] + r["totale"]
    return {"imponibile": imp, "iva_lavori": iva_l, "lavori_iva": lav_iva, "parcella": p, "rl": r, "spese": spese, "totale": lav_iva + spese,
            "incidenza_prof": p["imponibile"] / imp if imp else 0.0, "tot_imponibile": imp + p["imponibile"] + r["imponibile"],
            "tot_iva": iva_l + p["iva"] + r["iva"]}


# ----------------------------------------------------------------------------------------------------------------------- finanziamento
def rata_mensile(capitale, mesi, tan=0.06):
    c, n, i = float(capitale or 0), int(mesi or 0), float(tan or 0) / 12
    if c <= 0 or n <= 0:
        return 0.0
    return c / n if i == 0 else c * i / (1 - math.pow(1 + i, -n))


def piano(capitale, anni, tan=0.06):
    mesi = int(round(float(anni) * 12))
    r = rata_mensile(capitale, mesi, tan)
    return {"anni": anni, "mesi": mesi, "rata": r, "interessi": r * mesi - float(capitale or 0), "totale": r * mesi}


def recupero_fiscale(base, pct, anni=10):
    """Detrazione totale e quota annuale (distribuita su `anni`)."""
    tot = float(base or 0) * float(pct or 0) / 100.0
    return {"totale": tot, "annuo": tot / anni if anni else 0.0, "mensile": tot / (anni * 12) if anni else 0.0}


def simulazione(capitale, base_detrazione, durate=(3, 5, 10), tan=0.06, detrazioni=(50, 36), anni_detrazione=10, risparmio_annuo=0.0):
    """Per ogni durata: rata, interessi, totale e, per ogni % di detrazione, il costo reale e l'impatto mensile del condominio.
    impatto mensile = rata - recupero fiscale mensile - risparmio energetico mensile (calcolati sull'intero edificio, poi ripartiti per millesimi)."""
    out = []
    ris_m = float(risparmio_annuo or 0) / 12
    for a in durate:
        pn = piano(capitale, a, tan)
        riga = dict(pn)
        for d in detrazioni:
            rec = recupero_fiscale(base_detrazione, d, anni_detrazione)
            riga[f"rec{int(d)}"] = rec["totale"]
            riga[f"costo_reale{int(d)}"] = pn["totale"] - rec["totale"] - ris_m * 12 * anni_detrazione
            riga[f"impatto{int(d)}"] = pn["rata"] - rec["mensile"] - ris_m
        out.append(riga)
    return out


COL_UNITA = ["Unita", "Proprietario", "Millesimi", "Mq"]


def normalizza_unita(righe):
    out = []
    for r in righe or []:
        m = _f(r.get("Millesimi"))
        if not str(r.get("Unita") or "").strip() and not m:
            continue
        out.append({"Unita": str(r.get("Unita") or "").strip(), "Proprietario": str(r.get("Proprietario") or "").strip(), "Millesimi": m, "Mq": _f(r.get("Mq"))})
    return out


def import_millesimi(dati):
    """Tabella millesimale da Excel: cerca le colonne Unita/Interno, Proprietario, Millesimi, Mq (anche con nomi simili)."""
    wb = openpyxl.load_workbook(io.BytesIO(dati), data_only=True)
    ws = wb.worksheets[0]
    righe = list(ws.iter_rows(values_only=True))
    idx = next((i for i, r in enumerate(righe[:20]) if sum(1 for c in r if c not in (None, "")) >= 2 and any(isinstance(c, str) and "millesim" in c.lower() for c in r)), None)
    if idx is None:
        raise ValueError("Non trovo una colonna «Millesimi» nelle prime righe del foglio.")
    head = [str(c or "").lower() for c in righe[idx]]

    def col(*chiavi):
        return next((i for i, h in enumerate(head) if any(k in h for k in chiavi)), None)
    cu, cp, cm, cq = col("unit", "interno", "int.", "sub", "scala"), col("propriet", "condomin", "nomin", "intestat"), col("millesim"), col("mq", "m2", "superf")
    out = []
    for r in righe[idx + 1:]:
        mill = r[cm] if cm is not None and cm < len(r) else None
        if not isinstance(mill, (int, float)) or any(isinstance(c, str) and c.strip().lower().startswith("total") for c in r):
            continue
        out.append({"Unita": str(r[cu]).strip() if cu is not None and r[cu] is not None else str(len(out) + 1),
                    "Proprietario": str(r[cp]).strip() if cp is not None and r[cp] is not None else "",
                    "Millesimi": float(mill), "Mq": _f(r[cq]) if cq is not None else 0.0})
    return out


def riparto(unita, importo_mensile):
    """Quota di ogni unita' di un importo mensile secondo i millesimi."""
    return [{**u, "quota": importo_mensile * u["Millesimi"] / 1000.0} for u in unita]


def totale_millesimi(unita):
    return sum(u["Millesimi"] for u in unita)


# ----------------------------------------------------------------------------------------------------------------------- mercato
COL_ANNUNCI = ["Fonte", "Zona", "Stato", "Mq", "Prezzo", "Link"]
STATI_IMM = ["Così com'è", "Efficientato"]


def mercato(annunci, ante=None, post=None):
    """Prezzi al m2 medi per stato dagli annunci inseriti; se non ci sono annunci si usano i valori ante/post indicati a mano."""
    acc = {s: [] for s in STATI_IMM}
    for a in annunci or []:
        mq, pr = _f(a.get("Mq")), _f(a.get("Prezzo"))
        s = str(a.get("Stato") or "").strip()
        if mq > 0 and pr > 0:
            k = "Efficientato" if s.lower().startswith("effic") else "Così com'è"
            acc[k].append(pr / mq)
    medie = {k: (sum(v) / len(v) if v else None) for k, v in acc.items()}
    a_ = medie["Così com'è"] if medie["Così com'è"] is not None else ante
    p_ = medie["Efficientato"] if medie["Efficientato"] is not None else post
    delta = (p_ - a_) if (a_ is not None and p_ is not None) else None
    return {"n": {k: len(v) for k, v in acc.items()}, "ante": a_, "post": p_, "delta": delta, "da_annunci": any(acc.values())}


# ----------------------------------------------------------------------------------------------------------------------- richieste di finanziamento
STATI_FIN = ["Da preparare", "Inserita", "In istruttoria", "Integrazioni richieste", "Approvata", "Erogata", "Rifiutata", "Ritirata"]
APPROVATI = {"Approvata", "Erogata"}
IN_CORSO = {"Da preparare", "Inserita", "In istruttoria", "Integrazioni richieste"}
NEGATIVI = {"Rifiutata", "Ritirata"}
TIPI_FIN = ["Condominio", "Condomino"]
COL_FIN = ["Tipo", "Unita", "Richiedente", "Istituto", "Lavori", "Richiesto", "Stato", "Deliberato", "Data richiesta", "Data esito", "Esito", "Documenti", "Note"]
QUOTA_MAX_CONDOMINO = 0.50        # fino al 50% del valore dei lavori sulle parti private


def normalizza_fin(righe):
    out = []
    for r in righe or []:
        d = {c: r.get(c) for c in COL_FIN}
        if not str(d.get("Tipo") or "").strip() and not _f(d.get("Richiesto")) and not str(d.get("Richiedente") or "").strip():
            continue
        d["Tipo"] = "Condomino" if str(d.get("Tipo") or "").lower().startswith("condomin") and not str(d.get("Tipo")).lower().startswith("condominio") else "Condominio"
        d["Stato"] = d["Stato"] if d.get("Stato") in STATI_FIN else "Da preparare"
        for c in ("Lavori", "Richiesto", "Deliberato"):
            d[c] = _f(d.get(c))
        for c in ("Unita", "Richiedente", "Istituto", "Data richiesta", "Data esito", "Esito", "Documenti", "Note"):
            d[c] = "" if d.get(c) is None or (isinstance(d.get(c), float) and math.isnan(d.get(c))) else str(d.get(c))
        out.append(d)
    return out


def copertura(totale_progetto, righe):
    """Quanto dell'appalto e' coperto: importi deliberati (Approvata/Erogata), in istruttoria, rifiutati. Per tipo e in totale."""
    righe = normalizza_fin(righe)
    avvisi = []
    out = {"totale": float(totale_progetto or 0), "tipi": {}}
    for t in TIPI_FIN:
        rr = [r for r in righe if r["Tipo"] == t]
        out["tipi"][t] = {"n": len(rr),
                          "approvato": sum(r["Deliberato"] or r["Richiesto"] for r in rr if r["Stato"] in APPROVATI),
                          "in_corso": sum(r["Richiesto"] for r in rr if r["Stato"] in IN_CORSO),
                          "rifiutato": sum(r["Richiesto"] for r in rr if r["Stato"] in NEGATIVI),
                          "n_approvate": sum(1 for r in rr if r["Stato"] in APPROVATI), "n_in_corso": sum(1 for r in rr if r["Stato"] in IN_CORSO),
                          "n_rifiutate": sum(1 for r in rr if r["Stato"] in NEGATIVI)}
    for r in righe:
        if r["Tipo"] == "Condomino" and r["Lavori"] > 0 and r["Richiesto"] > r["Lavori"] * QUOTA_MAX_CONDOMINO + 0.5:
            avvisi.append(f"{r['Unita'] or r['Richiedente']}: richiesta di {r['Richiesto']:,.0f} € oltre il 50% dei lavori privati ({r['Lavori'] * QUOTA_MAX_CONDOMINO:,.0f} €).".replace(",", "."))
        if r["Stato"] in APPROVATI and r["Deliberato"] and r["Deliberato"] > r["Richiesto"] > 0:
            avvisi.append(f"{r['Unita'] or r['Richiedente']}: importo deliberato superiore al richiesto.")
    ap = sum(v["approvato"] for v in out["tipi"].values())
    ic = sum(v["in_corso"] for v in out["tipi"].values())
    rf = sum(v["rifiutato"] for v in out["tipi"].values())
    tot = out["totale"]
    out.update({"approvato": ap, "in_corso": ic, "rifiutato": rf, "pct_approvato": ap / tot * 100 if tot else 0.0,
                "pct_potenziale": (ap + ic) / tot * 100 if tot else 0.0, "scoperto": max(tot - ap, 0.0), "avvisi": avvisi})
    return out


def euro(v, dec=0):
    s = f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"


# ----------------------------------------------------------------------------------------------------------------------- insieme dei calcoli
PARAMS_DEFAULT = {"tan": 0.06, "durate": [3, 5, 10], "detrazioni": [50, 36], "anni": 10, "risparmio_annuo": 0.0, "base_con_spese": False}
QTE_DEFAULT = {"iva_lavori": 0.10, "cassa": 0.04, "iva_prof": 0.22}
PARCELLE_DEFAULT = {"categorie": [{"cat": "EDILIZIA", "id": "E.06", "quota": 100.0}], "codici": PRESET["Progetto esecutivo"] + PRESET["Direzione lavori e sicurezza"],
                    "bim": False, "sconto_pct": 0.0, "manuale": {"A": 0.0, "B": 0.0}, "rl_importo": 0.0, "rl_pct": 0.0}


def parcella_opzione(imponibile, par, ipotesi):
    """Parcella lorda dell'opzione: importo manuale se indicato, altrimenti calcolo D.Lgs. 36/2023 con V = imponibile x quota di ogni categoria."""
    par = {**PARCELLE_DEFAULT, **(par or {})}
    man = float((par.get("manuale") or {}).get(ipotesi) or 0)
    if man > 0:
        return man, None
    opere = [{"cat": c["cat"], "V": imponibile * float(c.get("quota") or 0) / 100.0, "id": c["id"]} for c in par["categorie"]]
    r = parcella(opere, par["codici"], par.get("bim"), (par.get("sconto_pct") or 0) / 100.0)
    return r["totale"], r


def contesto(p):
    """Dal salvataggio (dict) a tutti i risultati: computo, parcelle, QTE, simulazioni, copertura. Usato da schermo, offerta e Cruscotto."""
    p = p or {}
    voci, sconti = p.get("voci") or [], p.get("sconti") or []
    tot = totali_computo(voci, sconti)
    opz_in = p.get("opzioni") or {}
    qp = {**QTE_DEFAULT, **(p.get("qte_par") or {})}
    par_f = {**PARAMS_DEFAULT, **(p.get("params") or {})}
    par_f["durate"] = [d for d in par_f["durate"] if d] or [5]
    unita = normalizza_unita(p.get("unita"))
    pr = p.get("parcelle") or {}
    opzioni, sim = {}, {}
    ha_ipotesi = any(_ip(v.get("Ipotesi")) for v in voci)
    for h in ("A", "B"):
        d = opz_in.get(h) or {}
        imp = float(d.get("imponibile_manuale") or 0) or (tot[h]["imponibile"] if ha_ipotesi or h == "A" else 0.0)
        if imp <= 0:
            continue
        lorda, dett = parcella_opzione(imp, pr, h)
        rl = (float(pr.get("rl_pct") or 0) / 100.0 * imp) if float(pr.get("rl_pct") or 0) > 0 else float(pr.get("rl_importo") or 0)
        q = qte(imp, lorda, rl, qp["iva_lavori"], qp["cassa"], qp["iva_prof"])
        opzioni[h] = {"nome": d.get("nome") or "", "desc": d.get("desc") or "", "imponibile": imp, "qte": q, "parcella_dett": dett}
        base = q["lavori_iva"] + (q["spese"] if par_f.get("base_con_spese") else 0)
        sim[h] = simulazione(q["totale"], base, par_f["durate"], par_f["tan"], par_f["detrazioni"], par_f["anni"], par_f["risparmio_annuo"])
    tp = max((o["qte"]["totale"] for o in opzioni.values()), default=0.0)
    sc = p.get("scenario") or {}
    scelta = sc.get("opzione") if sc.get("opzione") in opzioni else next(iter(opzioni), None)
    mm = p.get("mercato_manuale") or {}
    return {"pratica": p.get("pratica") or {}, "opzioni": opzioni, "qte_par": qp, "params": par_f, "sim": sim, "unita": unita, "computo": tot,
            "scenario": {"opzione": scelta, "anni": sc.get("anni") or par_f["durate"][-1], "detrazione": sc.get("detrazione") or par_f["detrazioni"][0]},
            "confronto": p.get("confronto") or [], "annunci": p.get("annunci") or [], "mq_esempio": p.get("mq_esempio") or 100,
            "mercato": mercato(p.get("annunci"), mm.get("ante") or None, mm.get("post") or None),
            "copertura": copertura(float(opzioni[scelta]["qte"]["totale"]) if scelta else tp, p.get("richieste"))}
