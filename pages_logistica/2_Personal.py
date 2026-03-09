import streamlit as st
import pandas as pd
from datetime import date
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_connection import conectar_logistica


st.title("🚚 Gestión de Personal")

conn = conectar_logistica()
if not conn:
    st.stop()

tab1, tab2, tab3 = st.tabs([
    "📋 Listar Personal",
    "➕ Agregar/Editar Personal",
    "🏙️ Tarifas por Ciudad"
])

with tab1:
    st.subheader("Lista de Personal")

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                id, codigo, nombre_completo, identificacion, tipo_personal, zona, telefono, activo, fecha_ingreso
            FROM personal
            ORDER BY tipo_personal, codigo
        """)
        personal = cursor.fetchall()

        if personal:
            # Metricas
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                mensajeros = len([p for p in personal if p['tipo_personal'] == 'mensajero'])
                st.metric("Mensajeros", mensajeros)
            with col2:
                alistamiento = len([p for p in personal if p['tipo_personal'] == 'alistamiento'])
                st.metric("Alistamiento", alistamiento)
            with col3:
                couriers = len([p for p in personal if p['tipo_personal'] == 'courier_externo'])
                st.metric("Couriers", couriers)
            with col4:
                transportadoras = len([p for p in personal if p['tipo_personal'] == 'transportadora'])
                st.metric("Transportadoras", transportadoras)

            st.divider()

            # Filtro por tipo de personal
            tipos_disponibles = ['TODOS'] + list(set([p['tipo_personal'] for p in personal]))
            tipo_filtro = st.selectbox("Filtrar por tipo", tipos_disponibles, key="filtro_tipo_personal")

            if tipo_filtro != 'TODOS':
                personal_filtrado = [p for p in personal if p['tipo_personal'] == tipo_filtro]
            else:
                personal_filtrado = personal

            st.divider()

            # Edicion de zona en linea
            st.markdown("### Asignar Zona de Distribución")
            st.caption("Selecciona la zona para cada persona y guarda los cambios")

            zona_options = ['Sin asignar', 'norte', 'sur']

            # Guardar cambios de zona en session_state
            if 'zonas_modificadas' not in st.session_state:
                st.session_state.zonas_modificadas = {}

            # Encabezados
            col1, col2, col3, col4, col5 = st.columns([0.8, 2, 1.2, 1.2, 1])
            col1.write("**Código**")
            col2.write("**Nombre**")
            col3.write("**Tipo**")
            col4.write("**Zona Actual**")
            col5.write("**Nueva Zona**")

            st.markdown("---")

            for p in personal_filtrado:
                col1, col2, col3, col4, col5 = st.columns([0.8, 2, 1.2, 1.2, 1])

                with col1:
                    st.write(p['codigo'])
                with col2:
                    st.write(p['nombre_completo'])
                with col3:
                    st.write(p['tipo_personal'])
                with col4:
                    zona_actual = p['zona'] if p['zona'] else 'Sin asignar'
                    if zona_actual == 'norte':
                        st.write("🔵 Norte")
                    elif zona_actual == 'sur':
                        st.write("🔴 Sur")
                    else:
                        st.write("⚪ Sin asignar")
                with col5:
                    zona_index = zona_options.index(p['zona']) if p['zona'] in zona_options else 0
                    nueva_zona = st.selectbox(
                        "Zona",
                        zona_options,
                        index=zona_index,
                        key=f"zona_{p['id']}",
                        label_visibility="collapsed"
                    )
                    # Guardar si cambió
                    zona_valor = None if nueva_zona == 'Sin asignar' else nueva_zona
                    if zona_valor != p['zona']:
                        st.session_state.zonas_modificadas[p['id']] = zona_valor

            st.divider()

            # Boton para guardar cambios
            if st.session_state.zonas_modificadas:
                st.info(f"Hay {len(st.session_state.zonas_modificadas)} cambios pendientes")

                if st.button("💾 Guardar Cambios de Zona", type="primary"):
                    try:
                        cursor_update = conn.cursor()
                        for personal_id, nueva_zona in st.session_state.zonas_modificadas.items():
                            cursor_update.execute(
                                "UPDATE personal SET zona = %s WHERE id = %s",
                                (nueva_zona, personal_id)
                            )
                        conn.commit()
                        cursor_update.close()
                        st.session_state.zonas_modificadas = {}
                        st.success(f"Zonas actualizadas correctamente")
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Error al guardar: {e}")

        else:
            st.info("No hay personal registrado")
    except Exception as e:
        st.error(f"Error: {e}")

with tab2:
    st.subheader("Agregar/Editar Personal")

    col1, col2 = st.columns([1, 3])

    with col1:
        modo = st.radio("Modo", ["Agregar Nuevo", "Editar Existente"])

    with col2:
        if modo == "Editar Existente":
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id, codigo, nombre_completo, tipo_personal FROM personal ORDER BY nombre_completo")
                personal_list = cursor.fetchall()

                if personal_list:
                    personal_options = {
                        f"{p['codigo']} - {p['nombre_completo']} ({p['tipo_personal']})": p['id']
                        for p in personal_list
                    }
                    personal_sel = st.selectbox("Seleccionar Personal", list(personal_options.keys()))
                    personal_id = personal_options[personal_sel]

                    cursor.execute("SELECT * FROM personal WHERE id = %s", (personal_id,))
                    persona = cursor.fetchone()
                else:
                    st.warning("No hay personal para editar")
                    persona = None
            except Exception as e:
                st.error(f"Error: {e}")
                persona = None
        else:
            persona = None

    st.divider()

    with st.form("form_personal"):
        col1, col2, col3 = st.columns(3)

        with col1:
            codigo = st.text_input(
                "Código (4 dígitos) *",
                value=persona['codigo'] if persona else "",
                max_chars=4,
                help="Ejemplo: 0001, 0025, 1234"
            )
            nombre_completo = st.text_input("Nombre Completo *", value=persona['nombre_completo'] if persona else "")

        with col2:
            identificacion = st.text_input("Identificación *", value=persona['identificacion'] if persona else "")
            tipo_personal = st.selectbox(
                "Tipo de Personal *",
                ["mensajero", "alistamiento", "conductor", "courier_externo", "transportadora"],
                index=["mensajero", "alistamiento", "conductor", "courier_externo", "transportadora"].index(
                    persona['tipo_personal']
                ) if persona else 0
            )

        with col3:
            telefono = st.text_input("Teléfono", value=persona['telefono'] if persona else "")
            email = st.text_input("Email", value=persona['email'] if persona else "")

        col1, col2, col3 = st.columns(3)
        with col1:
            activo = st.checkbox("Activo", value=persona['activo'] if persona else True)
        with col2:
            zona_options = [None, 'norte', 'sur']
            zona_labels = ['Sin asignar', 'Norte', 'Sur']
            zona_actual = persona['zona'] if persona and persona.get('zona') else None
            zona_index = zona_options.index(zona_actual) if zona_actual in zona_options else 0
            zona = st.selectbox("Zona de Distribución", zona_labels, index=zona_index)
            zona_value = None if zona == 'Sin asignar' else zona.lower()
        with col3:
            fecha_ingreso = st.date_input(
                "Fecha Ingreso",
                value=persona['fecha_ingreso'] if persona and persona['fecha_ingreso'] else date.today()
            )

        observaciones = st.text_area("Observaciones", value=persona['observaciones'] if persona else "")

        # Tarifas para courier_externo
        st.markdown("#### Tarifas Courier Externo")
        st.caption("Solo aplica para tipo 'courier_externo'")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Local (Bogotá)**")
            tarifa_entrega_local = st.number_input(
                "Tarifa Entrega Local",
                min_value=0.0,
                value=float(persona['tarifa_entrega_local']) if persona and persona.get('tarifa_entrega_local') else 0.0,
                step=100.0
            )
            tarifa_devolucion_local = st.number_input(
                "Tarifa Devolución Local",
                min_value=0.0,
                value=float(persona['tarifa_devolucion_local']) if persona and persona.get('tarifa_devolucion_local') else 0.0,
                step=100.0
            )
        with col2:
            st.markdown("**Nacional**")
            tarifa_entrega_nacional = st.number_input(
                "Tarifa Entrega Nacional",
                min_value=0.0,
                value=float(persona['tarifa_entrega_nacional']) if persona and persona.get('tarifa_entrega_nacional') else 0.0,
                step=100.0
            )
            tarifa_devolucion_nacional = st.number_input(
                "Tarifa Devolución Nacional",
                min_value=0.0,
                value=float(persona['tarifa_devolucion_nacional']) if persona and persona.get('tarifa_devolucion_nacional') else 0.0,
                step=100.0
            )

        submitted = st.form_submit_button("💾 Guardar")

        if submitted:
            if not codigo or not nombre_completo or not identificacion:
                st.error("Código, Nombre e Identificación son obligatorios")
            elif len(codigo) != 4 or not codigo.isdigit():
                st.error("El código debe tener exactamente 4 dígitos numéricos")
            else:
                try:
                    cursor = conn.cursor()

                    if modo == "Agregar Nuevo":
                        cursor.execute("SELECT id FROM personal WHERE codigo = %s OR identificacion = %s", (codigo, identificacion))
                        if cursor.fetchone():
                            st.error(f"Ya existe personal con el código {codigo} o identificación {identificacion}")
                        else:
                            cursor.execute("""
                                INSERT INTO personal
                                (codigo, nombre_completo, identificacion, tipo_personal, zona, telefono, email, activo, fecha_ingreso, observaciones,
                                 tarifa_entrega_local, tarifa_entrega_nacional, tarifa_devolucion_local, tarifa_devolucion_nacional)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (codigo, nombre_completo, identificacion, tipo_personal, zona_value, telefono, email, activo, fecha_ingreso, observaciones,
                                  tarifa_entrega_local, tarifa_entrega_nacional, tarifa_devolucion_local, tarifa_devolucion_nacional))
                            conn.commit()
                            st.success(f"✅ Personal '{nombre_completo}' agregado exitosamente")
                            st.rerun()
                    else:
                        cursor.execute("SELECT id FROM personal WHERE (codigo = %s OR identificacion = %s) AND id != %s", (codigo, identificacion, personal_id))
                        if cursor.fetchone():
                            st.error(f"Ya existe otro personal con el código {codigo} o identificación {identificacion}")
                        else:
                            cursor.execute("""
                                UPDATE personal SET
                                codigo = %s, nombre_completo = %s, identificacion = %s, tipo_personal = %s, zona = %s,
                                telefono = %s, email = %s, activo = %s, fecha_ingreso = %s, observaciones = %s,
                                tarifa_entrega_local = %s, tarifa_entrega_nacional = %s, tarifa_devolucion_local = %s, tarifa_devolucion_nacional = %s
                                WHERE id = %s
                            """, (codigo, nombre_completo, identificacion, tipo_personal, zona_value, telefono, email, activo, fecha_ingreso, observaciones,
                                  tarifa_entrega_local, tarifa_entrega_nacional, tarifa_devolucion_local, tarifa_devolucion_nacional, personal_id))
                            conn.commit()
                            st.success(f"✅ Personal '{nombre_completo}' actualizado exitosamente")
                            st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")
                    conn.rollback()

