"""
14_Actualizacion_Nube.py  ·  Pipeline completo de sincronización con la nube
=============================================================================
Ejecuta 5 pasos secuenciales.  Cada paso muestra un resumen y requiere
que el usuario pulse el botón del siguiente paso para continuar.

  Paso 1 → Descarga los últimos 300 000 registros de 'histo' desde bases_web
  Paso 2 → Genera ordenes_procesadas.csv (órdenes nuevas) + imile_envios.csv
  Paso 3 → Genera agrupacion.csv (gestiones escáner) + paquetes_imile.csv
  Paso 4 → Inserta / actualiza ordenes en la BD logistica de la nube
  Paso 5 → Inserta / actualiza gestiones_mensajero en la BD logistica de la nube

Todos los CSVs intermedios se guardan en la carpeta de trabajo que el usuario
configura al inicio; así cualquier dispositivo puede usar su propia ruta.
"""

import io
import logging
import os
import traceback
from datetime import date as date_cls
from pathlib import Path

import mysql.connector
import numpy as np
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Carga las variables del archivo .env (host, usuario, contraseña de cada BD).
# load_dotenv() no sobreescribe variables ya definidas en el entorno del SO,
# lo que permite override en producción sin cambiar el archivo .env.
load_dotenv()

# ---------------------------------------------------------------------------
# CONFIGURACIÓN DE LOGS
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CREDENCIALES LEÍDAS DESDE .env
# ---------------------------------------------------------------------------
# BD bases_web  →  tabla histo (lectura)
_BW_HOST = os.environ.get("DB_HOST_BASES_WEB", "186.180.15.66")
_BW_PORT = int(os.environ.get("DB_PORT_BASES_WEB", "12539"))
_BW_USER = os.environ.get("DB_USER_BASES_WEB", "servilla_remoto")
_BW_PASS = os.environ.get("DB_PASSWORD_BASES_WEB", "")
_BW_NAME = os.environ.get("DB_NAME_BASES_WEB", "bases_web")

# BD logistica  →  ordenes, gestiones_mensajero, clientes, precios… (escritura)
_LG_HOST = os.environ.get("DB_HOST", "localhost")
_LG_PORT = int(os.environ.get("DB_PORT", "3306"))
_LG_USER = os.environ.get("DB_USER", "root")
_LG_PASS = os.environ.get("DB_PASSWORD", "")
_LG_NAME = os.environ.get("DB_NAME_LOGISTICA", "logistica")

# Número máximo de filas que se descargan de 'histo' para no sobrecargar la red.
HISTO_LIMIT = 300_000

# Couriers internos de Carvajal que se excluyen de las órdenes (no son clientes externos).
COURIERS_EXCLUIDOS = {"lecta", "prindel"}

# ---------------------------------------------------------------------------
# UI - TÍTULO
# ---------------------------------------------------------------------------
st.title("☁️ Actualización desde la Nube")
st.caption(
    "Pipeline automático · descarga histo → procesa órdenes y gestiones → "
    "actualiza la BD logistica en la nube"
)

# ---------------------------------------------------------------------------
# SECCIÓN DE CONFIGURACIÓN: carpeta de trabajo
# ---------------------------------------------------------------------------
# La carpeta es configurable porque la app puede correr desde cualquier
# dispositivo (Windows, Mac, etc.) con rutas de Downloads distintas.
st.markdown("### ⚙️ Configuración")

_default_carpeta = str(Path.home() / "Downloads" / "Dashboard")

carpeta = st.text_input(
    "Carpeta de trabajo (archivos CSV intermedios)",
    value=st.session_state.get("carpeta_nube", _default_carpeta),
    help="Se creará automáticamente si no existe. "
         "Cambia esta ruta según el dispositivo que uses.",
)
st.session_state["carpeta_nube"] = carpeta

# Botón auxiliar para crear la carpeta sin tener que avanzar al Paso 1.
if st.button("📁 Crear carpeta si no existe", key="btn_crear_carpeta"):
    try:
        Path(carpeta).mkdir(parents=True, exist_ok=True)
        st.success(f"Carpeta lista: `{carpeta}`")
    except Exception as exc:
        st.error(f"No se pudo crear la carpeta: {exc}")

st.divider()

# ---------------------------------------------------------------------------
# HELPERS DE CONEXIÓN
# ---------------------------------------------------------------------------

@st.cache_resource
def _get_histo_engine():
    """
    Engine SQLAlchemy para leer de bases_web (tabla histo).
    Se cachea como resource para no recrear el pool en cada rerun.
    Las credenciales vienen de las variables de entorno _BW_*.
    """
    url = (
        f"mysql+mysqlconnector://{_BW_USER}:{_BW_PASS}"
        f"@{_BW_HOST}:{_BW_PORT}/{_BW_NAME}"
    )
    return create_engine(url, pool_pre_ping=True)


