#!/usr/bin/env python3
"""
Auto Updater - Sistema de auto-actualización del ecosistema.

Funcionalidades:
- Verificar nuevas versiones
- Actualizar agentes
- Sincronizar con repositorio
- Backup antes de actualizar
- Rollback si falla
"""

import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from packaging.version import InvalidVersion, Version

try:
    from .security_utils import validate_url_for_ssrf
except ImportError:
    from security_utils import validate_url_for_ssrf


@dataclass
class UpdateInfo:
    """Información de actualización."""

    current_version: str
    latest_version: str
    update_available: bool
    changes: list[str]
    breaking_changes: bool = False
    source: str = "git"


@dataclass
class UpdateResult:
    """Resultado de actualización."""

    success: bool
    message: str
    old_version: str
    new_version: str
    backup_path: str | None = None
    changes_applied: list[str] | None = None


class AutoUpdater:
    """
    Sistema de auto-actualización.

    Flujo:
    1. Verificar versión actual
    2. Comparar con remoto
    3. Crear backup
    4. Aplicar actualizaciones
    5. Verificar integridad
    6. Rollback si falla
    """

    VERSION_FILE = ".agent/VERSION"
    BACKUP_DIR = ".agent/backups"
    CURRENT_VERSION = "4.3.0"

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.backup_dir = self.project_root / self.BACKUP_DIR
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _detect_default_branch(self) -> str:
        """Detecta la rama por defecto en origin."""
        try:
            result = subprocess.run(
                ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=10,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split("/")[-1]
        except Exception:
            pass

        return "main"

    @staticmethod
    def _check_pypi_latest_version() -> str | None:
        """Consulta PyPI para detectar versión publicada más reciente."""
        url = "https://pypi.org/pypi/antigravity-agents/json"
        try:
            # SSRF: validar URL (hardcoded a PyPI public, passara validacion)
            valid, _ = validate_url_for_ssrf(url)
            if valid:
                with urllib.request.urlopen(url, timeout=10) as response:
                    raw_payload = response.read().decode("utf-8")
            else:
                raw_payload = None
        except (urllib.error.URLError, TimeoutError):
            return None

        if raw_payload is None:
            return None

        try:
            data = json.loads(raw_payload)
        except json.JSONDecodeError:
            return None

        if not isinstance(data, dict):
            return None

        info = data.get("info", {})
        if not isinstance(info, dict):
            return None

        latest = info.get("version")
        if isinstance(latest, str) and latest.strip():
            return latest.strip()

        return None

    def get_current_version(self) -> str:
        """Obtiene versión actual."""
        version_file = self.project_root / self.VERSION_FILE
        if version_file.exists():
            return version_file.read_text(encoding="utf-8").strip()

        version_file.parent.mkdir(parents=True, exist_ok=True)
        version_file.write_text(self.CURRENT_VERSION, encoding="utf-8")
        return self.CURRENT_VERSION

    def check_for_updates(self) -> UpdateInfo:
        """Verifica si hay actualizaciones disponibles."""
        current = self.get_current_version()
        latest = current
        changes: list[str] = []
        update_available = False
        source = "git"

        try:
            result = subprocess.run(
                ["git", "fetch", "--dry-run"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=30,
                check=False,
            )

            if result.returncode == 0 and (result.stdout or result.stderr):
                result = subprocess.run(
                    ["git", "log", "HEAD..origin/main", "--oneline"],
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                    timeout=10,
                    check=False,
                )

                if result.returncode == 0 and result.stdout.strip():
                    commits = result.stdout.strip().split("\n")
                    if commits and commits[0]:
                        update_available = True
                        changes = commits[:10]
        except Exception:
            pass

        if not update_available:
            pypi_latest = self._check_pypi_latest_version()
            if pypi_latest and self._is_newer_version(current, pypi_latest):
                latest = pypi_latest
                source = "pypi"
                update_available = True
                changes = [f"Nueva versión publicada en PyPI: {pypi_latest}"]

        return UpdateInfo(
            current_version=current,
            latest_version=latest,
            update_available=update_available,
            changes=changes,
            breaking_changes=any("BREAKING" in c.upper() for c in changes),
            source=source,
        )

    @staticmethod
    def _is_newer_version(current: str, candidate: str) -> bool:
        """Evalúa si candidate es más nueva que current."""
        try:
            return Version(candidate) > Version(current)
        except InvalidVersion:
            return candidate.strip() != current.strip()

    def create_backup(self) -> str:
        """Crea backup antes de actualizar."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}"
        backup_path = self.backup_dir / backup_name

        critical_dirs = [".agent/core", ".agent/memory", ".agent/agents"]

        backup_path.mkdir(parents=True, exist_ok=True)

        for dir_name in critical_dirs:
            src = self.project_root / dir_name
            if src.exists():
                dst = backup_path / dir_name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src, dst, dirs_exist_ok=True)

        (backup_path / "VERSION").write_text(self.get_current_version(), encoding="utf-8")
        self._cleanup_old_backups(keep=5)
        return str(backup_path)

    def _cleanup_old_backups(self, keep: int = 5):
        """Elimina backups antiguos."""
        backups = sorted(
            [d for d in self.backup_dir.iterdir() if d.is_dir()],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )

        for old_backup in backups[keep:]:
            shutil.rmtree(old_backup)

    def apply_update(self, force: bool = False) -> UpdateResult:
        """Aplica actualización."""
        info = self.check_for_updates()

        if not info.update_available and not force:
            return UpdateResult(
                success=True,
                message="Already up to date",
                old_version=info.current_version,
                new_version=info.current_version,
            )

        if info.breaking_changes and not force:
            return UpdateResult(
                success=False,
                message="Breaking changes detected. Use --force to proceed.",
                old_version=info.current_version,
                new_version=info.latest_version,
            )

        backup_path = self.create_backup()

        try:
            result = subprocess.run(
                ["git", "pull", "origin", self._detect_default_branch()],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=120,
                check=False,
            )

            if result.returncode != 0:
                raise Exception(f"Git pull failed: {result.stderr}")

            version_file = self.project_root / self.VERSION_FILE
            new_version = self.CURRENT_VERSION
            version_file.write_text(new_version, encoding="utf-8")

            if not self._verify_integrity():
                raise Exception("Integrity check failed after update")

            return UpdateResult(
                success=True,
                message="Update applied successfully",
                old_version=info.current_version,
                new_version=new_version,
                backup_path=backup_path,
                changes_applied=info.changes,
            )

        except Exception as e:
            self._rollback(backup_path)
            return UpdateResult(
                success=False,
                message=f"Update failed, rolled back: {e}",
                old_version=info.current_version,
                new_version=info.current_version,
                backup_path=backup_path,
            )

    def _verify_integrity(self) -> bool:
        """Verifica integridad después de actualización."""
        critical_files = [
            ".agent/core/session_bootstrap.py",
            ".agent/core/claude_core.py",
            ".agent/core/health_check.py",
        ]

        for file_path in critical_files:
            if not (self.project_root / file_path).exists():
                return False

        agents_dir = self.project_root / ".agent/agents"
        if not agents_dir.exists():
            return False

        agents = list(agents_dir.glob("*/IDENTITY.md"))
        return len(agents) >= 10

    def _rollback(self, backup_path: str):
        """Restaura desde backup."""
        backup = Path(backup_path)
        if not backup.exists():
            return

        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_backup = Path(tmpdir) / "backup"
            shutil.copytree(backup, tmp_backup)

            for item in tmp_backup.iterdir():
                if item.is_dir() and item.name != "VERSION":
                    dst = self.project_root / item.name
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(item, dst)

            version_backup = tmp_backup / "VERSION"
            if version_backup.exists():
                version_file = self.project_root / self.VERSION_FILE
                version_file.parent.mkdir(parents=True, exist_ok=True)
                version_content = version_backup.read_text(encoding="utf-8")
                version_file.write_text(version_content, encoding="utf-8")

    def list_backups(self) -> list[dict]:
        """Lista backups disponibles."""
        backups = []
        for directory in sorted(self.backup_dir.iterdir(), reverse=True):
            if directory.is_dir():
                version_file = directory / "VERSION"
                version = "unknown"
                if version_file.exists():
                    version = version_file.read_text(encoding="utf-8").strip()

                backups.append(
                    {
                        "name": directory.name,
                        "path": str(directory),
                        "version": version,
                        "created": datetime.fromtimestamp(directory.stat().st_mtime).isoformat(),
                    }
                )
        return backups

    def restore_backup(self, backup_name: str) -> bool:
        """Restaura un backup específico."""
        backup_path = self.backup_dir / backup_name
        if not backup_path.exists():
            return False

        self._rollback(str(backup_path))
        return True


def main():
    """CLI para auto-updater."""
    import argparse

    parser = argparse.ArgumentParser(description="Antigravity Auto Updater")
    parser.add_argument(
        "command",
        choices=["check", "update", "backup", "list", "restore"],
        help="Comando a ejecutar",
    )
    parser.add_argument("--force", action="store_true", help="Forzar actualización")
    parser.add_argument("--backup-name", help="Nombre del backup a restaurar")
    args = parser.parse_args()

    updater = AutoUpdater()

    if args.command == "check":
        info = updater.check_for_updates()
        print(f"Current version: {info.current_version}")
        print(f"Update available: {info.update_available}")
        print(f"Source: {info.source}")
        if info.changes:
            print("Changes:")
            for change in info.changes:
                print(f"  - {change}")
    elif args.command == "update":
        result = updater.apply_update(force=args.force)
        print(f"Success: {result.success}")
        print(f"Message: {result.message}")
        if result.backup_path:
            print(f"Backup: {result.backup_path}")
    elif args.command == "backup":
        path = updater.create_backup()
        print(f"Backup created: {path}")
    elif args.command == "list":
        backups = updater.list_backups()
        print("Available backups:")
        for backup in backups:
            print(f"  - {backup['name']} (v{backup['version']}) - {backup['created']}")
    elif args.command == "restore":
        if not args.backup_name:
            print("Error: --backup-name required")
            sys.exit(1)
        if updater.restore_backup(args.backup_name):
            print(f"Restored: {args.backup_name}")
        else:
            print(f"Backup not found: {args.backup_name}")
            sys.exit(1)


if __name__ == "__main__":
    main()
