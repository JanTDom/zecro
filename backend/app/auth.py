"""Server-side access gate for the private Zecro studio.

The browser never receives password verifiers or the signing key. A valid
password creates a short-lived, signed, HttpOnly session cookie.
"""

import base64
import hashlib
import hmac
import os
import secrets
import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from .config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
COOKIE_NAME = "zecro_session"
SESSION_TTL = 24 * 60 * 60
PBKDF2_ITERATIONS = 210_000
PASSWORD_SALT = base64.b64decode("emVjcm8tcHJpdmF0ZS1wcmV2aWV3LTIwMjY=")
# Existing access passwords continue to work. These verifiers belong only on
# the server; do not include them in the frontend bundle.
PASSWORD_DIGESTS = frozenset({
    "M6B/U/U/v+nKe9YhkgGuMsVY906vLkpYFJHNptdyR/4=",
    "G6dCk/Z3s73Sz3wCHwPpYsr3gLpGItmk9HWURmDcOOY=",
    "qijkHwwE+2dgkP7e+7qOD85KAUxgrzj/4yOF8wKB+ak=",
})


def enabled() -> bool:
    return os.getenv("VERCEL", "").lower() in {"1", "true", "yes", "on"} or os.getenv("ZECRO_ENFORCE_LOGIN", "").lower() in {"1", "true", "yes", "on"}


def _secret() -> bytes:
    if not settings.secrets_key:
        raise HTTPException(status_code=503, detail="Logowanie jest chwilowo niedostępne.")
    return settings.secrets_key.encode("utf-8")


def _signed_session() -> str:
    payload = f"v1.{int(time.time())}.{secrets.token_urlsafe(16)}"
    signature = hmac.new(_secret(), payload.encode("ascii"), hashlib.sha256).digest()
    return f"{payload}.{base64.urlsafe_b64encode(signature).decode('ascii').rstrip('=')}"


def valid_session(value: str | None) -> bool:
    if not value:
        return False
    try:
        version, issued, nonce, signature = value.split(".")
        issued_at = int(issued)
        now = int(time.time())
        if version != "v1" or not nonce or issued_at > now + 60 or now - issued_at > SESSION_TTL:
            return False
        payload = f"{version}.{issued}.{nonce}"
        expected = hmac.new(_secret(), payload.encode("ascii"), hashlib.sha256).digest()
        supplied = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        return hmac.compare_digest(supplied, expected)
    except (ValueError, UnicodeError, HTTPException):
        return False


def _cookie_domain(request: Request) -> str | None:
    host = request.url.hostname or ""
    return ".zecro.pl" if host == "zecro.pl" or host.endswith(".zecro.pl") else None


def _check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin not in settings.cors_origins and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(status_code=403, detail="Ta strona nie ma dostępu do studia.")


class LoginInput(BaseModel):
    password: str


@router.post("/login")
def login(data: LoginInput, request: Request, response: Response):
    _check_origin(request)
    if not enabled():
        return {"authenticated": True}
    digest = base64.b64encode(hashlib.pbkdf2_hmac(
        "sha256", data.password.encode("utf-8"), PASSWORD_SALT, PBKDF2_ITERATIONS, dklen=32
    )).decode("ascii")
    if not any(hmac.compare_digest(digest, known) for known in PASSWORD_DIGESTS):
        raise HTTPException(status_code=401, detail="Hasło nie pasuje. Spróbuj ponownie.")
    response.set_cookie(COOKIE_NAME, _signed_session(), secure=bool(os.getenv("VERCEL")) or request.url.scheme == "https",
                        httponly=True, samesite="lax", path="/", domain=_cookie_domain(request))
    return {"authenticated": True}


@router.get("/session")
def session(request: Request):
    if not enabled():
        return {"authenticated": True}
    return {"authenticated": valid_session(request.cookies.get(COOKIE_NAME))}


@router.post("/logout")
def logout(request: Request, response: Response):
    _check_origin(request)
    response.delete_cookie(COOKIE_NAME, path="/", domain=_cookie_domain(request))
    return {"authenticated": False}
