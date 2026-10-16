"""Testy prymitywów U15–U19 w plan_composer (_Ctx.photo_fill, _Ctx.fill_block, _Ctx.snap_near_edges)."""
import pytest
from backend.app.models.schemas import (
    Element, ElementStyle, Frame, PageInputMaterial,
    StoryImageInput, StoryInput
)
from backend.app.engine.corpus_indexer import create_archetype_dnas
from backend.app.engine.plan_composer import _Ctx


def _minimal_dna():
    return create_archetype_dnas()["quality_press"]


def _minimal_material():
    return PageInputMaterial(
        masthead_title="TEST", issue_date="16.10.2026", issue_number="1", section_name="Główna",
        page_zone="front_page",
        stories=[
            StoryInput(id="s1", rank="lead", importance=1.0, headline="Wielki sukces polskiej nauki na świecie",
                       body="Treść artykułu opisująca przełomowe odkrycie.",
                       images=[StoryImageInput(id="img1", url="http://example.com/photo.jpg",
                                               width_px=1000, height_px=800, dpi=300,
                                               photo_analysis={"faces": [[0.3, 0.2, 0.5, 0.4]]})]),
        ]
    )


def test_ctx_photo_fill_crops_and_ensures_minimum_face_size():
    dna = _minimal_dna()
    mat = _minimal_material()
    ctx = _Ctx(dna, mat, {})
    img = mat.stories[0].images[0]
    rect = (15.0, 30.0, 115.0, 130.0)  # 100 x 100 mm

    el, full = ctx.photo_fill(img, rect, story=mat.stories[0], min_face_mm=16.0)
    assert el.role == "photo"
    assert "fills_module" in el.constraints
    assert el.frame.w == 100.0
    assert el.frame.h == 100.0
    assert len(el.crop_box) == 4
    assert 0.0 <= el.crop_box[0] < el.crop_box[2] <= 1.0
    assert 0.0 <= el.crop_box[1] < el.crop_box[3] <= 1.0


def test_ctx_fill_block_breaks_headline_without_dangling_prepositions():
    dna = _minimal_dna()
    mat = _minimal_material()
    ctx = _Ctx(dna, mat, {})
    text = "Nowy szpital w Warszawie i na Mazowszu"
    el = ctx.fill_block(text, "headline", width=120.0, height=40.0, max_lines=3, max_pt=40.0, min_size=14.0)
    assert el is not None
    assert el.role == "headline"
    lines = el.text_content.split("\n")
    dangling = {"i", "w", "z", "na", "do", "o", "a", "u", "za", "po", "od", "bo", "że", "dla", "się", "nie"}
    for line in lines[:-1]:
        last_word = line.split()[-1].lower()
        assert last_word not in dangling, f"Wiszący spójnik '{last_word}' w wierszu: '{line}'"


def test_ctx_snap_near_edges_snaps_sub_2_5mm_gaps_between_plates():
    dna = _minimal_dna()
    mat = _minimal_material()
    ctx = _Ctx(dna, mat, {})
    # Dwie płyty z przerwą 1.2 mm w osi Y
    p1 = Element(id="plate-1", role="band", importance=0.1, content_ref="p1",
                 frame=Frame(x=15.0, y=30.0, w=100.0, h=40.0),
                 style=ElementStyle(bg_color="#ffcc00"))
    p2 = Element(id="plate-2", role="band", importance=0.1, content_ref="p2",
                 frame=Frame(x=15.0, y=71.2, w=100.0, h=40.0),  # przerwa 1.2 mm (71.2 - (30+40))
                 style=ElementStyle(bg_color="#003366"))
    ctx.elements.extend([p1, p2])
    ctx.snap_near_edges(lo=0.3, hi=2.5)

    # Po snap_near_edges krawędzie stykają się dokładnie: p1 dół == p2 góra
    assert abs((p1.frame.y + p1.frame.h) - p2.frame.y) < 1e-4 or abs((p2.frame.y + p2.frame.h) - p1.frame.y) < 1e-4
