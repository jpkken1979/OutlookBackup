"""Local, versioned review store for Markdown plans.

The source document is read-only. Reviews live under
``~/.antigravity/plan-reviews`` and every mutation uses optimistic concurrency
plus an idempotency key.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

MAX_PLAN_BYTES = 2 * 1024 * 1024
VALID_DECISIONS = frozenset({"approved", "changes_requested", "skipped"})
_OPAQUE_ID = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


class PlanReviewError(ValueError):
    """Base error for safe API mapping."""


class InvalidPlanPath(PlanReviewError):
    """The requested plan is outside the allowlist or otherwise unsafe."""


class ReviewNotFound(PlanReviewError):
    """The review id is unknown."""


class RevisionConflict(PlanReviewError):
    """Another client updated the review first."""


class ContentChanged(PlanReviewError):
    """The source Markdown changed after this review was opened."""


class IdempotencyConflict(PlanReviewError):
    """An idempotency key was reused with a different operation payload."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return _sha256(encoded)


def _default_roots() -> dict[str, Path]:
    repo = Path(os.environ.get("ANTIGRAVITY_ROOT", Path(__file__).resolve().parents[2]))
    return {
        "plans": repo / "plans",
        "claude": repo / ".claude" / "planning",
    }


class PlanReviewStore:
    """Atomic store with two explicitly named, read-only source roots."""

    def __init__(
        self,
        *,
        roots: dict[str, Path] | None = None,
        storage_root: Path | None = None,
    ) -> None:
        configured = roots or _default_roots()
        if len(configured) != 2:
            raise ValueError("Plan Review requiere exactamente dos roots permitidos")
        self.roots = {name: path.resolve() for name, path in configured.items()}
        self.storage_root = (
            storage_root or Path.home() / ".antigravity" / "plan-reviews"
        ).resolve()
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    @staticmethod
    def valid_opaque_id(value: str) -> bool:
        return bool(_OPAQUE_ID.fullmatch(value))

    def list_reviews(self, workspace_id: str) -> list[dict[str, Any]]:
        self._root_for(workspace_id)
        reviews: list[dict[str, Any]] = []
        with self._lock:
            for path in self.storage_root.glob("review_*.json"):
                try:
                    review = self._read_path(path)
                except (OSError, json.JSONDecodeError, PlanReviewError):
                    continue
                if review["plan_ref"]["workspace_id"] == workspace_id:
                    reviews.append(self._public_review(review))
        return sorted(reviews, key=lambda review: review["updated_at"], reverse=True)

    def open_review(self, workspace_id: str, relative_path: str) -> dict[str, Any]:
        source, content = self._read_source(workspace_id, relative_path)
        content_hash = _sha256(content)
        normalized_path = source.relative_to(self._root_for(workspace_id)).as_posix()

        with self._lock:
            for review in self.list_reviews(workspace_id):
                plan_ref = review["plan_ref"]
                if (
                    plan_ref["relative_path"] == normalized_path
                    and plan_ref["content_sha256"] == content_hash
                ):
                    return self._public_review(review, content.decode("utf-8"))

            timestamp = _now()
            review = {
                "review_id": f"review_{uuid.uuid4().hex}",
                "revision": 1,
                "status": "open",
                "plan_ref": {
                    "workspace_id": workspace_id,
                    "relative_path": normalized_path,
                    "content_sha256": content_hash,
                },
                "annotations": [],
                "decision": None,
                "idempotency": {},
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            self._write(review)
            return self._public_review(review, content.decode("utf-8"))

    def get_review(self, review_id: str, *, include_content: bool = False) -> dict[str, Any]:
        review = self._load(review_id)
        if not include_content:
            return self._public_review(review)
        source, content = self._read_source(
            review["plan_ref"]["workspace_id"],
            review["plan_ref"]["relative_path"],
        )
        self._assert_source_unchanged(review, source, content)
        return self._public_review(review, content.decode("utf-8"))

    def add_annotation(
        self,
        review_id: str,
        *,
        expected_revision: int,
        idempotency_key: str,
        start_line: int,
        end_line: int,
        body: str,
        actor: str = "local-user",
    ) -> dict[str, Any]:
        clean_body = body.strip()
        if not clean_body or len(clean_body) > 4_000:
            raise PlanReviewError("La anotación debe tener entre 1 y 4000 caracteres")
        payload = {
            "operation": "annotation",
            "start_line": start_line,
            "end_line": end_line,
            "body": clean_body,
            "actor": actor,
        }
        with self._lock:
            review = self._load(review_id)
            if self._idempotent_retry(review, idempotency_key, payload):
                return self._public_review(review)
            self._assert_revision(review, expected_revision)
            source, content = self._review_source(review)
            self._assert_source_unchanged(review, source, content)
            line_count = max(1, len(content.decode("utf-8").splitlines()))
            if start_line < 1 or end_line < start_line or end_line > line_count:
                raise PlanReviewError("Rango de líneas inválido")

            timestamp = _now()
            review["annotations"].append(
                {
                    "annotation_id": f"annotation_{uuid.uuid4().hex}",
                    "start_line": start_line,
                    "end_line": end_line,
                    "body": clean_body,
                    "resolved": False,
                    "actor": actor,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
            )
            return self._public_review(self._commit(review, idempotency_key, payload))

    def resolve_annotation(
        self,
        review_id: str,
        annotation_id: str,
        *,
        expected_revision: int,
        idempotency_key: str,
        resolved: bool,
    ) -> dict[str, Any]:
        self._require_opaque_id(annotation_id, "anotación")
        payload = {
            "operation": "resolve_annotation",
            "annotation_id": annotation_id,
            "resolved": resolved,
        }
        with self._lock:
            review = self._load(review_id)
            if self._idempotent_retry(review, idempotency_key, payload):
                return self._public_review(review)
            self._assert_revision(review, expected_revision)
            self._assert_current_source(review)
            annotation = next(
                (item for item in review["annotations"] if item["annotation_id"] == annotation_id),
                None,
            )
            if annotation is None:
                raise ReviewNotFound("Anotación no encontrada")
            annotation["resolved"] = resolved
            annotation["updated_at"] = _now()
            return self._public_review(self._commit(review, idempotency_key, payload))

    def decide(
        self,
        review_id: str,
        *,
        expected_revision: int,
        idempotency_key: str,
        decision: str,
        actor: str = "local-user",
        summary: str = "",
    ) -> dict[str, Any]:
        if decision not in VALID_DECISIONS:
            raise PlanReviewError("Decisión inválida")
        clean_summary = summary.strip()
        if len(clean_summary) > 2_000:
            raise PlanReviewError("El resumen de decisión supera 2000 caracteres")
        payload = {
            "operation": "decision",
            "decision": decision,
            "actor": actor,
            "summary": clean_summary,
        }
        with self._lock:
            review = self._load(review_id)
            if self._idempotent_retry(review, idempotency_key, payload):
                return self._public_review(review)
            self._assert_revision(review, expected_revision)
            self._assert_current_source(review)
            timestamp = _now()
            review["status"] = decision
            review["decision"] = {
                "status": decision,
                "actor": actor,
                "summary": clean_summary,
                "decided_at": timestamp,
            }
            return self._public_review(self._commit(review, idempotency_key, payload))

    def _commit(
        self,
        review: dict[str, Any],
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self._require_opaque_id(idempotency_key, "idempotencia")
        review["revision"] += 1
        review["updated_at"] = _now()
        review["idempotency"][idempotency_key] = {
            "fingerprint": _fingerprint(payload),
            "revision": review["revision"],
        }
        self._write(review)
        return review

    @staticmethod
    def _public_review(review: dict[str, Any], content: str | None = None) -> dict[str, Any]:
        public = {key: value for key, value in review.items() if key != "idempotency"}
        if content is not None:
            public["content"] = content
        return public

    def _idempotent_retry(
        self,
        review: dict[str, Any],
        key: str,
        payload: dict[str, Any],
    ) -> bool:
        self._require_opaque_id(key, "idempotencia")
        previous = review["idempotency"].get(key)
        if previous is None:
            return False
        if previous["fingerprint"] != _fingerprint(payload):
            raise IdempotencyConflict("Clave de idempotencia reutilizada con otro payload")
        return True

    def _read_source(self, workspace_id: str, relative_path: str) -> tuple[Path, bytes]:
        root = self._root_for(workspace_id)
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise InvalidPlanPath("Ruta de plan vacía")
        posix = PurePosixPath(relative_path)
        windows = PureWindowsPath(relative_path)
        if posix.is_absolute() or windows.is_absolute() or windows.drive:
            raise InvalidPlanPath("La ruta debe ser relativa")
        if ".." in posix.parts or ".." in windows.parts:
            raise InvalidPlanPath("La ruta no puede contener '..'")
        if Path(relative_path).suffix.casefold() != ".md":
            raise InvalidPlanPath("Solo se permiten planes Markdown (.md)")

        source = (root / relative_path).resolve(strict=True)
        try:
            source.relative_to(root)
        except ValueError as exc:
            raise InvalidPlanPath("El plan está fuera del root permitido") from exc
        if not source.is_file():
            raise InvalidPlanPath("El plan no es un archivo")
        size = source.stat().st_size
        if size > MAX_PLAN_BYTES:
            raise InvalidPlanPath("El plan supera el límite de 2 MiB")
        try:
            content = source.read_bytes()
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidPlanPath("El plan debe ser UTF-8") from exc
        return source, content

    def _review_source(self, review: dict[str, Any]) -> tuple[Path, bytes]:
        plan_ref = review["plan_ref"]
        return self._read_source(plan_ref["workspace_id"], plan_ref["relative_path"])

    def _assert_current_source(self, review: dict[str, Any]) -> None:
        source, content = self._review_source(review)
        self._assert_source_unchanged(review, source, content)

    @staticmethod
    def _assert_source_unchanged(
        review: dict[str, Any],
        _source: Path,
        content: bytes,
    ) -> None:
        if _sha256(content) != review["plan_ref"]["content_sha256"]:
            raise ContentChanged("El plan cambió; abre una revisión nueva")

    def _root_for(self, workspace_id: str) -> Path:
        try:
            return self.roots[workspace_id]
        except KeyError as exc:
            raise InvalidPlanPath("Workspace de planes no permitido") from exc

    def _path_for(self, review_id: str) -> Path:
        self._require_opaque_id(review_id, "review")
        return self.storage_root / f"{review_id}.json"

    def _load(self, review_id: str) -> dict[str, Any]:
        path = self._path_for(review_id)
        if not path.is_file():
            raise ReviewNotFound("Review no encontrado")
        return self._read_path(path)

    @staticmethod
    def _read_path(path: Path) -> dict[str, Any]:
        review = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(review, dict) or not isinstance(review.get("revision"), int):
            raise PlanReviewError("Review persistido inválido")
        review.setdefault("annotations", [])
        review.setdefault("idempotency", {})
        return review

    def _write(self, review: dict[str, Any]) -> None:
        destination = self._path_for(review["review_id"])
        encoded = json.dumps(review, ensure_ascii=False, indent=2, sort_keys=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{review['review_id']}.",
            suffix=".tmp",
            dir=self.storage_root,
            text=True,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _assert_revision(review: dict[str, Any], expected: int) -> None:
        if review["revision"] != expected:
            raise RevisionConflict(
                f"Revisión esperada {expected}; revisión actual {review['revision']}"
            )

    @staticmethod
    def _require_opaque_id(value: str, label: str) -> None:
        if not isinstance(value, str) or not _OPAQUE_ID.fullmatch(value):
            raise PlanReviewError(f"Identificador de {label} inválido")


_store: PlanReviewStore | None = None


def get_plan_review_store() -> PlanReviewStore:
    """Return the process-wide store used by the gateway."""
    global _store
    if _store is None:
        _store = PlanReviewStore()
    return _store
