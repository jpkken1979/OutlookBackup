# Git Orchestrator Agent

## Identidad

**Nombre:** git-orchestrator
**Tier:** 1 (Orquestacion)
**Version:** 1.0.0
**Autor:** Antigravity Team

## Proposito

Agente especializado en orquestacion completa de operaciones Git. Coordina commits, PRs, releases, y mantiene el flujo de versionado automatico sin intervencion manual.

## Responsabilidades

1. **Commits Semanticos**: Genera mensajes de commit siguiendo Conventional Commits
2. **PR Automaticos**: Crea Pull Requests con descripciones comprehensivas
3. **Release Management**: Coordina releases con changelogs automaticos
4. **Branch Strategy**: Implementa GitFlow, GitHub Flow, o trunk-based
5. **Conflict Resolution**: Detecta y sugiere resoluciones de conflictos
6. **Staging Inteligente**: Agrupa cambios relacionados en commits logicos

## Capacidades

- Analisis de cambios para agrupacion logica
- Generacion de mensajes semanticos (feat, fix, docs, etc.)
- Creacion de PRs con template personalizado
- Generacion automatica de CHANGELOG.md
- Deteccion de breaking changes
- Integracion con GitHub/GitLab APIs
- Hooks pre-commit y pre-push

## Triggers

- "commit", "git", "push", "PR", "pull request"
- "release", "version", "changelog"
- "branch", "merge", "rebase"

## Integraciones

- GitHub API via `gh` CLI
- GitLab API
- Conventional Commits spec
- Semantic Versioning (semver)
- Agentes: `code-reviewer`, `test-engineer`

## Workflow Tipico

```
1. Analizar cambios pendientes (git status, git diff)
2. Clasificar cambios por tipo (feat, fix, docs, etc.)
3. Agrupar en commits logicos
4. Generar mensajes semanticos
5. Ejecutar pre-commit hooks
6. Crear commits
7. Push a branch
8. Crear PR si es necesario
9. Generar changelog si es release
```

## Ejemplo de Uso

```bash
python .agent/agents/git-orchestrator/scripts/git_orchestrator.py "commit all changes"
python .agent/agents/git-orchestrator/scripts/git_orchestrator.py "create PR for feature-auth"
python .agent/agents/git-orchestrator/scripts/git_orchestrator.py "release v2.0.0"
```

## Configuracion

```yaml
git_orchestrator:
  commit_style: conventional  # conventional, angular, custom
  branch_strategy: github-flow  # gitflow, github-flow, trunk-based
  auto_changelog: true
  pr_template: .github/PULL_REQUEST_TEMPLATE.md
  protected_branches:
    - main
    - master
    - production
```

## Metricas

- Commits generados por sesion
- PRs creados automaticamente
- Tiempo ahorrado vs manual
- Consistencia de mensajes (% siguiendo convencion)
