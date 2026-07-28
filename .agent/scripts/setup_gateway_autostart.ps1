# Setup Antigravity Gateway autostart en Windows
#
# Registra una Scheduled Task que ejecuta `python start_gateway.py` al login
# del usuario. Mantiene el gateway :4747 siempre disponible para mem0, brain,
# intelligence y observability.
#
# Uso:
#   Desde PowerShell elevado o normal:
#     .\.agent\scripts\setup_gateway_autostart.ps1
#
# Verificación post-instalación:
#   Get-ScheduledTask -TaskName "AntigravityGateway"
#   curl http://127.0.0.1:4747/v1/health
#
# Desregistrar:
#   Unregister-ScheduledTask -TaskName "AntigravityGateway" -Confirm:$false

$ErrorActionPreference = "Stop"

$taskName = "AntigravityGateway"
$repoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
$pythonExe = "$repoRoot\.venv-mcp\Scripts\python.exe"
$gatewayScript = "$repoRoot\start_gateway.py"

# Verificar prerequisites
if (-not (Test-Path $pythonExe)) {
    Write-Error "No se encontro $pythonExe. Verifica que .venv-mcp existe."
    exit 1
}
if (-not (Test-Path $gatewayScript)) {
    Write-Error "No se encontro $gatewayScript."
    exit 1
}

Write-Host "Configurando autostart del Antigravity Gateway..." -ForegroundColor Cyan
Write-Host "  Repo:    $repoRoot"
Write-Host "  Python:  $pythonExe"
Write-Host "  Script:  $gatewayScript"

# Eliminar task existente si la hay (idempotente)
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Task '$taskName' ya existe — la reemplazo." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# Configurar trigger: al login del usuario actual
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

# Configurar accion: ejecutar python con el script del gateway
# Workdir = repo raiz para que paths relativos funcionen
$action = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument "`"$gatewayScript`"" `
    -WorkingDirectory $repoRoot

# Settings: correr aunque el proceso anterior haya quedado, hidden window
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -RestartCount 3 `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

# Registrar task
Register-ScheduledTask `
    -TaskName $taskName `
    -Trigger $trigger `
    -Action $action `
    -Settings $settings `
    -Description "Antigravity Gateway HTTP :4747 — autostart al login. Provee mem0, brain, intelligence MCPs." `
    -RunLevel Limited | Out-Null

Write-Host ""
Write-Host "Task '$taskName' registrada exitosamente." -ForegroundColor Green
Write-Host ""
Write-Host "Para arrancar el gateway ahora (sin esperar al proximo login):" -ForegroundColor Cyan
Write-Host "  Start-ScheduledTask -TaskName $taskName"
Write-Host ""
Write-Host "Para verificar que arranco:" -ForegroundColor Cyan
Write-Host "  Start-Sleep 3"
Write-Host "  curl http://127.0.0.1:4747/v1/health"
Write-Host ""
Write-Host "Para deshabilitar el autostart en el futuro:" -ForegroundColor Cyan
Write-Host "  Unregister-ScheduledTask -TaskName $taskName -Confirm:`$false"
