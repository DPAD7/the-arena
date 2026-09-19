"""The books' own cards, sorted onto the pages they belong to.

   Both books build the same thing: a named card — "Brotherly Backfield" —
   with a few legs on it. A leg names a man or a club, and that is what
   decides where the card is shown:

     a leg naming a quarterback we carry  -> his page
     a leg naming a club                  -> that club's page
     both, or two quarterbacks            -> all of them

   A card naming nobody we follow is still kept. It is simply not shown —
   "South Philly Scoring Fest" is three receivers and a total, and belongs on
   no page of ours.

   Nothing here invents a card. These are the books' own, read as they were
   written, and the only work is deciding whose they are.

   Run:  python3 build/export_cards.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hashlib
import json
import re
import sqlite3
import time

DB = "data/qbspy.db"
OUT = "data/cards.js"

# A suffix says which of two men he is, not what he is called.
SUFFIX = re.compile(r"\s+(?:[JS]r\.?|I{1,3}|IV|VI{0,3}|IX|X)$", re.I)


# ---- How a fixture is written on a card ----

_CLUBS = None


def club_short():
    """Every club's name, city and nickname against its three letters."""
    global _CLUBS
    if _CLUBS is not None:
        return _CLUBS

    data = open("data/data.js").read()
    teams = json.loads(re.search(r"TEAMS = (\[.*?\n\]);", data, re.S).group(1))

    out = {}
    for team in teams:
        abbr = team["abbr"]
        for said in (team.get("name"), team.get("short"), team.get("location"),
                     "%s %s" % (team.get("abbr"), team.get("short")),
                     str(team.get("name", "")).split()[-1]):
            if said:
                out[said.lower()] = abbr
    _CLUBS = out
    return out


def short_fixture(said):
    """A fixture as a card says it: "WAS @ PHI".

       A club's full name belongs on a club's page. On a card it is the three
       letters, the same as inside a leg — and not only for tidiness: the line
       under the title is drawn at one size on a picture eleven hundred wide,
       and "Washington Commanders @ Philadelphia Eagles" with a day and a
       kickoff in front of it ran a hundred and sixty pixels past the edge.
       Two hundred and eighty-seven cards were being shared with their own
       fixture cut in half."""
    said = str(said or "").strip()
    if not said:
        return said

    # The books do not agree on what goes between two clubs: "@", "vs", "vs."
    # and "vs*" all turn up. Splitting on "@" alone left a third of the cards
    # untouched and reading "San Francisco 49ers vs* Los Angeles Rams".
    parts = re.split(r"\s+(?:@|vs\.?\*?|v\.?)\s+", said, maxsplit=1,
                     flags=re.I)

    # And sometimes nothing goes between them at all. The hub heads a
    # same-game card with "Washington Commanders  Philadelphia Eagles" — two
    # spaces where the "@" would be — so the split found one part, the name
    # was handed back whole, and the card read "Matchup Washington
    # Commanders Philadelphia Eagles".
    if len(parts) != 2 and "  " in said:
        parts = [one.strip() for one in re.split(r"\s{2,}", said, maxsplit=1)]

    if len(parts) != 2 or not all(parts):
        return said

    clubs = club_short()
    sides = [one.strip() for one in parts]

    out = []
    for one in sides:
        found = clubs.get(one.lower())

        # The books write their own short forms — "NY Giants", "SF 49ers",
        # "LA Rams" — which are neither the club's name nor our abbreviation
        # and its nickname. The nickname alone is enough and is unique across
        # the league, so it is tried when the whole string is not held.
        if not found:
            found = clubs.get(one.lower().split()[-1]) if one.split() else None

        if not found:
            # A name we do not hold is left exactly as it was written rather
            # than cut down to something that might be a different club.
            return said
        out.append(found)

    return "%s @ %s" % (out[0], out[1])


def plain(name):
    short = SUFFIX.sub("", str(name or "")).strip()
    return short or str(name or "")


def quarterbacks():
    """Every man we carry a page for, by every name a book might use.

       A book writes him as "Jalen Hurts", a card leg as "Jalen Hurts
       Touchdowns Scored", and a props table as "J. Hurts". All three have to
       find him.
    """
    data = open("data/data.js").read()
    at = data.find("var PLAYERS")
    body = data[at:]

    out = {}
    for m in re.finditer(r'"id":\s*"(\d+)",\s*"rank":\s*(\d+),\s*"team":\s*"(\w+)",'
                         r'\s*"name":\s*"([^"]+)"', body):
        qb_id, rank, team, name = m.group(1), int(m.group(2)), m.group(3), m.group(4)
        short = plain(name)
        parts = short.split()
        keys = {short.lower(), name.lower()}
        if len(parts) > 1:
            # "J. Hurts" and "J.Hurts", the way a book abbreviates him.
            keys.add(("%s. %s" % (parts[0][0], parts[-1])).lower())
            keys.add(("%s.%s" % (parts[0][0], parts[-1])).lower())
            # His surname alone, used only by the initial-matching pass —
            # never on its own, or every Allen is Josh.
            keys.add(parts[-1].lower())
        for key in keys:
            out.setdefault(key, {"id": qb_id, "name": short,
                                 "team": team, "rank": rank})
    return out


def clubs():
    """Every club, by every name a book might use for it."""
    data = open("data/data.js").read()
    out = {}
    for m in re.finditer(r'"id":\s*"(\w+)",\s*"espnId":\s*"\d+",\s*"abbr":\s*"(\w+)",'
                         r'\s*"name":\s*"([^"]+)",\s*"short":\s*"([^"]+)"', data):
        club, abbr, name, short = m.groups()
        for key in {abbr.lower(), name.lower(), short.lower(),
                    ("%s %s" % (abbr, short)).lower()}:
            out.setdefault(key, {"id": club, "abbr": abbr, "name": name,
                                 "short": short})
    return out


def squads():
    """Every player on every club's roster — not only the quarterbacks.

       A card is connected to every man it names, because the huddle already
       lists all of them and they will have pages of their own. What is shown
       today is narrower than what is stored: the quarterbacks and the clubs.
       Storing the rest now means nothing has to be swept again later.
    """
    data = open("data/rosters.js").read()
    out, by_id = {}, {}
    for club in re.finditer(r'"(\w{2,3})":\[(.*?)\](?=,"\w{2,3}":\[|\})', data, re.S):
        abbr, body = club.group(1), club.group(2)
        for man in re.finditer(r'"id":"(\d+)","name":"([^"]+)"[^}]*?"spot":"(\w*)"', body):
            one = {"id": man.group(1), "name": plain(man.group(2)),
                   "club": abbr, "spot": man.group(3)}
            out.setdefault(one["name"].lower(), []).append(one)
            by_id[one["id"]] = one

    # And every other way a source writes him.
    #
    # The roster is ESPN's spelling and the books are not obliged to agree
    # with it: it says "Kenny Gainwell" and DraftKings, theScore and the hub
    # all say "Kenneth Gainwell". Indexed on the roster's spelling alone, two
    # priced cards named him and reached no club and no page — which is
    # matching on the written name, the one thing there is a table to avoid.
    #
    # `person_name` already holds every spelling against one id. Each is
    # pointed at the man the roster knows, so a card is connected however the
    # book chose to write him.
    try:
        db = sqlite3.connect("data/qbspy.db", timeout=60)
        db.row_factory = sqlite3.Row
        by_name = {one["name"].lower(): one for one in by_id.values()}
        for row in db.execute("""SELECT pn.written, pn.person_id, p.name
                                   FROM person_name pn
                                   JOIN person p ON p.id = pn.person_id"""):
            # The id first, and the man's own name where the id does not
            # reach: `person` carries Gainwell twice, once under ESPN's id
            # and once under an older one, and the books' spelling is filed
            # against the older. The name is what ties the two together.
            one = (by_id.get(str(row["person_id"]))
                   or by_name.get(plain(row["name"] or "").lower()))
            said = plain(row["written"] or "").lower()
            if not one or not said or len(said) < 4:
                continue
            if one not in out.setdefault(said, []):
                out[said].append(one)
        db.close()
    except Exception:
        # A spelling table that will not open must not cost us the roster.
        pass

    return out


# What the line is about says who it can be about. A back does not throw for
# two hundred yards and a quarterback is not targeted — so the market itself
# rules most people out before any name is compared.
CAN_DO = {
    "Passing Yards": {"QB"},
    "Passing TDs": {"QB"},
    "Receiving Yards": {"WR", "TE", "RB", "FB"},
    "Receiving TDs": {"WR", "TE", "RB", "FB"},
    "Rushing Yards": {"QB", "RB", "FB", "WR"},
    "Rushing TDs": {"QB", "RB", "FB", "WR"},
    "Receiving": {"WR", "TE", "RB", "FB"},
    "Anytime TD": {"QB", "RB", "FB", "WR", "TE"},
    "First TD": {"QB", "RB", "FB", "WR", "TE"},
}


def could_be(man, kind):
    """Whether this man could be the one a line of that kind is about."""
    allowed = CAN_DO.get(kind)
    if not allowed:
        return True
    spot = (man.get("spot") or "").upper()
    return not spot or spot in allowed


def the_one(men, sides, kind=None):
    """Which of two men with the same name a line means.

       Two things tell them apart, and the stronger is what is being asked:
       Jeremiyah Love is a back, so a passing line is not his whatever club he
       is on. Where the market cannot separate them the fixture does — and
       where neither can, none is chosen. A guess here puts a linebacker's
       club on a receiver's card, which is how a Vikings card came to be filed
       under Cleveland.
    """
    if len(men) == 1:
        return men[0] if could_be(men[0], kind) else None

    able = [one for one in men if could_be(one, kind)]
    if len(able) == 1:
        return able[0]

    here = [one for one in (able or men) if one["club"] in (sides or [])]
    return here[0] if len(here) == 1 else None


def named_in(words, men, teams, squad=None, sides=None, kind=None):
    """Whoever a leg is about. A leg is a sentence — "Jalen Hurts Touchdowns
       Scored" — so the names are looked for inside it rather than matched
       against it whole."""
    said = " " + str(words or "").lower() + " "

    who, clubs_found, anyone = [], [], []

    for key, man in men.items():
        # Two words at least, so a bare surname cannot catch the wrong man.
        if " " not in key or len(key) < 6:
            continue
        if (" " + key + " ") in said or said.startswith(" " + key):
            if man["id"] not in [one["id"] for one in who]:
                who.append(man)

    # A book writes the name on his birth certificate; we hold the one he is
    # called. "Cameron Ward" is our "Cam Ward", and matching the two whole
    # never finds him. So a surname counts when the first names begin with
    # the same letter — which is Cam and Cameron, Mike and Michael, and not
    # two different Wards.
    for key, man in men.items():
        if " " in key or man["id"] in [one["id"] for one in who]:
            continue
        parts = man["name"].split()
        if len(parts) < 2:
            continue
        surname = parts[-1].lower()
        first = parts[0][0].lower()

        given = parts[0].lower()

        for hit in re.finditer(r"([a-z'\-\.]+)\s+" + re.escape(surname) + r"\b", said):
            said_first = hit.group(1).strip(".")
            if said_first[:1] != first:
                continue
            # An initial stands for anything; a written-out name must be one
            # of the two spellings of his own — "Cam" inside "Cameron", or
            # the other way about. "Jeremiyah" is neither, and is not him.
            initial = len(said_first) <= 1 or hit.group(1).endswith(".")
            if initial or said_first.startswith(given) or given.startswith(said_first):
                who.append(man)
                break

    for key, club in teams.items():
        if len(key) < 3:
            continue
        if (" " + key + " ") in said:
            if club["id"] not in [one["id"] for one in clubs_found]:
                clubs_found.append(club)

    # A card that names a man names his club, whether or not it says so:
    # "Jahmyr Gibbs Touchdowns Scored" is a Lions card. Every man named is
    # kept, quarterback or not.
    for key, lot in (squad or {}).items():
        if " " not in key or len(key) < 6:
            continue
        if (" " + key + " ") in said or said.startswith(" " + key):
            man = the_one(lot, sides, kind)
            if not man:
                continue
            if man["id"] not in [one["id"] for one in anyone]:
                anyone.append(man)
            club = teams.get(man["club"].lower())
            if club and club["id"] not in [one["id"] for one in clubs_found]:
                clubs_found.append(club)

    return who, clubs_found, anyone


def score_cards(db, men, teams):
    """theScore's named cards, newest reading of each."""
    out = []
    seen = set()

    for row in db.execute("""
            SELECT c.card_id, c.title, c.header, c.odds, c.payout, c.fixture,
                   c.starts, c.event_id, c.read_on
              FROM score_card c
             ORDER BY c.read_on DESC"""):
        # On the card, for the same reason as DraftKings below. Their board
        # has 60 names for 60 cards today, so this costs nothing now and
        # stops a reused name from quietly dropping cards later.
        if row["card_id"] in seen:
            continue
        seen.add(row["card_id"])

        legs = []
        for leg in db.execute("""
                SELECT at, market, said, odds FROM score_card_leg
                 WHERE card_id = ? AND read_on = ? ORDER BY at""",
                (row["card_id"], row["read_on"])):
            # The lounge writes which game a leg is from onto the end of
            # its market — "Jaxon Smith-Njigba Touchdowns Scored (NE @ SEA)"
            # — because a card there can span three of them. Read as it
            # comes, the fixture ended up inside the man's name: "Jaxon
            # Smith-Njigba (NE". The clubs are found from the whole card
            # anyway, so the tail is taken off before the leg is read.
            legs.append({"said": leg["said"],
                         # The lounge is one of two sources that prices each
                         # leg as well as the card. It has been read and
                         # dropped on the floor since the first sweep: the
                         # column is in the SELECT above and went nowhere.
                         "odds": leg["odds"],
                         "market": re.sub(r"\s*\([A-Z]{2,3} @ [A-Z]{2,3}\)\s*$",
                                          "", leg["market"] or "")})

        out.append({
            "id": row["card_id"], "source": "score", "title": row["title"],
            # "Same Game Parlay" is the book's word for a wager. What the
            # card is about is more use and reads as what this is.
            "header": None, "markets": None,
            "chance": likely(row["odds"]), "price": priced(row["odds"]),
            "fixture": short_fixture(row["fixture"]), "starts": row["starts"],
            "event": row["event_id"],
            "legs": [dict(read_leg(one.get("said"), one.get("market")), **one)
                     for one in legs],
        })

    return out


def total_on(db, fixture):
    """The number a fixture's total is set at.

       Found by the two clubs, not by an id: the hub numbers its own games —
       34118042 for the one ESPN calls 401872656 — and matching the id found
       nothing every time.
    """
    parts = re.split(r"\s+(?:@|vs\.?)\s+", str(fixture or ""))
    if len(parts) != 2:
        return None

    clubs = []
    for part in parts:
        got = db.execute(
            "SELECT club FROM club_look WHERE lower(name) = ? "
            "OR club = ? LIMIT 1",
            (part.strip().lower(), part.strip())).fetchone()
        if got:
            clubs.append(got[0])
    if len(clubs) != 2:
        return None

    got = db.execute(
        "SELECT l.over_under FROM espn_line l JOIN league_game g "
        "  ON g.game_id = l.event_id "
        "WHERE g.home IN (?, ?) AND g.away IN (?, ?) "
        "AND g.date > date('now') AND l.over_under IS NOT NULL "
        "ORDER BY l.read_on DESC LIMIT 1",
        (clubs[0], clubs[1], clubs[0], clubs[1])).fetchone()
    return got[0] if got else None


def his_line(db, who, market):
    """The number a man's own prop is set at, from whichever book has it."""
    if not who or not market:
        return None
    like = "%" + str(market).replace("Touchdown Passes Thrown",
                                     "Passing Touchdowns") + "%"
    for sql, args in (
        ("SELECT points FROM dk_prop WHERE player = ? AND market_kind LIKE ? "
         "AND points IS NOT NULL AND points <> '' "
         "ORDER BY read_on DESC LIMIT 1", (who, like)),
        ("SELECT said FROM score_prop WHERE player = ? AND market LIKE ? "
         "AND said LIKE '%%.%%' ORDER BY read_on DESC LIMIT 1", (who, like)),
        ("SELECT line FROM espn_prop WHERE player = ? AND prop LIKE ? "
         "AND line IS NOT NULL ORDER BY read_on DESC LIMIT 1", (who, like)),
    ):
        got = db.execute(sql, args).fetchone()
        if got and got[0]:
            held = re.search(r"(\d+(?:\.\d+)?)", str(got[0]))
            if held:
                return held.group(1)
    return None


