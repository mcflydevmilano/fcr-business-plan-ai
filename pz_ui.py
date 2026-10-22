"""pz_ui.py - Interfaccia del Prezziario: ricerca, caricamento dei listini, confronto tra quadrimestri e selettore per il Computo."""
import datetime as dt
import re

import pandas as pd
import streamlit as st

import guida
import pz
import theme
from core import fmt_num
from ui_util import sola_lettura

ss = st.session_state
LIMITE_TABELLA = 300


# ----------------------------------------------------------------------------
# DATI (con cache: le righe stanno nel database compresse, si leggono una volta)
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner="Carico il prezziario…", max_entries=4)
def _righe(pid, agg):
    return pz.carica_righe(pid)


@st.cache_data(show_spinner=False, max_entries=4)
def _df(pid, agg):
    return pz.prepara(_righe(pid, agg))


def attivo():
    """(meta, righe) del prezziario in vigore, oppure (None, None) se non ce n'e' nessuno."""
    try:
        m = pz.corrente(pz.carica_indice())
        if not m:
            return None, None
        return m, _righe(m["id"], pz.aggiornato_il(m["id"]))
    except Exception:
        return None, None


def prezzi_attivi():
    """Indice codice -> prezzi per il controllo degli ordini ({} se non c'e' un prezziario)."""
    m, righe = attivo()
    return pz.indice_prezzi(righe) if righe else {}


def periodo_da_nome(nome):
    """('2026', 2) da un nome file tipo «Listino_CCAA_2_quadrimestre_2026.xlsx», altrimenti None."""
    s = str(nome or "").replace("_", " ").replace("-", " ")
    m = re.search(r"(\d)\s*[°ºa]?\s*quadrimestre\D{0,4}(20\d{2})", s, re.I)
    if m and m.group(1) in "123":
        return int(m.group(2)), int(m.group(1))
    return None


def _quad_oggi(oggi=None):
    oggi = oggi or dt.date.today()
    return oggi.year, 1 if oggi.month <= 4 else (2 if oggi.month <= 8 else 3)


# ----------------------------------------------------------------------------
# SELETTORE PER IL COMPUTO (usato dentro Computo e Preventivo)
# ----------------------------------------------------------------------------
def scegli_voci(chiave, sg_pct, utile_pct):
    """Cerca nel prezziario in vigore e restituisce le voci scelte (righe per il Computo) quando si preme «Aggiungi», altrimenti None."""
    m, righe = attivo()
    if not righe:
        st.caption("Non c'è ancora un prezziario: caricalo dallo strumento «Prezziario» (scheda 2).")
        return None
    df = _df(m["id"], pz.aggiornato_il(m["id"]))
    st.caption(f"Prezziario in uso: **{m['periodo']}** ({m.get('nome', '')}). Cerca una voce, selezionala e inserisci la quantità: codice, unità e prezzo arrivano da soli.")
    c1, c2 = st.columns([3, 1])
    q = c1.text_input("Cerca (parole o inizio del codice)", key=chiave + "_q", placeholder="es. intonaco, serramento alluminio, B.06.04")
    sg = c2.selectbox("Capitolo", ["(tutti)"] + list(pz.capitoli(df).keys()), key=chiave + "_cap")
    ris = pz.cerca(df, q, "" if sg == "(tutti)" else sg, limite=60)
    if not q and sg == "(tutti)":
        st.info("Scrivi cosa cerchi o scegli un capitolo.")
        return None
    st.caption(f"{len(ris)} voci" + (" (mostro le prime 60: restringi la ricerca)" if len(ris) >= 60 else ""))
    mostra = pd.DataFrame({"Codice": ris["codice"], "Descrizione": ris["descrizione"], "UM": ris["um"], "Prezzo €": ris["prezzo"]})
    ev = st.dataframe(mostra, hide_index=True, width="stretch", height=240, on_select="rerun", selection_mode="multi-row", key=chiave + "_t",
                      column_config={"Descrizione": st.column_config.TextColumn(width="large"), "Prezzo €": st.column_config.NumberColumn(format="%.2f")})
    scelte = list(ev.selection.rows) if ev and ev.selection else []
    a, b = st.columns(2)
    qta = a.number_input("Quantità (per tutte le voci scelte)", min_value=0.0, value=1.0, step=1.0, key=chiave + "_qta")
    come = b.radio("Il prezzo del prezziario è…", ["prezzo", "costo"], key=chiave + "_come", horizontal=True,
                   format_func=lambda x: {"prezzo": "un prezzo (tolgo spese generali e utile)", "costo": "già un costo diretto"}[x])
    if come == "prezzo":
        st.caption(f"Costo = prezzo ÷ (1 + {sg_pct:g}% spese generali) ÷ (1 + {utile_pct:g}% utile): il preventivo poi li rimette, senza contarli due volte.")
    if st.button(f"➕ Aggiungi {len(scelte)} voci al computo" if scelte else "➕ Aggiungi al computo", key=chiave + "_ok", disabled=not scelte or sola_lettura(), type="primary"):
        base = ris.iloc[scelte].to_dict("records")
        return [pz.voce_per_computo(r, qta, come, sg_pct, utile_pct) for r in base]
    return None


