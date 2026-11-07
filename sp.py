"""sp.py - Sopralluogo da telefono: raccolta guidata dei dati sul posto e passaggio al preventivo fotovoltaico."""
import datetime as dt
import io
import uuid

import storage

NOME_CFG = "sopralluoghi"
MAX_FOTO = 8
M2_PER_MODULO = 2.0           # un modulo da ~430 Wp occupa circa 2 m2
UTILIZZABILE = {"Falda 30°": 0.6, "Falda 15-20°": 0.6, "Falda 40-45°": 0.6, "Tetto piano": 0.45}

TIPI_TETTO = ["Falda 30°", "Falda 15-20°", "Falda 40-45°", "Tetto piano"]
ORIENTAMENTI = ["Sud", "Sud-Est / Sud-Ovest", "Est / Ovest", "Nord"]
COPERTURE = ["Tegole / coppi", "Lamiera / pannello sandwich", "Guaina (piano)", "Eternit / amianto", "Altro"]
OMBRE = {"Nessuna": 0, "Poca (camini, antenne)": 5, "Media (alberi o palazzi vicini)": 15, "Molta": 30}
ZONE = ["Nord", "Centro", "Sud"]

CHECK = [("foto_tetto", "Foto del tetto intero"), ("foto_quadro", "Foto del quadro elettrico"), ("foto_contatore", "Foto del contatore"),
         ("foto_inverter", "Posto dove mettere l'inverter")]


def nuovo():
    return {"id": uuid.uuid4().hex[:8], "data": dt.date.today().isoformat(), "cliente": "", "indirizzo": "", "tipo": "Fotovoltaico",
            "tetto": "Falda 30°", "orientamento": "Sud", "superficie_m2": 0.0, "ombre": "Nessuna", "copertura": COPERTURE[0], "zona": "Nord",
            "potenza_kw": 3.0, "distanza_m": 10.0, "consumo_kwh": 3000.0, "accumulo": False, "note": "", "foto": [], "autore": ""}


def stima_moduli(superficie_m2, tetto="Falda 30°"):
    try:
        s = float(superficie_m2)
    except (TypeError, ValueError):
        return 0
    return max(0, int(s * UTILIZZABILE.get(tetto, 0.55) / M2_PER_MODULO))


def kwp(n_moduli, wp=430):
    return round(n_moduli * wp / 1000, 2)


def controlli(r):
    """Cose da sapere prima di fare il preventivo."""
    out = []
    n = stima_moduli(r.get("superficie_m2"), r.get("tetto"))
    k = kwp(n)
    if "amianto" in str(r.get("copertura", "")).lower() or "eternit" in str(r.get("copertura", "")).lower():
        out.append("Copertura in eternit/amianto: prima va bonificata, serve un preventivo a parte.")
    if r.get("orientamento") == "Nord":
        out.append("Tetto esposto a nord: la produzione sarà molto bassa, valuta un'altra superficie.")
    if n == 0:
        out.append("Manca la superficie utile: senza non so quanti moduli ci stanno.")
    try:
        if float(r.get("potenza_kw") or 0) and k > float(r["potenza_kw"]) * 1.1 and n:
            out.append(f"L'impianto stimato ({k} kWp) supera la potenza impegnata ({r['potenza_kw']} kW): serve chiedere l'aumento al distributore.")
    except (TypeError, ValueError):
        pass
    try:
        if float(r.get("distanza_m") or 0) > 30:
            out.append("Il quadro è lontano dall'inverter (oltre 30 m): prevedi cavi più lunghi nel preventivo.")
    except (TypeError, ValueError):
        pass
    if len(r.get("foto") or []) == 0:
        out.append("Nessuna foto: scatta almeno il tetto e il quadro elettrico.")
    return out


def parametri_fv(r):
    """Quello che si porta nel Preventivo fotovoltaico: chiavi con prefisso fv_ pronte per ss['_pending']."""
    n = stima_moduli(r.get("superficie_m2"), r.get("tetto"))
    p = {"fv_orientamento": r.get("orientamento", "Sud"), "fv_inclinazione": r.get("tetto", "Falda 30°"), "fv_ombra_pct": float(OMBRE.get(r.get("ombre"), 0)),
         "fv_zona": r.get("zona", "Nord"), "fv_consumo": float(r.get("consumo_kwh") or 0), "fv_accumulo_kwh": 5.0 if r.get("accumulo") else 0.0,
         "fv_cliente": r.get("cliente", ""), "fv_indirizzo": r.get("indirizzo", ""),
         "fv_note": ("Sopralluogo del %s. Copertura: %s. " % (r.get("data", ""), r.get("copertura", "")) + (r.get("note") or "")).strip()}
    if n:
        p["fv_n_moduli"] = n
    return p


def testo(r):
    n = stima_moduli(r.get("superficie_m2"), r.get("tetto"))
    righe = [f"SOPRALLUOGO del {r.get('data', '')}", f"Cliente: {r.get('cliente', '')}", f"Indirizzo: {r.get('indirizzo', '')}", "",
             f"Tetto: {r.get('tetto')} · {r.get('orientamento')} · superficie utile {r.get('superficie_m2')} m²", f"Copertura: {r.get('copertura')}",
             f"Ombre: {r.get('ombre')}", f"Potenza impegnata: {r.get('potenza_kw')} kW · distanza quadro-inverter: {r.get('distanza_m')} m",
             f"Consumo annuo: {r.get('consumo_kwh')} kWh · accumulo: {'sì' if r.get('accumulo') else 'no'}",
             f"Stima: {n} moduli ≈ {kwp(n)} kWp", f"Foto scattate: {len(r.get('foto') or [])}", ""]
    c = controlli(r)
    if c:
        righe += ["DA SAPERE:"] + ["- " + x for x in c] + [""]
    if r.get("note"):
        righe += ["Note:", r["note"]]
    return "\n".join(righe)


def docx_bytes(r):
    from docx import Document
    from docx.shared import Inches
    import base64
    d = Document()
    d.add_heading(f"Sopralluogo · {r.get('cliente') or 'senza nome'}", 1)
    for riga in testo(r).split("\n"):
        d.add_paragraph(riga)
    for f in (r.get("foto") or [])[:MAX_FOTO]:
        try:
            if str(f.get("tipo", "")).startswith("image/"):
                d.add_picture(io.BytesIO(base64.b64decode(f["dati"])), width=Inches(3))
        except Exception:
            continue
    b = io.BytesIO()
    d.save(b)
    return b.getvalue()


def carica(path=None):
    try:
        raw = storage.carica_pratica(NOME_CFG, path, modulo="cfg")
    except Exception:
        raw = None
    el = raw.get("elenco") if isinstance(raw, dict) else None
    return [x for x in (el or []) if isinstance(x, dict) and x.get("id")]


def salva(elenco, autore="", path=None):
    storage.salva_pratica(NOME_CFG, {"elenco": elenco}, path, autore=autore, modulo="cfg")
    storage.svuota_cache()


def aggiungi(r, autore="", path=None):
    el = [x for x in carica(path) if x["id"] != r["id"]]
    r = dict(r, autore=autore or r.get("autore", ""))
    salva([r] + el, autore, path)
