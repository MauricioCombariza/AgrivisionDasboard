# ============================================================
# WhatsApp Sender - Ejecutar con PowerShell
# ============================================================

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " WhatsApp Sender - Iniciando..." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Cambiar a la carpeta del script
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "Carpeta actual: $ScriptDir" -ForegroundColor Yellow
Write-Host ""

# Buscar instalación de conda/miniconda
Write-Host "Buscando conda..." -ForegroundColor Yellow

$condaPaths = @(
    "$env:USERPROFILE\miniconda3",
    "$env:USERPROFILE\anaconda3",
    "$env:USERPROFILE\AppData\Local\miniconda3",
    "$env:USERPROFILE\AppData\Local\anaconda3",
    "C:\ProgramData\Miniconda3",
    "C:\ProgramData\Anaconda3"
)

$condaRoot = $null
foreach ($path in $condaPaths) {
    if (Test-Path "$path\Scripts\conda.exe") {
        $condaRoot = $path
        Write-Host "✓ Conda encontrado: $path" -ForegroundColor Green
        break
    }
}

if (-not $condaRoot) {
    Write-Host ""
    Write-Host "ERROR: No se encontro conda" -ForegroundColor Red
    Write-Host ""
    Write-Host "Soluciones:" -ForegroundColor Yellow
    Write-Host "  1. Abre 'Anaconda Prompt' y ejecuta:" -ForegroundColor White
    Write-Host "     cd $ScriptDir" -ForegroundColor Cyan
    Write-Host "     conda activate carvajal" -ForegroundColor Cyan
    Write-Host "     streamlit run home.py" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  2. O ejecuta el archivo .bat:" -ForegroundColor White
    Write-Host "     2_EJECUTAR_APP.bat" -ForegroundColor Cyan
    Write-Host ""
    Read-Host "Presiona Enter para salir"
    exit 1
}

Write-Host ""

# Buscar ambiente carvajal
$envPath = "$condaRoot\envs\carvajal"
if (-not (Test-Path $envPath)) {
    Write-Host "ERROR: Ambiente 'carvajal' no encontrado" -ForegroundColor Red
    Write-Host ""
    Write-Host "Ejecuta primero: 1_INSTALAR_AMBIENTE.bat" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Presiona Enter para salir"
    exit 1
}

Write-Host "✓ Ambiente 'carvajal' encontrado" -ForegroundColor Green
Write-Host ""

# Buscar ejecutables
$pythonExe = "$envPath\python.exe"
$streamlitExe = "$envPath\Scripts\streamlit.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "ERROR: Python no encontrado en el ambiente" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $streamlitExe)) {
    Write-Host "ERROR: Streamlit no encontrado" -ForegroundColor Red
    Write-Host "Instalando streamlit..." -ForegroundColor Yellow
    & "$envPath\Scripts\pip.exe" install streamlit
    if (-not (Test-Path $streamlitExe)) {
        Write-Host "ERROR: No se pudo instalar streamlit" -ForegroundColor Red
        exit 1
    }
}

Write-Host "✓ Streamlit encontrado" -ForegroundColor Green
Write-Host ""

# Ejecutar Streamlit
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Iniciando Streamlit..." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "IMPORTANTE: NO CIERRES ESTA VENTANA" -ForegroundColor Magenta
Write-Host "Aqui veras los LOGS de cada envio" -ForegroundColor Magenta
Write-Host ""
Write-Host "Para detener: Presiona Ctrl+C" -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Ejecutar streamlit
& $streamlitExe run home.py

Write-Host ""
Write-Host "Streamlit cerrado" -ForegroundColor Yellow
Read-Host "Presiona Enter para salir"
