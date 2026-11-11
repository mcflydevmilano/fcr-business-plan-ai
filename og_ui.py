"""og_ui.py - Interfaccia di Organico e carico di lavoro."""
import datetime as dt

import pandas as pd
import streamlit as st
import guida

import charts
import og
import ops_report
import theme
from core import fmt_num
from ui_util import colonna_cantiere, esempi_attivi, senza_esempi, banner_esempio, blocco_tabella, pannello_archivio, scarica_dossier, sola_lettura, sostituisci_tabella

ss = st.session_state
PARAM = ("mesi", "sat_min_pct", "ore_giorno", "patrono", "festivita")
NOME = og.NOME_UNICO             # salvataggio condiviso: un solo elenco aziendale, tutti vedono lo stesso (come i Rapportini)


@senza_esempi
def _esempio():
    oggi = dt.date.today()
    g = lambda n: (oggi + dt.timedelta(days=n)).isoformat()
    interni = [("Capocantiere Bianchi", "Capocantiere", 45, 8, None, "", "")]
    operai = [("Squadra Muratori A", "Muratori", 32, 24, None, "", ""), ("Squadra Muratori B", "Muratori", 32, 16, None, "", ""),
              ("Impiantisti", "Impianti", 38, 16, None, "", ""), ("Gruista", "Operatore", 34, 8, None, "", "")]
    ass = [("Squadra Muratori A", "Villa Lago", g(-60), g(60), 300), ("Squadra Muratori A", "Scuola Elementare", g(30), g(240), 260), ("Squadra Muratori B", "Scuola Elementare", g(-30), g(150), 280),
           ("Impiantisti", "Scuola Elementare", g(60), g(180), 300), ("Impiantisti", "Villa Lago", g(-30), g(45), 120), ("Capocantiere Bianchi", "Villa Lago", g(-60), g(60), 90),
           ("Capocantiere Bianchi", "Scuola Elementare", g(-30), g(240), 100), ("Gruista", "Scuola Elementare", g(20), g(120), 120)]
    campi = ["Risorsa", "Ruolo", "Costo_orario", "Ore_giorno", "Ore_mese", "Assunzione", "Cessazione"]
    mk_ris = lambda tipo, rows: pd.DataFrame([{**dict(zip(campi, r)), "Tipo": tipo} for r in rows], columns=og.COLONNE_RIS)
    mk = lambda cols, rows: pd.DataFrame([dict(zip(cols, r)) for r in rows], columns=cols)
    return mk_ris("Interno", interni), mk_ris("Operaio", operai), mk(og.COLONNE_ASS, ass), mk(og.COLONNE_ASSENZE, [])


def _cfg():
    n, t = st.column_config.NumberColumn, st.column_config.TextColumn
    a, b = og.ETICHETTE_RIS, og.ETICHETTE_ASS
    cr = {"Risorsa": t(a["Risorsa"], width="medium"), "Tipo": None, "Ruolo": t(a["Ruolo"]), "Costo_orario": n(a["Costo_orario"], min_value=0.0, step=1.0, format="%.1f"),
          "Ore_giorno": n(a["Ore_giorno"], min_value=0.0, max_value=24.0, step=1.0, format="%.1f"), "Ore_mese": n(a["Ore_mese"], min_value=0.0, step=10.0, format="%.0f"),
          "Assunzione": t(a["Assunzione"], help="AAAA-MM-GG o GG/MM/AAAA"), "Cessazione": t(a["Cessazione"], help="Dopo questa data la persona esce da capacità, costi e previsioni.")}
    return (cr,
            {"Risorsa": t(b["Risorsa"], width="medium"), "Commessa": colonna_cantiere(b["Commessa"], (("og_ass", "Commessa"),)), "Dal": t(b["Dal"], help="AAAA-MM-GG o GG/MM/AAAA"), "Al": t(b["Al"], help="Vuoto = senza fine"),
             "Ore_mese": n(b["Ore_mese"], min_value=0.0, step=10.0, format="%.0f")},
            {"Risorsa": t(og.ETICHETTE_ASSENZE["Risorsa"], width="medium"), "Dal": t("Dal", help="AAAA-MM-GG o GG/MM/AAAA"), "Al": t(og.ETICHETTE_ASSENZE["Al"]), "Motivo": t(og.ETICHETTE_ASSENZE["Motivo"])})


