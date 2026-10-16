"""Category covers must differ in information architecture, not only type size."""

from backend.app.engine.corpus_indexer import create_archetype_dnas
from backend.app.engine.critic import LayoutCritic
from backend.app.engine.evolution import EvolutionaryLayoutGenerator, LayoutGenome
from backend.app.engine.plan_composer import compose_planned_page
from backend.app.engine.renderers.svg_renderer import SVGRenderer
from backend.app.models.schemas import PageInputMaterial, StoryImageInput, StoryInput


def _material():
    return PageInputMaterial(
        masthead_title="Wydanie próbne", issue_date="13.10.2026", issue_number="1",
        section_name="Miasto", page_zone="front_page",
        stories=[
            StoryInput(id="a", rank="lead", importance=1.0, kicker="MIASTO",
                       headline="Nowy pomysł na życie nad rzeką",
                       deck="Mieszkańcy rozmawiają o zmianach.",
                       lead="Projekt daje miastu nowe miejsca spotkań.",
                       body="Redakcja opisuje plan zmian nad rzeką. Mieszkańcy oglądają nowe propozycje. " * 8,
                       images=[StoryImageInput(id="im", url="/tmp/test-cover-photo.jpg",
                                               width_px=3000, height_px=2000, dpi=300)]),
            StoryInput(id="b", rank="second", importance=.7, headline="Powstanie nowa czytelnia",
                       body="Biblioteka przygotowuje miejsce na warsztaty i spotkania. " * 4),
            StoryInput(id="c", rank="third", importance=.5, headline="Zmiany w centrum miasta",
                       body="Samorząd przedstawia plan reorganizacji ulic. " * 4),
        ],
    )


def test_cover_categories_change_composition_and_pass_hard_gate():
    profiles = create_archetype_dnas()
    scenes = {}
    for key in ("quality_press", "tabloid", "editorial_magazine", "tv_guide"):
        dna = profiles[key]
        material = _material()
        material.style_blend = dna.style_blend
        scene = compose_planned_page(dna, material, {"layout_mode": "dominant-left"})
        gate = LayoutCritic(dna).evaluate_hard_gate(scene)
        assert gate.passed, (key, gate.violations)
        assert not scene.metadata.get("missing_content_refs"), key
        scenes[key] = scene

    assert len({scenes[key].metadata["architecture"] for key in scenes}) == 4
    logos = {key: next(e for e in scene.elements if e.role == "logo") for key, scene in scenes.items()}
    assert logos["tabloid"].style.color == profiles["tabloid"].palette.secondary
    assert not logos["editorial_magazine"].style.bg_color
    assert logos["tv_guide"].style.bg_color

    def teaser_after_logo(scene):
        logo = next(e for e in scene.elements if e.role == "logo")
        return any(e.role == "headline" and e.story_ref == "b" and e.frame.y > logo.frame.y for e in scene.elements)

    assert teaser_after_logo(scenes["tabloid"])
    assert teaser_after_logo(scenes["editorial_magazine"])
    assert teaser_after_logo(scenes["tv_guide"])


def test_saved_tabloid_dna_without_new_grammar_still_uses_popular_cover():
    dna = create_archetype_dnas()["tabloid"]
    dna.cover_grammar = {}
    material = _material()
    material.style_blend = dna.style_blend
    scene = compose_planned_page(dna, material, {"layout_mode": "dominant-left"})
    assert scene.metadata["architecture"] == "popular_collage"


def test_svg_preview_uses_title_dna_masthead_font_and_alignment():
    dna = create_archetype_dnas()["tabloid"]
    material = _material()
    material.style_blend = dna.style_blend
    scene = compose_planned_page(dna, material, {"layout_mode": "dominant-left"})
    logo = next(e for e in scene.elements if e.role == "logo")
    svg = SVGRenderer(dna).render(scene)
    assert f'font-family="{logo.style.font_family}, sans-serif"' in svg
    assert 'text-anchor="start"' in svg


