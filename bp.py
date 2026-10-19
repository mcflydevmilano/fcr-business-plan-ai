"""
bp.py - Motore di calcolo del Business Plan Studio (nuove iniziative, 3-5 anni).

Tutto e' deterministico e senza Streamlit, quindi testabile. L'AI non calcola nulla: al piu' propone le assunzioni
(normalizza_assunzioni) che l'utente verifica e applica.

Modello (importi in EUR, anno 0 = investimento iniziale, anni 1..n = gestione):
  Ricavi(t)      = Ricavi(1) x (1 + crescita)^(t-1)
  EBITDA(t)      = Ricavi - costi variabili (% ricavi) - personale (cresce di inflazione) - altri costi fissi
  Ammortamento   = Capex / anni di ammortamento (finche' dura)
  Interessi(t)   = tasso x debito residuo a inizio anno (piano di ammortamento del mutuo, rate annuali)
  Imposte(t)     = IRES + IRAP (modello "dettagliato", predefinito) oppure aliquota unica sugli utili positivi ("semplice").
                   IRES = aliquota x (utile ante imposte - perdite pregresse utilizzabili, max 80% del reddito);
                   IRAP = aliquota x (EBIT + personale non deducibile), dovuta anche in perdita civilistica.
  dCCN(t)        = ccn% x variazione dei ricavi (anno 1: ccn% x ricavi)
  FCF operativo  = EBITDA - imposte - dCCN
  Cassa(t)       = Cassa(t-1) + FCF operativo - interessi - quota capitale
  Cassa(0)       = mezzi propri + mutuo - capex
  DSCR(t)        = FCF operativo / (interessi + quota capitale)
  PFN(t)         = debito residuo - cassa
"""
import math

from core import fmt_num, to_float

BP_DEFAULT = {
    "anno_inizio": 2027,
    "n_anni": 3,
    "ricavi_y1": 1_500_000.0,
    "crescita": 15.0,
    "cv_pct": 55.0,
    "personale": 250_000.0,
    "infl_personale": 5.0,
    "costi_fissi": 120_000.0,
    "capex": 250_000.0,
    "anni_amm": 5,
    "mutuo": 200_000.0,
    "tasso": 4.5,
    "durata": 5,
    "tipo_rata": "francese",
    "equity": 50_000.0,
    "aliquota": 28.0,
    "ccn_pct": 10.0,
    "fisco": "dettagliato",      # "dettagliato" = IRES + IRAP con riporto perdite; "semplice" = aliquota unica
    "ires": 24.0,
    "irap": 3.9,
    "irap_ded_pers": 0.0,        # % del costo del personale deducibile dalla base IRAP (cuneo fiscale, apprendisti...)
    "riporto": True,             # riporto illimitato delle perdite fiscali, utilizzabile fino all'80% del reddito
}

LIMITE_RIPORTO = 0.80

# limiti ammessi (usati dalla normalizzazione dei valori proposti dall'AI e dai widget)
LIMITI = {
    "ricavi_y1": (0.0, 500_000_000.0), "crescita": (-20.0, 100.0), "cv_pct": (0.0, 95.0),
    "personale": (0.0, 100_000_000.0), "infl_personale": (0.0, 20.0), "costi_fissi": (0.0, 100_000_000.0),
    "capex": (0.0, 500_000_000.0), "anni_amm": (1, 20), "mutuo": (0.0, 500_000_000.0), "tasso": (0.0, 20.0),
    "durata": (1, 30), "equity": (0.0, 500_000_000.0), "aliquota": (0.0, 60.0), "ccn_pct": (0.0, 60.0),
    "n_anni": (3, 5), "ires": (0.0, 40.0), "irap": (0.0, 10.0), "irap_ded_pers": (0.0, 100.0),
}
ETICHETTE_BP = {
    "ricavi_y1": "Ricavi anno 1", "crescita": "Crescita annua dei ricavi (dal 2° anno)", "cv_pct": "Costi variabili (% dei ricavi)",
    "personale": "Costo del personale annuo", "infl_personale": "Aumento annuo del personale",
    "costi_fissi": "Altri costi fissi e servizi", "capex": "Investimento iniziale (CAPEX)",
    "anni_amm": "Anni di ammortamento", "mutuo": "Finanziamento bancario", "tasso": "Tasso d'interesse annuo",
    "durata": "Durata del finanziamento (anni)", "equity": "Mezzi propri apportati", "aliquota": "Aliquota fiscale (IRES+IRAP)",
    "ccn_pct": "Capitale circolante (% sulla variazione dei ricavi)",
    "ires": "Aliquota IRES", "irap": "Aliquota IRAP", "irap_ded_pers": "Personale deducibile dall'IRAP (%)",
}


