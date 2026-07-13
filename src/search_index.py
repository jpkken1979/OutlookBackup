"""Índice de búsqueda full-text sobre el historial de respaldos.

Feature B del plan v3.2.0 (docs/PLAN_HARDENING_WIN10_11.md).

La app no parsea PST (los copia como binarios crudos), así que "indexed search"
se refiere a buscar sobre los metadatos de los respaldos ya realizados: cuentas,
fechas, tamaños, estados, rutas de archivos PST y nombres de carpeta.

Implementación con SQLite FTS5 (Python stdlib, sin dependencias nuevas).

Uso:
    from search_index import SearchIndex

    idx = SearchIndex(index_path="UNS_Backup/search.db")
    idx.rebuild_from_history(history.list_backups())
    results = idx.search("kenji 2026-05", limit=20)

Diseño:
- Tabla FTS5 con columnas: name, accounts, start_time, status, pst_files, path.
- Columna "accounts" contiene los SMTP separados por espacio para que FTS tokenice.
- El PK externo (path del backup) permite abrir/inspeccionar el resultado desde la UI.
- `rebuild` es idempotente: borra y reconstruye desde cero. Útil después de backups.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS backups USING fts5(
    name,
    accounts,
    start_time,
    status,
    pst_files,
    path,
    accounts_count UNINDEXED,
    total_size_mb UNINDEXED,
    total_emails UNINDEXED,
    errors_count UNINDEXED,
    tokenize = 'unicode61'
);
"""


class SearchIndex:
    """Wrapper sobre SQLite FTS5 para buscar respaldos por metadatos."""

    def __init__(self, index_path: str | Path) -> None:
        self.index_path = Path(index_path)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.index_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> SearchIndex:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def rebuild_from_history(self, backups: list[dict[str, Any]]) -> int:
        """Reconstruye el índice desde una lista de backups (history.list_backups()).

        Borra el contenido previo y reinserta. Devuelve el número de documentos
        indexados. Es seguro llamarlo después de cada backup.
        """
        cur = self._conn.cursor()
        cur.execute("DELETE FROM backups")
        rows = [
            (
                b.get("name", ""),
                " ".join(self._extract_accounts(b)),
                b.get("start_time") or "",
                b.get("status") or "",
                " ".join(self._extract_pst_names(b)),
                b.get("path", ""),
                int(b.get("accounts_count", 0)),
                float(b.get("total_size_mb", 0)),
                int(b.get("total_emails", 0)),
                int(b.get("errors_count", 0)),
            )
            for b in backups
        ]
        cur.executemany(
            """INSERT INTO backups
               (name, accounts, start_time, status, pst_files, path,
                accounts_count, total_size_mb, total_emails, errors_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self._conn.commit()
        return len(rows)

    def search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """Busca respaldos por texto libre. Devuelve resultados ordenados por relevancia.

        El query usa sintaxis FTS5: "kenji 2026" OR frases. Columnas vacías en el
        resultado se rellenan con defaults para que la UI no crashee.
        """
        if not query.strip():
            return []
        # Sanitizar: FTS5 se ahoga con comillas sueltas.
        safe = self._sanitize_query(query)
        if not safe:
            return []
        cur = self._conn.cursor()
        cur.execute(
            """SELECT name, accounts, start_time, status, pst_files, path,
                      accounts_count, total_size_mb, total_emails, errors_count,
                      rank
               FROM backups
               WHERE backups MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (safe, limit),
        )
        return [self._row_to_dict(r) for r in cur.fetchall()]

    def count(self) -> int:
        cur = self._conn.cursor()
        cur.execute("SELECT COUNT(*) FROM backups")
        return int(cur.fetchone()[0])

    @staticmethod
    def _extract_accounts(backup: dict[str, Any]) -> list[str]:
        """SMTPs de las cuentas procesadas, si están en report.json."""
        accounts = backup.get("accounts_processed")
        if isinstance(accounts, list):
            return [str(a.get("smtp", a.get("email", ""))) for a in accounts if isinstance(a, dict)]
        return []

    @staticmethod
    def _extract_pst_names(backup: dict[str, Any]) -> list[str]:
        psts = backup.get("pst_files", [])
        if isinstance(psts, list):
            return [str(p.get("name", "")) for p in psts if isinstance(p, dict)]
        return []

    @staticmethod
    def _sanitize_query(query: str) -> str:
        """Construye un query FTS5 válido tokenizando por espacios y AND implícito.

        Ej: "kenji 2026-05 fallido" -> '"kenji" "2026-05" "fallido"'
        Así evitamos que paréntesis/comillas sueltas rompan el parser de FTS5.
        """
        tokens = [t for t in query.replace('"', " ").split() if t]
        return " ".join(f'"{t}"' for t in tokens)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "name": row["name"],
            "accounts": row["accounts"].split() if row["accounts"] else [],
            "start_time": row["start_time"],
            "status": row["status"],
            "pst_files": row["pst_files"].split() if row["pst_files"] else [],
            "path": row["path"],
            "accounts_count": row["accounts_count"],
            "total_size_mb": row["total_size_mb"],
            "total_emails": row["total_emails"],
            "errors_count": row["errors_count"],
            "rank": row["rank"],
        }
