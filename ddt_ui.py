"""ddt_ui.py - Scheda «Bolle (DDT)» dei Materiali: carica PDF, foto ed Excel, cerca nell'archivio, controlla cosa manca."""
import datetime as dt
import hashlib

import pandas as pd
import streamlit as st

import ddt
import mt
from sc import data_da
from ui_util import sola_lettura, sostituisci_tabella

ss = st.session_state
PAGINA = 20


def _puo_eliminare(meta, utente):
    u = ss.get("utente") or {}
    return u.get("ruolo") == "admin" or (meta.get("caricato_da") and meta["caricato_da"] == utente)


def _kb(n):
    return f"{n / 1024:.0f} KB" if n < 1048576 else f"{n / 1048576:.1f} MB"


def _data_it(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso and len(iso) >= 10 else ""


def _etichetta(m):
    return f"{('DDT ' + m['ddt_numero']) if m['ddt_numero'] else 'senza numero'} · {m['fornitore'] or 'fornitore n.d.'} · {m['nome_file']}"


def _commesse():
    return sorted({str(x).strip() for x in ss["mt_ord"].get("Commessa", []) if str(x).strip() and str(x) != "nan"}) if len(ss["mt_ord"]) else []


def _suggerimenti(nome, dati):
    chiave = ("ddt_sugg", hashlib.sha1(dati[:4096] + str(len(dati)).encode()).hexdigest())
    if chiave not in ss:
        try:
            ss[chiave] = ddt.proponi(nome, dati)
        except Exception:
            ss[chiave] = {"numero": "", "data": "", "fornitore": ""}
    return ss[chiave]


def _aggiungi_righe(righe, utente, audit, sorgente):
    esist = ss["mt_ord"].to_dict("records") if len(ss["mt_ord"]) else []
    nuove, doppie = ddt.righe_nuove(esist, righe)
    if nuove:
        base = ss["mt_ord"] if len(ss["mt_ord"]) else pd.DataFrame(columns=mt.COLONNE_ORDINI)
        sostituisci_tabella("mt_ord", pd.concat([base, pd.DataFrame(nuove, columns=mt.COLONNE_ORDINI)], ignore_index=True))
        ss["mt_demo"] = False
        audit("ddt_excel_importato", f"{len(nuove)} righe da {sorgente}")
    return len(nuove), doppie


# ----------------------------------------------------------------------------
def _carica(utente, audit):
    if sola_lettura():
        st.info("Il tuo profilo è in sola lettura: puoi consultare e scaricare le bolle, ma non caricarne.")
        return
    st.caption(f"Carica una o più bolle: **PDF, foto (JPG, PNG) o Excel**, fino a {ddt.MAX_BYTES // 1048576} MB ciascuna. "
               "La suite prova a leggere numero e data dal PDF o dal nome del file: **controlla sempre** quello che propone.")
    n = ss.setdefault("ddt_up_n", 0)
    files = st.file_uploader("Scegli i file (puoi trascinarne più di uno, o scattare la foto dal telefono)", type=ddt.TIPI_UPLOAD, accept_multiple_files=True, key=f"ddt_up_{n}")
    if not files:
        return
    commesse = _commesse()
    pronti = []
    for f in files:
        dati = f.getvalue()
        sha = hashlib.sha1(dati[:4096] + str(len(dati)).encode() + f.name.encode()).hexdigest()[:10]
        tipo = ddt.riconosci(dati)
        with st.container(border=True):
            st.markdown(f"**{f.name}** · {_kb(len(dati))}" + (f" · {tipo.upper()}" if tipo else ""))
            if tipo is None:
                st.error("Formato non riconosciuto: questo file non verrà caricato.")
                continue
            sug = _suggerimenti(f.name, dati)
            c1, c2, c3, c4 = st.columns([1, 1, 1.4, 1.4])
            numero = c1.text_input("N. DDT", value=sug["numero"], key=f"ddt_n_{sha}")
            data = c2.text_input("Data (GG/MM/AAAA)", value=_data_it(sug["data"]), key=f"ddt_d_{sha}")
            forn = c3.text_input("Fornitore", value=sug["fornitore"], key=f"ddt_f_{sha}")
            comm = c4.selectbox("Commessa", [""] + commesse, key=f"ddt_c_{sha}", accept_new_options=True) if commesse else c4.text_input("Commessa", key=f"ddt_c_{sha}")
            if sug["numero"] or sug["data"]:
                st.caption("🔎 Numero e data letti dal file: verifica che siano giusti.")
            elif tipo in ("jpg", "png"):
                st.caption("Le foto non si leggono in automatico: scrivi tu numero e data.")
            if tipo in ("xlsx", "xls"):
                try:
                    righe, av, _ = ddt.leggi_excel(dati, f.name)
                    for r in righe:
                        r["Ddt"] = r["Ddt"] or ddt.normalizza_numero(numero)
                        r["Fornitore"] = r["Fornitore"] or forn
                        r["Commessa"] = r["Commessa"] or (comm or "")
                        r["Data_consegna"] = r["Data_consegna"] or (data_da(data).isoformat() if data_da(data) else "")
                    st.markdown(f"**📊 {len(righe)} righe lette dall'Excel**" + (f" ({len(av)} da controllare)" if av else ""))
                    if righe:
                        st.dataframe(pd.DataFrame(righe)[["Materiale", "Quantita", "Um", "Prezzo_unit", "Fornitore", "Commessa", "Ddt", "Data_consegna"]].rename(columns={"Quantita": "Quantità", "Prezzo_unit": "Prezzo", "Ddt": "N. DDT", "Data_consegna": "Data"}), hide_index=True, width="stretch", height=min(300, 60 + 35 * len(righe)))
                    for x in av[:5]:
                        st.caption("⚠️ " + x)
                    if righe and st.button(f"➕ Aggiungi queste {len(righe)} righe agli Ordini e consegne", key=f"ddt_imp_{sha}"):
                        a, d = _aggiungi_righe(righe, utente, audit, f.name)
                        st.success(f"Aggiunte {a} righe" + (f" ({d} già presenti, saltate)" if d else "") + ". Per tenerle, salva con «Salva e riapri» in alto." if a else f"Nessuna riga aggiunta: erano già tutte presenti ({d}).")
                except ddt.DdtErrore as e:
                    st.warning(str(e) + " Puoi comunque archiviare il file.")
            pronti.append((f.name, dati, numero, data, forn, comm))
    if pronti and st.button(f"💾 Archivia {len(pronti)} file", type="primary", key="ddt_salva"):
        ok, avvisi = 0, []
        for nome, dati, numero, data, forn, comm in pronti:
            d = data_da(data)
            if data.strip() and d is None:
                avvisi.append(f"{nome}: la data «{data}» non è valida: scrivila come GG/MM/AAAA.")
                continue
            try:
                ddt.salva(nome, dati, numero, d.isoformat() if d else "", forn, comm or "", utente=utente)
                ok += 1
                audit("ddt_caricato", f"{nome} · DDT {ddt.normalizza_numero(numero) or 'senza numero'}")
            except ddt.DdtDoppio as e:
                avvisi.append(f"{nome}: {e}")
            except ddt.DdtErrore as e:
                avvisi.append(f"{nome}: {e}")
            except Exception:
                avvisi.append(f"{nome}: errore imprevisto durante il salvataggio, riprova.")
        for a in avvisi:
            st.warning(a)
        if ok:
            st.success(f"Archiviati {ok} file.")
            if not avvisi:
                ss["ddt_up_n"] = n + 1
                ss["ddt_msg"] = f"Archiviati {ok} file."
                st.rerun()


def _archivio(utente, audit):
    c1, c2, c3 = st.columns([2, 1, 1])
    testo = c1.text_input("Cerca (numero, fornitore, commessa, nome file)", key="ddt_cerca")
    filtra_data = c2.checkbox("Filtra per data", key="ddt_fdata")
    solo = c3.checkbox("Solo senza numero", key="ddt_solo")
    da = a = None
    if filtra_data:
        d1, d2 = st.columns(2)
        da, a = d1.date_input("Dal", value=dt.date.today() - dt.timedelta(days=30), key="ddt_da"), d2.date_input("Al", value=dt.date.today(), key="ddt_a")
    tot = ddt.conta(testo, da, a, solo)
    pagine = max(1, -(-tot // PAGINA))
    pag = int(st.number_input(f"Pagina (di {pagine})", 1, pagine, 1, key="ddt_pag")) if pagine > 1 else 1
    righe = ddt.elenca(testo, da, a, solo, PAGINA, (pag - 1) * PAGINA)
    st.caption(f"{tot} bolle trovate" + (f" · mostro la pagina {pag} di {pagine}" if pagine > 1 else ""))
    if not righe:
        st.info("Nessuna bolla trovata." if (testo or filtra_data or solo) else "Non c'è ancora nessuna bolla archiviata: caricale dalla scheda «Carica».")
        return
    st.dataframe(pd.DataFrame([{"Data": _data_it(r["ddt_data"]) or _data_it(r["creato"][:10]), "N. DDT": r["ddt_numero"], "Fornitore": r["fornitore"], "Commessa": r["commessa"],
                                "File": r["nome_file"], "Dimensione": _kb(r["dimensione"]), "Caricata da": r["caricato_da"]} for r in righe]), hide_index=True, width="stretch")
    idx = st.selectbox("Apri una bolla", range(len(righe)), format_func=lambda i: _etichetta(righe[i]), key="ddt_sel", index=None, placeholder="Scegli una bolla per scaricarla o correggerla")
    if idx is None:
        return
    m = righe[idx]
    letto = ddt.leggi(m["id"])
    if not letto:
        st.warning("Questa bolla non c'è più (qualcuno l'ha eliminata).")
        return
    meta, dati = letto
    with st.container(border=True):
        st.download_button(f"⬇️ Scarica {meta['nome_file']} ({_kb(meta['dimensione'])})", dati, file_name=meta["nome_file"], mime=meta["mime"], key=f"ddt_dl_{meta['id']}")
        if meta["mime"] == "image/jpeg":
            st.image(dati, width=420)
        elif meta["mime"] == "application/pdf":
            st.caption("Il PDF si apre con il pulsante «Scarica».")
        if not sola_lettura():
            with st.form(f"ddt_mod_{meta['id']}"):
                f1, f2, f3, f4 = st.columns([1, 1, 1.4, 1.4])
                n = f1.text_input("N. DDT", meta["ddt_numero"])
                d = f2.text_input("Data (GG/MM/AAAA)", _data_it(meta["ddt_data"]))
                fo = f3.text_input("Fornitore", meta["fornitore"])
                co = f4.text_input("Commessa", meta["commessa"])
                note = st.text_input("Note", meta["note"])
                if st.form_submit_button("Salva le correzioni"):
                    dd = data_da(d)
                    if d.strip() and dd is None:
                        st.error("Data non valida: scrivila come GG/MM/AAAA.")
                    else:
                        ddt.aggiorna(meta["id"], n, dd.isoformat() if dd else "", fo, co, note)
                        audit("ddt_modificato", f"{meta['nome_file']} · DDT {ddt.normalizza_numero(n) or 'senza numero'}")
                        st.success("Salvato.")
                        st.rerun()
            if _puo_eliminare(meta, utente):
                conf = st.checkbox("Sì, voglio eliminare questa bolla (non si può annullare)", key=f"ddt_conf_{meta['id']}")
                if st.button("🗑️ Elimina", key=f"ddt_del_{meta['id']}", disabled=not conf):
                    ddt.elimina(meta["id"])
                    audit("ddt_eliminato", f"{meta['nome_file']} · DDT {meta['ddt_numero'] or 'senza numero'}")
                    ss.pop("ddt_sel", None)
                    st.rerun()
            else:
                st.caption("Può eliminarla solo chi l'ha caricata o un amministratore.")


def _controlli(utente, audit):
    c = ddt.controlli(ss["mt_ord"].to_dict("records") if len(ss["mt_ord"]) else [])
    n, b = ddt.spazio()
    st.metric("Bolle archiviate", f"{n}")
    st.caption(f"Spazio occupato: {_kb(b)}")
    if b > ddt.AVVISO_SPAZIO_MB * 1048576:
        st.warning(f"Le bolle occupano {_kb(b)} del database. Se usi un database con spazio limitato, valuta di spostare gli archivi più vecchi o di passare al server aziendale.")
    if not (c["senza_file"] or c["senza_numero"] or c["file_orfani"]):
        st.success("Tutto in ordine: ogni consegna ha il numero DDT e il suo file, e ogni file è collegato a una consegna.")
    if c["senza_numero"]:
        st.error(f"**{len(c['senza_numero'])} consegne senza numero DDT**")
        st.dataframe(pd.DataFrame(c["senza_numero"])[["Materiale", "Fornitore", "Commessa", "Quantita", "Data_consegna"]].rename(columns={"Quantita": "Quantità", "Data_consegna": "Data consegna"}), hide_index=True, width="stretch")
    if c["senza_file"]:
        st.warning(f"**{len(c['senza_file'])} consegne con il numero DDT ma senza il file della bolla**")
        st.dataframe(pd.DataFrame(c["senza_file"])[["Materiale", "Fornitore", "Commessa", "Ddt", "Data_consegna"]].rename(columns={"Ddt": "N. DDT", "Data_consegna": "Data consegna"}), hide_index=True, width="stretch")
    if c["file_orfani"]:
        st.info(f"**{len(c['file_orfani'])} file il cui numero non compare in nessuna consegna** (forse la consegna non è ancora stata inserita)")
        st.dataframe(pd.DataFrame([{"N. DDT": f["ddt_numero"], "Fornitore": f["fornitore"], "Commessa": f["commessa"], "File": f["nome_file"]} for f in c["file_orfani"]]), hide_index=True, width="stretch")
    if c["senza_numero"] and not sola_lettura():
        st.markdown("**Collega un numero DDT a una consegna**")
        idx_righe = [i for i, r in ss["mt_ord"].iterrows() if str(r.get("Consegnato")) == "sì" and not ddt.normalizza_numero(r.get("Ddt"))]
        if idx_righe:
            a, b2 = st.columns(2)
            ri = a.selectbox("Consegna", idx_righe, format_func=lambda i: f"{ss['mt_ord'].loc[i, 'Materiale']} · {ss['mt_ord'].loc[i, 'Fornitore'] or 'n.d.'} · {ss['mt_ord'].loc[i, 'Commessa'] or 'n.d.'}", key="ddt_lk_r")
            cand = sorted(ddt.numeri_con_file())
            num = b2.selectbox("Numero DDT", cand, key="ddt_lk_n", accept_new_options=True) if cand else b2.text_input("Numero DDT", key="ddt_lk_n")
            if st.button("🔗 Collega", key="ddt_lk_ok", disabled=not num):
                df = ss["mt_ord"].copy()
                df.loc[ri, "Ddt"] = ddt.normalizza_numero(num)
                sostituisci_tabella("mt_ord", df)
                audit("ddt_collegato", f"{df.loc[ri, 'Materiale']} → DDT {num}")
                st.success("Collegato. Salva con «Salva e riapri» per tenerlo.")
                st.rerun()


def render(out, dati, utente, audit):
    st.markdown("### 📎 Bolle (DDT)")
    if ss.get("ddt_msg"):
        st.success(ss.pop("ddt_msg"))
    sez = st.radio("Sezione", ["📤 Carica", "🗂️ Archivio", "✅ Controlli"], horizontal=True, label_visibility="collapsed", key="ddt_sez")
    if sez.endswith("Carica"):
        _carica(utente, audit)
    elif sez.endswith("Archivio"):
        _archivio(utente, audit)
    else:
        _controlli(utente, audit)
