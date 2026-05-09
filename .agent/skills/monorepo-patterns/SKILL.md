---
name: monorepo-patterns
description: "Master monorepo patterns with expert patterns and practices."
type: feature
---

# Monorepo Patterns

> Patrones para monorepos con Turborepo, Nx, pnpm workspaces y Lerna.

---

## Descripción

Esta skill cubre arquitectura y gestión de monorepos para proyectos de cualquier escala, incluyendo configuración, caching, pipelines y mejores prácticas.

---

## Comparativa de Herramientas

| Herramienta | Enfoque | Caching | Plugins | Ideal Para |
|-------------|---------|---------|---------|------------|
| **Turborepo** | Tareas | Remote | Mínimo | Simplicidad, JS/TS |
| **Nx** | Completo | Remote | Extenso | Enterprise, múltiples lenguajes |
| **pnpm** | Dependencias | Local | N/A | Workspaces puros |
| **Lerna** | Publishing | Nx-powered | Limitado | Open source libs |
| **Rush** | Enterprise | Sí | Extenso | Microsoft stack |

---

## Turborepo

### Setup Inicial

```bash
# Crear nuevo monorepo
npx create-turbo@latest

# Estructura generada
my-monorepo/
├── apps/
│   ├── web/           # Next.js app
│   └── docs/          # Documentación
├── packages/
│   ├── ui/            # Componentes compartidos
│   ├── eslint-config/ # Config ESLint compartida
│   └── typescript-config/ # Config TS compartida
├── turbo.json
├── package.json
└── pnpm-workspace.yaml
```

### turbo.json

```json
{
  "$schema": "https://turbo.build/schema.json",
  "globalDependencies": ["**/.env.*local"],
  "pipeline": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": ["dist/**", ".next/**", "!.next/cache/**"]
    },
    "lint": {
      "dependsOn": ["^lint"]
    },
    "dev": {
      "cache": false,
      "persistent": true
    },
    "test": {
      "dependsOn": ["build"],
      "outputs": ["coverage/**"]
    },
    "deploy": {
      "dependsOn": ["build", "test", "lint"]
    }
  }
}
```

### pnpm-workspace.yaml

```yaml
packages:
  - "apps/*"
  - "packages/*"
```

### package.json (Root)

```json
{
  "name": "my-monorepo",
  "private": true,
  "scripts": {
    "build": "turbo build",
    "dev": "turbo dev",
    "lint": "turbo lint",
    "test": "turbo test",
    "clean": "turbo clean && rm -rf node_modules"
  },
  "devDependencies": {
    "turbo": "^2.0.0"
  },
  "packageManager": "pnpm@8.15.0"
}
```

### Remote Caching (Vercel)

```bash
# Login para remote caching
npx turbo login

# Link al proyecto Vercel
npx turbo link

# Ahora los builds son cacheados remotamente
turbo build
# >> FULL TURBO: 5 cached, 0 total
```

### Remote Caching Self-Hosted

```typescript
// turbo.json con self-hosted cache
{
  "$schema": "https://turbo.build/schema.json",
  "remoteCache": {
    "signature": true
  }
}

// Variables de entorno
// TURBO_API=https://my-cache-server.com
// TURBO_TOKEN=my-secret-token
// TURBO_TEAM=my-team
```

---

## Nx

### Setup Inicial

```bash
# Crear workspace
npx create-nx-workspace@latest my-org

# Agregar aplicaciones
nx generate @nx/next:application web
nx generate @nx/react:application admin
nx generate @nx/node:application api

# Agregar librerías compartidas
nx generate @nx/react:library ui --directory=shared
nx generate @nx/js:library utils --directory=shared
```

### nx.json

```json
{
  "$schema": "./node_modules/nx/schemas/nx-schema.json",
  "namedInputs": {
    "default": ["{projectRoot}/**/*", "sharedGlobals"],
    "production": [
      "default",
      "!{projectRoot}/**/?(*.)+(spec|test).[jt]s?(x)?(.snap)",
      "!{projectRoot}/tsconfig.spec.json",
      "!{projectRoot}/.eslintrc.json"
    ],
    "sharedGlobals": []
  },
  "targetDefaults": {
    "build": {
      "dependsOn": ["^build"],
      "inputs": ["production", "^production"],
      "cache": true
    },
    "test": {
      "inputs": ["default", "^production"],
      "cache": true
    },
    "lint": {
      "inputs": ["default"],
      "cache": true
    }
  },
  "generators": {
    "@nx/react": {
      "application": {
        "style": "tailwind",
        "linter": "eslint",
        "bundler": "vite"
      },
      "component": {
        "style": "tailwind"
      },
      "library": {
        "style": "tailwind",
        "linter": "eslint",
        "unitTestRunner": "vitest"
      }
    }
  }
}
```

