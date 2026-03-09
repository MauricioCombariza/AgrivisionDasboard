# -*- coding: utf-8 -*-
"""
Devoluciones iMile — versión móvil
Diseño vertical, botones grandes, sin tablas complejas.
"""

import sys
import os
import io
import json
import platform
import subprocess
from typing import Optional, List, Dict

import streamlit as st
import pandas as pd
import mysql.connector
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

st.set_page_config(
    page_title="Devoluciones iMile",
    page_icon="📦",
    layout="centered",
)

# ── Rutas ─────────────────────────────────────────────────────────────────────
_MOBILE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DASHBOARD   = os.path.dirname(_MOBILE_DIR)
_DIRNUM_DIR  = os.path.join(_DASHBOARD, "dirnum")
_DOWNLOADS   = "/mnt/c/Users/mcomb/Downloads"
_PS          = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"

if _DIRNUM_DIR not in sys.path:
    sys.path.insert(0, _DIRNUM_DIR)

from estandarizar_direcciones_v3 import estandarizar_direccion, buscar_localidad

load_dotenv(os.path.join(_DASHBOARD, ".env"))

# ── Constantes ────────────────────────────────────────────────────────────────
LOCALIDAD_ORIGEN = "Barrios Unidos"

MSG_TEMPLATE = (
    "Hola {nombre}, le informamos sobre su envío {serial}. "
    "Dirección registrada: {direccion}.\n"
    "Debido al código postal ingresado al momento del pedido de su paquete, "
    "Este salió hacia la localidad de " + LOCALIDAD_ORIGEN + ".\n"
    "Ya hacemos el reenvío hacia la empresa dedicada a distribuir su localidad, {localidad}.\n"
    "Escríbenos si tienes alguna diferencia contra lo escrito."
)

# ── Helpers ───────────────────────────────────────────────────────────────────
def _normalizar_numero(numero: str) -> str:
    numero = str(numero).strip()
    return numero if numero.startswith("+") else f"+{numero}"


def _python_win() -> Optional[str]:
    for p in [
        "/mnt/c/Users/mcomb/miniconda3/envs/carvajal/python.exe",
        "/mnt/c/Users/mcomb/anaconda3/envs/carvajal/python.exe",
    ]:
        if os.path.exists(p):
            return p.replace("/mnt/c/", "C:\\")
    return None


def _win_path(wsl_path: str) -> str:
    return wsl_path.replace("/mnt/c/", "C:\\").replace("/", "\\")


def _run_ps(python_win: str, script_win: str, *args) -> subprocess.CompletedProcess:
    args_str = " ".join(f'"{a}"' for a in args)
    return subprocess.run(
        [_PS, "-Command",
         f'[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; '
         f'& "{python_win}" "{script_win}" {args_str}'],
        capture_output=True,
    )


def _json_error(stdout: str) -> Optional[str]:
    for line in stdout.split("\n"):
        line = line.strip()
        if line.startswith("{"):
            try:
                obj = json.loads(line)
                if obj.get("status") == "error":
                    return obj.get("error", "Error desconocido")
            except Exception:
                pass
    return None


# ── Base de datos ─────────────────────────────────────────────────────────────
def _conectar_mysql():
    is_wsl = "microsoft" in platform.uname().release.lower()
    if is_wsl:
        try:
            res = subprocess.run(["ip", "route", "show"], capture_output=True, text=True)
            for line in res.stdout.split("\n"):
                if "default" in line:
                    windows_ip = line.split()[2]
                    try:
                        return mysql.connector.connect(
                            host=windows_ip, user="root",
                            password=os.environ.get("DB_PASSWORD", ""), database="imile",
                        )
                    except Exception:
                        break
        except Exception:
            pass
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST","localhost"), user=os.environ.get("DB_USER","root"), password=os.environ.get("DB_PASSWORD",""), database="imile",
    )


def _buscar_serial(serial: str):
    conn = None
    try:
        conn = _conectar_mysql()
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                "SELECT serial, nombre, direccion, telefono "
                "FROM paquetes WHERE serial = %s LIMIT 1",
                (serial.strip(),),
            )
            return cur.fetchone()
    except Exception:
        return None
    finally:
        if conn and conn.is_connected():
            conn.close()


