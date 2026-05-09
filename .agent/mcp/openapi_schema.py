#!/usr/bin/env python3
"""
OpenAPI Schema para el Antigravity Gateway.
============================================

Genera el schema OpenAPI 3.0 del gateway.

Extraido de gateway_main.py para modularidad.
"""

from __future__ import annotations

# Constantes necesarias para el schema (importadas desde gateway_main al construir)
# Se pasan como parametros para evitar importacion circular.

VERSION = "3.1.0"
MAX_TASK_LENGTH = 10000
MAX_TIMEOUT_SECONDS = 300
MAX_ITERATIONS_CAP = 50


def build_openapi_schema(
    version: str = VERSION,
    max_task_length: int = MAX_TASK_LENGTH,
    max_timeout_seconds: int = MAX_TIMEOUT_SECONDS,
    max_iterations_cap: int = MAX_ITERATIONS_CAP,
) -> dict:
    """Genera schema OpenAPI 3.0 del gateway.

    Args:
        version: Version del gateway para incluir en el schema.
        max_task_length: Longitud maxima de una tarea.
        max_timeout_seconds: Timeout maximo en segundos.
        max_iterations_cap: Maximo de iteraciones en modo autonomo.

    Returns:
        Diccionario con el schema OpenAPI 3.0.
    """
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Antigravity MCP HTTP Gateway",
            "version": version,
            "description": "REST API para el ecosistema de agentes Antigravity",
        },
        "servers": [{"url": "/v1", "description": "API v1"}],
        "security": [{"ApiKeyAuth": []}],
        "components": {
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                }
            },
            "schemas": {
                "AgentRunRequest": {
                    "type": "object",
                    "required": ["task"],
                    "properties": {
                        "task": {"type": "string", "maxLength": max_task_length},
                        "timeout": {
                            "type": "integer",
                            "default": 120,
                            "maximum": max_timeout_seconds,
                        },
                    },
                },
                "FindAgentRequest": {
                    "type": "object",
                    "required": ["task_description"],
                    "properties": {
                        "task_description": {"type": "string"},
                        "limit": {"type": "integer", "default": 5, "maximum": 20},
                    },
                },
                "AutonomousRequest": {
                    "type": "object",
                    "required": ["agent_name", "task"],
                    "properties": {
                        "agent_name": {"type": "string"},
                        "task": {"type": "string", "maxLength": max_task_length},
                        "max_iterations": {
                            "type": "integer",
                            "default": 15,
                            "maximum": max_iterations_cap,
                        },
                    },
                },
                "TeamRequest": {
                    "type": "object",
                    "required": ["task"],
                    "properties": {
                        "task": {"type": "string"},
                        "agents": {"type": "array", "items": {"type": "string"}},
                        "lead": {"type": "string"},
                        "auto_select": {"type": "boolean", "default": False},
                        "execute": {"type": "boolean", "default": False},
                    },
                },
                "TeamMessageRequest": {
                    "type": "object",
                    "required": ["from_agent", "to_agent", "content"],
                    "properties": {
                        "from_agent": {"type": "string"},
                        "to_agent": {"type": "string"},
                        "content": {"type": "string"},
                    },
                },
                "WatcherEvent": {
                    "type": "object",
                    "required": ["watch_id"],
                    "properties": {
                        "watch_id": {"type": "string"},
                        "label": {"type": "string"},
                        "pattern_label": {"type": "string"},
                        "importance": {
                            "type": "string",
                            "enum": ["low", "high", "critical"],
                        },
                        "line_text": {"type": "string", "maxLength": 500},
                        "line_number": {"type": "integer"},
                        "stream": {
                            "type": "string",
                            "enum": ["stdout", "stderr"],
                        },
                        "matched_at": {"type": "integer"},
                    },
                },
                "WatcherSpawnRequest": {
                    "type": "object",
                    "required": ["cmd"],
                    "properties": {
                        "cmd": {"type": "string"},
                        "cwd": {"type": "string"},
                        "label": {"type": "string"},
                        "env": {"type": "object"},
                        "patterns": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["regex", "label"],
                                "properties": {
                                    "regex": {"type": "string"},
                                    "label": {"type": "string"},
                                    "importance": {
                                        "type": "string",
                                        "enum": ["low", "high", "critical"],
                                    },
                                    "auto_brain_ingest": {"type": "boolean"},
                                },
                            },
                        },
                    },
                },
                "ContextEngineSwitch": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {
                            "type": "string",
                            "enum": [
                                "default",
                                "brain_aware",
                                "delta_aware",
                                "summarizing",
                                "domain_uns",
                                "composite",
                            ],
                        },
                        "project_dir": {"type": "string"},
                    },
                },
                "ContextEnginePreview": {
                    "type": "object",
                    "required": ["task"],
                    "properties": {
                        "task": {"type": "string"},
                        "engine_name": {"type": "string"},
                        "project_dir": {"type": "string"},
                        "current_file": {"type": "string"},
                        "open_files": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "include_prompt": {"type": "boolean", "default": False},
                    },
                },
            },
        },
        "paths": {
            "/": {"get": {"summary": "Info del gateway", "tags": ["Gateway"]}},
            "/health": {"get": {"summary": "Liveness check", "tags": ["Gateway"]}},
            "/ready": {"get": {"summary": "Readiness check", "tags": ["Gateway"]}},
            "/metrics": {"get": {"summary": "Metricas Prometheus", "tags": ["Observability"]}},
            "/agents": {
                "get": {
                    "summary": "Listar agentes",
                    "tags": ["Agents"],
                    "parameters": [
                        {
                            "name": "filter",
                            "in": "query",
                            "schema": {"type": "string", "enum": ["all", "executable"]},
                        },
                        {
                            "name": "offset",
                            "in": "query",
                            "schema": {"type": "integer", "default": 0},
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "schema": {"type": "integer", "default": 50},
                        },
                    ],
                }
            },
            "/agents/{name}": {"get": {"summary": "Info de agente", "tags": ["Agents"]}},
            "/agents/{name}/run": {
                "post": {
                    "summary": "Ejecutar agente",
                    "tags": ["Agents"],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/AgentRunRequest"}
                            }
                        }
                    },
                }
            },
            "/agents/find": {
                "post": {
                    "summary": "Buscar mejor agente",
                    "tags": ["Agents"],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/FindAgentRequest"}
                            }
                        }
                    },
                }
            },
            "/autonomous": {
                "post": {
                    "summary": "Modo autonomo (ReAct)",
                    "tags": ["Autonomous"],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/AutonomousRequest"}
                            }
                        }
                    },
                }
            },
            "/teams": {
                "post": {
                    "summary": "Crear equipo",
                    "tags": ["Teams"],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TeamRequest"}
                            }
                        }
                    },
                }
            },
            "/teams/{id}/message": {
                "post": {
                    "summary": "Mensaje en equipo",
                    "tags": ["Teams"],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TeamMessageRequest"}
                            }
                        }
                    },
                }
            },
            "/skills": {
                "get": {
                    "summary": "Listar skills",
                    "tags": ["Skills"],
                    "parameters": [
                        {"name": "search", "in": "query", "schema": {"type": "string"}},
                        {
                            "name": "offset",
                            "in": "query",
                            "schema": {"type": "integer", "default": 0},
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "schema": {"type": "integer", "default": 50},
                        },
                    ],
                }
            },
            "/skills/{name}": {"get": {"summary": "Leer SKILL.md", "tags": ["Skills"]}},
            "/costs": {"get": {"summary": "Reporte de costos", "tags": ["Costs"]}},
            "/history": {"get": {"summary": "Historial de ejecuciones", "tags": ["History"]}},
            "/events": {"get": {"summary": "SSE stream de eventos", "tags": ["Events"]}},
            "/openapi.json": {"get": {"summary": "Schema OpenAPI", "tags": ["Gateway"]}},
            # ------------------------------------------------------------
            # Process Watcher (v6.1.0+)
            # ------------------------------------------------------------
            "/watcher/events": {
                "post": {
                    "summary": "Ingesta de evento del ProcessWatcher",
                    "tags": ["Watcher"],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/WatcherEvent"}
                            }
                        }
                    },
                }
            },
            "/watcher/events/recent": {
                "get": {
                    "summary": "Historial in-memory reciente",
                    "tags": ["Watcher"],
                    "parameters": [
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50}},
                        {"name": "importance", "in": "query", "schema": {"type": "string", "enum": ["low", "high", "critical"]}},
                    ],
                }
            },
            "/watcher/events/history": {
                "get": {
                    "summary": "Historial persistido SQLite",
                    "tags": ["Watcher"],
                    "parameters": [
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 100}},
                        {"name": "importance", "in": "query", "schema": {"type": "string"}},
                        {"name": "watch_id", "in": "query", "schema": {"type": "string"}},
                    ],
                }
            },
            "/watcher/stream": {
                "get": {
                    "summary": "SSE stream de eventos del watcher",
                    "tags": ["Watcher"],
                    "parameters": [
                        {"name": "importance", "in": "query", "schema": {"type": "string", "enum": ["low", "high", "critical"]}},
                    ],
                }
            },
            "/watcher/status": {
                "get": {"summary": "Estado subsistema watcher", "tags": ["Watcher"]}
            },
            "/watcher/metrics": {
                "get": {
                    "summary": "Counters Prometheus del watcher",
                    "tags": ["Watcher", "Observability"],
                    "description": "Pasa `Accept: application/json` para formato JSON.",
                }
            },
            "/watcher/spawn": {
                "post": {
                    "summary": "Lanzar proceso en el daemon hospedado",
                    "tags": ["Watcher"],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/WatcherSpawnRequest"}
                            }
                        }
                    },
                }
            },
            "/watcher/list": {
                "get": {
                    "summary": "Listar watches activos e historicos",
                    "tags": ["Watcher"],
                    "parameters": [
                        {"name": "include_finished", "in": "query", "schema": {"type": "boolean", "default": True}},
                    ],
                }
            },
            "/watcher/{watch_id}/kill": {
                "post": {"summary": "Terminar proceso activo", "tags": ["Watcher"]}
            },
            "/watcher/{watch_id}/tail": {
                "get": {
                    "summary": "Ultimas lineas stdout/stderr",
                    "tags": ["Watcher"],
                    "parameters": [
                        {"name": "lines", "in": "query", "schema": {"type": "integer", "default": 50}},
                        {"name": "stream", "in": "query", "schema": {"type": "string", "enum": ["stdout", "stderr", "both"], "default": "both"}},
                    ],
                }
            },
            # ------------------------------------------------------------
            # Context Engine (v6.1.0+)
            # ------------------------------------------------------------
            "/context-engine/list": {
                "get": {"summary": "Context engines disponibles", "tags": ["ContextEngine"]}
            },
            "/context-engine/current": {
                "get": {"summary": "Engine activo + fuentes", "tags": ["ContextEngine"]}
            },
            "/context-engine/switch": {
                "post": {
                    "summary": "Cambiar engine activo",
                    "tags": ["ContextEngine"],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ContextEngineSwitch"}
                            }
                        }
                    },
                }
            },
            "/context-engine/preview": {
                "post": {
                    "summary": "Simular engine con tarea",
                    "tags": ["ContextEngine"],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ContextEnginePreview"}
                            }
                        }
                    },
                }
            },
            "/context-engine/stats": {
                "post": {
                    "summary": "Metricas chars/tokens vs legacy",
                    "tags": ["ContextEngine"],
                }
            },
            "/autotune/analyze": {
                "post": {
                    "summary": "Analizar contexto y obtener parametros LLM optimizados",
                    "tags": ["AutoTune"],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["messages"],
                                    "properties": {
                                        "messages": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "role": {"type": "string"},
                                                    "content": {"type": "string"},
                                                },
                                            },
                                        },
                                        "model": {"type": "string"},
                                    },
                                }
                            }
                        }
                    },
                }
            },
            "/autotune/feedback": {
                "post": {
                    "summary": "Enviar feedback para ajustar parametros",
                    "tags": ["AutoTune"],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["category", "rating"],
                                    "properties": {
                                        "category": {"type": "string"},
                                        "rating": {"type": "number", "minimum": 0, "maximum": 1},
                                        "parameters": {"type": "object"},
                                    },
                                }
                            }
                        }
                    },
                }
            },
            "/race/run": {
                "post": {
                    "summary": "Ejecutar carrera paralela de agentes",
                    "tags": ["Racing"],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["task"],
                                    "properties": {
                                        "task": {"type": "string"},
                                        "tier": {
                                            "type": "string",
                                            "enum": ["fast", "standard", "thorough", "ultra"],
                                            "default": "standard",
                                        },
                                        "agents": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                    },
                                }
                            }
                        }
                    },
                }
            },
            "/race/rankings": {
                "get": {
                    "summary": "Rankings acumulados de agentes en carreras",
                    "tags": ["Racing"],
                }
            },
            "/rate-limit/stats": {
                "get": {
                    "summary": "Estadisticas del rate limiter",
                    "tags": ["Gateway"],
                }
            },
        },
    }
