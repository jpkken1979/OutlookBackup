---
description: Capturar la ventana de WinCodexBar como imagen
argument-hint: [--no-restore|--out <ruta>]
allowed-tools: Bash, Read
---

Captura una imagen de la ventana de WinCodexBar (barra lateral de cuotas de IA).
Busca el proceso activo, lo mueve al monitor principal, captura y restaura la
posicion original. Si WinCodexBar no esta corriendo, intenta iniciarlo.

Argumentos opcionales:
- `--no-restore` — deja la ventana donde se movio tras capturar
- `--out <ruta>` — guarda el PNG en una ruta personalizada

Ejecuta el script de captura y luego lee el PNG para mostrarlo:

!`powershell -NoProfile -ExecutionPolicy Bypass -File .agent/scripts/codexbar_screenshot.ps1 $ARGUMENTS`

Despues de ejecutar el script, lee la ruta PNG que imprimio al stdout y muestrala con Read.
Si el script falla, explica el error y sugiere abrir WinCodexBar manualmente.
