"""
mt.py - Materiali e magazzino di cantiere: ordini e consegne, giacenze (carichi e scarichi) e costo dei materiali per commessa.
Deterministico, senza Streamlit. Importi in EUR al netto di IVA.
"""
from core import to_float
from sc import data_da
from scad import oggi_da

MT_DEFAULT = {"oggi": None, "preavviso_gg": 7}
COLONNE_ORDINI = ["Materiale", "Fornitore", "Commessa", "Quantita", "Um", "Prezzo_unit", "Consegna_prevista", "Consegnato", "Data_consegna", "Ddt"]
ETICHETTE_ORDINI = {"Materiale": "Materiale", "Fornitore": "Fornitore", "Commessa": "Commessa", "Quantita": "Quantità", "Um": "Unità", "Prezzo_unit": "Prezzo unitario (€)",
                    "Consegna_prevista": "Consegna prevista", "Consegnato": "Consegnato (sì/no)", "Data_consegna": "Data consegna", "Ddt": "N. DDT (documento di trasporto)"}
COLONNE_MOV = ["Materiale", "Commessa", "Data", "Tipo", "Quantita", "Magazzino"]
ETICHETTE_MOV = {"Materiale": "Materiale", "Commessa": "Cantiere / commessa", "Data": "Data", "Tipo": "Carico o scarico", "Quantita": "Quantità", "Magazzino": "Magazzino (vuoto = quello del cantiere)"}
COLONNE_ART = ["Codice", "Materiale", "Um", "Magazzino", "Scorta_min", "Prezzo"]
ETICHETTE_ART = {"Codice": "Codice a barre", "Materiale": "Materiale", "Um": "Unità", "Magazzino": "Magazzino abituale", "Scorta_min": "Scorta minima", "Prezzo": "Prezzo di listino (€)"}
DEPOSITO = "Deposito"
TIPI_MOV = ["Carico", "Scarico"]


def _s(v):
    return str(v or "").strip()


def _si(v):
    return _s(v).lower() in ("si", "sì", "s", "true", "1", "yes", "x", "consegnato")


def normalizza_ordini(righe):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(_s(r.get(c)) for c in COLONNE_ORDINI):
            continue
        m, q = _s(r.get("Materiale")), to_float(r.get("Quantita"), 0.0)
        if not m or q <= 0:
            avvisi.append(f"Riga {i} degli ordini: servono materiale e quantità maggiore di zero, riga ignorata.")
            continue
        cons = _si(r.get("Consegnato"))
        dc, dp = data_da(r.get("Data_consegna")), data_da(r.get("Consegna_prevista"))
        out.append({"Materiale": m, "Fornitore": _s(r.get("Fornitore")), "Commessa": _s(r.get("Commessa")) or "(senza commessa)", "Quantita": q, "Um": _s(r.get("Um")) or "pz",
                    "Prezzo_unit": max(0.0, to_float(r.get("Prezzo_unit"), 0.0)), "Consegna_prevista": dp.isoformat() if dp else "", "Consegnato": "sì" if cons else "no",
                    "Data_consegna": dc.isoformat() if dc else "", "Ddt": _s(r.get("Ddt"))})
    return out, avvisi


def righe_da_ordini_approvati(ordini_oa, esistenti=()):
    """Righe per «Ordini e consegne» di Materiali dagli ordini APPROVATI di Ordini e approvazioni (`ordini_oa`: righe di oa.calcola_oa).
    Quelle gia' presenti (stesso materiale, fornitore, commessa, quantita' e prezzo) non si ripetono. Restituisce (nuove, gia_presenti)."""
    def chiave(m, f, c, q, p):
        return (_s(m).lower(), _s(f).lower(), _s(c).lower(), round(float(q or 0), 4), round(float(p or 0), 4))
    visti = {chiave(e.get("Materiale"), e.get("Fornitore"), e.get("Commessa") or "(senza commessa)", to_float(e.get("Quantita"), 0.0), to_float(e.get("Prezzo_unit"), 0.0)) for e in existenti_lista(esistenti)}
    nuove, gia = [], 0
    for o in ordini_oa or []:
        if o.get("Stato") != "Approvato":
            continue
        q = to_float(o.get("Quantita"), 0.0)
        q = q if q > 0 else 1.0
        p = round(to_float(o.get("Importo"), 0.0) / q, 4)
        mat = _s(o.get("Descrizione")) or _s(o.get("Voce")) or _s(o.get("Fornitore"))
        comm = _s(o.get("Cantiere")) or "(senza commessa)"
        k = chiave(mat, o.get("Fornitore"), comm, q, p)
        if k in visti:
            gia += 1
            continue
        visti.add(k)
        nuove.append({"Materiale": mat, "Fornitore": _s(o.get("Fornitore")), "Commessa": comm, "Quantita": q, "Um": "pz",
                      "Prezzo_unit": p, "Consegna_prevista": "", "Consegnato": "no", "Data_consegna": "", "Ddt": ""})
    return nuove, gia


