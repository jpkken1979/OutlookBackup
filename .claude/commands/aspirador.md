# /aspirador — Auditoría exhaustiva, limpieza segura y recomendaciones

Limpia el proyecto de código muerto, archivos zombie, imports sin usar y deuda técnica
**sin romper nada**. Cada eliminación se verifica con tests antes de continuar.

---

## FILOSOFÍA

> "Borrar código es fácil. Borrar código sin romper nada es arte."

Reglas de oro:
1. **Nunca borres algo si no puedes verificar que está muerto** — busca en todo el proyecto
2. **Siempre testea después de cada eliminación**, no en lote al final
3. **Si los tests fallan después de borrar algo**, restaura inmediatamente con `git checkout`
4. **Documenta todo** lo que encontraste aunque no lo borres
5. Lo que no puedas eliminar con seguridad → lo marcas en el reporte, no lo tocas

---

## FASE 1 — Snapshot y baseline de tests

### 1.1 Estado inicial
```bash
git status
git stash  # si hay cambios sin commitear — preguntar al usuario primero
```

### 1.2 Tests baseline (deben pasar todos ANTES de empezar)
```bash
python -m pytest tests/ -x --tb=short -q 2>&1 | tail -10
cd nexus-app && npm test -- --run 2>&1 | tail -10
cd nexus-app && npx tsc -b tsconfig.app.json --noEmit 2>&1 | head -10
```

**Si los tests base fallan → DETENTE**. No puedes auditar código si ya hay tests rotos.
Reporta los fallos y pide instrucciones al usuario.

---

## FASE 2 — Auditoría de código muerto

### 2.1 Python — imports sin usar
```bash
python -m ruff check .agent/ --select F401 --output-format=text 2>&1 | head -50
```

### 2.2 Python — funciones/variables sin usar
```bash
python -m ruff check .agent/ --select F811,F841,ARG001,ARG002 --output-format=text 2>&1 | head -50
```

### 2.3 TypeScript — exports sin usar
```bash
cd nexus-app && npx ts-unused-exports tsconfig.app.json 2>&1 | head -30
# si no está instalado: npx -y ts-unused-exports tsconfig.app.json
```

### 2.4 TypeScript — imports sin usar
```bash
cd nexus-app && npm run lint -- --rule '{"@typescript-eslint/no-unused-vars": "error"}' 2>&1 | head -30
```

### 2.5 Archivos que nadie importa
Busca archivos `.py`, `.ts`, `.tsx` que no sean importados ni referenciados:
- Para Python: usa `grep -r "import <nombre_modulo>"` para cada archivo sospechoso
- Para TS/TSX: usa `grep -r "from.*<nombre_archivo>"` en el directorio

### 2.6 Archivos legacy y backups
```bash
find . -name "*.bak" -o -name "*.bak.*" -o -name "*_old*" -o -name "*_legacy*" \
       -o -name "*_deprecated*" -o -name "*.tmp" 2>/dev/null \
       | grep -v node_modules | grep -v .git
```

### 2.7 Código comentado en bloque (potencialmente zombie)
```bash
grep -rn "^#.*def \|^#.*class \|^//.*function\|^//.*class" \
     --include="*.py" --include="*.ts" --include="*.tsx" \
     --exclude-dir=node_modules --exclude-dir=.git \
     | head -30
```

### 2.8 TODOs, FIXMEs y HACKs acumulados
```bash
grep -rn "TODO\|FIXME\|HACK\|XXX\|DEPRECATED\|REMOVE ME" \
     --include="*.py" --include="*.ts" --include="*.tsx" --include="*.rs" \
     --exclude-dir=node_modules --exclude-dir=.git \
     | head -50
```

### 2.9 Dependencias sin usar en Python
```bash
# Lista deps en pyproject.toml que no aparecen en ningún import
python -c "
import re, os
deps = open('pyproject.toml').read()
imports_used = set()
for root, dirs, files in os.walk('.agent'):
    dirs[:] = [d for d in dirs if d not in ['__pycache__','.git']]
    for f in files:
        if f.endswith('.py'):
            for line in open(os.path.join(root,f), errors='ignore'):
                m = re.match(r'\s*(?:import|from)\s+(\w+)', line)
                if m: imports_used.add(m.group(1))
print('Imports usados:', sorted(imports_used)[:30])
" 2>/dev/null
```

### 2.10 node_modules fantasma y deps sin usar (JS/TS)
```bash
cd nexus-app && npx depcheck 2>&1 | head -30
# si no está: npx -y depcheck
```

---

## FASE 3 — Clasificación de hallazgos

Antes de eliminar nada, clasifica todo lo encontrado en 3 categorías:

### 🔴 ELIMINAR CON SEGURIDAD
Criterios para marcar como seguro eliminar:
- El símbolo no aparece en ningún `import`, `from`, `require` en todo el proyecto
- No es un punto de entrada público (no está en `__init__.py`, no es un MCP tool, no es un comando CLI)
- No es referenciado en documentación activa
- Los tests pasan después de eliminarlo

### 🟡 REVISAR — podría eliminarse pero requiere confirmación
- Está comentado pero el código activo lo rodea
- Tiene nombre genérico que podría confundirse con algo activo
- Está en un archivo de interfaces/tipos donde los IDEs a veces no detectan el uso

### 🟢 DEJAR — parece muerto pero NO tocar
- Es infraestructura de fallback o modo offline
- Es un mock/stub intencional para tests
- Está marcado con `# keep` o similar
- Es código de compatibilidad backward

