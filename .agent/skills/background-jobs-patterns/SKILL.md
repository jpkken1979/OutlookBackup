---
name: background-jobs-patterns
description: Patrones para procesamiento asíncrono, cron jobs y workers. Esta skill cubre implementación de tareas en background, job queues, scheduling, y workers para procesamiento asíncrono.
type: feature
---

# Background Jobs Patterns

> Patrones para procesamiento asíncrono, cron jobs y workers.

---

## Descripción

Esta skill cubre implementación de tareas en background, job queues, scheduling, y workers para procesamiento asíncrono.

---

## Tecnologías

| Tecnología | Lenguaje | Broker | Caso de Uso |
|------------|----------|--------|-------------|
| **BullMQ** | Node.js | Redis | Jobs con prioridad, retry |
| **Celery** | Python | Redis/RabbitMQ | Tasks distribuidas |
| **Sidekiq** | Ruby | Redis | Background jobs |
| **Agenda** | Node.js | MongoDB | Scheduling |
| **node-cron** | Node.js | In-memory | Cron simple |

---

## BullMQ (Node.js)

### Setup

```typescript
import { Queue, Worker, QueueScheduler } from 'bullmq';
import Redis from 'ioredis';

const connection = new Redis(process.env.REDIS_URL, {
  maxRetriesPerRequest: null,
});

// Crear queue
const emailQueue = new Queue('emails', { connection });

// Scheduler para delayed jobs
const scheduler = new QueueScheduler('emails', { connection });
```

### Definir Jobs

```typescript
interface EmailJobData {
  to: string;
  subject: string;
  template: string;
  variables: Record<string, any>;
}

// Agregar job
async function queueEmail(data: EmailJobData) {
  await emailQueue.add('send-email', data, {
    attempts: 3,
    backoff: {
      type: 'exponential',
      delay: 1000,
    },
    removeOnComplete: 100,
    removeOnFail: 1000,
  });
}

// Job con delay
async function scheduleReminder(userId: string, message: string, delayMs: number) {
  await emailQueue.add('reminder', { userId, message }, {
    delay: delayMs,
  });
}

// Job recurrente (cron)
async function scheduleDaily() {
  await emailQueue.add('daily-digest', {}, {
    repeat: {
      pattern: '0 9 * * *', // 9 AM todos los días
    },
  });
}
```

### Worker

```typescript
const worker = new Worker('emails', async (job) => {
  console.log(`Processing job ${job.id}: ${job.name}`);

  switch (job.name) {
    case 'send-email':
      await sendEmail(job.data);
      break;
    case 'reminder':
      await sendReminder(job.data);
      break;
    case 'daily-digest':
      await generateAndSendDigest();
      break;
  }

  return { success: true };
}, {
  connection,
  concurrency: 5,
  limiter: {
    max: 100,
    duration: 60000, // 100 jobs por minuto
  },
});

// Event handlers
worker.on('completed', (job, result) => {
  console.log(`Job ${job.id} completed:`, result);
});

worker.on('failed', (job, err) => {
  console.error(`Job ${job?.id} failed:`, err.message);
});

worker.on('progress', (job, progress) => {
  console.log(`Job ${job.id} progress: ${progress}%`);
});
```

### Progress y Resultados

```typescript
// Reportar progreso
const worker = new Worker('reports', async (job) => {
  const items = await getItems();
  let processed = 0;

  for (const item of items) {
    await processItem(item);
    processed++;
    await job.updateProgress(Math.round((processed / items.length) * 100));
  }

  return { totalProcessed: processed };
});

// Obtener resultado
const job = await reportQueue.add('generate', { userId: '123' });
const result = await job.waitUntilFinished(queueEvents);
```

---

## Celery (Python)

### Setup

```python
from celery import Celery

app = Celery('tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/1'
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    worker_prefetch_multiplier=1,
)
```

### Definir Tasks

```python
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@shared_task(bind=True, max_retries=3)
def send_email(self, to: str, subject: str, body: str):
    try:
        # Enviar email
        email_service.send(to, subject, body)
        logger.info(f"Email sent to {to}")
    except Exception as exc:
        logger.error(f"Failed to send email: {exc}")
        raise self.retry(exc=exc, countdown=60)

@shared_task(bind=True)
def process_large_file(self, file_path: str):
    total_lines = count_lines(file_path)
    processed = 0

    with open(file_path) as f:
        for line in f:
            process_line(line)
            processed += 1
            self.update_state(
                state='PROGRESS',
                meta={'current': processed, 'total': total_lines}
            )

    return {'processed': processed}
```

### Scheduling con Celery Beat

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    'daily-cleanup': {
        'task': 'tasks.cleanup_old_files',
        'schedule': crontab(hour=2, minute=0),  # 2 AM
    },
    'hourly-stats': {
        'task': 'tasks.calculate_stats',
        'schedule': crontab(minute=0),  # Cada hora
    },
    'every-5-minutes': {
        'task': 'tasks.health_check',
        'schedule': 300.0,  # 5 minutos
    },
}
```

### Chains y Groups

```python
from celery import chain, group, chord

