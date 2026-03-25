import streamlit as st
import pandas as pd
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

# Titulo de la pagina
st.title("Agrupacion por Escaner")

# Conexion a BD para mapeo de clientes
@st.cache_resource
def conectar_db():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="logistica"
        )
        return conn
    except Exception as e:
        st.error(f"Error conectando a BD local: {e}")
        return None

def nueva_conexion():
    """Conexion fresca (sin cache) para operaciones de escritura"""
    try:
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="logistica"
        )
    except Exception:
        return None

# Ruta del archivo CSV
ruta_archivo = '/mnt/c/Users/mcomb/Desktop/Carvajal/python/basesHisto.csv'

# Cargar datos
@st.cache_data(ttl=300)  # Recarga CSV cada 5 minutos para detectar cambios
def cargar_datos():
    if os.path.exists(ruta_archivo):
        df = pd.read_csv(ruta_archivo, low_memory=False)
        return df
    else:
        return None

# Cargar mapeos existentes
def cargar_mapeos(conn):
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT nombre_csv, nombre_bd FROM mapeo_clientes")
        mapeos = {m['nombre_csv'].upper(): m['nombre_bd'] for m in cursor.fetchall()}
        cursor.close()
        return mapeos
    except:
        return {}

# Cargar clientes de la BD
def cargar_clientes_bd(conn):
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, nombre_empresa FROM clientes WHERE activo = TRUE ORDER BY nombre_empresa")
        clientes = cursor.fetchall()
        cursor.close()
        return clientes
    except:
        return []

# Guardar mapeo
def guardar_mapeo(conn, nombre_csv, nombre_bd, cliente_id):
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO mapeo_clientes (nombre_csv, nombre_bd, cliente_id)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE nombre_bd = %s, cliente_id = %s
        """, (nombre_csv, nombre_bd, cliente_id, nombre_bd, cliente_id))
        conn.commit()
        cursor.close()
        return True
    except Exception as e:
        st.error(f"Error guardando mapeo: {e}")
        return False

# Cargar precios de mensajero por cliente (costo_mensajero_entrega/devolucion)
def cargar_precios_mensajero(conn):
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                c.nombre_empresa, pc.costo_mensajero_entrega, pc.costo_mensajero_devolucion
            FROM precios_cliente pc
            JOIN clientes c ON pc.cliente_id = c.id
            WHERE pc.activo = TRUE AND pc.ambito = 'bogota' AND pc.zona IS NULL
        """)
        rows = cursor.fetchall()
        cursor.close()
        precios = {}
        for p in rows:
            key = p['nombre_empresa'].upper().strip()
            if key not in precios:
                precios[key] = {'entrega': 0, 'devolucion': 0}
            if p['costo_mensajero_entrega']:
                nuevo = float(p['costo_mensajero_entrega'])
                if precios[key]['entrega'] == 0 or nuevo < precios[key]['entrega']:
                    precios[key]['entrega'] = nuevo
            if p['costo_mensajero_devolucion']:
                nuevo = float(p['costo_mensajero_devolucion'])
                if nuevo > precios[key]['devolucion']:
                    precios[key]['devolucion'] = nuevo
        return precios
    except:
        return {}

# Cargar personal activo (codigo -> id, nombre)
def cargar_personal_bd(conn):
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT codigo, id, nombre_completo FROM personal WHERE activo = TRUE")
        personal = {m['codigo']: {'id': m['id'], 'nombre': m['nombre_completo']} for m in cursor.fetchall()}
        cursor.close()
        return personal
    except:
        return {}

