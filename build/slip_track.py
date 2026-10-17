"""A slip read off his screenshot, tied to the board and put in the wallet.

   site/functions/slip.js has Claude read the screenshot he double tapped and
   starts .github/workflows/slip.yml with the reading's key. This ties every
   leg to its game and to DraftKings' own selection id -- the shape the
   wallet's legs always have (bets-go-in-the-way-the-wallet-builds-them) --
   and posts the bet to /bets (Jose, Oct 17, 2026).

     a moneyline    the board's game by the club, DraftKings' id off the card
     a fight        the bout by the man's surname and the night
     a player prop  DraftKings' own event, the selection by the man and the
                    market, his ESPN id for the face
     anything else  kept with its game and its words, so it still shows

   A name is never matched across sources as a string where an id exists: a
   club is turned into the board's abbreviation through the recorded school
   names, a man is found inside the one game his leg came off.

       python3 build/slip_track.py --key 639278387459988247
       python3 build/slip_track.py --file reading.json --dry
"""
import datetime as dt
import hashlib
import json
import os
import re
import sys
from zoneinfo import ZoneInfo

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import mirror
from read_dk import ask

SITE = "https://the-arenasports.pages.dev"
BETS = SITE + "/bets?k=arena-001bff8ddf784985"
ET = ZoneInfo("America/New_York")
DRY = "--dry" in sys.argv
LEAGUE = {"nfl": 88808, "ncaaf": 87637}
CATS = (1000, 1001, 1003, 1185, 1342)

NFL = {
    "arizona": "ARI", "cardinals": "ARI", "atlanta": "ATL", "falcons": "ATL", "baltimore": "BAL", "ravens": "BAL",
    "buffalo": "BUF", "bills": "BUF", "carolina": "CAR", "panthers": "CAR", "chicago": "CHI", "bears": "CHI",
    "cincinnati": "CIN", "bengals": "CIN", "cleveland": "CLE", "browns": "CLE", "dallas": "DAL", "cowboys": "DAL",
    "denver": "DEN", "broncos": "DEN", "detroit": "DET", "lions": "DET", "green bay": "GB", "packers": "GB",
    "houston": "HOU", "texans": "HOU", "indianapolis": "IND", "colts": "IND", "jacksonville": "JAX", "jaguars": "JAX",
    "kansas city": "KC", "chiefs": "KC", "la chargers": "LAC", "los angeles chargers": "LAC", "chargers": "LAC",
    "la rams": "LAR", "los angeles rams": "LAR", "rams": "LAR", "las vegas": "LV", "raiders": "LV",
    "miami": "MIA", "dolphins": "MIA", "minnesota": "MIN", "vikings": "MIN", "new england": "NE", "patriots": "NE",
    "new orleans": "NO", "saints": "NO", "ny giants": "NYG", "new york giants": "NYG", "giants": "NYG",
    "ny jets": "NYJ", "new york jets": "NYJ", "jets": "NYJ", "philadelphia": "PHI", "eagles": "PHI",
    "pittsburgh": "PIT", "steelers": "PIT", "seattle": "SEA", "seahawks": "SEA", "san francisco": "SF",
    "49ers": "SF", "tampa bay": "TB", "buccaneers": "TB", "tennessee": "TEN", "titans": "TEN",
    "washington": "WSH", "commanders": "WSH",
}


def fold(s):
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", str(s or "").lower())
    return re.sub(r"[^a-z0-9 ]", "", s).strip()


def last(s):
    w = fold(s).split()
    return w[-1] if w else ""


def when(iso):
    t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ET)
    return t.strftime("%-I:%M %p")


def minus(o):
    return str(o or "").replace("-", "−")


