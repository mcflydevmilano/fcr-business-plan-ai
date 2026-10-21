"""
lg.py - Studio legale: fascicolo del cliente da passare allo studio, registro riserve e varianti con scadenze, penali di ritardo
calcolate dal cronoprogramma, contratti in scadenza. Deterministico e senza Streamlit.

ATTENZIONE: e' un promemoria organizzativo. Le scadenze di legge (termini per le riserve, decadenze, prescrizioni) le stabilisce
lo studio legale: qui si scrivono le date che lo studio comunica. Non e' una consulenza legale.
"""
import os
import smtplib
import json
import urllib.request
from email.message import EmailMessage

import sc
from core import fmt_num, to_float
from sc import data_da
from scad import conta, oggi_da, peggiore, stato_scadenza

LG_DEFAULT = {"oggi": None, "preavviso_gg": 15, "tetto_pct": 10.0}
TIPI_RISERVA = ["Riserva", "Variante", "Contestazione", "Richiesta di proroga"]
STATI_RISERVA = ["Da inviare", "Inviata", "Accolta", "Respinta", "Chiusa"]
APERTI = ("Da inviare", "Inviata")
COLONNE_RISERVE = ["Cantiere", "Tipo", "Descrizione", "Importo", "Data", "Termine", "Stato"]
ETICHETTE_RISERVE = {"Cantiere": "Cantiere", "Tipo": "Tipo", "Descrizione": "Di cosa si tratta", "Importo": "Importo richiesto (€)", "Data": "Data", "Termine": "Termine fissato dallo studio", "Stato": "Stato"}
COLONNE_CONTRATTI = ["Contratto", "Controparte", "Cantiere", "Importo", "Scadenza", "Note"]
ETICHETTE_CONTRATTI = {"Contratto": "Contratto", "Controparte": "Controparte", "Cantiere": "Cantiere", "Importo": "Importo (€)", "Scadenza": "Scadenza / fine validità", "Note": "Note"}
COLONNE_TERMINI = ["Cantiere", "Importo", "Termine", "Penale_per_mille"]
ETICHETTE_TERMINI = {"Cantiere": "Cantiere (come nel Cronoprogramma)", "Importo": "Importo del contratto (€)", "Termine": "Termine contrattuale di fine lavori", "Penale_per_mille": "Penale (‰ al giorno)"}
LIVELLI = ["1 - Promemoria cortese", "2 - Sollecito formale", "3 - Diffida di pagamento"]
MODI = ["Email", "PEC", "Telefono", "Lettera", "Raccomandata"]
COLONNE_SOLLECITI = ["Cliente", "Data", "Livello", "Modalita", "Esito"]
ETICHETTE_SOLLECITI = {"Cliente": "Cliente", "Data": "Data", "Livello": "Livello", "Modalita": "Come", "Esito": "Esito / risposta"}


def _t(v):
    return "" if v is None or v != v else str(v).strip()


def _lista(righe, colonne, nome, chiavi, normal):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        if not any(_t(r.get(c)) for c in colonne):
            continue
        rec, err = normal(r)
        if err:
            avvisi.append(f"{nome}, riga {i}: {err}, riga ignorata.")
        else:
            out.append(rec)
    return out, avvisi


def _data(v):
    d = data_da(v)
    return d.isoformat() if d else ""


def normalizza_riserve(righe):
    def n(r):
        c, d = _t(r.get("Cantiere")), _t(r.get("Descrizione"))
        if not c or not d:
            return None, "servono cantiere e descrizione"
        t, s = _t(r.get("Tipo")), _t(r.get("Stato"))
        return {"Cantiere": c, "Tipo": t if t in TIPI_RISERVA else "Riserva", "Descrizione": d, "Importo": max(0.0, to_float(r.get("Importo"), 0.0)),
                "Data": _data(r.get("Data")), "Termine": _data(r.get("Termine")), "Stato": s if s in STATI_RISERVA else "Da inviare"}, None
    return _lista(righe, COLONNE_RISERVE, "Riserve", None, n)