def existenti_lista(e):
    return [dict(r) for r in (e.to_dict("records") if hasattr(e, "to_dict") else (e or []))]


def normalizza_mov(righe):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(_s(r.get(c)) for c in COLONNE_MOV):
            continue
        m, d, t, q = _s(r.get("Materiale")), data_da(r.get("Data")), _s(r.get("Tipo")).capitalize(), to_float(r.get("Quantita"), 0.0)
        if not m or t not in TIPI_MOV or q <= 0:
            avvisi.append(f"Riga {i} dei movimenti: " + ("manca il materiale" if not m else "tipo non valido (Carico o Scarico)" if t not in TIPI_MOV else "quantità non valida") + ", riga ignorata.")
            continue
        out.append({"Materiale": m, "Commessa": _s(r.get("Commessa")) or "(senza commessa)", "Data": d.isoformat() if d else "", "Tipo": t, "Quantita": q, "Magazzino": _s(r.get("Magazzino"))})
    return out, avvisi


def normalizza_articoli(righe):
    """Anagrafica articoli: codice a barre -> materiale. Il codice puo' essere vuoto (articolo senza etichetta)."""
    out, avvisi, codici = [], [], {}
    for i, r in enumerate(righe or [], start=1):
        if not any(_s(r.get(c)) for c in COLONNE_ART):
            continue
        m = _s(r.get("Materiale"))
        if not m:
            avvisi.append(f"Riga {i} degli articoli: manca il materiale, riga ignorata.")
            continue
        cod = _s(r.get("Codice"))
        if cod and cod in codici:
            avvisi.append(f"Codice {cod} ripetuto (già usato per «{codici[cod]}»): la seconda riga è ignorata.")
            continue
        if cod:
            codici[cod] = m
        out.append({"Codice": cod, "Materiale": m, "Um": _s(r.get("Um")) or "pz", "Magazzino": _s(r.get("Magazzino")), "Scorta_min": max(0.0, to_float(r.get("Scorta_min"), 0.0)),
                    "Prezzo": max(0.0, to_float(r.get("Prezzo"), 0.0))})
    return out, avvisi


def _n(t):
    """Chiave di confronto: minuscolo, senza spazi doppi."""
    return " ".join(str(t or "").lower().split())


def cerca_codice(articoli, codice):
    c = _s(codice)
    return next((a for a in articoli or [] if c and a["Codice"] == c), None)


def ultimo_prezzo(ordini, materiale, fornitore="", articoli=None):
    """Prezzo unitario da proporre: ultimo pagato a QUEL fornitore per quel materiale; se manca, ultimo pagato a un altro fornitore;
    se manca, prezzo di listino dell'articolo. Restituisce (prezzo, unita, origine) oppure None."""
    mm, ff = _n(materiale), _n(fornitore)
    if not mm:
        return None
    stesso = [o for o in ordini or [] if _n(o["Materiale"]) == mm and o["Prezzo_unit"] > 0]
    for o in reversed([x for x in stesso if ff and _n(x["Fornitore"]) == ff]):
        return o["Prezzo_unit"], o["Um"], f"ultimo prezzo pagato a {o['Fornitore']}"
    if stesso:
        o = stesso[-1]
        return o["Prezzo_unit"], o["Um"], "ultimo prezzo pagato" + (f" (a {o['Fornitore']})" if o["Fornitore"] else "")
    a = next((x for x in articoli or [] if _n(x["Materiale"]) == mm and x["Prezzo"] > 0), None)
    if a:
        return a["Prezzo"], a["Um"], "prezzo di listino"
    return None


def suggerimenti(ordini, articoli=None, extra_fornitori=(), extra_commesse=()):
    """Elenchi per il completamento automatico, dal piu' usato di recente."""
    def uniq(seq):
        v, out = set(), []
        for x in seq:
            x = _s(x)
            if x and _n(x) not in v and x != "(senza commessa)":
                v.add(_n(x))
                out.append(x)
        return out
    o = list(ordini or [])
    return {"materiali": uniq([x["Materiale"] for x in reversed(o)] + [a["Materiale"] for a in articoli or []]),
            "fornitori": uniq([x["Fornitore"] for x in reversed(o)] + list(extra_fornitori)),
            "commesse": uniq([x["Commessa"] for x in reversed(o)] + list(extra_commesse))}


