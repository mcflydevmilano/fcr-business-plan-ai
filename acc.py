"""
acc.py - Accessi del personale: Entrata, Pausa, Rientro, Uscita con il telefono (QR all'ingresso).
Senza Streamlit, quindi testabile.

Regole:
- Entrata e Uscita valgono solo se il telefono e' collegato dalla rete dell'ufficio (indirizzo IP della sede) oppure, da un'altra rete, se la
  posizione letta in QUEL momento e' entro il raggio dalla sede. La posizione non viene mai seguita e non viene salvata: si conserva solo
  il metodo (rete / posizione) e la distanza in metri.
- Pausa e Rientro non chiedono posizione.
- Le correzioni a mano e le annullate restano nel registro, con motivo e nome di chi le ha fatte.
"""
import datetime as dt
import ipaddress
import math

import storage

NOME_CFG = "accessi_cfg"
TIPI = ("entrata", "pausa", "rientro", "uscita")
ETICHETTE = {"entrata": "Entrata", "pausa": "Inizio pausa", "rientro": "Rientro dalla pausa", "uscita": "Uscita"}
CON_CONTROLLO = ("entrata", "uscita")                 # solo queste verificano rete o posizione
CFG_BASE = {"sede": "Via Giovanni Battista Soresina 11, Milano", "lat": None, "lon": None, "raggio_m": 150,
            "ip": [], "max_incertezza_m": 300, "url": "", "pause": False, "esterni": []}


def fuso():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("Europe/Rome")
    except Exception:
        return dt.timezone(dt.timedelta(hours=1))


def adesso_utc():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def a_locale(ts):
    """'2026-11-05 13:27:00' (UTC) -> datetime italiano."""
    d = dt.datetime.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
    return d.astimezone(fuso())


def da_locale(d):
    """datetime italiano (naive) -> stringa UTC."""
    return d.replace(tzinfo=fuso()).astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def intervallo_giorni(da, a):
    """Date locali (inclusi gli estremi) -> estremi UTC per la ricerca."""
    return da_locale(dt.datetime.combine(da, dt.time.min)), da_locale(dt.datetime.combine(a, dt.time(23, 59, 59)))


# ----------------------------------------------------------------------------
# Impostazioni
# ----------------------------------------------------------------------------
def normalizza_cfg(raw):
    c = dict(CFG_BASE)
    raw = raw if isinstance(raw, dict) else {}
    c["sede"] = str(raw.get("sede") or c["sede"]).strip()[:200]
    for k in ("lat", "lon"):
        try:
            v = float(raw.get(k))
            c[k] = v if (-90 <= v <= 90 if k == "lat" else -180 <= v <= 180) else None
        except (TypeError, ValueError):
            c[k] = None
    for k, mn, mx, base in (("raggio_m", 30, 2000, 150), ("max_incertezza_m", 30, 2000, 300)):
        try:
            c[k] = int(min(max(float(raw.get(k, base)), mn), mx))
        except (TypeError, ValueError):
            c[k] = base
    ips = raw.get("ip") or []
    if isinstance(ips, str):
        ips = [x for x in ips.replace(";", ",").replace("\n", ",").split(",")]
    c["ip"] = [x.strip() for x in ips if _rete_valida(x.strip())]
    c["url"] = str(raw.get("url") or "").strip()
    c["pause"] = bool(raw.get("pause", False))
    ext = raw.get("esterni") or []
    if isinstance(ext, str):
        ext = ext.split(",")
    c["esterni"] = sorted({" ".join(str(x).split()).lower() for x in ext if str(x).strip()})
    return c


def _rete_valida(x):
    try:
        ipaddress.ip_network(x, strict=False)
        return True
    except ValueError:
        return False


def carica_cfg(path=None):
    try:
        raw = storage.cache_lettura("accessi_cfg", lambda: storage.carica_pratica(NOME_CFG, path, modulo="cfg"), path, ttl=20)
    except Exception:
        raw = None
    return normalizza_cfg(raw)


