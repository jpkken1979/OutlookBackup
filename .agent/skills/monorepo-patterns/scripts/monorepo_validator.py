#!/usr/bin/env python3
"""
Monorepo Patterns - Validator and Scaffold

Este script ayuda a validar y crear estructuras de monorepo incluyendo:
- Validación de estructura Turborepo/Nx
- Verificación de workspaces
- Scaffold de nuevo monorepo
- Análisis de dependencias

Uso:
    python monorepo_validator.py --validate /path/to/monorepo
    python monorepo_validator.py --scaffold my-monorepo --tool turborepo
    python monorepo_validator.py --analyze /path/to/monorepo
"""

import argparse
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Resultado de validación."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)


@dataclass
class Package:
    """Información de un paquete."""

    name: str
    path: Path
    version: str
    dependencies: dict[str, str] = field(default_factory=dict)
    dev_dependencies: dict[str, str] = field(default_factory=dict)
    scripts: dict[str, str] = field(default_factory=dict)


class MonorepoValidator:
    """Validador de estructura de monorepo."""

    def __init__(self, root_path: Path) -> None:
        self.root = root_path
        self.tool: str | None = None
        self.packages: list[Package] = []

    def detect_tool(self) -> str | None:
        """Detectar herramienta de monorepo."""
        if (self.root / "turbo.json").exists():
            self.tool = "turborepo"
        elif (self.root / "nx.json").exists():
            self.tool = "nx"
        elif (self.root / "lerna.json").exists():
            self.tool = "lerna"
        elif (self.root / "rush.json").exists():
            self.tool = "rush"
        elif (self.root / "pnpm-workspace.yaml").exists():
            self.tool = "pnpm"

        return self.tool

    def validate(self) -> ValidationResult:
        """Validar estructura del monorepo."""
        result = ValidationResult(valid=True)

        # Detectar herramienta
        tool = self.detect_tool()
        if tool:
            result.info.append(f"Herramienta detectada: {tool}")
        else:
            result.warnings.append("No se detectó herramienta de monorepo (Turborepo, Nx, etc.)")

        # Validar package.json raíz
        root_pkg = self.root / "package.json"
        if not root_pkg.exists():
            result.errors.append("Falta package.json en la raíz")
            result.valid = False
        else:
            pkg_data = json.loads(root_pkg.read_text())
            if not pkg_data.get("private"):
                result.warnings.append("package.json raíz debería tener 'private: true'")

            if "workspaces" not in pkg_data and not (self.root / "pnpm-workspace.yaml").exists():
                result.warnings.append("No se encontró configuración de workspaces")

        # Validar estructura de directorios
        expected_dirs = ["apps", "packages"]
        for dir_name in expected_dirs:
            dir_path = self.root / dir_name
            if dir_path.exists():
                result.info.append(f"Directorio '{dir_name}/' encontrado")
                self._scan_packages(dir_path)
            else:
                result.info.append(f"Directorio '{dir_name}/' no encontrado (opcional)")

        # Validar configuraciones específicas
        if tool == "turborepo":
            self._validate_turborepo(result)
        elif tool == "nx":
            self._validate_nx(result)

        # Validar paquetes encontrados
        result.info.append(f"Paquetes encontrados: {len(self.packages)}")
        for pkg in self.packages:
            self._validate_package(pkg, result)

        return result

    def _scan_packages(self, directory: Path) -> None:
        """Escanear paquetes en un directorio."""
        for item in directory.iterdir():
            if item.is_dir():
                pkg_json = item / "package.json"
                if pkg_json.exists():
                    try:
                        data = json.loads(pkg_json.read_text())
                        pkg = Package(
                            name=data.get("name", item.name),
                            path=item,
                            version=data.get("version", "0.0.0"),
                            dependencies=data.get("dependencies", {}),
                            dev_dependencies=data.get("devDependencies", {}),
                            scripts=data.get("scripts", {}),
                        )
                        self.packages.append(pkg)
                    except json.JSONDecodeError:
                        logger.warning(f"Error parseando {pkg_json}")

    def _validate_turborepo(self, result: ValidationResult) -> None:
        """Validaciones específicas de Turborepo."""
        turbo_json = self.root / "turbo.json"
        if turbo_json.exists():
            try:
                data = json.loads(turbo_json.read_text())

                if "pipeline" in data:
                    pipelines = list(data["pipeline"].keys())
                    result.info.append(f"Pipelines configurados: {', '.join(pipelines)}")

                    # Verificar pipelines comunes
                    common = ["build", "test", "lint"]
                    for cmd in common:
                        if cmd not in data["pipeline"]:
                            result.warnings.append(f"Pipeline '{cmd}' no configurado")

            except json.JSONDecodeError:
                result.errors.append("turbo.json tiene formato inválido")
                result.valid = False

    def _validate_nx(self, result: ValidationResult) -> None:
        """Validaciones específicas de Nx."""
        nx_json = self.root / "nx.json"
        if nx_json.exists():
            try:
                data = json.loads(nx_json.read_text())
                if "targetDefaults" in data:
                    targets = list(data["targetDefaults"].keys())
                    result.info.append(f"Target defaults: {', '.join(targets)}")
            except json.JSONDecodeError:
                result.errors.append("nx.json tiene formato inválido")
                result.valid = False

    def _validate_package(self, pkg: Package, result: ValidationResult) -> None:
        """Validar un paquete individual."""
        # Verificar nombre con prefijo
        if not pkg.name.startswith("@"):
            result.warnings.append(f"Paquete '{pkg.name}' sin namespace (@org/name)")

        # Verificar dependencias internas
        internal_deps = [
            dep
            for dep in pkg.dependencies
            if dep.startswith("@") and "workspace:" in pkg.dependencies.get(dep, "")
        ]
        if internal_deps:
            result.info.append(f"  {pkg.name}: deps internas: {', '.join(internal_deps)}")


