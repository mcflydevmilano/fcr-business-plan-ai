"""
pv.py - Computo metrico e preventivo: voci, costi diretti, spese generali, utile, oneri di sicurezza, sconto, IVA e margine.

Deterministico e senza Streamlit (testabile). L'AI, se usata, al massimo PROPONE voci e quantita': prezzi e costi unitari
vanno sempre verificati su prezzari o offerte dei fornitori (le stime dell'AI non sono prezzi di riferimento).

Modello (importi in EUR):
  Costo voce        = quantita' x (materiali + manodopera + noli/altro) unitari
  Costi diretti CD  = somma dei costi voce
  Spese generali    = CD x sg%                        Costo industriale CI = CD + spese generali
  Utile d'impresa   = CI x utile%                     Prezzo di listino PL = CI + utile = CD x (1 + sg) x (1 + utile)
  Sconto al cliente = PL x sconto%                    Prezzo lavori scontato PS = PL - sconto
  Oneri sicurezza   = PL x sicurezza%                 (non soggetti a ribasso, riconosciuti a costo)
  Imponibile        = PS + oneri sicurezza            IVA = Imponibile x iva%
  Utile effettivo   = PS - CI                         Margine % = utile effettivo / Imponibile
"""

from core import fmt_num, to_float

PV_DEFAULT = {
    "sg_pct": 15.0,           # spese generali sui costi diretti
    "utile_pct": 10.0,        # utile d'impresa sul costo industriale
    "sicurezza_pct": 2.0,     # oneri di sicurezza sul prezzo di listino (non ribassabili)
    "sconto_pct": 0.0,        # sconto commerciale sui lavori
    "iva_pct": 10.0,          # aliquota IVA (0 per inversione contabile / esenzioni)
    "margine_min_pct": 8.0,   # margine minimo accettabile (per calcolare lo sconto massimo)
}
LIMITI_PV = {"sg_pct": (0.0, 60.0), "utile_pct": (0.0, 100.0), "sicurezza_pct": (0.0, 20.0), "sconto_pct": (0.0, 60.0),
             "iva_pct": (0.0, 30.0), "margine_min_pct": (0.0, 60.0)}

COLONNE_VOCI = ["Codice", "Categoria", "Descrizione", "UM", "Quantita", "Materiali", "Manodopera", "Noli_altro"]
ETICHETTE_VOCI = {"Codice": "Codice", "Categoria": "Categoria", "Descrizione": "Descrizione", "UM": "U.M.", "Quantita": "Quantità",
                  "Materiali": "Materiali €/u", "Manodopera": "Manodopera €/u", "Noli_altro": "Noli e altro €/u"}
CATEGORIE_SUGGERITE = ["Cantierizzazione", "Demolizioni", "Opere murarie", "Isolamento e cappotto", "Serramenti", "Impianti termici",
                       "Impianti elettrici e FV", "Finiture", "Oneri e varie"]


def _r2(x):
    return round(x + 0.0, 2)


# ----------------------------------------------------------------------------
# VOCI
# ----------------------------------------------------------------------------
def normalizza_voci(righe):
    """Pulisce le righe (da editor, file o AI). Restituisce (voci valide, avvisi). Scarta le righe senza descrizione e quantita'."""
    voci, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        desc = str(r.get("Descrizione") or "").strip()
        qta = to_float(r.get("Quantita"), 0.0)
        mat, man, nol = (max(0.0, to_float(r.get(k), 0.0)) for k in ("Materiali", "Manodopera", "Noli_altro"))
        if not desc and qta == 0 and not (mat or man or nol):
            continue
        if not desc:
            avvisi.append(f"Riga {i}: manca la descrizione.")
            desc = f"Voce {len(voci) + 1}"
        if qta <= 0:
            avvisi.append(f"Riga {i} ({desc[:30]}): quantita' nulla o negativa, voce ignorata.")
            continue
        if not (mat or man or nol):
            avvisi.append(f"Riga {i} ({desc[:30]}): nessun costo unitario inserito (la voce vale 0 euro).")
        voci.append({
            "Codice": str(r.get("Codice") or "").strip(), "Categoria": str(r.get("Categoria") or "").strip() or "Varie",
            "Descrizione": desc, "UM": str(r.get("UM") or "").strip() or "cad", "Quantita": qta,
            "Materiali": mat, "Manodopera": man, "Noli_altro": nol,
        })
    return voci, avvisi


