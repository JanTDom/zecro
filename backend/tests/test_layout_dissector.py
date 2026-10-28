"""Unit tests for LayoutDissector (IDML and PDF layout extraction)."""
from __future__ import annotations

import zipfile
import pytest
from pathlib import Path
from backend.app.engine.layout_dissector import LayoutDissector
from backend.app.models.schemas import Element, ElementStyle, Frame, PageMeta, SceneGraph
from backend.app.engine.renderers.idml_renderer import IDMLRenderer
from backend.app.engine.renderers.pdf_renderer import PDFRenderer


def _create_sample_idml_file(tmp_path: Path) -> Path:
    """Generate a valid sample IDML package using IDMLRenderer."""
    page = PageMeta(trim=[280.0, 400.0], page_zone="front_page")
    elements = [
        Element(
            id="main_title",
            role="headline",
            text_content="WIELKA REWOLUCJA NA KOLEI W WARSZAWIE",
            frame=Frame(x=15.0, y=20.0, w=250.0, h=30.0),
            z=2,
            style=ElementStyle(font_size_pt=36.0, font_weight="bold"),
        ),
        Element(
            id="lead_body",
            role="lead",
            text_content="Nowe składy pojadą szybciej niż kiedykolwiek wcześniej w historii spółki.",
            frame=Frame(x=15.0, y=55.0, w=160.0, h=25.0),
            z=2,
            style=ElementStyle(font_size_pt=14.0),
        ),
        Element(
            id="hero_photo",
            role="photo",
            frame=Frame(x=15.0, y=85.0, w=160.0, h=120.0),
            z=1,
            treatment="crop",
            importance=0.9,
        ),
        Element(
            id="col_text",
            role="body",
            text_content="Pasażerowie czekali na ten krok od wielu lat. Pierwsze pociągi wyjadą już w poniedziałek.",
            frame=Frame(x=185.0, y=55.0, w=80.0, h=150.0),
            z=2,
            style=ElementStyle(font_size_pt=9.5),
        ),
    ]
    scene = SceneGraph(page=page, elements=elements)
    idml_path = tmp_path / "sample.idml"
    IDMLRenderer().render_to_zip(scene, str(idml_path))
    return idml_path


def test_dissect_idml_extracts_scene_graph_and_dna(tmp_path: Path):
    idml_path = _create_sample_idml_file(tmp_path)
    dissector = LayoutDissector()
    scene, dna, meta = dissector.dissect_idml(idml_path, title_name="Głos Kolejowy")

    assert scene is not None
    assert len(scene.elements) >= 3
    assert scene.page.trim == [280.0, 400.0]

    roles = {e.role for e in scene.elements}
    assert "headline" in roles or "body" in roles

    # DNA extraction assertions
    assert dna.format.trim_w_mm == 280.0
    assert dna.format.trim_h_mm == 400.0
    assert dna.grid.columns in (5, 6)
    assert meta["detected_elements_count"] >= 3


def test_dissect_pdf_extracts_geometry(tmp_path: Path):
    scene = SceneGraph(
        page=PageMeta(trim=[210.0, 297.0]),
        elements=[
            Element(
                id="pdf_h1",
                role="headline",
                text_content="TYTUŁ PRASOWY",
                frame=Frame(x=15.0, y=20.0, w=180.0, h=20.0),
                style=ElementStyle(font_size_pt=28.0),
            ),
            Element(
                id="pdf_p1",
                role="body",
                text_content="To jest artykuł informacyjny o bieżących wydarzeniach.",
                frame=Frame(x=15.0, y=45.0, w=90.0, h=80.0),
                style=ElementStyle(font_size_pt=10.0),
            ),
        ],
    )
    pdf_path = tmp_path / "test_press.pdf"
    PDFRenderer().render_to_file(scene, str(pdf_path))

    dissector = LayoutDissector()
    extracted_scene, dna, meta = dissector.dissect_pdf(pdf_path, title_name="Biuletyn")

    assert extracted_scene is not None
    assert extracted_scene.page.trim[0] == pytest.approx(210.0, abs=2.0)
    assert extracted_scene.page.trim[1] == pytest.approx(297.0, abs=2.0)
    assert meta["elements_count"] >= 1
