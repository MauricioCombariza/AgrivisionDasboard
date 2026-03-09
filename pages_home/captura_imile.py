# ----------------------------
# 📦 IMPORTACIONES
# ----------------------------
import streamlit as st
import os
import time
import subprocess
import platform
import json
import mysql.connector
from dotenv import load_dotenv

# ----------------------------
# ⚙ CONFIGURACIÓN INICIAL
# ----------------------------


# Cargar variables de entorno
load_dotenv()

# Credenciales de iMile desde .env
IMILE_USER = os.getenv("IMILE_USER")
IMILE_PASS = os.getenv("IMILE_PASS")

# ----------------------------
# 🗃 MÓDULO MYSQL
# ----------------------------
def conectar_mysql():
    """Conexión con pool de conexiones"""
    try:
        import platform
        is_wsl = 'microsoft' in platform.uname().release.lower()

        if is_wsl:
            import subprocess as sp
            try:
                result = sp.run(
                    ["ip", "route", "show"],
                    capture_output=True,
                    text=True
                )
                windows_ip = None
                for line in result.stdout.split('\n'):
                    if 'default' in line:
                        windows_ip = line.split()[2]
                        break

                if windows_ip:
                    try:
                        return mysql.connector.connect(
                            host=windows_ip,
                            user="root",
                            password=os.environ.get("DB_PASSWORD", ""),
                            database="imile",
                            pool_size=3
                        )
                    except:
                        pass
            except:
                pass

        return mysql.connector.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database="imile",
            pool_size=3
        )
    except Exception as e:
        st.error("Error de conexión a MySQL")
        return None

def buscar_datos_por_serial(serial):
    """Búsqueda con manejo completo de errores"""
    conn = None
    try:
        conn = conectar_mysql()
        if not conn:
            return None

        with conn.cursor(dictionary=True) as cursor:
            query = "SELECT nombre, direccion, telefono, serial FROM paquetes WHERE serial = %s LIMIT 1"
            cursor.execute(query, (str(serial).strip(),))
            return cursor.fetchone()

    except Exception as e:
        st.error("Error al buscar datos")
        return None
    finally:
        if conn and conn.is_connected():
            conn.close()

# ----------------------------
# 📸 MÓDULO CAPTURA Y SUBIDA
# ----------------------------
def ejecutar_proceso_imile(serial, localidad):
    """Ejecuta el proceso completo: captura + subida"""
    try:
        # PASO 0: Buscar datos del serial en MySQL
        st.info("🔍 Buscando datos del serial en base de datos...")
        datos = buscar_datos_por_serial(serial)

        if not datos:
            st.error(f"⚠️ Serial {serial} no encontrado en la base de datos")
            return False

        telefono = datos['telefono']
        nombre = datos.get('nombre', 'Cliente')

        st.success(f"✅ Datos encontrados: {nombre} - {telefono}")
        st.info(f"📍 Localidad destino: {localidad}")

        # Detectar si estamos en WSL2
        is_wsl = 'microsoft' in platform.uname().release.lower()

        if is_wsl:
            # === MODO WSL2: Llamar scripts de Windows ===

            # Buscar Python de Windows
            python_win_paths = [
                "/mnt/c/Users/mcomb/miniconda3/envs/carvajal/python.exe",
                "/mnt/c/Users/mcomb/anaconda3/envs/carvajal/python.exe"
            ]

            python_win = None
            for path in python_win_paths:
                if os.path.exists(path):
                    python_win = path.replace('/mnt/c/', 'C:\\\\')
                    break

            if not python_win:
                st.error("Python de Windows no encontrado")
                return False

            # Rutas de scripts
            script_captura = "/mnt/c/Users/mcomb/Desktop/Carvajal/python/dashboard/captura_imile_windows.py"
            script_subida = "/mnt/c/Users/mcomb/Desktop/Carvajal/python/dashboard/subir_imile_windows.py"

            script_captura_win = script_captura.replace('/mnt/c/', 'C:\\\\').replace('/', '\\\\')
            script_subida_win = script_subida.replace('/mnt/c/', 'C:\\\\').replace('/', '\\\\')

            powershell_path = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"

            # PASO 1: Captura de pantalla
            st.info(f"📸 Abriendo WhatsApp con {nombre} ({telefono})...")
            st.warning("⏳ El mensaje se enviará automáticamente y luego capturará la pantalla")

            result_captura = subprocess.run([
                powershell_path, "-Command",
                f'[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; & "{python_win}" "{script_captura_win}" "{serial}" "{telefono}" "{localidad}"'
            ], capture_output=True)

            # Mostrar salida completa para debug
            try:
                stdout = result_captura.stdout.decode('utf-8', errors='replace')
                stderr = result_captura.stderr.decode('utf-8', errors='replace')

                if stdout:
                    st.text("Salida del script:")
                    st.code(stdout)

                if stderr:
                    st.text("Errores del script:")
                    st.code(stderr)
            except:
                pass

            if result_captura.returncode != 0:
                st.error(f"Error en captura de pantalla (código: {result_captura.returncode})")
                return False

            # Verificar resultado de captura
            try:
                output = result_captura.stdout.decode('utf-8', errors='replace')
                # Buscar el JSON en la salida
                for line in output.split('\n'):
                    if line.strip().startswith('{'):
                        resultado = json.loads(line.strip())
                        if resultado.get('status') == 'error':
                            st.error(f"Error: {resultado.get('error', 'Error desconocido')}")
                            return False
            except:
                pass

            st.success("✅ Captura completada")

            # PASO 2: Subir imagen
            st.info("📤 Subiendo imagen a iMile...")

            result_subida = subprocess.run([
                powershell_path, "-Command",
                f'[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; & "{python_win}" "{script_subida_win}" "{serial}"'
            ], capture_output=True)

            # Mostrar salida completa para debug de subida
            try:
                stdout_subida = result_subida.stdout.decode('utf-8', errors='replace')
                stderr_subida = result_subida.stderr.decode('utf-8', errors='replace')

                if stdout_subida:
                    st.text("Salida del script de subida:")
                    st.code(stdout_subida)

                if stderr_subida:
                    st.text("Errores del script de subida:")
                    st.code(stderr_subida)
            except:
                pass

            if result_subida.returncode != 0:
                st.error(f"Error al subir imagen (código: {result_subida.returncode})")
                return False

            # Verificar resultado de subida
            try:
                output = result_subida.stdout.decode('utf-8', errors='replace')
                for line in output.split('\n'):
                    if line.strip().startswith('{'):
                        resultado = json.loads(line.strip())
                        if resultado.get('status') == 'error':
                            st.error(f"Error: {resultado.get('error', 'Error desconocido')}")
                            return False
            except:
                pass

            st.success("✅ Imagen subida exitosamente")
            return True

        else:
            # === MODO WINDOWS NATIVO ===
            st.error("Modo Windows nativo no implementado aún. Usa WSL2.")
            return False

    except Exception as e:
        st.error("Error en el proceso")
        return False

