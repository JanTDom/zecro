from __future__ import annotations
from backend.app.ai.image_generator import generate_editorial_image
from backend.app.ai.photo_brief import PhotoBrief
from backend.app.ai.source_guard import guard_generated_text
from backend.app.engine.grammar import create_default_broadsheet_dna, create_default_tabloid_dna
from backend.app.engine.page_planner import plan_page, validate_page_plan
from backend.app.engine.shaper import measure_text
from backend.app.engine.image_ops import extract_alpha_contour
from backend.app.models.schemas import StoryInput


def _stories():
    return [StoryInput(id='lead', headline='Lead', body='lead ' * 400, rank='lead', importance=1),
            StoryInput(id='second-a', headline='Second A', body='second ' * 250, rank='second', importance=.8),
            StoryInput(id='second-b', headline='Second B', body='second ' * 250, rank='second', importance=.8),
            *[StoryInput(id=f'brief-{i}', headline=f'Brief {i}', body='brief ' * 60, rank='brief', importance=.4) for i in range(4)]]


def test_ranked_front_page_packs_all_stories_once_in_both_presets():
    for dna in (create_default_broadsheet_dna(), create_default_tabloid_dna()):
        plan = plan_page(dna, _stories())
        assert plan.status == 'valid'
        assert sorted(plan.story_refs) == sorted(story.id for story in _stories())
        assert validate_page_plan(plan, _stories()) == []
        assert all(slot.col_span >= 2 for slot in plan.slots)


def test_inner_page_packs_twelve_manual_ranks_and_respects_pins():
    ranks = ['lead', 'second', 'second', 'third', 'third', 'short', 'short',
             'short', 'brief', 'brief', 'box', 'column']
    stories = [StoryInput(id=f's{i}', headline=f'Story {i}', body='source ' * 20,
                          rank=rank, importance=1 - i / 20,
                          pin_zone='right_rail' if i == 2 else None,
                          pin_page=2 if i == 3 else None)
               for i, rank in enumerate(ranks)]
    for dna in (create_default_broadsheet_dna(), create_default_tabloid_dna()):
        plan = plan_page(dna, stories, page_zone='spread', page_number=2)
        assert plan.status == 'valid'
        assert len(plan.slots) == 12
        assert validate_page_plan(plan, stories) == []
        assert next(slot for slot in plan.slots if slot.story_ref == 's2').col_start + next(slot for slot in plan.slots if slot.story_ref == 's2').col_span == plan.columns


def test_source_guard_rejects_unsupported_number():
    result = guard_generated_text('Projekt kosztuje 42 mln zł.', 'Projekt kosztuje 12 mln zł.')
    assert result.status == 'unsupported'
    assert '42' in result.unsupported


def test_real_event_image_generation_is_refused():
    result = generate_editorial_image(PhotoBrief(is_real_event=True, real_people=['Anna Nowak']))
    assert result['status'] == 'refused'
    assert result['ai_generated'] is False


def test_shaper_is_explicitly_estimate_without_font():
    result = measure_text('To jest polski tekst testowy.', 50, font_size_pt=9.5)
    assert result.status == 'estimate'
    assert result.line_count >= 1


def test_missing_mask_never_fabricates_contour(tmp_path):
    assert extract_alpha_contour(str(tmp_path / 'missing.png'), 100, 100) == []


def test_evolution_produces_three_architectures_for_seven_stories():
    from backend.app.engine.evolution import EvolutionaryLayoutGenerator
    from backend.app.models.schemas import PageInputMaterial
    stories = [StoryInput(id='lead', headline='A strong lead headline', lead='Lead context. ' * 12, body='Lead body. ' * 400, rank='lead', importance=1),
               *[StoryInput(id=f'second-{i}', headline=f'Second story {i}', lead='Context. ' * 15, body='Second body. ' * 250, rank='second', importance=.8) for i in range(2)],
               *[StoryInput(id=f'brief-{i}', headline=f'Brief story {i}', body='Short copy. ' * 60, rank='brief', importance=.4) for i in range(4)]]
    for dna in (create_default_broadsheet_dna(), create_default_tabloid_dna()):
        results = EvolutionaryLayoutGenerator(dna).generate(PageInputMaterial(stories=stories), num_candidates=8, population_size=30, generations=3, seed=4, allow_transgressions=False)
        assert len(results) >= 3
        assert len({scene.metadata.get('layout_mode') for scene, _ in results}) >= 3
        for scene, critic in results:
            assert critic.hard_gate.passed
            assert isinstance(scene.metadata.get('fit_adjustments'), list)
            for story in stories:
                assert sum(element.role == 'headline' and element.story_ref == story.id for element in scene.elements) == 1


def test_health_ai_reports_missing_key(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.config import settings
    from backend.app.ai import integration_registry
    monkeypatch.setattr(settings, 'gemini_api_key', '')
    monkeypatch.setattr(integration_registry.db, 'list_integrations', lambda project_id=None: [])
    response = TestClient(app).get('/health/ai')
    assert response.status_code == 503
    assert response.json()['detail']['status'] == 'unavailable'


def test_admin_integration_secret_is_encrypted_and_masked(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.config import settings
    from backend.app.models.database import db
    monkeypatch.setattr(settings, 'admin_token', 'test-admin-token')
    monkeypatch.setattr(settings, 'secrets_key', 'test-master-key')
    client = TestClient(app)
    payload = {'kind':'ai_provider','provider':'custom','label':'Test adapter','api_key':'secret-value-123456','config':{'model':'test-model'}}
    assert client.post('/settings/integrations', json=payload).status_code == 403
    response = client.post('/settings/integrations', json=payload, headers={'X-Zecro-Admin-Token':'test-admin-token'})
    assert response.status_code == 200
    item = response.json()
    assert 'secret-value-123456' not in str(item)
    assert item['secret_source'] == 'panel'
    raw = db.get_integration(item['id'])
    assert raw and raw['secret_ref'] != 'secret-value-123456'
    assert 'secret-value-123456' not in raw['secret_ref']
    assert client.delete(f"/settings/integrations/{item['id']}", headers={'X-Zecro-Admin-Token':'test-admin-token'}).status_code == 200


def test_logo_profiles_change_masthead_geometry(tmp_path):
    from backend.app.engine.logo import analyze_logo, masthead_geometry
    wide = tmp_path / 'wide.svg'
    wide.write_text('<svg viewBox="0 0 400 80"><rect fill="#112233" width="400" height="80"/></svg>')
    square = tmp_path / 'square.svg'
    square.write_text('<svg viewBox="0 0 100 100"><rect fill="#112233" width="100" height="100"/></svg>')
    dna = create_default_broadsheet_dna()
    wide_profile = analyze_logo(wide)
    square_profile = analyze_logo(square)
    assert masthead_geometry(dna, wide_profile, 350)['mode'] == 'horizontal'
    assert masthead_geometry(dna, square_profile, 350)['mode'] == 'ears'


def test_custom_api_blocks_private_cloud_endpoint(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.config import settings
    monkeypatch.setattr(settings, 'admin_token', 'test-admin-token')
    monkeypatch.setattr(settings, 'secrets_key', 'test-master-key')
    payload = {'kind': 'photo_source', 'provider': 'custom', 'label': 'Private',
               'config': {'base_url': 'http://127.0.0.1:8080/search'}}
    response = TestClient(app).post('/settings/integrations', json=payload,
                                    headers={'X-Zecro-Admin-Token': 'test-admin-token'})
    assert response.status_code == 422
    assert 'private' in str(response.json()).lower()
