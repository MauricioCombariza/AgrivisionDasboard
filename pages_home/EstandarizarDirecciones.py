# -*- coding: utf-8 -*-
"""
Estandarización de Direcciones Colombianas
===========================================
Integra la lógica de dirnum para:
  - Estandarizar direcciones (estandarizar_direccion)
  - Generar dirección numérica de 18 dígitos (generar_direccion_numerica)
  - Buscar sector (buscar_sector)
  - Buscar código postal (buscar_codigo_postal)
  - Buscar localidad (buscar_localidad)
"""

import sys
import os
import io
import streamlit as st
import pandas as pd

# Asegurar que la carpeta dirnum esté en el path
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DIRNUM_DIR = os.path.join(_BASE_DIR, "dirnum")
if _DIRNUM_DIR not in sys.path:
    sys.path.insert(0, _DIRNUM_DIR)

from estandarizar_direcciones_v3 import (
    estandarizar_direccion,
    generar_direccion_numerica,
    buscar_sector,
    buscar_codigo_postal,
    buscar_localidad,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def procesar_fila(dir_original: str) -> dict:
    """Corre el pipeline completo para una dirección."""
    dir_std   = estandarizar_direccion(str(dir_original)) if dir_original else None
    dirnum    = generar_direccion_numerica(dir_std)        if dir_std   else None
    sector    = buscar_sector(dirnum)                      if dirnum    else None
    cod_postal = buscar_codigo_postal(dir_std)             if dir_std   else None
    localidad  = buscar_localidad(dir_std)                 if dir_std   else None
    return {
        "dir_estandarizada": dir_std,
        "dirnum":            dirnum,
        "sector":            sector,
        "cod_postal":        cod_postal,
        "localidad":         localidad,
    }


def df_a_excel(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.title("📍 Estandarización de Direcciones")
st.markdown(
    "Estandariza direcciones colombianas y genera "
    "**dirección numérica**, **sector**, **código postal** y **localidad**."
)

tab_individual, tab_masiva = st.tabs(["Dirección individual", "Carga masiva (Excel)"])

# ── Tab 1: Individual ────────────────────────────────────────────────────────
with tab_individual:
    st.subheader("Probar una dirección")
    dir_input = st.text_input(
        "Escribe la dirección",
        placeholder="Ej: Calle 95 # 49-22 apto 301",
    )

    if dir_input.strip():
        with st.spinner("Procesando..."):
            res = procesar_fila(dir_input.strip())

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Dirección estandarizada", res["dir_estandarizada"] or "—")
            st.metric("Dirección numérica (18 dígitos)", res["dirnum"] or "—")
            st.metric("Sector", res["sector"] or "—")
        with col2:
            st.metric("Código postal", res["cod_postal"] or "—")
            st.metric("Localidad", res["localidad"] or "—")

        if res["dirnum"]:
            with st.expander("Desglose de la dirección numérica"):
                d = res["dirnum"]
                try:
                    cardinal_map = {"1": "NORTE/sin cardinal", "2": "SUR", "3": "SUR ESTE", "4": "ESTE"}
                    tipo_map     = {"1": "CL / DG", "3": "CR / TR"}
                    sep_map      = {"1": "impar", "3": "par"}
                    rows = [
                        ("Pos [1]  — Cardinal",           d[0],    cardinal_map.get(d[0], d[0])),
                        ("Pos [2]  — Tipo vía",           d[1],    tipo_map.get(d[1], d[1])),
                        ("Pos [3-5] — Número vía principal",d[2:5], ""),
                        ("Pos [6-8] — Letras vía principal",d[5:8], "código de letras"),
                        ("Pos [9]  — Separador / paridad", d[8],    sep_map.get(d[8], d[8])),
                        ("Pos [10-12] — Número vía secundaria", d[9:12], ""),
                        ("Pos [13-15] — Letras vía secundaria", d[12:15], "código de letras"),
                        ("Pos [16-18] — Placa",           d[15:18], ""),
                    ]
                    st.table(pd.DataFrame(rows, columns=["Campo", "Valor", "Descripción"]))
                except Exception:
                    st.code(d)

# ── Tab 2: Masiva ─────────────────────────────────────────────────────────────
with tab_masiva:
    st.subheader("Procesar archivo Excel")
    st.markdown(
        "El archivo debe tener una columna llamada **`dirdes1`** "
        "(o cualquier nombre que elijas abajo). "
        "Se agregarán las columnas: `dir_estandarizada`, `dirnum`, `sector`, "
        "`cod_postal`, `localidad`."
    )

    archivo = st.file_uploader("Seleccionar archivo Excel", type=["xlsx", "xls"])

    if archivo is not None:
        try:
            df = pd.read_excel(archivo)
        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")
            st.stop()

        # Detectar columna de dirección
        columnas_disponibles = list(df.columns)
        col_default = next(
            (c for c in columnas_disponibles if c.lower().strip() == "dirdes1"),
            columnas_disponibles[0] if columnas_disponibles else None,
        )
        col_dir = st.selectbox(
            "Columna con la dirección",
            options=columnas_disponibles,
            index=columnas_disponibles.index(col_default) if col_default else 0,
        )

        total = len(df)
        st.info(f"Archivo cargado: **{total}** filas — columna seleccionada: **{col_dir}**")

        if st.button("▶ Procesar direcciones", type="primary"):
            progreso = st.progress(0, text="Iniciando...")
            resultados = []
            for i, val in enumerate(df[col_dir].astype(str)):
                resultados.append(procesar_fila(val))
                if i % max(1, total // 100) == 0:
                    pct = int((i + 1) / total * 100)
                    progreso.progress(pct, text=f"Procesando {i+1}/{total}…")
            progreso.progress(100, text="Completado")

            df_res = pd.concat([df, pd.DataFrame(resultados)], axis=1)

            n_std  = df_res["dir_estandarizada"].notna().sum()
            n_num  = df_res["dirnum"].notna().sum()
            n_sec  = df_res["sector"].notna().sum()
            n_cp   = df_res["cod_postal"].notna().sum()
            n_loc  = df_res["localidad"].notna().sum()

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Estandarizadas",  f"{n_std}/{total}")
            c2.metric("Con dirnum",       f"{n_num}/{total}")
            c3.metric("Con sector",       f"{n_sec}/{total}")
            c4.metric("Con cód. postal",  f"{n_cp}/{total}")
            c5.metric("Con localidad",    f"{n_loc}/{total}")

            st.dataframe(df_res, use_container_width=True)

            excel_bytes = df_a_excel(df_res)
            st.download_button(
                label="📥 Descargar resultado en Excel",
                data=excel_bytes,
                file_name="direcciones_estandarizadas.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
