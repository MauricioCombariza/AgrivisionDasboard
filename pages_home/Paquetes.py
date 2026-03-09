import streamlit as st
import pandas as pd
import numpy as np
import sys
import os
import io

# ——— Configurar sys.path para importar utils ———
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# ——— Imports propios ———
from utils.zonificador import zonificador
from utils.compute import compute
from utils.nearest_neighbor_route import nearest_neighbor_route
from utils.insertar_punto_por_sector import insertar_punto_por_sector

# Funciones de exportación
def to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Hoja1')
    return output.getvalue()

# Título
st.title("📋 Exportador de Datos")

# Mostrar el DataFrame
st.markdown("### Vista previa del DataFrame:")

# Botones de descarga
st.markdown("### 📤 Exportar archivo")

# ——— Subida de archivo Excel ———
uploaded_file = st.file_uploader("Elige un archivo Excel", type="xlsx")

# ——— Inicializar df_base en sesión ———
if "df_base" not in st.session_state:
    st.session_state.df_base = None

# ——— Cargar o recuperar df_base ———
if uploaded_file is not None:
    st.session_state.df_base = pd.read_excel(uploaded_file, engine='openpyxl')
elif st.session_state.df_base is None:
    st.info("Sube un archivo Excel para comenzar.")
    st.stop()

# Trabajamos siempre sobre una copia de df_base
df_base = st.session_state.df_base.copy()
st.success("Archivo cargado correctamente")
st.dataframe(df_base)

# ——— Zona: aplicar zonificador dos veces ———
df_z = zonificador(df_base)
df_final = zonificador(df_z)

# ——— Convertir a numérico ———
df_final[['Calle', 'Carrera', 'placa']] = df_final[['Calle', 'Carrera', 'placa']].apply(
    pd.to_numeric, errors='coerce'
)

# ——— Cargar reglas de sectorización ———
df_sec = pd.read_csv("sectores.csv", encoding="latin1", sep=";", header=0)

# ——— Asignar sectores por rangos ———
df_final['Sector'] = 'Fuera de sector'
for _, row in df_sec.iterrows():
    mask = (
        (df_final['Calle']   >= row['Calle_min']) &
        (df_final['Calle']   <= row['Calle_max']) &
        (df_final['Carrera'] >= row['Carrera_min']) &
        (df_final['Carrera'] <= row['Carrera_max'])
    )
    df_final.loc[mask, 'Sector'] = row['Sector']

# ——— Mostrar y editar direcciones fuera de sector ———
df_fuera = df_final[df_final['Sector'] == 'Fuera de sector'][['Serial', 'Address']]

if not df_fuera.empty:
    st.warning("Corrige las direcciones sin sector:")
    edited = st.data_editor(df_fuera, num_rows="dynamic", key="editor")

    if st.button("Reintentar con correcciones", key="btn_reintentar"):
        with st.spinner("Procesando correcciones..."):
            # 1) Aplicar correcciones a df_base
            for _, row in edited.iterrows():
                idx = df_base[df_base['Serial'] == row['Serial']].index
                if not idx.empty:
                    df_base.loc[idx[0], 'Address'] = row['Address']
            st.session_state.df_base = df_base

            # 2) Re-zonificar y re-sectorizar
            df_z = zonificador(df_base)
            df_final = zonificador(df_z)
            df_final[['Calle', 'Carrera', 'placa']] = df_final[['Calle', 'Carrera', 'placa']].apply(
                pd.to_numeric, errors='coerce'
            )
            df_final['Sector'] = 'Fuera de sector'
            for _, row in df_sec.iterrows():
                mask = (
                    (df_final['Calle']   >= row['Calle_min']) &
                    (df_final['Calle']   <= row['Calle_max']) &
                    (df_final['Carrera'] >= row['Carrera_min']) &
                    (df_final['Carrera'] <= row['Carrera_max'])
                )
                df_final.loc[mask, 'Sector'] = row['Sector']

            # 3) Filtrar las corregidas que ahora CAEN en un sector
            corr = df_final[
                df_final['Serial'].isin(edited['Serial']) &
                (df_final['Sector'] != 'Fuera de sector')
            ][['Serial', 'Address', 'Sector']]

        # ---- fuera del spinner ----
        st.success("Procesamiento completado")

        st.subheader("🔄 DataFrame completo tras correcciones:")
        st.dataframe(df_final)

        if not corr.empty:
            st.subheader("✅ Direcciones corregidas con sector asignado:")
            st.dataframe(corr)
        else:
            st.error("⚠️ Ninguna dirección corregida cayó en un sector válido. Sigue corrigiendo.")

        # st.stop()

    # Esperamos correcciones
    # st.stop()

# ——— Si ya no quedan fuera, continuar pipeline ———
st.success("Todas las direcciones tienen sector.")
st.dataframe(df_final)

# ——— Ajuste de coordenadas ———
df_final['num_letras_cl'] = df_final['letras_cl'].apply(lambda x: compute(x, ""))
df_final['num_letras_cr'] = df_final['letras_cr'].apply(lambda x: compute(x, ""))
df_final['Calle']   += df_final['num_letras_cl'] / 10000
df_final['Carrera'] += df_final['num_letras_cr'] / 10000

# ——— Vecino más cercano por sector ———
ordenados_por_sector = []
for sector, grupo in df_final.groupby('Sector'):
    coords = grupo[['Calle', 'Carrera']].to_numpy(dtype=float)
    route = nearest_neighbor_route(coords)
    g = grupo.iloc[route].copy()
    g['orden'] = range(1, len(g) + 1)
    ordenados_por_sector.append(g)

df_order = pd.concat(ordenados_por_sector).reset_index(drop=True)
df_ajustado = insertar_punto_por_sector(df_order)

# ——— Preparar DataFrames de salida ———
df_intermedio = df_ajustado[['Serial', 'Nombre', 'Telefono', 'Address', 'Sector', 'orden']]
df_output = df_ajustado.rename(columns={
    'Serial': 'serial',
    'Address': 'direccion',
    'Sector': 'sector',
    'orden': 'ruta',
    'Nombre': 'nombre',
    'Telefono': 'telefono'
})[['serial', 'direccion', 'sector', 'ruta', 'nombre', 'telefono']]

st.write("Ruta final ajustada:")
st.dataframe(df_output)

st.button("Test")

# ——— Botones de exportación ———
if st.button("Guardar Excel en Descargas"):
    # Definir la ruta local para guardar el archivo Excel
    ruta_excel = "/mnt/c/Users/mcomb/Downloads/intermedio.xlsx"  # Asegúrate de que esta ruta exista en tu sistema
    try:
        # Guardar el archivo en la ruta
        df_intermedio.to_excel(ruta_excel, index=False)
        st.success(f"Archivo guardado en: {ruta_excel}")
    except Exception as e:
        st.error(f"Error al guardar el archivo: {e}")

# Botón para guardar como CSV
if st.button("Guardar CSV en Descargas"):
    # Definir la ruta local para guardar el archivo CSV
    ruta_csv = "/mnt/c/Users/mcomb/Desktop/Carvajal/python/sectorizado.csv"  # Asegúrate de que esta ruta exista en tu sistema
    try:
        # Guardar el archivo en la ruta
        df_output.to_csv(ruta_csv, index=False)
        st.success(f"Archivo guardado en: {ruta_csv}")
    except Exception as e:
        st.error(f"Error al guardar el archivo: {e}")    
