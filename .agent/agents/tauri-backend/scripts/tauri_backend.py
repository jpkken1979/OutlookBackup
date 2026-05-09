#!/usr/bin/env python3
"""
Tauri Backend - Especialista en desarrollo backend Rust para Tauri.

Especializado en:
- Tauri Commands y su implementación
- Gestión de estado (State management)
- Comunicación IPC (invoke, events)
- Integración con crates de Rust

Uso:
    python tauri_backend.py "Crear command para leer archivos"
    python tauri_backend.py --generate-command read_file
    python tauri_backend.py --analyze ./src-tauri/src/
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("antigravity.agents.tauri-backend")


@dataclass
class CommandDefinition:
    """Definición de un Tauri command."""

    name: str
    description: str
    inputs: list[dict]
    output_type: str
    is_async: bool = True
    needs_state: bool = False
    needs_window: bool = False
    error_handling: str = "Result"


@dataclass
class StateDefinition:
    """Definición de estado de aplicación."""

    name: str
    fields: list[dict]
    is_mutex: bool = True


# Templates de código Rust
COMMAND_TEMPLATES = {
    "basic": """
#[tauri::command]
{async_kw}fn {name}({params}) -> Result<{output}, String> {{
    {body}
}}
""",
    "with_state": """
#[tauri::command]
{async_kw}fn {name}(
    state: tauri::State<'{lifetime}, {state_type}>,
    {params}
) -> Result<{output}, String> {{
    {body}
}}
""",
    "with_window": """
#[tauri::command]
{async_kw}fn {name}(
    window: tauri::Window,
    {params}
) -> Result<{output}, String> {{
    {body}
}}
""",
}

STATE_TEMPLATE = """
use std::sync::Mutex;

pub struct {name} {{
{fields}
}}

impl {name} {{
    pub fn new() -> Self {{
        Self {{
{defaults}
        }}
    }}
}}

