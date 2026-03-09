@echo off
echo ====================================
echo Instalando python-dotenv en Windows
echo ====================================
echo.

REM Buscar Python en conda
set PYTHON_PATH=

if exist "C:\Users\mcomb\miniconda3\envs\carvajal\python.exe" (
    set PYTHON_PATH=C:\Users\mcomb\miniconda3\envs\carvajal\python.exe
) else if exist "C:\Users\mcomb\anaconda3\envs\carvajal\python.exe" (
    set PYTHON_PATH=C:\Users\mcomb\anaconda3\envs\carvajal\python.exe
) else (
    echo ERROR: Python no encontrado
    pause
    exit /b 1
)

echo Python encontrado: %PYTHON_PATH%
echo.
echo Instalando python-dotenv...
echo.

"%PYTHON_PATH%" -m pip install python-dotenv

echo.
echo ====================================
echo Instalacion completada
echo ====================================
echo.
pause
