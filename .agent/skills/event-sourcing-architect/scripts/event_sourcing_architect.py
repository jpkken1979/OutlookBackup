#!/usr/bin/env python3
"""
Event Sourcing Architect - DevOps Utilities

Uso:
    python event_sourcing_architect.py --check-docker
    python event_sourcing_architect.py --check-ci
    python event_sourcing_architect.py --all
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)


def check_docker(project_dir: Path) -> dict:
    """Verifica configuración de Docker."""
    results = {"passed": [], "issues": []}

    dockerfile = list(project_dir.glob("**/Dockerfile*"))
    if dockerfile:
        results["passed"].append("Dockerfile encontrado")
        for df in dockerfile:
            content = df.read_text()
            if "USER" not in content:
                results["issues"].append(f"{df}: Sin USER (corre como root)")
            if "latest" in content:
                results["issues"].append(f"{df}: Evitar tag 'latest'")
    else:
        results["issues"].append("No se encontró Dockerfile")

    if (project_dir / ".dockerignore").exists():
        results["passed"].append(".dockerignore existe")
    else:
        results["issues"].append("Falta .dockerignore")

    return results


def check_ci(project_dir: Path) -> dict:
    """Verifica CI/CD."""
    results = {"passed": [], "issues": [], "ci": None}

    ci_files = {
        ".github/workflows": "GitHub Actions",
        ".gitlab-ci.yml": "GitLab CI",
        "Jenkinsfile": "Jenkins",
        ".circleci": "CircleCI",
    }

    for path, name in ci_files.items():
        if (project_dir / path).exists():
            results["ci"] = name
            results["passed"].append(f"CI configurado: {name}")
            break

    if not results["ci"]:
        results["issues"].append("No se encontró CI/CD")

    return results


def check_env(project_dir: Path) -> dict:
    """Verifica variables de entorno."""
    results = {"passed": [], "issues": []}

    if (project_dir / ".env.example").exists():
        results["passed"].append(".env.example existe")
    else:
        results["issues"].append("Falta .env.example")

    gitignore = project_dir / ".gitignore"
    if gitignore.exists() and ".env" in gitignore.read_text():
        results["passed"].append(".env en .gitignore")
    else:
        results["issues"].append(".env NO está en .gitignore")

    return results


def main():
    parser = argparse.ArgumentParser(description="Event Sourcing Architect")
    parser.add_argument("--dir", "-d", type=Path, default=".", help="Directorio")
    parser.add_argument("--check-docker", action="store_true")
    parser.add_argument("--check-ci", action="store_true")
    parser.add_argument("--check-env", action="store_true")
    parser.add_argument("--all", action="store_true")

    args = parser.parse_args()
    project_dir = args.dir.resolve()
    total_issues = 0

    print("=" * 50)
    print(f"DEVOPS CHECK: {project_dir}")
    print("=" * 50)

    if args.all or args.check_docker:
        print("\n[Docker]")
        r = check_docker(project_dir)
        for p in r["passed"]:
            print(f"  ✓ {p}")
        for i in r["issues"]:
            print(f"  ✗ {i}")
        total_issues += len(r["issues"])

    if args.all or args.check_ci:
        print("\n[CI/CD]")
        r = check_ci(project_dir)
        for p in r["passed"]:
            print(f"  ✓ {p}")
        for i in r["issues"]:
            print(f"  ✗ {i}")
        total_issues += len(r["issues"])

    if args.all or args.check_env:
        print("\n[Environment]")
        r = check_env(project_dir)
        for p in r["passed"]:
            print(f"  ✓ {p}")
        for i in r["issues"]:
            print(f"  ✗ {i}")
        total_issues += len(r["issues"])

    if not any([args.check_docker, args.check_ci, args.check_env, args.all]):
        parser.print_help()
        return

    print("\n" + "=" * 50)
    print(f"Total issues: {total_issues}")
    sys.exit(0 if total_issues == 0 else 1)


if __name__ == "__main__":
    main()
