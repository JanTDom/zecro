#!/usr/bin/env python3
"""Gemini vision audit of the reference corpus (never deletes).

  python3 scripts/audit_corpus.py corpus            # audit only, writes CORPUS_AUDIT.csv/json
  python3 scripts/audit_corpus.py corpus --apply    # move rejected pages to corpus/_quarantine/
Resumable: verdicts are cached in corpus/.audit_cache.jsonl.
"""
from __future__ import annotations
import argparse, csv, io, json, shutil, sys, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".pdf"}
ZONES = {"1_pierwsza_strona": "pierwsza strona", "2_srodek_rozkladowki": "środek", "3_ostatnia_strona": "ostatnia strona"}
lock = threading.Lock()


def _image_bytes(path: Path) -> bytes:
    from PIL import Image
    if path.suffix.lower() == ".pdf":
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(str(path)); page = doc[0]
        img = page.render(scale=900 / page.get_width()).to_pil(); doc.close()
    else:
        img = Image.open(path)
    img = img.convert("RGB"); img.thumbnail((900, 900))
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=80)
    return buf.getvalue()


def _title_for(path: Path, root: Path) -> str:
    for parent in path.parents:
        meta = parent / "metadata.json"
        if meta.exists():
            try:
                return json.loads(meta.read_text(encoding="utf-8")).get("name") or parent.name
            except Exception:
                return parent.name
        if parent == root:
            break
    return path.parent.parent.name


def judge(path: Path, root: Path) -> dict:
    from backend.app.ai.runtime import run_task
    from backend.app.ai.schemas import CorpusVerdict
    zone = next((ZONES[p] for p in path.parts if p in ZONES), "nieznana")
    res = run_task("corpus_audit", "corpus_audit", {"folder_title": _title_for(path, root), "folder_zone": zone, "filename": path.name},
                   CorpusVerdict, images=[{"data": _image_bytes(path), "mime_type": "image/jpeg"}])
    return res.data


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default="corpus", type=Path)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--exclude", action="append", default=[], help="top-level folder never moved by --apply (e.g. own assets)")
    a = ap.parse_args()
    root = a.root
    cache_path = root / ".audit_cache.jsonl"
    cache = {}
    if cache_path.exists():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line); cache[row["path"]] = row
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXT and "_quarantine" not in p.parts)
    todo = [p for p in files if str(p.relative_to(root)) not in cache]
    if a.limit:
        todo = todo[: a.limit]
    print(f"stron: {len(files)}, w cache: {len(files) - len(todo)}, do sprawdzenia: {len(todo)}", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=a.workers) as pool, cache_path.open("a", encoding="utf-8") as out:
        futures = {pool.submit(judge, p, root): p for p in todo}
        for fut in as_completed(futures):
            p = futures[fut]
            rel = str(p.relative_to(root))
            try:
                v = fut.result(); row = {"path": rel, "status": "ok", **v}
            except Exception as exc:
                row = {"path": rel, "status": "error", "reason": str(exc)[:200]}
            if row["status"] == "ok":
                with lock:
                    out.write(json.dumps(row, ensure_ascii=False) + "\n"); out.flush()
                cache[rel] = row
            done += 1
            if done % 25 == 0:
                print(f"{done}/{len(todo)}", flush=True)
    rows = []
    for p in files:
        rel = str(p.relative_to(root)); v = cache.get(rel)
        if not v:
            rows.append({"path": rel, "verdict": "unchecked"}); continue
        reject = not v["is_newspaper_or_magazine_page"]
        rows.append({"path": rel, "verdict": "rejected" if reject else "accepted", **{k: v.get(k) for k in ("title_matches_folder", "page_zone_guess", "era", "language", "reason")}})
    moved = 0
    if a.apply:
        q = root / "_quarantine"
        for r in rows:
            if r["verdict"] == "rejected" and r["path"].split("/")[0] not in a.exclude:
                src = root / r["path"]; dst = q / r["path"]
                if src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(src), str(dst)); moved += 1
                    r["quarantine_path"] = str(dst.relative_to(root))
    per_title: dict[str, dict] = {}
    for r in rows:
        title = r["path"].split("/")[1] if r["path"].count("/") >= 2 else r["path"].split("/")[0]
        t = per_title.setdefault(title, {"accepted": 0, "rejected": 0, "unchecked": 0, "title_mismatch": 0})
        t[r["verdict"]] += 1
        t["title_mismatch"] += r.get("title_matches_folder") == "no"
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "checked": sum(r["verdict"] != "unchecked" for r in rows),
              "accepted": sum(r["verdict"] == "accepted" for r in rows), "rejected": sum(r["verdict"] == "rejected" for r in rows),
              "unchecked": sum(r["verdict"] == "unchecked" for r in rows), "moved_to_quarantine": moved, "per_title": per_title, "rows": rows}
    (root / "CORPUS_AUDIT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with (root / "CORPUS_AUDIT.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["path", "verdict", "title_matches_folder", "page_zone_guess", "era", "language", "reason", "quarantine_path"], extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    print(json.dumps({k: report[k] for k in ("checked", "accepted", "rejected", "unchecked", "moved_to_quarantine")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
