"""UI/UX Designer — orquestador principal del pipeline de análisis y generación."""
import asyncio
import logging
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from analyzers.a11y_auditor import A11yViolation, audit_url
from analyzers.contrast_checker import ContrastResult, check_tokens_contrast
from analyzers.token_extractor import TokenExtractionResult, extract_tokens_from_project
from analyzers.visual_analyzer import VisualFeedback, analyze_screenshot
from evaluators.nielsen_judge import NielsenReport, run_nielsen_evaluation
from generators.component_gen import GeneratedComponent, generate_component
from generators.token_gen import TokenGenResult, generate_token_file

logger = logging.getLogger(__name__)

_DEV_PORTS = (1420, 5173, 3000, 8080)


@dataclass
class DesignReport:
    """Reporte completo del análisis UI/UX."""

    project_path: str
    stack_detected: dict = field(default_factory=dict)
    tokens: dict = field(default_factory=dict)
    token_drift: list[str] = field(default_factory=list)
    contrast_violations: list[ContrastResult] = field(default_factory=list)
    a11y_violations: list[A11yViolation] = field(default_factory=list)
    visual_feedback: list[VisualFeedback] = field(default_factory=list)
    nielsen_report: Optional[NielsenReport] = None
    components_generated: list[str] = field(default_factory=list)
    tokens_file: Optional[str] = None
    score_global: float = 0.0
    approved: bool = False


def _detect_dev_server() -> Optional[str]:
    """Detecta si hay un dev server activo en puertos conocidos."""
    for port in _DEV_PORTS:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return f"http://localhost:{port}"
        except OSError:
            pass
    return None


def _detect_stack(project_path: Path) -> dict:
    """Detecta el stack tecnológico del proyecto.

    Args:
        project_path: Ruta raíz del proyecto.

    Returns:
        Diccionario con flags del stack detectado.
    """
    return {
        "tailwind_v4": any(project_path.rglob("*.css")),
        "react": (project_path / "package.json").exists(),
        "tauri": (project_path / "src-tauri").exists(),
    }


class UIUXDesigner:
    """Orquestador del pipeline completo de análisis y mejora UI/UX."""

    async def analyze_project(
        self,
        project_path: str,
        dev_server_url: Optional[str] = None,
        generate: bool = False,
        component_description: Optional[str] = None,
    ) -> "DesignReport":
        """Ejecuta el pipeline completo de análisis UI/UX.

        Args:
            project_path: Ruta raíz del proyecto.
            dev_server_url: URL del dev server (auto-detectado si None).
            generate: Si True, genera componentes corregidos.
            component_description: Descripción del componente a generar.

        Returns:
            DesignReport con resultados completos.
        """
        path = Path(project_path)
        report = DesignReport(project_path=project_path)
        report.stack_detected = _detect_stack(path)

        server_url = dev_server_url or _detect_dev_server()
        if server_url:
            logger.info("Dev server detectado en %s", server_url)

        # FASE 1: Extracción de tokens
        token_result: TokenExtractionResult = extract_tokens_from_project(path)
        report.tokens = token_result.tokens
        report.token_drift = token_result.drift_violations

        # FASE 2: Análisis en paralelo
        async def _no_a11y() -> list:
            return []

        contrast_task = asyncio.to_thread(check_tokens_contrast, token_result.tokens)
        a11y_task = asyncio.to_thread(audit_url, server_url) if server_url else _no_a11y()
        nielsen_task = run_nielsen_evaluation(
            code_context=_collect_code_context(path),
            config_path=Path(__file__).parent.parent / "config" / "heuristics.json",
        )
        visual_task = asyncio.to_thread(
            analyze_screenshot, _find_latest_screenshot(path)
        )

        contrast_results, a11y_results, nielsen_report, visual_results = await asyncio.gather(
            contrast_task, a11y_task, nielsen_task, visual_task,
            return_exceptions=True,
        )

        report.contrast_violations = contrast_results if isinstance(contrast_results, list) else []
        report.a11y_violations = a11y_results if isinstance(a11y_results, list) else []
        report.nielsen_report = (
            nielsen_report if isinstance(nielsen_report, NielsenReport) else None
        )
        report.visual_feedback = visual_results if isinstance(visual_results, list) else []

        # FASE 3: Generación (opcional)
        if generate and component_description:
            violations_summary = [v.description for v in report.a11y_violations[:5]]
            component: GeneratedComponent = await generate_component(
                description=component_description,
                tokens=report.tokens,
                violations=violations_summary,
            )
            out_dir = path / ".ui-ux-artifacts"
            out_dir.mkdir(exist_ok=True)
            comp_file = out_dir / "generated_component.tsx"
            comp_file.write_text(component.tsx_content, encoding="utf-8")
            report.components_generated.append(str(comp_file))

        # FASE 4: Exportar tokens
        if report.tokens:
            artifacts = path / ".ui-ux-artifacts"
            token_result_file: TokenGenResult = generate_token_file(report.tokens, artifacts)
            report.tokens_file = str(token_result_file.dtcg_path)

        report.score_global = _compute_global_score(report)
        report.approved = report.score_global >= 7.5 and not any(
            v.impact == "critical" for v in report.a11y_violations
        )

        return report


