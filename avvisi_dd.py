"""avvisi_dd.py - Avvisi del Cruscotto: i semafori gialli e rossi vengono mandati per email e nella chat interna a chi e' incaricato.

Per ogni area (Cassa, Margine, Crediti, ...) si indica: da quale gravita' avvisare, il canale della chat, le persone (chat diretta + avviso sul telefono)
e gli indirizzi email. Lo stesso problema si invia al massimo una volta al giorno. Email: stessi Secrets di sempre (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, MAIL_FROM).
"""
import os
import re
import smtplib
from email.message import EmailMessage

import chat
import notifiche
import storage

NOME_CFG = "avvisi_cruscotto"
NOME_STATO = "avvisi_cruscotto_stato"
AUTORE_CHAT = "Cruscotto"
AREE = ["Cassa", "Crediti", "Debiti", "Liquidita' di cantiere", "Margine", "Rating", "Piano", "Commerciale", "Commesse", "Cantieri", "Fornitori", "Sicurezza", "Mezzi", "Organico"]
TUTTE = "Tutte le aree"
GRAVITA = {"bad": "Solo rosso", "warn": "Giallo e rosso"}
ETICHETTA_STATO = {"bad": "ROSSO", "warn": "GIALLO"}
EMAIL_RE = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")


def _lista(v):
    if isinstance(v, str):
        v = re.split(r"[,;\n]", v)
    return [str(x).strip() for x in (v or []) if str(x).strip()]


def normalizza(cfg):
    """Pulisce le regole: area valida, gravita' valida, email e persone come liste. Le regole senza destinatari si scartano."""
    cfg = cfg if isinstance(cfg, dict) else {}
    regole = []
    for r in cfg.get("regole") or []:
        area = str(r.get("area") or "").strip()
        if area != TUTTE and area not in AREE:
            continue
        da = r.get("da") if r.get("da") in GRAVITA else "bad"
        canale = str(r.get("canale") or "").strip()
        persone, email = _lista(r.get("persone")), [e for e in _lista(r.get("email")) if EMAIL_RE.match(e)]
        if canale or persone or email:
            regole.append({"area": area, "da": da, "canale": canale, "persone": persone, "email": email})
    rep = cfg.get("report") if isinstance(cfg.get("report"), dict) else {}
    report = {"attivo": bool(rep.get("attivo")), "email": [e for e in _lista(rep.get("email")) if EMAIL_RE.match(e)]}
    return {"regole": regole, "auto": bool(cfg.get("auto", True)), "report": report}


def carica_cfg(path=None):
    try:
        raw = storage.cache_lettura("avvisi_dd_cfg", lambda: storage.carica_pratica(NOME_CFG, path, modulo="cfg"), path, ttl=20)
    except Exception:
        raw = None
    return normalizza(raw)


def salva_cfg(cfg, autore="", path=None):
    cfg = normalizza(cfg)
    storage.salva_pratica(NOME_CFG, cfg, path, autore=autore, modulo="cfg")
    return cfg


def _carica_stato(path=None):
    try:
        s = storage.carica_pratica(NOME_STATO, path, modulo="cfg") or {}
    except Exception:
        s = {}
    return s if isinstance(s, dict) else {}


def _salva_stato(inviati, path=None, **altro):
    """Salva lo stato degli invii, tenendo gli altri campi (per esempio la data dell'ultimo rapporto settimanale)."""
    stato = _carica_stato(path)
    stato["inviati"] = inviati
    stato.update(altro)
    storage.salva_pratica(NOME_STATO, stato, path, autore=AUTORE_CHAT, modulo="cfg")


def _chiave(riga):
    return f"{riga.get('Area')}|{riga.get('Indicatore')}|{riga.get('Stato')}"


def _pertinente(regola, riga):
    if riga.get("Stato") not in ("bad", "warn"):
        return False
    if regola["area"] not in (TUTTE, riga.get("Area")):
        return False
    return riga["Stato"] == "bad" or regola["da"] == "warn"