# ----------------------------
# 🖥 INTERFAZ PRINCIPAL
# ----------------------------
def main():
    st.title("📸 Captura Automática iMile")

    st.write("""
    Esta herramienta automatiza el proceso de:
    1. Buscar datos del serial en MySQL
    2. Abrir WhatsApp con el contacto
    3. Enviar mensaje automático con la localidad
    4. Capturar pantalla de WhatsApp Web
    5. Subir la imagen a iMile
    """)

    # Campos de entrada
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        serial = st.text_input(
            "Número de Serial",
            placeholder="Ingresa el serial del paquete",
            help="Serial de devolución de iMile"
        )

    with col2:
        localidad = st.text_input(
            "Localidad Destino",
            placeholder="Ej: Kennedy, Suba, Engativá",
            help="Localidad a donde se reenvía el paquete"
        )

    with col3:
        st.write("")
        st.write("")
        ejecutar = st.button("🚀 Ejecutar", type="primary", use_container_width=True)

    # Información del sistema
    with st.expander("ℹ️ Información del Sistema"):
        is_wsl = 'microsoft' in platform.uname().release.lower()
        st.write(f"**Sistema operativo:** {'WSL2 (Linux en Windows)' if is_wsl else 'Windows Nativo'}")
        st.write(f"**Usuario iMile:** {IMILE_USER}")

        # Verificar si existe chromedriver
        chromedriver_path = "C:\\DriverChrome\\chromedriver.exe"
        wsl_path = chromedriver_path.replace('C:\\', '/mnt/c/').replace('\\', '/')
        if os.path.exists(wsl_path):
            st.success("✅ ChromeDriver encontrado")
        else:
            st.warning(f"⚠️ ChromeDriver no encontrado en {chromedriver_path}")

    # Ejecutar proceso
    if ejecutar:
        if not serial or serial.strip() == "":
            st.warning("⚠️ Por favor ingresa un número de serial")
        elif not localidad or localidad.strip() == "":
            st.warning("⚠️ Por favor ingresa la localidad destino")
        else:
            serial = serial.strip()
            localidad = localidad.strip()

            with st.status("🔄 Procesando...", expanded=True) as status:
                if ejecutar_proceso_imile(serial, localidad):
                    status.update(
                        label=f"✅ Proceso completado para serial {serial}",
                        state="complete"
                    )
                    st.balloons()
                else:
                    status.update(
                        label="❌ Proceso fallido",
                        state="error"
                    )

    # Historial de capturas
    st.divider()
    st.subheader("📁 Capturas Recientes")

    download_folder = os.path.join(os.path.expanduser('~'), 'Downloads')
    if os.path.exists(download_folder):
        capturas = [f for f in os.listdir(download_folder) if f.startswith('captura_') and f.endswith('.png')]
        capturas.sort(key=lambda x: os.path.getmtime(os.path.join(download_folder, x)), reverse=True)

        if capturas:
            for captura in capturas[:5]:  # Mostrar últimas 5
                file_path = os.path.join(download_folder, captura)
                file_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(file_path)))
                st.text(f"📄 {captura} - {file_time}")
        else:
            st.info("No hay capturas recientes")
    else:
        st.info("Carpeta Downloads no encontrada")

if __name__ == "__main__":
    main()
