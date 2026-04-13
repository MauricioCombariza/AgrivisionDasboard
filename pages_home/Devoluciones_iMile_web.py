"""
Devoluciones_iMile_web.py
=========================
Versión web de Devoluciones iMile.  Funciona desde cualquier dispositivo
(iPad, iPhone, PC, Android) sin necesidad de Windows ni Selenium.

Flujo:
  1. Verifica conexión WhatsApp (muestra QR si no está conectado)
  2. Carga Excel de seriales
  3. Enriquece desde BD cloud (imile.paquetes) + calcula localidad (dirnum)
  4. Serial por serial:
       a. Vista previa del mensaje
       b. Envía WA via wa-service (Node.js corriendo en el servidor)
       c. Genera imagen de confirmación descargable para subir a iMile
"""

import base64
import io
import os
import sys
from datetime import datetime
from pathlib import Path

import mysql.connector
import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

# ── Variables de entorno ───────────────────────────────────────────────────
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

# ── dirnum (estandarización de direcciones) ────────────────────────────────
# Agrega la carpeta dirnum al path para importar el módulo de localidades.
_DIRNUM_DIR = Path(__file__).parent.parent / "dirnum"
if str(_DIRNUM_DIR) not in sys.path:
    sys.path.insert(0, str(_DIRNUM_DIR))

try:
    from estandarizar_direcciones_v3 import estandarizar_direccion, buscar_localidad
    DIRNUM_OK = True
except ImportError:
    DIRNUM_OK = False

# ── Constantes ─────────────────────────────────────────────────────────────
# URL interna de la API WhatsApp (wa-service corriendo en el mismo servidor).
WA_API = os.environ.get("WA_API_URL", "http://127.0.0.1:3000")

LOCALIDAD_ORIGEN = "Barrios Unidos"

MSG_TEMPLATE = (
    "Hola {nombre}, le informamos sobre su envío {serial}. "
    "Dirección registrada: {direccion}.\n"
    "Debido al código postal ingresado al momento del pedido de su paquete, "
    "este salió hacia la localidad de " + LOCALIDAD_ORIGEN + ".\n"
    "Ya hacemos el reenvío hacia la empresa dedicada a distribuir su localidad, {localidad}.\n"
    "Escríbenos si tienes alguna diferencia contra lo escrito."
)

# ── Conexión BD cloud imile ────────────────────────────────────────────────
def _conectar_imile():
    """
    Conecta a la base de datos imile en el servidor cloud.
    La tabla paquetes se sincroniza desde local via SincronizarVPS.py.
    """
    try:
        return mysql.connector.connect(
            host=os.environ.get("DB_HOST_IMILE", "127.0.0.1"),
            port=int(os.environ.get("DB_PORT_IMILE", "3306")),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database="imile",
            connect_timeout=10,
        )
    except Exception as exc:
        st.error(f"Error conectando a BD imile: {exc}")
        return None


def _buscar_serial(serial: str, conn) -> dict | None:
    """Busca un serial en imile.paquetes y retorna sus datos o None."""
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT serial, nombre, telefono, direccion "
            "FROM paquetes WHERE serial = %s",
            (serial.strip(),),
        )
        row = cur.fetchone()
        cur.close()
        return row
    except Exception:
        return None


