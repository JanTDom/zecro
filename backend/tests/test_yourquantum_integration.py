"""Contract tests for the optional YourQuantum layout subsolver."""

from backend.app.config import settings
from backend.app.engine.evolution import LayoutGenome
from backend.app.engine.grammar import create_default_broadsheet_dna
from backend.app.integrations import yourquantum
from backend.app.models.schemas import PageInputMaterial, StoryInput


def _material():
    return PageInputMaterial(
        stories=[
            StoryInput(
                id="lead",
                headline="Najważniejszy temat dnia",
                lead="Krótki lead z faktem i konsekwencją.",
                body="Dłuższy materiał redakcyjny z potwierdzonymi informacjami.",
                importance=1.0,
            )
        ],
        page_zone="front_page",
    )


def test_yourquantum_is_disabled_without_explicit_server_configuration(monkeypatch):
    monkeypatch.setattr(settings, "yourquantum_api_url", "")
    monkeypatch.setattr(settings, "yourquantum_api_key", "")
    result = yourquantum.select_transgressions(create_default_broadsheet_dna(), _material())
    assert result.status == "disabled"
    assert result.selected_ids == []


def test_yourquantum_payload_uses_only_discrete_supported_effects(monkeypatch):
    monkeypatch.setattr(settings, "yourquantum_api_url", "https://yourquantum.test")
    monkeypatch.setattr(settings, "yourquantum_api_key", "test-token")
    seen = {}

    def fake_post(payload):
        seen["payload"] = payload
        return {
            "status": "SUCCESS",
            "solver_used": "cp_sat",
            "optimal_assignment": {"diagonal-break": 1},
            "optimal_selection": [{"id": "diagonal-break"}],
            "optimality_proven": True,
            "optimality_gap_percent": 0.0,
            "sha256_passport": "passport",
        }

    monkeypatch.setattr(yourquantum, "_post", fake_post)
    result = yourquantum.select_transgressions(create_default_broadsheet_dna(), _material())

    assert result.status == "ready"
    assert result.selected_ids == ["diagonal-break"]
    assert result.optimality_proven is True
    assert result.request_sha256
    payload = seen["payload"]
    assert payload["domain"] == "editorial_layout"
    assert payload["objective_attribute"] == "utility"
    assert payload["constraints"][0]["attribute"] == "energy_cost"
    assert {item["id"] for item in payload["variables"]} <= {"diagonal-break", "extreme-scale"}
    assert all("x" not in item and "y" not in item for item in payload["variables"])


def test_remote_policy_is_realized_by_the_local_genome_and_remains_discrete():
    dna = create_default_broadsheet_dna()
    genome = LayoutGenome(
        dna,
        preferred_transgressions=["diagonal-break", "extreme-scale"],
    )
    assert genome.hl_scale_mult == 1.35
    assert genome.hl_rotation_deg in {-3.5, 3.5}
    assert "cutout-wrap" not in genome.preferred_transgressions