impl Default for {name} {{
    fn default() -> Self {{
        Self::new()
    }}
}}
"""

# Patrones comunes de commands
COMMAND_PATTERNS = {
    "file_read": CommandDefinition(
        name="read_file",
        description="Lee contenido de un archivo",
        inputs=[{"name": "path", "type": "String"}],
        output_type="String",
        is_async=True,
    ),
    "file_write": CommandDefinition(
        name="write_file",
        description="Escribe contenido a un archivo",
        inputs=[
            {"name": "path", "type": "String"},
            {"name": "content", "type": "String"},
        ],
        output_type="()",
        is_async=True,
    ),
    "file_list": CommandDefinition(
        name="list_files",
        description="Lista archivos en un directorio",
        inputs=[{"name": "path", "type": "String"}],
        output_type="Vec<FileInfo>",
        is_async=True,
    ),
    "db_query": CommandDefinition(
        name="db_query",
        description="Ejecuta query en base de datos",
        inputs=[{"name": "query", "type": "String"}],
        output_type="Vec<serde_json::Value>",
        is_async=True,
        needs_state=True,
    ),
    "http_get": CommandDefinition(
        name="http_get",
        description="Hace request HTTP GET",
        inputs=[{"name": "url", "type": "String"}],
        output_type="String",
        is_async=True,
    ),
    "get_config": CommandDefinition(
        name="get_config",
        description="Obtiene configuración de la app",
        inputs=[],
        output_type="AppConfig",
        needs_state=True,
    ),
    "show_notification": CommandDefinition(
        name="show_notification",
        description="Muestra notificación del sistema",
        inputs=[
            {"name": "title", "type": "String"},
            {"name": "body", "type": "String"},
        ],
        output_type="()",
        needs_window=True,
    ),
}


class TauriBackend:
    """
    Especialista en desarrollo backend Rust para Tauri.

    Genera:
    - Commands con tipos correctos
    - Estructuras de estado
    - Manejo de errores
    - Código de integración
    """

    def __init__(self):
        self.patterns = COMMAND_PATTERNS

    def generate_command(self, cmd: CommandDefinition) -> str:
        """Genera código Rust para un command."""
        # Determinar template
        if cmd.needs_state:
            template = COMMAND_TEMPLATES["with_state"]
        elif cmd.needs_window:
            template = COMMAND_TEMPLATES["with_window"]
        else:
            template = COMMAND_TEMPLATES["basic"]

        # Preparar parámetros
        params = []
        for inp in cmd.inputs:
            params.append(f"{inp['name']}: {inp['type']}")
        params_str = ", ".join(params)

        # Generar body básico
        body = self._generate_body(cmd)

        # Aplicar template
        code = template.format(
            async_kw="async " if cmd.is_async else "",
            name=cmd.name,
            params=params_str,
            output=cmd.output_type,
            body=body,
            state_type="AppState",
            lifetime="a",
        )

        return code.strip()

    def _generate_body(self, cmd: CommandDefinition) -> str:
        """Genera el body del command."""
        if "file" in cmd.name.lower() and "read" in cmd.name.lower():
            return """let content = tokio::fs::read_to_string(&path)
        .await
        .map_err(|e| e.to_string())?;
    Ok(content)"""

        if "file" in cmd.name.lower() and "write" in cmd.name.lower():
            return """tokio::fs::write(&path, &content)
        .await
        .map_err(|e| e.to_string())?;
    Ok(())"""

        if "list" in cmd.name.lower():
            return """let mut entries = Vec::new();
    let mut dir = tokio::fs::read_dir(&path)
        .await
        .map_err(|e| e.to_string())?;

    while let Some(entry) = dir.next_entry().await.map_err(|e| e.to_string())? {
        entries.push(FileInfo {
            name: entry.file_name().to_string_lossy().to_string(),
            is_dir: entry.file_type().await.map(|t| t.is_dir()).unwrap_or(false),
        });
    }
    Ok(entries)"""

        if "http" in cmd.name.lower():
            return """let response = reqwest::get(&url)
        .await
        .map_err(|e| e.to_string())?
        .text()
        .await
        .map_err(|e| e.to_string())?;
    Ok(response)"""

        if cmd.needs_state:
            return """let data = state.0.lock().unwrap();
    // Acceder a data
    Ok(data.clone())"""

        return """// TODO: Implementar lógica
    Ok(Default::default())"""

    def generate_state(self, state: StateDefinition) -> str:
        """Genera estructura de estado."""
        fields = []
        defaults = []

        for f in state.fields:
            fields.append(f"    pub {f['name']}: {f['type']},")
            defaults.append(f"            {f['name']}: {f.get('default', 'Default::default()')},")

        return STATE_TEMPLATE.format(
            name=state.name,
            fields="\n".join(fields),
            defaults="\n".join(defaults),
        )

    def generate_mod_rs(self, commands: list[str]) -> str:
        """Genera archivo mod.rs para commands."""
        mods = []
        exports = []

        for cmd in commands:
            mod_name = cmd.replace("-", "_")
            mods.append(f"mod {mod_name};")
            exports.append(f"pub use {mod_name}::*;")

        return f"""// Commands module
{chr(10).join(mods)}

{chr(10).join(exports)}

// Register all commands
pub fn get_handlers() -> impl Fn(tauri::Invoke) {{
    tauri::generate_handler![
        {", ".join(commands)}
    ]
}}
"""

    def generate_main_rs(self, state_name: str | None = None) -> str:
        """Genera main.rs básico."""
        state_setup = ""
        if state_name:
            state_setup = f"""
    let app_state = {state_name}::new();
"""
            manage = ".manage(std::sync::Mutex::new(app_state))"
        else:
            manage = ""

        return f"""#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;

