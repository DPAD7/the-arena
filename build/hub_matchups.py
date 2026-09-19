"""What every club gives up and puts up, cut by position — and the odds
   hanging off each matchup.

   The hub's matchups board: one row per club, either side of the ball —
   what they have allowed or scored, as totals and per game, across the
   whole stat sheet (yards, points, touchdowns, then the passing, rushing
   and receiving breakdowns), filterable to what QBs, RBs, WRs or TEs
   specifically have done against them. "PHI allows 4.3 yards a carry to
   RBs" is a matchup fact, and this is the page that holds it.

   Only three of the six dropdowns are real: allowed/scored, the season
   type, and the position ask the server different questions. Stats type
   and format come back all at once — every cell names its own family and
   format in its class — and the dropdowns only show and hide columns.

   Under each club sits the player odds for its next game; those come
   from their own endpoint, once.

   Run:  python3 build/hub_matchups.py
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
CREATE TABLE IF NOT EXISTS hub_matchup (
    read_on  TEXT NOT NULL,
    section  TEXT NOT NULL,    -- allowed | scored
    season   TEXT NOT NULL,    -- all | regular | finals
    position TEXT NOT NULL,    -- all | qb | rb | wr | te
    club     TEXT NOT NULL,
    opponent TEXT,
    gp       TEXT,
    family   TEXT NOT NULL,    -- total | passing | rushing | receiving
    format   TEXT NOT NULL,    -- total | avg
    stat     TEXT NOT NULL,
    value    TEXT,
    PRIMARY KEY (section, season, position, club, family, format, stat,
                 read_on)
);
CREATE TABLE IF NOT EXISTS hub_matchup_odds (
    read_on    TEXT NOT NULL,
    player     TEXT NOT NULL,
    market     TEXT,
    odds       TEXT,
    event_id   TEXT,
    outcome_id TEXT,
    PRIMARY KEY (player, market, read_on)
);
"""

SECTIONS = ("allowed", "scored")
SEASONS = ("all", "regular", "finals")
POSITIONS = ("all", "qb", "rb", "wr", "te")


def get(path, section, season, position):
    url = ("%s/Matchups/%s?sport_url=american-football&league_url=nfl"
           "&season_type=%s&selected_positions=%s&selected_stats_type=total"
           "&selected_format=avg&current_season_url=2025&tabSection=%s"
           "&api_calling=1&theme=" % (BASE, path, season, position, section))
    done = subprocess.run(
        ["curl", "-s", "--max-time", "90",
         "-H", "X-Requested-With: XMLHttpRequest", "-H", "Loc: ", url],
        capture_output=True, text=True)
    return done.stdout or ""


def _text(said):
    return re.sub(r"\s+", " ", html.unescape(
        re.sub(r"<[^>]+>", " ",
               re.sub(r'data-bs-title="[^"]*"', "", said or "")))).strip()


def _mark(classes):
    family = re.search(r"(total|passing|rushing|receiving)_stats", classes)
    fmt = re.search(r"format_(total|avg)", classes)
    return (family.group(1) if family else None,
            fmt.group(1) if fmt else ("avg" if "avg_ta" in classes else None))


def table_in(page, section, season, position, when):
    """Headers and cells pair by position, and each names its own family
       and format — both are read, and a cell whose class disagrees with
       its header's is a table that changed shape and is left alone."""
    heads = re.findall(r'<th[^>]*class="([^"]*)"[^>]*>(.*?)</th>', page, re.S)
    heads = [(c, _text(x)) for c, x in heads]

    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = re.findall(r'<td[^>]*class="([^"]*)"[^>]*>(.*?)</td>',
                           row, re.S)
        if len(cells) < 6:
            continue
        club = opponent = gp = None
        for at, (classes, inside) in enumerate(cells):
            if at >= len(heads):
                break
            head_classes, label = heads[at]
            if "sticked-2" in classes:
                club = _text(inside)
                club = re.sub(r"^[A-Z]{2,3}\s+(?=[A-Z])", "", club)
            elif "next-td" in classes:
                opponent = _text(inside)
            elif label == "GP":
                gp = _text(inside)
            else:
                family, fmt = _mark(classes)
                if not family or not fmt or not club:
                    continue
                if _mark(head_classes) != (family, fmt):
                    continue
                out.append({"read_on": when, "section": section,
                            "season": season, "position": position,
                            "club": club, "opponent": opponent, "gp": gp,
                            "family": family, "format": fmt, "stat": label,
                            "value": _text(inside)})
    return out


def odds_in(page, when):
    out = []
    for said in re.findall(r'<div class="betslip-button add-to-betslip"'
                           r"([^>]*)>", page.replace("\\", "")):
        def attr(name):
            found = re.search(r'data-%s="?([^"\s>]+)' % name, said)
            return html.unescape(found.group(1)).strip() if found else None
        who = re.search(r'data-name="([^"]*)"', said)
        out.append({"read_on": when,
                    "player": html.unescape(who.group(1)).strip()
                    if who else (attr("name") or ""),
                    "market": attr("event-name"),
                    "odds": attr("american-odds"),
                    "event_id": attr("event-id"),
                    "outcome_id": attr("outcome-id")})
    return [one for one in out if one["player"] and one["odds"]]


def main():
    db = open_db()
    patiently(lambda: db.executescript(SCHEMA))
    when = time.strftime("%Y-%m-%dT%H:%M:%S")

    jobs = [(section, season, position) for section in SECTIONS
            for season in SEASONS for position in POSITIONS]

    def one(job):
        section, season, position = job
        return job, get("matchups_stats_ajax", section, season, position)

    kept = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for (section, season, position), page in pool.map(one, jobs):
            found = table_in(page, section, season, position, when)
            if found:
                patiently(lambda: put_many(db, "hub_matchup", found))
                patiently(db.commit)
                kept += len(found)
            print("   %-7s %-8s %-4s %5d values"
                  % (section, season, position, len(found)))

    odds = odds_in(get("matchups_player_stats_ajax", "allowed", "regular",
                       "all"), when)
    if odds:
        patiently(lambda: put_many(db, "hub_matchup_odds", odds))
        patiently(db.commit)
    print("   player odds: %d" % len(odds))

    print("\nheld: %d matchup values, %d odds"
          % (value(db, "SELECT COUNT(*) FROM hub_matchup", default=0),
             value(db, "SELECT COUNT(*) FROM hub_matchup_odds", default=0)))


if __name__ == "__main__":
    main()
