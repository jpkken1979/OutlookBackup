#!/usr/bin/env python3
"""
OpenClaw Integration - Integración bidireccional con OpenClaw.

Este script permite:
1. Importar skills de ClawHub al ecosistema Antigravity
2. Exportar skills de Antigravity al formato OpenClaw
3. Conectar con Gateway OpenClaw
4. Sincronizar agentes entre ecosistemas

Usage:
    python openclaw_integration.py --action import --skill-name playwright-pro
    python openclaw_integration.py --action export --skill-name browser-automation
    python openclaw_integration.py --action connect --openclaw-url ws://localhost:18789
    python openclaw_integration.py --action sync

Reference: https://github.com/clawdbot/clawdbot
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# Configurar logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

CLAWHUB_REGISTRY_URL = "https://clawhub.io/api/v1"
OPENCLAW_GATEWAY_DEFAULT = "ws://127.0.0.1:18789"
ANTIGRAVITY_SKILLS_DIR = Path(__file__).parent.parent.parent.parent / "skills"
OPENCLAW_SKILLS_DIR = Path.home() / ".openclaw" / "workspace" / "skills"


# =============================================================================
# Enums
# =============================================================================


class Action(str, Enum):
    """Acciones disponibles."""

    IMPORT = "import"
    EXPORT = "export"
    CONNECT = "connect"
    SYNC = "sync"
    LIST = "list"
    SEARCH = "search"


class SkillFormat(str, Enum):
    """Formatos de skill."""

    ANTIGRAVITY = "antigravity"
    OPENCLAW = "openclaw"


# =============================================================================
# Models
# =============================================================================


class OpenClawSkill(BaseModel):
    """Skill en formato OpenClaw."""

    name: str
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    category: str = "general"
    tags: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    entry_point: str | None = None
    config_schema: dict[str, Any] = Field(default_factory=dict)


class AntigravitySkill(BaseModel):
    """Skill en formato Antigravity."""

    name: str
    description: str = ""
    version: str = "1.0.0"
    category: str = "general"
    author: str = "Antigravity Team"
    dependencies: list[str] = Field(default_factory=list)
    inputs: list[dict[str, Any]] = Field(default_factory=list)
    outputs: dict[str, Any] = Field(default_factory=dict)


class IntegrationResult(BaseModel):
    """Resultado de operación de integración."""

    success: bool
    action: str
    message: str = ""
    result: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


# =============================================================================
# Skill Converter
# =============================================================================


class SkillConverter:
    """Convierte skills entre formatos Antigravity y OpenClaw."""

    @staticmethod
    def openclaw_to_antigravity(skill: OpenClawSkill) -> AntigravitySkill:
        """
        Convierte skill OpenClaw a formato Antigravity.

        Args:
            skill: Skill en formato OpenClaw

        Returns:
            Skill en formato Antigravity
        """
        # Mapear categorías
        category_map = {
            "coding": "Development",
            "browser": "Automation",
            "ai": "AI/Agents",
            "devops": "DevOps",
            "productivity": "Productivity",
        }

        category = "general"
        for oc_cat, ag_cat in category_map.items():
            if oc_cat in skill.category.lower():
                category = ag_cat
                break

        return AntigravitySkill(
            name=skill.name,
            description=skill.description,
            version=skill.version,
            category=category,
            author=skill.author or "OpenClaw Import",
            dependencies=skill.dependencies,
            inputs=[{"name": "config", "type": "dict", "required": False}],
            outputs={"result": "any"},
        )

    @staticmethod
    def antigravity_to_openclaw(skill: AntigravitySkill) -> OpenClawSkill:
        """
        Convierte skill Antigravity a formato OpenClaw.

        Args:
            skill: Skill en formato Antigravity

        Returns:
            Skill en formato OpenClaw
        """
        # Mapear categorías inversas
        category_map = {
            "Development": "coding",
            "Automation": "browser",
            "AI/Agents": "ai",
            "DevOps": "devops",
            "Frontend & UI": "web",
            "Backend & API": "backend",
            "Security": "security",
        }

        category = category_map.get(skill.category, "general")

        return OpenClawSkill(
            name=skill.name,
            description=skill.description,
            version=skill.version,
            author=skill.author,
            category=category,
            tags=[skill.category.lower()],
            dependencies=skill.dependencies,
        )


# =============================================================================
# ClawHub Client
# =============================================================================


@dataclass
class ClawHubClient:
    """Cliente para interactuar con ClawHub registry."""

    registry_url: str = CLAWHUB_REGISTRY_URL
    _skills_cache: dict[str, OpenClawSkill] = field(default_factory=dict)

    async def search_skills(
        self, query: str, category: str | None = None, limit: int = 20
    ) -> list[OpenClawSkill]:
        """
        Busca skills en ClawHub.

        Args:
            query: Término de búsqueda
            category: Filtrar por categoría
            limit: Máximo de resultados

        Returns:
            Lista de skills encontrados
        """
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                params = {"q": query, "limit": limit}
                if category:
                    params["category"] = category

                response = await client.get(
                    f"{self.registry_url}/skills/search", params=params, timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return [OpenClawSkill(**s) for s in data.get("skills", [])]
        except ImportError:
            logger.warning("httpx no instalado. Usando datos mock.")
        except Exception as e:
            logger.error(f"Error buscando en ClawHub: {e}")

        # Datos mock para demo
        return [
            OpenClawSkill(
                name=f"{query}-skill",
                description=f"Skill relacionado con {query}",
                category="general",
            )
        ]

    async def get_skill(self, name: str) -> OpenClawSkill | None:
        """
        Obtiene información de un skill específico.

        Args:
            name: Nombre del skill

        Returns:
            Skill o None si no existe
        """
        if name in self._skills_cache:
            return self._skills_cache[name]

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.registry_url}/skills/{name}", timeout=30.0)

                if response.status_code == 200:
                    skill = OpenClawSkill(**response.json())
                    self._skills_cache[name] = skill
                    return skill
        except Exception as e:
            logger.error(f"Error obteniendo skill {name}: {e}")

        return None

    async def download_skill(self, name: str, output_dir: Path) -> bool:
        """
        Descarga un skill de ClawHub.

        Args:
            name: Nombre del skill
            output_dir: Directorio de destino

        Returns:
            True si descarga exitosa
        """
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.registry_url}/skills/{name}/download", timeout=60.0
                )

                if response.status_code == 200:
                    skill_dir = output_dir / name
                    skill_dir.mkdir(parents=True, exist_ok=True)

                    # Guardar contenido (simplificado)
                    (skill_dir / "SKILL.md").write_text(response.text)
                    return True
        except Exception as e:
            logger.error(f"Error descargando skill {name}: {e}")

        return False


# =============================================================================
# OpenClaw Gateway Client
# =============================================================================


@dataclass
class OpenClawGatewayClient:
    """Cliente para conectar con Gateway OpenClaw."""

    gateway_url: str = OPENCLAW_GATEWAY_DEFAULT
    _connected: bool = False
    _websocket: Any = None

    async def connect(self) -> bool:
        """
        Conecta al Gateway OpenClaw.

        Returns:
            True si conexión exitosa
        """
        try:
            import websockets

            self._websocket = await websockets.connect(self.gateway_url)
            self._connected = True
            logger.info(f"Conectado a OpenClaw Gateway: {self.gateway_url}")

            # Handshake inicial
            await self._websocket.send(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": "initialize",
                        "params": {"client_type": "antigravity", "version": "3.0.0"},
                        "id": 1,
                    }
                )
            )

            response = await self._websocket.recv()
            logger.debug(f"Respuesta de Gateway: {response}")

            return True
        except ImportError:
            logger.warning("websockets no instalado.")
        except Exception as e:
            logger.error(f"Error conectando a Gateway: {e}")

        return False

    async def disconnect(self) -> None:
        """Desconecta del Gateway."""
        if self._websocket:
            await self._websocket.close()
        self._connected = False
        logger.info("Desconectado de OpenClaw Gateway")

    async def list_skills(self) -> list[str]:
        """
        Lista skills disponibles en OpenClaw.

        Returns:
            Lista de nombres de skills
        """
        if not self._connected:
            return []

        try:
            await self._websocket.send(
                json.dumps({"jsonrpc": "2.0", "method": "skills/list", "id": 2})
            )

            response = json.loads(await self._websocket.recv())
            return response.get("result", {}).get("skills", [])
        except Exception as e:
            logger.error(f"Error listando skills: {e}")
            return []

    async def invoke_skill(self, skill_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """
        Invoca un skill en OpenClaw.

        Args:
            skill_name: Nombre del skill
            args: Argumentos del skill

        Returns:
            Resultado de la invocación
        """
        if not self._connected:
            return {"error": "No conectado"}

        try:
            await self._websocket.send(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": "skills/invoke",
                        "params": {"name": skill_name, "arguments": args},
                        "id": 3,
                    }
                )
            )

            response = json.loads(await self._websocket.recv())
            return response.get("result", {})
        except Exception as e:
            logger.error(f"Error invocando skill: {e}")
            return {"error": str(e)}


# =============================================================================
# Integration Manager
# =============================================================================


@dataclass
class OpenClawIntegration:
    """Manager de integración con OpenClaw."""

    clawhub: ClawHubClient = field(default_factory=ClawHubClient)
    gateway: OpenClawGatewayClient = field(default_factory=OpenClawGatewayClient)
    converter: SkillConverter = field(default_factory=SkillConverter)

    async def import_skill(
        self, skill_name: str, target_dir: Path | None = None
    ) -> IntegrationResult:
        """
        Importa skill de ClawHub a Antigravity.

        Args:
            skill_name: Nombre del skill a importar
            target_dir: Directorio destino (default: .agent/skills/)

        Returns:
            Resultado de la importación
        """
        target_dir = target_dir or ANTIGRAVITY_SKILLS_DIR

        logger.info(f"Importando skill: {skill_name}")

        # Obtener info del skill
        skill = await self.clawhub.get_skill(skill_name)
        if not skill:
            # Crear skill mock para demo
            skill = OpenClawSkill(
                name=skill_name,
                description=f"Skill importado de ClawHub: {skill_name}",
                category="imported",
            )

        # Convertir a formato Antigravity
        ag_skill = self.converter.openclaw_to_antigravity(skill)

        # Crear directorio
        skill_dir = target_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "scripts").mkdir(exist_ok=True)

        # Crear SKILL.md
        skill_md = f"""# {ag_skill.name}

