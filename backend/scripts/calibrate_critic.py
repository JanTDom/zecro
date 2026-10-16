"""Calibrate the layout critic from A/B pairs.

  python -m backend.scripts.calibrate_critic prepare --archetype tabloid
  python -m backend.scripts.calibrate_critic judge --archetype tabloid --n 3   # resumable, sequential renders
  python -m backend.scripts.calibrate_critic fit --archetype tabloid

``prepare`` generates candidates for the fixed benchmark materials with the
*uncalibrated* critic and plans pairs across different architectures.
``judge`` asks the independent visual critic which render an editor would
print (random A/B order, both renders show the same material and photos).
``fit`` learns per-archetype weights (Bradley–Terry) and writes
``backend/app/engine/calibration/<archetype>.json`` only when the model passes
the leave-one-out floor.  Human pairs can be appended to the same pairs file
with ``"source": "human"``.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def workdir(archetype: str) -> Path:
    path = ROOT / "output" / "calibration" / archetype
    (path / "scenes").mkdir(parents=True, exist_ok=True)
    return path


def prepare(archetype: str, per_material: int, seed: int) -> None:
    from backend.app.engine.corpus_indexer import build_generation_guidance, create_archetype_dnas, load_feature_index
    from backend.app.engine.corpus_knowledge import enrich_feature_record
    from backend.app.engine.critic import LayoutCritic
    from backend.app.engine.critic_calibration import calibration_features
    from backend.app.engine.evolution import EvolutionaryLayoutGenerator, _architecture_key
    from backend.scripts.benchmark_quality import build_materials, photo_pool
    dna = create_archetype_dnas()[archetype]
    corpus = [enrich_feature_record(p) for p in (load_feature_index() or [])]
    guidance = build_generation_guidance(corpus, archetype=dna.archetype, zone="front_page")
    critic = LayoutCritic(dna, corpus_features=corpus, corpus_guidance=guidance)
    critic.use_calibration = False
    out = workdir(archetype)
    rng = random.Random(seed)
    plan = []
    for index, material in enumerate(build_materials(photo_pool())):
        material.style_blend = dna.style_blend
        generator = EvolutionaryLayoutGenerator(dna, corpus_features=corpus, corpus_guidance=guidance)
        generator.critic.use_calibration = False
        pairs = generator.generate(material=material, num_candidates=8, population_size=14, generations=2, seed=seed + index)
        ids = []
        for k, (scene, result) in enumerate(pairs):
            if not result.hard_gate.passed:
                continue
            sid = f"m{index}-c{k}"
            (out / "scenes" / f"{sid}.json").write_text(scene.model_dump_json(), encoding="utf-8")
            ids.append({"id": sid, "architecture": _architecture_key(scene),
                        "heuristic": result.total_fitness, "features": calibration_features(scene, critic)})
        options = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:] if a["architecture"] != b["architecture"]]
        rng.shuffle(options)
        for a, b in options[:per_material]:
            plan.append({"material": index, "a": a, "b": b})
        print("material", index, len(ids), "candidates")
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    print("planned pairs:", len(plan))


def _judge_one(archetype: str, row: dict, seed: int) -> dict:
    from backend.app.ai.runtime import run_task
    from backend.app.ai.schemas import PairwiseJudgement
    from backend.app.ai.visual_critic import render_png
    from backend.app.engine.corpus_indexer import create_archetype_dnas
    from backend.app.engine.editorial_style import editorial_style_label
    from backend.app.models.schemas import SceneGraph
    dna = create_archetype_dnas()[archetype]
    out = workdir(archetype)
    first, second = row["a"], row["b"]
    if random.Random(f"{seed}-{first['id']}-{second['id']}").random() < .5:
        first, second = second, first
    scenes = [SceneGraph.model_validate_json((out / "scenes" / f"{item['id']}.json").read_text(encoding="utf-8"))
              for item in (first, second)]
    images = [{"data": render_png(scene, dna, width_px=900), "mime_type": "image/jpeg"} for scene in scenes]
    meta = scenes[0].metadata or {}
    started = time.time()
    result = run_task("visual_pairwise", "visual_pairwise", {
        "archetype": dna.archetype, "title_style": editorial_style_label(meta.get("style_blend") or dna.style_blend),
        "editorial_mood": meta.get("editorial_mood", "auto"),
    }, PairwiseJudgement, images=images, timeout_s=150, max_retries=1)
    verdict = result.data
    winner = {"A": first, "B": second}.get(verdict.get("winner"))
    loser = {"A": second, "B": first}.get(verdict.get("winner"))
    return {"source": "vlm", "model": result.provenance.get("model"), "material": row["material"],
            "a": first["id"], "b": second["id"], "verdict": verdict.get("winner"),
            "confidence": verdict.get("confidence"), "reasons": verdict.get("reasons"),
            "winner_id": winner["id"] if winner else None, "loser_id": loser["id"] if loser else None,
            "winner_architecture": winner["architecture"] if winner else None,
            "loser_architecture": loser["architecture"] if loser else None,
            "winner": winner["features"] if winner else None, "loser": loser["features"] if loser else None,
            "seconds": round(time.time() - started, 1)}


def judge(archetype: str, n: int, workers: int, seed: int) -> None:
    out = workdir(archetype)
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    done_path = out / "pairs.jsonl"
    done = {(r["a"], r["b"]) for r in map(json.loads, done_path.read_text().splitlines())} if done_path.exists() else set()
    done |= {(b, a) for a, b in done}
    todo = [row for row in plan if (row["a"]["id"], row["b"]["id"]) not in done][:n]
    if not todo:
        print("nothing to judge")
        return
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(_judge_one, archetype, row, seed) for row in todo]
        for future in futures:
            try:
                record = future.result()
            except Exception as exc:  # recorded; never silently counted as a vote
                print("error:", str(exc)[:200])
                continue
            with done_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(record["verdict"], record["winner_architecture"], ">", record["loser_architecture"], record["seconds"])
    remaining = len(plan) - len({(r["a"], r["b"]) for r in map(json.loads, done_path.read_text().splitlines())})
    print("remaining", remaining)


def fit(archetype: str) -> None:
    from backend.app.engine.critic_calibration import fit_calibration, iter_pairs, save_calibration
    rows = [r for r in iter_pairs(workdir(archetype) / "pairs.jsonl") if r.get("winner") and r.get("loser")]
    sources = sorted({r.get("source", "vlm") for r in rows})
    data = fit_calibration(rows, archetype=archetype, source="+".join(sources))
    wins: dict[str, list[int]] = {}
    for r in rows:
        wins.setdefault(r["winner_architecture"], [0, 0])[0] += 1
        wins.setdefault(r["loser_architecture"], [0, 0])[1] += 1
    data["architecture_win_loss"] = wins
    path = save_calibration(data)
    print(json.dumps({k: data[k] for k in ("pairs", "loo_accuracy", "heuristic_pair_accuracy", "valid", "weights", "architecture_win_loss")},
                     ensure_ascii=False, indent=1))
    print("saved", path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "judge", "fit"])
    parser.add_argument("--archetype", default="tabloid")
    parser.add_argument("--per-material", type=int, default=5)
    parser.add_argument("--n", type=int, default=3)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--seed", type=int, default=211)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.archetype, args.per_material, args.seed)
    elif args.command == "judge":
        judge(args.archetype, args.n, args.workers, args.seed)
    else:
        fit(args.archetype)


if __name__ == "__main__":
    sys.exit(main())
