"""
dd.py - Cruscotto di direzione: riunisce margine, cassa, scoperto, crediti e rating dai moduli della suite e li traduce in semafori.

Funziona sui payload salvati (o sui dati di sessione) dei moduli: non rifa' calcoli propri, richiama i motori cf, sc, pv, bp e core.
Le soglie dei semafori sono ipotesi di lavoro modificabili (DD_DEFAULT), non standard di settore.
"""
import cf
import core
import pv
import sc
import sl
import ga
import fo
import sx
import mz
import og
import bp
from core import fmt_num

DD_DEFAULT = {
    "margine_target": 15.0,       # margine lordo % del portafoglio considerato "buono"
    "scaduto_warn": 10.0,         # % di crediti scaduti: giallo oltre questa soglia
    "scaduto_bad": 25.0,          # rosso oltre questa soglia
    "dscr_ok": 1.30, "dscr_warn": 1.00,
}
GRAVITA = {"nd": 0, "ok": 1, "warn": 2, "bad": 3}


def _riga(area, indicatore, valore, stato, nota=""):
    return {"Area": area, "Indicatore": indicatore, "Valore": valore, "Stato": stato, "Nota": nota}


# ----------------------------------------------------------------------------
# METRICHE DAI MODULI
# ----------------------------------------------------------------------------
def metriche_cf(payload):
    cantieri, _ = cf.normalizza_cantieri(payload.get("cantieri"))
    if not cantieri:
        return None
    out = cf.calcola_cf(cantieri, payload.get("params") or {})
    return {"kpi": out["kpi"], "avvisi": out["avvisi"]}


def metriche_sc(payload, oggi=None):
    docs, _ = sc.normalizza_documenti(payload.get("docs"))
    if not docs:
        return None
    p = dict(payload.get("params") or {})
    if oggi is not None:
        p["oggi"] = oggi
    out = sc.calcola_sc(docs, p)
    return {"kpi": out["kpi"], "avvisi": out["avvisi"], "solleciti": sc.solleciti(docs, out["params"]["oggi"])}


def metriche_sl(payload, oggi=None):
    com, _ = sl.normalizza_commesse(payload.get("commesse"))
    if not com:
        return None
    nomi = {c["Commessa"] for c in com}
    sal, _ = sl.normalizza_sal(payload.get("sal"), nomi)
    cos, _ = sl.normalizza_costi(payload.get("costi"), nomi)
    p = dict(payload.get("params") or {})
    if oggi is not None:
        p["oggi"] = oggi
    out = sl.calcola_sl(com, sal, cos, p)
    return {"kpi": out["kpi"], "avvisi": out["avvisi"], "commesse": out["commesse"]}


def metriche_ga(payload, oggi=None):
    gare, _ = ga.normalizza_gare(payload.get("gare"))
    if not gare:
        return None
    doc, _ = ga.normalizza_doc(payload.get("doc"), {g["Gara"] for g in gare})
    p = dict(payload.get("params") or {})
    if oggi is not None:
        p["oggi"] = oggi
    out = ga.calcola_ga(gare, doc, p)
    return {"kpi": out["kpi"], "avvisi": out["avvisi"]}


def metriche_fo(payload, oggi=None):
    docs, _ = fo.normalizza_docfo(payload.get("docs"))
    contr, _ = fo.normalizza_contratti(payload.get("contratti"))
    if not docs and not contr:
        return None
    p = dict(payload.get("params") or {})
    if oggi is not None:
        p["oggi"] = oggi
    out = fo.calcola_fo(docs, contr, [], p)
    return {"kpi": out["kpi"], "avvisi": out["avvisi"]}


def metriche_sx(payload, oggi=None):
    pers, _ = sx.normalizza_pers(payload.get("pers"))
    docc, _ = sx.normalizza_docc(payload.get("docc"))
    if not pers and not docc:
        return None
    p = dict(payload.get("params") or {})
    if oggi is not None:
        p["oggi"] = oggi
    out = sx.calcola_sx(pers, docc, p)
    return {"kpi": out["kpi"], "avvisi": out["avvisi"]}


