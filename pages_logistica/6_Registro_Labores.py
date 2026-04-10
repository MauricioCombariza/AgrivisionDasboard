import streamlit as st
import pandas as pd
from datetime import date, datetime
import sys
import os
import io

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_connection import conectar_logistica, cached_tarifas


# ── PDF pegado de guías ────────────────────────────────────────────────────────
def generar_pdf_pegado(data: dict) -> bytes:
    """
    Genera el PDF de un registro de pegado de guías.
    data keys: fecha, orden, filas (list of dicts con codigo/nombre/inicial/final/cantidad),
               tarifa, consecutivos
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle('titulo', parent=styles['Heading1'],
                                  fontSize=16, spaceAfter=4)
    sub_style = ParagraphStyle('sub', parent=styles['Normal'],
                               fontSize=10, spaceAfter=2)

    story = []

    # ── Encabezado ────────────────────────────────────────────────────────────
    story.append(Paragraph("Planilla Pegado de Guías", titulo_style))

    fecha_str = data['fecha'].strftime('%d/%m/%Y') if hasattr(data['fecha'], 'strftime') else str(data['fecha'])
    consecutivos_str = ', '.join([f'#{c}' for c in data['consecutivos']])

    story.append(Paragraph(f"<b>Fecha:</b> {fecha_str}", sub_style))
    story.append(Paragraph(f"<b>Orden:</b> {data['orden']}", sub_style))
    story.append(Paragraph(f"<b>Consecutivos:</b> {consecutivos_str}", sub_style))
    story.append(Paragraph(f"<b>Generado:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", sub_style))
    story.append(Spacer(1, 0.5*cm))

    # ── Tabla ─────────────────────────────────────────────────────────────────
    tarifa = data['tarifa']
    filas = data['filas']

    encabezado = ['Código', 'Nombre', 'Guía Inicial', 'Guía Final', 'Cant. Guías', 'Precio Unit.', 'Total']
    rows = [encabezado]
    total_guias = 0

    for f in filas:
        cant = f['cantidad']
        total = cant * tarifa
        total_guias += cant
        ini = f"{f['inicial']:,}" if isinstance(f['inicial'], int) else str(f['inicial'])
        fin = f"{f['final']:,}" if isinstance(f['final'], int) else str(f['final'])
        rows.append([
            f['codigo'],
            f['nombre'],
            ini,
            fin,
            f"{cant:,}",
            f"${tarifa:,.4f}",
            f"${total:,.0f}",
        ])

    # Fila de totales
    rows.append([
        '', 'TOTAL', '', '',
        f"{total_guias:,}",
        '',
        f"${total_guias * tarifa:,.0f}",
    ])

    col_widths = [2*cm, 5.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.8*cm, 2.8*cm]
    tabla = Table(rows, colWidths=col_widths, repeatRows=1)
    tabla.setStyle(TableStyle([
        # Encabezado
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5f8a')),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, 0), 9),
        ('ALIGN',      (0, 0), (-1, 0), 'CENTER'),
        # Datos
        ('FONTSIZE',   (0, 1), (-1, -1), 8.5),
        ('ALIGN',      (2, 1), (-1, -1), 'RIGHT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f0f4f8')]),
        # Fila total
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8f0e8')),
        ('FONTNAME',   (0, -1), (-1, -1), 'Helvetica-Bold'),
        # Bordes
        ('GRID',       (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('LINEBELOW',  (0, 0), (-1, 0), 1.5, colors.HexColor('#2c5f8a')),
        ('LINEABOVE',  (0, -1), (-1, -1), 1.5, colors.HexColor('#888888')),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    story.append(tabla)
    doc.build(story)
    return buf.getvalue()


def generar_pdf_pegado_dia(fecha, rows: list) -> bytes:
    """
    PDF unificado de todos los registros de pegado de un día.
    rows: lista de dicts con codigo, nombre, cantidad, tarifa_unitaria,
          numero_orden, cliente.
    Estructura:
      - Encabezado con fecha y listado de órdenes
      - Tabla detalle (todos los registros, ordenados por código)
      - Tabla resumen: totales por código
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from collections import defaultdict

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle('titulo', parent=styles['Heading1'], fontSize=15, spaceAfter=4)
    sub_style    = ParagraphStyle('sub',    parent=styles['Normal'],   fontSize=9,  spaceAfter=2)
    sec_style    = ParagraphStyle('sec',    parent=styles['Heading2'], fontSize=11, spaceBefore=10, spaceAfter=4)

    fecha_str = fecha.strftime('%d/%m/%Y') if hasattr(fecha, 'strftime') else str(fecha)
    story = []

    # ── Encabezado ────────────────────────────────────────────────────────────
    story.append(Paragraph("Planilla Diaria — Pegado de Guías", titulo_style))
    story.append(Paragraph(f"<b>Fecha:</b> {fecha_str}", sub_style))
    story.append(Paragraph(f"<b>Generado:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", sub_style))

    # Órdenes del día
    ordenes_unicas = sorted({f"{r['numero_orden']} - {r['cliente']}" for r in rows})
    story.append(Paragraph(f"<b>Órdenes:</b> {', '.join(ordenes_unicas)}", sub_style))
    story.append(Spacer(1, 0.4*cm))

    # ── Tabla detalle ─────────────────────────────────────────────────────────
    story.append(Paragraph("Detalle por trabajador", sec_style))

    enc_det = ['Código', 'Nombre', 'Orden', 'Cant. Guías', 'Precio Unit.', 'Total']
    rows_det = [enc_det]
    for r in sorted(rows, key=lambda x: x['codigo']):
        tarifa = float(r['tarifa_unitaria'])
        cant   = r['cantidad']
        rows_det.append([
            r['codigo'],
            r['nombre'],
            str(r['numero_orden']),
            f"{cant:,}",
            f"${tarifa:,.4f}",
            f"${cant * tarifa:,.0f}",
        ])

    col_w_det = [2*cm, 5.5*cm, 3*cm, 2.8*cm, 2.8*cm, 2.8*cm]
    t_det = Table(rows_det, colWidths=col_w_det, repeatRows=1)
    t_det.setStyle(TableStyle([
        ('BACKGROUND',     (0, 0), (-1, 0),  colors.HexColor('#2c5f8a')),
        ('TEXTCOLOR',      (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',       (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',       (0, 0), (-1, 0),  9),
        ('ALIGN',          (0, 0), (-1, 0),  'CENTER'),
        ('FONTSIZE',       (0, 1), (-1, -1), 8),
        ('ALIGN',          (3, 1), (-1, -1), 'RIGHT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4f8')]),
        ('GRID',           (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('LINEBELOW',      (0, 0), (-1, 0),  1.5, colors.HexColor('#2c5f8a')),
        ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',     (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 4),
    ]))
    story.append(t_det)
    story.append(Spacer(1, 0.6*cm))

    # ── Tabla resumen por código ───────────────────────────────────────────────
    story.append(Paragraph("Totales por código", sec_style))

    totales = defaultdict(lambda: {'nombre': '', 'cantidad': 0, 'valor': 0.0})
    for r in rows:
        cod = r['codigo']
        totales[cod]['nombre']   = r['nombre']
        totales[cod]['cantidad'] += r['cantidad']
        totales[cod]['valor']    += r['cantidad'] * float(r['tarifa_unitaria'])

    enc_res = ['Código', 'Nombre', 'Total Guías', 'Total $']
    rows_res = [enc_res]
    gran_guias = 0
    gran_valor = 0.0
    for cod, dat in sorted(totales.items()):
        rows_res.append([
            cod,
            dat['nombre'],
            f"{dat['cantidad']:,}",
            f"${dat['valor']:,.0f}",
        ])
        gran_guias += dat['cantidad']
        gran_valor += dat['valor']

    rows_res.append(['', 'TOTAL', f"{gran_guias:,}", f"${gran_valor:,.0f}"])

    col_w_res = [2*cm, 6*cm, 3.5*cm, 3.5*cm]
    t_res = Table(rows_res, colWidths=col_w_res, repeatRows=1)
    t_res.setStyle(TableStyle([
        ('BACKGROUND',     (0, 0),  (-1, 0),  colors.HexColor('#2c5f8a')),
        ('TEXTCOLOR',      (0, 0),  (-1, 0),  colors.white),
        ('FONTNAME',       (0, 0),  (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',       (0, 0),  (-1, 0),  9),
        ('ALIGN',          (0, 0),  (-1, 0),  'CENTER'),
        ('FONTSIZE',       (0, 1),  (-1, -1), 8.5),
        ('ALIGN',          (2, 1),  (-1, -1), 'RIGHT'),
        ('ROWBACKGROUNDS', (0, 1),  (-1, -2), [colors.white, colors.HexColor('#f0f4f8')]),
        ('BACKGROUND',     (0, -1), (-1, -1), colors.HexColor('#e8f0e8')),
        ('FONTNAME',       (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID',           (0, 0),  (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('LINEBELOW',      (0, 0),  (-1, 0),  1.5, colors.HexColor('#2c5f8a')),
        ('LINEABOVE',      (0, -1), (-1, -1), 1.5, colors.HexColor('#888888')),
        ('VALIGN',         (0, 0),  (-1, -1), 'MIDDLE'),
        ('TOPPADDING',     (0, 0),  (-1, -1), 4),
        ('BOTTOMPADDING',  (0, 0),  (-1, -1), 4),
    ]))
    story.append(t_res)

    doc.build(story)
    return buf.getvalue()


def convertir_horas_a_decimal(tiempo_str):
    """Convierte formato HH:MM a decimal (ej: '2:45' -> 2.75)"""
    try:
        if ':' in tiempo_str:
            horas, minutos = tiempo_str.split(':')
            horas = int(horas)
            minutos = int(minutos)
            if minutos < 0 or minutos >= 60:
                return None, "Los minutos deben estar entre 0 y 59"
            return horas + (minutos / 60), None
        else:
            # Si solo se ingresa un número, asumir que son horas
            return float(tiempo_str), None
    except:
        return None, "Formato inválido. Use HH:MM (ej: 2:45)"

# =====================================================
# FUNCIONES DE SUBSIDIO DE TRANSPORTE
# =====================================================

def calcular_subsidio_transporte(conn, personal_id: int, fecha) -> dict:
    """
    Calcula el subsidio de transporte para una persona en una fecha específica.

    Regla:
    - Sumar horas de alistamiento (registro_horas con orden_id NOT NULL)
    - Sumar horas administrativas (registro_horas con orden_id NULL y [ADMIN])
    - Si total >= 5 horas -> transporte_completo
    - Si total < 5 horas -> medio_transporte

    Returns:
        dict con: horas_totales, horas_alistamiento, horas_admin, tipo_subsidio, tarifa, ya_existe, subsidio_id
    """
    cursor = conn.cursor(dictionary=True)

    # 1. Verificar si ya existe subsidio para esa persona/fecha
    cursor.execute("""
        SELECT id, horas_totales, tipo_subsidio, tarifa, origen
        FROM subsidio_transporte
        WHERE personal_id = %s AND fecha = %s
    """, (personal_id, fecha))
    subsidio_existente = cursor.fetchone()

    # 2. Sumar horas de alistamiento y admin en una sola query
    cursor.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN observaciones IS NULL OR observaciones NOT LIKE '[ADMIN]%%'
                              THEN horas_trabajadas ELSE 0 END), 0) AS horas_alistamiento,
            COALESCE(SUM(CASE WHEN observaciones LIKE '[ADMIN]%%'
                              THEN horas_trabajadas ELSE 0 END), 0) AS horas_admin
        FROM registro_horas
        WHERE personal_id = %s AND fecha = %s
    """, (personal_id, fecha))
    resultado = cursor.fetchone()
    horas_alistamiento = float(resultado['horas_alistamiento']) if resultado else 0.0
    horas_admin = float(resultado['horas_admin']) if resultado else 0.0
    cursor.close()

    # 3. Total y tipo de subsidio
    horas_totales = horas_alistamiento + horas_admin
    if horas_totales >= 5.0:
        tipo_subsidio = 'transporte_completo'
    else:
        tipo_subsidio = 'medio_transporte'

    # 4. Tarifa vigente — cacheada (no varía por persona/fecha)
    tarifa = cached_tarifas(tipo_subsidio)

    return {
        'horas_totales': horas_totales,
        'horas_alistamiento': horas_alistamiento,
        'horas_admin': horas_admin,
        'tipo_subsidio': tipo_subsidio,
        'tarifa': tarifa,
        'ya_existe': subsidio_existente is not None,
        'subsidio_id': subsidio_existente['id'] if subsidio_existente else None,
        'subsidio_actual': subsidio_existente
    }


def crear_o_actualizar_subsidio(conn, personal_id: int, fecha, origen: str = 'automatico') -> int:
    """
    Crea o actualiza el subsidio de transporte para una persona/fecha.

    Args:
        origen: 'automatico', 'manual', o 'recalculado'

    Returns:
        ID del subsidio creado/actualizado, o None si no hay horas
    """
    calculo = calcular_subsidio_transporte(conn, personal_id, fecha)

    # Si no hay horas trabajadas, no crear subsidio
    if calculo['horas_totales'] <= 0:
        return None

    cursor = conn.cursor()

    if calculo['ya_existe']:
        # Actualizar existente (solo si no está liquidado)
        cursor.execute("""
            UPDATE subsidio_transporte
            SET horas_totales = %s,
                tipo_subsidio = %s,
                tarifa = %s,
                origen = %s,
                fecha_modificacion = CURRENT_TIMESTAMP
            WHERE id = %s AND liquidado = FALSE
        """, (
            calculo['horas_totales'],
            calculo['tipo_subsidio'],
            calculo['tarifa'],
            origen,
            calculo['subsidio_id']
        ))
        conn.commit()
        cursor.close()
        return calculo['subsidio_id']
    else:
        # Crear nuevo
        cursor.execute("""
            INSERT INTO subsidio_transporte
            (personal_id, fecha, horas_totales, tipo_subsidio, tarifa, origen)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            personal_id,
            fecha,
            calculo['horas_totales'],
            calculo['tipo_subsidio'],
            calculo['tarifa'],
            origen
        ))
        conn.commit()
        nuevo_id = cursor.lastrowid
        cursor.close()
        return nuevo_id


def auto_calcular_subsidios_consulta(conn, fecha_desde, fecha_hasta) -> int:
    """
    Se ejecuta automáticamente al consultar registros.
    Calcula subsidios faltantes para el rango de fechas consultado.

    Returns:
        Cantidad de subsidios creados
    """
    cursor = conn.cursor(dictionary=True)

    # Encontrar combinaciones personal/fecha que tienen horas pero no subsidio
    cursor.execute("""
        SELECT DISTINCT rh.personal_id, rh.fecha
        FROM registro_horas rh
        LEFT JOIN subsidio_transporte st
            ON rh.personal_id = st.personal_id AND rh.fecha = st.fecha
        WHERE rh.fecha BETWEEN %s AND %s
          AND st.id IS NULL
    """, (fecha_desde, fecha_hasta))

    faltantes = cursor.fetchall()
    cursor.close()

    creados = 0
    # Crear subsidios faltantes
    for reg in faltantes:
        try:
            resultado = crear_o_actualizar_subsidio(conn, reg['personal_id'], reg['fecha'], 'automatico')
            if resultado:
                creados += 1
        except Exception:
            pass  # Silenciar errores en auto-cálculo

    return creados


def recalcular_subsidios_rango(conn, fecha_desde, fecha_hasta, personal_id: int = None) -> dict:
    """
    Recalcula subsidios para un rango de fechas.

    Args:
        personal_id: Si es None, recalcula para todo el personal

    Returns:
        dict con estadísticas: creados, actualizados, errores
    """
    cursor = conn.cursor(dictionary=True)

    # Obtener combinaciones únicas de personal/fecha con horas registradas
    query = """
        SELECT DISTINCT personal_id, fecha
        FROM registro_horas
        WHERE fecha BETWEEN %s AND %s
    """
    params = [fecha_desde, fecha_hasta]

    if personal_id:
        query += " AND personal_id = %s"
        params.append(personal_id)

    cursor.execute(query, params)
    registros = cursor.fetchall()
    cursor.close()

    estadisticas = {'creados': 0, 'actualizados': 0, 'errores': 0}

    for reg in registros:
        try:
            calculo = calcular_subsidio_transporte(conn, reg['personal_id'], reg['fecha'])
            if calculo['horas_totales'] > 0:
                if calculo['ya_existe']:
                    estadisticas['actualizados'] += 1
                else:
                    estadisticas['creados'] += 1
                crear_o_actualizar_subsidio(conn, reg['personal_id'], reg['fecha'], 'recalculado')
        except Exception:
            estadisticas['errores'] += 1

    return estadisticas

st.title("⏱️ Registro de Horas y Labores")

# Reusar la conexión dentro de la misma sesión para evitar crear una nueva
# conexión TCP al VPS en cada rerun (causa principal de cuelgues)
if '_labores_conn' not in st.session_state or not st.session_state._labores_conn.is_connected():
    st.session_state._labores_conn = conectar_logistica()
conn = st.session_state._labores_conn
if not conn:
    st.stop()

# Asegurar tarifas de subsidio — solo una vez por sesión
if 'labores_tarifas_ok' not in st.session_state:
    try:
        cursor_init = conn.cursor()
        cursor_init.execute("""
            UPDATE tarifas_servicios
            SET tarifa = 8333
            WHERE tipo_servicio IN ('transporte_completo', 'medio_transporte')
              AND activo = TRUE AND tarifa != 8333
        """)
        if cursor_init.rowcount > 0:
            conn.commit()
            cached_tarifas.clear()  # Invalidar caché si cambió la tarifa
        cursor_init.close()
    except Exception:
        pass
    st.session_state['labores_tarifas_ok'] = True

# Inicializar contadores de formulario en session_state
if 'form_horas_counter' not in st.session_state:
    st.session_state.form_horas_counter = 0
if 'form_labor_counter' not in st.session_state:
    st.session_state.form_labor_counter = 0
if 'ultimo_consecutivo_horas' not in st.session_state:
    st.session_state.ultimo_consecutivo_horas = None
if 'ultimo_consecutivo_labor' not in st.session_state:
    st.session_state.ultimo_consecutivo_labor = None
if 'form_admin_counter' not in st.session_state:
    st.session_state.form_admin_counter = 0
if 'ultimo_consecutivo_admin' not in st.session_state:
    st.session_state.ultimo_consecutivo_admin = None
if 'editando_planilla' not in st.session_state:
    st.session_state.editando_planilla = None
# Variables para sesión de ingreso continuo
if 'personal_activo_horas' not in st.session_state:
    st.session_state.personal_activo_horas = None
if 'fecha_activa_horas' not in st.session_state:
    st.session_state.fecha_activa_horas = None
if 'registros_sesion_horas' not in st.session_state:
    st.session_state.registros_sesion_horas = []
# Variables para pegado de guías (multi-fila)
if 'lab_pegado_filas' not in st.session_state:
    st.session_state.lab_pegado_filas = []
if 'lab_pegado_next_id' not in st.session_state:
    st.session_state.lab_pegado_next_id = 0
# Variables para transporte completo (multi-fila)
if 'lab_transp_filas' not in st.session_state:
    st.session_state.lab_transp_filas = []
if 'lab_transp_next_id' not in st.session_state:
    st.session_state.lab_transp_next_id = 0

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "⏰ Registro de Horas",
    "🔧 Registro de Labores",
    "🏢 Labores Administrativas",
    "📊 Consultar Registros",
    "📑 Planilla Check"
])

