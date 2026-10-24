"""chat.py - Chat interna: canali, chat dirette, messaggi, non letti, allegati e preferenze di avviso (senza Streamlit, quindi testabile).

Regole di riservatezza (decise dalla direzione):
- le chat dirette e i gruppi privati sono visibili SOLO ai loro membri: nessun amministratore le legge, nemmeno dall'esportazione;
- se e' impostato il segreto CHAT_KEY, il testo e gli allegati delle chat dirette e private sono cifrati nel database (Fernet);
- l'esportazione e la moderazione riguardano solo i canali pubblici e lasciano traccia nel registro attivita'.
"""
import base64
import contextlib
import hashlib
import io
import os
import re
import secrets
import time

import storage

LIMITE_FOTO_PX = 1600                 # le foto si riducono a questo lato maggiore (JPEG): una foto da telefono scende a poche centinaia di KB
LIMITE_FOTO_ORIGINALE_MB = 12
LIMITE_PDF_MB = 8
MAX_TESTO = 4000
FINESTRA = 80                         # messaggi mostrati
TIPI = ("pubblico", "privato", "diretto")
MODI_AVVISO = {"menzioni": "Solo messaggi diretti e menzioni (@nome)", "tutto": "Tutti i messaggi dei miei canali", "niente": "Nessun avviso"}
PREFISSO_CIFRATO = "enc:"
CFG_NOME = "chat"


# ----------------------------------------------------------------------------
# Cifratura (facoltativa)
# ----------------------------------------------------------------------------
def chiave_segreta():
    k = os.environ.get("CHAT_KEY", "").strip()
    if not k:
        try:
            import streamlit as st
            k = str(st.secrets.get("CHAT_KEY", "") or "").strip()
        except Exception:
            k = ""
    return k


def _fernet():
    k = chiave_segreta()
    if not k:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(base64.urlsafe_b64encode(hashlib.sha256(k.encode("utf-8")).digest()))
    except Exception:
        return None


def cifratura_attiva():
    return _fernet() is not None


def _cifra(testo):
    f = _fernet()
    return PREFISSO_CIFRATO + f.encrypt(testo.encode("utf-8")).decode("ascii") if f else testo


def _decifra(testo):
    if not testo or not str(testo).startswith(PREFISSO_CIFRATO):
        return testo or ""
    f = _fernet()
    if not f:
        return "[messaggio cifrato: manca la chiave CHAT_KEY]"
    try:
        return f.decrypt(testo[len(PREFISSO_CIFRATO):].encode("ascii")).decode("utf-8")
    except Exception:
        return "[messaggio cifrato con un'altra chiave]"


# ----------------------------------------------------------------------------
# Database
# ----------------------------------------------------------------------------
_PRONTO = set()


def _ddl(pg):
    pk = "SERIAL PRIMARY KEY" if pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
    return [
        f"CREATE TABLE IF NOT EXISTS chat_canali (id {pk}, nome TEXT UNIQUE, tipo TEXT, descrizione TEXT, creato TEXT, creato_da TEXT, archiviato INTEGER DEFAULT 0)",
        "CREATE TABLE IF NOT EXISTS chat_membri (canale_id INTEGER, username TEXT, PRIMARY KEY (canale_id, username))",
        f"CREATE TABLE IF NOT EXISTS chat_messaggi (id {pk}, canale_id INTEGER, autore TEXT, ts TEXT, testo TEXT, cifrato INTEGER DEFAULT 0, "
        "allegato_nome TEXT, allegato_tipo TEXT, allegato_dati TEXT, link_modulo TEXT, link_etichetta TEXT, eliminato INTEGER DEFAULT 0)",
        "CREATE INDEX IF NOT EXISTS chat_msg_canale ON chat_messaggi (canale_id, id)",
        "CREATE TABLE IF NOT EXISTS chat_letture (canale_id INTEGER, username TEXT, ultimo_id INTEGER DEFAULT 0, PRIMARY KEY (canale_id, username))",
        "CREATE TABLE IF NOT EXISTS chat_avvisi (username TEXT PRIMARY KEY, telegram_chat_id TEXT, telegram_codice TEXT, ntfy_topic TEXT, "
        "modo TEXT DEFAULT 'menzioni', silenzio_da TEXT, silenzio_a TEXT)",
    ]


