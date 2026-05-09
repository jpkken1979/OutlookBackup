"""capture-demo.py — Helper script for ce-demo-reel agent.

Provides project detection, preflight checks, and capture functions
for browser reels, terminal recordings, and screenshots.
"""
import json as _json
import logging
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Project type detection
# ---------------------------------------------------------------------------


def detect_project_type(project_root: str | None = None) -> str:
    """Detect project type from filesystem heuristics.

    Args:
        project_root: Path to project root. Defaults to cwd.

    Returns:
        Project type: "frontend", "cli", "backend", "telegram-bot", "desktop", "unknown".
    """
    root = Path(project_root) if project_root else Path.cwd()

    # Desktop (Tauri)
    if (root / "src-tauri").exists() and (root / "Cargo.toml").exists():
        return "desktop"

    # Telegram bot
    if (root / "src").exists():
        src_files = list((root / "src").rglob("*.ts"))
        if any("bot" in f.name.lower() for f in src_files):
            return "telegram-bot"

    # Frontend
    if (root / "package.json").exists() and (root / "src").exists():
        if (root / "vite.config.ts").exists():
            return "frontend"
        if (root / "next.config.js").exists() or (root / "next.config.mjs").exists():
            return "frontend"
        if (root / "src" / "App.tsx").exists() or (root / "src" / "main.tsx").exists():
            return "frontend"
        return "frontend"

    # Python CLI/backend
    if (root / "pyproject.toml").exists() or (root / "setup.py").exists():
        if (root / "src").exists():
            return "backend"
        return "cli"

    # Go CLI
    if (root / "go.mod").exists():
        return "cli"

    # Node CLI
    if (root / "package.json").exists():
        return "cli"

    return "unknown"


# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------


def preflight() -> dict:
    """Run preflight checks for available capture tools.

    Returns:
        dict con herramientas disponibles: {"agent-browser": bool, "asciinema": bool, "vhs": bool}.
    """
    tools = {
        "agent-browser": shutil.which("agent-browser") is not None,
        "asciinema": shutil.which("asciinema") is not None,
        "vhs": shutil.which("vhs") is not None,
        "chrome-devtools": True,  # Available via MCP in Claude Code
    }
    logger.info("Preflight tools: %s", tools)
    return tools


def require_tool(name: str) -> None:
    """Raise if a tool is not available.

    Args:
        name: Nombre del tool a verificar.

    Raises:
        RuntimeError: si el tool no esta disponible.
    """
    available = preflight()
    if not available.get(name, False):
        raise RuntimeError(
            f"Tool '{name}' not found. Install it or use a different capture method.\n"
            f"Available: {[k for k, v in available.items() if v]}"
        )


# ---------------------------------------------------------------------------
# Browser reel capture
# ---------------------------------------------------------------------------


def capture_browser_reel(url: str, output: str, duration: int = 5) -> None:
    """Capture a browser GIF using agent-browser CLI.

    Args:
        url: URL to capture.
        output: Output GIF path.
        duration: Duration in seconds.

    Raises:
        RuntimeError: si agent-browser no esta disponible o falla.
    """
    require_tool("agent-browser")

    output_path = Path(output)
    logger.info("Capturing browser reel: url=%s, output=%s, duration=%d", url, output, duration)

    cmd = [
        "agent-browser",
        "capture",
        "--url", url,
        "--output", str(output_path),
        "--duration", str(duration),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False,
            timeout=duration + 30,
        )
        if result.returncode != 0:
            logger.warning("agent-browser stderr: %s", result.stderr)
            # Fallback: try chrome-devtools MCP if available
            raise RuntimeError(f"agent-browser failed: {result.stderr}")
    except FileNotFoundError:
        raise RuntimeError("agent-browser not found in PATH. Install it or use chrome-devtools MCP.")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"agent-browser timed out after {duration + 30}s")


def capture_screenshot(url: str, output: str) -> None:
    """Capture a single screenshot using agent-browser.

    Args:
        url: URL to capture.
        output: Output PNG path.

    Raises:
        RuntimeError: si agent-browser no esta disponible o falla.
    """
    require_tool("agent-browser")

    output_path = Path(output)
    logger.info("Capturing screenshot: url=%s, output=%s", url, output)

    cmd = [
        "agent-browser",
        "capture",
        "--url", url,
        "--output", str(output_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"agent-browser failed: {result.stderr}")
    except FileNotFoundError:
        raise RuntimeError("agent-browser not found in PATH")
    except subprocess.TimeoutExpired:
        raise RuntimeError("agent-browser timed out")


# ---------------------------------------------------------------------------
# Terminal recording capture
# ---------------------------------------------------------------------------


def capture_terminal_recording(
    command: str,
    output: str,
    duration: int = 10,
) -> None:
    """Capture terminal session using asciinema or vhs.

    Args:
        command: Command or script to record.
        output: Output .cast or .tape path.
        duration: Maximum duration in seconds.

    Raises:
        RuntimeError: si ningun tool de grabacion esta disponible.
    """
    tools = preflight()
    output_path = Path(output)

    # Try asciinema first
    if tools.get("asciinema", False):
        logger.info("Recording terminal with asciinema: %s", command)
        cmd = [
            "asciinema",
            "rec",
            "--max-size", "512KB",
            "--quiet",
            str(output_path),
        ]
        # Run in background, let user interact, then exit
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
        )
        # Execute the actual command
        try:
            subprocess.run(
                shlex.split(command),
                shell=False,
                timeout=duration,
                capture_output=True,
            )
        except subprocess.TimeoutExpired:
            pass
        proc.terminate()
        proc.wait(timeout=5)
        return

    # Try vhs (alternative: generates GIF from .tape script)
    if tools.get("vhs", False):
        logger.info("Recording terminal with vhs: %s", command)
        # vhs uses a .tape file as input, not a live command
        # Fallback: generate a simple tape file and run
        tape_content = (
            f"Output {output_path.with_suffix('.gif')}\n"
            f"Set FontSize 16\n"
            f"Set Width 120\n"
            f"Set Height 30\n"
            f"Type {command}\n"
            f"Enter\n"
            f"Sleep 2s\n"
        )
        tape_path = output_path.with_suffix(".tape")
        tape_path.write_text(tape_content, encoding="utf-8")

        cmd = ["vhs", str(tape_path)]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False,
            timeout=duration + 10,
        )
        if result.returncode != 0:
            raise RuntimeError(f"vhs failed: {result.stderr}")
        return

    raise RuntimeError(
        "No terminal recording tool available. Install asciinema (https://asciinema.org) "
        "or vhs (https://github.com/charmbracelet/vhs)"
    )


