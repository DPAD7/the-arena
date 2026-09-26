"""What could sink a leg, per game, for the page to warn by when a leg is added.

   Grunkemeyer 2+ PTD went on a slip for a game in the rain with 31 mph gusts,
   and nothing said so (Jose, Sep 26, 2026: "anything else that would crush my
   parlay like the VT one"). ESPN's game summary carries all of it, read once a
   sweep for every game in the next eight days, into site/alerts.json:

     {game id: {
        "wx":     {"c": condition, "t": temp F, "g": gust mph, "p": precip %, "in": 1 if covered},
        "spread": the favorite's points, from ESPN's pickcenter,
        "total":  the game's over/under, the same place,
        "out":    [{"id", "name", "pos", "status", "team", "lead": "receiving" | "rushing" | ""}],
     }}

   The page reads the file; it never asks ESPN for this itself.

       python3 build/alerts.py
"""
import datetime as dt
import json
import os
import re
import sys

from curl_cffi import requests as rq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(D, "site", "alerts.json")
NOW = dt.datetime.now(dt.timezone.utc)
HURT = ("Out", "Doubtful", "Questionable", "Injured Reserve", "Suspension")


def main():
    s = pagefile.read()
    games = []
    for var, lg in (("SCHED", "nfl"), ("CFB", "college-football")):
        m = re.search(r"  var %s = (\[\[.*?\]\]);" % var, s, re.S)
        for r in json.loads(m.group(1)) if m else []:
            try:
                k = dt.datetime.fromisoformat(r[2].replace("Z", "+00:00"))
            except ValueError:
                continue
            if NOW - dt.timedelta(hours=5) < k < NOW + dt.timedelta(days=8):
                games.append((str(r[1]), lg))
    out = {}
    for gid, lg in games:
        try:
            d = rq.get("https://site.api.espn.com/apis/site/v2/sports/football/%s/summary?event=%s" % (lg, gid),
                       impersonate="chrome124", timeout=20).json()
        except Exception:
            continue
        gi = d.get("gameInfo") or {}
        w, v = gi.get("weather") or {}, gi.get("venue") or {}
        e = {"wx": {"c": w.get("conditionId"), "t": w.get("temperature"), "g": w.get("gust"),
                    "p": w.get("precipitation"), "in": 1 if v.get("indoor") else 0}}
        pc = (d.get("pickcenter") or [{}])[0] or {}
        if pc.get("spread") is not None:
            e["spread"] = abs(float(pc["spread"]))
        if pc.get("overUnder") is not None:
            e["total"] = float(pc["overUnder"])
        # who leads each club in receiving and rushing
        lead = {}
        for t in d.get("leaders") or []:
            for cat in t.get("leaders") or []:
                if cat.get("name") in ("receivingYards", "rushingYards"):
                    for x in cat.get("leaders") or []:
                        lead[str((x.get("athlete") or {}).get("id"))] = "receiving" if cat["name"] == "receivingYards" else "rushing"
        hurt = []
        for t in d.get("injuries") or []:
            ab = ((t.get("team") or {}).get("abbreviation")) or ""
            for i in t.get("injuries") or []:
                a = i.get("athlete") or {}
                st = i.get("status") or ""
                pos = ((a.get("position") or {}).get("abbreviation")) or ""
                if st not in HURT or pos not in ("QB", "WR", "TE", "RB"):
                    continue
                hurt.append({"id": str(a.get("id")), "name": a.get("displayName"), "pos": pos,
                             "status": st, "team": ab, "lead": lead.get(str(a.get("id")), "")})
        if hurt:
            e["out"] = hurt
        out[gid] = e
    json.dump(out, open(OUT, "w"), separators=(",", ":"), sort_keys=True)
    print("alerts: %d games, %d in wind or rain, %d with injuries"
          % (len(out), sum(1 for x in out.values() if not x["wx"]["in"] and ((x["wx"]["g"] or 0) >= 15 or (x["wx"]["p"] or 0) >= 50)),
             sum(1 for x in out.values() if x.get("out"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
