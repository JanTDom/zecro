"""Single entry point for every AI task: routing, fallback, budget, provenance.

``run_task`` resolves the task through :mod:`integration_registry`, calls the
first provider of the chain and walks the fallback chain on failure.  Every
result carries a ``provenance`` record (provider, model, prompt version, input
hash, tokens, fallback history).  Nothing is fabricated: when no provider
works, :class:`AIUnavailable` is raised and the API answers 503.
"""
from __future__ import annotations
import base64, hashlib, json, mimetypes, time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from ..config import settings
from ..models.database import db
from .gemini_client import AIUnavailable, AIBudgetExceeded, prompt_text
from .integration_registry import registry, Route


@dataclass
class TaskResult:
    data: dict[str, Any]
    provenance: dict[str, Any]


# ---------------------------------------------------------------- helpers
def _image_bytes(item: Any) -> tuple[bytes, str]:
    if isinstance(item, (bytes, bytearray)):
        return bytes(item), "image/png"
    if isinstance(item, dict) and "data" in item:
        return item["data"], item.get("mime_type", "image/png")
    path = Path(str(item))
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return path.read_bytes(), mime


def _schema_of(schema: Any) -> dict:
    return schema.model_json_schema() if hasattr(schema, "model_json_schema") else dict(schema or {})


def _strip_json(text: str) -> Any:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0] or [0])
    return json.loads(text[start:])


def _validate(schema: Any, parsed: Any) -> dict:
    if hasattr(schema, "model_validate"):
        return schema.model_validate(parsed).model_dump(mode="json")
    return parsed


def month_spend_usd() -> tuple[float, bool]:
    """Spend this month using the user-entered price table (never guessed)."""
    limits = db.get_limits() or {}
    prices = limits.get("prices") or {}
    since = datetime.now(timezone.utc).strftime("%Y-%m-01")
    total, priced_all = 0.0, True
    for row in db.ai_usage_since(since):
        price = prices.get(row["model"])
        if not price:
            priced_all = priced_all and not (row["input_tokens"] or row["output_tokens"])
            continue
        total += row["input_tokens"] / 1e6 * float(price.get("input_per_mtok", 0)) + row["output_tokens"] / 1e6 * float(price.get("output_per_mtok", 0))
    return round(total, 4), priced_all


def _check_budget() -> None:
    limits = db.get_limits() or {}
    budget = limits.get("monthly_budget_usd") or settings.ai_monthly_budget_usd
    if budget:
        spent, _ = month_spend_usd()
        if spent >= float(budget):
            raise AIBudgetExceeded(f"monthly AI budget {budget} USD reached ({spent} USD)")


# ---------------------------------------------------------------- providers
def _call_gemini(route: Route, system: str, user: str, schema: Any, images: list, temperature, max_tokens, *, timeout_s: Optional[float] = None) -> tuple[Any, int | None, int | None]:
    try:
        from google import genai
        from google.genai import types
    except Exception as exc:
        raise AIUnavailable(f"google-genai is not installed: {exc}")
    client = genai.Client(api_key=route.api_key, http_options={"timeout": int((timeout_s or settings.gemini_timeout_s) * 1000)})
    parts: list[Any] = [user]
    for item in images:
        data, mime = _image_bytes(item)
        parts.append(types.Part.from_bytes(data=data, mime_type=mime))
    cfg = dict(system_instruction=system, response_mime_type="application/json")
    if schema is not None:
        cfg["response_json_schema"] = _schema_of(schema)
    if temperature is not None:
        cfg["temperature"] = float(temperature)
    if max_tokens:
        cfg["max_output_tokens"] = int(max_tokens)
    response = client.models.generate_content(model=route.model, contents=parts, config=types.GenerateContentConfig(**cfg))
    meta = getattr(response, "usage_metadata", None)
    return _strip_json(response.text or ""), getattr(meta, "prompt_token_count", None), getattr(meta, "candidates_token_count", None)


def _call_openai_compatible(route: Route, system: str, user: str, schema: Any, images: list, temperature, max_tokens, *, timeout_s: Optional[float] = None):
    import requests
    base = (route.base_url or ("https://api.mistral.ai/v1" if route.provider == "mistral" else "https://api.openai.com/v1")).rstrip("/")
    content: list[dict] = [{"type": "text", "text": user}]
    for item in images:
        data, mime = _image_bytes(item)
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}})
    body: dict[str, Any] = {"model": route.model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}]}
    if schema is not None:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "result", "schema": _schema_of(schema)}}
    if temperature is not None:
        body["temperature"] = float(temperature)
    if max_tokens:
        body["max_tokens"] = int(max_tokens)
    headers = {"Content-Type": "application/json"}
    if route.api_key:
        headers["Authorization"] = f"Bearer {route.api_key}"
    r = requests.post(f"{base}/chat/completions", json=body, headers=headers, timeout=timeout_s or settings.gemini_timeout_s)
    if r.status_code >= 400:
        raise RuntimeError(f"{route.provider} HTTP {r.status_code}: {r.text[:300]}")
    j = r.json()
    usage = j.get("usage") or {}
    return _strip_json(j["choices"][0]["message"]["content"]), usage.get("prompt_tokens"), usage.get("completion_tokens")


