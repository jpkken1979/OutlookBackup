"""Sub-paquete de IntelligentOrchestrator (Plan 018 — paso 1 de descomposicion).

Contiene los modelos y analizadores extraidos del monolito intelligent_orchestrator.py.
La API publica sigue siendo core.intelligent_orchestrator — este paquete es un
detalle de implementacion interno.

Modulos:
- models: enums TaskComplexity, ExecutionStrategy y dataclasses TaskAnalysis,
          ExecutionStep, ExecutionResult
- complexity_analyzer: funcion pura detect_complexity(task) extraida de
                       IntelligentOrchestrator._detect_complexity
"""

from __future__ import annotations