def _conectar_logistica():
    """
    Abre una conexión fresca a la BD logistica en la nube (escritura).
    Las credenciales vienen de las variables de entorno _LG_*.
    Retorna None (y muestra error) si falla.
    """
    try:
        return mysql.connector.connect(
            host=_LG_HOST,
            port=_LG_PORT,
            user=_LG_USER,
            password=_LG_PASS,
            database=_LG_NAME,
            connect_timeout=15,
        )
    except Exception as exc:
        st.error(f"❌ No se pudo conectar a la nube (logistica): {exc}")
        return None


# ---------------------------------------------------------------------------
# ESTADO DEL PIPELINE  (se almacena en session_state para sobrevivir reruns)
# ---------------------------------------------------------------------------

if "paso_ok" not in st.session_state:
    # Diccionario {1: bool, 2: bool, …}  — False = pendiente, True = completado
    st.session_state.paso_ok = {n: False for n in range(1, 6)}


def _marcar_paso(n: int):
    """Marca un paso como completado."""
    st.session_state.paso_ok[n] = True


def _resetear_desde(n: int):
    """
    Cuando se reprocesa un paso, todos los pasos posteriores vuelven a
    pendiente para evitar usar resultados desactualizados.
    """
    for i in range(n, 6):
        st.session_state.paso_ok[i] = False


def _icono(n: int) -> str:
    return "✅" if st.session_state.paso_ok[n] else "⏳"


# ---------------------------------------------------------------------------
# PASO 1 · Descargar histo.csv
# ---------------------------------------------------------------------------
with st.expander(
    f"{_icono(1)} Paso 1 · Descargar histo.csv desde la nube",
    expanded=not st.session_state.paso_ok[1],
):
    st.info(
        f"Descarga los últimos **{HISTO_LIMIT:,}** registros de la tabla `histo` "
        f"(base `{_BW_NAME}`) y los guarda como `histo.csv` en la carpeta de trabajo."
    )

    if st.button("⬇️ Descargar histo.csv", type="primary", key="btn_p1"):
        try:
            Path(carpeta).mkdir(parents=True, exist_ok=True)

            engine = _get_histo_engine()

            # Seleccionamos sólo las columnas que usan los pasos 2 y 3.
            # Ordenar DESC por orden (convertido a entero) garantiza traer
            # los registros más recientes cuando la tabla tiene millones de filas.
            query = f"""
                SELECT orden, f_emi, no_entidad, ciudad1, courrier,
                       retorno, ret_esc, serial,
                       f_esc, cod_men, lot_esc, mot_esc, cod_sec
                FROM histo
                ORDER BY CAST(NULLIF(TRIM(orden), '') AS SIGNED) DESC
                LIMIT {HISTO_LIMIT}
            """

            with st.spinner(f"Descargando {HISTO_LIMIT:,} registros…"):
                df_h = pd.read_sql(query, engine)

            ruta_histo = Path(carpeta) / "histo.csv"
            df_h.to_csv(ruta_histo, index=False)

            size_mb = ruta_histo.stat().st_size / 1_048_576
            st.success(
                f"✅ {len(df_h):,} registros guardados → `histo.csv` ({size_mb:.1f} MB)"
            )
            st.dataframe(df_h.head(5), use_container_width=True)

            _resetear_desde(2)
            _marcar_paso(1)
            st.rerun()

        except Exception as exc:
            st.error(f"❌ Error al descargar: {exc}")
            st.code(traceback.format_exc())

    if st.session_state.paso_ok[1]:
        ruta_h = Path(carpeta) / "histo.csv"
        size_mb = ruta_h.stat().st_size / 1_048_576 if ruta_h.exists() else 0
        st.success(f"histo.csv ya descargado ({size_mb:.1f} MB)")

