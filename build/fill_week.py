"""Prices for the drawn weeks: every game still to kick, from DraftKings.

   Week one's cards were built by hand, prices and all. Every later week is
   drawn from the schedule with an empty slot where each price goes, and
   nothing was filling those slots -- refresh.py reprices only ids it already
   knows, fill_nfl.py edits only hand-built cards. This asks DraftKings for
   each unkicked game and writes what it prices into PROPS (the drawn cards
   read it) and the moneyline fields of the schedule rows.

   NFL: moneyline, passing touchdowns 1+/2+, head to head when it is posted.
   College: moneyline, anytime touchdown (1+ = anytime, 2+ = "2+ TDs"),
   passing touchdowns 1+/2+. Only the two passers the card names.

   A DraftKings event is tied to a card through the club register (its team
   names are looked up, never guessed) and a passer through person_name --
   a college passer the register does not hold is matched only when the
   written name is identical, and that is counted and printed.

   Usage:  python3 fill_week.py          (writes and deploys)
           python3 fill_week.py --dry
"""
import datetime as dt
import json
import os
import re
import sqlite3
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile
import whoname
import prices as pricefile
from read_dk import ask

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY = "--dry" in sys.argv
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "qbspy.db")
NOW = dt.datetime.now(dt.timezone.utc)
HORIZON = NOW + dt.timedelta(days=8)
LEAGUE = {"nfl": 88808, "ncaaf": 87637}


def full(eid):
    """The eight a game is worth: a moneyline each club, 1+ and 2+ passing
       touchdowns each passer, an anytime touchdown each passer. Once all
       eight are held there is nothing left to ask DraftKings about that
       game, so it is not asked about again (Jose, Sep 22, 2026: "so we stop
       running to fetch the ones we have already... if we only get 1 we would
       have to search for 127").

       A week is a hundred and twenty-eight of these across sixteen games.
       Early in the week almost none are held and every game is asked about;
       by Saturday the asking has stopped on its own."""
    f = os.path.join(D, "site", "prices", "%s.json" % eid)
    if not os.path.exists(f):
        return False
    try:
        d = json.load(open(f))
    except ValueError:
        return False
    ml = d.get("ml") or []
    if len(ml) < 4 or not ml[0] or not ml[2]:
        return False
    pr = d.get("props") or {}
    for k, rungs in (("ptd", (0, 1)), ("atd", (0,))):
        v = pr.get(k) or []
        if len(v) < 2:
            return False
        for side in v:
            if not isinstance(side, list):
                return False
            for r in rungs:
                if len(side) <= r or not side[r]:
                    return False
    return True


def T(x):
    return dt.datetime.fromisoformat(x.replace("Z", "+00:00"))


def register():
    db = sqlite3.connect(DB)
    club = {w: a for w, a in db.execute("select written, abbr from club_name")}
    person = {w: str(p) for w, p in db.execute("select written, person_id from person_name")}
    return club, person


def pull(path):
    d = ask(None, None, path) or {}
    mk = {m["id"]: m for m in d.get("markets") or []}
    rows = []
    for sel in d.get("selections") or []:
        m = mk.get(sel.get("marketId")) or {}
        who = (sel.get("participants") or [{}])[0]
        rows.append({"market": m.get("name") or "", "label": sel.get("label") or "",
                     "odds": (sel.get("displayOdds") or {}).get("american") or "",
                     "oid": sel.get("id") or "", "who": who.get("name") or "",
                     # the handicap on a selection: the rung a touchdown market
                     # is set at, and nothing else -- spread and total are not kept
                     "points": sel.get("points"),
                     # his DraftKings number, and which half of the fixture he
                     # is on. The name is not read at all now: a man is his id
                     # (Jose, Sep 22, 2026: "why are we guessing name they wont
                     # fucking change")
                     "pid": str(who.get("id") or ""),
                     "role": who.get("venueRole") or ""})
    return rows


def american(o):
    return str(o).replace("−", "-")


def dk_events(league):
    d = ask(None, None, "/sportscontent/dkusmd/v1/leagues/%d" % LEAGUE[league]) or {}
    out = []
    for e in d.get("events") or []:
        name = e.get("name") or ""
        if " @ " not in name:
            continue
        away, home = name.split(" @ ", 1)
        out.append({"id": str(e["id"]), "away": away.strip(), "home": home.strip(),
                    "start": e.get("startEventDate") or ""})
    return out