def _call_anthropic(route: Route, system: str, user: str, schema: Any, images: list, temperature, max_tokens, *, timeout_s: Optional[float] = None):
    import requests
    content: list[dict] = []
    for item in images:
        data, mime = _image_bytes(item)
        content.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": base64.b64encode(data).decode()}})
    instruction = user + ("\n\nZwróć wyłącznie JSON zgodny ze schematem:\n" + json.dumps(_schema_of(schema), ensure_ascii=False) if schema is not None else "")
    content.append({"type": "text", "text": instruction})
    body = {"model": route.model, "max_tokens": int(max_tokens or 4096), "system": system, "messages": [{"role": "user", "content": content}]}
    if temperature is not None:
        body["temperature"] = float(temperature)
    r = requests.post((route.base_url or "https://api.anthropic.com").rstrip("/") + "/v1/messages", json=body,
                      headers={"x-api-key": route.api_key or "", "anthropic-version": "2023-06-01", "content-type": "application/json"}, timeout=timeout_s or settings.gemini_timeout_s)
    if r.status_code >= 400:
        raise RuntimeError(f"anthropic HTTP {r.status_code}: {r.text[:300]}")
    j = r.json()
    text = "".join(b.get("text", "") for b in j.get("content", []) if b.get("type") == "text")
    usage = j.get("usage") or {}
    return _strip_json(text), usage.get("input_tokens"), usage.get("output_tokens")


def _call_custom(route: Route, system: str, user: str, schema: Any, images: list, temperature, max_tokens, *, timeout_s: Optional[float] = None):
    from ..integrations.connector import call_custom_ai
    return call_custom_ai(route, system, user, schema)


PROVIDERS = {"gemini": _call_gemini, "openai": _call_openai_compatible, "mistral": _call_openai_compatible,
             "openai_compatible": _call_openai_compatible, "anthropic": _call_anthropic, "custom": _call_custom}


# ---------------------------------------------------------------- entry point
def run_task(task: str, prompt_id: str, inputs: Any, schema: Any = None, *, images: Optional[Iterable[Any]] = None,
             project_id: Optional[str] = None, use_cache: bool = True,
             timeout_s: Optional[float] = None, max_retries: Optional[int] = None) -> TaskResult:
    resolved = registry.resolve(task, project_id)
    if resolved.status != "ready":
        raise AIUnavailable(resolved.reason or f"task {task} has no provider")
    _check_budget()
    system, version = prompt_text(prompt_id)
    image_list = list(images or [])
    image_hashes = [hashlib.sha256(_image_bytes(i)[0]).hexdigest()[:16] for i in image_list]
    user = json.dumps(inputs, ensure_ascii=False, default=str)
    input_sha = hashlib.sha256((user + "|".join(image_hashes)).encode()).hexdigest()
    attempts: list[dict] = []
    for index, route in enumerate(resolved.chain):
        cache_key = hashlib.sha256(f"{route.provider}|{route.model}|{prompt_id}@{version}|{input_sha}".encode()).hexdigest()
        provenance = {"task": task, "provider": route.provider, "model": route.model, "integration_id": route.integration_id,
                      "prompt_id": prompt_id, "prompt_version": version, "input_sha256": input_sha, "cache_key": cache_key,
                      "fallback_from": resolved.chain[0].provider + (":" + str(resolved.chain[0].model)) if index else None,
                      "attempts": list(attempts), "status": "draft", "created_at": datetime.now(timezone.utc).isoformat()}
        if use_cache:
            cached = db.get_ai_call(cache_key)
            if cached and cached.get("status") == "draft" and isinstance(cached.get("raw_response"), dict):
                return TaskResult(cached["raw_response"], {**provenance, "cached": True})
        call = PROVIDERS.get(route.provider)
        if not call:
            attempts.append({"provider": route.provider, "model": route.model, "error": "no adapter"})
            continue
        last: Exception | None = None
        retry_count = max(1, max_retries if max_retries is not None else settings.gemini_max_retries)
        for attempt in range(retry_count):
            try:
                args = (route, system, user, schema, image_list, resolved.temperature, resolved.max_tokens)
                raw, tin, tout = call(*args, timeout_s=timeout_s) if timeout_s is not None else call(*args)
                data = _validate(schema, raw)
                db.save_ai_call({"cache_key": cache_key, "provider": route.provider, "model": route.model or "", "prompt_id": prompt_id,
                                 "prompt_version": version, "input_sha256": input_sha, "status": "draft", "input_tokens": tin,
                                 "output_tokens": tout, "raw_response": data})
                provenance.update(input_tokens=tin, output_tokens=tout)
                return TaskResult(data, provenance)
            except AIUnavailable as exc:
                last = exc
                break
            except Exception as exc:  # retry transient / validation errors, then fall back
                last = exc
                if attempt + 1 < retry_count:
                    time.sleep(min(6.0, 0.6 * (2 ** attempt)))
        attempts.append({"provider": route.provider, "model": route.model, "error": str(last)[:400]})
        db.save_ai_call({"cache_key": cache_key, "provider": route.provider, "model": route.model or "", "prompt_id": prompt_id,
                         "prompt_version": version, "input_sha256": input_sha, "status": "failed", "error": str(last)[:1000], "raw_response": None})
    raise AIUnavailable("all providers failed for task " + task + ": " + json.dumps(attempts, ensure_ascii=False)[:800])
