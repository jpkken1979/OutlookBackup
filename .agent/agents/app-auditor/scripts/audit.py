#!/usr/bin/env python3
"""
App Auditor - Generador de conocimiento de aplicación.

Escanea un proyecto y genera .context/APP_KNOWLEDGE.md con información
estructurada para que futuras modificaciones sean precisas.

Uso:
    python audit.py                    # Audita directorio actual
    python audit.py /ruta/proyecto     # Audita proyecto específico
    python audit.py --update           # Actualiza conocimiento existente
"""

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ProjectInfo:
    """Información del proyecto detectada."""

    name: str = ""
    type: str = "unknown"  # web, api, cli, mobile, fullstack
    language: str = "unknown"
    framework: str = ""
    database: str = ""
    styling: str = ""
    state_management: str = ""
    testing: str = ""
    deployment: str = ""

    # Estructuras detectadas
    entry_points: list = field(default_factory=list)
    routes: list = field(default_factory=list)
    models: list = field(default_factory=list)
    components: list = field(default_factory=list)
    services: list = field(default_factory=list)
    config_files: list = field(default_factory=list)
    env_vars: list = field(default_factory=list)
    dependencies: dict = field(default_factory=dict)
    scripts: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    todos: list = field(default_factory=list)


class ProjectDetector:
    """Detecta el tipo y stack de un proyecto."""

    def __init__(self, project_path: Path):
        self.path = project_path
        self.info = ProjectInfo()
        self.info.name = project_path.name

    def detect(self) -> ProjectInfo:
        """Ejecuta detección completa."""
        self._detect_language_and_framework()
        self._detect_database()
        self._detect_structure()
        self._detect_config()
        self._detect_dependencies()
        self._detect_todos_and_warnings()
        return self.info

    def _detect_language_and_framework(self):
        """Detecta lenguaje principal y framework."""
        # Node.js / JavaScript / TypeScript
        if (self.path / "package.json").exists():
            self.info.language = "TypeScript/JavaScript"
            pkg = json.loads((self.path / "package.json").read_text(encoding="utf-8"))
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

            # Detectar framework
            if "next" in deps:
                self.info.framework = f"Next.js {deps.get('next', '')}"
                self.info.type = "fullstack"
            elif "react" in deps:
                self.info.framework = f"React {deps.get('react', '')}"
                self.info.type = "web"
            elif "vue" in deps:
                self.info.framework = f"Vue {deps.get('vue', '')}"
                self.info.type = "web"
            elif "express" in deps:
                self.info.framework = "Express"
                self.info.type = "api"
            elif "fastify" in deps:
                self.info.framework = "Fastify"
                self.info.type = "api"
            elif "electron" in deps:
                self.info.framework = "Electron"
                self.info.type = "desktop"

            # Detectar estilos
            if "tailwindcss" in deps:
                self.info.styling = "Tailwind CSS"
            elif "styled-components" in deps:
                self.info.styling = "styled-components"
            elif "sass" in deps or "scss" in deps:
                self.info.styling = "SASS/SCSS"

            # Detectar estado
            if "zustand" in deps:
                self.info.state_management = "Zustand"
            elif "redux" in deps or "@reduxjs/toolkit" in deps:
                self.info.state_management = "Redux"
            elif "mobx" in deps:
                self.info.state_management = "MobX"
            elif "jotai" in deps:
                self.info.state_management = "Jotai"

            # Detectar testing
            if "vitest" in deps:
                self.info.testing = "Vitest"
            elif "jest" in deps:
                self.info.testing = "Jest"
            elif "playwright" in deps:
                self.info.testing = "Playwright"

            # Scripts
            self.info.scripts = pkg.get("scripts", {})

        # Python
        elif (self.path / "requirements.txt").exists() or (self.path / "pyproject.toml").exists():
            self.info.language = "Python"

            # Leer dependencias
            deps_text = ""
            if (self.path / "requirements.txt").exists():
                deps_text = (self.path / "requirements.txt").read_text(encoding="utf-8")
            elif (self.path / "pyproject.toml").exists():
                deps_text = (self.path / "pyproject.toml").read_text(encoding="utf-8")

            if "fastapi" in deps_text.lower():
                self.info.framework = "FastAPI"
                self.info.type = "api"
            elif "django" in deps_text.lower():
                self.info.framework = "Django"
                self.info.type = "fullstack"
            elif "flask" in deps_text.lower():
                self.info.framework = "Flask"
                self.info.type = "api"
            elif "streamlit" in deps_text.lower():
                self.info.framework = "Streamlit"
                self.info.type = "web"

            if "pytest" in deps_text.lower():
                self.info.testing = "pytest"

        # Go
        elif (self.path / "go.mod").exists():
            self.info.language = "Go"
            self.info.type = "api"

        # Rust
        elif (self.path / "Cargo.toml").exists():
            self.info.language = "Rust"

    def _detect_database(self):
        """Detecta base de datos."""
        # Buscar en archivos de config
        patterns = {
            "PostgreSQL": ["postgres", "postgresql", "pg_", "psycopg"],
            "MySQL": ["mysql", "mariadb"],
            "MongoDB": ["mongodb", "mongoose"],
            "SQLite": ["sqlite"],
            "Redis": ["redis"],
            "Prisma": ["prisma"],
            "Supabase": ["supabase"],
        }

        for db, keywords in patterns.items():
            for file in self.path.rglob("*"):
                if file.is_file() and file.suffix in [
                    ".json",
                    ".ts",
                    ".js",
                    ".py",
                    ".env",
                    ".toml",
                ]:
                    try:
                        content = file.read_text(encoding="utf-8", errors="ignore").lower()
                        if any(kw in content for kw in keywords):
                            self.info.database = db
                            return
                    except Exception:
                        pass

    def _detect_structure(self):
        """Detecta estructura del proyecto."""
        # Buscar puntos de entrada
        entry_patterns = [
            "src/index.*",
            "src/main.*",
            "src/app.*",
            "app/page.*",
            "pages/index.*",
            "index.*",
            "main.py",
            "app.py",
            "server.*",
        ]

        for pattern in entry_patterns:
            for match in self.path.glob(pattern):
                if match.is_file():
                    self.info.entry_points.append(str(match.relative_to(self.path)))

        # Buscar componentes (React/Vue)
        for comp_dir in ["components", "src/components", "app/components"]:
            comp_path = self.path / comp_dir
            if comp_path.exists():
                for f in comp_path.rglob("*"):
                    if f.is_file() and f.suffix in [".tsx", ".jsx", ".vue"]:
                        self.info.components.append(str(f.relative_to(self.path)))

        # Buscar rutas/endpoints
        api_dirs = ["api", "src/api", "app/api", "routes", "src/routes"]
        for api_dir in api_dirs:
            api_path = self.path / api_dir
            if api_path.exists():
                for f in api_path.rglob("*"):
                    if f.is_file() and f.suffix in [".ts", ".js", ".py"]:
                        self.info.routes.append(str(f.relative_to(self.path)))

        # Buscar modelos
        model_patterns = ["models", "src/models", "prisma/schema.prisma", "schemas"]
        for pattern in model_patterns:
            model_path = self.path / pattern
            if model_path.exists():
                if model_path.is_file():
                    self.info.models.append(str(model_path.relative_to(self.path)))
                else:
                    for f in model_path.rglob("*"):
                        if f.is_file():
                            self.info.models.append(str(f.relative_to(self.path)))

    def _detect_config(self):
        """Detecta archivos de configuración."""
        config_patterns = [
            "*.config.*",
            ".env*",
            "tsconfig.json",
            "next.config.*",
            "tailwind.config.*",
            "vite.config.*",
            "webpack.config.*",
            "docker-compose.*",
            "Dockerfile",
            ".dockerignore",
            "prisma/schema.prisma",
            "pyproject.toml",
        ]

        for pattern in config_patterns:
            for match in self.path.glob(pattern):
                if match.is_file():
                    self.info.config_files.append(str(match.relative_to(self.path)))

        # Detectar variables de entorno
        env_file = self.path / ".env.example"
        if not env_file.exists():
            env_file = self.path / ".env.local"
        if not env_file.exists():
            env_file = self.path / ".env"

        if env_file.exists():
            try:
                content = env_file.read_text(encoding="utf-8")
                for line in content.split("\n"):
                    if "=" in line and not line.startswith("#"):
                        var = line.split("=")[0].strip()
                        if var:
                            self.info.env_vars.append(var)
            except Exception:
                pass

    def _detect_dependencies(self):
        """Extrae dependencias principales."""
        if (self.path / "package.json").exists():
            try:
                pkg = json.loads((self.path / "package.json").read_text(encoding="utf-8"))
                self.info.dependencies = pkg.get("dependencies", {})
            except Exception:
                pass

    def _detect_todos_and_warnings(self):
        """Encuentra TODOs y warnings en el código."""
        todo_pattern = re.compile(r"(TODO|FIXME|HACK|XXX|BUG):\s*(.+)", re.IGNORECASE)

        for ext in ["*.ts", "*.tsx", "*.js", "*.jsx", "*.py"]:
            for file in self.path.rglob(ext):
                if "node_modules" in str(file) or ".next" in str(file):
                    continue
                try:
                    content = file.read_text(encoding="utf-8", errors="ignore")
                    for i, line in enumerate(content.split("\n"), 1):
                        match = todo_pattern.search(line)
                        if match:
                            self.info.todos.append(
                                {
                                    "file": str(file.relative_to(self.path)),
                                    "line": i,
                                    "type": match.group(1).upper(),
                                    "message": match.group(2).strip(),
                                }
                            )
                except Exception:
                    pass


