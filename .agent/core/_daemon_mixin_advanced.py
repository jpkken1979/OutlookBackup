"""Mixin compuesto de sistemas avanzados para AgentDaemon.

Compone los mixins especializados extraídos de este archivo original:
- DaemonReputationMixin: AgentReputation, AdaptiveTopology, TrustNetwork
- DaemonObservabilityMixin: EventChronicle, CircuitBreaker, DashboardFeed, AlertEngine
- DaemonIntelligenceMixin: PredictivePrefetch, GenomeManager, KnowledgeDistiller
- DaemonAutonomyMixin: Metacognition, GoalAutonomy, EmergentBehavior
- DaemonEcosystemMixin: AgentContracts, AdversarialArena, WebSocketBridge,
  AgentFederation, CapabilityMarketplace

Mantiene compatibilidad hacia atrás: importar DaemonAdvancedMixin de este módulo
sigue funcionando exactamente igual.
"""

from __future__ import annotations

from ._daemon_mixin_autonomy import DaemonAutonomyMixin
from ._daemon_mixin_ecosystem import DaemonEcosystemMixin
from ._daemon_mixin_intelligence import DaemonIntelligenceMixin
from ._daemon_mixin_observability import DaemonObservabilityMixin
from ._daemon_mixin_reputation import DaemonReputationMixin


class DaemonAdvancedMixin(
    DaemonReputationMixin,
    DaemonObservabilityMixin,
    DaemonIntelligenceMixin,
    DaemonAutonomyMixin,
    DaemonEcosystemMixin,
):
    """Mixin compuesto para compatibilidad hacia atrás.

    Combina todos los mixins avanzados del daemon en una sola clase.
    El código existente que importa ``DaemonAdvancedMixin`` sigue
    funcionando sin cambios.
    """

    pass
