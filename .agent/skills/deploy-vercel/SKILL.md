---
name: deploy-vercel
description: >
type: feature
---
  Deploy applications to Vercel with optimized configuration. Covers Next.js,
  static sites, serverless functions, environment variables, preview deployments,
  and edge functions. Use when deploying to Vercel platform.
source: Community
---

# Deploy to Vercel

Production deployment patterns for Vercel platform.

## Quick Deploy

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy (interactive setup on first run)
vercel

# Deploy to production
vercel --prod

# Deploy with specific settings
vercel --prod --env DATABASE_URL=@database-url
```

## vercel.json Configuration

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "outputDirectory": ".next",
  "regions": ["iad1"],
  "headers": [
    {
      "source": "/api/(.*)",
      "headers": [
        { "key": "Cache-Control", "value": "no-store" }
      ]
    },
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-XSS-Protection", "value": "1; mode=block" }
      ]
    }
  ],
  "rewrites": [
    { "source": "/api/:path*", "destination": "/api/:path*" }
  ],
  "redirects": [
    { "source": "/old-page", "destination": "/new-page", "permanent": true }
  ]
}
```

## Environment Variables

```bash
# Add env var
vercel env add DATABASE_URL production
vercel env add API_KEY preview development

# List env vars
vercel env ls

# Pull env vars to local .env
vercel env pull .env.local
```

## Serverless Functions

```typescript
// api/hello.ts
import type { VercelRequest, VercelResponse } from '@vercel/node';

export default function handler(req: VercelRequest, res: VercelResponse) {
  res.status(200).json({ message: 'Hello from Vercel!' });
}
```

## Edge Functions

```typescript
// app/api/edge/route.ts
export const runtime = 'edge';

export async function GET(request: Request) {
  return new Response(JSON.stringify({ region: process.env.VERCEL_REGION }), {
    headers: { 'content-type': 'application/json' },
  });
}
```

## Preview Deployments

```bash
# Every git push to a non-production branch creates a preview
git push origin feature/my-change
# → Vercel auto-deploys to unique preview URL

# Comment on PR with preview URL (automatic with GitHub integration)
```

## Deployment Checklist

- [ ] `vercel.json` configured
- [ ] Environment variables set for all environments
- [ ] Build command tested locally
- [ ] Security headers configured
- [ ] Error pages customized (404, 500)
- [ ] Domain configured and DNS verified
- [ ] Preview deployments working
- [ ] Production deployment tested