def normalizza_contratti(righe):
    def n(r):
        c = _t(r.get("Contratto"))
        if not c:
            return None, "manca il nome del contratto"
        return {"Contratto": c, "Controparte": _t(r.get("Controparte")), "Cantiere": _t(r.get("Cantiere")), "Importo": max(0.0, to_float(r.get("Importo"), 0.0)),
                "Scadenza": _data(r.get("Scadenza")), "Note": _t(r.get("Note"))}, None
    return _lista(righe, COLONNE_CONTRATTI, "Contratti", None, n)


def normalizza_termini(righe):
    def n(r):
        c, imp, t = _t(r.get("Cantiere")), to_float(r.get("Importo"), 0.0), data_da(r.get("Termine"))
        if not c or imp <= 0 or t is None:
            return None, "servono cantiere, importo e termine"
        return {"Cantiere": c, "Importo": imp, "Termine": t.isoformat(), "Penale_per_mille": min(5.0, max(0.0, to_float(r.get("Penale_per_mille"), 1.0)))}, None
    return _lista(righe, COLONNE_TERMINI, "Termini", None, n)


def normalizza_solleciti(righe):
    def n(r):
        c, d = _t(r.get("Cliente")), data_da(r.get("Data"))
        if not c or d is None:
            return None, "servono cliente e data"
        lv = _t(r.get("Livello"))
        return {"Cliente": c, "Data": d.isoformat(), "Livello": lv if lv in LIVELLI else LIVELLI[0], "Modalita": _t(r.get("Modalita")) or "Email", "Esito": _t(r.get("Esito"))}, None
    return _lista(righe, COLONNE_SOLLECITI, "Solleciti", None, n)


def penali(termini, commesse_gt, tetto_pct=10.0):
    """Per ogni cantiere con termine contrattuale: ritardo stimato (dal Cronoprogramma) e penale = importo x ‰ x giorni, con tetto in % dell'importo."""
    fine = {c["Commessa"].lower(): c for c in (commesse_gt or [])}
    out = []
    for t in termini:
        c = fine.get(t["Cantiere"].lower())
        if c is None:
            out.append({**t, "Fine stimata": "", "Ritardo gg": None, "Penale": 0.0, "Tetto": t["Importo"] * tetto_pct / 100, "Stato": "nd", "Nota": "Cantiere non trovato nel Cronoprogramma"})
            continue
        term, stim = data_da(t["Termine"]), data_da(c["Fine stimata"])
        gg = max(0, (stim - term).days)
        tetto = t["Importo"] * tetto_pct / 100
        pen = min(t["Importo"] * t["Penale_per_mille"] / 1000 * gg, tetto)
        out.append({**t, "Fine stimata": stim.isoformat(), "Ritardo gg": gg, "Penale": pen, "Tetto": tetto, "Stato": "bad" if gg and pen >= tetto else ("warn" if gg else "ok"),
                    "Nota": "tetto raggiunto" if gg and pen >= tetto else ""})
    return out


def fascicoli(fatture, solleciti, oggi):
    """Per cliente con fatture attive scadute: importi, ritardo, solleciti gia' fatti e suggerimento. Ordinato per importo."""
    out = []
    for c in sc.solleciti(fatture, oggi):
        fatti = sorted([s for s in solleciti if s["Cliente"].lower() == c["Cliente"].lower()], key=lambda s: s["Data"])
        ultimo = fatti[-1] if fatti else None
        if c["Livello"].startswith("3") and len(fatti) >= 2:
            sug = "Passa allo studio: diffida già scaduta e solleciti già fatti."
        elif c["Livello"].startswith("3"):
            sug = "Ritardo oltre 45 giorni: fai una diffida (o passa allo studio)."
        elif not fatti:
            sug = "Nessun sollecito ancora: parti con il promemoria."
        else:
            sug = "Solleciti in corso: attendi la risposta."
        out.append({**c, "Solleciti fatti": len(fatti), "Ultimo": ultimo, "Storico": fatti, "Suggerimento": sug})
    return out


