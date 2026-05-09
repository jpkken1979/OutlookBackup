"""api-tester — Prueba endpoints API y reporta status, latencia y errores."""

from __future__ import annotations

import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from _agent_utils import (  # noqa: E402
    llm_summarize,
    main_wrapper,
)


# Common endpoints to test when a base URL is given
COMMON_ENDPOINTS = [
    "/",
    "/health",
    "/v1/",
    "/v1/health",
    "/api/",
    "/api/health",
    "/docs",
    "/openapi.json",
]


def _extract_url_from_task(task: str) -> str | None:
    """Extract a URL from the task string."""
    match = re.search(r"https?://[^\s\"']+", task)
    return match.group(0).rstrip("/") if match else None


def _detect_urls_from_code(root: Path) -> list[str]:
    """Try to find API URLs in common config files."""
    urls: list[str] = []
    candidates = [
        root / ".env.example",
        root / "start_gateway.py",
        root / "docker-compose.yml",
        root / "docker-compose.yaml",
    ]
    port_pattern = re.compile(r"(?:port|PORT|host|HOST).*?(\d{4,5})")
    url_pattern = re.compile(r"https?://[^\s\"']+")

    for f in candidates:
        if f.exists():
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")[:10000]
                for m in url_pattern.finditer(text):
                    url = m.group(0).rstrip("/")
                    if url not in urls:
                        urls.append(url)
                for m in port_pattern.finditer(text):
                    port = m.group(1)
                    candidate = f"http://127.0.0.1:{port}"
                    if candidate not in urls:
                        urls.append(candidate)
            except OSError:
                pass
    return urls[:5]


def _test_endpoint(url: str, timeout: int = 10) -> dict:
    """Test a single endpoint and return results."""
    result: dict = {
        "url": url,
        "status": None,
        "latency_ms": None,
        "ok": False,
        "content_type": None,
        "cors": None,
        "error": None,
    }
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "api-tester/1.0")
        req.add_header("Origin", "http://localhost")

        start = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency = int((time.time() - start) * 1000)
            result["status"] = resp.status
            result["latency_ms"] = latency
            result["ok"] = 200 <= resp.status < 400
            result["content_type"] = resp.headers.get("Content-Type", "")
            result["cors"] = resp.headers.get("Access-Control-Allow-Origin", "none")
    except urllib.error.HTTPError as e:
        latency = int((time.time() - start) * 1000)
        result["status"] = e.code
        result["latency_ms"] = latency
        result["ok"] = False
        result["error"] = str(e.reason)
    except urllib.error.URLError as e:
        result["error"] = str(e.reason)
    except Exception as e:
        result["error"] = str(e)
    return result


def _format_table(results: list[dict]) -> str:
    """Format results as a readable table."""
    lines = [
        "Endpoint | Status | Latency | Content-Type | CORS | Result",
        "---------|--------|---------|--------------|------|-------",
    ]
    for r in results:
        status = str(r.get("status", "N/A"))
        latency = f"{r['latency_ms']}ms" if r.get("latency_ms") is not None else "N/A"
        ct = (r.get("content_type") or "N/A")[:30]
        cors = (r.get("cors") or "N/A")[:20]
        ok_str = "OK" if r.get("ok") else r.get("error", "ERROR")[:30]
        lines.append(f"{r['url']} | {status} | {latency} | {ct} | {cors} | {ok_str}")
    return "\n".join(lines)


def execute(task: str, root: Path) -> dict:
    """Execute API testing."""
    # Determine base URL(s)
    url = _extract_url_from_task(task)
    if url:
        base_urls = [url]
    else:
        base_urls = _detect_urls_from_code(root)
        if not base_urls:
            return {
                "status": "error",
                "summary": "No se encontró URL para probar. Proporciona una URL en la tarea, ej: 'test http://127.0.0.1:4747'",
                "raw": {"urls_checked": []},
                "llm_used": "none",
            }

    # Test endpoints
    all_results: list[dict] = []
    for base in base_urls:
        base = base.rstrip("/")
        for endpoint in COMMON_ENDPOINTS:
            full_url = base + endpoint if endpoint != "/" else base + "/"
            result = _test_endpoint(full_url)
            all_results.append(result)

    ok_count = sum(1 for r in all_results if r["ok"])
    error_count = sum(1 for r in all_results if r.get("error"))
    avg_latency = 0
    latencies = [r["latency_ms"] for r in all_results if r.get("latency_ms") is not None]
    if latencies:
        avg_latency = sum(latencies) // len(latencies)

    raw_data = {
        "base_urls": base_urls,
        "total_endpoints": len(all_results),
        "ok": ok_count,
        "errors": error_count,
        "avg_latency_ms": avg_latency,
        "results": all_results,
    }

    # LLM summary
    table = _format_table(all_results)
    llm_result = llm_summarize(
        table,
        "Eres un experto en APIs. Analiza estos resultados de prueba de endpoints. "
        "Resume: salud general de la API, endpoints con problemas, latencia anómala, "
        "y recomendaciones. Responde en español, conciso.",
    )

    if llm_result:
        return {"status": "success", "summary": llm_result, "raw": raw_data, "llm_used": "auto"}

    # Fallback
    fallback = (
        f"API Test Results — {ok_count}/{len(all_results)} endpoints OK, "
        f"{error_count} errores, latencia promedio {avg_latency}ms\n\n{table}"
    )
    return {"status": "success", "summary": fallback, "raw": raw_data, "llm_used": "none"}


if __name__ == "__main__":
    main_wrapper("api-tester", execute)
