#!/usr/bin/env python3
"""
Regression Detector Agent - Detecta regresiones de código automáticamente
"""

import re
import json
import subprocess
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FileChange:
    """Representa un cambio en un archivo"""

    path: str
    change_type: str  # added, modified, deleted, renamed
    additions: int = 0
    deletions: int = 0
    functions_changed: list[str] = field(default_factory=list)
    classes_changed: list[str] = field(default_factory=list)


@dataclass
class Dependency:
    """Dependencia entre archivos/funciones"""

    source: str
    target: str
    dependency_type: str  # import, call, inheritance
    strength: float = 1.0  # 0-1


@dataclass
class RegressionRisk:
    """Evaluación de riesgo de regresión"""

    level: str  # low, medium, high, critical
    score: float  # 0-100
    affected_files: list[str]
    affected_functions: list[str]
    reasons: list[str]
    recommendations: list[str]


@dataclass
class RegressionReport:
    """Reporte completo de análisis de regresión"""

    timestamp: str
    changes_analyzed: int
    total_risk_score: float
    risks: list[RegressionRisk]
    dependency_graph: dict[str, list[str]]
    test_suggestions: list[str]
    summary: str


class RegressionDetector:
    """Detector de regresiones de código"""

    # Patrones de código de alto riesgo
    HIGH_RISK_PATTERNS = [
        (r"def\s+__init__", "constructor", "high"),
        (r"class\s+\w+.*Exception", "exception", "high"),
        (r"@property", "property", "medium"),
        (r"async\s+def", "async_function", "medium"),
        (r"global\s+\w+", "global_var", "high"),
        (r"eval\s*\(", "eval", "critical"),
        (r"exec\s*\(", "exec", "critical"),
        (r"subprocess", "subprocess", "high"),
        (r"os\.(remove|unlink|rmdir)", "file_deletion", "critical"),
        (r"\.connect\(", "db_connection", "high"),
        (r"password|secret|token|key", "sensitive", "high"),
    ]

    # Archivos de alto riesgo
    HIGH_RISK_PATHS = [
        "auth",
        "security",
        "payment",
        "database",
        "db",
        "config",
        "settings",
        "core",
        "base",
        "main",
        "__init__",
        "migrations",
        "models",
    ]

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(".")
        self.dependency_cache: dict[str, set[str]] = {}
        self.baseline_file = self.project_root / ".agent" / "regression_baseline.json"

    def get_git_changes(
        self, base_ref: str = "HEAD~1", target_ref: str = "HEAD"
    ) -> list[FileChange]:
        """Obtener cambios de git"""
        changes = []

        try:
            # Obtener lista de archivos cambiados
            result = subprocess.run(
                ["git", "diff", "--name-status", base_ref, target_ref],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            if result.returncode != 0:
                return changes

            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                parts = line.split("\t")
                status = parts[0][0]
                path = parts[-1]

                change_type = {"A": "added", "M": "modified", "D": "deleted", "R": "renamed"}.get(
                    status, "modified"
                )

                change = FileChange(path=path, change_type=change_type)

                # Obtener estadísticas
                stat_result = subprocess.run(
                    ["git", "diff", "--numstat", base_ref, target_ref, "--", path],
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                )

                if stat_result.stdout.strip():
                    stat_parts = stat_result.stdout.strip().split("\t")
                    if len(stat_parts) >= 2:
                        try:
                            change.additions = int(stat_parts[0]) if stat_parts[0] != "-" else 0
                            change.deletions = int(stat_parts[1]) if stat_parts[1] != "-" else 0
                        except ValueError:
                            pass

                # Analizar funciones/clases cambiadas
                if path.endswith(".py") and change_type in ["modified", "added"]:
                    change.functions_changed, change.classes_changed = self._analyze_changed_code(
                        base_ref, target_ref, path
                    )

                changes.append(change)

        except Exception as e:
            print(f"Error getting git changes: {e}")

        return changes

    def _analyze_changed_code(
        self, base_ref: str, target_ref: str, path: str
    ) -> tuple[list[str], list[str]]:
        """Analizar qué funciones y clases cambiaron"""
        functions = []
        classes = []

        try:
            result = subprocess.run(
                ["git", "diff", "-U0", base_ref, target_ref, "--", path],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            diff = result.stdout

            # Buscar funciones cambiadas
            func_pattern = r"@@.*@@.*def\s+(\w+)"
            for match in re.finditer(func_pattern, diff):
                functions.append(match.group(1))

            # Buscar clases cambiadas
            class_pattern = r"@@.*@@.*class\s+(\w+)"
            for match in re.finditer(class_pattern, diff):
                classes.append(match.group(1))

            # También buscar en las líneas añadidas/eliminadas
            for line in diff.split("\n"):
                if line.startswith("+") or line.startswith("-"):
                    if "def " in line:
                        match = re.search(r"def\s+(\w+)", line)
                        if match and match.group(1) not in functions:
                            functions.append(match.group(1))
                    if "class " in line:
                        match = re.search(r"class\s+(\w+)", line)
                        if match and match.group(1) not in classes:
                            classes.append(match.group(1))

        except Exception:
            pass

        return list(set(functions)), list(set(classes))

    def find_dependencies(self, file_path: str) -> list[Dependency]:
        """Encontrar dependencias de un archivo"""
        dependencies = []
        full_path = self.project_root / file_path

        if not full_path.exists() or not file_path.endswith(".py"):
            return dependencies

        try:
            content = full_path.read_text()

            # Buscar imports
            import_patterns = [r"^import\s+([\w.]+)", r"^from\s+([\w.]+)\s+import"]

            for pattern in import_patterns:
                for match in re.finditer(pattern, content, re.MULTILINE):
                    module = match.group(1)
                    dependencies.append(
                        Dependency(source=file_path, target=module, dependency_type="import")
                    )

            # Buscar llamadas a funciones de otros módulos
            call_pattern = r"(\w+)\.(\w+)\s*\("
            for match in re.finditer(call_pattern, content):
                obj, method = match.groups()
                if obj[0].islower():  # Probablemente un módulo
                    dependencies.append(
                        Dependency(
                            source=file_path,
                            target=f"{obj}.{method}",
                            dependency_type="call",
                            strength=0.7,
                        )
                    )

            # Buscar herencia
            class_pattern = r"class\s+\w+\s*\(([^)]+)\)"
            for match in re.finditer(class_pattern, content):
                bases = match.group(1).split(",")
                for base in bases:
                    base = base.strip()
                    if base and base not in ("object", "ABC"):
                        dependencies.append(
                            Dependency(
                                source=file_path,
                                target=base,
                                dependency_type="inheritance",
                                strength=1.0,
                            )
                        )

        except Exception:
            pass

        return dependencies

    def find_reverse_dependencies(self, file_path: str) -> list[str]:
        """Encontrar archivos que dependen del archivo dado"""
        dependents = []
        module_name = file_path.replace("/", ".").replace(".py", "")

        # Buscar en todos los archivos Python
        for py_file in self.project_root.rglob("*.py"):
            if py_file.is_file():
                try:
                    content = py_file.read_text()
                    rel_path = py_file.relative_to(self.project_root)

                    # Verificar si importa el módulo
                    if module_name in content or file_path in content:
                        if str(rel_path) != file_path:
                            dependents.append(str(rel_path))
                except Exception:
                    pass

        return dependents[:50]  # Limitar para performance

    def calculate_risk(self, changes: list[FileChange]) -> RegressionRisk:
        """Calcular riesgo de regresión para un conjunto de cambios"""
        score = 0.0
        affected_files = []
        affected_functions = []
        reasons = []
        recommendations = []

        for change in changes:
            file_score = 0.0

            # Factor 1: Tipo de cambio
            if change.change_type == "deleted":
                file_score += 30
                reasons.append(f"Archivo eliminado: {change.path}")
            elif change.change_type == "added":
                file_score += 10
            else:  # modified
                file_score += 20

            # Factor 2: Cantidad de cambios
            total_changes = change.additions + change.deletions
            if total_changes > 100:
                file_score += 20
                reasons.append(f"Muchos cambios en {change.path} ({total_changes} líneas)")
            elif total_changes > 50:
                file_score += 10

            # Factor 3: Ruta de alto riesgo
            for risk_path in self.HIGH_RISK_PATHS:
                if risk_path in change.path.lower():
                    file_score += 15
                    reasons.append(f"Archivo en ruta crítica: {change.path}")
                    break

            # Factor 4: Patrones de alto riesgo en el código
            if change.change_type != "deleted":
                full_path = self.project_root / change.path
                if full_path.exists():
                    try:
                        content = full_path.read_text()
                        for pattern, name, risk_level in self.HIGH_RISK_PATTERNS:
                            if re.search(pattern, content, re.IGNORECASE):
                                if risk_level == "critical":
                                    file_score += 25
                                elif risk_level == "high":
                                    file_score += 15
                                else:
                                    file_score += 8
                                reasons.append(f"Patrón de riesgo '{name}' en {change.path}")
                    except Exception:
                        pass

            # Factor 5: Dependencias afectadas
            dependents = self.find_reverse_dependencies(change.path)
            if len(dependents) > 5:
                file_score += 20
                reasons.append(f"{len(dependents)} archivos dependen de {change.path}")
                affected_files.extend(dependents[:10])

            # Factor 6: Funciones críticas modificadas
            for func in change.functions_changed:
                affected_functions.append(f"{change.path}:{func}")
                if func in ["__init__", "__del__", "setup", "teardown", "main"]:
                    file_score += 10
                    reasons.append(f"Función crítica modificada: {func}")

            score += file_score
            affected_files.append(change.path)

        # Normalizar score
        score = min(100, score)

        # Determinar nivel
        if score >= 70:
            level = "critical"
            recommendations.append("⚠️ REQUIERE revisión exhaustiva antes de merge")
            recommendations.append("Ejecutar suite de tests completa")
            recommendations.append("Considerar feature flag para rollback rápido")
        elif score >= 50:
            level = "high"
            recommendations.append("Ejecutar tests de regresión focalizados")
            recommendations.append("Revisar con otro desarrollador")
        elif score >= 25:
            level = "medium"
            recommendations.append("Ejecutar tests unitarios relacionados")
            recommendations.append("Verificar comportamiento en staging")
        else:
            level = "low"
            recommendations.append("Cambios de bajo riesgo, verificación estándar")

        return RegressionRisk(
            level=level,
            score=round(score, 1),
            affected_files=list(set(affected_files)),
            affected_functions=affected_functions,
            reasons=reasons,
            recommendations=recommendations,
        )

    def generate_test_suggestions(self, changes: list[FileChange]) -> list[str]:
        """Generar sugerencias de tests basados en cambios"""
        suggestions = []

        for change in changes:
            if change.change_type == "deleted":
                suggestions.append(f"Verificar que nada dependa de {change.path}")
                continue

            # Sugerir tests para funciones modificadas
            for func in change.functions_changed:
                suggestions.append(f"Test unitario para {change.path}:{func}()")

            # Sugerir tests para clases modificadas
            for cls in change.classes_changed:
                suggestions.append(f"Test de integración para clase {cls} en {change.path}")

            # Tests específicos por tipo de archivo
            if "api" in change.path.lower() or "endpoint" in change.path.lower():
                suggestions.append(f"Test de API endpoint para {change.path}")

            if "model" in change.path.lower():
                suggestions.append(f"Test de modelo y migraciones para {change.path}")

            if "auth" in change.path.lower():
                suggestions.append(f"Test de autenticación/autorización para {change.path}")

        return list(set(suggestions))

    def analyze(
        self, base_ref: str = "HEAD~1", target_ref: str = "HEAD", file_path: str | None = None
    ) -> RegressionReport:
        """Realizar análisis completo de regresión"""

        if file_path:
            # Analizar archivo específico
            changes = [
                FileChange(
                    path=file_path,
                    change_type="modified",
                    functions_changed=self._get_all_functions(file_path),
                    classes_changed=self._get_all_classes(file_path),
                )
            ]
        else:
            # Analizar cambios de git
            changes = self.get_git_changes(base_ref, target_ref)

        if not changes:
            return RegressionReport(
                timestamp=datetime.now().isoformat(),
                changes_analyzed=0,
                total_risk_score=0,
                risks=[],
                dependency_graph={},
                test_suggestions=[],
                summary="No hay cambios para analizar",
            )

        # Calcular riesgo
        risk = self.calculate_risk(changes)

        # Construir grafo de dependencias
        dep_graph = {}
        for change in changes:
            deps = self.find_dependencies(change.path)
            dep_graph[change.path] = [d.target for d in deps]

        # Generar sugerencias de tests
        test_suggestions = self.generate_test_suggestions(changes)

        # Generar resumen
        summary = self._generate_summary(changes, risk)

        return RegressionReport(
            timestamp=datetime.now().isoformat(),
            changes_analyzed=len(changes),
            total_risk_score=risk.score,
            risks=[risk],
            dependency_graph=dep_graph,
            test_suggestions=test_suggestions,
            summary=summary,
        )

    def _get_all_functions(self, file_path: str) -> list[str]:
        """Obtener todas las funciones de un archivo"""
        functions = []
        full_path = self.project_root / file_path

        if full_path.exists():
            try:
                content = full_path.read_text()
                for match in re.finditer(r"def\s+(\w+)", content):
                    functions.append(match.group(1))
            except Exception:
                pass

        return functions

    def _get_all_classes(self, file_path: str) -> list[str]:
        """Obtener todas las clases de un archivo"""
        classes = []
        full_path = self.project_root / file_path

        if full_path.exists():
            try:
                content = full_path.read_text()
                for match in re.finditer(r"class\s+(\w+)", content):
                    classes.append(match.group(1))
            except Exception:
                pass

        return classes

    def _generate_summary(self, changes: list[FileChange], risk: RegressionRisk) -> str:
        """Generar resumen legible"""
        level_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}

        emoji = level_emoji.get(risk.level, "⚪")

        summary = f"{emoji} Riesgo {risk.level.upper()}: {risk.score}/100\n\n"
        summary += f"Archivos analizados: {len(changes)}\n"
        summary += f"Funciones afectadas: {len(risk.affected_functions)}\n"
        summary += f"Archivos dependientes: {len(risk.affected_files) - len(changes)}\n"

        if risk.reasons:
            summary += "\nFactores de riesgo principales:\n"
            for reason in risk.reasons[:5]:
                summary += f"  • {reason}\n"

        return summary


def main():
    parser = argparse.ArgumentParser(
        description="Regression Detector - Detecta regresiones de código"
    )
    parser.add_argument("--git-diff", action="store_true", help="Analizar últimos cambios de git")
    parser.add_argument(
        "--compare", nargs=2, metavar=("BASE", "TARGET"), help="Comparar dos referencias de git"
    )
    parser.add_argument("--file", "-f", help="Analizar archivo específico")
    parser.add_argument("--json", action="store_true", help="Output en JSON")
    parser.add_argument("--watch", action="store_true", help="Modo monitoreo continuo")

    args = parser.parse_args()
    detector = RegressionDetector()

    # Determinar qué analizar
    base_ref = "HEAD~1"
    target_ref = "HEAD"

    if args.compare:
        base_ref, target_ref = args.compare

    # Ejecutar análisis
    report = detector.analyze(base_ref=base_ref, target_ref=target_ref, file_path=args.file)

    # Output
    if args.json:
        output = {
            "timestamp": report.timestamp,
            "changes_analyzed": report.changes_analyzed,
            "risk_score": report.total_risk_score,
            "risk_level": report.risks[0].level if report.risks else "none",
            "affected_files": report.risks[0].affected_files if report.risks else [],
            "affected_functions": report.risks[0].affected_functions if report.risks else [],
            "reasons": report.risks[0].reasons if report.risks else [],
            "recommendations": report.risks[0].recommendations if report.risks else [],
            "test_suggestions": report.test_suggestions,
            "dependency_graph": report.dependency_graph,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print("\n" + "=" * 60)
        print("ANÁLISIS DE REGRESIÓN")
        print("=" * 60)
        print(f"\n{report.summary}")

        if report.risks and report.risks[0].recommendations:
            print("\nRecomendaciones:")
            for rec in report.risks[0].recommendations:
                print(f"  {rec}")

        if report.test_suggestions:
            print(f"\nTests sugeridos ({len(report.test_suggestions)}):")
            for sug in report.test_suggestions[:10]:
                print(f"  → {sug}")

        print()


if __name__ == "__main__":
    main()
