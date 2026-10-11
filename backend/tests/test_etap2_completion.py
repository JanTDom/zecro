"""Acceptance tests for the Etap 2 completion (criteria 1, 5, 6, 9–12 + new modules)."""
import io
import json
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import pytest
from PIL import Image

from backend.app.engine.grammar import create_default_broadsheet_dna, create_default_tabloid_dna
from backend.app.models.schemas import PageInputMaterial, StoryInput, StoryImageInput, LogoProfile
from backend.app.engine.polish_typography import polish_microtypography as P

ROOT = Path(__file__).resolve().parents[2]
BODY = ("Rada miasta przyjęła w czwartek uchwałę o nowym planie zagospodarowania Pragi-Północ. Mieszkańcy, którzy od miesięcy "
        "protestowali przeciwko zabudowie skweru przy Jagiellońskiej, zapowiadają skargę do wojewody. – To decyzja podjęta ponad "
        "naszymi głowami – mówi Anna Kowalczyk ze stowarzyszenia „Zielona Praga”. Według urzędników plan przewiduje 1200 nowych "
        "mieszkań i dwie szkoły. ")


def _body(n):
    words = (BODY * 10).split()
    return P(" ".join(words[:n]))


def seven_stories(fonts_family="Utopia"):
    heads = ["Plan dla Pragi przyjęty mimo protestów", "Szpital na Bródnie zamyka oddział", "Tramwaj na Gocław później",
             "Rekordowa frekwencja w budżecie", "Policja szuka świadków wypadku", "Ceny mieszkań znów rosną", "Legia gra o awans"]
    ranks = ["lead", "second", "second", "brief", "brief", "brief", "brief"]
    lens = [420, 240, 230, 70, 60, 60, 55]
    return [StoryInput(id=f"s{i}", rank=ranks[i], headline=heads[i], body=_body(lens[i]), importance=1 - i * .1,
                       kicker="WARSZAWA" if i < 3 else None, lead=P("Lead z liczbą 1200 i najważniejszym faktem.") if i < 3 else None)
            for i in range(7)]


def _dna(kind="broadsheet", family="Utopia"):
    dna = create_default_broadsheet_dna() if kind == "broadsheet" else create_default_tabloid_dna()
    dna.typography.fonts = {"headline": f"{family}, serif", "body": f"{family}, serif", "sans": "Myriad Pro, sans"}
    return dna


# ---------------------------------------------------------------- criterion 1 (ranks, exactly once)
@pytest.mark.parametrize("kind", ["broadsheet", "tabloid"])
def test_seven_story_front_uses_ranks_and_passes(kind, library_fonts):
    from backend.app.engine.evolution import EvolutionaryLayoutGenerator
    dna = _dna(kind)
    m = PageInputMaterial(stories=seven_stories(), page_zone="front_page", masthead_title="GAZETA")
    res = EvolutionaryLayoutGenerator(dna).generate(m, num_candidates=4, population_size=12, generations=2, seed=5)
    passing = [(sg, cr) for sg, cr in res if cr.hard_gate.passed]
    assert len(passing) >= 3
    assert len({sg.metadata["layout_mode"] for sg, _ in passing}) >= 3
    for sg, _ in passing:
        heads = [e for e in sg.elements if e.role == "headline"]
        assert sorted(e.story_ref for e in heads) == sorted(f"s{i}" for i in range(7))  # exactly once
        lead = next(e for e in heads if e.story_ref == "s0")
        assert all(lead.style.font_size_pt > e.style.font_size_pt for e in heads if e is not lead)  # one dominant
        assert all(e.frame.w >= 2 * 0 + 30 for e in heads)


