import os
import json
import pandas as pd
import google.generativeai as genai

# Configura la chiave API di Gemini leggendola dalle variabili d'ambiente
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

def simula_input_utente():
    return (
        "Vogliamo aprire una startup innovativa di sviluppo software e consulenza IT a Milano. "
        "Prevediamo 3 soci fondatori che lavorano a tempo pieno, un fatturato stimato di 120.000 euro "
        "nel primo anno, costi per affitto ufficio di 1.200 euro al mese, spese di marketing digital "
        "pari a 8.000 euro annuali e l'acquisto di hardware e licenze per 15.000 euro iniziali."
    )

def estrai_dati_finanziari_con_gemini(descrizione_testuale):
    prompt_sistema = """
    Sei un analista finanziario ed esperto di controllo di gestione. 
    Analizza la descrizione dell'attività fornita dall'utente e restituisci ESCLUSIVAMENTE un oggetto JSON valido 
    (senza blocchi di codice markdown come ```json ... ```) con la seguente struttura esatta:
    {
        "anno_riferimento": 2026,
        "ricavi_stimati": 0.0,
        "costi_personale": 0.0,
        "costi_operativi_annui": 0.0,
        "spese_marketing": 0.0,
        "investimenti_iniziali": 0.0
    }
    Stima cifre realistiche in base al testo se alcuni valori esatti non sono specificati.
    """
    
    # Usiamo l'alias ufficiale sempre aggiornato 'gemini-flash-latest'
    model = genai.GenerativeModel(
        model_name='gemini-flash-latest',
        system_instruction=prompt_sistema
    )
    
    response = model.generate_content(descrizione_testuale)
    testo_risposta = response.text.strip()
    
    # Pulizia di sicurezza nel caso il modello inserisca i tag markdown
    if testo_risposta.startswith("```"):
        testo_risposta = testo_risposta.split("```")[1]
        if testo_risposta.startswith("json"):
            testo_risposta = testo_risposta[4:].strip()
        testo_risposta = testo_risposta.split("```")[0].strip()
        
    return json.loads(testo_risposta)

def calcola_conto_economico(dati_finanziari):
    ricavi = dati_finanziari.get("ricavi_stimati", 0)
    costi_personale = dati_finanziari.get("costi_personale", 0)
    costi_operativi = dati_finanziari.get("costi_operativi_annui", 0)
    marketing = dati_finanziari.get("spese_marketing", 0)
    investimenti = dati_finanziari.get("investimenti_iniziali", 0)
    
    totale_costi_operativi = costi_personale + costi_operativi + marketing
    margine_operativo_lordo = ricavi - totale_costi_operativi
    ammortamenti = investimenti * 0.20
    risultato_operativo = margine_operativo_lordo - ammortamenti
    
    return {
        "Valore della Produzione / Ricavi": ricavi,
        "Costi Operativi Totali": totale_costi_operativi,
        "Margine Operativo Lordo (MOL / EBITDA)": margine_operativo_lordo,
        "Ammortamenti": ammortamenti,
        "Risultato Operativo (EBIT)": risultato_operativo
    }

def genera_commento_strategico(dati_finanziari, risultati_calcolati):
    prompt = f"""
    Dati di input inseriti dall'utente:
    {json.dumps(dati_finanziari, indent=2)}

    Risultati del Conto Economico calcolati dal sistema:
    {json.dumps(risultati_calcolati, indent=2)}

    Agisci come consulente di direzione aziendale. Scrivi un breve Executive Summary e un'analisi 
    della sostenibilità economica di questo business plan, evidenziando eventuali punti di attenzione 
    sul Margine Operativo Lordo e sulla redditività. Mantieni un tono professionale e orientato agli investitori.
    """

    model = genai.GenerativeModel('gemini-flash-latest')
    response = model.generate_content(prompt)
    return response.text

if __name__ == "__main__":
    print("--- 1. Acquisizione descrizione utente ---")
    descrizione = simula_input_utente()
    print(f"Testo:\n{descrizione}\n")
    
    print("--- 2. Estrazione stime tramite Gemini (Output JSON) ---")
    dati_strutturati = estrai_dati_finanziari_con_gemini(descrizione)
    print(json.dumps(dati_strutturati, indent=2))
    
    print("\n--- 3. Elaborazione matematica del Conto Economico (Python) ---")
    risultati = calcola_conto_economico(dati_strutturati)
    for voce, valore in risultati.items():
        print(f" - {voce}: € {valore:,.2f}")
        
    print("\n--- 4. Generazione Relazione Strategica con Gemini ---")
    relazione = genera_commento_strategico(dati_strutturati, risultati)
    print(relazione)