@contextlib.contextmanager
def _db(path=None):
    with storage._db(path) as con:
        chiave = storage._identita_db(path)[:2]
        if chiave not in _PRONTO or (chiave[0] == "sqlite" and not os.path.exists(chiave[1])):
            for ddl in _ddl(isinstance(con, storage._ConPG)):
                con.execute(ddl)
            _PRONTO.add(chiave)
        yield con


def _inserisci(con, sql, par):
    """INSERT che restituisce l'id nuovo, in SQLite e in PostgreSQL."""
    if isinstance(con, storage._ConPG):
        return con.execute(sql + " RETURNING id", par).fetchone()[0]
    return con.execute(sql, par).lastrowid


def _ora():
    return storage._now()


# ----------------------------------------------------------------------------
# Configurazione (chi gestisce i canali)
# ----------------------------------------------------------------------------
def carica_cfg(path=None):
    try:
        raw = storage.cache_lettura("chat_cfg", lambda: storage.carica_pratica(CFG_NOME, path, modulo="cfg"), path, ttl=20)
    except Exception:
        raw = None
    raw = raw if isinstance(raw, dict) else {}
    return {"gestori": sorted({str(u).strip().lower() for u in (raw.get("gestori") or []) if str(u).strip()})}


def salva_cfg(cfg, autore="", path=None):
    cfg = {"gestori": sorted({str(u).strip().lower() for u in (cfg.get("gestori") or []) if str(u).strip()})}
    storage.salva_pratica(CFG_NOME, cfg, path, autore=autore, modulo="cfg")
    return cfg


def e_gestore(utente, cfg=None):
    """Gestisce i canali (crea, archivia, modera quelli pubblici): gli amministratori e le persone scelte da loro."""
    if (utente or {}).get("ruolo") == "admin":
        return True
    cfg = cfg if cfg is not None else carica_cfg()
    return str((utente or {}).get("username", "")).strip().lower() in set(cfg["gestori"])


def puo_scrivere(utente):
    return (utente or {}).get("ruolo") in ("admin", "utente")


# ----------------------------------------------------------------------------
# Canali
# ----------------------------------------------------------------------------
def _nome_valido(nome):
    nome = re.sub(r"\s+", " ", str(nome or "").strip())
    if not 2 <= len(nome) <= 40 or "|" in nome or nome.lower().startswith("dm:"):
        raise ValueError("Il nome del canale deve avere da 2 a 40 caratteri e non contenere «|».")
    return nome


def crea_canale(nome, tipo, creato_da, membri=(), descrizione="", path=None):
    if tipo not in ("pubblico", "privato"):
        raise ValueError("Tipo di canale non valido.")
    nome = _nome_valido(nome)
    with _db(path) as con:
        if con.execute("SELECT 1 FROM chat_canali WHERE LOWER(nome)=?", (nome.lower(),)).fetchone():
            raise ValueError("Esiste gia' un canale con questo nome.")
        cid = _inserisci(con, "INSERT INTO chat_canali (nome, tipo, descrizione, creato, creato_da, archiviato) VALUES (?,?,?,?,?,0)",
                         (nome, tipo, str(descrizione or "")[:200], _ora(), creato_da))
        if tipo == "privato":
            for u in {str(m).strip() for m in list(membri) + [creato_da] if str(m).strip()}:
                con.execute("INSERT INTO chat_membri (canale_id, username) VALUES (?,?)", (cid, u))
    storage.svuota_cache()
    return cid


