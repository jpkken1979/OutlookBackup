"""
Autonomous Scheduler - Motor de tareas calendarizadas y event-driven.

Permite que el ecosistema ejecute tareas de forma proactiva sin
intervención humana, tanto en horarios fijos (cron-style) como
reaccionando a eventos del sistema.

Tipos de triggers:
  - Interval: cada N segundos/minutos/horas
  - Cron: expresión cron (minuto hora día mes día_semana)
  - Event: cuando se publica en un canal del bus
  - OneShot: una sola vez en T segundos

Integración:
  - Usa RedisMessageBus para escuchar eventos
  - Envía tareas al AgentDaemon via cola de prioridad
  - Persiste el registro de schedules en SQLite

Usage:
    scheduler = AutonomousScheduler()
    await scheduler.start()

    # Tarea cada 5 minutos
    scheduler.add_interval(
        name="health-check",
        agent="devops-engineer",
        task="ejecuta health check del ecosistema",
        seconds=300,
    )

    # Tarea al arrancar el sistema
    scheduler.add_one_shot(
        name="startup-sync",
        agent="explorer",
        task="sincroniza índice de skills",
        delay_seconds=10,
    )

    # Tarea disparada por evento
    scheduler.add_event_trigger(
        name="on-new-task",
        channel="tasks.completed",
        agent="documentation-writer",
        task_template="documenta resultado: {result}",
    )
"""

import asyncio
import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.autonomous_scheduler")

# ============================================================
# Constantes
# ============================================================
SCHEDULER_DB = Path(".antigravity_scheduler.db")
DEFAULT_PRIORITY = "NORMAL"


# ============================================================
# Tipos de trigger
# ============================================================
class TriggerType(Enum):
    INTERVAL = "interval"
    CRON = "cron"
    EVENT = "event"
    ONE_SHOT = "one_shot"


# ============================================================
# Definición de schedule
# ============================================================
@dataclass
class Schedule:
    """Define cuándo y cómo ejecutar una tarea autónoma."""

    name: str
    trigger_type: TriggerType
    agent_name: str
    task_template: str  # Puede contener {placeholders} para eventos
    priority: str = DEFAULT_PRIORITY
    enabled: bool = True
    context: dict[str, Any] = field(default_factory=dict)

    # Parámetros por tipo de trigger
    interval_seconds: float | None = None
    cron_expression: str | None = None
    event_channel: str | None = None
    delay_seconds: float | None = None

    # Estadísticas
    run_count: int = 0
    last_run: float | None = None
    next_run: float | None = None
    last_error: str | None = None
    schedule_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "name": self.name,
            "trigger_type": self.trigger_type.value,
            "agent_name": self.agent_name,
            "task_template": self.task_template,
            "priority": self.priority,
            "enabled": self.enabled,
            "interval_seconds": self.interval_seconds,
            "cron_expression": self.cron_expression,
            "event_channel": self.event_channel,
            "delay_seconds": self.delay_seconds,
            "run_count": self.run_count,
            "last_run": self.last_run,
            "next_run": self.next_run,
            "last_error": self.last_error,
        }


