"""
pz.py - Prezziario: prezzi di riferimento (es. listino della Camera di Commercio, un quadrimestre alla volta) consultabili per codice,
parola o capitolo, usabili nel Computo e nel controllo degli ordini. Senza Streamlit, quindi testabile.

Un prezziario ha un periodo di validita' (un quadrimestre: 1 gen-30 apr, 1 mag-31 ago, 1 set-31 dic). Quando il periodo e' finito
compare l'avviso «prezzi da aggiornare». I dati stanno nel database (strumento «pz»): un indice leggero con i prezziari caricati e,
per ognuno, le voci compresse (12.000 righe pesano meno di 1 MB).

Regole di lettura del file Excel:
  - le righe senza codice, le intestazioni di capitolo (prezzo 0) e le avvertenze non diventano voci (restano nel conteggio);
  - i caratteri HTML (&apos; &amp;) vengono ripuliti;
  - un codice che compare piu' volte (varianti con prezzi diversi) resta, con chiavi codice, codice#2, codice#3...
"""
import base64
import datetime as dt
import gzip
import html
import io
import json
import re
import unicodedata

import storage
from core import to_float

COLONNE = ["chiave", "codice", "descrizione", "um", "prezzo", "inc_mo", "inc_noli", "inc_sic", "supergruppo", "gruppo", "sottogruppo"]
NOME_INDICE = "indice"
SOGLIA_PREZZO_PCT = 10.0

_ALIAS = {
    "codice": "codice", "cod": "codice", "cod.": "codice", "articolo": "codice", "codice voce": "codice",
    "descrizione ridotta": "desc_ridotta", "descrizione breve": "desc_ridotta",
    "descrizione": "desc_estesa", "descrizione estesa": "desc_estesa", "descrizione completa": "desc_estesa", "descrizione voce": "desc_estesa", "voce": "desc_estesa",
    "unita di misura": "um", "unita' di misura": "um", "um": "um", "u.m.": "um", "unita": "um",
    "prezzo": "prezzo", "prezzo unitario": "prezzo", "importo": "prezzo", "prezzo euro": "prezzo",
    "incidenza manodopera": "inc_mo", "incidenza mano d'opera": "inc_mo", "inc. manodopera": "inc_mo", "% manodopera": "inc_mo", "manodopera": "inc_mo",
    "incidenza noli & trasporti": "inc_noli", "incidenza noli e trasporti": "inc_noli", "incidenza noli": "inc_noli", "noli": "inc_noli",
    "incidenza sicurezza": "inc_sic", "sicurezza": "inc_sic",
    "supergruppo": "supergruppo", "capitolo": "supergruppo", "gruppo": "gruppo", "sottogruppo": "sottogruppo",
}


# ----------------------------------------------------------------------------
# PERIODI
# ----------------------------------------------------------------------------
def periodo(anno, quad):
    return f"{int(quad)}° quadrimestre {int(anno)}"


def date_quadrimestre(anno, quad):
    """(primo giorno, ultimo giorno) del quadrimestre."""
    anno, quad = int(anno), int(quad)
    m1, m2, g2 = {1: (1, 4, 30), 2: (5, 8, 31), 3: (9, 12, 31)}[quad]
    return dt.date(anno, m1, 1), dt.date(anno, m2, g2)


def id_prezziario(anno, quad):
    return f"{int(anno)}-Q{int(quad)}"


# ----------------------------------------------------------------------------
# LETTURA DEL FILE
# ----------------------------------------------------------------------------
def _n(s):
    """Minuscolo, senza accenti, spazi singoli."""
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", s).strip()


def _t(v):
    if v is None or (isinstance(v, float) and v != v):
        return ""
    return re.sub(r"\s+", " ", html.unescape(str(v))).strip()


