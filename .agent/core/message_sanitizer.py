"""Adapta un payload Anthropic Messages API al formato que acepta cada backend.

Motivo: endpoints de terceros (z.ai/GLM) rechazan mensajes con role 'system'
en posiciones intermedias del array `messages` (Anthropic nativo los tolera).

Ademas, sanea los `thinking`/`redacted_thinking` blocks del historial en TODOS los
backends. Esos bloques llevan un `signature` criptografico de Anthropic; tras un
hot-swap de provider el historial puede arrastrar thinking generado por otro backend
(GLM/MiniMax) con firma invalida -> Claude responde 400 "Invalid `signature` in
`thinking` block". Removerlos del historial blinda el swap en caliente.
"""

from __future__ import annotations

import copy
from typing import Any

# Campos top-level estandar de la Messages API de Anthropic. Para backends
# alternativos (no-claude) se aplica esta whitelist: los betas experimentales
# (`thinking:{...}`, `container`, etc.) que Claude Code agrega al body se
# descartan porque los endpoints Anthropic-compatible de terceros los rechazan
# con 400. NO se aplica al passthrough de claude.
_MESSAGES_API_TOP_LEVEL_FIELDS = frozenset(
    {
        "model",
        "messages",
        "system",
        "tools",
        "tool_choice",
        "max_tokens",
        "temperature",
        "top_p",
        "top_k",
        "stop_sequences",
        "stream",
        "metadata",
    }
)

# Texto del `tool_result` sintetico que se inyecta cuando un `tool_use` quedo
# huerfano (sin su `tool_result`) tras un hot-swap de provider mid-tool-loop.
_INTERRUPTED_TOOL_RESULT_TEXT = "[interrumpido por cambio de proveedor]"

# Placeholder de texto para un mensaje que quedaria con `content == []` tras la
# purga agresiva de tool blocks. Anthropic rechaza content vacio con 400.
_EMPTY_CONTENT_PLACEHOLDER_TEXT = "[contenido omitido]"


