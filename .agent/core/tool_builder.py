#!/usr/bin/env python3
"""
Tool Builder - Genera agentes y MCP tool definitions desde lenguaje natural.

Permite que usuarios no-técnicos creen agentes sin código:
- Describir workflow en lenguaje natural
- El builder genera MCP tool definitions
- OAuth para calendar, email, spreadsheets
- Registra el agente automáticamente en el orchestrator
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("antigravity.tool_builder")

# ============================================================================
# ENUMS
# ============================================================================


class ToolCategory(str, Enum):
    """Categorías de herramientas predefinidas."""

    CALENDAR = "calendar"
    EMAIL = "email"
    SPREADSHEET = "spreadsheet"
    WEB = "web"
    FILE = "file"
    NOTIFICATION = "notification"
    MEMORY = "memory"
    AGENT = "agent"
    CUSTOM = "custom"


class OAuthProvider(str, Enum):
    """Providers OAuth soportados."""

    GOOGLE = "google"
    MICROSOFT = "microsoft"
    NOTION = "notion"
    SLACK = "slack"
    NONE = "none"


class ValidationSeverity(str, Enum):
    """Severidad de validación."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# ============================================================================
# SCHEMAS - Tool Definitions
# ============================================================================


class ToolParameter(BaseModel):
    """Parámetro de una tool definition."""

    name: str = Field(..., description="Nombre del parámetro")
    type: str = Field(default="string", description="Tipo (string, number, boolean, array, object)")
    description: str = Field(..., description="Descripción para el usuario")
    required: bool = Field(default=False, description="Si es obligatorio")
    default: str | None = Field(default=None, description="Valor por defecto")
    enum_values: list[str] | None = Field(default=None, description="Valores permitidos")


class ToolDefinition(BaseModel):
    """Definición completa de una tool MCP."""

    id: str = Field(default_factory=lambda: f"tool_{uuid.uuid4().hex[:8]}")
    name: str = Field(..., description="Nombre de la tool (snake_case)")
    display_name: str = Field(..., description="Nombre legible para UI")
    description: str = Field(..., description="Descripción de qué hace la tool")
    category: ToolCategory = Field(..., description="Categoría de la tool")
    parameters: list[ToolParameter] = Field(
        default_factory=list, description="Parámetros de entrada"
    )
    output_schema: dict[str, Any] = Field(
        default_factory=dict, description="Schema del output (JSON Schema)"
    )
    oauth_provider: OAuthProvider | None = Field(
        default=None, description="Provider OAuth si requiere"
    )
    oauth_scopes: list[str] = Field(default_factory=list, description="Scopes OAuth requeridos")
    endpoint: str | None = Field(default=None, description="Endpoint HTTP si aplica")
    requires_confirmation: bool = Field(
        default=False, description="Si requiere confirmación antes de ejecutar"
    )
    examples: list[str] = Field(default_factory=list, description="Ejemplos de uso en prompts")


class ValidationIssue(BaseModel):
    """Problema de validación encontrado."""

    severity: ValidationSeverity
    message: str
    tool_id: str | None = None
    field: str | None = None
    suggestion: str | None = None


class ValidationResult(BaseModel):
    """Resultado de validación de tools."""

    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    score: float = Field(ge=0.0, le=1.0, description="Score de coherencia 0-1")

    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]


class AgentConfig(BaseModel):
    """Configuración generada de un agente."""

    id: str = Field(default_factory=lambda: f"agent_{uuid.uuid4().hex[:8]}")
    name: str = Field(..., description="Nombre del agente")
    description: str = Field(..., description="Descripción del agente")
    version: str = Field(default="1.0.0")
    created_at: datetime = Field(default_factory=datetime.now)
    tools: list[ToolDefinition] = Field(default_factory=list)
    oauth_configs: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="Config OAuth por provider"
    )
    model: str = Field(default="sonnet", description="Modelo recomendado")
    tier: str = Field(default="specialized", description="Tier del agente")
    metadata: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# TEMPLATES DE TOOLS PREDEFINIDAS
# ============================================================================

TOOL_TEMPLATES: dict[str, ToolDefinition] = {}

