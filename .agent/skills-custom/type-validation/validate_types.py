#!/usr/bin/env python3
"""
Type Validation Helper - Ejecuta mypy en archivos específicos
Uso: python validate_types.py backend/services/payroll_service.py
"""

import subprocess
import sys
from pathlib import Path


def run_mypy(file_path: str, strict: bool = False) -> tuple[int, str, str]:
    """Ejecuta mypy en un archivo específico."""
    cmd = ["mypy", file_path, "--show-error-codes", "--pretty"]

    if strict:
        cmd.append("--strict")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 1, "", "Error: mypy no está instalado. Instala con: pip install mypy"
    except subprocess.TimeoutExpired:
        return 1, "", "Error: mypy tardó demasiado (timeout)"


def format_error_list(stdout: str) -> list[str]:
    """Extrae lista de errores del output de mypy."""
    lines = stdout.strip().split("\n")
    errors = []

    for line in lines:
        if "error:" in line or "note:" in line:
            errors.append(line)

    return errors


def print_report(file_path: str, return_code: int, stdout: str, stderr: str) -> None:
    """Imprime reporte formateado."""
    print("\n" + "=" * 70)
    print(f"TYPE VALIDATION REPORT: {file_path}")
    print("=" * 70 + "\n")

    if stderr:
        print(f"❌ Error ejecutando mypy:\n{stderr}\n")
        return

    errors = format_error_list(stdout)

    if return_code == 0:
        print("✅ SUCCESS: No type errors found!\n")
        print("Total errors: 0")
    else:
        print(f"❌ Type errors found: {len(errors)}\n")

        print("ERRORES ENCONTRADOS:")
        print("-" * 70)
        for i, error in enumerate(errors, 1):
            print(f"{i}. {error}")
        print("-" * 70)

        print("\n📋 PRÓXIMOS PASOS:")
        print("1. Crea TODO list con cada error")
        print("2. Corrige UN error a la vez")
        print("3. Ejecuta mypy nuevamente después de cada fix")
        print("4. Verifica que return code sea 0")

    print(f"\nFull output:\n{stdout}")


def main():
    if len(sys.argv) < 2:
        print("Uso: python validate_types.py <archivo.py> [--strict]")
        print("Ejemplo: python validate_types.py backend/services/payroll_service.py")
        sys.exit(1)

    file_path = sys.argv[1]
    strict = "--strict" in sys.argv

    # Verificar que archivo existe
    if not Path(file_path).exists():
        print(f"❌ Error: Archivo no encontrado: {file_path}")
        sys.exit(1)

    print(f"🔍 Validando tipos en: {file_path}")
    if strict:
        print("   (Modo STRICT habilitado)")
    print()

    # Ejecutar mypy
    return_code, stdout, stderr = run_mypy(file_path, strict=strict)

    # Imprimir reporte
    print_report(file_path, return_code, stdout, stderr)

    # Exit con código mypy
    sys.exit(return_code)


if __name__ == "__main__":
    main()
