#!/usr/bin/env python3
"""
Script de Windows para capturar pantalla de WhatsApp Web
Se ejecuta desde Windows usando PyAutoGUI (sin Selenium)
"""

import sys
import os
import time
import json
import subprocess
import pyautogui as pw
from PIL import Image
from urllib.parse import quote

# Configurar UTF-8 para salida
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Configuración de PyAutoGUI
pw.FAILSAFE = False

def capturar_whatsapp(serial, telefono, localidad):
    """Captura pantalla de WhatsApp Web y la recorta"""
    try:
        print(f"Capturando WhatsApp para serial {serial}...", flush=True)

        download_folder = os.path.join(os.environ["USERPROFILE"], "Downloads")
        file_path = os.path.join(download_folder, f"captura_{serial}.png")

        # Formatear número de teléfono
        telefono = str(telefono).strip()
        if not telefono.startswith("+"):
            telefono = f"+{telefono}"

        # Construir mensaje con la localidad
        mensaje = f"Muchas gracias. Debido al codigo postal ingresado al momento del pedido de su paquete, Este salio hacia la localidad de barrios unidos.\nYa hacemos el reenvio hacia la empresa dedicada a distribuir su localidad, {localidad}."

        # URL de WhatsApp con el número y mensaje
        mensaje_codificado = quote(mensaje)
        url = f"https://web.whatsapp.com/send?phone={telefono}&text={mensaje_codificado}"

        # Buscar Chrome
        chrome_paths = [
            "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
        ]

        chrome_path = None
        for path in chrome_paths:
            if os.path.exists(path):
                chrome_path = path
                break

        if not chrome_path:
            print("ERROR: Chrome no encontrado", flush=True)
            return False

        print(f"Abriendo Chrome con {telefono}...", flush=True)

        # Abrir Chrome maximizado
        subprocess.Popen([
            chrome_path,
            "--start-maximized",
            "--new-window",
            url
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Esperar carga (optimizado)
        print("Esperando a que cargue WhatsApp...", flush=True)
        time.sleep(10)  # Optimizado: 15s → 10s

        # Enviar mensaje automáticamente (click en botón enviar)
        coord_enviar_x = 1884
        coord_enviar_y = 979

        print("Enviando mensaje automáticamente...", flush=True)
        pw.moveTo(coord_enviar_x, coord_enviar_y, duration=0.2)  # Optimizado: 0.3s → 0.2s
        time.sleep(0.2)  # Optimizado: 0.3s → 0.2s
        pw.click(coord_enviar_x, coord_enviar_y)

        # Esperar que se envíe el mensaje (optimizado)
        print("Mensaje enviado. Esperando para capturar...", flush=True)
        time.sleep(3)  # Optimizado: 5s → 3s

        # Capturar pantalla con PyAutoGUI
        print("Capturando pantalla...", flush=True)
        screenshot = pw.screenshot()
        screenshot.save(file_path)

        # Recortar imagen (eliminar barra lateral izquierda y barras superior/inferior)
        print("Recortando imagen...", flush=True)
        img = Image.open(file_path)
        w, h = img.size
        img_recortada = img.crop((700, 150, w, h - 70))
        img_recortada.save(file_path)

        # Cerrar WhatsApp después de capturar
        print("Cerrando WhatsApp...", flush=True)
        pw.hotkey('ctrl', 'w')
        time.sleep(0.3)  # Optimizado

        print(json.dumps({
            "status": "success",
            "file": file_path,
            "serial": serial
        }), flush=True)

        return True

    except Exception as e:
        print(json.dumps({
            "status": "error",
            "error": str(e),
            "serial": serial
        }), flush=True)

        try:
            # Intentar cerrar solo la pestaña de WhatsApp en caso de error
            pw.hotkey('ctrl', 'w')
        except:
            pass

        return False

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python captura_imile_windows.py <serial> <telefono> <localidad>", flush=True)
        sys.exit(1)

    serial = sys.argv[1]
    telefono = sys.argv[2]
    localidad = sys.argv[3]
    exito = capturar_whatsapp(serial, telefono, localidad)
    sys.exit(0 if exito else 1)
