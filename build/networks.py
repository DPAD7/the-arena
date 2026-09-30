"""Who is showing each game, from theScore's own listings.

   The watch mark on a card should open the app that carries the game: Prime
   Video for Thursday night, Netflix for its own games, Peacock for theirs,
   and YouTube TV for everything else. theScore's media feed carries the US
   listing on every event; the clubs are looked up in the register, never
   guessed. Written to site/networks.json as {espn event id: "Prime Video"},
   and each game's theScore box score to site/scoreboxes.json as
   {espn event id: "/ncaaf/box_scores/34757"}.

   Usage:  python3 networks.py
"""
import datetime as dt
import json
import os
import sys
import re
import sqlite3
import subprocess

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "qbspy.db")
FEED = {"nfl": "https://api.thescore.com/nfl/events?limit=400",
        "ncaaf": "https://api.thescore.com/ncaaf/events?limit=1000"}


def get(u):
    out = subprocess.run(["curl", "-s", "--max-time", "60", "-A", "Mozilla/5.0", u],
                         capture_output=True, text=True).stdout
    try:
        return json.loads(out)
    except ValueError:
        return []


def main():
    s = pagefile.read()
    db = sqlite3.connect(DB)
    club = {w: a for w, a in db.execute("select written, abbr from club_name")}
    cfb = json.load(open(D + "/data/cfb_names.json"))
    out, boxes = {}, {}
    for league, var in (("nfl", "SCHED"), ("ncaaf", "CFB")):
        rows = json.loads(re.search(r"var %s = (\[\[.*?\]\]);" % var, s, re.S).group(1))
        ours = {}
        for g in rows:
            ours[(g[3], g[4], g[2][:10])] = g[1]
        listed = 0
        for e in get(FEED[league]):
            tv = ((e.get("tv_listings_by_country_code") or {}).get("us") or [])
            a, h = e.get("away_team") or {}, e.get("home_team") or {}
            an = cfb.get(a.get("full_name")) or club.get(a.get("full_name")) or cfb.get(a.get("name")) or club.get(a.get("name"))
            hn = cfb.get(h.get("full_name")) or club.get(h.get("full_name")) or cfb.get(h.get("name")) or club.get(h.get("name"))
            if not an or not hn:
                continue
            when = dt.datetime.strptime(e["game_date"], "%a, %d %b %Y %H:%M:%S %z")
            for day in (when, when - dt.timedelta(days=1)):
                eid = ours.get((an, hn, day.strftime("%Y-%m-%d")))
                if eid:
                    box = (e.get("box_score") or {}).get("api_uri")
                    if box:
                        boxes[eid] = box
                    if tv:
                        out[eid] = tv[0].get("long_name") or tv[0].get("short_name")
                        listed += 1
                    break
        print("%s: %d games listed" % (league.upper(), listed))
    json.dump(out, open(D + "/site/networks.json", "w"), separators=(",", ":"))
    # each game's box score on theScore, for the page to read when ESPN's
    # comes back empty: Oklahoma State at West Virginia had no player in
    # ESPN's box all night (Jose, Sep 26, 2026)
    json.dump(boxes, open(D + "/site/scoreboxes.json", "w"), separators=(",", ":"))
    print("scoreboxes: %d games" % len(boxes))
    seen = {}
    for v in out.values():
        seen[v] = seen.get(v, 0) + 1
    print("networks: %d games | %s" % (len(out), ", ".join("%s %d" % kv for kv in sorted(seen.items(), key=lambda x: -x[1])[:10])))


if __name__ == "__main__":
    main()
