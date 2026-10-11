"""Resolve task routes through saved integrations, with explicit availability."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from ..models.database import db
from ..config import settings

TASK_DEFAULTS = {
    "page_planning":"gemini_model_text_pro", "copy_fit":"gemini_model_text_pro", "headline_variants":"gemini_model_text_fast",
    "write_from_brief":"gemini_model_text_pro", "fact_guard":"gemini_model_text_fast", "translate":"gemini_model_text_pro",
    "photo_brief":"gemini_model_text_fast", "photo_ranking":"gemini_model_text_pro", "image_generation":"gemini_model_image",
    "mask_qa":"gemini_model_text_fast", "visual_critic":"gemini_model_text_pro", "corpus_audit":"gemini_model_text_fast",
    "embeddings":"gemini_model_embed", "logo_analysis":"gemini_model_text_pro",
}

@dataclass
class ResolvedTask:
    task: str
    provider: str
    model: str | None
    status: str
    reason: str | None = None
    integration_id: str | None = None
    fallback_from: str | None = None

class IntegrationRegistry:
    def resolve(self, task: str, project_id: str | None = None) -> ResolvedTask:
        routing=db.get_routing().get(task) or {}
        preferred=routing.get("provider","gemini")
        model=routing.get("model") or getattr(settings,TASK_DEFAULTS.get(task,"gemini_model_text_fast"))
        integrations=[item for item in db.list_integrations(project_id=project_id) if item.get("enabled") and item.get("kind")=="ai_provider"]
        for provider in [preferred,*routing.get("fallback",[])]:
            match=next((item for item in integrations if item.get("provider")==provider),None)
            if provider=="gemini" and (match or settings.gemini_api_key):
                return ResolvedTask(task,"gemini",model,"ready",integration_id=match.get("id") if match else None,fallback_from=preferred if provider!=preferred else None)
            if match and match.get("secret_ref"):
                return ResolvedTask(task,provider,match.get("config_json",{}).get("model") or model,"ready",integration_id=match.get("id"),fallback_from=preferred if provider!=preferred else None)
        return ResolvedTask(task,preferred,model,"unavailable",reason=f"No configured provider for task {task}")

registry=IntegrationRegistry()
