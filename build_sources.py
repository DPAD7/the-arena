"""Work out, once, where every price on the board comes from.

   Each price carries DraftKings' own selection id in data-oid, and those ids
   hold still across a repricing — 206 of 206 checked on the Lions game — so
   a price can be looked up again later by the same id. What has to be
   written down is which request returns it: most sit under an event's own
   category, but the first-quarter receptions and the head-to-head passing
   yards are only served league-wide, under a subcategory.

   Writes sources.json. Rerun it if the board gains a kind of price it has
   never carried before.
"""
import collections
import glob
import json
import os
import re

D = os.path.dirname(os.path.abspath(__file__))
board = set(re.findall(r'data-oid="([^"]*)"', open(D + "/site/index.html").read()))

# the league-wide subcategories, found by probing: nothing else serves these
LEAGUE = [
    {"path": "/sportscontent/dkusmd/v1/leagues/88808/categories/1342/subcategories/18527",
     "what": "receptions in the first quarter"},
    {"path": "/sportscontent/dkusmd/v1/leagues/88808/categories/1185/subcategories/11977",
     "what": "head to head passing yards"},
]

events = collections.defaultdict(lambda: {"cats": set(), "oids": set(),
                                          "start": None, "name": None})
for path in sorted(glob.glob(D + "/cache/*_cat*.json")):
    m = re.match(r"(\d+)_cat(\d+)\.json$", os.path.basename(path))
    if not m:
        continue
    eid, cat = m.group(1), int(m.group(2))
    try:
        d = json.load(open(path))
    except Exception:
        continue
    ours = {s.get("id") for s in (d.get("selections") or [])} & board
    if not ours:
        continue
    e = events[eid]
    e["cats"].add(cat)
    e["oids"] |= ours
    for x in (d.get("events") or []):
        if str(x.get("id")) == eid:
            e["start"] = x.get("startEventDate")
            e["name"] = x.get("name")

# which oids the league-wide requests answer for
league_oids = set()
for name, src in (("rec1q", LEAGUE[0]), ("h2h_fresh", LEAGUE[1])):
    f = D + "/cache/%s.json" % name
    if not os.path.exists(f):
        continue
    d = json.load(open(f))
    # which market each selection belongs to, and which event each market is on,
    # so a league-wide request can still be gated on whether its game has kicked
    on = {m["id"]: str(m.get("eventId")) for m in (d.get("markets") or [])}
    mine = {}
    for s in (d.get("selections") or []):
        if s.get("id") in board:
            mine[s["id"]] = on.get(s.get("marketId"))
    src["oids"] = sorted(mine)
    src["event_of"] = mine
    league_oids |= set(mine)

out = {
    "events": [
        {"id": eid, "name": e["name"], "start": e["start"],
         "cats": sorted(e["cats"]), "oids": sorted(e["oids"])}
        for eid, e in sorted(events.items(), key=lambda kv: kv[1]["start"] or "")
    ],
    "league": LEAGUE,
}
json.dump(out, open(D + "/sources.json", "w"), indent=1)

covered = set(league_oids)
for e in out["events"]:
    covered |= set(e["oids"])
print("events:", len(out["events"]), "| league-wide requests:", len(LEAGUE))
print("prices on the board:", len(board), "| accounted for:", len(covered),
      "| unaccounted:", len(board - covered))
for o in sorted(board - covered):
    print("   no source:", o)
