"""ca_ui.py - Calendario unico delle scadenze (legge i dati dei moduli, dalla sessione o dai salvataggi)."""
import datetime as dt
import io

import pandas as pd
import streamlit as st
import guida

import calendario
import dd
import dd_ui
import riepilogo
import storage
from ui_util import esempi_attivi
import theme
from core import fmt_num

ss = st.session_state
ICONE = {"ok": "🟢", "warn": "🟡", "bad": "🔴"}


def _payloads(includi_demo):
    """Per ogni modulo: dati della sessione (se presenti) oppure ultimo salvataggio. Restituisce (payloads, fonti)."""
    pay, fonti = {}, {}
    for m in calendario.MODULI_CALENDARIO:
        nome = calendario.NOMI_MODULO[m]
        if dd_ui._sessione_disponibile(m):
            if ss.get(f"{m}_demo") and not includi_demo:
                fonti[nome] = "dati di esempio esclusi"
            else:
                pay[m] = dd_ui._payload_sessione(m)
                fonti[nome] = "sessione" + (" (esempio)" if ss.get(f"{m}_demo") else "")
            continue
        try:
            elenco = storage.elenca_pratiche(modulo=m)
            if elenco:
                pay[m] = storage.carica_pratica(elenco[0]["nome"], modulo=m)
                fonti[nome] = f"salvataggio «{elenco[0]['nome']}»"
                continue
        except Exception:
            pass
        fonti[nome] = "nessun dato"
    try:                                                         # compiti nati dalla chat, assegnati alla persona collegata
        import chat
        comp = chat.compiti(ss["utente"]["username"])
        if comp:
            pay["ch"] = {"compiti": comp}
            fonti[calendario.NOMI_MODULO["ch"]] = f"{len(comp)} compiti miei"
    except Exception:
        pass
    return pay, fonti


