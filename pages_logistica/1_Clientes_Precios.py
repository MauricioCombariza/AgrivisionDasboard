import streamlit as st
from datetime import datetime, date
import pandas as pd
import sys
import os

# Agregar el directorio raíz al path para importar utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_connection import conectar_logistica


st.title("👥 Gestión de Clientes y Precios")

conn = conectar_logistica()
if not conn:
    st.stop()

tab1, tab2, tab3 = st.tabs(["📋 Listar Clientes", "➕ Agregar/Editar Cliente", "💰 Gestión de Precios"])

with tab1:
    st.subheader("Lista de Clientes")

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                id, nombre_empresa, nit, contacto_nombre, contacto_telefono, contacto_email,
                direccion, ciudad, activo, fecha_creacion
            FROM clientes
            ORDER BY nombre_empresa
        """)
        clientes = cursor.fetchall()

        if clientes:
            df = pd.DataFrame(clientes)
            df['activo'] = df['activo'].apply(lambda x: '✅' if x else '❌')
            df['fecha_creacion'] = pd.to_datetime(df['fecha_creacion']).dt.strftime('%d/%m/%Y')

            st.dataframe(df, use_container_width=True, hide_index=True)
            st.metric("Total Clientes", len(clientes))
        else:
            st.info("No hay clientes registrados")
    except Exception as e:
        st.error(f"Error: {e}")

with tab2:
    st.subheader("Agregar/Editar Cliente")

    col1, col2 = st.columns([1, 3])

    with col1:
        modo = st.radio("Modo", ["Agregar Nuevo", "Editar Existente"])

    with col2:
        if modo == "Editar Existente":
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id, nombre_empresa FROM clientes ORDER BY nombre_empresa")
                clientes = cursor.fetchall()

                if clientes:
                    cliente_options = {f"{c['nombre_empresa']} (ID: {c['id']})": c['id'] for c in clientes}
                    cliente_sel = st.selectbox("Seleccionar Cliente", list(cliente_options.keys()))
                    cliente_id = cliente_options[cliente_sel]

                    cursor.execute("SELECT * FROM clientes WHERE id = %s", (cliente_id,))
                    cliente = cursor.fetchone()
                else:
                    st.warning("No hay clientes para editar")
                    cliente = None
            except Exception as e:
                st.error(f"Error: {e}")
                cliente = None
        else:
            cliente = None

    st.divider()

    with st.form("form_cliente"):
        col1, col2 = st.columns(2)

        with col1:
            nombre_empresa = st.text_input("Nombre Empresa *", value=cliente['nombre_empresa'] if cliente else "")
            nit = st.text_input("NIT *", value=cliente['nit'] if cliente else "")
            contacto_nombre = st.text_input("Contacto", value=cliente['contacto_nombre'] if cliente else "")

        with col2:
            contacto_telefono = st.text_input("Teléfono", value=cliente['contacto_telefono'] if cliente else "")
            contacto_email = st.text_input("Email", value=cliente['contacto_email'] if cliente else "")
            activo = st.checkbox("Activo", value=cliente['activo'] if cliente else True)

        direccion = st.text_area("Dirección", value=cliente['direccion'] if cliente else "")
        ciudad = st.text_input("Ciudad", value=cliente['ciudad'] if cliente else "")

        submitted = st.form_submit_button("💾 Guardar")

        if submitted:
            if not nombre_empresa or not nit:
                st.error("El nombre de empresa y NIT son obligatorios")
            else:
                try:
                    cursor = conn.cursor()

                    if modo == "Agregar Nuevo":
                        cursor.execute("""
                            INSERT INTO clientes
                            (nombre_empresa, nit, contacto_nombre, contacto_telefono, contacto_email, direccion, ciudad, activo)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (nombre_empresa, nit, contacto_nombre, contacto_telefono, contacto_email, direccion, ciudad, activo))
                        conn.commit()
                        st.success(f"✅ Cliente '{nombre_empresa}' agregado exitosamente")
                    else:
                        cursor.execute("""
                            UPDATE clientes SET
                            nombre_empresa = %s, nit = %s, contacto_nombre = %s,
                            contacto_telefono = %s, contacto_email = %s, direccion = %s, ciudad = %s, activo = %s
                            WHERE id = %s
                        """, (nombre_empresa, nit, contacto_nombre, contacto_telefono, contacto_email, direccion, ciudad, activo, cliente_id))
                        conn.commit()
                        st.success(f"✅ Cliente '{nombre_empresa}' actualizado exitosamente")

                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")
                    conn.rollback()

