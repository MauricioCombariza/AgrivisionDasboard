@echo off
echo ============================================================
echo  VERIFICACION DE SISTEMA - WhatsApp Sender
echo ============================================================
echo.

echo [1] Verificando Conda...
where conda >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Conda NO encontrado
    echo     Instala Anaconda o Miniconda desde:
    echo     https://www.anaconda.com/download
    echo.
    pause
    exit /b 1
) else (
    echo [OK] Conda encontrado
    conda --version
)

echo.
echo [2] Verificando ambiente 'carvajal'...
call conda activate carvajal 2>nul
if %errorlevel% neq 0 (
    echo [X] Ambiente 'carvajal' NO encontrado
    echo     Crea el ambiente primero
    pause
    exit /b 1
) else (
    echo [OK] Ambiente 'carvajal' encontrado
    python --version
)

echo.
echo [3] Verificando Google Chrome...
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    echo [OK] Chrome encontrado
) else if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    echo [OK] Chrome encontrado en Program Files (x86)
) else (
    echo [!] Chrome no encontrado
    echo     Instala Google Chrome
)

echo.
echo [4] Verificando MySQL...
netstat -an | find "3306" >nul
if %errorlevel% neq 0 (
    echo [!] MySQL no esta corriendo (puerto 3306)
    echo     Inicia MySQL Server
) else (
    echo [OK] MySQL esta corriendo
)

echo.
echo [5] Verificando archivos del proyecto...
if exist "pages\wa.py" (
    echo [OK] Archivo principal encontrado
) else (
    echo [X] pages\wa.py NO encontrado
)

echo.
echo [6] Verificando PyAutoGUI...
pip show pyautogui >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] PyAutoGUI no esta instalado
    echo     Ejecuta: 1_INSTALAR_AMBIENTE.bat
) else (
    echo [OK] PyAutoGUI instalado
)

echo.
echo ============================================================
echo  VERIFICACION COMPLETADA
echo ============================================================
echo.
echo Siguiente paso:
echo   - Si falta PyAutoGUI: 1_INSTALAR_AMBIENTE.bat
echo   - Si todo OK: 2_EJECUTAR_APP.bat
echo.
pause
