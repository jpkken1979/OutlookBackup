#!/usr/bin/env python3
"""
Background Jobs Patterns Demo

Este script demuestra patrones de jobs en background incluyendo:
- Cola de tareas en memoria
- Workers y procesamiento
- Retry con backoff exponencial
- Dead Letter Queue
- Scheduling/Cron jobs

Uso:
    python jobs_demo.py --demo basic
    python jobs_demo.py --demo retry
    python jobs_demo.py --demo scheduler
"""

import argparse
import logging
import random
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from queue import Queue, Empty
from typing import Any
from collections.abc import Callable
from uuid import uuid4

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Estados de un job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    DEAD = "dead"


@dataclass
class Job:
    """Representación de un job."""

    id: str
    name: str
    data: dict
    status: JobStatus = JobStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    processed_at: datetime | None = None
    error: str | None = None
    result: Any | None = None


class InMemoryJobQueue:
    """
    Cola de jobs en memoria para demostración.

    En producción, usar Redis/BullMQ, RabbitMQ o Celery.
    """

    def __init__(self, name: str = "default") -> None:
        self.name = name
        self.queue: Queue[Job] = Queue()
        self.completed: list[Job] = []
        self.failed: list[Job] = []
        self.dead_letter: list[Job] = []
        self.handlers: dict[str, Callable] = {}
        self._running = False
        self._workers: list[threading.Thread] = []
        logger.info(f"Cola '{name}' inicializada")

    def register_handler(self, job_name: str, handler: Callable) -> None:
        """Registrar handler para un tipo de job."""
        self.handlers[job_name] = handler
        logger.info(f"Handler registrado para '{job_name}'")

    def add_job(self, name: str, data: dict, max_attempts: int = 3, delay_seconds: int = 0) -> Job:
        """Añadir job a la cola."""
        job = Job(id=str(uuid4())[:8], name=name, data=data, max_attempts=max_attempts)

        if delay_seconds > 0:
            # Simular delay (en producción usar delay de Redis/RabbitMQ)
            logger.info(f"Job {job.id} programado con delay de {delay_seconds}s")
            threading.Timer(delay_seconds, lambda: self.queue.put(job)).start()
        else:
            self.queue.put(job)

        logger.info(f"Job añadido: {job.id} ({job.name})")
        return job

    def process_job(self, job: Job) -> None:
        """Procesar un job individual."""
        job.status = JobStatus.PROCESSING
        job.attempts += 1

        logger.info(f"Procesando job {job.id} (intento {job.attempts}/{job.max_attempts})")

        handler = self.handlers.get(job.name)
        if not handler:
            job.status = JobStatus.FAILED
            job.error = f"No handler for job type: {job.name}"
            self.failed.append(job)
            return

        try:
            result = handler(job.data)
            job.status = JobStatus.COMPLETED
            job.result = result
            job.processed_at = datetime.now()
            self.completed.append(job)
            logger.info(f"Job {job.id} completado exitosamente")

        except Exception as e:
            job.error = str(e)

            if job.attempts < job.max_attempts:
                # Retry con backoff exponencial
                job.status = JobStatus.RETRY
                delay = 2**job.attempts  # 2, 4, 8 segundos
                logger.warning(f"Job {job.id} falló, retry en {delay}s: {e}")
                threading.Timer(delay, lambda: self.queue.put(job)).start()
            else:
                # Mover a Dead Letter Queue
                job.status = JobStatus.DEAD
                self.dead_letter.append(job)
                logger.error(f"Job {job.id} movido a DLQ después de {job.attempts} intentos")

    def start_workers(self, num_workers: int = 2) -> None:
        """Iniciar workers para procesar jobs."""
        self._running = True

        for i in range(num_workers):
            worker = threading.Thread(target=self._worker_loop, args=(i,), daemon=True)
            worker.start()
            self._workers.append(worker)

        logger.info(f"Iniciados {num_workers} workers")

    def stop_workers(self) -> None:
        """Detener workers."""
        self._running = False
        for worker in self._workers:
            worker.join(timeout=1)
        self._workers = []
        logger.info("Workers detenidos")

    def _worker_loop(self, worker_id: int) -> None:
        """Loop principal de un worker."""
        logger.debug(f"Worker {worker_id} iniciado")

        while self._running:
            try:
                job = self.queue.get(timeout=0.5)
                self.process_job(job)
            except Empty:
                continue

    def get_stats(self) -> dict:
        """Obtener estadísticas de la cola."""
        return {
            "queue_name": self.name,
            "pending": self.queue.qsize(),
            "completed": len(self.completed),
            "failed": len(self.failed),
            "dead_letter": len(self.dead_letter),
            "workers": len(self._workers),
        }


