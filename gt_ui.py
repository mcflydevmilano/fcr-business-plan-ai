"""gt_ui.py - Interfaccia del Cronoprogramma dei cantieri (Gantt)."""
import datetime as dt

import pandas as pd
import streamlit as st
import guida

import charts
import gt
import ops_report
import theme
from core import fmt_num
from sc import data_da
from ui_util import esempi_attivi, senza_esempi, banner_esempio, blocco_tabella, pannello_archivio, scarica_dossier, sola_lettura, sostituisci_tabella

ss = st.session_state
PARAM = ("soglia_pct", "preavviso_gg")
ICONE = {"ok": "🟢", "warn": "🟡", "bad": "🔴", "done": "✅", "wait": "⚪"}
NOMI_STATO = {"ok": "Nei tempi", "warn": "In ritardo", "bad": "Critica", "done": "Completata", "wait": "Da iniziare"}


@senza_esempi
def _esempio():
    oggi = dt.date.today()
    g = lambda n: (oggi + dt.timedelta(days=n)).isoformat()
    r = [("Villa Lago", "Scavi e fondazioni", -90, -50, 100, "Bianchi", ""), ("Villa Lago", "Strutture", -50, 40, 35, "Bianchi", "Scavi e fondazioni"), ("Villa Lago", "Impianti", 41, 111, 0, "Verdi", "Strutture -10"),
         ("Villa Lago", "Finiture", 111, 201, 0, "Verdi", "Impianti"),
         ("Scuola Elementare", "Fondazioni", -120, -30, 80, "Neri", ""), ("Scuola Elementare", "Elevazione", -30, 90, 0, "Neri", "Fondazioni"), ("Capannone Nord", "Intera commessa", 10, 200, 0, "Rossi", "", 30)]
    righe = []
    for x in r:
        c, f, a, b, av, resp, dopo = x[:7]
        righe.append(dict(zip(gt.COLONNE_FASI, (c, f, g(a), g(b), av, resp, dopo, g(x[7]) if len(x) > 7 else ""))))
    return pd.DataFrame(righe, columns=gt.COLONNE_FASI)


def _esempio_fermi():
    oggi = dt.date.today()
    g = lambda n: (oggi + dt.timedelta(days=n)).isoformat()
    return pd.DataFrame([{"Commessa": "Tutti", "Dal": g(60), "Al": g(74), "Motivo": "Ferie di fine anno"}, {"Commessa": "Villa Lago", "Dal": g(20), "Al": g(22), "Motivo": "Maltempo previsto"}], columns=gt.COLONNE_FERMI)


def _cfg():
    t, n = st.column_config.TextColumn, st.column_config.NumberColumn
    e = gt.ETICHETTE_FASI
    return {"Commessa": t(e["Commessa"]), "Fase": t(e["Fase"]), "Inizio": t(e["Inizio"], help="AAAA-MM-GG o GG/MM/AAAA"), "Fine": t(e["Fine"], help="AAAA-MM-GG o GG/MM/AAAA"),
            "Avanzamento": n(e["Avanzamento"], min_value=0.0, max_value=100.0, step=5.0, format="%.0f"), "Responsabile": t(e["Responsabile"]),
            "Dopo": t(e["Dopo"], help="Scrivi il nome della fase che deve finire prima (dello stesso cantiere). Più fasi: separale con «;». Per attese o sovrapposizioni aggiungi i giorni: «Strutture +5» (5 giorni dopo la fine) o «Strutture -10» (parte 10 giorni prima che finiscano). Vuoto = parte quando vuole."),
            "NonPrima": t(e["NonPrima"], help="Data minima di inizio: arrivo dei materiali, permessi, autorizzazioni. AAAA-MM-GG o GG/MM/AAAA. Vuoto = nessun vincolo.")}


