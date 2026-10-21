"""
sc.py - Scadenzario incassi e pagamenti: fatture attive (da incassare) e passive (da pagare), scaduto, solleciti e
previsione di cassa settimana per settimana.

Deterministico e senza Streamlit. Gli importi sono quelli REALI del documento (IVA inclusa): e' cio' che entra ed esce dal conto.

Regole della previsione (sempre dichiarate nel report):
  - Fattura attiva non scaduta: si incassa alla scadenza + `ritardo_attivo_gg` (ritardo abituale dei clienti).
  - Fattura attiva gia' scaduta: `incasso_scaduti_pct`% si incassa nella settimana 1; il resto e' considerato incerto e NON entra
    nella previsione (prudenza).
  - Fattura passiva non scaduta: si paga alla scadenza. Passiva scaduta: `pagamento_scaduti_pct`% si paga nella settimana 1.
  - Le settimane sono finestre di 7 giorni che partono da `oggi` (settimana 1 = oggi ... oggi + 6).
"""
import datetime as dt
import re

from core import fmt_num, to_float

SC_DEFAULT = {
    "oggi": None,                 # data di riferimento (None = oggi)
    "cassa0": 0.0,                # saldo di conto alla data di riferimento
    "fido": 0.0,                  # affidamento disponibile
    "settimane": 13,
    "ritardo_attivo_gg": 0,       # ritardo abituale dei clienti rispetto alla scadenza
    "incasso_scaduti_pct": 50.0,  # quota dello scaduto attivo che si pensa di incassare nella settimana 1
    "pagamento_scaduti_pct": 100.0,
}
LIMITI_SC = {"settimane": (4, 52), "ritardo_attivo_gg": (0, 365), "incasso_scaduti_pct": (0.0, 100.0), "pagamento_scaduti_pct": (0.0, 100.0)}

COLONNE_DOC = ["Tipo", "Controparte", "Cantiere", "Documento", "Data_doc", "Scadenza", "Importo", "Saldato"]
ETICHETTE_DOC = {"Tipo": "Tipo", "Controparte": "Cliente / Fornitore", "Cantiere": "Cantiere", "Documento": "N. documento",
                 "Data_doc": "Data documento", "Scadenza": "Scadenza", "Importo": "Importo (€, IVA inclusa)", "Saldato": "Già incassato / pagato (€)"}
TIPI = ("Attiva", "Passiva")
FASCE = [("Non scaduto", None, 0), ("1-30 gg", 1, 30), ("31-60 gg", 31, 60), ("61-90 gg", 61, 90), ("Oltre 90 gg", 91, None)]


def data_da(v, default=None):
    """Converte date in vari formati (date, datetime, Timestamp, 'AAAA-MM-GG', 'GG/MM/AAAA'); `default` se non valida."""
    if v is None or (isinstance(v, float) and v != v):
        return default
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if hasattr(v, "to_pydatetime"):
        try:
            return v.to_pydatetime().date()
        except Exception:
            return default
    s = str(v).strip()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        a, me, g = map(int, m.groups())
    else:
        m = re.match(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})$", s)
        if not m:
            return default
        g, me, a = map(int, m.groups())
        a += 2000 if a < 100 else 0
    try:
        return dt.date(a, me, g)
    except ValueError:
        return default


SINONIMI_DOC = {"Tipo": ("Natura", "Tipo documento", "Attiva/Passiva", "Registro"),
                "Controparte": ("Cliente", "Fornitore", "Cliente/Fornitore", "Ragione sociale", "Intestatario", "Anagrafica", "Descrizione cliente"),
                "Cantiere": ("Commessa", "Cantiere/Commessa", "Centro di costo"),
                "Documento": ("N. documento", "Numero", "Numero fattura", "N. fattura", "Nr. doc", "Num. doc", "Protocollo"),
                "Data_doc": ("Data documento", "Data fattura", "Data emissione", "Data reg", "Data registrazione"),
                "Scadenza": ("Data scadenza", "Scad.", "Scadenza pagamento", "Data pagamento previsto"),
                "Importo": ("Totale documento", "Totale fattura", "Importo scadenza", "Totale", "Valore", "Importo scaduto", "Da incassare", "Da pagare"),
                "Saldato": ("Pagato", "Incassato", "Importo pagato", "Già saldato", "Acconto")}


def _tipo(v):
    s = str(v or "").strip().lower()
    if s.startswith(("att", "inc", "cli", "ent", "vend")):
        return "Attiva"
    if s.startswith(("pas", "pag", "for", "usc", "acq")):
        return "Passiva"
    return None


