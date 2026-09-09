"""Manifest-driven, allowlisted quality gates for Nexus.

No manifest can provide executable code or a shell command.  Nodes resolve from
an internal handler registry and targeted checks resolve from a fixed argv
allowlist.
"""

from __future__ import annotations

import functools
import json
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.workflow_contracts import (
    FindingSeverity,
    GateEvidence,
    GateFinding,
    GateResult,
    GateVerdict,
    merge_findings,
    redact_text,
    redact_value,
    validate_relative_path,
)
from core.workflow_engine import END, StateGraph

QUALITY_GRAPH_IDS = frozenset(
    {
        "code-review-v1",
        "systematic-debug-v1",
        "targeted-test-v1",
        "finalize-v1",
    }
)
MAX_MANIFEST_NODES = 30
MAX_INITIAL_STATE_BYTES = 64_000
MAX_SCOPE_FILES = 100
MAX_RETRIES = 2
MAX_PROVIDER_REVIEWS = 3

_CORE_DIR = Path(__file__).resolve().parent
_AGENT_DIR = _CORE_DIR.parent
_REPO_ROOT = _AGENT_DIR.parent
_MANIFEST_DIR = _AGENT_DIR / "workflows" / "manifests"

_TEST_PROFILES: dict[str, tuple[Path, tuple[str, ...]]] = {
    "workflow-engine": (
        _REPO_ROOT,
        (
            sys.executable,
            "-m",
            "pytest",
            "tests/core/test_workflow_engine.py",
            "tests/core/test_quality_gate_workflows.py",
            "-q",
        ),
    ),
    "workflow-api": (
        _REPO_ROOT,
        (
            sys.executable,
            "-m",
            "pytest",
            "tests/mcp/test_workflow_api.py",
            "-q",
        ),
    ),
    "nexus-workflow-ui": (
        _REPO_ROOT / "nexus-app",
        (
            "npm.cmd",
            "test",
            "--",
            "--run",
            "src/features/nexus/workflows",
        ),
    ),
    "nexus-types": (
        _REPO_ROOT / "nexus-app",
        ("npm.cmd", "run", "ts:app"),
    ),
}

_ALLOWED_INITIAL_KEYS = frozenset(
    {
        "scope_files",
        "checks",
        "review_complete",
        "findings",
        "multi_provider",
        "diff_size_bytes",
        "diff_has_secrets",
        "issue_summary",
        "hypotheses",
        "root_cause",
        "max_retries",
        "retry_count",
    }
)


@dataclass(frozen=True)
class ManifestNode:
    id: str
    handler: str
    args: dict[str, Any]
    interrupt_before: bool = False


@dataclass(frozen=True)
class ManifestEdge:
    source: str
    target: str | None = None
    router: str | None = None
    condition_map: dict[str, str] | None = None


@dataclass(frozen=True)
class WorkflowManifest:
    id: str
    version: int
    title: str
    description: str
    entry_point: str
    finish_points: tuple[str, ...]
    nodes: tuple[ManifestNode, ...]
    edges: tuple[ManifestEdge, ...]

    def catalog_dict(self) -> dict[str, Any]:
        return {
            "name": self.id,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "entry_point": self.entry_point,
            "finish_points": list(self.finish_points),
            "nodes": [
                {
                    "name": node.id,
                    "handler": node.handler,
                    "interrupt_before": node.interrupt_before,
                }
                for node in self.nodes
            ],
        }


TestRunner = Callable[[str], GateEvidence]
ProviderReviewer = Callable[[str, dict[str, Any]], list[dict[str, Any]]]


def _safe_id(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 80
        or not all(character.isalnum() or character in "-_" for character in value)
    ):
        raise ValueError(f"{label} must be an opaque identifier")
    return value


def _validate_manifest_args(handler: str, args: Any) -> dict[str, Any]:
    if not isinstance(args, dict):
        raise ValueError(f"args for {handler} must be an object")
    schemas: dict[str, set[str]] = {
        "collect_scope": set(),
        "run_targeted_tests": {"default_checks"},
        "review_findings": set(),
        "formulate_hypotheses": set(),
        "optional_multi_review": set(),
        "request_decision": set(),
        "finalize_result": set(),
        "block_finalize": set(),
    }
    allowed = schemas.get(handler)
    if allowed is None:
        raise ValueError(f"unknown workflow handler: {handler}")
    unknown = set(args) - allowed
    if unknown:
        raise ValueError(f"unknown args for {handler}: {', '.join(sorted(unknown))}")
    result = dict(args)
    if "default_checks" in result:
        checks = result["default_checks"]
        if (
            not isinstance(checks, list)
            or not 1 <= len(checks) <= len(_TEST_PROFILES)
            or any(check not in _TEST_PROFILES for check in checks)
        ):
            raise ValueError("default_checks contains an unknown check profile")
    return result


