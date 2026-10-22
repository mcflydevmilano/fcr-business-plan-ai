"""
rc.py - Registro commerciale: le pratiche dalla prima richiesta al contratto, con stato, valore, probabilita' di successo e prossimo intervento.
Legge il foglio Excel del registro (e quello degli «Eliminati»), calcola cruscotto per stato e per commerciale, avvisi e scadenze. Senza Streamlit.
"""
import datetime as dt
import io
import re

import pandas as pd

from sc import data_da

STATI = ["S0-Apertura Pratica", "S1-Sopralluogo", "S2-Offerta", "S3-Contratto", "S4-Progetto", "S5-Esecuzione", "S6-Offerta KO", "S7-Annullato", "S8-Da Validare", "S9-Sospeso"]
CHIUSI = {"S6-Offerta KO", "S7-Annullato"}
VINTI = {"S3-Contratto", "S4-Progetto", "S5-Esecuzione"}
ARCHIVI = ["Attiva", "Eliminata"]
COLONNE = ["Codice", "Inserita", "Sopralluogo", "Offerta", "Citta", "PR", "Indirizzo", "Amministratore", "Commerciale", "Affiancato", "Finanziamento", "UI", "Stato",
           "Lavori", "Prossimo", "Revisioni", "Scadenza", "Chi", "Valore", "Successo", "Note", "Banca", "Archivio"]
ETICHETTE = {"Codice": "Codice", "Inserita": "Data inserimento", "Sopralluogo": "Data sopralluogo", "Offerta": "Data offerta", "Citta": "Città", "PR": "Prov.", "Indirizzo": "Indirizzo",
             "Amministratore": "Amministratore", "Commerciale": "Commerciale", "Affiancato": "Affiancato da", "Finanziamento": "Finanziamento", "UI": "N. UI", "Stato": "Stato",
             "Lavori": "Tipo lavori", "Prossimo": "Prossimo intervento", "Revisioni": "Revisioni", "Scadenza": "Scadenza prossimo intervento", "Chi": "Chi lo deve fare",
             "Valore": "Valore stimato (€)", "Successo": "% successo", "Note": "Note", "Banca": "Banca", "Archivio": "Archivio"}
# intestazioni del file Excel (minuscole, senza accenti) -> colonna interna
ALIAS = {"codice": "Codice", "data inserimento pratica": "Inserita", "data inserimento": "Inserita", "data sopralluogo": "Sopralluogo", "data offerta": "Offerta", "citta": "Citta",
         "pr": "PR", "prov": "PR", "provincia": "PR", "indirizzo": "Indirizzo", "amministratore": "Amministratore", "commerciale": "Commerciale", "affiancato da": "Affiancato",
         "finanziamento": "Finanziamento", "n. ui": "UI", "n ui": "UI", "stato": "Stato", "tipo lavori": "Lavori", "prossimo intervento": "Prossimo", "revisioni": "Revisioni",
         "scadenza prossimo intervento": "Scadenza", "chi deve fare prossimo intervento": "Chi", "valore stimato da qte": "Valore", "valore stimato": "Valore",
         "% successo stimata": "Successo", "% successo": "Successo", "note": "Note", "banca": "Banca"}
COLONNE_DATE = ("Inserita", "Sopralluogo", "Offerta", "Scadenza")
RC_DEFAULT = {"preavviso_gg": 7}


def _t(v):
    if v is None or v is pd.NaT or (isinstance(v, float) and v != v):
        return ""
    return str(v).strip()


def _n(s):
    s = _t(s).lower()
    for a, b in (("à", "a"), ("è", "e"), ("é", "e"), ("ì", "i"), ("ò", "o"), ("ù", "u")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s)


def _num(v):
    if v is None or (isinstance(v, float) and v != v):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", _t(v))
    if not s:
        return 0.0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.match(r"^-?\d{1,3}(\.\d{3})+$", s):          # «250.000» all'italiana
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _data_txt(v):
    if v is None or v is pd.NaT or (isinstance(v, float) and v != v):
        return ""
    d = data_da(v)
    return d.isoformat() if d else _t(v)


