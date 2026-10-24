"""miagiornata.py - «La mia giornata»: in cima all'Hub, le poche cose che contano per la persona collegata, scelte in base al suo profilo.

Legge l'ULTIMO salvataggio di ogni strumento (mai i dati dimostrativi) e mostra solo cio' che la persona puo' aprire.
La logica non usa Streamlit, quindi e' testabile; `render` disegna le caselle.
"""
import datetime as dt

import calendario
import dd
import freschezza
import storage

# Aree dei semafori del Cruscotto che interessano a ogni profilo, in ordine di importanza (per il resto: scadenze, compiti, chat, dati fermi)
AREE_PROFILO = {
    "presidente": [],
    "direzione": [],
    "amministrazione": ["Crediti", "Cassa", "Debiti"],
    "commerciale": ["Commerciale", "Commesse"],
    "cantiere": ["Cantieri", "Sicurezza", "Mezzi"],
    "legale": [],
}
TITOLI_PROFILO = {
    "presidente": "Il quadro dell'azienda", "direzione": "Il quadro dell'azienda", "amministrazione": "Cassa, crediti e scadenze",
    "commerciale": "Pratiche e offerte", "cantiere": "Cantieri e sicurezza", "legale": "Termini e contratti"}
ALIAS = {"accesso completo": "presidente"}          # l'amministratore vede il quadro completo
ORDINE_STATO = {"bad": 0, "warn": 1, "ok": 2, "nd": 3}
MAX_CASELLE = 6


def _carica(path=None):
    payloads = {}
    for m in dd.MODULI_METRICHE + ("lg",):
        try:
            elenco = storage.elenca_pratiche(path, modulo=m)
            if elenco:
                payloads[m] = storage.carica_pratica(elenco[0]["nome"], path, m)
        except Exception:
            continue
    return payloads


def _casella(area, ind, valore, stato, nota="", modulo=None):
    return {"Area": area, "Indicatore": ind, "Valore": valore, "Stato": stato, "Nota": nota, "Modulo": modulo}


def _sigla_da_nome(nome):
    return next((k for k, v in calendario.NOMI_MODULO.items() if v == nome), None)


def caselle(utente, profilo, consentiti, payloads=None, ultimi=None, compiti=None, oggi=None, path=None):
    """Elenco ordinato di caselle {Area, Indicatore, Valore, Stato, Nota, Modulo}: le piu' urgenti per questo profilo."""
    oggi = oggi or dt.date.today()
    profilo = ALIAS.get(profilo, profilo)
    consentiti = set(consentiti or [])
    payloads = _carica(path) if payloads is None else payloads
    out = []
    # 1) semafori del Cruscotto
    visibili = {m: p for m, p in payloads.items() if m in consentiti and m in dd.MODULI_METRICHE}
    metriche = {}
    for m in dd.MODULI_METRICHE:
        try:
            metriche[m] = dd.metriche_da_payload(m, visibili.get(m), oggi) if m in visibili else None
        except Exception:
            metriche[m] = None
    righe, gen, _ = dd.semafori(metriche)
    righe = [r for r in righe if r.get("Modulo") in consentiti]
    if "dd" in consentiti and any(metriche.values()):
        n_bad = sum(1 for r in righe if r["Stato"] == "bad")
        n_warn = sum(1 for r in righe if r["Stato"] == "warn")
        out.append(_casella("Cruscotto", "Semafori dell'azienda", f"{n_bad} rossi · {n_warn} gialli", "bad" if n_bad else ("warn" if n_warn else "ok"),
                            "Apri il Cruscotto per i dettagli", "dd"))
    for area in AREE_PROFILO.get(profilo, []):
        cand = [r for r in righe if r["Area"] == area and r["Stato"] != "nd"]
        if cand:
            r = sorted(cand, key=lambda x: ORDINE_STATO[x["Stato"]])[0]
            out.append(_casella(area, r["Indicatore"], r["Valore"], r["Stato"], r["Nota"], r["Modulo"]))
    # 2) scadenze dei prossimi 7 giorni (solo strumenti consentiti)
    pay_cal = {m: p for m, p in payloads.items() if m in consentiti and m in calendario.MODULI_CALENDARIO}
    if compiti:
        pay_cal["ch"] = {"compiti": compiti}
    ev = calendario.eventi(pay_cal, oggi, 7)
    if profilo == "legale":
        ev_leg = [e for e in ev if e["Modulo"] == calendario.NOMI_MODULO["lg"]]
        if "lg" in consentiti and ev_leg:
            sc_ = [e for e in ev_leg if e["Giorni"] < 0]
            out.append(_casella("Studio legale", "Termini e contratti in scadenza", f"{len(ev_leg)} in 7 giorni", "bad" if sc_ else "warn",
                                f"{len(sc_)} già scaduti" if sc_ else ev_leg[0]["Titolo"][:60], "lg"))
    if ev:
        scadute = [e for e in ev if e["Giorni"] < 0]
        out.append(_casella("Scadenze", "Nei prossimi 7 giorni", f"{len(ev)} scadenze", "bad" if scadute else "warn",
                            (f"{len(scadute)} già scadute · " if scadute else "") + f"la prima: {ev[0]['Titolo'][:50]}", "ca" if "ca" in consentiti else None))
    elif {"sc", "ga", "fo", "sx", "mz", "rp", "gt", "lg"} & set(pay_cal):
        out.append(_casella("Scadenze", "Nei prossimi 7 giorni", "nessuna", "ok", "Niente di urgente in calendario", "ca" if "ca" in consentiti else None))
    # 3) compiti miei
    if compiti is not None and "ch" in consentiti:
        scaduti = [t for t in compiti if t.get("scadenza") and t["scadenza"] < oggi.isoformat()]
        if compiti:
            out.append(_casella("Compiti", "Assegnati a me", f"{len(compiti)} aperti", "bad" if scaduti else "warn",
                                (f"{len(scaduti)} in ritardo · " if scaduti else "") + compiti[0]["titolo"][:50], "ch"))
    # 4) dati fermi
    if ultimi is not None:
        fermi = freschezza.fermi(freschezza.valuta(ultimi, moduli=consentiti))
        if fermi:
            f0 = fermi[0]
            out.append(_casella("Dati da aggiornare", f"{len(fermi)} strumenti fermi", f0["nome"], f0["stato"],
                                f"da {f0['giorni']} giorni" + (f" · ultimo: {f0['autore']}" if f0["autore"] else ""), f0["modulo"]))
    out.sort(key=lambda c: ORDINE_STATO[c["Stato"]])
    return out[:MAX_CASELLE]


