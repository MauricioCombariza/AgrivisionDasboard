import streamlit as st
from datetime import datetime
from utils.db_connection import conectar_logistica

# =====================================================
# PÁGINA PRINCIPAL
# =====================================================

st.title("📦 Sistema de Gestión Logística")
st.subheader("Agrivision - Dashboard Principal")

# Verificar conexión
conn = conectar_logistica()
if not conn:
    st.error("⚠️ No se pudo conectar a la base de datos")
    st.stop()

# =====================================================
# MÉTRICAS PRINCIPALES
# =====================================================

col1, col2, col3, col4 = st.columns(4)

try:
    cursor = conn.cursor(dictionary=True)

    # Total clientes activos
    cursor.execute("SELECT COUNT(*) as total FROM clientes WHERE activo = TRUE")
    total_clientes = cursor.fetchone()['total']

    # Total personal activo
    cursor.execute("SELECT COUNT(*) as total FROM personal WHERE activo = TRUE")
    total_personal = cursor.fetchone()['total']

    # Órdenes activas
    cursor.execute("SELECT COUNT(*) as total FROM ordenes WHERE estado = 'activa'")
    ordenes_activas = cursor.fetchone()['total']

    # Facturas pendientes de cobro
    cursor.execute("SELECT COUNT(*) as total FROM facturas_emitidas WHERE estado IN ('pendiente', 'parcial', 'vencida')")
    facturas_pendientes = cursor.fetchone()['total']

    with col1:
        st.metric("👥 Clientes Activos", total_clientes)

    with col2:
        st.metric("🚚 Personal Activo", total_personal)

    with col3:
        st.metric("📦 Órdenes Activas", ordenes_activas)

    with col4:
        st.metric("💰 Facturas por Cobrar", facturas_pendientes)

except Exception as e:
    st.error(f"Error cargando métricas: {e}")

st.divider()

# =====================================================
# RESUMEN DE ÓRDENES DEL MES
# =====================================================

st.subheader("📊 Resumen del Mes Actual")

