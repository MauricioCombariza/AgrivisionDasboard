import streamlit as st
import pandas as pd
import re
import io

def clean_and_normalize(text):
    """
    Limpia y normaliza el texto de la dirección para una mejor extracción.
    """
    if isinstance(text, str):
        # Elimina acentos y convierte a mayúsculas
        text = text.upper()
        text = text.replace('Á', 'A').replace('É', 'E').replace('Í', 'I').replace('Ó', 'O').replace('Ú', 'U')
        # Reemplaza abreviaturas comunes
        text = text.replace('AV.', 'AVENIDA').replace('CR', 'CARRERA').replace('CL', 'CALLE')
        text = text.replace('#', ' ').replace('-', ' ')
        return text
    return text

def extract_address_components(address):
    """
    Extrae los componentes de la dirección utilizando expresiones regulares.
    """
    address = clean_and_normalize(address)
    
    # Expresiones regulares para cada componente
    # Buscar "AVENIDA CALLE", "AVENIDA CARRERA", "CALLE", "CARRERA"
    main_street_type = ''
    if re.search(r'AVENIDA\s+CALLE', address):
        main_street_type = 'CALLE'
    elif re.search(r'AVENIDA\s+CARRERA', address):
        main_street_type = 'CARRERA'
    elif re.search(r'CALLE', address):
        main_street_type = 'CALLE'
    elif re.search(r'CARRERA', address):
        main_street_type = 'CARRERA'

    calle_abs = None
    letra_calle = None
    carrera_abs = None
    letra_carrera = None
    num_placa = None
    
    # Regex para extraer números y letras
    # Ejemplo: 'Calle 100 49-97' -> extrae 100, 49, 97
    # Ejemplo: 'Av. Carrera 64 #67D-67' -> extrae 64, 67, 67
    
    # Patrón general para capturar los números
    # Captura 1: tipo de vía (CALLE|CARRERA)
    # Captura 2: número absoluto de calle/carrera
    # Captura 3: letra de calle (si existe)
    # Captura 4: número absoluto de carrera/calle
    # Captura 5: letra de carrera (si existe)
    # Captura 6: número de placa
    
    pattern = r'(?:CALLE|CARRERA)\s+(\d+)\s*([A-Z])?'
    
    # Si la dirección principal es 'CALLE'
    if main_street_type == 'CALLE':
        match = re.search(r'CALLE\s+(\d+)\s*([A-Z])?\s*(?:CARRERA)?\s*(\d+)\s*([A-Z])?\s*(\d+)', address)
        if match:
            calle_abs = match.group(1)
            letra_calle = match.group(2) if match.group(2) else None
            carrera_abs = match.group(3)
            letra_carrera = match.group(4) if match.group(4) else None
            num_placa = match.group(5)

    # Si la dirección principal es 'CARRERA'
    elif main_street_type == 'CARRERA':
        match = re.search(r'CARRERA\s+(\d+)\s*([A-Z])?\s*(?:CALLE)?\s*(\d+)\s*([A-Z])?\s*(\d+)', address)
        if match:
            carrera_abs = match.group(1)
            letra_carrera = match.group(2) if match.group(2) else None
            calle_abs = match.group(3)
            letra_calle = match.group(4) if match.group(4) else None
            num_placa = match.group(5)
            
    # Lógica para manejar casos donde el tipo de vía no está explícito al inicio
    if not (calle_abs and carrera_abs and num_placa):
        # Patrón más flexible para cualquier secuencia de números y letras
        # Esto es menos robusto pero puede capturar casos más variados
        parts = re.findall(r'(\d+)\s*([A-Z])?', address)
        if len(parts) >= 3:
            calle_abs = parts[0][0]
            letra_calle = parts[0][1] if parts[0][1] else None
            
            carrera_abs = parts[1][0]
            letra_carrera = parts[1][1] if parts[1][1] else None
            
            num_placa = parts[2][0]

    return pd.Series([calle_abs, letra_calle, carrera_abs, letra_carrera, num_placa])

# --- Interfaz de la aplicación Streamlit ---
st.set_page_config(page_title="Extractor de Direcciones", layout="wide")
st.title("Extractor de Componentes de Direcciones con Regex")
st.subheader("Sube un archivo Excel para procesar y completar las columnas de dirección.")

uploaded_file = st.file_uploader("Elige un archivo Excel (.xlsx)", type=["xlsx"])

if uploaded_file:
    st.success("Archivo subido exitosamente. Procesando...")
    try:
        # Leer el archivo de Excel
        df = pd.read_excel(uploaded_file)
        
        # Validar si la columna 'direccion' existe
        if 'direccion' not in df.columns:
            st.error("El archivo Excel debe contener una columna llamada **'direccion'**.")
        else:
            # Procesar el DataFrame
            df[['calle_abs', 'letra_calle', 'carrera_abs', 'letra_carrera', 'num_placa']] = df['direccion'].apply(extract_address_components)
            
            st.success("Procesamiento completado. Tabla de resultados:")
            st.dataframe(df)

            # Opción para descargar el archivo procesado
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Direcciones_Procesadas')
            
            st.download_button(
                label="Descargar archivo Excel procesado",
                data=output.getvalue(),
                file_name="direcciones_procesadas.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"Ocurrió un error al procesar el archivo: {e}")
else:
    st.info("Sube tu archivo para comenzar. La tabla resultante se mostrará aquí.")