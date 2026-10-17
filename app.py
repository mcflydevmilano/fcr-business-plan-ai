import os
import json
import pandas as pd
import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
import io

# Configurazione della pagina Streamlit
st.set_page_config(
    page_title="FCR General Contractor | AI Business Plan & Basel Rating Platform", 
    page_icon="📊", 
    layout="wide"
)

# --- SISTEMA DI AUTENTICAZIONE CON PASSWORD, LOGO CENTRATO ED ANIMATO ---
def check_password():
    """Restituisce True se l'utente ha inserito la password corretta."""
    try:
        default_pwd = st.secrets.get("APP_PASSWORD", "fcr2026")
    except Exception:
        default_pwd = "fcr2026"

    def password_entered():
        if st.session_state["password_input"] == default_pwd:
            st.session_state["password_correct"] = True
            del st.session_state["password_input"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state or not st.session_state["password_correct"]:
        st.markdown("<br><br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 1.2, 1])
        with col2:
            st.markdown("""
                <div style="
                    background-color: #111827; 
                    padding: 40px 30px; 
                    border-radius: 16px; 
                    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.6); 
                    border: 1px solid #1f2937; 
                    text-align: center;
                    animation: fadeIn 0.8s ease-in-out;
                ">
            """, unsafe_allow_html=True)
            
            logo_path = "aetheris_labs_logo.jpg"
            if os.path.exists(logo_path):
                # Centrare l'immagine usando le colonne di Streamlit
                c1, c2, c3 = st.columns([1, 1.5, 1])
                with c2:
                    st.image(logo_path, use_container_width=True)
            
            st.markdown("<h2 style='color: #f8fafc; margin-top: 15px; font-size: 1.6rem;'>FCR GENERAL CONTRACTOR</h2>", unsafe_allow_html=True)
            st.markdown("<p style='color: #38bdf8; font-size: 0.95rem; font-weight: 500; margin-bottom: 25px;'>Aetheris Labs — Area Riservata Protetta</p>", unsafe_allow_html=True)
            
            st.text_input("Password di Accesso:", type="password", on_change=password_entered, key="password_input")
            
            if "password_correct" in st.session_state and not st.session_state["password_correct"]:
                st.error("😕 Password errata. Riprova.")
                
            st.markdown("</div>", unsafe_allow_html=True)
        return False
    else:
        return True

if not check_password():
    st.stop()

# --- STYLING CSS AVANZATO CON ANIMAZIONI (DARK MODE FINTECH) ---
st.markdown("""
<style>
    /* Keyframe Animazioni */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes pulseGlow {
        0% { box-shadow: 0 0 10px rgba(56, 189, 248, 0.2); }
        50% { box-shadow: 0 0 20px rgba(56, 189, 248, 0.5); }
        100% { box-shadow: 0 0 10px rgba(56, 189, 248, 0.2); }
    }

    /* Sfondo Generale */
    .stApp {
        background-color: #0b0f19;
        color: #e2e8f0;
        font-family: 'Inter', sans-serif;
    }

    /* Rimozione dello spazio / banda superiore nella Sidebar */
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1.5rem;
    }

    [data-testid="stSidebar"] {
        background-color: #111827;
        border-right: 1px solid #1f2937;
    }

    /* Animazione Logo Sidebar al passaggio del mouse */
    [data-testid="stSidebar"] img {
        border-radius: 12px;
        transition: transform 0.4s ease, box-shadow 0.4s ease;
        margin: 0 auto;
        display: block;
    }
    [data-testid="stSidebar"] img:hover {
        transform: scale(1.03);
        box-shadow: 0 8px 24px rgba(56, 189, 248, 0.35);
    }

    /* Testi e Titoli */
    h1, h2, h3 {
        color: #f8fafc;
        font-weight: 700;
    }

    /* Tab con Animazione */
    .stTabs [data-baseweb="tab"] {
        background-color: #1e293b;
        border-radius: 8px 8px 0px 0px;
        color: #94a3b8;
        padding: 12px 24px;
        font-weight: 600;
        border: none;
        transition: all 0.3s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #38bdf8;
        background-color: #334155;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #1e3a8a 0%, #0284c7 100%) !important;
        color: #ffffff !important;
        box-shadow: 0 4px 14px rgba(2, 132, 199, 0.4);
    }

    /* Bottoni Interattivi Animati */
    .stButton > button {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        color: white;
        border-radius: 8px;
        padding: 0.6rem 1.4rem;
        font-weight: 600;
        border: none;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 22px rgba(37, 99, 235, 0.6);
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    }

    /* Card Metriche con Bagliore */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 700;
        color: #38bdf8;
    }

    .stTextInput input, .stNumberInput input {
        background-color: #1e293b;
        color: white;
        border-radius: 8px;
        border: 1px solid #334155;
        transition: border 0.3s ease;
    }
    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: #38bdf8;
    }
</style>
""", unsafe_allow_html=True)

# Intestazione visiva principale
col_title1, col_title2 = st.columns([6, 1])
with col_title1:
    st.title("📊 FCR GENERAL CONTRACTOR — AI Business Plan & Basel Rating")
    st.markdown("Piattaforma di Credit Risk Management e Pianificazione Strategica Pluriennale (Standard Basilea 3/4 - Intesa Sanpaolo Style).")

# Gestione sicura della chiave API
api_key = os.environ.get("GEMINI_API_KEY", "")
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

if api_key:
    genai.configure(api_key=api_key)

# Barra Laterale con Branding Fisso e Logo Centrato
with st.sidebar:
    logo_path = "aetheris_labs_logo.jpg"
    if os.path.exists(logo_path):
        # Centratura Logo Sidebar
        sb_col1, sb_col2, sb_col3 = st.columns([1, 3, 1])
        with sb_col2:
            st.image(logo_path, use_container_width=True)
    else:
        st.warning("⚠️ Logo 'aetheris_labs_logo.jpg' non trovato.")
    
    st.markdown("<h3 style='text-align: center; color: #f8fafc; margin-top: 10px;'>AETHERIS LABS</h3>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 0.85rem;'>Software, AI & Game Development Division</p>", unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("<p style='text-align: center; margin-bottom: 2px;'>🛠️ <b>Sviluppato da</b></p>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: #38bdf8; margin: 0;'>Ing. Lorenzo Di Ferdinando</h4>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 0.85rem;'>FCR General Contractor</p>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    user_api_key = st.text_input("Gemini API Key (Locale)", value=api_key, type="password")
    if user_api_key:
        genai.configure(api_key=user_api_key)
    st.info("Motore neurale attivo per l'estrazione OCR e la simulazione del merito creditizio.")

# Inizializzazione session state per i dati
if 'financial_data' not in st.session_state:
    st.session_state['financial_data'] = {
        "anno_riferimento": 2025,
        "ricavi": 2500000.0,
        "ebitda": 300000.0,
        "utile_netto": 120000.0,
        "totale_attivo": 3000000.0,
        "patrimonio_netto": 800000.0,
        "debiti_finanziari_totali": 900000.0,
        "pfn": 600000.0,
        "dscr_stimato": 1.45
    }

def pulisci_testo_ia(testo):
    if not testo:
        return ""
    return testo.replace("```", "").replace("`", "")

# Classe PDF personalizzata con Logo integrato nell'Header
class PDFReport(FPDF):
    def header(self):
        self.set_fill_color(15, 23, 42)
        self.rect(0, 0, 210, 26, 'F')
        
        logo_path = "aetheris_labs_logo.jpg"
        if os.path.exists(logo_path):
            try:
                self.image(logo_path, 10, 4, 18)
            except Exception:
                pass
        
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(255, 255, 255)
        self.set_xy(32, 6)
        self.cell(0, 6, "FCR GENERAL CONTRACTOR - RISK MANAGEMENT REPORT", 0, 0, 'L')
        self.set_font('Helvetica', '', 8)
        self.set_xy(32, 13)
        self.cell(0, 6, "Powered by Aetheris Labs | Lead Eng: Ing. Lorenzo Di Ferdinando", 0, 0, 'L')
        self.ln(22)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Pagina {self.page_no()} - FCR General Contractor / Aetheris Labs', 0, 0, 'C')

def genera_pdf_report(dati, rating_info, piano_3_anni, relazione_testo):
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 8, "VALUTAZIONE DEL MERITO DI CREDITO E BUSINESS PLAN", ln=True)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, "Analisi di conformità, rating prospettico e parere per il Comitato Fidi", ln=True)
    pdf.ln(4)
    
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, "1. Sintesi Indicatori Economico-Finanziari Anno Base", ln=True)
    
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(30, 41, 59)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(110, 7, "  Parametro / Voce Contabile", 1, 0, 'L', True)
    pdf.cell(70, 7, "Valore / Giudizio  ", 1, 1, 'R', True)
    
    pdf.set_font("Helvetica", "", 9)
    table_data = [
        ("Ricavi delle Vendite", f"{dati['ricavi']:,.2f} EUR"),
        ("EBITDA (MOL)", f"{dati['ebitda']:,.2f} EUR"),
        ("Patrimonio Netto", f"{dati['patrimonio_netto']:,.2f} EUR"),
        ("Posizione Finanziaria Netta (PFN)", f"{dati['pfn']:,.2f} EUR"),
        ("Rapporto PFN / EBITDA", f"{rating_info['pfn_ebitda']:.2f}x"),
        ("Rapporto PFN / Patrimonio Netto", f"{rating_info['pfn_pn']:.2f}x"),
        ("Giudizio di Rating Stimato", rating_info['classe_rating'])
    ]
    
    fill = False
    for label, val in table_data:
        pdf.set_text_color(0, 0, 0)
        pdf.set_fill_color(241, 245, 249) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.cell(110, 6, f"  {label}", 1, 0, 'L', True)
        pdf.cell(70, 6, f"{val}  ", 1, 1, 'R', True)
        fill = not fill
        
    pdf.ln(4)
    
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, "2. Proiezioni Economico-Finanziarie Pluriennali (Business Plan)", ln=True)
    
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(30, 41, 59)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(45, 7, "  Anno", 1, 0, 'L', True)
    pdf.cell(45, 7, "Ricavi (EUR)", 1, 0, 'R', True)
    pdf.cell(45, 7, "EBITDA (EUR)", 1, 0, 'R', True)
    pdf.cell(45, 7, "PFN / EBITDA", 1, 1, 'R', True)
    
    pdf.set_font("Helvetica", "", 9)
    for row in piano_3_anni:
        pdf.set_text_color(0, 0, 0)
        pdf.cell(45, 6, f"  {row['Anno']}", 1, 0, 'L')
        pdf.cell(45, 6, f"{row['Ricavi']:,.0f}", 1, 0, 'R')
        pdf.cell(45, 6, f"{row['EBITDA']:,.0f}", 1, 0, 'R')
        pdf.cell(45, 6, f"{row['PFN/EBITDA']:.2f}x", 1, 1, 'R')
        
    pdf.ln(6)
    
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, "3. Relazione e Parere del Risk Management", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(50, 50, 50)
    
    clean_text = relazione_testo.replace("€", "EUR").replace("**", "").replace("###", "").encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 5, clean_text)
    
    return bytes(pdf.output(dest='S'))

