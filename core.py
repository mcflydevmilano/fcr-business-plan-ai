"""
core.py - Motore di calcolo (nessuna dipendenza da Streamlit, quindi testabile).

Contiene: formattazione italiana, normalizzazione/validazione dei dati, proiezione
pluriennale con free cash flow, scoring con soglie configurabili, leva minima
(funzione inversa), stress test, covenant, analisi del portafoglio commesse.
"""
import os
import copy
import hashlib
import json
import math
import re

import pandas as pd

# ----------------------------------------------------------------------------
# COSTANTI
# ----------------------------------------------------------------------------
CAMPI_MONETARI = [
    "ricavi", "ebitda", "utile_netto", "totale_attivo",
    "patrimonio_netto", "debiti_finanziari_totali", "pfn",
]
CAMPI_STORICO = ["ricavi", "ebitda", "patrimonio_netto", "pfn"]

DATI_DEFAULT = {
    "anno_riferimento": 2025,
    "ricavi": 2500000.0,
    "ebitda": 300000.0,
    "utile_netto": 120000.0,
    "totale_attivo": 3000000.0,
    "patrimonio_netto": 800000.0,
    "debiti_finanziari_totali": 900000.0,
    "pfn": 600000.0,
    "dscr_stimato": 1.45,
}

PIANO_DEFAULT = {
    "g_ricavi": 5.0,
    "g_ebitda": 6.0,
    "rimborso": 50000.0,
    "capex": 60000.0,
    "amm": 100000.0,
    "aliquota": 27.9,   # IRES 24% + IRAP 3,9% (indicativa)
    "tasso": 4.5,
    "ccn_pct": 20.0,
}

LEVE_DEFAULT = {"delta_pfn": 0.0, "delta_pn": 0.0, "delta_ebitda": 0.0}

# Soglie (verde, giallo). "min": minore e' meglio; "max": maggiore e' meglio.
# Sono ipotesi di lavoro, NON un rating regolamentare: vanno calibrate.
SOGLIE_DEFAULT = {
    "pfn_ebitda": (2.5, 4.5),
    "pfn_pn": (1.0, 2.0),
    "equity_ratio": (0.25, 0.15),
    "dscr": (1.30, 1.00),
}
VERSO = {"pfn_ebitda": "min", "pfn_pn": "min", "equity_ratio": "max", "dscr": "max"}

COVENANT_DEFAULT = {"pfn_ebitda_max": 3.5, "dscr_min": 1.20}

COLONNE_COMMESSE = [
    "Commessa", "Cliente", "Importo", "Avanzamento_pct", "Fatturato", "Incassato", "Margine_pct",
]

DISCLAIMER = (
    "Il presente documento e' una simulazione indicativa basata su un modello di scoring interno e "
    "su dati forniti dall'utente e/o estratti automaticamente con strumenti di intelligenza artificiale. "
    "Non costituisce un rating regolamentare ai sensi di Basilea 3/4, ne' un parere di merito creditizio "
    "di alcun istituto di credito, ne' consulenza finanziaria. I dati devono essere verificati da un "
    "professionista prima di qualsiasi utilizzo decisionale."
)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _trova_file(candidati):
    """Primo file esistente tra i candidati, cercato accanto ai .py e nella cartella corrente."""
    for nome in candidati:
        for base in (_BASE_DIR, os.getcwd()):
            p = os.path.join(base, nome)
            if os.path.isfile(p):
                return p
    # ultimo tentativo: qualsiasi PNG/JPG con "fcr" nel nome (per il logo FCR)
    return None


def _trova_logo_fcr():
    p = _trova_file(["fcr_logo.png", "logo_fcr_new_2026.png", "logo_fcr.png", "fcr.png", "logo_fcr.jpg"])
    if p:
        return p
    for base in (_BASE_DIR, os.getcwd()):
        try:
            for f in sorted(os.listdir(base)):
                if "fcr" in f.lower() and f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    return os.path.join(base, f)
        except OSError:
            pass
    return "fcr_logo.png"


