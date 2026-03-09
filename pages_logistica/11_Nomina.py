import streamlit as st
import pandas as pd
from datetime import date, datetime
from decimal import Decimal
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_connection import conectar_logistica


def obtener_parametros_nomina(cursor):
    """Obtiene los parámetros de nómina vigentes"""
    cursor.execute("""
        SELECT parametro, valor
        FROM nomina_parametros
        WHERE activo = TRUE
        ORDER BY vigencia_desde DESC
    """)
    params = {}
    for row in cursor.fetchall():
        params[row['parametro']] = float(row['valor'])
    return params

def calcular_nomina_empleado(salario, tiene_auxilio, params, auxilio_no_salarial=0):
    """Calcula todos los conceptos de nómina para un empleado

    Args:
        salario: Salario nominal (base para seguridad social y prestaciones)
        tiene_auxilio: Si tiene derecho a auxilio de transporte legal
        params: Parámetros de nómina (porcentajes, SMMLV, etc.)
        auxilio_no_salarial: Pago no constitutivo de salario (Ley 1393/2010, max 40%)
    """
    salario = float(salario)
    auxilio_no_salarial = float(auxilio_no_salarial)

    # Auxilio de transporte legal (solo si gana menos de 2 SMMLV)
    smmlv = params.get('smmlv', 1750905)
    if tiene_auxilio and salario <= (2 * smmlv):
        auxilio_transporte = params.get('auxilio_transporte', 249095)
    else:
        auxilio_transporte = 0

    # Validar límite 40% para auxilio no salarial (Ley 1393 de 2010)
    remuneracion_total = salario + auxilio_no_salarial
    porcentaje_no_salarial = (auxilio_no_salarial / remuneracion_total * 100) if remuneracion_total > 0 else 0
    excede_limite = porcentaje_no_salarial > 40

    # Base para prestaciones (salario + auxilio transporte, NO incluye auxilio no salarial)
    base_prestaciones = salario + auxilio_transporte

    # Aportes seguridad social (sobre salario nominal únicamente)
    arl = salario * (params.get('arl_porcentaje', 0.522) / 100)
    eps = salario * (params.get('eps_porcentaje', 8.5) / 100)
    afp = salario * (params.get('afp_porcentaje', 12.0) / 100)
    caja = salario * (params.get('caja_porcentaje', 4.0) / 100)

    # Provisiones (sobre salario + auxilio transporte, NO sobre auxilio no salarial)
    prima = base_prestaciones * (params.get('prima_porcentaje', 8.33) / 100)
    cesantias = base_prestaciones * (params.get('cesantias_porcentaje', 8.33) / 100)
    int_cesantias = cesantias * (params.get('int_cesantias_porcentaje', 12.0) / 100) / 12
    vacaciones = salario * (params.get('vacaciones_porcentaje', 4.17) / 100)

    # Totales
    total_seguridad_social = arl + eps + afp + caja
    total_provisiones = prima + cesantias + int_cesantias + vacaciones

    # Costo total = salario + auxilio transporte + seg social + provisiones + auxilio no salarial
    costo_total = salario + auxilio_transporte + total_seguridad_social + total_provisiones + auxilio_no_salarial

    return {
        'salario_base': salario,
        'auxilio_transporte': auxilio_transporte,
        'auxilio_no_salarial': auxilio_no_salarial,
        'remuneracion_total': remuneracion_total,
        'porcentaje_no_salarial': porcentaje_no_salarial,
        'excede_limite': excede_limite,
        'arl': arl,
        'eps': eps,
        'afp': afp,
        'caja_compensacion': caja,
        'prima': prima,
        'cesantias': cesantias,
        'int_cesantias': int_cesantias,
        'vacaciones': vacaciones,
        'total_seguridad_social': total_seguridad_social,
        'total_provisiones': total_provisiones,
        'costo_total': costo_total
    }

st.title("💼 Gestión de Nómina")
st.caption("Administración de nómina administrativa - Pago el 1 de cada mes")

conn = conectar_logistica()
if not conn:
    st.stop()

