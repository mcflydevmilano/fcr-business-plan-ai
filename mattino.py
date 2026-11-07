"""
mattino.py - «Il mio riepilogo»: ogni mattina, a ciascuno, solo le cose che lo riguardano.

Per ogni persona: i semafori e i compiti urgenti del suo profilo, le offerte da seguire, le scadenze di persone e mezzi, chi e' assente oggi.
Arriva per email (a chi ha l'indirizzo) e, per l'azienda, su Slack. Si accende da Amministrazione e parte dal server (vedi invia_mattino.py).
Il riepilogo generale del Cruscotto (riepilogo.py) resta com'e': questo e' quello personale. Senza Streamlit (testabile).
"""
import datetime as dt
import html
import json
import os
import urllib.request

import miagiornata
import permessi
import posta
import rc
import sd
import storage

NOME_CFG = "mattino_cfg"
NOME_STATO = "mattino_stato"
GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
ICONA = {"bad": "🔴", "warn": "🟡", "ok": "🟢", "nd": "⚪"}
MAX_PER_SEZIONE = 6


def data_it(oggi):
    return f"{GIORNI[oggi.weekday()]} {oggi.day} {MESI[oggi.month - 1]}"


def carica_cfg(path=None):
    try:
        raw = storage.carica_pratica(NOME_CFG, path, modulo="cfg")
    except Exception:
        raw = None
    raw = raw if isinstance(raw, dict) else {}
    return {"attivo": bool(raw.get("attivo", False)), "email": bool(raw.get("email", True)), "slack": bool(raw.get("slack", True)),
            "solo_se_c_e": bool(raw.get("solo_se_c_e", True)), "escludi": sorted({str(x).lower() for x in raw.get("escludi") or []})}


def salva_cfg(cfg, autore="", path=None):
    storage.salva_pratica(NOME_CFG, carica_cfg_da(cfg), path, autore=autore, modulo="cfg")
    storage.svuota_cache()


def carica_cfg_da(cfg):
    return {"attivo": bool(cfg.get("attivo")), "email": bool(cfg.get("email", True)), "slack": bool(cfg.get("slack", True)),
            "solo_se_c_e": bool(cfg.get("solo_se_c_e", True)), "escludi": sorted({str(x).lower() for x in cfg.get("escludi") or []})}


def sezioni(utente, profilo, consentiti, oggi=None, path=None):
    """[(titolo, [righe di testo])] solo con le sezioni che hanno qualcosa da dire."""
    oggi = oggi or dt.date.today()
    consentiti = set(consentiti or [])
    out = []
    nome = (utente or {}).get("username", "")
    # 1) i semafori e i compiti urgenti del profilo
    try:
        import ta
        cas = miagiornata.caselle(utente, profilo, consentiti, compiti=ta.miei(nome, path), oggi=oggi, path=path)
    except Exception:
        cas = []
    urg = [c for c in cas if c["Stato"] in ("bad", "warn")][:MAX_PER_SEZIONE]
    if urg:
        out.append(("Da guardare oggi", [f"{ICONA[c['Stato']]} {c['Area']} · {c['Indicatore']}: {c['Valore']}" + (f" - {c['Nota']}" if c.get("Nota") else "") for c in urg]))
    # 2) offerte da seguire
    if "rc" in consentiti:
        try:
            lista = rc.da_sollecitare(rc.righe_registro(path), oggi, solleciti=rc.carica_solleciti(path))
        except Exception:
            lista = []
        if lista:
            righe = [f"📞 {o['Codice']} · {o['Indirizzo'] or o['Citta']} ({o['Amministratore'] or 'senza referente'}): offerta di {o['Giorni']} giorni fa, nessun seguito" for o in lista[:MAX_PER_SEZIONE]]
            if len(lista) > MAX_PER_SEZIONE:
                righe.append(f"…e altre {len(lista) - MAX_PER_SEZIONE} offerte nel Registro commerciale")
            out.append(("Offerte da seguire", righe))
    # 3) scadenze di persone e mezzi
    if "sd" in consentiti:
        try:
            c = sd.carica(path)
            lista = sd.da_avvisare(c["voci"], oggi, c["preavvisi"])
        except Exception:
            lista = []
        if lista:
            righe = [f"{sd.STATI[v['stato']][0]} {sd.frase(v)}" for v in lista[:MAX_PER_SEZIONE]]
            if len(lista) > MAX_PER_SEZIONE:
                righe.append(f"…e altre {len(lista) - MAX_PER_SEZIONE} scadenze")
            out.append(("Scadenze di persone e mezzi", righe))
    # 3b) impianti ESCo da controllare
    if "mi" in consentiti:
        try:
            import mi
            av = mi.avvisi(mi.carica(path), oggi)
        except Exception:
            av = []
        if av:
            righe = [f"{ICONA.get(s, '•')} {f}" for s, f in av[:MAX_PER_SEZIONE]]
            if len(av) > MAX_PER_SEZIONE:
                righe.append(f"…e altri {len(av) - MAX_PER_SEZIONE} avvisi sugli impianti")
            out.append(("Impianti ESCo", righe))
    # 4) chi manca oggi
    if "fp" in consentiti:
        try:
            import fp
            import richieste
            ass = fp.assenti_il(richieste.elenca(fp.TIPO), oggi, stati=("Approvata",))
        except Exception:
            ass = {}
        if ass:
            out.append(("Chi manca oggi", [f"🏖️ {u}: {t.lower()}" for u, t in sorted(ass.items())]))
    return out


