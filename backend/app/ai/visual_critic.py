"""Visual critic: Gemini looks at the rendered page (PNG) and scores it.

Soft signal only — the hard gate stays deterministic.  Rendering uses the
production typesetter so the critic judges what will be printed.
"""
from __future__ import annotations
import hashlib, io, os, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

from .gemini_client import AIUnavailable
from .runtime import run_task
from . import schemas as S
from ..engine.editorial_style import editorial_style_label
from ..engine.page_topic import PAGE_TOPIC_LABELS


# A visual score is an estimate, not editorial approval.  A candidate must
# clear a high bar and have no visible genre contradiction before the editor
# is even asked to consider it.  The technical hard gate remains separate.
STYLE_FIDELITY_REVIEW_TARGET = 0.90


def category_review(critique: dict[str, Any], *, has_photos: bool = True) -> dict[str, Any]:
    fidelity = float(critique.get("style_fidelity") or 0.0)
    overall = float(critique.get("score") or 0.0)
    mismatches = critique.get("category_mismatch") or []
    photo_match = critique.get("photo_headline_match")
    photo_use = critique.get("photo_use")
    eligible = (fidelity >= STYLE_FIDELITY_REVIEW_TARGET and overall >= 0.80 and not mismatches
                and (not has_photos or photo_match is None or float(photo_match) >= .65)
                and (not has_photos or photo_use is None or float(photo_use) >= .65))
    return {
        "status": "candidate_for_editor" if eligible else "needs_revision",
        "target": STYLE_FIDELITY_REVIEW_TARGET,
        "editorial_approval_required": True,
    }


def render_png(sg, dna, *, width_px: int = 1100) -> bytes:
    from ..engine.renderers.pdf_renderer import PDFRenderer
    import pypdfium2 as pdfium
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "page.pdf"
        PDFRenderer(dna).render_to_file(sg, str(pdf))
        doc = pdfium.PdfDocument(str(pdf))
        page = doc[0]
        scale = width_px / page.get_width()
        img = page.render(scale=scale).to_pil().convert("RGB")
        buf = io.BytesIO(); img.save(buf, "JPEG", quality=88)
        doc.close()
        return buf.getvalue()


def critique(sg, dna, *, project_id: Optional[str] = None) -> dict[str, Any]:
    png = render_png(sg, dna)
    blend = (sg.metadata or {}).get("style_blend") or {}
    title_style = editorial_style_label(blend or dna.style_blend)
    topic = (sg.metadata or {}).get("page_topic", "general")
    mood = (sg.metadata or {}).get("editorial_mood", "auto")
    if topic != "general":
        title_style += f"; dział: {PAGE_TOPIC_LABELS.get(topic, 'temat ogólny')}"
    plan = [{"story": e.story_ref, "role": e.role, "size_pt": e.style.font_size_pt if e.style else None}
            for e in sg.elements if e.role in {"headline", "photo"}]
    lead_headline = next((e.text_content for e in sg.elements if e.role == "headline" and e.importance >= .95), "")
    res = run_task("visual_critic", "visual_critic", {"page_plan": plan, "title_style": title_style,
                   "editorial_mood": mood, "lead_headline": lead_headline,
                   "archetype": getattr(dna, "archetype", None), "cover_grammar": getattr(dna, "cover_grammar", None),
                   "photo_story_count": len({e.story_ref for e in sg.elements if e.role == "photo"}),
                   "grid": {"columns": dna.grid.columns, "trim_mm": [dna.format.trim_w_mm, dna.format.trim_h_mm]},
                   "render_sha": hashlib.sha256(png).hexdigest()[:16]}, S.PageCritique,
                   images=[{"data": png, "mime_type": "image/jpeg"}], project_id=project_id,
                   timeout_s=35, max_retries=1)
    return {**res.data, "category_review": category_review(res.data, has_photos=any(e.role == "photo" for e in sg.elements)),
            "provenance": res.provenance}


def rerank(pairs: list, dna, *, limit: int = 4, weight: float = 0.3, project_id: Optional[str] = None) -> tuple[list, dict]:
    """Attach critiques to the top passing candidates and blend the score."""
    status: dict[str, Any] = {"reviewed": 0, "candidates_for_editor": 0, "status": "ready"}
    scored = []
    to_review = [(index, sg) for index, (sg, cr) in enumerate(pairs)
                 if index < limit and getattr(cr.hard_gate, "passed", False)]
    reviews: dict[int, Any] = {}
    if to_review:
        # Rendering a print PDF and rasterising its embedded photographs can
        # briefly use hundreds of megabytes.  Three simultaneous candidates
        # were enough to terminate a small serverless worker.  Keep the
        # default deliberately serial; larger installations may opt into two
        # workers without changing the generator/critic contract.
        try:
            configured_workers = int(os.getenv("ZECRO_VISUAL_CRITIC_WORKERS", "1") or "1")
        except ValueError:
            configured_workers = 1
        review_workers = max(1, min(2, configured_workers, len(to_review)))
        status["review_workers"] = review_workers
        with ThreadPoolExecutor(max_workers=review_workers) as pool:
            futures = {index: pool.submit(critique, sg, dna, project_id=project_id)
                       for index, sg in to_review}
            for index, future in futures.items():
                try:
                    reviews[index] = future.result()
                except Exception as exc:
                    reviews[index] = exc
    for index, (sg, cr) in enumerate(pairs):
        base = float(getattr(cr, "total_fitness", 0.0) or 0.0)
        blended = base
        reviewed = False
        if index < limit and getattr(cr.hard_gate, "passed", False):
            try:
                c = reviews[index]
                if isinstance(c, Exception):
                    raise c
                reviewed = True
                sg.metadata["visual_critique"] = c
                fidelity = float(c.get("style_fidelity", c.get("score", 0)))
                visual_score = .55 * float(c.get("score", 0)) + .45 * fidelity
                blended = (1 - weight) * base + weight * visual_score
                if c["category_review"]["status"] == "candidate_for_editor":
                    status["candidates_for_editor"] += 1
                else:
                    blended *= .7
                status["reviewed"] += 1
            except AIUnavailable as exc:
                sg.metadata["visual_critique"] = {"status": "unavailable", "reason": str(exc)[:300]}
                status = {**status, "status": "unavailable", "reason": str(exc)[:300]}
            except Exception as exc:
                sg.metadata["visual_critique"] = {"status": "failed", "reason": str(exc)[:300]}
        elif getattr(cr.hard_gate, "passed", False):
            sg.metadata["visual_critique"] = {"status": "not_reviewed"}
        sg.metadata["blended_score"] = round(blended, 4)
        # An unreviewed scene must not outrank one that was actually judged
        # just because its original heuristic score escaped the visual penalty.
        scored.append((reviewed, blended, index, sg, cr))
    scored.sort(key=lambda t: (not t[4].hard_gate.passed, not t[0], -t[1], t[2]))
    status["unreviewed"] = sum(1 for reviewed, _, _, _, cr in scored if cr.hard_gate.passed and not reviewed)
    return [(sg, cr) for _, _, _, sg, cr in scored], status
