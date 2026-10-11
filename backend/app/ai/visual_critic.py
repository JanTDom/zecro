"""Visual critic: Gemini looks at the rendered page (PNG) and scores it.

Soft signal only — the hard gate stays deterministic.  Rendering uses the
production typesetter so the critic judges what will be printed.
"""
from __future__ import annotations
import hashlib, io, tempfile
from pathlib import Path
from typing import Any, Optional

from .gemini_client import AIUnavailable
from .runtime import run_task
from . import schemas as S


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
    plan = [{"story": e.story_ref, "role": e.role, "size_pt": e.style.font_size_pt if e.style else None}
            for e in sg.elements if e.role in {"headline", "photo"}]
    res = run_task("visual_critic", "visual_critic", {"page_plan": plan, "title_style": getattr(dna, "archetype", None),
                   "grid": {"columns": dna.grid.columns, "trim_mm": [dna.format.trim_w_mm, dna.format.trim_h_mm]},
                   "render_sha": hashlib.sha256(png).hexdigest()[:16]}, S.PageCritique,
                   images=[{"data": png, "mime_type": "image/jpeg"}], project_id=project_id)
    return {**res.data, "provenance": res.provenance}


def rerank(pairs: list, dna, *, limit: int = 4, weight: float = 0.3, project_id: Optional[str] = None) -> tuple[list, dict]:
    """Attach critiques to the top passing candidates and blend the score."""
    status: dict[str, Any] = {"reviewed": 0, "status": "ready"}
    scored = []
    for index, (sg, cr) in enumerate(pairs):
        base = float(getattr(cr, "total_fitness", 0.0) or 0.0)
        blended = base
        if index < limit and getattr(cr.hard_gate, "passed", False):
            try:
                c = critique(sg, dna, project_id=project_id)
                sg.metadata["visual_critique"] = c
                blended = (1 - weight) * base + weight * float(c.get("score", 0))
                status["reviewed"] += 1
            except AIUnavailable as exc:
                sg.metadata["visual_critique"] = {"status": "unavailable", "reason": str(exc)[:300]}
                status = {"reviewed": status["reviewed"], "status": "unavailable", "reason": str(exc)[:300]}
            except Exception as exc:
                sg.metadata["visual_critique"] = {"status": "failed", "reason": str(exc)[:300]}
        sg.metadata["blended_score"] = round(blended, 4)
        scored.append((blended, index, sg, cr))
    scored.sort(key=lambda t: (not t[3].hard_gate.passed, -t[0], t[1]))
    return [(sg, cr) for _, _, sg, cr in scored], status
