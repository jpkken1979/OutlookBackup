#!/usr/bin/env python3
"""Generate demo escalations data for testing the Nexus EscalationsCard."""

import json
from datetime import datetime, timedelta
from pathlib import Path


def generate_demo_escalations():
    """Generate demo escalations.jsonl file."""
    home = Path.home()
    antigravity_dir = home / ".antigravity" / "shu"
    antigravity_dir.mkdir(parents=True, exist_ok=True)

    escalations_file = antigravity_dir / "escalations.jsonl"

    # Generate 15 demo escalations with various statuses
    demo_escalations = [
        {
            "id": "esc_001",
            "timestamp": (datetime.utcnow() - timedelta(days=10)).isoformat() + "Z",
            "goal": "Fix authentication bypass in login module",
            "resolution_status": "resolved",
        },
        {
            "id": "esc_002",
            "timestamp": (datetime.utcnow() - timedelta(days=8)).isoformat() + "Z",
            "goal": "Database migration failed during production deployment",
            "resolution_status": "resolved",
        },
        {
            "id": "esc_003",
            "timestamp": (datetime.utcnow() - timedelta(days=6)).isoformat() + "Z",
            "goal": "Memory leak in background worker causing OOM errors",
            "resolution_status": "resolved",
        },
        {
            "id": "esc_004",
            "timestamp": (datetime.utcnow() - timedelta(days=5)).isoformat() + "Z",
            "goal": "Critical: API rate limiter causing false positives",
            "resolution_status": "critical",
        },
        {
            "id": "esc_005",
            "timestamp": (datetime.utcnow() - timedelta(days=4)).isoformat() + "Z",
            "goal": "Test coverage for payment processing module below 60%",
            "resolution_status": "resolved",
        },
        {
            "id": "esc_006",
            "timestamp": (datetime.utcnow() - timedelta(days=3)).isoformat() + "Z",
            "goal": "Cache invalidation strategy needs optimization",
            "resolution_status": "pending",
        },
        {
            "id": "esc_007",
            "timestamp": (datetime.utcnow() - timedelta(days=2, hours=12)).isoformat() + "Z",
            "goal": "Improve error logging for better observability",
            "resolution_status": "pending",
        },
        {
            "id": "esc_008",
            "timestamp": (datetime.utcnow() - timedelta(days=2)).isoformat() + "Z",
            "goal": "Performance regression in search endpoint detected",
            "resolution_status": "resolved",
        },
        {
            "id": "esc_009",
            "timestamp": (datetime.utcnow() - timedelta(days=1, hours=18)).isoformat() + "Z",
            "goal": "Critical: Security vulnerability in file upload handler",
            "resolution_status": "critical",
        },
        {
            "id": "esc_010",
            "timestamp": (datetime.utcnow() - timedelta(days=1, hours=6)).isoformat() + "Z",
            "goal": "Database query timeout on user dashboard causing timeouts",
            "resolution_status": "pending",
        },
        {
            "id": "esc_011",
            "timestamp": (datetime.utcnow() - timedelta(hours=12)).isoformat() + "Z",
            "goal": "Implement proper transaction handling in payment service",
            "resolution_status": "pending",
        },
        {
            "id": "esc_012",
            "timestamp": (datetime.utcnow() - timedelta(hours=8)).isoformat() + "Z",
            "goal": "Dependency conflict between lodash and underscore libraries",
            "resolution_status": "resolved",
        },
        {
            "id": "esc_013",
            "timestamp": (datetime.utcnow() - timedelta(hours=4)).isoformat() + "Z",
            "goal": "Add comprehensive documentation for API endpoints",
            "resolution_status": "pending",
        },
        {
            "id": "esc_014",
            "timestamp": (datetime.utcnow() - timedelta(hours=2)).isoformat() + "Z",
            "goal": "Critical: Service health check endpoint not responding",
            "resolution_status": "critical",
        },
        {
            "id": "esc_015",
            "timestamp": (datetime.utcnow() - timedelta(minutes=30)).isoformat() + "Z",
            "goal": "Refactor database schema for better normalization",
            "resolution_status": "pending",
        },
    ]

    # Write to JSONL format
    with open(escalations_file, "w") as f:
        for esc in demo_escalations:
            f.write(json.dumps(esc) + "\n")

    print(f"Generated {len(demo_escalations)} demo escalations at {escalations_file}")
    print("Stats:")
    print(f"  - Total: {len(demo_escalations)}")
    resolved = sum(1 for e in demo_escalations if e["resolution_status"] == "resolved")
    pending = sum(1 for e in demo_escalations if e["resolution_status"] == "pending")
    critical = sum(1 for e in demo_escalations if e["resolution_status"] == "critical")
    print(f"  - Resolved: {resolved}")
    print(f"  - Pending: {pending}")
    print(f"  - Critical: {critical}")
    print(f"  - Resolution %: {(resolved / len(demo_escalations) * 100):.1f}%")


if __name__ == "__main__":
    generate_demo_escalations()
