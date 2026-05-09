#!/usr/bin/env python3
"""
Antigravity Ollama MCP Server
==============================
Servidor MCP para gestión del ciclo de vida de modelos Ollama locales.
Expone herramientas para verificar estado, listar modelos, descargar,
generar texto, chat, embeddings, información detallada y benchmarking.

Tools:
- ollama_status: Estado del servicio Ollama (versión, modelos cargados, memoria)
- ollama_list_models: Listar modelos disponibles localmente
- ollama_pull_model: Descargar un modelo desde el registro de Ollama
- ollama_generate: Generar texto con un modelo local
- ollama_chat: Chat completion con historial de mensajes
- ollama_embeddings: Generar embeddings para texto
- ollama_model_info: Información detallada de un modelo específico
- ollama_benchmark: Benchmark rápido de rendimiento de un modelo

Dependencias: solo stdlib (urllib, json, sys, os, time)
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

# =============================================================================
# CONFIGURACIÓN
# =============================================================================


def _validate_ollama_url(url: str) -> str:
    """Valida que la URL base use HTTP o HTTPS para prevenir SSRF via env var.

    Args:
        url: URL a validar.

    Returns:
        La misma URL si es válida.

    Raises:
        ValueError: Si el scheme no es http o https.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"OLLAMA_BASE_URL tiene scheme invalido '{parsed.scheme}'. "
            "Solo se permiten http:// o https://"
        )
    return url


OLLAMA_BASE_URL: str = _validate_ollama_url(os.environ.get("OLLAMA_HOST", "http://localhost:11434"))

RECOMMENDED_MODELS: dict[str, str] = {
    "general": "llama3.1:8b",
    "code": "codellama:7b",
    "embeddings": "nomic-embed-text",
    "lightweight": "phi3:mini",
    "vision": "llava",
}

# Timeouts en segundos
TIMEOUT_STATUS: int = 10
TIMEOUT_GENERATE: int = 300
TIMEOUT_PULL: int = 600
TIMEOUT_DEFAULT: int = 30


# =============================================================================
# UTILIDADES HTTP
# =============================================================================


def _ollama_get(path: str, timeout: int = TIMEOUT_DEFAULT) -> dict[str, Any]:
    """Realiza una petición GET a la API de Ollama.

    Args:
        path: Ruta relativa de la API (ej: /api/version).
        timeout: Timeout en segundos.

    Returns:
        Diccionario con la respuesta JSON.

    Raises:
        ConnectionError: Si Ollama no está disponible.
        TimeoutError: Si la petición excede el timeout.
    """
    url = f"{OLLAMA_BASE_URL}{path}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise ConnectionError(f"Ollama no disponible en {OLLAMA_BASE_URL}: {e}") from e
    except TimeoutError as e:
        raise TimeoutError(f"Timeout contactando Ollama ({timeout}s)") from e


def _ollama_post(
    path: str,
    data: dict[str, Any],
    timeout: int = TIMEOUT_DEFAULT,
    stream: bool = False,
) -> dict[str, Any] | list[dict[str, Any]]:
    """Realiza una petición POST a la API de Ollama.

    Args:
        path: Ruta relativa de la API.
        data: Cuerpo de la petición.
        timeout: Timeout en segundos.
        stream: Si True, recopila todas las líneas NDJSON y retorna lista.

    Returns:
        Diccionario o lista de diccionarios con la respuesta.

    Raises:
        ConnectionError: Si Ollama no está disponible.
        TimeoutError: Si la petición excede el timeout.
    """
    url = f"{OLLAMA_BASE_URL}{path}"
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if stream:
                lines: list[dict[str, Any]] = []
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if line:
                        lines.append(json.loads(line))
                return lines
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise ConnectionError(f"Ollama no disponible en {OLLAMA_BASE_URL}: {e}") from e
    except TimeoutError as e:
        raise TimeoutError(f"Timeout contactando Ollama ({timeout}s)") from e


