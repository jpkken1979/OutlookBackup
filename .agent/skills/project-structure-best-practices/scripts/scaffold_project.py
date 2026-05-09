#!/usr/bin/env python3
"""
Project Scaffolder
Genera estructuras de proyecto siguiendo mejores prácticas.
"""

import sys
import json
import logging
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class ProjectType(Enum):
    FRONTEND_REACT = "frontend-react"
    FRONTEND_NEXT = "frontend-next"
    BACKEND_EXPRESS = "backend-express"
    BACKEND_FASTAPI = "backend-fastapi"
    FULLSTACK = "fullstack"


@dataclass
class ProjectConfig:
    """Configuración del proyecto a generar."""

    name: str
    project_type: ProjectType
    typescript: bool = True
    with_docker: bool = True
    with_tests: bool = True


class ProjectScaffolder:
    """Generador de estructuras de proyecto."""

    def __init__(self, config: ProjectConfig, base_path: str = "."):
        self.config = config
        self.base_path = Path(base_path)
        self.project_path = self.base_path / config.name

    def create_directory(self, path: str) -> None:
        """Crea un directorio."""
        full_path = self.project_path / path
        full_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"📁 Creado: {path}/")

    def create_file(self, path: str, content: str = "") -> None:
        """Crea un archivo con contenido."""
        full_path = self.project_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        logger.info(f"📄 Creado: {path}")

    def scaffold_frontend_react(self) -> None:
        """Genera estructura frontend React/Vite."""
        ext = "tsx" if self.config.typescript else "jsx"

        # Directorios
        directories = [
            "public",
            "src/assets/images",
            "src/assets/fonts",
            "src/components/ui",
            "src/components/layout",
            "src/components/common",
            "src/pages/Home",
            "src/pages/Auth",
            "src/hooks",
            "src/services",
            "src/store/slices",
            "src/utils",
            "src/types",
            "src/config",
        ]

        if self.config.with_tests:
            directories.append("src/__tests__")

        for dir_path in directories:
            self.create_directory(dir_path)

        # Archivos de configuración
        self.create_file(".gitignore", self._gitignore_frontend())
        self.create_file(".env.example", self._env_example_frontend())
        self.create_file("package.json", self._package_json_frontend())
        self.create_file("README.md", self._readme_frontend())

        if self.config.typescript:
            self.create_file("tsconfig.json", self._tsconfig_frontend())

        self.create_file("vite.config.ts", self._vite_config())

        # Archivos de código
        self.create_file(f"src/App.{ext}", self._app_component())
        self.create_file(f"src/main.{ext}", self._main_entry())
        self.create_file("src/index.css", self._base_css())

        # Componentes base
        self.create_file(f"src/components/ui/Button.{ext}", self._button_component())
        self.create_file("src/components/ui/index.ts", "export { Button } from './Button';\n")

        # Hooks base
        self.create_file("src/hooks/useAuth.ts", self._use_auth_hook())
        self.create_file("src/hooks/index.ts", "export { useAuth } from './useAuth';\n")

        # Services
        self.create_file("src/services/api.ts", self._api_service())
        self.create_file("src/services/index.ts", "export { api } from './api';\n")

        # Utils
        self.create_file("src/utils/formatDate.ts", self._format_date_util())
        self.create_file("src/utils/index.ts", "export { formatDate } from './formatDate';\n")

        # Types
        self.create_file("src/types/user.types.ts", self._user_types())
        self.create_file("src/types/index.ts", "export * from './user.types';\n")

        # Config
        self.create_file("src/config/routes.ts", self._routes_config())
        self.create_file("src/config/index.ts", "export { routes } from './routes';\n")

    def scaffold_backend_express(self) -> None:
        """Genera estructura backend Express."""
        # Directorios
        directories = [
            "src/config",
            "src/models",
            "src/routes",
            "src/controllers",
            "src/services",
            "src/middlewares",
            "src/validators",
            "src/utils",
            "src/types",
            "src/constants",
        ]

        if self.config.with_tests:
            directories.extend(
                [
                    "src/__tests__/unit",
                    "src/__tests__/integration",
                    "src/__tests__/fixtures",
                ]
            )

        for dir_path in directories:
            self.create_directory(dir_path)

        # Archivos de configuración
        self.create_file(".gitignore", self._gitignore_backend())
        self.create_file(".env.example", self._env_example_backend())
        self.create_file("package.json", self._package_json_backend())
        self.create_file("README.md", self._readme_backend())

        if self.config.typescript:
            self.create_file("tsconfig.json", self._tsconfig_backend())

        if self.config.with_docker:
            self.create_file("Dockerfile", self._dockerfile())
            self.create_file("docker-compose.yml", self._docker_compose())

        # Archivos de código
        self.create_file("src/index.ts", self._backend_entry())
        self.create_file("src/app.ts", self._express_app())

        # Config
        self.create_file("src/config/db.ts", self._db_config())
        self.create_file("src/config/env.ts", self._env_config())
        self.create_file("src/config/index.ts", "export * from './db';\nexport * from './env';\n")

        # Models
        self.create_file("src/models/User.ts", self._user_model())
        self.create_file("src/models/index.ts", "export { User } from './User';\n")

        # Routes
        self.create_file("src/routes/index.ts", self._routes_index())
        self.create_file("src/routes/userRoutes.ts", self._user_routes())
        self.create_file("src/routes/authRoutes.ts", self._auth_routes())

        # Controllers
        self.create_file("src/controllers/userController.ts", self._user_controller())
        self.create_file("src/controllers/index.ts", "export * from './userController';\n")

        # Services
        self.create_file("src/services/userService.ts", self._user_service())
        self.create_file("src/services/index.ts", "export * from './userService';\n")

        # Middlewares
        self.create_file("src/middlewares/auth.ts", self._auth_middleware())
        self.create_file("src/middlewares/errorHandler.ts", self._error_handler())
        self.create_file("src/middlewares/logger.ts", self._logger_middleware())
        self.create_file(
            "src/middlewares/index.ts",
            "export { authMiddleware } from './auth';\n"
            "export { errorHandler } from './errorHandler';\n"
            "export { loggerMiddleware } from './logger';\n",
        )

        # Utils
        self.create_file("src/utils/responseUtils.ts", self._response_utils())
        self.create_file("src/utils/index.ts", "export * from './responseUtils';\n")

    def scaffold(self) -> None:
        """Genera la estructura del proyecto."""
        logger.info(f"Creando proyecto: {self.config.name}")
        logger.info(f"Tipo: {self.config.project_type.value}")

        self.project_path.mkdir(parents=True, exist_ok=True)

        if self.config.project_type in [ProjectType.FRONTEND_REACT, ProjectType.FRONTEND_NEXT]:
            self.scaffold_frontend_react()
        elif self.config.project_type in [ProjectType.BACKEND_EXPRESS, ProjectType.BACKEND_FASTAPI]:
            self.scaffold_backend_express()
        elif self.config.project_type == ProjectType.FULLSTACK:
            # Crear subdirectorios
            frontend_config = ProjectConfig(
                name="frontend",
                project_type=ProjectType.FRONTEND_REACT,
                typescript=self.config.typescript,
            )
            backend_config = ProjectConfig(
                name="backend",
                project_type=ProjectType.BACKEND_EXPRESS,
                typescript=self.config.typescript,
                with_docker=self.config.with_docker,
            )

            ProjectScaffolder(frontend_config, str(self.project_path)).scaffold()
            ProjectScaffolder(backend_config, str(self.project_path)).scaffold()

            # Root files
            self.create_file("package.json", self._package_json_monorepo())
            self.create_file("README.md", self._readme_fullstack())
            self.create_file(".gitignore", self._gitignore_fullstack())

        logger.info(f"\n✅ Proyecto '{self.config.name}' creado exitosamente!")
        logger.info(f"📁 Ubicación: {self.project_path.absolute()}")

    # =========================================================================
    # TEMPLATES
    # =========================================================================

    def _gitignore_frontend(self) -> str:
        return """# Dependencies
node_modules/
.pnp/
.pnp.js

# Build
dist/
build/

# Environment
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
*.log
npm-debug.log*

# Testing
coverage/
"""

    def _gitignore_backend(self) -> str:
        return (
            self._gitignore_frontend()
            + """
# Uploads
uploads/

# Database
*.sqlite
*.db
"""
        )

    def _gitignore_fullstack(self) -> str:
        return self._gitignore_frontend()

    def _env_example_frontend(self) -> str:
        return """# API
VITE_API_URL=http://localhost:3000/api

# Auth
VITE_AUTH_DOMAIN=
VITE_AUTH_CLIENT_ID=
"""

    def _env_example_backend(self) -> str:
        return """# Server
PORT=3000
NODE_ENV=development

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/mydb

# JWT
JWT_SECRET=your-secret-key
JWT_EXPIRES_IN=7d

# Email (optional)
SMTP_HOST=
SMTP_PORT=
SMTP_USER=
SMTP_PASS=
"""

    def _package_json_frontend(self) -> str:
        return json.dumps(
            {
                "name": self.config.name,
                "version": "1.0.0",
                "type": "module",
                "scripts": {
                    "dev": "vite",
                    "build": "tsc && vite build",
                    "preview": "vite preview",
                    "lint": "eslint . --ext ts,tsx",
                    "test": "vitest",
                },
                "dependencies": {
                    "react": "^18.2.0",
                    "react-dom": "^18.2.0",
                    "react-router-dom": "^6.20.0",
                    "axios": "^1.6.0",
                },
                "devDependencies": {
                    "@types/react": "^18.2.0",
                    "@types/react-dom": "^18.2.0",
                    "@vitejs/plugin-react": "^4.2.0",
                    "typescript": "^5.3.0",
                    "vite": "^5.0.0",
                    "vitest": "^1.0.0",
                },
            },
            indent=2,
        )

    def _package_json_backend(self) -> str:
        return json.dumps(
            {
                "name": self.config.name,
                "version": "1.0.0",
                "main": "dist/index.js",
                "scripts": {
                    "dev": "ts-node-dev --respawn src/index.ts",
                    "build": "tsc",
                    "start": "node dist/index.js",
                    "lint": "eslint . --ext .ts",
                    "test": "jest",
                },
                "dependencies": {
                    "express": "^4.18.0",
                    "cors": "^2.8.5",
                    "helmet": "^7.1.0",
                    "dotenv": "^16.3.0",
                    "jsonwebtoken": "^9.0.0",
                    "bcryptjs": "^2.4.3",
                },
                "devDependencies": {
                    "@types/express": "^4.17.0",
                    "@types/cors": "^2.8.0",
                    "@types/jsonwebtoken": "^9.0.0",
                    "@types/bcryptjs": "^2.4.0",
                    "typescript": "^5.3.0",
                    "ts-node-dev": "^2.0.0",
                    "jest": "^29.7.0",
                    "@types/jest": "^29.5.0",
                },
            },
            indent=2,
        )

    def _package_json_monorepo(self) -> str:
        return json.dumps(
            {
                "name": self.config.name,
                "private": True,
                "workspaces": ["frontend", "backend"],
                "scripts": {
                    "dev": 'concurrently "npm run dev:frontend" "npm run dev:backend"',
                    "dev:frontend": "npm -C frontend run dev",
                    "dev:backend": "npm -C backend run dev",
                    "build": "npm -C frontend run build && npm -C backend run build",
                },
                "devDependencies": {"concurrently": "^8.2.0"},
            },
            indent=2,
        )

    def _tsconfig_frontend(self) -> str:
        return json.dumps(
            {
                "compilerOptions": {
                    "target": "ES2020",
                    "useDefineForClassFields": True,
                    "lib": ["ES2020", "DOM", "DOM.Iterable"],
                    "module": "ESNext",
                    "skipLibCheck": True,
                    "moduleResolution": "bundler",
                    "allowImportingTsExtensions": True,
                    "resolveJsonModule": True,
                    "isolatedModules": True,
                    "noEmit": True,
                    "jsx": "react-jsx",
                    "strict": True,
                    "noUnusedLocals": True,
                    "noUnusedParameters": True,
                    "noFallthroughCasesInSwitch": True,
                    "baseUrl": ".",
                    "paths": {
                        "@/*": ["src/*"],
                        "@components/*": ["src/components/*"],
                        "@hooks/*": ["src/hooks/*"],
                        "@services/*": ["src/services/*"],
                        "@utils/*": ["src/utils/*"],
                    },
                },
                "include": ["src"],
                "references": [{"path": "./tsconfig.node.json"}],
            },
            indent=2,
        )

    def _tsconfig_backend(self) -> str:
        return json.dumps(
            {
                "compilerOptions": {
                    "target": "ES2020",
                    "module": "commonjs",
                    "lib": ["ES2020"],
                    "outDir": "./dist",
                    "rootDir": "./src",
                    "strict": True,
                    "esModuleInterop": True,
                    "skipLibCheck": True,
                    "forceConsistentCasingInFileNames": True,
                    "resolveJsonModule": True,
                    "declaration": True,
                    "declarationMap": True,
                    "sourceMap": True,
                    "baseUrl": ".",
                    "paths": {"@/*": ["src/*"]},
                },
                "include": ["src/**/*"],
                "exclude": ["node_modules", "dist"],
            },
            indent=2,
        )

    def _vite_config(self) -> str:
        return """import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@services': path.resolve(__dirname, './src/services'),
      '@utils': path.resolve(__dirname, './src/utils'),
    },
  },
});
"""

    def _app_component(self) -> str:
        return """import { BrowserRouter, Routes, Route } from 'react-router-dom';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<div>Home</div>} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
"""

    def _main_entry(self) -> str:
        return """import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
"""

    def _base_css(self) -> str:
        return """* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen,
    Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
  line-height: 1.5;
}
"""

    def _button_component(self) -> str:
        return """import { ButtonHTMLAttributes, ReactNode } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger';
  children: ReactNode;
}

export function Button({ variant = 'primary', children, ...props }: ButtonProps) {
  return (
    <button className={`btn btn-${variant}`} {...props}>
      {children}
    </button>
  );
}
"""

    def _use_auth_hook(self) -> str:
        return """import { useState, useCallback } from 'react';

interface User {
  id: string;
  email: string;
  name: string;
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(false);

  const login = useCallback(async (email: string, password: string) => {
    setLoading(true);
    try {
      // Implementar: lógica de login
      console.log('Login:', email);
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
  }, []);

  return { user, loading, login, logout };
}
"""

    def _api_service(self) -> str:
        return """import axios from 'axios';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:3000/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
"""

    def _format_date_util(self) -> str:
        return """export function formatDate(date: Date | string, locale = 'es-ES'): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleDateString(locale, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

export function formatDateTime(date: Date | string, locale = 'es-ES'): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleString(locale);
}

export function formatRelativeTime(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) return `hace ${days} día${days > 1 ? 's' : ''}`;
  if (hours > 0) return `hace ${hours} hora${hours > 1 ? 's' : ''}`;
  if (minutes > 0) return `hace ${minutes} minuto${minutes > 1 ? 's' : ''}`;
  return 'ahora mismo';
}
"""

    def _user_types(self) -> str:
        return """export interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  createdAt: string;
  updatedAt: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
}

export interface AuthResponse {
  user: User;
  token: string;
}
"""

    def _routes_config(self) -> str:
        return """export const routes = {
  home: '/',
  login: '/login',
  register: '/register',
  dashboard: '/dashboard',
  profile: '/profile',
  settings: '/settings',
} as const;

export type RoutePath = (typeof routes)[keyof typeof routes];
"""

    def _readme_frontend(self) -> str:
        return f"""# {self.config.name}

Frontend application built with React + TypeScript + Vite.

## Getting Started

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

## Project Structure

```
src/
├── components/    # Reusable UI components
├── pages/         # Page components
├── hooks/         # Custom React hooks
├── services/      # API services
├── store/         # State management
├── utils/         # Utility functions
├── types/         # TypeScript types
└── config/        # App configuration
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```
"""

    def _readme_backend(self) -> str:
        return f"""# {self.config.name}

Backend API built with Express + TypeScript.

## Getting Started

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
npm start
```

## Project Structure

```
src/
├── config/        # Configuration
├── models/        # Database models
├── routes/        # API routes
├── controllers/   # Request handlers
├── services/      # Business logic
├── middlewares/   # Express middlewares
├── validators/    # Request validation
└── utils/         # Utility functions
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/auth/login | User login |
| POST | /api/auth/register | User registration |
| GET | /api/users | Get all users |
| GET | /api/users/:id | Get user by ID |
"""

    def _readme_fullstack(self) -> str:
        return f"""# {self.config.name}

Full-stack application with React frontend and Express backend.

## Getting Started

```bash
# Install all dependencies
npm install

# Start both frontend and backend
npm run dev
```

## Project Structure

```
{self.config.name}/
├── frontend/      # React application
└── backend/       # Express API
```
"""

    def _backend_entry(self) -> str:
        return """import app from './app';
import { env } from './config';

const PORT = env.PORT || 3000;

app.listen(PORT, () => {
  console.log(`🚀 Server running on http://localhost:${PORT}`);
  console.log(`📚 Environment: ${env.NODE_ENV}`);
});
"""

    def _express_app(self) -> str:
        return """import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import { router } from './routes';
import { errorHandler, loggerMiddleware } from './middlewares';

const app = express();

// Middlewares
app.use(helmet());
app.use(cors());
app.use(express.json());
app.use(loggerMiddleware);

// Routes
app.use('/api', router);

// Error handling
app.use(errorHandler);

export default app;
"""

    def _db_config(self) -> str:
        return """import { env } from './env';

export const dbConfig = {
  url: env.DATABASE_URL,
  // Add your database configuration here
};

export async function connectDB(): Promise<void> {
  // Implementar: conexión a base de datos
  console.log('📦 Database connected');
}
"""

    def _env_config(self) -> str:
        return """import dotenv from 'dotenv';

dotenv.config();

export const env = {
  NODE_ENV: process.env.NODE_ENV || 'development',
  PORT: parseInt(process.env.PORT || '3000', 10),
  DATABASE_URL: process.env.DATABASE_URL || '',
  JWT_SECRET: process.env.JWT_SECRET || 'secret',
  JWT_EXPIRES_IN: process.env.JWT_EXPIRES_IN || '7d',
} as const;
"""

    def _user_model(self) -> str:
        return """export interface User {
  id: string;
  email: string;
  password: string;
  name: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface CreateUserDTO {
  email: string;
  password: string;
  name: string;
}

export interface UpdateUserDTO {
  email?: string;
  name?: string;
}
"""

    def _routes_index(self) -> str:
        return """import { Router } from 'express';
import userRoutes from './userRoutes';
import authRoutes from './authRoutes';

export const router = Router();

router.use('/users', userRoutes);
router.use('/auth', authRoutes);

// Health check
router.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});
"""

    def _user_routes(self) -> str:
        return """import { Router } from 'express';
import { getUsers, getUserById, updateUser, deleteUser } from '../controllers/userController';
import { authMiddleware } from '../middlewares';

const router = Router();

router.get('/', authMiddleware, getUsers);
router.get('/:id', authMiddleware, getUserById);
router.put('/:id', authMiddleware, updateUser);
router.delete('/:id', authMiddleware, deleteUser);

export default router;
"""

    def _auth_routes(self) -> str:
        return """import { Router } from 'express';

const router = Router();

router.post('/login', (req, res) => {
  // Implementar: lógica de login
  res.json({ message: 'Login endpoint' });
});

router.post('/register', (req, res) => {
  // Implementar: lógica de registro
  res.json({ message: 'Register endpoint' });
});

export default router;
"""

    def _user_controller(self) -> str:
        return """import { Request, Response, NextFunction } from 'express';
import { userService } from '../services';
import { sendSuccess, sendError } from '../utils';

export async function getUsers(req: Request, res: Response, next: NextFunction) {
  try {
    const users = await userService.findAll();
    sendSuccess(res, users);
  } catch (error) {
    next(error);
  }
}

export async function getUserById(req: Request, res: Response, next: NextFunction) {
  try {
    const user = await userService.findById(req.params.id);
    if (!user) {
      return sendError(res, 'User not found', 404);
    }
    sendSuccess(res, user);
  } catch (error) {
    next(error);
  }
}

export async function updateUser(req: Request, res: Response, next: NextFunction) {
  try {
    const user = await userService.update(req.params.id, req.body);
    sendSuccess(res, user);
  } catch (error) {
    next(error);
  }
}

export async function deleteUser(req: Request, res: Response, next: NextFunction) {
  try {
    await userService.delete(req.params.id);
    sendSuccess(res, { message: 'User deleted' });
  } catch (error) {
    next(error);
  }
}
"""

    def _user_service(self) -> str:
        return """import { User, CreateUserDTO, UpdateUserDTO } from '../models';

// In-memory storage (replace with actual database)
let users: User[] = [];

export const userService = {
  async findAll(): Promise<User[]> {
    return users;
  },

  async findById(id: string): Promise<User | undefined> {
    return users.find(u => u.id === id);
  },

  async findByEmail(email: string): Promise<User | undefined> {
    return users.find(u => u.email === email);
  },

  async create(data: CreateUserDTO): Promise<User> {
    const user: User = {
      id: Date.now().toString(),
      ...data,
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    users.push(user);
    return user;
  },

  async update(id: string, data: UpdateUserDTO): Promise<User | undefined> {
    const index = users.findIndex(u => u.id === id);
    if (index === -1) return undefined;
    users[index] = { ...users[index], ...data, updatedAt: new Date() };
    return users[index];
  },

  async delete(id: string): Promise<boolean> {
    const index = users.findIndex(u => u.id === id);
    if (index === -1) return false;
    users.splice(index, 1);
    return true;
  },
};
"""

    def _auth_middleware(self) -> str:
        return """import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';
import { env } from '../config';

export function authMiddleware(req: Request, res: Response, next: NextFunction) {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'No token provided' });
  }

  const token = authHeader.substring(7);

  try {
    const decoded = jwt.verify(token, env.JWT_SECRET);
    (req as any).user = decoded;
    next();
  } catch (error) {
    return res.status(401).json({ error: 'Invalid token' });
  }
}
"""

    def _error_handler(self) -> str:
        return """import { Request, Response, NextFunction } from 'express';

export function errorHandler(
  err: Error,
  req: Request,
  res: Response,
  next: NextFunction
) {
  console.error('Error:', err.message);
  console.error('Stack:', err.stack);

  const statusCode = (err as any).statusCode || 500;
  const message = err.message || 'Internal Server Error';

  res.status(statusCode).json({
    success: false,
    error: message,
    ...(process.env.NODE_ENV === 'development' && { stack: err.stack }),
  });
}
"""

    def _logger_middleware(self) -> str:
        return """import { Request, Response, NextFunction } from 'express';

export function loggerMiddleware(req: Request, res: Response, next: NextFunction) {
  const start = Date.now();

  res.on('finish', () => {
    const duration = Date.now() - start;
    console.log(
      `[${new Date().toISOString()}] ${req.method} ${req.originalUrl} ${res.statusCode} - ${duration}ms`
    );
  });

  next();
}
"""

    def _response_utils(self) -> str:
        return """import { Response } from 'express';

export function sendSuccess<T>(res: Response, data: T, statusCode = 200) {
  res.status(statusCode).json({
    success: true,
    data,
  });
}

export function sendError(res: Response, message: string, statusCode = 400) {
  res.status(statusCode).json({
    success: false,
    error: message,
  });
}

export function sendPaginated<T>(
  res: Response,
  data: T[],
  total: number,
  page: number,
  limit: number
) {
  res.json({
    success: true,
    data,
    pagination: {
      total,
      page,
      limit,
      totalPages: Math.ceil(total / limit),
    },
  });
}
"""

    def _dockerfile(self) -> str:
        return """FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package*.json ./
RUN npm ci --only=production
EXPOSE 3000
CMD ["node", "dist/index.js"]
"""

    def _docker_compose(self) -> str:
        return f"""version: '3.8'

services:
  api:
    build: .
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=development
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/{self.config.name}
    depends_on:
      - db

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB={self.config.name}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  postgres_data:
"""


def main():
    """Punto de entrada."""
    if len(sys.argv) < 3:
        print("Uso: python scaffold_project.py <nombre> <tipo>")
        print("\nTipos disponibles:")
        for pt in ProjectType:
            print(f"  - {pt.value}")
        print("\nEjemplo:")
        print("  python scaffold_project.py mi-app frontend-react")
        print("  python scaffold_project.py mi-api backend-express")
        print("  python scaffold_project.py mi-proyecto fullstack")
        sys.exit(1)

    name = sys.argv[1]
    project_type_str = sys.argv[2]

    try:
        project_type = ProjectType(project_type_str)
    except ValueError:
        print(f"Error: Tipo '{project_type_str}' no válido")
        sys.exit(1)

    config = ProjectConfig(
        name=name, project_type=project_type, typescript=True, with_docker=True, with_tests=True
    )

    scaffolder = ProjectScaffolder(config)
    scaffolder.scaffold()


if __name__ == "__main__":
    main()