def calcola_lg(riserve, contratti, termini, solleciti, commesse_gt=None, fatture=None, p=None):
    q = {**LG_DEFAULT, **(p or {})}
    oggi, prev = oggi_da(q), int(max(0, to_float(q["preavviso_gg"], 15)))
    rs = []
    for r in riserve:
        st, g = stato_scadenza(r["Termine"], oggi, prev) if r["Stato"] in APERTI else ("ok", None)
        rs.append({**r, "Stato scadenza": st, "Giorni": g})
    ct = []
    for c in contratti:
        st, g = stato_scadenza(c["Scadenza"], oggi, prev)
        ct.append({**c, "Stato scadenza": st, "Giorni": g})
    pen = penali(termini, commesse_gt, to_float(q["tetto_pct"], 10.0))
    fas = fascicoli(fatture or [], solleciti, oggi)
    aperte = [r for r in rs if r["Stato"] in APERTI]
    avvisi = []
    for r in rs:
        if r["Stato scadenza"] == "bad":
            avvisi.append(f"{r['Tipo']} «{r['Descrizione'][:50]}» ({r['Cantiere']}): termine superato e ancora {r['Stato'].lower()}. Sentire subito lo studio.")
        elif r["Stato scadenza"] == "warn":
            avvisi.append(f"{r['Tipo']} «{r['Descrizione'][:50]}» ({r['Cantiere']}): termine tra {r['Giorni']} giorni.")
    for c in ct:
        if c["Stato scadenza"] in ("bad", "warn"):
            avvisi.append(f"Contratto «{c['Contratto']}»: " + ("scaduto" if c["Stato scadenza"] == "bad" else f"scade tra {c['Giorni']} giorni") + ".")
    for x in pen:
        if x["Ritardo gg"]:
            avvisi.append(f"{x['Cantiere']}: ritardo stimato di {x['Ritardo gg']} giorni, penale stimata {fmt_num(x['Penale'])} € ({x['Nota'] or 'sotto il tetto'}).")
    stati = [r["Stato scadenza"] for r in aperte] + [c["Stato scadenza"] for c in ct]
    kpi = {"riserve_aperte": len(aperte), "importo_riserve": sum(r["Importo"] for r in aperte), "termini_scaduti": sum(1 for r in aperte if r["Stato scadenza"] == "bad"),
           "termini_vicini": sum(1 for r in aperte if r["Stato scadenza"] == "warn"), "contratti": len(ct), "contratti_scaduti": sum(1 for c in ct if c["Stato scadenza"] == "bad"),
           "contratti_in_scadenza": sum(1 for c in ct if c["Stato scadenza"] == "warn"), "penali_stimate": sum(x["Penale"] for x in pen), "cantieri_in_ritardo": sum(1 for x in pen if x["Ritardo gg"]),
           "clienti_scaduti": len(fas), "scaduto_clienti": sum(f["Totale scaduto"] for f in fas), "da_passare": sum(1 for f in fas if f["Suggerimento"].startswith("Passa")),
           "n_bad": conta(stati)["bad"], "n_warn": conta(stati)["warn"], "peggiore": peggiore(stati)}
    return {"params": {**q, "oggi": oggi}, "riserve": rs, "contratti": ct, "penali": pen, "fascicoli": fas, "kpi": kpi, "avvisi": avvisi}