fn main() {{
    {state_setup}
    tauri::Builder::default()
        {manage}
        .invoke_handler(commands::get_handlers())
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}}
"""

    def analyze_backend(self, src_path: Path) -> dict:
        """Analiza código backend existente."""
        analysis = {
            "commands": [],
            "states": [],
            "issues": [],
            "recommendations": [],
        }

        if not src_path.exists():
            analysis["issues"].append(f"Path no existe: {src_path}")
            return analysis

        # Buscar archivos Rust
        for rs_file in src_path.rglob("*.rs"):
            content = rs_file.read_text(errors="ignore")

            # Detectar commands
            cmd_matches = re.findall(r"#\[tauri::command\]\s*(?:async\s+)?fn\s+(\w+)", content)
            for cmd in cmd_matches:
                analysis["commands"].append(
                    {
                        "name": cmd,
                        "file": str(rs_file.relative_to(src_path)),
                    }
                )

            # Detectar estados
            state_matches = re.findall(r'tauri::State<[\'"]?\w*[\'"]?,?\s*(\w+)>', content)
            analysis["states"].extend(state_matches)

            # Detectar problemas
            if "unwrap()" in content:
                analysis["issues"].append(
                    f"⚠️ Uso de unwrap() en {rs_file.name} - usar ? o handle errors"
                )

            if "panic!" in content:
                analysis["issues"].append(f"⚠️ panic! en {rs_file.name} - evitar en commands")

        # Generar recomendaciones
        if len(analysis["commands"]) == 0:
            analysis["recommendations"].append(
                "No se encontraron commands - crear en src/commands/"
            )

        if len(analysis["states"]) == 0:
            analysis["recommendations"].append("Considerar usar State para datos compartidos")

        return analysis

    def print_analysis(self, analysis: dict) -> None:
        """Imprime análisis de forma legible."""
        print(f"\n{'=' * 60}")
        print("ANÁLISIS BACKEND TAURI")
        print(f"{'=' * 60}")

        if analysis["commands"]:
            print(f"\n🔧 Commands encontrados ({len(analysis['commands'])}):")
            for cmd in analysis["commands"]:
                print(f"   - {cmd['name']} ({cmd['file']})")

        if analysis["states"]:
            print("\n📦 Estados detectados:")
            for state in set(analysis["states"]):
                print(f"   - {state}")

        if analysis["issues"]:
            print("\n⚠️ Problemas:")
            for issue in analysis["issues"]:
                print(f"   {issue}")

        if analysis["recommendations"]:
            print("\n💡 Recomendaciones:")
            for rec in analysis["recommendations"]:
                print(f"   - {rec}")

        print(f"\n{'=' * 60}\n")

    def list_patterns(self) -> None:
        """Lista patrones de commands disponibles."""
        print(f"\n{'=' * 60}")
        print("PATRONES DE COMMANDS TAURI")
        print(f"{'=' * 60}\n")

        for key, cmd in self.patterns.items():
            inputs = ", ".join(f"{i['name']}: {i['type']}" for i in cmd.inputs)
            async_str = "async " if cmd.is_async else ""
            print(f"📦 {key}")
            print(f"   {async_str}fn {cmd.name}({inputs}) -> {cmd.output_type}")
            print(f"   {cmd.description}")
            if cmd.needs_state:
                print("   🔗 Requiere State")
            if cmd.needs_window:
                print("   🪟 Requiere Window")
            print()

        print(f"{'=' * 60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Tauri Backend - Desarrollo backend Rust para Tauri"
    )
    parser.add_argument("task", nargs="?", help="Descripción del command a crear")
    parser.add_argument("--generate-command", "-g", help="Generar command por nombre de patrón")
    parser.add_argument("--analyze", "-a", type=Path, help="Analizar código backend existente")
    parser.add_argument(
        "--list-patterns", "-l", action="store_true", help="Listar patrones disponibles"
    )
    parser.add_argument("--json", "-j", action="store_true", help="Output en JSON")

    args = parser.parse_args()
    backend = TauriBackend()

    if args.list_patterns:
        backend.list_patterns()
        return 0

    if args.analyze:
        analysis = backend.analyze_backend(args.analyze)
        if args.json:
            print(json.dumps(analysis, indent=2))
        else:
            backend.print_analysis(analysis)
        return 0

    if args.generate_command:
        pattern = backend.patterns.get(args.generate_command)
        if pattern:
            code = backend.generate_command(pattern)
            print(code)
        else:
            print(f"Patrón no encontrado: {args.generate_command}")
            print(f"Disponibles: {', '.join(backend.patterns.keys())}")
            return 1
        return 0

    if args.task:
        # Detectar qué tipo de command crear basado en la descripción
        task_lower = args.task.lower()
        selected = None

        for key, pattern in backend.patterns.items():
            if any(word in task_lower for word in key.split("_")):
                selected = pattern
                break

        if selected:
            code = backend.generate_command(selected)
            print(f"// Command para: {args.task}")
            print(code)
        else:
            # Crear command genérico
            cmd = CommandDefinition(
                name="custom_command",
                description=args.task,
                inputs=[],
                output_type="String",
            )
            code = backend.generate_command(cmd)
            print(f"// Command genérico para: {args.task}")
            print(code)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