def stato_canonico(v):
    """«s0-Apertura Pratica», «S2» o «Offerta» -> «S0-Apertura Pratica». Un valore sconosciuto resta com'e'."""
    t = _t(v)
    if not t:
        return ""
    m = re.match(r"^\s*s\s*(\d)\b", t, re.I)
    if m and int(m.group(1)) < len(STATI):
        return STATI[int(m.group(1))]
    for s in STATI:
        if _n(t) == _n(s) or _n(t) == _n(s.split("-", 1)[1]):
            return s
    return t


def percentuale(v):
    """50, 0.5 o «50%» -> 50.0 (percento)."""
    if isinstance(v, str) and "%" in v:
        return min(max(_num(v), 0.0), 100.0)
    x = _num(v)
    return min(max(x * 100 if 0 < x <= 1 else x, 0.0), 100.0)


def normalizza(righe):
    """Righe pulite (liste di dict con COLONNE). Scarta quelle completamente vuote. Restituisce (righe, avvisi)."""
    out, avvisi, visti = [], [], {}
    for i, r in enumerate(righe or [], start=1):
        r = {c: r.get(c) for c in COLONNE}
        if not any(_t(r[c]) for c in ("Codice", "Indirizzo", "Amministratore", "Citta", "Commerciale")):
            continue
        z = {c: _t(r[c]) for c in COLONNE}
        for c in COLONNE_DATE:
            z[c] = _data_txt(r[c])
        z["Stato"], z["Prossimo"] = stato_canonico(r["Stato"]), stato_canonico(r["Prossimo"])
        z["PR"] = z["PR"].upper()[:2]
        f = _n(z["Finanziamento"])
        z["Finanziamento"] = "sì" if f in ("si", "x", "yes", "true") else "no" if f in ("no", "n") else z["Finanziamento"]
        z["Valore"] = _num(r["Valore"])
        z["Successo"] = percentuale(r["Successo"])
        z["UI"] = int(_num(r["UI"]))
        z["Revisioni"] = int(_num(r["Revisioni"]))
        z["Archivio"] = "Eliminata" if _n(z["Archivio"]).startswith("elimin") else "Attiva"
        if z["Codice"]:
            if z["Codice"].lower() in visti and z["Archivio"] == "Attiva" and visti[z["Codice"].lower()] == "Attiva":
                avvisi.append(f"Riga {i}: il codice «{z['Codice']}» compare più di una volta.")
            visti[z["Codice"].lower()] = z["Archivio"]
        if z["Stato"] and z["Stato"] not in STATI:
            avvisi.append(f"Riga {i} ({z['Codice'] or z['Indirizzo']}): stato «{z['Stato']}» non riconosciuto.")
        out.append(z)
    return out, avvisi


def pipeline(r):
    return round(_num(r.get("Valore")) * _num(r.get("Successo")) / 100.0, 2)


def _colonna_intestazioni(riga):
    return {j: ALIAS[_n(v)] for j, v in enumerate(riga) if _n(v) in ALIAS}


def da_excel(sorgente):
    """Legge il file del registro. Prende i fogli «Registro» (pratiche attive) ed «Eliminati»; se non li trova usa il primo foglio con l'intestazione giusta.
    Restituisce (righe_grezze, rapporto)."""
    xls = pd.ExcelFile(sorgente)
    rapp = {"fogli": [], "righe": 0, "eliminate": 0, "saltati": []}
    fogli = []
    for nome in xls.sheet_names:
        n = _n(nome)
        if "eliminat" in n:
            fogli.append((nome, "Eliminata"))
        elif "registro" in n:
            fogli.append((nome, "Attiva"))
    if not fogli:
        fogli = [(nome, "Attiva") for nome in xls.sheet_names]
    righe = []
    for nome, arch in fogli:
        raw = pd.read_excel(xls, nome, header=None)
        h = next((i for i in range(min(len(raw), 15)) if len(_colonna_intestazioni(list(raw.iloc[i]))) >= 5 and "Codice" in _colonna_intestazioni(list(raw.iloc[i])).values()), None)
        if h is None:
            rapp["saltati"].append(nome)
            continue
        mappa = _colonna_intestazioni(list(raw.iloc[h]))
        n0 = len(righe)
        for _, riga in raw.iloc[h + 1:].iterrows():
            d = {c: riga.iloc[j] for j, c in mappa.items()}
            d["Archivio"] = arch
            righe.append(d)
        rapp["fogli"].append(nome)
    return righe, rapp


