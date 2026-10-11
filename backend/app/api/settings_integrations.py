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


from ..ai.secrets_store import fernet as _fernet, mask as _mask, decrypt as _decrypt


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

PROVIDER_DEFAULT_BASE = {"openai": "https://api.openai.com/v1", "mistral": "https://api.mistral.ai/v1", "anthropic": "https://api.anthropic.com"}


def _list_provider_models(item: dict) -> dict:
    import requests
    provider = item.get("provider")
    cfg = item.get("config_json") or {}
    key = _decrypt(item.get("secret_ref"))
    if provider == "gemini":
        state, models = list_models(key)
        return {"status": state, "models": models}
    if provider in {"openai", "mistral", "openai_compatible"} or (provider == "custom" and cfg.get("type") == "openai_compatible"):
        base = (cfg.get("base_url") or PROVIDER_DEFAULT_BASE.get(provider, "")).rstrip("/")
        from ..integrations.connector import check_url
        check_url(base, allow_private=bool(cfg.get("allow_private")))
        r = requests.get(f"{base}/models", headers={"Authorization": f"Bearer {key}"} if key else {}, timeout=15)
        if r.status_code >= 400:
            return {"status": "error", "reason": f"HTTP {r.status_code}: {r.text[:200]}"}
        return {"status": "ready", "models": sorted(m.get("id") for m in r.json().get("data", []))}
    if provider == "anthropic":
        r = requests.get((cfg.get("base_url") or PROVIDER_DEFAULT_BASE["anthropic"]).rstrip("/") + "/v1/models",
                         headers={"x-api-key": key or "", "anthropic-version": "2023-06-01"}, timeout=15)
        if r.status_code >= 400:
            return {"status": "error", "reason": f"HTTP {r.status_code}: {r.text[:200]}"}
        return {"status": "ready", "models": [m.get("id") for m in r.json().get("data", [])]}
    return {"status": "unconfigured", "models": [], "reason": "ten adapter nie udostępnia listy modeli"}


class TestPayload(BaseModel):
    query: str = "Warszawa"
    params: dict[str, Any] = Field(default_factory=dict)


@router.post("/integrations/{integration_id}/test")
def test_integration(integration_id: str, payload: TestPayload = TestPayload()):
    import time
    item = db.get_integration(integration_id)
    if not item:
        raise HTTPException(status_code=404, detail="Integration not found")
    cfg = item.get("config_json") or {}
    started = time.time()
    try:
        if item.get("kind") == "ai_provider":
            listed = _list_provider_models(item)
            result = {**listed, "models": listed.get("models", [])[:50]}
            if listed.get("status") in {"ready", "warning"} and cfg.get("model"):
                from ..ai.integration_registry import Route
                from ..ai.runtime import PROVIDERS
                route = Route(item["provider"], cfg["model"], api_key=_decrypt(item.get("secret_ref")), base_url=cfg.get("base_url"), integration_id=item["id"], config=cfg)
                call = PROVIDERS.get(item["provider"] if item["provider"] != "custom" else "custom")
                data, tin, tout = call(route, "Odpowiadasz JSON.", 'Zwróć {"ok": true}', {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}, [], 0, 64)
                result["probe"] = {"response": data, "input_tokens": tin, "output_tokens": tout}
        elif cfg.get("request"):
            from ..integrations.connector import execute
            out = execute(item, {"query": payload.query, **payload.params}, raw=True)
            raw = out.get("raw")
            result = {"status": "ready" if not [e for e in out["errors"] if e.get("item") is not None] else "warning", "count": out["count"],
                      "items": out["items"][:3], "mapping_errors": out["errors"][:20], "raw_sample": json.dumps(raw, ensure_ascii=False)[:4000] if not isinstance(raw, str) else raw[:4000]}
        elif item.get("provider") in {"openverse", "wikimedia", "unsplash", "pexels", "pixabay"}:
            from ..integrations.photo_sources import BUILTIN
            rows = BUILTIN[item["provider"]](payload.query, 3)
            result = {"status": "ready", "count": len(rows), "items": rows[:3]}
        else:
            result = {"status": "unconfigured", "reason": "adapter wymaga umowy/danych dostępowych — skonfiguruj go jako własne API"}
    except LookupError:
        result = {"status": "unconfigured", "reason": "brak klucza"}
    except Exception as exc:
        result = {"status": "error", "reason": str(exc)[:400]}
    result["elapsed_ms"] = int((time.time() - started) * 1000)
    item["status"] = result["status"]
    item["last_test_at"] = datetime.now(timezone.utc).isoformat()
    item["last_test_result"] = json.dumps(result, ensure_ascii=False, default=str)[:8000]
    saved = db.save_integration(item)
    db.record_integration_audit(integration_id, "tested", {"status": result["status"]})
    return {**_public(saved), "test": result}


@router.get("/integrations/{integration_id}/models")
def integration_models(integration_id: str):
    item = db.get_integration(integration_id)
    if not item:
        raise HTTPException(status_code=404, detail="Integration not found")
    try:
        return _list_provider_models(item)
    except Exception as exc:
        return {"status": "error", "models": [], "reason": str(exc)[:300]}


class OpenAPIImport(BaseModel):
    spec: Optional[dict[str, Any]] = None
    url: Optional[str] = None
    role: str = "photo_source"


@router.post("/integrations/import-openapi")
def import_openapi(payload: OpenAPIImport):
    from ..integrations.connector import import_openapi as do_import, check_url
    spec = payload.spec
    if not spec and payload.url:
        import requests
        check_url(payload.url)
        r = requests.get(payload.url, timeout=20)
        r.raise_for_status()
        text = r.text
        try:
            spec = json.loads(text)
        except Exception:
            try:
                import yaml
                spec = yaml.safe_load(text)
            except Exception:
                raise HTTPException(status_code=422, detail="specyfikacja nie jest JSON/YAML")
    if not spec:
        raise HTTPException(status_code=422, detail="podaj spec albo url")
    return do_import(spec, payload.role)


@router.get("/routing")
def get_routing():
    from ..ai.integration_registry import TASK_DEFAULTS, registry
    saved = db.get_routing()
    out = {}
    for task, attr in TASK_DEFAULTS.items():
        resolved = registry.resolve(task)
        out[task] = {"config": saved.get(task) or {}, "default_model": getattr(settings, attr), "status": resolved.status,
                     "chain": [{"provider": r.provider, "model": r.model, "integration_id": r.integration_id} for r in resolved.chain],
                     "reason": resolved.reason}
    return out


@router.put("/routing")
def put_routing(payload: dict[str, Any]):
    from ..ai.integration_registry import TASK_DEFAULTS
    unknown = [t for t in payload if t.split(":")[-1] not in TASK_DEFAULTS]
    if unknown:
        raise HTTPException(status_code=422, detail=f"nieznane zadania: {unknown}")
    db.save_routing(payload)
    db.record_integration_audit("routing", "updated", {"tasks": list(payload)})
    return get_routing()


@router.get("/limits")
def get_limits():
    from ..ai.runtime import month_spend_usd
    spent, complete = month_spend_usd()
    return {**(db.get_limits() or {}), "month_spend_usd": spent, "price_table_complete": complete}


@router.put("/limits")
def put_limits(payload: dict[str, Any]):
    db.save_limits({k: v for k, v in payload.items() if k in {"monthly_budget_usd", "prices", "rpm", "project_budgets"}})
    return get_limits()


@router.get("/audit")
def get_audit():
    return db.list_integration_audit()
