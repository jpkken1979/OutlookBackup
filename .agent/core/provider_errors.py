"""Clasificacion fina de errores upstream de providers IA (proxy claudeproxy).

El proxy (`gateway/_mixin_proxy.py`) manejaba los errores upstream con una
politica binaria: streak de fallos -> circuito -> failover. Este modulo agrega
una clasificacion por CATEGORIA (status + cuerpo del error) para que el proxy
pueda decidir una accion distinta segun el tipo de fallo real:

- ``terminal_quota``: cuota/billing agotados de forma permanente (402, o 403/429
  con mensaje explicito de cuota/billing). No tiene sentido reintentar contra el
  mismo provider — hay que rotar o esperar el reset del plan.
- ``rate_limit``: 429 transitorio (rate limiting por request/minuto). Reintentable
  tras backoff.
- ``auth``: credencial invalida (401, o 403 sin marker de cuota). No es
  recuperable reintentando — requiere corregir la API key.
- ``context_overflow``: 400 cuyo body reporta que el prompt/historial excede la
  ventana de contexto del modelo. Recuperable reduciendo `max_tokens` o
  compactando el historial (ver ``compute_reduced_max_tokens``).
- ``transient``: 5xx del backend (500/502/503/504/529). Reintentable de inmediato
  o via failover a otro provider sano.
- ``client_error``: cualquier otro 4xx (payload/configuracion invalida). No
  recuperable con reintento automatico — el error debe volver crudo al usuario.

Patron tomado de Gitlawb/openclaude (``withRetry.ts``): clasificar antes de
decidir la accion, en vez de una politica unica para todo status != 200.

Modulo PURO: sin I/O, sin estado global, trivialmente testeable.
"""

from __future__ import annotations

import logging
import re
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorCategory(str, Enum):
    """Categoria fina de un error upstream, para decidir la accion de recuperacion."""

    TERMINAL_QUOTA = "terminal_quota"
    RATE_LIMIT = "rate_limit"
    AUTH = "auth"
    CONTEXT_OVERFLOW = "context_overflow"
    TRANSIENT = "transient"
    CLIENT_ERROR = "client_error"


# Markers de cuota/billing AGOTADOS de forma permanente (no un rate-limit
# transitorio). Cubren el wording de OpenAI-compatible (insufficient_quota,
# "exceeded your current quota") y Anthropic (credit balance bajo).
_QUOTA_MARKERS = (
    "insufficient_quota",
    "exceeded your current quota",
    "quota exceeded",
    "quota agotada",
    "monthly quota",
    "billing",
    "credit balance is too low",
    "purchase more credits",
)

# Markers de credencial invalida (401, o 403 sin marker de cuota).
_AUTH_MARKERS = (
    "invalid api key",
    "invalid_api_key",
    "invalid x-api-key",
    "unauthorized",
    "authentication_error",
    "invalid bearer token",
    "api key not valid",
)

# Markers de limite de CONTEXTO/TAMANO del payload excedido. Cubre el wording de
# OpenAI-compatible ("maximum context length", "context_length_exceeded") y
# Anthropic ("prompt is too long", "exceed ... context length").
_CONTEXT_OVERFLOW_MARKERS = (
    "context window",
    "context length",
    "context_length_exceeded",
    "model_context_window_exceeded",
    "maximum context",
    "maximum tokens",
    "prompt is too long",
    "input is too long",
    "too many tokens",
    "token limit",
    "exceed context limit",
    "exceed the model's context length",
)

_TRANSIENT_STATUSES = frozenset({500, 502, 503, 504, 529})


def _decode(body: bytes | str) -> str:
    """Normaliza el body del error a un string en minusculas para matching.

    Args:
        body: Cuerpo del error, como bytes o str.

    Returns:
        El texto decodificado en minusculas (bytes invalidos se ignoran).
    """
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="ignore")
    return body.lower()


def _has_marker(text: str, markers: tuple[str, ...]) -> bool:
    """True si alguno de los markers aparece como substring de ``text``."""
    return any(marker in text for marker in markers)


