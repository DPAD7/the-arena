"""Who is hurt, for every man the ledger carries.

   The wire outranks the record: a man who threw four last week is not a leg
   if he is on a table Monday morning, and the board had no way of saying so.
   ESPN keeps it on the athlete himself --

       sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/<yr>
           /athletes/<id>

   -- where `injuries` carries the status word, what it is, which side, when it
   happened and when he is expected back, with the reporter's own note.

   Written to site/wire.json, keyed by ESPN id so nothing is matched by name:

       {"4431611": {"status": "Questionable", "abbr": "Q", "type": "Hamstring",
                    "side": "Right", "since": "2026-09-20T20:54Z",
                    "returns": "2026-09-28",
                    "note": "Williams will undergo imaging ..."}}

   A man ESPN says nothing about is left out of the file entirely -- an absence
   is not a clean bill of health, it is an absence, and the board draws nothing
   for it.

       python3 build/wire.py
"""
import datetime
import json
import os
from concurrent.futures import ThreadPoolExecutor

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(D, "site", "wire.json")
WHO = ("https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
       "/seasons/%d/athletes/%s")


def year():
    now = datetime.datetime.now(datetime.timezone.utc)
    # the season is named for the year it starts in, and January belongs to it
    return now.year if now.month >= 3 else now.year - 1


def ask(pid):
    try:
        r = rq.get(WHO % (year(), pid), impersonate="chrome", timeout=20)
        if r.status_code != 200:
            return pid, None
        hurt = (r.json() or {}).get("injuries") or []
    except Exception:
        return pid, None
    if not hurt:
        return pid, None
    # the newest first, which is how ESPN hands them over
    it = hurt[0]
    d = it.get("details") or {}
    return pid, {"status": it.get("status"),
                 "abbr": ((it.get("type") or {}).get("abbreviation")),
                 "type": d.get("type"), "side": d.get("side"),
                 "since": it.get("date"), "returns": d.get("returnDate"),
                 "note": it.get("shortComment") or it.get("longComment")}


def main():
    led = json.load(open(os.path.join(D, "site", "ledger.json")))
    ids = []
    for wk in led:
        for r in led[wk]:
            if str(r[2]) not in ids:
                ids.append(str(r[2]))
    out = {}
    with ThreadPoolExecutor(8) as ex:
        for pid, hurt in ex.map(ask, ids):
            if hurt and hurt.get("status"):
                out[pid] = hurt
    json.dump(out, open(OUT, "w"), separators=(",", ":"))
    name = {}
    for wk in led:
        for r in led[wk]:
            name[str(r[2])] = (r[0], r[1])
    for pid, h in sorted(out.items(), key=lambda kv: name.get(kv[0], ("",))[0]):
        who, club = name.get(pid, ("?", "?"))
        print("   %-20s %-4s %-12s %-10s back %s" % (
            who, club, h["status"], h.get("type") or "-", h.get("returns") or "-"))
    print("%d of %d men on the wire, written to %s" % (len(out), len(ids), OUT))


if __name__ == "__main__":
    main()
