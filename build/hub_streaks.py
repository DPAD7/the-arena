"""Every run the hub says a club or a man is on, and what it points at.

   "38+ rushing yards with the Ravens as favorites against AFC South
   opponents — 9 wins" is a streak card: who, the sentence itself, how
   long the run is, the market it lives in, the next game, and the price
   on the button. They were being read into a JS file for the mock and
   nowhere else; a run is exactly the shape of fact a card is built from,
   so now they land in the record with everything else.

   The market and odds-floor dropdowns only narrow what one fetch already
   holds — the select is filled client-side from the cards themselves —
   so the whole board is three fetches, one per type.

   Run:  python3 build/hub_streaks.py
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
CREATE TABLE IF NOT EXISTS hub_streak (
    read_on  TEXT NOT NULL,
    kind     TEXT NOT NULL,    -- all | player | team
    who      TEXT NOT NULL,
    slug     TEXT,
    market   TEXT,
    said     TEXT NOT NULL,    -- the sentence, as written
    runs     TEXT,             -- "9 wins"
    next_up  TEXT,
    kickoff  TEXT,
    odds     TEXT,
    outcome_id TEXT,
    PRIMARY KEY (kind, who, said, read_on)
);
"""


def get(kind):
    url = ("%s/Streaks_new/get_streaks_content?sport_url=american-football"
           "&league_url=nfl&theme=dark&event_id=&streak_type=%s&series_url="
           "&streak_odds=any&sports_page=true&page=1&is_page_load=true"
           "&market_url=&offset=0&limit=500&is_scroll=false" % (BASE, kind))
    done = subprocess.run(
        ["curl", "-s", "--max-time", "90",
         "-H", "X-Requested-With: XMLHttpRequest", "-H", "Loc: ", url],
        capture_output=True, text=True)
    return done.stdout or ""


def _text(said):
    return re.sub(r"\s+", " ", html.unescape(
        re.sub(r"<[^>]+>", " ", said or ""))).strip()


def cards_in(page, kind, when):
    out = []
    for card in re.split(r'sport-item streak-box', page)[1:]:
        line = re.search(r'plr-posi-label">(.*?)</span>', card, re.S)
        if not line:
            continue
        who = re.search(r'tm-name">(.*?)</span>', card, re.S)
        slug = re.search(r"consistency-sheet-player-details/([a-z0-9.\-]+)",
                         card)
        market = re.search(r'c-title-label">(.*?)</span>', card, re.S)
        runs = re.search(r'wdl-bx-label">(.*?)</span>\s*'
                         r'<span class="wdl-bx-pre">(.*?)</span>', card, re.S)
        game = re.search(r'next-mt-teams">(.*?)</span>', card, re.S)
        when_next = re.search(r'next-mt-time">(.*?)</span>', card, re.S)
        odds = re.search(r'data-american-odds="([^"]*)"', card)
        outcome = re.search(r'data-outcome-id="([^"]*)"', card)
        out.append({
            "read_on": when, "kind": kind,
            "who": _text(who.group(1)) if who else "",
            "slug": slug.group(1) if slug else None,
            "market": _text(market.group(1)) if market else None,
            "said": _text(line.group(1)),
            "runs": ("%s %s" % (_text(runs.group(1)), _text(runs.group(2))))
                    if runs else None,
            "next_up": re.sub(r"^Next Game\s*", "",
                              _text(game.group(1))) if game else None,
            "kickoff": _text(when_next.group(1)) if when_next else None,
            "odds": odds.group(1).strip() if odds else None,
            "outcome_id": outcome.group(1) if outcome else None,
        })
    return out


def main():
    db = open_db()
    patiently(lambda: db.executescript(SCHEMA))
    when = time.strftime("%Y-%m-%dT%H:%M:%S")

    kept = 0
    for kind in ("all", "player", "team"):
        found = cards_in(get(kind), kind, when)
        if found:
            patiently(lambda: put_many(db, "hub_streak", found))
            patiently(db.commit)
        kept += len(found)
        print("   %-7s %d streaks" % (kind, len(found)))

    print("held: %d, %d markets"
          % (value(db, "SELECT COUNT(*) FROM hub_streak", default=0),
             value(db, "SELECT COUNT(DISTINCT market) FROM hub_streak",
                   default=0)))


if __name__ == "__main__":
    main()
