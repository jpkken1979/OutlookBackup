#!/usr/bin/env python3
"""
Universal Bootstrap para Antigravity Agents.

Detecta automaticamente el tipo de proyecto y configura el ecosistema
de agentes de forma inteligente. Adaptable a cualquier repositorio.

Uso:
    python .agent/scripts/universal_bootstrap.py [--target /path/to/repo]
    python .agent/scripts/universal_bootstrap.py --analyze-only
    python .agent/scripts/universal_bootstrap.py --minimal
"""

import argparse
import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("antigravity.bootstrap")


class ProjectType(Enum):
    """Tipos de proyecto soportados."""

    PYTHON = "python"
    NODEJS = "nodejs"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    GO = "go"
    JAVA = "java"
    CSHARP = "csharp"
    RUBY = "ruby"
    PHP = "php"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class FrameworkType(Enum):
    """Frameworks detectados."""

    # Python
    DJANGO = "django"
    FLASK = "flask"
    FASTAPI = "fastapi"
    PYTEST = "pytest"

    # JavaScript/TypeScript
    REACT = "react"
    NEXTJS = "nextjs"
    VUE = "vue"
    ANGULAR = "angular"
    EXPRESS = "express"
    NESTJS = "nestjs"

    # Rust
    ACTIX = "actix"
    ROCKET = "rocket"
    TAURI = "tauri"

    # Go
    GIN = "gin"
    FIBER = "fiber"

    # General
    DOCKER = "docker"
    KUBERNETES = "kubernetes"

    NONE = "none"


@dataclass
class ProjectAnalysis:
    """Resultado del analisis de proyecto."""

    project_type: ProjectType
    frameworks: list[FrameworkType]
    has_tests: bool
    has_ci: bool
    has_docker: bool
    has_docs: bool
    languages: dict[str, int]  # language -> file count
    entry_points: list[str]
    config_files: list[str]
    recommended_agents: list[str]
    project_size: str  # small, medium, large
    complexity_score: int  # 1-10

    def to_dict(self) -> dict:
        return {
            "project_type": self.project_type.value,
            "frameworks": [f.value for f in self.frameworks],
            "has_tests": self.has_tests,
            "has_ci": self.has_ci,
            "has_docker": self.has_docker,
            "has_docs": self.has_docs,
            "languages": self.languages,
            "entry_points": self.entry_points,
            "config_files": self.config_files,
            "recommended_agents": self.recommended_agents,
            "project_size": self.project_size,
            "complexity_score": self.complexity_score,
        }


