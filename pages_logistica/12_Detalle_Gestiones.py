import streamlit as st
import pandas as pd
from datetime import date, datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_connection import conectar_logistica


st.title("📋 Detalle de Gestiones por Mensajero")

conn = conectar_logistica()
if not conn:
    st.stop()

# Inicializar estado para edición
if 'editando_gestion' not in st.session_state:
    st.session_state.editando_gestion = None
if 'editando_grupo' not in st.session_state:
    st.session_state.editando_grupo = None

try:
    cursor = conn.cursor(dictionary=True)

    # =====================================================
    # FILTROS
    # =====================================================
    st.markdown("### 🔍 Filtros")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        fecha_desde = st.date_input("📅 Fecha Desde", value=date.today().replace(day=1))

    with col2:
        fecha_hasta = st.date_input("📅 Fecha Hasta", value=date.today())

    with col3:
        # Obtener mensajeros que tienen gestiones
        cursor.execute("""
            SELECT DISTINCT gm.cod_mensajero, COALESCE(p.nombre_completo, 'Sin asignar') as nombre
            FROM gestiones_mensajero gm
            LEFT JOIN personal p ON gm.mensajero_id = p.id
            ORDER BY gm.cod_mensajero
        """)
        mensajeros = cursor.fetchall()

        mensajero_options = {"TODOS": None}
        for m in mensajeros:
            mensajero_options[f"{m['cod_mensajero']} - {m['nombre']}"] = m['cod_mensajero']

        mensajero_sel = st.selectbox("👤 Mensajero", list(mensajero_options.keys()))
        cod_mensajero_filtro = mensajero_options[mensajero_sel]

    with col4:
        # Obtener clientes
        cursor.execute("SELECT DISTINCT cliente FROM gestiones_mensajero ORDER BY cliente")
        clientes = [r['cliente'] for r in cursor.fetchall()]

        cliente_options = ["TODOS"] + clientes
        cliente_filtro = st.selectbox("🏢 Cliente", cliente_options)

    st.divider()

    # =====================================================
    # CONSULTA DE GESTIONES
    # =====================================================
    query = """
        SELECT
            gm.id,
            gm.fecha_escaner,
            gm.cod_mensajero,
            COALESCE(p.nombre_completo, 'Sin asignar') as mensajero_nombre,
            gm.lot_esc,
            gm.orden,
            gm.tipo_gestion,
            gm.cliente,
            gm.total_seriales,
            gm.valor_unitario,
            gm.valor_total,
            gm.fecha_registro
        FROM gestiones_mensajero gm
        LEFT JOIN personal p ON gm.mensajero_id = p.id
        WHERE DATE(gm.fecha_registro) BETWEEN %s AND %s
    """
    params = [fecha_desde, fecha_hasta]

    if cod_mensajero_filtro:
        query += " AND gm.cod_mensajero = %s"
        params.append(cod_mensajero_filtro)

    if cliente_filtro != "TODOS":
        query += " AND gm.cliente = %s"
        params.append(cliente_filtro)

    query += " ORDER BY gm.fecha_registro DESC, gm.cod_mensajero, gm.cliente, gm.tipo_gestion"

    cursor.execute(query, tuple(params))
    gestiones = cursor.fetchall()

    if gestiones:
        # =====================================================
        # RESUMEN GENERAL
        # =====================================================
        st.markdown("### 📊 Resumen del Día")

        total_gestiones = len(gestiones)
        total_seriales = sum([g['total_seriales'] for g in gestiones])
        total_valor = sum([g['valor_total'] for g in gestiones])
        mensajeros_unicos = len(set([g['cod_mensajero'] for g in gestiones]))
        clientes_unicos = len(set([g['cliente'] for g in gestiones]))

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("📋 Gestiones", total_gestiones)
        with col2:
            st.metric("📦 Seriales", f"{total_seriales:,}")
        with col3:
            st.metric("💰 Valor Total", f"${total_valor:,.0f}")
        with col4:
            st.metric("👥 Mensajeros", mensajeros_unicos)
        with col5:
            st.metric("🏢 Clientes", clientes_unicos)

        st.divider()

        # =====================================================
        # VISTA POR MENSAJERO - AGRUPADO POR CLIENTE
        # =====================================================
        st.markdown("### 👤 Detalle por Mensajero (Agrupado por Cliente)")

        # Agrupar por mensajero
        from collections import defaultdict
        gestiones_por_mensajero = defaultdict(list)
        for g in gestiones:
            key = (g['cod_mensajero'], g['mensajero_nombre'])
            gestiones_por_mensajero[key].append(g)

        for (cod_mensajero, nombre_mensajero) in sorted(gestiones_por_mensajero.keys()):
            gestiones_mensajero = gestiones_por_mensajero[(cod_mensajero, nombre_mensajero)]
            total_mensajero = sum([g['valor_total'] for g in gestiones_mensajero])
            total_seriales_mensajero = sum([g['total_seriales'] for g in gestiones_mensajero])

            with st.expander(f"👤 **{cod_mensajero} - {nombre_mensajero}** | {total_seriales_mensajero} envíos | ${total_mensajero:,.0f}", expanded=True):

                # Agrupar por cliente Y tipo (entrega/devolución)
                resumen_cliente = defaultdict(lambda: {
                    'entregas': 0,
                    'devoluciones': 0,
                    'valor_entregas': 0,
                    'valor_devoluciones': 0,
                    'precio_entrega': 0,
                    'precio_devolucion': 0,
                    'ids_entregas': [],
                    'ids_devoluciones': []
                })

                for g in gestiones_mensajero:
                    cliente = g['cliente']
                    if 'entrega' in g['tipo_gestion'].lower():
                        resumen_cliente[cliente]['entregas'] += g['total_seriales']
                        resumen_cliente[cliente]['valor_entregas'] += g['valor_total']
                        resumen_cliente[cliente]['precio_entrega'] = g['valor_unitario']
                        resumen_cliente[cliente]['ids_entregas'].append(g['id'])
                    else:
                        resumen_cliente[cliente]['devoluciones'] += g['total_seriales']
                        resumen_cliente[cliente]['valor_devoluciones'] += g['valor_total']
                        resumen_cliente[cliente]['precio_devolucion'] = g['valor_unitario']
                        resumen_cliente[cliente]['ids_devoluciones'].append(g['id'])

                # Mostrar tabla agrupada por cliente
                for cliente in sorted(resumen_cliente.keys()):
                    datos = resumen_cliente[cliente]
                    total_cliente = datos['valor_entregas'] + datos['valor_devoluciones']

                    st.markdown(f"#### 🏢 {cliente}")

                    # Fila de Entregas
                    if datos['entregas'] > 0:
                        col1, col2, col3, col4, col5 = st.columns([1.5, 1.5, 1.5, 1.5, 1])
                        with col1:
                            st.write("✅ **Entregas**")
                        with col2:
                            st.write(f"Cantidad: **{datos['entregas']}**")
                        with col3:
                            st.write(f"Precio: **${datos['precio_entrega']:,.0f}**")
                        with col4:
                            st.write(f"Total: **${datos['valor_entregas']:,.0f}**")
                        with col5:
                            if st.button("✏️", key=f"edit_ent_{cod_mensajero}_{cliente}", help="Editar precio entregas"):
                                st.session_state.editando_grupo = {
                                    'tipo': 'entrega',
                                    'cliente': cliente,
                                    'cod_mensajero': cod_mensajero,
                                    'cantidad': datos['entregas'],
                                    'precio_actual': datos['precio_entrega'],
                                    'ids': datos['ids_entregas']
                                }
                                st.rerun()

                    # Fila de Devoluciones
                    if datos['devoluciones'] > 0:
                        col1, col2, col3, col4, col5 = st.columns([1.5, 1.5, 1.5, 1.5, 1])
                        with col1:
                            st.write("↩️ **Devoluciones**")
                        with col2:
                            st.write(f"Cantidad: **{datos['devoluciones']}**")
                        with col3:
                            st.write(f"Precio: **${datos['precio_devolucion']:,.0f}**")
                        with col4:
                            st.write(f"Total: **${datos['valor_devoluciones']:,.0f}**")
                        with col5:
                            if st.button("✏️", key=f"edit_dev_{cod_mensajero}_{cliente}", help="Editar precio devoluciones"):
                                st.session_state.editando_grupo = {
                                    'tipo': 'devolucion',
                                    'cliente': cliente,
                                    'cod_mensajero': cod_mensajero,
                                    'cantidad': datos['devoluciones'],
                                    'precio_actual': datos['precio_devolucion'],
                                    'ids': datos['ids_devoluciones']
                                }
                                st.rerun()

                    # Subtotal del cliente
                    st.write(f"**Subtotal {cliente}: ${total_cliente:,.0f}**")
                    st.markdown("---")

        # =====================================================
        # FORMULARIO DE EDICIÓN (PRECIO POR GRUPO)
        # =====================================================
        if st.session_state.editando_grupo:
            st.markdown("---")
            st.markdown("### ✏️ Editar Precio")

            grupo = st.session_state.editando_grupo
            tipo_texto = "Entregas" if grupo['tipo'] == 'entrega' else "Devoluciones"
            precio_actual = float(grupo['precio_actual'])
            cantidad = int(grupo['cantidad'])
            total_actual = cantidad * precio_actual

            with st.container():
                st.info(f"**Cliente:** {grupo['cliente']} | **Tipo:** {tipo_texto} | **Cantidad:** {cantidad} | **Registros afectados:** {len(grupo['ids'])}")

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Cantidad Total", cantidad)

                with col2:
                    st.metric("Precio Actual", f"${precio_actual:,.0f}")

                with col3:
                    st.metric("Total Actual", f"${total_actual:,.0f}")

                st.markdown("#### Nuevo Precio")

                col1, col2, col3 = st.columns(3)

                with col1:
                    nuevo_precio = st.number_input(
                        "Nuevo Precio Unitario ($)",
                        min_value=0.0,
                        value=precio_actual,
                        step=50.0,
                        key="edit_precio_grupo"
                    )

                with col2:
                    nuevo_total = cantidad * nuevo_precio
                    st.metric("Nuevo Total", f"${nuevo_total:,.0f}")

                with col3:
                    diferencia = nuevo_total - total_actual
                    st.metric("Diferencia", f"${diferencia:,.0f}", delta=f"${diferencia:,.0f}")

                col_btn1, col_btn2 = st.columns(2)

                with col_btn1:
                    if st.button("💾 Guardar Precio", type="primary", key="btn_guardar_grupo"):
                        try:
                            cursor_update = conn.cursor()

                            # Actualizar todas las gestiones del grupo
                            for gestion_id in grupo['ids']:
                                # Obtener la cantidad de seriales de esta gestión
                                cursor_update.execute(
                                    "SELECT total_seriales FROM gestiones_mensajero WHERE id = %s",
                                    (gestion_id,)
                                )
                                result = cursor_update.fetchone()
                                if result:
                                    cantidad_gestion = result[0]
                                    nuevo_valor_total = cantidad_gestion * nuevo_precio

                                    cursor_update.execute("""
                                        UPDATE gestiones_mensajero
                                        SET valor_unitario = %s,
                                            valor_total = %s
                                        WHERE id = %s
                                    """, (nuevo_precio, nuevo_valor_total, gestion_id))

                            conn.commit()
                            cursor_update.close()

                            st.session_state.editando_grupo = None
                            st.success(f"✅ Precio actualizado en {len(grupo['ids'])} registro(s)")
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error al actualizar: {e}")

                with col_btn2:
                    if st.button("❌ Cancelar", key="btn_cancelar_grupo"):
                        st.session_state.editando_grupo = None
                        st.rerun()

        # =====================================================
        # RESUMEN POR MENSAJERO Y PRECIO
        # =====================================================
        st.divider()
        st.markdown("### 👤 Resumen por Mensajero y Precio")
        st.info(f"📅 Período: {fecha_desde.strftime('%d/%m/%Y')} - {fecha_hasta.strftime('%d/%m/%Y')}")

        # Agrupar por mensajero -> precio -> cantidad
        resumen_mensajero_precio = defaultdict(lambda: defaultdict(lambda: {'cantidad': 0, 'valor': 0}))
        totales_mensajero = defaultdict(lambda: {'cantidad': 0, 'valor': 0})

        for g in gestiones:
            mensajero_key = f"{g['cod_mensajero']} - {g['mensajero_nombre']}"
            precio = float(g['valor_unitario'])
            cantidad = int(g['total_seriales'])
            valor = float(g['valor_total'])

            resumen_mensajero_precio[mensajero_key][precio]['cantidad'] += cantidad
            resumen_mensajero_precio[mensajero_key][precio]['valor'] += valor
            totales_mensajero[mensajero_key]['cantidad'] += cantidad
            totales_mensajero[mensajero_key]['valor'] += valor

        # Mostrar por mensajero
        for mensajero in sorted(resumen_mensajero_precio.keys()):
            precios_data = resumen_mensajero_precio[mensajero]
            total_mensajero = totales_mensajero[mensajero]

            with st.expander(f"👤 **{mensajero}** | Total: {total_mensajero['cantidad']} envíos | ${total_mensajero['valor']:,.0f}", expanded=False):

                # Crear tabla de precios
                tabla_precios = []
                for precio in sorted(precios_data.keys()):
                    datos = precios_data[precio]
                    tabla_precios.append({
                        'Precio Unitario': f"${precio:,.0f}",
                        'Cantidad': datos['cantidad'],
                        'Subtotal': f"${datos['valor']:,.0f}"
                    })

                df_precios = pd.DataFrame(tabla_precios)
                st.dataframe(df_precios, use_container_width=True, hide_index=True)

                # Totales
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("📦 Total Envíos", f"{total_mensajero['cantidad']:,}")
                with col2:
                    st.metric("💰 Valor Total", f"${total_mensajero['valor']:,.0f}")

        # =====================================================
        # TABLA RESUMEN GENERAL POR MENSAJERO
        # =====================================================
        st.markdown("#### 📋 Tabla Resumen General")

        tabla_general = []
        gran_total_cantidad = 0
        gran_total_valor = 0

        for mensajero in sorted(totales_mensajero.keys()):
            total = totales_mensajero[mensajero]
            tabla_general.append({
                'Mensajero': mensajero,
                'Total Envíos': total['cantidad'],
                'Valor Total': f"${total['valor']:,.0f}"
            })
            gran_total_cantidad += total['cantidad']
            gran_total_valor += total['valor']

        df_general = pd.DataFrame(tabla_general)
        st.dataframe(df_general, use_container_width=True, hide_index=True)

        # Gran total
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("👥 Mensajeros", len(totales_mensajero))
        with col2:
            st.metric("📦 Gran Total Envíos", f"{gran_total_cantidad:,}")
        with col3:
            st.metric("💰 Gran Total Valor", f"${gran_total_valor:,.0f}")

        # =====================================================
        # RESUMEN POR CLIENTE (TABLA)
        # =====================================================
        st.divider()
        st.markdown("### 📊 Resumen por Cliente")

        # Crear tabla resumen
        resumen_clientes = defaultdict(lambda: {'entregas': 0, 'devoluciones': 0, 'valor': 0})
        for g in gestiones:
            cliente = g['cliente']
            if 'entrega' in g['tipo_gestion'].lower():
                resumen_clientes[cliente]['entregas'] += int(g['total_seriales'])
            else:
                resumen_clientes[cliente]['devoluciones'] += int(g['total_seriales'])
            resumen_clientes[cliente]['valor'] += float(g['valor_total'])

        tabla_resumen = []
        for cliente, datos in sorted(resumen_clientes.items()):
            tabla_resumen.append({
                'Cliente': cliente,
                'Entregas': datos['entregas'],
                'Devoluciones': datos['devoluciones'],
                'Total Seriales': datos['entregas'] + datos['devoluciones'],
                'Valor Total': f"${datos['valor']:,.0f}"
            })

        df_resumen = pd.DataFrame(tabla_resumen)
        st.dataframe(df_resumen, use_container_width=True, hide_index=True)

        # =====================================================
        # EXPORTAR A CSV
        # =====================================================
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            # Preparar datos para exportar
            df_export = pd.DataFrame(gestiones)
            csv = df_export.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar Detalle (CSV)",
                data=csv,
                file_name=f"gestiones_{fecha_desde.strftime('%Y%m%d')}_{fecha_hasta.strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

    else:
        st.info(f"📭 No hay gestiones entre {fecha_desde.strftime('%d/%m/%Y')} y {fecha_hasta.strftime('%d/%m/%Y')} para los filtros seleccionados")

        # Mostrar fechas disponibles
        cursor.execute("""
            SELECT DISTINCT DATE(fecha_registro) as fecha, COUNT(*) as total
            FROM gestiones_mensajero
            GROUP BY DATE(fecha_registro)
            ORDER BY fecha DESC
            LIMIT 10
        """)
        fechas_disponibles = cursor.fetchall()

        if fechas_disponibles:
            st.markdown("#### 📅 Fechas con gestiones disponibles:")
            for f in fechas_disponibles:
                st.write(f"- {f['fecha'].strftime('%d/%m/%Y')}: {f['total']} gestiones")

except Exception as e:
    st.error(f"Error: {e}")
    import traceback
    st.code(traceback.format_exc())

if 'cursor' in locals():
    cursor.close()