def _enriquecer(serial: str) -> dict:
    datos = _buscar_serial(serial)
    if not datos:
        return {"serial": serial, "nombre": "NO ENCONTRADO",
                "telefono": "", "direccion": "", "localidad": "",
                "wa_capturado": False, "imile_subido": False}
    dir_std   = estandarizar_direccion(datos["direccion"] or "")
    localidad = buscar_localidad(dir_std) if dir_std else ""
    return {
        "serial":       datos["serial"],
        "nombre":       datos["nombre"]   or "",
        "telefono":     datos["telefono"] or "",
        "direccion":    datos["direccion"] or "",
        "localidad":    localidad          or "",
        "wa_capturado": False,
        "imile_subido": False,
    }


def _df_a_excel(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df[["serial", "nombre", "telefono", "direccion", "localidad"]].to_excel(w, index=False)
    return buf.getvalue()


# ── Imagen sin WhatsApp ────────────────────────────────────────────────────────
def _crear_imagen_sin_wa(serial: str, numero: str) -> str:
    path = os.path.join(_DOWNLOADS, f"captura_{serial}.png")
    img  = Image.new("RGB", (900, 320), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (900, 80)], fill=(200, 40, 40))
    try:
        f_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
        f_body  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
    except Exception:
        f_title = ImageFont.load_default()
        f_body  = f_title
    draw.text((20, 18),  "SIN WHATSAPP",                              fill=(255,255,255), font=f_title)
    draw.text((20, 105), f"Teléfono : {numero}",                      fill=(30,30,30),    font=f_body)
    draw.text((20, 150), f"Serial   : {serial}",                      fill=(30,30,30),    font=f_body)
    draw.text((20, 215), "El número no tiene WhatsApp activo.",        fill=(100,100,100), font=f_body)
    draw.text((20, 258), "Imagen generada automáticamente.",           fill=(160,160,160), font=f_body)
    img.save(path)
    return path


# ── Acciones Selenium ──────────────────────────────────────────────────────────
def _wa_y_capturar(numero: str, mensaje: str, serial: str) -> bool:
    py = _python_win()
    if not py:
        st.error("Python de Windows no encontrado")
        return False
    script  = _win_path(f"{_DASHBOARD}/wa_captura_windows.py")
    numero  = _normalizar_numero(numero)
    is_wsl  = "microsoft" in platform.uname().release.lower()
    r = _run_ps(py, script, numero, mensaje, serial) if is_wsl else \
        subprocess.run([py, script, numero, mensaje, serial], capture_output=True)
    stdout = r.stdout.decode("utf-8", errors="replace")
    stderr = r.stderr.decode("utf-8", errors="replace")
    if stdout.strip():
        with st.expander("Ver salida WA"):
            st.code(stdout, language=None)
    if stderr.strip():
        with st.expander("Ver errores WA"):
            st.code(stderr, language=None)
    fallo = r.returncode != 0 or bool(_json_error(stdout))
    if fallo:
        try:
            _crear_imagen_sin_wa(serial, numero)
            st.warning(f"Sin WhatsApp ({numero}). Imagen de respaldo generada.")
            return True
        except Exception as e:
            st.error(f"Error imagen respaldo: {e}")
            return False
    return True


def _subir_imile(serial: str) -> bool:
    py = _python_win()
    if not py:
        st.error("Python de Windows no encontrado")
        return False
    script = _win_path(f"{_DASHBOARD}/subir_imile_windows.py")
    is_wsl = "microsoft" in platform.uname().release.lower()
    r = _run_ps(py, script, serial) if is_wsl else \
        subprocess.run([py, script, serial], capture_output=True)
    stdout = r.stdout.decode("utf-8", errors="replace")
    stderr = r.stderr.decode("utf-8", errors="replace")
    if stdout.strip():
        with st.expander("Ver salida iMile"):
            st.code(stdout, language=None)
    if stderr.strip():
        with st.expander("Ver errores iMile"):
            st.code(stderr, language=None)
    if r.returncode != 0:
        st.error(f"Error iMile (código {r.returncode})")
        return False
    err = _json_error(stdout)
    if err:
        st.error(f"Error: {err}")
        return False
    return True


# ══════════════════════════════════════════════════════════════════════════════
# UI MOBILE
# ══════════════════════════════════════════════════════════════════════════════
st.title("📦 Devoluciones iMile")

# ── Estado ────────────────────────────────────────────────────────────────────
for key, val in [("m_filas", []), ("m_idx", 0), ("m_cargado", False)]:
    if key not in st.session_state:
        st.session_state[key] = val