# ---------------------------------------------------------------------------
# PASO 2 · Generar ordenes_procesadas.csv + imile_envios.csv
# ---------------------------------------------------------------------------
with st.expander(
    f"{_icono(2)} Paso 2 · Generar ordenes_procesadas.csv e imile_envios.csv",
    expanded=st.session_state.paso_ok[1] and not st.session_state.paso_ok[2],
):
    if not st.session_state.paso_ok[1]:
        st.warning("Completa el Paso 1 primero.")
    else:
        st.info(
            "Sube el archivo **delivered.xlsx** de iMile.  "
            "Se usará aquí (para generar imile_envios.csv) y también en el Paso 3."
        )

        delivered_file = st.file_uploader(
            "📤 delivered.xlsx / delivered.xls",
            type=["xlsx", "xls"],
            key="delivered_p2",
        )

        # El botón sólo se activa cuando hay archivo cargado.
        btn_p2 = st.button(
            "🔄 Procesar",
            type="primary",
            key="btn_p2",
            disabled=(delivered_file is None),
        )

        if btn_p2 and delivered_file is not None:
            try:
                ruta_histo = Path(carpeta) / "histo.csv"
                df_h = pd.read_csv(ruta_histo, low_memory=False)

                # ── 2A · Consultar órdenes ya existentes en la nube ──────────────
                # Así sólo se insertan órdenes nuevas, igual que hace Procesador_Ordenes.py
                with st.spinner("Consultando órdenes existentes en la nube…"):
                    conn_cl = _conectar_logistica()
                    ordenes_exist = set()
                    if conn_cl:
                        cur = conn_cl.cursor()
                        cur.execute("SELECT numero_orden FROM ordenes")
                        ordenes_exist = {str(r[0]) for r in cur.fetchall()}
                        cur.close()
                        conn_cl.close()

                st.caption(f"Órdenes ya registradas en la nube: {len(ordenes_exist):,}")

                # ── 2B · histo → ordenes_procesadas.csv ──────────────────────────
                with st.spinner("Procesando histo → ordenes_procesadas…"):
                    df = df_h.copy()

                    # Convertir orden a entero (puede venir como string del CSV)
                    df["orden"] = (
                        pd.to_numeric(df["orden"], errors="coerce").fillna(0).astype(int)
                    )

                    # Excluir couriers internos de Carvajal
                    if "courrier" in df.columns:
                        df = df[
                            ~df["courrier"]
                            .fillna("")
                            .str.lower()
                            .str.strip()
                            .isin(COURIERS_EXCLUIDOS)
                        ].copy()

                    df["f_emi"] = pd.to_datetime(df["f_emi"], errors="coerce")

                    # Clasificar destino: "bog" en ciudad → local; resto → nacional
                    es_local = (
                        df["ciudad1"].fillna("").str.contains("bog", case=False, na=False)
                        | df["ciudad1"].isna()
                    )
                    df["local"]    = np.where(es_local,  1, 0)
                    df["nacional"] = np.where(~es_local, 1, 0)

                    # Agrupar por número de orden (una fila por orden)
                    df_ord = (
                        df.groupby("orden")
                        .agg(
                            fecha_recepcion=("f_emi",    "first"),
                            nombre_cliente  =("no_entidad", "first"),
                            cantidad_local  =("local",    "sum"),
                            cantidad_nacional=("nacional", "sum"),
                        )
                        .reset_index()
                    )

                    df_ord["tipo_servicio"]   = "sobre"
                    df_ord["fecha_recepcion"] = pd.to_datetime(
                        df_ord["fecha_recepcion"]
                    ).dt.date
                    df_ord["cantidad_local"]    = df_ord["cantidad_local"].astype(int)
                    df_ord["cantidad_nacional"] = df_ord["cantidad_nacional"].astype(int)

                    # Filtrar sólo las órdenes que NO existen en la nube todavía
                    df_ord["_orden_str"] = df_ord["orden"].astype(str)
                    df_nuevas = df_ord[
                        ~df_ord["_orden_str"].isin(ordenes_exist)
                    ].drop("_orden_str", axis=1)

                    df_nuevas = df_nuevas[
                        ["orden", "fecha_recepcion", "nombre_cliente",
                         "tipo_servicio", "cantidad_local", "cantidad_nacional"]
                    ]

                ruta_ord = Path(carpeta) / "ordenes_procesadas.csv"
                df_nuevas.to_csv(ruta_ord, index=False)

                # ── 2C · delivered.xlsx → imile_envios.csv ───────────────────────
                with st.spinner("Procesando iMile…"):
                    df_del = pd.read_excel(delivered_file)

                    cols_req = {"Scan time", "Waybill No."}
                    if not cols_req.issubset(df_del.columns):
                        st.error(
                            f"El archivo delivered debe tener: {cols_req}.  "
                            f"Columnas encontradas: {list(df_del.columns)}"
                        )
                        st.stop()

                    df_del["fecha_recepcion"] = pd.to_datetime(
                        df_del["Scan time"]
                    ).dt.date

                    # Agrupar por fecha → una orden IM por día (ej. IM20240315)
                    df_imile = (
                        df_del.groupby("fecha_recepcion")["Waybill No."]
                        .count()
                        .reset_index()
                    )
                    df_imile.columns = ["fecha_recepcion", "cantidad_local"]
                    df_imile["orden"] = df_imile["fecha_recepcion"].apply(
                        lambda x: "IM" + x.strftime("%Y%m%d")
                    )
                    df_imile["nombre_cliente"]    = "Imile SAS"
                    df_imile["tipo_servicio"]     = "paquete"
                    df_imile["cantidad_nacional"] = 0
                    df_imile = df_imile[
                        ["orden", "fecha_recepcion", "nombre_cliente",
                         "tipo_servicio", "cantidad_local", "cantidad_nacional"]
                    ]

                ruta_imile = Path(carpeta) / "imile_envios.csv"
                df_imile.to_csv(ruta_imile, index=False)

                # Guardar los bytes del Excel en session_state para el Paso 3
                # (el file_uploader se limpia en el siguiente rerun)
                delivered_file.seek(0)
                st.session_state["delivered_bytes"] = delivered_file.read()

                st.success(f"✅ ordenes_procesadas.csv → {len(df_nuevas):,} órdenes nuevas")
                st.success(f"✅ imile_envios.csv → {len(df_imile):,} registros")

                col1, col2 = st.columns(2)
                with col1:
                    st.dataframe(df_nuevas.head(5), use_container_width=True)
                with col2:
                    st.dataframe(df_imile.head(5), use_container_width=True)

                _resetear_desde(3)
                _marcar_paso(2)
                st.rerun()

            except Exception as exc:
                st.error(f"❌ Error en Paso 2: {exc}")
                st.code(traceback.format_exc())

        if st.session_state.paso_ok[2]:
            st.success("ordenes_procesadas.csv e imile_envios.csv listos.")