def importa_excel(sorgente):
    """(righe pulite, avvisi, rapporto). Il «Valore pipeline» del file non si legge: lo ricalcola l'app da valore e % di successo."""
    grezze, rapp = da_excel(sorgente)
    righe, avvisi = normalizza(grezze)
    rapp["righe"] = sum(1 for r in righe if r["Archivio"] == "Attiva")
    rapp["eliminate"] = sum(1 for r in righe if r["Archivio"] == "Eliminata")
    for s in rapp["saltati"]:
        avvisi.append(f"Il foglio «{s}» non ha l'intestazione del registro e non è stato letto.")
    return righe, avvisi, rapp


def calcola(righe, oggi=None, params=None):
    """Cruscotto: per stato, per commerciale, prossimi interventi e avvisi. `righe` gia' normalizzate."""
    oggi = oggi or dt.date.today()
    p = {**RC_DEFAULT, **(params or {})}
    att = [r for r in righe if r["Archivio"] == "Attiva"]
    eli = [r for r in righe if r["Archivio"] == "Eliminata"]
    per_stato = []
    for s in STATI:
        g = [r for r in att if r["Stato"] == s]
        per_stato.append({"Stato": s, "Pratiche": len(g), "Valore": round(sum(r["Valore"] for r in g), 2), "Pipeline": round(sum(pipeline(r) for r in g), 2)})
    senza = [r for r in att if r["Stato"] not in STATI]
    if senza:
        per_stato.append({"Stato": "(senza stato)", "Pratiche": len(senza), "Valore": round(sum(r["Valore"] for r in senza), 2), "Pipeline": round(sum(pipeline(r) for r in senza), 2)})
    aperte = [r for r in att if r["Stato"] not in CHIUSI]
    comm = {}
    for r in att:
        c = r["Commerciale"] or "(senza commerciale)"
        e = comm.setdefault(c, {"Commerciale": c, "Pratiche": 0, "Aperte": 0, "Valore aperte": 0.0, "Pipeline": 0.0, "Vinte": 0, "Perse": 0})
        e["Pratiche"] += 1
        if r["Stato"] in CHIUSI:
            e["Perse"] += 1
        else:
            e["Aperte"] += 1
            e["Valore aperte"] += r["Valore"]
            e["Pipeline"] += pipeline(r)
        if r["Stato"] in VINTI:
            e["Vinte"] += 1
    for e in comm.values():
        e["Valore aperte"], e["Pipeline"] = round(e["Valore aperte"], 2), round(e["Pipeline"], 2)
    da_fare = []
    for r in aperte:
        sc_ = data_da(r["Scadenza"])
        if not sc_ and not r["Prossimo"]:
            continue
        gg = (sc_ - oggi).days if sc_ else None
        stato = "nd" if gg is None else "bad" if gg < 0 else "warn" if gg <= p["preavviso_gg"] else "ok"
        da_fare.append({"Codice": r["Codice"], "Indirizzo": r["Indirizzo"], "Stato": r["Stato"], "Prossimo": r["Prossimo"], "Scadenza": r["Scadenza"], "Giorni": gg,
                        "Chi": r["Chi"] or r["Commerciale"], "Stato_scad": stato})
    da_fare.sort(key=lambda x: (x["Giorni"] is None, x["Giorni"] if x["Giorni"] is not None else 0))
    avvisi = []
    scad = [d for d in da_fare if d["Stato_scad"] == "bad"]
    if scad:
        avvisi.append(f"{len(scad)} prossimi interventi sono già scaduti (il più vecchio: {scad[0]['Codice']}, {-scad[0]['Giorni']} giorni fa).")
    n_sc = [r for r in aperte if not r["Commerciale"]]
    if n_sc:
        avvisi.append(f"{len(n_sc)} pratiche aperte non hanno un commerciale assegnato.")
    n_v = [r for r in att if r["Stato"] in ("S2-Offerta", *VINTI) and not r["Valore"]]
    if n_v:
        avvisi.append(f"{len(n_v)} pratiche da offerta in poi non hanno il valore stimato.")
    n_o = [r for r in att if r["Stato"] == "S2-Offerta" and not r["Offerta"]]
    if n_o:
        avvisi.append(f"{len(n_o)} offerte senza data offerta.")
    chiusi_v, chiusi_p = sum(1 for r in att if r["Stato"] in VINTI), sum(1 for r in att if r["Stato"] == "S6-Offerta KO")
    kpi = {"n_attive": len(att), "n_aperte": len(aperte), "n_eliminate": len(eli), "valore_aperte": round(sum(r["Valore"] for r in aperte), 2),
           "pipeline": round(sum(pipeline(r) for r in aperte), 2), "n_offerte": sum(1 for r in att if r["Stato"] == "S2-Offerta"),
           "valore_offerte": round(sum(r["Valore"] for r in att if r["Stato"] == "S2-Offerta"), 2), "n_vinte": chiusi_v, "valore_vinte": round(sum(r["Valore"] for r in att if r["Stato"] in VINTI), 2),
           "n_sospese": sum(1 for r in att if r["Stato"] == "S9-Sospeso"), "n_ko": chiusi_p, "n_scadute": len(scad), "n_in_scadenza": sum(1 for d in da_fare if d["Stato_scad"] == "warn"),
           "tasso_successo": round(100.0 * chiusi_v / (chiusi_v + chiusi_p), 1) if (chiusi_v + chiusi_p) else None}
    return {"kpi": kpi, "per_stato": per_stato, "per_commerciale": sorted(comm.values(), key=lambda e: -e["Pipeline"]), "da_fare": da_fare, "avvisi": avvisi}


