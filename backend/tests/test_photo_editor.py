from types import SimpleNamespace

from PIL import Image

from backend.app.ai import photo_editor
from backend.app.models.schemas import PageInputMaterial, StoryImageInput, StoryInput


def test_photo_editor_promotes_content_match_and_applies_focal_point(monkeypatch, tmp_path):
    paths = []
    for index in range(3):
        path = tmp_path / f"candidate-{index}.jpg"
        Image.new("RGB", (600, 400), (40 + index * 40, 80, 120)).save(path)
        paths.append(path)
    material = PageInputMaterial(stories=[StoryInput(
        id="lead", rank="lead", importance=1, headline="Tłum ucieka ze stacji",
        body="Reporter opisuje nagłe wydarzenie.", images=[
            StoryImageInput(id=f"image-{index}", url=str(path), caption=f"Kadr {index}",
                            width_px=600, height_px=400)
            for index, path in enumerate(paths)
        ])])

    def fake_run(*_args, **kwargs):
        assert len(kwargs["images"]) == 3
        return SimpleNamespace(data={"scores": [
            {"index": 0, "relevance": .3, "newsworthiness": .2, "technical_quality": .9,
             "depicts_claimed_subject": "unknown", "crop_suggestion": [], "risks": [], "reason": "spokojne"},
            {"index": 1, "relevance": .95, "newsworthiness": .9, "technical_quality": .8,
             "depicts_claimed_subject": "yes", "crop_suggestion": [100, 200, 900, 800], "risks": [], "reason": "dynamiczne"},
            {"index": 2, "relevance": .8, "newsworthiness": .8, "technical_quality": .9,
             "depicts_claimed_subject": "no", "crop_suggestion": [], "risks": [], "reason": "inny temat"},
        ]}, provenance={"provider": "gemini", "model": "test"})

    monkeypatch.setattr(photo_editor, "run_task", fake_run)
    selected, trace = photo_editor.select_story_photos(material, project_id="project")
    assert selected.stories[0].images[0].id == "image-1"
    assert selected.stories[0].images[0].focal_point == [.5, .5]
    assert trace[0]["status"] == "selected"
    assert trace[0]["reason"] == "dynamiczne"
    assert material.stories[0].images[0].id == "image-0", "source material stays immutable"


def test_photo_editor_keeps_user_order_when_assets_cannot_be_compared():
    material = PageInputMaterial(stories=[StoryInput(
        id="lead", headline="Materiał", body="Treść", images=[
            StoryImageInput(id="first", url="https://example.invalid/first.jpg"),
            StoryImageInput(id="second", url="https://example.invalid/second.jpg"),
        ])])
    selected, trace = photo_editor.select_story_photos(material)
    assert [image.id for image in selected.stories[0].images] == ["first", "second"]
    assert trace[0]["status"] == "insufficient_local_candidates"
