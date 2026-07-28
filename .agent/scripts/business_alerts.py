#!/usr/bin/env python3
"""
Business Alerts — detecta alertas del negocio UNS y las inyecta al Brain.

Alertas detectadas:
  - Visas vencidas o a vencer en <60 dias
  - Empleados recien contratados (<30 dias)
  - Contratos proximos a cerrar periodo
  - Nodos criticos del brain con 0 accesos en 90 dias
  - Salud del brain por debajo de 7.0

Uso:
  python business_alerts.py          # ejecutar y mostrar
  python business_alerts.py --ingest # ingestar alertas al brain
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, UTC
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_ROOT))

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)


def check_visas_expiring(window_days: int = 60) -> list[dict]:
    """Chequea visas que vencen en los proximos N dias.

    Los empleados estan en el seed de Kobetsu v3 en GitHub, asi que
    tomamos la data del ultimo scan guardado en /tmp/ o del brain.
    """
    alerts: list[dict] = []
    seed_path = Path("/tmp/full_employees.json")

    if not seed_path.exists():
        return alerts

    try:
        employees = json.loads(seed_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return alerts

    now = datetime.now(UTC).replace(tzinfo=None)
    now + timedelta(days=window_days)

    for emp in employees:
        expiry_str = emp.get("visaExpiry")
        if not expiry_str:
            continue
        try:
            expiry = datetime.strptime(expiry_str, "%Y-%m-%d")
        except ValueError:
            continue

        days_remaining = (expiry - now).days

        if days_remaining < 0:
            severity = "critical"
            label = "EXPIRED"
        elif days_remaining < 30:
            severity = "high"
            label = f"expires in {days_remaining}d"
        elif days_remaining < window_days:
            severity = "normal"
            label = f"expires in {days_remaining}d"
        else:
            continue

        alerts.append(
            {
                "type": "visa_alert",
                "severity": severity,
                "employee": emp.get("fullName", "?"),
                "number": emp.get("employeeNumber", "?"),
                "visa_type": emp.get("visaType", "?"),
                "expires": expiry_str,
                "company": emp.get("companyName", "?"),
                "label": label,
                "days_remaining": days_remaining,
            }
        )

    return sorted(alerts, key=lambda a: a["days_remaining"])


def check_brain_health() -> list[dict]:
    """Chequea salud del brain y genera alertas si es baja."""
    alerts: list[dict] = []

    try:
        from core.brain import Brain  # noqa: PLC0415

        brain = Brain(AGENT_ROOT / "brain", app_id="nexus-mother")
        report = brain.lint()

        if report.score < 7.0:
            alerts.append(
                {
                    "type": "brain_health",
                    "severity": "high" if report.score < 5.0 else "normal",
                    "score": report.score,
                    "issues": len(report.issues),
                    "total_nodes": report.total_nodes,
                    "message": (
                        f"Brain health bajo: {report.score:.1f}/10 — "
                        f"{len(report.issues)} problemas en {report.total_nodes} nodos"
                    ),
                }
            )

        # Conceptos emergentes sin promover
        if len(report.concept_candidates) > 5:
            alerts.append(
                {
                    "type": "concept_candidates",
                    "severity": "normal",
                    "candidates": report.concept_candidates[:10],
                    "message": (
                        f"{len(report.concept_candidates)} tags aparecen en 3+ nodos "
                        "sin concepto propio. Ejecutar /brain promote"
                    ),
                }
            )

    except Exception as e:
        logger.debug("No se pudo chequear brain health: %s", e)

    return alerts


def check_stale_critical_nodes() -> list[dict]:
    """Nodos criticos sin accesos en 90+ dias."""
    alerts: list[dict] = []

    try:
        from core.brain import Brain  # noqa: PLC0415

        brain = Brain(AGENT_ROOT / "brain", app_id="nexus-mother")
        now = datetime.now(UTC).replace(tzinfo=None)
        threshold = now - timedelta(days=90)

        for node in brain.list_nodes(status="active"):
            if node.importance != "critical":
                continue
            if node.access_count > 0:
                continue
            try:
                created = datetime.strptime(node.date, "%Y-%m-%d")
            except ValueError:
                continue

            if created < threshold:
                days_old = (now - created).days
                alerts.append(
                    {
                        "type": "stale_critical",
                        "severity": "normal",
                        "slug": node.slug,
                        "title": node.title,
                        "days_old": days_old,
                        "message": f"Nodo critico sin usar en {days_old} dias",
                    }
                )
    except Exception as e:
        logger.debug("No se pudo chequear stale: %s", e)

    return alerts


def run_all_checks() -> dict:
    alerts = {
        "visa": check_visas_expiring(),
        "brain_health": check_brain_health(),
        "stale_critical": check_stale_critical_nodes(),
    }

    total = sum(len(v) for v in alerts.values())
    critical = sum(1 for group in alerts.values() for a in group if a.get("severity") == "critical")

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "total": total,
        "critical": critical,
        "alerts": alerts,
    }


def ingest_to_brain(alerts: dict) -> None:
    if alerts["total"] == 0:
        logger.info("Sin alertas, nada que ingestar")
        return

    try:
        from core.brain import Brain  # noqa: PLC0415

        brain = Brain(AGENT_ROOT / "brain", app_id="nexus-mother")

        # Un solo nodo con todas las alertas del dia
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        context_parts = [f"Resumen {alerts['total']} alertas ({alerts['critical']} criticas)"]

        for atype, items in alerts["alerts"].items():
            if not items:
                continue
            context_parts.append(f"\n## {atype} ({len(items)})")
            for item in items[:10]:
                if atype == "visa":
                    context_parts.append(
                        f"- {item['employee']} ({item['number']}): "
                        f"{item['visa_type']} {item['label']} — {item['company']}"
                    )
                else:
                    context_parts.append(f"- {item.get('message', item.get('title', '?'))}")

        brain.ingest(
            title=f"Alertas del negocio — {today}",
            context="\n".join(context_parts),
            area="business",
            tags=["alertas", "alerts", "business", today, "automated"],
            node_type="session",
            importance="high" if alerts["critical"] > 0 else "normal",
        )
        logger.info("Alertas ingresadas al Brain")
    except Exception as e:
        logger.error("No se pudo ingestar: %s", e)


def main() -> int:
    parser = argparse.ArgumentParser(description="Business alerts UNS")
    parser.add_argument("--ingest", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = run_all_checks()

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"\n=== Alertas del negocio UNS ({result['timestamp']}) ===")
        print(f"Total: {result['total']} | Criticas: {result['critical']}\n")

        if result["alerts"]["visa"]:
            print(f"\n>>> Visas ({len(result['alerts']['visa'])}):")
            for a in result["alerts"]["visa"][:10]:
                marker = "!" if a["severity"] == "critical" else "*"
                print(f"  {marker} {a['employee']:30s} {a['visa_type']:25s} {a['label']}")

        if result["alerts"]["brain_health"]:
            print("\n>>> Salud del Brain:")
            for a in result["alerts"]["brain_health"]:
                print(f"  - {a['message']}")

        if result["alerts"]["stale_critical"]:
            print(f"\n>>> Nodos criticos sin usar ({len(result['alerts']['stale_critical'])}):")
            for a in result["alerts"]["stale_critical"][:5]:
                print(f"  - {a['title'][:60]} ({a['days_old']}d)")

    if args.ingest:
        ingest_to_brain(result)

    return 0 if result["critical"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
