"""ru_ui.py - Interfaccia di Rubrica e cantieri."""
import datetime as dt

import pandas as pd
import streamlit as st

import fo
import guida
import ops_report
import ru
import sc
import theme
from core import fmt_num
from ui_util import banner_esempio, blocco_tabella, pannello_archivio, scarica_dossier, sola_lettura, sostituisci_tabella

ss = st.session_state


def _esempio():
    mk = lambda cols, rows: pd.DataFrame([dict(zip(cols, r)) for r in rows], columns=cols)
    anno = dt.date.today().year
    cont = [("Calcestruzzi Alfa", "Fornitore", "Marco Bianchi", "02 5551234", "ordini@calcestruzzialfa.example", "Consegne dal lunedì al sabato"),
            ("Elettroimpianti Beta", "Subappaltatore", "Luca Verdi", "333 1234567", "info@elettroimpiantibeta.example", ""),
            ("Ponteggi Gamma", "Subappaltatore", "Anna Neri", "347 7654321", "amministrazione@ponteggigamma.example", "Noleggio a settimana"),
            ("Comune di Esempio", "Cliente", "Ufficio tecnico", "02 5550000", "utc@comune.example", ""),
            ("Studio Legale Rossi", "Studio legale", "Avv. Rossi", "02 5559999", "studio@legalerossi.example", "Interno al gruppo")]
    can = [(f"CAN-{anno}-001", "Villa Lago", "Famiglia Lago", "Via dei Tigli 12, Como", "Ing. Di Ferdinando", "In corso", "monday-1001"),
           (f"CAN-{anno}-002", "Scuola Elementare", "Comune di Esempio", "Via Roma 1, Milano", "Geom. Colombo", "In corso", "monday-1002")]
    return mk(ru.COLONNE_CONTATTI, cont), mk(ru.COLONNE_CANTIERI, can)


def _cfg():
    t = st.column_config.TextColumn
    a, b = ru.ETICHETTE_CONTATTI, ru.ETICHETTE_CANTIERI
    return ({"Nome": t(a["Nome"], width="medium"), "Ruolo": st.column_config.SelectboxColumn(a["Ruolo"], options=ru.RUOLI), "Referente": t(a["Referente"]), "Telefono": t(a["Telefono"]),
             "Email": t(a["Email"], width="medium"), "Note": t(a["Note"], width="medium")},
            {"Codice": t(b["Codice"], help="Lascialo vuoto: lo assegna l'app (CAN-anno-progressivo)."), "Cantiere": t(b["Cantiere"], width="medium"), "Cliente": t(b["Cliente"]),
             "Indirizzo": t(b["Indirizzo"], width="medium"), "Responsabile": t(b["Responsabile"]), "Stato": st.column_config.SelectboxColumn(b["Stato"], options=ru.STATI_CANTIERE),
             "Esterno": t(b["Esterno"], help="Il codice con cui lo stesso cantiere è registrato in un altro sistema (es. la riga di monday).")})


def _raccogli():
    return {"contatti": ss["ru_cont"].to_dict("records"), "cantieri": ss["ru_can"].to_dict("records")}


def _applica(p, nome):
    sostituisci_tabella("ru_cont", pd.DataFrame(p.get("contatti") or [], columns=ru.COLONNE_CONTATTI))
    sostituisci_tabella("ru_can", pd.DataFrame(p.get("cantieri") or [], columns=ru.COLONNE_CANTIERI))
    ss["ru_demo"] = False


def _fonti():
    """Documenti dei fornitori e fatture, dalla sessione o dall'ultimo salvataggio (stessa logica del Calendario)."""
    try:
        import ca_ui
        pay, _ = ca_ui._payloads(True)
    except Exception:
        pay = {}
    docs = fo.normalizza_docfo((pay.get("fo") or {}).get("docs"))[0] if pay.get("fo") else []
    fat = sc.normalizza_documenti((pay.get("sc") or {}).get("docs"))[0] if pay.get("sc") else []
    return docs, fat