def _cfg_fermi():
    t = st.column_config.TextColumn
    e = gt.ETICHETTE_FERMI
    return {"Commessa": t(e["Commessa"], help="Nome del cantiere oppure «Tutti»"), "Dal": t(e["Dal"], help="AAAA-MM-GG o GG/MM/AAAA"), "Al": t(e["Al"], help="Ultimo giorno di fermo. Vuoto = un solo giorno."), "Motivo": t(e["Motivo"])}


def _raccogli():
    return {"fasi": ss["gt_fasi"].to_dict("records"), "fermi": ss["gt_fermi"].to_dict("records") if "gt_fermi" in ss else [], "params": {k: ss.get("gt_" + k, gt.GT_DEFAULT[k]) for k in PARAM}}


def _applica(p, nome):
    sostituisci_tabella("gt_fasi", pd.DataFrame(p.get("fasi") or [], columns=gt.COLONNE_FASI))
    sostituisci_tabella("gt_fermi", pd.DataFrame(p.get("fermi") or [], columns=gt.COLONNE_FERMI))
    ss["gt_demo"] = False
    ss["_pending"] = {"gt_" + k: v for k, v in (p.get("params") or {}).items() if k in PARAM}


def _aggiungi(nuove, audit, sigla):
    """Aggiunge le fasi che non ci sono gia' (stessa commessa e fase)."""
    att = ss["gt_fasi"]
    gia = {(str(r["Commessa"]).strip().lower(), str(r["Fase"]).strip().lower()) for r in att.to_dict("records")} if not ss.get("gt_demo") else set()
    nuove = [f for f in nuove if (f["Commessa"].lower(), f["Fase"].lower()) not in gia]
    if not nuove:
        st.info("Nessuna fase nuova da aggiungere.")
        return
    base = pd.DataFrame(columns=gt.COLONNE_FASI) if ss.get("gt_demo") else att
    sostituisci_tabella("gt_fasi", pd.concat([base, pd.DataFrame(nuove, columns=gt.COLONNE_FASI)], ignore_index=True))
    ss["gt_demo"] = False
    audit(f"gt_da_{sigla}", f"{len(nuove)} fasi")
    st.rerun()


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Cronoprogramma dei cantieri", "Il diagramma di Gantt: quando parte e finisce ogni fase, a che punto è davvero e dove si accumula ritardo."), unsafe_allow_html=True)
    guida.mostra("gt")
    if "gt_fasi" not in ss:
        ss["gt_fasi"] = _esempio()
        ss["gt_demo"] = esempi_attivi()
    if "gt_fermi" not in ss:
        ss["gt_fermi"] = _esempio_fermi() if ss.get("gt_demo") else pd.DataFrame(columns=gt.COLONNE_FERMI)
    for k in PARAM:
        ss.setdefault("gt_" + k, gt.GT_DEFAULT[k])
    pannello_archivio("gt", "il cronoprogramma", _raccogli, _applica, audit, utente)
    t1, t2, t3 = st.tabs(["🗓️ 1. Fasi", "📊 2. Gantt e ritardi", "📄 3. Dossier"])
    with t1:
        banner_esempio("gt_demo", [("gt_fasi", gt.COLONNE_FASI), ("gt_fermi", gt.COLONNE_FERMI)], "svuota_gt")
        blocco_tabella("gt_fasi", "Fasi dei cantieri", "Una riga per ogni fase (o una sola «Intera commessa»). L'avanzamento reale lo aggiorni tu, in percentuale.",
                       gt.COLONNE_FASI, gt.ETICHETTE_FASI, _cfg(), ss["gt_fasi"], "gt", 1, audit, 320)
        blocco_tabella("gt_fermi", "Giorni di fermo (ferie, maltempo, festività)", "I giorni di fermo che cadono dentro una fase la allungano; le fasi successive slittano di conseguenza. «Tutti» vale per ogni cantiere.",
                       gt.COLONNE_FERMI, gt.ETICHETTE_FERMI, _cfg_fermi(), ss["gt_fermi"], "gt", 2, audit, 200)
        if st.button("🎄 Aggiungi le festività italiane", key="fest_gt", disabled=sola_lettura(), help="Aggiunge i giorni festivi nazionali (con Pasqua e Pasquetta) per gli anni coperti dalle fasi."):
            fasi_ok, _ = gt.normalizza_fasi(ss["gt_fasi"].to_dict("records"))
            anni = sorted({int(f["Inizio"][:4]) for f in fasi_ok} | {int(f["Fine"][:4]) for f in fasi_ok} | {dt.date.today().year})
            att = ss["gt_fermi"].to_dict("records")
            gia = {(str(r.get("Commessa") or "").strip().lower(), str(data_da(r.get("Dal")))) for r in att}
            nuove = [x for a in anni for x in gt.festivita_italiane(a) if ("tutti", x["Dal"]) not in gia]
            sostituisci_tabella("gt_fermi", pd.DataFrame(att + nuove, columns=gt.COLONNE_FERMI))
            audit("gt_festivita", f"{len(nuove)} giorni")
            st.rerun()
        st.markdown("**Collega le fasi tra loro**")
        st.caption("Nella colonna «Parte dopo la fase…» scrivi quale fase deve finire prima. Se una fase slitta, il Gantt sposta da solo quelle che vengono dopo.")
        if st.button("🔗 Collega le fasi in sequenza", key="seq_gt", disabled=sola_lettura(), help="Per ogni cantiere mette ogni fase dopo quella che inizia prima. Non tocca i collegamenti già scritti."):
            nuove = gt.in_sequenza(ss["gt_fasi"].to_dict("records"))
            sostituisci_tabella("gt_fasi", pd.DataFrame(nuove, columns=gt.COLONNE_FASI))
            audit("gt_sequenza")
            st.rerun()
        st.markdown("**Parti da dati che hai già**")
        a, b = st.columns(2)
        if a.button("Carica le commesse dal SAL", key="da_sl_gt", width="stretch", disabled=sola_lettura(), help="Usa inizio, fine prevista e avanzamento reale inseriti nel SAL."):
            if "sl_com" not in ss:
                st.warning("Apri prima il SAL (o un suo salvataggio): i dati non sono ancora in questa sessione.")
            else:
                _aggiungi(gt.fasi_da_commesse_sl(ss["sl_com"].to_dict("records")), audit, "sl")
        if b.button("Crea le fasi dalle assegnazioni di Organico", key="da_og_gt", width="stretch", disabled=sola_lettura(), help="Una fase per ogni squadra o persona assegnata a una commessa."):
            if "og_ass" not in ss:
                st.warning("Apri prima Organico (o un suo salvataggio): i dati non sono ancora in questa sessione.")
            else:
                _aggiungi(gt.fasi_da_assegnazioni(ss["og_ass"].to_dict("records")), audit, "og")
        st.subheader("Ipotesi")
        c1, c2, c3 = st.columns(3)
        c1.date_input("Data di riferimento", key="gt_oggi", value=dt.date.today())
        c2.number_input("Ritardo: scostamento oltre (punti %)", 1.0, 60.0, step=1.0, key="gt_soglia_pct", help="Se l'avanzamento reale è sotto il previsto di più di questi punti, la fase è «in ritardo»; oltre il doppio è «critica».")
        c3.number_input("Fasi in scadenza entro (giorni)", 0, 60, step=1, key="gt_preavviso_gg")

    fasi, av_n = gt.normalizza_fasi(ss["gt_fasi"].to_dict("records"))
    fermi, _ = gt.normalizza_fermi(ss["gt_fermi"].to_dict("records"))
    out = gt.calcola_gt(fasi, fermi=fermi, p={"oggi": ss.get("gt_oggi", dt.date.today()), "soglia_pct": ss.get("gt_soglia_pct", 15.0), "preavviso_gg": ss.get("gt_preavviso_gg", 7)})
    k = out["kpi"]
    with t2:
        if not fasi:
            st.warning("Nessuna fase valida: servono cantiere, inizio e fine.")
        else:
            for x in av_n[:3]:
                st.caption("⚠️ " + x)
            if k["fasi_critiche"]:
                n = k["fasi_critiche"]
                st.error(f"**{n} {'fase critica' if n == 1 else 'fasi critiche'}**: oltre la fine prevista o molto in ritardo sull'avanzamento. Ritardo massimo stimato: {k['ritardo_max_gg']} giorni.")
            elif k["fasi_in_ritardo"]:
                st.warning(f"**{k['fasi_in_ritardo']} {'fase' if k['fasi_in_ritardo'] == 1 else 'fasi'} in ritardo** rispetto al previsto.")
            else:
                st.success("**Cronoprogramma nei tempi.**")
            st.markdown(theme.stat_strip([
                {"label": "Cantieri", "value": str(k["commesse"]), "sub": f"{k['fasi']} fasi", "tono": "info"},
                {"label": "Cantieri in ritardo", "value": str(k["commesse_in_ritardo"]), "sub": f"ritardo max {k['ritardo_max_gg']} gg", "tono": "bad" if k["commesse_in_ritardo"] else "ok"},
                {"label": "Fasi in ritardo", "value": str(k["fasi_in_ritardo"]), "sub": f"{k['fasi_critiche']} critiche", "tono": "bad" if k["fasi_critiche"] else ("warn" if k["fasi_in_ritardo"] else "ok")},
                {"label": "Fasi in scadenza", "value": str(k["fasi_in_scadenza"]), "sub": f"entro {out['params']['preavviso_gg']} giorni", "tono": "warn" if k["fasi_in_scadenza"] else "ok"}]), unsafe_allow_html=True)
            nomi = [c["Commessa"] for c in out["commesse"]]
            v1, v2 = st.columns([2, 1])
            sel = v1.selectbox("Cantiere", ["Tutti"] + nomi, key="gt_vista")
            solo = v2.checkbox("Solo i cantieri (senza fasi)", key="gt_solo")
            st.pyplot(charts.fig_gt(out, "light", solo_commesse=solo, commessa=None if sel == "Tutti" else sel), clear_figure=True)
            st.markdown("**Cantieri**")
            st.dataframe(pd.DataFrame([{"": ICONE[c["Stato"]], "Cantiere": c["Commessa"], "Inizio": c["Inizio"], "Fine prevista": c["Fine"], "Avanz. %": c["Avanzamento"], "Previsto %": c["Prevista"],
                                        "Fine stimata": c["Fine stimata"], "Ritardo gg": c["Ritardo gg"], "Fasi in ritardo": c["Fasi in ritardo"]} for c in out["commesse"]]), hide_index=True, width="stretch")
            slit = [f for f in out["fasi"] if f["Slitta gg"] > 0 or f["Giorni di fermo"] > 0]
            if slit:
                st.markdown("**Fasi che slittano o si allungano**")
                st.dataframe(pd.DataFrame([{"Cantiere": f["Commessa"], "Fase": f["Fase"], "Inizio previsto": f["Inizio"], "Inizio stimato": f["Inizio stimato"], "Slitta di (gg)": f["Slitta gg"],
                                            "Giorni di fermo": f["Giorni di fermo"], "Fine prevista": f["Fine"], "Fine stimata": f["Fine stimata"], "Perché": f["Motivo"]} for f in slit]), hide_index=True, width="stretch")
            if out["avvisi"]:
                st.markdown("**Da seguire**")
                for a in out["avvisi"][:10]:
                    st.warning(a)
    with t3:
        if not fasi:
            st.info("Aggiungi delle fasi per generare il dossier.")
        else:
            scarica_dossier("gt", lambda n: ops_report.report_gt(out, n), "Cronoprogramma", audit, "Cronoprogramma dei cantieri")
        st.caption("L'avanzamento previsto è lineare tra inizio e fine di ogni fase; la fine stimata usa il ritmo reale finora. Le fasi legate dalla colonna «Parte dopo la fase…» slittano a catena; non sono modellati ritardi di consegna, sovrapposizioni parziali né calendari di lavoro (ferie, maltempo). Sono indicazioni, non una pianificazione CPM completa.")
