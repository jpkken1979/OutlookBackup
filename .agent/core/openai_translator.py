"""Traduce payloads entre Anthropic Messages API y OpenAI Chat Completions.

Motivo: los backends locales (Ollama, LM Studio) y algunos cloud (OpenRouter, Kimi)
hablan el protocolo **OpenAI-compatible** (`/v1/chat/completions`), NO el de Anthropic
(`/v1/messages`). El proxy `claudeproxy` recibe siempre formato Anthropic desde Claude
Code; para servir estos backends hay que:

  1. Traducir el request Anthropic → OpenAI antes de reenviarlo (``anthropic_to_openai``).
  2. Traducir el stream SSE de respuesta OpenAI → eventos SSE Anthropic de vuelta
     (``OpenAiStreamTranslator``), porque Claude Code solo entiende el schema Anthropic.

Decisiones de diseno:

- ``system`` top-level de Anthropic (string o lista de bloques) se inyecta como primer
  mensaje ``role: system`` de OpenAI, que SÍ lo acepta en cualquier posicion. Diferencia
  clave con GLM/MiniMax (que rechazan system intermedio): aca el endpoint es OpenAI y el
  role system va a la API, no al array messages de Anthropic.
- ``tool_use`` / ``tool_result`` de Anthropic se mapean a ``tool_calls`` / ``role: tool``
  de OpenAI para que el razonamiento con herramientas siga funcionando.
- El stream se traduce **por eventos**: cada delta de OpenAI genera los content_block
  events que Claude Code espera (message_start, content_block_delta, ... message_stop).
- El modulo es puro (sin I/O, sin estado global) para que sea trivialmente testeable
  con mocks y no afecte al proxy existente hasta que se invoque explicitamente.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

# ----------------------------------------------------------------------------
# Request: Anthropic Messages API  ->  OpenAI Chat Completions
# ----------------------------------------------------------------------------


def _flatten_text(content: Any) -> str:
    """Extrae texto plano de un content Anthropic (str o lista de bloques)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif block.get("type") == "tool_result":
                # tool_result puede venir como content anidado; se maneja aparte.
                inner = block.get("content")
                if isinstance(inner, str):
                    parts.append(inner)
                elif isinstance(inner, list):
                    parts.append(_flatten_text(inner))
        return "\n".join(p for p in parts if p)
    return ""


