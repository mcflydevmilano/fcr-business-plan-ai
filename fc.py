"""
fc.py - Flusso commessa (schema FCR rev. 3.8): i 28 passaggi dal primo incontro con l'amministratore alla chiusura della commessa.
Senza Streamlit, quindi testabile. Il «codice madre» e' il codice della pratica nel Registro commerciale (es. 002-MI-MILLELIRE).

Regole dello schema rese operative:
- passaggi con decisione (3 CdA, 8 Presidente, 12 Assemblea, 15 firma contratti): finche' non sono approvati (GO) non si completano i passaggi successivi;
- NO GO al passo 3 o 12: la commessa si ferma; NO GO al passo 8: l'offerta torna al passo 7 per essere rivista;
- ogni passaggio registra iniziali e data di chi lo fa (titolare) e, dove richiesto, di chi approva; per i bonifici (25) anche esecutore, data e identificativo.
"""
import datetime as dt
import re

# (n, titolo, chi, cosa, strumento della suite)
PASSI = [
    (1, "Primo incontro con l'amministratore", "Commerciale", "Opportunità, anagrafica e privacy. DC o DT assegna il codice madre.", "Registro commerciale"),
    (2, "Secondo incontro nell'immobile", "Commerciale + DC", "Verificare la reale capacità economica della proprietà.", "Registro commerciale"),
    (3, "Report al CdA: GO / NO GO", "CdA", "Il CdA decide. NO GO: STOP; GO: ispezione tecnica e valutazione.", "Verbali e riunioni"),
    (4, "Ispezione e fascicolo fotografico", "DT", "Verbale e foto. Ogni immagine con logo FCR e codice madre.", "Archivio documenti"),
    (5, "Preventivazione tecnica", "DT", "Computo, costi, alternative e moduli specifici per gli interventi.", "Computo e Preventivo"),
    (6, "Documenti per la verifica finanziaria preliminare", "DF", "Fattibilità e ipotesi economico-finanziarie per l'offerta.", "Offerta e finanziamenti"),
    (7, "Predisposizione dell'offerta", "DC", "Preventivo, simulazione finanziamento e vantaggio economico/patrimoniale.", "Offerta e finanziamenti"),
    (8, "OK del Presidente: GO / NO GO", "Presidente", "NO GO: DC e DT rivedono l'offerta e la ripresentano al Presidente.", None),
    (9, "Invio offerta approvata via PEC", "DC", "All'amministratore; Commerciale in CC; raccomandazione di non divulgazione.", None),
    (10, "Negoziazione con l'amministratore", "Commerciale + DC", "Esito: GO oppure richiesta di modificare l'offerta.", "Registro commerciale"),
    (11, "Revisione dell'offerta (solo se richiesta)", "DC + DT", "Nuovo OK del Presidente; PEC aggiornata, Commerciale in CC.", "Offerta e finanziamenti"),
    (12, "Assemblea della proprietà", "Commerciale + DC + CdA", "Serve l'approvazione per procedere. DT se serve.", "Verbali e riunioni"),
    (13, "Pratica per il finanziamento", "DF + DC", "Documenti per banca o finanziaria, dopo l'approvazione dell'assemblea.", "Offerta e finanziamenti"),
    (14, "Redazione dei contratti principali", "DC + DLg", "Testo, obblighi, condizioni, scadenze e codice madre.", "Studio legale"),
    (15, "Validazione e firma dei contratti", "DLg + Presidenza", "La Direzione Legale valida prima della firma della Presidenza. Firma tracciata.", "Studio legale"),
    (16, "Incarichi professionali e compensi", "DC + DLg", "Contratti per DL, CSE e Amministratore se RL: funzioni, emolumenti, responsabilità.", "Studio legale"),
    (17, "Progetto e autorizzazioni", "DT", "Progetto definitivo, istanze agli enti, nulla osta e GO per l'avvio.", "Archivio documenti"),
    (18, "Ordini, fornitori e subappalti", "Acquisti + DT", "Ordini, contratti, materiali e servizi sempre con codice madre.", "Ordini e approvazioni"),
    (19, "Personale e manodopera", "Resp. di cantiere", "Assegnazioni, rapportini ore e costi per codice madre.", "Presenze e ore"),
    (20, "Esecuzione dell'intervento", "DT / cantiere", "Avanzamento lavori, verifiche, documenti e oneri di commessa.", "Rapportini di cantiere"),
    (21, "SAL e attestazioni tecniche", "DL", "Il Direttore dei Lavori misura, verifica e valida gli eventuali SAL.", "SAL e contabilità lavori"),
    (22, "Autorizzazioni ai pagamenti", "Amministratore + DL", "Autorizza l'amministratore; in caso di SAL serve anche la validazione del DL.", "Scadenzario"),
    (23, "Fatturazione contrattuale", "Amministrazione", "Fatture secondo contratto, SAL e autorizzazioni.", "Scadenzario"),
    (24, "Rapporti con banca / finanziaria", "Amministrazione", "Richieste, erogazioni e solleciti alle scadenze.", "Offerta e finanziamenti"),
    (25, "Incassi e pagamenti di commessa", "Amministrazione", "Bonifici in entrata e uscita con codice e controlli autorizzativi.", "Riconciliazione bancaria"),
    (26, "Imputazione costi e margini", "Controllo di gestione", "Fatture, ordini, DL/RL, ore e ricavi al centro di profitto.", "Margini per commessa"),
    (27, "Rendicontazione e assicurazioni", "Amministrazione + funzioni", "Quadrature, garanzie e verifiche finali.", None),
    (28, "Chiusura completa della commessa", "Direzione", "Solo dopo ultimo incasso, ultimo pagamento e completa definizione assicurativa.", None),
]
N_PASSI = len(PASSI)
PASSO = {p[0]: {"n": p[0], "titolo": p[1], "chi": p[2], "cosa": p[3], "strumento": p[4]} for p in PASSI}

