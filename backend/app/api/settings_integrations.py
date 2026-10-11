"""Administrator-facing AI/source integration registry API."""
from __future__ import annotations
import base64, hashlib, ipaddress, json, socket, secrets
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from ..config import settings
from ..models.database import db
from ..ai.gemini_client import list_models, AIUnavailable

def _admin(x_zecro_admin_token: str | None = Header(default=None)) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=503, detail={"status":"unconfigured", "reason":"ZECRO_ADMIN_TOKEN is required for integration settings"})
    if not x_zecro_admin_token or not secrets.compare_digest(x_zecro_admin_token, settings.admin_token):
        raise HTTPException(status_code=403, detail="Administrator role required")

router = APIRouter(prefix="/settings", tags=["settings", "integrations"], dependencies=[Depends(_admin)])

class IntegrationPayload(BaseModel):
    kind: str = "other"
    provider: str = "custom"
    label: str = ""
    scope: str = "global"
    project_id: Optional[str] = None
    enabled: bool = True
    priority: int = 0
    config: dict[str, Any] = Field(default_factory=dict)
    api_key: Optional[str] = None
    secret: Optional[str] = None
    status: str = "unconfigured"


def _fernet():
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


def _mask(secret: str | None) -> str | None:
    if not secret: return None
    return secret[:5] + "…" + secret[-3:] if len(secret) > 8 else "••••••"


def _public(item: dict[str, Any]) -> dict[str, Any]:
    result = dict(item)
    result.pop("secret_ref", None)
    result["config"] = dict(result.pop("config_json", result.pop("config", {})) or {})
    result["api_key_mask"] = result.pop("api_key_mask", None)
    result["secret_source"] = "panel" if item.get("secret_ref") else ("env" if item.get("provider") == "gemini" and settings.gemini_api_key else None)
    return result


def _validate_url(url: str, *, cloud: bool = True) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=422, detail="custom API URL must be http(s)")
    if cloud:
        host = parsed.hostname.lower()
        if host in {"localhost", "127.0.0.1", "::1"}:
            raise HTTPException(status_code=422, detail="private/localhost addresses are blocked in cloud mode")
        try:
            addresses = socket.getaddrinfo(host, parsed.port or 443)
            for _, _, _, _, sockaddr in addresses:
                if ipaddress.ip_address(sockaddr[0]).is_private or ipaddress.ip_address(sockaddr[0]).is_loopback:
                    raise HTTPException(status_code=422, detail="private addresses are blocked in cloud mode")
        except socket.gaierror:
            pass

@router.get("/integrations")
def list_integrations(project_id: Optional[str] = None):
    return [_public(item) for item in db.list_integrations(project_id=project_id)]

@router.post("/integrations")
def create_integration(payload: IntegrationPayload):
    secret = payload.api_key or payload.secret
    item = payload.model_dump(exclude={"api_key", "secret"})
    item["config_json"] = dict(item.pop("config"))
    if secret:
        f = _fernet()
        if not f:
            raise HTTPException(status_code=503, detail={"status":"unconfigured", "reason":"ZECRO_SECRETS_KEY is required to save secrets"})
        item["secret_ref"] = f.encrypt(secret.encode()).decode()
        item["config_json"]["api_key_mask"] = _mask(secret)
        item["status"] = "configured"
    if payload.provider == "custom" and item["config_json"].get("base_url"):
        _validate_url(item["config_json"]["base_url"])
    saved = db.save_integration(item)
    db.record_integration_audit(saved["id"], "created", {"provider": saved.get("provider"), "has_secret": bool(secret)})
    return _public(saved)

@router.put("/integrations/{integration_id}")
def update_integration(integration_id: str, payload: IntegrationPayload):
    if not db.get_integration(integration_id): raise HTTPException(status_code=404, detail="Integration not found")
    secret = payload.api_key or payload.secret
    item = payload.model_dump(exclude={"api_key", "secret"}); item["id"] = integration_id; item["config_json"] = dict(item.pop("config"))
    if secret:
        f = _fernet()
        if not f: raise HTTPException(status_code=503, detail={"status":"unconfigured", "reason":"ZECRO_SECRETS_KEY is required to save secrets"})
        item["secret_ref"] = f.encrypt(secret.encode()).decode(); item["config_json"]["api_key_mask"] = _mask(secret); item["status"] = "configured"
    saved=db.save_integration(item); db.record_integration_audit(integration_id,"updated",{"provider":saved.get("provider"),"has_secret":bool(secret)}); return _public(saved)

@router.delete("/integrations/{integration_id}")
def delete_integration(integration_id: str):
    if not db.delete_integration(integration_id): raise HTTPException(status_code=404, detail="Integration not found")
    db.record_integration_audit(integration_id,"deleted",{}); return {"status":"deleted"}

@router.post("/integrations/{integration_id}/test")
def test_integration(integration_id: str):
    item=db.get_integration(integration_id)
    if not item: raise HTTPException(status_code=404, detail="Integration not found")
    provider=item.get("provider")
    try:
        if provider == "gemini": state, models = list_models(); result={"status":state,"models":models}
        elif provider in {"custom", "openai", "anthropic", "mistral"}:
            base=item.get("config_json",{}).get("base_url")
            if not base: raise ValueError("base_url is required")
            _validate_url(base)
            import requests
            response = requests.get(base, timeout=8, allow_redirects=False, stream=True)
            if response.status_code >= 400:
                result={"status":"error","reason":f"provider returned HTTP {response.status_code}"}
            elif response.is_redirect:
                result={"status":"error","reason":"redirect blocked; configure the final URL"}
            else:
                result={"status":"ready","http_status":response.status_code,"message":"real provider HTTP probe succeeded"}
            response.close()
        else: result={"status":"unconfigured","reason":"provider adapter requires credentials or an agency contract"}
    except Exception as exc: result={"status":"error","reason":str(exc)}
    item["status"]=result["status"]; item["last_test_at"]=datetime.now(timezone.utc).isoformat(); item["last_test_result"]=json.dumps(result,ensure_ascii=False); saved=db.save_integration(item); db.record_integration_audit(integration_id,"tested",{"status":result["status"]}); return {**_public(saved),"test":result}

@router.get("/integrations/{integration_id}/models")
def integration_models(integration_id: str):
    item=db.get_integration(integration_id)
    if not item: raise HTTPException(status_code=404, detail="Integration not found")
    if item.get("provider") == "gemini":
        state, models=list_models(); return {"status":state,"models":models}
    return {"status":"unconfigured","models":[],"reason":"model discovery is not configured for this adapter"}

@router.post("/integrations/import-openapi")
def import_openapi(spec: dict[str, Any]):
    paths=spec.get("paths") or {}
    operations=[]
    for path, methods in paths.items():
        for method, operation in (methods or {}).items():
            if method.lower() in {"get","post","put","patch","delete"}:
                operations.append({"method":method.upper(),"path":path,"operation_id":(operation or {}).get("operationId")})
    return {"status":"ready","operations":operations}

@router.get("/routing")
def get_routing(): return db.get_routing()
@router.put("/routing")
def put_routing(payload: dict[str, Any]): return db.save_routing(payload)
@router.get("/limits")
def get_limits(): return db.get_limits()
@router.put("/limits")
def put_limits(payload: dict[str, Any]): return db.save_limits(payload)
@router.get("/audit")
def get_audit(): return db.list_integration_audit()
