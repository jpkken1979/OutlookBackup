#!/usr/bin/env python3
"""
Antigravity Intelligence MCP Server.

Exposes all 23 intelligence modules as MCP tools for any IDE/client.

Endpoints:
- reflect: Self-reflection on outputs
- think: Chain-of-thought reasoning
- react: ReAct pattern execution
- debate: Multi-agent debate
- assess_confidence: Metacognition
- query_knowledge: Knowledge graph queries
- score_quality: Quality scoring
- learn_tool: Tool learning from docs
- generate_skill: Auto-generate skills
- predict_escalation: Risk prediction
- compress_context: Context compression
- suggest: Proactive suggestions
- test_adversarial: Adversarial testing
- explain_decision: Decision explanations
- send_message: Cross-agent messaging
- ab_test: A/B testing
- detect_emotion: Emotion detection
- compose_skills: Skill composition
- specialize: Domain specialization
- share_memory: Collaborative memory
- remember: Time-aware memory
- recover_error: Error recovery
- intelligent_execute: Full intelligent execution

Version: 1.0.0
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field, asdict
import logging

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# MCP Protocol Implementation
@dataclass
class MCPTool:
    """MCP Tool definition."""

    name: str
    description: str
    input_schema: dict
    handler: callable


@dataclass
class MCPRequest:
    """MCP JSON-RPC request."""

    jsonrpc: str = "2.0"
    id: int | None = None
    method: str = ""
    params: dict = field(default_factory=dict)


@dataclass
class MCPResponse:
    """MCP JSON-RPC response."""

    jsonrpc: str = "2.0"
    id: int | None = None
    result: Any = None
    error: dict | None = None


class IntelligenceMCPServer:
    """
    MCP Server exposing all intelligence capabilities.

    Implements the Model Context Protocol for seamless IDE integration.
    """

    def __init__(self):
        self.tools: dict[str, MCPTool] = {}
        self.logger = logging.getLogger("intelligence-mcp")
        self._setup_logging()
        self._register_all_tools()

        # Lazy-loaded modules
        self._modules = {}

    def _setup_logging(self):
        """Configure logging."""
        logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")

    @staticmethod
    def _module_registry() -> dict[str, tuple[str, str | None]]:
        """Mapa nombre→(clase_o_factory, argumento_especial).

        Returns:
            Dict con nombre del módulo y tupla (import_name, arg_or_none).
        """
        return {
            "self_reflection": ("SelfReflection", None),
            "chain_of_thought": ("ChainOfThought", None),
            "react_pattern": ("create_default_react_agent", None),
            "multi_agent_debate": ("MultiAgentDebate", None),
            "metacognition": ("Metacognition", None),
            "knowledge_graph": ("create_knowledge_graph", None),
            "quality_scorer": ("QualityScorer", None),
            "tool_learning": ("ToolLearner", None),
            "skill_generator": ("SkillGenerator", None),
            "predictive_escalation": ("PredictiveEscalation", None),
            "context_compression": ("ContextCompressor", None),
            "proactive_suggestions": ("ProactiveSuggester", None),
            "adversarial_testing": ("AdversarialTester", None),
            "explainable_decisions": ("DecisionExplainer", None),
            "cross_agent_messaging": ("AgentMessenger", None),
            "ab_testing": ("ABTester", None),
            "emotion_detection": ("EmotionDetector", None),
            "skill_composition": ("SkillComposer", None),
            "domain_specialization": ("DomainSpecializer", None),
            "collaborative_memory": ("CollaborativeMemory", None),
            "time_aware_memory": ("TimeAwareMemory", None),
            "error_recovery": ("ErrorRecovery", None),
            "intelligent_agent": ("create_intelligent_agent", "mcp-agent"),
        }

    def _get_module(self, name: str):
        """Lazy load intelligence module."""
        if name not in self._modules:
            registry = self._module_registry()
            entry = registry.get(name)
            if entry is None:
                self._modules[name] = None
            else:
                import_name, special_arg = entry
                try:
                    import importlib

                    mod = importlib.import_module(
                        ".agent.core.intelligence", package=__package__ or "mcp"
                    )
                    factory = getattr(mod, import_name)
                    self._modules[name] = factory(special_arg) if special_arg else factory()
                except (ImportError, AttributeError) as e:
                    self.logger.warning(f"Could not load module {name}: {e}")
                    self._modules[name] = None
        return self._modules.get(name)

    def _register_all_tools(self):
        """Register all intelligence tools."""

        # =====================================================================
        # FOUNDATION TOOLS
        # =====================================================================

        self.register_tool(
            MCPTool(
                name="reflect",
                description="Self-reflection: Evaluate an output for quality, accuracy, and improvements",
                input_schema={
                    "type": "object",
                    "properties": {
                        "output": {"type": "string", "description": "The output to reflect on"},
                        "task": {"type": "string", "description": "Original task/prompt"},
                        "context": {"type": "string", "description": "Additional context"},
                    },
                    "required": ["output"],
                },
                handler=self._handle_reflect,
            )
        )

        self.register_tool(
            MCPTool(
                name="think",
                description="Chain-of-thought: Break down complex reasoning into explicit steps",
                input_schema={
                    "type": "object",
                    "properties": {
                        "problem": {"type": "string", "description": "Problem to reason through"},
                        "max_steps": {
                            "type": "integer",
                            "description": "Maximum reasoning steps",
                            "default": 10,
                        },
                    },
                    "required": ["problem"],
                },
                handler=self._handle_think,
            )
        )

        self.register_tool(
            MCPTool(
                name="react",
                description="ReAct pattern: Reasoning + Acting loop for complex tasks",
                input_schema={
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "Task to execute"},
                        "max_iterations": {
                            "type": "integer",
                            "description": "Max iterations",
                            "default": 10,
                        },
                    },
                    "required": ["task"],
                },
                handler=self._handle_react,
            )
        )

        self.register_tool(
            MCPTool(
                name="debate",
                description="Multi-agent debate: Multiple perspectives argue to reach consensus",
                input_schema={
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Topic to debate"},
                        "perspectives": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Different perspectives to consider",
                        },
                        "rounds": {
                            "type": "integer",
                            "description": "Number of debate rounds",
                            "default": 3,
                        },
                    },
                    "required": ["topic"],
                },
                handler=self._handle_debate,
            )
        )

        self.register_tool(
            MCPTool(
                name="assess_confidence",
                description="Metacognition: Assess confidence level and identify knowledge gaps",
                input_schema={
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string", "description": "Claim to assess"},
                        "evidence": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Supporting evidence",
                        },
                    },
                    "required": ["claim"],
                },
                handler=self._handle_assess_confidence,
            )
        )

        self.register_tool(
            MCPTool(
                name="query_knowledge",
                description="Knowledge graph: Query semantic knowledge with relationships",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Knowledge query"},
                        "depth": {
                            "type": "integer",
                            "description": "Traversal depth",
                            "default": 2,
                        },
                    },
                    "required": ["query"],
                },
                handler=self._handle_query_knowledge,
            )
        )

        self.register_tool(
            MCPTool(
                name="score_quality",
                description="Quality scoring: Evaluate output quality with detailed metrics",
                input_schema={
                    "type": "object",
                    "properties": {
                        "output": {"type": "string", "description": "Output to score"},
                        "criteria": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Quality criteria to evaluate",
                        },
                    },
                    "required": ["output"],
                },
                handler=self._handle_score_quality,
            )
        )

        # =====================================================================
        # NIVEL 1: CRITICAL TOOLS
        # =====================================================================

        self.register_tool(
            MCPTool(
                name="learn_tool",
                description="Tool learning: Learn a new tool from its documentation",
                input_schema={
                    "type": "object",
                    "properties": {
                        "tool_name": {"type": "string", "description": "Name of the tool"},
                        "documentation": {"type": "string", "description": "Tool documentation"},
                        "doc_type": {
                            "type": "string",
                            "enum": ["readme", "docstring", "json_schema", "man_page", "api_spec"],
                        },
                    },
                    "required": ["tool_name", "documentation"],
                },
                handler=self._handle_learn_tool,
            )
        )

        self.register_tool(
            MCPTool(
                name="generate_skill",
                description="Skill generator: Auto-generate a skill from execution patterns",
                input_schema={
                    "type": "object",
                    "properties": {
                        "task_description": {
                            "type": "string",
                            "description": "What the skill should do",
                        },
                        "example_inputs": {"type": "array", "items": {"type": "string"}},
                        "example_outputs": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["task_description"],
                },
                handler=self._handle_generate_skill,
            )
        )

        self.register_tool(
            MCPTool(
                name="predict_escalation",
                description="Predictive escalation: Predict if task needs human intervention",
                input_schema={
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "Current task"},
                        "context": {"type": "object", "description": "Execution context"},
                        "history": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Recent actions",
                        },
                    },
                    "required": ["task"],
                },
                handler=self._handle_predict_escalation,
            )
        )

        self.register_tool(
            MCPTool(
                name="compress_context",
                description="Context compression: Intelligently compress long context",
                input_schema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Content to compress"},
                        "max_tokens": {
                            "type": "integer",
                            "description": "Target token count",
                            "default": 4000,
                        },
                        "preserve_code": {
                            "type": "boolean",
                            "description": "Preserve code blocks",
                            "default": True,
                        },
                    },
                    "required": ["content"],
                },
                handler=self._handle_compress_context,
            )
        )

        self.register_tool(
            MCPTool(
                name="suggest",
                description="Proactive suggestions: Get improvement suggestions for code/text",
                input_schema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Content to analyze"},
                        "content_type": {
                            "type": "string",
                            "enum": ["code", "text", "config", "documentation"],
                        },
                        "categories": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": [
                                    "security",
                                    "performance",
                                    "quality",
                                    "style",
                                    "accessibility",
                                ],
                            },
                        },
                    },
                    "required": ["content"],
                },
                handler=self._handle_suggest,
            )
        )

        # =====================================================================
        # NIVEL 2: HIGH IMPACT TOOLS
        # =====================================================================

        self.register_tool(
            MCPTool(
                name="test_adversarial",
                description="Adversarial testing: Test with edge cases and attack vectors",
                input_schema={
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "description": "Function/endpoint to test"},
                        "categories": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": [
                                    "injection",
                                    "boundary",
                                    "malformed",
                                    "semantic",
                                    "privacy",
                                    "security",
                                ],
                            },
                        },
                    },
                    "required": ["target"],
                },
                handler=self._handle_test_adversarial,
            )
        )

        self.register_tool(
            MCPTool(
                name="explain_decision",
                description="Explainable decisions: Get human-readable explanation of a decision",
                input_schema={
                    "type": "object",
                    "properties": {
                        "decision": {"type": "string", "description": "The decision made"},
                        "factors": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Decision factors",
                        },
                        "alternatives": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Alternatives considered",
                        },
                    },
                    "required": ["decision"],
                },
                handler=self._handle_explain_decision,
            )
        )

        self.register_tool(
            MCPTool(
                name="send_message",
                description="Cross-agent messaging: Send message to another agent",
                input_schema={
                    "type": "object",
                    "properties": {
                        "to_agent": {"type": "string", "description": "Target agent ID"},
                        "message": {"type": "string", "description": "Message content"},
                        "message_type": {
                            "type": "string",
                            "enum": ["request", "response", "broadcast", "delegation"],
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "normal", "high", "critical"],
                        },
                    },
                    "required": ["to_agent", "message"],
                },
                handler=self._handle_send_message,
            )
        )

        self.register_tool(
            MCPTool(
                name="ab_test",
                description="A/B testing: Compare two approaches/agents",
                input_schema={
                    "type": "object",
                    "properties": {
                        "variant_a": {"type": "object", "description": "First variant config"},
                        "variant_b": {"type": "object", "description": "Second variant config"},
                        "test_cases": {"type": "array", "items": {"type": "string"}},
                        "metrics": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["quality", "speed", "accuracy", "completeness"],
                            },
                        },
                    },
                    "required": ["variant_a", "variant_b", "test_cases"],
                },
                handler=self._handle_ab_test,
            )
        )

        self.register_tool(
            MCPTool(
                name="detect_emotion",
                description="Emotion detection: Analyze emotional tone of text",
                input_schema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to analyze"},
                        "include_suggestions": {
                            "type": "boolean",
                            "description": "Include response tone suggestions",
                            "default": True,
                        },
                    },
                    "required": ["text"],
                },
                handler=self._handle_detect_emotion,
            )
        )

        # =====================================================================
        # NIVEL 3: DIFFERENTIATOR TOOLS
        # =====================================================================

        self.register_tool(
            MCPTool(
                name="compose_skills",
                description="Skill composition: Dynamically combine skills into pipeline",
                input_schema={
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "Complex task to decompose"},
                        "available_skills": {"type": "array", "items": {"type": "string"}},
                        "constraints": {"type": "object", "description": "Pipeline constraints"},
                    },
                    "required": ["task"],
                },
                handler=self._handle_compose_skills,
            )
        )

        self.register_tool(
            MCPTool(
                name="specialize",
                description="Domain specialization: Specialize agent for domain",
                input_schema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Agent to specialize"},
                        "domain": {
                            "type": "string",
                            "enum": [
                                "frontend",
                                "backend",
                                "database",
                                "security",
                                "devops",
                                "ml",
                                "mobile",
                            ],
                        },
                        "intensity": {
                            "type": "number",
                            "description": "Specialization intensity 0-1",
                            "default": 0.7,
                        },
                    },
                    "required": ["agent_id", "domain"],
                },
                handler=self._handle_specialize,
            )
        )

        self.register_tool(
            MCPTool(
                name="share_memory",
                description="Collaborative memory: Share knowledge across agents",
                input_schema={
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Memory key"},
                        "value": {"type": "object", "description": "Memory value"},
                        "access_level": {"type": "string", "enum": ["private", "team", "public"]},
                        "ttl_hours": {"type": "integer", "description": "Time to live in hours"},
                    },
                    "required": ["key", "value"],
                },
                handler=self._handle_share_memory,
            )
        )

        self.register_tool(
            MCPTool(
                name="remember",
                description="Time-aware memory: Store memory with temporal decay",
                input_schema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Content to remember"},
                        "priority": {
                            "type": "string",
                            "enum": ["critical", "high", "normal", "low"],
                        },
                        "decay_function": {
                            "type": "string",
                            "enum": ["none", "linear", "exponential", "step"],
                        },
                    },
                    "required": ["content"],
                },
                handler=self._handle_remember,
            )
        )

        self.register_tool(
            MCPTool(
                name="recover_error",
                description="Error recovery: Find and apply recovery strategy for error",
                input_schema={
                    "type": "object",
                    "properties": {
                        "error_type": {"type": "string", "description": "Type of error"},
                        "error_message": {"type": "string", "description": "Error message"},
                        "context": {"type": "object", "description": "Error context"},
                    },
                    "required": ["error_type", "error_message"],
                },
                handler=self._handle_recover_error,
            )
        )

        # =====================================================================
        # META TOOL
        # =====================================================================

        self.register_tool(
            MCPTool(
                name="intelligent_execute",
                description="Full intelligent execution: Run task with all intelligence modules",
                input_schema={
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "Task to execute"},
                        "modules": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Intelligence modules to use (default: all)",
                        },
                        "config": {"type": "object", "description": "Execution configuration"},
                    },
                    "required": ["task"],
                },
                handler=self._handle_intelligent_execute,
            )
        )

        # Model Advisor: recomienda haiku/sonnet/opus por tarea con piso de calidad.
        self.register_tool(
            MCPTool(
                name="recommend_model",
                description=(
                    "Recommend the Claude model (haiku/sonnet/opus) for a task "
                    "applying a conservative quality floor."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Task description"},
                        "file_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Files the task would touch (optional)",
                        },
                        "agent_tier": {
                            "type": "integer",
                            "description": "Assigned agent tier 1-6 (optional)",
                        },
                    },
                    "required": ["text"],
                },
                handler=self._handle_recommend_model,
            )
        )

    def register_tool(self, tool: MCPTool):
        """Register a tool."""
        self.tools[tool.name] = tool
        self.logger.info(f"Registered tool: {tool.name}")

    # =========================================================================
    # TOOL HANDLERS
    # =========================================================================

    async def _handle_reflect(self, params: dict) -> dict:
        """Handle reflect tool."""
        try:
            from core.intelligence import quick_reflect

            result = await quick_reflect(
                output=params["output"],
                task=params.get("task", ""),
                context=params.get("context", ""),
            )
            return {
                "success": True,
                "reflection": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_think(self, params: dict) -> dict:
        """Handle think tool."""
        try:
            from core.intelligence import think_through

            result = await think_through(
                problem=params["problem"], max_steps=params.get("max_steps", 10)
            )
            return {
                "success": True,
                "thought_chain": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_react(self, params: dict) -> dict:
        """Handle react tool."""
        try:
            from core.intelligence import create_default_react_agent

            agent = create_default_react_agent()
            result = await agent.execute(
                task=params["task"], max_iterations=params.get("max_iterations", 10)
            )
            return {
                "success": True,
                "result": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_debate(self, params: dict) -> dict:
        """Handle debate tool."""
        try:
            from core.intelligence import quick_debate

            result = await quick_debate(
                topic=params["topic"],
                perspectives=params.get("perspectives", ["pro", "con", "neutral"]),
                rounds=params.get("rounds", 3),
            )
            return {
                "success": True,
                "debate": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_assess_confidence(self, params: dict) -> dict:
        """Handle assess_confidence tool."""
        try:
            from core.intelligence import assess_confidence

            result = await assess_confidence(
                claim=params["claim"], evidence=params.get("evidence", [])
            )
            return {
                "success": True,
                "assessment": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_query_knowledge(self, params: dict) -> dict:
        """Handle query_knowledge tool."""
        try:
            from core.intelligence import create_knowledge_graph

            kg = create_knowledge_graph()
            results = kg.query(query=params["query"], depth=params.get("depth", 2))
            return {
                "success": True,
                "results": [r.to_dict() if hasattr(r, "to_dict") else str(r) for r in results],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_score_quality(self, params: dict) -> dict:
        """Handle score_quality tool."""
        try:
            from core.intelligence import quick_score

            result = await quick_score(output=params["output"], criteria=params.get("criteria", []))
            return {
                "success": True,
                "score": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_learn_tool(self, params: dict) -> dict:
        """Handle learn_tool tool."""
        try:
            from core.intelligence import learn_tool

            result = await learn_tool(
                tool_name=params["tool_name"],
                documentation=params["documentation"],
                doc_type=params.get("doc_type", "readme"),
            )
            return {
                "success": True,
                "knowledge": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_generate_skill(self, params: dict) -> dict:
        """Handle generate_skill tool."""
        try:
            from core.intelligence import auto_generate_skill

            result = await auto_generate_skill(
                task_description=params["task_description"],
                example_inputs=params.get("example_inputs", []),
                example_outputs=params.get("example_outputs", []),
            )
            return {
                "success": True,
                "skill": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_predict_escalation(self, params: dict) -> dict:
        """Handle predict_escalation tool."""
        try:
            from core.intelligence import predict_escalation

            result = await predict_escalation(
                task=params["task"],
                context=params.get("context", {}),
                history=params.get("history", []),
            )
            return {
                "success": True,
                "prediction": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_compress_context(self, params: dict) -> dict:
        """Handle compress_context tool."""
        try:
            from core.intelligence import compress_context

            result = await compress_context(
                content=params["content"],
                max_tokens=params.get("max_tokens", 4000),
                preserve_code=params.get("preserve_code", True),
            )
            return {
                "success": True,
                "compressed": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_suggest(self, params: dict) -> dict:
        """Handle suggest tool."""
        try:
            from core.intelligence import get_suggestions

            result = await get_suggestions(
                content=params["content"],
                content_type=params.get("content_type", "code"),
                categories=params.get("categories", []),
            )
            return {
                "success": True,
                "suggestions": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_test_adversarial(self, params: dict) -> dict:
        """Handle test_adversarial tool."""
        try:
            from core.intelligence import test_adversarially

            result = await test_adversarially(
                target=params["target"], categories=params.get("categories", [])
            )
            return {
                "success": True,
                "test_results": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_explain_decision(self, params: dict) -> dict:
        """Handle explain_decision tool."""
        try:
            from core.intelligence import explain_decision

            result = await explain_decision(
                decision=params["decision"],
                factors=params.get("factors", []),
                alternatives=params.get("alternatives", []),
            )
            return {
                "success": True,
                "explanation": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_send_message(self, params: dict) -> dict:
        """Handle send_message tool."""
        try:
            from core.intelligence import send_message

            result = await send_message(
                to_agent=params["to_agent"],
                message=params["message"],
                message_type=params.get("message_type", "request"),
                priority=params.get("priority", "normal"),
            )
            return {
                "success": True,
                "message_id": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_ab_test(self, params: dict) -> dict:
        """Handle ab_test tool."""
        try:
            from core.intelligence import run_ab_test

            result = await run_ab_test(
                variant_a=params["variant_a"],
                variant_b=params["variant_b"],
                test_cases=params["test_cases"],
                metrics=params.get("metrics", ["quality", "speed"]),
            )
            return {
                "success": True,
                "test_results": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_detect_emotion(self, params: dict) -> dict:
        """Handle detect_emotion tool."""
        try:
            from core.intelligence import detect_emotion

            result = await detect_emotion(
                text=params["text"], include_suggestions=params.get("include_suggestions", True)
            )
            return {
                "success": True,
                "analysis": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_compose_skills(self, params: dict) -> dict:
        """Handle compose_skills tool."""
        try:
            from core.intelligence import compose_skills

            result = await compose_skills(
                task=params["task"],
                available_skills=params.get("available_skills", []),
                constraints=params.get("constraints", {}),
            )
            return {
                "success": True,
                "pipeline": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_specialize(self, params: dict) -> dict:
        """Handle specialize tool."""
        try:
            from core.intelligence import specialize

            result = await specialize(
                agent_id=params["agent_id"],
                domain=params["domain"],
                intensity=params.get("intensity", 0.7),
            )
            return {
                "success": True,
                "profile": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_share_memory(self, params: dict) -> dict:
        """Handle share_memory tool."""
        try:
            from core.intelligence import share_knowledge

            result = await share_knowledge(
                key=params["key"],
                value=params["value"],
                access_level=params.get("access_level", "team"),
                ttl_hours=params.get("ttl_hours", 24),
            )
            return {
                "success": True,
                "memory_id": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_remember(self, params: dict) -> dict:
        """Handle remember tool."""
        try:
            from core.intelligence import remember

            result = await remember(
                content=params["content"],
                priority=params.get("priority", "normal"),
                decay_function=params.get("decay_function", "exponential"),
            )
            return {
                "success": True,
                "memory": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_recover_error(self, params: dict) -> dict:
        """Handle recover_error tool."""
        try:
            from core.intelligence import recover_from_error

            result = await recover_from_error(
                error_type=params["error_type"],
                error_message=params["error_message"],
                context=params.get("context", {}),
            )
            return {
                "success": True,
                "recovery": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_intelligent_execute(self, params: dict) -> dict:
        """Handle intelligent_execute tool - the meta tool."""
        try:
            from core.intelligence import create_intelligent_agent

            agent = create_intelligent_agent("mcp-intelligent-agent")
            result = await agent.execute(
                task=params["task"], modules=params.get("modules"), config=params.get("config", {})
            )
            return {
                "success": True,
                "result": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_recommend_model(self, params: dict) -> dict:
        """Handler del tool recommend_model.

        Inserta `.agent` en sys.path para resolver `core.*` aun cuando el server
        se lanza standalone (su path top-level solo agrega el repo root).
        """
        import sys
        from dataclasses import asdict
        from pathlib import Path

        agent_dir = str(Path(__file__).resolve().parent.parent)  # .agent
        if agent_dir not in sys.path:
            sys.path.insert(0, agent_dir)

        from core.model_advisor import TaskInput, recommend

        task = TaskInput(
            text=params["text"],
            file_paths=params.get("file_paths"),
            agent_tier=params.get("agent_tier"),
        )
        return asdict(recommend(task))

    # =========================================================================
    # MCP PROTOCOL
    # =========================================================================

    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """Handle MCP request."""
        try:
            if request.method == "initialize":
                return MCPResponse(
                    id=request.id,
                    result={
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {"listChanged": True}},
                        "serverInfo": {"name": "antigravity-intelligence", "version": "1.0.0"},
                    },
                )

            elif request.method == "tools/list":
                tools_list = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.input_schema,
                    }
                    for tool in self.tools.values()
                ]
                return MCPResponse(id=request.id, result={"tools": tools_list})

            elif request.method == "tools/call":
                tool_name = request.params.get("name")
                arguments = request.params.get("arguments", {})

                if tool_name not in self.tools:
                    return MCPResponse(
                        id=request.id,
                        error={"code": -32601, "message": f"Tool not found: {tool_name}"},
                    )

                tool = self.tools[tool_name]
                result = await tool.handler(arguments)

                return MCPResponse(
                    id=request.id,
                    result={
                        "content": [
                            {"type": "text", "text": json.dumps(result, indent=2, default=str)}
                        ]
                    },
                )

            elif request.method and request.method.startswith("notifications/"):
                # Notifications don't get responses (JSON-RPC 2.0 spec)
                return None

            else:
                return MCPResponse(
                    id=request.id,
                    error={"code": -32601, "message": f"Method not found: {request.method}"},
                )

        except Exception as e:
            self.logger.error(f"Error handling request: {e}")
            return MCPResponse(id=request.id, error={"code": -32603, "message": str(e)})

    async def run_stdio(self):
        """Run server using stdio transport."""
        # Los pipes stdio en Windows heredan la codepage del locale (cp932 en JP),
        # pero el protocolo MCP habla UTF-8: sin esto, el JSON entrante con no-ASCII
        # llega con surrogates sueltos y la respuesta puede fallar al escribirse.
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")

        self.logger.info("Starting Intelligence MCP Server on stdio...")

        while True:
            try:
                line = await asyncio.get_running_loop().run_in_executor(None, sys.stdin.readline)
                if not line:
                    break

                request_data = json.loads(line)
                request = MCPRequest(**request_data)

                response = await self.handle_request(request)

                if response is not None:
                    # Serialize excluding None fields (JSON-RPC 2.0: result XOR error)
                    resp_dict = {k: v for k, v in asdict(response).items() if v is not None}
                    resp_dict["jsonrpc"] = "2.0"  # Always include
                    response_json = json.dumps(resp_dict, default=str)
                    print(response_json, flush=True)

            except json.JSONDecodeError as e:
                self.logger.error(f"JSON decode error: {e}")
            except Exception as e:
                self.logger.error(f"Error: {e}")

    def get_tools_summary(self) -> str:
        """Get summary of all tools."""
        lines = [
            "# Antigravity Intelligence MCP Server",
            "",
            f"**Total Tools:** {len(self.tools)}",
            "",
            "## Available Tools",
            "",
        ]

        categories = {
            "Foundation": [
                "reflect",
                "think",
                "react",
                "debate",
                "assess_confidence",
                "query_knowledge",
                "score_quality",
            ],
            "Nivel 1 - Critical": [
                "learn_tool",
                "generate_skill",
                "predict_escalation",
                "compress_context",
                "suggest",
            ],
            "Nivel 2 - High Impact": [
                "test_adversarial",
                "explain_decision",
                "send_message",
                "ab_test",
                "detect_emotion",
            ],
            "Nivel 3 - Differentiators": [
                "compose_skills",
                "specialize",
                "share_memory",
                "remember",
                "recover_error",
            ],
            "Meta": ["intelligent_execute"],
        }

        for category, tool_names in categories.items():
            lines.append(f"### {category}")
            lines.append("")
            for name in tool_names:
                if name in self.tools:
                    tool = self.tools[name]
                    lines.append(f"- **{name}**: {tool.description}")
            lines.append("")

        return "\n".join(lines)


# =============================================================================
# MAIN
# =============================================================================


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Antigravity Intelligence MCP Server")
    parser.add_argument("--list", action="store_true", help="List all tools")
    parser.add_argument("--summary", action="store_true", help="Show tools summary")
    args = parser.parse_args()

    server = IntelligenceMCPServer()

    if args.list:
        for name, tool in server.tools.items():
            print(f"{name}: {tool.description}")
    elif args.summary:
        print(server.get_tools_summary())
    else:
        asyncio.run(server.run_stdio())


if __name__ == "__main__":
    main()
