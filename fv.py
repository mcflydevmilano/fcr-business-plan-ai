"""
fv.py - Preventivo per impianti fotovoltaici: costi, prezzo al cliente, detrazione, produzione, risparmio e tempo di rientro. Senza Streamlit (testabile).

I costi unitari proposti sono STIME di mercato da verificare con i propri fornitori; resa, prezzi dell'energia e detrazione sono ipotesi che si modificano.
"""
import re

ZONE = {"Nord": 1100.0, "Centro": 1250.0, "Sud": 1400.0}          # kWh prodotti ogni anno per ogni kWp (orientamento buono, ombre trascurabili)
ORIENTAMENTI = {"Sud": 1.00, "Sud-Est / Sud-Ovest": 0.95, "Est / Ovest": 0.85, "Nord": 0.60}           # coefficienti indicativi sulla resa
INCLINAZIONI = {"Falda 30°": 1.00, "Falda 15-20°": 0.96, "Falda 40-45°": 0.97, "Tetto piano": 0.90}
REGIMI = {"Privato - prima casa (detrazione 50%)": {"detrazione_pct": 50.0, "iva_pct": 10.0},
          "Privato - altra abitazione (detrazione 36%)": {"detrazione_pct": 36.0, "iva_pct": 10.0},
          "Azienda o altro uso (nessuna detrazione, IVA 22%)": {"detrazione_pct": 0.0, "iva_pct": 22.0}}
TETTO_SPESA_DETRAZIONE = 96000.0                                                                         # spesa massima detraibile per unita' immobiliare
FV_DEFAULT = {
    "regime": "Privato - prima casa (detrazione 50%)", "orientamento": "Sud", "inclinazione": "Falda 30°", "ombra_pct": 0.0,
    "zona": "Centro", "resa": 1250.0, "wp_modulo": 430.0, "n_moduli": 8, "accumulo_kwh": 0.0,
    "consumo": 3500.0, "prezzo_acquisto": 0.30, "prezzo_cessione": 0.10, "autoconsumo_pct": 35.0,
    "aumento_energia_pct": 2.0, "degrado_pct": 0.5, "manutenzione_kwp": 20.0,
    "ricarico_pct": 20.0, "iva_pct": 10.0, "detrazione_pct": 50.0, "detrazione_anni": 10, "anni": 25,
}
COLONNE_VOCI = ["Voce", "Quantita", "Um", "Costo_unit"]
ETICHETTE_VOCI = {"Voce": "Voce", "Quantita": "Quantità", "Um": "U.M.", "Costo_unit": "Costo unitario €"}


def _f(v, d=0.0):
    try:
        if v is None or v != v:
            return d
        if isinstance(v, str):
            v = re.sub(r"[^\d,.\-]", "", v).replace(".", "").replace(",", ".") if "," in v else re.sub(r"[^\d.\-]", "", v)
        return float(v)
    except (TypeError, ValueError):
        return d


def potenza_kwp(p):
    return round(max(0.0, _f(p.get("n_moduli"))) * max(0.0, _f(p.get("wp_modulo"))) / 1000.0, 3)


def voci_standard(p):
    """Voci di partenza per la potenza indicata (costi di acquisto + posa, IVA esclusa): da correggere con i propri prezzi."""
    kwp, n, acc = potenza_kwp(p), max(0, int(_f(p.get("n_moduli")))), max(0.0, _f(p.get("accumulo_kwh")))
    v = [
        {"Voce": "Moduli fotovoltaici", "Quantita": n, "Um": "pz", "Costo_unit": round(_f(p.get("wp_modulo")) * 0.28, 2)},
        {"Voce": "Inverter", "Quantita": 1, "Um": "pz", "Costo_unit": round(max(600.0, kwp * 170), 2)},
        {"Voce": "Strutture di fissaggio", "Quantita": kwp, "Um": "kWp", "Costo_unit": 100.0},
        {"Voce": "Cavi, quadri e protezioni", "Quantita": kwp, "Um": "kWp", "Costo_unit": 80.0},
        {"Voce": "Installazione (manodopera)", "Quantita": kwp, "Um": "kWp", "Costo_unit": 280.0},
        {"Voce": "Sopralluogo e progetto", "Quantita": 1, "Um": "corpo", "Costo_unit": 400.0},
        {"Voce": "Collaudo e attivazione", "Quantita": 1, "Um": "corpo", "Costo_unit": 150.0},
        {"Voce": "Pratiche GSE e distributore", "Quantita": 1, "Um": "corpo", "Costo_unit": 500.0},
        {"Voce": "Sicurezza e ponteggi", "Quantita": 1, "Um": "corpo", "Costo_unit": 700.0},
    ]
    if acc > 0:
        v.insert(2, {"Voce": "Batteria di accumulo", "Quantita": acc, "Um": "kWh", "Costo_unit": 480.0})
    return [x for x in v if x["Quantita"]]


