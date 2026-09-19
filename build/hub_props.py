"""Every player price the hub puts on a matchup, one row per selection.

   The hub keeps a page per fixture nobody had read: *player props*. It is
   the deepest board we have access to for the things the other four are
   thinnest on — a man's second touchdown, his third, the first scorer, the
   whole alt-yards ladder rung by rung. Six hundred priced selections for
   one game, and sixteen games a week.

   It was worth finding because of what it settles. Three hundred and forty
   legs sat on the shelf with no price and the note that no board sold them
   as a single leg — theScore only pairs them with a second man, and
   DraftKings only sells the season. Both true, and both beside the point:
   the hub sells every one of them on its own, per fixture, and has all
   along.

   Nothing is navigated and nothing is guessed. The page is fetched as it
   stands and every price on it is an attribute already in the markup —
   `data-name`, `data-event-name`, `data-american-odds` — so this reads
   what the page says rather than what a layout looks like.

   Run:  python3 build/hub_props.py              this week
         python3 build/hub_props.py 2026 1       a named week
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
from fetch_preview import BASE, schedule, week_games

SCHEMA = """
CREATE TABLE IF NOT EXISTS hub_prop (
    read_on    TEXT NOT NULL,
    event_id   TEXT NOT NULL,
    fixture    TEXT,
    kickoff    TEXT,
    player     TEXT,          -- as the button names him, figure and all
    market     TEXT,          -- the heading the page shows over the price
    book_said  TEXT,          -- the book's own internal name for the market
    said       TEXT,
    odds       TEXT,
    market_id  TEXT,
    outcome_id TEXT,
    PRIMARY KEY (event_id, outcome_id, read_on)
);
CREATE INDEX IF NOT EXISTS hub_prop_player ON hub_prop (player);
CREATE INDEX IF NOT EXISTS hub_prop_market ON hub_prop (market);

-- The hub's own address for a man. Harvested, never derived: it writes
-- "a-j-brown" where the name would give "aj-brown", and it writes
-- "kyle-williams-washington-state" where two men share a name and it
-- settles them by the college one of them went to. Neither is guessable
-- from the name, and a guessed address answers 404 or answers about
-- somebody else.
CREATE TABLE IF NOT EXISTS hub_player (
    slug      TEXT PRIMARY KEY,
    written   TEXT,
    person_id TEXT,          -- ours, where the register can settle him
    event_id  TEXT,
    seen_on   TEXT
);
CREATE INDEX IF NOT EXISTS hub_player_person ON hub_player (person_id);
"""

# Every attribute the markup already carries. Read as written: the page is
# the source, and a layout that shifts must not move a price.
WANT = {"name": "player", "event-name": "book_said", "american-odds": "odds",
        "market-id": "market_id", "outcome-id": "outcome_id",
        "description": "said", "dk-event-name": "fixture",
        "match-time": "kickoff", "event-id": "event_id"}


def get(event_id):
    """The matchup's player-prop page, as it stands."""
    url = "%s/american-football/nfl/player-props/%s" % (BASE, event_id)
    done = subprocess.run(
        ["curl", "-s", "--max-time", "90",
         "-H", "Referer: %s/american-football/nfl/" % BASE, url],
        capture_output=True, text=True)
    return done.stdout or ""


def priced_in(page, when):
    """One row per priced selection, under the heading it is sold beneath.

       The page groups its prices into market cards, each with a heading of
       its own — "Touchdown Scorer", "To Score 2+ TDs", "Alt Receptions" —
       and that heading is what a reader sees and what the market actually
       is. The button underneath carries the book's internal name instead,
       and the two are not the same: the heading says "Touchdown Scorer"
       where the button says "Anytime Touchdown", and the heading says
       "Team First Touchdown Scorer" where the button says "1st SEA
       Seahawks TD Scorer".

       So the page is read card by card and each price is kept under its own
       heading, with the book's internal name kept beside it rather than in
       place of it. Read button-first, every price on the page arrives
       labelled as something nobody publishing it ever called it.
    """
    out = []
    for card in re.split(r'<div class="market-card">', page)[1:]:
        heading = re.search(r'<span class="market-name">(.*?)</span>', card, re.S)
        market = html.unescape(re.sub(r"<[^>]+>", "", heading.group(1))).strip() \
            if heading else None

        for said in re.findall(
                r'<div class="betslip-button add-to-betslip"([^>]*)>', card):
            row = {"read_on": when, "market": market}
            for mark, name in WANT.items():
                found = re.search(r'data-%s\s*=\s*"([^"]*)"' % mark, said)
                row[name] = (html.unescape(found.group(1)).strip()
                             if found else None)
            # A selection with no price is a button the page draws and does
            # not sell. It is not a price and is not kept as one.
            if not row.get("odds") or not row.get("outcome_id"):
                continue
            out.append(row)
    return out


