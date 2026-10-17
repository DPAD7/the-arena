"""DraftKings' own start time for every game and bout on the board.

   ESPN lists the TV slot; DraftKings the real start -- Alabama at Tennessee
   3:30 on ESPN, 3:45 on the book, and the card shut its prices at 3:30 with
   the game not on (Jose, Oct 17, 2026: "use the correct times ... DraftKings
   is more accurate because they're paying to be accurate"). A started game's
   startEventDate is the moment it actually kicked off.

   Written to site/prices.json KICKS {espn id: "YYYY-MM-DDTHH:MMZ"}, which the
   page lays over each row's time. Football is tied by both clubs and the day,
   a bout by both men's surnames and the night.

       python3 build/dk_kicks.py           write
       python3 build/dk_kicks.py --dry     say what it would change
"""
import datetime as dt
import json
import os
import sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
from read_dk import ask
from slip_track import Board, fold, last
import prices as pricefile

LEAGUES = {"nfl": 88808, "ncaaf": 87637}
UFC = (9034, 187059)    # the UFC and the Contender Series
DRY = "--dry" in sys.argv


def T(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def stamp(s):
    return T(s if s.endswith("Z") or "+" in s[10:] else s + "Z").astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def football(board):
    out = {}
    for lg, lid in LEAGUES.items():
        d = ask(None, None, "/sportscontent/dkusmd/v1/leagues/%d" % lid) or {}
        for e in d.get("events") or []:
            st = e.get("startEventDate")
            roles = {(p.get("venueRole") or "").lower(): p.get("name") for p in e.get("participants") or []}
            if not st or "away" not in roles or "home" not in roles:
                continue
            ca, ch = board.clubs(roles["away"]), board.clubs(roles["home"])
            for g, _ in board.rows:
                if g[3] in ca and g[4] in ch and abs((T(g[2]) - T(stamp(st))).total_seconds()) < 12 * 3600:
                    out[str(g[1])] = stamp(st)
    return out


def bouts(board):
    out = {}
    evs = []
    for lid in UFC:
        evs += (ask(None, None, "/sportscontent/dkusmd/v1/leagues/%d" % lid) or {}).get("events") or []
    for e in evs:
        st = e.get("startEventDate")
        names = [last(p.get("name")) for p in e.get("participants") or []]
        if not st or len(names) != 2:
            continue
        for f in board.fights:
            if {last(f[3]), last(f[5])} == set(names) and abs((T(f[2]) - T(stamp(st))).total_seconds()) < 12 * 3600:
                out[str(f[1])] = stamp(st)
    return out


def main():
    board = Board()
    kicks = football(board)
    kicks.update(bouts(board))
    rows = {str(g[1]): g[2] for g, _ in board.rows}
    rows.update({str(f[1]): f[2] for f in board.fights})
    moved = {k: v for k, v in kicks.items() if rows.get(k) != v}
    for k, v in sorted(moved.items(), key=lambda x: x[1]):
        print("  %s  board %s  DraftKings %s" % (k, rows.get(k), v))
    print("dk_kicks: %d starts read, %d differ from the board" % (len(kicks), len(moved)))
    if DRY:
        return
    book = pricefile.read()
    book.setdefault("KICKS", {}).update(kicks)
    pricefile.write(book)


if __name__ == "__main__":
    main()
