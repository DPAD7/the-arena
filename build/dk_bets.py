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
       python3 build/dk_bets.py --keep   only keep the login alive (daily)
"""
import json
import os
import re
import sys
import uuid

from curl_cffi import requests as rq

DRY = "--dry" in sys.argv
KEEP = "--keep" in sys.argv
BOARD = "https://the-arenasports.pages.dev/bets?k=arena-001bff8ddf784985"
JWT = "https://gaming-us-md.draftkings.com/api/wager/v1/generateEnterpriseJWT"
SOCKET = "wss://gateway.northamerica-northeast2.prod.dkapis.com/dkusmd/shelby/api/v1/websocket?format=json&jwt="
BALANCE = "https://api.draftkings.com/finapi/v1/userbalances/%s/sportsbook/USD?format=json"
HEAD = {"origin": "https://sportsbook.draftkings.com", "referer": "https://sportsbook.draftkings.com/"}
LOCAL = os.path.expanduser("~/.arena/dk_cookies.json")


def seed():
    """The login as it was exported: the secret, or the file on his Mac."""
    raw = os.environ.get("DK_COOKIES")
    if raw:
        return raw
    if os.path.exists(LOCAL):
        return open(LOCAL).read()
    return None


def box(raw):
    """A lock keyed on the exported login itself, so only a run that holds the
       secret can open what is kept on the site, and a fresh export (a new
       secret) simply starts over from itself."""
    import base64
    import hashlib
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM(hashlib.sha256(("dk-jar:" + raw).encode()).digest()), base64


def kept(raw):
    """The login as DraftKings last re-issued it, kept locked on the site.
       Every token DraftKings mints hands back fresh login cookies -- the
       long ones good for a year, the session one for a week (Sep 26, 2026)
       -- so a read that keeps them keeps the login alive, and the HAR is
       exported once rather than again and again (Jose: "how do we not have
       to do it again and again")."""
    try:
        g = rq.get(BOARD + "&jar=1", impersonate="chrome124", timeout=30).json()
        blob = g.get("jar")
        if not blob:
            return None
        aes, b64 = box(raw)
        b = b64.b64decode(blob)
        return json.loads(aes.decrypt(b[:12], b[12:], None))
    except Exception:
        return None


def keep(raw, held, fresh):
    """Lock the re-issued cookies and put them on the site."""
    jar = dict(held.get("cookies") or {})
    jar.update(fresh)
    out = dict(held, cookies=jar)
    aes, b64 = box(raw)
    iv = os.urandom(12)
    blob = b64.b64encode(iv + aes.encrypt(iv, json.dumps(out).encode(), None)).decode()
    r = rq.post(BOARD, data=json.dumps({"jar": blob}), headers={"content-type": "application/json"},
                impersonate="chrome124", timeout=30)
    print("dk_bets: login re-issued and kept (%d cookies, %d)" % (len(fresh), r.status_code))


def sent():
    """The login his own browser sent last (tools/dk-bets), read back with
       ASK_SECRET. It is the freshest there is: it comes from the tab he is
       logged in on, so a login DraftKings has expired mends itself the next
       time DraftKings is open in Chrome."""
    sec = os.environ.get("ASK_SECRET")
    if not sec:
        return None
    try:
        g = rq.get(BOARD + "&login=1", headers={"x-ask-secret": sec}, impersonate="chrome124", timeout=30).json()
        return g if g.get("cookies") else None
    except Exception:
        return None


def logins():
    """Every login there is, newest first: the one DraftKings last re-issued
       to the reader (kept), the browser's own (sent), then the export. Each
       is tried in turn for a token; the first that mints is the one
       (Sep 30, 2026: the browser's cookies, sent minutes before, would not
       mint while the kept ones did, and the run gave up on the first)."""
    raw = seed()
    base = json.loads(raw) if raw else {}
    out = []
    # the browser's own first: it is the login as it stands. The kept jar,
    # DraftKings' re-issue merged over an older set, has answered 401 while
    # the browser's minted (Sep 30, 2026, 11:47), so it is only a fallback
    fresh = sent()
    if fresh:
        out.append(("sent", dict(base, cookies=fresh["cookies"])))
    k = kept(raw) if raw else None
    if k:
        out.append(("kept", k))
    if raw:
        out.append(("export", base))
    return out, raw


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
    # a milestone, one man or several: "Jaylen Waddle to Have 40+ Receiving
    # Yards, Davante Adams to Have 40+ Receiving Yards" is "Waddle + Adams 40+
    # Rec" -- the first word alone put "Jaylen" on the bag (Sep 27, 2026)
    ms = re.findall(r"([^,]+?) to (?:Have|Record|Score) (\d+\+) ([A-Za-z ]+?)(?:,|$)", pick)
    if ms:
        short = {"Receiving Yards": "Rec", "Rushing Yards": "Rush", "Passing Yards": "Pass Yds",
                 "Receptions": "Rec", "Passing Touchdowns": "PTD", "Touchdowns": "TD"}
        stats = {(n, short.get(st.strip(), st.strip())) for _, n, st in ms}
        who = " + ".join(surname(m[0].strip()) for m in ms)
        if len(stats) == 1:
            n, st = stats.pop()
            return "%s %s %s" % (who, n, st)
        return ", ".join("%s %s %s" % (surname(m[0].strip()), m[1], short.get(m[2].strip(), m[2].strip())) for m in ms)
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


def first(y, x, *keys):
    for o in (y, x):
        for k in keys:
            v = o.get(k)
            if isinstance(v, dict):
                v = v.get("id") or v.get("name")
            if v:
                return v
    return None


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
                        "status": (y.get("settlementStatus") or y.get("status") or "").lower(),
                        # the game it is on, by the book's own event number: a leg
                        # the board has no price for still finds its game through
                        # site/dkevents.json (Sep 29, 2026)
                        "ev": str(first(y, x, "eventId", "eventID", "event_id") or ""),
                        "evn": first(y, x, "eventName", "eventDisplayName", "eventDescription") or "",
                        # which fields the book sends, names only, until the
                        # event id is confirmed in them
                        "_k": sorted(k for k in y.keys() if "vent" in k.lower() or "game" in k.lower())})
    return out


