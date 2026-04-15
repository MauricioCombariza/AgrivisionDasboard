import streamlit as st
import pandas as pd
from datetime import date
from pathlib import Path
import sys
import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils.db_connection import conectar_logistica


def _conectar_bases_web():
    """Conexión de lectura a bases_web (tabla histo) para obtener ciudad1 por serial."""
    try:
        return mysql.connector.connect(
            host=os.environ.get("DB_HOST_BASES_WEB", "186.180.15.66"),
            port=int(os.environ.get("DB_PORT_BASES_WEB", "12539")),
            user=os.environ.get("DB_USER_BASES_WEB", "servilla_remoto"),
            password=os.environ.get("DB_PASSWORD_BASES_WEB", ""),
            database=os.environ.get("DB_NAME_BASES_WEB", "bases_web"),
            connect_timeout=10,
        )
    except Exception as e:
        st.warning(f"No se pudo conectar a bases_web: {e}")
        return None

st.title("📑 Planillas Mensajeros Check")

conn = conectar_logistica()
if not conn:
    st.stop()

# Inicializar estado para edicion
if 'editando_planilla' not in st.session_state:
    st.session_state.editando_planilla = None

# Inicializar estado para filas auditadas (checkeadas)
if 'filas_auditadas' not in st.session_state:
    st.session_state.filas_auditadas = set()

# Inicializar estado para busqueda de planilla
if 'planilla_buscada' not in st.session_state:
    st.session_state.planilla_buscada = None

