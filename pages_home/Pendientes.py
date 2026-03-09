from pydantic import BaseModel, Field, ValidationError, conint
import streamlit as st
import pandas as pd
import requests


# Título de la aplicación
st.write("# Pendientes")


class FilterInputs(BaseModel):
    """Modelo Pydantic para validar los filtros de entrada."""
    order_start: conint(ge=1) = Field(..., description="Orden inicial debe ser un entero positivo.")
    order_end: conint(ge=1) = Field(..., description="Orden final debe ser un entero positivo.")
    cliente_seleccionado: str

def cargar_datos(archivo_csv):
    """Carga y selecciona columnas del archivo CSV."""
    df = pd.read_csv(archivo_csv, low_memory=False)
    columnas_seleccionadas = [
        'no_entidad', 'servicio', 'nombred', 'dirdes1', 'serial', 
        'ciudad1', 'cod_sec', 'retorno', 'ret_esc', 'orden', 
        'planilla', 'f_emi', 'f_lleva', 'cod_men', 'dir_num', 
        'comentario', 'cliente'
    ]
    return df[columnas_seleccionadas]

def filtrar_datos(df, inputs):
    """Filtra el DataFrame según los criterios de orden y cliente seleccionados."""
    return df[
        (df['orden'] >= inputs.order_start) & 
        (df['orden'] <= inputs.order_end) & 
        (df['cliente'] == inputs.cliente_seleccionado) &
        ~(df['ret_esc'] == "E") & 
        ~(df['retorno'].isin(["D", "f"]))
    ]

def mostrar_resultados(df_filtrado, cliente):
    """Muestra los resultados filtrados y el total de pendientes por cliente."""
    conteo_por_cod_men = (
        df_filtrado.groupby('cod_men')['serial']
        .count()
        .reset_index(name='conteo')
        .sort_values(by='conteo', ascending=False)
    )
    total_filas = df_filtrado.shape[0]

    st.write("Pendientes por mensajero:")
    st.dataframe(conteo_por_cod_men)
    st.write(f"El total de pendientes de {cliente} es de {total_filas}")

# Subir archivo CSV
uploaded_file = st.file_uploader("Sube tu archivo CSV", type="csv")

if uploaded_file is not None:
    df = cargar_datos(uploaded_file)
    clientes_unicos = df['cliente'].unique()

    # Inputs de usuario para los filtros
    try:
        inputs = FilterInputs(
            order_start=st.number_input("Orden inicial:", min_value=1, step=1),
            order_end=st.number_input("Orden final:", min_value=1, step=1),
            cliente_seleccionado=st.selectbox('Selecciona un cliente', clientes_unicos)
        )

        # Filtrar y mostrar resultados
        df_filtrado = filtrar_datos(df, inputs)
        mostrar_resultados(df_filtrado, inputs.cliente_seleccionado)

    except ValidationError as e:
        st.error("Error en la validación de los datos de entrada.")
        st.write(e.json())
