---
name: cloudflare-wrangler
description: >
type: feature
---
  Comprehensive Cloudflare Workers CLI reference covering Workers, KV, R2, D1,
  Vectorize, Hyperdrive, Workers AI, Queues, Containers, Workflows, Pipelines,
  Secrets Store, Pages, Observability, and Testing. Use when developing or
  deploying Cloudflare Workers, managing edge resources, or building serverless
  applications on Cloudflare.
source: Cloudflare
---

# Cloudflare Wrangler CLI

Complete reference for developing and deploying on Cloudflare's edge platform.

## Quick Start

```bash
# Create new project
npm create cloudflare@latest my-worker

# Develop locally
npx wrangler dev

# Deploy
npx wrangler deploy

# Tail logs
npx wrangler tail
```

## Core Services

### Workers
```bash
# Create Worker
npx wrangler init my-worker

# Dev with local mode (no network calls to Cloudflare)
npx wrangler dev --local

# Deploy to production
npx wrangler deploy

# Deploy to specific environment
npx wrangler deploy --env staging
```

### KV (Key-Value Store)
```bash
# Create namespace
npx wrangler kv namespace create MY_KV

# Put/Get/Delete
npx wrangler kv key put --binding MY_KV "key" "value"
npx wrangler kv key get --binding MY_KV "key"
npx wrangler kv key delete --binding MY_KV "key"

# Bulk operations
npx wrangler kv bulk put --binding MY_KV data.json
```

### R2 (Object Storage)
```bash
# Create bucket
npx wrangler r2 bucket create my-bucket

# Upload/Download
npx wrangler r2 object put my-bucket/path/file.txt --file ./local-file.txt
npx wrangler r2 object get my-bucket/path/file.txt
```

### D1 (SQLite Database)
```bash
# Create database
npx wrangler d1 create my-db

# Execute SQL
npx wrangler d1 execute my-db --command "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"
npx wrangler d1 execute my-db --file schema.sql

# List databases
npx wrangler d1 list
```

### Vectorize (Vector Database)
```bash
# Create index
npx wrangler vectorize create my-index --dimensions 768 --metric cosine

# Insert/Query vectors via Worker code
```

### Workers AI
```bash
# Run AI model
npx wrangler ai run @cf/meta/llama-3.1-8b-instruct --prompt "Hello"

# List available models
npx wrangler ai models
```

### Queues
```bash
# Create queue
npx wrangler queues create my-queue

# Create consumer
npx wrangler queues consumer add my-queue my-worker
```

### Containers (Beta)
Workers can run containers on Cloudflare's edge:
```toml
# wrangler.toml
[[containers]]
name = "my-container"
image = "docker.io/library/nginx:latest"
```

### Workflows
Durable, multi-step workflows with automatic retry:
```typescript
import { WorkflowEntrypoint } from 'cloudflare:workers';

export class MyWorkflow extends WorkflowEntrypoint {
  async run(event, step) {
    const result = await step.do('step-1', async () => {
      return await fetchData();
    });
    await step.do('step-2', async () => {
      return await processData(result);
    });
  }
}
```

## Configuration (wrangler.toml)

```toml
name = "my-worker"
main = "src/index.ts"
compatibility_date = "2024-01-01"

[vars]
MY_VAR = "hello"

[[kv_namespaces]]
binding = "MY_KV"
id = "abc123"

[[r2_buckets]]
binding = "MY_BUCKET"
bucket_name = "my-bucket"

[[d1_databases]]
binding = "MY_DB"
database_name = "my-db"
database_id = "xxx"
```

## Testing

```bash
# Run tests with Vitest
npx wrangler test

# Miniflare for local simulation
npx wrangler dev --local --persist
```

## Observability

```bash
# Real-time logs
npx wrangler tail

# With filters
npx wrangler tail --format json --status error
```

## Secrets Management

```bash
# Set secret
npx wrangler secret put MY_SECRET

# List secrets
npx wrangler secret list

# Bulk secrets
npx wrangler secret bulk secrets.json
```

## Pages (Static Sites)

```bash
# Deploy static site
npx wrangler pages deploy ./dist

# Create project
npx wrangler pages project create my-site
```