# ============================================
# FUNCION DE SINCRONIZACION RAPIDA
# ============================================
def sincronizar_periodo(df_periodo, conn_sync):
    """Procesa un DataFrame de un periodo y lo registra en gestiones_mensajero.
    Aplica: mapeo clientes, reasignacion 0999, dedup seriales, agrupacion, precios.
    Retorna dict con estadísticas."""

    mapeos = cargar_mapeos(conn_sync)
    precios_mensajero = cargar_precios_mensajero(conn_sync)
    personal_bd = cargar_personal_bd(conn_sync)

    # Planillas marcadas como revisadas → NO se modifican por sincronización
    try:
        _cur_rev = conn_sync.cursor()
        _cur_rev.execute("SELECT lot_esc FROM planillas_revisadas")
        planillas_revisadas_set = {r[0] for r in _cur_rev.fetchall()}
        _cur_rev.close()
    except Exception:
        planillas_revisadas_set = set()

    df_p = df_periodo.copy()

    # Preparar columnas
    df_p['cod_men'] = (
        df_p['cod_men'].fillna(0).astype(str)
        .str.replace(r'[^\d]', '', regex=True)  # elimina chars no-dígito (ej. '}')
        .replace('', '0')
        .astype(int).astype(str).str.zfill(4)
    )
    df_p['lot_esc'] = df_p['lot_esc'].fillna(0).astype(int)
    df_p['orden'] = df_p['orden'].fillna(0).astype(int)
    if 'cod_sec' not in df_p.columns:
        df_p['cod_sec'] = ''
    else:
        df_p['cod_sec'] = df_p['cod_sec'].fillna('').astype(str)

    # Aplicar mapeo de clientes
    def aplicar_mapeo(nombre):
        nombre_upper = str(nombre).upper().strip()
        if nombre_upper in mapeos:
            return mapeos[nombre_upper]
        return nombre
    df_p['no_entidad'] = df_p['no_entidad'].apply(aplicar_mapeo)

    # Eliminar seriales duplicados
    df_p = df_p.drop_duplicates(subset=['serial'], keep='first')

    # Reasignar codigo 0999
    lotes_con_0999 = df_p[df_p['cod_men'] == '0999']['lot_esc'].unique()
    for lote in lotes_con_0999:
        codigos_en_lote = df_p[df_p['lot_esc'] == lote]['cod_men'].unique()
        if len(codigos_en_lote) == 2 and '0999' in codigos_en_lote:
            otro_codigo = [c for c in codigos_en_lote if c != '0999'][0]
            df_p.loc[(df_p['lot_esc'] == lote) & (df_p['cod_men'] == '0999'), 'cod_men'] = otro_codigo

    # Agrupar
    columnas_agrupacion = ['f_esc', 'cod_men', 'lot_esc', 'orden', 'mot_esc', 'no_entidad']
    resultado = df_p.groupby(columnas_agrupacion, as_index=False).agg(total_serial=('serial', 'count'))

    # Calcular valores
    def calc_valor(row):
        cliente = str(row['no_entidad']).upper().strip()
        mot = str(row['mot_esc']).lower().strip()
        tipo = 'entrega' if 'entrega' in mot else 'devolucion'
        return precios_mensajero.get(cliente, {}).get(tipo, 0)

    resultado['valor_unitario'] = resultado.apply(calc_valor, axis=1)
    resultado['valor_total'] = resultado['valor_unitario'] * resultado['total_serial']
    resultado['mensajero_id'] = resultado['cod_men'].apply(lambda x: personal_bd.get(x, {}).get('id', None))

    # Registrar en BD
    from datetime import date as date_cls
    cursor_reg = conn_sync.cursor()
    insertados = 0
    actualizados = 0
    errores = []

    for _, row in resultado.iterrows():
        try:
            lot_esc_val = str(row['lot_esc'])

            # Saltar planillas marcadas como revisadas
            if lot_esc_val in planillas_revisadas_set:
                continue

            orden_val = str(row['orden'])
            tipo_gestion = row['mot_esc']
            cliente = row['no_entidad']
            cod_men_val = row['cod_men']

            cursor_reg.execute("""
                SELECT id FROM gestiones_mensajero
                WHERE lot_esc = %s AND orden = %s AND tipo_gestion = %s
                AND cliente = %s AND cod_mensajero = %s
            """, (lot_esc_val, orden_val, tipo_gestion, cliente, cod_men_val))
            existente = cursor_reg.fetchone()

            if existente:
                # AND editado_manualmente = 0 protege registros con candado manual
                cursor_reg.execute("""
                    UPDATE gestiones_mensajero
                    SET total_seriales = %s, valor_unitario = %s, valor_total = %s
                    WHERE id = %s AND editado_manualmente = 0
                """, (int(row['total_serial']), float(row['valor_unitario']),
                      float(row['valor_total']), existente[0]))
                if cursor_reg.rowcount > 0:
                    actualizados += 1
            else:
                m_id = row['mensajero_id'] if pd.notna(row['mensajero_id']) else None
                cursor_reg.execute("""
                    INSERT INTO gestiones_mensajero
                    (fecha_escaner, cod_mensajero, mensajero_id, lot_esc, orden,
                     tipo_gestion, cliente, total_seriales, valor_unitario, valor_total,
                     fecha_registro, cod_sec)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (row['f_esc'], cod_men_val, m_id, lot_esc_val, orden_val,
                      tipo_gestion, cliente, int(row['total_serial']),
                      float(row['valor_unitario']), float(row['valor_total']),
                      date_cls.today(), None))
                insertados += 1
        except Exception as e_row:
            errores.append(str(e_row))

    conn_sync.commit()
    cursor_reg.close()

    return {
        'seriales_csv': len(df_p),
        'grupos': len(resultado),
        'insertados': insertados,
        'actualizados': actualizados,
        'errores': errores
    }


# Tabs principales
tab1, tab2 = st.tabs(["📊 Agrupacion Escaner", "📦 Ingreso Masivo Paquetes"])

# ============================================
# TAB 1: AGRUPACION POR ESCANER
# ============================================
with tab1:
    df = cargar_datos()

    if df is None:
        st.error(f"No se encontro el archivo en: {ruta_archivo}")
        st.stop()

    st.success(f"Archivo cargado correctamente. Total de registros: {len(df):,}")

    # Filtrar solo registros con fecha valida (formato AAAA.MM.DD)
    df = df[df['f_esc'].str.match(r'^\d{4}\.\d{2}\.\d{2}$', na=False)].copy()

    # Extraer anos unicos del campo f_esc (formato AAAA.MM.DD)
    df['anio_esc'] = df['f_esc'].str[:4]
    df['mes_esc'] = df['f_esc'].str[5:7]

    # =====================================================
    # SELECTOR DE AÑO
    # =====================================================
    anos_disponibles = sorted(df['anio_esc'].dropna().unique(), reverse=True)
    anio_seleccionado = st.selectbox(
        "Selecciona el Ano:",
        options=anos_disponibles,
        index=0 if anos_disponibles else None
    )

    df_anio = df[df['anio_esc'] == anio_seleccionado].copy() if anio_seleccionado else pd.DataFrame()

    # =====================================================
    # SINCRONIZACION RAPIDA
    # =====================================================
    st.markdown("### Sincronizacion Rapida con BD")

    fechas_pendientes = []
    conn_sync = nueva_conexion()
    if conn_sync:
        try:
            cursor_sync = conn_sync.cursor(dictionary=True)

            # Fechas del CSV para el año seleccionado
            fechas_csv = df_anio.groupby('f_esc').agg(
                seriales_csv=('serial', 'count')
            ).reset_index()

            # Fechas en BD filtradas por el año seleccionado
            cursor_sync.execute("""
                SELECT
                    fecha_escaner,
                    SUM(total_seriales) as seriales_bd
                FROM gestiones_mensajero
                WHERE fecha_escaner LIKE %s
                GROUP BY fecha_escaner
            """, (f"{anio_seleccionado}.%",))
            fechas_bd = {r['fecha_escaner']: int(r['seriales_bd']) for r in cursor_sync.fetchall()}
            cursor_sync.close()

            # Comparar a nivel de fecha individual
            fechas_estado = []
            for _, row in fechas_csv.iterrows():
                fecha = row['f_esc']
                csv_count = int(row['seriales_csv'])
                bd_count = fechas_bd.get(fecha, 0)
                diferencia = csv_count - bd_count

                if diferencia > 0:
                    estado = "Pendiente"
                    fechas_pendientes.append(fecha)
                elif diferencia == 0:
                    estado = "OK"
                else:
                    estado = "OK (otras fuentes)"

                fechas_estado.append({
                    'Fecha': fecha,
                    'Seriales CSV': csv_count,
                    'Seriales BD': bd_count,
                    'Diferencia': diferencia,
                    'Estado': estado
                })

            df_estado = pd.DataFrame(fechas_estado)
            st.dataframe(df_estado, use_container_width=True, hide_index=True)

            if fechas_pendientes:
                total_diferencia = df_estado[df_estado['Estado'] == 'Pendiente']['Diferencia'].sum()

                # Clave unica para evitar re-sincronizar las mismas fechas en loop
                sync_key = "sync_done_" + "_".join(sorted(fechas_pendientes))

                if sync_key not in st.session_state:
                    st.info(f"Sincronizando automaticamente {len(fechas_pendientes)} fechas pendientes ({total_diferencia:,} seriales de diferencia)...")

                    cargar_datos.clear()
                    df_fresh = cargar_datos()

                    barra_sync = st.progress(0)
                    total_insertados = 0
                    total_actualizados = 0
                    total_errores = []

                    for idx, fecha in enumerate(fechas_pendientes):
                        df_fecha = df_fresh[df_fresh['f_esc'] == fecha].copy()

                        if not df_fecha.empty:
                            conn_periodo = nueva_conexion()
                            if conn_periodo:
                                stats = sincronizar_periodo(df_fecha, conn_periodo)
                                total_insertados += stats['insertados']
                                total_actualizados += stats['actualizados']
                                total_errores.extend(stats['errores'])
                                st.caption(f"  {fecha}: +{stats['insertados']} nuevos, {stats['actualizados']} actualizados")
                                try:
                                    conn_periodo.close()
                                except:
                                    pass

                        barra_sync.progress((idx + 1) / len(fechas_pendientes))

                    barra_sync.progress(1.0)
                    st.success(f"Sincronizacion completada: {total_insertados} insertados | {total_actualizados} actualizados")

                    if total_errores:
                        with st.expander(f"Ver {len(total_errores)} errores"):
                            for err in total_errores[:20]:
                                st.warning(err)

                    st.session_state[sync_key] = True
                    st.rerun()
                else:
                    st.success("Fechas sincronizadas en esta sesion. Las diferencias restantes se deben a la deduplicacion de seriales.")
            else:
                st.success(f"Todas las fechas de {anio_seleccionado} estan sincronizadas con la BD")

        except Exception as e:
            st.error(f"Error en sincronizacion: {e}")
            import traceback
            st.code(traceback.format_exc())

    st.divider()

    # =====================================================
    # SELECTOR DE FECHAS A PROCESAR (independiente del sync)
    # =====================================================
    st.markdown("### Seleccionar Fechas a Procesar")

    df_filtrado = pd.DataFrame()  # inicializar para evitar NameError
    todas_las_fechas = sorted(df_anio['f_esc'].unique(), reverse=True)

    # Pre-seleccionar fechas pendientes si las hay, sino dejar vacío
    default_fechas = fechas_pendientes if fechas_pendientes else []

    fechas_seleccionadas = st.multiselect(
        "Fechas a procesar (puedes seleccionar cualquier fecha, incluso las ya sincronizadas):",
        options=todas_las_fechas,
        default=default_fechas
    )

    if not fechas_seleccionadas:
        st.info("Selecciona una o más fechas arriba para procesar y gestionar mensajeros.")
    else:
        df_filtrado = df_anio[df_anio['f_esc'].isin(fechas_seleccionadas)].copy()
        st.info(f"Procesando {len(fechas_seleccionadas)} fechas seleccionadas — {len(df_filtrado):,} registros")

    if fechas_seleccionadas and not df_filtrado.empty:

        # Agrupacion jerarquica: f_esc > cod_men > lot_esc > orden
        # Nota: cod_sec se excluye de la agrupacion para que todos los seriales de la misma planilla se sumen
        columnas_agrupacion = ['f_esc', 'cod_men', 'lot_esc', 'orden', 'mot_esc', 'no_entidad']

        # Verificar que existan las columnas necesarias (cod_sec es opcional para compatibilidad)
        columnas_requeridas = ['f_esc', 'cod_men', 'lot_esc', 'orden', 'mot_esc', 'no_entidad', 'serial']
        columnas_faltantes = [col for col in columnas_requeridas if col not in df_filtrado.columns]
        if columnas_faltantes:
            st.error(f"Columnas faltantes en el CSV: {columnas_faltantes}")

        # Llenar cod_men vacios con 999, convertir a entero y luego a texto de 4 digitos
        df_filtrado['cod_men'] = (
            df_filtrado['cod_men'].fillna(0).astype(str)
            .str.replace(r'[^\d]', '', regex=True)  # elimina chars no-dígito (ej. '}')
            .replace('', '0')
            .astype(int).astype(str).str.zfill(4)
        )

        # Convertir lot_esc y orden a enteros (sin decimales)
        df_filtrado['lot_esc'] = df_filtrado['lot_esc'].fillna(0).astype(int)
        df_filtrado['orden'] = df_filtrado['orden'].fillna(0).astype(int)

        # Manejar cod_sec (opcional para compatibilidad)
        if 'cod_sec' not in df_filtrado.columns:
            df_filtrado['cod_sec'] = ''
        else:
            df_filtrado['cod_sec'] = df_filtrado['cod_sec'].fillna('').astype(str)

        # === SISTEMA DE MAPEO DE CLIENTES ===
        conn = conectar_db()

        if conn:
            st.divider()
            st.markdown("### Mapeo de Clientes")

            # Cargar mapeos y clientes
            mapeos = cargar_mapeos(conn)
            clientes_bd = cargar_clientes_bd(conn)
            clientes_nombres = {c['nombre_empresa'].upper(): c for c in clientes_bd}

            # Obtener clientes unicos del CSV
            clientes_csv = df_filtrado['no_entidad'].dropna().unique()

            # Identificar clientes no mapeados
            clientes_sin_mapear = []
            for cliente in clientes_csv:
                cliente_upper = cliente.upper().strip()
                # Verificar si ya esta mapeado o existe en BD
                if cliente_upper not in mapeos and cliente_upper not in clientes_nombres:
                    clientes_sin_mapear.append(cliente)

            if clientes_sin_mapear:
                st.warning(f"Se encontraron {len(clientes_sin_mapear)} clientes sin mapear")

                # Mostrar tabla de mapeo
                with st.expander("Configurar mapeo de clientes", expanded=True):
                    opciones_clientes = ["-- Seleccionar --"] + [c['nombre_empresa'] for c in clientes_bd]

                    # Inicializar session state para mapeos pendientes
                    if 'mapeos_pendientes' not in st.session_state:
                        st.session_state.mapeos_pendientes = {}

                    for cliente_csv in clientes_sin_mapear:
                        col_a, col_b, col_c = st.columns([2, 2, 1])

                        with col_a:
                            st.text_input("Cliente CSV", value=cliente_csv, disabled=True, key=f"csv_{cliente_csv}")

                        with col_b:
                            seleccion = st.selectbox(
                                "Mapear a",
                                options=opciones_clientes,
                                key=f"map_{cliente_csv}"
                            )

                        with col_c:
                            st.write("")  # Espaciador
                            st.write("")
                            if seleccion != "-- Seleccionar --":
                                if st.button("Guardar", key=f"btn_{cliente_csv}"):
                                    cliente_bd = next((c for c in clientes_bd if c['nombre_empresa'] == seleccion), None)
                                    if cliente_bd:
                                        if guardar_mapeo(conn, cliente_csv.upper().strip(), seleccion, cliente_bd['id']):
                                            st.success(f"Mapeo guardado: {cliente_csv} -> {seleccion}")
                                            st.rerun()

                    st.divider()

                    # Boton para guardar todos los mapeos seleccionados
                    if st.button("Guardar todos los mapeos", type="primary"):
                        guardados = 0
                        for cliente_csv in clientes_sin_mapear:
                            seleccion = st.session_state.get(f"map_{cliente_csv}", "-- Seleccionar --")
                            if seleccion != "-- Seleccionar --":
                                cliente_bd = next((c for c in clientes_bd if c['nombre_empresa'] == seleccion), None)
                                if cliente_bd:
                                    if guardar_mapeo(conn, cliente_csv.upper().strip(), seleccion, cliente_bd['id']):
                                        guardados += 1
                        if guardados > 0:
                            st.success(f"Se guardaron {guardados} mapeos")
                            st.rerun()
            else:
                st.success("Todos los clientes estan mapeados correctamente")

            # Mostrar mapeos existentes
            if mapeos:
                with st.expander("Ver mapeos guardados"):
                    df_mapeos = pd.DataFrame([
                        {"Cliente CSV": k, "Cliente BD": v}
                        for k, v in mapeos.items()
                    ])
                    st.dataframe(df_mapeos, use_container_width=True, hide_index=True)

            # Aplicar mapeos al dataframe
            def aplicar_mapeo(nombre):
                nombre_upper = str(nombre).upper().strip()
                if nombre_upper in mapeos:
                    return mapeos[nombre_upper]
                return nombre

            df_filtrado['no_entidad_original'] = df_filtrado['no_entidad']
            df_filtrado['no_entidad'] = df_filtrado['no_entidad'].apply(aplicar_mapeo)

            st.divider()

        # =====================================================
        # VALIDACION DE SERIALES REPETIDOS
        # =====================================================
        st.markdown("### Validacion de Seriales")

        total_antes = len(df_filtrado)

        # Buscar seriales duplicados
        seriales_duplicados = df_filtrado[df_filtrado.duplicated(subset=['serial'], keep=False)]

        if not seriales_duplicados.empty:
            # Contar cuantos seriales unicos estan repetidos
            seriales_unicos_repetidos = seriales_duplicados['serial'].nunique()
            total_filas_duplicadas = len(seriales_duplicados)

            st.warning(f"Se encontraron {seriales_unicos_repetidos} seriales repetidos ({total_filas_duplicadas} filas afectadas). Se eliminaran los duplicados.")

            with st.expander("Ver seriales duplicados encontrados", expanded=False):
                # Mostrar detalle de los duplicados
                df_duplicados_detalle = seriales_duplicados[['serial', 'f_esc', 'cod_men', 'lot_esc', 'orden', 'mot_esc', 'no_entidad']].sort_values('serial')
                st.dataframe(df_duplicados_detalle, use_container_width=True)

            # Eliminar duplicados, quedarse solo con el primer registro de cada serial
            df_filtrado = df_filtrado.drop_duplicates(subset=['serial'], keep='first')

            total_despues = len(df_filtrado)
            eliminados = total_antes - total_despues

            st.info(f"Se eliminaron {eliminados} registros duplicados. Total seriales unicos: {total_despues}")
        else:
            st.success(f"No hay seriales repetidos. Total seriales unicos: {df_filtrado['serial'].nunique()}")

        st.divider()

        # =====================================================
        # REASIGNAR SERIALES DE CODIGO 0999
        # =====================================================
        st.markdown("### Reasignacion de Codigo 0999")

        # Identificar lotes que tienen exactamente 2 cod_men y uno es 0999
        lotes_con_0999 = df_filtrado[df_filtrado['cod_men'] == '0999']['lot_esc'].unique()
        lotes_reasignados = 0
        seriales_reasignados = 0

        for lote in lotes_con_0999:
            # Obtener todos los cod_men de este lote
            codigos_en_lote = df_filtrado[df_filtrado['lot_esc'] == lote]['cod_men'].unique()

            # Solo procesar si tiene exactamente 2 codigos y uno es 0999
            if len(codigos_en_lote) == 2 and '0999' in codigos_en_lote:
                # Obtener el otro codigo (el que no es 0999)
                otro_codigo = [c for c in codigos_en_lote if c != '0999'][0]

                # Contar seriales a reasignar
                seriales_a_reasignar = len(df_filtrado[(df_filtrado['lot_esc'] == lote) & (df_filtrado['cod_men'] == '0999')])

                # Reasignar: cambiar cod_men de 0999 al otro codigo
                df_filtrado.loc[(df_filtrado['lot_esc'] == lote) & (df_filtrado['cod_men'] == '0999'), 'cod_men'] = otro_codigo

                lotes_reasignados += 1
                seriales_reasignados += seriales_a_reasignar

        if lotes_reasignados > 0:
            st.info(f"Se reasignaron {seriales_reasignados} seriales de codigo 0999 en {lotes_reasignados} lotes")

            with st.expander("Ver lotes que aun tienen codigo 0999", expanded=False):
                # Mostrar lotes que quedaron con 0999 (los que tenian solo 0999 o mas de 2 codigos)
                lotes_restantes_0999 = df_filtrado[df_filtrado['cod_men'] == '0999']['lot_esc'].unique()
                if len(lotes_restantes_0999) > 0:
                    st.write(f"Lotes que mantienen codigo 0999: {len(lotes_restantes_0999)}")
                    df_0999_restante = df_filtrado[df_filtrado['cod_men'] == '0999'].groupby('lot_esc').agg(
                        seriales=('serial', 'count'),
                        codigos_en_lote=('cod_men', lambda x: ', '.join(df_filtrado[df_filtrado['lot_esc'] == x.name]['cod_men'].unique()))
                    ).reset_index()
                    st.dataframe(df_0999_restante, use_container_width=True)
                else:
                    st.success("No quedan registros con codigo 0999")
        else:
            # Verificar si hay registros con 0999
            total_0999 = len(df_filtrado[df_filtrado['cod_men'] == '0999'])
            if total_0999 > 0:
                st.info(f"Hay {total_0999} seriales con codigo 0999 que no se reasignaron (lotes con solo 0999 o mas de 2 codigos)")
            else:
                st.success("No hay registros con codigo 0999")

        st.divider()

        # Agrupar datos
        resultado = df_filtrado.groupby(columnas_agrupacion, as_index=False).agg(
            total_serial=('serial', 'count')
        )

        # Ordenar para facilitar la lectura
        resultado = resultado.sort_values(['f_esc', 'cod_men', 'lot_esc', 'orden'])

        # Mostrar resultados
        st.markdown("### Resultado de la Agrupacion")
        st.dataframe(resultado, use_container_width=True)

        # Estadisticas resumidas
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("Total Grupos", len(resultado))
        with col_b:
            st.metric("Total Seriales", resultado['total_serial'].sum())
        with col_c:
            st.metric("Fechas Unicas", resultado['f_esc'].nunique())

        # Exportar a CSV
        st.markdown("### Exportar Resultado")

        nombre_archivo = f"agrupacion_{anio_seleccionado}_pendientes.csv"

        csv_data = resultado.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Descargar CSV",
            data=csv_data,
            file_name=nombre_archivo,
            mime="text/csv"
        )

        # =====================================================
        # REGISTRAR GESTIONES EN BASE DE DATOS
        # =====================================================
        st.divider()
        st.markdown("### Registrar Gestiones en Base de Datos")

        conn_gest = conectar_db()
        if conn_gest:
            # Cargar precios y personal
            precios_mensajero = cargar_precios_mensajero(conn_gest)
            personal_bd = cargar_personal_bd(conn_gest)

            # Calcular valores para cada fila del resultado
            df_gestiones = resultado.copy()

            def calcular_valor_unitario(row):
                cliente = str(row['no_entidad']).upper().strip()
                mot = str(row['mot_esc']).lower().strip()
                tipo = 'entrega' if 'entrega' in mot else 'devolucion'
                return precios_mensajero.get(cliente, {}).get(tipo, 0)

            df_gestiones['valor_unitario'] = df_gestiones.apply(calcular_valor_unitario, axis=1)
            df_gestiones['valor_total'] = df_gestiones['valor_unitario'] * df_gestiones['total_serial']
            df_gestiones['mensajero_nombre'] = df_gestiones['cod_men'].apply(
                lambda x: personal_bd.get(x, {}).get('nombre', 'Sin asignar')
            )
            df_gestiones['mensajero_id'] = df_gestiones['cod_men'].apply(
                lambda x: personal_bd.get(x, {}).get('id', None)
            )

            # Mostrar preview con valores calculados
            df_preview = df_gestiones[[
                'f_esc', 'cod_men', 'mensajero_nombre', 'lot_esc', 'orden',
                'mot_esc', 'no_entidad', 'total_serial', 'valor_unitario', 'valor_total'
            ]].copy()

            st.dataframe(df_preview, use_container_width=True)

            # Metricas
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                st.metric("Total Gestiones", len(df_gestiones))
            with col_m2:
                st.metric("Total Seriales", int(df_gestiones['total_serial'].sum()))
            with col_m3:
                st.metric("Valor Total", f"${df_gestiones['valor_total'].sum():,.0f}")

            # Advertencias
            sin_precio = df_gestiones[df_gestiones['valor_unitario'] == 0]['no_entidad'].unique()
            if len(sin_precio) > 0:
                st.warning(f"Clientes sin precio configurado (valor $0): {list(sin_precio)}")

            sin_mensajero = df_gestiones[df_gestiones['mensajero_nombre'] == 'Sin asignar']['cod_men'].unique()
            if len(sin_mensajero) > 0:
                st.info(f"Codigos de mensajero sin asignar en BD: {list(sin_mensajero)}")

            # Selector de fecha de registro
            from datetime import date
            fecha_registro = st.date_input("Fecha de registro", value=date.today(), key="fecha_reg_agrup")

            # Boton para registrar
            if st.button("Registrar Gestiones en BD", type="primary", key="btn_registrar_gestiones"):
                try:
                    cursor_reg = conn_gest.cursor()
                    insertados = 0
                    actualizados = 0
                    omitidos_rev = 0
                    errores_reg = []

                    # Cargar planillas revisadas para no sobreescribirlas
                    try:
                        _cur_rev2 = conn_gest.cursor()
                        _cur_rev2.execute("SELECT lot_esc FROM planillas_revisadas")
                        _planillas_rev_reg = {r[0] for r in _cur_rev2.fetchall()}
                        _cur_rev2.close()
                    except Exception:
                        _planillas_rev_reg = set()

                    barra = st.progress(0)
                    total_filas = len(df_gestiones)

                    for i, (_, row) in enumerate(df_gestiones.iterrows()):
                        try:
                            lot_esc_val = str(row['lot_esc'])
                            orden_val = str(row['orden'])
                            tipo_gestion = row['mot_esc']
                            cliente = row['no_entidad']
                            cod_men_val = row['cod_men']

                            # Saltar planillas marcadas como revisadas
                            if lot_esc_val in _planillas_rev_reg:
                                omitidos_rev += 1
                                continue

                            # Verificar si ya existe
                            cursor_reg.execute("""
                                SELECT id FROM gestiones_mensajero
                                WHERE lot_esc = %s AND orden = %s AND tipo_gestion = %s
                                AND cliente = %s AND cod_mensajero = %s
                            """, (lot_esc_val, orden_val, tipo_gestion, cliente, cod_men_val))

                            existente = cursor_reg.fetchone()

                            if existente:
                                # Actualizar registro existente (respetar candado manual)
                                cursor_reg.execute("""
                                    UPDATE gestiones_mensajero
                                    SET total_seriales = %s, valor_unitario = %s, valor_total = %s
                                    WHERE id = %s AND editado_manualmente = 0
                                """, (
                                    int(row['total_serial']),
                                    float(row['valor_unitario']),
                                    float(row['valor_total']),
                                    existente[0]
                                ))
                                if cursor_reg.rowcount > 0:
                                    actualizados += 1
                            else:
                                # Insertar nuevo registro
                                m_id = row['mensajero_id'] if pd.notna(row['mensajero_id']) else None
                                cod_sec_val = None  # cod_sec ya no se usa en la agrupacion

                                cursor_reg.execute("""
                                    INSERT INTO gestiones_mensajero
                                    (fecha_escaner, cod_mensajero, mensajero_id, lot_esc, orden,
                                     tipo_gestion, cliente, total_seriales, valor_unitario, valor_total,
                                     fecha_registro, cod_sec)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """, (
                                    row['f_esc'],
                                    cod_men_val,
                                    m_id,
                                    lot_esc_val,
                                    orden_val,
                                    tipo_gestion,
                                    cliente,
                                    int(row['total_serial']),
                                    float(row['valor_unitario']),
                                    float(row['valor_total']),
                                    fecha_registro,
                                    cod_sec_val
                                ))
                                insertados += 1

                        except Exception as e_row:
                            errores_reg.append(f"Fila {i+1}: {e_row}")

                        if i % 10 == 0:
                            barra.progress((i + 1) / total_filas)

                    conn_gest.commit()
                    barra.progress(1.0)

                    msg_reg = f"Registros insertados: {insertados} | Actualizados: {actualizados}"
                    if omitidos_rev > 0:
                        msg_reg += f" | {omitidos_rev} omitido(s) por planilla revisada 🔒"
                    st.success(msg_reg)
                    if errores_reg:
                        with st.expander(f"Ver {len(errores_reg)} errores"):
                            for err in errores_reg:
                                st.warning(err)

                except Exception as e_reg:
                    conn_gest.rollback()
                    st.error(f"Error al registrar gestiones: {e_reg}")
        else:
            st.error("No se pudo conectar a la BD para registrar gestiones")

# ============================================
# TAB 2: INGRESO MASIVO DE PAQUETES
# ============================================

# Funciones para mapeo DA en BD
def cargar_mapeo_da(conn):
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT nombre_da, cod_mensajero FROM mapeo_da ORDER BY nombre_da")
        mapeos = {m['nombre_da']: m['cod_mensajero'] for m in cursor.fetchall()}
        cursor.close()
        return mapeos
    except:
        return {}

def guardar_mapeo_da(conn, nombre_da, cod_mensajero):
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO mapeo_da (nombre_da, cod_mensajero)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE cod_mensajero = %s
        """, (nombre_da, cod_mensajero, cod_mensajero))
        conn.commit()
        cursor.close()
        return True
    except Exception as e:
        st.error(f"Error guardando mapeo DA: {e}")
        return False