# ---- Calendar ----
TOOL_TEMPLATES["calendar_create_event"] = ToolDefinition(
    id="tool_calendar_create",
    name="calendar_create_event",
    display_name="Crear evento de calendario",
    description="Crea un nuevo evento en el calendario con título, hora, ubicación y asistentes.",
    category=ToolCategory.CALENDAR,
    oauth_provider=OAuthProvider.GOOGLE,
    oauth_scopes=["https://www.googleapis.com/auth/calendar"],
    endpoint="https://www.googleapis.com/calendar/v3/calendars/primary/events",
    parameters=[
        ToolParameter(
            name="title",
            type="string",
            description="Título del evento",
            required=True,
        ),
        ToolParameter(
            name="start_time",
            type="string",
            description="Fecha y hora de inicio (ISO 8601)",
            required=True,
        ),
        ToolParameter(
            name="end_time",
            type="string",
            description="Fecha y hora de fin (ISO 8601)",
            required=True,
        ),
        ToolParameter(
            name="location",
            type="string",
            description="Ubicación del evento",
            required=False,
        ),
        ToolParameter(
            name="attendees",
            type="array",
            description="Lista de emails de asistentes",
            required=False,
        ),
        ToolParameter(
            name="description",
            type="string",
            description="Descripción del evento",
            required=False,
        ),
    ],
    output_schema={
        "type": "object",
        "properties": {
            "event_id": {"type": "string"},
            "title": {"type": "string"},
            "start": {"type": "string"},
            "status": {"type": "string"},
        },
    },
    examples=[
        "Crea una reunión con maria@ejemplo.com mañana a las 10am",
        "Agrega un recordatorio para la revisión de presupuesto el viernes",
    ],
)

TOOL_TEMPLATES["calendar_list_events"] = ToolDefinition(
    id="tool_calendar_list",
    name="calendar_list_events",
    display_name="Listar eventos",
    description="Lista los eventos del calendario en un rango de fechas.",
    category=ToolCategory.CALENDAR,
    oauth_provider=OAuthProvider.GOOGLE,
    oauth_scopes=["https://www.googleapis.com/auth/calendar.readonly"],
    parameters=[
        ToolParameter(
            name="start_date",
            type="string",
            description="Fecha de inicio (ISO 8601)",
            required=True,
        ),
        ToolParameter(
            name="end_date",
            type="string",
            description="Fecha de fin (ISO 8601)",
            required=True,
        ),
        ToolParameter(
            name="max_results",
            type="number",
            description="Máximo de eventos a devolver",
            required=False,
            default="50",
        ),
    ],
    output_schema={
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "title": {"type": "string"},
                "start": {"type": "string"},
                "end": {"type": "string"},
            },
        },
    },
)

TOOL_TEMPLATES["calendar_delete_event"] = ToolDefinition(
    id="tool_calendar_delete",
    name="calendar_delete_event",
    display_name="Eliminar evento",
    description="Elimina un evento del calendario por su ID.",
    category=ToolCategory.CALENDAR,
    oauth_provider=OAuthProvider.GOOGLE,
    oauth_scopes=["https://www.googleapis.com/auth/calendar"],
    parameters=[
        ToolParameter(
            name="event_id",
            type="string",
            description="ID del evento a eliminar",
            required=True,
        ),
    ],
    requires_confirmation=True,
)

# ---- Email ----
TOOL_TEMPLATES["email_send"] = ToolDefinition(
    id="tool_email_send",
    name="email_send",
    display_name="Enviar email",
    description="Envía un email con asunto, cuerpo y destinatarios opcionales (CC/CCO).",
    category=ToolCategory.EMAIL,
    oauth_provider=OAuthProvider.GOOGLE,
    oauth_scopes=["https://www.googleapis.com/auth/gmail.send"],
    endpoint="https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
    parameters=[
        ToolParameter(
            name="to",
            type="string",
            description="Destinatario principal (email)",
            required=True,
        ),
        ToolParameter(
            name="subject",
            type="string",
            description="Asunto del email",
            required=True,
        ),
        ToolParameter(
            name="body",
            type="string",
            description="Cuerpo del email (puede ser HTML)",
            required=True,
        ),
        ToolParameter(
            name="cc",
            type="string",
            description="Destinatarios en copia (separados por coma)",
            required=False,
        ),
        ToolParameter(
            name="bcc",
            type="string",
            description="Destinatarios en copia oculta (separados por coma)",
            required=False,
        ),
    ],
    output_schema={
        "type": "object",
        "properties": {
            "message_id": {"type": "string"},
            "to": {"type": "string"},
            "status": {"type": "string"},
        },
    },
    examples=[
        "Envía un email a juan@empresa.com confirmando la reunión de mañana",
        "Manda un resumen semanal al equipo",
    ],
)

