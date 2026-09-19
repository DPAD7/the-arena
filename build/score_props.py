"""Every line theScore Bet is offering, game by game, week by week.

   The book keeps its prices behind a token, and for a while that looked like
   a wall: its plain endpoint answers UNAUTHORIZED, the section ids it wants
   are minted per page load, and the app grabs its own fetch before anything
   can be wrapped around it. The way through is that the token is handed to
   anybody who asks:

     Startup(connectToken)   mints an anonymous bearer — no login, and it
                             does not care what connect token it is given
     EventPage(canonicalUrl) the address you would paste in a browser, and
                             it answers with every tab and its section id
     EventSection(sectionId) the drawers on that tab
     EventDrawerContent      the markets, the men, and the prices

   So no browser is opened and no page is navigated. Three headers matter:
   the app's own x-app pair, the bearer, and a content-type — without the
   last the book refuses the call as cross-site.

   Two times are kept on every row: when we asked, and when the book says it
   set the price. Nothing is overwritten; a price read twice is two rows and
   the pair is the movement.

   Run:  python3 build/score_props.py              the whole slate
         python3 build/score_props.py --games 2    the first two
         python3 build/score_props.py --qb         passing and rushing only
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import re
import subprocess
import time
import urllib.parse

from store import open_db, patiently, put_many, value

# Maryland's shelf. The book keeps one per region and the default answers
# nothing — us-default was half of why this looked shut.
BASE = "https://sportsbook.us-md.thescore.bet/graphql/persisted_queries/"
SITE = "/sport/football/organization/united-states/competition/nfl"

# The book's own query hashes. They change when it redeploys — which is how
# fetch_book.py died — so a run that finds them stale says so rather than
# quietly storing nothing.
Q = {
    "Startup": "8c52170d05417bcc2642d4fb132694a00b4825facf4f23fa47bb78f2b8b59d83",
    "EventPage": "ea73e76bd4a828b507a14359bc702885cf473358f8a519315f9ad9569f641aa1",
    "EventSection": "8ac31d28c8fd43e02a73beebd64e888bb0390db701907ecbd7b633a1bf00a750",
    "EventDrawerContent": "0f351a688287fbcb437b57d8b6ec26ded758eb18fc889ca04b2595f7aa6960f1",
    "CompetitionPageSectionLinesTabNode":
        "bf8963f33b5a9f74940f9f1afca32e51ff1d4ed78ffc9503b5247f4b130cdce4",
    "Marketplace":
        "214baff67db6a99c586c906e564600c15a6a32618096e791378a9f5ff0fc1b41",
}

# What a quarterback is priced in. The rest are swept too unless --qb.
QB_TABS = ("passing", "rushing", "td_scorers", "popular")

SCHEMA = """
CREATE TABLE IF NOT EXISTS score_prop (
    read_on      TEXT NOT NULL,       -- when we asked
    set_at       TEXT,                -- when the book says it set the price
    event_id     TEXT NOT NULL,
    fixture      TEXT,
    starts       TEXT,
    tab          TEXT,                -- passing, td_scorers, ...
    drawer       TEXT,                -- "Total Passing Yards (O/U)"
    market_id    TEXT NOT NULL,
    market       TEXT,                -- "Sam Darnold Total Passing Yards"
    market_type  TEXT,                -- TOTAL, MONEYLINE, ...
    status       TEXT,
    player       TEXT,                -- "Sam Darnold", where the name gives one
    selection_id TEXT NOT NULL,
    said         TEXT,                -- "Over 229.5"
    short        TEXT,                -- "O 229.5"
    odds         TEXT,                -- "-125"
    PRIMARY KEY (read_on, selection_id)
);

CREATE INDEX IF NOT EXISTS score_prop_player ON score_prop (player);
CREATE INDEX IF NOT EXISTS score_prop_event  ON score_prop (event_id);
CREATE INDEX IF NOT EXISTS score_prop_market ON score_prop (market_id);