# =====================================================
# TAB 1: REGISTRO DE HORAS DE ALISTAMIENTO
# =====================================================
with tab1:
    st.subheader("Registro de Horas de Alistamiento")

    # Mostrar último consecutivo registrado
    if st.session_state.ultimo_consecutivo_horas:
        st.success(f"✅ Último registro guardado - Consecutivo: #{st.session_state.ultimo_consecutivo_horas}")

    st.divider()

    try:
        cursor = conn.cursor(dictionary=True)

        # Búsqueda de personal
        st.markdown("### 👤 Información del Personal")

        col1, col2, col3 = st.columns([1, 3, 1])

        with col1:
            # Usar valor de personal activo si existe
            valor_codigo = st.session_state.personal_activo_horas['codigo'] if st.session_state.personal_activo_horas else ""

            codigo_buscar = st.text_input(
                "Código del Personal *",
                value=valor_codigo,
                max_chars=4,
                help="Ingrese el código de 4 dígitos",
                key=f"codigo_horas_{st.session_state.form_horas_counter}"
            )

        personal_info = None
        if codigo_buscar and len(codigo_buscar) == 4:
            # Si hay personal activo y el código coincide, usar el activo
            if st.session_state.personal_activo_horas and st.session_state.personal_activo_horas['codigo'] == codigo_buscar:
                personal_info = st.session_state.personal_activo_horas
            else:
                cursor.execute("""
                    SELECT id, codigo, nombre_completo, identificacion, tipo_personal
                    FROM personal
                    WHERE codigo = %s AND activo = TRUE
                """, (codigo_buscar,))
                personal_info = cursor.fetchone()

                # Actualizar personal activo
                if personal_info:
                    st.session_state.personal_activo_horas = personal_info
                    # Limpiar registros de sesión si cambió de persona
                    st.session_state.registros_sesion_horas = []

            if personal_info:
                with col2:
                    st.info(f"**Nombre:** {personal_info['nombre_completo']} | **Cédula:** {personal_info['identificacion']}")
            else:
                with col2:
                    st.error("❌ Personal no encontrado o inactivo")
                st.session_state.personal_activo_horas = None

        with col3:
            if st.button("🔄 Nuevo Personal", help="Limpiar para ingresar otro personal"):
                st.session_state.personal_activo_horas = None
                st.session_state.fecha_activa_horas = None
                st.session_state.registros_sesion_horas = []
                st.session_state.form_horas_counter += 1
                st.rerun()

        # Mostrar resumen de sesión actual
        if st.session_state.personal_activo_horas and st.session_state.registros_sesion_horas:
            st.markdown("### 📊 Resumen de Sesión Actual")

            # Calcular totales por fecha
            from collections import defaultdict
            totales_por_fecha = defaultdict(lambda: {'horas': 0, 'registros': 0})

            for reg in st.session_state.registros_sesion_horas:
                fecha_str = reg['fecha'].strftime('%d/%m/%Y')
                totales_por_fecha[fecha_str]['horas'] += reg['horas']
                totales_por_fecha[fecha_str]['registros'] += 1

            col1, col2, col3 = st.columns(3)
            with col1:
                total_registros = len(st.session_state.registros_sesion_horas)
                st.metric("Registros Ingresados", total_registros)
            with col2:
                total_horas_sesion = sum([r['horas'] for r in st.session_state.registros_sesion_horas])
                horas_enteras = int(total_horas_sesion)
                minutos = int((total_horas_sesion - horas_enteras) * 60)
                st.metric("Total Horas", f"{horas_enteras}:{minutos:02d}")
            with col3:
                if st.session_state.registros_sesion_horas:
                    ultimo_reg = st.session_state.registros_sesion_horas[-1]
                    st.metric("Última Fecha", ultimo_reg['fecha'].strftime('%d/%m/%Y'))

            # Mostrar detalle por fecha
            with st.expander("📋 Ver detalle de registros ingresados"):
                for fecha_str, datos in sorted(totales_por_fecha.items(), reverse=True):
                    h = int(datos['horas'])
                    m = int((datos['horas'] - h) * 60)
                    st.write(f"**{fecha_str}:** {datos['registros']} registro(s) - {h}:{m:02d} horas")

        st.divider()

        # Formulario de registro solo si hay personal seleccionado
        if personal_info:
            st.markdown("### 📝 Registro de Horas")

            with st.form(key=f"form_registro_horas_{st.session_state.form_horas_counter}"):

                col1, col2 = st.columns(2)

                with col1:
                    # Usar fecha activa si existe, sino usar hoy
                    valor_fecha = st.session_state.fecha_activa_horas if st.session_state.fecha_activa_horas else date.today()

                    fecha_labor = st.date_input(
                        "Fecha de la Labor *",
                        value=valor_fecha,
                        help="Fecha en que se realizó el trabajo"
                    )

                with col2:
                    tipo_trabajo = st.selectbox(
                        "Tipo de Trabajo *",
                        ["alistamiento_sobres", "alistamiento_paquetes"],
                        format_func=lambda x: "Alistamiento de Sobres" if x == "alistamiento_sobres" else "Alistamiento de Paquetes"
                    )

                st.markdown("#### 📦 Órdenes Trabajadas")
                st.info("💡 Agregue las órdenes en las que trabajó y las horas dedicadas a cada una")

                # Obtener órdenes activas
                cursor.execute("""
                    SELECT o.id, o.numero_orden, c.nombre_empresa as cliente
                    FROM ordenes o
                    JOIN clientes c ON o.cliente_id = c.id
                    WHERE o.estado = 'activa'
                    ORDER BY o.fecha_recepcion DESC, o.id DESC
                """)
                ordenes_disponibles = cursor.fetchall()

                if not ordenes_disponibles:
                    st.warning("No hay órdenes activas disponibles")
                else:
                    # Permitir agregar hasta 5 órdenes diferentes
                    num_ordenes = st.number_input(
                        "¿Cuántas órdenes diferentes trabajó?",
                        min_value=1,
                        max_value=5,
                        value=1,
                        help="Puede trabajar en hasta 5 órdenes diferentes"
                    )

                    ordenes_data = []

                    for i in range(int(num_ordenes)):
                        st.markdown(f"**Orden #{i+1}**")
                        col1, col2, col3 = st.columns([2, 1, 1])

                        with col1:
                            orden_options = {
                                f"{o['numero_orden']} - {o['cliente']}": o['id']
                                for o in ordenes_disponibles
                            }
                            orden_sel = st.selectbox(
                                f"Orden",
                                list(orden_options.keys()),
                                key=f"orden_horas_{i}_{st.session_state.form_horas_counter}"
                            )
                            orden_id = orden_options[orden_sel]

                        with col2:
                            horas_input = st.text_input(
                                f"Horas (HH:MM)",
                                value="0:00",
                                key=f"horas_{i}_{st.session_state.form_horas_counter}",
                                help="Formato HH:MM - Ejemplo: 2:45 para 2 horas y 45 minutos"
                            )
                            horas, error_horas = convertir_horas_a_decimal(horas_input)
                            if horas is None:
                                horas = 0.0

                        with col3:
                            # Obtener tarifa por hora del personal
                            cursor.execute("""
                                SELECT tarifa FROM tarifas_servicios
                                WHERE tipo_servicio = 'alistamiento_hora'
                                  AND activo = TRUE
                                ORDER BY vigencia_desde DESC
                                LIMIT 1
                            """)
                            tarifa_result = cursor.fetchone()
                            tarifa_hora = float(tarifa_result['tarifa']) if tarifa_result else 0.0

                            st.metric("Tarifa/Hora", f"${tarifa_hora:,.0f}")

                        if horas > 0:
                            ordenes_data.append({
                                'orden_id': orden_id,
                                'horas': horas,
                                'tarifa_hora': tarifa_hora
                            })

                observaciones = st.text_area(
                    "Observaciones",
                    help="Información adicional sobre el trabajo realizado (opcional)"
                )

                submitted = st.form_submit_button("💾 Guardar Registro de Horas", type="primary")

                if submitted:
                    # Validar formato de horas
                    errores_formato = []
                    for i, orden_data in enumerate(ordenes_data):
                        if orden_data.get('horas') == 0.0:
                            errores_formato.append(f"Orden #{i+1}: Formato de horas inválido")

                    if errores_formato:
                        for error in errores_formato:
                            st.error(error)
                    elif not ordenes_data:
                        st.error("Debe ingresar al menos una orden con horas trabajadas")
                    else:
                        try:
                            cursor = conn.cursor()
                            consecutivos = []

                            for orden_data in ordenes_data:
                                cursor.execute("""
                                    INSERT INTO registro_horas
                                    (personal_id, orden_id, fecha, horas_trabajadas, tarifa_hora,
                                     tipo_trabajo, observaciones, aprobado)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE)
                                """, (
                                    personal_info['id'],
                                    orden_data['orden_id'],
                                    fecha_labor,
                                    orden_data['horas'],
                                    orden_data['tarifa_hora'],
                                    tipo_trabajo,
                                    observaciones
                                ))
                                consecutivos.append(cursor.lastrowid)

                            conn.commit()

                            # Guardar el último consecutivo
                            st.session_state.ultimo_consecutivo_horas = consecutivos[-1] if consecutivos else None

                            # Actualizar fecha activa
                            st.session_state.fecha_activa_horas = fecha_labor

                            # Agregar registros a la sesión actual
                            total_horas_agregadas = sum([od['horas'] for od in ordenes_data])
                            st.session_state.registros_sesion_horas.append({
                                'fecha': fecha_labor,
                                'horas': total_horas_agregadas,
                                'tipo': tipo_trabajo,
                                'ordenes': len(ordenes_data)
                            })

                            # RECALCULAR SUBSIDIO DE TRANSPORTE automáticamente
                            subsidio_result = crear_o_actualizar_subsidio(conn, personal_info['id'], fecha_labor, 'automatico')
                            calculo = calcular_subsidio_transporte(conn, personal_info['id'], fecha_labor)

                            # NO incrementar el counter para mantener el personal activo
                            # st.session_state.form_horas_counter += 1

                            st.success(f"✅ {len(ordenes_data)} registro(s) guardado(s) exitosamente")
                            st.info(f"📋 Consecutivos: {', '.join([f'#{c}' for c in consecutivos])}")

                            # Mostrar resumen de horas del día y subsidio
                            h_total = int(calculo['horas_totales'])
                            m_total = int((calculo['horas_totales'] - h_total) * 60)
                            st.success(f"⏱️ Total horas del día: **{h_total}:{m_total:02d}** (Alistamiento: {calculo['horas_alistamiento']:.2f}h + Admin: {calculo['horas_admin']:.2f}h)")
                            st.info(f"🚌 Subsidio: **{calculo['tipo_subsidio'].replace('_', ' ').title()}** - ${calculo['tarifa']:,.0f}")

                            st.rerun()

                        except Exception as e:
                            st.error(f"Error al guardar: {e}")
                            conn.rollback()

        else:
            st.info("👆 Ingrese el código del personal para comenzar el registro")

    except Exception as e:
        st.error(f"Error: {e}")

