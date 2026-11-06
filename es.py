"""
es.py - ESCo: diagnosi energetica (consumi di partenza), modello dell'investimento e bozza del contratto di prestazione energetica (EPC). Senza Streamlit.

Tutto al lordo delle imposte; i numeri sono stime da confrontare con il piano economico-finanziario del commercialista prima di firmare.
"""
import io
import re

MESI = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
COLONNE_BOLLETTE = ["Mese", "El_kWh", "El_euro", "Gas_Smc", "Gas_euro"]
ETICHETTE_BOLLETTE = {"Mese": "Mese", "El_kWh": "Elettricità kWh", "El_euro": "Elettricità €", "Gas_Smc": "Gas Smc", "Gas_euro": "Gas €"}
KWH_PER_SMC = 9.6                                                       # potere calorifico medio del gas naturale, kWh per Smc
TIPI = ["Fotovoltaico", "Pompa di calore", "Caldaia e regolazione", "Isolamento (cappotto, serramenti)", "Illuminazione LED", "Altro"]
COLONNE_INT = ["Intervento", "Tipo", "Investimento", "Risp_El_kWh", "Risp_Gas_Smc", "Altri_ricavi", "Manutenzione", "Incentivo", "Incentivo_anni"]
ETICHETTE_INT = {"Intervento": "Intervento", "Tipo": "Tipo", "Investimento": "Investimento €", "Risp_El_kWh": "Risparmio elettricità kWh/anno", "Risp_Gas_Smc": "Risparmio gas Smc/anno",
                 "Altri_ricavi": "Altri ricavi €/anno (es. cessione energia)", "Manutenzione": "Manutenzione €/anno", "Incentivo": "Incentivo totale €", "Incentivo_anni": "Incentivo in quanti anni"}
MODELLI = ["Risparmio condiviso", "Canone fisso"]
ES_DEFAULT = {
    "cliente": "", "indirizzo": "", "mq": 0.0, "uso": "", "gg_anno": 0.0, "gg_normali": 0.0,
    "prezzo_el": 0.0, "prezzo_gas": 0.0, "aumento_energia_pct": 2.0,
    "durata": 15, "modello": "Risparmio condiviso", "quota_esco_pct": 70.0, "canone": 0.0, "garantito_pct": 90.0,
    "debito_pct": 70.0, "tasso_pct": 5.0, "durata_debito": 12, "sconto_pct": 7.0, "degrado_pct": 0.5,
}


def _f(v, d=0.0):
    try:
        if v is None or v != v:
            return d
        if isinstance(v, str):
            v = re.sub(r"[^\d,.\-]", "", v).replace(".", "").replace(",", ".") if "," in v else re.sub(r"[^\d.\-]", "", v)
        return float(v)
    except (TypeError, ValueError):
        return d


def bollette_vuote():
    return [{"Mese": m, "El_kWh": 0.0, "El_euro": 0.0, "Gas_Smc": 0.0, "Gas_euro": 0.0} for m in MESI]


def normalizza_bollette(righe):
    out = []
    for r in righe or []:
        m = str((r or {}).get("Mese") or "").strip()
        if m:
            out.append({"Mese": m, **{c: max(0.0, _f((r or {}).get(c))) for c in COLONNE_BOLLETTE[1:]}})
    return out


