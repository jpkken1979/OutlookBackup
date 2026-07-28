"""Gateway package — mixins del gateway HTTP de Antigravity.

Nota: _WebSocketMixin removido intencionalmente (Option C — freeze fix).
El gateway opera en modo REST + SSE puro para evitar zombie connections.
"""

from ._mixin_system import _SystemMixin
from ._mixin_agents import _AgentsMixin
from ._mixin_skills import _SkillsMixin
from ._mixin_streaming import _StreamingMixin
from ._mixin_daemon import _DaemonMixin
from ._mixin_memory import _MemoryMixin
from ._mixin_intelligence import _IntelligenceMixin
from ._mixin_swarm import _SwarmMixin
from ._mixin_observatory import _ObservatoryMixin
from ._mixin_resilience import _ResilienceMixin
from ._mixin_advanced import _AdvancedMixin
from ._mixin_brain import _BrainMixin

__all__ = [
    "_SystemMixin",
    "_AgentsMixin",
    "_SkillsMixin",
    "_StreamingMixin",
    "_DaemonMixin",
    "_MemoryMixin",
    "_IntelligenceMixin",
    "_SwarmMixin",
    "_ObservatoryMixin",
    "_ResilienceMixin",
    "_AdvancedMixin",
    "_BrainMixin",
]
