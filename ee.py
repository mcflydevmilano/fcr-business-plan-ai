"""
ee.py - Preventivi di efficienza energetica sullo stesso schema del fotovoltaico: pompa di calore, caldaia e regolazione, cappotto e serramenti,
relamping LED, solare termico, colonnine di ricarica. Ogni tipo ha i suoi dati d'ingresso, le voci di costo di partenza e la stima del risparmio. Senza Streamlit.

Costi, rendimenti e prezzi sono stime di partenza da sostituire con i propri dati (listino) e con quelli del sopralluogo.
"""
import fv

KWH_SMC = 9.6                                          # kWh per Smc di gas
TIPI = {
    "pdc": "Pompa di calore",
    "cal": "Caldaia a condensazione e regolazione",
    "cap": "Cappotto e serramenti",
    "led": "Relamping LED",
    "sol": "Solare termico",
    "col": "Colonnine di ricarica",
}
# (chiave, etichetta, valore iniziale, minimo, massimo, passo, formato, aiuto)
PARAMETRI = {
    "pdc": [("gas_smc", "Gas consumato oggi (Smc/anno)", 2000.0, 0.0, 1e6, 50.0, "%.0f", "Solo la parte per riscaldamento (e acqua calda se la sostituisce)."), ("rend_vecchio", "Rendimento caldaia attuale", 0.80, 0.4, 1.1, 0.01, "%.2f", None),
            ("scop", "Efficienza stagionale della pompa (SCOP)", 3.4, 2.0, 6.0, 0.1, "%.1f", "Quanti kWh di calore per ogni kWh di elettricità: 3-4 nelle case ben isolate."), ("kw", "Potenza da installare (kW)", 12.0, 2.0, 500.0, 0.5, "%.1f", None)],
    "cal": [("gas_smc", "Gas consumato oggi (Smc/anno)", 2000.0, 0.0, 1e6, 50.0, "%.0f", None), ("rend_vecchio", "Rendimento caldaia attuale", 0.80, 0.4, 1.1, 0.01, "%.2f", None),
            ("rend_nuovo", "Rendimento caldaia nuova (con regolazione)", 0.95, 0.8, 1.1, 0.01, "%.2f", "Condensazione con termostati e valvole: 0,93-0,98."), ("kw", "Potenza da installare (kW)", 24.0, 4.0, 2000.0, 1.0, "%.0f", None)],
    "cap": [("gas_smc", "Gas consumato oggi (Smc/anno)", 3000.0, 0.0, 1e6, 50.0, "%.0f", None), ("rend_vecchio", "Rendimento dell'impianto attuale", 0.85, 0.4, 1.1, 0.01, "%.2f", None),
            ("mq_involucro", "Superficie dell'involucro trattato (m²)", 300.0, 1.0, 1e5, 10.0, "%.0f", "Pareti, tetto o serramenti che si isolano."), ("u_prima", "Trasmittanza prima (W/m²K)", 1.2, 0.1, 6.0, 0.05, "%.2f", "Muro non isolato ≈ 1,0-1,5; serramenti vecchi ≈ 3-5."),
            ("u_dopo", "Trasmittanza dopo (W/m²K)", 0.25, 0.1, 6.0, 0.05, "%.2f", "Muro con cappotto ≈ 0,22-0,30; serramenti nuovi ≈ 1,2-1,4."), ("gg", "Gradi giorno della zona", 2200.0, 500.0, 4000.0, 50.0, "%.0f", "Tabella dei gradi giorno del comune.")],
    "led": [("punti", "Punti luce da sostituire", 100.0, 1.0, 1e5, 1.0, "%.0f", None), ("w_vecchi", "Potenza attuale di un punto (W)", 58.0, 1.0, 1000.0, 1.0, "%.0f", "Es. tubo fluorescente 58 W, alogena 50 W."),
            ("w_nuovi", "Potenza LED di un punto (W)", 22.0, 1.0, 1000.0, 1.0, "%.0f", None), ("ore", "Ore di accensione all'anno", 3000.0, 100.0, 8760.0, 100.0, "%.0f", "Ufficio ≈ 2.500-3.000, negozio ≈ 4.000, 24 ore su 24 = 8.760."),
            ("manut_risp", "Manutenzione risparmiata (€/anno)", 150.0, 0.0, 1e6, 10.0, "%.0f", "Lampade e starter che non si cambiano più.")],
    "sol": [("persone", "Persone servite", 4.0, 1.0, 1000.0, 1.0, "%.0f", None), ("litri", "Acqua calda per persona (litri/giorno)", 50.0, 10.0, 200.0, 5.0, "%.0f", None),
            ("copertura", "Quota coperta dal sole", 0.60, 0.1, 0.95, 0.05, "%.2f", "Di solito 50-70% in un anno."), ("rend_vecchio", "Rendimento dello scaldacqua/caldaia attuale", 0.80, 0.4, 1.1, 0.01, "%.2f", None),
            ("mq", "Superficie dei collettori (m²)", 4.0, 1.0, 500.0, 0.5, "%.1f", None)],
    "col": [("n", "Numero di colonnine", 4.0, 1.0, 500.0, 1.0, "%.0f", None), ("kw", "Potenza di ogni colonnina (kW)", 22.0, 3.0, 350.0, 1.0, "%.0f", None),
            ("kwh_anno", "Energia erogata da ogni colonnina (kWh/anno)", 8000.0, 0.0, 500000.0, 500.0, "%.0f", None), ("prezzo_vendita", "Prezzo di vendita agli utenti (€/kWh)", 0.55, 0.0, 2.0, 0.01, "%.2f", None),
            ("costo_energia", "Costo dell'energia per la ESCo (€/kWh)", 0.28, 0.0, 2.0, 0.01, "%.2f", None), ("gestione", "Gestione e pagamenti (€/anno per colonnina)", 250.0, 0.0, 10000.0, 10.0, "%.0f", "Software, canone di rete, assistenza.")],
}
DEFAULT_COMUNI = {"prezzo_gas": 1.10, "prezzo_el": 0.30, "aumento_energia_pct": 2.0, "degrado_pct": 0.5, "ricarico_pct": 20.0, "anni": 20,
                  "regime": "Privato - prima casa (detrazione 50%)", "iva_pct": 10.0, "detrazione_pct": 50.0, "detrazione_anni": 10}