CANALI_INIZIALI = [
    ("Generale", "Avvisi e comunicazioni a tutta l'azienda"),
    ("Cantieri", "Avanzamento lavori, problemi e richieste dai cantieri"),
    ("Commerciale e gare", "Offerte, sopralluoghi, gare e pratiche con i clienti"),
    ("Amministrazione e fatture", "Fatture, pagamenti, incassi e scadenze"),
    ("Acquisti e fornitori", "Ordini, preventivi e documenti dei fornitori"),
    ("Sicurezza", "Sicurezza nei cantieri, DPI, formazione e segnalazioni"),
    ("Mezzi e logistica", "Parco mezzi, noli, consegne e manutenzioni"),
    ("Legale e contratti", "Contratti, riserve e passaggi allo studio legale"),
    ("Assistenza suite", "Domande e segnalazioni sull'uso della FCR Suite"),
    ("Idee e suggerimenti", "Proposte per migliorare il lavoro e la suite"),
]


def crea_canali_iniziali(creato_da="sistema", solo_se_vuoto=True, path=None):
    """Crea i canali pubblici consigliati. Con solo_se_vuoto (predefinito) lo fa una volta sola, quando non esiste ancora nessun canale pubblico
    (anche archiviato), cosi' un canale tolto dopo non ricompare. Restituisce quanti ne ha creati."""
    with _db(path) as con:
        if solo_se_vuoto and con.execute("SELECT 1 FROM chat_canali WHERE tipo='pubblico'").fetchone():
            return 0
    n = 0
    for nome, desc in CANALI_INIZIALI:
        try:
            crea_canale(nome, "pubblico", creato_da, descrizione=desc, path=path)
            n += 1
        except ValueError:
            pass
    return n


def canale_diretto(a, b, path=None):
    """Chat diretta tra due persone: la crea se non esiste e restituisce il suo id."""
    a, b = str(a).strip(), str(b).strip()
    if not a or not b or a.lower() == b.lower():
        raise ValueError("Scegli un'altra persona.")
    x, y = sorted([a, b], key=str.lower)
    nome = f"dm:{x}|{y}"
    with _db(path) as con:
        r = con.execute("SELECT id FROM chat_canali WHERE nome=?", (nome,)).fetchone()
        if r:
            return r[0]
        cid = _inserisci(con, "INSERT INTO chat_canali (nome, tipo, descrizione, creato, creato_da, archiviato) VALUES (?,?,?,?,?,0)",
                         (nome, "diretto", "", _ora(), a))
        for u in (x, y):
            con.execute("INSERT INTO chat_membri (canale_id, username) VALUES (?,?)", (cid, u))
    return cid


def _canale(con, cid):
    r = con.execute("SELECT id, nome, tipo, descrizione, archiviato FROM chat_canali WHERE id=?", (cid,)).fetchone()
    return dict(zip(("id", "nome", "tipo", "descrizione", "archiviato"), r)) if r else None


def e_membro(con, cid, username):
    return bool(con.execute("SELECT 1 FROM chat_membri WHERE canale_id=? AND username=?", (cid, username)).fetchone())


def puo_accedere(con, canale, username):
    """Pubblico: tutti. Privato e diretto: solo i membri (nessuna eccezione per gli amministratori)."""
    return bool(canale) and (canale["tipo"] == "pubblico" or e_membro(con, canale["id"], username))


def etichetta(canale, username):
    """Nome da mostrare: per la chat diretta e' il nome dell'altra persona."""
    if canale["tipo"] == "diretto":
        parti = canale["nome"][3:].split("|")
        altri = [p for p in parti if p.lower() != str(username).lower()]
        return altri[0] if altri else parti[0]
    return canale["nome"]


