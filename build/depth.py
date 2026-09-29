"""Every club's quarterback room, in order, and who is actually a go.

   The board drew a passer once, when the week was drawn, and nothing ever
   looked again. On Sep 22, 2026 that had Cooper Rush on Atlanta's card while
   ESPN's chart said Michael Penix Jr., Carson Wentz on Minnesota's while the
   chart said Kyler Murray, and no way for a reader to tell either way.

   Two questions a card needs answered, and ESPN answers them in two places
   that do not agree:

       who the club lists first     the depth chart
       whether he can play          the designation beside his name

   The chart page carries both. It is read rather than the core API's
   /depthcharts, which gives the order and nothing else -- on the morning this
   was written the core API had no injury at all for Tua Tagovailoa while the
   chart beside his name read O, and the same for six more quarterbacks
   (Jose, Sep 22, 2026: "who else are we missing"). ESPN's own legend:

       P    Probable            O     Out
       Q    Questionable        PUP   Physically unable to perform
       D    Doubtful            SUS   Suspended
       IR   Injured reserve

   build/wire.py stays, and is still the only source of what is wrong with him
   and when he is due back -- the chart gives a letter, not a diagnosis. Where
   both speak they are written side by side and neither is averaged away.

   Written to site/depth.json:

       {"ATL": {"qbs": [{"id": "4360423", "name": "Michael Penix Jr.",
                         "rank": 1, "mark": null,  "go": 1}, ...],
                "starter": "4360423"}}

   `go` is 1 when nothing stops him. The rule, as Jose set it on Sep 22, 2026:
   the chart names the starter and the mark can veto him. Out, Doubtful, IR,
   PUP or Suspended and the next man who is a go takes the card. Questionable
   is not a veto -- he starts, and the card carries the Q.

   A club ESPN hands back nothing for is left out of the file entirely. An
   absence is not an empty quarterback room, it is an absence, and the board
   keeps whatever it had rather than drawing a blank.

       python3 build/depth.py
"""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(D, "site", "depth.json")
WIRE = os.path.join(D, "site", "wire.json")
PAGE = "https://www.espn.com/nfl/team/depth/_/name/%s"
BLOB = re.compile(r"window\['__espnfitt__'\]=(\{.*?\});</script>", re.S)

# the letters that mean he does not take the field. Q and P are deliberately
# not here (Jose, Sep 22, 2026: "Questionable is not Out")
SITS = ("O", "D", "IR", "PUP", "SUS", "SUSP", "NFI")


def clubs():
    """Our three letters, from data/data.js -- the same table birthdays.py
       reads, so there is one club list on this board and not two."""
    d = open(os.path.join(D, "data", "data.js")).read()
    m = re.search(r"TEAMS = (\[.*?\n\]);", d, re.S)
    if not m:
        raise SystemExit("no TEAMS table in data/data.js")
    return sorted(t["abbr"] for t in json.loads(m.group(1)))


_TIDS = None


def feed(abbr):
    """The same room off ESPN's data feed, for when the chart page will not
       answer -- it does not from GitHub's machines, and the sweep wrote an
       empty file on Sep 28, 2026 that let Mayfield stay on Tampa's card while
       out. The feed has the order but no letters; the wire gives those."""
    global _TIDS
    try:
        if _TIDS is None:
            j = rq.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams",
                       impersonate="chrome", timeout=30).json()
            _TIDS = {t["team"]["abbreviation"]: t["team"]["id"] for t in j["sports"][0]["leagues"][0]["teams"]}
        tid = _TIDS.get(abbr) or _TIDS.get({"WAS": "WSH", "JAC": "JAX"}.get(abbr, abbr))
        if not tid:
            return []
        names = {}
        ro = rq.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/%s/roster" % tid,
                    impersonate="chrome", timeout=30).json()
        for g in ro.get("athletes") or []:
            for a in g.get("items") or []:
                names[str(a.get("id"))] = a.get("displayName") or a.get("fullName")
        import datetime as _dt
        now = _dt.datetime.now()
        yr = now.year if now.month >= 3 else now.year - 1
        d = rq.get("https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/%d/teams/%s/depthcharts"
                   % (yr, tid), impersonate="chrome", timeout=30).json()
        for it in d.get("items") or []:
            qb = (it.get("positions") or {}).get("qb")
            if not qb:
                continue
            out = []
            for rank, a in enumerate(qb.get("athletes") or [], 1):
                m = re.search(r"/athletes/(\d+)", (a.get("athlete") or {}).get("$ref", ""))
                if m:
                    out.append({"id": m.group(1), "name": names.get(m.group(1)) or "", "rank": rank, "mark": None})
            return out
    except Exception:
        return []
    return []