LOGO_PATH = _trova_file(["aetheris_labs_logo.jpg", "aetheris_labs_logo.png"]) or "aetheris_labs_logo.jpg"
LOGO_FCR_PATH = _trova_logo_fcr()        # logo FCR (PNG con trasparenza)

PRIVACY_PUNTI = [
    ("Dati trattati",
     "L'applicazione elabora dati contabili e finanziari di imprese. Evitare di inserire dati personali di persone "
     "fisiche (soci, amministratori, garanti, dipendenti) se non strettamente necessari."),
    ("Elaborazione con intelligenza artificiale",
     "Quando si usano le funzioni AI, i documenti caricati e i dati numerici vengono inviati ai server di Google "
     "(servizio Gemini API) per estrarre i dati e redigere la relazione. Nel piano gratuito Google puo' utilizzare i "
     "contenuti per migliorare i propri servizi; per i piani a pagamento valgono condizioni diverse. Verificare i "
     "termini vigenti prima di caricare dati di clienti."),
    ("Conservazione",
     "I dati inseriti restano nella sessione del browser fino alla sua chiusura. Le pratiche salvate sono memorizzate "
     "nel database dell'applicazione fino alla cancellazione manuale. I report generati non vengono conservati dal "
     "sistema: il registro di audit riporta solo ID, data, modello AI e impronta (hash) dei dati."),
    ("Responsabilita' dell'utente",
     "Chi utilizza l'applicazione deve disporre di una base giuridica per il trattamento, informare gli interessati, "
     "designare i fornitori come responsabili del trattamento, valutare gli eventuali trasferimenti di dati verso "
     "Paesi extra-UE e adottare adeguate misure di sicurezza, ai sensi del Regolamento (UE) 2016/679 (GDPR)."),
    ("Natura dell'informativa",
     "Questa informativa ha finalita' di trasparenza e non costituisce consulenza legale: per la conformita' "
     "consultare il proprio DPO o consulente privacy."),
]
PRIVACY_BREVE = (
    "Privacy: i dati e i documenti elaborati con le funzioni AI sono inviati a Google (Gemini API); nel piano gratuito "
    "Google puo' utilizzarli per migliorare i propri servizi. Evitare dati personali non necessari; l'utente e' "
    "responsabile della base giuridica, dell'informativa agli interessati e della conformita' al GDPR (Reg. UE 2016/679). "
    "Le pratiche salvate restano nel database dell'applicazione fino alla cancellazione manuale."
)

CLASSI = {
    "VERDE": "FASCIA VERDE - Rating Elevato / Bancabile",
    "GIALLA": "FASCIA GIALLA - Rating Neutro / Sotto Osservazione",
    "ROSSA": "FASCIA ROSSA - Rischio Elevato / Requisiti di Garanzia",
}


# ----------------------------------------------------------------------------
# FORMATTAZIONE
# ----------------------------------------------------------------------------
def fmt_num(x, dec=0):
    """Formato italiano: 1.234.567,89"""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n.d."
    if isinstance(x, float) and math.isinf(x):
        return "n.s."
    s = f"{x:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_eur(x, dec=0):
    v = fmt_num(x, dec)
    return v if v in ("n.d.", "n.s.") else f"{v} EUR"


def fmt_x(x):
    v = fmt_num(x, 2)
    return v if v in ("n.d.", "n.s.") else f"{v}x"


def fmt_pct(x, dec=1):
    v = fmt_num(x, dec)
    return v if v in ("n.d.", "n.s.") else f"{v}%"


def livello_classe(classe):
    """ROSSA=0, GIALLA=1, VERDE=2."""
    c = (classe or "").upper()
    return 2 if "VERDE" in c else (1 if "GIALLA" in c else 0)


def hash_payload(obj, n=12):
    raw = json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:n]