tab1, tab2, tab3, tab4 = st.tabs([
    "📂 1. Acquisizione Dati", 
    "⚡ 2. Simulatore What-If", 
    "📈 3. Business Plan Pluriennale", 
    "📑 4. Report PDF Ufficiale"
])

with tab1:
    st.subheader("Importazione Bilancio Aziendale (PDF o Excel)")
    mode = st.radio("Seleziona la modalità di caricamento:", ["Upload File (PDF o Excel)", "Inserimento Dati Manuale"])
    
    if mode == "Upload File (PDF o Excel)":
        uploaded_file = st.file_uploader("Trascina qui il file di bilancio (.pdf, .xlsx, .xls)", type=["pdf", "xlsx", "xls"])
        
        if uploaded_file and st.button("🚀 Estrai Dati Contabili con AI", type="primary"):
            if not api_key:
                st.error("Inserisci la chiave API Gemini.")
            else:
                file_name = uploaded_file.name.lower()
                with st.spinner("Elaborazione dati contabili in corso..."):
                    try:
                        model_ai = genai.GenerativeModel(model_name='gemini-flash-latest')
                        prompt_estrazione = "Sei un analista fidi esperto del modello di rating Intesa Sanpaolo / Basilea. Estrai i dati contabili e restituisci ESCLUSIVAMENTE un oggetto JSON valido con chiavi: anno_riferimento, ricavi, ebitda, utile_netto, totale_attivo, patrimonio_netto, debiti_finanziari_totali, pfn, dscr_stimato."
                        
                        if file_name.endswith(".pdf"):
                            bytes_data = uploaded_file.getvalue()
                            res = model_ai.generate_content([prompt_estrazione, {"mime_type": "application/pdf", "data": bytes_data}])
                        else:
                            engine = 'xlrd' if file_name.endswith('.xls') else 'openpyxl'
                            xls = pd.ExcelFile(uploaded_file, engine=engine)
                            excel_text = ""
                            for sheet in xls.sheet_names:
                                df = pd.read_excel(xls, sheet_name=sheet)
                                excel_text += f"\n--- Foglio: {sheet} ---\n" + df.to_string(index=False)
                            res = model_ai.generate_content([prompt_estrazione, excel_text])
                            
                        clean_txt = res.text.strip()
                        if clean_txt.startswith("```"):
                            clean_txt = clean_txt.split("```")[1]
                            if clean_txt.startswith("json"):
                                clean_txt = clean_txt[4:].strip()
                            clean_txt = clean_txt.split("```")[0].strip()
                            
                        st.session_state['financial_data'] = json.loads(clean_txt)
                        st.success("Dati estratti con successo!")
                    except Exception as e:
                        st.error(f"Errore durante l'elaborazione: {e}")
    else:
        col_a, col_b = st.columns(2)
        with col_a:
            ricavi_in = st.number_input("Ricavi delle Vendite (€)", value=float(st.session_state['financial_data']['ricavi']))
            ebitda_in = st.number_input("EBITDA / MOL (€)", value=float(st.session_state['financial_data']['ebitda']))
            pn_in = st.number_input("Patrimonio Netto (€)", value=float(st.session_state['financial_data']['patrimonio_netto']))
        with col_b:
            pfn_in = st.number_input("Posizione Finanziaria Netta - PFN (€)", value=float(st.session_state['financial_data']['pfn']))
            attivo_in = st.number_input("Totale Attivo (€)", value=float(st.session_state['financial_data']['totale_attivo']))
            
        if st.button("Aggiorna Dati Inseriti"):
            st.session_state['financial_data'].update({
                "ricavi": ricavi_in,
                "ebitda": ebitda_in,
                "patrimonio_netto": pn_in,
                "pfn": pfn_in,
                "totale_attivo": attivo_in
            })
            st.success("Dati aggiornati con successo!")

    st.markdown("### 📊 Stato Attuale del Dataset:")
    st.json(st.session_state['financial_data'])

