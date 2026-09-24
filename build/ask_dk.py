"""The double tap: the prices a card is missing, asked for there and then.

   The sweep prices the board three times a day, and a price DraftKings posts
   between two sweeps sits unread until the next one. A double tap on the
   board asks for the games in front of him now; the site starts this on
   GitHub, and it reads only those games -- nothing else, no file written, no
   deploy -- and hands what it found back to the site, which keeps it and
   gives it to the page (Jose, Sep 23, 2026).

   Nothing here is a new reader. A game is priced by fill_week.py's own
   steps and a bout by fill_fights.py's, so a price read on a tap is the same
   reading the sweep would have made. What comes back is the exact shape of
   site/prices/<id>.json, so the page merges it with no translation:

       a game   {"ml": [price, oid, price, oid],
                 "props": {"ptd": [[1+, 2+, 3+], [...]], "atd": [...], "h2h": [a, h]}}
       a bout   {"ml": [price, oid, price, oid], "props": {<the sheet's keys>}}

   A man is placed by his DraftKings number through data/dk_people.json,
   never by his written name. A game the register cannot tie to a DraftKings
   event is said to be unmapped, never guessed at; the college fallback that
   matches on the first word of a club's name is left off here for the same
   reason.

   Usage:  python3 build/ask_dk.py --games 401772810,401773017 --key K
           python3 build/ask_dk.py --games 401772810 --dry    print, post nothing

   The answer goes to $ASK_SITE/ask (the board by default), signed with
   $ASK_SECRET.
"""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile
import whoname
import fill_week
import fill_fights

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW = dt.datetime.now(dt.timezone.utc)
SITE = os.environ.get("ASK_SITE", "https://the-arenasports.pages.dev").rstrip("/")


def arg(name):
    if name in sys.argv:
        at = sys.argv.index(name)
        if at + 1 < len(sys.argv):
            return sys.argv[at + 1]
    return None


def T(x):
    return dt.datetime.fromisoformat(x.replace("Z", "+00:00"))


def rows(page, var):
    m = re.search(r"var %s = (\[\[.*?\]\]);" % var, page, re.S)
    return json.loads(m.group(1)) if m else []


def anything(v):
    """Whether a price object holds a single price."""
    if isinstance(v, list):
        if len(v) == 2 and isinstance(v[0], str) and isinstance(v[1], str):
            return bool(v[0])
        return any(anything(x) for x in v)
    if isinstance(v, dict):
        return any(anything(x) for k, x in v.items() if k != "rounds")
    return bool(v) and isinstance(v, str)


def games(asked, board, why):
    """NFL and college: fill_week.py's tie, then its reading, per game."""
    out = {}
    by_league = {}
    for gid in asked:
        for league, var in (("nfl", "SCHED"), ("ncaaf", "CFB")):
            g = board.get((var, gid))
            if g:
                by_league.setdefault(league, []).append(g)
    if not by_league:
        return out
    # the sweep copies register.db into place as qbspy.db; a tap has no need
    # of the copy and reads the register where it sits
    reg = os.path.join(D, "data", "register.db")
    if os.path.exists(reg) and not os.path.exists(fill_week.DB):
        fill_week.DB = reg
    club, _person = fill_week.register()
    dkp = os.path.join(D, "data", "dk_people.json")
    dkpeople = json.load(open(dkp)) if os.path.exists(dkp) else {}
    for league, rows_ in by_league.items():
        cfb = json.load(open(D + "/data/cfb_names.json")) if league == "ncaaf" else {}
        events = fill_week.dk_events(league)
        if not events:
            for g in rows_:
                why[g[1]] = "DraftKings answered with no %s events" % league
            continue
        keyed = fill_week.tie_events(league, events, club, cfb)
        for g in rows_:
            gid = str(g[1])
            if T(g[2]) <= NOW:
                why[gid] = "started"
                continue
            e, how = fill_week.event_for(g, league, keyed, events, club, cfb, loose=False)
            if not e:
                why[gid] = "unmapped (%s)" % how
                continue
            ml, entry = fill_week.price_event(e, [g[6], g[8]], league, dkpeople)
            one = {}
            if ml:
                row = ["", "", "", ""]
                for i, (price, oid) in ml.items():
                    row[i * 2], row[i * 2 + 1] = price, oid
                one["ml"] = row
            one["props"] = entry
            if not anything(one):
                why[gid] = "nothing priced (DraftKings event %s)" % e["id"]
                continue
            out[gid] = one
            print("  %-10s dk %-9s %s%s" % (g[3] + "/" + g[4], e["id"],
                  "ML yes" if "ml" in one else "ML no",
                  "  (%s)" % how if how else ""))
    return out