_H2H = None


def league_h2h(dk_event):
    """The league-wide head-to-head list, pulled once, rows for this event."""
    global _H2H
    if _H2H is None:
        d = ask(None, None, "/sportscontent/dkusmd/v1/leagues/88808/categories/1185/subcategories/11977") or {}
        mk = {m["id"]: m for m in d.get("markets") or []}
        _H2H = []
        for sel in d.get("selections") or []:
            m = mk.get(sel.get("marketId")) or {}
            who = (sel.get("participants") or [{}])[0]
            _H2H.append({"event": str(m.get("eventId")), "market": m.get("name") or "", "label": sel.get("label") or "",
                         "odds": (sel.get("displayOdds") or {}).get("american") or "", "oid": sel.get("id") or "",
                         "who": who.get("name") or ""})
    return [r for r in _H2H if r["event"] == str(dk_event)]


def side_of(label, away_w, home_w):
    if label == away_w:
        return 0
    if label == home_w:
        return 1
    return None


# The three steps below were the body of main() until the double tap needed
# them one game at a time. ask_dk.py prices the games the board asks about
# with exactly these, so a price read on a tap and a price read by the sweep
# are the same reading of the same thing (Jose, Sep 23, 2026).

def tie_events(league, events, club, cfb, unsettled=None):
    """DraftKings' events keyed by (away, home, day) in the board's own
       abbreviations, through the register -- never by a guess."""
    keyed = {}
    for e in events:
        # college first: DraftKings' "Pittsburgh" is PITT on a Saturday, and the NFL
        # register answering PIT left twelve games unpriced on Sep 16, 2026
        a = (cfb.get(e["away"]) or club.get(e["away"])) if league == "ncaaf" else (club.get(e["away"]) or cfb.get(e["away"]))
        h = (cfb.get(e["home"]) or club.get(e["home"])) if league == "ncaaf" else (club.get(e["home"]) or cfb.get(e["home"]))
        if a and h:
            keyed[(a, h, e["start"][:10])] = e
        elif league == "nfl" and unsettled is not None:
            unsettled.append(e["away"] + " @ " + e["home"])
    return keyed


def event_for(g, league, keyed, events, club, cfb, loose=True):
    """The DraftKings event a schedule row stands for.

       Returns (event, how). how is None for a straight tie, "flipped" for a
       neutral site DraftKings lists the other way round, "by_name" for the
       college prefix fallback (only when loose); with no event it is
       "unoffered" (neither club is on their board) or "unsettled"."""
    away, home, kick = g[3], g[4], T(g[2])
    e = keyed.get((away, home, g[2][:10])) or keyed.get((away, home, (kick - dt.timedelta(days=1)).strftime("%Y-%m-%d")))
    if e:
        return e, None
    # a neutral-site game DraftKings lists the other way round from ESPN
    # (Kansas @ Arizona State at Wembley, Sep 19, 2026). Taken, and said.
    r = keyed.get((home, away, g[2][:10]))
    if r:
        return dict(r, away=r["home"], home=r["away"]), "flipped"
    if loose and league == "ncaaf":
        # the register may not hold the college spelling: same day, same abbreviation prefix
        cands = [x for x in events if x["start"][:10] == g[2][:10]
                 and x["away"].split()[0].upper() == away and x["home"].split()[0].upper() == home]
        if len(cands) == 1:
            return cands[0], "by_name"
    offered = {x for ev in events for x in (cfb.get(ev["away"]) or club.get(ev["away"]), cfb.get(ev["home"]) or club.get(ev["home"]))}
    if away not in offered and home not in offered:
        return None, "unoffered"
    return None, "unsettled"


NEWPINS = {}


