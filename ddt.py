"""
ddt.py - Archivio delle bolle (DDT, documenti di trasporto): file PDF, foto ed Excel collegati alle consegne dei Materiali.

Senza Streamlit. I file stanno in una tabella a parte (`ddt_file`), NON nei salvataggi dei Materiali: cosi' non appesantiscono i dati
principali, non finiscono nelle versioni storiche e gli elenchi leggono solo i dati descrittivi (mai i file) anche con migliaia di bolle.
Controlli: tipo reale riconosciuto dal contenuto (non dal nome), dimensione massima, file doppi (stessa impronta), foto ridotte,
Excel letti solo dopo aver verificato che non siano «bombe» (file compressi enormi). Il PDF non viene mai aperto per mostrarlo: se ne legge
solo il testo, e solo per proporre numero e data.
"""
import contextlib
import hashlib
import io
import os
import re
import time
import uuid
import zipfile

import storage

MAX_BYTES = 10 * 1024 * 1024          # per file
MAX_ZIP_ESPANSO = 60 * 1024 * 1024    # un .xlsx che si espande oltre questo limite viene rifiutato
MAX_RIGHE_EXCEL = 5000
ESTENSIONI = {"pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
              "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xls": "application/vnd.ms-excel"}
TIPI_UPLOAD = list(ESTENSIONI)
AVVISO_SPAZIO_MB = 300                # su Neon gratuito il database e' di 512 MB: da qui in poi si avvisa
FILTRO_MAX = 200


class DdtErrore(ValueError):
    """File rifiutato: il messaggio e' scritto per l'utente."""


class DdtDoppio(DdtErrore):
    def __init__(self, id_esistente, numero=""):
        super().__init__("Questo file è già stato caricato" + (f" (DDT {numero})" if numero else "") + ".")
        self.id_esistente = id_esistente


# ----------------------------------------------------------------------------
# Database
# ----------------------------------------------------------------------------
_PRONTO = set()


def _ddl(pg):
    blob = "BYTEA" if pg else "BLOB"
    return ("CREATE TABLE IF NOT EXISTS ddt_file (id TEXT PRIMARY KEY, creato TEXT, ddt_numero TEXT, ddt_data TEXT, fornitore TEXT, commessa TEXT, "
            f"nome_file TEXT, mime TEXT, dimensione INTEGER, sha256 TEXT, caricato_da TEXT, note TEXT, dati {blob})",
            "CREATE INDEX IF NOT EXISTS ddt_file_numero ON ddt_file (ddt_numero)",
            "CREATE INDEX IF NOT EXISTS ddt_file_fornitore ON ddt_file (fornitore)",
            "CREATE INDEX IF NOT EXISTS ddt_file_creato ON ddt_file (creato)",
            "CREATE INDEX IF NOT EXISTS ddt_file_sha ON ddt_file (sha256)")


@contextlib.contextmanager
def _db(path=None):
    with storage._db(path) as con:
        chiave = storage._identita_db(path)[:2]
        if chiave not in _PRONTO or (chiave[0] == "sqlite" and not os.path.exists(chiave[1])):
            for ddl in _ddl(isinstance(con, storage._ConPG)):
                con.execute(ddl)
            _PRONTO.add(chiave)
        yield con


COLONNE_META = ("id", "creato", "ddt_numero", "ddt_data", "fornitore", "commessa", "nome_file", "mime", "dimensione", "caricato_da", "note")
_SEL = ", ".join(COLONNE_META)


def _riga(r):
    return dict(zip(COLONNE_META, r))