def metriche_mz(payload, oggi=None):
    mezzi, _ = mz.normalizza_mezzi(payload.get("mezzi"))
    if not mezzi:
        return None
    nomi = {m["Mezzo"] for m in mezzi}
    uso, _ = mz.normalizza_uso(payload.get("uso"), nomi)
    scad, _ = mz.normalizza_scad(payload.get("scad"), nomi)
    p = dict(payload.get("params") or {})
    if oggi is not None:
        p["oggi"] = oggi
    out = mz.calcola_mz(mezzi, uso, scad, p)
    return {"kpi": out["kpi"], "avvisi": out["avvisi"]}


def metriche_og(payload, oggi=None):
    ris, _ = og.normalizza_ris(payload.get("ris"))
    if not ris:
        return None
    ass, _ = og.normalizza_ass(payload.get("ass"), {r["Risorsa"] for r in ris})
    p = dict(payload.get("params") or {})
    if oggi is not None:
        p["oggi"] = oggi
    out = og.calcola_og(ris, ass, p)
    return {"kpi": out["kpi"], "avvisi": out["avvisi"]}


def metriche_pv(payload):
    voci, _ = pv.normalizza_voci(payload.get("voci"))
    if not voci:
        return None
    out = pv.calcola_preventivo(voci, payload.get("params") or {})
    return {"kpi": out["kpi"], "params": out["params"], "avvisi": out["avvisi"]}


def metriche_credit(payload):
    dati = {**core.DATI_DEFAULT, **(payload.get("dati") or {})}
    soglie = {k: tuple(v) for k, v in (payload.get("soglie") or {}).items()} or None
    piano = {**core.PIANO_DEFAULT, **(payload.get("piano_par") or {})}
    res = core.esegui_scenario(dati, payload.get("leve") or {}, piano, soglie)
    r = res["rating"]
    return {"classe": r["classe"], "punti": r["punti"], "pfn_ebitda": r["pfn_ebitda"], "dscr": r["dscr"], "anno": dati["anno_riferimento"],
            "demo": bool(payload.get("dati_demo"))}


def metriche_bp(payload):
    p = {k[3:] if k.startswith("bp_") else k: v for k, v in payload.items() if isinstance(k, str)}
    p = {k: v for k, v in p.items() if k in bp.BP_DEFAULT}
    out = bp.calcola_bp(p)
    return {"kpi": out["kpi"], "avvisi": out["avvisi"], "nome": payload.get("bp_nome", "")}


