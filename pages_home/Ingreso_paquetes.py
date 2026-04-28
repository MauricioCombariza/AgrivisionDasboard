import streamlit as st
import pandas as pd
import sys
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

# Configurar sys.path para importar utils
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from utils.sectorization import sectorizar_inicial, sectorizar_con_correcciones
from utils.export import to_csv, to_excel


def _conectar_local():
    """Conexión al imile local usando credenciales del .env."""
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST_IMILE", "localhost"),
            user=os.getenv("DB_USER_IMILE", "root"),
            password=os.getenv("DB_PASSWORD_IMILE", ""),
            database=os.getenv("DB_NAME_IMILE", "imile"),
        )
    except mysql.connector.Error as e:
        st.error(f"No se pudo conectar al imile local: {e}")
        return None


def _guardar_en_bd_local(df: pd.DataFrame):
    """
    Inserta o actualiza los registros de df en paquetes (imile local).
    df debe tener columnas: serial, nombre, telefono, direccion, f_emi.
    Retorna (ok, fallidos).
    """
    conn = _conectar_local()
    if conn is None:
        return 0, len(df)

    sql = """
        REPLACE INTO paquetes (serial, f_emi, nombre, telefono, direccion)
        VALUES (%s, %s, %s, %s, %s)
    """
    ok = 0
    fail = 0
    try:
        cur = conn.cursor()
        for _, row in df.iterrows():
            try:
                cur.execute(sql, (
                    str(row['serial']),
                    str(row['f_emi']),
                    str(row.get('nombre', '')),
                    str(row.get('telefono', '')),
                    str(row.get('direccion', '')),
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

# Nombres alternativos aceptados por columna interna
COL_ALIASES = {
    'serial':    ['Waybill number', 'Número de Guía'],
    'nombre':    ["Recipient's name", 'El nombre del destinatario'],
    'telefono':  ['Customer phone', 'Teléfono entrante'],
    'direccion': ['Address2', 'Dirección detallada del destinatario'],
}


def _resolver_col_map(df_columns):
    """Devuelve {col_excel: col_interna} eligiendo el alias presente en df_columns."""
    col_map = {}
    faltantes = []
    for interno, aliases in COL_ALIASES.items():
        encontrado = next((a for a in aliases if a in df_columns), None)
        if encontrado:
            col_map[encontrado] = interno
        else:
            faltantes.append(f"{interno} (esperado: {' o '.join(aliases)})")
    return col_map, faltantes

# Inicializar estados de sesión
for key, default in [
    ('ip_df_base', None),
    ('ip_df_final', None),
    ('ip_df_sin_sector', pd.DataFrame()),
    ('ip_correcciones', {}),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def main():
    st.title("Sistema de Gestión de Paquetes")

    tab1, tab2 = st.tabs(["Subir bases", "Procesar y Exportar"])

    with tab1:
        mostrar_subida_bases()

    with tab2:
        mostrar_procesamiento_exportacion()


def mostrar_subida_bases():
    st.title("Subir bases")

    uploaded_file = st.file_uploader("Elige un archivo Excel", type="xlsx")

    if uploaded_file is None:
        return

    try:
        df_raw = pd.read_excel(uploaded_file, engine='openpyxl')
    except Exception as e:
        st.error(f"Error al leer el archivo Excel: {e}")
        return

    st.success("Archivo cargado correctamente")
    st.dataframe(df_raw)

    fecha_entrega = st.date_input("Selecciona la fecha de entrega (f_emi)")

    if st.button("Guardar base localmente"):
        if df_raw.empty:
            st.warning("El archivo Excel está vacío.")
            return

        # Renombrar columnas al estándar interno (acepta nombres en inglés o español)
        col_map, faltantes = _resolver_col_map(df_raw.columns)
        if faltantes:
            st.error(f"**Columnas requeridas no encontradas ({len(faltantes)}):**")
            for col in faltantes:
                st.markdown(f"- `{col}`")
            st.info(f"**Columnas que tiene el archivo ({len(df_raw.columns)}):**\n\n" +
                    "\n".join(f"- `{c}`" for c in df_raw.columns))
            return

        df = df_raw[list(col_map.keys())].rename(columns=col_map).copy()
        df['serial'] = df['serial'].astype(str)
        df['f_emi'] = fecha_entrega.strftime('%Y-%m-%d')

        st.session_state.ip_df_base = df
        st.session_state.ip_df_final = None
        st.session_state.ip_df_sin_sector = pd.DataFrame()
        st.session_state.ip_correcciones = {}

        with st.spinner("Guardando en BD local…"):
            ok, fail = _guardar_en_bd_local(df)

        if fail == 0:
            st.success(f"Base guardada: {ok} registros insertados en imile local.")
        else:
            st.warning(f"Guardados: {ok} | Fallidos: {fail}")


def mostrar_procesamiento_exportacion():
    st.title("Procesar y Exportar Datos")

    if st.session_state.ip_df_base is None:
        st.info("Primero carga una base en la pestaña «Subir bases».")
        return

    st.caption(f"Base cargada: {len(st.session_state.ip_df_base)} registros")

    # ── Sectorización inicial ──────────────────────────────────────────────────
    if st.button("Iniciar proceso de sectorización"):
        with st.spinner("Procesando direcciones..."):
            df_proc, df_sin = sectorizar_inicial(st.session_state.ip_df_base)

        st.session_state.ip_df_final = df_proc
        st.session_state.ip_df_sin_sector = df_sin
        st.session_state.ip_correcciones = {}

        sectorizados = len(df_proc) - len(df_sin)
        st.success(f"Sectorizados: {sectorizados} / {len(df_proc)}")

    # ── Corrección manual ──────────────────────────────────────────────────────
    if not st.session_state.ip_df_sin_sector.empty:
        st.warning(
            f"{len(st.session_state.ip_df_sin_sector)} direcciones no pudieron sectorizarse. "
            "Corrígelas en la tabla:"
        )
        edited = st.data_editor(
            st.session_state.ip_df_sin_sector,
            num_rows="dynamic",
            key="ip_editor"
        )
        st.session_state.ip_correcciones = {
            row['serial']: row['direccion']
            for _, row in edited.iterrows()
        }

        if st.button("Reintentar con correcciones", key="btn_reintentar"):
            with st.spinner("Reintentando con correcciones..."):
                df_act, df_sin_act = sectorizar_con_correcciones(
                    st.session_state.ip_df_base,
                    st.session_state.ip_correcciones,
                )

            st.session_state.ip_df_final = df_act
            st.session_state.ip_df_sin_sector = df_sin_act
            st.session_state.ip_correcciones = {}

            if df_sin_act.empty:
                st.success("Todas las direcciones fueron sectorizadas exitosamente.")
            else:
                st.warning(f"Quedan {len(df_sin_act)} sin sector:")
                st.dataframe(df_sin_act)

    elif st.session_state.ip_df_final is not None:
        st.success("Todas las direcciones están sectorizadas.")

    # ── Exportar ───────────────────────────────────────────────────────────────
    df_final = st.session_state.ip_df_final
    if df_final is not None and not df_final.empty:
        st.subheader("Exportar datos")
        col1, col2 = st.columns(2)

        with col1:
            st.download_button(
                label="Descargar CSV",
                data=to_csv(df_final),
                file_name="paquetes_sectorizados.csv",
                mime="text/csv",
            )

        with col2:
            st.download_button(
                label="Descargar Excel",
                data=to_excel(df_final),
                file_name="paquetes_sectorizados.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


if __name__ == "__main__":
    main()