# =====================================================
# TAB 2: REGISTRO DE LABORES
# =====================================================
with tab2:
    st.subheader("Registro de Labores (Pegado, Transporte)")

    if st.session_state.ultimo_consecutivo_labor:
        st.success(f"✅ Último registro guardado - Consecutivo: #{st.session_state.ultimo_consecutivo_labor}")

    st.divider()

    try:
        cursor = conn.cursor(dictionary=True)

        # Cargar personal activo para búsqueda rápida (sin query por fila)
        cursor.execute("SELECT id, codigo, nombre_completo FROM personal WHERE activo = TRUE")
        personal_dict_lab = {p['codigo']: p for p in cursor.fetchall()}

        # Cargar órdenes activas
        cursor.execute("""
            SELECT o.id, o.numero_orden, c.nombre_empresa as cliente
            FROM ordenes o
            JOIN clientes c ON o.cliente_id = c.id
            WHERE o.estado = 'activa'
            ORDER BY o.fecha_recepcion DESC, o.id DESC
        """)
        ordenes_lab = cursor.fetchall()
        orden_options_lab2 = {
            f"{o['numero_orden']} - {o['cliente']}": o['id']
            for o in ordenes_lab
        }

        if not ordenes_lab:
            st.warning("No hay órdenes activas disponibles")
        else:
            tipo_labor = st.selectbox(
                "Tipo de Labor *",
                ["pegado_guia", "transporte_completo", "medio_transporte"],
                format_func=lambda x: {
                    'pegado_guia': '📌 Pegado de Guías',
                    'transporte_completo': '🚌 Transporte Completo',
                    'medio_transporte': '🚐 Medio Transporte'
                }[x],
                key=f"tipo_labor_{st.session_state.form_labor_counter}"
            )

            st.divider()

            # =============================================
            # PEGADO DE GUÍAS: fecha + orden fijas, filas por trabajador
            # =============================================
            if tipo_labor == 'pegado_guia':
                st.markdown("### 📌 Pegado de Guías")
                st.info("💡 Seleccione la fecha y la orden, luego agregue una fila por trabajador. El **Inicial** se pre-llena como Final anterior + 1.")

                cursor.execute("""
                    SELECT tarifa FROM tarifas_servicios
                    WHERE tipo_servicio = 'pegado_guia' AND activo = TRUE
                    ORDER BY vigencia_desde DESC LIMIT 1
                """)
                tr_peg = cursor.fetchone()
                tarifa_pegado = float(tr_peg['tarifa']) if tr_peg else 0.0

                col_pf1, col_pf2, col_pf3 = st.columns([1.5, 3, 1.2])
                with col_pf1:
                    fecha_pegado = st.date_input(
                        "Fecha de Labor *",
                        value=date.today(),
                        key="lab_pegado_fecha"
                    )
                with col_pf2:
                    orden_pegado_sel = st.selectbox(
                        "Orden *",
                        list(orden_options_lab2.keys()),
                        key="lab_pegado_orden"
                    )
                    orden_pegado_id = orden_options_lab2[orden_pegado_sel]
                with col_pf3:
                    st.metric("Tarifa por guía", f"${tarifa_pegado:,.4f}")

                st.markdown("---")

                col_add_p, col_clear_p, _ = st.columns([1, 1, 3])
                with col_add_p:
                    if st.button("➕ Agregar Fila", key="btn_add_pegado"):
                        rid_new = st.session_state.lab_pegado_next_id
                        st.session_state.lab_pegado_next_id += 1
                        prev_final = 0
                        if st.session_state.lab_pegado_filas:
                            last_rid = st.session_state.lab_pegado_filas[-1]
                            prev_final = st.session_state.get(f"lab_peg_final_{last_rid}", 0)
                        sugerido = int(prev_final) + 1
                        st.session_state[f"lab_peg_inicial_{rid_new}"] = sugerido
                        st.session_state[f"lab_peg_final_{rid_new}"] = sugerido
                        st.session_state.lab_pegado_filas.append(rid_new)
                        st.rerun()

                with col_clear_p:
                    if st.session_state.lab_pegado_filas:
                        if st.button("🗑️ Limpiar Todo", key="btn_clear_pegado"):
                            for rid in st.session_state.lab_pegado_filas:
                                for k in [f"lab_peg_codigo_{rid}",
                                          f"lab_peg_inicial_{rid}", f"lab_peg_final_{rid}"]:
                                    st.session_state.pop(k, None)
                            st.session_state.lab_pegado_filas = []
                            st.rerun()

                if st.session_state.lab_pegado_filas:
                    hc = st.columns([1, 3.5, 1.3, 1.3, 1.2, 0.5])
                    for ch, lbl in zip(hc, ["Código", "Nombre", "Inicial", "Final", "Cantidad", ""]):
                        ch.markdown(f"**{lbl}**")

                    filas_validas_peg = []
                    for rid in list(st.session_state.lab_pegado_filas):
                        c1, c2, c3, c4, c5, c6 = st.columns([1, 3.5, 1.3, 1.3, 1.2, 0.5])
                        with c1:
                            cod_in = st.text_input(
                                "Código", max_chars=4,
                                key=f"lab_peg_codigo_{rid}", label_visibility="collapsed"
                            )
                        with c2:
                            if cod_in and len(cod_in) == 4:
                                p_data = personal_dict_lab.get(cod_in)
                                st.write(f"✅ {p_data['nombre_completo']}" if p_data else "❌ No encontrado")
                            else:
                                st.write("—")
                        with c3:
                            ini_val = st.number_input(
                                "Inicial", min_value=1, step=1,
                                key=f"lab_peg_inicial_{rid}", label_visibility="collapsed"
                            )
                        with c4:
                            fin_val = st.number_input(
                                "Final", min_value=1, step=1,
                                key=f"lab_peg_final_{rid}", label_visibility="collapsed"
                            )
                        with c5:
                            if fin_val >= ini_val:
                                cant = fin_val - ini_val + 1
                                st.markdown(f"**{cant:,}**")
                            else:
                                cant = 0
                                st.markdown("⚠️")
                        with c6:
                            if st.button("✕", key=f"btn_del_peg_{rid}", help="Eliminar fila"):
                                st.session_state.lab_pegado_filas.remove(rid)
                                for k in [f"lab_peg_codigo_{rid}",
                                          f"lab_peg_inicial_{rid}", f"lab_peg_final_{rid}"]:
                                    st.session_state.pop(k, None)
                                st.rerun()

                        if (cod_in and len(cod_in) == 4
                                and personal_dict_lab.get(cod_in)
                                and fin_val >= ini_val and cant > 0):
                            filas_validas_peg.append({
                                'personal_id': personal_dict_lab[cod_in]['id'],
                                'codigo': cod_in,
                                'nombre': personal_dict_lab[cod_in]['nombre_completo'],
                                'inicial': ini_val,
                                'final': fin_val,
                                'cantidad': cant,
                            })

                    st.markdown("---")
                    total_guias = sum(f['cantidad'] for f in filas_validas_peg)
                    col_s1, col_s2, col_s3 = st.columns(3)
                    col_s1.metric("Filas válidas", f"{len(filas_validas_peg)} / {len(st.session_state.lab_pegado_filas)}")
                    col_s2.metric("Total guías", f"{total_guias:,}")
                    col_s3.metric("Valor total", f"${total_guias * tarifa_pegado:,.0f}")

                    obs_pegado = st.text_area("Observaciones (opcional)", key="lab_peg_obs")

                    if st.button("💾 Guardar Pegado", type="primary", key="btn_save_pegado"):
                        if not filas_validas_peg:
                            st.error("No hay filas válidas. Verifique códigos y que Final ≥ Inicial.")
                        else:
                            try:
                                cur_ins = conn.cursor()
                                consecutivos_peg = []
                                for fila in filas_validas_peg:
                                    cur_ins.execute("""
                                        INSERT INTO registro_labores
                                        (personal_id, orden_id, fecha, tipo_labor, cantidad,
                                         tarifa_unitaria, observaciones, aprobado)
                                        VALUES (%s, %s, %s, 'pegado_guia', %s, %s, %s, FALSE)
                                    """, (
                                        fila['personal_id'],
                                        orden_pegado_id,
                                        fecha_pegado,
                                        fila['cantidad'],
                                        tarifa_pegado,
                                        obs_pegado
                                    ))
                                    consecutivos_peg.append(cur_ins.lastrowid)
                                conn.commit()
                                cur_ins.close()

                                st.session_state.ultimo_consecutivo_labor = consecutivos_peg[-1]

                                # Guardar datos para PDF antes de limpiar
                                st.session_state['pendiente_pdf_pegado'] = {
                                    'fecha': fecha_pegado,
                                    'orden': orden_pegado_sel,
                                    'filas': list(filas_validas_peg),
                                    'tarifa': tarifa_pegado,
                                    'consecutivos': consecutivos_peg,
                                }

                                for rid in st.session_state.lab_pegado_filas:
                                    for k in [f"lab_peg_codigo_{rid}",
                                              f"lab_peg_inicial_{rid}", f"lab_peg_final_{rid}"]:
                                        st.session_state.pop(k, None)
                                st.session_state.lab_pegado_filas = []
                                st.session_state.form_labor_counter += 1

                                st.success(f"✅ {len(consecutivos_peg)} registro(s) guardados - Consecutivos: {', '.join([f'#{c}' for c in consecutivos_peg])}")
                                st.rerun()
                            except Exception as e_peg:
                                st.error(f"Error al guardar: {e_peg}")
                                conn.rollback()
                else:
                    st.info("↑ Haga clic en **➕ Agregar Fila** para comenzar")

                # ── Descarga PDF del último guardado ──────────────────────────
                if st.session_state.get('pendiente_pdf_pegado'):
                    pdf_data = st.session_state['pendiente_pdf_pegado']
                    fecha_str = pdf_data['fecha'].strftime('%Y-%m-%d') if hasattr(pdf_data['fecha'], 'strftime') else str(pdf_data['fecha'])
                    st.divider()
                    st.success("✅ Registro guardado — descarga la planilla en PDF:")
                    col_dl, col_ok = st.columns([2, 1])
                    with col_dl:
                        try:
                            pdf_bytes = generar_pdf_pegado(pdf_data)
                            st.download_button(
                                label="📄 Descargar PDF Pegado de Guías",
                                data=pdf_bytes,
                                file_name=f"pegado_guias_{fecha_str}.pdf",
                                mime="application/pdf",
                                key="dl_pdf_pegado",
                                type="primary",
                            )
                        except Exception as e_pdf:
                            st.error(f"Error generando PDF: {e_pdf}")
                    with col_ok:
                        if st.button("✓ Cerrar", key="btn_pdf_ok"):
                            del st.session_state['pendiente_pdf_pegado']
                            st.rerun()

                # ── Buscar PDF de fechas anteriores ───────────────────────────
                st.divider()
                with st.expander("🔍 Buscar planilla de una fecha anterior"):
                    col_h1, col_h2 = st.columns([1, 2])
                    with col_h1:
                        fecha_hist = st.date_input(
                            "Fecha a consultar",
                            value=date.today(),
                            key="hist_pegado_fecha"
                        )
                    with col_h2:
                        if st.button("🔎 Consultar", key="btn_hist_pegado"):
                            try:
                                cur_h = conn.cursor(dictionary=True)
                                cur_h.execute("""
                                    SELECT
                                        p.codigo,
                                        p.nombre_completo AS nombre,
                                        rl.cantidad,
                                        rl.tarifa_unitaria,
                                        rl.id AS consecutivo,
                                        o.numero_orden,
                                        c.nombre_empresa AS cliente
                                    FROM registro_labores rl
                                    JOIN personal p ON rl.personal_id = p.id
                                    JOIN ordenes o ON rl.orden_id = o.id
                                    JOIN clientes c ON o.cliente_id = c.id
                                    WHERE rl.fecha = %s AND rl.tipo_labor = 'pegado_guia'
                                    ORDER BY p.codigo
                                """, (fecha_hist,))
                                rows_hist = cur_h.fetchall()
                                cur_h.close()

                                if not rows_hist:
                                    st.warning("No hay registros de pegado para esa fecha.")
                                else:
                                    st.session_state['hist_pegado_rows'] = rows_hist
                                    st.session_state['hist_pegado_fecha_result'] = fecha_hist
                            except Exception as e_h:
                                st.error(f"Error consultando: {e_h}")

                    # Mostrar resultados y botón PDF unificado
                    if st.session_state.get('hist_pegado_rows') and st.session_state.get('hist_pegado_fecha_result') == fecha_hist:
                        rows_hist = st.session_state['hist_pegado_rows']

                        from collections import defaultdict

                        # Resumen por orden para la pantalla
                        grupos = defaultdict(list)
                        for r in rows_hist:
                            grupos[f"{r['numero_orden']} - {r['cliente']}"].append(r)

                        for orden_lbl, filas_g in grupos.items():
                            tarifa_g = float(filas_g[0]['tarifa_unitaria'])
                            total_g = sum(f['cantidad'] for f in filas_g)
                            st.markdown(f"**{orden_lbl}** — {len(filas_g)} trabajador(es) — {total_g:,} guías — ${total_g * tarifa_g:,.0f}")

                        # Un solo PDF con todas las órdenes del día
                        try:
                            fecha_slug = fecha_hist.strftime('%Y-%m-%d')
                            pdf_bytes_dia = generar_pdf_pegado_dia(fecha_hist, rows_hist)
                            st.download_button(
                                label="📄 Descargar PDF completo del día",
                                data=pdf_bytes_dia,
                                file_name=f"pegado_guias_{fecha_slug}.pdf",
                                mime="application/pdf",
                                key=f"dl_hist_dia_{fecha_slug}",
                                type="primary",
                            )
                        except Exception as e_pdf_h:
                            st.error(f"Error generando PDF: {e_pdf_h}")

            # =============================================
            # TRANSPORTE COMPLETO: mensajero fijo, filas por fecha/orden
            # =============================================
            elif tipo_labor == 'transporte_completo':
                st.markdown("### 🚌 Transporte Completo")
                st.info("💡 Fije el código del mensajero y agregue filas de **fecha + orden + tarifa**.")

                col_tc1, col_tc2, col_tc3 = st.columns([1, 3, 1])
                with col_tc1:
                    codigo_transp = st.text_input(
                        "Código Mensajero *", max_chars=4,
                        key=f"lab_transp_codigo_{st.session_state.form_labor_counter}"
                    )

                personal_transp = None
                if codigo_transp and len(codigo_transp) == 4:
                    personal_transp = personal_dict_lab.get(codigo_transp)
                    if personal_transp:
                        with col_tc2:
                            st.info(f"**Nombre:** {personal_transp['nombre_completo']}")
                    else:
                        with col_tc2:
                            st.error("❌ Personal no encontrado o inactivo")

                with col_tc3:
                    if st.button("🔄 Nuevo Mensajero", key="btn_nuevo_transp"):
                        for rid in st.session_state.lab_transp_filas:
                            for k in [f"lab_tr_fecha_{rid}", f"lab_tr_orden_{rid}", f"lab_tr_tarifa_{rid}"]:
                                st.session_state.pop(k, None)
                        st.session_state.lab_transp_filas = []
                        st.session_state.form_labor_counter += 1
                        st.rerun()

                if personal_transp:
                    st.markdown("---")

                    cursor.execute("""
                        SELECT tarifa FROM tarifas_servicios
                        WHERE tipo_servicio = 'transporte_completo' AND activo = TRUE
                        ORDER BY vigencia_desde DESC LIMIT 1
                    """)
                    tr_tc = cursor.fetchone()
                    tarifa_tc_default = int(tr_tc['tarifa']) if tr_tc else 55000

                    col_add_t, col_clear_t, _ = st.columns([1, 1, 3])
                    with col_add_t:
                        if st.button("➕ Agregar Fila", key="btn_add_transp"):
                            rid_new = st.session_state.lab_transp_next_id
                            st.session_state.lab_transp_next_id += 1
                            st.session_state[f"lab_tr_tarifa_{rid_new}"] = tarifa_tc_default
                            st.session_state.lab_transp_filas.append(rid_new)
                            st.rerun()

                    with col_clear_t:
                        if st.session_state.lab_transp_filas:
                            if st.button("🗑️ Limpiar Todo", key="btn_clear_transp"):
                                for rid in st.session_state.lab_transp_filas:
                                    for k in [f"lab_tr_fecha_{rid}", f"lab_tr_orden_{rid}", f"lab_tr_tarifa_{rid}"]:
                                        st.session_state.pop(k, None)
                                st.session_state.lab_transp_filas = []
                                st.rerun()

                    if st.session_state.lab_transp_filas:
                        hct = st.columns([1.8, 3.5, 1.8, 1.5, 0.5])
                        for ch, lbl in zip(hct, ["Fecha", "Orden", "Tarifa ($)", "Valor", ""]):
                            ch.markdown(f"**{lbl}**")

                        total_transp = 0
                        for rid in list(st.session_state.lab_transp_filas):
                            ct1, ct2, ct3, ct4, ct5 = st.columns([1.8, 3.5, 1.8, 1.5, 0.5])
                            with ct1:
                                st.date_input(
                                    "Fecha", value=date.today(),
                                    key=f"lab_tr_fecha_{rid}", label_visibility="collapsed"
                                )
                            with ct2:
                                st.selectbox(
                                    "Orden", list(orden_options_lab2.keys()),
                                    key=f"lab_tr_orden_{rid}", label_visibility="collapsed"
                                )
                            with ct3:
                                st.number_input(
                                    "Tarifa", min_value=0, step=1000,
                                    key=f"lab_tr_tarifa_{rid}", label_visibility="collapsed"
                                )
                            with ct4:
                                tarifa_actual = st.session_state.get(f"lab_tr_tarifa_{rid}", tarifa_tc_default)
                                st.markdown(f"**${tarifa_actual:,.0f}**")
                                total_transp += tarifa_actual
                            with ct5:
                                if st.button("✕", key=f"btn_del_tr_{rid}", help="Eliminar fila"):
                                    st.session_state.lab_transp_filas.remove(rid)
                                    for k in [f"lab_tr_fecha_{rid}", f"lab_tr_orden_{rid}", f"lab_tr_tarifa_{rid}"]:
                                        st.session_state.pop(k, None)
                                    st.rerun()

                        st.markdown("---")
                        col_tt1, col_tt2 = st.columns([3, 2])
                        col_tt1.metric("Total a pagar", f"${total_transp:,.0f}")
                        col_tt2.metric("Filas", len(st.session_state.lab_transp_filas))

                        obs_transp = st.text_area("Observaciones (opcional)", key="lab_tr_obs")

                        if st.button("💾 Guardar Transporte", type="primary", key="btn_save_transp"):
                            try:
                                cur_ins = conn.cursor()
                                consecutivos_tr = []
                                for rid in st.session_state.lab_transp_filas:
                                    fecha_v = st.session_state.get(f"lab_tr_fecha_{rid}", date.today())
                                    orden_lbl = st.session_state.get(f"lab_tr_orden_{rid}", list(orden_options_lab2.keys())[0])
                                    tarifa_v = st.session_state.get(f"lab_tr_tarifa_{rid}", tarifa_tc_default)
                                    cur_ins.execute("""
                                        INSERT INTO registro_labores
                                        (personal_id, orden_id, fecha, tipo_labor, cantidad,
                                         tarifa_unitaria, observaciones, aprobado)
                                        VALUES (%s, %s, %s, 'transporte_completo', 1, %s, %s, FALSE)
                                    """, (
                                        personal_transp['id'],
                                        orden_options_lab2[orden_lbl],
                                        fecha_v,
                                        tarifa_v,
                                        obs_transp
                                    ))
                                    consecutivos_tr.append(cur_ins.lastrowid)
                                conn.commit()
                                cur_ins.close()

                                st.session_state.ultimo_consecutivo_labor = consecutivos_tr[-1]
                                for rid in st.session_state.lab_transp_filas:
                                    for k in [f"lab_tr_fecha_{rid}", f"lab_tr_orden_{rid}", f"lab_tr_tarifa_{rid}"]:
                                        st.session_state.pop(k, None)
                                st.session_state.lab_transp_filas = []
                                st.session_state.form_labor_counter += 1

                                if len(consecutivos_tr) > 1:
                                    st.success(f"✅ {len(consecutivos_tr)} transportes registrados - Consecutivos: {', '.join([f'#{c}' for c in consecutivos_tr])}")
                                else:
                                    st.success(f"✅ Transporte registrado - Consecutivo: #{consecutivos_tr[0]}")
                                st.rerun()

                            except Exception as e_tr:
                                st.error(f"Error al guardar: {e_tr}")
                                conn.rollback()
                    else:
                        st.info("↑ Haga clic en **➕ Agregar Fila** para ingresar transportes")

                elif not personal_transp and not (codigo_transp and len(codigo_transp) == 4):
                    st.info("👆 Ingrese el código del mensajero para comenzar")

            # =============================================
            # MEDIO TRANSPORTE: simple, tarifa fija
            # =============================================
            else:
                st.markdown("### 🚐 Medio Transporte")

                col_mt1, col_mt2 = st.columns([1, 3])
                with col_mt1:
                    codigo_buscar_labor = st.text_input(
                        "Código del Personal *", max_chars=4,
                        help="Ingrese el código de 4 dígitos",
                        key=f"codigo_labor_{st.session_state.form_labor_counter}"
                    )

                personal_info_labor = None
                if codigo_buscar_labor and len(codigo_buscar_labor) == 4:
                    personal_info_labor = personal_dict_lab.get(codigo_buscar_labor)
                    if personal_info_labor:
                        with col_mt2:
                            st.info(f"**Nombre:** {personal_info_labor['nombre_completo']}")
                    else:
                        with col_mt2:
                            st.error("❌ Personal no encontrado o inactivo")

                if personal_info_labor:
                    with st.form(key=f"form_registro_labor_{st.session_state.form_labor_counter}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            fecha_labor_lab = st.date_input(
                                "Fecha de la Labor *",
                                value=date.today(),
                                key=f"fecha_labor_mt_{st.session_state.form_labor_counter}"
                            )
                        with col2:
                            orden_sel_lab = st.selectbox("Orden *", list(orden_options_lab2.keys()))
                            orden_id_lab = orden_options_lab2[orden_sel_lab]

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            cantidad_mt = st.number_input("Cantidad *", min_value=1, value=1)
                        with col2:
                            cursor.execute("""
                                SELECT tarifa FROM tarifas_servicios
                                WHERE tipo_servicio = 'medio_transporte' AND activo = TRUE
                                ORDER BY vigencia_desde DESC LIMIT 1
                            """)
                            tr_mt = cursor.fetchone()
                            tarifa_mt = float(tr_mt['tarifa']) if tr_mt else 0.0
                            st.metric("Tarifa Unitaria", f"${tarifa_mt:,.0f}")
                        with col3:
                            st.metric("Total", f"${cantidad_mt * tarifa_mt:,.0f}")

                        observaciones_lab = st.text_area(
                            "Observaciones",
                            key=f"obs_labor_{st.session_state.form_labor_counter}"
                        )
                        submitted_lab = st.form_submit_button("💾 Guardar Medio Transporte", type="primary")

                        if submitted_lab:
                            if cantidad_mt <= 0:
                                st.error("La cantidad debe ser mayor a 0")
                            else:
                                try:
                                    cur_mt = conn.cursor()
                                    cur_mt.execute("""
                                        INSERT INTO registro_labores
                                        (personal_id, orden_id, fecha, tipo_labor, cantidad,
                                         tarifa_unitaria, observaciones, aprobado)
                                        VALUES (%s, %s, %s, 'medio_transporte', %s, %s, %s, FALSE)
                                    """, (
                                        personal_info_labor['id'],
                                        orden_id_lab,
                                        fecha_labor_lab,
                                        cantidad_mt,
                                        tarifa_mt,
                                        observaciones_lab
                                    ))
                                    consecutivo_labor = cur_mt.lastrowid
                                    conn.commit()
                                    cur_mt.close()

                                    st.session_state.ultimo_consecutivo_labor = consecutivo_labor
                                    st.session_state.form_labor_counter += 1
                                    st.success(f"✅ Labor registrada - Consecutivo: #{consecutivo_labor}")
                                    st.rerun()
                                except Exception as e_mt:
                                    st.error(f"Error al guardar: {e_mt}")
                                    conn.rollback()
                else:
                    st.info("👆 Ingrese el código del personal para comenzar el registro")

    except Exception as e:
        st.error(f"Error: {e}")