def _f(x):
    return float(x)


def piano_mutuo(importo, tasso_pct, durata, tipo="francese"):
    """Piano di ammortamento a rate annuali. Restituisce una riga per anno: quota capitale, interessi, rata, debito residuo."""
    importo, durata = max(0.0, _f(importo)), int(max(1, durata))
    r = max(0.0, _f(tasso_pct)) / 100.0
    righe, residuo = [], importo
    if importo <= 0:
        return [{"Anno": a, "Quota capitale": 0.0, "Interessi": 0.0, "Rata": 0.0, "Debito residuo": 0.0}
                for a in range(1, durata + 1)]
    if tipo == "italiano":
        quota_fissa = importo / durata
    else:
        rata_fissa = importo / durata if r == 0 else importo * r / (1 - (1 + r) ** (-durata))
    for a in range(1, durata + 1):
        interessi = residuo * r
        quota = quota_fissa if tipo == "italiano" else rata_fissa - interessi
        if a == durata:
            quota = residuo                      # azzera eventuali residui da arrotondamento
        residuo = max(0.0, residuo - quota)
        righe.append({"Anno": a, "Quota capitale": quota, "Interessi": interessi, "Rata": quota + interessi,
                      "Debito residuo": residuo})
    return righe


def calcola_bp(p):
    """Calcola conto economico, cash flow e indicatori. `p`: dizionario con le chiavi di BP_DEFAULT."""
    q = {**BP_DEFAULT, **p}
    n = int(min(5, max(3, q["n_anni"])))
    sched = piano_mutuo(q["mutuo"], q["tasso"], q["durata"], q["tipo_rata"])
    sched_by = {r["Anno"]: r for r in sched}
    anni_amm = int(max(1, q["anni_amm"]))
    amm_annua = q["capex"] / anni_amm
    cassa = q["equity"] + q["mutuo"] - q["capex"]
    cassa0 = cassa
    ricavi_prec = 0.0
    debito = q["mutuo"]
    righe, cum_fcf, payback = [], 0.0, None
    perdite = 0.0
    for t in range(1, n + 1):
        ricavi = q["ricavi_y1"] * (1 + q["crescita"] / 100.0) ** (t - 1)
        cv = ricavi * q["cv_pct"] / 100.0
        pers = q["personale"] * (1 + q["infl_personale"] / 100.0) ** (t - 1)
        ebitda = ricavi - cv - pers - q["costi_fissi"]
        amm = amm_annua if t <= anni_amm else 0.0
        ebit = ebitda - amm
        m = sched_by.get(t, {"Quota capitale": 0.0, "Interessi": 0.0, "Debito residuo": 0.0})
        interessi, quota = m["Interessi"], m["Quota capitale"]
        debito = m["Debito residuo"] if t in sched_by else 0.0
        ebt = ebit - interessi
        utilizzo = 0.0
        if q["fisco"] == "semplice":
            ires, irap = max(0.0, ebt) * q["aliquota"] / 100.0, 0.0
        else:
            base_irap = max(0.0, ebit + pers * (1 - q["irap_ded_pers"] / 100.0))
            irap = base_irap * q["irap"] / 100.0
            if ebt < 0:
                if q["riporto"]:
                    perdite += -ebt
                imponibile = 0.0
            else:
                if q["riporto"]:
                    utilizzo = min(perdite, LIMITE_RIPORTO * ebt)
                    perdite -= utilizzo
                imponibile = ebt - utilizzo
            ires = imponibile * q["ires"] / 100.0
        imposte = ires + irap
        utile = ebt - imposte
        dccn = (ricavi - ricavi_prec) * q["ccn_pct"] / 100.0
        fcf_op = ebitda - imposte - dccn
        servizio = interessi + quota
        flusso = fcf_op - servizio
        prev_cum = cum_fcf
        cum_fcf += fcf_op
        if payback is None and q["capex"] > 0 and cum_fcf >= q["capex"]:
            frazione = (q["capex"] - prev_cum) / fcf_op if fcf_op > 0 else 1.0
            payback = (t - 1) + max(0.0, min(1.0, frazione))
        cassa += flusso
        pfn = debito - cassa
        righe.append({
            "AnnoNum": int(q["anno_inizio"]) + t - 1, "Anno": f"Anno {t} ({int(q['anno_inizio']) + t - 1})",
            "Ricavi": ricavi, "Costi variabili": cv, "Personale": pers, "Altri costi": q["costi_fissi"],
            "EBITDA": ebitda, "Margine EBITDA %": (ebitda / ricavi * 100.0) if ricavi else 0.0,
            "Ammortamenti": amm, "EBIT": ebit, "Interessi": interessi, "Utile ante imposte": ebt,
            "IRES": ires, "IRAP": irap, "Perdite utilizzate": utilizzo, "Perdite fiscali residue": perdite,
            "Imposte": imposte, "Utile netto": utile, "Variazione CCN": dccn, "FCF operativo": fcf_op,
            "Quota capitale": quota, "Flusso netto": flusso, "Cassa finale": cassa, "Debito residuo": debito,
            "PFN": pfn,
            "DSCR": (fcf_op / servizio) if servizio > 1e-9 else None,
            "PFN/EBITDA": (pfn / ebitda) if ebitda > 0 else (0.0 if pfn <= 0 else math.inf),
        })
        ricavi_prec = ricavi
    cassa_min = min([cassa0] + [r["Cassa finale"] for r in righe])
    dscr_vals = [r["DSCR"] for r in righe if r["DSCR"] is not None]
    kpi = {
        "fabbisogno": q["capex"], "fonti": q["mutuo"] + q["equity"], "gap_fonti": q["capex"] - q["mutuo"] - q["equity"],
        "cassa_iniziale": cassa0, "cassa_minima": cassa_min, "payback_anni": payback,
        "dscr_min": min(dscr_vals) if dscr_vals else None,
        "dscr_medio": (sum(dscr_vals) / len(dscr_vals)) if dscr_vals else None,
        "ebitda_cum": sum(r["EBITDA"] for r in righe), "utile_cum": sum(r["Utile netto"] for r in righe),
        "interessi_tot": sum(r["Interessi"] for r in sched),
        "copertura_ebitda_y1": (righe[0]["EBITDA"] / sched_by[1]["Rata"]) if sched_by.get(1, {}).get("Rata", 0) > 0 else None,
        "n_anni": n,
    }
    out = {"params": q, "anni": righe, "mutuo": sched, "kpi": kpi}
    out["avvisi"] = valida_bp(q, out)
    return out


