---
name: project-structure-best-practices
description: Skill description for project-structure-best-practices
type: feature
---

# Project Structure Best Practices

> Estructuras de carpetas estándar para proyectos Frontend y Backend profesionales.

---

## Descripción

Esta skill define las estructuras de carpetas óptimas para proyectos modernos, siguiendo las mejores prácticas de la industria. Garantiza consistencia, escalabilidad y mantenibilidad.

---

## Estructura Frontend (React/Next.js/Vite)

```
my-app-frontend/
├── package.json              # Dependencias y scripts
├── package-lock.json         # Lock file
├── README.md                 # Documentación del proyecto
├── .gitignore                # Archivos ignorados por git
├── .env.example              # Template de variables de entorno
├── tsconfig.json             # Configuración TypeScript
├── vite.config.ts            # Configuración Vite (o next.config.js)
├── eslint.config.js          # Configuración ESLint
├── vercel.json               # Configuración deploy (opcional)
│
├── public/                   # Archivos estáticos públicos
│   ├── index.html            # HTML principal
│   ├── favicon.ico           # Favicon
│   └── robots.txt            # SEO
│
├── node_modules/             # Dependencias (gitignore)
│
└── src/                      # Código fuente
    ├── index.tsx             # Punto de entrada
    ├── App.tsx               # Componente raíz
    ├── styles.css            # Estilos globales (o globals.css)
    │
    ├── assets/               # Recursos estáticos
    │   ├── images/           # Imágenes
    │   ├── fonts/            # Fuentes
    │   └── icons/            # Iconos SVG
    │
    ├── components/           # Componentes reutilizables
    │   ├── ui/               # Componentes UI básicos
    │   │   ├── Button.tsx
    │   │   ├── Input.tsx
    │   │   ├── Modal.tsx
    │   │   └── index.ts      # Barrel export
    │   ├── layout/           # Componentes de layout
    │   │   ├── Header.tsx
    │   │   ├── Footer.tsx
    │   │   ├── Sidebar.tsx
    │   │   └── index.ts
    │   └── common/           # Componentes compartidos
    │       ├── Loading.tsx
    │       ├── ErrorBoundary.tsx
    │       └── index.ts
    │
    ├── pages/                # Vistas/Páginas (o app/ en Next.js 13+)
    │   ├── Home/
    │   │   ├── Home.tsx
    │   │   ├── Home.test.tsx
    │   │   └── index.ts
    │   ├── Auth/
    │   │   ├── Login.tsx
    │   │   ├── Register.tsx
    │   │   └── index.ts
    │   ├── Dashboard/
    │   │   └── Dashboard.tsx
    │   ├── Admin/
    │   │   └── Admin.tsx
    │   └── Shop/
    │       ├── ProductList.tsx
    │       ├── ProductDetail.tsx
    │       └── Cart.tsx
    │
    ├── hooks/                # Custom hooks
    │   ├── useAuth.ts        # Autenticación
    │   ├── useFetch.ts       # Fetch genérico
    │   ├── useLocalStorage.ts
    │   ├── useDebounce.ts
    │   └── index.ts
    │
    ├── services/             # Servicios/API calls
    │   ├── api.ts            # Cliente API base (axios/fetch)
    │   ├── authService.ts    # Servicios de autenticación
    │   ├── userService.ts    # Servicios de usuario
    │   ├── productService.ts # Servicios de productos
    │   └── index.ts
    │
    ├── store/                # Estado global (Redux/Zustand)
    │   ├── store.ts          # Configuración del store
    │   ├── slices/           # Redux slices
    │   │   ├── authSlice.ts
    │   │   ├── userSlice.ts
    │   │   └── cartSlice.ts
    │   └── index.ts
    │
    ├── utils/                # Utilidades
    │   ├── formatDate.ts     # Formateo de fechas
    │   ├── formatCurrency.ts # Formateo de moneda
    │   ├── validators.ts     # Validaciones
    │   ├── constants.ts      # Constantes
    │   └── index.ts
    │
    ├── types/                # Tipos TypeScript
    │   ├── user.types.ts
    │   ├── product.types.ts
    │   ├── api.types.ts
    │   └── index.ts
    │
    ├── data/                 # Datos estáticos/mocks
    │   ├── mockUsers.ts
    │   └── navigation.ts
    │
    └── config/               # Configuración
        ├── routes.ts         # Rutas de la app
        ├── env.ts            # Variables de entorno tipadas
        └── theme.ts          # Configuración de tema
```