# =====================================================
# TAB 3: LABORES ADMINISTRATIVAS
# =====================================================
with tab3:
    st.subheader("Registro de Labores Administrativas")
    st.info("📋 Labores generales que no están asociadas a una orden específica (cortar hojas, organizar, limpieza, etc.)")

    # Mostrar último consecutivo registrado
    if st.session_state.ultimo_consecutivo_admin:
        st.success(f"✅ Último registro guardado - Consecutivo: #{st.session_state.ultimo_consecutivo_admin}")

    st.divider()

    try:
        cursor = conn.cursor(dictionary=True)

        # Búsqueda de personal
        st.markdown("### 👤 Información del Personal")

        col1, col2 = st.columns([1, 3])

        with col1:
            codigo_buscar_admin = st.text_input(
                "Código del Personal *",
                max_chars=4,
                help="Ingrese el código de 4 dígitos",
                key=f"codigo_admin_{st.session_state.form_admin_counter}"
            )

        personal_info_admin = None
        if codigo_buscar_admin and len(codigo_buscar_admin) == 4:
            cursor.execute("""
                SELECT id, codigo, nombre_completo, identificacion, tipo_personal
                FROM personal
                WHERE codigo = %s AND activo = TRUE
            """, (codigo_buscar_admin,))
            personal_info_admin = cursor.fetchone()

            if personal_info_admin:
                with col2:
                    st.info(f"**Nombre:** {personal_info_admin['nombre_completo']} | **Cédula:** {personal_info_admin['identificacion']}")
            else:
                with col2:
                    st.error("❌ Personal no encontrado o inactivo")

        st.divider()

        # Formulario de registro solo si hay personal seleccionado
        if personal_info_admin:
            st.markdown("### 🏢 Registro de Labor Administrativa")

            # Obtener órdenes activas para asignación opcional
            cursor.execute("""
                SELECT o.id, o.numero_orden, c.nombre_empresa as cliente
                FROM ordenes o
                JOIN clientes c ON o.cliente_id = c.id
                WHERE o.estado = 'activa'
                ORDER BY o.numero_orden DESC
                LIMIT 100
            """)
            ordenes_admin_disponibles = cursor.fetchall()
            ordenes_admin_options = {
                f"{o['numero_orden']} - {o['cliente']}": o['id']
                for o in ordenes_admin_disponibles
            }

            # Selección de órdenes FUERA del form para renderizar inputs dinámicos
            st.markdown("#### 📦 Asignar a Órdenes (opcional)")
            ordenes_seleccionadas_admin = st.multiselect(
                "Seleccione una o varias órdenes",
                list(ordenes_admin_options.keys()),
                help="Para cada orden podrá definir horas individuales. Sin selección se registra como labor general.",
                key=f"ordenes_admin_{st.session_state.form_admin_counter}"
            )

            with st.form(key=f"form_registro_admin_{st.session_state.form_admin_counter}"):

                col1, col2 = st.columns(2)

                with col1:
                    fecha_admin = st.date_input(
                        "Fecha de la Labor *",
                        value=date.today(),
                        help="Fecha en que se realizó el trabajo"
                    )

                with col2:
                    tipo_labor_admin = st.selectbox(
                        "Tipo de Labor Administrativa *",
                        ["cortar_hojas", "organizacion_zona", "limpieza_area", "mantenimiento_equipos", "archivo_documentos", "cajoneras", "otros_administrativos"],
                        format_func=lambda x: {
                            'cortar_hojas': 'Cortar Hojas',
                            'organizacion_zona': 'Organización de Zona de Trabajo',
                            'limpieza_area': 'Limpieza del Área',
                            'mantenimiento_equipos': 'Mantenimiento de Equipos',
                            'archivo_documentos': 'Archivo de Documentos',
                            'cajoneras': 'Cajoneras',
                            'otros_administrativos': 'Otros Administrativos'
                        }[x]
                    )

                # Obtener tarifa administrativa
                cursor.execute("""
                    SELECT tarifa FROM tarifas_servicios
                    WHERE tipo_servicio = 'alistamiento_hora'
                      AND activo = TRUE
                    ORDER BY vigencia_desde DESC
                    LIMIT 1
                """)
                tarifa_result_admin = cursor.fetchone()
                tarifa_admin = float(tarifa_result_admin['tarifa']) if tarifa_result_admin else 0.0

                if ordenes_seleccionadas_admin:
                    # --- Modo con órdenes: horas individuales por orden ---
                    st.markdown("#### ⏱️ Horas por Orden")
                    st.caption(f"Tarifa por hora: ${tarifa_admin:,.0f}")

                    ordenes_inputs = []
                    total_general = 0.0

                    for i, orden_label in enumerate(ordenes_seleccionadas_admin):
                        col1, col2, col3 = st.columns([3, 1.5, 1.5])
                        with col1:
                            st.write(f"**{orden_label}**")
                        with col2:
                            h_input = st.text_input(
                                "Horas (HH:MM)",
                                value="0:00",
                                key=f"h_ord_admin_{i}_{st.session_state.form_admin_counter}"
                            )
                        with col3:
                            horas_i, _ = convertir_horas_a_decimal(h_input)
                            horas_i = horas_i if horas_i else 0.0
                            valor_i = horas_i * tarifa_admin
                            st.metric("Valor", f"${valor_i:,.0f}")
                            total_general += valor_i

                        ordenes_inputs.append({'label': orden_label, 'horas_input': h_input})

                    st.markdown(f"**Total general: ${total_general:,.0f}**")

                else:
                    # --- Modo sin orden: horas generales ---
                    col1, col2 = st.columns(2)

                    with col1:
                        horas_admin_input = st.text_input(
                            "Horas Trabajadas (HH:MM) *",
                            value="0:00",
                            help="Formato HH:MM - Ejemplo: 2:45",
                            key=f"horas_admin_{st.session_state.form_admin_counter}"
                        )

                    with col2:
                        st.metric("Tarifa por Hora", f"${tarifa_admin:,.0f}")

                    horas_admin_gen, error_admin_gen = convertir_horas_a_decimal(horas_admin_input)
                    if horas_admin_gen is None:
                        horas_admin_gen = 0.0

                    total_admin = horas_admin_gen * tarifa_admin
                    st.metric("Total a Pagar", f"${total_admin:,.0f}")

                descripcion_admin = st.text_area(
                    "Descripción de la Labor *",
                    help="Detalle qué trabajo administrativo se realizó",
                    key=f"desc_admin_{st.session_state.form_admin_counter}"
                )

                submitted_admin = st.form_submit_button("💾 Guardar Labor Administrativa", type="primary")

                if submitted_admin:
                    if not descripcion_admin or len(descripcion_admin.strip()) < 10:
                        st.error("Debe ingresar una descripción detallada (mínimo 10 caracteres)")

                    elif ordenes_seleccionadas_admin:
                        # --- Guardar con órdenes individuales ---
                        errores_formato = []
                        datos_ordenes = []

                        for oi in ordenes_inputs:
                            horas_val, err_val = convertir_horas_a_decimal(oi['horas_input'])
                            if err_val:
                                errores_formato.append(f"{oi['label']}: {err_val}")
                            elif horas_val and horas_val > 0:
                                datos_ordenes.append({
                                    'label': oi['label'],
                                    'horas': horas_val,
                                    'orden_id': ordenes_admin_options[oi['label']]
                                })

                        if errores_formato:
                            for ef in errores_formato:
                                st.error(ef)
                        elif not datos_ordenes:
                            st.error("Debe ingresar horas > 0 en al menos una orden")
                        else:
                            try:
                                cursor = conn.cursor()
                                consecutivos_admin = []
                                obs_texto = f"[ADMIN] {tipo_labor_admin}: {descripcion_admin}"

                                for dato in datos_ordenes:
                                    cursor.execute("""
                                        INSERT INTO registro_horas
                                        (personal_id, orden_id, fecha, horas_trabajadas, tarifa_hora,
                                         tipo_trabajo, observaciones, aprobado)
                                        VALUES (%s, %s, %s, %s, %s, 'alistamiento_sobres', %s, FALSE)
                                    """, (
                                        personal_info_admin['id'],
                                        dato['orden_id'],
                                        fecha_admin,
                                        dato['horas'],
                                        tarifa_admin,
                                        obs_texto
                                    ))
                                    consecutivos_admin.append(cursor.lastrowid)

                                conn.commit()

                                crear_o_actualizar_subsidio(conn, personal_info_admin['id'], fecha_admin, 'automatico')
                                calculo = calcular_subsidio_transporte(conn, personal_info_admin['id'], fecha_admin)

                                st.session_state.ultimo_consecutivo_admin = consecutivos_admin[-1]
                                st.session_state.form_admin_counter += 1

                                st.success(f"✅ Labor registrada en {len(consecutivos_admin)} órdenes - Consecutivos: {', '.join([f'#{c}' for c in consecutivos_admin])}")
                                h_total = int(calculo['horas_totales'])
                                m_total = int((calculo['horas_totales'] - h_total) * 60)
                                st.success(f"⏱️ Total horas del día: **{h_total}:{m_total:02d}** (Alistamiento: {calculo['horas_alistamiento']:.2f}h + Admin: {calculo['horas_admin']:.2f}h)")
                                st.info(f"🚌 Subsidio: **{calculo['tipo_subsidio'].replace('_', ' ').title()}** - ${calculo['tarifa']:,.0f}")
                                st.rerun()

                            except Exception as e:
                                st.error(f"Error al guardar: {e}")
                                conn.rollback()

                    else:
                        # --- Guardar sin orden ---
                        horas_admin, error_admin = convertir_horas_a_decimal(horas_admin_input)
                        if error_admin:
                            st.error(f"Error en formato: {error_admin}")
                        elif not horas_admin or horas_admin <= 0:
                            st.error("Las horas trabajadas deben ser mayor a 0")
                        else:
                            try:
                                cursor = conn.cursor()
                                obs_texto = f"[ADMIN] {tipo_labor_admin}: {descripcion_admin}"

                                cursor.execute("""
                                    INSERT INTO registro_horas
                                    (personal_id, orden_id, fecha, horas_trabajadas, tarifa_hora,
                                     tipo_trabajo, observaciones, aprobado)
                                    VALUES (%s, NULL, %s, %s, %s, 'alistamiento_sobres', %s, FALSE)
                                """, (
                                    personal_info_admin['id'],
                                    fecha_admin,
                                    horas_admin,
                                    tarifa_admin,
                                    obs_texto
                                ))

                                consecutivo_admin = cursor.lastrowid
                                conn.commit()

                                crear_o_actualizar_subsidio(conn, personal_info_admin['id'], fecha_admin, 'automatico')
                                calculo = calcular_subsidio_transporte(conn, personal_info_admin['id'], fecha_admin)

                                st.session_state.ultimo_consecutivo_admin = consecutivo_admin
                                st.session_state.form_admin_counter += 1

                                st.success(f"✅ Labor administrativa registrada - Consecutivo: #{consecutivo_admin}")
                                h_total = int(calculo['horas_totales'])
                                m_total = int((calculo['horas_totales'] - h_total) * 60)
                                st.success(f"⏱️ Total horas del día: **{h_total}:{m_total:02d}** (Alistamiento: {calculo['horas_alistamiento']:.2f}h + Admin: {calculo['horas_admin']:.2f}h)")
                                st.info(f"🚌 Subsidio: **{calculo['tipo_subsidio'].replace('_', ' ').title()}** - ${calculo['tarifa']:,.0f}")
                                st.rerun()

                            except Exception as e:
                                st.error(f"Error al guardar: {e}")
                                conn.rollback()

        else:
            st.info("👆 Ingrese el código del personal para comenzar el registro")

    except Exception as e:
        st.error(f"Error: {e}")

