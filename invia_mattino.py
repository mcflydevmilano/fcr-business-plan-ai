"""invia_mattino.py - Manda il riepilogo personale del mattino (email a ciascuno e messaggio su Slack).

Da lanciare ogni mattina dal server (vedi deploy/fcr-mattino.timer). Legge le stesse impostazioni della suite (DATABASE_URL, SMTP_*, SLACK_*).
  python3 invia_mattino.py            invia se e' acceso, e' un giorno feriale e non e' gia' partito oggi
  python3 invia_mattino.py --forza    invia comunque (per provare)
  python3 invia_mattino.py --prova    stampa il riepilogo di ciascuno senza spedire
"""
import sys

import mattino
import permessi
import storage


def main(argv=None):
    argv = argv or sys.argv[1:]
    if "--prova" in argv:
        pc = permessi.carica_config()
        for u, mail in mattino._destinatari():
            sez = mattino.sezioni(u, permessi.profilo_di(u, pc), permessi.moduli_consentiti(u, pc))
            print(f"--- {u['username']} <{mail}>\n{mattino.testo(u, sez)}\n")
        return 0
    rep = mattino.invia_tutti(forza="--forza" in argv)
    print(rep)
    return 1 if rep["errori"] else 0


if __name__ == "__main__":
    sys.exit(main())
