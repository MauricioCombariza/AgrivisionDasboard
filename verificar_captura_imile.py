#!/usr/bin/env python3
"""
Script de verificación para la automatización de captura iMile
Verifica que todos los requisitos estén instalados correctamente
"""

import os
import sys
import platform

def verificar_requisitos():
    """Verifica todos los requisitos para la automatización"""

    print("=" * 60)
    print("VERIFICACIÓN DE REQUISITOS - CAPTURA IMILE")
    print("=" * 60)
    print()

    errores = []
    warnings = []

    # 1. Detectar sistema operativo
    is_wsl = 'microsoft' in platform.uname().release.lower()
    print(f"✓ Sistema operativo: {'WSL2' if is_wsl else 'Windows nativo'}")
    print()

    # 2. Verificar Python de Windows (solo en WSL2)
    if is_wsl:
        print("--- Verificación de Python de Windows ---")
        python_win_paths = [
            "/mnt/c/Users/mcomb/miniconda3/envs/carvajal/python.exe",
            "/mnt/c/Users/mcomb/anaconda3/envs/carvajal/python.exe"
        ]

        python_win = None
        for path in python_win_paths:
            if os.path.exists(path):
                python_win = path
                print(f"✓ Python de Windows encontrado: {path}")
                break

        if not python_win:
            errores.append("Python de Windows no encontrado")
            print("✗ Python de Windows NO encontrado")
        print()

    # 3. Verificar ChromeDriver
    print("--- Verificación de ChromeDriver ---")
    chromedriver_paths = [
        "/mnt/c/DriverChrome/chromedriver.exe" if is_wsl else "C:\\DriverChrome\\chromedriver.exe"
    ]

    chromedriver_found = False
    for path in chromedriver_paths:
        if os.path.exists(path):
            print(f"✓ ChromeDriver encontrado: {path}")
            chromedriver_found = True
            break

    if not chromedriver_found:
        errores.append("ChromeDriver no encontrado en C:\\DriverChrome\\chromedriver.exe")
        print("✗ ChromeDriver NO encontrado")
    print()

    # 4. Verificar perfil de Chrome
    print("--- Verificación de Perfil de Chrome ---")
    profile_path = "/mnt/c/Users/mcomb/ChromeSeleniumProfile" if is_wsl else "C:\\Users\\mcomb\\ChromeSeleniumProfile"

    if os.path.exists(profile_path):
        print(f"✓ Perfil de Chrome encontrado: {profile_path}")
    else:
        warnings.append(f"Perfil de Chrome no encontrado: {profile_path}")
        print(f"⚠ Perfil de Chrome NO encontrado: {profile_path}")
        print("  (Se creará automáticamente la primera vez)")
    print()

    # 5. Verificar scripts de Windows
    print("--- Verificación de Scripts de Windows ---")
    scripts_dir = "/mnt/c/Users/mcomb/Desktop/Carvajal/python/dashboard" if is_wsl else "C:\\Users\\mcomb\\Desktop\\Carvajal\\python\\dashboard"

    scripts = [
        "captura_imile_windows.py",
        "subir_imile_windows.py"
    ]

    for script in scripts:
        script_path = os.path.join(scripts_dir, script)
        if os.path.exists(script_path):
            print(f"✓ {script} encontrado")
        else:
            errores.append(f"Script {script} no encontrado")
            print(f"✗ {script} NO encontrado")
    print()

    # 6. Verificar página de Streamlit
    print("--- Verificación de Página de Streamlit ---")
    pages_dir = os.path.join(scripts_dir, "pages")
    captura_page = os.path.join(pages_dir, "captura_imile.py")

    if os.path.exists(captura_page):
        print(f"✓ Página de Streamlit encontrada: captura_imile.py")
    else:
        errores.append("Página de Streamlit captura_imile.py no encontrada")
        print("✗ Página de Streamlit NO encontrada")
    print()

    # 7. Verificar carpeta Downloads
    print("--- Verificación de Carpeta Downloads ---")
    downloads_folder = os.path.expanduser('~/Downloads')

    if os.path.exists(downloads_folder):
        print(f"✓ Carpeta Downloads encontrada: {downloads_folder}")
    else:
        warnings.append(f"Carpeta Downloads no encontrada: {downloads_folder}")
        print(f"⚠ Carpeta Downloads NO encontrada")
    print()

    # 8. Verificar librerías de Python
    print("--- Verificación de Librerías de Python ---")
    try:
        import selenium
        print(f"✓ Selenium instalado (versión {selenium.__version__})")
    except ImportError:
        warnings.append("Selenium no instalado en WSL2 (no es crítico si usas WSL2)")
        print("⚠ Selenium NO instalado en WSL2")

    try:
        import streamlit
        print(f"✓ Streamlit instalado")
    except ImportError:
        errores.append("Streamlit no instalado")
        print("✗ Streamlit NO instalado")

    try:
        from PIL import Image
        print(f"✓ Pillow instalado")
    except ImportError:
        warnings.append("Pillow no instalado (requerido para recorte de imágenes)")
        print("⚠ Pillow NO instalado")

    print()

    # Resumen
    print("=" * 60)
    print("RESUMEN")
    print("=" * 60)

    if not errores and not warnings:
        print("✅ ¡Todo listo! Todos los requisitos están instalados.")
        print()
        print("Para ejecutar:")
        print("  ./run_wsl.sh")
        print("  Luego abre la página 'Captura iMile' en el navegador")
        return True

    if errores:
        print(f"❌ Se encontraron {len(errores)} errores críticos:")
        for error in errores:
            print(f"  - {error}")
        print()

    if warnings:
        print(f"⚠️  Se encontraron {len(warnings)} advertencias:")
        for warning in warnings:
            print(f"  - {warning}")
        print()

    print("Revisa la documentación en CAPTURA_IMILE.md para más detalles.")

    return len(errores) == 0

if __name__ == "__main__":
    exito = verificar_requisitos()
    sys.exit(0 if exito else 1)
