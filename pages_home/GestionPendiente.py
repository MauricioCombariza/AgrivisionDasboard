import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime
import io
from openpyxl import Workbook

# Título de la página
st.title("Pendientes - Filtrado de Datos")

# Sección de entradas
st.header("Parámetros de Filtro")

# Entrada para la orden inicial y final
orden_inicio = st.text_input("Selecciona la Orden inicial:")
orden_fin = st.text_input("Selecciona la Orden final:")

# Entrada para los códigos 'cod_men'
cod_men_input = st.text_input("Ingresa uno o varios códigos cod_men separados por coma:")

# Mostrar los códigos ingresados



# Cargar archivo CSV
uploaded_file = st.file_uploader("Sube tu archivo CSV", type="csv")

if uploaded_file is not None:
    # Leer archivo CSV
    if cod_men_input:
        cod_men_list = [int(c.strip()) for c in cod_men_input.split(",") if c.strip().isdigit()]
        if cod_men_list:
            st.write(f"Códigos ingresados: **{cod_men_list}**") 
            orden_inicio_num = pd.to_numeric(orden_inicio, errors='coerce')
            orden_fin_num = pd.to_numeric(orden_fin, errors='coerce')
                    
            df = pd.read_csv(uploaded_file, low_memory=False, encoding='latin1')
            df['orden'] = pd.to_numeric(df['orden'], errors='coerce')
            df['cod_men'] = pd.to_numeric(df['cod_men'], errors='coerce')
            filtro_cod_men = df['cod_men'].isin(cod_men_list)

            # Filtro 2: Excluir 'retorno' con valores 'D' o 'o'
            filtro_retorno = ~df['retorno'].isin(['D', 'o'])

            # Filtro 3: Filtrar por 'ret_esc' igual a 'i'
            # filtro_ret_esc = df['ret_esc'] == 'i'
            filtro_ret_esc = df['ret_esc'].isin(['i', 'p'])

            # Filtro 4: Filtrar por rango de 'orden' (solo si se ingresaron ambos valores)
            if pd.notna(orden_inicio_num) and pd.notna(orden_fin_num):
                filtro_orden = (df['orden'] >= orden_inicio_num) & (df['orden'] <= orden_fin_num)
                df_filtrado = df[filtro_cod_men & filtro_retorno & filtro_ret_esc & filtro_orden]
            else:
                df_filtrado = df[filtro_cod_men & filtro_retorno & filtro_ret_esc]
            df_filtrado = df_filtrado[['serial', 'orden','cod_men','f_emi', 'no_entidad', 'nombred', 'dirdes1','cod_sec', 'ciudad1', 'dpto1', 'retorno', 'ret_esc', 'motivo']]
            
            # Mostrar los resultados
            if not df_filtrado.empty:
                st.write("Resultados filtrados:", df_filtrado.head())
                st.write("Fecha inicial", df_filtrado['f_emi'].min())
                st.write("Fecha final", df_filtrado['f_emi'].max())
                st.write(f"Total de registros antes de eliminar duplicados: {len(df_filtrado)}")

                # Eliminar seriales duplicados
                total_antes = len(df_filtrado)
                df_filtrado = df_filtrado.drop_duplicates(subset=['serial'], keep='first')
                total_despues = len(df_filtrado)
                duplicados_eliminados = total_antes - total_despues

                if duplicados_eliminados > 0:
                    st.warning(f"Se eliminaron {duplicados_eliminados} seriales duplicados")
                st.write(f"**Total de pendientes mensajero (seriales únicos): {len(df_filtrado)}**")

                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    df_filtrado.to_excel(writer, index=False, sheet_name="Hoja1")
                nombre_xlsx = f"pendientes_códigos_{'_'.join(map(str, cod_men_list))}.xlsx"
                st.download_button("📥 Descargar Excel", buf.getvalue(), nombre_xlsx,
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.write("No hay resultados para los filtros especificados.")
                
        else:
            st.write(f"No se encontraron coincidencias para los códigos cod_men: {cod_men_input}")
    else:
        st.write("Por favor, ingresa uno o varios códigos cod_men separados por coma.") 

else:
    st.info("Por favor, sube un archivo CSV para comenzar.")

    