def canali_visibili(username, path=None, archiviati=False):
    """Canali che la persona puo' aprire, con i messaggi non letti. [{id, nome, tipo, descrizione, non_letti, ultimo_id, etichetta}]"""
    with _db(path) as con:
        righe = con.execute(
            "SELECT c.id, c.nome, c.tipo, c.descrizione, "
            "(SELECT COUNT(*) FROM chat_messaggi m WHERE m.canale_id=c.id AND m.eliminato=0 AND m.autore<>? AND m.id > "
            " COALESCE((SELECT l.ultimo_id FROM chat_letture l WHERE l.canale_id=c.id AND l.username=?), -1)), "
            "(SELECT MAX(m.id) FROM chat_messaggi m WHERE m.canale_id=c.id), "
            "(SELECT l.ultimo_id FROM chat_letture l WHERE l.canale_id=c.id AND l.username=?) "
            "FROM chat_canali c WHERE c.archiviato=? AND (c.tipo='pubblico' OR EXISTS "
            "(SELECT 1 FROM chat_membri b WHERE b.canale_id=c.id AND b.username=?)) ORDER BY c.tipo, c.nome",
            (username, username, username, 1 if archiviati else 0, username)).fetchall()
        out = []
        for cid, nome, tipo, desc, nl, ultimo, letto in righe:
            if letto is None and tipo == "pubblico":                 # canale pubblico mai aperto: la storia precedente non conta come non letta
                con.execute("INSERT INTO chat_letture (canale_id, username, ultimo_id) VALUES (?,?,?)", (cid, username, ultimo or 0))
                nl = 0
            c = {"id": cid, "nome": nome, "tipo": tipo, "descrizione": desc or "", "non_letti": nl or 0, "ultimo_id": ultimo or 0}
            c["etichetta"] = etichetta(c, username)
            out.append(c)
    out.sort(key=lambda c: ({"pubblico": 0, "privato": 1, "diretto": 2}[c["tipo"]], c["nome"] != "Generale", c["etichetta"].lower()))
    return out


def non_letti_totale(username, path=None):
    """Totale dei messaggi non letti (per il contatore nella barra laterale). Ricordato per pochi secondi."""
    def calcola():
        return sum(c["non_letti"] for c in canali_visibili(username, path))
    return storage.cache_lettura(f"chat_nl_{username}", calcola, path, ttl=6)


def membri(cid, path=None):
    with _db(path) as con:
        return sorted(r[0] for r in con.execute("SELECT username FROM chat_membri WHERE canale_id=?", (cid,)).fetchall())


def imposta_membri(cid, utenti, path=None):
    with _db(path) as con:
        c = _canale(con, cid)
        if not c or c["tipo"] != "privato":
            raise ValueError("Solo i gruppi privati hanno una lista di membri.")
        con.execute("DELETE FROM chat_membri WHERE canale_id=?", (cid,))
        for u in {str(x).strip() for x in utenti if str(x).strip()}:
            con.execute("INSERT INTO chat_membri (canale_id, username) VALUES (?,?)", (cid, u))
    storage.svuota_cache()


def archivia_canale(cid, archiviato=True, path=None):
    with _db(path) as con:
        c = _canale(con, cid)
        if not c or c["tipo"] == "diretto":
            raise ValueError("Le chat dirette non si archiviano.")
        con.execute("UPDATE chat_canali SET archiviato=? WHERE id=?", (1 if archiviato else 0, cid))
    storage.svuota_cache()


def tutti_i_canali_gestibili(path=None):
    """Elenco per la gestione: SOLO canali pubblici e gruppi privati (mai le chat dirette). Dei gruppi privati si vede solo il nome, non i messaggi."""
    with _db(path) as con:
        return [dict(zip(("id", "nome", "tipo", "descrizione", "archiviato"), r)) for r in
                con.execute("SELECT id, nome, tipo, descrizione, archiviato FROM chat_canali WHERE tipo<>'diretto' ORDER BY archiviato, tipo, nome").fetchall()]


