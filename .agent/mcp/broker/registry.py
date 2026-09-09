"""Declarative connector catalog and permission classification."""

from __future__ import annotations

import fnmatch
import json
import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .models import (
    ConnectorCatalogDocument,
    ConnectorManifest,
    ConnectorStatus,
    OperationClass,
)
from .internal import sql_operation_class

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _expand_environment(value: str) -> str:
    """Expand only explicit ``${NAME}`` references."""

    return _ENV_PATTERN.sub(lambda match: os.environ.get(match.group(1), match.group(0)), value)


class ConnectorRegistry:
    """Loads the reviewable registry without starting any connector process."""

    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path
        self._document = self._load()
        self._connectors = {item.id: item for item in self._document.connectors}

    def _load(self) -> ConnectorCatalogDocument:
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        document = ConnectorCatalogDocument.model_validate(payload)
        duplicate_ids = [
            connector_id
            for connector_id in {item.id for item in document.connectors}
            if sum(item.id == connector_id for item in document.connectors) > 1
        ]
        if duplicate_ids:
            raise ValueError(f"Duplicate connector ids: {', '.join(sorted(duplicate_ids))}")
        return document

    @property
    def schema_version(self) -> int:
        return self._document.schema_version

    def reload(self) -> None:
        self._document = self._load()
        self._connectors = {item.id: item for item in self._document.connectors}

    def list(self) -> list[ConnectorManifest]:
        return sorted(self._connectors.values(), key=lambda item: item.display_name.lower())

    def get(self, connector_id: str) -> ConnectorManifest | None:
        return self._connectors.get(connector_id)

    def required_secrets_missing(self, connector: ConnectorManifest) -> list[str]:
        return [name for name in connector.auth.required_env if not os.environ.get(name)]

    def status(self, connector: ConnectorManifest) -> ConnectorStatus:
        if connector.verification != "verified":
            return ConnectorStatus.UNVERIFIED
        if self.required_secrets_missing(connector):
            return ConnectorStatus.AUTH_REQUIRED
        if connector.transport.type == "managed":
            return ConnectorStatus.OFFLINE
        if connector.transport.type == "stdio":
            command = _expand_environment(connector.transport.command or "")
            if not command or "${" in command:
                return ConnectorStatus.OFFLINE
            if not Path(command).exists():
                return ConnectorStatus.OFFLINE
        return ConnectorStatus.CONFIGURED

    @staticmethod
    def _classify_sqlite_operation(arguments: dict[str, Any] | None) -> OperationClass | None:
        """Clasifica una operacion SQLite inspeccionando el SQL crudo si vino en los argumentos.

        Returns:
            La clase de operacion si se pudo inferir del SQL, o ``None`` si no aplica
            (no es SQLite, faltan argumentos o no hay sentencia SQL reconocible).
        """
        if not isinstance(arguments, dict):
            return None
        raw_sql = arguments.get("sql")
        if not isinstance(raw_sql, str) or not raw_sql.strip():
            return None
        sql_class = sql_operation_class(raw_sql)
        if sql_class == "read":
            return OperationClass.READ
        if sql_class == "destructive":
            return OperationClass.DESTRUCTIVE
        return OperationClass.WRITE

    @staticmethod
    def _match_scope(normalized: str, patterns: Sequence[str]) -> bool:
        # Sequence y no list: esta clase define un metodo `list`, que sombrea al
        # builtin dentro del scope de la clase — mypy resuelve la anotacion al
        # metodo. Ademas Sequence es lo correcto para un parametro que solo se itera.
        return any(fnmatch.fnmatchcase(normalized, pattern.lower()) for pattern in patterns)

    def classify_operation(
        self,
        connector: ConnectorManifest,
        operation: str,
        arguments: dict[str, Any] | None = None,
    ) -> OperationClass:
        normalized = operation.strip().lower()
        if connector.id == "sqlite":
            sqlite_class = self._classify_sqlite_operation(arguments)
            if sqlite_class is not None:
                return sqlite_class
        if self._match_scope(normalized, connector.scopes.destructive):
            return OperationClass.DESTRUCTIVE
        if self._match_scope(normalized, connector.scopes.write):
            return OperationClass.WRITE
        if self._match_scope(normalized, connector.scopes.read):
            return OperationClass.READ
        # Unknown operations are not assumed safe.
        return OperationClass.WRITE

    def transport_values(self, connector: ConnectorManifest) -> dict[str, Any]:
        """Resolve bundle variables only at launch time."""

        transport = connector.transport.model_dump()
        for key in ("url", "command", "cwd"):
            value = transport.get(key)
            if value:
                transport[key] = _expand_environment(value)
        transport["args"] = [_expand_environment(arg) for arg in transport.get("args", [])]
        return transport

    def safe_catalog(self) -> list[dict[str, Any]]:
        """Return public metadata with secret names but never secret values."""

        return [
            {
                "id": connector.id,
                "display_name": connector.display_name,
                "owner": connector.owner,
                "description": connector.description,
                "source_url": connector.source_url,
                "version": connector.version,
                "checksum": connector.checksum,
                "verification": connector.verification,
                "transport": connector.transport.type,
                "sandbox": connector.sandbox,
                "status": self.status(connector).value,
                "missing_secrets": self.required_secrets_missing(connector),
            }
            for connector in self.list()
        ]
