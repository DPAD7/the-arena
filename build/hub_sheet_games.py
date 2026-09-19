"""The games behind every sheet row — what "Click to expand" shows.

   A sheet row says a man is 40% over his line across five games. The
   expand says which five: the opponent, whether it was home or away, the
   week, the date, the matchup grade the hub gave that opponent, and the
   number he actually put up. For clubs it is the same with the spread he
   carried and whether it won.

   One call per man per market *family*, not per line — the five games
   under "300+ Passing Yards" are the same five games under "250+", with
   the same yardage in the stat column; only the coloring against the
   line differs, and the coloring is arithmetic we can do.

   Run:  python3 build/hub_sheet_games.py            players and teams
         python3 build/hub_sheet_games.py teams      just the clubs
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
CREATE TABLE IF NOT EXISTS hub_sheet_game (
    read_on  TEXT NOT NULL,
    kind     TEXT NOT NULL,    -- player | team
    family   TEXT NOT NULL,    -- atts, payds, ruyds ... winloss, line
    who      TEXT NOT NULL,
    slug     TEXT,
    opponent TEXT,
    venue    TEXT,             -- vs | @
    grade    TEXT,             -- the matchup grade; clubs carry none
    week     TEXT,
    game_on  TEXT,
    spread   TEXT,             -- clubs only
    stat     TEXT,
    PRIMARY KEY (kind, family, who, week, game_on, read_on)
);
"""

# One market per family answers for the whole family. First and last of
# anything stay cut.
# The "Line" markets carry their side in the value — "ruyds,over", not
# "ruyds" — and the bare word answers an empty sheet without complaint.
FAMILIES = ["atts", "td,2,x", "payds,over", "paruyds,over", "patd,over",
            "pacomp,over", "att,over", "paint,over", "ruyds,over",
            "ruatt,over", "recyds,over", "rec,over", "target,over",
            "rurecyds,over", "sacks,over"]
TEAM_FAMILIES = ["winloss", "line", "overunder"]


def _text(said):
    return re.sub(r"\s+", " ", html.unescape(
        re.sub(r"<[^>]+>", " ",
               re.sub(r'data-bs-title="[^"]*"', "", said or "")))).strip()


def sheet_page(family):
    """One family's league sheet, to harvest each man's expand id."""
    url = ("%s/Consistency_sheet/consistency_sheet_ajax"
           "?sport_url=american-football&league_url=nfl"
           "&upcoming_match=all-matches&market_name=%s&odds_type=american"
           "&sortingValue=&home_road=&fav_und=&matches_type=season-2025"
           "&theme=&locations_info=&match_info=&page_load=true"
           "&current_season_url=2026&max_odds=&sort_by=&sort_type="
           "&limit=50&offset=&position=&over_under=over&day_night="
           % (BASE, family.replace(",", "%2C")))
    done = subprocess.run(
        ["curl", "-s", "--max-time", "120",
         "-H", "X-Requested-With: XMLHttpRequest", "-H", "Loc: null", url],
        capture_output=True, text=True)
    return done.stdout or ""


def men_on(page):
    """(player_id, slug) for every expandable row on a sheet."""
    return sorted(set(re.findall(
        r'data-player-id="(\d+)" data-playerurl-info="([a-z0-9.\-]+)"',
        page)))


def expand(family, player_id, slug):
    url = ("%s/Consistency_sheet/consistency_sheet_expand_ajax"
           "?sport_url=american-football&league_url=nfl"
           "&upcoming_match=all-matches&market_name=%s&odds_type=american"
           "&sortingValue=&home_road=&fav_und=&matches_type=season-2025"
           "&theme=&locations_info=&match_info=&page_load=true"
           "&current_season_url=2026&max_odds=&sort_by=&sort_type="
           "&limit=50&offset=&position=&over_under=over&day_night="
           "&player_id=%s&player_url=%s"
           % (BASE, family.replace(",", "%2C"), player_id, slug))
    done = subprocess.run(
        ["curl", "-s", "--max-time", "60",
         "-H", "X-Requested-With: XMLHttpRequest", "-H", "Loc: null", url],
        capture_output=True, text=True)
    return done.stdout or ""


