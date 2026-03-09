import streamlit as st
import pandas as pd
from datetime import date, timedelta
from decimal import Decimal
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_connection import conectar_logistica


# Categorias de reservas
CATEGORIAS_RESERVA = {
    'nomina': 'Nomina',
    'impuestos': 'Impuestos',
    'proveedores': 'Proveedores',
    'servicios': 'Servicios Publicos',
    'arriendo': 'Arriendo',
    'contingencia': 'Fondo de Contingencia',
    'otros': 'Otros'
}

st.title("💸 Flujo de Caja")

conn = conectar_logistica()
if not conn:
    st.stop()

# Categorias de gastos fijos
CATEGORIAS_GASTOS_FIJOS = {
    'arriendo': 'Arriendo',
    'servicios_agua': 'Agua',
    'servicios_luz': 'Luz/Energia',
    'servicios_gas': 'Gas',
    'internet': 'Internet/Telefonia',
    'seguros': 'Seguros/Polizas',
    'software': 'Software/Suscripciones',
    'contabilidad': 'Contabilidad',
    'seguridad': 'Vigilancia/Seguridad',
    'aseo': 'Aseo/Cafeteria',
    'otros': 'Otros'
}

# Crear tablas si no existen
try:
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reservas_dinero (
            id INT AUTO_INCREMENT PRIMARY KEY,
            fecha_creacion DATE NOT NULL,
            fecha_programada DATE,
            categoria VARCHAR(50) NOT NULL,
            descripcion VARCHAR(255) NOT NULL,
            monto DECIMAL(15,2) NOT NULL,
            estado ENUM('activa', 'liberada', 'ejecutada') DEFAULT 'activa',
            fecha_liberacion DATE,
            observaciones TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos_fijos_mensuales (
            id INT AUTO_INCREMENT PRIMARY KEY,
            categoria VARCHAR(50) NOT NULL,
            descripcion VARCHAR(255) NOT NULL,
            monto DECIMAL(15,2) NOT NULL,
            dia_pago INT DEFAULT 1,
            activo BOOLEAN DEFAULT TRUE,
            observaciones TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagos_gastos_fijos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            gasto_fijo_id INT NOT NULL,
            mes INT NOT NULL,
            anio INT NOT NULL,
            monto_pagado DECIMAL(15,2) NOT NULL,
            fecha_pago DATE NOT NULL,
            observaciones TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY unique_pago_mes (gasto_fijo_id, mes, anio)
        )
    """)
    conn.commit()
except Exception as e:
    st.error(f"Error creando tabla: {e}")

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Dashboard Flujo",
    "📅 Gastos Fijos Mensuales",
    "🔒 Reservas de Dinero",
    "📈 Proyeccion"
])

with tab1:
    st.subheader("Resumen de Flujo de Caja")

    cursor = conn.cursor(dictionary=True)

    # ===== INGRESOS ESPERADOS =====
    st.markdown("### 💵 Ingresos Esperados (Por Cobrar)")

    col1, col2, col3 = st.columns(3)

    # Facturas pendientes totales
    cursor.execute("""
        SELECT SUM(saldo_pendiente) as total
        FROM facturas_emitidas
        WHERE estado NOT IN ('pagada', 'anulada')
    """)
    total_por_cobrar = cursor.fetchone()['total'] or 0

    # Vencido
    cursor.execute("""
        SELECT SUM(saldo_pendiente) as total
        FROM facturas_emitidas
        WHERE estado = 'vencida'
    """)
    total_vencido = cursor.fetchone()['total'] or 0

    # Por vencer esta semana
    cursor.execute("""
        SELECT SUM(saldo_pendiente) as total
        FROM facturas_emitidas
        WHERE estado IN ('pendiente', 'parcial')
        AND fecha_vencimiento BETWEEN CURRENT_DATE AND DATE_ADD(CURRENT_DATE, INTERVAL 7 DAY)
    """)
    vence_semana = cursor.fetchone()['total'] or 0

    with col1:
        st.metric("Total Por Cobrar", f"${float(total_por_cobrar):,.0f}")
    with col2:
        st.metric("Vencido", f"${float(total_vencido):,.0f}", delta_color="inverse")
    with col3:
        st.metric("Vence Esta Semana", f"${float(vence_semana):,.0f}")

    # Detalle de facturas por cobrar
    with st.expander("Ver Detalle de Facturas Por Cobrar"):
        cursor.execute("""
            SELECT
                fe.numero_factura, c.nombre_empresa as cliente,
                fe.fecha_vencimiento, fe.saldo_pendiente, fe.estado
            FROM facturas_emitidas fe
            JOIN clientes c ON fe.cliente_id = c.id
            WHERE fe.estado NOT IN ('pagada', 'anulada')
            ORDER BY fe.fecha_vencimiento
        """)
        facturas = cursor.fetchall()

        if facturas:
            df_facturas = pd.DataFrame(facturas)
            df_facturas['fecha_vencimiento'] = pd.to_datetime(df_facturas['fecha_vencimiento']).dt.strftime('%d/%m/%Y')
            df_facturas['saldo_pendiente'] = df_facturas['saldo_pendiente'].apply(lambda x: f"${float(x):,.0f}")
            st.dataframe(df_facturas, use_container_width=True, hide_index=True)
        else:
            st.info("No hay facturas pendientes")

    st.divider()

    # ===== EGRESOS ESPERADOS =====
    st.markdown("### 💳 Egresos Esperados (Por Pagar)")

    # Determinar periodo de pago (lo del mes anterior se paga el 8 de este mes)
    hoy = date.today()
    if hoy.day < 8:
        # Aun no se ha pagado lo del mes anterior
        mes_pago_alistamiento = hoy.month - 1 if hoy.month > 1 else 12
        anio_pago_alistamiento = hoy.year if hoy.month > 1 else hoy.year - 1
        fecha_pago = date(hoy.year, hoy.month, 8)
        periodo_label = f"Pago 8/{hoy.month:02d} (trabajo de {mes_pago_alistamiento:02d}/{anio_pago_alistamiento})"
    else:
        # Ya se pago lo del mes anterior, mostrar lo del mes actual para el proximo pago
        mes_pago_alistamiento = hoy.month
        anio_pago_alistamiento = hoy.year
        mes_siguiente = hoy.month + 1 if hoy.month < 12 else 1
        anio_siguiente = hoy.year if hoy.month < 12 else hoy.year + 1
        fecha_pago = date(anio_siguiente, mes_siguiente, 8)
        periodo_label = f"Pago 8/{mes_siguiente:02d} (trabajo de {mes_pago_alistamiento:02d}/{anio_pago_alistamiento})"

    st.info(f"📅 Proximo pago de nomina operativa: **{periodo_label}**")

    col1, col2, col3, col4 = st.columns(4)

    # Gastos administrativos pendientes
    cursor.execute("""
        SELECT SUM(monto) as total
        FROM gastos_administrativos
        WHERE estado = 'pendiente'
    """)
    gastos_pendientes = cursor.fetchone()['total'] or 0

    # Gastos fijos mensuales PENDIENTES (no pagados este mes)
    cursor.execute("""
        SELECT COALESCE(SUM(gf.monto), 0) as total
        FROM gastos_fijos_mensuales gf
        LEFT JOIN pagos_gastos_fijos pgf ON gf.id = pgf.gasto_fijo_id
            AND pgf.mes = %s AND pgf.anio = %s
        WHERE gf.activo = TRUE AND pgf.id IS NULL
    """, (hoy.month, hoy.year))
    gastos_fijos_mes = cursor.fetchone()['total'] or 0

    # Reservas activas
    cursor.execute("""
        SELECT SUM(monto) as total
        FROM reservas_dinero
        WHERE estado = 'activa'
    """)
    reservas_activas = cursor.fetchone()['total'] or 0

    with col1:
        st.metric("Gastos Admin Pendientes", f"${float(gastos_pendientes):,.0f}")
    with col2:
        st.metric("Gastos Fijos Pend.", f"${float(gastos_fijos_mes):,.0f}")
    with col3:
        st.metric("Reservas Activas", f"${float(reservas_activas):,.0f}")

    # ===== PAGOS A ALISTAMIENTO (registro_horas + registro_labores) =====
    # Horas de alistamiento del periodo
    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) as total
        FROM registro_horas
        WHERE MONTH(fecha) = %s AND YEAR(fecha) = %s
    """, (mes_pago_alistamiento, anio_pago_alistamiento))
    total_horas_alistamiento = float(cursor.fetchone()['total'] or 0)

    # Labores (pegado, transporte) del periodo
    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) as total
        FROM registro_labores
        WHERE MONTH(fecha) = %s AND YEAR(fecha) = %s
    """, (mes_pago_alistamiento, anio_pago_alistamiento))
    total_labores = float(cursor.fetchone()['total'] or 0)

    total_alistamiento = total_horas_alistamiento + total_labores

    # ===== PAGOS A MENSAJEROS (gestiones_mensajero) =====
    cursor.execute("""
        SELECT COALESCE(SUM(valor_total), 0) as total
        FROM gestiones_mensajero
        WHERE MONTH(fecha_registro) = %s AND YEAR(fecha_registro) = %s
    """, (mes_pago_alistamiento, anio_pago_alistamiento))
    total_mensajeros = float(cursor.fetchone()['total'] or 0)

    with col4:
        total_nomina_operativa = total_alistamiento + total_mensajeros
        st.metric("Nomina Operativa Pend.", f"${total_nomina_operativa:,.0f}")

    # Segunda fila de metricas
    st.markdown("#### 👷 Detalle Nomina Operativa")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Horas Alistamiento", f"${total_horas_alistamiento:,.0f}")
    with col2:
        st.metric("Labores (Pegado/Transp)", f"${total_labores:,.0f}")
    with col3:
        st.metric("Gestiones Mensajeros", f"${total_mensajeros:,.0f}")
    with col4:
        total_egresos = float(gastos_pendientes) + float(gastos_fijos_mes) + float(reservas_activas) + total_nomina_operativa
        st.metric("TOTAL EGRESOS", f"${total_egresos:,.0f}", delta_color="inverse")

    # Detalle de alistamiento
    with st.expander(f"Ver Detalle Alistamiento ({mes_pago_alistamiento:02d}/{anio_pago_alistamiento})"):
        # Resumen por persona - Horas
        cursor.execute("""
            SELECT p.nombre_completo, SUM(rh.horas_trabajadas) as horas, SUM(rh.total) as total
            FROM registro_horas rh
            JOIN personal p ON rh.personal_id = p.id
            WHERE MONTH(rh.fecha) = %s AND YEAR(rh.fecha) = %s
            GROUP BY p.id, p.nombre_completo
            ORDER BY total DESC
        """, (mes_pago_alistamiento, anio_pago_alistamiento))
        detalle_horas = cursor.fetchall()

        if detalle_horas:
            st.markdown("**Horas de Alistamiento:**")
            df_horas = pd.DataFrame(detalle_horas)
            df_horas['horas'] = df_horas['horas'].apply(lambda x: f"{float(x):.2f}h")
            df_horas['total'] = df_horas['total'].apply(lambda x: f"${float(x):,.0f}")
            df_horas.columns = ['Nombre', 'Horas', 'Total']
            st.dataframe(df_horas, use_container_width=True, hide_index=True)

        # Resumen por persona - Labores
        cursor.execute("""
            SELECT p.nombre_completo, rl.tipo_labor, SUM(rl.cantidad) as cantidad, SUM(rl.total) as total
            FROM registro_labores rl
            JOIN personal p ON rl.personal_id = p.id
            WHERE MONTH(rl.fecha) = %s AND YEAR(rl.fecha) = %s
            GROUP BY p.id, p.nombre_completo, rl.tipo_labor
            ORDER BY total DESC
        """, (mes_pago_alistamiento, anio_pago_alistamiento))
        detalle_labores = cursor.fetchall()

        if detalle_labores:
            st.markdown("**Labores (Pegado/Transporte):**")
            df_labores = pd.DataFrame(detalle_labores)
            df_labores['tipo_labor'] = df_labores['tipo_labor'].apply(lambda x: {
                'pegado_guia': 'Pegado', 'transporte_completo': 'Transp. Completo', 'medio_transporte': 'Medio Transp.'
            }.get(x, x))
            df_labores['total'] = df_labores['total'].apply(lambda x: f"${float(x):,.0f}")
            df_labores.columns = ['Nombre', 'Tipo', 'Cantidad', 'Total']
            st.dataframe(df_labores, use_container_width=True, hide_index=True)

        if not detalle_horas and not detalle_labores:
            st.info("No hay registros de alistamiento para este periodo")

    # Detalle de mensajeros
    with st.expander(f"Ver Detalle Mensajeros ({mes_pago_alistamiento:02d}/{anio_pago_alistamiento})"):
        cursor.execute("""
            SELECT
                gm.cod_mensajero,
                COALESCE(p.nombre_completo, 'No asignado') as nombre,
                COUNT(*) as gestiones,
                SUM(gm.total_seriales) as seriales,
                SUM(gm.valor_total) as total
            FROM gestiones_mensajero gm
            LEFT JOIN personal p ON gm.mensajero_id = p.id
            WHERE MONTH(gm.fecha_registro) = %s AND YEAR(gm.fecha_registro) = %s
            GROUP BY gm.cod_mensajero, p.nombre_completo
            ORDER BY total DESC
        """, (mes_pago_alistamiento, anio_pago_alistamiento))
        detalle_mensajeros = cursor.fetchall()

        if detalle_mensajeros:
            df_mensajeros = pd.DataFrame(detalle_mensajeros)
            df_mensajeros['total'] = df_mensajeros['total'].apply(lambda x: f"${float(x):,.0f}")
            df_mensajeros.columns = ['Codigo', 'Nombre', 'Gestiones', 'Seriales', 'Total']
            st.dataframe(df_mensajeros, use_container_width=True, hide_index=True)
        else:
            st.info("No hay gestiones de mensajeros para este periodo")

    # Detalle de gastos pendientes
    with st.expander("Ver Detalle de Gastos Administrativos Pendientes"):
        cursor.execute("""
            SELECT fecha, categoria, descripcion, monto
            FROM gastos_administrativos
            WHERE estado = 'pendiente'
            ORDER BY fecha
        """)
        gastos = cursor.fetchall()

        if gastos:
            df_gastos = pd.DataFrame(gastos)
            df_gastos['fecha'] = pd.to_datetime(df_gastos['fecha']).dt.strftime('%d/%m/%Y')
            df_gastos['monto'] = df_gastos['monto'].apply(lambda x: f"${float(x):,.0f}")
            st.dataframe(df_gastos, use_container_width=True, hide_index=True)
        else:
            st.info("No hay gastos pendientes")

    # Detalle de gastos fijos mensuales (pendientes y pagados)
    with st.expander("Ver Detalle de Gastos Fijos Mensuales"):
        cursor.execute("""
            SELECT gf.categoria, gf.descripcion, gf.dia_pago, gf.monto,
                   CASE WHEN pgf.id IS NOT NULL THEN 'Pagado' ELSE 'Pendiente' END as estado
            FROM gastos_fijos_mensuales gf
            LEFT JOIN pagos_gastos_fijos pgf ON gf.id = pgf.gasto_fijo_id
                AND pgf.mes = %s AND pgf.anio = %s
            WHERE gf.activo = TRUE
            ORDER BY pgf.id IS NOT NULL, gf.dia_pago, gf.categoria
        """, (hoy.month, hoy.year))
        gastos_fijos = cursor.fetchall()

        if gastos_fijos:
            df_fijos = pd.DataFrame(gastos_fijos)
            df_fijos['categoria'] = df_fijos['categoria'].apply(lambda x: CATEGORIAS_GASTOS_FIJOS.get(x, x))
            df_fijos['dia_pago'] = df_fijos['dia_pago'].apply(lambda x: f"Dia {x}")
            df_fijos['monto'] = df_fijos['monto'].apply(lambda x: f"${float(x):,.0f}")
            df_fijos['estado'] = df_fijos['estado'].apply(lambda x: f"✅ {x}" if x == 'Pagado' else f"⏳ {x}")
            df_fijos.columns = ['Categoria', 'Descripcion', 'Dia Pago', 'Monto', 'Estado']
            st.dataframe(df_fijos, use_container_width=True, hide_index=True)
        else:
            st.info("No hay gastos fijos configurados. Ve a la pestaña 'Gastos Fijos Mensuales' para agregar.")

    st.divider()

    # ===== BALANCE =====
    st.markdown("### 📊 Balance Proyectado")

    balance = float(total_por_cobrar) - total_egresos

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Ingresos Esperados", f"${float(total_por_cobrar):,.0f}")
    with col2:
        st.metric("Gastos Fijos + Admin", f"${float(gastos_pendientes) + float(gastos_fijos_mes):,.0f}")
    with col3:
        st.metric("Nomina + Reservas", f"${total_nomina_operativa + float(reservas_activas):,.0f}")
    with col4:
        color = "normal" if balance >= 0 else "inverse"
        st.metric("Balance Proyectado", f"${balance:,.0f}", delta=f"{'Positivo' if balance >= 0 else 'Negativo'}", delta_color=color)

    if balance < 0:
        st.error(f"⚠️ ALERTA: El balance proyectado es negativo. Considera reservar fondos o buscar financiamiento por ${abs(balance):,.0f}")
    elif balance < total_egresos * 0.2:
        st.warning(f"⚠️ El margen es bajo. Considera crear reservas de contingencia.")
    else:
        st.success("✅ El flujo de caja proyectado es saludable")

with tab2:
    st.subheader("Gastos Fijos Mensuales")
    st.info("📅 Configura aqui los gastos que se repiten cada mes (arriendo, servicios, etc.)")

    cursor = conn.cursor(dictionary=True)

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 📋 Gastos Fijos Activos")

        cursor.execute("""
            SELECT id, categoria, descripcion, monto, dia_pago
            FROM gastos_fijos_mensuales
            WHERE activo = TRUE
            ORDER BY dia_pago, categoria
        """)
        gastos_fijos_lista = cursor.fetchall()

        if gastos_fijos_lista:
            # Obtener mes/año actual
            hoy_fijos = date.today()
            mes_actual = hoy_fijos.month
            anio_actual = hoy_fijos.year

            # Contar pagados vs pendientes del mes
            cursor.execute("""
                SELECT COUNT(*) as pagados
                FROM pagos_gastos_fijos
                WHERE mes = %s AND anio = %s
            """, (mes_actual, anio_actual))
            pagados_mes = cursor.fetchone()['pagados']
            pendientes_mes = len(gastos_fijos_lista) - pagados_mes

            total_fijos = sum([float(g['monto']) for g in gastos_fijos_lista])

            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                st.metric("Total Mensual", f"${total_fijos:,.0f}")
            with col_m2:
                st.metric("Pagados", f"{pagados_mes}/{len(gastos_fijos_lista)}")
            with col_m3:
                st.metric("Pendientes", pendientes_mes, delta_color="inverse" if pendientes_mes > 0 else "off")

            st.divider()

            for g in gastos_fijos_lista:
                cat_nombre = CATEGORIAS_GASTOS_FIJOS.get(g['categoria'], g['categoria'])

                # Verificar si está pagado este mes
                cursor.execute("""
                    SELECT id, fecha_pago, monto_pagado
                    FROM pagos_gastos_fijos
                    WHERE gasto_fijo_id = %s AND mes = %s AND anio = %s
                """, (g['id'], mes_actual, anio_actual))
                pago_mes = cursor.fetchone()

                if pago_mes:
                    estado_icon = "✅"
                    estado_texto = f"Pagado el {pago_mes['fecha_pago'].strftime('%d/%m/%Y')}"
                else:
                    estado_icon = "⏳"
                    estado_texto = "Pendiente"

                with st.expander(f"{estado_icon} Dia {g['dia_pago']} - {cat_nombre} - ${float(g['monto']):,.0f} - {estado_texto}"):
                    st.write(f"**Descripcion:** {g['descripcion']}")
                    st.write(f"**Categoria:** {cat_nombre}")
                    st.write(f"**Dia de pago:** {g['dia_pago']} de cada mes")
                    st.write(f"**Monto:** ${float(g['monto']):,.0f}")

                    st.divider()

                    # Estado de pago del mes actual
                    if pago_mes:
                        st.success(f"✅ Pagado el {pago_mes['fecha_pago'].strftime('%d/%m/%Y')} - ${float(pago_mes['monto_pagado']):,.0f}")

                        if st.button("↩️ Desmarcar pago", key=f"desmarcar_{g['id']}"):
                            cursor.execute("DELETE FROM pagos_gastos_fijos WHERE id = %s", (pago_mes['id'],))
                            conn.commit()
                            st.success("Pago desmarcado")
                            st.rerun()
                    else:
                        st.warning(f"⏳ Pendiente de pago - Mes {mes_actual:02d}/{anio_actual}")

                        col_p1, col_p2 = st.columns(2)
                        with col_p1:
                            fecha_pago_input = st.date_input("Fecha de pago", value=date.today(), key=f"fecha_pago_{g['id']}")
                        with col_p2:
                            monto_pago_input = st.number_input("Monto pagado", value=float(g['monto']), min_value=0.0, step=1000.0, key=f"monto_pago_{g['id']}")

                        if st.button("✅ Marcar como Pagado", key=f"pagar_{g['id']}", type="primary"):
                            try:
                                cursor.execute("""
                                    INSERT INTO pagos_gastos_fijos (gasto_fijo_id, mes, anio, monto_pagado, fecha_pago)
                                    VALUES (%s, %s, %s, %s, %s)
                                """, (g['id'], mes_actual, anio_actual, monto_pago_input, fecha_pago_input))
                                conn.commit()
                                st.success("Pago registrado")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

                    st.divider()

                    col_a, col_b = st.columns(2)

                    with col_a:
                        if st.button("🗑️ Eliminar gasto fijo", key=f"eliminar_fijo_{g['id']}"):
                            cursor.execute("UPDATE gastos_fijos_mensuales SET activo = FALSE WHERE id = %s", (g['id'],))
                            conn.commit()
                            st.success("Gasto fijo eliminado")
                            st.rerun()

                    with col_b:
                        # Editar monto
                        nuevo_monto = st.number_input(
                            "Nuevo monto mensual",
                            value=float(g['monto']),
                            min_value=0.0,
                            step=1000.0,
                            key=f"monto_fijo_{g['id']}"
                        )
                        if st.button("💾 Actualizar monto", key=f"actualizar_fijo_{g['id']}"):
                            cursor.execute("UPDATE gastos_fijos_mensuales SET monto = %s WHERE id = %s", (nuevo_monto, g['id']))
                            conn.commit()
                            st.success("Monto actualizado")
                            st.rerun()
        else:
            st.info("No hay gastos fijos configurados")

    with col2:
        st.markdown("### ➕ Nuevo Gasto Fijo")

        with st.form("form_gasto_fijo"):
            categoria_fijo = st.selectbox(
                "Categoria",
                options=list(CATEGORIAS_GASTOS_FIJOS.keys()),
                format_func=lambda x: CATEGORIAS_GASTOS_FIJOS[x]
            )
            descripcion_fijo = st.text_input("Descripcion", placeholder="Ej: Arriendo bodega")
            monto_fijo = st.number_input("Monto Mensual", min_value=0.0, step=10000.0, format="%.2f")
            dia_pago_fijo = st.number_input("Dia de Pago", min_value=1, max_value=31, value=1, help="Dia del mes en que se paga")
            observaciones_fijo = st.text_area("Observaciones (opcional)", height=80)

            submitted_fijo = st.form_submit_button("📅 Agregar Gasto Fijo", type="primary", use_container_width=True)

            if submitted_fijo:
                if not descripcion_fijo:
                    st.error("Ingresa una descripcion")
                elif monto_fijo <= 0:
                    st.error("El monto debe ser mayor a 0")
                else:
                    try:
                        cursor.execute("""
                            INSERT INTO gastos_fijos_mensuales
                            (categoria, descripcion, monto, dia_pago, observaciones)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (categoria_fijo, descripcion_fijo, monto_fijo, dia_pago_fijo, observaciones_fijo or None))
                        conn.commit()
                        st.success("Gasto fijo agregado exitosamente")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    st.divider()

    # Resumen por categoria
    st.markdown("### 📊 Resumen por Categoria")

    cursor.execute("""
        SELECT categoria, COUNT(*) as cantidad, SUM(monto) as total
        FROM gastos_fijos_mensuales
        WHERE activo = TRUE
        GROUP BY categoria
        ORDER BY total DESC
    """)
    resumen_fijos = cursor.fetchall()

    if resumen_fijos:
        df_resumen = pd.DataFrame(resumen_fijos)
        df_resumen['categoria'] = df_resumen['categoria'].apply(lambda x: CATEGORIAS_GASTOS_FIJOS.get(x, x))
        df_resumen['total'] = df_resumen['total'].apply(lambda x: f"${float(x):,.0f}")
        df_resumen.columns = ['Categoria', 'Cantidad', 'Total Mensual']
        st.dataframe(df_resumen, use_container_width=True, hide_index=True)

        # Calendario de pagos del mes
        st.markdown("### 📆 Calendario de Pagos del Mes")

        hoy_cal = date.today()
        mes_cal = hoy_cal.month
        anio_cal = hoy_cal.year

        cursor.execute("""
            SELECT gf.id, gf.dia_pago, gf.categoria, gf.descripcion, gf.monto,
                   pgf.fecha_pago as pagado_fecha
            FROM gastos_fijos_mensuales gf
            LEFT JOIN pagos_gastos_fijos pgf ON gf.id = pgf.gasto_fijo_id
                AND pgf.mes = %s AND pgf.anio = %s
            WHERE gf.activo = TRUE
            ORDER BY gf.dia_pago
        """, (mes_cal, anio_cal))
        calendario = cursor.fetchall()

        if calendario:
            for pago in calendario:
                cat_nombre = CATEGORIAS_GASTOS_FIJOS.get(pago['categoria'], pago['categoria'])

                if pago['pagado_fecha']:
                    icon = "✅"  # Pagado
                    estado = f"(Pagado {pago['pagado_fecha'].strftime('%d/%m')})"
                else:
                    fecha_limite = date(hoy_cal.year, hoy_cal.month, min(pago['dia_pago'], 28))
                    if fecha_limite < hoy_cal:
                        icon = "🔴"  # Vencido sin pagar
                        estado = "(VENCIDO)"
                    elif fecha_limite == hoy_cal:
                        icon = "⚠️"  # Hoy
                        estado = "(HOY)"
                    else:
                        icon = "⏳"  # Pendiente
                        estado = ""

                st.write(f"{icon} **Dia {pago['dia_pago']}** - {cat_nombre}: {pago['descripcion']} - ${float(pago['monto']):,.0f} {estado}")
    else:
        st.info("No hay gastos fijos para mostrar resumen")