def _cargar_lote(seriales: list, conn) -> pd.DataFrame:
    """
    Enriquece una lista de seriales con datos de BD y localidad calculada.
    Retorna un DataFrame con una fila por serial.
    """
    filas = []
    total = len(seriales)
    prog  = st.progress(0, text="Consultando base de datos…")

    for i, serial in enumerate(seriales):
        datos = _buscar_serial(serial, conn)

        if datos:
            # Calcular localidad de destino usando dirnum si está disponible
            dir_std   = estandarizar_direccion(datos["direccion"] or "") if DIRNUM_OK else ""
            localidad = buscar_localidad(dir_std) if DIRNUM_OK and dir_std else ""
            filas.append({
                "serial":          datos["serial"],
                "nombre":          datos["nombre"]    or "",
                "telefono":        datos["telefono"]  or "",
                "direccion":       datos["direccion"] or "",
                "localidad":       localidad           or "",
                "wa_enviado":      False,
                "imile_listo":     False,
            })
        else:
            filas.append({
                "serial":      serial,
                "nombre":      "NO ENCONTRADO",
                "telefono":    "",
                "direccion":   "",
                "localidad":   "",
                "wa_enviado":  False,
                "imile_listo": False,
            })

        prog.progress((i + 1) / total, text=f"Procesado {i + 1}/{total}")

    prog.empty()
    return pd.DataFrame(filas)


# ── Helpers WhatsApp API ───────────────────────────────────────────────────

def _wa_status() -> dict:
    """Consulta el estado de la sesión WhatsApp en el servidor."""
    try:
        r = requests.get(f"{WA_API}/status", timeout=3)
        return r.json()
    except Exception:
        return {"ready": False, "has_qr": False, "error": "API no disponible"}


def _wa_qr() -> dict:
    """Obtiene el QR actual como imagen base64."""
    try:
        r = requests.get(f"{WA_API}/qr", timeout=5)
        return r.json()
    except Exception:
        return {"status": "error", "error": "API no disponible"}


def _wa_enviar(phone: str, message: str) -> dict:
    """Envía un mensaje de WhatsApp al número indicado."""
    try:
        r = requests.post(
            f"{WA_API}/send",
            json={"phone": phone, "message": message},
            timeout=30,
        )
        return r.json()
    except Exception as exc:
        return {"error": str(exc)}


def _wa_reiniciar() -> dict:
    """Destruye la sesión y genera un nuevo QR."""
    try:
        r = requests.post(f"{WA_API}/restart", timeout=5)
        return r.json()
    except Exception as exc:
        return {"error": str(exc)}


# ── Generador de imagen de confirmación ───────────────────────────────────

