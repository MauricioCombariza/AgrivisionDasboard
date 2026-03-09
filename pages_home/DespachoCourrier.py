import streamlit as st
import pandas as pd
import os

# Título de la app
st.title("Filtrar Despachos por Mensajero y Fecha")

# Subida de archivo
uploaded_file = st.file_uploader("Sube tu archivo CSV", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    # Asegurar que f_emi esté en formato datetime, corrigiendo valores inválidos
    df['f_emi'] = pd.to_datetime(df['f_emi'], errors='coerce')

    # Rellenar fechas inválidas con la anterior válida
    df['f_emi'] = df['f_emi'].fillna(method='ffill')

    # Mostrar rango de fechas disponible
    fecha_min = df['f_emi'].min().date()
    fecha_max = df['f_emi'].max().date()

    st.markdown(f"Rango disponible en archivo: **{fecha_min}** a **{fecha_max}**")

    # Calendarios para seleccionar rango
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input("Fecha inicio", value=fecha_min, min_value=fecha_min, max_value=fecha_max)
    with col2:
        fecha_fin = st.date_input("Fecha fin", value=fecha_max, min_value=fecha_min, max_value=fecha_max)

    if fecha_inicio > fecha_fin:
        st.error("La fecha de inicio no puede ser mayor que la fecha de fin.")
    else:
        # Cuadro para ingresar número del mensajero
        cod_men_input = st.text_input("Ingresa el número del mensajero (cod_men):")

        if cod_men_input:
            try:
                cod_men = int(float(cod_men_input))  # Permitir si escriben 123.0

                # Asegurar que cod_men sea entero
                df['cod_men'] = pd.to_numeric(df['cod_men'], errors='coerce').fillna(0).astype(int)

                # Filtro por fecha y mensajero
                mascara = (
                    (df['cod_men'] == cod_men) &
                    (df['f_emi'].dt.date >= fecha_inicio) &
                    (df['f_emi'].dt.date <= fecha_fin)
                )
                df_filtrado = df[mascara]

                st.write(f"Se encontraron {len(df_filtrado)} registros.")
                st.dataframe(df_filtrado)

                # Guardar Excel
                if not df_filtrado.empty:
                    filename = f"despacho_{cod_men}_de{fecha_inicio}_a{fecha_fin}.xlsx"
                    path_descargas = "/mnt/c/Users/mcomb/Downloads"
                    ruta_final = os.path.join(path_descargas, filename)

                    df_filtrado.to_excel(ruta_final, index=False)
                    st.success(f"Archivo guardado correctamente en: {ruta_final}")
            except ValueError:
                st.error("El número del mensajero debe ser numérico.")