def _parse_manifest_payload(path: Path) -> dict[str, Any]:
    """Lee el JSON del manifest y valida sus campos de nivel superior.

    Args:
        path: Ruta del archivo de manifest.

    Returns:
        El payload crudo ya validado como objeto con campos permitidos.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    allowed_top = {
        "id",
        "version",
        "title",
        "description",
        "entry_point",
        "finish_points",
        "nodes",
        "edges",
    }
    if not isinstance(payload, dict) or set(payload) - allowed_top:
        raise ValueError(f"invalid manifest fields in {path.name}")
    return payload


def _parse_manifest_id_and_version(payload: dict[str, Any]) -> tuple[str, int]:
    """Valida el id (allowlisted) y la version del manifest.

    Args:
        payload: Payload crudo del manifest.

    Returns:
        Tupla (manifest_id, version).
    """
    manifest_id = _safe_id(payload.get("id"), "manifest.id")
    if manifest_id not in QUALITY_GRAPH_IDS:
        raise ValueError(f"manifest id is not allowlisted: {manifest_id}")
    version = payload.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or not 1 <= version <= 100:
        raise ValueError("manifest.version must be a bounded integer")
    return manifest_id, version


def _parse_manifest_nodes(raw_nodes: Any) -> tuple[tuple[ManifestNode, ...], set[str]]:
    """Valida y construye los nodos declarados en el manifest.

    Args:
        raw_nodes: Valor crudo del campo `nodes` del manifest.

    Returns:
        Tupla (nodes, node_ids) con los nodos construidos y sus ids.
    """
    if not isinstance(raw_nodes, list) or not 1 <= len(raw_nodes) <= MAX_MANIFEST_NODES:
        raise ValueError("manifest must contain between 1 and 30 nodes")
    nodes: list[ManifestNode] = []
    node_ids: set[str] = set()
    for raw_node in raw_nodes:
        if not isinstance(raw_node, dict) or set(raw_node) - {
            "id",
            "handler",
            "args",
            "interrupt_before",
        }:
            raise ValueError("invalid manifest node")
        node_id = _safe_id(raw_node.get("id"), "node.id")
        if node_id in node_ids:
            raise ValueError(f"duplicate manifest node: {node_id}")
        node_ids.add(node_id)
        handler = _safe_id(raw_node.get("handler"), "node.handler")
        nodes.append(
            ManifestNode(
                id=node_id,
                handler=handler,
                args=_validate_manifest_args(handler, raw_node.get("args", {})),
                interrupt_before=raw_node.get("interrupt_before", False) is True,
            )
        )
    return tuple(nodes), node_ids


def _parse_manifest_entry_and_finishes(
    payload: dict[str, Any], node_ids: set[str]
) -> tuple[str, tuple[str, ...]]:
    """Valida el entry_point y los finish_points contra los nodos existentes.

    Args:
        payload: Payload crudo del manifest.
        node_ids: Ids de nodos ya validados.

    Returns:
        Tupla (entry_point, finish_points).
    """
    entry = _safe_id(payload.get("entry_point"), "entry_point")
    raw_finishes = payload.get("finish_points")
    if not isinstance(raw_finishes, list) or not raw_finishes:
        raise ValueError("finish_points must be a non-empty list")
    finishes = tuple(_safe_id(value, "finish_point") for value in raw_finishes)
    if entry not in node_ids or any(value not in node_ids for value in finishes):
        raise ValueError("entry/finish points must reference manifest nodes")
    return entry, finishes


def _validate_condition_map(
    router: Any,
    condition_map: Any,
    node_ids: set[str],
    source: str,
    adjacency: dict[str, set[str]],
) -> dict[str, str]:
    """Valida el condition_map de un edge con router `gate_verdict`.

    Args:
        router: Nombre del router declarado en el edge.
        condition_map: Mapa verdict -> destino declarado en el edge.
        node_ids: Ids de nodos validos.
        source: Nodo origen del edge (para actualizar adjacency).
        adjacency: Grafo de adyacencia mutado in-place con los destinos validos.

    Returns:
        El condition_map normalizado.
    """
    if router != "gate_verdict" or not isinstance(condition_map, dict):
        raise ValueError("only the gate_verdict router is supported")
    if set(condition_map) - {item.value for item in GateVerdict}:
        raise ValueError("condition_map contains an unknown verdict")
    normalized: dict[str, str] = {}
    for verdict, destination in condition_map.items():
        destination = _safe_id(destination, "condition target")
        if destination != END and destination not in node_ids:
            raise ValueError(f"condition target does not exist: {destination}")
        normalized[verdict] = destination
        if destination != END:
            adjacency[source].add(destination)
    return normalized


def _parse_manifest_edge(
    raw_edge: Any, node_ids: set[str], adjacency: dict[str, set[str]]
) -> ManifestEdge:
    """Valida y construye una unica arista del manifest.

    Args:
        raw_edge: Valor crudo de una entrada de `edges`.
        node_ids: Ids de nodos validos.
        adjacency: Grafo de adyacencia mutado in-place con el destino valido.

    Returns:
        El ManifestEdge construido.
    """
    if not isinstance(raw_edge, dict) or set(raw_edge) - {
        "source",
        "target",
        "router",
        "condition_map",
    }:
        raise ValueError("invalid manifest edge")
    source = _safe_id(raw_edge.get("source"), "edge.source")
    if source not in node_ids:
        raise ValueError(f"edge source does not exist: {source}")
    target = raw_edge.get("target")
    router = raw_edge.get("router")
    condition_map = raw_edge.get("condition_map")
    if (target is None) == (router is None):
        raise ValueError("edge must define exactly one of target or router")
    if target is not None:
        target = _safe_id(target, "edge.target")
        if target != END and target not in node_ids:
            raise ValueError(f"edge target does not exist: {target}")
        if target != END:
            adjacency[source].add(target)
    else:
        condition_map = _validate_condition_map(router, condition_map, node_ids, source, adjacency)
    return ManifestEdge(source=source, target=target, router=router, condition_map=condition_map)


def _parse_manifest_edges(
    raw_edges: Any, node_ids: set[str]
) -> tuple[tuple[ManifestEdge, ...], dict[str, set[str]]]:
    """Valida y construye las aristas declaradas en el manifest.

    Args:
        raw_edges: Valor crudo del campo `edges` del manifest.
        node_ids: Ids de nodos validos.

    Returns:
        Tupla (edges, adjacency) con las aristas construidas y el grafo resultante.
    """
    if not isinstance(raw_edges, list):
        raise ValueError("manifest.edges must be a list")
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    edges = tuple(_parse_manifest_edge(raw_edge, node_ids, adjacency) for raw_edge in raw_edges)
    return edges, adjacency


def _validate_manifest_reachability(
    entry: str, node_ids: set[str], adjacency: dict[str, set[str]]
) -> None:
    """Verifica que el manifest no tenga ciclos y que todos los nodos sean alcanzables.

    Args:
        entry: Nodo de entrada del manifest.
        node_ids: Ids de todos los nodos declarados.
        adjacency: Grafo de adyacencia construido a partir de las aristas.
    """
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise ValueError("workflow manifest contains a cycle")
        if node_id in visited:
            return
        visiting.add(node_id)
        for destination in adjacency[node_id]:
            visit(destination)
        visiting.remove(node_id)
        visited.add(node_id)

    visit(entry)
    if visited != node_ids:
        unreachable = ", ".join(sorted(node_ids - visited))
        raise ValueError(f"manifest contains unreachable nodes: {unreachable}")


def load_workflow_manifest(path: Path) -> WorkflowManifest:
    """Load and statically validate one data-only workflow manifest."""

    payload = _parse_manifest_payload(path)
    manifest_id, version = _parse_manifest_id_and_version(payload)
    nodes, node_ids = _parse_manifest_nodes(payload.get("nodes"))
    entry, finishes = _parse_manifest_entry_and_finishes(payload, node_ids)
    edges, adjacency = _parse_manifest_edges(payload.get("edges"), node_ids)
    _validate_manifest_reachability(entry, node_ids, adjacency)
    return WorkflowManifest(
        id=manifest_id,
        version=version,
        title=_manifest_text(payload.get("title"), "manifest.title"),
        description=_manifest_text(payload.get("description"), "manifest.description"),
        entry_point=entry,
        finish_points=finishes,
        nodes=nodes,
        edges=edges,
    )


def _manifest_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise ValueError(f"{label} must be a bounded string")
    return redact_text(value.strip(), max_length=500)


def load_quality_manifests(directory: Path = _MANIFEST_DIR) -> dict[str, WorkflowManifest]:
    manifests: dict[str, WorkflowManifest] = {}
    for path in sorted(directory.glob("*.json")):
        manifest = load_workflow_manifest(path)
        if manifest.id in manifests:
            raise ValueError(f"duplicate workflow manifest: {manifest.id}")
        manifests[manifest.id] = manifest
    missing = QUALITY_GRAPH_IDS - manifests.keys()
    if missing:
        raise ValueError(f"missing workflow manifests: {', '.join(sorted(missing))}")
    return manifests


def _validate_scope_files(state: dict[str, Any]) -> list[str]:
    """Valida y normaliza la lista de archivos en scope."""
    scope = state.get("scope_files", [])
    if not isinstance(scope, list) or len(scope) > MAX_SCOPE_FILES:
        raise ValueError("scope_files must be a bounded list")
    return [validate_relative_path(item, label="scope_file") for item in scope]


def _validate_checks(state: dict[str, Any]) -> list[str]:
    """Valida la lista de perfiles de check solicitados."""
    checks = state.get("checks", [])
    if not isinstance(checks, list) or len(checks) > len(_TEST_PROFILES):
        raise ValueError("checks must be a bounded list")
    if any(check not in _TEST_PROFILES for check in checks):
        raise ValueError("checks contains an unknown profile")
    return list(dict.fromkeys(checks))


def _validate_findings(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Valida y normaliza la lista de findings iniciales."""
    findings = state.get("findings", [])
    if not isinstance(findings, list):
        raise ValueError("findings must be a list")
    return [GateFinding.from_dict(item).to_dict() for item in findings]