**Muestra la clasificación completa al usuario y pide confirmación antes de eliminar.**

---

## FASE 4 — Eliminación segura (one-by-one)

Para **cada ítem** de la categoría 🔴:

```
1. Anota exactamente qué vas a eliminar
2. Elimínalo
3. Ejecuta los tests relevantes inmediatamente:
   - Si es Python: pytest tests/ -x -q --tb=short
   - Si es TS: npx tsc --noEmit + npm test
   - Si es Rust: cargo check
4. ¿Tests pasan?
   → SÍ: continúa con el siguiente ítem
   → NO: git checkout <archivo> inmediatamente, mueve a categoría 🟢 con nota del error
```

Nunca elimines más de 5 cosas antes de correr tests. Preferiblemente una por una si son archivos grandes.

---

## FASE 5 — Auditoría de seguridad rápida

Busca patrones peligrosos que hayan podido quedar:

```bash
# Secrets hardcodeados
grep -rn "api_key\s*=\s*['\"][a-zA-Z0-9]" --include="*.py" --include="*.ts" \
     --exclude-dir=node_modules --exclude-dir=.git | grep -v ".env" | head -20

# shell=True en subprocess
grep -rn "shell=True" --include="*.py" --exclude-dir=node_modules | head -10

# eval() activo
grep -rn "eval(" --include="*.py" --include="*.ts" \
     --exclude-dir=node_modules --exclude-dir=.git | grep -v "^\s*#\|^\s*//" | head -10

# print/console.log de debug olvidados con datos sensibles
grep -rn "print(.*password\|print(.*token\|console.log(.*key" \
     --include="*.py" --include="*.ts" --exclude-dir=node_modules | head -10
```

---

## FASE 6 — Análisis de calidad y recomendaciones

### 6.1 Archivos demasiado grandes (candidatos a dividir)
```bash
find .agent/ nexus-app/src/ src/ -name "*.py" -o -name "*.ts" -o -name "*.tsx" \
     | xargs wc -l 2>/dev/null | sort -rn | head -15
```
Archivos > 500 líneas en Python o > 400 en TS son candidatos a refactorizar.

### 6.2 Funciones duplicadas
Busca funciones con nombres muy similares o que hacen lo mismo:
```bash
grep -rn "^def \|^async def \|^export function\|^export async function" \
     --include="*.py" --include="*.ts" --include="*.tsx" \
     --exclude-dir=node_modules --exclude-dir=.git \
     | awk -F: '{print $NF}' | sort | uniq -d | head -20
```

### 6.3 Complejidad alta (Python)
```bash
python -m ruff check .agent/ --select C901 --output-format=text 2>&1 | head -20
```

### 6.4 Type safety (Python)
```bash
python -m mypy .agent/core --ignore-missing-imports --no-error-summary 2>&1 | \
     grep "error:" | wc -l
```

### 6.5 Dependencias desactualizadas
```bash
pip list --outdated 2>/dev/null | head -15
cd nexus-app && npm outdated 2>/dev/null | head -15
```

---

## FASE 7 — Reporte final

Genera un reporte completo en este formato:

```
═══════════════════════════════════════════════
🧹 REPORTE ASPIRADOR — [FECHA]
═══════════════════════════════════════════════

📊 RESUMEN
  Archivos analizados: X
  Items encontrados: X
  Eliminados: X
  Descartados (necesarios): X
  Tests antes: X pasando
  Tests después: X pasando

🗑️ ELIMINADO
  - archivo.py:45 — función dead_function() sin uso desde hace 3 meses
  - nexus-app/src/old-component.tsx — componente no importado en ningún lugar
  [...]

⚠️ ENCONTRADO PERO NO ELIMINADO (requiere decisión manual)
  - .agent/core/old_system.py — parece legacy pero es referenciado en docs
  - src/utils/helper.ts — exporta 3 funciones, 1 sin usar pero 2 activas
  [...]

🔐 SEGURIDAD
  [hallazgos de seguridad o "ninguno encontrado"]

📋 RECOMENDACIONES
  1. [recomendación técnica concreta con archivo y línea]
  2. [...]

💡 MEJORAS SUGERIDAS (no urgentes)
  1. [sugerencia de arquitectura, refactor, etc.]
  2. [...]

🎯 PRÓXIMOS PASOS SUGERIDOS
  1. [acción concreta priorizada]
  2. [...]
═══════════════════════════════════════════════
```

---

## FASE 8 — Commit de limpieza

Si se eliminó código:

```bash
git add -u  # solo archivos modificados/eliminados, nunca archivos nuevos no revisados
git commit -m "chore(cleanup): eliminar código muerto detectado por aspirador

[lista de lo eliminado]

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**No incluyas en este commit** cambios funcionales — solo limpieza.

---

## Opciones de invocación

```
/aspirador              → auditoría completa (todas las fases)
/aspirador --solo-audit → solo fases 1-3 (reporte sin eliminar nada)
/aspirador --rapido     → solo imports/exports sin usar + seguridad
/aspirador --seguridad  → solo fase 5 (auditoría de seguridad)
```

---

## Compatibilidad

Este comando funciona con:
- Claude Code (`/aspirador`)
- Cursor — pega el contenido como prompt de sistema
- Windsurf, GitHub Copilot, cualquier AI — las fases son autoexplicativas
- También ejecutable manualmente siguiendo las fases en orden
