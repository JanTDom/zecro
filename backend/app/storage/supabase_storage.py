import os
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse
from ..config import settings

_client = None


def storage_reference(storage_path: str, bucket: Optional[str] = None) -> str:
    """Return a durable, non-public reference stored in database columns."""
    b_name = bucket or settings.supabase_storage_bucket
    key = str(storage_path).lstrip("/")
    if key.startswith(f"{b_name}/"):
        key = key[len(b_name) + 1:]
    return f"supabase://{b_name}/{key}"


def parse_storage_reference(value: str, bucket: Optional[str] = None) -> Optional[tuple[str, str]]:
    """Parse internal refs and public Supabase object URLs.

    Old rows contain absolute local paths.  Those intentionally return None so
    callers can decide whether a basename lookup is safe for their resource.
    """
    if not value:
        return None
    raw = str(value)
    if raw.startswith(("supabase://", "storage://")):
        parsed = urlparse(raw.replace("storage://", "supabase://", 1))
        if parsed.netloc and parsed.path.strip("/"):
            return unquote(parsed.netloc), unquote(parsed.path.strip("/"))
        return None
    marker = "/storage/v1/object/"
    if marker in raw:
        parsed = urlparse(raw)
        path = parsed.path.split(marker, 1)[1].lstrip("/")
        if path.startswith("public/"):
            path = path[len("public/"):]
        if "/" in path:
            b_name, key = path.split("/", 1)
            return unquote(b_name), unquote(key)
    if raw.startswith("uploads/") or raw.startswith("exports/"):
        return bucket or settings.supabase_storage_bucket, raw
    return None

def get_supabase_client():
    global _client
    if _client is not None:
        return _client
    if settings.supabase_url and (settings.supabase_service_role_key or settings.supabase_anon_key):
        from supabase import create_client
        key = settings.supabase_service_role_key or settings.supabase_anon_key
        _client = create_client(settings.supabase_url, key)
    return _client

def upload_to_storage(local_path: Path, storage_path: str, bucket: Optional[str] = None) -> Optional[str]:
    """Upload a local file and return a durable internal storage reference."""
    sb = get_supabase_client()
    if not sb or not local_path.exists():
        return None
    b_name = bucket or settings.supabase_storage_bucket
    try:
        with open(local_path, "rb") as fp:
            sb.storage.from_(b_name).upload(storage_path, fp.read(), {"upsert": "true"})
        return storage_reference(storage_path, b_name)
    except Exception:
        return None

def download_from_storage(storage_path: str, target_local_path: Path, bucket: Optional[str] = None) -> bool:
    """Downloads an object from Supabase Storage to a target local path."""
    sb = get_supabase_client()
    if not sb:
        return False
    parsed = parse_storage_reference(storage_path, bucket)
    if parsed:
        b_name, storage_path = parsed
    else:
        b_name = bucket or settings.supabase_storage_bucket
    try:
        data = sb.storage.from_(b_name).download(storage_path)
        target_local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_local_path, "wb") as fp:
            fp.write(data)
        return True
    except Exception:
        return False


def download_bytes_from_storage(storage_path: str, bucket: Optional[str] = None) -> Optional[bytes]:
    """Read an object without requiring a durable local filesystem."""
    sb = get_supabase_client()
    if not sb:
        return None
    parsed = parse_storage_reference(storage_path, bucket)
    if parsed:
        b_name, key = parsed
    else:
        b_name, key = bucket or settings.supabase_storage_bucket, str(storage_path).lstrip("/")
    try:
        return bytes(sb.storage.from_(b_name).download(key))
    except Exception:
        return None

def get_storage_public_url(storage_path: str, bucket: Optional[str] = None) -> str:
    parsed = parse_storage_reference(storage_path, bucket)
    if parsed:
        b_name, key = parsed
    else:
        b_name, key = bucket or settings.supabase_storage_bucket, str(storage_path).lstrip("/")
    return f"{settings.supabase_url}/storage/v1/object/public/{b_name}/{key}"
