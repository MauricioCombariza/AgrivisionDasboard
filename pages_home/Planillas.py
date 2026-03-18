import pandas as pd
import streamlit as st
from datetime import datetime
import io
from openpyxl import Workbook

# Título de la página
st.title("Pendientes - Filtrado de Datos")

# Sección de entradas
st.header("Parámetros de Filtro")

# Entrada para la orden inicial y final
planilla = st.text_input("Selecciona la Orden inicial:")

# Cargar archivo CSV
uploaded_file = st.file_uploader("Sube tu archivo CSV", type="csv")

if uploaded_file is not None:
    # Leer archivo CSV
    planilla_num = pd.to_numeric(planilla, errors='coerce')
            
    df = pd.read_csv(uploaded_file, low_memory=False)
    df['planilla'] = pd.to_numeric(df['planilla'], errors='coerce')
    st.write("Datos cargados exitosamente. Vista previa del archivo:")
    st.dataframe(df.head())  # Mostrar una vista previa del archivo cargado

    if planilla:
        try:
            # Convertir la columna 'cod_men' del DataFrame a numérico
            df['cod_men'] = pd.to_numeric(df['cod_men'], errors='coerce')
                        
            # Filtrar el DataFrame donde 'cod_men' coincida con cualquiera de los códigos ingresados
            df_filtrado = df[
                            (df['planilla'] == planilla_num) 
                ]
            
            df_filtrado = df_filtrado[['serial', 'orden', 'f_emi', 'cod_men','cod_sec', 'cliente', 'retorno', 'ret_esc', 'comentario', 'nombred', 'dirdes1', 'planilla']]
            
            # Mostrar los resultados
            if not df_filtrado.empty:
                
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    df_filtrado.to_excel(writer, index=False, sheet_name="Hoja1")
                st.download_button("📥 Descargar Excel", buf.getvalue(), f"planilla_{planilla_num}.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                
            else:
                st.write(f"No se encontraron coincidencias para la planilla: {planilla_num}")
        
        except ValueError:
            st.error("El número de plánilla ingresado no es valido.")
    else:
        st.write("Por favor, ingresa un numero de planilla")
    
else:
    st.info("Por favor, sube un archivo CSV para comenzar.")