# ----------------------------------------------------------------------------
# DATI: CONVERSIONE, NORMALIZZAZIONE, VALIDAZIONE
# ----------------------------------------------------------------------------
def to_float(v, default=0.0):
    """Converte numeri o stringhe (anche in formato italiano) in float."""
    if v is None:
        return default
    if isinstance(v, bool):
        return default
    if isinstance(v, (int, float)):
        return default if (isinstance(v, float) and math.isnan(v)) else float(v)
    s = str(v).strip().replace("€", "").replace("EUR", "").replace(" ", "")
    if not s:
        return default
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") > 1 or re.fullmatch(r"-?\d{1,3}\.\d{3}", s):
        # "1.234.567" oppure "2.500": punto come separatore delle migliaia (uso italiano)
        s = s.replace(".", "")
    try:
        n = float(s)
    except ValueError:
        return default
    return -n if neg else n


def normalizza_estrazione(raw):
    """
    Converte l'output JSON dell'AI in (dati, storico, fonti).
    - dati: dizionario con le chiavi di DATI_DEFAULT (default per i campi mancanti)
    - storico: lista di esercizi precedenti [{anno, ricavi, ebitda, patrimonio_netto, pfn}]
    - fonti: {campo: "pag. X / foglio Y"} per la verifica da parte dell'utente
    """
    if isinstance(raw, list) and raw:
        raw = raw[0]
    if not isinstance(raw, dict):
        raise ValueError("Il modello non ha restituito un oggetto JSON valido.")

    scala = 1000.0 if bool(raw.get("valori_in_migliaia", False)) else 1.0
    dati = dict(DATI_DEFAULT)
    trovati = []
    for k, default in DATI_DEFAULT.items():
        if k in raw and raw[k] is not None:
            dati[k] = to_float(raw[k], default)
            trovati.append(k)
    dati["anno_riferimento"] = int(dati["anno_riferimento"]) or DATI_DEFAULT["anno_riferimento"]
    for k in CAMPI_MONETARI:
        dati[k] *= scala

    storico = []
    for item in raw.get("storico") or []:
        if not isinstance(item, dict):
            continue
        anno = int(to_float(item.get("anno"), 0))
        if anno <= 0 or anno >= dati["anno_riferimento"]:
            continue
        riga = {"anno": anno}
        for k in CAMPI_STORICO:
            riga[k] = to_float(item.get(k), 0.0) * scala
        if not any(riga[k] for k in CAMPI_STORICO):
            continue            # anno senza alcun dato: non e' uno storico utile
        storico.append(riga)
    storico = sorted({r["anno"]: r for r in storico}.values(), key=lambda r: r["anno"])

    fonti_raw = raw.get("fonti") if isinstance(raw.get("fonti"), dict) else {}
    fonti = {k: str(fonti_raw.get(k, "") or "") for k in DATI_DEFAULT}
    # i campi non trovati dall'AI restano ai valori di esempio: li segnaliamo
    for k in DATI_DEFAULT:
        if k not in trovati:
            fonti[k] = "NON TROVATO - valore di esempio, da inserire"
    return dati, storico, fonti


def normalizza_dati(raw):
    """Compatibilita': restituisce solo il dizionario dei dati."""
    return normalizza_estrazione(raw)[0]