class ProjectDetector:
    """Detector inteligente de tipo de proyecto."""

    LANGUAGE_EXTENSIONS = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".cs": "csharp",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
    }

    FRAMEWORK_INDICATORS = {
        # Python
        "django": ["manage.py", "settings.py", "wsgi.py"],
        "flask": ["flask", "Flask("],
        "fastapi": ["fastapi", "FastAPI("],
        # JavaScript/TypeScript
        "react": ["react", "React", "jsx", "tsx"],
        "nextjs": ["next.config", "_app.tsx", "_app.js", "pages/"],
        "vue": ["vue.config", ".vue", "Vue("],
        "angular": ["angular.json", "@angular/core"],
        "express": ["express()", "app.listen"],
        "nestjs": ["@nestjs/core", "NestFactory"],
        # Rust
        "tauri": ["tauri.conf.json", "tauri::"],
        "actix": ["actix-web", "HttpServer"],
        "rocket": ["#[rocket::main]", "rocket::"],
        # Go
        "gin": ["gin-gonic/gin", "gin.Default()"],
        "fiber": ["gofiber/fiber", "fiber.New()"],
    }

    def __init__(self, root_path: Path):
        self.root = root_path
        self.analysis: ProjectAnalysis | None = None

    def analyze(self) -> ProjectAnalysis:
        """Analiza el proyecto completo."""
        logger.info(f"Analizando proyecto en: {self.root}")

        languages = self._count_languages()
        frameworks = self._detect_frameworks()
        project_type = self._determine_project_type(languages)

        # Detectar caracteristicas
        has_tests = self._has_tests()
        has_ci = self._has_ci()
        has_docker = self._has_docker()
        has_docs = self._has_docs()

        # Encontrar puntos de entrada
        entry_points = self._find_entry_points(project_type)
        config_files = self._find_config_files()

        # Calcular tamano y complejidad
        total_files = sum(languages.values())
        project_size = self._calculate_size(total_files)
        complexity = self._calculate_complexity(languages, frameworks)

        # Recomendar agentes
        recommended = self._recommend_agents(project_type, frameworks, has_tests)

        self.analysis = ProjectAnalysis(
            project_type=project_type,
            frameworks=frameworks,
            has_tests=has_tests,
            has_ci=has_ci,
            has_docker=has_docker,
            has_docs=has_docs,
            languages=languages,
            entry_points=entry_points,
            config_files=config_files,
            recommended_agents=recommended,
            project_size=project_size,
            complexity_score=complexity,
        )

        return self.analysis

    def _count_languages(self) -> dict[str, int]:
        """Cuenta archivos por lenguaje."""
        counts: dict[str, int] = {}

        for ext, lang in self.LANGUAGE_EXTENSIONS.items():
            try:
                files = list(self.root.rglob(f"*{ext}"))
                # Excluir node_modules, venv, etc.
                files = [
                    f
                    for f in files
                    if not any(
                        p in str(f)
                        for p in [
                            "node_modules",
                            "venv",
                            ".venv",
                            "__pycache__",
                            "target",
                            "dist",
                            "build",
                        ]
                    )
                ]
                if files:
                    counts[lang] = counts.get(lang, 0) + len(files)
            except Exception:
                pass

        return counts

    def _detect_frameworks(self) -> list[FrameworkType]:
        """Detecta frameworks utilizados."""
        detected: list[FrameworkType] = []

        # Buscar archivos de configuracion
        config_patterns = {
            FrameworkType.NEXTJS: ["next.config.js", "next.config.mjs", "next.config.ts"],
            FrameworkType.DJANGO: ["manage.py"],
            FrameworkType.TAURI: ["tauri.conf.json", "src-tauri/"],
            FrameworkType.DOCKER: ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"],
            FrameworkType.KUBERNETES: ["k8s/", "kubernetes/", "*.yaml"],
        }

        for framework, patterns in config_patterns.items():
            for pattern in patterns:
                if (self.root / pattern).exists() or list(self.root.glob(pattern)):
                    if framework not in detected:
                        detected.append(framework)
                    break

        # Buscar en package.json
        package_json = self.root / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                if "react" in deps:
                    detected.append(FrameworkType.REACT)
                if "next" in deps:
                    detected.append(FrameworkType.NEXTJS)
                if "vue" in deps:
                    detected.append(FrameworkType.VUE)
                if "@angular/core" in deps:
                    detected.append(FrameworkType.ANGULAR)
                if "express" in deps:
                    detected.append(FrameworkType.EXPRESS)
                if "@nestjs/core" in deps:
                    detected.append(FrameworkType.NESTJS)
            except Exception:
                pass

        # Buscar en requirements.txt o pyproject.toml
        for req_file in ["requirements.txt", "pyproject.toml", "setup.py"]:
            path = self.root / req_file
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8").lower()
                    if "django" in content:
                        detected.append(FrameworkType.DJANGO)
                    if "flask" in content:
                        detected.append(FrameworkType.FLASK)
                    if "fastapi" in content:
                        detected.append(FrameworkType.FASTAPI)
                    if "pytest" in content:
                        detected.append(FrameworkType.PYTEST)
                except Exception:
                    pass

        # Buscar en Cargo.toml (Rust)
        cargo_toml = self.root / "Cargo.toml"
        if cargo_toml.exists():
            try:
                content = cargo_toml.read_text(encoding="utf-8").lower()
                if "tauri" in content:
                    detected.append(FrameworkType.TAURI)
                if "actix-web" in content:
                    detected.append(FrameworkType.ACTIX)
                if "rocket" in content:
                    detected.append(FrameworkType.ROCKET)
            except Exception:
                pass

        return list(set(detected))

    def _determine_project_type(self, languages: dict[str, int]) -> ProjectType:
        """Determina el tipo principal de proyecto."""
        if not languages:
            return ProjectType.UNKNOWN

        # Si hay multiples lenguajes significativos, es mixto
        significant = [l for l, c in languages.items() if c > 10]
        if len(significant) > 2:
            return ProjectType.MIXED

        # Obtener lenguaje dominante
        dominant = max(languages.items(), key=lambda x: x[1])[0]

        mapping = {
            "python": ProjectType.PYTHON,
            "javascript": ProjectType.NODEJS,
            "typescript": ProjectType.TYPESCRIPT,
            "rust": ProjectType.RUST,
            "go": ProjectType.GO,
            "java": ProjectType.JAVA,
            "csharp": ProjectType.CSHARP,
            "ruby": ProjectType.RUBY,
            "php": ProjectType.PHP,
        }

        return mapping.get(dominant, ProjectType.UNKNOWN)

    def _has_tests(self) -> bool:
        """Verifica si hay tests."""
        test_indicators = [
            "tests/",
            "test/",
            "__tests__/",
            "*_test.py",
            "test_*.py",
            "*.spec.ts",
            "*.test.ts",
            "*.spec.js",
            "*.test.js",
        ]

        for indicator in test_indicators:
            if "/" in indicator:
                if (self.root / indicator.rstrip("/")).exists():
                    return True
            else:
                if list(self.root.rglob(indicator)):
                    return True

        return False

    def _has_ci(self) -> bool:
        """Verifica si hay CI configurado."""
        ci_paths = [
            ".github/workflows/",
            ".gitlab-ci.yml",
            ".circleci/",
            "Jenkinsfile",
            ".travis.yml",
            "azure-pipelines.yml",
        ]

        for path in ci_paths:
            full_path = self.root / path
            if full_path.exists():
                return True

        return False

    def _has_docker(self) -> bool:
        """Verifica si hay Docker."""
        return (
            (self.root / "Dockerfile").exists()
            or (self.root / "docker-compose.yml").exists()
            or (self.root / "docker-compose.yaml").exists()
        )

    def _has_docs(self) -> bool:
        """Verifica si hay documentacion."""
        doc_indicators = [
            "docs/",
            "documentation/",
            "doc/",
            "README.md",
            "CONTRIBUTING.md",
            "mkdocs.yml",
            "sphinx/",
        ]

        return any((self.root / indicator.rstrip("/")).exists() for indicator in doc_indicators)

    def _find_entry_points(self, project_type: ProjectType) -> list[str]:
        """Encuentra puntos de entrada del proyecto."""
        entry_points: list[str] = []

        patterns = {
            ProjectType.PYTHON: ["main.py", "app.py", "run.py", "manage.py", "__main__.py"],
            ProjectType.NODEJS: ["index.js", "app.js", "server.js", "main.js"],
            ProjectType.TYPESCRIPT: ["index.ts", "app.ts", "server.ts", "main.ts"],
            ProjectType.RUST: ["main.rs", "lib.rs"],
            ProjectType.GO: ["main.go", "cmd/"],
        }

        for pattern in patterns.get(project_type, []):
            if "/" in pattern:
                if (self.root / pattern).exists():
                    entry_points.append(pattern)
            else:
                for f in self.root.rglob(pattern):
                    rel_path = str(f.relative_to(self.root))
                    if not any(p in rel_path for p in ["node_modules", "venv", "__pycache__"]):
                        entry_points.append(rel_path)

        return entry_points[:10]  # Limitar a 10

    def _find_config_files(self) -> list[str]:
        """Encuentra archivos de configuracion."""
        config_patterns = [
            "*.json",
            "*.yaml",
            "*.yml",
            "*.toml",
            "*.ini",
            "*.env*",
            "Makefile",
            "Dockerfile",
            ".gitignore",
        ]

        configs: list[str] = []
        for pattern in config_patterns:
            for f in self.root.glob(pattern):
                if f.is_file():
                    configs.append(f.name)

        return list(set(configs))[:20]

    def _calculate_size(self, total_files: int) -> str:
        """Calcula tamano del proyecto."""
        if total_files < 50:
            return "small"
        elif total_files < 500:
            return "medium"
        else:
            return "large"

    def _calculate_complexity(
        self, languages: dict[str, int], frameworks: list[FrameworkType]
    ) -> int:
        """Calcula score de complejidad (1-10)."""
        score = 1

        # +1 por cada lenguaje significativo
        score += min(len([l for l, c in languages.items() if c > 5]), 3)

        # +1 por cada framework
        score += min(len(frameworks), 3)

        # +1 si tiene Docker
        if FrameworkType.DOCKER in frameworks:
            score += 1

        # +1 si tiene Kubernetes
        if FrameworkType.KUBERNETES in frameworks:
            score += 1

        return min(score, 10)

    def _recommend_agents(
        self, project_type: ProjectType, frameworks: list[FrameworkType], has_tests: bool
    ) -> list[str]:
        """Recomienda agentes basado en el analisis."""
        recommended = ["explorer", "architect", "planner", "code-reviewer"]

        # Por tipo de proyecto
        type_agents = {
            ProjectType.PYTHON: ["debugger", "performance-optimizer"],
            ProjectType.NODEJS: ["frontend-specialist", "api-designer"],
            ProjectType.TYPESCRIPT: ["frontend-specialist", "api-designer"],
            ProjectType.RUST: ["tauri-backend", "performance-optimizer"],
            ProjectType.GO: ["backend-specialist", "api-designer"],
        }
        recommended.extend(type_agents.get(project_type, []))

        # Por framework
        framework_agents = {
            FrameworkType.REACT: ["react-specialist", "ui-ux-designer", "a11y"],
            FrameworkType.NEXTJS: ["react-specialist", "seo-specialist"],
            FrameworkType.VUE: ["frontend-specialist", "ui-ux-designer"],
            FrameworkType.DJANGO: ["backend-specialist", "security-auditor"],
            FrameworkType.FASTAPI: ["api-designer", "backend-specialist"],
            FrameworkType.TAURI: ["tauri-architect", "tauri-frontend", "tauri-backend"],
            FrameworkType.DOCKER: ["devops-engineer", "infrastructure-architect"],
            FrameworkType.KUBERNETES: ["devops-engineer", "infrastructure-architect"],
        }
        for framework in frameworks:
            recommended.extend(framework_agents.get(framework, []))

        # Si tiene tests
        if has_tests:
            recommended.append("test-engineer")

        # Siempre utiles
        recommended.extend(["security-auditor", "dependency"])

        return list(dict.fromkeys(recommended))  # Eliminar duplicados manteniendo orden