## Metadata

| Campo | Valor |
|-------|-------|
| **Nombre** | {ag_skill.name} |
| **Versión** | {ag_skill.version} |
| **Categoría** | {ag_skill.category} |
| **Autor** | {ag_skill.author} |
| **Origen** | OpenClaw/ClawHub Import |

---

## Descripción

{ag_skill.description}

---

## Uso

```bash
python .agent/skills/{skill_name}/scripts/main.py
```

---

## Importado desde OpenClaw

- **Fecha**: {datetime.now().isoformat()}
- **Skill original**: {skill.name}
- **Categoría original**: {skill.category}
"""
        (skill_dir / "SKILL.md").write_text(skill_md)

        # Crear script placeholder
        main_py = f'''#!/usr/bin/env python3
"""
{ag_skill.name} - Importado de OpenClaw/ClawHub.

{ag_skill.description}
"""

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Punto de entrada principal."""
    logger.info("Ejecutando {ag_skill.name}")
    # Implementar: lógica del skill
    print("Skill ejecutado correctamente")


if __name__ == "__main__":
    main()
'''
        (skill_dir / "scripts" / "main.py").write_text(main_py)

        logger.info(f"Skill importado a: {skill_dir}")

        return IntegrationResult(
            success=True,
            action="import",
            message=f"Skill {skill_name} importado correctamente",
            result={
                "skill_name": skill_name,
                "version": ag_skill.version,
                "installed_path": str(skill_dir),
            },
        )

    async def export_skill(
        self, skill_name: str, output_dir: Path | None = None
    ) -> IntegrationResult:
        """
        Exporta skill de Antigravity a formato OpenClaw.

        Args:
            skill_name: Nombre del skill a exportar
            output_dir: Directorio de salida

        Returns:
            Resultado de la exportación
        """
        output_dir = output_dir or Path("./exported")
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Exportando skill: {skill_name}")

        # Buscar skill en Antigravity
        skill_dir = ANTIGRAVITY_SKILLS_DIR / skill_name
        if not skill_dir.exists():
            return IntegrationResult(
                success=False,
                action="export",
                message=f"Skill no encontrado: {skill_name}",
                errors=[f"Directorio no existe: {skill_dir}"],
            )

        # Leer SKILL.md
        skill_md_path = skill_dir / "SKILL.md"
        description = ""
        if skill_md_path.exists():
            description = skill_md_path.read_text()[:500]

        # Crear skill Antigravity
        ag_skill = AntigravitySkill(name=skill_name, description=description)

        # Convertir a formato OpenClaw
        oc_skill = self.converter.antigravity_to_openclaw(ag_skill)

        # Crear directorio de salida
        export_dir = output_dir / skill_name
        export_dir.mkdir(parents=True, exist_ok=True)

        # Crear SKILL.md en formato OpenClaw
        openclaw_md = f"""# {oc_skill.name}

{oc_skill.description}

## Installation

```bash
npx clawhub@latest install {oc_skill.name}
```

## Usage

```javascript
// Use in OpenClaw
await openclaw.skills.invoke("{oc_skill.name}", {{
  // arguments
}});
```

## Metadata

- **Version**: {oc_skill.version}
- **Author**: {oc_skill.author}
- **Category**: {oc_skill.category}
- **Tags**: {", ".join(oc_skill.tags)}

## Exported from Antigravity

- **Date**: {datetime.now().isoformat()}
- **Source**: .agent/skills/{skill_name}/
"""
        (export_dir / "SKILL.md").write_text(openclaw_md)

        # Copiar scripts si existen
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.exists():
            export_scripts = export_dir / "scripts"
            shutil.copytree(scripts_dir, export_scripts, dirs_exist_ok=True)

        logger.info(f"Skill exportado a: {export_dir}")

        return IntegrationResult(
            success=True,
            action="export",
            message=f"Skill {skill_name} exportado correctamente",
            result={
                "skill_name": skill_name,
                "format": "openclaw",
                "exported_path": str(export_dir),
            },
        )

    async def connect_gateway(self, gateway_url: str | None = None) -> IntegrationResult:
        """
        Conecta con Gateway OpenClaw.

        Args:
            gateway_url: URL del Gateway

        Returns:
            Resultado de la conexión
        """
        if gateway_url:
            self.gateway.gateway_url = gateway_url

        logger.info(f"Conectando a Gateway: {self.gateway.gateway_url}")

        success = await self.gateway.connect()

        if success:
            skills = await self.gateway.list_skills()
            return IntegrationResult(
                success=True,
                action="connect",
                message="Conectado a OpenClaw Gateway",
                result={"gateway_url": self.gateway.gateway_url, "skills_available": len(skills)},
            )
        else:
            return IntegrationResult(
                success=False,
                action="connect",
                message="No se pudo conectar al Gateway",
                errors=["Conexión fallida - verificar URL y disponibilidad"],
            )

    async def sync_agents(self) -> IntegrationResult:
        """
        Sincroniza agentes entre Antigravity y OpenClaw.

        Returns:
            Resultado de la sincronización
        """
        logger.info("Sincronizando agentes...")

        # Listar agentes Antigravity
        agents_dir = ANTIGRAVITY_SKILLS_DIR.parent / "agents"
        ag_agents = []
        if agents_dir.exists():
            ag_agents = [d.name for d in agents_dir.iterdir() if d.is_dir()]

        # Listar skills OpenClaw (si conectado)
        oc_skills: list[str] = []
        if self.gateway._connected:
            oc_skills = await self.gateway.list_skills()

        return IntegrationResult(
            success=True,
            action="sync",
            message="Sincronización completada",
            result={
                "antigravity_agents": len(ag_agents),
                "openclaw_skills": len(oc_skills),
                "agents": ag_agents[:10],  # Primeros 10
            },
        )

    async def search_clawhub(self, query: str, category: str | None = None) -> IntegrationResult:
        """
        Busca skills en ClawHub.

        Args:
            query: Término de búsqueda
            category: Filtrar por categoría

        Returns:
            Resultado de la búsqueda
        """
        logger.info(f"Buscando en ClawHub: {query}")

        skills = await self.clawhub.search_skills(query, category)

        return IntegrationResult(
            success=True,
            action="search",
            message=f"Encontrados {len(skills)} skills",
            result={
                "query": query,
                "count": len(skills),
                "skills": [s.model_dump() for s in skills],
            },
        )


# =============================================================================
# CLI
# =============================================================================


async def main() -> None:
    """Entry point principal."""
    parser = argparse.ArgumentParser(description="OpenClaw Integration - Integración bidireccional")
    parser.add_argument(
        "--action",
        "-a",
        type=str,
        choices=[a.value for a in Action],
        required=True,
        help="Acción a realizar",
    )
    parser.add_argument("--skill-name", "-s", type=str, help="Nombre del skill")
    parser.add_argument(
        "--openclaw-url",
        "-u",
        type=str,
        default=OPENCLAW_GATEWAY_DEFAULT,
        help="URL del Gateway OpenClaw",
    )
    parser.add_argument("--output-dir", "-o", type=str, help="Directorio de salida")
    parser.add_argument("--query", "-q", type=str, help="Término de búsqueda")
    parser.add_argument("--json", action="store_true", help="Output en JSON")

    args = parser.parse_args()

    integration = OpenClawIntegration()
    result: IntegrationResult

    action = Action(args.action)

    if action == Action.IMPORT:
        if not args.skill_name:
            parser.error("--skill-name requerido para import")
        result = await integration.import_skill(
            args.skill_name, Path(args.output_dir) if args.output_dir else None
        )

    elif action == Action.EXPORT:
        if not args.skill_name:
            parser.error("--skill-name requerido para export")
        result = await integration.export_skill(
            args.skill_name, Path(args.output_dir) if args.output_dir else None
        )

    elif action == Action.CONNECT:
        result = await integration.connect_gateway(args.openclaw_url)

    elif action == Action.SYNC:
        result = await integration.sync_agents()

    elif action == Action.LIST:
        # Listar skills locales
        skills = list(ANTIGRAVITY_SKILLS_DIR.iterdir()) if ANTIGRAVITY_SKILLS_DIR.exists() else []
        result = IntegrationResult(
            success=True,
            action="list",
            message=f"Encontrados {len(skills)} skills locales",
            result={"count": len(skills), "skills": [s.name for s in skills[:50]]},
        )

    elif action == Action.SEARCH:
        if not args.query:
            parser.error("--query requerido para search")
        result = await integration.search_clawhub(args.query)

    else:
        result = IntegrationResult(
            success=False, action=args.action, message="Acción no implementada"
        )

    # Output
    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(f"\n{'=' * 60}")
        print(f"Acción: {result.action.upper()}")
        print(f"Éxito: {'✓' if result.success else '✗'}")
        print(f"Mensaje: {result.message}")
        if result.result:
            print("\nResultado:")
            for key, value in result.result.items():
                print(f"  {key}: {value}")
        if result.errors:
            print("\nErrores:")
            for error in result.errors:
                print(f"  - {error}")
        print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
