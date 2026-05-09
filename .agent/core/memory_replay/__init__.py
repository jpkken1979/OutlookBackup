# mypy: ignore-errors
#!/usr/bin/env python3
"""
Memory Replay - Sistema de memoria de proyectos anteriores.

Permite que los agentes "recuerden" proyectos similares y aprendan
de decisiones pasadas, errores evitados, y patrones exitosos.

Uso:
    from .agent.core.memory_replay import MemoryReplay, ProjectMemory

    memory = MemoryReplay()

    # Guardar memoria de proyecto
    memory.remember_project(
        project_id="auth-system-v2",
        decisions=[...],
        patterns=[...],
        errors=[...]
    )

    # Recordar para proyecto similar
    relevant = await memory.recall(
        current_task="Implement OAuth authentication",
        top_k=5
    )
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("antigravity.core.memory_replay")


@dataclass
class Decision:
    """Una decision tomada en un proyecto."""

    id: str
    description: str
    alternatives_considered: list[str]
    chosen_option: str
    reasoning: str
    outcome: str  # "success", "partial", "failure"
    lessons_learned: list[str]
    tags: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Pattern:
    """Un patron exitoso identificado."""

    id: str
    name: str
    description: str
    context: str
    implementation: str
    benefits: list[str]
    applicable_when: list[str]
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ErrorRecord:
    """Un error cometido y como se resolvio."""

    id: str
    description: str
    root_cause: str
    symptoms: list[str]
    resolution: str
    prevention: str
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProjectMemory:
    """Memoria completa de un proyecto."""

    project_id: str
    project_name: str
    description: str
    tech_stack: list[str]
    decisions: list[Decision]
    patterns: list[Pattern]
    errors: list[ErrorRecord]
    agents_used: list[str]
    success_score: float  # 0-1
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "description": self.description,
            "tech_stack": self.tech_stack,
            "decisions": [d.to_dict() if hasattr(d, "to_dict") else d for d in self.decisions],
            "patterns": [p.to_dict() if hasattr(p, "to_dict") else p for p in self.patterns],
            "errors": [e.to_dict() if hasattr(e, "to_dict") else e for e in self.errors],
            "agents_used": self.agents_used,
            "success_score": self.success_score,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class RecallResult:
    """Resultado de una busqueda de memoria."""

    project_id: str
    relevance_score: float
    relevant_decisions: list[Decision]
    relevant_patterns: list[Pattern]
    relevant_errors: list[ErrorRecord]
    summary: str

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "relevance_score": self.relevance_score,
            "relevant_decisions": [d.to_dict() for d in self.relevant_decisions],
            "relevant_patterns": [p.to_dict() for p in self.relevant_patterns],
            "relevant_errors": [e.to_dict() for e in self.relevant_errors],
            "summary": self.summary,
        }


class MemoryReplay:
    """
    Sistema de memoria de proyectos para agentes.

    Almacena y recupera memorias de proyectos anteriores
    para ayudar en proyectos similares.
    """

    def __init__(self, storage_path: Path | None = None):
        self.storage_path = storage_path or Path.home() / ".antigravity" / "memory_replay"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.projects: dict[str, ProjectMemory] = {}
        self._load_all_projects()

    def _load_all_projects(self):
        """Cargar todos los proyectos almacenados."""
        for file in self.storage_path.glob("*.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                project = self._dict_to_project(data)
                self.projects[project.project_id] = project
            except Exception as e:
                logger.warning(f"No se pudo cargar {file}: {e}")

        logger.info(f"Cargados {len(self.projects)} proyectos de memoria")

    def _dict_to_project(self, data: dict) -> ProjectMemory:
        """Convertir dict a ProjectMemory."""
        return ProjectMemory(
            project_id=data["project_id"],
            project_name=data.get("project_name", data.get("name", "unnamed")),
            description=data.get("description", ""),
            tech_stack=data.get("tech_stack", []),
            decisions=[
                Decision(**d) if isinstance(d, dict) else d for d in data.get("decisions", [])
            ],
            patterns=[Pattern(**p) if isinstance(p, dict) else p for p in data.get("patterns", [])],
            errors=[ErrorRecord(**e) if isinstance(e, dict) else e for e in data.get("errors", [])],
            agents_used=data.get("agents_used", []),
            success_score=data.get("success_score", 0.5),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )

    def _save_project(self, project: ProjectMemory):
        """Guardar proyecto a disco."""
        file_path = self.storage_path / f"{project.project_id}.json"
        file_path.write_text(json.dumps(project.to_dict(), indent=2, ensure_ascii=False))

    def remember_project(
        self,
        project_id: str = None,
        project_name: str = "unnamed-project",
        description: str = "",
        tech_stack: list[str] = None,
        decisions: list[Decision] = None,
        patterns: list[Pattern] = None,
        errors: list[ErrorRecord] = None,
        agents_used: list[str] = None,
        success_score: float = 0.5,
    ) -> ProjectMemory:
        """
        Guardar memoria de un proyecto.

        Args:
            project_id: Identificador unico del proyecto (opcional, se genera si no se provee)
            project_name: Nombre legible
            description: Descripcion del proyecto
            tech_stack: Tecnologias usadas
            decisions: Decisiones tomadas
            patterns: Patrones identificados
            errors: Errores y resoluciones
            agents_used: Agentes que participaron
            success_score: Score de exito (0-1)

        Returns:
            ProjectMemory guardada
        """
        if not project_id:
            # Generar ID a partir del nombre y timestamp
            project_id = (
                f"{project_name.lower().replace(' ', '-')}-{int(datetime.now().timestamp())}"
            )

        project = ProjectMemory(
            project_id=project_id,
            project_name=project_name,
            description=description,
            tech_stack=tech_stack or [],
            decisions=decisions or [],
            patterns=patterns or [],
            errors=errors or [],
            agents_used=agents_used or [],
            success_score=success_score,
        )

        self.projects[project_id] = project
        self._save_project(project)

        logger.info(f"Proyecto {project_id} guardado en memoria")

        return project

    def _find_project_id(self, project_id: str = None, project_name: str = None) -> str | None:
        """Encontrar project_id por ID o nombre."""
        if project_id:
            if project_id in self.projects:
                return project_id
            # Probar si project_id es en realidad un project_name
            for p in self.projects.values():
                if p.project_name == project_id:
                    return p.project_id

        if project_name:
            # Busqueda exacta
            for p in self.projects.values():
                if p.project_name == project_name:
                    return p.project_id

            # Busqueda insensible a mayusculas/espacios
            norm_name = project_name.lower().strip()
            for p in self.projects.values():
                if p.project_name.lower().strip() == norm_name:
                    return p.project_id

        return None

    def add_decision(self, project_id: str = None, decision: Decision = None, **kwargs):
        """Agregar decision a un proyecto existente."""
        target_id = self._find_project_id(project_id, kwargs.get("project_name"))

        if not target_id or target_id not in self.projects:
            raise ValueError(f"Proyecto {target_id or project_id} no encontrado")

        if decision is None:
            # Crear decision de kwargs
            decision = Decision(
                id=f"dec-{int(datetime.now().timestamp())}",
                description=kwargs.get("description", kwargs.get("decision", "")),
                alternatives_considered=kwargs.get("alternatives_considered", []),
                chosen_option=kwargs.get("chosen_option", ""),
                reasoning=kwargs.get("reasoning", kwargs.get("rationale", "")),
                outcome=kwargs.get("outcome", "success"),
                lessons_learned=kwargs.get("lessons_learned", []),
                tags=kwargs.get("tags", []),
            )

        self.projects[target_id].decisions.append(decision)
        self.projects[target_id].updated_at = datetime.now().isoformat()
        self._save_project(self.projects[target_id])

    def get_decisions(self, project_id: str = None, project_name: str = None) -> list[Decision]:
        """Obtener decisiones de un proyecto."""
        target_id = self._find_project_id(project_id, project_name)

        if target_id and target_id in self.projects:
            return self.projects[target_id].decisions
        return []

    def add_pattern(self, project_id: str = None, pattern: Pattern = None, **kwargs):
        """Agregar patron a un proyecto existente."""
        target_id = self._find_project_id(project_id, kwargs.get("project_name"))

        if not target_id:
            raise ValueError("Proyecto no encontrado")

        if pattern is None:
            pattern = Pattern(
                id=f"pat-{int(datetime.now().timestamp())}",
                name=kwargs.get("name", ""),
                description=kwargs.get("description", ""),
                context=kwargs.get("context", ""),
                implementation=kwargs.get("implementation", ""),
                benefits=kwargs.get("benefits", []),
                applicable_when=kwargs.get("applicable_when", []),
                tags=kwargs.get("tags", []),
            )

        self.projects[target_id].patterns.append(pattern)
        self.projects[target_id].updated_at = datetime.now().isoformat()
        self._save_project(self.projects[target_id])

    def get_patterns(self, project_id: str = None, project_name: str = None) -> list[Pattern]:
        """Obtener patrones de un proyecto."""
        target_id = self._find_project_id(project_id, project_name)

        if target_id and target_id in self.projects:
            return self.projects[target_id].patterns
        return []

    def add_error(self, project_id: str, error: ErrorRecord):
        """Agregar error a un proyecto existente."""
        if project_id not in self.projects:
            raise ValueError(f"Proyecto {project_id} no encontrado")

        self.projects[project_id].errors.append(error)
        self.projects[project_id].updated_at = datetime.now().isoformat()
        self._save_project(self.projects[project_id])

    def recall(
        self, current_task: str, tech_stack: list[str] = None, top_k: int = 5
    ) -> list[RecallResult]:
        """
        Recordar proyectos relevantes para la tarea actual.

        Args:
            current_task: Descripcion de la tarea actual
            tech_stack: Tecnologias del proyecto actual
            top_k: Numero de proyectos a retornar

        Returns:
            Lista de RecallResult ordenados por relevancia
        """
        results = []
        task_lower = current_task.lower()
        task_keywords = set(task_lower.split())

        for project in self.projects.values():
            # Calcular relevancia
            relevance = self._calculate_relevance(task_keywords, tech_stack or [], project)

            if relevance > 0.1:
                # Filtrar items relevantes
                relevant_decisions = [
                    d
                    for d in project.decisions
                    if any(kw in d.description.lower() for kw in task_keywords)
                ][:3]

                relevant_patterns = [
                    p
                    for p in project.patterns
                    if any(
                        kw in p.description.lower() or kw in p.name.lower() for kw in task_keywords
                    )
                ][:3]

                relevant_errors = [
                    e
                    for e in project.errors
                    if any(kw in e.description.lower() for kw in task_keywords)
                ][:3]

                # Generar resumen
                summary = self._generate_summary(
                    project, relevant_decisions, relevant_patterns, relevant_errors
                )

                results.append(
                    RecallResult(
                        project_id=project.project_id,
                        relevance_score=relevance,
                        relevant_decisions=relevant_decisions,
                        relevant_patterns=relevant_patterns,
                        relevant_errors=relevant_errors,
                        summary=summary,
                    )
                )

        # Ordenar por relevancia
        results.sort(key=lambda x: x.relevance_score, reverse=True)

        return results[:top_k]

    def _calculate_relevance(
        self, task_keywords: set, current_stack: list[str], project: ProjectMemory
    ) -> float:
        """Calcular relevancia de un proyecto con scoring ponderado multi-factor.

        Factores:
        - Keyword overlap con descripcion y nombres de patrones/errores (0.25)
        - Tech stack match (0.20)
        - Success score historico (0.20)
        - Recencia temporal (0.15)
        - Densidad de conocimiento: decisiones+patrones+errores (0.10)
        - Agent overlap con agentes del ecosistema (0.10)
        """
        score = 0.0

        # Factor 1: Keyword overlap (0-0.25)
        desc_keywords = set(project.description.lower().split())
        # Tambien buscar en nombres de patrones y descripciones de errores
        pattern_keywords: set[str] = set()
        for p in project.patterns:
            pattern_keywords.update(p.name.lower().split())
            pattern_keywords.update(p.description.lower().split())
        for e in project.errors:
            pattern_keywords.update(e.description.lower().split())

        all_project_keywords = desc_keywords | pattern_keywords
        keyword_overlap = len(task_keywords & all_project_keywords)
        keyword_score = min(1.0, keyword_overlap / max(len(task_keywords), 1))
        score += keyword_score * 0.25

        # Factor 2: Tech stack match (0-0.20)
        if current_stack:
            current_set = {s.lower() for s in current_stack}
            project_set = {s.lower() for s in project.tech_stack}
            stack_overlap = len(current_set & project_set)
            stack_score = min(1.0, stack_overlap / max(len(current_set), 1))
            score += stack_score * 0.20

        # Factor 3: Success score (0-0.20)
        score += project.success_score * 0.20

        # Factor 4: Recencia temporal (0-0.15)
        try:
            updated = datetime.fromisoformat(project.updated_at)
            days_ago = (datetime.now() - updated).days
            if days_ago < 7:
                score += 0.15
            elif days_ago < 30:
                score += 0.10
            elif days_ago < 90:
                score += 0.05
        except (ValueError, TypeError):
            pass

        # Factor 5: Densidad de conocimiento (0-0.10)
        knowledge_count = len(project.decisions) + len(project.patterns) + len(project.errors)
        knowledge_score = min(1.0, knowledge_count / 10.0)
        score += knowledge_score * 0.10

        # Factor 6: Agent overlap (0-0.10)
        if project.agents_used:
            score += min(0.10, len(project.agents_used) * 0.02)

        return min(score, 1.0)

    def _generate_summary(
        self,
        project: ProjectMemory,
        decisions: list[Decision],
        patterns: list[Pattern],
        errors: list[ErrorRecord],
    ) -> str:
        """Generar resumen de memoria relevante."""
        parts = [f"Del proyecto '{project.project_name}':"]

        if decisions:
            parts.append(f"- {len(decisions)} decisiones relevantes")

        if patterns:
            parts.append(f"- {len(patterns)} patrones aplicables")

        if errors:
            parts.append(f"- {len(errors)} errores a evitar")

        if project.success_score > 0.7:
            parts.append(f"- Proyecto exitoso (score: {project.success_score:.0%})")

        return " ".join(parts)

    def list_projects(self) -> list[dict]:
        """Listar todos los proyectos en memoria."""
        return [
            {
                "project_id": p.project_id,
                "project_name": p.project_name,
                "name": p.project_name,  # Compatibilidad con tests
                "tech_stack": p.tech_stack,
                "decisions_count": len(p.decisions),
                "patterns_count": len(p.patterns),
                "errors_count": len(p.errors),
                "success_score": p.success_score,
            }
            for p in self.projects.values()
        ]

    def get_project(self, project_id: str) -> ProjectMemory | None:
        """Obtener proyecto por ID."""
        return self.projects.get(project_id)

    def delete_project(self, project_id: str) -> bool:
        """Eliminar proyecto de memoria."""
        if project_id in self.projects:
            del self.projects[project_id]
            file_path = self.storage_path / f"{project_id}.json"
            if file_path.exists():
                file_path.unlink()
            return True
        return False


# Singleton
_memory: MemoryReplay | None = None


def get_memory_replay() -> MemoryReplay:
    """Obtener instancia de MemoryReplay."""
    global _memory
    if _memory is None:
        _memory = MemoryReplay()
    return _memory