### project.json (por proyecto)

```json
{
  "name": "web",
  "$schema": "../../node_modules/nx/schemas/project-schema.json",
  "sourceRoot": "apps/web/src",
  "projectType": "application",
  "targets": {
    "build": {
      "executor": "@nx/next:build",
      "outputs": ["{options.outputPath}"],
      "options": {
        "outputPath": "dist/apps/web"
      }
    },
    "serve": {
      "executor": "@nx/next:server",
      "options": {
        "buildTarget": "web:build",
        "dev": true
      }
    },
    "test": {
      "executor": "@nx/jest:jest",
      "options": {
        "jestConfig": "apps/web/jest.config.ts"
      }
    }
  },
  "tags": ["scope:web", "type:app"]
}
```

### Affected Commands

```bash
# Solo ejecutar en proyectos afectados
nx affected:build
nx affected:test
nx affected:lint

# Grafo de dependencias
nx graph

# Ver proyectos afectados
nx show projects --affected
```

### Module Boundaries (Tags)

```json
// .eslintrc.json
{
  "rules": {
    "@nx/enforce-module-boundaries": [
      "error",
      {
        "enforceBuildableLibDependency": true,
        "allow": [],
        "depConstraints": [
          {
            "sourceTag": "scope:web",
            "onlyDependOnLibsWithTags": ["scope:shared", "scope:web"]
          },
          {
            "sourceTag": "scope:api",
            "onlyDependOnLibsWithTags": ["scope:shared", "scope:api"]
          },
          {
            "sourceTag": "type:app",
            "onlyDependOnLibsWithTags": ["type:lib", "type:util"]
          },
          {
            "sourceTag": "type:lib",
            "onlyDependOnLibsWithTags": ["type:lib", "type:util"]
          }
        ]
      }
    ]
  }
}
```

---

## Estructura de Paquetes Compartidos

### UI Library

```typescript
// packages/ui/src/index.ts
export * from './components/Button';
export * from './components/Card';
export * from './components/Modal';
export * from './components/Form';
export * from './hooks/useTheme';
```

```typescript
// packages/ui/src/components/Button/index.tsx
import { forwardRef } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        outline: 'border border-input bg-background hover:bg-accent',
        ghost: 'hover:bg-accent hover:text-accent-foreground',
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-9 px-3',
        lg: 'h-11 px-8',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        className={buttonVariants({ variant, size, className })}
        ref={ref}
        {...props}
      />
    );
  }
);
```

```json
// packages/ui/package.json
{
  "name": "@repo/ui",
  "version": "0.0.0",
  "private": true,
  "main": "./src/index.ts",
  "types": "./src/index.ts",
  "exports": {
    ".": "./src/index.ts",
    "./components/*": "./src/components/*/index.tsx",
    "./hooks/*": "./src/hooks/*.ts"
  },
  "scripts": {
    "lint": "eslint src/",
    "test": "vitest"
  },
  "peerDependencies": {
    "react": "^18.0.0"
  },
  "devDependencies": {
    "@repo/eslint-config": "workspace:*",
    "@repo/typescript-config": "workspace:*"
  }
}
```

### Shared Utils

```typescript
// packages/utils/src/index.ts
export * from './formatters';
export * from './validators';
export * from './constants';
export * from './types';
```

```typescript
// packages/utils/src/formatters.ts
export function formatCurrency(amount: number, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(amount);
}

export function formatDate(date: Date | string, locale = 'en-US'): string {
  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  }).format(new Date(date));
}

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s_-]+/g, '-')
    .replace(/^-+|-+$/g, '');
}
```

### Shared Config (TypeScript)

```json
// packages/typescript-config/base.json
{
  "$schema": "https://json.schemastore.org/tsconfig",
  "compilerOptions": {
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true
  }
}

// packages/typescript-config/nextjs.json
{
  "$schema": "https://json.schemastore.org/tsconfig",
  "extends": "./base.json",
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }]
  }
}

// packages/typescript-config/react-library.json
{
  "$schema": "https://json.schemastore.org/tsconfig",
  "extends": "./base.json",
  "compilerOptions": {
    "lib": ["ES2015", "DOM"],
    "jsx": "react-jsx",
    "declaration": true,
    "declarationMap": true
  }
}
```