def da_inviare(righe, cfg, inviati=None, oggi="", forza=False):
    """[(regola, [righe])]: per ogni regola i semafori da comunicare, escludendo quelli gia' mandati oggi (salvo `forza`)."""
    inviati = inviati or {}
    out = []
    for r in cfg["regole"]:
        pert = [x for x in righe if _pertinente(r, x) and (forza or inviati.get(f"{_chiave(x)}>{id_regola(r)}") != oggi)]
        if pert:
            out.append((r, pert))
    return out


def id_regola(r):
    return f"{r['area']}/{r['da']}/{r['canale']}/{','.join(r['persone'])}/{','.join(r['email'])}"


def testo_avviso(righe_regola, link=""):
    righe = sorted(righe_regola, key=lambda x: x["Stato"] != "bad")
    out = [f"Cruscotto di direzione: {len(righe)} semafor{'o' if len(righe) == 1 else 'i'} da guardare"]
    for r in righe:
        out.append(f"- {ETICHETTA_STATO[r['Stato']]} · {r['Area']} · {r['Indicatore']}: {r['Valore']}" + (f" ({r['Nota']})" if r.get("Nota") else ""))
    if link:
        out.append("\nApri la suite: " + link)
    return "\n".join(out)


def smtp_pronto(env=None):
    env = env or os.environ
    return bool(env.get("SMTP_HOST") and env.get("SMTP_USER") and env.get("SMTP_PASSWORD"))


def _mail_smtp(destinatari, oggetto, corpo, env=None, allegati=()):
    env = env or os.environ
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = oggetto, env.get("MAIL_FROM") or env["SMTP_USER"], ", ".join(destinatari)
    msg.set_content(corpo)
    for nome, dati, mime in allegati:
        tipo, sotto = mime.split("/", 1)
        msg.add_attachment(dati, maintype=tipo, subtype=sotto, filename=nome)
    porta = int(env.get("SMTP_PORT", "587") or 587)
    if porta == 465:
        with smtplib.SMTP_SSL(env["SMTP_HOST"], porta, timeout=30) as s:
            s.login(env["SMTP_USER"], env["SMTP_PASSWORD"])
            s.send_message(msg)
    else:
        with smtplib.SMTP(env["SMTP_HOST"], porta, timeout=30) as s:
            s.starttls()
            s.login(env["SMTP_USER"], env["SMTP_PASSWORD"])
            s.send_message(msg)


MAIL = _mail_smtp          # sostituibile nei test


def _canale_pubblico(nome, path=None):
    for c in chat.tutti_i_canali_gestibili(path):
        if c["tipo"] == "pubblico" and not c["archiviato"] and c["nome"].lower() == nome.lower():
            return c["id"]
    return None


