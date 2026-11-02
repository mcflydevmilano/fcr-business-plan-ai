"""
fc_sync.py - Collega il Flusso commessa al resto della suite, senza Streamlit (testabile):
  * aggiorna lo stato della pratica nel Registro commerciale;
  * crea e chiude i compiti in «Compiti e attivita'» per il responsabile del passaggio;
  * manda un messaggio in chat all'approvatore quando un passaggio aspetta il suo GO e al responsabile quando una commessa e' ferma.
`sessione` (facoltativa) e' il session_state di Streamlit: se contiene il Registro o i Compiti aperti, vengono aggiornati anche quelli.
"""
import datetime as dt

import fc
import storage

AUTORE = "Flusso commessa"
NOME_COMPITI = "Compiti azienda"
NOME_STATO = "flusso_avvisi_stato"
SCAD_DEFAULT = 7


def ultimo(modulo, path=None):
    """(nome, payload) dell'ultimo salvataggio non dimostrativo del modulo, oppure (None, None)."""
    try:
        elenco = storage.elenca_pratiche(path, modulo=modulo)
        if elenco:
            return elenco[0]["nome"], storage.carica_pratica(elenco[0]["nome"], path, modulo)
    except Exception:
        pass
    return None, None


def _modifica_salvato(modulo, trasforma, autore, path=None, crea_come=None):
    """Carica l'ultimo salvataggio, lo trasforma con `trasforma(payload) -> (payload, esito)` e lo risalva. Riprova se qualcuno l'ha toccato nel frattempo.
    Restituisce (esito, nome, timestamp) oppure (None, None, None) se non c'e' nulla da fare."""
    for _ in range(3):
        nome, payload = ultimo(modulo, path)
        if payload is None:
            if crea_come is None:
                return None, None, None
            nome, payload = crea_come, {}
            atteso = ""
        else:
            meta = storage.meta_pratica(nome, path, modulo)
            atteso = meta["aggiornato"] if meta else ""
        nuovo, esito = trasforma(dict(payload))
        if nuovo is None:
            return esito, nome, None
        try:
            ts = storage.salva_pratica(nome, nuovo, path, autore=autore, modulo=modulo, atteso=atteso)
            return esito, nome, ts
        except storage.ConflittoSalvataggio:
            continue
    return None, None, None


def _aggiorna_base(sessione, modulo, nome, ts):
    base = (sessione or {}).get(f"_base_{modulo}")
    if ts and isinstance(base, dict) and base.get("nome") == nome:
        base["agg"] = ts


def _sostituisci_sessione(sessione, chiave, righe, colonne):
    import pandas as pd
    sessione[chiave] = pd.DataFrame(righe, columns=colonne)
    sessione[chiave + "_v"] = sessione.get(chiave + "_v", 0) + 1


def sincronizza_registro(codice, passi, autore, path=None, sessione=None):
    """Porta la pratica allo stato del flusso. Restituisce (stato precedente, nuovo) oppure None se non cambia nulla."""
    import rc
    risultato = []

    def tr(payload):
        att = next((r for r in payload.get("pratiche") or [] if str(r.get("Codice", "")).strip().lower() == codice.lower() and str(r.get("Archivio") or "Attiva") == "Attiva"), None)
        if att is None:
            return None, None
        nuovo = fc.stato_registro(passi, att.get("Stato") or "")
        if not nuovo:
            return None, None
        payload["pratiche"], prima = fc.aggiorna_stato_registro(payload["pratiche"], codice, nuovo)
        risultato.append((prima, nuovo))
        return payload, (prima, nuovo)

    _esito, nome, ts = _modifica_salvato("rc", tr, autore, path)
    _aggiorna_base(sessione, "rc", nome, ts)
    if sessione is not None and "rc_df" in sessione and len(sessione["rc_df"]):          # il Registro aperto adesso
        righe = sessione["rc_df"].to_dict("records")
        att = next((r for r in righe if str(r.get("Codice", "")).strip().lower() == codice.lower() and str(r.get("Archivio") or "Attiva") == "Attiva"), None)
        nuovo = fc.stato_registro(passi, (att or {}).get("Stato") or "") if att else None
        if nuovo:
            righe, prima = fc.aggiorna_stato_registro(righe, codice, nuovo)
            _sostituisci_sessione(sessione, "rc_df", righe, list(sessione["rc_df"].columns))
            risultato.append((prima, nuovo))
    return risultato[0] if risultato else None


def sincronizza_compiti(codice, passi, mappa, autore, scad_gg=SCAD_DEFAULT, oggi=None, path=None, sessione=None):
    """Crea/chiude i compiti del flusso. Restituisce (creati, chiusi)."""
    import ta
    tot = [0, 0]

    def tr(payload):
        compiti = ta.normalizza(payload.get("compiti"), oggi)[0]
        nuovi, c, ch = fc.compiti_dal_flusso(codice, passi, compiti, mappa, oggi, scad_gg)
        if not (c or ch):
            return None, (0, 0)
        payload["compiti"] = nuovi
        payload.setdefault("params", {"preavviso_gg": ta.TA_DEFAULT["preavviso_gg"]})
        return payload, (c, ch)

    esito, nome, ts = _modifica_salvato("ta", tr, autore, path, crea_come=NOME_COMPITI)
    _aggiorna_base(sessione, "ta", nome, ts)
    if esito:
        tot = [esito[0], esito[1]]
    if sessione is not None and "ta_df" in sessione:                                      # la bacheca aperta adesso
        nuovi, c, ch = fc.compiti_dal_flusso(codice, passi, ta.normalizza(sessione["ta_df"].to_dict("records"), oggi)[0], mappa, oggi, scad_gg)
        if c or ch:
            _sostituisci_sessione(sessione, "ta_df", nuovi, ta.COLONNE)
            tot = [max(tot[0], c), max(tot[1], ch)]
    return tuple(tot)