def _combinati():
    """Le due tabelle di questa sessione (interni e operai) come un'unica lista, con il campo Tipo giusto per ciascuna."""
    i = ss["og_ris_int"].assign(Tipo="Interno").to_dict("records") if "og_ris_int" in ss else []
    o = ss["og_ris_op"].assign(Tipo="Operaio").to_dict("records") if "og_ris_op" in ss else []
    return i + o


def _raccogli():
    return {"ris": _combinati(), "ass": ss["og_ass"].to_dict("records"), "abs": ss["og_abs"].to_dict("records"), "params": {k: ss.get("og_" + k, og.OG_DEFAULT[k]) for k in PARAM}}


def _firma():
    import hashlib
    import json
    return hashlib.sha1(json.dumps(_raccogli(), default=str, sort_keys=True).encode("utf-8")).hexdigest()


def _applica(p, nome=""):
    ris = p.get("ris") or []
    interni = [r for r in ris if str(r.get("Tipo") or "") != "Operaio"]
    operai = [r for r in ris if str(r.get("Tipo") or "") == "Operaio"]
    sostituisci_tabella("og_ris_int", pd.DataFrame(interni, columns=og.COLONNE_RIS))
    sostituisci_tabella("og_ris_op", pd.DataFrame(operai, columns=og.COLONNE_RIS))
    sostituisci_tabella("og_ass", pd.DataFrame(p.get("ass") or [], columns=og.COLONNE_ASS))
    sostituisci_tabella("og_abs", pd.DataFrame(p.get("abs") or [], columns=og.COLONNE_ASSENZE))
    ss["og_demo"] = False
    ss["_og_firma"] = _firma()
    ss["_pending"] = {"og_" + k: v for k, v in (p.get("params") or {}).items() if k in PARAM}


def _carica_condiviso():
    """All'apertura: se esiste l'elenco condiviso lo carica; altrimenti parte con un esempio."""
    import storage
    try:
        p = storage.carica_pratica(NOME, modulo="og")
        meta = storage.meta_pratica(NOME, modulo="og") if p else None
    except Exception:
        p, meta = None, None
    if p:
        _applica(p, NOME)
        ss["_base_og"] = {"nome": NOME, "agg": meta["aggiornato"] if meta else ""}
    else:
        ss["og_ris_int"], ss["og_ris_op"], ss["og_ass"], ss["og_abs"] = _esempio()
        ss["og_demo"] = esempi_attivi()
        ss["_og_firma"] = _firma()


def _aggiorna_se_cambiato():
    """Se un collega ha salvato Organico (o un Rapportino ha aggiunto un operaio) e qui non ci sono modifiche in sospeso, rilegge i dati."""
    import storage
    base = ss.get("_base_og") or {}
    if base.get("nome") != NOME or ss.get("og_demo") or ss.get("_og_firma") != _firma():
        return
    try:
        meta = storage.meta_pratica(NOME, modulo="og")
        if meta and meta["aggiornato"] != base.get("agg"):
            p = storage.carica_pratica(NOME, modulo="og")
            if p:
                _applica(p, NOME)
                ss["_base_og"] = {"nome": NOME, "agg": meta["aggiornato"]}
    except Exception:
        pass


def _salva(utente, audit):
    import storage
    for _ in range(4):
        try:
            meta = storage.meta_pratica(NOME, modulo="og")
            agg = storage.salva_pratica(NOME, _raccogli(), autore=utente, modulo="og", atteso=meta["aggiornato"] if meta else "")
        except storage.ConflittoSalvataggio:
            p = storage.carica_pratica(NOME, modulo="og")
            if p:
                _applica(p, NOME)
            continue
        except Exception as e:
            return False, f"Salvataggio non riuscito: {e}"
        ss["_base_og"] = {"nome": NOME, "agg": agg}
        ss["_og_firma"] = _firma()
        audit("og_salvato", NOME)
        return True, ""
    return False, "Troppi salvataggi contemporanei: riprova tra un istante."