# ============================================================
# Parser de expresiones cron
# ============================================================
class CronParser:
    """
    Parser mínimo de expresiones cron de 5 campos:
    minuto(0-59) hora(0-23) día(1-31) mes(1-12) día_semana(0-6, 0=domingo)

    Soporta: * , - /
    Ejemplos:
      "*/5 * * * *"   → cada 5 minutos
      "0 9 * * 1-5"   → cada día de semana a las 9:00
      "0 0 1 * *"     → el primer día de cada mes a medianoche
    """

    @staticmethod
    def _parse_field(field_str: str, min_val: int, max_val: int) -> list[int]:
        """Parsea un campo cron y retorna lista de valores."""
        values: set[int] = set()

        for part in field_str.split(","):
            if "/" in part:
                range_part, step_str = part.split("/", 1)
                step = int(step_str)
                if range_part == "*":
                    start, end = min_val, max_val
                elif "-" in range_part:
                    start, end = map(int, range_part.split("-", 1))
                else:
                    start = int(range_part)
                    end = max_val
                for v in range(start, end + 1, step):
                    values.add(v)
            elif "-" in part:
                start, end = map(int, part.split("-", 1))
                for v in range(start, end + 1):
                    values.add(v)
            elif part == "*":
                for v in range(min_val, max_val + 1):
                    values.add(v)
            else:
                values.add(int(part))

        return sorted(values)

    @classmethod
    def next_occurrence(cls, cron_expr: str, after: float | None = None) -> float:
        """
        Calcula la próxima ejecución de una expresión cron.

        Args:
            cron_expr: Expresión cron de 5 campos
            after: Timestamp desde el cual buscar (default: ahora)

        Returns:
            Timestamp Unix de la próxima ejecución
        """
        import datetime

        parts = cron_expr.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Expresión cron inválida: '{cron_expr}' (se esperan 5 campos)")

        minutes = cls._parse_field(parts[0], 0, 59)
        hours = cls._parse_field(parts[1], 0, 23)
        days = cls._parse_field(parts[2], 1, 31)
        months = cls._parse_field(parts[3], 1, 12)
        weekdays = cls._parse_field(parts[4], 0, 6)

        start = datetime.datetime.fromtimestamp(after or time.time())
        # Avanzar 1 minuto desde el momento actual
        current = start.replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)

        # Buscar hasta 366 días en el futuro
        for _ in range(525_600):  # 365 * 24 * 60 minutos
            if (
                current.month in months
                and current.day in days
                and current.weekday() in [(d - 1) % 7 for d in weekdays]
                and current.hour in hours
                and current.minute in minutes
            ):
                return current.timestamp()
            current += datetime.timedelta(minutes=1)

        raise RuntimeError(f"No se encontró próxima ejecución para '{cron_expr}'")