def normalizza_voci(righe):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        nome, q, c = str((r or {}).get("Voce") or "").strip(), _f((r or {}).get("Quantita")), _f((r or {}).get("Costo_unit"))
        if not nome and not q and not c:
            continue
        if not nome or q <= 0 or c < 0:
            avvisi.append(f"Riga {i}: servono voce e quantità maggiore di zero, riga ignorata.")
            continue
        out.append({"Voce": nome, "Quantita": q, "Um": str((r or {}).get("Um") or "").strip(), "Costo_unit": c})
    return out, avvisi


def autoconsumo_suggerito(p):
    """% della produzione consumata in casa: circa un terzo senza batteria, di piu' con l'accumulo, mai oltre il consumo reale."""
    prod = potenza_kwp(p) * _f(p.get("resa")) * ORIENTAMENTI.get(p.get("orientamento"), 1.0) * INCLINAZIONI.get(p.get("inclinazione"), 1.0) * (1 - _f(p.get("ombra_pct")) / 100)
    if prod <= 0:
        return 0.0
    cons = max(0.0, _f(p.get("consumo")))
    kwh = prod * 0.30 + min(_f(p.get("accumulo_kwh")) * 365 * 0.75, prod * 0.45)
    return round(min(kwh, cons, prod * 0.95) / prod * 100, 1)


def calcola(voci, p=None):
    q = {**FV_DEFAULT, **{k: v for k, v in (p or {}).items() if k in FV_DEFAULT}}
    kwp = potenza_kwp(q)
    costo = sum(v["Quantita"] * v["Costo_unit"] for v in voci)
    imponibile = round(costo * (1 + _f(q["ricarico_pct"]) / 100), 2)
    iva = round(imponibile * _f(q["iva_pct"]) / 100, 2)
    totale = round(imponibile + iva, 2)
    detr = round(min(totale, TETTO_SPESA_DETRAZIONE) * _f(q["detrazione_pct"]) / 100, 2)
    anni_d = max(1, int(_f(q["detrazione_anni"], 10)))
    prod1 = kwp * _f(q["resa"]) * ORIENTAMENTI.get(q["orientamento"], 1.0) * INCLINAZIONI.get(q["inclinazione"], 1.0) * (1 - min(100.0, max(0.0, _f(q["ombra_pct"]))) / 100)
    aut_pct = min(100.0, max(0.0, _f(q["autoconsumo_pct"])))
    cons = max(0.0, _f(q["consumo"]))
    flusso, cum, rientro = [], -totale, None
    for y in range(1, max(1, int(_f(q["anni"], 25))) + 1):
        prod = prod1 * (1 - _f(q["degrado_pct"]) / 100) ** (y - 1)
        auto = min(prod * aut_pct / 100, cons)
        immessa = prod - auto
        prezzo = _f(q["prezzo_acquisto"]) * (1 + _f(q["aumento_energia_pct"]) / 100) ** (y - 1)
        ris, ric = auto * prezzo, immessa * _f(q["prezzo_cessione"])
        man = kwp * _f(q["manutenzione_kwp"])
        d = detr / anni_d if y <= anni_d else 0.0
        netto = ris + ric + d - man
        prima = cum
        cum += netto
        if rientro is None and cum >= 0:
            rientro = round(y - 1 + (-prima / netto if netto else 0), 1)
        flusso.append({"Anno": y, "Produzione kWh": round(prod), "Risparmio €": round(ris), "Cessione €": round(ric), "Detrazione €": round(d), "Manutenzione €": round(-man), "Flusso €": round(netto), "Cumulato €": round(cum)})
    kpi = {"kwp": kwp, "costo": round(costo, 2), "imponibile": imponibile, "iva": iva, "totale": totale, "per_kwp": round(imponibile / kwp, 2) if kwp else 0.0,
           "margine": round(imponibile - costo, 2), "detrazione": detr, "netto_detrazione": round(totale - detr, 2), "produzione": round(prod1), "autoconsumo_kwh": round(min(prod1 * aut_pct / 100, cons)),
           "risparmio_anno1": flusso[0]["Risparmio €"] + flusso[0]["Cessione €"] if flusso else 0, "rientro_anni": rientro, "guadagno_finale": flusso[-1]["Cumulato €"] if flusso else 0,
           "copertura_pct": round(min(prod1 * aut_pct / 100, cons) / cons * 100, 1) if cons else 0.0}
    avvisi = []
    if kwp <= 0:
        avvisi.append("Indica numero e potenza dei moduli.")
    if kwp and kpi["per_kwp"] and not 900 <= kpi["per_kwp"] <= 2600:
        avvisi.append(f"Prezzo di {kpi['per_kwp']:.0f} €/kWp: fuori dal campo abituale (circa 1.000-2.200 €/kWp per impianti residenziali). Controlla costi e ricarico.")
    if kwp and _f(q["ombra_pct"]) > 15:
        avvisi.append("Ombreggiamento oltre il 15%: valuta ottimizzatori o microinverter e verifica la resa con uno studio delle ombre.")
    if kwp and totale > TETTO_SPESA_DETRAZIONE and _f(q["detrazione_pct"]):
        avvisi.append(f"La spesa supera {TETTO_SPESA_DETRAZIONE:,.0f} € per unità immobiliare: la detrazione è calcolata solo fino a quel tetto.".replace(",", "."))
    if kwp and cons and prod1 > cons * 1.6:
        avvisi.append("L'impianto produce molto più di quanto consumi: quasi tutto andrebbe in rete e il rientro si allunga.")
    return {"params": q, "kpi": kpi, "flusso": flusso, "avvisi": avvisi}