GATE = (3, 8, 12, 15)                     # finche' non sono approvati, i passaggi successivi non si completano
APPROVAZIONE = (3, 8, 12, 15, 17, 21, 22)  # servono anche iniziali e data di chi approva
NO_GO = (3, 8, 12)                        # passaggi che prevedono l'esito NO GO
FACOLTATIVI = (11,)                       # solo se l'amministratore chiede modifiche
CON_ESECUTORE = (25,)                     # bonifici: esecutore, data e identificativo

STATI = ["Da fare", "In corso", "Fatto", "Approvato", "NO GO", "Non necessario"]
COLONNE = ["Codice", "Passo", "Stato", "Titolare", "Data titolare", "Approvatore", "Data approvazione", "Esecutore", "Data esecuzione", "Riferimento", "Note", "Aggiornato"]
ETICHETTE = {"Codice": "Codice madre", "Passo": "Passo", "Stato": "Stato", "Titolare": "Titolare (iniziali)", "Data titolare": "Data titolare", "Approvatore": "Approvatore (iniziali)",
             "Data approvazione": "Data approvazione", "Esecutore": "Esecutore (iniziali)", "Data esecuzione": "Data esecuzione", "Riferimento": "Contratto / ID operazione", "Note": "Note",
             "Aggiornato": "Ultimo aggiornamento"}
FC_DEFAULT = {"oggi": None, "fermo_gg": 14}
_RE_DATA = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def _s(v):
    return "" if v is None or str(v).strip().lower() in ("nan", "none", "nat") else str(v).strip()


def _data(v):
    t = _s(v)
    m = _RE_DATA.match(t)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", t)
    if m:
        try:
            return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def iniziali(nome):
    """Iniziali di un nome o di un nome utente: «Marco Palombi» -> MP, «m.siciliano» -> MS, «admin» -> AD."""
    parti = [p for p in re.split(r"[\s._\-@]+", _s(nome)) if p]
    if len(parti) >= 2:
        return (parti[0][0] + parti[1][0]).upper()
    return (parti[0][:2] if parti else "").upper()


def _riga_vuota(codice, n):
    r = {c: "" for c in COLONNE}
    r.update({"Codice": codice, "Passo": n, "Stato": "Da fare"})
    return r


def avvia(codice, oggi=None):
    """I 28 passaggi di una nuova commessa. Il primo e' «In corso»."""
    oggi = (oggi or dt.date.today()).isoformat()
    righe = [_riga_vuota(_s(codice), p[0]) for p in PASSI]
    righe[0]["Stato"] = "In corso"
    for r in righe:
        r["Aggiornato"] = oggi
    return righe


