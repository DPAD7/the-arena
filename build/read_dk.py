"""DraftKings, asked properly — through the browser that is allowed to ask.

   DraftKings' API is the one door that stayed shut. Akamai turns away a plain
   request with "Access Denied" even when it carries every header the club's
   own client sends, because what it wants is a cookie its JavaScript makes and
   throws away again. So the API was written off and the board read off the
   page instead, card by card, scrolling as we went.

   That was the wrong shape of answer. A page shows only what is on screen, so
   covering a league meant visiting every fixture and scrolling each one, and
   what was gathered was whatever happened to be rendered at the time.

   The way in is to ask from inside. A tab already on DraftKings has the
   cookies, the origin and the standing Akamai has spent its whole visit
   earning; a fetch issued from that page is simply the site talking to itself,
   and answers with JSON. Nothing is navigated and nothing is scrolled — the
   tab stays where its owner left it.

   Run:  python3 build/read_dk.py             the NFL, everything it will give
         python3 build/read_dk.py --probe     say which endpoints answer
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import subprocess

from curl_cffi import requests as browserish
import time
import urllib.parse

from store import open_db, patiently, put_many, value

NASH = "https://sportsbook-nash.draftkings.com/sites/US-MD-SB/api"

# One session, so the connection is opened once and reused.
SESSION = browserish.Session()

# DraftKings' own numbers for the leagues we care about.
# The preseason is a league of its own at DraftKings, not a part of the NFL
# one — asking only for 88808 answers with Week 1 onward and no preseason at
# all, which is why tonight's games had no cards while the site was full of
# them.
LEAGUES = {"nfl": 88808, "nfl-preseason": 24685, "ncaaf": 87637}

SCHEMA = """
-- The cards a person sees first. The API gives every part of one plainly:
-- the name somebody wrote, the sentence under it, the label saying what kind
-- of bet it is, and the address of the picture behind it — which appears in
-- no list DraftKings publishes and cannot be guessed.
CREATE TABLE IF NOT EXISTS dk_card (
    read_on     TEXT NOT NULL,
    league      TEXT NOT NULL,
    event_id    TEXT,
    fixture     TEXT,
    card_id     TEXT NOT NULL,
    title       TEXT,
    subtitle    TEXT,               -- the sentence explaining the idea
    label       TEXT,               -- SGPx, Parlay
    kind        TEXT,               -- PreLive, Live
    odds        TEXT,
    image       TEXT,
    ends        TEXT,
    legs        TEXT NOT NULL,
    PRIMARY KEY (read_on, card_id)
);

