---
description: Diseño de arquitectura de software sistemático. Workflow universal compatible con cualquier LLM.
universal: true
---

# /architect - Diseño de Arquitectura

> Workflow universal compatible con: Claude, GPT-4, Gemini, Codex, Llama, Mistral

## Requisito de Arquitectura

$ARGUMENTS

---

## Proceso de Diseño

### Fase 1: Análisis de Requisitos

```markdown
## Análisis de Requisitos

### Requisitos Funcionales
| ID | Requisito | Prioridad | Complejidad |
|----|-----------|-----------|-------------|
| RF-01 | [descripción] | [Alta/Media/Baja] | [Alta/Media/Baja] |

### Requisitos No Funcionales

#### Performance
- **Latencia esperada:** [X ms]
- **Throughput:** [X req/s]
- **Usuarios concurrentes:** [X]

#### Escalabilidad
- **Crecimiento esperado:** [X% anual]
- **Tipo:** [Horizontal/Vertical]

#### Disponibilidad
- **SLA objetivo:** [99.X%]
- **RTO:** [X horas]
- **RPO:** [X horas]

#### Seguridad
- **Autenticación:** [método]
- **Datos sensibles:** [descripción]
- **Compliance:** [GDPR, SOC2, etc.]

### Constraints
- **Presupuesto:** [descripción]
- **Timeline:** [descripción]
- **Equipo:** [tamaño y skills]
- **Tecnologías existentes:** [lista]
```

---

### Fase 2: Diseño de Alto Nivel

```markdown
## Arquitectura de Alto Nivel

### Diagrama de Contexto (C1)

\`\`\`
┌─────────────────────────────────────────────────────────────┐
│                        SISTEMA                               │
│                                                              │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                 │
│  │ Frontend│    │ Backend │    │ Database│                 │
│  └─────────┘    └─────────┘    └─────────┘                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
        ▲                                      │
        │                                      │
    ┌───┴───┐                          ┌───────┴───────┐
    │Usuario│                          │Servicios Ext. │
    └───────┘                          └───────────────┘
\`\`\`

### Estilo Arquitectónico
- [ ] Monolito
- [ ] Microservicios
- [ ] Serverless
- [ ] Event-Driven
- [ ] Híbrido

### Justificación
[Por qué este estilo para este proyecto]
```

---

### Fase 3: Diseño de Componentes

```markdown
## Componentes del Sistema

### Diagrama de Contenedores (C2)

\`\`\`
┌──────────────────────────────────────────────────────────────────┐
│                          FRONTEND                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   Web App       │  │   Mobile App    │  │   Admin Panel   │  │
│  │   (React/Next)  │  │   (React Native)│  │   (React)       │  │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘  │
└───────────┼────────────────────┼────────────────────┼────────────┘
            │                    │                    │
            └────────────────────┼────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │      API GATEWAY        │
                    │    (Kong/AWS/nginx)     │
                    └────────────┬────────────┘
                                 │
┌────────────────────────────────┼────────────────────────────────┐
│                          BACKEND                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Auth Service│  │ Core Service│  │ Notification│              │
│  │  (FastAPI)  │  │  (FastAPI)  │  │   Service   │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
└─────────┼────────────────┼────────────────┼─────────────────────┘
          │                │                │
┌─────────┼────────────────┼────────────────┼─────────────────────┐
│         │            DATA LAYER           │                      │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐              │
│  │ PostgreSQL  │  │    Redis    │  │Elasticsearch│              │
│  │  (Primary)  │  │   (Cache)   │  │  (Search)   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
\`\`\`

### Descripción de Componentes

| Componente | Responsabilidad | Tecnología | Comunicación |
|------------|-----------------|------------|--------------|
| Web App | UI principal | Next.js | REST/GraphQL |
| API Gateway | Routing, Auth | Kong | HTTP/gRPC |
| Auth Service | Autenticación | FastAPI | REST |
| Core Service | Lógica negocio | FastAPI | REST |
| PostgreSQL | Datos primarios | PostgreSQL | SQL |
| Redis | Cache, sessions | Redis | Redis Protocol |
```

---

### Fase 4: Decisiones Arquitectónicas

```markdown
## ADR (Architecture Decision Records)

### ADR-001: [Título de la Decisión]

**Estado:** Aceptada
**Fecha:** [fecha]
**Contexto:** [situación que motiva la decisión]

**Decisión:**
[La decisión tomada]

**Alternativas Consideradas:**
1. [Alternativa 1] - Rechazada porque [razón]
2. [Alternativa 2] - Rechazada porque [razón]

**Consecuencias:**
- Positivas: [lista]
- Negativas: [lista]
- Riesgos: [lista]

---

### ADR-002: Elección de Base de Datos

**Estado:** Aceptada
**Contexto:** Necesitamos persistencia de datos relacional con soporte para consultas complejas.

**Decisión:** PostgreSQL como base de datos principal.

**Alternativas Consideradas:**
1. MySQL - Menor soporte para JSON y tipos avanzados
2. MongoDB - Modelo relacional es más apropiado para nuestros datos

**Consecuencias:**
- Positivas: ACID, JSON support, extensiones, comunidad
- Negativas: Más complejo que SQLite para desarrollo
```