class KnowledgeGenerator:
    """Genera el archivo APP_KNOWLEDGE.md."""

    def __init__(self, info: ProjectInfo, project_path: Path):
        self.info = info
        self.path = project_path

    def generate(self) -> str:
        """Genera el contenido del archivo."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        md = f"""# {self.info.name} - Conocimiento de Aplicación

> Generado por app-auditor el {now}
> Última actualización: {now}

## Resumen Ejecutivo

- **Tipo**: {self.info.type.title()}
- **Lenguaje**: {self.info.language}
- **Framework**: {self.info.framework or "N/A"}
- **Base de datos**: {self.info.database or "N/A"}
- **Estilos**: {self.info.styling or "N/A"}
- **Estado**: {self.info.state_management or "N/A"}
- **Testing**: {self.info.testing or "N/A"}

---

## Estructura del Proyecto

```
{self._generate_tree()}
```

---

## Puntos de Entrada

| Archivo | Propósito |
|---------|-----------|
"""
        for entry in self.info.entry_points[:10]:
            md += f"| `{entry}` | Punto de entrada |\n"

        if self.info.routes:
            md += """
---

## Rutas/Endpoints

| Archivo | Tipo |
|---------|------|
"""
            for route in self.info.routes[:20]:
                md += f"| `{route}` | API endpoint |\n"

        if self.info.components:
            md += f"""