---

## Estructura Backend (Node.js/Express/NestJS)

```
my-app-backend/
├── package.json              # Dependencias y scripts
├── package-lock.json         # Lock file
├── README.md                 # Documentación
├── .gitignore                # Archivos ignorados
├── .env                      # Variables de entorno (gitignore)
├── .env.example              # Template de variables
├── tsconfig.json             # Configuración TypeScript
├── vercel.json               # Deploy config (opcional)
├── Dockerfile                # Containerización
├── docker-compose.yml        # Compose para desarrollo
│
├── node_modules/             # Dependencias (gitignore)
│
├── server.ts                 # Punto de entrada (o app.ts)
│
└── src/
    ├── index.ts              # Bootstrap de la aplicación
    │
    ├── config/               # Configuración
    │   ├── db.ts             # Conexión a base de datos
    │   ├── default.ts        # Configuración por defecto
    │   ├── env.ts            # Variables de entorno tipadas
    │   └── index.ts
    │
    ├── models/               # Modelos/Entidades (ORM)
    │   ├── User.ts           # Modelo de usuario
    │   ├── Product.ts        # Modelo de producto
    │   ├── Order.ts          # Modelo de orden
    │   └── index.ts
    │
    ├── routes/               # Definición de rutas
    │   ├── index.ts          # Router principal
    │   ├── userRoutes.ts     # Rutas de usuario
    │   ├── productRoutes.ts  # Rutas de productos
    │   ├── authRoutes.ts     # Rutas de autenticación
    │   └── orderRoutes.ts    # Rutas de órdenes
    │
    ├── controllers/          # Controladores (lógica de request/response)
    │   ├── userController.ts
    │   ├── productController.ts
    │   ├── authController.ts
    │   └── orderController.ts
    │
    ├── services/             # Lógica de negocio
    │   ├── userService.ts
    │   ├── productService.ts
    │   ├── authService.ts
    │   ├── emailService.ts
    │   └── paymentService.ts
    │
    ├── middlewares/          # Middlewares
    │   ├── auth.ts           # Autenticación JWT
    │   ├── logger.ts         # Logging de requests
    │   ├── errorHandler.ts   # Manejo de errores
    │   ├── rateLimiter.ts    # Rate limiting
    │   └── validator.ts      # Validación de requests
    │
    ├── validators/           # Esquemas de validación
    │   ├── userValidator.ts  # Validación de usuario
    │   ├── productValidator.ts
    │   └── authValidator.ts
    │
    ├── utils/                # Utilidades
    │   ├── emailSender.ts    # Envío de emails
    │   ├── tokenUtils.ts     # Manejo de JWT
    │   ├── hashUtils.ts      # Hashing de passwords
    │   ├── responseUtils.ts  # Respuestas estandarizadas
    │   └── index.ts
    │
    ├── helpers/              # Helpers (funciones auxiliares)
    │   ├── dateHelper.ts
    │   ├── stringHelper.ts
    │   └── index.ts
    │
    ├── types/                # Tipos TypeScript
    │   ├── express.d.ts      # Extensiones de Express
    │   ├── user.types.ts
    │   ├── api.types.ts
    │   └── index.ts
    │
    ├── constants/            # Constantes
    │   ├── httpStatus.ts
    │   ├── errorMessages.ts
    │   └── index.ts
    │
    └── __tests__/            # Tests
        ├── unit/
        │   ├── services/
        │   └── utils/
        ├── integration/
        │   └── routes/
        └── fixtures/
            └── mockData.ts
```

---

## Estructura Full-Stack (Monorepo)

```
my-app/
├── package.json              # Workspace root
├── pnpm-workspace.yaml       # Workspace config (o lerna.json)
├── turbo.json                # Turborepo config
├── README.md
├── .gitignore
│
├── apps/
│   ├── web/                  # Frontend (estructura arriba)
│   ├── api/                  # Backend (estructura arriba)
│   └── admin/                # Panel de administración
│
├── packages/
│   ├── ui/                   # Componentes compartidos
│   ├── config/               # Configuración compartida
│   ├── types/                # Tipos compartidos
│   └── utils/                # Utilidades compartidas
│
└── tools/
    ├── scripts/              # Scripts de build/deploy
    └── docker/               # Configuración Docker
```

