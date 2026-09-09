<##
.SYNOPSIS
  Captura WinCodexBar sin mover ni enfocar su ventana.

.DESCRIPTION
  Primero intenta PrintWindow, que obtiene la superficie de la ventana en
  segundo plano. Solo usa CopyFromScreen como respaldo, conservando siempre
  la posición actual. Los textos que parecen claves o tokens se cubren antes
  de guardar el PNG mediante la información de accesibilidad de Windows.

.PARAMETER OutPath
  Ruta de salida personalizada.

.PARAMETER NoRestore
  Conservado por compatibilidad. No modifica la posición de la ventana.

.PARAMETER NoRedact
  Desactiva la ocultación de secretos. No se usa desde Telegram.

.PARAMETER AllowMoveFallback
  Permite el antiguo respaldo que mueve la ventana. Está desactivado por
  defecto para que una captura remota nunca reorganice el escritorio.
#>
[CmdletBinding()]
param(
  [string]$OutPath,
  [switch]$NoRestore,
  [switch]$NoRedact,
  [switch]$AllowMoveFallback
)

$ErrorActionPreference = "Stop"

function Log-Info([string]$Message) {
  [Console]::Error.WriteLine($Message)
}

$scratchpad = Join-Path $env:LOCALAPPDATA "Temp\claude\D--BackupJp26-5-11-DesdelaAppBackup-Jpkken1979-OpenAntigravity26-3-30\4f6ad34e-6faf-4f70-92f2-ab76fa3c7672\scratchpad"
if ($OutPath) {
  $outFile = [IO.Path]::GetFullPath($OutPath)
} else {
  New-Item -ItemType Directory -Path $scratchpad -Force | Out-Null
  $outFile = Join-Path $scratchpad ("codexbar_{0}.png" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
}
$outParent = Split-Path -Parent $outFile
if ($outParent) { New-Item -ItemType Directory -Path $outParent -Force | Out-Null }

Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class CodexBarCaptureWin32 {
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT {
    public int Left;
    public int Top;
    public int Right;
    public int Bottom;
  }

  [DllImport("user32.dll")]
  public static extern bool GetWindowRect(IntPtr hWnd, ref RECT lpRect);

  [DllImport("user32.dll")]
  public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);

  [DllImport("user32.dll")]
  public static extern bool IsIconic(IntPtr hWnd);

  [DllImport("user32.dll")]
  public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

  [DllImport("user32.dll")]
  public static extern bool SetForegroundWindow(IntPtr hWnd);

  [DllImport("user32.dll")]
  public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);

  public const int SW_RESTORE = 9;
  public const int SW_MINIMIZE = 6;
}
"@ -ErrorAction SilentlyContinue

$proc = Get-Process -Name "WinCodexBar" -ErrorAction SilentlyContinue |
  Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero } |
  Select-Object -First 1

if (-not $proc) {
  $exePath = "C:\Program Files\WinCodexBar\WinCodexBar.exe"
  if (Test-Path -LiteralPath $exePath -PathType Leaf) {
    Log-Info "WinCodexBar no estaba activo. Iniciando en segundo plano..."
    Start-Process -FilePath $exePath -WindowStyle Minimized | Out-Null
    Start-Sleep -Milliseconds 2500
    $proc = Get-Process -Name "WinCodexBar" -ErrorAction SilentlyContinue |
      Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero } |
      Select-Object -First 1
  }
}

if (-not $proc) {
  throw "No se encontró WinCodexBar con una ventana disponible."
}

$hwnd = $proc.MainWindowHandle
$originalRect = New-Object CodexBarCaptureWin32+RECT
if (-not [CodexBarCaptureWin32]::GetWindowRect($hwnd, [ref]$originalRect)) {
  throw "No se pudo leer el tamaño de la ventana de WinCodexBar."
}
$originalMinimized = [CodexBarCaptureWin32]::IsIconic($hwnd)
$width = [int]$originalRect.Right - [int]$originalRect.Left
$height = [int]$originalRect.Bottom - [int]$originalRect.Top
if ($width -le 0 -or $height -le 0) {
  throw "Dimensiones de ventana inválidas: ${width}x${height}"
}