# ----------------------------------------------------------------------------
# STRUMENTO
# ----------------------------------------------------------------------------
def _scheda_cerca(indice):
    if not indice:
        st.info("Non c'è ancora nessun prezziario. Carica il file Excel nella scheda «2. Carica un prezziario».")
        return
    ordinati = sorted(indice.values(), key=lambda x: (x["anno"], x["quad"]), reverse=True)
    corr = pz.corrente(indice)
    ids = [x["id"] for x in ordinati]
    pid = st.selectbox("Prezziario", ids, index=ids.index(corr["id"]) if corr and corr["id"] in ids else 0, key="selez_listino",
                       format_func=lambda i: f"{indice[i]['periodo']} · {indice[i].get('nome', '')} · {indice[i]['n_voci']} voci") if len(ids) > 1 else ids[0]
    meta = indice[pid]
    df = _df(pid, pz.aggiornato_il(pid))
    cap = pz.capitoli(df)
    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
    q = c1.text_input("Cerca per parola o per codice", key="cerca_testo", placeholder="es. piastrelle bicottura · intonaco · C.05.01 · serramento alluminio")
    sg = c2.selectbox("Capitolo", ["(tutti)"] + list(cap.keys()), key="cerca_cap")
    gruppi = cap.get(sg, []) if sg != "(tutti)" else []
    gr = c3.selectbox("Gruppo", ["(tutti)"] + gruppi, key="cerca_gr", disabled=not gruppi)
    ums = sorted(u for u in df["um"].unique() if u)
    um = c4.selectbox("Unità", ["(tutte)"] + ums, key="cerca_um")
    ris = pz.cerca(df, q, "" if sg == "(tutti)" else sg, "" if gr == "(tutti)" else gr, "" if um == "(tutte)" else um, limite=100000)
    tot = len(ris)
    if not q and sg == "(tutti)" and um == "(tutte)":
        st.caption(f"Il prezziario ha {meta['n_voci']} voci. Scrivi una parola o scegli un capitolo per restringere.")
    st.markdown(f"**{tot} voci trovate**" + (f" · mostro le prime {LIMITE_TABELLA}: restringi la ricerca per vedere le altre" if tot > LIMITE_TABELLA else ""))
    vis = ris.head(LIMITE_TABELLA)
    tab = pd.DataFrame({"Codice": vis["codice"], "Descrizione": vis["descrizione"], "UM": vis["um"], "Prezzo €": vis["prezzo"], "Capitolo": vis["supergruppo"]})
    ev = st.dataframe(tab, hide_index=True, width="stretch", height=380, on_select="rerun", selection_mode="single-row", key="tabella_listino",
                      column_config={"Descrizione": st.column_config.TextColumn(width="large"), "Prezzo €": st.column_config.NumberColumn(format="%.2f")})
    sel = list(ev.selection.rows) if ev and ev.selection else []
    if sel:
        r = vis.iloc[sel[0]]
        st.markdown(f"#### {r['codice']}")
        st.markdown(f"{r['descrizione']}")
        a, b, c = st.columns(3)
        a.metric("Prezzo di riferimento", f"{fmt_num(r['prezzo'])} €", help=f"per {r['um'] or 'unità non indicata'}")
        b.metric("Unità", r["um"] or "—")
        c.metric("Periodo", meta["periodo"])
        st.caption(" › ".join(x for x in (r["supergruppo"], r["gruppo"], r["sottogruppo"]) if x))
        varianti = df[(df["codice"] == r["codice"])]
        if len(varianti) > 1:
            st.info(f"Questo codice ha {len(varianti)} varianti con prezzi diversi:")
            st.dataframe(pd.DataFrame({"Chiave": varianti["chiave"], "Descrizione": varianti["descrizione"], "UM": varianti["um"], "Prezzo €": varianti["prezzo"]}), hide_index=True, width="stretch")
        if meta.get("comprende_sg_utile") == "no":
            st.caption("Questi sono costi diretti: spese generali e utile vanno aggiunti nel preventivo.")
    st.caption("I prezzi sono di riferimento (listino della Camera di Commercio): non sono offerte di fornitori. Per gli acquisti chiedi sempre il prezzo al fornitore e usa questo come confronto.")
    if tot:
        st.download_button("📥 Scarica questi risultati in Excel", pz.excel_bytes(ris.head(5000)), file_name=f"prezziario_{pid}.xlsx", key="dl_listino",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _scheda_carica(indice, audit, utente):
    if sola_lettura():
        st.info("Con il ruolo «lettore» puoi consultare il prezziario ma non caricarne uno nuovo.")
    up = st.file_uploader("Carica il prezziario (Excel o CSV con colonne Codice, Descrizione, Unità di misura, Prezzo…)", type=["xlsx", "csv"], key="up_listino", disabled=sola_lettura())
    if up is not None and ss.get("_pz_nome") != up.name:
        ss["_pz_nome"] = up.name
        ss.pop("_pz_bozza", None)
    if up is not None:
        rilevato = periodo_da_nome(up.name) or _quad_oggi()
        sfx = re.sub(r"\W", "", up.name)[:30]                                  # chiavi diverse per file diversi: i valori rilevati si aggiornano
        c1, c2, c3 = st.columns([1, 1, 2])
        anno = c1.number_input("Anno", min_value=2000, max_value=2100, value=rilevato[0], step=1, key=f"listino_anno_{sfx}")
        quad = c2.selectbox("Quadrimestre", [1, 2, 3], index=rilevato[1] - 1, key=f"listino_quad_{sfx}", format_func=lambda x: f"{x}° (" + ["gen-apr", "mag-ago", "set-dic"][x - 1] + ")")
        nome = c3.text_input("Fonte", "Listino prezzi CCIAA Milano Monza Brianza Lodi", key=f"listino_nome_{sfx}")
        sgu = st.radio("I prezzi comprendono spese generali e utile d'impresa?", ["sì", "no", "non lo so"], horizontal=True, key=f"listino_sgu_{sfx}",
                       help="Se sono prezzi di opera compiuta (con spese generali e utile) il Computo ne ricava il costo diretto. Chiedilo all'area tecnica.")
        if st.button("🔍 Leggi il file", key="leggi_listino"):
            try:
                df = pd.read_csv(up, sep=None, engine="python", dtype=str) if up.name.lower().endswith(".csv") else pd.read_excel(up, dtype=str)
                righe, rap = pz.da_dataframe(df)
                if not righe:
                    st.error("Nel file non ho trovato nessuna voce con un prezzo.")
                else:
                    ss["_pz_bozza"] = {"righe": righe, "rap": rap}
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"File non leggibile: {e}")
        b = ss.get("_pz_bozza")
        if b:
            rap = b["rap"]
            st.success(f"Lette **{rap['voci']}** voci su {rap['righe_file']} righe del file.")
            a1, a2, a3, a4 = st.columns(4)
            a1.metric("Voci con prezzo", rap["voci"])
            a2.metric("Intestazioni saltate", rap["intestazioni"])
            a3.metric("Avvertenze saltate", rap["avvertenze"])
            a4.metric("Caratteri ripuliti", rap["caratteri_puliti"], help="Sequenze come &apos; sostituite con l'apostrofo.")
            for x in pz.avvisi_rapporto(rap):
                st.warning(x)
            st.dataframe(pd.DataFrame(b["righe"][:15])[["codice", "descrizione", "um", "prezzo", "supergruppo"]], hide_index=True, width="stretch")
            pid = pz.id_prezziario(anno, quad)
            if pid in indice:
                st.warning(f"Esiste già il {pz.periodo(anno, quad)} ({indice[pid]['n_voci']} voci): salvando lo sostituisci.")
            if st.button(f"💾 Salva il {pz.periodo(anno, quad)}", key="salva_listino", type="primary", disabled=sola_lettura()):
                try:
                    meta = pz.salva_prezziario({"anno": anno, "quad": quad, "nome": nome.strip(), "comprende_sg_utile": {"sì": "si", "no": "no"}.get(sgu, ""), "avvisi": pz.avvisi_rapporto(rap)},
                                               b["righe"], autore=utente)
                    audit("pz_salvato", f"{meta['periodo']} · {meta['n_voci']} voci")
                    ss.pop("_pz_bozza", None)
                    st.cache_data.clear()
                    st.success(f"Salvato: {meta['periodo']}, valido dal {dt.date.fromisoformat(meta['valido_da']).strftime('%d/%m/%Y')} al {dt.date.fromisoformat(meta['valido_a']).strftime('%d/%m/%Y')}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Salvataggio non riuscito: {e}")
    if indice:
        st.markdown("**Prezziari caricati**")
        for m in sorted(indice.values(), key=lambda x: (x["anno"], x["quad"]), reverse=True):
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"**{m['periodo']}** · {m.get('nome', '')} · {m['n_voci']} voci · valido dal {dt.date.fromisoformat(m['valido_da']).strftime('%d/%m/%Y')} al "
                        f"{dt.date.fromisoformat(m['valido_a']).strftime('%d/%m/%Y')} · caricato il {m['caricato']} da {m.get('autore', '')}")
            if (ss.get("utente") or {}).get("ruolo") == "admin" and c2.button("🗑️ Elimina", key="elimina_" + m["id"]):
                pz.elimina_prezziario(m["id"], autore=(ss.get("utente") or {}).get("username", ""))
                audit("pz_eliminato", m["periodo"])
                st.cache_data.clear()
                st.rerun()


