"""The hub's game preview, kept.

   One request returns the whole page — the section endpoints people go
   looking for do not exist, and `preview.js` makes a single call:

       american_football/nfl/Preview_new/preview_content_ajax?event_id=...

   Eight hundred kilobytes, and everything on it. The parts worth keeping are
   the ones nothing else we hold carries:

     fun facts    a sentence and the market it is about — "the Titans have
                  scored first in each of their last seven home games"
     venue        the ground, its average points, its over/under record
     preview      the written piece, which is the only prose any source gives
     h2h          every past meeting, with the spread and the total
     results      each club's last season game by game, and for every one of
                  them a header line no scoreboard prints: who covered, the
                  quarter-by-quarter leader, the margin at each break, and
                  who led at half and at full time

   The last is the reason for the whole thing. "BUF by 21 at half, BUF by 29
   at three quarters, BUF by 27 at the end" is the shape of an afternoon, and
   it is nowhere in a box score.

   Past games answer as well as future ones. SOURCES.md says the preview page
   is empty for a finished game and that is true of the page — this is the
   request behind it, and it serves them. Only Systems are missing, which the
   hub says outright: they regenerate weekly and are not kept.

   How the archive is reached: the preview endpoint answers on an event id
   and nothing else, and the only ids we held were the ones this week's sweep
   carried. The scoreboard is the enumerator —

       american_football/nfl/Scoreboard/get_active_week_month
       american_football/nfl/Scoreboard/show_scoreboard_matches?season=..

   — the first giving every season back to 2010 and the weeks in each, the
   second the games of one week. `preview_game` holds what they say.

   **2019 is the floor, not 2010.** From 2019 a game carries an event id and
   the full preview answers, finished or not. Before that a game has only a
   review id (`nfl/review/1859`) and the preview endpoint cannot answer on
   one. Those nine seasons are not lost — their review page holds the
   betting-results lines, under different markup — but they are a second
   reader, not this one.

   Run:  python3 build/fetch_preview.py            this week
         python3 build/fetch_preview.py --map      the scoreboard, every season
         python3 build/fetch_preview.py 2025       a whole season
         python3 build/fetch_preview.py --all      every season with event ids
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

from store import open_db, patiently, put_many, rows, value

BASE = "https://dk-statshub-web.isportgenius.com.au"
WORKERS = 3          # it tires under load; three at a time is its pace

SCHEMA = """
-- A sentence the hub wrote about the game, and the market it is about.
--
-- Not `preview_fact`: that name is taken by an older table keyed on our own
-- game_id, and a second thing under one name is how a query comes back right
-- and means something else.
CREATE TABLE IF NOT EXISTS preview_fun (
    event_id   TEXT NOT NULL,
    at         INTEGER NOT NULL,    -- its place in the list
    said       TEXT NOT NULL,       -- the sentence
    market     TEXT,
    side       TEXT,
    odds       TEXT,
    read_on    TEXT,
    PRIMARY KEY (event_id, at)
);

-- The ground, and how it has played.
CREATE TABLE IF NOT EXISTS preview_venue (
    event_id   TEXT PRIMARY KEY,
    venue      TEXT,
    town       TEXT,
    avg_points REAL,
    ou_record  TEXT,
    read_on    TEXT
);

-- Every game the hub holds, which is how the previews are found at all.
--
-- The preview endpoint answers on an event_id and nothing else, and the only
-- ids we held were this week's, out of the current sweep. The scoreboard is
-- the enumerator: one call per season and week gives the ids, and it goes
-- back to 2010.
--
-- `read` is set once a preview has been stored, so a run that stops halfway
-- can be started again without paying for what it already has.
CREATE TABLE IF NOT EXISTS preview_game (
    event_id   TEXT PRIMARY KEY,
    season     TEXT NOT NULL,
    week       TEXT NOT NULL,
    kickoff    TEXT,
    away       TEXT,
    home       TEXT,
    review_id  TEXT,              -- pre-2019 games have this and no event_id
    read       TEXT               -- the day its preview was stored
);
CREATE INDEX IF NOT EXISTS preview_game_when
    ON preview_game (season, week);

-- The written piece. The only prose any source gives us.
CREATE TABLE IF NOT EXISTS preview_story (
    event_id   TEXT PRIMARY KEY,
    story      TEXT,
    read_on    TEXT
);

