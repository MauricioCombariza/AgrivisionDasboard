import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import sys
import os
import io

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_connection import conectar_logistica


st.title("💰 Facturación y Pagos")

conn = conectar_logistica()
if not conn:
    st.stop()

# Migraciones de schema: correr UNA sola vez por sesión (no en cada rerun)
if 'facturacion_schema_ok' not in st.session_state:
    for _sql_liq in [
        "ALTER TABLE gestiones_mensajero ADD COLUMN facturado_liq INT NULL DEFAULT NULL",
        "ALTER TABLE registro_horas ADD COLUMN liquidado TINYINT(1) NOT NULL DEFAULT 0",
        "ALTER TABLE registro_labores ADD COLUMN liquidado TINYINT(1) NOT NULL DEFAULT 0",
        "ALTER TABLE facturas_recibidas MODIFY COLUMN tipo VARCHAR(50) NOT NULL DEFAULT 'otros'",
        "ALTER TABLE gastos_administrativos ADD COLUMN empresa VARCHAR(200) NULL",
        "ALTER TABLE gastos_administrativos ADD COLUMN numero_factura_ext VARCHAR(100) NULL",
    ]:
        try:
            _c = conn.cursor()
            _c.execute(_sql_liq)
            conn.commit()
            _c.close()
        except Exception:
            conn.rollback()

    try:
        _c_fix = conn.cursor()
        _c_fix.execute("""
            UPDATE gestiones_mensajero gm
            JOIN facturas_recibidas fr ON gm.facturado_liq = fr.id
            JOIN personal p ON fr.personal_id = p.id
            SET gm.facturado_liq = NULL
            WHERE CAST(gm.cod_mensajero AS UNSIGNED) != CAST(p.codigo AS UNSIGNED)
        """)
        conn.commit()
        _c_fix.close()
    except Exception:
        conn.rollback()

    st.session_state['facturacion_schema_ok'] = True

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📄 Facturas Emitidas (Clientes)",
    "💵 Registrar Pago Recibido",
    "📊 Resumen Financiero",
    "📥 Facturas Proveedores",
    "📋 Cuentas por Pagar",
    "👷 Pago Personal",
    "💼 Adelantos Dueño",
])