def _anthropic_content_to_openai(content: Any) -> str | list[dict[str, Any]]:
    """Convierte el content de un mensaje Anthropic al formato OpenAI.

    Devuelve:
        - Un string si son bloques de texto puro (lo mas comun).
        - Una lista de partes ``{type, text}`` si hay tool_use mezclado.

    Los bloques ``tool_use`` se procesan a nivel de mensaje en ``_convert_message``
    (van a ``tool_calls``), aca solo se baja el texto.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(str(block.get("text", "")))
        if text_parts:
            return "\n".join(text_parts)
    return ""


def _convert_message(msg: dict[str, Any], tool_call_index: list[int]) -> list[dict[str, Any]]:
    """Convierte UN mensaje Anthropic a CERO O MAS mensajes OpenAI Chat Completions.

    Devuelve una lista porque un unico mensaje ``user`` de Anthropic con varios
    ``tool_result`` (tool calls PARALELOS) debe expandirse a varios mensajes
    ``role: tool`` de OpenAI: el wire OpenAI exige una respuesta por cada
    ``tool_call_id``. Antes se devolvia solo el primero y el resto se perdia, lo
    que rompia a los providers OpenAI remotos (opencode/Moonshot) con un 400
    "tool_call_ids did not have response messages".

    Args:
        msg: Mensaje Anthropic (con ``role`` y ``content``).
        tool_call_index: Lista-mutable con el contador de tool_calls del mensaje
            (para asignar IDs/indices estables a los tool_use).

    Returns:
        Lista de mensajes OpenAI (vacia si el mensaje no aporta nada util).
    """
    role = msg.get("role")
    content = msg.get("content")

    # role 'system' se pasa directo (OpenAI lo acepta en cualquier posicion).
    if role == "system":
        text = _flatten_text(content)
        return [{"role": "system", "content": text}] if text else []

    if role == "user":
        # El user puede contener tool_result (respuesta de herramienta) o texto.
        if isinstance(content, list):
            tool_results = [
                b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"
            ]
            if tool_results:
                # Cada tool_result se convierte en un mensaje role:tool de OpenAI.
                # Con tool calls PARALELOS hay varios tool_result en un solo mensaje
                # user; OpenAI exige uno por cada tool_call_id, asi que los emitimos
                # TODOS (antes solo iba el primero -> 400 en providers OpenAI remotos).
                return [
                    {
                        "role": "tool",
                        "tool_call_id": str(tr.get("tool_use_id", "")),
                        "content": _flatten_text(tr.get("content")),
                    }
                    for tr in tool_results
                ]
        text = _flatten_text(content)
        return [{"role": "user", "content": text}]

    if role == "assistant":
        out: dict[str, Any] = {"role": "assistant"}
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text":
                    t = str(block.get("text", ""))
                    if t:
                        text_parts.append(t)
                elif btype == "tool_use":
                    idx = tool_call_index[0]
                    tool_call_index[0] += 1
                    tool_calls.append(
                        {
                            "id": str(block.get("id", f"call_{idx}")),
                            "type": "function",
                            "function": {
                                "name": str(block.get("name", "")),
                                "arguments": json.dumps(block.get("input", {}), ensure_ascii=False),
                            },
                        }
                    )
        if text_parts:
            out["content"] = "\n".join(text_parts)
        if tool_calls:
            out["tool_calls"] = tool_calls
        # assistant con content vacio Y sin tool_calls no aporta; se omite.
        if "content" not in out and "tool_calls" not in out:
            return []
        return [out]

    return []


def _convert_tools(tools: list[Any]) -> list[dict[str, Any]]:
    """Convierte la lista de tools Anthropic al formato tools de OpenAI."""
    out: list[dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        # Anthropic tool: {name, description, input_schema}. OpenAI: function wrapper.
        if "function" in tool and isinstance(tool["function"], dict):
            # Ya viene en formato OpenAI (por si rebotan); passthrough.
            out.append(tool)
            continue
        schema = tool.get("input_schema") or {}
        out.append(
            {
                "type": "function",
                "function": {
                    "name": str(tool.get("name", "")),
                    "description": str(tool.get("description", "")),
                    "parameters": schema,
                },
            }
        )
    return out


def _is_mergeable_text_message(msg: dict[str, Any]) -> bool:
    """True si ``msg`` es un mensaje OpenAI user/assistant de texto puro.

    Excluye ``role: tool`` (tool calls paralelos consecutivos son legales y no
    deben tocarse) y ``assistant`` con ``tool_calls`` (fusionarlo perderia la
    estructura de la llamada a herramientas).
    """
    return (
        msg.get("role") in ("user", "assistant")
        and "tool_calls" not in msg
        and isinstance(msg.get("content"), str)
    )


def _coalesce_consecutive_roles(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fusiona mensajes consecutivos del mismo role (user/assistant, texto puro).

    Providers OpenAI-compatible estrictos con alternancia (algunos de opencode)
    devuelven 400 si el array de mensajes tiene dos roles iguales seguidos. La
    traduccion Anthropic -> OpenAI puede producir esa forma (p. ej. mensajes
    Anthropic ya no alternados tras un hot-swap o una edicion manual del
    historial). Se fusiona concatenando el content con ``"\n"``.

    Nunca toca ``role: tool`` (las respuestas de tool calls paralelos deben
    permanecer una por ``tool_call_id``) ni mensajes ``assistant`` con
    ``tool_calls`` (fusionarlos perderia la estructura de la llamada).

    Args:
        messages: Mensajes ya convertidos a formato OpenAI.

    Returns:
        Lista con los mensajes consecutivos fusionables colapsados en uno.
    """
    if not messages:
        return messages
    out: list[dict[str, Any]] = [dict(messages[0])]
    for msg in messages[1:]:
        prev = out[-1]
        if (
            prev.get("role") == msg.get("role")
            and _is_mergeable_text_message(prev)
            and _is_mergeable_text_message(msg)
        ):
            prev["content"] = f"{prev['content']}\n{msg['content']}"
            continue
        out.append(dict(msg))
    return out


