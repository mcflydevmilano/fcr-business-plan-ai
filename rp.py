"""
rp.py - Rapportini di cantiere e segnalazioni: il giornale quotidiano compilato dai capicantiere (presenze, ore, lavorazioni, meteo)
e le segnalazioni (sicurezza, qualita', materiali, ritardi) con gravita', responsabile e scadenza.

Deterministico e senza Streamlit. Cosa calcola:
  - per cantiere: ultimo rapportino, giorni lavorativi senza rapportino, ore e presenze recenti;
  - segnalazioni aperte per gravita', scadute o in scadenza;
  - `unisci`: fusione di due versioni dello stesso registro (per chi compila da piu' telefoni contemporaneamente).
"""
import datetime as dt
import hashlib

from core import to_float
from sc import data_da
from scad import oggi_da, stato_scadenza

RP_DEFAULT = {"oggi": None, "giorni_senza_rapporto": 2, "preavviso_gg": 3, "finestra_gg": 30}
LIMITI_RP = {"giorni_senza_rapporto": (1, 30), "preavviso_gg": (0, 60), "finestra_gg": (7, 120)}
METEO = ("Sereno", "Nuvoloso", "Pioggia", "Vento forte", "Neve / gelo", "Caldo estremo")
TIPI_SEGN = ("Sicurezza", "Qualità", "Materiale / consegna", "Ritardo", "Mezzi", "Altro")
GRAVITA = ("Bassa", "Media", "Alta")
STATI_SEGN = ("Aperta", "In corso", "Chiusa")

COLONNE_RAPP = ["Id", "Data", "Cantiere", "Compilato_da", "Meteo", "Presenti", "Ore", "Lavorazioni", "Mezzi", "Note"]
ETICHETTE_RAPP = {"Id": "Id", "Data": "Data", "Cantiere": "Cantiere", "Compilato_da": "Compilato da", "Meteo": "Meteo", "Presenti": "Persone presenti",
                  "Ore": "Ore lavorate (totali)", "Lavorazioni": "Lavorazioni eseguite", "Mezzi": "Mezzi usati", "Note": "Note"}
COLONNE_SEGN = ["Id", "Data", "Cantiere", "Tipo", "Gravita", "Descrizione", "Responsabile", "Scadenza", "Stato"]
ETICHETTE_SEGN = {"Id": "Id", "Data": "Data", "Cantiere": "Cantiere", "Tipo": "Tipo", "Gravita": "Gravità", "Descrizione": "Descrizione",
                  "Responsabile": "Responsabile", "Scadenza": "Scadenza", "Stato": "Stato"}


def _s(v):
    """Testo pulito: None e NaN diventano stringa vuota."""
    return "" if v is None or (isinstance(v, float) and v != v) else str(v).strip()


def nuovo_id(*parti):
    """Identificativo breve e stabile: serve a riconoscere la stessa riga su telefoni diversi."""
    return hashlib.sha1("|".join(str(p) for p in parti).encode("utf-8")).hexdigest()[:10]


def giorni_lavorativi(da, a):
    """Giorni da lun a ven compresi tra `da` (escluso) e `a` (incluso)."""
    if da is None or a is None or a <= da:
        return 0
    return sum(1 for i in range(1, (a - da).days + 1) if (da + dt.timedelta(days=i)).weekday() < 5)


def normalizza_rapp(righe):
    out, avvisi, visti = [], [], set()
    for i, r in enumerate(righe or [], start=1):
        if not any(_s(r.get(c)) for c in COLONNE_RAPP if c != "Id"):
            continue
        d, cant = data_da(r.get("Data")), _s(r.get("Cantiere"))
        if d is None or not cant:
            avvisi.append(f"Rapportino {i}: servono data e cantiere, riga ignorata.")
            continue
        riga = {"Data": d.isoformat(), "Cantiere": cant, "Compilato_da": _s(r.get("Compilato_da")), "Meteo": _s(r.get("Meteo")),
                "Presenti": max(0.0, to_float(r.get("Presenti"), 0.0)), "Ore": max(0.0, to_float(r.get("Ore"), 0.0)),
                "Lavorazioni": _s(r.get("Lavorazioni")), "Mezzi": _s(r.get("Mezzi")), "Note": _s(r.get("Note"))}
        riga["Id"] = _s(r.get("Id")) or nuovo_id("R", d, cant, riga["Compilato_da"], riga["Lavorazioni"], riga["Ore"])
        if riga["Id"] in visti:
            continue
        visti.add(riga["Id"])
        out.append(riga)
    return out, avvisi


def normalizza_segn(righe):
    out, avvisi, visti = [], [], set()
    for i, r in enumerate(righe or [], start=1):
        if not any(_s(r.get(c)) for c in COLONNE_SEGN if c != "Id"):
            continue
        d, cant, desc = data_da(r.get("Data")), _s(r.get("Cantiere")), _s(r.get("Descrizione"))
        if d is None or not cant or not desc:
            avvisi.append(f"Segnalazione {i}: servono data, cantiere e descrizione, riga ignorata.")
            continue
        g, stato = (_s(r.get("Gravita")) or "Media"), (_s(r.get("Stato")) or "Aperta")
        sc_ = data_da(r.get("Scadenza"))
        riga = {"Data": d.isoformat(), "Cantiere": cant, "Tipo": (_s(r.get("Tipo")) or "Altro"), "Gravita": g if g in GRAVITA else "Media", "Descrizione": desc,
                "Responsabile": _s(r.get("Responsabile")), "Scadenza": sc_.isoformat() if sc_ else "", "Stato": stato if stato in STATI_SEGN else "Aperta"}
        riga["Id"] = _s(r.get("Id")) or nuovo_id("S", d, cant, desc)
        if riga["Id"] in visti:
            continue
        visti.add(riga["Id"])
        out.append(riga)
    return out, avvisi


