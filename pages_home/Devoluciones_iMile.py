# -*- coding: utf-8 -*-
"""
Devoluciones iMile
==================
Flujo completo por serial:
  1. Cargar Excel de seriales
  2. Enriquecer datos desde BD + calcular localidad (dirnum)
  3. Descargar Excel resultante
  4. Serial por serial:
       a. Vista previa del mensaje
       b. Enviar WA y capturar (wa_captura_windows.py — Selenium, sin coordenadas)
       c. Subir imagen a iMile (subir_imile_windows.py — Selenium)
"""

import sys
import os
import io
import json
import platform
import subprocess

import streamlit as st
import pandas as pd
import mysql.connector
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

# ── dirnum ────────────────────────────────────────────────────────────────────
_BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DIRNUM_DIR = os.path.join(_BASE_DIR, "dirnum")
if _DIRNUM_DIR not in sys.path:
    sys.path.insert(0, _DIRNUM_DIR)
from estandarizar_direcciones_v3 import estandarizar_direccion, buscar_localidad

# ── Entorno ───────────────────────────────────────────────────────────────────
load_dotenv()
IMILE_USER = os.getenv("IMILE_USER", "")

LOCALIDAD_ORIGEN = "Barrios Unidos"

MSG_TEMPLATE = (
    "Hola {nombre}, le informamos sobre su envío {serial}. "
    "Dirección registrada: {direccion}.\n"
    "Debido al código postal ingresado al momento del pedido de su paquete, "
    "Este salió hacia la localidad de " + LOCALIDAD_ORIGEN + ".\n"
    "Ya hacemos el reenvío hacia la empresa dedicada a distribuir su localidad, {localidad}.\n"
    "Escríbenos si tienes alguna diferencia contra lo escrito."
)

# ── Helpers comunes ───────────────────────────────────────────────────────────
def _normalizar_numero(numero: str) -> str:
    numero = str(numero).strip()
    return numero if numero.startswith("+") else f"+{numero}"


def _python_win() -> str | None:
    """Retorna la ruta al python.exe de Windows desde WSL2, o None si no se encuentra."""
    for p in [
        "/mnt/c/Users/mcomb/miniconda3/envs/carvajal/python.exe",
        "/mnt/c/Users/mcomb/anaconda3/envs/carvajal/python.exe",
    ]:
        if os.path.exists(p):
            return p.replace("/mnt/c/", "C:\\")
    return None


def _win_path(wsl_path: str) -> str:
    return wsl_path.replace("/mnt/c/", "C:\\").replace("/", "\\")


_PS = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
_DASHBOARD = "/mnt/c/Users/mcomb/Desktop/Carvajal/python/dashboard"


def _run_ps(python_win: str, script_win: str, *args) -> subprocess.CompletedProcess:
    """Ejecuta un script de Windows vía PowerShell y retorna el resultado."""
    args_str = " ".join(f'"{a}"' for a in args)
    return subprocess.run(
        [_PS, "-Command",
         f'[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; '
         f'& "{python_win}" "{script_win}" {args_str}'],
        capture_output=True,
    )


def _mostrar_salida(r: subprocess.CompletedProcess):
    stdout = r.stdout.decode("utf-8", errors="replace")
    stderr = r.stderr.decode("utf-8", errors="replace")
    if stdout.strip():
        st.code(stdout, language=None)
    if stderr.strip():
        st.code(stderr, language=None)
    return stdout


def _json_error(stdout: str) -> str | None:
    """Extrae el campo 'error' si el script devolvió un JSON de error."""
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


# ── Base local ────────────────────────────────────────────────────────────────
def _conectar_imile():
    """Conexión al imile local (MySQL)."""
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST_IMILE", "localhost"),
            user=os.getenv("DB_USER_IMILE", "root"),
            password=os.getenv("DB_PASSWORD_IMILE", ""),
            database=os.getenv("DB_NAME_IMILE", "imile"),
        )
    except mysql.connector.Error:
        return None


