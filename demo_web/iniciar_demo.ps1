# LESCO-Agent: inicia el visor web local de la demostración (solo 127.0.0.1, sin API).
# Uso desde PowerShell, en la raíz del repositorio:
#     powershell -ExecutionPolicy Bypass -File demo_web\iniciar_demo.ps1
#     powershell -ExecutionPolicy Bypass -File demo_web\iniciar_demo.ps1 -Puerto 8766
# Cierre: Ctrl+C en esta ventana.
param(
    [ValidateRange(1024, 65535)]
    [int]$Puerto = 8765,
    [switch]$SinNavegador
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) {
    Write-Host "No se encontró 'python' en el PATH. Instale Python 3.10 o superior." -ForegroundColor Red
    exit 1
}

$argumentos = @("$raiz\demo_web\servidor_demo.py", "--puerto", "$Puerto")
if (-not $SinNavegador) { $argumentos += "--abrir" }

Push-Location $raiz
try {
    & $python.Source @argumentos
} finally {
    Pop-Location
}