def dopo_azione(codice, passi, params, autore, path=None, sessione=None, oggi=None):
    """Da chiamare dopo ogni passaggio registrato. `params`: {"responsabili", "scad_gg", "sync_registro", "crea_compiti"}. Restituisce un testo per l'utente (puo' essere vuoto)."""
    params = params or {}
    msg = []
    if params.get("sync_registro", True):
        try:
            r = sincronizza_registro(codice, passi, autore, path, sessione)
            if r:
                msg.append(f"Registro commerciale: {r[0] or '—'} → {r[1]}")
        except Exception as e:
            msg.append(f"Registro non aggiornato ({type(e).__name__})")
    if params.get("crea_compiti", True):
        try:
            c, ch = sincronizza_compiti(codice, passi, params.get("responsabili") or {}, autore, int(params.get("scad_gg") or SCAD_DEFAULT), oggi, path, sessione)
            if c or ch:
                msg.append(f"Compiti: {c} nuovi, {ch} chiusi")
        except Exception as e:
            msg.append(f"Compiti non aggiornati ({type(e).__name__})")
    return " · ".join(msg)


# ----------------------------------------------------------------------------
# Avvisi: all'approvatore e al responsabile di una commessa ferma
# ----------------------------------------------------------------------------
def da_avvisare(righe, mappa, oggi=None, fermo_gg=14):
    """[(utente, chiave, testo)] per le commesse che aspettano un'approvazione o sono ferme da troppo tempo."""
    oggi = oggi or dt.date.today()
    out = []
    for cod, passi in fc.per_codice(righe).items():
        s = fc.stato_commessa(passi, oggi, fermo_gg)
        n = s["corrente"]
        if n is None or s["stato"] == "Ferma (NO GO)":
            continue
        r = passi[n]
        attesa = (r["Stato"] == "Fatto" and n in fc.APPROVAZIONE) or (n in fc.NO_GO and r["Stato"] in ("In corso", "Da fare") and (n == 1 or fc.completo(passi.get(n - 1, r))))
        if attesa and n in fc.APPROVATORE:
            for u in [x.strip() for x in fc.responsabili(fc.APPROVATORE[n], mappa).split(",") if x.strip()]:
                out.append((u, f"appr|{cod}|{n}|{u}", f"Flusso commessa {cod}: il passo {n} «{fc.PASSO[n]['titolo']}» aspetta la tua approvazione (GO / NO GO)."))
        elif s["stato"] == "Ferma da troppo tempo":
            for u in [x.strip() for x in fc.responsabili(fc.PASSO[n]["chi"], mappa).split(",") if x.strip()]:
                out.append((u, f"fermo|{cod}|{n}|{u}", f"Flusso commessa {cod}: ferma da {s['giorni_fermo']} giorni al passo {n} «{fc.PASSO[n]['titolo']}» ({fc.PASSO[n]['chi']}). Serve un aggiornamento."))
    return out


def avvisa(path=None, oggi=None, sincrono=True, dry_run=False, link=None):
    """Manda i messaggi in chat (e l'avviso sul telefono) a chi deve agire, una volta al giorno per lo stesso motivo.
    Restituisce {'chat': n, 'saltati': n, 'errori': [...], 'da_inviare': [...]}."""
    import chat
    import notifiche
    oggi = oggi or dt.date.today()
    esito = {"chat": 0, "saltati": 0, "errori": [], "da_inviare": []}
    _nome, payload = ultimo("fc", path)
    if not payload:
        return esito
    import fc as _fc
    righe = _fc.normalizza(payload.get("passi"))[0]
    par = payload.get("params") or {}
    dovuti = da_avvisare(righe, payload.get("responsabili") or par.get("responsabili") or {}, oggi, int(par.get("fermo_gg") or 14))
    try:
        stato = storage.carica_pratica(NOME_STATO, path, modulo="cfg") or {}
    except Exception:
        stato = {}
    inviati = {k: v for k, v in (stato.get("inviati") or {}).items() if str(v)[:7] == oggi.isoformat()[:7]}
    try:
        noti = {u["username"] for u in storage.elenca_utenti(path)}
    except Exception:
        noti = set()
    link = notifiche.app_url() if link is None else link
    for utente, chiave, testo in dovuti:
        if inviati.get(chiave) == oggi.isoformat():
            esito["saltati"] += 1
            continue
        esito["da_inviare"].append((utente, testo))
        if dry_run:
            continue
        if utente not in noti:
            esito["errori"].append(f"{utente}: non è un utente della suite, avviso non inviato.")
            continue
        try:
            cid = chat.canale_diretto(AUTORE, utente, path)
            info = chat.invia(cid, AUTORE, "utente", testo + (f"\nApri la suite: {link}" if link else ""), path=path)
            notifiche.avvisa(info, AUTORE, "", noti, path, sincrono=sincrono)
            esito["chat"] += 1
            inviati[chiave] = oggi.isoformat()
        except (ValueError, PermissionError) as e:
            esito["errori"].append(f"{utente}: {e}")
    if esito["chat"]:
        storage.salva_pratica(NOME_STATO, {"inviati": inviati}, path, autore=AUTORE, modulo="cfg")
        storage.svuota_cache()
    return esito
