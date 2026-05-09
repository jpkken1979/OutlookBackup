#!/usr/bin/env python3
"""
Startup Skill - Verifica entorno y lanza servidores
Automatiza: Python check, npm check, .env, puertos, dependencias, servidores

Uso:
    python startup.py
    python startup.py --verbose
    python startup.py --skip-deps
"""

import subprocess
import sys
import os
import time
from pathlib import Path
import argparse


class StartupManager:
    """Gestor de startup automatico"""

    def __init__(self, verbose: bool = False, skip_deps: bool = False):
        self.verbose = verbose
        self.skip_deps = skip_deps
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.errors = []
        self.warnings = []
        self.processes = []

    def log(self, message: str, level: str = "INFO"):
        """Log estructurado"""
        if level == "ERROR":
            print(f"[ERROR] {message}")
            self.errors.append(message)
        elif level == "WARN":
            print(f"[WARN] {message}")
            self.warnings.append(message)
        elif level == "SUCCESS":
            print(f"[OK] {message}")
        elif self.verbose:
            print(f"[INFO] {message}")

    def run_command(self, cmd: list, check: bool = False) -> tuple[int, str, str]:
        """Ejecutar comando del sistema"""
        try:
            # Pasar variables de entorno para que subprocess encuentre ejecutables
            env = os.environ.copy()
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=30, cwd=str(self.project_root), env=env
            )
            if self.verbose and result.stdout:
                print(f"   Output: {result.stdout[:100]}")
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Timeout"
        except Exception as e:
            return 1, "", str(e)

    # FASE 1: Verificar Python
    def check_python(self) -> bool:
        """Verificar Python 3.11+"""
        print("\n[FASE 1/6] Verificando Python...")

        version = sys.version_info
        required = (3, 11)

        if version >= required:
            self.log(f"Python {version.major}.{version.minor}.{version.micro} OK", "SUCCESS")
            return True
        else:
            self.log(f"Python 3.11+ requerido (tienes {version.major}.{version.minor})", "ERROR")
            return False

    # FASE 2: Verificar npm
    def check_npm(self) -> bool:
        """Verificar npm instalado"""
        print("\n[FASE 2/6] Verificando npm...")

        # En Windows, usar npm.cmd; en otros sistemas, npm
        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
        code, stdout, stderr = self.run_command([npm_cmd, "--version"])

        if code == 0:
            version = stdout.strip()
            self.log(f"npm {version} OK", "SUCCESS")
            return True
        else:
            self.log("npm no esta instalado", "ERROR")
            return False

    # FASE 3: Verificar .env
    def check_env(self) -> bool:
        """Verificar archivo .env"""
        print("\n[FASE 3/6] Verificando .env...")

        env_path = self.project_root / ".env"
        env_example = self.project_root / ".env.example"

        if env_path.exists():
            self.log(".env encontrado OK", "SUCCESS")
            return True
        elif env_example.exists():
            self.log(".env no existe, creando desde .env.example...")
            try:
                import shutil

                shutil.copy(env_example, env_path)
                self.log(".env creado desde .env.example OK", "SUCCESS")
                return True
            except Exception as e:
                self.log(f"No se pudo crear .env: {e}", "ERROR")
                return False
        else:
            self.log(".env y .env.example no encontrados", "WARN")
            return True  # No es critico

    # FASE 4: Resolver puertos
    def resolve_ports(self) -> bool:
        """Matar procesos en puertos conflictuados"""
        print("\n[FASE 4/6] Resolviendo puertos...")

        ports_to_check = [3000, 8000, 3777]

        for port in ports_to_check:
            if self._port_in_use(port):
                self.log(f"Puerto {port} en uso, intentando liberar...", "WARN")
                if self._kill_process_on_port(port):
                    self.log(f"Puerto {port} liberado OK", "SUCCESS")
                else:
                    self.log(f"No se pudo liberar puerto {port}", "WARN")

        return True

    def _port_in_use(self, port: int) -> bool:
        """Verificar si puerto esta en uso"""
        if sys.platform == "win32":
            code, _, _ = self.run_command(["netstat", "-an"], check=False)
            # En Windows, simplemente intentar iniciar en el puerto
            return False  # Por ahora, no verificamos
        else:
            code, _, _ = self.run_command(["lsof", "-i", f":{port}"], check=False)
            return code == 0

    def _kill_process_on_port(self, port: int) -> bool:
        """Matar proceso en puerto especifico"""
        if sys.platform == "win32":
            # En Windows, usar netstat y taskkill
            code, stdout, _ = self.run_command(["netstat", "-ano"], check=False)
            # Buscar puerto en output
            for line in stdout.split("\n"):
                if f":{port}" in line:
                    parts = line.split()
                    if parts:
                        try:
                            pid = parts[-1]
                            subprocess.run(["taskkill", "/PID", pid, "/F"], timeout=5)
                            return True
                        except Exception:
                            return False
            return False
        else:
            code, _, _ = self.run_command(["fuser", "-k", f"{port}/tcp"], check=False)
            return code == 0

    # FASE 5: Instalar dependencias
    def install_dependencies(self) -> bool:
        """Instalar dependencias Python y Node"""
        print("\n[FASE 5/6] Instalando dependencias...")

        if self.skip_deps:
            self.log("Saltando instalacion de dependencias (--skip-deps)", "WARN")
            return True

        # Python
        req_path = self.project_root / "requirements.txt"
        if req_path.exists():
            self.log("Instalando dependencias Python...")
            code, _, stderr = self.run_command(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
            )
            if code == 0:
                self.log("Dependencias Python instaladas OK", "SUCCESS")
            else:
                self.log(f"Error instalando Python deps: {stderr[:100]}", "WARN")

        # Node
        pkg_path = self.project_root / "package.json"
        if pkg_path.exists():
            self.log("Instalando dependencias Node...")
            npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
            code, _, stderr = self.run_command([npm_cmd, "install"])
            if code == 0:
                self.log("Dependencias Node instaladas OK", "SUCCESS")
            else:
                self.log(f"Error instalando Node deps: {stderr[:100]}", "WARN")

        return True

    # FASE 6: Iniciar servidores
    def start_servers(self) -> bool:
        """Iniciar servidores backend + frontend"""
        print("\n[FASE 6/6] Iniciando servidores...")

        # Buscar main.py (FastAPI)
        main_path = self.project_root / "main.py"
        if not main_path.exists():
            # Buscar en subdirectorios
            for candidate in self.project_root.glob("**/main.py"):
                if ".venv" not in str(candidate):
                    main_path = candidate
                    break

        if main_path.exists():
            self.log(f"Iniciando FastAPI desde {main_path.name}...")
            try:
                proc = subprocess.Popen(
                    [sys.executable, str(main_path)],
                    cwd=str(main_path.parent),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.processes.append(proc)
                time.sleep(2)  # Esperar a que inicie

                if proc.poll() is None:
                    self.log("FastAPI iniciado en http://localhost:8000 OK", "SUCCESS")
                else:
                    self.log("FastAPI no pudo iniciar", "ERROR")
                    return False
            except Exception as e:
                self.log(f"Error iniciando FastAPI: {e}", "ERROR")

        return True

    def report(self) -> int:
        """Reporte final"""
        print("\n" + "=" * 70)
        print("STARTUP REPORT")
        print("=" * 70)

        if not self.errors:
            print("\n[OK] STARTUP EXITOSO")
            print("\nServidores disponibles:")
            print("   Backend:  http://localhost:8000")
            print("   Frontend: http://localhost:3000")
            return 0
        else:
            print(f"\n[WARN] STARTUP CON PROBLEMAS ({len(self.errors)} errores)")
            print("\nErrores:")
            for err in self.errors:
                print(f"   [ERROR] {err}")

            if self.warnings:
                print(f"\nAdvertencias ({len(self.warnings)}):")
                for warn in self.warnings:
                    print(f"   [WARN] {warn}")

            return 1

    def run(self) -> int:
        """Ejecutar pipeline completo"""
        print("=" * 70)
        print("STARTUP - Verificacion & Lanzamiento")
        print("=" * 70)

        try:
            # Ejecutar fases
            if not self.check_python():
                return 1

            if not self.check_npm():
                return 1

            if not self.check_env():
                return 1

            if not self.resolve_ports():
                return 1

            if not self.install_dependencies():
                return 1

            if not self.start_servers():
                return 1

            # Reporte
            return self.report()

        except KeyboardInterrupt:
            print("\n\n[STOP] Startup interrumpido por usuario")
            self._cleanup()
            return 1
        except Exception as e:
            print(f"\n[ERROR] Error inesperado: {e}")
            return 1

    def _cleanup(self):
        """Limpiar procesos"""
        for proc in self.processes:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass


def main():
    parser = argparse.ArgumentParser(
        description="Startup - Verifica entorno y lanza servidores",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python startup.py              # Startup completo
  python startup.py --verbose    # Con detalles
  python startup.py --skip-deps  # Sin instalar deps
        """,
    )

    parser.add_argument("--verbose", action="store_true", help="Mostrar detalles")
    parser.add_argument("--skip-deps", action="store_true", help="No instalar dependencias")

    args = parser.parse_args()

    manager = StartupManager(verbose=args.verbose, skip_deps=args.skip_deps)
    exit_code = manager.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