# ---------------------------------------------------------------------------
# PASO 3 · Generar agrupacion.csv + paquetes_imile.csv
# ---------------------------------------------------------------------------
with st.expander(
    f"{_icono(3)} Paso 3 · Generar agrupacion.csv y paquetes_imile.csv",
    expanded=st.session_state.paso_ok[2] and not st.session_state.paso_ok[3],
):
    if not st.session_state.paso_ok[2]:
        st.warning("Completa el Paso 2 primero.")
    else:
        st.info(
            "Agrupa los registros de histo por escáner (f_esc, cod_men, lot_esc, orden) "
            "y procesa el delivered.xlsx para obtener los paquetes iMile por mensajero."
        )

        if st.button("🔄 Procesar Agrupación", type="primary", key="btn_p3"):
            try:
                ruta_histo = Path(carpeta) / "histo.csv"
                df_h = pd.read_csv(ruta_histo, low_memory=False)

                # ── 3A · Cargar mapeos desde la BD nube ──────────────────────────
                with st.spinner("Cargando mapeos desde la nube…"):
                    conn_cl = _conectar_logistica()
                    mapeo_da: dict       = {}   # DA → cod_mensajero (para paquetes iMile)
                    mapeos_cli: dict     = {}   # nombre_csv → nombre_bd (normalización clientes)

                    if conn_cl:
                        cur = conn_cl.cursor(dictionary=True)

                        # Mapeo DA→mensajero (tabla mapeo_da en logistica)
                        try:
                            cur.execute(
                                "SELECT nombre_da, cod_mensajero FROM mapeo_da"
                            )
                            mapeo_da = {
                                r["nombre_da"]: r["cod_mensajero"]
                                for r in cur.fetchall()
                            }
                        except Exception:
                            pass  # tabla puede no existir aún

                        # Mapeo de nombres de clientes del CSV a nombres en BD
                        try:
                            cur.execute(
                                "SELECT nombre_csv, nombre_bd FROM mapeo_clientes"
                            )
                            mapeos_cli = {
                                r["nombre_csv"].upper(): r["nombre_bd"]
                                for r in cur.fetchall()
                            }
                        except Exception:
                            pass

                        cur.close()
                        conn_cl.close()

                # ── 3B · histo → agrupacion.csv ──────────────────────────────────
                with st.spinner("Generando agrupacion.csv…"):
                    df_ag = df_h.copy()

                    # Sólo filas con fecha de escáner válida (formato AAAA.MM.DD)
                    df_ag = df_ag[
                        df_ag["f_esc"]
                        .fillna("")
                        .str.match(r"^\d{4}\.\d{2}\.\d{2}$", na=False)
                    ].copy()

                    # Normalizar cod_men: quitar caracteres no numéricos, rellenar 4 dígitos
                    df_ag["cod_men"] = (
                        df_ag["cod_men"]
                        .fillna(0)
                        .astype(str)
                        .str.replace(r"[^\d]", "", regex=True)
                        .replace("", "0")
                        .astype(int)
                        .astype(str)
                        .str.zfill(4)
                    )
                    df_ag["lot_esc"] = df_ag["lot_esc"].fillna(0).astype(int)
                    df_ag["orden"]   = df_ag["orden"].fillna(0).astype(int)

                    if "cod_sec" not in df_ag.columns:
                        df_ag["cod_sec"] = ""
                    else:
                        df_ag["cod_sec"] = df_ag["cod_sec"].fillna("").astype(str)

                    # Normalizar nombres de clientes usando el mapeo de BD
                    df_ag["no_entidad"] = df_ag["no_entidad"].apply(
                        lambda n: mapeos_cli.get(str(n).upper().strip(), n)
                    )

                    # Eliminar seriales duplicados (el mismo serial no debe contar dos veces)
                    df_ag = df_ag.drop_duplicates(subset=["serial"], keep="first")

                    # Reasignar cod_men 0999: si un lote tiene exactamente 2 códigos
                    # y uno es 0999, los registros del 0999 pasan al otro código.
                    lotes_0999 = df_ag[df_ag["cod_men"] == "0999"]["lot_esc"].unique()
                    for lote in lotes_0999:
                        codigos = df_ag[df_ag["lot_esc"] == lote]["cod_men"].unique()
                        if len(codigos) == 2 and "0999" in codigos:
                            otro = next(c for c in codigos if c != "0999")
                            df_ag.loc[
                                (df_ag["lot_esc"] == lote) & (df_ag["cod_men"] == "0999"),
                                "cod_men",
                            ] = otro

                    # Agrupar y contar seriales por combinación de escáner
                    cols_grp = ["f_esc", "cod_men", "lot_esc", "orden", "mot_esc", "no_entidad"]
                    resultado_ag = (
                        df_ag.groupby(cols_grp, as_index=False)
                        .agg(total_serial=("serial", "count"))
                        .sort_values(["f_esc", "cod_men", "lot_esc", "orden"])
                    )

                ruta_ag = Path(carpeta) / "agrupacion.csv"
                resultado_ag.to_csv(ruta_ag, index=False)

                # ── 3C · delivered.xlsx → paquetes_imile.csv ─────────────────────
                delivered_bytes = st.session_state.get("delivered_bytes")
                df_paq_final = pd.DataFrame()

                if delivered_bytes:
                    with st.spinner("Generando paquetes_imile.csv…"):
                        df_paq = pd.read_excel(io.BytesIO(delivered_bytes))
                        df_paq.columns = df_paq.columns.str.strip()

                        cols_req = ["DA", "Scan time", "Waybill No."]
                        faltantes = [c for c in cols_req if c not in df_paq.columns]

                        if faltantes:
                            st.error(
                                f"Columnas faltantes en delivered: {faltantes}.  "
                                f"Encontradas: {list(df_paq.columns)}"
                            )
                        else:
                            # Mapear DA al código de mensajero registrado en BD
                            df_paq["cod_men"] = df_paq["DA"].map(mapeo_da)

                            das_sin_mapeo = (
                                df_paq[df_paq["cod_men"].isna()]["DA"].unique()
                            )
                            if len(das_sin_mapeo) > 0:
                                st.warning(
                                    f"DAs sin mapeo en BD: {list(das_sin_mapeo)}.  "
                                    "Agrégalos en Agrupación Escáner → Tab 2."
                                )

                            df_paq["Scan time"] = pd.to_datetime(
                                df_paq["Scan time"], errors="coerce"
                            )
                            # f_esc en formato AAAA.MM.DD igual que histo
                            df_paq["f_esc"] = df_paq["Scan time"].dt.strftime("%Y.%m.%d")
                            # orden con prefijo IM (igual que imile_envios)
                            df_paq["orden"] = df_paq["Scan time"].apply(
                                lambda x: (
                                    "IM" + x.strftime("%Y%m%d")
                                    if pd.notnull(x)
                                    else "IM_SIN_FECHA"
                                )
                            )
                            df_paq["lot_esc"]    = df_paq["orden"]
                            df_paq["mot_esc"]    = "Entrega"
                            df_paq["no_entidad"] = "Imile SAS"

                            cols_grp_paq = [
                                "f_esc", "cod_men", "lot_esc",
                                "orden", "mot_esc", "no_entidad",
                            ]
                            df_paq_final = (
                                df_paq.groupby(cols_grp_paq, as_index=False)
                                .agg(total_serial=("Waybill No.", "count"))
                                .sort_values(["f_esc", "cod_men"])
                            )

                            ruta_paq = Path(carpeta) / "paquetes_imile.csv"
                            df_paq_final.to_csv(ruta_paq, index=False)
                            st.success(
                                f"✅ paquetes_imile.csv → {len(df_paq_final):,} grupos"
                            )
                else:
                    st.warning(
                        "No se encontró el archivo delivered en la sesión.  "
                        "Vuelve al Paso 2 y sube el archivo nuevamente."
                    )

                st.success(f"✅ agrupacion.csv → {len(resultado_ag):,} grupos")

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**agrupacion.csv**")
                    st.dataframe(resultado_ag.head(5), use_container_width=True)
                with col2:
                    if not df_paq_final.empty:
                        st.markdown("**paquetes_imile.csv**")
                        st.dataframe(df_paq_final.head(5), use_container_width=True)

                _resetear_desde(4)
                _marcar_paso(3)
                st.rerun()

            except Exception as exc:
                st.error(f"❌ Error en Paso 3: {exc}")
                st.code(traceback.format_exc())

        if st.session_state.paso_ok[3]:
            st.success("agrupacion.csv y paquetes_imile.csv listos.")