CREATE TABLE IF NOT EXISTS dk_market (
    read_on     TEXT NOT NULL,
    league      TEXT NOT NULL,
    event_id    TEXT,
    fixture     TEXT,
    category    TEXT,
    market_id   TEXT NOT NULL,
    market      TEXT,
    selection   TEXT NOT NULL,
    said        TEXT,
    line        REAL,
    odds        TEXT,
    participant TEXT,
    PRIMARY KEY (read_on, market_id, selection)
);
"""


def tab_on_dk():
    """A tab already on DraftKings, whose standing we borrow."""
    find = '''tell application "Google Chrome"
set out to ""
repeat with w from 1 to count of windows
repeat with t from 1 to count of tabs of window w
set out to out & w & "|" & t & "|" & (URL of tab t of window w) & ","
end repeat
end repeat
return out
end tell'''
    out = subprocess.run(["osascript", "-e", find],
                         capture_output=True, text=True).stdout
    for line in out.split(","):
        bits = line.strip().split("|", 2)
        if len(bits) == 3 and "sportsbook.draftkings.com" in bits[2]:
            return bits[0], bits[1]
    return None, None


def run(window, tab, code):
    code = code.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    script = ('tell application "Google Chrome" to tell tab %s of window %s '
              'to execute javascript "%s"' % (tab, window, code))
    return subprocess.run(["osascript", "-e", script],
                          capture_output=True, text=True).stdout.strip()


def over_the_wire(path, patience=3):
    """Ask DraftKings directly.

       For a long time this had to go through a tab somebody had open,
       because everything else came back 403 — and the 403 was not about the
       token or the headers. There is no token on these paths at all. Akamai
       reads the shape of the TLS handshake and refuses one that is not a
       browser's, which no combination of headers can change and which
       headless Chrome fails as well.

       curl_cffi shakes hands the way Chrome does. Same request, same second,
       same machine: 403 from curl, 200 and three hundred and seventy-seven
       kilobytes from this. The tab is no longer the only door.
    """
    for _ in range(patience):
        try:
            answer = SESSION.get(NASH + path, impersonate="chrome124",
                                 timeout=30)
        except Exception:
            time.sleep(1)
            continue
        if answer.status_code != 200:
            return None
        try:
            return answer.json()
        except ValueError:
            return None
    return None


def ask(window, tab, path, patience=20):
    """One request. The window and tab are ignored — they are kept in the
       signature so every caller below reads as it always did."""
    return over_the_wire(path)


def ask_through_a_tab(window, tab, path, patience=20):
    """One request, issued by the page and collected once it lands.

       AppleScript cannot wait on a promise, so the answer is left on the
       window and fetched from there a moment later.
    """
    run(window, tab, "window.__dk=undefined;'ok'")
    run(window, tab, """fetch('%s%s',{headers:{accept:'application/json'}})
        .then(function(r){return r.json();})
        .then(function(j){window.__dk=j;})
        .catch(function(e){window.__dk={error:String(e)};});'go'""" % (NASH, path))

    for _ in range(patience):
        time.sleep(0.5)
        if run(window, tab, "window.__dk===undefined?'':'here'"):
            break
    else:
        return None

    # A slate is far too large to pass back through AppleScript in one piece,
    # so the page hands it over in slices and it is joined up here.
    size = run(window, tab, "String(JSON.stringify(window.__dk).length)")
    if not size.isdigit():
        return None
    # AppleScript carries three hundred thousand characters as
    # readily as eight thousand — 0.47 seconds either way. Slicing small
    # turned one summary into sixty round trips and a season into a night.
    whole, step = "", 250000
    for at in range(0, int(size), step):
        whole += run(window, tab,
                     "JSON.stringify(window.__dk).slice(%d,%d)" % (at, at + step))
    try:
        return json.loads(whole)
    except ValueError:
        return None


def markets_in(payload, when, league):
    """Every priced selection in a slate, flattened."""
    events = {str(one.get("id")): one for one in (payload.get("events") or [])}
    # A selection knows its market and nothing else; the market is what knows
    # which fixture it belongs to. Read the other way round, every price comes
    # back unattached to a game.
    markets = {str(one.get("id")): one for one in (payload.get("markets") or [])}
    out = []
    for one in payload.get("selections") or []:
        market_id = str(one.get("marketId"))
        market = (markets.get(market_id) or {}).get("name")
        event_id = (markets.get(market_id) or {}).get("eventId")
        event = events.get(str(event_id)) or {}
        points = one.get("points")
        out.append({
            "read_on": when, "league": league,
            "event_id": str(event_id) if event_id else None,
            "fixture": event.get("name"),
            # tags come as a list — "Popular", "Player Props" and so on.
            "category": ", ".join(one.get("tags") or [])
                        if isinstance(one.get("tags"), list) else one.get("tags"),
            "market_id": market_id, "market": market,
            "selection": str(one.get("id")), "said": one.get("label"),
            "line": float(points) if points not in (None, "") else None,
            "odds": (one.get("displayOdds") or {}).get("american"),
            "participant": str(one.get("participantId") or "") or None,
        })
    return out


def cards_for(window, tab, event_id, fixture, when, league):
    """Every content card on one fixture, with its words and its picture."""
    got = ask(window, tab,
              "/sportscontent/prepacks/event/v1/contentcards/all/events/%s"
              % event_id)
    out = []
    for card in (got or {}).get("contentCards") or []:
        # A leg says "Jaxon Smith-Njigba to Score a TD" under selectionLabel,
        # not label, and carries no price of its own — only the card is priced.
        # Read for the wrong key it all comes back null, which is how two
        # thousand cards were stored with nothing in them.
        legs = [{"said": one.get("selectionLabel"),
                 "market": one.get("marketId"),
                 "selection": one.get("selectionId"),
                 # The club behind the leg, which is where its badge comes
                 # from: the card gives an id, and club_look holds the mark.
                 "club": ", ".join(str(who.get("teamId") or who.get("id"))
                                   for who in one.get("participants") or []),
                 "club_said": ", ".join(who.get("name") or ""
                                        for who in one.get("participants") or []),
                 "same_game": bool(one.get("isSameGameParlay"))}
                for one in card.get("selections") or []]
        out.append({
            "read_on": when, "league": league,
            # Which code of football this is. The table has always required
            # it and this never set it, so every card read here was thrown
            # away on the way to the database — the whole sweep failing on
            # the last line after doing all the work.
            "football": 1 if str(league).startswith("nfl") else 0,
            "event_id": str(event_id),
            "fixture": fixture, "card_id": card.get("id"),
            "title": card.get("title"), "subtitle": card.get("subtitle"),
            "label": card.get("cardLabel"), "kind": card.get("contentCardType"),
            "odds": (card.get("displayOdds") or {}).get("american"),
            "image": card.get("backgroundImageUrl"), "ends": card.get("endDate"),
            "legs": json.dumps(legs, separators=(",", ":")),
        })
    return out


# The league feed answers with a rolling window — about the next thirty days,
# seventy-five fixtures of an eighteen-week season — and no filter widens it.
# Five were tried: a date range, an OData filter on the start date, a take
# count, a category path and the old eventgroup route. All returned the same
# seventy-five.
#
# The way to the rest is not the league at all but the club. A team's own
# markets are asked for by its rosetta id, and that answers with its whole
# season, from August to January. Thirty-two of those, folded together, is
# every game there is.
GAME_LINES = 4518

def team_markets(team_id, sub=GAME_LINES):
    """The address of one club's markets.

       Built rather than templated: the query is percent-encoded, so a format
       string full of %20 and %27 fights whatever is substituted into it.
    """
    events = ("$filter=participants/any(p: p/metadata/any(m: m/key eq "
              "'rosettaTeamId' and m/value eq '%s'))" % team_id)
    markets = ("$filter=clientMetadata/subCategoryId eq '%d' "
               "AND tags/all(t: t ne 'SportcastBetBuilder')" % sub)
    return ("/sportscontent/controldata/team/leagueSubcategory/v1/markets"
            "?isBatchable=false&templateVars=%s,%d&eventsQuery=%s"
            "&marketsQuery=%s&include=Events&entity=events"
            % (team_id, sub, urllib.parse.quote(events, safe=""),
               urllib.parse.quote(markets, safe="")))


def clubs_in(payload):
    """Every club named on a slate, by the id its own markets are asked for."""
    found = {}
    for one in payload.get("events") or []:
        for side in one.get("participants") or []:
            meta = side.get("metadata")
            if not isinstance(meta, dict):
                continue
            rid = meta.get("rosettaTeamId")
            if rid:
                found[str(rid)] = {
                    "name": side.get("name"),
                    "short": meta.get("shortName"),
                    "color": meta.get("teamColor"),
                    "colour_two": meta.get("teamColorSecondary"),
                }
    return found


def season_for(window, tab, team_id):
    """One club's whole season, which the league feed will not give."""
    return ask(window, tab, team_markets(team_id))