with tab3:
    st.subheader("Gestion de Reservas de Dinero")

    cursor = conn.cursor(dictionary=True)

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 🔒 Reservas Activas")

        cursor.execute("""
            SELECT id, fecha_creacion, fecha_programada, categoria, descripcion, monto
            FROM reservas_dinero
            WHERE estado = 'activa'
            ORDER BY fecha_programada, fecha_creacion
        """)
        reservas = cursor.fetchall()

        if reservas:
            total_reservado = sum([float(r['monto']) for r in reservas])
            st.metric("Total Reservado", f"${total_reservado:,.0f}")

            st.divider()

            for r in reservas:
                cat_nombre = CATEGORIAS_RESERVA.get(r['categoria'], r['categoria'])
                fecha_prog = r['fecha_programada'].strftime('%d/%m/%Y') if r['fecha_programada'] else 'Sin fecha'

                with st.expander(f"🔒 {cat_nombre} - ${float(r['monto']):,.0f} - {fecha_prog}"):
                    st.write(f"**Descripcion:** {r['descripcion']}")
                    st.write(f"**Creada:** {r['fecha_creacion'].strftime('%d/%m/%Y')}")
                    st.write(f"**Programada para:** {fecha_prog}")

                    col_a, col_b, col_c = st.columns(3)

                    with col_a:
                        if st.button("✅ Ejecutar", key=f"ejecutar_{r['id']}", help="Marcar como ejecutada (pago realizado)"):
                            cursor.execute("""
                                UPDATE reservas_dinero
                                SET estado = 'ejecutada', fecha_liberacion = %s
                                WHERE id = %s
                            """, (date.today(), r['id']))
                            conn.commit()
                            st.success("Reserva ejecutada")
                            st.rerun()

                    with col_b:
                        if st.button("🔓 Liberar", key=f"liberar_{r['id']}", help="Liberar fondos (cancelar reserva)"):
                            cursor.execute("""
                                UPDATE reservas_dinero
                                SET estado = 'liberada', fecha_liberacion = %s
                                WHERE id = %s
                            """, (date.today(), r['id']))
                            conn.commit()
                            st.success("Reserva liberada")
                            st.rerun()

                    with col_c:
                        if st.button("🗑️ Eliminar", key=f"eliminar_res_{r['id']}"):
                            cursor.execute("DELETE FROM reservas_dinero WHERE id = %s", (r['id'],))
                            conn.commit()
                            st.success("Reserva eliminada")
                            st.rerun()
        else:
            st.info("No hay reservas activas")

    with col2:
        st.markdown("### ➕ Nueva Reserva")

        with st.form("form_reserva"):
            categoria = st.selectbox(
                "Categoria",
                options=list(CATEGORIAS_RESERVA.keys()),
                format_func=lambda x: CATEGORIAS_RESERVA[x]
            )
            descripcion = st.text_input("Descripcion", placeholder="Ej: Pago nomina enero")
            monto = st.number_input("Monto a Reservar", min_value=0.0, step=10000.0, format="%.2f")
            fecha_programada = st.date_input("Fecha Programada (opcional)", value=None)
            observaciones = st.text_area("Observaciones", height=80)

            submitted = st.form_submit_button("🔒 Crear Reserva", type="primary", use_container_width=True)

            if submitted:
                if not descripcion:
                    st.error("Ingresa una descripcion")
                elif monto <= 0:
                    st.error("El monto debe ser mayor a 0")
                else:
                    try:
                        cursor.execute("""
                            INSERT INTO reservas_dinero
                            (fecha_creacion, fecha_programada, categoria, descripcion, monto, observaciones)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (date.today(), fecha_programada, categoria, descripcion, monto, observaciones or None))
                        conn.commit()
                        st.success("Reserva creada exitosamente")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    st.divider()

    # Historial de reservas
    st.markdown("### 📋 Historial de Reservas")

    col1, col2 = st.columns(2)
    with col1:
        filtro_estado = st.selectbox("Estado", ['todas', 'activa', 'ejecutada', 'liberada'],
                                      format_func=lambda x: x.capitalize())

    if filtro_estado == 'todas':
        cursor.execute("""
            SELECT fecha_creacion, categoria, descripcion, monto, estado, fecha_liberacion
            FROM reservas_dinero
            ORDER BY fecha_creacion DESC
            LIMIT 50
        """)
    else:
        cursor.execute("""
            SELECT fecha_creacion, categoria, descripcion, monto, estado, fecha_liberacion
            FROM reservas_dinero
            WHERE estado = %s
            ORDER BY fecha_creacion DESC
            LIMIT 50
        """, (filtro_estado,))

    historial = cursor.fetchall()

    if historial:
        df_hist = pd.DataFrame(historial)
        df_hist['fecha_creacion'] = pd.to_datetime(df_hist['fecha_creacion']).dt.strftime('%d/%m/%Y')
        df_hist['fecha_liberacion'] = df_hist['fecha_liberacion'].apply(
            lambda x: x.strftime('%d/%m/%Y') if x else '-'
        )
        df_hist['categoria'] = df_hist['categoria'].apply(lambda x: CATEGORIAS_RESERVA.get(x, x))
        df_hist['monto'] = df_hist['monto'].apply(lambda x: f"${float(x):,.0f}")
        df_hist['estado'] = df_hist['estado'].apply(lambda x: {'activa': '🔒', 'ejecutada': '✅', 'liberada': '🔓'}.get(x, '') + ' ' + x)
        df_hist.columns = ['Creacion', 'Categoria', 'Descripcion', 'Monto', 'Estado', 'Fecha Lib/Ejec']
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
    else:
        st.info("No hay historial de reservas")

with tab4:
    st.subheader("Proyeccion de Flujo de Caja")

    cursor = conn.cursor(dictionary=True)

    # Selector de periodo
    col1, col2 = st.columns(2)
    with col1:
        periodo = st.selectbox("Periodo de Proyeccion", ['Proximas 4 semanas', 'Proximos 3 meses'])

    st.divider()

    if periodo == 'Proximas 4 semanas':
        # Proyeccion semanal
        semanas = []
        hoy = date.today()

        for i in range(4):
            inicio_semana = hoy + timedelta(days=i*7)
            fin_semana = inicio_semana + timedelta(days=6)

            # Ingresos esperados (facturas que vencen en esta semana)
            cursor.execute("""
                SELECT COALESCE(SUM(saldo_pendiente), 0) as total
                FROM facturas_emitidas
                WHERE estado IN ('pendiente', 'parcial')
                AND fecha_vencimiento BETWEEN %s AND %s
            """, (inicio_semana, fin_semana))
            ingresos = float(cursor.fetchone()['total'])

            # Reservas programadas para esta semana
            cursor.execute("""
                SELECT COALESCE(SUM(monto), 0) as total
                FROM reservas_dinero
                WHERE estado = 'activa'
                AND fecha_programada BETWEEN %s AND %s
            """, (inicio_semana, fin_semana))
            egresos_reservas = float(cursor.fetchone()['total'])

            semanas.append({
                'Semana': f"Sem {i+1}: {inicio_semana.strftime('%d/%m')} - {fin_semana.strftime('%d/%m')}",
                'Ingresos Esp.': ingresos,
                'Egresos Reserv.': egresos_reservas,
                'Balance': ingresos - egresos_reservas
            })

        df_semanas = pd.DataFrame(semanas)

        # Grafico
        st.markdown("### Flujo Semanal")

        chart_data = df_semanas.set_index('Semana')[['Ingresos Esp.', 'Egresos Reserv.']]
        st.bar_chart(chart_data)

        # Tabla
        st.markdown("### Detalle")
        df_display = df_semanas.copy()
        df_display['Ingresos Esp.'] = df_display['Ingresos Esp.'].apply(lambda x: f"${x:,.0f}")
        df_display['Egresos Reserv.'] = df_display['Egresos Reserv.'].apply(lambda x: f"${x:,.0f}")
        df_display['Balance'] = df_display['Balance'].apply(lambda x: f"${x:,.0f}")
        st.dataframe(df_display, use_container_width=True, hide_index=True)

    else:
        # Proyeccion mensual
        meses = []
        hoy = date.today()

        for i in range(3):
            mes_actual = hoy.month + i
            anio_actual = hoy.year
            if mes_actual > 12:
                mes_actual -= 12
                anio_actual += 1

            # Ingresos esperados del mes
            cursor.execute("""
                SELECT COALESCE(SUM(saldo_pendiente), 0) as total
                FROM facturas_emitidas
                WHERE estado IN ('pendiente', 'parcial')
                AND MONTH(fecha_vencimiento) = %s AND YEAR(fecha_vencimiento) = %s
            """, (mes_actual, anio_actual))
            ingresos = float(cursor.fetchone()['total'])

            # Reservas del mes
            cursor.execute("""
                SELECT COALESCE(SUM(monto), 0) as total
                FROM reservas_dinero
                WHERE estado = 'activa'
                AND MONTH(fecha_programada) = %s AND YEAR(fecha_programada) = %s
            """, (mes_actual, anio_actual))
            egresos_reservas = float(cursor.fetchone()['total'])

            meses_nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                           "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

            meses.append({
                'Mes': f"{meses_nombres[mes_actual-1]} {anio_actual}",
                'Ingresos Esp.': ingresos,
                'Egresos Reserv.': egresos_reservas,
                'Balance': ingresos - egresos_reservas
            })

        df_meses = pd.DataFrame(meses)

        # Grafico
        st.markdown("### Flujo Mensual")

        chart_data = df_meses.set_index('Mes')[['Ingresos Esp.', 'Egresos Reserv.']]
        st.bar_chart(chart_data)

        # Tabla
        st.markdown("### Detalle")
        df_display = df_meses.copy()
        df_display['Ingresos Esp.'] = df_display['Ingresos Esp.'].apply(lambda x: f"${x:,.0f}")
        df_display['Egresos Reserv.'] = df_display['Egresos Reserv.'].apply(lambda x: f"${x:,.0f}")
        df_display['Balance'] = df_display['Balance'].apply(lambda x: f"${x:,.0f}")
        st.dataframe(df_display, use_container_width=True, hide_index=True)

    st.divider()

    # Alertas
    st.markdown("### ⚠️ Alertas de Flujo")

    alertas = []

    # Facturas vencidas
    cursor.execute("SELECT COUNT(*) as total FROM facturas_emitidas WHERE estado = 'vencida'")
    fact_vencidas = cursor.fetchone()['total']
    if fact_vencidas > 0:
        alertas.append(f"🔴 Hay {fact_vencidas} factura(s) vencida(s) pendiente(s) de cobro")

    # Reservas sin fecha
    cursor.execute("SELECT COUNT(*) as total FROM reservas_dinero WHERE estado = 'activa' AND fecha_programada IS NULL")
    res_sin_fecha = cursor.fetchone()['total']
    if res_sin_fecha > 0:
        alertas.append(f"🟡 Hay {res_sin_fecha} reserva(s) sin fecha programada")

    # Balance negativo proyectado
    cursor.execute("SELECT COALESCE(SUM(saldo_pendiente), 0) as ingresos FROM facturas_emitidas WHERE estado IN ('pendiente', 'parcial')")
    ingresos_total = float(cursor.fetchone()['ingresos'])

    cursor.execute("SELECT COALESCE(SUM(monto), 0) as egresos FROM reservas_dinero WHERE estado = 'activa'")
    egresos_reservas_total = float(cursor.fetchone()['egresos'])

    cursor.execute("SELECT COALESCE(SUM(monto), 0) as gastos FROM gastos_administrativos WHERE estado = 'pendiente'")
    gastos_total = float(cursor.fetchone()['gastos'])

    # Calcular nomina operativa pendiente (mes anterior o actual segun fecha)
    hoy_alerta = date.today()
    if hoy_alerta.day < 8:
        mes_nomina = hoy_alerta.month - 1 if hoy_alerta.month > 1 else 12
        anio_nomina = hoy_alerta.year if hoy_alerta.month > 1 else hoy_alerta.year - 1
    else:
        mes_nomina = hoy_alerta.month
        anio_nomina = hoy_alerta.year

    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) as total FROM registro_horas
        WHERE MONTH(fecha) = %s AND YEAR(fecha) = %s
    """, (mes_nomina, anio_nomina))
    nomina_horas = float(cursor.fetchone()['total'])

    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) as total FROM registro_labores
        WHERE MONTH(fecha) = %s AND YEAR(fecha) = %s
    """, (mes_nomina, anio_nomina))
    nomina_labores = float(cursor.fetchone()['total'])

    cursor.execute("""
        SELECT COALESCE(SUM(valor_total), 0) as total FROM gestiones_mensajero
        WHERE MONTH(fecha_registro) = %s AND YEAR(fecha_registro) = %s
    """, (mes_nomina, anio_nomina))
    nomina_mensajeros = float(cursor.fetchone()['total'])

    nomina_total = nomina_horas + nomina_labores + nomina_mensajeros

    # Gastos fijos mensuales PENDIENTES (no pagados este mes)
    cursor.execute("""
        SELECT COALESCE(SUM(gf.monto), 0) as total
        FROM gastos_fijos_mensuales gf
        LEFT JOIN pagos_gastos_fijos pgf ON gf.id = pgf.gasto_fijo_id
            AND pgf.mes = %s AND pgf.anio = %s
        WHERE gf.activo = TRUE AND pgf.id IS NULL
    """, (hoy_alerta.month, hoy_alerta.year))
    gastos_fijos_total = float(cursor.fetchone()['total'])

    egresos_totales_alerta = egresos_reservas_total + gastos_total + gastos_fijos_total + nomina_total

    if ingresos_total < egresos_totales_alerta:
        faltante = egresos_totales_alerta - ingresos_total
        alertas.append(f"🔴 Balance negativo proyectado: faltan ${faltante:,.0f}")

    if alertas:
        for alerta in alertas:
            if alerta.startswith("🔴"):
                st.error(alerta)
            else:
                st.warning(alerta)
    else:
        st.success("✅ No hay alertas de flujo de caja")

if 'cursor' in locals():
    cursor.close()
