"""The day's last game is final: one full pass, once, to close the day out.

   Each game saves itself the moment a device sees it go final (settle.yml,
   started by /settled). When that leaves no game of the day -- Eastern -- still
   without its saved result, this runs refresh.py --day-end once: whatever no
   device reported is saved, and the board moves on to the next games, their
   prices, depth and injuries (Jose, Sep 29, 2026: "each game gets its final
   and reports where it needs to report, and then one last one as the games
   end"). data/served.json remembers the day, so it runs once.

       python3 build/day_end.py
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")


def main():
    s = pagefile.read()
    now = dt.datetime.now(dt.timezone.utc)
    today = now.astimezone(ET).date()
    games = []
    for var in ("SCHED", "CFB"):
        m = re.search(r"  var %s = (\[\[.*?\]\]);" % var, s, re.S)
        for g in json.loads(m.group(1)) if m else []:
            try:
                k = dt.datetime.fromisoformat(g[2].replace("Z", "+00:00"))
            except ValueError:
                continue
            # a game that kicked off yesterday evening and ended after
            # midnight belongs to yesterday's slate
            if k.astimezone(ET).date() in (today, today - dt.timedelta(days=1)) and k < now:
                games.append((str(g[1]), k.astimezone(ET).date()))
    for day in sorted(set(d for _, d in games), reverse=True):
        mine = [gid for gid, d in games if d == day]
        left = [gid for gid in mine if not os.path.exists(os.path.join(D, "site", "final", gid + ".json"))]
        key = "dayend@" + day.isoformat()
        f = os.path.join(D, "data", "served.json")
        try:
            seen = json.load(open(f))
        except (OSError, ValueError):
            seen = {}
        if left or key in seen:
            print("day end %s: %s" % (day, "%d still open" % len(left) if left else "already run"))
            continue
        if still_to_kick(s, day, now):
            print("day end %s: games still to kick off" % day)
            continue
        seen[key] = now.isoformat()
        json.dump(seen, open(f, "w"), indent=1)
        print("day end %s: all %d games final -- one full pass" % (day, len(mine)))
        r = subprocess.run([sys.executable, os.path.join(D, "build", "refresh.py"), "--day-end"], cwd=D)
        return r.returncode
    return 0


def still_to_kick(s, day, now):
    for var in ("SCHED", "CFB"):
        m = re.search(r"  var %s = (\[\[.*?\]\]);" % var, s, re.S)
        for g in json.loads(m.group(1)) if m else []:
            try:
                k = dt.datetime.fromisoformat(g[2].replace("Z", "+00:00"))
            except ValueError:
                continue
            if k.astimezone(ET).date() == day and k >= now:
                return True
    return False


if __name__ == "__main__":
    sys.exit(main())
