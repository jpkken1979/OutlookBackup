#!/usr/bin/env python3
"""
Bun Runtime Helper - Asistente para proyectos Bun.

Funcionalidades:
- Analizar proyecto y sugerir migracion desde Node.js
- Generar configuracion bunfig.toml
- Verificar compatibilidad de dependencias
- Generar server boilerplate

Uso:
    python bun_helper.py analyze ./my-project
    python bun_helper.py migrate ./node-project
    python bun_helper.py generate server
    python bun_helper.py generate test
"""

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class ProjectAnalysis:
    """Resultado del analisis de proyecto."""

    is_node_project: bool
    has_typescript: bool
    package_count: int
    scripts: dict
    can_migrate: bool
    migration_notes: list[str]


class BunHelper:
    """Helper para proyectos Bun."""

    # Paquetes conocidos que no son compatibles
    INCOMPATIBLE_PACKAGES = {
        "node-gyp",  # Native addons
        "fsevents",  # macOS specific
    }

    # Paquetes que tienen alternativas nativas en Bun
    BUN_NATIVE_ALTERNATIVES = {
        "sqlite3": "bun:sqlite",
        "better-sqlite3": "bun:sqlite",
        "bcrypt": "Bun.password",
        "node-fetch": "fetch (nativo)",
        "dotenv": "Bun.env (nativo)",
        "jest": "bun:test",
        "vitest": "bun:test",
        "mocha": "bun:test",
        "webpack": "Bun.build",
        "esbuild": "Bun.build",
        "rollup": "Bun.build",
        "nodemon": "bun --watch",
    }

    def analyze_project(self, path: Path) -> ProjectAnalysis:
        """Analizar proyecto Node.js para migracion a Bun."""
        package_json = path / "package.json"

        if not package_json.exists():
            return ProjectAnalysis(
                is_node_project=False,
                has_typescript=False,
                package_count=0,
                scripts={},
                can_migrate=False,
                migration_notes=["No se encontro package.json"],
            )

        with open(package_json) as f:
            pkg = json.load(f)

        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        scripts = pkg.get("scripts", {})

        # Verificar TypeScript
        has_ts = "typescript" in deps or (path / "tsconfig.json").exists()

        # Notas de migracion
        notes = []

        # Verificar incompatibles
        incompatible = set(deps.keys()) & self.INCOMPATIBLE_PACKAGES
        if incompatible:
            notes.append(f"Paquetes incompatibles: {', '.join(incompatible)}")

        # Sugerir alternativas nativas
        for pkg_name, alternative in self.BUN_NATIVE_ALTERNATIVES.items():
            if pkg_name in deps:
                notes.append(f"Reemplazar {pkg_name} con {alternative}")

        # Verificar scripts
        if "start" in scripts:
            start_cmd = scripts["start"]
            if "node " in start_cmd:
                notes.append("Cambiar 'node' por 'bun' en script start")

        can_migrate = len(incompatible) == 0

        return ProjectAnalysis(
            is_node_project=True,
            has_typescript=has_ts,
            package_count=len(deps),
            scripts=scripts,
            can_migrate=can_migrate,
            migration_notes=notes,
        )

    def generate_bunfig(self, project_path: Path) -> str:
        """Generar bunfig.toml."""
        analysis = self.analyze_project(project_path)

        config = """# bunfig.toml - Configuracion de Bun
# Generado por Antigravity Bun Helper

[install]
# No instalar dependencias opcionales
optional = false

# Registry (por defecto npm)
# registry = "https://registry.npmjs.org"

[run]
# Precargar archivos antes de ejecutar
# preload = ["./src/setup.ts"]

# Watch mode por defecto
# watch = true

[test]
# Configuracion de tests
coverage = true
# preload = ["./test/setup.ts"]

"""

        if analysis.has_typescript:
            config += """[install.scopes]
# Scope personalizado (ejemplo)
# "@myorg" = "https://npm.myorg.com"

"""

        return config

    def generate_server_template(self) -> str:
        """Generar template de servidor Bun."""
        return """// server.ts - Bun HTTP Server
// Generado por Antigravity Bun Helper

const server = Bun.serve({
  port: process.env.PORT || 3000,

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const method = request.method;

    // Logging
    console.log(`${method} ${url.pathname}`);

    // Router simple
    if (url.pathname === "/" && method === "GET") {
      return new Response("Hello from Bun!", {
        headers: { "Content-Type": "text/plain" },
      });
    }

    if (url.pathname === "/api/health" && method === "GET") {
      return Response.json({
        status: "ok",
        runtime: "bun",
        version: Bun.version,
        timestamp: new Date().toISOString(),
      });
    }

    if (url.pathname === "/api/users" && method === "GET") {
      // Ejemplo de respuesta JSON
      return Response.json({
        users: [
          { id: 1, name: "Alice" },
          { id: 2, name: "Bob" },
        ],
      });
    }

    if (url.pathname === "/api/users" && method === "POST") {
      try {
        const body = await request.json();
        // Procesar body...
        return Response.json({ success: true, data: body }, { status: 201 });
      } catch {
        return Response.json({ error: "Invalid JSON" }, { status: 400 });
      }
    }

    // 404 Not Found
    return Response.json({ error: "Not Found" }, { status: 404 });
  },

  // WebSocket upgrade (opcional)
  websocket: {
    message(ws, message) {
      console.log(`WebSocket message: ${message}`);
      ws.send(`Echo: ${message}`);
    },
    open(ws) {
      console.log("WebSocket connected");
    },
    close(ws) {
      console.log("WebSocket disconnected");
    },
  },
});

console.log(`Server running at http://localhost:${server.port}`);
"""

    def generate_test_template(self) -> str:
        """Generar template de tests Bun."""
        return """// example.test.ts - Bun Tests
// Generado por Antigravity Bun Helper

import { expect, test, describe, beforeAll, afterAll } from "bun:test";

describe("Example Test Suite", () => {
  beforeAll(() => {
    // Setup antes de todos los tests
    console.log("Setting up tests...");
  });

  afterAll(() => {
    // Cleanup despues de todos los tests
    console.log("Cleaning up...");
  });

  test("basic assertion", () => {
    expect(2 + 2).toBe(4);
  });

  test("string matching", () => {
    expect("hello world").toContain("world");
  });

  test("array operations", () => {
    const arr = [1, 2, 3];
    expect(arr).toHaveLength(3);
    expect(arr).toContain(2);
  });

  test("object matching", () => {
    const obj = { name: "test", value: 42 };
    expect(obj).toMatchObject({ name: "test" });
    expect(obj.value).toBeGreaterThan(40);
  });

  test("async operation", async () => {
    const result = await Promise.resolve("done");
    expect(result).toBe("done");
  });

  test("fetch request", async () => {
    // Ejemplo de test con fetch
    // const response = await fetch("http://localhost:3000/api/health");
    // expect(response.ok).toBe(true);
    // const data = await response.json();
    // expect(data.status).toBe("ok");
    expect(true).toBe(true);
  });
});

describe("Math operations", () => {
  test("addition", () => {
    expect(1 + 1).toBe(2);
  });

  test("multiplication", () => {
    expect(3 * 4).toBe(12);
  });
});
"""