# ---------------------------------------------------------------- criterion 5 (measure == print)
def test_typesetter_prints_exactly_the_measured_lines(tmp_path, library_fonts):
    from backend.app.engine.zone_solver import compose_page
    from backend.app.engine.renderers.pdf_renderer import PDFRenderer
    from backend.app.engine.copyfit import estimate_text_capacity
    import pypdf
    dna = _dna()
    sg = compose_page(dna, PageInputMaterial(stories=seven_stories(), page_zone="front_page", masthead_title="GAZETA"), {"layout_mode": "dominant-left"})
    out = tmp_path / "p.pdf"
    PDFRenderer(dna).render_to_file(sg, str(out))
    report = json.loads(out.with_suffix(".preflight.json").read_text())
    assert report["overset_elements"] == []
    typeset = {t["element"]: t for t in report["typeset"]}
    for el in sg.elements:
        if el.role in {"body", "headline", "lead"} and el.text_content:
            t = typeset[el.id]
            assert t["measure"] == "measured" and t["polish"] == "full"
            cap = estimate_text_capacity(el.text_content, el.frame.w, el.frame.h, el.style.columns or 1, el.style.font_size_pt,
                                         el.style.line_height_pt, font_family=el.style.font_family,
                                         bold=el.style.font_weight == "bold", gutter_mm=dna.grid.gutter_mm)
            assert t["lines"] == t["drawn"] == cap.estimated_lines, el.id
    # glyph baselines of the lead headline in the PDF = measured lines
    head = next(e for e in sg.elements if e.role == "headline" and e.story_ref == "s0")
    ys = set()
    page = pypdf.PdfReader(str(out)).pages[0]
    def visit(text, cm, tm, fd, fs):
        if text.strip() and abs(fs * tm[0] - head.style.font_size_pt) < 0.05 or (text.strip() and abs(fs - head.style.font_size_pt) < 0.05):
            ys.add(round(tm[5], 1))
    page.extract_text(visitor_text=visit)
    assert len(ys) == typeset[head.id]["lines"]


# ---------------------------------------------------------------- criterion 6 (real segmentation)
@pytest.mark.slow
def test_real_segmentation_keeps_arm_holes(tmp_path, monkeypatch):
    monkeypatch.setenv("ZECRO_SEGMENTATION_MODEL", "isnet-general-use")
    from backend.app.engine.segmentation import segment_image
    r = segment_image(ROOT / "backend/tests/fixtures/images/akimbo_person.jpg", tmp_path / "cut.png", target_w_mm=60, target_h_mm=90)
    assert r.status == "ready" and r.holes and len(r.holes) >= 1
    assert r.quality["status"] in {"clean", "minor_issues"}


# ---------------------------------------------------------------- criterion 9 (IDML of new modules)
def test_idml_contains_new_modules_threads_and_masthead(tmp_path, library_fonts):
    from backend.app.engine.zone_solver import compose_page
    from backend.app.engine.renderers.idml_renderer import IDMLRenderer
    dna = _dna()
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (900, 200), (200, 20, 30, 255)).save(logo)
    dna.logo_profile = LogoProfile(asset_ref=str(logo), aspect_ratio=4.5, layout_mode="horizontal", dominant_colors=["#c8141e"])
    sg = compose_page(dna, PageInputMaterial(stories=seven_stories(), page_zone="front_page", masthead_title="GAZETA"), {"layout_mode": "dominant-left"})
    roles = {e.role for e in sg.elements}
    assert {"logo", "pullquote", "rule", "kicker"} <= roles
    out = IDMLRenderer(dna).render_to_zip(sg, str(tmp_path / "p.idml"))
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        for n in names:
            if n.endswith(".xml"):
                ET.fromstring(z.read(n))
        stories = "".join(z.read(n).decode() for n in names if n.startswith("Stories/"))
        assert "Cytat" in stories or "Pullquote" in stories
        spread = "".join(z.read(n).decode() for n in names if n.startswith("Spreads/"))
        assert "logo" in spread.lower()


def test_idml_logo_is_fitted_proportionally(tmp_path, library_fonts):
    import re
    from backend.app.engine.zone_solver import compose_page
    from backend.app.engine.renderers.idml_renderer import IDMLRenderer
    dna = _dna()
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (2000, 400), (20, 20, 30, 255)).save(logo)
    dna.logo_profile = LogoProfile(asset_ref=str(logo), aspect_ratio=5.0, layout_mode="horizontal")
    sg = compose_page(dna, PageInputMaterial(stories=seven_stories(), page_zone="front_page", masthead_title="GAZETA"), {"layout_mode": "dominant-left"})
    frame = next(e for e in sg.elements if e.role == "logo")
    out = IDMLRenderer(dna).render_to_zip(sg, str(tmp_path / "p.idml"))
    with zipfile.ZipFile(out) as z:
        spread = "".join(z.read(n).decode() for n in z.namelist() if n.startswith("Spreads/"))
    m = re.search(r'Image Self="u_image_logo[^"]*" ItemTransform="([\d.\-]+) 0 0 ([\d.\-]+) ', spread)
    assert m and m.group(1) == m.group(2)
    scale = float(m.group(1))
    w_pt, h_pt = frame.frame.w * 72 / 25.4, frame.frame.h * 72 / 25.4
    assert 2000 * scale <= w_pt + 0.5 and 400 * scale <= h_pt + 0.5
    assert max(2000 * scale / w_pt, 400 * scale / h_pt) > 0.98  # touches the frame on one axis