def calcola_mt(ordini, mov, p=None, articoli=None):
    q = {**MT_DEFAULT, **(p or {})}
    oggi, prev = oggi_da(q), int(max(0, to_float(q["preavviso_gg"], 7)))
    righe, avvisi, senza_ddt = [], [], 0
    for o in ordini:
        importo = o["Quantita"] * o["Prezzo_unit"]
        g = (data_da(o["Consegna_prevista"]) - oggi).days if o["Consegna_prevista"] else None
        if o["Consegnato"] == "sì":
            st = "ok"
        elif g is None:
            st = "nd"
        else:
            st = "bad" if g < 0 else ("warn" if g <= prev else "ok")
        righe.append({**o, "Importo": importo, "Giorni": g, "Stato": st})
        if o["Consegnato"] == "sì" and not o["Ddt"]:
            senza_ddt += 1
            avvisi.append(f"{o['Materiale']} ({o['Commessa']}): consegnato ma senza numero DDT: scrivilo, serve per controllare la fattura.")
        if st == "bad":
            avvisi.append(f"{o['Materiale']} ({o['Commessa']}): consegna in ritardo di {-g} giorni" + (f", fornitore {o['Fornitore']}" if o["Fornitore"] else "") + ".")
    gi, nomi = {}, {}
    for x in mov:
        mag = x.get("Magazzino") or (x["Commessa"] if x["Commessa"] != "(senza commessa)" else DEPOSITO)
        k = (_n(x["Materiale"]), x["Commessa"], mag)
        nomi.setdefault(k[0], x["Materiale"])
        gi[k] = gi.get(k, 0.0) + (x["Quantita"] if x["Tipo"] == "Carico" else -x["Quantita"])
    giacenze = [{"Materiale": nomi[m], "Cantiere": c, "Magazzino": mag, "Giacenza": v} for (m, c, mag), v in sorted(gi.items())]
    # per magazzino (somma dei cantieri) e scorte minime
    pm = {}
    for (m, c, mag), v in gi.items():
        pm[(m, mag)] = pm.get((m, mag), 0.0) + v
    negativi = [(nomi[m], mag, v) for (m, mag), v in sorted(pm.items()) if v < -1e-9]
    for n_, mag, v in negativi:
        avvisi.append(f"{n_} ({mag}): giacenza negativa ({v:g}): uno scarico non ha un carico, controlla.")
    magazzini = [{"Magazzino": mag, "Materiale": nomi[m], "Giacenza": v} for (m, mag), v in sorted(pm.items())]
    sotto = []
    for a in articoli or []:
        if a["Scorta_min"] <= 0:
            continue
        mm = _n(a["Materiale"])
        tot = pm.get((mm, a["Magazzino"]), 0.0) if a["Magazzino"] else sum(v for (m, _), v in pm.items() if m == mm)
        if tot < a["Scorta_min"] - 1e-9:
            sotto.append({"Materiale": a["Materiale"], "Magazzino": a["Magazzino"] or "(tutti)", "Giacenza": tot, "Scorta minima": a["Scorta_min"], "Da ordinare": a["Scorta_min"] - tot, "Um": a["Um"]})
            avvisi.append(f"{a['Materiale']}: sotto scorta minima ({tot:g} su {a['Scorta_min']:g} {a['Um']}" + (f", {a['Magazzino']}" if a["Magazzino"] else "") + ").")
    com = {}
    for r in righe:
        if r["Consegnato"] == "sì":
            com[r["Commessa"]] = com.get(r["Commessa"], 0.0) + r["Importo"]
    per_comm = [{"Commessa": c, "Costo materiali consegnati": v} for c, v in sorted(com.items())]
    ritardi = sum(1 for r in righe if r["Stato"] == "bad")
    kpi = {"n_ordini": len(righe), "ordinato": sum(r["Importo"] for r in righe), "consegnato": sum(r["Importo"] for r in righe if r["Consegnato"] == "sì"),
           "in_ritardo": ritardi, "in_arrivo": sum(1 for r in righe if r["Stato"] == "warn"), "senza_ddt": senza_ddt, "giacenze_negative": len(negativi), "sotto_scorta": len(sotto),
           "n_bad": ritardi + len(negativi), "n_warn": sum(1 for r in righe if r["Stato"] == "warn") + len(sotto)}
    return {"params": {"oggi": oggi, "preavviso_gg": prev}, "ordini": righe, "giacenze": giacenze, "magazzini": magazzini, "sotto_scorta": sotto, "commesse": per_comm, "kpi": kpi, "avvisi": avvisi}


def costi_per_commessa(out):
    return {c["Commessa"]: c["Costo materiali consegnati"] for c in out["commesse"] if c["Commessa"] != "(senza commessa)"}


def per_sl_costi(out):
    return [{"Commessa": r["Commessa"], "Data": r["Data_consegna"] or out["params"]["oggi"].isoformat(), "Fornitore": r["Fornitore"] or "Materiali", "Descrizione": f"{r['Materiale']} - {r['Quantita']:g} {r['Um']}" + (f" - DDT {r['Ddt']}" if r["Ddt"] else "") + " (da Materiali)",
             "Categoria": "Materiali", "Importo": round(r["Importo"], 2), "Pagato": 0.0} for r in out["ordini"] if r["Consegnato"] == "sì" and r["Commessa"] != "(senza commessa)"]
