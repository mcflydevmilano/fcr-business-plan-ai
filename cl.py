"""cl.py - Computo di cantiere: lavori rimanenti con i prezzi aggiornati al nuovo prezzario.
Colonne di base come nel computo del Comune (N., codice E.P.U., descrizione, U.M., quantita', prezzo unitario, totale da esecutivo, coefficiente,
F x I, prezzario nuovo, differenza, % di aumento, prezzo aggiornato, totale aggiornato). Si possono aggiungere colonne libere."""
import io

COLONNE = ["N.", "Capitolo", "Codice E.P.U.", "Descrizione", "U.M.", "Quantità", "Prezzo unitario €", "Zona / note", "Coefficiente", "Prezzario nuovo €", "% di aumento",
           "Totale esecutivo a mano €", "Prezzo aggiornato a mano €", "Totale aggiornato a mano €"]
NUMERICHE = ["Quantità", "Prezzo unitario €", "Coefficiente", "Prezzario nuovo €", "% di aumento", "Totale esecutivo a mano €", "Prezzo aggiornato a mano €", "Totale aggiornato a mano €"]
TESTO = [c for c in COLONNE if c not in NUMERICHE]
COLONNE_RISULTATO = ["N.", "Capitolo", "Codice E.P.U.", "Descrizione", "U.M.", "Quantità", "Prezzo unitario €", "Totale da esecutivo €", "Zona / note", "Coefficiente", "F x I €",
                     "Prezzario nuovo €", "Differenza €", "% di aumento", "Aumento €", "Prezzo aggiornato €", "Totale aggiornato €"]
COEFF_BASE, PERC_BASE = 1.05, 0.8
MAX_EXTRA = 12
# nomi di colonna accettati quando si importa un Excel (minuscolo, senza spazi doppi)
ALIAS = {"n.": "N.", "n": "N.", "capitolo": "Capitolo", "codice e.p.u.": "Codice E.P.U.", "codice": "Codice E.P.U.", "codice epu": "Codice E.P.U.", "descrizione": "Descrizione",
         "u.m.": "U.M.", "um": "U.M.", "quantità": "Quantità", "quantita": "Quantità", "prezzo unitario €": "Prezzo unitario €", "prezzo unitario": "Prezzo unitario €",
         "prezzo unitario in euro": "Prezzo unitario €", "zona / note": "Zona / note", "note": "Zona / note", "zona": "Zona / note", "coefficiente": "Coefficiente",
         "coefficiente moltiplicatore": "Coefficiente", "prezzario nuovo €": "Prezzario nuovo €", "prezzario": "Prezzario nuovo €", "prezzario 2025": "Prezzario nuovo €",
         "% di aumento": "% di aumento", "percentuale di aumento": "% di aumento", "totale esecutivo a mano €": "Totale esecutivo a mano €", "totale da esecutivo €": "Totale esecutivo a mano €",
         "prezzo aggiornato a mano €": "Prezzo aggiornato a mano €", "totale aggiornato a mano €": "Totale aggiornato a mano €"}


