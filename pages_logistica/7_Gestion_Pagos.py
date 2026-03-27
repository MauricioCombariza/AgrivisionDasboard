import streamlit as st
import pandas as pd
from datetime import date
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mysql.connector
from utils.db_connection import conectar_logistica


st.title("💰 Gestion de Pagos a Mensajeros")

# BD local: gestiones_mensajero, ordenes, planillas_revisadas, clientes, precios
def _conectar_local():
    try:
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="logistica",
        )
    except Exception as e:
        st.error(f"Error conectando a BD local: {e}")
        return None

conn = _conectar_local()
if not conn:
    st.stop()

# BD nube: personal (para leer nombres, zonas y tarifas de mensajeros)
conn_nube = conectar_logistica()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📤 Cargar Gestiones",
    "📋 Gestiones Registradas",
    "📊 Resumen por Mensajero",
    "🔄 Recalcular Valores",
    "🏦 BCS *DEV_21"
])

with tab1:
    st.subheader("Cargar archivo de gestiones")

    uploaded_file = st.file_uploader("Selecciona el archivo CSV de agrupacion", type="csv")

    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)

        # Mostrar vista previa
        st.markdown("### Vista previa del archivo")
        st.dataframe(df, use_container_width=True)

        # Validar columnas requeridas (cod_sec es opcional para compatibilidad)
        columnas_requeridas = ['f_esc', 'cod_men', 'lot_esc', 'orden', 'mot_esc', 'no_entidad', 'total_serial']

        # Agregar cod_sec si no existe (para compatibilidad)
        if 'cod_sec' not in df.columns:
            df['cod_sec'] = ''
        else:
            df['cod_sec'] = df['cod_sec'].fillna('').astype(str)
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]

        if columnas_faltantes:
            st.error(f"Columnas faltantes: {columnas_faltantes}")
            st.stop()

        st.success(f"Archivo valido. {len(df)} registros encontrados.")

        # Validar duplicados exactos (misma combinacion de todas las columnas clave)
        st.markdown("### Validacion de duplicados")
        columnas_clave = ['f_esc', 'cod_men', 'lot_esc', 'orden', 'mot_esc', 'no_entidad']
        duplicados = df[df.duplicated(subset=columnas_clave, keep=False)]

        if not duplicados.empty:
            st.warning(f"Se encontraron {len(duplicados)} filas duplicadas exactas:")
            st.dataframe(duplicados[columnas_clave + ['total_serial']], use_container_width=True)
        else:
            st.success("No hay duplicados exactos en el archivo")

        st.divider()

        # Obtener clientes y precios de la BD
        st.markdown("### Mapeo de clientes y precios")

        try:
            cursor = conn.cursor(dictionary=True)

            # Obtener clientes
            cursor.execute("SELECT id, nombre_empresa FROM clientes WHERE activo = TRUE")
            clientes_bd = {c['nombre_empresa'].upper(): c['id'] for c in cursor.fetchall()}

            # Obtener precios por cliente (sin zona)
            cursor.execute("""
                SELECT
                    c.nombre_empresa, pc.cliente_id, pc.tipo_operacion,
                    pc.costo_mensajero_entrega, pc.costo_mensajero_devolucion
                FROM precios_cliente pc
                JOIN clientes c ON pc.cliente_id = c.id
                WHERE pc.activo = TRUE AND pc.ambito = 'bogota' AND pc.zona IS NULL
            """)
            precios_bd = cursor.fetchall()

            # Crear diccionario de precios (para clientes sin zona)
            # Entrega: priorizar el menor valor cuando hay duplicados
            # Devolucion: priorizar el mayor valor cuando hay duplicados
            precios_dict = {}
            for p in precios_bd:
                key = p['nombre_empresa'].upper()
                if key not in precios_dict:
                    precios_dict[key] = {'entrega': 0, 'devolucion': 0}
                if p['costo_mensajero_entrega']:
                    nuevo_precio = float(p['costo_mensajero_entrega'])
                    # Entrega: usar el menor precio
                    if precios_dict[key]['entrega'] == 0 or nuevo_precio < precios_dict[key]['entrega']:
                        precios_dict[key]['entrega'] = nuevo_precio
                if p['costo_mensajero_devolucion']:
                    nuevo_precio = float(p['costo_mensajero_devolucion'])
                    # Devolucion: usar el mayor precio
                    if nuevo_precio > precios_dict[key]['devolucion']:
                        precios_dict[key]['devolucion'] = nuevo_precio

            # Obtener precios por zona para clientes especiales (1, 3, 5)
            cursor.execute("""
                SELECT
                    c.nombre_empresa, pc.cliente_id, pc.tipo_operacion, pc.zona,
                    pc.costo_mensajero_entrega, pc.costo_mensajero_devolucion
                FROM precios_cliente pc
                JOIN clientes c ON pc.cliente_id = c.id
                WHERE pc.activo = TRUE AND pc.ambito = 'bogota' AND pc.zona IS NOT NULL
                AND pc.cliente_id IN (1, 3, 5)
            """)
            precios_zona_bd = cursor.fetchall()

            # Crear diccionario de precios por zona {cliente: {zona: {entrega: x, devolucion: y}}}
            precios_zona_dict = {}
            clientes_con_zona = set()
            for p in precios_zona_bd:
                key = p['nombre_empresa'].upper()
                zona = p['zona']
                clientes_con_zona.add(key)
                if key not in precios_zona_dict:
                    precios_zona_dict[key] = {'norte': {'entrega': 0, 'devolucion': 0}, 'sur': {'entrega': 0, 'devolucion': 0}}
                if p['costo_mensajero_entrega']:
                    precios_zona_dict[key][zona]['entrega'] = float(p['costo_mensajero_entrega'])
                if p['costo_mensajero_devolucion']:
                    precios_zona_dict[key][zona]['devolucion'] = float(p['costo_mensajero_devolucion'])

            # Obtener personal desde BD nube (fuente de verdad para mensajeros)
            cursor_nube = conn_nube.cursor(dictionary=True)
            cursor_nube.execute("""
                SELECT codigo, id, nombre_completo, tipo_personal, zona,
                       tarifa_entrega_local, tarifa_entrega_nacional,
                       tarifa_devolucion_local, tarifa_devolucion_nacional
                FROM personal
                WHERE activo = TRUE AND tipo_personal IN ('mensajero', 'courier_externo', 'alistamiento', 'conductor')
            """)
            mensajeros_bd = {m['codigo']: {
                'id': m['id'],
                'nombre': m['nombre_completo'],
                'zona': m['zona'],
                'tipo': m['tipo_personal'],
                'tarifa_entrega_local': float(m['tarifa_entrega_local']) if m['tarifa_entrega_local'] else 0,
                'tarifa_entrega_nacional': float(m['tarifa_entrega_nacional']) if m['tarifa_entrega_nacional'] else 0,
                'tarifa_devolucion_local': float(m['tarifa_devolucion_local']) if m['tarifa_devolucion_local'] else 0,
                'tarifa_devolucion_nacional': float(m['tarifa_devolucion_nacional']) if m['tarifa_devolucion_nacional'] else 0
            } for m in cursor_nube.fetchall()}
            cursor_nube.close()

            # Convertir cod_men a texto de 4 digitos con ceros a la izquierda
            df['cod_men'] = df['cod_men'].fillna(0).astype(int).astype(str).str.zfill(4)

            # Mapear datos del CSV
            df['cliente_upper'] = df['no_entidad'].str.upper().str.strip()
            df['mot_esc_lower'] = df['mot_esc'].str.lower().str.strip()

            # Mapear datos del mensajero
            df['mensajero_zona'] = df['cod_men'].apply(
                lambda x: mensajeros_bd.get(x, {}).get('zona', None)
            )
            df['mensajero_tipo'] = df['cod_men'].apply(
                lambda x: mensajeros_bd.get(x, {}).get('tipo', None)
            )
            df['mensajero_tarifa_entrega_local'] = df['cod_men'].apply(
                lambda x: mensajeros_bd.get(x, {}).get('tarifa_entrega_local', 0)
            )
            df['mensajero_tarifa_devolucion_local'] = df['cod_men'].apply(
                lambda x: mensajeros_bd.get(x, {}).get('tarifa_devolucion_local', 0)
            )

            # Funcion para calcular precio unitario considerando tipo de personal y zona
            def calcular_precio_unitario(row):
                cliente = row['cliente_upper']
                tipo = 'entrega' if 'entrega' in row['mot_esc_lower'] else 'devolucion'
                cod_men = row['cod_men']
                zona_mensajero = row['mensajero_zona']
                tipo_personal = row['mensajero_tipo']
                cod_sec = str(row.get('cod_sec', '')).strip()

                # REGLA ESPECIAL: Banco Caja Social (cliente_id=1) con cod_sec='*DEV_21' = precio 0
                if cliente == 'BANCO CAJA SOCIAL' and cod_sec == '*DEV_21':
                    return 0

                # Si es courier_externo, usar su tarifa propia (local por defecto en Bogota)
                if tipo_personal == 'courier_externo':
                    if tipo == 'entrega':
                        return row['mensajero_tarifa_entrega_local']
                    else:
                        return row['mensajero_tarifa_devolucion_local']

                # Si el cliente tiene precios por zona (solo para mensajeros normales)
                if cliente in clientes_con_zona:
                    if zona_mensajero and zona_mensajero in ['norte', 'sur']:
                        return precios_zona_dict.get(cliente, {}).get(zona_mensajero, {}).get(tipo, 0)
                    else:
                        # Mensajero sin zona asignada, usar precio por defecto (sur es mayor)
                        return precios_zona_dict.get(cliente, {}).get('sur', {}).get(tipo, 0)
                else:
                    # Cliente sin precios por zona, usar precio normal
                    return precios_dict.get(cliente, {}).get(tipo, 0)

            df['valor_unitario'] = df.apply(calcular_precio_unitario, axis=1)
            df['valor_total'] = df['valor_unitario'] * df['total_serial']

            # Mapear mensajero
            df['mensajero_nombre'] = df['cod_men'].apply(
                lambda x: mensajeros_bd.get(x, {}).get('nombre', 'NO ENCONTRADO')
            )
            df['mensajero_id'] = df['cod_men'].apply(
                lambda x: mensajeros_bd.get(x, {}).get('id', None)
            )

            # Verificar mensajeros sin zona asignada para clientes que requieren zona (excluir courier_externo)
            mensajeros_sin_zona = df[
                (df['cliente_upper'].isin(clientes_con_zona)) &
                (df['mensajero_zona'].isna()) &
                (df['mensajero_tipo'] != 'courier_externo')
            ]['cod_men'].unique()

            if len(mensajeros_sin_zona) > 0:
                st.warning(f"Mensajeros sin zona asignada (clientes con precio por zona): {list(mensajeros_sin_zona)}. Se uso precio de zona SUR por defecto.")

            # Verificar courier_externo sin tarifa configurada
            couriers_sin_tarifa = df[
                (df['mensajero_tipo'] == 'courier_externo') &
                ((df['mensajero_tarifa_entrega_local'] == 0) | (df['mensajero_tarifa_devolucion_local'] == 0))
            ]['cod_men'].unique()

            if len(couriers_sin_tarifa) > 0:
                st.warning(f"Courier externo sin tarifa configurada: {list(couriers_sin_tarifa)}. Verificar tarifas en Personal.")

            # Verificar clientes no mapeados
            clientes_csv = df['cliente_upper'].unique()
            clientes_no_encontrados = [c for c in clientes_csv if c not in precios_dict]

            if clientes_no_encontrados:
                st.warning(f"Clientes sin precio configurado: {clientes_no_encontrados}")

            # Verificar mensajeros no encontrados
            mensajeros_no_encontrados = df[df['mensajero_nombre'] == 'NO ENCONTRADO']['cod_men'].unique()
            if len(mensajeros_no_encontrados) > 0:
                st.warning(f"Codigos de mensajero no encontrados: {list(mensajeros_no_encontrados)}")

            # Mostrar resultado con valores calculados
            st.markdown("### Gestiones con valores calculados")

            df_resultado = df[[
                'f_esc', 'cod_men', 'mensajero_nombre', 'lot_esc', 'orden',
                'mot_esc', 'no_entidad', 'total_serial', 'valor_unitario', 'valor_total'
            ]].copy()

            st.dataframe(df_resultado, use_container_width=True)

            # Metricas
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Gestiones", len(df_resultado))
            with col2:
                st.metric("Total Seriales", df_resultado['total_serial'].sum())
            with col3:
                st.metric("Valor Total", f"${df_resultado['valor_total'].sum():,.0f}")
            with col4:
                st.metric("Mensajeros", df_resultado['cod_men'].nunique())

            st.divider()

            # Boton para registrar gestiones
            st.markdown("### Registrar en Base de Datos")

            fecha_pago = st.date_input("Fecha de registro", value=date.today())

            if st.button("💾 Registrar Gestiones", type="primary"):
                try:
                    cursor = conn.cursor()
                    registros_insertados = 0
                    registros_duplicados = 0

                    for _, row in df.iterrows():
                        # Verificar si ya existe la gestion (lot_esc + orden + tipo_gestion + cliente + cod_mensajero)
                        cursor.execute("""
                            SELECT id FROM gestiones_mensajero
                            WHERE lot_esc = %s AND orden = %s AND tipo_gestion = %s AND cliente = %s AND cod_mensajero = %s
                        """, (str(row['lot_esc']), str(row['orden']), row['mot_esc'], row['no_entidad'], row['cod_men']))

                        if cursor.fetchone():
                            registros_duplicados += 1
                            continue

                        # Insertar gestion
                        cursor.execute("""
                            INSERT INTO gestiones_mensajero
                            (fecha_escaner, cod_mensajero, mensajero_id, lot_esc, orden,
                             tipo_gestion, cliente, total_seriales, valor_unitario, valor_total,
                             fecha_registro, cod_sec)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            row['f_esc'],
                            row['cod_men'],
                            row['mensajero_id'] if pd.notna(row['mensajero_id']) else None,
                            str(row['lot_esc']),
                            str(row['orden']),
                            row['mot_esc'],
                            row['no_entidad'],
                            int(row['total_serial']),
                            float(row['valor_unitario']),
                            float(row['valor_total']),
                            fecha_pago,
                            str(row.get('cod_sec', '')) if row.get('cod_sec') else None
                        ))
                        registros_insertados += 1

                    conn.commit()
                    st.success(f"✅ {registros_insertados} gestiones registradas exitosamente")
                    if registros_duplicados > 0:
                        st.info(f"ℹ️ {registros_duplicados} registros omitidos (ya existian en BD)")

                except Exception as e:
                    conn.rollback()
                    st.error(f"Error al registrar: {e}")

        except Exception as e:
            st.error(f"Error: {e}")

with tab2:
    st.subheader("Gestiones Registradas")

    try:
        cursor = conn.cursor(dictionary=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            fecha_desde = st.date_input("Desde", value=date.today().replace(day=1), key="fecha_desde")
        with col2:
            fecha_hasta = st.date_input("Hasta", value=date.today(), key="fecha_hasta")
        with col3:
            # Obtener mensajeros con gestiones
            cursor.execute("""
                SELECT DISTINCT gm.cod_mensajero, COALESCE(p.nombre_completo, 'Sin asignar') as nombre
                FROM gestiones_mensajero gm
                LEFT JOIN personal p ON gm.mensajero_id = p.id
                ORDER BY gm.cod_mensajero
            """)
            mensajeros_list = cursor.fetchall()

            mensajero_options = {"TODOS": None}
            for m in mensajeros_list:
                mensajero_options[f"{m['cod_mensajero']} - {m['nombre']}"] = m['cod_mensajero']

            mensajero_sel = st.selectbox("Mensajero", list(mensajero_options.keys()), key="mensajero_tab2")
            cod_mensajero_filtro = mensajero_options[mensajero_sel]

        query = """
            SELECT
                gm.id, gm.fecha_escaner, gm.cod_mensajero,
                COALESCE(p.nombre_completo, 'No asignado') as mensajero,
                gm.lot_esc, gm.orden, gm.tipo_gestion, gm.cliente,
                gm.total_seriales, gm.valor_unitario, gm.valor_total,
                gm.fecha_registro
            FROM gestiones_mensajero gm
            LEFT JOIN personal p ON gm.mensajero_id = p.id
            WHERE gm.fecha_registro BETWEEN %s AND %s
        """
        params = [fecha_desde, fecha_hasta]

        if cod_mensajero_filtro:
            query += " AND gm.cod_mensajero = %s"
            params.append(cod_mensajero_filtro)

        query += " ORDER BY gm.fecha_escaner DESC, gm.cod_mensajero"

        cursor.execute(query, tuple(params))

        gestiones = cursor.fetchall()

        if gestiones:
            df_gestiones = pd.DataFrame(gestiones)
            df_gestiones['valor_unitario'] = df_gestiones['valor_unitario'].apply(lambda x: f"${x:,.0f}")
            df_gestiones['valor_total'] = df_gestiones['valor_total'].apply(lambda x: f"${x:,.0f}")

            st.dataframe(df_gestiones, use_container_width=True, hide_index=True)
            st.metric("Total Registros", len(gestiones))
        else:
            st.info("No hay gestiones registradas en el periodo seleccionado")

    except Exception as e:
        st.error(f"Error: {e}")

with tab3:
    st.subheader("Resumen de Pagos por Mensajero")

    try:
        cursor = conn.cursor(dictionary=True)

        col1, col2 = st.columns(2)
        with col1:
            fecha_desde_r = st.date_input("Desde", value=date.today().replace(day=1), key="fecha_desde_r")
        with col2:
            fecha_hasta_r = st.date_input("Hasta", value=date.today(), key="fecha_hasta_r")

        cursor.execute("""
            SELECT
                gm.cod_mensajero,
                COALESCE(p.nombre_completo, 'No asignado') as mensajero,
                COUNT(*) as total_gestiones,
                SUM(gm.total_seriales) as total_seriales,
                SUM(CASE WHEN gm.tipo_gestion LIKE '%%Entrega%%' THEN gm.total_seriales ELSE 0 END) as seriales_entrega,
                SUM(CASE WHEN gm.tipo_gestion NOT LIKE '%%Entrega%%' THEN gm.total_seriales ELSE 0 END) as seriales_devolucion,
                SUM(gm.valor_total) as valor_total
            FROM gestiones_mensajero gm
            LEFT JOIN personal p ON gm.mensajero_id = p.id
            WHERE gm.fecha_registro BETWEEN %s AND %s
            GROUP BY gm.cod_mensajero, p.nombre_completo
            ORDER BY valor_total DESC
        """, (fecha_desde_r, fecha_hasta_r))

        resumen = cursor.fetchall()

        if resumen:
            df_resumen = pd.DataFrame(resumen)
            df_resumen['valor_total'] = df_resumen['valor_total'].apply(lambda x: f"${x:,.0f}")

            st.dataframe(df_resumen, use_container_width=True, hide_index=True)

            # Metricas generales
            total_pagar = sum([r['valor_total'] for r in resumen if isinstance(r['valor_total'], (int, float))])
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Mensajeros", len(resumen))
            with col2:
                st.metric("Total Gestiones", sum([r['total_gestiones'] for r in resumen]))
            with col3:
                cursor.execute("""
                    SELECT SUM(valor_total) as total FROM gestiones_mensajero
                    WHERE fecha_registro BETWEEN %s AND %s
                """, (fecha_desde_r, fecha_hasta_r))
                total = cursor.fetchone()
                st.metric("Total a Pagar", f"${total['total']:,.0f}" if total['total'] else "$0")
        else:
            st.info("No hay datos para el periodo seleccionado")

    except Exception as e:
        st.error(f"Error: {e}")

with tab4:
    st.subheader("Recalcular Valores de Gestiones")
    st.warning("⚠️ Esta opción recalcula los valores de las gestiones usando los precios actuales de la tabla `precios_cliente`.")

    try:
        cursor = conn.cursor(dictionary=True)

        # Mostrar precios actuales por cliente
        st.markdown("### 💰 Precios Actuales (Mensajeros Bogotá)")
        cursor.execute("""
            SELECT
                c.nombre_empresa as cliente,
                pc.tipo_operacion,
                pc.costo_mensajero_entrega,
                pc.costo_mensajero_devolucion,
                pc.vigencia_desde,
                pc.vigencia_hasta
            FROM precios_cliente pc
            JOIN clientes c ON pc.cliente_id = c.id
            WHERE pc.activo = TRUE AND pc.ambito = 'bogota'
            ORDER BY c.nombre_empresa, pc.tipo_operacion
        """)
        precios_actuales = cursor.fetchall()

        if precios_actuales:
            df_precios = pd.DataFrame(precios_actuales)
            df_precios['costo_mensajero_entrega'] = df_precios['costo_mensajero_entrega'].apply(
                lambda x: f"${x:,.0f}" if x else "N/A"
            )
            df_precios['costo_mensajero_devolucion'] = df_precios['costo_mensajero_devolucion'].apply(
                lambda x: f"${x:,.0f}" if x else "N/A"
            )
            st.dataframe(df_precios, use_container_width=True, hide_index=True)

        st.divider()

        # Filtros para recalcular
        st.markdown("### 🔧 Configuración de Recálculo")

        col1, col2 = st.columns(2)
        with col1:
            # Valor por defecto: 1 de enero del año actual
            fecha_desde_rec = st.date_input("Desde", value=date(date.today().year, 1, 1), key="fecha_desde_rec")
        with col2:
            fecha_hasta_rec = st.date_input("Hasta", value=date.today(), key="fecha_hasta_rec")

        # Obtener clientes con gestiones en el periodo
        cursor.execute("""
            SELECT DISTINCT cliente FROM gestiones_mensajero
            WHERE DATE(fecha_escaner) BETWEEN %s AND %s
            ORDER BY cliente
        """, (fecha_desde_rec, fecha_hasta_rec))
        clientes_con_gestiones = [r['cliente'] for r in cursor.fetchall()]

        cliente_filtro = st.selectbox(
            "Cliente (opcional - vacío = todos)",
            ["TODOS"] + clientes_con_gestiones,
            key="cliente_filtro_rec"
        )

        # Preview de gestiones a recalcular
        st.markdown("### 📊 Vista Previa - Gestiones a Recalcular")

        # Construir WHERE dinámico antes de armar la query
        where_preview = "WHERE DATE(gm.fecha_escaner) BETWEEN %s AND %s"
        params_preview = [fecha_desde_rec, fecha_hasta_rec]
        if cliente_filtro != "TODOS":
            where_preview += " AND UPPER(TRIM(gm.cliente)) = UPPER(TRIM(%s))"
            params_preview.append(cliente_filtro)
        # Excluir planillas revisadas y registros editados manualmente
        where_preview += " AND gm.editado_manualmente = 0 AND gm.lot_esc NOT IN (SELECT lot_esc FROM planillas_revisadas)"

        # COALESCE prioriza 'sobre' antes que 'paquete' — evita duplicados por JOIN múltiple
        query_preview = f"""
            SELECT
                gm.id, gm.cliente, gm.tipo_gestion,
                gm.total_seriales,
                gm.valor_unitario as valor_actual,
                gm.valor_total as total_actual,
                COALESCE(
                    MAX(CASE WHEN pc.tipo_servicio = 'sobre' AND gm.tipo_gestion LIKE '%%Entrega%%' THEN pc.costo_mensajero_entrega END),
                    MAX(CASE WHEN pc.tipo_servicio = 'paquete' AND gm.tipo_gestion LIKE '%%Entrega%%' THEN pc.costo_mensajero_entrega END),
                    MAX(CASE WHEN pc.tipo_servicio = 'sobre' AND gm.tipo_gestion NOT LIKE '%%Entrega%%' THEN pc.costo_mensajero_devolucion END),
                    MAX(CASE WHEN pc.tipo_servicio = 'paquete' AND gm.tipo_gestion NOT LIKE '%%Entrega%%' THEN pc.costo_mensajero_devolucion END)
                ) as nuevo_valor_unitario
            FROM gestiones_mensajero gm
            LEFT JOIN clientes c ON UPPER(TRIM(c.nombre_empresa)) = UPPER(TRIM(gm.cliente))
            LEFT JOIN precios_cliente pc ON pc.cliente_id = c.id
                AND pc.activo = TRUE
                AND pc.ambito = 'bogota'
                AND ((gm.tipo_gestion LIKE '%%Entrega%%' AND pc.tipo_operacion = 'entrega')
                     OR (gm.tipo_gestion NOT LIKE '%%Entrega%%' AND pc.tipo_operacion = 'devolucion'))
            {where_preview}
            GROUP BY gm.id, gm.cliente, gm.tipo_gestion, gm.total_seriales, gm.valor_unitario, gm.valor_total
            ORDER BY gm.cliente, gm.tipo_gestion
        """

        cursor.execute(query_preview, tuple(params_preview))
        preview_data = cursor.fetchall()

        if preview_data:
            # Separar registros con precio encontrado vs sin precio
            rows_con_precio = [r for r in preview_data if r['nuevo_valor_unitario'] is not None]
            rows_sin_precio = [r for r in preview_data if r['nuevo_valor_unitario'] is None]

            # Calcular totales SOLO para registros con precio (los que realmente se actualizarán)
            resumen_cambios = {}
            total_diferencia = 0

            for row in rows_con_precio:
                cliente = row['cliente']
                if cliente not in resumen_cambios:
                    resumen_cambios[cliente] = {
                        'gestiones': 0,
                        'total_actual': 0,
                        'total_nuevo': 0
                    }

                nuevo_unitario = float(row['nuevo_valor_unitario'])
                nuevo_total = nuevo_unitario * row['total_seriales']
                total_actual = float(row['total_actual'] or 0)

                resumen_cambios[cliente]['gestiones'] += 1
                resumen_cambios[cliente]['total_actual'] += total_actual
                resumen_cambios[cliente]['total_nuevo'] += nuevo_total
                total_diferencia += (nuevo_total - total_actual)

            # Desglose de precios por tipo de gestión (precio unitario actual vs nuevo)
            st.markdown("#### Precios Unitarios")
            precios_por_tipo = {}
            for row in rows_con_precio:
                tipo = row['tipo_gestion']
                if tipo not in precios_por_tipo:
                    precios_por_tipo[tipo] = {
                        'gestiones': 0,
                        'seriales': 0,
                        'precios_actuales': set(),
                        'nuevo_precio': float(row['nuevo_valor_unitario'])
                    }
                precios_por_tipo[tipo]['gestiones'] += 1
                precios_por_tipo[tipo]['seriales'] += row['total_seriales']
                precio_unit_actual = float(row['valor_actual'] or 0)
                if precio_unit_actual > 0:
                    precios_por_tipo[tipo]['precios_actuales'].add(round(precio_unit_actual))

            tabla_precios = []
            for tipo, datos in sorted(precios_por_tipo.items()):
                precios_act_str = ", ".join([f"${p:,}" for p in sorted(datos['precios_actuales'])]) or "—"
                tabla_precios.append({
                    'Tipo Gestión': tipo,
                    'Gestiones': datos['gestiones'],
                    'Seriales': f"{datos['seriales']:,}",
                    'Precio Actual': precios_act_str,
                    'Precio Nuevo': f"${datos['nuevo_precio']:,.0f}",
                    'Cambio': '📈' if datos['nuevo_precio'] > min(datos['precios_actuales'], default=0)
                              else ('📉' if datos['nuevo_precio'] < min(datos['precios_actuales'], default=0) else '➡️')
                })

            st.dataframe(pd.DataFrame(tabla_precios), use_container_width=True, hide_index=True)

            # Resumen por cliente
            st.markdown("#### Resumen por Cliente")
            tabla_resumen = []
            for cliente, datos in resumen_cambios.items():
                diferencia = datos['total_nuevo'] - datos['total_actual']
                tabla_resumen.append({
                    'Cliente': cliente,
                    'Gestiones': datos['gestiones'],
                    'Total Actual': f"${datos['total_actual']:,.0f}",
                    'Total Nuevo': f"${datos['total_nuevo']:,.0f}",
                    'Diferencia': f"${diferencia:,.0f}",
                    '': '📈' if diferencia > 0 else ('📉' if diferencia < 0 else '➡️')
                })

            st.dataframe(pd.DataFrame(tabla_resumen), use_container_width=True, hide_index=True)

            # Métricas totales
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Se actualizarán", len(rows_con_precio))
            with col2:
                st.metric("Sin precio (se saltarán)", len(rows_sin_precio),
                          help="Estas gestiones no tienen precio configurado en precios_cliente y NO serán modificadas")
            with col3:
                total_actual_sum = sum([d['total_actual'] for d in resumen_cambios.values()])
                st.metric("Total Actual", f"${total_actual_sum:,.0f}")
            with col4:
                total_nuevo_sum = sum([d['total_nuevo'] for d in resumen_cambios.values()])
                st.metric("Total Nuevo", f"${total_nuevo_sum:,.0f}", f"${total_diferencia:,.0f}")

            # Advertencia si hay registros sin precio
            if rows_sin_precio:
                tipos_sin_precio = list(set([r['tipo_gestion'] for r in rows_sin_precio]))
                clientes_sin_precio = list(set([r['cliente'] for r in rows_sin_precio]))
                st.warning(
                    f"⚠️ **{len(rows_sin_precio)} gestiones NO se actualizarán** porque no tienen precio "
                    f"configurado en `precios_cliente` para su combinación de cliente/tipo/ámbito.\n\n"
                    f"**Clientes afectados:** {', '.join(clientes_sin_precio[:5])}\n\n"
                    f"**Tipos de gestión sin precio:** {', '.join(tipos_sin_precio[:5])}"
                )

            st.divider()

            # Botón para aplicar cambios
            confirmar_recalculo = st.checkbox("✅ Confirmo que quiero recalcular los valores", key="confirmar_recalculo")

            if st.button("🚀 RECALCULAR VALORES", type="primary", disabled=not confirmar_recalculo):
                try:
                    cursor_update = conn.cursor()

                    # Construir WHERE dinámico para la subquery interna
                    where_update = "WHERE DATE(gm2.fecha_escaner) BETWEEN %s AND %s"
                    params_update = [fecha_desde_rec, fecha_hasta_rec]
                    if cliente_filtro != "TODOS":
                        where_update += " AND UPPER(TRIM(gm2.cliente)) = UPPER(TRIM(%s))"
                        params_update.append(cliente_filtro)
                    # Excluir planillas revisadas y registros editados manualmente
                    where_update += " AND gm2.editado_manualmente = 0 AND gm2.lot_esc NOT IN (SELECT lot_esc FROM planillas_revisadas)"

                    # UPDATE con subquery: prioriza 'sobre' antes que 'paquete'
                    # evita que el JOIN múltiple aplique el precio incorrecto
                    query_update = f"""
                        UPDATE gestiones_mensajero gm
                        JOIN (
                            SELECT
                                gm2.id,
                                COALESCE(
                                    MAX(CASE WHEN pc.tipo_servicio = 'sobre' AND gm2.tipo_gestion LIKE '%%Entrega%%' THEN pc.costo_mensajero_entrega END),
                                    MAX(CASE WHEN pc.tipo_servicio = 'paquete' AND gm2.tipo_gestion LIKE '%%Entrega%%' THEN pc.costo_mensajero_entrega END),
                                    MAX(CASE WHEN pc.tipo_servicio = 'sobre' AND gm2.tipo_gestion NOT LIKE '%%Entrega%%' THEN pc.costo_mensajero_devolucion END),
                                    MAX(CASE WHEN pc.tipo_servicio = 'paquete' AND gm2.tipo_gestion NOT LIKE '%%Entrega%%' THEN pc.costo_mensajero_devolucion END)
                                ) as nuevo_precio
                            FROM gestiones_mensajero gm2
                            JOIN clientes c ON UPPER(TRIM(c.nombre_empresa)) = UPPER(TRIM(gm2.cliente))
                            JOIN precios_cliente pc ON pc.cliente_id = c.id
                                AND pc.activo = TRUE
                                AND pc.ambito = 'bogota'
                                AND ((gm2.tipo_gestion LIKE '%%Entrega%%' AND pc.tipo_operacion = 'entrega')
                                     OR (gm2.tipo_gestion NOT LIKE '%%Entrega%%' AND pc.tipo_operacion = 'devolucion'))
                            {where_update}
                            GROUP BY gm2.id
                        ) derived ON gm.id = derived.id
                        SET
                            gm.valor_unitario = derived.nuevo_precio,
                            gm.valor_total = gm.total_seriales * derived.nuevo_precio
                        WHERE derived.nuevo_precio IS NOT NULL
                    """

                    cursor_update.execute(query_update, tuple(params_update))
                    filas_actualizadas = cursor_update.rowcount
                    conn.commit()
                    cursor_update.close()

                    st.success(f"✅ Se recalcularon **{filas_actualizadas} gestiones** exitosamente")
                    st.balloons()
                    st.rerun()

                except Exception as e:
                    conn.rollback()
                    st.error(f"Error al recalcular: {e}")
                    import traceback
                    st.code(traceback.format_exc())

        else:
            st.info("No hay gestiones en el periodo seleccionado")

    except Exception as e:
        st.error(f"Error: {e}")
        import traceback
        st.code(traceback.format_exc())

with tab5:
    st.subheader("Aplicar Precio $0 - Banco Caja Social *DEV_21")
    st.info("Esta opción aplica precio $0 a las gestiones de Banco Caja Social donde el campo 'orden' contenga '*DEV_21'")

    try:
        cursor = conn.cursor(dictionary=True)

        # Filtros de fecha
        col1, col2 = st.columns(2)
        with col1:
            fecha_desde_bcs = st.date_input("Desde", value=date(date.today().year, 1, 1), key="fecha_desde_bcs")
        with col2:
            fecha_hasta_bcs = st.date_input("Hasta", value=date.today(), key="fecha_hasta_bcs")

        st.divider()

        # Preview de gestiones afectadas
        st.markdown("### 📊 Vista Previa - Gestiones a Modificar")

        query_preview_bcs = """
            SELECT
                gm.id, gm.fecha_escaner, gm.cod_mensajero, gm.orden, gm.cliente,
                gm.tipo_gestion, gm.total_seriales,
                gm.valor_unitario as valor_actual,
                gm.valor_total as total_actual,
                gm.cod_sec
            FROM gestiones_mensajero gm
            WHERE gm.fecha_registro BETWEEN %s AND %s
            AND UPPER(TRIM(gm.cliente)) = 'BANCO CAJA SOCIAL'
            AND (gm.orden LIKE '%%*DEV_21%%' OR gm.cod_sec = '*DEV_21')
            AND gm.valor_unitario > 0
            AND gm.editado_manualmente = 0
            AND gm.lot_esc NOT IN (SELECT lot_esc FROM planillas_revisadas)
            ORDER BY gm.fecha_escaner DESC
        """

        cursor.execute(query_preview_bcs, (fecha_desde_bcs, fecha_hasta_bcs))
        preview_bcs = cursor.fetchall()

        if preview_bcs:
            df_preview_bcs = pd.DataFrame(preview_bcs)

            # Calcular totales
            total_actual = sum([float(r['total_actual']) for r in preview_bcs])
            total_seriales = sum([r['total_seriales'] for r in preview_bcs])

            # Mostrar tabla
            df_display = df_preview_bcs.copy()
            df_display['valor_actual'] = df_display['valor_actual'].apply(lambda x: f"${x:,.0f}")
            df_display['total_actual'] = df_display['total_actual'].apply(lambda x: f"${x:,.0f}")
            st.dataframe(df_display, use_container_width=True, hide_index=True)

            # Metricas
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Gestiones a Modificar", len(preview_bcs))
            with col2:
                st.metric("Total Seriales", f"{total_seriales:,}")
            with col3:
                st.metric("Valor a Reducir", f"${total_actual:,.0f}", f"-${total_actual:,.0f}")

            st.divider()

            # Confirmar y aplicar
            confirmar_bcs = st.checkbox("✅ Confirmo que quiero aplicar precio $0 a estas gestiones", key="confirmar_bcs")

            if st.button("🚀 APLICAR PRECIO $0", type="primary", disabled=not confirmar_bcs):
                try:
                    cursor_update = conn.cursor()

                    query_update_bcs = """
                        UPDATE gestiones_mensajero
                        SET valor_unitario = 0, valor_total = 0
                        WHERE fecha_registro BETWEEN %s AND %s
                        AND UPPER(TRIM(cliente)) = 'BANCO CAJA SOCIAL'
                        AND (orden LIKE '%%*DEV_21%%' OR cod_sec = '*DEV_21')
                        AND valor_unitario > 0
                        AND editado_manualmente = 0
                        AND lot_esc NOT IN (SELECT lot_esc FROM planillas_revisadas)
                    """

                    cursor_update.execute(query_update_bcs, (fecha_desde_bcs, fecha_hasta_bcs))
                    filas_actualizadas = cursor_update.rowcount
                    conn.commit()
                    cursor_update.close()

                    st.success(f"✅ Se aplicó precio $0 a **{filas_actualizadas} gestiones**")
                    st.balloons()
                    st.rerun()

                except Exception as e:
                    conn.rollback()
                    st.error(f"Error al actualizar: {e}")
                    import traceback
                    st.code(traceback.format_exc())

        else:
            st.success("No hay gestiones de Banco Caja Social con *DEV_21 pendientes de ajustar en el periodo seleccionado")

        st.divider()

        # =====================================================
        # SECCION: Verificar estado general en BD
        # =====================================================
        st.markdown("### 🔍 Verificar Estado en Base de Datos")

        if st.button("🔍 Verificar todos los registros BCS *DEV_21 en BD", key="btn_verificar_general"):
            with st.spinner("Consultando base de datos..."):
                cursor_check = conn.cursor(dictionary=True)

                # Estadísticas generales de Banco Caja Social con *DEV_21 (sin filtro de fecha)
                cursor_check.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN valor_unitario = 0 THEN 1 ELSE 0 END) as con_precio_cero,
                        SUM(CASE WHEN valor_unitario > 0 THEN 1 ELSE 0 END) as con_precio_mayor,
                        SUM(CASE WHEN cod_sec = '*DEV_21' THEN 1 ELSE 0 END) as con_codsec,
                        SUM(CASE WHEN cod_sec IS NULL OR cod_sec = '' THEN 1 ELSE 0 END) as sin_codsec,
                        SUM(CASE WHEN valor_unitario > 0 THEN valor_total ELSE 0 END) as valor_pendiente
                    FROM gestiones_mensajero
                    WHERE UPPER(TRIM(cliente)) = 'BANCO CAJA SOCIAL'
                    AND (orden LIKE '%%*DEV_21%%' OR cod_sec = '*DEV_21')
                """)
                stats = cursor_check.fetchone()

                if stats['total'] > 0:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total en BD", f"{stats['total']:,}")
                    with col2:
                        st.metric("✅ Con precio $0", f"{stats['con_precio_cero']:,}")
                    with col3:
                        st.metric("⚠️ Con precio > $0", f"{stats['con_precio_mayor']:,}", f"${stats['valor_pendiente']:,.0f}" if stats['valor_pendiente'] else None)

                    col4, col5 = st.columns(2)
                    with col4:
                        st.metric("Con cod_sec='*DEV_21'", f"{stats['con_codsec']:,}")
                    with col5:
                        st.metric("Sin cod_sec", f"{stats['sin_codsec']:,}")

                    # Mostrar detalle de los que tienen precio > 0
                    if stats['con_precio_mayor'] > 0:
                        st.markdown("##### ⚠️ Registros con precio > $0 (pendientes de ajustar):")
                        cursor_check.execute("""
                            SELECT id, fecha_escaner, cod_mensajero, orden,
                                   total_seriales, valor_unitario, valor_total, cod_sec
                            FROM gestiones_mensajero
                            WHERE UPPER(TRIM(cliente)) = 'BANCO CAJA SOCIAL'
                            AND (orden LIKE '%%*DEV_21%%' OR cod_sec = '*DEV_21')
                            AND valor_unitario > 0
                            ORDER BY fecha_escaner DESC
                            LIMIT 100
                        """)
                        pendientes = cursor_check.fetchall()
                        df_pendientes = pd.DataFrame(pendientes)
                        df_pendientes['valor_unitario'] = df_pendientes['valor_unitario'].apply(lambda x: f"${x:,.0f}")
                        df_pendientes['valor_total'] = df_pendientes['valor_total'].apply(lambda x: f"${x:,.0f}")
                        st.dataframe(df_pendientes, use_container_width=True, hide_index=True)
                    else:
                        st.success("✅ Todos los registros de BCS *DEV_21 ya tienen precio $0")
                else:
                    st.info("No se encontraron registros de Banco Caja Social con *DEV_21 en la base de datos")

                cursor_check.close()

        st.divider()

        # =====================================================
        # SECCION: Actualizar cod_sec desde CSV histórico
        # =====================================================
        st.markdown("### 📂 Actualizar cod_sec desde CSV Histórico")
        st.info("Carga un CSV de agrupación para actualizar el campo cod_sec en registros existentes (hace match por lot_esc, orden, cliente, cod_mensajero)")

        # Opción de carga: archivo local o upload
        metodo_carga = st.radio(
            "Método de carga:",
            ["📁 Ruta local (archivos grandes)", "📤 Subir archivo (máx 200MB)"],
            key="metodo_carga_codsec",
            horizontal=True
        )

        df_codsec = None

        if metodo_carga == "📁 Ruta local (archivos grandes)":
            ruta_csv = st.text_input(
                "Ruta completa del archivo CSV:",
                value="/mnt/c/Users/mcomb/Desktop/Carvajal/python/basesHisto.csv",
                key="ruta_csv_codsec"
            )
            if st.button("📂 Cargar archivo", key="btn_cargar_local"):
                if os.path.exists(ruta_csv):
                    try:
                        with st.spinner("Cargando archivo grande..."):
                            df_codsec = pd.read_csv(ruta_csv, low_memory=False)
                            st.session_state['df_codsec_loaded'] = df_codsec
                        st.success(f"Archivo cargado: {len(df_codsec):,} registros")
                    except Exception as e:
                        st.error(f"Error al cargar: {e}")
                else:
                    st.error(f"Archivo no encontrado: {ruta_csv}")

            # Recuperar del session state si ya se cargó
            if 'df_codsec_loaded' in st.session_state:
                df_codsec = st.session_state['df_codsec_loaded']

        else:
            uploaded_file_codsec = st.file_uploader("Selecciona el archivo CSV de agrupación", type="csv", key="csv_codsec")
            if uploaded_file_codsec is not None:
                df_codsec = pd.read_csv(uploaded_file_codsec)

        if df_codsec is not None:

            # Verificar columnas requeridas
            cols_requeridas = ['lot_esc', 'orden', 'no_entidad', 'cod_men', 'cod_sec']
            cols_faltantes = [c for c in cols_requeridas if c not in df_codsec.columns]

            if cols_faltantes:
                st.error(f"Columnas faltantes: {cols_faltantes}")
            else:
                # Normalizar datos - convertir floats a int para quitar .0
                df_codsec['cod_men'] = df_codsec['cod_men'].fillna(999).astype(float).astype(int).astype(str).str.zfill(4)

                # Función para convertir valores numéricos (quitar .0)
                def convertir_numero(x):
                    if pd.isna(x):
                        return ''
                    x_str = str(x).strip()
                    if x_str == '' or x_str.lower() == 'nan':
                        return ''
                    try:
                        return str(int(float(x_str)))
                    except (ValueError, TypeError):
                        return x_str

                df_codsec['lot_esc'] = df_codsec['lot_esc'].apply(convertir_numero)
                df_codsec['orden'] = df_codsec['orden'].apply(convertir_numero)
                df_codsec['cod_sec'] = df_codsec['cod_sec'].fillna('').astype(str)

                # Filtrar solo registros con cod_sec no vacío
                df_con_codsec = df_codsec[df_codsec['cod_sec'].str.strip() != ''].copy()

                st.success(f"Archivo cargado: {len(df_codsec)} registros totales, {len(df_con_codsec)} con cod_sec")

                # Vista previa
                with st.expander("Vista previa de registros con cod_sec", expanded=False):
                    st.dataframe(df_con_codsec[['lot_esc', 'orden', 'no_entidad', 'cod_men', 'cod_sec']].head(50), use_container_width=True)

                # Filtrar solo *DEV_21 para Banco Caja Social
                df_dev21 = df_con_codsec[
                    (df_con_codsec['cod_sec'] == '*DEV_21') &
                    (df_con_codsec['no_entidad'].str.upper().str.strip() == 'BANCO CAJA SOCIAL')
                ].copy()

                if not df_dev21.empty:
                    st.warning(f"Se encontraron {len(df_dev21)} seriales de Banco Caja Social con *DEV_21 en el CSV")

                    # Obtener órdenes únicas del CSV
                    ordenes_csv = df_dev21['orden'].unique()
                    ordenes_csv = [o for o in ordenes_csv if o and o != '']
                    st.info(f"Órdenes únicas con *DEV_21: {len(ordenes_csv)}")

                    with st.expander("Ver órdenes únicas del CSV", expanded=False):
                        st.write(ordenes_csv[:100])  # Mostrar primeras 100

                    # Verificar cuáles órdenes existen en la BD
                    st.markdown("#### 📊 Verificar órdenes en Base de Datos")

                    if st.button("🔍 Verificar órdenes en BD", key="btn_verificar_ordenes"):
                        with st.spinner("Verificando órdenes en BD..."):
                            cursor_check = conn.cursor(dictionary=True)

                            # Obtener órdenes de Banco Caja Social en BD
                            cursor_check.execute("""
                                SELECT DISTINCT orden, cod_sec, valor_unitario
                                FROM gestiones_mensajero
                                WHERE UPPER(TRIM(cliente)) = 'BANCO CAJA SOCIAL'
                            """)
                            ordenes_bd = cursor_check.fetchall()
                            ordenes_bd_set = {str(o['orden']) for o in ordenes_bd}

                            # Encontrar coincidencias
                            ordenes_coinciden = [o for o in ordenes_csv if o in ordenes_bd_set]

                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Órdenes en CSV", len(ordenes_csv))
                            with col2:
                                st.metric("Órdenes en BD (BCS)", len(ordenes_bd_set))
                            with col3:
                                st.metric("Coincidencias", len(ordenes_coinciden))

                            if ordenes_coinciden:
                                # Verificar estado de las órdenes coincidentes
                                placeholders = ','.join(['%s'] * len(ordenes_coinciden))
                                cursor_check.execute(f"""
                                    SELECT
                                        COUNT(*) as total,
                                        SUM(CASE WHEN valor_unitario = 0 THEN 1 ELSE 0 END) as con_precio_cero,
                                        SUM(CASE WHEN valor_unitario > 0 THEN 1 ELSE 0 END) as con_precio_mayor,
                                        SUM(CASE WHEN cod_sec = '*DEV_21' THEN 1 ELSE 0 END) as con_codsec,
                                        SUM(CASE WHEN valor_unitario > 0 THEN valor_total ELSE 0 END) as valor_pendiente
                                    FROM gestiones_mensajero
                                    WHERE UPPER(TRIM(cliente)) = 'BANCO CAJA SOCIAL'
                                    AND orden IN ({placeholders})
                                """, tuple(ordenes_coinciden))
                                stats = cursor_check.fetchone()

                                st.markdown("##### Estado de órdenes coincidentes:")
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Total gestiones", f"{stats['total']:,}")
                                with col2:
                                    st.metric("✅ Precio $0", f"{stats['con_precio_cero']:,}")
                                with col3:
                                    st.metric("⚠️ Precio > $0", f"{stats['con_precio_mayor']:,}")

                                col4, col5 = st.columns(2)
                                with col4:
                                    st.metric("Con cod_sec", f"{stats['con_codsec']:,}")
                                with col5:
                                    st.metric("Valor pendiente", f"${stats['valor_pendiente']:,.0f}" if stats['valor_pendiente'] else "$0")

                                # Guardar órdenes coincidentes en session state
                                st.session_state['ordenes_dev21_coinciden'] = ordenes_coinciden

                                # Mostrar detalle
                                if stats['con_precio_mayor'] > 0:
                                    cursor_check.execute(f"""
                                        SELECT id, fecha_escaner, orden, total_seriales,
                                               valor_unitario, valor_total, cod_sec
                                        FROM gestiones_mensajero
                                        WHERE UPPER(TRIM(cliente)) = 'BANCO CAJA SOCIAL'
                                        AND orden IN ({placeholders})
                                        AND valor_unitario > 0
                                        ORDER BY orden
                                        LIMIT 100
                                    """, tuple(ordenes_coinciden))
                                    pendientes = cursor_check.fetchall()
                                    df_pend = pd.DataFrame(pendientes)
                                    df_pend['valor_unitario'] = df_pend['valor_unitario'].apply(lambda x: f"${x:,.0f}")
                                    df_pend['valor_total'] = df_pend['valor_total'].apply(lambda x: f"${x:,.0f}")
                                    st.dataframe(df_pend, use_container_width=True, hide_index=True)
                            else:
                                st.warning("No se encontraron coincidencias entre las órdenes del CSV y la BD")

                            cursor_check.close()

                    st.divider()

                    # Botón para actualizar cod_sec Y precio en un solo paso
                    st.markdown("#### 🚀 Actualizar cod_sec y Precio $0")
                    st.info("Este botón actualiza el campo cod_sec='*DEV_21' y aplica precio $0 a las órdenes que existen en la BD")

                    if 'ordenes_dev21_coinciden' in st.session_state and st.session_state['ordenes_dev21_coinciden']:
                        ordenes_a_actualizar = st.session_state['ordenes_dev21_coinciden']
                        st.success(f"Órdenes a actualizar: {len(ordenes_a_actualizar)}")

                        confirmar_update = st.checkbox("✅ Confirmo actualizar cod_sec y precio $0", key="confirmar_update_dev21")

                        if st.button("🔄 Actualizar cod_sec y Precio $0", type="primary", key="btn_update_codsec", disabled=not confirmar_update):
                            try:
                                cursor_upd = conn.cursor()

                                # Actualizar en un solo UPDATE usando IN
                                placeholders = ','.join(['%s'] * len(ordenes_a_actualizar))
                                cursor_upd.execute(f"""
                                    UPDATE gestiones_mensajero
                                    SET cod_sec = '*DEV_21', valor_unitario = 0, valor_total = 0
                                    WHERE UPPER(TRIM(cliente)) = 'BANCO CAJA SOCIAL'
                                    AND orden IN ({placeholders})
                                """, tuple(ordenes_a_actualizar))

                                actualizados = cursor_upd.rowcount
                                conn.commit()
                                cursor_upd.close()

                                st.success(f"✅ Se actualizaron {actualizados} gestiones con cod_sec='*DEV_21' y precio $0")
                                st.balloons()
                                # Limpiar session state
                                del st.session_state['ordenes_dev21_coinciden']
                                st.rerun()

                            except Exception as e:
                                conn.rollback()
                                st.error(f"Error: {e}")
                                import traceback
                                st.code(traceback.format_exc())
                    else:
                        st.warning("Primero presiona 'Verificar órdenes en BD' para identificar las órdenes a actualizar")
                else:
                    st.info("No se encontraron registros de Banco Caja Social con cod_sec = '*DEV_21' en el CSV")

        st.divider()

        # Mostrar historial de gestiones ya ajustadas
        st.markdown("### 📋 Gestiones ya ajustadas (precio $0)")

        query_ajustadas = """
            SELECT
                gm.id, gm.fecha_escaner, gm.cod_mensajero, gm.orden, gm.cliente,
                gm.tipo_gestion, gm.total_seriales, gm.cod_sec
            FROM gestiones_mensajero gm
            WHERE gm.fecha_registro BETWEEN %s AND %s
            AND UPPER(TRIM(gm.cliente)) = 'BANCO CAJA SOCIAL'
            AND (gm.orden LIKE '%%*DEV_21%%' OR gm.cod_sec = '*DEV_21')
            AND gm.valor_unitario = 0
            ORDER BY gm.fecha_escaner DESC
            LIMIT 100
        """

        cursor.execute(query_ajustadas, (fecha_desde_bcs, fecha_hasta_bcs))
        ajustadas = cursor.fetchall()

        if ajustadas:
            df_ajustadas = pd.DataFrame(ajustadas)
            st.dataframe(df_ajustadas, use_container_width=True, hide_index=True)
            st.caption(f"Mostrando {len(ajustadas)} registros (máximo 100)")
        else:
            st.info("No hay gestiones ajustadas en el periodo seleccionado")

    except Exception as e:
        st.error(f"Error: {e}")
        import traceback
        st.code(traceback.format_exc())

if 'cursor' in locals():
    cursor.close()