# ----------------------------------------------------------------------------
# Controllo e preparazione dei file
# ----------------------------------------------------------------------------
def riconosci(dati):
    """Tipo reale dal contenuto: 'pdf', 'jpg', 'png', 'xlsx', 'xls' oppure None."""
    if dati[:5] == b"%PDF-":
        return "pdf"
    if dati[:3] == b"\xff\xd8\xff":
        return "jpg"
    if dati[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if dati[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(io.BytesIO(dati)) as z:
                if "xl/workbook.xml" in z.namelist():
                    return "xlsx"
        except Exception:
            return None
    if dati[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "xls"
    return None


def nome_sicuro(nome):
    base = os.path.basename(str(nome or "").replace("\\", "/")).strip() or "documento"
    base = re.sub(r"[^\w.\- ()]", "_", base)[:120]
    return base or "documento"


def _zip_sicuro(dati):
    try:
        with zipfile.ZipFile(io.BytesIO(dati)) as z:
            if sum(i.file_size for i in z.infolist()) > MAX_ZIP_ESPANSO or len(z.infolist()) > 2000:
                return False
    except Exception:
        return False
    return True


def prepara(nome, dati):
    """Valida e ottimizza un file. Restituisce (nome_sicuro, tipo, mime, dati_da_salvare). Solleva DdtErrore."""
    if not dati:
        raise DdtErrore("Il file è vuoto.")
    if len(dati) > MAX_BYTES:
        raise DdtErrore(f"Il file pesa {len(dati) / 1048576:.1f} MB: il massimo è {MAX_BYTES // 1048576} MB. Riducilo o scansionalo a risoluzione più bassa.")
    tipo = riconosci(dati)
    if tipo is None:
        raise DdtErrore("Formato non riconosciuto: sono accettati PDF, foto (JPG, PNG) ed Excel (XLSX, XLS).")
    est = os.path.splitext(str(nome))[1].lower().lstrip(".")
    if est in ESTENSIONI and ESTENSIONI[est] != ESTENSIONI[tipo] and not (est in ("jpg", "jpeg") and tipo == "jpg"):
        raise DdtErrore(f"Il file «{nome_sicuro(nome)}» ha l'estensione .{est} ma dentro è un {tipo.upper()}: non lo carico per sicurezza.")
    if tipo == "xlsx" and not _zip_sicuro(dati):
        raise DdtErrore("Il file Excel è troppo grande una volta aperto: non lo carico.")
    nome = nome_sicuro(nome)
    if tipo in ("jpg", "png"):
        dati = _riduci_foto(dati)
        tipo = "jpg"
        nome = os.path.splitext(nome)[0] + ".jpg"
    return nome, tipo, ESTENSIONI[tipo], dati


def _riduci_foto(dati, lato=2000, qualita=80):
    """Le bolle fotografate devono restare leggibili (2000 px), ma non pesare 8 MB: si ricomprimono in JPEG."""
    try:
        from PIL import Image, ImageOps
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(dati))).convert("RGB")
        im.thumbnail((lato, lato))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=qualita, optimize=True)
        out = buf.getvalue()
        return out if len(out) < len(dati) or dati[:3] != b"\xff\xd8\xff" else dati
    except Exception as e:
        raise DdtErrore("La foto non si apre: è rovinata o non è un'immagine valida.") from e


# ----------------------------------------------------------------------------
# Salvataggio e ricerca
# ----------------------------------------------------------------------------
def _s(v, n=200):
    return str(v or "").strip()[:n]


def normalizza_numero(x):
    """'DDT n. 412/A del 28/10' -> '412/A del 28/10' non lo e': qui si pulisce solo il numero: spazi, 'n.', 'DDT'."""
    t = re.sub(r"(?i)\b(d\.?\s?d\.?\s?t\.?|n\.?|nr\.?|numero|doc(?:umento)?)\b[\s.:°]*", "", _s(x, 60)).strip(" .:-")
    return t


