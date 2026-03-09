import streamlit as st
import pandas as pd
from datetime import date
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_connection import conectar_logistica


# Mapeo de categorias para mostrar nombres amigables
CATEGORIAS = {
    'mantenimiento': 'Mantenimiento',
    'polizas': 'Pólizas',
    'servicios_publicos': 'Servicios Públicos',
    'caja_menor': 'Caja Menor',
    'papeleria': 'Papelería',
    'aseo': 'Implementos de Aseo',
    'internet': 'Internet',
    'software': 'Servicios de Software',
    'alquiler_equipos': 'Alquiler de Equipos',
    'arriendo': 'Arriendo',
    'honorarios': 'Honorarios',
    'impuestos': 'Impuestos',
    'otros': 'Otros'
}

st.title("💼 Gastos Administrativos")

conn = conectar_logistica()
if not conn:
    st.stop()

tab1, tab2, tab3 = st.tabs([
    "📥 Registrar Gasto",
    "📋 Gastos Registrados",
    "📊 Resumen por Categoría"
])

with tab1:
    st.subheader("Registrar Nuevo Gasto")

    col1, col2 = st.columns(2)

    with col1:
        fecha = st.date_input("Fecha del Gasto", value=date.today())
        categoria = st.selectbox(
            "Categoría",
            options=list(CATEGORIAS.keys()),
            format_func=lambda x: CATEGORIAS[x]
        )
        descripcion = st.text_input("Descripción", placeholder="Ej: Pago de luz mes de enero")
        monto = st.number_input("Monto", min_value=0.0, step=1000.0, format="%.2f")

    with col2:
        proveedor = st.text_input("Proveedor (opcional)", placeholder="Ej: Enel, Claro, etc.")
        numero_factura = st.text_input("Número de Factura (opcional)", placeholder="Ej: FAC-001")
        estado = st.selectbox("Estado", options=['pendiente', 'pagado'], format_func=lambda x: x.capitalize())
        if estado == 'pagado':
            fecha_pago = st.date_input("Fecha de Pago", value=date.today())
        else:
            fecha_pago = None

    observaciones = st.text_area("Observaciones (opcional)", height=80)

    if st.button("💾 Guardar Gasto", type="primary", use_container_width=True):
        if not descripcion:
            st.error("Ingresa una descripción del gasto")
        elif monto <= 0:
            st.error("El monto debe ser mayor a 0")
        else:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO gastos_administrativos
                    (fecha, categoria, descripcion, monto, proveedor, numero_factura, estado, fecha_pago, observaciones)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    fecha,
                    categoria,
                    descripcion,
                    monto,
                    proveedor or None,
                    numero_factura or None,
                    estado,
                    fecha_pago,
                    observaciones or None
                ))
                conn.commit()
                st.success("Gasto registrado exitosamente")
                st.rerun()
            except Exception as e:
                conn.rollback()
                st.error(f"Error al guardar: {e}")

