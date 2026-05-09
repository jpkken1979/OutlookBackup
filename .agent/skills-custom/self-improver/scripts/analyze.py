#!/usr/bin/env python3
"""
Self-Improver: Analisis avanzado de gaps en capacidades.
Detecta gaps basandose en el contexto real del proyecto y patrones de conversacion.
"""

import argparse
import json
import re
import sys
import io
from pathlib import Path
from typing import Any
from datetime import datetime
from collections import Counter

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

AGENT_ROOT = Path(__file__).parent.parent.parent.parent.parent  # repo root
sys.path.insert(0, str(AGENT_ROOT / ".agent"))

SKILLS_DIR = AGENT_ROOT / ".agent" / "skills-custom"
SKILLS_BASE = AGENT_ROOT / ".agent" / "skills"


def get_project_context() -> dict[str, Any]:
    """Analiza el contexto real del proyecto."""
    context = {
        "languages": [],
        "frameworks": [],
        "domains": [],
        "stack": [],
        "file_counts": Counter(),
    }

    # Detectar stacks por archivos en la raiz
    root_dirs = [d.name for d in AGENT_ROOT.glob("*") if d.is_dir() and not d.name.startswith(".")]
    context["domains"].extend(root_dirs)

    # Contar archivos por extension
    ext_counts = Counter()
    for ext in [".py", ".ts", ".tsx", ".rs", ".md", ".json", ".sh"]:
        ext_counts[ext] = len(list(AGENT_ROOT.rglob(f"*{ext}")))

    # Detectar lenguajes dominantes (>50 archivos)
    lang_map = {".py": "Python", ".ts": "TypeScript", ".tsx": "React", ".rs": "Rust", ".md": "Docs"}
    for ext, lang in lang_map.items():
        if ext_counts[ext] > 50:
            context["languages"].append(lang)
            context["stack"].append(lang)
        context["file_counts"][lang] = ext_counts[ext]

    # Detectar frameworks por archivos clave
    if (AGENT_ROOT / "nexus-app").exists():
        context["frameworks"].append("Tauri")
        context["frameworks"].append("React")
        context["stack"].append("Tauri")
    if (AGENT_ROOT / "src").exists() and (AGENT_ROOT / "src" / "index.ts").exists():
        context["frameworks"].append("grammY")
        context["frameworks"].append("Telegram Bot")
    if (AGENT_ROOT / "core").exists():
        context["frameworks"].append("MCP")
        context["stack"].append("MCP")

    # Dominios de negocio (carpetas relevantes)
    business_domains = []
    if any(f.name.startswith("kintai") or "kintai" in f.name.lower() for f in AGENT_ROOT.glob("*")):
        business_domains.append("kintai")
    if any("kobetsu" in f.name.lower() for f in AGENT_ROOT.glob("*")):
        business_domains.append("kobetsu")
    if any("arari" in f.name.lower() for f in AGENT_ROOT.glob("*")):
        business_domains.append("arari")
    context["domains"].extend(business_domains)

    return context


def load_skills() -> dict[str, dict[str, Any]]:
    """Carga todos los skills disponibles."""
    skills: dict[str, dict[str, Any]] = {}

    for skills_dir in [SKILLS_DIR, SKILLS_BASE]:
        if not skills_dir.exists():
            continue
        # Skip self and deprecated
        for skill_path in skills_dir.rglob("SKILL.md"):
            skill_name = skill_path.parent.name
            if skill_name.startswith("_") or skill_name == "self-improver":
                continue
            try:
                content = skill_path.read_text(encoding="utf-8")
                metadata = extract_frontmatter(content)
                tags = metadata.get("tags") or []
                if isinstance(tags, str):
                    tags = [tags]
                tags = [t for t in tags if isinstance(t, str)]
                skills[skill_name] = {
                    "path": str(skill_path),
                    "name": metadata.get("name", skill_name),
                    "description": metadata.get("description", ""),
                    "tags": tags,
                    "category": metadata.get("category", "general"),
                }
            except Exception:
                pass

    return skills


def extract_frontmatter(content: str) -> dict[str, Any]:
    """Extrae el frontmatter YAML de un markdown."""
    import yaml
    metadata: dict[str, Any] = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                metadata = yaml.safe_load(parts[1]) or {}
            except Exception:
                pass
    return metadata