# Chain: A -> B -> C (secuencial)
workflow = chain(
    fetch_data.s(url),
    process_data.s(),
    save_results.s()
)
result = workflow.apply_async()

# Group: A, B, C en paralelo
parallel = group(
    process_chunk.s(chunk) for chunk in chunks
)
result = parallel.apply_async()

# Chord: Group + callback cuando todos terminan
workflow = chord(
    (process_chunk.s(chunk) for chunk in chunks),
    aggregate_results.s()
)
result = workflow.apply_async()
```

---

## Patrones Comunes

### 1. Idempotencia

```typescript
const worker = new Worker('payments', async (job) => {
  const idempotencyKey = `payment:${job.data.orderId}`;

  // Verificar si ya se procesó
  const processed = await redis.get(idempotencyKey);
  if (processed) {
    console.log(`Payment already processed for order ${job.data.orderId}`);
    return JSON.parse(processed);
  }

  // Procesar pago
  const result = await processPayment(job.data);

  // Marcar como procesado
  await redis.set(idempotencyKey, JSON.stringify(result), 'EX', 86400);

  return result;
});
```

### 2. Dead Letter Queue

```typescript
const worker = new Worker('critical-jobs', async (job) => {
  // Procesar...
}, {
  connection,
});

worker.on('failed', async (job, err) => {
  if (job && job.attemptsMade >= job.opts.attempts!) {
    // Mover a DLQ después de agotar reintentos
    await deadLetterQueue.add('failed-job', {
      originalJob: job.data,
      error: err.message,
      failedAt: new Date().toISOString(),
      jobId: job.id,
    });
  }
});
```

### 3. Rate Limiting por Usuario

```typescript
// Queue por usuario para rate limiting
async function queueUserAction(userId: string, action: string, data: any) {
  const userQueue = new Queue(`user:${userId}`, { connection });

  await userQueue.add(action, data, {
    limiter: {
      max: 10,
      duration: 60000, // 10 acciones por minuto por usuario
    },
  });
}
```

### 4. Prioridades

```typescript
// Jobs con diferentes prioridades
await queue.add('task', data, { priority: 1 }); // Alta (se procesa primero)
await queue.add('task', data, { priority: 5 }); // Media
await queue.add('task', data, { priority: 10 }); // Baja

// Worker procesa por prioridad automáticamente
```

---

## Cron Jobs

### node-cron

```typescript
import cron from 'node-cron';

// Cada día a las 3 AM
cron.schedule('0 3 * * *', async () => {
  await cleanupOldSessions();
});

// Cada hora
cron.schedule('0 * * * *', async () => {
  await updateCaches();
});

// Cada 5 minutos
cron.schedule('*/5 * * * *', async () => {
  await healthCheck();
});

// Lunes a Viernes a las 9 AM
cron.schedule('0 9 * * 1-5', async () => {
  await sendDailyReport();
});
```

### Cron Distribuido (con Lock)

```typescript
import cron from 'node-cron';
import Redlock from 'redlock';

const redlock = new Redlock([redis]);

cron.schedule('0 * * * *', async () => {
  let lock;
  try {
    // Solo una instancia ejecuta
    lock = await redlock.acquire(['lock:hourly-job'], 5000);
    await hourlyJob();
  } catch (err) {
    // Otra instancia tiene el lock
    console.log('Skipping: another instance is running');
  } finally {
    if (lock) await lock.release();
  }
});
```

---

## Monitoreo

### Dashboard con Bull Board

```typescript
import { createBullBoard } from '@bull-board/api';
import { BullMQAdapter } from '@bull-board/api/bullMQAdapter';
import { ExpressAdapter } from '@bull-board/express';

const serverAdapter = new ExpressAdapter();

createBullBoard({
  queues: [
    new BullMQAdapter(emailQueue),
    new BullMQAdapter(reportQueue),
  ],
  serverAdapter,
});

app.use('/admin/queues', serverAdapter.getRouter());
```

### Métricas

```typescript
import { QueueEvents } from 'bullmq';

const queueEvents = new QueueEvents('emails', { connection });

const metrics = {
  completed: 0,
  failed: 0,
  processingTime: [] as number[],
};

queueEvents.on('completed', ({ jobId, returnvalue }) => {
  metrics.completed++;
});

queueEvents.on('failed', ({ jobId, failedReason }) => {
  metrics.failed++;
});

// Exponer métricas
app.get('/metrics/queues', async (req, res) => {
  const counts = await emailQueue.getJobCounts();
  res.json({
    ...counts,
    ...metrics,
    avgProcessingTime: metrics.processingTime.reduce((a, b) => a + b, 0) / metrics.processingTime.length,
  });
});
```

---

## Referencias

- [BullMQ Documentation](https://docs.bullmq.io/)
- [Celery Documentation](https://docs.celeryq.dev/)
- [node-cron](https://github.com/node-cron/node-cron)
- [Agenda](https://github.com/agenda/agenda)

---

*Skill creada: 2026-02-01*
*Versión: 1.0.0*
