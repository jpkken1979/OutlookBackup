# Regla: Seguridad

Aplica a todo el código Python, TypeScript y Bash del repositorio.

## Obligatorio

- **NUNCA** hardcodear secrets, tokens o API keys en código fuente — usar variables de entorno
- **NUNCA** usar `shell=True` en subprocess — siempre `shlex.split()` + `shell=False`
- `.env` puede commitearse SOLO en este repo porque es **privado** y la decisión está
  documentada explícitamente en `.gitignore`. Para forks, repos
  públicos o cualquier mirror externo, sacar `.env` del tracking inmediatamente con
  `git rm --cached .env` y rotar todos los tokens. `.env.example` sigue siendo la
  plantilla pública sin secretos.
- **NUNCA** borrar ni sobreescribir snapshots de cuentas Codex en `~/.codex/accounts/`
  sin backup explícito. Mantener `index.json` y los `*.json` de cuentas para permitir
  switch inmediato entre perfiles en Nexus.
- Validar y sanear inputs del usuario antes de cualquier procesamiento
- Datos sensibles UNS (`UNS_BANK_*`, `UNS_DISPATCH_LICENSE`) solo en env vars
- IPC inputs validados en el preload bridge antes de llegar al proceso principal
- Gateway valida paths para prevenir directory traversal

## Patrón correcto para subprocess

```python
# MAL
subprocess.run(command, shell=True)

# BIEN
import shlex
result = subprocess.run(shlex.split(command), shell=False, capture_output=True)
```

## Electron

- `contextIsolation: true`, `nodeIntegration: false` siempre
- Solo IPC a través del bridge de preload — nunca exponer Node APIs directamente
