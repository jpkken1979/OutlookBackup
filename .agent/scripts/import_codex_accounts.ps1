# .agent/scripts/import_codex_accounts.ps1
# Script para importar cuentas de Codex guardadas en el repositorio al directorio home del usuario.

$CodexHome = Join-Path $HOME ".codex"
$AccountsHome = Join-Path $CodexHome "accounts"
$RepoAccounts = Join-Path $PSScriptRoot "..\accounts\codex"

if (-not (Test-Path $RepoAccounts)) {
    Write-Error "No se encontraron cuentas en el repositorio: $RepoAccounts"
    exit 1
}

if (-not (Test-Path $AccountsHome)) {
    Write-Host "Creando directorio de cuentas: $AccountsHome"
    New-Item -ItemType Directory -Force -Path $AccountsHome
}

Write-Host "Importando cuentas desde el repositorio..."
Copy-Item "$RepoAccounts\*" -Destination $AccountsHome -Force -Recurse

Write-Host "✅ Cuentas importadas correctamente a $AccountsHome"
Write-Host "Ahora puedes usar el selector de cuentas en Nexus."
