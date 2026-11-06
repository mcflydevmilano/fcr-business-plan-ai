"""fp_ui.py - Interfaccia di Ferie e permessi."""
import datetime as dt
import io

import pandas as pd
import streamlit as st

import fp
import guida
import richieste
import storage
import theme
from ui_util import sola_lettura

ss = st.session_state
ICONE = {"In attesa": "🟡", "Approvata": "🟢", "Respinta": "🔴", "Annullata": "⚪"}
MESI = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]


def _personale(cfg, utenti_secrets):
    if cfg["personale"]:
        return list(cfg["personale"])
    n = set((utenti_secrets or {}).keys())
    try:
        n |= {u["username"] for u in storage.elenca_utenti() if u["attivo"]}
    except Exception:
        pass
    n.discard("admin") if len(n) > 1 else None
    return sorted(n, key=str.lower)


def _testo(r):
    d = r["dati"]
    dal, al = fp._d(d["dal"]), fp._d(d["al"])
    quando = f"{dal:%d/%m/%Y}" if dal == al else f"dal {dal:%d/%m/%Y} al {al:%d/%m/%Y}"
    extra = f", {d.get('ore')} ore" if d.get("tipo") == "Permesso (ore)" else ""
    return f"{d.get('tipo')} {quando}{extra}"


def _avviso_copertura(lista, dal, al, personale, cfg, chi, escludi_id=None):
    if cfg["minimo_presenti"] <= 0 or not personale:
        return
    buchi = fp.copertura(lista, dal, al, personale, cfg["minimo_presenti"], cfg["festivi_locali"], escludi_id, chi)
    if buchi:
        b = buchi[0]
        st.warning(f"⚠️ In {len(buchi)} giorn{'o' if len(buchi) == 1 else 'i'} del periodo resterebbero meno di {cfg['minimo_presenti']} presenti "
                   f"(il primo: {b['giorno']:%d/%m}, presenti {b['presenti']}; assenti: {', '.join(b['assenti'])}).")


def _chiedi(nome, ruolo, lista, cfg, personale, audit):
    oggi = dt.date.today()
    mie = [r for r in lista if r["utente"] == nome]
    rs = fp.residui(nome, oggi.year, lista, cfg)
    a, b, c, d = st.columns(4)
    a.metric("Ferie residue", f"{rs['ferie_residue']:g} giorni", f"su {rs['ferie_spettanti']:g}", delta_color="off")
    b.metric("Ferie già approvate", f"{rs['ferie_usate']:g} giorni")
    c.metric("Permessi residui", f"{rs['permessi_residui']:g} ore", f"su {rs['permessi_spettanti']:g}", delta_color="off")
    d.metric("In attesa di risposta", f"{rs['ferie_attesa']:g} gg · {rs['permessi_attesa']:g} h")
    msg = ss.pop("_fp_msg", None)
    if msg:
        st.success(msg[0])
        for w in msg[1]:
            st.warning(w)
    if sola_lettura():
        st.info("Con il ruolo «lettore» puoi consultare ma non fare richieste.")
    else:
        t = st.selectbox("Cosa chiedi", fp.TIPI, key="fp_n_tipo", help="La malattia è una comunicazione: indica il periodo e, appena puoi, porta o invia il certificato.")
        c1, c2, c3 = st.columns(3)
        dal = c1.date_input("Dal", value=oggi, format="DD/MM/YYYY", key="fp_n_dal")
        al = c2.date_input("Al (uguale al «Dal» se è un giorno solo)", value=oggi, format="DD/MM/YYYY", key="fp_n_al")
        ore = c3.number_input("Ore (solo per i permessi)", 0.0, 8.0, 0.0, 0.5, key="fp_n_ore")
        motivo = st.text_input("Motivo (facoltativo, obbligatorio per «Altro»)", key="fp_n_motivo")
        if dal and al and al >= dal and t != "Permesso (ore)":
            _gl = fp.giorni_lavorativi(dal, al, cfg['festivi_locali'])
            st.caption(f"Il periodo scelto ha {_gl} {'giorno lavorativo' if _gl == 1 else 'giorni lavorativi'} (sabato, domenica e festivi non contano).")
            _avviso_copertura(lista, dal, al, personale, cfg, nome)
        ok = st.button("📨 Invia la richiesta", type="primary", key="fp_invia")
        if ok:
            dati = {"tipo": t, "dal": str(dal), "al": str(al), "ore": ore if t == "Permesso (ore)" else 0, "motivo": motivo.strip()}
            err = fp.valida(dati, mie, cfg)
            if err:
                st.error(err)
            else:
                n = fp.giorni_richiesta(dati, cfg["festivi_locali"])
                stato = "Approvata" if t == "Malattia" else "In attesa"                       # la malattia si comunica, non si chiede
                rid = richieste.crea(fp.TIPO, nome, dati, stato=stato)
                audit("fp_richiesta", f"{t} {dal} {al}")
                avv = []
                if t == "Ferie" and n > rs["ferie_residue"]:
                    avv.append(f"Hai chiesto {n:g} giorni ma ne restano {rs['ferie_residue']:g}: l'approvatore lo vedrà.")
                if t != "Permesso (ore)" and cfg["minimo_presenti"] > 0 and fp.copertura(lista, dal, al, personale, cfg["minimo_presenti"], cfg["festivi_locali"], rid, nome):
                    avv.append(f"In alcuni giorni del periodo resterebbero meno di {cfg['minimo_presenti']} presenti: potrebbe servire un accordo con i colleghi.")
                ss["_fp_msg"] = ("Malattia registrata." if t == "Malattia" else "Richiesta inviata: la trovi qui sotto, in attesa di risposta.", avv)
                st.rerun()
    st.markdown("#### Le mie richieste")
    if not mie:
        st.caption("Nessuna richiesta.")
    for r in mie[:30]:
        x, y = st.columns([5, 1.3])
        x.markdown(f"{ICONE[r['stato']]} **{_testo(r)}** · {r['stato']}" + (f" · {r['deciso_da']}: {r['nota_decisione']}" if r["nota_decisione"] else (f" · da {r['deciso_da']}" if r["deciso_da"] else "")))
        if r["stato"] == "In attesa" and not sola_lettura() and y.button("Annulla", key=f"fp_ann_{r['id']}", width="stretch"):
            richieste.decidi(r["id"], "Annullata", nome, "annullata da chi l'ha chiesta")
            audit("fp_annullata", _testo(r))
            st.rerun()


