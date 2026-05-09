"""ce-demo-reel agent entry point.

Visual evidence capture agent that records GIFs, terminal sessions,
and screenshots for PR descriptions.
"""
import json
import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


CaptureTier = str  # "browser-reel" | "terminal-recording" | "screenshot-reel" | "static-screenshot" | "no-evidence"
ProjectType = str  # "frontend" | "cli" | "backend" | "telegram-bot" | "desktop" | "unknown"


def parse_input(input_str: str) -> dict:
    """Parse agent input string into parameters.

    Args:
        input_str: Input string with format "url=<url> [tier=<tier>] [duration=<seconds>]"

    Returns:
        dict con los parametros extraidos.
    """
    params = {
        "url": "",
        "tier": "auto",  # auto = detect automatically
        "duration": 5,
        "output": "demo",
        "confirm": False,
    }

    for part in input_str.split():
        if part.startswith("url="):
            params["url"] = part[4:]
        elif part.startswith("tier="):
            params["tier"] = part[5:]
        elif part.startswith("duration="):
            params["duration"] = int(part[9:])
        elif part.startswith("output="):
            params["output"] = part[7:]
        elif part == "confirm":
            params["confirm"] = True

    return params


def detect_project_type(project_root: str | None = None) -> ProjectType:
    """Detect the project type from the filesystem.

    Args:
        project_root: Path to project root. Defaults to current directory.

    Returns:
        ProjectType detected.
    """
    logger.info("Detecting project type from: %s", project_root)

    try:
        from scripts.capture_demo import detect_project_type as _detect

        return _detect(project_root)
    except ImportError:
        # Fallback when running standalone
        import scripts.capture_demo as cd_module

        return cd_module.detect_project_type(project_root)


def detect_change_type(project_type: ProjectType, change_description: str) -> CaptureTier:
    """Detect the optimal capture tier based on project and change type.

    Args:
        project_type: Type of project detected.
        change_description: Description of the changes to capture.

    Returns:
        CaptureTier recomendado.
    """
    logger.info("Detecting change type for project %s: %s", project_type, change_description)

    desc_lower = change_description.lower()
    motion_keywords = ["anim", "transition", "hover", "effect", "motion", "gif"]
    cli_keywords = ["cli", "command", "terminal", "console", "script"]
    state_keywords = ["state", "screen", "page", "view", "ui", "component"]
    no_viz_keywords = ["api", "model", "backend", "db", "database", "refactor", "config"]

    # Check no-evidence first
    if all(k in desc_lower for k in no_viz_keywords):
        return "no-evidence"

    # CLI projects
    if project_type in ("cli", "telegram-bot"):
        if any(k in desc_lower for k in cli_keywords):
            return "terminal-recording"
        return "terminal-recording"

    # Frontend projects
    if project_type in ("frontend", "desktop"):
        if any(k in desc_lower for k in motion_keywords):
            return "browser-reel"
        if any(k in desc_lower for k in state_keywords):
            return "screenshot-reel"
        return "browser-reel"  # default for frontend

    # Backend
    if project_type == "backend":
        if any(k in desc_lower for k in cli_keywords):
            return "terminal-recording"
        return "no-evidence"

    return "no-evidence"


def recommend_tier(project_type: ProjectType, change_type: CaptureTier) -> str:
    """Build recommendation message.

    Args:
        project_type: Detected project type.
        change_type: Recommended capture tier.

    Returns:
        str de recomendación para el usuario.
    """
    tier_descriptions = {
        "browser-reel": "GIF animado del browser (agent-browser CLI)",
        "terminal-recording": "Grabación de terminal (asciinema o vhs)",
        "screenshot-reel": "Secuencia de screenshots estáticos",
        "static-screenshot": "Screenshot individual",
        "no-evidence": "Sin captura visual (cambios backend/API)",
    }

    return (
        f"Project type: {project_type}\n"
        f"Recommended tier: {change_type}\n"
        f"Tool: {tier_descriptions.get(change_type, 'N/A')}\n"
    )


