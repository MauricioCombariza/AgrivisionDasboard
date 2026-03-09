#!/usr/bin/env python3
"""
TEST DE ENVÍO SIMPLIFICADO
Simula el proceso de envío paso por paso con pausas para observar
"""

import pyautogui as pw
import time
import subprocess
import os

print("="*60)
print("TEST DE ENVÍO DE WHATSAPP - PASO POR PASO")
print("="*60)
print()

# Desactivar failsafe
pw.FAILSAFE = False

# Configuración
numero = "+573001234567"  # Cambia esto por un número de prueba
mensaje = "Hola, este es un mensaje de prueba desde Python"

print("INSTRUCCIONES:")
print("1. Asegúrate de estar logueado en WhatsApp Web en Chrome")
print("2. Este script abrirá Chrome con WhatsApp Web")
print("3. Esperará 20 segundos")
print("4. Intentará hacer click en el botón de envío")
print("5. OBSERVA cada paso en la pantalla")
print()
input("Presiona Enter cuando estés listo...")
print()

# Buscar Chrome
print("[1/6] Buscando Google Chrome...")
chrome_path = None
posibles_rutas = [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
]

for ruta in posibles_rutas:
    if os.path.exists(ruta):
        chrome_path = ruta
        print(f"✅ Chrome encontrado: {chrome_path}")
        break

if not chrome_path:
    print("❌ ERROR: No se encontró Chrome")
    input("Presiona Enter para salir...")
    exit(1)

print()

# Construir URL
from urllib.parse import quote
mensaje_codificado = quote(mensaje)
url = f"https://web.whatsapp.com/send?phone={numero}&text={mensaje_codificado}"

print(f"[2/6] Abriendo WhatsApp Web...")
print(f"   Número: {numero}")
print(f"   URL: {url[:80]}...")
print()

# Abrir Chrome
subprocess.Popen([
    chrome_path,
    "--start-maximized",
    "--new-window",
    url
])

print("✅ Chrome abierto")
print()

# Esperar carga
print("[3/6] Esperando 20 segundos para que cargue WhatsApp Web...")
print("   ASEGÚRATE DE QUE WHATSAPP WEB ESTÉ CARGADO")
print()

for i in range(20, 0, -1):
    print(f"   {i} segundos restantes...", end='\r')
    time.sleep(1)

print()
print("✅ Espera completada")
print()

# Obtener info de pantalla
print("[4/6] Información de pantalla:")
screen_width, screen_height = pw.size()
print(f"   Tamaño: {screen_width}x{screen_height}")
current_pos = pw.position()
print(f"   Mouse actual: {current_pos}")
print()

# Coordenadas del botón
send_x = 960
send_y = 1026

print(f"[5/6] Moviendo mouse a botón de envío ({send_x}, {send_y})...")
print("   OBSERVA SI EL MOUSE SE MUEVE")
print()

pw.moveTo(send_x, send_y, duration=1)
time.sleep(1)

new_pos = pw.position()
print(f"✅ Mouse movido a: {new_pos}")
print()

if new_pos != (send_x, send_y):
    print(f"⚠️ ADVERTENCIA: El mouse no está exactamente en ({send_x}, {send_y})")
    print(f"   Está en {new_pos}")
    print()

print("[6/6] Haciendo click en botón de envío...")
print("   OBSERVA SI HACE CLICK")
print()

input("Presiona Enter para hacer el click...")

pw.click(send_x, send_y)
print("✅ Click ejecutado")
print()

time.sleep(3)

print("="*60)
print("TEST COMPLETADO")
print("="*60)
print()
print("PREGUNTAS:")
print("1. ¿Se abrió Chrome con WhatsApp Web? (SÍ/NO)")
print("2. ¿Se cargó el chat correctamente? (SÍ/NO)")
print("3. ¿Viste el mouse moverse? (SÍ/NO)")
print("4. ¿Se hizo click en el botón de envío? (SÍ/NO)")
print("5. ¿Se envió el mensaje? (SÍ/NO)")
print()
print("Si el mouse NO se movió:")
print("  - PyAutoGUI tiene un problema")
print()
print("Si el mouse SÍ se movió pero NO hizo click en el botón:")
print("  - Las coordenadas están mal")
print("  - Ejecuta: python obtener_coordenadas.py")
print()
print("Si hizo click pero no pasó nada:")
print("  - WhatsApp Web no estaba cargado completamente")
print("  - Aumenta el tiempo de espera")
print()

# Cerrar Chrome
print("Cerrando pestaña en 3 segundos...")
time.sleep(3)
pw.hotkey('ctrl', 'w')

print()
input("Presiona Enter para cerrar...")
