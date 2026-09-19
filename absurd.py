"""A price nobody could take is not a price.

   Twelve college cards came back at −100000 and worse: risk a hundred
   thousand to win a hundred. DraftKings publishes those to keep the market
   shaped, not to take the bet. On the board they read as real, and one of
   them sitting beside a −2800 makes the −2800 look wrong too.

   So anything shorter than −10000 falls back to the spread, which is what the
   book is actually saying about the game, and is already how the cards with no
   moneyline at all are shown.
"""
import concurrent.futures as cf
import json
import os
import re
import subprocess

D = os.path.dirname(os.path.abspath(__file__))
CORE = ("http://sports.core.api.espn.com/v2/sports/football/leagues/college-football"
        "/events/%s/competitions/%s/odds/100")
FLOOR = -10000


def num(x):
    x = str(x).replace("−", "-")
    try:
        return int(x)
    except ValueError:
        return None


def spread_of(eid):
    out = subprocess.run(["curl", "-s", "-m", "25", CORE % (eid, eid)],
                         capture_output=True, text=True).stdout
    try:
        d = json.loads(out or "{}")
    except Exception:
        return eid, None
    sp = d.get("spread")
    return eid, (float(sp) if sp is not None else None)


s = open(D + "/master.html").read()
m = re.search(r'  var CFB = (\[\[.*?\]\]);\n', s, re.S)
cfb = json.loads(m.group(1))
bad = [g for g in cfb
       if (num(g[10]) or 0) <= FLOOR or (num(g[12]) or 0) <= FLOOR]
print("cards priced below %d: %d" % (FLOOR, len(bad)))

got = {}
with cf.ThreadPoolExecutor(max_workers=8) as pool:
    for eid, sp in pool.map(lambda g: spread_of(g[1]), bad):
        if sp is not None:
            got[eid] = sp

fixed = dropped = 0
for g in bad:
    sp = got.get(g[1])
    if sp is None:
        g[10] = g[11] = g[12] = g[13] = ""
        dropped += 1
        continue
    home, away = sp, -sp
    f = lambda v: "s" + ("+" if v > 0 else "−") + ("%g" % abs(v))
    g[10], g[11] = f(away), ""
    g[12], g[13] = f(home), ""
    fixed += 1
print("shown as a spread instead: %d | left blank: %d" % (fixed, dropped))

s = s[:m.start()] + "  var CFB = " + json.dumps(cfb, separators=(",", ":")) + ";\n" + s[m.end():]
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