def normalizza(righe):
    """Righe pulite con tutte le colonne. Scarta quelle senza codice o con passo non valido. Restituisce (righe, avvisi)."""
    out, avvisi, visti = [], [], set()
    for i, r in enumerate(righe or [], start=1):
        z = {c: _s((r or {}).get(c)) for c in COLONNE}
        if not any(z.values()):
            continue
        try:
            n = int(float(z["Passo"]))
        except ValueError:
            n = 0
        if not z["Codice"] or n not in PASSO:
            avvisi.append(f"Riga {i}: servono codice madre e passo da 1 a {N_PASSI}, riga ignorata.")
            continue
        if (z["Codice"].lower(), n) in visti:
            avvisi.append(f"{z['Codice']}, passo {n}: riga ripetuta, ignorata.")
            continue
        visti.add((z["Codice"].lower(), n))
        z["Passo"] = n
        if z["Stato"] not in STATI:
            z["Stato"] = "Da fare"
        for c in ("Data titolare", "Data approvazione", "Data esecuzione", "Aggiornato"):
            d = _data(z[c])
            z[c] = d.isoformat() if d else ""
        z["Titolare"], z["Approvatore"], z["Esecutore"] = (z[c].upper() for c in ("Titolare", "Approvatore", "Esecutore"))
        out.append(z)
    return out, avvisi


def per_codice(righe):
    """{codice: {passo: riga}} nell'ordine di apparizione."""
    d = {}
    for r in righe:
        d.setdefault(r["Codice"], {})[int(r["Passo"])] = r
    return d


def completo(r):
    """Il passaggio e' concluso: approvato se richiede approvazione, altrimenti fatto; oppure non necessario."""
    if r["Stato"] == "Non necessario":
        return True
    if int(r["Passo"]) in APPROVAZIONE:
        return r["Stato"] == "Approvato"
    return r["Stato"] in ("Fatto", "Approvato")


def blocco(passi, n):
    """Motivo per cui il passaggio n non si puo' ancora completare, oppure ''. `passi` = {n: riga} della commessa."""
    for g in GATE:
        if g < n and g in passi and not completo(passi[g]):
            if passi[g]["Stato"] == "NO GO":
                return f"Passo {g} «{PASSO[g]['titolo']}»: NO GO, la commessa è ferma."
            return f"Passo {g} «{PASSO[g]['titolo']}» non ancora approvato (GO)."
    return ""


def _aggiorna(r, oggi, **k):
    r.update(k)
    r["Aggiornato"] = oggi.isoformat()
    return r


def _avanza(passi, n, oggi):
    """Dopo un passaggio concluso, il successivo (se non facoltativo) passa a «In corso»."""
    m = n + 1
    if m in passi and m not in FACOLTATIVI and passi[m]["Stato"] == "Da fare":
        _aggiorna(passi[m], oggi, Stato="In corso")


def registra(passi, n, azione, chi, oggi=None, riferimento="", note=""):
    """
    Applica un'azione a un passaggio. `passi` = {n: riga} (viene modificato). azione: avvia / fatto / approva / nogo / non_necessario / riapri.
    Restituisce (ok, messaggio). Le iniziali `chi` sono obbligatorie: lo schema vuole la traccia di ogni passaggio.
    """
    oggi = oggi or dt.date.today()
    r = passi.get(n)
    if r is None:
        return False, "Passaggio non trovato."
    chi = _s(chi).upper()
    iso = oggi.isoformat()
    if azione in ("fatto", "approva", "nogo") and not chi:
        return False, "Servono le iniziali di chi registra il passaggio."
    if azione == "avvia":
        _aggiorna(r, oggi, Stato="In corso")
        return True, "Passaggio avviato."
    if azione == "riapri":
        _aggiorna(r, oggi, Stato="In corso", Approvatore="", **{"Data approvazione": ""})
        return True, "Passaggio riaperto."
    if azione == "non_necessario":
        if n not in FACOLTATIVI:
            return False, "Solo i passaggi facoltativi si possono segnare «non necessario»."
        _aggiorna(r, oggi, Stato="Non necessario", Note=note or r["Note"])
        return True, "Passaggio non necessario."
    mot = blocco(passi, n)
    if mot and azione != "nogo":
        return False, mot
    if azione == "fatto":
        if n in GATE and n in APPROVAZIONE and n in NO_GO:
            return False, "Questo passaggio si chiude con la decisione GO / NO GO."
        k = {"Titolare": chi, "Data titolare": iso, "Note": note or r["Note"], "Stato": "Fatto"}
        if riferimento:
            k["Riferimento"] = riferimento
        _aggiorna(r, oggi, **k)
        _avanza(passi, n, oggi)
        return True, "Passaggio registrato" + (": ora serve l'approvazione." if n in APPROVAZIONE else ".")
    if azione == "approva":
        if n not in APPROVAZIONE:
            return False, "Questo passaggio non richiede approvazione."
        if n not in NO_GO and r["Stato"] != "Fatto":
            return False, "Prima va registrato il passaggio, poi si approva."
        k = {"Stato": "Approvato", "Approvatore": chi, "Data approvazione": iso, "Note": note or r["Note"]}
        if not r["Titolare"] and n in NO_GO:
            k.update({"Titolare": chi, "Data titolare": iso})        # decisione presa in riunione: titolare = chi la registra
        if riferimento:
            k["Riferimento"] = riferimento
        _aggiorna(r, oggi, **k)
        _avanza(passi, n, oggi)
        return True, "Approvato (GO)."
    if azione == "nogo":
        if n not in NO_GO:
            return False, "Il NO GO è previsto solo ai passaggi 3, 8 e 12."
        if n == 8:                                   # l'offerta torna a DC e DT
            _aggiorna(r, oggi, Stato="Da fare", Approvatore="", **{"Data approvazione": ""}, Note=(f"NO GO del {iso} ({chi}). " + (note or r["Note"])).strip())
            if 7 in passi:
                _aggiorna(passi[7], oggi, Stato="In corso", Note=(f"Da rivedere dopo NO GO del Presidente ({iso}). " + passi[7]["Note"]).strip())
            return True, "NO GO: l'offerta torna al passo 7 per essere rivista."
        _aggiorna(r, oggi, Stato="NO GO", Approvatore=chi, **{"Data approvazione": iso}, Note=note or r["Note"])
        return True, "NO GO registrato: la commessa è ferma."
    return False, "Azione non riconosciuta."