def anthropic_to_openai(
    payload: dict[str, Any],
    model: str,
    provider: str = "",
) -> dict[str, Any]:
    """Traduce un body Anthropic Messages API a OpenAI Chat Completions.

    Args:
        payload: Body Anthropic entrante (con ``messages``, opcional ``system``,
            ``tools``, ``max_tokens``, ``temperature``, etc.).
        model: Modelo a fijar en el request OpenAI (resuelto por el caller).
        provider: Id del backend (para logging/futuros ajustes por provider).

    Returns:
        Body listo para POST a ``/v1/chat/completions``.
    """
    out: dict[str, Any] = {
        "model": model,
        "stream": bool(payload.get("stream", True)),
    }
    if out["stream"]:
        # Pedir usage real al provider (lo manda en un chunk final sin choices).
        # Sin esto, la telemetria de tokens del proxy queda en cero para
        # openrouter/opencode/ollama. Parametro exclusivo de streaming.
        out["stream_options"] = {"include_usage": True}

    messages: list[dict[str, Any]] = []

    # system top-level Anthropic -> primer mensaje role:system de OpenAI.
    system = payload.get("system")
    sys_text = _flatten_text(system)
    if sys_text:
        messages.append({"role": "system", "content": sys_text})

    tool_call_index = [0]
    for msg in payload.get("messages", []) or []:
        if not isinstance(msg, dict):
            continue
        messages.extend(_convert_message(msg, tool_call_index))
    # Providers estrictos con alternancia rechazan roles repetidos seguidos.
    out["messages"] = _coalesce_consecutive_roles(messages)

    # Parametros de muestreo (solo si vienen explicitos).
    if "max_tokens" in payload:
        # OpenAI usa max_tokens (legacy) o max_completion_tokens. max_tokens sigue
        # siendo aceptado por Ollama/LM Studio; lo usamos para compatibilidad.
        out["max_tokens"] = payload["max_tokens"]
    if "temperature" in payload:
        out["temperature"] = payload["temperature"]
    if "top_p" in payload:
        out["top_p"] = payload["top_p"]
    if payload.get("stop_sequences"):
        out["stop"] = payload["stop_sequences"]

    tools = payload.get("tools")
    if isinstance(tools, list) and tools:
        out["tools"] = _convert_tools(tools)
        # Claude Code espera que el modelo pueda elegir herramientas libremente.
        out["tool_choice"] = "auto"

    return out


# ----------------------------------------------------------------------------
# Response: OpenAI Chat Completions stream  ->  Anthropic Messages SSE
# ----------------------------------------------------------------------------

# Estos ids son estables dentro de un turno: Claude Code los usa para correlacionar
# content blocks. Se generan por turno (no globales) en OpenAiStreamTranslator.
_TEXT_BLOCK_TYPE = "text"

# --- Dialectos de tool-calls emitidos como TEXTO (GLM/Qwen/Ollama) -----------
# Algunos modelos servidos por wire OpenAI (opencode/openrouter/ollama) emiten el
# tool-call como texto en vez del campo estructurado `tool_calls`. Sin parsearlos,
# Claude Code recibe el XML como prosa y el tool-loop muere. Patron de cascada de
# fallbacks tomado de Gitlawb/openclaude (openaiShim.ts).
_DIALECT_MARKERS = ("<tool_call>", "Tool calls requested:")
_MAX_MARKER_LEN = max(len(m) for m in _DIALECT_MARKERS)