def _validate_diff_size(state: dict[str, Any]) -> int:
    """Valida que diff_size_bytes sea un entero acotado."""
    diff_size = state.get("diff_size_bytes", 0)
    if (
        not isinstance(diff_size, int)
        or isinstance(diff_size, bool)
        or not 0 <= diff_size <= 50_000_000
    ):
        raise ValueError("diff_size_bytes must be a bounded integer")
    return diff_size


def _validate_text_fields(state: dict[str, Any]) -> tuple[str, str]:
    """Valida issue_summary y root_cause como strings acotados y redactados."""
    values: dict[str, str] = {}
    for text_key in ("issue_summary", "root_cause"):
        value = state.get(text_key, "")
        if not isinstance(value, str) or len(value) > 4_000:
            raise ValueError(f"{text_key} must be a bounded string")
        values[text_key] = redact_text(value)
    return values["issue_summary"], values["root_cause"]


def _validate_hypotheses(state: dict[str, Any]) -> list[str]:
    """Valida y redacta la lista de hipotesis."""
    hypotheses = state.get("hypotheses", [])
    if not isinstance(hypotheses, list) or len(hypotheses) > 20:
        raise ValueError("hypotheses must be a bounded list")
    return [
        redact_text(item, max_length=1_000)
        for item in hypotheses
        if isinstance(item, str) and item.strip()
    ]


