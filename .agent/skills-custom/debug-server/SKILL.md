---
name: debug-server
description: Diagnostica problemas de servidores: puertos conflictuados, errores CORS, .env incompleto, dependencias faltantes, conexión rechazada. Checks: puertos activos, variables entorno, logs, health checks. Triggers: debug server, server error, port already in use, EADDRINUSE, no se conecta, CORS error.
---

# Debug Server - Diagnóstico de Problemas

## Propósito

Diagnostica rápidamente problemas comunes de servidores.

## Checks Automáticos

1. **Verificar Puertos**
   - ¿Qué está usando puerto 3000?
   - ¿Qué está usando puerto 8000?
   - Procesos listeners

2. **Variables de Entorno**
   - .env existe y es válido
   - Variables requeridas presentes
   - Formato correcto

3. **Dependencias**
   - requirements.txt completado
   - node_modules present (si aplica)
   - Importaciones resolvibles

4. **Health Checks**
   - Backend responde en :8000
   - Frontend responde en :3000
   - CORS headers correctos

5. **Logs**
   - Errores recientes
   - Warnings importantes
   - Clues sobre causa

## Uso

```bash
/debug-server "descripción del problema"
```

Ejemplos:
- "No puedo conectarme a localhost:8000"
- "Puerto 3000 ya está en uso"
- "CORS error en requests"