def team_expand(family, team_url):
    url = ("%s/Team_consistency_sheet/team_consistency_sheet_expand_ajax"
           "?sport_url=american-football&league_url=nfl&sport_name=Football"
           "&upcoming_match=all-matches&market_name=%s&odds_type=american"
           "&home_road=&fav_und=&matches_type=2025&theme=&locations_info="
           "&match_info=&page_load=true&current_season_url=2026&max_odds="
           "&limit=50&offset=&position=&over_under=over&team_id="
           "&team_url=%s&day_night=&spread_value="
           % (BASE, family, team_url))
    done = subprocess.run(
        ["curl", "-s", "--max-time", "60",
         "-H", "X-Requested-With: XMLHttpRequest", "-H", "Loc: null", url],
        capture_output=True, text=True)
    return done.stdout or ""


def games_in(page, kind, family, who, slug, when):
    """The expand's rows: one game each, read by the cell's own class."""
    out = []
    for row in re.split(r"<tr[^>]*>", page)[1:]:
        cells = re.findall(r'<td[^>]*class="([^"]*)"[^>]*>(.*?)</td>',
                           row, re.S)
        if not cells:
            continue
        game = {"opponent": None, "venue": None, "grade": None,
                "week": None, "game_on": None, "spread": None, "stat": None}
        for mark, inside in cells:
            mark = " %s " % mark
            if "sheet-opp-td" in mark:
                # The venue label sits twice in the cell; stripped once by
                # class and once by word, or "vs" rode in on every name.
                game["opponent"] = re.sub(r"^(?:vs|@)\s+", "", _text(re.sub(
                    r'<span class="ht-at-label">.*?</span>', "", inside,
                    flags=re.S))) or None
                at = re.search(r'ht-at-label">(.*?)<', inside, re.S)
                game["venue"] = _text(at.group(1)) if at else None
            elif "matchup-td" in mark:
                game["grade"] = _text(inside) or None
            elif "sheet-date-td" in mark:
                got = _text(inside)
                if re.fullmatch(r"W\d+|WC|DR|CC|SB|PS\d*", got or ""):
                    game["week"] = got
                elif re.search(r"\d{4}", got or ""):
                    game["game_on"] = got
                elif got:
                    game["spread"] = got
            elif "sheet-stat-td" in mark or "sheet-spread-td" in mark:
                got = _text(inside)
                if "spread" in mark:
                    game["spread"] = got or None
                else:
                    game["stat"] = got or None
        if not game["opponent"]:
            continue
        out.append(dict(game, read_on=when, kind=kind, family=family,
                        who=who, slug=slug))
    return out


def main():
    db = open_db()
    patiently(lambda: db.executescript(SCHEMA))
    when = time.strftime("%Y-%m-%dT%H:%M:%S")
    only_teams = "teams" in sys.argv[1:]
    kept = 0

    if not only_teams:
        for family in FAMILIES:
            men = men_on(sheet_page(family))

            def one(pair):
                pid, slug = pair
                return slug, expand(family, pid, slug)

            got_here = 0
            with ThreadPoolExecutor(max_workers=4) as pool:
                for slug, page in pool.map(one, men):
                    found = games_in(page, "player", family.split(",")[0],
                                     slug, slug, when)
                    if found:
                        patiently(lambda: put_many(db, "hub_sheet_game",
                                                   found))
                        patiently(db.commit)
                        got_here += len(found)
            kept += got_here
            print("   %-10s %4d men  %6d games" % (family.split(",")[0],
                                                   len(men), got_here))

    clubs = [row["written"].lower().replace(" ", "-") for row in
             db.execute("""SELECT DISTINCT written FROM club_name
                            WHERE length(written) > 8
                              AND written LIKE '% %'
                              AND source LIKE '%score%'""")]
    for family in TEAM_FAMILIES:
        got_here = 0
        with ThreadPoolExecutor(max_workers=4) as pool:
            for club, page in pool.map(
                    lambda one: (one, team_expand(family, one)), clubs):
                found = games_in(page, "team", family, club, club, when)
                if found:
                    patiently(lambda: put_many(db, "hub_sheet_game", found))
                    patiently(db.commit)
                    got_here += len(found)
        kept += got_here
        print("   team %-8s %6d games" % (family, got_here))

    print("\nheld: %d game rows"
          % value(db, "SELECT COUNT(*) FROM hub_sheet_game", default=0))


if __name__ == "__main__":
    main()
