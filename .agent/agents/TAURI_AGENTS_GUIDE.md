# Guía Completa de Agentes Tauri

## 🎯 Introducción

Este documento proporciona una guía completa para usar el ecosistema de agentes especializados en **Tauri 2.0** para crear aplicaciones desktop y mobile multiplataforma.

**Características:**
- ✅ 4 agentes especializados
- ✅ 3 skills avanzados
- ✅ Learning Engine auto-evolucionante
- ✅ Orquestación inteligente
- ✅ Soporte multi-plataforma (Windows, macOS, Linux, iOS, Android)
- ✅ Soporte multi-framework (React, Vue, Angular, Svelte, Solid)

---

## 🏗️ Agentes Disponibles

### 1. Tauri Architect

**Especialidad:** Diseño arquitectónico de aplicaciones Tauri

**Cuándo usarlo:**
- Estás planeando una nueva aplicación Tauri
- Necesitas diseñar la división frontend/backend
- Quieres definir límites de seguridad
- Necesitas optimizar para múltiples plataformas

**Invocación:**
```bash
# Con Claude Code
/agent tauri-architect Diseñar arquitectura para gestor de tareas desktop con React

# Script directo
python .agent/scripts/invoke-agent.py tauri-architect "Mi requisito aquí"
```

**Salida:**
- Diagrama arquitectónico
- Recomendaciones de tech stack
- Patrones de comunicación IPC
- Decisiones de seguridad

### 2. Tauri Frontend

**Especialidad:** Desarrollo frontend con Tauri + cualquier framework JS

**Soporta:** React, Vue, Angular, Svelte, Solid

**Cuándo usarlo:**
- Necesitas implementar componentes frontend
- Quieres integrar Tauri API (file, dialog, menu, etc)
- Necesitas state management para desktop
- Quieres optimizar performance de UI

**Invocación:**
```bash
# Con Claude Code
/agent tauri-frontend Crear componentes de UI para editar archivos en Tauri

# Script directo
python .agent/scripts/invoke-agent.py tauri-frontend "Descripción aquí"
```

**Salida:**
- Componentes React/Vue/etc listos
- IPC hooks para invocar comandos
- State management setup
- Tests de componentes

### 3. Tauri Backend

**Especialidad:** Lógica de negocio en Rust + comandos IPC

**Cuándo usarlo:**
- Necesitas implementar lógica de negocio compleja
- Quieres crear comandos IPC seguros
- Necesitas integración con BD o APIs externas
- Requieres plugins nativos (Swift/Kotlin)

**Invocación:**
```bash
# Con Claude Code
/agent tauri-backend Crear comandos Rust para lectura/escritura de archivos

# Script directo
python .agent/scripts/invoke-agent.py tauri-backend "Descripción aquí"
```

**Salida:**
- Código Rust con tipos seguros
- Comandos Tauri listos para invocar desde frontend
- Manejo de errores robusto
- Documentación API

### 4. Learning Engine

**Especialidad:** Aprendizaje continuo y mejora automática

**Características Únicas:**
- 🧠 Aprende de cada proyecto completado
- 🔍 Detecta patrones y anti-patterns
- 🛠️ Genera nuevos skills automáticamente
- 📈 Mejora recomendaciones constantemente
- 🔐 Aprende de vulnerabilidades descubiertas
- ⚡ Optimiza basado en performance data

**Invocación:**
```bash
# Ver aprendizajes
python .agent/agents/learning-engine/scripts/main.py --show-learnings

# Ejecutar análisis manual
python .agent/agents/learning-engine/scripts/main.py --analyze

# Configurar ejecución automática
python .agent/agents/learning-engine/scripts/main.py --schedule weekly
```

**Lo que hace:**
- Captura metadatos de proyectos
- Identifica patrones exitosos
- Genera recomendaciones personalizadas
- Crea nuevos skills automáticamente
- Mantiene historial evolutivo

---

## 🛠️ Skills Disponibles

### 1. Tauri Project Generator

**Propósito:** Generar proyectos Tauri completos desde cero

**Inputs:**
```bash
python .agent/skills/tauri-project-generator/scripts/main.py \
  --project-name "my-app" \
  --frontend-framework "react" \
  --target-platforms "windows,macos,linux" \
  --typescript true \
  --database "sqlite" \
  --security-level "high" \
  --include-tests true
```

**Genera:**
- Proyecto Tauri completo
- Estructura de directorios optimizada
- Configuración de seguridad por defecto
- Scripts de build para múltiples plataformas
- Tests iniciales
- Documentación

**Tiempo:** ~30 segundos

### 2. Tauri Security Patterns

**Propósito:** Aplicar patrones de seguridad probados

