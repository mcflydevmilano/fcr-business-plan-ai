"""
sd.py - Scadenze di persone e mezzi: formazione sulla sicurezza, visite mediche, DURC, assicurazioni, revisioni.
Un elenco unico, con avvisi a 60, 30 e 7 giorni dalla scadenza. Senza Streamlit (testabile).
"""
import datetime as dt
import io
import re
import uuid

import storage
from sc import data_da

NOME_CFG = "scadenze_doc"
TIPI = ["Formazione sicurezza", "Visita medica", "Abilitazione / patentino", "DURC", "Assicurazione / polizza", "Revisione mezzo", "Bollo / tagliando mezzo", "Certificazione", "Altro"]
PREAVVISI_BASE = [60, 30, 7]
COLONNE = ["Tipo", "Soggetto", "Scadenza", "Responsabile", "Note"]
STATI = {"scaduto": ("🔴", "Scaduto", "bad"), "urgente": ("🟠", "Entro 7 giorni", "bad"), "vicino": ("🟡", "Entro 30 giorni", "warn"),
         "attenzione": ("🟢", "Entro 60 giorni", "ok"), "ok": ("⚪", "Più avanti", "ok"), "senza": ("❔", "Senza data", "nd")}


def _t(v):
    return "" if v is None or (isinstance(v, float) and v != v) else str(v).strip()


def normalizza(righe):
    """Righe pulite con id stabile. Scarta quelle senza soggetto e senza tipo."""
    out = []
    for r in righe or []:
        z = {"id": _t(r.get("id")) or uuid.uuid4().hex[:8], "Tipo": _t(r.get("Tipo")) or "Altro", "Soggetto": _t(r.get("Soggetto"))[:120],
             "Responsabile": _t(r.get("Responsabile"))[:80], "Note": _t(r.get("Note"))[:300]}
        d = data_da(r.get("Scadenza"))
        z["Scadenza"] = d.isoformat() if d else ""
        if not z["Soggetto"] and not d:
            continue
        out.append(z)
    return out


def stato(voce, oggi=None, preavvisi=None):
    """(chiave stato, giorni mancanti o None)."""
    oggi = oggi or dt.date.today()
    d = data_da(voce.get("Scadenza"))
    if not d:
        return "senza", None
    g = (d - oggi).days
    p = sorted(preavvisi or PREAVVISI_BASE)
    if g < 0:
        return "scaduto", g
    if g <= (p[0] if p else 7):
        return "urgente", g
    if g <= (p[1] if len(p) > 1 else 30):
        return "vicino", g
    if g <= (p[-1] if p else 60):
        return "attenzione", g
    return "ok", g


def elenco(voci, oggi=None, preavvisi=None):
    """Voci arricchite con stato e giorni, dalla piu' urgente."""
    out = []
    for v in voci or []:
        s, g = stato(v, oggi, preavvisi)
        out.append({**v, "stato": s, "giorni": g})
    out.sort(key=lambda x: (x["giorni"] is None, x["giorni"] if x["giorni"] is not None else 0))
    return out


def riepilogo(voci, oggi=None, preavvisi=None):
    c = {k: 0 for k in STATI}
    for v in elenco(voci, oggi, preavvisi):
        c[v["stato"]] += 1
    return c


def da_avvisare(voci, oggi=None, preavvisi=None):
    """Voci scadute o che scadono entro il primo preavviso: sono quelle da citare nel riepilogo del mattino."""
    return [v for v in elenco(voci, oggi, preavvisi) if v["stato"] in ("scaduto", "urgente", "vicino", "attenzione")]


def frase(v):
    g = v["giorni"]
    quando = f"scaduto da {-g} giorni" if g < 0 else "scade oggi" if g == 0 else f"scade tra {g} giorni"
    return f"{v['Tipo']} · {v['Soggetto'] or '(senza nome)'}: {quando}"


def carica(path=None):
    try:
        raw = storage.carica_pratica(NOME_CFG, path, modulo="cfg")
    except Exception:
        raw = None
    raw = raw if isinstance(raw, dict) else {}
    pre = sorted({int(x) for x in raw.get("preavvisi") or [] if str(x).isdigit() and 1 <= int(x) <= 365}) or list(PREAVVISI_BASE)
    return {"voci": normalizza(raw.get("voci")), "preavvisi": pre[:3] if len(pre) > 3 else pre}


def salva(cfg, autore="", path=None):
    dati = {"voci": normalizza(cfg.get("voci")), "preavvisi": cfg.get("preavvisi") or list(PREAVVISI_BASE)}
    storage.salva_pratica(NOME_CFG, dati, path, autore=autore, modulo="cfg")
    storage.svuota_cache()
    return dati


def soggetti_noti(path=None):
    """Nomi gia' presenti nel programma (persone dell'Organico e mezzi), per scegliere senza riscrivere."""
    nomi = []
    for modulo, chiavi in (("pe", ("persone", "Persona")), ("og", ("organico", "Nome")), ("mz", ("mezzi", "Mezzo"))):
        try:
            el = storage.elenca_pratiche(path, modulo=modulo)
            if not el:
                continue
            p = storage.carica_pratica(el[0]["nome"], path, modulo) or {}
            for r in p.get(chiavi[0]) or []:
                n = _t(r.get(chiavi[1]))
                if n and n not in nomi:
                    nomi.append(n)
        except Exception:
            continue
    return nomi


def da_excel(sorgente):
    """Legge un Excel/CSV con colonne tipo, soggetto/nome/mezzo, scadenza. Restituisce le righe normalizzate."""
    import pandas as pd
    try:
        df = pd.read_excel(sorgente)
    except Exception:
        sorgente.seek(0) if hasattr(sorgente, "seek") else None
        df = pd.read_csv(sorgente, sep=None, engine="python")
    alias = {"tipo": "Tipo", "documento": "Tipo", "corso": "Tipo", "soggetto": "Soggetto", "nome": "Soggetto", "persona": "Soggetto", "mezzo": "Soggetto", "targa": "Soggetto",
             "scadenza": "Scadenza", "data scadenza": "Scadenza", "scade": "Scadenza", "responsabile": "Responsabile", "note": "Note"}
    df = df.rename(columns={c: alias.get(re.sub(r"\s+", " ", str(c)).strip().lower(), c) for c in df.columns})
    return normalizza(df.to_dict("records"))


def excel_bytes(voci, oggi=None, preavvisi=None):
    import pandas as pd
    righe = [{"Stato": STATI[v["stato"]][1], "Tipo": v["Tipo"], "Soggetto": v["Soggetto"], "Scadenza": v["Scadenza"], "Giorni": v["giorni"], "Responsabile": v["Responsabile"], "Note": v["Note"]}
             for v in elenco(voci, oggi, preavvisi)]
    b = io.BytesIO()
    pd.DataFrame(righe).to_excel(b, index=False, sheet_name="Scadenze")
    return b.getvalue()
