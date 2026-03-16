import streamlit as st
import pandas as pd
import numpy as np
import mysql.connector
from datetime import datetime
import io
import subprocess
import tempfile
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine as sa_create_engine

load_dotenv()
from pathlib import Path



def conectar_db():
    """Conecta a la base de datos sin cache para evitar problemas de conexión expirada"""
    try:
        conn = mysql.connector.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database="logistica",
            autocommit=False,
            connect_timeout=10
        )
        return conn
    except Exception as e:
        st.error(f"Error conectando a BD: {e}")
        return None

def obtener_conexion():
    """Obtiene una conexión válida, creando una nueva si es necesario"""
    if 'db_connection' not in st.session_state or st.session_state.db_connection is None:
        st.session_state.db_connection = conectar_db()

    return st.session_state.db_connection

BASES_WEB_URL = "mysql+mysqlconnector://servilla_remoto:Servilla123@186.180.15.66:12539/bases_web"

def clasificar_destino(ciudad):
    """Clasifica destino como local si contiene 'bog', sino nacional"""
    ciudad = str(ciudad).lower().strip()
    return 'local' if 'bog' in ciudad else 'nacional'

@st.cache_resource
def get_bases_web_engine():
    """Crea engine para bases_web (cached a nivel de sesión)"""
    return sa_create_engine(BASES_WEB_URL, pool_pre_ping=True)

def cargar_histo_desde_bd(orden_minima=0):
    """Carga datos de la tabla histo directamente desde bases_web"""
    try:
        engine = get_bases_web_engine()
        query = f"""
            SELECT orden, f_emi, no_entidad, ciudad1, courrier,
                   retorno, ret_esc, serial
            FROM histo
            WHERE CAST(orden AS SIGNED) >= {int(orden_minima)}
            ORDER BY CAST(orden AS SIGNED) DESC
        """
        df = pd.read_sql(query, engine)
        return df, None
    except Exception as e:
        return None, str(e)

def verificar_julia():
    """Verifica si Julia está instalado"""
    try:
        result = subprocess.run(['julia', '--version'],
                              capture_output=True,
                              text=True,
                              timeout=5)
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, "Julia no respondió correctamente"
    except FileNotFoundError:
        return False, "Julia no está instalado o no está en PATH"
    except Exception as e:
        return False, str(e)