def spread_on(db, fixture, side):
    """The number a club is given or laying, written from that club's side.

       ESPN says it one way — "SEA -3.5" — and it is turned about for
       whichever club the leg is about.
    """
    parts = re.split(r"\s+(?:@|vs\.?)\s+", str(fixture or ""))
    if len(parts) != 2 or not side:
        return None

    clubs = []
    for part in parts:
        got = db.execute(
            "SELECT club FROM club_look WHERE lower(name) = ? OR club = ? "
            "LIMIT 1", (part.strip().lower(), part.strip())).fetchone()
        if got:
            clubs.append(got[0])
    if len(clubs) != 2:
        return None

    got = db.execute(
        "SELECT l.details FROM espn_line l JOIN league_game g "
        "  ON g.game_id = l.event_id "
        "WHERE g.home IN (?, ?) AND g.away IN (?, ?) AND g.date > date('now') "
        "AND l.details IS NOT NULL ORDER BY l.read_on DESC LIMIT 1",
        (clubs[0], clubs[1], clubs[0], clubs[1])).fetchone()
    if not got or not got[0]:
        return None

    held = re.match(r"\s*([A-Z]{2,3})\s*([+-]\d+(?:\.\d+)?)", got[0])
    if not held:
        return None
    named, edge = held.group(1), float(held.group(2))

    # Whose side is the leg on? The club named in it.
    mine = next((one for one in clubs
                 if one.lower() in str(side).lower()
                 or str(side).lower().startswith(one.lower())), None)
    if not mine:
        return None
    return "%+g" % (edge if mine == named else -edge)


# A board heading, in the words a reader sees.
#
# Some are the set's own name — "Division Dominator", "End Zone Kings" — and
# those stand as they are. Some are the market every leg is in, and those say
# what the card is about better than anything we could invent: a set of four
# touchdown scorers should read as touchdown scorers. Moneyline becomes Win,
# the way it does everywhere else.
#
# The rest are furniture. "Featured" and "Matchups" name nothing, and a card
# under them is named the way ours are.
AS_A_NAME = {
    "moneyline": "Win",
    "spread": "Spread",
    "total points": "Total Points",
    "touchdown scorer": "TD Scorers",
    "first touchdown": "First TD",
    "to score 2+ tds": "Two TD Scorers",
}

NOT_A_NAME = re.compile(r"^(featured|matchups|player|team|all|sgp)$", re.I)


def hub_name(heading):
    """A narrative set's name, where the heading is one."""
    said = (heading or "").strip()
    if not said or NOT_A_NAME.match(said):
        return None
    if said.lower() in AS_A_NAME:
        return AS_A_NAME[said.lower()]
    # "New England Patriots  Seattle Seahawks" is a fixture, not a name.
    if " @ " in said or re.search(r"\b(49ers|Bills|Ravens|Colts|Eagles|Rams|"
                                  r"Lions|Vikings|Chargers|Chiefs|Titans|"
                                  r"Steelers|Bengals|Panthers|Jaguars|Raiders|"
                                  r"Giants|Commanders|Seahawks|Patriots|"
                                  r"Cowboys|Saints|Texans|Broncos|Packers|"
                                  r"Dolphins|Jets|Browns|Buccaneers|Bears|"
                                  r"Cardinals|Falcons)\b.*\b(49ers|Bills|"
                                  r"Ravens|Colts|Eagles|Rams|Lions|Vikings|"
                                  r"Chargers|Chiefs|Titans|Steelers|Bengals|"
                                  r"Panthers|Jaguars|Raiders|Giants|"
                                  r"Commanders|Seahawks|Patriots|Cowboys|"
                                  r"Saints|Texans|Broncos|Packers|Dolphins|"
                                  r"Jets|Browns|Buccaneers|Bears|Cardinals|"
                                  r"Falcons)\b", said):
        return None
    return said


def numbered(heading, counted):
    """A set's name, and which of that set this one is."""
    said = hub_name(heading)
    if not said:
        return None
    counted[said] = counted.get(said, 0) + 1
    return "%s %d" % (said, counted[said])


def genius_cards(db, teams):
    """The hub's own boards: its team sets, its named narrative parlays, and
       the graded matchups.

       These are the only cards anywhere that carry their reasoning — "A+ ·
       Touchdown Scorer Allowed by WAS to TE" — and the reason is worth more
       than the pick, because it states a rule we can compute for anybody.
       It is kept on the leg and shown under it.
    """
    got = db.execute("SELECT MAX(read_on) FROM parlay").fetchone()
    latest = got[0] if got else None
    if not latest:
        return []

    # The tab is part of what a card is. All, Player and Team are three
    # boards under one heading — "Featured" is a different set of legs on
    # each — so a card keyed by heading alone kept one of the three and threw
    # the other two away.
    #
    # But they are not all different. Player and Team hand back the same
    # narrative and same-game cards as each other, leg for leg; only All
    # answers differently, and it is the one carrying Division Dominator and
    # Slump Busters. Keeping every tab put End Zone Kings on the shelf twice,
    # so the same legs under the same heading are read once, All first.
    #
    # A book collapsing its own repeat is not the same thing as collapsing
    # two books into one: two books publishing the same selections stay two
    # cards, each with its own name and its own price.
    out, already, counted = [], set(), {}
    for row in db.execute("SELECT board, filter, heading, fixture, blurb, "
                          "payout, legs FROM parlay WHERE read_on = ? "
                          "ORDER BY CASE filter WHEN 'all' THEN 0 ELSE 1 END",
                          (latest,)):
        # Keyed on the game, not on the legs.
        #
        # The five tabs are read seconds apart and the board moves under
        # them: the same set on the same matchup came back with forty-three
        # legs on one tab, forty-four on the next and forty-five on the
        # third, so keying on the legs kept three copies of one card. The
        # set and the game are what a card is; a leg added between two
        # requests is not a different card.
        same = (row["board"], row["heading"], row["fixture"])
        if same in already:
            continue
        already.add(same)
        try:
            held = json.loads(row["legs"] or "[]")
        except ValueError:
            continue
        if not held:
            continue

        legs, kept_raw = [], []
        for leg in held:
            side = leg.get("side")
            market = leg.get("market")

            # A total, a spread and a moneyline each need the number the hub
            # leaves off. It is on the fixture, and without it the leg says
            # "Under Total Points" and the bar has nothing to fill towards.
            if market in ("Total Points", "Total") and side and \
                    not re.search(r"\d", str(side)):
                mark = total_on(db, leg.get("fixture"))
                if mark:
                    side = "%s %s" % (side, mark)

            elif (market in ("Rushing Yards", "Passing Yards",
                             "Receiving Yards", "Receptions",
                             "Touchdown Passes Thrown")
                  and side and not re.search(r"\d", str(side))):
                # A graded matchup names the man and the stat and leaves the
                # number on the betslip button, which we do not read. It is
                # his own line, and a book has it. Without it the leg says
                # "Kyren Williams · Rushing Yards" and asks nothing.
                #
                # `side` already carries the direction — "Matthew Stafford
                # Over", "Josh Allen Under" — and that whole phrase used to
                # be asked for as a man's name, which matches nobody on any
                # roster. The line was never found for any leg shaped this
                # way; his own name is what the roster actually holds.
                just_him = re.sub(r"\s+(?:Over|Under)\s*$", "", side,
                                  flags=re.I).strip()
                mark = his_line(db, just_him, market)
                if mark:
                    # And this bolted the word "Over" on regardless of what
                    # `side` already said, so a real Under would have read
                    # "Josh Allen Under Over 1.5" the moment a line was ever
                    # found. The direction `side` already carries is kept.
                    side = "%s %s" % (side, mark)

            elif market == "Spread" and side and \
                    not re.search(r"\d", str(side)):
                mark = spread_on(db, leg.get("fixture"), side)
                if mark:
                    side = "%s %s" % (side, mark)

            said = " ".join(one for one in (side, market)
                            if one and str(one).strip())
            # `side` and `market` kept apart, not pre-joined into one blob.
            # read_leg is built to tell a name from a stat by which of its
            # two fields the direction word sits in; handed one flattened
            # string instead, it had to guess, and "Josh Allen Under 1.5"
            # left "Under" clinging to his name with nothing to strip it —
            # "Jacoby Brissett Passes Thrown" for the same reason.
            read = read_leg(side, market)
            # A stat with no number asks nothing. The hub leaves the figure
            # on a betslip button we do not read and no book has posted that
            # man's line yet, so the leg waits until one does rather than
            # standing on a card saying "Matthew Stafford · PYD" and nothing
            # else. The rest of the card is still worth showing.
            if not read.get("figure"):
                continue

            legs.append(dict(read, said=said, market=leg.get("market"),
                             # The reason it is on the card, and the letter
                             # the hub gave it.
                             why=leg.get("reason"), grade=leg.get("grade")))
            kept_raw.append(leg)

        # A game named on the leg, when the card holds more than one.
        #
        # "Texans Business" named Seattle, Houston and Kyren Williams, and
        # underneath them a bare "Total Points" — nothing said it was Dallas
        # at New York, the fourth game riding along on the same card, and a
        # reader had no way to know. theScore's own lounge already tags a
        # leg this way — "Touchdowns Scored (NE @ SEA)" — for exactly this
        # reason; done here too. Only a whole-game line needs it: a Win or
        # a Spread leg already names its own club and tagging it as well
        # said the same game twice — "SEA Seahawks (NE @ SEA)".
        games = {short_fixture(one.get("fixture")) for one in kept_raw
                if one.get("fixture")}
        if len(games) > 1:
            for entry, raw in zip(legs, kept_raw):
                if entry.get("kind") not in ("Total Points", "Total Yards"):
                    continue
                where = short_fixture(raw.get("fixture"))
                if where:
                    entry["says"] = "%s (%s)" % (entry["says"], where)

        # Every club actually on the card, not only the ones a leg's own
        # words happen to name. A bare "Total Points" leg names nobody —
        # that is the whole reason it needed the tag above — and the club
        # detection downstream reads leg text, so Dallas and New York never
        # reached it and a four-game card counted as three.
        clubs_hint = set()
        for one in kept_raw:
            clubs_hint.update(sides_in(one.get("fixture"), teams))

        named = next((leg.get("fixture") for leg in held if leg.get("fixture")),
                     None)
        # The set's own price, out of the legs that are actually on it —
        # `kept_raw`, not `held`, so a leg dropped for having no figure is
        # not still being charged for.
        whole = parlayed([one.get("odds") for one in kept_raw])
        out.append({
            "id": "hub-%s-%s-%s" % (row["board"], row["filter"] or "x",
                                    re.sub(r"\W+", "", row["heading"] or "")[:18]),
            "source": "genius",
            # The hub names its narrative sets and the names are good ones —
            # "Division Dominator", "Slump Busters", "End Zone Kings". They
            # were being thrown away and the card renamed from our own pool,
            # which is for cards nobody named. A heading that is a fixture or
            # a bare market — "Moneyline", "Total Points", "Matchups" — is a
            # label rather than a name and still goes to pick_title.
            # A set that is one card per matchup keeps its name and is
            # numbered. On the hub the title sits once above the matchups; on
            # a flat shelf that is twenty-nine cards called One Two Punch.
            #
            # Numbered rather than named for the game, because the game the
            # hub writes over a group is not to be trusted: "Swift Lions"
            # carries CHI @ CAR over Jahmyr Gibbs, Derrick Henry, the Rams
            # and D'Andre Swift — four different games — and every man in it
            # wears a Bears crest. The legs are right; the heading above them
            # is not. Nothing here reads a crest, and the fixture used is the
            # one on each leg's own button.
            # The same-game board heads every card MATCHUPS with the game
            # written under it, and the heading we hold is that game — so
            # the card is named for it rather than numbered, which is what a
            # reader would call it: "Matchup WAS @ PHI".
            "title": ("Matchup " + short_fixture(row["heading"])
                      if row["board"] == "same-game" and row["heading"]
                      else numbered(row["heading"], counted)),
            "header": None, "markets": None,
            "chance": likely(whole),
            "price": whole,
            "fixture": short_fixture(named), "starts": next(
                (leg.get("kickoff") for leg in held if leg.get("kickoff")), None),
            "event": next((leg.get("event_id") for leg in held
                           if leg.get("event_id")), None),
            "board_from": row["board"], "blurb": row["blurb"],
            "legs": legs, "clubs_hint": sorted(clubs_hint),
        })
    return out


def named_quietly(said):
    """A card's own name for itself, in ours.

       A book names its cards after its own machinery, and that naming was
       going out in the file — "FeaturedBetParlayCard", "MarketSelection", and
       the id of the row it sits in over there. It is replaced by a hash of
       itself: the same card gets the same name every run, so a bell turned on
       yesterday still finds it, and the name says nothing about where it came
       from.

       Ours keep theirs. "spy-" and "hub-" are our own words for our own
       cards and give nothing away.
    """
    said = str(said or "")
    if said.startswith(("spy-", "board-")):
        return said
    return "c" + hashlib.sha1(("qbspy:" + said).encode("utf-8")).hexdigest()[:14]


def spy_cards(db):
    """The Featured shelf, chosen by featured.py from what our own games say.

       It arrives in the same raw shape a book's card does — a fixture and
       legs in the words they were asked in — so it is built by the same
       pipeline as everything else and comes out with the same tracker, the
       same faces and a title of its own. featured.py picks which; nothing
       about how a card looks is decided there.
    """
    if not os.path.exists("data/featured.json"):
        return []

    with open("data/featured.json") as handle:
        shelf = json.load(handle)

    out = []
    for one in shelf:
        out.append({
            "id": one["id"], "title": None,
            # A card put at the head of the shelf by hand. featured.json is a
            # record as much as an output, and this is the one thing it can
            # say about order.
            "pin": bool(one.get("pin")),
            "header": None, "markets": None,
            # Ours are not priced and never will be. They rank on the record.
            "chance": one.get("rate"),
            "fixture": short_fixture(one["fixture"]), "starts": one.get("starts"),
            "event": one.get("event"),
            "featured": one.get("featured", True),
            "lane": one["lane"], "from": one.get("from"),
            "held": one.get("held"), "looked": one.get("looked"),
            "rate": one.get("rate"), "lift": one.get("lift"),
            "legs": [dict(read_leg(leg.get("said"), leg.get("market")), **leg)
                     for leg in one["legs"]],
        })
    return out


def sides_in(fixture, teams):
    """The two clubs a fixture is between, by their own names in it.

       Abbreviations count. A card's fixture is shortened to "ARI @ LAC"
       before it reaches the naming, and keys shorter than four letters were
       skipped here — so this answered nothing at all for every card, and the
       two clubs are what settle a written name against the men who were
       actually on the field. Fourteen Arizona cards named Brissett, McBride
       and Allgeier and came out naming nobody: two men answer to "McBride"
       and with no sides to choose between them, neither was taken.

       Longest first still, so "los angeles rams" is not read as "la".
    """
    said = " %s " % re.sub(r"[^a-z0-9]+", " ", (fixture or "").lower())
    out = []
    for key in sorted(teams, key=len, reverse=True):
        abbr = teams[key]["abbr"]
        if abbr in out:
            continue
        flat = re.sub(r"[^a-z0-9]+", " ", key.lower()).strip()
        if not flat:
            continue
        if len(flat) > 3:
            if flat in said:
                out.append(abbr)
        elif (" %s " % flat) in said:
            # Three letters or fewer only where the fixture says exactly
            # that word — "ne" must not be found inside "new orleans".
            out.append(abbr)
    return out[:2]


def kickoffs(db):
    """When each pair of clubs next meet.

       theScore stamps its cards with a kickoff; DraftKings does not, giving
       only "DEN Broncos @ KC Chiefs". The two clubs are enough to find the
       fixture in our own schedule, which is what lets every card sort by week
       whichever book it came from.

       Only the regular season counts as a fixture to stamp. A card stamped
       with a preseason kickoff would sort into a week it has nothing to do
       with, and the whole point of the stamp is the week.

       Every meeting is kept as well as the next one, so a card for a game
       that has already been played can be told from a card whose clubs we
       simply do not carry.
    """
    today = time.strftime("%Y-%m-%d")
    found, ever = {}, set()
    for row in db.execute("SELECT date, away, home, kind FROM league_game "
                          "ORDER BY date"):
        both = frozenset((row["away"], row["home"]))
        ever.add(both)
        if row["kind"] == "regular" and row["date"] >= today:
            found.setdefault(both, row["date"])

    def pair(abbrs):
        for one in abbrs:
            for two in abbrs:
                if one != two and frozenset((one, two)) in found:
                    return found[frozenset((one, two))]
        return None

    def asked(fixture):
        sides = re.findall(r"\b([A-Z]{2,3})\b", fixture or "")
        for one in sides:
            for two in sides:
                if one != two:
                    hit = found.get(frozenset((one, two)))
                    if hit:
                        return hit
        return None

    def gone(abbrs, fixture=None):
        """These clubs have met, and are not due to meet again.

           The fixture is read as well as the clubs, because a card naming
           one club in its legs — "Tony Pollard, first-drive rushing
           touchdown" — still says SEA @ TEN across the top of it, and it is
           the pair that settles whether the game has been played."""
        said = list(abbrs or [])
        said += re.findall(r"\b([A-Z]{2,3})\b", fixture or "")
        met = False
        for one in said:
            for two in said:
                if one == two:
                    continue
                both = frozenset((one, two))
                if both in found:
                    return False
                if both in ever:
                    met = True
        return met

    def club(abbr):
        """When this club next plays, whoever it is against."""
        best = None
        for both, day in found.items():
            if abbr in both and (best is None or day < best):
                best = day
        return best

    # Each club's own next real game, soonest first — so a card can be asked
    # how many different games it actually names.
    soonest = {}
    for both, day in found.items():
        for abbr in both:
            if abbr not in soonest or day < soonest[abbr][1]:
                soonest[abbr] = (both, day)

    def games_of(abbrs):
        """The distinct real games these clubs are playing.

           DraftKings and FanDuel file a card that spans several games under
           whichever single one it happened to be attached to — the fixture
           field says "NE @ SEA" for a four-way moneyline parlay with no
           Patriots leg on it anywhere. Each club is looked up against its
           own real opponent here, not against the others named on the
           card, which is what tells a genuine two-club game from a card
           that only looks like one because a book had to put it somewhere.
        """
        seen = set()
        for abbr in abbrs or []:
            got = soonest.get(abbr)
            if got:
                seen.add(got[0])
        return seen

    asked.pair = pair
    asked.gone = gone
    asked.club = club
    asked.games_of = games_of
    return asked