---

## CI/CD Pipeline

### GitHub Actions

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  TURBO_TOKEN: ${{ secrets.TURBO_TOKEN }}
  TURBO_TEAM: ${{ vars.TURBO_TEAM }}

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 2  # Para affected

      - uses: pnpm/action-setup@v2
        with:
          version: 8

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'pnpm'

      - name: Install dependencies
        run: pnpm install --frozen-lockfile

      - name: Build
        run: pnpm turbo build

      - name: Lint
        run: pnpm turbo lint

      - name: Test
        run: pnpm turbo test

  deploy-preview:
    needs: build
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v2
        with:
          version: 8

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'pnpm'

      - run: pnpm install --frozen-lockfile

      - name: Deploy Preview
        run: pnpm turbo deploy --filter=web... -- --preview
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
```

### Changesets para Versioning

```bash
# Instalar changesets
pnpm add -D @changesets/cli
pnpm changeset init

# Crear changeset
pnpm changeset

# Publicar versiones
pnpm changeset version
pnpm changeset publish
```

```json
// .changeset/config.json
{
  "$schema": "https://unpkg.com/@changesets/config@3.0.0/schema.json",
  "changelog": "@changesets/cli/changelog",
  "commit": false,
  "fixed": [],
  "linked": [["@repo/ui", "@repo/utils"]],
  "access": "restricted",
  "baseBranch": "main",
  "updateInternalDependencies": "patch",
  "ignore": ["@repo/web", "@repo/docs"]
}
```

---

## Docker Multi-Stage para Monorepos

```dockerfile
# Dockerfile
FROM node:20-alpine AS base
RUN corepack enable pnpm

FROM base AS builder
WORKDIR /app

# Copiar archivos de configuración
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY turbo.json ./

# Copiar package.json de todos los workspaces
COPY apps/web/package.json ./apps/web/
COPY packages/ui/package.json ./packages/ui/
COPY packages/utils/package.json ./packages/utils/

# Instalar dependencias
RUN pnpm install --frozen-lockfile

# Copiar código fuente
COPY . .

# Build solo la app web y sus dependencias
RUN pnpm turbo build --filter=web...

FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production

# Copiar solo lo necesario
COPY --from=builder /app/apps/web/.next/standalone ./
COPY --from=builder /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder /app/apps/web/public ./apps/web/public

EXPOSE 3000
CMD ["node", "apps/web/server.js"]
```

---

## Best Practices

### Organización de Código

```
my-monorepo/
├── apps/                    # Aplicaciones desplegables
│   ├── web/                 # App principal
│   ├── admin/               # Panel admin
│   ├── api/                 # Backend API
│   └── mobile/              # React Native (si aplica)
├── packages/                # Código compartido
│   ├── ui/                  # Componentes UI
│   ├── utils/               # Utilidades
│   ├── config/              # Configuraciones
│   ├── types/               # TypeScript types
│   └── database/            # Prisma/Drizzle schema
├── tooling/                 # Configuración de herramientas
│   ├── eslint/              # ESLint configs
│   ├── typescript/          # TS configs
│   └── tailwind/            # Tailwind config
├── docs/                    # Documentación
└── scripts/                 # Scripts de utilidad
```

### Convenciones de Nombrado

```json
// Nombrado de paquetes
{
  "name": "@myorg/ui",           // Prefijo de organización
  "name": "@myorg/utils",
  "name": "@myorg/web",          // Apps también con prefijo
  "name": "@myorg/eslint-config" // Configs con sufijo descriptivo
}
```

### Internal Dependencies

```json
// apps/web/package.json
{
  "dependencies": {
    "@myorg/ui": "workspace:*",      // Siempre última versión
    "@myorg/utils": "workspace:^1.0.0" // Con rango
  }
}
```

---

## Referencias

- [Turborepo Docs](https://turbo.build/repo/docs)
- [Nx Documentation](https://nx.dev/getting-started/intro)
- [pnpm Workspaces](https://pnpm.io/workspaces)
- [Changesets](https://github.com/changesets/changesets)
- [Monorepo Tools](https://monorepo.tools/)

---

*Skill creada: 2026-02-01*
*Versión: 1.0.0*