class MonorepoScaffold:
    """Generador de estructura de monorepo."""

    def __init__(self, name: str, tool: str = "turborepo") -> None:
        self.name = name
        self.tool = tool
        self.root = Path(name)

    def scaffold(self) -> list[str]:
        """Generar estructura de monorepo."""
        created_files = []

        # Crear directorios
        dirs = [
            "apps/web/src",
            "apps/docs/src",
            "packages/ui/src",
            "packages/utils/src",
            "packages/config",
        ]

        for dir_path in dirs:
            full_path = self.root / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            created_files.append(str(full_path))

        # Generar archivos según herramienta
        if self.tool == "turborepo":
            created_files.extend(self._scaffold_turborepo())
        elif self.tool == "nx":
            created_files.extend(self._scaffold_nx())

        # Archivos comunes
        created_files.extend(self._scaffold_common())

        return created_files

    def _scaffold_turborepo(self) -> list[str]:
        """Scaffolding específico de Turborepo."""
        files = []

        # turbo.json
        turbo_config = {
            "$schema": "https://turbo.build/schema.json",
            "globalDependencies": ["**/.env.*local"],
            "pipeline": {
                "build": {"dependsOn": ["^build"], "outputs": ["dist/**", ".next/**"]},
                "lint": {},
                "dev": {"cache": False, "persistent": True},
                "test": {"dependsOn": ["build"]},
            },
        }
        turbo_path = self.root / "turbo.json"
        turbo_path.write_text(json.dumps(turbo_config, indent=2))
        files.append(str(turbo_path))

        return files

    def _scaffold_nx(self) -> list[str]:
        """Scaffolding específico de Nx."""
        files = []

        nx_config = {
            "$schema": "./node_modules/nx/schemas/nx-schema.json",
            "targetDefaults": {
                "build": {"dependsOn": ["^build"], "cache": True},
                "test": {"cache": True},
            },
        }
        nx_path = self.root / "nx.json"
        nx_path.write_text(json.dumps(nx_config, indent=2))
        files.append(str(nx_path))

        return files

    def _scaffold_common(self) -> list[str]:
        """Archivos comunes a todos los monorepos."""
        files = []

        # Root package.json
        root_pkg = {
            "name": self.name,
            "private": True,
            "scripts": {
                "build": f"{'turbo' if self.tool == 'turborepo' else 'nx run-many --target='} build",
                "dev": f"{'turbo' if self.tool == 'turborepo' else 'nx run-many --target='} dev",
                "lint": f"{'turbo' if self.tool == 'turborepo' else 'nx run-many --target='} lint",
                "test": f"{'turbo' if self.tool == 'turborepo' else 'nx run-many --target='} test",
            },
            "devDependencies": {"turbo" if self.tool == "turborepo" else "nx": "latest"},
            "packageManager": "pnpm@8.15.0",
        }
        pkg_path = self.root / "package.json"
        pkg_path.write_text(json.dumps(root_pkg, indent=2))
        files.append(str(pkg_path))

        # pnpm-workspace.yaml
        workspace_config = """packages:
  - "apps/*"
  - "packages/*"
"""
        workspace_path = self.root / "pnpm-workspace.yaml"
        workspace_path.write_text(workspace_config)
        files.append(str(workspace_path))

        # .gitignore
        gitignore = """node_modules
dist
.next
.turbo
.nx
*.log
.env*.local
"""
        gitignore_path = self.root / ".gitignore"
        gitignore_path.write_text(gitignore)
        files.append(str(gitignore_path))

        # Apps package.json
        for app in ["web", "docs"]:
            app_pkg = {
                "name": f"@{self.name}/{app}",
                "version": "0.0.0",
                "private": True,
                "scripts": {
                    "dev": "next dev" if app == "web" else "vite",
                    "build": "next build" if app == "web" else "vite build",
                    "lint": "eslint .",
                },
                "dependencies": {
                    f"@{self.name}/ui": "workspace:*",
                    f"@{self.name}/utils": "workspace:*",
                },
            }
            app_pkg_path = self.root / "apps" / app / "package.json"
            app_pkg_path.write_text(json.dumps(app_pkg, indent=2))
            files.append(str(app_pkg_path))

        # Packages
        for pkg in ["ui", "utils"]:
            lib_pkg = {
                "name": f"@{self.name}/{pkg}",
                "version": "0.0.0",
                "main": "./src/index.ts",
                "types": "./src/index.ts",
                "scripts": {"lint": "eslint .", "test": "vitest"},
            }
            lib_pkg_path = self.root / "packages" / pkg / "package.json"
            lib_pkg_path.write_text(json.dumps(lib_pkg, indent=2))
            files.append(str(lib_pkg_path))

            # Index file
            index_path = self.root / "packages" / pkg / "src" / "index.ts"
            index_path.write_text(f"// {pkg} package\nexport const version = '0.0.0';\n")
            files.append(str(index_path))

        return files