def ask(abbr):
    """One club's quarterback room, in the order the chart lists it."""
    try:
        r = rq.get(PAGE % abbr.lower(), impersonate="chrome", timeout=30)
        if r.status_code != 200:
            return abbr, feed(abbr)
        m = BLOB.search(r.text)
        if not m:
            return abbr, feed(abbr)
        groups = json.loads(m.group(1))["page"]["content"]["depth"]["dethTeamGroups"]
    except Exception:
        return abbr, feed(abbr)

    out, seen = [], set()
    for g in groups:
        for row in g.get("rows", []):
            if not row or row[0] != "QB":
                continue
            # the row is the room in order: first man listed is QB1
            for rank, p in enumerate(row[1:], 1):
                if not isinstance(p, dict):
                    continue
                hit = re.search(r"/id/(\d+)/", p.get("href") or "")
                if not hit or hit.group(1) in seen:
                    continue
                seen.add(hit.group(1))
                marks = p.get("injuries") or []
                out.append({"id": hit.group(1), "name": p.get("displayName"),
                            "rank": rank, "mark": marks[0] if marks else None})
    return abbr, out


def main():
    hurt = {}
    if os.path.exists(WIRE):
        try:
            hurt = json.load(open(WIRE))
        except ValueError:
            hurt = {}

    with ThreadPoolExecutor(8) as ex:
        rooms = {a: qbs for a, qbs in ex.map(ask, clubs()) if qbs}

    out, vetoed, both = {}, [], []
    for abbr in sorted(rooms):
        qbs, starter = [], None
        for q in rooms[abbr]:
            his = hurt.get(q["id"]) or {}
            mark = q["mark"] or his.get("abbr")
            sits = (mark or "").upper() in SITS
            # where the two sources both speak, say so rather than pick
            if q["mark"] and his.get("abbr") and q["mark"] != his["abbr"]:
                both.append("%s %s: chart %s, wire %s"
                            % (abbr, q["name"], q["mark"], his["abbr"]))
            qbs.append({"id": q["id"], "name": q["name"], "rank": q["rank"],
                        "mark": mark, "go": 0 if sits else 1,
                        "why": his.get("type"), "back": his.get("returns")})
            if starter is None and not sits:
                starter = q["id"]
        if qbs and starter and starter != qbs[0]["id"]:
            him = [q["name"] for q in qbs if q["id"] == starter][0]
            vetoed.append("%-4s %-20s %-4s -> %s" % (abbr, qbs[0]["name"],
                                                     qbs[0]["mark"], him))
        out[abbr] = {"qbs": qbs, "starter": starter}

    # a club this read found nothing for keeps what the file held -- an
    # absence is never written over the last good room (the file went empty
    # on the Sep 28 morning sweep and nobody's card was checked all day)
    try:
        old = json.load(open(OUT))
    except (OSError, ValueError):
        old = {}
    for abbr, room in old.items():
        if abbr not in out:
            out[abbr] = room
    json.dump(out, open(OUT, "w"), separators=(",", ":"), sort_keys=True)
    marked = [q for v in out.values() for q in v["qbs"] if q["mark"]]
    print("depth: %d clubs, %d quarterbacks, %d carrying a mark -> %s"
          % (len(out), sum(len(v["qbs"]) for v in out.values()), len(marked), OUT))
    print("the mark moved the starter on %d:" % len(vetoed))
    for v in vetoed:
        print("   ", v)
    if both:
        # never averaged, never reconciled: both are written and the run says so
        print("chart and wire both speak, and differ, on %d:" % len(both))
        for b in both:
            print("   ", b)


if __name__ == "__main__":
    main()
