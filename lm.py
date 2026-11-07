"""
lm.py - Lettere e modelli: i documenti che si ripetono, compilati dalla Rubrica (destinatario, cantiere) e scaricabili in Word.
Un modello e' un testo con campi tra doppie graffe, per esempio {{cantiere}}. Senza Streamlit, quindi testabile.
"""
import datetime as dt
import io
import re

import storage

NOME_CFG = "lettere_cfg"
AUTO = {"destinatario": "Destinatario", "referente": "Persona di riferimento", "email_destinatario": "Email del destinatario", "cantiere": "Cantiere", "codice_cantiere": "Codice cantiere",
        "indirizzo_cantiere": "Indirizzo del cantiere", "cliente": "Cliente", "data": "Data", "luogo": "Luogo", "azienda": "Azienda", "firmatario": "Firmatario", "ruolo_firmatario": "Ruolo del firmatario"}
ETICHETTE = {"prestazione": "Prestazione richiesta", "compenso": "Compenso", "scadenza": "Entro il", "oggetto_richiesta": "Cosa si chiede in preventivo", "data_riunione": "Data della riunione",
             "ora": "Ora", "luogo_riunione": "Dove", "ordine_del_giorno": "Ordine del giorno", "riferimento_contratto": "Contratto o ordine di riferimento", "inadempimento": "Inadempimento contestato",
             "giorni": "Giorni di tempo", "data_comunicazione": "Data della comunicazione ricevuta", "argomento": "Argomento", "fattura": "Numero fattura", "data_fattura": "Data fattura", "importo": "Importo",
             "consegna": "Consegna richiesta entro", "note": "Altre indicazioni"}
