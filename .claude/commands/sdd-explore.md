# SDD Fase 1: Explore

Investiga el codebase para entender el contexto completo del cambio solicitado.
Esta fase NO propone soluciones — solo recopila información.

## Acciones

1. **Identificar archivos relevantes**
   - Usar `Grep` y `Glob` para encontrar código relacionado
   - Buscar por nombres de funciones, clases, tipos y patrones mencionados
   - Identificar archivos de config relevantes (`pyproject.toml`, `Cargo.toml`, `package.json`, `.mcp.json`)

2. **Mapear dependencias**
   - Imports internos: qué módulos dependen del área afectada
   - Imports externos: qué librerías se usan
   - Dependencias inversas: quién consume las interfaces que van a cambiar

3. **Documentar estado actual**
   - Leer los archivos clave (max 5 inline, más de 5 → sub-agente)
   - Anotar líneas de código relevantes con rutas absolutas
   - Identificar tests existentes para el área

4. **Identificar patrones existentes**
   - Cómo se resuelven problemas similares en el codebase
   - Convenciones de naming, estructura de archivos, manejo de errores
   - Patrones de la capa correspondiente (Python/TypeScript/Rust)

5. **Evaluar riesgos**
   - Áreas de alto acoplamiento
   - Código sin tests
   - Posibles breaking changes
   - Dependencias externas frágiles

## Output esperado

```markdown
## Reporte de Exploración — [nombre del cambio]

### Archivos relevantes
- `/ruta/absoluta/archivo.py` — descripción de relevancia
- ...

### Dependencias
- **Internas**: módulos que importan/consumen el área afectada
- **Externas**: librerías de terceros involucradas

### Estado actual
Descripción concisa de cómo funciona hoy el área afectada.

### Patrones existentes
- Patrón 1: descripción + ejemplo de archivo
- ...

### Tests existentes
- `tests/path/test_file.py` — qué cubre
- Cobertura estimada del área: X%

### Riesgos identificados
1. Riesgo — impacto — mitigación sugerida
2. ...

### Recomendación para Fase 2 (Propose)
Resumen de lo que se debe considerar al proponer soluciones.
```

---

Explora el codebase en relación a: $ARGUMENTS
