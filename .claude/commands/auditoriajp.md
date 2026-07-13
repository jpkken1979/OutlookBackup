# /auditoriajp

Auditoría profesional de seguridad y calidad (OWASP) sobre el target dado.

## Uso

```
/auditoriajp [target]
```

## Argumentos

- `target`: URL de web pública, path local a repo, o nombre de proyecto. Si se omite, pedir al usuario.

## Descripción

Invoca el agente `security-reviewer` de oh-my-claudecode para auditar el target con:
- Detección de secrets hardcodeados (API keys, tokens, passwords)
- OWASP Top 10: inyección (SQL, XSS, command, path traversal)
- Auth/autorización: tokens en URLs, validación de inputs
- Seguridad Tauri: contextIsolation, nodeIntegration, IPC invoke()
- Seguridad Python: shell=False en subprocess, eval/exec
- Supply chain: dependencias vulnerables (npm, pip, cargo)
- Configuración crítica: .mcp.json, CSP, capabilities

## Ejemplos

```
/auditoriajp https://mi-app.jp
/auditoriajp ./nexus-app
/auditoriajp mi-proyecto-local
```

## Alias

- `/auditar`
- `/auditweb`