def demo_validate() -> None:
    """Demostrar validación de monorepo."""
    logger.info("=== Demo: Validación de Monorepo ===")

    # Crear estructura temporal de ejemplo
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir) / "demo-monorepo"
        root.mkdir()

        # Crear estructura básica
        (root / "apps" / "web" / "src").mkdir(parents=True)
        (root / "packages" / "ui" / "src").mkdir(parents=True)

        # package.json raíz
        (root / "package.json").write_text(
            json.dumps(
                {"name": "demo-monorepo", "private": True, "workspaces": ["apps/*", "packages/*"]}
            )
        )

        # turbo.json
        (root / "turbo.json").write_text(
            json.dumps(
                {
                    "$schema": "https://turbo.build/schema.json",
                    "pipeline": {"build": {"dependsOn": ["^build"]}},
                }
            )
        )

        # Package apps/web
        (root / "apps" / "web" / "package.json").write_text(
            json.dumps(
                {
                    "name": "@demo/web",
                    "version": "1.0.0",
                    "dependencies": {"@demo/ui": "workspace:*"},
                }
            )
        )

        # Package packages/ui
        (root / "packages" / "ui" / "package.json").write_text(
            json.dumps({"name": "@demo/ui", "version": "1.0.0"})
        )

        print(f"\nValidando: {root}")
        print("-" * 60)

        validator = MonorepoValidator(root)
        result = validator.validate()

        print(f"\nResultado: {'✓ VÁLIDO' if result.valid else '✗ INVÁLIDO'}")

        if result.info:
            print("\n📋 Información:")
            for info in result.info:
                print(f"   {info}")

        if result.warnings:
            print("\n⚠️  Warnings:")
            for warning in result.warnings:
                print(f"   {warning}")

        if result.errors:
            print("\n❌ Errores:")
            for error in result.errors:
                print(f"   {error}")


