import streamlit as st
import pandas as pd
import os

RUTA_DESTINO = "/mnt/c/Mauricio/Agrivision/Pagos lotes"

st.title("📄 Excel a CSV sin encabezado")
st.caption("Convierte un archivo Excel a CSV UTF-8 separado por ';', sin encabezado.")

uploaded_file = st.file_uploader("Selecciona el archivo Excel", type=["xlsx", "xls"])

if not uploaded_file:
    st.stop()

try:
    df = pd.read_excel(uploaded_file, engine="openpyxl")
except Exception as e:
    st.error(f"Error al leer el archivo: {e}")
    st.stop()

# Corregir texto con encoding roto (UTF-8 leído como latin1): CÃ©dula → Cédula
def fix_encoding(val):
    if isinstance(val, str):
        try:
            return val.encode("cp1252").decode("utf-8")
        except Exception:
            return val
    return val

df = df.apply(lambda col: col.map(fix_encoding))

st.success(f"Archivo cargado: {df.shape[0]} filas × {df.shape[1]} columnas")
st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()

nombre = st.text_input("Nombre del archivo (sin extensión)", placeholder="Ej: pagos_lote_enero")

if st.button("💾 Guardar CSV", type="primary", disabled=not nombre.strip()):
    nombre_limpio = nombre.strip()
    if not nombre_limpio.endswith(".csv"):
        nombre_limpio += ".csv"

    os.makedirs(RUTA_DESTINO, exist_ok=True)
    ruta_final = os.path.join(RUTA_DESTINO, nombre_limpio)

    try:
        df.to_csv(ruta_final, index=False, header=False, sep=";", encoding="utf-8-sig")
        st.success(f"✅ Guardado en: {ruta_final}")
    except Exception as e:
        st.error(f"Error al guardar: {e}")