def valida_bp(q, out):
    """Avvisi di coerenza/sostenibilita' (frasi per l'utente)."""
    w, k, righe = [], out["kpi"], out["anni"]
    if q["ricavi_y1"] <= 0:
        w.append("I ricavi dell'anno 1 sono nulli: il piano non e' significativo.")
    if righe and righe[0]["EBITDA"] <= 0:
        w.append("L'EBITDA dell'anno 1 e' negativo o nullo: l'iniziativa non copre i costi operativi nel primo anno.")
    if k["gap_fonti"] > 1:
        w.append(f"Le fonti (mutuo + mezzi propri = {fmt_num(k['fonti'])} EUR) non coprono l'investimento "
                 f"({fmt_num(q['capex'])} EUR): mancano {fmt_num(k['gap_fonti'])} EUR di copertura iniziale.")
    if k["cassa_minima"] < -1:
        w.append(f"La cassa scende fino a {fmt_num(k['cassa_minima'])} EUR: serve un finanziamento aggiuntivo o piu' mezzi propri.")
    if k["dscr_min"] is not None and k["dscr_min"] < 1.0:
        w.append(f"Il DSCR minimo e' {fmt_num(k['dscr_min'], 2)}x: in almeno un anno il flusso operativo non copre il servizio del debito.")
    elif k["dscr_min"] is not None and k["dscr_min"] < 1.2:
        w.append(f"Il DSCR minimo e' {fmt_num(k['dscr_min'], 2)}x: margine di sicurezza ridotto (le banche chiedono spesso almeno 1,2x).")
    if q["mutuo"] > q["capex"] > 0:
        w.append("Il finanziamento supera l'investimento: verifica che sia coerente con l'uso dei fondi.")
    if q["mutuo"] > 0 and q["durata"] > q["anni_amm"] + 5:
        w.append("La durata del finanziamento e' molto piu' lunga della vita utile dell'investimento.")
    if q["durata"] > q["n_anni"] and q["mutuo"] > 0:
        w.append(f"Il finanziamento dura {int(q['durata'])} anni ma il piano ne copre {int(q['n_anni'])}: "
                 "il debito residuo a fine piano e' incluso nella PFN.")
    if k["payback_anni"] is None and q["capex"] > 0:
        w.append("L'investimento non rientra entro l'orizzonte del piano (payback oltre l'ultimo anno).")
    if q["cv_pct"] >= 90:
        w.append("I costi variabili superano il 90% dei ricavi: margine di contribuzione molto basso.")
    return w


