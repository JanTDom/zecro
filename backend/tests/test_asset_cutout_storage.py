"""Generated cutouts must keep the mask, contour and source as separate assets."""

import asyncio
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from PIL import Image

from backend.app.api import assets
from backend.app.engine.segmentation import SegmentationResult
from backend.app.engine.segmentation import _gemini_segment
from backend.app.engine.image_ops import extract_alpha_rings


def test_uploaded_photo_returns_persisted_mask_instead_of_source(monkeypatch, tmp_path):
    monkeypatch.setattr(assets.settings, "uploads_dir", tmp_path)
    records = []
    monkeypatch.setattr(assets.db, "save_editorial_object", lambda *args, **kwargs: records.append(args[1]))

    def segment(source, output, **kwargs):
        Image.new("RGBA", (40, 60), (255, 0, 0, 0)).save(output)
        return SegmentationResult(status="ready", mask_path=str(output),
                                  contour=[[10, 10], [80, 10], [80, 90], [10, 90]],
                                  quality={"status": "clean"}, provider="test-segmenter")

    uploaded = []

    def persist(path, *, prefix, key):
        uploaded.append(Path(path).name)
        return f"supabase://editorial/uploads/{key}"

    monkeypatch.setattr(assets, "segment_image", segment)
    monkeypatch.setattr(assets, "analyse_photo_focal", lambda *_: {"status": "unavailable", "focal_point": [.5, .5]})
    monkeypatch.setattr(assets, "persist_asset", persist)
    monkeypatch.setattr(assets, "get_storage_public_url", lambda ref: "https://storage.test/" + Path(ref).name)
    image = Image.new("RGB", (40, 60), (30, 80, 120))
    content = BytesIO()
    image.save(content, format="JPEG")
    content.seek(0)
    result = asyncio.run(assets.upload_image_asset(UploadFile(filename="picture.jpg", file=content), auto_cutout=True))

    assert result["cutout_status"] == "ready"
    assert result["alpha_mask_url"].endswith(".png")
    assert result["url"].endswith(".jpg")
    assert result["alpha_mask_url"] != result["url"]
    assert len(uploaded) == 2
    assert records[0].metadata["alpha_mask_ref"].endswith(".png")
    assert records[0].metadata["contour_polygon"] == result["contour_polygon"]


def test_photo_focal_preserves_a_vehicle_below_the_centre(monkeypatch, tmp_path):
    from backend.app.ai import photo_focal
    source = tmp_path / "train.jpg"
    Image.new("RGB", (400, 600), (40, 90, 130)).save(source)

    class Reply:
        data = {"subject_kind": "object", "point_x": 610, "point_y": 790,
                "confidence": .91, "reason": "Pociąg jest przy dolnej krawędzi."}
        provenance = {"provider": "gemini", "model": "test"}

    monkeypatch.setattr(photo_focal, "run_task", lambda *args, **kwargs: Reply())
    result = photo_focal.analyse_photo_focal(source)
    assert result["status"] == "ready"
    assert result["subject_kind"] == "object"
    assert result["focal_point"] == [.61, .79]


def test_uploaded_scene_uses_ai_focal_and_skips_person_cutout(monkeypatch, tmp_path):
    monkeypatch.setattr(assets.settings, "uploads_dir", tmp_path)
    monkeypatch.setattr(assets.db, "save_editorial_object", lambda *args, **kwargs: None)
    monkeypatch.setattr(assets, "analyse_photo_focal", lambda *_: {
        "status": "ready", "subject_kind": "object", "confidence": .91, "focal_point": [.61, .79]})
    monkeypatch.setattr(assets, "segment_image", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("a vehicle must not be segmented as a person")))
    monkeypatch.setattr(assets, "persist_asset", lambda path, *, prefix, key:
                        f"supabase://editorial/uploads/{key}")
    monkeypatch.setattr(assets, "get_storage_public_url", lambda ref: "https://storage.test/" + Path(ref).name)
    content = BytesIO()
    Image.new("RGB", (400, 600), (40, 90, 130)).save(content, format="JPEG")
    content.seek(0)
    result = asyncio.run(assets.upload_image_asset(
        UploadFile(filename="train.jpg", file=content), auto_cutout=True))
    assert result["cutout_status"] == "not_applicable"
    assert result["focal_point"] == [.61, .79]


def test_gemini_polygon_becomes_real_alpha_and_rejects_bounding_box(monkeypatch, tmp_path):
    from backend.app.ai import runtime
    source = tmp_path / "subject.jpg"
    Image.new("RGB", (300, 400), (200, 50, 50)).save(source)
    polygon = [[350, 120], [500, 100], [650, 120], [710, 230], [660, 400],
               [640, 850], [550, 900], [450, 900], [360, 850], [340, 400], [290, 230]]

    class Reply:
        data = {"objects": [{"label": "person", "box_2d": [100, 290, 900, 710], "mask": polygon}]}
        provenance = {"model": "test"}

    monkeypatch.setattr(runtime, "run_task", lambda *args, **kwargs: Reply())
    result = _gemini_segment(source, tmp_path / "cutout.png")
    assert result.status == "ready"
    assert result.provider == "gemini:test"
    with Image.open(result.mask_path) as cutout:
        alpha = cutout.getchannel("A")
        assert alpha.getpixel((150, 200)) > 245
        assert alpha.getpixel((5, 5)) < 10

    Reply.data = {"objects": [{"label": "person", "box_2d": [100, 290, 900, 710],
                               "mask": [[290, 100], [710, 100], [710, 900], [290, 900],
                                        [290, 100], [710, 100], [710, 900], [290, 900]]}]}
    invalid = _gemini_segment(source, tmp_path / "invalid.png")
    assert invalid.status == "unavailable"
    assert not (tmp_path / "invalid.png").exists()


def test_alpha_contour_is_traced_without_opencv(tmp_path):
    from PIL import ImageDraw
    path = tmp_path / "transparent-subject.png"
    image = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((20, 10, 280, 290), fill=(50, 70, 90, 255))
    draw.ellipse((105, 100, 195, 205), fill=(0, 0, 0, 0))
    image.save(path)
    rings = extract_alpha_rings(str(path), 100, 100)
    assert len(rings) == 1
    assert len(rings[0]["outer"]) >= 8
    assert len(rings[0]["holes"]) == 1
