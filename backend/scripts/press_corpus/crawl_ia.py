"""archive.org full issues: every page measured (≤48 sampled evenly), PDF deleted."""
import json, os, time, urllib.request, urllib.parse, concurrent.futures as cf
import pymupdf
from measure import measure_page
sel = json.load(open("ia_selection.json"))
OUT = "corpus_ia.jsonl"
done = set()
if os.path.exists(OUT):
    for l in open(OUT):
        try: done.add(json.loads(l)["identifier"])
        except Exception: pass
seen = set(done)
jobs = []
for k, docs in sel.items():
    for d in docs:
        if d["identifier"] in seen:
            continue
        seen.add(d["identifier"]); jobs.append((k, d))
print("jobs", len(jobs), flush=True)
os.makedirs("tmp", exist_ok=True)

def pick(ident):
    md = json.load(urllib.request.urlopen(f"https://archive.org/metadata/{urllib.parse.quote(ident)}", timeout=60))
    files = md.get("files") or []
    pdfs = [f for f in files if f["name"].lower().endswith(".pdf")]
    orig = [f for f in pdfs if not f["name"].endswith("_text.pdf") and f.get("source") == "original"]
    text = [f for f in pdfs if f["name"].endswith("_text.pdf")]
    opts = [f for f in orig[:1] + text[:1] if 0 < int(f.get("size") or 0) < 250e6]
    cand = min(opts, key=lambda f: int(f["size"])) if opts else None
    return md.get("metadata") or {}, cand

def fetch(job):
    kind, d = job
    ident = d["identifier"]
    try:
        meta, f = pick(ident)
        if not f:
            return job, None, None, "no pdf"
        path = f"tmp/ia_{len(jobs)}_{abs(hash(ident))}_{kind}.pdf"
        url = f"https://archive.org/download/{urllib.parse.quote(ident)}/{urllib.parse.quote(f['name'])}"
        urllib.request.urlretrieve(url, path)
        return job, path, {"file": f["name"], "language": meta.get("language"), "date": meta.get("date"),
                           "collection": meta.get("collection")}, None
    except Exception as e:
        return job, None, None, str(e)[:160]

def bounded(ex, fn, items, ahead=2):
    """map with at most `ahead` downloads in flight (disk stays small)."""
    from collections import deque
    q = deque()
    it = iter(items)
    for _ in range(ahead):
        try: q.append(ex.submit(fn, next(it)))
        except StopIteration: break
    while q:
        r = q.popleft().result()
        try: q.append(ex.submit(fn, next(it)))
        except StopIteration: pass
        yield r

with open(OUT, "a") as out, cf.ThreadPoolExecutor(2) as ex:
    for (kind, d), path, meta, err in bounded(ex, fetch, jobs):
        rec = {"source": "archive.org", "identifier": d["identifier"], "title": d.get("title"), "year": d.get("year"),
               "kind": kind, **(meta or {})}
        if err:
            rec["error"] = err
        else:
            try:
                with pymupdf.open(path) as doc:
                    n = doc.page_count
                    idx = list(range(n)) if n <= 48 else sorted({round(i * (n - 1) / 47) for i in range(48)})
                    pages = []
                    for i in idx:
                        try:
                            m = measure_page(doc[i])
                        except Exception as e:
                            m = {"error": str(e)[:120]}
                        m.update(page_index=i, page_count=n, page_role="front" if i == 0 else ("back" if i == n - 1 else "inside"))
                        pages.append(m)
                rec["pages"] = pages
            except Exception as e:
                rec["error"] = str(e)[:200]
            if os.path.exists(path):
                os.remove(path)
        out.write(json.dumps(rec, ensure_ascii=False) + "\n"); out.flush()
        print(time.strftime("%H:%M:%S"), kind, d["identifier"][:50], len(rec.get("pages") or []), rec.get("error", ""), flush=True)
print("done", flush=True)