class JobScheduler:
    """
    Programador de jobs tipo cron.

    Soporta intervalos y expresiones cron simplificadas.
    """

    def __init__(self, queue: InMemoryJobQueue) -> None:
        self.queue = queue
        self.scheduled_jobs: list[dict] = []
        self._running = False
        self._thread: threading.Thread | None = None

    def schedule_interval(self, job_name: str, data: dict, interval_seconds: int) -> str:
        """Programar job que se ejecuta cada N segundos."""
        schedule_id = str(uuid4())[:8]

        self.scheduled_jobs.append(
            {
                "id": schedule_id,
                "job_name": job_name,
                "data": data,
                "interval": interval_seconds,
                "next_run": datetime.now(),
                "type": "interval",
            }
        )

        logger.info(f"Job '{job_name}' programado cada {interval_seconds}s (id: {schedule_id})")
        return schedule_id

    def schedule_once(self, job_name: str, data: dict, run_at: datetime) -> str:
        """Programar job para ejecutarse una vez."""
        schedule_id = str(uuid4())[:8]

        self.scheduled_jobs.append(
            {
                "id": schedule_id,
                "job_name": job_name,
                "data": data,
                "next_run": run_at,
                "type": "once",
            }
        )

        logger.info(f"Job '{job_name}' programado para {run_at} (id: {schedule_id})")
        return schedule_id

    def start(self) -> None:
        """Iniciar el scheduler."""
        self._running = True
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._thread.start()
        logger.info("Scheduler iniciado")

    def stop(self) -> None:
        """Detener el scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        logger.info("Scheduler detenido")

    def _scheduler_loop(self) -> None:
        """Loop principal del scheduler."""
        while self._running:
            now = datetime.now()

            for schedule in self.scheduled_jobs[:]:
                if schedule["next_run"] <= now:
                    # Ejecutar job
                    self.queue.add_job(name=schedule["job_name"], data=schedule["data"])

                    if schedule["type"] == "interval":
                        # Reprogramar
                        schedule["next_run"] = now + timedelta(seconds=schedule["interval"])
                    else:
                        # Remover job de una sola ejecución
                        self.scheduled_jobs.remove(schedule)

            time.sleep(0.5)


# Handlers de ejemplo
def send_email_handler(data: dict) -> dict:
    """Handler para envío de emails."""
    logger.info(f"Enviando email a {data.get('to')}: {data.get('subject')}")
    time.sleep(0.3)  # Simular envío
    return {"status": "sent", "to": data.get("to")}


def process_payment_handler(data: dict) -> dict:
    """Handler para procesar pagos (puede fallar)."""
    amount = data.get("amount", 0)

    # Simular fallo aleatorio
    if random.random() < 0.3:  # 30% de probabilidad de fallo
        raise Exception("Payment gateway timeout")

    logger.info(f"Pago procesado: ${amount}")
    time.sleep(0.2)
    return {"status": "processed", "amount": amount}


def generate_report_handler(data: dict) -> dict:
    """Handler para generar reportes."""
    report_type = data.get("type", "daily")
    logger.info(f"Generando reporte {report_type}...")
    time.sleep(0.5)  # Simular generación
    return {"status": "generated", "type": report_type, "pages": 15}


def demo_basic_queue() -> None:
    """Demostrar cola básica de jobs."""
    logger.info("=== Demo: Cola Básica ===")

    queue = InMemoryJobQueue("demo")

    # Registrar handlers
    queue.register_handler("send_email", send_email_handler)
    queue.register_handler("generate_report", generate_report_handler)

    # Iniciar workers
    queue.start_workers(num_workers=2)

    # Añadir jobs
    print("\n1. Añadiendo jobs a la cola...")
    queue.add_job("send_email", {"to": "user@example.com", "subject": "Bienvenido"})
    queue.add_job("send_email", {"to": "admin@example.com", "subject": "Alerta"})
    queue.add_job("generate_report", {"type": "weekly"})

    # Esperar procesamiento
    time.sleep(2)

    # Mostrar estadísticas
    stats = queue.get_stats()
    print("\n2. Estadísticas:")
    print(f"   - Pendientes: {stats['pending']}")
    print(f"   - Completados: {stats['completed']}")
    print(f"   - Fallidos: {stats['failed']}")

    queue.stop_workers()


def demo_retry_mechanism() -> None:
    """Demostrar mecanismo de retry y DLQ."""
    logger.info("=== Demo: Retry y Dead Letter Queue ===")

    queue = InMemoryJobQueue("payments")

    # Handler que puede fallar
    queue.register_handler("process_payment", process_payment_handler)

    queue.start_workers(num_workers=1)

    print("\n1. Procesando pagos (algunos fallarán)...")
    for i in range(5):
        queue.add_job(
            "process_payment", {"amount": (i + 1) * 100, "order_id": f"ORD-{i + 1}"}, max_attempts=3
        )

    # Esperar procesamiento con retries
    time.sleep(15)

    stats = queue.get_stats()
    print("\n2. Resultados:")
    print(f"   - Completados: {stats['completed']}")
    print(f"   - En Dead Letter Queue: {stats['dead_letter']}")

    if queue.dead_letter:
        print("\n3. Jobs en DLQ:")
        for job in queue.dead_letter:
            print(f"   - Job {job.id}: {job.error} (intentos: {job.attempts})")

    queue.stop_workers()


def demo_scheduler() -> None:
    """Demostrar scheduler de jobs."""
    logger.info("=== Demo: Scheduler ===")

    queue = InMemoryJobQueue("scheduled")
    scheduler = JobScheduler(queue)

    queue.register_handler("generate_report", generate_report_handler)
    queue.register_handler("send_email", send_email_handler)

    queue.start_workers(num_workers=1)
    scheduler.start()

    print("\n1. Programando jobs...")

    # Job que se ejecuta cada 3 segundos
    scheduler.schedule_interval("generate_report", {"type": "metrics"}, interval_seconds=3)

    # Job programado para dentro de 2 segundos
    scheduler.schedule_once(
        "send_email",
        {"to": "boss@company.com", "subject": "Reporte Urgente"},
        run_at=datetime.now() + timedelta(seconds=2),
    )

    print("2. Esperando ejecuciones (10 segundos)...")
    time.sleep(10)

    stats = queue.get_stats()
    print(f"\n3. Jobs ejecutados: {stats['completed']}")

    scheduler.stop()
    queue.stop_workers()


def main() -> None:
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Background Jobs Patterns Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
    python jobs_demo.py --demo basic
    python jobs_demo.py --demo retry
    python jobs_demo.py --demo scheduler
    python jobs_demo.py --demo all
        """,
    )

    parser.add_argument(
        "--demo",
        choices=["basic", "retry", "scheduler", "all"],
        default="all",
        help="Tipo de demo a ejecutar",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("       BACKGROUND JOBS PATTERNS DEMO")
    print("=" * 60)

    if args.demo in ("basic", "all"):
        demo_basic_queue()
        print()

    if args.demo in ("retry", "all"):
        demo_retry_mechanism()
        print()

    if args.demo in ("scheduler", "all"):
        demo_scheduler()

    print("\n" + "=" * 60)
    print("Demo completada. Ver SKILL.md para patrones de producción")
    print("con BullMQ, Celery y RabbitMQ.")
    print("=" * 60)


if __name__ == "__main__":
    main()
