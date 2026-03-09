@echo off
echo ============================================================
echo  INSTALACION DE AMBIENTE CARVAJAL - WhatsApp Sender
echo ============================================================
echo.

echo Verificando si el ambiente 'carvajal' existe...
call conda activate carvajal 2>nul

if errorlevel 1 (
    echo.
    echo El ambiente 'carvajal' NO existe en Windows conda
    echo.
    echo CREANDO AMBIENTE NUEVO...
    echo.

    echo [1/4] Creando ambiente con Python 3.12...
    call conda create -n carvajal python=3.12 -y

    echo.
    echo [2/4] Activando ambiente...
    call conda activate carvajal

    echo.
    echo [3/4] Instalando dependencias...
    pip install streamlit pandas pyautogui mysql-connector-python openpyxl pillow numpy

    echo.
    echo [4/4] Verificando instalacion...
) else (
    echo.
    echo El ambiente 'carvajal' ya existe
    echo.
    echo Verificando dependencias...
    pip install --upgrade pyautogui pillow
)

echo.
echo Python:
python --version
echo.
echo Paquetes instalados:
pip list | findstr "streamlit pandas pyautogui mysql"

echo.
echo ============================================================
echo  INSTALACION COMPLETADA!
echo ============================================================
echo.
echo Para ejecutar la aplicacion, usa: 2_EJECUTAR_APP.bat
echo.
pause
