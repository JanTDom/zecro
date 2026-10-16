"""Private studio protection is enforced by the API, not only by the UI."""

import base64
import hashlib

from fastapi.testclient import TestClient

from backend.app import auth
from backend.app.main import app


def test_private_api_requires_login_and_preserves_session(monkeypatch):
    monkeypatch.setenv("ZECRO_ENFORCE_LOGIN", "1")
    monkeypatch.setattr(auth.settings, "secrets_key", "unit-test-signing-key")
    digest = base64.b64encode(hashlib.pbkdf2_hmac(
        "sha256", b"test-password", auth.PASSWORD_SALT, auth.PBKDF2_ITERATIONS, dklen=32
    )).decode("ascii")
    monkeypatch.setattr(auth, "PASSWORD_DIGESTS", frozenset({digest}))

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/projects").status_code == 401
        assert client.get("/auth/session").json() == {"authenticated": False}
        assert client.post("/auth/login", json={"password": "wrong"}).status_code == 401
        response = client.post("/auth/login", json={"password": "test-password"})
        assert response.status_code == 200
        assert "httponly" in response.headers["set-cookie"].lower()
        assert client.get("/auth/session").json() == {"authenticated": True}
        assert client.get("/projects").status_code == 200
        assert client.post("/auth/logout").status_code == 200
        assert client.get("/projects").status_code == 401


def test_signed_cookie_cannot_be_changed(monkeypatch):
    monkeypatch.setattr(auth.settings, "secrets_key", "unit-test-signing-key")
    token = auth._signed_session()
    assert auth.valid_session(token)
    assert not auth.valid_session(token + "x")
