from __future__ import annotations
from typing import Any
from .photo_brief import PhotoBrief


def generate_editorial_image(brief: PhotoBrief, *, aspect_ratio: str = "4:3", style: str = "editorial illustration") -> dict[str, Any]:
    """Guard kept for API compatibility: photoreal generation of real events is refused."""
    photoreal = "photo" in style.lower() or "realistic" in style.lower()
    if brief.real_people or (brief.is_real_event and photoreal):
        if True:
            return {"status": "refused", "reason": "Photorealistic generation is disabled for real events or named people",
                    "suggestion": "Use Tor A licensed search or an explicitly illustrated treatment", "ai_generated": False}
    from .gemini_client import generate_image
    result = generate_image(f"{style}. {brief.illustration_idea or brief.what_event}. No real people, no logos, no text.", aspect_ratio)
    result.update({"ai_generated": True, "caption_suffix": "Ilustracja wygenerowana przez AI", "status": "draft"})
    return result
