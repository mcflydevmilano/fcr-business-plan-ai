"""mi.py - Controllo impianti ESCo dopo la vendita: produzione reale contro attesa, canoni incassati, manutenzione."""
import datetime as dt
import uuid

import storage

NOME_CFG = "impianti_esco"
PROFILO_FV = [0.045, 0.060, 0.089, 0.107, 0.125, 0.133, 0.141, 0.126, 0.098, 0.066, 0.040, 0.034]     # quota di produzione annua per mese (Italia, indicativa)
KWH_PER_KWP = 1200.0
SOGLIA_OK, SOGLIA_BAD = 95.0, 85.0
PREAVVISO_MANUT = 30
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
COLONNE = ["Nome", "Cliente", "kWp", "Inizio", "Attesa annua kWh", "Canone mensile €", "Prossima manutenzione"]


def _f(v, d=0.0):
    try:
        x = float(str(v).replace(",", "."))
        return x if x == x else d
    except (TypeError, ValueError):
        return d


def _data(v):
    if isinstance(v, dt.date):
        return v.isoformat()
    try:
        return dt.date.fromisoformat(str(v)[:10]).isoformat()
    except (TypeError, ValueError):
        return ""


def _ym(v):
    s = str(v)[:7]
    try:
        a, m = int(s[:4]), int(s[5:7])
        return f"{a:04d}-{m:02d}" if 1 <= m <= 12 else ""
    except ValueError:
        return ""


def nuovo():
    return {"id": uuid.uuid4().hex[:8], "nome": "", "cliente": "", "kwp": 0.0, "inizio": "", "attesa_annua": 0.0, "canone": 0.0, "manutenzione": "", "letture": {}, "incassi": {}}


def normalizza(impianti):
    out = []
    for r in impianti or []:
        if not isinstance(r, dict) or not str(r.get("nome", "")).strip():
            continue
        out.append({"id": str(r.get("id") or uuid.uuid4().hex[:8]), "nome": str(r["nome"]).strip(), "cliente": str(r.get("cliente") or "").strip(), "kwp": max(0.0, _f(r.get("kwp"))),
                    "inizio": _data(r.get("inizio")), "attesa_annua": max(0.0, _f(r.get("attesa_annua"))), "canone": max(0.0, _f(r.get("canone"))),
                    "manutenzione": _data(r.get("manutenzione")),
                    "letture": {_ym(k): max(0.0, _f(v)) for k, v in (r.get("letture") or {}).items() if _ym(k) and v not in (None, "")},
                    "incassi": {_ym(k): max(0.0, _f(v)) for k, v in (r.get("incassi") or {}).items() if _ym(k) and v not in (None, "")}})
    return out


def attesa_mese(imp, ym):
    annua = imp.get("attesa_annua") or imp.get("kwp", 0) * KWH_PER_KWP
    return annua * PROFILO_FV[int(ym[5:7]) - 1] / sum(PROFILO_FV)


def mesi_chiusi(imp, oggi, n=12):
    """Gli ultimi n mesi finiti (non quello in corso), a partire dall'inizio del contratto."""
    y, m = oggi.year, oggi.month
    out = []
    for _ in range(n):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        ym = f"{y:04d}-{m:02d}"
        if imp.get("inizio") and ym < imp["inizio"][:7]:
            break
        out.append(ym)
    return out[::-1]


def stato_perc(p):
    return "ok" if p >= SOGLIA_OK else "warn" if p >= SOGLIA_BAD else "bad"


def analisi(imp, oggi=None, n=12):
    oggi = oggi or dt.date.today()
    righe = []
    for ym in mesi_chiusi(imp, oggi, n):
        att = attesa_mese(imp, ym)
        let = imp["letture"].get(ym)
        perc = round(let / att * 100, 1) if let is not None and att > 0 else None
        inc = imp["incassi"].get(ym)
        righe.append({"mese": ym, "atteso": round(att), "letto": let, "perc": perc, "stato": stato_perc(perc) if perc is not None else "manca",
                      "canone": imp["canone"], "incassato": inc, "canone_ok": (imp["canone"] <= 0) or (inc is not None and inc >= imp["canone"] * 0.99)})
    return righe


