# Plan de Refactorización de agent_base.py

**Archivo:** `.agent/core/agent_base.py`  
**Líneas actuales:** 1347  
**Estado:** CÓDIGO PRODUCTIVO (cambios solo si es necesario)  
**Prioridad:** MEDIA (mejoraría mantenibilidad pero no es urgente)

---

## Problema Actual

El archivo `agent_base.py` tiene **demasiadas responsabilidades en una sola clase**:

1. **Tool Management** (líneas 466-621)
   - `register_tool()`
   - `_setup_default_tools()`
   - `_tool_read_file()`, `_tool_write_file()`, `_tool_search_codebase()`, `_tool_execute_command()`

2. **Skill Loading & Execution** (líneas 622-692)
   - `load_skill()`
   - `_run_skill_script()`

3. **Memory Management** (líneas 694-710)
   - `remember()`, `recall()`, `get_relevant_context()`

4. **Intelligence Layer** (líneas 119-410)
   - Podría estar en módulo separado

5. **Agent Core** (líneas 413-465, 1206-1233)
   - `__init__()`, `get_system_prompt()`, `__repr__()`

---

## Solución Propuesta (3 fases)

### FASE 1: Extraer Intelligence Layer (SEGURA)

**Crear:** `.agent/core/intelligence_layer.py`

```python
# Mover líneas 119-410 a nuevo archivo
class IntelligenceLayer:
    """
    Capa de inteligencia que proporciona capacidades cognitivas avanzadas.
    [docstring completo]
    """
```

**Cambios en agent_base.py:**
```python
# Reemplazar import:
from core.intelligence_layer import IntelligenceLayer
```

**Ventajas:** Modulo self-contained, sin cambios en AntigravityAgent

### FASE 2: Extraer Tool Manager (MODERADAMENTE SEGURA)

**Crear:** `.agent/core/agent_tool_manager.py`

```python
class ToolManager:
    """Gestiona herramientas disponibles para agentes."""
    
    def __init__(self, agent_instance):
        self.agent = agent_instance
        self.tools = {}
    
    def register_tool(self, tool: Tool) -> None:
        # Mover de agent_base.py líneas 466-470
    
    def _setup_default_tools(self) -> None:
        # Mover de agent_base.py líneas 471-535
    
    def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        # Wrapper para _tool_* methods
```

**Cambios en AntigravityAgent:**
```python
self.tool_manager = ToolManager(self)
# Delegación: self.tool_manager.register_tool(tool)
```

**Ventajas:** Separa responsabilidad, mantiene interface igual

### FASE 3: Extraer Memory Manager (MODERADAMENTE SEGURA)

**Crear:** `.agent/core/agent_memory_manager.py`

```python
class MemoryManager:
    """Gestiona memoria y contexto del agente."""
    
    def __init__(self, agent_instance):
        self.agent = agent_instance
    
    def remember(self, key: str, value: Any) -> None:
        # Mover de agent_base.py líneas 694-700
    
    def recall(self, key: str) -> Any | None:
        # Mover de agent_base.py líneas 701-709
    
    def get_relevant_context(self, query: str, limit: int = 5) -> list[str]:
        # Mover de agent_base.py líneas 710-...
```

---

## Orden de Ejecución Recomendado

1. **PRIMERO:** FASE 1 (Extraer IntelligenceLayer)
   - Riesgo: BAJO
   - Tests: Verificar que IntelligenceLayer aún se inicializa
   - Tiempo: 30 min

2. **SEGUNDO:** FASE 2 (Extraer ToolManager)
   - Riesgo: MEDIO
   - Tests: Verificar que tools siguen funcionando
   - Tiempo: 1 hora

3. **TERCERO:** FASE 3 (Extraer MemoryManager)
   - Riesgo: MEDIO
   - Tests: Verificar que memory sigue funcionando
   - Tiempo: 45 min

**Total:** ~2.25 horas (dentro del presupuesto de 3 horas)

---

## Decisión Recomendada

### ✅ HACER FASE 1 AHORA (Extraer IntelligenceLayer)
- Riesgo: BAJO
- Impacto: POSITIVO (mejor organización)
- Tiempo: 30 min

### ⏭️ POSPONER FASES 2-3
- Razón: Requieren cambios más invasivos
- Mejor hacerlo cuando haya más contexto
- O cuando sea necesario por testing

---

## Métricas Post-Refactorización

Si se completan las 3 fases:

| Métrica | Antes | Después | Mejora |
|---------|-------|---------|--------|
| Líneas agent_base.py | 1347 | ~800 | -41% |
| Responsabilidades (AntigravityAgent) | 5 | 2 | -60% |
| Módulos agent/ | 1 (agent_base) | 4 | +3 |
| Complejidad ciclomática | ALTA | MEDIA | +25% |

---

## Notas de Seguridad

- ❌ NO dividir `AntigravityAgent.__init__()` (tiene muchas dependencias)
- ❌ NO tocar `SimpleAgent` (subclase simple, funciona bien)
- ✅ SI extraer clases que no tiene dependencias hacia AntigravityAgent (IntelligenceLayer)
- ✅ SI usar composición (ToolManager, MemoryManager como atributos)

---

## Autor
Auditoría `/aspirador` — 2026-04-04
