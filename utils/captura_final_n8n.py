# captura_final_autocierre.py
# VERSIÓN CON CIERRE AUTOMÁTICO INMEDIATO

import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from PIL import Image
from io import BytesIO
import os
import time

# --- Configuración (sin cambios) ---
URL_A_ABRIR = "https://web.whatsapp.com/"
CARPETA_DESTINO = os.path.join(os.path.expanduser('~'), 'Downloads')
CALIDAD_JPG = 90
CROP_LEFT = 660
CROP_TOP = 1
CROP_RIGHT = 1864
CROP_BOTTOM = 850

# --- Lógica para obtener el nombre del archivo (sin cambios) ---
nombre_base = None
if len(sys.argv) > 1:
    nombre_base = sys.argv[1]
    print(f"Nombre de archivo recibido desde n8n: '{nombre_base}'")
else:
    print("\nACCIÓN REQUERIDA: Prepara la ventana del navegador.")
    nombre_base = input("Escribe el nombre para el archivo (sin extensión) y presiona Enter para capturar: ")

# --- Opciones y Servicio de Chrome (sin cambios) ---
chrome_exe_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
driver_exe_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chromedriver.exe')
chrome_options = Options()
chrome_options.binary_location = chrome_exe_path
chrome_options.add_argument("--start-maximized")
user_data_dir = os.path.join(os.path.expanduser('~'), 'SeleniumProfiles', 'WhatsApp')
chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
service = Service(executable_path=driver_exe_path)

driver = None
try:
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(URL_A_ABRIR)
    
    if len(sys.argv) > 1:
        print("\nACCIÓN REQUERIDA: Tienes 30 segundos para preparar la ventana de WhatsApp...")
        time.sleep(13)
        print("Tiempo de espera finalizado. Capturando...")

    nombre_archivo_final = f"{nombre_base}.jpg"
    ruta_guardado = os.path.join(CARPETA_DESTINO, nombre_archivo_final)
    
    png_data = driver.get_screenshot_as_png()
    imagen_completa = Image.open(BytesIO(png_data))
    caja_recorte = (CROP_LEFT, CROP_TOP, CROP_RIGHT, CROP_BOTTOM)
    imagen_recortada = imagen_completa.crop(caja_recorte)
    imagen_rgb = imagen_recortada.convert('RGB')
    imagen_rgb.save(ruta_guardado, 'jpeg', quality=CALIDAD_JPG)
    
    print(f"¡Éxito! Captura guardada en: {os.path.abspath(ruta_guardado)}")

except Exception as e:
    print(f"Ocurrió un error: {e}")

finally:
    if driver:
        # --------------------------------------------------------------------------
        # CAMBIO: Hemos eliminado la línea time.sleep(5)
        # --------------------------------------------------------------------------
        print("Cerrando el navegador inmediatamente.")
        driver.quit() # Cierra el navegador y todos los procesos asociados.