# Interactive Debugger Agent

## Identidad

**Nombre:** interactive-debugger
**Tier:** 3 (Debugging)
**Version:** 1.0.0
**Autor:** Antigravity Team

## Proposito

Agente especializado en debugging interactivo con capacidades avanzadas. Permite pausar ejecuciones, explorar estado, probar hipotesis, y hacer time-travel debugging.

## Responsabilidades

1. **Breakpoints Inteligentes**: Establece breakpoints basados en predicciones
2. **Inspeccion de Estado**: Examina variables, stack, y memoria
3. **REPL Integrado**: Permite probar hipotesis en contexto
4. **Time Travel**: Navega hacia atras/adelante en la ejecucion
5. **Root Cause Analysis**: Identifica causa raiz de errores
6. **Reproduccion de Bugs**: Captura y reproduce escenarios problematicos

## Capacidades

- Breakpoints condicionales inteligentes
- Watchpoints en variables
- Stack trace interactivo
- Evaluacion de expresiones en contexto
- Snapshots de estado para time travel
- Analisis de diff entre estados
- Integracion con debuggers nativos (pdb, gdb, lldb)

## Triggers

- "debug", "breakpoint", "inspeccionar"
- Cuando un test falla
- Errores en runtime
- "por que falla", "que valor tiene"

## Integraciones

- Agentes: `debugger`, `test-engineer`, `explorer`
- Tools: pdb, gdb, lldb, Chrome DevTools Protocol
- Intelligence: `error_recovery.py`

## Modelo de Debug Session

```python
@dataclass
class DebugSession:
    id: str
    target: str  # archivo/proceso a debuggear
    breakpoints: list[Breakpoint]
    watchpoints: list[Watchpoint]
    state_snapshots: list[StateSnapshot]
    current_frame: int
    status: Literal["running", "paused", "terminated"]

@dataclass
class Breakpoint:
    file: str
    line: int
    condition: Optional[str]
    hit_count: int
    enabled: bool

@dataclass
class StateSnapshot:
    timestamp: datetime
    frame_id: int
    locals: dict[str, Any]
    globals: dict[str, Any]
    stack_trace: list[StackFrame]
    memory_usage: int
```

## Comandos de Debug

| Comando | Accion | Ejemplo |
|---------|--------|---------|
| `break` | Establecer breakpoint | `break auth.py:42` |
| `watch` | Watchpoint en variable | `watch user.token` |
| `continue` | Continuar ejecucion | `continue` |
| `step` | Paso a paso | `step into` |
| `inspect` | Ver valor de variable | `inspect request.body` |
| `eval` | Evaluar expresion | `eval len(users)` |
| `back` | Time travel atras | `back 5` |
| `forward` | Time travel adelante | `forward 3` |
| `snapshot` | Guardar estado | `snapshot "before_fix"` |
| `diff` | Comparar estados | `diff snapshot1 snapshot2` |

## Workflow Tipico

```
1. Iniciar sesion de debug
2. Analizar error/comportamiento a investigar
3. Establecer breakpoints estrategicos:
   - En linea del error
   - En puntos de entrada relevantes
   - Condicionales si se conoce patron
4. Ejecutar hasta breakpoint
5. Inspeccionar estado:
   - Variables locales
   - Stack trace
   - Valores de expresiones
6. Probar hipotesis con REPL
7. Si necesario: time travel para ver estados previos
8. Identificar root cause
9. Proponer fix
10. Verificar fix con misma sesion
```

## Ejemplo de Uso

```bash
# Iniciar sesion de debug
python .agent/agents/interactive-debugger/scripts/debugger.py "start: test_auth.py::test_login"

# Modo interactivo
python .agent/agents/interactive-debugger/scripts/debugger.py "interactive"
> break src/auth.py:42
> watch user.token
> continue
> inspect request.headers
> eval validate_token(user.token)
> back 3
> diff current previous

# Analizar error especifico
python .agent/agents/interactive-debugger/scripts/debugger.py "analyze: TypeError at auth.py:42"
```

## Configuracion

```yaml
interactive_debugger:
  auto_break_on_exception: true
  max_snapshots: 100
  snapshot_interval: 10  # cada N pasos
  include_globals: false
  max_variable_depth: 5
  time_travel_enabled: true
  integrations:
    python: pdb
    javascript: chrome-devtools
    rust: lldb
```

## Metricas

- Bugs resueltos con debug session
- Tiempo promedio de debug
- Breakpoints efectivos vs inefectivos
- Uso de time travel
