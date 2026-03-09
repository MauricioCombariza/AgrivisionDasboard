#!/usr/bin/env python3
"""
TEST DE PYAUTOGUI EN WINDOWS
Verifica que el mouse se pueda controlar correctamente
"""

import pyautogui as pw
import time

print("="*60)
print("TEST DE CONTROL DE MOUSE - Windows")
print("="*60)
print()

# Desactivar failsafe
pw.FAILSAFE = False

print("1. Información del sistema:")
screen_width, screen_height = pw.size()
print(f"   Tamaño de pantalla: {screen_width}x{screen_height}")
current_x, current_y = pw.position()
print(f"   Posición actual del mouse: ({current_x}, {current_y})")
print()

print("2. TEST DE MOVIMIENTO")
print("   En 3 segundos moveré el mouse al centro de la pantalla...")
print("   OBSERVA SI EL MOUSE SE MUEVE VISUALMENTE")
print()

for i in range(3, 0, -1):
    print(f"   {i}...")
    time.sleep(1)

center_x = screen_width // 2
center_y = screen_height // 2

print(f"   Moviendo a centro ({center_x}, {center_y})...")
pw.moveTo(center_x, center_y, duration=1)

final_pos = pw.position()
print(f"   ✅ Posición final: {final_pos}")
print()

if final_pos == (center_x, center_y):
    print("   ✅ ÉXITO: El mouse se movió correctamente")
else:
    print(f"   ⚠️ ADVERTENCIA: Se esperaba ({center_x}, {center_y}) pero está en {final_pos}")
print()

print("3. TEST DE MOVIMIENTO A COORDENADAS ESPECÍFICAS")
print("   En 3 segundos moveré el mouse a (960, 1026)")
print("   (Coordenadas del botón de envío de WhatsApp)")
print()

for i in range(3, 0, -1):
    print(f"   {i}...")
    time.sleep(1)

print("   Moviendo a (960, 1026)...")
pw.moveTo(960, 1026, duration=1)

final_pos = pw.position()
print(f"   ✅ Posición final: {final_pos}")
print()

print("4. TEST DE CLICK")
print("   En 3 segundos haré un click en la posición actual...")
print("   (No debería afectar nada, solo es una prueba)")
print()

for i in range(3, 0, -1):
    print(f"   {i}...")
    time.sleep(1)

print("   Haciendo click...")
pw.click()
print("   ✅ Click ejecutado")
print()

print("="*60)
print("RESUMEN DEL TEST")
print("="*60)
print()
print("¿Se movió el mouse visualmente en la pantalla?")
print("  - SI: PyAutoGUI funciona correctamente")
print("  - NO: Hay un problema con PyAutoGUI en tu sistema")
print()
print("Si el mouse SÍ se movió, el problema está en:")
print("  - Las coordenadas del botón de envío")
print("  - Los tiempos de espera")
print("  - WhatsApp Web no está cargado")
print()
print("="*60)
print()

input("Presiona Enter para cerrar...")