with tab2:
    st.subheader("🎯 Simulatore di Rating e Ottimizzazione Basilea 3/4")
    dati_attuali = st.session_state['financial_data']
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("#### ⚙️ Leve Strategiche")
        delta_pfn = st.slider("Variazione Debito PFN (€)", min_value=-500000, max_value=500000, value=0, step=25000)
        delta_pn = st.slider("Iniezione Capitale / Mezzi Propri (€)", min_value=0, max_value=500000, value=0, step=25000)
        delta_ebitda = st.slider("Miglioramento EBITDA (€)", min_value=-100000, max_value=300000, value=0, step=10000)
        
    sim_ebitda = max(dati_attuali['ebitda'] + delta_ebitda, 1.0)
    sim_pfn = max(dati_attuali['pfn'] + delta_pfn, 0.0)
    sim_pn = max(dati_attuali['patrimonio_netto'] + delta_pn, 1.0)
    
    sim_pfn_ebitda = sim_pfn / sim_ebitda
    sim_pfn_pn = sim_pfn / sim_pn
    
    if sim_pfn_ebitda < 2.5 and sim_pfn_pn < 1.0:
        classe_rating = "FASCIA VERDE - Rating Elevato / Bancabile"
    elif sim_pfn_ebitda < 4.5:
        classe_rating = "FASCIA GIALLA - Rating Neutro / Sotto Osservazione"
    else:
        classe_rating = "FASCIA ROSSA - Rischio Elevato / Requisiti di Garanzia"
        
    with col2:
        st.markdown("#### 📈 Output Modulo di Scoring")
        m1, m2, m3 = st.columns(3)
        m1.metric("PFN / EBITDA", f"{sim_pfn_ebitda:.2f}x", delta="Target < 2.5x", delta_color="inverse")
        m2.metric("PFN / Net Worth", f"{sim_pfn_pn:.2f}x", delta="Target < 1.0x", delta_color="inverse")
        m3.metric("Comitato Fidi", classe_rating.split(" - ")[0])
        st.info(f"**Posizionamento:** {classe_rating}")

