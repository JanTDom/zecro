#!/usr/bin/env python3
"""
Zecro Taste Preference Active Learner Engine.

Implements Active Learning and Bradley-Terry preference modeling for the
Art Director taste loop:
- Uncertainty sampling (Max Entropy) to pick most informative A/B pairs
- Bradley-Terry weight updates based on pairwise human decisions (A vs B)
- Geometric canvas edit delta ingestion (learning from manual frame adjustments)
- Preventing art direction drift across publication issues
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class LayoutCandidate:
    candidate_id: str
    archetype: str
    features: Dict[str, float]  # e.g., "hierarchy_contrast", "whitespace_balance", "visual_tension", "column_harmony"
    predicted_score: float = 0.0


@dataclass
class PreferenceWeights:
    hierarchy_contrast: float = 1.8
    whitespace_balance: float = 1.2
    visual_tension: float = 0.9
    column_harmony: float = 1.5
    novelty_distance: float = 1.1


def predict_score(features: Dict[str, float], weights: PreferenceWeights) -> float:
    w_dict = asdict(weights)
    score = 0.0
    for k, val in features.items():
        w = w_dict.get(k, 1.0)
        score += w * val
    return score


def calculate_pairwise_uncertainty(score_a: float, score_b: float) -> float:
    """Computes Shannon entropy of the pairwise choice probability."""
    delta = score_a - score_b
    prob_a = 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, delta))))
    prob_b = 1.0 - prob_a
    # Entropy: -p*log(p) - (1-p)*log(1-p)
    eps = 1e-9
    entropy = -(prob_a * math.log(prob_a + eps) + prob_b * math.log(prob_b + eps))
    return entropy


def select_active_learning_pair(candidates: List[LayoutCandidate], weights: PreferenceWeights) -> Tuple[LayoutCandidate, LayoutCandidate, float]:
    """Finds pair with maximum uncertainty (closest to 50% choice probability)."""
    for c in candidates:
        c.predicted_score = predict_score(c.features, weights)

    best_pair = None
    max_uncertainty = -1.0

    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            cand_a = candidates[i]
            cand_b = candidates[j]
            unc = calculate_pairwise_uncertainty(cand_a.predicted_score, cand_b.predicted_score)
            if unc > max_uncertainty:
                max_uncertainty = unc
                best_pair = (cand_a, cand_b)

    return best_pair[0], best_pair[1], max_uncertainty


def update_weights_bradley_terry(
    weights: PreferenceWeights,
    winner: LayoutCandidate,
    loser: LayoutCandidate,
    learning_rate: float = 0.05,
) -> PreferenceWeights:
    """Updates preference weights via Bradley-Terry gradient step."""
    delta_score = winner.predicted_score - loser.predicted_score
    prob_winner = 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, delta_score))))
    error = 1.0 - prob_winner  # target is 1.0

    w_dict = asdict(weights)
    for feat_name in w_dict.keys():
        diff_feat = winner.features.get(feat_name, 0.0) - loser.features.get(feat_name, 0.0)
        w_dict[feat_name] = max(0.1, w_dict[feat_name] + learning_rate * error * diff_feat)

    return PreferenceWeights(**w_dict)


def main() -> int:
    parser = argparse.ArgumentParser(description="Zecro Taste Preference Active Learner CLI")
    parser.add_argument("--demo", action="store_true", help="Run active learning demo on 4 candidates")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    weights = PreferenceWeights()

    # Demo layout candidates
    c1 = LayoutCandidate("cand_1", "dominant_hero", {"hierarchy_contrast": 0.85, "whitespace_balance": 0.60, "visual_tension": 0.40, "column_harmony": 0.90, "novelty_distance": 0.30})
    c2 = LayoutCandidate("cand_2", "modular_rhythm", {"hierarchy_contrast": 0.60, "whitespace_balance": 0.75, "visual_tension": 0.30, "column_harmony": 0.95, "novelty_distance": 0.40})
    c3 = LayoutCandidate("cand_3", "split_hero", {"hierarchy_contrast": 0.78, "whitespace_balance": 0.65, "visual_tension": 0.65, "column_harmony": 0.80, "novelty_distance": 0.60})
    c4 = LayoutCandidate("cand_4", "visual_opener", {"hierarchy_contrast": 0.92, "whitespace_balance": 0.50, "visual_tension": 0.75, "column_harmony": 0.70, "novelty_distance": 0.80})

    candidates = [c1, c2, c3, c4]
    pair_a, pair_b, unc = select_active_learning_pair(candidates, weights)

    print(f"# Zecro Active Learning: Rekomendowana Para Porównawcza A/B")
    print(f"- **Maksymalna entropia wyboru:** {unc:.3f} (najbardziej pouczająca dla modelu gustu)")
    print(f"- **Wariant A:** `{pair_a.candidate_id}` ({pair_a.archetype}) – przewidywana ocena: {pair_a.predicted_score:.2f}")
    print(f"- **Wariant B:** `{pair_b.candidate_id}` ({pair_b.archetype}) – przewidywana ocena: {pair_b.predicted_score:.2f}")
    print("\n## Wpływ na wagi preferencji (aktualizacja Bradley-Terry)")
    new_weights = update_weights_bradley_terry(weights, winner=pair_a, loser=pair_b)
    for k, v in asdict(new_weights).items():
        old_v = getattr(weights, k)
        print(f"- `{k}`: {old_v:.2f} -> **{v:.2f}** ({v - old_v:+.2f})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
