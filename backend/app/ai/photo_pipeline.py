"""Photo desk: brief → licensed search → AI ranking on the pixels → crop → caption.
Tor B: editorial illustrations (never photorealistic for real events/people).
"""
from __future__ import annotations
import hashlib, io, json
from pathlib import Path
from typing import Any, Optional

from ..config import settings
from ..integrations.photo_sources import search as source_search, UA
from .gemini_client import AIUnavailable, generate_image
from .photo_brief import build_photo_brief, PhotoBrief
from .runtime import run_task
from . import schemas as S

CACHE = settings.uploads_dir / "photo_cache"


def _download(url: str, max_bytes: int = 25_000_000) -> Optional[bytes]:
    import requests
    try:
        from ..integrations.connector import check_url
        check_url(url)
        r = requests.get(url, headers=UA, timeout=30, stream=True)
        if r.status_code >= 400:
            return None
        data = r.raw.read(max_bytes + 1, decode_content=True)
        return None if len(data) > max_bytes else data
    except Exception:
        return None


def _thumb(data: bytes, size: int = 768) -> bytes:
    from PIL import Image
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        im.thumbnail((size, size))
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=85)
        return buf.getvalue()


def _story_dict(story) -> dict:
    return {"headline": getattr(story, "headline", ""), "lead": getattr(story, "lead", "") or "", "body": (getattr(story, "body", "") or "")[:1500]}


def propose_photos(story, *, project_id: Optional[str] = None, limit: int = 6, providers: Optional[list[str]] = None) -> dict[str, Any]:
    brief = build_photo_brief(story, project_id=project_id)
    queries = (brief.search_queries_pl or []) + (brief.search_queries_en or [])
    found = source_search(queries or [story.headline], providers=providers, limit=6, project_id=project_id)
    candidates = []
    for row in found["results"][:14]:
        data = _download(row.get("thumb_url") or row["url"], 6_000_000)
        if not data:
            continue
        try:
            candidates.append({**row, "_thumb": _thumb(data)})
        except Exception:
            continue
    result: dict[str, Any] = {"brief": brief.model_dump(), "sources": found["sources"], "status": "draft"}
    if not candidates:
        result.update(candidates=[], reason="brak wyników w skonfigurowanych źródłach")
        return result
    try:
        listing = [{"index": i, "title": c.get("title"), "description": c.get("description", ""), "credit_line": c.get("credit_line"),
                    "license": c.get("license"), "width_px": c.get("width_px"), "height_px": c.get("height_px")} for i, c in enumerate(candidates)]
        ranked = run_task("photo_ranking", "photo_ranking", {"story": _story_dict(story), "brief": brief.model_dump(exclude={"provenance"}),
                          "candidates": listing}, S.PhotoRanking, images=[{"data": c["_thumb"], "mime_type": "image/jpeg"} for c in candidates],
                          project_id=project_id)
        scores = {s["index"]: s for s in ranked.data["scores"]}
        result["ranking_provenance"] = ranked.provenance
    except AIUnavailable as exc:
        scores, result["ranking_provenance"] = {}, {"status": "unavailable", "reason": str(exc)}
    out = []
    for i, c in enumerate(candidates):
        sc = scores.get(i, {})
        total = (0.55 * sc.get("relevance", 0) + 0.2 * sc.get("technical_quality", 0) + 0.15 * sc.get("newsworthiness", 0)
                 + (0.1 if sc.get("depicts_claimed_subject") == "yes" else 0) - (0.2 if sc.get("depicts_claimed_subject") == "no" else 0)
                 - 0.05 * len(sc.get("risks") or [])) if sc else None
        out.append({k: v for k, v in c.items() if k != "_thumb"} | {"score": None if total is None else round(total, 3), "ai": sc})
    out.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))
    result["candidates"] = out[:limit]
    return result


