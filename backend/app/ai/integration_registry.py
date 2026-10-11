"""Resolve AI tasks to an ordered provider chain from saved routing/integrations.

Routing (``/settings/routing``) maps a task to ``{provider, model, temperature,
max_tokens, fallback: [provider|"provider:model", ...]}``.  Providers are
``gemini`` (env or panel key), any saved ``ai_provider`` integration
(``openai``, ``anthropic``, ``mistral``, ``openai_compatible``, ``custom``) or a
custom-API integration id.  Nothing is resolved as ready without a usable key.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
from ..models.database import db
from ..config import settings
from .secrets_store import decrypt

TASK_DEFAULTS = {
    "page_planning": "gemini_model_text_pro", "copy_fit": "gemini_model_text_pro", "headline_variants": "gemini_model_text_pro",
    "write_from_brief": "gemini_model_text_pro", "fact_guard": "gemini_model_text_fast", "translate": "gemini_model_text_pro",
    "teaser": "gemini_model_text_fast", "caption": "gemini_model_text_fast", "pullquote": "gemini_model_text_fast", "infobox": "gemini_model_text_fast",
    "photo_brief": "gemini_model_text_fast", "photo_ranking": "gemini_model_text_pro", "image_generation": "gemini_model_image",
    "mask_qa": "gemini_model_text_fast", "visual_critic": "gemini_model_text_pro", "corpus_audit": "gemini_model_text_fast",
    "embeddings": "gemini_model_embed", "logo_analysis": "gemini_model_text_pro", "font_pairing": "gemini_model_text_pro",
}
FALLBACK_FAST = {"gemini_model_text_pro": "gemini_model_text_fast"}


@dataclass
class Route:
    provider: str
    model: Optional[str]
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    integration_id: Optional[str] = None
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolvedTask:
    task: str
    provider: str
    model: Optional[str]
    status: str
    reason: Optional[str] = None
    integration_id: Optional[str] = None
    fallback_from: Optional[str] = None
    chain: list[Route] = field(default_factory=list)
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class IntegrationRegistry:
    def _gemini_route(self, model: Optional[str], integrations: list[dict]) -> Optional[Route]:
        match = next((i for i in integrations if i.get("provider") == "gemini"), None)
        key = decrypt(match.get("secret_ref")) if match else None
        key = key or settings.gemini_api_key
        if not key:
            return None
        return Route("gemini", model, api_key=key, integration_id=match.get("id") if match else None,
                     config=dict((match or {}).get("config_json") or {}))

    def _route_for(self, spec: str, default_model: Optional[str], integrations: list[dict]) -> Optional[Route]:
        provider, _, model = spec.partition(":")
        model = model or None
        if provider == "gemini":
            return self._gemini_route(model or default_model, integrations)
        match = next((i for i in integrations if i.get("id") == provider), None) or \
            next((i for i in integrations if i.get("provider") == provider), None)
        if not match:
            return None
        cfg = dict(match.get("config_json") or {})
        key = decrypt(match.get("secret_ref"))
        needs_key = match.get("provider") not in {"custom", "openai_compatible"} or cfg.get("auth", {}).get("type", "none") != "none"
        if needs_key and not key and not cfg.get("local_no_key"):
            return None
        return Route(match.get("provider"), model or cfg.get("model") or None, api_key=key, base_url=cfg.get("base_url"),
                     integration_id=match.get("id"), config=cfg)

    def resolve(self, task: str, project_id: Optional[str] = None) -> ResolvedTask:
        routing_all = db.get_routing()
        routing = dict(routing_all.get(task) or {})
        if project_id:
            routing.update((routing_all.get(f"{project_id}:{task}") or {}))
        default_attr = TASK_DEFAULTS.get(task, "gemini_model_text_fast")
        default_model = getattr(settings, default_attr)
        preferred = routing.get("provider", "gemini")
        model = routing.get("model") or (default_model if preferred == "gemini" else None)
        integrations = [i for i in db.list_integrations(project_id=project_id) if i.get("enabled") and i.get("kind") == "ai_provider"]
        specs = [f"{preferred}:{model}" if model else preferred, *routing.get("fallback", [])]
        if not routing.get("fallback") and preferred == "gemini" and default_attr in FALLBACK_FAST:
            specs.append(f"gemini:{getattr(settings, FALLBACK_FAST[default_attr])}")
        chain: list[Route] = []
        for spec in specs:
            route = self._route_for(spec, default_model, integrations)
            if route and not any(r.provider == route.provider and r.model == route.model for r in chain):
                chain.append(route)
        if not chain:
            return ResolvedTask(task, preferred, model, "unavailable", reason=f"No configured provider for task {task}")
        first = chain[0]
        return ResolvedTask(task, first.provider, first.model, "ready", integration_id=first.integration_id,
                            fallback_from=preferred if first.provider != preferred else None, chain=chain,
                            temperature=routing.get("temperature"), max_tokens=routing.get("max_tokens"))


registry = IntegrationRegistry()
