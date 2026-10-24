"""demo_extra.py - Dati dimostrativi scritti a mano per gli strumenti che non hanno un esempio proprio (Registro commerciale, Offerta e finanziamenti)."""
import datetime as dt


def _d(oggi, giorni):
    return (oggi + dt.timedelta(days=giorni)).isoformat()


def registro(oggi):
    righe = [
        ("001-MI-ROSSI", -120, "S3", "Milano", "MI", "Via Verdi 12", "Studio Bianchi", "Verdi", "Riqualificazione facciate e cappotto", 420000, 80, 5, 42, 20),
        ("002-CR-BOSCO", -90, "S2", "Crema", "CR", "Via Viviani", "Amm. Ferrari", "Gialli", "Copertura e facciate", 768000, 60, -3, 42, 15),
        ("003-LO-AURORA", -75, "S2", "Lodi", "LO", "Via Aurora 5", "Amm. Colombo", "Verdi", "Cappotto termico", 310000, 50, 4, 24, 20),
        ("004-BG-ALPI", -60, "S1", "Bergamo", "BG", "Via delle Alpi 8", "Studio Rota", "Gialli", "Sostituzione centrale termica", 185000, 40, -12, 16, 30),
        ("005-MI-NAVIGLI", -45, "S1", "Milano", "MI", "Alzaia Naviglio 40", "Amm. Sala", "Verdi", "Rifacimento tetto", 540000, 30, 9, 30, 25),
        ("006-PV-TICINO", -30, "S0", "Pavia", "PV", "Viale Ticino 21", "Amm. Conti", "Gialli", "Facciate", 260000, 20, 14, 18, 10),
        ("007-CO-LAGO", -150, "S4", "Como", "CO", "Via Lago 3", "Studio Riva", "Verdi", "Impermeabilizzazione terrazzi", 150000, 100, 40, 12, 60),
        ("008-BS-CENTRO", -200, "S5", "Brescia", "BS", "Corso Centro 77", "Amm. Fusi", "Gialli", "Cappotto e serramenti", 620000, 100, 60, 36, 90),
        ("009-MB-OLONA", -40, "S6", "Monza", "MB", "Via Olona 2", "Amm. Besana", "Verdi", "Copertura", 230000, 0, 0, 20, 10),
    ]
    out = []
    for cod, ins, stato, citta, pr, ind, amm, com, lav, val, succ, scad, ui, rev in righe:
        out.append({"Codice": cod, "Inserita": _d(oggi, ins), "Sopralluogo": _d(oggi, ins + 10), "Offerta": _d(oggi, ins + 25) if stato not in ("S0", "S1") else "", "Citta": citta, "PR": pr, "Indirizzo": ind,
                    "Amministratore": amm, "Commerciale": com, "Affiancato": "", "Finanziamento": "Condominio + condomini" if val > 300000 else "Condominio", "UI": ui, "Stato": stato, "Lavori": lav,
                    "Prossimo": stato, "Revisioni": rev // 10, "Scadenza": _d(oggi, scad), "Chi": com, "Valore": val, "Successo": succ, "Note": "", "Banca": "", "Archivio": "Attiva"})
    return {"pratiche": out, "params": {"preavviso_gg": 7}}


def offerta(oggi):
    import of
    voci = [
        {"Cap": "A", "Cod": "1", "Descrizione": "Cantierizzazione, recinzioni e servizi", "UM": "a corpo", "Quantita": 1, "Prezzo": 48000, "Ipotesi": ""},
        {"Cap": "A", "Cod": "2", "Descrizione": "Ponteggio a telaio con PIMUS", "UM": "mq", "Quantita": 2400, "Prezzo": 24.5, "Ipotesi": ""},
        {"Cap": "B", "Cod": "1", "Descrizione": "Rimozione guaine e preparazioni", "UM": "mq", "Quantita": 1124, "Prezzo": 21, "Ipotesi": ""},
        {"Cap": "C", "Cod": "1A", "Descrizione": "Coibentazione in lana minerale 14 cm e doppia guaina", "UM": "mq", "Quantita": 732, "Prezzo": 130, "Ipotesi": "A"},
        {"Cap": "C", "Cod": "2A", "Descrizione": "Pannello sandwich sulle falde inclinate", "UM": "mq", "Quantita": 392, "Prezzo": 132, "Ipotesi": "A"},
        {"Cap": "C", "Cod": "1B", "Descrizione": "Copertura in lamiera grecata coibentata", "UM": "mq", "Quantita": 1124, "Prezzo": 123, "Ipotesi": "B"},
        {"Cap": "C", "Cod": "2B", "Descrizione": "Coibentazione termica lana di roccia 12 cm", "UM": "mq", "Quantita": 1124, "Prezzo": 30.5, "Ipotesi": "B"},
        {"Cap": "D", "Cod": "1", "Descrizione": "Lattonerie, scossaline e pluviali", "UM": "m", "Quantita": 730, "Prezzo": 62, "Ipotesi": ""},
        {"Cap": "D", "Cod": "2", "Descrizione": "Tinteggiatura facciate acril-silossanica", "UM": "mq", "Quantita": 4718, "Prezzo": 26, "Ipotesi": ""},
        {"Cap": "E", "Cod": "1", "Descrizione": "Ripristini murari a misura", "UM": "mq", "Quantita": 150, "Prezzo": 101.5, "Ipotesi": ""},
    ]
    sconti = [{"Descrizione": "Sconto parti comuni (ponteggio)", "Ipotesi": "", "Importo": -22512.0}, {"Descrizione": "Sconto ipotesi A", "Ipotesi": "A", "Importo": -5800.0}, {"Descrizione": "Sconto ipotesi B", "Ipotesi": "B", "Importo": -35986.0}]
    n = 42
    unita = [{"Unita": f"Int. {i + 1}", "Proprietario": f"Proprietario {i + 1}", "Millesimi": round(1000 / n, 3) if i < n - 1 else round(1000 - round(1000 / n, 3) * (n - 1), 3), "Mq": 70 + (i * 7) % 40} for i in range(n)]
    ric = [{"Tipo": "Condominio", "Richiedente": "Condominio Bosco", "Istituto": "Banca del Territorio", "Richiesto": 500000, "Stato": "Approvata", "Deliberato": 500000, "Data richiesta": _d(oggi, -30), "Data esito": _d(oggi, -8), "Documenti": "Delibera assembleare e visura consegnate"}]
    stati = ["Erogata", "Approvata", "Approvata", "In istruttoria", "In istruttoria", "Integrazioni richieste", "Inserita", "Rifiutata", "Da preparare", "Da preparare"]
    for i, stt in enumerate(stati):
        lav = 12000 + 1500 * i
        ric.append({"Tipo": "Condomino", "Unita": f"Int. {i + 1}", "Richiedente": f"Proprietario {i + 1}", "Istituto": "AGOS", "Lavori": lav, "Richiesto": lav * 0.5, "Stato": stt,
                    "Deliberato": lav * 0.5 if stt in ("Erogata", "Approvata") else 0, "Data richiesta": _d(oggi, -20 + i),
                    "Data esito": _d(oggi, -5) if stt in ("Erogata", "Approvata", "Rifiutata") else "", "Esito": "Reddito insufficiente" if stt == "Rifiutata" else "",
                    "Documenti": "Documento, CU e busta paga consegnati" if i < 5 else "Manca la busta paga", "Note": ""})
    ann = [{"Fonte": "Immobiliare.it", "Zona": "Semicentro", "Stato": "Così com'è", "Mq": 90, "Prezzo": 138000, "Link": ""}, {"Fonte": "Casa.it", "Zona": "Semicentro", "Stato": "Così com'è", "Mq": 80, "Prezzo": 124000, "Link": ""},
           {"Fonte": "Agenzia Centro", "Zona": "Semicentro", "Stato": "Così com'è", "Mq": 100, "Prezzo": 155000, "Link": ""}, {"Fonte": "Immobiliare.it", "Zona": "Semicentro", "Stato": "Efficientato", "Mq": 85, "Prezzo": 152000, "Link": ""},
           {"Fonte": "Casa.it", "Zona": "Semicentro", "Stato": "Efficientato", "Mq": 95, "Prezzo": 168000, "Link": ""}, {"Fonte": "Agenzia Centro", "Zona": "Semicentro", "Stato": "Efficientato", "Mq": 78, "Prezzo": 140000, "Link": ""}]
    return {"pratica": {"cod": "002-CR-BOSCO", "condominio": "Condominio Bosco", "indirizzo": "Via Viviani - Crema (CR)", "cf": "90012345678", "zona": "Via Viviani, Crema (Semicentro)", "commerciale": "Gialli",
                        "data": f"{oggi.day}/{oggi.month}/{oggi.year}", "ui": n, "validita_gg": 15, "descrizione": "Riqualificazione della copertura con nuova coibentazione, rifacimento di lattonerie e pluviali, tinteggiatura delle facciate e ripristini murari.",
                        "stato_fatto": "Copertura con riprese diffuse, disomogeneità e invecchiamento dei manti: aumenta il rischio di infiltrazioni e manutenzioni ricorrenti.",
                        "opere_comuni": "Cantierizzazione, ponteggi, demolizioni e preparazioni, lattonerie, tinteggiature e ripristini murari a misura."},
            "voci": voci, "sconti": sconti,
            "opzioni": {"A": {"nome": "guaina + pannello sandwich", "desc": "Parte piana: coibentazione in lana minerale 14 cm e doppia membrana bituminosa con finitura riflettente. Parte inclinata: pannello sandwich in alluminio con lana di roccia."},
                        "B": {"nome": "lamiera grecata", "desc": "Copertura completa in lastre metalliche grecate in alluminio preverniciato con isolamento continuo in lana di roccia 12 cm."}},
            "parcelle": {"manuale": {"A": 40644.22, "B": 40000.0}, "rl_importo": 39605.0}, "params": {"risparmio_annuo": 9000.0},
            "unita": unita, "annunci": ann, "richieste": ric,
            "confronto": [{"Parametro": "Manto parte piana", "A": "Doppia guaina bituminosa", "B": "Lamiera grecata"}, {"Parametro": "Isolamento principale", "A": "14 cm piano / 12 cm inclinato", "B": "12 cm su intera copertura"},
                          {"Parametro": "Finitura riflettente", "A": "SRI 80 su guaina bianca", "B": "Alluminio preverniciato bianco"}],
            "scenario": {"opzione": "A", "anni": 10, "detrazione": 50}}


def payloads(oggi):
    return {"rc": registro(oggi), "of": offerta(oggi)}