_ALIAS = {
    "codice": "Codice", "cod": "Codice", "articolo": "Codice", "categoria": "Categoria", "capitolo": "Categoria", "descrizione": "Descrizione",
    "voce": "Descrizione", "lavorazione": "Descrizione", "um": "UM", "u.m.": "UM", "unita": "UM", "unita' di misura": "UM",
    "quantita": "Quantita", "quantità": "Quantita", "qta": "Quantita", "q.ta": "Quantita", "q.tà": "Quantita", "qt": "Quantita",
    "materiali": "Materiali", "materiale": "Materiali", "manodopera": "Manodopera", "mano d'opera": "Manodopera",
    "noli": "Noli_altro", "noli e altro": "Noli_altro", "noli_altro": "Noli_altro", "altro": "Noli_altro",
    "costo unitario": "Materiali", "prezzo unitario": "Materiali", "costo_unitario": "Materiali", "prezzo": "Materiali",
}


def voci_da_dataframe(df):
    """Mappa le colonne di un file Excel/CSV (nomi flessibili) sulle colonne standard. Restituisce (righe, avvisi)."""
    mappa, avvisi, usati = {}, [], set()
    for col in df.columns:
        chiave = _ALIAS.get(str(col).strip().lower())
        if chiave and chiave not in usati:
            mappa[col] = chiave
            usati.add(chiave)
    if "Descrizione" not in usati or "Quantita" not in usati:
        raise ValueError("Il file deve avere almeno le colonne 'Descrizione' e 'Quantita' (accetto anche 'Voce', 'Qta', 'Q.ta').")
    if any(str(c).strip().lower() in ("costo unitario", "prezzo unitario", "costo_unitario", "prezzo") for c in mappa):
        avvisi.append("Il costo unitario del file e' stato inserito nella colonna Materiali: ripartiscilo tra materiali, manodopera e noli se serve.")
    righe = []
    for _, r in df.iterrows():
        righe.append({mappa[c]: r[c] for c in mappa})
    return righe, avvisi


def normalizza_voci_ai(raw):
    """Voci proposte dall'AI (JSON): lista di oggetti o {"voci": [...]}. Restituisce (voci, note)."""
    note = ""
    if isinstance(raw, dict):
        note = str(raw.get("note") or "")
        raw = raw.get("voci")
    if not isinstance(raw, list) or not raw:
        raise ValueError("Il modello non ha restituito un elenco di voci valido.")
    alias = {"quantita": "Quantita", "qta": "Quantita", "um": "UM", "descrizione": "Descrizione", "categoria": "Categoria", "codice": "Codice",
             "materiali": "Materiali", "manodopera": "Manodopera", "noli_altro": "Noli_altro", "noli": "Noli_altro"}
    righe = []
    for r in raw:
        if isinstance(r, dict):
            righe.append({alias.get(str(k).lower(), k): v for k, v in r.items()})
    voci, _ = normalizza_voci(righe)
    if not voci:
        raise ValueError("Nessuna voce utilizzabile nella risposta del modello.")
    return voci, note


# ----------------------------------------------------------------------------
# CALCOLO
# ----------------------------------------------------------------------------
def _pulisci_par(p):
    q = {**PV_DEFAULT, **(p or {})}
    for k, (lo, hi) in LIMITI_PV.items():
        q[k] = min(max(to_float(q[k], PV_DEFAULT[k]), lo), hi)
    return q


def calcola_preventivo(voci, p=None):
    """Calcola costi, prezzi per voce, totali, IVA e margine. `voci`: righe gia' normalizzate (normalizza_voci)."""
    q = _pulisci_par(p)
    k_prezzo = (1 + q["sg_pct"] / 100.0) * (1 + q["utile_pct"] / 100.0) * (1 - q["sconto_pct"] / 100.0)
    righe, cd = [], 0.0
    for v in voci:
        cu = v["Materiali"] + v["Manodopera"] + v["Noli_altro"]
        costo = v["Quantita"] * cu
        prezzo = _r2(costo * k_prezzo)
        righe.append({**v, "Costo unitario": cu, "Costo": costo, "Prezzo": prezzo,
                      "Prezzo unitario": (prezzo / v["Quantita"]) if v["Quantita"] else 0.0})
        cd += costo
    sg = cd * q["sg_pct"] / 100.0
    ci = cd + sg
    pl = ci * (1 + q["utile_pct"] / 100.0)                       # listino teorico, base per sicurezza e sconto
    ps = _r2(sum(r["Prezzo"] for r in righe))                      # prezzo lavori scontato (somma dei prezzi di riga arrotondati)
    sconto = pl - ps if q["sconto_pct"] else 0.0
    os_ = _r2(pl * q["sicurezza_pct"] / 100.0)
    imponibile = _r2(ps + os_)
    iva = _r2(imponibile * q["iva_pct"] / 100.0)
    utile = ps - ci
    cat = {}
    for r in righe:
        c = cat.setdefault(r["Categoria"], {"Categoria": r["Categoria"], "Voci": 0, "Costo": 0.0, "Prezzo": 0.0})
        c["Voci"] += 1
        c["Costo"] += r["Costo"]
        c["Prezzo"] += r["Prezzo"]
    kpi = {
        "n_voci": len(righe), "costi_diretti": cd, "spese_generali": sg, "costo_industriale": ci, "listino": pl,
        "sconto": sconto, "prezzo_lavori": ps, "oneri_sicurezza": os_, "imponibile": imponibile, "iva": iva, "totale": _r2(imponibile + iva),
        "utile": utile, "margine_pct": (utile / imponibile * 100.0) if imponibile else 0.0,
        "utile_su_costi_pct": (utile / ci * 100.0) if ci else 0.0,
        "sconto_max_pct": sconto_massimo(ci, pl, os_, q["margine_min_pct"]),
        "costi_totali_impresa": ci + os_,
    }
    out = {"params": q, "voci": righe, "categorie": list(cat.values()), "kpi": kpi}
    out["avvisi"] = valida_preventivo(q, out)
    return out