---

## Componentes ({len(self.info.components)} encontrados)

| Componente | Ubicación |
|------------|-----------|
"""
            for comp in self.info.components[:20]:
                name = Path(comp).stem
                md += f"| `{name}` | `{comp}` |\n"

            if len(self.info.components) > 20:
                md += f"\n*...y {len(self.info.components) - 20} componentes más*\n"

        if self.info.models:
            md += """
---

## Modelos de Datos

| Archivo |
|---------|
"""
            for model in self.info.models[:10]:
                md += f"| `{model}` |\n"

        if self.info.dependencies:
            md += """
---

## Dependencias Principales

| Paquete | Versión |
|---------|---------|
"""
            for pkg, ver in list(self.info.dependencies.items())[:15]:
                md += f"| `{pkg}` | {ver} |\n"

        if self.info.config_files:
            md += """
---

## Archivos de Configuración

| Archivo | Propósito |
|---------|-----------|
"""
            for cfg in self.info.config_files:
                md += f"| `{cfg}` | Configuración |\n"

        if self.info.env_vars:
            md += """
---

## Variables de Entorno

```env
"""
            for var in self.info.env_vars:
                md += f"{var}=\n"
            md += "```\n"

        if self.info.scripts:
            md += """
---

## Scripts Disponibles

| Comando | Script |
|---------|--------|
"""
            for name, script in list(self.info.scripts.items())[:10]:
                md += f"| `npm run {name}` | `{script[:50]}` |\n"

        if self.info.todos:
            md += f"""
---

## TODOs y Warnings ({len(self.info.todos)} encontrados)

| Archivo | Línea | Tipo | Mensaje |
|---------|-------|------|---------|
"""
            for todo in self.info.todos[:15]:
                md += f"| `{todo['file']}` | {todo['line']} | {todo['type']} | {todo['message'][:40]} |\n"

        md += """
---

## Cómo Hacer Modificaciones

### Para agregar una nueva página/ruta:
1. Crear archivo en la carpeta de rutas correspondiente
2. Seguir el patrón de archivos existentes
3. Importar componentes necesarios

### Para modificar un componente:
1. Localizar el componente en la tabla de arriba
2. Verificar dependencias (quién lo usa)
3. Hacer cambios manteniendo la interfaz

### Para agregar un endpoint:
1. Crear archivo en la carpeta de API
2. Seguir patrón de validación existente
3. Documentar en este archivo

---

## Zonas de Riesgo

| Área | Nivel | Razón |
|------|-------|-------|
| Configuración de BD | ALTO | Afecta toda la app |
| Autenticación | ALTO | Seguridad crítica |
| Componentes compartidos | MEDIO | Usados en múltiples lugares |

---

*Generado por app-auditor - Antigravity Ecosystem v3.1*
*Para actualizar: ejecutar `python audit.py --update`*
"""
        return md

    def _generate_tree(self) -> str:
        """Genera árbol de estructura simplificado."""
        tree_lines = [f"{self.info.name}/"]

        # Mostrar estructura básica
        important_dirs = [
            "src",
            "app",
            "components",
            "lib",
            "api",
            "pages",
            "public",
            "prisma",
            "tests",
        ]

        for d in sorted(self.path.iterdir()):
            if d.name.startswith(".") and d.name not in [".env.example"]:
                continue
            if d.name in ["node_modules", "__pycache__", ".next", "dist", "build"]:
                continue

            if d.is_dir():
                tree_lines.append(f"├── {d.name}/")
                # Mostrar primer nivel de subdirectorios importantes
                if d.name in important_dirs:
                    for sub in sorted(d.iterdir())[:5]:
                        if sub.is_dir():
                            tree_lines.append(f"│   ├── {sub.name}/")
                        else:
                            tree_lines.append(f"│   ├── {sub.name}")
            else:
                tree_lines.append(f"├── {d.name}")

        return "\n".join(tree_lines[:30])