PROBES = (
    "/sportscontent/dkusmd/v1/leagues/%(id)d",
    "/sportscontent/dkusmd/v1/leagues/%(id)d/categories",
    "/sportscontent/navigation/dkusmd/v2/nav/leagues/%(nav)d",
    "/sportscontent/prepacks/league/v1/contentcards/all/leagues/%(id)d",
)


def main():
    window, tab = None, None

    asked = [one for one in sys.argv[1:] if one in LEAGUES] or \
        ["nfl-preseason", "nfl"]
    for league in asked:
        print("\n=== %s ===" % league)
        one_league(window, tab, league)


def one_league(window, tab, league):
    nums = {"id": LEAGUES[league], "nav": 24685}

    if "--probe" in sys.argv:
        for shape in PROBES:
            path = shape % nums
            got = ask(window, tab, path)
            print("   %-58s %s" % (path[-58:],
                                   "nothing" if got is None else
                                   ", ".join(list(got)[:6])))
        return

    got = ask(window, tab, "/sportscontent/dkusmd/v1/leagues/%d" % nums["id"])
    if not got:
        sys.exit("the league came back empty — is the tab still on DraftKings?")

    when = time.strftime("%Y-%m-%dT%H:%M:%S")
    priced = markets_in(got, when, league)

    db = open_db()
    patiently(lambda: db.executescript(SCHEMA))
    put_many(db, "dk_market", priced)
    patiently(db.commit)

    kinds = {}
    for row in priced:
        kinds[row["market"]] = kinds.get(row["market"], 0) + 1
    print("%d prices across %d fixtures" % (len(priced),
          len({row["event_id"] for row in priced if row["event_id"]})))
    for market, count in sorted(kinds.items(), key=lambda x: -x[1])[:12]:
        print("   %-44s %5d" % (market, count))

    # Then each fixture's own cards, which is where the artwork and the
    # sentences live. The league answer does not carry them.
    #
    # And it does not carry every fixture either: it answers with a rolling
    # month, seventy-five games of an eighteen-week season, and no filter
    # widens it. Asking each club for its own season does — thirty-two of
    # those folded together is every game there is. This was written and
    # never called, so the sweep had been reading a quarter of the board and
    # the rest read as cards taken down.
    fixtures = {str(one.get("id")): one.get("name")
                for one in got.get("events") or []}

    # Only the games that are actually near. Walking all two hundred and
    # seventy-two through the browser one at a time takes twenty minutes to
    # answer a question about this week — the rest can be picked up week by
    # week as they come round.
    near = value(db,
        "SELECT group_concat(game_id) FROM league_game "
        "WHERE date >= date('now', '-1 day') "
        "AND (date <= date('now', '+4 days') OR week = 1) "
        "AND kind IN ('pre', 'regular')") or ""

    print("%d fixtures on the board, %d of them near"
          % (len(fixtures), len(fixtures)))
    cards = []
    for at, (event_id, fixture) in enumerate(sorted(fixtures.items()), 1):
        found = cards_for(window, tab, event_id, fixture, when, league)
        if not found:
            continue
        cards += found
        # Written as it goes. Held to the end, a run cut short lost every
        # card it had already read and the sweep looked like it had failed.
        put_many(db, "dk_card", found)
        patiently(db.commit)
        print("   %-34s %d cards" % ((fixture or event_id)[:34], len(found)))

    print("\n%d prices and %d cards held, over %d readings"
          % (value(db, "SELECT COUNT(*) FROM dk_market", default=0),
             value(db, "SELECT COUNT(*) FROM dk_card", default=0),
             value(db, "SELECT COUNT(DISTINCT read_on) FROM dk_market", default=0)))


if __name__ == "__main__":
    main()