TOOL_TEMPLATES["email_read"] = ToolDefinition(
    id="tool_email_read",
    name="email_read_emails",
    display_name="Leer emails",
    description="Lee emails no leídos o búsqueda por remitente/asunto.",
    category=ToolCategory.EMAIL,
    oauth_provider=OAuthProvider.GOOGLE,
    oauth_scopes=["https://www.googleapis.com/auth/gmail.readonly"],
    parameters=[
        ToolParameter(
            name="max_results",
            type="number",
            description="Cantidad de emails a leer",
            required=False,
            default="10",
        ),
        ToolParameter(
            name="query",
            type="string",
            description="Filtro de búsqueda (Gmail syntax)",
            required=False,
        ),
    ],
)

TOOL_TEMPLATES["email_search"] = ToolDefinition(
    id="tool_email_search",
    name="email_search",
    display_name="Buscar emails",
    description="Busca emails por remitente, asunto o contenido.",
    category=ToolCategory.EMAIL,
    oauth_provider=OAuthProvider.GOOGLE,
    oauth_scopes=["https://www.googleapis.com/auth/gmail.readonly"],
    parameters=[
        ToolParameter(
            name="query",
            type="string",
            description="Término de búsqueda",
            required=True,
        ),
        ToolParameter(
            name="max_results",
            type="number",
            description="Máximo de resultados",
            required=False,
            default="20",
        ),
    ],
    examples=[
        "Busca emails de factura en el último mes",
        "Encuentra emails de cambios de última hora",
    ],
)

# ---- Spreadsheet ----
TOOL_TEMPLATES["sheet_read"] = ToolDefinition(
    id="tool_sheet_read",
    name="spreadsheet_read",
    display_name="Leer planilla",
    description="Lee datos de una hoja de cálculo Google Sheets.",
    category=ToolCategory.SPREADSHEET,
    oauth_provider=OAuthProvider.GOOGLE,
    oauth_scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    parameters=[
        ToolParameter(
            name="spreadsheet_id",
            type="string",
            description="ID de la spreadsheet (de la URL)",
            required=True,
        ),
        ToolParameter(
            name="range",
            type="string",
            description="Rango a leer (ej. 'Sheet1!A1:D10')",
            required=False,
        ),
        ToolParameter(
            name="sheet_name",
            type="string",
            description="Nombre de la hoja",
            required=False,
        ),
    ],
    output_schema={"type": "array", "description": "Datos de la spreadsheet"},
)

TOOL_TEMPLATES["sheet_write"] = ToolDefinition(
    id="tool_sheet_write",
    name="spreadsheet_write",
    display_name="Escribir en planilla",
    description="Escribe datos en una hoja de cálculo Google Sheets.",
    category=ToolCategory.SPREADSHEET,
    oauth_provider=OAuthProvider.GOOGLE,
    oauth_scopes=["https://www.googleapis.com/auth/spreadsheets"],
    parameters=[
        ToolParameter(
            name="spreadsheet_id",
            type="string",
            description="ID de la spreadsheet",
            required=True,
        ),
        ToolParameter(
            name="range",
            type="string",
            description="Rango a escribir (ej. 'Sheet1!A1')",
            required=True,
        ),
        ToolParameter(
            name="values",
            type="array",
            description="Datos a escribir (array de arrays)",
            required=True,
        ),
        ToolParameter(
            name="sheet_name",
            type="string",
            description="Nombre de la hoja",
            required=False,
        ),
    ],
)

TOOL_TEMPLATES["sheet_append"] = ToolDefinition(
    id="tool_sheet_append",
    name="spreadsheet_append_row",
    display_name="Agregar fila",
    description="Agrega una nueva fila al final de una hoja de cálculo.",
    category=ToolCategory.SPREADSHEET,
    oauth_provider=OAuthProvider.GOOGLE,
    oauth_scopes=["https://www.googleapis.com/auth/spreadsheets"],
    parameters=[
        ToolParameter(
            name="spreadsheet_id",
            type="string",
            description="ID de la spreadsheet",
            required=True,
        ),
        ToolParameter(
            name="values",
            type="array",
            description="Valores de la fila",
            required=True,
        ),
        ToolParameter(
            name="sheet_name",
            type="string",
            description="Nombre de la hoja",
            required=False,
        ),
    ],
    examples=[
        "Agrega una nueva fila con los datos del cliente",
        "Añade el registro de ventas al final",
    ],
)

# ---- Web ----
TOOL_TEMPLATES["web_fetch"] = ToolDefinition(
    id="tool_web_fetch",
    name="web_fetch_url",
    display_name="Obtener página web",
    description="Obtiene el contenido HTML de una URL.",
    category=ToolCategory.WEB,
    parameters=[
        ToolParameter(
            name="url",
            type="string",
            description="URL a obtener",
            required=True,
        ),
        ToolParameter(
            name="extract_links",
            type="boolean",
            description="Extraer enlaces del contenido",
            required=False,
            default="false",
        ),
    ],
    output_schema={
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "title": {"type": "string"},
            "content": {"type": "string"},
            "links": {"type": "array"},
        },
    },
)