def _validate_retry_counters(state: dict[str, Any]) -> tuple[int, int]:
    """Valida max_retries/retry_count y que el presupuesto no este agotado."""
    max_retries = state.get("max_retries", MAX_RETRIES)
    retry_count = state.get("retry_count", 0)
    if (
        not isinstance(max_retries, int)
        or isinstance(max_retries, bool)
        or not 0 <= max_retries <= MAX_RETRIES
        or not isinstance(retry_count, int)
        or isinstance(retry_count, bool)
        or not 0 <= retry_count <= MAX_RETRIES
    ):
        raise ValueError("retry counters exceed the safe limit")
    if retry_count > max_retries:
        raise ValueError("retry budget is exhausted")
    return max_retries, retry_count


def validate_quality_initial_state(graph_id: str, state: Any) -> dict[str, Any]:
    """Validate the only state shape accepted by public quality endpoints."""

    if graph_id not in QUALITY_GRAPH_IDS:
        raise ValueError("workflow graph is not allowlisted")
    if not isinstance(state, dict):
        raise ValueError("workflow state must be an object")
    unknown = set(state) - _ALLOWED_INITIAL_KEYS
    if unknown:
        raise ValueError(f"unknown workflow state fields: {', '.join(sorted(unknown))}")
    serialized = json.dumps(state, ensure_ascii=True, default=str)
    if len(serialized.encode("utf-8")) > MAX_INITIAL_STATE_BYTES:
        raise ValueError("workflow state exceeds the 64 KB limit")
    result: dict[str, Any] = {}
    result["scope_files"] = _validate_scope_files(state)
    result["checks"] = _validate_checks(state)
    result["findings"] = _validate_findings(state)
    result["review_complete"] = state.get("review_complete", False) is True
    result["diff_has_secrets"] = state.get("diff_has_secrets", False) is True
    result["diff_size_bytes"] = _validate_diff_size(state)
    result["multi_provider"] = _validate_multi_provider(state.get("multi_provider", {}))
    issue_summary, root_cause = _validate_text_fields(state)
    result["issue_summary"] = issue_summary
    result["root_cause"] = root_cause
    result["hypotheses"] = _validate_hypotheses(state)
    max_retries, retry_count = _validate_retry_counters(state)
    result["max_retries"] = max_retries
    result["retry_count"] = retry_count
    return result


