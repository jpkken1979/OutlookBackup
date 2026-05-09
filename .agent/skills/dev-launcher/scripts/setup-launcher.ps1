#Requires -Version 5.1
<#
.SYNOPSIS
    Instala el Dev Launcher en una app.

.DESCRIPTION
    Copia o crea symlink del start-app.bat en el directorio de la app.

.PARAMETER AppPath
    Ruta de la app donde instalar el launcher.

.PARAMETER UseSymlink
    Usar symlink en lugar de copiar (requiere admin).

.EXAMPLE
    .\setup-launcher.ps1 -AppPath "$env:USERPROFILE\MiApp"

.EXAMPLE
    .\setup-launcher.ps1 -AppPath "$env:USERPROFILE\MiApp" -UseSymlink
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$AppPath,

    [switch]$UseSymlink
)

$ErrorActionPreference = "Stop"

# Rutas
$SkillPath = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$LauncherSource = Join-Path $SkillPath "templates\start-app.bat"
$LauncherDest = Join-Path $AppPath "start-app.bat"

Write-Host "`n=== Dev Launcher Setup ===" -ForegroundColor Cyan
Write-Host "App: $AppPath"
Write-Host "Launcher: $LauncherSource`n"

# Verificar que existe la app
if (-not (Test-Path $AppPath)) {
    Write-Host "✗ El directorio no existe: $AppPath" -ForegroundColor Red
    exit 1
}

# Verificar que existe el launcher source
if (-not (Test-Path $LauncherSource)) {
    Write-Host "✗ No se encontró el launcher: $LauncherSource" -ForegroundColor Red
    exit 1
}

# Eliminar launcher existente
if (Test-Path $LauncherDest) {
    Remove-Item $LauncherDest -Force
    Write-Host "  → Launcher anterior eliminado" -ForegroundColor Yellow
}

# Crear symlink o copiar
if ($UseSymlink) {
    # Verificar permisos de admin
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

    if (-not $isAdmin) {
        Write-Host "✗ Se requieren permisos de administrador para crear symlinks" -ForegroundColor Red
        Write-Host "  Ejecuta PowerShell como Administrador o usa sin -UseSymlink" -ForegroundColor Yellow
        exit 1
    }

    New-Item -ItemType SymbolicLink -Path $LauncherDest -Target $LauncherSource | Out-Null
    Write-Host "✓ Symlink creado: $LauncherDest" -ForegroundColor Green
} else {
    Copy-Item $LauncherSource $LauncherDest
    Write-Host "✓ Launcher copiado: $LauncherDest" -ForegroundColor Green
}

Write-Host "`n=== Instalación Completada ===" -ForegroundColor Green
Write-Host "`nPara iniciar tu app:"
Write-Host "  cd `"$AppPath`"" -ForegroundColor Cyan
Write-Host "  .\start-app.bat" -ForegroundColor Cyan
Write-Host ""
