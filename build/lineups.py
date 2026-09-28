"""Each club's eleven on offense and eleven on defense, for the search card's
   formation: who started the club's last game, with tonight's injury report
   laid over it (Jose, Sep 28, 2026: the Eagles' offense against the Bears'
   defense in Kalshi's jerseys, a red edge on a starter who is out and his
   backup's number in the spot, a yellow edge on one who is questionable).

   All of it is ESPN's, read for every NFL game in the next eight days:

     the starters     the club's last finished game, its roster's starter flags
                      -- the same men the NFL's gamebook lists as the lineup
     positions        the club's roster: each man's position and number
     tonight          the game summary's injury report
     the backup       the club's depth chart: the next man at an out
                      starter's spot who is not out himself

   Written to site/lineups.json:
     {game id: {club: {"off": [man, ...], "def": [man, ...]}}}
   a man is {"n": number, "p": position, "s": "out" | "q" | ""}

       python3 build/lineups.py
"""
import datetime as dt
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from curl_cffi import requests as rq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(D, "site", "lineups.json")
SITE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
NOW = dt.datetime.now(dt.timezone.utc)
try:
    HELD = json.load(open(os.path.join(D, "data", "wire_held.json")))
except (OSError, ValueError):
    HELD = {}
# out means he does not play; questionable means he might not
OUTS = ("Out", "Injured Reserve", "Doubtful", "Suspension", "Physically Unable to Perform")
QS = ("Questionable",)
OFF = {"QB", "RB", "FB", "WR", "TE", "C", "G", "OG", "T", "OT", "OL"}
DEF = {"DE", "DT", "NT", "DL", "LB", "OLB", "ILB", "MLB", "CB", "S", "FS", "SS", "DB", "EDGE"}
_OL = ("lt", "lg", "c", "rg", "rt")
_DL = ("lde", "ldt", "nt", "rdt", "rde")
_LB = ("lolb", "lilb", "mlb", "rilb", "rolb", "wlb", "slb")
_DB = ("lcb", "rcb", "nb", "fs", "ss")
SPOTS = {"QB": ("qb",), "RB": ("rb", "hb", "fb"), "FB": ("fb", "rb"), "WR": ("wr",), "TE": ("te",),
         "C": _OL, "G": _OL, "OG": _OL, "T": _OL, "OT": _OL, "OL": _OL,
         "DE": _DL + _LB, "DT": _DL, "NT": _DL, "DL": _DL, "EDGE": _DL + _LB,
         "LB": _LB, "OLB": _LB + _DL, "ILB": _LB, "MLB": _LB,
         "CB": _DB, "S": _DB, "FS": _DB, "SS": _DB, "DB": _DB}


def get(u):
    try:
        r = rq.get(u.replace("http://", "https://"), impersonate="chrome", timeout=30)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def season():
    return NOW.year if NOW.month >= 3 else NOW.year - 1


def roster(tid):
    """{espn id: (number, position)} for the club."""
    out = {}
    for g in (get("%s/teams/%s/roster" % (SITE, tid)) or {}).get("athletes") or []:
        for a in g.get("items") or []:
            out[str(a.get("id"))] = (str(a.get("jersey") or ""), ((a.get("position") or {}).get("abbreviation") or "").upper())
    return out


def jersey(pid):
    a = get("%s/seasons/%d/athletes/%s" % (CORE, season(), pid)) or {}
    return str(a.get("jersey") or "")


def last_game(tid):
    last = None
    for e in (get("%s/teams/%s/schedule" % (SITE, tid)) or {}).get("events") or []:
        c = (e.get("competitions") or [{}])[0]
        if ((c.get("status") or {}).get("type") or {}).get("completed"):
            last = str(e["id"])
    return last


def starters(eid, tid):
    d = get("%s/events/%s/competitions/%s/competitors/%s/roster" % (CORE, eid, eid, tid)) or {}
    return [(str(x.get("playerId")), str(x.get("jersey") or "")) for x in d.get("entries") or [] if x.get("starter")]