/* The book's own named cards — "Brotherly Backfield" — which sit in the
   carousel on a game's Popular tab. A card is a title, a price and a handful
   of legs; the legs are what say whose card it is. */
CREATE TABLE IF NOT EXISTS score_card (
    read_on    TEXT NOT NULL,
    event_id   TEXT NOT NULL,
    card_id    TEXT NOT NULL,
    fixture    TEXT,
    starts     TEXT,
    title      TEXT,               -- "Brotherly Backfield"
    header     TEXT,               -- "Same Game Parlay"
    kind       TEXT,               -- PARLAY_PLUS
    odds       TEXT,               -- "+2057"
    payout     TEXT,               -- "$10.00 pays $205.68"
    wagers     TEXT,
    legs       INTEGER,
    PRIMARY KEY (read_on, card_id)
);

/* One leg of one card, in the order the card shows them. */
CREATE TABLE IF NOT EXISTS score_card_leg (
    read_on    TEXT NOT NULL,
    card_id    TEXT NOT NULL,
    at         INTEGER NOT NULL,   -- its place on the card
    market     TEXT,               -- "Jalen Hurts Touchdowns Scored"
    said       TEXT,               -- "1+"
    odds       TEXT,
    set_at     TEXT,
    PRIMARY KEY (read_on, card_id, at)
);

CREATE INDEX IF NOT EXISTS score_card_leg_market ON score_card_leg (market);
"""

TOKEN = [None]


def flat(obj):
    """The payload as one string, written the way the wire writes it.

       json.dumps puts a space after every colon by default, so a pattern
       matching the book's own "slug":"passing" finds nothing in it. Every
       reading here goes through this, so no pattern has to know that.
    """
    return json.dumps(obj, separators=(",", ":"))


def ask(op, variables, patience=2):
    """One query, asked as the app asks it."""
    h = Q[op]
    url = (BASE + h + "?operationName=" + op + "&variables=" +
           urllib.parse.quote(json.dumps(variables), safe="") +
           "&extensions=" + urllib.parse.quote(json.dumps(
               {"persistedQuery": {"version": 1, "sha256Hash": h}}), safe=""))

    head = ["-H", "accept: application/json",
            "-H", "content-type: application/json",
            "-H", "apollographql-client-name: espnbet-espnbet-web",
            "-H", "apollographql-client-version: 26.16.1",
            "-H", "x-app: espnbet", "-H", "x-client: espnbet",
            "-H", "x-platform: web", "-H", "x-device: DESKTOP",
            "-H", "x-app-version: 26.16.1",
            "-H", "x-install-id: qbspy", "-H", "x-dma: 512"]
    if TOKEN[0]:
        head += ["-H", "x-anonymous-authorization: Bearer " + TOKEN[0]]

    for _ in range(patience):
        out = subprocess.run(["curl", "-s", "--max-time", "40", url] + head,
                             capture_output=True, text=True).stdout
        try:
            return json.loads(out)
        except ValueError:
            time.sleep(1)
    return {}


def token():
    """An anonymous bearer. The book hands one to anybody — it does not care
       what connect token it is shown, or whether it is shown one at all."""
    got = ask("Startup", {"connectToken": ""})
    found = re.search(r'"anonymousToken":"(eyJ[^"]+)"', flat(got))
    return found.group(1) if found else None


def sections(event_id):
    """Every tab on a game, by the address a person would type."""
    got = ask("EventPage", {
        "includeRichEvent": True, "includeStandardizedBoxscore": True,
        "isCfpRankingEnabled": True, "isCombatSportsRedesignEnabled": True,
        "canonicalUrl": "%s/event/%s" % (SITE, event_id)})

    raw = flat(got)
    out = {}
    for m in re.finditer(r'"(Section:[0-9a-f-]{36}:Event:[0-9a-f-]{36})"', raw):
        tail = raw[m.end():m.end() + 300]
        slug = re.search(r'"slug":"([a-z][a-z_-]*)"', tail)
        if slug and slug.group(1) not in out:
            out[slug.group(1)] = m.group(1)

    fixture = re.search(r'"name":"([^"]+ (?:@|vs) [^"]+)"', raw)
    starts = re.search(r'"startTime":"([^"]+)"', raw)
    return out, (fixture.group(1) if fixture else None), \
        (starts.group(1) if starts else None)


def drawers(section_id):
    got = ask("EventSection", {
        "includeFeaturedCarousel": False, "includeQuickBetDetails": False,
        "sectionId": section_id, "selectedMarketId": None})
    part = ((got.get("data") or {}).get("eventSection") or {})
    return [one for one in (part.get("sectionChildren") or [])
            if one.get("groupId")]


def named(market_name):
    """The man a market is about. "Sam Darnold Total Passing Yards" is his;
       "Total Points" is nobody's."""
    cut = re.match(r"^([A-Z][a-zA-Z'\-\.]+(?: [A-Z][a-zA-Z'\-\.]+){1,2})\s+"
                   r"(?:Total|Longest|To |Anytime|First|Last|Alternate)",
                   market_name or "")
    return cut.group(1) if cut else None


