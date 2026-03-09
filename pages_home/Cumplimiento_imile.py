import streamlit as st
import pandas as pd
from io import BytesIO

# Título de la página
st.title("📊 Reporte de Cumplimiento Agrupado")

# Subir archivo Excel
archivo = st.file_uploader("Sube un archivo Excel", type=["xlsx", "xls"])

if archivo is not None:
    try:
        # Leer archivo desde Sheet1
        df = pd.read_excel(archivo, sheet_name="sheet1", header=0)

        # Normalizar nombres de columnas
        df.columns = df.columns.str.strip().str.lower()

        # Definir columnas necesarias
        col_escaneo = "última hora de escaneo".lower()
        col_recepcion = "tiempo de recepción".lower()

        if col_escaneo in df.columns and col_recepcion in df.columns:
            # Convertir a datetime
            df[col_escaneo] = pd.to_datetime(df[col_escaneo], errors="coerce")
            df[col_recepcion] = pd.to_datetime(df[col_recepcion], errors="coerce")

            # Crear columna Fecha (solo día/mes/año)
            df["Fecha"] = df[col_escaneo].dt.strftime("%d/%m/%Y")

            # Calcular diferencia en días
            df["dias"] = (df[col_escaneo] - df[col_recepcion]).dt.days

            # Crear columna Cumplimiento
            df["Cumplimiento"] = df["dias"].apply(lambda x: 1 if pd.notnull(x) and x < 4 else 0)

            # Agrupar por fecha
            resumen = df.groupby("Fecha").agg(
                suma_cumplimiento=("Cumplimiento", "sum"),
                conteo=("Cumplimiento", "count")
            ).reset_index()

            # Calcular % Diario
            resumen["% Diario"] = (resumen["suma_cumplimiento"] / resumen["conteo"]) * 100

            # Calcular % Acumulado
            resumen["% Acumulado"] = (
                resumen["suma_cumplimiento"].cumsum() / resumen["conteo"].cumsum()
            ) * 100

            # Mostrar en Streamlit
            st.write("### 📋 Resumen agrupado por fecha:")
            st.dataframe(resumen)

            # Guardar en Excel
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                resumen.to_excel(writer, index=False, sheet_name="Resumen")
            output.seek(0)

            # Botón de descarga
            st.download_button(
                label="⬇️ Descargar resumen en Excel",
                data=output,
                file_name="resumen_cumplimiento.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.error("⚠️ No se encontraron las columnas necesarias en Sheet1. "
                     "Verifica que existan: 'Última hora de escaneo' y 'tiempo de recepción'.")

    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")
