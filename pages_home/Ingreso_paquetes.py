import streamlit as st
import pandas as pd
import numpy as np
import sys
import os
import io

# Configurar sys.path para importar utils
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Imports propios
from utils.db_connection import conectar_bd, insertar_paquetes, obtener_paquetes
from utils.direcciones import extraer_componentes_direccion
from utils.sectorization import sectorizar_inicial, sectorizar_con_correcciones, actualizar_bd_con_sectores
from utils.export import to_csv, to_excel

# Inicializar estados de sesión
if 'df_final' not in st.session_state:
    st.session_state.df_final = None
if 'direcciones_sin_sector' not in st.session_state:
    st.session_state.direcciones_sin_sector = pd.DataFrame()
if 'direcciones_corregidas' not in st.session_state:
    st.session_state.direcciones_corregidas = {}

# Función principal de la aplicación
def main():
    st.title("Sistema de Gestión de Paquetes")
    
    # Crear pestañas
    tab1, tab2 = st.tabs(["Subir bases", "Procesar y Exportar"])
    
    with tab1:
        mostrar_subida_bases()
        
    with tab2:
        mostrar_procesamiento_exportacion()

def mostrar_subida_bases():
    """
    Muestra la interfaz para subir archivos Excel y cargar datos a la base de datos.
    """
    st.title("Subir bases")

    uploaded_file = st.file_uploader("Elige un archivo Excel", type="xlsx")

    if uploaded_file is not None:
        try:
            df_subida = pd.read_excel(uploaded_file, engine='openpyxl')
            st.success("Archivo cargado correctamente")
            st.dataframe(df_subida)  # Mostrar el DataFrame cargado
        except Exception as e:
            st.error(f"Error al leer el archivo Excel: {e}")
            st.stop()

        fecha_entrega = st.date_input("Selecciona la fecha de entrega (f_emi)")

        if st.button("Subir datos a MySQL"):
            if df_subida.empty:
                st.warning("El archivo Excel está vacío. No hay datos para insertar.")
            else:
                registros_insertados, registros_fallidos = insertar_paquetes(df_subida, fecha_entrega)
                
                if registros_insertados > 0:
                    st.success(f"Se insertaron {registros_insertados} registros correctamente.")
                if registros_fallidos > 0:
                    st.warning(f"Hubo {registros_fallidos} registros que no se pudieron insertar.")

def mostrar_procesamiento_exportacion():
    """
    Muestra la interfaz para procesar direcciones, sectorizar y exportar datos.
    """
    st.title("📋 Procesar y Exportar Datos")

    # Botón para iniciar el proceso de sectorización
    if st.button("Iniciar proceso de sectorización"):
        with st.spinner("Obteniendo datos de MySQL y procesando direcciones..."):
            # Obtener datos de paquetes
            df_paquetes = obtener_paquetes()
            
            if df_paquetes.empty:
                st.error("No se pudieron obtener datos de la base de datos.")
                return
            
            # Sectorizar y actualizar la base de datos
            df_procesado, df_sin_sector = sectorizar_inicial(df_paquetes)
            registros_actualizados = actualizar_bd_con_sectores(df_procesado)
            
            st.success(f"Se actualizaron {registros_actualizados} registros en la base de datos.")
            
            # Guardar en el estado de sesión
            st.session_state.df_final = df_procesado
            st.session_state.direcciones_sin_sector = df_sin_sector

        # Mostrar direcciones no sectorizadas para corrección
        if not df_sin_sector.empty:
            st.warning("Las siguientes direcciones no pudieron ser procesadas. Por favor, corrígelas:")
            edited = st.data_editor(df_sin_sector, num_rows="dynamic", key="editor")
            
            # Guardar las correcciones en el estado de sesión
            st.session_state.direcciones_corregidas = {
                row['serial']: row['dirajustada'] for _, row in edited.iterrows()
            }
        else:
            st.success("Todas las direcciones fueron procesadas y sectorizadas.")
            st.session_state.direcciones_sin_sector = pd.DataFrame()  # Resetear

    # Botón para reintentar con correcciones
    if st.button("Reintentar con correcciones", key="btn_reintentar"):
        if not st.session_state.direcciones_corregidas:
            st.warning("No hay correcciones para procesar.")
            return
            
        with st.spinner("Reintentando procesamiento con las correcciones..."):
            # Obtener el dataframe original
            df_paquetes = obtener_paquetes()
            
            # Procesar con las correcciones
            df_actualizado, df_sin_sector_actualizado = sectorizar_con_correcciones(
                df_paquetes, 
                st.session_state.direcciones_corregidas
            )
            
            # Actualizar la base de datos
            registros_actualizados = actualizar_bd_con_sectores(df_actualizado)
            
            if registros_actualizados > 0:
                st.success(f"Se actualizaron {registros_actualizados} registros en la base de datos.")
            
            st.session_state.df_final = df_actualizado
            st.session_state.direcciones_sin_sector = df_sin_sector_actualizado

        # Mostrar resultado del reintento
        if df_sin_sector_actualizado.empty:
            st.success("Todas las direcciones fueron procesadas y sectorizadas exitosamente.")
            st.success("Los sectores se subieron de forma exitosa!!")
            st.session_state.direcciones_sin_sector = pd.DataFrame()  # Resetear
        else:
            st.warning(f"Quedan {len(df_sin_sector_actualizado)} direcciones sin sector:")
            st.dataframe(df_sin_sector_actualizado)

    # Añadir opciones de exportación
    if st.session_state.df_final is not None and not st.session_state.df_final.empty:
        st.subheader("Exportar datos")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Exportar a CSV"):
                csv = to_csv(st.session_state.df_final)
                st.download_button(
                    label="Descargar CSV",
                    data=csv,
                    file_name="paquetes_sectorizados.csv",
                    mime="text/csv"
                )
                
        with col2:
            if st.button("Exportar a Excel"):
                excel = to_excel(st.session_state.df_final)
                st.download_button(
                    label="Descargar Excel",
                    data=excel,
                    file_name="paquetes_sectorizados.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

if __name__ == "__main__":
    main()