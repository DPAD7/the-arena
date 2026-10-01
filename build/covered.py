"""What the board actually holds, per league, after a sweep.

   Every step of the chain is wired and league-gated, and each one says what
   it did -- but only into its own line of the log, and only about itself. So
   a gap took three days and a screenshot to find: college week four drew
   midnight for thirty-three games, every college card carried the Dolphins'
   record, and the touchdown prices were the wrong man's. Each script had
   reported success.

   This asks one question at the end, twice, once per league: of the fixtures
   we are drawing, how many have a kickoff, a starter, a moneyline, and a
   price on the men -- and names what is missing rather than counting it.

       NFL  wk3  16/16 kicked  16/16 starters  16/16 priced   32 pinned
       CFB  wk4  71/71 kicked  71/71 starters  56/71 priced   76 pinned
          CFB not priced: HOW/RUTG, BUCK/PITT, LIN/EMU ...

   Nothing is fetched. It reads what the sweep has already written, so it
   costs nothing and cannot itself go stale.

       python3 build/covered.py
"""
import datetime as dt
import json
import os
import re
import sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile
NOW = dt.datetime.now(dt.timezone.utc)
# the week being played into: what is still ahead, plus what finished today
AHEAD = dt.timedelta(hours=12)


def arrays():
    s = pagefile.read()
    out = {}
    for var in ("SCHED", "CFB"):
        m = re.search(r"var %s = (\[\[.*?\]\]);" % var, s, re.S)
        out[var] = json.loads(m.group(1)) if m else []
    return out


def priced(eid):
    f = os.path.join(D, "site", "prices", "%s.json" % eid)
    if not os.path.exists(f):
        return False, False
    try:
        d = json.load(open(f))
    except ValueError:
        return False, False
    ml = any(d.get("ml") or [])
    pr = d.get("props") or {}
    men = any(x for k in ("ptd", "atd") for side in (pr.get(k) or [])
              for x in (side or []) if x)
    return ml, men


def main():
    a = arrays()
    pins = {}
    f = os.path.join(D, "data", "dk_people.json")
    if os.path.exists(f):
        try:
            pins = json.load(open(f))
        except ValueError:
            pins = {}

    for var, label in (("SCHED", "NFL"), ("CFB", "CFB")):
        rows = a[var]
        # the week in front of us: the earliest week with a game still to come
        ahead = [g for g in rows
                 if dt.datetime.fromisoformat(g[2].replace("Z", "+00:00")) > NOW - AHEAD]
        if not ahead:
            print("%-4s nothing ahead" % label)
            continue
        wk = min(g[0] for g in ahead)
        week = [g for g in rows if g[0] == wk]

        kicked = [g for g in week if g[2][11:] != "04:00Z"]
        started = [g for g in week if g[5] and g[7]]
        got_ml, got_men, no_ml = [], [], []
        for g in week:
            ml, men = priced(str(g[1]))
            (got_ml if ml else no_ml).append(g)
            if men:
                got_men.append(g)

        mine = sum(1 for v in pins.values()
                   if var == "SCHED") if False else len(pins)
        print("%-4s wk%-3s %3d/%-3d kicked  %3d/%-3d starters  %3d/%-3d priced  %3d/%-3d on the men"
              % (label, wk, len(kicked), len(week), len(started), len(week),
                 len(got_ml), len(week), len(got_men), len(week)))

        if len(kicked) < len(week):
            late = [g for g in week if g[2][11:] == "04:00Z"]
            print("     %s no kickoff yet: %s%s" % (label,
                  ", ".join("%s/%s" % (g[3], g[4]) for g in late[:6]),
                  " ..." if len(late) > 6 else ""))
        if no_ml:
            print("     %s not priced: %s%s" % (label,
                  ", ".join("%s/%s" % (g[3], g[4]) for g in no_ml[:6]),
                  " ..." if len(no_ml) > 6 else ""))
        # complete: the moneyline, 1+ and 2+ passing scores, the anytime score
        # and the head to head, both sides -- fill_week's own test, so the
        # count and the asking agree (Jose, Oct 1, 2026: "only fetch what's
        # missing to get 100% completion")
        import fill_week
        whole = [g for g in week if fill_week.full(str(g[1]))]
        print("     %s complete (ML, PTD 1+ 2+, ATD, H2H): %d/%d" % (label, len(whole), len(week)))
        short = [g for g in week if g not in whole and g in got_ml]
        if short:
            print("     %s still short: %s%s" % (label,
                  ", ".join("%s/%s" % (g[3], g[4]) for g in short[:8]),
                  " ..." if len(short) > 8 else ""))
        bare = [g for g in week if g not in got_men]
        if bare:
            print("     %s no price on the men: %s%s" % (label,
                  ", ".join("%s/%s" % (g[3], g[4]) for g in bare[:6]),
                  " ..." if len(bare) > 6 else ""))

    print("DraftKings ids pinned: %d" % len(pins))
    return 0


if __name__ == "__main__":
    sys.exit(main())
