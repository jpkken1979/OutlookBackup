#!/usr/bin/env python3
"""
Finalizer - Cierre limpio de sesiones de trabajo.

Uso:
    python finalize.py                    # Finaliza sesión actual
    python finalize.py --no-push          # Sin push
    python finalize.py --dry-run          # Solo mostrar qué haría
    python finalize.py --message "msg"    # Mensaje de commit personalizado
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


class Colors:
    """Colores ANSI para terminal."""

    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


class Finalizer:
    """Agente que cierra sesiones de trabajo de forma limpia."""

    def __init__(self, project_path: Path, dry_run: bool = False):
        self.path = project_path
        self.dry_run = dry_run
        self.modified_files: list[str] = []
        self.completed_tasks: list[str] = []
        self.pending_tasks: list[str] = []
        self.warnings: list[str] = []
        self.commit_hash: str | None = None
        self.is_git_repo = (self.path / ".git").exists()

    def run(self, custom_message: str | None = None, no_push: bool = False) -> bool:
        """Ejecuta el proceso completo de finalización."""
        print(f"\n{Colors.CYAN}{'=' * 60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}           FINALIZANDO SESION{Colors.RESET}")
        print(f"{Colors.CYAN}{'=' * 60}{Colors.RESET}\n")

        # Fase 1: Recolectar información
        print(f"{Colors.CYAN}[1/6]{Colors.RESET} Recolectando informacion...")
        self._collect_info()

        # Fase 2: Actualizar memoria
        print(f"{Colors.CYAN}[2/6]{Colors.RESET} Actualizando memoria...")
        self._update_memory()

        # Fase 3: Verificar documentación
        print(f"{Colors.CYAN}[3/6]{Colors.RESET} Verificando documentacion...")
        self._check_documentation()

        # Fase 4: Verificar código
        print(f"{Colors.CYAN}[4/6]{Colors.RESET} Verificando codigo...")
        self._verify_code()

        # Fase 5: Limpiar temporales
        print(f"{Colors.CYAN}[5/6]{Colors.RESET} Limpiando temporales...")
        self._clean_temp()

        # Fase 6: Commit y Push
        print(f"{Colors.CYAN}[6/6]{Colors.RESET} Commit y Push...")
        if self.is_git_repo:
            self._commit_and_push(custom_message, no_push)
        else:
            print(f"      {Colors.YELLOW}[SKIP]{Colors.RESET} No es repositorio git")

        # Mostrar resumen
        self._show_summary()

        return True

    def _collect_info(self):
        """Recolecta información sobre la sesión."""
        if self.is_git_repo:
            # Archivos modificados
            result = subprocess.run(
                ["git", "status", "--porcelain"], cwd=self.path, capture_output=True, text=True
            )
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    status = line[:2].strip()
                    filename = line[3:].strip()
                    self.modified_files.append(f"{status} {filename}")

            print(f"      -> {len(self.modified_files)} archivos modificados")

        # Buscar TODOs en archivos recientes
        self._find_pending_tasks()
        print(f"      -> {len(self.pending_tasks)} tareas pendientes encontradas")

    def _find_pending_tasks(self):
        """Busca tareas pendientes en archivos de contexto."""
        context_files = [
            self.path / ".context" / "SESSION_LOG.md",
            self.path / ".context" / "PENDING_TASKS.md",
            self.path / ".md" / f"session-{datetime.now().strftime('%Y-%m-%d')}.md",
        ]

        for f in context_files:
            if f.exists():
                try:
                    content = f.read_text(encoding="utf-8")
                    # Buscar checkboxes sin marcar
                    for match in re.finditer(r"- \[ \] (.+)", content):
                        task = match.group(1).strip()
                        if task not in self.pending_tasks:
                            self.pending_tasks.append(task)
                except Exception:
                    pass

    def _update_memory(self):
        """Actualiza archivos de memoria/contexto."""
        context_dir = self.path / ".context"
        context_dir.mkdir(exist_ok=True)

        session_log = context_dir / "SESSION_LOG.md"
        now = datetime.now()

        # Crear entrada de sesión
        entry = f"""
## Sesion {now.strftime("%Y-%m-%d %H:%M")}

