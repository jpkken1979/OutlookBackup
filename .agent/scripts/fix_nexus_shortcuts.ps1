param(
    [string]$AppExe = "$env:LOCALAPPDATA\Antigravity Nexus\antigravity-nexus.exe"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $AppExe)) {
    throw "No se encontro el ejecutable principal: $AppExe"
}

$shell = New-Object -ComObject WScript.Shell
$links = @(
    "$env:USERPROFILE\OneDrive\Desktop\Antigravity Nexus.lnk",
    "$env:USERPROFILE\Desktop\Antigravity Nexus.lnk",
    "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Antigravity Nexus.lnk"
)

foreach ($linkPath in $links) {
    if (-not (Test-Path $linkPath)) {
        continue
    }

    $shortcut = $shell.CreateShortcut($linkPath)
    $shortcut.TargetPath = $AppExe
    $shortcut.IconLocation = "$AppExe,0"
    $shortcut.WorkingDirectory = Split-Path -Parent $AppExe
    $shortcut.Save()
    Write-Host "Shortcut actualizado: $linkPath"
}

$oldGlobalLink = "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\Antigravity Nexus.lnk"
if (Test-Path $oldGlobalLink) {
    Remove-Item -Force $oldGlobalLink
    Write-Host "Shortcut legado removido: $oldGlobalLink"
}

# Refresca cache de iconos (no requiere reiniciar sesion)
Start-Process -FilePath "ie4uinit.exe" -ArgumentList "-show" -Wait -WindowStyle Hidden
Write-Host "Refresco de iconos ejecutado."