def _da_approvare(nome, ruolo, profilo, lista, cfg, personale, audit):
    attesa = [r for r in lista if r["stato"] == "In attesa" and fp.puo_approvare(nome, ruolo, profilo, cfg, r["utente"])]
    if not attesa:
        st.success("Nessuna richiesta da approvare.")
        return
    for r in sorted(attesa, key=lambda r: r["dati"]["dal"]):
        d = r["dati"]
        with st.container(border=True):
            st.markdown(f"**{r['utente']}** · {_testo(r)}" + (f" — {d['motivo']}" if d.get("motivo") else ""))
            rs = fp.residui(r["utente"], fp._d(d["dal"]).year, lista, cfg)
            st.caption(f"Ferie residue (con questa richiesta già conteggiata): {rs['ferie_residue']:g} giorni · permessi residui: {rs['permessi_residui']:g} ore")
            if d.get("tipo") != "Permesso (ore)":
                _avviso_copertura(lista, fp._d(d["dal"]), fp._d(d["al"]), personale, cfg, None, r["id"])
                altri = [f"{p} ({t.lower()})" for g in (fp._d(d["dal"]),) for p, t in fp.assenti_il(lista, g, escludi_id=r["id"]).items() if p != r["utente"]]
                if altri:
                    st.caption("Lo stesso giorno mancano anche: " + ", ".join(altri))
            nota = st.text_input("Nota (obbligatoria se respingi)", key=f"fp_nota_{r['id']}")
            a, b = st.columns(2)
            if a.button("✅ Approva", key=f"fp_ok_{r['id']}", type="primary", width="stretch"):
                richieste.decidi(r["id"], "Approvata", nome, nota)
                audit("fp_approvata", f"{r['utente']} · {_testo(r)}")
                st.rerun()
            if b.button("⛔ Respingi", key=f"fp_no_{r['id']}", width="stretch", disabled=not nota.strip()):
                richieste.decidi(r["id"], "Respinta", nome, nota)
                audit("fp_respinta", f"{r['utente']} · {_testo(r)}")
                st.rerun()