### Archivos Modificados
"""
        for f in self.modified_files[:20]:
            entry += f"- `{f}`\n"

        if len(self.modified_files) > 20:
            entry += f"- ... y {len(self.modified_files) - 20} mas\n"

        if self.pending_tasks:
            entry += "\n### Tareas Pendientes\n"
            for task in self.pending_tasks:
                entry += f"- [ ] {task}\n"

        entry += "\n---\n"

        if not self.dry_run:
            # Append al log existente o crear nuevo
            if session_log.exists():
                existing = session_log.read_text(encoding="utf-8")
                session_log.write_text(existing + entry, encoding="utf-8")
            else:
                header = "# Session Log\n\nHistorial de sesiones de trabajo.\n\n---\n"
                session_log.write_text(header + entry, encoding="utf-8")

            print(f"      {Colors.GREEN}[OK]{Colors.RESET} .context/SESSION_LOG.md actualizado")
        else:
            print(f"      {Colors.YELLOW}[DRY-RUN]{Colors.RESET} Actualizaria SESSION_LOG.md")

    def _check_documentation(self):
        """Verifica y actualiza documentación si es necesario."""
        # Verificar si CHANGELOG existe
        changelog = self.path / "CHANGELOG.md"
        if changelog.exists() and self.modified_files:
            print(
                f"      {Colors.YELLOW}[INFO]{Colors.RESET} CHANGELOG.md existe - considera actualizarlo"
            )

        # Verificar APP_KNOWLEDGE.md
        app_knowledge = self.path / ".context" / "APP_KNOWLEDGE.md"
        if app_knowledge.exists():
            print(f"      {Colors.GREEN}[OK]{Colors.RESET} APP_KNOWLEDGE.md presente")
        else:
            print(
                f"      {Colors.YELLOW}[INFO]{Colors.RESET} Sin APP_KNOWLEDGE.md - considera ejecutar app-auditor"
            )

    def _verify_code(self):
        """Ejecuta verificaciones de código."""
        # Verificar archivos sensibles
        sensitive_patterns = [".env", "credentials", "secret", "password", "token", "api_key"]

        for f in self.modified_files:
            filename = f.split()[-1].lower()
            for pattern in sensitive_patterns:
                if pattern in filename and not filename.endswith(".example"):
                    self.warnings.append(f"Archivo sensible: {f}")

        if self.warnings:
            print(f"      {Colors.RED}[WARN]{Colors.RESET} {len(self.warnings)} advertencias")
            for w in self.warnings:
                print(f"             - {w}")
        else:
            print(f"      {Colors.GREEN}[OK]{Colors.RESET} Sin archivos sensibles")

        # Intentar ejecutar linter
        if (self.path / "package.json").exists():
            result = subprocess.run(
                ["npm", "run", "lint"], cwd=self.path, capture_output=True, text=True, shell=False
            )
            if result.returncode == 0:
                print(f"      {Colors.GREEN}[OK]{Colors.RESET} Linter JS/TS passed")
            else:
                print(f"      {Colors.YELLOW}[WARN]{Colors.RESET} Linter tiene warnings")

        elif (self.path / "pyproject.toml").exists() or (self.path / "requirements.txt").exists():
            result = subprocess.run(
                ["python", "-m", "ruff", "check", "."],
                cwd=self.path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print(f"      {Colors.GREEN}[OK]{Colors.RESET} Linter Python passed")
            elif "No module named ruff" not in result.stderr:
                print(f"      {Colors.YELLOW}[WARN]{Colors.RESET} Linter tiene warnings")

    def _clean_temp(self):
        """Busca archivos temporales."""
        temp_patterns = ["*.tmp", "*.bak", "*~", "*.swp", "*.pyc"]
        temp_found = []

        for pattern in temp_patterns:
            for f in self.path.rglob(pattern):
                if ".git" not in str(f) and "node_modules" not in str(f):
                    temp_found.append(str(f.relative_to(self.path)))

        if temp_found:
            print(
                f"      {Colors.YELLOW}[INFO]{Colors.RESET} {len(temp_found)} archivos temporales encontrados"
            )
        else:
            print(f"      {Colors.GREEN}[OK]{Colors.RESET} Sin temporales")

    def _commit_and_push(self, custom_message: str | None, no_push: bool):
        """Hace commit y push."""
        if not self.modified_files:
            print(f"      {Colors.YELLOW}[SKIP]{Colors.RESET} Sin cambios para commit")
            return

        # Detectar tipo de commit
        commit_type = "chore"
        files_str = " ".join(f.split()[-1] for f in self.modified_files[:5])

        if any(x in files_str for x in ["feat", "add", "new", "create"]):
            commit_type = "feat"
        elif any(x in files_str for x in ["fix", "bug", "patch"]):
            commit_type = "fix"
        elif any(x in files_str for x in [".md", "README", "docs"]):
            commit_type = "docs"
        elif any(x in files_str for x in ["test", "spec"]):
            commit_type = "test"

        # Generar mensaje
        if custom_message:
            message = custom_message
        else:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            summary = f"Session {now}"
            if len(self.modified_files) <= 3:
                files_list = ", ".join(f.split()[-1] for f in self.modified_files)
                summary = f"Update {files_list}"

            message = f"""{commit_type}: {summary}