with tab3:
    st.subheader("📈 Proiezioni Pluriennali (3 Anni)")
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        crescita_ricavi = st.slider("Crescita Annua Ricavi (%)", min_value=-10.0, max_value=30.0, value=5.0, step=0.5)
        crescita_ebitda = st.slider("Crescita Annua EBITDA (%)", min_value=-10.0, max_value=30.0, value=6.0, step=0.5)
    with col_p2:
        rimborso_debito_annuo = st.number_input("Rimborso Annuo Debito / PFN (€)", min_value=0.0, max_value=200000.0, value=50000.0, step=10000.0)

    anno_base = dati_attuali['anno_riferimento']
    piano_3_anni = []
    curr_ricavi = dati_attuali['ricavi']
    curr_ebitda = dati_attuali['ebitda']
    curr_pfn = sim_pfn
    
    for i in range(1, 4):
        curr_ricavi *= (1 + crescita_ricavi / 100.0)
        curr_ebitda *= (1 + crescita_ebitda / 100.0)
        curr_pfn = max(curr_pfn - rimborso_debito_annuo, 0.0)
        ratio = curr_pfn / max(curr_ebitda, 1.0)
        
        piano_3_anni.append({
            "Anno": f"Anno {i} ({int(anno_base) + i})",
            "Ricavi": curr_ricavi,
            "EBITDA": curr_ebitda,
            "PFN": curr_pfn,
            "PFN/EBITDA": ratio
        })
        
    df_piano = pd.DataFrame(piano_3_anni)
    st.dataframe(df_piano.style.format({
        "Ricavi": "{:,.2f} EUR",
        "EBITDA": "{:,.2f} EUR",
        "PFN": "{:,.2f} EUR",
        "PFN/EBITDA": "{:.2f}x"
    }), use_container_width=True)

