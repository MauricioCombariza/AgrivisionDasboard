import streamlit as st
import pandas as pd
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()
from datetime import datetime
import io

st.set_page_config(page_title="Procesador de Órdenes", page_icon="🔄", layout="wide")

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

def clasificar_destino(ciudad):
    """Clasifica destino como local si contiene 'bog', sino nacional"""
    ciudad = str(ciudad).lower().strip()
    return 'local' if 'bog' in ciudad else 'nacional'

def procesar_archivo_historico(ruta_archivo, orden_minima):
    """Procesa el archivo histórico y retorna DataFrame con formato requerido"""
    try:
        # Leer archivo
        df = pd.read_csv(ruta_archivo)

        # Pre-procesamiento de tipos de datos
        df['orden'] = pd.to_numeric(df['orden'], errors='coerce').fillna(0).astype(int)

        # Filtrar por número de orden
        df_filtrado = df[df['orden'] >= orden_minima].copy()

        # Conversión de fecha
        df_filtrado['f_emi'] = pd.to_datetime(df_filtrado['f_emi'], errors='coerce')

        # Creación de columna destino
        df_filtrado['destino'] = df_filtrado['ciudad1'].apply(clasificar_destino)

        # Usar pivot_table para separar cantidades local/nacional (método eficiente)
        # Crear conteos por orden y destino
        conteos = df_filtrado.groupby(['orden', 'destino']).agg(
            cantidad=('serial', 'count')
        ).reset_index()

        # Pivot para tener columnas local y nacional
        conteos_pivot = conteos.pivot_table(
            index='orden',
            columns='destino',
            values='cantidad',
            fill_value=0
        ).reset_index()

        # Renombrar columnas si existen
        if 'local' in conteos_pivot.columns:
            conteos_pivot.rename(columns={'local': 'cantidad_local'}, inplace=True)
        else:
            conteos_pivot['cantidad_local'] = 0

        if 'nacional' in conteos_pivot.columns:
            conteos_pivot.rename(columns={'nacional': 'cantidad_nacional'}, inplace=True)
        else:
            conteos_pivot['cantidad_nacional'] = 0

        # Obtener información adicional (fecha y cliente)
        info_adicional = df_filtrado.groupby('orden').agg(
            fecha_recepcion=('f_emi', 'first'),
            nombre_cliente=('no_entidad', 'first')
        ).reset_index()

        # Combinar todo
        df_final = info_adicional.merge(conteos_pivot, on='orden', how='left')

        # Asegurar que las columnas de cantidad existan
        if 'cantidad_local' not in df_final.columns:
            df_final['cantidad_local'] = 0
        if 'cantidad_nacional' not in df_final.columns:
            df_final['cantidad_nacional'] = 0

        # Formato final
        df_final['tipo_servicio'] = 'sobre'

        # Aseguramos que la fecha se vea limpia
        df_final['fecha_recepcion'] = df_final['fecha_recepcion'].dt.date

        # Convertir cantidades a int
        df_final['cantidad_local'] = df_final['cantidad_local'].fillna(0).astype(int)
        df_final['cantidad_nacional'] = df_final['cantidad_nacional'].fillna(0).astype(int)

        # Reordenar columnas
        df_final = df_final[['orden', 'fecha_recepcion', 'nombre_cliente', 'tipo_servicio', 'cantidad_local', 'cantidad_nacional']]

        return df_final, None
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
tab1, tab2, tab3 = st.tabs([
    "📊 Procesar Archivo",
    "🏢 Mapeo de Clientes",
    "📥 Resultado"
])

# ==============================================================================
# TAB 1: PROCESAR ARCHIVO
# ==============================================================================
with tab1:
    st.subheader("Procesamiento de Archivo Histórico")

    col1, col2 = st.columns(2)

    with col1:
        ruta_archivo = st.text_input(
            "Ruta del Archivo CSV",
            value="/mnt/c/Users/mcomb/Desktop/Carvajal/python/basesHisto.csv"
        )

    with col2:
        orden_minima = st.number_input(
            "Orden Mínima a Procesar",
            min_value=0,
            value=123273,
            step=1,
            help="Solo se procesarán órdenes >= a este número"
        )

    if st.button("🚀 Procesar Archivo", type="primary"):
        with st.spinner("Procesando archivo histórico..."):
            # Procesar archivo
            df_procesado, error = procesar_archivo_historico(ruta_archivo, orden_minima)

            if error:
                st.error(f"Error al procesar archivo: {error}")
            elif df_procesado is not None:
                st.success(f"✅ Archivo procesado exitosamente: {len(df_procesado)} registros encontrados")

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
