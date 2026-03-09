@echo off
echo ============================================================
echo  WhatsApp Sender - Ejecutando Aplicacion
echo ============================================================
echo.

REM Buscar conda en ubicaciones comunes
echo Buscando Conda...

set CONDA_PATH=
if exist "%USERPROFILE%\miniconda3\Scripts\conda.exe" (
    set CONDA_PATH=%USERPROFILE%\miniconda3
    echo Conda encontrado en: %USERPROFILE%\miniconda3
) else if exist "%USERPROFILE%\anaconda3\Scripts\conda.exe" (
    set CONDA_PATH=%USERPROFILE%\anaconda3
    echo Conda encontrado en: %USERPROFILE%\anaconda3
) else if exist "C:\ProgramData\Miniconda3\Scripts\conda.exe" (
    set CONDA_PATH=C:\ProgramData\Miniconda3
    echo Conda encontrado en: C:\ProgramData\Miniconda3
) else if exist "C:\ProgramData\Anaconda3\Scripts\conda.exe" (
    set CONDA_PATH=C:\ProgramData\Anaconda3
    echo Conda encontrado en: C:\ProgramData\Anaconda3
) else if exist "%USERPROFILE%\AppData\Local\miniconda3\Scripts\conda.exe" (
    set CONDA_PATH=%USERPROFILE%\AppData\Local\miniconda3
    echo Conda encontrado en: %USERPROFILE%\AppData\Local\miniconda3
) else if exist "%USERPROFILE%\AppData\Local\anaconda3\Scripts\conda.exe" (
    set CONDA_PATH=%USERPROFILE%\AppData\Local\anaconda3
    echo Conda encontrado en: %USERPROFILE%\AppData\Local\anaconda3
)

if not defined CONDA_PATH (
    echo.
    echo ERROR: No se encontro conda en las ubicaciones comunes
    echo.
    echo SOLUCION:
    echo 1. Abre "Anaconda Prompt" desde el menu inicio
    echo 2. Ejecuta estos comandos:
    echo    cd %CD%
    echo    conda activate carvajal
    echo    streamlit run home.py
    echo.
    pause
    exit /b 1
)

echo.
echo Activando ambiente 'carvajal'...

REM Inicializar conda
call "%CONDA_PATH%\Scripts\activate.bat" "%CONDA_PATH%"
call conda activate carvajal

if errorlevel 1 (
    echo.
    echo ERROR: No se pudo activar el ambiente 'carvajal'
    echo.
    echo Verifica que el ambiente exista con: conda env list
    echo.
    pause
    exit /b 1
)

echo.
echo Ambiente activado correctamente
echo.

REM Verificar que streamlit existe
set STREAMLIT_PATH=%CONDA_PATH%\envs\carvajal\Scripts\streamlit.exe

if not exist "%STREAMLIT_PATH%" (
    echo ERROR: Streamlit no encontrado en el ambiente
    echo Instalando streamlit...
    pip install streamlit
)

echo.
echo Iniciando Streamlit...
echo.
echo ============================================================
echo IMPORTANTE: NO CIERRES ESTA VENTANA
echo Aqui veras los LOGS detallados de cada envio
echo ============================================================
echo.

"%STREAMLIT_PATH%" run home.py

pause
