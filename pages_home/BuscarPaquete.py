import streamlit as st
import pandas as pd
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from utils.db_connection import conectar_bd

CSV_HISTO = "/mnt/c/Users/mcomb/Desktop/Carvajal/python/basesHisto.csv"

COLS_DISPLAY = ["Guia / Serial", "Nombre", "Teléfono", "Dirección", "Fecha", "Ciudad", "Cód. Mensajero", "Estado", "Fuente"]


@st.cache_data(show_spinner=False, ttl=3600)
def cargar_histo() -> pd.DataFrame:
    if not os.path.exists(CSV_HISTO):
        return pd.DataFrame()
    df = pd.read_csv(CSV_HISTO, low_memory=False, encoding="latin1", dtype=str)
    df.columns = df.columns.str.strip()
    for col in ["serial", "nombred", "dirdes1", "ciudad1", "f_emi", "cod_sec", "cod_men", "estado"]:
        if col not in df.columns:
            df[col] = ""
    df = df.fillna("")
    return df


def normalizar_histo(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte columnas del CSV al formato de display unificado."""
    out = pd.DataFrame()
    out["Guia / Serial"] = df["serial"].str.strip()
    out["Nombre"]        = df["nombred"].str.strip().str.title()
    out["Teléfono"]      = "—"
    out["Dirección"]     = df["dirdes1"].str.strip()
    out["Fecha"]         = pd.to_datetime(df["f_emi"], errors="coerce").dt.strftime("%d/%m/%Y")
    out["Ciudad"]           = df["ciudad1"].str.strip().str.title()
    out["Cód. Mensajero"]   = df["cod_men"].str.strip()
    out["Estado"]           = df["estado"].str.strip()
    out["Fuente"]           = "📁 Histórico"
    return out


def normalizar_imile(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte columnas de la tabla paquetes al formato de display unificado."""
    out = pd.DataFrame()
    out["Guia / Serial"] = df["serial"].astype(str)
    out["Nombre"]        = df["nombre"]
    out["Teléfono"]      = df["telefono"].astype(str)
    out["Dirección"]     = df["direccion"]
    out["Fecha"]         = pd.to_datetime(df["f_emi"], errors="coerce").dt.strftime("%d/%m/%Y")
    out["Ciudad"]           = df.get("ciudad", pd.Series(["—"] * len(df)))
    out["Cód. Mensajero"]   = "—"
    out["Estado"]           = "—"
    out["Fuente"]           = "🗄️ iMile DB"
    return out


# ── UI ────────────────────────────────────────────────────────────────────────

st.title("🔍 Buscador de Paquetes")
st.caption("Busca simultáneamente en la base de datos iMile y en el histórico CSV.")

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

termino = termino.strip()
resultados_partes = []

# ── Búsqueda en iMile DB ──────────────────────────────────────────────────────
conn = conectar_bd()
if conn:
    try:
        cursor = conn.cursor(dictionary=True)

        if modo == "🔢 Número de Guia / Serial":
            cursor.execute("""
                SELECT serial, nombre, telefono, direccion, f_emi, sector, ruta
                FROM paquetes WHERE serial LIKE %s ORDER BY f_emi DESC LIMIT 100
            """, (f"%{termino}%",))

        elif modo == "👤 Nombre del Cliente":
            palabras = [p for p in termino.split() if p]
            if palabras:
                cond   = " AND ".join(["LOWER(nombre) LIKE %s"] * len(palabras))
                params = tuple(f"%{p.lower()}%" for p in palabras)
                cursor.execute(f"""
                    SELECT serial, nombre, telefono, direccion, f_emi, sector, ruta
                    FROM paquetes WHERE {cond} ORDER BY f_emi DESC LIMIT 100
                """, params)
            else:
                cursor.close()
                conn.close()
                conn = None

        else:  # Teléfono
            cursor.execute("""
                SELECT serial, nombre, telefono, direccion, f_emi, sector, ruta
                FROM paquetes WHERE telefono LIKE %s ORDER BY f_emi DESC LIMIT 100
            """, (f"%{termino}%",))

        if conn:
            rows = cursor.fetchall()
            cursor.close()
            if rows:
                resultados_partes.append(normalizar_imile(pd.DataFrame(rows)))
    except Exception as e:
        st.warning(f"Error en iMile DB: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()
else:
    st.warning("No se pudo conectar a iMile DB.")

# ── Búsqueda en CSV histórico ─────────────────────────────────────────────────
if modo != "📞 Teléfono":
    with st.spinner("Buscando en histórico..."):
        df_histo = cargar_histo()

    if df_histo.empty:
        st.warning(f"Histórico no encontrado: `{CSV_HISTO}`")
    else:
        if modo == "🔢 Número de Guia / Serial":
            mask = df_histo["serial"].str.contains(termino, na=False, case=False)
        else:  # Nombre
            palabras = [p for p in termino.split() if p]
            mask = pd.Series([True] * len(df_histo), index=df_histo.index)
            for p in palabras:
                mask &= df_histo["nombred"].str.contains(p, na=False, case=False)

        sub = df_histo[mask].head(200)
        if not sub.empty:
            resultados_partes.append(normalizar_histo(sub))
else:
    st.info("La búsqueda por teléfono solo aplica a la base iMile (el histórico CSV no contiene este campo).")

# ── Mostrar resultados ────────────────────────────────────────────────────────
if not resultados_partes:
    st.info("No se encontraron resultados.")
    st.stop()

df_final = pd.concat(resultados_partes, ignore_index=True)[COLS_DISPLAY]
df_final = df_final.drop_duplicates(subset=["Guia / Serial"])

st.success(f"{len(df_final)} resultado(s) — iMile DB: {sum(r['Fuente'].str.startswith('🗄️').sum() for r in resultados_partes if not r.empty)} · Histórico: {sum(r['Fuente'].str.startswith('📁').sum() for r in resultados_partes if not r.empty)}")

st.dataframe(df_final, use_container_width=True, hide_index=True)

# ── Detalle cuando hay un único resultado ─────────────────────────────────────
if len(df_final) == 1:
    row = df_final.iloc[0]
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Guia / Serial:** `{row['Guia / Serial']}`")
        st.markdown(f"**Nombre:** {row['Nombre']}")
        st.markdown(f"**Teléfono:** {row['Teléfono']}")
    with col2:
        st.markdown(f"**Dirección:** {row['Dirección']}")
        st.markdown(f"**Fecha:** {row['Fecha']}")
        st.markdown(f"**Ciudad:** {row['Ciudad']}")
        st.markdown(f"**Cód. Mensajero:** {row['Cód. Mensajero']}")
        st.markdown(f"**Estado:** {row['Estado']}")
        st.markdown(f"**Fuente:** {row['Fuente']}")