def _dati():
    r, a1 = og.normalizza_ris(_combinati())
    a, a2 = og.normalizza_ass(ss["og_ass"].to_dict("records"), {x["Risorsa"] for x in r})
    ab, a3 = og.normalizza_assenze(ss["og_abs"].to_dict("records"), [x["Risorsa"] for x in r])
    return r, a, ab, a1 + a2 + a3


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Organico e carico di lavoro", "Quanta gente serve nei prossimi mesi, quando si è in troppi o in pochi e quanto costano le ore ferme."), unsafe_allow_html=True)
    guida.mostra("og")
    if "og_ris_int" not in ss:
        _carica_condiviso()
    else:
        _aggiorna_se_cambiato()
    for _k, _cols in (("og_ris_int", ("Ruolo", "Assunzione", "Cessazione")), ("og_ris_op", ("Ruolo", "Assunzione", "Cessazione")),
                      ("og_ass", ("Dal", "Al")), ("og_abs", ("Risorsa", "Dal", "Al", "Motivo"))):
        for _c in _cols:
            if _c in ss[_k].columns and ss[_k][_c].dtype != object:
                ss[_k][_c] = ss[_k][_c].astype(object).where(ss[_k][_c].notna(), "")
    st.caption("Organico è un unico elenco aziendale: quello che vedi è sempre l'ultimo salvato, anche se aggiunto da un Rapportino.")
    if st.button("💾 Salva le modifiche", key="og_salva", type="primary", disabled=sola_lettura()):
        ok, err = _salva(utente, audit)
        st.success("Salvato.") if ok else st.error(err)
    t1, t2, t3 = st.tabs(["👷 1. Risorse e Assegnazioni", "📊 2. Carico di lavoro", "📄 3. Dossier"])
    cr, ca, cb = _cfg()
    with t1:
        banner_esempio("og_demo", [("og_ris_int", og.COLONNE_RIS), ("og_ris_op", og.COLONNE_RIS), ("og_ass", og.COLONNE_ASS), ("og_abs", og.COLONNE_ASSENZE)], "svuota_og")
        blocco_tabella("og_ris_int", "Personale interno", "Dipendenti e staff fisso dell'azienda.", og.COLONNE_RIS, og.ETICHETTE_RIS, cr, ss["og_ris_int"], "og", 1, audit, 180)
        blocco_tabella("og_ris_op", "Operai di cantiere", "Operai e squadre di cantiere (anche esterni): qui compaiono anche quelli aggiunti in automatico dai Rapportini.", og.COLONNE_RIS, og.ETICHETTE_RIS, cr, ss["og_ris_op"], "og", 2, audit, 220)
        blocco_tabella("og_ass", "Assegnazioni alle commesse", "Una riga per ogni periodo in cui una risorsa lavora a una commessa, con le ore mensili. Al vuoto = senza fine.", og.COLONNE_ASS, og.ETICHETTE_ASS, ca, ss["og_ass"], "og", 3, audit, 280)
        blocco_tabella("og_abs", "Ferie, malattie, chiusure", "Giorni in cui una risorsa non c'è. Scrivi «Tutti» per una chiusura aziendale (es. Ferragosto, ponte). Sabato, domenica e festività nazionali sono già esclusi.", og.COLONNE_ASSENZE, og.ETICHETTE_ASSENZE, cb, ss["og_abs"], "og", 4, audit, 180)
        ss.setdefault("og_mesi", int(og.OG_DEFAULT["mesi"]))
        ss.setdefault("og_sat_min_pct", float(og.OG_DEFAULT["sat_min_pct"]))
        st.subheader("Ipotesi")
        ss.setdefault("og_ore_giorno", float(og.OG_DEFAULT["ore_giorno"]))
        ss.setdefault("og_patrono", "")
        ss.setdefault("og_festivita", True)
        a, b, c = st.columns(3)
        a.date_input("Data di riferimento", key="og_oggi", value=dt.date.today())
        b.number_input("Mesi da prevedere", 1, 24, step=1, key="og_mesi")
        c.number_input("Saturazione minima (%)", 0.0, 100.0, step=5.0, key="og_sat_min_pct", help="Sotto questa soglia il mese è considerato «scarico».")
        d, e, f = st.columns(3)
        d.number_input("Ore al giorno (standard)", 1.0, 24.0, step=0.5, key="og_ore_giorno", help="Usate quando in Risorse non indichi le ore al giorno.")
        e.text_input("Festa del patrono (GG/MM)", key="og_patrono", placeholder="es. 07/12", help="Il giorno del santo patrono della tua città: non si lavora.")
        f.toggle("Escludi le festività nazionali", key="og_festivita", help="Capodanno, Epifania, Pasqua e Pasquetta, 25 aprile, 1 maggio, 2 giugno, Ferragosto, Ognissanti, 8, 25 e 26 dicembre.")

    ris, ass, ab, av_n = _dati()
    out = og.calcola_og(ris, ass, {"oggi": ss.get("og_oggi", dt.date.today()), "mesi": ss.get("og_mesi", 6), "sat_min_pct": ss.get("og_sat_min_pct", 60.0),
                                   "ore_giorno": ss.get("og_ore_giorno", 8.0), "patrono": ss.get("og_patrono", ""), "festivita": ss.get("og_festivita", True)}, ab)
    k, mesi = out["kpi"], out["mesi"]

    with t2:
        if not ris:
            st.warning("Nessuna risorsa valida: inserisci nome e ore disponibili.")
        else:
            for x in av_n[:3]:
                st.caption("⚠️ " + x)
            if k["mesi_sovraccarico"]:
                st.error(f"**{k['mesi_sovraccarico']} mesi in sovraccarico**: al picco servono circa {fmt_num(k['ore_extra_picco'])} ore in più (≈ {fmt_num(k['persone_in_piu_picco'], 1)} persone).")
            elif k["mesi_scarico"]:
                st.warning(f"**{k['mesi_scarico']} mesi con poco lavoro**: ore ferme per circa {fmt_num(k['costo_inattivo'])} €.")
            else:
                st.success("**Carico equilibrato** nel periodo.")
            st.markdown(theme.stat_strip([
                {"label": "Saturazione media", "value": f"{fmt_num(k['saturazione_media'], 0)}%", "sub": f"picco {fmt_num(k['picco_saturazione'], 0)}%", "tono": "info"},
                {"label": "Mesi in sovraccarico", "value": str(k["mesi_sovraccarico"]), "sub": f"{fmt_num(k['ore_extra_picco'])} ore extra al picco", "tono": "bad" if k["mesi_sovraccarico"] else "ok"},
                {"label": "Mesi con poco lavoro", "value": str(k["mesi_scarico"]), "sub": "sotto la saturazione minima", "tono": "warn" if k["mesi_scarico"] else "ok"},
                {"label": "Costo ore inattive", "value": f"{fmt_num(k['costo_inattivo'])} €", "sub": "stima sul periodo", "tono": "warn" if k["costo_inattivo"] > 0 else "ok"}]), unsafe_allow_html=True)
            for a in out["avvisi"][:6]:
                st.warning(a)
            st.pyplot(charts.fig_og_carico(mesi, "light"), clear_figure=True)
            st.dataframe(pd.DataFrame([{k2: v for k2, v in m.items() if k2 != "Stato"} for m in mesi]).round(0), hide_index=True, width="stretch")
            st.markdown("**Saturazione per risorsa (%)**")
            st.dataframe(pd.DataFrame([{k2: v for k2, v in r.items() if k2 != "Stato"} for r in out["risorse"]]).round(0), hide_index=True, width="stretch")
            if out["commesse"]:
                st.markdown("**Costo del personale per commessa (€)**")
                st.dataframe(pd.DataFrame(out["commesse"]), hide_index=True, width="stretch")

    with t3:
        if not ris:
            st.info("Aggiungi delle risorse per generare il dossier.")
        else:
            scarica_dossier("og", lambda n: ops_report.report_og(out, ris, ass, n, ab), "Organico", audit, "Organico e carico di lavoro")
        st.caption("Le ore disponibili vengono dal calendario (lun-ven, senza festività e assenze inserite). Gli straordinari non sono considerati.")
        with st.expander("🗄️ Copie di sicurezza con nome (facoltativo)"):
            st.caption("Organico è un elenco unico: questa è solo una copia di sicurezza con un nome a tua scelta, per tornare indietro se serve. Non serve per il lavoro di tutti i giorni.")
            pannello_archivio("og", "una copia di Organico", _raccogli, _applica, audit, utente)
