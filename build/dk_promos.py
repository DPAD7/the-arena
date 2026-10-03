"""DraftKings' boosts, off its own public promotions -- the list its home page
   shows a visitor who is not signed in (Jose, Oct 3, 2026: "add the bet that
   it applies to and then add to wallet").

   Each profit boost on the list is kept with what it applies to: one game
   ("Alabama @ Mississippi State 50% Profit Boost"), or a league for a day
   ("College Football 50% Profit Boost", "NFL Week 4 Sunday 50% Profit
   Boost"), its percent, when it runs, the minimum odds, the fewest legs and
   the maximum wager the public terms state. The maximum is DraftKings'
   public one; his own account can carry a larger one, so the wallet lets him
   change it.

   Written to site/promos.json:
       [{"id", "head", "pct", "start", "end", "sport", "game", "gid",
         "minOdds", "minLegs", "maxWager", "types"}]

       python3 build/dk_promos.py
"""
import datetime as dt
import json
import os
import re
import sys

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile

OUT = os.path.join(D, "site", "promos.json")
URL = "https://api.draftkings.com/en/api/promotions/v2/promotions/query"
BODY = {"filterByProduct": True, "geoLocation": "US-DC", "siteExperience": "US-DC-SB",
        "productName": "Sportsbook", "language": "en",
        "zones": [{"zoneName": "WebCarousel", "zoneIdentifierId": "LNLHNDNData", "inliningEntityIds": {}},
                  {"zoneName": "WebHomeScreen", "zoneIdentifierId": "Z3YASNFData", "inliningEntityIds": {}}]}
SPORTS = (("college football", "college-football"), ("cfb", "college-football"),
          ("nfl", "nfl"), ("ufc", "mma"), ("mma", "mma"), ("boxing", "boxing"))


def odds_of(text):
    m = re.search(r"(?:minimum|total bet) odds (?:must be |of )?([+\-−]\d{3,4})", text, re.I)
    return m.group(1).replace("−", "-") if m else ""


def legs_of(text):
    m = re.search(r"(\d+)\+ ?leg", text, re.I) or re.search(r"minimum (?:of )?(\d+) (?:legs|selections)", text, re.I)
    return int(m.group(1)) if m else 1


def max_of(text):
    m = re.search(r"max(?:imum)?\s*\$?(\d+(?:\.\d+)?)\s*wager", text, re.I) or \
        re.search(r"maximum (?:wager|bet|stake)[^$\d]{0,40}\$(\d+(?:\.\d+)?)", text, re.I)
    return float(m.group(1)) if m else None


def board_games():
    """Every game on the board still to come, with its clubs' names, for tying a
       one-game boost to its card."""
    page = pagefile.read()
    names = {}
    try:
        cfb = json.load(open(os.path.join(D, "data", "cfb_names.json")))
        for k, v in (cfb.items() if isinstance(cfb, dict) else []):
            if isinstance(v, str):
                names.setdefault(v, set()).add(k.lower())
    except (OSError, ValueError):
        pass
    out = []
    for var, sport in (("SCHED", "nfl"), ("CFB", "college-football")):
        m = re.search(r"  var %s = (\[\[.*?\]\]);" % var, page, re.S)
        for g in json.loads(m.group(1)) if m else []:
            out.append((sport, str(g[1]), g[2], g[3], g[4]))
    return out, names


def tie(game, games, names):
    """A one-game boost's written fixture -- "Alabama @ Mississippi State" --
       to the board's game, by both clubs' names; one match or none."""
    m = re.match(r"(.+?)\s+(?:@|vs\.?|at)\s+(.+)", game, re.I)
    if not m:
        return ""
    a, h = m.group(1).strip().lower(), m.group(2).strip().lower()
    hits = []
    for sport, gid, start, ab, hb in games:
        an = names.get(ab, set()) | {ab.lower()}
        hn = names.get(hb, set()) | {hb.lower()}
        if (a in an or any(a == n or n.startswith(a + " ") for n in an)) and \
           (h in hn or any(h == n or n.startswith(h + " ") for n in hn)):
            hits.append(gid)
    return hits[0] if len(hits) == 1 else ""


def main():
    r = rq.post(URL, json=BODY, headers={"referer": "https://sportsbook.draftkings.com/",
                                         "origin": "https://sportsbook.draftkings.com"},
                impersonate="chrome", timeout=30)
    if r.status_code != 200:
        print("dk_promos: DraftKings answered %d; promos.json left as it was" % r.status_code)
        return 0
    seen, out = set(), []
    games, names = board_games()
    now = dt.datetime.now(dt.timezone.utc)
    for z in r.json().get("zones") or []:
        for p in z.get("promotions") or []:
            md = p.get("merchandisingData") or {}
            head = md.get("promotionHeadline") or ""
            if p.get("promotionId") in seen or not re.search(r"(\d+)% ?(?:Profit|Parlay|SGP)? ?Boost", head, re.I):
                continue
            seen.add(p.get("promotionId"))
            terms = " ".join(str(md.get(k) or "") for k in ("terms", "loggedOutTerms", "additionalDetail", "promotionDescription"))
            end = p.get("expirationDate") or ""
            try:
                if dt.datetime.fromisoformat(end.replace("Z", "+00:00")[:26] + "+00:00" if "+" not in end else end) < now:
                    continue
            except ValueError:
                pass
            low = (head + " " + (md.get("promotionDescription") or "")).lower()
            sport = next((s for k, s in SPORTS if k in low), "")
            gm = re.match(r"(.+?(?:@|vs\.?)\s+.+?)\s+\d+%", head)
            game = gm.group(1).strip() if gm else ""
            types = [t for t in ("single", "sgp", "sgpx", "parlay") if re.search(r"\b%s\b" % t, low)]
            out.append({
                "id": p.get("publicPromotionId") or str(p.get("promotionId")),
                "head": head, "pct": int(re.search(r"(\d+)%", head).group(1)),
                "start": p.get("startDate"), "end": end, "sport": sport,
                "game": game, "gid": "",
                "minOdds": odds_of(terms), "minLegs": legs_of(head + " " + terms),
                "maxWager": max_of(terms), "types": types or ["any"],
            })
    # a one-game boost is tied to its card, and takes that card's league
    for o in out:
        if o["game"]:
            o["gid"] = tie(o["game"], games, names)
            o["sport"] = o["sport"] or next((g[0] for g in games if g[1] == o["gid"]), "")
    json.dump(out, open(OUT, "w"), indent=1)
    for o in out:
        print("dk_promos: %-48s %d%%  %s  min %s  max %s  legs %d%s" % (
            o["head"][:48], o["pct"], o["sport"] or "-", o["minOdds"] or "-", o["maxWager"] or "-",
            o["minLegs"], ("  game %s" % o["gid"]) if o["gid"] else ""))
    print("dk_promos: %d boosts" % len(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
