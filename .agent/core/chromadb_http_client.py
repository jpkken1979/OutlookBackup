#!/usr/bin/env python3
"""
Minimal ChromaDB HTTP client for Python 3.14+ compatibility.

The official chromadb package uses pydantic v1 internally which is
incompatible with Python 3.14. This module provides the same interface
used by VectorMemory but talks directly to the ChromaDB REST API (v2).

Supports ChromaDB 0.6.x HTTP API.
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger("antigravity.chromadb_http")

DEFAULT_TENANT = "default_tenant"
DEFAULT_DATABASE = "default_database"


class ChromaHttpCollection:
    """Minimal ChromaDB collection interface via HTTP."""

    def __init__(self, client: "ChromaHttpClient", collection_id: str, name: str):
        self._client = client
        self._id = collection_id
        self.name = name

    def _base(self) -> str:
        return (
            f"{self._client._base_url}/api/v2/tenants/{self._client.tenant}"
            f"/databases/{self._client.database}/collections/{self._id}"
        )

    def add(
        self,
        documents: list[str],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
        embeddings: list[list[float]] | None = None,
    ) -> None:
        payload: dict[str, Any] = {"documents": documents}
        if ids:
            payload["ids"] = ids
        if metadatas:
            payload["metadatas"] = metadatas
        if embeddings:
            payload["embeddings"] = embeddings
        self._client._post(f"{self._base()}/add", payload)

    def query(
        self,
        query_texts: list[str] | None = None,
        query_embeddings: list[list[float]] | None = None,
        n_results: int = 10,
        where: dict | None = None,
        include: list[str] | None = None,
    ) -> dict:
        payload: dict[str, Any] = {"n_results": n_results}
        if query_texts:
            payload["query_texts"] = query_texts
        if query_embeddings:
            payload["query_embeddings"] = query_embeddings
        if where:
            payload["where"] = where
        if include:
            payload["include"] = include
        return self._client._post(f"{self._base()}/query", payload)  # type: ignore[return-value]  # HTTP response parsed at runtime

    def get(
        self,
        ids: list[str] | None = None,
        where: dict | None = None,
        include: list[str] | None = None,
    ) -> dict:
        payload: dict[str, Any] = {}
        if ids:
            payload["ids"] = ids
        if where:
            payload["where"] = where
        if include:
            payload["include"] = include
        return self._client._post(f"{self._base()}/get", payload)  # type: ignore[return-value]  # HTTP response parsed at runtime

    def delete(self, ids: list[str] | None = None, where: dict | None = None) -> None:
        payload: dict[str, Any] = {}
        if ids:
            payload["ids"] = ids
        if where:
            payload["where"] = where
        self._client._post(f"{self._base()}/delete", payload)

    def count(self) -> int:
        result = self._client._get(f"{self._base()}/count")
        return int(result) if result is not None else 0


class ChromaHttpClient:
    """
    Minimal ChromaDB HTTP client.

    Usage:
        client = ChromaHttpClient(host="localhost", port=8000)
        col = client.get_or_create_collection("my_collection")
        col.add(documents=["hello world"], ids=["1"])
        results = col.query(query_texts=["hello"], n_results=3)
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8000,
        tenant: str = DEFAULT_TENANT,
        database: str = DEFAULT_DATABASE,
        timeout: int = 30,
    ):
        self._base_url = f"http://{host}:{port}"
        self.tenant = tenant
        self.database = database
        self.timeout = timeout

        # Ensure tenant and database exist
        self._ensure_tenant_database()
        logger.debug("ChromaHttpClient connected to %s", self._base_url)

    def _ensure_tenant_database(self) -> None:
        """Create tenant and database if they don't exist."""
        try:
            self._get(f"/api/v2/tenants/{self.tenant}")
        except Exception as _e:
            try:
                self._post("/api/v2/tenants", {"name": self.tenant})
            except Exception as _ex:
                logger.debug("Failed to create tenant: %s (optional module)", _ex)

        try:
            self._get(f"/api/v2/tenants/{self.tenant}/databases/{self.database}")
        except Exception as _e:
            try:
                self._post(
                    f"/api/v2/tenants/{self.tenant}/databases",
                    {"name": self.database},
                )
            except Exception as _ex:
                logger.debug("Failed to create database: %s (optional module)", _ex)

    def _collections_base(self) -> str:
        return f"/api/v2/tenants/{self.tenant}/databases/{self.database}/collections"

    def _get(self, path: str) -> Any:
        url = self._base_url + path if path.startswith("/") else path
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # nosec B310 — URL proviene de configuración interna del cliente ChromaDB
            return json.loads(resp.read().decode())

    def _post(self, path: str, payload: dict) -> Any:
        url = self._base_url + path if path.startswith("/") else path
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # nosec B310 — URL proviene de configuración interna del cliente ChromaDB
                body = resp.read()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            logger.warning("ChromaDB HTTP %s %s: %s", exc.code, url, body)
            raise

    def heartbeat(self) -> dict:
        return self._get("/api/v2/heartbeat")  # type: ignore[return-value]  # HTTP response parsed at runtime

    def list_collections(self) -> list[dict]:
        return self._get(self._collections_base()) or []  # type: ignore[return-value]  # HTTP response parsed at runtime

    def get_or_create_collection(
        self, name: str, metadata: dict | None = None
    ) -> ChromaHttpCollection:
        """Get existing collection or create it."""
        # Try to find existing
        collections = self.list_collections()
        for col in collections:
            if col.get("name") == name:
                return ChromaHttpCollection(self, col["id"], name)

        # Create new
        payload: dict[str, Any] = {"name": name}
        if metadata:
            payload["metadata"] = metadata
        result = self._post(self._collections_base(), payload)
        return ChromaHttpCollection(self, result["id"], name)

    def delete_collection(self, name: str) -> None:
        collections = self.list_collections()
        for col in collections:
            if col.get("name") == name:
                self._post(f"{self._collections_base()}/{col['id']}/delete", {})
                break