def da_dataframe(df):
    """Dal file (DataFrame) alle voci. Restituisce (righe, rapporto). Solleva ValueError se mancano colonne indispensabili."""
    mappa = {}
    for col in df.columns:
        k = _ALIAS.get(_n(col).replace("’", "'"))
        if k and k not in mappa.values():
            mappa[col] = k
    inv = {v: c for c, v in mappa.items()}
    descr = inv.get("desc_estesa") or inv.get("desc_ridotta")
    mancanti = [nome for nome, ok in (("Codice", "codice" in inv), ("Descrizione", bool(descr)), ("Prezzo", "prezzo" in inv)) if not ok]
    if mancanti:
        raise ValueError("Nel file mancano le colonne: " + ", ".join(mancanti) + ". Servono almeno Codice, Descrizione e Prezzo (accetto anche «Descrizione ridotta», «Unità di misura», «Supergruppo»…).")
    rap = {"righe_file": len(df), "voci": 0, "senza_codice": 0, "intestazioni": 0, "avvertenze": 0, "prezzi_negativi": 0, "senza_um": 0,
           "codici_ripetuti": 0, "descrizioni_tagliate": 0, "caratteri_puliti": 0, "incidenze_presenti": False, "descrizione_estesa": "desc_estesa" in inv}
    righe, visti = [], {}
    get = lambda r, k: r[inv[k]] if k in inv else ""
    for _, r in df.iterrows():
        cod = _t(get(r, "codice"))
        if not cod:
            rap["senza_codice"] += 1
            continue
        d_raw = str(get(r, "desc_estesa") if "desc_estesa" in inv else get(r, "desc_ridotta") or "")
        d = _t(d_raw)
        if "AVVERTENZE" in cod.upper() or d.upper().startswith("AVVERTENZE"):
            rap["avvertenze"] += 1
            continue
        prezzo = to_float(get(r, "prezzo"), 0.0)
        if prezzo == 0:
            rap["intestazioni"] += 1
            continue
        if re.search(r"&(apos|amp|quot|lt|gt|#\d+);", d_raw + " " + str(get(r, "gruppo")) + " " + str(get(r, "supergruppo"))):
            rap["caratteri_puliti"] += 1
        if " ... " in d:
            rap["descrizioni_tagliate"] += 1
        um = _t(get(r, "um"))
        if um in ("0", "-"):
            um = ""
        if not um:
            rap["senza_um"] += 1
        if prezzo < 0:
            rap["prezzi_negativi"] += 1
        visti[cod] = visti.get(cod, 0) + 1
        if visti[cod] == 2:
            rap["codici_ripetuti"] += 1
        righe.append({"chiave": cod if visti[cod] == 1 else f"{cod}#{visti[cod]}", "codice": cod, "descrizione": d, "um": um, "prezzo": round(prezzo, 4),
                      "inc_mo": to_float(get(r, "inc_mo"), 0.0), "inc_noli": to_float(get(r, "inc_noli"), 0.0), "inc_sic": to_float(get(r, "inc_sic"), 0.0),
                      "supergruppo": _t(get(r, "supergruppo")), "gruppo": _t(get(r, "gruppo")), "sottogruppo": _t(get(r, "sottogruppo"))})
    rap["voci"] = len(righe)
    inc = [x for r in righe for x in (r["inc_mo"], r["inc_noli"]) if x]
    if inc:
        rap["incidenze_presenti"] = True
        if max(inc) <= 1.0:                          # frazioni (0,35) -> percentuali (35)
            for r in righe:
                r["inc_mo"], r["inc_noli"], r["inc_sic"] = r["inc_mo"] * 100, r["inc_noli"] * 100, r["inc_sic"] * 100
    for r in righe:
        for g in ("supergruppo", "gruppo", "sottogruppo"):
            if r[g] in ("<nessuno>", "<none>"):
                r[g] = ""
    return righe, rap


def avvisi_rapporto(rap):
    """Frasi da mostrare dopo la lettura del file."""
    a = []
    if rap.get("descrizioni_tagliate") and not rap.get("descrizione_estesa"):
        a.append(f"{rap['descrizioni_tagliate']} descrizioni sono accorciate con «...»: chiedi all'area tecnica il file con la descrizione completa.")
    if not rap.get("incidenze_presenti"):
        a.append("Le incidenze di manodopera e noli sono vuote o a zero: nel Computo il costo non potrà essere diviso tra manodopera e materiali.")
    if rap.get("senza_um"):
        a.append(f"{rap['senza_um']} voci hanno il prezzo ma non l'unità di misura.")
    if rap.get("codici_ripetuti"):
        a.append(f"{rap['codici_ripetuti']} codici compaiono più volte (varianti con prezzi diversi): le trovi tutte, con chiave codice#2, #3…")
    return a