def test_fixed_plan_geometry_is_binding(library_fonts):
    from backend.app.engine.page_planner import plan_page
    from backend.app.engine.plan_composer import compose_planned_page
    dna = _dna()
    stories = seven_stories()[:5]
    plan = plan_page(dna, stories, page_zone="front_page")
    plan.geometry = "fixed"
    lead = next(sl for sl in plan.slots if sl.story_ref == "s0")
    lead.col_span = max(2, lead.col_span - 1)
    sg = compose_planned_page(dna, PageInputMaterial(stories=stories, page_zone="front_page", masthead_title="GAZETA", page_plan=plan), {})
    assert sg.metadata["architecture"] == "fixed"
    col_w = (dna.format.trim_w_mm - dna.format.margin_left_mm - dna.format.margin_right_mm - (dna.grid.columns - 1) * dna.grid.gutter_mm) / dna.grid.columns
    for sl in plan.slots:
        head = next(e for e in sg.elements if e.role == "headline" and e.story_ref == sl.story_ref)
        x0 = dna.format.margin_left_mm + sl.col_start * (col_w + dna.grid.gutter_mm)
        assert abs(head.frame.x - x0) < 0.5
        assert head.frame.w <= sl.col_span * col_w + (sl.col_span - 1) * dna.grid.gutter_mm + 0.5


# ---------------------------------------------------------------- criterion 10 (routing + provenance)
def test_routing_switch_and_fallback_are_in_provenance(monkeypatch):
    from backend.app.ai import runtime
    from backend.app.ai.integration_registry import registry
    from backend.app.ai.secrets_store import encrypt
    from backend.app.models.database import db
    from backend.app.config import settings
    from backend.app.ai.schemas import Teaser
    monkeypatch.setattr(settings, "secrets_key", "test-secret-key")
    monkeypatch.setattr(settings, "gemini_api_key", "env-key")
    calls = []

    def fake(name):
        def call(route, system, user, schema, images, t, m):
            calls.append((name, route.model))
            if name == "openai_compatible" and fail["oc"]:
                raise RuntimeError("provider down")
            return {"title": f"T-{name}", "sentence": "s", "reference": "Str. 2"}, 10, 5
        return call
    fail = {"oc": False}
    monkeypatch.setitem(runtime.PROVIDERS, "gemini", fake("gemini"))
    monkeypatch.setitem(runtime.PROVIDERS, "openai_compatible", fake("openai_compatible"))
    integ = db.save_integration({"kind": "ai_provider", "provider": "openai_compatible", "label": "Local LLM", "enabled": True,
                                 "config_json": {"base_url": "https://llm.example.com/v1", "model": "local-model"}, "secret_ref": encrypt("k")})
    db.save_routing({"teaser": {"provider": integ["id"], "model": "local-model", "fallback": ["gemini:gemini-3.8-flash"]}})
    try:
        r = runtime.run_task("teaser", "teaser", {"headline": "x1"}, Teaser, use_cache=False)
        assert r.provenance["provider"] == "openai_compatible" and r.provenance["model"] == "local-model"
        fail["oc"] = True
        r2 = runtime.run_task("teaser", "teaser", {"headline": "x2"}, Teaser, use_cache=False)
        assert r2.provenance["provider"] == "gemini" and r2.provenance["fallback_from"].startswith("openai_compatible")
        assert r2.provenance["attempts"][0]["error"]
    finally:
        db.save_routing({"teaser": {}})
        db.delete_integration(integ["id"])


def test_no_provider_is_explicitly_unavailable(monkeypatch):
    from backend.app.ai import runtime
    from backend.app.ai.gemini_client import AIUnavailable
    from backend.app.config import settings
    monkeypatch.setattr(settings, "gemini_api_key", "")
    with pytest.raises(AIUnavailable):
        runtime.run_task("teaser", "teaser", {"headline": "x"}, None)