def _loads_or_repair(raw: str) -> Any:
    """``json.loads`` con reparacion de sufijos comunes de JSON truncado por stream.

    Args:
        raw: JSON posiblemente cortado a mitad (stream interrumpido).

    Returns:
        El objeto parseado, o ``None`` si no se pudo reparar.
    """
    raw = raw.strip()
    if not raw:
        return None
    # ponytail: reparacion por sufijos comunes, no un parser incremental completo;
    # cubre los cortes tipicos de stream (llaves sin cerrar). Si aparece un corte
    # mas exotico, el fallback es tratar el texto como prosa (no se pierde nada).
    candidates = (raw, raw + '"}', raw + '"}}', raw + "}", raw + "}}", raw + "}}}")
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _parse_tool_call_body(body: str) -> dict[str, Any] | None:
    """Parsea el cuerpo de UN ``<tool_call>`` textual a ``{'name', 'input'}``.

    Soporta tres formatos observados en modelos OpenAI-compatible:
      1. JSON: ``{"name": "x", "arguments": {...}}`` (GLM/Qwen modernos)
      2. ``<function=NAME><parameter=KEY>valor</parameter>...`` (Qwen agentico)
      3. ``NOMBRE\\n<arg_key>k</arg_key><arg_value>v</arg_value>`` (GLM-4 legacy)

    Args:
        body: Contenido entre ``<tool_call>`` y ``</tool_call>`` (cierre opcional).

    Returns:
        Dict con ``name`` e ``input``, o ``None`` si no es parseable.
    """
    body = body.strip()
    if body.startswith("{"):
        obj = _loads_or_repair(body)
        if isinstance(obj, dict) and obj.get("name"):
            args = obj.get("arguments", obj.get("parameters", {}))
            if isinstance(args, str):
                args = _loads_or_repair(args) or {}
            return {
                "name": str(obj["name"]),
                "input": args if isinstance(args, dict) else {},
            }
        return None
    fn_match = re.match(r"<function=([\w.\-]+)>(.*)", body, re.S)
    if fn_match:
        params = dict(
            re.findall(r"<parameter=([\w.\-]+)>(.*?)</parameter>", fn_match.group(2), re.S)
        )
        return {"name": fn_match.group(1), "input": params}
    lines = body.splitlines()
    if lines and re.fullmatch(r"[\w.\-]+", lines[0].strip()):
        keys = re.findall(r"<arg_key>(.*?)</arg_key>", body, re.S)
        vals = re.findall(r"<arg_value>(.*?)</arg_value>", body, re.S)
        if keys and len(keys) == len(vals):
            return {"name": lines[0].strip(), "input": dict(zip(keys, vals, strict=False))}
    return None


def _parse_dialect_tool_calls(text: str) -> list[dict[str, Any]]:
    """Extrae tool-calls de texto con dialecto XML/plano.

    Args:
        text: Texto retenido desde la primera aparicion de un marker de dialecto.

    Returns:
        Lista de ``{'name', 'input'}``; vacia si nada es parseable (el caller
        debe re-emitir el texto como prosa para no perder contenido).
    """
    calls: list[dict[str, Any]] = []
    if "<tool_call>" in text:
        for segment in text.split("<tool_call>")[1:]:
            call = _parse_tool_call_body(segment.split("</tool_call>")[0])
            if call:
                calls.append(call)
        return calls
    if text.lstrip().startswith("Tool calls requested:"):
        # Formato texto de Ollama: `- NOMBRE({json args}) [id: x]`
        for match in re.finditer(r"-\s*([\w.\-]+)\s*\((\{.*?\})\)", text, re.S):
            args = _loads_or_repair(match.group(2))
            if isinstance(args, dict):
                calls.append({"name": match.group(1), "input": args})
    return calls


