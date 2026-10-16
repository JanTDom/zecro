import json, os, sys, urllib.request, time
URL="https://45hclcjhi5bljn7uixadeenerq.appsync-api.us-east-1.amazonaws.com/graphql"
KEY=os.environ.get("FF_APPSYNC_KEY")  # the public x-api-key the frontpages.freedomforum.org page itself sends
if not KEY:
    sys.exit("set FF_APPSYNC_KEY (read it from the gallery page's network requests)")
Q="""query q($limit:Int,$nextToken:String){listActiveFrontPages(limit:$limit,nextToken:$nextToken){nextToken items{id title date pdf images{large} newsPaper{name slug city state country region website}}}}"""
items,tok=[],None
while True:
    body=json.dumps({"query":Q,"variables":{"limit":200,"nextToken":tok}}).encode()
    r=urllib.request.Request(URL,data=body,headers={"Content-Type":"application/json","x-api-key":KEY})
    d=json.load(urllib.request.urlopen(r,timeout=60))
    if d.get("errors"): print(d["errors"]); break
    page=d["data"]["listActiveFrontPages"]; items+=page["items"]; tok=page["nextToken"]
    print(len(items)); 
    if not tok: break
    time.sleep(.5)
json.dump(items,open("ff_list.json","w"),ensure_ascii=False)
from collections import Counter
print(Counter(i["newsPaper"]["country"] for i in items if i.get("newsPaper")).most_common(40))
print(Counter(i["date"] for i in items).most_common(5))
print(items[0])