def demo_scaffold() -> None:
    """Demostrar scaffolding de monorepo."""
    logger.info("=== Demo: Scaffolding de Monorepo ===")

    print("\nGenerando estructura de monorepo (simulación)...")
    print("-" * 60)

    # Mostrar estructura que se generaría
    structure = """
my-monorepo/
├── apps/
│   ├── web/
│   │   ├── src/
│   │   └── package.json
│   └── docs/
│       ├── src/
│       └── package.json
├── packages/
│   ├── ui/
│   │   ├── src/
│   │   │   └── index.ts
│   │   └── package.json
│   ├── utils/
│   │   ├── src/
│   │   │   └── index.ts
│   │   └── package.json
│   └── config/
├── turbo.json
├── pnpm-workspace.yaml
├── package.json
└── .gitignore
"""
    print(structure)

    print("Archivos de configuración generados:")
    print("  • turbo.json - Configuración de pipelines")
    print("  • pnpm-workspace.yaml - Definición de workspaces")
    print("  • package.json - Dependencias y scripts raíz")
    print("  • .gitignore - Exclusiones de git")

    print("\nPróximos pasos:")
    print("  1. cd my-monorepo")
    print("  2. pnpm install")
    print("  3. pnpm dev")


def main() -> None:
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Monorepo Patterns - Validator and Scaffold",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
    python monorepo_validator.py --demo validate
    python monorepo_validator.py --demo scaffold
    python monorepo_validator.py --validate /path/to/monorepo
    python monorepo_validator.py --scaffold my-app --tool turborepo
        """,
    )

    parser.add_argument("--demo", choices=["validate", "scaffold", "all"], help="Ejecutar demo")

    parser.add_argument("--validate", type=str, metavar="PATH", help="Validar monorepo existente")

    parser.add_argument("--scaffold", type=str, metavar="NAME", help="Crear nuevo monorepo")

    parser.add_argument(
        "--tool",
        choices=["turborepo", "nx"],
        default="turborepo",
        help="Herramienta de monorepo (default: turborepo)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("         MONOREPO PATTERNS DEMO")
    print("=" * 60)

    if args.validate:
        path = Path(args.validate)
        if not path.exists():
            print(f"Error: {path} no existe")
            return

        validator = MonorepoValidator(path)
        result = validator.validate()
        print(f"\nResultado: {'VÁLIDO' if result.valid else 'INVÁLIDO'}")

    elif args.scaffold:
        print(f"\nPara crear monorepo '{args.scaffold}' con {args.tool}:")
        print(f"  npx create-turbo@latest {args.scaffold}")

    elif args.demo:
        if args.demo in ("validate", "all"):
            demo_validate()
            print()

        if args.demo in ("scaffold", "all"):
            demo_scaffold()

    else:
        demo_validate()
        print()
        demo_scaffold()

    print("\n" + "=" * 60)
    print("Ver SKILL.md para patrones avanzados de Turborepo y Nx.")
    print("=" * 60)


if __name__ == "__main__":
    main()
