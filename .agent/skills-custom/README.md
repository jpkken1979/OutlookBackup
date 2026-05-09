# AntigravitiSkillUSN - Skills & Agentes Centralizados

**Status:** ✅ COMPLETAMENTE CENTRALIZADO
**Ubicación:** `C:\Users\kenji\AntigravitiSkillUSN\.agent\skills-custom\`
**Fecha:** 2026-02-10

---

## 🎯 Resumen Ejecutivo

Todos tus **7 skills y agentes** ahora están centralizados en una ubicación:

```
.agent/skills-custom/
├── startup/
├── finalizar/
├── finalizar-autonomo/
├── type-validation/ (NUEVO)
├── debug-server/
├── excel-parsing/
├── skill-rules.json
├── INVENTORY.md
└── README.md (este archivo)
```

---

## ✨ Qué Se Centralizó

| Skill | Tipo | Estado | Ubicación |
|-------|------|--------|-----------|
| **startup** | Domain | ✅ | `.agent/skills-custom/startup/` |
| **finalizar** | Domain | ✅ | `.agent/skills-custom/finalizar/` |
| **finalizar-autonomo** | Domain | ✅ | `.agent/skills-custom/finalizar-autonomo/` |
| **type-validation** | Guardrail | ✅ | `.agent/skills-custom/type-validation/` |
| **debug-server** | Domain | ✅ | `.agent/skills-custom/debug-server/` |
| **excel-parsing** | Domain | ✅ | `.agent/skills-custom/excel-parsing/` |

---

## 🚀 Acceso Rápido

### Skills Disponibles

```bash
# 1. Iniciar entorno
/startup

# 2. Finalizar sesión
/finalizar

# 3. Validar tipos (ONE FILE AT A TIME)
/type-validation

# 4. Debug de problemas
/debug-server "Descripción"

# 5. Parsear Excel
/excel-parsing "Descripción"

# 6. Automatización completa (CI/CD)
./finalizar auto-update
./finalizar api --port 5000
```

---

## 📚 Documentación

### Para Empezar Rápido
1. **INVENTORY.md** - Inventario completo de skills
2. **Cada SKILL.md** - Documentación específica de cada skill
3. **QUICK_START.md** - Guía rápida (en type-validation)

### Para Profundizar
- **type-validation/SKILL.md** - Enfoque ONE FILE AT A TIME
- **finalizar-autonomo/SKILL.md** - 7 fases automáticas
- **skill-rules.json** - Configuración de triggers

---

## 🔧 Configuración

### Project Level
```
.agent/skills-custom/skill-rules.json
```
Define triggers y comportamiento de los 7 skills.

### Global Level (Mantener)
```
~/.claude/skills/skill-rules.json
```
Includes finalizar-autonomo components (script.py, api.py, etc.)

---

## 📊 Skills por Categoría

### Automatización
- **finalizar-autonomo** - 7 fases autónomas + API + Docker + CI/CD
- **finalizar** - Workflow simple de fin de sesión

### Setup & Debug
- **startup** - Verificación de entorno
- **debug-server** - Diagnóstico de problemas

### Código
- **type-validation** - Prevención de type errors
- **excel-parsing** - Parseo de Excel

---

## ⚡ Patrones de Uso Recomendados

### Sesión Típica
```
1. /startup              → Verificar entorno
2. [Desarrollar]
3. /type-validation      → Validar tipos (si cambios Python)
4. /finalizar            → Finalizar sesión
```

### Con Automatización
```
git push origin main
→ GitHub Actions ejecuta finalizar-autonomo automáticamente
```

### Para Excel/Data
```
/excel-parsing "Necesito leer datos de archivo.xlsx"
→ Mejores prácticas de parsing
```

---

## 🎯 Próximos Pasos

### Inmediato
- [ ] Prueba `/startup` para verificar que funciona
- [ ] Prueba `/type-validation` en un archivo Python
- [ ] Verifica acceso a todos los skills

### Corto Plazo
- [ ] Integra tipo-validation en workflow diario
- [ ] Automatiza con finalizar-autonomo en CI/CD
- [ ] Customiza triggers según necesidades

### Futuro
- [ ] Agregar más skills especializados
- [ ] Crear reportes de automatización
- [ ] Mejorar performance

---

## 📁 Estructura Física

```
AntigravitiSkillUSN/
.
├── .agent/
│   └── skills-custom/          ← TODO AQUI
│       ├── startup/
│       ├── finalizar/
│       ├── finalizar-autonomo/
│       ├── type-validation/
│       ├── debug-server/
│       ├── excel-parsing/
│       ├── skill-rules.json     ← Configuración local
│       ├── INVENTORY.md         ← Inventario completo
│       └── README.md            ← Este archivo
│
├── .github/
│   └── workflows/
│       └── finalizar-autonomo.yml ← CI/CD (mantener aquí)
│
└── ...resto del proyecto
```

---

## ✅ Beneficios de Centralización

✅ **Un solo lugar** para encontrar todo
✅ **Documentación unificada** fácil de leer
✅ **Triggers locales** además de globales
✅ **Fácil de mantener** y actualizar
✅ **Accesible** desde cualquier editor
✅ **Git-friendly** para colaboración

---

## 🔗 Links Útiles

- **INVENTORY.md** - Inventario detallado de todos los skills
- **skill-rules.json** - Configuración de triggers
- **type-validation/QUICK_START.md** - Guía rápida de validación de tipos
- **~/.claude/skills/finalizar-autonomo/** - Componentes globales

---

## 📞 Soporte Rápido

| Necesidad | Solución |
|-----------|----------|
| ¿Cómo uso skills? | Lee INVENTORY.md |
| ¿Qué es type-validation? | Ve a type-validation/SKILL.md |
| ¿Cómo configuro? | Edita skill-rules.json |
| ¿Dónde está el código? | ~/.claude/skills/finalizar-autonomo/ (global) |
| ¿Cómo agrego skills? | Crea directorio en .agent/skills-custom/ |

---

**Creado:** 2026-02-10
**Versión:** 1.0
**Status:** ✅ COMPLETO Y CENTRALIZADO
