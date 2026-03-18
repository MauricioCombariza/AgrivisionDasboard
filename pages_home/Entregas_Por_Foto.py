import streamlit as st
import sys
import os
from PIL import Image
import io

# ── Paths ──────────────────────────────────────────────────────────────────────
_CURRENT = os.path.dirname(os.path.abspath(__file__))
_ROOT    = os.path.abspath(os.path.join(_CURRENT, ".."))
_READER  = "/home/mauro/personalProjects/agrivision/barcode_qr_reader"

for _p in [_ROOT, _READER]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from utils.db_connection import conectar_bd
from reader.decoder import decode
from reader.deduplicator import deduplicate

# ──────────────────────────────────────────────────────────────────────────────

st.title("📦 Entregas por Foto")
st.caption("Fotografía el código de barras o QR del paquete para identificarlo y guardar la evidencia.")

uploaded = st.file_uploader(
    "Sube la foto del paquete",
    type=["jpg", "jpeg", "png", "webp"],
    key="entregas_foto_upload",
)

if not uploaded:
    st.stop()

# Leer imagen una sola vez
img_bytes = uploaded.read()
pil_img   = Image.open(io.BytesIO(img_bytes)).convert("RGB")

col_img, col_info = st.columns([1, 1], gap="large")

with col_img:
    st.image(pil_img, caption=uploaded.name, use_container_width=True)

with col_info:
    with st.spinner("Leyendo código…"):
        raw_detections = decode(pil_img)
        deduped        = deduplicate(raw_detections)

    if not deduped:
        st.warning("No se detectó ningún código de barras ni QR en la imagen.")
        st.stop()

    # Tomar el primer serial (mayor confianza)
    serial = deduped[0].value
    code_type = deduped[0].primary_type

    st.success(f"Código detectado")
    st.markdown(f"**Serial:** `{serial}`")
    st.markdown(f"**Tipo:** {code_type}")

    if len(deduped) > 1:
        with st.expander(f"Otros códigos detectados ({len(deduped) - 1})"):
            for d in deduped[1:]:
                st.code(d.value)

    st.divider()

    # ── Búsqueda en BD ────────────────────────────────────────────────────────
    conn = conectar_bd()
    paquete = None
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT serial, nombre, telefono, direccion, f_emi, sector, ruta "
                "FROM paquetes WHERE serial = %s LIMIT 1",
                (serial,),
            )
            paquete = cursor.fetchone()
            cursor.close()
        except Exception as e:
            st.error(f"Error al consultar BD: {e}")
        finally:
            if conn.is_connected():
                conn.close()
    else:
        st.error("No se pudo conectar a la base de datos.")

    if paquete:
        st.markdown(f"**Destinatario:** {paquete.get('nombre', '—')}")
        st.markdown(f"**Dirección:** {paquete.get('direccion', '—')}")
        if paquete.get('telefono'):
            st.markdown(f"**Teléfono:** {paquete['telefono']}")
        if paquete.get('f_emi'):
            from datetime import datetime
            fecha = paquete['f_emi']
            if hasattr(fecha, 'strftime'):
                fecha = fecha.strftime('%d/%m/%Y')
            st.markdown(f"**Fecha emisión:** {fecha}")
        if paquete.get('sector'):
            st.markdown(f"**Sector:** {paquete['sector']}")
        if paquete.get('ruta'):
            st.markdown(f"**Ruta:** {paquete['ruta']}")
    else:
        st.info("Serial no encontrado en la base de datos.")

    st.divider()

    # ── Descargar foto ────────────────────────────────────────────────────────
    ext = os.path.splitext(uploaded.name)[1] or ".jpg"
    dest_filename = f"{serial}{ext}"
    fmt = "JPEG" if ext.lower() in (".jpg", ".jpeg") else "PNG"
    buf_img = io.BytesIO()
    pil_img.save(buf_img, format=fmt)
    st.download_button("💾 Descargar foto", buf_img.getvalue(), dest_filename,
                       f"image/{fmt.lower()}", type="primary", key="btn_guardar_foto")
