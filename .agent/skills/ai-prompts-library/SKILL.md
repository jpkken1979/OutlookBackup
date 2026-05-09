---
name: ai-prompts-library
description: Biblioteca completa de system prompts filtrados de las principales IAs del mercado + herramientas avanzadas para crear, combinar y gestionar agentes IA.
type: feature
---

# AI Prompts Library - Sistema de Prompts de IA

## Descripción

Biblioteca completa de system prompts filtrados de las principales IAs del mercado + herramientas avanzadas para crear, combinar y gestionar agentes IA.

**Fuente de prompts:** [asgeirtj/system_prompts_leaks](https://github.com/asgeirtj/system_prompts_leaks)

## Características

- **107+ prompts** de Claude, GPT, Gemini, Grok y más
- **12 personalidades** configurables para agentes
- **Sistema de memoria** persistente
- **Generador de agentes** desde templates
- **Guardrails** de seguridad
- **Prompt Mixer** para combinar prompts

---

## CLI Unificado

```bash
# CLI principal - acceso a todas las herramientas
python ai_toolkit.py <comando>

# Ver ayuda
python ai_toolkit.py --help
```

| Comando | Descripción |
|---------|-------------|
| `personality` | Sistema de 12 personalidades |
| `research` | Investigación profunda automatizada |
| `memory` | Memoria persistente para agentes |
| `mix` | Mezclar y combinar prompts |
| `agent` | Crear agentes personalizados |
| `guard` | Verificar seguridad del contenido |
| `prompts` | Buscar en la biblioteca |
| `optimize` | **NUEVO** Optimizar prompts para Claude/GPT/Gemini/Grok |
| `workflow` | **NUEVO** Encadenar herramientas automáticamente |
| `stats` | Estadísticas del ecosistema |

---

## Herramientas

### 1. Personality Engine - Sistema de Personalidades

12 personalidades para tus agentes basadas en GPT-5.1 y Grok:

| Personalidad | Descripción |
|--------------|-------------|
| `default` | Balanceado y versátil |
| `professional` | Formal y orientado a negocios |
| `friendly` | Cálido y accesible |
| `nerdy` | Técnico y detallado |
| `cynical` | Directo y sin rodeos |
| `candid` | Honesto y transparente |
| `efficient` | Conciso, al grano |
| `quirky` | Creativo y único |
| `unfiltered` | Estilo Grok, sin filtros |
| `researcher` | Analítico y metódico |
| `mentor` | Paciente y educativo |
| `developer` | Enfocado en código |

```bash
# Listar personalidades
python ai_toolkit.py personality --list

# Aplicar personalidad a un prompt
python ai_toolkit.py personality --style nerdy --prompt "Explica qué es Python"

# Mezclar personalidades
python ai_toolkit.py personality --mix friendly,nerdy --prompt "Hola mundo"

# Exportar personalidad
python ai_toolkit.py personality --export professional
```

### 2. Deep Research Agent

Investigación automatizada basada en el sistema de OpenAI:

```bash
# Investigación rápida
python ai_toolkit.py research "Estado de la IA en 2025"

# Investigación profunda
python ai_toolkit.py research "Quantum computing" --depth comprehensive

# Guardar resultado
python ai_toolkit.py research "Machine Learning" --output report.md
```

**Profundidades disponibles:**
- `quick` - 1-2 minutos, puntos clave
- `standard` - 5-10 minutos, análisis balanceado
- `comprehensive` - 15-30 minutos, investigación exhaustiva

### 3. Memory Manager

Memoria persistente para agentes:

```bash
# Añadir memoria
python ai_toolkit.py memory add "Usuario prefiere Python"
python ai_toolkit.py memory add "Es desarrollador senior" --category facts --importance high

# Buscar memorias
python ai_toolkit.py memory search "preferencias"

# Listar todas
python ai_toolkit.py memory list

# Obtener contexto para inyección
python ai_toolkit.py memory context

# Ver categorías
python ai_toolkit.py memory categories
```

**Categorías de memoria:**
- `preferences` - Preferencias del usuario
- `context` - Contexto de proyecto
- `facts` - Hechos sobre usuario/proyecto
- `instructions` - Instrucciones específicas
- `learnings` - Aprendizajes
- `project` - Info del proyecto
- `temporary` - Temporal de sesión

### 4. Prompt Mixer

Combina prompts de diferentes IAs:

```bash
# Analizar un prompt
python ai_toolkit.py mix --analyze anthropic/claude-code.md

# Mezclar prompts
python ai_toolkit.py mix anthropic/claude-code.md openai/codex-cli.md --output hybrid.md

# Extraer patrones de un directorio
python ai_toolkit.py mix --patterns openai/

# Ver templates predefinidos
python ai_toolkit.py mix --templates
```

**Estrategias de mezcla:**
- `balanced` - Una sección de cada fuente
- `merge` - Combina todas las secciones
- `first` - Prioriza primera fuente

### 5. Agent Builder

Genera agentes personalizados:

```bash
# Crear agente
python ai_toolkit.py agent create "code-reviewer" --base claude-code --personality cynical

# Listar bases disponibles
python ai_toolkit.py agent bases

# Listar agentes creados
python ai_toolkit.py agent list

# Preview de agente
python ai_toolkit.py agent preview "code-reviewer"
```

**Bases de agentes disponibles:**
- `claude-code` - Asistente de código estilo Claude
- `gpt-agent` - Agente autónomo estilo GPT-5
- `deep-research` - Investigación profunda
- `grok-unfiltered` - Directo estilo Grok
- `coding-mentor` - Mentor de programación
- `devops-agent` - Especialista DevOps
- `data-analyst` - Análisis de datos

### 6. Guardrails System

Sistema de seguridad para agentes:

```bash
# Verificar contenido
python ai_toolkit.py guard check "Cómo hackear un servidor"

# Listar reglas
python ai_toolkit.py guard rules

# Generar prompt de seguridad
python ai_toolkit.py guard prompt
```

**Categorías de seguridad:**
- `safety` - Contenido dañino
- `privacy` - Información personal
- `legal` - Actividades ilegales
- `accuracy` - Desinformación
- `compliance` - Disclaimers requeridos
- `security` - Inyección de código
- `ethics` - Prevención de sesgos

### 7. Prompt Optimizer (NUEVO)

Optimiza automáticamente tus prompts según la IA destino:

```bash
# Optimizar para Claude
python ai_toolkit.py optimize "Crea una función que ordene números" --target claude

# Optimizar para GPT
python ai_toolkit.py optimize "Explica qué es React" --target gpt

# Comparar todas las IAs
python ai_toolkit.py optimize "Tu prompt" --compare

# Modo interactivo
python ai_toolkit.py optimize --interactive

# Desde archivo
python ai_toolkit.py optimize --file mi_prompt.txt --target gemini --output optimizado.txt
```

**Targets disponibles:**

| IA | Formato | Estilo |
|----|---------|--------|
| `claude` | XML tags | Estructurado, step-by-step |
| `gpt` | Markdown | Rol definido, personalidad |
| `gemini` | Estructurado | Safety considerations |
| `grok` | Directo | Sin filtros, honesto |
| `local` | Mínimo | Eficiente en contexto |

### 8. Workflow Engine (NUEVO)

Encadena herramientas automáticamente:

```bash
# Listar workflows predefinidos
python ai_toolkit.py workflow --list

# Usar preset
python ai_toolkit.py workflow --preset safe-prompt --input "mi prompt"

# Cadena personalizada
python ai_toolkit.py workflow "guard,optimize,memory" --input "texto"
```

**Presets disponibles:**

| Preset | Cadena | Descripción |
|--------|--------|-------------|
| `safe-prompt` | guard → optimize | Verifica y optimiza |
| `research-deep` | research → memory | Investiga y guarda |
| `agent-create` | personality → agent → guard | Crea agente seguro |

---

## Estructura de Archivos

```
ai-prompts-library/
├── ai_toolkit.py           # CLI unificado
├── SKILL.md                # Esta documentación
├── catalog.json            # Índice de prompts
│
├── tools/                  # Herramientas
│   ├── personality_engine.py
│   ├── deep_research.py
│   ├── memory_manager.py
│   ├── prompt_mixer.py
│   ├── agent_builder.py
│   ├── guardrails.py
│   ├── prompt_optimizer.py # NUEVO: Optimizador de prompts
│   └── search_prompts.py   # Buscador de prompts
│
├── memory/                 # Almacenamiento de memoria
├── agents/                 # Agentes generados
├── guardrails/             # Reglas de seguridad
│
├── anthropic/              # 22 prompts de Claude
├── openai/                 # 51 prompts de GPT
├── google/                 # 13 prompts de Gemini
├── xai/                    # 5 prompts de Grok
├── perplexity/             # 2 prompts
├── proton/                 # 2 prompts
└── misc/                   # 8 prompts varios
```

---

## Buscar Prompts

```bash
# Estadísticas
python ai_toolkit.py prompts --stats

# Buscar por palabra clave
python ai_toolkit.py prompts "memory"

# Listar por proveedor
python ai_toolkit.py prompts --provider openai --list

# Buscador directo
python scripts/search_prompts.py "tool" --provider openai --content
```

---

## Ejemplos de Uso Avanzado

### Crear un agente de code review personalizado

```bash
# 1. Crear agente base
python ai_toolkit.py agent create code-reviewer --base claude-code --personality cynical

# 2. Ver el prompt generado
python ai_toolkit.py agent preview code-reviewer

# 3. Añadir memoria de preferencias
python ai_toolkit.py memory add "Siempre verificar tipos de TypeScript" --category instructions
python ai_toolkit.py memory add "Priorizar performance sobre legibilidad" --category preferences
```

### Crear un investigador especializado

```bash
# 1. Investigar un tema
python ai_toolkit.py research "Arquitecturas de microservicios" --depth comprehensive

# 2. Crear agente de investigación
python ai_toolkit.py agent create tech-researcher --base deep-research --personality nerdy

# 3. Mezclar con capacidades de código
python ai_toolkit.py mix openai/tool-deep-research.md anthropic/claude-code.md -o research-coder.md
```

### Verificar seguridad de respuestas

```bash
# Verificar antes de enviar
python ai_toolkit.py guard check "SELECT * FROM users WHERE password = 'admin'"

# Generar prompt de seguridad para agente
python ai_toolkit.py guard prompt >> my_agent_prompt.md
```

---

## Estadísticas del Ecosistema

| Métrica | Valor |
|---------|-------|
| Prompts de IA | 107+ |
| Proveedores | 7 |
| Personalidades | 12 |
| Bases de agentes | 7 |
| Reglas de seguridad | 10+ |
| Categorías de memoria | 7 |
| Herramientas | 9 |
| Targets de optimización | 5 |
| Workflows predefinidos | 3 |
| Agentes mejorados | 20 |

---

## Casos de Uso

1. **Desarrollo de agentes** - Usar prompts como referencia y bases
2. **Personalización** - Aplicar diferentes estilos a tus agentes
3. **Seguridad** - Verificar contenido con guardrails
4. **Investigación** - Automatizar research con Deep Research
5. **Memoria** - Mantener contexto entre sesiones
6. **Híbridos** - Combinar lo mejor de cada IA

---

*AI Prompts Library v2.0 - Ecosistema Antigravity*
*Actualizado: 2026-01-31*
