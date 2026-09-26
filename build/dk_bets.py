"""His open DraftKings bets and his balance, read straight from the book.

   My Bets is not a page of HTML: the site opens a socket and asks for the
   bets page as data -- every slip with its legs, the price each leg filled
   at, and DraftKings' own selection id, which is the same id the board keeps
   on its price buttons. The socket wants a two-minute token, and the token is
   minted from his login cookies. Held as a secret, those cookies let a sweep
   read his bets with nothing from him (Jose, Sep 26, 2026: "I'm not trying to
   always do that").

   The cookies come from the DK_COOKIES secret on GitHub, or from
   ~/.arena/dk_cookies.json on his Mac -- never from the repo.

   What it writes: POST /bets on the site, the shape the page reads --
     { balance, bets: [ {id, type, odds, wager, topay, placed, boosted,
                         legs: [ {sel, pick, market, odds, status} ] } ] }
   Open bets only: the board settles them itself, and the balance already
   carries whatever has paid.

       python3 build/dk_bets.py          read and send
       python3 build/dk_bets.py --dry    read and print
"""
import json
import os
import re
import sys
import uuid

from curl_cffi import requests as rq

DRY = "--dry" in sys.argv
BOARD = "https://the-arenasports.pages.dev/bets?k=arena-001bff8ddf784985"
JWT = "https://gaming-us-md.draftkings.com/api/wager/v1/generateEnterpriseJWT"
SOCKET = "wss://gateway.northamerica-northeast2.prod.dkapis.com/dkusmd/shelby/api/v1/websocket?format=json&jwt="
BALANCE = "https://api.draftkings.com/finapi/v1/userbalances/%s/sportsbook/USD?format=json"
HEAD = {"origin": "https://sportsbook.draftkings.com", "referer": "https://sportsbook.draftkings.com/"}
LOCAL = os.path.expanduser("~/.arena/dk_cookies.json")


def login():
    raw = os.environ.get("DK_COOKIES")
    if raw:
        return json.loads(raw)
    if os.path.exists(LOCAL):
        return json.load(open(LOCAL))
    return None


def plain(o):
    return str(o or "").replace("−", "-")


def page(ws, skip):
    ws.send(json.dumps({"jsonrpc": "2.0", "method": "InitializeBetsPageRequest", "id": str(uuid.uuid4()),
                        "params": {"betsRequest": {"filter": {"status": "Open"},
                                                   "pagination": {"count": 25, "skip": skip},
                                                   "ScoreboardType": "EventScore"},
                                   "cashOut": {"information": True, "pullOperations": True}, "locale": "en"}}))
    for _ in range(20):
        m = ws.recv()[0]
        m = m.decode() if isinstance(m, bytes) else m
        if '"result"' in m or '"error"' in m:
            d = json.loads(m)
            if d.get("error"):
                raise RuntimeError(str(d["error"])[:200])
            return ((d.get("result") or {}).get("initial") or {}).get("bets") or []
    return []


def surname(n):
    n = re.sub(r"\s*\([A-Za-z&.\- ]+\)$", "", n or "").strip()
    b = [x for x in n.split() if not re.match(r"^(Jr\.?|Sr\.?|II|III|IV|V)$", x)]
    return b[-1] if b else n


def label(x):
    """The leg as the board writes one: Stockton 2+ PTD, Chambliss H2H, Texas ML."""
    pick, mk = x.get("selectionDisplayName") or "", x.get("marketDisplayName") or ""
    m = re.match(r"(.+?) Passing Touchdowns$", mk)
    if m:
        return "%s %s PTD" % (surname(m.group(1)), pick)
    if "Passing Yards Moneyline" in mk:
        return "%s H2H" % surname(pick)
    m = re.match(r"(.+?) (?:Anytime TD|Touchdown)", mk)
    if "Anytime" in mk or "TD Scorer" in mk:
        return "%s 1+ ATD" % surname(pick)
    if mk == "Moneyline":
        return "%s ML" % pick
    return ("%s %s" % (pick, mk)).strip()


