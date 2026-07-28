#!/usr/bin/env python3
"""Crea un session node maestro para la corrida Matrix Absorb 2026-04-20."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / ".agent"))
from core.brain import Brain  # noqa: E402


def main() -> None:
    brain = Brain(REPO_ROOT / ".agent" / "brain", app_id="nexus-mother")

    context = (
        "Absorcion masiva de 37 apps locales del ecosistema UNS/Jpkken1979 "
        "al Brain Network como una descarga 'Matrix'. Cada app genero hasta 4 nodos "
        "(estructura + modelos + rutas + config) con tags canonicos segun "
        "docs/rules-reference/repo-crawler.md para cross-linking automatico.\n\n"
        "**Apps absorbidas (37)**: Kobetsuv2.26.4.1, Arari-PROv5.026.3.30, "
        "Arari-PROv2.0_Dokploy26.3.30, Chingiv7.026.3.30, KintaiFlow1.0v26.3.30, "
        "KintaiKyuryouv2.026.3.30, JpRirekiUltimate26.3.30, JpRireki-app1.0v26.3.30, "
        "JpRireki-Shain-unifi26.3.30, RirekishoDBaseAntigua26.3.30, CV-RIREKI-26.3.30, "
        "YukyuData-AppFusion2.1626.3.30, Kashitsuke-UNSv1.026.3.30, tiravisas-master26.3.30, "
        "UNS-System-JpNyushaTaisha26.3.30, Uns-Kintai-appJpX26.3.30, "
        "Opus4.6Apartementos26.3.30, opus46apartementos26.3.30, uns-apartment26.3.30, "
        "uns-kobetsu26.3.30, CodexBar-mainJp26.3.30, CodeXCATimerCard26.3.30, "
        "TimercardStudioIA26.3.30, OpenClaudeJp, Pdf-studio-Jp26.3.30, "
        "OpenShaken.v26.4.16, Paginaweb26.3.30, Paginaweb26.3.30test, "
        "Intro3D-UNS-Kikaku, Obsidian, BackUp-App-Jp202626.3.30, "
        "BorrarCarpetas26.3.30, autoriararpeta, RobotUns, JP-v1.26.3.25-30, "
        "JP-v26.3.30nousar, mcp-server."
    )

    decisions = (
        "- Script nuevo: .agent/scripts/local_matrix_absorb.py (no modifica master_plan_absorb.py).\n"
        "- Lectura desde filesystem local (no clone desde GitHub) para capturar cambios no pusheados.\n"
        "- SKIP_DIRS excluye node_modules, .git, target, dist, build, .next, venv, __pycache__.\n"
        "- Idempotente via hash SHA256 del contenido scaneado en source_notes.\n"
        "- Tags canonicos respetan repo-crawler.md (arari, kobetsu, rirekisho, kintai, yukyu, "
        "chingi, tiravisas, apartments, paginaweb, uns-dispatch).\n"
        "- Tag obligatorio: matrix-absorb-local + auto-ingested para distinguir de ingestas manuales.\n"
        "- 4 nodos por app: estructura (entity), modelos (concept), rutas (concept), config (session).\n"
        "- --skip-large 50000 (default) para absorber hasta apps gigantes como Paginaweb (15631 files)."
    )

    output = (
        "**Resultado**: 37 apps procesadas, 0 skipped, 136 nodos nuevos en el Brain.\n\n"
        "**Tech stack detectado** (top):\n"
        "- React + Vite: mayoria de apps UNS (Kobetsu, Arari, Kintai, Yukyu, Tiravisas, etc.)\n"
        "- Next.js + Prisma: JpRirekiUltimate (Staffing OS)\n"
        "- Tauri + Rust: BackUp-App-Jp, BorrarCarpetas (desktop apps)\n"
        "- Express: UNS-System-JpNyushaTaisha, Obsidian, JP-v26.3.30nousar\n"
        "- Docker/Dokploy: Arari-PROv2, OpenShaken, YukyuData\n"
        "- Python: mcp-server (portable MCP runtime)\n\n"
        "**Dominios**:\n"
        "- business (core UNS): 28 apps\n"
        "- dev (herramientas): 5 apps (CodexBar, OpenClaudeJp, Pdf-studio, etc.)\n"
        "- ux (web/marketing): 3 apps (Paginaweb x2, Intro3D)\n"
        "- ops (utilidades): 3 apps (BackUp, BorrarCarpetas, autoriararpeta)\n"
        "- docs (knowledge): 1 app (Obsidian vault)\n"
        "- infra: 1 app (mcp-server)\n\n"
        "**Cross-linking automatico**: Brain._detect_related() conecto los 136 nodos nuevos "
        "con los 977 existentes por tags solapados (arari, kobetsu, uns-dispatch, kintai, etc.).\n\n"
        "**Apps sin nodos de modelos/rutas** (proyectos pequenos o landings):\n"
        "- Intro3D-UNS-Kikaku (2 archivos, HTML + README)\n"
        "- RobotUns (3 archivos, experimental web)\n"
        "- mcp-server (9 archivos Python del portable MCP)\n"
        "- OpenShaken.v26.4.16 (125 archivos, pero estructura docker sin models/routes explicitos)"
    )

    pending = (
        "- OpenShaken tiene schemas en shakken-dokploy/public/pdf/ y src/ que un deep dive manual "
        "podria absorber con mas detalle (es app activa con commits recientes).\n"
        "- Intro3D + RobotUns: al ser mas codigo (aun no desarrollado) merecen re-scan cuando crezcan.\n"
        "- Considerar hook en /finalize para correr local_matrix_absorb.py cuando se agreguen apps nuevas.\n"
        '- Ejecutar `/brain query "mis apps"` para validar que el Brain responde con el mapa completo.'
    )

    brain.ingest(
        title="Matrix Absorb 2026-04-20 — 37 apps locales absorbidas al Brain",
        context=context,
        decisions=decisions,
        output=output,
        pending=pending,
        area="architecture",
        tags=[
            "matrix-absorb-local",
            "session",
            "brain",
            "uns-dispatch",
            "auto-ingested",
            "cross-app",
            "knowledge-ingest",
        ],
        node_type="session",
        importance="critical",
        source_notes="Ejecutado por .agent/scripts/local_matrix_absorb.py desde "
        "C:/Users/kenji/Github/Jpkken1979 — 37 apps, 136 nodos nuevos.",
    )

    brain.rebuild_index()
    print("Session node maestro creado + brain index rebuilt")


if __name__ == "__main__":
    main()