def invia(righe, cfg=None, path=None, forza=False, oggi=None, utenti_noti=(), link=None, sincrono=False):
    """Manda gli avvisi dovuti. Restituisce {'chat': n, 'email': n, 'telefono': n, 'saltati': n, 'errori': [..], 'regole': n}."""
    cfg = cfg or carica_cfg(path)
    oggi = oggi or storage._now()[:10]
    stato = _carica_stato(path)
    inviati = {k: v for k, v in (stato.get("inviati") or {}).items() if str(v)[:7] == oggi[:7]}      # tiene solo il mese corrente
    esito = {"chat": 0, "email": 0, "telefono": 0, "saltati": 0, "errori": [], "regole": 0}
    link = notifiche.app_url() if link is None else link
    dovuti = da_inviare(righe, cfg, inviati, oggi, forza)
    esito["saltati"] = sum(len([x for x in righe if _pertinente(r, x)]) for r in cfg["regole"]) - sum(len(p) for _, p in dovuti)
    noti = set(utenti_noti) | {p for r in cfg["regole"] for p in r["persone"]}
    for regola, pert in dovuti:
        testo = testo_avviso(pert, link)
        ok = False
        if regola["canale"]:
            cid = _canale_pubblico(regola["canale"], path)
            if cid is None:
                esito["errori"].append(f"Canale «{regola['canale']}» non trovato o archiviato.")
            else:
                citati = " ".join("@" + p for p in regola["persone"])
                corpo_chat = testo.split("\nApri la suite")[0] + (("\n" + citati) if citati else "")
                info = chat.invia(cid, AUTORE_CHAT, "utente", corpo_chat, path=path)
                esito["chat"] += 1
                esito["telefono"] += notifiche.avvisa(info, AUTORE_CHAT, corpo_chat, noti, path, sincrono=sincrono)
                ok = True
        for p in regola["persone"]:
            try:
                cid = chat.canale_diretto(AUTORE_CHAT, p, path)
                info = chat.invia(cid, AUTORE_CHAT, "utente", testo.split("\nApri la suite")[0], path=path)
                esito["chat"] += 1
                esito["telefono"] += notifiche.avvisa(info, AUTORE_CHAT, "", noti, path, sincrono=sincrono)
                ok = True
            except (ValueError, PermissionError) as e:
                esito["errori"].append(f"{p}: {e}")
        if regola["email"]:
            try:
                MAIL(regola["email"], f"FCR Suite - Cruscotto: {len(pert)} avvisi", testo)
                esito["email"] += len(regola["email"])
                ok = True
            except Exception as e:
                esito["errori"].append(f"Email non inviata ({type(e).__name__}): controlla SMTP_HOST, SMTP_USER e SMTP_PASSWORD nei Secrets.")
        if ok:
            esito["regole"] += 1
            for x in pert:
                inviati[f"{_chiave(x)}>{id_regola(regola)}"] = oggi
    if esito["regole"]:
        _salva_stato(inviati, path)
        storage.svuota_cache()
    return esito


# ----------------------------------------------------------------------------
# Rapporto settimanale e controllo programmato (si lancia da cron / GitHub Actions: vedi job_avvisi.py)
# ----------------------------------------------------------------------------
def rapporto_pdf(righe, generale, azioni, fonti):
    import dd_report
    ctx = dd_report.costruisci_ctx_dd(righe, generale, azioni, fonti)
    return dd_report.genera_pdf_dd(ctx), ctx["report_id"]


def invia_rapporto(righe, generale, azioni, fonti, cfg=None, path=None, forza=False, oggi=None):
    """Manda il PDF del Cruscotto per email a chi e' indicato in «Rapporto settimanale». Una sola volta al giorno (salvo `forza`).
    Restituisce {'email': n, 'errori': [...], 'saltato': motivo|''}."""
    cfg = cfg or carica_cfg(path)
    oggi = oggi or storage._now()[:10]
    esito = {"email": 0, "errori": [], "saltato": ""}
    rep = cfg["report"]
    if not rep["attivo"] or not rep["email"]:
        esito["saltato"] = "rapporto non attivo o senza indirizzi"
        return esito
    if not forza and _carica_stato(path).get("ultimo_rapporto") == oggi:
        esito["saltato"] = "gia' inviato oggi"
        return esito
    try:
        pdf, rid = rapporto_pdf(righe, generale, azioni, fonti)
        c = {"ok": 0, "warn": 0, "bad": 0, "nd": 0}
        for r in righe:
            c[r["Stato"]] = c.get(r["Stato"], 0) + 1
        corpo = (f"Rapporto di direzione FCR del {oggi[8:]}/{oggi[5:7]}/{oggi[:4]}\n\n{c['bad']} semafori rossi, {c['warn']} gialli, {c['ok']} in regola.\n"
                 "Il PDF allegato riporta semafori, azioni da fare e fonti dei dati.\n\nMessaggio automatico della FCR Suite: le simulazioni sono indicative.")
        MAIL(rep["email"], f"FCR - Rapporto di direzione del {oggi[8:]}/{oggi[5:7]}/{oggi[:4]}", corpo, allegati=[(f"Cruscotto_{rid}.pdf", pdf, "application/pdf")])
        esito["email"] = len(rep["email"])
        _salva_stato((_carica_stato(path).get("inviati") or {}), path, ultimo_rapporto=oggi)
        storage.svuota_cache()
    except Exception as e:
        esito["errori"].append(f"Rapporto non inviato ({type(e).__name__}): controlla le impostazioni SMTP nei Secrets.")
    return esito
