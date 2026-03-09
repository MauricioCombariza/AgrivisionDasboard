# utils/utils_sectores_finales.py
import streamlit as st
import pandas as pd
import re
import io

# --- FUNCIONES DE UTILIDAD ---

def clean_and_normalize(text):
    if not isinstance(text, str): return ""
    text = text.upper().replace('Á', 'A').replace('É', 'E').replace('Í', 'I').replace('Ó', 'O').replace('Ú', 'U')
    text = text.replace('AV.', 'AVENIDA').replace('CL', 'CALLE').replace('CLL', 'CALLE')
    text = text.replace('CR', 'CARRERA').replace('KR', 'CARRERA').replace('KRA', 'CARRERA')
    text = text.replace('DG', 'DIAGONAL').replace('DIAG', 'DIAGONAL')
    text = text.replace('TV', 'TRANSVERSAL').replace('TR', 'TRANSVERSAL')
    text = re.sub(r'[#\-(),]', ' ', text)
    text = re.sub(r'[^A-Z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_orientation(normalized_address):
    if " SUR " in normalized_address: return "SUR"
    if " ESTE " in normalized_address: return "ESTE"
    return "NORTE"

def extract_address_components(address):
    """
    Extrae componentes y AÑADE EL TIPO DE VÍA PRINCIPAL ('CALLE', 'CARRERA', 'UNKNOWN').
    """
    address_norm = clean_and_normalize(address)
    orientacion = extract_orientation(address_norm)
    
    if address_norm.startswith("AVENIDA "):
        address_norm_for_logic = address_norm.replace("AVENIDA ", "", 1)
    else:
        address_norm_for_logic = address_norm
    
    calle_abs, letra_calle, carrera_abs, letra_carrera, num_placa, street_type = None, None, None, None, None, 'UNKNOWN'
    
    parts = re.findall(r'(\d+)\s*([A-Z])?', address_norm_for_logic)
    
    if len(parts) >= 2:
        num1, letra1 = parts[0]
        num2, letra2 = parts[1]
        
        if address_norm_for_logic.startswith(('CARRERA', 'TRANSVERSAL')):
            street_type = 'CARRERA'
            carrera_abs, letra_carrera = num1, letra1
            calle_abs, letra_calle = num2, letra2
        
        elif address_norm_for_logic.startswith(('CALLE', 'DIAGONAL')):
            street_type = 'CALLE'
            calle_abs, letra_calle = num1, letra1
            carrera_abs, letra_carrera = num2, letra2
            
        else: # Fallback por defecto es tratarlo como CALLE
            street_type = 'CALLE'
            calle_abs, letra_calle = num1, letra1
            carrera_abs, letra_carrera = num2, letra2
            
        if len(parts) >= 3:
            num_placa = parts[2][0]

    letra_calle = letra_calle if letra_calle else None
    letra_carrera = letra_carrera if letra_carrera else None
            
    return pd.Series([orientacion, calle_abs, letra_calle, carrera_abs, letra_carrera, num_placa, street_type])

# --- CÓDIGO DE LA APLICACIÓN (SIN CAMBIOS) ---
def main():
    st.set_page_config(page_title="Extractor de Direcciones", layout="wide")
    st.title("Extractor de Componentes de Direcciones (V4 - Con Tipo de Vía)")
    st.markdown("Ahora extrae también el tipo de vía principal para una lógica de sectores más avanzada.")
    uploaded_file = st.file_uploader("Elige un archivo Excel (.xlsx)", type=["xlsx"])
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        if 'direccion' not in df.columns:
            st.error("El archivo debe tener una columna 'direccion'.")
        else:
            component_cols = ['orientacion', 'calle_abs', 'letra_calle', 'carrera_abs', 'letra_carrera', 'num_placa', 'street_type']
            df[component_cols] = df['direccion'].apply(extract_address_components)
            st.dataframe(df)
            # Lógica de descarga...

if __name__ == "__main__":
    main()