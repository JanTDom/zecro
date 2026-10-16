"""AI dyrektor artystyczny + redaktor techniczny na materiale Wukadki NR21.

python -m scripts.art_direct_demo [--rounds 3] [--tag ad]
Wynik: output/wukadka-demo/<tag>-rN.pdf|png i <tag>.trace.json
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from scripts.wukadka_demo import DEMO, material  # noqa: E402
from app.engine.art_director import art_direct  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--tag", default="ad")
    ap.add_argument("--composer", default="framed_cover:wukadka")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--step", type=int, default=None, help="ile rund w tym wywołaniu")
    a = ap.parse_args()
    res = art_direct(material(), a.composer, rounds=a.rounds, out_dir=DEMO, tag=a.tag, resume=a.resume, max_new_rounds=a.step)
    print("STAN:", res["trace"].get("done") or "w toku")
    t = res["trace"]
    print(json.dumps({"plan": t.get("plan"), "rejected": t.get("plan_rejected_moves")}, ensure_ascii=False, indent=1)[:4000])
    for r in t["rounds"]:
        rv = r.get("review") or {}
        print(f"--- runda {r['round']} bramka {r['gate']} ocena {rv.get('ocena')} do_druku {rv.get('do_druku')} accepted {r.get('accepted')}")
        print("  geny", json.dumps(r["genes"], ensure_ascii=False))
        for v in r["violations"][:6]:
            print("  !", v)
        print("  werdykt:", rv.get("werdykt"))
        for d in rv.get("defekty") or []:
            print("  ", d.get("id"), d.get("waga"), d.get("gdzie"), "—", d.get("opis"))
        for f in rv.get("poprawki") or []:
            print("  →", f)
        if r.get("rejected_fixes"):
            print("  odrzucone:", r["rejected_fixes"])
        if r.get("pairwise"):
            print("  pary:", r["pairwise"])
    print("najlepsza runda:", t.get("best_round"))


if __name__ == "__main__":
    main()