# =====================================================
# TAB 4: CONSULTAR REGISTROS
# =====================================================
with tab4:
    st.subheader("Consultar y Editar Registros")

    # Variables de edición
    if 'editando_registro' not in st.session_state:
        st.session_state.editando_registro = None
    if 'confirmando_eliminacion' not in st.session_state:
        st.session_state.confirmando_eliminacion = None

    try:
        cursor = conn.cursor(dictionary=True)

        col1, col2, col3 = st.columns(3)

        with col1:
            tipo_consulta = st.selectbox(
                "Tipo de Registro",
                ["Todos", "Horas de Alistamiento", "Labores", "Labores Administrativas", "Subsidio Transporte"]
            )

        with col2:
            fecha_desde = st.date_input("Desde", value=date.today())

        with col3:
            fecha_hasta = st.date_input("Hasta", value=date.today())

        st.divider()

        # Botón para recalcular subsidios
        with st.expander("🔄 Recalcular Subsidios de Transporte", expanded=False):
            st.warning("⚠️ Esto recalculará los subsidios de transporte para el período seleccionado, sumando las horas de alistamiento + administrativas.")

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("🔄 Recalcular Subsidios del Período", type="primary"):
                    resultado = recalcular_subsidios_rango(conn, fecha_desde, fecha_hasta)
                    st.success(f"✅ Recálculo completado: {resultado['creados']} creados, {resultado['actualizados']} actualizados, {resultado['errores']} errores")
                    st.rerun()

            with col_btn2:
                # Opción para recalcular desde el 1 de enero
                if st.button("📅 Recalcular desde 01/01/2026"):
                    fecha_inicio_anio = date(2026, 1, 1)
                    # Actualizar retroactivamente todos los subsidios con tarifa $8.333
                    try:
                        cursor_retro = conn.cursor()
                        cursor_retro.execute("""
                            UPDATE subsidio_transporte
                            SET tarifa = 8333,
                                origen = 'recalculado',
                                fecha_modificacion = CURRENT_TIMESTAMP
                            WHERE fecha >= '2026-01-01' AND liquidado = FALSE AND tarifa != 8333
                        """)
                        actualizados_retro = cursor_retro.rowcount
                        conn.commit()
                        cursor_retro.close()
                    except Exception:
                        actualizados_retro = 0
                    resultado = recalcular_subsidios_rango(conn, fecha_inicio_anio, date.today())
                    st.success(f"✅ Recálculo completado desde 01/01/2026: {resultado['creados']} creados, {resultado['actualizados']} actualizados, {actualizados_retro} tarifas corregidas a $8.333")
                    st.rerun()

        st.divider()

        if tipo_consulta == "Todos":
            st.markdown("### 📋 Resumen de Labores por Fecha")

            # Auto-calcular subsidios faltantes — solo una vez por carga de página,
            # no en cada rerun (evita writes automáticos en cada interacción del usuario)
            _auto_key = f"_auto_subsidios_{fecha_desde}_{fecha_hasta}"
            if _auto_key not in st.session_state:
                subsidios_creados = auto_calcular_subsidios_consulta(conn, fecha_desde, fecha_hasta)
                st.session_state[_auto_key] = subsidios_creados
            else:
                subsidios_creados = st.session_state[_auto_key]
            if subsidios_creados > 0:
                st.info(f"Se calcularon {subsidios_creados} subsidio(s) de transporte automáticamente")

            # Consulta unificada de todos los registros (incluye subsidios)
            cursor.execute("""
                SELECT
                    'Horas' as tipo_registro,
                    rh.id,
                    p.codigo,
                    p.nombre_completo,
                    COALESCE(o.numero_orden, 'N/A') as numero_orden,
                    rh.fecha,
                    rh.horas_trabajadas as cantidad,
                    rh.tarifa_hora as tarifa,
                    rh.total,
                    rh.tipo_trabajo as subtipo,
                    rh.observaciones,
                    rh.aprobado,
                    rh.fecha_creacion,
                    CASE
                        WHEN rh.observaciones LIKE '[ADMIN]%%'
                        THEN 'Administrativa'
                        ELSE 'Alistamiento'
                    END as categoria
                FROM registro_horas rh
                JOIN personal p ON rh.personal_id = p.id
                LEFT JOIN ordenes o ON rh.orden_id = o.id
                WHERE rh.fecha BETWEEN %s AND %s

                UNION ALL

                SELECT
                    'Labor' as tipo_registro,
                    rl.id,
                    p.codigo,
                    p.nombre_completo,
                    o.numero_orden,
                    rl.fecha,
                    rl.cantidad,
                    rl.tarifa_unitaria as tarifa,
                    rl.total,
                    rl.tipo_labor as subtipo,
                    rl.observaciones,
                    rl.aprobado,
                    rl.fecha_creacion,
                    'Labor' as categoria
                FROM registro_labores rl
                JOIN personal p ON rl.personal_id = p.id
                LEFT JOIN ordenes o ON rl.orden_id = o.id
                WHERE rl.fecha BETWEEN %s AND %s

                UNION ALL

                SELECT
                    'Subsidio' as tipo_registro,
                    st.id,
                    p.codigo,
                    p.nombre_completo,
                    'N/A' as numero_orden,
                    st.fecha,
                    st.horas_totales as cantidad,
                    st.tarifa,
                    st.total,
                    st.tipo_subsidio as subtipo,
                    st.observaciones,
                    st.aprobado,
                    st.fecha_creacion,
                    'Subsidio Transporte' as categoria
                FROM subsidio_transporte st
                JOIN personal p ON st.personal_id = p.id
                WHERE st.fecha BETWEEN %s AND %s

                ORDER BY fecha DESC, nombre_completo
            """, (fecha_desde, fecha_hasta, fecha_desde, fecha_hasta, fecha_desde, fecha_hasta))

            registros_todos = cursor.fetchall()

            if registros_todos:
                st.info(f"📊 Se encontraron {len(registros_todos)} registros en total")

                # Agrupar registros por fecha
                from collections import defaultdict
                registros_por_fecha = defaultdict(list)
                for reg in registros_todos:
                    registros_por_fecha[reg['fecha']].append(reg)

                # Mostrar por fecha
                for fecha in sorted(registros_por_fecha.keys(), reverse=True):
                    registros_dia = registros_por_fecha[fecha]

                    # Calcular totales del día
                    total_dinero_dia = sum([r['total'] for r in registros_dia])
                    total_horas_dia = sum([r['cantidad'] for r in registros_dia if r['tipo_registro'] == 'Horas'])
                    total_labores_dia = sum([r['cantidad'] for r in registros_dia if r['tipo_registro'] == 'Labor'])
                    personal_unico = len(set([r['nombre_completo'] for r in registros_dia]))

                    with st.expander(
                        f"📅 **{fecha.strftime('%A, %d de %B de %Y')}** - {personal_unico} personas - {len(registros_dia)} registros - ${total_dinero_dia:,.0f}",
                        expanded=False
                    ):
                        # Resumen del día
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Personal", personal_unico)
                        with col2:
                            st.metric("Total Horas", f"{total_horas_dia:.2f}h")
                        with col3:
                            st.metric("Total Labores", f"{int(total_labores_dia)}")
                        with col4:
                            st.metric("Total $", f"${total_dinero_dia:,.0f}")

                        st.divider()

                        # Agrupar por persona
                        registros_por_persona = defaultdict(list)
                        for reg in registros_dia:
                            registros_por_persona[reg['nombre_completo']].append(reg)

                        # Mostrar cada persona
                        for nombre_persona in sorted(registros_por_persona.keys()):
                            registros_persona = registros_por_persona[nombre_persona]
                            total_persona = sum([r['total'] for r in registros_persona])
                            codigo_persona = registros_persona[0]['codigo']

                            st.markdown(f"#### 👤 {nombre_persona} ({codigo_persona}) - ${total_persona:,.0f}")

                            # Tabla con los registros de esta persona
                            for reg in registros_persona:
                                col1, col2, col3, col4, col5, col6 = st.columns([1.5, 2, 1, 1.5, 0.4, 0.4])

                                with col1:
                                    if reg['tipo_registro'] == 'Horas':
                                        icono = '⏰'
                                    elif reg['tipo_registro'] == 'Subsidio':
                                        icono = '🚌'
                                    else:
                                        icono = '🔧'
                                    st.write(f"{icono} **{reg['categoria']}**")

                                with col2:
                                    if reg['tipo_registro'] == 'Horas':
                                        if reg['categoria'] == 'Administrativa':
                                            # Extraer tipo de labor administrativa
                                            tipo_labor = reg['observaciones'].split(':')[0].replace('[ADMIN] ', '') if reg['observaciones'] and '[ADMIN]' in reg['observaciones'] else 'Admin'
                                            orden_info = f" - Orden: {reg['numero_orden']}" if reg['numero_orden'] and reg['numero_orden'] != 'N/A' else ""
                                            st.write(f"{tipo_labor}{orden_info}")
                                        else:
                                            tipo_texto = 'Sobres' if reg['subtipo'] == 'alistamiento_sobres' else 'Paquetes'
                                            st.write(f"{tipo_texto} - Orden: {reg['numero_orden']}")
                                    elif reg['tipo_registro'] == 'Subsidio':
                                        tipo_subsidio_texto = 'Completo' if reg['subtipo'] == 'transporte_completo' else 'Medio'
                                        st.write(f"Subsidio {tipo_subsidio_texto}")
                                    else:
                                        tipo_labor_map = {
                                            'pegado_guia': 'Pegado',
                                            'transporte_completo': 'Transporte Completo',
                                            'medio_transporte': 'Medio Transporte'
                                        }
                                        st.write(f"{tipo_labor_map.get(reg['subtipo'], reg['subtipo'])} - Orden: {reg['numero_orden']}")

                                with col3:
                                    if reg['tipo_registro'] == 'Horas':
                                        # Convertir horas decimal a HH:MM
                                        horas_decimal = reg['cantidad']
                                        horas_enteras = int(horas_decimal)
                                        minutos = int((horas_decimal - horas_enteras) * 60)
                                        st.write(f"⏱️ {horas_enteras}:{minutos:02d}")
                                    elif reg['tipo_registro'] == 'Subsidio':
                                        # Mostrar horas base del subsidio
                                        horas_decimal = reg['cantidad']
                                        horas_enteras = int(horas_decimal)
                                        minutos = int((horas_decimal - horas_enteras) * 60)
                                        st.write(f"⏱️ {horas_enteras}:{minutos:02d}h base")
                                    else:
                                        st.write(f"📦 {int(reg['cantidad'])} und")

                                with col4:
                                    st.write(f"💰 ${reg['total']:,.0f}")
                                    if not reg['aprobado']:
                                        st.caption("⏳ Pendiente")

                                with col5:
                                    if st.button("✏️", key=f"edit_fecha_{reg['tipo_registro']}_{reg['id']}", help="Editar"):
                                        st.session_state.editando_registro = {
                                            'tipo': reg['tipo_registro'],
                                            'id': reg['id'],
                                            'data': reg
                                        }
                                        st.rerun()

                                with col6:
                                    if st.button("🗑️", key=f"del_fecha_{reg['tipo_registro']}_{reg['id']}", help="Eliminar"):
                                        st.session_state.confirmando_eliminacion = {
                                            'tipo': reg['tipo_registro'],
                                            'id': reg['id'],
                                            'data': reg
                                        }
                                        st.rerun()

                            st.divider()

                # Métricas generales del período
                st.markdown("---")
                st.markdown("### 📊 Resumen del Período")
                col1, col2, col3, col4, col5 = st.columns(5)

                with col1:
                    st.metric("Días", len(registros_por_fecha))
                with col2:
                    st.metric("Total Registros", len(registros_todos))
                with col3:
                    total_horas = sum([r['cantidad'] for r in registros_todos if r['tipo_registro'] == 'Horas'])
                    st.metric("Total Horas", f"{total_horas:.2f}h")
                with col4:
                    total_labores = sum([r['cantidad'] for r in registros_todos if r['tipo_registro'] == 'Labor'])
                    st.metric("Total Labores", f"{int(total_labores)}")
                with col5:
                    total_valor = sum([float(r['total']) for r in registros_todos])
                    st.metric("Valor Total", f"${total_valor:,.0f}")

                # Desglose por tipo de labor
                st.markdown("### 📈 Desglose por Tipo de Labor")
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.markdown("**⏰ Horas de Alistamiento**")
                    horas_alist = [r for r in registros_todos if r['tipo_registro'] == 'Horas' and r['categoria'] == 'Alistamiento']
                    if horas_alist:
                        total_h = sum([r['cantidad'] for r in horas_alist])
                        total_dinero = sum([r['total'] for r in horas_alist])
                        st.write(f"• {total_h:.2f} horas")
                        st.write(f"• ${total_dinero:,.0f}")
                    else:
                        st.write("Sin registros")

                with col2:
                    st.markdown("**🏢 Labores Administrativas**")
                    horas_admin = [r for r in registros_todos if r['tipo_registro'] == 'Horas' and r['categoria'] == 'Administrativa']
                    if horas_admin:
                        total_h = sum([r['cantidad'] for r in horas_admin])
                        total_dinero = sum([r['total'] for r in horas_admin])
                        st.write(f"• {total_h:.2f} horas")
                        st.write(f"• ${total_dinero:,.0f}")
                    else:
                        st.write("Sin registros")

                with col3:
                    st.markdown("**🔧 Labores (Pegado/Transporte)**")
                    labores = [r for r in registros_todos if r['tipo_registro'] == 'Labor']
                    if labores:
                        total_cant = sum([r['cantidad'] for r in labores])
                        total_dinero = sum([r['total'] for r in labores])
                        st.write(f"• {int(total_cant)} unidades")
                        st.write(f"• ${total_dinero:,.0f}")
                    else:
                        st.write("Sin registros")

                with col4:
                    st.markdown("**🚌 Subsidio Transporte**")
                    subsidios = [r for r in registros_todos if r['tipo_registro'] == 'Subsidio']
                    if subsidios:
                        completos = sum(1 for s in subsidios if s['subtipo'] == 'transporte_completo')
                        medios = sum(1 for s in subsidios if s['subtipo'] == 'medio_transporte')
                        total_dinero = sum([r['total'] for r in subsidios])
                        st.write(f"• {len(subsidios)} subsidios")
                        st.write(f"• {completos} completos, {medios} medios")
                        st.write(f"• ${total_dinero:,.0f}")
                    else:
                        st.write("Sin subsidios")

            else:
                st.info("No hay registros en el rango de fechas seleccionado")

        elif tipo_consulta == "Horas de Alistamiento":
            st.markdown("### ⏰ Registros de Horas de Alistamiento")

            cursor.execute("""
                SELECT
                    rh.id as consecutivo,
                    p.codigo,
                    p.nombre_completo,
                    o.numero_orden,
                    rh.orden_id,
                    rh.fecha,
                    rh.horas_trabajadas,
                    rh.tarifa_hora,
                    rh.total,
                    rh.tipo_trabajo,
                    rh.aprobado,
                    rh.observaciones,
                    rh.fecha_creacion
                FROM registro_horas rh
                JOIN personal p ON rh.personal_id = p.id
                LEFT JOIN ordenes o ON rh.orden_id = o.id
                WHERE rh.fecha BETWEEN %s AND %s
                ORDER BY rh.fecha_creacion DESC
                LIMIT 100
            """, (fecha_desde, fecha_hasta))

            registros = cursor.fetchall()

            if registros:
                # Mostrar cada registro con opción de editar
                for reg in registros:
                    with st.expander(
                        f"#{reg['consecutivo']} - {reg['nombre_completo']} - {reg['fecha'].strftime('%d/%m/%Y')} - {reg['horas_trabajadas']}h - ${reg['total']:,.0f} {'✅' if reg['aprobado'] else '⏳'}"
                    ):
                        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 0.5, 0.5])

                        with col1:
                            st.write(f"**Código:** {reg['codigo']}")
                            st.write(f"**Orden:** {reg.get('numero_orden', 'N/A')}")
                            st.write(f"**Tipo:** {'Sobres' if reg['tipo_trabajo'] == 'alistamiento_sobres' else 'Paquetes'}")

                        with col2:
                            st.write(f"**Fecha:** {reg['fecha'].strftime('%d/%m/%Y')}")
                            st.write(f"**Horas:** {reg['horas_trabajadas']}")
                            st.write(f"**Tarifa/h:** ${reg['tarifa_hora']:,.0f}")

                        with col3:
                            st.write(f"**Total:** ${reg['total']:,.0f}")
                            st.write(f"**Aprobado:** {'✅ Sí' if reg['aprobado'] else '⏳ Pendiente'}")
                            if reg.get('observaciones'):
                                st.write(f"**Obs:** {reg['observaciones'][:50]}...")

                        with col4:
                            if st.button("✏️", key=f"edit_horas_{reg['consecutivo']}", help="Editar"):
                                st.session_state.editando_registro = {
                                    'tipo': 'Horas',
                                    'id': reg['consecutivo'],
                                    'data': reg
                                }
                                st.rerun()

                        with col5:
                            if st.button("🗑️", key=f"del_horas_{reg['consecutivo']}", help="Eliminar"):
                                st.session_state.confirmando_eliminacion = {
                                    'tipo': 'Horas',
                                    'id': reg['consecutivo'],
                                    'data': reg
                                }
                                st.rerun()

                # Métricas
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Registros", len(registros))
                with col2:
                    total_horas = sum([r['horas_trabajadas'] for r in registros])
                    st.metric("Total Horas", f"{total_horas:.2f}")
                with col3:
                    total_valor = sum([float(r['total']) for r in registros])
                    st.metric("Valor Total", f"${total_valor:,.0f}")
            else:
                st.info("No hay registros en el rango de fechas seleccionado")

        elif tipo_consulta == "Labores":
            st.markdown("### 🔧 Registros de Labores")

            cursor.execute("""
                SELECT
                    rl.id as consecutivo,
                    p.codigo,
                    p.nombre_completo,
                    o.numero_orden,
                    rl.orden_id,
                    rl.fecha,
                    rl.tipo_labor,
                    rl.cantidad,
                    rl.tarifa_unitaria,
                    rl.total,
                    rl.observaciones,
                    rl.aprobado,
                    rl.fecha_creacion
                FROM registro_labores rl
                JOIN personal p ON rl.personal_id = p.id
                LEFT JOIN ordenes o ON rl.orden_id = o.id
                WHERE rl.fecha BETWEEN %s AND %s
                ORDER BY rl.fecha_creacion DESC
                LIMIT 100
            """, (fecha_desde, fecha_hasta))

            registros_lab = cursor.fetchall()

            if registros_lab:
                # Mostrar cada registro con opción de editar
                for reg in registros_lab:
                    tipo_labor_texto = {
                        'pegado_guia': 'Pegado Guías',
                        'transporte_completo': 'Transporte Completo',
                        'medio_transporte': 'Medio Transporte'
                    }.get(reg['tipo_labor'], reg['tipo_labor'])

                    with st.expander(
                        f"#{reg['consecutivo']} - {reg['nombre_completo']} - {reg['fecha'].strftime('%d/%m/%Y')} - {tipo_labor_texto} - ${reg['total']:,.0f} {'✅' if reg['aprobado'] else '⏳'}"
                    ):
                        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 0.5, 0.5])

                        with col1:
                            st.write(f"**Código:** {reg['codigo']}")
                            st.write(f"**Orden:** {reg.get('numero_orden', 'N/A')}")
                            st.write(f"**Tipo Labor:** {tipo_labor_texto}")

                        with col2:
                            st.write(f"**Fecha:** {reg['fecha'].strftime('%d/%m/%Y')}")
                            st.write(f"**Cantidad:** {reg['cantidad']}")
                            st.write(f"**Tarifa Unit.:** ${reg['tarifa_unitaria']:,.0f}")

                        with col3:
                            st.write(f"**Total:** ${reg['total']:,.0f}")
                            st.write(f"**Aprobado:** {'✅ Sí' if reg['aprobado'] else '⏳ Pendiente'}")
                            if reg.get('observaciones'):
                                st.write(f"**Obs:** {reg['observaciones'][:50]}...")

                        with col4:
                            if st.button("✏️", key=f"edit_labor_{reg['consecutivo']}", help="Editar"):
                                st.session_state.editando_registro = {
                                    'tipo': 'Labor',
                                    'id': reg['consecutivo'],
                                    'data': reg
                                }
                                st.rerun()

                        with col5:
                            if st.button("🗑️", key=f"del_labor_{reg['consecutivo']}", help="Eliminar"):
                                st.session_state.confirmando_eliminacion = {
                                    'tipo': 'Labor',
                                    'id': reg['consecutivo'],
                                    'data': reg
                                }
                                st.rerun()

                # Métricas
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Registros", len(registros_lab))
                with col2:
                    total_cantidad = sum([r['cantidad'] for r in registros_lab])
                    st.metric("Total Cantidad", f"{total_cantidad:,}")
                with col3:
                    total_valor_lab = sum([float(r['total']) for r in registros_lab])
                    st.metric("Valor Total", f"${total_valor_lab:,.0f}")
            else:
                st.info("No hay registros en el rango de fechas seleccionado")

        elif tipo_consulta == "Labores Administrativas":
            st.markdown("### 🏢 Registros de Labores Administrativas")

            cursor.execute("""
                SELECT
                    rh.id as consecutivo,
                    p.codigo,
                    p.nombre_completo,
                    COALESCE(o.numero_orden, 'Sin Orden') as numero_orden,
                    rh.orden_id,
                    rh.fecha,
                    rh.horas_trabajadas,
                    rh.tarifa_hora,
                    rh.total,
                    rh.observaciones,
                    rh.aprobado,
                    rh.fecha_creacion
                FROM registro_horas rh
                JOIN personal p ON rh.personal_id = p.id
                LEFT JOIN ordenes o ON rh.orden_id = o.id
                WHERE rh.fecha BETWEEN %s AND %s
                  AND rh.observaciones LIKE '[ADMIN]%%'
                ORDER BY rh.fecha_creacion DESC
                LIMIT 100
            """, (fecha_desde, fecha_hasta))

            registros_admin = cursor.fetchall()

            if registros_admin:
                # Mostrar cada registro con opción de editar
                for reg in registros_admin:
                    # Extraer tipo de labor administrativa de observaciones
                    tipo_labor_admin = reg['observaciones'].split(':')[0].replace('[ADMIN] ', '') if '[ADMIN]' in reg['observaciones'] else 'N/A'
                    descripcion = reg['observaciones'].split(':', 1)[1].strip() if ':' in reg['observaciones'] else reg['observaciones']
                    orden_texto = f" - Orden: {reg['numero_orden']}" if reg.get('numero_orden') and reg['numero_orden'] != 'Sin Orden' else ""

                    with st.expander(
                        f"#{reg['consecutivo']} - {reg['nombre_completo']} - {reg['fecha'].strftime('%d/%m/%Y')} - {tipo_labor_admin}{orden_texto} - ${reg['total']:,.0f} {'✅' if reg['aprobado'] else '⏳'}"
                    ):
                        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 0.5, 0.5])

                        with col1:
                            st.write(f"**Código:** {reg['codigo']}")
                            st.write(f"**Tipo Labor:** {tipo_labor_admin}")
                            if reg.get('numero_orden') and reg['numero_orden'] != 'Sin Orden':
                                st.write(f"**Orden:** {reg['numero_orden']}")

                        with col2:
                            st.write(f"**Fecha:** {reg['fecha'].strftime('%d/%m/%Y')}")
                            st.write(f"**Horas:** {reg['horas_trabajadas']}")
                            st.write(f"**Tarifa/h:** ${reg['tarifa_hora']:,.0f}")

                        with col3:
                            st.write(f"**Total:** ${reg['total']:,.0f}")
                            st.write(f"**Aprobado:** {'✅ Sí' if reg['aprobado'] else '⏳ Pendiente'}")
                            st.write(f"**Desc:** {descripcion[:50]}...")

                        with col4:
                            if st.button("✏️", key=f"edit_admin_{reg['consecutivo']}", help="Editar"):
                                st.session_state.editando_registro = {
                                    'tipo': 'Admin',
                                    'id': reg['consecutivo'],
                                    'data': reg
                                }
                                st.rerun()

                        with col5:
                            if st.button("🗑️", key=f"del_admin_{reg['consecutivo']}", help="Eliminar"):
                                st.session_state.confirmando_eliminacion = {
                                    'tipo': 'Admin',
                                    'id': reg['consecutivo'],
                                    'data': reg
                                }
                                st.rerun()

                # Métricas
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Registros", len(registros_admin))
                with col2:
                    total_horas_admin = sum([r['horas_trabajadas'] for r in registros_admin])
                    st.metric("Total Horas", f"{total_horas_admin:.2f}")
                with col3:
                    total_valor_admin = sum([float(r['total']) for r in registros_admin])
                    st.metric("Valor Total", f"${total_valor_admin:,.0f}")
            else:
                st.info("No hay registros administrativos en el rango de fechas seleccionado")

        elif tipo_consulta == "Subsidio Transporte":
            st.markdown("### 🚌 Subsidios de Transporte")
            st.info("💡 El subsidio se calcula automáticamente: >= 5 horas = Completo, < 5 horas = Medio")

            # Auto-calcular subsidios faltantes
            subsidios_creados = auto_calcular_subsidios_consulta(conn, fecha_desde, fecha_hasta)
            if subsidios_creados > 0:
                st.success(f"Se calcularon {subsidios_creados} subsidio(s) automáticamente")

            # Botón para recalcular manualmente
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("🔄 Recalcular Subsidios", type="secondary"):
                    stats = recalcular_subsidios_rango(conn, fecha_desde, fecha_hasta)
                    st.success(f"Recalculados: {stats['creados']} nuevos, {stats['actualizados']} actualizados")
                    st.rerun()

            cursor.execute("""
                SELECT
                    st.id as consecutivo,
                    p.codigo,
                    p.nombre_completo,
                    st.personal_id,
                    st.fecha,
                    st.horas_totales,
                    st.tipo_subsidio,
                    st.tarifa,
                    st.total,
                    st.origen,
                    st.aprobado,
                    st.observaciones,
                    st.fecha_creacion
                FROM subsidio_transporte st
                JOIN personal p ON st.personal_id = p.id
                WHERE st.fecha BETWEEN %s AND %s
                ORDER BY st.fecha DESC, p.nombre_completo
            """, (fecha_desde, fecha_hasta))

            subsidios_list = cursor.fetchall()

            if subsidios_list:
                # Mostrar cada registro con opción de editar
                for sub in subsidios_list:
                    tipo_texto = "Completo" if sub['tipo_subsidio'] == 'transporte_completo' else "Medio"
                    icono_tipo = "🚌" if sub['tipo_subsidio'] == 'transporte_completo' else "🚐"

                    with st.expander(
                        f"#{sub['consecutivo']} - {sub['nombre_completo']} - "
                        f"{sub['fecha'].strftime('%d/%m/%Y')} - {icono_tipo} {tipo_texto} - "
                        f"${sub['total']:,.0f} {'✅' if sub['aprobado'] else '⏳'}"
                    ):
                        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 0.5, 0.5])

                        with col1:
                            st.write(f"**Código:** {sub['codigo']}")
                            st.write(f"**Tipo:** {tipo_texto}")
                            st.write(f"**Origen:** {sub['origen'].capitalize() if sub['origen'] else 'N/A'}")

                        with col2:
                            st.write(f"**Fecha:** {sub['fecha'].strftime('%d/%m/%Y')}")
                            h = int(sub['horas_totales'])
                            m = int((sub['horas_totales'] - h) * 60)
                            st.write(f"**Horas Base:** {h}:{m:02d}")
                            st.write(f"**Tarifa:** ${sub['tarifa']:,.0f}")

                        with col3:
                            st.write(f"**Total:** ${sub['total']:,.0f}")
                            st.write(f"**Aprobado:** {'✅ Sí' if sub['aprobado'] else '⏳ Pendiente'}")
                            if sub.get('observaciones'):
                                st.write(f"**Obs:** {sub['observaciones'][:50]}...")

                        with col4:
                            if st.button("✏️", key=f"edit_subsidio_{sub['consecutivo']}", help="Editar"):
                                st.session_state.editando_registro = {
                                    'tipo': 'Subsidio',
                                    'id': sub['consecutivo'],
                                    'data': sub
                                }
                                st.rerun()

                        with col5:
                            if st.button("🗑️", key=f"del_subsidio_{sub['consecutivo']}", help="Eliminar"):
                                st.session_state.confirmando_eliminacion = {
                                    'tipo': 'Subsidio',
                                    'id': sub['consecutivo'],
                                    'data': sub
                                }
                                st.rerun()

                # Métricas
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Registros", len(subsidios_list))
                with col2:
                    completos = sum(1 for s in subsidios_list if s['tipo_subsidio'] == 'transporte_completo')
                    st.metric("Transporte Completo", completos)
                with col3:
                    medios = sum(1 for s in subsidios_list if s['tipo_subsidio'] == 'medio_transporte')
                    st.metric("Medio Transporte", medios)
                with col4:
                    total_valor_sub = sum([float(s['total']) for s in subsidios_list])
                    st.metric("Valor Total", f"${total_valor_sub:,.0f}")
            else:
                st.info("No hay subsidios en el rango de fechas seleccionado")

        # =====================================================
        # FORMULARIO DE EDICIÓN - Simplificado
        # =====================================================
        if st.session_state.editando_registro:
            st.divider()
            st.markdown("### ✏️ Editar Registro")

            reg_edit = st.session_state.editando_registro
            tipo_edit = reg_edit['tipo']
            id_edit = reg_edit['id']
            data_edit = reg_edit['data']

            st.info(f"Editando registro #{id_edit} - Tipo: {tipo_edit}")

            # Botón para cancelar fuera del formulario
            if st.button("❌ Cancelar Edición", key="btn_cancelar_top"):
                st.session_state.editando_registro = None
                st.rerun()

            # Determinar qué campos mostrar según el tipo
            es_horas = (tipo_edit == "Horas" or tipo_edit == "Admin")
            es_subsidio = (tipo_edit == "Subsidio")

            # Obtener órdenes disponibles para el selector (no aplica para subsidios)
            if not es_subsidio:
                cursor_ordenes = conn.cursor(dictionary=True)
                cursor_ordenes.execute("""
                    SELECT id, numero_orden
                    FROM ordenes
                    WHERE estado = 'activa'
                    ORDER BY numero_orden
                """)
                ordenes_disponibles = cursor_ordenes.fetchall()
                cursor_ordenes.close()

                # Crear diccionario de órdenes: {id: numero_orden}
                ordenes_dict = {None: "Sin orden asignada"}
                ordenes_dict.update({o['id']: o['numero_orden'] for o in ordenes_disponibles})

                # Obtener orden_id actual del registro
                orden_id_actual = data_edit.get('orden_id', None)

            # Preparar valores por defecto seguros
            if es_subsidio:
                horas_decimal = data_edit.get('horas_totales', 0)
                horas_enteras = int(horas_decimal)
                minutos = int((horas_decimal - horas_enteras) * 60)
                valor_horas_default = f"{horas_enteras}:{minutos:02d}"
                valor_tarifa_default = float(data_edit.get('tarifa', 0))
            elif es_horas:
                horas_decimal = data_edit.get('horas_trabajadas', data_edit.get('cantidad', 0))
                horas_enteras = int(horas_decimal)
                minutos = int((horas_decimal - horas_enteras) * 60)
                valor_horas_default = f"{horas_enteras}:{minutos:02d}"
                valor_tarifa_default = float(data_edit.get('tarifa_hora', data_edit.get('tarifa', 0)))
            else:
                valor_cantidad_default = int(data_edit.get('cantidad', 1))
                valor_tarifa_default = float(data_edit.get('tarifa_unitaria', data_edit.get('tarifa', 0)))

            # FORMULARIO ÚNICO
            if es_subsidio:
                # Formulario especial para subsidios
                with st.form(key="form_edicion_subsidio", clear_on_submit=False):
                    col1, col2 = st.columns(2)

                    with col1:
                        fecha_edit = st.date_input(
                            "Fecha *",
                            value=data_edit['fecha']
                        )

                    with col2:
                        tipo_subsidio_edit = st.selectbox(
                            "Tipo de Subsidio *",
                            ['transporte_completo', 'medio_transporte'],
                            index=0 if data_edit.get('tipo_subsidio') == 'transporte_completo' else 1,
                            format_func=lambda x: "Transporte Completo (>= 5h)" if x == 'transporte_completo' else "Medio Transporte (< 5h)"
                        )

                    col1, col2 = st.columns(2)

                    with col1:
                        # Mostrar horas base (solo lectura)
                        st.text_input("Horas Base (calculado)", value=valor_horas_default, disabled=True)

                    with col2:
                        tarifa_edit = st.number_input(
                            "Tarifa *",
                            value=valor_tarifa_default,
                            min_value=0.0,
                            help="Tarifa del subsidio"
                        )

                    col1, col2 = st.columns(2)

                    with col1:
                        st.metric("Total a Pagar", f"${tarifa_edit:,.0f}")

                    with col2:
                        aprobado_edit = st.checkbox(
                            "Aprobado",
                            value=bool(data_edit.get('aprobado', False))
                        )

                    observaciones_edit = st.text_area(
                        "Observaciones",
                        value=data_edit.get('observaciones', '') or '',
                        height=100
                    )

                    # Botones del formulario
                    col1, col2 = st.columns(2)
                    with col1:
                        submitted = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)
                    with col2:
                        cancelado = st.form_submit_button("❌ Cancelar", use_container_width=True)
            else:
                # Formulario para Horas, Admin y Labor
                with st.form(key="form_edicion_universal", clear_on_submit=False):
                    col1, col2 = st.columns(2)

                    with col1:
                        fecha_edit = st.date_input(
                            "Fecha *",
                            value=data_edit['fecha']
                        )

                    with col2:
                        # Selector de orden
                        orden_seleccionada = st.selectbox(
                            "Número de Orden",
                            options=list(ordenes_dict.keys()),
                            format_func=lambda x: ordenes_dict[x],
                            index=list(ordenes_dict.keys()).index(orden_id_actual) if orden_id_actual in ordenes_dict.keys() else 0,
                            help="Selecciona una orden o deja 'Sin orden asignada'"
                        )

                    col1, col2 = st.columns(2)

                    with col1:
                        if es_horas:
                            horas_edit_input = st.text_input(
                                "Horas (HH:MM) *",
                                value=valor_horas_default,
                                help="Formato HH:MM - Ejemplo: 2:45"
                            )
                        else:
                            cantidad_edit = st.number_input(
                                "Cantidad *",
                                value=valor_cantidad_default,
                                min_value=1
                            )

                    col1, col2 = st.columns(2)
                    with col1:
                        tarifa_edit = st.number_input(
                            "Tarifa *",
                            value=valor_tarifa_default,
                            min_value=0.0,
                            help="Tarifa por hora" if es_horas else "Tarifa unitaria"
                        )

                    with col2:
                        aprobado_edit = st.checkbox(
                            "Aprobado",
                            value=bool(data_edit.get('aprobado', False))
                        )

                    observaciones_edit = st.text_area(
                        "Observaciones",
                        value=data_edit.get('observaciones', '') or '',
                        height=100
                    )

                    # Botones del formulario
                    col1, col2 = st.columns(2)
                    with col1:
                        submitted = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)
                    with col2:
                        cancelado = st.form_submit_button("❌ Cancelar", use_container_width=True)

            # Procesar fuera del formulario
            if cancelado:
                st.session_state.editando_registro = None
                st.rerun()

            if submitted:
                try:
                    cursor = conn.cursor()

                    if es_subsidio:
                        # Procesar edición de subsidio
                        cursor.execute("""
                            UPDATE subsidio_transporte
                            SET tipo_subsidio = %s,
                                tarifa = %s,
                                origen = 'manual',
                                aprobado = %s,
                                observaciones = %s,
                                fecha_modificacion = CURRENT_TIMESTAMP
                            WHERE id = %s AND liquidado = FALSE
                        """, (
                            tipo_subsidio_edit,
                            tarifa_edit,
                            aprobado_edit,
                            observaciones_edit,
                            id_edit
                        ))
                        conn.commit()
                        st.success("✅ Subsidio actualizado exitosamente")
                        st.session_state.editando_registro = None
                        st.rerun()
                    elif es_horas:
                        # Procesar edición de horas
                        horas_edit, error_edit = convertir_horas_a_decimal(horas_edit_input)

                        if error_edit:
                            st.error(f"Error en formato de horas: {error_edit}")
                        elif horas_edit and horas_edit > 0:
                            # NO incluir 'total' - es una columna generada automáticamente
                            cursor.execute("""
                                UPDATE registro_horas
                                SET fecha = %s, horas_trabajadas = %s, tarifa_hora = %s,
                                    observaciones = %s, aprobado = %s, orden_id = %s
                                WHERE id = %s
                            """, (fecha_edit, horas_edit, tarifa_edit, observaciones_edit, aprobado_edit, orden_seleccionada, id_edit))
                            conn.commit()
                            st.success("✅ Registro de horas actualizado exitosamente")
                            st.session_state.editando_registro = None
                            st.rerun()
                        else:
                            st.error("Las horas deben ser mayor a 0")
                    else:
                        # Procesar edición de labores
                        if cantidad_edit > 0:
                            # NO incluir 'total' - es una columna generada automáticamente
                            cursor.execute("""
                                UPDATE registro_labores
                                SET fecha = %s, cantidad = %s, tarifa_unitaria = %s,
                                    observaciones = %s, aprobado = %s, orden_id = %s
                                WHERE id = %s
                            """, (fecha_edit, cantidad_edit, tarifa_edit, observaciones_edit, aprobado_edit, orden_seleccionada, id_edit))
                            conn.commit()
                            st.success("✅ Registro de labor actualizado exitosamente")
                            st.session_state.editando_registro = None
                            st.rerun()
                        else:
                            st.error("La cantidad debe ser mayor a 0")

                except Exception as e:
                    st.error(f"Error al actualizar: {e}")
                    conn.rollback()

        # =====================================================
        # CONFIRMACIÓN DE ELIMINACIÓN
        # =====================================================
        if st.session_state.confirmando_eliminacion:
            st.divider()
            st.markdown("### 🗑️ Confirmar Eliminación")

            reg_del = st.session_state.confirmando_eliminacion
            tipo_del = reg_del['tipo']
            id_del = reg_del['id']
            data_del = reg_del['data']

            st.warning(f"⚠️ ¿Está seguro de eliminar el registro **#{id_del}** de tipo **{tipo_del}**?")
            st.write(f"**Nombre:** {data_del.get('nombre_completo', 'N/A')}")
            if hasattr(data_del.get('fecha', ''), 'strftime'):
                st.write(f"**Fecha:** {data_del['fecha'].strftime('%d/%m/%Y')}")

            # Botón para cancelar fuera del formulario
            if st.button("❌ Cancelar Eliminación", key="btn_cancelar_elim_top"):
                st.session_state.confirmando_eliminacion = None
                st.rerun()

            col_del1, col_del2 = st.columns(2)
            with col_del1:
                if st.button("🗑️ Sí, Eliminar", type="primary", key="btn_confirmar_eliminar", use_container_width=True):
                    try:
                        cursor_del = conn.cursor(dictionary=True)

                        if tipo_del in ('Horas', 'Admin'):
                            # Obtener info antes de eliminar para recalcular subsidio
                            cursor_del.execute("SELECT personal_id, fecha FROM registro_horas WHERE id = %s", (id_del,))
                            info_reg = cursor_del.fetchone()
                            cursor_del.execute("DELETE FROM registro_horas WHERE id = %s", (id_del,))
                            conn.commit()
                            # Recalcular subsidio de transporte
                            if info_reg:
                                calculo = calcular_subsidio_transporte(conn, info_reg['personal_id'], info_reg['fecha'])
                                if calculo['horas_totales'] > 0:
                                    crear_o_actualizar_subsidio(conn, info_reg['personal_id'], info_reg['fecha'], 'recalculado')
                                elif calculo['ya_existe']:
                                    cursor_del.execute("DELETE FROM subsidio_transporte WHERE id = %s AND liquidado = FALSE", (calculo['subsidio_id'],))
                                    conn.commit()

                        elif tipo_del == 'Labor':
                            cursor_del.execute("DELETE FROM registro_labores WHERE id = %s", (id_del,))
                            conn.commit()

                        elif tipo_del == 'Subsidio':
                            cursor_del.execute("DELETE FROM subsidio_transporte WHERE id = %s AND liquidado = FALSE", (id_del,))
                            conn.commit()

                        cursor_del.close()
                        st.session_state.confirmando_eliminacion = None
                        st.success("✅ Registro eliminado exitosamente")
                        st.rerun()

                    except Exception as e:
                        st.error(f"Error al eliminar: {e}")
                        conn.rollback()

            with col_del2:
                if st.button("❌ Cancelar", key="btn_cancelar_eliminar", use_container_width=True):
                    st.session_state.confirmando_eliminacion = None
                    st.rerun()

    except Exception as e:
        st.error(f"Error: {e}")

