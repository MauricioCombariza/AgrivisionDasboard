import streamlit as st
import pandas as pd
import logging
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_connection import conectar_logistica

# --- 1. CONFIGURACIÓN DE LOGS Y PÁGINA ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- 2. GESTIÓN DE BASE DE DATOS ---
def conectar_db():
    return conectar_logistica()

# --- 3. CARGA DE MAESTROS (OPTIMIZACIÓN DE MEMORIA) ---
@st.cache_data(ttl=600)
def cargar_maestros():
    """Descarga clientes y precios a RAM para evitar consultas en el loop"""
    conn = conectar_db()
    if not conn: return {}, {}
    
    cursor = conn.cursor(dictionary=True)
    
    # Cargar Clientes
    cursor.execute("SELECT id, nombre_empresa FROM clientes WHERE activo = TRUE")
    clientes = {c['nombre_empresa'].strip().lower(): c['id'] for c in cursor.fetchall()}
    
    # Cargar Precios
    cursor.execute("SELECT cliente_id, tipo_servicio, ambito, precio_unitario FROM precios_cliente WHERE activo = TRUE")
    precios = {(p['cliente_id'], p['tipo_servicio'].lower(), p['ambito'].lower()): float(p['precio_unitario']) for p in cursor.fetchall()}
    
    cursor.close()
    return clientes, precios

# --- 4. INTERFAZ PRINCIPAL ---
st.title("🚀 Procesador de Órdenes Masivo")

if 'procesado_ok' not in st.session_state:
    st.session_state.procesado_ok = False

tab1, tab2 = st.tabs(["📊 Vista Previa y Carga", "📜 Historial"])

with tab1:
    archivo = st.file_uploader("Subir archivo CSV de órdenes", type=['csv'])
    
    if archivo is not None and not st.session_state.procesado_ok:
        try:
            # SOLUCIÓN AL DtypeWarning: Leemos todo como string y low_memory=False
            logger.info("Leyendo CSV con tipos definidos...")
            df = pd.read_csv(archivo, dtype=str, low_memory=False).dropna(how='all')
            
            st.write(f"✅ Se detectaron **{len(df)}** registros en el archivo.")
            st.dataframe(df.head(10), use_container_width=True)

            if st.button("📥 PROCESAR E INSERTAR EN BASE DE DATOS", type="primary"):
                logger.info("Iniciando procesamiento masivo...")
                
                # Cargar datos maestros
                dict_clientes, dict_precios = cargar_maestros()
                
                conn = conectar_db()
                cursor = conn.cursor()
                
                try:
                    # DESACTIVAR AUTOCOMMIT PARA VELOCIDAD MÁXIMA
                    conn.autocommit = False
                    
                    barra = st.progress(0)
                    status = st.empty()
                    errores = []
                    exitos = 0
                    actualizados = 0

                    for i, fila in df.iterrows():
                        try:
                            # 1. Normalización de datos (Conversión manual segura)
                            id_cliente = dict_clientes.get(str(fila['nombre_cliente']).strip().lower())
                            if not id_cliente:
                                raise ValueError(f"Cliente '{fila['nombre_cliente']}' no existe.")

                            tipo_ser = str(fila['tipo_servicio']).lower()
                            c_local = int(float(fila.get('cantidad_local', 0)))
                            c_nac = int(float(fila.get('cantidad_nacional', 0)))
                            num_orden = str(fila['orden'])
                            fecha = fila['fecha_recepcion']

                            # 2. Búsqueda de precios en memoria
                            p_local = dict_precios.get((id_cliente, tipo_ser, 'bogota'), 0.0)
                            p_nac = dict_precios.get((id_cliente, tipo_ser, 'nacional'), 0.0)

                            v_total = (c_local * p_local) + (c_nac * p_nac)

                            # 3. Verificar si la orden ya existe
                            cursor.execute("SELECT id FROM ordenes WHERE numero_orden = %s", (num_orden,))
                            existente = cursor.fetchone()

                            if existente:
                                # Actualizar cantidad_local y cantidad_nacional
                                cursor.execute("""
                                    UPDATE ordenes
                                    SET cantidad_local = %s, cantidad_nacional = %s,
                                        cantidad_recibido_local = %s, cantidad_recibido_nacional = %s,
                                        valor_total = %s
                                    WHERE id = %s
                                """, (c_local, c_nac, c_local, c_nac, v_total, existente[0]))
                                actualizados += 1
                            else:
                                # Insertar nueva orden
                                cursor.execute("""
                                    INSERT INTO ordenes (numero_orden, cliente_id, fecha_recepcion, tipo_servicio,
                                    cantidad_local, cantidad_nacional,
                                    cantidad_recibido_local, cantidad_recibido_nacional,
                                    valor_total, estado)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'activa')
                                """, (num_orden, id_cliente, fecha, tipo_ser, c_local, c_nac, c_local, c_nac, v_total))
                                exitos += 1

                        except Exception as e_fila:
                            errores.append(f"Fila {i+2}: {str(e_fila)}")

                        # Actualizar barra cada 10 registros
                        if i % 10 == 0:
                            barra.progress((i + 1) / len(df))
                    
                    # 4. ÚNICO COMMIT AL FINAL (Aquí se guarda todo de golpe)
                    conn.commit()
                    logger.info(f"Carga finalizada. Nuevos: {exitos}, Actualizados: {actualizados}, Errores: {len(errores)}")

                    st.session_state.procesado_ok = True
                    st.success(f"📦 Procesamiento finalizado. {exitos} nuevas insertadas, {actualizados} actualizadas.")
                    
                    if errores:
                        with st.expander("Ver advertencias/errores"):
                            for err in errores: st.warning(err)
                    
                    # Forzar recarga para limpiar memoria
                    st.rerun()

                except Exception as e_db:
                    conn.rollback()
                    st.error(f"Error crítico: {e_db}")
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

# --- 5. LOG DE CONSOLA PARA TRAZABILIDAD ---
logger.info("Script ejecutado correctamente.")