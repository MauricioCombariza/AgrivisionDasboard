# ----------------------------
# 📦 IMPORTACIONES
# ----------------------------
import sys
import numpy as np
import streamlit as st
import pandas as pd
import pyautogui as pw
import os
from dotenv import load_dotenv

load_dotenv()
import time
import subprocess
from urllib.parse import quote
from PIL import Image

# Dirnum: estandarización y localidad
_BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DIRNUM_DIR = os.path.join(_BASE_DIR, "dirnum")
if _DIRNUM_DIR not in sys.path:
    sys.path.insert(0, _DIRNUM_DIR)
from estandarizar_direcciones_v3 import estandarizar_direccion, buscar_localidad

# ----------------------------
# ⚙ CONFIGURACIÓN INICIAL
# ----------------------------

pw.PAUSE = 1.5  # Pausa entre acciones de pyautogui
pw.FAILSAFE = False  # Desactivar failsafe para evitar bloqueos

# ----------------------------
# 📱 MÓDULO WHATSAPP
# ----------------------------
def obtener_posicion_mouse():
    """Función de ayuda para obtener coordenadas del mouse (debugging)"""
    try:
        st.info("Mueve el mouse sobre el botón de envío y presiona Ctrl+C en la terminal")
        while True:
            x, y = pw.position()
            print(f"\rPosición actual: X={x}, Y={y}", end="")
            time.sleep(0.1)
    except KeyboardInterrupt:
        x, y = pw.position()
        st.success(f"Coordenadas guardadas: X={x}, Y={y}")
        return x, y

def enviar_mensaje_whatsapp(numero, mensaje):
    """Envía un mensaje por WhatsApp Web con pyautogui optimizado."""
    try:
        numero = str(numero).strip()
        if not numero.startswith("+"):
            numero = f"+{numero}"

        # --- 🔍 Detectar si estamos en Windows o WSL ---
        import platform
        is_wsl = 'microsoft' in platform.uname().release.lower()

        if is_wsl:
            # === MODO WSL2: Llamar script de Windows ===
            # Obtener coordenadas configuradas
            if hasattr(st.session_state, 'coord_enviar') and st.session_state.coord_enviar:
                coord_x, coord_y = st.session_state.coord_enviar
            else:
                coord_x, coord_y = 1884, 979

            # Ruta al script de Windows
            script_windows = "/mnt/c/Users/mcomb/Desktop/Carvajal/python/dashboard/enviar_mensaje_windows.py"

            # Buscar Python de Windows en el ambiente carvajal
            python_win_paths = [
                "/mnt/c/Users/mcomb/miniconda3/envs/carvajal/python.exe",
                "/mnt/c/Users/mcomb/anaconda3/envs/carvajal/python.exe"
            ]

            python_win = None
            for path in python_win_paths:
                if os.path.exists(path):
                    python_win = path.replace('/mnt/c/', 'C:\\')
                    break

            if not python_win:
                st.error("❌ Error: Python de Windows no encontrado")
                return False

            # Convertir rutas de WSL a Windows
            script_win = script_windows.replace('/mnt/c/', 'C:\\').replace('/', '\\')

            import subprocess as sp

            # Ruta completa de PowerShell en WSL2
            powershell_path = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"

            # Ejecutar sin decodificación automática para evitar errores de encoding
            result = sp.run([
                powershell_path, "-Command",
                f'[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; & "{python_win}" "{script_win}" "{numero}" "{mensaje}" {coord_x} {coord_y}'
            ], capture_output=True)

            # Solo verificar resultado sin mostrar logs
            if result.returncode == 0:
                return True
            else:
                st.error("Error en envío del mensaje")
                return False

        # === MODO WINDOWS NATIVO: PyAutoGUI directo ===

        mensaje_codificado = quote(mensaje)
        url = f"https://web.whatsapp.com/send?phone={numero}&text={mensaje_codificado}"

        # --- 🔍 Buscar ruta correcta de Chrome (Windows nativo) ---
        chrome_base = "C:\\Program Files\\Google\\Chrome\\Application\\"

        posibles_rutas = [
            os.path.join(chrome_base, "chrome.exe"),
            os.path.join(chrome_base, "chrome_proxy.exe")
        ]

        # También buscar en Program Files (x86)
        chrome_base_x86 = "C:\\Program Files (x86)\\Google\\Chrome\\Application\\"
        if os.path.exists(chrome_base_x86):
            posibles_rutas.append(os.path.join(chrome_base_x86, "chrome.exe"))

        if os.path.exists(chrome_base):
            for item in os.listdir(chrome_base):
                if os.path.isdir(os.path.join(chrome_base, item)) and item[0].isdigit():
                    posibles_rutas.append(os.path.join(chrome_base, item, "chrome.exe"))

        chrome_path = next((p for p in posibles_rutas if os.path.exists(p)), None)
        if not chrome_path:
            st.error("⚠️ No se encontró Google Chrome.")
            return False

        # --- 🚀 Abrir Chrome maximizado ---
        subprocess.Popen([
            chrome_path,
            "--start-maximized",
            "--new-window",
            url
        ])

        # --- ⏳ Esperar carga (reducido a 10s) ---
        time.sleep(10)

        # --- 📤 Enviar mensaje ---
        # Coordenadas predeterminadas
        DEFAULT_SEND_X = 1884
        DEFAULT_SEND_Y = 979

        # Verificar coordenadas personalizadas
        if hasattr(st.session_state, 'coord_enviar') and st.session_state.coord_enviar:
            x, y = st.session_state.coord_enviar
        else:
            x, y = DEFAULT_SEND_X, DEFAULT_SEND_Y

        # Mover y hacer click
        pw.moveTo(x, y, duration=0.3)
        time.sleep(0.3)
        pw.click(x, y)
        time.sleep(2)

        # --- 🧹 NO cerrar la pestaña - dejarla abierta para ver el resultado ---
        # La pestaña se cerrará al inicio del SIGUIENTE envío

        return True

    except Exception as e:
        st.error("Error al enviar mensaje")
        try:
            # Intentar cerrar solo la pestaña de WhatsApp en caso de error
            pw.hotkey('ctrl', 'w')
        except:
            pass
        return False