def salva(nome, dati, numero="", data="", fornitore="", commessa="", note="", utente="", path=None):
    """Salva un file. Restituisce l'id. Solleva DdtErrore (file non valido) o DdtDoppio (stesso contenuto gia' presente)."""
    nome, tipo, mime, dati = prepara(nome, dati)
    sha = hashlib.sha256(dati).hexdigest()
    with _db(path) as con:
        r = con.execute("SELECT id, ddt_numero FROM ddt_file WHERE sha256=? LIMIT 1", (sha,)).fetchone()
        if r:
            raise DdtDoppio(r[0], r[1] or "")
        i = uuid.uuid4().hex[:16]
        con.execute("INSERT INTO ddt_file (id, creato, ddt_numero, ddt_data, fornitore, commessa, nome_file, mime, dimensione, sha256, caricato_da, note, dati) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (i, storage._now(), normalizza_numero(numero), _s(data, 10), _s(fornitore), _s(commessa), nome, mime, len(dati), sha, _s(utente, 60), _s(note, 500), dati))
    storage.svuota_cache()
    return i


def _filtro(testo, da, a, solo_senza_numero):
    cond, par = [], []
    t = _s(testo, FILTRO_MAX)
    if t:
        cond.append("(LOWER(ddt_numero) LIKE ? OR LOWER(fornitore) LIKE ? OR LOWER(commessa) LIKE ? OR LOWER(nome_file) LIKE ?)")
        par += ["%" + t.lower().replace("%", "") + "%"] * 4
    if da:
        cond.append("COALESCE(NULLIF(ddt_data, ''), SUBSTR(creato, 1, 10)) >= ?")
        par.append(str(da)[:10])
    if a:
        cond.append("COALESCE(NULLIF(ddt_data, ''), SUBSTR(creato, 1, 10)) <= ?")
        par.append(str(a)[:10])
    if solo_senza_numero:
        cond.append("(ddt_numero IS NULL OR ddt_numero = '')")
    return (" WHERE " + " AND ".join(cond)) if cond else "", par


def elenca(testo="", da=None, a=None, solo_senza_numero=False, limite=25, offset=0, path=None):
    """Dati descrittivi (mai i file) dal piu' recente. Con migliaia di bolle si legge una pagina alla volta."""
    w, par = _filtro(testo, da, a, solo_senza_numero)
    with _db(path) as con:
        return [_riga(r) for r in con.execute(f"SELECT {_SEL} FROM ddt_file{w} ORDER BY creato DESC, id LIMIT ? OFFSET ?", (*par, int(limite), int(offset))).fetchall()]


def conta(testo="", da=None, a=None, solo_senza_numero=False, path=None):
    w, par = _filtro(testo, da, a, solo_senza_numero)
    with _db(path) as con:
        return con.execute(f"SELECT COUNT(*) FROM ddt_file{w}", tuple(par)).fetchone()[0]


def leggi(id_, path=None):
    """(dati_descrittivi, bytes) oppure None."""
    with _db(path) as con:
        r = con.execute(f"SELECT {_SEL}, dati FROM ddt_file WHERE id=?", (_s(id_, 40),)).fetchone()
    if not r:
        return None
    return _riga(r[:-1]), bytes(r[-1])


def aggiorna(id_, numero=None, data=None, fornitore=None, commessa=None, note=None, path=None):
    campi = {"ddt_numero": None if numero is None else normalizza_numero(numero), "ddt_data": None if data is None else _s(data, 10),
             "fornitore": None if fornitore is None else _s(fornitore), "commessa": None if commessa is None else _s(commessa), "note": None if note is None else _s(note, 500)}
    campi = {k: v for k, v in campi.items() if v is not None}
    if not campi:
        return False
    with _db(path) as con:
        con.execute(f"UPDATE ddt_file SET {', '.join(k + '=?' for k in campi)} WHERE id=?", (*campi.values(), _s(id_, 40)))
    storage.svuota_cache()
    return True


def elimina(id_, path=None):
    with _db(path) as con:
        con.execute("DELETE FROM ddt_file WHERE id=?", (_s(id_, 40),))
    storage.svuota_cache()


def per_numero(numero, path=None):
    """Tutti i file di un DDT (stesso numero), senza i dati."""
    n = normalizza_numero(numero)
    if not n:
        return []
    with _db(path) as con:
        return [_riga(r) for r in con.execute(f"SELECT {_SEL} FROM ddt_file WHERE ddt_numero=? ORDER BY creato", (n,)).fetchall()]


def numeri_con_file(path=None):
    """Insieme dei numeri DDT che hanno almeno un file allegato (per controllare cosa manca)."""
    with _db(path) as con:
        return {r[0] for r in con.execute("SELECT DISTINCT ddt_numero FROM ddt_file WHERE ddt_numero IS NOT NULL AND ddt_numero <> ''").fetchall()}


def spazio(path=None):
    """(numero_file, byte_totali)."""
    with _db(path) as con:
        n, b = con.execute("SELECT COUNT(*), COALESCE(SUM(dimensione), 0) FROM ddt_file").fetchone()
    return int(n), int(b)


def elenco_per_backup(path=None):
    """Solo i dati descrittivi: i file non entrano nella copia JSON (peserebbero troppo)."""
    with _db(path) as con:
        return [_riga(r) for r in con.execute(f"SELECT {_SEL} FROM ddt_file ORDER BY creato").fetchall()]


# ----------------------------------------------------------------------------
# Lettura del PDF: propone numero e data (da controllare sempre)
# ----------------------------------------------------------------------------
_NUM = re.compile(r"(?i)(?:d\.?\s?d\.?\s?t\.?|documento\s+di\s+trasporto|bolla|d\.?t\.?\s?t\.?)\s*(?:n\.?|nr\.?|numero|n°|num\.?)?\s*[:.]?\s*([A-Z0-9][A-Z0-9/\-_.]{0,20})")
_DATA = re.compile(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4}|\d{2})\b")