def chart(tid):
    """The club's depth chart as {"off": {spot: [ids]}, "def": {spot: [ids]}}:
       offense from its three-receiver set, defense from its base 4-3 or
       3-4. A spot ESPN numbers more than once -- the three receivers share
       "wr", told apart by slot -- becomes wr1, wr2, wr3 in slot order. The
       nickel back is left out: eleven a side, always (Jose, Sep 28, 2026)."""
    d = get("%s/seasons/%d/teams/%s/depthcharts" % (CORE, season(), tid)) or {}
    out = {"off": {}, "def": {}}
    for it in d.get("items") or []:
        name = (it.get("name") or "").lower()
        pos = it.get("positions") or {}
        side = "off" if "qb" in pos else "def" if name.startswith("base") else None
        if not side or out[side]:
            continue
        for key, v in pos.items():
            if key == "nb":
                continue
            groups = {}
            for a in v.get("athletes") or []:
                m = re.search(r"/athletes/(\d+)", (a.get("athlete") or {}).get("$ref", ""))
                if m:
                    groups.setdefault(a.get("slot") or 0, []).append(m.group(1))
            slots = sorted(groups)
            for n, sl in enumerate(slots):
                spot = key if len(slots) == 1 else "%s%d" % (key, n + 1)
                out[side][spot] = groups[sl]
    return out


# the eleven spots a side, and nothing else: five up front, the passer, one
# back, one tight end, three receivers; the defense as its chart names it
OFFSPOTS = ("lt", "lg", "c", "rg", "rt", "qb", "rb", "te", "wr1", "wr2", "wr3")


def club(tid, hurt, qb=None):
    """One club's two elevens off its depth chart, tonight's report laid over
       it: the first man at each spot starts; one who is out gives way to the
       next man there who is not, and the spot wears that man's number with a
       red edge; one who is questionable keeps it with a yellow edge."""
    ros, ch = roster(tid), chart(tid)
    if not ch["off"] or not ch["def"]:
        return None
    taken = set()
    for spots in ch.values():
        for ids in spots.values():
            if ids:
                taken.add(ids[0])
    side = {"off": [], "def": []}
    for which, spots in (("off", [(k, ch["off"].get(k) or ch["off"].get(k.rstrip("0123456789")) or []) for k in OFFSPOTS]),
                         ("def", list(ch["def"].items()))):
        for k, ids in spots:
            if not ids:
                continue
            first = ids[0]
            if k == "qb" and qb and qb in ros:
                # the man named to start tonight, whoever the chart has first
                s = "out" if qb != first and hurt.get(first, "") in OUTS else \
                    "q" if hurt.get(qb, "") in QS else ""
                side[which].append({"n": ros[qb][0] or jersey(qb), "p": "QB", "s": s, "k": k})
                continue
            st = hurt.get(first, "")
            s = "out" if st in OUTS else "q" if st in QS else ""
            man = first
            if s == "out":
                man = next((x for x in ids[1:] if hurt.get(x, "") not in OUTS and x not in taken), first)
                taken.add(man)
            num = (ros.get(man) or ("", ""))[0] or jersey(man)
            side[which].append({"n": num, "p": (ros.get(first) or ("", ""))[1], "s": s, "k": k})
    return side


def game(g):
    gid = str(g[1])
    d = get("%s/summary?event=%s" % (SITE, gid)) or {}
    comp = (((d.get("header") or {}).get("competitions")) or [{}])[0]
    teams = {str((c.get("team") or {}).get("abbreviation")): str((c.get("team") or {}).get("id"))
             for c in comp.get("competitors") or []}
    hurt = {}
    for t in d.get("injuries") or []:
        for i in t.get("injuries") or []:
            hurt[str((i.get("athlete") or {}).get("id"))] = i.get("status") or ""
    # news seen before ESPN's report has it, any position, held by hand in
    # data/wire_held.json until ESPN says something newer (Sep 28, 2026)
    for pid, h in HELD.items():
        if h.get("status"):
            hurt[str(pid)] = h["status"]
    named = {str(g[3]): str(g[6] or ""), str(g[4]): str(g[8] or "")}
    out = {}
    for ab, tid in teams.items():
        if tid and tid != "None":
            one = club(tid, hurt, named.get(ab) or None)
            if one:
                out[ab] = one
    return gid, out


def main():
    s = pagefile.read()
    m = re.search(r"  var SCHED = (\[\[.*?\]\]);", s, re.S)
    games = []
    for g in json.loads(m.group(1)) if m else []:
        try:
            t = dt.datetime.fromisoformat(g[2].replace("Z", "+00:00"))
        except ValueError:
            continue
        if NOW - dt.timedelta(hours=5) <= t <= NOW + dt.timedelta(days=8):
            games.append(g)
    out = {}
    with ThreadPoolExecutor(6) as ex:
        for gid, lu in ex.map(game, games):
            if lu:
                out[gid] = lu
    json.dump(out, open(OUT, "w"), separators=(",", ":"))
    marked = sum(1 for g in out.values() for c in g.values() for side in c.values() for x in side if x["s"])
    print("lineups: %d games, %d clubs, %d men marked out or questionable"
          % (len(out), sum(len(g) for g in out.values()), marked))


if __name__ == "__main__":
    main()