# ----------------------------
# 🗃 BASE LOCAL (MySQL localhost)
# ----------------------------
import mysql.connector as _mc

def buscar_datos_por_serial(serial):
    """Busca el serial en la BD local imile (localhost)."""
    try:
        conn = _mc.connect(host="localhost", user="root", password=os.environ.get("DB_PASSWORD_IMILE", ""), database="imile")
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                "SELECT serial, nombre, direccion, telefono "
                "FROM paquetes WHERE serial = %s LIMIT 1",
                (str(serial).strip(),),
            )
            return cur.fetchone()
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass

# ----------------------------
# 🖥 INTERFAZ PRINCIPAL
# ----------------------------
def main():
    st.title("🚀 Envío Masivo WhatsApp")

    # --- ⚙️ Configuración de coordenadas (opcional) ---
    with st.expander("⚙️ Configuración Avanzada (Opcional)"):
        st.write("**Coordenadas predeterminadas del botón de envío:** X=1884, Y=979")
        st.write("Si el envío falla en tu pantalla, puedes ajustar las coordenadas:")

        col1, col2, col3 = st.columns(3)
        with col1:
            coord_x = st.number_input("Coordenada X del botón enviar", value=1884, min_value=0, max_value=3840)
        with col2:
            coord_y = st.number_input("Coordenada Y del botón enviar", value=979, min_value=0, max_value=2160)
        with col3:
            if st.button("🎯 Probar Posición"):
                try:
                    st.info("Moviendo mouse en 3 segundos...")
                    print(f"\n🎯 PRUEBA DE POSICIÓN")
                    print(f"Tamaño pantalla: {pw.size()}")
                    print(f"Posición actual: {pw.position()}")
                    print(f"Moviendo a: ({coord_x}, {coord_y})")

                    time.sleep(3)
                    pw.moveTo(coord_x, coord_y, duration=0.5)

                    new_pos = pw.position()
                    print(f"Nueva posición: {new_pos}")
                    st.success(f"✅ Mouse movido a {new_pos}")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
                    print(f"❌ Error en prueba: {e}")

        if coord_x != 1884 or coord_y != 979:
            st.session_state.coord_enviar = (coord_x, coord_y)
            st.success(f"✅ Coordenadas personalizadas: ({coord_x}, {coord_y})")
        else:
            st.session_state.coord_enviar = None
            st.info(f"ℹ️ Usando coordenadas predeterminadas: (1884, 979)")

    uploaded_file = st.file_uploader("Subir Excel", type=["xlsx"])

    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file).convert_dtypes()
            st.session_state.df_original = df.copy()
            st.dataframe(df.head(5), height=200)

            # --- 📥 GENERAR EXCEL CON DATOS DE LA BASE ---
            st.divider()
            st.markdown("### 📥 Exportar Datos desde Base de Datos")

            if st.button("🔍 Buscar datos en BD y generar Excel", key="btn_generar_excel"):
                with st.spinner("Buscando datos en la base de datos..."):
                    datos_exportar = []
                    seriales_no_encontrados = []

                    for i, row in df.iterrows():
                        serial = str(row['serial']).strip()
                        datos = buscar_datos_por_serial(serial)

                        if datos:
                            dir_std   = estandarizar_direccion(datos['direccion'] or '')
                            localidad = buscar_localidad(dir_std) if dir_std else None
                            datos_exportar.append({
                                'Serial':    datos['serial'],
                                'Nombre':    datos['nombre'],
                                'Direccion': datos['direccion'],
                                'Localidad': localidad or '',
                                'Telefono':  datos['telefono'],
                            })
                        else:
                            seriales_no_encontrados.append(serial)

                    if datos_exportar:
                        df_export = pd.DataFrame(datos_exportar)
                        st.session_state.df_exportar = df_export

                        st.success(f"✅ Se encontraron {len(datos_exportar)} registros")

                        if seriales_no_encontrados:
                            st.warning(f"⚠️ {len(seriales_no_encontrados)} seriales no encontrados: {', '.join(seriales_no_encontrados[:10])}{'...' if len(seriales_no_encontrados) > 10 else ''}")

                        st.dataframe(df_export, use_container_width=True, hide_index=True)
                    else:
                        st.error("❌ No se encontraron datos en la base de datos")

            # Botón de descarga (separado para que persista)
            if 'df_exportar' in st.session_state and st.session_state.df_exportar is not None:
                from io import BytesIO

                # Crear archivo Excel en memoria
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    st.session_state.df_exportar.to_excel(writer, index=False, sheet_name='Envios')
                output.seek(0)

                st.download_button(
                    label="📥 Descargar Excel",
                    data=output,
                    file_name="envios_datos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            st.divider()

            if st.button("⏳ Iniciar Envíos", key="send_btn"):
                if 'progreso' not in st.session_state:
                    st.session_state.progreso = {
                        'enviados': set(),
                        'fallidos': set(),
                        'actual': 0
                    }
                
                with st.status("📤 Procesando...", expanded=True) as status:
                    df = st.session_state.df_original
                    progress_bar = st.progress(0)
                    
                    for i, row in df.iterrows():
                        if i in st.session_state.progreso['enviados']:
                            continue
                            
                        serial = str(row['serial']).strip()
                        datos = buscar_datos_por_serial(serial)
                        
                        if not datos:
                            st.warning(f"⚠ Serial {serial} no encontrado")
                            st.session_state.progreso['fallidos'].add(i)
                            continue
                            
                        msg = f"""Hola {datos['nombre']}, le informamos sobre su envío {datos['serial']}. Dirección registrada: {datos['direccion']}. ¿Podría confirmar si es correcta?, y cual es el nombre de su localidad?"""
                        
                        if enviar_mensaje_whatsapp(datos['telefono'], msg):
                            st.success(f"✅ Enviado a {datos['nombre']}")
                            st.session_state.progreso['enviados'].add(i)
                        else:
                            st.error(f"❌ Falló {serial}")
                            st.session_state.progreso['fallidos'].add(i)
                            
                        st.session_state.progreso['actual'] = i
                        progress = (i+1)/len(df)
                        progress_bar.progress(min(progress, 1.0))
                        time.sleep(5)
                    
                    status.update(
                        label=f"✅ Completado | Enviados: {len(st.session_state.progreso['enviados'])}",
                        state="complete"
                    )
                    st.balloons()
        
            elif st.button("⏳ Confirmar entregas", key="send_entrega"):
                if 'progreso' not in st.session_state:
                    st.session_state.progreso = {
                        'enviados': set(),
                        'fallidos': set(),
                        'actual': 0
                    }
                
                with st.status("📤 Procesando...", expanded=True) as status:
                    df = st.session_state.df_original
                    progress_bar = st.progress(0)
                    
                    for i, row in df.iterrows():
                        if i in st.session_state.progreso['enviados']:
                            continue
                            
                        serial = str(row['serial']).strip()
                        datos = buscar_datos_por_serial(serial)
                        
                        if not datos:
                            st.warning(f"⚠ Serial {serial} no encontrado")
                            st.session_state.progreso['fallidos'].add(i)
                            continue
                            
                        msg = f"""Hola {datos['nombre']}, le informamos sobre su envío {datos['serial']}. Dirección registrada: {datos['direccion']}. Se encuentra como entregado, nos puede confirmar su entrega?.  Muchas gracias"""
                                                            
                        if enviar_mensaje_whatsapp(datos['telefono'], msg):
                            st.success(f"✅ Enviado a {datos['nombre']}")
                            st.session_state.progreso['enviados'].add(i)
                        else:
                            st.error(f"❌ Falló {serial}")
                            st.session_state.progreso['fallidos'].add(i)
                            
                        st.session_state.progreso['actual'] = i
                        progress = (i+1)/len(df)
                        progress_bar.progress(min(progress, 1.0))
                        time.sleep(5)
                    
                    status.update(
                        label=f"✅ Completado | Enviados: {len(st.session_state.progreso['enviados'])}",
                        state="complete"
                    )
                    st.balloons()
        
        except Exception as e:
            st.error("Error procesando archivo Excel")

if __name__ == "__main__":
    main()
