#!/usr/bin/env python3
"""
Tauri Frontend - Especialista en desarrollo frontend para Tauri.

Especializado en:
- Integración con @tauri-apps/api
- Invocación de commands desde frontend
- Manejo de eventos Tauri
- Componentes específicos de desktop

Uso:
    python tauri_frontend.py "Crear componente para listar archivos"
    python tauri_frontend.py --generate-hook useFileSystem
    python tauri_frontend.py --analyze ./src/
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
logger = logging.getLogger("antigravity.agents.tauri-frontend")


@dataclass
class HookDefinition:
    """Definición de un React hook para Tauri."""

    name: str
    description: str
    commands: list[str]
    state: list[dict]
    returns: list[str]


@dataclass
class ComponentDefinition:
    """Definición de un componente React para Tauri."""

    name: str
    description: str
    hooks: list[str]
    props: list[dict]
    tauri_apis: list[str]


# Templates de código TypeScript/React
HOOK_TEMPLATE = """
import {{ useState, useCallback{extra_imports} }} from 'react';
import {{ invoke }} from '@tauri-apps/api/tauri';
{api_imports}

{types}

export function {name}() {{
{state}

{functions}

  return {{
{returns}
  }};
}}
"""

COMPONENT_TEMPLATE = """
import React{extra_imports} from 'react';
{hook_imports}
{api_imports}

interface {name}Props {{
{props}
}}