def main():
    tries, raw = logins()
    if not tries:
        print("dk_bets: no login held (DK_COOKIES), nothing read")
        return 0
    held = jar = uid = s = r = None
    for name, cand in tries:
        held = cand
        jar, uid = held.get("cookies") or {}, held.get("uid")
        s = rq.Session(impersonate="chrome124")
        r = s.get(JWT, cookies=jar, headers=HEAD, timeout=30)
        print("dk_bets: the %s login: %d" % (name, r.status_code))
        if r.status_code == 200 and "token" in r.text:
            break
    fresh = {c.name: c.value for c in s.cookies.jar}
    if r.status_code == 200 and "token" in r.text and fresh and not DRY and raw:
        keep(raw, held, fresh)
    if KEEP:
        # the daily touch: the login is kept alive, the bets are not read
        alive = r.status_code == 200 and "token" in r.text
        print("dk_bets: keep -- the login is %s" % ("alive and re-issued" if alive else "EXPIRED (%d); Jose signs in on Chrome" % r.status_code))
        return 0 if alive else 1
    if r.status_code != 200 or "token" not in r.text:
        print("dk_bets: LOGIN EXPIRED -- the cookies no longer mint a token (%d); export them again" % r.status_code)
        # what DraftKings said and which cookies were offered -- names only,
        # never a value -- so the cause can be read off the run (Sep 30, 2026)
        print("dk_bets: said %s" % re.sub(r'"token"\s*:\s*"[^"]+"', '"token":"-"', r.text)[:200].replace("\n", " "))
        print("dk_bets: cookies offered (%d): %s" % (len(jar), " ".join(sorted(jar))[:600]))
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