# Crear tabla pagos_operativos_mensuales si no existe
try:
    _cursor = conn.cursor()
    _cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagos_operativos_mensuales (
            id INT AUTO_INCREMENT PRIMARY KEY,
            tipo ENUM('mensajeros', 'alistamiento') NOT NULL,
            periodo_mes INT NOT NULL,
            periodo_anio INT NOT NULL,
            monto_total DECIMAL(15, 2) NOT NULL,
            fecha_vencimiento DATE NOT NULL,
            estado ENUM('pendiente', 'pagado') DEFAULT 'pendiente',
            fecha_pago DATE,
            observaciones TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_tipo_periodo (tipo, periodo_mes, periodo_anio)
        )
    """)
    conn.commit()
    _cursor.close()
except Exception:
    pass

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "👥 Empleados",
    "📊 Resumen Nómina",
    "📅 Provisiones Mensuales",
    "⚙️ Parámetros",
    "💰 Pago Mensajeros/Alistamiento"
])

# =====================================================
# TAB 1: GESTIÓN DE EMPLEADOS
# =====================================================
with tab1:
    st.subheader("Gestión de Empleados de Nómina")

    try:
        cursor = conn.cursor(dictionary=True)

        # Mostrar empleados actuales
        cursor.execute("""
            SELECT id, nombre_completo, identificacion, cargo, salario_mensual,
                   tiene_auxilio_transporte, COALESCE(auxilio_no_salarial, 0) as auxilio_no_salarial,
                   fecha_ingreso, activo
            FROM nomina_empleados
            ORDER BY activo DESC, cargo
        """)
        empleados = cursor.fetchall()

        if empleados:
            st.markdown("### Empleados Registrados")

            # Obtener parámetros para calcular costos
            params = obtener_parametros_nomina(cursor)

            for emp in empleados:
                if emp['salario_mensual'] > 0:
                    calculo = calcular_nomina_empleado(
                        emp['salario_mensual'],
                        emp['tiene_auxilio_transporte'],
                        params,
                        emp['auxilio_no_salarial']
                    )
                    costo_total = calculo['costo_total']
                    aux_no_sal = float(emp['auxilio_no_salarial'])
                else:
                    costo_total = 0
                    aux_no_sal = 0

                estado = "✅" if emp['activo'] else "❌"
                titulo = f"{estado} {emp['nombre_completo']} - {emp['cargo']} - Salario: ${float(emp['salario_mensual']):,.0f}"
                if aux_no_sal > 0:
                    titulo += f" + Aux.NoSal: ${aux_no_sal:,.0f}"

                with st.expander(titulo):
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.write(f"**Identificación:** {emp['identificacion']}")
                        st.write(f"**Cargo:** {emp['cargo']}")
                        st.write(f"**Fecha Ingreso:** {emp['fecha_ingreso']}")

                    with col2:
                        st.write(f"**Salario Nominal:** ${float(emp['salario_mensual']):,.0f}")
                        if aux_no_sal > 0:
                            st.write(f"**Auxilio No Salarial:** ${aux_no_sal:,.0f}")
                            pct = calculo['porcentaje_no_salarial']
                            color = "🟢" if pct <= 40 else "🔴"
                            st.write(f"**% No Salarial:** {color} {pct:.1f}% {'(OK)' if pct <= 40 else '(EXCEDE 40%)'}")
                        st.write(f"**Auxilio Transporte:** {'Sí' if emp['tiene_auxilio_transporte'] else 'No'}")
                        st.write(f"**Estado:** {'Activo' if emp['activo'] else 'Inactivo'}")

                    with col3:
                        if aux_no_sal > 0:
                            st.metric("Remuneración Total", f"${calculo['remuneracion_total']:,.0f}")
                        st.metric("Costo Total Mensual", f"${costo_total:,.0f}")

                    # Botón para editar
                    if st.button(f"✏️ Editar", key=f"edit_emp_{emp['id']}"):
                        st.session_state.editando_empleado = emp['id']
                        st.rerun()

        st.divider()

        # Formulario para EDITAR empleado existente
        if 'editando_empleado' in st.session_state and st.session_state.editando_empleado:
            emp_id = st.session_state.editando_empleado
            # Buscar datos del empleado
            cursor.execute("""
                SELECT id, nombre_completo, identificacion, cargo, salario_mensual,
                       tiene_auxilio_transporte, COALESCE(auxilio_no_salarial, 0) as auxilio_no_salarial,
                       fecha_ingreso, activo
                FROM nomina_empleados WHERE id = %s
            """, (emp_id,))
            emp_editar = cursor.fetchone()

            if emp_editar:
                st.markdown(f"### ✏️ Editando: {emp_editar['nombre_completo']}")

                with st.form(key="form_editar_empleado"):
                    col1, col2 = st.columns(2)

                    with col1:
                        nombre_edit = st.text_input("Nombre Completo *", value=emp_editar['nombre_completo'])
                        identificacion_edit = st.text_input("Identificación *", value=emp_editar['identificacion'])
                        cargo_edit = st.text_input("Cargo *", value=emp_editar['cargo'])
                        fecha_ingreso_edit = st.date_input("Fecha de Ingreso", value=emp_editar['fecha_ingreso'])

                    with col2:
                        salario_edit = st.number_input("Salario Nominal *", min_value=0.0, step=100000.0,
                            value=float(emp_editar['salario_mensual']),
                            help="Base para seguridad social y prestaciones")
                        auxilio_no_sal_edit = st.number_input("Auxilio No Salarial", min_value=0.0, step=100000.0,
                            value=float(emp_editar['auxilio_no_salarial']),
                            help="Pago no constitutivo de salario (Ley 1393/2010, máx 40% del total)")
                        tiene_auxilio_edit = st.checkbox("Tiene Auxilio de Transporte Legal",
                            value=emp_editar['tiene_auxilio_transporte'],
                            help="Solo aplica si salario <= 2 SMMLV ($3,501,810)")
                        activo_edit = st.checkbox("Empleado Activo", value=emp_editar['activo'])

                    # Mostrar validación del 40%
                    if salario_edit > 0 and auxilio_no_sal_edit > 0:
                        total = salario_edit + auxilio_no_sal_edit
                        pct = auxilio_no_sal_edit / total * 100
                        if pct > 40:
                            st.error(f"⚠️ El auxilio no salarial ({pct:.1f}%) excede el límite legal del 40%")
                        else:
                            st.success(f"✓ Auxilio no salarial: {pct:.1f}% (dentro del límite legal)")

                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        submitted_edit = st.form_submit_button("💾 Guardar Cambios", type="primary")
                    with col_btn2:
                        cancelar = st.form_submit_button("❌ Cancelar")

                    if cancelar:
                        del st.session_state.editando_empleado
                        st.rerun()

                    if submitted_edit:
                        if not nombre_edit or not identificacion_edit or not cargo_edit:
                            st.error("Complete todos los campos obligatorios")
                        elif salario_edit > 0 and auxilio_no_sal_edit > 0:
                            total = salario_edit + auxilio_no_sal_edit
                            pct = auxilio_no_sal_edit / total * 100
                            if pct > 40:
                                st.error("No se puede guardar: el auxilio no salarial excede el 40%")
                            else:
                                try:
                                    cursor.execute("""
                                        UPDATE nomina_empleados
                                        SET nombre_completo = %s, identificacion = %s, cargo = %s,
                                            salario_mensual = %s, tiene_auxilio_transporte = %s,
                                            auxilio_no_salarial = %s, fecha_ingreso = %s, activo = %s
                                        WHERE id = %s
                                    """, (nombre_edit, identificacion_edit, cargo_edit, salario_edit,
                                          tiene_auxilio_edit, auxilio_no_sal_edit, fecha_ingreso_edit,
                                          activo_edit, emp_id))
                                    conn.commit()
                                    st.success("✅ Empleado actualizado exitosamente")
                                    del st.session_state.editando_empleado
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
                                    conn.rollback()
                        else:
                            try:
                                cursor.execute("""
                                    UPDATE nomina_empleados
                                    SET nombre_completo = %s, identificacion = %s, cargo = %s,
                                        salario_mensual = %s, tiene_auxilio_transporte = %s,
                                        auxilio_no_salarial = %s, fecha_ingreso = %s, activo = %s
                                    WHERE id = %s
                                """, (nombre_edit, identificacion_edit, cargo_edit, salario_edit,
                                      tiene_auxilio_edit, auxilio_no_sal_edit, fecha_ingreso_edit,
                                      activo_edit, emp_id))
                                conn.commit()
                                st.success("✅ Empleado actualizado exitosamente")
                                del st.session_state.editando_empleado
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                                conn.rollback()

            st.divider()

        # Formulario para agregar empleado
        st.markdown("### Agregar Nuevo Empleado")

        with st.form(key="form_nuevo_empleado"):
            col1, col2 = st.columns(2)

            with col1:
                nombre = st.text_input("Nombre Completo *")
                identificacion = st.text_input("Identificación *")
                cargo = st.text_input("Cargo *")
                fecha_ingreso = st.date_input("Fecha de Ingreso", value=date.today())

            with col2:
                salario = st.number_input("Salario Nominal *", min_value=0.0, step=100000.0,
                    help="Base para seguridad social y prestaciones")
                auxilio_no_sal = st.number_input("Auxilio No Salarial", min_value=0.0, step=100000.0,
                    help="Pago no constitutivo de salario (Ley 1393/2010, máx 40% del total)")
                tiene_auxilio = st.checkbox("Tiene Auxilio de Transporte Legal", value=True,
                    help="Solo aplica si salario <= 2 SMMLV ($3,501,810)")

            # Mostrar validación del 40%
            if salario > 0 and auxilio_no_sal > 0:
                total = salario + auxilio_no_sal
                pct = auxilio_no_sal / total * 100
                if pct > 40:
                    st.error(f"⚠️ El auxilio no salarial ({pct:.1f}%) excede el límite legal del 40%")
                else:
                    st.success(f"✓ Auxilio no salarial: {pct:.1f}% (dentro del límite legal)")

            submitted = st.form_submit_button("💾 Guardar Empleado", type="primary")

            if submitted:
                if not nombre or not identificacion or not cargo:
                    st.error("Complete todos los campos obligatorios")
                elif salario > 0 and auxilio_no_sal > 0:
                    total = salario + auxilio_no_sal
                    pct = auxilio_no_sal / total * 100
                    if pct > 40:
                        st.error("No se puede guardar: el auxilio no salarial excede el 40%")
                    else:
                        try:
                            cursor.execute("""
                                INSERT INTO nomina_empleados
                                (nombre_completo, identificacion, cargo, salario_mensual,
                                 tiene_auxilio_transporte, auxilio_no_salarial, fecha_ingreso)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (nombre, identificacion, cargo, salario, tiene_auxilio, auxilio_no_sal, fecha_ingreso))
                            conn.commit()
                            st.success("✅ Empleado registrado exitosamente")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                            conn.rollback()
                else:
                    try:
                        cursor.execute("""
                            INSERT INTO nomina_empleados
                            (nombre_completo, identificacion, cargo, salario_mensual,
                             tiene_auxilio_transporte, auxilio_no_salarial, fecha_ingreso)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (nombre, identificacion, cargo, salario, tiene_auxilio, auxilio_no_sal, fecha_ingreso))
                        conn.commit()
                        st.success("✅ Empleado registrado exitosamente")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                        conn.rollback()

    except Exception as e:
        st.error(f"Error: {e}")

# =====================================================
# TAB 2: RESUMEN DE NÓMINA
# =====================================================
with tab2:
    st.subheader("Resumen de Nómina Mensual")
    st.info("💡 Estos valores representan el costo total mensual que debe reservarse para el pago del 1 de cada mes")

    try:
        cursor = conn.cursor(dictionary=True)

        # Obtener parámetros
        params = obtener_parametros_nomina(cursor)

        # Obtener empleados activos
        cursor.execute("""
            SELECT id, nombre_completo, cargo, salario_mensual, tiene_auxilio_transporte,
                   COALESCE(auxilio_no_salarial, 0) as auxilio_no_salarial
            FROM nomina_empleados
            WHERE activo = TRUE AND salario_mensual > 0
            ORDER BY cargo
        """)
        empleados_activos = cursor.fetchall()

        if empleados_activos:
            # Calcular nómina para cada empleado
            datos_nomina = []
            totales = {
                'salario_base': 0, 'auxilio_transporte': 0, 'auxilio_no_salarial': 0,
                'arl': 0, 'eps': 0, 'afp': 0, 'caja_compensacion': 0,
                'prima': 0, 'cesantias': 0, 'int_cesantias': 0, 'vacaciones': 0,
                'total_seguridad_social': 0, 'total_provisiones': 0, 'costo_total': 0
            }

            for emp in empleados_activos:
                calculo = calcular_nomina_empleado(
                    emp['salario_mensual'],
                    emp['tiene_auxilio_transporte'],
                    params,
                    emp['auxilio_no_salarial']
                )

                datos_nomina.append({
                    'Empleado': emp['nombre_completo'],
                    'Cargo': emp['cargo'],
                    'Salario Nominal': calculo['salario_base'],
                    'Aux. No Salarial': calculo['auxilio_no_salarial'],
                    'Aux. Transporte': calculo['auxilio_transporte'],
                    'Costo Total': calculo['costo_total']
                })

                for key in totales:
                    if key in calculo:
                        totales[key] += calculo[key]

            # Mostrar tabla resumen
            st.markdown("### Nómina por Empleado")
            df_nomina = pd.DataFrame(datos_nomina)
            df_nomina['Salario Nominal'] = df_nomina['Salario Nominal'].apply(lambda x: f"${x:,.0f}")
            df_nomina['Aux. No Salarial'] = df_nomina['Aux. No Salarial'].apply(lambda x: f"${x:,.0f}" if x > 0 else "-")
            df_nomina['Aux. Transporte'] = df_nomina['Aux. Transporte'].apply(lambda x: f"${x:,.0f}" if x > 0 else "-")
            df_nomina['Costo Total'] = df_nomina['Costo Total'].apply(lambda x: f"${x:,.0f}")
            st.dataframe(df_nomina, use_container_width=True, hide_index=True)

            st.divider()

            # Resumen de costos
            st.markdown("### Desglose de Costos Mensuales")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("**📋 Nómina Base**")
                st.write(f"• Salarios Nominales: ${totales['salario_base']:,.0f}")
                st.write(f"• Auxilios de Transporte: ${totales['auxilio_transporte']:,.0f}")
                if totales['auxilio_no_salarial'] > 0:
                    st.write(f"• Auxilios No Salariales: ${totales['auxilio_no_salarial']:,.0f}")
                st.markdown(f"**TOTAL REMUNERACIÓN: ${totales['salario_base'] + totales['auxilio_transporte'] + totales['auxilio_no_salarial']:,.0f}**")

            with col2:
                st.markdown("**🏥 Seguridad Social (Empleador)**")
                st.write(f"• ARL: ${totales['arl']:,.0f}")
                st.write(f"• EPS: ${totales['eps']:,.0f}")
                st.write(f"• AFP: ${totales['afp']:,.0f}")
                st.write(f"• Caja de Compensación: ${totales['caja_compensacion']:,.0f}")
                st.markdown(f"**TOTAL SEG. SOCIAL: ${totales['total_seguridad_social']:,.0f}**")
                st.caption("(Calculado sobre salario nominal)")

            with col3:
                st.markdown("**💰 Provisiones Mensuales**")
                st.write(f"• Primas: ${totales['prima']:,.0f}")
                st.write(f"• Cesantías: ${totales['cesantias']:,.0f}")
                st.write(f"• Int. a las Cesantías: ${totales['int_cesantias']:,.0f}")
                st.write(f"• Vacaciones: ${totales['vacaciones']:,.0f}")
                st.markdown(f"**TOTAL PROVISIONES: ${totales['total_provisiones']:,.0f}**")
                st.caption("(Calculado sobre salario + aux. transporte)")

            st.divider()

            # Total general
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Salarios + Auxilios", f"${totales['salario_base'] + totales['auxilio_transporte'] + totales['auxilio_no_salarial']:,.0f}")
            with col2:
                st.metric("Seg. Social + Provisiones", f"${totales['total_seguridad_social'] + totales['total_provisiones']:,.0f}")
            with col3:
                st.metric("COSTO TOTAL MENSUAL", f"${totales['costo_total']:,.0f}", delta="A reservar el 1 de cada mes")

            # Tabla comparativa con valores del usuario
            st.markdown("### Comparación con Valores de Referencia")
            with st.expander("Ver comparación detallada"):
                comparacion = [
                    ("TOTAL NÓMINA ADMINISTRATIVA", totales['salario_base'], 8734410),
                    ("Auxilios de Transporte", totales['auxilio_transporte'], 253200),
                    ("ARL", totales['arl'], 45594),
                    ("EPS", totales['eps'], 742425),
                    ("AFP", totales['afp'], 1048129),
                    ("Caja de Compensación", totales['caja_compensacion'], 349376),
                    ("Primas", totales['prima'], 727868),
                    ("Cesantías", totales['cesantias'], 727868),
                    ("Int. a las Cesantías", totales['int_cesantias'], 7279),
                    ("Vacaciones", totales['vacaciones'], 363934),
                ]

                df_comp = pd.DataFrame(comparacion, columns=['Concepto', 'Calculado', 'Referencia'])
                df_comp['Diferencia'] = df_comp['Calculado'] - df_comp['Referencia']
                df_comp['Calculado'] = df_comp['Calculado'].apply(lambda x: f"${x:,.0f}")
                df_comp['Referencia'] = df_comp['Referencia'].apply(lambda x: f"${x:,.0f}")
                df_comp['Diferencia'] = df_comp['Diferencia'].apply(lambda x: f"${x:,.0f}")
                st.dataframe(df_comp, use_container_width=True, hide_index=True)

        else:
            st.info("No hay empleados activos con salario registrado")

    except Exception as e:
        st.error(f"Error: {e}")

# =====================================================
# TAB 3: PROVISIONES MENSUALES
# =====================================================
with tab3:
    st.subheader("Provisiones Mensuales")
    st.info("💡 Genere y registre las provisiones de nómina para cada mes")

    try:
        cursor = conn.cursor(dictionary=True)

        col1, col2 = st.columns(2)
        with col1:
            mes_provision = st.selectbox("Mes", list(range(1, 13)),
                index=datetime.now().month - 1,
                format_func=lambda x: ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                                       'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'][x-1])
        with col2:
            anio_provision = st.number_input("Año", min_value=2020, max_value=2030, value=datetime.now().year)

        # Verificar si ya existen provisiones para este período
        cursor.execute("""
            SELECT np.*,
                   (np.salario_base + np.auxilio_transporte + COALESCE(np.auxilio_no_salarial, 0) +
                    np.arl + np.eps + np.afp + np.caja_compensacion +
                    np.prima + np.cesantias + np.int_cesantias + np.vacaciones) as costo_calculado,
                   e.nombre_completo, e.cargo
            FROM nomina_provisiones np
            JOIN nomina_empleados e ON np.empleado_id = e.id
            WHERE np.periodo_mes = %s AND np.periodo_anio = %s
            ORDER BY e.cargo
        """, (mes_provision, anio_provision))
        provisiones_existentes = cursor.fetchall()

        if provisiones_existentes:
            st.success(f"✅ Provisiones ya generadas para {mes_provision}/{anio_provision}")

            # Mostrar resumen - usar costo_calculado en lugar de costo_total_empleado
            total_costo = sum([float(p['costo_calculado']) for p in provisiones_existentes])
            st.metric("Total Provisionado", f"${total_costo:,.0f}")

            # Mostrar detalle
            with st.expander("Ver detalle de provisiones"):
                for p in provisiones_existentes:
                    st.write(f"**{p['nombre_completo']}** ({p['cargo']}): Salario ${float(p['salario_base']):,.0f} → Costo ${float(p['costo_calculado']):,.0f}")

            st.divider()

            # Botón para recalcular provisiones con salarios actuales
            st.markdown("#### 🔄 Recalcular Provisiones")
            st.warning("⚠️ Esto actualizará las provisiones del período seleccionado usando los salarios actuales de los empleados.")

            # Primero mostrar vista previa de lo que se va a recalcular
            st.markdown("##### Vista previa de salarios actuales:")
            cursor.execute("""
                SELECT id, nombre_completo, salario_mensual, tiene_auxilio_transporte,
                       COALESCE(auxilio_no_salarial, 0) as auxilio_no_salarial
                FROM nomina_empleados
                WHERE activo = TRUE AND salario_mensual > 0
            """)
            empleados_preview = cursor.fetchall()
            params_preview = obtener_parametros_nomina(cursor)

            total_nuevo = 0
            for emp in empleados_preview:
                calculo = calcular_nomina_empleado(
                    emp['salario_mensual'],
                    emp['tiene_auxilio_transporte'],
                    params_preview,
                    emp['auxilio_no_salarial']
                )
                total_nuevo += calculo['costo_total']
                st.write(f"• {emp['nombre_completo']}: Salario ${float(emp['salario_mensual']):,.0f} → Costo ${calculo['costo_total']:,.0f}")

            st.metric("Nuevo Total (si recalcula)", f"${total_nuevo:,.0f}",
                     delta=f"${total_nuevo - total_costo:,.0f}" if total_nuevo != total_costo else None)

            if st.button("🔄 Recalcular con Salarios Actuales", key="btn_recalcular_provisiones"):
                try:
                    # Eliminar provisiones existentes del período
                    cursor.execute("""
                        DELETE FROM nomina_provisiones
                        WHERE periodo_mes = %s AND periodo_anio = %s
                    """, (mes_provision, anio_provision))

                    eliminados = cursor.rowcount
                    st.info(f"Eliminadas {eliminados} provisiones existentes")

                    # Regenerar provisiones con valores actuales
                    for emp in empleados_preview:
                        calculo = calcular_nomina_empleado(
                            emp['salario_mensual'],
                            emp['tiene_auxilio_transporte'],
                            params_preview,
                            emp['auxilio_no_salarial']
                        )

                        cursor.execute("""
                            INSERT INTO nomina_provisiones
                            (empleado_id, periodo_mes, periodo_anio, salario_base, auxilio_transporte,
                             auxilio_no_salarial, arl, eps, afp, caja_compensacion, prima, cesantias,
                             int_cesantias, vacaciones)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            emp['id'], mes_provision, anio_provision,
                            calculo['salario_base'], calculo['auxilio_transporte'], calculo['auxilio_no_salarial'],
                            calculo['arl'], calculo['eps'], calculo['afp'], calculo['caja_compensacion'],
                            calculo['prima'], calculo['cesantias'], calculo['int_cesantias'], calculo['vacaciones']
                        ))

                    conn.commit()
                    st.success(f"✅ Provisiones recalculadas para {len(empleados_preview)} empleados")
                    st.rerun()

                except Exception as e:
                    st.error(f"Error: {e}")
                    import traceback
                    st.code(traceback.format_exc())
                    conn.rollback()
        else:
            st.warning(f"⚠️ No hay provisiones generadas para {mes_provision}/{anio_provision}")

            if st.button("📝 Generar Provisiones", type="primary"):
                try:
                    # Obtener parámetros y empleados
                    params = obtener_parametros_nomina(cursor)

                    cursor.execute("""
                        SELECT id, salario_mensual, tiene_auxilio_transporte,
                               COALESCE(auxilio_no_salarial, 0) as auxilio_no_salarial
                        FROM nomina_empleados
                        WHERE activo = TRUE AND salario_mensual > 0
                    """)
                    empleados = cursor.fetchall()

                    for emp in empleados:
                        calculo = calcular_nomina_empleado(
                            emp['salario_mensual'],
                            emp['tiene_auxilio_transporte'],
                            params,
                            emp['auxilio_no_salarial']
                        )

                        cursor.execute("""
                            INSERT INTO nomina_provisiones
                            (empleado_id, periodo_mes, periodo_anio, salario_base, auxilio_transporte,
                             auxilio_no_salarial, arl, eps, afp, caja_compensacion, prima, cesantias, int_cesantias, vacaciones)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            emp['id'], mes_provision, anio_provision,
                            calculo['salario_base'], calculo['auxilio_transporte'], calculo['auxilio_no_salarial'],
                            calculo['arl'], calculo['eps'], calculo['afp'], calculo['caja_compensacion'],
                            calculo['prima'], calculo['cesantias'], calculo['int_cesantias'], calculo['vacaciones']
                        ))

                    conn.commit()
                    st.success(f"✅ Provisiones generadas para {len(empleados)} empleados")
                    st.rerun()

                except Exception as e:
                    st.error(f"Error: {e}")
                    conn.rollback()

        st.divider()

        # Histórico de provisiones
        st.markdown("### Histórico de Provisiones")

        cursor.execute("""
            SELECT
                periodo_anio, periodo_mes,
                COUNT(*) as empleados,
                SUM(salario_base + auxilio_transporte + COALESCE(auxilio_no_salarial, 0) +
                    arl + eps + afp + caja_compensacion +
                    prima + cesantias + int_cesantias + vacaciones) as total
            FROM nomina_provisiones
            GROUP BY periodo_anio, periodo_mes
            ORDER BY periodo_anio DESC, periodo_mes DESC
            LIMIT 12
        """)
        historico = cursor.fetchall()

        if historico:
            meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
            df_hist = pd.DataFrame(historico)
            df_hist['Período'] = df_hist.apply(lambda x: f"{meses[x['periodo_mes']-1]} {x['periodo_anio']}", axis=1)
            df_hist['Total'] = df_hist['total'].apply(lambda x: f"${float(x):,.0f}")
            st.dataframe(df_hist[['Período', 'empleados', 'Total']], use_container_width=True, hide_index=True)
        else:
            st.info("No hay provisiones registradas")

    except Exception as e:
        st.error(f"Error: {e}")

# =====================================================
# TAB 4: PARÁMETROS DE NÓMINA
# =====================================================
with tab4:
    st.subheader("Parámetros de Nómina")
    st.info("💡 Configure los porcentajes y valores para el cálculo de nómina")

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, parametro, valor, descripcion, vigencia_desde
            FROM nomina_parametros
            WHERE activo = TRUE
            ORDER BY parametro
        """)
        parametros = cursor.fetchall()

        if parametros:
            for param in parametros:
                col1, col2, col3 = st.columns([2, 1, 1])

                with col1:
                    st.write(f"**{param['descripcion']}**")
                    st.caption(f"Parámetro: {param['parametro']}")

                with col2:
                    if 'porcentaje' in param['parametro']:
                        st.write(f"{float(param['valor']):.2f}%")
                    else:
                        st.write(f"${float(param['valor']):,.0f}")

                with col3:
                    st.write(f"Desde: {param['vigencia_desde']}")

                st.divider()

            # Formulario para actualizar parámetros
            st.markdown("### Actualizar Parámetro")

            with st.form("form_parametro"):
                param_seleccionado = st.selectbox(
                    "Parámetro a actualizar",
                    [p['parametro'] for p in parametros],
                    format_func=lambda x: next((p['descripcion'] for p in parametros if p['parametro'] == x), x)
                )

                nuevo_valor = st.number_input("Nuevo valor", min_value=0.0, step=0.01)
                nueva_vigencia = st.date_input("Vigencia desde", value=date.today())

                if st.form_submit_button("💾 Actualizar"):
                    try:
                        cursor.execute("""
                            UPDATE nomina_parametros
                            SET valor = %s, vigencia_desde = %s
                            WHERE parametro = %s
                        """, (nuevo_valor, nueva_vigencia, param_seleccionado))
                        conn.commit()
                        st.success("✅ Parámetro actualizado")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                        conn.rollback()

    except Exception as e:
        st.error(f"Error: {e}")

