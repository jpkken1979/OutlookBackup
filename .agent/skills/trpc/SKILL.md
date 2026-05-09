---
name: trpc
type: feature
description: "Implementa APIs type-safe con tRPC. End-to-end type safety entre cliente y servidor sin generación de código. Soporta Next.js App Router, middleware, context, subscriptions con WebSocket, error handling tipado, y Zod para validación. Triggers: tRPC, type-safe API, end-to-end types, Next.js, React Query, TypeScript API."
---

# tRPC

## Metadata
- **Name**: tRPC
- **Category**: Backend/API
- **Version**: 1.0.0
- **Author**: Antigravity Team

## Description
Skill para implementar APIs type-safe con tRPC. Permite end-to-end type safety entre cliente y servidor sin código de generación.

## Capabilities
- Generación de routers tRPC
- Configuración de procedures (query/mutation)
- Integración con Next.js App Router
- Middleware y context
- Subscriptions con WebSocket
- Error handling tipado
- Integración con Zod para validación

## Key Features
- **Zero codegen**: Types inferidos automáticamente
- **Full TypeScript**: Autocompletado en cliente y servidor
- **Framework agnostic**: Funciona con Next.js, Express, Fastify
- **Subscriptions**: Soporte para tiempo real

## Usage
```bash
# Generar router básico
python scripts/trpc.py router --name users

# Generar procedure
python scripts/trpc.py procedure --router users --name getById --type query

# Generar setup completo Next.js
python scripts/trpc.py setup --framework nextjs

# Listar patterns
python scripts/trpc.py patterns
```

## Inputs
- `router_name`: Nombre del router
- `procedure_name`: Nombre del procedure
- `procedure_type`: query | mutation | subscription
- `input_schema`: Schema Zod de entrada
- `framework`: nextjs | express | fastify

## Outputs
- Router files (TypeScript)
- Client configuration
- Context setup
- Middleware examples

## Dependencies
- @trpc/server
- @trpc/client
- @trpc/react-query
- zod
- @tanstack/react-query

## Related Skills
- `api-patterns`
- `typescript-patterns`
- `nextjs-app-router-patterns`