DETRAZIONE_TIPO = {"led": 0.0}                       # il solo relamping di norma non e' detraibile (lo e' dentro una ristrutturazione): si puo' correggere a mano


def _n(x):
    return f"{x:,.0f}".replace(",", ".")


def default_params(tipo):
    d = dict(DEFAULT_COMUNI)
    d.update({k: v for k, _l, v, *_ in PARAMETRI[tipo]})
    if tipo in DETRAZIONE_TIPO:
        d["detrazione_pct"] = DETRAZIONE_TIPO[tipo]
    return d


def stima(tipo, p):
    """Cosa fa guadagnare l'intervento: {risp_gas_smc, risp_el_kwh (negativo = piu' elettricita'), ricavi_altri (€/anno), manutenzione (€/anno), nota}."""
    f = fv._f
    r = {"risp_gas_smc": 0.0, "risp_el_kwh": 0.0, "ricavi_altri": 0.0, "manutenzione": 0.0, "nota": ""}
    if tipo == "pdc":
        calore = f(p.get("gas_smc")) * KWH_SMC * f(p.get("rend_vecchio"))
        el = calore / max(0.1, f(p.get("scop")))
        r.update(risp_gas_smc=f(p.get("gas_smc")), risp_el_kwh=-el, manutenzione=f(p.get("kw")) * 8, nota=f"Calore da produrre {_n(calore)} kWh/anno, elettricità necessaria {_n(el)} kWh.")
    elif tipo == "cal":
        vecchio, nuovo = max(0.01, f(p.get("rend_vecchio"))), max(0.01, f(p.get("rend_nuovo")))
        r.update(risp_gas_smc=max(0.0, f(p.get("gas_smc")) * (1 - vecchio / nuovo)), manutenzione=0.0, nota="Risparmio = gas × (1 − rendimento vecchio ÷ rendimento nuovo).")
    elif tipo == "cap":
        kwh = max(0.0, f(p.get("u_prima")) - f(p.get("u_dopo"))) * f(p.get("mq_involucro")) * f(p.get("gg")) * 24 / 1000
        smc = kwh / KWH_SMC / max(0.1, f(p.get("rend_vecchio")))
        r.update(risp_gas_smc=min(smc, f(p.get("gas_smc"))), nota=f"Dispersioni evitate {_n(kwh)} kWh/anno ({_n(smc)} Smc), non oltre il gas consumato oggi.")
    elif tipo == "led":
        kwh = f(p.get("punti")) * max(0.0, f(p.get("w_vecchi")) - f(p.get("w_nuovi"))) * f(p.get("ore")) / 1000
        r.update(risp_el_kwh=kwh, ricavi_altri=f(p.get("manut_risp")), nota=f"{_n(kwh)} kWh in meno all'anno.")
    elif tipo == "sol":
        kwh_giorno = f(p.get("persone")) * f(p.get("litri")) * 4.186 * 35 / 3600
        utile = kwh_giorno * 365 * f(p.get("copertura"))
        r.update(risp_gas_smc=utile / KWH_SMC / max(0.1, f(p.get("rend_vecchio"))), manutenzione=60.0, nota=f"Fabbisogno di acqua calda {_n(kwh_giorno * 365)} kWh/anno, coperto dal sole per {_n(utile)} kWh.")
    elif tipo == "col":
        n = f(p.get("n"))
        margine = max(0.0, f(p.get("prezzo_vendita")) - f(p.get("costo_energia")))
        r.update(ricavi_altri=n * f(p.get("kwh_anno")) * margine, manutenzione=n * f(p.get("gestione")), nota=f"Margine di {margine:.2f} €/kWh su {_n(n * f(p.get('kwh_anno')))} kWh venduti all'anno.")
    return r


