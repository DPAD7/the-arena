"""Every club's season, cut every way the hub cuts it.

   The club half of `hub_splits.py`: one league-wide table per stat sheet
   (passing, rushing, receiving, defense, kicking), either side of the
   ball, filterable by home and road, favorite and dog, the spread band
   the club carried, the quarter, the red zone. Each filter is asked for
   alone; the crosses multiply into thousands of near-empty slices and
   answer nothing a single cut does not.

   The endpoint lives at the site root and wants exactly the parameters
   the page sends — one extra and it answers 500 with no words. The
   parameter list here is copied from a headless load of the page itself,
   not composed.

   Run:  python3 build/hub_team_splits.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

from store import open_db, patiently, put_many, value
from fetch_preview import BASE

SCHEMA = """
CREATE TABLE IF NOT EXISTS hub_team_split (
    read_on TEXT NOT NULL,
    side    TEXT NOT NULL,     -- offense | defense
    kind    TEXT NOT NULL,     -- passing | rushing | receiving | defense | kicking
    season_type TEXT NOT NULL, -- regular | playoffs | all
    cut     TEXT NOT NULL,     -- all | home | road | fav | dog | qtr1.. | spread bands | red-zone
    club    TEXT NOT NULL,
    stat    TEXT NOT NULL,
    value   TEXT,
    PRIMARY KEY (side, kind, season_type, cut, club, stat, read_on)
);
"""

SIDES = ("offense", "defense")
KINDS = ("passing", "rushing", "receiving", "defense", "kicking")
SEASONS = ("regular", "playoffs", "all")

# Each cut is one query-string fragment, sent alone.
CUTS = {"all": "",
        "home": "home_away=hm", "road": "home_away=aw",
        "fav": "fav_und_record=fav", "dog": "fav_und_record=und",
        "qtr1": "quarter_half=qtr1", "qtr2": "quarter_half=qtr2",
        "qtr3": "quarter_half=qtr3", "qtr4": "quarter_half=qtr4",
        "half-1": "quarter_half=half-1", "half-2": "quarter_half=half-2",
        "ot": "quarter_half=ot",
        "spread--3-0": "spread_dropdown=-3.0%2C0",
        "spread--7--3.5": "spread_dropdown=-7%2C-3.5",
        "spread--10--7.5": "spread_dropdown=-10%2C-7.5",
        "spread--10.5": "spread_dropdown=-10.5",
        "spread-0-3": "spread_dropdown=0%2C3.0",
        "spread-3.5-7": "spread_dropdown=3.5%2C7",
        "spread-7.5-10": "spread_dropdown=7.5%2C10",
        "red-zone": "red_zone=true"}


def get(side, kind, season_type, cut):
    base = ("sport_url=american-football&league_url=nfl&theme="
            "&season_url=2025&season_type=%s&statsfilter=%s&stats_type="
            "&current_season_data=true&home_away=&fav_und_record="
            "&vs_opp_team=&vs_div_league=&spread_dropdown=&quarter_half="
            "&month=&red_zone=&roster_type=%s" % (season_type, kind, side))
    extra = CUTS[cut]
    if extra:
        key = extra.split("=")[0]
        base = re.sub(r"%s=[^&]*" % key, extra, base)
    done = subprocess.run(
        ["curl", "-s", "--max-time", "90",
         "-H", "X-Requested-With: XMLHttpRequest", "-H", "Loc: ",
         "%s/get-team-splits-ajax?%s" % (BASE, base)],
        capture_output=True, text=True)
    return done.stdout or ""


def _text(said):
    return re.sub(r"\s+", " ", html.unescape(
        re.sub(r"<[^>]+>", " ",
               re.sub(r'data-bs-title="[^"]*"', "", said or "")))).strip()


def table_in(page, side, kind, season_type, cut, when):
    heads = [_text(one) for one in re.findall(r"<th[^>]*>(.*?)</th>", page,
                                              re.S)]
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 3:
            continue
        club = re.search(r'data-section="team\|([^"]+)"', row) or \
            re.search(r'teams/([a-z-]+)"', row)
        club = (html.unescape(club.group(1)).strip().replace("-", " ").title()
                if club else _text(cells[1]))
        for at, cell in enumerate(cells):
            if at < 2 or at >= len(heads):
                continue
            out.append({"read_on": when, "side": side, "kind": kind,
                        "season_type": season_type, "cut": cut,
                        "club": club, "stat": heads[at],
                        "value": _text(cell)})
    return out


def main():
    db = open_db()
    patiently(lambda: db.executescript(SCHEMA))
    when = time.strftime("%Y-%m-%dT%H:%M:%S")

    jobs = [(side, kind, "regular", cut)
            for side in SIDES for kind in KINDS for cut in CUTS]
    jobs += [(side, kind, season_type, "all")
             for side in SIDES for kind in KINDS
             for season_type in ("playoffs", "all")]

    def one(job):
        return job, get(*job)

    kept = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for at, ((side, kind, season_type, cut), page) in enumerate(
                pool.map(one, jobs), 1):
            found = table_in(page, side, kind, season_type, cut, when)
            if found:
                patiently(lambda: put_many(db, "hub_team_split", found))
                patiently(db.commit)
                kept += len(found)
            if at % 40 == 0 or at == len(jobs):
                print("   %3d/%d — %d values" % (at, len(jobs), kept))

    print("held: %d values, %d clubs, %d cuts"
          % (value(db, "SELECT COUNT(*) FROM hub_team_split", default=0),
             value(db, "SELECT COUNT(DISTINCT club) FROM hub_team_split",
                   default=0),
             value(db, "SELECT COUNT(DISTINCT cut) FROM hub_team_split",
                   default=0)))


if __name__ == "__main__":
    main()
