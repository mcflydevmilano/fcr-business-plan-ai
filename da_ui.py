"""da_ui.py - Interfaccia di Documenti aziendali FCR (DURC, SOA, certificazioni, assicurazioni, visura...)."""
import datetime as dt

import pandas as pd
import streamlit as st
import guida

import da
import doc_allegati
import ops_report
import theme
from ddt import DdtErrore
from ui_util import esempi_attivi, senza_esempi, banner_esempio, blocco_tabella, pannello_archivio, scarica_dossier, sola_lettura, sostituisci_tabella

ss = st.session_state
ICONE = {"ok": "🟢", "warn": "🟡", "bad": "🔴", "nd": "⚪"}


@senza_esempi
def _esempio():
    g = lambda n: (dt.date.today() + dt.timedelta(days=n)).isoformat()
    righe = [("DURC", "Regolarità contributiva", "", g(25), "Paola Neri"), ("SOA", "OG1 classifica III", "SOA-00123", g(220), "Paola Neri"),
             ("Visura camerale", "", "", g(-5), "Paola Neri"), ("Assicurazione RCT/RCO", "Polizza generale", "RCT-998877", g(150), "Anna Bianchi"),
             ("Certificazione ISO", "ISO 9001:2015", "ISO-4455", g(300), "Anna Bianchi")]
    return pd.DataFrame([dict(zip(da.COLONNE_DOC, r)) for r in righe], columns=da.COLONNE_DOC)


def _cfg():
    t = st.column_config.TextColumn
    a = da.ETICHETTE_DOC
    return {"Tipo": st.column_config.SelectboxColumn(a["Tipo"], options=da.TIPI, width="medium"), "Descrizione": t(a["Descrizione"], width="medium"), "Numero": t(a["Numero"]),
            "Scadenza": t(a["Scadenza"], help="AAAA-MM-GG o GG/MM/AAAA"), "Responsabile": t(a["Responsabile"])}


def _raccogli():
    return {"doc": ss["da_doc"].to_dict("records"), "params": {"preavviso_gg": ss.get("da_preavviso_gg", da.DA_DEFAULT["preavviso_gg"])}}


def _applica(p, nome):
    sostituisci_tabella("da_doc", pd.DataFrame(p.get("doc") or [], columns=da.COLONNE_DOC))
    ss["da_demo"] = False
    ss["_pending"] = {"da_preavviso_gg": (p.get("params") or {}).get("preavviso_gg", da.DA_DEFAULT["preavviso_gg"])}


def _kb(n):
    n = n or 0
    return f"{n / 1048576:.1f} MB" if n > 1048576 else f"{n / 1024:.0f} KB"


