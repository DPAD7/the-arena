"""The hub's teaser board: every club's spread, moved, and how it holds.

   A teaser moves the spread in the buyer's favor — six points, six and a
   half, seven, ten, thirteen — and this page answers the only question
   about it: how often each club's teased number has actually held over
   its last five or ten. The Wong rows are the narrow case the trade is
   named for, spreads that cross both the three and the seven when moved.

   Held per club per tease size per window, plus the board's own "best
   facts" and "best streaks" shelves, read as written.

   Run:  python3 build/hub_teasers.py
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
CREATE TABLE IF NOT EXISTS hub_teaser (
    read_on TEXT NOT NULL,
    tease   TEXT NOT NULL,     -- 6 | 6.5 | 7 | 10 | 13 | wong
    sample  TEXT NOT NULL,     -- last-5 | last-10
    club    TEXT NOT NULL,
    win_rate TEXT,
    spread  TEXT,              -- the teased number
    original TEXT,             -- wong rows carry the untouched spread too
    odds    TEXT,
    next_up TEXT,
    results TEXT,
    PRIMARY KEY (tease, sample, club, read_on)
);
CREATE TABLE IF NOT EXISTS hub_teaser_note (
    read_on TEXT NOT NULL,
    board   TEXT NOT NULL,     -- facts | streaks
    said    TEXT NOT NULL,
    PRIMARY KEY (board, said, read_on)
);
"""

TEASES = ("6", "6.5", "7", "10", "13")
SAMPLES = ("last-5", "last-10")


def ask(path, args):
    url = "%s/teasers/%s?sport_url=american-football&league_url=nfl&%s" % (
        BASE, path, args)
    done = subprocess.run(
        ["curl", "-s", "--max-time", "90",
         "-H", "X-Requested-With: XMLHttpRequest", "-H", "Loc: ", url],
        capture_output=True, text=True)
    return done.stdout or ""


def _text(said):
    return re.sub(r"\s+", " ", html.unescape(
        re.sub(r"<[^>]+>", " ",
               re.sub(r'data-bs-title="[^"]*"', "", said or "")))).strip()


def board(tease, sample, wong):
    return ask("teasers_content_ajax",
               "matches_type=%s&theme=&location=&current_season_url=2026"
               "&teaser_value=%s&wong_teaser=%s"
               % (sample, tease, "true" if wong else "false"))


def rows_in(page, tease, sample, when):
    """Ten cells a row, mapped by position — the ajax ships no headings.

       club · win% · teased spread · the priced button (whose text also
       carries the original spread) · next game · then one letter per game
       played. The wong board ships the same ten cells.
    """
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 6:
            continue
        said = [_text(one) for one in cells]
        club = re.search(r'data-section="team\|([^"]+)"', row)
        club = (html.unescape(club.group(1)).strip() if club else said[0])
        odds = re.search(r'data-american-odds="([^"]*)"', row)
        # "Carolina Panthers +2.5 Panthers" — the number in the button's
        # own words is the spread before it was teased.
        original = re.search(r"[+-]\d+(?:\.\d+)?", said[3] or "")
        out.append({
            "read_on": when, "tease": tease, "sample": sample, "club": club,
            "win_rate": said[1] or None,
            "spread": said[2] or None,
            "original": original.group(0) if original else None,
            "odds": odds.group(1).strip() if odds else None,
            "next_up": said[4] or None,
            "results": " ".join(said[5:]) or None,
        })
    return out


def main():
    db = open_db()
    patiently(lambda: db.executescript(SCHEMA))
    when = time.strftime("%Y-%m-%dT%H:%M:%S")

    jobs = [(tease, sample, False) for tease in TEASES for sample in SAMPLES]
    jobs += [("wong", sample, True) for sample in SAMPLES]

    def one(job):
        tease, sample, wong = job
        return job, board("6" if wong else tease, sample, wong)

    kept = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for (tease, sample, _), page in pool.map(one, jobs):
            found = rows_in(page, tease, sample, when)
            if found:
                patiently(lambda: put_many(db, "hub_teaser", found))
                patiently(db.commit)
                kept += len(found)
            print("   %-5s %-8s %2d clubs" % (tease, sample, len(found)))

    notes = []
    for name, path in (("facts", "teaser_best_facts_content_ajax"),
                       ("streaks", "teaser_best_streaks_content_ajax")):
        page = ask(path, "matches_type=last-5&theme=&location="
                         "&current_season_url=2026&teaser_value=6"
                         "&wong_teaser=false")
        for block in re.findall(r"<li[^>]*>(.*?)</li>", page, re.S):
            got = _text(block)
            if got and len(got) > 12:
                notes.append({"read_on": when, "board": name,
                              "said": got[:400]})
    if notes:
        patiently(lambda: put_many(db, "hub_teaser_note", notes))
        patiently(db.commit)

    print("held: %d teaser rows, %d notes"
          % (value(db, "SELECT COUNT(*) FROM hub_teaser", default=0),
             value(db, "SELECT COUNT(*) FROM hub_teaser_note", default=0)))


if __name__ == "__main__":
    main()
