"""SHU Analytics Engine — Agregación y predicción sobre feedback de /shu.

Provee:
- Agregación por usuario: total de ejecuciones, tasa de éxito, categorías top.
- Agregación por categoría: tendencia temporal, usuarios top.
- Skill matrix: usuarios x categorías con success_rate %.
- Predicción de éxito: similitud a goals históricos + base rate de categoría.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, UTC
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Tipos internos ─────────────────────────────────────────────────────────────

_DEFAULT_FEEDBACK_FILE = Path.home() / ".antigravity" / "shu" / "feedback.jsonl"


def _load_records(feedback_file: Path, days: int) -> list[dict]:
    """Carga registros del archivo JSONL dentro de la ventana temporal.

    Args:
        feedback_file: Ruta al archivo feedback.jsonl.
        days: Ventana de días hacia atrás desde ahora.

    Returns:
        Lista de registros filtrados por ventana temporal.
    """
    if not feedback_file.exists():
        return []

    cutoff = datetime.now(UTC) - timedelta(days=days)
    records: list[dict] = []

    try:
        with open(feedback_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    # Parsear timestamp — soporta con y sin timezone
                    ts_str = record.get("timestamp", "")
                    try:
                        if ts_str.endswith("Z"):
                            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        elif "+" in ts_str or ts_str.endswith("00:00"):
                            ts = datetime.fromisoformat(ts_str)
                        else:
                            ts = datetime.fromisoformat(ts_str).replace(tzinfo=UTC)
                    except ValueError:
                        ts = datetime.now(UTC)  # fallback si no se puede parsear
                    if ts >= cutoff:
                        records.append(record)
                except json.JSONDecodeError:
                    logger.debug(f"Línea JSONL inválida ignorada: {line[:80]}")
    except Exception as e:
        logger.error(f"Error cargando feedback: {e}")

    return records


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """Calcula similitud Jaccard entre dos textos usando tokens de palabras.

    Args:
        text_a: Primer texto.
        text_b: Segundo texto.

    Returns:
        Similitud entre 0.0 y 1.0.
    """
    tokens_a = set(text_a.lower().split())
    tokens_b = set(text_b.lower().split())
    if not tokens_a and not tokens_b:
        return 1.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union) if union else 0.0


# ── Engine ─────────────────────────────────────────────────────────────────────


class ShuAnalyticsEngine:
    """Analiza el feedback de /shu para producir métricas y predicciones.

    Attributes:
        feedback_file: Ruta al archivo feedback.jsonl.
    """

    def __init__(self, feedback_file: Path | None = None) -> None:
        """Inicializa el engine.

        Args:
            feedback_file: Ruta al JSONL de feedback. Si es None, usa el
                path default ~/.antigravity/shu/feedback.jsonl.
        """
        self.feedback_file = feedback_file or _DEFAULT_FEEDBACK_FILE

    # ── API pública ────────────────────────────────────────────────────────────

    def aggregate_by_user(self, user_id: str, days: int = 7) -> dict:
        """Agrega métricas de un usuario en la ventana temporal.

        Args:
            user_id: Identificador del usuario.
            days: Ventana de días hacia atrás (default: 7).

        Returns:
            Diccionario con:
            - user_id: str
            - period_days: int
            - total_executions: int
            - success_rate: float — porcentaje 0-100
            - avg_time_ms: float
            - top_categories: list de {category, count, success_rate}
            - error_patterns: list de {pattern, count}
        """
        records = _load_records(self.feedback_file, days)
        user_records = [r for r in records if r.get("user_id", "anonymous") == user_id]

        if not user_records:
            return {
                "user_id": user_id,
                "period_days": days,
                "total_executions": 0,
                "success_rate": 0.0,
                "avg_time_ms": 0.0,
                "top_categories": [],
                "error_patterns": [],
            }

        total = len(user_records)
        successes = sum(1 for r in user_records if r.get("result") == "success")
        success_rate = (successes / total * 100) if total > 0 else 0.0
        avg_time_ms = (
            sum(r.get("execution_time_ms", 0.0) for r in user_records) / total if total > 0 else 0.0
        )

        # Categorías top
        cat_stats: dict[str, dict] = defaultdict(lambda: {"total": 0, "success": 0})
        for r in user_records:
            cat = r.get("category", "unknown")
            cat_stats[cat]["total"] += 1
            if r.get("result") == "success":
                cat_stats[cat]["success"] += 1

        top_categories = sorted(
            [
                {
                    "category": cat,
                    "count": stats["total"],
                    "success_rate": (
                        stats["success"] / stats["total"] * 100 if stats["total"] > 0 else 0.0
                    ),
                }
                for cat, stats in cat_stats.items()
            ],
            key=lambda x: x["count"],
            reverse=True,
        )[:5]

        # Patrones de error: goals que resultaron en error
        error_goals: dict[str, int] = defaultdict(int)
        for r in user_records:
            if r.get("result") == "error":
                goal = r.get("goal", "")
                if goal:
                    # Truncar a 60 chars como patrón
                    pattern = goal[:60]
                    error_goals[pattern] += 1

        error_patterns = [
            {"pattern": pattern, "count": count}
            for pattern, count in sorted(
                error_goals.items(), key=lambda item: item[1], reverse=True
            )[:5]
        ]

        return {
            "user_id": user_id,
            "period_days": days,
            "total_executions": total,
            "success_rate": round(success_rate, 2),
            "avg_time_ms": round(avg_time_ms, 2),
            "top_categories": top_categories,
            "error_patterns": error_patterns,
        }

    def aggregate_by_category(self, category: str, days: int = 7) -> dict:
        """Agrega métricas de una categoría en la ventana temporal.

        Args:
            category: Nombre de la categoría.
            days: Ventana de días hacia atrás (default: 7).

        Returns:
            Diccionario con:
            - category: str
            - period_days: int
            - total_executions: int
            - success_rate: float — porcentaje 0-100
            - avg_time_ms: float
            - top_users: list de {user_id, count, success_rate}
            - improvement_trend: list de {day, success_rate} (hasta 30 días)
        """
        records = _load_records(self.feedback_file, days)
        cat_records = [r for r in records if r.get("category") == category]

        if not cat_records:
            return {
                "category": category,
                "period_days": days,
                "total_executions": 0,
                "success_rate": 0.0,
                "avg_time_ms": 0.0,
                "top_users": [],
                "improvement_trend": [],
            }

        total = len(cat_records)
        successes = sum(1 for r in cat_records if r.get("result") == "success")
        success_rate = (successes / total * 100) if total > 0 else 0.0
        avg_time_ms = (
            sum(r.get("execution_time_ms", 0.0) for r in cat_records) / total if total > 0 else 0.0
        )

        # Usuarios top
        user_stats: dict[str, dict] = defaultdict(lambda: {"total": 0, "success": 0})
        for r in cat_records:
            uid = r.get("user_id", "anonymous")
            user_stats[uid]["total"] += 1
            if r.get("result") == "success":
                user_stats[uid]["success"] += 1

        top_users = sorted(
            [
                {
                    "user_id": uid,
                    "count": stats["total"],
                    "success_rate": (
                        stats["success"] / stats["total"] * 100 if stats["total"] > 0 else 0.0
                    ),
                }
                for uid, stats in user_stats.items()
            ],
            key=lambda x: x["count"],
            reverse=True,
        )[:5]

        # Tendencia de mejora: success_rate por día
        day_stats: dict[str, dict] = defaultdict(lambda: {"total": 0, "success": 0})
        for r in cat_records:
            ts_str = r.get("timestamp", "")
            try:
                if ts_str.endswith("Z"):
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                elif "+" in ts_str:
                    ts = datetime.fromisoformat(ts_str)
                else:
                    ts = datetime.fromisoformat(ts_str).replace(tzinfo=UTC)
                day_key = ts.strftime("%Y-%m-%d")
            except ValueError:
                day_key = "unknown"

            day_stats[day_key]["total"] += 1
            if r.get("result") == "success":
                day_stats[day_key]["success"] += 1

        improvement_trend = sorted(
            [
                {
                    "day": day,
                    "success_rate": (
                        stats["success"] / stats["total"] * 100 if stats["total"] > 0 else 0.0
                    ),
                }
                for day, stats in day_stats.items()
                if day != "unknown"
            ],
            key=lambda x: x["day"],
        )

        return {
            "category": category,
            "period_days": days,
            "total_executions": total,
            "success_rate": round(success_rate, 2),
            "avg_time_ms": round(avg_time_ms, 2),
            "top_users": top_users,
            "improvement_trend": improvement_trend,
        }

    def get_user_skill_matrix(self) -> dict:
        """Construye la matriz usuarios x categorías con success_rate %.

        Usa todos los registros disponibles (sin ventana temporal).

        Returns:
            Diccionario con:
            - users: list[str] — user_ids ordenados
            - categories: list[str] — categorías ordenadas
            - matrix: list[list[float]] — success_rate % por (user, category).
              -1.0 indica sin datos para esa combinación.
        """
        # Cargar todos los registros (ventana amplia: 365 días)
        records = _load_records(self.feedback_file, 365)

        if not records:
            return {"users": [], "categories": [], "matrix": []}

        # Construir índice (user_id, category) → {total, success}
        cell_stats: dict[tuple[str, str], dict] = defaultdict(lambda: {"total": 0, "success": 0})
        all_users: set[str] = set()
        all_categories: set[str] = set()

        for r in records:
            uid = r.get("user_id", "anonymous")
            cat = r.get("category", "unknown")
            all_users.add(uid)
            all_categories.add(cat)
            cell_stats[(uid, cat)]["total"] += 1
            if r.get("result") == "success":
                cell_stats[(uid, cat)]["success"] += 1

        users = sorted(all_users)
        categories = sorted(all_categories)

        matrix: list[list[float]] = []
        for uid in users:
            row: list[float] = []
            for cat in categories:
                stats = cell_stats.get((uid, cat))
                if stats and stats["total"] > 0:
                    rate = stats["success"] / stats["total"] * 100
                    row.append(round(rate, 2))
                else:
                    row.append(-1.0)  # sin datos
            matrix.append(row)

        return {
            "users": users,
            "categories": categories,
            "matrix": matrix,
        }

    def predict_success_rate(self, goal_text: str, category: str) -> float:
        """Estima la tasa de éxito para un goal y categoría dados.

        Combina:
        1. Tasa base de éxito de la categoría (histórico completo).
        2. Similitud Jaccard a goals anteriores ponderada por su resultado.

        Args:
            goal_text: Texto del goal a evaluar.
            category: Categoría esperada.

        Returns:
            Porcentaje estimado de éxito entre 0.0 y 100.0.
        """
        records = _load_records(self.feedback_file, 365)

        if not records:
            return 50.0  # default sin datos

        # Tasa base de la categoría
        cat_records = [r for r in records if r.get("category") == category]
        if cat_records:
            cat_successes = sum(1 for r in cat_records if r.get("result") == "success")
            base_rate = cat_successes / len(cat_records) * 100
        else:
            # Sin datos de esta categoría, usar global
            global_successes = sum(1 for r in records if r.get("result") == "success")
            base_rate = global_successes / len(records) * 100 if records else 50.0

        if not goal_text.strip():
            return round(base_rate, 2)

        # Similitud ponderada a goals históricos
        similarity_scores: list[tuple[float, bool]] = []
        for r in records:
            historical_goal = r.get("goal", "")
            if not historical_goal:
                continue
            sim = _jaccard_similarity(goal_text, historical_goal)
            if sim > 0.1:  # umbral mínimo de similitud
                is_success = r.get("result") == "success"
                similarity_scores.append((sim, is_success))

        if not similarity_scores:
            return round(base_rate, 2)

        # Ponderar por similitud
        total_weight = sum(sim for sim, _ in similarity_scores)
        weighted_success = sum(sim for sim, success in similarity_scores if success)
        similarity_rate = (weighted_success / total_weight * 100) if total_weight > 0 else base_rate

        # Combinar: 60% similitud + 40% base rate
        combined = 0.6 * similarity_rate + 0.4 * base_rate

        return round(max(0.0, min(100.0, combined)), 2)

    def list_active_users(self, days: int = 30) -> list[str]:
        """Lista usuarios activos ordenados por actividad descendente.

        Args:
            days: Ventana de días (default: 30).

        Returns:
            Lista de user_ids ordenados por número de ejecuciones.
        """
        records = _load_records(self.feedback_file, days)
        user_counts: dict[str, int] = defaultdict(int)
        for r in records:
            uid = r.get("user_id", "anonymous")
            user_counts[uid] += 1
        return sorted(user_counts.keys(), key=lambda u: user_counts[u], reverse=True)

    def list_active_categories(self, days: int = 30) -> list[str]:
        """Lista categorías activas ordenadas por actividad descendente.

        Args:
            days: Ventana de días (default: 30).

        Returns:
            Lista de categorías ordenadas por número de ejecuciones.
        """
        records = _load_records(self.feedback_file, days)
        cat_counts: dict[str, int] = defaultdict(int)
        for r in records:
            cat = r.get("category", "unknown")
            cat_counts[cat] += 1
        return sorted(cat_counts.keys(), key=lambda c: cat_counts[c], reverse=True)