def sconto_massimo(ci, pl, os_, margine_min_pct):
    """Sconto % massimo sul listino che mantiene un margine (utile / imponibile) pari almeno a `margine_min_pct`."""
    m = margine_min_pct / 100.0
    if pl <= 0 or m >= 1:
        return 0.0
    s = 1.0 - (ci + m * os_) / (pl * (1 - m))
    return max(0.0, min(100.0, s * 100.0))


def valida_preventivo(q, out):
    k, w = out["kpi"], []
    if k["n_voci"] == 0:
        return ["Nessuna voce nel computo: aggiungi almeno una riga con descrizione e quantita'."]
    if k["utile"] < 0:
        w.append(f"Il preventivo e' in perdita: l'utile effettivo e' {fmt_num(k['utile'])} EUR. Riduci lo sconto o rivedi i costi.")
    elif k["margine_pct"] < q["margine_min_pct"]:
        w.append(f"Il margine ({fmt_num(k['margine_pct'], 1)}%) e' sotto il minimo che hai fissato ({fmt_num(q['margine_min_pct'], 1)}%): "
                 f"lo sconto massimo coerente e' {fmt_num(k['sconto_max_pct'], 1)}%.")
    senza_costi = [v["Descrizione"] for v in out["voci"] if v["Costo"] <= 0]
    if senza_costi:
        w.append(f"{len(senza_costi)} voci hanno costo zero (es. {senza_costi[0][:40]}): controlla che i costi unitari siano completi.")
    if q["sconto_pct"] > k["sconto_max_pct"] + 1e-9:
        w.append(f"Lo sconto del {fmt_num(q['sconto_pct'], 1)}% supera quello massimo sostenibile ({fmt_num(k['sconto_max_pct'], 1)}%).")
    return w


def sensibilita_costi(voci, p=None, variazioni=(-10, -5, 0, 5, 10, 15, 20)):
    """Margine se i costi diretti variano ma il prezzo al cliente resta quello gia' offerto (rischio di aumento dei costi)."""
    base = calcola_preventivo(voci, p)
    q, k = base["params"], base["kpi"]
    righe = []
    for v in variazioni:
        cd = k["costi_diretti"] * (1 + v / 100.0)
        ci = cd * (1 + q["sg_pct"] / 100.0)
        utile = k["prezzo_lavori"] - ci
        righe.append({"Variazione costi %": v, "Costi diretti": cd, "Utile": utile,
                      "Margine %": (utile / k["imponibile"] * 100.0) if k["imponibile"] else 0.0})
    return righe


def costi_massimi_aumento(voci, p=None):
    """Aumento % dei costi diretti che azzera l'utile, a prezzo invariato."""
    base = calcola_preventivo(voci, p)
    k, q = base["kpi"], base["params"]
    if k["costi_diretti"] <= 0:
        return None
    return (k["prezzo_lavori"] / (1 + q["sg_pct"] / 100.0) / k["costi_diretti"] - 1.0) * 100.0


def per_cash_flow(out, nome="Nuovo cantiere", inizio=1, durata=3, anticipo=30.0, saldo=30.0, gg_incasso=30):
    """Riga del portafoglio del Cash Flow di cantiere costruita da un preventivo: contratto = imponibile, costi% = costi totali / imponibile."""
    k = out["kpi"]
    imp = k["imponibile"]
    return {"Cantiere": nome, "Contratto": imp, "Inizio": int(inizio), "Durata": int(durata), "Anticipo_pct": float(anticipo),
            "Saldo_pct": float(saldo), "Gg_incasso": int(gg_incasso),
            "Costi_pct": (k["costi_totali_impresa"] / imp * 100.0) if imp else 0.0}
