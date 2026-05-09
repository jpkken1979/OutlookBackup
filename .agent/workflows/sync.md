---
description: Sync with GitHub (pull + commit + push) and auto-update project memory with a changelog entry
---

# /sync — Sincronizar con GitHub y actualizar memoria del proyecto

// turbo-all

## Workflow

### 1. Verificar estado del repositorio
```bash
git status -s
```
Observar qué archivos fueron modificados, añadidos o eliminados.

### 2. Revisar los cambios en detalle
```bash
git diff --stat
```
Obtener estadísticas de los cambios (archivos, inserciones, eliminaciones).

### 3. Traer cambios remotos (pull)
```bash
git pull --rebase origin main
```
Si hay conflictos, resolverlos antes de continuar.

### 4. Generar resumen de cambios para memoria
```bash
git log --oneline -5
```
Revisar los últimos commits para no duplicar información.

### 5. Actualizar ESTADO_PROYECTO.md con entrada de sesión

Antes del primer bloque `## Sesión` existente en `ESTADO_PROYECTO.md`, insertar una nueva sección:

```markdown
## Sesión {FECHA_HOY} — {RESUMEN_BREVE}

### Cambios realizados

| Área | Estado |
|---|---|
| {archivo_o_area_1} | {descripción_del_cambio_1} |
| {archivo_o_area_2} | {descripción_del_cambio_2} |

### Validación

- {resultado_de_validación}
```

**Reglas para el resumen:**
- `{FECHA_HOY}` = fecha actual en formato `YYYY-MM-DD`
- `{RESUMEN_BREVE}` = máximo 10 palabras describiendo el tema principal de la sesión
- Solo incluir cambios **significativos** (no listar cada archivo trivial)
- Si no hay cambios significativos desde la última sesión registrada, NO agregar entrada nueva
- Agrupar cambios relacionados en una sola fila de la tabla

### 6. Agregar todos los cambios al staging
```bash
git add -A
```

### 7. Crear commit con mensaje descriptivo
```bash
git commit -m "chore(sync): {RESUMEN_BREVE_EN_ESPAÑOL}"
```
El mensaje debe describir qué cambió en esta sesión. Si el ESTADO_PROYECTO.md fue actualizado, mencionarlo.

### 8. Push al remoto
```bash
git push origin main
```

### 9. Confirmar sincronización
```bash
git log --oneline -3
```
Mostrar los últimos 3 commits para confirmar que todo se subió correctamente.

### 10. Reporte final al usuario

Mostrar un resumen:
```
✅ Sincronización completada
📥 Pull: {resultado}
📤 Push: {cantidad_archivos} archivos, {inserciones}+, {eliminaciones}-
📝 Memoria: ESTADO_PROYECTO.md actualizado con sesión {FECHA}
🔗 Último commit: {hash} — {mensaje}
```

## Notas

- Si no hay cambios locales, solo hacer pull y reportar "sin cambios locales"
- Si hay conflictos en el pull, parar y pedir resolución al usuario
- La entrada en ESTADO_PROYECTO.md debe ir DESPUÉS de la sección "Estado Operativo" y ANTES de la primera "Sesión" existente
- Actualizar la línea `> Última actualización:` al inicio del archivo con la fecha actual