def test_popular_cover_genome_changes_image_and_teaser_architecture():
    dna = create_archetype_dnas()["tabloid"]
    material = _material()
    material.style_blend = dna.style_blend
    scenes = {mode: compose_planned_page(dna, material, {"layout_mode": mode})
              for mode in ("dominant-left", "dominant-right", "stacked", "photo-top", "modular-grid")}
    photos = {mode: next(e for e in scene.elements if e.role == "photo") for mode, scene in scenes.items()}
    assert photos["dominant-left"].frame.x > photos["dominant-right"].frame.x
    assert photos["photo-top"].frame.w > photos["modular-grid"].frame.w
    for scene in scenes.values():
        logo_y = next(e.frame.y for e in scene.elements if e.role == "logo")
        assert all(logo_y < e.frame.y for e in scene.elements if e.role == "photo")
    assert any("overlap-scrim" in e.transgressions for e in scenes["photo-top"].elements)
    collage_headline = next(e for e in scenes["dominant-left"].elements
                            if e.role == "headline" and e.story_ref == "a")
    assert collage_headline.text_content.count("\n") == 1
    assert collage_headline.text_content.replace("\n", " ") == material.stories[0].headline


def test_sparse_popular_cover_expands_hero_and_rejects_forgotten_quadrant():
    dna = create_archetype_dnas()["tabloid"]
    material = _material()
    material.style_blend = dna.style_blend
    lead = material.stories[0]
    lead.kicker = ""
    lead.deck = ""
    lead.lead = ""
    scene = compose_planned_page(dna, material, {"layout_mode": "dominant-right"})
    hero = next(e for e in scene.elements if e.role == "photo" and e.story_ref == "a")
    printable_width = dna.format.trim_w_mm - dna.format.margin_left_mm - dna.format.margin_right_mm
    assert hero.frame.w == printable_width
    assert hero.treatment == "crop"
    assert LayoutCritic(dna).evaluate_hard_gate(scene).passed

    # Simulate the historical failure: the hero occupied only half the page
    # while the other half contained no editorial module.  This must be a hard
    # failure, regardless of the candidate's soft balance score.
    hero.frame.w *= .5
    gate = LayoutCritic(dna).evaluate_hard_gate(scene)
    assert not gate.passed
    assert any("large uncomposed empty region" in reason for reason in gate.violations)


def test_popular_cover_keeps_seven_stories_readable():
    dna = create_archetype_dnas()["tabloid"]
    material = _material()
    material.style_blend = dna.style_blend
    for index in range(4):
        material.stories.append(StoryInput(
            id=f"extra-{index}", rank="second", importance=.4 - index * .05,
            kicker="WIADOMOŚCI", headline=f"Ważna wiadomość numer {index} dla miasta",
            body="Krótki opis wydarzenia w mieście. " * 15,
        ))
    for mode in ("dominant-left", "stacked", "modular-grid"):
        scene = compose_planned_page(dna, material, {"layout_mode": mode})
        assert not scene.metadata["missing_content_refs"]
        assert LayoutCritic(dna).evaluate_hard_gate(scene).passed


def test_photo_led_tabloid_uses_real_print_resolution_and_keeps_five_stories():
    dna = create_archetype_dnas()["tabloid"]
    material = _material()
    material.style_blend = dna.style_blend
    for story in material.stories[1:]:
        story.images = [StoryImageInput(id=f"photo-{story.id}", url=f"/tmp/{story.id}.jpg",
                                        width_px=3000, height_px=2000, dpi=300)]
    for index in range(2):
        material.stories.append(StoryInput(
            id=f"teaser-{index}", rank="second", importance=.4 - index * .1,
            kicker="MIASTO", headline=f"Ważny temat numer {index + 1}",
            body="Redakcja opisuje próbny temat w mieście. " * 5,
            images=[StoryImageInput(id=f"teaser-photo-{index}", url=f"/tmp/teaser-{index}.jpg",
                                    width_px=3000, height_px=2000, dpi=300)],
        ))
    scene = compose_planned_page(dna, material, {"layout_mode": "photo-top"})
    assert scene.metadata["architecture"] == "popular_poster"
    assert scene.metadata["style_readiness"]["photo_story_count"] == 5
    assert not scene.metadata["missing_content_refs"]
    assert sum(e.role == "photo" for e in scene.elements) == 5
    assert LayoutCritic(dna).evaluate_hard_gate(scene).passed

    material.stories[0].images[0].width_px = 700
    low_resolution = compose_planned_page(dna, material, {"layout_mode": "photo-top"})
    assert low_resolution.metadata["architecture"] == "popular_collage"


