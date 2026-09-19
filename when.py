"""Print the wake plan: every moment the refresher will look at DraftKings,
   and which kickoffs each one is standing in for. Reads nothing but the
   clock and sources.json, asks DraftKings nothing."""
import collections
import datetime
import json
import os
import sys

D = os.path.dirname(os.path.abspath(__file__))
ET = datetime.timezone(datetime.timedelta(hours=-4))
NOW = datetime.datetime.now(datetime.timezone.utc)
BEFORE = (120, 60, 30)

src = json.load(open(D + "/sources.json"))
served = {}
if os.path.exists(D + "/served.json"):
    served = json.load(open(D + "/served.json"))

wakes = collections.defaultdict(list)
for e in src["events"]:
    if not e["start"]:
        continue
    kick = datetime.datetime.fromisoformat(e["start"].replace("Z", "+00:00"))
    if kick <= NOW:
        continue
    for mins in BEFORE:
        w = kick - datetime.timedelta(minutes=mins)
        if w <= NOW and "%s@%d" % (e["id"], mins) not in served:
            continue          # missed while the Mac was off; it will not fire
        wakes[w.replace(second=0, microsecond=0)].append((e["name"], mins))

print("now:", NOW.astimezone(ET).strftime("%a %-m/%-d %-I:%M %p"), "ET")
print("%d wakes ahead, %d already served\n" % (len(wakes), len(served)))
for w in sorted(wakes):
    games = wakes[w]
    ahead = (w - NOW).total_seconds() / 3600.0
    print("%s ET  (in %5.1fh)  %d game%s" %
          (w.astimezone(ET).strftime("%a %-m/%-d %-I:%M %p"), ahead,
           len(games), "" if len(games) == 1 else "s"))
    for name, mins in sorted(games, key=lambda g: -g[1]):
        print("      %3d min before  %s" % (mins, name))
