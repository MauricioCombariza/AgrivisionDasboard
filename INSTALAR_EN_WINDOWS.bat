@echo off
echo ============================================================
echo  INSTALACION DE AMBIENTE CARVAJAL EN WINDOWS
echo ============================================================
echo.
echo Este script creara el ambiente 'carvajal' en Windows conda
echo e instalara todas las dependencias necesarias.
echo.
echo Tiempo estimado: 3-5 minutos
echo.
pause

echo.
echo [1/4] Creando ambiente 'carvajal' con Python 3.12...
echo.
call conda create -n carvajal python=3.12 -y

if errorlevel 1 (
    echo.
    echo ERROR: No se pudo crear el ambiente
    echo Verifica que conda este instalado correctamente
    pause
    exit /b 1
)

echo.
echo [2/4] Activando ambiente...
echo.
call conda activate carvajal

if errorlevel 1 (
    echo.
    echo ERROR: No se pudo activar el ambiente
    pause
    exit /b 1
)

echo.
echo [3/4] Instalando dependencias principales...
echo.
pip install streamlit pandas pyautogui mysql-connector-python openpyxl pillow numpy

if errorlevel 1 (
    echo.
    echo ERROR: No se pudieron instalar las dependencias
    pause
    exit /b 1
)

echo.
echo [4/4] Verificando instalacion...
echo.
echo Python:
python --version
echo.
echo Paquetes instalados:
pip list | findstr "streamlit pandas pyautogui mysql"

echo.
echo ============================================================
echo  INSTALACION COMPLETADA EXITOSAMENTE!
echo ============================================================
echo.
echo El ambiente 'carvajal' ha sido creado en Windows conda
echo.
echo Para ejecutar la aplicacion, usa:
echo    2_EJECUTAR_APP.bat
echo.
echo O ejecuta manualmente:
echo    conda activate carvajal
echo    streamlit run pages\wa.py
echo.
pause
