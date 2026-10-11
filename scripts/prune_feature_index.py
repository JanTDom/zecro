"""Drop index entries whose page no longer exists (e.g. moved to _quarantine)
and recompute the archetype aggregates — no page rescan needed."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.engine.corpus_indexer import aggregate_archetype_features, CATEGORY_TO_ARCHETYPE  # noqa: E402

root = Path(sys.argv[1] if len(sys.argv) > 1 else "corpus").resolve()
target = root / "FEATURE_INDEX.json"
index = json.loads(target.read_text(encoding="utf-8"))
def exists(p):
    raw = p["path"]
    rel = raw.split("/corpus/", 1)[1] if "/corpus/" in raw else raw
    return (root / rel).exists()
before = len(index["pages"])
pages = [p for p in index["pages"] if exists(p)]
if before and not pages:
    sys.exit("żadna strona z indeksu nie istnieje pod tym katalogiem — przerwano bez zapisu")
index.update(pages=pages, page_count=len(pages), title_count=len({p.get("title_id") for p in pages if p.get("title_id")}),
             categories={c: sum(1 for p in pages if p.get("category") == c) for c in sorted(CATEGORY_TO_ARCHETYPE)},
             zones={z: sum(1 for p in pages if p.get("zone") == z) for z in ("front", "inside", "back")},
             archetypes=aggregate_archetype_features(pages))
target.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"before": before, "after": len(pages), "removed": before - len(pages)}))