def valida_dati(d):
    """Restituisce una lista di avvisi di coerenza sui dati."""
    w = []
    if d["ricavi"] <= 0:
        w.append("I ricavi sono nulli o negativi.")
    if d["ebitda"] > d["ricavi"] > 0:
        w.append("L'EBITDA supera i ricavi: controlla le unita' (euro o migliaia?).")
    if d["totale_attivo"] > 0 and d["patrimonio_netto"] > d["totale_attivo"]:
        w.append("Il patrimonio netto supera il totale attivo.")
    if d["totale_attivo"] > 0 and d["debiti_finanziari_totali"] > d["totale_attivo"]:
        w.append("I debiti finanziari superano il totale attivo.")
    if d["pfn"] > d["debiti_finanziari_totali"] > 0:
        w.append("La PFN supera i debiti finanziari totali (possibile solo con liquidita' negativa).")
    if d["patrimonio_netto"] <= 0:
        w.append("Patrimonio netto nullo o negativo: possibile perdita del capitale.")
    if d["ebitda"] <= 0:
        w.append("EBITDA nullo o negativo: i rapporti basati sull'EBITDA non sono significativi.")
    if d["ricavi"] > 0 and abs(d["utile_netto"]) > d["ricavi"]:
        w.append("L'utile netto supera i ricavi in valore assoluto: controlla le unita'.")
    if d["utile_netto"] > d["ebitda"] > 0:
        w.append("L'utile netto supera l'EBITDA: dato anomalo (salvo componenti straordinarie).")
    if d["ricavi"] > 0 and d["pfn"] > 5 * d["ricavi"]:
        w.append("La PFN supera 5 volte i ricavi: controlla le unita' dei valori (euro o migliaia?).")
    if d["ricavi"] > 0 and 0 < d["ebitda"] < 0.01 * d["ricavi"]:
        w.append("Il margine EBITDA e' inferiore all'1% dei ricavi: controlla le unita' (euro o migliaia?).")
    if d["ricavi"] > 0 and d["ebitda"] > 0.6 * d["ricavi"]:
        w.append("Il margine EBITDA supera il 60% dei ricavi: valore insolito, verifica il dato.")
    return w


def ratio(num, den):
    """Rapporto sicuro. Den <= 0 con num > 0 -> inf (non significativo)."""
    if den > 0:
        return num / den
    return math.inf if num > 0 else 0.0


# ----------------------------------------------------------------------------
# PROIEZIONE PLURIENNALE
# ----------------------------------------------------------------------------
def proietta(ricavi0, ebitda0, pfn0, p, anno_base, n=3):
    """
    Proiezione con free cash flow:
        FCF   = EBITDA - imposte - capex - interessi - variazione CCN
        PFN_t = PFN_(t-1) - FCF
    Il rimborso del debito NON riduce la PFN (usa cassa) ma pesa sul DSCR:
        DSCR  = (EBITDA - imposte - variazione CCN) / (interessi + rimborso)
    """
    rows = []
    r_prev, e, pfn = ricavi0, ebitda0, pfn0
    for i in range(1, n + 1):
        r = r_prev * (1 + p["g_ricavi"] / 100.0)
        e = e * (1 + p["g_ebitda"] / 100.0)
        interessi = max(pfn, 0.0) * p["tasso"] / 100.0
        imposte = max(e - p["amm"] - interessi, 0.0) * p["aliquota"] / 100.0
        d_ccn = p["ccn_pct"] / 100.0 * (r - r_prev)
        capex = p["capex"]
        fcf = e - imposte - capex - interessi - d_ccn
        pfn_new = pfn - fcf
        servizio = interessi + p["rimborso"]
        dscr = (e - imposte - d_ccn) / servizio if servizio > 0 else None
        rows.append(
            {
                "Anno": f"Anno {i} ({int(anno_base) + i})",
                "AnnoNum": int(anno_base) + i,
                "Ricavi": r,
                "EBITDA": e,
                "Interessi": interessi,
                "Imposte": imposte,
                "dCCN": d_ccn,
                "Capex": capex,
                "FCF": fcf,
                "PFN": pfn_new,
                "PFN/EBITDA": ratio(pfn_new, e),
                "Servizio": servizio,
                "DSCR": dscr,
            }
        )
        r_prev, pfn = r, pfn_new
    return rows


# ----------------------------------------------------------------------------
# SCORING
# ----------------------------------------------------------------------------
def _punti(v, verde, giallo, verso):
    if verso == "min":
        return 2 if v < verde else (1 if v < giallo else 0)
    return 2 if v >= verde else (1 if v >= giallo else 0)


