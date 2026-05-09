# Skills & Agentes Inventory - AntigravitiSkillUSN

**Última actualización:** 2026-02-10
**Ubicación centralizada:** `C:\Users\kenji\AntigravitiSkillUSN\.agent\skills-custom\`

---

## 📦 Skills Centralizados (6 Total)

### 1. ⭐ startup
**Estado:** ✅ CENTRALIZADO
**Ubicación:** `.agent/skills-custom/startup/`
**Archivos:**
- `SKILL.md`

**Función:** Verifica entorno (Python, npm, .env) y lanza servidores FastAPI + React
**Triggers:** "startup", "iniciar servidores", "start servers", "launch"
**Uso:**
```bash
/startup
```

---

### 2. ⭐ finalizar
**Estado:** ✅ CENTRALIZADO
**Ubicación:** `.agent/skills-custom/finalizar/`
**Archivos:**
- `SKILL.md`

**Función:** Workflow de finalización: tests → docs → lint → commit → push
**Triggers:** "finalizar", "finish", "done", "completado"
**Uso:**
```bash
/finalizar
/finalizar --dry-run
/finalizar --skip-tests
```

---

### 3. ⭐⭐ finalizar-autonomo (FLAGSHIP)
**Estado:** ✅ CENTRALIZADO + COMPONENTES GLOBALES
**Ubicación:** `.agent/skills-custom/finalizar-autonomo/` (SKILL.md)
**Componentes Globales (MANTENER EN GLOBAL):**
- `~/.claude/finalizar` (wrapper CLI)
- `~/.claude/skills/finalizar-autonomo/script.py`
- `~/.claude/skills/finalizar-autonomo/api.py`
- `~/.claude/skills/finalizar-autonomo/auto-update.py`
- `~/.claude/skills/finalizar-autonomo/docker-compose.yml`
- `~/.claude/skills/finalizar-autonomo/Dockerfile`
- `~/.github/workflows/finalizar-autonomo.yml`

**Función:**
- 7 fases autónomas (cambios → tests → docs → lint → commit → push → reporte)
- Sincronización remota (fetch → sync → resolve conflictos → pull → push)
- REST API (Flask)
- Docker containerización
- GitHub Actions CI/CD

**Formas de Uso:**
```bash
# CLI
./finalizar
./finalizar auto-update
./finalizar api --port 5000

# Python directo
python ~/.claude/skills/finalizar-autonomo/script.py
python ~/.claude/skills/finalizar-autonomo/api.py

# Docker
docker-compose run --rm finalizer-cli

