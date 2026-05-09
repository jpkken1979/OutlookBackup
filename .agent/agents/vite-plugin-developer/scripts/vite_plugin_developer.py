#!/usr/bin/env python3
"""
Vite Plugin Developer - Especialista en desarrollo de plugins para Vite.

Especializado en:
- Hooks de Vite (config, transform, load, etc.)
- Desarrollo de plugins personalizados
- Integración con Rollup plugins
- Testing de plugins

Uso:
    python vite_plugin_developer.py "Plugin para transformar markdown"
    python vite_plugin_developer.py --template transform
    python vite_plugin_developer.py --list-hooks
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("antigravity.agents.vite-plugin-developer")


@dataclass
class HookInfo:
    """Información sobre un hook de Vite."""

    name: str
    description: str
    phase: str  # "build" | "serve" | "both"
    signature: str
    example: str


@dataclass
class PluginTemplate:
    """Template de plugin."""

    name: str
    description: str
    hooks: list[str]
    code: str


# Hooks de Vite
VITE_HOOKS = {
    "config": HookInfo(
        name="config",
        description="Modificar configuración antes de resolver",
        phase="both",
        signature="(config: UserConfig, env: ConfigEnv) => UserConfig | null | void",
        example="""
config(config, { command }) {
  if (command === 'build') {
    config.base = '/prod/';
  }
}""",
    ),
    "configResolved": HookInfo(
        name="configResolved",
        description="Leer configuración final resuelta",
        phase="both",
        signature="(config: ResolvedConfig) => void",
        example="""
configResolved(resolvedConfig) {
  // Guardar referencia a config
  config = resolvedConfig;
}""",
    ),
    "configureServer": HookInfo(
        name="configureServer",
        description="Configurar servidor de desarrollo",
        phase="serve",
        signature="(server: ViteDevServer) => void | (() => void)",
        example="""
configureServer(server) {
  server.middlewares.use((req, res, next) => {
    // Custom middleware
    next();
  });
}""",
    ),
    "transformIndexHtml": HookInfo(
        name="transformIndexHtml",
        description="Transformar index.html",
        phase="both",
        signature="(html: string) => string | HtmlTagDescriptor[]",
        example="""
transformIndexHtml(html) {
  return html.replace(
    /<title>(.*?)<\\/title>/,
    '<title>My App</title>'
  );
}""",
    ),
    "resolveId": HookInfo(
        name="resolveId",
        description="Resolver imports personalizados",
        phase="both",
        signature="(id: string, importer?: string) => string | null",
        example="""
resolveId(id) {
  if (id === 'virtual:my-module') {
    return '\\0virtual:my-module';
  }
}""",
    ),
    "load": HookInfo(
        name="load",
        description="Cargar contenido de módulos virtuales",
        phase="both",
        signature="(id: string) => string | null",
        example="""
load(id) {
  if (id === '\\0virtual:my-module') {
    return 'export const msg = "Hello"';
  }
}""",
    ),
    "transform": HookInfo(
        name="transform",
        description="Transformar código de módulos",
        phase="both",
        signature="(code: string, id: string) => string | { code: string, map?: SourceMap }",
        example="""
transform(code, id) {
  if (id.endsWith('.md')) {
    return `export default ${JSON.stringify(marked(code))}`;
  }
}""",
    ),
    "handleHotUpdate": HookInfo(
        name="handleHotUpdate",
        description="Personalizar HMR",
        phase="serve",
        signature="(ctx: HmrContext) => Module[] | void",
        example="""
handleHotUpdate({ file, server }) {
  if (file.endsWith('.custom')) {
    server.ws.send({ type: 'custom', event: 'update' });
    return [];
  }
}""",
    ),
    "buildStart": HookInfo(
        name="buildStart",
        description="Hook al inicio del build",
        phase="build",
        signature="(options: InputOptions) => void",
        example="""