# ══ PASO 1: Ingresar seriales ══════════════════════════════════════════════════
if not st.session_state.m_cargado:
    st.subheader("Paso 1 — Ingresa los seriales")

    modo = st.radio("Modo de ingreso", ["✍️ Escribir / pegar", "📂 Subir Excel"], horizontal=True)
    seriales_raw: List[str] = []

    if modo == "✍️ Escribir / pegar":
        texto = st.text_area(
            "Un serial por línea (o separados por coma)",
            height=180,
            placeholder="IM1234567890\nIM0987654321\n...",
        )
        if texto.strip():
            seriales_raw = [
                s.strip()
                for part in texto.replace(",", "\n").split("\n")
                for s in [part.strip()]
                if s
            ]
    else:
        archivo = st.file_uploader("Excel con columna **serial**", type=["xlsx", "xls"])
        if archivo:
            try:
                df_raw = pd.read_excel(archivo)
                col = next((c for c in df_raw.columns if c.lower().strip() == "serial"), None)
                if col:
                    seriales_raw = df_raw[col].astype(str).str.strip().tolist()
                else:
                    st.error(f"No hay columna 'serial'. Columnas: {', '.join(df_raw.columns)}")
            except Exception as e:
                st.error(f"Error al leer Excel: {e}")

    if seriales_raw:
        st.info(f"**{len(seriales_raw)}** seriales listos")

    if seriales_raw and st.button("🔍 Buscar en BD", type="primary", use_container_width=True):
        filas = []
        prog = st.progress(0, text="Consultando BD…")
        for i, s in enumerate(seriales_raw):
            filas.append(_enriquecer(s))
            prog.progress(int((i + 1) / len(seriales_raw) * 100), text=f"{i+1}/{len(seriales_raw)}")
        prog.empty()
        st.session_state.m_filas   = filas
        st.session_state.m_idx     = 0
        st.session_state.m_cargado = True
        st.rerun()