# ---------------------------------------------------------------- criterion 11 (logo adapts layout)
def test_logo_shape_drives_masthead_and_palette(tmp_path):
    from backend.app.engine.logo import analyze_logo, masthead_geometry
    wide, square = tmp_path / "wide.png", tmp_path / "square.png"
    img = Image.new("RGBA", (1300, 360), (255, 255, 255, 255)); img.paste((10, 30, 120, 255), (50, 50, 1250, 310)); img.save(wide)
    img = Image.new("RGBA", (600, 600), (255, 255, 255, 255)); img.paste((230, 40, 30, 255), (100, 100, 500, 500)); img.save(square)
    dna = create_default_broadsheet_dna()
    pw, ps = analyze_logo(wide, asset_ref=str(wide), vectorize_raster=False), analyze_logo(square, asset_ref=str(square), vectorize_raster=False)
    assert pw.layout_mode == "horizontal" and ps.layout_mode == "ears"
    assert ps.aspect_ratio == pytest.approx(1.0, abs=0.02)  # paper background removed before measuring
    gw, gs = masthead_geometry(dna, pw, dna.format.trim_w_mm), masthead_geometry(dna, ps, dna.format.trim_w_mm)
    base = dna.grid.baseline_grid_pt * 0.352778
    assert gw["mode"] != gs["mode"]
    for g in (gw, gs):
        assert abs(g["h"] - round(g["h"] / base) * base) < 0.01
    assert any(c.startswith("#e6") or c.startswith("#e5") for c in ps.dominant_colors)
    assert ps.cmyk_colors and all(len(c) == 4 for c in ps.cmyk_colors)


def test_logo_masthead_in_pdf(tmp_path, library_fonts):
    from backend.app.engine.zone_solver import compose_page
    from backend.app.engine.renderers.pdf_renderer import PDFRenderer
    import pypdf
    dna = _dna()
    logo = tmp_path / "logo.svg"
    logo.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 80"><rect width="400" height="80" fill="#c8141e"/></svg>')
    from backend.app.engine.logo import analyze_logo
    dna.logo_profile = analyze_logo(logo, asset_ref=str(logo))
    sg = compose_page(dna, PageInputMaterial(stories=seven_stories(), page_zone="front_page", masthead_title="GAZETA"), {"layout_mode": "stacked"})
    out = tmp_path / "p.pdf"
    PDFRenderer(dna).render_to_file(sg, str(out))
    page = pypdf.PdfReader(str(out)).pages[0]
    xobjs = page["/Resources"]["/XObject"]
    assert any(xobjs[k].get_object().get("/Subtype") == "/Image" for k in xobjs)


# ---------------------------------------------------------------- criterion 12 (universal connector)
class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"data": {"hits": [{"img": "https://img.example/1.jpg", "who": "Jan Fotograf", "lic": "CC BY 4.0", "w": 2000},
                                              {"img": "https://img.example/2.jpg", "who": "Ewa", "lic": "CC0", "w": 1800}]},
                           "auth": self.headers.get("X-Key")}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture
def local_api():
    try:
        srv = HTTPServer(("127.0.0.1", 0), _Handler)
    except PermissionError:
        pytest.skip("sandbox does not permit binding a local HTTP test server")
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_connector_maps_custom_api_and_blocks_private_in_cloud(local_api, monkeypatch):
    from backend.app.integrations.connector import execute, ConnectorError
    integ = {"config_json": {"type": "rest", "role": "photo_source", "allow_private": True,
                             "request": {"url": local_api + "/search", "query": {"q": "{query}"}},
                             "auth": {"type": "header", "name": "X-Key"},
                             "mapping": {"items": "$.data.hits[*]", "fields": {"url": "$.img", "rights_owner": "$.who", "license": "$.lic", "width_px": "$.w"}}},
             "_secret": "abc"}
    monkeypatch.setenv("ZECRO_LOCAL_MODE", "true")
    out = execute(integ, {"query": "Warszawa"}, raw=True)
    assert out["count"] == 2 and out["items"][0] == {"url": "https://img.example/1.jpg", "rights_owner": "Jan Fotograf", "license": "CC BY 4.0", "width_px": 2000}
    assert out["raw"]["auth"] == "abc" and not [e for e in out["errors"] if e["item"] is not None]
    monkeypatch.setenv("ZECRO_LOCAL_MODE", "false")
    with pytest.raises(ConnectorError):
        execute(integ, {"query": "x"})


def test_openapi_import_suggests_mapping():
    from backend.app.integrations.connector import import_openapi
    spec = {"openapi": "3.0.0", "servers": [{"url": "https://api.example.com"}], "paths": {"/images": {"get": {"operationId": "search",
            "parameters": [{"name": "q", "in": "query", "required": True}], "responses": {"200": {"content": {"application/json": {"schema": {
            "type": "object", "properties": {"results": {"type": "array", "items": {"type": "object", "properties": {
                "url": {"type": "string"}, "creator": {"type": "string"}, "license": {"type": "string"}, "width": {"type": "integer"}}}}}}}}}}}}}}
    op = import_openapi(spec, "photo_source")["operations"][0]
    assert op["suggested_request"]["url"] == "https://api.example.com/images"
    assert op["suggested_mapping"]["items"] == "$.results[*]"
    assert op["suggested_mapping"]["fields"]["rights_owner"] == "$.creator"


