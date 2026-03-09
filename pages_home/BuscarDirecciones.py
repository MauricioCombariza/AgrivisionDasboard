# BuscarDirecciones.py - AJUSTE DE TIPO DE DATOS EN EL MERGE
import streamlit as st
import pandas as pd
import io
import mysql.connector
from mysql.connector import Error
from utils.db_connection import conectar_bd

# Importar la función de conexión de tu módulo
# try:
#     from ..utils.db_connection import conectar_bd
#     # Usaremos Error de mysql.connector (ya importado arriba)
# except ImportError:
#     st.error("❌ Error al importar utils.db_conection. Asegúrate de que el archivo existe en la carpeta 'utils'.")
#     st.stop()
# except Exception as e:
#     st.error(f"❌ Error al cargar la conexión de la DB: {e}")
#     st.stop()

# --- Constantes ---
DB_TABLE = "paquetes"

# --- Función de Consulta a MySQL ---

def fetch_addresses_for_serials(serials: list) -> pd.DataFrame:
    """
    Busca la dirección en MySQL para una lista de seriales utilizando conectar_bd().
    """
    cnx = conectar_bd()
    if cnx is None:
        return pd.DataFrame(columns=['serial', 'direccion_DB'])
        
    if not serials:
        if cnx and cnx.is_connected():
            cnx.close()
        return pd.DataFrame(columns=['serial', 'direccion_DB'])

    # La lista 'serials' ya contiene strings gracias al procesamiento en Streamlit
    placeholders = ', '.join(['%s'] * len(serials))
    query = f"SELECT serial, direccion FROM {DB_TABLE} WHERE serial IN ({placeholders})"
    
    try:
        cursor = cnx.cursor()
        cursor.execute(query, tuple(serials))
        results = cursor.fetchall()
        cursor.close()
        
        df = pd.DataFrame(results, columns=['serial', 'direccion_DB'])
        
        # *** AJUSTE CLAVE 1: Asegurar que la columna 'serial' de la DB sea STRING ***
        df['serial'] = df['serial'].astype(str)
        
        return df
        
    except Error as err:
        st.error(f"❌ Error al ejecutar la consulta en MySQL: {err}")
        return pd.DataFrame(columns=['serial', 'direccion_DB'])
    except Exception as e:
        st.error(f"❌ Error inesperado durante la consulta: {e}")
        return pd.DataFrame(columns=['serial', 'direccion_DB'])
    finally:
        if cnx and cnx.is_connected():
            cnx.close()


# --- Interfaz de la aplicación Streamlit ---


st.title("🗺️ Buscador de Direcciones por Serial (vía `db_conection`)")
st.markdown("Sube un archivo **Excel** con una columna llamada **'serial'** para buscar la dirección asociada en la tabla `paquetes`.")

uploaded_file = st.file_uploader("Elige un archivo Excel (.xlsx)", type=["xlsx"])

if uploaded_file:
    st.info("Archivo subido. Leyendo seriales...")
    try:
        # 1. Leer seriales del Excel
        df_serials_original = pd.read_excel(uploaded_file)
        
        # 2. Validar y preparar seriales
        col_match = [col for col in df_serials_original.columns if col.strip().lower() == 'serial']
        if not col_match:
            st.error("❌ Error: El archivo Excel debe contener una columna llamada 'serial'.")
            st.stop()
        
        df_serials_original.rename(columns={col_match[0]: 'serial'}, inplace=True)
        
        # *** AJUSTE CLAVE 2: Convertir la columna 'serial' del EXCEL a STRING antes del merge ***
        df_serials_original['serial'] = df_serials_original['serial'].astype(str) 

        # Obtener seriales únicos para la consulta
        serials_to_search = df_serials_original['serial'].unique().tolist()
        
        if not serials_to_search:
            st.warning("⚠️ Advertencia: El archivo no contiene seriales válidos para buscar.")
            st.stop()
            
        st.success(f"Se detectaron {len(serials_to_search)} seriales únicos.")

        # 3. Buscar direcciones en MySQL
        with st.spinner(f'Conectando y buscando {len(serials_to_search)} seriales en la DB...'):
            df_addresses = fetch_addresses_for_serials(serials_to_search)
            
        # 4. Combinar resultados: Ambos 'serial' ya son de tipo string, permitiendo el merge
        df_final = pd.merge(
            df_serials_original, 
            df_addresses, 
            on='serial', 
            how='left'
        )
        
        # ... (Resto del código de visualización y descarga) ...
        df_final['direccion_DB'] = df_final['direccion_DB'].fillna('SERIAL NO ENCONTRADO EN DB')

        st.success("✅ Búsqueda completada. Resultados:")

        display_cols = ['serial', 'direccion_DB'] + [col for col in df_final.columns if col not in ['serial', 'direccion_DB']]
        st.dataframe(df_final[display_cols])

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_final.to_excel(writer, index=False, sheet_name='Direcciones_Encontradas')
            
        st.download_button(
            label="📥 Descargar archivo Excel con direcciones",
            data=output.getvalue(),
            file_name="seriales_con_direcciones_buscadas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    except Exception as e:
        # Se mantiene el manejo de error general para cualquier otro fallo
        st.error(f"❌ Ocurrió un error grave durante el procesamiento: {e}")
        st.warning("Asegúrate de que el archivo es un formato Excel (.xlsx) válido.")
else:
    st.info("Esperando que cargues un archivo Excel.")