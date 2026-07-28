---
description: Capturar ventana de WinCodexBar como imagen
argument-hint: [ruta-de-salida-opcional]
allowed-tools: Bash, Read
---

Capturar la ventana visible de WinCodexBar (la app de barra de cuotas) como PNG
y mostrarla al usuario. Usa el script de PowerShell dedicado que:

1. Busca el proceso WinCodexBar activo
2. Mueve la ventana al monitor principal temporalmente
3. Captura solo esa ventana con CopyFromScreen
4. Restaura la posición original
5. Devuelve la ruta del PNG para que Claude la lea y muestre

Resultado:
!`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .agent/scripts/codexbar_screenshot.ps1 $ARGUMENTS`

Después de ejecutar el script, lee la imagen devuelta con la herramienta Read
para que el usuario la vea en el chat. Si el script falla, explica el error y
sugiere verificar que WinCodexBar esté corriendo.
