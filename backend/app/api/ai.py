from __future__ import annotations
from fastapi import APIRouter, HTTPException
from ..ai.gemini_client import AIUnavailable, generate_json, list_models, _client
from ..config import settings
from ..models.database import db
from pydantic import BaseModel

router = APIRouter(tags=["ai"])

class HealthReply(BaseModel):
    status: str
    provider: str = "gemini"
    model: str
    available_models: list[str] = []
    reason: str | None = None

@router.get("/health/ai", response_model=HealthReply)
def health_ai():
    state, models = list_models()
    if state == "unavailable":
        raise HTTPException(status_code=503, detail={"status":"unavailable", "reason":"GEMINI_API_KEY or google-genai is unavailable", "available_models": models})
    try:
        client = _client()
        response = client.models.generate_content(model=settings.gemini_model_text_fast, contents="Reply with the single word READY.")
        return HealthReply(status="ready" if getattr(response, "text", "").strip() else "unavailable", model=settings.gemini_model_text_fast, available_models=models)
    except AIUnavailable as exc:
        raise HTTPException(status_code=503, detail={"status":"unavailable", "reason":str(exc), "available_models":models})
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"status":"unavailable", "reason":str(exc), "available_models":models})

@router.get("/ai/usage")
def ai_usage():
    return {"status":"ready", "calls":db.list_ai_usage(), "budget_usd":settings.ai_monthly_budget_usd}