# =====================================================
# TAB 5: PLANILLA CHECK
# =====================================================
with tab5:
    st.subheader("Planilla Check - Resumen por Personal")
    st.info("📋 Consulta el resumen totalizado de labores por tipo y fecha para un personal específico")

    try:
        cursor = conn.cursor(dictionary=True)

        # Filtros
        st.markdown("### Filtros")

        # Cargar personal activo para selector
        cursor.execute("""
            SELECT codigo, nombre_completo FROM personal
            WHERE activo = TRUE
            ORDER BY codigo
        """)
        personal_lista = cursor.fetchall()
        personal_options_plan = {"TODOS": "TODOS"}
        for p_item in personal_lista:
            personal_options_plan[f"{p_item['codigo']} - {p_item['nombre_completo']}"] = p_item['codigo']

        col1, col2, col3 = st.columns([1.5, 1.5, 1.5])

        with col1:
            personal_sel_plan = st.selectbox(
                "Personal",
                list(personal_options_plan.keys()),
                key="codigo_planilla_check"
            )
            codigo_planilla = personal_options_plan[personal_sel_plan]

        with col2:
            fecha_desde_plan = st.date_input(
                "Fecha Desde",
                value=date.today().replace(day=1),
                key="fecha_desde_planilla"
            )

        with col3:
            fecha_hasta_plan = st.date_input(
                "Fecha Hasta",
                value=date.today(),
                key="fecha_hasta_planilla"
            )

        # Buscar personal
        personal_plan = None
        es_todos_plan = (codigo_planilla == "TODOS")
        if es_todos_plan:
            personal_plan = {"id": None, "codigo": "TODOS", "nombre_completo": "TODOS", "identificacion": "-", "tipo_personal": "-"}
            st.success("**TODOS** - Mostrando resumen de todo el personal")
        elif codigo_planilla and len(codigo_planilla) == 4:
            cursor.execute("""
                SELECT id, codigo, nombre_completo, identificacion, tipo_personal
                FROM personal
                WHERE codigo = %s AND activo = TRUE
            """, (codigo_planilla,))
            personal_plan = cursor.fetchone()

            if personal_plan:
                st.success(f"**{personal_plan['codigo']}** - {personal_plan['nombre_completo']} | Cédula: {personal_plan['identificacion']}")
            else:
                st.error("Personal no encontrado o inactivo")

        st.divider()

        if personal_plan and es_todos_plan:
            # =====================================================
            # VISTA TODOS: Resumen de todo el personal
            # =====================================================
            st.markdown("### Resumen de TODO el Personal")
            st.markdown(f"**Periodo:** {fecha_desde_plan.strftime('%d/%m/%Y')} - {fecha_hasta_plan.strftime('%d/%m/%Y')}")

            # Cachear resultados por periodo para evitar 3 queries pesadas en cada rerun
            _plan_cache_key = f"_plan_todos_{fecha_desde_plan}_{fecha_hasta_plan}"
            if _plan_cache_key not in st.session_state:
                cursor.execute("""
                    SELECT p.codigo, p.nombre_completo,
                        COALESCE(SUM(rh.total), 0) as valor_horas
                    FROM personal p
                    LEFT JOIN registro_horas rh ON rh.personal_id = p.id
                        AND rh.fecha BETWEEN %s AND %s
                    WHERE p.activo = TRUE
                    GROUP BY p.id, p.codigo, p.nombre_completo
                """, (fecha_desde_plan, fecha_hasta_plan))
                totales_horas = {r['codigo']: {'nombre': r['nombre_completo'], 'horas': float(r['valor_horas'])} for r in cursor.fetchall()}

                cursor.execute("""
                    SELECT p.codigo,
                        COALESCE(SUM(rl.total), 0) as valor_labores
                    FROM personal p
                    LEFT JOIN registro_labores rl ON rl.personal_id = p.id
                        AND rl.fecha BETWEEN %s AND %s
                    WHERE p.activo = TRUE
                    GROUP BY p.id, p.codigo
                """, (fecha_desde_plan, fecha_hasta_plan))
                totales_labores = {r['codigo']: float(r['valor_labores']) for r in cursor.fetchall()}

                cursor.execute("""
                    SELECT p.codigo,
                        COALESCE(SUM(sub_t.total), 0) as valor_subsidio
                    FROM personal p
                    LEFT JOIN subsidio_transporte sub_t ON sub_t.personal_id = p.id
                        AND sub_t.fecha BETWEEN %s AND %s
                    WHERE p.activo = TRUE
                    GROUP BY p.id, p.codigo
                """, (fecha_desde_plan, fecha_hasta_plan))
                totales_subsidios = {r['codigo']: float(r['valor_subsidio']) for r in cursor.fetchall()}

                st.session_state[_plan_cache_key] = (totales_horas, totales_labores, totales_subsidios)
            else:
                totales_horas, totales_labores, totales_subsidios = st.session_state[_plan_cache_key]

            # Combinar resultados
            resumen_personal = []
            for codigo, datos in totales_horas.items():
                valor_horas = datos['horas']
                valor_labores = totales_labores.get(codigo, 0)
                valor_subsidios = totales_subsidios.get(codigo, 0)
                valor_total_p = valor_horas + valor_labores + valor_subsidios
                if valor_total_p > 0:
                    resumen_personal.append({
                        'codigo': codigo,
                        'nombre': datos['nombre'],
                        'valor_horas': valor_horas,
                        'valor_labores': valor_labores,
                        'valor_subsidios': valor_subsidios,
                        'valor_total': valor_total_p
                    })

            if resumen_personal:
                resumen_personal.sort(key=lambda x: x['codigo'])
                gran_total = sum(r['valor_total'] for r in resumen_personal)

                # Metricas generales
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Personal con Registros", len(resumen_personal))
                with col2:
                    st.metric("Valor Total General", f"${gran_total:,.0f}")

                st.divider()

                # Tabla de resumen
                hcol1, hcol2, hcol3, hcol4, hcol5, hcol6 = st.columns([0.8, 2.5, 1.2, 1.2, 1.2, 1.5])
                hcol1.write("**Codigo**")
                hcol2.write("**Nombre**")
                hcol3.write("**Horas**")
                hcol4.write("**Labores**")
                hcol5.write("**Subsidios**")
                hcol6.write("**Total**")
                st.markdown("---")

                for rp in resumen_personal:
                    c1, c2, c3, c4, c5, c6 = st.columns([0.8, 2.5, 1.2, 1.2, 1.2, 1.5])
                    c1.write(rp['codigo'])
                    c2.write(rp['nombre'])
                    c3.write(f"${rp['valor_horas']:,.0f}")
                    c4.write(f"${rp['valor_labores']:,.0f}")
                    c5.write(f"${rp['valor_subsidios']:,.0f}")
                    c6.write(f"${rp['valor_total']:,.0f}")

                st.markdown("---")
                st.markdown(f"### **TOTAL GENERAL: ${gran_total:,.0f}**")

                # Exportar
                st.divider()
                df_todos_export = pd.DataFrame(resumen_personal)
                csv_todos_plan = df_todos_export.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Descargar Resumen CSV",
                    data=csv_todos_plan,
                    file_name=f"planilla_TODOS_{fecha_desde_plan.strftime('%Y%m%d')}_{fecha_hasta_plan.strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No hay registros para ningun personal en el periodo seleccionado")

        if personal_plan and not es_todos_plan:
            # =====================================================
            # RESUMEN GENERAL
            # =====================================================
            st.markdown(f"### Resumen de {personal_plan['nombre_completo']}")
            st.markdown(f"**Período:** {fecha_desde_plan.strftime('%d/%m/%Y')} - {fecha_hasta_plan.strftime('%d/%m/%Y')}")

            # Consultar todas las labores del personal en el período
            # 1. Horas de alistamiento (con orden)
            cursor.execute("""
                SELECT
                    rh.fecha,
                    'Alistamiento' as categoria,
                    CASE
                        WHEN rh.tipo_trabajo = 'alistamiento_sobres' THEN 'Alistamiento Sobres'
                        ELSE 'Alistamiento Paquetes'
                    END as tipo_labor,
                    SUM(rh.horas_trabajadas) as cantidad,
                    'horas' as unidad,
                    SUM(rh.total) as valor_total,
                    COUNT(*) as registros
                FROM registro_horas rh
                WHERE rh.personal_id = %s
                  AND rh.fecha BETWEEN %s AND %s
                  AND rh.orden_id IS NOT NULL
                GROUP BY rh.fecha, rh.tipo_trabajo
            """, (personal_plan['id'], fecha_desde_plan, fecha_hasta_plan))
            horas_alistamiento = cursor.fetchall()

            # 2. Labores administrativas (sin orden)
            cursor.execute("""
                SELECT
                    rh.fecha,
                    'Administrativa' as categoria,
                    CASE
                        WHEN rh.observaciones LIKE '[ADMIN] cortar_hojas%' THEN 'Cortar Hojas'
                        WHEN rh.observaciones LIKE '[ADMIN] organizacion_zona%' THEN 'Organización Zona'
                        WHEN rh.observaciones LIKE '[ADMIN] limpieza_area%' THEN 'Limpieza Área'
                        WHEN rh.observaciones LIKE '[ADMIN] mantenimiento_equipos%' THEN 'Mantenimiento Equipos'
                        WHEN rh.observaciones LIKE '[ADMIN] archivo_documentos%' THEN 'Archivo Documentos'
                        WHEN rh.observaciones LIKE '[ADMIN] cajoneras%' THEN 'Cajoneras'
                        ELSE 'Otros Administrativos'
                    END as tipo_labor,
                    SUM(rh.horas_trabajadas) as cantidad,
                    'horas' as unidad,
                    SUM(rh.total) as valor_total,
                    COUNT(*) as registros
                FROM registro_horas rh
                WHERE rh.personal_id = %s
                  AND rh.fecha BETWEEN %s AND %s
                  AND rh.orden_id IS NULL
                GROUP BY rh.fecha, tipo_labor
            """, (personal_plan['id'], fecha_desde_plan, fecha_hasta_plan))
            horas_admin = cursor.fetchall()

            # 3. Labores (pegado, transporte)
            cursor.execute("""
                SELECT
                    rl.fecha,
                    'Labor' as categoria,
                    CASE
                        WHEN rl.tipo_labor = 'pegado_guia' THEN 'Pegado de Guías'
                        WHEN rl.tipo_labor = 'transporte_completo' THEN 'Transporte Completo'
                        WHEN rl.tipo_labor = 'medio_transporte' THEN 'Medio Transporte'
                        ELSE rl.tipo_labor
                    END as tipo_labor,
                    SUM(rl.cantidad) as cantidad,
                    'unidades' as unidad,
                    SUM(rl.total) as valor_total,
                    COUNT(*) as registros
                FROM registro_labores rl
                WHERE rl.personal_id = %s
                  AND rl.fecha BETWEEN %s AND %s
                GROUP BY rl.fecha, rl.tipo_labor
            """, (personal_plan['id'], fecha_desde_plan, fecha_hasta_plan))
            labores = cursor.fetchall()

            # 4. Subsidios de transporte
            cursor.execute("""
                SELECT
                    st.fecha,
                    'Subsidio' as categoria,
                    CASE
                        WHEN st.tipo_subsidio = 'transporte_completo' THEN 'Subsidio Completo'
                        ELSE 'Subsidio Medio'
                    END as tipo_labor,
                    st.horas_totales as cantidad,
                    'horas base' as unidad,
                    st.total as valor_total,
                    1 as registros
                FROM subsidio_transporte st
                WHERE st.personal_id = %s
                  AND st.fecha BETWEEN %s AND %s
            """, (personal_plan['id'], fecha_desde_plan, fecha_hasta_plan))
            subsidios = cursor.fetchall()

            # Combinar todos los registros
            todos_registros = list(horas_alistamiento) + list(horas_admin) + list(labores) + list(subsidios)

            if todos_registros:
                # Calcular totales generales
                total_valor_general = sum([float(r['valor_total']) for r in todos_registros])
                total_registros_general = sum([r['registros'] for r in todos_registros])
                dias_trabajados = len(set([r['fecha'] for r in todos_registros]))

                # Métricas generales
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Días Trabajados", dias_trabajados)
                with col2:
                    st.metric("Total Registros", total_registros_general)
                with col3:
                    total_horas = sum([float(r['cantidad']) for r in todos_registros if r['unidad'] == 'horas'])
                    h = int(total_horas)
                    m = int((total_horas - h) * 60)
                    st.metric("Total Horas", f"{h}:{m:02d}")
                with col4:
                    st.metric("Valor Total", f"${total_valor_general:,.0f}")

                st.divider()

                # =====================================================
                # DETALLE POR FECHA
                # =====================================================
                st.markdown("### Detalle por Fecha")

                # Agrupar por fecha
                from collections import defaultdict
                registros_por_fecha = defaultdict(list)
                for reg in todos_registros:
                    registros_por_fecha[reg['fecha']].append(reg)

                # Mostrar por fecha (más reciente primero)
                for fecha in sorted(registros_por_fecha.keys(), reverse=True):
                    regs_dia = registros_por_fecha[fecha]
                    total_dia = sum([float(r['valor_total']) for r in regs_dia])

                    with st.expander(f"📅 **{fecha.strftime('%A %d/%m/%Y')}** - ${total_dia:,.0f}", expanded=False):
                        # Encabezados
                        hcol1, hcol2, hcol3, hcol4, hcol5 = st.columns([1.5, 2, 1.2, 1.2, 1.2])
                        hcol1.write("**Categoría**")
                        hcol2.write("**Tipo de Labor**")
                        hcol3.write("**Cantidad**")
                        hcol4.write("**Registros**")
                        hcol5.write("**Valor**")

                        st.markdown("---")

                        for reg in regs_dia:
                            col1, col2, col3, col4, col5 = st.columns([1.5, 2, 1.2, 1.2, 1.2])

                            # Icono según categoría
                            icono = {
                                'Alistamiento': '⏰',
                                'Administrativa': '🏢',
                                'Labor': '🔧',
                                'Subsidio': '🚌'
                            }.get(reg['categoria'], '📋')

                            col1.write(f"{icono} {reg['categoria']}")
                            col2.write(reg['tipo_labor'])

                            if reg['unidad'] == 'horas' or reg['unidad'] == 'horas base':
                                h = int(reg['cantidad'])
                                m = int((float(reg['cantidad']) - h) * 60)
                                col3.write(f"{h}:{m:02d} h")
                            else:
                                col3.write(f"{int(reg['cantidad'])} und")

                            col4.write(f"{reg['registros']}")
                            col5.write(f"${float(reg['valor_total']):,.0f}")

                        st.markdown("---")
                        st.write(f"**Total del día: ${total_dia:,.0f}**")

                st.divider()

                # =====================================================
                # RESUMEN POR TIPO DE LABOR
                # =====================================================
                st.markdown("### Resumen por Tipo de Labor")

                # Agrupar por tipo de labor
                resumen_por_tipo = defaultdict(lambda: {'cantidad': 0, 'valor': 0, 'registros': 0, 'unidad': ''})
                for reg in todos_registros:
                    key = f"{reg['categoria']} - {reg['tipo_labor']}"
                    resumen_por_tipo[key]['cantidad'] += float(reg['cantidad'])
                    resumen_por_tipo[key]['valor'] += float(reg['valor_total'])
                    resumen_por_tipo[key]['registros'] += reg['registros']
                    resumen_por_tipo[key]['unidad'] = reg['unidad']

                # Encabezados
                hcol1, hcol2, hcol3, hcol4 = st.columns([2.5, 1.2, 1, 1.5])
                hcol1.write("**Tipo de Labor**")
                hcol2.write("**Cantidad Total**")
                hcol3.write("**Registros**")
                hcol4.write("**Valor Total**")

                st.markdown("---")

                for tipo, datos in sorted(resumen_por_tipo.items()):
                    col1, col2, col3, col4 = st.columns([2.5, 1.2, 1, 1.5])
                    col1.write(tipo)

                    if datos['unidad'] == 'horas' or datos['unidad'] == 'horas base':
                        h = int(datos['cantidad'])
                        m = int((datos['cantidad'] - h) * 60)
                        col2.write(f"{h}:{m:02d} h")
                    else:
                        col2.write(f"{int(datos['cantidad'])} und")

                    col3.write(f"{datos['registros']}")
                    col4.write(f"${datos['valor']:,.0f}")

                st.markdown("---")
                st.markdown(f"### **TOTAL GENERAL: ${total_valor_general:,.0f}**")

                # =====================================================
                # EXPORTAR
                # =====================================================
                st.divider()

                # Preparar datos para exportar
                datos_export = []
                for reg in todos_registros:
                    datos_export.append({
                        'Fecha': reg['fecha'].strftime('%Y-%m-%d'),
                        'Categoría': reg['categoria'],
                        'Tipo Labor': reg['tipo_labor'],
                        'Cantidad': reg['cantidad'],
                        'Unidad': reg['unidad'],
                        'Valor Total': float(reg['valor_total']),
                        'Registros': reg['registros']
                    })

                df_export = pd.DataFrame(datos_export)
                csv = df_export.to_csv(index=False).encode('utf-8')

                st.download_button(
                    label="📥 Descargar Planilla CSV",
                    data=csv,
                    file_name=f"planilla_{personal_plan['codigo']}_{fecha_desde_plan.strftime('%Y%m%d')}_{fecha_hasta_plan.strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )

                # =====================================================
                # EDITAR REGISTROS DE CONDUCTOR (TRANSPORTE)
                # =====================================================
                st.divider()
                st.markdown("### ✏️ Editar Registros de Transporte")

                cursor.execute("""
                    SELECT
                        rl.id,
                        rl.fecha,
                        rl.tipo_labor,
                        rl.cantidad,
                        rl.tarifa_unitaria,
                        rl.total,
                        rl.observaciones,
                        rl.orden_id,
                        COALESCE(o.numero_orden, 'Sin orden') as numero_orden,
                        COALESCE(c.nombre_empresa, '') as cliente
                    FROM registro_labores rl
                    LEFT JOIN ordenes o ON rl.orden_id = o.id
                    LEFT JOIN clientes c ON o.cliente_id = c.id
                    WHERE rl.personal_id = %s
                      AND rl.fecha BETWEEN %s AND %s
                      AND rl.tipo_labor = 'transporte_completo'
                    ORDER BY rl.fecha DESC
                """, (personal_plan['id'], fecha_desde_plan, fecha_hasta_plan))
                registros_transporte = cursor.fetchall()

                if registros_transporte:
                    st.caption(f"{len(registros_transporte)} registro(s) de transporte encontrados")

                    # Encabezados
                    hc1, hc2, hc3, hc4, hc5 = st.columns([1.5, 3, 1.5, 1, 0.5])
                    hc1.write("**Fecha**")
                    hc2.write("**Orden**")
                    hc3.write("**Tarifa**")
                    hc4.write("**ID**")
                    hc5.write("")

                    for reg_t in registros_transporte:
                        col1, col2, col3, col4, col5 = st.columns([1.5, 3, 1.5, 1, 0.5])
                        with col1:
                            st.write(reg_t['fecha'].strftime('%d/%m/%Y'))
                        with col2:
                            st.write(f"{reg_t['numero_orden']} - {reg_t['cliente']}")
                        with col3:
                            st.write(f"${float(reg_t['tarifa_unitaria']):,.0f}")
                        with col4:
                            st.write(f"#{reg_t['id']}")
                        with col5:
                            if st.button("✏️", key=f"edit_tp_{reg_t['id']}"):
                                st.session_state.editando_planilla = {
                                    'id': reg_t['id'],
                                    'data': dict(reg_t)
                                }
                                st.rerun()
                else:
                    st.caption("No hay registros de transporte en este período")

                # --- Formulario de edición ---
                if st.session_state.editando_planilla:
                    reg_ep = st.session_state.editando_planilla['data']

                    st.markdown("---")
                    st.markdown(f"#### ✏️ Editando registro #{reg_ep['id']}")

                    if st.button("❌ Cancelar edición", key="cancel_edit_plan"):
                        st.session_state.editando_planilla = None
                        st.rerun()

                    # Obtener órdenes para el selector
                    cursor.execute("""
                        SELECT o.id, o.numero_orden, c.nombre_empresa as cliente
                        FROM ordenes o
                        JOIN clientes c ON o.cliente_id = c.id
                        WHERE o.estado = 'activa'
                        ORDER BY o.numero_orden DESC
                        LIMIT 100
                    """)
                    ordenes_edit_plan = cursor.fetchall()
                    ordenes_dict_plan = {
                        f"{o['numero_orden']} - {o['cliente']}": o['id']
                        for o in ordenes_edit_plan
                    }
                    opciones_orden_plan = list(ordenes_dict_plan.keys())

                    # Buscar índice de la orden actual
                    orden_actual_label = f"{reg_ep['numero_orden']} - {reg_ep['cliente']}"
                    default_idx_plan = opciones_orden_plan.index(orden_actual_label) if orden_actual_label in opciones_orden_plan else 0

                    with st.form(key="form_edit_planilla"):
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            nueva_fecha_plan = st.date_input(
                                "Fecha",
                                value=reg_ep['fecha']
                            )

                        with col2:
                            nueva_orden_plan = st.selectbox(
                                "Orden",
                                opciones_orden_plan,
                                index=default_idx_plan
                            )

                        with col3:
                            nueva_tarifa_plan = st.number_input(
                                "Tarifa ($)",
                                value=int(reg_ep['tarifa_unitaria']),
                                min_value=0,
                                step=1000
                            )

                        col1, col2 = st.columns(2)
                        with col1:
                            save_plan = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)
                        with col2:
                            cancel_plan = st.form_submit_button("❌ Cancelar", use_container_width=True)

                    if cancel_plan:
                        st.session_state.editando_planilla = None
                        st.rerun()

                    if save_plan:
                        try:
                            nuevo_orden_id_plan = ordenes_dict_plan[nueva_orden_plan]
                            cursor_ep = conn.cursor()
                            cursor_ep.execute("""
                                UPDATE registro_labores
                                SET fecha = %s, orden_id = %s, tarifa_unitaria = %s
                                WHERE id = %s
                            """, (nueva_fecha_plan, nuevo_orden_id_plan, nueva_tarifa_plan, reg_ep['id']))
                            conn.commit()
                            cursor_ep.close()
                            st.session_state.editando_planilla = None
                            st.success("✅ Registro actualizado exitosamente")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar: {e}")
                            conn.rollback()

            else:
                st.info(f"No hay registros para {personal_plan['nombre_completo']} en el período seleccionado")

                # Mostrar fechas disponibles
                cursor.execute("""
                    SELECT DISTINCT fecha, COUNT(*) as total
                    FROM (
                        SELECT fecha FROM registro_horas WHERE personal_id = %s
                        UNION ALL
                        SELECT fecha FROM registro_labores WHERE personal_id = %s
                    ) as fechas
                    GROUP BY fecha
                    ORDER BY fecha DESC
                    LIMIT 10
                """, (personal_plan['id'], personal_plan['id']))
                fechas_disp = cursor.fetchall()

                if fechas_disp:
                    st.markdown("#### Fechas con registros disponibles:")
                    for f in fechas_disp:
                        st.write(f"- {f['fecha'].strftime('%d/%m/%Y')}: {f['total']} registro(s)")

        if not personal_plan:
            st.info("Seleccione el personal para ver su planilla")

    except Exception as e:
        st.error(f"Error: {e}")
        import traceback
        st.code(traceback.format_exc())

if 'cursor' in locals():
    cursor.close()