def _n(v):
    """Numero oppure None (cella vuota). Accetta anche '1.234,56' e '€ 12,50'."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return None if v != v else float(v)
    s = str(v).replace("€", "").replace(" ", "").strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        x = float(s)
    except ValueError:
        return None
    return -x if neg else x


def _t(v):
    return "" if v is None or (isinstance(v, float) and v != v) else str(v).strip()


def normalizza(righe, extra=()):
    """Righe pulite: testo come testo, numeri come numeri o None. Scarta le righe del tutto vuote."""
    out = []
    for r in righe or []:
        if not isinstance(r, dict):
            continue
        z = {c: _t(r.get(c)) for c in TESTO}
        z.update({c: _n(r.get(c)) for c in NUMERICHE})
        z.update({c: _t(r.get(c)) for c in extra})
        if not (z["Codice E.P.U."] or z["Descrizione"] or any(z[c] is not None for c in NUMERICHE)):
            continue
        out.append(z)
    return out


def calcola_riga(r):
    """Tutte le colonne del computo per una riga. Dove manca il coefficiente o il prezzario nuovo, il prezzo resta quello di progetto."""
    q, pu, coef, prz, perc = r.get("Quantità"), r.get("Prezzo unitario €"), r.get("Coefficiente"), r.get("Prezzario nuovo €"), r.get("% di aumento")
    tot = r.get("Totale esecutivo a mano €")
    if tot is None and q is not None and pu is not None:
        tot = q * pu
    fxi = pu * coef if pu is not None and coef else None
    diff = prz - fxi if prz is not None and fxi is not None else None
    aum = diff * perc if diff is not None and perc else None
    agg = r.get("Prezzo aggiornato a mano €")
    if agg is None:
        agg = pu + aum if pu is not None and aum is not None else pu
    tota = r.get("Totale aggiornato a mano €")
    if tota is None:
        tota = q * agg if q is not None and agg is not None else tot
    return {"Totale da esecutivo €": tot, "F x I €": fxi, "Differenza €": diff, "Aumento €": aum, "Prezzo aggiornato €": agg, "Totale aggiornato €": tota}


def calcola(righe, extra=()):
    """{'righe': [...colonne del computo...], 'tot_esecutivo', 'tot_aggiornato', 'differenza', 'aumento_pct', 'per_capitolo', 'avvisi'}"""
    out, avvisi = [], []
    te = ta = 0.0
    capitoli = {}
    for i, r in enumerate(righe, 1):
        c = calcola_riga(r)
        riga = {k: r.get(k) for k in COLONNE_RISULTATO if k in r}
        riga.update(c)
        riga.update({k: r.get(k, "") for k in extra})
        out.append({k: riga.get(k) for k in list(COLONNE_RISULTATO) + list(extra)})
        e, a = c["Totale da esecutivo €"] or 0.0, c["Totale aggiornato €"] or 0.0
        te += e
        ta += a
        cap = r.get("Capitolo") or "(senza capitolo)"
        capitoli.setdefault(cap, [0.0, 0.0])
        capitoli[cap][0] += e
        capitoli[cap][1] += a
        nome = r.get("Codice E.P.U.") or f"riga {i}"
        if c["Totale da esecutivo €"] is None:
            avvisi.append(f"{nome}: mancano quantità e prezzo, la riga vale zero.")
        elif c["Aumento €"] is not None and c["Aumento €"] < 0 and r.get("Prezzo aggiornato a mano €") is None:
            avvisi.append(f"{nome}: il prezzario nuovo è più basso del prezzo di progetto rivalutato, quindi il prezzo scende.")
    return {"righe": out, "tot_esecutivo": round(te, 2), "tot_aggiornato": round(ta, 2), "differenza": round(ta - te, 2), "aumento_pct": round((ta / te - 1) * 100, 2) if te else 0.0,
            "per_capitolo": [{"Capitolo": k, "Totale da esecutivo €": round(v[0], 2), "Totale aggiornato €": round(v[1], 2)} for k, v in capitoli.items()], "avvisi": avvisi}


def da_excel(dati, extra=()):
    """Legge un Excel con le colonne del computo (in qualunque ordine). Le colonne sconosciute diventano colonne aggiunte. -> (righe, extra, avvisi)"""
    import pandas as pd
    df = pd.read_excel(io.BytesIO(dati), header=None)
    riga_tit = 0
    for i in range(min(len(df), 15)):                       # l'intestazione e' la prima riga che contiene «descrizione»
        if any(str(v).strip().lower() == "descrizione" for v in df.iloc[i].tolist()):
            riga_tit = i
            break
    tit = [_t(v) for v in df.iloc[riga_tit].tolist()]
    mappa, nuove = {}, list(extra)
    for j, t in enumerate(tit):
        if not t:
            continue
        k = ALIAS.get(" ".join(t.lower().split()))
        if k:
            mappa[j] = k
        elif t not in COLONNE_RISULTATO and len(nuove) < MAX_EXTRA:
            if t not in nuove:
                nuove.append(t)
            mappa[j] = t
    if "Descrizione" not in mappa.values():
        return [], list(extra), ["Non trovo la colonna «Descrizione»: usa il modello Excel scaricabile qui sotto."]
    righe = [{mappa[j]: v for j, v in enumerate(riga) if j in mappa} for riga in df.iloc[riga_tit + 1:].values.tolist()]
    righe = normalizza(righe, nuove)
    return righe, nuove, [f"Lette {len(righe)} righe."]


def excel_bytes(righe, extra=(), titolo="Computo", etichette=("progetto", "aggiornato")):
    import pandas as pd
    out = calcola(righe, extra)
    b = io.BytesIO()
    with pd.ExcelWriter(b, engine="openpyxl") as w:
        pd.DataFrame(out["righe"], columns=list(COLONNE_RISULTATO) + list(extra)).to_excel(w, index=False, sheet_name="Computo")
        pd.DataFrame([{"Voce": f"Totale {etichette[0]}", "€": out["tot_esecutivo"]}, {"Voce": f"Totale {etichette[1]}", "€": out["tot_aggiornato"]},
                      {"Voce": "Differenza", "€": out["differenza"]}, {"Voce": "Aumento %", "€": out["aumento_pct"]}]).to_excel(w, index=False, sheet_name="Riepilogo")
        pd.DataFrame(out["per_capitolo"]).to_excel(w, index=False, sheet_name="Per capitolo")
        pd.DataFrame(righe, columns=list(COLONNE) + list(extra)).to_excel(w, index=False, sheet_name="Dati da reimportare")
        ws = w.sheets["Computo"]
        ws.column_dimensions["D"].width = 70
        for col in "BCEFGHIJKLMNOPQ":
            ws.column_dimensions[col].width = 16
        ws.freeze_panes = "A2"
    return b.getvalue()


def modello_excel():
    import pandas as pd
    b = io.BytesIO()
    pd.DataFrame([{"N.": "1", "Capitolo": "MASSETTI", "Codice E.P.U.": "E.13.002.00", "Descrizione": "Massetto in sabbia e cemento spessore cm 4", "U.M.": "m²", "Quantità": 100.0,
                   "Prezzo unitario €": 17.24, "Zona / note": "Piano terra", "Coefficiente": COEFF_BASE, "Prezzario nuovo €": 23.26, "% di aumento": PERC_BASE}],
                 columns=COLONNE).to_excel(b, index=False, sheet_name="Computo")
    return b.getvalue()
