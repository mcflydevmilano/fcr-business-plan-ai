"""
registro.py - Descrive in italiano COSA e' cambiato tra due versioni di un salvataggio (per il registro attivita').
Puro e senza Streamlit: confronta i dati salvati (liste di righe, parametri) e restituisce una frase breve.

Esempi:  «Fasi: +2 righe (Villa Lago · Strutture; …), 1 riga rimossa, 3 modificate · Parametri: soglia_pct 15→20»
"""
import json

ETICHETTE = {
    "fasi": "Fasi", "fermi": "Giorni di fermo", "rapp": "Rapportini", "segn": "Segnalazioni", "docs": "Documenti", "commesse": "Commesse", "sal": "SAL emessi", "costi": "Costi",
    "gare": "Gare", "doc": "Documenti", "contr": "Contratti", "off": "Offerte", "pers": "Persone", "docc": "Documenti di cantiere", "mezzi": "Mezzi", "uso": "Utilizzo mezzi",
    "scad": "Scadenze mezzi", "ris": "Risorse", "ass": "Assegnazioni", "cantieri": "Cantieri", "voci": "Voci di computo", "params": "Parametri", "df": "Tabella",
}
NOMI_MODULO = {"credit": "Credit Risk", "bp": "Business Plan", "cf": "Cash Flow", "pv": "Computo e Preventivo", "sc": "Scadenzario", "sl": "SAL e contabilità lavori", "ga": "Gare e offerte",
               "fo": "Fornitori", "sx": "Sicurezza", "mz": "Parco mezzi", "og": "Organico", "rp": "Rapportini", "gt": "Cronoprogramma", "cfg": "Permessi", "ru": "Rubrica e cantieri", "lg": "Studio legale", "bk": "Riconciliazione bancaria", "oa": "Ordini e approvazioni", "pe": "Persone e ruoli", "pz": "Prezziario", "rc": "Registro commerciale", "of": "Offerta e finanziamenti"}
MAX_ESEMPI = 2


def _s(v):
    return "" if v is None or v != v else str(v).strip()


def _riga_txt(r, n=3):
    """Riassunto breve di una riga: i primi valori non vuoti."""
    vals = [_s(v) for v in (r.values() if isinstance(r, dict) else [r]) if _s(v) and _s(v) not in ("0", "0.0")]
    return " · ".join(v[:28] for v in vals[:n])


def _canon(r):
    return json.dumps(r, sort_keys=True, ensure_ascii=False, default=str)


def _chiave_riga(r):
    vals = [_s(v) for v in r.values() if _s(v)]
    return " ".join(vals[:2]).lower()


def _campi_cambiati(vecchia, nuova):
    cambi = [f"{c} {_s(vecchia.get(c))[:18] or '—'}→{_s(x)[:18] or '—'}" for c, x in nuova.items() if _s(vecchia.get(c)) != _s(x)]
    return ", ".join(cambi[:3])


def _diff_tabella(vecchia, nuova):
    """(aggiunte, rimosse, modificate, esempi_aggiunte, esempi_modifiche). Con «Id» il confronto e' per Id; altrimenti per contenuto e, per le righe cambiate, per le prime due colonne."""
    vecchia = [r for r in vecchia if isinstance(r, dict)]
    nuova = [r for r in nuova if isinstance(r, dict)]
    ha_id = vecchia and nuova and all(r.get("Id") for r in vecchia + nuova)
    if ha_id:
        v, n = {r["Id"]: r for r in vecchia}, {r["Id"]: r for r in nuova}
        agg = [n[k] for k in n if k not in v]
        rim = [v[k] for k in v if k not in n]
        mod = [(v[k], n[k]) for k in n if k in v and _canon(n[k]) != _canon(v[k])]
    else:
        rest_v, agg = [(_canon(r), r) for r in vecchia], []
        for r in nuova:
            c = _canon(r)
            hit = next((x for x in rest_v if x[0] == c), None)
            if hit:
                rest_v.remove(hit)
            else:
                agg.append(r)
        rim, mod = [x[1] for x in rest_v], []
        for r in list(agg):
            k = _chiave_riga(r)
            hit = next((x for x in rim if _chiave_riga(x) == k and k), None)
            if hit is not None:
                mod.append((hit, r))
                rim.remove(hit)
                agg.remove(r)
    ess_a = [_riga_txt(x) for x in agg[:MAX_ESEMPI]]
    ess_m = [f"{_riga_txt(n_, 2)}: {_campi_cambiati(o, n_)}" for o, n_ in mod[:MAX_ESEMPI]]
    return len(agg), len(rim), len(mod), ess_a, ess_m


def _plur(n, sing, plur):
    return f"{n} {sing if n == 1 else plur}"


def descrivi_modifiche(vecchio, nuovo, max_len=900):
    """Frase che dice cosa e' cambiato. `vecchio` None = primo salvataggio."""
    pezzi = []
    if not isinstance(nuovo, dict):
        return "dati aggiornati" if vecchio != nuovo else "nessuna modifica ai dati"
    vecchio = vecchio if isinstance(vecchio, dict) else None
    for k, nv in nuovo.items():
        ov = (vecchio or {}).get(k)
        nome = ETICHETTE.get(k, k.replace("_", " ").capitalize())
        if isinstance(nv, list) and (not nv or isinstance(nv[0], dict)):
            ov = ov if isinstance(ov, list) else []
            if vecchio is None:
                if nv:
                    pezzi.append(f"{nome}: {_plur(len(nv), 'riga', 'righe')}")
                continue
            a, r, m, ess, ess_m = _diff_tabella(ov, nv)
            parti = []
            if a:
                parti.append(f"+{_plur(a, 'riga', 'righe')}" + (f" ({'; '.join(e for e in ess if e)})" if any(ess) else ""))
            if r:
                parti.append(_plur(r, "riga rimossa", "righe rimosse"))
            if m:
                parti.append(_plur(m, "modificata", "modificate") + (f" ({'; '.join(e for e in ess_m if e)})" if any(ess_m) else ""))
            if parti:
                pezzi.append(f"{nome}: " + ", ".join(parti))
        elif isinstance(nv, dict):
            ov = ov if isinstance(ov, dict) else {}
            cambi = [f"{c} {_s(ov.get(c))[:20] or '—'}→{_s(x)[:20] or '—'}" for c, x in nv.items() if _s(ov.get(c)) != _s(x) and not isinstance(x, (list, dict))]
            if cambi and vecchio is not None:
                pezzi.append(f"{nome}: " + ", ".join(cambi[:4]) + (f" (+{len(cambi) - 4})" if len(cambi) > 4 else ""))
        elif vecchio is not None and _s(ov) != _s(nv):
            pezzi.append(f"{nome}: {_s(ov)[:20] or '—'}→{_s(nv)[:20] or '—'}")
    if vecchio is not None:
        for k in vecchio:
            if k not in nuovo and vecchio[k]:
                pezzi.append(f"{ETICHETTE.get(k, k)} tolto")
    if not pezzi:
        return "salvato di nuovo senza modifiche ai dati" if vecchio is not None else "salvataggio vuoto"
    testo = (" · ".join(pezzi))
    return ("nuovo salvataggio: " if vecchio is None else "") + (testo if len(testo) <= max_len else testo[:max_len - 1] + "…")
