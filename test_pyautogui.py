#!/usr/bin/env python3
"""
Script de prueba para verificar que pyautogui funcione correctamente
"""

import pyautogui as pw
import time

print("="*60)
print("🧪 TEST DE PYAUTOGUI")
print("="*60)

# Desactivar failsafe
pw.FAILSAFE = False

print("\n1️⃣ Información del sistema:")
print(f"   Tamaño de pantalla: {pw.size()}")
print(f"   Posición actual del mouse: {pw.position()}")

print("\n2️⃣ Test de movimiento del mouse:")
print("   En 3 segundos moveré el mouse al centro de la pantalla...")
time.sleep(3)

screen_width, screen_height = pw.size()
center_x = screen_width // 2
center_y = screen_height // 2

print(f"   Moviendo a centro ({center_x}, {center_y})...")
pw.moveTo(center_x, center_y, duration=1)

final_pos = pw.position()
print(f"   ✅ Mouse movido a: {final_pos}")

print("\n3️⃣ Test de movimiento a coordenadas específicas:")
print("   En 3 segundos moveré el mouse a (960, 1026)...")
time.sleep(3)

print("   Moviendo a (960, 1026)...")
pw.moveTo(960, 1026, duration=1)

final_pos = pw.position()
print(f"   ✅ Mouse movido a: {final_pos}")

if final_pos == (960, 1026):
    print("\n✅ ¡PYAUTOGUI FUNCIONA CORRECTAMENTE!")
else:
    print(f"\n⚠️  Advertencia: Se esperaba (960, 1026) pero está en {final_pos}")
    print("   Esto puede deberse a:")
    print("   - Múltiples monitores")
    print("   - Escala de DPI diferente")
    print("   - Zoom del navegador")

print("\n" + "="*60)
print("Test completado")
print("="*60)
