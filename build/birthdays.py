"""Who plays on, or first after, his birthday.

   The birthday game is the first game a man plays on or after his birthday:
   the NFL week runs Wednesday to Tuesday, so every birthday falls in exactly
   one week and that week's game is his. The rule never looks back, so there
   are no ties; a bye moves it to the next game he plays. (Jose, Sep 16, 2026)

   The passers on the schedule get the mark on the page. Each club's top two
   receivers, tight end and lead back are kept in the same file for research
   only -- the men who would catch the passing touchdown -- and are not drawn.

   Dates of birth come from ESPN's athlete record, once each, and are kept in
   cache/dob.json so the sweep never asks twice. Written to site/birthdays.json:

     {"qb":   {event id: {athlete id: {"name", "age", "on"}}},
      "cast": {club: [{"id", "name", "pos", "rank", "dob", "age", "on", "game"}]}}

   Usage:  python3 birthdays.py [--dry]
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
DRY = "--dry" in sys.argv
CACHE = D + "/cache/dob.json"
SEASON = "2026"
CAST = {"wr": 2, "te": 1, "rb": 1}


def get(u):
    for _ in range(3):
        try:
            r = rq.get(u, impersonate="chrome124", timeout=40)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
    return {}


def teams():
    """ESPN's team ids by club letters, from the QB Spy roster file."""
    d = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "data.js")).read()
    at = d.index("TEAMS = ") + len("TEAMS = ")
    out = {}
    for t in json.JSONDecoder().raw_decode(d, at)[0]:
        out[t["abbr"]] = t["espnId"]
    out.setdefault("WSH", out.get("WAS"))
    out.setdefault("WAS", out.get("WSH"))
    return out


def et_day(iso):
    """the game's date in the East, where the week is counted"""
    return (dt.datetime.fromisoformat(iso.replace("Z", "+00:00")) - dt.timedelta(hours=4)).date()


def birthday_game(dob, games, weeks):
    """The first game he plays on or after his birthday. A bye pushes it to
       the next game he plays, and the rule never looks back, so there are no
       ties and no man is marked for a day that has not come.

       It used to take the game in the week his birthday fell in, which is not
       the same thing: the week runs past the Sunday, so six men were marked
       on a game played before their birthday. Tyler Shough was carded a
       birthday on the 27th and turned 27 on the 28th (Jose, Sep 22, 2026).
       None out of season."""
    if not dob or not games:
        return None
    b = dt.date.fromisoformat(dob[:10])
    mine = sorted((et_day(g[2]), g) for g in games)
    first, last = min(w[0] for w in weeks.values()), max(w[1] for w in weeks.values())
    for year in (first.year, last.year):
        try:
            this = b.replace(year=year)
        except ValueError:
            this = b.replace(year=year, day=28)
        if this < first or this > last:
            continue
        hit = next((g for d, g in mine if d >= this), None)
        if hit:
            return {"on": this.isoformat(), "age": year - b.year, "game": hit[1], "day": et_day(hit[2]) == this}
    return None


def main():
    s = pagefile.read()
    sched = json.loads(re.search(r"var SCHED = (\[\[.*?\]\]);", s, re.S).group(1))
    dob = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    # each week's window: its first game day through the Tuesday after its last
    weeks = {}
    for g in sched:
        d = et_day(g[2])
        a, z = weeks.get(g[0], (d, d))
        weeks[g[0]] = (min(a, d), max(z, d))
    weeks = {w: (a, z + dt.timedelta(days=1)) for w, (a, z) in weeks.items()}

    # the cast, club by club, off ESPN's depth chart
    ids = teams()
    cast = {}
    clubs = sorted({g[3] for g in sched} | {g[4] for g in sched})
    for club in clubs:
        tid = ids.get(club)
        if not tid:
            print("no ESPN team id for %s" % club)
            continue
        chart = get("https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/%s/teams/%s/depthcharts" % (SEASON, tid))
        rows = []
        for item in chart.get("items") or []:
            for pos, keep in CAST.items():
                slot = (item.get("positions") or {}).get(pos)
                for a in (slot or {}).get("athletes") or []:
                    rank = int(a.get("rank") or 9)
                    if rank > keep:
                        continue
                    m = re.search(r"athletes/(\d+)", (a.get("athlete") or {}).get("$ref") or "")
                    if m:
                        rows.append({"id": m.group(1), "pos": pos.upper(), "rank": rank})
        cast[club] = rows

    # every man we need a date for: the passers and the cast
    want = {}
    for g in sched:
        for name, pid in ((g[5], g[6]), (g[7], g[8])):
            if pid:
                want[str(pid)] = name
    for club, rows in cast.items():
        for r in rows:
            want.setdefault(r["id"], "")

    def fetch(pid):
        j = get("https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/athletes/%s" % pid)
        return pid, (j.get("dateOfBirth") or "")[:10], j.get("fullName") or j.get("displayName") or ""

    missing = [p for p in want if p not in dob]
    with ThreadPoolExecutor(8) as ex:
        for pid, d, full in ex.map(fetch, missing):
            dob[pid] = {"dob": d, "name": full}
    if not DRY:
        os.makedirs(D + "/cache", exist_ok=True)
        json.dump(dob, open(CACHE, "w"), separators=(",", ":"))

    # the passers: his games are the ones he is carded on
    qb = {}
    by_pid = {}
    for g in sched:
        for pid in (g[6], g[8]):
            if pid:
                by_pid.setdefault(str(pid), []).append(g)
    for pid, games in by_pid.items():
        hit = birthday_game(dob.get(pid, {}).get("dob"), games, weeks)
        if hit:
            qb.setdefault(hit["game"], {})[pid] = {"name": want.get(pid) or dob[pid]["name"], "age": hit["age"], "on": hit["on"], "day": hit["day"]}

    # the cast: his games are his club's
    out_cast = {}
    for club, rows in cast.items():
        games = [g for g in sched if club in (g[3], g[4])]
        for r in rows:
            d = dob.get(r["id"], {})
            hit = birthday_game(d.get("dob"), games, weeks)
            out_cast.setdefault(club, []).append({
                "id": r["id"], "name": d.get("name") or "", "pos": r["pos"], "rank": r["rank"],
                "dob": d.get("dob") or "", "age": hit and hit["age"], "on": hit and hit["on"], "game": hit and hit["game"]})

    n_qb = sum(len(v) for v in qb.values())
    n_cast = sum(1 for rows in out_cast.values() for r in rows if r["on"])
    print("birthdays: %d passers in season | cast %d men on %d clubs, %d in season | dates known %d of %d"
          % (n_qb, sum(len(v) for v in out_cast.values()), len(out_cast), n_cast,
             sum(1 for p in want if dob.get(p, {}).get("dob")), len(want)))
    for eid, men in sorted(qb.items(), key=lambda kv: min(m["on"] for m in kv[1].values())):
        for pid, m in men.items():
            print("   %s  %-18s turns %d  game %s" % (m["on"], m["name"], m["age"], eid))
    if DRY:
        return
    json.dump({"qb": qb, "cast": out_cast}, open(D + "/site/birthdays.json", "w"), separators=(",", ":"))
    print("written site/birthdays.json")


if __name__ == "__main__":
    main()