---

## Reglas de Organización

### 1. Nomenclatura de Archivos

| Tipo | Convención | Ejemplo |
|------|------------|---------|
| Componentes React | PascalCase | `UserProfile.tsx` |
| Hooks | camelCase con 'use' | `useAuth.ts` |
| Servicios | camelCase con 'Service' | `userService.ts` |
| Utilidades | camelCase | `formatDate.ts` |
| Tipos | camelCase con '.types' | `user.types.ts` |
| Tests | mismo nombre con '.test' | `UserProfile.test.tsx` |
| Estilos | mismo nombre con '.module' | `UserProfile.module.css` |

### 2. Barrel Exports (index.ts)

Cada carpeta debe tener un `index.ts` para exportaciones limpias:

```typescript
// components/ui/index.ts
export { Button } from './Button';
export { Input } from './Input';
export { Modal } from './Modal';

// Uso:
import { Button, Input, Modal } from '@/components/ui';
```

### 3. Imports Absolutos

Configurar path aliases en `tsconfig.json`:

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"],
      "@components/*": ["src/components/*"],
      "@hooks/*": ["src/hooks/*"],
      "@services/*": ["src/services/*"],
      "@utils/*": ["src/utils/*"]
    }
  }
}
```

### 4. Separación de Responsabilidades

| Capa | Responsabilidad | NO debe contener |
|------|-----------------|------------------|
| **Controllers** | Request/Response | Lógica de negocio |
| **Services** | Lógica de negocio | Acceso directo a DB |
| **Models** | Esquema de datos | Lógica de negocio |
| **Utils** | Funciones puras | Estado, side effects |
| **Middlewares** | Cross-cutting concerns | Lógica de negocio |

### 5. Organización por Feature (Alternativa)

Para proyectos grandes, organizar por feature:

```
src/
├── features/
│   ├── auth/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── types/
│   │   └── index.ts
│   ├── products/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── services/
│   │   └── index.ts
│   └── orders/
│       └── ...
└── shared/
    ├── components/
    ├── hooks/
    └── utils/
```

---

## Archivos de Configuración Obligatorios

### Frontend

| Archivo | Propósito |
|---------|-----------|
| `.env.example` | Template de variables de entorno |
| `tsconfig.json` | Configuración TypeScript |
| `.eslintrc.js` | Reglas de linting |
| `.prettierrc` | Formateo de código |
| `vite.config.ts` | Configuración de build |

### Backend

| Archivo | Propósito |
|---------|-----------|
| `.env.example` | Template de variables de entorno |
| `tsconfig.json` | Configuración TypeScript |
| `.eslintrc.js` | Reglas de linting |
| `Dockerfile` | Containerización |
| `docker-compose.yml` | Orquestación local |

---

## Anti-Patterns a Evitar

### NO Hacer:

```
❌ src/
   ├── Button.tsx
   ├── Header.tsx
   ├── api.ts
   ├── formatDate.ts
   └── User.ts          # Todo mezclado en raíz
```

```
❌ components/
   └── UserProfileCardWithAvatarAndActions.tsx  # Nombres muy largos
```

```
❌ utils/
   ├── utils.ts         # Archivo genérico
   └── helpers.ts       # Sin especificidad
```

### SÍ Hacer:

```
✅ src/
   ├── components/
   │   └── ui/
   │       └── Button.tsx
   ├── services/
   │   └── api.ts
   └── utils/
       └── formatDate.ts
```

---

## Validación de Estructura

Usar el script `validate_structure.py` para verificar que un proyecto sigue estas convenciones.

```bash
python .agent/skills/project-structure-best-practices/scripts/validate_structure.py /path/to/project
```

---

## Referencias

- [Bulletproof React](https://github.com/alan2207/bulletproof-react)
- [Next.js Project Structure](https://nextjs.org/docs/app/building-your-application)
- [NestJS Architecture](https://docs.nestjs.com/fundamentals/custom-providers)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)

---

*Skill creada: 2026-02-01*
*Versión: 1.0.0*
