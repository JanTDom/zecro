"""Auditable AI assistance for the editorial layout pipeline.

The art director is a coordinator, not an opaque prompt glued to the
renderer.  It tells each specialist what evidence it may use, what it must
return and which decisions still require a human.  A deterministic fallback
is always available, so an unavailable model cannot silently turn a measured
layout into an invented one.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


CONTRACT_VERSION = "ai-director-contract/1.0"


@dataclass(frozen=True)
class AIDirector:
    """Build explainable AI operating contracts from real project evidence."""

    dna: Any
    knowledge: Mapping[str, Any]
    preference_model: Optional[Any] = None
    vision_provider: Optional[Any] = None
    writer_provider: Optional[Any] = None
    task_statuses: Optional[Mapping[str, str]] = None

    def contract(self) -> dict[str, Any]:
        evidence = dict(self.knowledge.get("evidence") or {})
        source = str(self.knowledge.get("source") or "unavailable")
        sample_count = int(evidence.get("knowledge_pages") or self.knowledge.get("sample_count") or 0)
        structural = int(evidence.get("structural_pages") or 0)
        semantic = int(evidence.get("semantic_pages") or 0)
        return {
            "version": CONTRACT_VERSION,
            "mode": "generator_critic_separated",
            "source_policy": "database_first_remote_only_in_production",
            "knowledge": {
                "source": source,
                "sample_count": sample_count,
                "structural_pages": structural,
                "semantic_pages": semantic,
                "evidence_levels": evidence.get("levels", {}),
                "warnings": list(evidence.get("warnings") or []),
            },
            "specialists": {
                "corpus_analyst": {"status": "ready" if sample_count else "blocked", "output": "measured_priors_and_unknowns"},
                "layout_generator": {"status": "ready", "output": "fresh_scene_graph_candidates"},
                "hard_critic": {"status": "ready", "output": "pass_fail_gate"},
                "taste_critic": {
                    "status": "learned" if self.preference_model and getattr(self.preference_model, "sample_count", 0) else "heuristic",
                    "output": "ranked_candidates_with_reason",
                },
                "visual_critic": {
                    "status": (self.task_statuses or {}).get("visual_critic") or ("ready" if self.vision_provider and getattr(self.vision_provider, "info", None) and getattr(self.vision_provider.info, "provider", "") != "disabled" else "unconfigured"),
                    "output": "render_review_with_observations",
                },
                "copy_editor": {
                    "status": (self.task_statuses or {}).get("copy_fit") or ("ready" if self.writer_provider else "source_bound_fallback"),
                    "output": "frame_bound_variants_with_provenance",
                },
            },
            "gates": [
                "hard_gate_before_soft_ranking",
                "all_required_content_or_explicit_editorial_reduction",
                "no_unverified_claim_becomes_approved_copy",
                "no_layout_is_approved_from_metadata_only",
                "production_render_and_preview_share_the_scene_graph",
            ],
            "feedback": {
                "pairwise_choices": "stored_as_preference_signals",
                "manual_geometry_edits": "stored_as_feature_deltas",
                "model_update": "per_project_after_human_signal",
            },
        }

    def candidate_trace(self, scene_graph: Any, critic_result: Any) -> dict[str, Any]:
        """Return a per-candidate trace without fabricating a probability."""

        hard = getattr(critic_result, "hard_gate", None)
        passed = bool(getattr(hard, "passed", False))
        violations = list(getattr(hard, "violations", []) or [])
        metadata = getattr(scene_graph, "metadata", {}) or {}
        guidance = metadata.get("corpus_guidance") or {}
        evidence = self.knowledge.get("evidence") or {}
        return {
            "contract_version": CONTRACT_VERSION,
            "knowledge_source": self.knowledge.get("source", "unavailable"),
            "knowledge_sample_count": int(evidence.get("knowledge_pages") or 0),
            "knowledge_evidence_levels": evidence.get("levels", {}),
            "generation": {
                "role": "exploration",
                "fresh_scene_graph": True,
                "guidance_sample_count": guidance.get("sample_count", 0),
                "strategy_distribution": guidance.get("strategy_distribution", {}),
            },
            "selection": {
                "role": "critique",
                "hard_gate": "PASS" if passed else "FAIL",
                "violations": violations,
                "soft_score_source": "learned_preference_model" if self.preference_model and getattr(self.preference_model, "sample_count", 0) else "measured_heuristics",
                "visual_review": "available" if (self.task_statuses or {}).get("visual_critic") == "ready" or self.vision_provider else "unconfigured",
            },
            "approval": "eligible_for_editor_review" if passed else "blocked_by_hard_gate",
            "unknowns": [item for item in [
                "semantic roles in raster corpus are unverified",
                "human preference model is sparse" if not self.preference_model or not getattr(self.preference_model, "sample_count", 0) else "",
                "visual model review is not configured" if not self.vision_provider and (self.task_statuses or {}).get("visual_critic") != "ready" else "",
            ] if item],
        }


def build_ai_director_contract(dna: Any, knowledge: Mapping[str, Any], preference_model: Optional[Any] = None) -> dict[str, Any]:
    """Small functional entry point for API routes and tests."""

    return AIDirector(dna=dna, knowledge=knowledge, preference_model=preference_model).contract()


__all__ = ["AIDirector", "CONTRACT_VERSION", "build_ai_director_contract"]