def dk_cards(db, men, teams, when):
    """DraftKings' cards, newest reading of each, and only the ones whose
       legs were actually read — a card with hollow legs says nothing."""
    out = []
    seen = set()

    for row in db.execute("""
            SELECT card_id, title, subtitle, odds, fixture, event_id, legs, read_on
              FROM dk_card
             WHERE league = 'nfl' AND legs != '[]'
               AND legs NOT LIKE '%"said":null%'
             ORDER BY read_on DESC, fixture"""):
        try:
            legs = json.loads(row["legs"])
        except ValueError:
            continue

        # Folded on the legs, which are what a card actually is.
        #
        # Not on the title: DraftKings writes one name across a whole week,
        # so "Score & Soar" is sixteen different cards, one per game, each
        # with its own legs and its own price. Folding on the name kept one
        # of the sixteen — 32 cards reached the shelf out of week 1's 77, and
        # 181 out of the 1,870 ever read.
        #
        # And not on the card_id either: they re-issue one every time they
        # refresh a card, so folding on the id shipped the same card once per
        # reading — "Score & Soar" came out 272 times.
        #
        # The legs settle both, and the third case as well: a card whose legs
        # span several games is filed under each of them, so "Always Open" —
        # seven receivers in seven games — arrives seven times. Same legs, so
        # it is kept once.
        mark = tuple(sorted(str(one.get("said") or "") for one in legs))
        if mark in seen:
            continue
        # And one name per game, newest reading. The legs above catch a
        # re-issued id and a card filed under several games, but not a card
        # re-priced between sweeps: "Score & Soar" on ATL @ PIT came back at
        # +350 and +315 with the total moved, which is one card twice, not
        # two cards. Read newest first, so the first seen is the current one.
        named = (row["title"], row["fixture"])
        if named in seen:
            continue
        seen.add(mark)
        seen.add(named)

        out.append({
            "id": row["card_id"], "source": "dk", "title": row["title"],
            "header": None, "markets": None,
            "chance": likely(row["odds"]), "price": priced(row["odds"]),
            "fixture": short_fixture(row["fixture"]),
            "starts": when(row["fixture"]),
            "event": row["event_id"],
            "legs": [dict(read_leg(one.get("said"), one.get("club_said")),
                          said=one.get("said"),
                          market=one.get("club_said")) for one in legs
                     if one.get("said")],
        })

    # ---- One name, sixteen cards ----
    #
    # DraftKings writes a name across a whole week: "Score & Soar" is one
    # card per game, sixteen of them, each with its own legs and its own
    # price. They are all kept, so the name has to tell them apart — the
    # earliest kickoff is 1, the way the hub's own sets are numbered.
    #
    # A name used once is left exactly as the book wrote it. Numbering a
    # card that has no sibling would put a "1" on it for no reason.
    over = {}
    for card in out:
        over[card["title"]] = over.get(card["title"], 0) + 1

    counted = {}
    for card in sorted(out, key=lambda one: (str(one.get("starts") or ""),
                                             str(one.get("fixture") or ""))):
        if over.get(card["title"], 0) < 2:
            continue
        counted[card["title"]] = counted.get(card["title"], 0) + 1
        card["title"] = "%s %d" % (card["title"], counted[card["title"]])

    return out


def club_slug(teams, abbr):
    """"SF" as league_player writes it — "san-francisco-49ers"."""
    for team in (teams or {}).values() if isinstance(teams, dict) else (teams or []):
        if isinstance(team, dict) and team.get("abbr") == abbr:
            return re.sub(r"[^a-z0-9]+", "-",
                          str(team.get("name", "")).lower()).strip("-")
    return None


_INITIALLED = None


def by_initial(db):
    """Every man on a roster, under the initialled form a book writes him in.

       "C.McCaffrey" is not a name, it is a shape a name can take, and nine
       men on these rosters answer to "J.Jones". So this is keyed by the club
       as well: a card names two, and inside one game the shape is almost
       always the one man. Where it is not, nobody is named — a leg left
       unread is a leg somebody can look at, and the wrong man on a card is
       not."""
    global _INITIALLED
    if _INITIALLED is not None:
        return _INITIALLED

    out = {}
    for row in db.execute("SELECT name, club FROM league_player "
                          "WHERE name LIKE '% %'"):
        name, club = row["name"], row["club"]
        first, last = name.split(" ", 1)
        for shape in ("%s.%s" % (first[0], last.replace(" ", "")),
                      "%s.%s" % (first[0], last)):
            out.setdefault((shape.lower(), club), set()).add(name)

    _INITIALLED = out
    return out


def spelt_out(db, said, clubs):
    """A leg's words with the initialled name written in full, where the two
       clubs on the card settle who it is."""
    hold = re.match(r"^([A-Z][A-Za-z'\-]*\.[A-Za-z'\-\.]+)\s+(.*)$", said)
    if not hold:
        return said

    shape, rest = hold.group(1).lower(), hold.group(2)

    found = set()
    for club in clubs:
        found |= by_initial(db).get((shape, club), set())

    # One man, or nobody. Two is a conflict and is left as it was written.
    if len(found) != 1:
        return said

    return "%s %s" % (found.pop(), rest)


def fd_title(said):
    """A FanDuel name, or nothing.

       Guarded rather than trusted, because the reader spent weeks writing
       the fixture abbreviation into this field and those rows are still in
       the table. A name with " @ " in it is a fixture, not a name.
    """
    said = (said or "").strip()
    if not said or " @ " in said or " vs " in said.lower():
        return None
    return said


def _figure(line):
    """1.5 as "1.5", 40.0 as "40" — a whole number keeps no decimal."""
    try:
        said = float(line)
    except (TypeError, ValueError):
        return str(line)
    return ("%d" % said) if said == int(said) else ("%s" % said)


# What a book calls a market that settles at the end of the season rather
# than at the end of a game.
A_SEASON = re.compile(r"regular season|season total|\bfull season\b|"
                      r"to win the |\bmvp\b|super bowl|"
                      r"\bmost \w+ (?:yards|touchdowns|passes)\b", re.I)


def fanduel_cards(db, men, teams, when):
    """FanDuel's cards, newest reading of each.

       Their legs are written short and initialled — "J.Smith-Njigba 70+
       Yards" with "Alt Receiving Yds" beside it. The figure is in the words
       and the market is the long name of the stat, which is the two things a
       leg needs, so it reads the same way a book's own card does.

       "Alt" is the book's word for a line it moved off the main one. It says
       nothing to a reader and comes out, the way the rest of their clutter
       does."""
    out = []
    seen = set()

    for row in db.execute("""
            SELECT card_id, title, fixture, event_id, bets, odds, legs,
                   home, away, read_on
              FROM fd_card
             WHERE legs != '[]'
             ORDER BY read_on DESC"""):
        if row["card_id"] in seen:
            continue
        seen.add(row["card_id"])

        try:
            legs = json.loads(row["legs"])
        except ValueError:
            continue

        # The two clubs on this card, as league_player writes them, so an
        # initialled name can be settled against who was actually there.
        sides = [slug for slug in
                 (club_slug(teams, row["away"]), club_slug(teams, row["home"]))
                 if slug]

        said = []
        for one in legs:
            words = (one.get("said") or "").strip()
            market = re.sub(r"^\s*Alt\s+", "", one.get("market") or "").strip()
            # Their own shorthand. "Rushing Yds" is the same market as
            # "Rushing Yards" and nothing downstream knows the short form —
            # it read every one of them as a man with no stat beside him.
            market = re.sub(r"\bYds\b", "Yards", market)
            market = re.sub(r"\bTDs?\b", "Touchdowns", market)
            market = re.sub(r"\bRec\b", "Receiving", market, flags=re.I)
            # They write it as two words. Everything that reads a leg knows
            # "Anytime", and "Any Time" left the man's name welded to the
            # market — "Christian McCaffrey Any Time · TD".
            market = re.sub(r"\bAny\s+Time\b", "Anytime", market, flags=re.I)
            if not words:
                continue
            # A leg with no market beside it is the card's own team badge
            # repeated, not a leg — FanDuel puts both in the same list.
            if not market:
                continue

            # A season is not a game. FanDuel sells "1250+ Regular Season
            # Receiving Yards" and "30+ Regular Season Passing Touchdowns"
            # in among the week's cards, and read as week-one legs they put
            # a man on the shelf needing twelve hundred yards on a Sunday.
            # The book says which they are in its own words, so that is
            # what is read — not the size of the number, which would be us
            # deciding what is too big for a game.
            if A_SEASON.search(market) or A_SEASON.search(words or ""):
                continue

            # Their plain Over/Under legs put the direction in the words and
            # the number in the market beside them — "Baker Mayfield Over"
            # with 1.5 on the market. Read as words alone the leg has no
            # figure, and a leg with no figure was dropped; two of those on a
            # card left it under two legs and the card went too. Fifty-nine
            # of a hundred and sixty went that way, most of the parlay hub
            # among them. The reader has always stored the number as `line`
            # and nothing ever read it.
            if one.get("line") is not None:
                if re.search(r"\b(over|under)\s*$", words, flags=re.I):
                    words = "%s %s" % (words, _figure(one["line"]))

            # FanDuel splits a leg in two: "C.McCaffrey 60+ Yards" and, in
            # its own field, "Rushing Yds". Neither half says what the leg is
            # — "60+ Yards" could be rushing, receiving or passing — so they
            # are put back together before anything reads them. The bare unit
            # at the end of the first half is what the second half says at
            # length, so it is replaced rather than repeated.
            whole = re.sub(r"\s+(yards|yds|touchdowns?|tds?|receptions|"
                           r"completions|attempts|points)\s*$", "",
                           words, flags=re.I)
            whole = ("%s %s" % (whole, market)).strip()
            # A cross-game card has no fixture of its own, so `sides` is
            # empty and nothing settled — "J.Williams" went out unread on
            # every card that spans games, while the same leg on a one-game
            # card came out "Jameson Williams". But the leg knows its own
            # game: FanDuel writes a fixture on every leg. The leg's game
            # settles the leg; the card's only stands in where the leg is
            # silent.
            his_game = [slug for slug in
                        (club_slug(teams, abbr) for abbr in
                         sides_in(short_fixture(one.get("fixture") or ""),
                                  teams))
                        if slug] if one.get("fixture") else []
            whole = spelt_out(db, whole, his_game or sides)

            leg = dict(read_leg(whole, market), said=whole, market=market)

            # Their plain Over/Under markets say "C.McCaffrey Over" and keep
            # the number itself in the market attachment, which is not read
            # here. A leg with no figure gives the bar nothing to fill
            # towards and reads as half a sentence, so it is left out rather
            # than shown empty. Their Alt markets carry the number in the
            # words and are unaffected.
            if not leg.get("figure"):
                continue

            said.append(leg)

        # One leg is not a card.
        if len(said) < 2:
            continue

        if not said:
            continue

        out.append({
            "id": row["card_id"], "source": "fd",
            # Most of their cards have no name, and those are left unnamed
            # for pick_title to name the way it does ours. The few FanDuel
            # writes by hand do have one — "North Stars", "Balanced
            # Attacks" — and this said so in a comment while passing None
            # regardless, which threw every one of them away.
            "title": fd_title(row["title"]),
            "header": None, "markets": None,
            "chance": likely(row["odds"]), "price": priced(row["odds"]),
            "fixture": short_fixture(row["fixture"]),
            "starts": when(row["fixture"]),
            "event": row["event_id"],
            # The one thing no other book gives: how many people actually
            # took it, rather than what share of them did.
            "taken": row["bets"],
            "legs": said,
        })

    return out


# What a special is about, so it can be named and described without ever
# reading like a betting slip.
ABOUT = [
    (re.compile(r"pass(ing)?\s*(yards|yds)", re.I), "Passing Yards"),
    (re.compile(r"pass(ing)?\s*(touchdown|td)|throw[a-z]*\s+[^.]*touchdown", re.I),
     "Passing TDs"),
    (re.compile(r"rush(ing)?\s*(yards|yds)", re.I), "Rushing Yards"),
    (re.compile(r"rush(ing)?\s*(touchdown|td)|anytime\s+touchdown|"
                r"(first|last)\s+touchdown|touchdowns?\s+scored", re.I),
     "Rushing TDs"),
    (re.compile(r"receiving", re.I), "Receiving"),
    (re.compile(r"longest", re.I), "Longest Play"),
    (re.compile(r"moneyline|to win\b", re.I), "The Result"),
    # Points in the game — not any "over", which is on every line there is.
    (re.compile(r"total points|to go (over|under)", re.I), "Scoring"),
]


def about(text):
    """What the card is about, in our words rather than the book's.

       A card can ask two different things — his passing yards and whether he
       scores — and naming only the first is worse than naming neither. Every
       kind it touches is said, in the order they are listed above.
    """
    found = []
    for pattern, said in ABOUT:
        if pattern.search(text) and said not in found:
            found.append(said)

    return " \u00b7 ".join(found[:3]) if found else "Specials"


def rookies():
    """Who is in his first season."""
    data = open("data/data.js").read()
    out = {}
    for m in re.finditer(r'"id":\s*"(\d+)"[^{]*?"experience":\s*"([^"]+)"', data):
        out[m.group(1)] = m.group(2).lower().startswith("1st")
    return out


def form(db):
    """How a man has actually gone in the markets he is priced in, from the
       stats hub. A record of fifteen from twenty-one is the most quotable
       thing on a card and the book never prints it."""
    out = {}
    for row in db.execute("""
            SELECT player, market, hit, missed FROM genius_record
             WHERE hit IS NOT NULL AND missed IS NOT NULL"""):
        whole = row["hit"] + row["missed"]
        if whole < 5:
            continue
        held = out.setdefault(row["player"], [])
        held.append({"market": row["market"], "hit": row["hit"], "of": whole})
    return out


# "each of their last 10 games", "four of their last five", "six of eight"
STREAK = re.compile(r"each of (?:their|his) last (\d+|\w+)", re.I)
OUT_OF = re.compile(r"(\d+|\w+) of (?:their|his|the) last (\d+|\w+)", re.I)

WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
         "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
         "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15}

SPELT = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six",
         7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten", 11: "Eleven",
         12: "Twelve", 13: "Thirteen", 14: "Fourteen", 15: "Fifteen",
         16: "Sixteen", 17: "Seventeen", 18: "Eighteen", 19: "Nineteen",
         20: "Twenty", 21: "Twenty-One"}


def figure(word):
    word = str(word).lower()
    return int(word) if word.isdigit() else WORDS.get(word)


def club_facts(db):
    """The hub's sentences, filed under the club each one is about — the
       note names the club, so nothing has to be matched up by id."""
    out = {}
    for row in db.execute("SELECT DISTINCT said FROM genius_note"):
        said = row["said"]
        if len(said) > 130 or "Systems require" in said:
            continue
        for m in re.finditer(r"\b([A-Z][a-z]+(?:s|ers|ans|ohawks))\b", said):
            out.setdefault(m.group(1), []).append(said)
    return out


FUTURE = re.compile(r"season|playoff|super bowl|conference|division\b|"
                    r"\b(mvp|award|champion)", re.I)


def is_future(fixture):
    """A card hung on the whole year rather than a kickoff.

       Its "fixture" is a competition — "NFL 2026/27 Season", "NFL 2026/27 -
       Playoffs" — with no two clubs facing each other in it. QB Spy is about
       the next kickoff, so a future is read and kept but never shown.
    """
    said = fixture or ""
    return bool(FUTURE.search(said)) and " @ " not in said and " vs " not in said


# --- one wording for every leg, whichever book wrote it ----------------------
#
# The books do not agree with themselves, let alone each other. theScore says
# "Drake Maye To Record Over 249.5 Passing Yards"; DraftKings says "Cameron
# Ward to Throw TD Pass on 1st Offensive Drive"; a card leg says "1+" with
# "Cam Skattebo Touchdowns Scored" beside it. Three ways of saying one thing.
#
# Every one is read into the same two parts: the number, which is what the
# eye goes to, and a plain line under it saying whose and what. Nothing keeps
# the book's own filler — "To Record", "To Go", "Scorer" — and no betting word
# survives the trip: a moneyline is a club winning, and that is what it says.