def _chi_manca(lista, cfg, personale, gestore):
    oggi = dt.date.today()
    c1, c2 = st.columns(2)
    mese = c1.selectbox("Mese", range(1, 13), index=oggi.month - 1, format_func=lambda m: MESI[m - 1], key="fp_mese")
    anno = c2.selectbox("Anno", range(oggi.year + 1, oggi.year - 3, -1), index=1, key="fp_anno")
    righe = fp.matrice_mese(lista, anno, mese, personale, cfg["festivi_locali"])
    df = pd.DataFrame(righe)
    st.dataframe(df, hide_index=True, width="stretch")
    st.caption("F ferie · P permesso a ore · M malattia · A altro · ? in attesa di approvazione · · fine settimana o festivo")
    if gestore:
        res = pd.DataFrame([{"Persona": p, **{k: v for k, v in fp.residui(p, anno, lista, cfg).items()}} for p in personale]).rename(columns={
            "ferie_spettanti": "Ferie spettanti", "ferie_usate": "Ferie usate", "ferie_attesa": "Ferie in attesa", "ferie_residue": "Ferie residue",
            "permessi_spettanti": "Permessi spettanti (h)", "permessi_usati": "Permessi usati (h)", "permessi_attesa": "Permessi in attesa (h)", "permessi_residui": "Permessi residui (h)"})
        st.markdown(f"#### Giorni residui {anno}")
        st.dataframe(res, hide_index=True, width="stretch")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            res.to_excel(w, index=False, sheet_name="Residui")
            df.to_excel(w, index=False, sheet_name=f"{MESI[mese - 1]} {anno}")
            pd.DataFrame([{"Persona": r["utente"], "Richiesta": _testo(r), "Stato": r["stato"], "Deciso da": r["deciso_da"], "Nota": r["nota_decisione"], "Motivo": r["dati"].get("motivo", "")} for r in lista]).to_excel(w, index=False, sheet_name="Richieste")
        st.download_button("📥 Scarica in Excel", buf.getvalue(), file_name=f"ferie_{anno}.xlsx", key="fp_xls", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _regole(cfg, utente, audit, utenti_secrets):
    st.caption("Chi sono le persone da considerare, quante ferie hanno e quanti presenti devono restare almeno.")
    tutti = _personale({**cfg, "personale": []}, utenti_secrets)
    c1, c2, c3 = st.columns(3)
    gf = c1.number_input("Giorni di ferie all'anno", 0.0, 60.0, cfg["giorni_ferie"], 0.5, key="fp_r_gf")
    op = c2.number_input("Ore di permesso all'anno", 0.0, 300.0, cfg["ore_permesso"], 1.0, key="fp_r_op")
    mn = c3.number_input("Presenti minimi in ufficio", 0, 100, cfg["minimo_presenti"], 1, key="fp_r_min", help="Sotto questo numero, chi chiede e chi approva vede un avviso. 0 = nessun controllo.")
    pers = st.multiselect("Persone da considerare (vuoto = tutti gli utenti attivi)", sorted(set(tutti) | set(cfg["personale"])), default=cfg["personale"], key="fp_r_pers")
    appr = st.multiselect("Chi approva (vuoto = direzione e amministrazione)", sorted(set(tutti) | set(cfg["approvatori"])), default=cfg["approvatori"], key="fp_r_appr")
    fl = st.text_input("Festività locali (MM-GG separate da virgola)", ", ".join(cfg["festivi_locali"]), key="fp_r_fl", help="Il patrono della città: 12-07 per Milano (Sant'Ambrogio).")
    base = pd.DataFrame([{"Persona": p, "Giorni ferie": cfg["per_persona"].get(p, {}).get("giorni_ferie", gf), "Ore permesso": cfg["per_persona"].get(p, {}).get("ore_permesso", op)} for p in (pers or tutti)])
    st.markdown("**Spettanze diverse per persona** (modifica solo chi ha un contratto diverso)")
    ed = st.data_editor(base, hide_index=True, width="stretch", disabled=["Persona"], key="fp_r_pp")
    if st.button("💾 Salva le regole", type="primary", key="fp_r_salva", disabled=sola_lettura()):
        pp = {r["Persona"]: {"giorni_ferie": float(r["Giorni ferie"]), "ore_permesso": float(r["Ore permesso"])} for r in ed.to_dict("records") if (float(r["Giorni ferie"]), float(r["Ore permesso"])) != (gf, op)}
        fp.salva_cfg({"giorni_ferie": gf, "ore_permesso": op, "minimo_presenti": mn, "personale": pers, "approvatori": appr, "per_persona": pp,
                      "festivi_locali": [x.strip() for x in fl.replace(";", ",").split(",") if x.strip()]}, utente["username"])
        audit("fp_regole", f"{gf:g} gg, minimo {mn}")
        st.success("Regole salvate.")
        st.rerun()


def render(fcr_uri, audit, utente, profilo, utenti_secrets=None):
    audit = audit or (lambda *a, **k: None)
    nome, ruolo = utente["username"], utente.get("ruolo")
    st.markdown(theme.hero(fcr_uri, "Ferie e permessi", "Chiedi, approva e guarda chi manca: tutto in un posto."), unsafe_allow_html=True)
    guida.mostra("fp")
    cfg = fp.carica_cfg()
    personale = _personale(cfg, utenti_secrets)
    lista = richieste.elenca(fp.TIPO)
    gestore = ruolo == "admin" or profilo in ("presidente", "direzione", "amministrazione", "accesso completo")
    n_attesa = sum(1 for r in lista if r["stato"] == "In attesa" and fp.puo_approvare(nome, ruolo, profilo, cfg, r["utente"]))
    approva = ruolo == "admin" or n_attesa > 0 or fp.puo_approvare(nome, ruolo, profilo, cfg, "(altri)")
    nomi = ["✍️ Chiedi"] + ([f"✅ Da approvare{f' ({n_attesa})' if n_attesa else ''}"] if approva else []) + ["📅 Chi manca"] + (["⚙️ Regole"] if gestore else [])
    tabs = st.tabs(nomi)
    with tabs[0]:
        _chiedi(nome, ruolo, lista, cfg, personale, audit)
    i = 1
    if approva:
        with tabs[i]:
            _da_approvare(nome, ruolo, profilo, lista, cfg, personale, audit)
        i += 1
    with tabs[i]:
        _chi_manca(lista, cfg, personale, gestore)
    if gestore:
        with tabs[i + 1]:
            _regole(cfg, utente, audit, utenti_secrets)