def _collect_code_context(project_path: Path, max_chars: int = 4000) -> str:
    """Recolecta contexto de código relevante del proyecto.

    Args:
        project_path: Ruta raíz del proyecto.
        max_chars: Máximo de caracteres a recolectar.

    Returns:
        Concatenación de snippets de código TSX/JSX del proyecto.
    """
    snippets: list[str] = []
    total = 0
    for ext in ("*.tsx", "*.jsx"):
        for f in sorted(project_path.rglob(ext)):
            if "node_modules" not in str(f) and total < max_chars:
                try:
                    text = f.read_text(encoding="utf-8")[:500]
                    snippets.append(f"// {f.name}\n{text}")
                    total += len(text)
                except Exception:
                    pass
    return "\n\n".join(snippets)


def _find_latest_screenshot(project_path: Path) -> Path:
    """Busca el screenshot más reciente en artifacts.

    Args:
        project_path: Ruta raíz del proyecto.

    Returns:
        Path al screenshot más reciente, o Path('/nonexistent') si no hay ninguno.
    """
    artifacts = project_path / ".ui-ux-artifacts"
    screenshots = list(artifacts.glob("*.png")) if artifacts.exists() else []
    return (
        max(screenshots, key=lambda f: f.stat().st_mtime) if screenshots else Path("/nonexistent")
    )


def _compute_global_score(report: "DesignReport") -> float:
    """Calcula score global compuesto (0-10).

    Args:
        report: DesignReport con resultados del análisis.

    Returns:
        Score global entre 0.0 y 10.0.
    """
    scores: list[float] = []

    if report.nielsen_report:
        scores.append(report.nielsen_report.global_score)

    critical = sum(1 for v in report.a11y_violations if v.impact == "critical")
    serious = sum(1 for v in report.a11y_violations if v.impact == "serious")
    a11y_penalty = min(3.0, critical * 1.0 + serious * 0.3)
    scores.append(max(0.0, 10.0 - a11y_penalty))

    drift_penalty = min(2.0, len(report.token_drift) * 0.2)
    scores.append(max(0.0, 10.0 - drift_penalty))

    return round(sum(scores) / len(scores), 2) if scores else 0.0


async def main() -> "DesignReport":
    """CLI entry point for ui-ux-designer agent."""
    import sys

    project_path = sys.argv[1] if len(sys.argv) > 1 else "."
    agent = UIUXDesigner()
    return await agent.analyze_project(project_path)


if __name__ == "__main__":
    import asyncio

    report = asyncio.run(main())
    print(f"Global score: {report.score_global} — Approved: {report.approved}")


def main_wrapper():
    """main_wrapper-compatible entry point for ui-ux-designer agent."""
    return asyncio.run(main())
