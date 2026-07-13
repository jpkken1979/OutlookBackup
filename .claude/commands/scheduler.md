# /scheduler — AI Scheduler para Google Calendar

Invoque el agente **ai-scheduler** para automatizar scheduling del equipo de dispatch.
Convierte objectives de texto libre en eventos de Google Calendar via OAuth2.

## Comandos

### /scheduler status
Ver el estado actual del scheduler:
- OAuth status
- Ultimo objective procesado
- Eventos creados total
- Horas total agendadas

### /scheduler book \<objective\>
Procesar un objective de scheduling.

```bash
# Ejemplos:
/scheduler book "bloquear 10hs de focus time esta semana"
/scheduler book "reservar 2hs para preparar presentation el miercoles"
/scheduler book "schedule 4hs de admin work"
```

**Flujo:**
1. Parsea el objective (duracion, prioridad, periodo)
2. Detecta conflictos con eventos existentes
3. Muestra plan para confirmacion humana
4. Crea evento en Google Calendar
5. Notifica al gateway

### /scheduler list
Listar eventos creados por el scheduler.

```bash
/scheduler list              # Proximos 7 dias
/scheduler list --days 30    # Proximos 30 dias
```

### /scheduler setup
Configurar OAuth2 por primera vez.

```bash
/scheduler setup
```

Necesita:
- `GOOGLE_CALENDAR_CLIENT_ID` en `.env`
- `GOOGLE_CALENDAR_CLIENT_SECRET` en `.env`

Abre browser para authorization y guarda tokens en `~/.antigravity/scheduler/credentials.json`.

## Setup Requerido

### Google Cloud Console

1. Ir a https://console.cloud.google.com/apis/credentials
2. Crear "OAuth client ID" (Desktop app)
3. Copiar Client ID y Client Secret

### Agregar al .env

```bash
GOOGLE_CALENDAR_CLIENT_ID=tu_client_id
GOOGLE_CALENDAR_CLIENT_SECRET=tu_client_secret
```

### Autorizar

```bash
python .agent/agents/scheduler/scripts/scheduler.py setup
```

## Prioridades

| Prioridad | Color | Cuando |
|---|---|---|
| critical | Rojo | Debe agendarse hoy |
| high | Amarillo | Agendar esta semana |
| medium | Azul | Agendar cuando sea posible |
| low | Gris | Solo si queda tiempo |

## Conflict Detection

El scheduler **nunca sobreescribe eventos existentes**.
Antes de reservar:
1. Obtiene todos los eventos del periodo
2. Verifica cada slot candidato
3. Salta slots que overlap con eventos existentes
4. Sugiere alternativas si no hay slots disponibles

## Notification al Gateway

Cuando se crea un evento, notifica automaticamente a `:4747/v1/events`.
Esto permite que otros agentes o Nexus reaccionen al scheduling.

## Errores comunes

| Error | Solucion |
|---|---|
| "Credentials not found in .env" | Agregar GOOGLE_CALENDAR_CLIENT_ID/SECRET al .env |
| "No refresh token available" | Correr `setup` de nuevo para re-autorizar |
| "No available slots" | Probar con duracion menor o periodo mas largo |
| "API quota exceeded" | Esperar y reintentar (max 3 intentos automaticos) |

## Implementacion

- Agente: `.agent/agents/scheduler/`
- Skill: `.agent/skills-custom/ai-scheduler/`
- Token cache: `~/.antigravity/scheduler/credentials.json`