def _buscar_serial(serial: str):
    """Busca un serial en la BD local imile.paquetes (fuente persistente)."""
    conn = _conectar_imile()
    if conn is not None:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                "SELECT serial, nombre, telefono, direccion FROM paquetes WHERE serial = %s",
                (serial.strip(),),
            )
            row = cur.fetchone()
            cur.close()
            return row  # dict o None
        except Exception:
            pass
        finally:
            if conn.is_connected():
                conn.close()

    # Fallback: session_state (útil si la BD no está disponible)
    df: pd.DataFrame | None = st.session_state.get("ip_df_base")
    if df is None or df.empty:
        return None
    fila = df[df["serial"] == serial.strip()]
    if fila.empty:
        return None
    row = fila.iloc[0]
    return {
        "serial":    row["serial"],
        "nombre":    row.get("nombre", ""),
        "direccion": row.get("direccion", ""),
        "telefono":  row.get("telefono", ""),
    }


# ── Enriquecimiento ───────────────────────────────────────────────────────────
def _cargar_lote(seriales: list[str]) -> pd.DataFrame:
    filas = []
    total = len(seriales)
    prog  = st.progress(0, text="Consultando base de datos…")
    for i, serial in enumerate(seriales):
        datos = _buscar_serial(serial)
        if datos:
            dir_std   = estandarizar_direccion(datos["direccion"] or "")
            localidad = buscar_localidad(dir_std) if dir_std else ""
            filas.append({
                "serial":            datos["serial"],
                "nombre":            datos["nombre"]   or "",
                "telefono":          datos["telefono"] or "",
                "direccion":         datos["direccion"] or "",
                "direccion_ajustada": dir_std           or "",
                "localidad":         localidad          or "",
                "wa_capturado":      False,
                "imile_subido":      False,
            })
        else:
            filas.append({
                "serial":            serial,
                "nombre":            "NO ENCONTRADO",
                "telefono":          "",
                "direccion":         "",
                "direccion_ajustada": "",
                "localidad":         "",
                "wa_capturado":      False,
                "imile_subido":      False,
            })
        prog.progress(int((i + 1) / total * 100), text=f"Procesado {i+1}/{total}")
    prog.empty()
    return pd.DataFrame(filas)


