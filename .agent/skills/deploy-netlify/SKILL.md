---
name: deploy-netlify
description: >
type: feature
---
  Deploy applications to Netlify including static sites, serverless functions,
  edge functions, forms, and identity. Covers netlify.toml configuration, CLI
  deployment, and environment management. Use when deploying to Netlify.
source: Community
---

# Deploy to Netlify

Production deployment patterns for Netlify.

## Quick Deploy

```bash
# Install Netlify CLI
npm i -g netlify-cli

# Login
netlify login

# Initialize project
netlify init

# Dev server
netlify dev

# Deploy draft
netlify deploy

# Deploy to production
netlify deploy --prod
```

## netlify.toml

```toml
[build]
  command = "npm run build"
  publish = "dist"
  functions = "netlify/functions"

[build.environment]
  NODE_VERSION = "20"

[[redirects]]
  from = "/api/*"
  to = "/.netlify/functions/:splat"
  status = 200

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200

[[headers]]
  for = "/*"
  [headers.values]
    X-Content-Type-Options = "nosniff"
    X-Frame-Options = "DENY"
    X-XSS-Protection = "1; mode=block"

[context.production]
  environment = { NODE_ENV = "production" }

[context.deploy-preview]
  environment = { NODE_ENV = "preview" }
```

## Serverless Functions

```typescript
// netlify/functions/hello.ts
import type { Handler, HandlerEvent, HandlerContext } from "@netlify/functions";

export const handler: Handler = async (event: HandlerEvent, context: HandlerContext) => {
  return {
    statusCode: 200,
    body: JSON.stringify({ message: "Hello from Netlify Functions!" }),
    headers: {
      "Content-Type": "application/json",
    },
  };
};
```

## Edge Functions

```typescript
// netlify/edge-functions/geo.ts
import type { Context } from "@netlify/edge-functions";

export default async (request: Request, context: Context) => {
  return Response.json({
    geo: context.geo,
    ip: context.ip,
  });
};

export const config = {
  path: "/api/geo",
};
```

## Environment Variables

```bash
# Set env var
netlify env:set API_KEY "value"
netlify env:set DATABASE_URL "value" --context production

# List env vars
netlify env:list

# Import from .env
netlify env:import .env
```

## Deployment Checklist

- [ ] `netlify.toml` configured
- [ ] Environment variables set
- [ ] Build command tested locally
- [ ] Redirects and headers configured
- [ ] Functions tested with `netlify dev`
- [ ] Custom domain configured
- [ ] Deploy previews enabled
- [ ] Production deploy verified
