import json, re, urllib.request, urllib.parse
def q(s, rows=60):
    u = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(
        {"q": s, "fl[]": ["identifier", "title", "year", "date", "language", "collection", "imagecount"], "rows": rows,
         "output": "json", "sort[]": "downloads desc"}, doseq=True)
    return json.load(urllib.request.urlopen(u, timeout=90))["response"]["docs"]
BOOKS = {"inlibrary", "printdisabled", "internetarchivebooks", "americana", "gutenberg"}
G = {
 "pl_tv_guide": ([('mediatype:texts AND (title:"Fakt TV" OR title:"Super Express TV" OR title:"Tele Tydzień" OR title:"Telemagazyn" OR title:"Tele Świat" OR title:"Kurier TV" OR title:"Tele Max" OR title:"Tele Program")', 80)],
                 r"(fakt tv|super express tv|tele ?tydzie|telemagazyn|tele [śs]wiat|kurier tv|tele max|tele program)", 25),
 "pl_newspaper": ([('mediatype:texts AND (title:"Gazeta Wyborcza" OR title:"Dziennik Bałtycki" OR title:"Super Express" OR title:"Fakt" OR title:"Rzeczpospolita" OR title:"Gazeta Polska" OR title:"Nasz Dziennik" OR title:"Głos" OR title:"Kurier Lubelski" OR title:"Gazeta Krakowska" OR title:"Dziennik Zachodni" OR title:"Express Ilustrowany" OR title:"Trybuna" OR title:"Życie Warszawy" OR title:"Gazeta Lubuska")', 120)],
                 r"(gazeta|dziennik|super express|fakt|rzeczpospolita|kurier|express|trybuna|[żz]ycie|g[łl]os)", 40),
 "pl_magazine": ([('mediatype:texts AND (title:Polityka OR title:Wprost OR title:"Newsweek Polska" OR title:"Przekrój" OR title:"Tygodnik Powszechny" OR title:"Do Rzeczy" OR title:"Sieci" OR title:"Angora" OR title:"Przegląd")', 80)],
                 r"(polityka|wprost|newsweek|przekr[óo]j|tygodnik|do rzeczy|sieci|angora|przegl[ąa]d)", 25),
 "tabloid": ([('mediatype:texts AND (title:"National Enquirer" OR title:"Weekly World News" OR title:"Sun (UK)" OR title:"Daily Mirror" OR title:"Daily Star" OR title:"Bild-Zeitung" OR title:"Bild Zeitung" OR title:"New York Post" OR title:"Daily News" OR title:"Star Magazine" OR title:"Globe tabloid" OR title:"Midweek Sport" OR subject:tabloid)', 150)],
             r"(enquirer|weekly world|mirror|daily star|bild|new york post|daily news|star magazine|globe|midweek sport|tabloid|super express|fakt\b)", 40),
}
sel = json.load(open("ia_selection.json"))
for k, (queries, rx, keep) in G.items():
    docs = []
    for s, rows in queries:
        docs += q(s, rows)
    out = []
    for d in docs:
        t = str(d.get("title") or "")
        cols = set(d.get("collection") or []) if isinstance(d.get("collection"), list) else {d.get("collection")}
        if cols & BOOKS or not re.search(rx, t, re.I) or re.search(r"(pdfdrive|ebook|history of|introduction)", t, re.I):
            continue
        if d["identifier"] in {x["identifier"] for x in out}:
            continue
        out.append(d)
    sel[k] = out[:keep]
    print(k, len(sel[k]), [t["title"][:35] for t in sel[k][:8]])
# clean the other groups from books too
for k in ("world_newspaper", "consumer_magazine", "news_magazine", "tv_guide", "us_local_newspaper"):
    sel[k] = [d for d in sel[k] if not ((set(d.get("collection") or []) if isinstance(d.get("collection"), list) else {d.get("collection")}) & BOOKS)]
    print(k, len(sel[k]))
json.dump(sel, open("ia_selection.json", "w"), ensure_ascii=False)
print("total", sum(len(v) for v in sel.values()))