def _validate_multi_provider(value: Any) -> dict[str, Any]:
    if value in (None, {}):
        return {"enabled": False, "providers": [], "failure_policy": "needs_input"}
    if not isinstance(value, dict):
        raise ValueError("multi_provider must be an object")
    allowed = {"enabled", "providers", "failure_policy", "max_cost_units"}
    if set(value) - allowed:
        raise ValueError("multi_provider contains unknown fields")
    providers = value.get("providers", [])
    if not isinstance(providers, list) or len(providers) > MAX_PROVIDER_REVIEWS:
        raise ValueError("multi_provider.providers must be a bounded list")
    normalized: list[dict[str, str]] = []
    for provider in providers:
        if not isinstance(provider, dict) or set(provider) != {"id", "status"}:
            raise ValueError("each provider must contain id and status")
        if provider["status"] not in ("ready", "not_ready", "offline"):
            raise ValueError("provider.status is invalid")
        normalized.append(
            {
                "id": _safe_id(provider["id"], "provider.id"),
                "status": provider["status"],
            }
        )
    failure_policy = value.get("failure_policy", "needs_input")
    if failure_policy not in ("needs_input", "continue_single"):
        raise ValueError("multi_provider.failure_policy is invalid")
    max_cost = value.get("max_cost_units", 0)
    if not isinstance(max_cost, int) or isinstance(max_cost, bool) or not 0 <= max_cost <= 10:
        raise ValueError("multi_provider.max_cost_units is invalid")
    return {
        "enabled": value.get("enabled", False) is True,
        "providers": normalized,
        "failure_policy": failure_policy,
        "max_cost_units": max_cost,
    }


def _default_test_runner(profile_id: str) -> GateEvidence:
    cwd, argv = _TEST_PROFILES[profile_id]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            check=False,
            shell=False,
            text=True,
            timeout=180,
        )
        output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
        summary = redact_text(output[-3_000:] or "Check completed without output")
        return GateEvidence(
            command=profile_id,
            exit_code=completed.returncode,
            summary=summary,
            duration_ms=round((time.monotonic() - started) * 1_000),
        )
    except subprocess.TimeoutExpired:
        return GateEvidence(
            command=profile_id,
            exit_code=124,
            summary="Safe check timeout reached",
            duration_ms=round((time.monotonic() - started) * 1_000),
        )


def _set_result(state: dict[str, Any], result: GateResult) -> dict[str, Any]:
    updated = dict(state)
    updated["gate_result"] = result.to_dict()
    return updated


def _current_result(state: dict[str, Any]) -> GateResult | None:
    payload = state.get("gate_result")
    return GateResult.from_dict(payload) if isinstance(payload, dict) else None


def _handle_collect_scope(state: dict[str, Any], **_: Any) -> dict[str, Any]:
    """Handler del nodo `collect_scope`: registra los archivos en scope."""
    scope = state.get("scope_files", [])
    summary = f"{len(scope)} workspace-relative file(s) selected"
    evidence = GateEvidence(command="collect-scope", exit_code=0, summary=summary)
    return _set_result(
        state,
        GateResult(
            verdict=GateVerdict.PASS,
            evidence=(evidence,),
            summary=summary,
            next_action="Run the configured quality gate",
        ),
    )


