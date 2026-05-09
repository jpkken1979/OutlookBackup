# Regla: Seguridad

Aplica a todo el código Python, TypeScript y Bash del repositorio.

## Obligatorio

- **NUNCA** hardcodear secrets, tokens o API keys — usar variables de entorno
- **NUNCA** usar `shell=True` en subprocess — siempre `shlex.split()` + `shell=False`
- **NUNCA** commitear archivos `.env` (`.env.example` es la plantilla segura)
- Validar y sanear inputs del usuario antes de cualquier procesamiento
- Validar paths antes de I/O para prevenir directory traversal
- Sanitizar mensajes de error hacia el cliente (no exponer paths internos)
- Rate limiting en endpoints públicos
- CORS restrictivo: solo orígenes conocidos

## Patrón correcto para subprocess

```python
# MAL
subprocess.run(command, shell=True)

# BIEN
import shlex
result = subprocess.run(shlex.split(command), shell=False, capture_output=True)
```

## Tauri / Electron

- `contextIsolation: true`, `nodeIntegration: false` siempre
- Solo IPC a través del bridge de preload — nunca exponer Node APIs directamente
- Inputs IPC validados antes de llegar al proceso principal