def eliminar_mapeo_da(conn, nombre_da):
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM mapeo_da WHERE nombre_da = %s", (nombre_da,))
        conn.commit()
        cursor.close()
        return True
    except Exception as e:
        st.error(f"Error eliminando mapeo DA: {e}")
        return False

with tab2:
    st.subheader("Ingreso Masivo de Ordenes de Paquetes")
    st.info("Carga un archivo Excel con las entregas y genera un CSV en formato de agrupacion")

    # Conexion a BD
    conn_da = conectar_db()

    # Mapeo de DA a cod_men desde BD
    st.markdown("### Configuracion de Mapeo DA -> Codigo Mensajero")

    if conn_da:
        mapeo_da_bd = cargar_mapeo_da(conn_da)

        with st.expander("Ver/Editar mapeo de DA", expanded=False):
            # Mostrar mapeos actuales
            if mapeo_da_bd:
                df_mapeo_da = pd.DataFrame([
                    {"DA": k, "Codigo": v}
                    for k, v in mapeo_da_bd.items()
                ])
                st.dataframe(df_mapeo_da, use_container_width=True, hide_index=True)
            else:
                st.info("No hay mapeos configurados")

            st.divider()

            # Agregar nuevo mapeo
            st.markdown("#### Agregar/Actualizar mapeo")
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                nuevo_da = st.text_input("Nombre DA", key="nuevo_da")
            with col2:
                nuevo_cod = st.text_input("Codigo (4 dig)", key="nuevo_cod", max_chars=4)
            with col3:
                st.write("")
                st.write("")
                if st.button("Guardar", key="btn_guardar_da"):
                    if nuevo_da and nuevo_cod and len(nuevo_cod) == 4:
                        if guardar_mapeo_da(conn_da, nuevo_da.strip(), nuevo_cod):
                            st.success(f"Guardado: {nuevo_da} -> {nuevo_cod}")
                            st.rerun()
                    else:
                        st.error("Complete nombre y codigo de 4 digitos")

            # Eliminar mapeo
            st.markdown("#### Eliminar mapeo")
            col1, col2 = st.columns([3, 1])
            with col1:
                if mapeo_da_bd:
                    da_eliminar = st.selectbox("Seleccionar DA a eliminar", list(mapeo_da_bd.keys()), key="da_eliminar")
                else:
                    da_eliminar = None
            with col2:
                st.write("")
                st.write("")
                if da_eliminar and st.button("Eliminar", key="btn_eliminar_da"):
                    if eliminar_mapeo_da(conn_da, da_eliminar):
                        st.success(f"Eliminado: {da_eliminar}")
                        st.rerun()
    else:
        mapeo_da_bd = {}
        st.error("No se pudo conectar a la BD")

    st.divider()

    # Configuracion de cliente
    st.markdown("### Configuracion del Cliente")
    col1, col2 = st.columns(2)
    with col1:
        cliente_paquetes = st.text_input("Nombre del Cliente (no_entidad)", value="Imile SAS")
    with col2:
        prefijo_orden = st.text_input("Prefijo de Orden", value="IM")

    st.divider()

    # Carga de archivo
    st.markdown("### Cargar Archivo Excel")
    uploaded_file = st.file_uploader("Selecciona el archivo Excel", type=["xlsx", "xls"])

    if uploaded_file is not None:
        try:
            df_paq = pd.read_excel(uploaded_file)
            df_paq.columns = df_paq.columns.str.strip()

            st.success(f"Archivo cargado: {len(df_paq)} registros")

            # Vista previa
            with st.expander("Vista previa del archivo", expanded=True):
                st.dataframe(df_paq.head(10), use_container_width=True)

            # Verificar columnas requeridas
            columnas_requeridas = ['DA', 'Scan time', 'Waybill No.']
            columnas_faltantes = [col for col in columnas_requeridas if col not in df_paq.columns]

            if columnas_faltantes:
                st.error(f"Columnas faltantes en el archivo: {columnas_faltantes}")
                st.info(f"Columnas disponibles: {list(df_paq.columns)}")
                st.stop()

            st.divider()

            # Procesar datos
            if st.button("Procesar Datos", type="primary"):
                with st.spinner("Procesando..."):
                    # 1. Mapeo de DA a cod_men (desde BD)
                    df_paq['cod_men'] = df_paq['DA'].map(mapeo_da_bd)

                    # Verificar DAs no mapeados
                    das_no_mapeados = df_paq[df_paq['cod_men'].isna()]['DA'].unique()
                    if len(das_no_mapeados) > 0:
                        st.warning(f"DAs sin mapeo: {list(das_no_mapeados)}")
                        st.info("Agregue los mapeos faltantes arriba y vuelva a procesar")

                    # 2. Tratamiento de 'Scan time'
                    df_paq['Scan time'] = pd.to_datetime(df_paq['Scan time'], errors='coerce')

                    # A. Crear 'f_esc' (Formato: AAAA.MM.DD)
                    df_paq['f_esc'] = df_paq['Scan time'].dt.strftime('%Y.%m.%d')

                    # B. Crear 'orden' (Formato: PREFIJO + AAAAMMDD)
                    df_paq['orden'] = df_paq['Scan time'].apply(
                        lambda x: prefijo_orden + x.strftime('%Y%m%d') if pd.notnull(x) else f"{prefijo_orden}_SIN_FECHA"
                    )

                    # 3. Asignacion de columnas adicionales
                    df_paq['lot_esc'] = df_paq['orden']
                    df_paq['mot_esc'] = 'Entrega'
                    df_paq['no_entidad'] = cliente_paquetes

                    # 4. Agrupacion y Conteo Final
                    columnas_agrupacion = ['f_esc', 'cod_men', 'lot_esc', 'orden', 'mot_esc', 'no_entidad']

                    df_final = df_paq.groupby(columnas_agrupacion, as_index=False).agg(
                        total_serial=('Waybill No.', 'count')
                    )

                    # 5. Ordenamiento
                    df_final = df_final.sort_values(['f_esc', 'cod_men', 'lot_esc', 'orden'])

                    # Guardar en session state
                    st.session_state.df_paquetes_resultado = df_final

                    st.success("Procesamiento completado")

            # Mostrar resultado si existe
            if 'df_paquetes_resultado' in st.session_state:
                df_final = st.session_state.df_paquetes_resultado

                st.markdown("### Resultado del Procesamiento")
                st.dataframe(df_final, use_container_width=True)

                # Estadisticas
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Registros", len(df_final))
                with col2:
                    st.metric("Total Seriales", df_final['total_serial'].sum())
                with col3:
                    st.metric("Fechas Unicas", df_final['f_esc'].nunique())
                with col4:
                    st.metric("Mensajeros", df_final['cod_men'].nunique())

                st.divider()

                # Exportar
                st.markdown("### Exportar Resultado")

                # Obtener fecha para nombre de archivo
                if not df_final.empty:
                    primera_fecha = df_final['f_esc'].iloc[0].replace('.', '')
                    nombre_archivo_paq = f"paquetes_{cliente_paquetes.replace(' ', '_')}_{primera_fecha}.csv"
                else:
                    nombre_archivo_paq = "paquetes_resultado.csv"

                csv_data = df_final.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Descargar CSV",
                    data=csv_data,
                    file_name=nombre_archivo_paq,
                    mime="text/csv",
                    key="download_paquetes"
                )

        except Exception as e:
            st.error(f"Error al cargar el archivo: {e}")
