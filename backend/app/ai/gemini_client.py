"""Small, auditable wrapper around Google's official ``google-genai`` SDK."""
from __future__ import annotations
import hashlib, json, time
from pathlib import Path
from typing import Any, Iterable
from ..config import settings
from ..models.database import db

class AIUnavailable(RuntimeError):
    status_code = 503
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)

class AIBudgetExceeded(RuntimeError):
    status_code = 429

PROMPT_DIR = Path(__file__).with_name("prompts")


def _prompt(prompt_id: str) -> tuple[str, str]:
    path = PROMPT_DIR / f"{prompt_id}.md"
    if not path.exists():
        raise AIUnavailable(f"prompt '{prompt_id}' is unavailable")
    raw = path.read_text(encoding="utf-8")
    version = "1"
    for line in raw.splitlines()[:4]:
        if "version:" in line:
            version = line.split("version:", 1)[1].strip()
    return raw, version


def _client():
    if not settings.gemini_api_key:
        raise AIUnavailable("GEMINI_API_KEY is not configured")
    try:
        from google import genai
    except Exception as exc:
        raise AIUnavailable(f"google-genai is not installed: {exc}")
    return genai.Client(api_key=settings.gemini_api_key, http_options={"timeout": int(settings.gemini_timeout_s * 1000)})


def _hash_input(model: str, prompt_key: str, inputs: Any) -> str:
    payload = json.dumps({"model": model, "prompt": prompt_key, "inputs": inputs}, sort_keys=True, ensure_ascii=False, default=str).encode()
    return hashlib.sha256(payload).hexdigest()


def _usage(response: Any) -> tuple[int | None, int | None]:
    meta = getattr(response, "usage_metadata", None)
    if not meta: return None, None
    return getattr(meta, "prompt_token_count", None), getattr(meta, "candidates_token_count", None)


def generate_json(model: str, prompt_id: str, inputs: Any, response_schema: Any, images: Iterable[Any] | None = None) -> dict[str, Any]:
    """Call Gemini with structured JSON and validate the decoded response.

    A malformed structured response gets exactly one repair request carrying
    the validation error.  Every call is cached and retained with provenance.
    """
    prompt, version = _prompt(prompt_id)
    cache_key = _hash_input(model, f"{prompt_id}@{version}", {"inputs": inputs, "images": list(images or [])})
    cached = db.get_ai_call(cache_key)
    if cached and cached.get("status") in {"draft", "approved"} and isinstance(cached.get("raw_response"), dict):
        return cached["raw_response"]
    client = _client()
    try:
        from google.genai import types
    except Exception as exc:
        raise AIUnavailable(f"google-genai types unavailable: {exc}")
    schema = response_schema.model_json_schema() if hasattr(response_schema, "model_json_schema") else response_schema
    contents: list[Any] = [prompt, json.dumps(inputs, ensure_ascii=False, default=str)]
    if images:
        contents.extend(list(images))
    last_error: Exception | None = None
    for attempt in range(max(1, settings.gemini_max_retries)):
        try:
            config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema)
            response = client.models.generate_content(model=model, contents=contents, config=config)
            raw = getattr(response, "text", "") or ""
            parsed = json.loads(raw)
            if hasattr(response_schema, "model_validate"):
                parsed = response_schema.model_validate(parsed).model_dump(mode="json")
            in_tokens, out_tokens = _usage(response)
            db.save_ai_call({"cache_key": cache_key, "provider":"gemini", "model":model, "prompt_id":prompt_id, "prompt_version":version, "input_sha256":hashlib.sha256(json.dumps(inputs, sort_keys=True, default=str).encode()).hexdigest(), "status":"draft", "input_tokens":in_tokens, "output_tokens":out_tokens, "raw_response":parsed})
            return parsed
        except Exception as exc:
            last_error = exc
            if attempt + 1 < max(1, settings.gemini_max_retries):
                time.sleep(min(8.0, .5 * (2 ** attempt)))
    db.save_ai_call({"cache_key": cache_key, "provider":"gemini", "model":model, "prompt_id":prompt_id, "prompt_version":version, "input_sha256":hashlib.sha256(json.dumps(inputs, sort_keys=True, default=str).encode()).hexdigest(), "status":"failed", "error":str(last_error), "raw_response":None})
    raise AIUnavailable(f"Gemini request failed: {last_error}")


def generate_image(prompt: str, aspect_ratio: str = "4:3", *, model: str | None = None) -> dict[str, Any]:
    if not settings.gemini_api_key:
        raise AIUnavailable("GEMINI_API_KEY is not configured")
    client = _client(); selected = model or settings.gemini_model_image
    try:
        response = client.models.generate_content(model=selected, contents=prompt)
        parts = getattr(getattr(response, "candidates", [None])[0], "content", None)
        return {"status":"draft", "model":selected, "aspect_ratio":aspect_ratio, "response":response, "provenance":{"prompt_id":"image_generation@1", "provider":"gemini"}}
    except Exception as exc:
        raise AIUnavailable(f"Gemini image generation failed: {exc}")


def embed(values: Iterable[Any], *, model: str | None = None) -> list[list[float]]:
    client = _client(); selected = model or settings.gemini_model_embed
    try:
        response = client.models.embed_content(model=selected, contents=list(values))
        return [list(getattr(item, "values", [])) for item in getattr(response, "embeddings", [])]
    except Exception as exc:
        raise AIUnavailable(f"Gemini embeddings failed: {exc}")


def list_models() -> tuple[str, list[str]]:
    if not settings.gemini_api_key:
        return "unavailable", []
    try:
        client = _client()
        models = [str(getattr(item, "name", "")).split("models/")[-1] for item in client.models.list()]
        configured = [settings.gemini_model_text_pro, settings.gemini_model_text_fast, settings.gemini_model_image, settings.gemini_model_embed]
        missing = [name for name in configured if name not in models]
        return ("warning" if missing else "ready"), models
    except Exception:
        return "unavailable", []
