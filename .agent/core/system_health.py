"""
System Health — Re-exporta desde health_check.py (módulo unificado).

DEPRECADO: Usar directamente ``from core.health_check import HealthChecker``.
Este archivo se mantiene solo por compatibilidad con imports existentes.
"""

from __future__ import annotations

from .health_check import (
    CheckResult as ComponentHealth,
)
from .health_check import (
    HealthChecker as SystemHealth,
)
from .health_check import (
    HealthReport as SystemHealthReport,
)
from .health_check import (
    Status as HealthStatus,
)
from .health_check import (
    main,
)

__all__ = [
    "ComponentHealth",
    "HealthStatus",
    "SystemHealth",
    "SystemHealthReport",
    "main",
]
