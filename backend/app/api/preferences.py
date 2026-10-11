from fastapi import APIRouter, HTTPException, status
from ..models.schemas import PreferenceSignal, TasteModel
from ..models.database import db
from ..engine.taste_loop import TasteLoopTrainer
from ..engine.critic import LayoutCritic

router = APIRouter(prefix="/projects", tags=["preferences"])

@router.post("/{project_id}/preferences", response_model=PreferenceSignal, status_code=status.HTTP_201_CREATED)
def record_preference(project_id: str, signal: PreferenceSignal):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    signal.project_id = project_id
    saved_signal = db.record_preference_signal(signal)

    # Trigger online preference model update
    signals = db.list_preference_signals(project_id)
    dna = db.get_title_dna(project_id)

    # Build candidates map for winner and loser
    candidate_ids = set()
    for s in signals:
        if s.winner_candidate_id:
            candidate_ids.add(s.winner_candidate_id)
        if s.loser_candidate_id:
            candidate_ids.add(s.loser_candidate_id)

    cand_map = {}
    for cid in candidate_ids:
        cand = db.get_candidate(cid)
        if cand:
            cand_map[cid] = cand.scene_graph

    critic = LayoutCritic(dna)
    existing_model = db.get_taste_model(project_id)

    trainer = TasteLoopTrainer(project_id=project_id)
    updated_model = trainer.train_reward_model(
        signals=signals,
        candidates_map=cand_map,
        critic=critic,
        existing_model=existing_model
    )
    db.save_taste_model(updated_model)

    return saved_signal

@router.get("/{project_id}/taste-model", response_model=TasteModel)
def get_project_taste_model(project_id: str):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    tm = db.get_taste_model(project_id)
    if not tm:
        tm = TasteModel(
            project_id=project_id,
            version=1,
            feature_weights={},
            sample_count=0,
            human_preference_win_rate=0.0,
            time_to_approve_avg_iterations=1.0
        )
    return tm