buildStart() {
  console.log('Build starting...');
}""",
    ),
    "buildEnd": HookInfo(
        name="buildEnd",
        description="Hook al final del build",
        phase="build",
        signature="(error?: Error) => void",
        example="""
buildEnd(error) {
  if (error) {
    console.error('Build failed:', error);
  }
}""",
    ),
    "closeBundle": HookInfo(
        name="closeBundle",
        description="Hook después de escribir bundle",
        phase="build",
        signature="() => void",
        example="""
closeBundle() {
  console.log('Bundle written successfully');
}""",
    ),
}

# Templates de plugins
PLUGIN_TEMPLATES = {
    "basic": PluginTemplate(
        name="Plugin Básico",
        description="Estructura mínima de plugin",
        hooks=["config"],
        code="""
import type { Plugin } from 'vite';

export interface MyPluginOptions {
  // Opciones del plugin
}

export default function myPlugin(options: MyPluginOptions = {}): Plugin {
  return {
    name: 'vite-plugin-my-plugin',

    config(config, { command }) {
      // Modificar configuración
    },
  };
}
""",
    ),
    "transform": PluginTemplate(
        name="Plugin de Transformación",
        description="Transformar archivos específicos",
        hooks=["transform"],
        code="""
import type { Plugin } from 'vite';

export interface TransformOptions {
  include?: string[];
  exclude?: string[];
}

export default function transformPlugin(options: TransformOptions = {}): Plugin {
  const { include = ['**/*.custom'], exclude = [] } = options;

  return {
    name: 'vite-plugin-transform',

    transform(code, id) {
      // Solo procesar archivos que coincidan
      if (!id.match(/\\.custom$/)) {
        return null;
      }

      // Transformar código
      const transformed = processCode(code);

      return {
        code: transformed,
        map: null, // Generar sourcemap si es necesario
      };
    },
  };
}

function processCode(code: string): string {
  // Tu lógica de transformación
  return code;
}
""",
    ),
    "virtual": PluginTemplate(
        name="Plugin de Módulo Virtual",
        description="Crear módulos virtuales",
        hooks=["resolveId", "load"],
        code="""
import type { Plugin } from 'vite';

const VIRTUAL_MODULE_ID = 'virtual:my-module';
const RESOLVED_VIRTUAL_MODULE_ID = '\\0' + VIRTUAL_MODULE_ID;

export interface VirtualModuleOptions {
  content?: Record<string, string>;
}

export default function virtualModule(options: VirtualModuleOptions = {}): Plugin {
  const { content = {} } = options;

  return {
    name: 'vite-plugin-virtual-module',

    resolveId(id) {
      if (id === VIRTUAL_MODULE_ID) {
        return RESOLVED_VIRTUAL_MODULE_ID;
      }
    },

    load(id) {
      if (id === RESOLVED_VIRTUAL_MODULE_ID) {
        return `
          export const data = ${JSON.stringify(content)};
          export default data;
        `;
      }
    },
  };
}
""",
    ),
    "server-middleware": PluginTemplate(
        name="Plugin con Middleware",
        description="Añadir middleware al dev server",
        hooks=["configureServer"],
        code="""
import type { Plugin, ViteDevServer } from 'vite';

export interface MiddlewareOptions {
  path?: string;
}

export default function middlewarePlugin(options: MiddlewareOptions = {}): Plugin {
  const { path = '/api' } = options;

  return {
    name: 'vite-plugin-middleware',

    configureServer(server: ViteDevServer) {
      server.middlewares.use(path, (req, res, next) => {
        // Tu lógica de middleware
        if (req.url === '/health') {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'ok' }));
          return;
        }

        next();
      });
    },
  };
}
""",
    ),
    "html-transform": PluginTemplate(
        name="Plugin de HTML",
        description="Transformar index.html",
        hooks=["transformIndexHtml"],
        code="""
import type { Plugin, HtmlTagDescriptor } from 'vite';

