# /agent - Invocar Agente Especializado

Invoca un agente específico del ecosistema Antigravity para realizar una tarea.

## Uso

```
/agent <nombre_agente> [descripción_tarea]
```

## Agentes Disponibles

| Agente | Descripción |
|--------|-------------|
| `planner` | Crea planes de ejecución con múltiples agentes |
| `critic` | Cuestiona y valida decisiones antes de implementar |
| `explorer` | Investiga código existente en profundidad |
| `architect` | Diseña arquitectura y previene deuda técnica |
| `api-designer` | Diseña APIs REST/GraphQL con OpenAPI |
| `ui-ux-designer` | Evalúa y mejora UI/UX |
| `react-specialist` | Experto en React y patrones |
| `security-auditor` | Audita seguridad (OWASP) |
| `a11y` | Audita accesibilidad (WCAG) |
| `i18n` | Internacionalización |
| `refactor` | Refactoriza código |
| `dependency` | Analiza dependencias |
| `memory` | Guarda/carga contexto |
| `stuck` | Escala problemas al usuario |

## Ejemplos

```bash
# Planificar una nueva feature
/agent planner Crear sistema de autenticación con OAuth

# Revisar una decisión de arquitectura
/agent critic Evaluar si usar microservicios o monolito

# Explorar código antes de modificar
/agent explorer Analizar el módulo de pagos

# Diseñar una API
/agent api-designer Diseñar endpoints para gestión de usuarios

# Auditar seguridad
/agent security-auditor Revisar autenticación y autorización
```

## Cómo Funciona

1. Lee el archivo `IDENTITY.md` del agente especificado
2. Adopta la personalidad y proceso del agente
3. Ejecuta la tarea siguiendo las instrucciones del agente
4. Produce output en el formato definido por el agente

## Invocar Múltiples Agentes

Para tareas complejas, usa el orquestador:

```bash
python .agent/scripts/orchestrator.py "Tu tarea compleja aquí"
```

O invoca el agente `planner` que creará un plan con múltiples agentes:

```
/agent planner Migrar la aplicación de JavaScript a TypeScript
```
