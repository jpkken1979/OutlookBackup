from __future__ import annotations
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
logger = logging.getLogger(__name__)


def run(
    goal: str,
    category_detected: str,
    user_responses: list[str],
    execution_result: str,
    execution_time_ms: float,
) -> None:
    agent_root = str(Path(__file__).parent.parent.parent / '.agent')
    if agent_root not in sys.path:
        sys.path.insert(0, agent_root)
    try:
        from core.shu_auto_improvement import ShuFeedbackCollector, ShuImprovementEngine
        from core.shu_brain_integration import ShuBrainIntegrator
        collector = ShuFeedbackCollector()
        collector.record(
            goal=goal,
            category=category_detected,
            responses=user_responses,
            result=execution_result,
            execution_time_ms=execution_time_ms,
        )
        try:
            integrator = ShuBrainIntegrator()
            node_id = integrator.ingest_execution(
                goal=goal,
                category=category_detected,
                responses=user_responses,
                result=execution_result,
                execution_time_ms=execution_time_ms,
            )
            logger.info('[INFO] SHU -> Brain: nodo creado %s', node_id)
        except Exception as brain_exc:
            logger.debug('[DEBUG] SHU Brain ingest (execution) skipped: %s', brain_exc)
        feedback_dir = Path.home() / '.antigravity' / 'shu'
        feedback_file = feedback_dir / 'feedback.jsonl'
        if feedback_file.exists():
            file_lines = [
                l for l in feedback_file.read_text(encoding='utf-8').strip().split('\n')
                if l.strip()
            ]
            if len(file_lines) >= 50:
                engine = ShuImprovementEngine(feedback_file=feedback_file)
                suggestions = engine.suggest_improvements()
                suggestions_file = feedback_dir / 'last_suggestions.json'
                suggestions_data = {'timestamp': datetime.utcnow().isoformat() + 'Z', **suggestions}
                suggestions_file.write_text(
                    json.dumps(suggestions_data, ensure_ascii=False, indent=2),
                    encoding='utf-8',
                )
                logger.info('[INFO] Shu auto-improvement: %s sugerencias generadas', len(suggestions.get('recommendations', [])))
                try:
                    integrator = ShuBrainIntegrator()
                    affected = suggestions.get('affected_templates', [])
                    improvement_id = integrator.ingest_improvement(
                        suggestions=suggestions,
                        affected_templates=affected if isinstance(affected, list) else [],
                    )
                    logger.info('[INFO] SHU -> Brain: mejora ingestada %s', improvement_id)
                except Exception as brain_exc:
                    logger.debug('[DEBUG] SHU Brain ingest (improvement) skipped: %s', brain_exc)
    except Exception as e:
        logger.error('[ERROR] Post-shu hook failed: %s: %s', type(e).__name__, e)


if __name__ == '__main__':
    run(
        goal='Test goal',
        category_detected='test',
        user_responses=['r1', 'r2', 'r3', 'r4', 'r5', 'r6'],
        execution_result='success',
        execution_time_ms=1000.0,
    )