export function {name}({{ {prop_names} }}: {name}Props) {{
{hook_calls}

  return (
{jsx}
  );
}}
"""

# Patrones de hooks comunes
HOOK_PATTERNS = {
    "useFileSystem": HookDefinition(
        name="useFileSystem",
        description="Hook para operaciones de archivos",
        commands=["read_file", "write_file", "list_files"],
        state=[
            {"name": "files", "type": "FileInfo[]", "default": "[]"},
            {"name": "loading", "type": "boolean", "default": "false"},
            {"name": "error", "type": "string | null", "default": "null"},
        ],
        returns=["files", "loading", "error", "readFile", "writeFile", "listFiles", "refresh"],
    ),
    "useWindow": HookDefinition(
        name="useWindow",
        description="Hook para controlar la ventana",
        commands=[],
        state=[
            {"name": "isMaximized", "type": "boolean", "default": "false"},
            {"name": "isFullscreen", "type": "boolean", "default": "false"},
        ],
        returns=[
            "isMaximized",
            "isFullscreen",
            "minimize",
            "maximize",
            "close",
            "toggleFullscreen",
        ],
    ),
    "useNotification": HookDefinition(
        name="useNotification",
        description="Hook para notificaciones del sistema",
        commands=["show_notification"],
        state=[
            {
                "name": "permission",
                "type": "'granted' | 'denied' | 'default'",
                "default": "'default'",
            },
        ],
        returns=["permission", "requestPermission", "sendNotification"],
    ),
    "useDialog": HookDefinition(
        name="useDialog",
        description="Hook para diálogos nativos",
        commands=[],
        state=[],
        returns=[
            "openFile",
            "openFiles",
            "openDirectory",
            "saveFile",
            "showMessage",
            "showConfirm",
        ],
    ),
    "useStore": HookDefinition(
        name="useStore",
        description="Hook para almacenamiento persistente",
        commands=[],
        state=[
            {"name": "data", "type": "T | null", "default": "null"},
            {"name": "loading", "type": "boolean", "default": "true"},
        ],
        returns=["data", "loading", "set", "get", "remove", "clear"],
    ),
}

# APIs de Tauri disponibles
TAURI_APIS = {
    "window": {
        "import": "import { appWindow } from '@tauri-apps/api/window';",
        "functions": ["minimize", "maximize", "close", "setTitle", "setFullscreen"],
    },
    "dialog": {
        "import": "import { open, save, message, confirm } from '@tauri-apps/api/dialog';",
        "functions": ["open", "save", "message", "confirm"],
    },
    "fs": {
        "import": "import { readTextFile, writeTextFile, readDir } from '@tauri-apps/api/fs';",
        "functions": ["readTextFile", "writeTextFile", "readDir", "createDir", "removeFile"],
    },
    "path": {
        "import": "import { appDataDir, documentDir, homeDir } from '@tauri-apps/api/path';",
        "functions": ["appDataDir", "documentDir", "homeDir", "join"],
    },
    "notification": {
        "import": "import { sendNotification, requestPermission, isPermissionGranted } from '@tauri-apps/api/notification';",
        "functions": ["sendNotification", "requestPermission", "isPermissionGranted"],
    },
    "clipboard": {
        "import": "import { writeText, readText } from '@tauri-apps/api/clipboard';",
        "functions": ["writeText", "readText"],
    },
    "shell": {
        "import": "import { open as shellOpen } from '@tauri-apps/api/shell';",
        "functions": ["open"],
    },
    "store": {
        "import": "import { Store } from 'tauri-plugin-store-api';",
        "functions": ["get", "set", "delete", "clear", "save"],
    },
}


class TauriFrontend:
    """
    Especialista en desarrollo frontend para Tauri.

    Genera:
    - Hooks de React para Tauri APIs
    - Componentes con integración Tauri
    - TypeScript types
    - Código de invocación de commands
    """

    def __init__(self):
        self.hook_patterns = HOOK_PATTERNS
        self.apis = TAURI_APIS

    def generate_hook(self, hook: HookDefinition) -> str:
        """Genera código de hook React."""
        # Imports adicionales
        extra_imports = ", useEffect" if hook.state else ""
        api_imports = []

        # State
        state_lines = []
        for s in hook.state:
            state_lines.append(
                f"  const [{s['name']}, set{s['name'].title()}] = useState<{s['type']}>({s['default']});"
            )

        # Detectar APIs necesarias
        if "window" in hook.name.lower():
            api_imports.append(TAURI_APIS["window"]["import"])
        if "file" in hook.name.lower():
            api_imports.append(TAURI_APIS["fs"]["import"])
        if "dialog" in hook.name.lower():
            api_imports.append(TAURI_APIS["dialog"]["import"])
        if "notification" in hook.name.lower():
            api_imports.append(TAURI_APIS["notification"]["import"])

        # Functions
        functions = self._generate_hook_functions(hook)

        # Returns
        returns_lines = []
        for r in hook.returns:
            returns_lines.append(f"    {r},")

        # Types
        types = self._generate_types(hook)

        return HOOK_TEMPLATE.format(
            name=hook.name,
            extra_imports=extra_imports,
            api_imports="\n".join(api_imports),
            types=types,
            state="\n".join(state_lines),
            functions=functions,
            returns="\n".join(returns_lines),
        )

    def _generate_hook_functions(self, hook: HookDefinition) -> str:
        """Genera funciones del hook."""
        functions = []

        if "file" in hook.name.lower():
            functions.append("""
  const readFile = useCallback(async (path: string): Promise<string> => {
    setLoading(true);
    setError(null);
    try {
      const content = await invoke<string>('read_file', { path });
      return content;
    } catch (e) {
      setError(String(e));
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const writeFile = useCallback(async (path: string, content: string): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      await invoke('write_file', { path, content });
    } catch (e) {
      setError(String(e));
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const listFiles = useCallback(async (path: string): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      const result = await invoke<FileInfo[]>('list_files', { path });
      setFiles(result);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const refresh = useCallback(async (path: string) => {
    await listFiles(path);
  }, [listFiles]);""")

        elif "window" in hook.name.lower():
            functions.append("""
  const minimize = useCallback(async () => {
    await appWindow.minimize();
  }, []);

  const maximize = useCallback(async () => {
    const maximized = await appWindow.isMaximized();
    if (maximized) {
      await appWindow.unmaximize();
    } else {
      await appWindow.maximize();
    }
    setIsMaximized(!maximized);
  }, []);

  const close = useCallback(async () => {
    await appWindow.close();
  }, []);

  const toggleFullscreen = useCallback(async () => {
    const fullscreen = await appWindow.isFullscreen();
    await appWindow.setFullscreen(!fullscreen);
    setIsFullscreen(!fullscreen);
  }, []);""")

        elif "notification" in hook.name.lower():
            functions.append("""
  const checkPermission = useCallback(async () => {
    const granted = await isPermissionGranted();
    setPermission(granted ? 'granted' : 'default');
    return granted;
  }, []);

  const requestPermission = useCallback(async () => {
    const result = await tauri_requestPermission();
    setPermission(result);
    return result === 'granted';
  }, []);

  const sendNotification = useCallback(async (title: string, body?: string) => {
    const granted = await checkPermission();
    if (granted) {
      await tauri_sendNotification({ title, body });
    }
  }, [checkPermission]);""")

        elif "dialog" in hook.name.lower():
            functions.append("""
  const openFile = useCallback(async (options?: OpenDialogOptions) => {
    return await open({ ...options, multiple: false }) as string | null;
  }, []);

  const openFiles = useCallback(async (options?: OpenDialogOptions) => {
    return await open({ ...options, multiple: true }) as string[] | null;
  }, []);

  const openDirectory = useCallback(async (options?: OpenDialogOptions) => {
    return await open({ ...options, directory: true }) as string | null;
  }, []);

  const saveFile = useCallback(async (options?: SaveDialogOptions) => {
    return await save(options);
  }, []);

  const showMessage = useCallback(async (msg: string, title?: string) => {
    await message(msg, { title, type: 'info' });
  }, []);

  const showConfirm = useCallback(async (msg: string, title?: string) => {
    return await confirm(msg, { title });
  }, []);""")

        return "\n".join(functions)

    def _generate_types(self, hook: HookDefinition) -> str:
        """Genera tipos TypeScript."""
        types = []

        if "file" in hook.name.lower():
            types.append("""
interface FileInfo {
  name: string;
  isDir: boolean;
  path?: string;
  size?: number;
  modified?: string;
}""")

        if "dialog" in hook.name.lower():
            types.append("""
interface OpenDialogOptions {
  defaultPath?: string;
  filters?: { name: string; extensions: string[] }[];
  title?: string;
}

interface SaveDialogOptions {
  defaultPath?: string;
  filters?: { name: string; extensions: string[] }[];
  title?: string;
}""")

        return "\n".join(types)

    def generate_component(self, comp: ComponentDefinition) -> str:
        """Genera código de componente React."""
        # Imports
        extra_imports = ""
        hook_imports = []
        api_imports = []

        for hook in comp.hooks:
            hook_imports.append(f"import {{ {hook} }} from '../hooks/{hook}';")

        for api in comp.tauri_apis:
            if api in TAURI_APIS:
                api_imports.append(TAURI_APIS[api]["import"])

        # Props
        props_lines = []
        prop_names = []
        for p in comp.props:
            props_lines.append(f"  {p['name']}: {p['type']};")
            prop_names.append(p["name"])

        # Hook calls
        hook_calls = []
        for hook in comp.hooks:
            hook_calls.append(f"  const {{ /* destructure here */ }} = {hook}();")

        # JSX placeholder
        jsx = f'''    <div className="{comp.name.lower()}">
      <h2>{comp.name}</h2>
      {{/* TODO: Implementar UI */}}
    </div>'''

        return COMPONENT_TEMPLATE.format(
            name=comp.name,
            extra_imports=extra_imports,
            hook_imports="\n".join(hook_imports),
            api_imports="\n".join(api_imports),
            props="\n".join(props_lines) if props_lines else "  // No props",
            prop_names=", ".join(prop_names),
            hook_calls="\n".join(hook_calls),
            jsx=jsx,
        )

    def analyze_frontend(self, src_path: Path) -> dict:
        """Analiza código frontend existente."""
        analysis = {
            "components": [],
            "hooks": [],
            "tauri_imports": [],
            "invoke_calls": [],
            "issues": [],
            "recommendations": [],
        }

        if not src_path.exists():
            analysis["issues"].append(f"Path no existe: {src_path}")
            return analysis

        # Buscar archivos TypeScript/JavaScript
        for ext in ["*.tsx", "*.ts", "*.jsx", "*.js"]:
            for file in src_path.rglob(ext):
                content = file.read_text(errors="ignore")

                # Detectar componentes
                comp_matches = re.findall(r"export\s+(?:default\s+)?function\s+(\w+)", content)
                for comp in comp_matches:
                    if comp[0].isupper():  # Convención de componentes
                        analysis["components"].append(
                            {
                                "name": comp,
                                "file": str(file.relative_to(src_path)),
                            }
                        )

                # Detectar hooks
                hook_matches = re.findall(r"function\s+(use\w+)", content)
                analysis["hooks"].extend(hook_matches)

                # Detectar imports de Tauri
                tauri_imports = re.findall(r"from\s+['\"]@tauri-apps/api/(\w+)['\"]", content)
                analysis["tauri_imports"].extend(tauri_imports)

                # Detectar invoke calls
                invoke_matches = re.findall(r"invoke(?:<[^>]+>)?\(['\"](\w+)['\"]", content)
                analysis["invoke_calls"].extend(invoke_matches)

                # Detectar problemas
                if "any" in content and "// @ts-ignore" not in content:
                    if content.count(": any") > 3:
                        analysis["issues"].append(
                            f"⚠️ Muchos 'any' en {file.name} - tipar correctamente"
                        )

        # Generar recomendaciones
        if not analysis["hooks"]:
            analysis["recommendations"].append(
                "Considerar crear hooks personalizados para Tauri APIs"
            )

        if "window" not in analysis["tauri_imports"] and analysis["components"]:
            analysis["recommendations"].append(
                "Considerar usar @tauri-apps/api/window para control de ventana"
            )

        return analysis

    def print_analysis(self, analysis: dict) -> None:
        """Imprime análisis de forma legible."""
        print(f"\n{'=' * 60}")
        print("ANÁLISIS FRONTEND TAURI")
        print(f"{'=' * 60}")

        if analysis["components"]:
            print(f"\n🧩 Componentes ({len(analysis['components'])}):")
            for comp in analysis["components"][:10]:
                print(f"   - {comp['name']} ({comp['file']})")

        if analysis["hooks"]:
            print("\n🪝 Hooks personalizados:")
            for hook in set(analysis["hooks"]):
                print(f"   - {hook}")

        if analysis["tauri_imports"]:
            print("\n📦 APIs de Tauri usadas:")
            for api in set(analysis["tauri_imports"]):
                print(f"   - @tauri-apps/api/{api}")

        if analysis["invoke_calls"]:
            print("\n⚡ Commands invocados:")
            for cmd in set(analysis["invoke_calls"]):
                print(f"   - {cmd}")

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
        """Lista patrones de hooks disponibles."""
        print(f"\n{'=' * 60}")
        print("PATRONES DE HOOKS TAURI")
        print(f"{'=' * 60}\n")

        for key, hook in self.hook_patterns.items():
            print(f"🪝 {key}")
            print(f"   {hook.description}")
            print(f"   Returns: {', '.join(hook.returns[:5])}...")
            if hook.commands:
                print(f"   Commands: {', '.join(hook.commands)}")
            print()

        print(f"{'=' * 60}\n")


def main():
    parser = argparse.ArgumentParser(description="Tauri Frontend - Desarrollo frontend para Tauri")
    parser.add_argument("task", nargs="?", help="Descripción del componente/hook a crear")
    parser.add_argument("--generate-hook", "-g", help="Generar hook por nombre de patrón")
    parser.add_argument("--analyze", "-a", type=Path, help="Analizar código frontend existente")
    parser.add_argument(
        "--list-patterns", "-l", action="store_true", help="Listar patrones disponibles"
    )
    parser.add_argument("--json", "-j", action="store_true", help="Output en JSON")

    args = parser.parse_args()
    frontend = TauriFrontend()

    if args.list_patterns:
        frontend.list_patterns()
        return 0

    if args.analyze:
        analysis = frontend.analyze_frontend(args.analyze)
        if args.json:
            print(json.dumps(analysis, indent=2))
        else:
            frontend.print_analysis(analysis)
        return 0

    if args.generate_hook:
        pattern = frontend.hook_patterns.get(args.generate_hook)
        if pattern:
            code = frontend.generate_hook(pattern)
            print(code)
        else:
            print(f"Patrón no encontrado: {args.generate_hook}")
            print(f"Disponibles: {', '.join(frontend.hook_patterns.keys())}")
            return 1
        return 0

    if args.task:
        # Detectar qué tipo crear basado en la descripción
        task_lower = args.task.lower()

        if "hook" in task_lower or "use" in task_lower:
            # Crear hook
            for key, pattern in frontend.hook_patterns.items():
                if any(word in task_lower for word in key.lower().split("use")[-1:]):
                    code = frontend.generate_hook(pattern)
                    print(f"// Hook para: {args.task}")
                    print(code)
                    return 0

        # Crear componente genérico
        comp = ComponentDefinition(
            name="CustomComponent",
            description=args.task,
            hooks=[],
            props=[],
            tauri_apis=[],
        )
        code = frontend.generate_component(comp)
        print(f"// Componente para: {args.task}")
        print(code)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