def normalizza_documenti(righe):
    """Pulisce le righe (da editor o file). Restituisce (documenti validi, avvisi). Righe senza importo, tipo o scadenza sono scartate."""
    docs, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        importo = to_float(r.get("Importo"), 0.0)
        vuota = not any(str(r.get(c) or "").strip() for c in COLONNE_DOC)
        if vuota:
            continue
        tipo = _tipo(r.get("Tipo"))
        scad = data_da(r.get("Scadenza"))
        if importo <= 0 or tipo is None or scad is None:
            motivo = "importo non valido" if importo <= 0 else ("tipo non riconosciuto (Attiva/Passiva)" if tipo is None else "scadenza non valida")
            avvisi.append(f"Riga {i}: {motivo}, riga ignorata.")
            continue
        saldato = min(importo, max(0.0, to_float(r.get("Saldato"), 0.0)))
        d0 = data_da(r.get("Data_doc"))
        if d0 and d0 > scad:
            avvisi.append(f"Riga {i}: la scadenza e' precedente alla data del documento.")
        docs.append({"Tipo": tipo, "Controparte": str(r.get("Controparte") or "").strip() or "(non indicato)",
                     "Cantiere": str(r.get("Cantiere") or "").strip(), "Documento": str(r.get("Documento") or "").strip(),
                     "Data_doc": d0.isoformat() if d0 else "", "Scadenza": scad.isoformat(), "Importo": importo, "Saldato": saldato})
    return docs, avvisi


def _pulisci(p):
    q = {**SC_DEFAULT, **(p or {})}
    q["oggi"] = data_da(q.get("oggi"), dt.date.today())
    for k in ("cassa0", "fido"):
        q[k] = max(0.0, to_float(q[k], 0.0)) if k == "fido" else to_float(q[k], 0.0)
    for k, (lo, hi) in LIMITI_SC.items():
        q[k] = min(max(to_float(q[k], SC_DEFAULT[k]), lo), hi)
    q["settimane"] = int(q["settimane"])
    q["ritardo_attivo_gg"] = int(q["ritardo_attivo_gg"])
    return q


def _giorni_ritardo(d, oggi):
    return max(0, (oggi - data_da(d["Scadenza"])).days)


def fasce_scaduto(docs, oggi=None):
    """Residuo per fascia di ritardo, separato tra attive e passive."""
    oggi = data_da(oggi, dt.date.today())
    out = []
    for nome, lo, hi in FASCE:
        riga = {"Fascia": nome, "Attive": 0.0, "Passive": 0.0}
        for d in docs:
            res = d["Importo"] - d["Saldato"]
            if res <= 0:
                continue
            g = _giorni_ritardo(d, oggi)
            if (lo is None and g == 0) or (lo is not None and g >= lo and (hi is None or g <= hi)):
                riga["Attive" if d["Tipo"] == "Attiva" else "Passive"] += res
        out.append(riga)
    return out