Log-Info "WinCodexBar encontrado (PID: $($proc.Id), HWND: $hwnd, ${width}x${height})"

function Test-BitmapHasPixels([System.Drawing.Bitmap]$Bitmap) {
  $stepX = [Math]::Max(1, [int]($Bitmap.Width / 16))
  $stepY = [Math]::Max(1, [int]($Bitmap.Height / 16))
  for ($x = 0; $x -lt $Bitmap.Width; $x += $stepX) {
    for ($y = 0; $y -lt $Bitmap.Height; $y += $stepY) {
      $pixel = $Bitmap.GetPixel($x, $y)
      if (($pixel.R + $pixel.G + $pixel.B) -gt 24) { return $true }
    }
  }
  return $false
}

$script:capturedBitmap = $null

function Capture-WithPrintWindow([IntPtr]$Handle, [int]$W, [int]$H) {
  Add-Type -AssemblyName System.Drawing | Out-Null
  $bitmap = New-Object System.Drawing.Bitmap($W, $H, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  [void]$graphics.Clear([System.Drawing.Color]::FromArgb(8, 12, 20))
  $hdc = $graphics.GetHdc()
  try {
    # PW_RENDERFULLCONTENT (2) is needed by Chromium/Electron windows.
    $printed = [CodexBarCaptureWin32]::PrintWindow($Handle, $hdc, 2)
  } finally {
    [void]$graphics.ReleaseHdc($hdc)
    [void]$graphics.Dispose()
  }
  if ($printed -and (Test-BitmapHasPixels $bitmap)) {
    $script:capturedBitmap = $bitmap
    return
  }
  $bitmap.Dispose()
  return $null
}

function Capture-WithScreen([IntPtr]$Handle, [int]$W, [int]$H) {
  Add-Type -AssemblyName System.Drawing | Out-Null
  $rect = New-Object CodexBarCaptureWin32+RECT
  [void][CodexBarCaptureWin32]::GetWindowRect($Handle, [ref]$rect)
  $bitmap = New-Object System.Drawing.Bitmap($W, $H, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  [void]$graphics.CopyFromScreen([int]$rect.Left, [int]$rect.Top, 0, 0, (New-Object System.Drawing.Size([int]$W, [int]$H)))
  [void]$graphics.Dispose()
  $script:capturedBitmap = $bitmap
}

function Get-SecretAccessibilityRects([IntPtr]$Handle, [int]$WindowLeft, [int]$WindowTop) {
  $rects = @()
  try {
    Add-Type -AssemblyName UIAutomationClient | Out-Null
    Add-Type -AssemblyName UIAutomationTypes | Out-Null
    $root = [System.Windows.Automation.AutomationElement]::FromHandle($Handle)
    if ($null -eq $root) { return $rects }
    $condition = [System.Windows.Automation.Condition]::TrueCondition
    $elements = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)
    $seen = @{}
    foreach ($element in $elements) {
      $name = [string]$element.Current.Name
      if (-not $name -or $name -notmatch '(?i)(?:\bsk-[a-z0-9._-]{4,}|\b(?:api|access|secret|auth)[ _-]?key\b|\bbearer[ _-]+[a-z0-9._-]{8,}|\btoken[ _-]*(?:key|secret)\s*[:=])') {
        continue
      }
      $bounds = $element.Current.BoundingRectangle
      if ($bounds.Width -le 0 -or $bounds.Height -le 0) { continue }
      $left = [int]$bounds.X - $WindowLeft
      $top = [int]$bounds.Y - $WindowTop
      $right = $left + [int]$bounds.Width
      $bottom = $top + [int]$bounds.Height
      # Electron exposes a whole provider row as a button. For a row whose
      # accessible name contains a token, cover only the token chip region;
      # keep the provider name, quota bar, and percentage readable.
      if ($name -match '(?i)\bsk-[a-z0-9._-]{4,}') {
        $left = $left + 89
        $right = [Math]::Min($right, $left + 106)
        $top = $top + 4
        $bottom = [Math]::Min($bottom, $top + 28)
      }
      $key = "$left,$top,$right,$bottom"
      if (-not $seen.ContainsKey($key)) {
        $seen[$key] = $true
        $rects += [PSCustomObject]@{ Left = $left; Top = $top; Right = $right; Bottom = $bottom }
      }
    }
  } catch {
    Log-Info "No se pudo consultar la accesibilidad para ocultar etiquetas sensibles."
  }
  return $rects
}

function Redact-SecretRects([System.Drawing.Bitmap]$Bitmap, $Rects) {
  if (-not $Rects -or $Rects.Count -eq 0) { return 0 }
  $graphics = [System.Drawing.Graphics]::FromImage($Bitmap)
  $brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(12, 18, 36))
  $pen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(55, 92, 150), 1)
  $font = New-Object System.Drawing.Font("Segoe UI", 8, [System.Drawing.FontStyle]::Regular)
  $count = 0
  try {
    foreach ($rect in $Rects) {
      $left = [Math]::Max(0, [Math]::Min([int]$Bitmap.Width - 1, [int]$rect.Left))
      $top = [Math]::Max(0, [Math]::Min([int]$Bitmap.Height - 1, [int]$rect.Top))
      $right = [Math]::Max($left + 1, [Math]::Min([int]$Bitmap.Width, [int]$rect.Right))
      $bottom = [Math]::Max($top + 1, [Math]::Min([int]$Bitmap.Height, [int]$rect.Bottom))
      $area = [System.Drawing.Rectangle]::new(
        [int]$left,
        [int]$top,
        [int]($right - $left),
        [int]($bottom - $top)
      )
      [void]$graphics.FillRectangle($brush, $area)
      [void]$graphics.DrawRectangle($pen, $area)
      [void]$count++
    }
  } finally {
    $font.Dispose()
    $pen.Dispose()
    $brush.Dispose()
    $graphics.Dispose()
  }
  return $count
}