# ══ PASO 2 + 3: Procesar ══════════════════════════════════════════════════════
else:
    filas   = st.session_state.m_filas
    n_total = len(filas)
    idx     = st.session_state.m_idx

    # Barra de progreso global
    n_done = sum(1 for f in filas if f["wa_capturado"] and f["imile_subido"])
    st.progress(n_done / n_total, text=f"Completados: {n_done} / {n_total}")

    # Descarga Excel enriquecido
    df_export = pd.DataFrame(filas)
    st.download_button(
        "📥 Descargar Excel enriquecido",
        data=_df_a_excel(df_export),
        file_name="devoluciones_enriquecidas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    if n_done == n_total:
        st.success("🎉 Todos los seriales procesados")
        if st.button("🔄 Nueva tanda", use_container_width=True):
            st.session_state.m_filas   = []
            st.session_state.m_idx     = 0
            st.session_state.m_cargado = False
            st.rerun()
        st.stop()

    st.divider()

    # Navegación (solo prev / next + contador)
    nav_col1, nav_col2, nav_col3 = st.columns([1, 3, 1])
    with nav_col1:
        if st.button("◀", disabled=(idx == 0), use_container_width=True):
            st.session_state.m_idx -= 1
            st.rerun()
    with nav_col2:
        st.markdown(
            f"<div style='text-align:center;font-size:1.1rem;padding-top:6px'>"
            f"<b>{idx + 1} / {n_total}</b></div>",
            unsafe_allow_html=True,
        )
    with nav_col3:
        if st.button("▶", disabled=(idx == n_total - 1), use_container_width=True):
            st.session_state.m_idx += 1
            st.rerun()

    fila = filas[idx]

    st.divider()

    # ── Tarjeta del serial actual ──────────────────────────────────────────────
    estado_wa    = "✅" if fila["wa_capturado"] else "⬜"
    estado_imile = "✅" if fila["imile_subido"]  else "⬜"

    st.markdown(f"### {fila['serial']}")
    st.markdown(f"**{estado_wa} WA &nbsp;&nbsp; {estado_imile} iMile**")

    if fila["nombre"] == "NO ENCONTRADO":
        st.error("Serial no encontrado en la BD. Avanza al siguiente.")
        if idx < n_total - 1:
            if st.button("Siguiente ▶", use_container_width=True):
                st.session_state.m_idx += 1
                st.rerun()
        st.stop()

    # Datos del paquete (apilados verticalmente)
    st.markdown(f"👤 **{fila['nombre']}**")
    st.markdown(f"📞 `{fila['telefono']}`")
    st.markdown(f"📍 {fila['direccion']}")

    # Localidad editable inline
    nueva_loc = st.text_input(
        "🏙️ Localidad destino",
        value=fila["localidad"],
        key=f"loc_{idx}",
    )
    if nueva_loc != fila["localidad"]:
        st.session_state.m_filas[idx]["localidad"] = nueva_loc
        fila = st.session_state.m_filas[idx]

    if not fila["localidad"]:
        st.warning("Sin localidad — el mensaje quedará incompleto.")

    # Vista previa del mensaje (colapsable para ahorrar espacio)
    localidad_msg = fila["localidad"] or "[LOCALIDAD NO DISPONIBLE]"
    mensaje = MSG_TEMPLATE.format(
        nombre=fila["nombre"],
        serial=fila["serial"],
        direccion=fila["direccion"],
        localidad=localidad_msg,
    )
    with st.expander("📝 Ver mensaje a enviar"):
        st.text(mensaje)

    st.divider()

    # ── Botones de acción (full-width, apilados) ───────────────────────────────

    # Botón principal: hace todo y avanza
    if not (fila["wa_capturado"] and fila["imile_subido"]):
        if fila["wa_capturado"] and not fila["imile_subido"]:
            lbl_todo = "2️⃣ Subir a iMile + Siguiente ▶"
        elif not fila["wa_capturado"]:
            lbl_todo = "🚀 WA + iMile + Siguiente ▶"
        else:
            lbl_todo = "Siguiente ▶"

        if st.button(lbl_todo, type="primary", use_container_width=True):
            if not fila["wa_capturado"]:
                with st.status("Enviando WhatsApp…", expanded=True):
                    ok_wa = _wa_y_capturar(fila["telefono"], mensaje, fila["serial"])
                if ok_wa:
                    st.session_state.m_filas[idx]["wa_capturado"] = True
                    fila = st.session_state.m_filas[idx]
                else:
                    st.error("Falló WA. Corrige y reintenta.")
                    st.stop()

            if not fila["imile_subido"]:
                with st.status("Subiendo a iMile…", expanded=True):
                    ok_im = _subir_imile(fila["serial"])
                if ok_im:
                    st.session_state.m_filas[idx]["imile_subido"] = True
                else:
                    st.error("Falló iMile. Corrige y reintenta.")
                    st.stop()

            if idx < n_total - 1:
                st.session_state.m_idx += 1
            st.rerun()

    # Botones individuales (por si algo falla y quieres hacerlo por separado)
    with st.expander("Opciones individuales"):
        if st.button(
            "1️⃣ Solo enviar WA",
            disabled=fila["wa_capturado"],
            use_container_width=True,
        ):
            with st.status("Enviando WhatsApp…", expanded=True):
                ok = _wa_y_capturar(fila["telefono"], mensaje, fila["serial"])
            if ok:
                st.session_state.m_filas[idx]["wa_capturado"] = True
                st.success("WA enviado y capturado")
                st.rerun()

        if st.button(
            "2️⃣ Solo subir a iMile",
            disabled=fila["imile_subido"] or not fila["wa_capturado"],
            use_container_width=True,
            help="Primero debes enviar el WA" if not fila["wa_capturado"] else "",
        ):
            with st.status("Subiendo a iMile…", expanded=True):
                ok2 = _subir_imile(fila["serial"])
            if ok2:
                st.session_state.m_filas[idx]["imile_subido"] = True
                st.success("Subido a iMile")
                st.rerun()

    # Saltar al siguiente sin procesar
    if idx < n_total - 1:
        if st.button("⏭️ Saltar este serial", use_container_width=True):
            st.session_state.m_idx += 1
            st.rerun()

    # Resumen de todos los seriales al final
    with st.expander(f"📋 Ver todos los seriales ({n_done}/{n_total} listos)"):
        for i, f in enumerate(filas):
            wa  = "✅" if f["wa_capturado"] else "⬜"
            im  = "✅" if f["imile_subido"]  else "⬜"
            cur = " ◀ actual" if i == idx else ""
            st.markdown(f"`{f['serial']}` — {wa} WA {im} iMile{cur}")
        if st.button("Ir al primero pendiente", use_container_width=True):
            for i, f in enumerate(filas):
                if not (f["wa_capturado"] and f["imile_subido"]) and f["nombre"] != "NO ENCONTRADO":
                    st.session_state.m_idx = i
                    st.rerun()
                    break