TIDY = [
    (re.compile(r"\btouchdowns?\b", re.I), "TD"),
    (re.compile(r"\bpassing tds\b", re.I), "Passing TDs"),
]


def mark_of(text):
    """The exact number a leg is measured against, whichever way it is said."""
    for pattern in (r"\bover\s+(\d+(?:\.\d+)?)", r"\bunder\s+(\d+(?:\.\d+)?)",
                    r"\b(\d+(?:\.\d+)?)\+"):
        hit = re.search(pattern, text, re.I)
        if hit:
            return float(hit.group(1))
    if re.search(r"\bfirst\s+touchdown\b|touchdown|\btd\b", text, re.I):
        return 1.0
    return None


def whole(number):
    """159.5 is shown as 160 — nobody gains half a yard."""
    import math
    return int(math.ceil(number))


def figure_of(text):
    """The number the leg turns on, said the short way."""
    over = re.search(r"\bover\s+(\d+(?:\.\d+)?)", text, re.I)
    if over:
        return "%d+" % whole(float(over.group(1)))

    under = re.search(r"\bunder\s+(\d+(?:\.\d+)?)|\bU\s+(\d+(?:\.\d+)?)",
                      text, re.I)
    if under:
        return "U %s" % (under.group(1) or under.group(2))

    # A book writes an over three ways — "Over 44.5", "O 44.5", "44.5+" —
    # and they are one number.
    short = re.search(r"\bO\s+(\d+(?:\.\d+)?)", text)
    if short:
        return "%d+" % whole(float(short.group(1)))

    plus = re.search(r"\b(\d+(?:\.\d+)?)\+", text)
    if plus:
        return "%d+" % whole(float(plus.group(1)))

    if re.search(r"first\s+team\s+to\s+score", text, re.I):
        return "1ST"
    if re.search(r"make\s+playoffs", text, re.I):
        return "SZN"
    if re.search(r"\bfirst\s+touchdown\b|\b1st\s+td\b|\bfirst\s+td\b",
                 text, re.I):
        return "1st"
    # A touchdown leg is one or more, so it is said the way every other
    # number on a card is said. "TD" over "Puka Nacua · Anytime TD" says
    # touchdown twice and gives the bar nothing to fill towards.
    if re.search(r"touchdown|\btd\b", text, re.I):
        return "1+"
    edge = re.search(r"([+-]\d+(?:\.\d+)?)", text)
    if edge and re.search(r"spread", text, re.I):
        return edge.group(1)
    if re.search(r"moneyline|\bto win\b", text, re.I):
        return "WIN"
    return ""


# What a leg is really about, once the book's wording is taken off. A ball
# caught for a score is a ball thrown for one — the quarterback is the lead
# here, so a receiving line is read as his.
SAYS = [
    (re.compile(r"passing yards|throw .*yards", re.I), "Passing Yards"),
    # iSportGenius' own market name is "Touchdown Passes Thrown" — a count of
    # scoring passes, not a count of attempts. It contains the words "passes
    # thrown", which is also the wording for the Pass Attempts pattern further
    # down, and being checked first there classified every one of these as
    # Pass Attempts. Checked here, ahead of it, fixes the whole board.
    (re.compile(r"passing touchdowns|passing tds|throw .*td|"
                r"touchdown passes thrown|td passes thrown", re.I),
     "Passing TDs"),
    (re.compile(r"receiving touchdown", re.I), "Receiving TDs"),
    (re.compile(r"receiving yards", re.I), "Receiving Yards"),
    (re.compile(r"rushing yards", re.I), "Rushing Yards"),
    (re.compile(r"rushing touchdown|rushing td", re.I), "Rushing TDs"),
    (re.compile(r"first team to score", re.I), "First to Score"),
    (re.compile(r"first touchdown|\b1st\s+td\b|first\s+td\b", re.I),
     "First TD"),
    (re.compile(r"anytime.*touchdown|touchdowns? scored|anytime td|"
                r"touchdown\s+scorer|score\s+a\s+td", re.I), "Anytime TD"),
    # A count of them and nothing else. The hub writes "2+ Touchdowns" with
    # the man in the other field, and every pattern above wants a qualifier —
    # passing, receiving, anytime, scored — so it matched none of them and
    # the leg went out as "Kyren Williams 2+" with nothing saying of what.
    # Last of the touchdown patterns, so it cannot shadow the specific ones.
    (re.compile(r"\btouchdowns?\b", re.I), "TD"),
    # Catches must come before the loose ones below, or "Total Receptions"
    # is read as a game total and the man's name is dropped — "AJ Barner
    # Receptions · Total Points", which is three things and none of them
    # right.
    (re.compile(r"reception", re.I), "Receptions"),
    (re.compile(r"\bcarries\b|rush(ing)? attempts", re.I), "Carries"),
    (re.compile(r"\bcompletions?\b", re.I), "Completions"),
    (re.compile(r"\battempts?\b|passes\s+thrown", re.I), "Pass Attempts"),
    (re.compile(r"interception|\bpicks?\b", re.I), "Interceptions"),
    (re.compile(r"\bsacks?\b", re.I), "Sacks"),
    (re.compile(r"total yards", re.I), "Total Yards"),
    (re.compile(r"total points|total\b|\bpoints\b", re.I), "Total Points"),
    (re.compile(r"\bspread\b|\bby\s+\d", re.I), "Spread"),
    (re.compile(r"make\s+playoffs|to\s+make\s+the\s+playoffs", re.I),
     "Playoffs"),
    (re.compile(r"moneyline|\bto win\b", re.I), "Win"),
    (re.compile(r"longest", re.I), "Passing Yards"),
]

# Everything the book puts in that says nothing. Struck out so what is left
# is a name, which is the only part of the wording worth keeping.
FILLER = re.compile(
    r"\b(?:to\s+(?:record|score|throw|be|go|have|win)|scorer|scored|scores|"
    r"an\s+anytime|a\s+receiving|a\s+rushing|the\s+first|anytime|first|"
    r"over|under|total|points|yards|moneyline|passing|receiving|rushing|"
    r"touchdowns?|tds?|td\s+pass|pass|"
    # The stat is already said in the line beneath the figure, so a name
    # that still carries it says it twice — "AJ Barner Receptions ·
    # Receptions".
    r"receptions?|carries|completions?|attempts?|interceptions?|picks?|"
    r"sacks?|team|to\s+score|scorer|spread|o/u|\balt\b|\bo\b|\bu\b|"
    r"make\s+playoffs)\b", re.I)


# Qualifiers the book adds that change what has to happen, and so must
# survive the tidying that strips everything else.
WHEN = [(re.compile(r"on\s+\d+(?:st|nd|rd|th)\s+offensive\s+drive", re.I),
         "1st Drive"),
        (re.compile(r"in\s+the\s+(1st|first)\s+quarter", re.I), "1st Qtr"),
        (re.compile(r"in\s+the\s+(1st|first)\s+half", re.I), "1st Half"),
        (re.compile(r"in\s+the\s+(2nd|second)\s+half", re.I), "2nd Half")]


def whose(text):
    """The name at the front of a leg, before the book starts describing."""
    said = re.sub(r"^\s*(over|under)\s+[\d.]+\s*", "", text, flags=re.I)
    cut = re.split(r"\s+(?:to|vs\.?|@|:)\s+", said, 1, flags=re.I)[0]
    # A figure can lead the sentence as well as end it — DraftKings writes
    # "87+ Jaxon Smith-Njigba Receiving Yards" — and only the trailing form
    # was stripped here. The leading "87" came off two lines down, but "+"
    # is not a digit and nothing else took it, so "+ Jaxon Smith-Njigba"
    # went out with the sign standing in for his first name.
    cut = re.sub(r"^\s*\d+(?:\.\d+)?\+\s*", "", cut)
    cut = re.sub(r"\s+\d+(?:\.\d+)?\+.*$", "", cut)
    # A spread's sign belongs to the number, not to the club beside it.
    # "Seattle Seahawks -3.5" lost only the digits here, since a sign is not
    # a digit either — "Seattle Seahawks -" went out with the minus left
    # standing in for the number that used to follow it.
    cut = re.sub(r"[+-]?\d+(?:\.\d+)?\b", "", cut)
    # A bare direction word left behind once its own number is gone — "Josh
    # Allen Under" with the "1.5" already stripped above — is not part of
    # anybody's name.
    cut = re.sub(r"\b(?:over|under)\b", "", cut, flags=re.I)
    cut = re.sub(r"\bon\s+\d+(?:st|nd|rd|th)\s+offensive\s+drive\b", "",
                 cut, flags=re.I)
    cut = FILLER.sub("", cut)
    cut = re.sub(r"\s{2,}", " ", cut).strip(" .,:+-")
    return cut


PASSERS = set()


def is_passer(who):
    """Is this man a quarterback? Filled once from the roster."""
    return bool(who) and who.strip() in PASSERS


EMOJI = re.compile(
    "[" "\U0001F000-\U0001FAFF" "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF" "\U00002190-\U000021FF"
    "\U0000FE00-\U0000FE0F" "\U00002B00-\U00002BFF" "]+")


def plain_title(said):
    """A title with the pictures taken out. The books put them in theirs —
       "Air Raid Showdown ✈️" — and ours are words."""
    return " ".join(EMOJI.sub("", said or "").split()).strip(" -–·")


_MEN_KNOWN = None


def known_man(said):
    """Is this a man we hold, however he is written.

       Out of `person_name`, which is the only thing allowed to say so. A
       spelling two men share still answers yes — the question here is
       whether this is a person at all, not which person.
    """
    global _MEN_KNOWN
    if not said:
        return False
    if _MEN_KNOWN is None:
        try:
            from store import open_db
            _MEN_KNOWN = {str(row["written"]).strip().lower()
                          for row in open_db().execute(
                              "SELECT written FROM person_name")}
        except Exception:
            _MEN_KNOWN = set()
    said = str(said).strip().lower()
    return said in _MEN_KNOWN or plain(said).strip().lower() in _MEN_KNOWN


def read_leg(said, market):
    """One leg, as the site says it: a figure, and a line under it.

       Returns the number large and the plain words beneath — "249.5+" over
       "Drake Maye · Passing Yards" — so a card reads the same whichever book
       it came from and whatever it is about.
    """
    said_whole = " ".join(one for one in (market, said)
                          if one and str(one).strip()).strip()
    if not said_whole:
        return {"figure": "", "says": "", "kind": "", "mark": None}

    kind = ""
    for pattern, name in SAYS:
        if pattern.search(said_whole):
            kind = name
            break

    figure = figure_of(said_whole)
    # The two books fill the two fields the other way round from each other.
    # theScore puts "1+" in one and "Cam Skattebo Touchdowns Scored" in the
    # other; DraftKings puts "Javonte Williams to Score a TD" in one and the
    # bare club in the other. Whichever field says what has to happen is the
    # field with the right name in it.
    doing = re.compile(r"\bto\s+(?:score|record|throw|be|go|win|make)\b|"
                       r"\b(?:over|under)\s+\d", re.I)
    first = said if doing.search(said or "") else market
    other = market if first is said else said
    # A name has letters in it. "250+ Total Passing Yards" came back as "+",
    # which is what put five Parlay Lounge cards on the site reading
    # "+ · PYD" where a man's name belongs — the lounge fills the two fields
    # the other way round again, the figure in the market and the man on his
    # own, and anything without a letter in it is not a man.
    def named(said):
        found = whose(said or "")
        return found if found and re.search(r"[A-Za-z]", found) else None

    # Which field holds the man is settled by asking whether what came out
    # of it is a man, not by which field it was.
    #
    # FanDuel writes "B.Bowers" in one field and "1000+ Regular Season
    # Receiving Yards" in the other. Read in field order the man comes out
    # as "Regular Season" — a phrase that is not a person and never was,
    # and it went to the site as one on card after card. The register knows
    # every spelling of every man including FanDuel's own, so it is asked,
    # and only where it cannot answer does the old field order stand.
    here, there = named(first), named(other)
    if there and known_man(there) and not known_man(here):
        who = there
    else:
        who = here or there

    # A whole-game line belongs to the game, not to either club in it.
    if kind in ("Total Points", "Total Yards") and re.search(r"\bvs\b|@", said_whole):
        who = ""

    if kind == "Win":
        who = whose(said if (said or "").strip() else market or "")
        return {"figure": "WIN", "says": plain(who).strip(), "kind": kind,
                "mark": None}

    # A qualifier goes on the end, where it reads as the condition it is.
    when = ""
    for pattern, name in WHEN:
        if pattern.search(said_whole):
            when = name
            break

    # A skill player's anytime touchdown is just a touchdown — the figure
    # already says which kind, 1+ against 1st, so "Anytime" repeats it. A
    # quarterback's does not: his own score can be run in or caught on a
    # trick play, and against his Passing TDs leg the word is what tells them
    # apart. So he keeps it and nobody else does.
    if kind == "Anytime TD":
        kind = "Anytime TD" if is_passer(who) else "TD"

    # The line beneath the figure is the only place a stat is ever shown —
    # the chips were dropped from the card and nothing renders them, so a
    # stat spelled out in full is a stat spelled out for nobody's benefit.
    # It is said here the short way the site says everything else.
    # A man is shown by his name, not his generation. "Sr" and "Jr" are how
    # a roster tells two men apart; a reader looking at one card needs
    # neither, and the register keeps the full form so nothing is lost.
    who = plain(who)

    says = " · ".join(one for one in (who, ON_A_LEG.get(kind, kind), when)
                      if one)
    return {"figure": figure, "says": says or said_whole, "kind": kind,
            "mark": mark_of(said_whole)}


# --- what a card is about, in the short forms a board uses -------------------
SHORT = {"Passing Yards": "PYD", "Passing TDs": "PTD",
         "Rushing Yards": "RYD", "Rushing TDs": "RTD",
         # A long play is passing yards, and a ball caught for a score is a
         # ball thrown for one — neither gets a box of its own.
         "Receiving": "REC YDS", "Longest Play": "PYD",
         "The Result": "WIN", "Scoring": "O/U", "Spread": "SPD"}


def priced(odds):
    """American odds, with the sign a reader needs to tell them apart.

       DraftKings, theScore and bet365 write the sign into the string —
       "+459". FanDuel's own field is a bare number, 459, and that number
       went out to the site unsigned — "459" beside a card that reads every
       other price with a plus in front of it, the one place a missing sign
       looks like a different kind of number rather than a positive one.
    """
    said = str(odds if odds is not None else "").strip()
    # DraftKings' main board writes a true minus sign, U+2212, not a hyphen
    # — thirteen thousand rows of it. Read as a character that is not a
    # sign, "−115" looked unsigned and had a plus put in front of it, and a
    # thousand legs went to the site reading "+−115". Both are the same
    # sign and only one of them is typeable, so it is made the typeable one
    # here, once, where every price already passes through.
    said = said.replace("\u2212", "-").replace("\u2013", "-")
    if not said:
        return None
    # "Even" is a hundred either way. It is a word on theScore's board and a
    # number everywhere else, and left as a word it fails every sum it is
    # put into — silently, because a price that will not parse is dropped
    # rather than complained about.
    if said.lower() in ("even", "evens", "ev"):
        return "+100"
    if said[0] in "+-":
        return said
    return "+" + said


def parlayed(prices):
    """Every leg's price multiplied out into the card's own.

       The hub prices each leg and does not price the set, so the card was
       being given the first leg's number — a four-leg set whose longest
       leg was +400 went out at -185, which is not merely wrong but
       impossible: a parlay can never be shorter than the shortest thing
       in it. Its own payout line agreed with the arithmetic and not with
       what we published — "$291.21" off a ten-dollar stake is +2813.

       Nothing back if any leg is unpriced. A price built from some of the
       legs is worse than the blank the shelf already knows how to show.
    """
    running = 1.0
    for said in prices:
        said = str(said or "").strip().replace("\u2212", "-").replace("+", "")
        if not said:
            return None
        if said.lower() in ("even", "evens", "ev"):
            said = "100"
        try:
            price = float(said)
        except ValueError:
            return None
        if price == 0:
            return None
        running *= (1 + price / 100.0) if price > 0 else (1 + 100.0 / -price)

    if running <= 1:
        return None
    out = ((running - 1) * 100) if running >= 2 else (-100 / (running - 1))
    return "%+d" % int(round(out))


def likely(odds):
    """How near a card is to happening, from the price it carries.

       A price is a book's own estimate of a chance, and it is the only read
       we have on whether a card is a near thing or a long shot. It stays in
       the database — what leaves is this, a share between nought and one,
       and only ever as an ordering. The number itself is never shown and
       never shipped; the site is handed a rank and sorts on that.
    """
    said = str(odds or "").strip().replace("+", "")
    if not said:
        return None
    try:
        price = float(said)
    except ValueError:
        return None

    if price == 0:
        return None
    if price > 0:
        return 100.0 / (price + 100.0)
    return -price / (-price + 100.0)


# Markets that are not what the site is about. A club scoring first, or
# making the playoffs in January, says nothing about how a quarterback plays
# on Sunday, and they read as clutter beside legs that do.
NOT_OURS = ("First to Score", "Playoffs")