TOOL_TEMPLATES["web_search"] = ToolDefinition(
    id="tool_web_search",
    name="web_search",
    display_name="Buscar en la web",
    description="Busca información en la web.",
    category=ToolCategory.WEB,
    parameters=[
        ToolParameter(
            name="query",
            type="string",
            description="Consulta de búsqueda",
            required=True,
        ),
        ToolParameter(
            name="max_results",
            type="number",
            description="Cantidad de resultados",
            required=False,
            default="5",
        ),
    ],
    examples=[
        "Busca las últimas noticias sobre inteligencia artificial",
        "Encuentra información sobre el nuevo marco legal",
    ],
)

# ---- File ----
TOOL_TEMPLATES["file_read"] = ToolDefinition(
    id="tool_file_read",
    name="file_read",
    display_name="Leer archivo",
    description="Lee el contenido de un archivo de texto.",
    category=ToolCategory.FILE,
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Ruta del archivo",
            required=True,
        ),
        ToolParameter(
            name="max_lines",
            type="number",
            description="Máximo de líneas a leer",
            required=False,
            default="500",
        ),
    ],
)

TOOL_TEMPLATES["file_write"] = ToolDefinition(
    id="tool_file_write",
    name="file_write",
    display_name="Escribir archivo",
    description="Escribe contenido en un archivo.",
    category=ToolCategory.FILE,
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Ruta del archivo",
            required=True,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="Contenido a escribir",
            required=True,
        ),
    ],
    requires_confirmation=True,
)

TOOL_TEMPLATES["file_list"] = ToolDefinition(
    id="tool_file_list",
    name="file_list",
    display_name="Listar archivos",
    description="Lista archivos en un directorio.",
    category=ToolCategory.FILE,
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Ruta del directorio",
            required=True,
        ),
        ToolParameter(
            name="pattern",
            type="string",
            description="Patrón glob para filtrar (ej. *.txt)",
            required=False,
        ),
    ],
)

# ---- Notification ----
TOOL_TEMPLATES["notification_send"] = ToolDefinition(
    id="tool_notification",
    name="notification_send",
    display_name="Enviar notificación",
    description="Envía una notificación push o muestra un alert.",
    category=ToolCategory.NOTIFICATION,
    parameters=[
        ToolParameter(
            name="title",
            type="string",
            description="Título de la notificación",
            required=True,
        ),
        ToolParameter(
            name="body",
            type="string",
            description="Cuerpo del mensaje",
            required=True,
        ),
        ToolParameter(
            name="urgency",
            type="string",
            description="Nivel de urgencia (low, normal, high)",
            required=False,
            default="normal",
            enum_values=["low", "normal", "high"],
        ),
    ],
    examples=[
        "Notifica al equipo que el deploy está listo",
        "Alerta sobre errores críticos en producción",
    ],
)

# ---- Memory ----
TOOL_TEMPLATES["memory_save"] = ToolDefinition(
    id="tool_memory_save",
    name="memory_save",
    display_name="Guardar en memoria",
    description="Guarda información importante en la memoria del ecosistema.",
    category=ToolCategory.MEMORY,
    parameters=[
        ToolParameter(
            name="content",
            type="string",
            description="Contenido a guardar",
            required=True,
        ),
        ToolParameter(
            name="category",
            type="string",
            description="Categoría (decision, bugfix, pattern, session)",
            required=False,
            default="general",
            enum_values=["decision", "bugfix", "pattern", "session", "general"],
        ),
        ToolParameter(
            name="tags",
            type="array",
            description="Tags para categorizar",
            required=False,
        ),
    ],
    examples=[
        "Guarda la decisión de usar PostgreSQL como base de datos",
        "Memo sobre el patrón de autenticación elegido",
    ],
)

TOOL_TEMPLATES["memory_search"] = ToolDefinition(
    id="tool_memory_search",
    name="memory_search",
    display_name="Buscar en memoria",
    description="Busca en la memoria del ecosistema con búsqueda semántica.",
    category=ToolCategory.MEMORY,
    parameters=[
        ToolParameter(
            name="query",
            type="string",
            description="Consulta de búsqueda",
            required=True,
        ),
        ToolParameter(
            name="category",
            type="string",
            description="Filtrar por categoría",
            required=False,
        ),
        ToolParameter(
            name="max_results",
            type="number",
            description="Máximo de resultados",
            required=False,
            default="5",
        ),
    ],
)

