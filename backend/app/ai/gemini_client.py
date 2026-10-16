"""Low-level Gemini helpers (official ``google-genai`` SDK).

Text/JSON tasks go through :func:`runtime.run_task`, which adds routing,
fallback and provenance.  This module keeps prompt loading, image generation,
embeddings and model discovery.
"""
from __future__ import annotations
import hashlib, json, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional
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


def prompt_text(prompt_id: str) -> tuple[str, str]:
    """Return (system prompt without header, version)."""
    path = PROMPT_DIR / f"{prompt_id}.md"
    if not path.exists():
        raise AIUnavailable(f"prompt '{prompt_id}' is unavailable")
    version, body = "1", []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# version:"):
            version = line.split(":", 1)[1].strip()
        elif line.startswith("# prompt_id:"):
            continue
        else:
            body.append(line)
    return "\n".join(body).strip(), version


# backwards-compatible name
def _prompt(prompt_id: str) -> tuple[str, str]:
    return prompt_text(prompt_id)


def gemini_key() -> Optional[str]:
    from .secrets_store import decrypt
    for item in db.list_integrations():
        if item.get("provider") == "gemini" and item.get("enabled") and item.get("secret_ref"):
            key = decrypt(item.get("secret_ref"))
            if key:
                return key
    return settings.gemini_api_key or None


def _client(api_key: Optional[str] = None):
    key = api_key or gemini_key()
    if not key:
        raise AIUnavailable("GEMINI_API_KEY is not configured")
    try:
        from google import genai
    except Exception as exc:
        raise AIUnavailable(f"google-genai is not installed: {exc}")
    return genai.Client(api_key=key, http_options={"timeout": int(settings.gemini_timeout_s * 1000)})


def generate_json(model: str, prompt_id: str, inputs: Any, response_schema: Any, images: Iterable[Any] | None = None) -> dict[str, Any]:
    """Compatibility wrapper: a Gemini-only call through the runtime."""
    from .runtime import run_task
    return run_task("copy_fit", prompt_id, inputs, response_schema, images=images).data


def generate_image(prompt: str, aspect_ratio: str = "4:3", *, model: Optional[str] = None,
                   output_dir: Optional[Path] = None, n: int = 1) -> dict[str, Any]:
    """Generate image(s) and save them as files.  Returns paths + provenance."""
    from .integration_registry import registry
    resolved = registry.resolve("image_generation")
    if resolved.status != "ready":
        raise AIUnavailable(resolved.reason or "image generation unavailable")
    route = resolved.chain[0]
    if route.provider != "gemini":
        raise AIUnavailable(f"image generation adapter for {route.provider} is not implemented")
    selected = model or route.model or settings.gemini_model_image
    client = _client(route.api_key)
    from google.genai import types
    out = Path(output_dir or settings.uploads_dir / "generated")
    out.mkdir(parents=True, exist_ok=True)
    files, errors = [], []
    for index in range(max(1, n)):
        try:
            cfg = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"],
                                              image_config=types.ImageConfig(aspect_ratio=aspect_ratio))
            response = client.models.generate_content(model=selected, contents=prompt, config=cfg)
            for cand in response.candidates or []:
                for part in (cand.content.parts if cand.content else []) or []:
                    blob = getattr(part, "inline_data", None)
                    if blob and blob.data:
                        ext = ".png" if "png" in (blob.mime_type or "") else ".jpg"
                        name = f"ai_{hashlib.sha256(blob.data).hexdigest()[:16]}{ext}"
                        (out / name).write_bytes(blob.data)
                        files.append(str(out / name))
        except Exception as exc:
            errors.append(str(exc)[:300])
    if not files:
        raise AIUnavailable("Gemini image generation produced no image: " + "; ".join(errors))
    record = {"model": selected, "prompt": prompt, "aspect_ratio": aspect_ratio, "created_at": datetime.now(timezone.utc).isoformat()}
    db.save_ai_call({"cache_key": hashlib.sha256((selected + prompt + str(time.time())).encode()).hexdigest(), "provider": "gemini",
                     "model": selected, "prompt_id": "image_generation", "prompt_version": "1",
                     "input_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "status": "draft", "raw_response": {"files": files}})
    return {"status": "draft", "files": files, "errors": errors, "provenance": {**record, "provider": "gemini", "prompt_id": "image_generation@1"}}


def embed(values: Iterable[Any], *, model: Optional[str] = None) -> list[list[float]]:
    from .runtime import _image_bytes
    client = _client()
    selected = model or settings.gemini_model_embed
    from google.genai import types
    contents = []
    for value in values:
        if isinstance(value, str) and not Path(value).exists():
            contents.append(value)
        else:
            data, mime = _image_bytes(value)
            contents.append(types.Content(parts=[types.Part.from_bytes(data=data, mime_type=mime)]))
    try:
        response = client.models.embed_content(model=selected, contents=contents)
        return [list(item.values) for item in response.embeddings]
    except Exception as exc:
        raise AIUnavailable(f"Gemini embeddings failed: {exc}")


def list_models(api_key: Optional[str] = None) -> tuple[str, list[str]]:
    try:
        client = _client(api_key)
        models = [str(getattr(item, "name", "")).split("models/")[-1] for item in client.models.list()]
    except Exception:
        return "unavailable", []
    configured = [settings.gemini_model_text_pro, settings.gemini_model_text_fast,
                  settings.gemini_model_segmentation, settings.gemini_model_image, settings.gemini_model_embed]
    return ("warning" if [m for m in configured if m not in models] else "ready"), models