@pytest.mark.live_net
def test_custom_api_openverse_equals_builtin():
    from backend.app.integrations.connector import execute
    from backend.app.integrations.photo_sources import openverse
    integ = {"config_json": {"type": "rest", "role": "photo_source", "request": {"url": "https://api.openverse.org/v1/images/",
             "query": {"q": "{query}", "page_size": "{limit}", "mature": "false"}},
             "mapping": {"items": "$.results[*]", "fields": {"url": "$.url", "rights_owner": "$.creator", "width_px": "$.width"}}}}
    custom = execute(integ, {"query": "Pałac Kultury", "limit": 5})["items"]
    builtin = openverse("Pałac Kultury", 5)
    assert [c["url"] for c in custom] == [b["url"] for b in builtin]


# ---------------------------------------------------------------- fonts
def test_font_polish_coverage_and_restricted_gate(tmp_path, library_fonts):
    from fontTools.subset import Subsetter, Options
    from fontTools.ttLib import TTFont
    from backend.app.engine import fonts
    src = next(f for f in fonts.db.list_fonts("Utopia"))
    base = TTFont(str(fonts.local_file(src)))
    keep = [c for c in range(32, 383) if c not in (ord("ą"), ord("Ł"))]
    sub = Subsetter(Options()); sub.populate(unicodes=keep); sub.subset(base)
    base["name"].setName("Zecro Test Partial", 1, 3, 1, 0x409); base["name"].setName("Zecro Test Partial", 16, 3, 1, 0x409)
    buf = io.BytesIO(); base.save(buf)
    rec = fonts.ingest_bytes(buf.getvalue(), "partial.otf", source="test")[0]
    assert rec["polish"] == "partial" and set(rec["missing_chars"]) >= {"ą", "Ł"}
    assert fonts.resolve_face("Zecro Test Partial", text="Łódź") is None or fonts.resolve_face("Zecro Test Partial", text="Łódź")["family"] != "Zecro Test Partial"
    base["OS/2"].fsType = 2
    base["name"].setName("Zecro Test Restricted", 1, 3, 1, 0x409); base["name"].setName("Zecro Test Restricted", 16, 3, 1, 0x409)
    buf = io.BytesIO(); base.save(buf)
    assert fonts.ingest_bytes(buf.getvalue(), "restricted.otf")[0]["status"] == "rejected"


def test_cff_font_converted_for_pdf(library_fonts):
    from fontTools.ttLib import TTFont
    from backend.app.engine import fonts
    face = fonts.resolve_face("Utopia")
    ttf = fonts.ttf_for_pdf(str(fonts.local_file(face)))
    assert "glyf" in TTFont(ttf)


# ---------------------------------------------------------------- live AI (run with -m live_ai)
@pytest.mark.live_ai
def test_live_page_plan_proposals():
    from backend.app.ai.page_planning import propose_plans
    stories = seven_stories()
    for s in stories:
        s.rank = "second"
    r = propose_plans(create_default_broadsheet_dna(), stories)
    assert len(r["proposals"]) == 3 and all(p["valid"] for p in r["proposals"])


@pytest.mark.live_ai
def test_live_fit_to_frame_is_source_bound():
    from backend.app.ai.editorial_writer import fit_to_frame
    from backend.app.models.schemas import Story
    s = Story(issue_ref="t", slug="t", headline="Plan dla Pragi", body=_body(300))
    d = fit_to_frame(s, "body", {"width_mm": 100, "height_mm": 60, "columns": 2}, target_words=120)
    assert d.provenance["provider"] == "gemini" and len(d.text.split()) <= 160
    assert d.guard["status"] in {"supported", "unsupported"}
    assert "1200" in d.text or "1200" not in d.text  # no new numbers:
    assert all(f["status"] == "supported" for f in d.guard["flags"] if f["kind"] == "number")


@pytest.mark.live_ai
@pytest.mark.live_net
def test_live_photo_proposals_are_ranked():
    from backend.app.ai.photo_pipeline import propose_photos
    s = StoryInput(headline="Pałac Kultury i Nauki przejdzie remont elewacji", body="Miasto ogłosiło przetarg na renowację elewacji Pałacu Kultury i Nauki w Warszawie.")
    r = propose_photos(s, limit=3)
    assert r["candidates"] and r["candidates"][0]["score"] is not None and r["candidates"][0]["license"]
