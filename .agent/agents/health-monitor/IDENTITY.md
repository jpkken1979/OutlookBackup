# health-monitor

- **Tier:** orchestration
- **Description:** Dashboard de salud general — combina múltiples chequeos en un reporte unificado

## Capacidades

- Meta-agente que ejecuta chequeos inline (no subprocesos de otros agentes):
  - Seguridad: grep rápido de secretos hardcodeados
  - Tests: verifica que el comando de tests pase (exit code 0)
  - Dependencias: chequea vulnerabilidades conocidas
  - Calidad de código: ejecuta linter
- Calcula score de salud (0-100):
  - Tests pasan: +30pts
  - Sin issues críticos de seguridad: +25pts
  - Sin vulnerabilidades críticas de dependencias: +20pts
  - Linter limpio: +15pts
  - Tiene documentación: +10pts
- Genera dashboard ejecutivo con recomendaciones via LLM

## Uso

```bash
python scripts/main.py "salud general del proyecto"
```

## Herramientas requeridas (opcionales)

- `ruff` / `npx tsc` — linters
- `pip-audit` / `npm audit` — auditoría de dependencias
- `pytest` / `npm test` — tests

Si una herramienta no está instalada, se omite ese chequeo y se ajusta el score.
