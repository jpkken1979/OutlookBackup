"""Portable bundle v2 staging, atomic install, repair and rollback."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from .constants import (
    ANTIGRAVITY_FILES,
    CLAUDE_DIRS,
    ECOSYSTEM_VERSION,
    PORTABLE_AGENT_DIRS,
    ROOT_RULE_FILES,
    RULES_EXCLUDE,
    SKIP_TREE_NAMES,
    SKIP_TREE_PREFIXES,
)

INSTALL_SCHEMA_VERSION = 2
INSTALL_MANIFEST = Path(".antigravity/install.json")
_INSTALL_LOCKS: dict[str, threading.RLock] = {}
_INSTALL_LOCKS_GUARD = threading.Lock()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _io_path(path: Path) -> Path:
    """Return a Windows extended-length path for filesystem operations."""

    if os.name != "nt":
        return path
    value = str(path.resolve())
    if value.startswith("\\\\?\\"):
        return Path(value)
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value[2:])
    return Path("\\\\?\\" + value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with _io_path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write(path: Path, content: bytes) -> None:
    io_path = _io_path(path)
    io_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=io_path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(_io_path(temporary), io_path)


def _install_lock(target_dir: Path) -> threading.RLock:
    key = os.path.normcase(str(target_dir.resolve()))
    with _INSTALL_LOCKS_GUARD:
        return _INSTALL_LOCKS.setdefault(key, threading.RLock())


def _should_skip(path: Path) -> bool:
    name = path.name
    return (
        name in SKIP_TREE_NAMES
        or name.startswith(SKIP_TREE_PREFIXES)
        or name.endswith((".pyc", ".pyo", ".log", ".tmp"))
    )


def _iter_tree(source: Path, destination_prefix: Path) -> Iterator[tuple[Path, Path]]:
    if not source.exists():
        return
    if source.is_file():
        if not _should_skip(source):
            yield source, destination_prefix
        return
    for child in sorted(source.iterdir(), key=lambda item: item.name.lower()):
        if _should_skip(child):
            continue
        relative = destination_prefix / child.name
        if child.is_dir():
            yield from _iter_tree(child, relative)
        else:
            yield child, relative


def iter_bundle_files(
    repo_root: Path,
    *,
    runtime_root: Path | None = None,
) -> Iterator[tuple[Path, Path]]:
    """Yield source/destination pairs without memory, secrets or build junk."""

    for dirname in PORTABLE_AGENT_DIRS:
        yield from _iter_tree(
            repo_root / ".agent" / dirname,
            Path(".agent") / dirname,
        )
    yield from _iter_tree(repo_root / ".agent" / "VERSION", Path(".agent/VERSION"))
    yield from _iter_tree(repo_root / "mcp-server", Path("mcp-server"))

    for dirname in CLAUDE_DIRS:
        source = repo_root / ".claude" / dirname
        for source_path, relative in _iter_tree(source, Path(".claude") / dirname):
            if dirname == "rules" and source_path.name in RULES_EXCLUDE:
                continue
            yield source_path, relative

    yield from _iter_tree(repo_root / ".context", Path(".context"))
    for filename in ANTIGRAVITY_FILES:
        yield from _iter_tree(
            repo_root / ".antigravity" / filename,
            Path(".antigravity") / filename,
        )
    for filename in ROOT_RULE_FILES:
        yield from _iter_tree(repo_root / filename, Path(filename))
    if runtime_root is not None:
        yield from _iter_tree(
            runtime_root,
            Path(".antigravity") / "runtime" / "current",
        )


def _source_index(
    repo_root: Path,
    *,
    runtime_root: Path | None = None,
) -> dict[str, tuple[Path, str]]:
    index: dict[str, tuple[Path, str]] = {}
    for source, relative in iter_bundle_files(repo_root, runtime_root=runtime_root):
        normalized = relative.as_posix()
        index[normalized] = (source, _sha256(source))
    return index


def _bundle_digest(index: dict[str, tuple[Path, str]]) -> str:
    digest = hashlib.sha256()
    for relative, (_, file_hash) in sorted(index.items()):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


@dataclass(slots=True)
class InstallManifestV2:
    schema_version: int
    bundle_version: str
    bundle_digest: str
    installed_at: str
    install_id: str
    managed_files: dict[str, str]
    overlay_files: list[str] = field(default_factory=list)
    clients: list[str] = field(default_factory=list)
    feature_flags: dict[str, bool] = field(
        default_factory=lambda: {"mcpBrokerV2": True}
    )
    previous_install_id: str | None = None
    backup_dir: str | None = None


def read_install_manifest(target_dir: Path) -> InstallManifestV2 | None:
    path = target_dir / INSTALL_MANIFEST
    io_path = _io_path(path)
    if not io_path.is_file():
        return None
    try:
        payload = json.loads(io_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != INSTALL_SCHEMA_VERSION:
            return None
        return InstallManifestV2(**payload)
    except (OSError, ValueError, TypeError):
        return None


def analyze_source_install(repo_root: Path, target_dir: Path) -> dict[str, Any]:
    index = _source_index(repo_root)
    return _analyze_index(index, target_dir)


def _analyze_index(
    index: dict[str, tuple[Path, str]],
    target_dir: Path,
) -> dict[str, Any]:
    previous = read_install_manifest(target_dir)
    changes = {"create": [], "update": [], "repair": [], "remove": [], "preserve": []}
    for relative, (_, expected_hash) in index.items():
        destination = target_dir / relative
        io_destination = _io_path(destination)
        if not io_destination.exists():
            changes["create"].append(relative)
            continue
        if not io_destination.is_file() or _sha256(destination) != expected_hash:
            if relative.startswith(".agent/skills-custom/"):
                changes["preserve"].append(relative)
            elif previous and relative in previous.managed_files:
                changes["repair"].append(relative)
            else:
                changes["update"].append(relative)
    if previous:
        changes["remove"] = sorted(set(previous.managed_files) - set(index))
    return {
        "schema_version": INSTALL_SCHEMA_VERSION,
        "bundle_version": ECOSYSTEM_VERSION,
        "bundle_digest": _bundle_digest(index),
        "file_count": len(index),
        "changes": {name: sorted(paths) for name, paths in changes.items()},
        "change_count": sum(
            len(changes[name]) for name in ("create", "update", "repair", "remove")
        ),
    }


def install_from_source(
    repo_root: Path,
    target_dir: Path,
    *,
    clients: list[str] | None = None,
) -> dict[str, Any]:
    """Stage clean files, then atomically replace only managed paths."""

    repo_root = repo_root.resolve()
    return _install_index(
        _source_index(repo_root),
        target_dir,
        clients=clients,
    )


def _install_index(
    index: dict[str, tuple[Path, str]],
    target_dir: Path,
    *,
    clients: list[str] | None = None,
) -> dict[str, Any]:
    """Install an already verified file index transactionally."""

    target_dir = target_dir.resolve()
    with _install_lock(target_dir):
        digest = _bundle_digest(index)
        previous = read_install_manifest(target_dir)
        analysis = _analyze_index(index, target_dir)
        actionable = sum(
            len(analysis["changes"][key])
            for key in ("create", "update", "repair", "remove")
        )
        if (
            actionable == 0
            and previous is not None
            and previous.bundle_digest == digest
            and previous.clients == sorted(clients or previous.clients)
        ):
            return {
                "changed": False,
                "change_count": 0,
                "manifest": asdict(previous),
                "analysis": analysis,
            }

        install_id = f"ins_{uuid.uuid4().hex[:12]}"
        # A short sibling staging path avoids adding a large nested prefix to
        # every target file on Windows.
        staging_root = target_dir.parent / f".ag-stage-{uuid.uuid4().hex[:8]}"
        backup_root = target_dir / ".antigravity" / "backups" / install_id
        _io_path(staging_root).mkdir(parents=True, exist_ok=False)
        backup_records: dict[str, dict[str, Any]] = {}

        try:
            changed_paths = (
                analysis["changes"]["create"]
                + analysis["changes"]["update"]
                + analysis["changes"]["repair"]
            )
            for relative in changed_paths:
                source = index[relative][0]
                staged = staging_root / relative
                _io_path(staged).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(_io_path(source), _io_path(staged))

            for relative in analysis["changes"]["remove"]:
                destination = target_dir / relative
                if not _io_path(destination).exists():
                    continue
                backup = backup_root / "files" / relative
                _io_path(backup).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(_io_path(destination), _io_path(backup))
                backup_records[relative] = {"existed": True}
                _io_path(destination).unlink()

            overlay_paths = set(analysis["changes"]["preserve"])
            for relative in changed_paths:
                destination = target_dir / relative
                existed = _io_path(destination).is_file()
                if existed:
                    backup = backup_root / "files" / relative
                    _io_path(backup).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(_io_path(destination), _io_path(backup))
                backup_records[relative] = {"existed": existed}
                _io_path(destination).parent.mkdir(parents=True, exist_ok=True)
                os.replace(_io_path(staging_root / relative), _io_path(destination))

            previous_manifest_path = target_dir / INSTALL_MANIFEST
            previous_manifest_bytes = (
                _io_path(previous_manifest_path).read_bytes()
                if _io_path(previous_manifest_path).is_file()
                else None
            )
            if backup_records or previous_manifest_bytes is not None:
                _io_path(backup_root).mkdir(parents=True, exist_ok=True)
                rollback_metadata = {
                    "schema_version": INSTALL_SCHEMA_VERSION,
                    "files": backup_records,
                    "previous_manifest_present": previous_manifest_bytes is not None,
                }
                _atomic_write(
                    backup_root / "rollback.json",
                    json.dumps(rollback_metadata, indent=2, sort_keys=True).encode("utf-8"),
                )
                if previous_manifest_bytes is not None:
                    _atomic_write(
                        backup_root / "previous-install.json",
                        previous_manifest_bytes,
                    )

            manifest = InstallManifestV2(
                schema_version=INSTALL_SCHEMA_VERSION,
                bundle_version=ECOSYSTEM_VERSION,
                bundle_digest=digest,
                installed_at=_utc_now(),
                install_id=install_id,
                managed_files={
                    relative: file_hash
                    for relative, (_, file_hash) in index.items()
                    if relative not in overlay_paths
                },
                overlay_files=sorted(
                    {
                        relative
                        for relative in index
                        if relative.startswith(".agent/skills-custom/")
                    }
                ),
                clients=sorted(clients or []),
                feature_flags={"mcpBrokerV2": True},
                previous_install_id=previous.install_id if previous else None,
                backup_dir=(
                    backup_root.relative_to(target_dir).as_posix()
                    if _io_path(backup_root).exists()
                    else None
                ),
            )
            _atomic_write(
                target_dir / INSTALL_MANIFEST,
                json.dumps(asdict(manifest), indent=2, sort_keys=True).encode("utf-8"),
            )
            return {
                "changed": True,
                "change_count": actionable,
                "manifest": asdict(manifest),
                "analysis": analysis,
            }
        finally:
            shutil.rmtree(_io_path(staging_root), ignore_errors=True)


def repair_from_source(repo_root: Path, target_dir: Path) -> dict[str, Any]:
    previous = read_install_manifest(target_dir)
    return install_from_source(
        repo_root,
        target_dir,
        clients=previous.clients if previous else [],
    )


def _archive_file_index(root: Path) -> dict[str, tuple[Path, str]]:
    return {
        path.relative_to(root).as_posix(): (path, _sha256(path))
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def install_from_archive(
    archive_path: Path,
    signature_path: Path,
    target_dir: Path,
    *,
    trusted_public_key_b64: str | None = None,
    clients: list[str] | None = None,
) -> dict[str, Any]:
    """Verify and securely install a signed platform ``tar.zst`` bundle."""

    try:
        import zstandard
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise RuntimeError("Bundle installation requires zstandard and cryptography") from exc

    archive_path = archive_path.resolve()
    signature_path = signature_path.resolve()
    signature = json.loads(signature_path.read_text(encoding="utf-8"))
    trusted = trusted_public_key_b64 or os.environ.get("ANTIGRAVITY_BUNDLE_PUBLIC_KEY", "")
    if not trusted:
        raise RuntimeError("A trusted bundle public key is required")
    if not isinstance(signature, dict) or signature.get("public_key") != trusted:
        raise RuntimeError("Bundle signer is not trusted")
    archive_digest = _sha256(archive_path)
    if signature.get("sha256") != archive_digest:
        raise RuntimeError("Bundle digest mismatch")
    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(trusted))
        public_key.verify(
            base64.b64decode(str(signature["signature"])),
            bytes.fromhex(archive_digest),
        )
    except (InvalidSignature, ValueError, KeyError) as exc:
        raise RuntimeError("Bundle signature verification failed") from exc

    with tempfile.TemporaryDirectory(prefix="antigravity-bundle-") as temporary:
        extraction_root = Path(temporary) / "bundle"
        extraction_root.mkdir()
        tar_path = Path(temporary) / "bundle.tar"
        with archive_path.open("rb") as compressed, tar_path.open("wb") as uncompressed:
            zstandard.ZstdDecompressor().copy_stream(compressed, uncompressed)
        with tarfile.open(tar_path, "r:") as archive:
            for member in archive.getmembers():
                member_path = Path(member.name)
                if (
                    member_path.is_absolute()
                    or ".." in member_path.parts
                    or member.issym()
                    or member.islnk()
                    or not member.isfile()
                ):
                    raise RuntimeError("Bundle contains an unsafe archive member")
                destination = (extraction_root / member_path).resolve()
                if extraction_root.resolve() not in destination.parents:
                    raise RuntimeError("Bundle member escapes extraction root")
                destination.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise RuntimeError("Bundle member could not be read")
                with source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output)

        runtime_manifest = (
            extraction_root
            / ".antigravity"
            / "runtime"
            / "current"
            / "runtime-manifest.json"
        )
        if runtime_manifest.is_file():
            from .portable_build import platform_tag

            runtime = json.loads(runtime_manifest.read_text(encoding="utf-8"))
            if runtime.get("platform") != platform_tag():
                raise RuntimeError("Bundle platform does not match this machine")
        result = _install_index(
            _archive_file_index(extraction_root),
            target_dir,
            clients=clients,
        )
        result["signature_verified"] = True
        result["archive_sha256"] = archive_digest
        return result


def rollback(target_dir: Path) -> dict[str, Any]:
    """Restore the exact bytes replaced by the current installation."""

    target_dir = target_dir.resolve()
    with _install_lock(target_dir):
        current = read_install_manifest(target_dir)
        if current is None or not current.backup_dir:
            raise RuntimeError("No recoverable previous installation")
        backup_root = target_dir / current.backup_dir
        metadata = json.loads(
            _io_path(backup_root / "rollback.json").read_text(encoding="utf-8")
        )
        restored = 0
        removed = 0
        for relative, record in metadata["files"].items():
            destination = target_dir / relative
            if record["existed"]:
                backup = backup_root / "files" / relative
                _atomic_write(destination, _io_path(backup).read_bytes())
                restored += 1
            elif _io_path(destination).exists():
                _io_path(destination).unlink()
                removed += 1

        manifest_path = target_dir / INSTALL_MANIFEST
        previous_manifest = backup_root / "previous-install.json"
        if metadata.get("previous_manifest_present") and _io_path(previous_manifest).is_file():
            _atomic_write(manifest_path, _io_path(previous_manifest).read_bytes())
        elif _io_path(manifest_path).exists():
            _io_path(manifest_path).unlink()
        return {"restored": restored, "removed": removed, "install_id": current.install_id}


def build_tar_zst(
    repo_root: Path,
    output_path: Path,
    *,
    runtime_root: Path | None = None,
    signing_key_b64: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic tar.zst and Ed25519 signature sidecar."""

    try:
        import zstandard
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError as exc:
        raise RuntimeError("Bundle build requires zstandard and cryptography") from exc

    index = _source_index(
        repo_root.resolve(),
        runtime_root=runtime_root.resolve() if runtime_root else None,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_path.parent) as temporary_dir:
        tar_path = Path(temporary_dir) / "bundle.tar"
        with tarfile.open(tar_path, "w", format=tarfile.PAX_FORMAT) as archive:
            for relative, (source, _) in sorted(index.items()):
                info = archive.gettarinfo(str(source), arcname=relative)
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mtime = 0
                with source.open("rb") as handle:
                    archive.addfile(info, handle)
        compressor = zstandard.ZstdCompressor(level=19, threads=0)
        with tar_path.open("rb") as source, output_path.open("wb") as destination:
            compressor.copy_stream(source, destination)

    archive_digest = _sha256(output_path)
    signing_key_b64 = signing_key_b64 or os.environ.get("ANTIGRAVITY_BUNDLE_SIGNING_KEY")
    if not signing_key_b64:
        raise RuntimeError("ANTIGRAVITY_BUNDLE_SIGNING_KEY is required for signed bundles")
    private_key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(signing_key_b64))
    signature = private_key.sign(bytes.fromhex(archive_digest))
    public_key = private_key.public_key().public_bytes_raw()
    signature_payload = {
        "algorithm": "ed25519",
        "sha256": archive_digest,
        "signature": base64.b64encode(signature).decode("ascii"),
        "public_key": base64.b64encode(public_key).decode("ascii"),
        "bundle_version": ECOSYSTEM_VERSION,
        "file_count": len(index),
    }
    signature_path = output_path.with_suffix(output_path.suffix + ".sig.json")
    _atomic_write(
        signature_path,
        json.dumps(signature_payload, indent=2, sort_keys=True).encode("utf-8"),
    )
    return {
        "archive": str(output_path),
        "signature_path": str(signature_path),
        **signature_payload,
    }