def normalizza_assunzioni(raw):
    """
    Converte il JSON proposto dall'AI in (valori, motivazioni, note):
    - valori: solo le chiavi di BP_DEFAULT riconosciute, portate nei limiti ammessi;
    - motivazioni: {chiave: breve spiegazione fornita dall'AI};
    - note: testo libero (rischi, cosa verificare).
    """
    if isinstance(raw, list) and raw:
        raw = raw[0]
    if not isinstance(raw, dict):
        raise ValueError("Il modello non ha restituito un oggetto JSON valido.")
    alias = {"crescita_pct": "crescita", "costi_variabili_pct": "cv_pct", "costo_personale": "personale",
             "anni_ammortamento": "anni_amm", "durata_mutuo": "durata", "tasso_pct": "tasso", "aliquota_pct": "aliquota",
             "mezzi_propri": "equity", "investimento": "capex", "ricavi_anno1": "ricavi_y1", "importo_mutuo": "mutuo",
             "altri_costi_fissi": "costi_fissi", "anni": "n_anni"}
    valori = {}
    for k, v in raw.items():
        kk = alias.get(k, k)
        if kk not in LIMITI or v is None:
            continue
        x = to_float(v, None)
        if x is None:
            continue
        lo, hi = LIMITI[kk]
        x = min(max(x, lo), hi)
        valori[kk] = int(round(x)) if kk in ("anni_amm", "durata", "n_anni") else float(x)
    mot_raw = raw.get("motivazioni") if isinstance(raw.get("motivazioni"), dict) else {}
    motivazioni = {alias.get(k, k): str(v) for k, v in mot_raw.items() if alias.get(k, k) in LIMITI}
    return valori, motivazioni, str(raw.get("note") or "")


# ----------------------------------------------------------------------------
# SCENARI E ANALISI DI SENSIBILITA'
# ----------------------------------------------------------------------------
# Ogni scenario e' un insieme di scostamenti rispetto alle ipotesi base:
#   *_pct = variazione relativa in % (es. -15 = -15% del valore base); *_pp = punti percentuali assoluti.
CAMPI_SCENARIO = {
    "ricavi_pct": ("ricavi_y1", "rel", "Ricavi anno 1 (variazione %)"),
    "crescita_pp": ("crescita", "pp", "Crescita annua (punti %)"),
    "cv_pp": ("cv_pct", "pp", "Costi variabili (punti % dei ricavi)"),
    "personale_pct": ("personale", "rel", "Costo del personale (variazione %)"),
    "costi_fissi_pct": ("costi_fissi", "rel", "Altri costi fissi (variazione %)"),
    "capex_pct": ("capex", "rel", "Investimento (variazione %)"),
    "tasso_pp": ("tasso", "pp", "Tasso d'interesse (punti %)"),
    "ccn_pp": ("ccn_pct", "pp", "Capitale circolante (punti %)"),
}

SCENARI_DEFAULT = {
    "Pessimistico": {"ricavi_pct": -15.0, "crescita_pp": -5.0, "cv_pp": 3.0, "personale_pct": 0.0, "costi_fissi_pct": 5.0,
                     "capex_pct": 10.0, "tasso_pp": 1.0, "ccn_pp": 5.0},
    "Base": {k: 0.0 for k in CAMPI_SCENARIO},
    "Ottimistico": {"ricavi_pct": 10.0, "crescita_pp": 3.0, "cv_pp": -2.0, "personale_pct": 0.0, "costi_fissi_pct": 0.0,
                    "capex_pct": 0.0, "tasso_pp": -0.5, "ccn_pp": -2.0},
}


def _limita(chiave, v):
    lo, hi = LIMITI.get(chiave, (-math.inf, math.inf))
    v = min(max(v, lo), hi)
    return int(round(v)) if chiave in ("anni_amm", "durata", "n_anni") else v


def applica_scenario(p, delta):
    """Restituisce i parametri modificati secondo gli scostamenti `delta` (campi di CAMPI_SCENARIO)."""
    q = {**BP_DEFAULT, **p}
    for campo, (chiave, modo, _et) in CAMPI_SCENARIO.items():
        d = to_float((delta or {}).get(campo), 0.0)
        if not d:
            continue
        q[chiave] = _limita(chiave, q[chiave] * (1 + d / 100.0) if modo == "rel" else q[chiave] + d)
    return q


