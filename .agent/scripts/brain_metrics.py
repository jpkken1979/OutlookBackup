#!/usr/bin/env python3
"""
Brain Metrics — Metricas de uso del Brain Network.

Registra y reporta:
  - Queries por dia/hora
  - Nodos mas accedidos
  - Tiempo de respuesta promedio
  - Ratio hit/miss
  - Tags mas buscados

Uso:
  python brain_metrics.py                    # report dashboard
  python brain_metrics.py --record query "kobetsu" 45  # registrar query+latency_ms
  python brain_metrics.py --json             # salida JSON
  python brain_metrics.py --reset            # borrar historico
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from datetime import datetime, timedelta, UTC
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)

AGENT_ROOT = Path(__file__).resolve().parent.parent
METRICS_FILE = AGENT_ROOT / "brain" / ".metrics.jsonl"
METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)


def record_event(event_type: str, data: dict) -> None:
    """Registra un evento en el log JSONL."""
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "type": event_type,
        **data,
    }
    with METRICS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_events(days: int = 30) -> list[dict]:
    """Carga eventos de los ultimos N dias."""
    if not METRICS_FILE.exists():
        return []

    cutoff = datetime.now(UTC) - timedelta(days=days)
    events = []
    try:
        with METRICS_FILE.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    ts = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
                    if ts >= cutoff:
                        events.append(e)
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
    except OSError:
        pass
    return events


def compute_metrics(events: list[dict]) -> dict:
    """Computa metricas desde eventos."""
    queries = [e for e in events if e.get("type") == "query"]
    ingests = [e for e in events if e.get("type") == "ingest"]
    accesses = [e for e in events if e.get("type") == "access"]

    # Por dia (ultimos 7)
    by_day: Counter = Counter()
    now = datetime.now(UTC)
    for e in events:
        try:
            ts = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
            days_ago = (now - ts).days
            if days_ago < 7:
                key = ts.strftime("%Y-%m-%d")
                by_day[key] += 1
        except (ValueError, KeyError):
            continue

    # Latencia promedio
    latencies = [e.get("latency_ms", 0) for e in queries if e.get("latency_ms")]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    # Queries mas frecuentes
    query_texts: Counter = Counter(e.get("query", "")[:60] for e in queries if e.get("query"))

    # Nodos mas accedidos
    slug_counts: Counter = Counter(e.get("slug", "") for e in accesses if e.get("slug"))

    # Hits vs misses
    hits = sum(1 for e in queries if e.get("results_count", 0) > 0)
    misses = len(queries) - hits
    hit_rate = (hits / len(queries) * 100) if queries else 0

    return {
        "period_days": 30,
        "total_events": len(events),
        "queries": len(queries),
        "ingests": len(ingests),
        "accesses": len(accesses),
        "avg_latency_ms": round(avg_latency, 1),
        "hit_rate_pct": round(hit_rate, 1),
        "hits": hits,
        "misses": misses,
        "by_day": dict(sorted(by_day.items())),
        "top_queries": dict(query_texts.most_common(10)),
        "top_accessed_nodes": dict(slug_counts.most_common(10)),
    }


def print_report(metrics: dict) -> None:
    """Imprime report legible."""
    print("\n=== Brain Metrics (30 dias) ===")
    print(f"Total eventos: {metrics['total_events']}")
    print(f"  Queries:    {metrics['queries']}")
    print(f"  Ingests:    {metrics['ingests']}")
    print(f"  Accesses:   {metrics['accesses']}")
    print(f"\nLatencia promedio: {metrics['avg_latency_ms']}ms")
    print(
        f"Hit rate: {metrics['hit_rate_pct']}% ({metrics['hits']} hits, {metrics['misses']} misses)"
    )

    if metrics["by_day"]:
        print("\n>>> Actividad ultimos 7 dias:")
        for day, count in metrics["by_day"].items():
            bar = "█" * min(count, 50)
            print(f"  {day}  {bar} {count}")

    if metrics["top_queries"]:
        print("\n>>> Queries mas frecuentes:")
        for q, c in list(metrics["top_queries"].items())[:5]:
            print(f"  {c:3d}x  {q}")

    if metrics["top_accessed_nodes"]:
        print("\n>>> Nodos mas accedidos:")
        for slug, c in list(metrics["top_accessed_nodes"].items())[:5]:
            print(f"  {c:3d}x  {slug}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Brain metrics")
    parser.add_argument("--record", nargs=3, metavar=("TYPE", "QUERY", "LATENCY"))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    if args.reset:
        if METRICS_FILE.exists():
            METRICS_FILE.unlink()
        logger.info("Metrics reset")
        return 0

    if args.record:
        event_type, query, latency = args.record
        record_event(
            event_type,
            {
                "query": query,
                "latency_ms": int(latency) if latency.isdigit() else 0,
            },
        )
        return 0

    events = load_events(days=args.days)
    metrics = compute_metrics(events)

    if args.json:
        print(json.dumps(metrics, indent=2, ensure_ascii=False))
    else:
        print_report(metrics)

    return 0


if __name__ == "__main__":
    sys.exit(main())