$wasRestored = $false
try {
  if ($originalMinimized) {
    # Restore only the rendering surface; never move or focus it.
    [void][CodexBarCaptureWin32]::ShowWindow($hwnd, [CodexBarCaptureWin32]::SW_RESTORE)
    Start-Sleep -Milliseconds 350
    $wasRestored = $true
  }

  $script:capturedBitmap = $null
  Capture-WithPrintWindow $hwnd $width $height
  $bitmap = $script:capturedBitmap
  $captureMethod = "PrintWindow (fondo)"

  if ($null -eq $bitmap) {
    Log-Info "PrintWindow no devolvió una superficie válida; usando CopyFromScreen sin mover la ventana."
    $script:capturedBitmap = $null
    Capture-WithScreen $hwnd $width $height
    $bitmap = $script:capturedBitmap
    $captureMethod = "CopyFromScreen (posición actual)"
  }

  if (-not $NoRedact) {
    $secretRects = Get-SecretAccessibilityRects $hwnd $originalRect.Left $originalRect.Top
    $redacted = Redact-SecretRects $bitmap $secretRects
    if ($redacted -gt 0) { Log-Info "Ocultadas $redacted etiquetas potencialmente sensibles." }
  }

  $bitmap.Save($outFile, [System.Drawing.Imaging.ImageFormat]::Png)
  $bitmap.Dispose()
  Log-Info "Captura guardada ($captureMethod): $outFile"
} finally {
  if ($wasRestored -and $originalMinimized) {
    [void][CodexBarCaptureWin32]::ShowWindow($hwnd, [CodexBarCaptureWin32]::SW_MINIMIZE)
  }
}

Write-Output $outFile
