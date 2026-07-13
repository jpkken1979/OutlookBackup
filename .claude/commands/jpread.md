# /jpread — Diagnóstico React con react-doctor

> Escanea el código React del proyecto con `react-doctor` (autor: Aiden Bai,
> creador de Million.js) y produce un reporte estructurado con score 0-100,
> errores críticos y top warnings.

## Qué hace

Cuando se invoca `/jpread` (con o sin args), Claude debe:

1. **Ejecutar** `npx -y react-doctor@latest --json` desde la raíz del proyecto
2. **Capturar** el JSON completo a un archivo temporal `.tmp-react-doctor-report.json`
3. **Analizar** el JSON con counters por categoría, regla y archivo
4. **Reportar** estructurado al usuario:
   - **Score** 0-100 (con label: Great / Needs work / Critical)
   - **Errores reales** (severity = error) — uno por línea con `archivo:linea` + mensaje truncado
   - **Top 10 categorías** con conteo
   - **Top 15 reglas** más recurrentes con `[plugin] rule`
   - **Top 10 archivos** más afectados
5. **Limpiar** el archivo temporal al finalizar
6. **NO aplicar fixes automáticamente** — para eso usar `/jp` con instrucción explícita

## Argumentos opcionales

```
/jpread              # Scan completo + reporte
/jpread --score      # Solo el número (rápido, sin análisis)
/jpread --json       # Volcar JSON crudo sin análisis (debugging)
/jpread --fix        # Después del scan, ofrece plan de fixes
```

## Qué es react-doctor

- **Paquete npm**: [react-doctor](https://www.npmjs.com/package/react-doctor)
- **Repo**: [millionco/react-doctor](https://github.com/millionco/react-doctor)
- **Autor**: Aiden Bai (creador de Million.js, persona pública del ecosistema React)
- **Naturaleza**: lint + dead-code + a11y + perf detector. Solo escanea, no
  modifica archivos.

## Qué detecta

- **State & Effects**: useEffect leaks, missing cleanup, prefer-useReducer, etc.
- **Performance**: bundle size, lazy loading, redundant renders
- **Architecture**: componentes gigantes, hooks mal usados
- **Accessibility**: WCAG 2.x, jsx-a11y reglas
- **Bundle Size**: tree-shaking, LazyMotion para framer-motion
- **Correctness**: anti-patterns React (no-array-index-as-key, hydration mismatch)
- **Dead Code**: vía `knip` (exports/types no usados)

## Seguridad

- `npx -y react-doctor@latest` baja y ejecuta código del paquete. Es legítimo
  (autor conocido, 47+ versiones publicadas), pero **NO** ejecutar variantes
  con typo (typosquatting): siempre `react-doctor`, no `reactdoctor`,
  `react-doctor-cli`, etc.
- El paquete **no modifica archivos del repo** en modo `--json`. Tampoco
  envía datos sin consentimiento — el flag `--offline` deshabilita telemetría.

## Comportamiento detallado

### 1. Pre-flight

Antes de ejecutar:
- Confirmar que hay código React en el repo (buscar `package.json` con
  dependencia `react`). Si no hay, abortar con mensaje claro.
- Verificar que `node` y `npx` están accesibles. Si no, agregar
  `C:\Program Files\nodejs` al `$env:PATH` (gotcha Windows del sandbox).

### 2. Ejecución

```powershell
$env:PATH = "C:\Program Files\nodejs;" + $env:PATH
& "C:\Program Files\nodejs\npx.cmd" -y react-doctor@latest --json `
    | Out-File -Encoding utf8 .tmp-react-doctor-report.json
```

Timeout sugerido: 10 minutos (proyectos grandes pueden tardar). En proyectos
chicos termina en < 5 segundos.

### 3. Análisis

Usar un script Python inline (vía `.venv\Scripts\python.exe`) que lea el JSON
y produzca el reporte:

```python
import json
from collections import Counter
from pathlib import Path

data = json.loads(Path(".tmp-react-doctor-report.json").read_text(encoding="utf-8"))
summary = data["summary"]
diagnostics = data["diagnostics"]

# Header
print(f"SCORE: {summary['score']}/100 ({summary['scoreLabel']})")
print(f"errors: {summary['errorCount']}, warnings: {summary['warningCount']}")
print(f"files affected: {summary['affectedFileCount']}")

# Errors (severity = error)
errors = [d for d in diagnostics if d.get("severity") == "error"]
for e in errors:
    print(f"  {e['filePath']}:{e['line']}  {e['message'][:120]}")

# Top categorias / reglas / archivos
for top, key in [
    ("CATEGORIA", lambda d: d.get("category")),
    ("REGLA", lambda d: f"[{d.get('plugin')}] {d.get('rule')}"),
    ("ARCHIVO", lambda d: d.get("filePath")),
]:
    print(f"Top {top}:")
    for k, count in Counter(map(key, diagnostics)).most_common(15):
        print(f"  {count}  {k}")
```

### 4. Reporte al usuario

Formato Markdown con tablas. Incluir interpretación:

- **Score ≥ 75**: estado verde, solo mejoras opcionales
- **Score 50-74**: needs work, priorizar errors + top warnings
- **Score < 50**: critical, plan de remediación obligatorio

### 5. Cleanup

`rm .tmp-react-doctor-report.json` al final, antes de devolver control.

## Reglas inquebrantables

| Regla | Por qué |
|---|---|
| `no_autofix_silencioso` | Nunca aplicar fixes sin confirmar con el usuario |
| `cleanup_temp_files` | El JSON temporal NO debe quedar en el working tree |
| `report_falsos_positivos` | Algunas reglas (ej. prefers-reduced-motion) pueden ser falsos positivos si el proyecto ya tiene MotionConfig. Verificar antes de reportar como bug |
| `tolerancia_sandbox` | Si el sandbox no tiene `node` en PATH, usar ruta absoluta `C:\Program Files\nodejs\npx.cmd` |

## Flujo completo

```
/jpread
    ↓
1. Pre-flight: node disponible? React en repo?
    ↓
2. npx -y react-doctor@latest --json > .tmp-react-doctor-report.json
    ↓
3. Python parsea JSON → counters
    ↓
4. Reporte markdown al usuario
    ↓
5. Cleanup temp file
    ↓
6. Si usuario quiere fixes: sugerir /jp con plan en milestones
```

## Integración con otros comandos

- `/jpread` → diagnóstico (read-only)
- `/jp "fixea los errors del reporte de react-doctor"` → ejecutar fixes
- `/aspirador` → limpieza de dead code (overlap con knip dentro de react-doctor)
- `/finalize` → cierre completo (NO incluye jpread por default)

## Output esperado

```
## React Doctor Report

**Score: X/100 (Label)** — N errors, M warnings en K archivos

### 🔴 Errores reales (severity=error)
| # | Archivo:línea | Problema |
|---|---|---|
| 1 | path/file.tsx:N | mensaje truncado |

### ⚠️ Top reglas
| Conteo | Plugin | Regla |

### 📊 Por categoría
[bloque con conteos]

### Recomendación
[texto breve sobre próximos pasos]
```

---

**version**: 1.0.0
**autor**: K. Kaneshiro (idea), Claude Opus 4.7 (implementación)
**fecha**: 2026-05-12
**tags**: `react, doctor, diagnostic, lint, accessibility, performance, ecosystem`
