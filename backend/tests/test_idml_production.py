"""Structural production checks for IDML stories, spreads, and cutouts."""

from __future__ import annotations

import base64
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from backend.app.engine.renderers.idml_renderer import IDMLRenderer, MM_TO_PT
from backend.app.models.schemas import Element, ElementStyle, Frame, PageMeta, SceneGraph, TextWrap


def _text_scene(*, spread: bool = False) -> SceneGraph:
    page_width = 420.0 if spread else 210.0
    page = PageMeta(trim=[page_width, 297.0], page_zone="spread" if spread else "front_page")
    elements = [
        Element(
            id="headline-a",
            role="headline",
            text_content="A threaded headline",
            frame=Frame(x=12, y=12, w=120, h=24),
            style=ElementStyle(font_size_pt=22),
        ),
        Element(
            id="body-a",
            role="body",
            text_content="Pierwszy fragment tekstu",
            frame=Frame(x=12, y=48, w=90, h=90),
            style=ElementStyle(font_size_pt=9),
        ),
        Element(
            id="body-b",
            role="body",
            text_content="drugi fragment tekstu",
            frame=Frame(x=222 if spread else 108, y=48, w=90, h=90),
            style=ElementStyle(font_size_pt=9),
        ),
    ]
    metadata = {"text_threads": {"story-main": ["body-a", "body-b"]}}
    if spread:
        metadata["single_page_width_mm"] = 210.0
        metadata["page_count"] = 2
    return SceneGraph(page=page, elements=elements, metadata=metadata)


def _render(scene: SceneGraph, path: Path) -> zipfile.ZipFile:
    IDMLRenderer().render_to_zip(scene, str(path))
    return zipfile.ZipFile(path)


def test_text_threads_share_story_and_have_reciprocal_refs(tmp_path: Path):
    scene = _text_scene()
    with _render(scene, tmp_path / "threaded.idml") as package:
        spread = ET.fromstring(package.read("Spreads/Spread_u_spread_0.xml"))
        frames = {frame.attrib["Self"]: frame for frame in spread.findall(".//TextFrame")}
        assert frames["u_tf_body-a"].attrib["ParentStory"] == "u_story_story-main"
        assert frames["u_tf_body-b"].attrib["ParentStory"] == "u_story_story-main"
        assert frames["u_tf_body-a"].attrib["PreviousTextFrame"] == "n"
        assert frames["u_tf_body-a"].attrib["NextTextFrame"] == "u_tf_body-b"
        assert frames["u_tf_body-b"].attrib["PreviousTextFrame"] == "u_tf_body-a"
        assert frames["u_tf_body-b"].attrib["NextTextFrame"] == "n"

        story = ET.fromstring(package.read("Stories/Story_u_story_story-main.xml"))
        contents = [node.text or "" for node in story.findall(".//Content")]
        assert "Pierwszy fragment tekstu" in contents[0]
        assert "drugi fragment tekstu" in contents[1]
        assert list(package.namelist()).count("Stories/Story_u_story_story-main.xml") == 1
        # Independent headline remains an independent story/frame.
        assert "Stories/Story_u_story_headline-a.xml" in package.namelist()


def test_spread_emits_two_pages_and_preserves_canvas_coordinates(tmp_path: Path):
    scene = _text_scene(spread=True)
    with _render(scene, tmp_path / "spread.idml") as package:
        spread = ET.fromstring(package.read("Spreads/Spread_u_spread_0.xml"))
        root = spread.find("Spread")
        pages = root.findall("Page")
        assert root.attrib["PageCount"] == "2"
        assert len(pages) == 2
        first_bounds = [float(value) for value in pages[0].attrib["GeometricBounds"].split()]
        second_bounds = [float(value) for value in pages[1].attrib["GeometricBounds"].split()]
        assert first_bounds == pytest.approx([0.0, 0.0, 297.0 * MM_TO_PT, 210.0 * MM_TO_PT], abs=0.01)
        assert second_bounds[1] == pytest.approx(210.0 * MM_TO_PT, abs=0.01)
        assert second_bounds[3] == pytest.approx(420.0 * MM_TO_PT, abs=0.01)

        frame = next(frame for frame in root.findall("TextFrame") if frame.attrib["Self"] == "u_tf_body-b")
        bounds = [float(value) for value in frame.attrib["GeometricBounds"].split()]
        assert bounds[1] == pytest.approx(222.0 * MM_TO_PT, abs=0.01)
        assert bounds[3] == pytest.approx((222.0 + 90.0) * MM_TO_PT, abs=0.01)
        prefs = ET.fromstring(package.read("Resources/Preferences.xml"))
        pref = prefs.find("DocumentPreference")
        assert float(pref.attrib["PageWidth"]) == pytest.approx(210.0 * MM_TO_PT, abs=0.01)
        assert pref.attrib["PagesPerSpread"] == "2"


def test_cutout_path_and_local_link_are_packaged(tmp_path: Path):
    # A tiny valid PNG keeps this test independent of optional image tooling.
    pixel = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    image = tmp_path / "local.png"
    image.write_bytes(pixel)
    scene = SceneGraph(
        page=PageMeta(trim=[210, 297]),
        elements=[
            Element(
                id="cutout-1",
                role="photo",
                image_url=str(image),
                treatment="cutout",
                frame=Frame(x=10, y=20, w=80, h=60),
                contour_points=[[0, 0], [80, 0], [40, 60]],
                text_wrap=TextWrap(mode="contour", offset_mm=2),
            )
        ],
    )
    with _render(scene, tmp_path / "cutout.idml") as package:
        names = package.namelist()
        assert "Links/cutout-1.png" in names
        spread = ET.fromstring(package.read("Spreads/Spread_u_spread_0.xml"))
        rectangle = spread.find(".//Rectangle")
        points = rectangle.findall("./Properties/PathGeometry/GeometryPathType/PathPointArray/PathPointType")
        assert len(points) == 3
        # The first point is translated from frame-relative mm to page points.
        assert points[0].attrib["Anchor"] == f"{10 * MM_TO_PT:.2f} {20 * MM_TO_PT:.2f}"
        assert rectangle.find(".//Image/Link") is not None
        assert rectangle.find("TextWrapPreference/ContourOption").attrib["PathData"]
        # Parse every XML member, catching malformed packaging early.
        for name in names:
            if name.endswith(".xml"):
                ET.fromstring(package.read(name))