def main():
    parser = argparse.ArgumentParser(description="App Auditor - Genera conocimiento de aplicación")
    parser.add_argument("path", nargs="?", default=".", help="Ruta del proyecto")
    parser.add_argument(
        "--update", "-u", action="store_true", help="Actualizar conocimiento existente"
    )
    parser.add_argument(
        "--output", "-o", help="Archivo de salida (default: .context/APP_KNOWLEDGE.md)"
    )

    args = parser.parse_args()

    project_path = Path(args.path).resolve()

    if not project_path.exists():
        print(f"Error: El directorio {project_path} no existe")
        return 1

    print(f"[AUDIT] Auditando: {project_path.name}")
    print("-" * 50)

    # Detectar proyecto
    detector = ProjectDetector(project_path)
    info = detector.detect()

    print(f"[TIPO] {info.type}")
    print(f"[STACK] {info.language} + {info.framework}")
    print(f"[BD] {info.database or 'No detectada'}")
    print(f"[COMPONENTES] {len(info.components)}")
    print(f"[RUTAS] {len(info.routes)}")
    print(f"[TODOS] {len(info.todos)}")
    print("-" * 50)

    # Generar conocimiento
    generator = KnowledgeGenerator(info, project_path)
    content = generator.generate()

    # Guardar archivo
    context_dir = project_path / ".context"
    context_dir.mkdir(exist_ok=True)

    output_file = Path(args.output) if args.output else context_dir / "APP_KNOWLEDGE.md"
    output_file.write_text(content, encoding="utf-8")

    print(f"[OK] Conocimiento guardado en: {output_file}")
    print(f"[LINES] {len(content.split(chr(10)))} lineas generadas")

    return 0


if __name__ == "__main__":
    exit(main())