def _system_text(content: Any) -> str:
    """Extrae texto plano de un campo `content` (str o lista de bloques).

    Args:
        content: Valor de `content` (string o lista de content blocks).

    Returns:
        Texto concatenado de los bloques de tipo text, o el string tal cual.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "\n".join(parts)
    return ""


def _strip_cache_control(messages: list) -> None:
    """Quita `cache_control` de todos los content blocks in-place.

    Args:
        messages: Lista de mensajes Anthropic.
    """
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    block.pop("cache_control", None)


def _strip_cache_control_top_level(payload: dict) -> None:
    """Quita `cache_control` de los bloques `system` top-level y de `tools` in-place.

    Claude Code marca con breakpoints de prompt caching el array `system` y la
    ultima tool, ademas de los messages. Los backends Anthropic-compatible de
    terceros los limitan (GLM: max 4 breakpoints y 400 ante conflicto de TTL;
    MiniMax M3 usa caching pasivo), asi que se quitan todos — el caching
    implicito del provider sigue funcionando igual.

    Args:
        payload: Body Anthropic ya copiado (se modifica in-place).
    """
    system = payload.get("system")
    if isinstance(system, list):
        for block in system:
            if isinstance(block, dict):
                block.pop("cache_control", None)
    tools = payload.get("tools")
    if isinstance(tools, list):
        for tool in tools:
            if isinstance(tool, dict):
                tool.pop("cache_control", None)


def _strip_thinking_blocks(messages: list) -> bool:
    """Quita los content blocks `thinking`/`redacted_thinking` in-place.

    Los thinking blocks de Anthropic llevan un `signature` criptografico. Tras un
    hot-swap de provider el historial puede traer thinking generado por otro backend
    (firma invalida para Anthropic) o thinking de Claude que un alternativo no acepta.
    Removerlos del historial evita el 400 "Invalid `signature` in `thinking` block".

    Args:
        messages: Lista de mensajes Anthropic (se modifica in-place).

    Returns:
        True si removio al menos un bloque.
    """
    removed = False
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        filtered = [
            block
            for block in content
            if not (
                isinstance(block, dict) and block.get("type") in ("thinking", "redacted_thinking")
            )
        ]
        if len(filtered) != len(content):
            msg["content"] = filtered
            removed = True
    return removed


def _reconcile_tool_blocks(messages: list) -> list:
    """Reconcilia pares `tool_use`/`tool_result` huerfanos del historial.

    Tras un hot-swap de provider en medio de un loop de herramientas, el historial
    puede quedar con un `tool_use` (en un mensaje `assistant`) sin su `tool_result`
    correspondiente (en un mensaje `user`), o al reves. Los backends alternativos
    rechazan esa estructura con 400. Esta funcion la repara:

    - `tool_use` sin `tool_result` -> inyecta un `tool_result` sintetico
      (`is_error=True`, contenido ``[interrumpido por cambio de proveedor]``) en el
      mensaje `user` inmediatamente posterior (o crea uno si no existe).
    - `tool_result` sin `tool_use` previo -> elimina ese bloque.
    - Preserva el orden y el resto del contenido.

    Es idempotente: correrla dos veces produce el mismo resultado (los `tool_result`
    sinteticos ya satisfacen a sus `tool_use`, asi que no se vuelven a inyectar).

    Args:
        messages: Lista de mensajes Anthropic. No se modifica in-place.

    Returns:
        Una nueva lista de mensajes con los pares reconciliados.
    """
    result = copy.deepcopy(messages)

    # 1) Indexar los tool_use_id que YA tienen su tool_result.
    seen_tool_use_ids: set[str] = set()
    resolved_tool_use_ids: set[str] = set()
    for msg in result:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "tool_use" and msg.get("role") == "assistant":
                tu_id = block.get("id")
                if isinstance(tu_id, str):
                    seen_tool_use_ids.add(tu_id)
            elif btype == "tool_result":
                # Un tool_result cuenta como "resuelto" para su tool_use_id sin
                # importar el rol del mensaje contenedor: tras un hot-swap el
                # historial puede degenerar y traerlo fuera de un role:user. Si
                # exigimos role:user, marcariamos el tool_use como huerfano e
                # inyectariamos un tool_result DUPLICADO (mismo id -> 400).
                tr_id = block.get("tool_use_id")
                if isinstance(tr_id, str):
                    resolved_tool_use_ids.add(tr_id)

    # 2) Eliminar `tool_result` huerfanos (sin `tool_use` previo). Operamos sobre
    #    cualquier mensaje con content-lista (no solo role:user) por la misma razon
    #    de historial degenerado post-swap.
    for msg in result:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        filtered = [
            block
            for block in content
            if not (
                isinstance(block, dict)
                and block.get("type") == "tool_result"
                and block.get("tool_use_id") not in seen_tool_use_ids
            )
        ]
        if len(filtered) != len(content):
            msg["content"] = filtered

    # 3) Inyectar `tool_result` sinteticos para los `tool_use` sin resolver,
    #    preservando el orden: se inyectan en el mensaje user inmediatamente
    #    posterior al assistant que abrio el tool_use (o se crea uno).
    orphan_ids = seen_tool_use_ids - resolved_tool_use_ids
    if not orphan_ids:
        return result

    out: list = []
    idx = 0
    n = len(result)
    while idx < n:
        msg = result[idx]
        out.append(msg)
        pending = _orphan_ids_in_message(msg, orphan_ids)
        if pending:
            synthetic = [_synthetic_tool_result(tu_id) for tu_id in pending]
            next_msg = result[idx + 1] if idx + 1 < n else None
            if isinstance(next_msg, dict) and next_msg.get("role") == "user":
                # Inyectamos los tool_result en el user posterior, sin importar si
                # su content es string o lista. Si fuera string, lo envolvemos en un
                # bloque de texto: Claude Code MUY frecuentemente manda content como
                # string plano, y crear un user sintetico nuevo en el medio dejaria
                # dos role:user consecutivos -> la Messages API lo rechaza con 400.
                next_content = next_msg.get("content")
                if isinstance(next_content, str):
                    next_content = [{"type": "text", "text": next_content}]
                elif not isinstance(next_content, list):
                    next_content = []
                # Los tool_result deben ir al principio del content de un user.
                next_msg["content"] = synthetic + next_content
                out.append(next_msg)
                idx += 2
                continue
            # Solo creamos un user sintetico nuevo si NO hay user posterior
            # (tool_use huerfano al final del historial). Nunca dos user seguidos.
            out.append({"role": "user", "content": synthetic})
        idx += 1
    return out


def reconcile_tool_blocks(messages: list) -> list:
    """API publica de `_reconcile_tool_blocks` para uso cross-modulo.

    El proxy del gateway (rama OpenAI-compatible de `_build_proxy_request`) necesita
    reconciliar pares `tool_use`/`tool_result` huerfanos ANTES de traducir a Chat
    Completions: providers `wire="openai"` estrictos (OpenCode Go / Kimi -> "tool_call_id
    is not found"; MiniMax -> 2013) rechazan un `role:tool` sin su `tool_call`. La rama
    Anthropic ya lo hace via `sanitize_anthropic_payload`; esto reexpone solo esa pieza
    sin arrastrar el resto del saneo (whitelist, normalize_tools, strip thinking), que el
    traductor OpenAI no necesita.

    Args:
        messages: Lista de mensajes Anthropic. No se modifica in-place.

    Returns:
        Una nueva lista con los pares tool_use/tool_result reconciliados.
    """
    return _reconcile_tool_blocks(messages)


def _orphan_ids_in_message(msg: Any, orphan_ids: set[str]) -> list[str]:
    """Devuelve los tool_use_id huerfanos abiertos en un mensaje assistant.

    Args:
        msg: Mensaje Anthropic a inspeccionar.
        orphan_ids: Conjunto de tool_use_id sin tool_result correspondiente.

    Returns:
        Lista ordenada (orden de aparicion) de los ids huerfanos del mensaje.
    """
    if not isinstance(msg, dict) or msg.get("role") != "assistant":
        return []
    content = msg.get("content")
    if not isinstance(content, list):
        return []
    pending: list[str] = []
    for block in content:
        if (
            isinstance(block, dict)
            and block.get("type") == "tool_use"
            and block.get("id") in orphan_ids
        ):
            pending.append(block["id"])
    return pending


def _synthetic_tool_result(tool_use_id: str) -> dict:
    """Construye el `tool_result` sintetico para un `tool_use` interrumpido.

    Args:
        tool_use_id: Id del `tool_use` huerfano.

    Returns:
        Bloque `tool_result` con marca de error y texto de interrupcion.
    """
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": _INTERRUPTED_TOOL_RESULT_TEXT,
        "is_error": True,
    }


def _strip_tool_blocks(messages: list) -> None:
    """Purga TODOS los bloques `tool_use`/`tool_result` del historial in-place.

    Modo agresivo (ultimo recurso ante un 400 persistente): deja solo el contenido
    de texto de cada mensaje. Un mensaje cuyo unico contenido eran bloques de
    herramientas quedaria con `content == []`, y Anthropic rechaza content vacio
    con 400; en ese caso se reemplaza por un placeholder de texto (mas seguro que
    descartar el mensaje, que rompe la alternancia user/assistant). Aplica tanto a
    assistant como a user vacios.

    Args:
        messages: Lista de mensajes Anthropic (se modifica in-place).
    """
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        stripped = [
            block
            for block in content
            if not (isinstance(block, dict) and block.get("type") in ("tool_use", "tool_result"))
        ]
        if not stripped:
            stripped = [{"type": "text", "text": _EMPTY_CONTENT_PLACEHOLDER_TEXT}]
        msg["content"] = stripped


def _whitelist_top_level_fields(payload: dict) -> None:
    """Descarta campos top-level fuera de la whitelist de la Messages API in-place.

    Quita betas experimentales del body (`thinking:{...}`, `container`, etc.) que
    los backends alternativos rechazan. Solo se aplica a providers no-claude.

    Args:
        payload: Body Anthropic ya copiado (se modifica in-place).
    """
    for key in list(payload.keys()):
        if key not in _MESSAGES_API_TOP_LEVEL_FIELDS:
            payload.pop(key, None)


def _normalize_tools(payload: dict) -> None:
    """Normaliza cada tool a `{name, description, input_schema}` in-place.

    Los backends alternativos solo aceptan el shape estandar de tool de la Messages
    API. Se descartan claves no estandar a nivel tool y se garantiza que
    `input_schema.type == "object"`. Las `properties` del schema se preservan: NO
    se altera la semantica del schema, solo el envoltorio.

    Args:
        payload: Body Anthropic ya copiado (se modifica in-place).
    """
    tools = payload.get("tools")
    if not isinstance(tools, list):
        return
    normalized: list = []
    for tool in tools:
        if not isinstance(tool, dict):
            normalized.append(tool)
            continue
        clean: dict = {}
        if "name" in tool:
            clean["name"] = tool["name"]
        if "description" in tool:
            clean["description"] = tool["description"]
        schema = tool.get("input_schema")
        if isinstance(schema, dict):
            schema = dict(schema)
            schema["type"] = "object"
            clean["input_schema"] = schema
        else:
            clean["input_schema"] = {"type": "object"}
        normalized.append(clean)
    payload["tools"] = normalized


def sanitize_anthropic_payload(
    payload: dict, provider: str, model: str, aggressive: bool = False
) -> dict:
    """Devuelve una copia del payload adaptada al backend.

    Args:
        payload: Body Anthropic Messages API entrante.
        provider: Backend activo (claude | zai | ...).
        model: Modelo a inyectar para el backend.
        aggressive: Si es True (solo para backends alternativos), purga TODO el
            historial de herramientas (`tool_use`/`tool_result`) dejando solo texto.
            Es la red de seguridad ante un 400 persistente. No afecta a claude.

    Returns:
        Copia profunda saneada.
    """
    out = copy.deepcopy(payload)

    if provider == "claude":
        # Passthrough casi puro: NO tocamos el modelo ni los parametros. Claude Code usa
        # su propio modelo (Opus, etc.) con su effort/thinking; forzar otro modelo rompe
        # (p. ej. 'effort xhigh' no es soportado por claude-sonnet-4-6 -> HTTP 400).
        # UNICA excepcion: limpiamos thinking blocks del historial. Por diseno Claude corre
        # nativo-directo (bypass del proxy); cuando se sirve por aca es transitorio/legacy y
        # el historial puede traer thinking contaminado de otro backend -> 400 de firma.
        messages = out.get("messages")
        if isinstance(messages, list):
            _strip_thinking_blocks(messages)
        return out

    out["model"] = model

    # Backends Anthropic-compatible estrictos (z.ai/GLM): el array `messages`
    # solo admite user/assistant. Movemos system intermedios al top-level.
    messages = out.get("messages")
    if isinstance(messages, list):
        moved: list[str] = []
        kept: list[dict] = []
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "system":
                moved.append(_system_text(msg.get("content")))
            else:
                kept.append(msg)
        if moved:
            existing = out.get("system")
            existing_text = _system_text(existing) if existing else ""
            combined = "\n".join([t for t in [existing_text, *moved] if t])
            out["system"] = combined
            out["messages"] = kept
        # Un backend no-Claude tampoco debe recibir thinking firmado por Claude del
        # historial: la firma no le sirve y puede rechazar el turno.
        _strip_thinking_blocks(out.get("messages", []))
        _strip_cache_control(out.get("messages", []))
        if aggressive:
            # Ultimo recurso ante un 400 persistente: dejar solo texto.
            _strip_tool_blocks(out.get("messages", []))
        else:
            # Reconciliar pares tool_use/tool_result huerfanos (causa raiz del
            # 400 intermitente al cambiar de provider mid-tool-loop).
            out["messages"] = _reconcile_tool_blocks(out.get("messages", []))

    _strip_cache_control_top_level(out)

    # Saneo de tools y limpieza de betas del body: solo para alternativos.
    _normalize_tools(out)
    _whitelist_top_level_fields(out)

    return out