def calcola_rating(pfn, ebitda, pn, attivo, dscr, soglie=None):
    s = soglie or SOGLIE_DEFAULT
    pfn_ebitda = ratio(pfn, ebitda)
    pfn_pn = ratio(pfn, pn)
    equity_ratio = pn / attivo if attivo > 0 else 0.0

    valori = {"pfn_ebitda": pfn_ebitda, "pfn_pn": pfn_pn, "equity_ratio": equity_ratio, "dscr": dscr}
    etichette = {
        "pfn_ebitda": "PFN / EBITDA", "pfn_pn": "PFN / Patrimonio netto",
        "equity_ratio": "Patrimonio netto / Attivo", "dscr": "DSCR (anno 1 del piano)",
    }
    dettaglio, punti = [], 0
    for k in ("pfn_ebitda", "pfn_pn", "equity_ratio", "dscr"):
        v = valori[k]
        pt = 2 if (k == "dscr" and v is None) else _punti(v, s[k][0], s[k][1], VERSO[k])
        punti += pt
        dettaglio.append(
            {"chiave": k, "indicatore": etichette[k], "valore": v, "punti": pt,
             "verde": s[k][0], "giallo": s[k][1], "verso": VERSO[k]}
        )

    if pn <= 0 or ebitda <= 0 or punti < 4:
        classe = CLASSI["ROSSA"]
    elif punti >= 7:
        classe = CLASSI["VERDE"]
    else:
        classe = CLASSI["GIALLA"]

    return {
        "pfn_ebitda": pfn_ebitda, "pfn_pn": pfn_pn, "equity_ratio": equity_ratio,
        "dscr": dscr, "punti": punti, "classe": classe, "dettaglio": dettaglio,
    }


# ----------------------------------------------------------------------------
# SCENARI
# ----------------------------------------------------------------------------
def esegui_scenario(dati, leve, piano_par, soglie=None, shock=None):
    """
    Calcola scenario + piano + rating. `leve`: delta_pfn, delta_pn, delta_ebitda.
    `shock` (stress test, opzionale): ebitda_pct, ricavi_pct, tasso_pp.
    L'aumento di capitale entra come liquidita': +PN, -PFN.
    """
    leve = {**LEVE_DEFAULT, **(leve or {})}
    sh = {"ebitda_pct": 0.0, "ricavi_pct": 0.0, "tasso_pp": 0.0, **(shock or {})}
    par = dict(piano_par)
    par["tasso"] = par["tasso"] + sh["tasso_pp"]

    scen = {
        "ricavi": dati["ricavi"] * (1 + sh["ricavi_pct"] / 100.0),
        "ebitda": (dati["ebitda"] + leve["delta_ebitda"]) * (1 + sh["ebitda_pct"] / 100.0),
        "pfn": dati["pfn"] + leve["delta_pfn"] - leve["delta_pn"],
        "pn": dati["patrimonio_netto"] + leve["delta_pn"],
        "attivo": dati["totale_attivo"] + leve["delta_pn"],
    }
    piano = proietta(scen["ricavi"], scen["ebitda"], scen["pfn"], par, dati["anno_riferimento"])
    rating = calcola_rating(scen["pfn"], scen["ebitda"], scen["pn"], scen["attivo"], piano[0]["DSCR"], soglie)
    return {"scen": scen, "piano": piano, "rating": rating, "leve": leve, "par": par}


def leva_minima(dati, leve, piano_par, soglie, leva, target="VERDE", step=5000.0, massimo=3_000_000.0):
    """
    Valore minimo (aggiuntivo) di una leva per raggiungere la fascia `target`
    (VERDE oppure GIALLA), tenendo fissi gli altri parametri.
    leva: 'delta_pn' (capitale), 'delta_ebitda', 'delta_pfn' (riduzione del debito, valore positivo).
    Restituisce il valore (>= 0) oppure None se non raggiungibile entro `massimo`.
    """
    obiettivo = 2 if target.upper() == "VERDE" else 1
    segno = -1.0 if leva == "delta_pfn" else 1.0
    base = {**LEVE_DEFAULT, **(leve or {})}
    # partiamo da zero sulla leva scelta, lasciando le altre come impostate
    base[leva] = 0.0
    k = 0
    while k * step <= massimo:
        prova = dict(base)
        prova[leva] = segno * k * step
        r = esegui_scenario(dati, prova, piano_par, soglie)
        if livello_classe(r["rating"]["classe"]) >= obiettivo:
            return k * step
        k += 1
    return None