# ----------------------------------------------------------------------------
# Messaggi
# ----------------------------------------------------------------------------
def prepara_allegato(nome, dati):
    """(nome, tipo, base64) pronto da salvare. Le foto si ridimensionano; i PDF hanno un limite. Altri file: rifiutati."""
    nome = os.path.basename(str(nome or "file")).strip() or "file"
    low = nome.lower()
    if low.endswith(".pdf"):
        if len(dati) > LIMITE_PDF_MB * 1024 * 1024:
            raise ValueError(f"Il PDF supera il limite di {LIMITE_PDF_MB} MB.")
        if not dati.startswith(b"%PDF"):
            raise ValueError("Il file non sembra un PDF.")
        return nome, "application/pdf", base64.b64encode(dati).decode("ascii")
    if low.endswith((".jpg", ".jpeg", ".png", ".webp", ".heic")):
        if len(dati) > LIMITE_FOTO_ORIGINALE_MB * 1024 * 1024:
            raise ValueError(f"La foto supera il limite di {LIMITE_FOTO_ORIGINALE_MB} MB.")
        try:
            from PIL import Image, ImageOps
            with Image.open(io.BytesIO(dati)) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                if max(im.size) > LIMITE_FOTO_PX:
                    im.thumbnail((LIMITE_FOTO_PX, LIMITE_FOTO_PX))
                buf = io.BytesIO()
                im.save(buf, format="JPEG", quality=82, optimize=True)
        except Exception:
            raise ValueError("La foto non si riesce a leggere.")
        base = os.path.splitext(nome)[0] or "foto"
        return base + ".jpg", "image/jpeg", base64.b64encode(buf.getvalue()).decode("ascii")
    raise ValueError("Si possono allegare foto (JPG, PNG, WEBP) e PDF.")


def menzioni(testo, utenti_noti):
    """Nomi utente citati con @nome (solo quelli esistenti)."""
    noti = {str(u).lower(): u for u in utenti_noti}
    return {noti[m.lower()] for m in re.findall(r"@([A-Za-z0-9_.\-]+)", testo or "") if m.lower() in noti}


def invia(cid, autore, ruolo, testo="", allegato=None, link=None, path=None):
    """Scrive un messaggio. `allegato` = (nome, byte); `link` = (sigla strumento, etichetta). Restituisce {id, canale, tipo}."""
    if ruolo not in ("admin", "utente"):
        raise PermissionError("Con il ruolo «lettore» si possono solo leggere i messaggi.")
    testo = str(testo or "").strip()
    if len(testo) > MAX_TESTO:
        raise ValueError(f"Il messaggio supera {MAX_TESTO} caratteri.")
    all_nome = all_tipo = all_dati = None
    if allegato:
        all_nome, all_tipo, all_dati = prepara_allegato(*allegato)
    if not testo and not all_dati and not link:
        raise ValueError("Scrivi un messaggio o allega qualcosa.")
    with _db(path) as con:
        c = _canale(con, cid)
        if not c or c["archiviato"] or not puo_accedere(con, c, autore):
            raise PermissionError("Non puoi scrivere in questo canale.")
        cifrare = c["tipo"] != "pubblico" and cifratura_attiva()
        t_db = _cifra(testo) if (cifrare and testo) else testo
        d_db = _cifra(all_dati) if (cifrare and all_dati) else all_dati
        mid = _inserisci(con,
                         "INSERT INTO chat_messaggi (canale_id, autore, ts, testo, cifrato, allegato_nome, allegato_tipo, allegato_dati, link_modulo, link_etichetta, eliminato) "
                         "VALUES (?,?,?,?,?,?,?,?,?,?,0)",
                         (cid, autore, _ora(), t_db, 1 if cifrare else 0, all_nome, all_tipo, d_db, (link or (None, None))[0], (link or (None, None))[1]))
        _segna(con, cid, autore, mid)
    storage.svuota_cache()
    return {"id": mid, "canale": cid, "tipo": c["tipo"], "nome": c["nome"]}


def ultimo_id(cid, path=None):
    with _db(path) as con:
        return con.execute("SELECT MAX(id) FROM chat_messaggi WHERE canale_id=?", (cid,)).fetchone()[0] or 0