class Board:
    def __init__(self):
        a = mirror.arrays()
        self.rows = [(g, "nfl") for g in a["SCHED"]] + [(g, "ncaaf") for g in a["CFB"]]
        self.fights = a["FIGHTS"]
        self.prices = json.load(open(D + "/site/prices.json"))
        self.cfb_names = {fold(k): v for k, v in json.load(open(D + "/data/cfb_names.json")).items()}
        self.cfb_school = json.load(open(D + "/data/cfb_schools.json"))
        self.people = {fold(k): v for k, v in json.load(open(D + "/data/cfb_people.json")).items()}
        self.dkp = json.load(open(D + "/data/dk_people.json"))
        self.abbrs = {g[3] for g, _ in self.rows} | {g[4] for g, _ in self.rows}
        self._events = {}

    def clubs(self, text):
        """Every board abbreviation the written club could be."""
        t = fold(text)
        out = set()
        up = str(text or "").strip().upper()
        if up in self.abbrs:
            out.add(up)
        if t in self.cfb_names:
            out.add(self.cfb_names[t])
        for k, v in NFL.items():
            if t == k or t.endswith(" " + k) or t.startswith(k + " "):
                out.add(v)
        return out

    def game(self, clubs, placed, other=""):
        """The one board game with that club nearest after the bet was placed."""
        both = self.clubs(other) if other else set()
        best = None
        for g, lg in self.rows:
            if not clubs & {g[3], g[4]}:
                continue
            if both and not both & {g[3], g[4]}:
                continue
            k = dt.datetime.fromisoformat(g[2].replace("Z", "+00:00"))
            gap = (k - placed).total_seconds()
            if gap < -8 * 3600 or gap > 9 * 86400:
                continue
            if best is None or abs(gap) < best[0]:
                best = (abs(gap), g, lg)
        return (best[1], best[2]) if best else (None, None)

    def event(self, lg, g):
        """DraftKings' own event for a board game, by both clubs' names."""
        names = {fold(self.cfb_school.get(g[3], g[3])), fold(self.cfb_school.get(g[4], g[4]))}
        if lg not in self._events:
            d = ask(None, None, "/sportscontent/dkusmd/v1/leagues/%d" % LEAGUE[lg]) or {}
            self._events[lg] = d.get("events") or []
        for e in self._events[lg]:
            ps = {fold(p.get("name")) for p in (e.get("participants") or [])}
            if lg == "ncaaf" and names <= ps:
                return str(e.get("id"))
            if lg == "nfl" and {g[3], g[4]} <= {a for p in ps for a in self.clubs(p)}:
                return str(e.get("id"))
        return None


def prop_sel(board, lg, g, leg):
    """DraftKings' selection for a man's prop, read off his own event."""
    eid = board.event(lg, g)
    if not eid:
        return None, None
    who, mk, line = last(leg.get("who")), fold(leg.get("market")), str(leg.get("line") or "").strip()
    ou = re.match(r"(over|under)\s*([\d.]+)", line, re.I)
    for c in CATS:
        d = ask(None, None, "/sportscontent/dkusmd/v1/events/%s/categories/%s" % (eid, c)) or {}
        mks = {m["id"]: m.get("name") or "" for m in d.get("markets") or []}
        for s in d.get("selections") or []:
            name = fold(mks.get(s.get("marketId"), ""))
            if who not in name.split() or (mk and mk not in name):
                continue
            lab = str(s.get("label") or "").strip()
            if ou:
                if not lab.lower().startswith(ou.group(1).lower()) or float(s.get("points") or -1) != float(ou.group(2)):
                    continue
            elif lab.replace(" ", "") != line.replace(" ", ""):
                continue
            pid = ""
            for p in s.get("participants") or []:
                if (p.get("type") or "") == "Player":
                    pid = (board.dkp.get(str(p.get("id"))) or {}).get("espn", "")
            return s.get("id"), pid
    return None, None