def etichetta_mese(ym):
    return f"{MESI[int(ym[5:7]) - 1]} {ym[:4]}"


def manutenzione(imp, oggi=None):
    oggi = oggi or dt.date.today()
    if not imp.get("manutenzione"):
        return None, ""
    g = (dt.date.fromisoformat(imp["manutenzione"]) - oggi).days
    return g, "bad" if g < 0 else "warn" if g <= PREAVVISO_MANUT else "ok"


def avvisi(impianti, oggi=None):
    """[(stato, frase)] da portare nel riepilogo del mattino; solo i problemi."""
    oggi = oggi or dt.date.today()
    out = []
    for imp in impianti:
        a = analisi(imp, oggi, 12)
        if a:
            u = a[-1]
            if u["stato"] == "manca":
                out.append(("warn", f"{imp['nome']}: manca la lettura di {etichetta_mese(u['mese'])}"))
            elif u["stato"] in ("warn", "bad"):
                out.append((u["stato"], f"{imp['nome']}: {etichetta_mese(u['mese'])} al {u['perc']:.0f}% dell'atteso"))
        mancanti = [x for x in a if not x["canone_ok"]]
        if mancanti:
            out.append(("bad", f"{imp['nome']}: canone non incassato per {len(mancanti)} " + ("mese" if len(mancanti) == 1 else "mesi") + f" (l'ultimo: {etichetta_mese(mancanti[-1]['mese'])})"))
        g, st_ = manutenzione(imp, oggi)
        if st_ in ("bad", "warn"):
            out.append((st_, f"{imp['nome']}: manutenzione " + (f"scaduta da {-g} giorni" if g < 0 else f"tra {g} giorni")))
    return sorted(out, key=lambda x: 0 if x[0] == "bad" else 1)


def riepilogo(impianti, oggi=None):
    oggi = oggi or dt.date.today()
    tot_att = tot_let = 0.0
    insoluti = 0
    for imp in impianti:
        for r in analisi(imp, oggi, 12):
            if r["letto"] is not None:
                tot_att += r["atteso"]
                tot_let += r["letto"]
        insoluti += sum(1 for r in analisi(imp, oggi, 12) if not r["canone_ok"])
    av = avvisi(impianti, oggi)
    return {"impianti": len(impianti), "kwp": round(sum(i["kwp"] for i in impianti), 1), "perc": round(tot_let / tot_att * 100, 1) if tot_att else None,
            "insoluti": insoluti, "avvisi": len(av)}


def carica(path=None):
    try:
        raw = storage.carica_pratica(NOME_CFG, path, modulo="cfg")
    except Exception:
        raw = None
    return normalizza(raw.get("impianti") if isinstance(raw, dict) else None)


def salva(impianti, autore="", path=None):
    storage.salva_pratica(NOME_CFG, {"impianti": normalizza(impianti)}, path, autore=autore, modulo="cfg")
    storage.svuota_cache()


def excel_bytes(impianti, oggi=None):
    import io
    import pandas as pd
    righe = []
    for imp in impianti:
        for r in analisi(imp, oggi, 24):
            righe.append({"Impianto": imp["nome"], "Cliente": imp["cliente"], "Mese": r["mese"], "Atteso kWh": r["atteso"], "Letto kWh": r["letto"], "% sull'atteso": r["perc"],
                          "Canone €": r["canone"], "Incassato €": r["incassato"]})
    b = io.BytesIO()
    pd.DataFrame(righe, columns=["Impianto", "Cliente", "Mese", "Atteso kWh", "Letto kWh", "% sull'atteso", "Canone €", "Incassato €"]).to_excel(b, index=False, sheet_name="Impianti")
    return b.getvalue()
