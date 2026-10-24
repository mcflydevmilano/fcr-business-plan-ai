"""
genera_demo.py - Prepara demo_dati.json: un salvataggio dimostrativo per ogni strumento, con dati coerenti (stessi cantieri, clienti e persone).
Uso (dalla cartella dell'app):  python genera_demo.py
Apre ogni strumento con gli esempi accesi e lo salva con il pulsante vero «Salva»; poi aggiunge a mano i dati dei moduli senza esempio.
Il file prodotto lo legge demo.py (pulsante «Carica dati dimostrativi» del Cruscotto).
"""
import datetime as dt
import json
import os
import sys
import tempfile

os.environ["ESEMPI_ATTIVI"] = "1"
os.environ["APP_PASSWORD"] = "segreta"
QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)

import storage  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

NOME = "DEMO - Esempio"
OGGI = dt.date.today()
APP = os.path.join(QUI, "app.py")
MODULI_UI = ["sc", "cf", "pv", "sl", "ga", "fo", "sx", "mz", "og", "rp", "gt", "bk", "oa", "lg", "pe", "ru", "bp"]


def da_app(m, db):
    at = AppTest.from_file(APP, default_timeout=240)
    at.session_state["utente"] = {"username": "root", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = m
    at.run()
    if at.exception:
        raise RuntimeError(f"{m}: {[e.value for e in at.exception]}")
    at.text_input(key=f"sv_nome_{m}").set_value(NOME)
    at.button(key=f"sv_salva_{m}").click().run()
    return storage.carica_pratica(NOME, db, m)


def credit(db):
    at = AppTest.from_file(APP, default_timeout=240)
    at.session_state["utente"] = {"username": "root", "ruolo": "admin", "origine": "app_password"}
    at.session_state["active_module"] = "credit"
    at.run()
    at.text_input(key="pratica_nome").set_value(NOME)
    [b for b in at.button if b.label.startswith("💾 Salva pratica")][0].click().run()
    return storage.carica_pratica(NOME, db, "credit")


def main():
    db = os.path.join(tempfile.mkdtemp(), "demo.db")
    storage.DB_PATH = db
    out = {"_base": OGGI.isoformat()}
    for m in MODULI_UI:
        try:
            out[m] = da_app(m, db)
            print("ok", m)
        except Exception as e:
            print("SALTATO", m, e)
    try:
        out["credit"] = credit(db)
        print("ok credit")
    except Exception as e:
        print("SALTATO credit", e)
    import demo_extra
    out.update(demo_extra.payloads(OGGI))
    out = {k: v for k, v in out.items() if v}
    with open(os.path.join(QUI, "demo_dati.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, default=str)
    print("scritto demo_dati.json:", sorted(k for k in out if k != "_base"))


if __name__ == "__main__":
    main()
