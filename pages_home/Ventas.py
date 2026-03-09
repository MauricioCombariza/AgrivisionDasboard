import pandas as pd
import streamlit as st
from pydantic import BaseModel, Field, ValidationError
import matplotlib.pyplot as plt
import requests


# Título de la página
st.title("Ventas - Análisis de Ventas Mensuales por Cliente")

class DashboardData(BaseModel):
    """Modelo Pydantic para validar y procesar los datos del dashboard."""
    f_emi: str
    serial: str
    cliente: str

def cargar_y_procesar_datos(archivo_csv):
    """Carga y procesa el archivo CSV, convierte f_emi en fecha y crea mes_año."""
    df = pd.read_csv(archivo_csv, low_memory=False)
    
    # Validación de datos usando Pydantic
    datos_validados = []
    for _, row in df.iterrows():
        try:
            dato = DashboardData(
                f_emi=row['f_emi'],
                serial=row['serial'],
                cliente=row['cliente']
            )
            datos_validados.append(dato.dict())
        except ValidationError as e:
            st.error(f"Error en la validación de datos: {e}")
    
    # Convertir a DataFrame
    df_validado = pd.DataFrame(datos_validados)
    
    # Convertir f_emi a fecha
    df_validado['f_emi'] = pd.to_datetime(df_validado['f_emi'], errors='coerce')
    
    # Crear campo mes_año
    df_validado['mes_año'] = df_validado['f_emi'].dt.to_period('M')
    
    return df_validado

def agrupar_por_mes_cliente(df):
    """Agrupa el DataFrame por mes_año y cliente, y cuenta el campo serial."""
    conteo_ventas = (
        df.groupby(['mes_año', 'cliente'])
        .agg(ventas=('serial', 'count'))
        .reset_index()
    )
    return conteo_ventas

def graficar_ventas_por_cliente(conteo_ventas):
    """Genera una gráfica de barras de las ventas por cliente y mes."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for cliente in conteo_ventas['cliente'].unique():
        cliente_df = conteo_ventas[conteo_ventas['cliente'] == cliente]
        ax.bar(cliente_df['mes_año'].astype(str), cliente_df['ventas'], label=cliente)
    
    ax.set_xlabel("Mes-Año")
    ax.set_ylabel("Cantidad de Ventas")
    ax.set_title("Ventas Mensuales por Cliente")
    ax.legend(title="Cliente", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.xticks(rotation=45)
    st.pyplot(fig)

# Cargar archivo CSV
uploaded_file = st.file_uploader("Sube tu archivo dashboard.csv", type="csv")

if uploaded_file is not None:
    # Cargar y procesar datos
    df_validado = cargar_y_procesar_datos(uploaded_file)
    
    # Agrupar por mes y cliente
    conteo_ventas = agrupar_por_mes_cliente(df_validado)
    
    # Mostrar la tabla de conteo de ventas
    st.write("Tabla de Ventas Mensuales por Cliente:")
    st.dataframe(conteo_ventas)
    
    # Mostrar gráfica de barras
    graficar_ventas_por_cliente(conteo_ventas)