class AntigravityBootstrap:
    """Bootstrap del ecosistema Antigravity."""

    def __init__(self, target_path: Path, source_path: Path | None = None):
        self.target = target_path
        self.source = source_path or Path(__file__).parent.parent.parent
        self.detector = ProjectDetector(target_path)
        self.analysis: ProjectAnalysis | None = None

    def run(self, minimal: bool = False, analyze_only: bool = False) -> dict:
        """Ejecuta el bootstrap completo."""
        logger.info("=" * 60)
        logger.info("ANTIGRAVITY UNIVERSAL BOOTSTRAP")
        logger.info("=" * 60)

        # Paso 1: Analizar proyecto
        self.analysis = self.detector.analyze()
        self._print_analysis()

        if analyze_only:
            return self.analysis.to_dict()

        # Paso 2: Crear estructura base
        self._create_base_structure(minimal)

        # Paso 3: Copiar agentes recomendados
        if not minimal:
            self._copy_recommended_agents()

        # Paso 4: Crear configuracion especifica
        self._create_project_config()

        # Paso 5: Crear CLAUDE.md adaptado
        self._create_claude_md()

        # Paso 6: Crear hooks de activacion
        self._create_activation_hooks()

        logger.info("=" * 60)
        logger.info("BOOTSTRAP COMPLETADO")
        logger.info("=" * 60)

        return {
            "status": "success",
            "analysis": self.analysis.to_dict(),
            "created_files": self._list_created_files(),
        }

    def _print_analysis(self):
        """Imprime el analisis del proyecto."""
        if not self.analysis:
            return

        print("\n" + "=" * 50)
        print("ANALISIS DEL PROYECTO")
        print("=" * 50)
        print(f"Tipo: {self.analysis.project_type.value}")
        print(f"Frameworks: {', '.join(f.value for f in self.analysis.frameworks) or 'ninguno'}")
        print(f"Tamano: {self.analysis.project_size}")
        print(f"Complejidad: {self.analysis.complexity_score}/10")
        print(f"Tests: {'Si' if self.analysis.has_tests else 'No'}")
        print(f"CI/CD: {'Si' if self.analysis.has_ci else 'No'}")
        print(f"Docker: {'Si' if self.analysis.has_docker else 'No'}")
        print(f"Docs: {'Si' if self.analysis.has_docs else 'No'}")
        print("\nLenguajes:")
        for lang, count in sorted(self.analysis.languages.items(), key=lambda x: -x[1]):
            print(f"  - {lang}: {count} archivos")
        print("\nAgentes recomendados:")
        for agent in self.analysis.recommended_agents[:10]:
            print(f"  - {agent}")
        print("=" * 50 + "\n")

    def _create_base_structure(self, minimal: bool):
        """Crea estructura base del ecosistema."""
        logger.info("Creando estructura base...")

        dirs = [
            ".agent",
            ".agent/core",
            ".agent/agents",
            ".agent/skills",
            ".agent/memory",
            ".agent/config",
        ]

        if not minimal:
            dirs.extend(
                [
                    ".agent/workflows",
                    ".agent/observability",
                    ".agent/scripts",
                ]
            )

        for d in dirs:
            (self.target / d).mkdir(parents=True, exist_ok=True)
            logger.info(f"  Creado: {d}/")

    def _copy_recommended_agents(self):
        """Copia agentes recomendados."""
        if not self.analysis:
            return

        logger.info("Copiando agentes recomendados...")
        agents_source = self.source / ".agent" / "agents"

        for agent_name in self.analysis.recommended_agents[:15]:  # Limitar
            source_agent = agents_source / agent_name
            target_agent = self.target / ".agent" / "agents" / agent_name

            if source_agent.exists() and not target_agent.exists():
                try:
                    shutil.copytree(source_agent, target_agent)
                    logger.info(f"  Copiado: {agent_name}")
                except Exception as e:
                    logger.warning(f"  Error copiando {agent_name}: {e}")

    def _create_project_config(self):
        """Crea configuracion especifica del proyecto."""
        if not self.analysis:
            return

        config = {
            "version": "1.0.0",
            "project": {
                "type": self.analysis.project_type.value,
                "frameworks": [f.value for f in self.analysis.frameworks],
                "size": self.analysis.project_size,
                "complexity": self.analysis.complexity_score,
            },
            "agents": {
                "recommended": self.analysis.recommended_agents,
                "active": self.analysis.recommended_agents[:10],
            },
            "analysis": {
                "has_tests": self.analysis.has_tests,
                "has_ci": self.analysis.has_ci,
                "has_docker": self.analysis.has_docker,
                "entry_points": self.analysis.entry_points,
            },
            "created_at": datetime.now().isoformat(),
        }

        config_path = self.target / ".agent" / "config" / "project.json"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        logger.info(f"Creada configuracion: {config_path}")

    def _create_claude_md(self):
        """Crea CLAUDE.md adaptado al proyecto."""
        if not self.analysis:
            return

        claude_md = f"""# CLAUDE.md

Este archivo configura Claude Code para trabajar con este proyecto.

## Tipo de Proyecto

- **Tipo**: {self.analysis.project_type.value}
- **Frameworks**: {", ".join(f.value for f in self.analysis.frameworks) or "ninguno"}
- **Complejidad**: {self.analysis.complexity_score}/10

## Agentes Recomendados

{chr(10).join(f"- `{a}`" for a in self.analysis.recommended_agents[:10])}

## Comandos Utiles

```bash
# Invocar agente
python .agent/scripts/invoke-agent.py <agent-name> "<tarea>"

# Analizar proyecto
python .agent/scripts/universal_bootstrap.py --analyze-only

# Listar agentes
python .agent/scripts/invoke-agent.py --list
```

## Reglas del Proyecto

1. **Idioma**: Responder en espanol
2. **Tests**: {"Ejecutar tests antes de commit" if self.analysis.has_tests else "Agregar tests para nuevo codigo"}
3. **CI/CD**: {"Verificar que CI pase" if self.analysis.has_ci else "Considerar agregar CI"}
4. **Docker**: {"Usar Docker para desarrollo" if self.analysis.has_docker else "No hay Docker configurado"}

## Puntos de Entrada

{chr(10).join(f"- `{e}`" for e in self.analysis.entry_points[:5]) or "- No detectados"}

## Configuracion

El ecosistema Antigravity fue configurado automaticamente.
Ver `.agent/config/project.json` para detalles.

---
*Generado por Antigravity Bootstrap v1.0*
"""

        claude_md_path = self.target / "CLAUDE.md"

        # No sobreescribir si ya existe
        if not claude_md_path.exists():
            with open(claude_md_path, "w") as f:
                f.write(claude_md)
            logger.info("Creado: CLAUDE.md")
        else:
            logger.info("CLAUDE.md ya existe, no se sobreescribe")

    def _create_activation_hooks(self):
        """Crea hooks de activacion."""
        hook_script = '''#!/usr/bin/env python3
"""
Hook de activacion para Antigravity.
Se ejecuta automaticamente al iniciar una sesion de Claude Code.
"""

import json
import sys
from pathlib import Path

def main():
    config_path = Path(".agent/config/project.json")

    if not config_path.exists():
        print("Proyecto no inicializado. Ejecuta: python .agent/scripts/universal_bootstrap.py")
        return

    with open(config_path) as f:
        config = json.load(f)

    project_type = config.get("project", {}).get("type", "unknown")
    agents = config.get("agents", {}).get("active", [])

    print(f"Proyecto: {project_type}")
    print(f"Agentes activos: {len(agents)}")
    print("Antigravity listo!")

if __name__ == "__main__":
    main()
'''

        hook_path = self.target / ".agent" / "scripts" / "activation_hook.py"
        hook_path.parent.mkdir(parents=True, exist_ok=True)

        with open(hook_path, "w") as f:
            f.write(hook_script)

        logger.info(f"Creado: {hook_path}")

    def _list_created_files(self) -> list[str]:
        """Lista archivos creados."""
        created: list[str] = []

        agent_dir = self.target / ".agent"
        if agent_dir.exists():
            for f in agent_dir.rglob("*"):
                if f.is_file():
                    created.append(str(f.relative_to(self.target)))

        return created


def main():
    parser = argparse.ArgumentParser(
        description="Antigravity Universal Bootstrap",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Analizar proyecto actual
  python universal_bootstrap.py --analyze-only

  # Bootstrap minimo
  python universal_bootstrap.py --minimal

  # Bootstrap completo en otro directorio
  python universal_bootstrap.py --target /path/to/project
        """,
    )

    parser.add_argument(
        "--target", "-t", type=Path, default=Path.cwd(), help="Directorio del proyecto a configurar"
    )
    parser.add_argument(
        "--analyze-only", "-a", action="store_true", help="Solo analizar, no crear archivos"
    )
    parser.add_argument(
        "--minimal", "-m", action="store_true", help="Configuracion minima (solo core)"
    )
    parser.add_argument("--json", "-j", action="store_true", help="Output en formato JSON")

    args = parser.parse_args()

    bootstrap = AntigravityBootstrap(args.target)
    result = bootstrap.run(minimal=args.minimal, analyze_only=args.analyze_only)

    if args.json:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