with tab1:
    st.subheader("Facturas Emitidas a Clientes")

    # Estado para confirmación de borrado
    if '_fac_ids_borrar' not in st.session_state:
        st.session_state._fac_ids_borrar = []
    if '_fac_nums_borrar' not in st.session_state:
        st.session_state._fac_nums_borrar = []

    col1, col2 = st.columns([3, 1])

    with col1:
        filtro = st.radio(
            "Mostrar",
            ["Pendientes", "Pagadas", "Todas"],
            horizontal=True,
            key="filtro_facturas_emitidas"
        )
        where_estado = {
            "Pendientes": "AND fe.estado NOT IN ('pagada', 'anulada')",
            "Pagadas":    "AND fe.estado = 'pagada'",
            "Todas":      "",
        }[filtro]

        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(f"""
                SELECT
                    fe.id, fe.numero_factura, c.nombre_empresa as cliente,
                    fe.fecha_emision, fe.fecha_vencimiento,
                    fe.cantidad_items, fe.total, fe.saldo_pendiente, fe.estado
                FROM facturas_emitidas fe
                JOIN clientes c ON fe.cliente_id = c.id
                WHERE 1=1 {where_estado}
                ORDER BY fe.fecha_emision DESC
                LIMIT 200
            """)
            facturas = cursor.fetchall()

            if facturas:
                df = pd.DataFrame(facturas)
                df_export = df.copy()

                # Calcular valor unitario
                df['valor_unitario'] = df.apply(
                    lambda r: float(r['total']) / float(r['cantidad_items'])
                    if r['cantidad_items'] and float(r['cantidad_items']) > 0 else 0.0,
                    axis=1
                )
                df_export['valor_unitario'] = df['valor_unitario']

                # Formatear para pantalla
                df['fecha_emision']    = pd.to_datetime(df['fecha_emision']).dt.strftime('%d/%m/%Y')
                df['fecha_vencimiento']= pd.to_datetime(df['fecha_vencimiento']).dt.strftime('%d/%m/%Y')
                df['cantidad_items']   = df['cantidad_items'].apply(lambda x: f"{int(x):,}" if x else '0')
                df['valor_unitario']   = df['valor_unitario'].apply(lambda x: f"${x:,.2f}")
                df['total']            = df['total'].apply(lambda x: f"${float(x):,.0f}")
                df['saldo_pendiente']  = df['saldo_pendiente'].apply(lambda x: f"${float(x):,.0f}")

                estado_colors = {
                    'pendiente': '🔴', 'parcial': '🟡',
                    'pagada': '🟢', 'vencida': '⚫', 'anulada': '❌'
                }
                df['estado'] = df['estado'].apply(lambda x: f"{estado_colors.get(x, '')} {x}")

                # Reordenar columnas
                df_display = df[['numero_factura', 'cliente', 'fecha_emision', 'fecha_vencimiento',
                                 'cantidad_items', 'valor_unitario', 'total', 'saldo_pendiente', 'estado']].copy()
                df_display.columns = ['Número Factura', 'Cliente', 'Fecha Emisión', 'Fecha Vencimiento',
                                      'Cantidad Envíos', 'Valor Unit.', 'Total', 'Saldo Pendiente', 'Estado']
                df_display.insert(0, '☑', False)

                edited = st.data_editor(
                    df_display,
                    use_container_width=True,
                    hide_index=True,
                    column_config={'☑': st.column_config.CheckboxColumn('☑', width='small')},
                    disabled=[c for c in df_display.columns if c != '☑'],
                    key="fe_check_table",
                )

                seleccionadas = edited[edited['☑']]
                if not seleccionadas.empty:
                    # Obtener totales y saldos numéricos de df_export para las filas seleccionadas
                    idx_sel = seleccionadas.index
                    total_sel   = df_export.loc[idx_sel, 'total'].astype(float).sum()
                    saldo_sel   = df_export.loc[idx_sel, 'saldo_pendiente'].astype(float).sum()
                    items_sel   = df_export.loc[idx_sel, 'cantidad_items'].astype(float).sum()
                    st.info(
                        f"**{len(seleccionadas)} factura(s) seleccionada(s)** — "
                        f"Envíos: **{int(items_sel):,}** · "
                        f"Total: **${total_sel:,.0f}** · "
                        f"Saldo por cobrar: **${saldo_sel:,.0f}**"
                    )

                    # Guardar IDs seleccionados para el panel de borrado en col2
                    _ids_sel  = df.loc[idx_sel, 'id'].tolist()
                    _nums_sel = [str(n) for n in df.loc[idx_sel, 'numero_factura'].tolist()]
                    if st.button("🗑️ Eliminar factura(s) seleccionada(s)", key="btn_del_fac_trigger", type="secondary"):
                        st.session_state._fac_ids_borrar  = _ids_sel
                        st.session_state._fac_nums_borrar = _nums_sel

                try:
                    df_export['fecha_emision']    = pd.to_datetime(df_export['fecha_emision'])
                    df_export['fecha_vencimiento']= pd.to_datetime(df_export['fecha_vencimiento'])
                    df_export = df_export[['numero_factura', 'cliente', 'fecha_emision', 'fecha_vencimiento',
                                           'cantidad_items', 'valor_unitario', 'total', 'saldo_pendiente', 'estado']]
                    df_export.columns = [
                        'Número Factura', 'Cliente', 'Fecha Emisión', 'Fecha Vencimiento',
                        'Cantidad Envíos', 'Valor Unit.', 'Total', 'Saldo Pendiente', 'Estado'
                    ]
                    buf_fac = io.BytesIO()
                    with pd.ExcelWriter(buf_fac, engine='openpyxl') as writer:
                        df_export.to_excel(writer, index=False, sheet_name='Facturas Emitidas')
                    st.download_button("📥 Exportar a Excel", buf_fac.getvalue(), "facturas_emitidas.xlsx",
                                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                       key="export_facturas_emitidas")
                except Exception as e:
                    st.error(f"Error al exportar: {e}")
            else:
                st.info("No hay facturas para el filtro seleccionado")
        except Exception as e:
            st.error(f"Error: {e}")

    with col2:
        st.markdown("### 📊 Resumen")
        try:
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT COUNT(*) as total FROM facturas_emitidas WHERE estado != 'pagada' AND estado != 'anulada'")
            pendientes = cursor.fetchone()['total']
            st.metric("Facturas Pendientes", pendientes)

            cursor.execute("SELECT SUM(saldo_pendiente) as total FROM facturas_emitidas WHERE estado NOT IN ('pagada', 'anulada')")
            saldo = cursor.fetchone()['total'] or 0
            st.metric("Por Cobrar", f"${saldo:,.0f}")

            cursor.execute("SELECT COUNT(*) as total FROM facturas_emitidas WHERE estado = 'vencida'")
            vencidas = cursor.fetchone()['total']
            st.metric("Vencidas", vencidas, delta_color="inverse")
        except Exception as e:
            st.error(f"Error: {e}")

        # ── Panel de confirmación de borrado ──────────────────────────────────
        if st.session_state._fac_ids_borrar:
            st.divider()
            st.markdown("### 🗑️ Confirmar eliminación")
            st.error(
                f"Se eliminarán **{len(st.session_state._fac_ids_borrar)}** factura(s) y todos sus pagos.\n\n"
                "Las órdenes vinculadas quedarán disponibles para facturar nuevamente."
            )
            for num in st.session_state._fac_nums_borrar:
                st.caption(f"• {num}")

            if st.button("✅ Sí, eliminar", key="btn_del_fac_confirm", type="primary", use_container_width=True):
                try:
                    _cur_del = conn.cursor()
                    for _fid in st.session_state._fac_ids_borrar:
                        # 1. Liberar órdenes vinculadas
                        _cur_del.execute("""
                            UPDATE ordenes o
                            JOIN detalle_facturas_emitidas dfe ON dfe.orden_id = o.id
                            SET o.facturado = FALSE
                            WHERE dfe.factura_id = %s AND dfe.orden_id IS NOT NULL
                        """, (_fid,))
                        # 2. Borrar pagos recibidos
                        _cur_del.execute("DELETE FROM pagos_recibidos WHERE factura_id = %s", (_fid,))
                        # 3. Borrar detalle
                        _cur_del.execute("DELETE FROM detalle_facturas_emitidas WHERE factura_id = %s", (_fid,))
                        # 4. Borrar factura
                        _cur_del.execute("DELETE FROM facturas_emitidas WHERE id = %s", (_fid,))
                    conn.commit()
                    _cur_del.close()
                    st.success(f"✅ {len(st.session_state._fac_ids_borrar)} factura(s) eliminada(s)")
                    st.session_state._fac_ids_borrar  = []
                    st.session_state._fac_nums_borrar = []
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"Error al eliminar: {e}")

            if st.button("❌ Cancelar", key="btn_del_fac_cancel", use_container_width=True):
                st.session_state._fac_ids_borrar  = []
                st.session_state._fac_nums_borrar = []
                st.rerun()

    st.divider()

    # ── Diagnóstico: órdenes en más de una factura ────────────────────────────
    with st.expander("🔍 Diagnóstico: órdenes facturadas más de una vez", expanded=False):
        try:
            _cur_diag = conn.cursor(dictionary=True)
            _cur_diag.execute("""
                SELECT
                    o.numero_orden,
                    c.nombre_empresa as cliente,
                    GROUP_CONCAT(fe.numero_factura ORDER BY fe.fecha_emision SEPARATOR ' | ') as facturas,
                    COUNT(dfe.factura_id) as veces
                FROM detalle_facturas_emitidas dfe
                JOIN ordenes o ON dfe.orden_id = o.id
                JOIN facturas_emitidas fe ON dfe.factura_id = fe.id
                JOIN clientes c ON fe.cliente_id = c.id
                WHERE dfe.orden_id IS NOT NULL
                GROUP BY dfe.orden_id
                HAVING COUNT(dfe.factura_id) > 1
                ORDER BY c.nombre_empresa, o.numero_orden
            """)
            _duplicados_diag = _cur_diag.fetchall()
            _cur_diag.close()

            if _duplicados_diag:
                st.error(f"⚠️ Se encontraron **{len(_duplicados_diag)}** órdenes en más de una factura:")
                _df_diag = pd.DataFrame(_duplicados_diag)
                _df_diag.columns = ['Orden', 'Cliente', 'Facturas', 'Veces facturada']
                st.dataframe(_df_diag, use_container_width=True, hide_index=True)
                st.caption("Para corregir: elimina la factura duplicada usando el checkbox y el botón '🗑️ Eliminar'.")
            else:
                st.success("✅ No hay órdenes duplicadas en facturas.")
        except Exception as e:
            st.error(f"Error en diagnóstico: {e}")

    st.divider()

    st.markdown("### ➕ Crear Nueva Factura")

    # === PASO 1: Seleccionar Cliente (fuera del form para actualizar órdenes) ===
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre_empresa FROM clientes WHERE activo = TRUE ORDER BY nombre_empresa")
    clientes = cursor.fetchall()
    if not clientes:
        st.error("No hay clientes activos")
        st.stop()
    cliente_options = {c['nombre_empresa']: c['id'] for c in clientes}

    col_cliente, col_empty = st.columns([2, 2])
    with col_cliente:
        cliente_sel = st.selectbox("👥 Seleccionar Cliente", list(cliente_options.keys()), key="cliente_factura")
        cliente_id = cliente_options[cliente_sel]

    # === PASO 2: Mostrar Órdenes del Cliente con Checkboxes ===
    st.markdown("### 📦 Órdenes Disponibles para Facturar")

    cursor.execute("""
        SELECT id, numero_orden, fecha_recepcion, cantidad_total, valor_total, estado
        FROM ordenes
        WHERE cliente_id = %s
        AND (facturado = FALSE OR facturado IS NULL)
        ORDER BY fecha_recepcion DESC
    """, (cliente_id,))
    ordenes_disponibles = cursor.fetchall()

    # Inicializar session state para órdenes seleccionadas
    if 'ordenes_seleccionadas_factura' not in st.session_state:
        st.session_state.ordenes_seleccionadas_factura = []

    ordenes_ids_seleccionadas = []

    if ordenes_disponibles:
        st.caption(f"Se encontraron {len(ordenes_disponibles)} órdenes sin facturar para {cliente_sel}")

        # Crear tabla con checkboxes
        col_check, col_orden, col_fecha, col_items, col_valor, col_estado = st.columns([0.5, 2, 1.5, 1, 1.5, 1])
        with col_check:
            st.markdown("**✓**")
        with col_orden:
            st.markdown("**Orden**")
        with col_fecha:
            st.markdown("**Fecha**")
        with col_items:
            st.markdown("**Items**")
        with col_valor:
            st.markdown("**Valor**")
        with col_estado:
            st.markdown("**Estado**")

        total_valor_seleccionado = 0
        total_items_seleccionado = 0

        for orden in ordenes_disponibles:
            col_check, col_orden, col_fecha, col_items, col_valor, col_estado = st.columns([0.5, 2, 1.5, 1, 1.5, 1])

            with col_check:
                seleccionada = st.checkbox(
                    "sel",
                    key=f"orden_{orden['id']}",
                    label_visibility="collapsed"
                )
                if seleccionada:
                    ordenes_ids_seleccionadas.append(orden['id'])
                    total_valor_seleccionado += float(orden['valor_total'] or 0)
                    total_items_seleccionado += int(orden['cantidad_total'] or 0)

            with col_orden:
                st.write(orden['numero_orden'])
            with col_fecha:
                st.write(orden['fecha_recepcion'].strftime('%d/%m/%Y') if orden['fecha_recepcion'] else '-')
            with col_items:
                st.write(f"{orden['cantidad_total']:,}")
            with col_valor:
                st.write(f"${orden['valor_total']:,.0f}")
            with col_estado:
                st.write(orden['estado'])

        if ordenes_ids_seleccionadas:
            st.success(f"✅ {len(ordenes_ids_seleccionadas)} órdenes seleccionadas | Items: {total_items_seleccionado:,} | Valor: ${total_valor_seleccionado:,.0f}")
    else:
        st.info("No hay órdenes pendientes de facturar para este cliente")
        total_valor_seleccionado = 0
        total_items_seleccionado = 0

    st.divider()

    # === PASO 3: Formulario de Factura ===
    st.markdown("### 💵 Datos de la Factura")

    with st.form("form_factura"):
        col1, col2, col3 = st.columns(3)

        with col1:
            numero_factura = st.text_input("Número Factura *")

        with col2:
            fecha_emision = st.date_input("Fecha Emisión *", value=date.today())
            plazo_dias = st.number_input("Plazo Días", min_value=0, value=30, step=1)
            fecha_vencimiento = fecha_emision + timedelta(days=plazo_dias)
            st.info(f"Vencimiento: {fecha_vencimiento.strftime('%d/%m/%Y')}")

        with col3:
            periodo_mes = st.number_input("Mes Periodo", min_value=1, max_value=12, value=date.today().month)
            periodo_anio = st.number_input("Año Periodo", min_value=2020, max_value=2030, value=date.today().year)

        st.divider()

        # === VALOR DE LA FACTURA ===
        col_val1, col_val2 = st.columns(2)
        with col_val1:
            # Usar valor de órdenes seleccionadas como default si hay
            default_valor = float(total_valor_seleccionado) if total_valor_seleccionado > 0 else 0.0
            total_factura = st.number_input(
                "Valor Total a Facturar *",
                min_value=0.0,
                value=default_valor,
                step=10000.0,
                format="%.0f",
                help="Puede modificar el valor. Por defecto es la suma de órdenes seleccionadas."
            )
        with col_val2:
            default_items = total_items_seleccionado if total_items_seleccionado > 0 else 0
            cantidad_items = st.number_input(
                "Cantidad de Items",
                min_value=0,
                value=default_items,
                step=1
            )

        descripcion_factura = st.text_input(
            "Descripción / Concepto",
            value=f"Servicio de mensajería {periodo_mes}/{periodo_anio}"
        )

        # Mostrar resumen de órdenes seleccionadas
        if ordenes_ids_seleccionadas:
            st.info(f"📦 Se vincularán {len(ordenes_ids_seleccionadas)} órdenes a esta factura")

        st.divider()
        st.metric("💰 Total a Facturar", f"${total_factura:,.0f}")

        submitted = st.form_submit_button("💾 Crear Factura", type="primary")

        if submitted:
            if not numero_factura:
                st.error("El número de factura es obligatorio")
            elif total_factura <= 0:
                st.error("El valor de la factura debe ser mayor a 0")
            else:
                # ── Verificar que ninguna orden ya esté en otra factura ────────
                _ordenes_duplicadas = []
                if ordenes_ids_seleccionadas:
                    try:
                        _cur_chk = conn.cursor(dictionary=True)
                        _ph = ','.join(['%s'] * len(ordenes_ids_seleccionadas))
                        _cur_chk.execute(f"""
                            SELECT o.numero_orden, fe.numero_factura, fe.id as factura_id
                            FROM detalle_facturas_emitidas dfe
                            JOIN facturas_emitidas fe ON dfe.factura_id = fe.id
                            JOIN ordenes o ON dfe.orden_id = o.id
                            WHERE dfe.orden_id IN ({_ph})
                        """, ordenes_ids_seleccionadas)
                        _ordenes_duplicadas = _cur_chk.fetchall()
                        _cur_chk.close()
                    except Exception:
                        pass

                if _ordenes_duplicadas:
                    st.error("⚠️ Las siguientes órdenes ya están vinculadas a otra factura:")
                    for _dup in _ordenes_duplicadas:
                        st.error(f"  • Orden **{_dup['numero_orden']}** → factura **{_dup['numero_factura']}**")
                    st.warning("Elimina la factura existente o deselecciona esas órdenes antes de continuar.")
                else:
                    try:
                        cursor = conn.cursor()

                        # Cantidad de items: usar ingresado o contar órdenes seleccionadas
                        items_factura = cantidad_items if cantidad_items > 0 else (len(ordenes_ids_seleccionadas) if ordenes_ids_seleccionadas else 1)

                        cursor.execute("""
                            INSERT INTO facturas_emitidas
                            (numero_factura, cliente_id, fecha_emision, fecha_vencimiento,
                             periodo_mes, periodo_anio, cantidad_items, subtotal, total, saldo_pendiente, estado)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pendiente')
                        """, (numero_factura, cliente_id, fecha_emision, fecha_vencimiento,
                              periodo_mes, periodo_anio, items_factura,
                              total_factura, total_factura, total_factura))

                        factura_id = cursor.lastrowid

                        # Insertar detalle principal con la descripción
                        cursor.execute("""
                            INSERT INTO detalle_facturas_emitidas
                            (factura_id, orden_id, descripcion, cantidad, precio_unitario, subtotal)
                            VALUES (%s, NULL, %s, %s, %s, %s)
                        """, (factura_id,
                              descripcion_factura or f"Facturación período {periodo_mes}/{periodo_anio}",
                              items_factura,
                              total_factura / items_factura if items_factura > 0 else total_factura,
                              total_factura))

                        # Si hay órdenes seleccionadas con checkboxes, vincularlas y marcarlas como facturadas
                        ordenes_vinculadas = 0
                        if ordenes_ids_seleccionadas:
                            for orden_id_sel in ordenes_ids_seleccionadas:
                                orden = [o for o in ordenes_disponibles if o['id'] == orden_id_sel][0]

                                cursor.execute("""
                                    INSERT INTO detalle_facturas_emitidas
                                    (factura_id, orden_id, descripcion, cantidad, precio_unitario, subtotal)
                                    VALUES (%s, %s, %s, %s, 0, 0)
                                """, (factura_id, orden['id'], f"Orden vinculada: {orden['numero_orden']}", orden['cantidad_total']))

                                cursor.execute("UPDATE ordenes SET facturado = TRUE WHERE id = %s", (orden['id'],))
                                ordenes_vinculadas += 1

                        conn.commit()
                        msg = f"✅ Factura {numero_factura} creada por ${total_factura:,.0f}"
                        if ordenes_vinculadas > 0:
                            msg += f" | {ordenes_vinculadas} órdenes vinculadas y marcadas como facturadas"
                        st.success(msg)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al crear factura: {e}")
                        import traceback
                        st.code(traceback.format_exc())
                        conn.rollback()