def stato_commessa(passi, oggi=None, fermo_gg=14):
    """Sintesi di una commessa: avanzamento, passo corrente, stato (Ferma / Chiusa / In attesa di approvazione / Ferma da troppo / In corso)."""
    oggi = oggi or dt.date.today()
    attivi = {n: r for n, r in passi.items() if not (n in FACOLTATIVI and r["Stato"] == "Da fare")}      # un passaggio facoltativo mai aperto non conta
    fatti = sum(1 for r in attivi.values() if completo(r))
    nogo = next((n for n, r in sorted(passi.items()) if r["Stato"] == "NO GO"), None)
    corr = next((n for n in sorted(attivi) if not completo(attivi[n])), None)
    ultimo = max((d for d in (_data(r["Aggiornato"]) for r in passi.values()) if d), default=None)
    giorni = (oggi - ultimo).days if ultimo else None
    if nogo:
        stato = "Ferma (NO GO)"
    elif corr is None:
        stato = "Chiusa"
    elif giorni is not None and giorni > fermo_gg:
        stato = "Ferma da troppo tempo"
    elif passi[corr]["Stato"] == "Fatto" and corr in APPROVAZIONE:
        stato = "In attesa di approvazione"
    else:
        stato = "In corso"
    return {"avanzamento": round(100 * fatti / max(len(attivi), 1)), "fatti": fatti, "totale": len(attivi), "corrente": corr, "stato": stato,
            "titolo_corrente": PASSO[corr]["titolo"] if corr else "", "chi": PASSO[corr]["chi"] if corr else "", "giorni_fermo": giorni, "ultimo": ultimo.isoformat() if ultimo else ""}