# ============================================================
# Autonomous Scheduler
# ============================================================
class AutonomousScheduler:
    """
    Motor de scheduling event-driven para tareas autónomas.

    Capacidades:
    - Interval: ejecuta agentes cada N segundos
    - Cron: horarios fijos tipo cron de 5 campos
    - Event-driven: reacciona a publicaciones en canales del bus
    - One-shot: tareas retardadas de una sola ejecución
    - Persistencia de schedules en SQLite
    - Hot-reload: agregar/quitar schedules en runtime
    """

    def __init__(self, db_path: Path = SCHEDULER_DB) -> None:
        self._db_path = db_path
        self._schedules: dict[str, Schedule] = {}
        self._running = False
        self._bus = None
        self._timer_tasks: dict[str, asyncio.Task] = {}
        self._event_tasks: dict[str, asyncio.Task] = {}
        self._daemon = None
        self._init_db()
        self._load_from_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schedules (
                    schedule_id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    config_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schedule_runs (
                    run_id TEXT PRIMARY KEY,
                    schedule_id TEXT NOT NULL,
                    task_id TEXT,
                    started_at REAL NOT NULL,
                    status TEXT DEFAULT 'submitted',
                    error TEXT
                )
            """)
            conn.commit()

    # --------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------
    async def start(self) -> None:
        """Inicia el scheduler."""
        from .agent_daemon import get_daemon
        from .redis_message_bus import get_message_bus

        self._bus = await get_message_bus()  # type: ignore[assignment]  # redis: dep opcional
        self._daemon = await get_daemon()  # type: ignore[assignment]  # daemon: lazy init
        self._running = True

        # Iniciar tasks para cada schedule
        for schedule in self._schedules.values():
            if schedule.enabled:
                self._start_schedule_task(schedule)

        logger.info(
            "AutonomousScheduler iniciado con %d schedules",
            len(self._schedules),
        )

    async def stop(self) -> None:
        """Para el scheduler limpiamente."""
        self._running = False
        for task in list(self._timer_tasks.values()) + list(self._event_tasks.values()):
            task.cancel()
        logger.info("AutonomousScheduler detenido")

    # --------------------------------------------------------
    # Agregar schedules
    # --------------------------------------------------------
    def add_interval(
        self,
        name: str,
        agent: str,
        task: str,
        seconds: float,
        priority: str = DEFAULT_PRIORITY,
        context: dict | None = None,
        start_immediately: bool = False,
    ) -> Schedule:
        """Agrega una tarea que se ejecuta cada N segundos."""
        schedule = Schedule(
            name=name,
            trigger_type=TriggerType.INTERVAL,
            agent_name=agent,
            task_template=task,
            priority=priority,
            interval_seconds=seconds,
            next_run=time.time() + (0 if start_immediately else seconds),
            context=context or {},
        )
        self._register(schedule)
        return schedule

    def add_cron(
        self,
        name: str,
        agent: str,
        task: str,
        cron_expression: str,
        priority: str = DEFAULT_PRIORITY,
        context: dict | None = None,
    ) -> Schedule:
        """Agrega una tarea con expresión cron (5 campos)."""
        next_run = CronParser.next_occurrence(cron_expression)
        schedule = Schedule(
            name=name,
            trigger_type=TriggerType.CRON,
            agent_name=agent,
            task_template=task,
            priority=priority,
            cron_expression=cron_expression,
            next_run=next_run,
            context=context or {},
        )
        self._register(schedule)
        return schedule

    def add_event_trigger(
        self,
        name: str,
        channel: str,
        agent: str,
        task_template: str,
        priority: str = DEFAULT_PRIORITY,
        context: dict | None = None,
    ) -> Schedule:
        """
        Agrega una tarea que se dispara cuando se publica en un canal.
        El task_template puede usar {key} para interpolar campos del payload.
        """
        schedule = Schedule(
            name=name,
            trigger_type=TriggerType.EVENT,
            agent_name=agent,
            task_template=task_template,
            priority=priority,
            event_channel=channel,
            context=context or {},
        )
        self._register(schedule)
        return schedule

    def add_one_shot(
        self,
        name: str,
        agent: str,
        task: str,
        delay_seconds: float = 0.0,
        priority: str = DEFAULT_PRIORITY,
        context: dict | None = None,
    ) -> Schedule:
        """Agrega una tarea que se ejecuta una sola vez después de delay."""
        schedule = Schedule(
            name=name,
            trigger_type=TriggerType.ONE_SHOT,
            agent_name=agent,
            task_template=task,
            priority=priority,
            delay_seconds=delay_seconds,
            next_run=time.time() + delay_seconds,
            context=context or {},
        )
        self._register(schedule)
        return schedule

    def remove(self, name: str) -> bool:
        """Elimina un schedule por nombre."""
        schedule = self._schedules.get(name)
        if not schedule:
            return False

        # Cancelar tasks asociadas
        for task_dict in [self._timer_tasks, self._event_tasks]:
            task = task_dict.pop(name, None)
            if task:
                task.cancel()

        del self._schedules[name]
        self._delete_from_db(schedule.schedule_id)
        logger.info("Schedule '%s' eliminado", name)
        return True

    def enable(self, name: str) -> bool:
        """Habilita un schedule."""
        schedule = self._schedules.get(name)
        if not schedule:
            return False
        schedule.enabled = True
        self._start_schedule_task(schedule)
        self._save_to_db(schedule)
        return True

    def disable(self, name: str) -> bool:
        """Deshabilita un schedule (no cancela la tarea activa actual)."""
        schedule = self._schedules.get(name)
        if not schedule:
            return False
        schedule.enabled = False
        self._save_to_db(schedule)
        return True

    # --------------------------------------------------------
    # Loop de timers (Interval + Cron + OneShot)
    # --------------------------------------------------------
    def _start_schedule_task(self, schedule: Schedule) -> None:
        """Inicia la asyncio task correspondiente al tipo de trigger."""
        if not self._running:
            return  # No crear tasks si el scheduler no está corriendo
        if schedule.trigger_type == TriggerType.EVENT:
            if schedule.name not in self._event_tasks:
                task = asyncio.create_task(
                    self._event_loop(schedule),
                    name=f"scheduler-event-{schedule.name}",
                )
                self._event_tasks[schedule.name] = task
        else:
            if schedule.name not in self._timer_tasks:
                task = asyncio.create_task(
                    self._timer_loop(schedule),
                    name=f"scheduler-timer-{schedule.name}",
                )
                self._timer_tasks[schedule.name] = task

    async def _timer_loop(self, schedule: Schedule) -> None:
        """Loop para triggers de tiempo (interval, cron, one_shot)."""
        while self._running and schedule.enabled:
            try:
                now = time.time()
                next_run = schedule.next_run or now

                wait = max(0.0, next_run - now)
                if wait > 0:
                    await asyncio.sleep(wait)

                if not self._running or not schedule.enabled:
                    break

                # Ejecutar tarea
                await self._fire(schedule, event_data={})

                # Calcular próxima ejecución
                if schedule.trigger_type == TriggerType.INTERVAL:
                    schedule.next_run = time.time() + (schedule.interval_seconds or 60)
                elif schedule.trigger_type == TriggerType.CRON:
                    schedule.next_run = CronParser.next_occurrence(
                        schedule.cron_expression or "* * * * *"
                    )
                elif schedule.trigger_type == TriggerType.ONE_SHOT:
                    # No repetir
                    schedule.enabled = False
                    self._timer_tasks.pop(schedule.name, None)
                    break

                self._save_to_db(schedule)

            except asyncio.CancelledError:
                return
            except Exception as e:
                schedule.last_error = str(e)
                logger.error("Error en schedule '%s': %s", schedule.name, e)
                await asyncio.sleep(10)

    async def _event_loop(self, schedule: Schedule) -> None:
        """Loop para triggers de eventos (escucha el canal del bus)."""
        channel = schedule.event_channel or ""
        if not channel:
            logger.warning("Schedule '%s' sin canal de evento", schedule.name)
            return

        consumer_name = f"scheduler-{schedule.name[:20]}"
        async for msg in self._bus.subscribe(channel, consumer_name=consumer_name):  # type: ignore[union-attr,attr-defined]  # bus: nullable, checked at runtime
            if not self._running or not schedule.enabled:
                break
            try:
                await self._fire(schedule, event_data=msg.payload)
                await self._bus.ack(msg)  # type: ignore[union-attr,attr-defined]  # bus: nullable, checked at runtime
            except asyncio.CancelledError:
                return
            except Exception as e:
                schedule.last_error = str(e)
                logger.error("Error en event schedule '%s': %s", schedule.name, e)

    async def _fire(self, schedule: Schedule, event_data: dict) -> None:
        """Dispara la ejecución de una tarea."""
        # Interpolar template con datos del evento
        try:
            task = schedule.task_template.format(**{**event_data, **schedule.context})
        except KeyError:
            task = schedule.task_template

        schedule.run_count += 1
        schedule.last_run = time.time()
        schedule.last_error = None

        logger.info(
            "Scheduler disparando '%s' → agente='%s' tarea='%.60s...'",
            schedule.name,
            schedule.agent_name,
            task,
        )

        # Registrar ejecución en BD
        run_id = str(uuid.uuid4())
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO schedule_runs (run_id, schedule_id, started_at) VALUES (?,?,?)",
                (run_id, schedule.schedule_id, time.time()),
            )
            conn.commit()

        # Enviar al daemon
        try:
            task_id = await self._daemon.submit_task(  # type: ignore[union-attr,attr-defined]  # daemon: nullable, checked at runtime
                agent_name=schedule.agent_name,
                task=task,
                from_agent=f"scheduler:{schedule.name}",
                context=schedule.context,
                priority_name=schedule.priority,
            )
            # Actualizar run con task_id
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "UPDATE schedule_runs SET task_id=?, status='submitted' WHERE run_id=?",
                    (task_id, run_id),
                )
                conn.commit()
        except Exception as e:
            schedule.last_error = str(e)
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "UPDATE schedule_runs SET status='error', error=? WHERE run_id=?",
                    (str(e), run_id),
                )
                conn.commit()
            raise

    # --------------------------------------------------------
    # Persistencia
    # --------------------------------------------------------
    def _register(self, schedule: Schedule) -> None:
        """Registra un schedule en memoria y BD."""
        self._schedules[schedule.name] = schedule
        self._save_to_db(schedule)
        if self._running and schedule.enabled:
            self._start_schedule_task(schedule)
        logger.info(
            "Schedule registrado: '%s' [%s] agente='%s'",
            schedule.name,
            schedule.trigger_type.value,
            schedule.agent_name,
        )

    def _save_to_db(self, schedule: Schedule) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO schedules
                   (schedule_id, name, config_json, created_at, updated_at)
                   VALUES (?,?,?,?,?)""",
                (
                    schedule.schedule_id,
                    schedule.name,
                    json.dumps(schedule.to_dict()),
                    schedule.last_run or time.time(),
                    time.time(),
                ),
            )
            conn.commit()

    def _delete_from_db(self, schedule_id: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM schedules WHERE schedule_id=?", (schedule_id,))
            conn.commit()

    def _load_from_db(self) -> None:
        """Carga schedules persistidos de ejecuciones anteriores."""
        try:
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute(
                    "SELECT config_json FROM schedules ORDER BY created_at"
                ).fetchall()

            for (config_json,) in rows:
                data = json.loads(config_json)
                schedule = Schedule(
                    name=data["name"],
                    trigger_type=TriggerType(data["trigger_type"]),
                    agent_name=data["agent_name"],
                    task_template=data["task_template"],
                    priority=data.get("priority", DEFAULT_PRIORITY),
                    enabled=data.get("enabled", True),
                    interval_seconds=data.get("interval_seconds"),
                    cron_expression=data.get("cron_expression"),
                    event_channel=data.get("event_channel"),
                    delay_seconds=data.get("delay_seconds"),
                    run_count=data.get("run_count", 0),
                    last_run=data.get("last_run"),
                    next_run=data.get("next_run"),
                    schedule_id=data["schedule_id"],
                )
                # Para one_shot ya ejecutados, no re-cargar
                if schedule.trigger_type == TriggerType.ONE_SHOT and schedule.run_count > 0:
                    continue
                self._schedules[schedule.name] = schedule

            if self._schedules:
                logger.info("Cargados %d schedules desde BD", len(self._schedules))
        except Exception as e:
            logger.warning("No se pudieron cargar schedules desde BD: %s", e)

    # --------------------------------------------------------
    # API pública
    # --------------------------------------------------------
    def list_schedules(self) -> list[dict[str, Any]]:
        """Lista todos los schedules con su estado."""
        return [s.to_dict() for s in self._schedules.values()]

    def get_schedule(self, name: str) -> dict[str, Any] | None:
        """Obtiene un schedule por nombre."""
        s = self._schedules.get(name)
        return s.to_dict() if s else None

    def get_run_history(self, schedule_name: str | None = None, limit: int = 50) -> list[dict]:
        """Obtiene el historial de ejecuciones."""
        try:
            with sqlite3.connect(self._db_path) as conn:
                if schedule_name and schedule_name in self._schedules:
                    sid = self._schedules[schedule_name].schedule_id
                    rows = conn.execute(
                        "SELECT * FROM schedule_runs WHERE schedule_id=? ORDER BY started_at DESC LIMIT ?",
                        (sid, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM schedule_runs ORDER BY started_at DESC LIMIT ?", (limit,)
                    ).fetchall()

                return [
                    {
                        "run_id": r[0],
                        "schedule_id": r[1],
                        "task_id": r[2],
                        "started_at": r[3],
                        "status": r[4],
                        "error": r[5],
                    }
                    for r in rows
                ]
        except Exception:
            return []


# ============================================================
# Singleton global
# ============================================================
_scheduler_instance: AutonomousScheduler | None = None


async def get_scheduler() -> AutonomousScheduler:
    """Obtiene o crea el scheduler global."""
    global _scheduler_instance
    if _scheduler_instance is None or not _scheduler_instance._running:
        _scheduler_instance = AutonomousScheduler()
        await _scheduler_instance.start()
    return _scheduler_instance


# ============================================================
# Setup por defecto del ecosistema
# ============================================================
async def setup_default_schedules(scheduler: AutonomousScheduler) -> None:
    """
    Configura los schedules por defecto del ecosistema Antigravity.
    Se ejecuta al arrancar para activar la autonomía del sistema.
    """
    # Health check cada 5 minutos
    scheduler.add_interval(
        name="ecosystem-health-check",
        agent="devops-engineer",
        task="ejecuta un health check completo del ecosistema y reporta el estado",
        seconds=300,
        priority="LOW",
    )

    # Sincronización de índice de skills cada hora
    scheduler.add_interval(
        name="skills-index-sync",
        agent="explorer",
        task="sincroniza y valida el índice de skills del ecosistema",
        seconds=3600,
        priority="LOW",
    )

    # Limpieza de logs cada día (cron: medianoche)
    scheduler.add_cron(
        name="daily-log-cleanup",
        agent="devops-engineer",
        task="limpia logs antiguos de más de 7 días en el directorio .agent/",
        cron_expression="0 0 * * *",
        priority="BACKGROUND",
    )

    # Auto-documentación cuando se completa una tarea importante
    scheduler.add_event_trigger(
        name="auto-document-on-completion",
        channel="tasks.completed",
        agent="documentation-writer",
        task_template="documenta brevemente el resultado del agente {agent} con tarea: {task}",
        priority="BACKGROUND",
    )

    logger.info("Schedules por defecto del ecosistema configurados")