def _handle_run_targeted_tests(
    state: dict[str, Any],
    *,
    test_runner: TestRunner,
    default_checks: list[str] | None = None,
) -> dict[str, Any]:
    """Handler del nodo `run_targeted_tests`: corre los checks allowlisted."""
    checks = state.get("checks") or default_checks or []
    if not checks:
        return _set_result(
            state,
            GateResult(
                verdict=GateVerdict.NEEDS_INPUT,
                summary="No safe check profile was selected",
                next_action="Select at least one allowlisted check",
            ),
        )
    evidence = tuple(test_runner(profile) for profile in checks)
    failed = any(item.exit_code != 0 for item in evidence)
    retry_count = int(state.get("retry_count", 0))
    result = GateResult(
        verdict=GateVerdict.FAIL if failed else GateVerdict.PASS,
        evidence=evidence,
        summary="Targeted checks failed" if failed else "Targeted checks passed",
        next_action=(
            "Inspect evidence and retry explicitly" if failed else "Continue to the next gate"
        ),
        attempt=retry_count + 1,
    )
    return _set_result(state, result)


def _handle_review_findings(state: dict[str, Any], **_: Any) -> dict[str, Any]:
    """Handler del nodo `review_findings`: evalua la severidad de los findings."""
    findings = tuple(GateFinding.from_dict(item) for item in state.get("findings", []))
    if not state.get("review_complete"):
        verdict = GateVerdict.NEEDS_INPUT
        summary = "Review evidence needs an explicit decision"
    elif any(
        finding.severity in (FindingSeverity.HIGH, FindingSeverity.CRITICAL) for finding in findings
    ):
        verdict = GateVerdict.FAIL
        summary = "Blocking review findings remain"
    else:
        verdict = GateVerdict.PASS
        summary = "Review completed without blocking findings"
    return _set_result(
        state,
        GateResult(
            verdict=verdict,
            findings=findings,
            summary=summary,
            next_action=(
                "Resolve blocking findings"
                if verdict is GateVerdict.FAIL
                else "Record an explicit review decision"
                if verdict is GateVerdict.NEEDS_INPUT
                else "Continue"
            ),
        ),
    )


def _handle_formulate_hypotheses(state: dict[str, Any], **_: Any) -> dict[str, Any]:
    """Handler del nodo `formulate_hypotheses`: exige hipotesis + root cause."""
    hypotheses = state.get("hypotheses", [])
    root_cause = state.get("root_cause", "")
    verdict = GateVerdict.PASS if hypotheses and root_cause else GateVerdict.NEEDS_INPUT
    return _set_result(
        state,
        GateResult(
            verdict=verdict,
            summary=(
                "Root cause and hypotheses recorded"
                if verdict is GateVerdict.PASS
                else "Debugging needs hypotheses and a selected root cause"
            ),
            next_action=(
                "Run the targeted reproducer"
                if verdict is GateVerdict.PASS
                else "Add evidence-backed hypotheses and choose a root cause"
            ),
            metadata={"hypothesis_count": len(hypotheses)},
        ),
    )


def _skip_multi_review(state: dict[str, Any]) -> dict[str, Any]:
    """Retorna el resultado cuando el multi-provider review no esta habilitado."""
    current = _current_result(state)
    return _set_result(
        state,
        GateResult(
            verdict=GateVerdict.SKIPPED,
            findings=current.findings if current else (),
            evidence=current.evidence if current else (),
            summary="Multi-provider review was not enabled",
            next_action="Continue with local evidence",
            metadata={"provider_calls": 0},
        ),
    )


def _ready_provider_ids(config: dict[str, Any]) -> list[str]:
    """Extrae los ids de providers en estado `ready` del config multi-provider."""
    return [item["id"] for item in config.get("providers", []) if item.get("status") == "ready"]


def _multi_review_preconditions_met(
    state: dict[str, Any], config: dict[str, Any], providers: list[str]
) -> bool:
    """Verifica que el diff sea seguro y haya providers/presupuesto suficientes."""
    unsafe = state.get("diff_has_secrets") or state.get("diff_size_bytes", 0) > 200_000
    cost_limit = config.get("max_cost_units", 0)
    return not (unsafe or len(providers) < 2 or cost_limit < len(providers))


def _multi_review_needs_input(state: dict[str, Any]) -> dict[str, Any]:
    """Retorna el resultado cuando las precondiciones de multi-provider no se cumplen."""
    return _set_result(
        state,
        GateResult(
            verdict=GateVerdict.NEEDS_INPUT,
            summary="Multi-provider preconditions were not satisfied",
            next_action="Use at least two ready providers and safe metadata limits",
            metadata={"provider_calls": 0},
        ),
    )