def testo_pdf(dati, max_pagine=3):
    try:
        from pypdf import PdfReader
        r = PdfReader(io.BytesIO(dati))
        if r.is_encrypted:
            return ""
        return "\n".join((p.extract_text() or "") for p in r.pages[:max_pagine])[:20000]
    except Exception:
        return ""


def proponi_da_testo(testo):
    """{'numero', 'data', 'fornitore'} - ognuno puo' essere vuoto. Sono suggerimenti: l'utente li conferma."""
    out = {"numero": "", "data": "", "fornitore": ""}
    if not testo:
        return out
    for m in _NUM.finditer(testo):
        cand = m.group(1).strip(".-/")
        if re.search(r"\d", cand) and cand.lower() not in ("del", "data"):
            out["numero"] = cand
            break
    pos = testo.lower().find("data")
    for m in list(_DATA.finditer(testo)):
        g, me, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
        a += 2000 if a < 100 else 0
        if 1 <= g <= 31 and 1 <= me <= 12 and 2000 <= a <= 2100:
            out["data"] = f"{a:04d}-{me:02d}-{g:02d}"
            break
    righe = [x.strip() for x in testo.splitlines() if x.strip()]
    for x in righe[:12]:
        if re.search(r"(?i)\b(s\.?r\.?l|s\.?p\.?a|s\.?n\.?c|s\.?a\.?s|ditta|srl|spa)\b", x) and len(x) < 80:
            out["fornitore"] = x
            break
    return out


def proponi(nome, dati):
    """Suggerimenti per un file: dal testo del PDF, altrimenti dal nome del file (es. DDT_412_2026-10-28.pdf)."""
    tipo = riconosci(dati)
    out = proponi_da_testo(testo_pdf(dati)) if tipo == "pdf" else {"numero": "", "data": "", "fornitore": ""}
    if tipo in ("xlsx", "xls") and not out["numero"]:
        try:                                                        # un Excel con un solo numero DDT in tutte le righe: lo propone
            righe, _, _ = leggi_excel(dati, nome)
            numeri = {r["Ddt"] for r in righe if r["Ddt"]}
            dati_r = {r["Data_consegna"] for r in righe if r["Data_consegna"]}
            fornitori = {r["Fornitore"] for r in righe if r["Fornitore"]}
            out["numero"] = numeri.pop() if len(numeri) == 1 else ""
            out["data"] = out["data"] or (dati_r.pop() if len(dati_r) == 1 else "")
            out["fornitore"] = out["fornitore"] or (fornitori.pop() if len(fornitori) == 1 else "")
        except Exception:
            pass
    if not out["numero"]:
        m = re.search(r"(?i)ddt[\s_\-]*(?:n[\s_\-.]*)?([A-Za-z0-9]+?(?:[/_\-][A-Za-z0-9]{1,3}(?![A-Za-z0-9]))?)(?=[\s_\-.]|$)", os.path.basename(str(nome)))
        if m and re.search(r"\d", m.group(1)):
            out["numero"] = m.group(1).replace("_", "/")
    if not out["data"]:
        m = re.search(r"(20\d{2})[\-_.](\d{2})[\-_.](\d{2})", str(nome))
        if m:
            out["data"] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return out