def salva_cfg(cfg, autore="", path=None):
    cfg = normalizza_cfg(cfg)
    storage.salva_pratica(NOME_CFG, cfg, path, autore=autore, modulo="cfg")
    return cfg


# ----------------------------------------------------------------------------
# Rete e posizione
# ----------------------------------------------------------------------------
def ip_cliente(intestazioni, ip_diretto=""):
    """Indirizzo del telefono: Cloudflare lo mette in CF-Connecting-IP; altrimenti X-Forwarded-For (il primo) o la connessione diretta."""
    h = {str(k).lower(): str(v) for k, v in (intestazioni or {}).items()}
    for k in ("cf-connecting-ip", "x-real-ip"):
        if h.get(k, "").strip():
            return h[k].strip()
    if h.get("x-forwarded-for", "").strip():
        return h["x-forwarded-for"].split(",")[0].strip()
    return str(ip_diretto or "").strip()


def ip_in_sede(ip, cfg):
    try:
        a = ipaddress.ip_address(str(ip).strip())
    except ValueError:
        return False
    for r in cfg.get("ip") or []:
        try:
            if a in ipaddress.ip_network(r, strict=False):
                return True
        except ValueError:
            continue
    return False


def distanza_m(lat1, lon1, lat2, lon2):
    """Distanza in metri tra due punti (haversine)."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(x))


def valuta_accesso(cfg, ip, pos=None):
    """Controllo per Entrata/Uscita. pos = {'lat', 'lon', 'acc'} letto in quel momento, o None.
    Restituisce {ok, metodo ('rete'|'posizione'|''), distanza_m, serve_posizione, messaggio}."""
    if ip_in_sede(ip, cfg):
        return {"ok": True, "metodo": "rete", "distanza_m": None, "serve_posizione": False, "messaggio": "Collegato dalla rete dell'ufficio."}
    if not pos:
        return {"ok": False, "metodo": "", "distanza_m": None, "serve_posizione": True,
                "messaggio": "Non sei sulla rete dell'ufficio: serve la posizione, letta solo adesso, per verificare che sei in sede."}
    if cfg.get("lat") is None or cfg.get("lon") is None:
        return {"ok": False, "metodo": "", "distanza_m": None, "serve_posizione": False,
                "messaggio": "La posizione della sede non è ancora impostata: avvisa l'amministratore."}
    try:
        lat, lon, acc = float(pos["lat"]), float(pos["lon"]), float(pos.get("acc") or 0)
    except (KeyError, TypeError, ValueError):
        return {"ok": False, "metodo": "", "distanza_m": None, "serve_posizione": True, "messaggio": "Posizione non valida: riprova."}
    if acc > cfg["max_incertezza_m"]:
        return {"ok": False, "metodo": "", "distanza_m": None, "serve_posizione": True,
                "messaggio": f"Il segnale GPS è poco preciso (±{int(acc)} m). Avvicinati a una finestra o all'ingresso e riprova."}
    d = distanza_m(lat, lon, cfg["lat"], cfg["lon"])
    if d <= cfg["raggio_m"]:
        return {"ok": True, "metodo": "posizione", "distanza_m": int(round(d)), "serve_posizione": False, "messaggio": "Posizione verificata."}
    return {"ok": False, "metodo": "", "distanza_m": int(round(d)), "serve_posizione": False,
            "messaggio": f"Risulti a circa {int(round(d))} m dalla sede: la timbratura vale solo in ufficio."}


# ----------------------------------------------------------------------------
# Stato e timbrature
# ----------------------------------------------------------------------------
def stato(eventi, adesso=None):
    """'fuori' | 'dentro' | 'in_pausa' dall'ultima timbratura valida. Se l'ultima e' di un giorno precedente e non e' un'Uscita
    (uscita dimenticata) si riparte da 'fuori': il giorno vecchio resta segnalato come «Uscita mancante»."""
    ultimo = eventi[-1]["tipo"] if eventi else "uscita"
    if eventi and ultimo != "uscita":
        ora = (adesso or adesso_utc()).replace(tzinfo=dt.timezone.utc).astimezone(fuso())
        if a_locale(eventi[-1]["ts"]).date() < ora.date():
            ultimo = "uscita"
    return {"entrata": "dentro", "rientro": "dentro", "pausa": "in_pausa"}.get(ultimo, "fuori")


def azioni_consentite(st_, pause=True):
    """Pulsanti possibili. Con le pause spente (impostazione predefinita) restano solo Entrata e Uscita; chi e' gia' in pausa puo' sempre rientrare."""
    return {"fuori": ["entrata"], "dentro": ["pausa", "uscita"] if pause else ["uscita"], "in_pausa": ["rientro", "uscita"]}[st_]


