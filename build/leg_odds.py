"""What every source charges for the same leg.

   A card's price is the product of its legs, and until now only two of the
   five sources handed us a leg's own price. The other three publish a card
   price and nothing under it, so nothing could be checked: a card read
   "-185" and there was no way to tell whether that was the card, one leg of
   it, or a misread field.

   This is the other half. Every price any source publishes is folded into
   one book, keyed by what the leg *says* rather than by how a source spells
   it — the same `read_leg` the site renders with, so the key is built the
   same way on both sides and there is no second, quieter normaliser to keep
   in step.

   The house rule holds throughout: **when sources disagree the disagreement
   is kept, never averaged.** `quotes()` hands back every price found, each
   with the source that wrote it and when. Picking one is the caller's job,
   and it picks by named preference, not by arithmetic.
"""
import re
from store import rows
from export_cards import read_leg, club_short, plain


# Which source to believe when several price the same leg. The book that
# sold the card comes first — its own price is what a reader would have
# been charged — then the two that publish the deepest boards.
TRUST = ["own", "dk", "score", "hub", "espn"]


def _figure_in(said, points):
    """DraftKings keeps the number beside the leg, not in it.

       Their row says "Over" with 1.5 in `points`; theScore says
       "Over 1.5" outright. Keyed as they come the same leg lands in two
       places and neither finds the other.
    """
    said = (said or "").strip()
    if points is None or str(points).strip() == "":
        return said
    if re.search(r"\b(over|under)\s*$", said, flags=re.I):
        return "%s %s" % (said, str(points).strip())
    return said


def key_of(said, market):
    """A leg, as the site says it — the key both sides are built with.

       A club is keyed by its three letters, never by how a source wrote
       it. DraftKings' board says "NYJ Jets" and FanDuel's card says "New
       York Jets", and keyed as written those are two different teams: 350
       result legs went unpriced against a board that prices every one of
       them. The register in `club_short` already holds every spelling
       against its abbreviation, which is the whole reason it exists.
    """
    read = read_leg(said, market)
    says = (read.get("says") or "").strip()
    figure = (read.get("figure") or "").strip()
    if not says:
        return None

    return key_from(says, figure, read.get("kind"))


def key_from(says, figure, kind):
    """The same key, from a leg that has already been read once.

       A published leg carries its own `says`, `figure` and `kind` — the
       three fields the site renders — so it is keyed from those rather
       than by putting the words back through the reader a second time and
       hoping it lands the same way.
    """
    says = (says or "").strip()
    figure = (figure or "").strip()
    if not says:
        return None
    if kind == "Win":
        abbr = _abbr(says)
        return (abbr.lower(), "win") if abbr else None

    # "Derrick Henry · TD" — the man, then what he has to do. The man is
    # keyed by his id and the rest by what it says, so the same leg keys
    # the same however the board that wrote it spells him.
    who, _, rest = says.partition(" · ")
    found = men().get(plain(who).strip().lower())
    if found:
        return (found, rest.strip().lower(), figure.lower())

    return (says.lower(), figure.lower())


_MEN = None


def men():
    """Every spelling of every man, against the one id that is him.

       FanDuel writes "D.Henry", "A.St. Brown", "J.Gibbs"; every other
       board writes the name out. Keyed as written those are different
       people, and a hundred and twenty FanDuel legs went unpriced against
       boards that price all of them. `person_name` exists for exactly this
       and is the only thing allowed to answer it.

       A spelling that two men could answer to is left out rather than
       guessed at. It is counted by `build/people.py` and settled there,
       where the clubs on the field that day can be seen; here there is
       nothing to settle it with, and a wrong man is worse than no price.
    """
    global _MEN
    if _MEN is not None:
        return _MEN

    from store import open_db
    seen = {}
    for row in open_db().execute("SELECT written, person_id FROM person_name"):
        key = plain(row["written"] or "").strip().lower()
        if not key:
            continue
        if key in seen and seen[key] != row["person_id"]:
            seen[key] = None          # two men, one spelling: unsettled
        else:
            seen.setdefault(key, row["person_id"])
    _MEN = {said: who for said, who in seen.items() if who}
    return _MEN


_CLUB_SAID = None