# GitHub Actions (automático)
git push origin main
```

**Portabilidad:**
- ✅ CLI standalone
- ✅ API REST
- ✅ Docker
- ✅ GitHub Actions
- ✅ Cualquier LLM (no solo Claude)

---

### 4. ⭐ type-validation (NUEVO)
**Estado:** ✅ CENTRALIZADO
**Ubicación:** `.agent/skills-custom/type-validation/`
**Archivos:**
- `SKILL.md` (enfoque ONE FILE AT A TIME)
- `validate_types.py` (script helper)
- `QUICK_START.md` (guía rápida)

**Función:** Previene type errors con mypy, crea plans secuenciales
**Triggers:** "type error", "mypy", "type check", "type validation"
**Uso:**
```bash
/type-validation
python .agent/skills-custom/type-validation/validate_types.py <archivo.py>
```

**Patrón:** ONE FILE AT A TIME (ejecutar mypy en 1 archivo, arreglarlo completamente, luego siguiente)

---

### 5. debug-server
**Estado:** ✅ CENTRALIZADO
**Ubicación:** `.agent/skills-custom/debug-server/`
**Archivos:**
- `SKILL.md`

**Función:** Diagnostica problemas de servidores (puertos, CORS, .env, conexión)
**Triggers:** "debug server", "server error", "port in use", "CORS error"
**Uso:**
```bash
/debug-server "No puedo conectarme a localhost:8000"
```

---

### 6. excel-parsing
**Estado:** ✅ CENTRALIZADO
**Ubicación:** `.agent/skills-custom/excel-parsing/`
**Archivos:**
- `SKILL.md`

**Función:** Mejores prácticas para parsear Excel (headers, whitespace, validación)
**Triggers:** "Excel", "xlsx", "parse Excel", "data import"
**Uso:**
```bash
/excel-parsing "Necesito leer archivo.xlsx con..."
```

---

## 🔧 Configuración

### Project-Level
**Ubicación:** `.agent/skills-custom/skill-rules.json`
- Configuración de triggers para 7 skills
- Enforcement levels
- Priority levels
- Portability specs

### Global Level (Se Mantiene)
**Ubicación:** `~/.claude/skills/skill-rules.json`
- Skills globales (startup, finalizar, etc.)
- Configuración global
- NOTA: finalizar-autonomo también está aquí (síncrono)

---

## 📊 Flujo de Trabajo Recomendado

### Para Desarrollo Normal
```
1. /startup          → Verificar entorno
2. [Desarrollo]
3. /finalizar        → Finalizar sesión
```

### Para Type Checking
```
1. /type-validation
2. "Ejecuta mypy en <archivo.py>"
3. Arreglar UN archivo a la vez
4. Verificar que mypy dice "Success"
5. Siguiente archivo
```

### Para Debugging
```
1. /debug-server "Descripción del problema"
2. Implementar fixes
3. /startup (reiniciar si needed)
```

### Para Automatización CI/CD
```
# Automático en push
git push origin main
→ .github/workflows/finalizar-autonomo.yml ejecuta automáticamente
```

---

## 📋 Checklist: Acceso Rápido

### Cuándo Necesitas...
| Necesidad | Comando |
|-----------|---------|
| Iniciar servidores | `/startup` |
| Finalizar sesión | `/finalizar` |
| Validar tipos | `/type-validation` |
| Debug problemas | `/debug-server "..."` |
| Parsear Excel | `/excel-parsing "..."` |
| Automatización CI/CD | `git push` (automático) |

---

## 🚀 Próximas Actividades

### Tareas Activas
- [ ] Ejecutar /startup en AntigravitiSkillUSN
- [ ] Usar /type-validation para validar módulos Python
- [ ] Implementar /finalizar-autonomo en CI/CD

### Mejoras Futuras
- [ ] Agregar más skills especializados
- [ ] Integrar analytics de skills
- [ ] Dashboard de automatización
- [ ] Pre-commit hooks con type-validation

---

## 📁 Estructura Física

```
AntigravitiSkillUSN/
└── .agent/
    └── skills-custom/
        ├── startup/
        │   └── SKILL.md
        ├── finalizar/
        │   └── SKILL.md
        ├── finalizar-autonomo/
        │   └── SKILL.md
        ├── type-validation/
        │   ├── SKILL.md
        │   ├── validate_types.py
        │   └── QUICK_START.md
        ├── debug-server/
        │   └── SKILL.md
        ├── excel-parsing/
        │   └── SKILL.md
        ├── skill-rules.json
        └── INVENTORY.md (este archivo)

TAMBIÉN EXISTEN GLOBALMENTE (Mantener):
~/.claude/
├── finalizar (wrapper CLI)
└── skills/
    ├── finalizar-autonomo/
    │   ├── script.py
    │   ├── api.py
    │   ├── auto-update.py
    │   ├── docker-compose.yml
    │   └── Dockerfile
    └── skill-rules.json

.github/
└── workflows/
    └── finalizar-autonomo.yml
```

---

## 🔄 Sincronización Global vs Proyecto

### En Global (~/.claude/)
- Wrapper CLI: `.claude/finalizar`
- Skills usables globalmente en cualquier proyecto
- Configuración compartida

### En Proyecto (AntigravitiSkillUSN/.agent/skills-custom/)
- Documentación centralizada
- Quick reference
- Inventario
- skill-rules.json local

### Estrategia
- **Código:** Global (reutilizable)
- **Documentación:** Proyecto (accesible localmente)
- **Triggers:** Ambos (Global + Proyecto)

---

## ✅ Verificación

Para verificar que todo está centralizado:

```bash
# Verificar skills locales
ls -la .agent/skills-custom/

# Verificar skill-rules.json
cat .agent/skills-custom/skill-rules.json

# Verificar scripts globales
ls -la ~/.claude/skills/finalizar-autonomo/
```

---

**Status:** ✅ COMPLETAMENTE CENTRALIZADO
**Accesibilidad:** 100% desde AntigravitiSkillUSN
**Documentación:** Completa en .agent/skills-custom/
**Mantenibilidad:** Alta (todo en un lugar)
