import streamlit as st
import pandas as pd
import logging
from datetime import datetime
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mysql.connector

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- BD ---

def conectar_db():
    try:
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password=os.environ.get("DB_PASSWORD_LOCAL", ""),
            database="logistica",
        )
    except Exception as e:
        st.error(f"Error conectando a BD local: {e}")
        return None


@st.cache_data(ttl=600)
def cargar_maestros():
    """Clientes, precios_cliente y precios_mensajero en RAM."""
    conn = conectar_db()
    if not conn:
        return {}, {}, {}
    cursor = conn.cursor(dictionary=True)

    # {nombre_lower: cliente_id}
    cursor.execute("SELECT id, nombre_empresa FROM clientes WHERE activo = TRUE")
    clientes = {c['nombre_empresa'].strip().lower(): c['id'] for c in cursor.fetchall()}

    # {(cliente_id, tipo_servicio, ambito): precio_unitario}
    cursor.execute("""
        SELECT cliente_id, tipo_servicio, ambito, precio_unitario
        FROM precios_cliente
        WHERE activo = TRUE
    """)
    precios_cli = {
        (p['cliente_id'], p['tipo_servicio'].lower(), p['ambito'].lower()): float(p['precio_unitario'])
        for p in cursor.fetchall()
    }

    # {NOMBRE_UPPER: {'entrega': float, 'devolucion': float}} — costo mensajero desde precios_cliente
    cursor.execute("""
        SELECT c.nombre_empresa, pc.costo_mensajero_entrega, pc.costo_mensajero_devolucion
        FROM precios_cliente pc
        JOIN clientes c ON pc.cliente_id = c.id
        WHERE pc.activo = TRUE AND pc.ambito = 'bogota' AND pc.zona IS NULL
    """)
    precios_men = {}
    for row in cursor.fetchall():
        key = row['nombre_empresa'].upper().strip()
        if key not in precios_men:
            precios_men[key] = {'entrega': 0, 'devolucion': 0}
        if row['costo_mensajero_entrega']:
            v = float(row['costo_mensajero_entrega'])
            if precios_men[key]['entrega'] == 0 or v < precios_men[key]['entrega']:
                precios_men[key]['entrega'] = v
        if row['costo_mensajero_devolucion']:
            v = float(row['costo_mensajero_devolucion'])
            if v > precios_men[key]['devolucion']:
                precios_men[key]['devolucion'] = v

    cursor.close()
    conn.close()
    return clientes, precios_cli, precios_men


# --- UI ---

st.title("🚀 Procesador de Órdenes Masivo")
st.caption(
    "Formato CSV esperado (una fila por serial): "
    "`orden, serial, fecha_recepcion, nombre_cliente, tipo_servicio, ambito`"
)

COLUMNAS_REQUERIDAS = {'orden', 'serial', 'fecha_recepcion', 'nombre_cliente',
                       'tipo_servicio', 'ambito'}

if 'procesado_ok' not in st.session_state:
    st.session_state.procesado_ok = False

tab1, tab2 = st.tabs(["📊 Vista Previa y Carga", "📜 Historial"])