# --- Listino prezzi (si carica da Excel/CSV del fornitore) ---
COLONNE_LISTINO = ["Codice", "Descrizione", "Um", "Costo_unit", "Fornitore"]
_ALIAS = {"Codice": ("codice", "cod", "articolo", "sku", "art", "tariffa"), "Descrizione": ("descrizione", "designazione", "prodotto", "articolo", "voce", "modello", "nome"),
          "Um": ("um", "u.m", "unita", "unità", "misura"), "Costo_unit": ("prezzo", "costo", "listino", "importo", "netto", "euro", "€"), "Fornitore": ("fornitore", "marca", "produttore", "brand")}


def _campo(h):
    h = re.sub(r"\s+", " ", str(h or "").strip().lower())
    if not h or h == "nan":
        return None
    for campo in ("Costo_unit", "Um", "Fornitore", "Codice", "Descrizione"):                  # prima i campi piu' specifici
        if any(h == a or h.startswith(a) or (len(a) > 3 and a in h) for a in _ALIAS[campo]):
            return campo
    return None


def leggi_listino(dati, nome_file=""):
    """Legge un listino Excel o CSV cosi' com'e' (cerca da solo la riga delle intestazioni). Restituisce (righe, avvisi)."""
    import io
    import pandas as pd
    try:
        if str(nome_file).lower().endswith((".csv", ".txt")):
            testo = dati.decode("utf-8", "ignore") if isinstance(dati, (bytes, bytearray)) else str(dati)
            fogli = {"csv": pd.read_csv(io.StringIO(testo), header=None, sep=None, engine="python", dtype=str)}
        else:
            fogli = pd.read_excel(io.BytesIO(dati), sheet_name=None, header=None, dtype=str)
    except Exception as e:
        return [], [f"File non leggibile: {e}"]
    righe, avvisi = [], []
    for nome, df in fogli.items():
        mappa, riga_int = {}, None
        for i in range(min(40, len(df))):
            m = {}
            for j, h in enumerate(df.iloc[i].tolist()):
                c = _campo(h)
                if c and c not in m.values():
                    m[j] = c
            if "Costo_unit" in m.values() and "Descrizione" in m.values():
                mappa, riga_int = m, i
                break
        if riga_int is None:
            avvisi.append(f"Foglio «{nome}»: non ho trovato le colonne descrizione e prezzo.")
            continue
        for i in range(riga_int + 1, len(df)):
            r = {c: str(df.iat[i, j]).strip() if df.iat[i, j] == df.iat[i, j] else "" for j, c in mappa.items()}
            if not r.get("Descrizione") or r["Descrizione"] == "nan":
                continue
            prezzo = _f(r.get("Costo_unit"), -1.0)
            if prezzo < 0:
                continue
            righe.append({"Codice": r.get("Codice", ""), "Descrizione": r["Descrizione"], "Um": r.get("Um", ""), "Costo_unit": prezzo, "Fornitore": r.get("Fornitore", "")})
    return righe, avvisi
