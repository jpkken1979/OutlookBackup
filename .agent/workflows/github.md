---
description: Sincronización rápida con GitHub (pull, commit automático y push) sin alterar memoria
---

# /github — Sincronización rápida (Git)

// turbo-all

## Workflow

### 1. Verificar estado local
```bash
git status -s
git diff --stat
```
Observar los cambios para poder redactar el mensaje del commit automático.

### 2. Sincronizar con remoto (Pull)
```bash
git pull origin main --rebase
```
Traer los cambios más recientes. *(Nota: Si existe conflicto, el proceso debe pausarse para pedirle al usuario que los resuelva).*

### 3. Preparar los cambios
```bash
git add -A
```

### 4. Generar el mensaje de commit y commitear
Analizar los cambios en el paso 1 y crear un mensaje de commit usando formato _Conventional Commits_ (feat, fix, refactor, docs, chore, etc.).

```bash
git commit -m "<tipo>(<alcance>): <descripción corta y concisa>"
```

### 5. Enviar cambios al repositorio remoto (Push)
```bash
git push origin main
```

### 6. Reporte Final
Mostrar un resumen al usuario:
```text
✅ Sincronización con GitHub exitosa.
📥 Pull: OK
📤 Push: [N] archivos modificados.
🔗 Último commit: [mensaje corto del commit]
```

## Diferencias con `/sync`
- `/github` **NO** actualiza ni lee el archivo `ESTADO_PROYECTO.md` u otros registros de memoria. Es exclusivamente una operación rápida y directa de Git.
