---
name: plugin-eval-skill
description: Framework de evaluación de 3 capas para skills y agentes Antigravity
trigger: "evaluar skill" OR "evaluar agente" OR "calidad de skill" OR "certificar skill"
---

# PluginEval — Antigravity Skill Evaluator

Usa este skill para evaluar la calidad de skills y agentes del ecosistema Antigravity.

## Cuando usar

- Antes de instalar o usar un skill nuevo del ecosistema
- Para auditar skills huérfanos o inflados
- Para certificar calidad antes de merge
- Para comparar skills similares

## Qué hace

Ejecuta evaluación en 3 capas:

1. **Static Analysis** (<2s, gratis) — análisis determinístico
2. **LLM Judge** (~30s) — evaluación semántica con Haiku + Sonnet
3. **Monte Carlo** (2-6 min) — simulación estadística con 50 runs

## 10 Dimensiones de Calidad

| Dimensión | Peso | Qué mide |
|---|---|---|
| triggering_accuracy | 25% | ¿Se activa para prompts correctos? |
| orchestration_fitness | 20% | ¿Es worker composable? |
| output_quality | 15% | ¿Produce output útil y correcto? |
| scope_calibration | 12% | ¿Scope bien calibrado? |
| progressive_disclosure | 10% | ¿Usa references/ para contenido pesado? |
| token_efficiency | 6% | ¿Es conciso sin repetición? |
| robustness | 5% | ¿Maneja inputs variados? |
| structural_completeness | 3% | ¿Tiene headings y code blocks? |
| code_template_quality | 2% | ¿Los ejemplos son production-ready? |
| ecosystem_coherence | 2% | ¿Linkea a skills/agents relacionados? |

## Badges

| Badge | Score | Elo |
|---|---|---|
| Platinum | ≥90% | ≥1600 |
| Gold | ≥80% | ≥1500 |
| Silver | ≥70% | ≥1400 |
| Bronze | ≥60% | ≥1300 |

## Anti-Patrones Detectados

- **BLOATED_SKILL**: >800 líneas sin progressive disclosure
- **MISSING_TRIGGER**: Sin "Use when..." trigger phrase
- **EMPTY_DESCRIPTION**: Descripción <20 chars
- **OVER_CONSTRAINED**: >15 MUST/ALWAYS/NEVER

## CLI Usage

```bash
# Quick: solo estática (<2s)
py -3 -m plugin_eval.cli score .agent/skills/custom/mi-skill --depth quick

# Standard: estática + LLM (~30s)
py -3 -m plugin_eval.cli score .agent/skills/custom/mi-skill --depth standard

# Deep: 3 capas (~3 min, ~54 LLM calls)
py -3 -m plugin_eval.cli score .agent/skills/custom/mi-skill --depth deep

# Certificación (deep + threshold 70%)
py -3 -m plugin_eval.cli certify .agent/skills/custom/mi-skill

# Batch evaluation
py -3 -m plugin_eval.cli batch .agent/skills/custom/ --depth standard
```

## Integración con Brain

Después de evaluar, los resultados se ingestan al Brain como:
- `node_type: pattern`
- `area: plugin-eval`
- `tags: [plugin-eval, badge:{badge}, anti-pattern:{flags}]`

Para recall: `/recall evaluar skill calidad`
