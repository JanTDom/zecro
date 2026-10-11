"""Durable asset references for local and Supabase-backed deployments.

The database contains metadata, while PDFs/images/exports live in either the
local runtime directory or the configured Supabase Storage bucket.  Legacy
rows created before the storage migration still contain absolute local paths;
for generated corpus/export names we can resolve those rows by basename in the
matching Storage prefix without rewriting the database in place.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from ..config import settings
from .supabase_storage import download_from_storage, parse_storage_reference, storage_reference, upload_to_storage


def storage_configured() -> bool:
    return bool(settings.supabase_url and (settings.supabase_service_role_key or settings.supabase_anon_key))


def _basename(value: str) -> str:
    return Path(str(value).split("?", 1)[0]).name


def legacy_storage_key(value: str, prefix: str) -> Optional[str]:
    """Map a generated legacy local path to its Storage object key."""
    name = _basename(value)
    if not name or name in {".", "/"}:
        return None
    if prefix == "uploads" and (name.startswith("corpus_") or name.startswith("asset_")):
        return f"uploads/{name}"
    if prefix == "exports" and name.startswith("export_"):
        return f"exports/{name}"
    return None


def materialize_asset(reference: str, *, prefix: str, cache_dir: Path) -> Optional[Path]:
    """Return a readable local path, downloading a remote object on demand."""
    local = Path(reference).expanduser() if reference and not parse_storage_reference(reference) else None
    if local and local.is_file():
        return local
    parsed = parse_storage_reference(reference) if reference else None
    key = parsed[1] if parsed else legacy_storage_key(reference or "", prefix)
    if not key or not storage_configured():
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    # A key can include nested folders and two buckets can contain the same
    # basename.  Hash the complete remote reference to avoid cache collisions
    # and never let an untrusted Storage key escape the cache directory.
    bucket = parsed[0] if parsed else settings.supabase_storage_bucket
    remote_reference = storage_reference(key, bucket)
    cache_key = hashlib.sha256(remote_reference.encode("utf-8")).hexdigest()[:16]
    target = cache_dir / cache_key / _basename(key)
    if target.is_file() and target.stat().st_size > 0:
        return target
    if download_from_storage(remote_reference, target):
        return target
    return None


def persist_asset(local_path: Path, *, prefix: str, key: str) -> Optional[str]:
    """Upload an asset when configured, enforcing remote-only deployments."""
    remote = storage_configured()
    if remote:
        reference = upload_to_storage(local_path, f"{prefix}/{Path(key).name}")
        if reference:
            try:
                local_path.unlink(missing_ok=True)
            except OSError:
                pass
            return reference
    if settings.require_remote_storage:
        try:
            local_path.unlink(missing_ok=True)
        except OSError:
            pass
        return None
    return str(local_path)

