"""The board's prices, in a file of their own.

   They used to be written into master.html, so every price that moved meant
   rewriting the page -- which meant a price update and an edit to the page
   could not both happen at once. One of the two always lost. Now they live in
   site/prices.json and the page reads them on load.

   What the page still carries is the last known set, which is what a reader
   sees for the moment before the file lands, and what he sees if it never
   does. Nothing writes those numbers any more; they only ever get staler, and
   harmlessly so.

   The shape:

       {"SCHED":  {game id: [price, oid, price, oid]},     away, then home
        "CFB":    {game id: [price, oid, price, oid]},
        "FIGHTS": {bout id: [price, oid, price, oid]},
        "PROPS":  {game id: ...},                          as the page holds it
        "FPROPS": {bout id: ...}}

   Usage:  python3 prices.py --from-page     lift what the page holds into the
                                             file, once, to start it off
           python3 prices.py --tidy          take the event-keyed collisions out
           python3 prices.py                 print what the file holds

   (Jose, Sep 18, 2026)
"""
import json
import os
import re
import sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(D, "site", "prices.json")

# which columns of each row carry the two moneylines and their DraftKings ids
COLS = {"SCHED": (9, 10, 11, 12), "CFB": (10, 11, 12, 13), "FIGHTS": (8, 9, 10, 11)}
# what a row is keyed by: a game by its ESPN id, a bout by its own
# a game by its ESPN id, a bout by its own -- index 1 in all three arrays.
# FIGHTS[0] is the EVENT id, which every bout on a card shares, so keying on
# it made the last bout written stand for the whole bill (Jose, Sep 18, 2026)
KEY = {"SCHED": 1, "CFB": 1, "FIGHTS": 1}


def read():
    """What the file holds, or an empty set of shelves."""
    if os.path.exists(OUT):
        try:
            d = json.load(open(OUT))
        except Exception:
            d = {}
    else:
        d = {}
    for k in ("SCHED", "CFB", "FIGHTS", "PROPS", "FPROPS"):
        d.setdefault(k, {})
    return d


_EVENTS = None


def event_ids():
    """The ids that stand for a whole fight card rather than for one bout.

       FIGHTS[0] is the event -- every bout on a bill carries the same one --
       and FIGHTS[1] is the bout. Keying a price on the event made the last
       bout written stand for the whole card. Nothing has keyed them that way
       since Sep 18, 2026, but this file is merged into and never pruned, so a
       day later 172 of those collisions were still sitting in it, one per
       bout, each holding some other fight's price.

       An id counts as an event where it is some row's field 0 and no row's
       field 1. That is read off the board, not guessed from how the number
       looks: nothing here decides anything by the shape of a string.
    """
    global _EVENTS
    if _EVENTS is None:
        try:
            page = open(os.path.join(D, "master.html")).read()
            arr = rows(page, "FIGHTS") or []
        except Exception:
            arr = []
        bouts = set(str(r[1]) for r in arr if len(r) > 1)
        _EVENTS = set(str(r[0]) for r in arr if r) - bouts
    return _EVENTS


def tidy(d):
    """Take every event-keyed collision back out. Returns how many went."""
    gone = 0
    bad = event_ids()
    if not bad:
        return 0
    for shelf in ("FIGHTS", "FPROPS", "KICKS"):
        held = d.get(shelf)
        if not isinstance(held, dict):
            continue
        for k in [k for k in held if str(k) in bad]:
            del held[k]
            gone += 1
    return gone


def write(d):
    tidy(d)
    json.dump(d, open(OUT, "w"), separators=(",", ":"))
    split(d)


def split(d):
    """One file an event, in site/prices/<id>.json.

       The board used to pull the whole 159 KB of prices every minute, for
       every card on it, whether the game had finished in February or had not
       started. A card asks for its own prices now, and a finished one asks
       once and never again (Jose, Sep 22, 2026: "it needs per card and once
       it's final it doesn't keep fetching").

       Each file holds what that one event has:

           {"ml": [price, oid, price, oid], "props": {...}}
    """
    out = os.path.join(os.path.dirname(OUT), "prices")
    os.makedirs(out, exist_ok=True)
    ids = set()
    for shelf in ("SCHED", "CFB", "FIGHTS"):
        ids |= set((d.get(shelf) or {}).keys())
    for shelf in ("PROPS", "FPROPS"):
        ids |= set((d.get(shelf) or {}).keys())
    kept = 0
    for eid in ids:
        one = {}
        for shelf in ("SCHED", "CFB", "FIGHTS"):
            v = (d.get(shelf) or {}).get(eid)
            if v:
                one["ml"] = v
                break
        for shelf in ("PROPS", "FPROPS"):
            v = (d.get(shelf) or {}).get(eid)
            if v:
                one["props"] = v
                break
        if not one:
            continue
        json.dump(one, open(os.path.join(out, "%s.json" % eid), "w"),
                  separators=(",", ":"))
        kept += 1
    print("prices/: %d events, one file each" % kept)


def rows(page, var):
    """The array as the page holds it, or None."""
    m = re.search(r"var %s = (\[\[.*?\]\]);" % var, page, re.S)
    return json.loads(m.group(1)) if m else None


def put(d, var, row, price0, oid0, price1, oid1):
    """One row's two moneylines, keyed the way the page keys it."""
    d.setdefault(var, {})[str(row[KEY[var]])] = [price0, oid0, price1, oid1]


def from_page(page):
    """Lift every price the page carries into the file's shape."""
    d = read()
    n = 0
    for var in ("SCHED", "CFB", "FIGHTS"):
        arr = rows(page, var)
        if not arr:
            continue
        a, b, c, e = COLS[var]
        for row in arr:
            if len(row) <= e:
                continue
            if not (row[a] or row[c]):
                continue        # nothing priced yet; leave the shelf empty
            put(d, var, row, row[a], row[b], row[c], row[e])
            n += 1
    for var in ("PROPS", "FPROPS"):
        m = re.search(r"var %s = (\{.*?\});\n" % var, page, re.S)
        if m:
            d[var] = json.loads(m.group(1))
    return d, n


def main():
    if "--from-page" in sys.argv:
        page = open(os.path.join(D, "master.html")).read()
        d, n = from_page(page)
        write(d)
        print("prices.json: %d priced games and bouts, %d games in PROPS, %d bouts in FPROPS"
              % (n, len(d["PROPS"]), len(d["FPROPS"])))
        return
    if "--tidy" in sys.argv:
        d = read()
        gone = tidy(d)
        write(d)
        print("prices.json: %d event-keyed collisions removed" % gone)
        return
    d = read()
    print("prices.json: %s"
          % ", ".join("%s %d" % (k, len(v)) for k, v in d.items()))


if __name__ == "__main__":
    main()
