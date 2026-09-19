"""The hub's team consistency sheet: every club, every result market.

   The club half of what `hub_sheets.py` holds for men. One row per club
   per market — the result, the spread, the total, and the winning-margin
   bands — with the price, the strike rate over the window, and the club's
   next game beside it.

   Same endpoint family as the player sheet and the same trap done
   differently: the player sheet wanted `matches_type=last-5`, this one
   wants `5-matches`, and it also refuses without `sport_name=Football`
   and the sport's own event id, both copied from hidden inputs on its
   page rather than guessed.

   First-to-score markets are not fetched; the house does not track a
   first or last of anything.

   Run:  python3 build/hub_team_sheets.py
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
CREATE TABLE IF NOT EXISTS hub_team_sheet (
    read_on TEXT NOT NULL,
    market  TEXT NOT NULL,
    sample  TEXT NOT NULL,     -- 5-matches | 10-matches | 20-matches | 2025
    side    TEXT NOT NULL,
    cut     TEXT NOT NULL DEFAULT 'all',   -- all | home | road | fav | dog | day | night     -- over | under (the total; others ignore it)
    club    TEXT NOT NULL,     -- the club as written; settle via club_name
    next_up TEXT,
    line    TEXT,
    odds    TEXT,
    win_rate TEXT,
    PRIMARY KEY (market, sample, side, cut, club, read_on)
);
"""

CUT = re.compile(r"\bfirst\b|\b1st\b|\blast\b|longest", re.I)
SAMPLES = ("5-matches", "10-matches", "20-matches", "2025")


def page():
    done = subprocess.run(
        ["curl", "-s", "--max-time", "90",
         "%s/american-football/nfl/team-consistency-sheets" % BASE],
        capture_output=True, text=True)
    return done.stdout or ""


def markets_on(said):
    held = re.search(r'<select[^>]*id="select_market"[^>]*>(.*?)</select>',
                     said, re.S)
    out = []
    for mark, label in re.findall(
            r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>',
            held.group(1) if held else "", re.S):
        label = re.sub(r"\s+", " ", html.unescape(
            re.sub(r"<[^>]+>", "", label))).strip()
        if not mark or CUT.search(label) or (mark, label) in out:
            continue
        out.append((mark, label))
    return out


CUTS = {"all": ("", "", ""),
        "home": ("hm", "", ""), "road": ("aw", "", ""),
        "fav": ("", "fav", ""), "dog": ("", "und", ""),
        "day": ("", "", "day"), "night": ("", "", "night")}


def sheet(market, sample, side, cut="all"):
    url = ("%s/Team_consistency_sheet/consistency_sheet_ajax"
           "?sport_url=american-football&league_url=nfl&sport_name=Football"
           "&event_id=2001&upcoming_match=all-matches&market_name=%s"
           "&odds_type=american&sortingValue=&home_road=%s&fav_und=%s"
           "&matches_type=%s&theme=&locations_info=&match_info="
           "&page_load=true&current_season_url=2026&max_odds=&position="
           "&over_under=%s&away_team_id=&home_team_id=&day_night=%s"
           "&spread_value="
           % (BASE, market.replace(",", "%2C"),
              CUTS[cut][0], CUTS[cut][1], sample, side, CUTS[cut][2]))
    done = subprocess.run(
        ["curl", "-s", "--max-time", "120",
         "-H", "X-Requested-With: XMLHttpRequest", "-H", "Loc: null", url],
        capture_output=True, text=True)
    return done.stdout or ""


def _text(said):
    return re.sub(r"\s+", " ", html.unescape(
        re.sub(r"<[^>]+>", " ",
               re.sub(r'data-bs-title="[^"]*"', "", said or "")))).strip()


def rows_in(said, market, sample, side, when, cut="all"):
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", said, re.S):
        if "standing-cell" not in row:
            continue
        cells = re.findall(r'<td[^>]*class="([^"]*)"[^>]*>(.*?)(?=<td|$)',
                           row, re.S)
        club = kept_next = line = odds = win = None
        for mark, inside in cells:
            mark = " %s " % mark
            if " sticked-2 " in mark:
                club = _text(inside) or None
            elif "next-td" in mark:
                kept_next = _text(inside) or None
            elif "td-odds-cell" in mark:
                found = re.search(r'data-american-odds="([^"]*)"', inside)
                odds = found.group(1).strip() if found else _text(inside) or None
            elif "hide_lines" in mark:
                line = _text(inside) or None
            elif mark.strip() == "standing-cell":
                win = _text(inside) or None
        if not club:
            continue
        out.append({"read_on": when, "market": market, "sample": sample,
                    "side": side, "cut": cut, "club": club,
                    "next_up": kept_next,
                    "line": line, "odds": odds, "win_rate": win})
    return out


def main():
    db = open_db()
    patiently(lambda: db.executescript(SCHEMA))
    when = time.strftime("%Y-%m-%dT%H:%M:%S")

    offered = markets_on(page())
    print("%d markets after the cut" % len(offered))

    # Over and under only mean something on the total; everything else is
    # asked one way up so the same club is not stored twice for one fact.
    import sys as _sys
    cuts = (_sys.argv[1:] or ["all"])
    jobs = []
    for mark, label in offered:
        sides = ("over", "under") if mark == "overunder" else ("over",)
        for sample in SAMPLES:
            for side in sides:
                for cut in cuts:
                    jobs.append((mark, label, sample, side, cut))

    def one(job):
        mark, label, sample, side, cut = job
        return job, sheet(mark, sample, side, cut)

    kept = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for at, ((mark, label, sample, side, cut), got) in enumerate(
                pool.map(one, jobs), 1):
            found = rows_in(got, label, sample, side, when, cut)
            if found:
                patiently(lambda: put_many(db, "hub_team_sheet", found))
                patiently(db.commit)
                kept += len(found)
            if at % 20 == 0 or at == len(jobs):
                print("   %3d/%d — %d rows" % (at, len(jobs), kept))

    print("held: %d rows, %d clubs, %d markets"
          % (value(db, "SELECT COUNT(*) FROM hub_team_sheet", default=0),
             value(db, "SELECT COUNT(DISTINCT club) FROM hub_team_sheet",
                   default=0),
             value(db, "SELECT COUNT(DISTINCT market) FROM hub_team_sheet",
                   default=0)))


if __name__ == "__main__":
    main()