**Cobertura:**
- ✅ Validación de entrada (JS + Rust)
- ✅ Manejo de permisos del sistema
- ✅ Comunicación IPC segura
- ✅ Encriptación de datos
- ✅ CORS & CSP hardening
- ✅ Auditoría automática

**Invocación:**
```bash
python .agent/skills/tauri-security-patterns/scripts/main.py \
  --project-path ./my-app \
  --pattern-type all \
  --threat-level high \
  --generate-report
```

**Salida:**
- Código seguro
- Patrones de ejemplo
- Reporte de vulnerabilidades
- Score de seguridad (0-100)

### 3. Tauri Performance Optimization

**Propósito:** Optimizar bundle size, startup time y memory

**Áreas de Optimización:**
- Bundle size (objetivo: < 600KB)
- Startup time (objetivo: < 500ms)
- Memory usage (objetivo: < 100MB idle)
- IPC latency (objetivo: < 1ms)
- Frontend performance (60 FPS)

**Invocación:**
```bash
python .agent/skills/tauri-performance-optimization/scripts/main.py \
  --project-path ./my-app \
  --area all \
  --optimization-level aggressive \
  --generate-report
```

**Salida:**
- Análisis de performance
- Recomendaciones específicas
- Código optimizado
- Comparación antes/después

---

## 🎬 Cómo Empezar

### Opción 1: Crear Nueva Aplicación (Recomendado)

```bash
# 1. Orquestar creación completa
python .agent/scripts/tauri-orchestrator.py \
  "Crear aplicación de gestor de tareas con React, SQL, auth, Windows/macOS/Linux"

# Resultado:
# - Proyecto Tauri generado
# - Arquitectura diseñada
# - Frontend implementado
# - Backend Rust completado
# - Tests creados
# - CI/CD configurado
# - Learning Engine analiza patrones

# 2. Navegar y empezar desarrollo
cd my-app
npm run tauri dev
```

### Opción 2: Paso a Paso Manual

```bash
# 1. Diseñar arquitectura
/agent tauri-architect Crear app de chat con persistencia local

# 2. Generar proyecto base
python .agent/skills/tauri-project-generator/scripts/main.py \
  --project-name "chat-app" \
  --frontend-framework "react"

# 3. Implementar frontend
/agent tauri-frontend Crear UI de chat con lista de mensajes

# 4. Implementar backend
/agent tauri-backend Comandos para guardar/cargar mensajes en SQLite

# 5. Auditoría de seguridad
/agent security-auditor Revisar seguridad de la app de chat

# 6. Optimizar performance
python .agent/skills/tauri-performance-optimization/scripts/main.py \
  --project-path ./chat-app --area all

# 7. Learning Engine captura aprendizajes
python .agent/agents/learning-engine/scripts/main.py --analyze
```

### Opción 3: Agregar Feature a Proyecto Existente

```bash
# Orquestar adición de feature
python .agent/scripts/tauri-orchestrator.py \
  --task-type add_feature \
  --project-path ./my-app \
  --feature "Agregar soporte para themes oscuro/claro"

# Resultado:
# - Feature planificada
# - Frontend implementado
# - Backend soporta persistencia
# - Tests escritos
# - Security revisada
```

---

## 📊 Flujo de Orquestación

```
┌─────────────────────────────────────────┐
│ Descripción de Tarea Natural             │
└──────────────────┬──────────────────────┘
                   ↓
         ┌─────────────────────┐
         │ Orchestrator        │
         │ - Clasifica tarea   │
         │ - Extrae spec       │
         └──────────┬──────────┘
                    ↓
     ┌──────────────────────────────┐
     │ Selecciona Secuencia de      │
     │ Agentes Óptima              │
     └──────────┬───────────────────┘
                ↓
    ┌─────────────────────────────────┐
    │ Ejecuta Agentes en Secuencia:   │
    │ 1. tauri-architect              │
    │ 2. tauri-frontend               │
    │ 3. tauri-backend                │
    │ 4. security-auditor             │
    │ 5. test-engineer                │
    │ 6. devops-engineer              │
    │ 7. learning-engine              │
    └──────────┬──────────────────────┘
               ↓
      ┌────────────────────┐
      │ Reporte Final +    │
      │ Artefactos +       │
      │ Aprendizajes       │
      └────────────────────┘
```

---

## 🔐 Seguridad

Todos los agentes incorporan best practices de seguridad:

- ✅ Validación de entrada en JS y Rust
- ✅ Type-safe IPC communication
- ✅ Permisos granulares del sistema
- ✅ No hardcodear secrets (solo env vars)
- ✅ CSP y CORS configurados
- ✅ Regular security audits