# ----------------------------------------------------------------------------
# Excel: righe di bolla -> ordini/consegne dei Materiali
# ----------------------------------------------------------------------------
_SINONIMI = {
    "Materiale": ("materiale", "descrizione", "descrizione merce", "articolo", "prodotto", "merce", "voce", "descrizione articolo"),
    "Fornitore": ("fornitore", "ragione sociale", "mittente", "venditore"),
    "Commessa": ("commessa", "cantiere", "destinazione", "cantiere/commessa"),
    "Quantita": ("quantita", "quantità", "qta", "q.tà", "qtà", "q.ta", "qty", "q.ta'"),
    "Um": ("um", "u.m.", "unita", "unità", "unita di misura", "unità di misura"),
    "Prezzo_unit": ("prezzo", "prezzo unitario", "prezzo unit", "prezzo unit.", "importo unitario", "p.u.", "pu", "costo unitario"),
    "Ddt": ("ddt", "n. ddt", "n ddt", "numero ddt", "n°ddt", "n° ddt", "documento", "n. documento", "bolla", "n. bolla", "numero documento", "ddt n.", "ddt numero"),
    "Data_consegna": ("data", "data ddt", "data consegna", "data documento", "data bolla"),
}


def _chiave(t):
    return re.sub(r"\s+", " ", str(t or "").strip().lower())


def _num(v):
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return 0.0 if v != v else float(v)                       # NaN (cella vuota) = 0
    t = str(v).strip().replace("€", "").replace(" ", "")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        x = float(t)
        return 0.0 if x != x else x
    except ValueError:
        return 0.0


def _data(v):
    import datetime as dt
    if isinstance(v, dt.datetime):
        return v.date().isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    from sc import data_da
    d = data_da(v)
    return d.isoformat() if d else ""


