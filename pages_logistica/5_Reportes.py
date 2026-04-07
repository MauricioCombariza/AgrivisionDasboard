import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, date
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_connection import conectar_logistica


# CSS personalizado para mejorar la apariencia
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 15px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .metric-card-green {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
    }
    .metric-card-blue {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
    }
    .metric-card-orange {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    }
    .metric-card-red {
        background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%);
    }
    .metric-value {
        font-size: 28px;
        font-weight: bold;
        margin: 10px 0;
    }
    .metric-label {
        font-size: 14px;
        opacity: 0.9;
    }
    .section-header {
        background: linear-gradient(90deg, #1a1a2e 0%, #16213e 100%);
        color: white;
        padding: 15px 20px;
        border-radius: 10px;
        margin: 20px 0;
        font-size: 18px;
        font-weight: bold;
    }
    .profit-positive {
        color: #00c853;
        font-weight: bold;
    }
    .profit-negative {
        color: #ff1744;
        font-weight: bold;
    }
    .client-card {
        border-left: 4px solid #667eea;
        padding-left: 15px;
        margin: 10px 0;
    }
    .stMetric {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# Header principal
st.markdown("# 📊 Centro de Reportes y Análisis")
st.markdown("---")

conn = conectar_logistica()
if not conn:
    st.stop()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "💰 Rentabilidad General",
    "📦 Estado de Órdenes",
    "👥 Desempeño Personal",
    "📋 Detalle por Orden",
    "📈 Comparativo Mensual",
    "💳 Cartera y Rentabilidad Real"
])

