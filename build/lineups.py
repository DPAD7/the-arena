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


def depth(tid):
    """Every depth list the club keeps, as (spot, [espn ids in order]) --
       the spot is ESPN's own key: lt, lg, c, rg, rt, te, wr, lde, ldt, mlb,
       lcb, fs and the rest, which is how each man is put in his place"""
    d = get("%s/seasons/%d/teams/%s/depthcharts" % (CORE, season(), tid)) or {}
    lists = []
    for it in d.get("items") or []:
        for key, pos in (it.get("positions") or {}).items():
            ids = []
            for a in pos.get("athletes") or []:
                ref = (a.get("athlete") or {}).get("$ref", "")
                m = re.search(r"/athletes/(\d+)", ref)
                if m:
                    ids.append(m.group(1))
            if ids:
                lists.append((key, ids))
    return lists


def club(tid, hurt, qb=None):
    """One club's two elevens, tonight's report laid over its last lineup."""
    eid = last_game(tid)
    if not eid:
        return None
    ros, first = roster(tid), starters(eid, tid)
    if not first:
        return None
    lists = depth(tid)
    taken = {pid for pid, _ in first}
    side = {"off": [], "def": []}
    for pid, num in first:
        pos = (ros.get(pid) or ("", ""))[1]
        num = (ros.get(pid) or (num, ""))[0] or num
        which = "off" if pos in OFF else "def" if pos in DEF else None
        if not which:
            continue
        st = hurt.get(pid, "")
        s = "out" if st in OUTS else "q" if st in QS else ""
        if pos == "QB" and qb and qb in ros:
            # the man named to start tonight, whoever the chart has next
            num, s = ros[qb][0] or num, "" if hurt.get(qb, "") not in QS else "q"
            if qb != pid:
                s = "out" if st in OUTS else s
        elif s == "out":
            # his backup's number in his spot: the next man on any list he is
            # on who is neither out nor already starting elsewhere, and failing
            # that anyone at his position who is free
            found = None
            for _, ids in lists:
                if pid not in ids:
                    continue
                for nxt in ids[ids.index(pid) + 1:]:
                    if nxt in taken or hurt.get(nxt, "") in OUTS or nxt not in ros:
                        continue
                    found = nxt
                    break
                if found:
                    break
            if not found:
                found = next((x for x, v in ros.items() if v[1] == pos and x not in taken
                              and hurt.get(x, "") not in OUTS), None)
            if found:
                # a man signed this week can be on the roster before his number
                # is: his own page has it, and a blank beats the hurt man's
                num = ros[found][0] or jersey(found)
                taken.add(found)
        # his spot on the chart, one that fits his position -- a receiver who
        # also returns kicks is listed first at kr, and that is not where he
        # lines up: where he stands first, else anywhere he is listed
        fit = SPOTS.get(pos, ())
        k = next((key for key, ids in lists if ids and ids[0] == pid and key in fit), None) or \
            next((key for key, ids in lists if pid in ids and key in fit), "")
        side[which].append({"n": num, "p": pos, "s": s, "k": k, "_id": pid})
    # two linemen on one spot: ESPN moves the backup up once a starter is
    # hurt, so the hurt man and his backup both answer to it and a spot goes
    # empty. The hurt man takes the empty spot, wearing the number of whoever
    # stands first there now (Sep 28, 2026: Baltimore's centre)
    line = [m for m in side["off"] if m["k"] in _OL]
    free = [k for k in _OL if k not in {m["k"] for m in line}]
    seen = {}
    for m in sorted(line, key=lambda m: m["s"] == "out"):
        if m["k"] in seen and free:
            k = free.pop(0)
            m["k"] = k
            for key, ids in lists:
                if key != k:
                    continue
                nxt = next((x for x in ids if x not in taken and hurt.get(x, "") not in OUTS and x in ros), None)
                if nxt:
                    m["n"] = ros[nxt][0] or jersey(nxt)
                    taken.add(nxt)
                break
        seen[m["k"]] = 1
    for x in side["off"] + side["def"]:
        x.pop("_id", None)
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
