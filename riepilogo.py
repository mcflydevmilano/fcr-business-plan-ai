"""
riepilogo.py - Riepilogo mattutino via email: semafori e azioni del Cruscotto + scadenze scadute e dei prossimi giorni.

Si esegue da riga di comando (o da GitHub Actions, vedi .github/workflows/riepilogo.yml). Legge l'ULTIMO salvataggio di ogni modulo dal database
(DATABASE_URL) e invia la mail con SMTP. Variabili d'ambiente: DATABASE_URL, SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, MAIL_TO
(uno o piu' indirizzi separati da virgola), MAIL_FROM (opzionale). Con --dry-run stampa il testo senza inviare.
"""
import datetime as dt
import html
import os
import smtplib
import sys
from email.message import EmailMessage

import calendario
import dd
import storage
from core import fmt_num

SIMBOLO = {"ok": "OK", "warn": "ATTENZIONE", "bad": "CRITICO", "nd": "-"}
COLORE = {"ok": "#16a34a", "warn": "#d97706", "bad": "#dc2626", "nd": "#64748b"}


def raccogli(path=None):
    """Ultimo salvataggio di ogni modulo: ({modulo: payload}, {modulo: nome salvataggio})."""
    payloads, fonti = {}, {}
    for m in dd.MODULI_METRICHE:
        try:
            elenco = storage.elenca_pratiche(path, modulo=m)
            if elenco:
                payloads[m] = storage.carica_pratica(elenco[0]["nome"], path, m)
                fonti[m] = elenco[0]["nome"]
        except Exception:
            continue
    return payloads, fonti


def costruisci(payloads, oggi=None, orizzonte_gg=7):
    """Restituisce (oggetto, testo, html, n_criticita)."""
    oggi = oggi or dt.date.today()
    metriche = {}
    for m in dd.MODULI_METRICHE:
        try:
            metriche[m] = dd.metriche_da_payload(m, payloads.get(m), oggi)
        except Exception:
            metriche[m] = None
    righe, generale, azioni = dd.semafori(metriche)
    ev = calendario.eventi(payloads, oggi, orizzonte_gg)
    scadute = [e for e in ev if e["Giorni"] < 0]
    prossime = [e for e in ev if e["Giorni"] >= 0]
    crit = sum(1 for r in righe if r["Stato"] == "bad") + len(scadute)
    oggetto = f"FCR - Riepilogo del {oggi.strftime('%d/%m/%Y')}: " + (f"{crit} punti critici" if crit else "tutto sotto controllo")
    fe = lambda e: f"{e['Data'].strftime('%d/%m')} [{e['Categoria']}] {e['Titolo']}" + (f" - {fmt_num(e['Importo'])} EUR" if e["Importo"] else "") + (f" ({e['Giorni']} gg)" if e["Giorni"] < 0 else "")
    t = [f"RIEPILOGO FCR - {oggi.strftime('%d/%m/%Y')}", ""]
    t.append("COSA FARE")
    t += [f"- [{SIMBOLO[s].lower()}] {x}" for s, x in azioni] or ["- Nessuna azione urgente."]
    t += ["", f"SCADUTE ({len(scadute)})"] + [f"- {fe(e)}" for e in scadute] or [""]
    t += ["", f"PROSSIMI {orizzonte_gg} GIORNI ({len(prossime)})"] + ([f"- {fe(e)}" for e in prossime] or ["- Nessuna scadenza."])
    t += ["", "SEMAFORI"] + [f"- {r['Indicatore']}: {r['Valore']} [{SIMBOLO[r['Stato']]}]" for r in righe if r["Stato"] != "nd"]
    t += ["", "Dati dall'ultimo salvataggio di ogni modulo. Messaggio automatico: le simulazioni sono indicative."]
    testo = "\n".join(t)
    h = html.escape
    li = lambda s, x: f"<li><b style='color:{COLORE[s]}'>{SIMBOLO[s]}</b> {h(x)}</li>"
    ev_li = lambda e: f"<li>{e['Data'].strftime('%d/%m')} · <i>{h(e['Categoria'])}</i> · {h(e['Titolo'])}" + (f" · {fmt_num(e['Importo'])} €" if e["Importo"] else "") + (f" <b style='color:#dc2626'>({-e['Giorni']} gg di ritardo)</b>" if e["Giorni"] < 0 else "") + "</li>"
    corpo = (f"<div style='font-family:Arial,sans-serif;max-width:640px'><h2 style='color:#0a2d5a'>Riepilogo del {oggi.strftime('%d/%m/%Y')}</h2>"
             f"<h3>Cosa fare</h3><ul>{''.join(li(s, x) for s, x in azioni) or '<li>Nessuna azione urgente.</li>'}</ul>"
             f"<h3>Scadute ({len(scadute)})</h3><ul>{''.join(ev_li(e) for e in scadute) or '<li>Nessuna.</li>'}</ul>"
             f"<h3>Prossimi {orizzonte_gg} giorni ({len(prossime)})</h3><ul>{''.join(ev_li(e) for e in prossime) or '<li>Nessuna scadenza.</li>'}</ul>"
             f"<h3>Semafori</h3><ul>{''.join(li(r['Stato'], r['Indicatore'] + ': ' + r['Valore']) for r in righe if r['Stato'] != 'nd')}</ul>"
             "<p style='color:#64748b;font-size:12px'>Dati dall'ultimo salvataggio di ogni modulo. Messaggio automatico: le simulazioni sono indicative.</p></div>")
    return oggetto, testo, corpo, crit


def invia(oggetto, testo, corpo_html, env=None):
    env = env or os.environ
    host, user, pw, dest = env.get("SMTP_HOST", ""), env.get("SMTP_USER", ""), env.get("SMTP_PASSWORD", ""), [x.strip() for x in env.get("MAIL_TO", "").split(",") if x.strip()]
    if not (host and user and pw and dest):
        raise RuntimeError("Configurazione email incompleta: servono SMTP_HOST, SMTP_USER, SMTP_PASSWORD e MAIL_TO.")
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = oggetto, env.get("MAIL_FROM") or user, ", ".join(dest)
    msg.set_content(testo)
    msg.add_alternative(corpo_html, subtype="html")
    with smtplib.SMTP(host, int(env.get("SMTP_PORT", "587") or 587), timeout=30) as s:
        s.starttls()
        s.login(user, pw)
        s.send_message(msg)
    return dest


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    payloads, fonti = raccogli()
    if not payloads:
        print("Nessun salvataggio trovato nel database: niente da riepilogare (controlla DATABASE_URL).")
        return 0
    oggetto, testo, corpo, crit = costruisci(payloads)
    if "--dry-run" in argv:
        print(oggetto + "\n\n" + testo)
        return 0
    dest = invia(oggetto, testo, corpo)
    print(f"Riepilogo inviato a {len(dest)} destinatari ({crit} punti critici). Moduli letti: {', '.join(sorted(fonti))}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