def unisci(db, locale, toccati=(), colonna_id="Id"):
    """Fonde il registro salvato (`db`) con quello del telefono (`locale`), righe = liste di dict.
    - le righe del database restano tutte (anche quelle aggiunte da altri nel frattempo);
    - le righe toccate da questo telefono (id in `toccati`: nuove o modificate) prevalgono sulla versione del database;
    - le righe del telefono ma non nel database e non toccate sono state eliminate da qualcun altro: non tornano."""
    toccati = set(toccati)
    mio = {str(r.get(colonna_id)): r for r in (locale or []) if str(r.get(colonna_id) or "")}
    out, visti = [], set()
    for r in db or []:
        k = str(r.get(colonna_id))
        out.append(mio[k] if k in toccati and k in mio else r)
        visti.add(k)
    for k, r in mio.items():
        if k not in visti and k in toccati:
            out.append(r)
    return out


def calcola_rp(rapp, segn, p=None):
    p = {**RP_DEFAULT, **(p or {})}
    oggi = oggi_da(p)
    soglia, prev, fin = int(p["giorni_senza_rapporto"]), int(p["preavviso_gg"]), int(p["finestra_gg"])
    da = oggi - dt.timedelta(days=fin)
    cant = {}
    for r in rapp:
        d = data_da(r["Data"])
        c = cant.setdefault(r["Cantiere"], {"Cantiere": r["Cantiere"], "ultimo": None, "rapporti": 0, "ore": 0.0, "presenze": 0.0})
        if c["ultimo"] is None or d > c["ultimo"]:
            c["ultimo"] = d
        if da <= d <= oggi:
            c["rapporti"] += 1
            c["ore"] += r["Ore"]
            c["presenze"] += r["Presenti"]
    aperte_per = {}
    for s in segn:
        if s["Stato"] != "Chiusa":
            aperte_per[s["Cantiere"]] = aperte_per.get(s["Cantiere"], 0) + 1
    cantieri = []
    for c in cant.values():
        if c["ultimo"] < da:                       # fermo da oltre la finestra: cantiere non piu' attivo
            continue
        gl = giorni_lavorativi(c["ultimo"], oggi)
        stato = "bad" if gl > 2 * soglia else ("warn" if gl > soglia else "ok")
        cantieri.append({"Cantiere": c["Cantiere"], "Ultimo rapportino": c["ultimo"].isoformat(), "Giorni lavorativi senza rapportino": gl, "Rapportini": c["rapporti"],
                         "Ore": round(c["ore"], 1), "Presenze medie": round(c["presenze"] / c["rapporti"], 1) if c["rapporti"] else 0.0,
                         "Segnalazioni aperte": aperte_per.get(c["Cantiere"], 0), "Stato": stato})
    cantieri.sort(key=lambda x: (-{"bad": 2, "warn": 1, "ok": 0}[x["Stato"]], -x["Giorni lavorativi senza rapportino"], x["Cantiere"]))
    seg = []
    for s in segn:
        if s["Stato"] == "Chiusa":
            continue
        st_sc, g = stato_scadenza(s["Scadenza"], oggi, prev)
        stato = "bad" if (st_sc == "bad" or s["Gravita"] == "Alta") else ("warn" if st_sc == "warn" or s["Gravita"] == "Media" else "ok")
        seg.append({**s, "Stato scadenza": st_sc, "Giorni": g, "Livello": stato})
    seg.sort(key=lambda x: (-{"bad": 2, "warn": 1, "ok": 0}[x["Livello"]], -GRAVITA.index(x["Gravita"]), x["Scadenza"] or "9999", x["Data"]))
    kpi = {"cantieri_attivi": len(cantieri), "cantieri_senza_rapporto": sum(1 for c in cantieri if c["Stato"] != "ok"),
           "rapportini": sum(c["Rapportini"] for c in cantieri), "ore": round(sum(c["Ore"] for c in cantieri), 1),
           "segn_aperte": len(seg), "segn_alte": sum(1 for s in seg if s["Gravita"] == "Alta"), "segn_scadute": sum(1 for s in seg if s["Stato scadenza"] == "bad"),
           "segn_in_scadenza": sum(1 for s in seg if s["Stato scadenza"] == "warn")}
    avvisi = [f"{c['Cantiere']}: nessun rapportino da {c['Giorni lavorativi senza rapportino']} giorni lavorativi." for c in cantieri if c["Stato"] != "ok"]
    avvisi += [f"Segnalazione {s['Gravita'].lower()} aperta a {s['Cantiere']}: {s['Descrizione'][:60]}" + (" (scaduta)" if s["Stato scadenza"] == "bad" else "") for s in seg if s["Livello"] == "bad"]
    return {"params": {**p, "oggi": oggi}, "cantieri": cantieri, "segnalazioni": seg, "kpi": kpi, "avvisi": avvisi}


def oggi_italia():
    """Data di oggi in Italia (il server puo' essere in UTC: dopo le 22 sarebbe ancora 'ieri')."""
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("Europe/Rome")).date()
    except Exception:
        return dt.date.today()
