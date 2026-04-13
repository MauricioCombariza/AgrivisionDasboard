"""
Ingreso_paquetes_web.py
=======================
Versión web de Ingreso de Paquetes.  Sube el despacho diario directamente
a la base imile en la nube (VPS), sin pasar por el local.

Tabs:
  1. Subir despacho  → carga Excel y guarda en imile cloud
  2. Verificar sync  → compara registros cloud vs lo que se esperaría por fecha
"""

import os
from datetime import date, timedelta
from pathlib import Path

import mysql.connector
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# ── Variables de entorno ───────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

# ── Conexión BD imile cloud ────────────────────────────────────────────────────
def _conectar_cloud():
    """
    Conecta a imile en el servidor cloud (mismo servidor donde corre la app).
    Usa DB_HOST_IMILE para no colisionar con otras variables de entorno.
    """
    try:
        return mysql.connector.connect(
            host=os.environ.get("DB_HOST_IMILE", "127.0.0.1"),
            port=int(os.environ.get("DB_PORT_IMILE", "3306")),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database="imile",
            connect_timeout=10,
        )
    except Exception as exc:
        st.error(f"Error conectando a BD imile cloud: {exc}")
        return None


# ── Mapeo de columnas del Excel fuente ────────────────────────────────────────
COL_MAP = {
    "Waybill number":   "serial",
    "Recipient's name": "nombre",
    "Customer phone":   "telefono",
    "Address2":         "direccion",
}

# ── Guardar en BD cloud ────────────────────────────────────────────────────────
def _guardar_cloud(df: pd.DataFrame) -> tuple[int, int]:
    """
    REPLACE INTO imile.paquetes en la nube.
    df debe tener: serial, nombre, telefono, direccion, f_emi.
    Retorna (ok, fallidos).
    """
    conn = _conectar_cloud()
    if conn is None:
        return 0, len(df)

    sql = """
        REPLACE INTO paquetes (serial, f_emi, nombre, telefono, direccion)
        VALUES (%s, %s, %s, %s, %s)
    """
    ok = fail = 0
    try:
        cur = conn.cursor()
        for _, row in df.iterrows():
            try:
                cur.execute(sql, (
                    str(row["serial"]),
                    str(row["f_emi"]),
                    str(row.get("nombre", "")),
                    str(row.get("telefono", "")),
                    str(row.get("direccion", "")),
                ))
                ok += 1
            except Exception:
                fail += 1
        conn.commit()
        cur.close()
    finally:
        if conn.is_connected():
            conn.close()
    return ok, fail


# ── Consultar resumen cloud por fecha ─────────────────────────────────────────
def _resumen_cloud(fecha_desde: date, fecha_hasta: date) -> pd.DataFrame:
    """Devuelve conteo de paquetes en cloud agrupado por f_emi en el rango dado."""
    conn = _conectar_cloud()
    if conn is None:
        return pd.DataFrame()

    sql = """
        SELECT f_emi, COUNT(*) AS total
        FROM paquetes
        WHERE f_emi BETWEEN %s AND %s
        GROUP BY f_emi
        ORDER BY f_emi DESC
    """
    try:
        df = pd.read_sql(sql, conn, params=(
            fecha_desde.strftime("%Y-%m-%d"),
            fecha_hasta.strftime("%Y-%m-%d"),
        ))
    except Exception as exc:
        st.error(f"Error al consultar cloud: {exc}")
        df = pd.DataFrame()
    finally:
        if conn.is_connected():
            conn.close()
    return df


# ── UI ────────────────────────────────────────────────────────────────────────
st.title("Ingreso de Paquetes — Nube")

tab_subir, tab_sync = st.tabs(["☁️ Subir despacho", "🔄 Verificar sync"])

# ── TAB 1: Subir despacho ─────────────────────────────────────────────────────
with tab_subir:
    st.subheader("Subir despacho diario a la nube")

    uploaded = st.file_uploader("Archivo Excel de despacho iMile", type="xlsx")
    fecha_emi = st.date_input("Fecha de emisión (f_emi)", value=date.today())

    if uploaded is not None:
        try:
            df_raw = pd.read_excel(uploaded, engine="openpyxl")
        except Exception as e:
            st.error(f"Error al leer Excel: {e}")
            st.stop()

        st.caption(f"{len(df_raw)} filas leídas")
        st.dataframe(df_raw.head(5), use_container_width=True)

        # Validar columnas requeridas
        faltantes = [c for c in COL_MAP if c not in df_raw.columns]
        if faltantes:
            st.error("Columnas requeridas no encontradas:")
            for col in faltantes:
                st.markdown(f"- `{col}`")
            st.info("Columnas disponibles: " + ", ".join(f"`{c}`" for c in df_raw.columns))
        else:
            df = df_raw[list(COL_MAP)].rename(columns=COL_MAP).copy()
            df["serial"] = df["serial"].astype(str)
            df["f_emi"] = fecha_emi.strftime("%Y-%m-%d")

            st.success(f"**{len(df)} registros** listos para subir a la nube.")

            if st.button("☁️ Guardar en imile cloud", type="primary"):
                with st.spinner("Subiendo a la nube…"):
                    ok, fail = _guardar_cloud(df)
                if fail == 0:
                    st.success(f"✅ {ok} registros guardados en imile cloud.")
                else:
                    st.warning(f"Guardados: {ok} | Fallidos: {fail}")

# ── TAB 2: Verificar sync ─────────────────────────────────────────────────────
with tab_sync:
    st.subheader("Registros en imile cloud por fecha")
    st.caption("Compara con el despacho local para verificar que están sincronizados.")

    col1, col2 = st.columns(2)
    with col1:
        desde = st.date_input("Desde", value=date.today() - timedelta(days=7), key="sync_desde")
    with col2:
        hasta = st.date_input("Hasta", value=date.today(), key="sync_hasta")

    if st.button("🔍 Consultar cloud"):
        with st.spinner("Consultando…"):
            df_res = _resumen_cloud(desde, hasta)

        if df_res.empty:
            st.warning("No hay registros en ese rango de fechas.")
        else:
            total = df_res["total"].sum()
            st.metric("Total paquetes en cloud", total)
            st.dataframe(df_res, use_container_width=True, hide_index=True)

            # Alerta si alguna fecha tiene 0 registros (vacíos de sync)
            rango = pd.date_range(desde, hasta)
            fechas_cloud = set(df_res["f_emi"].astype(str))
            faltantes = [
                str(d.date()) for d in rango
                if str(d.date()) not in fechas_cloud
            ]
            if faltantes:
                st.warning(
                    f"**{len(faltantes)} fecha(s) sin registros en cloud:** "
                    + ", ".join(faltantes)
                )
            else:
                st.success("Todas las fechas del rango tienen registros en cloud.")
