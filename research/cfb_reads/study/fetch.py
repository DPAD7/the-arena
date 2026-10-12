"""Fetch everything the CFB 1+ PTD study needs, caching raw JSON to disk.

  python3 fetch.py            # all seasons 2016..2026
  python3 fetch.py 2026       # just one season (refresh the current one)

Writes:
  weeks/<yr>_<type>_<wk>.json   ESPN scoreboard per week (groups=80)
  cache/<event id>.json         ESPN game summary (completed games only)
  fbs/<yr>.json                 FBS team ids per season (conference children)
  odds/<event id>.json          ESPN core closing spread/total by provider
  bp/<yr>_<wk>.json             BettingPros NCAAF pass-TD props (market 441)
"""
import json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor
import requests

D = os.path.dirname(os.path.abspath(__file__))
for sub in ("weeks", "cache", "fbs", "bp", "odds"):
    os.makedirs(os.path.join(D, sub), exist_ok=True)
SB = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
SUM = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event={}"
CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/seasons/{}/types/2/groups/80/children?limit=50"
BPKEY = {"x-api-key": "CHi8Hy5CEE4khd46XNYL23dCFX96oUdw6qOt1Dnh"}
SES = requests.Session()


def get(url, headers=None, tries=5):
    for i in range(tries):
        try:
            r = SES.get(url, headers=headers, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
        except Exception:
            pass
        time.sleep(1.5 * (i + 1))
    return None


def weeks(yr, refresh=False):
    jobs = [(2, w) for w in range(1, 17)] + [(3, 1)]
    out = []
    for st, w in jobs:
        fn = os.path.join(D, "weeks", f"{yr}_{st}_{w}.json")
        if os.path.exists(fn) and not refresh:
            d = json.load(open(fn))
        else:
            u = f"{SB}?groups=80&seasontype={st}&dates={yr}&limit=300" + (f"&week={w}" if st == 2 else "")
            d = get(u) or {}
            json.dump(d, open(fn, "w"))
        for e in d.get("events", []):
            if e["competitions"][0]["status"]["type"].get("completed"):
                out.append(e["id"])
    return out


def summary(eid):
    fn = os.path.join(D, "cache", f"{eid}.json")
    if os.path.exists(fn):
        return
    d = get(SUM.format(eid))
    if d:
        json.dump(d, open(fn, "w"))


ODDS = "https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/events/{0}/competitions/{0}/odds?limit=50"


def odds(eid):
    """Closing spread/total per provider (summaries of finished games carry no pickcenter)."""
    fn = os.path.join(D, "odds", f"{eid}.json")
    if os.path.exists(fn):
        return
    d = get(ODDS.format(eid)) or {}
    keep = [dict(p=i.get("provider", {}).get("name"), pid=i.get("provider", {}).get("id"),
                 spread=i.get("spread"), ou=i.get("overUnder"), details=i.get("details"))
            for i in d.get("items", [])]
    json.dump(keep, open(fn, "w"))


def fbs(yr):
    fn = os.path.join(D, "fbs", f"{yr}.json")
    if os.path.exists(fn):
        return
    g = get(CORE.format(yr))
    teams = {}
    for c in g["items"]:
        cc = get(c["$ref"])
        t = get(cc["teams"]["$ref"].split("?")[0] + "?limit=60")
        for x in t["items"]:
            teams[re.search(r"teams/(\d+)", x["$ref"]).group(1)] = cc.get("abbreviation") or cc["name"]
    json.dump(teams, open(fn, "w"))


def bp(yr):
    """BettingPros NCAAF pass-TD props (market 441). Only 2026 has any."""
    for wk in range(1, 17):
        fn = os.path.join(D, "bp", f"{yr}_{wk}.json")
        if os.path.exists(fn) and yr < 2026:
            continue
        rows, page = [], 1
        while True:
            d = get(f"https://api.bettingpros.com/v3/props?sport=NCAAF&market_id=441&season={yr}&week={wk}&limit=50&page={page}", BPKEY)
            if not d:
                break
            rows += d.get("props", [])
            if page >= (d.get("_pagination", {}).get("total_pages") or 0):
                break
            page += 1
        json.dump(rows, open(fn, "w"))
        if rows:
            ev = get(f"https://api.bettingpros.com/v3/events?sport=NCAAF&season={yr}&week={wk}", BPKEY) or {}
            json.dump({e["id"]: e["scheduled"] for e in ev.get("events", [])},
                      open(os.path.join(D, "bp", f"ev_{yr}_{wk}.json"), "w"))


if __name__ == "__main__":
    yrs = [int(a) for a in sys.argv[1:]] or list(range(2016, 2027))
    for yr in yrs:
        fbs(yr)
        ids = weeks(yr, refresh=(yr == 2026))
        with ThreadPoolExecutor(6) as ex:
            list(ex.map(summary, ids))
            list(ex.map(odds, ids))
        print(yr, "games", len(ids), flush=True)
    for yr in yrs:
        if yr >= 2022:
            bp(yr)
    print("done", len(os.listdir(os.path.join(D, "cache"))))