with tab1:
    archivo = st.file_uploader("Subir archivo CSV de órdenes", type=['csv'])

    if archivo is not None and not st.session_state.procesado_ok:
        try:
            df = pd.read_csv(archivo, dtype=str, low_memory=False).dropna(how='all')
            st.write(f"✅ Se detectaron **{len(df)}** registros en el archivo.")
            st.dataframe(df.head(10), use_container_width=True)

            faltantes = COLUMNAS_REQUERIDAS - set(df.columns)
            if faltantes:
                st.error(f"Columnas faltantes: {', '.join(sorted(faltantes))}")
                st.info("Formato: orden, serial, fecha_recepcion, nombre_cliente, tipo_servicio, ambito")
            elif st.button("📥 PROCESAR E INSERTAR EN BASE DE DATOS", type="primary"):
                logger.info("Iniciando procesamiento masivo...")

                dict_clientes, dict_precios_cli, dict_precios_men = cargar_maestros()

                # Normalizar columnas de apoyo
                df['_orden']    = df['orden'].str.strip().str.replace(r'\.0$', '', regex=True)
                df['_es_local'] = df['ambito'].str.lower().str.strip().str.contains('bog', na=False)

                conn = conectar_db()
                if not conn:
                    st.stop()

                try:
                    conn.autocommit = False
                    cursor = conn.cursor()

                    barra    = st.progress(0)
                    errores  = []
                    sg_nuevos = 0
                    total    = len(df)

                    # ── Paso 1: un serial por fila → seriales_gestion (pendiente) ──
                    for i, fila in df.iterrows():
                        try:
                            cliente_nom = str(fila['nombre_cliente']).strip()
                            id_cliente  = dict_clientes.get(cliente_nom.lower())
                            if not id_cliente:
                                raise ValueError(f"Cliente '{cliente_nom}' no existe en BD")

                            serial     = str(fila['serial']).strip()
                            num_orden  = str(fila['_orden'])
                            fecha      = str(fila['fecha_recepcion']).strip()
                            tipo_ser   = str(fila['tipo_servicio']).lower().strip()
                            ambito_val = 'bogota' if fila['_es_local'] else 'nacional'

                            precio_cli = dict_precios_cli.get((id_cliente, tipo_ser, ambito_val), 0.0)
                            precio_men = dict_precios_men.get(
                                cliente_nom.upper().strip(), {}
                            ).get('entrega', 0.0)

                            # INSERT IGNORE: el escáner posterior usará ON DUPLICATE KEY UPDATE
                            # para completar fecha_escaner real, cod_men y planilla de escáner
                            # cuando el serial pase de 'pendiente' a 'Entrega' o 'Devolucion'.
                            cursor.execute("""
                                INSERT IGNORE INTO seriales_gestion
                                    (serial, planilla, orden, fecha_escaner, cod_men, cliente,
                                     tipo_gestion, tipo_envio, ambito,
                                     precio_cliente, precio_mensajero, estado, origen)
                                VALUES (%s, '', %s, %s, '', %s, 'Entrega', %s, %s, %s, %s, 'pendiente', 'manual')
                            """, (serial, num_orden, fecha, cliente_nom,
                                  tipo_ser, ambito_val, precio_cli, precio_men))

                            if cursor.rowcount > 0:
                                sg_nuevos += 1

                        except Exception as e_fila:
                            errores.append(f"Fila {i+2} (serial {fila.get('serial','?')}): {e_fila}")

                        if i % 10 == 0:
                            barra.progress(min((i + 1) / total, 1.0))

                    # ── Paso 2: agrupar por orden → tabla ordenes ──
                    resumen = (
                        df.groupby(['_orden', 'fecha_recepcion', 'nombre_cliente', 'tipo_servicio'])
                        .agg(
                            cantidad_local    =('_es_local', 'sum'),
                            cantidad_nacional  =('_es_local', lambda x: (~x).sum()),
                        )
                        .reset_index()
                    )

                    exitos_ord     = 0
                    actualizados_ord = 0

                    for _, grp in resumen.iterrows():
                        try:
                            cliente_nom = str(grp['nombre_cliente']).strip()
                            id_cliente  = dict_clientes.get(cliente_nom.lower())
                            if not id_cliente:
                                errores.append(f"Orden {grp['_orden']}: cliente no encontrado")
                                continue

                            num_orden = str(grp['_orden'])
                            fecha     = str(grp['fecha_recepcion']).strip()
                            tipo_ser  = str(grp['tipo_servicio']).lower().strip()
                            c_local   = int(grp['cantidad_local'])
                            c_nac     = int(grp['cantidad_nacional'])
                            c_total   = c_local + c_nac
                            p_local   = dict_precios_cli.get((id_cliente, tipo_ser, 'bogota'),   0.0)
                            p_nac     = dict_precios_cli.get((id_cliente, tipo_ser, 'nacional'), 0.0)
                            v_total   = (c_local * p_local) + (c_nac * p_nac)

                            cursor.execute(
                                "SELECT id FROM ordenes WHERE numero_orden = %s", (num_orden,)
                            )
                            existente = cursor.fetchone()

                            if existente:
                                cursor.execute("""
                                    UPDATE ordenes
                                    SET cantidad_local              = %s,
                                        cantidad_nacional           = %s,
                                        cantidad_total              = %s,
                                        cantidad_recibido_local     = %s,
                                        cantidad_recibido_nacional  = %s,
                                        valor_total                 = %s
                                    WHERE id = %s
                                """, (c_local, c_nac, c_total, c_local, c_nac,
                                      v_total, existente[0]))
                                actualizados_ord += 1
                            else:
                                cursor.execute("""
                                    INSERT INTO ordenes
                                        (numero_orden, cliente_id, fecha_recepcion, tipo_servicio,
                                         cantidad_local, cantidad_nacional, cantidad_total,
                                         cantidad_recibido_local, cantidad_recibido_nacional,
                                         valor_total, estado)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'activa')
                                """, (num_orden, id_cliente, fecha, tipo_ser,
                                      c_local, c_nac, c_total,
                                      c_local, c_nac, v_total))
                                exitos_ord += 1

                        except Exception as e_ord:
                            errores.append(f"Orden {grp.get('_orden', '?')}: {e_ord}")

                    conn.commit()
                    barra.progress(1.0)

                    logger.info(
                        f"Carga: órdenes nuevas={exitos_ord}, actualizadas={actualizados_ord}, "
                        f"seriales_gestion={sg_nuevos}, errores={len(errores)}"
                    )
                    st.session_state.procesado_ok = True
                    st.success(
                        f"📦 {exitos_ord} órdenes nuevas · {actualizados_ord} actualizadas — "
                        f"📋 {sg_nuevos} seriales registrados en seriales_gestion"
                    )

                    if errores:
                        with st.expander(f"Ver {len(errores)} advertencias/errores"):
                            for err in errores:
                                st.warning(err)

                    st.rerun()

                except Exception as e_db:
                    conn.rollback()
                    st.error(f"Error crítico: {e_db}")
                    import traceback
                    st.code(traceback.format_exc())
                finally:
                    cursor.close()
                    conn.autocommit = True

        except Exception as e_lectura:
            st.error(f"Error al abrir el CSV: {e_lectura}")

    elif st.session_state.procesado_ok:
        st.balloons()
        st.success("¡El archivo anterior fue cargado con éxito!")
        if st.button("🔄 Cargar nuevo archivo"):
            st.session_state.procesado_ok = False
            st.rerun()

logger.info("Script ejecutado correctamente.")
