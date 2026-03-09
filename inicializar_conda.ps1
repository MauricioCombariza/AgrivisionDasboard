# ============================================================
# Inicializar Conda en PowerShell
# ============================================================

Write-Host "Inicializando Conda en PowerShell..." -ForegroundColor Yellow
Write-Host ""

# Buscar la instalación de conda
$condaPaths = @(
    "$env:USERPROFILE\anaconda3\Scripts\conda.exe",
    "$env:USERPROFILE\miniconda3\Scripts\conda.exe",
    "C:\ProgramData\Anaconda3\Scripts\conda.exe",
    "C:\ProgramData\Miniconda3\Scripts\conda.exe"
)

$condaPath = $null
foreach ($path in $condaPaths) {
    if (Test-Path $path) {
        $condaPath = $path
        break
    }
}

if ($condaPath) {
    Write-Host "Conda encontrado en: $condaPath" -ForegroundColor Green
    Write-Host ""
    Write-Host "Ejecutando inicialización..." -ForegroundColor Yellow

    # Inicializar conda para PowerShell
    & $condaPath init powershell

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "Conda inicializado!" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "IMPORTANTE: Cierra y vuelve a abrir PowerShell" -ForegroundColor Red
    Write-Host "Luego ejecuta: .\ejecutar.ps1" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "ERROR: No se encontró conda" -ForegroundColor Red
    Write-Host ""
    Write-Host "Busca 'Anaconda Prompt' en el menú inicio" -ForegroundColor Yellow
    Write-Host "O usa los archivos .bat directamente" -ForegroundColor Yellow
    Write-Host ""
}

Read-Host -Prompt "Presiona Enter para continuar"
