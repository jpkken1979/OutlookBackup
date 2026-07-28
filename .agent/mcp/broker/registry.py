"""Declarative connector catalog and permission classification."""

from __future__ import annotations

import fnmatch
import json
import os
import re
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

    def classify_operation(
        self,
        connector: ConnectorManifest,
        operation: str,
        arguments: dict[str, Any] | None = None,
    ) -> OperationClass:
        normalized = operation.strip().lower()
        if connector.id == "sqlite" and isinstance(arguments, dict):
            raw_sql = arguments.get("sql")
            if isinstance(raw_sql, str) and raw_sql.strip():
                sql_class = sql_operation_class(raw_sql)
                if sql_class == "read":
                    return OperationClass.READ
                if sql_class == "destructive":
                    return OperationClass.DESTRUCTIVE
                return OperationClass.WRITE
        for pattern in connector.scopes.destructive:
            if fnmatch.fnmatchcase(normalized, pattern.lower()):
                return OperationClass.DESTRUCTIVE
        for pattern in connector.scopes.write:
            if fnmatch.fnmatchcase(normalized, pattern.lower()):
                return OperationClass.WRITE
        for pattern in connector.scopes.read:
            if fnmatch.fnmatchcase(normalized, pattern.lower()):
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
