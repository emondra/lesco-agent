# LESCO-Agent: inicia el visor web local de la demostración (solo 127.0.0.1, sin API).
# Uso desde PowerShell, en la raíz del repositorio:
#     powershell -ExecutionPolicy Bypass -File demo_web\iniciar_demo.ps1
#     powershell -ExecutionPolicy Bypass -File demo_web\iniciar_demo.ps1 -Puerto 8766
# Cierre: Ctrl+C en esta ventana.
param(
    [ValidateRange(1024, 65535)]
    [int]$Puerto = 8765,
    [switch]$SinNavegador,
    # Visor de señas CENAREC (desactivado por defecto). -VisorCenarec usa la página OFICIAL: solo con las
    # condiciones de uso y el permiso de CENAREC confirmados. -VisorCenarecPrueba usa una página local.
    [switch]$VisorCenarec,
    [switch]$VisorCenarecPrueba,
    # «Voz con IA real» (fase 2): llamadas con costo a la API, cada una autorizada con un clic; máximo 5.
    [switch]$PermitirApi
)
if ($VisorCenarec -and $VisorCenarecPrueba) {
    Write-Host "Use solo uno: -VisorCenarec o -VisorCenarecPrueba." -ForegroundColor Red
    exit 1
}

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) {
    Write-Host "No se encontró 'python' en el PATH. Instale Python 3.10 o superior." -ForegroundColor Red
    exit 1
}

$argumentos = @("$raiz\demo_web\servidor_demo.py", "--puerto", "$Puerto")
if (-not $SinNavegador) { $argumentos += "--abrir" }
if ($VisorCenarec) { $argumentos += "--visor-cenarec" }
if ($VisorCenarecPrueba) { $argumentos += "--visor-cenarec-prueba" }
if ($PermitirApi) { $argumentos += "--permitir-api" }

Push-Location $raiz
try {
    & $python.Source @argumentos
} finally {
    Pop-Location
}
