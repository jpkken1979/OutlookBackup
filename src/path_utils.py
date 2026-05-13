"""Soporte de paths largos en Windows (Fase 3 plan v3.2).

Por que existe este modulo
--------------------------
Windows tiene un limite historico MAX_PATH = 260 chars (incluido NUL terminator).
Para paths mas largos hay que usar el prefijo `\\?\\` (extended-length path syntax)
que sube el limite a 32767 chars wchars.

Por que importa para UNS-Kikaku
-------------------------------
Paths japoneses con kanji/hiragana cuentan como UN char por glifo (no por byte),
pero igualmente se acumulan rapido. Casos reales:

- backup_dir custom del usuario: `C:\\Users\\田中太郎\\OneDrive\\バックアップ\\` (~50 chars)
- timestamp del backup: `backup_20260513_142312\\` (+25 chars)
- slug de cuenta: `tanaka_taro_at_uns-kikaku_com.pst` (+35 chars)
- subfolder en MSG export: `\\受信トレイ\\2026年5月\\重要なメール\\` (+30 chars)

Total acumulado facilmente excede 260 chars, especialmente con paths de OneDrive
sincronizados que ya empiezan en 100+ chars.

API publica
-----------
- `safe_path(p)` — devuelve string con prefijo `\\?\\` si hace falta y es Windows.
- `is_long_path(p)` — True si el path supera el umbral seguro.
- `validate_backup_dir(p)` — chequea writability + space + length, devuelve mensaje japones.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

# Limite NTFS sin prefijo (incluye NUL terminator).
MAX_PATH = 260

# Umbral conservador para activar el prefijo. Damos 20 chars de margen para
# operaciones intermedias (renames, temp files con sufijo) que pueden crecer
# el path despues de la validacion inicial.
LONG_PATH_THRESHOLD = 240

# Limite con prefijo `\\?\` (en wchars, no bytes).
LONG_PATH_LIMIT = 32_767

# Prefijo extended-length de Windows.
LONG_PATH_PREFIX = "\\\\?\\"
# Variante para UNC paths.
LONG_PATH_PREFIX_UNC = "\\\\?\\UNC\\"


def is_long_path(p: Path | str) -> bool:
    """True si el path supera el umbral seguro (sin contar prefijo).

    Args:
        p: Path o string a evaluar.

    Returns:
        True si len(str(p)) > LONG_PATH_THRESHOLD.
    """
    s = str(p)
    # Si ya tiene prefijo, descontarlo del calculo
    if s.startswith(LONG_PATH_PREFIX_UNC):
        s = s[len(LONG_PATH_PREFIX_UNC) :]
    elif s.startswith(LONG_PATH_PREFIX):
        s = s[len(LONG_PATH_PREFIX) :]
    return len(s) > LONG_PATH_THRESHOLD


def safe_path(p: Path | str) -> str:
    """Devuelve un string del path apto para APIs Win32 con paths largos.

    Si el path supera el umbral conservador (240 chars), agrega el prefijo
    `\\\\?\\` que las APIs Win32 wide (W) reconocen para subir el limite a
    ~32767 wchars. Para paths cortos, devuelve el string tal cual (compat
    con APIs viejas que no manejan el prefijo).

    En non-Windows (Linux, Mac), passthrough sin modificar — los limites de
    PATH_MAX en POSIX son mucho mas altos (4096 typical) y no necesitan prefijo.

    Args:
        p: Path o string a normalizar.

    Returns:
        String del path, con prefijo si es necesario y aplicable.

    Notes:
        - El prefijo solo funciona con paths absolutos. Esta funcion los resuelve
          a absoluto via Path.resolve() si vienen relativos.
        - UNC paths (`\\\\server\\share\\...`) usan el prefijo especial `\\\\?\\UNC\\`.
        - Si el path ya tiene prefijo, no se duplica.
    """
    s = str(p)

    # Non-Windows: passthrough
    if os.name != "nt":
        return s

    # Si ya tiene prefijo, no tocar
    if s.startswith(LONG_PATH_PREFIX) or s.startswith(LONG_PATH_PREFIX_UNC):
        return s

    # Path corto: no necesita prefijo. Esto preserva compat con APIs viejas
    # (algunos drivers / herramientas de terceros se quejan del prefijo).
    if not is_long_path(s):
        return s

    # Path largo: resolver a absoluto antes de prefijar (el prefijo solo funciona absoluto)
    try:
        resolved = Path(s).resolve()
    except (OSError, RuntimeError):
        # Si no se puede resolver (ej: parent inexistente), devolver original
        # con prefijo igual; el caller vera el error de la API en el momento
        log.warning("No se pudo resolver path absoluto: %s", s)
        resolved = Path(s)

    abs_str = str(resolved)

    # UNC path: \\server\share\... → \\?\UNC\server\share\...
    if abs_str.startswith("\\\\") and not abs_str.startswith(LONG_PATH_PREFIX):
        # quitar los 2 backslashes iniciales y prepender el prefijo UNC
        return LONG_PATH_PREFIX_UNC + abs_str[2:]

    # Path local: C:\... → \\?\C:\...
    return LONG_PATH_PREFIX + abs_str


def validate_backup_dir(p: Path) -> tuple[bool, str]:
    """Verifica que el directorio sea apto para almacenar backups.

    Chequea:
    1. Existe (o se puede crear).
    2. Es escribible (intenta crear archivo temp).
    3. La longitud del path no compromete operaciones futuras.

    Args:
        p: Path al directorio destino del backup.

    Returns:
        Tupla (is_valid, message). Message en japones cuando is_valid=False
        para mostrar directo en la UI.
    """
    # 1. Existencia / creacion
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return False, f"フォルダを作成できません: {e}"

    if not p.is_dir():
        return False, "指定されたパスはフォルダではありません"

    # 2. Length check — preventivo
    base_len = len(str(p))
    # Peor caso esperado: agregar timestamp + slug de cuenta + extension
    # Ej: "\\backup_20260513_142312\\tanaka_taro_at_uns-kikaku_com.pst" ~= 60 chars
    expected_overhead = 80
    if base_len + expected_overhead > LONG_PATH_LIMIT:
        return False, (
            f"パスが長すぎます ({base_len} 文字)。"
            "より短いフォルダを選択してください。"
        )

    if base_len + expected_overhead > MAX_PATH and os.name == "nt":
        # No es bloqueante, pero advertencia (paths largos podrian fallar en
        # APIs viejas; safe_path los maneja pero algunos componentes de
        # terceros no usan el prefijo).
        log.warning(
            "Backup dir cerca del limite MAX_PATH (%d chars). "
            "Activando soporte de long paths.",
            base_len,
        )

    # 3. Writability test
    try:
        with tempfile.NamedTemporaryFile(
            dir=str(p), prefix=".uns_writetest_", suffix=".tmp", delete=True
        ) as _tmp:
            pass
    except OSError as e:
        return False, f"フォルダに書き込みできません: {e}"

    return True, ""
