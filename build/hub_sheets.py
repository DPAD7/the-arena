"""The hub's league-wide consistency sheet, one row per man per game.

   One row per man per market: his line, its price, his matchup graded
   A+ through F, his strike rate and his average — the whole league on
   one sheet per market, which is the one thing the per-player pages
   cannot say.

   The endpoint took an afternoon to open for one reason worth writing
   down: it answers 400 to `max_odds=any` and answers everything to
   `max_odds=` — the word the page's own dropdown shows is not the value
   its script sends. The first-touchdown, last-touchdown and longest
   markets are deliberately not fetched; the house does not track them.

   The page also names two things harvested on the way past: the hub's
   address for men the prop pages never linked ("bryce-christopher-young"
   is not derivable from Bryce Young), and its second id for a game — the
   match id, 30433, which lives beside the event id and is what the
   consistency and touchdown machinery key on.

   Run:  python3 build/hub_sheets.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
import re
import subprocess
import time

from store import open_db, patiently, put_many, value
from fetch_preview import BASE

SCHEMA = """
CREATE TABLE IF NOT EXISTS hub_sheet (
    read_on TEXT NOT NULL,
    market  TEXT NOT NULL,
    sample  TEXT NOT NULL,    -- last-5 | last-10 | season-2025
    side    TEXT NOT NULL,
    cut     TEXT NOT NULL DEFAULT 'all',   -- all | home | road | fav | dog | day | night    -- over | under
    player  TEXT NOT NULL,
    slug    TEXT,
    matchup TEXT,             -- the grade
    line    TEXT,
    odds    TEXT,
    win_rate TEXT,
    average TEXT,
    results TEXT,
    PRIMARY KEY (market, sample, side, cut, player, read_on)
);
"""


def get():
    done = subprocess.run(
        ["curl", "-s", "--max-time", "90",
         "%s/american-football/nfl/consistency-sheets" % BASE],
        capture_output=True, text=True)
    return done.stdout or ""


# What the house does not track: a first or last of anything, and any
# "longest". Cut on Jose's word, not on room.
CUT = re.compile(r"\bfirst\b|\blast\b|longest", re.I)


def markets_on(page):
    """Every market the sheet offers, as (value, label) — minus the cut."""
    held = re.search(r'<select[^>]*id="select_market"[^>]*>(.*?)</select>',
                     page, re.S)
    out = []
    for value, label in re.findall(
            r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>',
            held.group(1) if held else "", re.S):
        label = re.sub(r"\s+", " ", html.unescape(
            re.sub(r"<[^>]+>", "", label))).strip()
        if not value or CUT.search(label) or (value, label) in out:
            continue
        out.append((value, label))
    return out


# The sheet's own tokens for each single-filter cut. One filter at a
# time, never crossed: the crosses multiply into nine thousand sheets of
# road-underdog-at-night slivers, while each filter alone is the number a
# reader would actually ask for. Splits do not stand in for these — they
# carry raw yards per cut, not the strike rate against the line.
CUTS = {"all": ("", "", ""),
        "home": ("hm", "", ""), "road": ("aw", "", ""),
        "fav": ("", "fav", ""), "dog": ("", "und", ""),
        "day": ("", "", "day"), "night": ("", "", "night")}


def sheet(market, sample, side, cut="all"):
    """One market's league sheet: one window, one way up, one cut.

       Sorting and a price ceiling change the order, not the data.
    """
    url = ("%s/Consistency_sheet/consistency_sheet_ajax"
           "?sport_url=american-football&league_url=nfl"
           "&upcoming_match=all-matches&market_name=%s&odds_type=american"
           "&sortingValue=&home_road=%s&fav_und=%s&matches_type=%s&theme="
           "&locations_info=&match_info=&page_load=%s"
           "&current_season_url=2026&max_odds=&sort_by=&sort_type="
           "&limit=50&offset=%s&position=&over_under=%s&day_night=%s"
           # A filtered ask is a second ask, and the server knows the
           # difference: with a cut set it answers 400 to page_load=true
           # and to a blank offset — the two values the page only sends
           # on its first, unfiltered load.
           % (BASE, market.replace(",", "%2C"),
              CUTS[cut][0], CUTS[cut][1], sample,
              "true" if cut == "all" else "false",
              "" if cut == "all" else "0",
              side, CUTS[cut][2]))
    done = subprocess.run(
        ["curl", "-s", "--max-time", "120",
         "-H", "X-Requested-With: XMLHttpRequest", "-H", "Loc: null", url],
        capture_output=True, text=True)
    return done.stdout or ""


def _text(said):
    return re.sub(r"\s+", " ", html.unescape(
        re.sub(r"<[^>]+>", " ",
               re.sub(r'data-bs-title="[^"]*"', "", said or "")))).strip()


def games_on(page):
    """The week's games, under the hub's second id for each."""
    out = {}
    for match_id, said in re.findall(
            r'<option[^>]*value="(\d{4,6})"[^>]*>([^<]*?@[^<]*?)</option>',
            page):
        out.setdefault(match_id, said.strip())
    return out


def rows_in(page, market, sample, side, when, cut="all"):
    """Each man's row, read cell by cell against what the cell says it is."""
    out, men = [], []

    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        if "standing-cell" not in row:
            continue
        full = re.search(r'data-bs-title="([^"]+)"', row)
        slug = re.search(r"consistency-sheet-player-details/([a-z0-9.\-]+)",
                         row)
        if not full:
            continue
        who = html.unescape(full.group(1)).strip()

        cells = re.findall(r'<td[^>]*class="([^"]*)"[^>]*>(.*?)</td>', row,
                           re.S)
        # The row's cells, by what each says it is. Two are unnamed —
        # the strike rate is a bare standing-cell and the average hides
        # behind hide_stats — so those two go by the only mark they have.
        said = {"matchup": None, "line": None, "odds": None,
                "win_rate": None, "average": None}
        for mark, inside in cells:
            mark = " %s " % mark
            if " matchup-td" in mark:
                said["matchup"] = _text(inside) or None
            elif "betting-show-item" in mark and "odds" not in mark:
                said["line"] = _text(inside) or None
            elif "td-odds-cell" in mark:
                found = re.search(r'data-american-odds="([^"]*)"', inside)
                said["odds"] = (found.group(1).strip() if found
                                else None)
            elif "hide_stats" in mark:
                said["average"] = _text(inside) or None
            elif mark.strip() == "standing-cell":
                said["win_rate"] = _text(inside) or None

        out.append(dict(said, read_on=when, market=market, sample=sample,
                        side=side, cut=cut, player=who,
                        slug=slug.group(1) if slug else None,
                        results=None))
        if slug:
            men.append({"slug": slug.group(1), "written": who,
                        "person_id": None, "event_id": None,
                        "seen_on": when})
    return out, men