def price_event(e, qbs_id, league, dkpeople, names=None):
    """One DraftKings event, read: the moneyline as {side: (price, oid)},
       and the PROPS entry -- ptd, atd, h2h -- for the two passers named."""
    qbs_id = [str(x) for x in qbs_id]
    ml, entry = {}, {}
    # who a price belongs to, by number. dk_people.json pins a
    # DraftKings id to ours, once, under a rule that cannot pick the
    # wrong man -- see build/dk_people.py. An id that is not pinned is
    # not priced: an unknown man draws nothing rather than somebody
    # else's price.
    def his_side(r):
        who = dkpeople.get(r.get("pid") or "")
        if not who and r.get("pid") and names:
            # a man DraftKings numbers but we have not pinned: his written name
            # against the two passers on this card, the only two men it could
            # be. One match pins him for good; both, or neither, and he is
            # left alone. Mason McKenzie's prices were thrown away for want
            # of a pin while the book priced him (Jose, Sep 26, 2026)
            bare = re.sub(r"\s*\([A-Za-z&.\- ]+\)$", "", r.get("who") or "")
            hit = [i for i in (0, 1) if names[i] and whoname.same(bare, names[i])]
            if len(hit) == 1:
                who = {"espn": qbs_id[hit[0]], "name": names[hit[0]]}
                dkpeople[r["pid"]] = who
                NEWPINS[r["pid"]] = who
        if not who:
            return None
        for i in (0, 1):
            if str(qbs_id[i]) == str(who["espn"]):
                return i
        return None
    # the game lines: the moneyline is the only one we keep. The board
    # is about the passer, and spread and total are game numbers nobody
    # on the card is asked about (Jose, Sep 22, 2026: "spread / total
    # dont do this ... just in general"). The one-passing-touchdown rule
    # still reads both, from ESPN, in ptd10.py.
    lines = pull("/sportscontent/dkusmd/v1/events/%s/categories/492" % e["id"])
    for r in lines:
        if r["market"] != "Moneyline":
            continue
        i = side_of(r["label"], e["away"], e["home"])
        if i is not None:
            ml[i] = (american(r["odds"]), r["oid"])
    # the whole passing-touchdown ladder DraftKings sells, 1+ up to whatever
    # its top rung is (Jose, Sep 28, 2026: Shough threw four and the board
    # had kept only 1+ to 3+, so his 4+ never counted)
    ptd = [[None, None, None], [None, None, None]]
    # every passer DraftKings prices a side for, whoever the card names: the
    # book's word on who starts (Jose, Sep 25, 2026: "dk should confirm").
    # venueRole says which half of the fixture he is on, in DraftKings' own
    # order; the caller turns that into the board's
    entry["_qb"] = {}
    for r in pull("/sportscontent/dkusmd/v1/events/%s/categories/1000" % e["id"]):
        if r["market"].endswith("Passing Touchdowns") and r["pid"] and r["role"].lower() in ("away", "home"):
            entry["_qb"].setdefault(r["role"].lower(), {})[r["pid"]] = re.sub(r"\s*\([A-Za-z&.\- ]+\)$", "", r["who"])
        m = re.match(r"^(\d+)\+$", str(r["label"]).strip())
        if not r["market"].endswith("Passing Touchdowns") or not m:
            continue
        i = his_side(r)
        if i is not None:
            k = int(m.group(1)) - 1
            while len(ptd[i]) <= k:
                ptd[i].append(None)
            ptd[i][k] = [american(r["odds"]), r["oid"]]
    entry["ptd"] = ptd
    # anytime touchdowns for both leagues: the college card draws them, the
    # NFL card does not, but the ledger tracks them (Jose, Sep 16, 2026:
    # "I want all the ptd and atd that are available and we will just track them all")
    # anytime, 2+ and 3+ touchdowns. The market name is matched whole:
    # "Anytime TD Scorer - 1st Half" begins the same way, and taking it
    # put a first-half price on the card as if it were the game's
    # (Jose, Sep 22, 2026 -- Chambliss read +255, which is his first
    # half; anytime is +125).
    RUNGS = {"Anytime TD Scorer": 0, "2+ TDs": 1, "3+ TDs": 2}
    atd = [[None, None, None], [None, None, None]]
    for r in pull("/sportscontent/dkusmd/v1/events/%s/categories/1003" % e["id"]):
        slot = RUNGS.get(r["market"])
        if slot is None:
            continue
        i = his_side(r)
        if i is not None:
            atd[i][slot] = [american(r["odds"]), r["oid"]]
    entry["atd"] = atd
    # the head to head, both leagues (Jose, Sep 17, 2026: college carries it
    # too, so the two boards read the same). College's 1185 also holds the
    # receivers and the spread version, so only the passers' moneyline counts.
    h2h = [None, None]
    # served under the event, or league-wide (where it sat last week)
    rows = pull("/sportscontent/dkusmd/v1/events/%s/categories/1185" % e["id"])
    if not rows and league == "nfl":
        rows = [r for r in league_h2h(e["id"])]
    for r in rows:
        if "Passing Yards Moneyline" not in (r["market"] or ""):
            continue
        i = his_side(r)
        if i is not None:
            h2h[i] = [american(r["odds"]), r["oid"]]
    entry["h2h"] = h2h
    return ml, entry