def bouts(asked, board, why):
    """UFC and the Contender Series: fill_fights.py's bout, then its sheet."""
    out = {}
    rows_ = [board[("FIGHTS", gid)] for gid in asked if ("FIGHTS", gid) in board]
    if not rows_:
        return out
    held = json.load(open(fill_fights.ARCHIVE)) if os.path.exists(fill_fights.ARCHIVE) else {}
    theirs = fill_fights.dk_bouts()
    for f in rows_:
        gid = str(f[1])
        left, right = f[3], f[5]
        eid, when = theirs.get((whoname.key(left), whoname.key(right))) or (None, "")
        # a bout already read once carries its DraftKings number in the
        # archive; that number is the tie, and the names only find a bout
        # never read before -- the same key fill_fights.py prices it by
        known = (held.get(gid) or {}).get("dk")
        if known:
            if eid and eid != known:
                print("  %s: the archive says %s, their board says %s -- the archive's taken"
                      % (gid, known, eid))
            eid = known
        if not eid:
            why[gid] = "unmapped (not on DraftKings by these names)"
            continue
        start = when or f[2]
        if T(start) <= NOW:
            why[gid] = "started"
            continue
        mkts = fill_fights.pull(eid)
        if not mkts:
            why[gid] = "nothing came back (DraftKings event %s)" % eid
            continue
        ml = ["", "", "", ""]
        for lab, got in (fill_fights.dig(mkts, "Moneyline") or {}).items():
            if fill_fights.fold(lab) == fill_fights.fold(left):
                ml[0], ml[1] = got
            elif fill_fights.fold(lab) == fill_fights.fold(right):
                ml[2], ml[3] = got
        one = {}
        if ml[0] or ml[2]:
            one["ml"] = ml
        one["props"] = fill_fights.sheet(mkts, left, right, fill_fights.rounds_of(mkts))
        if not anything(one):
            why[gid] = "nothing priced (DraftKings event %s)" % eid
            continue
        out[gid] = one
        print("  %-22s v %-22s dk %s" % (left, right, eid))
    return out


def shape(v):
    """What a price object is made of, with the prices taken out: a slot is
       a slot whether it is priced or empty."""
    if isinstance(v, dict):
        return {k: shape(x) for k, x in sorted(v.items())}
    if isinstance(v, list):
        if len(v) == 2 and all(isinstance(x, str) for x in v):
            return "slot"
        if all(isinstance(x, str) for x in v):
            return "row%d" % len(v)
        return [shape(x) for x in v]
    if v is None:
        return "slot"
    return type(v).__name__


def send(body):
    secret = os.environ.get("ASK_SECRET") or ""
    if not secret:
        sys.exit("no ASK_SECRET -- the site will not take an unsigned answer")
    data = json.dumps(body, separators=(",", ":")).encode()
    for tries in range(3):
        try:
            req = urllib.request.Request(SITE + "/ask", data=data, method="POST",
                                         headers={"content-type": "application/json",
                                                  "x-ask-secret": secret,
                                                  "user-agent": "the-arena-ask"})
            with urllib.request.urlopen(req, timeout=20) as r:
                print("posted to %s/ask: %s" % (SITE, r.read().decode()[:200]))
                return True
        except Exception as e:
            print("post failed (%s), try %d" % (e, tries + 1))
            time.sleep(2)
    return False


def main():
    asked = [x.strip() for x in (arg("--games") or "").split(",") if x.strip().isdigit()]
    key = arg("--key") or ""
    dry = "--dry" in sys.argv
    if not asked:
        sys.exit("nothing asked: --games id1,id2")
    page = pagefile.read()
    board = {}
    for var in ("SCHED", "CFB", "FIGHTS"):
        for r in rows(page, var):
            board[(var, str(r[1]))] = r
    why = {}
    for gid in asked:
        if not any((var, gid) in board for var in ("SCHED", "CFB", "FIGHTS")):
            why[gid] = "unmapped (not on the board)"
    print("asked about %d: %s" % (len(asked), ", ".join(asked)))
    prices = {}
    prices.update(games(asked, board, why))
    prices.update(bouts(asked, board, why))
    missing = [gid for gid in asked if gid not in prices]
    for gid in missing:
        why.setdefault(gid, "nothing priced")
        print("  %s: %s" % (gid, why[gid]))
    body = {"key": key, "prices": prices, "missing": missing, "why": why,
            "read": NOW.isoformat(timespec="seconds")}
    if dry:
        print(json.dumps(body, indent=1))
        for gid, one in prices.items():
            f = os.path.join(D, "site", "prices", "%s.json" % gid)
            if not os.path.exists(f):
                print("%s: no file to hold it against" % gid)
                continue
            have = json.load(open(f))
            same = shape(have) == shape(one)
            print("%s: shape %s the file's" % (gid, "matches" if same else "DIFFERS from"))
            if not same:
                print("   file: %s\n   read: %s" % (json.dumps(shape(have)), json.dumps(shape(one))))
            for part in ("ml", "props"):
                if part in have and part in one:
                    print("   %s %s" % (part, "same prices as the file" if have[part] == one[part] else "prices moved since the file"))
        print("dry run -- nothing posted")
        return
    if not send(body):
        sys.exit("the site never took the answer")


if __name__ == "__main__":
    main()