def puo_fuori_sede(utente, cfg):
    return " ".join(str(utente or "").split()).lower() in set((cfg or {}).get("esterni") or [])


def timbra(utente, tipo, cfg, ip, pos=None, path=None, adesso=None, esterno=None):
    """Registra la timbratura se e' coerente con lo stato e, per Entrata/Uscita, se la sede e' verificata.
    `esterno`: testo di giustificazione (dove va, cosa fa) per chi e' abilitato al lavoro fuori sede: niente verifica di rete o posizione,
    la timbratura resta nel registro come «fuori sede» con la giustificazione. Restituisce {ok, messaggio, stato, serve_posizione}."""
    if tipo not in TIPI:
        return {"ok": False, "messaggio": "Azione non valida.", "stato": "", "serve_posizione": False}
    ev = storage.elenca_timbrature(utente=utente, path=path)
    s = stato(ev, adesso)
    if tipo not in azioni_consentite(s, cfg.get("pause")):
        return {"ok": False, "messaggio": f"Adesso risulti «{s.replace('_', ' ')}»: non puoi registrare «{ETICHETTE[tipo]}».", "stato": s, "serve_posizione": False}
    metodo, dist, nota = "", None, ""
    if esterno is not None:
        if not puo_fuori_sede(utente, cfg):
            return {"ok": False, "messaggio": "Non sei abilitato a timbrare da fuori sede: chiedi all'amministratore.", "stato": s, "serve_posizione": False}
        nota = " ".join(str(esterno).split())[:300]
        if tipo == "entrata" and len(nota) < 5:
            return {"ok": False, "messaggio": "Scrivi dove vai e cosa devi fare (almeno qualche parola).", "stato": s, "serve_posizione": False}
        if tipo not in CON_CONTROLLO:
            return {"ok": False, "messaggio": "Azione non valida da fuori sede.", "stato": s, "serve_posizione": False}
        metodo = "esterno"
    elif tipo in CON_CONTROLLO:
        v = valuta_accesso(cfg, ip, pos)
        if not v["ok"]:
            return {"ok": False, "messaggio": v["messaggio"], "stato": s, "serve_posizione": v["serve_posizione"]}
        metodo, dist = v["metodo"], v["distanza_m"]
    else:
        metodo = "rete" if ip_in_sede(ip, cfg) else "telefono"
    ts = (adesso or adesso_utc()).strftime("%Y-%m-%d %H:%M:%S")
    storage.aggiungi_timbratura(utente, tipo, metodo, dist, nota, utente, ts, path)
    nuovo = stato(ev + [{"tipo": tipo, "ts": ts}], adesso)
    return {"ok": True, "messaggio": f"{ETICHETTE[tipo]} registrata alle {a_locale(ts).strftime('%H:%M')}.", "stato": nuovo, "serve_posizione": False}


def correggi(utente, tipo, quando_locale, nota, autore, path=None):
    """Inserimento a mano (dimenticanze): richiede il motivo. quando_locale = datetime italiano."""
    if tipo not in TIPI:
        raise ValueError("Tipo non valido.")
    if not str(nota or "").strip():
        raise ValueError("Scrivi il motivo della correzione.")
    return storage.aggiungi_timbratura(utente, tipo, "manuale", None, str(nota).strip()[:300], autore, da_locale(quando_locale), path)


