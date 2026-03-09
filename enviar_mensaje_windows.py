#!/usr/bin/env python3
"""
Script de Windows para enviar mensaje por WhatsApp
Este script se ejecuta en Windows y controla el mouse con PyAutoGUI
Es llamado desde WSL2 para evitar problemas de control de mouse
"""

import sys
import pyautogui as pw
import time
import subprocess
import os
from urllib.parse import quote

# Configurar UTF-8 para evitar errores de codificación en Windows
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Desactivar failsafe
pw.FAILSAFE = False

def enviar_mensaje_whatsapp(numero, mensaje, coord_x=1884, coord_y=979):
    """Envía un mensaje por WhatsApp Web"""
    try:
        # Formatear número
        numero = str(numero).strip()
        if not numero.startswith("+"):
            numero = f"+{numero}"

        print(f"Enviando a {numero}...", flush=True)

        # Construir URL
        mensaje_codificado = quote(mensaje)
        url = f"https://web.whatsapp.com/send?phone={numero}&text={mensaje_codificado}"

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

        # Abrir Chrome maximizado
        subprocess.Popen([
            chrome_path,
            "--start-maximized",
            "--new-window",
            url
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Esperar carga (reducido de 15s a 10s)
        time.sleep(10)

        # Mover y hacer click
        pw.moveTo(coord_x, coord_y, duration=0.3)
        time.sleep(0.3)
        pw.click(coord_x, coord_y)
        time.sleep(2)

        # NO cerrar la pestaña - dejarla abierta para ver el resultado
        # La pestaña se cerrará al inicio del SIGUIENTE envío

        print("OK", flush=True)
        return True

    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        try:
            # Intentar cerrar solo la pestaña de WhatsApp en caso de error
            pw.hotkey('ctrl', 'w')
        except:
            pass
        return False

if __name__ == "__main__":
    # Recibir parámetros desde línea de comandos
    if len(sys.argv) < 3:
        print("Uso: python enviar_mensaje_windows.py <numero> <mensaje> [coord_x] [coord_y]", flush=True)
        sys.exit(1)

    numero = sys.argv[1]
    mensaje = sys.argv[2]
    coord_x = int(sys.argv[3]) if len(sys.argv) > 3 else 1884
    coord_y = int(sys.argv[4]) if len(sys.argv) > 4 else 979

    exito = enviar_mensaje_whatsapp(numero, mensaje, coord_x, coord_y)
    sys.exit(0 if exito else 1)