SAME_THING = {"TD": "Anytime TD", "First TD": "Anytime TD"}

# How a stat is said on the line under the figure. Short, because that line is
# read at a glance beside a number, and because it is the only place the stat
# appears at all now the chips are gone.
ON_A_LEG = {
    "Passing Yards": "PYD", "Passing TDs": "PTD",
    "Rushing Yards": "RYD", "Rushing TDs": "RTD",
    "Receiving Yards": "REC YDS", "Receiving TDs": "REC TD",
    "Receptions": "REC", "Pass Attempts": "ATT", "Completions": "CMP",
    "Interceptions": "INT", "Sacks": "SACKS", "Carries": "CAR",
    # These already read as themselves and are left alone.
    "Anytime TD": "Anytime TD", "TD": "TD", "First TD": "First TD",
    "First to Score": "First to Score", "Total Points": "Total Points",
    "Total Yards": "Total Yards", "Win": "Win", "Spread": "Spread",
    "Playoffs": "Playoffs",
}


def from_legs(legs):
    """What a card is about and what boxes it wears, from its own read legs."""
    kinds = []
    for leg in legs:
        name = leg.get("kind")
        # A quarterback's anytime score and a receiver's touchdown are one
        # thing on the header, however differently each leg says it.
        if name and SAME_THING.get(name, name) not in \
                [SAME_THING.get(one, one) for one in kinds]:
            kinds.append(name)

    boxes = []
    for name in kinds:
        short = LEG_SHORT.get(name)
        if short and short not in boxes:
            boxes.append(short)

    return " \u00b7 ".join(kinds[:3]) or "Specials", boxes


# What each read leg is, in the short form a board uses. A long play and a
# ball caught for a score are the quarterback's throw, so neither gets a box
# of its own.
LEG_SHORT = {"Passing Yards": "PYD", "Passing TDs": "PTD",
             "Receptions": "REC", "Carries": "CAR", "Completions": "CMP",
             "Pass Attempts": "ATT", "Interceptions": "INT", "Sacks": "SCK",
             "Rushing Yards": "RYD", "Rushing TDs": "RTD",
             # A catch used to wear the quarterback's box, on the reasoning
             # that a ball caught is a ball thrown. It reads wrong on the
             # receiver's own card, so it says what it is — and REC is kept
             # for catches alone, since three catches and sixty yards are not
             # the same question.
             "Receiving Yards": "REC YDS", "Receiving TDs": "REC TD",
             # A quarterback's own score is one he ran in, so it wears the
             # rushing box. Anybody else could have caught it or carried it,
             # and the box cannot claim to know which — it says touchdown and
             # stops there.
             "Anytime TD": "RTD", "TD": "ATD", "First TD": "ATD",
             "First to Score": "1ST", "Playoffs": "SZN",
             "Total Points": "O/U", "Total Yards": "O/U", "Win": "WIN",
             "Spread": "SPD"}


def markets_in(text):
    """Every market the card touches, as a board would abbreviate it."""
    out = []
    for pattern, said in ABOUT:
        if pattern.search(text) and SHORT[said] not in out:
            out.append(SHORT[said])
    return out


# --- who a man is, where that touches this game -----------------------------
STATE = re.compile(r",\s*([A-Z]{2})\s*$")

# Where a programme plays, for the ones whose men keep turning up. Only the
# schools we are sure of — a homecoming claimed wrongly is worse than no
# title at all.
SCHOOL_STATE = {
    "alabama": "AL", "auburn": "AL", "arizona": "AZ", "arizona state": "AZ",
    "arkansas": "AR", "california": "CA", "ucla": "CA", "usc": "CA",
    "stanford": "CA", "san diego state": "CA", "fresno state": "CA",
    "colorado": "CO", "colorado state": "CO", "connecticut": "CT",
    "florida": "FL", "florida state": "FL", "miami": "FL", "ucf": "FL",
    "south florida": "FL", "georgia": "GA", "georgia tech": "GA",
    "boise state": "ID", "illinois": "IL", "northwestern": "IL",
    "indiana": "IN", "purdue": "IN", "notre dame": "IN", "iowa": "IA",
    "iowa state": "IA", "kansas": "KS", "kansas state": "KS",
    "kentucky": "KY", "louisville": "KY", "lsu": "LA", "tulane": "LA",
    "maryland": "MD", "boston college": "MA", "michigan": "MI",
    "michigan state": "MI", "minnesota": "MN", "mississippi": "MS",
    "ole miss": "MS", "mississippi state": "MS", "missouri": "MO",
    "nebraska": "NE", "nevada": "NV", "unlv": "NV", "rutgers": "NJ",
    "syracuse": "NY", "north carolina": "NC", "nc state": "NC",
    "duke": "NC", "wake forest": "NC", "north dakota state": "ND",
    "ohio state": "OH", "cincinnati": "OH", "toledo": "OH",
    "oklahoma": "OK", "oklahoma state": "OK", "oregon": "OR",
    "oregon state": "OR", "penn state": "PA", "pittsburgh": "PA",
    "clemson": "SC", "south carolina": "SC", "tennessee": "TN",
    "memphis": "TN", "vanderbilt": "TN", "texas": "TX", "texas a&m": "TX",
    "tcu": "TX", "baylor": "TX", "houston": "TX", "texas tech": "TX",
    "smu": "TX", "byu": "UT", "utah": "UT", "utah state": "UT",
    "virginia": "VA", "virginia tech": "VA", "washington": "WA",
    "washington state": "WA", "west virginia": "WV", "wisconsin": "WI",
    "wyoming": "WY",
}

REVENGE = ["Return To Sender", "Old Friends", "Familiar Faces", "Unfinished",
           "The Reunion", "Old Address", "Score To Settle", "Payback Visit",
           "Knows The Way", "Former Flame", "Old Haunt", "Circled In Red",
           "Ex Files", "Debt Collection"]

# The game is in the state he is from — true of a whole state, so nothing
# here may claim he grew up down the road.
HOME_STATE = ["Home State Homework", "Back On Home Soil", "Native Son",
              "Home Cooking", "Familiar Ground", "Roots Showing",
              "Close To Home", "Same State Business", "Known Country",
              "Home Air", "State He Knows", "Old Country"]

# The game is in the town he is from. Only then may it say so.
HOME_TOWN = ["Back Where It Started", "Hometown Return", "Local Boy",
             "Homecoming", "Where He Grew Up", "Own Backyard", "Home Streets",
             "Hometown Hero", "Back On His Block", "Where It Began"]

ALMA = ["Old Campus", "School Reunion", "Back To Class", "Old College Try",
        "Where He Learned It", "Campus Visit", "Homework Done", "Class Reunion",
        "Alma Mater", "Old Stomping Ground", "Back To School"]

DRAFTED = ["The One That Got Away", "Passed Over", "Draft Day Grudge",
           "Second Look", "They Had A Chance", "Wrong Call", "Buyers Remorse",
           "Regret Returns", "The Pick They Missed", "Sliding Doors"]

BIRTHDAY = ["Birthday Boy", "Many Happy Returns", "Cake And Candles",
            "Born For This", "Birthday Business", "Another Year On",
            "Party Of One", "Candles Out", "Birthday Bash", "His Day"]


def slugs():
    """"new-england-patriots" is how a season log names a club; NE is how the
       rest of the site does. One map between them, built from our own list."""
    data = open("data/data.js").read()
    out = {}
    for m in re.finditer(r'"abbr":\s*"(\w+)",\s*"name":\s*"([^"]+)"', data):
        out[m.group(2).lower().replace(" ", "-")] = m.group(1)
    return out


SLUGS = {}


def bios():
    """Who each man is, from the record we already hold — where he was born,
       when, where he went to school, who drafted him, and every club he has
       played for. Read once; a card asks it many times."""
    data = open("data/data.js").read()
    hit = re.search(r"var PLAYERS = (\[.*?\]);", data, re.S)
    if not hit:
        return {}

    out = {}
    for man in json.loads(hit.group(1)):
        past = set()
        for kind in (man.get("stats") or {}).values():
            for season in (kind or {}).get("seasons") or []:
                if season.get("team"):
                    past.add(season["team"])

        drafted = re.search(r"\(([A-Z]{2,3})\)", man.get("draft") or "")
        birth = STATE.search(man.get("birthplace") or "")
        when = (man.get("born") or "").split("/")

        out[str(man["id"])] = {
            "club": man.get("team"),
            "state": birth.group(1) if birth else None,
            "town": (man.get("birthplace") or "").split(",")[0].strip(),
            "school": (man.get("college") or "").strip().lower(),
            "drafted": drafted.group(1) if drafted else None,
            "past": past,
            "born": ("%02d-%02d" % (int(when[0]), int(when[1])))
                    if len(when) == 3 and when[0].isdigit() else None,
        }
    return out


def where(db):
    """Where and when each fixture is played, by the two clubs meeting."""
    today = time.strftime("%Y-%m-%d")
    found = {}
    for row in db.execute("SELECT date, away, home, venue, location "
                          "FROM league_game WHERE date >= ? ORDER BY date",
                          (today,)):
        found.setdefault(frozenset((row["away"], row["home"])),
                         {"date": row["date"], "venue": row["venue"],
                          "location": row["location"]})
    return found


def bio_ideas(who, sides, lives, spots):
    """What is true about this man that is also true about this game.

       A record of where somebody was born and what he did before is only
       worth a headline when it touches the fixture in front of him — facing
       the club that let him go, playing in the state he grew up in, or
       turning a year older on the day. Anything else is a fact, not a story,
       and the tier is skipped rather than forced.

       Never says the fact outright. The title alludes; the description and
       the page underneath it explain.
    """
    out = []
    if not who or len(sides) < 2:
        return out

    game = spots.get(frozenset(sides[:2]))

    for man in who[:2]:
        life = lives.get(str(man["id"]))
        if not life:
            continue

        other = [one for one in sides if one != life["club"]]

        # He has played for the club across from him.
        for slug in life["past"]:
            for abbr in other:
                club = SLUGS.get(slug)
                if club and club == abbr:
                    out.extend(REVENGE)
                    break

        # They drafted him and he plays elsewhere now.
        if life["drafted"] and life["drafted"] in other:
            out.extend(DRAFTED)

        if game:
            state = STATE.search(game["location"] or "")
            state = state.group(1) if state else None

            town = (game["location"] or "").split(",")[0].strip().lower()
            his = (life["town"] or "").lower()

            # The town he is from, which is a far stronger claim than a state
            # and so is only made when the two actually match.
            if town and his and town == his:
                out.extend(HOME_TOWN)

            # Otherwise only that the state is his.
            elif state and life["state"] and state == life["state"]:
                out.extend(HOME_STATE)

            # The game is in the state he played his college ball in.
            school = SCHOOL_STATE.get(life["school"])
            if state and school and school == state:
                out.extend(ALMA)

            # He turns a year older on the day.
            if life["born"] and game["date"][5:10] == life["born"]:
                out.extend(BIRTHDAY)

    return out


# A city's own words for itself. The back page never writes "Pittsburgh" when
# it can write Yinz, or "Minnesota" when it can write Skol — the club is named
# in the slang its own crowd uses, and that is most of the voice right there.
VOICE = {
    "ARI": ["Desert", "Big Red", "Cactus", "The Valley", "Red Sea"],
    "ATL": ["Dirty Birds", "The A", "Rise Up", "Peachtree", "ATL"],
    "BAL": ["Charm City", "The Flock", "Purple Reign", "Nevermore", "Ravens Roost"],
    "BUF": ["Mafia", "Orchard Park", "The Hammer", "Bills Mafia", "Snow Country"],
    "CAR": ["Keep Pounding", "Queen City", "Carolina Blue", "The Prowl"],
    "CHI": ["Chi-Town", "Windy City", "Monsters", "Soldier Field", "The Midway"],
    "CIN": ["The Jungle", "Who Dey", "Stripes", "Jungle Noise"],
    "CLE": ["Dawg Pound", "The Land", "Muni Lot", "Believeland"],
    "DAL": ["Big D", "The Star", "Americas Team", "Big Tex"],
    "DEN": ["Mile High", "Thin Air", "Broncos Country", "Rocky Mountain"],
    "DET": ["Motor City", "Motown", "One Pride", "Ford Field"],
    "GB":  ["Titletown", "Lambeau", "Cheesehead", "Frozen Tundra", "The Pack"],
    "HOU": ["H-Town", "Space City", "Bulls On Parade", "Battle Red"],
    "IND": ["Circle City", "The Horseshoe", "Naptown", "Indy"],
    "JAX": ["Duval", "Sacksonville", "Bold City", "Teal Town"],
    "KC":  ["Arrowhead", "Red Sea", "Chiefs Kingdom", "Barbecue", "Sea Of Red"],
    "LAC": ["Bolt Up", "The Bolts", "Powder Blue", "Southern Sun"],
    "LAR": ["Hollywood", "The Horns", "SoFi", "City Of Angels"],
    "LV":  ["Vegas", "Sin City", "Silver And Black", "Raider Nation", "The Strip"],
    "MIA": ["South Beach", "The 305", "The Tide", "Fins Up", "Ocean Drive"],
    "MIN": ["Minny", "Skol", "Purple", "The North", "Twin Cities"],
    "NE":  ["Foxborough", "The Pats", "New England", "Patriot Way"],
    "NO":  ["Who Dat", "The Bayou", "Big Easy", "Superdome", "Bourbon Street"],
    "NYG": ["Big Blue", "The Meadowlands", "MetLife", "Jersey"],
    "NYJ": ["Gang Green", "Florham Park", "Jets Nation", "Green Machine"],
    "PHI": ["Brotherly", "South Philly", "Broad Street", "The Birds"],
    "PIT": ["Yinz", "The Burgh", "Steel City", "Terrible", "Three Rivers"],
    "SEA": ["The Twelves", "Emerald City", "Rain City", "Pike Place", "Loud House"],
    "SF":  ["The Bay", "Gold Rush", "The Faithful", "Bay Area"],
    "TB":  ["Pirate Ship", "Siege The Day", "The Cannon", "The Krewe", "Bay Life"],
    "TEN": ["Titan Up", "Music City", "Nashville", "Two Tone Blue"],
    "WSH": ["The District", "Burgundy", "Capital", "DC"],
}

# Which of those are places rather than the club itself.
#
# A club's slang travels with it — the Pats are the Pats in Seattle. A town
# does not: "Foxborough Foot Race" was ten cards named for a stadium three
# thousand miles from the one the game is played in, which is the same fault
# as putting SoFi on a game at the MCG. So these only speak when their club
# is at home.
PLACES = {
    "Desert", "The Valley", "Peachtree", "Charm City", "Orchard Park",
    "Snow Country", "Queen City", "Chi-Town", "Windy City", "Soldier Field",
    "The Midway", "The Jungle", "Jungle Noise", "The Land", "Muni Lot",
    "Believeland", "Big D", "Big Tex", "Mile High", "Thin Air",
    "Rocky Mountain", "Motor City", "Motown", "Ford Field", "Titletown",
    "Lambeau", "Frozen Tundra", "H-Town", "Space City", "Circle City",
    "Naptown", "Indy", "Duval", "Sacksonville", "Bold City", "Teal Town",
    "Arrowhead", "Southern Sun", "Hollywood", "SoFi", "City Of Angels",
    "Vegas", "Sin City", "The Strip", "South Beach", "The 305",
    "Ocean Drive", "Minny", "Twin Cities", "The North", "Foxborough",
    "New England", "The Bayou", "Big Easy", "Superdome", "Bourbon Street",
    "The Meadowlands", "MetLife", "Jersey", "Florham Park", "South Philly",
    "Broad Street", "Yinz", "The Burgh", "Steel City", "Three Rivers",
    "Emerald City", "Rain City", "Pike Place", "Loud House", "The Bay",
    "Bay Area", "Bay Life", "Music City", "Nashville", "The District",
    "Capital", "DC",
}


def at_home(abbr, fixture):
    """Whether this club is the one hosting. "NE @ SEA" — the home side is
       the one after the at-sign."""
    parts = re.split(r"\s+@\s+", str(fixture or ""))
    return len(parts) == 2 and parts[1].strip().upper().startswith(abbr.upper())