with tab3:
    st.subheader("Tarifas de Personal por Ciudad")
    st.info("ℹ️ Configurar tarifas específicas por ciudad para personal")

    # Inicializar contador de formulario para resetear campos
    if 'form_tarifa_counter' not in st.session_state:
        st.session_state.form_tarifa_counter = 0

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, codigo, nombre_completo, tipo_personal
            FROM personal
            WHERE activo = TRUE
            ORDER BY nombre_completo
        """)
        personal_list = cursor.fetchall()

        if not personal_list:
            st.warning("No hay personal activo")
        else:
            personal_options = {f"{p['codigo']} - {p['nombre_completo']} ({p['tipo_personal']})": p['id'] for p in personal_list}
            personal_sel = st.selectbox("Seleccionar Personal", list(personal_options.keys()), key="tarifa_personal")
            personal_id = personal_options[personal_sel]

            st.divider()

            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown("### 📍 Ciudades Asignadas")
                cursor.execute("""
                    SELECT
                        pc.id, c.nombre as ciudad, pc.tipo_servicio,
                        pc.tarifa_entrega, pc.tarifa_devolucion,
                        pc.vigencia_desde, pc.vigencia_hasta
                    FROM personal_ciudades pc
                    JOIN ciudades c ON pc.ciudad_id = c.id
                    WHERE pc.personal_id = %s AND pc.activo = TRUE
                    ORDER BY c.nombre, pc.tipo_servicio
                """, (personal_id,))
                asignaciones = cursor.fetchall()

                if asignaciones:
                    df = pd.DataFrame(asignaciones)
                    df['tipo_servicio'] = df['tipo_servicio'].fillna('sobre')
                    df['tarifa_entrega'] = df['tarifa_entrega'].apply(lambda x: f"${x:,.0f}" if x else "-")
                    df['tarifa_devolucion'] = df['tarifa_devolucion'].apply(lambda x: f"${x:,.0f}" if x else "-")
                    df['vigencia_desde'] = pd.to_datetime(df['vigencia_desde']).dt.strftime('%d/%m/%Y')
                    df['vigencia_hasta'] = df['vigencia_hasta'].apply(lambda x: pd.to_datetime(x).strftime('%d/%m/%Y') if pd.notna(x) else 'Indefinido')
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info("No hay ciudades asignadas")

            with col2:
                st.markdown("### 🗑️ Eliminar")
                if asignaciones:
                    asig_options = {
                        f"{a['ciudad']} - {a['tipo_servicio']} (E:${a['tarifa_entrega']:,.0f} D:${a['tarifa_devolucion'] or 0:,.0f})": a['id']
                        for a in asignaciones
                    }
                    asig_sel = st.selectbox("Seleccionar", list(asig_options.keys()))

                    if st.button("🗑️ Eliminar", type="secondary"):
                        try:
                            cursor = conn.cursor()
                            cursor.execute("UPDATE personal_ciudades SET activo = FALSE WHERE id = %s", (asig_options[asig_sel],))
                            conn.commit()
                            st.success("✅ Asignación eliminada")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

            st.divider()
            st.markdown("### ➕ Agregar Ciudad")

            # Verificar el tipo de personal para mostrar ayuda
            cursor.execute("SELECT tipo_personal FROM personal WHERE id = %s", (personal_id,))
            tipo_personal_data = cursor.fetchone()
            if tipo_personal_data and tipo_personal_data['tipo_personal'] in ['courier_externo', 'transportadora']:
                st.info("💡 **Courier/Transportadora:** Configure tarifas diferentes para sobres y paquetes en cada ciudad")

            with st.form(key=f"form_asignar_ciudad_{st.session_state.form_tarifa_counter}"):
                col1, col2 = st.columns(2)

                with col1:
                    cursor.execute("SELECT id, nombre FROM ciudades WHERE activa = TRUE ORDER BY nombre")
                    ciudades = cursor.fetchall()
                    ciudad_options = {c['nombre']: c['id'] for c in ciudades}
                    ciudad_sel = st.selectbox("Ciudad *", list(ciudad_options.keys()))

                with col2:
                    tipo_servicio = st.selectbox("Tipo Servicio *", ["sobre", "paquete"])

                col1, col2 = st.columns(2)
                with col1:
                    tarifa_entrega = st.number_input("Tarifa Entrega *", min_value=0.0, step=100.0)
                with col2:
                    tarifa_devolucion = st.number_input("Tarifa Devolución", min_value=0.0, step=100.0, value=0.0)

                col1, col2 = st.columns(2)
                with col1:
                    # Valor por defecto: 1 de enero del año actual
                    vigencia_desde = st.date_input("Vigencia Desde *", value=date(date.today().year, 1, 1))
                with col2:
                    sin_limite = st.checkbox("Sin fecha límite", value=True)
                    vigencia_hasta = None if sin_limite else st.date_input("Vigencia Hasta", value=date(date.today().year, 12, 31))

                submitted = st.form_submit_button("💾 Guardar")

                if submitted:
                    if tarifa_entrega <= 0:
                        st.error("La tarifa de entrega debe ser mayor a 0")
                    else:
                        try:
                            ciudad_id = ciudad_options[ciudad_sel]
                            cursor = conn.cursor()

                            # Verificar si ya existe la combinación
                            cursor.execute("""
                                SELECT id FROM personal_ciudades
                                WHERE personal_id = %s AND ciudad_id = %s AND tipo_servicio = %s AND activo = TRUE
                            """, (personal_id, ciudad_id, tipo_servicio))

                            if cursor.fetchone():
                                st.error(f"Ya existe una tarifa activa para {ciudad_sel} - {tipo_servicio}")
                            else:
                                cursor.execute("""
                                    INSERT INTO personal_ciudades
                                    (personal_id, ciudad_id, tipo_servicio, tarifa_entrega, tarifa_devolucion,
                                     vigencia_desde, vigencia_hasta, activo)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
                                """, (personal_id, ciudad_id, tipo_servicio, tarifa_entrega, tarifa_devolucion,
                                      vigencia_desde, vigencia_hasta))
                                conn.commit()
                                # Incrementar contador para limpiar formulario
                                st.session_state.form_tarifa_counter += 1
                                st.success("✅ Ciudad asignada exitosamente")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                            conn.rollback()

    except Exception as e:
        st.error(f"Error: {e}")

if 'cursor' in locals():
    cursor.close()