with tab1:
    # Filtros en un contenedor más elegante
    with st.container():
        st.markdown("#### 🔍 Filtros de Período")
        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            anio = st.selectbox("📅 Año", options=list(range(2024, 2031)), index=list(range(2024, 2031)).index(date.today().year))
        with col2:
            meses_lista = ["Todos", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                          "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            mes = st.selectbox("📆 Mes", meses_lista)

    st.markdown("---")

    # ========== DEBUG: Diagnóstico de Imile ==========
    with st.expander("🔍 Diagnóstico IMILE SAS", expanded=False):
        try:
            cursor_debug = conn.cursor(dictionary=True)

            # Precios configurados para Imile
            cursor_debug.execute("""
                SELECT pc.tipo_servicio, pc.ambito, pc.tipo_operacion,
                       pc.precio_unitario, pc.costo_mensajero_entrega, pc.costo_mensajero_devolucion
                FROM precios_cliente pc
                JOIN clientes c ON pc.cliente_id = c.id
                WHERE UPPER(c.nombre_empresa) LIKE '%IMILE%' AND pc.activo = TRUE
            """)
            precios_imile = cursor_debug.fetchall()

            if precios_imile:
                st.markdown("**Precios configurados para IMILE:**")
                df_precios = pd.DataFrame(precios_imile)
                st.dataframe(df_precios, use_container_width=True, hide_index=True)

            # Valores en órdenes de Imile del mes seleccionado
            cursor_debug.execute("""
                SELECT o.numero_orden, o.cantidad_total, o.valor_total,
                       o.cantidad_local, o.cantidad_nacional
                FROM ordenes o
                JOIN clientes c ON o.cliente_id = c.id
                WHERE UPPER(c.nombre_empresa) LIKE '%IMILE%'
                AND o.estado = 'activa'
                ORDER BY o.fecha_recepcion DESC
                LIMIT 10
            """)
            ordenes_imile = cursor_debug.fetchall()

            if ordenes_imile:
                st.markdown("**Últimas 10 órdenes de IMILE (activas):**")
                df_ord = pd.DataFrame(ordenes_imile)
                if not df_ord.empty and 'cantidad_total' in df_ord.columns:
                    df_ord['valor_por_item'] = df_ord.apply(
                        lambda r: r['valor_total'] / r['cantidad_total'] if r['cantidad_total'] and r['cantidad_total'] > 0 else 0, axis=1
                    )
                st.dataframe(df_ord, use_container_width=True, hide_index=True)

            # Gestiones de mensajero para Imile
            cursor_debug.execute("""
                SELECT COUNT(*) as total_gestiones,
                       SUM(total_seriales) as total_seriales,
                       SUM(valor_total) as costo_total_mensajeros,
                       AVG(valor_unitario) as valor_unitario_promedio
                FROM gestiones_mensajero
                WHERE UPPER(cliente) LIKE '%IMILE%'
                AND YEAR(fecha_registro) = YEAR(CURRENT_DATE)
                AND MONTH(fecha_registro) = MONTH(CURRENT_DATE)
            """)
            gestiones_imile = cursor_debug.fetchone()

            if gestiones_imile and gestiones_imile['total_gestiones']:
                st.markdown("**Gestiones de mensajero IMILE (mes actual):**")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Gestiones", gestiones_imile['total_gestiones'])
                with col2:
                    st.metric("Seriales", f"{gestiones_imile['total_seriales']:,}")
                with col3:
                    st.metric("Costo Mensajeros", f"${gestiones_imile['costo_total_mensajeros']:,.0f}")
                with col4:
                    st.metric("$/unidad promedio", f"${gestiones_imile['valor_unitario_promedio']:,.0f}")

            cursor_debug.close()
        except Exception as e:
            st.error(f"Error en diagnóstico: {e}")

    try:
        cursor = conn.cursor(dictionary=True)

        # Determinar mes numerico
        if mes != "Todos":
            mes_num = meses_lista.index(mes)
        else:
            mes_num = None

        # ============ OBTENER TODOS LOS DATOS ============

        # 1. Costos de mensajeros por cliente - filtrado por fecha de la GESTIÓN (fecha_escaner)
        # Así se capturan todas las gestiones realizadas en el período, sin importar la fecha de la orden
        if mes_num:
            cursor.execute("""
                SELECT
                    UPPER(TRIM(c.nombre_empresa)) as cliente,
                    SUM(gm.valor_total) as costo_mensajeros
                FROM gestiones_mensajero gm
                JOIN ordenes o ON TRIM(REPLACE(gm.orden, '.0', '')) = TRIM(REPLACE(o.numero_orden, '.0', ''))
                JOIN clientes c ON o.cliente_id = c.id
                WHERE YEAR(gm.fecha_escaner) = %s AND MONTH(gm.fecha_escaner) = %s
                GROUP BY UPPER(TRIM(c.nombre_empresa))
            """, (anio, mes_num))
        else:
            cursor.execute("""
                SELECT
                    UPPER(TRIM(c.nombre_empresa)) as cliente,
                    SUM(gm.valor_total) as costo_mensajeros
                FROM gestiones_mensajero gm
                JOIN ordenes o ON TRIM(REPLACE(gm.orden, '.0', '')) = TRIM(REPLACE(o.numero_orden, '.0', ''))
                JOIN clientes c ON o.cliente_id = c.id
                WHERE YEAR(gm.fecha_escaner) = %s
                GROUP BY UPPER(TRIM(c.nombre_empresa))
            """, (anio,))

        costos_mensajeros = {r['cliente']: float(r['costo_mensajeros'] or 0) for r in cursor.fetchall()}
        total_costo_mensajeros = sum(costos_mensajeros.values())

        # 2. Costos de transporte por cliente
        if mes_num:
            cursor.execute("""
                SELECT UPPER(TRIM(c.nombre_empresa)) as cliente, SUM(dft.costo_asignado) as costo_transporte
                FROM detalle_facturas_transporte dft
                JOIN facturas_transporte ft ON dft.factura_id = ft.id
                JOIN ordenes o ON dft.orden_id = o.id
                JOIN clientes c ON o.cliente_id = c.id
                WHERE YEAR(ft.fecha_factura) = %s AND MONTH(ft.fecha_factura) = %s
                AND ft.estado != 'anulada'
                GROUP BY UPPER(TRIM(c.nombre_empresa))
            """, (anio, mes_num))
        else:
            cursor.execute("""
                SELECT UPPER(TRIM(c.nombre_empresa)) as cliente, SUM(dft.costo_asignado) as costo_transporte
                FROM detalle_facturas_transporte dft
                JOIN facturas_transporte ft ON dft.factura_id = ft.id
                JOIN ordenes o ON dft.orden_id = o.id
                JOIN clientes c ON o.cliente_id = c.id
                WHERE YEAR(ft.fecha_factura) = %s
                AND ft.estado != 'anulada'
                GROUP BY UPPER(TRIM(c.nombre_empresa))
            """, (anio,))

        costos_transporte = {r['cliente']: float(r['costo_transporte'] or 0) for r in cursor.fetchall()}
        total_costo_transporte = sum(costos_transporte.values())

        # 3. Gastos administrativos
        if mes_num:
            cursor.execute("""
                SELECT SUM(monto) as total_gastos
                FROM gastos_administrativos
                WHERE YEAR(fecha) = %s AND MONTH(fecha) = %s
            """, (anio, mes_num))
        else:
            cursor.execute("""
                SELECT SUM(monto) as total_gastos
                FROM gastos_administrativos
                WHERE YEAR(fecha) = %s
            """, (anio,))

        result_gastos = cursor.fetchone()
        total_gastos_admin = float(result_gastos['total_gastos'] or 0) if result_gastos else 0

        # 4. Desglose de gastos administrativos por categoría
        if mes_num:
            cursor.execute("""
                SELECT categoria, SUM(monto) as total
                FROM gastos_administrativos
                WHERE YEAR(fecha) = %s AND MONTH(fecha) = %s
                GROUP BY categoria
                ORDER BY total DESC
            """, (anio, mes_num))
        else:
            cursor.execute("""
                SELECT categoria, SUM(monto) as total
                FROM gastos_administrativos
                WHERE YEAR(fecha) = %s
                GROUP BY categoria
                ORDER BY total DESC
            """, (anio,))

        gastos_por_categoria = {r['categoria']: float(r['total'] or 0) for r in cursor.fetchall()}

        # 4.5 Gastos de Nómina
        if mes_num:
            cursor.execute("""
                SELECT
                    SUM(costo_total_empleado) as total_nomina,
                    SUM(salario_base + auxilio_transporte + auxilio_no_salarial) as total_salarios,
                    SUM(total_seguridad_social) as total_seguridad_social,
                    SUM(total_provisiones) as total_provisiones
                FROM nomina_provisiones
                WHERE periodo_anio = %s AND periodo_mes = %s
            """, (anio, mes_num))
        else:
            cursor.execute("""
                SELECT
                    SUM(costo_total_empleado) as total_nomina,
                    SUM(salario_base + auxilio_transporte + auxilio_no_salarial) as total_salarios,
                    SUM(total_seguridad_social) as total_seguridad_social,
                    SUM(total_provisiones) as total_provisiones
                FROM nomina_provisiones
                WHERE periodo_anio = %s
            """, (anio,))

        result_nomina = cursor.fetchone()
        total_nomina = float(result_nomina['total_nomina'] or 0) if result_nomina else 0
        total_salarios = float(result_nomina['total_salarios'] or 0) if result_nomina else 0
        total_seg_social = float(result_nomina['total_seguridad_social'] or 0) if result_nomina else 0
        total_provisiones = float(result_nomina['total_provisiones'] or 0) if result_nomina else 0

        # 4.6 Costos de Alistamiento (registro_horas + registro_labores + subsidio_transporte)
        # Mismas tablas que usa Facturación → Pago Personal → Alistamiento
        if mes_num:
            cursor.execute("""
                SELECT SUM(total) as total_alistamiento FROM (
                    SELECT total FROM registro_horas
                    WHERE YEAR(fecha) = %s AND MONTH(fecha) = %s
                    UNION ALL
                    SELECT total FROM registro_labores
                    WHERE YEAR(fecha) = %s AND MONTH(fecha) = %s
                    UNION ALL
                    SELECT total FROM subsidio_transporte
                    WHERE YEAR(fecha) = %s AND MONTH(fecha) = %s
                ) t
            """, (anio, mes_num, anio, mes_num, anio, mes_num))
        else:
            cursor.execute("""
                SELECT SUM(total) as total_alistamiento FROM (
                    SELECT total FROM registro_horas
                    WHERE YEAR(fecha) = %s
                    UNION ALL
                    SELECT total FROM registro_labores
                    WHERE YEAR(fecha) = %s
                    UNION ALL
                    SELECT total FROM subsidio_transporte
                    WHERE YEAR(fecha) = %s
                ) t
            """, (anio, anio, anio))

        result_alistamiento = cursor.fetchone()
        total_alistamiento = float(result_alistamiento['total_alistamiento'] or 0) if result_alistamiento else 0

        # 5. Entregas y devoluciones por cliente - filtrado por fecha de la GESTIÓN (fecha_escaner)
        if mes_num:
            cursor.execute("""
                SELECT UPPER(TRIM(c.nombre_empresa)) as cliente,
                    SUM(CASE WHEN gm.tipo_gestion LIKE '%%Entrega%%' THEN gm.total_seriales ELSE 0 END) as entregados,
                    SUM(CASE WHEN gm.tipo_gestion NOT LIKE '%%Entrega%%' THEN gm.total_seriales ELSE 0 END) as devoluciones
                FROM gestiones_mensajero gm
                JOIN ordenes o ON TRIM(REPLACE(gm.orden, '.0', '')) = TRIM(REPLACE(o.numero_orden, '.0', ''))
                JOIN clientes c ON o.cliente_id = c.id
                WHERE YEAR(gm.fecha_escaner) = %s AND MONTH(gm.fecha_escaner) = %s
                GROUP BY UPPER(TRIM(c.nombre_empresa))
            """, (anio, mes_num))
        else:
            cursor.execute("""
                SELECT UPPER(TRIM(c.nombre_empresa)) as cliente,
                    SUM(CASE WHEN gm.tipo_gestion LIKE '%%Entrega%%' THEN gm.total_seriales ELSE 0 END) as entregados,
                    SUM(CASE WHEN gm.tipo_gestion NOT LIKE '%%Entrega%%' THEN gm.total_seriales ELSE 0 END) as devoluciones
                FROM gestiones_mensajero gm
                JOIN ordenes o ON TRIM(REPLACE(gm.orden, '.0', '')) = TRIM(REPLACE(o.numero_orden, '.0', ''))
                JOIN clientes c ON o.cliente_id = c.id
                WHERE YEAR(gm.fecha_escaner) = %s
                GROUP BY UPPER(TRIM(c.nombre_empresa))
            """, (anio,))

        gestiones_cliente = {r['cliente']: {'entregados': int(r['entregados'] or 0), 'devoluciones': int(r['devoluciones'] or 0)} for r in cursor.fetchall()}

        # 6. Query principal de ordenes
        # NOTA: costo_total de ordenes NO se usa porque duplica registro_horas/labores y gestiones_mensajero
        query = """
            SELECT
                c.nombre_empresa as cliente,
                COUNT(DISTINCT o.id) as total_ordenes,
                SUM(o.cantidad_total) as total_items,
                SUM(o.valor_total) as ingresos,
                0 as costos_operativos,
                SUM(o.valor_total) as utilidad_base
            FROM clientes c
            LEFT JOIN ordenes o ON c.id = o.cliente_id
            WHERE YEAR(o.fecha_recepcion) = %s
        """

        params = [anio]

        if mes_num:
            query += " AND MONTH(o.fecha_recepcion) = %s"
            params.append(mes_num)

        query += " GROUP BY c.id, c.nombre_empresa HAVING COUNT(DISTINCT o.id) > 0 ORDER BY utilidad_base DESC"

        cursor.execute(query, tuple(params))
        resultados = cursor.fetchall()

        # 7. Detalle de órdenes por cliente (para mostrar en el expander)
        query_ordenes = """
            SELECT
                UPPER(TRIM(c.nombre_empresa)) as cliente,
                o.numero_orden,
                o.cantidad_total as items_totales,
                COALESCE(o.cantidad_entregados_local, 0) + COALESCE(o.cantidad_entregados_nacional, 0) as entregas,
                COALESCE(o.cantidad_devolucion_local, 0) + COALESCE(o.cantidad_devolucion_nacional, 0) as devoluciones,
                o.fecha_recepcion,
                o.estado
            FROM ordenes o
            JOIN clientes c ON o.cliente_id = c.id
            WHERE YEAR(o.fecha_recepcion) = %s
        """
        params_ordenes = [anio]

        if mes_num:
            query_ordenes += " AND MONTH(o.fecha_recepcion) = %s"
            params_ordenes.append(mes_num)

        query_ordenes += " ORDER BY o.fecha_recepcion DESC"

        cursor.execute(query_ordenes, tuple(params_ordenes))
        ordenes_detalle = cursor.fetchall()

        # Agrupar órdenes por cliente
        ordenes_por_cliente = {}
        for orden in ordenes_detalle:
            cliente_key = orden['cliente']
            if cliente_key not in ordenes_por_cliente:
                ordenes_por_cliente[cliente_key] = []
            ordenes_por_cliente[cliente_key].append(orden)

        if resultados or costos_mensajeros or gestiones_cliente:
            # Procesar resultados
            datos_procesados = []
            for r in resultados:
                cliente_upper = r['cliente'].strip().upper()
                costo_msg = float(costos_mensajeros.get(cliente_upper, 0))
                costo_transp = float(costos_transporte.get(cliente_upper, 0))
                gestion_data = gestiones_cliente.get(cliente_upper, {'entregados': 0, 'devoluciones': 0})
                ingresos = float(r['ingresos'] or 0)
                costos_op = float(r['costos_operativos'] or 0)
                costos_totales = costos_op + costo_msg + costo_transp
                utilidad_real = ingresos - costos_totales
                margen = (utilidad_real / ingresos * 100) if ingresos > 0 else 0

                datos_procesados.append({
                    'cliente': r['cliente'],
                    'total_ordenes': r['total_ordenes'],
                    'total_items': r['total_items'],
                    'entregados': gestion_data['entregados'],
                    'devoluciones': gestion_data['devoluciones'],
                    'ingresos': ingresos,
                    'costos_operativos': costos_op,
                    'costo_mensajeros': costo_msg,
                    'costo_transporte': costo_transp,
                    'costos_totales': costos_totales,
                    'utilidad': utilidad_real,
                    'margen_porcentaje': margen
                })

            datos_procesados = sorted(datos_procesados, key=lambda x: x['utilidad'], reverse=True)

            # ============ DASHBOARD PRINCIPAL ============

            # Calcular totales
            total_ingresos = sum([r['ingresos'] for r in datos_procesados])
            # costos_operativos de ordenes NO se suma — duplica registro_horas/labores y gestiones_mensajero
            total_costos_directos = total_costo_mensajeros + total_costo_transporte + total_alistamiento
            utilidad_bruta = total_ingresos - total_costos_directos
            total_gastos_fijos = total_gastos_admin + total_nomina
            utilidad_neta = utilidad_bruta - total_gastos_fijos
            margen_bruto = (utilidad_bruta / total_ingresos * 100) if total_ingresos > 0 else 0
            margen_neto = (utilidad_neta / total_ingresos * 100) if total_ingresos > 0 else 0

            # ===== SECCIÓN 1: RESUMEN EJECUTIVO =====
            st.markdown('<div class="section-header">📈 RESUMEN EJECUTIVO</div>', unsafe_allow_html=True)

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    label="💵 Ingresos Totales",
                    value=f"${total_ingresos:,.0f}",
                    delta=None
                )

            with col2:
                st.metric(
                    label="📊 Utilidad Bruta",
                    value=f"${utilidad_bruta:,.0f}",
                    delta=f"{margen_bruto:.1f}% margen"
                )

            with col3:
                delta_color = "normal" if utilidad_neta >= 0 else "inverse"
                st.metric(
                    label="💰 Utilidad Neta",
                    value=f"${utilidad_neta:,.0f}",
                    delta=f"{margen_neto:.1f}% margen",
                    delta_color=delta_color
                )

            with col4:
                total_entregados = sum([r['entregados'] for r in datos_procesados])
                total_devoluciones = sum([r['devoluciones'] for r in datos_procesados])
                tasa_exito = (total_entregados / (total_entregados + total_devoluciones) * 100) if (total_entregados + total_devoluciones) > 0 else 0
                st.metric(
                    label="✅ Tasa de Éxito",
                    value=f"{tasa_exito:.1f}%",
                    delta=f"{total_entregados:,} entregas"
                )

            st.markdown("---")

            # ===== SECCIÓN 2: DESGLOSE DE COSTOS =====
            st.markdown('<div class="section-header">💸 DESGLOSE DE COSTOS</div>', unsafe_allow_html=True)

            col1, col2 = st.columns([2, 1])

            with col1:
                # Tabla de costos
                costos_data = {
                    'Concepto': [
                        '🏍️ Costo Mensajeros',
                        '🏭 Alistamiento / Labores',
                        '🚚 Costo Transporte',
                        '🏢 Gastos Administrativos',
                        '👥 Nómina y Provisiones'
                    ],
                    'Monto': [
                        f"${total_costo_mensajeros:,.0f}",
                        f"${total_alistamiento:,.0f}",
                        f"${total_costo_transporte:,.0f}",
                        f"${total_gastos_admin:,.0f}",
                        f"${total_nomina:,.0f}"
                    ],
                    '% de Ingresos': [
                        f"{(total_costo_mensajeros/total_ingresos*100) if total_ingresos > 0 else 0:.1f}%",
                        f"{(total_alistamiento/total_ingresos*100) if total_ingresos > 0 else 0:.1f}%",
                        f"{(total_costo_transporte/total_ingresos*100) if total_ingresos > 0 else 0:.1f}%",
                        f"{(total_gastos_admin/total_ingresos*100) if total_ingresos > 0 else 0:.1f}%",
                        f"{(total_nomina/total_ingresos*100) if total_ingresos > 0 else 0:.1f}%"
                    ]
                }
                df_costos = pd.DataFrame(costos_data)
                st.dataframe(df_costos, use_container_width=True, hide_index=True)

                # Total de costos
                total_todos_costos = total_costo_mensajeros + total_alistamiento + total_costo_transporte + total_gastos_admin + total_nomina
                st.markdown(f"**Total Costos: ${total_todos_costos:,.0f}** ({(total_todos_costos/total_ingresos*100) if total_ingresos > 0 else 0:.1f}% de ingresos)")

            with col2:
                # Gráfico de costos
                if gastos_por_categoria:
                    st.markdown("**📊 Gastos Admin. por Categoría**")
                    CATEGORIAS_NOMBRES = {
                        'mantenimiento': 'Mantenimiento',
                        'polizas': 'Pólizas',
                        'servicios_publicos': 'Serv. Públicos',
                        'caja_menor': 'Caja Menor',
                        'papeleria': 'Papelería',
                        'aseo': 'Aseo',
                        'internet': 'Internet',
                        'software': 'Software',
                        'alquiler_equipos': 'Alq. Equipos',
                        'arriendo': 'Arriendo',
                        'honorarios': 'Honorarios',
                        'impuestos': 'Impuestos',
                        'otros': 'Otros'
                    }
                    df_gastos = pd.DataFrame({
                        'Categoría': [CATEGORIAS_NOMBRES.get(k, k) for k in gastos_por_categoria.keys()],
                        'Monto': list(gastos_por_categoria.values())
                    })
                    st.bar_chart(df_gastos.set_index('Categoría'))

                # Desglose de Nómina
                if total_nomina > 0:
                    st.markdown("**👥 Desglose de Nómina**")
                    nomina_desglose = pd.DataFrame({
                        'Concepto': ['Salarios y Auxilios', 'Seguridad Social', 'Provisiones'],
                        'Monto': [f"${total_salarios:,.0f}", f"${total_seg_social:,.0f}", f"${total_provisiones:,.0f}"]
                    })
                    st.dataframe(nomina_desglose, use_container_width=True, hide_index=True)

            st.markdown("---")

            # ===== SECCIÓN 3: RENTABILIDAD POR CLIENTE =====
            st.markdown('<div class="section-header">👥 RENTABILIDAD POR CLIENTE</div>', unsafe_allow_html=True)

            # Tabla resumen de clientes
            tabla_clientes = []
            for row in datos_procesados:
                tabla_clientes.append({
                    'Cliente': row['cliente'],
                    'Órdenes': row['total_ordenes'],
                    'Entregas': f"{row['entregados']:,}",
                    'Ingresos': f"${row['ingresos']:,.0f}",
                    'Costos': f"${row['costos_totales']:,.0f}",
                    'Utilidad': f"${row['utilidad']:,.0f}",
                    'Margen': f"{row['margen_porcentaje']:.1f}%",
                    'Estado': '🟢' if row['margen_porcentaje'] >= 30 else '🟡' if row['margen_porcentaje'] >= 15 else '🔴'
                })

            df_clientes = pd.DataFrame(tabla_clientes)
            st.dataframe(df_clientes, use_container_width=True, hide_index=True)

            # Detalle expandible por cliente
            st.markdown("#### 🔍 Detalle por Cliente")

            for row in datos_procesados:
                color = "🟢" if row['margen_porcentaje'] >= 30 else "🟡" if row['margen_porcentaje'] >= 15 else "🔴"
                tasa_exito_cliente = (row['entregados'] / row['total_items'] * 100) if row['total_items'] > 0 else 0

                with st.expander(f"{color} **{row['cliente']}** | Utilidad: ${row['utilidad']:,.0f} | Margen: {row['margen_porcentaje']:.1f}%"):

                    # Fila 1: Métricas principales
                    col1, col2, col3, col4, col5 = st.columns(5)

                    with col1:
                        st.markdown("**📋 Operación**")
                        st.write(f"Órdenes: **{row['total_ordenes']}**")
                        st.write(f"Items: **{row['total_items']:,}**")

                    with col2:
                        st.markdown("**📦 Gestión**")
                        st.write(f"Entregas: **{row['entregados']:,}**")
                        st.write(f"Devoluciones: **{row['devoluciones']:,}**")
                        st.write(f"Éxito: **{tasa_exito_cliente:.1f}%**")

                    with col3:
                        st.markdown("**💵 Ingresos**")
                        st.write(f"Total: **${row['ingresos']:,.0f}**")

                    with col4:
                        st.markdown("**💸 Costos**")
                        st.write(f"Mensajeros: ${row['costo_mensajeros']:,.0f}")
                        st.write(f"Transporte: ${row['costo_transporte']:,.0f}")
                        st.write(f"**Total: ${row['costos_totales']:,.0f}**")

                    with col5:
                        st.markdown("**💰 Resultado**")
                        utilidad_color = "green" if row['utilidad'] >= 0 else "red"
                        st.markdown(f"<span style='color:{utilidad_color}; font-size:20px; font-weight:bold'>${row['utilidad']:,.0f}</span>", unsafe_allow_html=True)
                        st.write(f"Margen: **{row['margen_porcentaje']:.1f}%**")

                    # Barra de progreso visual del margen
                    st.progress(max(0, min(row['margen_porcentaje'] / 100, 1.0)))

                    # Tabla de órdenes del cliente
                    cliente_key = row['cliente'].strip().upper()
                    ordenes_cliente = ordenes_por_cliente.get(cliente_key, [])

                    if ordenes_cliente:
                        st.markdown("---")
                        st.markdown("**📋 Detalle de Órdenes**")

                        tabla_ordenes = []
                        for orden in ordenes_cliente:
                            items = orden['items_totales'] or 0
                            entregas = orden['entregas'] or 0
                            devs = orden['devoluciones'] or 0
                            progreso = ((entregas + devs) / items * 100) if items > 0 else 0

                            tabla_ordenes.append({
                                'N° Orden': orden['numero_orden'],
                                'Items': items,
                                'Entregas': entregas,
                                'Devoluciones': devs,
                                'Progreso': f"{progreso:.0f}%",
                                'Estado': orden['estado'].capitalize() if orden['estado'] else '-',
                                'Fecha': orden['fecha_recepcion'].strftime('%d/%m/%Y') if orden['fecha_recepcion'] else '-'
                            })

                        df_ordenes = pd.DataFrame(tabla_ordenes)
                        st.dataframe(df_ordenes, use_container_width=True, hide_index=True)

        else:
            st.info("📭 No hay datos para el periodo seleccionado")

    except Exception as e:
        st.error(f"Error: {e}")
        import traceback
        st.code(traceback.format_exc())