# ---- Agent ----
TOOL_TEMPLATES["agent_invoke"] = ToolDefinition(
    id="tool_agent_invoke",
    name="agent_invoke",
    display_name="Invocar agente",
    description="Invoca otro agente del ecosistema para realizar una tarea específica.",
    category=ToolCategory.AGENT,
    parameters=[
        ToolParameter(
            name="agent_name",
            type="string",
            description="Nombre del agente a invocar",
            required=True,
        ),
        ToolParameter(
            name="task",
            type="string",
            description="Tarea para el agente",
            required=True,
        ),
        ToolParameter(
            name="context",
            type="object",
            description="Contexto adicional para el agente",
            required=False,
        ),
    ],
    examples=[
        "Ejecuta el agente de análisis de código en la carpeta src",
        "Pide al agente de calidad que revise los tests",
    ],
)


# ============================================================================
# TEMPLATE REGISTRY
# ============================================================================

ALL_TEMPLATES: list[ToolDefinition] = list(TOOL_TEMPLATES.values())

TEMPLATE_BY_CATEGORY: dict[ToolCategory, list[ToolDefinition]] = {}
for tool in ALL_TEMPLATES:
    if tool.category not in TEMPLATE_BY_CATEGORY:
        TEMPLATE_BY_CATEGORY[tool.category] = []
    TEMPLATE_BY_CATEGORY[tool.category].append(tool)


# ============================================================================
# PATTERN MATCHING - NL → Tools
# ============================================================================

# Patrones keyword → categoría y tool específica
TOOL_PATTERNS: list[tuple[re.Pattern[str], list[str], ToolCategory]] = [
    # Calendar
    (
        re.compile(r"calendar|evento|reunión|reunion|cita|agenda|meeting|schedule", re.I),
        ["calendar_create_event", "calendar_list_events"],
        ToolCategory.CALENDAR,
    ),
    (
        re.compile(r"crear\s+(evento|reunión|reunion|cita|calendar)", re.I),
        ["calendar_create_event"],
        ToolCategory.CALENDAR,
    ),
    (
        re.compile(r"listar\s+(eventos|calendario)", re.I),
        ["calendar_list_events"],
        ToolCategory.CALENDAR,
    ),
    (
        re.compile(r"borrar\s+(evento|reunión|cita)", re.I),
        ["calendar_delete_event"],
        ToolCategory.CALENDAR,
    ),
    # Email
    (
        re.compile(r"email|correo|gmail|enviar\s+(email|correo|mail)", re.I),
        ["email_send", "email_read", "email_search"],
        ToolCategory.EMAIL,
    ),
    (re.compile(r"enviar\s+(email|correo|mail)", re.I), ["email_send"], ToolCategory.EMAIL),
    (re.compile(r"buscar\s+(email|correo)", re.I), ["email_search"], ToolCategory.EMAIL),
    (re.compile(r"leer\s+(email|correo|inbox)", re.I), ["email_read"], ToolCategory.EMAIL),
    # Spreadsheet
    (
        re.compile(r"excel|sheet|planilla|spreadsheet|google\s*sheets", re.I),
        ["spreadsheet_read", "spreadsheet_write", "spreadsheet_append_row"],
        ToolCategory.SPREADSHEET,
    ),
    (
        re.compile(r"leer\s+(excel|planilla|sheet)", re.I),
        ["spreadsheet_read"],
        ToolCategory.SPREADSHEET,
    ),
    (
        re.compile(r"escribir\s+en\s+(excel|planilla|sheet)", re.I),
        ["spreadsheet_write"],
        ToolCategory.SPREADSHEET,
    ),
    (
        re.compile(r"agregar\s+fila|datos\s+nuevos", re.I),
        ["spreadsheet_append_row"],
        ToolCategory.SPREADSHEET,
    ),
    # Web
    (
        re.compile(r"web|página|URL|fetch|scrape|buscar\s+en\s+internet", re.I),
        ["web_fetch_url", "web_search"],
        ToolCategory.WEB,
    ),
    (re.compile(r"buscar\s+en\s+(web|internet|google)", re.I), ["web_search"], ToolCategory.WEB),
    # File
    (
        re.compile(r"archivo|fichero|leer\s+archivo|file|directorio|folder", re.I),
        ["file_read", "file_write", "file_list"],
        ToolCategory.FILE,
    ),
    (
        re.compile(r"escribir\s+(en\s+)?archivo|crear\s+archivo", re.I),
        ["file_write"],
        ToolCategory.FILE,
    ),
    # Notification
    (
        re.compile(r"notificar|alerta|alert|notification|push|aviso", re.I),
        ["notification_send"],
        ToolCategory.NOTIFICATION,
    ),
    # Memory
    (
        re.compile(r"memoria|recordar|guardar|remember|memory", re.I),
        ["memory_save", "memory_search"],
        ToolCategory.MEMORY,
    ),
    # Agent
    (
        re.compile(r"agente|invoque|invoke|ejecutar\s+agente|ejecutar", re.I),
        ["agent_invoke"],
        ToolCategory.AGENT,
    ),
]


