"""utilita.py - Campanella degli avvisi e «Esporta tutto in Excel» (dati salvati di tutti gli strumenti consentiti)."""
import datetime as dt
import io

import calendario
import registro
import storage


def _ultimo(m):
    el = storage.elenca_pratiche(modulo=m)
    return storage.carica_pratica(el[0]["nome"], modulo=m) if el else None


def payload_salvati(consentiti):
    """{modulo: ultimo salvataggio non dimostrativo} per gli strumenti che l'utente puo' vedere."""
    out = {}
    for m in storage.MODULI_ARCHIVIO:
        if m in ("cfg", "al", "pz") or (consentiti is not None and m not in consentiti):
            continue
        try:
            p = _ultimo(m)
        except Exception:
            p = None
        if p:
            out[m] = p
    return out


def avvisi(consentiti, oggi=None, giorni=7):
    """Scadute e in arrivo entro `giorni`, solo dai dati salvati (leggero: usato a ogni caricamento)."""
    pay = storage.cache_lettura("util_pay|" + ",".join(sorted(consentiti or [])), lambda: {m: p for m, p in payload_salvati(consentiti).items() if m in calendario.MODULI_CALENDARIO}, ttl=120)
    return calendario.eventi(pay, oggi or dt.date.today(), giorni)


def excel_tutto(consentiti):
    """Bytes di un .xlsx: un foglio per ogni tabella salvata. Foglio «Indice» in testa."""
    import pandas as pd
    pay = payload_salvati(consentiti)
    buf = io.BytesIO()
    indice, usati = [], set()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for m, p in pay.items():
            if not isinstance(p, dict):
                continue
            for k, v in p.items():
                if isinstance(v, list) and v and all(isinstance(r, dict) for r in v):
                    nome = f"{m}_{k}"[:31]
                    n = 1
                    while nome in usati:
                        n += 1
                        nome = f"{m}_{k}"[:28] + f"_{n}"
                    usati.add(nome)
                    pd.DataFrame(v).to_excel(xw, index=False, sheet_name=nome)
                    indice.append({"Foglio": nome, "Strumento": registro.NOMI_MODULO.get(m, m), "Righe": len(v)})
        pd.DataFrame(indice or [{"Foglio": "-", "Strumento": "Nessun dato salvato", "Righe": 0}]).to_excel(xw, index=False, sheet_name="Indice")
        xw.book.move_sheet("Indice", offset=-len(xw.book.sheetnames) + 1)
    return buf.getvalue(), len(indice)


def render_sidebar(consentiti):
    import streamlit as st
    ev = []
    try:
        ev = avvisi(consentiti)
    except Exception:
        pass
    scad = sum(1 for e in ev if e["Giorni"] < 0)
    with st.expander(f"🔔 Avvisi ({len(ev)})" if ev else "🔔 Avvisi"):
        if not ev:
            st.caption("Nessuna scadenza nei prossimi 7 giorni.")
        for e in ev[:8]:
            st.markdown(("🔴 " if e["Giorni"] < 0 else "🟡 ") + f"**{e['Titolo']}** · {e['Categoria']} · {e['Data']}")
        if scad:
            st.caption(f"{scad} già scadute.")
        if len(ev) > 8:
            st.caption(f"…e altre {len(ev) - 8} nel Calendario.")
    with st.expander("📦 Esporta tutto in Excel"):
        st.caption("Tutti i dati salvati degli strumenti che puoi vedere, un foglio per tabella.")
        if st.button("Prepara il file", key="util_xl", width="stretch"):
            st.session_state["_util_xl"] = excel_tutto(consentiti)
        r = st.session_state.get("_util_xl")
        if r:
            st.download_button(f"⬇️ Scarica ({r[1]} fogli)", r[0], f"FCR_tutti_i_dati_{dt.date.today().isoformat()}.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="util_xl_dl", width="stretch")