def execute_capture(
    tier: CaptureTier,
    url: str,
    duration: int,
    output: str,
) -> dict:
    """Execute the visual capture.

    Args:
        tier: Capture tier to execute.
        url: URL or command to capture.
        duration: Duration in seconds.
        output: Output filename prefix.

    Returns:
        dict con resultado de la captura.
    """
    logger.info("Executing capture: tier=%s, url=%s, duration=%d", tier, url, duration)

    try:
        from scripts.capture_demo import (
            capture_browser_reel,
            capture_terminal_recording,
            capture_screenshot,
            upload_to_url,
        )

        output_path = Path(output)
        result: dict = {"status": "completed", "tier": tier}

        if tier == "browser-reel":
            gif_path = output_path.with_suffix(".gif")
            capture_browser_reel(url, str(gif_path), duration)
            result["file"] = str(gif_path)
            result["url"] = upload_to_url(gif_path)

        elif tier == "terminal-recording":
            cast_path = output_path.with_suffix(".cast")
            capture_terminal_recording(url, str(cast_path), duration)
            result["file"] = str(cast_path)
            result["url"] = upload_to_url(cast_path)

        elif tier in ("screenshot-reel", "static-screenshot"):
            png_path = output_path.with_suffix(".png")
            capture_screenshot(url, str(png_path))
            result["file"] = str(png_path)
            result["url"] = upload_to_url(png_path)

        elif tier == "no-evidence":
            result["status"] = "skipped"
            result["reason"] = "no-evidence tier selected"

        return result

    except ImportError as e:
        logger.warning("capture_demo script not available: %s", e)
        return {"status": "failed", "error": f"capture script unavailable: {e}"}
    except Exception as e:
        logger.error("Capture failed: %s", str(e))
        return {"status": "failed", "error": str(e)}


def generate_markdown(result: dict, tier: CaptureTier) -> str:
    """Generate markdown embeddable for PR.

    Args:
        result: Result from execute_capture.
        tier: Capture tier used.

    Returns:
        Markdown string para copiar en PR.
    """
    if result["status"] == "skipped":
        return "## Demo\n\nNo se requiere evidencia visual para este cambio.\n"

    if result["status"] == "failed":
        return f"## Demo\n\n**Error en captura**: {result.get('error', 'unknown')}\n"

    url = result.get("url", "")

    if tier == "terminal-recording":
        cast_name = Path(result["file"]).name
        return (
            f"## Demo\n\n"
            f"[Ver grabación de terminal]({url})\n"
            f"<!-- asciinema: {cast_name} -->\n"
        )

    # browser-reel, screenshot-reel, static-screenshot
    return f"## Demo\n\n![]({url})\n"


def run(input_str: str) -> dict:
    """Run ce-demo-reel capture operation.

    Args:
        input_str: Parametros de captura.
            Format: "url=<url> [tier=<tier>] [duration=<seconds>] [output=<name>]"

    Returns:
        dict con resultado de captura.
    """
    logger.info("Starting ce-demo-reel capture")
    logger.info("Input: %s", input_str)

    params = parse_input(input_str)
    url = params["url"]
    tier = params["tier"]
    duration = params["duration"]
    output = params["output"]

    # Step 1: Detect project type if tier is auto
    if tier == "auto":
        project_type = detect_project_type()
        change_desc = input_str  # Use the full input as change description hint
        tier = detect_change_type(project_type, change_desc)
        logger.info("Detected project_type=%s, auto-tier=%s", project_type, tier)
    else:
        project_type = detect_project_type()

    # Step 2: Build recommendation
    recommendation = recommend_tier(project_type, tier)
    logger.info("Recommendation: %s", recommendation)

    # Step 3: Execute capture
    result = execute_capture(tier, url, duration, output)
    result["tier"] = tier
    result["recommendation"] = recommendation
    result["markdown"] = generate_markdown(result, tier)

    logger.info("Capture result: status=%s", result["status"])

    return result


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    )
    input_data = sys.argv[1] if len(sys.argv) > 1 else ""
    result = run(input_data)
    print(json.dumps(result, indent=2, default=str))