def _multi_review_missing_reviewer(state: dict[str, Any]) -> dict[str, Any]:
    """Retorna el resultado cuando no hay provider_reviewer configurado."""
    return _set_result(
        state,
        GateResult(
            verdict=GateVerdict.NEEDS_INPUT,
            summary="No provider reviewer is configured",
            next_action="Configure the opt-in reviewer or continue with local evidence",
            metadata={"provider_calls": 0},
        ),
    )


def _build_scope_summary(state: dict[str, Any]) -> dict[str, Any]:
    """Arma el resumen de scope que se envia a cada provider reviewer."""
    return {
        "scope_files": state.get("scope_files", []),
        "issue_summary": state.get("issue_summary", ""),
        "finding_count": len(state.get("findings", [])),
    }


def _collect_provider_findings(
    providers: list[str],
    provider_reviewer: ProviderReviewer,
    scope_summary: dict[str, Any],
) -> tuple[list[GateFinding], int, int]:
    """Invoca cada provider reviewer y acumula findings, llamadas y fallos.

    Returns:
        Tupla (all_findings, calls, failures).
    """
    all_findings: list[GateFinding] = []
    failures = 0
    calls = 0
    for provider in providers:
        try:
            calls += 1
            for payload in provider_reviewer(provider, scope_summary):
                enriched = dict(payload)
                provenance = list(enriched.get("provenance", []))
                provenance.append(provider)
                enriched["provenance"] = provenance
                all_findings.append(GateFinding.from_dict(enriched))
        except Exception:
            failures += 1
    return all_findings, calls, failures


def _resolve_multi_review_verdict(
    config: dict[str, Any], all_findings: list[GateFinding], failures: int
) -> GateVerdict:
    """Decide el verdict final del multi-review segun fallos y severidad."""
    if failures and config.get("failure_policy") == "needs_input":
        return GateVerdict.NEEDS_INPUT
    if any(
        item.severity in (FindingSeverity.HIGH, FindingSeverity.CRITICAL) for item in all_findings
    ):
        return GateVerdict.FAIL
    return GateVerdict.PASS


def _handle_optional_multi_review(
    state: dict[str, Any],
    *,
    provider_reviewer: ProviderReviewer | None,
    **_: Any,
) -> dict[str, Any]:
    """Handler del nodo `optional_multi_review`: revision opt-in multi-provider."""
    config = state.get("multi_provider", {})
    if not config.get("enabled"):
        return _skip_multi_review(state)
    providers = _ready_provider_ids(config)
    if not _multi_review_preconditions_met(state, config, providers):
        return _multi_review_needs_input(state)
    if provider_reviewer is None:
        return _multi_review_missing_reviewer(state)
    scope_summary = _build_scope_summary(state)
    all_findings, calls, failures = _collect_provider_findings(
        providers, provider_reviewer, scope_summary
    )
    verdict = _resolve_multi_review_verdict(config, all_findings, failures)
    return _set_result(
        state,
        GateResult(
            verdict=verdict,
            findings=merge_findings(all_findings),
            summary=f"{calls} opt-in provider review(s) completed",
            next_action=(
                "Resolve provider disagreement or failure"
                if verdict is GateVerdict.NEEDS_INPUT
                else "Resolve blocking provider findings"
                if verdict is GateVerdict.FAIL
                else "Continue"
            ),
            metadata={"provider_calls": calls, "provider_failures": failures},
        ),
    )


def _handle_request_decision(state: dict[str, Any], **_: Any) -> dict[str, Any]:
    """Handler del nodo `request_decision`: exige una decision humana explicita."""
    human_input = state.get("__human_input__", {})
    decision = human_input.get("decision") if isinstance(human_input, dict) else None
    if decision not in ("approve", "reject"):
        return _set_result(
            state,
            GateResult(
                verdict=GateVerdict.NEEDS_INPUT,
                summary="A human decision is required",
                next_action="Approve or reject the gate",
            ),
        )
    verdict = GateVerdict.PASS if decision == "approve" else GateVerdict.FAIL
    current = _current_result(state)
    return _set_result(
        state,
        GateResult(
            verdict=verdict,
            findings=current.findings if current else (),
            evidence=current.evidence if current else (),
            summary=f"Gate decision: {decision}",
            next_action="Finalize" if verdict is GateVerdict.PASS else "Resolve findings",
        ),
    )


