---
name: startup
description: Verifica entorno completo (Python 3.11+, npm, .env) y lanza servidores. Mata procesos en puertos 3000, 8000, 3777. Instala dependencias si faltan. Inicia FastAPI backend (:8000) + React frontend (:3000). Valida CORS entre servidores. Reporta status final. Triggers: startup, start servers, iniciar servidores, launch, port conflict, CORS error, server not running.
---

# Startup - Verificación e Inicio de Servidores

## Propósito

Automatiza la verificación del entorno completo y el lanzamiento de servidores (backend FastAPI + frontend React).

## Cuándo Usar

- Inicio de sesión de desarrollo
- Después de clonar repositorio
- Después de cambios en dependencias
- Problemas de conexión servidor-cliente
- Puertos conflictuados

## Pasos Ejecutados

1. **Verificar Entorno**
   - Python 3.11+
   - npm instalado
   - .env configurado

2. **Resolver Puertos**
   - Matar procesos en: 3000, 8000, 3777
   - O: usar puertos alternativos
   - O: preguntar al usuario

3. **Instalar Dependencias**
   - Backend: pip install -r requirements.txt
   - Frontend: npm install (si package.json existe)

4. **Iniciar Servidores**
   - Backend: FastAPI en puerto 8000
   - Frontend: React en puerto 3000
   - Esperar health checks

5. **Validar CORS**
   - Verificar configuración
   - Probar conexión cross-origin

6. **Reportar Status**
   - URLs de acceso
   - Logs de error (si aplica)

## Uso

```bash
/startup
```

O directamente:
```bash
python .agent/scripts/startup.py --verbose
```