def prices(event_id, fixture, starts, tab, drawer, when):
    """One row per selection — the single line a person would follow."""
    got = ask("EventDrawerContent", {
        "isSubscription": False, "pageType": "EVENT",
        "eventDrawerInput": {"groupId": drawer["groupId"],
                             "sectionSlug": tab, "eventId": event_id},
        "oddsFormat": "AMERICAN"})

    rows = []

    def walk(node):
        if isinstance(node, list):
            for one in node:
                walk(one)
            return
        if not isinstance(node, dict):
            return

        if node.get("__typename") == "Market" and node.get("selections"):
            who = named(node.get("name"))
            for pick in node["selections"]:
                name = pick.get("name") or {}
                odds = pick.get("odds") or {}
                rows.append({
                    "read_on": when,
                    "set_at": node.get("updatedAtTime"),
                    "event_id": event_id,
                    "fixture": fixture,
                    "starts": starts,
                    "tab": tab,
                    "drawer": drawer.get("labelText"),
                    "market_id": str(node.get("id") or ""),
                    "market": node.get("name"),
                    "market_type": node.get("type"),
                    "status": node.get("status"),
                    "player": who,
                    "selection_id": str(pick.get("id") or ""),
                    "said": name.get("fullName") or name.get("defaultName"),
                    "short": name.get("minimalName"),
                    "odds": (odds.get("formattedOdds") or "").replace("−", "-")
                            or None,
                })
            return

        for one in node.values():
            walk(one)

    walk(got.get("data"))
    return [one for one in rows if one["selection_id"]]


def cards(event_id, fixture, starts, when):
    """The book's named cards on one game — the carousel on its Popular tab.

       EventSection names the carousel but does not open it: the child comes
       back as a bare reference. Marketplace opens it, and wants the page's
       address as well as the carousel's id.

       This was missed the first time round twice over — the section was
       asked for with includeFeaturedCarousel off, and the drawer filter
       dropped anything without a groupId, which is exactly what a carousel
       is.
    """
    got = ask("Marketplace", {
        "id": "FeaturedMarketsCarousel:Event:" + event_id,
        "canonicalUrl": "%s/event/%s" % (SITE, event_id),
        "oddsFormat": "AMERICAN", "includeRecommendedProps": True,
        "isSubscription": False, "pageType": "EVENT",
        "isBrandingImageEnabled": True,
        "isNewFeaturedBetParticipantLogoEnabled": True,
        "isFeaturedBetCarouselHeaderRedesignEnabled": True,
        "isFeaturedMarketCardRedesignEnabled": True,
        "isDsModelRecommendedPropsEnabled": False,
        "isBlueprintUiFieldEnabled": False,
        "includeStandardizedBoxscore": True, "isCfpRankingEnabled": True,
        "isCombatSportsRedesignEnabled": True, "includeRichEvent": True})

    made, legs = [], []

    def walk(node):
        if isinstance(node, list):
            for one in node:
                walk(one)
            return
        if not isinstance(node, dict):
            return

        if node.get("__typename") == "FeaturedBetParlayCard":
            card_id = str(node.get("id") or "")
            picks = node.get("selections") or []

            made.append({
                "read_on": when, "event_id": event_id, "card_id": card_id,
                "fixture": fixture, "starts": starts,
                "title": node.get("title"), "header": node.get("header"),
                "kind": node.get("parlayType"),
                "odds": (node.get("odds") or {}).get("formattedOdds"),
                "payout": node.get("estimatedPayout"),
                "wagers": node.get("numberOfWagers") or None,
                "legs": len(picks),
            })

            for at, leg in enumerate(picks, 1):
                market = leg.get("market") or {}
                said = None
                for pick in market.get("selections") or []:
                    name = pick.get("name") or {}
                    said = name.get("fullName") or name.get("defaultName")
                    break
                legs.append({
                    "read_on": when, "card_id": card_id, "at": at,
                    "market": market.get("name"),
                    "said": said,
                    "odds": (leg.get("odds") or {}).get("formattedOdds"),
                    "set_at": market.get("updatedAtTime"),
                })
            return

        for one in node.values():
            walk(one)

    walk(got.get("data"))
    return made, legs


