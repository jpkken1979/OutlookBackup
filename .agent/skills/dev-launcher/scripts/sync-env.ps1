#Requires -Version 5.1
<#
.SYNOPSIS
    Sincroniza archivos .env con los puertos especificados.

.DESCRIPTION
    Este script actualiza todos los archivos .env del proyecto
    con los puertos de frontend y backend correctos.

.PARAMETER FrontendPort
    Puerto del frontend (ej: 3001)

.PARAMETER BackendPort
    Puerto del backend (ej: 8001)

.PARAMETER ProjectPath
    Ruta del proyecto (por defecto: directorio actual)

.EXAMPLE
    .\sync-env.ps1 -FrontendPort 3001 -BackendPort 8001
#>

param(
    [Parameter(Mandatory=$true)]
    [int]$FrontendPort,

    [Parameter(Mandatory=$true)]
    [int]$BackendPort,

    [string]$ProjectPath = (Get-Location).Path
)

# Colores
$Colors = @{
    Success = "Green"
    Warning = "Yellow"
    Error = "Red"
    Info = "Cyan"
}

function Write-Status {
    param(
        [string]$Message,
        [string]$Type = "Info"
    )
    $symbol = switch ($Type) {
        "Success" { "✓" }
        "Warning" { "⚠" }
        "Error" { "✗" }
        "Info" { "→" }
    }
    Write-Host "  $symbol " -ForegroundColor $Colors[$Type] -NoNewline
    Write-Host $Message
}

function Update-EnvFile {
    param(
        [string]$FilePath,
        [hashtable]$Variables
    )

    $envContent = @{}

    # Leer archivo existente
    if (Test-Path $FilePath) {
        Get-Content $FilePath | ForEach-Object {
            if ($_ -match '^([^#=]+)=(.*)$') {
                $envContent[$Matches[1].Trim()] = $Matches[2].Trim()
            }
        }
    }

    # Actualizar con nuevas variables
    foreach ($key in $Variables.Keys) {
        $envContent[$key] = $Variables[$key]
    }

    # Escribir archivo
    $output = @()
    $output += "# Auto-generado por Dev Launcher"
    $output += "# Fecha: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    $output += ""

    foreach ($key in ($envContent.Keys | Sort-Object)) {
        $output += "$key=$($envContent[$key])"
    }

    $output | Set-Content -Path $FilePath -Encoding UTF8
    Write-Status "Actualizado: $FilePath" -Type "Success"
}

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

Write-Host "`n=== Sincronizando archivos .env ===" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:$FrontendPort"
Write-Host "Backend:  http://localhost:$BackendPort`n"

# Variables comunes para frontend
$frontendVars = @{
    "PORT" = $FrontendPort
    "NEXT_PUBLIC_PORT" = $FrontendPort
    "NEXT_PUBLIC_API_URL" = "http://localhost:$BackendPort"
    "NEXT_PUBLIC_BACKEND_URL" = "http://localhost:$BackendPort"
    "VITE_API_URL" = "http://localhost:$BackendPort"
    "VITE_BACKEND_URL" = "http://localhost:$BackendPort"
    "REACT_APP_API_URL" = "http://localhost:$BackendPort"
    "REACT_APP_BACKEND_URL" = "http://localhost:$BackendPort"
    "API_URL" = "http://localhost:$BackendPort"
}

# Variables para backend
$backendVars = @{
    "PORT" = $BackendPort
    "BACKEND_PORT" = $BackendPort
    "FRONTEND_URL" = "http://localhost:$FrontendPort"
    "CORS_ORIGINS" = "http://localhost:$FrontendPort,http://127.0.0.1:$FrontendPort"
    "CORS_ORIGIN" = "http://localhost:$FrontendPort"
    "ALLOWED_ORIGINS" = "http://localhost:$FrontendPort,http://127.0.0.1:$FrontendPort"
    "ALLOWED_HOSTS" = "localhost,127.0.0.1"
}

# Buscar y actualizar archivos .env
$envFiles = @(
    ".env",
    ".env.local",
    ".env.development",
    ".env.development.local",
    "frontend\.env",
    "frontend\.env.local",
    "client\.env",
    "client\.env.local"
)

$backendEnvFiles = @(
    "backend\.env",
    "server\.env",
    "api\.env"
)

# Actualizar archivos frontend
foreach ($file in $envFiles) {
    $fullPath = Join-Path $ProjectPath $file
    if (Test-Path $fullPath) {
        Update-EnvFile -FilePath $fullPath -Variables $frontendVars
    } elseif ($file -eq ".env" -or $file -eq ".env.local") {
        # Crear archivo principal si no existe
        Update-EnvFile -FilePath $fullPath -Variables $frontendVars
    }
}

# Actualizar archivos backend
foreach ($file in $backendEnvFiles) {
    $fullPath = Join-Path $ProjectPath $file
    $dirPath = Split-Path $fullPath -Parent
    if (Test-Path $dirPath) {
        Update-EnvFile -FilePath $fullPath -Variables $backendVars
    }
}

# Si hay requirements.txt en la raíz, crear .env para backend
if (Test-Path (Join-Path $ProjectPath "requirements.txt")) {
    $backendEnv = Join-Path $ProjectPath ".env"
    # Combinar variables
    $combinedVars = $frontendVars.Clone()
    foreach ($key in $backendVars.Keys) {
        $combinedVars[$key] = $backendVars[$key]
    }
    Update-EnvFile -FilePath $backendEnv -Variables $combinedVars
}

Write-Host "`n✓ Sincronización completada`n" -ForegroundColor Green