CAMPI_LUNGHI = {"ordine_del_giorno", "inadempimento", "oggetto_richiesta", "prestazione", "note", "argomento"}
MODELLI_BASE = {
    "incarico": {"titolo": "Lettera di incarico professionale", "oggetto": "Incarico professionale - {{cantiere}}",
                 "corpo": "Spett.le {{destinatario}},\n\ncon la presente Vi conferiamo l'incarico di {{prestazione}} relativo ai lavori di {{cantiere}} presso {{indirizzo_cantiere}}, per conto del committente {{cliente}}.\n\n"
                          "Il compenso concordato è pari a {{compenso}}, oltre IVA e oneri di legge. La prestazione dovrà essere conclusa entro il {{scadenza}}.\n\n"
                          "Vi chiediamo di restituirci copia della presente firmata per accettazione, insieme ai documenti di rito (polizza professionale, DURC o equivalente, dati per la fatturazione).\n\nDistinti saluti."},
    "preventivo": {"titolo": "Richiesta di preventivo", "oggetto": "Richiesta di preventivo - {{cantiere}}",
                   "corpo": "Spett.le {{destinatario}},\n\nper i lavori di {{cantiere}} presso {{indirizzo_cantiere}} Vi chiediamo di formulare un preventivo per:\n\n{{oggetto_richiesta}}\n\n"
                            "Vi preghiamo di inviarci l'offerta entro il {{scadenza}}, con prezzi in euro IVA esclusa, voci distinte per materiali e posa, tempi di consegna ({{consegna}}), validità dell'offerta e condizioni di pagamento.\n\n"
                            "Per chiarimenti potete contattare {{firmatario}}.\n\nCordiali saluti."},
    "convocazione": {"titolo": "Convocazione di riunione", "oggetto": "Convocazione riunione - {{cantiere}} - {{data_riunione}}",
                     "corpo": "Gentile {{destinatario}},\n\nla invitiamo alla riunione che si terrà il {{data_riunione}} alle ore {{ora}} presso {{luogo_riunione}}.\n\nOrdine del giorno:\n{{ordine_del_giorno}}\n\n"
                              "Vi preghiamo di confermare la partecipazione rispondendo a questa comunicazione.\n\nCordiali saluti."},
    "diffida": {"titolo": "Diffida ad adempiere", "oggetto": "Diffida ad adempiere - {{riferimento_contratto}}",
                "corpo": "Spett.le {{destinatario}},\n\nfacciamo riferimento a {{riferimento_contratto}} relativo a {{cantiere}}.\n\nCon la presente contestiamo quanto segue:\n{{inadempimento}}\n\n"
                         "Vi diffidiamo ad adempiere entro {{giorni}} giorni dal ricevimento della presente. Decorso inutilmente tale termine ci riserviamo di considerare risolto il contratto ai sensi dell'art. 1454 del Codice civile e di agire per il risarcimento dei danni.\n\n"
                         "La presente vale come formale messa in mora.\n\nDistinti saluti."},
    "risposta": {"titolo": "Risposta tipo (conferma di ricezione)", "oggetto": "Riscontro alla Vostra comunicazione del {{data_comunicazione}}",
                 "corpo": "Gentile {{destinatario}},\n\nconfermiamo di aver ricevuto la Vostra comunicazione del {{data_comunicazione}} riguardo a {{argomento}}.\n\nLa stiamo esaminando e Vi daremo una risposta entro {{giorni}} giorni.\n\nCordiali saluti."},
    "sollecito_offerta": {"titolo": "Seguito a un'offerta inviata", "oggetto": "Seguito alla nostra offerta del {{data_offerta}} - {{cantiere}}",
                          "corpo": "Gentile {{destinatario}},\n\nLe scriviamo in merito all'offerta che Le abbiamo inviato il {{data_offerta}} per {{cantiere}}.\n\n"
                                   "Vorremmo sapere se ha avuto modo di valutarla e se desidera chiarimenti, una revisione dei punti dell'offerta o un nuovo sopralluogo. Restiamo a disposizione per qualsiasi domanda.\n\nCordiali saluti."},
    "sollecito": {"titolo": "Sollecito di pagamento", "oggetto": "Sollecito di pagamento - fattura {{fattura}}",
                  "corpo": "Spett.le {{destinatario}},\n\nrisulta ancora aperta la fattura n. {{fattura}} del {{data_fattura}} di importo {{importo}}, scaduta il {{scadenza}}.\n\n"
                           "Vi chiediamo di provvedere al pagamento entro {{giorni}} giorni, o di segnalarci eventuali motivi di contestazione. Se avete già pagato, Vi preghiamo di ignorare questa comunicazione e di inviarci la contabile.\n\nCordiali saluti."},
}
AZIENDA_BASE = {"azienda": "FCR General Contractor", "indirizzo": "Via Giovanni Battista Soresina 11, Milano", "luogo": "Milano", "firmatario": "", "ruolo_firmatario": "", "contatti": ""}


def carica_cfg(path=None):
    try:
        raw = storage.carica_pratica(NOME_CFG, path, modulo="cfg")
    except Exception:
        raw = None
    raw = raw if isinstance(raw, dict) else {}
    az = {k: str((raw.get("azienda") or {}).get(k, v) or "").strip()[:200] for k, v in AZIENDA_BASE.items()}
    mod = {}
    for k, v in (raw.get("modelli") or {}).items():
        if isinstance(v, dict) and str(v.get("corpo") or "").strip():
            mod[str(k)] = {"titolo": str(v.get("titolo") or k)[:80], "oggetto": str(v.get("oggetto") or "")[:200], "corpo": str(v["corpo"])[:8000]}
    return {"azienda": az, "modelli": mod}


def salva_cfg(cfg, autore="", path=None):
    storage.salva_pratica(NOME_CFG, cfg, path, autore=autore, modulo="cfg")


def modelli(cfg=None):
    """Tutti i modelli: quelli di base (eventualmente modificati) e quelli creati dall'utente."""
    out = {k: dict(v, base=True, modificato=False) for k, v in MODELLI_BASE.items()}
    for k, v in ((cfg or {}).get("modelli") or {}).items():
        out[k] = dict(v, base=k in MODELLI_BASE, modificato=k in MODELLI_BASE)
    return out