with tab3:
    st.subheader("Gestión de Precios por Cliente")

    # Inicializar contador de formulario para resetear campos
    if 'form_precio_counter' not in st.session_state:
        st.session_state.form_precio_counter = 0

    # === SECCIÓN: Actualización Masiva de Vigencia (TODOS LOS CLIENTES) ===
    with st.expander("🔄 ACTUALIZACIÓN MASIVA - Todos los Clientes", expanded=False):
        st.warning("⚠️ Esta opción actualiza la vigencia de TODOS los precios activos de TODOS los clientes en la base de datos.")

        cursor_stats = conn.cursor(dictionary=True)
        cursor_stats.execute("""
            SELECT COUNT(*) as total_precios, COUNT(DISTINCT cliente_id) as total_clientes
            FROM precios_cliente WHERE activo = TRUE
        """)
        stats = cursor_stats.fetchone()
        cursor_stats.close()

        st.info(f"📊 Actualmente hay **{stats['total_precios']} precios activos** de **{stats['total_clientes']} clientes**")

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            masiva_vigencia_desde = st.date_input(
                "Nueva Vigencia Desde (TODOS)",
                value=date(2025, 1, 1),
                key="masiva_vig_desde"
            )
        with col_m2:
            masiva_vigencia_hasta = st.date_input(
                "Nueva Vigencia Hasta (TODOS)",
                value=date(2025, 12, 31),
                key="masiva_vig_hasta"
            )

        confirmar_masivo = st.checkbox("✅ Confirmo que quiero actualizar TODOS los precios", key="confirmar_masivo")

        if st.button("🚀 ACTUALIZAR TODOS LOS PRECIOS", type="primary", disabled=not confirmar_masivo, key="btn_masivo"):
            if masiva_vigencia_hasta < masiva_vigencia_desde:
                st.error("La fecha 'hasta' debe ser posterior a la fecha 'desde'")
            else:
                try:
                    cursor_masivo = conn.cursor()
                    cursor_masivo.execute("""
                        UPDATE precios_cliente
                        SET vigencia_desde = %s, vigencia_hasta = %s
                        WHERE activo = TRUE
                    """, (masiva_vigencia_desde, masiva_vigencia_hasta))
                    filas_actualizadas = cursor_masivo.rowcount
                    conn.commit()
                    cursor_masivo.close()
                    st.success(f"✅ Se actualizaron **{filas_actualizadas} precios** con vigencia desde {masiva_vigencia_desde.strftime('%d/%m/%Y')} hasta {masiva_vigencia_hasta.strftime('%d/%m/%Y')}")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al actualizar: {e}")
                    conn.rollback()

    st.divider()

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, nombre_empresa FROM clientes WHERE activo = TRUE ORDER BY nombre_empresa")
        clientes = cursor.fetchall()

        if not clientes:
            st.warning("No hay clientes activos")
        else:
            cliente_options = {c['nombre_empresa']: c['id'] for c in clientes}
            cliente_sel = st.selectbox("Seleccionar Cliente", list(cliente_options.keys()))
            cliente_id = cliente_options[cliente_sel]

            st.divider()

            # === SECCIÓN: Actualizar Vigencia Retroactiva (por cliente) ===
            with st.expander("📅 Actualizar Vigencia - Solo este Cliente", expanded=False):
                st.info("Esta opción actualiza la fecha de vigencia de todos los precios activos del cliente seleccionado.")

                col_fecha1, col_fecha2 = st.columns(2)
                with col_fecha1:
                    nueva_vigencia_desde = st.date_input(
                        "Nueva Vigencia Desde",
                        value=date(2025, 1, 1),
                        key="nueva_vig_desde"
                    )
                with col_fecha2:
                    nueva_vigencia_hasta = st.date_input(
                        "Nueva Vigencia Hasta",
                        value=date(2025, 12, 31),
                        key="nueva_vig_hasta"
                    )

                if st.button("🔄 Actualizar Vigencia de Todos los Precios", type="primary", key="btn_actualizar_vigencia"):
                    if nueva_vigencia_hasta < nueva_vigencia_desde:
                        st.error("La fecha 'hasta' debe ser posterior a la fecha 'desde'")
                    else:
                        try:
                            cursor_update = conn.cursor()
                            # Actualizar vigencia de todos los precios activos del cliente
                            cursor_update.execute("""
                                UPDATE precios_cliente
                                SET vigencia_desde = %s, vigencia_hasta = %s
                                WHERE cliente_id = %s AND activo = TRUE
                            """, (nueva_vigencia_desde, nueva_vigencia_hasta, cliente_id))
                            filas_actualizadas = cursor_update.rowcount
                            conn.commit()
                            cursor_update.close()
                            st.success(f"✅ Se actualizaron {filas_actualizadas} precios con vigencia desde {nueva_vigencia_desde.strftime('%d/%m/%Y')} hasta {nueva_vigencia_hasta.strftime('%d/%m/%Y')}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar: {e}")
                            conn.rollback()

            st.divider()

            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown("### 📊 Precios Configurados")
                cursor.execute("""
                    SELECT
                        id, tipo_servicio, ambito, tipo_operacion, precio_unitario,
                        costo_mensajero_entrega, costo_mensajero_devolucion,
                        vigencia_desde, vigencia_hasta
                    FROM precios_cliente
                    WHERE cliente_id = %s AND activo = TRUE
                    ORDER BY tipo_servicio, ambito, tipo_operacion
                """, (cliente_id,))
                precios = cursor.fetchall()

                if precios:
                    df = pd.DataFrame(precios)
                    df['precio_unitario'] = df['precio_unitario'].apply(lambda x: f"${x:,.0f}")
                    # Mostrar costo mensajero solo para Bogotá
                    df['costo_mensajero'] = df.apply(
                        lambda row: f"${row['costo_mensajero_entrega']:,.0f}" if row['ambito'] == 'bogota' and row['costo_mensajero_entrega']
                        else (f"${row['costo_mensajero_devolucion']:,.0f}" if row['ambito'] == 'bogota' and row['costo_mensajero_devolucion']
                        else 'N/A'), axis=1
                    )
                    df['vigencia_desde'] = pd.to_datetime(df['vigencia_desde']).dt.strftime('%d/%m/%Y')
                    df['vigencia_hasta'] = pd.to_datetime(df['vigencia_hasta']).dt.strftime('%d/%m/%Y')
                    # Eliminar columnas internas antes de mostrar
                    df = df.drop(['costo_mensajero_entrega', 'costo_mensajero_devolucion'], axis=1)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info("No hay precios configurados para este cliente")

            with col2:
                st.markdown("### ✏️ Editar / 🗑️ Eliminar")
                if precios:
                    precio_options = {
                        f"{p['tipo_servicio']} - {p['ambito']} - {p['tipo_operacion']} (${p['precio_unitario']:,.0f})": p
                        for p in precios
                    }
                    precio_sel = st.selectbox("Seleccionar Precio", list(precio_options.keys()))
                    precio_data = precio_options[precio_sel]

                    col_edit, col_del = st.columns(2)
                    with col_edit:
                        if st.button("✏️ Editar", type="primary"):
                            st.session_state.precio_editar = precio_data
                            st.session_state.modo_precio = "editar"
                    with col_del:
                        if st.button("🗑️ Eliminar", type="secondary"):
                            try:
                                cursor = conn.cursor()
                                cursor.execute("UPDATE precios_cliente SET activo = FALSE WHERE id = %s", (precio_data['id'],))
                                conn.commit()
                                st.success("✅ Precio eliminado")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

            st.divider()

            # Determinar modo (agregar o editar)
            modo_precio = st.session_state.get('modo_precio', 'agregar')
            precio_editar = st.session_state.get('precio_editar', None)

            if modo_precio == "editar" and precio_editar:
                st.markdown("### ✏️ Editar Precio")
                if st.button("Cancelar edicion"):
                    st.session_state.modo_precio = "agregar"
                    st.session_state.precio_editar = None
                    st.rerun()
            else:
                st.markdown("### ➕ Agregar Nuevo Precio")
            st.info("💡 **Tip:** Las devoluciones se calculan automáticamente al 70% del precio de entrega")

            with st.form(key=f"form_precio_{st.session_state.form_precio_counter}"):
                col1, col2, col3 = st.columns(3)

                # Valores por defecto (modo agregar o editar)
                default_tipo_servicio = precio_editar['tipo_servicio'] if precio_editar else "sobre"
                default_ambito = precio_editar['ambito'] if precio_editar else "bogota"
                default_tipo_operacion = precio_editar['tipo_operacion'] if precio_editar else "entrega"

                with col1:
                    tipo_servicio = st.selectbox(
                        "Tipo Servicio *",
                        ["sobre", "paquete"],
                        index=["sobre", "paquete"].index(default_tipo_servicio),
                        disabled=(modo_precio == "editar")
                    )

                with col2:
                    ambito = st.selectbox(
                        "Ámbito *",
                        ["bogota", "nacional"],
                        index=["bogota", "nacional"].index(default_ambito),
                        disabled=(modo_precio == "editar")
                    )

                with col3:
                    tipo_operacion = st.selectbox(
                        "Tipo *",
                        ["entrega", "devolucion"],
                        index=["entrega", "devolucion"].index(default_tipo_operacion),
                        disabled=(modo_precio == "editar")
                    )

                # Mostrar ayuda según el ámbito
                if ambito == "bogota":
                    st.info("📍 **Ámbito Local:** Configure el precio que cobra al cliente y el costo del mensajero")
                else:
                    st.info("🌎 **Ámbito Nacional:** Configure solo el precio al cliente. El costo del courier se configura en Personal > Tarifas por Ciudad")

                precio_base = None
                if tipo_operacion == "devolucion":
                    try:
                        cursor.execute("""
                            SELECT precio_unitario FROM precios_cliente
                            WHERE cliente_id = %s
                            AND tipo_servicio = %s
                            AND ambito = %s
                            AND tipo_operacion = 'entrega'
                            AND activo = TRUE
                            ORDER BY vigencia_desde DESC
                            LIMIT 1
                        """, (cliente_id, tipo_servicio, ambito))
                        result = cursor.fetchone()
                        if result:
                            precio_base = result['precio_unitario']
                            precio_sugerido = precio_base * 0.7
                            st.success(f"✅ Precio de entrega encontrado: ${precio_base:,.0f}")
                            st.info(f"💡 Precio sugerido (70%): ${precio_sugerido:,.0f}")
                        else:
                            st.warning("⚠️ No existe precio de entrega para esta configuración")
                            precio_sugerido = 0
                    except:
                        precio_sugerido = 0
                else:
                    precio_sugerido = 0

                col1, col2 = st.columns(2)

                # Valores por defecto para precio y costo
                if precio_editar:
                    default_precio = float(precio_editar['precio_unitario'])
                    if precio_editar['tipo_operacion'] == 'entrega':
                        default_costo = float(precio_editar['costo_mensajero_entrega'] or 0)
                    else:
                        default_costo = float(precio_editar['costo_mensajero_devolucion'] or 0)
                    default_vigencia_desde = precio_editar['vigencia_desde']
                    default_vigencia_hasta = precio_editar['vigencia_hasta']
                else:
                    default_precio = float(precio_sugerido) if precio_sugerido > 0 else 0.0
                    default_costo = 0.0
                    default_vigencia_desde = date.today()
                    default_vigencia_hasta = date(2025, 12, 31)

                with col1:
                    precio = st.number_input(
                        "Precio al Cliente *",
                        min_value=0.0,
                        value=default_precio,
                        step=100.0,
                        help="Precio que cobra al cliente"
                    )

                with col2:
                    # Solo mostrar campos de costo mensajero para ámbito Bogotá
                    if ambito == "bogota":
                        costo_mensajero = st.number_input(
                            "Costo Mensajero *",
                            min_value=0.0,
                            value=default_costo,
                            step=100.0,
                            help="Lo que se le paga al mensajero"
                        )
                    else:
                        costo_mensajero = None
                        st.write("")  # Espacio vacío para mantener layout

                col1, col2 = st.columns(2)
                with col1:
                    vigencia_desde = st.date_input("Vigencia Desde *", value=default_vigencia_desde)
                with col2:
                    vigencia_hasta = st.date_input("Vigencia Hasta *", value=default_vigencia_hasta)

                btn_text = "💾 Actualizar Precio" if modo_precio == "editar" else "💾 Guardar Precio"
                submitted = st.form_submit_button(btn_text)

                if submitted:
                    if precio <= 0:
                        st.error("El precio debe ser mayor a 0")
                    elif vigencia_hasta < vigencia_desde:
                        st.error("La fecha 'hasta' debe ser posterior a la fecha 'desde'")
                    elif ambito == "bogota" and (costo_mensajero is None or costo_mensajero <= 0):
                        st.error("Para ámbito Bogotá, debe configurar el costo del mensajero")
                    else:
                        try:
                            cursor = conn.cursor()

                            # Preparar valores según el ámbito
                            if ambito == "bogota":
                                if tipo_operacion == "entrega":
                                    costo_entrega = costo_mensajero
                                    costo_devolucion = None
                                else:
                                    costo_entrega = None
                                    costo_devolucion = costo_mensajero
                            else:
                                costo_entrega = None
                                costo_devolucion = None

                            if modo_precio == "editar" and precio_editar:
                                # Actualizar precio existente
                                cursor.execute("""
                                    UPDATE precios_cliente SET
                                    precio_unitario = %s,
                                    costo_mensajero_entrega = %s,
                                    costo_mensajero_devolucion = %s,
                                    vigencia_desde = %s,
                                    vigencia_hasta = %s
                                    WHERE id = %s
                                """, (precio, costo_entrega, costo_devolucion,
                                      vigencia_desde, vigencia_hasta, precio_editar['id']))
                                conn.commit()
                                st.session_state.modo_precio = "agregar"
                                st.session_state.precio_editar = None
                                st.session_state.form_precio_counter += 1
                                st.success("✅ Precio actualizado exitosamente")
                            else:
                                # Desactivar precios anteriores del mismo tipo
                                cursor.execute("""
                                    UPDATE precios_cliente
                                    SET activo = FALSE
                                    WHERE cliente_id = %s
                                      AND tipo_servicio = %s
                                      AND ambito = %s
                                      AND tipo_operacion = %s
                                      AND activo = TRUE
                                """, (cliente_id, tipo_servicio, ambito, tipo_operacion))
                                precios_desactivados = cursor.rowcount

                                # Insertar nuevo precio
                                cursor.execute("""
                                    INSERT INTO precios_cliente
                                    (cliente_id, tipo_servicio, ambito, tipo_operacion, precio_unitario,
                                     costo_mensajero_entrega, costo_mensajero_devolucion,
                                     vigencia_desde, vigencia_hasta, activo)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                                """, (cliente_id, tipo_servicio, ambito, tipo_operacion, precio,
                                      costo_entrega, costo_devolucion,
                                      vigencia_desde, vigencia_hasta))
                                conn.commit()
                                st.session_state.form_precio_counter += 1
                                msg = "✅ Precio agregado exitosamente"
                                if precios_desactivados > 0:
                                    msg += f" ({precios_desactivados} precio(s) anterior(es) desactivado(s))"
                                st.success(msg)

                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                            conn.rollback()

    except Exception as e:
        st.error(f"Error: {e}")

if 'cursor' in locals():
    cursor.close()
