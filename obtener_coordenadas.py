#!/usr/bin/env python3
"""
Script de ayuda para obtener las coordenadas del botón de envío de WhatsApp Web
Instrucciones:
1. Ejecuta este script: python obtener_coordenadas.py
2. Abre WhatsApp Web en Chrome MAXIMIZADO
3. Mueve el mouse sobre el botón de envío (flecha verde)
4. Presiona Ctrl+C cuando estés sobre el botón
5. Las coordenadas se guardarán automáticamente
"""

import pyautogui as pw
import time

# Desactivar failsafe
pw.FAILSAFE = False

print("="*60)
print("🎯 DETECTOR DE COORDENADAS - WhatsApp Web")
print("="*60)
print()
print("INSTRUCCIONES:")
print()
print("1. Abre Chrome")
print("2. Ve a: https://web.whatsapp.com")
print("3. MAXIMIZA Chrome (presiona F11 o botón maximizar)")
print("4. Presiona Ctrl+0 para zoom al 100%")
print("5. Abre cualquier chat")
print("6. Escribe algo en el cuadro de texto")
print("7. Verás aparecer el BOTÓN DE ENVÍO (flecha verde)")
print()
print("-"*60)
print("Esperando 10 segundos para que prepares WhatsApp Web...")
print("-"*60)
print()

for i in range(10, 0, -1):
    print(f"Comenzando en {i} segundos...", end='\r')
    time.sleep(1)

print()
print("="*60)
print("✅ ¡LISTO! Ahora mueve el mouse al botón de envío...")
print("="*60)
print()
print("Cuando el mouse esté sobre el BOTÓN DE ENVÍO (flecha verde),")
print("presiona Ctrl+C en esta ventana")
print()
print("Posición actual del mouse:")
print()

try:
    while True:
        x, y = pw.position()
        screen_width, screen_height = pw.size()
        # Mostrar con formato más visual
        print(f"\r   X = {x:4d}  |  Y = {y:4d}  |  Pantalla: {screen_width}x{screen_height}   ", end="", flush=True)
        time.sleep(0.1)
except KeyboardInterrupt:
    x, y = pw.position()
    print("\n\n" + "="*60)
    print("✅ COORDENADAS GUARDADAS:")
    print("="*60)
    print(f"   Coordenada X: {x}")
    print(f"   Coordenada Y: {y}")
    print("="*60)
    print()
    print("📝 SIGUIENTE PASO:")
    print()
    print("1. Anota estos valores:")
    print(f"   X = {x}")
    print(f"   Y = {y}")
    print()
    print("2. Abre la aplicación de Streamlit")
    print()
    print("3. Despliega 'Configuración Avanzada'")
    print()
    print("4. Ingresa:")
    print(f"   Coordenada X: {x}")
    print(f"   Coordenada Y: {y}")
    print()
    print("5. Click en 'Probar Posición' para verificar")
    print()
    print("6. Si el mouse va al botón correcto, intenta enviar")
    print()
    print("="*60)
    print()
    input("Presiona Enter para cerrar...")
