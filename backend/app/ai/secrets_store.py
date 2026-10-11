"""Server-side secret encryption shared by the settings API and AI runtime."""
from __future__ import annotations
import base64, hashlib
from typing import Optional
from ..config import settings


def fernet():
    if not settings.secrets_key:
        return None
    try:
        from cryptography.fernet import Fernet
        key = settings.secrets_key.encode()
        try:
            Fernet(key)
        except Exception:
            key = base64.urlsafe_b64encode(hashlib.sha256(key).digest())
        return Fernet(key)
    except Exception:
        return None


def encrypt(secret: str) -> Optional[str]:
    f = fernet()
    return f.encrypt(secret.encode()).decode() if f else None


def decrypt(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    f = fernet()
    if not f:
        return None
    try:
        return f.decrypt(token.encode()).decode()
    except Exception:
        return None


def mask(secret: Optional[str]) -> Optional[str]:
    if not secret:
        return None
    return secret[:5] + "…" + secret[-3:] if len(secret) > 8 else "••••••"