def _sse(event: str, data: dict[str, Any]) -> bytes:
    """Serializa un evento SSE Anthropic (``event: ...\\ndata: ...\\n\\n``)."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()


class OpenAiStreamTranslator:
    """Traduce un stream SSE OpenAI Chat Completions a eventos SSE Anthropic.

    Uso::

        translator = OpenAiStreamTranslator(model="llama3")
        async for chunk in upstream.content:
            for sse_bytes in translator.feed(chunk):
                await response.write(sse_bytes)
        for sse_bytes in translator.flush():
            await response.write(sse_bytes)

    Emite la secuencia canonica que Claude Code parsea:

        message_start -> [content_block_start] -> content_block_delta* ->
        content_block_stop -> [tool_use blocks] -> message_delta(stop) -> message_stop

    El flujo de texto se acumula en UN solo content_block de tipo text. Los
    ``tool_calls`` del stream se emiten como content_block_start/delta de tool_use.
    """

    def __init__(self, model: str) -> None:
        self.model = model
        self._message_started = False
        self._text_block_open = False
        self._tool_blocks: dict[int, dict[str, Any]] = {}  # index -> bloque tool_use en curso
        self._input_tokens = 0
        self._output_tokens = 0
        self._finished = False  # True tras _finish(): evita doble cierre en flush()
        # Carry-over de la linea `data:` incompleta entre feed(): iter_any() de
        # aiohttp no alinea chunks a limites de linea. Se guarda en BYTES (no str)
        # para no partir un caracter UTF-8 multi-byte al decodificar.
        self._line_buffer = b""
        # Texto recibido pero aun no emitido: retiene una cola corta que podria
        # ser el arranque de un tool-call textual (dialectos GLM/Qwen/Ollama), y
        # en _dialect_mode retiene TODO hasta resolver en _finish()/flush().
        self._pending_text = ""
        self._dialect_mode = False

    def _begin_message(self) -> list[bytes]:
        """Emite message_start (una sola vez por turno)."""
        self._message_started = True
        return [
            _sse(
                "message_start",
                {
                    "type": "message_start",
                    "message": {
                        "id": "msg_proxy_local",
                        "type": "message",
                        "role": "assistant",
                        "model": self.model,
                        "content": [],
                        "stop_reason": None,
                        "stop_sequence": None,
                        "usage": {"input_tokens": self._input_tokens, "output_tokens": 0},
                    },
                },
            )
        ]

    def _open_text_block(self) -> list[bytes]:
        """Abre el content_block de texto (index 0)."""
        self._text_block_open = True
        return [
            _sse(
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": _TEXT_BLOCK_TYPE, "text": ""},
                },
            )
        ]

    def _close_text_block(self) -> list[bytes]:
        """Cierra el content_block de texto si estaba abierto."""
        if not self._text_block_open:
            return []
        self._text_block_open = False
        return [_sse("content_block_stop", {"type": "content_block_stop", "index": 0})]

    def _emit_text_delta(self, text: str) -> list[bytes]:
        """Emite un text_delta del bloque 0, abriendolo si hace falta."""
        out: list[bytes] = []
        if not self._text_block_open:
            out.extend(self._open_text_block())
        out.append(
            _sse(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": text},
                },
            )
        )
        return out

    def _stream_text_piece(self, piece: str) -> list[bytes]:
        """Streamea texto reteniendo lo que pueda ser un tool-call textual.

        En modo normal emite todo salvo una cola corta que podria ser el
        arranque de un marker de dialecto (se resuelve en el proximo delta o en
        ``_finish``/``flush``). Si aparece un marker completo, emite el texto
        previo y pasa a ``_dialect_mode``: desde ahi TODO se retiene hasta el
        cierre del stream, donde se parsea como tool-calls (o se re-emite como
        texto si no era parseable — no se pierde contenido).
        """
        self._pending_text += piece
        if self._dialect_mode:
            return []
        earliest: int | None = None
        for marker in _DIALECT_MARKERS:
            found = self._pending_text.find(marker)
            if found != -1 and (earliest is None or found < earliest):
                earliest = found
        if earliest is not None:
            out: list[bytes] = []
            prefix = self._pending_text[:earliest]
            if prefix:
                out.extend(self._emit_text_delta(prefix))
            self._pending_text = self._pending_text[earliest:]
            self._dialect_mode = True
            return out
        # Sin marker completo: retener solo la cola que podria ser el inicio de uno.
        keep = 0
        max_tail = min(len(self._pending_text), _MAX_MARKER_LEN - 1)
        for k in range(max_tail, 0, -1):
            tail = self._pending_text[-k:]
            if any(m.startswith(tail) for m in _DIALECT_MARKERS):
                keep = k
                break
        emit_upto = len(self._pending_text) - keep
        if emit_upto <= 0:
            return []
        out = self._emit_text_delta(self._pending_text[:emit_upto])
        self._pending_text = self._pending_text[emit_upto:]
        return out

    def _emit_dialect_tool_blocks(self, calls: list[dict[str, Any]]) -> list[bytes]:
        """Emite content blocks tool_use completos (start/delta/stop) por dialecto."""
        out: list[bytes] = []
        if self._text_block_open:
            out.extend(self._close_text_block())
        base_index = 1 + len(self._tool_blocks)
        for i, call in enumerate(calls):
            block_index = base_index + i
            tool_id = f"toolu_proxy_dialect_{i}"
            out.append(
                _sse(
                    "content_block_start",
                    {
                        "type": "content_block_start",
                        "index": block_index,
                        "content_block": {
                            "type": "tool_use",
                            "id": tool_id,
                            "name": call["name"],
                            "input": {},
                        },
                    },
                )
            )
            out.append(
                _sse(
                    "content_block_delta",
                    {
                        "type": "content_block_delta",
                        "index": block_index,
                        "delta": {
                            "type": "input_json_delta",
                            "partial_json": json.dumps(call["input"], ensure_ascii=False),
                        },
                    },
                )
            )
            out.append(
                _sse(
                    "content_block_stop",
                    {"type": "content_block_stop", "index": block_index},
                )
            )
        return out

    def _resolve_pending_text(self) -> tuple[list[bytes], bool]:
        """Resuelve el texto retenido al cierre: tool-calls de dialecto o prosa.

        Returns:
            ``(eventos, hubo_tool_calls_de_dialecto)`` — si hubo, el caller debe
            reportar ``stop_reason: tool_use``.
        """
        pending, self._pending_text = self._pending_text, ""
        dialect, self._dialect_mode = self._dialect_mode, False
        if not pending:
            return [], False
        if dialect:
            calls = _parse_dialect_tool_calls(pending)
            if calls:
                return self._emit_dialect_tool_blocks(calls), True
        # Prosa normal (o dialecto no parseable): emitir tal cual, sin perder nada.
        return self._emit_text_delta(pending), False

    def feed(self, raw_chunk: bytes) -> list[bytes]:
        """Procesa un chunk crudo del stream OpenAI y devuelve eventos SSE Anthropic.

        OpenAI manda ``data: {json}\\n\\n`` por delta; los chunks pueden venir
        partidos o agrupados, asi que parseamos por lineas ``data:``.
        """
        out: list[bytes] = []
        if not raw_chunk:
            return out

        # Un chunk TCP puede contener varios `data:` o uno cortado a mitad de
        # linea/caracter. Acumulamos bytes y procesamos SOLO lineas completas
        # (terminadas en \n); el resto queda en el buffer para el proximo feed().
        # ponytail: sin cap de tamano — el peor caso es UNA linea SSE del upstream
        # (un delta JSON, tipicamente KBs); si algun backend emitiera lineas de
        # cientos de MB habria que agregar un limite con descarte explicito.
        self._line_buffer += raw_chunk
        *complete_lines, self._line_buffer = self._line_buffer.split(b"\n")
        for raw_line in complete_lines:
            out.extend(self._process_line(raw_line))
        return out

    def _process_line(self, raw_line: bytes) -> list[bytes]:
        """Procesa UNA linea completa del stream SSE OpenAI."""
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line.startswith("data:"):
            return []
        data_str = line[len("data:") :].strip()
        if data_str == "[DONE]":
            # El cierre final lo hace flush() para garantizar orden de stop.
            return []
        try:
            delta_obj = json.loads(data_str)
        except json.JSONDecodeError:
            # Linea completa pero corrupta de verdad (ya no es un corte de chunk:
            # el re-ensamblado lo resuelve el buffer). Se descarta sin tumbar el stream.
            return []
        return self._handle_delta(delta_obj)

    def _handle_delta(self, delta_obj: dict[str, Any]) -> list[bytes]:
        """Convierte UN objeto delta de OpenAI a eventos Anthropic."""
        out: list[bytes] = []
        if not self._message_started:
            out.extend(self._begin_message())

        # Token de uso ANTES del early-return por choices vacio: con
        # stream_options.include_usage, OpenAI manda el usage en un chunk final
        # extra SIN choices — si se lee despues del return, se pierde siempre.
        usage = delta_obj.get("usage")
        if isinstance(usage, dict):
            if usage.get("prompt_tokens"):
                self._input_tokens = int(usage["prompt_tokens"])
            if usage.get("completion_tokens"):
                self._output_tokens = int(usage["completion_tokens"])

        choices = delta_obj.get("choices") or []
        if not choices:
            return out
        choice = choices[0]
        delta = choice.get("delta") or {}

        # Texto incremental -> content_block_delta del bloque 0 (con retencion
        # de posibles tool-calls textuales — dialectos GLM/Qwen/Ollama).
        text_piece = delta.get("content")
        if isinstance(text_piece, str) and text_piece:
            out.extend(self._stream_text_piece(text_piece))

        # tool_calls incremental -> tool_use content blocks (index a partir de 1).
        tool_calls = delta.get("tool_calls")
        if isinstance(tool_calls, list):
            if tool_calls and self._pending_text and not self._dialect_mode:
                # Llego un tool_call estructurado: la cola de texto retenida ya no
                # puede ser un dialecto — emitirla antes de cerrar el bloque texto.
                out.extend(self._emit_text_delta(self._pending_text))
                self._pending_text = ""
            for tc in tool_calls:
                if not isinstance(tc, dict):
                    continue
                idx = int(tc.get("index", 0))
                block = self._tool_blocks.get(idx)
                if block is None:
                    # Nuevo tool_use: reservar index despues del bloque de texto.
                    block_index = idx + 1
                    tool_id = str(tc.get("id", f"toolu_proxy_{idx}"))
                    fn = tc.get("function") or {}
                    name = str(fn.get("name", ""))
                    block = {
                        "index": block_index,
                        "id": tool_id,
                        "name": name,
                        "arguments": "",
                    }
                    self._tool_blocks[idx] = block
                    if self._text_block_open:
                        out.extend(self._close_text_block())
                    out.append(
                        _sse(
                            "content_block_start",
                            {
                                "type": "content_block_start",
                                "index": block_index,
                                "content_block": {
                                    "type": "tool_use",
                                    "id": tool_id,
                                    "name": name,
                                    "input": {},
                                },
                            },
                        )
                    )
                # Acumular argumentos (viene en cachitos delta).
                fn = tc.get("function") or {}
                arg_piece = fn.get("arguments")
                if isinstance(arg_piece, str) and arg_piece:
                    block["arguments"] += arg_piece
                    out.append(
                        _sse(
                            "content_block_delta",
                            {
                                "type": "content_block_delta",
                                "index": block["index"],
                                "delta": {
                                    "type": "input_json_delta",
                                    "partial_json": arg_piece,
                                },
                            },
                        )
                    )

        # finish_reason -> cerramos bloques abiertos y señalamos stop.
        finish_reason = choice.get("finish_reason")
        if finish_reason:
            out.extend(self._finish(finish_reason))
        return out

    def _finish(self, finish_reason: str) -> list[bytes]:
        """Cierra todos los content blocks y emite message_delta + message_stop."""
        out: list[bytes] = []
        resolved, had_dialect_tools = self._resolve_pending_text()
        out.extend(resolved)
        if had_dialect_tools:
            # El "texto" era un tool-call de dialecto: el stop real es tool_use.
            finish_reason = "tool_calls"
        out.extend(self._close_text_block())
        for block in self._tool_blocks.values():
            out.append(
                _sse("content_block_stop", {"type": "content_block_stop", "index": block["index"]})
            )
        # Mapeo grosero de stop reasons OpenAI -> Anthropic.
        stop_reason = {
            "stop": "end_turn",
            "length": "max_tokens",
            "tool_calls": "tool_use",
            "function_call": "tool_use",
        }.get(finish_reason, "end_turn")
        out.append(
            _sse(
                "message_delta",
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                    "usage": {"output_tokens": self._output_tokens},
                },
            )
        )
        out.append(_sse("message_stop", {"type": "message_stop"}))
        # El stream ya cerro limpio: marcar para que flush() sea no-op y los tool
        # blocks no se re-cierren (evita message_stop duplicado hacia Claude Code).
        self._tool_blocks.clear()
        self._finished = True
        return out

    def flush(self) -> list[bytes]:
        """Emite el cierre del stream si el upstream no mando finish_reason.

        Garantiza que Claude Code siempre reciba message_stop aun si el backend
        local corto el stream abruptamente (comun en Ollama con --nowordwrap).
        Si ``_finish`` ya cerro el stream (llego un finish_reason), es no-op.
        """
        if self._finished:
            return []
        out: list[bytes] = []
        # Drenar la ultima linea bufferizada si el upstream cerro sin \n final
        # (completa pero sin terminador). Puede traer texto o el finish_reason.
        if self._line_buffer:
            pending, self._line_buffer = self._line_buffer, b""
            out.extend(self._process_line(pending))
            if self._finished:
                # La linea drenada traia finish_reason -> _finish ya cerro todo.
                return out
        if not self._message_started:
            # El upstream jamas respondio con datos validos: mensaje vacio legitimo.
            out.extend(self._begin_message())
            out.extend(self._open_text_block())
        resolved, had_dialect_tools = self._resolve_pending_text()
        out.extend(resolved)
        out.extend(self._close_text_block())
        for block in self._tool_blocks.values():
            out.append(
                _sse("content_block_stop", {"type": "content_block_stop", "index": block["index"]})
            )
        # Si ya emitimos message_stop via _finish, no duplicar.
        if not any(b"message_stop" in b for b in out[-3:]):
            stop_reason = "tool_use" if had_dialect_tools else "end_turn"
            out.append(
                _sse(
                    "message_delta",
                    {
                        "type": "message_delta",
                        "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                        "usage": {"output_tokens": self._output_tokens},
                    },
                )
            )
            out.append(_sse("message_stop", {"type": "message_stop"}))
        return out


async def translate_stream(
    upstream_content: AsyncIterator[bytes],
    model: str,
) -> AsyncIterator[bytes]:
    """Traduce un stream OpenAI upstream a eventos SSE Anthropic.

    Helper async para usar directo en el proxy::

        async for sse_bytes in translate_stream(upstream.content, model):
            await response.write(sse_bytes)

    Args:
        upstream_content: Iterator de chunks bytes del upstream (``upstream.content``).
        model: Nombre del modelo (para el campo ``message.model``).
    """
    translator = OpenAiStreamTranslator(model=model)
    async for chunk in upstream_content:
        for sse_bytes in translator.feed(chunk):
            yield sse_bytes
    for sse_bytes in translator.flush():
        yield sse_bytes