def annulla(id_, motivo, autore, path=None):
    if not str(motivo or "").strip():
        raise ValueError("Scrivi il motivo.")
    storage.annulla_timbratura(id_, str(motivo).strip()[:300], autore, path)


# ----------------------------------------------------------------------------
# Riepiloghi
# ----------------------------------------------------------------------------
def riepilogo_giorno(eventi, giorno, adesso=None):
    """Eventi di UNA persona (ordinati). Restituisce {entrata, uscita, lavorato_min, pausa_min, anomalie[], aperta}
    per il giorno locale `giorno` (date)."""
    adesso = adesso or adesso_utc()
    ev = [e for e in eventi if a_locale(e["ts"]).date() == giorno]
    if not ev:
        return None
    lav = pausa = 0.0
    inizio = ini_pausa = None
    anomalie = []
    for e in ev:
        t = a_locale(e["ts"])
        k = e["tipo"]
        if k == "entrata":
            if inizio is not None:
                anomalie.append("Entrata doppia")
            inizio = t
        elif k == "rientro":
            if ini_pausa is not None:
                pausa += (t - ini_pausa).total_seconds() / 60
                ini_pausa = None
            else:
                anomalie.append("Rientro senza pausa")
            inizio = t
        elif k == "pausa":
            if inizio is not None:
                lav += (t - inizio).total_seconds() / 60
                inizio = None
            ini_pausa = t
        elif k == "uscita":
            if inizio is not None:
                lav += (t - inizio).total_seconds() / 60
                inizio = None
            elif ini_pausa is not None:
                pausa += (t - ini_pausa).total_seconds() / 60
                ini_pausa = None
            else:
                anomalie.append("Uscita senza entrata")
    aperta = inizio is not None or ini_pausa is not None
    ora = adesso.replace(tzinfo=dt.timezone.utc).astimezone(fuso())
    if aperta:
        if ora.date() == giorno:
            if inizio is not None:
                lav += (ora - inizio).total_seconds() / 60
            if ini_pausa is not None:
                pausa += (ora - ini_pausa).total_seconds() / 60
        else:
            anomalie.append("Uscita mancante")
    entrate = [a_locale(e["ts"]) for e in ev if e["tipo"] == "entrata"]
    uscite = [a_locale(e["ts"]) for e in ev if e["tipo"] == "uscita"]
    return {"entrata": entrate[0] if entrate else None, "uscita": uscite[-1] if uscite else None, "lavorato_min": int(round(lav)),
            "pausa_min": int(round(pausa)), "anomalie": anomalie, "aperta": aperta and ora.date() == giorno, "manuale": any(e["metodo"] == "manuale" for e in ev),
            "fuori_sede": [str(e.get("nota") or "").strip() for e in ev if e["metodo"] == "esterno" and str(e.get("nota") or "").strip()],
            "esterno": any(e["metodo"] == "esterno" for e in ev)}


def ore(minuti):
    return f"{int(minuti) // 60}:{int(minuti) % 60:02d}"


def tabella(eventi, da, a, adesso=None):
    """Righe per persona e giorno nel periodo (date locali)."""
    per_utente = {}
    for e in eventi:
        per_utente.setdefault(e["utente"], []).append(e)
    righe = []
    for u in sorted(per_utente):
        g = da
        while g <= a:
            r = riepilogo_giorno(per_utente[u], g, adesso)
            if r:
                righe.append({"Persona": u, "Giorno": g, "Entrata": r["entrata"].strftime("%H:%M") if r["entrata"] else "",
                              "Uscita": r["uscita"].strftime("%H:%M") if r["uscita"] else ("in corso" if r["aperta"] else ""),
                              "Ore in ufficio": ore(r["lavorato_min"]), "Pausa": ore(r["pausa_min"]), "_min": r["lavorato_min"],
                              "Note": ", ".join(r["anomalie"] + (["modificata a mano"] if r["manuale"] else []) + (["fuori sede: " + " / ".join(r["fuori_sede"]) if r["fuori_sede"] else "fuori sede"] if r["esterno"] else []))})
            g += dt.timedelta(days=1)
    return righe