def calcola_scenari(p, scenari=None):
    """{nome scenario: risultato di calcola_bp}. Lo scenario "Base" usa sempre le ipotesi correnti, senza scostamenti."""
    scenari = dict(scenari or SCENARI_DEFAULT)
    scenari["Base"] = {}
    ordine = [n for n in ("Pessimistico", "Base", "Ottimistico") if n in scenari] + [n for n in scenari if n not in ("Pessimistico", "Base", "Ottimistico")]
    return {n: calcola_bp(applica_scenario(p, scenari[n])) for n in ordine}


def confronto_scenari(risultati):
    """Tabella di confronto: una riga per scenario con gli indicatori chiave."""
    righe = []
    for nome, o in risultati.items():
        a, k = o["anni"], o["kpi"]
        righe.append({
            "Scenario": nome, "Ricavi ultimo anno": a[-1]["Ricavi"], "EBITDA ultimo anno": a[-1]["EBITDA"],
            "Utile netto cumulato": k["utile_cum"], "Cassa minima": k["cassa_minima"],
            "DSCR minimo": k["dscr_min"], "Payback (anni)": k["payback_anni"], "PFN ultimo anno": a[-1]["PFN"],
        })
    return righe


DRIVER_SENS = {   # chiave: (etichetta, modo, ampiezza)  rel = +/-% del valore; pp = +/- punti
    "ricavi_y1": ("Ricavi anno 1", "rel", 10.0), "crescita": ("Crescita annua ricavi", "pp", 5.0),
    "cv_pct": ("Costi variabili %", "pp", 5.0), "personale": ("Costo del personale", "rel", 10.0),
    "costi_fissi": ("Altri costi fissi", "rel", 10.0), "capex": ("Investimento (CAPEX)", "rel", 10.0),
    "tasso": ("Tasso d'interesse", "pp", 1.0), "ccn_pct": ("Capitale circolante %", "pp", 5.0),
}
METRICHE = {"dscr_min": "DSCR minimo", "cassa_minima": "Cassa minima (EUR)", "utile_cum": "Utile netto cumulato (EUR)",
            "ebitda_cum": "EBITDA cumulato (EUR)"}


def _metrica(out, m):
    v = out["kpi"].get(m)
    return None if v is None else float(v)


def _con(p, chiave, modo, ampiezza, segno):
    q = {**BP_DEFAULT, **p}
    base = q[chiave]
    q[chiave] = _limita(chiave, base * (1 + segno * ampiezza / 100.0) if modo == "rel" else base + segno * ampiezza)
    return q


def sensibilita(p, metrica="cassa_minima", driver=None):
    """
    Analisi 'tornado': per ogni variabile calcola la metrica con valore ridotto e aumentato (ampiezza in DRIVER_SENS).
    Restituisce le righe ordinate per impatto decrescente. Se la metrica non e' definita (es. DSCR senza mutuo) restituisce [].
    """
    base = _metrica(calcola_bp(p), metrica)
    if base is None:
        return []
    righe = []
    for chiave, (et, modo, amp) in (driver or DRIVER_SENS).items():
        lo = _metrica(calcola_bp(_con(p, chiave, modo, amp, -1)), metrica)
        hi = _metrica(calcola_bp(_con(p, chiave, modo, amp, +1)), metrica)
        if lo is None or hi is None:
            continue
        righe.append({"chiave": chiave, "Variabile": et, "Variazione": f"±{amp:g}{'%' if modo == 'rel' else ' pt'}",
                      "Con valore minore": lo, "Con valore maggiore": hi, "Base": base,
                      "Impatto": max(abs(lo - base), abs(hi - base))})
    return sorted(righe, key=lambda r: -r["Impatto"])


def griglia(p, chiave_x, valori_x, chiave_y, valori_y, metrica="cassa_minima"):
    """Matrice righe=valori_y, colonne=valori_x della metrica scelta (None dove non definita)."""
    out = []
    for vy in valori_y:
        riga = []
        for vx in valori_x:
            q = {**BP_DEFAULT, **p}
            q[chiave_x], q[chiave_y] = _limita(chiave_x, vx), _limita(chiave_y, vy)
            riga.append(_metrica(calcola_bp(q), metrica))
        out.append(riga)
    return out