def _bottoni(c, oggetto=""):
    """Chiama / scrivi / WhatsApp per un contatto, come collegamenti."""
    out = []
    if ru.link_chiama(c["Telefono"]):
        out.append(f"[📞 Chiama]({ru.link_chiama(c['Telefono'])})")
    if ru.link_email(c["Email"]):
        out.append(f"[✉️ Scrivi]({ru.link_email(c['Email'], oggetto)})")
    if ru.link_whatsapp(c["Telefono"]):
        out.append(f"[💬 WhatsApp]({ru.link_whatsapp(c['Telefono'])})")
    return "  ·  ".join(out) or "_nessun recapito_"


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Rubrica e cantieri", "Tutti i contatti in un posto solo e ogni cantiere con il suo codice unico."), unsafe_allow_html=True)
    guida.mostra("ru")
    if "ru_cont" not in ss:
        ss["ru_cont"], ss["ru_can"] = _esempio()
        ss["ru_demo"] = True
    pannello_archivio("ru", "la rubrica", _raccogli, _applica, audit, utente)
    t1, t2, t3, t4 = st.tabs(["🧾 1. Contatti e cantieri", "📇 2. Scheda contatto", "🔗 3. Codici cantiere", "📄 4. Dossier"])
    cc, ccan = _cfg()
    with t1:
        banner_esempio("ru_demo", [("ru_cont", ru.COLONNE_CONTATTI), ("ru_can", ru.COLONNE_CANTIERI)], "svuota_ru")
        blocco_tabella("ru_cont", "Contatti", "Fornitori, clienti, professionisti, enti. Una riga per azienda, con la persona di riferimento.", ru.COLONNE_CONTATTI, ru.ETICHETTE_CONTATTI, cc,
                       ss["ru_cont"], "ru", 1, audit, 260, ru.SINONIMI_CONTATTI)
        blocco_tabella("ru_can", "Cantieri", "Lascia vuoto il codice: lo assegna l'app. Poi usa lo stesso codice nelle altre tabelle.", ru.COLONNE_CANTIERI, ru.ETICHETTE_CANTIERI, ccan, ss["ru_can"], "ru", 2, audit, 200)
        if st.button("🔢 Assegna i codici mancanti", key="ru_codici", disabled=sola_lettura()):
            nuovi, _ = ru.normalizza_cantieri(ss["ru_can"].to_dict("records"))
            sostituisci_tabella("ru_can", pd.DataFrame(nuovi, columns=ru.COLONNE_CANTIERI))
            audit("ru_codici_assegnati", f"{len(nuovi)} cantieri")
            st.rerun()
    contatti, a1 = ru.normalizza_contatti(ss["ru_cont"].to_dict("records"))
    cantieri, a2 = ru.normalizza_cantieri(ss["ru_can"].to_dict("records"))
    out = ru.calcola_ru(contatti, cantieri)
    k = out["kpi"]
    docs, fat = _fonti()

    with t2:
        if not contatti:
            st.warning("La rubrica è vuota: inserisci almeno un contatto nella scheda 1.")
        else:
            for x in (a1 + out["avvisi"])[:4]:
                st.caption("⚠️ " + x)
            cerca = st.text_input("Cerca (nome, persona, ruolo)", key="ru_cerca", placeholder="es. calcestruzzi, subappaltatore…")
            ok = [c for c in contatti if not cerca or cerca.lower() in " ".join(c.values()).lower()]
            if not ok:
                st.info("Nessun contatto trovato.")
            else:
                nome = st.selectbox("Contatto", [c["Nome"] for c in ok], key="ru_sel")
                c = next(x for x in ok if x["Nome"] == nome)
                col = ru.collegamenti(c, docs, fat, cantieri)
                st.markdown(f"### {c['Nome']}")
                st.caption(f"{c['Ruolo']}" + (f" · referente {c['Referente']}" if c["Referente"] else ""))
                st.markdown(_bottoni(c, "FCR General Contractor"))
                if c["Note"]:
                    st.info(c["Note"])
                x1, x2, x3 = st.columns(3)
                x1.metric("Documenti registrati", len(col["documenti"]), f"{sum(1 for d in col['documenti'] if d['Scadenza'] and d['Scadenza'] < dt.date.today().isoformat())} scaduti" if col["documenti"] else None, delta_color="inverse")
                x2.metric("Fatture", len(col["fatture"]), f"da regolare {fmt_num(col['aperto'])} €" if col["aperto"] else None, delta_color="off")
                x3.metric("Cantieri collegati", len(col["cantieri"]))
                if col["documenti"]:
                    st.markdown("**Documenti**")
                    st.dataframe(pd.DataFrame(col["documenti"]), hide_index=True, width="stretch")
                if col["fatture"]:
                    st.markdown("**Fatture**")
                    st.dataframe(pd.DataFrame([{"Documento": f["Documento"], "Tipo": f["Tipo"], "Scadenza": f["Scadenza"], "Importo": f["Importo"], "Saldato": f["Saldato"], "Cantiere": f["Cantiere"]}
                                               for f in col["fatture"]]), hide_index=True, width="stretch")
                if col["cantieri"]:
                    st.markdown("**Cantieri**")
                    st.dataframe(pd.DataFrame(col["cantieri"])[["Codice", "Cantiere", "Stato"]], hide_index=True, width="stretch")
                if not (col["documenti"] or col["fatture"] or col["cantieri"]):
                    st.caption("Nessun documento, fattura o cantiere collegato a questo nome. Il collegamento avviene per nome: scrivilo uguale negli altri strumenti.")

    with t3:
        if not cantieri:
            st.info("Inserisci i cantieri nella scheda 1.")
        else:
            for x in a2[:3]:
                st.warning(x)
            st.caption("Questo è l'elenco da tenere a fianco di monday o di qualsiasi altro sistema: stesso codice, stesso cantiere ovunque.")
            st.dataframe(pd.DataFrame(cantieri).rename(columns=ru.ETICHETTE_CANTIERI), hide_index=True, width="stretch")
            if k["senza_codice_esterno"]:
                st.caption(f"{k['senza_codice_esterno']} cantieri senza codice nell'altro sistema (colonna «Codice in altro sistema»).")

    with t4:
        if not contatti:
            st.info("Aggiungi dei contatti per generare il dossier.")
        else:
            def _gen(nome):
                return ops_report.report_generico(
                    "Rubrica e cantieri", "Contatti e codici cantiere", nome, dt.date.today(), [("CONTATTI", str(k["contatti"])), ("CANTIERI", str(k["cantieri"]))],
                    [("Contatti", str(k["contatti"]), "in rubrica", "info"), ("Cantieri", str(k["cantieri"]), f"{k['in_corso']} in corso", "info"),
                     ("Senza recapito", str(k["senza_recapito"]), "né telefono né email", "warn" if k["senza_recapito"] else "ok"), ("Senza codice esterno", str(k["senza_codice_esterno"]), "da collegare", "info")],
                    ("RUBRICA ORDINATA" if not (k["senza_recapito"]) else "DA COMPLETARE", "ok" if not k["senza_recapito"] else "warn", f"{k['contatti']} contatti, {k['cantieri']} cantieri"),
                    [{"titolo": "Contatti", "tabella": (["Nome", "Tipo", "Referente", "Telefono", "Email"], [(c["Nome"][:24], c["Ruolo"][:14], c["Referente"][:20], c["Telefono"][:16], c["Email"][:30]) for c in contatti])},
                     {"titolo": "Cantieri e codici", "tabella": (["Codice", "Cantiere", "Cliente", "Responsabile", "Stato", "Altro sistema"],
                                                                   [(c["Codice"], c["Cantiere"][:22], c["Cliente"][:20], c["Responsabile"][:18], c["Stato"], c["Esterno"][:14]) for c in cantieri]), "pagina": True},
                     {"titolo": "Nota", "testo": ["I dati di contatto sono quelli inseriti dagli utenti: verificali prima di usarli per comunicazioni formali."]}],
                    [{"nome": "Contatti", "intest": ru.COLONNE_CONTATTI, "righe": [[c[x] for x in ru.COLONNE_CONTATTI] for c in contatti]},
                     {"nome": "Cantieri", "intest": ru.COLONNE_CANTIERI, "righe": [[c[x] for x in ru.COLONNE_CANTIERI] for c in cantieri]}], [k["contatti"], k["cantieri"]])
            scarica_dossier("ru", _gen, "Rubrica", audit, "Rubrica e cantieri")