with tab2:
    st.subheader("Registrar Pago Recibido")

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT fe.id, fe.numero_factura, c.nombre_empresa as cliente, fe.saldo_pendiente
            FROM facturas_emitidas fe
            JOIN clientes c ON fe.cliente_id = c.id
            WHERE fe.estado IN ('pendiente', 'parcial', 'vencida')
            ORDER BY fe.fecha_emision DESC
        """)
        facturas_pendientes = cursor.fetchall()

        if not facturas_pendientes:
            st.info("No hay facturas pendientes de pago")
        else:
            factura_options = {
                f"{f['numero_factura']} - {f['cliente']} - Saldo: ${f['saldo_pendiente']:,.0f}": f['id']
                for f in facturas_pendientes
            }
            factura_sel = st.selectbox("Seleccionar Factura", list(factura_options.keys()))
            factura_id = factura_options[factura_sel]

            factura_data = [f for f in facturas_pendientes if f['id'] == factura_id][0]

            st.divider()

            st.markdown("### 📋 Pagos Registrados")
            cursor.execute("""
                SELECT fecha_pago, monto, metodo_pago, referencia
                FROM pagos_recibidos
                WHERE factura_id = %s
                ORDER BY fecha_pago DESC
            """, (factura_id,))
            pagos = cursor.fetchall()

            if pagos:
                df = pd.DataFrame(pagos)
                df['fecha_pago'] = pd.to_datetime(df['fecha_pago']).dt.strftime('%d/%m/%Y')
                df['monto'] = df['monto'].apply(lambda x: f"${x:,.0f}")
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No hay pagos registrados para esta factura")

            st.divider()

            st.markdown("### ➕ Registrar Nuevo Pago")

            with st.form("form_pago"):
                col1, col2 = st.columns(2)

                with col1:
                    fecha_pago = st.date_input("Fecha Pago *", value=date.today())
                    monto = st.number_input(
                        "Monto *",
                        min_value=0.0,
                        max_value=float(factura_data['saldo_pendiente']),
                        value=float(factura_data['saldo_pendiente']),
                        step=100.0
                    )

                with col2:
                    metodo_pago = st.selectbox("Método de Pago *", [
                        "transferencia", "efectivo", "cheque", "tarjeta", "otros"
                    ])
                    referencia = st.text_input("Referencia/Comprobante")

                observaciones = st.text_area("Observaciones")

                submitted = st.form_submit_button("💾 Registrar Pago")

                if submitted:
                    if monto <= 0:
                        st.error("El monto debe ser mayor a 0")
                    else:
                        try:
                            cursor = conn.cursor()

                            cursor.execute("""
                                INSERT INTO pagos_recibidos
                                (factura_id, fecha_pago, monto, metodo_pago, referencia, observaciones)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (factura_id, fecha_pago, monto, metodo_pago, referencia, observaciones))

                            nuevo_saldo = factura_data['saldo_pendiente'] - monto
                            nuevo_estado = 'pagada' if nuevo_saldo <= 0 else 'parcial'

                            cursor.execute("""
                                UPDATE facturas_emitidas SET
                                saldo_pendiente = %s,
                                estado = %s
                                WHERE id = %s
                            """, (nuevo_saldo, nuevo_estado, factura_id))

                            conn.commit()
                            st.success(f"✅ Pago de ${monto:,.0f} registrado exitosamente")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                            conn.rollback()

    except Exception as e:
        st.error(f"Error: {e}")

with tab3:
    st.subheader("Resumen Financiero")

    try:
        cursor = conn.cursor(dictionary=True)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            cursor.execute("SELECT SUM(saldo_pendiente) as total FROM facturas_emitidas WHERE estado NOT IN ('pagada', 'anulada')")
            por_cobrar = cursor.fetchone()['total'] or 0
            st.metric("💵 Por Cobrar", f"${por_cobrar:,.0f}")

        with col2:
            cursor.execute("""
                SELECT SUM(saldo_pendiente) as total FROM facturas_emitidas
                WHERE estado = 'vencida'
            """)
            vencido = cursor.fetchone()['total'] or 0
            st.metric("⚠️ Vencido", f"${vencido:,.0f}", delta_color="inverse")

        with col3:
            cursor.execute("""
                SELECT SUM(monto) as total FROM pagos_recibidos
                WHERE MONTH(fecha_pago) = MONTH(CURRENT_DATE)
                AND YEAR(fecha_pago) = YEAR(CURRENT_DATE)
            """)
            recibido_mes = cursor.fetchone()['total'] or 0
            st.metric("📈 Recibido Este Mes", f"${recibido_mes:,.0f}")

        with col4:
            cursor.execute("""
                SELECT COUNT(*) as total FROM facturas_emitidas
                WHERE estado IN ('pendiente', 'parcial', 'vencida')
            """)
            facturas_abiertas = cursor.fetchone()['total']
            st.metric("📄 Facturas Abiertas", facturas_abiertas)

        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 🔴 Facturas Vencidas")
            cursor.execute("""
                SELECT
                    fe.numero_factura, c.nombre_empresa as cliente,
                    fe.fecha_vencimiento, fe.saldo_pendiente
                FROM facturas_emitidas fe
                JOIN clientes c ON fe.cliente_id = c.id
                WHERE fe.estado = 'vencida'
                ORDER BY fe.fecha_vencimiento
                LIMIT 10
            """)
            vencidas = cursor.fetchall()

            if vencidas:
                for v in vencidas:
                    dias_vencido = (date.today() - v['fecha_vencimiento']).days
                    st.error(f"**{v['numero_factura']}** - {v['cliente']} - ${v['saldo_pendiente']:,.0f} ({dias_vencido} días vencido)")
            else:
                st.success("✅ No hay facturas vencidas")

        with col2:
            st.markdown("### 🟡 Próximas a Vencer (7 días)")
            cursor.execute("""
                SELECT
                    fe.numero_factura, c.nombre_empresa as cliente,
                    fe.fecha_vencimiento, fe.saldo_pendiente
                FROM facturas_emitidas fe
                JOIN clientes c ON fe.cliente_id = c.id
                WHERE fe.estado IN ('pendiente', 'parcial')
                AND fe.fecha_vencimiento BETWEEN CURRENT_DATE AND DATE_ADD(CURRENT_DATE, INTERVAL 7 DAY)
                ORDER BY fe.fecha_vencimiento
            """)
            por_vencer = cursor.fetchall()

            if por_vencer:
                for pv in por_vencer:
                    dias = (pv['fecha_vencimiento'] - date.today()).days
                    st.warning(f"**{pv['numero_factura']}** - {pv['cliente']} - ${pv['saldo_pendiente']:,.0f} (vence en {dias} días)")
            else:
                st.info("No hay facturas por vencer en los próximos 7 días")

    except Exception as e:
        st.error(f"Error: {e}")