def calcola_sc(docs, p=None):
    q = _pulisci(p)
    oggi, n = q["oggi"], q["settimane"]
    sett = [{"Settimana": i + 1, "Dal": oggi + dt.timedelta(days=7 * i), "Al": oggi + dt.timedelta(days=7 * i + 6),
             "Incassi": 0.0, "Pagamenti": 0.0} for i in range(n)]
    fine = oggi + dt.timedelta(days=7 * n - 1)
    da_inc = da_pag = scad_att = scad_pass = 0.0
    incerti = oltre = 0.0
    ritardo_pond = 0.0
    for d in docs:
        res = d["Importo"] - d["Saldato"]
        if res <= 0:
            continue
        s = data_da(d["Scadenza"])
        att = d["Tipo"] == "Attiva"
        if att:
            da_inc += res
        else:
            da_pag += res
        scaduta = s < oggi
        if scaduta:
            if att:
                scad_att += res
                ritardo_pond += res * (oggi - s).days
            else:
                scad_pass += res
        quota = (q["incasso_scaduti_pct"] if att else q["pagamento_scaduti_pct"]) / 100.0 if scaduta else 1.0
        previsto = (s + dt.timedelta(days=q["ritardo_attivo_gg"])) if (att and not scaduta) else s
        if scaduta:
            previsto = oggi
        if scaduta and att:
            incerti += res * (1 - quota)
        importo_prev = res * quota
        if previsto > fine:
            oltre += importo_prev if att else 0.0
            continue
        k = min(n - 1, max(0, (previsto - oggi).days // 7))
        sett[k]["Incassi" if att else "Pagamenti"] += importo_prev
    cassa = q["cassa0"]
    picco, sett_picco, fuori = 0.0, 0, 0
    for r in sett:
        r["Flusso netto"] = r["Incassi"] - r["Pagamenti"]
        cassa += r["Flusso netto"]
        r["Cassa finale"] = cassa
        r["Scoperto"] = max(0.0, -cassa)
        r["Fido residuo"] = q["fido"] - r["Scoperto"]
        if r["Scoperto"] > picco + 1e-9:
            picco, sett_picco = r["Scoperto"], r["Settimana"]
        if not fuori and r["Scoperto"] > q["fido"] + 1e-6:
            fuori = r["Settimana"]
    kpi = {
        "n_documenti": len(docs), "da_incassare": da_inc, "da_pagare": da_pag, "saldo_netto": da_inc - da_pag,
        "scaduto_attivo": scad_att, "scaduto_passivo": scad_pass,
        "scaduto_attivo_pct": (scad_att / da_inc * 100.0) if da_inc else 0.0,
        "ritardo_medio_gg": (ritardo_pond / scad_att) if scad_att else 0.0,
        "cassa0": q["cassa0"], "cassa_settimana1": sett[0]["Cassa finale"], "cassa_finale": sett[-1]["Cassa finale"],
        "cassa_minima": min([q["cassa0"]] + [r["Cassa finale"] for r in sett]),
        "picco_fabbisogno": picco, "settimana_picco": sett_picco, "prima_settimana_fuori_fido": fuori, "fido": q["fido"],
        "incerti": incerti, "incassi_oltre_orizzonte": oltre, "settimane": n,
        "incassi_tot": sum(r["Incassi"] for r in sett), "pagamenti_tot": sum(r["Pagamenti"] for r in sett),
        "ok_settimana": sett[0]["Cassa finale"] >= 0,
    }
    out = {"params": q, "settimane": sett, "kpi": kpi, "fasce": fasce_scaduto(docs, oggi)}
    out["avvisi"] = valida_sc(q, out)
    return out


def valida_sc(q, out):
    k, w = out["kpi"], []
    if k["n_documenti"] == 0:
        return ["Nessun documento nello scadenzario: aggiungi almeno una fattura con importo e scadenza."]
    if k["prima_settimana_fuori_fido"]:
        w.append(f"Dalla settimana {k['prima_settimana_fuori_fido']} lo scoperto supera il fido ({fmt_num(k['fido'])} EUR): picco di "
                 f"{fmt_num(k['picco_fabbisogno'])} EUR alla settimana {k['settimana_picco']}. Servono incassi anticipati, pagamenti dilazionati o piu' liquidita'.")
    elif k["picco_fabbisogno"] > 0:
        w.append(f"La cassa va in scoperto (picco {fmt_num(k['picco_fabbisogno'])} EUR alla settimana {k['settimana_picco']}), dentro il fido di {fmt_num(k['fido'])} EUR.")
    if k["scaduto_attivo_pct"] > 25:
        w.append(f"Il {fmt_num(k['scaduto_attivo_pct'], 0)}% dei crediti e' scaduto ({fmt_num(k['scaduto_attivo'])} EUR, ritardo medio {fmt_num(k['ritardo_medio_gg'], 0)} giorni): "
                 "conviene sollecitare i clienti.")
    if k["scaduto_passivo"] > 0:
        w.append(f"Hai {fmt_num(k['scaduto_passivo'])} EUR di debiti verso fornitori gia' scaduti: rischio di blocco forniture e interessi di mora.")
    if k["incerti"] > 1:
        w.append(f"{fmt_num(k['incerti'])} EUR di crediti scaduti sono considerati incerti e non entrano nella previsione.")
    return w


def confronto_ritardi(docs, p=None, ritardi=(0, 15, 30, 60)):
    """Cosa succede se i clienti pagano con piu' giorni di ritardo. Restituisce righe per la tabella."""
    righe = []
    for g in ritardi:
        q = {**(p or {}), "ritardo_attivo_gg": g}
        o = calcola_sc(docs, q)
        k = o["kpi"]
        righe.append({"Ritardo clienti (gg)": g, "Cassa minima": k["cassa_minima"], "Picco fabbisogno": k["picco_fabbisogno"],
                      "Settimana del picco": k["settimana_picco"], "Fuori fido dalla settimana": k["prima_settimana_fuori_fido"]})
    return righe


# ----------------------------------------------------------------------------
# SOLLECITI
# ----------------------------------------------------------------------------
def livello_sollecito(giorni):
    if giorni <= 15:
        return "1 - Promemoria cortese"
    if giorni <= 45:
        return "2 - Sollecito formale"
    return "3 - Diffida di pagamento"


def solleciti(docs, oggi=None):
    """Per cliente: fatture attive scadute, totale, ritardo massimo e livello di sollecito. Ordinato per importo decrescente."""
    oggi = data_da(oggi, dt.date.today())
    per = {}
    for d in docs:
        res = d["Importo"] - d["Saldato"]
        if d["Tipo"] != "Attiva" or res <= 0 or _giorni_ritardo(d, oggi) <= 0:
            continue
        c = per.setdefault(d["Controparte"], {"Cliente": d["Controparte"], "Fatture": [], "Totale scaduto": 0.0, "Ritardo max (gg)": 0})
        c["Fatture"].append({**d, "Residuo": res, "Ritardo": _giorni_ritardo(d, oggi)})
        c["Totale scaduto"] += res
        c["Ritardo max (gg)"] = max(c["Ritardo max (gg)"], _giorni_ritardo(d, oggi))
    out = sorted(per.values(), key=lambda c: -c["Totale scaduto"])
    for c in out:
        c["Livello"] = livello_sollecito(c["Ritardo max (gg)"])
    return out


def pagamenti_scaduti(docs, oggi=None):
    """Per fornitore: fatture passive scadute non pagate. Ordinato per importo decrescente."""
    oggi = data_da(oggi, dt.date.today())
    per = {}
    for d in docs:
        res = d["Importo"] - d["Saldato"]
        if d["Tipo"] != "Passiva" or res <= 0 or _giorni_ritardo(d, oggi) <= 0:
            continue
        c = per.setdefault(d["Controparte"], {"Fornitore": d["Controparte"], "Fatture": 0, "Totale scaduto": 0.0, "Ritardo max (gg)": 0})
        c["Fatture"] += 1
        c["Totale scaduto"] += res
        c["Ritardo max (gg)"] = max(c["Ritardo max (gg)"], _giorni_ritardo(d, oggi))
    return sorted(per.values(), key=lambda c: -c["Totale scaduto"])


def testo_sollecito(c, mittente="FCR General Contractor"):
    """Bozza di sollecito per un cliente (voce di `solleciti`). Va riletta e personalizzata prima dell'invio."""
    elenco = "\n".join(f"- fattura {f['Documento'] or 'n.d.'} del {_fmt_data(f['Data_doc'])}, scaduta il {_fmt_data(f['Scadenza'])}: "
                       f"{fmt_num(f['Residuo'], 2)} EUR ({f['Ritardo']} giorni di ritardo)" for f in c["Fatture"])
    tot = fmt_num(c["Totale scaduto"], 2)
    liv = c["Livello"][0]
    if liv == "1":
        corpo = (f"Gentile {c['Cliente']},\n\nrisulta ancora aperto quanto segue:\n{elenco}\n\nTotale: {tot} EUR.\n"
                 "Se il pagamento e' gia' stato disposto, La preghiamo di ignorare questo messaggio; in caso contrario Le saremmo grati se "
                 f"potesse provvedere a breve.\n\nCordiali saluti\n{mittente}")
        ogg = "Promemoria di pagamento"
    elif liv == "2":
        corpo = (f"Spett.le {c['Cliente']},\n\nnonostante il nostro precedente contatto, risultano ancora insoluti i seguenti documenti:\n{elenco}\n\n"
                 f"Totale scaduto: {tot} EUR.\nLa invitiamo a regolarizzare entro 7 giorni dal ricevimento della presente, comunicandoci "
                 f"gli estremi del pagamento.\n\nDistinti saluti\n{mittente}")
        ogg = "Sollecito di pagamento"
    else:
        corpo = (f"Spett.le {c['Cliente']},\n\nrisultano insoluti da oltre 45 giorni i seguenti documenti:\n{elenco}\n\nTotale scaduto: {tot} EUR.\n"
                 "La invitiamo a pagare entro 7 giorni dal ricevimento della presente; in difetto saremo costretti a tutelare i nostri diritti nelle "
                 "sedi opportune, con addebito di interessi di mora e spese. [Testo da verificare con il legale prima dell'invio.]\n\n"
                 f"Distinti saluti\n{mittente}")
        ogg = "Diffida di pagamento"
    return ogg, corpo


def _fmt_data(s):
    d = data_da(s)
    return d.strftime("%d/%m/%Y") if d else "n.d."


def da_dataframe(df):
    return [{c: (None if c not in df.columns else df.iloc[i][c]) for c in COLONNE_DOC} for i in range(len(df))]
