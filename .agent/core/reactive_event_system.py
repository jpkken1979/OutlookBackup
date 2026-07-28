"""
Reactive Event System — Event-driven agent triggers.

Los agentes reaccionan automáticamente a eventos del sistema:
- Cambios en archivos (path patterns con glob)
- Eventos git (commits, PRs)
- Patrones de error (regex en logs)
- Triggers cron (programados)
- Webhooks externos
- Eventos internos del bus de mensajes

Cada regla de reacción mapea: EventPattern → Agente + Task Template.

El sistema implementa:
  - Pattern matching con regex y glob
  - Debouncing para evitar tormentas de eventos
  - Cooldown por regla para evitar ejecuciones repetitivas
  - Event history para auditoría
  - Prioridades de reglas (menor número = mayor prioridad)
  - Integración con RedisMessageBus para distribución

Usage:
    system = ReactiveEventSystem(bus=bus)

    # Regla: cambios en archivos Python disparan exploración
    system.register_rule(EventRule(
        name="auto-review-python",
        event_type=EventType.FILE_CHANGE,
        pattern="*.py",
        agent="explorer",
        task_template="Analiza cambios en {file_path}",
        cooldown_seconds=60,
    ))

    # Regla: errores de importación disparan debugger
    system.register_rule(EventRule(
        name="auto-debug-import",
        event_type=EventType.ERROR_PATTERN,
        pattern=r"ImportError|ModuleNotFoundError",
        agent="debugger",
        task_template="Diagnostica error de importación: {error_message}",
    ))

    # Emitir un evento — las reglas matching se ejecutan automáticamente
    await system.emit(SystemEvent(
        event_type=EventType.FILE_CHANGE,
        source="watcher",
        data={"file_path": "src/api.py", "change_type": "modified"},
    ))

    await system.start()   # Inicia processing loop en background
    await system.stop()    # Shutdown graceful
"""

import asyncio
import fnmatch
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("antigravity.reactive_events")

# ============================================================
# Constantes
# ============================================================
MAX_EVENT_HISTORY = 500
MAX_TRIGGERED_HISTORY = 200
DEFAULT_COOLDOWN = 30.0  # segundos
DEFAULT_DEBOUNCE = 2.0  # segundos
EVENT_CHANNEL = "reactive.events"
TRIGGER_CHANNEL = "reactive.triggers"


# ============================================================
# Tipos de evento
# ============================================================
class EventType(str, Enum):
    """Tipos de eventos del sistema."""

    FILE_CHANGE = "file_change"
    GIT_EVENT = "git_event"
    ERROR_PATTERN = "error_pattern"
    CRON_TRIGGER = "cron_trigger"
    WEBHOOK = "webhook"
    BUS_EVENT = "bus_event"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"
    ANOMALY_DETECTED = "anomaly_detected"
    CUSTOM = "custom"


class MatchStrategy(str, Enum):
    """Estrategia de matching para el patrón."""

    GLOB = "glob"  # fnmatch para paths
    REGEX = "regex"  # regex para texto
    EXACT = "exact"  # igualdad exacta
    CONTAINS = "contains"  # substring


# ============================================================
# Modelos de datos
# ============================================================
@dataclass
class SystemEvent:
    """Evento emitido por el sistema."""

    event_type: EventType
    source: str
    data: dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    severity: str = "info"  # info, warning, error, critical

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source": self.source,
            "data": self.data,
            "timestamp": self.timestamp,
            "severity": self.severity,
        }


@dataclass
class EventRule:
    """Regla de reacción a un tipo de evento."""

    name: str
    event_type: EventType
    pattern: str  # Patrón de matching (glob, regex, exact, contains)
    agent: str  # Agente que ejecuta la reacción
    task_template: str  # Template con {placeholders} de event.data
    match_strategy: MatchStrategy = MatchStrategy.GLOB
    match_field: str = ""  # Campo de event.data contra el cual matchear (vacío = todo)
    priority: int = 5  # 1-10, menor = mayor prioridad
    cooldown_seconds: float = DEFAULT_COOLDOWN
    enabled: bool = True
    max_concurrent: int = 1  # Máximo de ejecuciones concurrentes de esta regla
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "event_type": self.event_type.value,
            "pattern": self.pattern,
            "agent": self.agent,
            "task_template": self.task_template,
            "match_strategy": self.match_strategy.value,
            "match_field": self.match_field,
            "priority": self.priority,
            "cooldown_seconds": self.cooldown_seconds,
            "enabled": self.enabled,
            "max_concurrent": self.max_concurrent,
        }


