import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from fpdf import FPDF
import gspread
from google.oauth2.service_account import Credentials
import time

# --- 1. CONFIGURARE PAGINĂ ---
st.set_page_config(page_title="Platformă Comenzi", layout="wide", page_icon="🛒")

# --- CSS COMPLET ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    button[title="Column menu"] { display: none !important; }
    div[data-testid="stDataFrame"] div[role="columnheader"] button { display: none !important; }
    [data-testid="stElementToolbar"] { display: none !important; }

    /* ADAPTARE AUTOMATĂ: Alb pe Dark Mode, Negru pe Light Mode */
    .big-font { font-size: 20px !important; font-weight: 800; color: var(--text-color) !important; padding-top: 10px; }
    .tva-font { font-size: 16px !important; color: var(--text-color) !important; font-weight: 800; padding-top: 15px; text-align: center; }
    
    div.stButton > button { width: 100%; height: 50px; font-size: 16px; font-weight: bold; border-radius: 8px; border: 1px solid #dfe6e9; background-color: #f1f2f6; color: #2d3436; }
    
    div[data-testid="stNumberInput"] input { font-size: 20px; height: 50px; text-align: center; }
    button[kind="secondary"] { height: 50px; }
    
    /* MENIU PLUTITOR DREAPTA (Cos Cumparaturi) */
    .floating-menu {
        position: fixed;
        bottom: 50px;
        right: -135px;
        display: flex;
        flex-direction: column;
        gap: 10px;
        background: rgba(45, 52, 54, 0.95);
        padding: 15px 15px 15px 20px;
        border-radius: 20px 0 0 20px;
        transition: right 0.3s ease-in-out;
        z-index: 99999;
        box-shadow: -4px 4px 15px rgba(0,0,0,0.4);
    }
    .floating-menu:hover, .floating-menu:active, .floating-menu:focus { right: 0px; }
    .floating-menu::before {
        content: "◀";
        position: absolute;
        left: -25px;
        top: 50%;
        transform: translateY(-50%);
        background: rgba(45, 52, 54, 0.95);
        color: white;
        padding: 20px 5px;
        border-radius: 10px 0 0 10px;
        font-size: 14px;
        cursor: pointer;
    }
    
    /* MENIU PLUTITOR STANGA (Admin - Comenzi) */
    .floating-menu-left {
        position: fixed;
        bottom: 50px;
        left: -135px;
        display: flex;
        flex-direction: column;
        gap: 10px;
        background: rgba(45, 52, 54, 0.95);
        padding: 15px 20px 15px 15px;
        border-radius: 0 20px 20px 0;
        transition: left 0.3s ease-in-out;
        z-index: 999999;
        box-shadow: 4px 4px 15px rgba(0,0,0,0.4);
    }
    .floating-menu-left:hover, .floating-menu-left:active, .floating-menu-left:focus { left: 0px; }
    .floating-menu-left::after {
        content: "▶";
        position: absolute;
        right: -25px;
        top: 50%;
        transform: translateY(-50%);
        background: rgba(45, 52, 54, 0.95);
        color: white;
        padding: 20px 5px;
        border-radius: 0 10px 10px 0;
        font-size: 14px;
        cursor: pointer;
    }
    
    .float-btn {
        background-color: #0984e3;
        color: white !important;
        border-radius: 8px;
        padding: 10px;
        font-size: 14px;
        font-weight: bold;
        text-decoration: none;
        text-align: center;
        min-width: 100px;
        border: 1px solid #74b9ff;
    }
    .float-btn:hover { background-color: #74b9ff; }
    </style>
    """, unsafe_allow_html=True)

# --- CONSTANTE & CREDENȚIALE ---
NUME_GOOGLE_SHEET = 'Platforma_Comenzi_Demo_DB'

TAB_PRODUSE = 'Produse'
TAB_COMENZI = 'Comenzi'
TAB_ARHIVA_PRODUSE = 'Arhiva_Produse'
TAB_ARHIVA_COMENZI = 'Arhiva_Comenzi'
TAB_DRAFT = 'Cos_Salvat' 

COLOANE_PRODUSE = ['Cod SAGA', 'Nume Produs', 'TVA', 'UM', 'Pret Unitar', 'Pret Vanzare', 'In Stoc']

PAROLA_ADMIN = "admin123" 
PAROLA_BIROU = "birou123"

CREDENTIALE_MAGAZINE = {
    "Magazin Centru": "centru1", 
    "Magazin Nord": "nord1", 
    "Magazin Sud": "sud1", 
    "Magazin Est": "est1",
    "Magazin Vest": "vest1"
}

CIF_MAGAZINE = {
    "Magazin Centru": "RO000001", 
    "Magazin Nord": "RO000002",  
    "Magazin Sud": "RO000003", 
    "Magazin Est": "RO000004",
    "Magazin Vest": "RO000005"
}

FIRMA_NUME = "COMPANIA DEMO SRL"
FIRMA_CIF = "RO12345678"
FIRMA_RC = "J00/000/2024"
FIRMA_ADRESA = "Oras, str. Exemplu nr. 10"
FIRMA_CAPITAL = "200 RON"
FIRMA_CONTACT = "Tel.0700000000  Email: contact@companiademo.ro"
FIRMA_BANCA = "BANCA DEMO SA"
FIRMA_IBAN = "RO00DEMO1234567890123456"

# --- STATE ---
if 'sort_state' not in st.session_state: st.session_state.sort_state = {'col': None, 'dir': None}
if 'user_logat' not in st.session_state: st.session_state.user_logat = None 
if 'cos_cumparaturi' not in st.session_state: st.session_state.cos_cumparaturi = {} 
# Variabile noi pentru editare și resetare interfață
if 'edit_order_id' not in st.session_state: st.session_state.edit_order_id = None
if 'edit_order_store' not in st.session_state: st.session_state.edit_order_store = None
if 'edit_order_date' not in st.session_state: st.session_state.edit_order_date = None
if 'cart_reset_counter' not in st.session_state: st.session_state.cart_reset_counter = 0

def actualizeaza_cos(produs, key):
    cant = st.session_state[key]
    if cant != 0:
        st.session_state.cos_cumparaturi[produs] = cant
    elif produs in st.session_state.cos_cumparaturi:
        del st.session_state.cos_cumparaturi[produs]

# --- CONEXIUNE GOOGLE SHEETS ---
@st.cache_resource
def init_connection():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    return client

@st.cache_data(ttl=600)
def get_data(tab_name, columns):
    try:
        client = init_connection()
        sheet = client.open(NUME_GOOGLE_SHEET)
        
        try:
            worksheet = sheet.worksheet(tab_name)
        except Exception:
            worksheet = sheet.add_worksheet(title=tab_name, rows=1000, cols=20)
            
        data_bruta = worksheet.get_all_values()
        
        if not data_bruta:
            return pd.DataFrame(columns=columns)
            
        headers = data_bruta[0]
        rows = data_bruta[1:]
        df = pd.DataFrame(rows, columns=headers)
        
        if 'Cod SAGA' in df.columns:
            df['Cod SAGA'] = df['Cod SAGA'].astype(str).str.replace(r'\.0$', '', regex=True)

        for col in columns:
            if col not in df.columns:
                if "Pret" in col: df[col] = 0.0
                elif "Nr" in col: df[col] = 1
                elif "UM" in col: df[col] = ""
                elif "In Stoc" in col: df[col] = "DA"
                else: df[col] = ""
        
        if 'Pret Unitar' in df.columns: 
            df['Pret Unitar'] = df['Pret Unitar'].astype(str).str.replace(',', '.', regex=False)
            df['Pret Unitar'] = pd.to_numeric(df['Pret Unitar'], errors='coerce').fillna(0.0)
        if 'Pret Vanzare' in df.columns: 
            df['Pret Vanzare'] = df['Pret Vanzare'].astype(str).str.replace(',', '.', regex=False)
            df['Pret Vanzare'] = pd.to_numeric(df['Pret Vanzare'], errors='coerce').fillna(0.0)
            
        if 'Nr Comanda' in df.columns: df['Nr Comanda'] = pd.to_numeric(df['Nr Comanda'], errors='coerce').fillna(0)
        
        if tab_name == TAB_PRODUSE and not df.empty:
            df = df[[c for c in COLOANE_PRODUSE if c in df.columns]]
            
        return df
    except Exception as e:
        st.error(f"⚠️ Eroare temporară de conectare. Refresh la pagină!")
        return pd.DataFrame(columns=columns)

def save_data(df, tab_name):
    try:
        client = init_connection()
        sheet = client.open(NUME_GOOGLE_SHEET)
        
        try:
            worksheet = sheet.worksheet(tab_name)
        except Exception:
            worksheet = sheet.add_worksheet(title=tab_name, rows=1000, cols=20)
            
        df_clean = df.copy()
        
        if 'Cod SAGA' in df_clean.columns:
            df_clean['Cod SAGA'] = df_clean['Cod SAGA'].astype(str).str.replace(r'\.0$', '', regex=True)

        if 'Pret Unitar' in df_clean.columns:
            df_clean['Pret Unitar'] = pd.to_numeric(df_clean['Pret Unitar'], errors='coerce').fillna(0.0).map(lambda x: f"{x:.2f}")
        if 'Pret Vanzare' in df_clean.columns:
            df_clean['Pret Vanzare'] = pd.to_numeric(df_clean['Pret Vanzare'], errors='coerce').fillna(0.0).map(lambda x: f"{x:.2f}")
            
        df_clean = df_clean.fillna("")
        df_clean = df_clean.astype(str) 
        
        if tab_name == TAB_PRODUSE and not df_clean.empty:
            df_clean = df_clean[[c for c in COLOANE_PRODUSE if c in df_clean.columns]]
            
        lista_valori = [df_clean.columns.values.tolist()] + df_clean.values.tolist()
        
        worksheet.clear()
        
        try:
            worksheet.update(values=lista_valori, range_name="A1", value_input_option='RAW')
        except TypeError:
            worksheet.update("A1", lista_valori, value_input_option='RAW')
            
        get_data.clear()
        return True
    except Exception as e:
        st.error(f"Eroare la salvare: {e}")
        return False

def append_data(df_nou, tab_name):
    if df_nou.empty: return 
    try:
        client = init_connection()
        sheet = client.open(NUME_GOOGLE_SHEET)
        
        try:
            worksheet = sheet.worksheet(tab_name)
        except Exception:
            worksheet = sheet.add_worksheet(title=tab_name, rows=1000, cols=20)
            try:
                worksheet.update("A1", [df_nou.columns.tolist()], value_input_option='RAW')
            except TypeError:
                worksheet.update(values=[df_nou.columns.tolist()], range_name="A1", value_input_option='RAW')
            
        df_clean = df_nou.copy()
        
        if 'Cod SAGA' in df_clean.columns:
            df_clean['Cod SAGA'] = df_clean['Cod SAGA'].astype(str).str.replace(r'\.0$', '', regex=True)

        if 'Pret Unitar' in df_clean.columns:
            df_clean['Pret Unitar'] = pd.to_numeric(df_clean['Pret Unitar'], errors='coerce').fillna(0.0).map(lambda x: f"{x:.2f}")
        if 'Pret Vanzare' in df_clean.columns:
            df_clean['Pret Vanzare'] = pd.to_numeric(df_clean['Pret Vanzare'], errors='coerce').fillna(0.0).map(lambda x: f"{x:.2f}")
            
        df_clean = df_clean.fillna("")
        df_clean = df_clean.astype(str)
        
        lista_valori = df_clean.values.tolist()
        if not lista_valori: return
            
        try:
            worksheet.append_rows(lista_valori, value_input_option='RAW')
        except TypeError:
            worksheet.append_rows(values=lista_valori, value_input_option='RAW')
            
    except Exception as e:
        st.error(f"Eroare la arhivare ({tab_name}): {str(e)}")

# --- ALTE FUNCȚII ---
def curata_preturi_import(df):
    col_map = {}
    for col in df.columns:
        c_low = str(col).lower().strip()
        if c_low in ['pret unitar', 'pret achizitie', 'achizitie']: col_map[col] = 'Pret Unitar'
        elif c_low in ['pret vanzare', 'vanzare']: col_map[col] = 'Pret Vanzare'
        elif c_low in ['nume produs', 'produs', 'denumire']: col_map[col] = 'Nume Produs'
        elif c_low in ['tva', 'categorie', 'taxa']: col_map[col] = 'TVA'
        elif c_low in ['um', 'unitate']: col_map[col] = 'UM'
        elif c_low in ['cod', 'cod saga', 'cod articol', 'id']: col_map[col] = 'Cod SAGA'
    
    df = df.rename(columns=col_map)
    if 'Cod SAGA' in df.columns:
        df['Cod SAGA'] = df['Cod SAGA'].astype(str).str.replace(r'\.0$', '', regex=True)

    cols = ['Pret Unitar', 'Pret Vanzare']
    for col in cols:
        if col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    return df

def migrare_automata_tva(df):
    modificat = False
    if 'Categorie' in df.columns:
        if 'TVA' in df.columns:
            df['TVA'] = df.apply(lambda r: r['Categorie'] if pd.notna(r['Categorie']) and str(r['Categorie']).strip() != "" else r['TVA'], axis=1)
            df = df.drop(columns=['Categorie'])
        else:
            df = df.rename(columns={'Categorie': 'TVA'})
        modificat = True

    if 'TVA' in df.columns:
        def adauga_procent(x):
            x_str = str(x).strip().replace('%', '').replace(',', '.')
            if x_str.lower() == 'nan' or x_str == '': return '21%' 
            try:
                val = float(x_str)
                if 0 < val <= 1: val = val * 100
                val_intreg = round(val)
                if val_intreg == 11: return '11%'
                elif val_intreg == 21: return '21%'
                elif val_intreg < 15: return '11%'
                else: return '21%'
            except: return '21%' 

        TVA_nou = df['TVA'].apply(adauga_procent)
        if not df['TVA'].equals(TVA_nou):
            df['TVA'] = TVA_nou
            modificat = True
            
    if 'TVA' not in df.columns:
        df['TVA'] = '21%'
        modificat = True
        
    df = df[[c for c in COLOANE_PRODUSE if c in df.columns]]
    return df, modificat

# 💡 LOGICA REPARATĂ: Sortarea sigură a priorităților
def get_sort_priority(nume_produs):
    nume_low = str(nume_produs).lower().replace(" ", "")
    if 'sifon' in nume_low:
        return 1
    elif 'beresuceava' in nume_low:
        return 2
    elif 'sgr' in nume_low:
        return 3
    # Regex strict: "5l" nu trebuie sa aiba niciun numar, punct sau virgula in fata lui!
    elif re.search(r'(?<![,\.0-9])5l', nume_low):
        return 4
    else:
        return 5

def parseaza_text_in_tabel(text_comanda, df_inv=None):
    try:
        text = str(text_comanda).replace("{", "").replace("}", "").replace("'", "").replace('"', "")
        items = text.split(", ")
        rezultat = [{"Produs": item.split(":")[0].strip(), "Cantitate": item.split(":")[1].strip()} for item in items if ":" in item]
        
        def sort_key_istoric(x):
            tva_val = 999
            if df_inv is not None and not df_inv.empty:
                m = df_inv[df_inv['Nume Produs'].str.strip().str.lower() == x['Produs'].lower()]
                if not m.empty:
                    try: tva_val = float(str(m.iloc[0]['TVA']).replace('%', '').replace(',', '.'))
                    except: pass
            
            nume = x['Produs']
            return (get_sort_priority(nume), tva_val, nume.lower())
            
        rezultat.sort(key=sort_key_istoric)
        return rezultat
    except: return []

def safe_text(text):
    replacements = {'ă': 'a', 'â': 'a', 'î': 'i', 'ș': 's', 'ț': 't', 'Ă': 'A', 'Â': 'A', 'Î': 'I', 'Ș': 'S', 'Ț': 'T', '„': '"', '”': '"'}
    text = str(text)
    for k, v in replacements.items(): text = text.replace(k, v)
    return text.encode('latin-1', 'replace').decode('latin-1')

def cycle_sort(col_name):
    current_col = st.session_state.sort_state['col']
    current_dir = st.session_state.sort_state['dir']
    if current_col != col_name: st.session_state.sort_state = {'col': col_name, 'dir': 'asc'}
    else:
        if current_dir == 'asc': st.session_state.sort_state['dir'] = 'desc'
        elif current_dir == 'desc': st.session_state.sort_state = {'col': None, 'dir': None}
        else: st.session_state.sort_state = {'col': col_name, 'dir': 'asc'}

# --- PDF GENERATOR ---
def get_pdf_volume_priority(nume_produs):
    nume_low = str(nume_produs).lower().replace(" ", "")
    if '2,5l' in nume_low or '2.5l' in nume_low: return 1
    # Regex strict pt volume ca "2l" sa nu dea match pe "1.2l"
    if re.search(r'(?<![,\.0-9])2l', nume_low): return 2
    if '1,5l' in nume_low or '1.5l' in nume_low: return 3
    if re.search(r'(?<![,\.0-9])1l', nume_low): return 4
    if '0,5l' in nume_low or '0.5l' in nume_low: return 5
    return 99

def genereaza_pdf_aviz(data_comenzii, magazin, produse_lista, id_comanda, df_inv):
    pdf = FPDF(); pdf.add_page(); pdf.set_font('Arial', '', 9)
    
    data_str = str(data_comenzii)
    data_zi = data_str.split(' ')[0] if ' ' in data_str else data_str
    
    pdf.set_font('Arial', 'B', 14); pdf.cell(0, 7, safe_text("NECESAR DE PRODUSE"), 0 , 1, 'L') 
    pdf.cell(0, 7, safe_text(f"Numar {id_comanda}"), 0, 1, 'L')
    pdf.cell(0, 7, safe_text(f"Data {data_zi}"), 0, 1, 'L')
    
    y_start = pdf.get_y()
    pdf.set_font('Arial', '', 8); pdf.cell(90, 4, "Furnizor", 0, 1)
    y_line = pdf.get_y(); pdf.line(10, y_line, 100, y_line) 
    
    pdf.set_xy(110, y_start); pdf.cell(90, 4, "Client", 0, 1); pdf.line(110, y_line, 200, y_line) 
    pdf.set_y(y_line + 1)
    
    y_info = pdf.get_y()
    pdf.set_font('Arial', 'B', 9); pdf.cell(90, 5, safe_text(FIRMA_NUME), 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.set_x(110); pdf.set_font('Arial', 'B', 12); pdf.cell(90, 4, safe_text(str(magazin)), 0, 1)

    pdf.ln(10)
    
    produse_11 = []
    produse_21 = []
    
    for item in produse_lista:
        nume_p_db = item['Produs']
        
        try:
            cant_p_introdusa = float(str(item['Cantitate']).replace(',', '.').strip())
        except ValueError:
            cant_p_introdusa = 0.0
            
        match = re.search(r'(\d+)\s*/\s*[a-zA-Z]+', nume_p_db)
        
        nume_p_afisat = nume_p_db
        cant_p_finala = cant_p_introdusa

        if match:
            multiplicator = int(match.group(1))
            cant_p_finala = cant_p_introdusa * multiplicator
            nume_p_afisat = nume_p_db[:match.start()].strip()
        
        nume_cautat = str(nume_p_db).strip().lower()
        match_db = df_inv[df_inv['Nume Produs'].astype(str).str.strip().str.lower() == nume_cautat]
        
        tva_produs = "21"
        if not match_db.empty and 'TVA' in match_db.columns:
            tva_raw = str(match_db.iloc[0]['TVA']).replace('%', '').replace(',', '.').strip()
            try:
                if float(tva_raw) <= 15:
                    tva_produs = "11"
            except ValueError:
                pass
        
        prod_info = {
            'nume': nume_p_afisat,
            'cantitate': cant_p_finala,
            'nume_original': nume_p_db 
        }
        
        if tva_produs == "11":
            produse_11.append(prod_info)
        else:
            produse_21.append(prod_info)
            
    # Ordinea DOAR pentru PDF, exact cum ai cerut
    def sort_key_prioritati(x):
        nume = x['nume_original']
        prio_main = get_sort_priority(nume)
        
        # Volumul contează doar dacă este SGR (prio_main == 3)
        if prio_main == 3:
            prio_vol = get_pdf_volume_priority(nume)
        else:
            prio_vol = 99
            
        return (prio_main, prio_vol, nume.lower())
        
    produse_11.sort(key=sort_key_prioritati)
    produse_21.sort(key=sort_key_prioritati)

    def deseneaza_tabel(lista_produse, titlu_tva):
        if not lista_produse: 
            return 
            
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, safe_text(f"Produse - TVA {titlu_tva}"), 0, 1, 'L')
        
        w = [20, 125, 45] 
        h = ['Nr. crt.', 'Denumire produse', 'Cantitate']
        aligns_h = ['C', 'L', 'C'] 
        
        pdf.set_font('Arial', 'B', 10) 
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        for i in range(len(h)): 
            pdf.cell(w[i], 8, safe_text(h[i]), 0, 0, aligns_h[i])
        pdf.ln(8)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        
        pdf.set_font('Arial', '', 10) 
        
        for i, prod in enumerate(lista_produse):
            pdf.cell(w[0], 7, str(i+1), 0, 0, 'C')
            nume_trunc = prod['nume'][:60] if len(prod['nume']) > 60 else prod['nume']
            pdf.cell(w[1], 7, safe_text(nume_trunc), 0, 0, 'L')
            pdf.cell(w[2], 7, f"{prod['cantitate']:.3f}", 0, 1, 'C') 
            
        pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(10) 

    deseneaza_tabel(produse_11, "11%")
    deseneaza_tabel(produse_21, "21%")
    
    return pdf.output(dest='S').encode('latin-1')

# --- LOGICĂ APP ---
df_produse = get_data(TAB_PRODUSE, COLOANE_PRODUSE)
df_comenzi = get_data(TAB_COMENZI, ['Data', 'Magazin', 'Detalii Comanda', 'Nr Comanda'])

df_produse, a_mod = migrare_automata_tva(df_produse)
if a_mod:
    if save_data(df_produse, TAB_PRODUSE): st.rerun()

st.title("🛒 Platformă Gestiune Comenzi")
st.markdown("---")

with st.sidebar:
    mod = st.radio("Meniu", ["📝 Plasează Comandă", "💼 Birou", "🔒 Panou Admin"])

if mod == "📝 Plasează Comandă":
    if st.session_state.user_logat is None:
        st.subheader("🔐 Acces Magazin")
        nume_s = st.selectbox("Alege Magazinul:", list(CREDENTIALE_MAGAZINE.keys()))
        pass_i = st.text_input("Parola:", type="password")
        if st.button("Accesare"):
            if pass_i == CREDENTIALE_MAGAZINE[nume_s]: 
                st.session_state.user_logat = nume_s
                
                df_draft = get_data(TAB_DRAFT, ['Magazin', 'Produs', 'Cantitate'])
                if not df_draft.empty:
                    draft_mag = df_draft[df_draft['Magazin'] == nume_s]
                    for _, rand in draft_mag.iterrows():
                        p = rand['Produs']
                        try:
                            c = int(float(rand['Cantitate']))
                        except:
                            c = 0
                        if c > 0:
                            st.session_state.cos_cumparaturi[p] = c
                            
                st.rerun()
            else: st.error("Parolă greșită!")
    else:
        c_h1, c_h2 = st.columns([3, 1])
        c_h1.subheader(f"📍 {st.session_state.user_logat}")
        if c_h2.button("Ieșire Cont"): st.session_state.user_logat = None; st.rerun()
        
        tab_comanda, tab_istoric = st.tabs(["📝 Comandă Nouă", "📂 Istoric Comenzi"])
        
        with tab_comanda:
            col_prod, col_cos = st.columns([2.5, 1.5])
            
            with col_cos:
                st.markdown('<div id="zona-cos" style="position:relative; top:-50px;"></div>', unsafe_allow_html=True)
                st.markdown("### 🛒 Coșul Tău")
                
                if st.session_state.edit_order_id is not None:
                    st.warning(f"⚠️ **MODIFICI COMANDA DIN {st.session_state.edit_order_date}** pentru {st.session_state.edit_order_store}. Adaugă cantități pozitive pentru a suplimenta sau negative (cu minus) pentru a scădea/șterge din comanda existentă.")
                    
                with st.container(border=True):
                    if not st.session_state.cos_cumparaturi:
                        st.info("Coșul este gol momentan. Caută produse și adaugă cantitatea dorită!")
                    else:
                        def sort_key_cos(x):
                            p_nume = x[0]
                            tva = 999
                            m = df_produse[df_produse['Nume Produs'].str.strip().str.lower() == p_nume.lower()]
                            if not m.empty:
                                try: tva = float(str(m.iloc[0]['TVA']).replace('%', '').replace(',', '.'))
                                except: pass
                            return (get_sort_priority(p_nume), tva, p_nume)

                        cos_sortat = sorted(st.session_state.cos_cumparaturi.items(), key=sort_key_cos)
                        for p, c in cos_sortat:
                            st.write(f"**{c} BUC** | {p}")
                        st.divider()
                        
                    if st.session_state.edit_order_id is not None:
                        c_btn_cancel, c_btn_save = st.columns(2)
                        
                        if c_btn_cancel.button("❌ Anulează Modificarea", use_container_width=True):
                            st.session_state.edit_order_id = None
                            st.session_state.edit_order_store = None
                            st.session_state.edit_order_date = None
                            st.session_state.cos_cumparaturi.clear()
                            st.session_state.cart_reset_counter += 1
                            st.rerun()

                        is_cart_empty = not bool(st.session_state.cos_cumparaturi)
                        if c_btn_save.button("💾 Adaugă/Scade din Comandă", use_container_width=True, type="primary", disabled=is_cart_empty):
                            nr_c_edit = st.session_state.edit_order_id
                            
                            df_comenzi['Nr Comanda Numeric'] = pd.to_numeric(df_comenzi['Nr Comanda'], errors='coerce')
                            
                            if not df_comenzi[df_comenzi['Nr Comanda Numeric'] == nr_c_edit].empty:
                                rand_comanda = df_comenzi[df_comenzi['Nr Comanda Numeric'] == nr_c_edit].iloc[0]
                                detalii_curente = str(rand_comanda['Detalii Comanda'])
                                produse_curente = parseaza_text_in_tabel(detalii_curente, df_produse)

                                dict_produse = {}
                                for p in produse_curente:
                                    try: dict_produse[p['Produs']] = float(str(p['Cantitate']).replace(',', '.').strip())
                                    except: pass

                                for p_nou, c_nou in st.session_state.cos_cumparaturi.items():
                                    if p_nou in dict_produse:
                                        dict_produse[p_nou] += c_nou
                                    else:
                                        dict_produse[p_nou] = c_nou
                                        
                                dict_produse = {k: v for k, v in dict_produse.items() if v > 0}

                                elemente = []
                                for k, v in dict_produse.items():
                                    str_v = str(int(v)) if v.is_integer() else str(v)
                                    elemente.append(f"{k}: {str_v}")
                                nou_detalii = ", ".join(elemente)

                                df_comenzi.loc[df_comenzi['Nr Comanda Numeric'] == nr_c_edit, 'Detalii Comanda'] = nou_detalii
                                df_comenzi = df_comenzi.drop(columns=['Nr Comanda Numeric'])

                                if save_data(df_comenzi, TAB_COMENZI):
                                    st.session_state.edit_order_id = None
                                    st.session_state.edit_order_store = None
                                    st.session_state.edit_order_date = None
                                    st.session_state.cos_cumparaturi.clear()
                                    st.session_state.cart_reset_counter += 1
                                    st.success("✅ Modificările au fost aplicate cu succes! Poți relua activitatea.")
                                    time.sleep(2)
                                    st.rerun()
                            else:
                                st.error("Comanda nu a fost gasita in sistem!")
                                
                    else:
                        c_btn1, c_btn2 = st.columns(2)
                        
                        if c_btn1.button("💾 Salvează Coș (Pauză)", use_container_width=True):
                            try:
                                df_draft = get_data(TAB_DRAFT, ['Magazin', 'Produs', 'Cantitate'])
                                
                                if 'Magazin' not in df_draft.columns:
                                    df_draft['Magazin'] = ""
                                if 'Produs' not in df_draft.columns:
                                    df_draft['Produs'] = ""
                                if 'Cantitate' not in df_draft.columns:
                                    df_draft['Cantitate'] = ""
                                
                                if not df_draft.empty:
                                    df_draft = df_draft[df_draft['Magazin'].astype(str) != str(st.session_state.user_logat)]
                                
                                if st.session_state.cos_cumparaturi:
                                    d_list = [{'Magazin': str(st.session_state.user_logat), 'Produs': str(p), 'Cantitate': str(c)} for p, c in st.session_state.cos_cumparaturi.items()]
                                    df_nou_draft = pd.DataFrame(d_list)
                                    
                                    if df_draft.empty:
                                        df_draft = df_nou_draft
                                    else:
                                        df_draft = pd.concat([df_draft, df_nou_draft], ignore_index=True)
                                
                                if save_data(df_draft, TAB_DRAFT):
                                    st.success("✅ Coșul a fost salvat cu succes! Poți ieși din aplicație.")
                                    
                            except Exception as e:
                                st.error(f"⚠️ Eroare la salvarea coșului: {str(e)}")

                        is_cart_empty = not bool(st.session_state.cos_cumparaturi)
                        if c_btn2.button("✅ TRIMITE COMANDA", use_container_width=True, type="primary", disabled=is_cart_empty):
                            if st.session_state.cos_cumparaturi:
                                articole = [f"{p}: {c}" for p, c in st.session_state.cos_cumparaturi.items()]
                                df_comenzi['Nr Comanda'] = pd.to_numeric(df_comenzi['Nr Comanda'], errors='coerce').fillna(0)
                                nr_nou = int(df_comenzi['Nr Comanda'].max()) + 1 if not df_comenzi.empty else 1
                                
                                ora_corecta = datetime.utcnow() + timedelta(hours=3)
                                
                                nou = pd.DataFrame({
                                    'Data': [ora_corecta.strftime("%d.%m.%Y %H:%M")], 
                                    'Magazin': [st.session_state.user_logat], 
                                    'Detalii Comanda': [", ".join(articole)], 
                                    'Nr Comanda': [nr_nou]
                                })
                                df_comenzi_actualizat = pd.concat([df_comenzi, nou], ignore_index=True)
                                
                                if save_data(df_comenzi_actualizat, TAB_COMENZI):
                                    try:
                                        df_draft = get_data(TAB_DRAFT, ['Magazin', 'Produs', 'Cantitate'])
                                        if not df_draft.empty and 'Magazin' in df_draft.columns:
                                            df_draft = df_draft[df_draft['Magazin'].astype(str) != str(st.session_state.user_logat)]
                                            save_data(df_draft, TAB_DRAFT)
                                    except Exception: 
                                        pass

                                    st.session_state.cos_cumparaturi.clear()
                                    st.session_state.cart_reset_counter += 1
                                            
                                    st.balloons()
                                    st.rerun()

            with col_prod:
                st.markdown('<div id="top-search" style="position:relative; top:-50px;"></div>', unsafe_allow_html=True)
                st.markdown("### 🔍 Produse")
                cautare = st.text_input("Caută produs...", placeholder="Scrie aici...")
                
                df_disponibile = df_produse[df_produse['In Stoc'].astype(str).str.upper() != 'NU']
                df_a = df_disponibile[df_disponibile['Nume Produs'].str.contains(cautare, case=False)] if cautare else df_disponibile.copy()
                
                df_a['priority'] = df_a['Nume Produs'].apply(get_sort_priority)
                df_a['TVA_num'] = df_a['TVA'].astype(str).str.replace('%', '').apply(pd.to_numeric, errors='coerce').fillna(999)
                
                st_col, st_dir = st.session_state.sort_state['col'], st.session_state.sort_state['dir']
                cs1, cs2, cs3 = st.columns([3, 1, 1.5])
                
                if cs1.button(f"🔤 Nume Produs"): cycle_sort('Nume Produs'); st.rerun()
                if cs2.button(f"% TVA"): cycle_sort('TVA'); st.rerun()
                cs3.markdown("<div style='text-align:center;font-weight:bold;padding-top:15px;'>Cant.</div>", unsafe_allow_html=True)
                
                if st_col and st_dir:
                    if st_col == 'Nume Produs': 
                        df_a = df_a.sort_values(by=['priority', 'Nume Produs'], ascending=[True, (st_dir=='asc')])
                    else:
                        df_a = df_a.sort_values(by=['priority', 'TVA_num', 'Nume Produs'], ascending=[True, (st_dir=='asc'), True])
                else:
                    df_a = df_a.sort_values(by=['priority', 'TVA_num', 'Nume Produs'], ascending=[True, True, True])

                df_a = df_a.drop(columns=['TVA_num', 'priority'])

                for _, r in df_a.iterrows():
                    r1, r2, r3 = st.columns([3, 1, 1.5])
                    p_nume = r['Nume Produs']
                    r1.markdown(f"<div class='big-font'>{p_nume}</div>", unsafe_allow_html=True)
                    r2.markdown(f"<div class='tva-font'>{r['TVA']}</div>", unsafe_allow_html=True)
                    
                    k = f"q_{st.session_state.cart_reset_counter}_{p_nume}"
                    if k not in st.session_state:
                        st.session_state[k] = st.session_state.cos_cumparaturi.get(p_nume, 0)
                        
                    limita_minima = -1000 if st.session_state.edit_order_id is not None else 0
                    r3.number_input("qty", limita_minima, 1000, key=k, on_change=actualizeaza_cos, args=(p_nume, k), label_visibility="collapsed")
                    st.divider()

            st.markdown('''
                <div class="floating-menu">
                    <a href="#zona-cos" class="float-btn">🛒 Coș</a>
                    <a href="#top-search" class="float-btn">🔍 Sus</a>
                </div>
            ''', unsafe_allow_html=True)

        with tab_istoric:
            cautare_istoric = st.text_input("🔍 Caută în istoric (Număr, Data, Produse)...", key="search_user")
            ist = df_comenzi[(df_comenzi['Magazin'] == st.session_state.user_logat) & (df_comenzi['Magazin'] != 'SYSTEM')].iloc[::-1]
            
            if cautare_istoric:
                term = cautare_istoric.lower()
                ist = ist[
                    ist['Nr Comanda'].astype(str).str.contains(term, case=False) |
                    ist['Data'].astype(str).str.contains(term, case=False) |
                    ist['Detalii Comanda'].astype(str).str.contains(term, case=False)
                ]
                
            for idx, r in ist.iterrows():
                with st.container(border=True):
                    try:
                        nr_c = int(float(r['Nr Comanda']))
                    except:
                        nr_c = 0
                    
                    uid = f"{nr_c}_{idx}"
                        
                    st.write(f"🗓️ {r['Data']} | 🆔 Comanda #{nr_c}")
                    lista_p_user = parseaza_text_in_tabel(r['Detalii Comanda'], df_produse)
                    df_ist_tabel = pd.DataFrame(lista_p_user)
                    if not df_ist_tabel.empty:
                        df_ist_tabel.index = df_ist_tabel.index + 1
                        st.table(df_ist_tabel)
                    
                    try:
                        data_f_nume = str(r['Data']).split(' ')[0].replace('/', '.')
                        nume_scurt = CREDENTIALE_MAGAZINE.get(str(r['Magazin']), str(r['Magazin'])).upper()
                        
                        pdf_key = f"pdf_data_user_{uid}"
                        if pdf_key not in st.session_state:
                            if st.button(f"📄 Generează PDF #{nr_c}", key=f"btn_gen_user_{uid}"):
                                with st.spinner("Generez PDF-ul..."):
                                    st.session_state[pdf_key] = genereaza_pdf_aviz(r['Data'], r['Magazin'], lista_p_user, nr_c, df_produse)
                                st.rerun()
                        else:
                            st.download_button(
                                label=f"📥 Descarcă PDF #{nr_c}", 
                                data=st.session_state[pdf_key], 
                                file_name=f"Necesar {nume_scurt} ({data_f_nume}).pdf", 
                                mime="application/pdf",
                                key=f"btn_dl_user_{uid}",
                                type="primary"
                            )
                    except Exception as e: 
                        st.error(f"Eroare la generarea PDF-ului: {e}")

                    with st.expander("➕ Modificare Comandă (Necesită Parolă Admin)"):
                        c_pass, c_btn = st.columns(2)
                        parola = c_pass.text_input("Parola Admin:", type="password", key=f"pass_mod_user_{uid}")
                        if c_btn.button("🛒 Editează Comanda", key=f"btn_mod_user_{uid}"):
                            if parola == PAROLA_ADMIN:
                                st.session_state.edit_order_id = nr_c
                                st.session_state.edit_order_store = r['Magazin']
                                st.session_state.edit_order_date = str(r['Data']).split(' ')[0]
                                st.session_state.cos_cumparaturi.clear()
                                st.session_state.cart_reset_counter += 1
                                st.success("✅ Mod de editare activat! Mergi la tab-ul '📝 Comandă Nouă' pentru modificarea comenzilor.")
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.error("Parolă incorectă!")

# --- SECȚIUNEA NOUĂ: BIROU ---
elif mod == "💼 Birou":
    if st.sidebar.text_input("Parola Birou", type="password") == PAROLA_BIROU:
        st.subheader("💼 Panou Birou")
        
        cautare_birou = st.text_input("🔍 Caută / Filtrează comanda (Magazin, Număr, Data, Produse)...", key="search_birou")
        
        if not df_comenzi.empty:
            df_afisare_birou = df_comenzi[df_comenzi['Magazin'] != 'SYSTEM'].iloc[::-1]
        else:
            df_afisare_birou = pd.DataFrame(columns=['Data', 'Magazin', 'Detalii Comanda', 'Nr Comanda'])

        if cautare_birou and not df_afisare_birou.empty:
            term_b = cautare_birou.lower()
            df_afisare_birou = df_afisare_birou[
                df_afisare_birou['Nr Comanda'].astype(str).str.contains(term_b, case=False) |
                df_afisare_birou['Data'].astype(str).str.contains(term_b, case=False) |
                df_afisare_birou['Detalii Comanda'].astype(str).str.contains(term_b, case=False) |
                df_afisare_birou['Magazin'].astype(str).str.contains(term_b, case=False)
            ]
        
        st.divider()
        
        if df_afisare_birou.empty:
            st.success("Tabelul este curat. Nu există nicio comandă plasată momentan.")
        else:
            for idx, r in df_afisare_birou.iterrows():
                with st.container(border=True):
                    try:
                        nr_c = int(float(r['Nr Comanda']))
                    except:
                        nr_c = 0
                        
                    uid = f"{nr_c}_{idx}"
                        
                    st.write(f"📦 #{nr_c} - {r['Magazin']} | {r['Data']}")
                    lista_p = parseaza_text_in_tabel(r['Detalii Comanda'], df_produse)
                    df_birou_tab = pd.DataFrame(lista_p)
                    if not df_birou_tab.empty:
                        df_birou_tab.index = df_birou_tab.index + 1
                        st.table(df_birou_tab)
                    try:
                        data_f_nume = str(r['Data']).split(' ')[0].replace('/', '.')
                        nume_scurt = CREDENTIALE_MAGAZINE.get(str(r['Magazin']), str(r['Magazin'])).upper()
                        
                        pdf_key = f"pdf_data_birou_{uid}"
                        if pdf_key not in st.session_state:
                            if st.button(f"📄 Generează PDF #{nr_c}", key=f"btn_gen_birou_{uid}"):
                                with st.spinner("Generez PDF-ul..."):
                                    st.session_state[pdf_key] = genereaza_pdf_aviz(r['Data'], r['Magazin'], lista_p, nr_c, df_produse)
                                st.rerun()
                        else:
                            st.download_button(
                                label=f"📥 Descarcă PDF #{nr_c}", 
                                data=st.session_state[pdf_key], 
                                file_name=f"Necesar {nume_scurt} ({data_f_nume}).pdf", 
                                mime="application/pdf",
                                key=f"btn_dl_birou_{uid}",
                                type="primary"
                            )
                    except Exception as e: 
                        st.error(f"Eroare PDF: {e}")
                        
                    with st.expander("➕ Modificare Comandă (Adaugă/Scade Produse)"):
                        c_pass, c_btn = st.columns(2)
                        parola = c_pass.text_input("Parola Admin:", type="password", key=f"pass_mod_birou_{uid}")
                        if c_btn.button("🛒 Mergi la magazin pentru editare", key=f"btn_mod_birou_{uid}"):
                            if parola == PAROLA_ADMIN:
                                st.session_state.edit_order_id = nr_c
                                st.session_state.edit_order_store = r['Magazin']
                                st.session_state.edit_order_date = str(r['Data']).split(' ')[0]
                                st.session_state.user_logat = r['Magazin']
                                st.session_state.cos_cumparaturi.clear()
                                st.session_state.cart_reset_counter += 1
                                st.success("✅ Mod de editare activat! Navighează manual la secțiunea '📝 Plasează Comandă' din meniul stânga.")
                            else:
                                st.error("Parolă incorectă!")

# --- SECȚIUNEA ADMIN ---
elif mod == "🔒 Panou Admin":
    if st.sidebar.text_input("Parola", type="password") == PAROLA_ADMIN:
        st.subheader("🛠️ Administrare")
        
        t1, t_stoc, t2 = st.tabs(["📦 Produse", "📊 Stoc", "📄 Comenzi"])
        
        with t1:
            with st.expander("📤 Import listă (Excel/salvat .csv)"):
                st.info("💡 **Format Coloane Excel: Cod SAGA, Nume Produs, TVA, UM, Pret Unitar, Pret Vanzare.**")
                up = st.file_uploader("", type=['csv', 'xlsx', 'xls']) 
                
                if up is not None:
                    if st.button("📥 Pornește Importul Fișierului"):
                        try:
                            if up.name.endswith('.csv'): df_up = curata_preturi_import(pd.read_csv(up, sep=None, engine='python'))
                            else: df_up = curata_preturi_import(pd.read_excel(up))
                            
                            df_produse = pd.concat([df_produse, df_up]).drop_duplicates(subset=['Nume Produs'], keep='last')
                            df_produse['In Stoc'] = df_produse.get('In Stoc', 'DA').fillna('DA').replace('', 'DA')
                            
                            df_produse, _ = migrare_automata_tva(df_produse)
                            df_produse = df_produse[[c for c in COLOANE_PRODUSE if c in df_produse.columns]]
                            
                            if save_data(df_produse, TAB_PRODUSE):
                                st.success("✅ Produsele au fost salvate pe bune în Google Sheets!")
                                st.rerun()
                        except Exception as e: st.error(f"Eroare la procesarea fișierului: {e}")
            
            st.markdown("##### ➕ Produs Nou/Actualizare pret")
            with st.form("form_produs_nou"):
                c1, c2, c3 = st.columns([1, 2, 1])
                p_n = c2.text_input("Nume Produs")
                t_n = c3.selectbox("TVA", ["11%", "21%"])
                
                c4, c5, c6 = st.columns(3)
                um_n = c4.selectbox("UM (Unitate Măsură)", ["", "BUC", "PET", "KG", "BAX"])
                p_u = c5.number_input("Achiziție", 0.00, step=0.01, format="%.2f")
                p_v = c6.number_input("Vânzare", 0.00, step=0.01, format="%.2f")
                
                if st.form_submit_button("Salvează Produs"):
                    if p_n.strip() != "":
                        df_produse = df_produse[df_produse['Nume Produs'] != p_n]
                        df_nou = pd.DataFrame({'Cod SAGA': [cod_s], 'TVA':[t_n], 'Nume Produs':[p_n], 'UM':[um_n], 'Pret Unitar':[p_u],'Pret Vanzare':[p_v], 'In Stoc': ['DA']})
                        df_produse = pd.concat([df_produse, df_nou])
                        df_produse = df_produse[[c for c in COLOANE_PRODUSE if c in df_produse.columns]]
                        if save_data(df_produse, TAB_PRODUSE): st.rerun()
                    else: st.warning("Te rog să completezi numele produsului!")
            
            st.divider()
            cautare_admin_produse = st.text_input("🔍 Caută un produs în tabel...", placeholder="Scrie numele produsului...")
            
            df_disp_prod = df_produse.copy()
            if cautare_admin_produse:
                df_disp_prod = df_disp_prod[df_disp_prod['Nume Produs'].str.contains(cautare_admin_produse, case=False, na=False)]
            
            if 'Cod SAGA' in df_disp_prod.columns:
                df_disp_prod['Cod SAGA'] = df_disp_prod['Cod SAGA'].astype(str).str.replace(r'\.0$', '', regex=True)

            df_disp_prod['Pret Unitar'] = pd.to_numeric(df_disp_prod['Pret Unitar'], errors='coerce').fillna(0.0).map(lambda x: f"{x:.2f}")
            df_disp_prod['Pret Vanzare'] = pd.to_numeric(df_disp_prod['Pret Vanzare'], errors='coerce').fillna(0.0).map(lambda x: f"{x:.2f}")
            
            df_disp_prod.index = range(1, len(df_disp_prod) + 1)
            st.dataframe(df_disp_prod, use_container_width=True)
            
            st.divider(); st.subheader("🗑️ Ștergere Produs Individual")
            p_del = st.selectbox("Alege produsul:", options=df_produse['Nume Produs'].tolist(), index=None, placeholder="Scrie sau alege un produs pentru ștergere...")
            if st.button("❌ Șterge Produsul Selectat"):
                if p_del:
                    append_data(df_produse[df_produse['Nume Produs'] == p_del], TAB_ARHIVA_PRODUSE)
                    df_produse = df_produse[df_produse['Nume Produs'] != p_del]
                    if save_data(df_produse, TAB_PRODUSE): st.rerun()
                else:
                    st.warning("Te rog să selectezi un produs din listă mai întâi!")

            st.divider()
            st.subheader("🚨 Resetare Bază de Date Produse")
            confirm_del_all = st.checkbox("Sunt sigur că vreau să șterg TOATE produsele din magazin!")
            if st.button("🧨 ȘTERGE TOT") and confirm_del_all:
                if not df_produse.empty: append_data(df_produse, TAB_ARHIVA_PRODUSE) 
                df_gol = pd.DataFrame(columns=COLOANE_PRODUSE)
                if save_data(df_gol, TAB_PRODUSE): st.rerun()

        with t_stoc:
            st.subheader("📊 Gestionare Stoc Produse")
            st.info("Bifează produsele care NU SUNT ÎN STOC (Stoc 0). Acestea vor dispărea de pe panoul de comandă al magazinelor, fără a fi șterse din sistem.")

            cautare_stoc = st.text_input("🔍 Caută produs pentru stoc...", key="search_stoc")

            df_edit_stoc = df_produse.copy()
            df_edit_stoc['Lipsă Stoc'] = df_edit_stoc['In Stoc'].apply(lambda x: True if str(x).upper() == 'NU' else False)

            if cautare_stoc:
                df_edit_stoc = df_edit_stoc[df_edit_stoc['Nume Produs'].str.contains(cautare_stoc, case=False)]

            st.write("### Listă Produse")
            edited_stoc = st.data_editor(
                df_edit_stoc[['Nume Produs', 'Lipsă Stoc']],
                hide_index=True,
                disabled=['Nume Produs'],
                use_container_width=True,
                height=500
            )

            if st.button("💾 Salvează Modificările de Stoc", type="primary"):
                for _, r in edited_stoc.iterrows():
                    nume = r['Nume Produs']
                    lipsa = r['Lipsă Stoc']
                    val_noua = "NU" if lipsa else "DA"
                    df_produse.loc[df_produse['Nume Produs'] == nume, 'In Stoc'] = val_noua

                if save_data(df_produse, TAB_PRODUSE):
                    st.success("✅ Stocul a fost actualizat cu succes!")
                    time.sleep(1)
                    st.rerun()

        with t2:
            st.markdown('<div id="top-admin-comenzi" style="position:relative; top:-50px;"></div>', unsafe_allow_html=True)
            
            
            cautare_admin = st.text_input("🔍 Caută / Filtrează comanda (Magazin, Număr, Data, Produse)...", key="search_admin")
            
            if not df_comenzi.empty:
                df_afisare = df_comenzi[df_comenzi['Magazin'] != 'SYSTEM'].iloc[::-1]
            else:
                df_afisare = pd.DataFrame(columns=['Data', 'Magazin', 'Detalii Comanda', 'Nr Comanda'])

            if cautare_admin and not df_afisare.empty:
                term_a = cautare_admin.lower()
                df_afisare = df_afisare[
                    df_afisare['Nr Comanda'].astype(str).str.contains(term_a, case=False) |
                    df_afisare['Data'].astype(str).str.contains(term_a, case=False) |
                    df_afisare['Detalii Comanda'].astype(str).str.contains(term_a, case=False) |
                    df_afisare['Magazin'].astype(str).str.contains(term_a, case=False)
                ]

            
            st.divider()
            
            if df_afisare.empty:
                st.success("Tabelul este curat. Nu există nicio comandă plasată momentan.")
            else:
                for idx, r in df_afisare.iterrows():
                    with st.container(border=True):
                        try:
                            nr_c = int(float(r['Nr Comanda']))
                        except:
                            nr_c = 0
                            
                        uid = f"{nr_c}_{idx}"
                            
                        st.write(f"📦 #{nr_c} - {r['Magazin']} | {r['Data']}")
                        lista_p = parseaza_text_in_tabel(r['Detalii Comanda'], df_produse)
                        df_adm_tab = pd.DataFrame(lista_p)
                        if not df_adm_tab.empty:
                            df_adm_tab.index = df_adm_tab.index + 1
                            st.table(df_adm_tab)
                        try:
                            data_f_nume = str(r['Data']).split(' ')[0].replace('/', '.')
                            nume_scurt = CREDENTIALE_MAGAZINE.get(str(r['Magazin']), str(r['Magazin'])).upper()
                            
                            pdf_key = f"pdf_data_admin_{uid}"
                            if pdf_key not in st.session_state:
                                if st.button(f"📄 Generează PDF #{nr_c}", key=f"btn_gen_admin_{uid}"):
                                    with st.spinner("Generez PDF-ul..."):
                                        st.session_state[pdf_key] = genereaza_pdf_aviz(r['Data'], r['Magazin'], lista_p, nr_c, df_produse)
                                    st.rerun()
                            else:
                                st.download_button(
                                    label=f"📥 Descarcă PDF #{nr_c}", 
                                    data=st.session_state[pdf_key], 
                                    file_name=f"Necesar {nume_scurt} ({data_f_nume}).pdf", 
                                    mime="application/pdf",
                                    key=f"btn_dl_admin_{uid}",
                                    type="primary"
                                )
                        except Exception as e: 
                            st.error(f"Eroare PDF: {e}")
                            
                        with st.expander("➕ Modificare Comandă (Adaugă/Scade Produse)"):
                            c_pass, c_btn = st.columns(2)
                            parola = c_pass.text_input("Parola Admin:", type="password", key=f"pass_mod_admin_{uid}")
                            if c_btn.button("🛒 Mergi la magazin pentru editare", key=f"btn_mod_admin_{uid}"):
                                if parola == PAROLA_ADMIN:
                                    st.session_state.edit_order_id = nr_c
                                    st.session_state.edit_order_store = r['Magazin']
                                    st.session_state.edit_order_date = str(r['Data']).split(' ')[0]
                                    st.session_state.user_logat = r['Magazin']
                                    st.session_state.cos_cumparaturi.clear()
                                    st.session_state.cart_reset_counter += 1
                                    st.success("✅ Mod de editare activat! Navighează manual la secțiunea '📝 Plasează Comandă' din meniul stânga.")
                                else:
                                    st.error("Parolă incorectă!")

            st.markdown('<div id="zona-stergere-comenzi" style="position:relative; top:-50px;"></div>', unsafe_allow_html=True)
            st.divider()
            st.subheader("🗑️ Ștergere Comenzi")
            
            # AM ADĂUGAT DEFINIREA VARIABILEI AICI
            lista_edit_c = []
            if 'df_afisare' in locals() and not df_afisare.empty:
                for _, r in df_afisare.iterrows():
                    try:
                        nr_c = int(float(r['Nr Comanda']))
                    except:
                        nr_c = 0
                    lista_edit_c.append(f"#{nr_c} - {r['Magazin']} | {r['Data']}")

            if lista_edit_c:
                c_del = st.selectbox("Selectează comanda pentru ștergere individuală:", lista_edit_c)
                if st.button("🗑️ Șterge Comanda Selectată"):
                    nr_s = int(c_del.split(" ")[0].replace("#", ""))
                    
                    df_comenzi['Nr Comanda Numeric'] = pd.to_numeric(df_comenzi['Nr Comanda'], errors='coerce')
                    append_data(df_comenzi[df_comenzi['Nr Comanda Numeric'] == nr_s].drop(columns=['Nr Comanda Numeric']), TAB_ARHIVA_COMENZI)
                    df_comenzi = df_comenzi[df_comenzi['Nr Comanda Numeric'] != nr_s]
                    df_comenzi = df_comenzi.drop(columns=['Nr Comanda Numeric'])
                    
                    if save_data(df_comenzi, TAB_COMENZI): st.rerun()
            else:
                st.info("Nu există comenzi pentru a fi șterse individual.")
            
            st.write("---")
            confirm = st.checkbox("Bifează pentru confirmarea ștergerii TUTUROR comenzilor")
            if st.button("🚨 RESET TOTAL COMENZI") and confirm:
                if not df_comenzi[df_comenzi['Magazin'] != 'SYSTEM'].empty:
                    append_data(df_comenzi[df_comenzi['Magazin'] != 'SYSTEM'], TAB_ARHIVA_COMENZI)
                df_config = df_comenzi[df_comenzi['Magazin'] == 'SYSTEM']
                if save_data(df_config, TAB_COMENZI): st.rerun()

            st.write("---")
            st.subheader("🔢 Setări Numărătoare Comenzi")
            st.info("Aici poți seta de la ce număr va începe următoarea comandă plasată în sistem.")
            
            c_nr1, c_nr2 = st.columns([1, 2])
            numar_start = c_nr1.number_input("Număr următoarea comandă:", min_value=1, value=1, step=1)
            
            if c_nr2.button("🔄 Setează Numărul", use_container_width=True):
                df_comenzi_clean = df_comenzi[df_comenzi['Magazin'] != 'SYSTEM']
                nou_config = pd.DataFrame({
                    'Data': ['CONFIG'], 
                    'Magazin': ['SYSTEM'], 
                    'Detalii Comanda': ['Setare numar custom'], 
                    'Nr Comanda': [numar_start - 1]
                })
                df_comenzi_actualizat = pd.concat([df_comenzi_clean, nou_config], ignore_index=True)
                if save_data(df_comenzi_actualizat, TAB_COMENZI):
                    st.success(f"✅ Sistemul a fost actualizat! Următoarea comandă va avea numărul {numar_start}.")
                    time.sleep(2)
                    st.rerun()
                    
            # MENIUL PLUTITOR DIN STANGA ADAUGAT AICI
            st.markdown('''
                <div class="floating-menu-left">
                    <a href="#zona-stergere-comenzi" class="float-btn">🗑️ Ștergere</a>
                    <a href="#top-admin-comenzi" class="float-btn">⬆️ Sus</a>
                </div>
            ''', unsafe_allow_html=True)