# ============================================================================
# OAUTH CONFIG TEMPLATES
# ============================================================================

OAUTH_CONFIGS: dict[str, dict[str, Any]] = {
    "google": {
        "provider": "google",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": [
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/spreadsheets",
        ],
        "default_scopes": ["https://www.googleapis.com/auth/calendar"],
    },
    "microsoft": {
        "provider": "microsoft",
        "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "scopes": ["Calendars.ReadWrite", "Mail.Send", "Files.ReadWrite"],
        "default_scopes": ["Calendars.ReadWrite"],
    },
}


# ============================================================================
# TOOL BUILDER CLASS
# ============================================================================


class ToolBuilder:
    """Generador de agentes y tool definitions desde lenguaje natural."""

    def __init__(self) -> None:
        self.available_tools: list[ToolDefinition] = ALL_TEMPLATES
        self.templates_by_category = TEMPLATE_BY_CATEGORY
        self.oauth_configs = OAUTH_CONFIGS

    @staticmethod
    def _infer_tools_by_keywords(natural_language: str) -> list[ToolDefinition]:
        """Infiere tools por palabras clave cuando ningún patrón matcheó.

        Args:
            natural_language: Descripción en texto libre.

        Returns:
            Lista de ToolDefinition inferidas por intención general.
        """
        text = natural_language.lower()
        keyword_map: list[tuple[list[str], str]] = [
            (["email", "correo", "gmail", "mail"], "email_send"),
            (["calendar", "evento", "reunión", "schedule"], "calendar_list_events"),
            (["datos", "excel", "sheet", "planilla"], "sheet_read"),
            (["notificar", "alert", "aviso"], "notification_send"),
            (["memoria", "recordar", "guardar"], "memory_save"),
        ]
        tools: list[ToolDefinition] = []
        for keywords, tool_id in keyword_map:
            if any(kw in text for kw in keywords):
                tools.append(TOOL_TEMPLATES[tool_id])
        return tools

    def generate_from_description(self, natural_language: str) -> list[ToolDefinition]:
        """Convierte descripción en tool definitions.

        Args:
            natural_language: Descripción del workflow en texto libre.

        Returns:
            Lista de ToolDefinition recomendadas.

        Ejemplo:
            >>> builder = ToolBuilder()
            >>> tools = builder.generate_from_description(
            ...     "Necesito un agente que maneje el calendario y envíe emails de resumen"
            ... )
            >>> [t.name for t in tools]
            ['calendar_list_events', 'email_send']
        """
        matched_ids: set[str] = set()
        matched_tools: list[ToolDefinition] = []

        # Match por patrones keyword
        for pattern, tool_ids, category in TOOL_PATTERNS:
            if pattern.search(natural_language):
                for tool_id in tool_ids:
                    if tool_id in TOOL_TEMPLATES and tool_id not in matched_ids:
                        matched_ids.add(tool_id)
                        matched_tools.append(TOOL_TEMPLATES[tool_id])

        # Si no matcheó nada, inferir por categoría de contexto
        if not matched_tools:
            matched_tools = self._infer_tools_by_keywords(natural_language)

        logger.info(
            "Generated %d tools from description: %s",
            len(matched_tools),
            [t.name for t in matched_tools],
        )
        return matched_tools

    def validate_tools(self, tools: list[ToolDefinition]) -> ValidationResult:
        """Valida que las tools sean seguras y coherentes.

        Args:
            tools: Lista de tools a validar.

        Returns:
            ValidationResult con issues encontrados.
        """
        issues: list[ValidationIssue] = []

        for tool in tools:
            # Validar nombre (snake_case)
            if not re.match(r"^[a-z][a-z0-9_]*$", tool.name):
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        message=f"Tool '{tool.name}' debe usar snake_case",
                        tool_id=tool.id,
                        field="name",
                        suggestion="Usar solo minúsculas, números y guiones bajos",
                    )
                )

            # Validar duplicados
            names = [t.name for t in tools]
            if names.count(tool.name) > 1:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        message=f"Tool '{tool.name}' aparece múltiples veces",
                        tool_id=tool.id,
                        field="name",
                    )
                )

            # Validar OAuth scopes
            if tool.oauth_provider and not tool.oauth_scopes:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        message=f"Tool '{tool.name}' tiene OAuth provider pero sin scopes",
                        tool_id=tool.id,
                        field="oauth_scopes",
                        suggestion="Agregar los scopes necesarios para el provider",
                    )
                )

            # Tool con endpoint pero sin descripción
            if tool.endpoint and not tool.description:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        message=f"Tool '{tool.name}' tiene endpoint pero sin descripción",
                        tool_id=tool.id,
                        field="description",
                    )
                )

        # Score de coherencia
        score = 1.0
        errors = [i for i in issues if i.severity == ValidationSeverity.ERROR]
        warnings = [i for i in issues if i.severity == ValidationSeverity.WARNING]

        if errors:
            score = 0.0
        elif warnings:
            score = 1.0 - (len(warnings) * 0.1)

        return ValidationResult(
            valid=len(errors) == 0,
            issues=issues,
            score=max(0.0, score),
        )

    def build_agent_config(
        self,
        name: str,
        description: str,
        tools: list[ToolDefinition],
        model: str = "sonnet",
        oauth_configs: dict[str, dict[str, Any]] | None = None,
    ) -> AgentConfig:
        """Genera config de agente lista para usar.

        Args:
            name: Nombre del agente (snake_case).
            description: Descripción del workflow.
            tools: Tools seleccionadas.
            model: Modelo recomendado.
            oauth_configs: Configuraciones OAuth por provider.

        Returns:
            AgentConfig con toda la metadata necesaria.
        """
        # Recopilar providers OAuth únicos
        oauth_providers: dict[str, dict[str, Any]] = {}
        for tool in tools:
            if tool.oauth_provider and tool.oauth_provider != OAuthProvider.NONE:
                provider_key = tool.oauth_provider.value
                if provider_key not in oauth_providers:
                    # Inyectar scopes de todas las tools del mismo provider
                    all_scopes: set[str] = set()
                    for t in tools:
                        if t.oauth_provider and t.oauth_provider.value == provider_key:
                            all_scopes.update(t.oauth_scopes)
                    oauth_template = self.oauth_configs.get(provider_key, {})
                    oauth_providers[provider_key] = {
                        **oauth_template,
                        "active_scopes": list(all_scopes),
                    }

        return AgentConfig(
            name=name,
            description=description,
            tools=tools,
            model=model,
            oauth_configs=oauth_providers if oauth_configs is None else oauth_configs,
            metadata={
                "builder_version": "1.0.0",
                "tools_count": len(tools),
                "oauth_providers": list(oauth_providers.keys()),
            },
        )

    def build_agent_directory(
        self,
        config: AgentConfig,
        agents_dir: Path,
        *,
        overwrite: bool = False,
    ) -> Path:
        """Genera el directorio del agente con IDENTITY.md + scripts/main.py.

        Args:
            config: Configuración del agente.
            agents_dir: Directorio base de agentes (`.agent/agents/`).
            overwrite: Si True, sobreescribe agentes existentes.

        Returns:
            Path al directorio creado.

        Raises:
            FileExistsError: Si el agente existe y overwrite=False.
        """
        agent_dir = agents_dir / config.id

        if agent_dir.exists() and not overwrite:
            raise FileExistsError(f"Agent '{config.id}' already exists at {agent_dir}")

        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "memory").mkdir(exist_ok=True)

        # Generar IDENTITY.md
        identity_md = self._generate_identity_md(config)
        (agent_dir / "IDENTITY.md").write_text(identity_md, encoding="utf-8")

        # Generar scripts/main.py
        main_py = self._generate_main_py(config)
        (agent_dir / "scripts").mkdir(exist_ok=True)
        (agent_dir / "scripts" / "main.py").write_text(main_py, encoding="utf-8")

        # Generar config.json

        config_json = config.model_dump_json(indent=2)
        (agent_dir / "config.json").write_text(config_json, encoding="utf-8")

        logger.info("Built agent directory: %s", agent_dir)
        return agent_dir

    def _generate_identity_md(self, config: AgentConfig) -> str:
        """Genera el IDENTITY.md del agente."""
        tools_list = ", ".join([t.name for t in config.tools])
        oauth_note = ""
        if config.oauth_configs:
            providers = ", ".join(config.oauth_configs.keys())
            oauth_note = f"\n- OAuth providers: {providers}"

        return f"""---
name: {config.id}
description: {config.description}
tools: {tools_list}
model: {config.model}
---

# {config.name} Agent

## Descripción
{config.description}

## Herramientas Disponibles
{chr(10).join(f"- **{t.display_name}** (`{t.name}`): {t.description}" for t in config.tools)}

## Configuración
- Model: {config.model}
- Tier: {config.tier}
- Tools: {len(config.tools)}{oauth_note}

## Ejemplos de Uso
{chr(10).join(f"- {ex}" for t in config.tools for ex in (t.examples or []))}

---
Generado por ToolBuilder el {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

    def _generate_main_py(self, config: AgentConfig) -> str:
        """Genera scripts/main.py con los handlers de tools."""

        # Imports de tools
        tool_imports = []
        for tool in config.tools:
            tool_imports.append(f"# {tool.display_name}")
            tool_imports.append(f"# Tool: {tool.name}")

        # Cuerpo principal con handlers
        handler_code = []

        for tool in config.tools:
            param_list = ", ".join(f"{p.name}: {p.type}" for p in tool.parameters)
            handler_code.append(f"""
