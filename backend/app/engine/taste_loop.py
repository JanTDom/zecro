import math
from typing import List, Dict, Any, Tuple, Optional
from ..models.schemas import PreferenceSignal, TasteModel, SceneGraph, Candidate
from .critic import LayoutCritic

class TasteLoopTrainer:
    def __init__(self, project_id: str, learning_rate: float = 0.1, regularization: float = 0.01):
        self.project_id = project_id
        self.lr = learning_rate
        self.l2_reg = regularization

    def train_reward_model(
        self,
        signals: List[PreferenceSignal],
        candidates_map: Dict[str, SceneGraph],
        critic: LayoutCritic,
        existing_model: Optional[TasteModel] = None
    ) -> TasteModel:
        """
        Trains or updates a Bradley-Terry logistic preference model on pairwise preference signals.
        P(winner > loser) = sigmoid(w^T * (x_winner - x_loser))
        """
        num_features = 10
        weights = [0.0] * num_features

        # Rebuild from the recorded history.  Initializing from the previous
        # model and replaying all old choices would count them repeatedly.

        # Prepare pairwise training examples: (delta_vector, label=1).  Keep
        # their order so the newest feedback can be held out for a truthful
        # generalisation metric.
        pairs: List[Tuple[List[float], int]] = []

        for sig in signals:
            if sig.signal_type in ["pairwise_comparison", "selection"] and sig.winner_candidate_id and sig.loser_candidate_id:
                sg_win = candidates_map.get(sig.winner_candidate_id)
                sg_lose = candidates_map.get(sig.loser_candidate_id)
                if sg_win and sg_lose:
                    fv_win = critic.extract_layout_feature_vector(sg_win)
                    fv_lose = critic.extract_layout_feature_vector(sg_lose)
                    if len(fv_win) == num_features and len(fv_lose) == num_features:
                        delta = [w - l for w, l in zip(fv_win, fv_lose)]
                        pairs.append((delta, 1))

            elif sig.signal_type == "manual_edit_delta" and sig.delta_features:
                delta = [sig.delta_features.get(f"feat_{i}", 0.0) for i in range(num_features)]
                pairs.append((delta, 1))

        if not pairs:
            return existing_model or TasteModel(
                project_id=self.project_id,
                version=1,
                feature_weights={f"feat_{i}": round(weights[i], 4) for i in range(num_features)},
                sample_count=0,
                human_preference_win_rate=0.0,
                time_to_approve_avg_iterations=0.0,
                held_out_win_rate=0.0,
                evaluated_sample_count=0,
                feedback_count=len(signals),
            )

        # Reserve the newest quarter for evaluation once there is enough data
        # to make that split meaningful.  With fewer than four choices we
        # train on all available feedback and explicitly report that no
        # held-out estimate exists.
        held_out: List[Tuple[List[float], int]] = []
        train_pairs = pairs
        if len(pairs) >= 4:
            heldout_count = max(1, len(pairs) // 4)
            train_pairs = pairs[:-heldout_count]
            held_out = pairs[-heldout_count:]

        # Gradient descent optimization on Bradley-Terry logistic loss.
        # This is intentionally bounded: the endpoint is an online feedback
        # surface and must stay responsive as the archive grows.
        epochs = 60
        for _ in range(epochs):
            for delta, target in train_pairs:
                # Dot product w^T * delta
                score = sum(w * d for w, d in zip(weights, delta))
                # Sigmoid prob
                prob = 1.0 / (1.0 + math.exp(-max(-15.0, min(15.0, score))))
                # Gradient of cross-entropy w.r.t weights: (prob - target) * delta + l2_reg * w
                grad_err = prob - target
                for i in range(num_features):
                    grad = grad_err * delta[i] + self.l2_reg * weights[i]
                    weights[i] -= self.lr * grad

        # Evaluate win rate on training pairs
        correct_predictions = 0
        for delta, target in train_pairs:
            score = sum(w * d for w, d in zip(weights, delta))
            if score >= 0.0:  # predicted winner > loser
                correct_predictions += 1

        win_rate = round(correct_predictions / len(train_pairs), 3)

        held_out_correct = sum(
            1 for delta, target in held_out
            if (sum(w * d for w, d in zip(weights, delta)) >= 0.0) == bool(target)
        )
        held_out_rate = round(held_out_correct / len(held_out), 3) if held_out else 0.0

        # Approval time is measured by the UI and carried by each signal.  Do
        # not invent a duration when older signals do not have one.
        sample_count = len(pairs)
        durations = [float(getattr(sig, "review_duration_sec", 0.0) or 0.0) for sig in signals]
        durations = [value for value in durations if value > 0]
        time_to_approve = round(sum(durations) / len(durations), 2) if durations else 0.0

        return TasteModel(
            project_id=self.project_id,
            version=(existing_model.version + 1) if existing_model else 1,
            feature_weights={f"feat_{i}": round(weights[i], 4) for i in range(num_features)},
            sample_count=sample_count,
            human_preference_win_rate=win_rate,
            time_to_approve_avg_iterations=time_to_approve,
            held_out_win_rate=held_out_rate,
            evaluated_sample_count=len(held_out),
            feedback_count=len(signals),
        )