def leggi_excel(dati, nome_file=""):
    """Legge un Excel di bolle e lo trasforma in righe per la tabella «Ordini e consegne».
    Restituisce (righe, avvisi, colonne_riconosciute). Solleva DdtErrore se non trova le colonne minime (Materiale e Quantita)."""
    tipo = riconosci(dati)
    if tipo not in ("xlsx", "xls"):
        raise DdtErrore("Non è un file Excel.")
    if tipo == "xlsx" and not _zip_sicuro(dati):
        raise DdtErrore("Il file Excel è troppo grande una volta aperto: non lo leggo.")
    import pandas as pd
    try:
        fogli = pd.read_excel(io.BytesIO(dati), sheet_name=None, header=None, dtype=object, nrows=MAX_RIGHE_EXCEL + 20)
    except Exception as e:
        raise DdtErrore("Non riesco ad aprire il file Excel: potrebbe essere rovinato o protetto da password.") from e
    righe, avvisi, riconosciute = [], [], []
    for nome_f, df in fogli.items():
        if df.empty:
            continue
        mappa, riga_int = {}, None
        for i in range(min(15, len(df))):
            cand = {}
            for j, v in enumerate(df.iloc[i].tolist()):
                k = _chiave(v)
                for campo, syn in _SINONIMI.items():
                    if k in syn and campo not in cand:
                        cand[campo] = j
            if "Materiale" in cand and "Quantita" in cand and len(cand) > len(mappa):
                mappa, riga_int = cand, i
        if not mappa:
            continue
        riconosciute = sorted(set(riconosciute) | set(mappa))
        base = _s(os.path.splitext(os.path.basename(str(nome_file)))[0], 60)
        for i in range(riga_int + 1, min(len(df), riga_int + 1 + MAX_RIGHE_EXCEL)):
            r = df.iloc[i].tolist()
            g = lambda c: r[mappa[c]] if c in mappa and mappa[c] < len(r) else None
            mat, q = _s(g("Materiale")), _num(g("Quantita"))
            if mat.lower() in ("nan", "none"):
                mat = ""
            if not mat and q == 0 and not any(str(x).strip() not in ("", "nan", "None", "NaT") for x in r):
                continue
            if not mat or q <= 0:
                avvisi.append(f"Foglio «{nome_f}», riga {i + 1}: manca il materiale o la quantità, riga ignorata.")
                continue
            dd = _s(g("Ddt"))
            if dd.lower() in ("nan", "none"):
                dd = ""
            if dd.endswith(".0") and dd[:-2].isdigit():
                dd = dd[:-2]
            um = _s(g("Um"))
            righe.append({"Materiale": mat, "Fornitore": "" if _s(g("Fornitore")).lower() in ("nan", "none") else _s(g("Fornitore")),
                          "Commessa": "" if _s(g("Commessa")).lower() in ("nan", "none") else _s(g("Commessa")), "Quantita": q,
                          "Um": "" if um.lower() in ("nan", "none") else um, "Prezzo_unit": _num(g("Prezzo_unit")),
                          "Consegna_prevista": "", "Consegnato": "sì", "Data_consegna": _data(g("Data_consegna")), "Ddt": normalizza_numero(dd) if dd else ""})
    if not riconosciute:
        raise DdtErrore("Non trovo le colonne «Materiale» (o Descrizione) e «Quantità» nelle prime righe. Controlla le intestazioni del file.")
    if len(righe) > MAX_RIGHE_EXCEL:
        righe = righe[:MAX_RIGHE_EXCEL]
        avvisi.append(f"Lette solo le prime {MAX_RIGHE_EXCEL} righe.")
    return righe, avvisi, riconosciute


def righe_nuove(esistenti, nuove):
    """Toglie dalle righe importate quelle gia' presenti (stesso materiale, DDT, quantita' e commessa). Restituisce (da_aggiungere, doppie)."""
    visti = {(_chiave(r.get("Materiale")), _chiave(normalizza_numero(r.get("Ddt"))), round(_num(r.get("Quantita")), 4), _chiave(r.get("Commessa"))) for r in (esistenti or [])}
    out, doppie = [], 0
    for r in nuove:
        k = (_chiave(r["Materiale"]), _chiave(r["Ddt"]), round(_num(r["Quantita"]), 4), _chiave(r["Commessa"]))
        if k in visti:
            doppie += 1
            continue
        visti.add(k)
        out.append(r)
    return out, doppie


def controlli(ordini, path=None):
    """Confronto tra la tabella dei Materiali e i file archiviati.
    Restituisce {'senza_file': [righe consegnate con DDT ma senza file], 'senza_numero': [righe consegnate senza DDT],
                 'file_orfani': [file il cui numero non compare in nessuna riga]}."""
    con_file = numeri_con_file(path)
    nelle_righe = set()
    senza_file, senza_numero = [], []
    for o in ordini or []:
        if str(o.get("Consegnato")) != "sì":
            continue
        n = normalizza_numero(o.get("Ddt"))
        if not n:
            senza_numero.append(o)
        else:
            nelle_righe.add(n)
            if n not in con_file:
                senza_file.append(o)
    orfani = []
    if con_file - nelle_righe:
        with _db(path) as c:
            for n in sorted(con_file - nelle_righe):
                orfani += [_riga(r) for r in c.execute(f"SELECT {_SEL} FROM ddt_file WHERE ddt_numero=? ORDER BY creato", (n,)).fetchall()]
    return {"senza_file": senza_file, "senza_numero": senza_numero, "file_orfani": orfani}
