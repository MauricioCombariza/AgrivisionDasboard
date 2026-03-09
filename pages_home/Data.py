import streamlit as st
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv
import os

# Cargar variables de entorno
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Crear cliente de Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("🌍 Subir paquetes a la nube")

uploaded_file = st.file_uploader("Sube un archivo CSV con las columnas: serial, direccion, sector, ruta", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    st.write("Vista previa del archivo:")
    st.dataframe(df)

    if st.button("🚀 Insertar en la nube"):
        if all(col in df.columns for col in ["serial", "direccion", "sector", "ruta", "nombre", "telefono"]):
            insertados = 0
            duplicados = 0
            errores = 0

            for _, row in df.iterrows():
                serial = row["serial"]

                # Verificar si el serial ya existe
                check_response = supabase.table("paquetes").select("serial_number").eq("serial_number", serial).execute()
                if check_response.data:
                    duplicados += 1
                    st.warning(f"⚠️ Serial duplicado: {serial}")
                    continue

                # Intentar insertar
                data = {
                    "serial_number": serial,
                    "direccion_origen": row["direccion"],
                    "sector": row["sector"],
                    "ruta": row["ruta"],
                    "nombre": row["nombre"],
                    "telefono": row["telefono"]
                }

                try:
                    insert_response = supabase.table("paquetes").insert(data).execute()
                    if insert_response.data:
                        insertados += 1
                        st.success(f"✅ Insertado: {serial}")
                    else:
                        errores += 1
                        st.error(f"❌ Error al insertar: {serial}")
                except Exception as e:
                    errores += 1
                    st.error(f"❌ Excepción al insertar: {serial}")
                    st.text(str(e))

            st.info(f"✅ {insertados} insertados, ⚠️ {duplicados} duplicados, ❌ {errores} errores.")
        else:
            st.error("❌ El archivo debe tener las columnas: serial, direccion, sector, ruta.")
else:
    st.info("Por favor, sube un archivo CSV para comenzar.")