def testo(utente, sez, oggi=None):
    oggi = oggi or dt.date.today()
    nome = (utente or {}).get("username", "").title()
    righe = [f"Buongiorno {nome}, ecco cosa conta oggi, {data_it(oggi)}.", ""]
    if not sez:
        righe.append("Oggi non c'è niente di urgente per te. Buon lavoro!")
    for titolo, rr in sez:
        righe.append(titolo.upper())
        righe += [f"  {r}" for r in rr]
        righe.append("")
    righe.append("Apri la suite: https://suite.piattaformafcr.it")
    return "\n".join(righe)


def corpo_html(utente, sez, oggi=None):
    oggi = oggi or dt.date.today()
    nome = html.escape((utente or {}).get("username", "").title())
    p = [f"<div style='font-family:Arial,sans-serif;max-width:620px;color:#0f172a'><h2 style='color:#1e3fae;margin-bottom:4px'>Buongiorno {nome}</h2>",
         f"<p style='margin-top:0;color:#475569'>Ecco cosa conta oggi, {html.escape(data_it(oggi))}.</p>"]
    if not sez:
        p.append("<p>Oggi non c'è niente di urgente per te. Buon lavoro!</p>")
    for titolo, rr in sez:
        p.append(f"<h3 style='margin:18px 0 6px;font-size:15px;color:#1e3fae'>{html.escape(titolo)}</h3><ul style='padding-left:18px;margin:0'>")
        p += [f"<li style='margin:4px 0'>{html.escape(r)}</li>" for r in rr]
        p.append("</ul>")
    p.append("<p style='margin-top:22px'><a href='https://suite.piattaformafcr.it' style='background:#1e3fae;color:#fff;padding:10px 16px;border-radius:8px;text-decoration:none'>Apri la suite</a></p></div>")
    return "".join(p)


def oggetto(oggi=None):
    return f"☀️ Il tuo riepilogo di oggi · {data_it(oggi or dt.date.today())}"


def _destinatari(path=None):
    """[(utente dict, email)] delle persone attive con un indirizzo valido."""
    out = []
    for u in storage.elenca_utenti(path):
        if u.get("attivo") and posta.indirizzo_valido(u.get("email") or ""):
            out.append(({"username": u["username"], "ruolo": u["ruolo"]}, u["email"].strip()))
    return out


def _stato(path=None):
    try:
        return storage.carica_pratica(NOME_STATO, path, modulo="cfg") or {}
    except Exception:
        return {}


def invia_slack(testo_, env=None):
    env = env or os.environ
    url = (env.get("SLACK_RIEPILOGO_WEBHOOK_URL") or env.get("SLACK_WEBHOOK_URL") or "").strip()
    if not url.startswith("https://hooks.slack.com/"):
        return False
    req = urllib.request.Request(url, data=json.dumps({"text": testo_}).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status == 200


def invia_tutti(path=None, oggi=None, forza=False, env=None):
    """Manda il riepilogo a tutti. Una sola volta al giorno, solo nei giorni feriali (a meno di `forza`). Restituisce {inviati, saltati, errori, slack}."""
    oggi = oggi or dt.date.today()
    rep = {"inviati": [], "saltati": [], "errori": [], "slack": False}
    cfg = carica_cfg(path)
    if not forza and (not cfg["attivo"] or oggi.weekday() >= 5 or _stato(path).get("ultimo") == oggi.isoformat()):
        rep["saltati"].append("non è il momento (spento, fine settimana o già inviato oggi)")
        return rep
    pc = permessi.carica_config(path)
    if cfg["email"]:
        for u, mail in _destinatari(path):
            if u["username"].lower() in cfg["escludi"]:
                rep["saltati"].append(f"{u['username']} (non lo vuole)")
                continue
            sez = sezioni(u, permessi.profilo_di(u, pc), permessi.moduli_consentiti(u, pc), oggi, path)
            if cfg["solo_se_c_e"] and not sez:
                rep["saltati"].append(f"{u['username']} (niente da dire)")
                continue
            try:
                posta.invia([mail], oggetto(oggi), testo(u, sez, oggi), html=corpo_html(u, sez, oggi), env=env, path=path)
                rep["inviati"].append(u["username"])
            except Exception as ex:
                rep["errori"].append(f"{u['username']}: {ex}")
    if cfg["slack"]:
        quadro = {"username": "azienda", "ruolo": "admin"}
        sez = sezioni(quadro, "presidente", set(permessi.TUTTI), oggi, path)
        if sez or not cfg["solo_se_c_e"]:
            try:
                rep["slack"] = invia_slack(testo(quadro, sez, oggi).replace("Buongiorno Azienda", "Buongiorno a tutti"), env)
            except Exception as ex:
                rep["errori"].append(f"Slack: {ex}")
    if rep["inviati"] or rep["slack"]:
        storage.salva_pratica(NOME_STATO, {"ultimo": oggi.isoformat(), "report": {k: v for k, v in rep.items() if k != "slack"}}, path, autore="sistema", modulo="cfg")
    return rep
