"""Freedom Forum front pages: 520 titles × several dates, measured, PDF deleted."""
import json, os, sys, time, urllib.request, concurrent.futures as cf
# ff_list.json comes from ff_list.py (Freedom Forum gallery listing)
from measure import measure_pdf
papers = json.load(open("ff_list.json"))
DATES = ["2026-10-15", "2026-10-11", "2026-10-13", "2026-09-20", "2026-08-14", "2026-06-15", "2026-01-15", "2025-10-15"]
OUT = "corpus_ff.jsonl"
done = set()
if os.path.exists(OUT):
    for l in open(OUT):
        try:
            r = json.loads(l); done.add((r["slug"], r["date"]))
        except Exception:
            pass
jobs = [(p, d) for d in DATES for p in papers if p.get("newsPaper") and (p["newsPaper"]["slug"], d) not in done]
print("jobs", len(jobs), flush=True)
os.makedirs("tmp", exist_ok=True)

def fetch(job):
    p, d = job
    slug = p["newsPaper"]["slug"]
    url = f"https://d2dr22b2lm4tvw.cloudfront.net/{slug}/{d}/front-page.pdf"
    path = f"tmp/ff_{slug}_{d}.pdf"
    try:
        urllib.request.urlretrieve(url, path)
        return job, path, None
    except Exception as e:
        return job, None, str(e)[:120]

with open(OUT, "a") as out, cf.ThreadPoolExecutor(4) as ex:
    n = 0
    for (p, d), path, err in ex.map(fetch, jobs):
        np_ = p["newsPaper"]
        rec = {"source": "freedomforum", "slug": np_["slug"], "title": np_["name"], "city": np_.get("city"),
               "state": np_.get("state"), "country": np_.get("country"), "region": np_.get("region"), "date": d,
               "kind": "daily_newspaper"}
        if err:
            rec["error"] = err
        else:
            try:
                rec["pages"] = measure_pdf(path, max_pages=2)
            except Exception as e:
                rec["error"] = str(e)[:200]
            os.remove(path)
        out.write(json.dumps(rec, ensure_ascii=False) + "\n"); out.flush()
        n += 1
        if n % 100 == 0:
            print(n, time.strftime("%H:%M:%S"), flush=True)
print("done", flush=True)
