"""The hub's league tables: every player and every club, back to 2013.

   Player Stats is the leaderboard — one row per man per season per stat
   sheet, with the columns that sheet carries (a passer's rating and
   completion rate, a receiver's targets, a kicker's range). Team Stats
   is the same for clubs, three tabs deep: offense, defense, special
   teams, each with its own sub-sheets.

   The position dropdown on the player page filters rows the response
   already holds, so it is not asked; the season, season type and sheet
   all change the server's answer, so they all are. The team endpoint
   answers only to a live event id harvested off the page — a made-up one
   gets an empty table with a 200 on it, which is the quietest kind of no.

   Run:  python3 build/hub_league_stats.py            2025 and 2026
         python3 build/hub_league_stats.py --deep     2013 through 2026
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
CREATE TABLE IF NOT EXISTS hub_player_stat (
    read_on TEXT NOT NULL,
    season  TEXT NOT NULL,
    season_type TEXT NOT NULL,  -- all | regular | finals
    sheet   TEXT NOT NULL,      -- passing | receiving | rushing | defense | kicking
    player  TEXT NOT NULL,
    club    TEXT,
    stat    TEXT NOT NULL,
    value   TEXT,
    PRIMARY KEY (season, season_type, sheet, player, stat, read_on)
);
CREATE TABLE IF NOT EXISTS hub_team_stat (
    read_on TEXT NOT NULL,
    season  TEXT NOT NULL,
    season_type TEXT NOT NULL,
    tab     TEXT NOT NULL,      -- offense | defense | specialteam
    sheet   TEXT NOT NULL,      -- total | passing | ... | returning | kicking | punting
    club    TEXT NOT NULL,
    stat    TEXT NOT NULL,
    value   TEXT,
    PRIMARY KEY (season, season_type, tab, sheet, club, stat, read_on)
);
"""

TYPES = ("regular", "finals", "all")
PLAYER_SHEETS = ("passing", "receiving", "rushing", "defense", "kicking")
TEAM_TABS = {"offense": ("total", "passing", "rushing", "receiving"),
             "defense": ("total", "passing", "rushing", "receiving"),
             "specialteam": ("returning", "kicking", "punting")}


def ask(url):
    done = subprocess.run(
        ["curl", "-s", "--max-time", "90",
         "-H", "X-Requested-With: XMLHttpRequest", "-H", "Loc: ", url],
        capture_output=True, text=True)
    return done.stdout or ""


def _text(said):
    return re.sub(r"\s+", " ", html.unescape(
        re.sub(r"<[^>]+>", " ",
               re.sub(r'data-bs-title="[^"]*"', "", said or "")))).strip()


def live_event_id():
    page = ask("%s/american-football/nfl/team-stats" % BASE)
    found = re.search(r'data-event-id="(\d{5,})"', page) or \
        re.search(r'id="event_id"[^>]*value="(\d{5,})"', page)
    return found.group(1) if found else ""


def table_in(page, keys, who_key, when):
    heads = [_text(one) for one in re.findall(r"<th[^>]*>(.*?)</th>", page,
                                              re.S)]
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 3:
            continue
        title = re.search(r'data-bs-title="([^"]+)"', row)
        name = re.search(r'class="tm-name(?: mob-none)?">(.*?)</span>', row,
                         re.S)
        who = _text((title or name).group(1)) if (title or name) \
            else _text(cells[1])
        # The cell decorates the man twice over — a tooltip arrow and the
        # name repeated for two screen widths — and he came out
        # "--> Aaron Rodgers Aaron Rodgers". Strip the arrow; and when the
        # string is the same name said twice, say it once.
        who = re.sub(r"^[-=>\s]+", "", who).strip()
        half = len(who) // 2
        if half > 2 and who[:half].strip() == who[half:].strip():
            who = who[:half].strip()
        club = re.search(r'data-section="team\|([^"]+)"', row)
        for at, cell in enumerate(cells):
            if at < 2 or at >= len(heads) or heads[at] in ("No.",):
                continue
            entry = dict(keys, read_on=when, stat=heads[at],
                         value=_text(cell))
            entry[who_key] = who
            if who_key == "player":
                entry["club"] = (html.unescape(club.group(1)).strip()
                                 if club else None)
            out.append(entry)
    return out


def main():
    db = open_db()
    patiently(lambda: db.executescript(SCHEMA))
    when = time.strftime("%Y-%m-%dT%H:%M:%S")
    seasons = [str(one) for one in range(2013, 2027)] \
        if "--deep" in sys.argv else ["2025", "2026"]
    event = live_event_id()

    jobs = [("player", season, kind, sheet, None)
            for season in seasons for kind in TYPES
            for sheet in PLAYER_SHEETS]
    jobs += [("team", season, kind, sheet, tab)
             for season in seasons for kind in TYPES
             for tab, sheets in TEAM_TABS.items() for sheet in sheets]

    def one(job):
        side, season, kind, sheet, tab = job
        if side == "player":
            url = ("%s/american_football/nfl/Player_stats/"
                   "american_football_player_stats_ajax?event_id=%s"
                   "&league_url=nfl&selected_season=%s&season_type=%s"
                   "&player_stats=%s&player_position=&theme=&stats="
                   % (BASE, event, season, kind, sheet))
        else:
            url = ("%s/american_football/nfl/Team_stats/"
                   "american_football_team_stats_ajax?event_id=%s"
                   "&league_url=nfl&selected_season=%s&season_type=%s"
                   "&team_stats=%s&selected_tab=%s&theme="
                   % (BASE, event, season, kind, sheet, tab))
        return job, ask(url)

    kept = {"player": 0, "team": 0}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for at, ((side, season, kind, sheet, tab), page) in enumerate(
                pool.map(one, jobs), 1):
            if side == "player":
                found = table_in(page, {"season": season,
                                        "season_type": kind,
                                        "sheet": sheet}, "player", when)
                table = "hub_player_stat"
            else:
                found = table_in(page, {"season": season,
                                        "season_type": kind,
                                        "tab": tab, "sheet": sheet},
                                 "club", when)
                table = "hub_team_stat"
            if found:
                patiently(lambda: put_many(db, table, found))
                patiently(db.commit)
                kept[side] += len(found)
            if at % 25 == 0 or at == len(jobs):
                print("   %3d/%d — player %d, team %d values"
                      % (at, len(jobs), kept["player"], kept["team"]))

    print("held: %d player values, %d team values"
          % (value(db, "SELECT COUNT(*) FROM hub_player_stat", default=0),
             value(db, "SELECT COUNT(*) FROM hub_team_stat", default=0)))


if __name__ == "__main__":
    main()