export interface HtmlPluginOptions {
  inject?: {
    tags?: HtmlTagDescriptor[];
  };
}

export default function htmlPlugin(options: HtmlPluginOptions = {}): Plugin {
  return {
    name: 'vite-plugin-html',

    transformIndexHtml(html) {
      const tags: HtmlTagDescriptor[] = options.inject?.tags || [];

      // También puedes modificar el HTML directamente
      html = html.replace(
        '</head>',
        `<meta name="generator" content="My Plugin">\\n</head>`
      );

      return {
        html,
        tags,
      };
    },
  };
}
""",
    ),
    "hmr": PluginTemplate(
        name="Plugin con HMR",
        description="Personalizar Hot Module Replacement",
        hooks=["handleHotUpdate", "configureServer"],
        code="""
import type { Plugin, HmrContext } from 'vite';

export default function hmrPlugin(): Plugin {
  return {
    name: 'vite-plugin-hmr',

    configureServer(server) {
      // Escuchar eventos personalizados
      server.ws.on('my-event', (data) => {
        console.log('Received:', data);
      });
    },

    handleHotUpdate({ file, server, modules }: HmrContext) {
      if (file.endsWith('.custom')) {
        // Enviar evento personalizado al cliente
        server.ws.send({
          type: 'custom',
          event: 'custom-update',
          data: { file },
        });

        // Retornar array vacío para prevenir HMR normal
        return [];
      }

      // Retornar undefined para HMR normal
    },
  };
}
""",
    ),
    "full": PluginTemplate(
        name="Plugin Completo",
        description="Plugin con todos los hooks principales",
        hooks=["config", "configResolved", "configureServer", "transform", "buildEnd"],
        code="""
import type { Plugin, ResolvedConfig, ViteDevServer } from 'vite';

export interface FullPluginOptions {
  debug?: boolean;
}