def handle_{tool.name}({param_list}) -> dict:
    \"\"\"Handler para {tool.display_name}.

    Args:
        {chr(10).join(f"        {p.name}: {p.description}" for p in tool.parameters)}
    Returns:
        Resultado de la operación.
    \"\"\"
    # TODO: implementar lógica de {tool.name}
    return {{
        "status": "ok",
        "tool": "{tool.name}",
        "params": locals(),
    }}
""")

        # Función principal de dispatch
        dispatch_cases = "\n".join(
            f'        "{t.name}": lambda ctx: handle_{t.name}(**ctx),' for t in config.tools
        )

        return f'''#!/usr/bin/env python3
"""
{config.name} - Agente generado por ToolBuilder.

{config.description}
"""

import json
import logging
from typing import Any

logger = logging.getLogger("{config.id}")

{chr(10).join(tool_imports)}

{chr(10).join(handler_code)}

TOOL_HANDLERS = {{
{dispatch_cases}
}}


def execute_tool(tool_name: str, params: dict[str, Any]) -> dict:
    """Ejecuta una tool por nombre.

    Args:
        tool_name: Nombre de la tool.
        params: Parámetros de la tool.

    Returns:
        Resultado de la ejecución.
    """
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return {{"error": f"Tool '{{tool_name}}' no disponible", "tool": tool_name}}

    try:
        return handler(params)
    except Exception as e:
        logger.exception(f"Error executing {{tool_name}}")
        return {{"error": str(e), "tool": tool_name}}


def main() -> None:
    """Entry point del agente."""
    logger.info("Agent %s started", "{config.id}")

    # TODO: integrar con el orchestrator del ecosistema
    # Por ahora expone la interfaz de tools
    print(json.dumps({{
        "agent": "{config.id}",
        "name": "{config.name}",
        "tools": {[t.name for t in config.tools]},
        "status": "ready",
    }}, indent=2))


if __name__ == "__main__":
    main()
'''


# ============================================================================
# CLI INTERFACE
# ============================================================================


def main() -> None:
    """CLI para probar el Tool Builder."""
    import argparse

    parser = argparse.ArgumentParser(description="Agent Tool Builder CLI")
    parser.add_argument("--name", required=True, help="Nombre del agente")
    parser.add_argument("--description", required=True, help="Descripción del workflow")
    parser.add_argument("--agents-dir", default=".agent/agents", help="Directorio de agentes")
    parser.add_argument("--model", default="sonnet", help="Modelo recomendado")
    parser.add_argument("--overwrite", action="store_true", help="Sobreescribir agente existente")
    args = parser.parse_args()

    builder = ToolBuilder()

    # Generar tools
    tools = builder.generate_from_description(args.description)
    print(f"Tools generadas: {[t.name for t in tools]}")

    # Validar
    validation = builder.validate_tools(tools)
    print(f"Validación: {'OK' if validation.valid else 'ERRORES'}")
    for issue in validation.issues:
        print(f"  [{issue.severity.value}] {issue.message}")

    if not validation.valid:
        print("Corregir errores antes de continuar.")
        return

    # Construir config
    config = builder.build_agent_config(
        name=args.name,
        description=args.description,
        tools=tools,
        model=args.model,
    )
    print(f"Agent ID: {config.id}")

    # Crear directorio
    agents_path = Path(args.agents_dir)
    agent_dir = builder.build_agent_directory(config, agents_path, overwrite=args.overwrite)
    print(f"Agente creado en: {agent_dir}")


if __name__ == "__main__":
    main()
