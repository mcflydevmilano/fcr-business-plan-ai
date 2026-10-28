"""
mc.py - Margini per commessa: una vista unica che unisce contratto e SAL (SAL e contabilita' lavori) con i costi reali di subappalti, manodopera,
materiali e mezzi, e ricalcola il margine finale. Deterministico, senza Streamlit.

Evita il doppio conteggio: dai costi di SAL toglie le righe nate dagli altri strumenti (marcatori sotto) e le sostituisce con i dati diretti degli strumenti.
"""
import dd
import mt
import mz
import pr
import sa
import sl
from core import to_float
from sc import data_da

FONTI = {"sa": "Subappalti", "pr": "Manodopera (presenze)", "mt": "Materiali consegnati", "mz": "Mezzi"}
FONTI_ORDINE = ("sa", "pr", "mt", "mz")


def _marcata(x):
    """Riga di costo di SAL che e' stata inviata da un altro strumento (si sostituisce con il dato diretto)."""
    return (x.get("Fornitore") in ("Parco mezzi interno", "Manodopera interna") or x.get("Descrizione") == "SAL subappaltatore" or str(x.get("Descrizione") or "").endswith("(da Materiali)"))


def righe_fonti(payloads, oggi=None):
    """{fonte: righe di costo nel formato di SAL}, calcolate dai dati diretti di ogni strumento."""
    r, p = {}, payloads or {}
    base = {"oggi": oggi} if oggi else {}
    if p.get("sa"):
        c, _ = sa.normalizza_contratti(p["sa"].get("contratti"))
        s, _ = sa.normalizza_sal(p["sa"].get("sal"), c)
        d, _ = sa.normalizza_doc(p["sa"].get("doc"), {x["Subappaltatore"] for x in c})
        r["sa"] = sa.per_sl_costi(sa.calcola_sa(c, s, d, {**(p["sa"].get("params") or {}), **base}), s)
    if p.get("pr"):
        pe, _ = pr.normalizza_persone(p["pr"].get("persone"))
        o, _ = pr.normalizza_ore(p["pr"].get("ore"), {x["Persona"] for x in pe})
        r["pr"] = pr.per_sl_costi(pr.calcola_pr(pe, o, {**(p["pr"].get("params") or {}), **base}))
    if p.get("mt"):
        od, _ = mt.normalizza_ordini(p["mt"].get("ordini"))
        mv, _ = mt.normalizza_mov(p["mt"].get("mov"))
        r["mt"] = mt.per_sl_costi(mt.calcola_mt(od, mv, {**(p["mt"].get("params") or {}), **base}))
    if p.get("mz"):
        me, _ = mz.normalizza_mezzi(p["mz"].get("mezzi"))
        nomi = {m["Mezzo"] for m in me}
        u, _ = mz.normalizza_uso(p["mz"].get("uso"), nomi)
        s, _ = mz.normalizza_scad(p["mz"].get("scad"), nomi)
        r["mz"] = mz.per_sl_costi(mz.calcola_mz(me, u, s, {**(p["mz"].get("params") or {}), **base}))
    return r


def calcola_mc(payloads, includi=FONTI_ORDINE, oggi=None):
    """Restituisce {commesse, composizione, kpi, avvisi, non_assegnati} oppure None se non ci sono commesse in SAL."""
    p = payloads or {}
    if not p.get("sl"):
        return None
    com, _ = sl.normalizza_commesse(p["sl"].get("commesse"))
    if not com:
        return None
    nomi = {c["Commessa"] for c in com}
    sal, _ = sl.normalizza_sal(p["sl"].get("sal"), nomi)
    costi_sl, _ = sl.normalizza_costi(p["sl"].get("costi"), nomi)
    par = dict(p["sl"].get("params") or {})
    if oggi:
        par["oggi"] = oggi
    fonti = righe_fonti(p, oggi)
    manuali = [x for x in costi_sl if not _marcata(x)]
    extra = []
    for f in FONTI_ORDINE:
        if f in includi:
            extra += [dict(x, _fonte=f) for x in fonti.get(f, [])]
    norm_extra, _ = sl.normalizza_costi([{k: v for k, v in x.items() if not k.startswith("_")} for x in extra], nomi)
    # normalizza_costi puo' scartare righe: riallinea la fonte in base a (commessa, data, descrizione, importo)
    fonte_di = {(x["Commessa"], x["Data"], x["Descrizione"], round(x["Importo"], 2)): x["_fonte"] for x in extra}
    out = sl.calcola_sl(com, sal, manuali + norm_extra, par)
    out0 = sl.calcola_sl(com, sal, costi_sl, par)                    # come lo vede SAL oggi, per il confronto
    comp = []
    for c in sorted(nomi):
        riga = {"Commessa": c, "Costi inseriti in SAL": sum(x["Importo"] for x in manuali if x["Commessa"] == c)}
        for f in FONTI_ORDINE:
            riga[FONTI[f]] = sum(x["Importo"] for x in norm_extra if x["Commessa"] == c and fonte_di.get((x["Commessa"], x["Data"], x["Descrizione"], round(x["Importo"], 2))) == f)
        riga["Costi totali"] = sum(v for k, v in riga.items() if k != "Commessa")
        comp.append(riga)
    non_ass = {}
    for f in includi:
        for x in fonti.get(f, []):
            if x["Commessa"] not in nomi and x["Commessa"]:
                non_ass[x["Commessa"]] = non_ass.get(x["Commessa"], 0.0) + x["Importo"]
    avvisi = list(out["avvisi"])
    for c, v in sorted(non_ass.items()):
        avvisi.append(f"Costi per {v:,.0f} € su «{c}» non assegnati: la commessa non esiste in SAL e contabilità lavori (controlla come è scritto il nome).".replace(",", "."))
    k0 = out0["kpi"]
    kpi = dict(out["kpi"])
    kpi["margine_finale_sal"] = k0["margine_finale"]
    kpi["differenza_vs_sal"] = out["kpi"]["margine_finale"] - k0["margine_finale"]
    kpi["costi_extra"] = sum(x["Importo"] for x in norm_extra)
    kpi["n_non_assegnati"] = len(non_ass)
    return {"commesse": out["commesse"], "fatture": out["fatture"], "composizione": comp, "kpi": kpi, "avvisi": avvisi, "non_assegnati": non_ass, "params": out["params"]}
