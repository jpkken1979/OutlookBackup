"""Token generator — exporta design tokens en W3C DTCG 2025.10 + Tailwind v4 config."""
import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TokenGenResult:
    """Resultado de la generación de archivos de tokens.

    Args:
        dtcg_path: Ruta al archivo tokens.json en formato W3C DTCG.
        tailwind_config_path: Ruta al archivo tailwind-tokens.css con @theme.
        merged: True si se hizo merge con tokens existentes.
    """

    dtcg_path: Path
    tailwind_config_path: Path
    merged: bool


def _tokens_to_tailwind_theme(tokens: dict) -> str:
    """Convierte tokens DTCG a bloque @theme de Tailwind v4.

    Args:
        tokens: Design tokens en formato DTCG anidado.

    Returns:
        Bloque CSS @theme con variables CSS generadas.
    """
    lines: list[str] = ["@theme {"]
    for category, group in tokens.items():
        if isinstance(group, dict):
            for name, token in group.items():
                if isinstance(token, dict) and "$value" in token:
                    lines.append(f"  --{category}-{name}: {token['$value']};")
    lines.append("}")
    return "\n".join(lines)


def generate_token_file(tokens: dict, output_dir: Path) -> TokenGenResult:
    """Genera tokens.json (DTCG) y tailwind-tokens.css en el directorio indicado.

    Args:
        tokens: Design tokens en formato DTCG anidado.
        output_dir: Directorio donde guardar los archivos generados.

    Returns:
        TokenGenResult con las rutas generadas y si hubo merge.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    dtcg_path = output_dir / "tokens.json"
    tailwind_path = output_dir / "tailwind-tokens.css"

    merged = False
    existing: dict = {}

    if dtcg_path.exists():
        try:
            existing = json.loads(dtcg_path.read_text(encoding="utf-8"))
            merged = True
        except Exception as exc:
            logger.warning("No se pudo leer tokens existentes en %s: %s", dtcg_path, exc)

    merged_tokens = {**existing, **tokens}

    dtcg_path.write_text(
        json.dumps(merged_tokens, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    tailwind_path.write_text(_tokens_to_tailwind_theme(merged_tokens), encoding="utf-8")

    logger.info("Tokens generados: %s (%s)", dtcg_path, "merge" if merged else "nuevo")
    return TokenGenResult(
        dtcg_path=dtcg_path,
        tailwind_config_path=tailwind_path,
        merged=merged,
    )