def calcola(utente, profilo, consentiti, compiti=None, path=None):
    """Come `caselle`, ma legge i dati dal database e ricorda il risultato per poco (la pagina si ridisegna a ogni clic)."""
    chiave = f"giornata_{(utente or {}).get('username', '')}_{profilo}_{len(consentiti or [])}"

    def calcolo():
        try:
            ultimi = storage.ultimi_aggiornamenti(path)
        except Exception:
            ultimi = None
        return caselle(utente, profilo, consentiti, ultimi=ultimi, compiti=compiti, path=path)
    return storage.cache_lettura(chiave, calcolo, path, ttl=30)


def saluto(utente, adesso=None):
    adesso = adesso or dt.datetime.now()
    s = "Buongiorno" if adesso.hour < 13 else ("Buon pomeriggio" if adesso.hour < 18 else "Buonasera")
    return f"{s}, {(utente or {}).get('username', '')}"


def render(vai_a, utente, profilo, consentiti, compiti=None, non_letti=0, audit=None):
    import streamlit as st
    import theme
    ss = st.session_state
    try:
        cas = calcola(utente, profilo, consentiti, compiti)
    except Exception:
        return
    if non_letti:
        cas = [_casella("Chat", "Messaggi da leggere", f"{non_letti} nuovi", "warn", "Apri la chat interna", "ch")] + [c for c in cas if c["Area"] != "Chat"]
    if not cas:
        return
    titolo = TITOLI_PROFILO.get(ALIAS.get(profilo, profilo), "Per te, oggi")
    with st.expander(f"☀️  La mia giornata · {titolo}", expanded=True):
        st.caption(f"{saluto(utente)}. Qui trovi le cose più urgenti per il tuo ruolo; i dati vengono dall'ultimo salvataggio di ogni strumento.")
        for i0 in range(0, len(cas), 3):
            cols = st.columns(3)
            for j, c in enumerate(cas[i0:i0 + 3]):
                i = i0 + j
                with cols[j], st.container(key=f"giorc_{i}"):
                    st.markdown(theme.semaforo_card(c), unsafe_allow_html=True)
                    m = c.get("Modulo")
                    if m and m in set(consentiti or []):
                        if st.button("Apri  →", key=f"giorv_{i}", type="primary" if c["Stato"] in ("bad", "warn") else "secondary", width="stretch"):
                            if audit:
                                audit("giornata_aperta", f"{c['Area']} -> {m}")
                            vai_a(m)
