"""Measurable quality benchmark (handoff §9).

Fixed set of materials per genre × N variants each.  Reports medians, P10 and
threshold shares — never a single best case.

Deterministic part (always): hard-gate pass rate, topological diversity per
material, novelty vs corpus, dead-zone count, morphology mix, generation time
and peak memory.

VLM part (``--vlm K``): the K best candidates per material are rendered to PDF
and judged *sequentially* by the independent visual critic (no parallel
renders in one process).  Scores are model estimates; human A/B review and
explicit editorial approval are still required.

Usage (repository root):
  python -m backend.scripts.benchmark_quality --genres tabloid editorial_magazine tv_guide \
      --variants 6 --out output/benchmark
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
import tracemalloc
from pathlib import Path

from PIL import Image

from backend.app.engine.corpus_indexer import build_generation_guidance, create_archetype_dnas, load_feature_index
from backend.app.engine.corpus_knowledge import enrich_feature_record
from backend.app.engine.critic import _largest_empty_editorial_region
from backend.app.engine.evolution import EvolutionaryLayoutGenerator, _architecture_key
from backend.app.models.schemas import PageInputMaterial, StoryImageInput, StoryInput

ROOT = Path(__file__).resolve().parents[2]

# Ten fixed topics with different emotions.  Text is fictional test copy.
TOPICS = [
    ("urgent", "PILNE", "Ewakuacja całego osiedla po wycieku gazu", "Strażacy wyprowadzili mieszkańców w nocy."),
    ("scandal", "AFERA", "Urzędnik ukrył raport o zatrutej wodzie", "Dokumenty pokazują, kto wiedział wcześniej."),
    ("solemn", "ŻAŁOBA", "Miasto żegna ratownika, który zginął na służbie", "Tysiące ludzi przyszły na pogrzeb."),
    ("celebratory", "SPORT", "Zwycięstwo w ostatniej sekundzie meczu", "Kibice świętowali do rana na rynku."),
    ("entertainment", "GWIAZDY", "Gwiazda serialu wraca na plan po latach", "Ekipa zdradza pierwsze szczegóły."),
    ("human", "LUDZIE", "Sąsiedzi odbudowali dom samotnej matce", "Pomoc przyszła z każdego piętra bloku."),
    ("urgent", "POGODA", "Wichura zerwała dachy w trzech powiatach", "Synoptycy ostrzegają przed kolejną nocą."),
    ("scandal", "TYLKO U NAS", "Fałszywe faktury za remont szkoły", "Kontrolerzy znaleźli podwójne płatności."),
    ("human", "ZDROWIE", "Ośmiolatek uratował dziadka telefonem", "Dyspozytorka prowadziła go krok po kroku."),
    ("celebratory", "MIASTO", "Nowy most otwarty przed terminem", "Pierwsi piesi przeszli o świcie."),
]
SECONDARY = [
    ("CENTRUM", "Rozkopali pół miasta", "Utrudnienia przy budowie nowego przejścia potrwają do zimy."),
    ("KOLEJ", "Pociąg ominie stację?", "Pasażerowie pytają o zmiany w rozkładzie jazdy."),
    ("PO GODZINACH", "Tu też nie przejdziemy?", "Piesi pytają o objazd przy pobliskiej ulicy."),
    ("ROZMOWA", "Zaczyna wszystko od nowa", "Rozmówczyni opowiada o planach po przeprowadzce."),
]


def photo_pool() -> list[Path]:
    found = sorted(p for p in (ROOT / "corpus").rglob("*")
                   if "Links" in p.parts and p.suffix.lower() in {".jpg", ".jpeg"} and p.stat().st_size > 300_000)
    return found


def build_materials(pool: list[Path]) -> list[PageInputMaterial]:
    sizes = {}
    for path in pool:
        with Image.open(path) as image:
            sizes[path] = image.size
    materials = []
    for index, (mood, kicker, headline, lead) in enumerate(TOPICS):
        def image(offset: int):
            path = pool[(index + offset) % len(pool)]
            w, h = sizes[path]
            return StoryImageInput(id=f"m{index}-{offset}", url=str(path), width_px=w, height_px=h, dpi=300,
                                   caption="Zdjęcie testowe")
        stories = [StoryInput(id=f"m{index}-lead", rank="lead", importance=1.0, kicker=kicker, headline=headline,
                              lead=lead, body=(lead + " Redakcja opisuje przebieg zdarzenia i relacje świadków. ") * 4,
                              images=[image(0)])]
        for s_index, (s_kicker, s_head, s_body) in enumerate(SECONDARY):
            stories.append(StoryInput(id=f"m{index}-s{s_index}", rank="second" if s_index < 2 else "third",
                                      importance=.7 - s_index * .1, kicker=s_kicker, headline=s_head,
                                      body=s_body * 3, images=[image(s_index + 1)]))
        materials.append(PageInputMaterial(masthead_title="PRÓBA ZECRO", issue_date="15.10.2026",
                                           issue_number="TEST", section_name="Wiadomości", page_zone="front_page",
                                           editorial_mood=mood, stories=stories))
    return materials


def tv_fixture(index: int):
    """Deterministic fictional schedule (5 stations, 06:00–01:00)."""
    import random
    from backend.app.models.schemas import TVSlot
    titles = ["Wiadomości", "Pogoda", "Serial obyczajowy", "Film dokumentalny", "Magazyn reporterów",
              "Teleturniej", "Kabaret", "Film fabularny", "Sport", "Koncert", "Kuchnia", "Podróże"]
    rng, slots = random.Random(1000 + index), []
    for station in ["TVP1", "TVP2", "POLSAT", "TVN", "TV4"]:
        minute = 6 * 60
        while minute < 25 * 60:
            slots.append(TVSlot(station=station, time=f"{(minute // 60) % 24:02d}:{minute % 60:02d}",
                                title=rng.choice(titles)))
            minute += rng.choice([30, 45, 60, 90, 120])
    slots[rng.randrange(len(slots))].highlight = True
    return slots


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))], 4)


def summary(values: list[float], threshold: float | None = None) -> dict:
    if not values:
        return {"n": 0}
    out = {"n": len(values), "median": round(statistics.median(values), 4), "p10": pct(values, .10)}
    if threshold is not None:
        out[f"share_ge_{threshold}"] = round(sum(v >= threshold for v in values) / len(values), 4)
    return out


def run(genres: list[str], variants: int, vlm: int, out_dir: Path, seed: int,
        only: list[int] | None = None) -> dict:
    pool = photo_pool()
    if len(pool) < 5:
        raise SystemExit("Benchmark needs at least 5 local photographs in corpus/**/Links.")
    materials = build_materials(pool)
    corpus = [enrich_feature_record(p) for p in (load_feature_index() or [])]
    dnas = create_archetype_dnas()
    report: dict = {"materials": len(materials), "variants_requested": variants, "photo_pool": len(pool), "genres": {}}
    for genre in genres:
        dna = dnas[genre]
        guidance = build_generation_guidance(corpus, archetype=dna.archetype, zone="front_page")
        rows_path = out_dir / f"{genre}-rows.json"
        previous = json.loads(rows_path.read_text(encoding="utf-8")) if (only and rows_path.exists()) else []
        rows = []
        for index, base in enumerate(materials):
            if only and index not in only:
                continue
            material = base.model_copy(deep=True)
            material.style_blend = dna.style_blend
            if genre == "tv_guide":
                material.tv_schedule = tv_fixture(index)
                material.page_zone = "back_page"
            tracemalloc.start()
            started = time.perf_counter()
            pairs = EvolutionaryLayoutGenerator(dna, corpus_features=corpus, corpus_guidance=guidance).generate(
                material=material, num_candidates=variants, population_size=14, generations=2, seed=seed + index)
            elapsed = time.perf_counter() - started
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            for scene, critic in pairs:
                area, w, h = _largest_empty_editorial_region(scene, dna)
                rows.append({
                    "material": index, "mood": material.editorial_mood, "passed": critic.hard_gate.passed,
                    "violations": critic.hard_gate.violations[:3], "architecture": _architecture_key(scene),
                    "topology": scene.metadata.get("topology"), "novelty": critic.novelty_vs_corpus,
                    "fitness": critic.total_fitness, "dead_zone": area > .08 and w > .2 and h > .15,
                    "seconds": round(elapsed, 2), "peak_mb": round(peak / 2**20, 1), "scene": scene,
                })
        if vlm:
            from backend.app.ai.visual_critic import category_review, critique
            for index in sorted({r["material"] for r in rows}):
                # Same policy as production: best candidate of each page
                # architecture first, so the VLM compares different topologies.
                from backend.app.api.generate import _diversity_first
                ordered = sorted([r for r in rows if r["material"] == index and r["passed"]],
                                 key=lambda r: r["fitness"], reverse=True)
                by_scene = {id(r["scene"]): r for r in ordered}
                ranked = [by_scene[id(sg)] for sg, _ in _diversity_first([(r["scene"], None) for r in ordered])][:vlm]
                for row in ranked:
                    try:
                        verdict = critique(row["scene"], dna)
                        row["vlm"] = {key: verdict.get(key) for key in
                                      ("score", "style_fidelity", "photo_use", "photo_headline_match", "category_mismatch")}
                        row["vlm"]["status"] = category_review(verdict)["status"]
                    except Exception as exc:  # recorded, never hidden
                        row["vlm"] = {"error": str(exc)[:200]}
        done = {r["material"] for r in rows}
        rows = [*[r for r in previous if r["material"] not in done], *rows]
        rows.sort(key=lambda r: r["material"])
        per_material_topologies = [len({r["topology"] for r in rows if r["material"] == i}) for i in sorted({r["material"] for r in rows})]
        vlm_rows = [r["vlm"] for r in rows if isinstance(r.get("vlm"), dict) and "score" in r["vlm"]]
        genre_report = {
            "candidates": len(rows),
            "hard_gate_pass_rate": round(sum(r["passed"] for r in rows) / max(1, len(rows)), 4),
            "distinct_topologies_per_material": summary([float(v) for v in per_material_topologies]),
            "novelty_vs_corpus": summary([float(r["novelty"]) for r in rows]),
            "dead_zone_candidates": sum(r["dead_zone"] for r in rows),
            "architectures": {key: sum(r["architecture"] == key for r in rows) for key in sorted({r["architecture"] for r in rows})},
            "seconds_per_material": summary(sorted({(r["material"], r["seconds"]) for r in rows}) and
                                            [s for _, s in sorted({(r["material"], r["seconds"]) for r in rows})]),
            "peak_mb_per_material": summary([m for _, m in sorted({(r["material"], r["peak_mb"]) for r in rows})]),
            "vlm_reviewed": len(vlm_rows),
            "vlm_errors": sum(1 for r in rows if isinstance(r.get("vlm"), dict) and "error" in r["vlm"]),
        }
        if vlm_rows:
            genre_report.update({
                "vlm_overall": summary([float(v["score"] or 0) for v in vlm_rows], .80),
                "vlm_style_fidelity": summary([float(v["style_fidelity"] or 0) for v in vlm_rows], .90),
                "vlm_photo_headline_match": summary([float(v["photo_headline_match"] or 0) for v in vlm_rows], .65),
                "vlm_photo_use": summary([float(v["photo_use"] or 0) for v in vlm_rows], .65),
                "vlm_category_mismatch_share": round(sum(bool(v.get("category_mismatch")) for v in vlm_rows) / len(vlm_rows), 4),
                "vlm_candidate_for_editor_share": round(sum(v.get("status") == "candidate_for_editor" for v in vlm_rows) / len(vlm_rows), 4),
            })
        report["genres"][genre] = genre_report
        out_dir.mkdir(parents=True, exist_ok=True)
        rows_path.write_text(json.dumps(
            [{k: v for k, v in r.items() if k != "scene"} for r in rows], ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--genres", nargs="+", default=["tabloid", "editorial_magazine", "tv_guide"])
    parser.add_argument("--variants", type=int, default=6)
    parser.add_argument("--vlm", type=int, default=0, help="VLM-review the K best candidates per material")
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--only", default="", help="comma-separated material indices; merges with earlier rows")
    parser.add_argument("--out", default=str(ROOT / "output" / "benchmark"))
    args = parser.parse_args()
    only = [int(v) for v in args.only.split(",") if v.strip()] or None
    print(json.dumps(run(args.genres, args.variants, args.vlm, Path(args.out), args.seed, only), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