def _generar_imagen_confirmacion(
    serial: str, nombre: str, telefono: str, mensaje: str
) -> bytes:
    """
    Genera una imagen PNG que documenta el envío del mensaje WhatsApp.
    El usuario la descarga y la sube manualmente al portal iMile como evidencia.
    """
    img  = Image.new("RGB", (900, 420), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Encabezado verde (color de WhatsApp)
    draw.rectangle([(0, 0), (900, 80)], fill=(37, 211, 102))

    try:
        f_title = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
        f_body  = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        f_small = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 17)
    except Exception:
        f_title = ImageFont.load_default()
        f_body  = f_title
        f_small = f_title

    draw.text((20, 20), "✓ Mensaje WhatsApp Enviado", fill=(255, 255, 255), font=f_title)

    y = 100
    draw.text((20, y), f"Serial  :  {serial}",   fill=(30, 30, 30), font=f_body); y += 38
    draw.text((20, y), f"Cliente :  {nombre}",   fill=(30, 30, 30), font=f_body); y += 38
    draw.text((20, y), f"Teléfono:  {telefono}", fill=(30, 30, 30), font=f_body); y += 38
    draw.text((20, y), f"Fecha   :  {datetime.now().strftime('%Y-%m-%d %H:%M')}",
              fill=(30, 30, 30), font=f_body); y += 50

    # Línea separadora
    draw.line([(20, y), (880, y)], fill=(200, 200, 200), width=1); y += 15
    draw.text((20, y), "Mensaje:", fill=(100, 100, 100), font=f_small); y += 28

    # Texto del mensaje con salto de línea automático
    for linea in mensaje.split("\n"):
        palabras = linea.split()
        frase    = ""
        for p in palabras:
            prueba = (frase + " " + p).strip()
            if len(prueba) > 95:
                draw.text((20, y), frase, fill=(60, 60, 60), font=f_small)
                y += 22
                frase = p
                if y > 400:
                    break
            else:
                frase = prueba
        if frase and y <= 400:
            draw.text((20, y), frase, fill=(60, 60, 60), font=f_small)
            y += 22
        if y > 400:
            break

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _df_a_excel(df: pd.DataFrame) -> bytes:
    """Convierte el DataFrame enriquecido a bytes de Excel para descargar."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df[["serial", "nombre", "telefono", "direccion", "localidad"]].to_excel(
            w, index=False
        )
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════
st.title("📦 Devoluciones iMile — Web")
st.caption("Funciona desde cualquier dispositivo · Envía WhatsApp automáticamente")

# ── SECCIÓN: Estado de WhatsApp ────────────────────────────────────────────
st.markdown("### 📱 Conexión WhatsApp")

status = _wa_status()

if status.get("ready"):
    st.success("✅ WhatsApp conectado — listo para enviar mensajes")

elif status.get("error") == "API no disponible":
    st.error(
        "❌ La API de WhatsApp no está corriendo en el servidor.  \n"
        "Pide al administrador que ejecute:  \n"
        "`systemctl start whatsapp-api`"
    )
    st.stop()

else:
    # No conectado: mostrar QR para escanear
    st.warning("⚠️ WhatsApp no está conectado. Escanea el código QR con tu teléfono.")

    col_qr, col_inst = st.columns([1, 1])

    with col_qr:
        qr_data = _wa_qr()

        if qr_data.get("status") == "ready":
            st.success("✅ Conectado")
            st.rerun()

        elif qr_data.get("status") == "qr":
            # Decodificar base64 del data URL y mostrar como imagen
            qr_b64  = qr_data["qr"].split(",")[1]
            qr_bytes = base64.b64decode(qr_b64)
            st.image(qr_bytes, caption="Escanea con WhatsApp", width=280)

        elif qr_data.get("status") == "loading":
            st.info("⏳ Iniciando WhatsApp… espera unos segundos")
            if st.button("🔄 Refrescar"):
                st.rerun()

        else:
            st.error(f"Error: {qr_data.get('error')}")

    with col_inst:
        st.markdown(
            "**Cómo conectar:**\n"
            "1. Abre **WhatsApp** en tu teléfono\n"
            "2. Ve a **Dispositivos vinculados**\n"
            "3. Toca **Vincular un dispositivo**\n"
            "4. Escanea el QR de la izquierda\n\n"
            "La sesión queda activa permanentemente.\n"
            "Solo necesitas escanear **una vez**."
        )

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        if st.button("🔄 Refrescar estado", key="btn_refresh_qr"):
            st.rerun()
    with col_r2:
        if st.button("🔁 Generar nuevo QR", key="btn_new_qr"):
            _wa_reiniciar()
            st.info("Reiniciando… espera 10 segundos y refresca")

    st.stop()  # No continuar hasta que WhatsApp esté conectado

st.divider()

# ── PASO 1: Cargar Excel ───────────────────────────────────────────────────
st.subheader("Paso 1 — Cargar seriales")

archivo = st.file_uploader(
    "Archivo Excel con columna **serial**", type=["xlsx", "xls"]
)

if archivo is not None:
    try:
        df_raw = pd.read_excel(archivo)
    except Exception as exc:
        st.error(f"Error al leer el archivo: {exc}")
        st.stop()

    # Buscar columna serial sin importar mayúsculas
    col_serial = next(
        (c for c in df_raw.columns if c.lower().strip() == "serial"), None
    )
    if col_serial is None:
        st.error(
            f"No se encontró columna 'serial'. "
            f"Columnas detectadas: {', '.join(df_raw.columns)}"
        )
        st.stop()

    seriales = df_raw[col_serial].astype(str).str.strip().tolist()
    st.info(f"**{len(seriales)}** seriales detectados")

    if st.button("🔍 Buscar en BD y calcular localidades", type="primary"):
        conn = _conectar_imile()
        if conn:
            with st.spinner("Consultando BD cloud…"):
                df = _cargar_lote(seriales, conn)
            conn.close()
            st.session_state.devol_df  = df
            st.session_state.devol_idx = 0
            if not DIRNUM_OK:
                st.warning(
                    "⚠️ Módulo dirnum no disponible — localidades no calculadas"
                )
            st.rerun()

# ── PASO 2: Resumen + descarga ─────────────────────────────────────────────
if "devol_df" in st.session_state and st.session_state.devol_df is not None:
    df: pd.DataFrame = st.session_state.devol_df

    n_total  = len(df)
    n_ok     = (df["nombre"] != "NO ENCONTRADO").sum()
    n_wa     = int(df["wa_enviado"].sum())
    n_imile  = int(df["imile_listo"].sum())
    n_sin_loc = int(
        ((df["localidad"] == "") & (df["nombre"] != "NO ENCONTRADO")).sum()
    )

    st.divider()
    st.subheader("Paso 2 — Resumen")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total",          n_total)
    c2.metric("En BD",          n_ok)
    c3.metric("Sin localidad",  n_sin_loc)
    c4.metric("WA enviado",     n_wa)
    c5.metric("iMile listo",    n_imile)

    # Tabla editable (localidad se puede corregir manualmente)
    def _estado(row):
        if row["nombre"] == "NO ENCONTRADO":
            return "❌ No encontrado"
        partes = []
        if row["wa_enviado"]:  partes.append("✅ WA")
        if row["imile_listo"]: partes.append("✅ iMile")
        return " | ".join(partes) if partes else "⏳ Pendiente"

    df_vista = df.copy()
    df_vista["estado"] = df_vista.apply(_estado, axis=1)

    edited = st.data_editor(
        df_vista[["serial", "nombre", "direccion", "localidad", "estado"]],
        use_container_width=True,
        hide_index=True,
        disabled=["serial", "nombre", "direccion", "estado"],
        key="tabla_resumen",
    )
    # Persisitir ediciones de localidad del usuario
    st.session_state.devol_df["localidad"] = edited["localidad"].values

    st.download_button(
        "📥 Descargar Excel enriquecido",
        data=_df_a_excel(df),
        file_name="devoluciones_enriquecidas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.divider()

    # ── PASO 3: Serial por serial ──────────────────────────────────────────
    st.subheader("Paso 3 — Procesar serial por serial")

    idx = st.session_state.get("devol_idx", 0)

    # Barra de navegación
    nav1, nav2, nav3 = st.columns([1, 4, 1])
    with nav1:
        if st.button("◀ Anterior", disabled=(idx == 0)):
            st.session_state.devol_idx -= 1
            st.rerun()
    with nav2:
        nuevo_idx = st.selectbox(
            "Serial",
            options=range(n_total),
            index=idx,
            format_func=lambda i: (
                f"{i+1}. {df.iloc[i]['serial']}  "
                f"({'✅' if df.iloc[i]['wa_enviado'] and df.iloc[i]['imile_listo'] else '⏳'})"
            ),
            label_visibility="collapsed",
        )
        if nuevo_idx != idx:
            st.session_state.devol_idx = nuevo_idx
            st.rerun()
    with nav3:
        if st.button("Siguiente ▶", disabled=(idx >= n_total - 1)):
            st.session_state.devol_idx += 1
            st.rerun()

    st.markdown(f"**Serial {idx + 1} de {n_total}**")
    fila = df.iloc[idx]

    if fila["nombre"] == "NO ENCONTRADO":
        st.error(
            f"⚠️ Serial **{fila['serial']}** no encontrado en la BD. "
            "Verifica que esté registrado en iMile."
        )
    else:
        # Datos del serial
        ci1, ci2, ci3, ci4 = st.columns(4)
        ci1.metric("Nombre",    fila["nombre"])
        ci2.metric("Teléfono",  fila["telefono"])
        ci3.metric("Localidad", fila["localidad"] or "—")
        ci4.metric(
            "Estado",
            f"{'✅' if fila['wa_enviado'] else '⬜'} WA  "
            f"{'✅' if fila['imile_listo'] else '⬜'} iMile"
        )

        st.caption(f"Dirección: {fila['direccion']}")

        # Mensaje prellenado (editable por si necesita ajuste)
        localidad_msg = fila["localidad"] if fila["localidad"] else "[LOCALIDAD NO DISPONIBLE]"
        if not fila["localidad"]:
            st.warning("⚠️ Localidad no calculada. Complétala en la tabla de arriba antes de enviar.")

        mensaje = MSG_TEMPLATE.format(
            nombre=fila["nombre"],
            serial=fila["serial"],
            direccion=fila["direccion"],
            localidad=localidad_msg,
        )

        mensaje_editado = st.text_area(
            "📝 Mensaje a enviar (editable)",
            value=mensaje,
            height=160,
            key=f"msg_{idx}",
        )

        st.divider()

        # ── Botones de acción ──────────────────────────────────────────────
        b1, b2 = st.columns(2)

        # ── Botón 1: Enviar WhatsApp ───────────────────────────────────────
        with b1:
            if fila["wa_enviado"]:
                st.success("✅ WhatsApp enviado")
            else:
                if st.button(
                    "📤 Enviar WhatsApp",
                    type="primary",
                    key=f"wa_{idx}",
                    use_container_width=True,
                ):
                    telefono = str(fila["telefono"]).strip()
                    if not telefono:
                        st.error("❌ Este serial no tiene número de teléfono.")
                    else:
                        with st.spinner("Enviando mensaje…"):
                            resultado = _wa_enviar(telefono, mensaje_editado)

                        if "error" in resultado:
                            st.error(f"❌ Error: {resultado['error']}")
                        else:
                            st.session_state.devol_df.at[idx, "wa_enviado"] = True
                            st.success("✅ Mensaje enviado correctamente")
                            st.rerun()

        # ── Botón 2: Descargar imagen para iMile ──────────────────────────
        with b2:
            if fila["imile_listo"]:
                st.success("✅ iMile listo")
            else:
                # Solo habilitar después de enviar WA
                if not fila["wa_enviado"]:
                    st.button(
                        "📷 Generar imagen iMile",
                        disabled=True,
                        key=f"imile_{idx}",
                        use_container_width=True,
                        help="Primero envía el WhatsApp",
                    )
                else:
                    # Generar imagen de confirmación para subir a iMile
                    img_bytes = _generar_imagen_confirmacion(
                        fila["serial"], fila["nombre"],
                        fila["telefono"], mensaje_editado,
                    )

                    # El download_button en Streamlit descarga automáticamente
                    # al pulsarlo, sin necesidad de un botón adicional.
                    descargado = st.download_button(
                        label="📷 Descargar imagen para iMile",
                        data=img_bytes,
                        file_name=f"imile_{fila['serial']}.png",
                        mime="image/png",
                        key=f"dl_imile_{idx}",
                        use_container_width=True,
                    )
                    if descargado:
                        st.session_state.devol_df.at[idx, "imile_listo"] = True
                        st.info(
                            "Imagen descargada. Súbela manualmente al portal iMile "
                            "como evidencia del contacto."
                        )
                        # Avanzar automáticamente al siguiente serial
                        if idx < n_total - 1:
                            st.session_state.devol_idx += 1
                        st.rerun()

    # ── Barra de progreso global ───────────────────────────────────────────
    st.divider()
    completados = int(df["wa_enviado"].sum() & df["imile_listo"].sum() if n_total > 0 else 0)
    wa_done     = int(df["wa_enviado"].sum())
    st.progress(
        wa_done / n_total if n_total > 0 else 0,
        text=f"WA enviados: {wa_done}/{n_total} · iMile listos: {n_imile}/{n_total}",
    )
