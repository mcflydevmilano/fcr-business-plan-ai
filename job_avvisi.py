"""
job_avvisi.py - Controllo programmato: manda gli avvisi del Cruscotto (email, chat interna, telefono) e, il lunedi', il rapporto PDF di direzione.

Non serve che qualcuno apra la suite. Si lancia da riga di comando, da cron sul vostro server o da GitHub Actions (vedi avvisi.yml):
    python job_avvisi.py                 # avvisi (una volta al giorno per lo stesso problema) + rapporto se e' lunedi'
    python job_avvisi.py --rapporto      # manda il rapporto PDF anche se non e' lunedi'
    python job_avvisi.py --dry-run       # mostra cosa invierebbe, senza inviare
Legge l'ULTIMO salvataggio di ogni strumento (mai i dati dimostrativi). Variabili d'ambiente: DATABASE_URL, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
MAIL_FROM, CHAT_KEY, TELEGRAM_BOT_TOKEN, NTFY_URL, APP_URL. Le regole (chi riceve cosa) si impostano nel Cruscotto, riquadro «Avvisi».
"""
import datetime as dt
import sys

import avvisi_dd
import dd
import permessi
import riepilogo
import storage


def prepara(path=None, oggi=None):
    """(righe, generale, azioni, fonti) dei semafori dall'ultimo salvataggio di ogni strumento."""
    oggi = oggi or dt.date.today()
    payloads, fonti = riepilogo.raccogli(path)
    metriche = {}
    for m in dd.MODULI_METRICHE:
        try:
            metriche[m] = dd.metriche_da_payload(m, payloads.get(m), oggi)
        except Exception:
            metriche[m] = None
    righe, gen, azioni = dd.semafori(metriche)
    nomi = permessi.NOMI
    return righe, gen, azioni, {nomi.get(m, m): f"salvataggio «{n}»" for m, n in fonti.items()}


def esegui(path=None, oggi=None, forza_rapporto=False, dry_run=False):
    """Restituisce un dizionario con l'esito (utile ai test)."""
    oggi = oggi or dt.date.today()
    righe, gen, azioni, fonti = prepara(path, oggi)
    cfg = avvisi_dd.carica_cfg(path)
    out = {"semafori": sum(1 for r in righe if r["Stato"] in ("bad", "warn")), "avvisi": None, "rapporto": None}
    try:
        noti = [u["username"] for u in storage.elenca_utenti(path)]
    except Exception:
        noti = []
    if dry_run:
        out["avvisi"] = [(r["area"], [x["Indicatore"] for x in p]) for r, p in avvisi_dd.da_inviare(righe, cfg, (avvisi_dd._carica_stato(path).get("inviati") or {}), oggi.isoformat())]
        out["rapporto"] = {"saltato": "dry-run", "previsto": bool(cfg["report"]["attivo"] and (oggi.weekday() == 0 or forza_rapporto))}
        return out
    if cfg["regole"] and cfg["auto"]:
        out["avvisi"] = avvisi_dd.invia(righe, cfg, path, oggi=oggi.isoformat(), utenti_noti=noti, sincrono=True)
    if cfg["report"]["attivo"] and (oggi.weekday() == 0 or forza_rapporto):
        out["rapporto"] = avvisi_dd.invia_rapporto(righe, gen, azioni, fonti, cfg, path, forza=False, oggi=oggi.isoformat())
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    out = esegui(forza_rapporto="--rapporto" in argv, dry_run="--dry-run" in argv)
    print(f"Semafori da guardare: {out['semafori']}")
    print("Avvisi:", out["avvisi"] if out["avvisi"] is not None else "nessuna regola attiva (o invio automatico spento)")
    print("Rapporto:", out["rapporto"] if out["rapporto"] is not None else "non previsto oggi")
    errori = (out["avvisi"] or {}).get("errori", []) if isinstance(out["avvisi"], dict) else []
    errori += (out["rapporto"] or {}).get("errori", []) if isinstance(out["rapporto"], dict) else []
    for e in errori:
        print("ERRORE:", e)
    return 1 if errori else 0


if __name__ == "__main__":
    sys.exit(main())
