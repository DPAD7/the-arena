"""A finished game is written down once and never asked about again.

   The page used to ask ESPN for every finished game on every load. A final
   score does not change, so each finished football game gets one small file
   at site/final/{espn id}.json holding exactly what the card reads -- the
   status and score, the two passers' lines, the scoring plays, the drives'
   plays, the win-probability series and the single-play clips. The page
   reads that first and asks ESPN only for a game with no file, i.e. one in
   progress.

   Usage:  python3 settle.py          (finished games without a file)
           python3 settle.py --force
"""
import datetime as dt
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile
OUT = os.path.join(D, "site", "final")
FORCE = "--force" in sys.argv
NOW = dt.datetime.now(dt.timezone.utc)


def T(x):
    return dt.datetime.fromisoformat(x.replace("Z", "+00:00"))


def get(u):
    for attempt in range(3):
        try:
            return rq.get(u, impersonate="chrome124", timeout=45).json()
        except Exception:
            pass
    return None


def board():
    s = pagefile.read()
    out = []
    for var, lg in (("SCHED", "nfl"), ("CFB", "college-football")):
        for g in json.loads(re.search(r"var %s = (\[\[.*?\]\]);" % var, s, re.S).group(1)):
            out.append((lg, g[1], g[2], str(g[6]), str(g[8])))
    return out


def slim(d, v, qbids):
    comp = (((d.get("header") or {}).get("competitions")) or [{}])[0]
    keep = {
        "header": {"competitions": [{
            "id": comp.get("id"), "date": comp.get("date"), "status": comp.get("status"),
            "competitors": [{"id": c.get("id"), "homeAway": c.get("homeAway"), "winner": c.get("winner"),
                             "score": c.get("score"),
                             # each quarter's points: an HT/FT leg settles off the half (Oct 8, 2026)
                             "linescores": [{"displayValue": q.get("displayValue")} for q in c.get("linescores") or []],
                             "team": {"id": (c.get("team") or {}).get("id"),
                                                               "abbreviation": (c.get("team") or {}).get("abbreviation")}}
                            for c in comp.get("competitors") or []]}]},
        "scoringPlays": [{"id": p.get("id"), "text": p.get("text"), "team": {"abbreviation": (p.get("team") or {}).get("abbreviation")}}
                         for p in d.get("scoringPlays") or []],
        "winprobability": [{"playId": p.get("playId"), "homeWinPercentage": p.get("homeWinPercentage")}
                           for p in d.get("winprobability") or []],
        "drives": {"previous": [{"plays": [{"id": p.get("id"), "period": {"number": (p.get("period") or {}).get("number")},
                                            "clock": {"displayValue": (p.get("clock") or {}).get("displayValue")},
                                            "start": {"downDistanceText": (p.get("start") or {}).get("downDistanceText")},
                                            "text": (p.get("text") or "")[:120]}
                                           for p in dr.get("plays") or []]}
                                for dr in ((d.get("drives") or {}).get("previous")) or []]},
        "boxscore": {"players": []},
        "videos": [],
    }
    for team in ((d.get("boxscore") or {}).get("players")) or []:
        stats = []
        for c in team.get("statistics") or []:
            if c.get("name") not in ("passing", "rushing", "receiving", "kicking", "defensive"):
                continue
            # every man who threw is kept, not just the two the card names: a
            # starter who was hurt still has a line (Sam Darnold at Seattle,
            # week one -- Jose, Sep 16, 2026). Rushing and receiving stay
            # trimmed to the named passers, which is what the cards read.
            ath = [{"athlete": {"id": (a.get("athlete") or {}).get("id"), "displayName": (a.get("athlete") or {}).get("displayName")},
                    "stats": a.get("stats")} for a in c.get("athletes") or []
                   if c.get("name") in ("passing", "kicking", "defensive") or str((a.get("athlete") or {}).get("id")) in qbids]
            stats.append({"name": c.get("name"), "labels": c.get("labels"), "athletes": ath})
        keep["boxscore"]["players"].append({"team": {"abbreviation": (team.get("team") or {}).get("abbreviation")}, "statistics": stats})
    for x in (v or d.get("videos") or []):
        if (x.get("tracking") or {}).get("coverageType") not in ("OnePlay", "Highlight"):
            continue
        src = ((x.get("links") or {}).get("source") or {}).get("href")
        if not src:
            continue
        keep["videos"].append({"id": x.get("id"), "headline": x.get("headline"), "originalPublishDate": x.get("originalPublishDate"),
                               "tracking": {"coverageType": (x.get("tracking") or {}).get("coverageType")},
                               "links": {"source": {"href": src}}})
    return keep


def one(g):
    lg, eid, kick, aq, hq = g
    path = os.path.join(OUT, eid + ".json")
    # a game is asked about the moment it has kicked off, not three hours
    # later. The old guard was there because nothing watched a game while it
    # was being played, so the first sensible moment to ask was long after the
    # whistle -- which is why a Thursday night game read final on the page and
    # not in our own record until the small hours (Jose, Sep 22, 2026: "why
    # the fuck are we asking again 3 1/2 and 5 1/2"). watch.py now asks every
    # thirty seconds while a game is live, so the answer arrives at the
    # whistle; a game that is not over yet answers "not final" and costs one
    # call. A game already written is never asked about again.
    if T(kick) > NOW or (os.path.exists(path) and not FORCE):
        return None
    d = get("https://site.api.espn.com/apis/site/v2/sports/football/%s/summary?event=%s" % (lg, eid))
    if not d:
        return (eid, "no answer")
    st = ((((d.get("header") or {}).get("competitions") or [{}])[0].get("status") or {}).get("type")) or {}
    if not (st.get("state") == "post" or st.get("completed")):
        return (eid, "not final")
    v = get("https://site.api.espn.com/apis/site/v2/sports/football/%s/videos?event=%s&limit=200" % (lg, eid)) or {}
    keep = slim(d, v.get("videos"), {aq, hq})
    json.dump(keep, open(path, "w"), separators=(",", ":"))
    return (eid, "%d KB" % (os.path.getsize(path) // 1024))


def main():
    os.makedirs(OUT, exist_ok=True)
    games = board()
    with ThreadPoolExecutor(10) as ex:
        res = [r for r in ex.map(one, games) if r]
    print("finished games written: %d | skipped: %s" % (sum(1 for _, s in res if s.endswith("KB")),
          [r for r in res if not r[1].endswith("KB")][:6]))
    print("files: %d, total %d KB" % (len(os.listdir(OUT)), sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT)) // 1024))


if __name__ == "__main__":
    main()
