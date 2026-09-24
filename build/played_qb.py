"""Who actually took the snaps, on a game that has been played.

   A row's two quarterbacks are written when the schedule is drawn, months
   before kickoff, from whoever is the starter then. That is a guess about the
   future and it is often wrong: Atlanta's week two row still said Michael
   Penix Jr. two days after Cooper Rush played the game, so the card named a
   man who was not there and his stat line came back empty -- nought yards,
   nought touchdowns -- because there is nothing of his in that box score
   (Jose, Sep 22, 2026: "he didn't even play, how does he have stats").

   A played game does not need a guess. The box score says who threw the ball.
   This reads it and writes that man into the row, so a finished card names
   the man who was on the field and his numbers are his own.

   The rule: the row is left alone unless the man on it never appeared. He is
   who the board priced, and that is what a played card should name. Jaxson
   Dart started for the Giants, was hurt, and Jameis Winston threw twenty-seven
   times to his five -- the row stays Dart, because Dart is who the odds were
   on (Jose, Sep 22, 2026: "whoever starts the game is the starter ... we had
   the odds for Murray, so leave it at that").

   The box score cannot tell us who started: ESPN lists that game's passers
   Winston first and Dart second, so neither the first listed nor the busiest
   is the starter. It can only tell us who was there. So the one thing this
   corrects is a man who was not.

   Only games we hold a settled file for are touched, which is the same as
   saying only games that are over. Nothing upcoming is changed: that is
   starters.py's job and it works off the depth chart.

       python3 build/played_qb.py          fix every played game
       python3 build/played_qb.py --dry    say what it would change
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY = "--dry" in sys.argv


def passers(box, ab):
    """Every passer that club had, in ESPN's order: [(name, espn id), ...].

       Matched on the club's abbreviation, because settle.py keeps the box
       score slim and the team id is not in it -- only ATL and CAR are."""
    out = []
    for team in box:
        if str(((team.get("team") or {}).get("abbreviation")) or "").upper() != str(ab).upper():
            continue
        for cat in team.get("statistics") or []:
            if cat.get("name") != "passing":
                continue
            for a in cat.get("athletes") or []:
                ath = a.get("athlete") or {}
                if ath.get("id"):
                    out.append((ath.get("displayName") or "", str(ath.get("id"))))
    return out

def main():
    s = pagefile.read()
    changed, looked = [], 0

    for var in ("SCHED", "CFB"):
        m = re.search(r"  var %s = (\[\[.*?\]\]);\n" % var, s, re.S)
        if not m:
            continue
        rows = json.loads(m.group(1))
        touched = False
        for g in rows:
            f = os.path.join(D, "site", "final", "%s.json" % g[1])
            if not os.path.exists(f):
                continue
            try:
                d = json.load(open(f))
            except ValueError:
                continue
            comp = (((d.get("header") or {}).get("competitions") or [{}])[0])
            box = (d.get("boxscore") or {}).get("players") or []
            if not box:
                continue
            looked += 1
            # which club is on which side, by ESPN's own ids
            sides = {}
            for c in comp.get("competitors") or []:
                sides[c.get("homeAway")] = str((c.get("team") or {}).get("abbreviation") or "")
            for i, home in ((5, "away"), (7, "home")):
                club = sides.get(home)
                if not club:
                    continue
                had = passers(box, club)
                if not had:
                    continue
                # he was there: leave him, whatever his share of the throwing
                if any(str(g[i + 1]) == pid for _, pid in had):
                    continue
                name, pid = had[0]
                changed.append((var, g[0], g[3], g[4], g[i], name))
                g[i], g[i + 1] = name, pid
                touched = True
        if touched:
            s = (s[:m.start()] +
                 "  var %s = %s;\n" % (var, json.dumps(rows, separators=(",", ":"))) +
                 s[m.end():])

    print("played games read: %d | rows corrected: %d" % (looked, len(changed)))
    for var, wk, a, b, was, now in changed[:20]:
        print("   %-5s wk%-3s %-5s v %-5s  %s -> %s" % (var, wk, a, b, was, now))
    if DRY:
        print("(dry run, nothing written)")
        return 0
    if not changed:
        return 0
    if not pagefile.write(s):
        print("the page changed under us, nothing written")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
