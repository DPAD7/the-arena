"""When each drawn game actually kicks off.

   A week is drawn once and its kickoffs are never read again. That is fine
   for the NFL, which knows its times a season ahead, and wrong for college,
   where the networks pick them six to twelve days out. Until then ESPN files
   a game at 04:00Z -- midnight Eastern -- and the board printed that as a
   real slot: thirty-three of week four's games under "SAT 12:00 AM", forty-one
   of week five's (Jose, Sep 22, 2026: "who in the fuck is playing at 12 am").

   The times exist by now. Oklahoma at Georgia had been given 3:30 and Oregon
   at USC 7:30 while the board still read midnight for both. Nothing was
   asking.

   So this asks, for every drawn game still to come, and rewrites the kickoff
   on the page where it has moved. It only ever moves a game that has not
   started: a kickoff in the past is the record of when it happened and is
   left alone.

       python3 build/kicks.py           every drawn week still ahead
       python3 build/kicks.py --dry     say what would move, write nothing
"""
import datetime as dt
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY = "--dry" in sys.argv
NOW = dt.datetime.now(dt.timezone.utc)
# the same reach the rest of the sweep prices
HORIZON_DAYS = 21
SUM = ("https://site.api.espn.com/apis/site/v2/sports/football/%s"
       "/summary?event=%s")


def ask(job):
    lg, gid = job
    try:
        r = rq.get(SUM % (lg, gid), impersonate="chrome", timeout=25)
        if r.status_code != 200:
            return gid, None
        comp = (((r.json() or {}).get("header") or {}).get("competitions") or [{}])[0]
        when = comp.get("date")
    except Exception:
        return gid, None
    if not when:
        return gid, None
    # ESPN writes 2026-09-26T19:30Z; the page holds the same shape
    try:
        t = dt.datetime.fromisoformat(when.replace("Z", "+00:00"))
    except ValueError:
        return gid, None
    return gid, t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def main():
    s = pagefile.read()
    moved, asked = [], []

    for var, lg in (("SCHED", "nfl"), ("CFB", "college-football")):
        m = re.search(r"  var %s = (\[\[.*?\]\]);\n" % var, s, re.S)
        if not m:
            continue
        rows = json.loads(m.group(1))
        want = []
        for g in rows:
            try:
                kick = dt.datetime.fromisoformat(g[2].replace("Z", "+00:00"))
            except ValueError:
                continue
            # a game that has started is the record of when it started
            if kick <= NOW or kick > NOW + dt.timedelta(days=HORIZON_DAYS):
                continue
            want.append((lg, str(g[1])))
        asked.append((var, len(want)))
        if not want:
            continue
        with ThreadPoolExecutor(8) as ex:
            fresh = {gid: iso for gid, iso in ex.map(ask, want) if iso}
        for g in rows:
            iso = fresh.get(str(g[1]))
            if iso and iso != g[2]:
                moved.append((var, g[3], g[4], g[2], iso))
                g[2] = iso
        s = (s[:m.start()] +
             "  var %s = %s;\n" % (var, json.dumps(rows, separators=(",", ":"))) +
             s[m.end():])

    print("asked about: " + ", ".join("%s %d" % x for x in asked))
    print("kickoffs that moved: %d" % len(moved))
    for var, a, b, was, now in moved[:14]:
        print("   %-5s %-5s v %-5s  %s -> %s" % (var, a, b, was, now))
    if DRY:
        print("(dry run, nothing written)")
        return 0
    if not moved:
        return 0
    if not pagefile.write(s):
        print("page changed under us, nothing written")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