def test_poster_skyline_uses_portrait_focal_point_without_overriding_editor():
    dna = create_archetype_dnas()["tabloid"]
    material = _material()
    material.style_blend = dna.style_blend
    for story in material.stories[1:]:
        story.images = [StoryImageInput(id=f"photo-{story.id}", url=f"/tmp/{story.id}.jpg",
                                        width_px=2400, height_px=4200, dpi=300)]
    for index in range(2):
        material.stories.append(StoryInput(
            id=f"teaser-{index}", rank="second", importance=.4 - index * .1,
            headline="Pytania o życie w mieście", body="Próbna wiadomość dla mieszkańców.",
            images=[StoryImageInput(id=f"teaser-photo-{index}", url=f"/tmp/teaser-{index}.jpg",
                                    width_px=3000, height_px=2000, dpi=300)],
        ))
    scene = compose_planned_page(dna, material, {"layout_mode": "photo-top"})
    skyline_photo = next(e for e in scene.elements if e.role == "photo" and e.story_ref == "b")
    assert skyline_photo.focal_point == [.5, .34]
    assert any(item["action"] == "portrait_skyline_focal" for item in scene.metadata["fit_adjustments"])

    material.stories[1].images[0].focal_point = [.6, .68]
    edited = compose_planned_page(dna, material, {"layout_mode": "photo-top"})
    skyline_photo = next(e for e in edited.elements if e.role == "photo" and e.story_ref == "b")
    assert skyline_photo.focal_point == [.6, .68]


def test_poster_places_source_bound_badge_on_crop_without_breaking_gate():
    dna = create_archetype_dnas()["tabloid"]
    material = _material()
    material.style_blend = dna.style_blend
    for story in material.stories[1:]:
        story.images = [StoryImageInput(id=f"photo-{story.id}", url=f"/tmp/{story.id}.jpg",
                                        width_px=3000, height_px=2000, dpi=300)]
    for index in range(2):
        material.stories.append(StoryInput(
            id=f"badge-extra-{index}", rank="second", importance=.35,
            headline="Kolejny temat dla mieszkańców", body="Krótka informacja redakcyjna.",
            images=[StoryImageInput(id=f"badge-photo-{index}", url=f"/tmp/badge-{index}.jpg",
                                    width_px=3000, height_px=2000, dpi=300)],
        ))
    scene = compose_planned_page(dna, material, {"layout_mode": "photo-top", "photo_treatment": "crop"})
    badge = next(e for e in scene.elements
                 if e.role == "kicker" and e.story_ref == "a" and "intentional_photo_badge" in e.constraints)
    hero = next(e for e in scene.elements if e.role == "photo" and e.story_ref == "a")
    assert badge.text_content == material.stories[0].kicker.upper()
    assert badge.frame.rotation_deg < 0
    assert badge.frame.y >= hero.frame.y
    assert LayoutCritic(dna).evaluate_hard_gate(scene).passed