def render(fcr_uri, audit=None, consentiti=None):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Calendario scadenze", "Fatture, gare, documenti, formazioni e mezzi: tutte le scadenze in un'unica lista, anche sul telefono."), unsafe_allow_html=True)
    guida.mostra("ca")
    a, b, c = st.columns([1, 2, 1])
    ss.setdefault("ca_orizzonte", 30)
    ss.setdefault("ca_demo", esempi_attivi())
    a.number_input("Giorni da mostrare", 7, 365, step=7, key="ca_orizzonte")
    b.multiselect("Tipo di scadenza", calendario.CATEGORIE, key="ca_cat", placeholder="Tutte")
    c.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
    c.checkbox("Includi i dati di esempio", key="ca_demo")
    pay, fonti = _payloads(ss["ca_demo"])
    if consentiti is not None:                                 # chi non vede uno strumento non ne vede nemmeno le scadenze
        pay = {k: v for k, v in pay.items() if k in consentiti}
        ok = {calendario.NOMI_MODULO[m] for m in consentiti if m in calendario.NOMI_MODULO}
        fonti = {k: v for k, v in fonti.items() if k in ok}
    oggi = dt.date.today()
    ev = calendario.eventi(pay, oggi, ss["ca_orizzonte"], ss.get("ca_cat") or None)
    r = calendario.riassunto(ev)
    t1, t2, t3 = st.tabs(["📅 1. Scadenze", "📤 2. Esporta", "✉️ 3. Riepilogo email"])

    with t1:
        st.caption("Dati letti da: " + " · ".join(f"{k}: {v}" for k, v in fonti.items()))
        if not ev:
            st.success("Nessuna scadenza nel periodo scelto." if pay else "Nessun dato: inserisci dati nei moduli (o salvali) per vedere le scadenze.")
        else:
            st.markdown(theme.stat_strip([
                {"label": "Scadute", "value": str(r["scadute"]), "sub": "da gestire subito", "tono": "bad" if r["scadute"] else "ok"},
                {"label": "Entro 7 giorni", "value": str(r["settimana"]), "sub": "questa settimana", "tono": "warn" if r["settimana"] else "ok"},
                {"label": "Entro 30 giorni", "value": str(r["mese"]), "sub": "nel mese", "tono": "info"},
                {"label": "Totale", "value": str(r["totale"]), "sub": f"nei prossimi {ss['ca_orizzonte']} giorni", "tono": "info"}]), unsafe_allow_html=True)
            tab = pd.DataFrame([{"": ICONE[e["Stato"]], "Data": e["Data"].strftime("%d/%m/%Y"), "Quando": ("scaduta da %d gg" % -e["Giorni"]) if e["Giorni"] < 0 else ("oggi" if e["Giorni"] == 0 else f"tra {e['Giorni']} gg"),
                                 "Tipo": e["Categoria"], "Cosa": e["Titolo"], "Importo": e["Importo"], "Dettaglio": e["Dettaglio"], "Modulo": e["Modulo"]} for e in ev])
            st.dataframe(tab, hide_index=True, width="stretch", column_config={"Importo": st.column_config.NumberColumn(format="%.0f €")})

    with t2:
        if not ev:
            st.info("Nessuna scadenza da esportare.")
        else:
            st.write("**Calendario del telefono o del computer.** Scarica il file e aprilo: le scadenze si aggiungono a Google Calendar, Outlook o al calendario dell'iPhone (con promemoria il giorno prima).")
            st.download_button("📥 Scarica il file calendario (.ics)", calendario.genera_ics(ev), file_name="scadenze_FCR.ics", mime="text/calendar", key="dl_ics")
            bio = io.BytesIO()
            pd.DataFrame([{"Data": e["Data"], "Giorni": e["Giorni"], "Tipo": e["Categoria"], "Cosa": e["Titolo"], "Importo": e["Importo"], "Dettaglio": e["Dettaglio"], "Modulo": e["Modulo"]} for e in ev]).to_excel(bio, index=False)
            st.download_button("📥 Scarica l'elenco in Excel", bio.getvalue(), file_name="scadenze_FCR.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_xls")
            st.caption("Il file è una fotografia di oggi: se cambi le date, riscaricalo.")

    with t3:
        st.write("Una mail ogni mattina nei giorni feriali con **cosa fare, scadute, prossimi 7 giorni e semafori**, calcolati sull'ultimo salvataggio di ogni modulo. "
                 "Ecco come sarebbe oggi (anteprima sui dati salvati):")
        pay_s, _ = riepilogo.raccogli()
        if not pay_s:
            st.info("Nessun salvataggio nel database: salva i dati dei moduli (riquadro «Salva e riapri») per ricevere il riepilogo.")
        else:
            ogg, testo, _h, crit = riepilogo.costruisci(pay_s, oggi)
            st.markdown(f"**Oggetto:** {ogg}")
            st.text_area("Testo", testo, height=360, key="ca_anteprima", disabled=True)
        with st.expander("⚙️ Come attivare l'invio automatico"):
            st.markdown("""
1. Crea una **password per le app** dell'account email che invia (per Gmail: Account Google → Sicurezza → Verifica in due passaggi → Password per le app).
2. Su GitHub apri il repository → **Settings → Secrets and variables → Actions → New repository secret** e crea questi 6 segreti
   (mai nel codice): `DATABASE_URL` (la stessa dei Secrets di Streamlit), `SMTP_HOST` (es. `smtp.gmail.com`), `SMTP_PORT` (`587`),
   `SMTP_USER` (l'indirizzo che invia), `SMTP_PASSWORD` (la password per le app), `MAIL_TO` (destinatari separati da virgola).
   **Per Slack** (anche al posto dell'email): in Slack crea un'app con un *Incoming Webhook* per il canale scelto, copia l'indirizzo che inizia con
   `https://hooks.slack.com/` e salvalo come segreto `SLACK_WEBHOOK_URL`. Basta uno dei due canali; se li configuri entrambi il riepilogo arriva su tutti e due.
3. Carica nel repository il file `.github/workflows/riepilogo.yml` (e `riepilogo.py`, `calendario.py`).
4. Vai su **Actions → Riepilogo mattutino → Run workflow** per provarlo subito. Poi parte da solo ogni giorno feriale (06:00 UTC: le 8 in estate, le 7 in inverno).
""")
