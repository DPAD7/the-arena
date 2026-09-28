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
import datetime
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


def attempts(box, ab, pid):
    """How many passes one man threw for that club."""
    for team in box:
        if str(((team.get("team") or {}).get("abbreviation")) or "").upper() != str(ab).upper():
            continue
        for cat in team.get("statistics") or []:
            if cat.get("name") != "passing":
                continue
            labels = cat.get("labels") or []
            j = labels.index("C/ATT") if "C/ATT" in labels else -1
            for a in cat.get("athletes") or []:
                if str((a.get("athlete") or {}).get("id")) == str(pid) and j >= 0:
                    try:
                        return int(str(a["stats"][j]).split("/")[1])
                    except (IndexError, ValueError, KeyError):
                        return 0
    return 0


def busiest(box, ab):
    """The passer with the most attempts for that club, or None."""
    best, most = None, -1
    for team in box:
        if str(((team.get("team") or {}).get("abbreviation")) or "").upper() != str(ab).upper():
            continue
        for cat in team.get("statistics") or []:
            if cat.get("name") != "passing":
                continue
            labels = cat.get("labels") or []
            j = labels.index("C/ATT") if "C/ATT" in labels else -1
            for a in cat.get("athletes") or []:
                ath = a.get("athlete") or {}
                try:
                    att = int(str((a.get("stats") or [])[j]).split("/")[1]) if j >= 0 else 0
                except (IndexError, ValueError):
                    att = 0
                if ath.get("id") and att > most:
                    best, most = (ath.get("displayName") or "", str(ath.get("id"))), att
    return best

def first_up(d, had):
    """Which of these passers threw first, from the plays in order. The play
       text writes a man three ways -- "Dylan Lonergan", "D. Lonergan",
       "D.Lonergan" -- so all three are tried. None when no play names one."""
    forms = []
    for name, pid in had:
        b = [x for x in name.split() if not re.match(r"^(Jr\.?|Sr\.?|II|III|IV|V)$", x)]
        if len(b) < 2:
            continue
        last = re.escape(" ".join(b[1:]))
        pat = r"(?:%s|%s\.\s?%s)\s+(?:pass|sacked|scrambles)" % (re.escape(" ".join(b)), re.escape(b[0][0]), last)
        forms.append((re.compile(pat), (name, pid)))
    drives = ((d.get("drives") or {}).get("previous") or [])
    cur = (d.get("drives") or {}).get("current")
    if cur:
        drives = drives + [cur]
    for dr in drives:
        for pl in dr.get("plays") or []:
            t = pl.get("text") or ""
            for rx, him in forms:
                if rx.search(t):
                    return him
    return None


def priced(gid, side):
    """DraftKings priced this side's passing props: the man on the row is
       who the board priced, and a played card keeps him (Jose, Sep 22, 2026:
       "we had the odds for Murray, so leave it at that")."""
    f = os.path.join(D, "site", "prices", "%s.json" % gid)
    try:
        pr = json.load(open(f))
    except (OSError, ValueError):
        return False
    for market in ("ptd", "atd"):
        got = (pr.get("props") or {}).get(market) or []
        if len(got) > side and "\"" in json.dumps(got[side]):
            return True
    return False


def live_feed(var, gid):
    """A game under way, from ESPN, when there is no settled file yet."""
    lg = "nfl" if var == "SCHED" else "college-football"
    u = ("https://site.api.espn.com/apis/site/v2/sports/football/%s/summary?event=%s" % (lg, gid))
    try:
        from curl_cffi import requests as rq
        return rq.get(u, impersonate="chrome124", timeout=30).json()
    except Exception:
        return None


def main():
    s = pagefile.read()
    changed, looked = [], 0
    now = datetime.datetime.now(datetime.timezone.utc)

    for var in ("SCHED", "CFB"):
        m = re.search(r"  var %s = (\[\[.*?\]\]);\n" % var, s, re.S)
        if not m:
            continue
        rows = json.loads(m.group(1))
        touched = False
        for g in rows:
            f = os.path.join(D, "site", "final", "%s.json" % g[1])
            if os.path.exists(f):
                try:
                    d = json.load(open(f))
                except ValueError:
                    continue
            else:
                # a game on now: the box score already says who is throwing,
                # so the card does not wait for the whistle to be right
                try:
                    kick = datetime.datetime.fromisoformat(str(g[2]).replace("Z", "+00:00"))
                except ValueError:
                    continue
                if not (kick <= now <= kick + datetime.timedelta(hours=5)):
                    continue
                d = live_feed(var, g[1])
                if not d:
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
                # the row's own club first: a neutral site can list the row's
                # home side as ESPN's away, and Arkansas was given Utah's man
                club = g[3] if i == 5 else g[4]
                had = passers(box, club)
                if not had:
                    club = sides.get(home)
                    had = passers(box, club) if club else []
                if not had:
                    continue
                # the man who threw first started. A priced man who played
                # stays -- he is who the board priced -- but an unpriced one
                # who only came in late gives way to the starter: Rutgers kept
                # AJ Surace, 3 of 7, while Dylan Lonergan started (Sep 25, 2026)
                first = first_up(d, had)
                # no play names a thrower (a settled file keeps no drives): the
                # busiest passer, never a backup with one throw -- West Virginia
                # read Jyron Hughley, 1 attempt, for Michael Hawkins Jr.'s game
                # (Jose, Sep 27, 2026)
                top = busiest(box, club)
                if not first or (top and first[1] != top[1] and
                                 2 * attempts(box, club, first[1]) < attempts(box, club, top[1])):
                    # a first throw that was a trick play or a backup's one
                    # snap: Hughley threw once, first, while Hawkins threw 17
                    first = top
                there = any(str(g[i + 1]) == pid for _, pid in had)
                if there and (not first or str(g[i + 1]) == first[1]
                              or priced(g[1], 0 if i == 5 else 1)):
                    continue
                name, pid = first or had[0]
                if str(g[i + 1]) == pid:
                    continue
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