def voci_standard(tipo, p):
    """Voci di costo di partenza (acquisto + posa, IVA esclusa) per i dati indicati: da correggere con il listino."""
    f = fv._f
    v = []
    if tipo == "pdc":
        kw = f(p.get("kw"))
        v = [("Pompa di calore", kw, "kW", 650.0), ("Accumulo e puffer", 1, "corpo", 900.0), ("Idraulica e collegamenti", kw, "kW", 120.0), ("Smaltimento vecchia caldaia", 1, "corpo", 350.0),
             ("Installazione (manodopera)", kw, "kW", 140.0), ("Pratiche e contabilizzazione", 1, "corpo", 400.0)]
    elif tipo == "cal":
        kw = f(p.get("kw"))
        v = [("Caldaia a condensazione", kw, "kW", 75.0), ("Regolazione, termostati e valvole", 1, "corpo", 700.0), ("Fumisteria e scarico condensa", 1, "corpo", 450.0), ("Installazione (manodopera)", 1, "corpo", 900.0), ("Pratiche", 1, "corpo", 250.0)]
    elif tipo == "cap":
        mq = f(p.get("mq_involucro"))
        v = [("Isolante e collanti", mq, "m²", 38.0), ("Intonaco e finitura", mq, "m²", 22.0), ("Ponteggio", mq, "m²", 14.0), ("Posa (manodopera)", mq, "m²", 32.0), ("Progetto, APE e pratiche", 1, "corpo", 900.0)]
    elif tipo == "led":
        n = f(p.get("punti"))
        v = [("Corpo illuminante LED", n, "pz", 38.0), ("Posa (manodopera)", n, "pz", 14.0), ("Smaltimento vecchie lampade", n, "pz", 1.5), ("Progetto illuminotecnico", 1, "corpo", 400.0)]
    elif tipo == "sol":
        mq = f(p.get("mq"))
        v = [("Collettori solari", mq, "m²", 420.0), ("Bollitore con scambiatore", 1, "corpo", 1500.0), ("Circuito, pompa e regolazione", 1, "corpo", 900.0), ("Installazione (manodopera)", 1, "corpo", 1200.0), ("Pratiche", 1, "corpo", 300.0)]
    elif tipo == "col":
        n, kw = f(p.get("n")), f(p.get("kw"))
        v = [("Colonnina di ricarica", n, "pz", 700.0 + kw * 60), ("Quadro e protezioni", 1, "corpo", 1200.0), ("Linea di alimentazione", 1, "corpo", 2500.0), ("Posa (manodopera)", n, "pz", 600.0), ("Pratiche e connessione", 1, "corpo", 800.0)]
    return [{"Voce": a, "Quantita": q, "Um": u, "Costo_unit": c} for a, q, u, c in v if q]


