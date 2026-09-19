"""How often a man has cleared a figure, and what it pays now.

   The hub's consistency sheet answers one question per row: over his last
   five games, or ten, or last season, how often did this man clear this
   line — and what is the price on it today. It grades the matchup, gives
   the average, the strike rate, the price, and then the games themselves
   one at a time.

   It is the closest thing any source we read has to what we compute
   ourselves out of `league_play`, which makes it the one board worth
   holding beside our own numbers rather than instead of them. Where the
   two disagree that disagreement is a thing to look at; it is not resolved
   here and nothing here overwrites anything of ours.

   Run:  python3 build/hub_consistency.py
         python3 build/hub_consistency.py jaxon-smith-njigba
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
import re
import subprocess
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from store import open_db, patiently, put_many, rows, value
from fetch_preview import BASE

SCHEMA = """
CREATE TABLE IF NOT EXISTS hub_form (
    read_on   TEXT NOT NULL,
    slug      TEXT NOT NULL,
    person_id TEXT,
    market    TEXT NOT NULL,   -- touchdowns | rushing | receiving | ...
    sample    TEXT NOT NULL,   -- last-5 | last-10 | season-2025
    line      TEXT NOT NULL,   -- the sheet's own heading: "Anytime Touchdown"
    matchup   TEXT,            -- the grade it gives the fixture
    average   TEXT,
    win_rate  TEXT,
    odds      TEXT,
    results   TEXT,            -- the games themselves, oldest last
    PRIMARY KEY (slug, market, sample, line, read_on)
);
CREATE INDEX IF NOT EXISTS hub_form_person ON hub_form (person_id, market);
"""

# The offensive markets. Defensive is on the same sheet and is not what any
# card here is about.
MARKETS = ["touchdowns", "rushing", "receiving", "rurecyds,over"]
SAMPLES = ["last-5", "season-2025"]


def get(slug, written, market, sample):
    url = ("%s/Consistency_sheet/player_consistency_sheet_ajax"
           "?sport_url=american-football&league_url=nfl&player_url=%s"
           "&market_name=%s&market_value=%s&matches_type=%s"
           "&home_road=&fav_und=&better_pitcher=&player_name=%s"
           "&player_full_name=&theme=&locations_info="
           "&current_season_url=2026&previous_season_url=2025"
           "&colspan=5&day_night="
           % (BASE, urllib.parse.quote(slug),
              urllib.parse.quote(market.split(",")[0]),
              urllib.parse.quote(market),
              urllib.parse.quote(sample),
              urllib.parse.quote(written or "")))
    done = subprocess.run(
        ["curl", "-s", "--max-time", "60",
         "-H", "X-Requested-With: XMLHttpRequest",
         "-H", "Referer: %s/american-football/nfl/"
               "consistency-sheet-player-details/%s" % (BASE, slug), url],
        capture_output=True, text=True)
    return done.stdout or ""


def _text(said):
    return html.unescape(re.sub(r"<[^>]+>", " ", said or "")).strip()


def sheets_in(page, slug, person_id, market, sample, when_read):
    """One row per line the sheet grades."""
    out = []
    for block in re.split(r'<div class="consistency-table', page)[1:]:
        heading = re.search(r'<span class="consist-heading">(.*?)</span>',
                            block, re.S)
        line = _text(heading.group(1)) if heading else None
        if not line:
            continue

        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", block, re.S):
            cells = re.findall(r'<td class="([^"]*)"[^>]*>(.*?)</td>',
                               row, re.S)
            if not cells:
                continue

            # Read by what each cell says it is, never by counting across.
            # Not every line has every column — "First Touchdown" carries no
            # average where "Anytime Touchdown" does — so a row read
            # positionally shifts one place left at that line and every
            # number after it belongs to the column before. The grade came
            # out as the average, the average as the strike rate, and the
            # price as a list of dates.
            said = {"matchup": None, "average": None, "win_rate": None,
                    "odds": None}
            games = []
            for mark, inside in cells:
                mark = " %s " % mark
                if "matchup-td" in mark:
                    said["matchup"] = _text(inside) or None
                elif "avg_high_low_stats" in mark:
                    said["average"] = _text(inside) or None
                elif "win-cell" in mark:
                    said["win_rate"] = _text(inside) or None
                elif "td-odds-cell" in mark:
                    found = re.search(r'data-american-odds="([^"]*)"', inside)
                    said["odds"] = (found.group(1).strip() if found
                                    else _text(inside) or None)
                elif "td-tooltip" in mark:
                    # The game is named in the cell's tooltip and the number
                    # it returned is the cell's own text. Both are wanted,
                    # each once: read whole, the cell repeats its tooltip
                    # back and every game reads "SB - February 8 2026 SB -
                    # February 8 2026".
                    when = re.search(r"class='op-date'>(.*?)</span>", inside)
                    got = _text(re.sub(r'data-bs-title="[^"]*"', "", inside))
                    games.append(" ".join(one for one in (
                        _text(when.group(1)) if when else "", got) if one))

            if not any(said.values()):
                continue
            out.append(dict(said, read_on=when_read, slug=slug,
                            person_id=person_id, market=market,
                            sample=sample, line=line,
                            results=" | ".join(one for one in games if one)
                            or None))

    return out


def sweep(db, men, markets=MARKETS, samples=SAMPLES):
    when = time.strftime("%Y-%m-%dT%H:%M:%S")
    kept = blank = 0
    jobs = [(man, market, sample) for man in men
            for market in markets for sample in samples]

    def one(job):
        man, market, sample = job
        return job, get(man["slug"], man.get("written"), market, sample)

    with ThreadPoolExecutor(max_workers=4) as pool:
        for at, ((man, market, sample), page) in enumerate(
                pool.map(one, jobs), 1):
            found = sheets_in(page, man["slug"], man.get("person_id"),
                              market, sample, when)
            if not found:
                blank += 1
            else:
                patiently(lambda: put_many(db, "hub_form", found))
                patiently(db.commit)
                kept += len(found)
            if at % 100 == 0 or at == len(jobs):
                print("   %5d/%d  %d rows held" % (at, len(jobs), kept))
    return kept, blank


def main():
    db = open_db()
    patiently(lambda: db.executescript(SCHEMA))

    if len(sys.argv) > 1:
        men = [{"slug": one, "person_id": None, "written": None}
               for one in sys.argv[1:]]
    else:
        men = [dict(one) for one in rows(
            db, "SELECT slug, person_id, written FROM hub_player ORDER BY slug")]

    print("%d men — %d sheets\n"
          % (len(men), len(men) * len(MARKETS) * len(SAMPLES)))
    kept, blank = sweep(db, men)
    print("\n%d rows this pass, %d sheets with nothing on them" % (kept, blank))
    print("held: %d rows, %d men, %d lines"
          % (value(db, "SELECT COUNT(*) FROM hub_form", default=0),
             value(db, "SELECT COUNT(DISTINCT slug) FROM hub_form", default=0),
             value(db, "SELECT COUNT(DISTINCT line) FROM hub_form", default=0)))


if __name__ == "__main__":
    main()