with tab4:
    st.subheader("Facturas de Proveedores")

    try:
        cursor = conn.cursor(dictionary=True)

        # Formulario para registrar factura de proveedor
        st.markdown("### Registrar Factura de Proveedor")

        # Obtener personal para selector de proveedor
        cursor.execute("""
            SELECT id, nombre_completo, tipo_personal
            FROM personal WHERE activo = TRUE
            ORDER BY nombre_completo
        """)
        proveedores = cursor.fetchall()

        with st.form("form_factura_proveedor"):
            col1, col2, col3 = st.columns(3)

            with col1:
                num_factura_prov = st.text_input("Numero de Factura *", key="num_fact_prov")
                tipo_factura_prov = st.selectbox("Tipo", ['materiales', 'otros'], key="tipo_fact_prov")

            with col2:
                # Proveedor: texto libre o seleccionar de personal
                modo_proveedor = st.radio("Proveedor", ["Seleccionar de Personal", "Escribir nombre"], horizontal=True, key="modo_prov")
                if modo_proveedor == "Seleccionar de Personal" and proveedores:
                    prov_options = {f"{p['nombre_completo']} ({p['tipo_personal']})": p['id'] for p in proveedores}
                    prov_sel = st.selectbox("Personal", list(prov_options.keys()), key="prov_sel")
                    personal_id_prov = prov_options[prov_sel]
                else:
                    personal_id_prov = None
                    if proveedores:
                        # Si elige escribir, necesitamos igualmente un personal_id
                        st.caption("Se asignara al primer registro de personal disponible")
                        personal_id_prov = proveedores[0]['id']

            with col3:
                fecha_recepcion_prov = st.date_input("Fecha Recepcion", value=date.today(), key="fecha_rec_prov")
                plazo_dias_prov = st.number_input("Plazo Dias", min_value=0, value=30, step=1, key="plazo_prov")
                fecha_venc_prov = fecha_recepcion_prov + timedelta(days=plazo_dias_prov)
                st.info(f"Vencimiento: {fecha_venc_prov.strftime('%d/%m/%Y')}")

            col_val1, col_val2 = st.columns(2)
            with col_val1:
                total_prov = st.number_input("Total *", min_value=0.0, step=10000.0, format="%.2f", key="total_prov")
            with col_val2:
                descripcion_prov = st.text_input("Descripcion / Concepto", key="desc_prov")

            submitted_prov = st.form_submit_button("Guardar Factura Proveedor", type="primary")

            if submitted_prov:
                if not num_factura_prov:
                    st.error("El numero de factura es obligatorio")
                elif total_prov <= 0:
                    st.error("El total debe ser mayor a 0")
                elif not personal_id_prov:
                    st.error("Seleccione un proveedor")
                else:
                    try:
                        cursor_w = conn.cursor()
                        cursor_w.execute("""
                            INSERT INTO facturas_recibidas
                            (numero_factura, personal_id, tipo, fecha_recepcion, fecha_vencimiento,
                             subtotal, total, saldo_pendiente, observaciones)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (num_factura_prov, personal_id_prov, tipo_factura_prov,
                              fecha_recepcion_prov, fecha_venc_prov,
                              total_prov, total_prov, total_prov,
                              descripcion_prov or None))
                        conn.commit()
                        st.success(f"Factura {num_factura_prov} registrada exitosamente")
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Error: {e}")

        st.divider()

        # Listado de facturas de proveedores
        st.markdown("### Facturas de Proveedores Registradas")

        cursor.execute("""
            SELECT fr.id, fr.numero_factura, p.nombre_completo as proveedor,
                   fr.tipo, fr.fecha_recepcion, fr.fecha_vencimiento,
                   fr.total, fr.saldo_pendiente, fr.estado
            FROM facturas_recibidas fr
            JOIN personal p ON fr.personal_id = p.id
            WHERE fr.tipo IN ('materiales', 'otros')
            ORDER BY fr.fecha_recepcion DESC
            LIMIT 50
        """)
        facturas_prov = cursor.fetchall()

        if facturas_prov:
            for fp in facturas_prov:
                estado_icon = "🟢" if fp['estado'] == 'pagada' else "🟡" if fp['estado'] == 'pendiente' else "🔴"

                with st.expander(f"{estado_icon} {fp['numero_factura']} - {fp['proveedor']} - ${float(fp['total']):,.0f} - {fp['estado'].capitalize()}"):
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("Tipo", fp['tipo'].capitalize())
                        st.write(f"**Recepcion:** {fp['fecha_recepcion'].strftime('%d/%m/%Y')}")
                    with col2:
                        st.metric("Total", f"${float(fp['total']):,.0f}")
                    with col3:
                        st.metric("Saldo", f"${float(fp['saldo_pendiente']):,.0f}")
                    with col4:
                        if fp['fecha_vencimiento']:
                            st.metric("Vencimiento", fp['fecha_vencimiento'].strftime('%d/%m/%Y'))
                            if fp['estado'] != 'pagada':
                                dias_rest = (fp['fecha_vencimiento'] - date.today()).days
                                if dias_rest < 0:
                                    st.error(f"Vencida hace {abs(dias_rest)} dias")
                                elif dias_rest <= 7:
                                    st.warning(f"Vence en {dias_rest} dias")
                                else:
                                    st.info(f"{dias_rest} dias restantes")

                    # Cambiar estado
                    col_est1, col_est2 = st.columns([1, 3])
                    with col_est1:
                        nuevo_estado_prov = st.selectbox(
                            "Cambiar estado",
                            ['pendiente', 'pagada', 'anulada'],
                            index=['pendiente', 'pagada', 'anulada'].index(fp['estado']) if fp['estado'] in ['pendiente', 'pagada', 'anulada'] else 0,
                            key=f"estado_prov_{fp['id']}"
                        )
                    with col_est2:
                        if st.button("Actualizar", key=f"btn_prov_{fp['id']}"):
                            try:
                                cursor_u = conn.cursor()
                                saldo = 0 if nuevo_estado_prov == 'pagada' else float(fp['total'])
                                cursor_u.execute("""
                                    UPDATE facturas_recibidas SET estado = %s, saldo_pendiente = %s WHERE id = %s
                                """, (nuevo_estado_prov, saldo, fp['id']))
                                conn.commit()
                                st.success("Estado actualizado")
                                st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"Error: {e}")

            # Totales
            st.divider()
            total_prov_all = sum([float(f['total']) for f in facturas_prov])
            pendiente_prov = sum([float(f['saldo_pendiente']) for f in facturas_prov if f['estado'] != 'pagada'])

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Facturas", len(facturas_prov))
            with col2:
                st.metric("Monto Total", f"${total_prov_all:,.0f}")
            with col3:
                st.metric("Pendiente Pago", f"${pendiente_prov:,.0f}")
        else:
            st.info("No hay facturas de proveedores registradas")

    except Exception as e:
        st.error(f"Error: {e}")

with tab5:
    st.subheader("Cuentas por Pagar - Vista Consolidada")
    st.info("Vista unificada de todas las obligaciones pendientes de pago")

    try:
        cursor = conn.cursor(dictionary=True)

        cuentas = []

        # 1. Facturas de transporte pendientes
        try:
            cursor.execute("""
                SELECT ft.numero_factura, p.nombre_completo as proveedor,
                       ft.monto_total, ft.fecha_vencimiento, ft.estado
                FROM facturas_transporte ft
                JOIN personal p ON ft.courrier_id = p.id
                WHERE ft.estado = 'pendiente'
                ORDER BY ft.fecha_vencimiento
            """)
            for row in cursor.fetchall():
                cuentas.append({
                    'Concepto': f"Transporte: {row['numero_factura']} - {row['proveedor']}",
                    'Tipo': 'Transporte',
                    'Monto': float(row['monto_total']),
                    'Fecha Vencimiento': row['fecha_vencimiento'],
                    'Estado': row['estado'].capitalize()
                })
        except Exception:
            pass

        # 2. Pagos operativos mensuales pendientes (mensajeros + alistamiento)
        try:
            cursor.execute("""
                SELECT tipo, periodo_mes, periodo_anio, monto_total, fecha_vencimiento, estado
                FROM pagos_operativos_mensuales
                WHERE estado = 'pendiente'
                ORDER BY fecha_vencimiento
            """)
            meses_n = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
            for row in cursor.fetchall():
                tipo_label = "Mensajeros" if row['tipo'] == 'mensajeros' else "Alistamiento"
                periodo = f"{meses_n[row['periodo_mes']-1]} {row['periodo_anio']}"
                cuentas.append({
                    'Concepto': f"{tipo_label}: {periodo}",
                    'Tipo': 'Operativo',
                    'Monto': float(row['monto_total']),
                    'Fecha Vencimiento': row['fecha_vencimiento'],
                    'Estado': row['estado'].capitalize()
                })
        except Exception:
            pass

        # 3. Facturas recibidas (proveedores + liquidaciones personal) pendientes
        try:
            cursor.execute("""
                SELECT fr.numero_factura, p.nombre_completo as proveedor,
                       fr.tipo, fr.saldo_pendiente, fr.fecha_vencimiento, fr.estado
                FROM facturas_recibidas fr
                JOIN personal p ON fr.personal_id = p.id
                WHERE fr.estado NOT IN ('pagada', 'anulada')
                ORDER BY fr.fecha_vencimiento
            """)
            for row in cursor.fetchall():
                if row['tipo'] in ('mensajero', 'alistamiento'):
                    tipo_label = row['tipo'].capitalize()
                    cuentas.append({
                        'Concepto': f"{tipo_label}: {row['numero_factura']} - {row['proveedor']}",
                        'Tipo': tipo_label,
                        'Monto': float(row['saldo_pendiente']),
                        'Fecha Vencimiento': row['fecha_vencimiento'],
                        'Estado': row['estado'].capitalize()
                    })
                else:
                    cuentas.append({
                        'Concepto': f"Proveedor: {row['numero_factura']} - {row['proveedor']} ({row['tipo']})",
                        'Tipo': 'Proveedor',
                        'Monto': float(row['saldo_pendiente']),
                        'Fecha Vencimiento': row['fecha_vencimiento'],
                        'Estado': row['estado'].capitalize()
                    })
        except Exception:
            pass

        # 4. Nomina provisiones del mes actual
        try:
            mes_actual = date.today().month
            anio_actual = date.today().year
            cursor.execute("""
                SELECT
                    SUM(salario_base + auxilio_transporte + COALESCE(auxilio_no_salarial, 0) +
                        arl + eps + afp + caja_compensacion +
                        prima + cesantias + int_cesantias + vacaciones) as total
                FROM nomina_provisiones
                WHERE periodo_mes = %s AND periodo_anio = %s
            """, (mes_actual, anio_actual))
            result = cursor.fetchone()
            if result and result['total']:
                cuentas.append({
                    'Concepto': f"Nomina Administrativa: {date.today().strftime('%B %Y')}",
                    'Tipo': 'Nomina',
                    'Monto': float(result['total']),
                    'Fecha Vencimiento': date(anio_actual, mes_actual + 1, 1) if mes_actual < 12 else date(anio_actual + 1, 1, 1),
                    'Estado': 'Provisionado'
                })
        except Exception:
            pass

        # 5. Gastos administrativos pendientes
        try:
            cursor.execute("""
                SELECT fecha, categoria, descripcion, monto
                FROM gastos_administrativos
                WHERE estado = 'pendiente'
                ORDER BY fecha
            """)
            for row in cursor.fetchall():
                cuentas.append({
                    'Concepto': f"Gasto: {row['categoria']} - {row['descripcion']}",
                    'Tipo': 'Gasto Admin.',
                    'Monto': float(row['monto']),
                    'Fecha Vencimiento': row['fecha'],
                    'Estado': 'Pendiente'
                })
        except Exception:
            pass

        # Mostrar tabla consolidada
        if cuentas:
            df_cuentas = pd.DataFrame(cuentas)

            # Formatear fecha vencimiento
            df_cuentas['Fecha Vencimiento'] = pd.to_datetime(df_cuentas['Fecha Vencimiento']).dt.strftime('%d/%m/%Y')

            # Calcular dias restantes para ordenar
            df_display = df_cuentas.copy()
            df_display['Monto'] = df_display['Monto'].apply(lambda x: f"${x:,.0f}")

            st.dataframe(df_display, use_container_width=True, hide_index=True)

            st.divider()

            # Totales por categoria
            st.markdown("### Resumen por Categoria")

            totales_tipo = df_cuentas.groupby('Tipo')['Monto'].sum().reset_index()
            totales_tipo = totales_tipo.sort_values('Monto', ascending=False)

            cols = st.columns(len(totales_tipo))
            for i, (_, row) in enumerate(totales_tipo.iterrows()):
                with cols[i]:
                    st.metric(row['Tipo'], f"${row['Monto']:,.0f}")

            st.divider()

            # Total general
            total_general = df_cuentas['Monto'].sum()
            st.metric("TOTAL CUENTAS POR PAGAR", f"${total_general:,.0f}")

            st.divider()
            try:
                buf_cp = io.BytesIO()
                with pd.ExcelWriter(buf_cp, engine='openpyxl') as writer:
                    df_cuentas.to_excel(writer, index=False, sheet_name='Cuentas por Pagar')
                st.download_button("📥 Exportar a Excel", buf_cp.getvalue(), "cuentas_por_pagar.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   key="export_cuentas_pagar")
            except Exception as e:
                st.error(f"Error al exportar: {e}")

        else:
            st.success("No hay cuentas por pagar pendientes")

    except Exception as e:
        st.error(f"Error: {e}")

with tab6:
    st.subheader("👷 Pago a Personal")
    subtab_crear, subtab_pagar = st.tabs(["📋 Crear Liquidación", "💸 Pago por Transferencia"])

    with subtab_crear:
        st.markdown("### Crear Liquidación de Pago")

        try:
            cursor_t6 = conn.cursor(dictionary=True)
            cursor_t6.execute("""
                SELECT id, codigo, nombre_completo, tipo_personal
                FROM personal
                WHERE activo = TRUE
                ORDER BY nombre_completo
            """)
            personal_t6 = cursor_t6.fetchall()
            personal_options_t6 = {f"{p['nombre_completo']} ({p['codigo']})": p for p in personal_t6}
        except Exception as e:
            st.error(f"Error cargando personal: {e}")
            personal_options_t6 = {}

        col_p1, col_p2 = st.columns([3, 2])
        with col_p1:
            worker_options_list = ["👥 Todos los trabajadores"] + list(personal_options_t6.keys())
            worker_sel = st.selectbox(
                "👤 Seleccionar Trabajador",
                worker_options_list,
                key="liq_worker_sel"
            )
        with col_p2:
            tipo_liq = st.radio(
                "Tipo",
                ["🚴 Planillas Mensajero", "🏭 Alistamiento / Labores"],
                key="liq_tipo",
                horizontal=True
            )

        if worker_sel == "👥 Todos los trabajadores":
            st.divider()
            st.caption("Vista de resumen — selecciona un trabajador individual para crear liquidaciones")

            hoy_t = date.today()
            mes_ini_t = hoy_t.month - 2 if hoy_t.month > 2 else hoy_t.month + 10
            anio_ini_t = hoy_t.year if hoy_t.month > 2 else hoy_t.year - 1
            col_td1, col_td2 = st.columns([1.5, 1.5])
            with col_td1:
                fecha_desde_todos = st.date_input("Desde", value=date(anio_ini_t, mes_ini_t, 1), key="todos_desde")
            with col_td2:
                fecha_hasta_todos = st.date_input("Hasta", value=hoy_t, key="todos_hasta")

            try:
                cursor_todos = conn.cursor(dictionary=True)

                if tipo_liq == "🚴 Planillas Mensajero":
                    cursor_todos.execute("""
                        SELECT p.nombre_completo, p.codigo,
                               COUNT(DISTINCT gm.lot_esc) as planillas_pendientes,
                               SUM(gm.total_seriales)    as seriales_pendientes,
                               SUM(gm.valor_total)       as total_pendiente
                        FROM gestiones_mensajero gm
                        JOIN personal p ON CAST(gm.cod_mensajero AS UNSIGNED) = CAST(p.codigo AS UNSIGNED)
                        WHERE gm.facturado_liq IS NULL
                          AND DATE(gm.fecha_escaner) BETWEEN %s AND %s
                          AND p.activo = TRUE
                        GROUP BY p.id, p.nombre_completo, p.codigo
                        ORDER BY p.nombre_completo
                    """, (fecha_desde_todos, fecha_hasta_todos))
                    resumen_todos = cursor_todos.fetchall()

                    if not resumen_todos:
                        st.info("No hay planillas pendientes de liquidar en el período")
                    else:
                        total_general = sum(float(r['total_pendiente'] or 0) for r in resumen_todos)
                        st.caption(f"{len(resumen_todos)} mensajeros con planillas pendientes | ${total_general:,.0f} total")

                        col_rh0, col_rh1, col_rh2, col_rh3, col_rh4 = st.columns([2.5, 1, 1.5, 1.5, 1.5])
                        with col_rh0: st.markdown("**Trabajador**")
                        with col_rh1: st.markdown("**Código**")
                        with col_rh2: st.markdown("**Planillas**")
                        with col_rh3: st.markdown("**Seriales**")
                        with col_rh4: st.markdown("**Total**")

                        for r in resumen_todos:
                            c0, c1, c2, c3, c4 = st.columns([2.5, 1, 1.5, 1.5, 1.5])
                            with c0: st.write(r['nombre_completo'])
                            with c1: st.write(r['codigo'])
                            with c2: st.write(int(r['planillas_pendientes']))
                            with c3: st.write(f"{int(r['seriales_pendientes'] or 0):,}")
                            with c4: st.write(f"${float(r['total_pendiente'] or 0):,.0f}")

                else:  # Alistamiento
                    cursor_todos.execute("""
                        SELECT p.nombre_completo, p.codigo,
                               COUNT(DISTINCT combined.fecha) as fechas_pendientes,
                               SUM(combined.total)            as total_pendiente
                        FROM (
                            SELECT personal_id, fecha, SUM(total) as total
                            FROM registro_horas
                            WHERE (liquidado = 0 OR liquidado IS NULL)
                              AND fecha BETWEEN %s AND %s
                            GROUP BY personal_id, fecha
                            UNION ALL
                            SELECT personal_id, fecha, SUM(total) as total
                            FROM registro_labores
                            WHERE (liquidado = 0 OR liquidado IS NULL)
                              AND fecha BETWEEN %s AND %s
                            GROUP BY personal_id, fecha
                            UNION ALL
                            SELECT personal_id, fecha, SUM(total) as total
                            FROM subsidio_transporte
                            WHERE (liquidado = 0 OR liquidado IS NULL)
                              AND fecha BETWEEN %s AND %s
                            GROUP BY personal_id, fecha
                        ) combined
                        JOIN personal p ON p.id = combined.personal_id
                        WHERE p.activo = TRUE
                        GROUP BY p.id, p.nombre_completo, p.codigo
                        ORDER BY p.nombre_completo
                    """, (fecha_desde_todos, fecha_hasta_todos,
                          fecha_desde_todos, fecha_hasta_todos,
                          fecha_desde_todos, fecha_hasta_todos))
                    resumen_todos = cursor_todos.fetchall()

                    if not resumen_todos:
                        st.info("No hay labores pendientes de liquidar en el período")
                    else:
                        total_general = sum(float(r['total_pendiente'] or 0) for r in resumen_todos)
                        st.caption(f"{len(resumen_todos)} trabajadores con labores pendientes | ${total_general:,.0f} total")

                        col_rh0, col_rh1, col_rh2, col_rh3 = st.columns([3, 1, 1.5, 1.5])
                        with col_rh0: st.markdown("**Trabajador**")
                        with col_rh1: st.markdown("**Código**")
                        with col_rh2: st.markdown("**Fechas**")
                        with col_rh3: st.markdown("**Total**")

                        for r in resumen_todos:
                            c0, c1, c2, c3 = st.columns([3, 1, 1.5, 1.5])
                            with c0: st.write(r['nombre_completo'])
                            with c1: st.write(r['codigo'])
                            with c2: st.write(int(r['fechas_pendientes']))
                            with c3: st.write(f"${float(r['total_pendiente'] or 0):,.0f}")

                cursor_todos.close()
            except Exception as e:
                st.error(f"Error: {e}")

        elif worker_sel and personal_options_t6:
            worker_t6 = personal_options_t6[worker_sel]
            worker_codigo = worker_t6['codigo']
            worker_id = worker_t6['id']

            st.divider()

            if tipo_liq == "🚴 Planillas Mensajero":
                try:
                    # Filtros de fecha y estado
                    col_f1, col_f2, col_f3 = st.columns([1.5, 1.5, 2])
                    with col_f1:
                        hoy = date.today()
                        # Por defecto: primer día de hace 2 meses
                        mes_ini = hoy.month - 2 if hoy.month > 2 else hoy.month + 10
                        anio_ini = hoy.year if hoy.month > 2 else hoy.year - 1
                        fecha_desde_mens = st.date_input(
                            "Desde", value=date(anio_ini, mes_ini, 1), key="mens_desde"
                        )
                    with col_f2:
                        fecha_hasta_mens = st.date_input(
                            "Hasta", value=hoy, key="mens_hasta"
                        )
                    with col_f3:
                        mostrar_mens = st.radio(
                            "Mostrar",
                            ["🟢 Pendientes", "📋 Todas"],
                            key="mens_mostrar",
                            horizontal=True
                        )

                    solo_pendientes = (mostrar_mens == "🟢 Pendientes")
                    # Filtro en HAVING (no WHERE) para no partir lot_esc con mezcla de estados
                    cond_having = "HAVING MAX(facturado_liq) IS NULL" if solo_pendientes else ""

                    # DATE() igual que Planilla Check — maneja 'YYYY.MM.DD' y otros formatos
                    # CAST numérico maneja códigos con/sin cero inicial ('0519' = '519')
                    cursor_t6.execute(f"""
                        SELECT lot_esc,
                               MIN(fecha_escaner) as fecha_escaner,
                               SUM(total_seriales) as total_seriales,
                               AVG(valor_unitario) as valor_unitario,
                               SUM(valor_total) as valor_total,
                               MAX(cliente) as cliente,
                               MAX(facturado_liq) as facturado_liq
                        FROM gestiones_mensajero
                        WHERE CAST(cod_mensajero AS UNSIGNED) = CAST(%s AS UNSIGNED)
                          AND DATE(fecha_escaner) BETWEEN %s AND %s
                        GROUP BY lot_esc
                        {cond_having}
                        ORDER BY DATE(MIN(fecha_escaner)) DESC
                    """, (worker_codigo, fecha_desde_mens, fecha_hasta_mens))
                    planillas = cursor_t6.fetchall()

                    # Totales del período completo (para comparar con Planilla Check)
                    cursor_t6.execute("""
                        SELECT COUNT(DISTINCT lot_esc) as total_planillas,
                               SUM(total_seriales) as total_seriales,
                               SUM(valor_total) as total_valor
                        FROM gestiones_mensajero
                        WHERE CAST(cod_mensajero AS UNSIGNED) = CAST(%s AS UNSIGNED)
                          AND DATE(fecha_escaner) BETWEEN %s AND %s
                    """, (worker_codigo, fecha_desde_mens, fecha_hasta_mens))
                    resumen_periodo = cursor_t6.fetchone() or {}

                    if not planillas:
                        total_plan_periodo = int(resumen_periodo.get('total_planillas') or 0)
                        total_ser_periodo = int(resumen_periodo.get('total_seriales') or 0)
                        if total_plan_periodo > 0:
                            st.info(f"No hay planillas pendientes — el período tiene {total_plan_periodo} planillas ({total_ser_periodo:,} seriales) ya liquidadas")
                        else:
                            st.info("No hay planillas para el período seleccionado")
                    else:
                        pendientes_lista = [p for p in planillas if p.get('facturado_liq') is None]
                        total_periodo = sum(float(p['valor_total'] or 0) for p in planillas)
                        total_ser_shown = sum(int(p['total_seriales'] or 0) for p in planillas)
                        total_plan_periodo = int(resumen_periodo.get('total_planillas') or 0)
                        total_ser_periodo = int(resumen_periodo.get('total_seriales') or 0)
                        if solo_pendientes and total_plan_periodo > len(planillas):
                            st.caption(
                                f"**{len(planillas)} pendientes** ({total_ser_shown:,} seriales · ${total_periodo:,.0f}) "
                                f"· Período completo: {total_plan_periodo} planillas | {total_ser_periodo:,} seriales"
                            )
                        else:
                            st.caption(f"{len(planillas)} planillas | {total_ser_shown:,} seriales | ${total_periodo:,.0f}")

                        col_sel1, col_sel2, _ = st.columns([1.2, 1.2, 4])
                        with col_sel1:
                            if st.button("☑️ Seleccionar todas", key="btn_sel_todas_mens"):
                                for p in pendientes_lista:
                                    st.session_state[f"liq_pl_{p['lot_esc']}"] = True
                                st.rerun()
                        with col_sel2:
                            if st.button("⬜ Deseleccionar", key="btn_desel_mens"):
                                for p in pendientes_lista:
                                    st.session_state[f"liq_pl_{p['lot_esc']}"] = False
                                st.rerun()

                        col_h0, col_h1, col_h2, col_h3, col_h4, col_h5, col_h6 = st.columns([0.5, 2, 1.5, 2, 1, 1.5, 1.5])
                        with col_h0: st.markdown("**✓**")
                        with col_h1: st.markdown("**Planilla**")
                        with col_h2: st.markdown("**Fecha**")
                        with col_h3: st.markdown("**Cliente**")
                        with col_h4: st.markdown("**Seriales**")
                        with col_h5: st.markdown("**Val. Unit.**")
                        with col_h6: st.markdown("**Total**")

                        total_sel_mens = 0.0
                        planillas_sel = []

                        for pl in planillas:
                            ya_liquidada = pl.get('facturado_liq') is not None
                            chk = False
                            c0, c1, c2, c3, c4, c5, c6 = st.columns([0.5, 2, 1.5, 2, 1, 1.5, 1.5])
                            with c0:
                                if ya_liquidada:
                                    if st.button("↩", key=f"unliq_pl_{pl['lot_esc']}", help="Desliquidar planilla"):
                                        try:
                                            cw_ul = conn.cursor()
                                            cw_ul.execute(
                                                "UPDATE gestiones_mensajero SET facturado_liq = NULL "
                                                "WHERE lot_esc = %s AND CAST(cod_mensajero AS UNSIGNED) = CAST(%s AS UNSIGNED)",
                                                (pl['lot_esc'], worker_codigo)
                                            )
                                            conn.commit()
                                            cw_ul.close()
                                            st.rerun()
                                        except Exception as e:
                                            conn.rollback()
                                            st.error(f"Error: {e}")
                                else:
                                    chk = st.checkbox(
                                        "s", key=f"liq_pl_{pl['lot_esc']}",
                                        label_visibility="collapsed"
                                    )
                            with c1:
                                lbl = f"~~{pl['lot_esc']}~~ 💳" if ya_liquidada else pl['lot_esc']
                                st.write(lbl)
                            with c2:
                                _fe = str(pl['fecha_escaner'] or '')
                                try:
                                    _fe_disp = pd.to_datetime(_fe.replace('.', '-')).strftime('%d/%m/%Y')
                                except Exception:
                                    _fe_disp = _fe or '-'
                                st.write(_fe_disp)
                            with c3:
                                st.write(pl['cliente'] or '-')
                            with c4:
                                st.write(f"{int(pl['total_seriales'] or 0):,}")
                            with c5:
                                st.write(f"${float(pl['valor_unitario'] or 0):,.0f}")
                            with c6:
                                st.write(f"${float(pl['valor_total'] or 0):,.0f}")
                            if chk:
                                planillas_sel.append(pl['lot_esc'])
                                total_sel_mens += float(pl['valor_total'] or 0)

                        if planillas_sel:
                            st.divider()
                            st.success(f"✅ {len(planillas_sel)} planillas | Total: ${total_sel_mens:,.0f}")

                            if not solo_pendientes:
                                st.info("Cambia a **🟢 Pendientes** para crear la liquidación.")
                            if solo_pendientes:
                                col_m1, col_f1 = st.columns(2)
                                with col_m1:
                                    _mk_mens = f"liq_monto_mens_{len(planillas_sel)}_{int(total_sel_mens)}"
                                    monto_mens = st.number_input(
                                        "Monto Acordado *",
                                        min_value=0.0,
                                        value=float(total_sel_mens),
                                        step=1000.0,
                                        format="%.0f",
                                        key=_mk_mens
                                    )
                                with col_f1:
                                    fecha_liq_mens = st.date_input("Fecha Liquidación", value=date.today(), key="liq_fecha_mens")

                                obs_mens = st.text_input("Observaciones (opcional)", key="liq_obs_mens")

                                if st.button("💾 Crear Liquidación", type="primary", key="btn_liq_mens"):
                                    try:
                                        cw = conn.cursor(dictionary=True)
                                        fecha_str = fecha_liq_mens.strftime('%Y%m%d')
                                        prefix_liq = f"LIQ-{worker_codigo}-{fecha_str}"
                                        cw.execute(
                                            "SELECT COUNT(*) as cnt FROM facturas_recibidas WHERE numero_factura LIKE %s",
                                            (f"{prefix_liq}%",)
                                        )
                                        seq = cw.fetchone()['cnt']
                                        num_liq = f"{prefix_liq}-{seq + 1}"

                                        cw.execute("""
                                            INSERT INTO facturas_recibidas
                                            (numero_factura, personal_id, tipo, fecha_recepcion, fecha_vencimiento,
                                             subtotal, total, saldo_pendiente, estado, observaciones)
                                            VALUES (%s, %s, 'mensajero', %s, %s, %s, %s, %s, 'pendiente', %s)
                                        """, (num_liq, worker_id, fecha_liq_mens, fecha_liq_mens,
                                              monto_mens, monto_mens, monto_mens,
                                              obs_mens or f"Planillas: {', '.join(str(p) for p in planillas_sel)}"))

                                        factura_id_nuevo = cw.lastrowid
                                        for lot in planillas_sel:
                                            cw.execute(
                                                "UPDATE gestiones_mensajero SET facturado_liq = %s "
                                                "WHERE lot_esc = %s AND CAST(cod_mensajero AS UNSIGNED) = CAST(%s AS UNSIGNED)",
                                                (factura_id_nuevo, lot, worker_codigo)
                                            )
                                        conn.commit()
                                        cw.close()
                                        st.success(f"✅ Liquidación **{num_liq}** creada por ${monto_mens:,.0f}")
                                        st.rerun()
                                    except Exception as e:
                                        conn.rollback()
                                        st.error(f"Error: {e}")

                except Exception as e:
                    st.error(f"Error consultando planillas: {e}")

            else:  # Alistamiento / Labores — agrupado por fecha (registro_horas + registro_labores + subsidio_transporte)
                try:
                    # Filtros de fecha y estado
                    hoy_al = date.today()
                    mes_ini_al = hoy_al.month - 2 if hoy_al.month > 2 else hoy_al.month + 10
                    anio_ini_al = hoy_al.year if hoy_al.month > 2 else hoy_al.year - 1
                    col_fa1, col_fa2, col_fa3 = st.columns([1.5, 1.5, 2])
                    with col_fa1:
                        fecha_desde_al = st.date_input(
                            "Desde", value=date(anio_ini_al, mes_ini_al, 1), key="al_desde"
                        )
                    with col_fa2:
                        fecha_hasta_al = st.date_input(
                            "Hasta", value=hoy_al, key="al_hasta"
                        )
                    with col_fa3:
                        mostrar_al = st.radio(
                            "Mostrar",
                            ["🟢 Pendientes", "📋 Todas"],
                            key="al_mostrar",
                            horizontal=True
                        )
                    solo_pend_al = (mostrar_al == "🟢 Pendientes")
                    cond_liq_rh = "AND (rh.liquidado = 0 OR rh.liquidado IS NULL)" if solo_pend_al else ""
                    cond_liq_rl = "AND (rl.liquidado = 0 OR rl.liquidado IS NULL)" if solo_pend_al else ""
                    cond_liq_st = "AND (st.liquidado = 0 OR st.liquidado IS NULL)" if solo_pend_al else ""

                    cursor_t6.execute(f"""
                        SELECT fecha,
                               SUM(num_registros) as num_registros,
                               SUM(total_dia)     as total_dia,
                               GROUP_CONCAT(DISTINCT ordenes ORDER BY ordenes SEPARATOR ', ') as ordenes,
                               MAX(liquidado) as liquidado
                        FROM (
                            SELECT rh.fecha,
                                   COUNT(*) as num_registros,
                                   SUM(rh.total) as total_dia,
                                   GROUP_CONCAT(DISTINCT COALESCE(o.numero_orden,'Sin orden') SEPARATOR ', ') as ordenes,
                                   MAX(COALESCE(rh.liquidado, 0)) as liquidado
                            FROM registro_horas rh
                            LEFT JOIN ordenes o ON rh.orden_id = o.id
                            WHERE rh.personal_id = %s
                              AND rh.fecha BETWEEN %s AND %s
                              {cond_liq_rh}
                            GROUP BY rh.fecha

                            UNION ALL

                            SELECT rl.fecha,
                                   COUNT(*) as num_registros,
                                   SUM(rl.total) as total_dia,
                                   GROUP_CONCAT(DISTINCT COALESCE(o.numero_orden,'Sin orden') SEPARATOR ', ') as ordenes,
                                   MAX(COALESCE(rl.liquidado, 0)) as liquidado
                            FROM registro_labores rl
                            LEFT JOIN ordenes o ON rl.orden_id = o.id
                            WHERE rl.personal_id = %s
                              AND rl.fecha BETWEEN %s AND %s
                              {cond_liq_rl}
                            GROUP BY rl.fecha

                            UNION ALL

                            SELECT st.fecha,
                                   COUNT(*) as num_registros,
                                   SUM(st.total) as total_dia,
                                   NULL as ordenes,
                                   MAX(COALESCE(st.liquidado, 0)) as liquidado
                            FROM subsidio_transporte st
                            WHERE st.personal_id = %s
                              AND st.fecha BETWEEN %s AND %s
                              {cond_liq_st}
                            GROUP BY st.fecha
                        ) combined
                        GROUP BY fecha
                        ORDER BY fecha DESC
                    """, (worker_id, fecha_desde_al, fecha_hasta_al,
                          worker_id, fecha_desde_al, fecha_hasta_al,
                          worker_id, fecha_desde_al, fecha_hasta_al))
                    fechas_lab = cursor_t6.fetchall()

                    if not fechas_lab:
                        st.info(f"No hay labores {'pendientes ' if solo_pend_al else ''}en el período para {worker_t6['nombre_completo']}")
                    else:
                        pendientes_al = [f for f in fechas_lab if not f.get('liquidado')]
                        liquidadas_al = [f for f in fechas_lab if f.get('liquidado')]
                        total_periodo_al = sum(float(f['total_dia'] or 0) for f in fechas_lab)
                        if solo_pend_al:
                            st.caption(f"{len(fechas_lab)} fechas pendientes | ${total_periodo_al:,.0f}")
                        else:
                            st.caption(
                                f"{len(pendientes_al)} pendientes · {len(liquidadas_al)} liquidadas "
                                f"| ${total_periodo_al:,.0f} total"
                            )

                        col_sal1, col_sal2, _ = st.columns([1.2, 1.2, 4])
                        with col_sal1:
                            if st.button("☑️ Seleccionar todas", key="btn_sel_todas_al"):
                                for fb in pendientes_al:
                                    st.session_state[f"liq_al_{str(fb['fecha'])}"] = True
                                st.rerun()
                        with col_sal2:
                            if st.button("⬜ Deseleccionar", key="btn_desel_al"):
                                for fb in pendientes_al:
                                    st.session_state[f"liq_al_{str(fb['fecha'])}"] = False
                                st.rerun()

                        col_h0, col_h1, col_h2, col_h3, col_h4 = st.columns([0.5, 1.5, 1, 4, 1.5])
                        with col_h0: st.markdown("**✓**")
                        with col_h1: st.markdown("**Fecha**")
                        with col_h2: st.markdown("**Registros**")
                        with col_h3: st.markdown("**Órdenes**")
                        with col_h4: st.markdown("**Total**")

                        total_sel_al = 0.0
                        fechas_sel = []

                        for fb in fechas_lab:
                            ya_liq_al = bool(fb.get('liquidado'))
                            fecha_key = str(fb['fecha'])
                            c0, c1, c2, c3, c4 = st.columns([0.5, 1.5, 1, 4, 1.5])
                            with c0:
                                if ya_liq_al:
                                    if st.button("↩", key=f"unliq_al2_{fecha_key}", help="Desliquidar fecha"):
                                        try:
                                            cw_ul3 = conn.cursor()
                                            for _tbl in ('registro_horas', 'registro_labores', 'subsidio_transporte'):
                                                cw_ul3.execute(
                                                    f"UPDATE {_tbl} SET liquidado = 0 "
                                                    f"WHERE personal_id = %s AND fecha = %s",
                                                    (worker_id, fb['fecha'])
                                                )
                                            conn.commit()
                                            cw_ul3.close()
                                            st.rerun()
                                        except Exception as e:
                                            conn.rollback()
                                            st.error(f"Error: {e}")
                                else:
                                    chk = st.checkbox("s", key=f"liq_al_{fecha_key}", label_visibility="collapsed")
                            with c1:
                                lbl_f = pd.to_datetime(fb['fecha']).strftime('%d/%m/%Y') if fb['fecha'] else '-'
                                st.write(f"~~{lbl_f}~~ 💳" if ya_liq_al else lbl_f)
                            with c2:
                                st.write(int(fb['num_registros']))
                            with c3:
                                st.write(fb['ordenes'] or '-')
                            with c4:
                                st.write(f"${float(fb['total_dia'] or 0):,.0f}")
                            if not ya_liq_al and chk:
                                fechas_sel.append(fb['fecha'])
                                total_sel_al += float(fb['total_dia'] or 0)

                        if fechas_sel:
                            st.divider()
                            st.success(f"✅ {len(fechas_sel)} fechas seleccionadas | Total: ${total_sel_al:,.0f}")

                            if not solo_pend_al:
                                st.info("Cambia a **🟢 Pendientes** para crear la liquidación.")
                            if solo_pend_al:
                                col_m2, col_f2 = st.columns(2)
                                with col_m2:
                                    _mk_al = f"liq_monto_al_{len(fechas_sel)}_{int(total_sel_al)}"
                                    monto_al = st.number_input(
                                        "Monto Acordado *",
                                        min_value=0.0,
                                        value=float(total_sel_al),
                                        step=1000.0,
                                        format="%.0f",
                                        key=_mk_al
                                    )
                                with col_f2:
                                    fecha_liq_al = st.date_input("Fecha Liquidación", value=date.today(), key="liq_fecha_al")

                                obs_al = st.text_input("Observaciones (opcional)", key="liq_obs_al")

                                if st.button("💾 Crear Liquidación", type="primary", key="btn_liq_al"):
                                    try:
                                        cw = conn.cursor(dictionary=True)
                                        fecha_str = pd.to_datetime(fecha_liq_al).strftime('%Y%m%d')
                                        prefix_liq = f"LIQ-{worker_codigo}-{fecha_str}"
                                        cw.execute(
                                            "SELECT COUNT(*) as cnt FROM facturas_recibidas WHERE numero_factura LIKE %s",
                                            (f"{prefix_liq}%",)
                                        )
                                        seq = cw.fetchone()['cnt']
                                        num_liq = f"{prefix_liq}-{seq + 1}"

                                        fechas_txt = ', '.join(
                                            pd.to_datetime(f).strftime('%d/%m/%Y') for f in fechas_sel
                                        )
                                        cw.execute("""
                                            INSERT INTO facturas_recibidas
                                            (numero_factura, personal_id, tipo, fecha_recepcion, fecha_vencimiento,
                                             subtotal, total, saldo_pendiente, estado, observaciones)
                                            VALUES (%s, %s, 'alistamiento', %s, %s, %s, %s, %s, 'pendiente', %s)
                                        """, (num_liq, worker_id, fecha_liq_al, fecha_liq_al,
                                              monto_al, monto_al, monto_al,
                                              obs_al or f"Fechas: {fechas_txt}"))

                                        ph = ', '.join(['%s'] * len(fechas_sel))
                                        params_upd = [worker_id] + list(fechas_sel)
                                        for _tbl in ('registro_horas', 'registro_labores', 'subsidio_transporte'):
                                            cw.execute(
                                                f"UPDATE {_tbl} SET liquidado = 1 "
                                                f"WHERE personal_id = %s AND fecha IN ({ph})",
                                                params_upd
                                            )
                                        conn.commit()
                                        cw.close()
                                        st.success(f"✅ Liquidación **{num_liq}** creada por ${monto_al:,.0f}")
                                        st.rerun()
                                    except Exception as e:
                                        conn.rollback()
                                        st.error(f"Error: {e}")

                    # Fechas ya liquidadas — permite desliquidar
                    with st.expander("↩ Desliquidar fechas ya liquidadas"):
                        try:
                            cursor_t6.execute("""
                                SELECT fecha,
                                       SUM(num_registros) as num_registros,
                                       SUM(total_dia)     as total_dia
                                FROM (
                                    SELECT rh.fecha, COUNT(*) as num_registros, SUM(rh.total) as total_dia
                                    FROM registro_horas rh
                                    WHERE rh.personal_id = %s AND rh.fecha BETWEEN %s AND %s AND rh.liquidado = 1
                                    GROUP BY rh.fecha
                                    UNION ALL
                                    SELECT rl.fecha, COUNT(*) as num_registros, SUM(rl.total) as total_dia
                                    FROM registro_labores rl
                                    WHERE rl.personal_id = %s AND rl.fecha BETWEEN %s AND %s AND rl.liquidado = 1
                                    GROUP BY rl.fecha
                                    UNION ALL
                                    SELECT st2.fecha, COUNT(*) as num_registros, SUM(st2.total) as total_dia
                                    FROM subsidio_transporte st2
                                    WHERE st2.personal_id = %s AND st2.fecha BETWEEN %s AND %s AND st2.liquidado = 1
                                    GROUP BY st2.fecha
                                ) combined
                                GROUP BY fecha
                                ORDER BY fecha DESC
                            """, (worker_id, fecha_desde_al, fecha_hasta_al,
                                  worker_id, fecha_desde_al, fecha_hasta_al,
                                  worker_id, fecha_desde_al, fecha_hasta_al))
                            fechas_liq = cursor_t6.fetchall()
                            if not fechas_liq:
                                st.info("No hay fechas liquidadas en el período seleccionado")
                            else:
                                st.caption(f"{len(fechas_liq)} fechas liquidadas en el período")
                                col_lh1, col_lh2, col_lh3, col_lh4 = st.columns([1.5, 1, 1.5, 0.8])
                                with col_lh1: st.markdown("**Fecha**")
                                with col_lh2: st.markdown("**Registros**")
                                with col_lh3: st.markdown("**Total**")
                                with col_lh4: st.markdown("**↩**")
                                for flq in fechas_liq:
                                    col_ul1, col_ul2, col_ul3, col_ul4 = st.columns([1.5, 1, 1.5, 0.8])
                                    with col_ul1:
                                        st.write(pd.to_datetime(flq['fecha']).strftime('%d/%m/%Y') if flq['fecha'] else '-')
                                    with col_ul2:
                                        st.write(int(flq['num_registros']))
                                    with col_ul3:
                                        st.write(f"${float(flq['total_dia'] or 0):,.0f}")
                                    with col_ul4:
                                        if st.button("↩", key=f"unliq_al_{flq['fecha']}", help="Desliquidar fecha"):
                                            try:
                                                cw_ul2 = conn.cursor()
                                                for _tbl in ('registro_horas', 'registro_labores', 'subsidio_transporte'):
                                                    cw_ul2.execute(
                                                        f"UPDATE {_tbl} SET liquidado = 0 "
                                                        f"WHERE personal_id = %s AND fecha = %s",
                                                        (worker_id, flq['fecha'])
                                                    )
                                                conn.commit()
                                                cw_ul2.close()
                                                st.rerun()
                                            except Exception as e:
                                                conn.rollback()
                                                st.error(f"Error: {e}")
                        except Exception as e:
                            st.error(f"Error cargando fechas liquidadas: {e}")

                except Exception as e:
                    st.error(f"Error consultando labores: {e}")

    with subtab_pagar:
        st.markdown("### 💸 Pago por Transferencia Masiva")
        st.caption("Seleccione liquidaciones pendientes y registre la transferencia bancaria")

        if 'editing_liq_id' not in st.session_state:
            st.session_state.editing_liq_id = None

        filtro_pago_estado = st.radio(
            "Ver",
            ["⏳ Pendientes", "✅ Pagadas"],
            horizontal=True,
            key="filtro_pago_estado"
        )
        mostrar_pagadas = (filtro_pago_estado == "✅ Pagadas")

        try:
            cursor_t6b = conn.cursor(dictionary=True)
            if mostrar_pagadas:
                estado_cond = "fr.estado = 'pagada'"
            else:
                estado_cond = "fr.estado NOT IN ('pagada', 'anulada')"
            cursor_t6b.execute(f"""
                SELECT fr.id, fr.numero_factura, p.nombre_completo as nombre,
                       p.codigo, fr.personal_id, fr.tipo, fr.saldo_pendiente, fr.total,
                       fr.fecha_recepcion, fr.observaciones
                FROM facturas_recibidas fr
                JOIN personal p ON fr.personal_id = p.id
                WHERE fr.tipo IN ('mensajero', 'alistamiento')
                  AND {estado_cond}
                ORDER BY p.nombre_completo ASC, fr.fecha_recepcion DESC
            """)
            liquidaciones = cursor_t6b.fetchall()

            if not liquidaciones:
                st.info("No hay liquidaciones pendientes de pago")
            else:
                col_cap, col_exp = st.columns([4, 1])
                with col_cap:
                    st.caption(f"{len(liquidaciones)} liquidaciones pendientes")
                with col_exp:
                    try:
                        df_exp = pd.DataFrame([{
                            'Liquidacion': lq['numero_factura'],
                            'Trabajador': lq['nombre'],
                            'Codigo': lq['codigo'],
                            'Tipo': lq['tipo'].capitalize(),
                            'Fecha': pd.to_datetime(lq['fecha_recepcion']).strftime('%d/%m/%Y') if lq['fecha_recepcion'] else '',
                            'Monto': float(lq['saldo_pendiente'] or 0),
                            'Observaciones': lq['observaciones'] or '',
                        } for lq in liquidaciones])
                        buf_liq = io.BytesIO()
                        with pd.ExcelWriter(buf_liq, engine='openpyxl') as writer:
                            df_exp.to_excel(writer, index=False, sheet_name='Liquidaciones')
                        st.download_button("📥 Exportar Excel", buf_liq.getvalue(), "liquidaciones_pendientes.xlsx",
                                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                           key="export_liq_pago")
                    except Exception as e:
                        st.error(f"Error al exportar: {e}")

                if not mostrar_pagadas:
                    col_ps1, col_ps2, _ = st.columns([1.2, 1.2, 4])
                    with col_ps1:
                        if st.button("☑️ Seleccionar todas", key="btn_sel_todas_pago"):
                            for lq in liquidaciones:
                                st.session_state[f"pago_liq_{lq['id']}"] = True
                            st.rerun()
                    with col_ps2:
                        if st.button("⬜ Deseleccionar", key="btn_desel_pago"):
                            for lq in liquidaciones:
                                st.session_state[f"pago_liq_{lq['id']}"] = False
                            st.rerun()

                col_h0, col_h1, col_h2, col_h3, col_h4, col_h5, col_h6 = st.columns([0.5, 2.5, 2.5, 1.5, 1.5, 1.8, 1.2])
                with col_h0: st.markdown("**✓**" if not mostrar_pagadas else "")
                with col_h1: st.markdown("**Liquidación**")
                with col_h2: st.markdown("**Trabajador**")
                with col_h3: st.markdown("**Tipo**")
                with col_h4: st.markdown("**Fecha**")
                with col_h5: st.markdown("**Monto**")
                with col_h6: st.markdown("**Ajuste**" if not mostrar_pagadas else "**Desliquidar**")

                total_transf = 0.0
                liq_sel = []
                obs_por_id = {lq['id']: lq['observaciones'] or '' for lq in liquidaciones}

                for liq in liquidaciones:
                    is_editing = (st.session_state.editing_liq_id == liq['id'])
                    chk = False
                    c0, c1, c2, c3, c4, c5, c6 = st.columns([0.5, 2.5, 2.5, 1.5, 1.5, 1.8, 1.2])
                    with c0:
                        if not mostrar_pagadas:
                            chk = st.checkbox("s", key=f"pago_liq_{liq['id']}",
                                              label_visibility="collapsed", disabled=is_editing)
                    with c1:
                        st.write(liq['numero_factura'])
                    with c2:
                        st.write(liq['nombre'])
                    with c3:
                        st.write(liq['tipo'].capitalize())
                    with c4:
                        st.write(pd.to_datetime(liq['fecha_recepcion']).strftime('%d/%m/%Y') if liq['fecha_recepcion'] else '-')
                    with c5:
                        if not mostrar_pagadas and is_editing:
                            nuevo_monto = st.number_input(
                                "monto", min_value=0.0,
                                value=float(liq['saldo_pendiente'] or 0),
                                step=1000.0, format="%.0f",
                                key=f"edit_monto_{liq['id']}",
                                label_visibility="collapsed"
                            )
                        else:
                            monto_disp = liq['total'] if mostrar_pagadas else liq['saldo_pendiente']
                            st.write(f"${float(monto_disp or 0):,.0f}")
                    with c6:
                        if mostrar_pagadas:
                            if st.button("↩ Desliquidar", key=f"undo_liq_{liq['id']}"):
                                try:
                                    cw_u = conn.cursor()
                                    # Revertir facturas_recibidas
                                    cw_u.execute(
                                        "UPDATE facturas_recibidas "
                                        "SET estado = 'pendiente', saldo_pendiente = total WHERE id = %s",
                                        (liq['id'],)
                                    )
                                    # Para mensajero: limpiar facturado_liq en gestiones_mensajero
                                    if liq['tipo'] == 'mensajero':
                                        cw_u.execute(
                                            "UPDATE gestiones_mensajero SET facturado_liq = NULL "
                                            "WHERE facturado_liq = %s",
                                            (liq['id'],)
                                        )
                                    # Para alistamiento: revertir liquidado en registros del trabajador
                                    elif liq['tipo'] == 'alistamiento':
                                        for _tbl in ('registro_horas', 'registro_labores', 'subsidio_transporte'):
                                            cw_u.execute(
                                                f"UPDATE {_tbl} SET liquidado = 0 "
                                                f"WHERE personal_id = %s AND liquidado = 1",
                                                (liq['personal_id'],)
                                            )
                                    conn.commit()
                                    cw_u.close()
                                    st.rerun()
                                except Exception as e:
                                    conn.rollback()
                                    st.error(f"Error: {e}")
                        elif is_editing:
                            cs, cc = st.columns(2)
                            with cs:
                                if st.button("💾", key=f"save_monto_{liq['id']}", help="Guardar"):
                                    try:
                                        cw_e = conn.cursor()
                                        cw_e.execute(
                                            "UPDATE facturas_recibidas "
                                            "SET total = %s, subtotal = %s, saldo_pendiente = %s WHERE id = %s",
                                            (nuevo_monto, nuevo_monto, nuevo_monto, liq['id'])
                                        )
                                        conn.commit()
                                        cw_e.close()
                                        st.session_state.editing_liq_id = None
                                        st.rerun()
                                    except Exception as e:
                                        conn.rollback()
                                        st.error(f"Error: {e}")
                            with cc:
                                if st.button("✗", key=f"cancel_monto_{liq['id']}", help="Cancelar"):
                                    st.session_state.editing_liq_id = None
                                    st.rerun()
                        else:
                            if st.button("✏️", key=f"edit_btn_{liq['id']}", help="Ajustar monto"):
                                st.session_state.editing_liq_id = liq['id']
                                st.rerun()
                    if chk and not is_editing:
                        liq_sel.append(liq['id'])
                        total_transf += float(liq['saldo_pendiente'] or 0)

                if not mostrar_pagadas and liq_sel:
                    st.divider()
                    st.success(f"✅ {len(liq_sel)} liquidaciones seleccionadas | Total: ${total_transf:,.0f}")

                    # --- Desliquidar seleccionadas ---
                    if st.button("🗑️ Desliquidar seleccionadas", key="btn_desliq_sel"):
                        try:
                            cw_dl = conn.cursor(dictionary=True)
                            for liq_id in liq_sel:
                                # Obtener tipo y personal_id
                                cw_dl.execute(
                                    "SELECT tipo, personal_id FROM facturas_recibidas WHERE id = %s",
                                    (liq_id,)
                                )
                                row = cw_dl.fetchone()
                                if not row:
                                    continue
                                if row['tipo'] == 'mensajero':
                                    cw_dl.execute(
                                        "UPDATE gestiones_mensajero SET facturado_liq = NULL "
                                        "WHERE facturado_liq = %s",
                                        (liq_id,)
                                    )
                                elif row['tipo'] == 'alistamiento':
                                    for _tbl in ('registro_horas', 'registro_labores', 'subsidio_transporte'):
                                        cw_dl.execute(
                                            f"UPDATE {_tbl} SET liquidado = 0 "
                                            f"WHERE personal_id = %s AND liquidado = 1",
                                            (row['personal_id'],)
                                        )
                                cw_dl.execute(
                                    "DELETE FROM facturas_recibidas WHERE id = %s", (liq_id,)
                                )
                            conn.commit()
                            cw_dl.close()
                            st.success(f"✅ {len(liq_sel)} liquidaciones eliminadas")
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error: {e}")

                    st.divider()

                    col_t1, col_t2 = st.columns(2)
                    with col_t1:
                        num_transf = st.text_input("Número de Transferencia *", key="pago_num_transf")
                    with col_t2:
                        fecha_transf = st.date_input("Fecha de Transferencia *", value=date.today(), key="pago_fecha_transf")

                    obs_transf_extra = st.text_input("Observaciones adicionales (opcional)", key="pago_obs_transf")

                    if st.button("✅ Registrar Pago", type="primary", key="btn_pago_transf"):
                        if not num_transf:
                            st.error("Ingrese el número de transferencia")
                        else:
                            try:
                                cw2 = conn.cursor()
                                ref = f"Transf: {num_transf} ({fecha_transf.strftime('%d/%m/%Y')})"
                                if obs_transf_extra:
                                    ref += f" - {obs_transf_extra}"

                                for liq_id in liq_sel:
                                    obs_prev = obs_por_id.get(liq_id, '')
                                    nueva_obs = f"{obs_prev} | {ref}".strip(' |') if obs_prev else ref
                                    cw2.execute("""
                                        UPDATE facturas_recibidas
                                        SET estado = 'pagada', saldo_pendiente = 0, observaciones = %s
                                        WHERE id = %s
                                    """, (nueva_obs, liq_id))

                                conn.commit()
                                cw2.close()
                                st.success(f"✅ {len(liq_sel)} liquidaciones marcadas como pagadas | Transf: {num_transf}")
                                st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"Error: {e}")

        except Exception as e:
            st.error(f"Error: {e}")

with tab7:
    st.subheader("💼 Adelantos Dueño — Facturas Pagadas por el Propietario")
    st.info(
        "Registra aquí las facturas que pagaste de tu bolsillo a nombre de la empresa. "
        "Quedan clasificadas como **Gasto Administrativo** y aparecen en Cuentas por Pagar."
    )

    try:
        cursor_t7 = conn.cursor(dictionary=True)

        # ── Formulario de ingreso ──────────────────────────────────────────────
        st.markdown("### ➕ Registrar Factura Pagada")

        with st.form("form_adelanto_dueno", clear_on_submit=True):
            col_a, col_b = st.columns(2)

            with col_a:
                ad_fecha      = st.date_input("Fecha de la factura *", value=date.today(), key="ad_fecha")
                ad_empresa    = st.text_input("Empresa / Proveedor *", key="ad_empresa",
                                              placeholder="Ej: Claro, Seguros Bolívar, Almacén XYZ")
                ad_num_fac    = st.text_input("Número de factura", key="ad_num_fac",
                                              placeholder="Ej: FE-2025-001")

            with col_b:
                ad_motivo     = st.text_area("Motivo / Descripción *", key="ad_motivo",
                                             placeholder="Ej: Pago internet mes de marzo",
                                             height=100)
                ad_monto      = st.number_input("Monto pagado *", min_value=0.0,
                                                step=1000.0, format="%.0f", key="ad_monto")

            ad_submit = st.form_submit_button("💾 Registrar adelanto", type="primary")

            if ad_submit:
                errores = []
                if not ad_empresa.strip():
                    errores.append("La empresa es obligatoria.")
                if not ad_motivo.strip():
                    errores.append("El motivo es obligatorio.")
                if ad_monto <= 0:
                    errores.append("El monto debe ser mayor a 0.")

                if errores:
                    for err in errores:
                        st.error(err)
                else:
                    descripcion_bd = ad_motivo.strip()
                    if ad_num_fac.strip():
                        descripcion_bd = f"Factura {ad_num_fac.strip()} — {descripcion_bd}"

                    try:
                        cursor_ins = conn.cursor()
                        cursor_ins.execute("""
                            INSERT INTO gastos_administrativos
                                (fecha, categoria, descripcion, monto, estado, proveedor, numero_factura, observaciones)
                            VALUES (%s, 'otros', %s, %s, 'pendiente', %s, %s, 'Adelanto Dueño')
                        """, (
                            ad_fecha,
                            descripcion_bd,
                            ad_monto,
                            ad_empresa.strip(),
                            ad_num_fac.strip() or None,
                        ))
                        conn.commit()
                        cursor_ins.close()
                        st.success(f"✅ Registrado: {ad_empresa.strip()} — ${ad_monto:,.0f}")
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Error al guardar: {e}")

        st.divider()

        # ── Listado de adelantos ───────────────────────────────────────────────
        st.markdown("### 📋 Adelantos Registrados")

        filtro_ad = st.radio(
            "Mostrar",
            ["Pendientes", "Pagados", "Todos"],
            horizontal=True,
            key="filtro_adelantos"
        )
        where_ad = {
            "Pendientes": "AND estado = 'pendiente'",
            "Pagados":    "AND estado = 'pagado'",
            "Todos":      "",
        }[filtro_ad]

        cursor_t7.execute(f"""
            SELECT id, fecha, proveedor AS empresa, numero_factura AS numero_factura_ext, descripcion, monto, estado
            FROM gastos_administrativos
            WHERE observaciones = 'Adelanto Dueño' {where_ad}
            ORDER BY fecha DESC
            LIMIT 200
        """)
        adelantos = cursor_t7.fetchall()

        if adelantos:
            total_pendiente = sum(float(r['monto']) for r in adelantos if r['estado'] == 'pendiente')
            total_pagado    = sum(float(r['monto']) for r in adelantos if r['estado'] == 'pagado')

            m1, m2, m3 = st.columns(3)
            m1.metric("Registros mostrados", len(adelantos))
            m2.metric("Pendiente de reembolso", f"${total_pendiente:,.0f}")
            m3.metric("Ya reembolsado", f"${total_pagado:,.0f}")

            st.divider()

            for ad in adelantos:
                icon = "🟡" if ad['estado'] == 'pendiente' else "🟢"
                fac_label = f" — Factura: {ad['numero_factura_ext']}" if ad['numero_factura_ext'] else ""
                with st.expander(
                    f"{icon} {ad['fecha'].strftime('%d/%m/%Y')} | {ad['empresa']}{fac_label} — ${float(ad['monto']):,.0f}"
                ):
                    st.write(f"**Descripción:** {ad['descripcion']}")
                    st.write(f"**Estado:** {ad['estado'].capitalize()}")

                    col_e1, col_e2, _ = st.columns([1, 1, 2])
                    with col_e1:
                        nuevo_est = st.selectbox(
                            "Estado",
                            ["pendiente", "pagado", "anulado"],
                            index=["pendiente", "pagado", "anulado"].index(ad['estado'])
                                  if ad['estado'] in ["pendiente", "pagado", "anulado"] else 0,
                            key=f"est_ad_{ad['id']}",
                            label_visibility="collapsed",
                        )
                    with col_e2:
                        if st.button("Actualizar", key=f"btn_ad_{ad['id']}"):
                            try:
                                cursor_upd = conn.cursor()
                                cursor_upd.execute(
                                    "UPDATE gastos_administrativos SET estado = %s WHERE id = %s",
                                    (nuevo_est, ad['id'])
                                )
                                conn.commit()
                                cursor_upd.close()
                                st.success("Estado actualizado")
                                st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"Error: {e}")
        else:
            st.info("No hay adelantos registrados para el filtro seleccionado.")

    except Exception as e:
        st.error(f"Error: {e}")


if 'cursor' in locals():
    cursor.close()
