#!/usr/bin/env python3
"""
Tauri Architect - Diseña arquitecturas para aplicaciones de escritorio con Tauri.

Especializado en:
- Estructura de proyectos Tauri
- Comunicación frontend-backend (Commands, Events)
- Patrones de seguridad (CSP, allowlist)
- Distribución multiplataforma

Uso:
    python tauri_architect.py "Diseñar app de notas con sincronización"
    python tauri_architect.py --analyze ./mi-proyecto
    python tauri_architect.py --template file-manager
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("antigravity.agents.tauri-architect")

# Plantillas de arquitectura Tauri
ARCHITECTURE_TEMPLATES = {
    "basic": {
        "name": "Aplicación Básica",
        "description": "Estructura mínima para empezar",
        "structure": {
            "src-tauri": {
                "src": ["main.rs", "lib.rs", "commands.rs"],
                "Cargo.toml": None,
                "tauri.conf.json": None,
                "build.rs": None,
            },
            "src": {
                "App.tsx": None,
                "main.tsx": None,
                "styles": ["global.css"],
            },
            "package.json": None,
            "vite.config.ts": None,
        },
        "features": ["window", "shell", "dialog"],
    },
    "file-manager": {
        "name": "Gestor de Archivos",
        "description": "App para gestionar archivos locales",
        "structure": {
            "src-tauri": {
                "src": [
                    "main.rs",
                    "lib.rs",
                    "commands/mod.rs",
                    "commands/files.rs",
                    "commands/system.rs",
                    "utils/mod.rs",
                    "utils/paths.rs",
                ],
                "Cargo.toml": None,
                "tauri.conf.json": None,
            },
            "src": {
                "components": ["FileTree.tsx", "FileViewer.tsx", "Toolbar.tsx"],
                "hooks": ["useFileSystem.ts", "useWatcher.ts"],
                "stores": ["fileStore.ts"],
                "App.tsx": None,
            },
        },
        "features": ["fs", "path", "dialog", "shell", "window"],
        "permissions": ["fs:read", "fs:write", "path:default", "dialog:open"],
    },
    "notes-sync": {
        "name": "Notas con Sincronización",
        "description": "App de notas con sync cloud",
        "structure": {
            "src-tauri": {
                "src": [
                    "main.rs",
                    "lib.rs",
                    "commands/mod.rs",
                    "commands/notes.rs",
                    "commands/sync.rs",
                    "db/mod.rs",
                    "db/sqlite.rs",
                    "sync/mod.rs",
                    "sync/client.rs",
                ],
            },
            "src": {
                "components": ["NoteList.tsx", "NoteEditor.tsx", "SyncStatus.tsx"],
                "hooks": ["useNotes.ts", "useSync.ts"],
                "stores": ["noteStore.ts", "syncStore.ts"],
            },
        },
        "features": ["fs", "http", "notification", "window"],
        "dependencies": ["rusqlite", "reqwest", "serde_json"],
    },
    "media-player": {
        "name": "Reproductor Multimedia",
        "description": "App para reproducir audio/video",
        "structure": {
            "src-tauri": {
                "src": [
                    "main.rs",
                    "lib.rs",
                    "commands/mod.rs",
                    "commands/media.rs",
                    "commands/playlist.rs",
                    "player/mod.rs",
                    "player/audio.rs",
                ],
            },
            "src": {
                "components": ["Player.tsx", "Playlist.tsx", "Controls.tsx", "Visualizer.tsx"],
                "hooks": ["usePlayer.ts", "usePlaylist.ts", "useMediaKeys.ts"],
            },
        },
        "features": ["window", "shell", "global-shortcut", "notification"],
    },
}

# Patrones de seguridad
SECURITY_PATTERNS = {
    "csp": {
        "name": "Content Security Policy",
        "description": "Política de seguridad de contenido",
        "config": {
            "default-src": "'self'",
            "script-src": "'self'",
            "style-src": "'self' 'unsafe-inline'",
            "img-src": "'self' data: https:",
            "connect-src": "'self' https://api.example.com",
        },
    },
    "allowlist": {
        "name": "Allowlist de APIs",
        "description": "Lista blanca de APIs permitidas",
        "principle": "Mínimo privilegio - solo habilitar lo necesario",
    },
    "ipc": {
        "name": "IPC Seguro",
        "description": "Comunicación segura frontend-backend",
        "patterns": [
            "Validar todos los inputs en commands",
            "No exponer paths absolutos al frontend",
            "Usar tipos fuertemente tipados",
            "Sanitizar outputs antes de enviar",
        ],
    },
}


@dataclass
class ArchitectureAnalysis:
    """Análisis de arquitectura de un proyecto Tauri."""

    project_path: str
    has_tauri_config: bool = False
    has_cargo_toml: bool = False
    rust_files: list[str] = field(default_factory=list)
    frontend_framework: str = "unknown"
    features_enabled: list[str] = field(default_factory=list)
    security_score: int = 0
    recommendations: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


@dataclass
class ArchitecturePlan:
    """Plan de arquitectura para nuevo proyecto."""

    name: str
    description: str
    template: str
    structure: dict
    features: list[str]
    security_config: dict
    build_targets: list[str]
    estimated_setup_time: str


class TauriArchitect:
    """
    Arquitecto especializado en aplicaciones Tauri.

    Capacidades:
    - Diseñar estructuras de proyecto
    - Analizar proyectos existentes
    - Recomendar patrones de seguridad
    - Generar configuraciones
    """

    def __init__(self):
        self.templates = ARCHITECTURE_TEMPLATES
        self.security = SECURITY_PATTERNS

    def analyze_project(self, project_path: Path) -> ArchitectureAnalysis:
        """Analiza un proyecto Tauri existente."""
        analysis = ArchitectureAnalysis(project_path=str(project_path))

        if not project_path.exists():
            analysis.issues.append(f"Proyecto no encontrado: {project_path}")
            return analysis

        # Buscar archivos clave
        tauri_dir = project_path / "src-tauri"
        if tauri_dir.exists():
            analysis.has_tauri_config = (tauri_dir / "tauri.conf.json").exists()
            analysis.has_cargo_toml = (tauri_dir / "Cargo.toml").exists()

            # Listar archivos Rust
            for rust_file in tauri_dir.rglob("*.rs"):
                analysis.rust_files.append(str(rust_file.relative_to(project_path)))

        # Detectar framework frontend
        if (project_path / "package.json").exists():
            try:
                with open(project_path / "package.json") as f:
                    pkg = json.load(f)
                    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                    if "react" in deps:
                        analysis.frontend_framework = "React"
                    elif "vue" in deps:
                        analysis.frontend_framework = "Vue"
                    elif "svelte" in deps:
                        analysis.frontend_framework = "Svelte"
                    elif "@angular/core" in deps:
                        analysis.frontend_framework = "Angular"
            except Exception:
                pass

        # Analizar tauri.conf.json si existe
        tauri_conf = tauri_dir / "tauri.conf.json"
        if tauri_conf.exists():
            try:
                with open(tauri_conf) as f:
                    conf = json.load(f)
                    # Extraer features habilitadas
                    allowlist = conf.get("tauri", {}).get("allowlist", {})
                    for feature, settings in allowlist.items():
                        if isinstance(settings, dict) and settings.get("all"):
                            analysis.features_enabled.append(f"{feature}:all")
                        elif settings is True:
                            analysis.features_enabled.append(feature)
            except Exception:
                pass

        # Calcular score de seguridad
        analysis.security_score = self._calculate_security_score(analysis)

        # Generar recomendaciones
        analysis.recommendations = self._generate_recommendations(analysis)

        return analysis

    def _calculate_security_score(self, analysis: ArchitectureAnalysis) -> int:
        """Calcula score de seguridad (0-100)."""
        score = 50  # Base

        # Penalizar features peligrosas
        dangerous = ["shell:all", "fs:all", "http:all"]
        for feature in analysis.features_enabled:
            if feature in dangerous:
                score -= 15

        # Bonus por buenas prácticas
        if analysis.has_tauri_config:
            score += 10
        if len(analysis.rust_files) > 3:  # Código modularizado
            score += 10

        return max(0, min(100, score))

    def _generate_recommendations(self, analysis: ArchitectureAnalysis) -> list[str]:
        """Genera recomendaciones basadas en el análisis."""
        recs = []

        if not analysis.has_tauri_config:
            recs.append("❌ Falta tauri.conf.json - ejecutar 'npm run tauri init'")

        if "shell:all" in analysis.features_enabled:
            recs.append("⚠️ shell:all es peligroso - usar permisos específicos")

        if "fs:all" in analysis.features_enabled:
            recs.append("⚠️ fs:all es peligroso - limitar a paths específicos")

        if len(analysis.rust_files) == 0:
            recs.append("📁 No se encontraron archivos Rust - verificar src-tauri/src/")

        if len(analysis.rust_files) < 3:
            recs.append("💡 Considerar modularizar el código Rust (commands/, utils/)")

        if analysis.security_score < 70:
            recs.append("🔒 Score de seguridad bajo - revisar allowlist y CSP")

        return recs

    def design_architecture(self, description: str, template: str = "basic") -> ArchitecturePlan:
        """Diseña arquitectura para un nuevo proyecto."""
        base = self.templates.get(template, self.templates["basic"])

        # Ajustar según descripción
        features = list(base.get("features", []))
        if "sync" in description.lower() or "cloud" in description.lower():
            features.extend(["http", "notification"])
        if "archivo" in description.lower() or "file" in description.lower():
            features.extend(["fs", "dialog", "path"])

        # Configuración de seguridad
        security_config = {
            "csp": self.security["csp"]["config"],
            "allowlist": dict.fromkeys(features, True),
        }

        return ArchitecturePlan(
            name=base["name"],
            description=description,
            template=template,
            structure=base["structure"],
            features=list(set(features)),
            security_config=security_config,
            build_targets=["windows", "macos", "linux"],
            estimated_setup_time="30-60 minutos",
        )

    def print_analysis(self, analysis: ArchitectureAnalysis) -> None:
        """Imprime análisis de forma legible."""
        print(f"\n{'=' * 60}")
        print("ANÁLISIS DE ARQUITECTURA TAURI")
        print(f"{'=' * 60}")
        print(f"\n📁 Proyecto: {analysis.project_path}")
        print(f"⚙️  tauri.conf.json: {'✅' if analysis.has_tauri_config else '❌'}")
        print(f"📦 Cargo.toml: {'✅' if analysis.has_cargo_toml else '❌'}")
        print(f"🎨 Frontend: {analysis.frontend_framework}")
        print(f"🔒 Score Seguridad: {analysis.security_score}/100")

        if analysis.features_enabled:
            print("\n📋 Features habilitadas:")
            for f in analysis.features_enabled:
                print(f"   - {f}")

        if analysis.rust_files:
            print(f"\n🦀 Archivos Rust ({len(analysis.rust_files)}):")
            for f in analysis.rust_files[:10]:
                print(f"   - {f}")
            if len(analysis.rust_files) > 10:
                print(f"   ... y {len(analysis.rust_files) - 10} más")

        if analysis.recommendations:
            print("\n💡 Recomendaciones:")
            for rec in analysis.recommendations:
                print(f"   {rec}")

        print(f"\n{'=' * 60}\n")

    def print_plan(self, plan: ArchitecturePlan) -> None:
        """Imprime plan de arquitectura."""
        print(f"\n{'=' * 60}")
        print("PLAN DE ARQUITECTURA TAURI")
        print(f"{'=' * 60}")
        print(f"\n📋 Template: {plan.template} - {plan.name}")
        print(f"📝 Descripción: {plan.description}")
        print(f"⏱️  Setup estimado: {plan.estimated_setup_time}")

        print("\n📁 Estructura:")
        self._print_structure(plan.structure, indent=3)

        print("\n🔧 Features requeridas:")
        for f in plan.features:
            print(f"   - {f}")

        print("\n🎯 Targets de build:")
        for t in plan.build_targets:
            print(f"   - {t}")

        print("\n🔒 Configuración de seguridad:")
        print(f"   CSP: {len(plan.security_config.get('csp', {}))} directivas")

        print(f"\n{'=' * 60}\n")

    def _print_structure(self, structure: dict, indent: int = 0) -> None:
        """Imprime estructura de forma recursiva."""
        for key, value in structure.items():
            prefix = " " * indent
            if isinstance(value, dict):
                print(f"{prefix}📁 {key}/")
                self._print_structure(value, indent + 3)
            elif isinstance(value, list):
                print(f"{prefix}📁 {key}/")
                for item in value:
                    print(f"{prefix}   📄 {item}")
            else:
                print(f"{prefix}📄 {key}")

    def list_templates(self) -> None:
        """Lista plantillas disponibles."""
        print(f"\n{'=' * 60}")
        print("PLANTILLAS DE ARQUITECTURA TAURI")
        print(f"{'=' * 60}\n")

        for key, template in self.templates.items():
            print(f"📦 {key}")
            print(f"   Nombre: {template['name']}")
            print(f"   Descripción: {template['description']}")
            print(f"   Features: {', '.join(template.get('features', []))}")
            print()

        print(f"{'=' * 60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Tauri Architect - Diseña arquitecturas de apps de escritorio"
    )
    parser.add_argument("task", nargs="?", help="Descripción de la app a diseñar")
    parser.add_argument("--analyze", "-a", type=Path, help="Analizar proyecto existente")
    parser.add_argument(
        "--template",
        "-t",
        default="basic",
        help="Template a usar (basic, file-manager, notes-sync, media-player)",
    )
    parser.add_argument(
        "--list-templates", "-l", action="store_true", help="Listar templates disponibles"
    )
    parser.add_argument("--json", "-j", action="store_true", help="Output en JSON")

    args = parser.parse_args()
    architect = TauriArchitect()

    if args.list_templates:
        architect.list_templates()
        return 0

    if args.analyze:
        analysis = architect.analyze_project(args.analyze)
        if args.json:
            print(json.dumps(asdict(analysis), indent=2))
        else:
            architect.print_analysis(analysis)
        return 0

    if not args.task:
        parser.print_help()
        return 1

    plan = architect.design_architecture(args.task, args.template)
    if args.json:
        print(json.dumps(asdict(plan), indent=2))
    else:
        architect.print_plan(plan)

    return 0


if __name__ == "__main__":
    sys.exit(main())
