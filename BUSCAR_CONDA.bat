@echo off
echo ============================================================
echo  BUSCADOR DE CONDA
echo ============================================================
echo.
echo Buscando instalacion de Conda en tu sistema...
echo.

set FOUND=0

echo Verificando ubicaciones comunes:
echo.

if exist "%USERPROFILE%\miniconda3\Scripts\conda.exe" (
    echo [ENCONTRADO] %USERPROFILE%\miniconda3
    set FOUND=1
)

if exist "%USERPROFILE%\anaconda3\Scripts\conda.exe" (
    echo [ENCONTRADO] %USERPROFILE%\anaconda3
    set FOUND=1
)

if exist "C:\ProgramData\Miniconda3\Scripts\conda.exe" (
    echo [ENCONTRADO] C:\ProgramData\Miniconda3
    set FOUND=1
)

if exist "C:\ProgramData\Anaconda3\Scripts\conda.exe" (
    echo [ENCONTRADO] C:\ProgramData\Anaconda3
    set FOUND=1
)

if exist "%USERPROFILE%\AppData\Local\miniconda3\Scripts\conda.exe" (
    echo [ENCONTRADO] %USERPROFILE%\AppData\Local\miniconda3
    set FOUND=1
)

if exist "%USERPROFILE%\AppData\Local\anaconda3\Scripts\conda.exe" (
    echo [ENCONTRADO] %USERPROFILE%\AppData\Local\anaconda3
    set FOUND=1
)

if %FOUND%==0 (
    echo.
    echo [NO ENCONTRADO] Conda no esta instalado en ubicaciones comunes
    echo.
    echo SOLUCION 1: Busca "Anaconda Prompt" en el menu inicio de Windows
    echo             Si lo encuentras, conda SI esta instalado
    echo.
    echo SOLUCION 2: Instala Miniconda desde:
    echo             https://docs.conda.io/en/latest/miniconda.html
    echo.
)

echo.
echo ============================================================
echo  Verificando PATH
echo ============================================================
echo.

where conda >nul 2>&1
if %errorlevel%==0 (
    echo [OK] Conda esta en el PATH del sistema
    where conda
) else (
    echo [ADVERTENCIA] Conda NO esta en el PATH
    echo.
    echo Esto es normal. Usa "Anaconda Prompt" para ejecutar comandos conda
)

echo.
echo ============================================================
echo.
pause