# ----------------------------------------------------------------------------
# SEMAFORI
# ----------------------------------------------------------------------------
def semafori(m, soglie=None):
    """`m`: {"cf":…, "sc":…, "pv":…, "credit":…, "bp":…} (i moduli assenti sono None). Restituisce (righe, stato generale, azioni)."""
    s = {**DD_DEFAULT, **(soglie or {})}
    righe, azioni = [], []

    if m.get("sc"):
        k = m["sc"]["kpi"]
        stato = "ok" if k["cassa_settimana1"] >= 0 else ("warn" if -k["cassa_settimana1"] <= k["fido"] else "bad")
        righe.append(_riga("Cassa", "Cassa a fine settimana 1", f"{fmt_num(k['cassa_settimana1'])} €", stato,
                           "Quanto resta sul conto dopo i movimenti dei prossimi 7 giorni"))
        if stato != "ok":
            azioni.append(("bad" if stato == "bad" else "warn", "Questa settimana la cassa non regge: anticipa gli incassi piu' sicuri o dilaziona i pagamenti non urgenti."))
        if k["prima_settimana_fuori_fido"]:
            st2 = "bad"
        elif k["picco_fabbisogno"] > 0:
            st2 = "warn"
        else:
            st2 = "ok"
        righe.append(_riga("Cassa", f"Scoperto massimo ({k['settimane']} settimane)", f"{fmt_num(k['picco_fabbisogno'])} €", st2,
                           f"Fido {fmt_num(k['fido'])} €" + (f" · fuori fido dalla settimana {k['prima_settimana_fuori_fido']}" if k["prima_settimana_fuori_fido"] else "")))
        if st2 == "bad":
            azioni.append(("bad", f"Lo scoperto supera il fido dalla settimana {k['prima_settimana_fuori_fido']}: parla con la banca o recupera liquidita' prima di quella data."))
        pct = k["scaduto_attivo_pct"]
        st3 = "ok" if pct <= s["scaduto_warn"] else ("warn" if pct <= s["scaduto_bad"] else "bad")
        righe.append(_riga("Crediti", "Crediti scaduti sul totale da incassare", f"{fmt_num(pct, 1)}%", st3,
                           f"{fmt_num(k['scaduto_attivo'])} € scaduti, ritardo medio {fmt_num(k['ritardo_medio_gg'], 0)} gg"))
        if st3 != "ok":
            n = len(m["sc"].get("solleciti") or [])
            azioni.append((st3, f"Sollecita i clienti con fatture scadute ({n} da contattare, {fmt_num(k['scaduto_attivo'])} €)."))
        st4 = "ok" if k["scaduto_passivo"] <= 0 else ("warn" if k["scaduto_passivo"] <= 0.1 * max(k["da_pagare"], 1) else "bad")
        righe.append(_riga("Debiti", "Debiti verso fornitori scaduti", f"{fmt_num(k['scaduto_passivo'])} €", st4, f"Da pagare in totale {fmt_num(k['da_pagare'])} €"))
        if st4 != "ok":
            azioni.append((st4, "Hai fornitori scaduti: regola i piu' critici per evitare blocchi di forniture e interessi di mora."))
    else:
        righe.append(_riga("Cassa", "Scadenzario", "dati mancanti", "nd", "Inserisci le fatture nel modulo Scadenzario"))

    if m.get("cf"):
        k = m["cf"]["kpi"]
        st5 = "bad" if k["primo_mese_fuori_fido"] else ("warn" if k["picco_fabbisogno"] > 0 else "ok")
        righe.append(_riga("Liquidita' di cantiere", f"Picco di fabbisogno ({k['mesi']} mesi)", f"{fmt_num(k['picco_fabbisogno'])} €", st5,
                           f"Fido {fmt_num(k['fido'])} €" + (f" · fuori fido dal mese {k['primo_mese_fuori_fido']}" if k["primo_mese_fuori_fido"] else "")))
        if st5 == "bad":
            azioni.append(("bad", f"Il portafoglio cantieri supera il fido dal mese {k['primo_mese_fuori_fido']}: aumenta gli anticipi contrattuali o il fido (vedi Stress e Soluzioni nel Cash Flow)."))
        mg = k["margine_lordo_pct"]
        st6 = "ok" if mg >= s["margine_target"] else ("warn" if mg >= s["margine_target"] - 5 else "bad")
        righe.append(_riga("Margine", "Margine lordo del portafoglio cantieri", f"{fmt_num(mg, 1)}%", st6, f"Obiettivo {fmt_num(s['margine_target'], 0)}% · {fmt_num(k['margine_lordo'])} €"))
        if st6 != "ok":
            azioni.append((st6, "Il margine del portafoglio e' sotto l'obiettivo: rivedi prezzi, costi o mix di cantieri."))
        st7 = "ok" if k["margine_netto"] >= 0 else "bad"
        righe.append(_riga("Margine", "Margine dopo i costi generali", f"{fmt_num(k['margine_netto'])} €", st7, "Nell'orizzonte considerato"))
    else:
        righe.append(_riga("Liquidita' di cantiere", "Cash flow di cantiere", "dati mancanti", "nd", "Compila il modulo Cash Flow di cantiere"))

    if m.get("pv"):
        k, q = m["pv"]["kpi"], m["pv"]["params"]
        mg = k["margine_pct"]
        mn = q["margine_min_pct"]
        st8 = "ok" if mg >= mn else ("warn" if mg >= 0.75 * mn else "bad")
        righe.append(_riga("Margine", "Margine dell'ultimo preventivo", f"{fmt_num(mg, 1)}%", st8, f"Minimo accettabile {fmt_num(mn, 1)}% · imponibile {fmt_num(k['imponibile'])} €"))
        if st8 != "ok":
            azioni.append((st8, "Il preventivo in esame ha un margine sotto il minimo: riduci lo sconto o rinegozia i costi prima di offrire."))

    if m.get("credit"):
        c = m["credit"]
        righe.append(_riga("Rating", "Rating indicativo dell'azienda", c["classe"].split(" - ")[0].replace("FASCIA ", "").title(),
                           {"VERDE": "ok", "GIALLA": "warn", "ROSSA": "bad"}.get(c["classe"].split(" - ")[0].replace("FASCIA ", ""), "nd"),
                           f"{c['punti']}/8 punti · PFN/EBITDA {fmt_num(c['pfn_ebitda'], 1)}x" + (" · dati di esempio" if c["demo"] else "")))
        if c["classe"].startswith("FASCIA ROSSA"):
            azioni.append(("bad", "Il rating indicativo e' in fascia rossa: valuta di ridurre la PFN o rafforzare il patrimonio prima di chiedere nuovo credito."))
        elif c["classe"].startswith("FASCIA GIALLA"):
            azioni.append(("warn", "Rating in fascia gialla: lavora su PFN/EBITDA o DSCR per migliorare la bancabilita'."))
    else:
        righe.append(_riga("Rating", "Rating indicativo dell'azienda", "dati mancanti", "nd", "Salva una pratica nel modulo Credit Risk"))

    if m.get("bp"):
        k = m["bp"]["kpi"]
        d = k["dscr_min"]
        if d is None:
            st9 = "nd"
        else:
            st9 = "ok" if d >= s["dscr_ok"] else ("warn" if d >= s["dscr_warn"] else "bad")
        righe.append(_riga("Piano", "DSCR minimo del business plan", "n.d." if d is None else f"{fmt_num(d, 2)}x", st9,
                           f"Cassa minima {fmt_num(k['cassa_minima'])} €" + (f" · {m['bp']['nome']}" if m["bp"].get("nome") else "")))
        if st9 in ("warn", "bad"):
            azioni.append((st9, "Il business plan copre poco il servizio del debito: rivedi investimento, mutuo o ricavi."))

    if m.get("sl"):
        k = m["sl"]["kpi"]
        gap = k["margine_atteso_pct"] - k["margine_finale_pct"]
        st10 = "bad" if k["margine_finale"] < 0 or gap > sl.TOLL_WARN else ("warn" if gap > sl.TOLL_OK else "ok")
        righe.append(_riga("Margine", "Margine a finire delle commesse", f"{fmt_num(k['margine_finale_pct'], 1)}%", st10,
                           f"Preventivato {fmt_num(k['margine_atteso_pct'], 1)}% · {k['n_commesse']} commesse, avanzamento {fmt_num(k['avanzamento'], 0)}%"))
        if st10 != "ok":
            azioni.append((st10, "Le commesse in corso chiuderanno con meno margine del preventivato: controlla costi e varianti non fatturate."))
        n_crit = k["n_bad"]
        st11 = "bad" if n_crit else ("warn" if k["n_warn"] else "ok")
        righe.append(_riga("Commesse", "Commesse in sofferenza", str(n_crit), st11, f"{k['n_warn']} da tenere d'occhio su {k['n_commesse']}"))
        if n_crit:
            nomi = ", ".join(d["Commessa"] for d in m["sl"].get("commesse", []) if d["Stato"] == "bad")
            azioni.append(("bad", "Commesse critiche" + (f" ({nomi})" if nomi else "") + ": verifica subito costi a finire e rinegozia varianti o prezzi."))
        if k["da_fatturare"] > 0:
            st12 = "warn"
            righe.append(_riga("Crediti", "Lavori eseguiti da fatturare", f"{fmt_num(k['da_fatturare'])} €", st12, "Emetti il prossimo SAL: è liquidità che aspetta"))
            azioni.append(("warn", f"Hai {fmt_num(k['da_fatturare'])} € di lavori eseguiti non ancora fatturati: emetti i SAL."))

    if m.get("ga"):
        k = m["ga"]["kpi"]
        stg = "bad" if k["scadute"] or k["n_bad"] else ("warn" if k["in_scadenza"] or k["doc_mancanti"] else "ok")
        righe.append(_riga("Commerciale", "Gare in scadenza o in ritardo", str(k["in_scadenza"] + k["scadute"]), stg,
                           f"{k['n_aperte']} gare aperte · pipeline ponderata {fmt_num(k['ponderato'])} € · {k['doc_mancanti']} documenti mancanti"))
        if stg != "ok":
            azioni.append((stg, "Ci sono gare con scadenza vicina o superata, o documenti mancanti: completa le offerte in tempo."))
    if m.get("fo"):
        k = m["fo"]["kpi"]
        stf = "bad" if k["doc_scaduti"] else ("warn" if k["doc_in_scadenza"] or k["sovrafatturati"] else "ok")
        righe.append(_riga("Fornitori", "Documenti dei fornitori scaduti", str(k["doc_scaduti"]), stf, f"{k['doc_in_scadenza']} in scadenza · {k['forn_critici']} fornitori critici"))
        if stf != "ok":
            azioni.append((stf, "Chiedi il rinnovo dei documenti scaduti o in scadenza (DURC, assicurazioni) ai fornitori."))
    if m.get("sx"):
        k = m["sx"]["kpi"]
        sts = "bad" if k["cantieri_a_rischio"] else ("warn" if k["in_scadenza"] else "ok")
        righe.append(_riga("Sicurezza", "Cantieri con documenti o formazioni non in regola", str(k["cantieri_a_rischio"]), sts,
                           f"{k['persone_non_in_regola']} persone non in regola · {k['doc_mancanti']} documenti mancanti"))
        if sts != "ok":
            azioni.append((sts, "Sicurezza: aggiorna formazioni, idoneità e documenti di cantiere in scadenza o mancanti (verifica con il RSPP)."))
    if m.get("mz"):
        k = m["mz"]["kpi"]
        stm = "bad" if k["scad_scadute"] else ("warn" if k["scad_in_arrivo"] or k["sottoutilizzati"] else "ok")
        righe.append(_riga("Mezzi", "Scadenze dei mezzi superate", str(k["scad_scadute"]), stm, f"{k['scad_in_arrivo']} in arrivo · fissi non assorbiti {fmt_num(k['fissi_non_assorbiti'])} €"))
        if stm != "ok":
            azioni.append((stm, "Parco mezzi: rinnova le scadenze e valuta i mezzi poco usati (costi fissi non coperti)."))
    if m.get("og"):
        k = m["og"]["kpi"]
        sto = "bad" if k["mesi_sovraccarico"] else ("warn" if k["mesi_scarico"] else "ok")
        righe.append(_riga("Organico", "Mesi in sovraccarico", str(k["mesi_sovraccarico"]), sto, f"saturazione media {fmt_num(k['saturazione_media'], 0)}% · {k['mesi_scarico']} mesi con poco lavoro"))
        if sto != "ok":
            azioni.append((sto, "Organico: nei mesi di sovraccarico servono più risorse; nei mesi scarichi ci sono ore ferme da riempire."))

    pres = [r["Stato"] for r in righe if r["Stato"] != "nd"]
    if not pres:
        generale = "nd"
    else:
        generale = max(pres, key=lambda x: GRAVITA[x])
    azioni.sort(key=lambda a: -GRAVITA[a[0]])
    return righe, generale, azioni


def conteggio(righe):
    c = {"ok": 0, "warn": 0, "bad": 0, "nd": 0}
    for r in righe:
        c[r["Stato"]] += 1
    return c


MODULI_METRICHE = ("sc", "cf", "pv", "sl", "ga", "fo", "sx", "mz", "og", "credit", "bp")


def metriche_da_payload(m, payload, oggi=None):
    """Calcola le metriche di un modulo da un payload salvato (usato dal Cruscotto e dal riepilogo email)."""
    if not payload:
        return None
    if m == "cf":
        return metriche_cf(payload)
    if m == "pv":
        return metriche_pv(payload)
    if m == "credit":
        return metriche_credit(payload)
    if m == "bp":
        return metriche_bp(payload)
    return globals()["metriche_" + m](payload, oggi)
