"""
ui_util.py - Tabelle modificabili che conservano le modifiche anche cambiando modulo.

st.data_editor tiene le modifiche in uno stato interno che Streamlit dimentica quando il widget non viene disegnato (per esempio
tornando all'Hub). Qui la tabella "vera" sta in st.session_state[chiave]; a ogni modifica una callback la aggiorna e cambia la
chiave del widget (nuova versione), cosi' il widget riparte pulito dai dati aggiornati.
"""
import pandas as pd
import streamlit as st

ss = st.session_state


def _applica_modifiche(df, stato):
    df = df.copy().reset_index(drop=True)
    for i, ch in (stato.get("edited_rows") or {}).items():
        for col, val in ch.items():
            if col in df.columns and int(i) < len(df):
                df[col] = df[col].astype(object)
                df.at[int(i), col] = val
    canc = [int(i) for i in (stato.get("deleted_rows") or []) if int(i) < len(df)]
    if canc:
        df = df.drop(df.index[canc]).reset_index(drop=True)
    agg = stato.get("added_rows") or []
    if agg:
        df = pd.concat([df, pd.DataFrame(agg, columns=df.columns)], ignore_index=True)
    return df


def tabella_modificabile(chiave, df_iniziale, column_config=None, altezza=None, num_rows="dynamic"):
    """Mostra la tabella e restituisce il DataFrame aggiornato. `chiave` identifica i dati in session_state (usa un prefisso del modulo)."""
    if chiave not in ss:
        ss[chiave] = df_iniziale.copy()
    ver = ss.setdefault(chiave + "_v", 0)
    key_ed = f"ed_{chiave}_{ver}"                      # nessun prefisso del modulo: lo stato del widget non va ripristinato a mano

    def _cb():
        ss[chiave] = _applica_modifiche(ss[chiave], ss.get(key_ed) or {})
        ss[chiave + "_v"] = ver + 1

    kw = {"height": altezza} if altezza else {}
    st.data_editor(ss[chiave], key=key_ed, on_change=_cb, num_rows=num_rows, hide_index=True, column_config=column_config or {},
                   width="stretch", **kw)
    return ss[chiave]


def sostituisci_tabella(chiave, df):
    """Sostituisce i dati (es. dopo una generazione) e riavvia l'editor con la nuova versione."""
    ss[chiave] = df.copy()
    ss[chiave + "_v"] = ss.get(chiave + "_v", 0) + 1


def pannello_archivio(modulo, etichetta, raccogli, applica, audit=None, utente=""):
    """Riquadro 'Salva / apri' per un modulo. `raccogli()` -> payload (dict JSON); `applica(payload, nome)` ripristina i dati."""
    import storage
    audit = audit or (lambda *a, **k: None)
    with st.expander(f"💾 Salva e riapri {etichetta}"):
        if not storage.database_persistente():
            st.warning("Database esterno non configurato: i salvataggi si perdono al riavvio dell'app (vedi DATABASE_URL nei Secrets).")
        a, b = st.columns([3, 1])
        nome = a.text_input("Nome", key=f"sv_nome_{modulo}", placeholder="es. Portafoglio 2027")
        b.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
        if b.button("💾 Salva", key=f"sv_salva_{modulo}", width="stretch"):
            try:
                storage.salva_pratica(nome, raccogli(), autore=utente, modulo=modulo)
                audit(f"{modulo}_salvato", nome)
                st.success("Salvato.")
            except Exception as e:
                st.error(f"Impossibile salvare: {e}")
        try:
            elenco = storage.elenca_pratiche(modulo=modulo)
        except Exception as e:
            elenco = []
            st.error(f"Database non disponibile: {e}")
        if elenco:
            nomi = [p["nome"] for p in elenco]
            scelta = st.selectbox("Salvati", nomi, key=f"sv_scelta_{modulo}",
                                  format_func=lambda n: next(f"{p['nome']}  ({p['aggiornato'][:16]}" + (f", {p['autore']}" if p["autore"] else "") + ")" for p in elenco if p["nome"] == n))
            c1, c2 = st.columns(2)
            if c1.button("📂 Apri", key=f"sv_apri_{modulo}", width="stretch"):
                payload = storage.carica_pratica(scelta, modulo=modulo)
                if payload:
                    audit(f"{modulo}_aperto", scelta)
                    applica(payload, scelta)
                    st.rerun()
            if c2.button("🗑️ Elimina", key=f"sv_elimina_{modulo}", width="stretch"):
                storage.elimina_pratica(scelta, modulo=modulo)
                audit(f"{modulo}_eliminato", scelta)
                st.rerun()
        else:
            st.caption("Nessun salvataggio per questo modulo.")