def procesar_con_julia(ruta_archivo, orden_minima):
    """Procesa el archivo usando Julia para máximo rendimiento"""
    try:
        # Obtener ruta del script Julia
        script_dir = Path(__file__).parent
        julia_script = script_dir / "Procesador_Ordenes.jl"

        if not julia_script.exists():
            return None, f"No se encontró el script Julia en: {julia_script}"

        # Leer el script y modificar la ruta del archivo
        with open(julia_script, 'r') as f:
            julia_code = f.read()

        # Reemplazar la llamada a procesar_masivo para incluir orden_minima
        julia_code_modified = julia_code.replace(
            'procesar_masivo("/mnt/c/Users/mcomb/Desktop/Carvajal/python/dashboard/pages_home/tu_archivo.csv")',
            f'procesar_masivo("{ruta_archivo}", {orden_minima})'
        )

        # Crear script temporal
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jl', delete=False) as tmp_jl:
            tmp_jl.write(julia_code_modified)
            temp_jl_path = tmp_jl.name

        # Ejecutar Julia con output en tiempo real (combinar stdout y stderr)
        process = subprocess.Popen(
            ['julia', '--threads=auto', temp_jl_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Redirigir stderr a stdout para capturar todo
            text=True,
            bufsize=1
        )

        output_lines = []
        for line in process.stdout:
            output_lines.append(line.strip())
            yield line.strip()

        process.wait()

        # Limpiar archivo temporal
        try:
            os.unlink(temp_jl_path)
        except:
            pass

        if process.returncode == 0:
            # Julia procesó todo exitosamente
            return "success", '\n'.join(output_lines)
        else:
            return None, f"Error en Julia (código {process.returncode}): Ver log para detalles"

    except Exception as e:
        return None, f"Error ejecutando Julia: {str(e)}"

def procesar_dataframe_historico(df, orden_minima):
    """Procesa un DataFrame histórico (puede venir de CSV o BD)"""
    try:
        df = df.copy()

        # Pre-procesamiento de tipos de datos
        df['orden'] = pd.to_numeric(df['orden'], errors='coerce').fillna(0).astype(int)

        # Filtrar por número de orden
        df_filtrado = df[df['orden'] >= orden_minima].copy()

        # Excluir couriers LECTA y PRINDEL (comparación en minúsculas)
        couriers_excluidos = ['lecta', 'prindel']
        if 'courrier' in df_filtrado.columns:
            df_filtrado = df_filtrado[~df_filtrado['courrier'].fillna('').str.lower().str.strip().isin(couriers_excluidos)]

        # Conversión de fecha (soporta formato '2024.01.15' de bases_web y otros)
        df_filtrado['f_emi'] = pd.to_datetime(df_filtrado['f_emi'], errors='coerce')

        # Método eficiente con numpy: crear columnas de conteo condicional
        es_local = df_filtrado['ciudad1'].fillna('').str.contains('bog', case=False, na=False) | df_filtrado['ciudad1'].isna()

        df_filtrado['local'] = np.where(es_local, 1, 0)
        df_filtrado['nacional'] = np.where(~es_local, 1, 0)

        # Agrupación y suma directa
        df_final = df_filtrado.groupby('orden').agg(
            fecha_recepcion=('f_emi', 'first'),
            nombre_cliente=('no_entidad', 'first'),
            cantidad_local=('local', 'sum'),
            cantidad_nacional=('nacional', 'sum')
        ).reset_index()

        # Formato final
        df_final['tipo_servicio'] = 'sobre'
        df_final['fecha_recepcion'] = pd.to_datetime(df_final['fecha_recepcion']).dt.date

        df_final['cantidad_local'] = df_final['cantidad_local'].astype(int)
        df_final['cantidad_nacional'] = df_final['cantidad_nacional'].astype(int)

        df_final = df_final[['orden', 'fecha_recepcion', 'nombre_cliente', 'tipo_servicio', 'cantidad_local', 'cantidad_nacional']]

        return df_final, None
    except Exception as e:
        return None, str(e)

def procesar_archivo_historico(ruta_archivo, orden_minima):
    """Procesa el archivo histórico desde CSV"""
    try:
        df = pd.read_csv(ruta_archivo)
        return procesar_dataframe_historico(df, orden_minima)
    except Exception as e:
        return None, str(e)

def normalizar_nombre_cliente(nombre, mapeo_clientes):
    """Normaliza el nombre del cliente usando el mapeo"""
    nombre_normalizado = str(nombre).strip()

    # Buscar en el mapeo
    for nombre_correcto, variaciones in mapeo_clientes.items():
        if nombre_normalizado in variaciones or nombre_normalizado.lower() in [v.lower() for v in variaciones]:
            return nombre_correcto

    return nombre_normalizado

@st.cache_data(ttl=60, show_spinner=False)
def obtener_clientes_bd(_conn):
    """Obtiene lista de clientes activos de la BD"""
    try:
        cursor = _conn.cursor(dictionary=True)
        cursor.execute("SELECT nombre_empresa FROM clientes WHERE activo = TRUE ORDER BY nombre_empresa")
        result = cursor.fetchall()
        cursor.close()
        return [c['nombre_empresa'] for c in result]
    except Exception as e:
        st.error(f"Error al obtener clientes: {e}")
        return []

def obtener_ordenes_existentes(conn):
    """Obtiene las órdenes ya creadas en la BD"""
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                o.numero_orden,
                o.cantidad_local,
                o.cantidad_nacional,
                c.nombre_empresa,
                o.tipo_servicio
            FROM ordenes o
            JOIN clientes c ON o.cliente_id = c.id
        """)
        ordenes_existentes = cursor.fetchall()
        cursor.close()

        # Crear set de números de orden para comparación rápida
        ordenes_set = {str(o['numero_orden']) for o in ordenes_existentes}

        return ordenes_set, ordenes_existentes
    except Exception as e:
        st.error(f"Error al obtener órdenes existentes: {e}")
        return set(), []

st.title("🔄 Procesador de Órdenes Históricas")

st.info("""
    Esta herramienta procesa el archivo histórico de órdenes y lo prepara para carga masiva:
    - ✅ Clasifica destinos automáticamente (local/nacional)
    - ✅ Agrupa y cuenta cantidades
    - ✅ Normaliza nombres de clientes
    - ✅ Elimina duplicados ya existentes en BD
    - ✅ Genera CSV listo para cargar
""")

conn = obtener_conexion()
if not conn:
    st.stop()

# Crear tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Procesar Archivo",
    "🏢 Mapeo de Clientes",
    "📥 Resultado",
    "📦 Envios Imile",
    "📊 Actualizar Gestiones"
])

# ==============================================================================
# TAB 1: PROCESAR ARCHIVO
# ==============================================================================
with tab1:
    st.subheader("Procesamiento de Archivo Histórico")

    fuente_datos = st.radio(
        "Fuente de datos",
        ["🗄️ Base de Datos (bases_web)", "📄 Archivo CSV"],
        index=0,
        horizontal=True
    )

    col1, col2 = st.columns(2)

    with col1:
        if fuente_datos == "📄 Archivo CSV":
            ruta_archivo = st.text_input(
                "Ruta del Archivo CSV",
                value="/mnt/c/Users/mcomb/Desktop/Carvajal/python/basesHisto.csv"
            )
        else:
            st.info("Se consultará directamente la tabla `histo` en bases_web")
            ruta_archivo = None

    with col2:
        orden_minima = st.number_input(
            "Orden Mínima a Procesar",
            min_value=0,
            value=123273,
            step=1,
            help="Solo se procesarán órdenes >= a este número"
        )

    # Selector de motor de procesamiento
    st.divider()
    col_motor1, col_motor2, col_motor3 = st.columns([1, 2, 1])

    with col_motor1:
        # Verificar si Julia está disponible
        julia_disponible, julia_info = verificar_julia()

    with col_motor2:
        motor = st.radio(
            "Motor de Procesamiento",
            ["Python (Numpy/Pandas - Recomendado)", "Julia (Alto Rendimiento)"],
            index=0,
            help="Python con Numpy es eficiente y confiable. Julia es experimental."
        )

    with col_motor3:
        if julia_disponible:
            st.success("✅ Julia OK")
        else:
            st.error("❌ Julia N/D")

    if not julia_disponible and motor == "Julia (Alto Rendimiento)":
        st.warning(f"⚠️ {julia_info}")
        st.info("Instala Julia desde: https://julialang.org/downloads/")

    if st.button("🚀 Procesar Archivo", type="primary"):
        # Determinar qué motor usar
        usar_julia = motor == "Julia (Alto Rendimiento)" and julia_disponible

        if fuente_datos == "🗄️ Base de Datos (bases_web)":
            st.info("⚙️ Cargando datos desde bases_web...")
            with st.spinner("Consultando base de datos remota..."):
                df_raw, error_bd = cargar_histo_desde_bd(orden_minima)

            if error_bd:
                st.error(f"❌ Error al conectar con bases_web: {error_bd}")
            else:
                st.success(f"✅ {len(df_raw):,} registros cargados desde bases_web")

                with st.spinner("Procesando datos..."):
                    df_procesado, error_proc = procesar_dataframe_historico(df_raw, orden_minima)

                if error_proc:
                    st.error(f"❌ Error al procesar: {error_proc}")
                else:
                    st.success(f"✅ Archivo procesado exitosamente: {len(df_procesado)} registros encontrados")
                    st.info("ℹ️ Se excluyeron automáticamente los couriers LECTA y PRINDEL")

                    st.session_state['df_procesado'] = df_procesado

                    keys_to_clear = ['df_normalizado', 'ordenes_existentes_set', 'ordenes_existentes_list',
                                     'df_nuevas', 'df_duplicadas']
                    for key in keys_to_clear:
                        if key in st.session_state:
                            del st.session_state[key]

                    st.session_state['mapeos_aplicados'] = False
                    st.session_state['force_reprocess'] = False

                    st.markdown("### 👀 Vista Previa del Procesamiento")
                    st.dataframe(df_procesado.tail(50), use_container_width=True)

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Órdenes", len(df_procesado))
                    with col2:
                        total_items = df_procesado['cantidad_local'].sum() + df_procesado['cantidad_nacional'].sum()
                        st.metric("Total Items", f"{total_items:,}")
                    with col3:
                        st.metric("Items Locales", f"{df_procesado['cantidad_local'].sum():,}")
                    with col4:
                        st.metric("Items Nacionales", f"{df_procesado['cantidad_nacional'].sum():,}")

                    st.markdown("### 🏢 Clientes Identificados")
                    clientes_unicos = df_procesado['nombre_cliente'].unique()
                    st.info(f"Se encontraron **{len(clientes_unicos)}** nombres de clientes diferentes")
                    with st.expander("Ver lista completa de clientes"):
                        st.write(sorted(clientes_unicos))

        elif usar_julia:
            # Usar Julia para procesamiento
            st.info("⚙️ Usando motor Julia con multithreading...")
            output_container = st.empty()

            with st.spinner("Procesando con Julia..."):
                try:
                    result_generator = procesar_con_julia(ruta_archivo, orden_minima)
                    output_lines = []

                    # Mostrar output en tiempo real
                    for line in result_generator:
                        output_lines.append(line)
                        output_container.code('\n'.join(output_lines[-15:]))  # Últimas 15 líneas

                    st.success("✅ Procesamiento completado con Julia")

                    with st.expander("📜 Log completo de Julia"):
                        st.code('\n'.join(output_lines))

                    # Cargar el CSV procesado por Julia desde Downloads
                    nombre_archivo = os.path.basename(ruta_archivo)
                    nombre_procesado = nombre_archivo.replace('.csv', '_procesado_julia.csv')
                    ruta_procesada = f"/mnt/c/Users/mcomb/Downloads/{nombre_procesado}"

                    if os.path.exists(ruta_procesada):
                        st.info(f"📂 Cargando archivo procesado: {ruta_procesada}")
                        df_procesado = pd.read_csv(ruta_procesada)

                        # Convertir fecha
                        df_procesado['fecha_recepcion'] = pd.to_datetime(df_procesado['fecha_recepcion']).dt.date

                        # Guardar en session_state
                        st.session_state['df_procesado'] = df_procesado

                        # Limpiar cachés para forzar reprocesamiento en TAB 3
                        keys_to_clear = ['df_normalizado', 'ordenes_existentes_set', 'ordenes_existentes_list',
                                         'df_nuevas', 'df_duplicadas']
                        for key in keys_to_clear:
                            if key in st.session_state:
                                del st.session_state[key]

                        # Resetear flags
                        st.session_state['mapeos_aplicados'] = False
                        st.session_state['force_reprocess'] = False

                        st.success(f"✅ Archivo procesado cargado: {len(df_procesado)} órdenes")
                        st.balloons()

                        # Mostrar estadísticas
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Órdenes", len(df_procesado))
                        with col2:
                            total_items = df_procesado['cantidad_local'].sum() + df_procesado['cantidad_nacional'].sum()
                            st.metric("Total Items", f"{total_items:,}")
                        with col3:
                            st.metric("Items Locales", f"{df_procesado['cantidad_local'].sum():,}")
                        with col4:
                            st.metric("Items Nacionales", f"{df_procesado['cantidad_nacional'].sum():,}")

                        st.info("👉 Ahora vaya a la pestaña **'Resultado'** para mapear clientes y generar el CSV final")
                    else:
                        st.error(f"❌ No se encontró el archivo procesado: {ruta_procesada}")

                except Exception as e:
                    st.error(f"❌ Error al ejecutar Julia: {e}")

        else:
            # Usar Python (Numpy/Pandas) para procesamiento
            st.info("⚙️ Usando motor Python (Numpy/Pandas) - Método optimizado...")

            with st.spinner("Procesando archivo histórico..."):
                # Procesar archivo
                df_procesado, error = procesar_archivo_historico(ruta_archivo, orden_minima)

                if error:
                    st.error(f"Error al procesar archivo: {error}")
                elif df_procesado is not None:
                    st.success(f"✅ Archivo procesado exitosamente: {len(df_procesado)} registros encontrados")
                    st.info("ℹ️ Se excluyeron automáticamente los couriers LECTA y PRINDEL")

                    # Guardar en session_state
                    st.session_state['df_procesado'] = df_procesado

                # Limpiar cachés para forzar reprocesamiento en TAB 3
                keys_to_clear = ['df_normalizado', 'ordenes_existentes_set', 'ordenes_existentes_list',
                                 'df_nuevas', 'df_duplicadas']
                for key in keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]

                # Resetear flags
                st.session_state['mapeos_aplicados'] = False
                st.session_state['force_reprocess'] = False

                # Mostrar preview
                st.markdown("### 👀 Vista Previa del Procesamiento")
                st.dataframe(df_procesado.tail(50), use_container_width=True)

                # Estadísticas
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Órdenes", len(df_procesado))
                with col2:
                    total_items = df_procesado['cantidad_local'].sum() + df_procesado['cantidad_nacional'].sum()
                    st.metric("Total Items", f"{total_items:,}")
                with col3:
                    st.metric("Items Locales", f"{df_procesado['cantidad_local'].sum():,}")
                with col4:
                    st.metric("Items Nacionales", f"{df_procesado['cantidad_nacional'].sum():,}")

                # Clientes únicos
                st.markdown("### 🏢 Clientes Identificados")
                clientes_unicos = df_procesado['nombre_cliente'].unique()
                st.info(f"Se encontraron **{len(clientes_unicos)}** nombres de clientes diferentes")

                with st.expander("Ver lista completa de clientes"):
                    st.write(sorted(clientes_unicos))

# ==============================================================================
# TAB 2: MAPEO DE CLIENTES
# ==============================================================================
with tab2:
    st.subheader("Mapeo de Nombres de Clientes")

    st.info("""
        Configure aquí las variaciones de nombres de clientes para normalizarlos.
        Esto evita crear clientes duplicados por errores tipográficos.
    """)

    # Inicializar mapeo en session_state
    if 'mapeo_clientes' not in st.session_state:
        st.session_state['mapeo_clientes'] = {
            "Distribuidora XYZ": ["DISTRIBUIDORA XYZ", "Distribuidora XYZ S.A.", "Dist XYZ"],
            "Empresa ABC": ["EMPRESA ABC", "Empresa ABC LTDA", "ABC"],
            "Corporación DEF": ["CORPORACION DEF", "Corp DEF", "Corporación DEF S.A.S"]
        }

    st.markdown("### 📋 Configuración de Mapeo")

    # Mostrar mapeo actual
    st.markdown("#### Mapeo Actual:")
    for nombre_correcto, variaciones in st.session_state['mapeo_clientes'].items():
        with st.expander(f"✏️ {nombre_correcto}"):
            st.write("**Variaciones aceptadas:**")
            for var in variaciones:
                st.write(f"- {var}")

    st.divider()

    # Agregar nuevo mapeo
    st.markdown("#### ➕ Agregar Nuevo Mapeo")

    col1, col2 = st.columns(2)

    with col1:
        nombre_correcto = st.text_input(
            "Nombre Correcto del Cliente",
            help="Este será el nombre que se usará en el CSV final"
        )

    with col2:
        variaciones = st.text_area(
            "Variaciones (una por línea)",
            help="Ingrese todas las variaciones posibles, una por línea"
        )

    if st.button("💾 Agregar Mapeo"):
        if nombre_correcto and variaciones:
            variaciones_list = [v.strip() for v in variaciones.split('\n') if v.strip()]
            if nombre_correcto not in st.session_state['mapeo_clientes']:
                st.session_state['mapeo_clientes'][nombre_correcto] = []
            st.session_state['mapeo_clientes'][nombre_correcto].extend(variaciones_list)
            st.session_state['mapeo_clientes'][nombre_correcto] = list(set(st.session_state['mapeo_clientes'][nombre_correcto]))
            st.success(f"✅ Mapeo agregado para '{nombre_correcto}'")
            st.rerun()
        else:
            st.error("Complete ambos campos")

    st.divider()

    # Eliminar mapeo
    st.markdown("#### 🗑️ Eliminar Mapeo")
    if st.session_state['mapeo_clientes']:
        cliente_eliminar = st.selectbox(
            "Seleccione cliente a eliminar",
            list(st.session_state['mapeo_clientes'].keys())
        )
        if st.button("🗑️ Eliminar", type="secondary"):
            del st.session_state['mapeo_clientes'][cliente_eliminar]
            st.success(f"✅ Mapeo eliminado para '{cliente_eliminar}'")
            st.rerun()

    st.divider()

    # Mapeos Interactivos guardados
    st.markdown("#### 🔗 Mapeos Interactivos (Asignaciones Directas)")

    if 'mapeo_interactivo_clientes' in st.session_state and st.session_state['mapeo_interactivo_clientes']:
        st.info(f"Se encontraron **{len(st.session_state['mapeo_interactivo_clientes'])}** mapeos interactivos guardados")

        with st.expander("Ver Mapeos Interactivos"):
            for csv_name, bd_name in st.session_state['mapeo_interactivo_clientes'].items():
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.text(csv_name)
                with col2:
                    st.text(f"→ {bd_name}")
                with col3:
                    if st.button("❌", key=f"del_int_{csv_name}"):
                        del st.session_state['mapeo_interactivo_clientes'][csv_name]
                        st.rerun()

        # Botón para exportar mapeos
        import json

        mapeos_json = json.dumps(st.session_state['mapeo_interactivo_clientes'], indent=2)

        st.download_button(
            label="📥 Exportar Mapeos Interactivos (JSON)",
            data=mapeos_json,
            file_name="mapeos_clientes.json",
            mime="application/json",
            help="Descargue este archivo para guardar sus mapeos permanentemente"
        )

        if st.button("🗑️ Limpiar Todos los Mapeos Interactivos", type="secondary"):
            st.session_state['mapeo_interactivo_clientes'] = {}
            st.success("✅ Todos los mapeos interactivos fueron eliminados")
            st.rerun()
    else:
        st.info("No hay mapeos interactivos guardados. Se crean automáticamente cuando asigna clientes en la pestaña 'Resultado'")

    # Importar mapeos
    st.markdown("##### 📤 Importar Mapeos")
    uploaded_json = st.file_uploader(
        "Cargar archivo de mapeos (JSON)",
        type=['json'],
        help="Cargue un archivo JSON previamente exportado con mapeos"
    )

    if uploaded_json is not None:
        try:
            import json
            mapeos_importados = json.load(uploaded_json)

            if isinstance(mapeos_importados, dict):
                if st.button("✅ Confirmar Importación"):
                    if 'mapeo_interactivo_clientes' not in st.session_state:
                        st.session_state['mapeo_interactivo_clientes'] = {}

                    st.session_state['mapeo_interactivo_clientes'].update(mapeos_importados)
                    st.success(f"✅ Se importaron {len(mapeos_importados)} mapeos exitosamente")
                    st.rerun()

                st.info(f"Archivo válido con {len(mapeos_importados)} mapeos. Haga clic en 'Confirmar Importación' para cargarlos.")
            else:
                st.error("Formato de archivo inválido")
        except Exception as e:
            st.error(f"Error al cargar archivo: {e}")

# ==============================================================================
# TAB 3: RESULTADO
# ==============================================================================
with tab3:
    st.subheader("Generar CSV para Carga Masiva")

    if 'df_procesado' not in st.session_state:
        st.warning("⚠️ Primero debe procesar el archivo en la pestaña 'Procesar Archivo'")
    else:
        st.markdown("### 🔍 Validación y Limpieza")

        # Procesar solo una vez y cachear resultado
        if 'df_normalizado' not in st.session_state or st.session_state.get('force_reprocess', False):
            with st.spinner("Procesando datos..."):
                st.write("**Paso 1:** Normalizando nombres de clientes...")
                df_procesado = st.session_state['df_procesado'].copy()
                df_procesado['nombre_cliente'] = df_procesado['nombre_cliente'].apply(
                    lambda x: normalizar_nombre_cliente(x, st.session_state['mapeo_clientes'])
                )
                st.session_state['df_normalizado'] = df_procesado
                st.success(f"✅ Nombres normalizados usando {len(st.session_state['mapeo_clientes'])} reglas de mapeo")

                # Obtener órdenes existentes
                st.write("**Paso 2:** Verificando órdenes existentes en BD...")
                ordenes_existentes_set, ordenes_existentes_list = obtener_ordenes_existentes(conn)
                st.session_state['ordenes_existentes_set'] = ordenes_existentes_set
                st.session_state['ordenes_existentes_list'] = ordenes_existentes_list
                st.info(f"📦 Se encontraron {len(ordenes_existentes_set)} órdenes ya creadas en la base de datos")

                st.session_state['force_reprocess'] = False
        else:
            # Usar datos cacheados
            df_procesado = st.session_state['df_normalizado']
            ordenes_existentes_set = st.session_state['ordenes_existentes_set']
            ordenes_existentes_list = st.session_state['ordenes_existentes_list']

            st.write("**Paso 1:** ✅ Nombres normalizados (usando caché)")
            st.write("**Paso 2:** ✅ Órdenes verificadas (usando caché)")
            st.info(f"📦 {len(ordenes_existentes_set)} órdenes en base de datos")

        # Filtrar duplicados (cachear resultado)
        if 'df_nuevas' not in st.session_state or st.session_state.get('force_reprocess', False):
            st.write("**Paso 3:** Filtrando duplicados...")

            # Convertir número de orden a string para comparación
            df_procesado['orden_str'] = df_procesado['orden'].astype(str)

            # Filtrar
            df_nuevas = df_procesado[~df_procesado['orden_str'].isin(ordenes_existentes_set)].copy()
            df_duplicadas = df_procesado[df_procesado['orden_str'].isin(ordenes_existentes_set)].copy()

            # Eliminar columna auxiliar
            df_nuevas = df_nuevas.drop('orden_str', axis=1)
            df_duplicadas = df_duplicadas.drop('orden_str', axis=1)

            # Cachear resultados
            st.session_state['df_nuevas'] = df_nuevas
            st.session_state['df_duplicadas'] = df_duplicadas

            st.success(f"✅ Se identificaron {len(df_nuevas)} órdenes nuevas para crear")
            st.warning(f"⚠️ Se excluyeron {len(df_duplicadas)} órdenes duplicadas")
            st.info("ℹ️ **Nota:** Con el nuevo formato, cada orden puede tener cantidades tanto locales como nacionales en un solo registro")
        else:
            # Usar datos cacheados
            df_nuevas = st.session_state['df_nuevas']
            df_duplicadas = st.session_state['df_duplicadas']
            st.write("**Paso 3:** ✅ Duplicados filtrados (usando caché)")
            st.info(f"📊 {len(df_nuevas)} nuevas | {len(df_duplicadas)} duplicadas")

        st.divider()

        # Mostrar resultados
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### ✅ Órdenes Nuevas")
            st.metric("Total", len(df_nuevas))
            if len(df_nuevas) > 0:
                total_items = df_nuevas['cantidad_local'].sum() + df_nuevas['cantidad_nacional'].sum()
                st.metric("Total Items", f"{total_items:,}")
            else:
                st.metric("Total Items", "0")

            if len(df_nuevas) > 0:
                with st.expander("Ver datos"):
                    st.dataframe(df_nuevas, use_container_width=True, hide_index=True)

        with col2:
            st.markdown("### ⚠️ Órdenes Duplicadas (Excluidas)")
            st.metric("Total", len(df_duplicadas))

            if len(df_duplicadas) > 0:
                with st.expander("Ver datos"):
                    st.dataframe(df_duplicadas, use_container_width=True, hide_index=True)

        st.divider()

        # Validar clientes existen en BD
        if len(df_nuevas) > 0:
            st.markdown("### 🏢 Validación de Clientes")

            clientes_bd = obtener_clientes_bd(conn)

            clientes_csv = df_nuevas['nombre_cliente'].unique()
            clientes_no_encontrados = [c for c in clientes_csv if c not in clientes_bd]

            # Inicializar mapeo interactivo en session_state
            if 'mapeo_interactivo_clientes' not in st.session_state:
                st.session_state['mapeo_interactivo_clientes'] = {}

            if clientes_no_encontrados:
                st.error(f"❌ Se encontraron {len(clientes_no_encontrados)} clientes que NO existen en la base de datos")

                st.info("""
                    📋 **Mapeo Interactivo de Clientes**

                    Asigne cada cliente del CSV a un cliente existente en la base de datos.
                    Este mapeo se guardará para futuras cargas.
                """)

                # Crear DataFrame para mapeo interactivo
                st.markdown("#### 🔗 Asignar Clientes")

                # Preparar opciones: agregar opción "No mapear" al inicio
                opciones_bd = ["[No mapear - Crear cliente nuevo]"] + clientes_bd

                # Variable para rastrear si hay cambios
                mapeos_realizados = {}

                # Crear tabla de mapeo
                for idx, cliente_csv in enumerate(clientes_no_encontrados):
                    col1, col2, col3 = st.columns([2, 2, 1])

                    with col1:
                        st.text_input(
                            "Cliente en CSV",
                            value=cliente_csv,
                            disabled=True,
                            key=f"csv_{idx}"
                        )

                    with col2:
                        # Buscar si ya hay un mapeo guardado
                        mapeo_previo = st.session_state['mapeo_interactivo_clientes'].get(cliente_csv)

                        # Si hay mapeo previo, usarlo como default
                        if mapeo_previo and mapeo_previo in opciones_bd:
                            default_index = opciones_bd.index(mapeo_previo)
                        else:
                            default_index = 0

                        cliente_seleccionado = st.selectbox(
                            "Cliente en Base de Datos",
                            opciones_bd,
                            index=default_index,
                            key=f"bd_{idx}",
                            help="Seleccione el cliente correcto de la BD"
                        )

                        if cliente_seleccionado != "[No mapear - Crear cliente nuevo]":
                            mapeos_realizados[cliente_csv] = cliente_seleccionado

                    with col3:
                        # Indicador visual
                        if cliente_csv in st.session_state['mapeo_interactivo_clientes']:
                            st.success("✓ Guardado")
                        else:
                            st.warning("⏳ Nuevo")

                st.divider()

                col1, col2, col3 = st.columns([1, 1, 2])

                with col1:
                    if st.button("💾 Guardar Mapeos", type="primary"):
                        # Actualizar mapeos en session_state
                        st.session_state['mapeo_interactivo_clientes'].update(mapeos_realizados)

                        # También agregar al mapeo de clientes general
                        for cliente_csv, cliente_bd in mapeos_realizados.items():
                            if cliente_bd not in st.session_state['mapeo_clientes']:
                                st.session_state['mapeo_clientes'][cliente_bd] = []
                            if cliente_csv not in st.session_state['mapeo_clientes'][cliente_bd]:
                                st.session_state['mapeo_clientes'][cliente_bd].append(cliente_csv)

                        st.success(f"✅ Se guardaron {len(mapeos_realizados)} mapeos")
                        st.info("🔄 Refresque para aplicar los cambios")

                with col2:
                    if st.button("🔄 Aplicar Mapeos y Regenerar"):
                        # Limpiar cachés para forzar reprocesamiento completo
                        keys_to_clear = ['df_normalizado', 'df_nuevas', 'df_duplicadas']
                        for key in keys_to_clear:
                            if key in st.session_state:
                                del st.session_state[key]

                        # Resetear flags
                        st.session_state['mapeos_aplicados'] = False
                        st.session_state['force_reprocess'] = True

                        st.success("✅ Mapeos guardados. Recargando...")
                        st.rerun()

                with col3:
                    st.metric("Mapeos Guardados", len(st.session_state['mapeo_interactivo_clientes']))

                st.divider()

                # Mostrar mapeos guardados
                if st.session_state['mapeo_interactivo_clientes']:
                    with st.expander("📋 Ver Todos los Mapeos Guardados"):
                        st.markdown("**Mapeos activos:**")
                        for csv_name, bd_name in st.session_state['mapeo_interactivo_clientes'].items():
                            st.write(f"• `{csv_name}` → `{bd_name}`")

                # Aplicar mapeos automáticamente si ya existen (solo una vez)
                if 'mapeos_aplicados' not in st.session_state:
                    st.session_state['mapeos_aplicados'] = False

                if st.session_state['mapeo_interactivo_clientes'] and not st.session_state['mapeos_aplicados']:
                    df_nuevas_copy = df_nuevas.copy()
                    cambios = 0

                    for cliente_csv, cliente_bd in st.session_state['mapeo_interactivo_clientes'].items():
                        if cliente_csv in df_nuevas_copy['nombre_cliente'].values:
                            df_nuevas_copy.loc[df_nuevas_copy['nombre_cliente'] == cliente_csv, 'nombre_cliente'] = cliente_bd
                            cambios += 1

                    if cambios > 0:
                        df_nuevas = df_nuevas_copy
                        st.info(f"ℹ️ Se aplicaron automáticamente {cambios} mapeos guardados")
                        st.session_state['mapeos_aplicados'] = True

                        # Recalcular clientes no encontrados
                        clientes_csv_nuevos = df_nuevas['nombre_cliente'].unique()
                        clientes_no_encontrados = [c for c in clientes_csv_nuevos if c not in clientes_bd]

            # Mostrar estado final de validación
            if not clientes_no_encontrados:
                st.success("✅ Todos los clientes existen en la base de datos o han sido mapeados correctamente")
            else:
                clientes_sin_mapear = [c for c in clientes_no_encontrados if c not in st.session_state['mapeo_interactivo_clientes']]
                if clientes_sin_mapear:
                    st.warning(f"⚠️ Quedan {len(clientes_sin_mapear)} clientes sin mapear. Configure el mapeo arriba.")

            st.divider()

            # Generar CSV para descarga
            st.markdown("### 📥 Descargar CSV para Carga Masiva")

            # Recalcular clientes no encontrados después de mapeos
            clientes_csv_final = df_nuevas['nombre_cliente'].unique()
            clientes_no_encontrados_final = [c for c in clientes_csv_final if c not in clientes_bd]

            if clientes_no_encontrados_final:
                st.warning(f"⚠️ Hay {len(clientes_no_encontrados_final)} clientes sin mapear. Algunas órdenes fallarán al cargar.")

            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                # Convertir a CSV
                csv_buffer = io.StringIO()
                df_nuevas.to_csv(csv_buffer, index=False)
                csv_data = csv_buffer.getvalue()

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                nombre_archivo = f"ordenes_procesadas_{timestamp}.csv"

                st.download_button(
                    label="📥 Descargar CSV de Órdenes Nuevas",
                    data=csv_data,
                    file_name=nombre_archivo,
                    mime="text/csv",
                    type="primary"
                )

            with col2:
                st.metric("Órdenes en CSV", len(df_nuevas))

            with col3:
                total_items_csv = df_nuevas['cantidad_local'].sum() + df_nuevas['cantidad_nacional'].sum()
                st.metric("Items Totales", f"{total_items_csv:,}")

            st.info("""
                💡 **Siguiente paso:**
                1. Descargue el CSV generado
                2. Vaya a: **Órdenes** > **Carga Masiva CSV**
                3. Cargue el archivo descargado
                4. Revise la validación y procese
            """)
        else:
            st.info("ℹ️ No hay órdenes nuevas para procesar. Todas las órdenes ya existen en la base de datos.")

    st.divider()

    # Estadísticas adicionales
    if 'df_procesado' in st.session_state:
        st.markdown("### 📊 Resumen General")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Órdenes Procesadas", len(st.session_state['df_procesado']))
        with col2:
            st.metric("Órdenes Nuevas", len(df_nuevas) if 'df_nuevas' in locals() else 0)
        with col3:
            st.metric("Órdenes Duplicadas", len(df_duplicadas) if 'df_duplicadas' in locals() else 0)
        with col4:
            efectividad = (len(df_nuevas) / len(st.session_state['df_procesado']) * 100) if len(st.session_state['df_procesado']) > 0 and 'df_nuevas' in locals() else 0
            st.metric("% Nuevas", f"{efectividad:.1f}%")

# ==============================================================================
# TAB 4: ENVIOS IMILE
# ==============================================================================
with tab4:
    st.subheader("📦 Procesador de Envíos Imile")

    st.info("""
        Esta herramienta procesa archivos Excel de Imile y genera un archivo de órdenes:
        - ✅ Lee la columna 'Scan time' y 'Waybill No.'
        - ✅ Agrupa por fecha y cuenta envíos
        - ✅ Genera órdenes con formato IM + fecha
        - ✅ Descarga archivo listo para carga
    """)

    # File uploader
    uploaded_file = st.file_uploader(
        "📤 Subir archivo Excel de Imile",
        type=['xlsx', 'xls'],
        help="Suba el archivo Excel que contiene las columnas 'Scan time' y 'Waybill No.'"
    )

    if uploaded_file is not None:
        try:
            # Leer el archivo Excel
            df = pd.read_excel(uploaded_file)

            st.success(f"✅ Archivo cargado exitosamente: {len(df)} registros")

            # Mostrar preview del archivo original
            with st.expander("👀 Vista previa del archivo original"):
                st.dataframe(df.head(20), use_container_width=True)

            # Verificar que existan las columnas necesarias
            if 'Scan time' not in df.columns or 'Waybill No.' not in df.columns:
                st.error("❌ Error: El archivo debe contener las columnas 'Scan time' y 'Waybill No.'")
                st.info(f"Columnas encontradas: {', '.join(df.columns)}")
            else:
                st.divider()

                if st.button("🚀 Procesar Envíos Imile", type="primary"):
                    with st.spinner("Procesando datos..."):
                        try:
                            # 1. Convertir 'Scan time' a datetime y extraer solo la fecha
                            df['fecha_recepcion'] = pd.to_datetime(df['Scan time']).dt.date

                            # 2. Agrupar por fecha para obtener la cantidad (conteo de Waybill No.)
                            df_new = df.groupby('fecha_recepcion')['Waybill No.'].count().reset_index()
                            df_new.columns = ['fecha_recepcion', 'cantidad_local']

                            # 3. Crear las columnas requeridas para carga masiva
                            df_new['orden'] = df_new['fecha_recepcion'].apply(lambda x: "IM" + x.strftime('%Y%m%d'))
                            df_new['nombre_cliente'] = 'Imile SAS'
                            df_new['tipo_servicio'] = 'paquete'
                            df_new['cantidad_nacional'] = 0  # Imile solo opera local

                            # 4. Reordenar las columnas para que coincidan con el formato de carga masiva
                            column_order = ['orden', 'fecha_recepcion', 'nombre_cliente', 'tipo_servicio', 'cantidad_local', 'cantidad_nacional']
                            df_final = df_new[column_order]

                            # Guardar en session_state
                            st.session_state['df_imile_procesado'] = df_final

                            st.success(f"✅ Procesamiento completado: {len(df_final)} registros generados")

                            # Mostrar estadísticas
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Registros Originales", len(df))
                            with col2:
                                st.metric("Días Procesados", len(df_final))
                            with col3:
                                st.metric("Total Paquetes", df_final['cantidad_local'].sum())

                            # Mostrar preview del resultado
                            st.markdown("### 📊 Vista Previa del Resultado")
                            st.dataframe(df_final, use_container_width=True, hide_index=True)

                        except Exception as e:
                            st.error(f"❌ Error al procesar el archivo: {str(e)}")
                            st.exception(e)

        except Exception as e:
            st.error(f"❌ Error al leer el archivo: {str(e)}")

    # Botón de descarga (solo si hay datos procesados)
    if 'df_imile_procesado' in st.session_state:
        st.divider()
        st.markdown("### 📥 Descargar Archivo Procesado")

        df_imile = st.session_state['df_imile_procesado']

        # Convertir a CSV
        csv_buffer = io.StringIO()
        df_imile.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()

        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            st.download_button(
                label="📥 Descargar imileEnvios.csv",
                data=csv_data,
                file_name="imileEnvios.csv",
                mime="text/csv",
                type="primary"
            )

        with col2:
            st.metric("Registros", len(df_imile))

        with col3:
            st.metric("Total Paquetes", df_imile['cantidad_local'].sum())

        st.info("""
            💡 **Archivo listo para descargar:**
            - El archivo contiene las columnas: orden, fecha_recepcion, nombre_cliente, tipo_servicio, cantidad_local, cantidad_nacional
            - Formato CSV (.csv)
            - Listo para carga masiva
        """)

# ==============================================================================
# TAB 5: ACTUALIZAR GESTIONES
# ==============================================================================
with tab5:
    st.subheader("📊 Actualizar Gestiones desde CSV Base")

    st.info("""
        Suba el archivo CSV base (con columna 'retorno') para actualizar el estado de las órdenes:
        - ✅ Cuenta entregas, devoluciones y envíos en lleva por orden
        - ✅ Omite órdenes que ya están al 100%
        - ✅ Ajusta entregas si la gestión supera el 100%
        - ✅ Actualiza directamente la base de datos
    """)

    def mapear_estado_gestion(row):
        """Mapea retorno/ret_esc a estado de gestión"""
        retorno = row.get('retorno', '')
        ret_esc = row.get('ret_esc', '') if 'ret_esc' in row.index else ''

        r = str(retorno).strip() if pd.notna(retorno) else ''
        e = str(ret_esc).strip() if pd.notna(ret_esc) else ''

        # ret_esc tiene prioridad (estado del escáner)
        if e in ('e', 'E', 'T'):
            return 'Entregado'
        if e in ('o', 'd', 'D'):
            return 'Devolución'

        # Luego revisar retorno
        if r in ('l', 'k', 'p'):
            return 'En Lleva'
        elif r in ('e', 'E', 'T'):
            return 'Entregado'
        elif r in ('o', 'd', 'D'):
            return 'Devolución'
        else:
            return 'Otro'

    def normalizar_orden_gestion(val):
        """Normaliza número de orden"""
        s = str(val).strip()
        if s.endswith('.0'):
            s = s[:-2]
        return s

    fuente_gestiones = st.radio(
        "Fuente de datos para gestiones",
        ["🗄️ Base de Datos (bases_web)", "📄 Archivo CSV"],
        index=0,
        horizontal=True,
        key="fuente_gestiones"
    )

    if fuente_gestiones == "📄 Archivo CSV":
        ruta_base = st.text_input(
            "Ruta del archivo CSV base",
            value="/mnt/c/Users/mcomb/Desktop/Carvajal/python/basesHisto.csv",
            key="ruta_csv_gestiones"
        )
    else:
        ruta_base = None
        orden_min_gestiones = st.number_input(
            "Orden Mínima (dejar en 0 para todas las órdenes activas)",
            min_value=0,
            value=0,
            step=1,
            key="orden_min_gestiones",
            help="Filtra registros de histo con orden >= este valor"
        )
        st.info("Se consultará directamente la tabla `histo` en bases_web")

    if st.button("🚀 Procesar y Actualizar Gestiones", type="primary", key="btn_procesar_gestiones"):
        if fuente_gestiones == "📄 Archivo CSV" and not os.path.exists(ruta_base):
            st.error(f"No se encontró el archivo: {ruta_base}")
        else:
            try:
                if fuente_gestiones == "🗄️ Base de Datos (bases_web)":
                    with st.spinner("Cargando datos desde bases_web..."):
                        df_gest, error_bd_gest = cargar_histo_desde_bd(orden_min_gestiones)
                    if error_bd_gest:
                        st.error(f"❌ Error al conectar con bases_web: {error_bd_gest}")
                        st.stop()
                    df_gest = df_gest.astype(str)
                    st.success(f"✅ {len(df_gest):,} registros cargados desde bases_web")
                else:
                    with st.spinner("Leyendo archivo CSV (puede tardar por el tamaño)..."):
                        df_gest = pd.read_csv(ruta_base, low_memory=False, encoding='latin1', dtype=str)

                if 'retorno' not in df_gest.columns or 'orden' not in df_gest.columns:
                    st.error("El CSV debe contener las columnas 'retorno' y 'orden'")
                else:
                    # Excluir couriers LECTA y PRINDEL
                    if 'courrier' in df_gest.columns:
                        antes = len(df_gest)
                        couriers_excluidos = ['lecta', 'prindel']
                        df_gest = df_gest[~df_gest['courrier'].fillna('').str.lower().str.strip().isin(couriers_excluidos)]
                        excluidos = antes - len(df_gest)
                        if excluidos > 0:
                            st.info(f"Se excluyeron {excluidos} registros de couriers LECTA/PRINDEL")

                    st.info(f"Archivo cargado: {len(df_gest)} registros. Procesando estados...")

                    # Eliminar seriales duplicados (mantener solo la primera aparición)
                    if 'serial' in df_gest.columns:
                        total_antes = len(df_gest)
                        df_gest = df_gest.drop_duplicates(subset=['serial'], keep='first')
                        duplicados = total_antes - len(df_gest)
                        if duplicados > 0:
                            st.warning(f"Se eliminaron {duplicados} seriales duplicados. Registros únicos: {len(df_gest)}")
                    else:
                        st.warning("No se encontró columna 'serial'. No se pudo verificar duplicados.")

                    # Mapear estados
                    df_gest['estado_item'] = df_gest.apply(mapear_estado_gestion, axis=1)
                    df_gest['orden_norm'] = df_gest['orden'].apply(normalizar_orden_gestion)

                    # Agrupar por orden y estado (solo los que interesan)
                    estados_interes = ['Entregado', 'Devolución', 'En Lleva']
                    df_filtrado = df_gest[df_gest['estado_item'].isin(estados_interes)]

                    resumen = df_filtrado.groupby(['orden_norm', 'estado_item']).size().unstack(fill_value=0).reset_index()

                    for col in estados_interes:
                        if col not in resumen.columns:
                            resumen[col] = 0

                    resumen = resumen.rename(columns={
                        'Entregado': 'entregas_csv',
                        'Devolución': 'devoluciones_csv',
                        'En Lleva': 'en_lleva_csv'
                    })

                    total_por_orden = df_gest.groupby('orden_norm').size().reset_index(name='total_csv')
                    resumen = resumen.merge(total_por_orden, on='orden_norm', how='left')

                    st.success(f"CSV procesado: {len(df_gest)} registros, {len(resumen)} órdenes con gestión")

                    # Obtener órdenes de la BD
                    conn_gest = conectar_db()
                    if conn_gest:
                        cursor_gest = conn_gest.cursor(dictionary=True)
                        cursor_gest.execute("""
                            SELECT id, numero_orden, cantidad_total,
                                   COALESCE(cantidad_entregados_local, 0) + COALESCE(cantidad_entregados_nacional, 0) as entregas_actuales,
                                   COALESCE(cantidad_devolucion_local, 0) + COALESCE(cantidad_devolucion_nacional, 0) as devoluciones_actuales,
                                   COALESCE(cantidad_en_lleva, 0) as en_lleva_actual
                            FROM ordenes
                            WHERE estado = 'activa'
                        """)
                        ordenes_bd = cursor_gest.fetchall()
                        cursor_gest.close()

                        ordenes_dict = {}
                        for o in ordenes_bd:
                            key = normalizar_orden_gestion(o['numero_orden'])
                            ordenes_dict[key] = o

                        # Cruzar datos
                        actualizaciones = []
                        omitidas_100 = []
                        ajustadas = []
                        no_encontradas = []

                        for _, row in resumen.iterrows():
                            orden_num = row['orden_norm']
                            orden_bd = ordenes_dict.get(orden_num)

                            if not orden_bd:
                                no_encontradas.append(orden_num)
                                continue

                            cantidad_total = int(orden_bd['cantidad_total'] or 0)
                            entregas_act = int(orden_bd['entregas_actuales'])
                            devol_act = int(orden_bd['devoluciones_actuales'])

                            if cantidad_total > 0 and (entregas_act + devol_act) >= cantidad_total:
                                omitidas_100.append({
                                    'orden': orden_num,
                                    'total': cantidad_total,
                                    'entregas': entregas_act,
                                    'devoluciones': devol_act
                                })
                                continue

                            nuevas_entregas = int(row.get('entregas_csv', 0))
                            nuevas_devol = int(row.get('devoluciones_csv', 0))
                            nuevas_lleva = int(row.get('en_lleva_csv', 0))

                            ajustada = False
                            if cantidad_total > 0 and (nuevas_entregas + nuevas_devol) > cantidad_total:
                                nuevas_entregas = cantidad_total - nuevas_devol
                                if nuevas_entregas < 0:
                                    nuevas_entregas = 0
                                    nuevas_devol = cantidad_total
                                ajustada = True

                            gestion_total = nuevas_entregas + nuevas_devol
                            porcentaje = (gestion_total / cantidad_total * 100) if cantidad_total > 0 else 0

                            registro = {
                                'orden_id': orden_bd['id'],
                                'orden': orden_num,
                                'total': cantidad_total,
                                'entregas': nuevas_entregas,
                                'devoluciones': nuevas_devol,
                                'en_lleva': nuevas_lleva,
                                'porcentaje': porcentaje
                            }
                            actualizaciones.append(registro)
                            if ajustada:
                                ajustadas.append(registro)

                        # Ejecutar UPDATE directo (sin botón anidado)
                        if actualizaciones:
                            conn_upd = conectar_db()
                            if conn_upd:
                                try:
                                    cursor_upd = conn_upd.cursor()
                                    conn_upd.autocommit = False
                                    barra = st.progress(0)
                                    exitos = 0
                                    errores_upd = []

                                    for i, reg in enumerate(actualizaciones):
                                        try:
                                            cursor_upd.execute("""
                                                UPDATE ordenes
                                                SET cantidad_entregados_local = %s,
                                                    cantidad_entregados_nacional = 0,
                                                    cantidad_devolucion_local = %s,
                                                    cantidad_devolucion_nacional = 0,
                                                    cantidad_en_lleva = %s
                                                WHERE id = %s
                                            """, (reg['entregas'], reg['devoluciones'], reg['en_lleva'], reg['orden_id']))
                                            exitos += 1
                                        except Exception as e_row:
                                            errores_upd.append(f"Orden {reg['orden']}: {e_row}")
                                        if i % 10 == 0:
                                            barra.progress((i + 1) / len(actualizaciones))

                                    conn_upd.commit()
                                    barra.progress(1.0)

                                except Exception as e_db:
                                    conn_upd.rollback()
                                    st.error(f"Error en BD: {e_db}")
                                finally:
                                    cursor_upd.close()
                                    conn_upd.close()

                        # Mostrar resumen
                        st.markdown("---")
                        st.markdown("### 📊 Resultado")

                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Órdenes actualizadas", len(actualizaciones))
                        with col2:
                            st.metric("Omitidas (100%)", len(omitidas_100))
                        with col3:
                            st.metric("Ajustadas (>100%)", len(ajustadas))
                        with col4:
                            st.metric("No encontradas en BD", len(no_encontradas))

                        if actualizaciones:
                            st.success(f"✅ {len(actualizaciones)} órdenes actualizadas en la base de datos")
                            with st.expander("Ver detalle de actualizaciones"):
                                df_preview = pd.DataFrame(actualizaciones)
                                df_preview = df_preview[['orden', 'total', 'entregas', 'devoluciones', 'en_lleva', 'porcentaje']]
                                df_preview['porcentaje'] = df_preview['porcentaje'].apply(lambda x: f"{x:.1f}%")
                                df_preview.columns = ['Orden', 'Total', 'Entregas', 'Devoluciones', 'En Lleva', '% Gestión']
                                st.dataframe(df_preview, use_container_width=True, hide_index=True)
                        else:
                            st.info("No hay órdenes para actualizar")

                        if omitidas_100:
                            with st.expander(f"Ver {len(omitidas_100)} órdenes omitidas (ya al 100%)"):
                                df_omit = pd.DataFrame(omitidas_100)
                                st.dataframe(df_omit, use_container_width=True, hide_index=True)

                        if ajustadas:
                            with st.expander(f"Ver {len(ajustadas)} órdenes ajustadas (>100%)"):
                                st.warning("Se redujeron las entregas para que entregas + devoluciones = total")
                                df_ajust = pd.DataFrame(ajustadas)
                                df_ajust = df_ajust[['orden', 'total', 'entregas', 'devoluciones']]
                                st.dataframe(df_ajust, use_container_width=True, hide_index=True)

                        if no_encontradas:
                            with st.expander(f"Ver {len(no_encontradas)} órdenes no encontradas en BD"):
                                st.write(no_encontradas[:50])

                        conn_gest.close()

            except Exception as e_gest:
                st.error(f"Error al procesar CSV: {e_gest}")
                import traceback
                st.code(traceback.format_exc())

    # --- Sección Imile: sincronizar desde gestiones_mensajero ---
    st.markdown("---")
    st.markdown("### 📦 Sincronizar Órdenes Imile SAS")
    st.info("Imile no usa CSV base. Sus entregas vienen de gestiones_mensajero. "
            "Si las entregas superan el recibido, se actualiza el recibido y el valor de venta.")

    if st.button("🔄 Sincronizar y Actualizar Imile", type="primary", key="btn_sync_imile"):
        conn_imile = conectar_db()
        if conn_imile:
            try:
                cursor_im = conn_imile.cursor(dictionary=True)

                # 1. Obtener entregas por orden de Imile desde gestiones_mensajero
                cursor_im.execute("""
                    SELECT orden, SUM(total_seriales) as total_entregas
                    FROM gestiones_mensajero
                    WHERE UPPER(TRIM(cliente)) = 'IMILE SAS'
                    GROUP BY orden
                """)
                imile_gestiones = cursor_im.fetchall()

                # 2. Obtener órdenes Imile de la BD
                cursor_im.execute("""
                    SELECT o.id, o.numero_orden, o.cantidad_local, o.cantidad_nacional,
                           o.cantidad_total, o.valor_total, o.cliente_id, o.tipo_servicio
                    FROM ordenes o
                    JOIN clientes c ON o.cliente_id = c.id
                    WHERE UPPER(TRIM(c.nombre_empresa)) = 'IMILE SAS'
                    AND o.estado = 'activa'
                """)
                ordenes_imile = {str(o['numero_orden']).strip(): o for o in cursor_im.fetchall()}

                # 3. Obtener precio de Imile
                cursor_im.execute("""
                    SELECT pc.precio_unitario
                    FROM precios_cliente pc
                    JOIN clientes c ON pc.cliente_id = c.id
                    WHERE UPPER(TRIM(c.nombre_empresa)) = 'IMILE SAS'
                    AND pc.activo = TRUE
                    LIMIT 1
                """)
                precio_row = cursor_im.fetchone()
                precio_imile = float(precio_row['precio_unitario']) if precio_row else 0.0
                cursor_im.close()

                if precio_imile > 0:
                    st.caption(f"Precio unitario Imile: ${precio_imile:,.0f}")
                else:
                    st.warning("No se encontró precio para Imile SAS. El valor de venta se pondrá en $0.")

                # 4. Comparar y ejecutar actualizaciones directamente
                actualizaciones_imile = []
                ya_ok = 0

                for gest in imile_gestiones:
                    orden_num = str(gest['orden']).strip()
                    entregas = int(gest['total_entregas'] or 0)
                    orden_bd = ordenes_imile.get(orden_num)

                    if not orden_bd:
                        continue

                    cantidad_actual = int(orden_bd['cantidad_total'] or 0)

                    if entregas > cantidad_actual:
                        nuevo_valor = entregas * precio_imile
                        actualizaciones_imile.append({
                            'orden_id': orden_bd['id'],
                            'orden': orden_num,
                            'recibido_anterior': cantidad_actual,
                            'recibido_nuevo': entregas,
                            'entregas': entregas,
                            'valor_anterior': float(orden_bd['valor_total'] or 0),
                            'valor_nuevo': nuevo_valor
                        })
                    else:
                        ya_ok += 1

                # 5. Ejecutar UPDATE si hay cambios
                if actualizaciones_imile:
                    conn_upd_im = conectar_db()
                    if conn_upd_im:
                        try:
                            cursor_upd_im = conn_upd_im.cursor()
                            conn_upd_im.autocommit = False

                            for reg in actualizaciones_imile:
                                cursor_upd_im.execute("""
                                    UPDATE ordenes
                                    SET cantidad_local = %s,
                                        cantidad_nacional = 0,
                                        cantidad_recibido_local = %s,
                                        cantidad_recibido_nacional = 0,
                                        cantidad_entregados_local = %s,
                                        cantidad_entregados_nacional = 0,
                                        valor_total = %s
                                    WHERE id = %s
                                """, (
                                    reg['recibido_nuevo'],
                                    reg['recibido_nuevo'],
                                    reg['entregas'],
                                    reg['valor_nuevo'],
                                    reg['orden_id']
                                ))

                            conn_upd_im.commit()
                            cursor_upd_im.close()
                            conn_upd_im.close()

                            # Mostrar resumen de lo actualizado
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Órdenes actualizadas", len(actualizaciones_imile))
                            with col2:
                                st.metric("Órdenes sin cambios", ya_ok)

                            df_imile_preview = pd.DataFrame(actualizaciones_imile)
                            df_imile_preview = df_imile_preview[['orden', 'recibido_anterior', 'recibido_nuevo', 'entregas', 'valor_anterior', 'valor_nuevo']]
                            df_imile_preview.columns = ['Orden', 'Recibido Ant.', 'Recibido Nuevo', 'Entregas', 'Valor Ant.', 'Valor Nuevo']
                            st.dataframe(df_imile_preview, use_container_width=True, hide_index=True)

                            st.success(f"✅ {len(actualizaciones_imile)} órdenes Imile actualizadas en la base de datos")

                        except Exception as e_im:
                            conn_upd_im.rollback()
                            cursor_upd_im.close()
                            conn_upd_im.close()
                            st.error(f"Error: {e_im}")
                else:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Órdenes actualizadas", 0)
                    with col2:
                        st.metric("Órdenes sin cambios", ya_ok)
                    st.success("Todas las órdenes Imile están correctas (recibido >= entregas)")

            except Exception as e_sync:
                st.error(f"Error: {e_sync}")
                import traceback
                st.code(traceback.format_exc())
            finally:
                conn_imile.close()

# Información adicional en sidebar
st.sidebar.markdown("### 📖 Ayuda")
st.sidebar.info("""
    **Flujo de trabajo:**

    1️⃣ **Procesar Archivo**
    - Carga y procesa el CSV histórico
    - Clasifica destinos
    - Agrupa por orden

    2️⃣ **Mapeo de Clientes**
    - Configura variaciones de nombres
    - Normaliza clientes

    3️⃣ **Resultado**
    - Valida contra BD
    - Elimina duplicados
    - Genera CSV listo para carga
""")

st.sidebar.markdown("### ⚙️ Configuración Actual")
if 'df_procesado' in st.session_state:
    st.sidebar.success(f"✅ Archivo procesado: {len(st.session_state['df_procesado'])} registros")
else:
    st.sidebar.warning("⏳ No hay archivo procesado")

st.sidebar.metric("Reglas de Mapeo", len(st.session_state.get('mapeo_clientes', {})))
st.sidebar.metric("Mapeos Interactivos", len(st.session_state.get('mapeo_interactivo_clientes', {})))

# Motor de procesamiento
st.sidebar.divider()
st.sidebar.markdown("### ⚙️ Motor de Procesamiento")
julia_ok, julia_ver = verificar_julia()
if julia_ok:
    st.sidebar.success("✅ Julia disponible")
    st.sidebar.caption(julia_ver.split('\n')[0])
    st.sidebar.info("💡 Selecciona Julia en TAB 1 para procesamiento 2-10x más rápido")
else:
    st.sidebar.warning("⚠️ Julia no disponible")
    st.sidebar.caption("Usando solo Python")

# Estado del caché
st.sidebar.divider()
st.sidebar.markdown("### 🔍 Estado del Caché")
cache_status = {
    'df_normalizado': '✅' if 'df_normalizado' in st.session_state else '❌',
    'df_nuevas': '✅' if 'df_nuevas' in st.session_state else '❌',
    'ordenes_existentes': '✅' if 'ordenes_existentes_set' in st.session_state else '❌'
}
for key, status in cache_status.items():
    st.sidebar.text(f"{status} {key}")

# Botón para limpiar caché
if st.sidebar.button("🗑️ Limpiar Todo el Caché", type="secondary"):
    keys_to_clear = ['df_normalizado', 'ordenes_existentes_set', 'ordenes_existentes_list',
                     'df_nuevas', 'df_duplicadas', 'mapeos_aplicados', 'force_reprocess']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.sidebar.success("✅ Caché limpiado")
    st.rerun()
