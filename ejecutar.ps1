# ============================================================
# WhatsApp Sender - Script de Ejecución PowerShell
# ============================================================

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " WhatsApp Sender - Ejecutando Aplicacion" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Navegar a la carpeta del proyecto
Set-Location -Path "C:\Users\mcomb\Desktop\Carvajal\python\dashboard"

# Buscar conda
Write-Host "Buscando Conda..." -ForegroundColor Yellow
$condaPaths = @(
    "$env:USERPROFILE\anaconda3\Scripts\conda.exe",
    "$env:USERPROFILE\miniconda3\Scripts\conda.exe",
    "C:\ProgramData\Anaconda3\Scripts\conda.exe",
    "C:\ProgramData\Miniconda3\Scripts\conda.exe",
    "$env:USERPROFILE\AppData\Local\anaconda3\Scripts\conda.exe",
    "$env:USERPROFILE\AppData\Local\miniconda3\Scripts\conda.exe"
)

$condaPath = $null
foreach ($path in $condaPaths) {
    if (Test-Path $path) {
        $condaPath = $path
        break
    }
}

if (-not $condaPath) {
    Write-Host ""
    Write-Host "ERROR: No se encontro conda en PowerShell" -ForegroundColor Red
    Write-Host ""
    Write-Host "SOLUCION: Usa uno de estos metodos:" -ForegroundColor Yellow
    Write-Host "  1. Abre 'Anaconda Prompt' y ejecuta:" -ForegroundColor Cyan
    Write-Host "     cd C:\Users\mcomb\Desktop\Carvajal\python\dashboard" -ForegroundColor White
    Write-Host "     conda activate carvajal" -ForegroundColor White
    Write-Host "     streamlit run pages\wa.py" -ForegroundColor White
    Write-Host ""
    Write-Host "  2. O simplemente haz doble click en:" -ForegroundColor Cyan
    Write-Host "     2_EJECUTAR_APP.bat" -ForegroundColor White
    Write-Host ""
    Read-Host -Prompt "Presiona Enter para cerrar"
    exit 1
}

Write-Host "Conda encontrado: $condaPath" -ForegroundColor Green
Write-Host ""
Write-Host "Activando ambiente 'carvajal'..." -ForegroundColor Yellow

# Buscar Python en el ambiente carvajal
$pythonPath = "$env:USERPROFILE\miniconda3\envs\carvajal\python.exe"
if (-not (Test-Path $pythonPath)) {
    $pythonPath = "$env:USERPROFILE\anaconda3\envs\carvajal\python.exe"
}

if (Test-Path $pythonPath) {
    Write-Host "Python encontrado: $pythonPath" -ForegroundColor Green

    # Buscar streamlit
    $streamlitPath = "$env:USERPROFILE\miniconda3\envs\carvajal\Scripts\streamlit.exe"
    if (-not (Test-Path $streamlitPath)) {
        $streamlitPath = "$env:USERPROFILE\anaconda3\envs\carvajal\Scripts\streamlit.exe"
    }

    if (Test-Path $streamlitPath) {
        Write-Host ""
        Write-Host "Iniciando Streamlit..." -ForegroundColor Green
        Write-Host ""
        Write-Host "IMPORTANTE: Mira esta ventana para ver los LOGS de envio" -ForegroundColor Magenta
        Write-Host "Los logs mostraran cada paso del proceso de envio" -ForegroundColor Magenta
        Write-Host ""
        Write-Host "NO CIERRES ESTA VENTANA - Aqui veras el progreso real" -ForegroundColor Red
        Write-Host ""
        Write-Host "============================================================" -ForegroundColor Cyan
        Write-Host ""

        # Ejecutar Streamlit
        & $streamlitPath run pages\wa.py
    } else {
        Write-Host "ERROR: No se encontro streamlit" -ForegroundColor Red
        Write-Host "Ejecuta: pip install streamlit" -ForegroundColor Yellow
    }
} else {
    Write-Host "ERROR: No se encontro Python en ambiente 'carvajal'" -ForegroundColor Red
}

# Pausar al finalizar
Read-Host -Prompt "Presiona Enter para cerrar"
