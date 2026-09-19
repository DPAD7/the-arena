"""The hub's system plays: a graded angle, its record, and who fits it.

   "Moneyline: Medium Favorites — A+, 7-1, 87.5% over the last four
   weeks" is a system play: a condition any game can meet, graded on how
   the condition has been paying, with the upcoming games that meet it
   listed underneath. It is the hub doing openly what our own anchor work
   does — a rule and its record — which makes it worth holding beside
   ours rather than instead of it.

   The index is asked per view (by grade, by team), per window, per
   market; every system it names carries a filter token in its own link
   ("aw+fav-medium"), and the token is what the detail endpoint answers
   on. Tokens are harvested, never composed.

   Run:  python3 build/hub_systems.py
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
CREATE TABLE IF NOT EXISTS hub_system (
    read_on  TEXT NOT NULL,
    window   TEXT NOT NULL,    -- 4-weeks | all | last-season
    market   TEXT NOT NULL,    -- moneyline | spread | total
    token    TEXT NOT NULL,    -- the hub's own filter token
    label    TEXT NOT NULL,    -- "Moneyline: Medium Favorites"
    grade    TEXT,
    record   TEXT,
    win_rate TEXT,
    upcoming TEXT,             -- how many games fit it this week
    PRIMARY KEY (window, market, token, read_on)
);
CREATE TABLE IF NOT EXISTS hub_system_game (
    read_on TEXT NOT NULL,
    window  TEXT NOT NULL,
    market  TEXT NOT NULL,
    token   TEXT NOT NULL,
    said    TEXT NOT NULL,     -- the game line, as the detail writes it
    played  TEXT,              -- past record row or upcoming fixture
    PRIMARY KEY (window, market, token, said, read_on)
);
"""

WINDOWS = ("4-weeks", "all", "last-season")
MARKETS = ("moneyline", "spread", "total")
SHOWS = ("by-grade", "by-team")


def ask(path, args):
    url = "%s/System_plays/%s?%s" % (BASE, path, args)
    done = subprocess.run(
        ["curl", "-s", "--max-time", "90",
         "-H", "X-Requested-With: XMLHttpRequest", "-H", "Loc: ", url],
        capture_output=True, text=True)
    return done.stdout or ""


def _text(said):
    return re.sub(r"\s+", " ", html.unescape(
        re.sub(r"<[^>]+>", " ", said or ""))).strip()


def index(window, market, show):
    page = ask("get_system_plays_data",
               "sport_url=american-football&league_url=nfl&show=%s"
               "&filter=%s&market=%s&theme=&location=" % (show, window,
                                                          market))
    out = []
    for href, inside in re.findall(
            r'<a class="sp-category-label" href="([^"]+)">(.*?)</a>',
            page, re.S):
        token = re.search(r"system-plays-old/[^/]+/([^/]+)/", href)
        badge = re.search(r'<span class="badge">(\d+)</span>', inside)
        label = _text(re.sub(r'<span class="badge">.*?</span>', "", inside,
                             flags=re.S))
        if token:
            out.append({"token": token.group(1), "label": label,
                        "upcoming": badge.group(1) if badge else None})
    return out


def detail(window, market, token):
    page = ask("plays_detail_data",
               "sport_url=american-football&league_url=nfl&filter=%s"
               "&data_filter=%s&market=%s&include_upcoming=true&theme="
               "&location=" % (window, token.replace("+", "%2B"), market))
    said = dict(re.findall(
        r'system-plays-label">(.*?)</p>\s*'
        r'<span class="system-plays-record">(.*?)</span>', page, re.S))
    said = {_text(k): _text(v) for k, v in said.items()}

    games = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        got = _text(row)
        if got and len(got) > 8:
            games.append(got)
    return said, games


def main():
    db = open_db()
    patiently(lambda: db.executescript(SCHEMA))
    when = time.strftime("%Y-%m-%dT%H:%M:%S")

    found = {}
    for window in WINDOWS:
        for market in MARKETS:
            for show in SHOWS:
                for one in index(window, market, show):
                    found.setdefault((window, market, one["token"]), one)
    print("%d systems named on the index" % len(found))

    def one(key):
        window, market, token = key
        return key, detail(window, market, token)

    kept = games_kept = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for (window, market, token), (said, games) in pool.map(
                one, sorted(found)):
            head = found[(window, market, token)]
            patiently(lambda: put_many(db, "hub_system", [{
                "read_on": when, "window": window, "market": market,
                "token": token, "label": head["label"],
                "grade": said.get("Grade"), "record": said.get("Record"),
                "win_rate": said.get("Win %"),
                "upcoming": head.get("upcoming")}]))
            rows = [{"read_on": when, "window": window, "market": market,
                     "token": token, "said": g[:400], "played": None}
                    for g in games]
            if rows:
                patiently(lambda: put_many(db, "hub_system_game", rows))
            patiently(db.commit)
            kept += 1
            games_kept += len(rows)

    print("held: %d systems, %d game rows"
          % (value(db, "SELECT COUNT(*) FROM hub_system", default=0),
             value(db, "SELECT COUNT(*) FROM hub_system_game", default=0)))


if __name__ == "__main__":
    main()