with tab2:
    st.markdown('<div class="section-header">📦 ESTADO DE ÓRDENES</div>', unsafe_allow_html=True)

    try:
        cursor = conn.cursor(dictionary=True)

        def normalizar_orden(val):
            s = str(val).strip()
            if s.endswith('.0'):
                s = s[:-2]
            return s

        # ── Filtros ──
        col1, col2, col3, col4 = st.columns([1, 1, 1.5, 1])

        with col1:
            fecha_desde_ord = st.date_input(
                "📅 Desde",
                value=date.today().replace(month=1, day=1),
                key="fecha_desde_ordenes"
            )
        with col2:
            fecha_hasta_ord = st.date_input(
                "📅 Hasta",
                value=date.today(),
                key="fecha_hasta_ordenes"
            )
        with col3:
            cursor.execute("""
                SELECT DISTINCT c.id, c.nombre_empresa
                FROM clientes c
                JOIN ordenes o ON c.id = o.cliente_id
                WHERE o.estado = 'activa'
                ORDER BY c.nombre_empresa
            """)
            clientes_ord = cursor.fetchall()
            opciones_clientes_ord = {"Todos": None}
            for c in clientes_ord:
                opciones_clientes_ord[c['nombre_empresa']] = c['id']
            cliente_sel_ord = st.selectbox("👥 Cliente", list(opciones_clientes_ord.keys()), key="cliente_ordenes")
            cliente_id_ord = opciones_clientes_ord[cliente_sel_ord]
        with col4:
            solo_pendientes = st.checkbox("⏳ Solo con pendientes", value=False, key="solo_pendientes_ord")

        st.markdown("---")

        # 1. Consultar órdenes activas con filtros
        query_ord = """
            SELECT o.numero_orden, c.nombre_empresa as cliente, cd.nombre as ciudad,
                   o.cantidad_total, o.estado, o.fecha_recepcion,
                   COALESCE(o.cantidad_entregados_local, 0) + COALESCE(o.cantidad_entregados_nacional, 0) as entregas_bd,
                   COALESCE(o.cantidad_devolucion_local, 0) + COALESCE(o.cantidad_devolucion_nacional, 0) as devoluciones_bd,
                   COALESCE(o.cantidad_en_lleva, 0) as en_lleva_bd
            FROM ordenes o
            JOIN clientes c ON o.cliente_id = c.id
            LEFT JOIN ciudades cd ON o.ciudad_destino_id = cd.id
            WHERE o.estado = 'activa'
            AND o.fecha_recepcion BETWEEN %s AND %s
        """
        params_ord = [fecha_desde_ord, fecha_hasta_ord]

        if cliente_id_ord:
            query_ord += " AND o.cliente_id = %s"
            params_ord.append(cliente_id_ord)

        query_ord += " ORDER BY o.fecha_recepcion DESC"
        cursor.execute(query_ord, tuple(params_ord))
        ordenes_activas = cursor.fetchall()

        # 2. Consultar entregas de Imile SAS desde gestiones_mensajero (todo = entrega)
        cursor.execute("""
            SELECT orden, SUM(total_seriales) as entregados
            FROM gestiones_mensajero
            WHERE UPPER(TRIM(cliente)) = 'IMILE SAS'
            GROUP BY orden
        """)
        imile_entregas = {normalizar_orden(r['orden']): int(r['entregados'] or 0) for r in cursor.fetchall()}

        # 3. Calcular pendiente por orden y aplicar filtro "solo pendientes"
        ordenes_procesadas = []
        for orden in ordenes_activas:
            num = normalizar_orden(orden['numero_orden'])
            cliente_upper = str(orden['cliente']).strip().upper()
            total = int(orden['cantidad_total'] or 0)

            if cliente_upper == 'IMILE SAS':
                entregas = imile_entregas.get(num, 0)
                devoluciones = 0
                en_lleva = 0
            else:
                entregas = int(orden['entregas_bd'] or 0)
                devoluciones = int(orden['devoluciones_bd'] or 0)
                en_lleva = int(orden['en_lleva_bd'] or 0)

            pendiente = max(total - entregas - devoluciones - en_lleva, 0)

            if solo_pendientes and pendiente == 0:
                continue

            ordenes_procesadas.append({
                'orden': orden,
                'num': num,
                'cliente_upper': cliente_upper,
                'total': total,
                'entregas': entregas,
                'devoluciones': devoluciones,
                'en_lleva': en_lleva,
                'pendiente': pendiente
            })

        # 4. Mostrar órdenes
        if ordenes_procesadas:
            tot_total = sum(o['total'] for o in ordenes_procesadas)
            tot_pendiente = sum(o['pendiente'] for o in ordenes_procesadas)
            tot_lleva = sum(o['en_lleva'] for o in ordenes_procesadas)
            tot_entregados = sum(o['entregas'] for o in ordenes_procesadas)
            tot_devoluciones = sum(o['devoluciones'] for o in ordenes_procesadas)

            # Métricas generales
            col1, col2, col3, col4, col5, col6 = st.columns(6)
            with col1:
                st.metric("📋 Órdenes", len(ordenes_procesadas))
            with col2:
                st.metric("📦 Recibido", f"{tot_total:,}")
            with col3:
                st.metric("⏳ Pendiente", f"{tot_pendiente:,}")
            with col4:
                st.metric("🚚 En Lleva", f"{tot_lleva:,}")
            with col5:
                st.metric("✅ Entregado", f"{tot_entregados:,}")
            with col6:
                st.metric("↩️ Devolución", f"{tot_devoluciones:,}")

            st.markdown("---")

            for o in ordenes_procesadas:
                orden = o['orden']
                total = o['total']
                entregas = o['entregas']
                devoluciones = o['devoluciones']
                en_lleva = o['en_lleva']
                pendiente = o['pendiente']
                cliente_upper = o['cliente_upper']

                cantidad_ref = total if total > 0 else 1
                progreso = float((entregas + devoluciones) / cantidad_ref * 100) if cantidad_ref > 0 else 0.0
                progreso_color = "🟢" if progreso >= 80 else "🟡" if progreso >= 50 else "🔴"

                with st.expander(f"{progreso_color} **{orden['numero_orden']}** - {orden['cliente']} | {progreso:.0f}% completado | {total:,} items"):
                    col1, col2, col3, col4, col5 = st.columns(5)

                    with col1:
                        st.metric("📦 Recibido", f"{total:,}")
                    with col2:
                        st.metric("⏳ Pendiente", f"{pendiente:,}")
                    with col3:
                        st.metric("🚚 En Lleva", f"{en_lleva:,}")
                    with col4:
                        st.metric("✅ Entregado", f"{entregas:,}")
                    with col5:
                        st.metric("↩️ Devolución", f"{devoluciones:,}")

                    st.progress(min(progreso / 100, 1.0))
                    ciudad = orden['ciudad'] or 'Sin asignar'
                    fuente = " (Gestiones)" if cliente_upper == 'IMILE SAS' else ""
                    st.caption(f"📍 Ciudad: {ciudad} | 📅 Recepción: {orden['fecha_recepcion'].strftime('%d/%m/%Y')}{fuente}")
        else:
            if ordenes_activas:
                st.info("No hay órdenes con items pendientes en el periodo seleccionado")
            else:
                st.info("No hay órdenes activas en el periodo seleccionado")

        st.markdown("---")

        # Estadísticas del mes
        st.markdown('<div class="section-header">📊 ESTADÍSTICAS DEL MES ACTUAL</div>', unsafe_allow_html=True)

        cursor.execute("""
            SELECT
                COUNT(*) as total_ordenes,
                SUM(o.cantidad_total) as total_items,
                SUM(COALESCE(o.cantidad_entregados_local, 0) + COALESCE(o.cantidad_entregados_nacional, 0)) as entregados,
                SUM(COALESCE(o.cantidad_devolucion_local, 0) + COALESCE(o.cantidad_devolucion_nacional, 0)) as devoluciones,
                SUM(o.valor_total) as ingresos
            FROM ordenes o
            WHERE MONTH(o.fecha_recepcion) = MONTH(CURRENT_DATE)
            AND YEAR(o.fecha_recepcion) = YEAR(CURRENT_DATE)
        """)
        stats = cursor.fetchone()

        if stats and stats['total_ordenes'] and stats['total_ordenes'] > 0:
            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                st.metric("📋 Órdenes", stats['total_ordenes'])
            with col2:
                st.metric("📦 Items", f"{stats['total_items']:,}")
            with col3:
                entregados_mes = stats['entregados'] or 0
                tasa = (entregados_mes / stats['total_items'] * 100) if stats['total_items'] > 0 else 0
                st.metric("✅ Entregados", f"{entregados_mes:,}", f"{tasa:.1f}%")
            with col4:
                devoluciones_mes = stats['devoluciones'] or 0
                tasa_dev = (devoluciones_mes / stats['total_items'] * 100) if stats['total_items'] > 0 else 0
                st.metric("↩️ Devoluciones", f"{devoluciones_mes:,}", f"{tasa_dev:.1f}%")
            with col5:
                st.metric("💵 Ingresos", f"${stats['ingresos']:,.0f}")
        else:
            st.info("📭 No hay órdenes este mes")

    except Exception as e:
        st.error(f"Error: {e}")