def main():
    db = open_db()
    patiently(lambda: db.executescript(SCHEMA))
    when = time.strftime("%Y-%m-%dT%H:%M:%S")

    page = get()
    games = games_on(page)
    offered = markets_on(page)
    print("%d markets offered after the cut" % len(offered))

    from concurrent.futures import ThreadPoolExecutor
    import sys as _sys
    cuts = (_sys.argv[1:] or ["all"])
    jobs = [(mark, label, sample, side, cut) for mark, label in offered
            for sample in ("last-5", "last-10", "season-2025")
            for side in ("over", "under") for cut in cuts]

    def one(job):
        mark, label, sample, side, cut = job
        return job, sheet(mark, sample, side, cut)

    found, men = [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for at, ((mark, label, sample, side, cut), page_got) in enumerate(
                pool.map(one, jobs), 1):
            got, named = rows_in(page_got, label, sample, side, when, cut)
            found.extend(got)
            men.extend(named)
            if got:
                patiently(lambda: put_many(db, "hub_sheet", got))
                patiently(db.commit)
            if at % 30 == 0 or at == len(jobs):
                print("   %4d/%d sheets — %d rows so far"
                      % (at, len(jobs), len(found)))

    # A man this page names that the prop pages never linked is still a
    # man whose address we now know. Existing rows are left alone — an
    # INSERT OR IGNORE in effect, done by hand because put_many replaces.
    held = {row["slug"] for row in
            db.execute("SELECT slug FROM hub_player")}
    fresh = [one for one in men if one["slug"] not in held]
    if fresh:
        from export_cards import plain
        known = {}
        for row in db.execute("SELECT written, person_id FROM person_name"):
            key = plain(row["written"] or "").strip().lower()
            if key in known and known[key] != row["person_id"]:
                known[key] = None
            else:
                known.setdefault(key, row["person_id"])
        for one in fresh:
            one["person_id"] = known.get(plain(one["written"] or "")
                                         .strip().lower())
        patiently(lambda: put_many(db, "hub_player", fresh))

    # The hub's second id for a game, into the matchup register.
    kept_games = 0
    try:
        clubs = {row["written"].strip().lower(): row["abbr"] for row in
                 db.execute("SELECT written, abbr FROM club_name")}
        for match_id, said in games.items():
            names = [one.strip() for one in re.split(r"\s*@\s*", re.sub(
                r"\s*-\s*\w+day.*$", "", said)) if one.strip()]
            pair = [clubs.get(one.lower()) for one in names]
            if len(pair) == 2 and all(pair):
                db.execute("INSERT OR REPLACE INTO game_name VALUES (?,?,?,?)",
                           ("%s@%s" % tuple(pair), "hub-match", match_id,
                            said))
                kept_games += 1
    except Exception:
        pass
    patiently(db.commit)

    print("%d sheet rows, %d new addresses, %d match ids"
          % (len(found), len(fresh), kept_games))
    print("held: %d sheet rows, %d addresses"
          % (value(db, "SELECT COUNT(*) FROM hub_sheet", default=0),
             value(db, "SELECT COUNT(*) FROM hub_player", default=0)))


if __name__ == "__main__":
    main()