def messaggi(cid, username, limite=FINESTRA, path=None):
    """Ultimi messaggi, dal piu' vecchio al piu' recente, gia' decifrati. Solo per chi ha accesso al canale."""
    with _db(path) as con:
        c = _canale(con, cid)
        if not puo_accedere(con, c, username):
            raise PermissionError("Non hai accesso a questo canale.")
        righe = con.execute(
            "SELECT id, autore, ts, testo, cifrato, allegato_nome, allegato_tipo, allegato_dati, link_modulo, link_etichetta, eliminato "
            "FROM chat_messaggi WHERE canale_id=? ORDER BY id DESC LIMIT ?", (cid, int(limite))).fetchall()
    out = []
    for mid, aut, ts, testo, cif, an, at, ad, lm, le, el in reversed(righe):
        dati = None
        if ad and not el:
            try:
                dati = base64.b64decode(_decifra(ad)) if cif else base64.b64decode(ad)
            except Exception:
                dati = None
        out.append({"id": mid, "autore": aut, "ts": ts, "testo": "" if el else (_decifra(testo) if cif else (testo or "")), "eliminato": bool(el),
                    "allegato_nome": an if not el else None, "allegato_tipo": at, "allegato": dati, "link_modulo": lm, "link_etichetta": le})
    return out


def _segna(con, cid, username, ultimo):
    r = con.execute("SELECT ultimo_id FROM chat_letture WHERE canale_id=? AND username=?", (cid, username)).fetchone()
    if r is None:
        con.execute("INSERT INTO chat_letture (canale_id, username, ultimo_id) VALUES (?,?,?)", (cid, username, ultimo))
    elif (r[0] or 0) < ultimo:
        con.execute("UPDATE chat_letture SET ultimo_id=? WHERE canale_id=? AND username=?", (ultimo, cid, username))


def segna_letti(cid, username, ultimo, path=None):
    with _db(path) as con:
        _segna(con, cid, username, int(ultimo))
    storage.svuota_cache()


def elimina_messaggio(mid, utente, path=None):
    """Lo puo' fare l'autore; nei canali pubblici anche chi gestisce i canali (moderazione)."""
    with _db(path) as con:
        r = con.execute("SELECT m.autore, c.tipo FROM chat_messaggi m JOIN chat_canali c ON c.id=m.canale_id WHERE m.id=?", (mid,)).fetchone()
        if not r:
            raise ValueError("Messaggio inesistente.")
        autore, tipo = r
        if autore != utente["username"] and not (tipo == "pubblico" and e_gestore(utente)):
            raise PermissionError("Puoi eliminare solo i tuoi messaggi.")
        con.execute("UPDATE chat_messaggi SET eliminato=1, testo='', allegato_dati=NULL, allegato_nome=NULL WHERE id=?", (mid,))
    storage.svuota_cache()


def esporta_canale(cid, utente, path=None):
    """Testo di un canale PUBBLICO, per chi lo gestisce. I gruppi privati e le chat dirette non si esportano per nessuno."""
    if not e_gestore(utente):
        raise PermissionError("Solo chi gestisce i canali puo' esportare.")
    with _db(path) as con:
        c = _canale(con, cid)
        if not c or c["tipo"] != "pubblico":
            raise PermissionError("Si possono esportare solo i canali pubblici.")
        righe = con.execute("SELECT ts, autore, testo, allegato_nome, eliminato FROM chat_messaggi WHERE canale_id=? ORDER BY id", (cid,)).fetchall()
    out = [f"Canale: {c['nome']}  (esportato il {_ora()} UTC)", ""]
    for ts, aut, testo, an, el in righe:
        out.append(f"[{ts[:16]}] {aut}: " + ("(messaggio eliminato)" if el else (testo or "") + (f"  [allegato: {an}]" if an else "")))
    return "\n".join(out)


def pulisci(mesi, path=None):
    """Cancella i messaggi piu' vecchi di `mesi` mesi in tutti i canali. Restituisce quanti ne ha tolti."""
    mesi = int(mesi)
    if mesi < 1:
        raise ValueError("Indica almeno 1 mese.")
    limite = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() - mesi * 30.4375 * 86400))
    with _db(path) as con:
        n = con.execute("SELECT COUNT(*) FROM chat_messaggi WHERE ts<?", (limite,)).fetchone()[0]
        con.execute("DELETE FROM chat_messaggi WHERE ts<?", (limite,))
    storage.svuota_cache()
    return n