def filtra(righe, testo="", stati=None, commerciali=None, archivio="Attiva"):
    """Righe che contengono tutte le parole cercate (in qualunque colonna di testo) e che rispettano i filtri."""
    toks = _n(testo).split()
    out = []
    for r in righe:
        if archivio and r["Archivio"] != archivio:
            continue
        if stati and r["Stato"] not in stati:
            continue
        if commerciali and (r["Commerciale"] or "(senza commerciale)") not in commerciali:
            continue
        blob = _n(" ".join(str(r[c]) for c in ("Codice", "Citta", "Indirizzo", "Amministratore", "Commerciale", "Affiancato", "Lavori", "Note", "Chi")))
        if all(t in blob for t in toks):
            out.append(r)
    return out


def excel_bytes(righe, out):
    """Excel con le pratiche, il riepilogo per stato e per commerciale e le cose da fare."""
    buf = io.BytesIO()
    att = [r for r in righe if r["Archivio"] == "Attiva"]
    eli = [r for r in righe if r["Archivio"] == "Eliminata"]

    def tab(rs):
        return pd.DataFrame([{ETICHETTE[c]: r[c] for c in COLONNE if c != "Archivio"} | {"Valore pipeline (€)": pipeline(r)} for r in rs])

    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        tab(att).to_excel(w, sheet_name="Pratiche", index=False)
        pd.DataFrame(out["per_stato"]).to_excel(w, sheet_name="Per stato", index=False)
        pd.DataFrame(out["per_commerciale"]).to_excel(w, sheet_name="Per commerciale", index=False)
        pd.DataFrame([{k: v for k, v in d.items() if k != "Stato_scad"} for d in out["da_fare"]]).to_excel(w, sheet_name="Da fare", index=False)
        if eli:
            tab(eli).to_excel(w, sheet_name="Eliminate", index=False)
        for ws in w.book.worksheets:
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(max(len(str(col[0].value or "")) + 2, 12), 40)
    return buf.getvalue()