def legs_of(b):
    """Every leg, with a same-game parlay inside a parlay opened into its own
       legs: DraftKings writes it as one "2 Pick SGP" selection with its
       price, and the legs under it carry none (Sep 26, 2026)."""
    out = []
    for x in b.get("selections") or []:
        nest = x.get("nestedSGPSelections") or []
        for y in (nest or [x]):
            out.append({"sel": y.get("selectionId"), "pick": y.get("selectionDisplayName"),
                        "market": y.get("marketDisplayName"), "label": label(y),
                        "odds": "" if nest else plain(y.get("displayOdds")),
                        "sgp": plain(x.get("displayOdds")) if nest else "",
                        "status": (y.get("settlementStatus") or y.get("status") or "").lower()})
    return out


def main():
    held = login()
    if not held:
        print("dk_bets: no login held (DK_COOKIES), nothing read")
        return 0
    jar, uid = held.get("cookies") or {}, held.get("uid")
    s = rq.Session(impersonate="chrome124")
    r = s.get(JWT, cookies=jar, headers=HEAD, timeout=30)
    if r.status_code != 200 or "token" not in r.text:
        print("dk_bets: LOGIN EXPIRED -- the cookies no longer mint a token (%d); export them again" % r.status_code)
        if not DRY:
            rq.post(BOARD, data=json.dumps({"expired": True}), headers={"content-type": "application/json"},
                    impersonate="chrome124", timeout=30)
        return 1
    tok = r.json()["token"]

    bal = None
    if uid:
        b = s.get(BALANCE % uid, cookies=jar, headers=HEAD, timeout=30)
        if b.status_code == 200:
            bal = b.json().get("PlayableAndWithdrawableAmount")

    ws = s.ws_connect(SOCKET + tok, headers=HEAD)
    raw, skip = [], 0
    while True:
        got = page(ws, skip)
        raw += got
        if len(got) < 25 or skip > 200:
            break
        skip += 25
    ws.close()

    bets = []
    for b in raw:
        # a profit boost does not move the slip's own price: it rides in
        # "bonus" / "playerBonus", with the boosted price and what it pays
        # ("+468" boosted 50% to "+703", $803 on $100 -- Sep 26, 2026)
        bo = b.get("bonus") or {}
        pb = b.get("playerBonus") or {}
        bodds = plain(bo.get("boostDisplayOdds") or pb.get("boostedDisplayOdds"))
        bpay = bo.get("boostMaxReturns") or pb.get("maxWinningAmount")
        bets.append({
            "id": b.get("receiptId") or b.get("betId"),
            "type": b.get("type"),
            "odds": bodds or plain(b.get("displayOdds")),
            "was": plain(b.get("originalDisplayOdds") or b.get("displayOdds")),
            "boosted": bool(bodds),
            "boost": ("+%d%% %s" % (round((bo.get("boostValue") or 0) * 100) or pb.get("boostPercentage") or 0,
                                     "profit boost" if "Profit" in (bo.get("boostType") or pb.get("type") or "") else "boost")) if bodds else "",
            "wager": b.get("stake"),
            "topay": bpay or b.get("potentialReturns"),
            "placed": b.get("placementDate"),
            "status": "open",
            "legs": legs_of(b)})
    print("dk_bets: balance %s, %d open bets, %d legs"
          % (bal, len(bets), sum(len(b["legs"]) for b in bets)))
    if DRY:
        print(json.dumps(bets, indent=1)[:2000])
        return 0
    if bal is None:
        print("dk_bets: no balance read, nothing sent")
        return 1
    p = rq.post(BOARD, data=json.dumps({"balance": bal, "bets": bets}),
                headers={"content-type": "application/json"}, impersonate="chrome124", timeout=30)
    print("dk_bets: sent", p.status_code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
