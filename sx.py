"""
sx.py - Sicurezza e documenti di cantiere: scadenze di formazione e idoneita' del personale, documenti obbligatori per cantiere.
Strumento di promemoria: non sostituisce il RSPP/CSE ne' la verifica degli obblighi di legge.
"""
from core import to_float
from sc import data_da
from scad import conta, oggi_da, peggiore, stato_scadenza

SX_DEFAULT = {"oggi": None, "preavviso_gg": 30}
COLONNE_PERS = ["Persona", "Ruolo", "Cantiere", "Documento", "Scadenza"]
ETICHETTE_PERS = {"Persona": "Persona", "Ruolo": "Ruolo", "Cantiere": "Cantiere", "Documento": "Formazione / idoneità", "Scadenza": "Scadenza"}
COLONNE_DOCC = ["Cantiere", "Documento", "Presente", "Scadenza"]
ETICHETTE_DOCC = {"Cantiere": "Cantiere", "Documento": "Documento di cantiere", "Presente": "Presente", "Scadenza": "Scadenza (se c'è)"}
CORSI = ["Formazione generale", "Formazione specifica", "Aggiornamento", "Visita medica", "Addetto antincendio", "Primo soccorso", "Lavori in quota"]
DOC_CANTIERE = ["Notifica preliminare", "PSC (piano di sicurezza e coordinamento)", "POS (piano operativo di sicurezza)", "DURC delle imprese",
                "Verifica idoneità tecnico-professionale", "Cartello di cantiere", "Registro presenze"]
SINONIMI_PERS = {"Persona": ("Nome", "Lavoratore", "Dipendente", "Cognome e nome"), "Documento": ("Corso", "Attestato", "Formazione", "Idoneità"), "Scadenza": ("Data scadenza", "Valido fino al")}


def _vero(v):
    if isinstance(v, str):
        return v.strip().lower() in ("1", "si", "sì", "s", "true", "x", "ok", "yes", "presente")
    return bool(v) if v == v else False


def normalizza_pers(righe):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(str(r.get(c) or "").strip() for c in COLONNE_PERS):
            continue
        n, d = str(r.get("Persona") or "").strip(), str(r.get("Documento") or "").strip()
        if not n or not d:
            avvisi.append(f"Riga {i} del personale: servono persona e documento, riga ignorata.")
            continue
        s = data_da(r.get("Scadenza"))
        out.append({"Persona": n, "Ruolo": str(r.get("Ruolo") or "").strip(), "Cantiere": str(r.get("Cantiere") or "").strip(), "Documento": d, "Scadenza": s.isoformat() if s else ""})
    return out, avvisi


def normalizza_docc(righe):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(str(r.get(c) or "").strip() for c in ("Cantiere", "Documento", "Scadenza")) and not _vero(r.get("Presente")):
            continue
        c, d = str(r.get("Cantiere") or "").strip(), str(r.get("Documento") or "").strip()
        if not c or not d:
            avvisi.append(f"Riga {i} dei documenti di cantiere: servono cantiere e documento, riga ignorata.")
            continue
        s = data_da(r.get("Scadenza"))
        out.append({"Cantiere": c, "Documento": d, "Presente": _vero(r.get("Presente")), "Scadenza": s.isoformat() if s else ""})
    return out, avvisi


def calcola_sx(pers, docc, p=None):
    q = {**SX_DEFAULT, **(p or {})}
    oggi, prev = oggi_da(q), int(max(0, to_float(q["preavviso_gg"], 30)))
    rp = []
    for x in pers:
        st, g = stato_scadenza(x["Scadenza"], oggi, prev)
        rp.append({**x, "Stato": st, "Giorni": g})
    persone, avvisi = [], []
    for n in sorted({x["Persona"] for x in rp}):
        m = [x for x in rp if x["Persona"] == n]
        persone.append({"Persona": n, "Ruolo": m[0]["Ruolo"], "Cantiere": m[0]["Cantiere"], "Scaduti": sum(1 for x in m if x["Stato"] == "bad"),
                        "In scadenza": sum(1 for x in m if x["Stato"] == "warn"), "Stato": peggiore([x["Stato"] for x in m]),
                        "Scaduti elenco": ", ".join(x["Documento"] for x in m if x["Stato"] == "bad")})
    rd = []
    for x in docc:
        st, g = stato_scadenza(x["Scadenza"], oggi, prev) if x["Scadenza"] else ("ok", None)
        if not x["Presente"]:
            st = "bad"
        rd.append({**x, "Stato": st, "Giorni": g})
    cantieri = []
    for c in sorted({x["Cantiere"] for x in rd} | {x["Cantiere"] for x in rp if x["Cantiere"]}):
        dc = [x for x in rd if x["Cantiere"] == c]
        pc = [x for x in persone if x["Cantiere"] == c]
        manc = [x["Documento"] for x in dc if not x["Presente"]]
        scad_d = [x["Documento"] for x in dc if x["Presente"] and x["Stato"] == "bad"]
        non_id = [x["Persona"] for x in pc if x["Stato"] == "bad"]
        stato = "bad" if (manc or scad_d or non_id) else ("warn" if any(x["Stato"] == "warn" for x in dc) or any(x["Stato"] == "warn" for x in pc) else "ok")
        cantieri.append({"Cantiere": c, "Persone": len(pc), "Persone non in regola": len(non_id), "Documenti mancanti": len(manc), "Documenti scaduti": len(scad_d), "Stato": stato})
        if manc:
            avvisi.append(f"{c}: mancano {len(manc)} documenti di cantiere ({', '.join(manc[:3])}{'...' if len(manc) > 3 else ''}).")
        if non_id:
            avvisi.append(f"{c}: persone con formazione o idoneità scaduta: {', '.join(non_id)}.")
    cp = conta([x["Stato"] for x in rp])
    kpi = {"n_persone": len(persone), "scaduti": cp["bad"], "in_scadenza": cp["warn"], "ok": cp["ok"], "persone_non_in_regola": sum(1 for x in persone if x["Stato"] == "bad"),
           "doc_mancanti": sum(1 for x in rd if not x["Presente"]), "doc_scaduti": sum(1 for x in rd if x["Presente"] and x["Stato"] == "bad"),
           "n_cantieri": len(cantieri), "cantieri_a_rischio": sum(1 for x in cantieri if x["Stato"] == "bad")}
    return {"params": {"oggi": oggi, "preavviso_gg": prev}, "scadenze": rp, "persone": persone, "documenti": rd, "cantieri": cantieri, "kpi": kpi, "avvisi": avvisi}
