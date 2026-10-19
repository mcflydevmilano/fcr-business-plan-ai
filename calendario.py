"""
calendario.py - Calendario unico delle scadenze: fatture da incassare/pagare, gare, documenti di gara, documenti dei fornitori,
formazioni e idoneita' del personale, documenti di cantiere, scadenze dei mezzi. Deterministico, senza Streamlit.
"""
import datetime as dt
import hashlib

import fo
import ga
import mz
import sc
import sx
from sc import data_da

MODULI_CALENDARIO = ("sc", "ga", "fo", "sx", "mz")
NOMI_MODULO = {"sc": "Scadenzario", "ga": "Gare e offerte", "fo": "Fornitori", "sx": "Sicurezza", "mz": "Parco mezzi"}
CATEGORIE = ["Incasso", "Pagamento", "Gara", "Documento gara", "Documento fornitore", "Formazione / idoneità", "Documento di cantiere", "Mezzo"]


def _stato(giorni, preavviso):
    return "bad" if giorni < 0 else ("warn" if giorni <= preavviso else "ok")


def _ev(data, oggi, modulo, categoria, titolo, dettaglio="", importo=None, preavviso=30):
    g = (data - oggi).days
    return {"Data": data, "Giorni": g, "Modulo": NOMI_MODULO[modulo], "Categoria": categoria, "Titolo": titolo, "Dettaglio": dettaglio, "Importo": importo, "Stato": _stato(g, preavviso)}


def eventi(payloads, oggi=None, orizzonte_gg=60, categorie=None):
    """payloads: {modulo: payload salvato/di sessione}. Restituisce gli eventi scaduti (tutti) e quelli entro l'orizzonte, ordinati per data."""
    oggi = data_da(oggi, dt.date.today())
    ev = []
    p = payloads or {}
    if p.get("sc"):
        docs, _ = sc.normalizza_documenti(p["sc"].get("docs"))
        for d in docs:
            res = d["Importo"] - d["Saldato"]
            if res > 0:
                att = d["Tipo"] == "Attiva"
                ev.append(_ev(data_da(d["Scadenza"]), oggi, "sc", "Incasso" if att else "Pagamento", f"{d['Controparte']} - {d['Documento'] or 'fattura'}", d["Cantiere"], res, 7))
    if p.get("ga"):
        gare, _ = ga.normalizza_gare(p["ga"].get("gare"))
        doc, _ = ga.normalizza_doc(p["ga"].get("doc"), {g["Gara"] for g in gare})
        prev = int((p["ga"].get("params") or {}).get("preavviso_gg", ga.GA_DEFAULT["preavviso_gg"]))
        aperte = {g["Gara"] for g in gare if g["Stato"] in ("Da valutare", "In preparazione")}
        for g in gare:
            if g["Gara"] in aperte and g["Scadenza"]:
                ev.append(_ev(data_da(g["Scadenza"]), oggi, "ga", "Gara", f"Scadenza offerta: {g['Gara']}", f"{g['Ente']} - base {g['Importo_base']:,.0f} EUR".replace(",", "."), None, prev))
        for d in doc:
            if d["Gara"] in aperte and not d["Fatto"] and d["Scadenza"]:
                ev.append(_ev(data_da(d["Scadenza"]), oggi, "ga", "Documento gara", f"{d['Documento']} ({d['Gara']})", "", None, prev))
    if p.get("fo"):
        docs, _ = fo.normalizza_docfo(p["fo"].get("docs"))
        prev = int((p["fo"].get("params") or {}).get("preavviso_gg", fo.FO_DEFAULT["preavviso_gg"]))
        for d in docs:
            if d["Scadenza"]:
                ev.append(_ev(data_da(d["Scadenza"]), oggi, "fo", "Documento fornitore", f"{d['Documento']} - {d['Fornitore']}", d["Tipo"], None, prev))
    if p.get("sx"):
        pers, _ = sx.normalizza_pers(p["sx"].get("pers"))
        docc, _ = sx.normalizza_docc(p["sx"].get("docc"))
        prev = int((p["sx"].get("params") or {}).get("preavviso_gg", sx.SX_DEFAULT["preavviso_gg"]))
        for x in pers:
            if x["Scadenza"]:
                ev.append(_ev(data_da(x["Scadenza"]), oggi, "sx", "Formazione / idoneità", f"{x['Documento']} - {x['Persona']}", x["Cantiere"], None, prev))
        for x in docc:
            if x["Presente"] and x["Scadenza"]:
                ev.append(_ev(data_da(x["Scadenza"]), oggi, "sx", "Documento di cantiere", f"{x['Documento']} - {x['Cantiere']}", "", None, prev))
    if p.get("mz"):
        mezzi, _ = mz.normalizza_mezzi(p["mz"].get("mezzi"))
        scad, _ = mz.normalizza_scad(p["mz"].get("scad"), {m["Mezzo"] for m in mezzi})
        prev = int((p["mz"].get("params") or {}).get("preavviso_gg", mz.MZ_DEFAULT["preavviso_gg"]))
        for x in scad:
            if x["Scadenza"]:
                ev.append(_ev(data_da(x["Scadenza"]), oggi, "mz", "Mezzo", f"{x['Documento']} - {x['Mezzo']}", "", None, prev))
    if categorie:
        ev = [e for e in ev if e["Categoria"] in categorie]
    ev = [e for e in ev if e["Giorni"] <= orizzonte_gg]
    ev.sort(key=lambda e: (e["Data"], e["Categoria"], e["Titolo"]))
    return ev


def riassunto(ev):
    return {"scadute": sum(1 for e in ev if e["Giorni"] < 0), "settimana": sum(1 for e in ev if 0 <= e["Giorni"] <= 7), "mese": sum(1 for e in ev if 7 < e["Giorni"] <= 30),
            "oltre": sum(1 for e in ev if e["Giorni"] > 30), "totale": len(ev)}


def genera_ics(ev, nome="FCR Scadenze"):
    """File iCalendar (importabile in Google Calendar, Outlook, iPhone) con gli eventi non ancora scaduti, a giornata intera."""
    def esc(s):
        return str(s).replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")
    righe = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//FCR General Contractor//Scadenze//IT", "CALSCALE:GREGORIAN", f"X-WR-CALNAME:{esc(nome)}"]
    for e in ev:
        if e["Giorni"] < 0:
            continue
        uid = hashlib.sha1(f"{e['Data']}{e['Categoria']}{e['Titolo']}".encode()).hexdigest()[:16] + "@fcr"
        fine = e["Data"] + dt.timedelta(days=1)
        desc = e["Dettaglio"] + (f" - {e['Importo']:,.0f} EUR".replace(",", ".") if e["Importo"] else "")
        righe += ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}", f"DTSTART;VALUE=DATE:{e['Data'].strftime('%Y%m%d')}",
                  f"DTEND;VALUE=DATE:{fine.strftime('%Y%m%d')}", f"SUMMARY:{esc(e['Categoria'] + ': ' + e['Titolo'])}", f"DESCRIPTION:{esc(desc.strip(' -'))}",
                  "BEGIN:VALARM", "TRIGGER:-P1D", "ACTION:DISPLAY", "DESCRIPTION:Scadenza domani", "END:VALARM", "END:VEVENT"]
    righe.append("END:VCALENDAR")
    return "\r\n".join(righe) + "\r\n"