def _abbr(said):
    """Three letters for a club, however it was written.

       Out of `club_name`, which was harvested from what the sources
       actually write — "LA Rams", "NY Jets", "WAS Commanders" among them.
       `club_short` is kept behind it as the fallback it has always been,
       for a spelling nobody has written down yet.
    """
    global _CLUB_SAID
    said = (said or "").strip().lower()
    if not said:
        return None

    if _CLUB_SAID is None:
        from store import open_db
        _CLUB_SAID = {}
        try:
            for row in open_db().execute("SELECT written, abbr FROM club_name"):
                _CLUB_SAID[row["written"].strip().lower()] = row["abbr"]
        except Exception:
            _CLUB_SAID = {}

    return _CLUB_SAID.get(said) or club_short().get(said)


# A leg is one thing happening. "Matthew Stafford To Throw Over 1.5 Passing
# Touchdowns & Brock Purdy To Throw Over 1.5" is two, sold as one, and it
# keys as whichever man is written first — which is how a two-man special
# came to sit in the book as a price for one man's leg. Both halves of the
# test are needed: the ampersand catches the written ones, and Yes/No
# catches the rest, since a plain leg never answers Yes.
BOTH = re.compile(r"\s&\s|\bEach\b|\bBoth\b", re.I)


def _one_thing(said, market):
    if BOTH.search(market or "") or BOTH.search(said or ""):
        return False
    return (said or "").strip().lower() not in ("yes", "no")


def price_book(db):
    """Every priced leg on every board, keyed by what it says.

       Only the newest sweep of each source is read, and a sweep is taken
       to be a day rather than an instant: DraftKings stamps every row with
       its own second, so "the newest reading" read literally is the last
       second of the sweep and nearly none of the board.

       An older sweep is a
       price that was true last night, and a card checked against last
       night's number disagrees with the board for a reason that has
       nothing to do with the card.

       Where a source prices the same leg twice at one reading — theScore
       sells Stafford's second passing score as both "2+" at -140 and
       "Over 1.5" at -150 — both are kept. That is a conflict in their own
       board, and the house rule is that a conflict is logged, not averaged
       away.
    """
    book = {}

    def keep(said, market, odds, source, read_on):
        if not odds or str(odds).strip() in ("", "None"):
            return
        if not _one_thing(said, market):
            return
        key = key_of(said, market)
        if not key:
            return
        book.setdefault(key, []).append(
            {"source": source, "odds": str(odds).strip(), "read_on": read_on})

    for row in db.execute("""SELECT said, points, market, odds, read_on,
                                     fixture
                               FROM dk_prop WHERE odds IS NOT NULL
                                AND substr(read_on,1,10) = (SELECT MAX(substr(read_on,1,10)) FROM dk_prop)"""):
        # Season fixtures sell season sentences — "50+ receiving yards in
        # every game (all 17)" — and boiled to a figure they key exactly
        # like one Sunday's leg. A.J. Brown's -188 printed as +4000 for
        # that reason. A leg's price only ever comes from a game.
        if str(row["fixture"] or "").startswith("NFL "):
            continue
        keep(_figure_in(row["said"], row["points"]), row["market"],
             row["odds"], "dk", row["read_on"])

    for row in db.execute("""SELECT said, market, odds, read_on
                               FROM score_prop WHERE odds IS NOT NULL
                                AND substr(read_on,1,10) = (SELECT MAX(substr(read_on,1,10)) FROM score_prop)"""):
        keep(row["said"], row["market"], row["odds"], "score", row["read_on"])

    # The hub's own per-fixture board — six hundred priced selections a
    # game, and the only place that sells a man's second touchdown, his
    # third, or the alt-yards ladder rung by rung. Three hundred and forty
    # legs sat unpriced with a note saying no board sold them singly; this
    # is the board that does, and it had been sitting behind a page nobody
    # fetched.
    for row in db.execute("""SELECT player, market, odds, read_on
                               FROM hub_prop WHERE odds IS NOT NULL
                                AND substr(read_on,1,10) =
                                    (SELECT MAX(substr(read_on,1,10)) FROM hub_prop)"""):
        said = row["player"] or ""
        market = row["market"] or ""
        # "2+ TDs" is the hub's shorthand and reads as no kind at all — the
        # reader wants the word. Written out, the leg keys as the touchdown
        # leg it plainly is.
        market = re.sub(r"\bTDs?\b", "Touchdowns", market)
        if said and not market.lower().startswith(said.lower().split()[0].lower()):
            market = "%s %s" % (said, market)
        keep(said, market, row["odds"], "hub", row["read_on"])

    # DraftKings' main board — the spread, the total and the result, which
    # no prop table carries and which half the cards are built out of.
    for row in db.execute("""SELECT said, line, market, fixture, odds, read_on
                               FROM dk_market WHERE odds IS NOT NULL
                                AND substr(read_on,1,10) = (SELECT MAX(substr(read_on,1,10)) FROM dk_market)"""):
        keep(_figure_in(row["said"], row["line"]),
             "%s %s" % (row["fixture"] or "", row["market"] or ""),
             row["odds"], "dk", row["read_on"])

    # A day holds several sweeps. Kept as they come, one leg carries the
    # same price six times over — once per sweep — and the two prices that
    # actually differ are lost in the repetition. One row per distinct
    # price per source, stamped with when it was last seen: repetition
    # gone, the disagreement still standing.
    for key, found in book.items():
        found.sort(key=lambda one: str(one["read_on"]), reverse=True)
        kept, seen = [], set()
        for one in found:
            mark = (one["source"], one["odds"])
            if mark in seen:
                continue
            seen.add(mark)
            kept.append(one)
        book[key] = kept
    return book