def test_poster_places_real_subject_contour_over_editable_colour_field():
    dna = create_archetype_dnas()["tabloid"]
    material = _material()
    material.style_blend = dna.style_blend
    material.stories[0].images[0].contour_polygon = [
        [30, 0], [41, 1], [50, 9], [58, 20], [64, 21], [79, 33],
        [86, 56], [80, 99], [18, 99], [14, 57], [24, 30], [30, 0],
    ]
    for story in material.stories[1:]:
        story.images = [StoryImageInput(id=f"photo-{story.id}", url=f"/tmp/{story.id}.jpg",
                                        width_px=3000, height_px=2000, dpi=300)]
    for index in range(2):
        material.stories.append(StoryInput(
            id=f"extra-{index}", rank="second", importance=.4 - index * .1,
            headline="Pytania o życie w mieście", body="Próbna wiadomość dla mieszkańców.",
            images=[StoryImageInput(id=f"extra-photo-{index}", url=f"/tmp/extra-{index}.jpg",
                                    width_px=3000, height_px=2000, dpi=300)],
        ))
    scene = compose_planned_page(dna, material, {"layout_mode": "photo-top", "photo_treatment": "cutout"})
    hero = next(e for e in scene.elements if e.role == "photo" and e.story_ref == "a")
    field = next(e for e in scene.elements if e.id == "hero-field-a")
    assert hero.treatment == "cutout"
    assert hero.contour_points and len(hero.contour_points) >= 8
    assert field.frame.x == hero.frame.x and field.frame.w == hero.frame.w
    assert hero.frame.y < field.frame.y and field.z < hero.z
    assert any(e.role == "kicker" and e.story_ref == "a" and e.style.bg_color
               for e in scene.elements)
    assert scene.metadata["cover_morphology"] == "subject_cutout_collage"
    assert LayoutCritic(dna).evaluate_hard_gate(scene).passed
    cropped = compose_planned_page(dna, material, {"layout_mode": "photo-top", "photo_treatment": "crop"})
    assert not any(e.id == "hero-field-a" for e in cropped.elements)
    assert next(e for e in cropped.elements if e.role == "photo" and e.story_ref == "a").treatment == "crop"


def test_poster_rebalances_main_headline_and_preserves_editorial_words(library_fonts):
    dna = create_archetype_dnas()["tabloid"]
    material = _material()
    material.style_blend = dna.style_blend
    material.stories[0].headline = "Nie mamy jak wrócić do domu!"
    for index, story in enumerate(material.stories[1:], start=1):
        story.images = [StoryImageInput(id=f"photo-{index}", url=f"/tmp/{index}.jpg",
                                        width_px=3000, height_px=2000, dpi=300)]
    for index in range(2):
        material.stories.append(StoryInput(
            id=f"extra-{index}", rank="second", importance=.35,
            headline="Pytania o życie w mieście", body="Próbna wiadomość dla mieszkańców.",
            images=[StoryImageInput(id=f"more-{index}", url=f"/tmp/more-{index}.jpg",
                                    width_px=3000, height_px=2000, dpi=300)],
        ))
    scene = compose_planned_page(dna, material, {"layout_mode": "photo-top"})
    headline = next(e for e in scene.elements if e.role == "headline" and e.importance >= .95)
    assert headline.text_content.replace("\n", " ") == material.stories[0].headline
    assert headline.text_content.split("\n") == ["Nie mamy jak", "wrócić do domu!"]
    assert headline.style.font_family in dna.cover_grammar["display_font_candidates"]
    assert headline.style.outline_width_pt > 0
    assert LayoutCritic(dna).evaluate_hard_gate(scene).passed

    headline.text_content = "Nie mamy jak wrócić do\ndomu!"
    assert any("single word" in reason for reason in LayoutCritic(dna).evaluate_hard_gate(scene).violations)

    overlay = compose_planned_page(dna, material, {"layout_mode": "photo-top",
                                                   "poster_headline_treatment": "overlay"})
    overlay_heads = sorted((e for e in overlay.elements if e.role == "headline" and e.importance >= .95),
                           key=lambda e: e.frame.y)
    assert overlay.metadata["cover_morphology"] == "photo_overlay_collage"
    assert len(overlay_heads) == 2
    assert " ".join(e.text_content for e in overlay_heads) == material.stories[0].headline
    assert all(e.style.bg_color is None for e in overlay_heads)
    assert all(e.style.outline_width_pt >= 1 for e in overlay_heads)
    assert LayoutCritic(dna).evaluate_hard_gate(overlay).passed


