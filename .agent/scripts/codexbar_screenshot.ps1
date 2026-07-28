<#
.SYNOPSIS
  Capture WinCodexBar window as a PNG screenshot.
.DESCRIPTION
  Finds the WinCodexBar process window, brings it to front, captures it,
  and saves the PNG to the scratchpad or a user-specified path.
  Restores window position afterwards.
.PARAMETER OutPath
  Output file path. Defaults to a timestamped file in the scratchpad dir.
.PARAMETER NoRestore
  Do not restore the original window position after capture.
#>
param(
  [string]$OutPath = "",
  [switch]$NoRestore
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

# --- P/Invoke ----------------------------------------------------------------
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class WinAPI {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@

# --- Find WinCodexBar window -------------------------------------------------
$procs = Get-Process WinCodexBar -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 }
if (-not $procs) {
  # Fallback: try all WinCodexBar processes and check each handle
  $procs = Get-Process WinCodexBar -ErrorAction SilentlyContinue
  if (-not $procs) {
    Write-Error "WinCodexBar no está corriendo."
    exit 1
  }
}

$hwnd = [IntPtr]::Zero
foreach ($p in $procs) {
  if ($p.MainWindowHandle -ne [IntPtr]::Zero) {
    $hwnd = $p.MainWindowHandle
    break
  }
}
if ($hwnd -eq [IntPtr]::Zero) {
  Write-Error "No se encontró ventana visible de WinCodexBar."
  exit 1
}

# --- Save original position --------------------------------------------------
$origRect = New-Object WinAPI+RECT
[WinAPI]::GetWindowRect($hwnd, [ref]$origRect) | Out-Null
$origX = $origRect.Left
$origY = $origRect.Top
$origW = $origRect.Right - $origRect.Left
$origH = $origRect.Bottom - $origRect.Top

# --- Determine output path ---------------------------------------------------
if ([string]::IsNullOrEmpty($OutPath)) {
  $scratchDir = "$env:LOCALAPPDATA\Temp\claude\D--BackupJp26-5-11-DesdelaAppBackup-Jpkken1979-uns-backup-app-v3-1\22fffc62-f712-4bb0-b054-8a1b35c1941e\scratchpad"
  if (-not (Test-Path $scratchDir)) { New-Item -ItemType Directory -Path $scratchDir -Force | Out-Null }
  $ts = Get-Date -Format "yyyyMMdd-HHmmss"
  $OutPath = Join-Path $scratchDir "codexbar_$ts.png"
}

# --- Move to primary monitor, capture, restore -------------------------------
$primary = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$captureX = $primary.Left + 50
$captureY = $primary.Top + 50

# Restore if minimized
if ([WinAPI]::IsIconic($hwnd)) {
  [WinAPI]::ShowWindow($hwnd, 9) | Out-Null  # SW_RESTORE
}

# Move to primary screen for reliable capture
[WinAPI]::MoveWindow($hwnd, $captureX, $captureY, $origW, $origH, $true) | Out-Null
Start-Sleep -Milliseconds 400

# Bring to front
[WinAPI]::SetForegroundWindow($hwnd) | Out-Null
Start-Sleep -Milliseconds 400

# Capture
$bmp = New-Object System.Drawing.Bitmap($origW, $origH)
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$gfx.CopyFromScreen($captureX, $captureY, 0, 0, (New-Object System.Drawing.Size($origW, $origH)))
$bmp.Save($OutPath, [System.Drawing.Imaging.ImageFormat]::Png)
$gfx.Dispose()
$bmp.Dispose()

# Restore original position
if (-not $NoRestore) {
  [WinAPI]::MoveWindow($hwnd, $origX, $origY, $origW, $origH, $true) | Out-Null
}

# Output the path for Claude to read
Write-Output $OutPath
