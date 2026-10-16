import os
import tempfile
import zipfile
import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader
from backend.app.models.schemas import PageInputMaterial, StoryInput, StoryImageInput
from backend.app.models.schemas import Element, Frame, PageMeta, SceneGraph
from backend.app.engine.grammar import create_default_broadsheet_dna
from backend.app.engine.solver import GridSolver
from backend.app.engine.renderers.svg_renderer import SVGRenderer
from backend.app.engine.renderers.html_renderer import HTMLRenderer
from backend.app.engine.renderers.pdf_renderer import PDFRenderer
from backend.app.engine.renderers.idml_renderer import IDMLRenderer

@pytest.fixture
def sample_scene_graph():
    dna = create_default_broadsheet_dna()
    solver = GridSolver(dna)
    material = PageInputMaterial(
        masthead_title="THE DAILY CHRONICLE",
        stories=[
            StoryInput(
                id="s1",
                kicker="ARCHITECTURE",
                headline="SCENE GRAPH RENDERING IN PRODUCTION",
                lead="Demonstrating SVG, HTML, PDF and IDML export capabilities.",
                body="Paragraph copy formatted into modular columns.",
                importance=1.0,
                images=[
                    StoryImageInput(
                        id="img-1",
                        url="https://example.com/building.jpg",
                        caption="A historic spire.",
                        importance=0.9,
                        is_cutout_candidate=True
                    )
                ]
            )
        ]
    )
    return solver.solve(material)

def test_svg_renderer(sample_scene_graph):
    dna = create_default_broadsheet_dna()
    renderer = SVGRenderer(dna)
    svg_output = renderer.render(sample_scene_graph)

    assert svg_output.startswith("<svg")
    assert svg_output.endswith("</svg>")
    assert "THE DAILY CHRONICLE" in svg_output
    assert "SCENE GRAPH RENDERING" in svg_output

def test_html_renderer(sample_scene_graph):
    dna = create_default_broadsheet_dna()
    renderer = HTMLRenderer(dna)
    html_output = renderer.render(sample_scene_graph)

    assert "<!DOCTYPE html>" in html_output
    assert "@page" in html_output
    assert "page-sheet" in html_output
    assert "SCENE GRAPH RENDERING" in html_output

def test_pdf_renderer(sample_scene_graph):
    dna = create_default_broadsheet_dna()
    renderer = PDFRenderer(dna)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = f.name

    try:
        renderer.render_to_file(sample_scene_graph, pdf_path)
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 0
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


def test_pdf_cutout_keeps_alpha_soft_mask(tmp_path):
    source = Image.new("RGBA", (240, 240), (225, 30, 30, 0))
    ImageDraw.Draw(source).ellipse((30, 10, 220, 235), fill=(225, 30, 30, 255))
    image_path = tmp_path / "person.png"
    source.save(image_path)
    dna = create_default_broadsheet_dna()
    scene = SceneGraph(
        page=PageMeta(trim=[210, 297], bleed_mm=3, safe_margin_mm=10,
                      grid={"cols": 4, "gutter_mm": 4, "baseline_mm": 4},
                      title_dna_ref=dna.id),
        elements=[Element(id="person", role="photo", importance=.8,
                          content_ref="person.image", image_url=str(image_path),
                          mask_ref=str(image_path), treatment="cutout",
                          contour_points=[[5, 25], [9, 6], [32, 1], [58, 4],
                                          [76, 18], [80, 75], [50, 80], [10, 70]],
                          frame=Frame(x=20, y=20, w=80, h=80))],
    )
    out = tmp_path / "cutout.pdf"
    PDFRenderer(dna).render_to_file(scene, str(out))
    xobjects = PdfReader(str(out)).pages[0]["/Resources"]["/XObject"]
    assert any("/SMask" in obj.get_object() for obj in xobjects.values())

def test_idml_renderer(sample_scene_graph):
    dna = create_default_broadsheet_dna()
    renderer = IDMLRenderer(dna)
    with tempfile.NamedTemporaryFile(suffix=".idml", delete=False) as f:
        idml_path = f.name

    try:
        renderer.render_to_zip(sample_scene_graph, idml_path)
        assert os.path.exists(idml_path)
        assert os.path.getsize(idml_path) > 100

        # Verify IDML internal ZIP structure
        with zipfile.ZipFile(idml_path, "r") as zf:
            file_list = zf.namelist()
            assert "mimetype" in file_list
            assert "META-INF/container.xml" in file_list
            assert "designmap.xml" in file_list
            assert "Resources/Styles.xml" in file_list
            assert "Resources/Preferences.xml" in file_list
            assert "Spreads/Spread_u_spread_0.xml" in file_list
            assert any(f.startswith("Stories/Story_") for f in file_list)
    finally:
        if os.path.exists(idml_path):
            os.remove(idml_path)