Archivos modificados: {len(self.modified_files)}
"""
            if self.pending_tasks:
                message += "\nTareas pendientes:\n"
                for task in self.pending_tasks[:5]:
                    message += f"- [ ] {task}\n"

            message += "\nCo-Authored-By: Claude <noreply@anthropic.com>"

        if self.dry_run:
            print(f"      {Colors.YELLOW}[DRY-RUN]{Colors.RESET} Commit: {commit_type}: ...")
            return

        # Remover archivos sensibles del staging
        for w in self.warnings:
            if "Archivo sensible" in w:
                filename = w.split(": ")[-1].split()[-1]
                subprocess.run(
                    ["git", "reset", "HEAD", filename], cwd=self.path, capture_output=True
                )

        # Git add
        subprocess.run(["git", "add", "-A"], cwd=self.path, capture_output=True)

        # Git commit
        result = subprocess.run(
            ["git", "commit", "-m", message], cwd=self.path, capture_output=True, text=True
        )

        if result.returncode == 0:
            # Obtener hash del commit
            hash_result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=self.path,
                capture_output=True,
                text=True,
            )
            self.commit_hash = hash_result.stdout.strip()
            print(f"      {Colors.GREEN}[OK]{Colors.RESET} Commit: {self.commit_hash}")

            # Push
            if not no_push:
                # Obtener branch actual
                branch_result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=self.path,
                    capture_output=True,
                    text=True,
                )
                branch = branch_result.stdout.strip() or "main"

                push_result = subprocess.run(
                    ["git", "push", "origin", branch], cwd=self.path, capture_output=True, text=True
                )

                if push_result.returncode == 0:
                    print(f"      {Colors.GREEN}[OK]{Colors.RESET} Push: origin/{branch}")
                else:
                    print(f"      {Colors.RED}[ERROR]{Colors.RESET} Push fallido")
                    print(f"             {push_result.stderr[:100]}")
            else:
                print(f"      {Colors.YELLOW}[SKIP]{Colors.RESET} Push deshabilitado")
        else:
            if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                print(f"      {Colors.YELLOW}[SKIP]{Colors.RESET} Nada que commitear")
            else:
                print(f"      {Colors.RED}[ERROR]{Colors.RESET} Commit fallido")

    def _show_summary(self):
        """Muestra resumen final."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        print(f"\n{Colors.GREEN}{'=' * 60}{Colors.RESET}")
        print(f"{Colors.GREEN}{'=' * 60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.GREEN}           SESION FINALIZADA{Colors.RESET}")
        print(f"{Colors.GREEN}{'=' * 60}{Colors.RESET}")
        print(f"  Fecha: {now}")
        print(f"  Proyecto: {self.path.name}")
        print(f"{Colors.GREEN}{'-' * 60}{Colors.RESET}")
        print(f"  Archivos modificados: {len(self.modified_files)}")
        print(f"  Tareas pendientes: {len(self.pending_tasks)}")
        print(f"  Advertencias: {len(self.warnings)}")

        if self.commit_hash:
            print(f"  Commit: {self.commit_hash}")

        print(f"{Colors.GREEN}{'=' * 60}{Colors.RESET}")

        if self.pending_tasks:
            print(f"\n{Colors.YELLOW}Tareas pendientes:{Colors.RESET}")
            for task in self.pending_tasks[:10]:
                print(f"  - [ ] {task}")

        print(f"\n{Colors.CYAN}Memoria guardada en: .context/SESSION_LOG.md{Colors.RESET}")
        print(f"{Colors.CYAN}Para retomar: lee .context/SESSION_LOG.md{Colors.RESET}\n")


def main():
    parser = argparse.ArgumentParser(description="Finalizer - Cierre limpio de sesiones")
    parser.add_argument("path", nargs="?", default=".", help="Ruta del proyecto")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Solo mostrar que haria")
    parser.add_argument("--no-push", action="store_true", help="No hacer push")
    parser.add_argument("--message", "-m", help="Mensaje de commit personalizado")

    args = parser.parse_args()

    project_path = Path(args.path).resolve()

    if not project_path.exists():
        print(f"Error: {project_path} no existe")
        return 1

    finalizer = Finalizer(project_path, dry_run=args.dry_run)
    finalizer.run(custom_message=args.message, no_push=args.no_push)

    return 0


if __name__ == "__main__":
    sys.exit(main())