try:
    # 1. Datos básicos de órdenes
    cursor.execute("""
        SELECT
            COUNT(*) as total_ordenes,
            COALESCE(SUM(cantidad_total), 0) as total_items,
            COALESCE(SUM(valor_total), 0) as ingresos
        FROM ordenes
        WHERE MONTH(fecha_recepcion) = MONTH(CURRENT_DATE)
        AND YEAR(fecha_recepcion) = YEAR(CURRENT_DATE)
    """)
    ordenes_mes = cursor.fetchone()

    # 2. Entregas y devoluciones desde gestiones_mensajero
    cursor.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN tipo_gestion LIKE '%%Entrega%%' THEN total_seriales ELSE 0 END), 0) as entregados,
            COALESCE(SUM(CASE WHEN tipo_gestion NOT LIKE '%%Entrega%%' THEN total_seriales ELSE 0 END), 0) as devoluciones
        FROM gestiones_mensajero
        WHERE MONTH(fecha_registro) = MONTH(CURRENT_DATE)
        AND YEAR(fecha_registro) = YEAR(CURRENT_DATE)
    """)
    entregas_mes = cursor.fetchone()

    # 3. TODOS los costos del mes (registro_horas - alistamiento y administrativas)
    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) as costo_horas
        FROM registro_horas
        WHERE MONTH(fecha) = MONTH(CURRENT_DATE)
        AND YEAR(fecha) = YEAR(CURRENT_DATE)
    """)
    costo_horas = cursor.fetchone()['costo_horas']

    # 4. Costos de labores (pegado, transporte, etc.)
    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) as costo_labores
        FROM registro_labores
        WHERE MONTH(fecha) = MONTH(CURRENT_DATE)
        AND YEAR(fecha) = YEAR(CURRENT_DATE)
    """)
    costo_labores = cursor.fetchone()['costo_labores']

    # 5. Subsidios de transporte
    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) as costo_subsidios
        FROM subsidio_transporte
        WHERE MONTH(fecha) = MONTH(CURRENT_DATE)
        AND YEAR(fecha) = YEAR(CURRENT_DATE)
    """)
    costo_subsidios = cursor.fetchone()['costo_subsidios']

    # 6. Costos de mensajería (gestiones_mensajero)
    cursor.execute("""
        SELECT COALESCE(SUM(valor_total), 0) as costo_mensajeros
        FROM gestiones_mensajero
        WHERE MONTH(fecha_registro) = MONTH(CURRENT_DATE)
        AND YEAR(fecha_registro) = YEAR(CURRENT_DATE)
    """)
    costo_mensajeros = cursor.fetchone()['costo_mensajeros']

    # 7. Otros gastos administrativos
    cursor.execute("""
        SELECT COALESCE(SUM(monto), 0) as otros_gastos
        FROM costos_adicionales
        WHERE MONTH(fecha) = MONTH(CURRENT_DATE)
        AND YEAR(fecha) = YEAR(CURRENT_DATE)
    """)
    otros_gastos = cursor.fetchone()['otros_gastos']

    # 8. Costos de nómina administrativa (provisiones del mes)
    cursor.execute("""
        SELECT
            COALESCE(SUM(salario_base + auxilio_transporte), 0) as nomina_base,
            COALESCE(SUM(COALESCE(auxilio_no_salarial, 0)), 0) as nomina_aux_no_sal,
            COALESCE(SUM(total_seguridad_social), 0) as nomina_seg_social,
            COALESCE(SUM(total_provisiones), 0) as nomina_provisiones,
            COALESCE(SUM(costo_total_empleado + COALESCE(auxilio_no_salarial, 0)), 0) as nomina_total
        FROM nomina_provisiones
        WHERE periodo_mes = MONTH(CURRENT_DATE)
        AND periodo_anio = YEAR(CURRENT_DATE)
    """)
    nomina_mes = cursor.fetchone()
    costo_nomina = float(nomina_mes['nomina_total'] or 0)
    nomina_base = float(nomina_mes['nomina_base'] or 0)
    nomina_aux_no_sal = float(nomina_mes['nomina_aux_no_sal'] or 0)
    nomina_seg_social = float(nomina_mes['nomina_seg_social'] or 0)
    nomina_provisiones = float(nomina_mes['nomina_provisiones'] or 0)

    # Calcular totales
    ingresos = float(ordenes_mes['ingresos'] or 0)
    total_items = ordenes_mes['total_items'] or 0
    total_ordenes = ordenes_mes['total_ordenes'] or 0
    entregados = entregas_mes['entregados'] or 0
    devoluciones = entregas_mes['devoluciones'] or 0

    # COSTO TOTAL REAL = todos los gastos (operativos + nómina administrativa)
    costo_operativo = float(costo_horas) + float(costo_labores) + float(costo_subsidios) + float(costo_mensajeros) + float(otros_gastos)
    costo_total_real = costo_operativo + costo_nomina
    utilidad_real = ingresos - costo_total_real
    margen = (utilidad_real / ingresos * 100) if ingresos > 0 else 0

    if total_ordenes > 0:
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Órdenes", total_ordenes)
            st.metric("Total Items", f"{total_items:,}")

        with col2:
            st.metric("Entregados", f"{entregados:,}")
            st.metric("Devoluciones", f"{devoluciones:,}")

        with col3:
            st.metric("Ingresos", f"${ingresos:,.0f}")
            delta_color = "normal" if utilidad_real >= 0 else "inverse"
            st.metric("Utilidad Real", f"${utilidad_real:,.0f}", f"{margen:.1f}%", delta_color=delta_color)

        # Desglose de costos
        with st.expander("📋 Ver desglose de costos del mes"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**Costos Operativos:**")
                st.write(f"• Horas alistamiento/admin: ${float(costo_horas):,.0f}")
                st.write(f"• Labores (pegado/transporte): ${float(costo_labores):,.0f}")
                st.write(f"• Subsidio transporte: ${float(costo_subsidios):,.0f}")
                st.write(f"• Mensajeros/Entregas: ${float(costo_mensajeros):,.0f}")
                st.write(f"• Otros gastos: ${float(otros_gastos):,.0f}")
                st.markdown(f"**Subtotal Operativo: ${costo_operativo:,.0f}**")
            with col2:
                st.markdown("**Nómina Administrativa:**")
                if costo_nomina > 0:
                    st.write(f"• Salarios + Aux.Transp: ${nomina_base:,.0f}")
                    if nomina_aux_no_sal > 0:
                        st.write(f"• Auxilios No Salariales: ${nomina_aux_no_sal:,.0f}")
                    st.write(f"• Seguridad Social: ${nomina_seg_social:,.0f}")
                    st.write(f"• Provisiones: ${nomina_provisiones:,.0f}")
                    st.markdown(f"**Subtotal Nómina: ${costo_nomina:,.0f}**")
                else:
                    st.warning("Sin provisiones generadas")
            with col3:
                st.markdown("**Resumen:**")
                st.write(f"• Costos Operativos: ${costo_operativo:,.0f}")
                st.write(f"• Nómina Administrativa: ${costo_nomina:,.0f}")
                st.markdown("---")
                st.markdown(f"**COSTO TOTAL: ${costo_total_real:,.0f}**")

        if entregados == 0 and devoluciones == 0:
            st.warning("⚠️ No hay entregas/devoluciones registradas este mes. Cargue las gestiones desde 'Gestión de Pagos'.")
    else:
        st.info("No hay órdenes registradas este mes")

        # Mostrar costos aunque no haya órdenes
        if costo_total_real > 0:
            with st.expander("📋 Ver costos del mes (sin órdenes)"):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Costos Operativos:**")
                    st.write(f"• Horas alistamiento/admin: ${float(costo_horas):,.0f}")
                    st.write(f"• Labores: ${float(costo_labores):,.0f}")
                    st.write(f"• Subsidio transporte: ${float(costo_subsidios):,.0f}")
                    st.write(f"• Mensajeros: ${float(costo_mensajeros):,.0f}")
                    st.write(f"• Otros gastos: ${float(otros_gastos):,.0f}")
                with col2:
                    st.markdown("**Nómina Administrativa:**")
                    if costo_nomina > 0:
                        st.write(f"• Salarios + Auxilio: ${nomina_base:,.0f}")
                        st.write(f"• Seguridad Social: ${nomina_seg_social:,.0f}")
                        st.write(f"• Provisiones: ${nomina_provisiones:,.0f}")
                        st.markdown(f"**Total Nómina: ${costo_nomina:,.0f}**")
                st.markdown(f"**COSTO TOTAL DEL MES: ${costo_total_real:,.0f}**")

except Exception as e:
    st.error(f"Error cargando resumen: {e}")

st.divider()

# =====================================================
# CUENTAS POR COBRAR/PAGAR
# =====================================================

col1, col2 = st.columns(2)

with col1:
    st.subheader("💵 Cuentas por Cobrar")

    try:
        cursor.execute("""
            SELECT
                numero_factura,
                cliente,
                fecha_vencimiento,
                saldo_pendiente,
                clasificacion
            FROM vista_cuentas_por_cobrar
            ORDER BY fecha_vencimiento
            LIMIT 5
        """)

        cuentas_cobrar = cursor.fetchall()

        if cuentas_cobrar:
            for cuenta in cuentas_cobrar:
                venc = cuenta['fecha_vencimiento'].strftime('%d/%m/%Y')
                clasificacion = cuenta['clasificacion']
                color = "🔴" if clasificacion == "VENCIDA" else "🟡" if clasificacion == "POR VENCER" else "🟢"

                st.write(f"{color} **{cuenta['numero_factura']}** - ${cuenta['saldo_pendiente']:,.0f} - Vence: {venc}")
        else:
            st.success("✅ No hay cuentas pendientes")

    except Exception as e:
        st.error(f"Error: {e}")

with col2:
    st.subheader("💸 Cuentas por Pagar")

    try:
        from datetime import date, timedelta

        cuentas_pagar = []

        # 1. Facturas de transporte pendientes
        try:
            cursor.execute("""
                SELECT ft.numero_factura as referencia, p.nombre_completo as acreedor,
                       ft.fecha_vencimiento, ft.monto_total as monto
                FROM facturas_transporte ft
                JOIN personal p ON ft.courrier_id = p.id
                WHERE ft.estado = 'pendiente'
                ORDER BY ft.fecha_vencimiento
            """)
            for row in cursor.fetchall():
                cuentas_pagar.append(row)
        except Exception:
            pass

        # 2. Facturas recibidas de proveedores pendientes
        try:
            cursor.execute("""
                SELECT fr.numero_factura as referencia, p.nombre_completo as acreedor,
                       fr.fecha_vencimiento, fr.saldo_pendiente as monto
                FROM facturas_recibidas fr
                JOIN personal p ON fr.personal_id = p.id
                WHERE fr.estado NOT IN ('pagada', 'anulada')
                ORDER BY fr.fecha_vencimiento
            """)
            for row in cursor.fetchall():
                cuentas_pagar.append(row)
        except Exception:
            pass

        # 3. Pagos operativos mensuales pendientes
        try:
            cursor.execute("""
                SELECT
                    CONCAT(UPPER(tipo), ' ', periodo_mes, '/', periodo_anio) as referencia,
                    tipo as acreedor,
                    fecha_vencimiento, monto_total as monto
                FROM pagos_operativos_mensuales
                WHERE estado = 'pendiente'
                ORDER BY fecha_vencimiento
            """)
            for row in cursor.fetchall():
                cuentas_pagar.append(row)
        except Exception:
            pass

        # 4. Gastos administrativos pendientes
        try:
            cursor.execute("""
                SELECT descripcion as referencia, COALESCE(proveedor, categoria) as acreedor,
                       fecha as fecha_vencimiento, monto
                FROM gastos_administrativos
                WHERE estado = 'pendiente'
                ORDER BY fecha
            """)
            for row in cursor.fetchall():
                cuentas_pagar.append(row)
        except Exception:
            pass

        # Ordenar por fecha de vencimiento y mostrar top 5
        cuentas_pagar.sort(key=lambda x: x['fecha_vencimiento'] if x['fecha_vencimiento'] else date.max)

        if cuentas_pagar:
            total_por_pagar = 0
            for cuenta in cuentas_pagar[:5]:
                monto = float(cuenta['monto'] or 0)
                total_por_pagar += monto
                if cuenta['fecha_vencimiento']:
                    venc = cuenta['fecha_vencimiento'].strftime('%d/%m/%Y')
                    dias = (cuenta['fecha_vencimiento'] - date.today()).days
                    if dias < 0:
                        color = "🔴"
                    elif dias <= 7:
                        color = "🟡"
                    else:
                        color = "🟢"
                else:
                    venc = "Sin fecha"
                    color = "⚪"

                st.write(f"{color} **{cuenta['referencia']}** - {cuenta['acreedor']} - ${monto:,.0f} - Vence: {venc}")

            if len(cuentas_pagar) > 5:
                st.caption(f"... y {len(cuentas_pagar) - 5} más")

            total_general = sum(float(c['monto'] or 0) for c in cuentas_pagar)
            st.metric("Total por Pagar", f"${total_general:,.0f}")
        else:
            st.success("✅ No hay cuentas pendientes")

    except Exception as e:
        st.error(f"Error: {e}")

# =====================================================
# PIE DE PÁGINA
# =====================================================

st.divider()
st.caption(f"Sistema Logística Agrivision © 2026 - {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# Cerrar cursor
if 'cursor' in locals():
    cursor.close()