STRESS_DEFAULT = [
    ("Scenario corrente", {}),
    ("EBITDA -10%", {"ebitda_pct": -10.0}),
    ("EBITDA -20%", {"ebitda_pct": -20.0}),
    ("Ricavi -10% / EBITDA -20%", {"ricavi_pct": -10.0, "ebitda_pct": -20.0}),
    ("Tassi +2 punti", {"tasso_pp": 2.0}),
    ("Combinato (ric. -10%, EBITDA -20%, tassi +2)", {"ricavi_pct": -10.0, "ebitda_pct": -20.0, "tasso_pp": 2.0}),
]


def stress_test(dati, leve, piano_par, soglie=None, casi=None):
    righe = []
    for nome, shock in (casi or STRESS_DEFAULT):
        r = esegui_scenario(dati, leve, piano_par, soglie, shock)
        dscr = [x["DSCR"] for x in r["piano"] if x["DSCR"] is not None]
        righe.append(
            {
                "Caso": nome,
                "PFN/EBITDA anno 3": r["piano"][-1]["PFN/EBITDA"],
                "DSCR minimo": min(dscr) if dscr else None,
                "Punteggio": r["rating"]["punti"],
                "Fascia": r["rating"]["classe"].split(" - ")[0].replace("FASCIA ", ""),
            }
        )
    return righe


def verifica_covenant(piano, cov):
    """Controlla i covenant su ogni anno del piano."""
    out = []
    for r in piano:
        ok_lev = r["PFN/EBITDA"] <= cov["pfn_ebitda_max"]
        dscr = r["DSCR"]
        ok_dscr = True if dscr is None else dscr >= cov["dscr_min"]
        margine = (
            (cov["pfn_ebitda_max"] - r["PFN/EBITDA"]) if not math.isinf(r["PFN/EBITDA"]) else -math.inf
        )
        out.append(
            {
                "Anno": r["Anno"], "PFN/EBITDA": r["PFN/EBITDA"], "Limite PFN/EBITDA": cov["pfn_ebitda_max"],
                "Esito leva": "OK" if ok_lev else "SFORATO", "DSCR": dscr, "Limite DSCR": cov["dscr_min"],
                "Esito DSCR": "OK" if ok_dscr else "SFORATO", "Margine leva (x)": margine,
            }
        )
    return out


# ----------------------------------------------------------------------------
# PORTAFOGLIO COMMESSE (settore costruzioni)
# ----------------------------------------------------------------------------
def commesse_vuote():
    return pd.DataFrame(
        [
            {"Commessa": "Esempio A", "Cliente": "Cliente 1", "Importo": 1_000_000.0,
             "Avanzamento_pct": 40.0, "Fatturato": 350_000.0, "Incassato": 250_000.0, "Margine_pct": 12.0},
        ],
        columns=COLONNE_COMMESSE,
    )