export default function fullPlugin(options: FullPluginOptions = {}): Plugin {
  let config: ResolvedConfig;
  const { debug = false } = options;

  function log(...args: any[]) {
    if (debug) console.log('[my-plugin]', ...args);
  }

  return {
    name: 'vite-plugin-full',

    // Fase: Configuración
    config(userConfig, { command, mode }) {
      log('Config phase:', { command, mode });
      return {
        // Modificaciones a config
      };
    },

    configResolved(resolvedConfig) {
      config = resolvedConfig;
      log('Config resolved:', config.root);
    },

    // Fase: Servidor de desarrollo
    configureServer(server: ViteDevServer) {
      log('Configuring dev server');

      return () => {
        // Post-hook (después de middlewares internos)
        server.middlewares.use((req, res, next) => {
          log('Request:', req.url);
          next();
        });
      };
    },

    // Fase: Transformación
    transform(code, id) {
      if (!id.includes('node_modules')) {
        log('Transform:', id);
      }
      return null; // No transformar
    },

    // Fase: Build
    buildStart() {
      log('Build starting');
    },

    buildEnd(error) {
      if (error) {
        log('Build error:', error.message);
      } else {
        log('Build completed successfully');
      }
    },

    closeBundle() {
      log('Bundle closed');
    },
  };
}
""",
    ),
}


class VitePluginDeveloper:
    """
    Especialista en desarrollo de plugins para Vite.

    Genera:
    - Código de plugins
    - Documentación de hooks
    - Templates personalizados
    """

    def __init__(self):
        self.hooks = VITE_HOOKS
        self.templates = PLUGIN_TEMPLATES

    def generate_plugin(self, template_name: str) -> str:
        """Genera código de plugin basado en template."""
        template = self.templates.get(template_name, self.templates["basic"])
        return template.code

    def get_hook_info(self, hook_name: str) -> HookInfo | None:
        """Obtiene información de un hook."""
        return self.hooks.get(hook_name)

    def list_hooks(self) -> None:
        """Lista todos los hooks disponibles."""
        print(f"\n{'=' * 60}")
        print("HOOKS DE VITE")
        print(f"{'=' * 60}\n")

        # Agrupar por fase
        phases = {"serve": [], "build": [], "both": []}
        for name, hook in self.hooks.items():
            phases[hook.phase].append((name, hook))

        for phase, hooks in phases.items():
            if not hooks:
                continue

            phase_name = {
                "serve": "🔥 Solo Desarrollo (serve)",
                "build": "📦 Solo Build",
                "both": "🔄 Ambos (serve & build)",
            }[phase]

            print(f"{phase_name}")
            print("-" * 40)

            for name, hook in hooks:
                print(f"  {name}")
                print(f"    {hook.description}")
            print()

        print(f"{'=' * 60}\n")

    def show_hook_example(self, hook_name: str) -> None:
        """Muestra ejemplo de uso de un hook."""
        hook = self.hooks.get(hook_name)
        if not hook:
            print(f"Hook no encontrado: {hook_name}")
            print(f"Disponibles: {', '.join(self.hooks.keys())}")
            return

        print(f"\n{'=' * 60}")
        print(f"HOOK: {hook.name}")
        print(f"{'=' * 60}")
        print(f"\n{hook.description}")
        print(f"\nFase: {hook.phase}")
        print("\nSignature:")
        print(f"  {hook.signature}")
        print("\nEjemplo:")
        print("```typescript")
        print(hook.example)
        print("```")
        print(f"\n{'=' * 60}\n")

    def list_templates(self) -> None:
        """Lista templates disponibles."""
        print(f"\n{'=' * 60}")
        print("TEMPLATES DE PLUGINS VITE")
        print(f"{'=' * 60}\n")

        for key, template in self.templates.items():
            print(f"📦 {key}")
            print(f"   {template.name}")
            print(f"   {template.description}")
            print(f"   Hooks: {', '.join(template.hooks)}")
            print()

        print(f"{'=' * 60}\n")

    def generate_from_description(self, description: str) -> str:
        """Genera plugin basado en descripción."""
        desc_lower = description.lower()

        # Detectar tipo de plugin
        if "transform" in desc_lower or "convertir" in desc_lower:
            return self.generate_plugin("transform")
        elif "virtual" in desc_lower or "módulo" in desc_lower:
            return self.generate_plugin("virtual")
        elif "middleware" in desc_lower or "api" in desc_lower:
            return self.generate_plugin("server-middleware")
        elif "html" in desc_lower:
            return self.generate_plugin("html-transform")
        elif "hmr" in desc_lower or "hot" in desc_lower:
            return self.generate_plugin("hmr")
        elif "completo" in desc_lower or "full" in desc_lower:
            return self.generate_plugin("full")
        else:
            return self.generate_plugin("basic")


def main():
    parser = argparse.ArgumentParser(description="Vite Plugin Developer - Desarrollo de plugins")
    parser.add_argument("task", nargs="?", help="Descripción del plugin a crear")
    parser.add_argument("--template", "-t", help="Usar template específico")
    parser.add_argument("--list-hooks", "-l", action="store_true", help="Listar hooks de Vite")
    parser.add_argument("--hook", "-k", help="Mostrar ejemplo de hook")
    parser.add_argument("--list-templates", action="store_true", help="Listar templates")
    parser.add_argument("--json", "-j", action="store_true", help="Output en JSON")

    args = parser.parse_args()
    dev = VitePluginDeveloper()

    if args.list_hooks:
        dev.list_hooks()
        return 0

    if args.hook:
        dev.show_hook_example(args.hook)
        return 0

    if args.list_templates:
        dev.list_templates()
        return 0

    if args.template:
        code = dev.generate_plugin(args.template)
        print(code)
        return 0

    if args.task:
        code = dev.generate_from_description(args.task)
        print(f"// Plugin para: {args.task}")
        print(code)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