def testo_passaggio(f, nota="", mittente="FCR General Contractor", riserve=None):
    """Oggetto e corpo della mail con cui si passa un cliente allo studio. Elenca fatture, solleciti gia' fatti e riserve aperte dello stesso cliente."""
    righe = [f"- fattura {x['Documento'] or 'n.d.'} del {sc._fmt_data(x['Data_doc'])}, scaduta il {sc._fmt_data(x['Scadenza'])}: {fmt_num(x['Residuo'], 2)} EUR ({x['Ritardo']} giorni di ritardo)"
             for x in f["Fatture"]]
    sol = [f"- {sc._fmt_data(s['Data'])}: {s['Livello'][4:].lower()} via {s['Modalita'].lower()}" + (f" - {s['Esito']}" if s["Esito"] else "") for s in f["Storico"]] or ["- nessun sollecito registrato"]
    corpo = [f"Egregi Avvocati,", "", f"Vi trasmettiamo il fascicolo del cliente {f['Cliente']} per le valutazioni del caso.", "",
             f"CREDITO SCADUTO: {fmt_num(f['Totale scaduto'], 2)} EUR (ritardo massimo {f['Ritardo max (gg)']} giorni)", *righe, "", "SOLLECITI GIÀ EFFETTUATI", *sol]
    if riserve:
        corpo += ["", "RISERVE E VARIANTI APERTE CON LO STESSO CLIENTE"] + [f"- {r['Tipo']} ({r['Cantiere']}): {r['Descrizione']} - {fmt_num(r['Importo'], 2)} EUR" for r in riserve]
    if nota:
        corpo += ["", "NOTE", nota]
    corpo += ["", "Restiamo a disposizione per ogni documento utile. Vi chiediamo di indicarci le azioni consigliate e i relativi termini.", "", "Cordiali saluti", mittente]
    return f"Fascicolo cliente {f['Cliente']} - credito scaduto {fmt_num(f['Totale scaduto'])} EUR", "\n".join(corpo)


def destinatari(env=None):
    env = env or os.environ
    return [x.strip() for x in (env.get("STUDIO_LEGALE_EMAIL", "")).split(",") if x.strip()]


def canali_attivi(env=None):
    env = env or os.environ
    mail = bool(destinatari(env) and env.get("SMTP_HOST") and env.get("SMTP_USER") and env.get("SMTP_PASSWORD"))
    slack = (env.get("STUDIO_LEGALE_SLACK_WEBHOOK_URL") or "").startswith("https://hooks.slack.com/")
    return {"email": mail, "slack": slack}


def invia_studio(oggetto, corpo, allegati=(), env=None):
    """Spedisce il fascicolo allo studio: email (con allegati) e/o Slack. Solleva RuntimeError se nessun canale e' configurato. Restituisce i canali usati."""
    env = env or os.environ
    can = canali_attivi(env)
    if not (can["email"] or can["slack"]):
        raise RuntimeError("Nessun canale configurato: servono STUDIO_LEGALE_EMAIL (con SMTP_HOST, SMTP_USER, SMTP_PASSWORD) oppure STUDIO_LEGALE_SLACK_WEBHOOK_URL nei Secrets.")
    usati = []
    if can["email"]:
        msg = EmailMessage()
        msg["Subject"], msg["From"], msg["To"] = oggetto, env.get("MAIL_FROM") or env["SMTP_USER"], ", ".join(destinatari(env))
        msg.set_content(corpo)
        for nome, dati, mime in allegati:
            tipo, sotto = mime.split("/", 1)
            msg.add_attachment(dati, maintype=tipo, subtype=sotto, filename=nome)
        with smtplib.SMTP(env["SMTP_HOST"], int(env.get("SMTP_PORT", "587") or 587), timeout=30) as s:
            s.starttls()
            s.login(env["SMTP_USER"], env["SMTP_PASSWORD"])
            s.send_message(msg)
        usati.append("email")
    if can["slack"]:
        testo = f"*{oggetto}*\n" + corpo[:2800]
        req = urllib.request.Request(env["STUDIO_LEGALE_SLACK_WEBHOOK_URL"].strip(), data=json.dumps({"text": testo}).encode("utf-8"), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            if r.status != 200:
                raise RuntimeError(f"Slack ha risposto {r.status}")
        usati.append("Slack")
    return usati