def main():
    parser = argparse.ArgumentParser(
        description="Bun Runtime Helper - Asistente para proyectos Bun"
    )
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analizar proyecto")
    analyze_parser.add_argument("path", help="Ruta al proyecto")

    # migrate
    migrate_parser = subparsers.add_parser("migrate", help="Sugerir migracion")
    migrate_parser.add_argument("path", help="Ruta al proyecto Node.js")

    # generate
    generate_parser = subparsers.add_parser("generate", help="Generar templates")
    generate_parser.add_argument(
        "type", choices=["server", "test", "config"], help="Tipo de template"
    )
    generate_parser.add_argument("--output", "-o", help="Archivo de salida")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    helper = BunHelper()

    if args.command == "analyze":
        path = Path(args.path)
        analysis = helper.analyze_project(path)

        print("\n=== Analisis de Proyecto ===")
        print(f"Es proyecto Node.js: {'Si' if analysis.is_node_project else 'No'}")
        print(f"Tiene TypeScript: {'Si' if analysis.has_typescript else 'No'}")
        print(f"Dependencias: {analysis.package_count}")
        print(f"Puede migrar a Bun: {'Si' if analysis.can_migrate else 'No'}")

        if analysis.migration_notes:
            print("\nNotas de migracion:")
            for note in analysis.migration_notes:
                print(f"  - {note}")

    elif args.command == "migrate":
        path = Path(args.path)
        analysis = helper.analyze_project(path)

        print("\n=== Guia de Migracion a Bun ===")

        if not analysis.is_node_project:
            print("Este no parece ser un proyecto Node.js")
            return

        print("\n1. Instalar Bun:")
        print("   curl -fsSL https://bun.sh/install | bash")

        print("\n2. Eliminar lockfile existente:")
        print("   rm package-lock.json yarn.lock pnpm-lock.yaml")

        print("\n3. Instalar dependencias con Bun:")
        print("   bun install")

        if analysis.migration_notes:
            print("\n4. Cambios recomendados:")
            for note in analysis.migration_notes:
                print(f"   - {note}")

        print("\n5. Ejecutar proyecto:")
        print("   bun run src/index.ts")

    elif args.command == "generate":
        if args.type == "server":
            content = helper.generate_server_template()
            filename = "server.ts"
        elif args.type == "test":
            content = helper.generate_test_template()
            filename = "example.test.ts"
        elif args.type == "config":
            content = helper.generate_bunfig(Path("."))
            filename = "bunfig.toml"

        if args.output:
            Path(args.output).write_text(content)
            print(f"Generado: {args.output}")
        else:
            print(f"# {filename}")
            print(content)


if __name__ == "__main__":
    main()