def controlli(righe, oggi=None, fermo_gg=14):
    """Anomalie rispetto alle regole trasversali dello schema. [{codice, passo, gravita (bad/warn), messaggio}]"""
    oggi = oggi or dt.date.today()
    out = []

    def add(c, n, g, m):
        out.append({"codice": c, "passo": n, "gravita": g, "messaggio": m})

    for cod, passi in per_codice(righe).items():
        for n, r in sorted(passi.items()):
            t = f"{n} «{PASSO[n]['titolo']}»"
            if r["Stato"] in ("Fatto", "Approvato") and (not r["Titolare"] or not r["Data titolare"]) and not (n in NO_GO and r["Approvatore"]):
                add(cod, n, "warn", f"Passo {t}: mancano iniziali o data del titolare.")
            if n in APPROVAZIONE and r["Stato"] == "Approvato" and (not r["Approvatore"] or not r["Data approvazione"]):
                add(cod, n, "warn", f"Passo {t}: approvato senza iniziali o data dell'approvatore.")
            if n in CON_ESECUTORE and r["Stato"] in ("Fatto", "Approvato") and not (r["Esecutore"] and r["Data esecuzione"] and r["Riferimento"]):
                add(cod, n, "warn", f"Passo {t}: per i bonifici servono esecutore, data e identificativo dell'operazione.")
            if r["Stato"] in ("Fatto", "Approvato"):
                mot = blocco(passi, n)
                if mot:
                    add(cod, n, "bad", f"Passo {t} completato ma {mot[0].lower() + mot[1:]}")
                else:
                    prec = [m for m in range(1, n) if m in passi and m not in FACOLTATIVI and not completo(passi[m]) and passi[m]["Stato"] != "NO GO"]
                    if prec and n not in (18, 19, 20, 24, 26):          # questi passaggi corrono in parallelo agli altri
                        add(cod, n, "warn", f"Passo {t} completato fuori sequenza: il passo {prec[0]} non è concluso.")
            if r["Stato"] == "Fatto" and n in APPROVAZIONE:
                d = _data(r["Data titolare"])
                if d and (oggi - d).days > 7:
                    add(cod, n, "warn", f"Passo {t}: in attesa di approvazione da {(oggi - d).days} giorni.")
        if 28 in passi and passi[28]["Stato"] in ("Fatto", "Approvato"):
            for m in (25, 27):
                if m in passi and not completo(passi[m]):
                    add(cod, 28, "bad", f"Commessa chiusa ma il passo {m} «{PASSO[m]['titolo']}» non è concluso.")
        s = stato_commessa(passi, oggi, fermo_gg)
        if s["stato"] == "Ferma da troppo tempo":
            add(cod, s["corrente"], "warn", f"Nessun aggiornamento da {s['giorni_fermo']} giorni (passo {s['corrente']} «{s['titolo_corrente']}», {s['chi']}).")
    return sorted(out, key=lambda x: (x["gravita"] != "bad", x["codice"], x["passo"]))


def calcola(righe, oggi=None, params=None):
    oggi = oggi or dt.date.today()
    fermo = int((params or {}).get("fermo_gg", FC_DEFAULT["fermo_gg"]))
    comm = []
    for cod, passi in per_codice(righe).items():
        s = stato_commessa(passi, oggi, fermo)
        comm.append({"Codice": cod, "Stato": s["stato"], "Avanzamento": s["avanzamento"], "Passo": s["corrente"] or N_PASSI,
                     "Fase": s["titolo_corrente"] or "Conclusa", "Chi": s["chi"], "Giorni": s["giorni_fermo"]})
    ordine = {"Ferma (NO GO)": 0, "Ferma da troppo tempo": 1, "In attesa di approvazione": 2, "In corso": 3, "Chiusa": 4}
    comm.sort(key=lambda c: (ordine.get(c["Stato"], 9), c["Codice"]))
    kpi = {"commesse": len(comm), "in_corso": sum(c["Stato"] in ("In corso", "In attesa di approvazione", "Ferma da troppo tempo") for c in comm),
           "ferme_nogo": sum(c["Stato"] == "Ferma (NO GO)" for c in comm), "attesa_appr": sum(c["Stato"] == "In attesa di approvazione" for c in comm),
           "ferme": sum(c["Stato"] == "Ferma da troppo tempo" for c in comm), "chiuse": sum(c["Stato"] == "Chiusa" for c in comm)}
    return {"commesse": comm, "kpi": kpi, "controlli": controlli(righe, oggi, fermo)}


def stato_dal_passo(passo):
    """Stato del Registro commerciale corrispondente al passo del flusso (per proporre l'aggiornamento)."""
    if passo <= 1:
        return "S0-Apertura Pratica"
    if passo <= 6:
        return "S1-Sopralluogo"
    if passo <= 13:
        return "S2-Offerta"
    if passo <= 16:
        return "S3-Contratto"
    if passo <= 17:
        return "S4-Progetto"
    return "S5-Esecuzione"


def codici_da_registro(pratiche):
    """Codici delle pratiche attive del Registro commerciale (righe gia' normalizzate)."""
    return [p["Codice"] for p in pratiche if p.get("Codice") and p.get("Archivio", "Attiva") == "Attiva"]


def excel_bytes(righe, commesse):
    import io
    import pandas as pd
    b = io.BytesIO()
    with pd.ExcelWriter(b, engine="openpyxl") as w:
        pd.DataFrame(commesse).to_excel(w, sheet_name="Commesse", index=False)
        rows = [{ETICHETTE[c]: r[c] for c in COLONNE} | {"Descrizione passo": PASSO[int(r["Passo"])]["titolo"]} for r in righe]
        pd.DataFrame(rows).to_excel(w, sheet_name="Passaggi", index=False)
    return b.getvalue()