# ----------------------------------------------------------------------------
# Preferenze di avviso
# ----------------------------------------------------------------------------
def prefs(username, path=None):
    with _db(path) as con:
        r = con.execute("SELECT telegram_chat_id, telegram_codice, ntfy_topic, modo, silenzio_da, silenzio_a FROM chat_avvisi WHERE username=?", (username,)).fetchone()
    if not r:
        return {"telegram_chat_id": "", "telegram_codice": "", "ntfy_topic": "", "modo": "menzioni", "silenzio_da": "", "silenzio_a": ""}
    return {"telegram_chat_id": r[0] or "", "telegram_codice": r[1] or "", "ntfy_topic": r[2] or "", "modo": r[3] or "menzioni",
            "silenzio_da": r[4] or "", "silenzio_a": r[5] or ""}


def salva_prefs(username, path=None, **campi):
    ammessi = {"telegram_chat_id", "telegram_codice", "ntfy_topic", "modo", "silenzio_da", "silenzio_a"}
    campi = {k: v for k, v in campi.items() if k in ammessi}
    if "modo" in campi and campi["modo"] not in MODI_AVVISO:
        raise ValueError("Modo di avviso non valido.")
    with _db(path) as con:
        if not con.execute("SELECT 1 FROM chat_avvisi WHERE username=?", (username,)).fetchone():
            con.execute("INSERT INTO chat_avvisi (username, modo) VALUES (?, 'menzioni')", (username,))
        if campi:
            con.execute("UPDATE chat_avvisi SET " + ", ".join(f"{k}=?" for k in campi) + " WHERE username=?", (*campi.values(), username))
    storage.svuota_cache()


def nuovo_codice_telegram(username, path=None):
    codice = secrets.token_hex(4)
    salva_prefs(username, path, telegram_codice=codice)
    return codice


def nuovo_topic_ntfy(username, path=None):
    topic = "fcr-" + secrets.token_urlsafe(14).replace("_", "x").replace("-", "y")
    salva_prefs(username, path, ntfy_topic=topic)
    return topic


def scollega_avvisi(username, path=None):
    salva_prefs(username, path, telegram_chat_id="", telegram_codice="", ntfy_topic="")


def in_silenzio(p, adesso=None):
    """True se l'ora (Europe/Rome) cade nella fascia di silenzio della persona."""
    da, a = p.get("silenzio_da") or "", p.get("silenzio_a") or ""
    if not da or not a or da == a:
        return False
    if adesso is None:
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            adesso = datetime.now(ZoneInfo("Europe/Rome")).strftime("%H:%M")
        except Exception:
            adesso = time.strftime("%H:%M")
    return (da <= adesso < a) if da < a else (adesso >= da or adesso < a)


def destinatari_avviso(cid, autore, menzionati, path=None, adesso=None):
    """Persone da avvisare per un nuovo messaggio: [{username, telegram_chat_id, ntfy_topic}]. Rispetta modo e fasce di silenzio."""
    menzionati = {str(m).lower() for m in menzionati}
    with _db(path) as con:
        c = _canale(con, cid)
        if not c:
            return []
        if c["tipo"] == "pubblico":
            candidati = None                                   # tutti, filtrati dal modo
        else:
            candidati = {r[0] for r in con.execute("SELECT username FROM chat_membri WHERE canale_id=?", (cid,)).fetchall()}
        righe = con.execute("SELECT username, telegram_chat_id, ntfy_topic, modo, silenzio_da, silenzio_a FROM chat_avvisi WHERE modo<>'niente'").fetchall()
    out = []
    for u, tg, nt, modo, sd, sa in righe:
        if u == autore or (candidati is not None and u not in candidati) or not (tg or nt):
            continue
        diretto_o_citato = c["tipo"] == "diretto" or u.lower() in menzionati
        if not (diretto_o_citato or modo == "tutto"):
            continue
        if in_silenzio({"silenzio_da": sd, "silenzio_a": sa}, adesso):
            continue
        out.append({"username": u, "telegram_chat_id": tg or "", "ntfy_topic": nt or ""})
    return out
