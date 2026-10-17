"""A DraftKings share link, put in the wallet exactly as the bet was placed.

   DraftKings' Share on a bet makes a link (sportsbook.draftkings.com/social/
   post/<key>). The post carries the whole bet as DraftKings holds it -- the
   bet id, stake, payout, every leg with its selection id and the price it
   filled at, a nested same-game parlay's legs too -- under
   api.draftkings.com/comments/feed/post/details.json, as base64 "betJSON".
   No login, no screenshot, nothing read by eye (Jose, Oct 17, 2026: he sent
   the link of a 6-pick SGPx).

   Each leg is tied to its board game by build/slip_track.py and keeps
   DraftKings' own selection id.

       python3 build/dk_share.py <link>          add it to the wallet
       python3 build/dk_share.py <link> --dry    print what it would add
"""
import base64
import datetime as dt
import json
import os
import re
import sys

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import slip_track

POST = "https://api.draftkings.com/comments/feed/post/details.json"
HEAD = {"origin": "https://sportsbook.draftkings.com", "referer": "https://sportsbook.draftkings.com/"}


def bet_of(link):
    key = re.search(r"/post/([0-9a-f-]{36})", link).group(1)
    d = rq.post(POST, json={"postKey": key}, headers=HEAD, impersonate="chrome", timeout=30).json()
    for e in (d.get("post") or {}).get("postEntries") or []:
        props = (e.get("metadataProperties") or {}).get("properties") or {}
        for p in props if isinstance(props, list) else [props]:
            if p.get("name") == "betJSON":
                return json.loads(base64.b64decode(p["value"] + "==="))
    raise SystemExit("no bet on that post")


def leg_of(o, nested):
    offer, out = o.get("offerLabel") or "", o.get("outcomeLabel") or ""
    m = re.match(r"(.+?) \((\w+)\) (.+)$", offer)
    if m:
        who, team, market, line = m.group(1), m.group(2), m.group(3), out
    else:
        who, team, market, line = out, "", re.sub(r"^Live ", "", offer), ""
    return {"who": who, "team": team, "market": market, "line": line,
            "odds": o.get("playedOddsAmerican") or o.get("enterpriseDisplayOdds") or "",
            "game": "%s @ %s" % (o.get("awayTeamName"), o.get("homeTeamName")),
            "status": o.get("status") or "open", "_sel": o.get("providerSelectionId"), "_sgp": nested}


def main():
    link = [a for a in sys.argv[1:] if a.startswith("http")][0]
    b = bet_of(link)
    legs = []
    for o in b.get("combinationOutcomes") or []:
        if o.get("nestedSGPSelections"):
            legs += [leg_of(x, True) for x in o["nestedSGPSelections"]]
        else:
            legs.append(leg_of(o, False))
    reading = {"bet_id": b["betId"], "type": "SGP" if b.get("type", "").lower().startswith("sgp") else "Parlay",
               "odds": b.get("originalDisplayOdds") or (b.get("combinations") or [{}])[0].get("totalEnterpriseDisplayOdds"),
               "wager": b.get("stake"), "topay": b.get("potentialPayout"), "boost": "",
               "placed": dt.datetime.fromisoformat(b["placedDate"].replace("Z", "+00:00")).astimezone(slip_track.ET).replace(tzinfo=None).isoformat(),
               "legs": legs}
    board = slip_track.Board()
    reading["_placed"] = dt.datetime.fromisoformat(reading["placed"]).replace(tzinfo=slip_track.ET)
    reading["id"] = "board-dk" + reading["bet_id"]
    tied = []
    for lg in legs:
        t = slip_track.tie(board, reading, lg)
        # DraftKings' own id -- except a moneyline the board prices under
        # another id (a live moneyline, Alabama in-game): it wins or loses with
        # the board's, which the wallet and the clock settle by; the book's is
        # kept beside it
        if lg["market"].lower() == "moneyline" and t.get("sel") and not str(t["sel"]).startswith("dk-"):
            if lg["_sel"] and lg["_sel"] != t["sel"]:
                t["dksel"] = lg["_sel"]
        else:
            t["sel"] = lg["_sel"] or t.get("sel")
        t["sgp"] = "1" if lg["_sgp"] else ""
        tied.append(t)
    sent = {"id": reading["id"], "type": reading["type"] if len(tied) > 1 else "Single",
            "odds": slip_track.minus(reading["odds"]), "was": slip_track.minus(reading["odds"]),
            "wager": slip_track.money(reading["wager"]), "topay": slip_track.money(reading["topay"]),
            "boost": "", "boosted": False, "placed": b["placedDate"][:19] + "Z", "status": "open",
            "from": "board", "legs": tied}
    print(json.dumps(sent, ensure_ascii=False, indent=1))
    if "--dry" not in sys.argv:
        r = rq.post(slip_track.BETS, json={"unsent": sent["id"], "sent": sent}, impersonate="chrome", timeout=30)
        print("posted", sent["id"], r.status_code, r.text[:80])


if __name__ == "__main__":
    main()