def men_in(page, event_id, when):
    """Every man the page links to, and the hub's address for him.

       The link and the name beside it are read together, so the address is
       tied to a spelling rather than to a position on the page. The
       spelling is then put through `person_name` like every other name
       here — and where the register cannot settle it, the row is kept with
       nobody attached rather than attached to a guess.
    """
    from export_cards import plain

    # The link and the name are one element:
    #   <span class="props-tm-name player-page-link"
    #         target-data-url="...player-details/rhamondre-stevenson">
    #       Rhamondre Stevenson</span>
    # so they are read from it together. Read separately — the links from
    # one block and the names from another — every man in a block came back
    # wearing the name of whoever was written first in it, and three
    # hundred slugs all answered to Tory Horton.
    found = {}
    for slug, name in re.findall(
            r'target-data-url="[^"]*consistency-sheet-player-details/'
            r'([a-z0-9.\-]+)"[^>]*>(.*?)<', page, re.S):
        name = html.unescape(re.sub(r"<[^>]+>", "", name)).strip()
        if slug and name:
            found.setdefault(slug, name)

    known = {}
    try:
        from store import open_db as _open
        for row in _open().execute("SELECT written, person_id FROM person_name"):
            key = plain(row["written"] or "").strip().lower()
            if key in known and known[key] != row["person_id"]:
                known[key] = None
            else:
                known.setdefault(key, row["person_id"])
    except Exception:
        known = {}

    out = []
    for slug, name in found.items():
        # The button's name carries the figure on a ladder rung — "Jaxon
        # Smith-Njigba 90+" — and the man is the part in front of it.
        bare = re.sub(r"\s+\d+(?:\.\d+)?\+?$", "", name or "").strip()
        out.append({"slug": slug, "written": bare or None,
                    "person_id": known.get(plain(bare).strip().lower()),
                    "event_id": event_id, "seen_on": when})
    return out


def fixture_of(game):
    """The two clubs, as the fixture is written."""
    return "%s @ %s" % (game.get("away") or "?", game.get("home") or "?")


def sweep(db, games):
    when = time.strftime("%Y-%m-%dT%H:%M:%S")
    kept = 0

    def one(game):
        page = get(game["event_id"])
        return game, priced_in(page, when), men_in(page, game["event_id"], when)

    # Sixteen pages of a megabyte each. Read a few at a time rather than one
    # after another, and rather than all at once — the hub is somebody
    # else's machine and there is no hurry that justifies leaning on it.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for game, rows, men in pool.map(one, games):
            if not rows:
                print("   %-12s nothing priced" % fixture_of(game))
                continue
            for row in rows:
                row.setdefault("event_id", game["event_id"])
                row["event_id"] = row["event_id"] or game["event_id"]
            # Written and committed per fixture. `put_many` does not commit
            # — every caller does its own — and a sweep that only committed
            # at the end reported six thousand prices held and left none
            # behind it.
            patiently(lambda: put_many(db, "hub_prop", rows))
            if men:
                patiently(lambda: put_many(db, "hub_player", men))
            patiently(db.commit)
            kept += len(rows)
            print("   %-12s %4d priced" % (fixture_of(game), len(rows)))
    return kept


def main():
    db = open_db()
    patiently(lambda: db.executescript(SCHEMA))

    if len(sys.argv) > 2:
        season, week = sys.argv[1], sys.argv[2]
        if not week.startswith("week"):
            week = "week-%s" % week
    else:
        # The week being played is the first one nobody has played yet, in
        # the newest season the hub lists. Asked for by name it would go
        # stale on a Tuesday; asked for this way it never does.
        weeks = schedule()
        newest = max(one["season"] for one in weeks)
        ahead = [one for one in weeks
                 if one["season"] == newest and not one["played"]]
        season = newest
        week = ahead[0]["week"] if ahead else "week-1"

    games = week_games(season, week)
    print("%d games, %s %s\n" % (len(games), season, week))

    kept = sweep(db, games)
    print("\n%d priced selections this pass" % kept)
    print("held: %d prices, %d men, %d markets"
          % (value(db, "SELECT COUNT(*) FROM hub_prop", default=0),
             value(db, "SELECT COUNT(DISTINCT player) FROM hub_prop", default=0),
             value(db, "SELECT COUNT(DISTINCT market) FROM hub_prop", default=0)))


if __name__ == "__main__":
    main()