@dataclass
class TriggerRecord:
    """Registro de un trigger ejecutado."""

    trigger_id: str
    rule_name: str
    event_id: str
    agent: str
    task: str
    task_id: str | None = None
    status: str = "triggered"  # triggered, submitted, completed, failed
    triggered_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "rule_name": self.rule_name,
            "event_id": self.event_id,
            "agent": self.agent,
            "task": self.task,
            "task_id": self.task_id,
            "status": self.status,
            "triggered_at": self.triggered_at,
            "completed_at": self.completed_at,
        }


# ============================================================
# Pattern Matcher
# ============================================================
class PatternMatcher:
    """Evalúa si un valor matchea un patrón según la estrategia."""

    @staticmethod
    def matches(value: str, pattern: str, strategy: MatchStrategy) -> bool:
        """Retorna True si el valor coincide con el patrón."""
        if strategy == MatchStrategy.GLOB:
            return fnmatch.fnmatch(value, pattern)
        elif strategy == MatchStrategy.REGEX:
            try:
                return bool(re.search(pattern, value))
            except re.error:
                logger.warning("Regex inválido en regla: %s", pattern)
                return False
        elif strategy == MatchStrategy.EXACT:
            return value == pattern
        elif strategy == MatchStrategy.CONTAINS:
            return pattern in value
        return False


