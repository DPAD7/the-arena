"""The college moneylines the pricer never caught, from ESPN's stored odds.

   fill_week.py prices a game only while it is still to kick, so a college
   Saturday that passed before the board reached it has empty moneyline
   slots. ESPN keeps the closing line per competition, DraftKings' own, and
   that is what this writes into the CFB rows -- only where a slot is empty,
   never over a price the board already holds.

   Usage:  python3 cfb_ml.py            (writes and deploys nothing; run the
                                         page build afterwards)
           python3 cfb_ml.py --dry
"""
import datetime as dt
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY = "--dry" in sys.argv
NOW = dt.datetime.now(dt.timezone.utc)
ODDS = ("https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/"
        "events/%s/competitions/%s/odds")


def money(v):
    if v is None:
        return None
    n = int(v)
    return ("+%d" % n) if n > 0 else str(n)


def one(eid):
    for _ in range(3):
        try:
            r = rq.get(ODDS % (eid, eid), impersonate="chrome124", timeout=45)
            if r.status_code != 200:
                continue
            best = None
            for it in r.json().get("items") or []:
                name = ((it.get("provider") or {}).get("name") or "")
                a = money((it.get("awayTeamOdds") or {}).get("moneyLine"))
                h = money((it.get("homeTeamOdds") or {}).get("moneyLine"))
                if a and h:
                    if "draftkings" in name.lower():
                        return a, h
                    best = best or (a, h)
            return best
        except Exception:
            pass
    return None


def main():
    s = open(D + "/master.html").read()
    m = re.search(r"var CFB = (\[\[.*?\]\]);", s, re.S)
    C = json.loads(m.group(1))
    want = [g for g in C if dt.datetime.fromisoformat(g[2].replace("Z", "+00:00")) < NOW and not (g[10] and g[12])]
    print("played college games with a moneyline missing: %d" % len(want))
    with ThreadPoolExecutor(8) as ex:
        got = list(ex.map(lambda g: one(g[1]), want))
    filled = 0
    for g, pair in zip(want, got):
        if not pair:
            continue
        # the slot only where it is empty; a price the board holds stands
        if not g[10]:
            g[10], g[11] = pair[0], ""
        if not g[12]:
            g[12], g[13] = pair[1], ""
        filled += 1
    print("filled from ESPN's closing line: %d | still missing: %d" % (filled, len(want) - filled))
    if DRY or not filled:
        return
    s = s[:m.start(1)] + json.dumps(C, separators=(",", ":")) + s[m.end(1):]
    open(D + "/master.html", "w").write(s)
    doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
           '<meta name="theme-color" content="#000000">\n'
           '<meta name="robots" content="noindex">\n<meta name="referrer" content="no-referrer">\n</head>\n<body>\n')
    open(D + "/site/index.html", "w").write(doc + s + "\n</body>\n</html>\n")
    print("written")


if __name__ == "__main__":
    main()