def tie(board, bet, leg):
    placed = bet["_placed"]
    who, mk = str(leg.get("who") or ""), str(leg.get("market") or "")
    out = {"market": "", "odds": minus(leg.get("odds")), "status": leg.get("status") or "open",
           "sgp": "1" if bet.get("type", "").upper().startswith("SGP") else ""}
    game_txt = str(leg.get("game") or "")
    sides = re.split(r"\s+(?:vs\.?|@|at)\s+", game_txt, flags=re.I)
    other = ""
    # a fight: the bout by the man's surname, the night of the bet
    for f in board.fights:
        k = dt.datetime.fromisoformat(f[2].replace("Z", "+00:00"))
        if not -8 * 3600 < (k - placed).total_seconds() < 9 * 86400:
            continue
        s = 0 if last(f[3]) == last(who) else 1 if last(f[5]) == last(who) else -1
        if s < 0:
            continue
        name = (f[3] if s == 0 else f[5]).split()[-1].upper()
        if re.search(r"moneyline|to win", mk, re.I):
            out.update(sel=(f[9] if s == 0 else f[11]) or "dk-ml-%s-%d" % (f[1], s), label=name + " ‖ ML")
        else:
            out.update(sel="dk-" + hashlib.md5((bet["id"] + who + mk + str(leg.get("line"))).encode()).hexdigest()[:12],
                       label=name + " ‖ " + (leg.get("line") or mk).upper(), market=mk + " " + who)
        out.update(pick=out["label"] + " · " + when(f[2]), g=str(f[1]), evn=f[3] + " vs " + f[5])
        return out
    # football: the club, from the man's tag or the club itself
    clubs = board.clubs(leg.get("team") or who)
    if not clubs:
        for side in sides:
            clubs |= board.clubs(side)
    for side in sides:
        if not board.clubs(side) & clubs:
            other = side
    # the opponent as written only breaks a tie: DraftKings' "IND" is Indiana
    # on a college slip and the Colts on the board (Oct 17, 2026)
    g, lg = board.game(clubs, placed, other)
    if not g:
        g, lg = board.game(clubs, placed)
    if not g:
        out.update(sel="dk-" + hashlib.md5((bet["id"] + who + mk).encode()).hexdigest()[:12],
                   label=(who + " " + (leg.get("line") or mk)).strip(), pick=(leg.get("line") or who), market=who + " " + mk)
        return out
    out.update(g=str(g[1]), evn=g[3] + " @ " + g[4])
    t = when(g[2])
    if re.fullmatch(r"\s*moneyline\s*", mk, re.I) and not leg.get("team"):
        ab = (clubs & {g[3], g[4]}).pop()
        s = 0 if ab == g[3] else 1
        row = (board.prices.get("SCHED" if lg == "nfl" else "CFB") or {}).get(str(g[1])) or []
        sel = row[1 + 2 * s] if len(row) > 1 + 2 * s else ""
        out.update(sel=sel or "dk-ml-%s-%s" % (g[1], ab), label=ab + " ML", pick=ab + " ML · " + t)
        return out
    sel, pid = prop_sel(board, lg, g, leg)
    if not pid:
        pid = board.people.get(fold(who), "")
    line = str(leg.get("line") or "").strip()
    out.update(sel=sel or "dk-" + hashlib.md5((bet["id"] + who + mk + line).encode()).hexdigest()[:12],
               market=who + " " + mk, pick=line or who, label=(last(who).title() + " " + line + " " +
               ("PTD" if re.search(r"passing touchdown", mk, re.I) else mk)).strip())
    if pid:
        out["pid"] = str(pid)
    return out


def money(x):
    try:
        return round(float(str(x).replace("$", "").replace(",", "")), 2)
    except ValueError:
        return 0.0


def main():
    if "--file" in sys.argv:
        reading = json.load(open(sys.argv[sys.argv.index("--file") + 1]))
    else:
        key = sys.argv[sys.argv.index("--key") + 1]
        r = rq.get(SITE + "/slip?key=" + key, headers={"x-ask-secret": os.environ["ASK_SECRET"]}, impersonate="chrome", timeout=30)
        r.raise_for_status()
        reading = r.json()
    board = Board()
    for bet in reading.get("bets") or []:
        try:
            placed = dt.datetime.fromisoformat(bet.get("placed") or "")
            placed = placed.replace(tzinfo=ET) if placed.tzinfo is None else placed
        except ValueError:
            placed = dt.datetime.now(ET)
        bet["_placed"] = placed
        bet["id"] = bet.get("id") or "board-dk" + re.sub(r"\D", "", str(bet.get("bet_id")))
        legs = [tie(board, bet, lg) for lg in bet.get("legs") or []]
        typ = str(bet.get("type") or "")
        typ = "Single" if len(legs) < 2 else "SGP" if typ.upper().startswith("SGP") else "Parlay"
        sent = {"id": bet["id"], "type": typ, "odds": minus(bet.get("odds")), "was": minus(bet.get("was") or bet.get("odds")),
                "wager": money(bet.get("wager")), "topay": money(bet.get("topay")), "boost": bet.get("boost") or "",
                "boosted": bool(bet.get("boost")), "placed": placed.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "status": "open", "from": "board", "legs": legs}
        print(json.dumps(sent, ensure_ascii=False, indent=1))
        loose = [l["label"] for l in legs if str(l.get("sel", "")).startswith("dk-")]
        if loose:
            print("kept by its words, no DraftKings id: " + ", ".join(loose))
        if not DRY:
            r = rq.post(BETS, json={"unsent": sent["id"], "sent": sent}, impersonate="chrome", timeout=30)
            print("posted", sent["id"], r.status_code, r.text[:80])


if __name__ == "__main__":
    main()
