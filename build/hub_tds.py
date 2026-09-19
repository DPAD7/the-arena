"""The hub's touchdown page: who scores, how often, and who allows it.

   Two tables per cut. The first is the player himself — touchdowns, per
   game, the streak he is on, how often he gets one and two, what share of
   his club's scores are his, how long they run. The second is the matchup
   — the implied chance this week, and what the opponent has been giving
   up: total scores allowed, the rate, how many games with one or two
   against them.

   This is the closest published thing to the pairing work ours will do,
   which is why it is held: the rebuild gets to stand on it rather than
   start beside it.

   Run:  python3 build/hub_tds.py
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
CREATE TABLE IF NOT EXISTS hub_td (
    read_on TEXT NOT NULL,
    board   TEXT NOT NULL,     -- stats | matchups
    kind    TEXT NOT NULL,     -- rushing-receiving | passing | rushing | receiving
    sample  TEXT NOT NULL,     -- 5-matches | 10-matches | all
    rank    TEXT,
    player  TEXT NOT NULL,
    stat    TEXT NOT NULL,     -- the column, as the page titles it
    value   TEXT,
    PRIMARY KEY (board, kind, sample, player, stat, read_on)
);
CREATE INDEX IF NOT EXISTS hub_td_player ON hub_td (player, kind);
"""

KINDS = ["rushing-receiving", "passing", "rushing", "receiving"]
# Their "all" is not this season — it is the man's career. Henry answers
# it with 134 touchdowns and Allen with 91, which read as nonsense beside
# a season and are exactly right beside a career. Stored under the name
# it actually means.
#
# One column is broken at the source on that sample: career "% TEAM TDs"
# comes back over 300% — they sum the season shares instead of computing
# the share. Kept as written, per the house rule, and never to be read by
# anything that scores a leg.
SAMPLES = ["5-matches", "10-matches", "all"]
SAMPLE_NAMES = {"5-matches": "5-matches", "10-matches": "10-matches",
                "all": "career"}
BOARDS = {"stats": "touchdown_stats", "matchups": "upcoming_games"}

SECTIONS = ("touchdowns|streak|Oneplus_touchdowns_percentage|"
            "total_first_touchdowns|first_td_streak|"
            "first_game_touchdown_percentage|overall")


def get(kind, sample, target):
    url = ("%s/american_football/nfl/touchdowns/get_touchdown_stats"
           "?sport_url=american-football&league_url=nfl&season_url=2025"
           "&theme=&team_url=all&stats_type=%s&sample_size=%s"
           "&all_stats_section=%s&target_id=%s&is_clicked=false"
           % (BASE, kind, sample,
              SECTIONS.replace("|", "%7C"), target))
    done = subprocess.run(
        ["curl", "-s", "--max-time", "90",
         "-H", "X-Requested-With: XMLHttpRequest",
         "-H", "Referer: %s/american-football/nfl/touchdowns" % BASE, url],
        capture_output=True, text=True)
    return done.stdout or ""


def _text(said):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ",
                                re.sub(r"data-bs-title=\"[^\"]*\"", "",
                                       said or "")))).strip()


def table_in(page, board, kind, sample, when):
    """The one table on the page, read against its own headings.

       The headings and the rows come out of the same table, so a column
       that moves takes its name with it. The name cell keeps only the
       man — the page tucks his short form and his tooltip into the same
       cell, which read whole comes out "Chase Brown C. Brown".
    """
    heads = [_text(one) for one in re.findall(r"<th[^>]*>(.*?)</th>", page,
                                              re.S)]
    heads = [one for one in heads if one]
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 4:
            continue
        rank = _text(cells[0])
        # The name cell writes the man twice — his full name for wide
        # screens, his short form for narrow ones — and read whole he came
        # out "Chase Brown C. Brown". The wide form is the name.
        cell = cells[1] if len(cells) > 1 else ""
        name = re.search(r'class="tm-name mob-none">(.*?)</span>', cell, re.S)
        who = _text(name.group(1)) if name else _text(cell)
        for at, cell in enumerate(cells):
            if at >= len(heads):
                break
            stat = heads[at]
            if stat in ("RANK", "NAME") or stat.startswith("ODDS"):
                continue
            out.append({"read_on": when, "board": board, "kind": kind,
                        "sample": sample, "rank": rank, "player": who,
                        "stat": stat, "value": _text(cell)})
    return out


def main():
    db = open_db()
    patiently(lambda: db.executescript(SCHEMA))
    when = time.strftime("%Y-%m-%dT%H:%M:%S")

    jobs = [(board, target, kind, sample)
            for board, target in BOARDS.items()
            for kind in KINDS for sample in SAMPLES]

    def one(job):
        board, target, kind, sample = job
        return job, get(kind, sample, target)

    kept = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for (board, target, kind, sample), page in pool.map(one, jobs):
            rows = table_in(page, board, kind, SAMPLE_NAMES[sample], when)
            if rows:
                patiently(lambda: put_many(db, "hub_td", rows))
                patiently(db.commit)
                kept += len(rows)
            print("   %-9s %-18s %-10s %5d rows" % (board, kind, sample,
                                                    len(rows)))
    print("\n%d rows this pass — held %d"
          % (kept, value(db, "SELECT COUNT(*) FROM hub_td", default=0)))


if __name__ == "__main__":
    main()