def _handle_finalize_result(state: dict[str, Any], **_: Any) -> dict[str, Any]:
    """Handler del nodo `finalize_result`: cierra el gate si el verdict lo permite."""
    current = _current_result(state)
    if current is None:
        current = GateResult(
            verdict=GateVerdict.NEEDS_INPUT,
            summary="No gate result was produced",
            next_action="Run the required quality nodes",
        )
    if current.verdict in (GateVerdict.FAIL, GateVerdict.NEEDS_INPUT):
        raise RuntimeError("Finalize is blocked by the gate verdict")
    return _set_result(
        state,
        GateResult(
            verdict=GateVerdict.PASS,
            findings=current.findings,
            evidence=current.evidence,
            summary="Quality gate completed",
            next_action="The verified operation may continue",
            attempt=current.attempt,
            metadata=current.metadata,
        ),
    )


def _handle_block_finalize(state: dict[str, Any], **_: Any) -> dict[str, Any]:
    """Handler del nodo `block_finalize`: cierra el gate en fail-closed."""
    current = _current_result(state)
    return _set_result(
        state,
        GateResult(
            verdict=GateVerdict.FAIL,
            findings=current.findings if current else (),
            evidence=current.evidence if current else (),
            summary=current.summary if current else "Quality gate failed closed",
            next_action="Resolve findings and retry explicitly",
            attempt=current.attempt if current else 1,
            metadata=current.metadata if current else {},
        ),
    )


def _build_handlers(
    *,
    test_runner: TestRunner,
    provider_reviewer: ProviderReviewer | None,
) -> dict[str, Callable[..., dict[str, Any]]]:
    """Construye la tabla de despacho de handlers del quality gate.

    Cada handler vive como funcion de modulo independiente; aca solo se
    inyectan sus dependencias (`test_runner`, `provider_reviewer`) via
    `functools.partial`, preservando la firma `(state, **args)` que usa
    `build_quality_gate_graphs`.
    """
    return {
        "collect_scope": _handle_collect_scope,
        "run_targeted_tests": functools.partial(
            _handle_run_targeted_tests, test_runner=test_runner
        ),
        "review_findings": _handle_review_findings,
        "formulate_hypotheses": _handle_formulate_hypotheses,
        "optional_multi_review": functools.partial(
            _handle_optional_multi_review, provider_reviewer=provider_reviewer
        ),
        "request_decision": _handle_request_decision,
        "finalize_result": _handle_finalize_result,
        "block_finalize": _handle_block_finalize,
    }


def _route_gate_verdict(state: dict[str, Any]) -> str:
    result = _current_result(state)
    if result is None:
        return GateVerdict.NEEDS_INPUT.value
    return result.verdict.value


def build_quality_gate_graphs(
    *,
    test_runner: TestRunner | None = None,
    provider_reviewer: ProviderReviewer | None = None,
    manifest_dir: Path = _MANIFEST_DIR,
) -> list[StateGraph]:
    """Build the four quality graphs from validated data manifests."""

    handlers = _build_handlers(
        test_runner=test_runner or _default_test_runner,
        provider_reviewer=provider_reviewer,
    )
    graphs: list[StateGraph] = []
    for manifest in load_quality_manifests(manifest_dir).values():
        graph = StateGraph(
            manifest.id,
            manifest.description,
            version=manifest.version,
            metadata={"title": manifest.title, "quality_gate": True},
        )
        for node in manifest.nodes:
            handler = handlers[node.handler]

            def run_node(
                state: dict[str, Any],
                *,
                _handler: Callable[..., dict[str, Any]] = handler,
                _args: dict[str, Any] = node.args,
            ) -> dict[str, Any]:
                return redact_value(_handler(dict(state), **_args))

            graph.add_node(
                node.id,
                run_node,
                metadata={"handler": node.handler},
                interrupt_before=node.interrupt_before,
            )
        graph.set_entry_point(manifest.entry_point)
        for edge in manifest.edges:
            if edge.target is not None:
                graph.add_edge(edge.source, edge.target)
            else:
                graph.add_conditional_edge(
                    edge.source,
                    _route_gate_verdict,
                    edge.condition_map,
                )
        for finish in manifest.finish_points:
            graph.set_finish_point(finish)
        graphs.append(graph)
    return graphs


def quality_catalog() -> list[dict[str, Any]]:
    return [manifest.catalog_dict() for manifest in load_quality_manifests().values()]
