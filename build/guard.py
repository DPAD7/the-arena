"""The sweep checks its own work before it deploys, and mends what it can.

   Every out QB Jose had to point at on Sep 28, 2026 had the same cause: a
   read came back empty on GitHub and nothing said so. So after the passers
   are settled, this asks the finished files the questions he would:

     1. does site/depth.json hold all 32 clubs?         if not, depth.py again
     2. does site/wire.json hold anyone at all?          if not, wire.py again
     3. is any passer named on the page Out, on IR,
        suspended or doubtful on the wire?               if so, starters.py again
     4. does every NFL game in the next day have a
        lineup in site/lineups.json?                     if not, lineups.py again

   Whatever is still wrong after the mend is written to site/guard.json and
   printed on a line of its own that starts GUARD, so the run log says it.
   An empty guard.json means the board passed.

       python3 build/guard.py
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(D, "site", "guard.json")
STOP = ("out", "injured reserve", "physically unable to perform", "suspended", "suspension", "pup", "ir", "doubtful")


def load(name):
    try:
        return json.load(open(os.path.join(D, "site", name)))
    except (OSError, ValueError):
        return {}


def run(job, *args):
    r = subprocess.run([sys.executable, os.path.join(D, "build", job)] + list(args),
                       capture_output=True, text=True, cwd=D)
    for line in (r.stdout + r.stderr).strip().splitlines()[-3:]:
        print("   %s: %s" % (job[:-3], line))


def games():
    s = pagefile.read()
    m = re.search(r"  var SCHED = (\[\[.*?\]\]);", s, re.S)
    now = dt.datetime.now(dt.timezone.utc)
    out = []
    for g in json.loads(m.group(1)) if m else []:
        try:
            t = dt.datetime.fromisoformat(g[2].replace("Z", "+00:00"))
        except ValueError:
            continue
        if now - dt.timedelta(hours=4) <= t <= now + dt.timedelta(days=8):
            out.append((g, t - now))
    return out


def benched(depth, wire):
    """The passers named on the page that the wire says will not play."""
    bad = []
    for g, _ in games():
        for i, ci in ((5, 3), (7, 4)):
            club, pid = g[ci], str(g[i + 1] or "")
            if club not in depth or not pid:
                continue
            st = ((wire.get(pid) or {}).get("status") or "").lower()
            if st in STOP:
                bad.append("%s %s is named for game %s and the wire has him %s" % (club, g[i], g[1], st))
    return bad


def short_lineups():
    lu = load("lineups.json")
    return ["game %s (%s at %s) has no lineup" % (g[1], g[3], g[4])
            for g, left in games() if left <= dt.timedelta(days=1) and g[3] in load("depth.json")
            and str(g[1]) not in lu]


def check():
    depth, wire = load("depth.json"), load("wire.json")
    wrong = []
    if len(depth) < 32:
        wrong.append("depth.json holds %d clubs, not 32" % len(depth))
    if not wire:
        wrong.append("wire.json is empty")
    wrong += benched(depth, wire)
    wrong += short_lineups()
    return wrong


def main():
    wrong = check()
    if wrong:
        for w in wrong:
            print("   mending: " + w)
        if any(w.startswith("depth.json") for w in wrong):
            run("depth.py")
        if any(w.startswith("wire.json") for w in wrong):
            run("wire.py")
        if any("the wire has him" in w for w in wrong) or any(w.startswith("depth.json") for w in wrong):
            run("starters.py")
        run("lineups.py")
        wrong = check()
    json.dump({"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "wrong": wrong},
              open(OUT, "w"), indent=1)
    for w in wrong:
        print("GUARD: " + w)
    print("guard: %s" % ("the board passed" if not wrong else "%d still wrong" % len(wrong)))


if __name__ == "__main__":
    main()