-- Every past meeting between these two.
CREATE TABLE IF NOT EXISTS preview_h2h (
    event_id   TEXT NOT NULL,
    at         INTEGER NOT NULL,
    week       TEXT,                -- "W2, 2024"
    home       TEXT,
    score      TEXT,
    spread     TEXT,
    total      TEXT,
    read_on    TEXT,
    PRIMARY KEY (event_id, at)
);

-- One past game of one club, with the header line the hub prints over it.
--
-- This is the part nothing else holds. A box score says who won; this says
-- who covered, who led at each break, and by how much.
CREATE TABLE IF NOT EXISTS preview_result (
    event_id     TEXT NOT NULL,
    at           INTEGER NOT NULL,
    club         TEXT,              -- whose run of results this is
    round        TEXT,              -- "Week 18"
    played       TEXT,
    against      TEXT,
    score        TEXT,
    wl           TEXT,
    venue        TEXT,
    quarters     TEXT,              -- both clubs' line score, as printed
    ats_winner   TEXT,
    total_points TEXT,
    qtr_leader   TEXT,
    qtr_margin   TEXT,
    half_margin  TEXT,
    three_margin TEXT,
    win_margin   TEXT,
    lead_half    TEXT,
    lead_full    TEXT,
    read_on      TEXT,
    PRIMARY KEY (event_id, at)
);
"""


def words(fragment):
    return re.sub(r"\s+", " ", html.unescape(
        re.sub(r"<[^>]+>", " ", fragment or ""))).strip()


def number(said):
    found = re.search(r"-?\d+(?:\.\d+)?", said or "")
    return float(found.group(0)) if found else None


def get(event_id):
    url = ("%s/american_football/nfl/Preview_new/preview_content_ajax"
           "?event_id=%s&league_url=nfl&theme=" % (BASE, event_id))
    done = subprocess.run(
        ["curl", "-s", "--max-time", "90",
         "-H", "X-Requested-With: XMLHttpRequest",
         "-H", "Loc: null",
         "-H", "Referer: %s/american-football/nfl/preview/%s" % (BASE, event_id)],
        capture_output=True, text=True) if False else subprocess.run(
        ["curl", "-s", "--max-time", "90",
         "-H", "X-Requested-With: XMLHttpRequest",
         "-H", "Loc: null",
         "-H", "Referer: %s/american-football/nfl/preview/%s" % (BASE, event_id),
         url], capture_output=True, text=True)
    return done.stdout


def facts_in(page):
    out = []
    block = re.search(r"Fun Facts(.*?)(?:Venue Details|GAME PREVIEW|$)",
                      page, re.S | re.I)
    if not block:
        return out
    for at, one in enumerate(re.split(r'<li class="mt-fact-li"', block.group(1))[1:], 1):
        # The sentence, then the market it is about and who it is on. The
        # market is in `betslip-name` above the button and the side is inside
        # it — read the other way round, every fact came back with the market
        # filed as the side and nothing where the market goes.
        said = re.search(r'class="fact-pre">(.*?)</p>', one, re.S)
        market = re.search(r'class="betslip-name">(.*?)</span>', one, re.S)
        side = re.search(r'data-name="([^"]*)"', one)
        odds = re.search(r'data-american-odds="([^"]*)"', one)
        if not said:
            said = re.search(r"<p[^>]*>(.*?)</p>", one, re.S)
        if not said:
            continue
        out.append({"at": at, "said": words(said.group(1)),
                    "market": words(market.group(1)) if market else None,
                    "side": words(side.group(1)) if side else None,
                    "odds": odds.group(1) if odds else None})
    return out


def results_in(page):
    """Each past game of each club, and the header line over it.

       The summary — the round, who it was against, the score and whether it
       was won — sits in the list item; the header line sits in the drawer
       that opens under it. Read from the drawer alone, every result came
       back with no round and no opponent, because they are above it.
    """
    # Which club each run belongs to. The two clubs are tabs, and the tab
    # says whose it is: id="tb1" carries data-section="results|New York Jets".
    # The nearest heading above the list names the *other* club as often as
    # not, which filed every Jets game under Tennessee.
    whose = {}
    for tab, said in re.findall(r'id="(tb\d+)"[^>]*data-section="results\|'
                                r'([^"]*)"', page):
        whose[tab] = words(said)

    out = []
    at = 0
    at_end = 0
    for run in re.split(r'<ul class="result-ul[^"]*">', page)[1:]:
        at_end = page.index(run, at_end)
        which = re.findall(r'class="tab-content (tb\d+)"', page[:at_end])
        club = whose.get(which[-1]) if which else None

        # Split on what starts a row, not on "<li>": each row holds a list
        # of its own and splitting on the tag cut every row at its first
        # inner item, so nothing had a header line under it and the whole
        # section read as empty.
        for one in re.split(r'<li>\s*<a href="javascript:void\(0\)">', run)[1:]:
            body = re.search(r'<ul class="results-points">(.*?)</ul>', one, re.S)
            if not body:
                continue
            by = {}
            for line in re.split(r"<li>", body.group(1))[1:]:
                left = re.search(r'pull-left">(.*?)</div>', line, re.S)
                right = re.search(r'pull-right">(.*?)</div>\s*</div>', line, re.S)
                if left:
                    by[words(left.group(1))] = (words(right.group(1))
                                                if right else None)

            at += 1
            home = re.search(r'class="home-td">(.*?)</div>', one, re.S)
            other = re.search(r'<figure class="tm-figure">.*?</figure>\s*'
                              r'<span>(.*?)</span>', one, re.S)
            rnd = re.search(r'class="round-dt">(.*?)</div>', one, re.S)
            score = re.search(r'<samp>(.*?)</samp>', one, re.S)
            wl = re.search(r'class="wdl [a-z]+">(.*?)</span>', one, re.S)
            when = re.search(r'class="event-title-time">\s*<span>(.*?)</span>',
                             one, re.S)
            where = re.search(r'class="stadium_link"[^>]*>(.*?)</a>', one, re.S)
            lines = re.findall(r'class="right_cell">(.*?)</div>', one, re.S)

            out.append({
                "at": at, "club": club,
                "round": words(rnd.group(1)) if rnd else None,
                "played": words(when.group(1)) if when else None,
                "venue": words(where.group(1)) if where else None,
                # "@" in front of the opponent means it was away.
                "against": ((words(home.group(1)) + " ") if home else "")
                           + (words(other.group(1)) if other else ""),
                "score": words(score.group(1)) if score else None,
                "wl": words(wl.group(1)) if wl else None,
                "quarters": " | ".join(words(x) for x in lines[1:3]) or None,
                "ats_winner": by.get("ATS Winner"),
                "total_points": by.get("Total Points"),
                "qtr_leader": by.get("Qtr by Qtr Leader"),
                "qtr_margin": by.get("Qtr Time Margin"),
                "half_margin": by.get("Half Time Margin"),
                "three_margin": by.get("3 Qtr Time Margin"),
                "win_margin": by.get("Winning Margin"),
                "lead_half": by.get("Team Lead at Half Time"),
                "lead_full": by.get("Team Lead at Full Time"),
            })
    return out


def h2h_in(page):
    out = []
    block = re.search(r"Recent H2H(.*?)(?:</table>)", page, re.S | re.I)
    if not block:
        return out
    for at, row in enumerate(re.split(r"<tr[^>]*>", block.group(1))[1:], 1):
        cells = [words(one) for one in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        cells = [one for one in cells if one]
        if len(cells) < 4:
            continue
        out.append({"at": at, "week": cells[0], "home": cells[1],
                    "score": cells[2],
                    "spread": cells[3] if len(cells) > 3 else None,
                    "total": cells[4] if len(cells) > 4 else None})
    return out


def venue_in(page):
    block = re.search(r"Venue Details(.*?)(?:GAME PREVIEW|Game Preview)",
                      page, re.S | re.I)
    if not block:
        return None
    said = words(block.group(1))
    ground = re.search(r"^(.*?)(?:Stadium|Field|Dome|Park|Center|Centre)\b", said)
    avg = re.search(r"(\d+(?:\.\d+)?)\s*Avg\.?\s*Points", said, re.I)
    ou = re.search(r"(\d+-\d+)\s*O/U", said, re.I)
    town = re.search(r",\s*([A-Za-z ]+?)\s*Stadium", said)
    return {"venue": (ground.group(0).strip() if ground else said[:60]) or None,
            "town": town.group(1).strip() if town else None,
            "avg_points": float(avg.group(1)) if avg else None,
            "ou_record": ou.group(1) if ou else None}


def story_in(page):
    block = re.search(r"(?:GAME PREVIEW|Game Preview)(.*?)(?:Streaks|Systems|$)",
                      page, re.S)
    said = words(block.group(1)) if block else ""
    said = re.sub(r"\s*(?:Less|More)\s*$", "", said).strip()
    return said or None


SEASONS = ("%s/american_football/nfl/Scoreboard/get_active_week_month"
           "?league_url=nfl&sport_url=american-football" % BASE)

MATCHES = ("%s/american_football/nfl/Scoreboard/show_scoreboard_matches"
           "?league_url=nfl&sport_url=american-football"
           "&active_week_month=%%s&season=%%s&team=&offset=0&limit=50&theme="
           % BASE)


def fetched(url):
    got = subprocess.run(["curl", "-s", "-m", "60", url],
                         capture_output=True, text=True)
    return got.stdout or ""


def schedule():
    """Every season the hub holds, and the weeks in each.

       One call. `completed_matches` per week is the count to check an
       enumeration against — a week that comes back short is a week that
       needs reading again, not a week with fewer games.
    """
    said = json.loads(fetched(SEASONS))
    out = []
    weeks = said.get("season_wise_month_weeks", {})
    for one in said.get("all_seasons", []):
        season = one["season"]
        for week in (weeks.get(season, {}).get("season_weeks") or {}).values():
            out.append({
                "season": season,
                "week": week["week_url"],
                "name": week["week_name"],
                "played": int(week.get("completed_matches") or 0),
            })
    return out


def _slug_club(card, which):
    """The club an upcoming card names in its own attribute."""
    found = re.search(r'data-%s="([^"]+)"' % which, card)
    return found.group(1).replace("-", " ").title() if found else None


def week_games(season, week):
    """The games of one week: the id, the kickoff and the two clubs."""
    page = fetched(MATCHES % (week, season))
    out = {}
    # A card names its event id several times over — on the stadium, on each
    # club. Keyed by id, so the repeats fold together.
    # A game that has been played is written "card-info-new result-game-info";
    # one that has not is "card-info-new upcoming-game-card". Split on the
    # half they share, or a week nobody has played yet reads as a week with
    # no games in it — which is exactly how the week being played came back
    # empty while every past week came back whole.
    for card in re.split(r'class="card-info-new ', page)[1:]:
        found = re.search(r'data-event-id="(\d{4,})"', card)
        review = re.search(r'nfl/review/(\d+)', card)
        if not (found or review):
            continue
        # 2019 onward carry an event id, which the preview endpoint answers
        # on. Before that a game has only a review id and the preview is
        # unreachable — the review page holds the betting-results lines
        # instead. Keyed on whichever it has, so nothing is dropped.
        who = found.group(1) if found else "r%s" % review.group(1)
        when = re.search(r'class="vanue-label">(.*?)</span>', card, re.S)
        clubs = re.findall(r'class="m-none">(.*?)</span>', card, re.S)
        out[who] = {
            "event_id": who,
            "review_id": review.group(1) if review else None,
            "season": season, "week": week,
            "kickoff": words(when.group(1)) if when else None,
            # The hub lists the away club first, as the fixture is written.
            # A result card writes the clubs into spans; an upcoming one
            # writes them as slugs on the card itself. Either is read, the
            # spans first, so nothing about the played weeks changes.
            "away": (words(clubs[0]) if len(clubs) > 0
                     else _slug_club(card, "team1")),
            "home": (words(clubs[1]) if len(clubs) > 1
                     else _slug_club(card, "team2")),
        }
    return list(out.values())


def one_game(event_id):
    page = get(event_id)
    if len(page) < 20000:
        return event_id, None
    return event_id, page


def store(db, when, pages):
    """Everything off a batch of pages, written in one go.

       Per week rather than per run: a season is two hundred requests and a
       run that falls over at the end having written nothing is a run that
       has to be paid for twice.
    """
    facts, venues, stories, h2hs, results = [], [], [], [], []
    done = []
    for event_id, page in pages:
        facts += [dict(one, event_id=event_id, read_on=when)
                  for one in facts_in(page)]
        got = venue_in(page)
        if got:
            venues.append(dict(got, event_id=event_id, read_on=when))
        story = story_in(page)
        if story:
            stories.append({"event_id": event_id, "story": story,
                            "read_on": when})
        h2hs += [dict(one, event_id=event_id, read_on=when)
                 for one in h2h_in(page)]
        results += [dict(one, event_id=event_id, read_on=when)
                    for one in results_in(page)]
        done.append(event_id)

    for name, lot in (("preview_fun", facts), ("preview_venue", venues),
                      ("preview_story", stories), ("preview_h2h", h2hs),
                      ("preview_result", results)):
        if lot:
            put_many(db, name, lot)
    for event_id in done:
        patiently(lambda: db.execute(
            "UPDATE preview_game SET read = ? WHERE event_id = ?",
            (when, event_id)))
    patiently(db.commit)
    return len(facts), len(h2hs), len(results)


def read_these(db, when, ids, why):
    """Read a list of games and store them, saying what came back."""
    if not ids:
        return
    kept = []
    with ThreadPoolExecutor(WORKERS) as pool:
        for event_id, page in pool.map(one_game, ids):
            if not page:
                print("   %-12s nothing came back" % event_id)
                continue
            kept.append((event_id, page))
    facts, h2hs, results = store(db, when, kept)
    print("   %-22s %2d/%-3d games  %4d facts, %4d meetings, %4d results"
          % (why, len(kept), len(ids), facts, h2hs, results))


def map_out(db, seasons=None):
    """Fill `preview_game` from the scoreboard, week by week.

       This is what makes an archive possible at all: the preview endpoint
       answers on an event id, and until now the only ids we held were the
       ones this week's sweep happened to carry.
    """
    kept = 0
    for one in schedule():
        if seasons and one["season"] not in seasons:
            continue
        games = week_games(one["season"], one["week"])
        if games:
            put_many(db, "preview_game", games)
            patiently(db.commit)
        kept += len(games)
        short = ("" if len(games) == one["played"] or not one["played"]
                 else "  (hub says %d)" % one["played"])
        print("   %-6s %-24s %2d games%s"
              % (one["season"], one["week"], len(games), short))
    print("\n%d games mapped" % kept)


def main():
    when = time.strftime("%Y-%m-%d")
    db = open_db()
    patiently(lambda: db.executescript(SCHEMA))

    args = sys.argv[1:]
    flags = [one for one in args if one.startswith("-")]
    want = [one for one in args if not one.startswith("-")]

    if "--map" in flags:
        map_out(db, want or None)
        return 0

    if want or "--all" in flags:
        # An archive run. Map first if we have not, then read what is
        # unread — a game already stored is never fetched twice.
        if not value(db, "SELECT COUNT(*) FROM preview_game", default=0):
            print("no games mapped yet — reading the scoreboard first\n")
            map_out(db)

        held = ("SELECT event_id, season, week FROM preview_game "
                "WHERE read IS NULL AND event_id NOT LIKE 'r%' ")
        if want:
            held += "AND season IN (%s) " % ",".join("?" * len(want))
        # Newest first: the recent seasons are the ones anything on the site
        # would show, and a run that is stopped early should have those.
        held += "ORDER BY season DESC, event_id"
        todo = rows(db, held, *want)

        skipped = value(db, "SELECT COUNT(*) FROM preview_game "
                            "WHERE event_id LIKE 'r%'", default=0)
        print("%d games to read%s" % (
            len(todo),
            (", %d before 2019 left alone — those have a review id and no "
             "event id, and the preview endpoint cannot answer on one"
             % skipped) if skipped else ""))

        # A week at a time, so the run can be stopped and started again.
        at = None
        batch = []
        for row in todo:
            mark = (row["season"], row["week"])
            if mark != at and batch:
                read_these(db, when, batch, "%s %s" % at)
                batch = []
            at = mark
            batch.append(str(row["event_id"]))
        if batch:
            read_these(db, when, batch, "%s %s" % at)
    else:
        ids = [str(row["event_id"]) for row in rows(
            db, "SELECT DISTINCT event_id FROM sgp_grid "
                "WHERE read_on = (SELECT MAX(read_on) FROM sgp_grid)")]
        print("%d games to read" % len(ids))
        read_these(db, when, ids, "this week")

    print("\nheld: %d facts, %d venues, %d stories, %d meetings, %d results"
          % (value(db, "SELECT COUNT(*) FROM preview_fun", default=0),
             value(db, "SELECT COUNT(*) FROM preview_venue", default=0),
             value(db, "SELECT COUNT(*) FROM preview_story", default=0),
             value(db, "SELECT COUNT(*) FROM preview_h2h", default=0),
             value(db, "SELECT COUNT(*) FROM preview_result", default=0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