def situazione_di_partenza(bollette, p=None):
    """Consumi e costi annui, prezzi medi, indice kWh/m2 e correzione climatica del gas (gradi giorno dell'anno rispetto a quelli normali)."""
    q = {**ES_DEFAULT, **(p or {})}
    b = normalizza_bollette(bollette)
    mesi_el = sum(1 for r in b if r["El_kWh"] > 0)
    mesi_gas = sum(1 for r in b if r["Gas_Smc"] > 0)
    el, el_e = sum(r["El_kWh"] for r in b), sum(r["El_euro"] for r in b)
    gas, gas_e = sum(r["Gas_Smc"] for r in b), sum(r["Gas_euro"] for r in b)
    if 0 < mesi_el < 12:                                               # anno incompleto: si porta a 12 mesi con la media dei mesi presenti
        el, el_e = el / mesi_el * 12, el_e / mesi_el * 12
    if 0 < mesi_gas < 12:
        gas, gas_e = gas / mesi_gas * 12, gas_e / mesi_gas * 12
    ggA, ggN = _f(q["gg_anno"]), _f(q["gg_normali"])
    fattore = ggN / ggA if ggA > 0 and ggN > 0 else 1.0
    gas_corr = gas * fattore
    kwh_tot = el + gas_corr * KWH_PER_SMC
    mq = _f(q["mq"])
    avvisi = []
    if mesi_el < 12 and mesi_el:
        avvisi.append(f"Elettricità: ci sono solo {mesi_el} mesi, il resto è stimato con la media. Per un contratto servono 12 mesi (meglio 24-36).")
    if mesi_gas < 12 and mesi_gas:
        avvisi.append(f"Gas: ci sono solo {mesi_gas} mesi, il resto è stimato con la media.")
    if not (mesi_el or mesi_gas):
        avvisi.append("Inserisci almeno i consumi dell'elettricità o del gas.")
    if gas and fattore == 1.0:
        avvisi.append("Senza i gradi giorno dell'anno e quelli normali il gas non è corretto per il clima: un inverno mite o freddo falserebbe il risparmio misurato.")
    return {"el_kwh": round(el), "el_euro": round(el_e, 2), "gas_smc": round(gas), "gas_euro": round(gas_e, 2), "gas_smc_corretto": round(gas_corr), "fattore_clima": round(fattore, 3),
            "prezzo_el": round(el_e / el, 4) if el else 0.0, "prezzo_gas": round(gas_e / gas, 4) if gas else 0.0, "costo_annuo": round(el_e + gas_e, 2),
            "kwh_totali": round(kwh_tot), "kwh_m2": round(kwh_tot / mq, 1) if mq else None, "mesi_el": mesi_el, "mesi_gas": mesi_gas, "avvisi": avvisi}


def normalizza_interventi(righe):
    out, avvisi = [], []
    for i, r in enumerate(righe or [], start=1):
        r = r or {}
        nome = str(r.get("Intervento") or "").strip()
        v = {c: (_f(r.get(c)) if c in ("Risp_El_kWh", "Risp_Gas_Smc") else max(0.0, _f(r.get(c)))) for c in COLONNE_INT[2:]}      # il risparmio puo' essere negativo (es. pompa di calore: piu' elettricita')
        if not nome and not any(v.values()):
            continue
        if not nome or v["Investimento"] <= 0:
            avvisi.append(f"Intervento, riga {i}: servono nome e investimento maggiore di zero, riga ignorata.")
            continue
        t = str(r.get("Tipo") or "").strip()
        v["Incentivo_anni"] = max(1.0, v["Incentivo_anni"] or 1.0)
        out.append({"Intervento": nome, "Tipo": t if t in TIPI else "Altro", **v})
    return out, avvisi


