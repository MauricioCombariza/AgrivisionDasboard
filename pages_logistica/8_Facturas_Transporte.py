import streamlit as st
import pandas as pd
from datetime import date, timedelta
from decimal import Decimal
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_connection import conectar_logistica


st.title("🚚 Facturas de Transporte")

conn = conectar_logistica()
if not conn:
    st.stop()

# Asegurar columnas opcionales en facturas_transporte
try:
    _cursor = conn.cursor()
    for _col, _ddl in [
        ('fecha_vencimiento', 'ALTER TABLE facturas_transporte ADD COLUMN fecha_vencimiento DATE NULL'),
        ('monto_pagado',      'ALTER TABLE facturas_transporte ADD COLUMN monto_pagado DECIMAL(15,2) NULL'),
    ]:
        _cursor.execute("""
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'facturas_transporte'
            AND COLUMN_NAME = %s
        """, (_col,))
        if _cursor.fetchone()[0] == 0:
            _cursor.execute(_ddl)
            conn.commit()
    _cursor.close()
except Exception:
    pass

tab1, tab2, tab3, tab4 = st.tabs([
    "📥 Registrar Factura",
    "📋 Facturas Registradas",
    "📊 Resumen por Courrier",
    "📝 Asignar Órdenes"
])

with tab1:
    st.subheader("Registrar Nueva Factura de Transporte")

    try:
        cursor = conn.cursor(dictionary=True)

        # Obtener courriers (courier_externo y transportadora)
        cursor.execute("""
            SELECT id, codigo, nombre_completo
            FROM personal
            WHERE activo = TRUE AND tipo_personal IN ('courier_externo', 'transportadora')
            ORDER BY nombre_completo
        """)
        courriers = cursor.fetchall()

        if not courriers:
            st.warning("No hay courriers registrados. Registra primero en la seccion de Personal.")
            st.stop()

        # Obtener ordenes activas
        cursor.execute("""
            SELECT o.id, o.numero_orden, c.nombre_empresa as cliente, o.cantidad_total,
                   o.fecha_recepcion
            FROM ordenes o
            JOIN clientes c ON o.cliente_id = c.id
            WHERE o.estado = 'activa'
            ORDER BY o.fecha_recepcion DESC, c.nombre_empresa
        """)
        ordenes = cursor.fetchall()

        if not ordenes:
            st.warning("No hay ordenes activas para asignar.")

        # Formulario de cabecera
        st.markdown("### Datos de la Factura")

        col1, col2, col3 = st.columns(3)

        with col1:
            numero_factura = st.text_input("Numero de Factura", placeholder="Ej: FT-001, ABC123")

        with col2:
            fecha_factura = st.date_input("Fecha de Factura", value=date.today())

        with col3:
            courrier_options = {f"{c['codigo']} - {c['nombre_completo']}": c['id'] for c in courriers}
            courrier_selected = st.selectbox("Courrier", options=list(courrier_options.keys()))
            courrier_id = courrier_options[courrier_selected] if courrier_selected else None

        col_monto, col_plazo, col_venc = st.columns(3)

        with col_monto:
            monto_total = st.number_input("Monto Total de la Factura", min_value=0.0, step=1000.0, format="%.2f")

        with col_plazo:
            plazo_dias = st.number_input("Plazo de Pago (dias)", min_value=0, value=30, step=1)

        with col_venc:
            fecha_vencimiento = fecha_factura + timedelta(days=plazo_dias)
            st.date_input("Fecha de Vencimiento", value=fecha_vencimiento, disabled=True, key="fv_display")

        st.divider()

        # Detalle de ordenes
        st.markdown("### Detalle por Orden")
        st.caption("Agrega las ordenes incluidas en esta factura con su cantidad de sobres")

        # Inicializar estado para ordenes agregadas
        if 'ordenes_factura' not in st.session_state:
            st.session_state.ordenes_factura = []

        # Selector para agregar orden
        col1, col2, col3 = st.columns([3, 1, 1])

        with col1:
            orden_options = {f"{o['numero_orden']} - {o['cliente']} ({o['cantidad_total']} items)": o for o in ordenes}
            orden_selected = st.selectbox("Seleccionar Orden", options=[""] + list(orden_options.keys()))

        with col2:
            cantidad_sobres = st.number_input("Cantidad Sobres", min_value=1, value=1, step=1)

        with col3:
            st.write("")
            st.write("")
            if st.button("➕ Agregar", type="secondary"):
                if orden_selected and orden_selected != "":
                    orden_data = orden_options[orden_selected]
                    # Verificar que no este ya agregada
                    ids_agregados = [o['orden_id'] for o in st.session_state.ordenes_factura]
                    if orden_data['id'] not in ids_agregados:
                        st.session_state.ordenes_factura.append({
                            'orden_id': orden_data['id'],
                            'numero_orden': orden_data['numero_orden'],
                            'cliente': orden_data['cliente'],
                            'cantidad_sobres': cantidad_sobres
                        })
                        st.rerun()
                    else:
                        st.warning("Esta orden ya fue agregada")
                else:
                    st.warning("Selecciona una orden")

        # Mostrar ordenes agregadas
        if st.session_state.ordenes_factura:
            st.markdown("#### Ordenes Agregadas")

            total_sobres = sum([o['cantidad_sobres'] for o in st.session_state.ordenes_factura])

            # Crear tabla con calculo de porcentaje y costo
            datos_tabla = []
            for i, orden in enumerate(st.session_state.ordenes_factura):
                porcentaje = (orden['cantidad_sobres'] / total_sobres * 100) if total_sobres > 0 else 0
                costo = (porcentaje / 100 * monto_total) if monto_total > 0 else 0
                datos_tabla.append({
                    '#': i + 1,
                    'Orden': orden['numero_orden'],
                    'Cliente': orden['cliente'],
                    'Sobres': orden['cantidad_sobres'],
                    '%': f"{porcentaje:.2f}%",
                    'Costo Asignado': f"${costo:,.2f}"
                })

            df_ordenes = pd.DataFrame(datos_tabla)
            st.dataframe(df_ordenes, use_container_width=True, hide_index=True)

            # Resumen
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Ordenes", len(st.session_state.ordenes_factura))
            with col2:
                st.metric("Total Sobres", total_sobres)
            with col3:
                st.metric("Monto Total", f"${monto_total:,.2f}")

            # Boton para eliminar ultima orden
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("🗑️ Quitar Ultima"):
                    if st.session_state.ordenes_factura:
                        st.session_state.ordenes_factura.pop()
                        st.rerun()

            with col2:
                if st.button("🧹 Limpiar Todo"):
                    st.session_state.ordenes_factura = []
                    st.rerun()

            st.divider()

            # Observaciones
            observaciones = st.text_area("Observaciones (opcional)", height=80)

            # Boton guardar
            if st.button("💾 Guardar Factura", type="primary", use_container_width=True):
                if not numero_factura:
                    st.error("Ingresa el numero de factura")
                elif not courrier_id:
                    st.error("Selecciona un courrier")
                elif monto_total <= 0:
                    st.error("El monto debe ser mayor a 0")
                elif not st.session_state.ordenes_factura:
                    st.error("Agrega al menos una orden")
                else:
                    try:
                        cursor = conn.cursor()

                        # Verificar que no exista la factura
                        cursor.execute("""
                            SELECT id FROM facturas_transporte
                            WHERE numero_factura = %s AND courrier_id = %s
                        """, (numero_factura, courrier_id))

                        if cursor.fetchone():
                            st.error("Ya existe una factura con ese numero para este courrier")
                        else:
                            # Insertar cabecera
                            cursor.execute("""
                                INSERT INTO facturas_transporte
                                (numero_factura, fecha_factura, courrier_id, monto_total, total_sobres, observaciones, fecha_vencimiento)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (numero_factura, fecha_factura, courrier_id, monto_total, total_sobres, observaciones or None, fecha_vencimiento))

                            factura_id = cursor.lastrowid

                            # Insertar detalle y actualizar costo_flete en ordenes
                            for orden in st.session_state.ordenes_factura:
                                porcentaje = orden['cantidad_sobres'] / total_sobres * 100
                                costo_asignado = porcentaje / 100 * monto_total

                                # Insertar detalle
                                cursor.execute("""
                                    INSERT INTO detalle_facturas_transporte
                                    (factura_id, orden_id, cantidad_sobres, costo_asignado)
                                    VALUES (%s, %s, %s, %s)
                                """, (factura_id, orden['orden_id'], orden['cantidad_sobres'], costo_asignado))

                                # Actualizar costo_flete_total en la orden
                                cursor.execute("""
                                    UPDATE ordenes
                                    SET costo_flete_total = COALESCE(costo_flete_total, 0) + %s
                                    WHERE id = %s
                                """, (costo_asignado, orden['orden_id']))

                            conn.commit()
                            st.success(f"Factura {numero_factura} registrada exitosamente")
                            st.session_state.ordenes_factura = []
                            st.rerun()

                    except Exception as e:
                        conn.rollback()
                        st.error(f"Error al guardar: {e}")

        else:
            st.info("Agrega ordenes usando el selector de arriba")

    except Exception as e:
        st.error(f"Error: {e}")

with tab2:
    st.subheader("Facturas Registradas")

    try:
        cursor = conn.cursor(dictionary=True)

        col_buscar, col_desde, col_hasta = st.columns([2, 1, 1])
        with col_buscar:
            buscar_factura = st.text_input("Buscar por Nro. Factura o Courrier", placeholder="Ej: FT-001, Servientrega...", key="buscar_ft")
        with col_desde:
            fecha_desde = st.date_input("Desde", value=date.today().replace(day=1), key="fecha_desde_ft")
        with col_hasta:
            fecha_hasta = st.date_input("Hasta", value=date.today(), key="fecha_hasta_ft")

        like_param = f"%{buscar_factura.strip()}%" if buscar_factura.strip() else "%"

        cursor.execute("""
            SELECT
                ft.id, ft.numero_factura, ft.fecha_factura,
                p.nombre_completo as courrier,
                ft.courrier_id,
                ft.monto_total, ft.total_sobres, ft.estado,
                ft.fecha_vencimiento, ft.monto_pagado,
                ft.observaciones,
                COUNT(dft.id) as num_ordenes,
                COALESCE(SUM(dft.costo_asignado), 0) as total_asignado
            FROM facturas_transporte ft
            JOIN personal p ON ft.courrier_id = p.id
            LEFT JOIN detalle_facturas_transporte dft ON ft.id = dft.factura_id
            WHERE ft.fecha_factura BETWEEN %s AND %s
              AND (ft.numero_factura LIKE %s OR p.nombre_completo LIKE %s)
            GROUP BY ft.id
            ORDER BY ft.fecha_factura DESC
        """, (fecha_desde, fecha_hasta, like_param, like_param))

        facturas = cursor.fetchall()

        if not facturas:
            st.info("No hay facturas en el periodo seleccionado")
        else:
            # --- Resumen rapido ---
            col1, col2, col3, col4 = st.columns(4)
            total_monto = sum(float(f['monto_total']) for f in facturas)
            total_pagado = sum(float(f['monto_pagado']) for f in facturas if f['monto_pagado'])
            n_pendientes = sum(1 for f in facturas if f['estado'] == 'pendiente')
            monto_pendiente = sum(float(f['monto_total']) for f in facturas if f['estado'] == 'pendiente')
            with col1:
                st.metric("Total Facturas", len(facturas))
            with col2:
                st.metric("Monto Total", f"${total_monto:,.0f}")
            with col3:
                st.metric("Pendientes", n_pendientes, delta=f"-${monto_pendiente:,.0f}", delta_color="inverse")
            with col4:
                st.metric("Total Pagado", f"${total_pagado:,.0f}")

            # --- Facturas pendientes del periodo (formulario visible) ---
            pendientes_list = [f for f in facturas if f['estado'] == 'pendiente']
            if pendientes_list:
                st.divider()
                st.markdown(f"### Pendientes de Pago ({len(pendientes_list)})")

                for factura in pendientes_list:
                    fid = factura['id']
                    monto_pagado_actual = float(factura['monto_pagado']) if factura['monto_pagado'] else 0.0
                    total_asignado = float(factura['total_asignado'] or 0)

                    if factura['fecha_vencimiento']:
                        dias_restantes = (factura['fecha_vencimiento'] - date.today()).days
                        if dias_restantes < 0:
                            alerta_venc = f"Vencida hace {abs(dias_restantes)} dias"
                            color_venc = "error"
                        elif dias_restantes <= 7:
                            alerta_venc = f"Vence en {dias_restantes} dias"
                            color_venc = "warning"
                        else:
                            alerta_venc = f"{dias_restantes} dias para vencer"
                            color_venc = "info"
                    else:
                        alerta_venc = None
                        color_venc = None

                    with st.container(border=True):
                        # Cabecera de la factura
                        col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns([2, 1, 1, 1, 1])
                        with col_h1:
                            st.markdown(f"**{factura['numero_factura']}** — {factura['courrier']}")
                            st.caption(f"Fecha: {factura['fecha_factura'].strftime('%d/%m/%Y')}")
                        with col_h2:
                            st.metric("Monto Factura", f"${float(factura['monto_total']):,.0f}")
                        with col_h3:
                            st.metric("Suma Ordenes", f"${total_asignado:,.0f}")
                        with col_h4:
                            st.metric("Sobres", factura['total_sobres'])
                        with col_h5:
                            if alerta_venc:
                                if color_venc == "error":
                                    st.error(alerta_venc)
                                elif color_venc == "warning":
                                    st.warning(alerta_venc)
                                else:
                                    st.info(alerta_venc)
                            else:
                                st.metric("Vencimiento", "No definido")

                        # Formulario de pago
                        st.markdown("**Registrar Pago**")
                        col_p1, col_p2, col_p3, col_p4 = st.columns([2, 2, 1, 1])
                        with col_p1:
                            pay_monto = st.number_input(
                                "Monto Pagado",
                                min_value=0.0, step=1000.0, format="%.2f",
                                value=monto_pagado_actual if monto_pagado_actual > 0 else float(factura['monto_total']),
                                help="Ingresa el valor real pagado (puede incluir descuentos o penalizaciones)",
                                key=f"pay_monto_{fid}"
                            )
                            diferencia = pay_monto - float(factura['monto_total'])
                            if abs(diferencia) > 0.01:
                                if diferencia < 0:
                                    st.caption(f"Descuento aplicado: ${abs(diferencia):,.0f}")
                                else:
                                    st.caption(f"Penalizacion aplicada: +${diferencia:,.0f}")
                        with col_p2:
                            pay_obs = st.text_input(
                                "Observacion del pago",
                                placeholder="Ej: Transferencia 12345, descuento por...",
                                key=f"pay_obs_{fid}"
                            )
                        with col_p3:
                            pay_estado = st.selectbox(
                                "Estado",
                                ['pendiente', 'pagada', 'anulada'],
                                index=0,
                                key=f"pay_est_{fid}"
                            )
                        with col_p4:
                            st.write("")
                            st.write("")
                            if st.button("Guardar Pago", type="primary", key=f"pay_btn_{fid}"):
                                try:
                                    monto_guardar = pay_monto if pay_monto > 0 else None
                                    obs_actual = factura.get('observaciones') or ''
                                    nueva_obs = (obs_actual + f" | Pago: {pay_obs}").strip(" |") if pay_obs else obs_actual
                                    cursor2 = conn.cursor()
                                    cursor2.execute("""
                                        UPDATE facturas_transporte
                                        SET estado = %s, monto_pagado = %s
                                        WHERE id = %s
                                    """, (pay_estado, monto_guardar, fid))
                                    conn.commit()
                                    cursor2.close()
                                    st.success(f"Factura {factura['numero_factura']} actualizada")
                                    st.rerun()
                                except Exception as e:
                                    conn.rollback()
                                    st.error(f"Error: {e}")

            # --- Listado completo con detalle (expandible) ---
            st.divider()
            st.markdown("### Todas las Facturas del Periodo")

            # Courriers para el selector de edición
            cursor.execute("""
                SELECT id, codigo, nombre_completo FROM personal
                WHERE activo = TRUE AND tipo_personal IN ('courier_externo', 'transportadora')
                ORDER BY nombre_completo
            """)
            edit_courrier_opts = {
                f"{c['codigo']} - {c['nombre_completo']}": c['id']
                for c in cursor.fetchall()
            }

            # Órdenes activas para agregar a facturas existentes
            cursor.execute("""
                SELECT o.id, o.numero_orden, c.nombre_empresa as cliente
                FROM ordenes o
                JOIN clientes c ON o.cliente_id = c.id
                WHERE o.estado = 'activa'
                ORDER BY o.fecha_recepcion DESC, c.nombre_empresa
            """)
            todas_ordenes = cursor.fetchall()

            for factura in facturas:
                estado_icon = "🟢" if factura['estado'] == 'pagada' else "🟡" if factura['estado'] == 'pendiente' else "🔴"
                fid = factura['id']
                monto_pagado_actual = float(factura['monto_pagado']) if factura['monto_pagado'] else None
                total_asignado = float(factura['total_asignado'] or 0)
                etiqueta_pagado = f" | Pagado: ${monto_pagado_actual:,.0f}" if monto_pagado_actual else ""

                with st.expander(f"{estado_icon} {factura['numero_factura']} - {factura['courrier']} - ${float(factura['monto_total']):,.0f}{etiqueta_pagado}"):
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        st.metric("Fecha", factura['fecha_factura'].strftime('%d/%m/%Y'))
                    with col2:
                        st.metric("Monto Factura", f"${float(factura['monto_total']):,.0f}")
                    with col3:
                        st.metric("Suma Ordenes", f"${total_asignado:,.0f}")
                    with col4:
                        st.metric("Sobres", factura['total_sobres'])
                    with col5:
                        if monto_pagado_actual:
                            st.metric("Monto Pagado", f"${monto_pagado_actual:,.0f}")
                        elif factura['fecha_vencimiento']:
                            st.metric("Vencimiento", factura['fecha_vencimiento'].strftime('%d/%m/%Y'))
                        else:
                            st.metric("Estado", factura['estado'].capitalize())

                    # ── Órdenes de la factura con opción de quitar ───────
                    cursor.execute("""
                        SELECT dft.id as detalle_id, dft.orden_id,
                               dft.cantidad_sobres, dft.costo_asignado,
                               o.numero_orden, c.nombre_empresa as cliente
                        FROM detalle_facturas_transporte dft
                        JOIN ordenes o ON dft.orden_id = o.id
                        JOIN clientes c ON o.cliente_id = c.id
                        WHERE dft.factura_id = %s
                        ORDER BY c.nombre_empresa
                    """, (fid,))
                    detalles = cursor.fetchall()

                    if detalles:
                        st.markdown("**Órdenes de la factura:**")
                        hdr = st.columns([2, 2, 1, 2, 1])
                        for lbl, col in zip(["Orden", "Cliente", "Sobres", "% · Costo", ""], hdr):
                            col.markdown(f"**{lbl}**")
                        for det in detalles:
                            pct = det['cantidad_sobres'] / factura['total_sobres'] * 100 if factura['total_sobres'] else 0
                            dc1, dc2, dc3, dc4, dc5 = st.columns([2, 2, 1, 2, 1])
                            dc1.write(det['numero_orden'])
                            dc2.write(det['cliente'])
                            dc3.write(str(det['cantidad_sobres']))
                            dc4.write(f"{pct:.1f}%  ·  ${float(det['costo_asignado']):,.0f}")
                            if dc5.button("❌", key=f"quitar_det_{det['detalle_id']}", help="Quitar esta orden"):
                                try:
                                    c2 = conn.cursor(dictionary=True)
                                    old_sobres = int(det['cantidad_sobres'])
                                    old_costo  = float(det['costo_asignado'])
                                    new_total  = max(0, int(factura['total_sobres']) - old_sobres)
                                    monto_ft   = float(factura['monto_total'])

                                    # Revertir costo en la orden
                                    c2.execute("""
                                        UPDATE ordenes
                                        SET costo_flete_total = GREATEST(0, COALESCE(costo_flete_total, 0) - %s)
                                        WHERE id = %s
                                    """, (old_costo, det['orden_id']))

                                    # Eliminar línea de detalle
                                    c2.execute("DELETE FROM detalle_facturas_transporte WHERE id = %s", (det['detalle_id'],))

                                    # Actualizar total_sobres en la factura
                                    c2.execute("UPDATE facturas_transporte SET total_sobres = %s WHERE id = %s", (new_total, fid))

                                    # Recalcular proporciones en las líneas restantes
                                    if new_total > 0:
                                        c2.execute("""
                                            SELECT id, orden_id, cantidad_sobres, costo_asignado
                                            FROM detalle_facturas_transporte WHERE factura_id = %s
                                        """, (fid,))
                                        for rem in c2.fetchall():
                                            nc = monto_ft * rem['cantidad_sobres'] / new_total
                                            delta = nc - float(rem['costo_asignado'])
                                            c2.execute("UPDATE detalle_facturas_transporte SET costo_asignado = %s WHERE id = %s", (nc, rem['id']))
                                            if abs(delta) > 0.01:
                                                c2.execute("""
                                                    UPDATE ordenes SET costo_flete_total = COALESCE(costo_flete_total, 0) + %s WHERE id = %s
                                                """, (delta, rem['orden_id']))

                                    conn.commit()
                                    c2.close()
                                    st.success(f"Orden {det['numero_orden']} removida y costos recalculados")
                                    st.rerun()
                                except Exception as e_q:
                                    conn.rollback()
                                    st.error(f"Error al quitar: {e_q}")

                    # ── Agregar orden a la factura ────────────────────────
                    st.markdown("**Agregar orden:**")
                    ordenes_en_factura = {det['orden_id'] for det in (detalles or [])}
                    ordenes_disponibles = [o for o in todas_ordenes if o['id'] not in ordenes_en_factura]
                    col_ao1, col_ao2, col_ao3 = st.columns([3, 1, 1])
                    with col_ao1:
                        add_ord_opts = {f"{o['numero_orden']} - {o['cliente']}": o for o in ordenes_disponibles}
                        add_ord_sel = st.selectbox("Orden a agregar", options=[""] + list(add_ord_opts.keys()), key=f"add_ord_sel_{fid}")
                    with col_ao2:
                        add_sobres = st.number_input("Sobres", min_value=1, value=1, step=1, key=f"add_sobres_{fid}")
                    with col_ao3:
                        st.write("")
                        st.write("")
                        if st.button("➕ Agregar", key=f"add_ord_btn_{fid}"):
                            if add_ord_sel:
                                orden_data = add_ord_opts[add_ord_sel]
                                new_total = int(factura['total_sobres']) + add_sobres
                                monto_ft  = float(factura['monto_total'])
                                try:
                                    c2 = conn.cursor(dictionary=True)
                                    # Recalcular líneas existentes con el nuevo total de sobres
                                    c2.execute("""
                                        SELECT id, orden_id, cantidad_sobres, costo_asignado
                                        FROM detalle_facturas_transporte WHERE factura_id = %s
                                    """, (fid,))
                                    for ex in c2.fetchall():
                                        nc = monto_ft * ex['cantidad_sobres'] / new_total
                                        delta = nc - float(ex['costo_asignado'])
                                        c2.execute("UPDATE detalle_facturas_transporte SET costo_asignado = %s WHERE id = %s", (nc, ex['id']))
                                        if abs(delta) > 0.01:
                                            c2.execute("""
                                                UPDATE ordenes SET costo_flete_total = COALESCE(costo_flete_total, 0) + %s WHERE id = %s
                                            """, (delta, ex['orden_id']))
                                    # Insertar nueva línea
                                    nc_new = monto_ft * add_sobres / new_total
                                    c2.execute("""
                                        INSERT INTO detalle_facturas_transporte (factura_id, orden_id, cantidad_sobres, costo_asignado)
                                        VALUES (%s, %s, %s, %s)
                                    """, (fid, orden_data['id'], add_sobres, nc_new))
                                    c2.execute("""
                                        UPDATE ordenes SET costo_flete_total = COALESCE(costo_flete_total, 0) + %s WHERE id = %s
                                    """, (nc_new, orden_data['id']))
                                    c2.execute("UPDATE facturas_transporte SET total_sobres = %s WHERE id = %s", (new_total, fid))
                                    conn.commit()
                                    c2.close()
                                    st.success(f"Orden {orden_data['numero_orden']} agregada y costos recalculados")
                                    st.rerun()
                                except Exception as e_a:
                                    conn.rollback()
                                    st.error(f"Error al agregar: {e_a}")
                            else:
                                st.warning("Selecciona una orden para agregar")

                    # ── Editar cabecera ───────────────────────────────────
                    st.markdown("---")
                    st.markdown("**Editar Factura**")

                    col_e1, col_e2, col_e3, col_e4 = st.columns(4)
                    with col_e1:
                        edit_num_factura = st.text_input("Numero Factura", value=factura['numero_factura'], key=f"edit_num_{fid}")
                    with col_e2:
                        edit_fecha_factura = st.date_input("Fecha Factura", value=factura['fecha_factura'], key=f"edit_fecha_{fid}")
                    with col_e3:
                        edit_fecha_venc = st.date_input(
                            "Fecha Vencimiento",
                            value=factura['fecha_vencimiento'] if factura['fecha_vencimiento'] else date.today() + timedelta(days=30),
                            key=f"edit_venc_{fid}"
                        )
                    with col_e4:
                        edit_monto = st.number_input("Monto Total", min_value=0.0, step=1000.0, format="%.2f",
                                                     value=float(factura['monto_total']), key=f"edit_monto_{fid}")

                    col_e5, col_e6, col_e7 = st.columns([1, 1, 2])
                    with col_e5:
                        # Preseleccionar el courrier actual de la factura
                        edit_cour_keys = list(edit_courrier_opts.keys())
                        try:
                            cour_default = list(edit_courrier_opts.values()).index(factura['courrier_id'])
                        except ValueError:
                            cour_default = 0
                        edit_cour_sel = st.selectbox("Courrier", options=edit_cour_keys, index=cour_default, key=f"edit_cour_{fid}")
                        edit_courrier_id = edit_courrier_opts[edit_cour_sel]
                    with col_e6:
                        nuevo_estado = st.selectbox(
                            "Estado",
                            ['pendiente', 'pagada', 'anulada'],
                            index=['pendiente', 'pagada', 'anulada'].index(factura['estado']),
                            key=f"estado_{fid}"
                        )
                        edit_monto_pagado = st.number_input(
                            "Monto Pagado",
                            min_value=0.0, step=1000.0, format="%.2f",
                            value=monto_pagado_actual if monto_pagado_actual else 0.0,
                            key=f"pagado_{fid}"
                        )
                        if edit_monto_pagado > 0:
                            diferencia = edit_monto_pagado - float(factura['monto_total'])
                            if diferencia < 0:
                                st.caption(f"Descuento: ${abs(diferencia):,.0f}")
                            elif diferencia > 0:
                                st.caption(f"Penalizacion: +${diferencia:,.0f}")
                    with col_e7:
                        edit_obs = st.text_area(
                            "Observaciones",
                            value=factura.get('observaciones') or '',
                            height=100,
                            key=f"edit_obs_{fid}"
                        )

                    if st.button("💾 Guardar Cambios", key=f"btn_{fid}", type="primary"):
                        try:
                            monto_pagado_guardar = edit_monto_pagado if edit_monto_pagado > 0 else None
                            cursor2 = conn.cursor(dictionary=True)

                            # Si cambió el monto, propagar a detalle y a ordenes.costo_flete_total
                            if abs(edit_monto - float(factura['monto_total'])) > 0.01 and factura['total_sobres'] > 0:
                                cursor2.execute("""
                                    SELECT id, orden_id, cantidad_sobres, costo_asignado
                                    FROM detalle_facturas_transporte WHERE factura_id = %s
                                """, (fid,))
                                for det in cursor2.fetchall():
                                    new_costo = edit_monto * det['cantidad_sobres'] / factura['total_sobres']
                                    delta = new_costo - float(det['costo_asignado'])
                                    cursor2.execute(
                                        "UPDATE detalle_facturas_transporte SET costo_asignado = %s WHERE id = %s",
                                        (new_costo, det['id'])
                                    )
                                    if abs(delta) > 0.01:
                                        cursor2.execute("""
                                            UPDATE ordenes SET costo_flete_total = COALESCE(costo_flete_total, 0) + %s WHERE id = %s
                                        """, (delta, det['orden_id']))

                            cursor2.execute("""
                                UPDATE facturas_transporte
                                SET numero_factura = %s, fecha_factura = %s,
                                    fecha_vencimiento = %s, monto_total = %s,
                                    estado = %s, monto_pagado = %s,
                                    courrier_id = %s, observaciones = %s
                                WHERE id = %s
                            """, (edit_num_factura, edit_fecha_factura,
                                  edit_fecha_venc, edit_monto,
                                  nuevo_estado, monto_pagado_guardar,
                                  edit_courrier_id, edit_obs or None, fid))
                            conn.commit()
                            cursor2.close()
                            st.success("Factura actualizada")
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error al actualizar: {e}")

    except Exception as e:
        st.error(f"Error: {e}")

with tab3:
    st.subheader("Resumen por Courrier")

    try:
        cursor = conn.cursor(dictionary=True)

        col1, col2 = st.columns(2)
        with col1:
            anio = st.number_input("Año", min_value=2020, max_value=2030, value=date.today().year, key="anio_resumen")
        with col2:
            mes = st.selectbox("Mes", [
                "Todos", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
            ], key="mes_resumen")

        if mes != "Todos":
            mes_num = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                       "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes) + 1
            cursor.execute("""
                SELECT
                    p.nombre_completo as courrier,
                    COUNT(ft.id) as total_facturas,
                    SUM(ft.monto_total) as monto_total,
                    SUM(ft.total_sobres) as total_sobres
                FROM facturas_transporte ft
                JOIN personal p ON ft.courrier_id = p.id
                WHERE YEAR(ft.fecha_factura) = %s AND MONTH(ft.fecha_factura) = %s
                AND ft.estado != 'anulada'
                GROUP BY p.id, p.nombre_completo
                ORDER BY monto_total DESC
            """, (anio, mes_num))
        else:
            cursor.execute("""
                SELECT
                    p.nombre_completo as courrier,
                    COUNT(ft.id) as total_facturas,
                    SUM(ft.monto_total) as monto_total,
                    SUM(ft.total_sobres) as total_sobres
                FROM facturas_transporte ft
                JOIN personal p ON ft.courrier_id = p.id
                WHERE YEAR(ft.fecha_factura) = %s
                AND ft.estado != 'anulada'
                GROUP BY p.id, p.nombre_completo
                ORDER BY monto_total DESC
            """, (anio,))

        resumen = cursor.fetchall()

        if resumen:
            st.markdown("### Por Courrier")

            for r in resumen:
                costo_por_sobre = r['monto_total'] / r['total_sobres'] if r['total_sobres'] > 0 else 0

                with st.expander(f"🚚 {r['courrier']} - ${r['monto_total']:,.0f}"):
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("Facturas", r['total_facturas'])
                    with col2:
                        st.metric("Monto Total", f"${r['monto_total']:,.0f}")
                    with col3:
                        st.metric("Total Sobres", f"{r['total_sobres']:,}")
                    with col4:
                        st.metric("Costo/Sobre", f"${costo_por_sobre:,.2f}")

            st.divider()

            # Totales generales
            st.markdown("### Totales Generales")
            col1, col2, col3 = st.columns(3)

            with col1:
                total_facturas = sum([r['total_facturas'] for r in resumen])
                st.metric("Total Facturas", total_facturas)
            with col2:
                total_monto = sum([r['monto_total'] for r in resumen])
                st.metric("Monto Total", f"${total_monto:,.0f}")
            with col3:
                total_sobres = sum([r['total_sobres'] for r in resumen])
                costo_promedio = total_monto / total_sobres if total_sobres > 0 else 0
                st.metric("Costo Promedio/Sobre", f"${costo_promedio:,.2f}")

            st.divider()

            # Resumen por cliente
            st.markdown("### Distribucion por Cliente")

            if mes != "Todos":
                cursor.execute("""
                    SELECT
                        c.nombre_empresa as cliente,
                        SUM(dft.cantidad_sobres) as total_sobres,
                        SUM(dft.costo_asignado) as costo_total
                    FROM detalle_facturas_transporte dft
                    JOIN facturas_transporte ft ON dft.factura_id = ft.id
                    JOIN ordenes o ON dft.orden_id = o.id
                    JOIN clientes c ON o.cliente_id = c.id
                    WHERE YEAR(ft.fecha_factura) = %s AND MONTH(ft.fecha_factura) = %s
                    AND ft.estado != 'anulada'
                    GROUP BY c.id, c.nombre_empresa
                    ORDER BY costo_total DESC
                """, (anio, mes_num))
            else:
                cursor.execute("""
                    SELECT
                        c.nombre_empresa as cliente,
                        SUM(dft.cantidad_sobres) as total_sobres,
                        SUM(dft.costo_asignado) as costo_total
                    FROM detalle_facturas_transporte dft
                    JOIN facturas_transporte ft ON dft.factura_id = ft.id
                    JOIN ordenes o ON dft.orden_id = o.id
                    JOIN clientes c ON o.cliente_id = c.id
                    WHERE YEAR(ft.fecha_factura) = %s
                    AND ft.estado != 'anulada'
                    GROUP BY c.id, c.nombre_empresa
                    ORDER BY costo_total DESC
                """, (anio,))

            clientes_resumen = cursor.fetchall()

            if clientes_resumen:
                df_clientes = pd.DataFrame(clientes_resumen)
                df_clientes['costo_por_sobre'] = (df_clientes['costo_total'] / df_clientes['total_sobres']).round(2)
                df_clientes['costo_total'] = df_clientes['costo_total'].apply(lambda x: f"${x:,.2f}")
                df_clientes['costo_por_sobre'] = df_clientes['costo_por_sobre'].apply(lambda x: f"${x:,.2f}")
                df_clientes.columns = ['Cliente', 'Sobres', 'Costo Total', 'Costo/Sobre']
                st.dataframe(df_clientes, use_container_width=True, hide_index=True)

        else:
            st.info("No hay datos para el periodo seleccionado")

    except Exception as e:
        st.error(f"Error: {e}")

with tab4:
    st.subheader("Asignar Órdenes a Facturas Existentes")
    st.info("Use esta sección para asignar órdenes a facturas que fueron registradas sin detalle de órdenes.")

    try:
        cursor = conn.cursor(dictionary=True)

        # Obtener facturas sin órdenes asignadas o con asignación parcial
        cursor.execute("""
            SELECT
                ft.id, ft.numero_factura, ft.fecha_factura,
                p.nombre_completo as courrier,
                ft.monto_total, ft.total_sobres,
                COALESCE(SUM(dft.cantidad_sobres), 0) as sobres_asignados
            FROM facturas_transporte ft
            JOIN personal p ON ft.courrier_id = p.id
            LEFT JOIN detalle_facturas_transporte dft ON ft.id = dft.factura_id
            WHERE ft.estado != 'anulada'
            GROUP BY ft.id
            HAVING sobres_asignados < ft.total_sobres OR sobres_asignados = 0
            ORDER BY ft.fecha_factura DESC
        """)
        facturas_pendientes = cursor.fetchall()

        if not facturas_pendientes:
            st.success("✅ Todas las facturas tienen sus órdenes asignadas correctamente")
        else:
            st.warning(f"⚠️ Hay {len(facturas_pendientes)} facturas pendientes de asignar órdenes")

            # Selector de factura
            factura_options = {
                f"{f['numero_factura']} - {f['courrier']} - ${f['monto_total']:,.0f} ({f['sobres_asignados']}/{f['total_sobres']} sobres)": f
                for f in facturas_pendientes
            }
            factura_selected = st.selectbox("Seleccionar Factura", list(factura_options.keys()))
            factura_data = factura_options[factura_selected]

            st.markdown("---")

            # Mostrar info de la factura (convertir Decimal a int/float)
            monto_total = float(factura_data['monto_total'] or 0)
            total_sobres = int(factura_data['total_sobres'] or 0)
            sobres_asignados = int(factura_data['sobres_asignados'] or 0)

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Monto Total", f"${monto_total:,.0f}")
            with col2:
                st.metric("Sobres Declarados", total_sobres)
            with col3:
                st.metric("Sobres Asignados", sobres_asignados)
            with col4:
                pendientes = total_sobres - sobres_asignados
                st.metric("Pendientes", pendientes)

            st.markdown("---")

            # Obtener órdenes activas con cantidad nacional
            cursor.execute("""
                SELECT o.id, o.numero_orden, c.nombre_empresa as cliente,
                       o.cantidad_nacional, o.cantidad_local, o.fecha_recepcion
                FROM ordenes o
                JOIN clientes c ON o.cliente_id = c.id
                WHERE o.estado = 'activa' AND o.cantidad_nacional > 0
                ORDER BY o.fecha_recepcion DESC, c.nombre_empresa
            """)
            ordenes = cursor.fetchall()

            # Inicializar estado para órdenes de esta factura
            state_key = f'ordenes_factura_{factura_data["id"]}'
            if state_key not in st.session_state:
                st.session_state[state_key] = []

            # Selector para agregar orden
            st.markdown("### Agregar Órdenes")
            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                orden_options = {
                    f"{o['numero_orden']} - {o['cliente']} ({o['cantidad_nacional']} nac)": o
                    for o in ordenes
                }
                orden_selected = st.selectbox("Seleccionar Orden", [""] + list(orden_options.keys()), key="orden_asignar")

            with col2:
                max_sobres = total_sobres - sobres_asignados
                cantidad_sobres = st.number_input("Cantidad Sobres", min_value=1, value=1, step=1, key="cant_asignar")

            with col3:
                st.write("")
                st.write("")
                if st.button("➕ Agregar", key="btn_agregar_asignar"):
                    if orden_selected and orden_selected != "":
                        orden_data = orden_options[orden_selected]
                        ids_agregados = [o['orden_id'] for o in st.session_state[state_key]]
                        if orden_data['id'] not in ids_agregados:
                            st.session_state[state_key].append({
                                'orden_id': orden_data['id'],
                                'numero_orden': orden_data['numero_orden'],
                                'cliente': orden_data['cliente'],
                                'cantidad_sobres': cantidad_sobres
                            })
                            st.rerun()
                        else:
                            st.warning("Esta orden ya fue agregada")

            # Mostrar órdenes agregadas
            if st.session_state[state_key]:
                st.markdown("### Órdenes a Asignar")

                total_sobres_agregar = sum([o['cantidad_sobres'] for o in st.session_state[state_key]])

                datos_tabla = []
                for i, orden in enumerate(st.session_state[state_key]):
                    porcentaje = (orden['cantidad_sobres'] / total_sobres * 100) if total_sobres > 0 else 0
                    costo = (porcentaje / 100 * monto_total)
                    datos_tabla.append({
                        '#': i + 1,
                        'Orden': orden['numero_orden'],
                        'Cliente': orden['cliente'],
                        'Sobres': orden['cantidad_sobres'],
                        '%': f"{porcentaje:.2f}%",
                        'Costo Asignado': f"${costo:,.2f}"
                    })

                df_ordenes = pd.DataFrame(datos_tabla)
                st.dataframe(df_ordenes, use_container_width=True, hide_index=True)

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Órdenes a Agregar", len(st.session_state[state_key]))
                with col2:
                    st.metric("Sobres a Asignar", total_sobres_agregar)
                with col3:
                    total_a_asignar = sobres_asignados + total_sobres_agregar
                    st.metric("Total después", f"{total_a_asignar}/{total_sobres}")

                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button("🗑️ Quitar Última", key="quitar_asignar"):
                        st.session_state[state_key].pop()
                        st.rerun()
                with col2:
                    if st.button("🧹 Limpiar Todo", key="limpiar_asignar"):
                        st.session_state[state_key] = []
                        st.rerun()

                st.markdown("---")

                # Botón guardar
                if st.button("💾 Guardar Asignaciones", type="primary", use_container_width=True):
                    try:
                        cursor = conn.cursor()

                        for orden in st.session_state[state_key]:
                            porcentaje = (orden['cantidad_sobres'] / total_sobres * 100) if total_sobres > 0 else 0
                            costo_asignado = porcentaje / 100 * monto_total

                            # Insertar detalle
                            cursor.execute("""
                                INSERT INTO detalle_facturas_transporte
                                (factura_id, orden_id, cantidad_sobres, costo_asignado)
                                VALUES (%s, %s, %s, %s)
                            """, (factura_data['id'], orden['orden_id'], orden['cantidad_sobres'], costo_asignado))

                            # Actualizar costo_flete_total en la orden
                            cursor.execute("""
                                UPDATE ordenes
                                SET costo_flete_total = COALESCE(costo_flete_total, 0) + %s
                                WHERE id = %s
                            """, (costo_asignado, orden['orden_id']))

                        conn.commit()
                        st.success(f"✅ Se asignaron {len(st.session_state[state_key])} órdenes a la factura")
                        st.session_state[state_key] = []
                        st.rerun()

                    except Exception as e:
                        conn.rollback()
                        st.error(f"Error al guardar: {e}")
            else:
                st.info("Agregue órdenes usando el selector de arriba")

    except Exception as e:
        st.error(f"Error: {e}")

if 'cursor' in locals():
    cursor.close()
