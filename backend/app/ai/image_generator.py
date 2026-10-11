from __future__ import annotations
from typing import Any
from .photo_brief import PhotoBrief
from .gemini_client import generate_image, AIUnavailable

def generate_editorial_image(brief: PhotoBrief, *, aspect_ratio: str = "4:3", style: str = "editorial illustration") -> dict[str, Any]:
    if brief.is_real_event or brief.real_people:
        return {"status":"refused", "reason":"Photorealistic generation is disabled for real events or named people", "suggestion":"Use Tor A licensed search or an explicitly illustrated treatment", "ai_generated":False}
    result=generate_image(f"{style}. {brief.what_event}. Avoid logos and claims not in the brief.", aspect_ratio)
    result.update({"ai_generated":True,"caption_suffix":"Ilustracja wygenerowana przez AI","prompt_provenance":"photo_generation@1","status":"draft"})
    return result
