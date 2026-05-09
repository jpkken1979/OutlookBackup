---
name: deploy-cloudflare
description: >
type: feature
---
  Deploy applications to Cloudflare Workers and Pages. Covers Wrangler CLI,
  Workers configuration, Pages deployment, D1 databases, KV storage, R2 buckets,
  and Durable Objects. Use when deploying to Cloudflare platform.
source: Community
---

# Deploy to Cloudflare

Production deployment patterns for Cloudflare Workers and Pages.

## Workers Deployment

### wrangler.toml

```toml
name = "my-worker"
main = "src/index.ts"
compatibility_date = "2024-01-01"
compatibility_flags = ["nodejs_compat"]

[vars]
ENVIRONMENT = "production"

[[kv_namespaces]]
binding = "MY_KV"
id = "abc123"

[[d1_databases]]
binding = "DB"
database_name = "my-database"
database_id = "def456"

[[r2_buckets]]
binding = "BUCKET"
bucket_name = "my-bucket"
```

### Deploy
```bash
# Install Wrangler
npm install -g wrangler

# Login
wrangler login

# Dev server
wrangler dev

# Deploy
wrangler deploy

# Deploy to specific environment
wrangler deploy --env production
```

## Pages Deployment

```bash
# Deploy static site
wrangler pages deploy ./dist

# Or with Git integration (automatic)
# Connect repo in Cloudflare Dashboard → Pages → Create project
```

### pages.toml
```toml
[build]
command = "npm run build"
directory = "dist"

[env.production]
NODE_VERSION = "20"

[env.preview]
NODE_VERSION = "20"
```

## Worker Script

```typescript
// src/index.ts
export interface Env {
  MY_KV: KVNamespace;
  DB: D1Database;
  BUCKET: R2Bucket;
  API_KEY: string;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === '/api/data') {
      const data = await env.MY_KV.get('key');
      return Response.json({ data });
    }

    return new Response('Not Found', { status: 404 });
  },
} satisfies ExportedHandler<Env>;
```

## Secrets Management

```bash
# Add secret
wrangler secret put API_KEY
# (Prompts for value — never in command)

# List secrets
wrangler secret list

# Delete secret
wrangler secret delete API_KEY
```

## D1 Database

```bash
# Create database
wrangler d1 create my-database

# Run SQL
wrangler d1 execute my-database --command "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"

# Run migration file
wrangler d1 execute my-database --file schema.sql

# Query remotely
wrangler d1 execute my-database --command "SELECT * FROM users" --remote
```

## KV Storage

```bash
# Create namespace
wrangler kv namespace create MY_KV

# Put/Get values
wrangler kv key put --namespace-id abc123 "key" "value"
wrangler kv key get --namespace-id abc123 "key"
```

## Custom Domains

```bash
# Add custom domain
wrangler domains add my-worker example.com

# Or via route in wrangler.toml
# [[routes]]
# pattern = "api.example.com/*"
# zone_name = "example.com"
```

## Deployment Checklist

- [ ] `wrangler.toml` configured
- [ ] Secrets set via `wrangler secret put`
- [ ] Bindings (KV, D1, R2) configured
- [ ] Custom domain set up
- [ ] Dev tested with `wrangler dev`
- [ ] Production deployed with `wrangler deploy`