try:
    cursor = conn.cursor(dictionary=True)

    # Migraciones de esquema: se ejecutan una vez y fallan silenciosamente si ya existen
    for _migration_sql in [
        "ALTER TABLE gestiones_mensajero ADD COLUMN editado_manualmente TINYINT(1) NOT NULL DEFAULT 0",
        "ALTER TABLE personal ADD COLUMN precio_local DECIMAL(10,0) NULL DEFAULT NULL",
        "ALTER TABLE personal ADD COLUMN precio_nacional DECIMAL(10,0) NULL DEFAULT NULL",
        # Tabla para persistir la clasificación local/nacional por ciudad (courier externo)
        """CREATE TABLE IF NOT EXISTS ciudad_tipo (
            ciudad    VARCHAR(150) NOT NULL PRIMARY KEY,
            tipo      ENUM('local','nacional') NOT NULL DEFAULT 'nacional',
            fecha_mod DATE NULL
        )""",
    ]:
        try:
            _cur_init = conn.cursor()
            _cur_init.execute(_migration_sql)
            conn.commit()
            _cur_init.close()
        except Exception:
            conn.rollback()

    # Crear tabla planillas_revisadas si no existe
    try:
        _cur_rev = conn.cursor()
        _cur_rev.execute("""
            CREATE TABLE IF NOT EXISTS planillas_revisadas (
                lot_esc   VARCHAR(100) NOT NULL PRIMARY KEY,
                fecha_revision DATE NOT NULL
            )
        """)
        conn.commit()
        _cur_rev.close()
    except Exception:
        conn.rollback()

    # Cargar planillas revisadas en memoria para esta ejecución
    cursor.execute("SELECT lot_esc FROM planillas_revisadas")
    planillas_revisadas_set = {r['lot_esc'] for r in cursor.fetchall()}

    # =====================================================
    # BUSCADOR DE PLANILLA POR NUMERO
    # =====================================================
    with st.expander("Buscar Planilla por Numero", expanded=False):
        st.markdown("#### Buscar y Editar Planilla")

        col_busq1, col_busq2 = st.columns([2, 1])

        with col_busq1:
            numero_planilla_buscar = st.text_input(
                "Numero de Planilla",
                value="",
                key="input_buscar_planilla",
                placeholder="Ingrese el numero de planilla..."
            )

        with col_busq2:
            btn_buscar = st.button("Buscar", key="btn_buscar_planilla", type="primary")

        if btn_buscar and numero_planilla_buscar:
            # Forzar nueva transaccion para ver cambios recientes
            conn.commit()
            # Buscar la planilla en la base de datos
            cursor.execute("""
                SELECT
                    gm.id,
                    gm.lot_esc as planilla,
                    gm.fecha_escaner as f_esc,
                    gm.total_seriales as cantidad_seriales,
                    gm.valor_unitario as precio,
                    gm.valor_total,
                    gm.cod_mensajero,
                    gm.cliente,
                    gm.tipo_gestion,
                    gm.orden,
                    gm.editado_manualmente,
                    p.nombre_completo as nombre_mensajero,
                    p.tipo_personal,
                    p.precio_local,
                    p.precio_nacional
                FROM gestiones_mensajero gm
                LEFT JOIN personal p ON gm.cod_mensajero = p.codigo
                WHERE gm.lot_esc = %s
                ORDER BY gm.fecha_escaner ASC
            """, (numero_planilla_buscar,))
            resultados_busqueda = cursor.fetchall()

            if resultados_busqueda:
                st.session_state.planilla_buscada = {
                    'numero': numero_planilla_buscar,
                    'registros': resultados_busqueda
                }
            else:
                st.session_state.planilla_buscada = None
                st.warning(f"No se encontro la planilla {numero_planilla_buscar}")

        # Mostrar resultados de busqueda
        if st.session_state.planilla_buscada:
            registros = st.session_state.planilla_buscada['registros']
            num_planilla = st.session_state.planilla_buscada['numero']

            _is_rev_busq = num_planilla in planillas_revisadas_set
            col_hdr1, col_hdr2 = st.columns([3, 1])
            with col_hdr1:
                st.success(f"Planilla **{num_planilla}** encontrada - {len(registros)} registro(s)")
            with col_hdr2:
                if _is_rev_busq:
                    if st.button("🔄 Desmarcar Revisión", key="btn_unrev_busq",
                                 help="Quitar revisión — la sincronización podrá modificar esta planilla"):
                        try:
                            _cur = conn.cursor()
                            _cur.execute("DELETE FROM planillas_revisadas WHERE lot_esc = %s", (num_planilla,))
                            conn.commit()
                            _cur.close()
                            planillas_revisadas_set.discard(num_planilla)
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error: {e}")
                else:
                    if st.button("✅ Marcar como Revisada", key="btn_rev_busq",
                                 help="Marcar como revisada — la sincronización no podrá modificar esta planilla"):
                        try:
                            _cur = conn.cursor()
                            _cur.execute(
                                "INSERT IGNORE INTO planillas_revisadas (lot_esc, fecha_revision) VALUES (%s, CURDATE())",
                                (num_planilla,)
                            )
                            conn.commit()
                            _cur.close()
                            planillas_revisadas_set.add(num_planilla)
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error: {e}")

            df_busq = pd.DataFrame(registros)

            # Detectar si el mensajero es courier_externo para mostrar vista por ciudad
            _tipo_personal = df_busq['tipo_personal'].iloc[0] if not df_busq.empty else None
            es_courier_externo_busq = (_tipo_personal == 'courier_externo')
            precio_local_busq   = float(df_busq['precio_local'].iloc[0]   or 0) if not df_busq.empty else 0.0
            precio_nacional_busq = float(df_busq['precio_nacional'].iloc[0] or 0) if not df_busq.empty else 0.0

            # Obtener lista de mensajeros para el selector
            cursor.execute("""
                SELECT codigo, nombre_completo
                FROM personal
                WHERE activo = TRUE
                AND tipo_personal IN ('mensajero', 'courier_externo', 'alistamiento')
                ORDER BY codigo
            """)
            lista_mensajeros = cursor.fetchall()
            opciones_mensajeros = {f"{m['codigo']} - {m['nombre_completo']}": m['codigo'] for m in lista_mensajeros}

            # =====================================================
            # CAMBIAR MENSAJERO DE TODA LA PLANILLA
            # =====================================================
            mensajeros_en_planilla = df_busq['cod_mensajero'].unique()
            total_seriales_planilla = df_busq['cantidad_seriales'].sum()
            total_valor_planilla = df_busq['valor_total'].astype(float).sum()

            st.markdown("##### Cambiar Mensajero de toda la Planilla")

            col_m1, col_m2, col_m3 = st.columns([1.5, 1.5, 1])
            with col_m1:
                st.write(f"**Mensajero(s) actual(es):** {', '.join(mensajeros_en_planilla)}")
                st.write(f"**Registros:** {len(registros)} | **Seriales:** {total_seriales_planilla:,} | **Valor:** ${total_valor_planilla:,.0f}")

            with col_m2:
                nuevo_men_planilla = st.selectbox(
                    "Nuevo Mensajero para toda la planilla",
                    options=["-- Seleccionar --"] + list(opciones_mensajeros.keys()),
                    key="select_men_toda_planilla"
                )

            with col_m3:
                st.write("")
                st.write("")
                if nuevo_men_planilla != "-- Seleccionar --":
                    nuevo_cod_planilla = opciones_mensajeros[nuevo_men_planilla]
                    if st.button("Aplicar a toda la planilla", type="primary", key="btn_cambiar_men_planilla"):
                        try:
                            cursor_upd = conn.cursor(dictionary=True)

                            # Obtener mensajero_id del nuevo codigo para actualizar la FK
                            cursor_upd.execute(
                                "SELECT id FROM personal WHERE codigo = %s LIMIT 1",
                                (nuevo_cod_planilla,)
                            )
                            _men_row = cursor_upd.fetchone()
                            nuevo_men_id = _men_row['id'] if _men_row else None

                            ids_planilla = df_busq['id'].tolist()
                            actualizados = 0
                            fusionados = 0
                            eliminados_ids = []

                            for gestion_id in ids_planilla:
                                # Saltar si ya fue eliminado por fusion
                                if gestion_id in eliminados_ids:
                                    continue

                                # Obtener datos del registro actual
                                cursor_upd.execute("""
                                    SELECT id, lot_esc, orden, tipo_gestion, cliente, cod_mensajero,
                                           total_seriales, valor_unitario, valor_total, editado_manualmente
                                    FROM gestiones_mensajero WHERE id = %s
                                """, (gestion_id,))
                                reg = cursor_upd.fetchone()

                                if not reg or reg['cod_mensajero'] == nuevo_cod_planilla:
                                    continue

                                # Verificar si ya existe un registro con el nuevo mensajero
                                cursor_upd.execute("""
                                    SELECT id, total_seriales, valor_unitario, valor_total
                                    FROM gestiones_mensajero
                                    WHERE lot_esc = %s AND orden = %s AND tipo_gestion = %s
                                    AND cliente = %s AND cod_mensajero = %s AND id != %s
                                """, (reg['lot_esc'], reg['orden'], reg['tipo_gestion'],
                                      reg['cliente'], nuevo_cod_planilla, gestion_id))

                                existente = cursor_upd.fetchone()

                                if existente:
                                    # Fusionar: sumar seriales al registro existente y bloquearlo
                                    nuevos_seriales = existente['total_seriales'] + reg['total_seriales']
                                    nuevo_valor = nuevos_seriales * float(existente['valor_unitario'])

                                    cursor_upd.execute("""
                                        UPDATE gestiones_mensajero
                                        SET total_seriales = %s, valor_total = %s,
                                            editado_manualmente = 1
                                        WHERE id = %s
                                    """, (nuevos_seriales, nuevo_valor, existente['id']))

                                    # Eliminar el registro duplicado
                                    cursor_upd.execute("""
                                        DELETE FROM gestiones_mensajero WHERE id = %s
                                    """, (gestion_id,))

                                    eliminados_ids.append(gestion_id)
                                    fusionados += 1
                                else:
                                    # No hay duplicado, reasignar mensajero y bloquear
                                    cursor_upd.execute("""
                                        UPDATE gestiones_mensajero
                                        SET cod_mensajero = %s, mensajero_id = %s,
                                            editado_manualmente = 1
                                        WHERE id = %s
                                    """, (nuevo_cod_planilla, nuevo_men_id, gestion_id))
                                    actualizados += 1

                            # Marcar la planilla como revisada para que sync no reinserte
                            cursor_upd.execute("""
                                INSERT IGNORE INTO planillas_revisadas (lot_esc, fecha_revision)
                                VALUES (%s, CURDATE())
                            """, (num_planilla,))
                            planillas_revisadas_set.add(num_planilla)

                            conn.commit()
                            cursor_upd.close()

                            msg = f"Planilla {num_planilla}: "
                            if actualizados > 0:
                                msg += f"{actualizados} registro(s) reasignados"
                            if fusionados > 0:
                                if actualizados > 0:
                                    msg += f", "
                                msg += f"{fusionados} registro(s) fusionados"
                            msg += f" a mensajero {nuevo_cod_planilla} — planilla bloqueada ✅"
                            st.success(msg)

                            st.session_state.planilla_buscada = None
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error: {e}")

            st.divider()

            if es_courier_externo_busq:
                # =====================================================
                # COURIER EXTERNO: AJUSTE DE PRECIO POR CIUDAD
                # 1. Consulta histo para obtener ciudad1 por serial
                # 2. Muestra agrupación por ciudad con selector local/nacional
                # 3. Persiste clasificación en tabla ciudad_tipo
                # 4. Recalcula valor de cada registro de gestiones_mensajero
                #    según cuántos de sus seriales son local vs nacional
                # =====================================================
                st.markdown("##### 🏙️ Ajuste de Precio por Ciudad (Courier Externo)")

                # ── Tarifas del mensajero ────────────────────────────────────
                col_tar1, col_tar2 = st.columns(2)
                with col_tar1:
                    precio_local_edit = st.number_input(
                        "Tarifa Local ($/serial)",
                        min_value=0.0, value=precio_local_busq, step=500.0, format="%.0f",
                        key="tar_local_busq"
                    )
                with col_tar2:
                    precio_nac_edit = st.number_input(
                        "Tarifa Nacional ($/serial)",
                        min_value=0.0, value=precio_nacional_busq, step=500.0, format="%.0f",
                        key="tar_nac_busq"
                    )

                if precio_local_edit != precio_local_busq or precio_nac_edit != precio_nacional_busq:
                    if st.button("💾 Guardar tarifas del mensajero", key="btn_save_tarifas_busq"):
                        try:
                            _cur_tar = conn.cursor()
                            _cur_tar.execute(
                                "UPDATE personal SET precio_local=%s, precio_nacional=%s WHERE codigo=%s",
                                (precio_local_edit, precio_nac_edit, df_busq['cod_mensajero'].iloc[0])
                            )
                            conn.commit()
                            _cur_tar.close()
                            st.success("Tarifas guardadas")
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error: {e}")

                # ── Cargar clasificaciones previas de ciudad_tipo ───────────
                try:
                    _cur_ct = conn.cursor(dictionary=True)
                    _cur_ct.execute("SELECT ciudad, tipo FROM ciudad_tipo")
                    ciudad_tipo_guardado = {r['ciudad']: r['tipo'] for r in _cur_ct.fetchall()}
                    _cur_ct.close()
                except Exception:
                    ciudad_tipo_guardado = {}

                # ── Consultar histo: seriales de la planilla agrupados por ciudad1 ──
                cod_men_planilla = str(df_busq['cod_mensajero'].iloc[0])
                lot_esc_planilla = str(num_planilla)

                conn_bw = _conectar_bases_web()
                df_ciudades = pd.DataFrame()

                if conn_bw:
                    try:
                        cur_bw = conn_bw.cursor(dictionary=True)
                        # Agrupa por ciudad1 para ver cuántos seriales van a cada destino
                        cur_bw.execute("""
                            SELECT
                                COALESCE(NULLIF(TRIM(ciudad1), ''), 'Sin ciudad') AS ciudad,
                                COUNT(*) AS seriales
                            FROM histo
                            WHERE lot_esc = %s AND cod_men = %s
                            GROUP BY ciudad
                            ORDER BY seriales DESC
                        """, (lot_esc_planilla, cod_men_planilla))
                        rows_bw = cur_bw.fetchall()
                        cur_bw.close()
                        conn_bw.close()

                        if rows_bw:
                            df_ciudades = pd.DataFrame(rows_bw)
                            # Pre-rellenar tipo desde clasificaciones guardadas
                            df_ciudades['tipo'] = df_ciudades['ciudad'].map(
                                lambda c: ciudad_tipo_guardado.get(c, 'nacional')
                            )
                        else:
                            st.warning("No se encontraron seriales en histo para esta planilla y mensajero.")
                    except Exception as e_bw:
                        st.warning(f"Error al consultar histo: {e_bw}")

                if df_ciudades.empty:
                    st.info("Sin datos de ciudad desde histo. Usa el ajuste manual abajo.")
                else:
                    # ── Tabla editable: una fila por ciudad ─────────────────
                    st.caption(
                        "Clasifica cada ciudad como **local** o **nacional**. "
                        "La clasificación se guarda para futuras planillas del mismo mensajero."
                    )

                    df_editor_ciudades = df_ciudades[['ciudad', 'seriales', 'tipo']].copy()
                    df_editor_ciudades.columns = ['Ciudad', 'Seriales', 'Tipo']

                    df_ciudad_editado = st.data_editor(
                        df_editor_ciudades,
                        column_config={
                            'Ciudad':   st.column_config.TextColumn('Ciudad', disabled=True),
                            'Seriales': st.column_config.NumberColumn('Seriales', disabled=True),
                            'Tipo': st.column_config.SelectboxColumn(
                                'Tipo', options=['local', 'nacional'], required=True
                            ),
                        },
                        use_container_width=True,
                        hide_index=True,
                        key="editor_ciudades_busq"
                    )

                    # Calcular resumen local / nacional con las tarifas actuales
                    tipo_map = dict(zip(df_ciudad_editado['Ciudad'], df_ciudad_editado['Tipo']))
                    df_ciudad_editado['Precio'] = df_ciudad_editado['Tipo'].map(
                        {'local': precio_local_edit, 'nacional': precio_nac_edit}
                    )
                    df_ciudad_editado['Valor'] = df_ciudad_editado['Seriales'] * df_ciudad_editado['Precio']

                    total_loc  = df_ciudad_editado[df_ciudad_editado['Tipo'] == 'local']['Seriales'].sum()
                    total_nac  = df_ciudad_editado[df_ciudad_editado['Tipo'] == 'nacional']['Seriales'].sum()
                    total_val  = df_ciudad_editado['Valor'].sum()
                    st.dataframe(
                        df_ciudad_editado[['Ciudad', 'Seriales', 'Tipo', 'Precio', 'Valor']],
                        use_container_width=True, hide_index=True
                    )
                    st.info(
                        f"Local: **{total_loc:,}** seriales × ${precio_local_edit:,.0f} | "
                        f"Nacional: **{total_nac:,}** seriales × ${precio_nac_edit:,.0f} | "
                        f"**Total: ${total_val:,.0f}**"
                    )

                    if st.button("💾 Aplicar clasificación y actualizar precios", type="primary", key="btn_aplicar_ciudad_busq"):
                        try:
                            cursor_upd = conn.cursor()

                            # 1. Persistir clasificaciones en ciudad_tipo para uso futuro
                            for _, cr in df_ciudad_editado.iterrows():
                                cursor_upd.execute("""
                                    INSERT INTO ciudad_tipo (ciudad, tipo, fecha_mod)
                                    VALUES (%s, %s, CURDATE())
                                    ON DUPLICATE KEY UPDATE tipo = VALUES(tipo), fecha_mod = CURDATE()
                                """, (cr['Ciudad'], cr['Tipo']))

                            # 2. Para cada registro de gestiones_mensajero en la planilla,
                            #    recalcular valor según cuántos de sus seriales son local vs nacional.
                            #    Se consulta histo agrupado por (orden, ciudad1) para ese registro.
                            conn_bw2 = _conectar_bases_web()
                            errores_upd = []

                            for _, gm_row in df_busq.iterrows():
                                gestion_id = int(gm_row['id'])
                                orden_gm   = str(gm_row['orden'])

                                if conn_bw2:
                                    try:
                                        cur_bw2 = conn_bw2.cursor(dictionary=True)
                                        cur_bw2.execute("""
                                            SELECT
                                                COALESCE(NULLIF(TRIM(ciudad1), ''), 'Sin ciudad') AS ciudad,
                                                COUNT(*) AS cnt
                                            FROM histo
                                            WHERE lot_esc = %s AND cod_men = %s AND orden = %s
                                            GROUP BY ciudad
                                        """, (lot_esc_planilla, cod_men_planilla, orden_gm))
                                        ciudad_rows = cur_bw2.fetchall()
                                        cur_bw2.close()

                                        # Calcular valor: cada ciudad aporta según su tipo
                                        nuevo_valor = 0.0
                                        for cr in ciudad_rows:
                                            t = tipo_map.get(cr['ciudad'], 'nacional')
                                            p = precio_local_edit if t == 'local' else precio_nac_edit
                                            nuevo_valor += cr['cnt'] * p

                                        total_ser = int(gm_row['cantidad_seriales'])
                                        # precio_unitario = promedio ponderado
                                        precio_unit = nuevo_valor / total_ser if total_ser > 0 else 0.0

                                    except Exception as e_ord:
                                        errores_upd.append(f"Gestion {gestion_id}: {e_ord}")
                                        nuevo_valor  = float(gm_row['valor_total'])
                                        precio_unit  = float(gm_row['precio'])
                                else:
                                    # Sin conexión a histo: usar proporción global local/nacional
                                    total_histo = total_loc + total_nac
                                    if total_histo > 0:
                                        prop_loc = total_loc / total_histo
                                        prop_nac = total_nac / total_histo
                                    else:
                                        prop_loc, prop_nac = 0, 1
                                    total_ser    = int(gm_row['cantidad_seriales'])
                                    nuevo_valor  = total_ser * (prop_loc * precio_local_edit + prop_nac * precio_nac_edit)
                                    precio_unit  = nuevo_valor / total_ser if total_ser > 0 else 0.0

                                cursor_upd.execute("""
                                    UPDATE gestiones_mensajero
                                    SET valor_unitario = %s, valor_total = %s, editado_manualmente = 1
                                    WHERE id = %s
                                """, (round(precio_unit, 2), round(nuevo_valor, 2), gestion_id))

                            if conn_bw2:
                                conn_bw2.close()

                            conn.commit()
                            cursor_upd.close()

                            if errores_upd:
                                st.warning(f"{len(errores_upd)} registro(s) con error: {errores_upd[:5]}")
                            st.success(f"✅ Precios actualizados por ciudad — Total planilla: ${total_val:,.0f}")
                            st.session_state.planilla_buscada = None
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error: {e}")

            else:
                # =====================================================
                # MENSAJERO REGULAR: AJUSTAR PRECIO ÚNICO DE LA PLANILLA
                # =====================================================
                st.markdown("##### Ajustar Precio de toda la Planilla")

                precios_actuales = df_busq['precio'].astype(float).unique()
                precios_str = ", ".join([f"${p:,.0f}" for p in sorted(precios_actuales)])
                precio_promedio_planilla = float(df_busq['valor_total'].astype(float).sum() / total_seriales_planilla) if total_seriales_planilla > 0 else 0.0

                col_p1, col_p2, col_p3 = st.columns([1.5, 1.5, 1])

                with col_p1:
                    st.write(f"**Precio(s) actual(es):** {precios_str}")
                    st.write(f"**Seriales:** {total_seriales_planilla:,} | **Valor actual:** ${total_valor_planilla:,.0f}")

                with col_p2:
                    nuevo_precio_planilla = st.number_input(
                        "Nuevo Precio Unitario ($)",
                        min_value=0.0,
                        value=precio_promedio_planilla,
                        step=50.0,
                        key="nuevo_precio_toda_planilla"
                    )
                    nuevo_valor_total_planilla = total_seriales_planilla * nuevo_precio_planilla
                    st.caption(f"Nuevo valor total: **${nuevo_valor_total_planilla:,.0f}**")

                with col_p3:
                    st.write("")
                    st.write("")
                    if nuevo_precio_planilla != precio_promedio_planilla or len(precios_actuales) > 1:
                        if st.button("Aplicar precio a toda la planilla", type="primary", key="btn_cambiar_precio_planilla"):
                            try:
                                cursor_upd = conn.cursor()
                                ids_planilla = df_busq['id'].tolist()
                                actualizados_precio = 0

                                for gestion_id in ids_planilla:
                                    cursor_upd.execute(
                                        "SELECT total_seriales FROM gestiones_mensajero WHERE id = %s",
                                        (gestion_id,)
                                    )
                                    res = cursor_upd.fetchone()
                                    if res:
                                        valor_reg = res[0] * nuevo_precio_planilla
                                        cursor_upd.execute("""
                                            UPDATE gestiones_mensajero
                                            SET valor_unitario = %s, valor_total = %s, editado_manualmente = 1
                                            WHERE id = %s
                                        """, (nuevo_precio_planilla, valor_reg, gestion_id))
                                        actualizados_precio += 1

                                conn.commit()
                                cursor_upd.close()
                                msg_precio = f"Planilla {num_planilla}: precio actualizado a ${nuevo_precio_planilla:,.0f} en {actualizados_precio} registro(s)"
                                st.success(msg_precio)
                                st.session_state.planilla_buscada = None
                                st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"Error: {e}")

            st.divider()

            # =====================================================
            # DETALLE POR CLIENTE Y ORDEN
            # =====================================================
            st.markdown("##### Detalle por Cliente y Orden")

            # Encabezados
            hcol0, hcol1, hcol2, hcol3, hcol4, hcol5, hcol6, hcol7, hcol8 = st.columns([0.4, 1.2, 1.5, 0.8, 1, 1, 1.2, 0.8, 0.5])
            hcol0.write("**Sel**")
            hcol1.write("**Orden**")
            hcol2.write("**Cliente**")
            hcol3.write("**Seriales**")
            hcol4.write("**Precio**")
            hcol5.write("**Valor**")
            hcol6.write("**Mensajero**")
            hcol7.write("**Fecha**")
            hcol8.write("**🔒**")

            st.markdown("---")

            # Inicializar selecciones si no existen
            if 'seleccion_registros_busq' not in st.session_state:
                st.session_state.seleccion_registros_busq = set()

            # Mostrar cada registro individual
            registros_seleccionados = []
            total_sel_seriales = 0
            total_sel_valor = 0.0

            for idx, row in df_busq.iterrows():
                fecha_str = row['f_esc'].strftime('%Y-%m-%d') if hasattr(row['f_esc'], 'strftime') else str(row['f_esc'])
                row_id = row['id']
                is_protected = bool(row.get('editado_manualmente', 0))

                c0, c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([0.4, 1.2, 1.5, 0.8, 1, 1, 1.2, 0.8, 0.5])

                with c0:
                    is_selected = st.checkbox(
                        "",
                        value=row_id in st.session_state.seleccion_registros_busq,
                        key=f"sel_busq_{row_id}",
                        label_visibility="collapsed"
                    )
                    if is_selected:
                        st.session_state.seleccion_registros_busq.add(row_id)
                        registros_seleccionados.append(row)
                        total_sel_seriales += row['cantidad_seriales']
                        total_sel_valor += float(row['valor_total'])
                    elif row_id in st.session_state.seleccion_registros_busq:
                        st.session_state.seleccion_registros_busq.discard(row_id)

                c1.write(f"{row['orden'] or '-'}")
                c2.write(f"{row['cliente'] or '-'}")
                c3.write(f"{row['cantidad_seriales']}")
                c4.write(f"${float(row['precio']):,.0f}")
                c5.write(f"${float(row['valor_total']):,.0f}")
                c6.write(f"{row['cod_mensajero']}")
                c7.write(fecha_str)

                with c8:
                    if is_protected:
                        if st.button("🔓", key=f"unlock_busq_{row_id}", help="Quitar protección manual"):
                            try:
                                _cur = conn.cursor()
                                _cur.execute(
                                    "UPDATE gestiones_mensajero SET editado_manualmente = 0 WHERE id = %s",
                                    (row_id,)
                                )
                                conn.commit()
                                _cur.close()
                                st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"Error: {e}")
                    else:
                        st.caption("—")

            # Botones de seleccion rapida
            st.markdown("---")
            col_sel1, col_sel2, col_sel3 = st.columns([1, 1, 2])
            with col_sel1:
                if st.button("Seleccionar Todos", key="btn_sel_todos_busq"):
                    st.session_state.seleccion_registros_busq = set(df_busq['id'].tolist())
                    st.rerun()
            with col_sel2:
                if st.button("Deseleccionar Todos", key="btn_desel_todos_busq"):
                    st.session_state.seleccion_registros_busq = set()
                    st.rerun()

            # =====================================================
            # EDICION DE REGISTROS SELECCIONADOS
            # =====================================================
            if registros_seleccionados:
                st.markdown("##### Editar Registros Seleccionados")

                # Crear DataFrame de seleccionados y agrupar por cliente/orden
                df_seleccionados = pd.DataFrame(registros_seleccionados)
                df_sel_agrupado = df_seleccionados.groupby(['cliente', 'orden']).agg({
                    'cantidad_seriales': 'sum',
                    'valor_total': 'sum',
                    'precio': 'first',
                    'id': lambda x: list(x)
                }).reset_index()

                # Mostrar detalle de seleccion por cliente/orden
                st.markdown("**Detalle de Seleccion:**")

                # Encabezados
                eh1, eh2, eh3, eh4, eh5 = st.columns([1.5, 1.2, 0.8, 1.2, 1.5])
                eh1.write("**Cliente**")
                eh2.write("**Orden**")
                eh3.write("**Registros**")
                eh4.write("**Seriales**")
                eh5.write("**Valor Actual**")

                for _, grp in df_sel_agrupado.iterrows():
                    ec1, ec2, ec3, ec4, ec5 = st.columns([1.5, 1.2, 0.8, 1.2, 1.5])
                    ec1.write(f"{grp['cliente'] or '-'}")
                    ec2.write(f"{grp['orden'] or '-'}")
                    ec3.write(f"{len(grp['id'])}")
                    ec4.write(f"{grp['cantidad_seriales']:,}")
                    ec5.write(f"${float(grp['valor_total']):,.0f}")

                st.markdown("---")

                # Resumen total
                st.info(f"**Total:** {len(registros_seleccionados)} registro(s) | "
                       f"**Seriales:** {total_sel_seriales:,} | "
                       f"**Valor actual:** ${total_sel_valor:,.0f}")

                st.markdown("**Aplicar Cambios:**")

                col_edit1, col_edit2 = st.columns(2)

                with col_edit1:
                    nuevo_mensajero_busq = st.selectbox(
                        "Nuevo Mensajero",
                        options=["(Sin cambio)"] + list(opciones_mensajeros.keys()),
                        key="select_nuevo_mensajero_busq"
                    )

                with col_edit2:
                    # Precio promedio de seleccionados
                    precio_prom = total_sel_valor / total_sel_seriales if total_sel_seriales > 0 else 0.0
                    nuevo_precio_busq = st.number_input(
                        "Nuevo Precio Unitario ($)",
                        min_value=0.0,
                        value=precio_prom,
                        step=50.0,
                        key="input_nuevo_precio_busq"
                    )

                # Calcular nuevo valor total
                nuevo_valor_total_busq = total_sel_seriales * nuevo_precio_busq

                col_prev1, col_prev2, col_prev3 = st.columns(3)
                with col_prev1:
                    st.metric("Seriales Seleccionados", f"{total_sel_seriales:,}")
                with col_prev2:
                    st.metric("Nuevo Valor Total", f"${nuevo_valor_total_busq:,.0f}")
                with col_prev3:
                    diferencia_busq = nuevo_valor_total_busq - total_sel_valor
                    st.metric("Diferencia", f"${diferencia_busq:,.0f}", delta=f"${diferencia_busq:,.0f}")

                col_btn_busq1, col_btn_busq2 = st.columns(2)

                with col_btn_busq1:
                    if st.button("Guardar Cambios", type="primary", key="btn_guardar_busqueda"):
                        try:
                            cursor_upd = conn.cursor()

                            nuevo_cod = None
                            if nuevo_mensajero_busq != "(Sin cambio)":
                                nuevo_cod = opciones_mensajeros[nuevo_mensajero_busq]

                            ids_actualizar = list(st.session_state.seleccion_registros_busq)

                            for gestion_id in ids_actualizar:
                                cursor_upd.execute(
                                    "SELECT total_seriales FROM gestiones_mensajero WHERE id = %s",
                                    (gestion_id,)
                                )
                                res = cursor_upd.fetchone()
                                if res:
                                    seriales_reg = res[0]
                                    valor_reg = seriales_reg * nuevo_precio_busq

                                    if nuevo_cod:
                                        cursor_upd.execute("""
                                            UPDATE gestiones_mensajero
                                            SET valor_unitario = %s,
                                                valor_total = %s,
                                                cod_mensajero = %s,
                                                editado_manualmente = 1
                                            WHERE id = %s
                                        """, (nuevo_precio_busq, valor_reg, nuevo_cod, gestion_id))
                                    else:
                                        cursor_upd.execute("""
                                            UPDATE gestiones_mensajero
                                            SET valor_unitario = %s,
                                                valor_total = %s,
                                                editado_manualmente = 1
                                            WHERE id = %s
                                        """, (nuevo_precio_busq, valor_reg, gestion_id))

                            conn.commit()
                            cursor_upd.close()

                            msg_exito = f"Planilla {num_planilla}: {len(ids_actualizar)} registro(s) actualizado(s)"
                            if nuevo_cod:
                                msg_exito += f" - Mensajero cambiado a {nuevo_cod}"
                            st.success(msg_exito)
                            st.session_state.seleccion_registros_busq = set()
                            st.session_state.planilla_buscada = None
                            st.rerun()

                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error al actualizar: {e}")

                with col_btn_busq2:
                    if st.button("Cancelar", key="btn_cancelar_busqueda"):
                        st.session_state.seleccion_registros_busq = set()
                        st.session_state.planilla_buscada = None
                        st.rerun()
            else:
                st.warning("Seleccione al menos un registro para editar")
                if st.button("Cerrar Busqueda", key="btn_cerrar_busqueda"):
                    st.session_state.planilla_buscada = None
                    st.rerun()

    # =====================================================
    # CANDADO MASIVO
    # =====================================================
    with st.expander("🔒 Aplicar Candado Masivo por Fecha", expanded=False):
        st.markdown("Protege todos los registros de un rango de fechas para que no sean sobreescritos por recálculos masivos.")

        col_lk1, col_lk2, col_lk3 = st.columns([1.5, 1.5, 1])
        with col_lk1:
            fecha_lock_desde = st.date_input("Fecha Escaneo Desde", value=date.today(), key="fecha_lock_desde")
        with col_lk2:
            fecha_lock_hasta = st.date_input("Fecha Escaneo Hasta", value=date.today(), key="fecha_lock_hasta")

        try:
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN editado_manualmente = 0 THEN 1 ELSE 0 END) as sin_candado,
                    SUM(CASE WHEN editado_manualmente = 1 THEN 1 ELSE 0 END) as con_candado
                FROM gestiones_mensajero
                WHERE DATE(fecha_escaner) BETWEEN %s AND %s
            """, (fecha_lock_desde, fecha_lock_hasta))
            stats_lock = cursor.fetchone()

            col_lk4, col_lk5, col_lk6 = st.columns(3)
            with col_lk4:
                st.metric("Total registros", f"{stats_lock['total']:,}")
            with col_lk5:
                st.metric("Sin candado 🔓", f"{stats_lock['sin_candado']:,}")
            with col_lk6:
                st.metric("Ya protegidos 🔒", f"{stats_lock['con_candado']:,}")

            with col_lk3:
                st.write("")
                st.write("")
                if stats_lock['sin_candado'] > 0:
                    if st.button(f"🔒 Aplicar candado a {stats_lock['sin_candado']:,} registros",
                                 type="primary", key="btn_candado_masivo"):
                        try:
                            _cur_lock = conn.cursor()
                            _cur_lock.execute("""
                                UPDATE gestiones_mensajero
                                SET editado_manualmente = 1
                                WHERE DATE(fecha_escaner) BETWEEN %s AND %s
                                AND editado_manualmente = 0
                            """, (fecha_lock_desde, fecha_lock_hasta))
                            afectados = _cur_lock.rowcount
                            conn.commit()
                            _cur_lock.close()
                            st.success(f"🔒 Candado aplicado a {afectados:,} registros")
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error: {e}")
                else:
                    st.info("Todos ya protegidos")
        except Exception as e:
            st.error(f"Error: {e}")

    st.divider()

    # =====================================================
    # FILTROS
    # =====================================================
    st.markdown("### Filtros")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Obtener mensajeros disponibles
        cursor.execute("""
            SELECT DISTINCT
                p.codigo,
                p.nombre_completo
            FROM personal p
            WHERE p.activo = TRUE
            AND p.tipo_personal IN ('mensajero', 'courier_externo', 'alistamiento')
            ORDER BY p.codigo
        """)
        mensajeros = cursor.fetchall()

        mensajero_options = {"TODOS": "TODOS"}
        for m in mensajeros:
            mensajero_options[f"{m['codigo']} - {m['nombre_completo']}"] = m['codigo']

        if len(mensajero_options) <= 1:
            st.warning("No hay mensajeros activos")
            st.stop()

        mensajero_sel = st.selectbox("Codigo Mensajero", list(mensajero_options.keys()))
        cod_mensajero = mensajero_options[mensajero_sel]

    with col2:
        fecha_desde = st.date_input("Fecha Desde", value=date.today().replace(day=1))

    with col3:
        fecha_hasta = st.date_input("Fecha Hasta", value=date.today())

    if cod_mensajero == "TODOS":
        nombre_mensajero = "TODOS"
    else:
        # Obtener nombre del mensajero seleccionado
        cursor.execute("""
            SELECT nombre_completo FROM personal WHERE codigo = %s
        """, (cod_mensajero,))
        resultado_nombre = cursor.fetchone()
        nombre_mensajero = resultado_nombre['nombre_completo'] if resultado_nombre else "No encontrado"

    st.divider()

    if cod_mensajero == "TODOS":
        st.markdown("### Resumen de TODOS los Mensajeros")
    else:
        st.markdown(f"### Mensajero: **{cod_mensajero}** - **{nombre_mensajero}**")

    # =====================================================
    # CONSULTA DE PLANILLAS
    # =====================================================
    if cod_mensajero == "TODOS":
        query = """
            SELECT
                gm.id,
                gm.lot_esc as planilla,
                gm.fecha_escaner as f_esc,
                gm.total_seriales as cantidad_seriales,
                gm.valor_unitario as precio,
                gm.valor_total,
                gm.cliente,
                gm.tipo_gestion,
                gm.orden,
                gm.cod_mensajero,
                gm.editado_manualmente
            FROM gestiones_mensajero gm
            WHERE DATE(gm.fecha_escaner) BETWEEN %s AND %s
            ORDER BY gm.cod_mensajero ASC, gm.lot_esc ASC, gm.fecha_escaner ASC
        """
        cursor.execute(query, (fecha_desde, fecha_hasta))
    else:
        query = """
            SELECT
                gm.id,
                gm.lot_esc as planilla,
                gm.fecha_escaner as f_esc,
                gm.total_seriales as cantidad_seriales,
                gm.valor_unitario as precio,
                gm.valor_total,
                gm.cliente,
                gm.tipo_gestion,
                gm.orden,
                gm.editado_manualmente
            FROM gestiones_mensajero gm
            WHERE gm.cod_mensajero = %s
            AND DATE(gm.fecha_escaner) BETWEEN %s AND %s
            ORDER BY gm.lot_esc ASC, gm.fecha_escaner ASC
        """
        cursor.execute(query, (cod_mensajero, fecha_desde, fecha_hasta))
    planillas = cursor.fetchall()

    if planillas:
        # =====================================================
        # RESUMEN
        # =====================================================
        st.markdown("### Resumen")

        total_planillas = len(set([p['planilla'] for p in planillas]))
        total_registros = len(planillas)
        total_seriales = sum([p['cantidad_seriales'] for p in planillas])
        total_valor = sum([p['valor_total'] for p in planillas])

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Planillas Unicas", total_planillas)
        with col2:
            st.metric("Registros", total_registros)
        with col3:
            st.metric("Total Seriales", f"{total_seriales:,}")
        with col4:
            st.metric("Valor Total", f"${total_valor:,.0f}")

        st.divider()

    # =====================================================
    # VISTA TODOS: Resumen por Mensajero
    # =====================================================
    if planillas and cod_mensajero == "TODOS":
        st.markdown("### Detalle por Mensajero")

        df_todos = pd.DataFrame(planillas)

        cursor.execute("SELECT codigo, nombre_completo FROM personal WHERE activo = TRUE")
        nombres_dict = {p['codigo']: p['nombre_completo'] for p in cursor.fetchall()}

        resumen_men = df_todos.groupby('cod_mensajero').agg(
            planillas_unicas=('planilla', 'nunique'),
            total_seriales=('cantidad_seriales', 'sum'),
            valor_total=('valor_total', 'sum')
        ).reset_index()

        resumen_men['nombre'] = resumen_men['cod_mensajero'].map(nombres_dict).fillna('Sin asignar')
        resumen_men = resumen_men.sort_values('cod_mensajero')

        # Encabezados
        hcol1, hcol2, hcol3, hcol4, hcol5 = st.columns([1, 2.5, 1, 1.2, 1.5])
        hcol1.write("**Codigo**")
        hcol2.write("**Nombre**")
        hcol3.write("**Planillas**")
        hcol4.write("**Seriales**")
        hcol5.write("**Valor Total**")
        st.markdown("---")

        for _, row_men in resumen_men.iterrows():
            c1, c2, c3, c4, c5 = st.columns([1, 2.5, 1, 1.2, 1.5])
            c1.write(row_men['cod_mensajero'])
            c2.write(row_men['nombre'])
            c3.write(f"{row_men['planillas_unicas']}")
            c4.write(f"{int(row_men['total_seriales']):,}")
            c5.write(f"${float(row_men['valor_total']):,.0f}")

        st.markdown("---")
        st.markdown(f"### **TOTAL GENERAL: ${total_valor:,.0f}**")

        # Exportar resumen
        st.divider()
        df_resumen_export = resumen_men[['cod_mensajero', 'nombre', 'planillas_unicas', 'total_seriales', 'valor_total']].copy()
        df_resumen_export.columns = ['Codigo', 'Nombre', 'Planillas', 'Seriales', 'Valor Total']
        csv_todos = df_resumen_export.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Descargar Resumen CSV",
            data=csv_todos,
            file_name=f"resumen_mensajeros_{fecha_desde.strftime('%Y%m%d')}_{fecha_hasta.strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

        # # =====================================================
        # # DETALLE AGRUPADO POR PLANILLA
        # # =====================================================
        # st.markdown("### Detalle de Planillas")

        # # Agrupar por planilla
        # from collections import defaultdict
        # planillas_agrupadas = defaultdict(lambda: {
        #     'seriales': 0,
        #     'valor': 0,
        #     'fecha': None,
        #     'ids': [],
        #     'precio_promedio': 0
        # })

        # for p in planillas:
        #     planilla_num = p['planilla']
        #     planillas_agrupadas[planilla_num]['seriales'] += p['cantidad_seriales']
        #     planillas_agrupadas[planilla_num]['valor'] += float(p['valor_total'])
        #     planillas_agrupadas[planilla_num]['ids'].append(p['id'])
        #     if not planillas_agrupadas[planilla_num]['fecha']:
        #         planillas_agrupadas[planilla_num]['fecha'] = p['f_esc']

        # # Calcular precio promedio
        # for planilla_num in planillas_agrupadas:
        #     datos = planillas_agrupadas[planilla_num]
        #     if datos['seriales'] > 0:
        #         datos['precio_promedio'] = datos['valor'] / datos['seriales']

        # # Encabezados
        # col1, col2, col3, col4, col5, col6 = st.columns([1.5, 1.5, 1, 1.2, 1.3, 0.8])
        # col1.write("**Planilla**")
        # col2.write("**Fecha Escaneo**")
        # col3.write("**Seriales**")
        # col4.write("**Precio**")
        # col5.write("**Valor**")
        # col6.write("**Accion**")

        # st.markdown("---")

        # # Mostrar planillas agrupadas ordenadas de menor a mayor
        # for planilla_num in sorted(planillas_agrupadas.keys()):
        #     datos = planillas_agrupadas[planilla_num]
        #     fecha_str = datos['fecha'].strftime('%Y-%m-%d') if hasattr(datos['fecha'], 'strftime') else str(datos['fecha'])

        #     col1, col2, col3, col4, col5, col6 = st.columns([1.5, 1.5, 1, 1.2, 1.3, 0.8])

        #     with col1:
        #         st.write(f"**{planilla_num}**")
        #     with col2:
        #         st.write(fecha_str)
        #     with col3:
        #         st.write(f"{datos['seriales']}")
        #     with col4:
        #         st.write(f"${datos['precio_promedio']:,.0f}")
        #     with col5:
        #         st.write(f"${datos['valor']:,.0f}")
        #     with col6:
        #         if st.button("Editar", key=f"edit_{planilla_num}"):
        #             st.session_state.editando_planilla = {
        #                 'planilla': planilla_num,
        #                 'fecha': datos['fecha'],
        #                 'cantidad_seriales': datos['seriales'],
        #                 'precio': datos['precio_promedio'],
        #                 'valor_total': datos['valor'],
        #                 'ids': datos['ids']
        #             }
        #             st.rerun()

    # =====================================================
    # VISTA INDIVIDUAL (un solo mensajero)
    # =====================================================
    if planillas and cod_mensajero != "TODOS":
        # =====================================================
        # DETALLE AGRUPADO POR PLANILLA Y PRECIO
        # =====================================================
        st.markdown("### Detalle de Planillas")

        # Convertir a DataFrame para manipular fácilmente
        df_planillas = pd.DataFrame(planillas)

        # Agrupamos por 'planilla' y 'precio'
        # Usamos agg para obtener la suma de seriales/valor y capturar los IDs en una lista
        df_agrupado = df_planillas.groupby(['planilla', 'precio']).agg({
            'f_esc': 'first',
            'cantidad_seriales': 'sum',
            'valor_total': 'sum',
            'id': lambda x: list(x),
            'editado_manualmente': 'max'
        }).reset_index()

        # Ordenar por planilla y luego por precio
        df_agrupado = df_agrupado.sort_values(['planilla', 'precio'])

        # Crear clave unica para cada fila
        df_agrupado['row_key'] = df_agrupado.apply(
            lambda r: f"{cod_mensajero}_{r['planilla']}_{r['precio']}", axis=1
        )

        # =====================================================
        # RESUMEN DE AUDITORIA
        # =====================================================
        total_auditado_seriales = 0
        total_auditado_valor = 0
        filas_auditadas_count = 0

        for _, row in df_agrupado.iterrows():
            if row['row_key'] in st.session_state.filas_auditadas:
                total_auditado_seriales += row['cantidad_seriales']
                total_auditado_valor += float(row['valor_total'])
                filas_auditadas_count += 1

        if filas_auditadas_count > 0:
            st.markdown("#### Resumen Auditoria")
            col_aud1, col_aud2, col_aud3, col_aud4, col_aud5 = st.columns([1, 1, 1, 1, 0.8])
            with col_aud1:
                st.metric("Filas Auditadas", filas_auditadas_count)
            with col_aud2:
                st.metric("Seriales Auditados", f"{total_auditado_seriales:,}")
            with col_aud3:
                st.metric("Valor Auditado", f"${total_auditado_valor:,.0f}")
            with col_aud4:
                porcentaje = (total_auditado_valor / float(total_valor) * 100) if total_valor > 0 else 0
                st.metric("% Auditado", f"{porcentaje:.1f}%")
            with col_aud5:
                if st.button("Limpiar", key="btn_limpiar_auditoria"):
                    st.session_state.filas_auditadas = set()
                    st.rerun()
            st.divider()

        # Encabezados de la tabla
        col0, col1, col2, col3, col4, col5, col6, col7 = st.columns([0.5, 1.2, 1.2, 0.9, 1.1, 1.2, 0.7, 0.7])
        col0.write("**Check**")
        col1.write("**Planilla**")
        col2.write("**Fecha Escaneo**")
        col3.write("**Seriales**")
        col4.write("**Precio Unit.**")
        col5.write("**Valor Total**")
        col6.write("**Editar**")
        col7.write("**✅ Rev.**")

        st.markdown("---")

        # Mostrar las filas agrupadas
        for index, row in df_agrupado.iterrows():
            fecha_str = row['f_esc'].strftime('%Y-%m-%d') if hasattr(row['f_esc'], 'strftime') else str(row['f_esc'])
            row_key = row['row_key']
            is_checked = row_key in st.session_state.filas_auditadas
            is_protected = bool(row.get('editado_manualmente', 0))
            planilla_str = str(row['planilla'])
            is_revisada  = planilla_str in planillas_revisadas_set

            # Aplicar estilo si esta checkeada
            if is_checked:
                st.markdown(
                    f"""<div style="background-color: #d4edda; padding: 5px; border-radius: 5px; border-left: 4px solid #28a745;">""",
                    unsafe_allow_html=True
                )

            c0, c1, c2, c3, c4, c5, c6, c7 = st.columns([0.5, 1.2, 1.2, 0.9, 1.1, 1.2, 0.7, 0.7])

            with c0:
                checked = st.checkbox("", value=is_checked, key=f"check_{row_key}", label_visibility="collapsed")
                if checked and row_key not in st.session_state.filas_auditadas:
                    st.session_state.filas_auditadas.add(row_key)
                    st.rerun()
                elif not checked and row_key in st.session_state.filas_auditadas:
                    st.session_state.filas_auditadas.discard(row_key)
                    st.rerun()

            rev_icon  = " ✅" if is_revisada else ""
            lock_icon = " 🔒" if is_protected else ""
            if is_checked:
                c1.write(f"~~**{row['planilla']}**~~{lock_icon}{rev_icon}")
                c2.write(f"~~{fecha_str}~~")
                c3.write(f"~~{row['cantidad_seriales']}~~")
                c4.write(f"~~${row['precio']:,.0f}~~")
                c5.write(f"~~${row['valor_total']:,.0f}~~")
            else:
                c1.write(f"**{row['planilla']}**{lock_icon}{rev_icon}")
                c2.write(fecha_str)
                c3.write(f"{row['cantidad_seriales']}")
                c4.write(f"${row['precio']:,.0f}")
                c5.write(f"${row['valor_total']:,.0f}")

            # Botón de edición único por combinación planilla-precio
            if c6.button("Editar", key=f"edit_{row['planilla']}_{row['precio']}"):
                st.session_state.editando_planilla = {
                    'planilla': row['planilla'],
                    'fecha': row['f_esc'],
                    'cantidad_seriales': row['cantidad_seriales'],
                    'precio': row['precio'],
                    'valor_total': row['valor_total'],
                    'ids': row['id']
                }
                st.rerun()

            # Botón de revisión por planilla (bloquea la sincronización automática)
            with c7:
                if is_revisada:
                    if st.button("🔄", key=f"unrev_{row['planilla']}_{row['precio']}",
                                 help="Desmarcar revisión — la sincronización del escáner podrá modificar esta planilla"):
                        try:
                            _cur = conn.cursor()
                            _cur.execute(
                                "DELETE FROM planillas_revisadas WHERE lot_esc = %s",
                                (planilla_str,)
                            )
                            conn.commit()
                            _cur.close()
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error: {e}")
                else:
                    if st.button("✅", key=f"rev_{row['planilla']}_{row['precio']}",
                                 help="Marcar como revisada — la sincronización no podrá modificar esta planilla"):
                        try:
                            _cur = conn.cursor()
                            _cur.execute(
                                "INSERT IGNORE INTO planillas_revisadas (lot_esc, fecha_revision)"
                                " VALUES (%s, CURDATE())",
                                (planilla_str,)
                            )
                            conn.commit()
                            _cur.close()
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error: {e}")

            if is_checked:
                st.markdown("</div>", unsafe_allow_html=True)

        # =====================================================
        # FORMULARIO DE EDICION
        # =====================================================
        if st.session_state.editando_planilla:
            st.divider()
            st.markdown("### Editar Planilla")

            planilla_edit = st.session_state.editando_planilla

            with st.container():
                st.info(f"**Planilla:** {planilla_edit['planilla']} | **Registros afectados:** {len(planilla_edit['ids'])}")

                # Obtener detalle de los registros por cliente y orden
                ids_str = ','.join([str(id) for id in planilla_edit['ids']])
                cursor.execute(f"""
                    SELECT
                        id, cliente, orden, total_seriales, valor_unitario, valor_total,
                        editado_manualmente
                    FROM gestiones_mensajero
                    WHERE id IN ({ids_str})
                    ORDER BY cliente, orden
                """)
                registros_detalle = cursor.fetchall()

                # Mostrar detalle por cliente y orden con edicion inline
                st.markdown("#### Detalle por Cliente y Orden")

                # Encabezados
                dh1, dh2, dh3, dh4, dh5, dh6, dh7 = st.columns([1.3, 1, 0.7, 1, 1, 0.8, 0.6])
                dh1.write("**Cliente**")
                dh2.write("**Orden**")
                dh3.write("**Seriales**")
                dh4.write("**Nuevo Precio**")
                dh5.write("**Nuevo Valor**")
                dh6.write("**Guardar**")
                dh7.write("**🔒**")

                st.markdown("---")

                for reg in registros_detalle:
                    is_prot = bool(reg.get('editado_manualmente', 0))
                    dc1, dc2, dc3, dc4, dc5, dc6, dc7 = st.columns([1.3, 1, 0.7, 1, 1, 0.8, 0.6])
                    dc1.write(f"{reg['cliente'] or '-'}")
                    dc2.write(f"{reg['orden'] or '-'}")
                    dc3.write(f"{reg['total_seriales']}")

                    with dc4:
                        nuevo_precio_row = st.number_input(
                            "Precio",
                            min_value=0.0,
                            value=float(reg['valor_unitario']),
                            step=50.0,
                            key=f"precio_row_{reg['id']}",
                            label_visibility="collapsed"
                        )

                    # Calcular nuevo valor
                    nuevo_valor_row = reg['total_seriales'] * nuevo_precio_row
                    dc5.write(f"${nuevo_valor_row:,.0f}")

                    with dc6:
                        if st.button("💾", key=f"save_row_{reg['id']}", help="Guardar este registro"):
                            try:
                                cursor_upd = conn.cursor()
                                cursor_upd.execute("""
                                    UPDATE gestiones_mensajero
                                    SET valor_unitario = %s, valor_total = %s, editado_manualmente = 1
                                    WHERE id = %s
                                """, (nuevo_precio_row, nuevo_valor_row, reg['id']))
                                conn.commit()
                                cursor_upd.close()
                                st.success(f"Orden {reg['orden']} actualizada y protegida 🔒")
                                st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"Error: {e}")

                    with dc7:
                        if is_prot:
                            if st.button("🔓", key=f"unlock_det_{reg['id']}", help="Quitar protección manual"):
                                try:
                                    _cur = conn.cursor()
                                    _cur.execute(
                                        "UPDATE gestiones_mensajero SET editado_manualmente = 0 WHERE id = %s",
                                        (reg['id'],)
                                    )
                                    conn.commit()
                                    _cur.close()
                                    st.rerun()
                                except Exception as e:
                                    conn.rollback()
                                    st.error(f"Error: {e}")
                        else:
                            st.caption("—")

                # Mostrar opción para desproteger toda la planilla si hay registros protegidos
                protegidos_planilla = [r for r in registros_detalle if r.get('editado_manualmente')]
                if protegidos_planilla:
                    st.info(f"🔒 {len(protegidos_planilla)} registro(s) protegido(s) — las actualizaciones masivas los omitirán.")
                    if st.button("🔓 Desproteger todos los registros de esta planilla", key="btn_desproteger_planilla"):
                        try:
                            _cur = conn.cursor()
                            for r in protegidos_planilla:
                                _cur.execute(
                                    "UPDATE gestiones_mensajero SET editado_manualmente = 0 WHERE id = %s",
                                    (r['id'],)
                                )
                            conn.commit()
                            _cur.close()
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error: {e}")

                st.markdown("---")

                # Resumen
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Cantidad Seriales", planilla_edit['cantidad_seriales'])

                with col2:
                    st.metric("Precio Actual", f"${planilla_edit['precio']:,.0f}")

                with col3:
                    st.metric("Valor Total Actual", f"${planilla_edit['valor_total']:,.0f}")

                st.markdown("#### Aplicar Cambios a Todos")

                col_msg1, col_msg2 = st.columns(2)

                with col_msg1:
                    nuevo_cod_mensajero = st.text_input(
                        "Nuevo Codigo Mensajero (dejar vacio para no cambiar)",
                        value="",
                        key="edit_nuevo_mensajero"
                    )

                with col_msg2:
                    if nuevo_cod_mensajero:
                        # Verificar si el codigo existe
                        cursor.execute("""
                            SELECT codigo, nombre_completo FROM personal
                            WHERE codigo = %s AND activo = TRUE
                        """, (nuevo_cod_mensajero,))
                        mensajero_encontrado = cursor.fetchone()
                        if mensajero_encontrado:
                            st.success(f"Mensajero: {mensajero_encontrado['nombre_completo']}")
                        else:
                            st.warning("Codigo de mensajero no encontrado o inactivo")

                col1, col2, col3 = st.columns(3)

                with col1:
                    nuevo_precio = st.number_input(
                        "Nuevo Precio Unitario ($)",
                        min_value=0.0,
                        value=float(planilla_edit['precio']),
                        step=50.0,
                        key="edit_precio_planilla"
                    )

                with col2:
                    nuevo_valor_total = planilla_edit['cantidad_seriales'] * nuevo_precio
                    st.metric("Nuevo Valor Total", f"${nuevo_valor_total:,.0f}")

                with col3:
                    diferencia = nuevo_valor_total - float(planilla_edit['valor_total'])
                    st.metric("Diferencia", f"${diferencia:,.0f}", delta=f"${diferencia:,.0f}")

                col_btn1, col_btn2 = st.columns(2)

                with col_btn1:
                    if st.button("Guardar Todos", type="primary", key="btn_guardar_planilla"):
                        # Validar mensajero si se ingreso uno nuevo
                        mensajero_valido = True
                        if nuevo_cod_mensajero:
                            cursor.execute("""
                                SELECT codigo FROM personal
                                WHERE codigo = %s AND activo = TRUE
                            """, (nuevo_cod_mensajero,))
                            if not cursor.fetchone():
                                mensajero_valido = False
                                st.error("El codigo de mensajero no existe o esta inactivo")

                        if mensajero_valido:
                            try:
                                cursor_update = conn.cursor()

                                # Actualizar todos los registros de la planilla
                                for gestion_id in planilla_edit['ids']:
                                    # Obtener seriales de cada registro
                                    cursor_update.execute(
                                        "SELECT total_seriales FROM gestiones_mensajero WHERE id = %s",
                                        (gestion_id,)
                                    )
                                    result = cursor_update.fetchone()
                                    if result:
                                        seriales_registro = result[0]
                                        valor_registro = seriales_registro * nuevo_precio

                                        # Construir query dinamico segun si cambia mensajero
                                        if nuevo_cod_mensajero:
                                            cursor_update.execute("""
                                                UPDATE gestiones_mensajero
                                                SET valor_unitario = %s,
                                                    valor_total = %s,
                                                    cod_mensajero = %s,
                                                    editado_manualmente = 1
                                                WHERE id = %s
                                            """, (nuevo_precio, valor_registro, nuevo_cod_mensajero, gestion_id))
                                        else:
                                            cursor_update.execute("""
                                                UPDATE gestiones_mensajero
                                                SET valor_unitario = %s,
                                                    valor_total = %s,
                                                    editado_manualmente = 1
                                                WHERE id = %s
                                            """, (nuevo_precio, valor_registro, gestion_id))

                                conn.commit()
                                cursor_update.close()

                                st.session_state.editando_planilla = None
                                msg = f"Planilla {planilla_edit['planilla']} actualizada ({len(planilla_edit['ids'])} registros)"
                                if nuevo_cod_mensajero:
                                    msg += f" - Mensajero cambiado a {nuevo_cod_mensajero}"
                                st.success(msg)
                                st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"Error al actualizar: {e}")

                with col_btn2:
                    if st.button("Cancelar", key="btn_cancelar_planilla"):
                        st.session_state.editando_planilla = None
                        st.rerun()

        # =====================================================
        # EXPORTAR
        # =====================================================
        st.divider()

        df_export = pd.DataFrame(planillas)
        csv = df_export.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Descargar CSV",
            data=csv,
            file_name=f"planillas_{cod_mensajero}_{fecha_desde.strftime('%Y%m%d')}_{fecha_hasta.strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

    if not planillas:
        if cod_mensajero == "TODOS":
            st.info(f"No hay planillas entre {fecha_desde.strftime('%d/%m/%Y')} y {fecha_hasta.strftime('%d/%m/%Y')}")
        else:
            st.info(f"No hay planillas para el mensajero {cod_mensajero} entre {fecha_desde.strftime('%d/%m/%Y')} y {fecha_hasta.strftime('%d/%m/%Y')}")

            # Mostrar fechas disponibles para este mensajero
            cursor.execute("""
                SELECT DISTINCT DATE(fecha_escaner) as fecha, COUNT(*) as total
                FROM gestiones_mensajero
                WHERE cod_mensajero = %s
                GROUP BY DATE(fecha_escaner)
                ORDER BY fecha DESC
                LIMIT 10
            """, (cod_mensajero,))
            fechas_disponibles = cursor.fetchall()

            if fechas_disponibles:
                st.markdown("#### Fechas con planillas disponibles:")
                for f in fechas_disponibles:
                    st.write(f"- {f['fecha'].strftime('%d/%m/%Y')}: {f['total']} registros")

except Exception as e:
    st.error(f"Error: {e}")
    import traceback
    st.code(traceback.format_exc())

if 'cursor' in locals():
    cursor.close()