def _sezione_documenti(righe_doc, utente, audit):
    st.markdown("**📎 File caricati (PDF o foto del documento)**")
    opz = [r for r in righe_doc if (r.get("Tipo") or "").strip()]
    if not opz:
        st.caption("Aggiungi prima almeno una riga qui sopra (Tipo di documento), poi torna qui per caricare il file.")
        return
    etichette = [f"{r['Tipo']}" + (f" · {r['Descrizione']}" if r.get("Descrizione") else "") for r in opz]
    idx = st.selectbox("Documento", range(len(opz)), format_func=lambda i: etichette[i], key="da_doc_sel")
    r = opz[idx]
    voce = r.get("Descrizione") or r.get("Numero") or "documento"
    esistenti = [e for e in doc_allegati.elenca("azienda", r["Tipo"]) if e["voce"] == voce]
    for e in esistenti:
        c1, c2, c3 = st.columns([3, 1, 1])
        c1.caption(f"📄 {e['nome_file']} · {_kb(e['dimensione'])} · caricato da {e['caricato_da'] or '—'}")
        letto = doc_allegati.leggi(e["id"])
        if letto:
            c2.download_button("⬇️ Scarica", letto[1], file_name=e["nome_file"], mime=e["mime"], key=f"da_doc_dl_{e['id']}")
        if not sola_lettura() and c3.button("🗑️ Elimina", key=f"da_doc_del_{e['id']}"):
            doc_allegati.elimina(e["id"])
            audit("da_doc_eliminato", f"{r['Tipo']}: {e['nome_file']}")
            st.rerun()
    if not esistenti:
        st.caption("Nessun file caricato per questo documento.")
    if sola_lettura():
        return
    up = st.file_uploader("Carica il PDF (o una foto)", type=["pdf", "jpg", "jpeg", "png"], key="da_doc_up")
    if up is not None and st.button("📎 Allega", key="da_doc_allega"):
        try:
            doc_allegati.salva("azienda", r["Tipo"], voce, up.name, up.getvalue(), scadenza=r.get("Scadenza", ""), utente=utente)
        except doc_allegati.DocDoppio:
            st.warning("Questo file è già stato caricato.")
        except DdtErrore as e:
            st.error(str(e))
        else:
            audit("da_doc_caricato", f"{r['Tipo']}: {up.name}")
            st.rerun()


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Documenti aziendali FCR", "DURC, SOA, certificazioni, assicurazioni, visura camerale: tutto l'elenco con scadenze e file, subito visibile."), unsafe_allow_html=True)
    guida.mostra("da")
    if "da_doc" not in ss:
        ss["da_doc"] = _esempio()
        ss["da_demo"] = esempi_attivi()
    pannello_archivio("da", "i documenti aziendali", _raccogli, _applica, audit, utente)
    t1, t2 = st.tabs(["📑 1. Documenti", "📄 2. Dossier"])
    with t1:
        banner_esempio("da_demo", [("da_doc", da.COLONNE_DOC)], "svuota_da")
        blocco_tabella("da_doc", "Documenti dell'azienda", "Una riga per documento (DURC, SOA, certificazioni, assicurazioni, visura...). Tutto l'elenco è già qui, senza doverlo aprire.",
                        da.COLONNE_DOC, da.ETICHETTE_DOC, _cfg(), ss["da_doc"], "da", 1, audit, 260, da.SINONIMI_DOC)
        _sezione_documenti(ss["da_doc"].to_dict("records"), utente, audit)
        ss.setdefault("da_preavviso_gg", int(da.DA_DEFAULT["preavviso_gg"]))
        st.subheader("Ipotesi")
        a, b = st.columns(2)
        a.date_input("Data di riferimento", key="da_oggi", value=dt.date.today())
        b.number_input("Preavviso scadenze (giorni)", 0, 180, step=5, key="da_preavviso_gg")

    doc, av = da.normalizza_doc(ss["da_doc"].to_dict("records"))
    out = da.calcola_da(doc, {"oggi": ss.get("da_oggi", dt.date.today()), "preavviso_gg": ss.get("da_preavviso_gg", 30)})
    k = out["kpi"]

    with t1:
        if doc:
            for x in av[:3]:
                st.caption("⚠️ " + x)
            if k["scaduti"]:
                st.error(f"**{k['scaduti']} documenti scaduti.**")
            elif k["in_scadenza"]:
                st.warning(f"**{k['in_scadenza']} documenti in scadenza.**")
            else:
                st.success("**Tutti i documenti sono in regola.**")
            st.markdown(theme.stat_strip([
                {"label": "Documenti", "value": str(k["n_doc"]), "sub": f"{k['senza_scadenza']} senza scadenza", "tono": "info"},
                {"label": "Scaduti", "value": str(k["scaduti"]), "sub": "da rinnovare subito", "tono": "bad" if k["scaduti"] else "ok"},
                {"label": "In scadenza", "value": str(k["in_scadenza"]), "sub": "entro il preavviso", "tono": "warn" if k["in_scadenza"] else "ok"},
                {"label": "In regola", "value": str(k["ok"]), "sub": f"su {k['n_doc']}", "tono": "ok"}]), unsafe_allow_html=True)
            for a in out["avvisi"][:8]:
                st.warning(a)
            st.dataframe(pd.DataFrame([{"": ICONE[d["Stato"]], "Tipo": d["Tipo"], "Descrizione": d["Descrizione"], "Numero": d["Numero"], "Scadenza": d["Scadenza"], "Giorni": d["Giorni"],
                                        "Responsabile": d["Responsabile"]} for d in out["documenti"]]), hide_index=True, width="stretch")

    with t2:
        if not doc:
            st.info("Aggiungi dei documenti per generare il dossier.")
        else:
            def _gen(nome):
                return ops_report.report_generico(
                    "Documenti aziendali FCR", "Documenti aziendali", nome, dt.date.today(), [("DOCUMENTI", str(k["n_doc"])), ("SCADUTI", str(k["scaduti"]))],
                    [("Documenti", str(k["n_doc"]), f"{k['senza_scadenza']} senza scadenza", "info"), ("Scaduti", str(k["scaduti"]), "da rinnovare", "bad" if k["scaduti"] else "ok"),
                     ("In scadenza", str(k["in_scadenza"]), f"entro {out['params']['preavviso_gg']} giorni", "warn" if k["in_scadenza"] else "ok"),
                     ("In regola", str(k["ok"]), f"su {k['n_doc']}", "ok")],
                    ("TUTTO IN REGOLA" if not out["avvisi"] else "DA CONTROLLARE", "ok" if not out["avvisi"] else "bad", f"{k['n_doc']} documenti"),
                    [{"titolo": "Documenti", "tabella": (["Tipo", "Descrizione", "Numero", "Scadenza", "Responsabile"],
                                                          [(d["Tipo"][:22], d["Descrizione"][:30], d["Numero"][:18], d["Scadenza"], d["Responsabile"][:18]) for d in out["documenti"]])},
                     {"titolo": "Punti di attenzione", "testo": ["- " + a for a in (out["avvisi"] or ["Nessuna anomalia rilevata."])]}],
                    [{"nome": "Documenti", "intest": da.COLONNE_DOC, "righe": [[d[c] for c in da.COLONNE_DOC] for d in doc]}], [k["n_doc"]])
            scarica_dossier("da", _gen, "Documenti aziendali", audit, "Documenti aziendali FCR")
        st.caption("Promemoria delle scadenze inserite: verifica sempre i documenti originali prima di affidare lavori o firmare contratti.")
