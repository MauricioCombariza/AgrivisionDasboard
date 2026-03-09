@echo off
echo ============================================================
echo  Instalando Selenium en Windows (ambiente carvajal)
echo ============================================================
echo.

REM Buscar conda
set CONDA_PATH=
if exist "%USERPROFILE%\miniconda3\Scripts\conda.exe" (
    set CONDA_PATH=%USERPROFILE%\miniconda3
) else if exist "%USERPROFILE%\anaconda3\Scripts\conda.exe" (
    set CONDA_PATH=%USERPROFILE%\anaconda3
)

if not defined CONDA_PATH (
    echo ERROR: No se encontro conda
    pause
    exit /b 1
)

echo Activando ambiente carvajal...
call "%CONDA_PATH%\Scripts\activate.bat" "%CONDA_PATH%"
call conda activate carvajal

echo.
echo Instalando Selenium y Pillow...
pip install selenium pillow

echo.
echo ============================================================
echo  Instalacion completada!
echo ============================================================
echo.
pause