with tab3:
    st.markdown('<div class="section-header">👥 DESEMPEÑO DE PERSONAL</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        anio_p = st.selectbox("📅 Año", options=list(range(2024, 2031)), index=list(range(2024, 2031)).index(date.today().year), key="anio_personal")
    with col2:
        mes_p = st.selectbox("📆 Mes", meses_lista if 'meses_lista' in dir() else ["Todos", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                          "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], key="mes_personal")

    try:
        cursor = conn.cursor(dictionary=True)

        meses_lista_local = ["Todos", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                              "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

        query = """
            SELECT
                p.codigo, p.nombre_completo, p.tipo_personal,
                COUNT(DISTINCT op.orden_id) as ordenes_trabajadas,
                SUM(op.cantidad_asignada) as items_asignados,
                SUM(op.cantidad_entregada) as items_entregados,
                SUM(op.cantidad_devolucion) as items_devueltos,
                SUM(op.total_pagar) as ingresos_generados,
                CASE
                    WHEN SUM(op.cantidad_asignada) > 0
                    THEN (SUM(op.cantidad_entregada) / SUM(op.cantidad_asignada) * 100)
                    ELSE 0
                END as tasa_exito
            FROM personal p
            LEFT JOIN orden_personal op ON p.id = op.personal_id
            WHERE YEAR(op.fecha_asignacion) = %s
        """

        params = [anio_p]

        if mes_p != "Todos":
            mes_num_p = meses_lista_local.index(mes_p)
            query += " AND MONTH(op.fecha_asignacion) = %s"
            params.append(mes_num_p)

        query += " GROUP BY p.id, p.codigo, p.nombre_completo, p.tipo_personal HAVING ordenes_trabajadas > 0 ORDER BY items_entregados DESC"

        cursor.execute(query, tuple(params))
        personal_stats = cursor.fetchall()

        if personal_stats:
            # Métricas generales
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("👥 Personal Activo", len(personal_stats))
            with col2:
                total_entregados_p = sum([p['items_entregados'] or 0 for p in personal_stats])
                st.metric("✅ Total Entregas", f"{total_entregados_p:,}")
            with col3:
                promedio_exito = sum([p['tasa_exito'] for p in personal_stats]) / len(personal_stats)
                st.metric("📈 Tasa Éxito Prom.", f"{promedio_exito:.1f}%")
            with col4:
                total_generado = sum([p['ingresos_generados'] or 0 for p in personal_stats])
                st.metric("💰 Total Generado", f"${total_generado:,.0f}")

            st.markdown("---")

            # Ranking
            st.markdown("### 🏆 Ranking de Desempeño")

            for i, persona in enumerate(personal_stats[:10], 1):
                if i == 1:
                    medalla = "🥇"
                elif i == 2:
                    medalla = "🥈"
                elif i == 3:
                    medalla = "🥉"
                else:
                    medalla = f"#{i}"

                with st.expander(f"{medalla} **{persona['nombre_completo']}** ({persona['codigo']}) | {persona['items_entregados'] or 0:,} entregas"):
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("📋 Órdenes", persona['ordenes_trabajadas'])
                    with col2:
                        st.metric("📦 Asignados", f"{persona['items_asignados']:,}")
                    with col3:
                        st.metric("✅ Entregados", f"{persona['items_entregados'] or 0:,}")
                    with col4:
                        st.metric("📈 Éxito", f"{persona['tasa_exito']:.1f}%")

                    st.progress(min(persona['tasa_exito'] / 100, 1.0))

        else:
            st.info("📭 No hay datos de desempeño para el periodo seleccionado")

    except Exception as e:
        st.error(f"Error: {e}")

with tab4:
    st.markdown('<div class="section-header">📋 DETALLE DE RENTABILIDAD POR ORDEN</div>', unsafe_allow_html=True)

    try:
        cursor = conn.cursor(dictionary=True)

        # Filtros
        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            fecha_desde_det = st.date_input(
                "📅 Desde",
                value=date.today().replace(day=1),
                key="fecha_desde_detalle"
            )
        with col2:
            fecha_hasta_det = st.date_input(
                "📅 Hasta",
                value=date.today(),
                key="fecha_hasta_detalle"
            )
        with col3:
            # Obtener clientes
            cursor.execute("""
                SELECT DISTINCT c.id, c.nombre_empresa
                FROM clientes c
                JOIN ordenes o ON c.id = o.cliente_id
                ORDER BY c.nombre_empresa
            """)
            clientes_list = cursor.fetchall()
            cliente_options = {"TODOS": None}
            for c in clientes_list:
                cliente_options[c['nombre_empresa']] = c['id']

            cliente_sel_det = st.selectbox(
                "👥 Cliente",
                list(cliente_options.keys()),
                key="cliente_detalle"
            )
            cliente_id_filtro = cliente_options[cliente_sel_det]

        st.markdown("---")

        # Query principal de órdenes
        query_ordenes = """
            SELECT
                o.numero_orden,
                c.nombre_empresa as cliente,
                o.fecha_recepcion,
                o.cantidad_total as items,
                o.valor_total as total_vendido,
                o.estado
            FROM ordenes o
            JOIN clientes c ON o.cliente_id = c.id
            WHERE o.fecha_recepcion BETWEEN %s AND %s
        """
        params = [fecha_desde_det, fecha_hasta_det]

        if cliente_id_filtro:
            query_ordenes += " AND o.cliente_id = %s"
            params.append(cliente_id_filtro)

        query_ordenes += " ORDER BY c.nombre_empresa, o.fecha_recepcion DESC"

        cursor.execute(query_ordenes, tuple(params))
        ordenes_result = cursor.fetchall()

        if ordenes_result:
            # Costos de mensajeros por orden — solo entregas/devoluciones, NO alistamiento
            # El alistamiento se toma de registro_horas + registro_labores (6_Registro_Labores)
            query_costos_msg = """
                SELECT
                    orden,
                    UPPER(TRIM(cliente)) as cliente,
                    SUM(valor_total) as costo_mensajeros
                FROM gestiones_mensajero
                WHERE fecha_registro BETWEEN %s AND %s
                GROUP BY orden, UPPER(TRIM(cliente))
            """
            cursor.execute(query_costos_msg, (fecha_desde_det, fecha_hasta_det))
            costos_msg_result = cursor.fetchall()

            # Crear diccionario de costos por orden
            costos_por_orden = {}
            for r in costos_msg_result:
                orden_key = str(r['orden']).strip()
                if orden_key.endswith('.0'):
                    orden_key = orden_key[:-2]
                costos_por_orden[orden_key] = {
                    'costo_mensajeros': float(r['costo_mensajeros'] or 0),
                }

            # Procesar datos
            datos_tabla = []
            totales = {
                'items': 0,
                'vendido': 0,
                'costo_msg': 0,
                'utilidad': 0
            }

            for orden in ordenes_result:
                num_orden = str(orden['numero_orden']).strip()
                if num_orden.endswith('.0'):
                    num_orden = num_orden[:-2]

                costos = costos_por_orden.get(num_orden, {'costo_mensajeros': 0})

                items = int(orden['items'] or 0)
                vendido = float(orden['total_vendido'] or 0)
                costo_msg = costos['costo_mensajeros']
                utilidad = vendido - costo_msg
                margen = (utilidad / vendido * 100) if vendido > 0 else 0

                datos_tabla.append({
                    'Cliente': orden['cliente'],
                    'Orden': orden['numero_orden'],
                    'Fecha': orden['fecha_recepcion'].strftime('%d/%m/%Y') if orden['fecha_recepcion'] else '-',
                    'Items': items,
                    'Vendido': vendido,
                    'Costo Msg': costo_msg,
                    'Utilidad': utilidad,
                    'Margen %': margen,
                    'Estado': orden['estado'].capitalize() if orden['estado'] else '-'
                })

                totales['items'] += items
                totales['vendido'] += vendido
                totales['costo_msg'] += costo_msg
                totales['utilidad'] += utilidad

            # Métricas resumen
            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                st.metric("📋 Órdenes", len(datos_tabla))
            with col2:
                st.metric("💵 Total Vendido", f"${totales['vendido']:,.0f}")
            with col3:
                st.metric("🏍️ Costo Mensajeros", f"${totales['costo_msg']:,.0f}")
            with col4:
                margen_total = (totales['utilidad'] / totales['vendido'] * 100) if totales['vendido'] > 0 else 0
                st.metric("💰 Utilidad", f"${totales['utilidad']:,.0f}", f"{margen_total:.1f}%")

            st.markdown("---")

            # Tabla detallada
            df_detalle = pd.DataFrame(datos_tabla)

            # Formatear columnas numéricas para mostrar
            df_display = df_detalle.copy()
            df_display['Vendido'] = df_display['Vendido'].apply(lambda x: f"${x:,.0f}")
            df_display['Costo Msg'] = df_display['Costo Msg'].apply(lambda x: f"${x:,.0f}")
            df_display['Costo Alist'] = df_display['Costo Alist'].apply(lambda x: f"${x:,.0f}")
            df_display['Utilidad'] = df_display['Utilidad'].apply(lambda x: f"${x:,.0f}")
            df_display['Margen %'] = df_display['Margen %'].apply(lambda x: f"{x:.1f}%")

            st.dataframe(df_display, use_container_width=True, hide_index=True)

            # Botón para descargar
            csv = df_detalle.to_csv(index=False)
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"detalle_ordenes_{fecha_desde_det}_{fecha_hasta_det}.csv",
                mime="text/csv"
            )

            # Resumen por cliente
            st.markdown("---")
            st.markdown("### 📊 Resumen por Cliente")

            df_resumen = df_detalle.groupby('Cliente').agg({
                'Orden': 'count',
                'Items': 'sum',
                'Vendido': 'sum',
                'Costo Msg': 'sum',
                'Costo Alist': 'sum',
                'Utilidad': 'sum'
            }).reset_index()

            df_resumen.columns = ['Cliente', 'Órdenes', 'Items', 'Vendido', 'Costo Msg', 'Costo Alist', 'Utilidad']
            df_resumen['Margen %'] = df_resumen.apply(
                lambda r: (r['Utilidad'] / r['Vendido'] * 100) if r['Vendido'] > 0 else 0, axis=1
            )
            df_resumen = df_resumen.sort_values('Utilidad', ascending=False)

            # Formatear para mostrar
            df_resumen_display = df_resumen.copy()
            df_resumen_display['Vendido'] = df_resumen_display['Vendido'].apply(lambda x: f"${x:,.0f}")
            df_resumen_display['Costo Msg'] = df_resumen_display['Costo Msg'].apply(lambda x: f"${x:,.0f}")
            df_resumen_display['Costo Alist'] = df_resumen_display['Costo Alist'].apply(lambda x: f"${x:,.0f}")
            df_resumen_display['Utilidad'] = df_resumen_display['Utilidad'].apply(lambda x: f"${x:,.0f}")
            df_resumen_display['Margen %'] = df_resumen_display['Margen %'].apply(lambda x: f"{x:.1f}%")

            st.dataframe(df_resumen_display, use_container_width=True, hide_index=True)

        else:
            st.info("📭 No hay órdenes en el periodo seleccionado")

    except Exception as e:
        st.error(f"Error: {e}")
        import traceback
        st.code(traceback.format_exc())

with tab5:
    st.markdown('<div class="section-header">📈 COMPARATIVO MENSUAL</div>', unsafe_allow_html=True)

    MESES_NOMBRES = {
        1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"
    }

    anio_comp = st.selectbox(
        "📅 Año a comparar",
        options=list(range(2024, 2031)),
        index=list(range(2024, 2031)).index(date.today().year),
        key="anio_comparativo"
    )

    try:
        cursor = conn.cursor(dictionary=True)

        # ── 1. Ingresos por mes (sin costo_total de ordenes — duplica costos reales) ──
        cursor.execute("""
            SELECT
                MONTH(o.fecha_recepcion) as mes,
                SUM(o.valor_total) as ingresos,
                SUM(o.cantidad_total) as items_totales
            FROM ordenes o
            WHERE YEAR(o.fecha_recepcion) = %s
            GROUP BY MONTH(o.fecha_recepcion)
            ORDER BY mes
        """, (anio_comp,))
        datos_mensuales = cursor.fetchall()

        # ── 2. Costos de mensajeros por mes (por fecha de gestión) ──
        cursor.execute("""
            SELECT
                MONTH(gm.fecha_escaner) as mes,
                SUM(gm.valor_total) as costo_mensajeros
            FROM gestiones_mensajero gm
            JOIN ordenes o ON TRIM(REPLACE(gm.orden, '.0', '')) = TRIM(REPLACE(o.numero_orden, '.0', ''))
            WHERE YEAR(gm.fecha_escaner) = %s
            GROUP BY MONTH(gm.fecha_escaner)
            ORDER BY mes
        """, (anio_comp,))
        costos_msg_mes = {r['mes']: float(r['costo_mensajeros'] or 0) for r in cursor.fetchall()}

        # ── 2b. Alistamiento por mes (registro_horas + registro_labores + subsidio_transporte) ──
        cursor.execute("""
            SELECT mes, SUM(total) as total_alistamiento FROM (
                SELECT MONTH(fecha) as mes, total FROM registro_horas WHERE YEAR(fecha) = %s
                UNION ALL
                SELECT MONTH(fecha) as mes, total FROM registro_labores WHERE YEAR(fecha) = %s
                UNION ALL
                SELECT MONTH(fecha) as mes, total FROM subsidio_transporte WHERE YEAR(fecha) = %s
            ) t GROUP BY mes ORDER BY mes
        """, (anio_comp, anio_comp, anio_comp))
        alistamiento_mes = {r['mes']: float(r['total_alistamiento'] or 0) for r in cursor.fetchall()}

        # ── 3. Costos de transporte por mes ──
        cursor.execute("""
            SELECT
                MONTH(ft.fecha_factura) as mes,
                SUM(dft.costo_asignado) as costo_transporte
            FROM detalle_facturas_transporte dft
            JOIN facturas_transporte ft ON dft.factura_id = ft.id
            WHERE YEAR(ft.fecha_factura) = %s AND ft.estado != 'anulada'
            GROUP BY MONTH(ft.fecha_factura)
            ORDER BY mes
        """, (anio_comp,))
        costos_transp_mes = {r['mes']: float(r['costo_transporte'] or 0) for r in cursor.fetchall()}

        # ── 4. Gastos administrativos por mes ──
        cursor.execute("""
            SELECT MONTH(fecha) as mes, SUM(monto) as total_gastos
            FROM gastos_administrativos
            WHERE YEAR(fecha) = %s
            GROUP BY MONTH(fecha)
            ORDER BY mes
        """, (anio_comp,))
        gastos_admin_mes = {r['mes']: float(r['total_gastos'] or 0) for r in cursor.fetchall()}

        # ── 5. Nómina por mes ──
        cursor.execute("""
            SELECT periodo_mes as mes, SUM(costo_total_empleado) as total_nomina
            FROM nomina_provisiones
            WHERE periodo_anio = %s
            GROUP BY periodo_mes
            ORDER BY mes
        """, (anio_comp,))
        nomina_mes = {r['mes']: float(r['total_nomina'] or 0) for r in cursor.fetchall()}

        # ── 6. Entregas y devoluciones por mes ──
        cursor.execute("""
            SELECT
                MONTH(o.fecha_recepcion) as mes,
                SUM(CASE WHEN gm.tipo_gestion LIKE '%%Entrega%%' THEN gm.total_seriales ELSE 0 END) as entregados,
                SUM(CASE WHEN gm.tipo_gestion NOT LIKE '%%Entrega%%' THEN gm.total_seriales ELSE 0 END) as devoluciones
            FROM gestiones_mensajero gm
            JOIN ordenes o ON TRIM(REPLACE(gm.orden, '.0', '')) = TRIM(REPLACE(o.numero_orden, '.0', ''))
            WHERE YEAR(o.fecha_recepcion) = %s
            GROUP BY MONTH(o.fecha_recepcion)
            ORDER BY mes
        """, (anio_comp,))
        gestiones_mes = {r['mes']: {'entregados': int(r['entregados'] or 0), 'devoluciones': int(r['devoluciones'] or 0)} for r in cursor.fetchall()}

        # ── 7. Ingresos por cliente por mes ──
        cursor.execute("""
            SELECT
                MONTH(o.fecha_recepcion) as mes,
                UPPER(TRIM(c.nombre_empresa)) as cliente,
                SUM(o.valor_total) as ingresos
            FROM ordenes o
            JOIN clientes c ON o.cliente_id = c.id
            WHERE YEAR(o.fecha_recepcion) = %s
            GROUP BY MONTH(o.fecha_recepcion), UPPER(TRIM(c.nombre_empresa))
            ORDER BY mes
        """, (anio_comp,))
        ingresos_cliente_mes = cursor.fetchall()

        # ── 8. Gastos admin por categoría por mes ──
        cursor.execute("""
            SELECT MONTH(fecha) as mes, categoria, SUM(monto) as total
            FROM gastos_administrativos
            WHERE YEAR(fecha) = %s
            GROUP BY MONTH(fecha), categoria
            ORDER BY mes
        """, (anio_comp,))
        gastos_cat_mes = cursor.fetchall()

        if datos_mensuales:
            # Construir DataFrame principal
            filas = []
            for r in datos_mensuales:
                m = r['mes']
                ingresos = float(r['ingresos'] or 0)
                c_msg = costos_msg_mes.get(m, 0)
                c_alist = alistamiento_mes.get(m, 0)
                c_transp = costos_transp_mes.get(m, 0)
                g_admin = gastos_admin_mes.get(m, 0)
                g_nomina = nomina_mes.get(m, 0)
                costos_directos = c_msg + c_alist + c_transp
                gastos_fijos = g_admin + g_nomina
                utilidad_bruta = ingresos - costos_directos
                utilidad_neta = utilidad_bruta - gastos_fijos
                gest = gestiones_mes.get(m, {'entregados': 0, 'devoluciones': 0})

                filas.append({
                    'mes': m,
                    'mes_nombre': MESES_NOMBRES[m],
                    'ingresos': ingresos,
                    'costo_mensajeros': c_msg,
                    'costo_alistamiento': c_alist,
                    'costo_transporte': c_transp,
                    'gastos_admin': g_admin,
                    'nomina': g_nomina,
                    'utilidad_bruta': utilidad_bruta,
                    'utilidad_neta': utilidad_neta,
                    'entregados': gest['entregados'],
                    'devoluciones': gest['devoluciones'],
                    'items': int(r['items_totales'] or 0),
                    'margen_bruto': (utilidad_bruta / ingresos * 100) if ingresos > 0 else 0,
                    'margen_neto': (utilidad_neta / ingresos * 100) if ingresos > 0 else 0
                })

            df_comp = pd.DataFrame(filas)
            orden_meses = [MESES_NOMBRES[m] for m in sorted(df_comp['mes'].unique())]

            # ════════════════════════════════════════════
            # GRÁFICA 1: Ingresos vs Utilidad Bruta vs Utilidad Neta
            # ════════════════════════════════════════════
            st.markdown("### 💵 Ingresos y Utilidad por Mes")

            df_ing = df_comp[['mes_nombre', 'ingresos', 'utilidad_bruta', 'utilidad_neta']].melt(
                id_vars='mes_nombre', var_name='Concepto', value_name='Monto'
            )
            nombres_conceptos = {
                'ingresos': 'Ingresos',
                'utilidad_bruta': 'Utilidad Bruta',
                'utilidad_neta': 'Utilidad Neta'
            }
            df_ing['Concepto'] = df_ing['Concepto'].map(nombres_conceptos)

            chart_ingresos = alt.Chart(df_ing).mark_bar().encode(
                x=alt.X('mes_nombre:N', title='Mes', sort=orden_meses),
                y=alt.Y('Monto:Q', title='Monto ($)', axis=alt.Axis(format=',.0f')),
                color=alt.Color('Concepto:N', scale=alt.Scale(
                    domain=['Ingresos', 'Utilidad Bruta', 'Utilidad Neta'],
                    range=['#4facfe', '#38ef7d', '#667eea']
                )),
                xOffset='Concepto:N',
                tooltip=[
                    alt.Tooltip('mes_nombre:N', title='Mes'),
                    alt.Tooltip('Concepto:N'),
                    alt.Tooltip('Monto:Q', title='Monto', format='$,.0f')
                ]
            ).properties(height=400)

            st.altair_chart(chart_ingresos, use_container_width=True)

            # Tabla resumen debajo
            with st.expander("Ver tabla de datos"):
                df_tabla_ing = df_comp[['mes_nombre', 'ingresos', 'utilidad_bruta', 'utilidad_neta', 'margen_bruto', 'margen_neto']].copy()
                df_tabla_ing.columns = ['Mes', 'Ingresos', 'Utilidad Bruta', 'Utilidad Neta', 'Margen Bruto %', 'Margen Neto %']
                df_show = df_tabla_ing.copy()
                df_show['Ingresos'] = df_show['Ingresos'].apply(lambda x: f"${x:,.0f}")
                df_show['Utilidad Bruta'] = df_show['Utilidad Bruta'].apply(lambda x: f"${x:,.0f}")
                df_show['Utilidad Neta'] = df_show['Utilidad Neta'].apply(lambda x: f"${x:,.0f}")
                df_show['Margen Bruto %'] = df_show['Margen Bruto %'].apply(lambda x: f"{x:.1f}%")
                df_show['Margen Neto %'] = df_show['Margen Neto %'].apply(lambda x: f"{x:.1f}%")
                st.dataframe(df_show, use_container_width=True, hide_index=True)

            st.markdown("---")

            # ════════════════════════════════════════════
            # GRÁFICA 2: Desglose de Costos por Mes
            # ════════════════════════════════════════════
            st.markdown("### 💸 Desglose de Costos por Mes")

            df_costos_m = df_comp[['mes_nombre', 'costo_mensajeros', 'costo_alistamiento', 'costo_transporte', 'gastos_admin', 'nomina']].melt(
                id_vars='mes_nombre', var_name='Tipo Costo', value_name='Monto'
            )
            nombres_costos = {
                'costo_mensajeros': 'Mensajeros',
                'costo_alistamiento': 'Alistamiento',
                'costo_transporte': 'Transporte',
                'gastos_admin': 'Gastos Admin',
                'nomina': 'Nómina'
            }
            df_costos_m['Tipo Costo'] = df_costos_m['Tipo Costo'].map(nombres_costos)

            chart_costos = alt.Chart(df_costos_m).mark_bar().encode(
                x=alt.X('mes_nombre:N', title='Mes', sort=orden_meses),
                y=alt.Y('Monto:Q', title='Monto ($)', axis=alt.Axis(format=',.0f'), stack='zero'),
                color=alt.Color('Tipo Costo:N', scale=alt.Scale(
                    domain=['Mensajeros', 'Alistamiento', 'Transporte', 'Gastos Admin', 'Nómina'],
                    range=['#ff6b6b', '#ffa726', '#42a5f5', '#ab47bc', '#78909c']
                )),
                tooltip=[
                    alt.Tooltip('mes_nombre:N', title='Mes'),
                    alt.Tooltip('Tipo Costo:N'),
                    alt.Tooltip('Monto:Q', title='Monto', format='$,.0f')
                ]
            ).properties(height=400)

            st.altair_chart(chart_costos, use_container_width=True)

            st.markdown("---")

            # ════════════════════════════════════════════
            # GRÁFICA 3: Entregas vs Devoluciones por Mes
            # ════════════════════════════════════════════
            st.markdown("### 📦 Entregas vs Devoluciones por Mes")

            df_gest = df_comp[['mes_nombre', 'entregados', 'devoluciones']].melt(
                id_vars='mes_nombre', var_name='Tipo', value_name='Cantidad'
            )
            df_gest['Tipo'] = df_gest['Tipo'].map({'entregados': 'Entregas', 'devoluciones': 'Devoluciones'})

            chart_gestiones = alt.Chart(df_gest).mark_bar().encode(
                x=alt.X('mes_nombre:N', title='Mes', sort=orden_meses),
                y=alt.Y('Cantidad:Q', title='Unidades', axis=alt.Axis(format=',.0f')),
                color=alt.Color('Tipo:N', scale=alt.Scale(
                    domain=['Entregas', 'Devoluciones'],
                    range=['#38ef7d', '#ff416c']
                )),
                xOffset='Tipo:N',
                tooltip=[
                    alt.Tooltip('mes_nombre:N', title='Mes'),
                    alt.Tooltip('Tipo:N'),
                    alt.Tooltip('Cantidad:Q', format=',')
                ]
            ).properties(height=400)

            # Línea de tasa de éxito
            df_tasa = df_comp[['mes_nombre', 'entregados', 'devoluciones']].copy()
            df_tasa['tasa_exito'] = df_tasa.apply(
                lambda r: (r['entregados'] / (r['entregados'] + r['devoluciones']) * 100)
                if (r['entregados'] + r['devoluciones']) > 0 else 0, axis=1
            )

            st.altair_chart(chart_gestiones, use_container_width=True)

            # Tasa de éxito como línea separada
            chart_tasa = alt.Chart(df_tasa).mark_line(
                point=True, color='#667eea', strokeWidth=3
            ).encode(
                x=alt.X('mes_nombre:N', title='Mes', sort=orden_meses),
                y=alt.Y('tasa_exito:Q', title='Tasa de Éxito (%)', scale=alt.Scale(domain=[0, 100])),
                tooltip=[
                    alt.Tooltip('mes_nombre:N', title='Mes'),
                    alt.Tooltip('tasa_exito:Q', title='Tasa Éxito', format='.1f')
                ]
            ).properties(height=250)

            st.markdown("**Tasa de Éxito Mensual (%)**")
            st.altair_chart(chart_tasa, use_container_width=True)

            st.markdown("---")

            # ════════════════════════════════════════════
            # GRÁFICA 4: Margen de Utilidad por Mes
            # ════════════════════════════════════════════
            st.markdown("### 📊 Márgenes de Utilidad por Mes")

            df_margen = df_comp[['mes_nombre', 'margen_bruto', 'margen_neto']].melt(
                id_vars='mes_nombre', var_name='Tipo', value_name='Porcentaje'
            )
            df_margen['Tipo'] = df_margen['Tipo'].map({'margen_bruto': 'Margen Bruto', 'margen_neto': 'Margen Neto'})

            chart_margen = alt.Chart(df_margen).mark_bar().encode(
                x=alt.X('mes_nombre:N', title='Mes', sort=orden_meses),
                y=alt.Y('Porcentaje:Q', title='Margen (%)'),
                color=alt.Color('Tipo:N', scale=alt.Scale(
                    domain=['Margen Bruto', 'Margen Neto'],
                    range=['#4facfe', '#667eea']
                )),
                xOffset='Tipo:N',
                tooltip=[
                    alt.Tooltip('mes_nombre:N', title='Mes'),
                    alt.Tooltip('Tipo:N'),
                    alt.Tooltip('Porcentaje:Q', title='Margen', format='.1f')
                ]
            ).properties(height=350)

            # Línea de referencia en 0%
            linea_cero = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(
                color='red', strokeDash=[4, 4]
            ).encode(y='y:Q')

            st.altair_chart(chart_margen + linea_cero, use_container_width=True)

            st.markdown("---")

            # ════════════════════════════════════════════
            # GRÁFICA 5: Ingresos por Cliente por Mes
            # ════════════════════════════════════════════
            st.markdown("### 👥 Ingresos por Cliente por Mes")

            if ingresos_cliente_mes:
                df_cli_mes = pd.DataFrame(ingresos_cliente_mes)
                df_cli_mes['mes_nombre'] = df_cli_mes['mes'].map(MESES_NOMBRES)
                df_cli_mes['ingresos'] = df_cli_mes['ingresos'].apply(lambda x: float(x or 0))

                chart_clientes = alt.Chart(df_cli_mes).mark_bar().encode(
                    x=alt.X('mes_nombre:N', title='Mes', sort=orden_meses),
                    y=alt.Y('ingresos:Q', title='Ingresos ($)', axis=alt.Axis(format=',.0f'), stack='zero'),
                    color=alt.Color('cliente:N', title='Cliente'),
                    tooltip=[
                        alt.Tooltip('mes_nombre:N', title='Mes'),
                        alt.Tooltip('cliente:N', title='Cliente'),
                        alt.Tooltip('ingresos:Q', title='Ingresos', format='$,.0f')
                    ]
                ).properties(height=400)

                st.altair_chart(chart_clientes, use_container_width=True)

            st.markdown("---")

            # ════════════════════════════════════════════
            # GRÁFICA 6: Gastos Administrativos por Categoría por Mes
            # ════════════════════════════════════════════
            st.markdown("### 🏢 Gastos Administrativos por Categoría por Mes")

            if gastos_cat_mes:
                CATEGORIAS_NOMBRES = {
                    'mantenimiento': 'Mantenimiento', 'polizas': 'Pólizas',
                    'servicios_publicos': 'Serv. Públicos', 'caja_menor': 'Caja Menor',
                    'papeleria': 'Papelería', 'aseo': 'Aseo', 'internet': 'Internet',
                    'software': 'Software', 'alquiler_equipos': 'Alq. Equipos',
                    'arriendo': 'Arriendo', 'honorarios': 'Honorarios',
                    'impuestos': 'Impuestos', 'otros': 'Otros'
                }

                df_gcat = pd.DataFrame(gastos_cat_mes)
                df_gcat['mes_nombre'] = df_gcat['mes'].map(MESES_NOMBRES)
                df_gcat['total'] = df_gcat['total'].apply(lambda x: float(x or 0))
                df_gcat['categoria_nombre'] = df_gcat['categoria'].map(lambda x: CATEGORIAS_NOMBRES.get(x, x))

                chart_gastos_cat = alt.Chart(df_gcat).mark_bar().encode(
                    x=alt.X('mes_nombre:N', title='Mes', sort=orden_meses),
                    y=alt.Y('total:Q', title='Monto ($)', axis=alt.Axis(format=',.0f'), stack='zero'),
                    color=alt.Color('categoria_nombre:N', title='Categoría'),
                    tooltip=[
                        alt.Tooltip('mes_nombre:N', title='Mes'),
                        alt.Tooltip('categoria_nombre:N', title='Categoría'),
                        alt.Tooltip('total:Q', title='Monto', format='$,.0f')
                    ]
                ).properties(height=400)

                st.altair_chart(chart_gastos_cat, use_container_width=True)

            st.markdown("---")

            # ════════════════════════════════════════════
            # GRÁFICA 7: Volumen Operativo (Items procesados por mes)
            # ════════════════════════════════════════════
            st.markdown("### 📦 Volumen Operativo Mensual")

            col1, col2 = st.columns(2)

            with col1:
                chart_items = alt.Chart(df_comp).mark_bar(
                    color='#4facfe', cornerRadiusTopLeft=5, cornerRadiusTopRight=5
                ).encode(
                    x=alt.X('mes_nombre:N', title='Mes', sort=orden_meses),
                    y=alt.Y('items:Q', title='Items Totales', axis=alt.Axis(format=',')),
                    tooltip=[
                        alt.Tooltip('mes_nombre:N', title='Mes'),
                        alt.Tooltip('items:Q', title='Items', format=',')
                    ]
                ).properties(height=350, title='Items Recibidos por Mes')

                st.altair_chart(chart_items, use_container_width=True)

            with col2:
                # Ingreso promedio por item
                df_comp['ingreso_por_item'] = df_comp.apply(
                    lambda r: r['ingresos'] / r['items'] if r['items'] > 0 else 0, axis=1
                )

                chart_prom = alt.Chart(df_comp).mark_bar(
                    color='#38ef7d', cornerRadiusTopLeft=5, cornerRadiusTopRight=5
                ).encode(
                    x=alt.X('mes_nombre:N', title='Mes', sort=orden_meses),
                    y=alt.Y('ingreso_por_item:Q', title='$/Item', axis=alt.Axis(format=',.0f')),
                    tooltip=[
                        alt.Tooltip('mes_nombre:N', title='Mes'),
                        alt.Tooltip('ingreso_por_item:Q', title='$/Item', format='$,.0f')
                    ]
                ).properties(height=350, title='Ingreso Promedio por Item')

                st.altair_chart(chart_prom, use_container_width=True)

        else:
            st.info(f"No hay datos para el año {anio_comp}")

    except Exception as e:
        st.error(f"Error: {e}")
        import traceback
        st.code(traceback.format_exc())

with tab6:
    st.markdown('<div class="section-header">💳 CARTERA Y RENTABILIDAD REAL</div>', unsafe_allow_html=True)

    col1_r, col2_r = st.columns([1, 1])
    with col1_r:
        anio_r = st.selectbox(
            "📅 Año", options=list(range(2024, 2031)),
            index=list(range(2024, 2031)).index(date.today().year),
            key="anio_real"
        )
    with col2_r:
        meses_lista_r = ["Todos", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_r = st.selectbox("📆 Mes", meses_lista_r, key="mes_real")

    mes_num_r = meses_lista_r.index(mes_r) if mes_r != "Todos" else None

    try:
        cursor = conn.cursor(dictionary=True)

        st.markdown('<div class="section-header">👥 COBROS POR CLIENTE</div>', unsafe_allow_html=True)

        # Valor de órdenes (estimado base)
        if mes_num_r:
            cursor.execute("""
                SELECT UPPER(TRIM(c.nombre_empresa)) as cliente, SUM(o.valor_total) as valor_ordenes
                FROM ordenes o JOIN clientes c ON o.cliente_id = c.id
                WHERE YEAR(o.fecha_recepcion) = %s AND MONTH(o.fecha_recepcion) = %s
                GROUP BY UPPER(TRIM(c.nombre_empresa))
            """, (anio_r, mes_num_r))
        else:
            cursor.execute("""
                SELECT UPPER(TRIM(c.nombre_empresa)) as cliente, SUM(o.valor_total) as valor_ordenes
                FROM ordenes o JOIN clientes c ON o.cliente_id = c.id
                WHERE YEAR(o.fecha_recepcion) = %s
                GROUP BY UPPER(TRIM(c.nombre_empresa))
            """, (anio_r,))
        valor_ordenes_cli = {r['cliente']: float(r['valor_ordenes'] or 0) for r in cursor.fetchall()}

        # Facturado y saldo por cliente (por periodo de la factura)
        if mes_num_r:
            cursor.execute("""
                SELECT UPPER(TRIM(c.nombre_empresa)) as cliente,
                       SUM(fe.total) as facturado,
                       SUM(fe.saldo_pendiente) as saldo_pendiente
                FROM facturas_emitidas fe JOIN clientes c ON fe.cliente_id = c.id
                WHERE fe.periodo_anio = %s AND fe.periodo_mes = %s AND fe.estado != 'anulada'
                GROUP BY UPPER(TRIM(c.nombre_empresa))
            """, (anio_r, mes_num_r))
        else:
            cursor.execute("""
                SELECT UPPER(TRIM(c.nombre_empresa)) as cliente,
                       SUM(fe.total) as facturado,
                       SUM(fe.saldo_pendiente) as saldo_pendiente
                FROM facturas_emitidas fe JOIN clientes c ON fe.cliente_id = c.id
                WHERE fe.periodo_anio = %s AND fe.estado != 'anulada'
                GROUP BY UPPER(TRIM(c.nombre_empresa))
            """, (anio_r,))
        facturado_cli = {r['cliente']: {
            'facturado': float(r['facturado'] or 0),
            'saldo': float(r['saldo_pendiente'] or 0)
        } for r in cursor.fetchall()}

        # Cobrado: pagos recibidos sobre facturas del período
        if mes_num_r:
            cursor.execute("""
                SELECT UPPER(TRIM(c.nombre_empresa)) as cliente, SUM(pr.monto) as cobrado
                FROM pagos_recibidos pr
                JOIN facturas_emitidas fe ON pr.factura_id = fe.id
                JOIN clientes c ON fe.cliente_id = c.id
                WHERE fe.periodo_anio = %s AND fe.periodo_mes = %s AND fe.estado != 'anulada'
                GROUP BY UPPER(TRIM(c.nombre_empresa))
            """, (anio_r, mes_num_r))
        else:
            cursor.execute("""
                SELECT UPPER(TRIM(c.nombre_empresa)) as cliente, SUM(pr.monto) as cobrado
                FROM pagos_recibidos pr
                JOIN facturas_emitidas fe ON pr.factura_id = fe.id
                JOIN clientes c ON fe.cliente_id = c.id
                WHERE fe.periodo_anio = %s AND fe.estado != 'anulada'
                GROUP BY UPPER(TRIM(c.nombre_empresa))
            """, (anio_r,))
        cobrado_cli = {r['cliente']: float(r['cobrado'] or 0) for r in cursor.fetchall()}

        # Construir tabla clientes
        todos_clientes_r = set(valor_ordenes_cli.keys()) | set(facturado_cli.keys()) | set(cobrado_cli.keys())
        filas_cli = []
        for cli in sorted(todos_clientes_r):
            ordenes_val = valor_ordenes_cli.get(cli, 0)
            fac_data = facturado_cli.get(cli, {})
            facturado = fac_data.get('facturado', 0)
            saldo = fac_data.get('saldo', 0)
            cobrado = cobrado_cli.get(cli, 0)
            filas_cli.append({
                'Cliente': cli,
                'Valor Órdenes': ordenes_val,
                'Facturado': facturado,
                'Cobrado': cobrado,
                'Saldo Pendiente': saldo
            })

        if filas_cli:
            df_cli_r = pd.DataFrame(filas_cli)
            tot_ordenes_r = df_cli_r['Valor Órdenes'].sum()
            tot_facturado_r = df_cli_r['Facturado'].sum()
            tot_cobrado_r = df_cli_r['Cobrado'].sum()
            tot_saldo_r = df_cli_r['Saldo Pendiente'].sum()

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📋 Valor Órdenes", f"${tot_ordenes_r:,.0f}")
            with col2:
                st.metric("🧾 Total Facturado", f"${tot_facturado_r:,.0f}")
            with col3:
                st.metric("✅ Total Cobrado", f"${tot_cobrado_r:,.0f}")
            with col4:
                st.metric("⏳ Saldo por Cobrar", f"${tot_saldo_r:,.0f}", delta_color="inverse")

            df_cli_display = df_cli_r.copy()
            for col_n in ['Valor Órdenes', 'Facturado', 'Cobrado', 'Saldo Pendiente']:
                df_cli_display[col_n] = df_cli_display[col_n].apply(lambda x: f"${x:,.0f}")
            st.dataframe(df_cli_display, use_container_width=True, hide_index=True)
        else:
            tot_ordenes_r = tot_facturado_r = tot_cobrado_r = tot_saldo_r = 0
            st.info("No hay datos de clientes para el período seleccionado")

        st.markdown("---")

        st.markdown('<div class="section-header">🏍️ PAGOS A MENSAJEROS</div>', unsafe_allow_html=True)

        if mes_num_r:
            cursor.execute("""
                SELECT p.nombre_completo, p.codigo,
                       COUNT(DISTINCT gm.lot_esc) as planillas,
                       SUM(gm.total_seriales) as seriales,
                       SUM(gm.valor_total) as estimado,
                       SUM(CASE WHEN gm.facturado_liq IS NOT NULL THEN gm.valor_total ELSE 0 END) as en_liq,
                       SUM(CASE WHEN fr.estado = 'pagada' THEN gm.valor_total ELSE 0 END) as pagado
                FROM gestiones_mensajero gm
                JOIN personal p ON CAST(gm.cod_mensajero AS UNSIGNED) = CAST(p.codigo AS UNSIGNED)
                LEFT JOIN facturas_recibidas fr ON gm.facturado_liq = fr.id
                WHERE YEAR(gm.fecha_escaner) = %s AND MONTH(gm.fecha_escaner) = %s
                GROUP BY p.id, p.nombre_completo, p.codigo
                ORDER BY p.nombre_completo
            """, (anio_r, mes_num_r))
        else:
            cursor.execute("""
                SELECT p.nombre_completo, p.codigo,
                       COUNT(DISTINCT gm.lot_esc) as planillas,
                       SUM(gm.total_seriales) as seriales,
                       SUM(gm.valor_total) as estimado,
                       SUM(CASE WHEN gm.facturado_liq IS NOT NULL THEN gm.valor_total ELSE 0 END) as en_liq,
                       SUM(CASE WHEN fr.estado = 'pagada' THEN gm.valor_total ELSE 0 END) as pagado
                FROM gestiones_mensajero gm
                JOIN personal p ON CAST(gm.cod_mensajero AS UNSIGNED) = CAST(p.codigo AS UNSIGNED)
                LEFT JOIN facturas_recibidas fr ON gm.facturado_liq = fr.id
                WHERE YEAR(gm.fecha_escaner) = %s
                GROUP BY p.id, p.nombre_completo, p.codigo
                ORDER BY p.nombre_completo
            """, (anio_r,))
        estimado_msg = {r['codigo']: {
            'nombre': r['nombre_completo'],
            'planillas': int(r['planillas'] or 0),
            'seriales': int(r['seriales'] or 0),
            'estimado': float(r['estimado'] or 0),
            'en_liq': float(r['en_liq'] or 0),
            'pagado': float(r['pagado'] or 0),
        } for r in cursor.fetchall()}

        if estimado_msg:
            filas_msg = []
            for cod, data in estimado_msg.items():
                en_liq = data['en_liq']
                pagado = data['pagado']
                pendiente = data['estimado'] - pagado
                filas_msg.append({
                    'Mensajero': data['nombre'],
                    'Planillas': data['planillas'],
                    'Seriales': data['seriales'],
                    'Total Gestiones': data['estimado'],
                    'En Liquidación': en_liq,
                    'Pagado': pagado,
                    'Pendiente': pendiente
                })

            df_msg = pd.DataFrame(filas_msg)
            tot_msg_estimado = df_msg['Total Gestiones'].sum()
            tot_msg_en_liq = df_msg['En Liquidación'].sum()
            tot_msg_pagado = df_msg['Pagado'].sum()
            tot_msg_pendiente = df_msg['Pendiente'].sum()

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📋 Total Gestiones", f"${tot_msg_estimado:,.0f}")
            with col2:
                st.metric("📄 En Liquidación", f"${tot_msg_en_liq:,.0f}")
            with col3:
                st.metric("✅ Pagado", f"${tot_msg_pagado:,.0f}")
            with col4:
                st.metric("⏳ Pendiente", f"${tot_msg_pendiente:,.0f}", delta_color="inverse")

            df_msg_display = df_msg.copy()
            for col_n in ['Total Gestiones', 'En Liquidación', 'Pagado', 'Pendiente']:
                df_msg_display[col_n] = df_msg_display[col_n].apply(lambda x: f"${x:,.0f}")
            df_msg_display['Seriales'] = df_msg_display['Seriales'].apply(lambda x: f"{int(x):,}")
            st.dataframe(df_msg_display, use_container_width=True, hide_index=True)
        else:
            tot_msg_estimado = tot_msg_en_liq = tot_msg_pagado = tot_msg_pendiente = 0
            st.info("No hay gestiones de mensajeros en el período")

        st.markdown("---")

        st.markdown('<div class="section-header">🏭 PAGOS DE ALISTAMIENTO</div>', unsafe_allow_html=True)

        if mes_num_r:
            cursor.execute("""
                SELECT p.nombre_completo, p.codigo,
                       SUM(combined.total) as estimado,
                       SUM(CASE WHEN combined.liquidado = 1 THEN combined.total ELSE 0 END) as pagado
                FROM (
                    SELECT personal_id, total, liquidado FROM registro_horas
                    WHERE YEAR(fecha) = %s AND MONTH(fecha) = %s
                    UNION ALL
                    SELECT personal_id, total, liquidado FROM registro_labores
                    WHERE YEAR(fecha) = %s AND MONTH(fecha) = %s
                ) combined
                JOIN personal p ON combined.personal_id = p.id
                GROUP BY p.id, p.nombre_completo, p.codigo
                ORDER BY p.nombre_completo
            """, (anio_r, mes_num_r, anio_r, mes_num_r))
        else:
            cursor.execute("""
                SELECT p.nombre_completo, p.codigo,
                       SUM(combined.total) as estimado,
                       SUM(CASE WHEN combined.liquidado = 1 THEN combined.total ELSE 0 END) as pagado
                FROM (
                    SELECT personal_id, total, liquidado FROM registro_horas WHERE YEAR(fecha) = %s
                    UNION ALL
                    SELECT personal_id, total, liquidado FROM registro_labores WHERE YEAR(fecha) = %s
                ) combined
                JOIN personal p ON combined.personal_id = p.id
                GROUP BY p.id, p.nombre_completo, p.codigo
                ORDER BY p.nombre_completo
            """, (anio_r, anio_r))
        estimado_alist = {r['codigo']: {
            'nombre': r['nombre_completo'],
            'estimado': float(r['estimado'] or 0),
            'pagado': float(r['pagado'] or 0),
        } for r in cursor.fetchall()}

        if estimado_alist:
            filas_alist = []
            for cod, data in estimado_alist.items():
                pagado_a = data['pagado']
                pendiente_a = data['estimado'] - pagado_a
                filas_alist.append({
                    'Personal': data['nombre'],
                    'Total Registrado': data['estimado'],
                    'Pagado': pagado_a,
                    'Pendiente': pendiente_a
                })

            df_alist = pd.DataFrame(filas_alist)
            tot_alist_estimado = df_alist['Total Registrado'].sum()
            tot_alist_pagado = df_alist['Pagado'].sum()
            tot_alist_pendiente = df_alist['Pendiente'].sum()

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📋 Total Registrado", f"${tot_alist_estimado:,.0f}")
            with col2:
                st.metric("✅ Pagado", f"${tot_alist_pagado:,.0f}")
            with col3:
                st.metric("⏳ Pendiente", f"${tot_alist_pendiente:,.0f}", delta_color="inverse")

            df_alist_display = df_alist.copy()
            for col_n in ['Total Registrado', 'Pagado', 'Pendiente']:
                df_alist_display[col_n] = df_alist_display[col_n].apply(lambda x: f"${x:,.0f}")
            st.dataframe(df_alist_display, use_container_width=True, hide_index=True)
        else:
            tot_alist_estimado = tot_alist_pagado = tot_alist_pendiente = 0
            st.info("No hay registros de alistamiento en el período")

        st.markdown("---")

        st.markdown('<div class="section-header">💰 RENTABILIDAD REAL vs. ESTIMADA</div>', unsafe_allow_html=True)

        # Transporte (sin tracking de pagado/pendiente)
        if mes_num_r:
            cursor.execute("""
                SELECT SUM(dft.costo_asignado) as total
                FROM detalle_facturas_transporte dft
                JOIN facturas_transporte ft ON dft.factura_id = ft.id
                WHERE YEAR(ft.fecha_factura) = %s AND MONTH(ft.fecha_factura) = %s
                AND ft.estado != 'anulada'
            """, (anio_r, mes_num_r))
        else:
            cursor.execute("""
                SELECT SUM(dft.costo_asignado) as total
                FROM detalle_facturas_transporte dft
                JOIN facturas_transporte ft ON dft.factura_id = ft.id
                WHERE YEAR(ft.fecha_factura) = %s AND ft.estado != 'anulada'
            """, (anio_r,))
        r_transp_r = cursor.fetchone()
        costo_transp_r = float(r_transp_r['total'] or 0) if r_transp_r else 0

        # Gastos admin
        if mes_num_r:
            cursor.execute("""
                SELECT SUM(monto) as total FROM gastos_administrativos
                WHERE YEAR(fecha) = %s AND MONTH(fecha) = %s
            """, (anio_r, mes_num_r))
        else:
            cursor.execute("""
                SELECT SUM(monto) as total FROM gastos_administrativos WHERE YEAR(fecha) = %s
            """, (anio_r,))
        r_ga_r = cursor.fetchone()
        gastos_admin_r = float(r_ga_r['total'] or 0) if r_ga_r else 0

        # Nómina
        if mes_num_r:
            cursor.execute("""
                SELECT SUM(costo_total_empleado) as total FROM nomina_provisiones
                WHERE periodo_anio = %s AND periodo_mes = %s
            """, (anio_r, mes_num_r))
        else:
            cursor.execute("""
                SELECT SUM(costo_total_empleado) as total FROM nomina_provisiones WHERE periodo_anio = %s
            """, (anio_r,))
        r_nom_r = cursor.fetchone()
        nomina_r = float(r_nom_r['total'] or 0) if r_nom_r else 0

        gastos_fijos_r = gastos_admin_r + nomina_r

        # ── Calcular P&L ──
        # Estimado
        costos_directos_estimados = tot_msg_estimado + tot_alist_estimado + costo_transp_r
        utilidad_estimada = tot_ordenes_r - costos_directos_estimados - gastos_fijos_r

        # Real: facturado a clientes vs pagado a mensajeros/alistamiento
        costos_directos_reales = tot_msg_pagado + tot_alist_pagado + costo_transp_r
        utilidad_real_facturada = tot_facturado_r - costos_directos_reales - gastos_fijos_r
        utilidad_real_cobrada = tot_cobrado_r - costos_directos_reales - gastos_fijos_r

        # Métricas principales
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📋 Valor Órdenes", f"${tot_ordenes_r:,.0f}",
                      delta=f"Utilidad est. ${utilidad_estimada:,.0f}")
        with col2:
            st.metric("🧾 Total Facturado", f"${tot_facturado_r:,.0f}",
                      delta=f"Utilidad ${utilidad_real_facturada:,.0f}")
        with col3:
            st.metric("✅ Total Cobrado", f"${tot_cobrado_r:,.0f}",
                      delta=f"Utilidad cobrada ${utilidad_real_cobrada:,.0f}")
        with col4:
            diferencia = tot_facturado_r - tot_ordenes_r
            st.metric("📊 Facturado vs Órdenes", f"${diferencia:,.0f}",
                      delta=f"{'▲' if diferencia >= 0 else '▼'} vs valor órdenes",
                      delta_color="normal" if diferencia >= 0 else "inverse")

        st.markdown("---")

        # Tabla P&L comparativo
        pnl_data = [
            {
                'Concepto': '💵 Ingresos',
                'Estimado (Órdenes)': tot_ordenes_r,
                'Facturado': tot_facturado_r,
                'Cobrado Real': tot_cobrado_r
            },
            {
                'Concepto': '🏍️ (−) Mensajeros',
                'Estimado (Órdenes)': tot_msg_estimado,
                'Facturado': tot_msg_en_liq,
                'Cobrado Real': tot_msg_pagado
            },
            {
                'Concepto': '🏭 (−) Alistamiento',
                'Estimado (Órdenes)': tot_alist_estimado,
                'Facturado': tot_alist_estimado,
                'Cobrado Real': tot_alist_pagado
            },
            {
                'Concepto': '🚚 (−) Transporte',
                'Estimado (Órdenes)': costo_transp_r,
                'Facturado': costo_transp_r,
                'Cobrado Real': costo_transp_r
            },
            {
                'Concepto': '🏢 (−) Gastos Admin',
                'Estimado (Órdenes)': gastos_admin_r,
                'Facturado': gastos_admin_r,
                'Cobrado Real': gastos_admin_r
            },
            {
                'Concepto': '👥 (−) Nómina',
                'Estimado (Órdenes)': nomina_r,
                'Facturado': nomina_r,
                'Cobrado Real': nomina_r
            },
            {
                'Concepto': '── Total Costos',
                'Estimado (Órdenes)': costos_directos_estimados + gastos_fijos_r,
                'Facturado': tot_msg_en_liq + tot_alist_estimado + costo_transp_r + gastos_fijos_r,
                'Cobrado Real': costos_directos_reales + gastos_fijos_r
            },
            {
                'Concepto': '💰 UTILIDAD',
                'Estimado (Órdenes)': utilidad_estimada,
                'Facturado': utilidad_real_facturada,
                'Cobrado Real': utilidad_real_cobrada
            },
        ]

        df_pnl = pd.DataFrame(pnl_data)
        df_pnl_display = df_pnl.copy()
        for col_n in ['Estimado (Órdenes)', 'Facturado', 'Cobrado Real']:
            df_pnl_display[col_n] = df_pnl_display[col_n].apply(lambda x: f"${x:,.0f}")
        st.dataframe(df_pnl_display, use_container_width=True, hide_index=True)

        st.caption(
            "**Estimado**: basado en valor de órdenes y total de gestiones/alistamiento del período. "
            "**Facturado**: lo facturado a clientes / gestiones en liquidación. "
            "**Cobrado Real**: pagos recibidos de clientes vs pagos realizados a mensajeros/alistamiento (liquidado=pagado)."
        )

    except Exception as e:
        st.error(f"Error: {e}")
        import traceback
        st.code(traceback.format_exc())

if 'cursor' in locals():
    cursor.close()