# =====================================================
# TAB 5: PAGO MENSAJEROS Y ALISTAMIENTO
# =====================================================
with tab5:
    st.subheader("Pago Mensajeros y Alistamiento")
    st.info("💡 Registre los pagos totales mensuales de mensajeros y alistamiento. La fecha de vencimiento se calcula automáticamente como el 8 del mes siguiente.")

    try:
        cursor = conn.cursor(dictionary=True)

        # Selector de periodo
        col1, col2 = st.columns(2)
        with col1:
            mes_pago = st.selectbox("Mes", list(range(1, 13)),
                index=datetime.now().month - 1,
                format_func=lambda x: ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                                       'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'][x-1],
                key="mes_pago_op")
        with col2:
            anio_pago = st.number_input("Año", min_value=2020, max_value=2030, value=datetime.now().year, key="anio_pago_op")

        # Calcular fecha de vencimiento: 8 del mes siguiente
        if mes_pago == 12:
            fecha_venc_op = date(anio_pago + 1, 1, 8)
        else:
            fecha_venc_op = date(anio_pago, mes_pago + 1, 8)

        st.caption(f"Fecha de vencimiento calculada: **{fecha_venc_op.strftime('%d/%m/%Y')}**")

        st.divider()

        # Verificar si ya existen registros para este periodo
        cursor.execute("""
            SELECT * FROM pagos_operativos_mensuales
            WHERE periodo_mes = %s AND periodo_anio = %s
            ORDER BY tipo
        """, (mes_pago, anio_pago))
        pagos_existentes = cursor.fetchall()

        pagos_dict = {p['tipo']: p for p in pagos_existentes}

        # Formulario de registro
        st.markdown("### Registrar Pagos del Periodo")

        with st.form("form_pagos_operativos"):
            col1, col2 = st.columns(2)

            with col1:
                monto_mensajeros_default = float(pagos_dict['mensajeros']['monto_total']) if 'mensajeros' in pagos_dict else 0.0
                monto_mensajeros = st.number_input(
                    "Monto Total Mensajeros",
                    min_value=0.0, step=100000.0, format="%.2f",
                    value=monto_mensajeros_default
                )

            with col2:
                monto_alistamiento_default = float(pagos_dict['alistamiento']['monto_total']) if 'alistamiento' in pagos_dict else 0.0
                monto_alistamiento = st.number_input(
                    "Monto Total Alistamiento",
                    min_value=0.0, step=100000.0, format="%.2f",
                    value=monto_alistamiento_default
                )

            observaciones_op = st.text_area("Observaciones (opcional)", height=80, key="obs_pago_op")

            submitted_op = st.form_submit_button("💾 Guardar Pagos", type="primary")

            if submitted_op:
                if monto_mensajeros <= 0 and monto_alistamiento <= 0:
                    st.error("Ingrese al menos un monto mayor a 0")
                else:
                    try:
                        cursor_w = conn.cursor()

                        for tipo, monto in [('mensajeros', monto_mensajeros), ('alistamiento', monto_alistamiento)]:
                            if monto > 0:
                                cursor_w.execute("""
                                    INSERT INTO pagos_operativos_mensuales
                                    (tipo, periodo_mes, periodo_anio, monto_total, fecha_vencimiento, observaciones)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                    ON DUPLICATE KEY UPDATE
                                    monto_total = VALUES(monto_total),
                                    fecha_vencimiento = VALUES(fecha_vencimiento),
                                    observaciones = VALUES(observaciones)
                                """, (tipo, mes_pago, anio_pago, monto, fecha_venc_op, observaciones_op or None))

                        conn.commit()
                        st.success("Pagos registrados exitosamente")
                        st.rerun()

                    except Exception as e:
                        conn.rollback()
                        st.error(f"Error al guardar: {e}")

        st.divider()

        # Vista de pagos registrados
        st.markdown("### Pagos Registrados")

        cursor.execute("""
            SELECT tipo, periodo_mes, periodo_anio, monto_total, fecha_vencimiento, estado, fecha_pago, observaciones, id
            FROM pagos_operativos_mensuales
            ORDER BY periodo_anio DESC, periodo_mes DESC, tipo
        """)
        todos_pagos = cursor.fetchall()

        if todos_pagos:
            meses_nombres = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

            for pago in todos_pagos:
                estado_icon = "🟢" if pago['estado'] == 'pagado' else "🟡"
                periodo_str = f"{meses_nombres[pago['periodo_mes']-1]} {pago['periodo_anio']}"
                tipo_label = "Mensajeros" if pago['tipo'] == 'mensajeros' else "Alistamiento"

                with st.expander(f"{estado_icon} {tipo_label} - {periodo_str} - ${float(pago['monto_total']):,.0f} - {pago['estado'].capitalize()}"):
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.metric("Monto", f"${float(pago['monto_total']):,.0f}")
                    with col2:
                        st.metric("Vencimiento", pago['fecha_vencimiento'].strftime('%d/%m/%Y'))
                        if pago['estado'] == 'pendiente':
                            dias_rest = (pago['fecha_vencimiento'] - date.today()).days
                            if dias_rest < 0:
                                st.error(f"Vencido hace {abs(dias_rest)} dias")
                            elif dias_rest <= 7:
                                st.warning(f"Vence en {dias_rest} dias")
                            else:
                                st.info(f"{dias_rest} dias restantes")
                    with col3:
                        st.metric("Estado", pago['estado'].capitalize())
                        if pago['fecha_pago']:
                            st.write(f"Pagado: {pago['fecha_pago'].strftime('%d/%m/%Y')}")

                    if pago['observaciones']:
                        st.write(f"**Observaciones:** {pago['observaciones']}")

                    # Boton para marcar como pagado
                    if pago['estado'] == 'pendiente':
                        col_btn1, col_btn2 = st.columns([1, 3])
                        with col_btn1:
                            if st.button("Marcar como Pagado", key=f"pagar_op_{pago['id']}"):
                                try:
                                    cursor_u = conn.cursor()
                                    cursor_u.execute("""
                                        UPDATE pagos_operativos_mensuales
                                        SET estado = 'pagado', fecha_pago = %s
                                        WHERE id = %s
                                    """, (date.today(), pago['id']))
                                    conn.commit()
                                    st.success("Marcado como pagado")
                                    st.rerun()
                                except Exception as e:
                                    conn.rollback()
                                    st.error(f"Error: {e}")

            # Totales
            st.divider()
            total_pendiente = sum([float(p['monto_total']) for p in todos_pagos if p['estado'] == 'pendiente'])
            total_pagado = sum([float(p['monto_total']) for p in todos_pagos if p['estado'] == 'pagado'])

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Registros", len(todos_pagos))
            with col2:
                st.metric("Pendiente", f"${total_pendiente:,.0f}")
            with col3:
                st.metric("Pagado", f"${total_pagado:,.0f}")

        else:
            st.info("No hay pagos operativos registrados")

    except Exception as e:
        st.error(f"Error: {e}")

# Cerrar cursor
if 'cursor' in locals():
    cursor.close()