def main():
    s = pagefile.read()
    club, person = register()
    # college passers pinned to their ESPN id as DraftKings writes them; a man first
    # met by an identical written name on his own card is written here, so the pin
    # is a recorded fact after that and not a match made again at read time
    pins_path = D + "/data/cfb_people.json"
    pins = json.load(open(pins_path)) if os.path.exists(pins_path) else {}
    new_pins = {}
    props = {}
    unsettled, by_name, flipped, unoffered = [], [], [], []
    held = []
    both_ways = []
    dk_qbs = {}
    sched_new = {}
    # DraftKings' number for a man, pinned to ours by build/dk_people.py
    dkp = os.path.join(D, "data", "dk_people.json")
    dkpeople = json.load(open(dkp)) if os.path.exists(dkp) else {}
    print("dk_people.json: %d men pinned" % len(dkpeople))

    for league, var in (("nfl", "SCHED"), ("ncaaf", "CFB")):
        arr = json.loads(re.search(r"var %s = (\[\[.*?\]\]);" % var, s, re.S).group(1))
        games = [g for g in arr if NOW < T(g[2]) <= HORIZON]
        if not games:
            continue
        events = dk_events(league)
        # college spellings come from ESPN's own scoreboard (cfb_names.json), the
        # same source the board's abbreviations come from
        cfb = json.load(open(D + "/data/cfb_names.json")) if league == "ncaaf" else {}
        keyed = tie_events(league, events, club, cfb, unsettled)
        print("%s: %d games to kick, %d DraftKings events, %d tied by the register"
              % (league.upper(), len(games), len(events), len(keyed)))
        for g in games:
            eid, kick, away, home = g[1], T(g[2]), g[3], g[4]
            e, how = event_for(g, league, keyed, events, club, cfb)
            if how == "flipped":
                flipped.append("%s/%s (DraftKings writes %s @ %s)" % (away, home, e["home"], e["away"]))
            elif how == "by_name":
                by_name.append(away + "/" + home)
            elif how == "unoffered":
                unoffered.append("%s/%s" % (away, home))
                continue
            elif how == "unsettled":
                unsettled.append("%s/%s (%s)" % (away, home, league))
                continue
            if full(str(eid)):
                held.append("%s/%s" % (away, home))
                continue
            # the two passers, by id through person_name; else the identical written name
            qbs = [(g[5], str(g[6])), (g[7], str(g[8]))]
            qbs_id = [str(g[6]), str(g[8])]
            def is_him(written, i):
                name, pid = qbs[i]
                if not name:
                    return False
                # DraftKings tags college men with their club, "Jayden Maiava (USC)";
                # the tag is not part of the name and the register never saw it
                bare = re.sub(r"\s*\([A-Za-z&.\- ]+\)$", "", written or "")
                if person.get(bare) == pid or pins.get(bare) == pid:
                    return True
                # A written name is enough in the NFL, where there are thirty-two
                # rosters and the two passers in front of us are the only men it
                # could be. It is not enough in college. Matched by name there,
                # a third of the anytime-touchdown prices we took were shorter
                # than -150 -- running back prices on a quarterback's card,
                # against one in seventy-two in the NFL. College is matched by
                # id or not at all (Jose, Sep 22, 2026: "we should have NFL and
                # CFB in different").
                if league == "ncaaf":
                    return False
                # a suffix, an accent or a full stop does not make another man:
                # theirs is Billy Edwards where ours is Billy Edwards Jr., and
                # the two passers in front of us are the only men it could be
                # (Jose, Sep 19, 2026: "we shouldn't get hung up on names")
                if whoname.same(bare, name):
                    other = qbs[1 - i][0]
                    if other and whoname.same(bare, other):
                        both_ways.append(bare)     # said, never guessed
                        return False
                    return True
                return False
            ml, entry = price_event(e, qbs_id, league, dkpeople, [g[5], g[7]])
            # the book's passers, by side on the board, as ESPN ids where we
            # hold the pin; a man we cannot pin is kept by name and said
            seen_qb = entry.pop("_qb", {})
            dkq = [[], []]
            for role, men in seen_qb.items():
                side = 0 if role == "away" else 1
                if how == "flipped":
                    side = 1 - side
                for pid, nm in men.items():
                    espn = (dkpeople.get(pid) or {}).get("espn") or pins.get(nm) or ""
                    dkq[side].append([str(espn), nm])
            dk_qbs[str(eid)] = dkq
            for i, v in ml.items():
                sched_new[(var, eid, i)] = v
            ptd = entry["ptd"]
            props[eid] = entry
            got = sum(1 for side in ptd for x in side if x)
            print("  %-9s dk %-9s ML %s  PTD %d/4  ATD %d/4%s" % (away + "/" + home, e["id"],
                  "yes" if (var, eid, 0) in sched_new else "no", got,
                  sum(1 for side in entry.get("atd", []) for x in side if x),
                  "  H2H %d/2" % sum(1 for x in entry.get("h2h", []) if x)))
    if unsettled:
        print("not tied to a DraftKings event (%d): %s" % (len(unsettled), "; ".join(sorted(set(unsettled))[:12])))
    if held:
        print("already complete, not asked about again (%d games, %d prices held): %s"
              % (len(held), len(held) * 8, ", ".join(held[:10]) + (" ..." if len(held) > 10 else "")))
    if flipped:
        print("home and away disagree with DraftKings, board order kept (%d): %s" % (len(flipped), "; ".join(flipped)))
    if unoffered:
        print("DraftKings offers nothing on (%d): %s" % (len(unoffered), "; ".join(unoffered)))
    if by_name:
        print("pinned on an identical written name on his own card, now in cfb_people.json (%d): %s" % (len(set(by_name)), ", ".join(sorted(set(by_name))[:10])))
    if both_ways:
        print("a written name that fits both passers in the same game, so neither took it (%d): %s"
              % (len(set(both_ways)), ", ".join(sorted(set(both_ways)))))
    if NEWPINS and not DRY:
        allp = json.load(open(dkp)) if os.path.exists(dkp) else {}
        allp.update(NEWPINS)
        json.dump(allp, open(dkp, "w"), indent=1, sort_keys=True)
        print("pinned from the card's own two passers (%d): %s"
              % (len(NEWPINS), ", ".join(v["name"] for v in NEWPINS.values())))
    if new_pins and not DRY:
        pins.update(new_pins)
        json.dump(pins, open(pins_path, "w"), indent=0, sort_keys=True)
    if DRY:
        print("DraftKings passers read for %d games" % len(dk_qbs))
        print("dry run -- nothing written")
        return
    qf = os.path.join(D, "data", "dk_qbs.json")
    try:
        allq = json.load(open(qf))
    except (OSError, ValueError):
        allq = {}
    allq.update(dk_qbs)
    json.dump(allq, open(qf, "w"), separators=(",", ":"), sort_keys=True)
    # PROPS and the moneylines go to site/prices.json, never into the page: a
    # price that moves must not mean rewriting the page, or a price update and
    # an edit to the page can never both happen at once (Jose, Sep 18, 2026)
    # merged over what is there: past weeks keep their prices, this run's games take theirs
    book = pricefile.read()
    book["PROPS"].update(props)
    for var in ("SCHED", "CFB"):
        m = re.search(r"var %s = (\[\[.*?\]\]);" % var, s, re.S)
        arr = json.loads(m.group(1))
        for g in arr:
            have = book[var].get(str(g[1]))
            row = list(have) if have else ["", "", "", ""]
            touched = False
            for i in (0, 1):
                v = sched_new.get((var, g[1], i))
                if v:
                    row[i * 2], row[i * 2 + 1] = v[0], v[1]
                    touched = True
            if touched:
                book[var][str(g[1])] = row
    pricefile.write(book)
    print("written: %d games in PROPS, prices.json only -- the page is untouched" % len(props))
    subprocess.run(["npx", "wrangler", "pages", "deploy", ".", "--project-name=the-arenasports", "--branch=main"],
                   cwd=D + "/site", capture_output=True, text=True)
    print("deployed")


if __name__ == "__main__":
    main()
