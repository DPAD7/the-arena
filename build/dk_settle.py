"""Every tracked slip settled by DraftKings' own word.

   A slip added from a share link keeps the post it came from. The post
   carries DraftKings' copy of the bet, and DraftKings marks each leg and the
   bet won or lost there as it settles them -- any sport, any promotion, a
   boxing night ESPN never lists (Jose, Oct 17, 2026: "we can do the
   settlement based off DraftKings. Everything is attached to DraftKings").

   For each open slip with a post: read the bet, write each leg's won or lost
   onto the leg with the same DraftKings selection id (a nested same-game
   parlay's legs too), and the bet's own result once DraftKings has one.
   Only what DraftKings has settled is written; nothing is inferred.

       python3 build/dk_settle.py          settle and write
       python3 build/dk_settle.py --dry    say what it would write
"""
import base64
import json
import os
import sys
import time

from curl_cffi import requests as rq

BETS = "https://the-arenasports.pages.dev/bets?k=arena-001bff8ddf784985"
POST = "https://api.draftkings.com/comments/feed/post/details.json"
HEAD = {"origin": "https://sportsbook.draftkings.com", "referer": "https://sportsbook.draftkings.com/"}
DRY = "--dry" in sys.argv
DONE = ("won", "lost")


def book_bet(key):
    d = rq.post(POST, json={"postKey": key}, headers=HEAD, impersonate="chrome", timeout=30).json()
    for e in (d.get("post") or {}).get("postEntries") or []:
        props = (e.get("metadataProperties") or {}).get("properties") or {}
        for p in props if isinstance(props, list) else [props]:
            if p.get("name") == "betJSON":
                return json.loads(base64.b64decode(p["value"] + "==="))
    return None


def word(s):
    s = str(s or "").lower()
    return "won" if s in ("won", "win") else "lost" if s in ("lost", "lose", "loss") else ""


def main():
    sent = rq.get(BETS, impersonate="chrome", timeout=30).json().get("sent") or []
    changed = 0
    for bet in sent:
        if word(bet.get("status")) or not bet.get("post"):
            continue
        try:
            b = book_bet(bet["post"])
        except Exception as ex:
            print("  %s: unread (%s)" % (bet["id"], ex))
            continue
        if not b:
            continue
        said = {}
        for o in b.get("combinationOutcomes") or []:
            for x in (o.get("nestedSGPSelections") or [o]):
                if word(x.get("status")):
                    said[x.get("providerSelectionId")] = word(x["status"])
        moved = False
        for lg in bet.get("legs") or []:
            st = said.get(lg.get("sel")) or said.get(lg.get("dksel"))
            if st and word(lg.get("status")) != st:
                lg["status"] = st
                moved = True
        whole = word(b.get("status"))
        if whole and word(bet.get("status")) != whole:
            bet["status"] = whole
            bet["settledAt"] = int(time.time() * 1000)
            moved = True
        if moved:
            changed += 1
            print("  %s: %s, legs %s" % (bet["id"], bet.get("status"), [lg.get("status") for lg in bet.get("legs") or []]))
            if not DRY:
                rq.post(BETS, json={"unsent": bet["id"], "sent": bet}, impersonate="chrome", timeout=30)
    print("dk_settle: %d slip(s) moved by DraftKings' word" % changed)


if __name__ == "__main__":
    main()
