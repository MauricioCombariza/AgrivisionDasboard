# Sectores.py
import streamlit as st
import pandas as pd
import io
import re

try:
    from utils.sector_rules import SECTOR_RULES
    import utils.sectores_finales as address_parser
except ImportError:
    st.error("Error al importar módulos desde la carpeta 'utils'.")
    st.stop()

# --- NUEVAS FUNCIONES DE UTILIDAD PARA COMPARACIÓN ALFANUMÉRICA ---

def parse_rule_limit(value: str) -> tuple:
    """
    Parsea un límite de regla como "67 Z" en una tupla (67, 'Z').
    Si no hay letra, devuelve (número, '').
    """
    match = re.search(r'(\d+)\s*([A-Z])?', str(value))
    if match:
        number = int(match.group(1))
        letter = match.group(2) if match.group(2) else '' # Usar '' en vez de None para facilitar la comparación
        return (number, letter)
    return (0, '') # Fallback

def is_within_bounds(addr_tuple: tuple, min_tuple: tuple, max_tuple: tuple, inclusive_max: bool = True) -> bool:
    """
    Compara si una tupla de dirección (num, letra) está dentro de un rango.
    Python compara tuplas lexicográficamente, que es exactamente lo que necesitamos:
    (67, 'D') > (67, 'C') -> True
    (67, 'D') < (68, 'A') -> True
    """
    if addr_tuple < min_tuple:
        return False
    
    if inclusive_max:
        return addr_tuple <= max_tuple # Para la vía principal
    else:
        return addr_tuple < max_tuple  # Para la vía secundaria (lógica de "max - 1")

def check_parity(number_str: str, parity_rule: str) -> bool:
    """ Verifica la paridad de un número dado como string. """
    try:
        number = int(float(number_str))
        parity_rule = parity_rule.upper()
        if parity_rule == 'CUALQUIERA': return True
        if parity_rule == 'PAR': return number % 2 == 0
        if parity_rule == 'IMPAR': return number % 2 != 0
    except (ValueError, TypeError):
        return False
    return False

# --- FUNCIÓN find_sector RECONSTRUIDA ---

def find_sector(row: pd.Series) -> str:
    """
    Implementa la lógica de sector con comparación alfanumérica.
    """
    try:
        orientacion_addr = row['orientacion']
        street_type = row['street_type']
        
        # Crear tuplas para la dirección, tratando letras None como ''
        calle_tuple = (int(float(row['calle_abs'])), row['letra_calle'] or '')
        carrera_tuple = (int(float(row['carrera_abs'])), row['letra_carrera'] or '')
        
        num_placa_str = row['num_placa']
    except (ValueError, TypeError, KeyError):
        return "Datos Insuficientes"

    for rule in SECTOR_RULES:
        try:
            # 1. Filtro por orientación
            if rule['orientacion'].upper() != orientacion_addr.upper():
                continue

            # 2. Parsear los límites de la regla a tuplas (num, letra)
            min_calle, max_calle = parse_rule_limit(rule['reglas'][0]), parse_rule_limit(rule['reglas'][1])
            paridad_calle_max = rule['reglas'][2]
            
            min_carrera, max_carrera = parse_rule_limit(rule['reglas'][3]), parse_rule_limit(rule['reglas'][4])
            paridad_carrera_max = rule['reglas'][5]
            
            # 3. Aplicar lógica condicional
            is_match = False
            
            if street_type in ['CALLE', 'DIAGONAL']:
                # Vía principal: CALLE (rango inclusivo)
                # Vía secundaria: CARRERA (rango exclusivo en el máximo)
                calle_ok = is_within_bounds(calle_tuple, min_calle, max_calle, inclusive_max=True)
                carrera_ok = is_within_bounds(carrera_tuple, min_carrera, max_carrera, inclusive_max=False)
                
                placa_ok = True # Asumir OK por defecto
                if calle_tuple == max_calle: # Condición de placa
                    placa_ok = check_parity(num_placa_str, paridad_calle_max)
                
                if calle_ok and carrera_ok and placa_ok:
                    is_match = True

            elif street_type in ['CARRERA', 'TRANSVERSAL']:
                # Vía principal: CARRERA (rango inclusivo)
                # Vía secundaria: CALLE (rango exclusivo en el máximo)
                carrera_ok = is_within_bounds(carrera_tuple, min_carrera, max_carrera, inclusive_max=True)
                calle_ok = is_within_bounds(calle_tuple, min_calle, max_calle, inclusive_max=False)

                placa_ok = True # Asumir OK por defecto
                if carrera_tuple == max_carrera: # Condición de placa
                    placa_ok = check_parity(num_placa_str, paridad_carrera_max)

                if carrera_ok and calle_ok and placa_ok:
                    is_match = True
            
            if is_match:
                return rule['sector']

        except (ValueError, IndexError):
            continue

    return "Sector No Encontrado"

# --- Interfaz de la aplicación Streamlit (sin cambios en su estructura) ---

st.title("Asignador de Sectores (Comparación Alfanumérica)")
st.markdown("Sube tu archivo Excel. La lógica ahora compara correctamente números y letras en las direcciones.")

uploaded_file = st.file_uploader("Elige un archivo Excel (.xlsx)", type=["xlsx"])

if uploaded_file:
    # ... (El resto del código de la interfaz de Streamlit es idéntico al anterior) ...
    st.info("Archivo subido. Procesando...")
    try:
        df = pd.read_excel(uploaded_file)
        
        if 'direccion' not in df.columns:
            st.error("Error: El archivo Excel debe contener una columna 'direccion'.")
        else:
            with st.spinner('Extrayendo componentes de las direcciones...'):
                component_cols = ['orientacion', 'calle_abs', 'letra_calle', 'carrera_abs', 'letra_carrera', 'num_placa', 'street_type']
                df[component_cols] = df['direccion'].apply(address_parser.extract_address_components)
            st.success("Componentes de dirección extraídos.")

            with st.spinner('Asignando sectores con lógica alfanumérica...'):
                df['sector_asignado'] = df.apply(find_sector, axis=1)
            st.success("Procesamiento completado.")
            
            final_cols = ['direccion', 'sector_asignado'] + component_cols + [col for col in df.columns if col not in ['direccion', 'sector_asignado'] + component_cols]
            df_final = df[final_cols]
            st.dataframe(df_final)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Sectores_Asignados')
            st.download_button(
                label="📥 Descargar archivo Excel procesado",
                data=output.getvalue(),
                file_name="direcciones_con_sectores_alfanumerico.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    except Exception as e:
        st.error(f"Ocurrió un error: {e}")
        st.warning("Asegúrate de que el archivo es un formato Excel (.xlsx) válido.")
else:
    st.info("Esperando un archivo Excel para comenzar el proceso.")