# ----------------------------------------------------------------------------
# SALVATAGGIO
# ----------------------------------------------------------------------------
def impacchetta(righe):
    return base64.b64encode(gzip.compress(json.dumps(righe, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 6)).decode("ascii")


def spacchetta(testo):
    return json.loads(gzip.decompress(base64.b64decode(testo.encode("ascii"))).decode("utf-8"))


def carica_indice(path=None):
    """{id: meta} dei prezziari caricati."""
    try:
        return dict((storage.carica_pratica(NOME_INDICE, path, modulo="pz") or {}).get("prezziari", {}))
    except Exception:
        return {}


def salva_prezziario(meta, righe, autore="", path=None):
    """Salva (o sostituisce) il prezziario del periodo indicato in `meta` (anno, quad, nome, fonte, ...). Restituisce la meta completa."""
    anno, quad = int(meta["anno"]), int(meta["quad"])
    pid = id_prezziario(anno, quad)
    da, a = date_quadrimestre(anno, quad)
    meta = {**meta, "id": pid, "anno": anno, "quad": quad, "periodo": periodo(anno, quad), "valido_da": meta.get("valido_da") or da.isoformat(),
            "valido_a": meta.get("valido_a") or a.isoformat(), "n_voci": len(righe), "caricato": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "autore": autore}
    storage.salva_pratica("dati_" + pid, {"righe_gz": impacchetta(righe)}, path, autore=autore, modulo="pz")
    for _ in range(5):
        try:
            m = storage.meta_pratica(NOME_INDICE, path, modulo="pz")
            ind = (storage.carica_pratica(NOME_INDICE, path, modulo="pz") or {}) if m else {}
            prez = dict(ind.get("prezziari") or {})
            prez[pid] = meta
            storage.salva_pratica(NOME_INDICE, {"prezziari": prez}, path, autore=autore, modulo="pz", atteso=m["aggiornato"] if m else "")
            return meta
        except storage.ConflittoSalvataggio:
            continue
    raise RuntimeError("Salvataggio dell'indice non riuscito: riprova.")


def aggiornato_il(pid, path=None):
    m = storage.meta_pratica("dati_" + pid, path, modulo="pz")
    return m["aggiornato"] if m else ""


def carica_righe(pid, path=None):
    p = storage.carica_pratica("dati_" + pid, path, modulo="pz")
    return spacchetta(p["righe_gz"]) if p and p.get("righe_gz") else []


def elimina_prezziario(pid, autore="", path=None):
    storage.elimina_pratica("dati_" + pid, path, modulo="pz")
    for _ in range(5):
        try:
            m = storage.meta_pratica(NOME_INDICE, path, modulo="pz")
            if not m:
                return
            prez = dict((storage.carica_pratica(NOME_INDICE, path, modulo="pz") or {}).get("prezziari") or {})
            prez.pop(pid, None)
            storage.salva_pratica(NOME_INDICE, {"prezziari": prez}, path, autore=autore, modulo="pz", atteso=m["aggiornato"])
            return
        except storage.ConflittoSalvataggio:
            continue


def corrente(indice, oggi=None):
    """Il prezziario da usare: quello in vigore oggi, altrimenti il piu' recente. None se non ce ne sono."""
    oggi = oggi or dt.date.today()
    if not indice:
        return None
    ordinati = sorted(indice.values(), key=lambda m: (m["anno"], m["quad"]), reverse=True)
    for m in ordinati:
        if m["valido_da"] <= oggi.isoformat() <= m["valido_a"]:
            return m
    return ordinati[0]


def stato_validita(indice, oggi=None):
    """Riga per l'elenco «dati aggiornati?» dell'Hub: scaduto quando il quadrimestre e' finito; rosso dopo piu' di un quadrimestre di ritardo."""
    oggi = oggi or dt.date.today()
    m = corrente(indice, oggi)
    if not m:
        return {"modulo": "pz", "nome": "Prezziario", "giorni": None, "stato": "nd", "autore": "", "soglia": 0, "testo": "nessun prezziario caricato"}
    fine = dt.date.fromisoformat(m["valido_a"])
    if oggi <= fine:
        return {"modulo": "pz", "nome": "Prezziario", "giorni": 0, "stato": "ok", "autore": m.get("autore", ""), "soglia": 0,
                "testo": f"{m['periodo']}: in vigore fino al {fine.strftime('%d/%m/%Y')}"}
    g = (oggi - fine).days
    return {"modulo": "pz", "nome": "Prezziario", "giorni": g, "stato": "warn" if g <= 120 else "bad", "autore": m.get("autore", ""), "soglia": 0,
            "testo": f"{m['periodo']}: scaduto il {fine.strftime('%d/%m/%Y')} ({g} giorni fa), prezzi da aggiornare"}


# ----------------------------------------------------------------------------
# RICERCA
# ----------------------------------------------------------------------------
def prepara(righe):
    """DataFrame con la colonna di ricerca (codice + descrizione + capitolo, senza accenti)."""
    import pandas as pd
    df = pd.DataFrame(righe, columns=COLONNE)
    df["ric"] = (df["codice"] + " " + df["descrizione"] + " " + df["gruppo"] + " " + df["supergruppo"]).map(_n)
    df["cod_n"] = df["codice"].str.lower()
    return df


def capitoli(df):
    """Elenco dei supergruppi e, per ognuno, dei gruppi."""
    out = {}
    for sg, g in df[["supergruppo", "gruppo"]].drop_duplicates().itertuples(index=False):
        out.setdefault(sg or "(senza capitolo)", [])
        if g:
            out[sg or "(senza capitolo)"].append(g)
    return {k: sorted(set(v)) for k, v in sorted(out.items())}


def cerca(df, testo="", supergruppo="", gruppo="", um="", limite=500):
    """Voci che contengono TUTTE le parole cercate (nel codice, nella descrizione o nel capitolo). Un testo che somiglia a un codice cerca per inizio codice."""
    r = df
    if supergruppo:
        r = r[r["supergruppo"].replace("", "(senza capitolo)") == supergruppo]
    if gruppo:
        r = r[r["gruppo"] == gruppo]
    if um:
        r = r[r["um"] == um]
    q = _n(testo)
    if q:
        if re.match(r"^[a-z]\.?\d", q) and " " not in q:
            r = r[r["cod_n"].str.startswith(q)]
        else:
            for tok in q.split():
                r = r[r["ric"].str.contains(re.escape(tok), regex=True)]
    return r.head(limite)


def indice_prezzi(righe):
    """{codice: {min, max, um, descrizione}} per il controllo degli ordini (le varianti dello stesso codice formano un intervallo)."""
    out = {}
    for r in righe:
        c = r["codice"]
        e = out.get(c)
        if e is None:
            out[c] = {"min": r["prezzo"], "max": r["prezzo"], "um": r["um"], "descrizione": r["descrizione"]}
        else:
            e["min"], e["max"] = min(e["min"], r["prezzo"]), max(e["max"], r["prezzo"])
    return out


# ----------------------------------------------------------------------------
# USO NEL PREVENTIVO E NEGLI ORDINI
# ----------------------------------------------------------------------------
def costo_da_prezzo(prezzo, sg_pct, utile_pct):
    """Il prezzo di un prezziario comprende spese generali e utile: il costo diretto e' quello che resta senza."""
    return round(prezzo / ((1 + sg_pct / 100.0) * (1 + utile_pct / 100.0)), 4)


def voce_per_computo(r, quantita, come="prezzo", sg_pct=15.0, utile_pct=10.0):
    """Riga per la tabella del Computo. come: «prezzo» (il prezzo comprende spese generali e utile: ne ricavo il costo) oppure «costo» (e' gia' un costo diretto)."""
    costo = costo_da_prezzo(r["prezzo"], sg_pct, utile_pct) if come == "prezzo" else float(r["prezzo"])
    mo, nl = max(0.0, r.get("inc_mo") or 0.0) / 100.0, max(0.0, r.get("inc_noli") or 0.0) / 100.0
    if mo + nl > 1.0:
        mo = nl = 0.0
    return {"Codice": r["codice"], "Categoria": (r.get("supergruppo") or "Varie")[:60], "Descrizione": r["descrizione"], "UM": r["um"] or "cad", "Quantita": float(quantita),
            "Materiali": round(costo * (1 - mo - nl), 4), "Manodopera": round(costo * mo, 4), "Noli_altro": round(costo * nl, 4)}


def controllo_prezzo(ordine, prezzi, soglia_pct=SOGLIA_PREZZO_PCT):
    """Confronta il prezzo unitario di un ordine (importo / quantita') con il prezziario. Restituisce una frase se c'e' qualcosa da segnalare, altrimenti None.
    Servono la voce (codice) e la quantita' nell'ordine; senza, il controllo non scatta."""
    cod = str(ordine.get("Voce") or "").strip()
    if not cod or not prezzi:
        return None
    qta = to_float(ordine.get("Quantita"), 0.0)
    e = prezzi.get(cod)
    if e is None:
        return f"la voce {cod} non è nel prezziario"
    if qta <= 0:
        return None
    unit = to_float(ordine.get("Importo"), 0.0) / qta
    if unit > e["max"] * (1 + soglia_pct / 100.0):
        sopra = (unit / e["max"] - 1) * 100
        rif = f"{e['max']:.2f}" if e["min"] == e["max"] else f"{e['min']:.2f}-{e['max']:.2f}"
        return f"prezzo unitario {unit:.2f} € sopra il prezziario ({rif} €/{e['um'] or 'UM'}) del {sopra:.0f}%"
    return None


# ----------------------------------------------------------------------------
# CONFRONTO TRA QUADRIMESTRI
# ----------------------------------------------------------------------------
def confronta(vecchie, nuove):
    """Cosa cambia tra due prezziari: voci variate (con %), nuove ed eliminate."""
    v = {r["chiave"]: r for r in vecchie}
    n = {r["chiave"]: r for r in nuove}
    variate, uguali, cambio_um = [], 0, 0
    for k, r in n.items():
        o = v.get(k)
        if o is None:
            continue
        if o["um"] != r["um"]:
            cambio_um += 1
        if abs(o["prezzo"] - r["prezzo"]) < 0.005:
            uguali += 1
            continue
        pct = (r["prezzo"] / o["prezzo"] - 1) * 100 if o["prezzo"] else 0.0
        variate.append({"chiave": k, "codice": r["codice"], "descrizione": r["descrizione"], "um": r["um"], "prezzo_prima": o["prezzo"], "prezzo_ora": r["prezzo"], "variazione_pct": round(pct, 2),
                        "supergruppo": r["supergruppo"]})
    variate.sort(key=lambda x: -abs(x["variazione_pct"]))
    pcts = [x["variazione_pct"] for x in variate]
    per_cap = {}
    for x in variate:
        per_cap.setdefault(x["supergruppo"] or "(senza capitolo)", []).append(x["variazione_pct"])
    return {"variate": variate, "nuove": [r for k, r in n.items() if k not in v], "eliminate": [r for k, r in v.items() if k not in n], "invariate": uguali, "cambio_um": cambio_um,
            "aumenti": sum(1 for p in pcts if p > 0), "riduzioni": sum(1 for p in pcts if p < 0), "media_pct": round(sum(pcts) / len(pcts), 2) if pcts else 0.0,
            "per_capitolo": sorted(({"capitolo": c, "voci": len(p), "media_pct": round(sum(p) / len(p), 2)} for c, p in per_cap.items()), key=lambda x: -abs(x["media_pct"]))}


def excel_bytes(df, nome_foglio="Prezziario"):
    """Esporta in Excel le colonne utili di un risultato di ricerca."""
    import pandas as pd
    col = [c for c in ("codice", "descrizione", "um", "prezzo", "supergruppo", "gruppo", "sottogruppo") if c in df.columns]
    nomi = {"codice": "Codice", "descrizione": "Descrizione", "um": "UM", "prezzo": "Prezzo €", "supergruppo": "Capitolo", "gruppo": "Gruppo", "sottogruppo": "Sottogruppo"}
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df[col].rename(columns=nomi).to_excel(w, index=False, sheet_name=nome_foglio[:30])
        ws = w.sheets[nome_foglio[:30]]
        for letter, larg in zip("ABCDEFG", (18, 90, 8, 12, 40, 30, 20)):
            ws.column_dimensions[letter].width = larg
    return buf.getvalue()