# ---------------------------------------------------------------------------
# Upload utilities
# ---------------------------------------------------------------------------


def upload_to_url(file_path: str) -> str:
    """Upload a file and return the public URL.

    Args:
        file_path: Path to file to upload.

    Returns:
        Public URL del archivo subido.

    Raises:
        RuntimeError: si el upload falla.
    """
    path = Path(file_path)
    if not path.exists():
        raise RuntimeError(f"File not found: {file_path}")

    file_size = path.stat().st_size
    logger.info("Uploading %s (%d bytes)", file_path, file_size)

    # Try imgbb (no auth required, 32MB limit)
    try:
        url = _upload_imgbb(str(path))
        if url:
            logger.info("Uploaded to imgbb: %s", url)
            return url
    except Exception as e:
        logger.warning("imgbb upload failed: %s", e)

    # Try 0x0.st (no auth, 512MB limit)
    try:
        url = _upload_0x0_st(str(path))
        if url:
            logger.info("Uploaded to 0x0.st: %s", url)
            return url
    except Exception as e:
        logger.warning("0x0.st upload failed: %s", e)

    # Try tmpfiles.org (no auth, 50MB limit)
    try:
        url = _upload_tmpfiles(str(path))
        if url:
            logger.info("Uploaded to tmpfiles.org: %s", url)
            return url
    except Exception as e:
        logger.warning("tmpfiles.org upload failed: %s", e)

    raise RuntimeError("All upload targets failed")


def _upload_imgbb(file_path: str) -> str | None:
    """Upload to imgbb.com without API key.

    Args:
        file_path: Path to file.

    Returns:
        URL directa de la imagen o None si falla.
    """
    import urllib.request

    try:
        with open(file_path, "rb") as f:
            data = f.read()
    except OSError as e:
        raise RuntimeError(f"Cannot read {file_path}: {e}") from e

    import urllib.parse
    import os

    fields = [
        ("key", os.environ.get("IMGBB_API_KEY", "")),
        ("image", ("", data, "application/octet-stream")),
    ]

    boundary = "----FormBoundary7MA4YWxkTrZu0gW"
    body_parts = []
    for name, (filename, data, mime) in fields:
        body_parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        )
        if isinstance(data, bytes):
            body_parts.append(data)
        else:
            body_parts.append(data.encode("utf-8"))
        body_parts.append(b"\r\n")
    body_parts.append(f"--{boundary}--\r\n".encode())

    body = b"".join(body_parts)

    req = urllib.request.Request(
        "https://api.imgbb.com/1/upload",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        result = _json.loads(resp.read())

    if result.get("data", {}).get("url"):
        return result["data"]["url"]

    return None


def _upload_0x0_st(file_path: str) -> str | None:
    """Upload to 0x0.st.

    Args:
        file_path: Path to file.

    Returns:
        URL directa o None si falla.
    """
    import urllib.request

    with open(file_path, "rb") as f:
        data = f.read()

    req = urllib.request.Request(
        "https://0x0.st",
        data=data,
        headers={"Content-Type": "application/octet-stream"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        url = resp.read().decode("utf-8").strip()

    if url.startswith("http"):
        return url

    return None


def _upload_tmpfiles(file_path: str) -> str | None:
    """Upload to tmpfiles.org.

    Args:
        file_path: Path to file.

    Returns:
        URL directa o None si falla.
    """
    import urllib.request

    with open(file_path, "rb") as f:
        data = f.read()

    req = urllib.request.Request(
        "https://tmpfiles.org/api/v1/upload",
        data=data,
        headers={"Content-Type": "application/octet-stream"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        result = _json.loads(resp.read())

    if result.get("status") == "ok":
        # tmpfiles.org returns a page URL, need to extract the actual file URL
        page_url = result.get("data", {}).get("url", "")
        if page_url:
            # Convert page URL to direct URL
            return page_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")

    return None


# ---------------------------------------------------------------------------
# Main (for testing)
# ---------------------------------------------------------------------------


def main() -> dict:
    """CLI entry point for capture-demo helper script."""
    return {
        "project_type": detect_project_type("."),
        "preflight": preflight(),
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    )

    print(_json.dumps(main(), indent=2))


def main_wrapper():
    """main_wrapper-compatible entry point for capture-demo helper script."""
    return main()