# What the card feels like, never what it measures. The stat lives in the
# description; the title only says what kind of afternoon it would be.
MOOD = {
    "air": ["Heaves", "Airmail", "Air Raid", "Aerial Show", "Bombs Away",
            "Slinging", "Long Distance", "Deep Shots", "Sky Mail",
            "Letting It Rip", "Arm Day", "Skyline", "Overhead", "Wind Up",
            "Launch Party", "Flight Plan", "High And Deep", "Above It All",
            "Airing It Out", "Long Ball", "Sky Traffic"],
    "ptd": ["Six Pack", "Paydirt", "Cashing In", "Strikes", "Fireworks",
            "Scoring Spree", "Special Delivery", "Pay Window", "Front Door",
            "Ringing It Up", "Cash Register", "Sending It In", "Seven Points",
            "Signed And Delivered", "Money Down"],
    "rtd": ["Pounding", "Ground Game", "Punching In", "Bulldozing",
            "Short Yardage", "Muscle", "Nose First", "Goal Line Grind",
            "Hard Hats", "Downhill", "Body Blows", "Heavy Legs", "Inches",
            "Through The Middle", "Grinding", "Push Pile"],
    "ryd": ["Running Wild", "Scrambling", "On The Move", "Breakaway",
            "Loose Legs", "Open Field", "Out The Back", "Escape Act",
            "Foot Race", "Green Grass", "Track Meet", "Gone"],
    "win": ["Business", "Statement", "Handled", "Takeover", "Sunday Best",
            "Bragging Rights", "Getting It Done", "Last Word", "Order Restored",
            "House Money", "Closing Time", "Buttoned Up", "No Doubt",
            "Bossing It", "Sealed"],
    "any": ["Showtime", "Big Day", "The Works", "Sunday Special", "Full Menu",
            "Main Event", "Loud Day", "Full Send", "Prime Time", "Circled",
            "Marquee", "Everything At Once"],
    # Two clubs on the card: neither one's slang may claim it, so the card is
    # named for the argument between them instead.
    "duel": ["Trading Haymakers", "Answer For Answer", "Both Arms Live",
             "Nobody Blinks", "Trading Blows", "Punch For Punch",
             "Back And Forth", "No Letting Up", "Blow For Blow",
             "Neither Backing Down", "Point For Point", "Toe To Toe",
             "Last One Standing", "Shot For Shot", "Even Money Argument",
             "Nobody Gives", "Round For Round", "Both Sides Cooking"],
    # A card that wants the arm and the legs. Naming half of it is a lie.
    "mixed": ["Arm And Legs", "Every Which Way", "Both Ways", "Air And Ground",
              "Whole Toolbox", "Two Ways Home", "Nothing Off Limits",
              "All Of It", "Beats You Twice", "Full Repertoire",
              "Land And Air", "More Than One Way", "Whole Playbook",
              "Doing It All", "Every Angle", "Two Kinds Of Trouble",
              "Anything Goes", "The Complete Package"],
}

# Known phrases bent to fit — the other half of the back-page voice.
FLIPS = ["Business In %s", "Trouble In %s", "Made In %s", "Night In %s",
         "%s Calling", "%s Rising", "Welcome To %s", "Meet Me In %s",
         "%s Weather", "Straight Outta %s", "Nothing But %s"]

# What a man does, said the way a headline says it.
DOES = {
    "air": ["%s Goes Deep", "%s Winds Up", "%s Lets It Fly", "Arm Of %s",
            "%s Airmail", "Deep In %s"],
    "ptd": ["%s Delivers", "%s Cashes In", "%s Finds Paydirt", "%s Strikes"],
    "rtd": ["%s Punches In", "%s Barrels In", "%s Bulldozes", "%s Grinds It"],
    "ryd": ["%s Runs Wild", "%s Breaks Loose", "Legs Of %s", "%s On The Loose"],
    "win": ["%s Takes Over", "%s Says So", "Answer From %s", "%s Handles It"],
    "any": ["%s Weather", "%s Country", "%s Time", "%s Show", "All %s"],
    "mixed": ["%s Does It All", "Every Way %s", "%s Both Ways",
              "All Of %s", "%s Unbounded", "Two Ways With %s"],
    "duel": ["%s Answers", "%s Will Not Blink", "%s Trades Blows"],
}

PAIR = ["The %s %s Show", "%s And %s", "Two Man Job", "Double Trouble",
        "Tag Team", "Partners In Crime", "Twin Engines"]

# --- the parts every register is built from ---------------------------------
#
# A fixed list of titles runs out; a set of parts does not. Each register is
# given words that combine — a noun that can follow a city, a shape a city or
# a surname can be dropped into — so the number of names available is the
# product of the parts rather than the length of a list. Thirty-two clubs, a
# few hundred players and a dozen shapes apiece is thousands of titles, and
# every one still reads like a back page wrote it.

DUEL_NOUN = ["Standoff", "Shootout", "Slugfest", "Showdown", "Argument",
             "Duel", "Business", "Reckoning", "Grudge", "Traffic",
             "Racket", "Ruckus", "Noise", "Tussle", "Reunion", "Quarrel"]

# Only true after dark, so only offered then.
DUEL_NIGHT = ["Nightcap", "Fireworks", "Lights", "Prime Cut", "Late Show"]

DUEL_SHAPE = ["%s Standoff", "Shootout In %s", "Argument In %s",
              "Business In %s", "Nobody Blinks In %s",
              "Trouble In %s", "Meet Me In %s", "Loud In %s", "%s Or Bust",
              "Settled In %s", "%s Has Two", "Both Ways In %s",
              "%s Picks A Side", "Last Word In %s"]

DUEL_NIGHT_SHAPE = ["Night In %s", "Late In %s", "%s After Dark",
                    "Lights On In %s"]

MIXED_NOUN = ["Toolbox", "Repertoire", "Playbook", "Range", "Menu",
              "Arsenal", "Inventory", "Everything", "Options", "Angles",
              "Ways Home", "Kinds Of Trouble", "Bag Of Tricks"]

MIXED_SHAPE = ["%s Does It All", "Every Way %s", "%s Both Ways", "All Of %s",
               "Two Ways With %s", "%s Has Two", "No Stopping %s",
               "%s From Anywhere", "%s Everywhere", "Pick Your Poison With %s",
               "%s Leaves Nothing", "Whichever Way %s"]


def mixed_words(said, names):
    """Names for a card that wants the arm and the legs, built rather than
       listed — the club's own word in front of a noun that means range."""
    out = list(MOOD["mixed"])
    for slang in said:
        for noun in MIXED_NOUN:
            line = "%s %s" % (slang, noun)
            if 2 <= len(line.split()) <= 4:
                out.append(line)
    if len(names) == 1:
        for shape in MIXED_SHAPE:
            line = shape % names[0]
            if 2 <= len(line.split()) <= 4:
                out.append(line)
    return out


def duel_words(town, names, dark=False):
    """Names for a card spanning two clubs. The ground may be named — it
       belongs to neither side — but no club's slang may."""
    out = list(MOOD["duel"])
    if town:
        for noun in DUEL_NOUN + (DUEL_NIGHT if dark else []):
            line = "%s %s" % (town, noun)
            if 2 <= len(line.split()) <= 4:
                out.append(line)
        for shape in DUEL_SHAPE + (DUEL_NIGHT_SHAPE if dark else []):
            line = shape % town
            if 2 <= len(line.split()) <= 4:
                out.append(line)
    # Exactly two. "Stafford Or Maye" over four quarterbacks names two of
    # them and says the card is a choice between the pair, which is not what
    # a card of four men is. With more than two, the ground and the mood name
    # it instead.
    if len(names) == 2:
        for shape in ("%s Against %s", "%s Or %s", "%s Answers %s",
                      "The %s %s Argument", "Neither %s Nor %s"):
            line = shape % (names[0], names[1])
            if 2 <= len(line.split()) <= 4:
                out.append(line)
    if len(names) == 1:
        for shape in ("%s Will Not Blink", "%s Answers Back", "%s Says Otherwise",
                      "Over To %s", "%s Has A Reply"):
            line = shape % names[0]
            if 2 <= len(line.split()) <= 4:
                out.append(line)
    return out


def moods(kind):
    """Which registers this card can be spoken in, in the order it should try
       them — what it mostly is, first."""
    out = []
    if "Passing Yards" in kind:
        out.append("air")
    if "Passing TDs" in kind:
        out.append("ptd")
    if "Rushing TDs" in kind:
        out.append("rtd")
    if "Rushing Yards" in kind:
        out.append("ryd")
    if "The Result" in kind:
        out.append("win")
    out.append("any")
    return out


def ring(title):
    """How much the title sounds like itself.

       Saints Ain't, Raiders Ruckus, Charging Up — the back page reaches for
       the word that starts the same way, so the ones that do go first.
    """
    heads = [word[0].lower() for word in title.split()
             if word.lower() not in ("the", "in", "of", "and", "to", "a", "it")]
    return sum(1 for at in range(1, len(heads)) if heads[at] == heads[at - 1])


def sung(lot):
    """Best-sounding first, but never reordered across tiers — a club title
       still beats a player one, however it rings."""
    return [one for one in sorted(lot, key=lambda one: -ring(one))]


def turned(lot, by):
    """The same list, started from a different place. Sixteen games asking the
       same question in the same week otherwise all take the first answer."""
    if not lot or not by:
        return lot
    at = by % len(lot)
    return lot[at:] + lot[:at]


def title_ideas(text, men_named, clubs_named, kind, legs, young, records,
                facts, lives=None, spots=None, sides_of=None, seed=0,
                fixture=""):
    """Every name this card could carry, best first.

       Back-page copy, not a row of data. The stat is never in it — that is
       the description's job. The words are picked to ring off each other,
       and a surname only appears when the man is the story rather than one
       of the names on it.

       Which register applies is decided by what the card actually spans:

         two clubs      no single club's slang may claim it, so it is named
                        for the argument between them;
         two stat kinds naming the arm alone when the legs are on it too is
                        simply wrong, so it is named for the range;
         one of each    the city may speak in its own words.

       Above all of those sits whatever is true about the man that is also
       true about this game — the club that let him go, the state he is from,
       the day he was born. That is a headline; the rest is a description.

       A list is returned rather than an answer so the caller can take the
       first nobody has used, which is what keeps two hundred cards from
       sounding like a dozen.
    """
    who = list(men_named)[:3]
    names = [one["name"].split()[-1] for one in who]
    kinds = moods(kind)
    stats = [one for one in kinds if one != "any"]
    two_clubs = len(clubs_named) > 1

    # Whether he is asked to do it with his arm and with his legs — which is
    # what the mixed register is about. A moneyline is not a third way of
    # moving the ball, so it does not make a card mixed on its own.
    air = [one for one in stats if one in ("air", "ptd")]
    ground = [one for one in stats if one in ("rtd", "ryd")]
    two_kinds = bool(air) and bool(ground)

    out = []

    who = list(men_named)[:3]
    names = [one["name"].split()[-1] for one in who]
    kinds = moods(kind)
    stats = [one for one in kinds if one != "any"]
    two_clubs = len(clubs_named) > 1

    # Whether he is asked to do it with his arm and with his legs — which is
    # what the mixed register is about. A moneyline is not a third way of
    # moving the ball, so it does not make a card mixed on its own.
    air = [one for one in stats if one in ("air", "ptd")]
    ground = [one for one in stats if one in ("rtd", "ryd")]
    two_kinds = bool(air) and bool(ground)

    out = []

    # The rules first. They are the only tier that names a card from what is
    # on it rather than from a register — a surname that is also a word, a
    # collision the card itself proves, the shape of the legs — so where one
    # fires it is the best name available and nothing below needs asking.
    #
    # They fire on about one card in fifteen. The rest of this function is
    # what names the other fourteen.
    try:
        import title_rules
        for said in title_rules.every_name(
                {"legs": legs, "players": [
                    {"name": one["name"], "club": one.get("club"),
                     "spot": one.get("spot")}
                    for one in (men_named or []) + (clubs_named or [])
                    if one.get("name")],
                 "clubs": [one["abbr"] for one in clubs_named or []]},
                (spots or {}).get(
                    frozenset(one["abbr"] for one in (clubs_named or [])[:2]),
                    {}).get("location", "").split(",")[0].strip()):
            out.append(said)
    except Exception:
        # A rule that throws must not cost the card its name.
        pass


    # 1. Two clubs — the matchup register. Neither side's slang applies.
    if two_clubs:
        # The host city names the ground, not a side, so it is fair to use.
        game = (spots or {}).get(frozenset(one["abbr"] for one in clubs_named[:2]))
        town = (game or {}).get("location", "").split(",")[0].strip() if game else ""
        # After seven in the evening, local time, is a night game.
        hour = int(((game or {}).get("date") or "T00")[11:13] or 0)
        out.extend(turned(sung(duel_words(town, names,
                                          dark=hour >= 23 or hour < 8)), seed))

    # 2. Both the arm and the legs — name the range, not half of it.
    if two_kinds:
        said = VOICE.get(clubs_named[0]["abbr"], []) if clubs_named else []
        out.extend(sung(mixed_words(said if not two_clubs else [], names)))

    # 3. What is true about the man and about this game.
    out.extend(bio_ideas(who, sides_of or [], lives or {}, spots or {}))

    # 4. One club, one kind — the city speaks in its own words.
    if not two_clubs:
        for side in clubs_named[:1]:
            said = VOICE.get(side["abbr"], [side["short"]])
            # A town only speaks when its club is hosting.
            if not at_home(side["abbr"], fixture):
                said = [one for one in said if one not in PLACES] or \
                    [side["short"]]
            for mood in (["mixed"] if two_kinds else (stats or ["any"])):
                lot = []
                for slang in said:
                    for word in MOOD[mood]:
                        line = "%s %s" % (slang, word)
                        if 2 <= len(line.split()) <= 4:
                            lot.append(line)
                out.extend(sung(lot))

            lot = []
            for slang in said:
                for shape in FLIPS:
                    line = shape % slang
                    if 2 <= len(line.split()) <= 4:
                        lot.append(line)
            out.extend(sung(lot))

    # 5. The man, when he is the story rather than a name on it — which he
    #    is only when he is the one man on it.
    if len(names) == 1:
        for mood in (["mixed"] if two_kinds else kinds):
            for shape in DOES.get(mood, DOES["any"]):
                line = shape % names[0]
                if 2 <= len(line.split()) <= 4:
                    out.append(line)

    # A pair's names, only when there is a pair. Naming the first two of
    # four reads as though the other two were not on the card.
    if len(names) == 2:
        for shape in PAIR:
            line = shape % (names[0], names[1]) if shape.count("%s") == 2 else shape
            if 2 <= len(line.split()) <= 4:
                out.append(line)

    if len(names) >= 3:
        out.extend(["Three Deep", "Full House", "The Whole Crew"])

    # 6. Nothing else left: the mood, with the game in front of it.
    #
    # A mood is the back half of a shape and half of them are one word —
    # "Pounding", "Muscle", "Inches". Offered bare they went out as titles on
    # their own, nine cards named a single verb. The town or the club goes in
    # front, and the bare word is offered last so it is only reached when
    # every fuller form is already taken.
    bare = []
    for mood in (["duel"] if two_clubs else []) + (["mixed"] if two_kinds else []) + kinds:
        for word in MOOD[mood]:
            if len(word.split()) > 1:
                out.append(word)
            else:
                for one in (clubs_named or [])[:2]:
                    said = one.get("short") or one.get("abbr")
                    if said:
                        out.append("%s %s" % (said, word))
                bare.append(word)
    out.extend(bare)

    seen = set()
    return [one for one in out if one and not (one in seen or seen.add(one))]


# "Cam Ward & Geno Smith Each To Record Over 274.5 Passing Yards" — one
# sentence, two men, two legs.
EACH = re.compile(r"^(.+?)\s+&\s+(.+?)\s+Each\s+To\s+(.+)$", re.I)


def legs_of(text):
    """A special written as one sentence, cut back into the lines it is made
       of.

       The ampersand is the book's own join between legs — but it also joins
       two names inside one leg, as in "Kirk Cousins & Malik Willis Each To
       Throw Over 1.5 Passing Touchdowns". A piece that carries no verb is
       not a leg of its own; it belongs to the piece after it.
    """
    # "Cam Ward & Geno Smith Each To Record Over 274.5 Passing Yards" is two
    # men doing the same thing — two legs, not one sentence about a pair.
    both = EACH.match(text)
    if both:
        return ["%s To %s" % (both.group(1).strip(), both.group(3).strip()),
                "%s To %s" % (both.group(2).strip(), both.group(3).strip())]

    parts = [one.strip() for one in re.split(r"\s+&\s+", text) if one.strip()]

    out = []
    held = ""
    for part in parts:
        joined = (held + " & " + part).strip(" &") if held else part
        # A leg says what somebody does — "To Record", "To Score", "Each To".
        if re.search(r"\b(to|over|under|each)\b", part, re.I):
            out.append(joined)
            held = ""
        else:
            held = joined

    if held:
        if out:
            out[-1] = out[-1] + " & " + held
        else:
            out.append(held)

    return out or [text]


# What fits across a card without the end being cut off. "Foxborough Scoring
# Spree" is twenty-four and comes up as "FOXBOROUGH SCORING S…", which is not
# a name, it is half of one.
FITS = 20


