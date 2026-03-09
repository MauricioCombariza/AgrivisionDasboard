import streamlit as st
import pandas as pd
import requests
from pydantic import BaseModel, validator
from typing import Optional
import os


# Título de la aplicación
st.write("# Análisis de reclamos")

def cargar_datos(archivo_csv):
    """Carga y selecciona columnas del archivo CSV."""
    df = pd.read_csv(archivo_csv, low_memory=False)
    columnas_seleccionadas = [
        'no_entidad', 'servicio', 'nombred', 'dirdes1', 'serial', 
        'ciudad1', 'cod_sec', 'retorno', 'ret_esc', 'orden', 
        'planilla', 'f_emi', 'f_lleva', 'cod_men', 'dir_num', 
        'comentario', 'cliente'
    ]
    # Convertir la columna 'serial' a string
    df['serial'] = df['serial'].astype(str)

    return df[columnas_seleccionadas]

serial = st.text_input("Introduce el número de serial:")

# Subir archivo CSV
uploaded_file = st.file_uploader("Sube tu archivo CSV", type="csv")

if uploaded_file is not None:
    df = cargar_datos(uploaded_file)

    if serial:
        # Filtrar el DataFrame por el serial ingresado
        fila_encontrada = df[df['serial'] == serial]
        
        # Mostrar la fila si se encontró alguna coincidencia
        if not fila_encontrada.empty:
            st.write("Datos de la fila encontrada:")
            st.write(fila_encontrada)
        else:
            st.write("No se encontró ninguna fila con ese número de serial.")

        # Solo procesamos si el serial tiene la longitud adecuada

        if len(serial) == 16:
            inicio = serial[:8]
            medio = serial[8:13]
            final = serial[10:16]
        elif len(serial) == 13:
            inicio = serial[:8]
            medio = serial[8:13]
            final = serial[10:13]
        else:
            inicio = serial[:4]
            medio = serial[4:7]
            final = serial[4:10]

        # Construimos la URL de la imagen
        image_url = f"https://www.gruposervilla.com/guias/{inicio}/{medio}/{final}.png"

        # Mostrar la URL y la imagen
        st.write("URL de la imagen:", image_url)
        st.image(image_url, caption="Imagen generada a partir del serial")
    else:
        st.info("Por favor, introduce un número de serial para generar la imagen.")