def analisi_commesse(df, ricavi_base=None):
    """
    KPI del portafoglio ordini. Restituisce (kpi: dict, per_cliente: DataFrame) oppure (None, None).
    - backlog          = importo residuo da eseguire
    - da_fatturare     = produzione eseguita - fatturato (negativo = anticipi/fatturato in eccesso)
    - crediti          = fatturato - incassato
    - margine_backlog  = margine medio ponderato sul backlog
    """
    if df is None or len(df) == 0:
        return None, None
    d = df.copy()
    for c in COLONNE_COMMESSE:
        if c not in d.columns:
            d[c] = 0.0 if c not in ("Commessa", "Cliente") else ""
    for c in ("Importo", "Avanzamento_pct", "Fatturato", "Incassato", "Margine_pct"):
        d[c] = d[c].apply(to_float)
    d["Avanzamento_pct"] = d["Avanzamento_pct"].clip(0, 100)
    d["Cliente"] = d["Cliente"].fillna("").astype(str).replace("", "(n.d.)")
    d = d[d["Importo"] > 0]
    if d.empty:
        return None, None

    d["Backlog"] = d["Importo"] * (1 - d["Avanzamento_pct"] / 100.0)
    d["Produzione"] = d["Importo"] * d["Avanzamento_pct"] / 100.0
    d["DaFatturare"] = d["Produzione"] - d["Fatturato"]
    d["Crediti"] = d["Fatturato"] - d["Incassato"]

    tot_importo = d["Importo"].sum()
    backlog = d["Backlog"].sum()
    per_cliente = (
        d.groupby("Cliente")[["Importo", "Backlog", "Crediti"]].sum().sort_values("Importo", ascending=False).reset_index()
    )
    per_cliente["Quota_pct"] = per_cliente["Importo"] / tot_importo * 100.0

    kpi = {
        "n_commesse": int(len(d)),
        "importo_totale": float(tot_importo),
        "backlog": float(backlog),
        "produzione_eseguita": float(d["Produzione"].sum()),
        "da_fatturare": float(d["DaFatturare"].sum()),
        "crediti": float(d["Crediti"].sum()),
        "margine_backlog_pct": float((d["Backlog"] * d["Margine_pct"]).sum() / backlog) if backlog > 0 else 0.0,
        "top1_pct": float(per_cliente["Quota_pct"].iloc[0]),
        "top3_pct": float(per_cliente["Quota_pct"].head(3).sum()),
        "copertura_ricavi": float(backlog / ricavi_base) if ricavi_base and ricavi_base > 0 else None,
    }
    return kpi, per_cliente


def copia(d):
    return copy.deepcopy(d)


# ----------------------------------------------------------------------------
# CONTROLLO DEI NUMERI NEL TESTO GENERATO DALL'AI
# ----------------------------------------------------------------------------
_RE_NUM = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")


def _raccogli_numeri(obj, out, profondita=0):
    if profondita > 6:
        return
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        if not (isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj))):
            out.add(abs(float(obj)))
    elif isinstance(obj, dict):
        for v in obj.values():
            _raccogli_numeri(v, out, profondita + 1)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _raccogli_numeri(v, out, profondita + 1)


def numeri_sospetti(testo, contesto, tolleranza=0.01):
    """
    Restituisce i numeri citati nel testo che non compaiono (entro tolleranza) tra i valori del
    contesto di calcolo. Serve a intercettare cifre inventate dall'AI; e' un controllo euristico.
    Sono ignorati i numeri piccoli (<= 10), gli anni e i numeri di elenco.
    """
    ammessi = set()
    _raccogli_numeri(contesto, ammessi)
    esteso = set()
    for v in ammessi:
        esteso.update({v, v * 100, v / 1000, v / 1_000_000, v * 1000})
    sospetti = []
    for m in _RE_NUM.finditer(testo or ""):
        grezzo = m.group(0)
        n = to_float(grezzo, None)
        if n is None or n <= 10 or (1990 <= n <= 2100 and "," not in grezzo and "." not in grezzo):
            continue
        if not any(abs(n - a) <= max(tolleranza * a, 0.51 if a > 50 else 0.051) for a in esteso):
            if grezzo not in sospetti:
                sospetti.append(grezzo)
    return sospetti


# ----------------------------------------------------------------------------
# FORMATTAZIONE DEL DETTAGLIO PUNTEGGIO (condivisa da app e report)
# ----------------------------------------------------------------------------
def valore_dettaglio(d):
    v = d["valore"]
    if d["chiave"] == "equity_ratio":
        return fmt_pct(100 * v)
    if v is None:
        return "n.d."
    return fmt_x(v)


def soglie_testo(d):
    if d["chiave"] == "equity_ratio":
        return f">= {fmt_pct(100 * d['verde'], 0)} / {fmt_pct(100 * d['giallo'], 0)}"
    segno = "<" if d["verso"] == "min" else ">="
    return f"{segno} {fmt_num(d['verde'], 2)} / {fmt_num(d['giallo'], 2)}"