# ---- A name has to be true of the card ----
#
# The ideas are good ones; they were simply free to land anywhere. "Land And
# Air" went on a card of passing yards and a receiver's touchdown — no ground
# anywhere on it — while the card of rushing yards and passing yards beside
# it was called "Both Sides Cooking". And "SoFi Six Pack" was two legs.
#
# So a name that claims something has to find it in the legs. Each rule is a
# word the title might use and the kinds of leg that make it true.
CLAIMS = [
    (re.compile(r"\b(ground|land|legs?|run|running|rush\w*|carry|carries|"
                r"scamper\w*|feet)\b", re.I),
     ("Rushing Yards", "Rushing TDs")),
    (re.compile(r"\b(air|arm|arms|heave\w*|throw\w*|pass\w*|deep|bomb\w*|"
                r"aerial)\b", re.I),
     ("Passing Yards", "Passing TDs", "Pass Attempts", "Completions")),
    (re.compile(r"\b(hands|catch\w*|receiv\w*|reception\w*|target\w*)\b", re.I),
     ("Receiving Yards", "Receiving TDs", "Receptions")),
    (re.compile(r"\b(six|sixes|tuddy|tuddies|touchdown\w*|endzone|scoring)\b", re.I),
     ("TD", "Anytime TD", "First TD", "Rushing TDs", "Passing TDs",
      "Receiving TDs")),
]

# A number in a name is a count of the legs, and it has to be the right one.
COUNTS = {"two": 2, "double": 2, "pair": 2, "duo": 2,
          "three": 3, "triple": 3, "treble": 3, "trio": 3,
          "four": 4, "quad": 4, "five": 5, "six": 6, "seven": 7}


# Words that say a thing happened a lot. On a card of unders they say the
# opposite of what is being asked: "Foxborough Foot Race" over two lines
# betting Drake Maye stays under twenty-six rushing yards.
LOUD = re.compile(
    r"\b(race|spree|shootout|fireworks|raid|slinging|heaves|airmail|"
    r"pounding|blitz|barrage|explosion|onslaught|surge|storm|feast|"
    r"parade|takeover|rampage|romp)\b", re.I)

QUIET = re.compile(r"\b(quiet|slow|grind|lock|shut|still|hold|clamp)\b", re.I)


def true_of(said, legs):
    """Whether a name says only what the card can back up."""
    legs = legs or []
    kinds = {str(leg.get("kind") or "") for leg in legs}

    # Which way the card is asking. An under is a card about something not
    # happening, and a word about it happening is not a smaller mistake than
    # naming the wrong stat.
    figs = [str(leg.get("figure") or "") for leg in legs]
    unders = [f for f in figs if f.startswith("U ")]
    if figs and len(unders) == len(figs):
        if LOUD.search(said):
            return False
    elif QUIET.search(said) and not unders:
        return False

    for word, many in COUNTS.items():
        if re.search(r"\b%s\b" % word, said, re.I) and len(legs or []) != many:
            return False

    # A kind is only claimed by a leg asking for it, not one asking against
    # it: a rushing under does not make "ground" true.
    over = {str(leg.get("kind") or "") for leg in legs
            if not str(leg.get("figure") or "").startswith("U ")}
    for shape, wanted in CLAIMS:
        if shape.search(said) and not ((over or kinds) & set(wanted)):
            return False

    return True


def pick_title(ideas, used, legs=None):
    """The first name nobody has taken that fits across a card, and that the
       card can stand behind.

       Every idea that fits is tried before any that does not, so a long one
       is only reached when nothing short is left — a title cut off mid-word
       is worse than a plainer title said whole.
    """
    if legs is not None:
        honest = [one for one in ideas if true_of(one, legs)]
        # Never leave a card nameless: if nothing survives, the ideas stand
        # and the checker will say so rather than the card going out blank.
        ideas = honest or ideas

    # A name is at least two words.
    #
    # "Business", "Statement", "Handled", "Muscle" all went out as titles —
    # the back half of a shape with nothing in front of it, which reads as a
    # word left behind rather than a name for anything. They are tried last,
    # after every idea that says something.
    whole = [one for one in ideas if len(one.split()) > 1]
    ideas = whole + [one for one in ideas if one not in whole]

    short = [one for one in ideas if len(one) <= FITS]
    for one in short + [one for one in ideas if one not in short]:
        if one not in used:
            used.add(one)
            return one

    # Everything taken: number it rather than repeat it silently, and number
    # the shortest so the count is not what gets cut off.
    base = (short or ideas or ["Special"])[0]
    for at in range(2, 99):
        tried = "%s (%d)" % (base, at)
        if tried not in used:
            used.add(tried)
            return tried
    return base


# Primetime is a slot, not a broadcaster. Sunday night and Monday night, at
# eight — the two games a week that stand on their own with nothing else on.
# A Wednesday opener and a Thursday game in Melbourne are neither, whoever is
# carrying them.
def primetime(game):
    when = str(game.get("date") or "")
    if len(when) < 16:
        return False

    try:
        at = time.strptime(when[:16], "%Y-%m-%dT%H:%M")
    except ValueError:
        return False

    # The files are in UTC, so a Sunday night game reads as Monday morning.
    day = at.tm_wday          # 0 Monday .. 6 Sunday
    hour = at.tm_hour
    return (day == 0 and hour < 6) or (day == 1 and hour < 6)


def board_cards(teams, when, spots, lives, records, facts, used):
    """The week's primetime games, one card each.

       Everything else on the shelf is about a man. These are about the game —
       who wins it and by how much — and they are the primetime ones because
       that is what featured means to anybody reading a sports page. It needs
       no judgement of ours and no data we do not already hold: the schedule
       says who is carrying it.
    """
    data = open("data/data.js").read()
    hit = re.search(r"var SCHEDULES = (\{.*?\});\n", data, re.S)
    if not hit:
        return []

    season = str(time.strftime("%Y"))
    weeks = json.loads(hit.group(1)).get(season) or {}
    now = time.strftime("%Y-%m-%dT%H:%M")

    def in_order(key):
        """Preseason, then the season in number order, then the playoffs.
           Sorting the keys as text put "p1" before week one and "10" before
           two, which is how a January bracket came to be this week."""
        if key.startswith("s"):
            return (0, int(key[1:] or 0))
        if key.startswith("p"):
            return (2, int(key[1:] or 0))
        return (1, int(key))

    # The week being played, or the next one — whichever has a game to come.
    ahead = []
    for key in sorted(weeks, key=in_order):
        # The preseason is not featured. Nobody is priced in it and the men
        # playing are not the men anybody came to watch.
        if key.startswith("s"):
            continue
        for game in weeks[key]:
            if not game.get("done") and str(game.get("date") or "") >= now:
                ahead.append((key, game))
    if not ahead:
        return []

    this_week = ahead[0][0]
    out = []

    for key, game in ahead:
        if key != this_week:
            continue
        odds = game.get("odds") or {}
        home = _spread(odds.get("homeSpread"))
        away = _spread(odds.get("awaySpread"))
        if home is None and away is None:
            continue

        fixture = "%s @ %s" % (game["away"], game["home"])
        found = [one for one in (teams.get(game["away"].lower()),
                                 teams.get(game["home"].lower())) if one]
        total = odds.get("total")

        # A card a club, not a card a game. Somebody following the Giants
        # wants the Giants' card — one holding both sides is a board, and a
        # board is not something anybody puts their name to.
        for abbr, line in ((game["away"], away), (game["home"], home)):
            club = teams.get(abbr.lower())
            if not club or line is None:
                continue

            legs = [
                {"figure": "WIN", "says": club["name"], "kind": "Win",
                 "club": abbr, "mark": None, "now": None, "won": None,
                 "push": False, "said": None,
                 "market": club["name"] + " To Win"},
                {"figure": _signed(line),
                 "says": club["name"] + " \u00b7 Spread", "kind": "Spread",
                 "club": abbr, "mark": line, "now": None, "won": None,
                 "push": False, "said": None,
                 "market": "%s %s" % (club["name"], _signed(line))},
            ]

            if total:
                legs.append({
                    "figure": figure_of("Over %s Total Points" % total),
                    "says": "Total Points",
                    "kind": "Total Points", "club": None,
                    "mark": float(total), "now": None, "won": None,
                    "push": False, "said": None,
                    "market": "Over %s Total Points" % total,
                })

            out.append({
                "id": "board-%s-%s" % (game["id"], abbr),
                "featured": primetime(game),
                "title": pick_title(
                    title_ideas(fixture, [], [club], "The Result", legs, {},
                                records, facts, lives, spots,
                                [game["away"], game["home"]],
                                seed=int(str(game["id"])[-3:] or 0),
                                fixture=fixture),
                    used, legs),
                "header": None, "markets": None, "chance": None,
                "fixture": fixture, "starts": game["date"],
                "event": str(game["id"]), "board": True,
                "legs": legs,
            })

    return out


def _spread(said):
    try:
        return float(str(said or "").replace("+", ""))
    except ValueError:
        return None


def _signed(number):
    """A spread as it is written: -7 for the club giving them, +7 for the one
       getting them, and no trailing nought on a whole number."""
    said = ("%g" % abs(number))
    return ("-" if number < 0 else "+") + said


def _spread(said):
    try:
        return float(str(said or "").replace("+", ""))
    except ValueError:
        return None


# bet365's shorthand, in the words the rest of the file reads.
B365 = [
    (re.compile(r"^\s*money\s*line\s*-\s*(.+)$", re.I), r"\1 to Win"),
    (re.compile(r"\bPass\s+Yards\b", re.I), "Passing Yards"),
    (re.compile(r"\bPass\s+TDs?\b", re.I), "Passing Touchdowns"),
    (re.compile(r"\bRec\s+Yards\b", re.I), "Receiving Yards"),
    (re.compile(r"\bRush\s+Yards\b", re.I), "Rushing Yards"),
    (re.compile(r"\bRec\s+TDs?\b", re.I), "Receiving Touchdowns"),
    (re.compile(r"\bRush\s+TDs?\b", re.I), "Rushing Touchdowns"),
]


def as_said(one):
    """A boost's line, in everybody else's words."""
    said = str(one or "").strip()
    for pattern, into in B365:
        said = pattern.sub(into, said)
    return said.replace(":", " ").strip()


def boost_cards(db, men, teams, squad):
    """bet365's boosts.

       Read out of an open tab by read_bet365.py and, until now, read no
       further: `boost_card` and `boost_leg` had been filling since the end
       of August and nothing in this file had ever looked at them. Fifty-nine
       cards fetched every morning, none of which reached a page.

       A boost has no fixture of its own — it is a name, two or three lines
       and two prices — so the game is found from the first club its legs
       name and that club's next fixture. The price is what it pays after the
       boost; what it paid before is the thing being boosted, and nobody is
       taking that.
    """
    today = time.strftime("%Y-%m-%d")
    plays = {}
    for row in db.execute("SELECT date, away, home FROM league_game "
                          "WHERE kind = 'regular' AND date >= ? "
                          "ORDER BY date", (today,)):
        for side in (row["away"], row["home"]):
            plays.setdefault(side, (row["away"] + " @ " + row["home"],
                                    row["date"]))

    # The latest sweep only. The board is a rotating shelf and bet365 puts
    # the same name over a different card from one day to the next — "Maye
    # Day" was a moneyline and two Maye lines this morning and three Maye
    # lines yesterday. Keeping every reading put both on the site, one of
    # them priced at something nobody can take any more.
    out = []
    newest = {}
    last = db.execute("SELECT MAX(read_on) FROM boost_card").fetchone()[0]
    for row in db.execute("""SELECT card_id, name, was, now, read_on, fixture
                               FROM boost_card WHERE read_on = ?""", (last,)):
        newest[row["card_id"]] = dict(row)

    for card_id, row in newest.items():
        said = [one["said"] for one in db.execute(
            """SELECT said FROM boost_leg
                WHERE card_id = ? AND read_on = ? ORDER BY at""",
            (card_id, row["read_on"]))]
        if len(said) < 2:
            continue

        # bet365 writes a market four ways and none of them are the words
        # every other book uses: "Money Line - SEA Seahawks", "Drake Maye:
        # 250+ Pass Yards", "2+ Pass TDs", "100+ Rec Yards". Read as they
        # come, a boost's legs lost their market entirely — "Kirk Cousins
        # 225+" with nothing saying of what. Put into the long words first,
        # they read like anybody else's.
        legs = [dict(read_leg(None, as_said(one)), said=None,
                     market=as_said(one))
                for one in said]

        # The game as the board itself writes it — "NE Patriots @ SEA
        # Seahawks" — read off the heading above the block. Where an older
        # reading has none, it falls back to the first club its legs name
        # and that club's next fixture.
        said_where = row.get("fixture")
        where = None
        if said_where:
            sides = re.findall(r"\b([A-Z]{2,3})\b", said_where)
            where = next((plays.get(one) for one in sides if plays.get(one)), None)
        if not where:
            _, clubs_found, _ = named_in(" & ".join(said), men, teams, squad)
            where = next((plays.get(one["abbr"].upper()) for one in clubs_found
                          if plays.get(one["abbr"].upper())), None)

        # "Same Game Parlay" is the book's word for a wager, not a name for
        # anything. Left unnamed, it is named the way ours are.
        title = (row["name"] or "").strip()
        if re.search(r"parlay|sgp|boost|bet\b|odds|wager", title, re.I):
            title = None

        out.append({
            "id": "b365-" + card_id, "source": "bet365",
            "title": title,
            "header": None, "markets": None,
            "chance": likely(row["now"]), "price": priced(row["now"]),
            "fixture": short_fixture(where[0]) if where else None,
            "starts": where[1] if where else None,
            "event": None,
            "legs": legs,
        })

    return out


def special_cards(db, men, teams, squad, young, taken, records, facts,
                  lives, spots):
    """The book's specials, which are cards by another name.

       A special is one priced line whose text is a whole parlay written out.
       Cut into its legs and given a name of its own, it is a card like any
       other — and it reaches every man it names.
    """
    out = []
    seen = set()
    used = taken

    for row in db.execute("""
            SELECT drawer, said, odds, fixture, starts, event_id, selection_id,
                   read_on
              FROM score_prop
             WHERE tab = 'specials' AND drawer IS NOT NULL
             ORDER BY read_on DESC"""):
        text = (row["drawer"] or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)

        parts = legs_of(text)
        who, clubs_found, _ = named_in(text, men, teams, squad,
                                       sides_in(row["fixture"], teams))
        kind = about(text)
        legs = [dict(read_leg(None, one), said=None, market=one)
                for one in parts]

        out.append({
            "id": row["selection_id"], "source": "score",
            "title": pick_title(
                title_ideas(text, who, clubs_found, kind, legs, young,
                            records, facts, lives, spots,
                            sides_in(row["fixture"], teams),
                            fixture=short_fixture(row["fixture"])),
                used, legs),
            "header": None, "markets": None,
            "chance": likely(row["odds"]), "price": priced(row["odds"]),
            "fixture": short_fixture(row["fixture"]), "starts": row["starts"],
            "event": row["event_id"], "special": True,
            "legs": legs,
        })

    return out