def _scheda_confronta(indice):
    if len(indice) < 2:
        st.info("Per confrontare servono almeno due prezziari (per esempio il 2° e il 3° quadrimestre). Quando arriva il nuovo listino, caricalo nella scheda 2 e torna qui.")
        return
    ordinati = sorted(indice.values(), key=lambda x: (x["anno"], x["quad"]))
    ids = [x["id"] for x in ordinati]
    etich = lambda i: f"{indice[i]['periodo']}"
    c1, c2 = st.columns(2)
    prima = c1.selectbox("Prima", ids, index=len(ids) - 2, format_func=etich, key="conf_prima")
    dopo = c2.selectbox("Dopo", ids, index=len(ids) - 1, format_func=etich, key="conf_dopo")
    if prima == dopo:
        st.warning("Scegli due prezziari diversi.")
        return
    cf = pz.confronta(_righe(prima, pz.aggiornato_il(prima)), _righe(dopo, pz.aggiornato_il(dopo)))
    st.markdown(theme.stat_strip([
        {"label": "Variazione media", "value": f"{cf['media_pct']:+.1f}%", "sub": "sulle voci cambiate", "tono": "warn" if cf["media_pct"] > 3 else "info"},
        {"label": "Prezzi aumentati", "value": str(cf["aumenti"]), "sub": f"{cf['riduzioni']} diminuiti", "tono": "warn" if cf["aumenti"] > cf["riduzioni"] else "ok"},
        {"label": "Invariati", "value": str(cf["invariate"]), "sub": "", "tono": "info"},
        {"label": "Voci nuove / tolte", "value": f"{len(cf['nuove'])} / {len(cf['eliminate'])}", "sub": "", "tono": "info"}]), unsafe_allow_html=True)
    if cf["per_capitolo"]:
        st.markdown("**Dove sono cambiati di più i prezzi (media per capitolo)**")
        st.dataframe(pd.DataFrame([{"Capitolo": x["capitolo"], "Voci cambiate": x["voci"], "Variazione media %": x["media_pct"]} for x in cf["per_capitolo"][:15]]), hide_index=True, width="stretch")
    if cf["variate"]:
        st.markdown(f"**Le variazioni più forti** (prime {min(len(cf['variate']), LIMITE_TABELLA)} su {len(cf['variate'])})")
        tab = pd.DataFrame([{"Codice": x["codice"], "Descrizione": x["descrizione"], "UM": x["um"], "Prima €": x["prezzo_prima"], "Ora €": x["prezzo_ora"], "Var. %": x["variazione_pct"]} for x in cf["variate"][:LIMITE_TABELLA]])
        st.dataframe(tab, hide_index=True, width="stretch", height=360, column_config={"Descrizione": st.column_config.TextColumn(width="large"), "Var. %": st.column_config.NumberColumn(format="%+.1f")})
        import io
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            pd.DataFrame(cf["variate"]).to_excel(w, index=False, sheet_name="Variazioni")
            pd.DataFrame(cf["nuove"]).to_excel(w, index=False, sheet_name="Voci nuove")
            pd.DataFrame(cf["eliminate"]).to_excel(w, index=False, sheet_name="Voci tolte")
        st.download_button("📥 Scarica il confronto in Excel", buf.getvalue(), file_name=f"confronto_{prima}_{dopo}.xlsx", key="dl_confronto",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption("Le voci si confrontano per codice (e per variante se lo stesso codice compare più volte). Un codice con unità di misura diversa conviene guardarlo a mano.")


def render(fcr_uri, audit=None, utente=""):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Prezziario", "I prezzi di riferimento per preventivi e acquisti: cercali, usali nel Computo e controlla gli ordini."), unsafe_allow_html=True)
    guida.mostra("pz")
    if ss.get("_pz_prefill"):                                   # arrivo dalla ricerca dell'Hub: la parola cercata passa alla ricerca del prezziario
        ss["cerca_testo"] = ss.pop("_pz_prefill")
    indice = pz.carica_indice()
    s = pz.stato_validita(indice)
    if s["stato"] == "nd":
        st.warning("Nessun prezziario caricato.")
    elif s["stato"] == "ok":
        st.success("📚 " + s["testo"])
    else:
        st.warning("⚠️ " + s["testo"] + ". Quando arriva il nuovo listino caricalo nella scheda 2.")
    t1, t2, t3 = st.tabs(["🔎 1. Cerca", "📥 2. Carica un prezziario", "🔄 3. Confronta quadrimestri"])
    with t1:
        _scheda_cerca(indice)
    with t2:
        _scheda_carica(indice, audit, utente)
    with t3:
        _scheda_confronta(indice)