# ---------------------------------------------------------------------------
# PASO 4 · Actualizar ordenes en la BD logistica de la nube
# ---------------------------------------------------------------------------
with st.expander(
    f"{_icono(4)} Paso 4 · Actualizar órdenes en la nube",
    expanded=st.session_state.paso_ok[3] and not st.session_state.paso_ok[4],
):
    if not st.session_state.paso_ok[3]:
        st.warning("Completa el Paso 3 primero.")
    else:
        ruta_ord   = Path(carpeta) / "ordenes_procesadas.csv"
        ruta_imile = Path(carpeta) / "imile_envios.csv"

        if not ruta_ord.exists() or not ruta_imile.exists():
            st.error("Faltan archivos CSV.  Repite el Paso 2.")
        else:
            df_ord_prev   = pd.read_csv(ruta_ord)
            df_imile_prev = pd.read_csv(ruta_imile)

            # Combinar ambos CSVs en un único DataFrame para procesarlos juntos
            df_todos_ord = pd.concat(
                [df_ord_prev, df_imile_prev], ignore_index=True
            )

            st.info(
                f"Se procesarán **{len(df_ord_prev):,}** órdenes + "
                f"**{len(df_imile_prev):,}** registros iMile → "
                f"**{len(df_todos_ord):,}** total"
            )

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**ordenes_procesadas.csv** (primeras filas)")
                st.dataframe(df_ord_prev.head(5), use_container_width=True)
            with col2:
                st.markdown("**imile_envios.csv** (primeras filas)")
                st.dataframe(df_imile_prev.head(5), use_container_width=True)

            if st.button(
                "⬆️ Actualizar Órdenes en la Nube",
                type="primary",
                key="btn_p4",
            ):
                conn_cl = _conectar_logistica()
                if not conn_cl:
                    st.stop()

                try:
                    # Cargar clientes y precios en memoria para evitar N+1 queries
                    cur_setup = conn_cl.cursor(dictionary=True)

                    cur_setup.execute(
                        "SELECT id, nombre_empresa FROM clientes WHERE activo = TRUE"
                    )
                    dict_clientes = {
                        c["nombre_empresa"].strip().lower(): c["id"]
                        for c in cur_setup.fetchall()
                    }

                    cur_setup.execute(
                        "SELECT cliente_id, tipo_servicio, ambito, precio_unitario "
                        "FROM precios_cliente WHERE activo = TRUE"
                    )
                    dict_precios = {
                        (
                            p["cliente_id"],
                            p["tipo_servicio"].lower(),
                            p["ambito"].lower(),
                        ): float(p["precio_unitario"])
                        for p in cur_setup.fetchall()
                    }
                    cur_setup.close()

                    # Desactivar autocommit: el commit único al final es mucho más rápido
                    conn_cl.autocommit = False
                    cur_op = conn_cl.cursor()

                    exitos, actualizados, errores = 0, 0, []
                    total_rows = len(df_todos_ord)

                    barra  = st.progress(0)
                    status = st.empty()

                    for i, fila in df_todos_ord.iterrows():
                        try:
                            nombre = str(fila["nombre_cliente"]).strip().lower()
                            id_cli = dict_clientes.get(nombre)
                            if not id_cli:
                                raise ValueError(
                                    f"Cliente '{fila['nombre_cliente']}' no existe en la nube."
                                )

                            tipo_ser = str(fila["tipo_servicio"]).lower()
                            c_loc    = int(float(fila.get("cantidad_local",    0)))
                            c_nac    = int(float(fila.get("cantidad_nacional", 0)))
                            num_ord  = str(fila["orden"])
                            fecha    = fila["fecha_recepcion"]

                            # Precio: local = ámbito 'bogota', nacional = ámbito 'nacional'
                            p_loc = dict_precios.get((id_cli, tipo_ser, "bogota"),    0.0)
                            p_nac = dict_precios.get((id_cli, tipo_ser, "nacional"),  0.0)
                            v_total = (c_loc * p_loc) + (c_nac * p_nac)

                            cur_op.execute(
                                "SELECT id FROM ordenes WHERE numero_orden = %s",
                                (num_ord,),
                            )
                            existente = cur_op.fetchone()

                            if existente:
                                cur_op.execute(
                                    """
                                    UPDATE ordenes
                                    SET cantidad_local = %s, cantidad_nacional = %s,
                                        cantidad_recibido_local = %s,
                                        cantidad_recibido_nacional = %s,
                                        valor_total = %s
                                    WHERE id = %s
                                    """,
                                    (c_loc, c_nac, c_loc, c_nac, v_total, existente[0]),
                                )
                                actualizados += 1
                            else:
                                cur_op.execute(
                                    """
                                    INSERT INTO ordenes
                                    (numero_orden, cliente_id, fecha_recepcion, tipo_servicio,
                                     cantidad_local, cantidad_nacional,
                                     cantidad_recibido_local, cantidad_recibido_nacional,
                                     valor_total, estado)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'activa')
                                    """,
                                    (
                                        num_ord, id_cli, fecha, tipo_ser,
                                        c_loc, c_nac, c_loc, c_nac, v_total,
                                    ),
                                )
                                exitos += 1

                        except Exception as exc_fila:
                            errores.append(f"Fila {i + 1}: {exc_fila}")

                        # Actualizar barra de progreso cada 10 filas
                        if total_rows > 0 and i % 10 == 0:
                            barra.progress((i + 1) / total_rows)
                            status.caption(f"Procesando {i + 1}/{total_rows}…")

                    # Un solo COMMIT para máxima velocidad (transacción atómica)
                    conn_cl.commit()
                    barra.progress(1.0)
                    status.empty()

                    st.success(
                        f"✅ {exitos:,} nuevas insertadas | "
                        f"{actualizados:,} actualizadas en la nube"
                    )
                    if errores:
                        with st.expander(f"Ver {len(errores)} errores/advertencias"):
                            for err in errores:
                                st.warning(err)

                    _resetear_desde(5)
                    _marcar_paso(4)
                    st.rerun()

                except Exception as exc_db:
                    conn_cl.rollback()
                    st.error(f"❌ Error crítico en Paso 4: {exc_db}")
                    st.code(traceback.format_exc())
                finally:
                    conn_cl.autocommit = True
                    conn_cl.close()

        if st.session_state.paso_ok[4]:
            st.success("Órdenes actualizadas en la nube.")

