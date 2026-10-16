import json, urllib.request, urllib.parse
def q(s, rows):
    u = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(
        {"q": s, "fl[]": ["identifier", "title", "year", "date", "language", "collection", "imagecount"], "rows": rows,
         "output": "json", "sort[]": "downloads desc"}, doseq=True)
    return json.load(urllib.request.urlopen(u, timeout=90))["response"]["docs"]
GROUPS = {
  # kind, query, rows
  "pl_tv_guide":        ('mediatype:texts AND (title:"Fakt TV" OR title:"Super Express TV" OR title:"Tele Tydzień" OR title:"Telemagazyn" OR title:"Tele Świat" OR title:"Kurier TV")', 25),
  "pl_newspaper":       ('mediatype:texts AND language:(pol OR polish) AND (collection:newspapers OR subject:gazeta OR subject:dziennik OR title:gazeta OR title:dziennik OR title:kurier OR title:express) AND year:[1990 TO 2026]', 40),
  "pl_magazine":        ('mediatype:texts AND language:(pol OR polish) AND (title:Polityka OR title:Wprost OR title:Newsweek OR title:"Przekrój" OR title:"Tygodnik" OR collection:magazine_rack) AND year:[1990 TO 2026]', 30),
  "tabloid":            ('mediatype:texts AND (subject:tabloid OR title:"National Enquirer" OR title:"Weekly World News" OR title:"Daily Mirror" OR title:"The Sun" OR title:"Bild" OR title:"Daily Star" OR title:"Globe") AND year:[1980 TO 2026]', 40),
  "us_local_newspaper": ('mediatype:texts AND collection:kentuckynewspapers AND year:[2000 TO 2026]', 30),
  "world_newspaper":    ('mediatype:texts AND collection:newspapers_miscellaneous AND year:[2005 TO 2026]', 60),
  "tv_guide":           ('mediatype:texts AND collection:tvguidearchive', 25),
  "news_magazine":      ('mediatype:texts AND (title:Newsweek OR title:"Time Magazine" OR title:"Der Spiegel" OR title:"The Economist" OR title:"Maclean") AND year:[1990 TO 2026]', 30),
  "consumer_magazine":  ('mediatype:texts AND collection:(fashionmagazines OR computermagazines OR gamemagazines) AND year:[1995 TO 2026]', 40),
}
sel = {}
for k, (s, rows) in GROUPS.items():
    try:
        docs = q(s, rows)
    except Exception as e:
        print(k, "ERR", e); continue
    sel[k] = docs
    print(k, len(docs), [str(d.get("title"))[:40] for d in docs[:6]])
json.dump(sel, open("ia_selection.json", "w"), ensure_ascii=False)
