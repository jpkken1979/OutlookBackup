---
description: Mejorar o agregar funcionalidad a código existente. Workflow universal compatible con cualquier LLM.
universal: true
---

# /enhance - Mejorar Aplicación

> Workflow universal compatible con: Claude, GPT-4, Gemini, Codex, Llama, Mistral

## Solicitud de Mejora

$ARGUMENTS

---

## Proceso de Mejora

### Fase 1: Análisis del Estado Actual

Antes de modificar, entender qué existe:

```markdown
## Análisis de Estado Actual

### Estructura del Proyecto
\`\`\`
[Árbol de archivos relevantes]
\`\`\`

### Tecnologías Detectadas
| Componente | Tecnología | Versión |
|------------|------------|---------|
| Framework | [nombre] | [versión] |
| Lenguaje | [nombre] | [versión] |
| Database | [nombre] | [versión] |

### Features Existentes
- [Feature 1]
- [Feature 2]
- [Feature 3]

### Patrones de Código
- Estilo: [convenciones detectadas]
- Arquitectura: [patrones usados]
- Testing: [framework/cobertura]
```

---

### Fase 2: Planificación del Cambio

```markdown
## Plan de Mejora

### Cambio Solicitado
[Descripción clara de qué se va a agregar/modificar]

### Impacto Estimado

#### Archivos a Modificar
| Archivo | Cambio | Riesgo |
|---------|--------|--------|
| `path/file.js` | [descripción] | [bajo/medio/alto] |

#### Archivos a Crear
| Archivo | Propósito |
|---------|-----------|
| `path/new.js` | [descripción] |

#### Archivos Afectados Indirectamente
| Archivo | Por qué |
|---------|---------|
| `path/other.js` | [dependencia/import] |

### Dependencias Nuevas
| Paquete | Versión | Propósito |
|---------|---------|-----------|
| [nombre] | [versión] | [para qué] |

### Riesgos y Mitigaciones
| Riesgo | Probabilidad | Mitigación |
|--------|--------------|------------|
| [riesgo] | [baja/media/alta] | [acción] |

### Compatibilidad
- [ ] Compatible con features existentes
- [ ] No rompe tests actuales
- [ ] Mantiene patrones del proyecto
```

---

### Fase 3: Confirmación

```markdown
## Confirmación de Cambios

**Mejora:** [descripción breve]

**Impacto:**
- Modificar: [X] archivos
- Crear: [Y] archivos nuevos
- Dependencias: [Z] nuevas

**Riesgo general:** [Bajo/Medio/Alto]

**¿Procedo con la implementación?**
- "sí" → Implementar cambios
- "explicar [archivo]" → Detallar cambio específico
- "alternativa" → Proponer otra solución
- "cancelar" → No hacer cambios
```

---

### Fase 4: Implementación

```markdown
## Progreso de Implementación

### Cambios Realizados

#### Archivos Modificados
| Archivo | Líneas | Cambio |
|---------|--------|--------|
| `path/file.js` | 15-30 | [descripción] |

#### Archivos Creados
| Archivo | Líneas | Propósito |
|---------|--------|-----------|
| `path/new.js` | 50 | [descripción] |

### Código Cambiado

**Antes (`path/file.js:15-20`):**
\`\`\`javascript
// código anterior
\`\`\`

**Después:**
\`\`\`javascript
// código nuevo
\`\`\`

### Verificación
- [ ] Código compila/corre sin errores
- [ ] Tests existentes pasan
- [ ] Nueva funcionalidad funciona
```

---

### Fase 5: Entrega

```markdown
## Mejora Completada

### Resumen
- **Cambio:** [descripción]
- **Archivos modificados:** [cantidad]
- **Archivos creados:** [cantidad]

### Cambios Detallados
| Tipo | Archivo | Descripción |
|------|---------|-------------|
| MOD | `path/a.js` | [cambio] |
| NEW | `path/b.js` | [propósito] |

### Cómo Probar
\`\`\`bash
# Comandos para verificar el cambio
npm test
npm run dev
# Navegar a /ruta-nueva
\`\`\`

### Notas de Migración
[Si aplica, pasos para usuarios existentes]

### Rollback (si es necesario)
\`\`\`bash
# Pasos para revertir
git revert [commit]
\`\`\`
```

---

## Ejemplos de Uso

```
/enhance agregar modo oscuro
/enhance implementar búsqueda con filtros
/enhance optimizar carga de imágenes
/enhance agregar autenticación OAuth
/enhance mejorar accesibilidad
/enhance agregar internacionalización (i18n)
/enhance implementar cache de API
/enhance hacer responsive el dashboard
```

---

## Tipos de Mejora

### Funcionalidad Nueva
- Agregar features que no existían
- Integrar servicios externos
- Nuevos endpoints/páginas

### Refactoring
- Mejorar estructura sin cambiar comportamiento
- Optimizar rendimiento
- Reducir deuda técnica

### Fix/Mejora
- Corregir bugs
- Mejorar UX existente
- Actualizar dependencias

### Infraestructura
- Mejorar CI/CD
- Agregar monitoring
- Configurar caching

---

## Principios de Mejora

1. **No romper lo existente** - Mantener compatibilidad
2. **Cambios incrementales** - Pequeños commits
3. **Mantener estilo** - Seguir convenciones del proyecto
4. **Documentar cambios** - Actualizar README si aplica
5. **Testing** - Agregar tests para nuevas features

---

## Precauciones

### Antes de Cambiar
- [ ] ¿Entiendo el código existente?
- [ ] ¿Hay tests que debo mantener?
- [ ] ¿Hay dependencias que pueden romperse?

### Durante el Cambio
- [ ] ¿Estoy siguiendo los patrones del proyecto?
- [ ] ¿Estoy documentando cambios complejos?
- [ ] ¿Los cambios son reversibles?

### Después del Cambio
- [ ] ¿Pasan los tests existentes?
- [ ] ¿La nueva funcionalidad funciona?
- [ ] ¿Actualicé la documentación?

---

*Workflow de Mejora Universal v2.0 - Compatible con cualquier LLM*