**Scoring automático (0-100):**
```bash
python .agent/skills/tauri-security-patterns/scripts/main.py \
  --project-path ./my-app --generate-report

# Output: Security Score: 92/100
```

---

## ⚡ Performance Targets

| Métrica | Objetivo | Cómo Lograrlo |
|---------|----------|---------------|
| Bundle Size (Windows) | < 600KB | Usar performance-optimization skill |
| Bundle Size (macOS) | < 500KB | Code splitting + minification agresiva |
| Startup Time | < 500ms | Lazy initialization + asset preloading |
| Memory Idle | < 100MB | Efficient data structures |
| IPC Latency | < 1ms | Serialization optimization |
| Frontend FPS | 60 | Virtual scrolling + memoization |

---

## 📚 Ejemplos

### Ejemplo 1: Gestor de Tareas Desktop

```bash
python .agent/scripts/tauri-orchestrator.py \
  "Crear gestor de tareas multiplataforma (Windows/macOS/Linux) con React, \
   sincronización local, búsqueda, categorías, persistencia en SQLite, \
   tema oscuro/claro, atajos de teclado"

# Genera proyecto completo con:
# - Componentes React optimizados
# - Comandos Rust para BD
# - IPC communication
# - Security patterns aplicados
# - 80%+ test coverage
```

### Ejemplo 2: Agregar Feature

```bash
/agent tauri-frontend Agregar widget de gráficos con Chart.js

# Resultado:
# - Componente Chart.js integrado
# - Props type-safe
# - Responsive design
# - Performance optimizado
```

### Ejemplo 3: Auditoría de Seguridad

```bash
/agent security-auditor Revisar aplicación Tauri existente en ./my-app

# Output:
# - Vulnerabilidades encontradas
# - Recommendations
# - Security score
# - Remediation steps
```

---

## 🧠 Learning Engine en Acción

El Learning Engine **aprende automáticamente** de:

1. **Proyectos completados**
   - Patrones arquitectónicos exitosos
   - Decisiones de design recurrentes
   - Tech stacks populares

2. **Errores y soluciones**
   - Bugs comunes
   - Patrones que causan issues
   - Soluciones probadas

3. **Performance data**
   - Bundle sizes alcanzados
   - Startup times observados
   - Memory usage patterns

4. **Security incidents**
   - Vulnerabilidades descubiertas
   - Mitigaciones efectivas
   - Best practices actualizadas

**Mejora esperada:** 20-50% mensual

---

## 🔧 Configuración Avanzada

### Habilitar Learning Engine Auto-Evolving

```bash
# Configurar en .env
export TAURI_LEARNING_ENABLED=true
export TAURI_AUTO_SKILL_GENERATION=true
export TAURI_MEMORY_PERSISTENCE=".agent/agents/learning-engine/memory/"

# Ejecutar scheduled learning
python .agent/agents/learning-engine/scripts/main.py --schedule weekly
```

### Usar Prompts Personalizados

```bash
python .agent/scripts/tauri-orchestrator.py \
  --custom-orchestration-strategy "Priorizar seguridad sobre tamaño de bundle"
```

### Integración MCP

```json
{
  "mcpServers": {
    "tauri-agents": {
      "command": "python",
      "args": [".agent/scripts/tauri-orchestrator.py"],
      "description": "Orquestador Tauri"
    }
  }
}
```

---

## 📞 Soporte y Recursos

### Documentación
- 📖 Agentes: `.agent/agents/[agent-name]/IDENTITY.md`
- 📖 Skills: `.agent/skills/[skill-name]/SKILL.md`
- 📖 Arquitectura: `.agent/ARCHITECTURE.md`

### Tauri Official
- 🌐 Website: https://v2.tauri.app/
- 📚 Docs: https://docs.tauri.app/
- 💬 Community: https://tauri.app/en/community/

### Issues & Feedback
- 🐛 Reportar bugs: GitHub Issues
- 💡 Sugerencias: GitHub Discussions
- 🎉 Contribuir: Pull Requests

---

## 📈 Roadmap

### v1.0 (Actual)
✅ 4 agentes especializados
✅ 3 skills avanzados
✅ Learning Engine
✅ Orquestación inteligente

### v1.5 (Próximas semanas)
- [ ] Plugins nativos Swift/Kotlin
- [ ] CLI mejorada
- [ ] Templates de proyecto
- [ ] Integración con GitHub Actions

### v2.0 (Planificado)
- [ ] Marketplace de skills
- [ ] Contribuciones comunitarias
- [ ] AI-powered code review
- [ ] Predictive optimization

---

*Guía de Agentes Tauri v1.0 - Elite Edition*
*Creado: 2026-02-03*
*Compatible con Tauri 2.0+*
