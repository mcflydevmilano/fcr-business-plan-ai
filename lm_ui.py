"""lm_ui.py - Interfaccia di Lettere e modelli."""
import datetime as dt

import streamlit as st

import guida
import lm
import ru
import storage
import theme
from ui_util import cantieri_rubrica, sola_lettura

ss = st.session_state


def _contatti():
    try:
        el = storage.elenca_pratiche(modulo="ru")
        righe = (storage.carica_pratica(el[0]["nome"], modulo="ru") or {}).get("contatti", []) if el else []
        return [c for c in ru.normalizza_contatti(righe)[0] if c.get("Nome")]
    except Exception:
        return []


def _scrivi(cfg, utente, audit):
    mod = lm.modelli(cfg)
    chiavi = list(mod)
    k = st.selectbox("Che documento vuoi scrivere", chiavi, format_func=lambda x: mod[x]["titolo"], key="lm_modello")
    m = mod[k]
    contatti, cantieri = _contatti(), cantieri_rubrica()
    c1, c2 = st.columns(2)
    et_c = [f"{c['Nome']}" + (f" · {c['Ruolo']}" if c.get("Ruolo") else "") for c in contatti]
    sc = c1.selectbox("A chi (dalla Rubrica)", ["— scrivo io —"] + et_c, key="lm_dest")
    contatto = contatti[et_c.index(sc)] if sc != "— scrivo io —" else None
    et_k = [f"{c['Codice']} · {c['Cantiere']}" for c in cantieri if c.get("Codice")]
    sk = c2.selectbox("Cantiere (dalla Rubrica)", ["—"] + et_k, key="lm_cant")
    cantiere = next((c for c in cantieri if f"{c['Codice']} · {c['Cantiere']}" == sk), None) if sk != "—" else None
    if not contatti:
        st.caption("Nella Rubrica non ci sono ancora contatti: scrivi il destinatario qui sotto.")
    auto = lm.valori_automatici(cfg["azienda"], contatto, cantiere)
    st.markdown("**Completa i dati**")
    a, b, c = st.columns(3)
    auto["destinatario"] = a.text_input("Destinatario", auto["destinatario"], key=f"lm_d_{sc}")
    auto["referente"] = b.text_input("Alla cortese attenzione di", auto["referente"], key=f"lm_r_{sc}")
    auto["luogo"] = c.text_input("Luogo", auto["luogo"], key="lm_luogo")
    d1, d2, d3 = st.columns(3)
    auto["cantiere"] = d1.text_input("Cantiere", auto["cantiere"], key=f"lm_k_{sk}")
    auto["indirizzo_cantiere"] = d2.text_input("Indirizzo del cantiere", auto["indirizzo_cantiere"], key=f"lm_i_{sk}")
    auto["cliente"] = d3.text_input("Cliente / committente", auto["cliente"], key=f"lm_cl_{sk}")
    data_lettera = st.date_input("Data della lettera", value=dt.date.today(), format="DD/MM/YYYY", key="lm_data")
    auto["data"] = data_lettera
    val = dict(auto)
    for ch, et, tipo in lm.campi(m):
        key = f"lm_f_{k}_{ch}"
        if tipo == "data":
            val[ch] = st.date_input(et, value=None, format="DD/MM/YYYY", key=key)
        elif tipo == "lungo":
            val[ch] = st.text_area(et, key=key, height=100)
        else:
            val[ch] = st.text_input(et, key=key)
    oggetto, corpo, mancanti = lm.compila(m, val)
    st.markdown("#### Anteprima")
    if mancanti:
        st.warning("Da completare: " + ", ".join(mancanti) + ". I campi vuoti restano tra [parentesi quadre] nel documento.")
    st.markdown(f"**Oggetto:** {oggetto}")
    st.text(corpo)
    dest = "\n".join(x for x in [f"Spett.le {auto['destinatario']}" if auto["destinatario"] else "", f"c.a. {auto['referente']}" if auto["referente"] else "", auto.get("email_destinatario", "")] if x)
    word = lm.docx_lettera(cfg["azienda"], dest, oggetto, corpo, f"{auto['luogo']}, {data_lettera:%d/%m/%Y}".strip(", "), auto["firmatario"], auto["ruolo_firmatario"])
    if st.download_button("📥 Scarica in Word", word, file_name=f"{m['titolo'].split(' (')[0].lower().replace(' ', '_')}_{data_lettera:%Y%m%d}.docx", key="lm_dl",
                          mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
        audit("lm_lettera", m["titolo"])
    if contatto and contatto.get("Email"):
        st.markdown(f"[✉️ Apri la mail a {contatto['Email']}]({ru.link_email(contatto['Email'], oggetto, corpo)})")


def _modelli(cfg, utente, audit):
    st.caption("Cambia il testo dei modelli o creane di nuovi. I campi tra doppie graffe, come {{cantiere}}, si compilano da soli o ti vengono chiesti. "
               "Campi che arrivano dalla Rubrica: " + ", ".join("{{" + k + "}}" for k in lm.AUTO) + ".")
    mod = lm.modelli(cfg)
    scelta = st.selectbox("Modello", list(mod) + ["+ nuovo modello"], format_func=lambda x: mod[x]["titolo"] if x in mod else "+ Crea un nuovo modello", key="lm_ed_sel")
    m = mod.get(scelta, {"titolo": "", "oggetto": "", "corpo": ""})
    titolo = st.text_input("Nome del modello", m["titolo"], key=f"lm_ed_t_{scelta}")
    ogg = st.text_input("Oggetto", m["oggetto"], key=f"lm_ed_o_{scelta}")
    corpo = st.text_area("Testo", m["corpo"], height=320, key=f"lm_ed_c_{scelta}")
    a, b = st.columns(2)
    if a.button("💾 Salva il modello", type="primary", key="lm_ed_salva", disabled=sola_lettura() or not titolo.strip() or not corpo.strip()):
        chiave = scelta if scelta in mod else "mio_" + "".join(ch for ch in titolo.lower() if ch.isalnum())[:30]
        cfg["modelli"][chiave] = {"titolo": titolo.strip(), "oggetto": ogg.strip(), "corpo": corpo}
        lm.salva_cfg(cfg, utente["username"])
        audit("lm_modello", titolo.strip())
        st.rerun()
    if scelta in mod and (mod[scelta].get("modificato") or not mod[scelta]["base"]) and b.button("↩️ Ripristina il testo originale" if mod[scelta]["base"] else "🗑️ Elimina il modello", key="lm_ed_ripr", disabled=sola_lettura()):
        cfg["modelli"].pop(scelta, None)
        lm.salva_cfg(cfg, utente["username"])
        audit("lm_modello_ripristinato" if mod[scelta]["base"] else "lm_modello_eliminato", mod[scelta]["titolo"])
        st.rerun()
    st.info("I modelli di diffida e di incarico sono una base: falli rivedere da un legale prima dell'uso.")


def _azienda(cfg, utente, audit):
    az = cfg["azienda"]
    st.caption("Questi dati compaiono in testa e in fondo a ogni lettera.")
    c1, c2 = st.columns(2)
    nome = c1.text_input("Azienda", az["azienda"], key="lm_az_n")
    ind = c2.text_input("Indirizzo", az["indirizzo"], key="lm_az_i")
    c3, c4, c5 = st.columns(3)
    luogo = c3.text_input("Luogo (per la data)", az["luogo"], key="lm_az_l")
    firm = c4.text_input("Firmatario", az["firmatario"], key="lm_az_f")
    ruolo = c5.text_input("Ruolo del firmatario", az["ruolo_firmatario"], key="lm_az_r")
    cont = st.text_input("Contatti in testa alla lettera (telefono, PEC…)", az["contatti"], key="lm_az_c")
    if st.button("💾 Salva", type="primary", key="lm_az_salva", disabled=sola_lettura()):
        cfg["azienda"] = {"azienda": nome, "indirizzo": ind, "luogo": luogo, "firmatario": firm, "ruolo_firmatario": ruolo, "contatti": cont}
        lm.salva_cfg(cfg, utente["username"])
        audit("lm_azienda", nome)
        st.success("Dati salvati.")
        st.rerun()


def render(fcr_uri, audit, utente, profilo, utenti_secrets=None):
    audit = audit or (lambda *a, **k: None)
    st.markdown(theme.hero(fcr_uri, "Lettere e modelli", "Scegli il modello e il destinatario dalla Rubrica: i dati si compilano da soli e scarichi il Word."), unsafe_allow_html=True)
    guida.mostra("lm")
    cfg = lm.carica_cfg()
    gestore = utente.get("ruolo") == "admin" or profilo in ("presidente", "direzione", "amministrazione", "commerciale", "accesso completo")
    tabs = st.tabs(["✉️ Scrivi una lettera", "📚 Modelli"] + (["🏢 Dati azienda"] if gestore else []))
    with tabs[0]:
        _scrivi(cfg, utente, audit)
    with tabs[1]:
        _modelli(cfg, utente, audit)
    if gestore:
        with tabs[2]:
            _azienda(cfg, utente, audit)