def test_type_led_cover_requires_portrait_and_keeps_story_complete(library_fonts):
    dna = create_archetype_dnas()["tabloid"]
    material = _material()
    material.style_blend = dna.style_blend
    material.stories[0].headline = "Nie mamy jak wrócić do domu!"
    material.stories[0].images[0].width_px = 2400
    material.stories[0].images[0].height_px = 3200
    for index, story in enumerate(material.stories[1:], start=1):
        story.images = [StoryImageInput(id=f"photo-{index}", url=f"/tmp/{index}.jpg",
                                        width_px=3000, height_px=2000, dpi=300)]
    for index in range(2):
        material.stories.append(StoryInput(
            id=f"extra-{index}", rank="second", importance=.35,
            headline="Pytania o życie w mieście", body="Próbna wiadomość dla mieszkańców.",
            images=[StoryImageInput(id=f"more-{index}", url=f"/tmp/more-{index}.jpg",
                                    width_px=3000, height_px=2000, dpi=300)],
        ))
    scene = compose_planned_page(dna, material, {"layout_mode": "type-led"})
    assert scene.metadata["architecture"] == "popular_type_led"
    assert not scene.metadata["missing_content_refs"]
    assert sum(e.role == "photo" for e in scene.elements) == 5
    headlines = sorted((e for e in scene.elements if e.role == "headline" and e.importance >= .95),
                       key=lambda e: e.frame.y)
    assert " ".join(e.text_content for e in headlines) == material.stories[0].headline
    assert len(headlines[-1].text_content.split()) > 1
    assert len({e.style.color for e in headlines}) > 1
    decks = [e for e in scene.elements if e.role == "deck" and e.story_ref == "a"]
    assert decks and decks[0].frame.y > headlines[-1].frame.y + headlines[-1].frame.h
    assert LayoutCritic(dna).evaluate_hard_gate(scene).passed

    material.stories[0].images[0].contour_polygon = [
        [20, 0], [65, 0], [80, 20], [90, 50], [80, 99], [25, 99], [10, 50], [20, 20]
    ]
    cutout = compose_planned_page(dna, material, {"layout_mode": "type-led"})
    hero = next(e for e in cutout.elements if e.role == "photo" and e.story_ref == "a")
    plain_hero = next(e for e in scene.elements if e.role == "photo" and e.story_ref == "a")
    assert hero.treatment == "cutout"
    assert hero.frame.y < plain_hero.frame.y
    assert LayoutCritic(dna).evaluate_hard_gate(cutout).passed

    generator = EvolutionaryLayoutGenerator(dna)
    narrow, wide = LayoutGenome(dna), LayoutGenome(dna)
    for genome, share, strap in ((narrow, .34, .45), (wide, .48, .58)):
        genome.layout_mode = "type-led"
        genome.type_led_photo_share = share
        genome.type_led_strap_y = strap
    narrow_scene = generator.decode_genome_to_scene_graph(narrow, material)
    wide_scene = generator.decode_genome_to_scene_graph(wide, material)
    photo_x = lambda sg: next(e.frame.x for e in sg.elements if e.role == "photo" and e.story_ref == "a")
    assert photo_x(narrow_scene) > photo_x(wide_scene)
    assert narrow_scene.metadata["generation_genes"]["type_led_photo_share"] == .34
    assert wide_scene.metadata["generation_genes"]["type_led_strap_y"] == .58
    assert LayoutCritic(dna).extract_strategy_feature_vector(narrow_scene) != LayoutCritic(dna).extract_strategy_feature_vector(wide_scene)

    material.stories[0].body = "Krótki opis."
    material.stories[0].lead = ""
    material.stories[0].deck = ""
    sparse = compose_planned_page(dna, material, {"layout_mode": "type-led"})
    assert sparse.metadata["architecture"] != "popular_type_led"

    material.stories[0].images[0].width_px = 3200
    material.stories[0].images[0].height_px = 2100
    fallback = compose_planned_page(dna, material, {"layout_mode": "type-led"})
    assert fallback.metadata["architecture"] == "popular_poster"


def test_unvalidated_experimental_cover_is_not_sampled_automatically():
    dna = create_archetype_dnas()["tabloid"]
    assert all(LayoutGenome(dna).layout_mode != "type-led" for _ in range(80))
    assert all(LayoutGenome(dna).poster_headline_treatment == "banner" for _ in range(80))
    assert "type-led" in {LayoutGenome(dna, corpus_guidance={"type_led_validated": True}).layout_mode
                          for _ in range(200)}