---

### Fase 5: Diseño de APIs

```markdown
## Diseño de APIs

### REST API Endpoints

\`\`\`yaml
/api/v1:
  /auth:
    POST /login         # Autenticación
    POST /register      # Registro
    POST /refresh       # Refresh token
    POST /logout        # Cerrar sesión

  /users:
    GET /               # Lista usuarios
    POST /              # Crear usuario
    GET /{id}           # Obtener usuario
    PUT /{id}           # Actualizar usuario
    DELETE /{id}        # Eliminar usuario

  /resources:
    GET /               # Lista con paginación
    POST /              # Crear recurso
    GET /{id}           # Obtener recurso
    PUT /{id}           # Actualizar recurso
    DELETE /{id}        # Eliminar recurso
\`\`\`

### Formato de Respuesta

\`\`\`json
{
  "status": "success",
  "data": { ... },
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 100
  }
}
\`\`\`

### Códigos de Error

| Código | Significado |
|--------|-------------|
| 400 | Bad Request - Validación fallida |
| 401 | Unauthorized - No autenticado |
| 403 | Forbidden - Sin permisos |
| 404 | Not Found - Recurso no existe |
| 422 | Unprocessable Entity - Error de negocio |
| 500 | Internal Server Error |
```

---

### Fase 6: Diseño de Datos

```markdown
## Modelo de Datos

### Diagrama ER

\`\`\`
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   users     │       │   orders    │       │  products   │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ id (PK)     │──┐    │ id (PK)     │    ┌──│ id (PK)     │
│ email       │  │    │ user_id(FK) │◄───┤  │ name        │
│ name        │  └───►│ status      │    │  │ price       │
│ created_at  │       │ total       │    │  │ stock       │
└─────────────┘       │ created_at  │    │  └─────────────┘
                      └─────────────┘    │
                             │           │
                      ┌──────▼──────┐    │
                      │ order_items │    │
                      ├─────────────┤    │
                      │ id (PK)     │    │
                      │ order_id(FK)│    │
                      │ product_id  │────┘
                      │ quantity    │
                      │ price       │
                      └─────────────┘
\`\`\`

### Estrategia de Migraciones
- Tool: [Alembic/Flyway/Prisma]
- Versionado: [timestamp/sequential]
- Rollback: [estrategia]
```

---

### Fase 7: Infraestructura

```markdown
## Infraestructura

### Ambiente de Desarrollo
\`\`\`yaml
services:
  app:
    build: .
    ports:
      - "3000:3000"
    depends_on:
      - db
      - redis

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: app_dev
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev

  redis:
    image: redis:7-alpine
\`\`\`

### Ambiente de Producción

\`\`\`
┌─────────────────────────────────────────────────────────────┐
│                         CDN                                  │
│                    (CloudFlare)                              │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                    Load Balancer                             │
│                   (AWS ALB/nginx)                            │
└─────────────────────────┬───────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
    ┌─────────┐      ┌─────────┐      ┌─────────┐
    │  App 1  │      │  App 2  │      │  App 3  │
    │(Container)│    │(Container)│    │(Container)│
    └─────────┘      └─────────┘      └─────────┘
         │                │                │
         └────────────────┼────────────────┘
                          ▼
              ┌───────────────────────┐
              │    Database (RDS)     │
              │   + Read Replicas     │
              └───────────────────────┘
\`\`\`

### Escalabilidad
- **Horizontal:** Auto-scaling basado en CPU/memoria
- **Base de datos:** Read replicas para queries
- **Cache:** Redis cluster para sesiones y cache
```

---

### Fase 8: Entrega

```markdown
## Resumen de Arquitectura

### Stack Tecnológico Final

| Capa | Tecnología | Justificación |
|------|------------|---------------|
| Frontend | Next.js 14 | SSR, performance, DX |
| API | FastAPI | Async, tipado, OpenAPI |
| Database | PostgreSQL | ACID, extensiones |
| Cache | Redis | Performance, pubsub |
| Infra | AWS/Docker | Escalabilidad |

### Métricas de Diseño

| Métrica | Objetivo |
|---------|----------|
| Latencia P95 | < 200ms |
| Disponibilidad | 99.9% |
| Time to Market | X semanas |

### Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| [riesgo] | [A/M/B] | [A/M/B] | [acción] |

### Próximos Pasos

1. [ ] Validar diseño con stakeholders
2. [ ] Crear POC de componentes críticos
3. [ ] Definir plan de implementación
4. [ ] Setup de infraestructura base
```

---

## Patrones Arquitectónicos

### Por Escala

| Usuarios | Patrón Recomendado |
|----------|-------------------|
| < 1K | Monolito |
| 1K - 100K | Monolito modular |
| 100K - 1M | Microservicios |
| > 1M | Microservicios + Event-Driven |

### Por Tipo de Aplicación

| Tipo | Patrón |
|------|--------|
| SaaS B2B | Multi-tenant, monolito modular |
| E-commerce | Microservicios, event-driven |
| Real-time | WebSockets, pub/sub |
| Data-intensive | CQRS, event sourcing |

---

*Workflow de Arquitectura v1.0 - Compatible con cualquier LLM*
