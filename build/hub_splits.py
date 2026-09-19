"""Last season, cut every way the hub cuts it, for one man at a time.

   The hub keeps a splits page per player: 2025 broken down by home and
   road, day and night, month, conference, division, each opponent, wins
   and losses, favorite and underdog, quarter and half, and inside the
   twenty. Three of those cuts — opponent, division, home/road — are the
   ones a card about this week's fixture would actually want, and none of
   them exist anywhere else we read.

   A man's address on the hub is harvested, never derived. It writes
   "a-j-brown" where his name would give "aj-brown", and
   "kyle-williams-washington-state" where two men share a name and it
   settles them by the college one went to. `hub_player` holds those,
   filled by `hub_props.py` from the pages that link to them.

   The numbers are stored long — one row per man, per stat type, per cut,
   per bucket, per column — because the columns themselves differ by stat
   type, and a table wide enough for all of them would be mostly empty and
   would need widening the first time the hub adds one.

   Run:  python3 build/hub_splits.py            everyone we have an address for
         python3 build/hub_splits.py jaxon-smith-njigba
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

from store import open_db, patiently, put_many, rows, value
from fetch_preview import BASE

SCHEMA = """
CREATE TABLE IF NOT EXISTS hub_split (
    read_on   TEXT NOT NULL,
    slug      TEXT NOT NULL,
    person_id TEXT,
    kind      TEXT NOT NULL,   -- rushing | receiving | passing
    cut       TEXT NOT NULL,   -- Overall, Location, Month, Opponent, ...
    bucket    TEXT NOT NULL,   -- Home, September, ARI, Wins, Q1, ...
    stat      TEXT NOT NULL,   -- games_played, rushing_yards, ...
    value     TEXT,
    PRIMARY KEY (slug, kind, cut, bucket, stat, read_on)
);
CREATE INDEX IF NOT EXISTS hub_split_person ON hub_split (person_id, kind);
CREATE INDEX IF NOT EXISTS hub_split_cut ON hub_split (cut, bucket);
"""

KINDS = ("rushing", "receiving", "passing")


def get(slug, kind):
    """One man's splits page for one stat type.

       Only `stats_type` is answered on the address. Season and season type
       are not — they are read off the page's own selects — and the page
       opens on last season's regular games, which is the cut wanted here.
    """
    url = "%s/american-football/nfl/player-splits/%s?stats_type=%s" % (
        BASE, slug, kind)
    done = subprocess.run(
        ["curl", "-s", "--max-time", "60",
         "-H", "Referer: %s/american-football/nfl/" % BASE, url],
        capture_output=True, text=True)
    return done.stdout or ""


def _text(said):
    return html.unescape(re.sub(r"<[^>]+>", " ", said or "")).strip()


def splits_in(page, slug, person_id, kind, when):
    """Every cut on the page, as the page lays it out.

       Each block names itself in a `tb-title` and holds one table. The
       columns are named on the cells themselves — `sort-type` — rather
       than only in the heading, so a row is read by what each cell says it
       is instead of by counting across, and a column appearing or moving
       does not silently shift every number one place along.
    """
    out = []
    for block in re.split(r'<div class="player-splits-table-block">', page)[1:]:
        title = re.search(r'<span class="tb-title">(.*?)</span>', block, re.S)
        cut = _text(title.group(1)) if title else None
        if not cut:
            continue

        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", block, re.S):
            cells = re.findall(
                r'<td[^>]*sort-type="([^"]*)"[^>]*?'
                r'(?:data-first="([^"]*)")?[^>]*>(.*?)</td>', row, re.S)
            if not cells:
                continue

            named = []
            for stat, first, shown in cells:
                stat = stat.strip()
                if stat in ("", "count", "no-sort"):
                    continue
                said = first if first not in (None, "") else _text(shown)
                named.append((re.sub(r"^player_stats_", "", stat), said))
            if not named:
                continue

            # The first named cell is what the row is a row *of* — the
            # month, the opponent, the season. The rest are its numbers.
            bucket = _text(named[0][1]) or named[0][0]
            for stat, said in named[1:]:
                out.append({"read_on": when, "slug": slug,
                            "person_id": person_id, "kind": kind,
                            "cut": cut, "bucket": bucket,
                            "stat": stat, "value": said})
    return out


def sweep(db, men, kinds=KINDS):
    when = time.strftime("%Y-%m-%dT%H:%M:%S")
    kept = blank = 0

    def one(job):
        man, kind = job
        return man, kind, get(man["slug"], kind)

    jobs = [(man, kind) for man in men for kind in kinds]
    # Somebody else's machine, and no hurry that justifies leaning on it.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for at, (man, kind, page) in enumerate(pool.map(one, jobs), 1):
            found = splits_in(page, man["slug"], man.get("person_id"),
                              kind, when)
            if not found:
                blank += 1
            else:
                patiently(lambda: put_many(db, "hub_split", found))
                patiently(db.commit)
                kept += len(found)
            if at % 50 == 0 or at == len(jobs):
                print("   %4d/%d  %-30s %-10s %d rows held"
                      % (at, len(jobs), man["slug"][:30], kind, kept))
    return kept, blank


def main():
    db = open_db()
    patiently(lambda: db.executescript(SCHEMA))

    if len(sys.argv) > 1:
        men = [{"slug": one, "person_id": None} for one in sys.argv[1:]]
    else:
        men = [dict(one) for one in rows(
            db, "SELECT slug, person_id FROM hub_player ORDER BY slug")]

    print("%d men, %d stat types — %d pages\n"
          % (len(men), len(KINDS), len(men) * len(KINDS)))

    kept, blank = sweep(db, men)
    print("\n%d rows this pass, %d pages with nothing on them" % (kept, blank))
    print("held: %d rows, %d men, %d cuts"
          % (value(db, "SELECT COUNT(*) FROM hub_split", default=0),
             value(db, "SELECT COUNT(DISTINCT slug) FROM hub_split", default=0),
             value(db, "SELECT COUNT(DISTINCT cut) FROM hub_split", default=0)))


if __name__ == "__main__":
    main()