def lounge(when):
    """The Parlay Lounge — the book's cards for the whole competition.

       Every card above sits on one game's Popular carousel and is asked for
       by that game's id. A card spanning two games is on neither: "Send 'Em
       Deep" is a touchdown in Cincinnati, two in Detroit and one in Houston,
       and it lives at the league's own address instead. Fetching game by
       game, every cross-game card theScore publishes was missed.

       The cards come back in exactly the shape a game's carousel gives, so
       they are written to the same two tables. `event_id` is the lounge
       rather than a fixture, and the fixture is left empty — a card across
       three games has no single one, and export_cards.py takes its week from
       the clubs its legs name.
    """
    got = ask("Marketplace", {
        "canonicalUrl": "/parlay-lounge/section/nfl",
        "oddsFormat": "AMERICAN",
        "includeRecommendedProps": False, "includeRichEvent": False})

    made, legs = [], []

    def walk(node):
        if isinstance(node, list):
            for one in node:
                walk(one)
            return
        if not isinstance(node, dict):
            return

        if node.get("__typename") == "FeaturedBetParlayCard":
            card_id = str(node.get("id") or "")
            picks = node.get("selections") or []
            made.append({
                "read_on": when, "event_id": "parlay-lounge", "card_id": card_id,
                "fixture": None, "starts": node.get("startTime"),
                "title": node.get("title"), "header": node.get("header"),
                "kind": node.get("parlayType"),
                "odds": (node.get("odds") or {}).get("formattedOdds"),
                "payout": node.get("estimatedPayout"),
                "wagers": node.get("numberOfWagers") or None,
                "legs": len(picks),
            })
            for at, leg in enumerate(picks, 1):
                market = leg.get("market") or {}
                said = leg.get("selectionName")
                if not said:
                    for pick in market.get("selections") or []:
                        name = pick.get("name") or {}
                        said = name.get("fullName") or name.get("defaultName")
                        break
                legs.append({
                    "read_on": when, "card_id": card_id, "at": at,
                    "market": leg.get("marketName") or market.get("name"),
                    "said": said,
                    "odds": (leg.get("odds") or {}).get("formattedOdds"),
                    "set_at": market.get("updatedAtTime"),
                })
            return

        for one in node.values():
            walk(one)

    walk(got.get("data"))
    return made, legs


def slate():
    """Every NFL game theScore has, from its own media feed — the two share
       nothing but the fixtures, and that feed needs no token at all."""
    out = subprocess.run(["curl", "-s", "--max-time", "40", "-A", "Mozilla/5.0",
                          "https://api.thescore.com/nfl/events?limit=400"],
                         capture_output=True, text=True).stdout
    try:
        return json.loads(out)
    except ValueError:
        return []