def main():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row

    men = quarterbacks()
    teams = clubs()
    squad = squads()
    young = rookies()
    records = form(db)
    facts = club_facts(db)
    print("%d quarterback keys, %d club keys, %d men on rosters"
          % (len(men), len(teams), len(squad)))

    global SLUGS, PASSERS
    SLUGS = slugs()
    PASSERS = {row[0] for row in db.execute(
        "SELECT name FROM league_player WHERE position = 'QB'")}
    lives = bios()
    spots = where(db)
    when = kickoffs(db)
    # bet365 belongs in here, not after the naming below it: a boost the
    # book calls "Same Game Parlay" has its name taken off — that is a word
    # for a wager, not a name — and added afterwards it went out with none at
    # all, one card on the shelf titled nothing.
    theirs = (score_cards(db, men, teams) + dk_cards(db, men, teams, when)
              + fanduel_cards(db, men, teams, when)
              + boost_cards(db, men, teams, squad)
              + spy_cards(db) + genius_cards(db, teams))
    taken = set(card["title"] for card in theirs if card.get("title"))

    # The shelf's cards come with no name — nobody published them, we chose
    # them — so they are given one the same way a special is, from the same
    # pool of back-page shapes, and against the same set of names already
    # used so no two cards on the site read alike.
    for at, card in enumerate(one for one in theirs if not one.get("title")):
        text = " ".join(leg.get("said") or leg.get("market") or ""
                        for leg in card["legs"])
        who, clubs_found, _ = named_in(text, men, teams, squad,
                                       sides_in(card.get("fixture"), teams))
        # The rules first, and only here — they read the figure, the stat
        # and the man off a finished leg, and a leg is not finished until
        # read_leg has been over it. Asked any earlier they are half blind:
        # thirteen of forty-nine fired when this sat inside title_ideas.
        said = None
        try:
            import title_rules
            played = (spots or {}).get(
                frozenset(one["abbr"] for one in clubs_found[:2]), {})
            # Two words at least, here as well as in pick_title. The rules
            # can hand back the back half of a shape on its own — "Pounding",
            # "Muscle", "Inches" — which reads as a word left behind rather
            # than a name. One is taken only when nothing fuller is offered.
            found = [one for one in title_rules.every_name(
                card, str(played.get("location") or "").split(",")[0].strip())
                if one not in taken]
            said = next((one for one in found if len(one.split()) > 1),
                        found[0] if found else None)
        except Exception:
            # A rule that throws must not cost the card its name.
            said = None

        card["title"] = said or pick_title(
            title_ideas(text, who, clubs_found, about(text), card["legs"],
                        young, records, facts, lives, spots,
                        sides_in(card.get("fixture"), teams), seed=at,
                        fixture=card.get("fixture")),
            taken, card["legs"])

        # A mood word wants a club in front of it.
        #
        # MOOD holds the back half of a shape — "Pounding", "Muscle",
        # "Inches" — meant to follow a club: "The Ravens Pounding". When
        # every prefixed form is already taken the bare word went out on its
        # own, and nine cards were titled a single verb. The club is put back
        # rather than the card being left with a fragment.
        if card["title"] and len(card["title"].split()) == 1 and clubs_found:
            for one in clubs_found:
                tried = "%s %s" % (one.get("short") or one.get("abbr"),
                                   card["title"])
                if tried not in taken:
                    card["title"] = tried
                    break

        taken.add(card["title"])

    # The primetime game cards no longer carry the Featured flag. Kicking off
    # at night is a reason to put a game on a page and no reason at all to put
    # a card on the shelf — it says nothing about whether the numbers on it
    # are likely to come in. The shelf is built by build/featured.py from what
    # our own games say, with the best of each source beside it. These stay on
    # the schedule where they belong.
    board = board_cards(teams, when, spots, lives, records, facts, taken)
    for card in board:
        card["featured"] = False

    cards = (theirs +
             special_cards(db, men, teams, squad, young, taken,
                            records, facts, lives, spots) +
             board)
    print("%d cards read" % len(cards))

    shown, kept = [], 0
    for card in cards:
        # A title is words, and a card is about how a man plays. The books'
        # pictures come out of the one, and the markets that are not ours
        # come out of the other.
        if card.get("title"):
            card["title"] = plain_title(card["title"])
        card["legs"] = [leg for leg in card["legs"]
                        if leg.get("kind") not in NOT_OURS]
        if not card["legs"]:
            continue

        who, clubs_found, anyone = [], [], []
        for leg in card["legs"]:
            # Not `why`. The hub's own reasoning is free text about
            # something that is not the pick — "Davante Adams has scored a
            # touchdown in six of his last seven against the 49ers" sat
            # under three Lions and Saints legs naming nobody named Adams,
            # and searching it anyway put a Rams receiver, and the Rams
            # themselves, on a card that has no Rams leg on it at all.
            said_by = " ".join(str(one or "") for key, one in leg.items()
                               if key != "why" and not isinstance(one, (int, float)))
            a, b, c = named_in(said_by, men, teams, squad,
                               sides_in(card.get("fixture"), teams),
                               leg.get("kind"))
            for one in a:
                if one["id"] not in [x["id"] for x in who]:
                    who.append(one)
            for one in b:
                if one["id"] not in [x["id"] for x in clubs_found]:
                    clubs_found.append(one)
            for one in c:
                if one["id"] not in [x["id"] for x in anyone]:
                    anyone.append(one)

        card["qbs"] = [{"id": one["id"], "name": one["name"]} for one in who]

        # A club's page shows a card only when the card actually names that
        # club — either in a leg a reader can see, or through a man on it.
        #
        # The clubs above are found in everything a leg carries, the book's
        # own phrasing included, and that phrasing is stripped before the
        # file is written. So a club could be named in text nobody would ever
        # see and still decide which page the card landed on: a card of four
        # wins — Seattle, the Rams, Houston, Minnesota — reached Buffalo's
        # page with no Buffalo leg anywhere on it.
        drawn = " ".join(str(leg.get("says") or "") for leg in card["legs"])
        drawn = drawn.lower()
        theirs = {one["club"] for one in anyone if one.get("club")}

        card["clubs"] = [
            one["abbr"] for one in clubs_found
            if one["abbr"] in theirs
            or any(str(one.get(part) or "").lower() in drawn
                   for part in ("abbr", "short", "name", "location")
                   if one.get(part))
        ]
        # A club a leg's own words never name — the game a bare "Total
        # Points" belongs to, on a card that holds more than one — reaches
        # here from genius_cards() directly rather than through the text a
        # leg happens to say.
        for abbr in card.pop("clubs_hint", []):
            if abbr not in card["clubs"]:
                card["clubs"].append(abbr)
        # A future is kept but flagged, so the pages can leave it out.
        said, boxes = from_legs(card["legs"])
        card["header"] = said
        card["markets"] = boxes
        # Week by week, and nothing else.
        #
        # A season-long card is not a card this asks about: it has no kickoff,
        # so it sorts into no week, and every filter that works by week — the
        # shelf, the builder's Similar and All — reaches past it silently.
        # Kept out here rather than left in to be ignored everywhere.
        card["future"] = is_future(card.get("fixture"))
        if card["future"]:
            continue
        if not card.get("starts") and len(card["clubs"]) >= 2:
            card["starts"] = when.pair(card["clubs"])

        # And where the clubs cannot settle it, the fixture says so outright.
        #
        # Seven cards sat with no kickoff for want of this. Every one of them
        # names a single club in its legs — five Rams and 49ers cards, two
        # Titans — so the pair lookup above had nothing to pair, while the
        # fixture on the card read "SF @ LAR" and "NYJ @ TEN" in plain sight.
        if not card.get("starts"):
            card["starts"] = when(card.get("fixture"))

        # A card for a game already played is not a card.
        #
        # Five were on the shelf: Seattle beat Tennessee 19-16 on 24 August
        # and Indianapolis beat Detroit 25-16 on the 29th, both preseason,
        # and their cards carried no kickoff because this only ever looked
        # forward. With no kickoff nothing dropped them and nothing could —
        # they sorted into no week, so no week check ever saw them.
        if not card.get("starts") and when.gone(card["clubs"], card.get("fixture")):
            continue

        # And a card with no game at all takes its week from the men on it.
        #
        # Five men across five games, no fixture written anywhere: the card
        # belongs to a week rather than to a fixture, and the week is the one
        # its players are next playing in. Without this it sorted nowhere and
        # no week filter could ever reach it.
        if not card.get("starts"):
            days = [when.club(one["club"]) for one in anyone if one.get("club")]
            days = [day for day in days if day]
            if days:
                card["starts"] = min(days)

        # A card that actually spans several games is not the one game its
        # fixture text happened to land on.
        #
        # "Win 1" named four winners — Seattle, the Rams, Houston, Minnesota
        # — from four different games, and its fixture read "NE @ SEA": the
        # New England leg does not exist, that is simply the row DraftKings
        # filed it under. "Always Open" read "ARI @ LAC" while naming seven
        # men across seven other games, LAC not among them. Purely cosmetic
        # — `starts` above is already worked out from the real clubs, not
        # from this text — so it changes nothing else about the card.
        spans = when.games_of(card["clubs"])
        if len(spans) > 1:
            card["fixture"] = "%d games" % len(spans)

        # Everyone the card names, so a skill player's page needs no re-sweep.
        card["players"] = [{"id": one["id"], "name": one["name"],
                            "club": one["club"], "spot": one["spot"]}
                           for one in anyone]

        # A card belongs on a page only if it names somebody with one.
        if who or clubs_found:
            shown.append(card)
        kept += 1

    # ---- A duplicate leg, and only a duplicate leg ----
    #
    # This used to fold any two legs asking the same question at different
    # numbers — "U 25.5 Drake Maye rushing yards" and "U 26.5" — keeping the
    # keener. But those are two different asks, and a card is the book's
    # card: every leg it published is kept unless the same leg was published
    # twice. So the number is part of what makes a leg itself, and a leg is
    # dropped only when an identical one is already on the card.
    folded = 0
    for card in shown:
        best = {}
        for leg in card.get("legs") or []:
            key = (str(leg.get("says") or ""), str(leg.get("kind") or ""),
                   str(leg.get("figure") or ""), leg.get("mark"))
            if key in best:
                folded += 1
                continue
            best[key] = leg
        if len(best) != len(card.get("legs") or []):
            card["legs"] = list(best.values())

    if folded:
        print("%d leg%s dropped as an exact repeat of another on the card"
              % (folded, "" if folded == 1 else "s"))

    # And a card that folded down to one leg is not a card any more.
    #
    # "We're Going Over" was two DraftKings lines on the same question at two
    # numbers; the keener was kept and what went out was a single leg with a
    # card's name and a card's price on it. Only cards the fold shortened are
    # dropped — one that arrived with one leg arrived that way on purpose.
    thin = [card for card in shown
            if len(card.get("legs") or []) < 2 and card.get("price")]
    if thin:
        print("%d card%s dropped, folded down to one leg" %
              (len(thin), "" if len(thin) == 1 else "s"))
        shown = [card for card in shown if card not in thin]

    # ---- One card per set of legs ----
    #
    # Two books offering the same pair is one card to a reader, however
    # differently they name it: "The Hammer Handled" and "Mafia Business"
    # were Josh Allen's touchdown and Buffalo to win, in the two possible
    # orders, one above the other on Buffalo's page.
    #
    # The order of the legs is not part of what a card is, so the signature
    # is sorted. The first one kept wins — they arrive in the order the lanes
    # are read, and that order is ours first.
    # Kept, not dropped.
    #
    # This used to keep the first of any two cards with the same selections
    # and throw the rest away — thirty-one of them a night. Nothing at source
    # is actually duplicated: across theScore and bet365 not one leg-set is
    # written the same way twice, and the collision only appears after both
    # are put into our own wording. What it was throwing away was a second
    # book's name for the card and a second book's price for it — "Falcon
    # Fever" at +1000 went, and "Fly High Falcons" at +742 stayed.
    #
    # A card is a book's card. Each one keeps its own.
    seen, only = {}, list(shown)
    for card in shown:
        mark = (card.get("fixture") or "",
                tuple(sorted((leg.get("figure") or "") + "|" +
                             (leg.get("says") or "")
                             for leg in card.get("legs") or [])))
        seen[mark] = seen.get(mark, 0) + 1

    same = sum(n - 1 for n in seen.values() if n > 1)
    if same:
        print("%d card%s another book also publishes, kept" %
              (same, "" if same == 1 else "s"))
    shown = only

    # Nearest to happening first. The share each card was worked out from is
    # dropped here — the site is handed a place in a queue and nothing else,
    # which cannot be read back into what any book was charging.
    ranked = sorted([one for one in shown if one.get("chance") is not None],
                    key=lambda one: -one["chance"])
    for at, card in enumerate(ranked, 1):
        card["near"] = at
    for card in shown:
        if card.pop("chance", None) is None:
            # Nothing to judge it by: it sorts after everything judged.
            card["near"] = len(ranked) + 1

    # A pinned card goes above everything, whatever it was ranked. Nought is
    # ahead of first.
    for card in shown:
        if card.pop("pin", False):
            card["near"] = 0

    # ---- Nothing leaves that says where a card came from ----
    #
    # None of this was ever on screen, and all of it was in the file. An id
    # like "FeaturedBetParlayCard:f90b2113" is a book's own naming, carried
    # through untouched, and it says both which book and what it calls the
    # thing. A `from` field named it outright. Anyone opening the page source
    # could read the whole provenance of the shelf.
    #
    # So an id becomes a hash of itself — stable, so a bell or a reaction
    # given yesterday still finds its card, and meaningless to anybody who
    # has not got the same input. And the fields that name a source or say
    # what it charged are dropped rather than renamed: a field that is not
    # there cannot be read.
    for card in shown:
        card["id"] = named_quietly(card.get("id"))
        # `price` is not in this list.
        #
        # It is dropped from what is published, not from what we hold —
        # quietly.py takes it off on the way into ship/, along with odds and
        # payout, so the page source still says nothing about what anybody
        # charged. Keeping it here is what lets our own screens rank on it
        # and show it where a reader is meant to see it.
        for gone in ("from", "board_from", "special", "chance", "odds",
                     "payout", "wagers"):
            card.pop(gone, None)

        # A blurb written by whoever published the card, in their words —
        # "A dominant Rams parlay." Ours is the week and the fixture, drawn
        # from the kickoff, so a borrowed sentence is only ever a way for
        # somebody else's language to reach the page.
        if card.get("blurb") and re.search(
                r"parlay|bet\b|odds|moneyline|book|sportsbook|wager|payout",
                str(card["blurb"]), re.I):
            card["blurb"] = None

    # ---- What each leg costs ----
    #
    # Two of the five sources price every leg under their cards; three
    # publish the card price and nothing beneath it. So most of the shelf
    # showed a figure and a line with no way to tell what either was worth,
    # and a card whose price came from one leg by mistake read exactly like
    # a card whose price was right.
    #
    # Every leg is looked up in one book built from every board that prices
    # anything — DraftKings' props and main lines, theScore's board — keyed
    # by what the leg says rather than by how a source spells it, so a leg
    # is matched the same way it is rendered. Where the selling book gave a
    # price, that price stands: it is what a reader would have been charged.
    # Where several sources price the same leg and disagree, the
    # disagreement is carried out with the leg rather than averaged away.
    from leg_odds import price_book, key_from, ladders, around, TRUST

    book = price_book(db)
    rungs = ladders(book)
    priced_legs = unpriced_legs = 0
    for card in shown:
        for leg in card.get("legs") or []:
            key = key_from(leg.get("says"), leg.get("figure"),
                           leg.get("kind"))
            found = [dict(one, own=False) for one in (book.get(key) or [])] \
                if key else []
            own = leg.get("odds")
            if own and str(own).strip() not in ("", "None"):
                found = [{"source": card.get("source") or "ours",
                          "odds": priced(own), "own": True}] + found

            if not found:
                leg["odds"] = None
                unpriced_legs += 1
                # A card is allowed to write its own number — "Sam Darnold
                # 234+" — and nobody sells that number alone. The rungs
                # either side of it are sold, and they bound what the leg
                # is worth: more than 230+ costs, less than 240+ pays. So
                # the neighbours travel with the leg, plainly labelled as
                # the neighbours they are, instead of a blank that reads
                # as ignorance or a guess that reads as a price.
                said = re.fullmatch(r"(\d+)\+",
                                    str(leg.get("figure") or ""))
                ou = re.fullmatch(r"([OU])\s*(\d+(?:\.\d+)?)",
                                  str(leg.get("figure") or ""))
                near = []
                if said and key and len(key) == 3:
                    below, above = around(rungs.get(key[:2]), int(said.group(1)))
                    near = [dict(one, odds=priced(one["odds"]))
                            for one in (below, above) if one]
                elif ou and key and len(key) == 3:
                    shelfside = "under" if ou.group(1) == "U" else "over"
                    below, above = around(
                        rungs.get((key[0], "%s %s" % (key[1], shelfside))),
                        float(ou.group(2)))
                    near = [dict(one, odds=priced(one["odds"]))
                            for one in (below, above) if one]
                if near:
                    leg["odds_near"] = near
                continue

            # The book that sold the card comes first, whoever else prices
            # the leg. Its number is what a reader would actually have been
            # charged; another board's is a second opinion, however deep
            # that board is. Ranked on depth alone DraftKings' props
            # outrank theScore's own price on theScore's own card, which is
            # how six hundred legs came to be quoted at the wrong shop.
            order = {name: at for at, name in enumerate(TRUST)}
            first = min(found, key=lambda one: (
                not one["own"], order.get(one["source"], 99)))
            leg["odds"] = priced(first["odds"])
            leg["odds_from"] = first["source"]
            priced_legs += 1

            # Two boards, two prices, and nothing in the record says which
            # is right — so both travel with the leg and the card can show
            # that they differ. Averaging them would make the conflict
            # disappear without making it false.
            others = [one for one in found
                      if priced(one["odds"]) != leg["odds"]]
            if others:
                leg["odds_else"] = [
                    {"source": one["source"], "odds": priced(one["odds"])}
                    for one in others[:3]]

    print("%d legs priced, %d with no price on any board"
          % (priced_legs, unpriced_legs))

    for card in shown:
        # A leg keeps the words it was read from — the book's own market name
        # and its own phrasing — and neither is used to draw anything. The
        # figure and the line beneath it were made from them and are all the
        # card shows, so the raw pair goes: "Moneyline" is a book's word for
        # a win, and it was in the file fifty-two times.
        for leg in card.get("legs") or []:
            leg.pop("market", None)
            leg.pop("said", None)
            # The hub's own reasoning and its letter grade. Neither is drawn,
            # both are its copy word for word — "the Saints have covered the
            # spread in each of their last six" — and that sentence names
            # both a source and a thing we do not talk about.
            leg.pop("why", None)
            leg.pop("grade", None)

    with open(OUT, "w") as handle:
        handle.write("/* The week's cards, sorted onto the pages they name."
                     "\n   Generated by export_cards.py — do not edit by hand. */\n")
        handle.write("var CARDS = %s;\n"
                     % json.dumps(shown, indent=1, ensure_ascii=False))

    on_qb = sum(1 for one in shown if one["qbs"])
    on_club = sum(1 for one in shown if one["clubs"])

    print("\n%d cards shown of %d — %d name a quarterback, %d name a club"
          % (len(shown), kept, on_qb, on_club))
    print("written to %s" % OUT)

    for one in shown[:6]:
        print("   %-26s qb:%-22s club:%s"
              % (one["title"][:26],
                 ",".join(x["name"] for x in one["qbs"])[:22],
                 ",".join(one["clubs"])))


if __name__ == "__main__":
    main()