def classify_upstream_error(status: int, body: bytes | str) -> ErrorCategory:
    """Clasifica un error upstream de un provider IA en una categoria fina.

    Args:
        status: Codigo HTTP devuelto por el upstream (se asume != 200).
        body: Cuerpo de la respuesta de error (bytes o str).

    Returns:
        La ``ErrorCategory`` que mejor describe el error, para que el caller
        decida la accion de recuperacion (retry local, rotar provider, o
        devolver el error crudo).
    """
    text = _decode(body)

    if status == 402:
        return ErrorCategory.TERMINAL_QUOTA

    if status == 403:
        if _has_marker(text, _QUOTA_MARKERS):
            return ErrorCategory.TERMINAL_QUOTA
        # Sin marker de cuota, un 403 se asume problema de credencial/permiso
        # (unico otro significado valido segun el spec de categorias).
        return ErrorCategory.AUTH

    if status == 401:
        return ErrorCategory.AUTH

    if status == 429:
        if _has_marker(text, _QUOTA_MARKERS):
            return ErrorCategory.TERMINAL_QUOTA
        return ErrorCategory.RATE_LIMIT

    if status == 400:
        if _has_marker(text, _CONTEXT_OVERFLOW_MARKERS):
            return ErrorCategory.CONTEXT_OVERFLOW
        return ErrorCategory.CLIENT_ERROR

    if status in _TRANSIENT_STATUSES or status >= 500:
        return ErrorCategory.TRANSIENT

    return ErrorCategory.CLIENT_ERROR


# ---------------------------------------------------------------------------
# Heuristica de reduccion de max_tokens ante un context_overflow
# ---------------------------------------------------------------------------

# Extrae el par (limite_de_contexto, tokens_usados) del wording tipico OpenAI:
# "This model's maximum context length is 8192 tokens. However, your messages
# resulted in 10000 tokens." Tolera texto intermedio variable (DOTALL) y comas
# de miles en los numeros.
_CONTEXT_NUMBERS_RE = re.compile(
    r"maximum context length is\s*([\d,]+)\s*tokens.*?"
    r"(?:resulted in|requested|is)\s*([\d,]+)\s*tokens",
    re.IGNORECASE | re.DOTALL,
)

_RETRY_MARGIN = 0.95
_HALVING_FLOOR = 1024
# Piso absoluto de seguridad para la rama numerica: si el espacio restante
# calculado es minusculo, evita devolver 0/negativo (max_tokens invalido).
_NUMERIC_FLOOR = 16


def compute_reduced_max_tokens(current_max_tokens: int, error_text: str) -> int:
    """Calcula un ``max_tokens`` reducido para reintentar tras un context_overflow.

    Si el error trae los numeros de limite/uso (formato OpenAI-compatible),
    calcula el espacio restante con un margen de seguridad del 5%. Si no hay
    numeros parseables (u origina un espacio restante no positivo), reduce el
    valor actual a la mitad con un piso de 1024.

    Args:
        current_max_tokens: Valor de ``max_tokens`` del request que fallo.
        error_text: Cuerpo del error upstream (para extraer los numeros).

    Returns:
        El nuevo valor de ``max_tokens`` a usar en el reintento. Puede ser
        mayor o igual al actual si la heuristica no logra reducirlo — el
        caller es responsable de no reintentar en ese caso.
    """
    match = _CONTEXT_NUMBERS_RE.search(error_text)
    if match:
        limit = int(match.group(1).replace(",", ""))
        used = int(match.group(2).replace(",", ""))
        remaining = limit - used
        if remaining > 0:
            candidate = int(remaining * _RETRY_MARGIN)
            return max(candidate, _NUMERIC_FLOOR)
        logger.info(
            "context_overflow: numeros del error no dejan espacio remanente "
            "(limit=%d, used=%d) — cae a la heuristica de mitad",
            limit,
            used,
        )
    return max(current_max_tokens // 2, _HALVING_FLOOR)