def _irr(flussi):
    def van(t):
        return sum(f / (1 + t) ** i for i, f in enumerate(flussi))
    lo, hi = -0.9, 1.0
    if van(lo) * van(hi) > 0:
        return None
    for _ in range(80):
        mid = (lo + hi) / 2
        if van(lo) * van(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def modello(interventi, base, p=None):
    """Flusso di cassa dell'ESCo anno per anno: risparmio del cliente, ricavo ESCo (quota o canone), incentivi, manutenzione, rata del finanziamento, VAN, TIR, rientro, DSCR."""
    q = {**ES_DEFAULT, **(p or {})}
    iv = interventi
    inv = sum(x["Investimento"] for x in iv)
    anni = max(1, int(_f(q["durata"], 15)))
    pel = _f(q["prezzo_el"]) or (base or {}).get("prezzo_el", 0.0)
    pgas = _f(q["prezzo_gas"]) or (base or {}).get("prezzo_gas", 0.0)
    agg, deg = _f(q["aumento_energia_pct"]) / 100, _f(q["degrado_pct"]) / 100
    debito = inv * min(100.0, max(0.0, _f(q["debito_pct"]))) / 100
    ndeb, tasso = max(1, int(_f(q["durata_debito"], 12))), _f(q["tasso_pct"]) / 100
    rata = debito * tasso / (1 - (1 + tasso) ** -ndeb) if tasso > 0 else debito / ndeb
    sconto = _f(q["sconto_pct"]) / 100
    garantito = _f(q["garantito_pct"]) / 100
    quota = _f(q["quota_esco_pct"]) / 100
    flusso, cum_p, cum_e = [], -inv, -(inv - debito)
    prog, eq_flows = [-inv], [-(inv - debito)]
    dscr, rientro, rientro_cum = [], None, -inv
    for y in range(1, anni + 1):
        risp = sum(x["Risp_El_kWh"] * pel * (1 - deg) ** (y - 1) + x["Risp_Gas_Smc"] * pgas * (1 - deg) ** (y - 1) for x in iv) * (1 + agg) ** (y - 1)
        ricavi_altri = sum(x["Altri_ricavi"] for x in iv) * (1 - deg) ** (y - 1)
        inc = sum(x["Incentivo"] / x["Incentivo_anni"] for x in iv if y <= x["Incentivo_anni"])
        man = sum(x["Manutenzione"] for x in iv)
        ricavo_esco = risp * quota if q["modello"] == "Risparmio condiviso" else _f(q["canone"])
        risp_cliente = risp - ricavo_esco
        cfads = ricavo_esco + ricavi_altri + inc - man
        servizio = rata if y <= ndeb else 0.0
        netto_p = cfads
        netto_e = cfads - servizio
        prima = rientro_cum
        rientro_cum += netto_p
        if rientro is None and rientro_cum >= 0:
            rientro = round(y - 1 + (-prima / netto_p if netto_p else 0), 1)
        if servizio:
            dscr.append(cfads / servizio)
        prog.append(netto_p)
        eq_flows.append(netto_e)
        cum_e += netto_e
        flusso.append({"Anno": y, "Risparmio totale €": round(risp), "Al cliente €": round(risp_cliente), "Ricavo ESCo €": round(ricavo_esco), "Altri ricavi €": round(ricavi_altri), "Incentivi €": round(inc),
                       "Manutenzione €": round(-man), "Rata debito €": round(-servizio), "Flusso ESCo €": round(netto_e), "Cumulato ESCo €": round(cum_e)})
    van = sum(f / (1 + sconto) ** i for i, f in enumerate(prog))
    tir = _irr(prog)
    tir_e = _irr(eq_flows)
    risp1 = flusso[0]["Risparmio totale €"] if flusso else 0
    garantito_eur = round(risp1 * garantito)
    avvisi = []
    if not iv:
        avvisi.append("Inserisci almeno un intervento.")
    if base and base.get("costo_annuo") and risp1 > base["costo_annuo"] * 0.9:
        avvisi.append("Il risparmio previsto è quasi tutta la spesa attuale: controlla i numeri o spiega come si ottiene.")
    if base and base.get("el_kwh") and sum(x["Risp_El_kWh"] for x in iv) > base["el_kwh"] * 1.0 and not any(x["Tipo"] == "Fotovoltaico" for x in iv):
        avvisi.append("Risparmio di elettricità superiore al consumo attuale: senza fotovoltaico non è possibile.")
    if base and base.get("gas_smc") and sum(x["Risp_Gas_Smc"] for x in iv) > base["gas_smc"]:
        avvisi.append("Risparmio di gas superiore al consumo attuale: non è possibile.")
    if dscr and min(dscr) < 1.2:
        avvisi.append(f"Copertura del debito minima {min(dscr):.2f}: sotto 1,2 le banche di solito non finanziano. Riduci il debito o aumenta il ricavo.")
    if q["modello"] == "Canone fisso" and risp1 and _f(q["canone"]) > risp1:
        avvisi.append("Il canone è più alto del risparmio del primo anno: il cliente ci rimetterebbe.")
    if ndeb > anni:
        avvisi.append("Il finanziamento dura più del contratto: la banca non sarà ripagata dal contratto.")
    kpi = {"investimento": round(inv, 2), "debito": round(debito, 2), "capitale_proprio": round(inv - debito, 2), "rata": round(rata, 2), "risparmio_anno1": risp1, "garantito_anno1": garantito_eur,
           "ricavo_esco_anno1": flusso[0]["Ricavo ESCo €"] if flusso else 0, "al_cliente_anno1": flusso[0]["Al cliente €"] if flusso else 0, "rientro_anni": rientro, "van": round(van),
           "tir": round(tir * 100, 1) if tir is not None else None, "tir_capitale_proprio": round(tir_e * 100, 1) if tir_e is not None else None, "dscr_min": round(min(dscr), 2) if dscr else None,
           "dscr_medio": round(sum(dscr) / len(dscr), 2) if dscr else None, "guadagno_finale": flusso[-1]["Cumulato ESCo €"] if flusso else 0,
           "risparmio_percentuale": round(risp1 / base["costo_annuo"] * 100, 1) if base and base.get("costo_annuo") else None}
    return {"kpi": kpi, "flusso": flusso, "avvisi": avvisi, "params": q}


def bozza_epc(dati, interventi, base, out):
    """Testo della bozza di contratto di prestazione energetica: lista di (titolo, [paragrafi]). Da far rivedere al legale prima dell'uso."""
    q = {**ES_DEFAULT, **dati}
    k = out["kpi"]
    cliente = q.get("cliente") or "[CLIENTE]"
    elenco = "; ".join(f"{x['Intervento']} (investimento {x['Investimento']:,.0f} €)".replace(",", ".") for x in interventi) or "[INTERVENTI]"
    quota = (f"Il Cliente riconosce all'ESCo il {q['quota_esco_pct']:.0f}% del risparmio misurato in ogni anno contrattuale; il restante {100 - q['quota_esco_pct']:.0f}% resta al Cliente."
             if q["modello"] == "Risparmio condiviso" else f"Il Cliente riconosce all'ESCo un canone annuo di {q['canone']:,.2f} € oltre IVA, pagato in rate [mensili/trimestrali].".replace(",", "X").replace(".", ",").replace("X", "."))
    return [
        ("1. Parti e oggetto", [f"Tra [RAGIONE SOCIALE ESCo], P. IVA [..], di seguito «ESCo», e {cliente}, di seguito «Cliente», per l'immobile sito in {q.get('indirizzo') or '[INDIRIZZO]'}.",
                                f"Oggetto: progettazione, finanziamento, realizzazione, gestione e manutenzione dei seguenti interventi di efficienza energetica: {elenco}.",
                                "La realizzazione avviene a cura e spese dell'ESCo, che si ripaga con il risparmio energetico ottenuto, come descritto di seguito."]),
        ("2. Durata", [f"Il contratto dura {int(q['durata'])} anni dalla data di collaudo e messa in esercizio degli interventi. Le parti si danno atto che non è previsto rinnovo tacito."]),
        ("3. Situazione di partenza (baseline)", [
            f"Il consumo di riferimento prima degli interventi è di {base.get('el_kwh', 0):,} kWh di elettricità e {base.get('gas_smc_corretto', 0):,} Smc di gas all'anno (gas corretto per i gradi giorno), "
            f"per una spesa annua di {base.get('costo_annuo', 0):,.0f} €.".replace(",", "."),
            "I consumi derivano dalle bollette dei periodi indicati nell'Allegato A, che le parti dichiarano di conoscere e accettare. Il Cliente comunica all'ESCo ogni variazione dell'uso dell'immobile (orari, superfici, attività) che incida sui consumi: in tal caso la baseline si ricalcola."]),
        ("4. Risparmio garantito", [f"L'ESCo garantisce un risparmio annuo non inferiore a {k['garantito_anno1']:,} € (pari al {q['garantito_pct']:.0f}% del risparmio atteso di {k['risparmio_anno1']:,} € nel primo anno), ai prezzi dell'energia della baseline.".replace(",", "."),
                                    "Se il risparmio misurato in un anno è inferiore al garantito, l'ESCo riconosce al Cliente la differenza o la porta a compensazione nell'anno successivo [scegliere]."]),
        ("5. Corrispettivo", [quota, "I corrispettivi sono aggiornati ogni anno secondo [indice ISTAT / prezzo dell'energia] e sono soggetti a IVA di legge."]),
        ("6. Misura e verifica del risparmio", ["Il risparmio si calcola ogni anno confrontando i consumi misurati con la baseline, corretta per clima e utilizzo secondo il protocollo IPMVP (opzione [..]). I dati sono letti da [contatori / bollette / sistema di monitoraggio].",
                                              "Il Cliente consente l'accesso ai contatori e ai documenti necessari. Il rapporto annuale viene consegnato entro [30] giorni dalla chiusura dell'anno contrattuale; in caso di contestazione decide un perito indipendente scelto di comune accordo."]),
        ("7. Incentivi", ["Gli incentivi legati agli interventi (detrazioni, Conto Termico, certificati bianchi, altri) spettano a [ESCo / Cliente / secondo ripartizione]; il Cliente fornisce i documenti e le firme necessarie.",
                          "Se un incentivo atteso non viene riconosciuto per cause non imputabili all'ESCo, le parti rinegoziano il corrispettivo."]),
        ("8. Manutenzione e gestione", [f"L'ESCo esegue a proprio carico la manutenzione ordinaria e straordinaria degli impianti realizzati (costo previsto {sum(x['Manutenzione'] for x in interventi):,.0f} € all'anno), garantisce i tempi di intervento di [..] ore dalla segnalazione e mantiene le garanzie dei costruttori.".replace(",", "."),
                                       "L'ESCo stipula una polizza [all risks / responsabilità civile] con massimale di [..] €."]),
        ("9. Obblighi del Cliente", ["Il Cliente usa gli impianti con diligenza, non li modifica senza consenso scritto, paga i corrispettivi alle scadenze e permette l'accesso per manutenzione e misure."]),
        ("10. Proprietà degli impianti e fine contratto", ["Durante il contratto gli impianti restano di proprietà dell'ESCo [oppure: del Cliente con patto di riservato dominio]. Alla scadenza passano al Cliente [gratuitamente / dietro riscatto di [..] €], in buono stato di funzionamento, con la documentazione tecnica."]),
        ("11. Ritardi, inadempimenti e recesso", ["In caso di ritardo nei pagamenti superiore a [..] giorni decorrono gli interessi di legge (D.Lgs. 231/2002). Ciascuna parte può risolvere il contratto per grave inadempimento non sanato entro [..] giorni dalla diffida.",
                                                 "Se il Cliente cessa l'attività o vende l'immobile, subentra l'acquirente oppure si applica un indennizzo pari al valore residuo degli investimenti non ancora recuperati."]),
        ("12. Foro e legge applicabile", ["Legge italiana. Foro competente: [..]."]),
        ("Allegati", ["A. Bollette e consumi di partenza · B. Interventi e specifiche tecniche · C. Piano economico · D. Metodo di misura e verifica · E. Polizze."]),
    ]


def docx_epc(sezioni, titolo="Contratto di prestazione energetica (EPC) - BOZZA"):
    from docx import Document
    d = Document()
    d.add_heading(titolo, 0)
    d.add_paragraph().add_run("Bozza di lavoro generata dalla suite: va completata nelle parti tra parentesi quadre e fatta rivedere da un legale prima della firma.").italic = True
    for t, pars in sezioni:
        d.add_heading(t, 1)
        for p in pars:
            d.add_paragraph(p)
    b = io.BytesIO()
    d.save(b)
    return b.getvalue()
