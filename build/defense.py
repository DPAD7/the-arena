"""What each defence has actually given up, counted off the play-by-play.

   A team page gives its own offence, not what its opponents did to it, so
   every completed game is walked instead and the other side's touchdowns are
   counted from the scoring plays. Small samples this early — the number of
   games is printed with every figure, because that is the figure that
   decides how much any of it is worth.
"""
import json
import subprocess

TEAMS = {"South Florida": 58, "Michigan": 130, "Temple": 218,
         "Oklahoma State": 197, "Penn State": 213}


def get(url):
    out = subprocess.run(["curl", "-s", url], capture_output=True, text=True, timeout=60)
    try:
        return json.loads(out.stdout)
    except Exception:
        return {}


def games(tid):
    j = get("https://site.api.espn.com/apis/site/v2/sports/football/college-football"
            "/teams/%d/schedule?season=2026" % tid)
    out = []
    for e in j.get("events", []):
        c = (e.get("competitions") or [{}])[0]
        if (c.get("status") or {}).get("type", {}).get("completed"):
            out.append((e["id"], e.get("name"), e.get("date", "")[:10]))
    return out


def allowed(tid, name):
    """Touchdowns the other side scored, by how they scored them."""
    rush = pas = other = 0
    played = []
    for gid, gname, when in games(tid):
        d = get("https://site.api.espn.com/apis/site/v2/sports/football/"
                "college-football/summary?event=%s" % gid)
        mine = None
        for t in ((d.get("header") or {}).get("competitions") or [{}])[0].get("competitors", []):
            if str((t.get("team") or {}).get("id")) == str(tid):
                mine = t.get("id")
        r = p = o = 0
        for pl in d.get("scoringPlays") or []:
            if str(((pl.get("team") or {}).get("id"))) == str(mine):
                continue                      # their own score, not one conceded
            ty = ((pl.get("type") or {}).get("abbreviation") or "").upper()
            txt = (pl.get("text") or "").lower()
            if ty != "TD":
                continue
            if " pass " in txt or "pass from" in txt:
                p += 1
            elif " run" in txt or "rush" in txt:
                r += 1
            else:
                o += 1
        rush += r; pas += p; other += o
        played.append((gname, when, r, p, o))
    print("== %s: %d game%s played" % (name, len(played), "" if len(played) == 1 else "s"))
    for gname, when, r, p, o in played:
        print("   %-46s %s   rush %d  pass %d  other %d" % (gname[:46], when, r, p, o))
    if played:
        n = len(played)
        print("   ALLOWED: rushing TD %d (%.1f a game) | passing TD %d (%.1f a game) | other %d"
              % (rush, rush / n, pas, pas / n, other / n if False else other))
    print()
    return rush, pas, len(played)


for name, tid in TEAMS.items():
    allowed(tid, name)