with tab4:
    st.subheader("📑 Generazione Report Esecutivo per il Comitato di Credito")
    if st.button("🚀 Genera Report PDF Istituzionale", type="primary"):
        if not api_key:
            st.error("Inserisci la chiave API Gemini.")
        else:
            with st.spinner("Creazione del report in corso..."):
                try:
                    rating_info = {
                        "pfn_ebitda": sim_pfn_ebitda,
                        "pfn_pn": sim_pfn_pn,
                        "classe_rating": classe_rating
                    }
                    
                    prompt_strat = f"Agisci come Risk Manager di Intesa Sanpaolo. Dati: Ricavi {dati_attuali['ricavi']}, EBITDA {sim_ebitda}, PFN {sim_pfn}, PN {sim_pn}, PFN/EBITDA {sim_pfn_ebitda:.2f}x, Giudizio {classe_rating}. Redigi una relazione formale per il Comitato di Credito su: 1. Solvibilità. 2. Punti di forza/criticità Basilea 3/4. 3. Sostenibilità piano pluriennale. 4. Raccomandazioni. Scrivi in testo semplice senza markdown."
                    
                    model_rel = genai.GenerativeModel(model_name='gemini-flash-latest')
                    response_rel = model_rel.generate_content(prompt_strat)
                    relazione_txt = pulisci_testo_ia(response_rel.text)
                    
                    st.markdown("### 📄 Sintesi della Relazione")
                    st.markdown(relazione_txt)
                    
                    pdf_bytes = genera_pdf_report(dati_attuali, rating_info, piano_3_anni, relazione_txt)
                    
                    st.download_button(
                        label="📥 Scarica Report PDF Ufficiale",
                        data=pdf_bytes,
                        file_name="Report_Rating_FCR_General_Contractor.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error(f"Errore nella generazione del report: {e}")
