"""The news, read for the passers before the injury wire has it.

   ESPN's NFL news feed tags every story with the ESPN ids of the men in it,
   so nothing here is matched by name: a headline counts for a passer only
   when he is the first man it is tagged with, and he is on a club's chart in
   site/depth.json or named on the page.

       site.api.espn.com/apis/site/v2/sports/football/nfl/news

   Two kinds of headline are acted on, the same day they run (Jose, Sep 28,
   2026: "I keep having to tell you this person's out"):

     out        "Mayfield (thumb) out at least three weeks", ruled out, on IR,
                doubtful -- held in data/wire_held.json, which wire.py lays
                over ESPN's own injury entry until that entry is newer
     starts     "Keenum to start", named the starter -- held in
                data/qb_named.json against the club's next game, which
                starters.py puts on the card ahead of the chart

   A held mark whose return date has passed is let go.

       python3 build/news.py
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
FEED = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?limit=100"
HELD = os.path.join(D, "data", "wire_held.json")
NAMED = os.path.join(D, "data", "qb_named.json")
DEPTH = os.path.join(D, "site", "depth.json")
NOW = dt.datetime.now(dt.timezone.utc)

# a headline that says he will not play; the ones that say he will are read
# first and win, so "won't miss" and "cleared" never mark a man out
NOT_OUT = re.compile(r"won'?t miss|not expected to miss|avoids|cleared|return(s|ing)? |set to return|"
                     r"no long-term|could play|expected to play|will play|practic", re.I)
IR = re.compile(r"\b(IR|injured reserve)\b", re.I)
OUT = re.compile(r"\)\s+out\b|\bout (for|at least|indefinitely|with|vs\.?|against|this|until|through|\d)|ruled out|will miss|to miss|expected to miss|sidelined|season-ending|"
                 r"torn|to sit|won'?t play|inactive", re.I)
DOUBT = re.compile(r"\bdoubtful\b", re.I)
START = re.compile(r"\b(to start|will start|set to start|slated to start|gets the start|"
                   r"named (the )?starter|start(s|ing)? at QB)\b", re.I)


def load(path):
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return {}


def main():
    try:
        r = rq.get(FEED, impersonate="chrome", timeout=30)
        arts = (r.json() or {}).get("articles") or [] if r.status_code == 200 else []
    except Exception:
        arts = []
    if not arts:
        print("news: the feed did not answer; nothing changed")
        return

    depth = load(DEPTH)
    club_of = {}
    for club, room in depth.items():
        for q in room.get("qbs") or []:
            club_of[str(q["id"])] = (club, q.get("name") or "")
    s = pagefile.read()
    m = re.search(r"  var SCHED = (\[\[.*?\]\]);", s, re.S)
    sched = json.loads(m.group(1)) if m else []
    for g in sched:
        for i, ci in ((5, 3), (7, 4)):
            if g[i + 1]:
                club_of.setdefault(str(g[i + 1]), (g[ci], g[i]))

    held, named = load(HELD), load(NAMED)
    moved = []
    # oldest first, so a later headline about the same man has the last word
    for a in sorted(arts, key=lambda a: a.get("published") or ""):
        if a.get("type") != "HeadlineNews":
            continue
        ids = [str(c["athleteId"]) for c in a.get("categories") or []
               if c.get("type") == "athlete" and c.get("athleteId")]
        if not ids or ids[0] not in club_of:
            continue
        pid, (club, name) = ids[0], club_of[ids[0]]
        head = a.get("headline") or ""
        when = (a.get("published") or "")[:16] + "Z"
        try:
            age = NOW - dt.datetime.fromisoformat(when.replace("Z", "+00:00"))
        except ValueError:
            continue
        if age > dt.timedelta(days=3):
            continue
        src = "ESPN news, %s: %s" % (when, head)
        if NOT_OUT.search(head):
            if pid in held and (held[pid].get("since") or "") < when and held[pid].get("src", "").startswith("ESPN news"):
                del held[pid]
                moved.append("%s %s cleared (%s)" % (club, name, head))
            continue
        status = "Injured Reserve" if IR.search(head) else "Out" if OUT.search(head) else \
            "Doubtful" if DOUBT.search(head) else None
        if status:
            was = held.get(pid) or {}
            if (was.get("since") or "") >= when:
                continue
            ret = None
            wk = re.search(r"(\w+)(?:-to-\w+)? weeks?", head)
            n = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "eight": 8}
            if wk and (wk.group(1).lower() in n or wk.group(1).isdigit()):
                k = int(wk.group(1)) if wk.group(1).isdigit() else n[wk.group(1).lower()]
                ret = (NOW + dt.timedelta(weeks=k)).date().isoformat()
            held[pid] = {"status": status, "abbr": status[0], "type": None, "side": None,
                         "since": when, "returns": ret or was.get("returns"),
                         "note": head, "src": src}
            moved.append("%s %s %s (%s)" % (club, name, status, head))
            continue
        if START.search(head):
            nxt = None
            for g in sorted(sched, key=lambda g: g[2]):
                try:
                    t = dt.datetime.fromisoformat(g[2].replace("Z", "+00:00"))
                except ValueError:
                    continue
                if t > NOW and club in (g[3], g[4]):
                    nxt = g
                    break
            if nxt:
                key = "%s|%s" % (nxt[1], club)
                if (named.get(key) or {}).get("id") != pid:
                    named[key] = {"id": pid, "name": name, "why": src}
                    moved.append("%s %s named to start (%s)" % (club, name, head))

    # a held mark lets go once the date he was due back has passed
    today = NOW.date().isoformat()
    for pid in [p for p, h in held.items() if h.get("returns") and h["returns"] < today]:
        del held[pid]
    # a named start lets go once its game is over
    live = {str(g[1]) for g in sched}
    for key in [k for k in named if k.split("|")[0] not in live]:
        del named[key]

    json.dump(held, open(HELD, "w"), indent=1)
    json.dump(named, open(NAMED, "w"), indent=1)
    for line in moved:
        print("   " + line)
    print("news: %d headlines read, %d passers moved" % (len(arts), len(moved)))


if __name__ == "__main__":
    main()