def _df_a_excel(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df[["serial", "nombre", "telefono", "direccion", "localidad"]].to_excel(w, index=False)
    return buf.getvalue()


# ── Imagen de respaldo cuando el número no tiene WhatsApp ─────────────────────
import tempfile as _tempfile
_DOWNLOADS_WSL = _tempfile.gettempdir()


def _crear_imagen_sin_wa(serial: str, numero: str) -> str:
    """
    Genera una imagen PNG que documenta que el número no tiene WhatsApp.
    Se guarda en el directorio temporal del sistema.
    """
    path = os.path.join(_DOWNLOADS_WSL, f"captura_{serial}.png")

    img  = Image.new("RGB", (900, 320), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Encabezado rojo
    draw.rectangle([(0, 0), (900, 80)], fill=(200, 40, 40))
    try:
        f_title = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
        f_body  = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
    except Exception:
        f_title = ImageFont.load_default()
        f_body  = f_title

    draw.text((20, 18), "SIN WHATSAPP", fill=(255, 255, 255), font=f_title)
    draw.text((20, 105), f"Teléfono : {numero}",  fill=(30, 30, 30),   font=f_body)
    draw.text((20, 150), f"Serial   : {serial}",  fill=(30, 30, 30),   font=f_body)
    draw.text((20, 215), "El número no tiene WhatsApp activo.",
              fill=(100, 100, 100), font=f_body)
    draw.text((20, 258), "Imagen generada automáticamente.",
              fill=(160, 160, 160), font=f_body)

    img.save(path)
    return path


# ── Paso 1: Enviar WA y capturar (script Selenium unificado) ──────────────────
def _wa_y_capturar(numero: str, mensaje: str, serial: str) -> bool:
    """
    Llama a wa_captura_windows.py que con Selenium:
      - Abre WhatsApp Web
      - Espera carga con explicit wait (sin sleep fijo)
      - Localiza el botón Enviar por selector CSS
      - Toma screenshot con driver.save_screenshot()

    Si el número no tiene WhatsApp (error de Selenium al abrir el chat),
    genera una imagen de respaldo y retorna True para que la subida a iMile
    pueda continuar igualmente.
    """
    try:
        is_wsl = "microsoft" in platform.uname().release.lower()

        py = _python_win()
        if not py:
            st.error("Python de Windows no encontrado")
            return False

        script = _win_path(f"{_DASHBOARD}/wa_captura_windows.py")
        numero = _normalizar_numero(numero)

        if is_wsl:
            r = _run_ps(py, script, numero, mensaje, serial)
        else:
            r = subprocess.run(
                [py, script, numero, mensaje, serial],
                capture_output=True,
            )

        stdout = _mostrar_salida(r)

        fallo = r.returncode != 0 or bool(_json_error(stdout))
        if fallo:
            # El número probablemente no tiene WhatsApp.
            # Creamos imagen de respaldo para poder subir evidencia a iMile.
            try:
                ruta = _crear_imagen_sin_wa(serial, numero)
                st.warning(
                    f"⚠️ No se pudo enviar WhatsApp ({numero}). "
                    f"Se generó imagen de respaldo: `{os.path.basename(ruta)}`. "
                    "Puedes subir a iMile indicando que no tiene WhatsApp."
                )
                return True   # desbloquea botón iMile
            except Exception as img_err:
                st.error(f"Error al generar imagen de respaldo: {img_err}")
                return False

        return True

    except Exception as e:
        st.error(f"Error inesperado: {e}")
        return False


# ── Paso 2: Subir imagen a iMile ──────────────────────────────────────────────
def _subir_imile(serial: str) -> bool:
    """
    Llama a subir_imile_windows.py que con Selenium:
      - Reutiliza Chrome con remote debugging (sin re-login)
      - Llena el formulario con selectores role="combobox" (sin clases hasheadas)
      - Sube el archivo con send_keys en input[type="file"] (sin PyAutoGUI)
    """
    try:
        is_wsl = "microsoft" in platform.uname().release.lower()

        py = _python_win()
        if not py:
            st.error("Python de Windows no encontrado")
            return False

        script = _win_path(f"{_DASHBOARD}/subir_imile_windows.py")

        if is_wsl:
            r = _run_ps(py, script, serial)
        else:
            r = subprocess.run([py, script, serial], capture_output=True)

        stdout = _mostrar_salida(r)

        if r.returncode != 0:
            st.error(f"Error en subida a iMile (código {r.returncode})")
            return False

        err = _json_error(stdout)
        if err:
            st.error(f"Error reportado por el script: {err}")
            return False

        return True

    except Exception as e:
        st.error(f"Error inesperado: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════
st.title("📦 Devoluciones iMile")
st.markdown(
    "Carga el Excel con seriales, enriquece desde la BD, "
    "envía WhatsApp con captura automática (Selenium) y sube a iMile serial por serial."
)

# ── Estado inicial ────────────────────────────────────────────────────────────
for key, val in [("devol_df", None), ("devol_idx", 0)]:
    if key not in st.session_state:
        st.session_state[key] = val

if st.session_state.get("ip_df_base") is None:
    conn_test = _conectar_imile()
    if conn_test is None:
        st.warning(
            "No hay base local cargada ni conexión a la BD. Ve a **Ingreso paquetes → Subir bases** "
            "y presiona «Guardar base localmente» primero."
        )
        st.stop()
    else:
        conn_test.close()

st.divider()

# ── PASO 1: Cargar archivo ────────────────────────────────────────────────────
st.subheader("Paso 1 — Cargar seriales")
archivo = st.file_uploader("Archivo Excel con columna **serial**", type=["xlsx", "xls"])

if archivo is not None:
    try:
        df_raw = pd.read_excel(archivo)
    except Exception as e:
        st.error(f"Error al leer el archivo: {e}")
        st.stop()

    col_match = next(
        (c for c in df_raw.columns if c.lower().strip() == "serial"), None
    )
    if col_match is None:
        st.error(f"No se encontró columna 'serial'. Columnas: {', '.join(df_raw.columns)}")
        st.stop()

    seriales = df_raw[col_match].astype(str).str.strip().tolist()
    st.info(f"**{len(seriales)}** seriales detectados")

    if st.button("🔍 Buscar en BD y calcular localidades", type="primary"):
        with st.spinner("Procesando…"):
            df = _cargar_lote(seriales)
        st.session_state.devol_df  = df
        st.session_state.devol_idx = 0
        st.rerun()

# ── PASO 2: Resumen + descarga ────────────────────────────────────────────────
if st.session_state.devol_df is not None:
    df: pd.DataFrame = st.session_state.devol_df
    n_total   = len(df)
    n_ok      = (df["nombre"] != "NO ENCONTRADO").sum()
    n_wa      = df["wa_capturado"].sum()
    n_imile   = df["imile_subido"].sum()
    n_sin_loc = ((df["localidad"] == "") & (df["nombre"] != "NO ENCONTRADO")).sum()

    st.divider()
    st.subheader("Paso 2 — Resumen")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total seriales",    n_total)
    m2.metric("Encontrados en BD", n_ok)
    m3.metric("Sin localidad",     n_sin_loc)
    m4.metric("WA + captura",      int(n_wa))
    m5.metric("iMile subidos",     int(n_imile))

    def _estado(row):
        if row["nombre"] == "NO ENCONTRADO":
            return "❌ No encontrado"
        partes = []
        if row["wa_capturado"]:
            partes.append("✅ WA")
        if row["imile_subido"]:
            partes.append("✅ iMile")
        return " | ".join(partes) if partes else "⏳ Pendiente"

    df_vista = df.copy()
    df_vista["estado"] = df_vista.apply(_estado, axis=1)
    edited = st.data_editor(
        df_vista[["serial", "direccion_ajustada", "direccion", "localidad", "estado"]],
        width="stretch",
        hide_index=True,
        disabled=["serial", "direccion_ajustada", "direccion", "estado"],
        key="tabla_resumen",
    )
    st.session_state.devol_df["localidad"] = edited["localidad"].values

    st.download_button(
        "📥 Descargar Excel enriquecido",
        data=_df_a_excel(df),
        file_name="devoluciones_enriquecidas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.divider()

    # ── PASO 3: Serial por serial ─────────────────────────────────────────────
    st.subheader("Paso 3 — Procesar serial por serial")
    idx = st.session_state.devol_idx

    # Navegación
    nav1, nav2, nav3 = st.columns([1, 4, 1])
    with nav1:
        if st.button("◀ Anterior") and idx > 0:
            st.session_state.devol_idx -= 1
            st.rerun()
    with nav2:
        nuevo_idx = st.selectbox(
            "Ir al serial",
            options=range(n_total),
            index=idx,
            format_func=lambda i: (
                f"{i+1}. {df.iloc[i]['serial']} "
                f"({'✅' if df.iloc[i]['wa_capturado'] and df.iloc[i]['imile_subido'] else '⏳'})"
            ),
            label_visibility="collapsed",
        )
        if nuevo_idx != idx:
            st.session_state.devol_idx = nuevo_idx
            st.rerun()
    with nav3:
        if st.button("Siguiente ▶") and idx < n_total - 1:
            st.session_state.devol_idx += 1
            st.rerun()

    st.markdown(f"**Serial {idx + 1} de {n_total}**")
    fila = df.iloc[idx]

    if fila["nombre"] == "NO ENCONTRADO":
        st.error(f"⚠️ Serial **{fila['serial']}** no se encontró en la BD. Pasa al siguiente.")
    else:
        ci1, ci2, ci3, ci4 = st.columns(4)
        ci1.metric("Dirección ajustada", fila.get("direccion_ajustada") or fila["direccion"] or "—")
        ci2.metric("Teléfono",           fila["telefono"])
        ci3.metric("Localidad destino", fila["localidad"] or "—")
        ci4.metric("Estado",
                   f"{'✅' if fila['wa_capturado'] else '⬜'} WA  "
                   f"{'✅' if fila['imile_subido'] else '⬜'} iMile")

        st.text(f"Dirección: {fila['direccion']}")

        # Vista previa del mensaje
        localidad_msg = fila["localidad"] if fila["localidad"] else "[LOCALIDAD NO DISPONIBLE]"
        if not fila["localidad"]:
            st.warning("⚠️ No se pudo calcular la localidad destino. El mensaje quedará incompleto.")

        mensaje = MSG_TEMPLATE.format(
            nombre=fila["nombre"],
            serial=fila["serial"],
            direccion=fila["direccion"],
            localidad=localidad_msg,
        )
        st.text_area("📝 Mensaje a enviar", mensaje, height=160, disabled=True, key=f"msg_{idx}")

        # ── Botones de acción ─────────────────────────────────────────────────
        b1, b2, b3 = st.columns(3)

        with b1:
            lbl = "✅ WA enviado y capturado" if fila["wa_capturado"] else "1️⃣ Enviar WA y Capturar"
            if st.button(lbl, key=f"wa_{idx}",
                         disabled=fila["wa_capturado"],
                         width="stretch"):
                with st.status("Enviando WhatsApp y capturando…", expanded=True):
                    ok = _wa_y_capturar(fila["telefono"], mensaje, fila["serial"])
                if ok:
                    st.session_state.devol_df.at[idx, "wa_capturado"] = True
                    st.success("✅ Mensaje enviado y pantalla capturada")
                    st.rerun()

        with b2:
            lbl2 = "✅ Subido a iMile" if fila["imile_subido"] else "2️⃣ Subir a iMile"
            if st.button(lbl2, key=f"imile_{idx}",
                         disabled=fila["imile_subido"] or not fila["wa_capturado"],
                         width="stretch",
                         help="Primero debes enviar el WA y capturar" if not fila["wa_capturado"] else ""):
                with st.status("Subiendo a iMile…", expanded=True):
                    ok2 = _subir_imile(fila["serial"])
                if ok2:
                    st.session_state.devol_df.at[idx, "imile_subido"] = True
                    st.success("✅ Imagen subida a iMile")
                    st.rerun()

        with b3:
            # Etiqueta dinámica según lo que queda por hacer
            if fila["wa_capturado"] and fila["imile_subido"]:
                lbl3 = "Siguiente ▶"
            elif fila["wa_capturado"]:
                lbl3 = "2️⃣ iMile + Siguiente ▶"
            else:
                lbl3 = "1️⃣ WA + iMile + Siguiente ▶"

            if st.button(lbl3, key=f"next_{idx}", type="primary", width="stretch"):
                # Paso 1: WA (si aún no se hizo)
                if not fila["wa_capturado"]:
                    with st.status("Enviando WhatsApp y capturando…", expanded=True):
                        ok_wa = _wa_y_capturar(fila["telefono"], mensaje, fila["serial"])
                    if ok_wa:
                        st.session_state.devol_df.at[idx, "wa_capturado"] = True
                        fila = st.session_state.devol_df.iloc[idx]
                    else:
                        st.error("Falló el envío de WA. Corrige antes de continuar.")
                        st.stop()

                # Paso 2: iMile (si aún no se hizo)
                if not fila["imile_subido"]:
                    with st.status("Subiendo a iMile…", expanded=True):
                        ok_imile = _subir_imile(fila["serial"])
                    if ok_imile:
                        st.session_state.devol_df.at[idx, "imile_subido"] = True
                    else:
                        st.error("Falló la subida a iMile. Corrige antes de continuar.")
                        st.stop()

                # Paso 3: avanzar
                if idx < n_total - 1:
                    st.session_state.devol_idx += 1
                else:
                    st.success("🎉 Todos los seriales procesados")
                st.rerun()
