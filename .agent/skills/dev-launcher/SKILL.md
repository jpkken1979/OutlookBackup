---
name: dev-launcher
version: 1.0.0
description: Lanzador inteligente de apps para Windows. Auto-detecta proyecto, gestiona puertos, sincroniza .env y CORS, instala dependencias, y mantiene ventana abierta en errores.
type: feature
category: automation
tags: [windows, bat, powershell, launcher, ports, env, cors, docker]
author: Antigravity Agents
---

# Dev Launcher - Lanzador Inteligente de Apps (Windows)

Skill para simplificar el inicio de aplicaciones en desarrollo en Windows.

## Características

- ✅ **Auto-detección** de tipo de proyecto (Next.js, React, Python, Node, etc.)
- ✅ **Selección de puertos** interactiva (solo 3 dígitos finales)
- ✅ **Sincronización automática** de frontend/backend ports
- ✅ **Actualización de .env** con los puertos elegidos
- ✅ **Configuración de CORS** automática
- ✅ **Instalación de dependencias** si faltan
- ✅ **Ventana NO se cierra** en errores
- ✅ **Logs con colores** para fácil lectura
- ✅ **Preparado para Docker** (futuro)

## Instalación Rápida

```cmd
:: Copiar el launcher a tu app
copy "%USERPROFILE%\AntigravitiSkillUSN\.agent\skills\dev-launcher\templates\start-app.bat" "%USERPROFILE%\MiApp\"

:: O crear symlink (recomendado)
mklink "%USERPROFILE%\MiApp\start-app.bat" "%USERPROFILE%\AntigravitiSkillUSN\.agent\skills\dev-launcher\templates\start-app.bat"
```

## Uso

```cmd
:: Simplemente ejecutar el .bat
start-app.bat

:: O con puerto predefinido
start-app.bat 3001

:: O especificar modo
start-app.bat --frontend-only
start-app.bat --backend-only
start-app.bat --docker
```

## Flujo de Ejecución

```
┌─────────────────────────────────────────────────────────────┐
│  START-APP.BAT                                              │
├─────────────────────────────────────────────────────────────┤
│  1. Detectar ubicación actual                               │
│  2. Detectar tipo de proyecto                               │
│  3. Preguntar puerto (ej: 001 → 3001/8001)                  │
│  4. Actualizar .env con puertos                             │
│  5. Actualizar CORS en backend                              │
│  6. Verificar/Instalar dependencias                         │
│  7. Iniciar backend (si existe)                             │
│  8. Iniciar frontend                                        │
│  9. Mostrar URLs de acceso                                  │
│                                                             │
│  ⚠️ Si hay error: NO cerrar ventana, mostrar log           │
└─────────────────────────────────────────────────────────────┘
```

## Estructura de Puertos

| Dígitos | Frontend | Backend | Ejemplo App        |
|---------|----------|---------|-------------------|
| 001     | 3001     | 8001    | Chingin           |
| 002     | 3002     | 8002    | Shain-Daicho      |
| 003     | 3003     | 8003    | Kintai            |
| 004     | 3004     | 8004    | Rirekisho         |

## Archivos Generados

```
MiApp/
├── start-app.bat           # Launcher principal
├── .env                    # Variables (auto-actualizado)
├── .env.local              # Para Next.js (auto-actualizado)
├── frontend/
│   └── .env.local          # Si frontend está separado
└── backend/
    └── .env                # Si backend está separado
```

## Detección Automática de Proyecto

| Archivo/Carpeta        | Tipo Detectado       |
|-----------------------|---------------------|
| `package.json` + `next` | Next.js            |
| `package.json` + `react` | React (CRA/Vite)  |
| `package.json` + `vue`  | Vue.js             |
| `requirements.txt`      | Python             |
| `pyproject.toml`        | Python (Poetry)    |
| `Cargo.toml`            | Rust               |
| `go.mod`                | Go                 |
| `docker-compose.yml`    | Docker             |

## Variables de Entorno Sincronizadas

```env
# Frontend (.env.local)
NEXT_PUBLIC_API_URL=http://localhost:8001
NEXT_PUBLIC_PORT=3001
PORT=3001

# Backend (.env)
PORT=8001
FRONTEND_URL=http://localhost:3001
CORS_ORIGINS=http://localhost:3001,http://127.0.0.1:3001
```

## Manejo de Errores

La ventana NUNCA se cierra automáticamente si hay error:

```
❌ ERROR: No se pudo iniciar el servidor
   Código de salida: 1

   Posibles causas:
   - Puerto 3001 ya está en uso
   - Faltan dependencias
   - Error en el código

   Presiona cualquier tecla para ver el log completo...
```

## Comandos Disponibles

```cmd
start-app.bat                    # Inicio interactivo
start-app.bat 001                # Puerto predefinido
start-app.bat --install          # Solo instalar dependencias
start-app.bat --check            # Solo verificar proyecto
start-app.bat --kill-ports       # Matar procesos en puertos
start-app.bat --docker           # Iniciar con Docker
start-app.bat --help             # Mostrar ayuda
```

## Requisitos

- Windows 10/11
- Node.js (para proyectos JS)
- Python 3.8+ (para proyectos Python)
- PowerShell 5.1+

## Estructura de la Skill

```
dev-launcher/
├── SKILL.md
├── scripts/
│   ├── detect-project.ps1      # Detecta tipo de proyecto
│   ├── sync-env.ps1            # Sincroniza .env files
│   ├── sync-cors.ps1           # Actualiza CORS
│   ├── check-port.ps1          # Verifica puertos libres
│   └── install-deps.ps1        # Instala dependencias
├── templates/
│   ├── start-app.bat           # Launcher principal
│   ├── start-frontend.bat      # Solo frontend
│   ├── start-backend.bat       # Solo backend
│   └── docker-start.bat        # Con Docker
└── examples/
    └── .env.example            # Ejemplo de .env
```
