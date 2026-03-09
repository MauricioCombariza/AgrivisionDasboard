import streamlit as st
import pandas as pd
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from utils.db_connection import conectar_bd

st.title("🔍 Buscador de Paquetes")

modo = st.radio(
    "Buscar por",
    ["🔢 Número de Guia / Serial", "👤 Nombre del Cliente", "📞 Teléfono"],
    horizontal=True,
    key="buscar_modo"
)

termino = st.text_input(
    "Ingresa el término de búsqueda",
    key="buscar_termino",
    placeholder={
        "🔢 Número de Guia / Serial": "Ej: 75213001234",
        "👤 Nombre del Cliente":      "Ej: garcia maria  /  maria garcia  /  garcia",
        "📞 Teléfono":                "Ej: 3001234567",
    }[modo]
)

if not termino or not termino.strip():
    st.stop()

conn = conectar_bd()
if not conn:
    st.stop()

try:
    cursor = conn.cursor(dictionary=True)
    resultados = []

    if modo == "🔢 Número de Guia / Serial":
        cursor.execute("""
            SELECT serial, nombre, telefono, direccion, f_emi, sector, ruta
            FROM paquetes
            WHERE serial LIKE %s
            ORDER BY f_emi DESC
            LIMIT 100
        """, (f"%{termino.strip()}%",))
        resultados = cursor.fetchall()

    elif modo == "👤 Nombre del Cliente":
        palabras = [p for p in termino.strip().split() if p]
        if palabras:
            condiciones = " AND ".join(["LOWER(nombre) LIKE %s"] * len(palabras))
            params = tuple(f"%{p.lower()}%" for p in palabras)
            cursor.execute(f"""
                SELECT serial, nombre, telefono, direccion, f_emi, sector, ruta
                FROM paquetes
                WHERE {condiciones}
                ORDER BY f_emi DESC
                LIMIT 100
            """, params)
            resultados = cursor.fetchall()

    else:  # Teléfono
        cursor.execute("""
            SELECT serial, nombre, telefono, direccion, f_emi, sector, ruta
            FROM paquetes
            WHERE telefono LIKE %s
            ORDER BY f_emi DESC
            LIMIT 100
        """, (f"%{termino.strip()}%",))
        resultados = cursor.fetchall()

    cursor.close()

    if not resultados:
        st.info("No se encontraron resultados para la búsqueda.")
        st.stop()

    df = pd.DataFrame(resultados)
    df['f_emi'] = pd.to_datetime(df['f_emi'], errors='coerce').dt.strftime('%d/%m/%Y')
    df = df.rename(columns={
        'serial':    'Guia / Serial',
        'nombre':    'Nombre',
        'telefono':  'Teléfono',
        'direccion': 'Dirección',
        'f_emi':     'Fecha',
        'sector':    'Sector',
        'ruta':      'Ruta',
    })

    st.success(f"{len(df)} resultado(s) encontrado(s)")
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Detalle al hacer clic en una fila
    if len(df) == 1:
        row = df.iloc[0]
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Guia / Serial:** `{row['Guia / Serial']}`")
            st.markdown(f"**Nombre:** {row['Nombre']}")
            st.markdown(f"**Teléfono:** {row['Teléfono']}")
        with col2:
            st.markdown(f"**Dirección:** {row['Dirección']}")
            st.markdown(f"**Fecha:** {row['Fecha']}")
            if row.get('Sector'):
                st.markdown(f"**Sector:** {row['Sector']}")
            if row.get('Ruta'):
                st.markdown(f"**Ruta:** {row['Ruta']}")

except Exception as e:
    st.error(f"Error al buscar: {e}")
finally:
    if conn and conn.is_connected():
        conn.close()