def calcola(tipo, voci, p):
    """Prezzo al cliente, detrazione, risparmio e rientro, con la stessa logica del fotovoltaico."""
    q = {**default_params(tipo), **{k: v for k, v in (p or {}).items()}}
    f = fv._f
    costo = sum(v["Quantita"] * v["Costo_unit"] for v in voci)
    imponibile = round(costo * (1 + f(q["ricarico_pct"]) / 100), 2)
    iva = round(imponibile * f(q["iva_pct"]) / 100, 2)
    totale = round(imponibile + iva, 2)
    detr = round(min(totale, fv.TETTO_SPESA_DETRAZIONE) * f(q["detrazione_pct"]) / 100, 2)
    anni_d = max(1, int(f(q["detrazione_anni"], 10)))
    s = stima(tipo, q)
    agg, deg = f(q["aumento_energia_pct"]) / 100, f(q["degrado_pct"]) / 100
    flusso, cum, rientro = [], -totale, None
    for y in range(1, max(1, int(f(q["anni"], 20))) + 1):
        k = (1 - deg) ** (y - 1) * (1 + agg) ** (y - 1)
        risp = (s["risp_gas_smc"] * f(q["prezzo_gas"]) + s["risp_el_kwh"] * f(q["prezzo_el"])) * k
        altri = s["ricavi_altri"] * (1 - deg) ** (y - 1)
        d = detr / anni_d if y <= anni_d else 0.0
        netto = risp + altri + d - s["manutenzione"]
        prima, cum = cum, cum + netto
        if rientro is None and cum >= 0:
            rientro = round(y - 1 + (-prima / netto if netto else 0), 1)
        flusso.append({"Anno": y, "Risparmio €": round(risp), "Altri ricavi €": round(altri), "Detrazione €": round(d), "Manutenzione €": round(-s["manutenzione"]), "Flusso €": round(netto), "Cumulato €": round(cum)})
    kpi = {"costo": round(costo, 2), "imponibile": imponibile, "iva": iva, "totale": totale, "margine": round(imponibile - costo, 2), "detrazione": detr, "netto_detrazione": round(totale - detr, 2),
           "risparmio_anno1": flusso[0]["Risparmio €"] + flusso[0]["Altri ricavi €"] if flusso else 0, "rientro_anni": rientro, "guadagno_finale": flusso[-1]["Cumulato €"] if flusso else 0,
           "risp_gas_smc": round(s["risp_gas_smc"]), "risp_el_kwh": round(s["risp_el_kwh"])}
    avvisi = []
    if not voci:
        avvisi.append("Inserisci almeno una voce di costo.")
    if tipo == "pdc" and f(q.get("scop")) < 2.8:
        avvisi.append("Con un SCOP così basso la pompa di calore conviene poco: verifica l'isolamento e le temperature dei terminali.")
    if tipo == "cal" and f(q.get("rend_nuovo")) <= f(q.get("rend_vecchio")):
        avvisi.append("Il rendimento nuovo non supera quello attuale: nessun risparmio.")
    if tipo == "cap" and f(q.get("u_dopo")) >= f(q.get("u_prima")):
        avvisi.append("La trasmittanza dopo non è migliore di quella di prima: nessun risparmio.")
    if tipo == "led" and f(q.get("w_nuovi")) >= f(q.get("w_vecchi")):
        avvisi.append("Il LED consuma quanto o più dell'impianto attuale: nessun risparmio.")
    if tipo == "col" and f(q.get("prezzo_vendita")) <= f(q.get("costo_energia")):
        avvisi.append("Il prezzo di vendita non supera il costo dell'energia: le colonnine non guadagnano.")
    if costo and kpi["risparmio_anno1"] <= 0:
        avvisi.append("L'intervento non genera risparmio con questi dati.")
    return {"params": q, "kpi": kpi, "flusso": flusso, "avvisi": avvisi, "stima": s}


def intervento_per_esco(tipo, kpi, stima_, nome=None):
    """Riga per la tabella interventi dello strumento ESCo (investimento = costo per chi realizza)."""
    return {"Intervento": nome or TIPI[tipo], "Tipo": {"pdc": "Pompa di calore", "cal": "Caldaia e regolazione", "cap": "Isolamento (cappotto, serramenti)", "led": "Illuminazione LED", "sol": "Altro", "col": "Altro"}[tipo],
            "Investimento": kpi["costo"], "Risp_El_kWh": round(stima_["risp_el_kwh"]), "Risp_Gas_Smc": round(stima_["risp_gas_smc"]), "Altri_ricavi": round(stima_["ricavi_altri"], 2),
            "Manutenzione": round(stima_["manutenzione"], 2), "Incentivo": 0.0, "Incentivo_anni": 1.0}
