"""DraftKings' prices, fetched the easy way -- through ESPN.

   ESPN's odds feed carries DraftKings as a provider, keyed by ESPN's own event
   id. That is worth more than DraftKings' API for this job: no club has to be
   matched by how it is written, and a game that finished three weeks ago still
   answers. The club register stays for the live refresher; this is what fills
   the board.

   Writes odds.json:  espn event id -> [away price, home price, details]
"""
import concurrent.futures as cf
import json
import os
import re
import subprocess
import sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile
CORE = ("http://sports.core.api.espn.com/v2/sports/football/leagues/%s"
        "/events/%s/competitions/%s/odds")


def ask(lg, eid):
    out = subprocess.run(["curl", "-s", "-m", "25", CORE % (lg, eid, eid)],
                         capture_output=True, text=True).stdout
    try:
        d = json.loads(out or "{}")
    except Exception:
        return eid, None
    for it in d.get("items") or []:
        if ((it.get("provider") or {}).get("name") or "") != "DraftKings":
            continue
        h = (it.get("homeTeamOdds") or {}).get("moneyLine")
        a = (it.get("awayTeamOdds") or {}).get("moneyLine")
        if h is None or a is None:
            continue
        return eid, [int(a), int(h), it.get("details") or ""]
    return eid, None


def fmt(v):
    return ("+%d" % v) if v > 0 else ("−%d" % abs(v))


want = []
for g in json.load(open("/tmp/cfb_all.json")):
    want.append(("college-football", g[1]))
print("asking ESPN about %d college games" % len(want))

got = {}
with cf.ThreadPoolExecutor(max_workers=16) as pool:
    for i, (eid, res) in enumerate(pool.map(lambda x: ask(*x), want), 1):
        if res:
            got[eid] = res
        if i % 200 == 0:
            print("   %d asked, %d priced" % (i, len(got)))
print("college games with a DraftKings moneyline: %d of %d" % (len(got), len(want)))
json.dump(got, open(D + "/data/odds.json", "w"))

s = pagefile.read()
m = re.search(r'  var CFB = (\[\[.*?\]\]);\n', s, re.S)
cfb = json.loads(m.group(1))
live = {g[1] for g in cfb if g[11]}      # a live DraftKings id: leave it alone
filled = 0
for g in cfb:
    if g[11]:
        continue
    p = got.get(g[1])
    if not p:
        continue
    g[10], g[11] = fmt(p[0]), ""
    g[12], g[13] = fmt(p[1]), ""
    filled += 1
print("%d already live from DraftKings, %d filled from ESPN, %d still blank"
      % (len(live), filled, sum(1 for g in cfb if not g[10])))
s = s[:m.start()] + "  var CFB = " + json.dumps(cfb, separators=(",", ":")) + ";\n" + s[m.end():]
if not pagefile.write(s):
    print("page changed under us, not written")
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("page %.0f KB" % (len(s) / 1024.0))
