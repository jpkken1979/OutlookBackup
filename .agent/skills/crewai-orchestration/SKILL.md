---
name: crewai-orchestration
description: "Orquestación multi-agente inspirada en CrewAI. Permite definir crews de agentes con roles, tareas y workflows colaborativos."
type: feature
category: ai
version: "1.0.0"
author: Antigravity Team
source: internal
dependencies: []
related_skills: [agent-orchestration, agent-memory-systems]
keywords: [crewai, multi-agent, orchestration, collaboration, workflow, crew]
tier: 1
---

# CrewAI Orchestration Skill

Orquestación de equipos de agentes inspirada en [CrewAI](https://github.com/crewAIInc/crewAI), el framework líder de multi-agentes.

## Conceptos Clave

### Crew (Equipo)
Un grupo de agentes que colaboran en una tarea común.

### Agent (Agente)
Un agente especializado con:
- **Role**: Su función en el equipo
- **Goal**: Su objetivo principal
- **Backstory**: Contexto que informa su comportamiento

### Task (Tarea)
Una unidad de trabajo asignada a un agente con:
- **Description**: Qué hacer
- **Expected Output**: Formato de resultado esperado
- **Agent**: Quién la ejecuta

## Uso

### Definir un Crew via YAML

```yaml
# crew.yaml
crew:
  name: "Code Review Crew"
  process: sequential  # sequential | parallel | hierarchical

agents:
  - name: code_reviewer
    role: "Senior Code Reviewer"
    goal: "Find bugs and improve code quality"
    backstory: "Expert developer with 10 years experience"
    tools: [code-reviewer, security-auditor]

  - name: test_engineer
    role: "Test Engineer"
    goal: "Ensure comprehensive test coverage"
    backstory: "QA specialist focused on edge cases"
    tools: [test-engineer]

tasks:
  - name: review_code
    description: "Review the pull request for bugs and issues"
    agent: code_reviewer
    expected_output: "List of issues with severity and suggestions"

  - name: generate_tests
    description: "Generate tests for new/changed code"
    agent: test_engineer
    context: [review_code]  # Depends on previous task
    expected_output: "Test file with pytest tests"
```

### Ejecutar un Crew

```bash
python scripts/crewai_orchestration.py run --config crew.yaml --input "Review PR #123"
```

### Ejecutar desde Python

```python
from crewai_orchestration import Crew, Agent, Task

# Define agents
reviewer = Agent(
    role="Code Reviewer",
    goal="Find issues in code",
    backstory="Senior developer"
)

tester = Agent(
    role="Test Engineer",
    goal="Generate tests",
    backstory="QA specialist"
)

# Define tasks
review_task = Task(
    description="Review the code changes",
    agent=reviewer,
    expected_output="Issue list"
)

test_task = Task(
    description="Generate tests",
    agent=tester,
    context=[review_task],
    expected_output="Test file"
)

# Create and run crew
crew = Crew(
    agents=[reviewer, tester],
    tasks=[review_task, test_task],
    process="sequential"
)

result = crew.kickoff(inputs={"code": "path/to/code"})
```

## Procesos de Ejecución

### Sequential
Los agentes ejecutan tareas en orden, pasando contexto al siguiente.

```
Agent1 → Task1 → Result1 → Agent2 → Task2 → Result2
```

### Parallel
Los agentes ejecutan tareas simultáneamente cuando no hay dependencias.

```
Agent1 → Task1 ─┐
                ├→ Combine → Final
Agent2 → Task2 ─┘
```

### Hierarchical
Un agente manager coordina a los demás.

```
        Manager
       ↙   ↓   ↘
    Agent1 Agent2 Agent3
```

## Memoria Compartida

El crew mantiene memoria compartida para:
- **Short-term**: Contexto de la sesión actual
- **Long-term**: Aprendizajes persistentes
- **Entity**: Información sobre entidades mencionadas

## Integración con Antigravity Agents

Este skill mapea automáticamente agentes de Antigravity:

| CrewAI Role | Antigravity Agent |
|-------------|-------------------|
| Code Reviewer | code-reviewer |
| Security Expert | security-auditor |
| Test Engineer | test-engineer |
| Architect | architect |
| Planner | planner |

## Ejemplos de Crews

### PR Review Crew
```yaml
crew:
  name: "PR Review"
  agents: [code-reviewer, security-auditor, test-engineer]
  process: sequential
```

### Feature Development Crew
```yaml
crew:
  name: "Feature Development"
  agents: [planner, architect, backend-specialist, frontend-specialist, test-engineer]
  process: hierarchical
  manager: planner
```

### Security Audit Crew
```yaml
crew:
  name: "Security Audit"
  agents: [security-auditor, debugger, performance-optimizer]
  process: parallel
```

---

*Inspirado en CrewAI v0.152.0 - Framework líder en orquestación multi-agente*
