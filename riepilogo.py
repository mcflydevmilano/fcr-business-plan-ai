"""
riepilogo.py - Riepilogo mattutino via email e/o Slack: semafori e azioni del Cruscotto + scadenze scadute e dei prossimi giorni.

Si esegue da riga di comando (o da GitHub Actions, vedi .github/workflows/riepilogo.yml). Legge l'ULTIMO salvataggio di ogni modulo dal database
(DATABASE_URL) e invia la mail con SMTP. Variabili d'ambiente: DATABASE_URL, SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, MAIL_TO
(uno o piu' indirizzi separati da virgola), MAIL_FROM (opzionale); per Slack: SLACK_WEBHOOK_URL (Incoming Webhook). Basta uno dei due canali. Con --dry-run stampa il testo senza inviare.
"""
import datetime as dt
import html
import json
import os
import smtplib
import sys
import urllib.request
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
    import posta
    posta.invia(dest, oggetto, testo, html=corpo_html, env=env)       # un solo tentativo, timeout 10 s, mai riprovato da solo
    return dest


def per_slack(oggetto, testo):
    """Testo del riepilogo nel formato di Slack (grassetto con *, limite di 3000 caratteri per blocco)."""
    righe = []
    for r in testo.split("\n")[1:]:
        if r.isupper() or (r and r.split(" (")[0].isupper() and r.endswith(")")):
            r = f"*{r}*"
        for k, v in (("[critico]", ":red_circle:"), ("[attenzione]", ":large_yellow_circle:"), ("[ok]", ":large_green_circle:")):
            r = r.replace(k, v)
        righe.append(r.replace(" [CRITICO]", " :red_circle:").replace(" [ATTENZIONE]", " :large_yellow_circle:").replace(" [OK]", " :large_green_circle:"))
    corpo = "\n".join(righe).strip()
    blocchi = [corpo[i:i + 2900] for i in range(0, len(corpo), 2900)][:10]
    return {"text": oggetto, "blocks": [{"type": "header", "text": {"type": "plain_text", "text": oggetto[:150]}}] +
            [{"type": "section", "text": {"type": "mrkdwn", "text": b}} for b in blocchi]}


def invia_slack(oggetto, testo, env=None):
    """Pubblica il riepilogo in un canale Slack tramite Incoming Webhook (segreto SLACK_WEBHOOK_URL)."""
    env = env or os.environ
    url = (env.get("SLACK_WEBHOOK_URL") or "").strip()
    if not url.startswith("https://hooks.slack.com/"):
        raise RuntimeError("SLACK_WEBHOOK_URL mancante o non valido (deve iniziare con https://hooks.slack.com/).")
    req = urllib.request.Request(url, data=json.dumps(per_slack(oggetto, testo)).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        if r.status != 200:
            raise RuntimeError(f"Slack ha risposto {r.status}")
    return True


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
    email = all(os.environ.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "MAIL_TO"))
    slack = bool((os.environ.get("SLACK_WEBHOOK_URL") or "").strip())
    if not (email or slack):
        raise RuntimeError("Nessun canale configurato: servono i segreti dell'email (SMTP_*, MAIL_TO) e/o SLACK_WEBHOOK_URL.")
    errori = []
    if email:
        try:
            dest = invia(oggetto, testo, corpo)
            print(f"Email inviata a {len(dest)} destinatari.")
        except Exception as e:
            errori.append(f"email: {e}")
    if slack:
        try:
            invia_slack(oggetto, testo)
            print("Messaggio pubblicato su Slack.")
        except Exception as e:
            errori.append(f"slack: {e}")
    print(f"{crit} punti critici. Moduli letti: {', '.join(sorted(fonti))}.")
    if errori:
        raise RuntimeError("Invio non riuscito: " + "; ".join(errori))
    return 0


if __name__ == "__main__":
    sys.exit(main())
