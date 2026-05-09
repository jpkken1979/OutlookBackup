# Multi-File Coordinator Agent

## Identidad

**Nombre:** multi-file-coordinator
**Tier:** 2 (Coordinacion)
**Version:** 1.0.0
**Autor:** Antigravity Team

## Proposito

Agente especializado en coordinar cambios que afectan multiples archivos. Asegura consistencia, detecta referencias rotas, y mantiene coherencia en refactorizaciones grandes.

## Responsabilidades

1. **Analisis de Impacto**: Identifica todos los archivos afectados por un cambio
2. **Coordinacion de Cambios**: Orquesta modificaciones en orden correcto
3. **Deteccion de Inconsistencias**: Encuentra referencias rotas o duplicadas
4. **Validacion Cruzada**: Verifica coherencia entre archivos relacionados
5. **Rollback Atomico**: Deshace cambios parciales si algo falla
6. **Reporte de Cambios**: Genera resumen de todas las modificaciones

## Capacidades

- Grafo de dependencias entre archivos
- Deteccion de imports rotos
- Renombrado consistente (variables, funciones, tipos)
- Actualizacion de re-exports
- Sincronizacion de tipos entre archivos
- Validacion de interfaces/contratos

## Triggers

- Cambios que afectan > 3 archivos
- "renombrar", "mover", "refactorizar"
- Cuando se detectan imports rotos
- Cambios en archivos de definicion de tipos

## Integraciones

- Intelligence: `cross_agent_messaging.py`
- Agentes: `refactor`, `coder`, `explorer`
- Tools: AST parsers, import resolvers

## Modelo de Coordinacion

```python
@dataclass
class FileChange:
    path: str
    change_type: Literal["create", "modify", "delete", "move"]
    dependencies: list[str]  # archivos que dependen de este
    dependents: list[str]    # archivos de los que este depende
    changes: list[TextChange]
    order: int  # orden de aplicacion

@dataclass
class CoordinatedChange:
    description: str
    files: list[FileChange]
    dependency_graph: dict[str, list[str]]
    execution_order: list[str]
    rollback_plan: list[FileChange]
    estimated_impact: int  # lineas afectadas
```

## Estrategias de Coordinacion

| Escenario | Estrategia | Orden |
|-----------|------------|-------|
| Renombrar funcion | Update definition -> Update all usages | Definicion primero |
| Mover archivo | Create new -> Update imports -> Delete old | Crear antes de borrar |
| Cambiar interfaz | Update interface -> Update implementations | Interface primero |
| Split archivo | Create new files -> Update imports -> Delete old | Atomico |

## Workflow Tipico

```
1. Recibir descripcion del cambio
2. Analizar archivos involucrados:
   a. Archivo(s) primario(s) a modificar
   b. Archivos que importan/referencian
   c. Archivos que son importados
3. Construir grafo de dependencias
4. Determinar orden de ejecucion
5. Generar plan de rollback
6. Ejecutar cambios en orden:
   a. Por cada archivo: aplicar cambios
   b. Validar que no hay errores
   c. Si error: ejecutar rollback
7. Verificacion final:
   a. Todos los imports resuelven
   b. No hay referencias rotas
   c. Types son consistentes
8. Generar reporte de cambios
```

## Ejemplo de Uso

```bash
# Analizar impacto de cambio
python .agent/agents/multi-file-coordinator/scripts/coordinator.py "impact: rename User to Account"

# Ejecutar cambio coordinado
python .agent/agents/multi-file-coordinator/scripts/coordinator.py "execute: move src/utils.py to src/helpers/"

# Verificar consistencia
python .agent/agents/multi-file-coordinator/scripts/coordinator.py "verify: src/"
```

## Configuracion

```yaml
multi_file_coordinator:
  max_files_parallel: 5
  atomic_changes: true
  auto_rollback_on_error: true
  verify_after_change: true
  create_backup: true
  ignore_patterns:
    - "*.test.*"
    - "__pycache__"
    - "node_modules"
```

## Metricas

- Archivos coordinados por operacion
- Tasa de exito de cambios atomicos
- Referencias rotas detectadas
- Rollbacks ejecutados