def main():
    only = None
    if "--games" in sys.argv:
        only = int(sys.argv[sys.argv.index("--games") + 1])

    db = open_db()
    patiently(lambda: db.executescript(SCHEMA))

    TOKEN[0] = token()
    if not TOKEN[0]:
        sys.exit("no token — theScore has redeployed and the Startup hash is "
                 "stale. Capture a HAR of a page load and read the new one.")
    print("token minted\n")

    # The book's game ids are its own — the media feed's numbers mean nothing
    # here. The competition page names its tabs; the Lines tab holds the
    # slate. Both are found by asking, so a new week needs no new address.
    page = ask("EventPage", {"includeRichEvent": True,
                             "includeStandardizedBoxscore": True,
                             "isCfpRankingEnabled": True,
                             "isCombatSportsRedesignEnabled": True,
                             "canonicalUrl": SITE})

    lines_id = None
    for m in re.finditer(r'"(Section:[0-9a-f-]{36})","label":"([^"]+)"',
                         flat(page)):
        if m.group(2).lower() == "lines":
            lines_id = m.group(1)
            break
    if not lines_id:
        found = re.search(r'"(Section:[0-9a-f-]{36})"', flat(page))
        lines_id = found.group(1) if found else None

    slate_page = ask("CompetitionPageSectionLinesTabNode", {
        "isSubscription": False, "pageType": "PAGE",
        "includeRecommendedProps": True, "isBrandingImageEnabled": True,
        "isNewFeaturedBetParticipantLogoEnabled": True,
        "isFeaturedBetCarouselHeaderRedesignEnabled": True,
        "includeStandardizedBoxscore": True, "isCfpRankingEnabled": True,
        "isCombatSportsRedesignEnabled": True,
        "isFeaturedMarketCardRedesignEnabled": True,
        "isDsModelRecommendedPropsEnabled": False,
        "isBlueprintUiFieldEnabled": False, "includeRichEvent": True,
        "oddsFormat": "AMERICAN", "sectionId": lines_id,
        "selectedFilterId": ""})

    ids = []
    for one in re.findall(r'Event:([0-9a-f-]{36})', flat(slate_page)):
        if one not in ids:
            ids.append(one)

    if not ids:
        sys.exit("no games listed — the competition page answered nothing")

    if only:
        ids = ids[:only]
    print("%d games\n" % len(ids))

    when = time.strftime("%Y-%m-%dT%H:%M:%S")
    total = 0

    # The Parlay Lounge first: the competition's own cards, the ones that
    # belong to no single game.
    made, legs = lounge(when)
    if made:
        put_many(db, "score_card", made)
        put_many(db, "score_card_leg", legs)
        patiently(db.commit)
    print("parlay lounge   %d cards, %d legs\n" % (len(made), len(legs)))

    for at, event in enumerate(ids, 1):
        tabs, fixture, starts = sections(event)
        wanted = {k: v for k, v in tabs.items()
                  if "--qb" not in sys.argv or k in QB_TABS}

        # The named cards first — they are the thing a person sees before any
        # single line, and they belong to whoever is on them.
        made, legs = cards(event, fixture, starts, when)
        if made:
            put_many(db, "score_card", made)
            put_many(db, "score_card_leg", legs)
            patiently(db.commit)

        kept = 0
        for tab, section in wanted.items():
            for drawer in drawers(section):
                rows = prices(event, fixture, starts, tab, drawer, when)
                if rows:
                    put_many(db, "score_prop", rows)
                    patiently(db.commit)
                    kept += len(rows)
            time.sleep(0.1)

        total += kept
        print("%2d/%d  %-34s %4d lines, %d cards"
              % (at, len(ids), (fixture or event)[:34], kept, len(made)))

    print("\n%d lines this pass" % total)
    print("held: %d lines, %d games, %d men"
          % (value(db, "SELECT COUNT(*) FROM score_prop", default=0),
             value(db, "SELECT COUNT(DISTINCT event_id) FROM score_prop", default=0),
             value(db, "SELECT COUNT(DISTINCT player) FROM score_prop "
                       "WHERE player IS NOT NULL", default=0)))


if __name__ == "__main__":
    main()