def analyze_coverage(skills: dict[str, dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
    """Analiza el coverage de capacidades vs contexto del proyecto."""
    # Recolectar todos los tags cubiertos
    covered_tags: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()

    for skill in skills.values():
        for tag in (skill.get("tags") or []):
            covered_tags[tag.lower()] += 1
        cat = skill.get("category", "general")
        category_counts[cat] += 1

    # Areas que el proyecto necesita basandose en contexto
    needed_areas = []
    for lang in context.get("languages", []):
        needed_areas.append(("language", lang.lower(), f"Skills para {lang}"))
    for fw in context.get("frameworks", []):
        needed_areas.append(("framework", fw.lower(), f"Skills para {fw}"))
    for domain in context.get("domains", []):
        needed_areas.append(("domain", domain.lower(), f"Skills para {domain}"))

    # Detectar gaps
    gaps = []
    covered_lower = {t.lower() for t in covered_tags.keys()}

    for area_type, area_name, suggestion in needed_areas:
        # Buscar si hay skills que cubren esta area
        related_skills = []
        for skill_name, skill in skills.items():
            skill_tags = [t.lower() for t in skill.get("tags", [])]
            if area_name in skill_tags or any(area_name in t for t in skill_tags):
                related_skills.append(skill_name)

        if not related_skills:
            gaps.append({
                "type": area_type,
                "area": area_name,
                "coverage": 0,
                "status": "MISSING",
                "suggestion": suggestion,
                "skills_needed": 1,
            })
        elif len(related_skills) < 2:
            gaps.append({
                "type": area_type,
                "area": area_name,
                "coverage": len(related_skills),
                "status": "WEAK",
                "suggestion": f"Solo {len(related_skills)} skill(s) para {area_name}",
                "skills_needed": 3 - len(related_skills),
                "existing": related_skills[:2],
            })

    # Calcular coverage score
    total_needed = len(needed_areas) if needed_areas else 1
    covered_count = sum(1 for g in gaps if g["status"] != "MISSING")
    coverage_score = int((covered_count / total_needed) * 100) if total_needed > 0 else 100

    return {
        "total_skills": len(skills),
        "total_tags": len(covered_tags),
        "needed_areas": len(needed_areas),
        "categories": dict(category_counts.most_common(10)),
        "top_tags": dict(covered_tags.most_common(15)),
        "gaps": gaps,
        "coverage_score": coverage_score,
    }


def get_conversation_history() -> list[dict[str, Any]]:
    """Intenta cargar el historial de conversacion reciente."""
    history = []

    # Buscar transcripts recientes
    search_paths = [
        AGENT_ROOT / ".claude" / "memory",
        Path.home() / ".claude" / "projects",
    ]

    for base in search_paths:
        if base.exists():
            for transcript in base.rglob("*.jsonl"):
                try:
                    import time
                    mtime = transcript.stat().st_mtime
                    age_hours = (time.time() - mtime) / 3600
                    if age_hours < 24:
                        content = transcript.read_text(encoding="utf-8", errors="ignore")
                        for line in content.strip().split("\n"):
                            if line:
                                try:
                                    history.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass
                except Exception:
                    pass

    return history[-50:]


def detect_conversation_gaps(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detecta gaps en patrones de conversacion."""
    need_patterns = [
        (r"no tengo|falta|no existe|no hay", "MISSING"),
        (r"automatiz[ae]|hace[rr] esto solo", "AUTOMATION"),
        (r"mejorar|optimizar|refactorizar", "REFACTOR"),
        (r"test|prob[ae]r|coverage", "TESTING"),
    ]

    gaps = []
    seen_types = set()
    for msg in history:
        content = str(msg.get("content", "")).lower()
        for pattern, gap_type in need_patterns:
            if re.search(pattern, content) and gap_type not in seen_types:
                gaps.append({
                    "type": gap_type,
                    "priority": "high" if gap_type in ["MISSING", "AUTOMATION"] else "medium",
                })
                seen_types.add(gap_type)

    return gaps


def generate_recommendations(coverage: dict[str, Any], conv_gaps: list[dict[str, Any]]) -> list[str]:
    """Genera recomendaciones accionables."""
    recs = []

    # Basado en coverage
    score = coverage.get("coverage_score", 100)
    if score < 50:
        recs.append(f"[CRITICAL] Coverage bajo: {score}% - faltan {len(coverage.get('gaps', []))} areas")
    elif score < 80:
        recs.append(f"[MEDIUM] Coverage: {score}% - mejorar {len(coverage.get('gaps', []))} areas")

    # Basado en gaps
    missing = [g for g in coverage.get("gaps", []) if g["status"] == "MISSING"]
    weak = [g for g in coverage.get("gaps", []) if g["status"] == "WEAK"]

    if missing:
        recs.append(f"[HIGH] {len(missing)} areas sin cobertura: {', '.join(g['area'] for g in missing[:3])}")
    if weak:
        recs.append(f"[MEDIUM] {len(weak)} areas debiles: {', '.join(g['area'] for g in weak[:3])}")

    # Basado en conversacion
    gap_types = {g["type"] for g in conv_gaps}
    if "AUTOMATION" in gap_types:
        recs.append("[HIGH] Automatizar tareas repetitivas de conversacion")
    if "TESTING" in gap_types:
        recs.append("[MEDIUM] Mejorar capacidades de testing")

    if not recs:
        recs.append("[OK] Cobertura adecuada para el contexto actual")

    return recs


def analyze_gaps(verbose: bool = True) -> dict[str, Any]:
    """Ejecuta el analisis completo de gaps."""
    if verbose:
        print("[1/4] Analizando contexto del proyecto...")
    context = get_project_context()

    if verbose:
        print("[2/4] Cargando skills disponibles...")
    skills = load_skills()

    if verbose:
        print("[3/4] Calculando coverage...")
    coverage = analyze_coverage(skills, context)

    if verbose:
        print("[4/4] Detectando gaps en conversacion...")
    history = get_conversation_history()
    conv_gaps = detect_conversation_gaps(history)

    recommendations = generate_recommendations(coverage, conv_gaps)

    return {
        "timestamp": datetime.now().isoformat(),
        "context": context,
        "coverage": coverage,
        "gaps_detected": len(coverage.get("gaps", [])),
        "conversation_gaps": conv_gaps,
        "recommendations": recommendations,
    }


def print_report(result: dict[str, Any], verbose: bool = False):
    """Imprime el reporte de analisis."""
    print("\n" + "=" * 60)
    print("SELF-IMPROVER: ANALISIS DE CAPACIDADES")
    print("=" * 60)

    ctx = result.get("context", {})
    cov = result.get("coverage", {})

    print("\n[CONTEXTO DEL PROYECTO]")
    print(f"  Lenguajes: {', '.join(ctx.get('languages', []) or ['No detectados'])}")
    print(f"  Frameworks: {', '.join(ctx.get('frameworks', []) or ['No detectados'])}")
    print(f"  Dominios: {', '.join(ctx.get('domains', [])[:5] or ['No detectados'])}")

    print("\n[COVERAGE]")
    print(f"  Skills cargados: {cov.get('total_skills', 0)}")
    print(f"  Tags unicos: {cov.get('total_tags', 0)}")
    print(f"  Areas necesarias: {cov.get('needed_areas', 0)}")
    print(f"  Coverage score: {cov.get('coverage_score', 0)}%")

    if verbose:
        print("\n  [TOP TAGS]")
        for tag, count in list(cov.get("top_tags", {}).items())[:8]:
            print(f"    {tag}: {count}")
        print("\n  [CATEGORIAS]")
        for cat, count in list(cov.get("categories", {}).items())[:5]:
            print(f"    {cat}: {count}")

    print("\n[GAPS]")
    gaps = cov.get("gaps", [])
    missing = [g for g in gaps if g["status"] == "MISSING"]
    weak = [g for g in gaps if g["status"] == "WEAK"]

    if missing:
        print(f"  [MISSING] ({len(missing)} areas sin skills)")
        for g in missing[:5]:
            print(f"    - {g['area']}: {g['suggestion']}")
    else:
        print("  [OK] Todas las areas tienen coverage")

    if weak:
        print(f"\n  [WEAK] ({len(weak)} areas con coverage limitado)")
        for g in weak[:3]:
            print(f"    - {g['area']}: {g['coverage']} skill(s) - {g.get('existing', [])[:1]}")

    if result.get("conversation_gaps"):
        print("\n[GAPS DE CONVERSACION]")
        for g in result["conversation_gaps"][:3]:
            print(f"  [{g['priority'].upper()}] {g['type']}")

    print("\n[RECOMENDACIONES]")
    for rec in result.get("recommendations", []):
        print(f"  {rec}")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Analisis de gaps de capacidades")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Modo detallado")
    parser.add_argument("--brain", action="store_true", help="Ingestar al Brain")
    parser.add_argument("--auto", action="store_true", help="Generar skills automaticamente")

    args = parser.parse_args()

    # Si es --json, silenciar logs de progreso
    verbose = not args.json
    result = analyze_gaps(verbose=verbose)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_report(result, verbose=args.verbose)

    if args.brain:
        try:
            from core.brain import Brain
            brain = Brain(AGENT_ROOT / ".agent" / "brain", app_id="nexus-mother")
            brain.ingest(
                title=f"Self-Improver Analysis {datetime.now().strftime('%Y-%m-%d')}",
                context=json.dumps(result, ensure_ascii=False),
                area="intelligence",
                tags=["self-improvement", "coverage", "analysis"],
                node_type="pattern",
                importance="high",
            )
            print("\n[OK] Ingestado al Brain")
        except Exception as e:
            print(f"\n[WARNING] No se pudo ingestar al Brain: {e}")

    if args.auto:
        from generate import generate_skill, update_registry
        gaps = result.get("coverage", {}).get("gaps", [])
        for gap in gaps[:3]:
            if gap["status"] == "MISSING":
                skill_result = generate_skill(
                    skill_name=f"auto-{gap['area']}",
                    description=f"Skill auto-generado para el area: {gap['area']}",
                    gap=gap["suggestion"],
                    triggers=[gap["area"], "auto-generated"],
                    use_cases=[gap["suggestion"], "Caso generico"],
                    steps=["Recibir input", "Procesar", "Retornar resultado"],
                )
                update_registry(skill_result)
                print(f"[OK] Generado: {skill_result['skill_name']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