def campi(modello):
    """Campi da compilare a mano (quelli che non arrivano dalla Rubrica): [(chiave, etichetta, tipo)] nell'ordine in cui compaiono."""
    visti, out = set(), []
    for k in re.findall(r"\{\{\s*(\w+)\s*\}\}", modello["oggetto"] + "\n" + modello["corpo"]):
        if k in AUTO or k in visti:
            continue
        visti.add(k)
        tipo = "data" if (k.startswith("data_") or k.startswith("scadenza") or k == "consegna") else ("lungo" if k in CAMPI_LUNGHI else "testo")
        out.append((k, ETICHETTE.get(k, k.replace("_", " ").capitalize()), tipo))
    return out


def _fmt(v):
    if isinstance(v, (dt.date, dt.datetime)):
        return f"{v:%d/%m/%Y}"
    return str(v or "").strip()


def compila(modello, valori):
    """(oggetto, corpo, mancanti): ogni campo vuoto resta visibile come [Etichetta] cosi' non si spedisce una lettera con buchi senza accorgersene."""
    mancanti = []

    def sost(m):
        k = m.group(1)
        v = _fmt(valori.get(k))
        if v:
            return v
        e = AUTO.get(k) or ETICHETTE.get(k, k.replace("_", " ").capitalize())
        if e not in mancanti:
            mancanti.append(e)
        return f"[{e}]"
    rx = re.compile(r"\{\{\s*(\w+)\s*\}\}")
    return rx.sub(sost, modello["oggetto"]), rx.sub(sost, modello["corpo"]), mancanti


def valori_automatici(azienda, contatto=None, cantiere=None, oggi=None):
    """Campi che arrivano da dati gia' presenti: azienda, contatto della Rubrica, cantiere della Rubrica."""
    c, k = contatto or {}, cantiere or {}
    return {"destinatario": c.get("Nome", ""), "referente": c.get("Referente", ""), "email_destinatario": c.get("Email", ""), "cantiere": k.get("Cantiere", ""),
            "codice_cantiere": k.get("Codice", ""), "indirizzo_cantiere": k.get("Indirizzo", ""), "cliente": k.get("Cliente", ""), "data": oggi or dt.date.today(), "luogo": azienda.get("luogo", ""),
            "azienda": azienda.get("azienda", ""), "firmatario": azienda.get("firmatario", ""), "ruolo_firmatario": azienda.get("ruolo_firmatario", "")}


def docx_lettera(azienda, destinatario, oggetto, corpo, luogo_data, firmatario="", ruolo=""):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt
    d = Document()
    d.styles["Normal"].font.name = "Calibri"
    d.styles["Normal"].font.size = Pt(11)
    p = d.add_paragraph()
    r = p.add_run(azienda.get("azienda", ""))
    r.bold, r.font.size = True, Pt(14)
    if azienda.get("indirizzo"):
        d.add_paragraph(azienda["indirizzo"] + (f" · {azienda['contatti']}" if azienda.get("contatti") else ""))
    d.add_paragraph()
    for riga in [x for x in destinatario.splitlines() if x.strip()]:
        q = d.add_paragraph(riga)
        q.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        q.paragraph_format.space_after = Pt(0)
    d.add_paragraph()
    d.add_paragraph(luogo_data)
    o = d.add_paragraph()
    o.add_run("Oggetto: ").bold = True
    o.add_run(oggetto).bold = True
    for blocco in re.split(r"\n\s*\n", corpo):
        if blocco.strip():
            d.add_paragraph(blocco.strip())
    d.add_paragraph()
    d.add_paragraph(azienda.get("azienda", ""))
    if firmatario:
        d.add_paragraph(firmatario + (f"\n{ruolo}" if ruolo else ""))
    b = io.BytesIO()
    d.save(b)
    return b.getvalue()