with tab2:
    st.subheader("Gastos Registrados")

    try:
        cursor = conn.cursor(dictionary=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            fecha_desde = st.date_input("Desde", value=date.today().replace(day=1), key="fecha_desde_ga")
        with col2:
            fecha_hasta = st.date_input("Hasta", value=date.today(), key="fecha_hasta_ga")
        with col3:
            filtro_categoria = st.selectbox(
                "Categoría",
                options=['todas'] + list(CATEGORIAS.keys()),
                format_func=lambda x: 'Todas' if x == 'todas' else CATEGORIAS[x],
                key="filtro_cat"
            )

        if filtro_categoria == 'todas':
            cursor.execute("""
                SELECT * FROM gastos_administrativos
                WHERE fecha BETWEEN %s AND %s
                ORDER BY fecha DESC
            """, (fecha_desde, fecha_hasta))
        else:
            cursor.execute("""
                SELECT * FROM gastos_administrativos
                WHERE fecha BETWEEN %s AND %s AND categoria = %s
                ORDER BY fecha DESC
            """, (fecha_desde, fecha_hasta, filtro_categoria))

        gastos = cursor.fetchall()

        if gastos:
            # Totales
            total_gastos = sum([g['monto'] for g in gastos])
            total_pendiente = sum([g['monto'] for g in gastos if g['estado'] == 'pendiente'])
            total_pagado = sum([g['monto'] for g in gastos if g['estado'] == 'pagado'])

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Gastos", f"${total_gastos:,.0f}")
            with col2:
                st.metric("Registros", len(gastos))
            with col3:
                st.metric("Pagado", f"${total_pagado:,.0f}")
            with col4:
                st.metric("Pendiente", f"${total_pendiente:,.0f}")

            st.divider()

            for gasto in gastos:
                estado_icon = "✅" if gasto['estado'] == 'pagado' else "⏳"
                cat_nombre = CATEGORIAS.get(gasto['categoria'], gasto['categoria'])

                with st.expander(f"{estado_icon} {gasto['fecha'].strftime('%d/%m/%Y')} - {cat_nombre} - ${gasto['monto']:,.0f}"):
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.write(f"**Descripción:** {gasto['descripcion']}")
                        st.write(f"**Categoría:** {cat_nombre}")

                    with col2:
                        st.write(f"**Proveedor:** {gasto['proveedor'] or 'N/A'}")
                        st.write(f"**Factura:** {gasto['numero_factura'] or 'N/A'}")

                    with col3:
                        st.write(f"**Estado:** {gasto['estado'].capitalize()}")
                        if gasto['fecha_pago']:
                            st.write(f"**Fecha Pago:** {gasto['fecha_pago'].strftime('%d/%m/%Y')}")

                    if gasto['observaciones']:
                        st.write(f"**Observaciones:** {gasto['observaciones']}")

                    # Acciones
                    col1, col2, col3 = st.columns([1, 1, 2])

                    with col1:
                        if gasto['estado'] == 'pendiente':
                            if st.button("✅ Marcar Pagado", key=f"pagar_{gasto['id']}"):
                                cursor.execute("""
                                    UPDATE gastos_administrativos
                                    SET estado = 'pagado', fecha_pago = %s
                                    WHERE id = %s
                                """, (date.today(), gasto['id']))
                                conn.commit()
                                st.success("Marcado como pagado")
                                st.rerun()

                    with col2:
                        if st.button("🗑️ Eliminar", key=f"eliminar_{gasto['id']}"):
                            cursor.execute("DELETE FROM gastos_administrativos WHERE id = %s", (gasto['id'],))
                            conn.commit()
                            st.success("Gasto eliminado")
                            st.rerun()

        else:
            st.info("No hay gastos en el periodo seleccionado")

    except Exception as e:
        st.error(f"Error: {e}")

with tab3:
    st.subheader("Resumen por Categoría")

    try:
        cursor = conn.cursor(dictionary=True)

        col1, col2 = st.columns(2)
        with col1:
            anio = st.number_input("Año", min_value=2020, max_value=2030, value=date.today().year, key="anio_resumen_ga")
        with col2:
            mes = st.selectbox("Mes", [
                "Todos", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
            ], key="mes_resumen_ga")

        if mes != "Todos":
            mes_num = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                       "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes) + 1
            cursor.execute("""
                SELECT categoria, COUNT(*) as cantidad, SUM(monto) as total
                FROM gastos_administrativos
                WHERE YEAR(fecha) = %s AND MONTH(fecha) = %s
                GROUP BY categoria
                ORDER BY total DESC
            """, (anio, mes_num))
        else:
            cursor.execute("""
                SELECT categoria, COUNT(*) as cantidad, SUM(monto) as total
                FROM gastos_administrativos
                WHERE YEAR(fecha) = %s
                GROUP BY categoria
                ORDER BY total DESC
            """, (anio,))

        resumen = cursor.fetchall()

        if resumen:
            # Total general
            total_general = sum([r['total'] for r in resumen])

            st.metric("Total Gastos Administrativos", f"${total_general:,.0f}")

            st.divider()

            # Tabla de resumen
            datos_tabla = []
            for r in resumen:
                porcentaje = (r['total'] / total_general * 100) if total_general > 0 else 0
                datos_tabla.append({
                    'Categoría': CATEGORIAS.get(r['categoria'], r['categoria']),
                    'Cantidad': r['cantidad'],
                    'Total': f"${r['total']:,.0f}",
                    'Porcentaje': f"{porcentaje:.1f}%"
                })

            df_resumen = pd.DataFrame(datos_tabla)
            st.dataframe(df_resumen, use_container_width=True, hide_index=True)

            st.divider()

            # Detalle por categoria
            st.markdown("### Detalle por Categoría")

            for r in resumen:
                cat_nombre = CATEGORIAS.get(r['categoria'], r['categoria'])
                porcentaje = (r['total'] / total_general * 100) if total_general > 0 else 0

                with st.expander(f"📁 {cat_nombre} - ${r['total']:,.0f} ({porcentaje:.1f}%)"):
                    if mes != "Todos":
                        cursor.execute("""
                            SELECT fecha, descripcion, monto, proveedor, estado
                            FROM gastos_administrativos
                            WHERE YEAR(fecha) = %s AND MONTH(fecha) = %s AND categoria = %s
                            ORDER BY fecha DESC
                        """, (anio, mes_num, r['categoria']))
                    else:
                        cursor.execute("""
                            SELECT fecha, descripcion, monto, proveedor, estado
                            FROM gastos_administrativos
                            WHERE YEAR(fecha) = %s AND categoria = %s
                            ORDER BY fecha DESC
                        """, (anio, r['categoria']))

                    detalles = cursor.fetchall()

                    if detalles:
                        df_detalle = pd.DataFrame(detalles)
                        df_detalle['fecha'] = df_detalle['fecha'].apply(lambda x: x.strftime('%d/%m/%Y'))
                        df_detalle['monto'] = df_detalle['monto'].apply(lambda x: f"${x:,.0f}")
                        df_detalle['estado'] = df_detalle['estado'].apply(lambda x: '✅' if x == 'pagado' else '⏳')
                        df_detalle.columns = ['Fecha', 'Descripción', 'Monto', 'Proveedor', 'Estado']
                        st.dataframe(df_detalle, use_container_width=True, hide_index=True)

            # Comparativa mensual (si es año completo)
            if mes == "Todos":
                st.divider()
                st.markdown("### Evolución Mensual")

                cursor.execute("""
                    SELECT MONTH(fecha) as mes, SUM(monto) as total
                    FROM gastos_administrativos
                    WHERE YEAR(fecha) = %s
                    GROUP BY MONTH(fecha)
                    ORDER BY mes
                """, (anio,))

                mensual = cursor.fetchall()

                if mensual:
                    meses_nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                                     "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
                    datos_mensual = {meses_nombres[m['mes']-1]: float(m['total']) for m in mensual}

                    df_mensual = pd.DataFrame({
                        'Mes': list(datos_mensual.keys()),
                        'Total': list(datos_mensual.values())
                    })

                    st.bar_chart(df_mensual.set_index('Mes'))

        else:
            st.info("No hay gastos registrados para el periodo seleccionado")

    except Exception as e:
        st.error(f"Error: {e}")

if 'cursor' in locals():
    cursor.close()