def _format_bytes(size_bytes: int | float) -> str:
    """Formatea bytes a unidad legible (KB, MB, GB).

    Args:
        size_bytes: Tamaño en bytes.

    Returns:
        Cadena formateada con unidad apropiada.
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes / (1024**2):.1f} MB"
    else:
        return f"{size_bytes / (1024**3):.2f} GB"


def _error_result(request_id: Any, message: str) -> dict[str, Any]:
    """Genera una respuesta de error MCP estándar.

    Args:
        request_id: ID de la petición JSON-RPC.
        message: Mensaje de error.

    Returns:
        Respuesta JSON-RPC con isError=True.
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": f"Error: {message}"}],
            "isError": True,
        },
    }


def _success_result(request_id: Any, text: str) -> dict[str, Any]:
    """Genera una respuesta exitosa MCP estándar.

    Args:
        request_id: ID de la petición JSON-RPC.
        text: Contenido de la respuesta.

    Returns:
        Respuesta JSON-RPC exitosa.
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {"content": [{"type": "text", "text": text}]},
    }


# =============================================================================
# IMPLEMENTACIÓN DE TOOLS
# =============================================================================


def tool_ollama_status() -> str:
    """Verifica el estado del servicio Ollama, versión y modelos activos."""
    try:
        version_info = _ollama_get("/api/version", timeout=TIMEOUT_STATUS)
    except (ConnectionError, TimeoutError, Exception):
        return json.dumps(
            {
                "status": "stopped",
                "message": f"Ollama no está corriendo en {OLLAMA_BASE_URL}",
                "hint": "Ejecuta 'ollama serve' o instala desde https://ollama.com",
            },
            indent=2,
            ensure_ascii=False,
        )

    result: dict[str, Any] = {
        "status": "running",
        "base_url": OLLAMA_BASE_URL,
        "version": version_info.get("version", "desconocida"),
    }

    try:
        ps_info = _ollama_get("/api/ps", timeout=TIMEOUT_STATUS)
        models_running = ps_info.get("models", [])
        result["active_models"] = []
        for m in models_running:
            model_entry: dict[str, Any] = {
                "name": m.get("name", ""),
                "size": _format_bytes(m.get("size", 0)),
                "processor": m.get("details", {}).get("quantization_level", ""),
            }
            if "size_vram" in m:
                model_entry["vram"] = _format_bytes(m["size_vram"])
            result["active_models"].append(model_entry)
        result["active_model_count"] = len(models_running)
    except Exception:
        result["active_models"] = []
        result["active_model_count"] = 0
        result["ps_error"] = "No se pudo obtener modelos activos"

    return json.dumps(result, indent=2, ensure_ascii=False)


def tool_ollama_list_models() -> str:
    """Lista todos los modelos descargados localmente."""
    try:
        data = _ollama_get("/api/tags", timeout=TIMEOUT_DEFAULT)
    except (ConnectionError, TimeoutError) as e:
        return f"Error: {e}"

    models = data.get("models", [])
    if not models:
        recs = "\n".join(
            f"  - {use}: ollama pull {name}" for use, name in RECOMMENDED_MODELS.items()
        )
        return f"No hay modelos descargados.\n\nModelos recomendados:\n{recs}"

    result_lines: list[str] = [f"Modelos locales ({len(models)}):\n"]
    for m in models:
        name = m.get("name", "desconocido")
        size = _format_bytes(m.get("size", 0))
        modified = m.get("modified_at", "")[:19].replace("T", " ")
        details = m.get("details", {})
        params = details.get("parameter_size", "")
        quant = details.get("quantization_level", "")
        family = details.get("family", "")

        line = f"  {name}"
        meta_parts: list[str] = []
        if params:
            meta_parts.append(params)
        if quant:
            meta_parts.append(quant)
        if family:
            meta_parts.append(family)
        meta_parts.append(size)
        if modified:
            meta_parts.append(f"modificado: {modified}")
        line += f" ({', '.join(meta_parts)})"
        result_lines.append(line)

    return "\n".join(result_lines)


def tool_ollama_pull_model(model: str) -> str:
    """Descarga un modelo desde el registro de Ollama.

    Args:
        model: Nombre del modelo a descargar (ej: llama3.1:8b).
    """
    if not model or not isinstance(model, str) or not model.strip():
        return "Error: se requiere un nombre de modelo válido"

    model = model.strip()
    try:
        lines = _ollama_post(
            "/api/pull",
            {"name": model, "stream": True},
            timeout=TIMEOUT_PULL,
            stream=True,
        )
    except (ConnectionError, TimeoutError) as e:
        return f"Error descargando '{model}': {e}"
    except Exception as e:
        return f"Error inesperado descargando '{model}': {e}"

    if not isinstance(lines, list):
        lines = [lines]

    # Extraer progreso final
    last_status = ""
    error_msg = ""
    for entry in lines:
        if isinstance(entry, dict):
            if "error" in entry:
                error_msg = entry["error"]
            last_status = entry.get("status", last_status)

    if error_msg:
        return f"Error al descargar '{model}': {error_msg}"

    return f"Modelo '{model}' descargado exitosamente. Último estado: {last_status}"


def tool_ollama_generate(
    model: str,
    prompt: str,
    system: str = "",
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """Genera texto con un modelo local de Ollama.

    Args:
        model: Nombre del modelo.
        prompt: Prompt de entrada.
        system: Prompt de sistema opcional.
        temperature: Temperatura de generación (0.0-2.0).
        max_tokens: Máximo de tokens a generar.
    """
    if not model or not prompt:
        return "Error: se requieren 'model' y 'prompt'"

    payload: dict[str, Any] = {
        "model": model.strip(),
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    if system:
        payload["system"] = system

    try:
        resp = _ollama_post("/api/generate", payload, timeout=TIMEOUT_GENERATE)
    except (ConnectionError, TimeoutError) as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error inesperado: {e}"

    if not isinstance(resp, dict):
        return "Error: respuesta inesperada de Ollama"

    if "error" in resp:
        return f"Error de Ollama: {resp['error']}"

    text = resp.get("response", "")
    total_duration = resp.get("total_duration", 0)
    eval_count = resp.get("eval_count", 0)
    eval_duration = resp.get("eval_duration", 1)

    tokens_per_sec = (eval_count / (eval_duration / 1e9)) if eval_duration > 0 else 0
    total_sec = total_duration / 1e9 if total_duration > 0 else 0

    metrics = (
        f"\n\n---\nMétricas: {eval_count} tokens en {total_sec:.1f}s "
        f"({tokens_per_sec:.1f} tokens/s) | modelo: {model}"
    )
    return text + metrics


def tool_ollama_chat(
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2048,
    tools: list[dict[str, Any]] | None = None,
) -> str:
    """Chat completion con historial de mensajes.

    Args:
        model: Nombre del modelo.
        messages: Lista de mensajes con role/content.
        temperature: Temperatura de generación.
        max_tokens: Máximo de tokens.
        tools: Definiciones de herramientas opcionales (formato OpenAI).
    """
    if not model or not messages:
        return "Error: se requieren 'model' y 'messages'"

    payload: dict[str, Any] = {
        "model": model.strip(),
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    if tools:
        payload["tools"] = tools

    try:
        resp = _ollama_post("/api/chat", payload, timeout=TIMEOUT_GENERATE)
    except (ConnectionError, TimeoutError) as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error inesperado: {e}"

    if not isinstance(resp, dict):
        return "Error: respuesta inesperada de Ollama"

    if "error" in resp:
        return f"Error de Ollama: {resp['error']}"

    message = resp.get("message", {})
    content = message.get("content", "")
    tool_calls = message.get("tool_calls", [])

    total_duration = resp.get("total_duration", 0)
    eval_count = resp.get("eval_count", 0)
    eval_duration = resp.get("eval_duration", 1)
    tokens_per_sec = (eval_count / (eval_duration / 1e9)) if eval_duration > 0 else 0
    total_sec = total_duration / 1e9 if total_duration > 0 else 0

    result_parts: list[str] = []
    if content:
        result_parts.append(content)
    if tool_calls:
        result_parts.append(f"\nTool calls: {json.dumps(tool_calls, indent=2, ensure_ascii=False)}")

    result_parts.append(
        f"\n---\nMétricas: {eval_count} tokens en {total_sec:.1f}s "
        f"({tokens_per_sec:.1f} tokens/s) | modelo: {model}"
    )
    return "\n".join(result_parts)


def tool_ollama_embeddings(text: str, model: str = "nomic-embed-text") -> str:
    """Genera embeddings para el texto proporcionado.

    Args:
        text: Texto a vectorizar.
        model: Modelo de embeddings (default: nomic-embed-text).
    """
    if not text:
        return "Error: se requiere 'text'"

    try:
        resp = _ollama_post(
            "/api/embed",
            {"model": model.strip(), "input": text},
            timeout=TIMEOUT_DEFAULT,
        )
    except (ConnectionError, TimeoutError) as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error inesperado: {e}"

    if not isinstance(resp, dict):
        return "Error: respuesta inesperada de Ollama"

    if "error" in resp:
        return f"Error de Ollama: {resp['error']}"

    embeddings = resp.get("embeddings", [])
    if not embeddings:
        return "Error: no se obtuvieron embeddings. Verifica que el modelo esté descargado."

    first_vec = embeddings[0] if isinstance(embeddings[0], list) else embeddings
    dims = len(first_vec)
    preview = first_vec[:5]

    return json.dumps(
        {
            "model": model,
            "dimensions": dims,
            "preview": [round(v, 6) for v in preview],
            "total_vectors": len(embeddings) if isinstance(embeddings[0], list) else 1,
            "embedding": first_vec,
        },
        indent=2,
        ensure_ascii=False,
    )


def tool_ollama_model_info(model: str) -> str:
    """Obtiene información detallada de un modelo específico.

    Args:
        model: Nombre del modelo.
    """
    if not model:
        return "Error: se requiere 'model'"

    try:
        resp = _ollama_post(
            "/api/show",
            {"name": model.strip()},
            timeout=TIMEOUT_DEFAULT,
        )
    except (ConnectionError, TimeoutError) as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error inesperado: {e}"

    if not isinstance(resp, dict):
        return "Error: respuesta inesperada de Ollama"

    if "error" in resp:
        return f"Error de Ollama: {resp['error']}"

    details = resp.get("details", {})
    model_info = resp.get("model_info", {})

    result: dict[str, Any] = {
        "name": model,
        "family": details.get("family", ""),
        "parameter_size": details.get("parameter_size", ""),
        "quantization": details.get("quantization_level", ""),
        "format": details.get("format", ""),
    }

    template = resp.get("template", "")
    if template:
        result["template_preview"] = template[:300] + ("..." if len(template) > 300 else "")

    system = resp.get("system", "")
    if system:
        result["system_prompt"] = system[:300] + ("..." if len(system) > 300 else "")

    license_text = resp.get("license", "")
    if license_text:
        result["license_preview"] = license_text[:200] + ("..." if len(license_text) > 200 else "")

    # Extraer parámetros clave del model_info
    if model_info:
        key_params: dict[str, Any] = {}
        for key in [
            "general.architecture",
            "general.parameter_count",
            "general.context_length",
            "general.embedding_length",
        ]:
            if key in model_info:
                key_params[key] = model_info[key]
        if key_params:
            result["model_parameters"] = key_params

    return json.dumps(result, indent=2, ensure_ascii=False)


def tool_ollama_benchmark(model: str) -> str:
    """Ejecuta un benchmark rápido de rendimiento de un modelo.

    Args:
        model: Nombre del modelo a evaluar.
    """
    if not model:
        return "Error: se requiere 'model'"

    benchmark_prompt = "Explain the concept of recursion in programming in exactly 3 sentences."

    # Medir first token latency y generación completa
    start_time = time.time()
    try:
        resp = _ollama_post(
            "/api/generate",
            {
                "model": model.strip(),
                "prompt": benchmark_prompt,
                "stream": False,
                "options": {"temperature": 0.5, "num_predict": 256},
            },
            timeout=TIMEOUT_GENERATE,
        )
    except (ConnectionError, TimeoutError) as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error inesperado: {e}"

    end_time = time.time()

    if not isinstance(resp, dict):
        return "Error: respuesta inesperada de Ollama"

    if "error" in resp:
        return f"Error de Ollama: {resp['error']}"

    load_duration_ns = resp.get("load_duration", 0)
    prompt_eval_duration_ns = resp.get("prompt_eval_duration", 0)
    eval_duration_ns = resp.get("eval_duration", 1)
    eval_count = resp.get("eval_count", 0)
    prompt_eval_count = resp.get("prompt_eval_count", 0)

    eval_duration_s = eval_duration_ns / 1e9 if eval_duration_ns > 0 else 0.001
    tokens_per_sec = eval_count / eval_duration_s if eval_duration_s > 0 else 0
    first_token_ms = (load_duration_ns + prompt_eval_duration_ns) / 1e6
    total_sec = end_time - start_time

    result: dict[str, Any] = {
        "model": model,
        "benchmark_prompt": benchmark_prompt,
        "results": {
            "first_token_latency_ms": round(first_token_ms, 1),
            "generation_tokens_per_sec": round(tokens_per_sec, 1),
            "total_time_sec": round(total_sec, 2),
            "tokens_generated": eval_count,
            "prompt_tokens_evaluated": prompt_eval_count,
            "model_load_time_ms": round(load_duration_ns / 1e6, 1),
        },
        "response_preview": resp.get("response", "")[:200],
    }

    # Evaluación cualitativa
    if tokens_per_sec >= 30:
        result["rating"] = "excelente (>=30 tok/s)"
    elif tokens_per_sec >= 15:
        result["rating"] = "bueno (>=15 tok/s)"
    elif tokens_per_sec >= 5:
        result["rating"] = "aceptable (>=5 tok/s)"
    else:
        result["rating"] = "lento (<5 tok/s)"

    return json.dumps(result, indent=2, ensure_ascii=False)


# =============================================================================
# DEFINICIÓN DE HERRAMIENTAS MCP
# =============================================================================

TOOLS: list[dict[str, Any]] = [
    {
        "name": "ollama_status",
        "description": "Verificar si Ollama está corriendo, versión, modelos activos y uso de memoria",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ollama_list_models",
        "description": "Listar todos los modelos disponibles localmente con tamaño y metadatos",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ollama_pull_model",
        "description": "Descargar un modelo desde el registro de Ollama",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": (
                        "Nombre del modelo a descargar (ej: llama3.1:8b, codellama:7b, "
                        "nomic-embed-text, phi3:mini, llava)"
                    ),
                },
            },
            "required": ["model"],
        },
    },
    {
        "name": "ollama_generate",
        "description": "Generar texto con un modelo local de Ollama",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Nombre del modelo"},
                "prompt": {"type": "string", "description": "Prompt de entrada"},
                "system": {
                    "type": "string",
                    "description": "Prompt de sistema opcional",
                    "default": "",
                },
                "temperature": {
                    "type": "number",
                    "description": "Temperatura de generación (0.0-2.0)",
                    "default": 0.7,
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Máximo de tokens a generar",
                    "default": 2048,
                },
            },
            "required": ["model", "prompt"],
        },
    },
    {
        "name": "ollama_chat",
        "description": "Chat completion con historial de mensajes y soporte de herramientas",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Nombre del modelo"},
                "messages": {
                    "type": "array",
                    "description": "Lista de mensajes con role y content",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {
                                "type": "string",
                                "enum": ["system", "user", "assistant"],
                            },
                            "content": {"type": "string"},
                        },
                        "required": ["role", "content"],
                    },
                },
                "temperature": {
                    "type": "number",
                    "description": "Temperatura de generación",
                    "default": 0.7,
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Máximo de tokens",
                    "default": 2048,
                },
                "tools": {
                    "type": "array",
                    "description": "Definiciones de herramientas (formato OpenAI)",
                    "items": {"type": "object"},
                },
            },
            "required": ["model", "messages"],
        },
    },
    {
        "name": "ollama_embeddings",
        "description": "Generar embeddings vectoriales para texto",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Texto a vectorizar"},
                "model": {
                    "type": "string",
                    "description": "Modelo de embeddings",
                    "default": "nomic-embed-text",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "ollama_model_info",
        "description": "Obtener información detallada de un modelo (parámetros, template, licencia)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Nombre del modelo"},
            },
            "required": ["model"],
        },
    },
    {
        "name": "ollama_benchmark",
        "description": "Benchmark rápido de un modelo: latencia, tokens/s, tiempo total",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Nombre del modelo a evaluar"},
            },
            "required": ["model"],
        },
    },
]


# =============================================================================
# HANDLER JSON-RPC
# =============================================================================


def handle_request(request: dict[str, Any]) -> dict[str, Any]:
    """Procesa una petición JSON-RPC del protocolo MCP.

    Args:
        request: Petición JSON-RPC entrante.

    Returns:
        Respuesta JSON-RPC.
    """
    method: str = request.get("method", "")
    params: dict[str, Any] = request.get("params", {})
    request_id: Any = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "antigravity-ollama", "version": "1.0.0"},
            },
        }

    # Notifications don't get responses (JSON-RPC 2.0 spec)
    if method and method.startswith("notifications/"):
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        name: str = params.get("name", "")
        args: dict[str, Any] = params.get("arguments", {})

        try:
            if name == "ollama_status":
                result_text = tool_ollama_status()

            elif name == "ollama_list_models":
                result_text = tool_ollama_list_models()

            elif name == "ollama_pull_model":
                model = args.get("model", "")
                if not model:
                    return _error_result(request_id, "Parámetro 'model' requerido")
                result_text = tool_ollama_pull_model(model)

            elif name == "ollama_generate":
                model = args.get("model", "")
                prompt = args.get("prompt", "")
                if not model or not prompt:
                    return _error_result(request_id, "Parámetros 'model' y 'prompt' requeridos")
                result_text = tool_ollama_generate(
                    model=model,
                    prompt=prompt,
                    system=args.get("system", ""),
                    temperature=float(args.get("temperature", 0.7)),
                    max_tokens=int(args.get("max_tokens", 2048)),
                )

            elif name == "ollama_chat":
                model = args.get("model", "")
                messages = args.get("messages", [])
                if not model or not messages:
                    return _error_result(request_id, "Parámetros 'model' y 'messages' requeridos")
                result_text = tool_ollama_chat(
                    model=model,
                    messages=messages,
                    temperature=float(args.get("temperature", 0.7)),
                    max_tokens=int(args.get("max_tokens", 2048)),
                    tools=args.get("tools"),
                )

            elif name == "ollama_embeddings":
                text = args.get("text", "")
                if not text:
                    return _error_result(request_id, "Parámetro 'text' requerido")
                result_text = tool_ollama_embeddings(
                    text=text,
                    model=args.get("model", "nomic-embed-text"),
                )

            elif name == "ollama_model_info":
                model = args.get("model", "")
                if not model:
                    return _error_result(request_id, "Parámetro 'model' requerido")
                result_text = tool_ollama_model_info(model)

            elif name == "ollama_benchmark":
                model = args.get("model", "")
                if not model:
                    return _error_result(request_id, "Parámetro 'model' requerido")
                result_text = tool_ollama_benchmark(model)

            else:
                return _error_result(request_id, f"Herramienta desconocida: {name}")

            return _success_result(request_id, result_text)

        except Exception as e:
            return _error_result(request_id, f"Error interno: {e}")

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": "Method not found"},
    }


# =============================================================================
# PUNTO DE ENTRADA — LOOP STDIO MCP
# =============================================================================

if __name__ == "__main__":
    _empty_count: int = 0
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                _empty_count += 1
                if _empty_count >= 5:
                    break  # EOF persistente — cliente desconectado
                time.sleep(0.2)
                continue
            _empty_count = 0
            request = json.loads(line)
            response = handle_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError:
            continue
        except KeyboardInterrupt:
            break
        except Exception:
            import traceback

            print(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32603, "message": "Internal error"},
                    }
                ),
                flush=True,
            )
            print(traceback.format_exc(), file=sys.stderr, flush=True)