def moves(db):
    """What ESPN says a figure opened at and stands at now.

       Not a price — a line move. A leg written against a figure that has
       since moved is a leg whose price is stale whatever the price says,
       and that is worth showing beside the number rather than hiding.
    """
    out = {}
    for row in db.execute("""SELECT written, club, market, opened, now,
                                    over_odds, under_odds, kickoff
                               FROM line_move"""):
        who = (row["written"] or row["club"] or "").strip()
        if not who:
            continue
        out.setdefault(who.lower(), []).append(dict(row))
    return out


def quotes(book, said, market, own=None):
    """Every price found for one leg, the trusted one first.

       `own` is the price the book that sold the card put on the leg, where
       it published one. It is not merged with the rest and it does not
       overrule them — it is simply first in the list, and marked as whose.
    """
    found = []
    if own and str(own).strip() not in ("", "None"):
        found.append({"source": "own", "odds": str(own).strip(),
                      "read_on": None})
    key = key_of(said, market)
    if key:
        seen = set()
        for one in book.get(key, []):
            if one["source"] in seen:
                continue
            seen.add(one["source"])
            found.append(one)
    order = {name: at for at, name in enumerate(TRUST)}
    found.sort(key=lambda one: order.get(one["source"], 99))
    return found


def ladders(book):
    """Every man's priced rungs, per stat, sorted by the number.

       Built from the same book the legs are priced from, so a rung here is
       a rung a board actually sells. It exists for the legs a card writes
       at its own number — "Sam Darnold 234+" — which no board sells alone:
       the rungs either side of it are real prices, and shown as the
       neighbours they are, they say what the leg is worth without a number
       being invented for it.
    """
    import re as _re
    out = {}
    for key, found in book.items():
        if len(key) != 3:
            continue
        who, what, figure = key
        step = _re.fullmatch(r"(\d+)\+", figure or "")
        side = _re.fullmatch(r"(?:(o|over)|(u|under))\s*(\d+(?:\.\d+)?)",
                             figure or "", flags=_re.I)
        if not step and not side:
            continue
        best_here = min(found, key=lambda one: TRUST.index(one["source"])
                        if one["source"] in TRUST else 99)
        if step:
            out.setdefault((who, what), []).append(
                (int(step.group(1)), figure, best_here["odds"],
                 best_here["source"]))
        else:
            way = "over" if side.group(1) else "under"
            out.setdefault((who, "%s %s" % (what, way)), []).append(
                (float(side.group(3)), figure, best_here["odds"],
                 best_here["source"]))
    for rungs in out.values():
        rungs.sort()
    return out


def around(rungs, number):
    """The rung at or just under a number, and the one just over it."""
    below = above = None
    for at, figure, odds, source in rungs or []:
        if at <= number:
            below = {"figure": figure, "odds": odds, "source": source}
        elif above is None:
            above = {"figure": figure, "odds": odds, "source": source}
            break
    return below, above