# ---------------------------------------------------------------------------
# PASO 5 · Actualizar gestiones_mensajero en la BD logistica de la nube
# ---------------------------------------------------------------------------
with st.expander(
    f"{_icono(5)} Paso 5 · Actualizar gestiones de mensajeros en la nube",
    expanded=st.session_state.paso_ok[4] and not st.session_state.paso_ok[5],
):
    if not st.session_state.paso_ok[4]:
        st.warning("Completa el Paso 4 primero.")
    else:
        ruta_ag  = Path(carpeta) / "agrupacion.csv"
        ruta_paq = Path(carpeta) / "paquetes_imile.csv"

        if not ruta_ag.exists():
            st.error("Falta agrupacion.csv.  Repite el Paso 3.")
        else:
            df_ag_prev  = pd.read_csv(ruta_ag)
            df_paq_prev = pd.read_csv(ruta_paq) if ruta_paq.exists() else pd.DataFrame()

            df_todos_gest = (
                pd.concat([df_ag_prev, df_paq_prev], ignore_index=True)
                if not df_paq_prev.empty
                else df_ag_prev.copy()
            )

            st.info(
                f"Se procesarán **{len(df_ag_prev):,}** grupos de agrupación + "
                f"**{len(df_paq_prev):,}** paquetes iMile → "
                f"**{len(df_todos_gest):,}** total"
            )

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**agrupacion.csv** (primeras filas)")
                st.dataframe(df_ag_prev.head(5), use_container_width=True)
            with col2:
                if not df_paq_prev.empty:
                    st.markdown("**paquetes_imile.csv** (primeras filas)")
                    st.dataframe(df_paq_prev.head(5), use_container_width=True)

            if st.button(
                "⬆️ Actualizar Gestiones en la Nube",
                type="primary",
                key="btn_p5",
            ):
                conn_cl = _conectar_logistica()
                if not conn_cl:
                    st.stop()

                try:
                    cur_setup = conn_cl.cursor(dictionary=True)

                    # ── Precios por mensajero (entrega / devolución) ──────────────
                    cur_setup.execute(
                        """
                        SELECT c.nombre_empresa,
                               pc.costo_mensajero_entrega,
                               pc.costo_mensajero_devolucion
                        FROM precios_cliente pc
                        JOIN clientes c ON pc.cliente_id = c.id
                        WHERE pc.activo = TRUE AND pc.ambito = 'bogota' AND pc.zona IS NULL
                        """
                    )
                    precios_men: dict = {}
                    for p in cur_setup.fetchall():
                        key = p["nombre_empresa"].upper().strip()
                        if key not in precios_men:
                            precios_men[key] = {"entrega": 0.0, "devolucion": 0.0}
                        # Entrega: precio más bajo (más favorable al cliente)
                        if p["costo_mensajero_entrega"]:
                            nuevo = float(p["costo_mensajero_entrega"])
                            if precios_men[key]["entrega"] == 0 or nuevo < precios_men[key]["entrega"]:
                                precios_men[key]["entrega"] = nuevo
                        # Devolución: precio más alto (mayor cobertura)
                        if p["costo_mensajero_devolucion"]:
                            nuevo = float(p["costo_mensajero_devolucion"])
                            if nuevo > precios_men[key]["devolucion"]:
                                precios_men[key]["devolucion"] = nuevo

                    # ── Personal activo (código → id) ────────────────────────────
                    cur_setup.execute(
                        "SELECT codigo, id FROM personal WHERE activo = TRUE"
                    )
                    personal_bd = {
                        m["codigo"]: m["id"] for m in cur_setup.fetchall()
                    }

                    # ── Planillas marcadas como revisadas → no se modifican ───────
                    planillas_revisadas: set = set()
                    try:
                        cur_setup.execute("SELECT lot_esc FROM planillas_revisadas")
                        planillas_revisadas = {
                            str(r["lot_esc"]) for r in cur_setup.fetchall()
                        }
                    except Exception:
                        pass  # tabla puede no existir

                    # ── Lotes con registros editados manualmente (candado) ────────
                    # No se insertan nuevos registros para no contaminar esos lotes.
                    lotes_candado: set = set()
                    try:
                        cur_setup.execute(
                            "SELECT DISTINCT lot_esc FROM gestiones_mensajero "
                            "WHERE editado_manualmente = 1"
                        )
                        lotes_candado = {
                            str(r["lot_esc"]) for r in cur_setup.fetchall()
                        }
                    except Exception:
                        pass

                    cur_setup.close()

                    conn_cl.autocommit = False
                    cur_op = conn_cl.cursor()

                    insertados, actualizados, errores = 0, 0, []
                    total_rows = len(df_todos_gest)

                    barra  = st.progress(0)
                    status = st.empty()

                    for i, (_, row) in enumerate(df_todos_gest.iterrows()):
                        try:
                            # lot_esc puede ser entero (agrupacion) o string tipo "IM20240315"
                            lot_raw = row.get("lot_esc", "0")
                            try:
                                lot_esc_val = str(int(float(lot_raw)))
                            except (ValueError, TypeError):
                                lot_esc_val = str(lot_raw)

                            # Planillas revisadas no se tocan
                            if lot_esc_val in planillas_revisadas:
                                continue

                            # orden puede ser entero o string tipo "IM20240315"
                            ord_raw = row.get("orden", "0")
                            try:
                                orden_val = str(int(float(ord_raw)))
                            except (ValueError, TypeError):
                                orden_val = str(ord_raw)

                            tipo_gestion = str(row["mot_esc"])
                            cliente      = str(row["no_entidad"])
                            cod_men_val  = str(row["cod_men"])
                            total_ser    = int(row["total_serial"])

                            # Calcular precio según tipo de gestión
                            cli_key  = cliente.upper().strip()
                            mot_low  = tipo_gestion.lower().strip()
                            tipo_precio = "entrega" if "entrega" in mot_low else "devolucion"
                            valor_unit  = precios_men.get(cli_key, {}).get(tipo_precio, 0.0)
                            valor_tot   = valor_unit * total_ser

                            # ID del mensajero (puede ser None si el código no está en BD)
                            m_id = personal_bd.get(cod_men_val, None)

                            # Verificar si ya existe el registro en gestiones_mensajero
                            cur_op.execute(
                                """
                                SELECT id FROM gestiones_mensajero
                                WHERE lot_esc = %s AND orden = %s
                                  AND tipo_gestion = %s AND cliente = %s
                                  AND cod_mensajero = %s
                                """,
                                (lot_esc_val, orden_val, tipo_gestion, cliente, cod_men_val),
                            )
                            existente = cur_op.fetchone()

                            if existente:
                                # Actualizar sólo si NO tiene candado manual
                                cur_op.execute(
                                    """
                                    UPDATE gestiones_mensajero
                                    SET total_seriales = %s,
                                        valor_unitario = %s,
                                        valor_total    = %s
                                    WHERE id = %s AND editado_manualmente = 0
                                    """,
                                    (total_ser, valor_unit, valor_tot, existente[0]),
                                )
                                if cur_op.rowcount > 0:
                                    actualizados += 1

                            elif lot_esc_val not in lotes_candado:
                                # Insertar sólo si el lote no tiene candado manual
                                cur_op.execute(
                                    """
                                    INSERT INTO gestiones_mensajero
                                    (fecha_escaner, cod_mensajero, mensajero_id,
                                     lot_esc, orden, tipo_gestion, cliente,
                                     total_seriales, valor_unitario, valor_total,
                                     fecha_registro, cod_sec)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    """,
                                    (
                                        row["f_esc"], cod_men_val, m_id,
                                        lot_esc_val, orden_val, tipo_gestion, cliente,
                                        total_ser, valor_unit, valor_tot,
                                        date_cls.today(), None,
                                    ),
                                )
                                insertados += 1

                        except Exception as exc_row:
                            errores.append(f"Fila {i + 1}: {exc_row}")

                        if total_rows > 0 and i % 10 == 0:
                            barra.progress((i + 1) / total_rows)
                            status.caption(f"Procesando {i + 1}/{total_rows}…")

                    conn_cl.commit()
                    barra.progress(1.0)
                    status.empty()

                    st.success(
                        f"✅ {insertados:,} insertados | "
                        f"{actualizados:,} actualizados en la nube"
                    )
                    if errores:
                        with st.expander(f"Ver {len(errores)} errores"):
                            for err in errores[:30]:
                                st.warning(err)

                    _marcar_paso(5)
                    st.rerun()

                except Exception as exc_db:
                    conn_cl.rollback()
                    st.error(f"❌ Error crítico en Paso 5: {exc_db}")
                    st.code(traceback.format_exc())
                finally:
                    conn_cl.autocommit = True
                    conn_cl.close()

        if st.session_state.paso_ok[5]:
            st.balloons()
            st.success("🎉 ¡Pipeline completo!  Todos los datos fueron actualizados en la nube.")
            if st.button("🔄 Reiniciar pipeline", key="btn_reiniciar"):
                st.session_state.paso_ok = {n: False for n in range(1, 6)}
                st.rerun()

# ---------------------------------------------------------------------------
# BARRA DE ESTADO GLOBAL (siempre visible al pie)
# ---------------------------------------------------------------------------
st.divider()
pasos_ok = sum(st.session_state.paso_ok.values())
st.progress(pasos_ok / 5, text=f"Pipeline: {pasos_ok}/5 pasos completados")