# ============================================================
# Reactive Event System
# ============================================================
class ReactiveEventSystem:
    """
    Sistema reactivo basado en eventos.

    Recibe eventos, los matchea contra reglas registradas,
    y dispara ejecuciones de agentes automáticamente via el daemon.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus
        self._rules: dict[str, EventRule] = {}
        self._event_history: list[SystemEvent] = []
        self._trigger_history: list[TriggerRecord] = []
        self._running = False

        # Cooldown tracking: rule_name → timestamp del último trigger
        self._last_triggered: dict[str, float] = {}

        # Concurrency tracking: rule_name → count de ejecuciones activas
        self._active_triggers: dict[str, int] = {}

        # Debounce: event_key → timer task
        self._debounce_timers: dict[str, asyncio.Task] = {}

        # Processing queue
        self._event_queue: asyncio.Queue[SystemEvent] = asyncio.Queue(maxsize=5000)

        # Background tasks
        self._processor_task: asyncio.Task | None = None
        self._bus_listener_task: asyncio.Task | None = None

        # Métricas
        self._metrics = {
            "events_received": 0,
            "events_matched": 0,
            "events_dropped_cooldown": 0,
            "events_dropped_concurrency": 0,
            "triggers_fired": 0,
            "triggers_succeeded": 0,
            "triggers_failed": 0,
        }

    # --------------------------------------------------------
    # Rule Management
    # --------------------------------------------------------
    def register_rule(self, rule: EventRule) -> None:
        """Registra una regla de reacción."""
        self._rules[rule.name] = rule
        self._active_triggers.setdefault(rule.name, 0)
        logger.info(
            "Regla registrada: '%s' → %s:%s (agent=%s)",
            rule.name,
            rule.event_type.value,
            rule.pattern,
            rule.agent,
        )

    def unregister_rule(self, name: str) -> bool:
        """Elimina una regla por nombre."""
        if name in self._rules:
            del self._rules[name]
            return True
        return False

    def enable_rule(self, name: str) -> bool:
        """Habilita una regla."""
        if name in self._rules:
            self._rules[name].enabled = True
            return True
        return False

    def disable_rule(self, name: str) -> bool:
        """Deshabilita una regla."""
        if name in self._rules:
            self._rules[name].enabled = False
            return True
        return False

    def list_rules(self) -> list[dict[str, Any]]:
        """Lista todas las reglas registradas."""
        return [
            {
                **r.to_dict(),
                "active_triggers": self._active_triggers.get(r.name, 0),
                "last_triggered": self._last_triggered.get(r.name),
            }
            for r in sorted(self._rules.values(), key=lambda r: r.priority)
        ]

    def get_rule(self, name: str) -> dict[str, Any] | None:
        """Retorna una regla por nombre."""
        rule = self._rules.get(name)
        if rule is None:
            return None
        return {
            **rule.to_dict(),
            "active_triggers": self._active_triggers.get(name, 0),
            "last_triggered": self._last_triggered.get(name),
        }

    # --------------------------------------------------------
    # Event Emission
    # --------------------------------------------------------
    async def emit(
        self,
        event: SystemEvent,
        debounce_key: str | None = None,
        debounce_seconds: float = DEFAULT_DEBOUNCE,
    ) -> None:
        """
        Emite un evento al sistema.

        Si debounce_key es dado, agrupa eventos con la misma key
        y solo procesa el último después de debounce_seconds.
        """
        self._metrics["events_received"] += 1

        if debounce_key:
            await self._debounced_emit(event, debounce_key, debounce_seconds)
        else:
            await self._event_queue.put(event)

        # Publicar en bus para distribución
        if self._bus:
            try:
                await self._bus.publish(
                    EVENT_CHANNEL,
                    event.to_dict(),
                    from_agent="reactive-system",
                )
            except Exception as e:
                logger.debug("Error publicando evento en bus: %s", e)

    async def _debounced_emit(
        self,
        event: SystemEvent,
        key: str,
        delay: float,
    ) -> None:
        """Emit con debounce — cancela el timer anterior y espera."""
        if key in self._debounce_timers:
            self._debounce_timers[key].cancel()

        async def _delayed_put() -> None:
            await asyncio.sleep(delay)
            await self._event_queue.put(event)
            self._debounce_timers.pop(key, None)

        self._debounce_timers[key] = asyncio.create_task(_delayed_put())

    # --------------------------------------------------------
    # Event Processing
    # --------------------------------------------------------
    async def start(self) -> None:
        """Inicia el sistema reactivo en background."""
        if self._running:
            return
        self._running = True

        self._processor_task = asyncio.create_task(
            self._process_loop(),
            name="reactive-processor",
        )

        # Escuchar eventos del bus si disponible
        if self._bus:
            self._bus_listener_task = asyncio.create_task(
                self._listen_bus_events(),
                name="reactive-bus-listener",
            )

        logger.info(
            "ReactiveEventSystem iniciado con %d reglas",
            len(self._rules),
        )

    async def stop(self) -> None:
        """Detiene el sistema reactivo."""
        self._running = False

        # Cancelar debounce timers
        for task in self._debounce_timers.values():
            task.cancel()
        self._debounce_timers.clear()

        if self._processor_task:
            self._processor_task.cancel()
        if self._bus_listener_task:
            self._bus_listener_task.cancel()

        logger.info("ReactiveEventSystem detenido. Métricas: %s", self._metrics)

    async def _process_loop(self) -> None:
        """Loop principal: consume eventos de la queue y ejecuta reglas."""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=5.0,
                )
                await self._process_event(event)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error("Error procesando evento: %s", e)

    async def _process_event(self, event: SystemEvent) -> None:
        """Procesa un evento contra todas las reglas."""
        # Guardar en historial
        self._event_history.append(event)
        if len(self._event_history) > MAX_EVENT_HISTORY:
            self._event_history = self._event_history[-MAX_EVENT_HISTORY:]

        # Buscar reglas que matchean
        matching_rules = self._find_matching_rules(event)

        if matching_rules:
            self._metrics["events_matched"] += 1

        for rule in matching_rules:
            await self._fire_trigger(rule, event)

    def _find_matching_rules(self, event: SystemEvent) -> list[EventRule]:
        """Encuentra todas las reglas que matchean un evento."""
        matches = []

        for rule in self._rules.values():
            if not rule.enabled:
                continue
            if rule.event_type != event.event_type:
                continue

            # Determinar el valor contra el cual matchear
            if rule.match_field:
                value = str(event.data.get(rule.match_field, ""))
            else:
                # Match contra todos los valores del data
                value = json.dumps(event.data, default=str)

            if PatternMatcher.matches(value, rule.pattern, rule.match_strategy):
                matches.append(rule)

        # Ordenar por prioridad
        matches.sort(key=lambda r: r.priority)
        return matches

    async def _fire_trigger(self, rule: EventRule, event: SystemEvent) -> None:
        """Ejecuta una regla disparada por un evento."""
        now = time.time()

        # Check cooldown
        last = self._last_triggered.get(rule.name, 0)
        if now - last < rule.cooldown_seconds:
            self._metrics["events_dropped_cooldown"] += 1
            logger.debug(
                "Regla '%s' en cooldown (%.0fs restantes)",
                rule.name,
                rule.cooldown_seconds - (now - last),
            )
            return

        # Check concurrency
        active = self._active_triggers.get(rule.name, 0)
        if active >= rule.max_concurrent:
            self._metrics["events_dropped_concurrency"] += 1
            logger.debug(
                "Regla '%s' en máxima concurrencia (%d/%d)",
                rule.name,
                active,
                rule.max_concurrent,
            )
            return

        # Renderizar el task template con datos del evento
        task = self._render_template(rule.task_template, event)

        trigger = TriggerRecord(
            trigger_id=str(uuid.uuid4()),
            rule_name=rule.name,
            event_id=event.event_id,
            agent=rule.agent,
            task=task,
        )

        self._last_triggered[rule.name] = now
        self._active_triggers[rule.name] = active + 1
        self._metrics["triggers_fired"] += 1

        logger.info(
            "Trigger disparado: regla='%s' → agente='%s' tarea='%.60s...'",
            rule.name,
            rule.agent,
            task,
        )

        # Encolar tarea en el daemon via bus
        try:
            task_id = await self._submit_to_daemon(rule.agent, task, rule.context, event)
            trigger.task_id = task_id
            trigger.status = "submitted"
            self._metrics["triggers_succeeded"] += 1

            # Publicar trigger en bus
            if self._bus:
                await self._bus.publish(
                    TRIGGER_CHANNEL,
                    trigger.to_dict(),
                    from_agent="reactive-system",
                )

        except Exception as e:
            trigger.status = "failed"
            self._metrics["triggers_failed"] += 1
            logger.error("Error disparando trigger '%s': %s", rule.name, e)

        finally:
            self._active_triggers[rule.name] = max(0, self._active_triggers.get(rule.name, 1) - 1)
            trigger.completed_at = time.time()

            self._trigger_history.append(trigger)
            if len(self._trigger_history) > MAX_TRIGGERED_HISTORY:
                self._trigger_history = self._trigger_history[-MAX_TRIGGERED_HISTORY:]

    async def _submit_to_daemon(
        self,
        agent: str,
        task: str,
        context: dict[str, Any],
        event: SystemEvent,
    ) -> str:
        """Encola la tarea en el AgentDaemon."""
        if self._bus is None:
            raise RuntimeError("Bus no disponible")

        from .redis_message_bus import Priority

        task_id = str(uuid.uuid4())
        await self._bus.enqueue_priority(
            "tasks",
            {
                "agent": agent,
                "task": task,
                "task_id": task_id,
                "context": {
                    **context,
                    "_reactive_event": event.to_dict(),
                    "_trigger_source": "reactive_event_system",
                },
            },
            priority=Priority.HIGH,
            from_agent="reactive-system",
        )
        return task_id

    def _render_template(self, template: str, event: SystemEvent) -> str:
        """Renderiza un template con datos del evento."""
        replacements = {
            "event_type": event.event_type.value,
            "source": event.source,
            "event_id": event.event_id,
            "severity": event.severity,
            **{str(k): str(v) for k, v in event.data.items()},
        }
        result = template
        for key, val in replacements.items():
            result = result.replace(f"{{{key}}}", val)
        return result

    # --------------------------------------------------------
    # Bus Listener — escucha eventos del ecosistema
    # --------------------------------------------------------
    async def _listen_bus_events(self) -> None:
        """Escucha canales del bus y los convierte en SystemEvents."""
        channels_to_watch = [
            ("tasks.completed", EventType.AGENT_COMPLETED),
            ("tasks.failed", EventType.AGENT_FAILED),
        ]

        try:
            for channel, event_type in channels_to_watch:
                queue = await self._bus.subscribe_queue(channel)
                asyncio.create_task(
                    self._relay_bus_channel(queue, event_type, channel),
                    name=f"reactive-relay-{channel}",
                )
        except Exception as e:
            logger.debug("Error escuchando bus: %s", e)

    async def _relay_bus_channel(
        self,
        queue: Any,
        event_type: EventType,
        source_channel: str,
    ) -> None:
        """Relay: mensajes del bus → SystemEvents."""
        while self._running:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=5.0)
                payload = msg.payload if hasattr(msg, "payload") else msg
                event = SystemEvent(
                    event_type=event_type,
                    source=source_channel,
                    data=payload if isinstance(payload, dict) else {"raw": str(payload)},
                )
                await self._event_queue.put(event)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.debug("Error en relay %s: %s", source_channel, e)

    # --------------------------------------------------------
    # Stats & History
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del sistema."""
        return {
            "running": self._running,
            "rules_count": len(self._rules),
            "rules_enabled": sum(1 for r in self._rules.values() if r.enabled),
            "event_queue_size": self._event_queue.qsize(),
            "metrics": {**self._metrics},
        }

    def get_event_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retorna eventos recientes."""
        return [e.to_dict() for e in self._event_history[-limit:]]

    def get_trigger_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retorna triggers recientes."""
        return [t.to_dict() for t in self._trigger_history[-limit:]]


# ============================================================
# Singleton
# ============================================================
_instance: ReactiveEventSystem | None = None


async def get_reactive_system(bus: Any = None) -> ReactiveEventSystem:
    """Obtiene o crea el sistema reactivo global."""
    global _instance
    if _instance is None:
        _instance = ReactiveEventSystem(bus=bus)
    return _instance
