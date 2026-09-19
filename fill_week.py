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

sys.path.insert(0, "/Users/joe/qbspy/build")
import pagefile
import prices as pricefile
from read_dk import ask

D = os.path.dirname(os.path.abspath(__file__))
DRY = "--dry" in sys.argv
DB = "/Users/joe/qbspy/data/qbspy.db"
NOW = dt.datetime.now(dt.timezone.utc)
HORIZON = NOW + dt.timedelta(days=8)
LEAGUE = {"nfl": 88808, "ncaaf": 87637}


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
                     "oid": sel.get("id") or "", "who": who.get("name") or ""})
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


def main():
    s = pagefile.read()
    club, person = register()
    # college passers pinned to their ESPN id as DraftKings writes them; a man first
    # met by an identical written name on his own card is written here, so the pin
    # is a recorded fact after that and not a match made again at read time
    pins_path = D + "/cfb_people.json"
    pins = json.load(open(pins_path)) if os.path.exists(pins_path) else {}
    new_pins = {}
    props = {}
    unsettled, by_name, flipped, unoffered = [], [], [], []
    sched_new = {}
    for league, var in (("nfl", "SCHED"), ("ncaaf", "CFB")):
        arr = json.loads(re.search(r"var %s = (\[\[.*?\]\]);" % var, s, re.S).group(1))
        games = [g for g in arr if NOW < T(g[2]) <= HORIZON]
        if not games:
            continue
        events = dk_events(league)
        keyed = {}
        # college spellings come from ESPN's own scoreboard (cfb_names.json), the
        # same source the board's abbreviations come from
        cfb = json.load(open(D + "/cfb_names.json")) if league == "ncaaf" else {}
        for e in events:
            # college first: DraftKings' "Pittsburgh" is PITT on a Saturday, and the NFL
            # register answering PIT left twelve games unpriced on Sep 16, 2026
            a = (cfb.get(e["away"]) or club.get(e["away"])) if league == "ncaaf" else (club.get(e["away"]) or cfb.get(e["away"]))
            h = (cfb.get(e["home"]) or club.get(e["home"])) if league == "ncaaf" else (club.get(e["home"]) or cfb.get(e["home"]))
            if a and h:
                keyed[(a, h, e["start"][:10])] = e
            elif league == "nfl":
                unsettled.append(e["away"] + " @ " + e["home"])
        print("%s: %d games to kick, %d DraftKings events, %d tied by the register"
              % (league.upper(), len(games), len(events), len(keyed)))
        for g in games:
            eid, kick, away, home = g[1], T(g[2]), g[3], g[4]
            e = keyed.get((away, home, g[2][:10])) or keyed.get((away, home, (kick - dt.timedelta(days=1)).strftime("%Y-%m-%d")))
            if not e:
                # a neutral-site game DraftKings lists the other way round from ESPN
                # (Kansas @ Arizona State at Wembley, Sep 19, 2026). Taken, and said.
                r = keyed.get((home, away, g[2][:10]))
                if r:
                    e = dict(r, away=r["home"], home=r["away"])
                    flipped.append("%s/%s (DraftKings writes %s @ %s)" % (away, home, r["away"], r["home"]))
            if not e and league == "ncaaf":
                # the register may not hold the college spelling: same day, same abbreviation prefix
                cands = [x for x in events if x["start"][:10] == g[2][:10]
                         and x["away"].split()[0].upper() == away and x["home"].split()[0].upper() == home]
                e = cands[0] if len(cands) == 1 else None
                if e:
                    by_name.append(away + "/" + home)
            if not e:
                offered = {x for ev in events for x in (cfb.get(ev["away"]) or club.get(ev["away"]), cfb.get(ev["home"]) or club.get(ev["home"]))}
                if away not in offered and home not in offered:
                    unoffered.append("%s/%s" % (away, home))
                else:
                    unsettled.append("%s/%s (%s)" % (away, home, league))
                continue
            entry = {}
            # moneyline
            ml = [r for r in pull("/sportscontent/dkusmd/v1/events/%s/categories/492" % e["id"]) if r["market"] == "Moneyline"]
            for r in ml:
                i = side_of(r["label"], e["away"], e["home"])
                if i is not None:
                    sched_new[(var, eid, i)] = (american(r["odds"]), r["oid"])
            # the two passers, by id through person_name; else the identical written name
            qbs = [(g[5], str(g[6])), (g[7], str(g[8]))]
            def is_him(written, i):
                name, pid = qbs[i]
                if not name:
                    return False
                # DraftKings tags college men with their club, "Jayden Maiava (USC)";
                # the tag is not part of the name and the register never saw it
                written = re.sub(r"\s*\([A-Za-z&.\- ]+\)$", "", written or "")
                if person.get(written) == pid or pins.get(written) == pid:
                    return True
                if written == name:
                    if league == "ncaaf":
                        new_pins[written] = pid
                        by_name.append(written)
                    return True
                return False
            ptd = [[None, None], [None, None]]
            for r in pull("/sportscontent/dkusmd/v1/events/%s/categories/1000" % e["id"]):
                if not r["market"].endswith("Passing Touchdowns") or r["label"] not in ("1+", "2+"):
                    continue
                for i in (0, 1):
                    if is_him(r["who"], i):
                        ptd[i][int(r["label"][0]) - 1] = [american(r["odds"]), r["oid"]]
            entry["ptd"] = ptd
            # anytime touchdowns for both leagues: the college card draws them, the
            # NFL card does not, but the ledger tracks them (Jose, Sep 16, 2026:
            # "I want all the ptd and atd that are available and we will just track them all")
            atd = [[None, None], [None, None]]
            for r in pull("/sportscontent/dkusmd/v1/events/%s/categories/1003" % e["id"]):
                slot = 0 if r["market"] == "Anytime TD Scorer" else 1 if r["market"] == "2+ TDs" else None
                if slot is None:
                    continue
                for i in (0, 1):
                    if is_him(r["label"], i) or is_him(r["who"], i):
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
                for i in (0, 1):
                    if is_him(r["label"], i) or is_him(r["who"], i):
                        h2h[i] = [american(r["odds"]), r["oid"]]
            entry["h2h"] = h2h
            props[eid] = entry
            got = sum(1 for side in ptd for x in side if x)
            print("  %-9s dk %-9s ML %s  PTD %d/4  ATD %d/4%s" % (away + "/" + home, e["id"],
                  "yes" if (var, eid, 0) in sched_new else "no", got,
                  sum(1 for side in entry.get("atd", []) for x in side if x),
                  "  H2H %d/2" % sum(1 for x in entry.get("h2h", []) if x)))
    if unsettled:
        print("not tied to a DraftKings event (%d): %s" % (len(unsettled), "; ".join(sorted(set(unsettled))[:12])))
    if flipped:
        print("home and away disagree with DraftKings, board order kept (%d): %s" % (len(flipped), "; ".join(flipped)))
    if unoffered:
        print("DraftKings offers nothing on (%d): %s" % (len(unoffered), "; ".join(unoffered)))
    if by_name:
        print("pinned on an identical written name on his own card, now in cfb_people.json (%d): %s" % (len(set(by_name)), ", ".join(sorted(set(by_name))[:10])))
    if new_pins and not DRY:
        pins.update(new_pins)
        json.dump(pins, open(pins_path, "w"), indent=0, sort_keys=True)
    if DRY:
        print("dry run -- nothing written")
        return
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
    subprocess.run(["npx", "wrangler", "pages", "deploy", ".", "--project-name=sports-odds", "--branch=main"],
                   cwd=D + "/site", capture_output=True, text=True)
    print("deployed")


if __name__ == "__main__":
    main()
