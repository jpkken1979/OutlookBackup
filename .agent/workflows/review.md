---
description: Revisión de código sistemática y profesional. Workflow universal compatible con cualquier LLM.
universal: true
---

# /review - Code Review Profesional

> Workflow universal compatible con: Claude, GPT-4, Gemini, Codex, Llama, Mistral

## Código a Revisar

$ARGUMENTS

---

## Proceso de Revisión

### Fase 1: Análisis Inicial

```markdown
## Contexto de Revisión

### Tipo de Cambio
- [ ] Nueva funcionalidad
- [ ] Bug fix
- [ ] Refactoring
- [ ] Configuración
- [ ] Documentación
- [ ] Tests

### Archivos Afectados
| Archivo | Líneas | Tipo de Cambio |
|---------|--------|----------------|
| `path/file.ext` | +X/-Y | [descripción] |

### Impacto Estimado
- **Riesgo:** [Bajo/Medio/Alto]
- **Complejidad:** [Baja/Media/Alta]
- **Tests requeridos:** [Sí/No]
```

---

### Fase 2: Revisión Detallada

#### Checklist de Revisión

```markdown
## Checklist de Código

### Funcionalidad
- [ ] El código hace lo que se espera
- [ ] Edge cases manejados
- [ ] Comportamiento en errores correcto
- [ ] Sin regresiones en funcionalidad existente

### Diseño
- [ ] Sigue patrones del proyecto
- [ ] Responsabilidades bien separadas
- [ ] No hay duplicación de código
- [ ] Acoplamiento apropiado

### Legibilidad
- [ ] Nombres descriptivos (variables, funciones)
- [ ] Código auto-documentado
- [ ] Comentarios donde es necesario
- [ ] Estructura lógica y clara

### Seguridad
- [ ] Sin vulnerabilidades obvias
- [ ] Input validado
- [ ] Sin datos sensibles expuestos
- [ ] Permisos verificados

### Performance
- [ ] Sin loops innecesarios
- [ ] Queries optimizadas
- [ ] Sin memory leaks
- [ ] Complejidad razonable

### Testing
- [ ] Tests unitarios incluidos
- [ ] Tests de integración si aplica
- [ ] Cobertura adecuada
- [ ] Tests pasan
```

---

### Fase 3: Comentarios de Revisión

```markdown
## Comentarios de Revisión

### Bloqueantes (Deben corregirse)

**[BLOQUEANTE] Archivo:línea - Título**
```[lenguaje]
// Código problemático
```
**Problema:** [descripción]
**Sugerencia:**
```[lenguaje]
// Código sugerido
```

---

### Sugerencias (Recomendado)

**[SUGERENCIA] Archivo:línea - Título**
**Observación:** [descripción]
**Mejora propuesta:** [descripción o código]

---

### Nits (Opcional)

**[NIT] Archivo:línea**
[Comentario menor sobre estilo o preferencia]
```

---

### Fase 4: Veredicto

```markdown
## Resultado de Revisión

### Veredicto: [APROBAR / CAMBIOS REQUERIDOS / RECHAZAR]

### Resumen
| Tipo | Cantidad |
|------|----------|
| Bloqueantes | X |
| Sugerencias | X |
| Nits | X |

### Comentario General
[Comentario constructivo sobre la calidad general del código]

### Próximos Pasos
- [ ] [Acción 1]
- [ ] [Acción 2]

### Para Aprobar
1. [Requisito 1]
2. [Requisito 2]
```

---

## Categorías de Comentarios

### Por Severidad

| Categoría | Descripción | Acción |
|-----------|-------------|--------|
| **BLOQUEANTE** | Bug, seguridad, o diseño incorrecto | Debe corregirse antes de merge |
| **SUGERENCIA** | Mejora recomendada | Considerar seriamente |
| **NIT** | Estilo o preferencia | Opcional |
| **PREGUNTA** | Necesita clarificación | Responder antes de aprobar |
| **ELOGIO** | Código bien hecho | Reconocimiento positivo |

### Por Área

| Área | Ejemplos |
|------|----------|
| **SECURITY** | Vulnerabilidades, validación |
| **PERF** | Rendimiento, optimización |
| **DESIGN** | Arquitectura, patrones |
| **STYLE** | Formato, naming |
| **TEST** | Cobertura, casos |
| **DOCS** | Documentación, comentarios |

---

## Ejemplos de Comentarios

### Bloqueante - Seguridad

```markdown
**[BLOQUEANTE] src/api/users.py:45 - SQL Injection**
```python
query = f"SELECT * FROM users WHERE id = {user_id}"
```
**Problema:** Query construida con string formatting permite SQL injection.
**Sugerencia:**
```python
query = "SELECT * FROM users WHERE id = %s"
cursor.execute(query, (user_id,))
```
**Referencia:** OWASP A03:2021
```

### Sugerencia - Performance

```markdown
**[SUGERENCIA] src/services/data.py:120 - Query N+1**
**Observación:** El loop ejecuta una query por cada item, causando N+1 queries.
**Mejora propuesta:** Usar eager loading o batch query.
```python
# En vez de
for user in users:
    orders = Order.query.filter_by(user_id=user.id).all()

# Usar
users = User.query.options(joinedload(User.orders)).all()
```
```

### Nit - Estilo

```markdown
**[NIT] src/utils/helpers.ts:30**
Preferir `const` sobre `let` cuando la variable no se reasigna.
```

### Elogio

```markdown
**[ELOGIO] src/core/validator.py**
Excelente uso del patrón Strategy para los validadores. Muy extensible y testeable.
```

---

## Principios de Code Review

### Para el Revisor

1. **Sé respetuoso** - Critica el código, no la persona
2. **Sé específico** - Señala exactamente qué y por qué
3. **Sé constructivo** - Ofrece alternativas, no solo críticas
4. **Sé oportuno** - Responde en menos de 24 horas
5. **Sé abierto** - Acepta diferentes enfoques válidos

### Para el Autor

1. **No lo tomes personal** - El objetivo es mejorar el código
2. **Explica tu razonamiento** - Ayuda al revisor a entender
3. **Agradece el feedback** - El tiempo del revisor es valioso
4. **Aprende de los comentarios** - Cada review es oportunidad de mejora

---

## Integración con Git

```bash
# Ver cambios en PR
git diff main...feature-branch

# Ver archivos cambiados
git diff --name-only main...feature-branch

# Ver estadísticas
git diff --stat main...feature-branch

# Ver contexto específico
git log --oneline main...feature-branch
```

---

## Automatizaciones Recomendadas

### Pre-Review (Automático)

- [ ] Linting (ESLint, Pylint, Rubocop)
- [ ] Formateo (Prettier, Black)
- [ ] Type checking (TypeScript, mypy)
- [ ] Tests unitarios
- [ ] Cobertura de código
- [ ] Scan de seguridad (Snyk, npm audit)

### Durante Review (Manual)

- [ ] Lógica de negocio
- [ ] Diseño y arquitectura
- [ ] Edge cases
- [ ] Documentación
- [ ] Naming y legibilidad

---

*Workflow de Code Review v1.0 - Compatible con cualquier LLM*