def _focal(img, crop_suggestion: Optional[list[int]]) -> list[float]:
    """Focal point: faces first (OpenCV), then the model's crop box, then centre."""
    try:
        import cv2, numpy as np
        arr = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2GRAY)
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = cascade.detectMultiScale(arr, scaleFactor=1.1, minNeighbors=6, minSize=(max(24, arr.shape[1] // 40),) * 2)
        if len(faces):
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            return [round((x + w / 2) / arr.shape[1], 4), round((y + h * 0.6) / arr.shape[0], 4)]
    except Exception:
        pass
    if crop_suggestion and len(crop_suggestion) == 4:
        ymin, xmin, ymax, xmax = crop_suggestion
        return [round((xmin + xmax) / 2000, 4), round((ymin + ymax) / 2000, 4)]
    return [0.5, 0.5]


def accept_photo(candidate: dict, story=None, *, project_id: Optional[str] = None) -> dict[str, Any]:
    """Download the full-resolution file, store it, compute focal point and caption."""
    from PIL import Image
    data = _download(candidate["url"])
    if not data:
        raise AIUnavailable("nie udało się pobrać pliku zdjęcia")
    CACHE.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(data).hexdigest()[:16]
    with Image.open(io.BytesIO(data)) as im:
        ext = ".png" if im.format == "PNG" else ".jpg"
        path = CACHE / f"photo_{sha}{ext}"
        path.write_bytes(data)
        w, h = im.size
        dpi = float(im.info.get("dpi", (0,))[0] or 0) or None
        focal = _focal(im, (candidate.get("ai") or {}).get("crop_suggestion"))
    caption = None
    if story is not None:
        try:
            cap = run_task("caption", "caption", {"story": _story_dict(story), "image": {"title": candidate.get("title"),
                           "description": candidate.get("description", ""), "captured_at": candidate.get("captured_at")},
                           "credit_line": candidate.get("credit_line")}, S.Caption, images=[{"data": _thumb(data), "mime_type": "image/jpeg"}], project_id=project_id)
            caption = cap.data
        except AIUnavailable:
            caption = None
    from ..storage.asset_store import persist_asset
    import shutil
    up = settings.uploads_dir / f"asset_{sha}{ext}"
    shutil.copy2(path, up)
    ref = persist_asset(up, prefix="uploads", key=up.name) or str(up)
    return {"url": _public(ref, up), "storage_ref": ref, "width_px": w, "height_px": h, "dpi": dpi, "focal_point": focal, "credit": candidate.get("credit_line"),
            "license": candidate.get("license"), "license_url": candidate.get("license_url"), "source_page": candidate.get("source_page"),
            "caption": (caption or {}).get("caption"), "caption_identity_basis": (caption or {}).get("identity_basis"),
            "provider": candidate.get("provider"), "ai_generated": False, "status": "draft"}


def _public(ref: str, local: Path) -> str:
    """URL usable both by the browser and by the renderers."""
    from ..storage.supabase_storage import parse_storage_reference, get_storage_public_url
    try:
        if parse_storage_reference(ref):
            return get_storage_public_url(ref)
    except Exception:
        pass
    return f"/static/uploads/{local.name}"


def generate_illustration(story, *, project_id: Optional[str] = None, aspect_ratio: str = "4:3", style: str = "editorial vector illustration",
                          palette: Optional[list[str]] = None, n: int = 3) -> dict[str, Any]:
    brief = build_photo_brief(story, project_id=project_id)
    photoreal = "photo" in style.lower() or "realistic" in style.lower()
    if brief.real_people and photoreal or (photoreal and brief.is_real_event):
        return {"status": "refused", "reason": "Fotorealizm wyłączony dla prawdziwych zdarzeń i osób z nazwiska",
                "suggestion": "Użyj zdjęcia z licencjonowanego źródła (Tor A) albo stylu ilustracyjnego", "brief": brief.model_dump()}
    p = run_task("caption", "image_prompt", {"brief": {"illustration_idea": brief.illustration_idea or brief.what_event, "what_event": brief.what_event,
                 "must_show": brief.must_show, "must_not_show": brief.must_not_show + (brief.real_people or [])}, "palette": palette or [],
                 "style": style, "aspect_ratio": aspect_ratio}, S.ImagePrompt, project_id=project_id)
    prompt = p.data["prompt"] + " Avoid: " + ", ".join(p.data["negative"] + ["real people likeness", "logos", "text", "photojournalism look"])
    gen = generate_image(prompt, aspect_ratio, n=n)
    import shutil
    from ..storage.asset_store import persist_asset
    files = []
    for f in gen["files"]:
        labelled = Path(_label_ai(Path(f), prompt))
        up = settings.uploads_dir / f"ai_{labelled.name}"
        shutil.copy2(labelled, up)
        ref = persist_asset(up, prefix="uploads", key=up.name) or str(up)
        files.append({"url": _public(ref, up), "storage_ref": ref, "path": str(labelled)})
    return {"status": "draft", "files": files, "prompt": prompt, "brief": brief.model_dump(), "ai_generated": True,
            "caption_suffix": "Ilustracja wygenerowana przez AI", "provenance": {**gen["provenance"], "prompt_task": p.provenance}}


def _label_ai(path: Path, prompt: str) -> str:
    """Embed IPTC DigitalSourceType=trainedAlgorithmicMedia (XMP) + sidecar."""
    from PIL import Image
    xmp = ('<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
           '<rdf:Description xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/" '
           'Iptc4xmpExt:DigitalSourceType="http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"/>'
           '</rdf:RDF></x:xmpmeta>').encode()
    out = path.with_suffix(".jpg")
    with Image.open(path) as im:
        im.convert("RGB").save(out, "JPEG", quality=94, xmp=xmp)
    out.with_suffix(".provenance.json").write_text(json.dumps({"ai_generated": True, "digital_source_type": "trainedAlgorithmicMedia",
                                                               "prompt": prompt}, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out)
